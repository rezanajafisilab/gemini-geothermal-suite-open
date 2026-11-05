"""Tests for the sandbox and model generation, run with a scripted model so they need no Ollama."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemini_agent import modelgen, sandbox
from gemini_agent.llm import ModelUnavailable, ScriptedLLM
from gemini_agent.modelgen import (
    SPECS,
    GenerationResult,
    Registry,
    check_model,
    clean_code,
    find_spec,
    generate,
    iter_generate,
    spec_message,
)

GOOD_CHILLER = """import math


def adsorption_chiller(drive_temp_c, heat_available_mw, cooling_water_temp_c,
                       chilled_water_temp_c):
    tg = drive_temp_c + 273.15
    tc = cooling_water_temp_c + 273.15
    te = chilled_water_temp_c + 273.15
    min_drive_temp_c = 2 * cooling_water_temp_c - chilled_water_temp_c
    load = min(1.0, max(0.0, (drive_temp_c - min_drive_temp_c) / 20.0))
    drive_heat_mw = load * heat_available_mw
    cop_carnot = (1 - tc / tg) * te / (tc - te) if tg > tc else 0.0
    cop = min(0.65, 0.4 * cop_carnot) if drive_heat_mw > 0 else 0.0
    cold_mw = cop * drive_heat_mw
    return {
        "cold_mw": cold_mw,
        "drive_heat_mw": drive_heat_mw,
        "rejected_heat_mw": drive_heat_mw + cold_mw,
        "cop": cop,
        "min_drive_temp_c": min_drive_temp_c,
    }
"""

# Forgets the cold in the heat rejected: the energy balance must catch it.
LEAKY_CHILLER = GOOD_CHILLER.replace(
    '"rejected_heat_mw": drive_heat_mw + cold_mw', '"rejected_heat_mw": drive_heat_mw'
)

GOOD_ATES = """import math


def store(energy_mwh, delta_k, thickness_m):
    if energy_mwh <= 0 or delta_k <= 0:
        return 0.0, 0.0
    v = energy_mwh * 3.6e9 / (4.18e6 * delta_k)
    r = math.sqrt(4.18e6 * v / (2.8e6 * math.pi * thickness_m))
    return r, min(0.9, max(0.0, 1 - 3.8 * (2 / thickness_m + 2 / r)))


def ates(heat_stored_mwh, cold_stored_mwh, warm_temp_c, cold_temp_c, aquifer_temp_c,
         thickness_m):
    rw, hw = store(heat_stored_mwh, warm_temp_c - aquifer_temp_c, thickness_m)
    rc, hc = store(cold_stored_mwh, aquifer_temp_c - cold_temp_c, thickness_m)
    return {
        "heat_recovered_mwh": hw * heat_stored_mwh,
        "heat_loss_mwh": heat_stored_mwh - hw * heat_stored_mwh,
        "heat_recovery": hw,
        "cold_recovered_mwh": hc * cold_stored_mwh,
        "cold_loss_mwh": cold_stored_mwh - hc * cold_stored_mwh,
        "cold_recovery": hc,
        "warm_radius_m": rw,
        "cold_radius_m": rc,
    }
"""


def reply(code, reason="Follows the physics steps."):
    """Return a model reply in the generation schema."""
    return {"reason": reason, "code": code}


class TestCheckCode(unittest.TestCase):
    """The syntax-tree allow-list."""

    def test_forbidden_import_rejected(self):
        """Only math and numpy may be imported, in any import form."""
        for code in (
            "import os\ndef f(x):\n    return {}\n",
            "import subprocess as s\ndef f(x):\n    return {}\n",
            "from socket import socket\ndef f(x):\n    return {}\n",
            "def f(x):\n    import sys\n    return {}\n",
            "import numpy.linalg\ndef f(x):\n    return {}\n",
            "from numpy import load\ndef f(x):\n    return {}\n",
        ):
            violations = sandbox.check_code(code, "f")
            self.assertTrue(violations, code)
            self.assertTrue(any("import" in v for v in violations), violations)
        self.assertEqual(
            sandbox.check_code(
                "import math\nimport numpy as np\n" "def f(x):\n    return {}\n", "f"
            ),
            [],
        )

    def test_open_and_escape_hatches_rejected(self):
        """File access, eval, getattr, dunders, frames and str.format are refused."""
        cases = {
            "open('/etc/passwd').read()": "open",
            "eval('1+1')": "eval",
            "getattr(x, 'real')": "getattr",
            "x.__class__": "__class__",
            "(i for i in [x]).gi_frame": "gi_frame",
            "'{0.__class__}'.format(x)": ".format",
            "__builtins__": "__builtins__",
        }
        for expr, word in cases.items():
            code = f"def f(x):\n    y = {expr}\n    return {{'y': 1.0}}\n"
            violations = sandbox.check_code(code, "f")
            self.assertTrue(any(word in v for v in violations), (expr, violations))
            self.assertTrue(violations[0].startswith("line 2:"), violations)

    def test_structure_rules(self):
        """One named function, no classes, globals, with blocks or top-level work."""
        self.assertIn("There is no top-level function named f.", sandbox.check_code("x = 1\n", "f"))
        code = (
            "class A:\n    pass\n"
            "def f(x):\n    global y\n    with x:\n        pass\n    return {}\n"
            "f(1)\n"
        )
        text = " ".join(sandbox.check_code(code, "f"))
        for word in ("classes", "global", "with blocks", "top level"):
            self.assertIn(word, text)
        self.assertIn("does not parse", sandbox.check_code("def f(:\n", "f")[0])

    def test_signature_must_match_the_inputs(self):
        """The function takes exactly the spec's named arguments."""
        code = "def f(a, b):\n    return {}\n"
        self.assertEqual(sandbox.check_code(code, "f", ["b", "a"]), [])
        self.assertIn("exactly these arguments", sandbox.check_code(code, "f", ["a", "c"])[0])
        code = "def f(**kw):\n    return {}\n"
        self.assertIn("named arguments only", sandbox.check_code(code, "f", ["a"])[0])


class TestRun(unittest.TestCase):
    """The child process."""

    def test_good_code_runs_in_one_batch(self):
        """Outputs come back per case; numpy numbers become floats; prints are dropped."""
        code = (
            "import math\nimport numpy as np\n\n"
            "def f(x):\n    print('noise')\n"
            "    return {'y': np.float64(math.sqrt(x)), 'n': np.int64(2)}\n"
        )
        result = sandbox.run(code, "f", [{"x": 4}, {"x": 9}])
        self.assertTrue(result.ok, result)
        self.assertEqual(result.outputs, [{"y": 2.0, "n": 2.0}, {"y": 3.0, "n": 2.0}])
        self.assertIn("timeout 5 s", result.limits)

    def test_errors_are_reported_per_case_with_the_line(self):
        """A failing case names the line; the other cases still run."""
        result = sandbox.run("def f(x):\n    return {'y': 1 / x}\n", "f", [{"x": 0}, {"x": 2}])
        self.assertFalse(result.ok)
        self.assertEqual(result.outputs[1], {"y": 0.5})
        self.assertIn("line 2: ZeroDivisionError", result.errors[0])
        result = sandbox.run("def f(x):\n    return [x]\n", "f", [{"x": 1}])
        self.assertIn("not a dict", result.errors[0])

    def test_violations_stop_the_run(self):
        """Code that breaks a rule never starts a process."""
        with mock.patch("subprocess.run") as started:
            result = sandbox.run("import os\ndef f(x):\n    return {}\n", "f", [{"x": 1}])
        started.assert_not_called()
        self.assertFalse(result.ok)
        self.assertTrue(result.violations)

    def test_infinite_loop_times_out(self):
        """An endless loop is killed at the timeout."""
        result = sandbox.run("def f(x):\n    while True:\n        x += 1\n", "f", [{"x": 1}], 1.0)
        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)
        self.assertLess(result.seconds, 4.0)

    def test_child_refuses_what_the_checker_missed(self):
        """With the checker bypassed, the child still has no os import and no open."""
        with mock.patch.object(sandbox, "check_code", return_value=[]):
            result = sandbox.run(
                "def f(x):\n    import os\n    return {}\n"
                "def g(x):\n    return {'n': len(open('x').read())}\n",
                "f",
                [{"x": 1}],
            )
            self.assertIn("ImportError: import of os is not allowed", result.errors[0])
            result = sandbox.run(
                "def g(x):\n    return {'n': len(open('x').read())}\n", "g", [{"x": 1}]
            )
            self.assertIn("NameError", result.errors[0])

    @unittest.skipUnless(sandbox.HAVE_RESOURCE, "resource limits need Linux or macOS")
    def test_memory_limit(self):
        """A huge allocation fails inside the child instead of filling the machine."""
        result = sandbox.run("def f(x):\n    return {'n': len([0] * 10 ** 10)}\n", "f", [{"x": 1}])
        self.assertFalse(result.ok)
        self.assertTrue("MemoryError" in result.errors[0] or result.error, result)

    def test_windows_falls_back_to_the_timeout(self):
        """Without resource, only the timeout is listed and the code still runs."""
        with mock.patch.object(sandbox, "HAVE_RESOURCE", False):
            result = sandbox.run("def f(x):\n    return {'y': x}\n", "f", [{"x": 1}])
        self.assertTrue(result.ok)
        self.assertEqual(result.limits, ["timeout 5 s"])


class TestSpecs(unittest.TestCase):
    """The component specs and their checks."""

    def test_good_adsorption_chiller_passes(self):
        """The reference chiller passes every check, with no cold below 48 °C."""
        attempt = check_model(SPECS["adsorption_chiller"], GOOD_CHILLER)
        self.assertTrue(attempt.passed, attempt.problems())
        self.assertEqual(len(attempt.checks), 9)
        cold_45 = attempt.outputs[1]
        self.assertEqual((cold_45["cold_mw"], cold_45["min_drive_temp_c"]), (0.0, 48.0))

    def test_good_ates_passes_and_bad_ates_fails(self):
        """The reference ATES passes; recovering more than was stored fails."""
        spec = SPECS["ates"]
        self.assertTrue(check_model(spec, GOOD_ATES).passed)
        greedy = GOOD_ATES.replace("min(0.9, max(0.0, 1 - 3.8", "(1.2 + 0 * (3.8")
        failed = {c.name for c in check_model(spec, greedy).failed_checks}
        self.assertIn("Recovers no more than was stored", failed)
        self.assertIn("Recovery between 0 and 0.9", failed)

    def test_checks_catch_physics_errors(self):
        """A COP above Carnot, cold below the minimum drive and a falling output all fail."""
        spec = SPECS["adsorption_chiller"]
        cases = {
            "COP within the Carnot limit": GOOD_CHILLER.replace(
                "min(0.65, 0.4 * cop_carnot)", "0.9"
            ),
            "No cold below the minimum drive temperature": GOOD_CHILLER.replace(
                "max(0.0, (drive_temp_c", "max(0.1, (drive_temp_c"
            ),
            "Cold rises with drive temperature": GOOD_CHILLER.replace(
                "cold_mw = cop * drive_heat_mw", "cold_mw = cop * drive_heat_mw * 50 / drive_temp_c"
            ),
        }
        for name, code in cases.items():
            failed = {c.name for c in check_model(spec, code).failed_checks}
            self.assertIn(name, failed)

    def test_missing_output_is_reported_first(self):
        """A missing key is the only problem reported, so it gets fixed first."""
        code = GOOD_CHILLER.replace('"min_drive_temp_c": min_drive_temp_c,', "")
        attempt = check_model(SPECS["adsorption_chiller"], code)
        self.assertEqual(len(attempt.checks), 1)
        self.assertIn("missing min_drive_temp_c", attempt.checks[0].detail)

    def test_prompt_and_lookup(self):
        """The prompt names the function, units and tests; requests find their spec."""
        text = spec_message(SPECS["adsorption_chiller"])
        self.assertIn("def adsorption_chiller(drive_temp_c, heat_available_mw", text)
        self.assertIn("Energy balance", text)
        self.assertEqual(
            find_spec("Add an adsorption chiller on the HEX outlet").name, "adsorption_chiller"
        )
        self.assertEqual(find_spec("Can we use ATES for seasonal storage?").name, "ates")
        self.assertIsNone(find_spec("What are the rates for heat?"))
        self.assertIn("Generate it?", SPECS["ates"].offer())

    def test_clean_code(self):
        """Fences and double-escaped line breaks are undone."""
        self.assertEqual(clean_code("```python\nx = 1\n```"), "x = 1\n")
        self.assertEqual(clean_code("def f():\\n    return 1"), "def f():\n    return 1\n")


class TestGenerate(unittest.TestCase):
    """The generate-test-correct loop."""

    def test_first_attempt_passes(self):
        """Good code passes at once: one call, a full table, the tokens counted."""
        llm = ScriptedLLM([reply(GOOD_CHILLER)])
        result = generate(SPECS["adsorption_chiller"], llm)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.attempts), 1)
        self.assertEqual(len(result.table), len(SPECS["adsorption_chiller"].cases))
        self.assertEqual(result.tokens, {"prompt": 100, "output": 20})
        self.assertIn("| drive_temp_c [°C] |", result.table_markdown())
        json.dumps(result.as_dict())

    def test_failed_check_is_fed_back_and_fixed(self):
        """The energy-balance failure goes back to the model; its second answer passes."""
        seen = []

        def model(purpose, messages):
            seen.append(messages)
            return reply(LEAKY_CHILLER if len(seen) == 1 else GOOD_CHILLER)

        steps = list(iter_generate(SPECS["adsorption_chiller"], ScriptedLLM(model)))
        self.assertEqual([a.passed for a in steps], [False, True])
        self.assertEqual([c.name for c in steps[0].failed_checks], ["Energy balance"])
        retry = seen[1]
        self.assertEqual([m["role"] for m in retry], ["system", "user", "assistant", "user"])
        self.assertIn(
            "Failed check 'Energy balance' (rule: drive_heat_mw + cold_mw = rejected_heat_mw",
            retry[-1]["content"],
        )
        self.assertIn("but rejected_heat_mw is", retry[-1]["content"])
        self.assertEqual(json.loads(retry[2]["content"])["code"], LEAKY_CHILLER)
        result = generate(
            SPECS["adsorption_chiller"], ScriptedLLM([reply(LEAKY_CHILLER), reply(GOOD_CHILLER)])
        )
        self.assertTrue(result.passed)
        self.assertEqual(len(result.calls), 2)

    def test_rule_violation_and_bad_reply_are_fed_back(self):
        """A forbidden import and an empty reply each become feedback, then give up."""
        llm = ScriptedLLM(
            [reply("import os\n" + GOOD_CHILLER), {"reason": "x", "code": ""}, reply(LEAKY_CHILLER)]
        )
        result = generate(SPECS["adsorption_chiller"], llm)
        self.assertFalse(result.passed)
        self.assertEqual(len(result.attempts), 3)
        self.assertTrue(result.attempts[0].violations)
        self.assertEqual(result.attempts[1].error, "the reply had no code")
        self.assertEqual(result.code, LEAKY_CHILLER)  # the best of three: one failed check

    def test_identical_retry_is_skipped(self):
        """Two answers without code would repeat at temperature 0, so the loop stops."""
        llm = ScriptedLLM([{"reason": "x", "code": ""}] * 3)
        result = generate(SPECS["adsorption_chiller"], llm)
        self.assertEqual(len(result.attempts), 2)
        self.assertFalse(result.passed)

    def test_model_unavailable_is_raised(self):
        """A missing model server stops generation, so the agent can say how to fix it."""
        with self.assertRaises(ModelUnavailable):
            generate(SPECS["adsorption_chiller"], ScriptedLLM([ConnectionError("refused")]))


class TestRegistry(unittest.TestCase):
    """Saving, loading and running approved models."""

    def setUp(self):
        """Use a temporary folder."""
        self._tmp = tempfile.TemporaryDirectory()
        self.registry = Registry(self._tmp.name)

    def tearDown(self):
        """Remove the folder."""
        self._tmp.cleanup()

    def test_round_trip(self):
        """Save, list, load and evaluate with defaults; the per-case checks run too."""
        result = generate(SPECS["adsorption_chiller"], ScriptedLLM([reply(GOOD_CHILLER)]))
        path = self.registry.save(result, approved_by="user")
        self.assertEqual(self.registry.names(), ["adsorption_chiller"])
        text = path.read_text()
        self.assertIn("approved by user", text)
        self.assertIn("PASS Energy balance", text)
        self.assertEqual((Path(self._tmp.name) / ".gitignore").read_text().splitlines()[1], "*")
        outputs = self.registry.evaluate(
            "adsorption_chiller",
            [{"drive_temp_c": 45, "heat_available_mw": 3}, {"drive_temp_c": 65}],
        )
        self.assertEqual(outputs[0]["cold_mw"], 0.0)
        self.assertAlmostEqual(outputs[1]["cold_mw"], 1.5237, places=3)
        ev = self.registry.evaluate_checked("adsorption_chiller", [{"drive_temp_c": 95}])
        self.assertTrue(ev.passed)
        self.assertEqual(
            ev.assumed[0], ["heat_available_mw", "cooling_water_temp_c", "chilled_water_temp_c"]
        )
        self.assertIn("outside the tested range", ev.warnings[0])
        self.assertNotIn("Cold rises with drive temperature", [c.name for c in ev.checks])

    def test_only_passing_approved_code_is_saved(self):
        """A failed result or a missing approval is refused."""
        failed = generate(
            SPECS["adsorption_chiller"], ScriptedLLM([reply(LEAKY_CHILLER)]), max_attempts=1
        )
        with self.assertRaises(ValueError):
            self.registry.save(failed, approved_by="user")
        passed = generate(SPECS["adsorption_chiller"], ScriptedLLM([reply(GOOD_CHILLER)]))
        with self.assertRaises(ValueError):
            self.registry.save(passed, approved_by="")
        forged = passed.as_dict()
        forged["code"] = LEAKY_CHILLER  # a session edited between test and approval
        with self.assertRaises(ValueError):
            self.registry.save(GenerationResult.from_dict(forged), approved_by="user")
        self.assertEqual(self.registry.names(), [])

    def test_result_survives_a_saved_session(self):
        """A result kept as JSON across the approval interrupt can still be registered."""
        result = generate(
            SPECS["adsorption_chiller"],
            ScriptedLLM([reply(LEAKY_CHILLER), reply(GOOD_CHILLER)]),
        )
        back = GenerationResult.from_dict(json.loads(json.dumps(result.as_dict())))
        self.assertEqual(back.tokens, result.tokens)
        self.assertEqual(len(back.attempts), 2)
        self.assertEqual(back.table, result.table)
        self.registry.save(back, approved_by="user")
        self.assertEqual(self.registry.load("adsorption_chiller").code, GOOD_CHILLER)

    def test_tampered_or_unknown_model_is_refused(self):
        """Edited code no longer matches its approval; unknown names and inputs raise."""
        result = generate(SPECS["adsorption_chiller"], ScriptedLLM([reply(GOOD_CHILLER)]))
        path = self.registry.save(result, approved_by="user")
        with self.assertRaises(ValueError):
            self.registry.evaluate("adsorption_chiller", [{"depth_m": 3}])
        path.write_text(path.read_text().replace("0.65", "0.95"))
        with self.assertRaises(ValueError):
            self.registry.load("adsorption_chiller")
        with self.assertRaises(KeyError):
            self.registry.load("ates")

    def test_default_folder_is_git_ignored(self):
        """The default folder ships a .gitignore that keeps generated code local."""
        ignore = modelgen.MODELS_DIR / ".gitignore"
        self.assertTrue(ignore.exists())
        self.assertIn("*", ignore.read_text().splitlines())


if __name__ == "__main__":
    unittest.main()
