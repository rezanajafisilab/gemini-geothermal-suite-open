"""Helpers of the parameters reading: a second look, worked examples, the short-prompt rule."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemini_agent import parameters, reading_examples
from gemini_agent.llm import ScriptedLLM

NOW = {
    "heat_supply_c": 100.0,
    "heat_return_c": 60.0,
    "heat_demand_scale": 1.0,
    "gas_eur_per_mwh": 69.4,
    "carbon_eur_per_t": 73.9,
    "flow_max_m3h": 300.0,
}


def reading(*changes, **more):
    """Return a model's reading with these (key, value, quote) changes."""
    out = {"changes": [{"key": k, "value": v, "quote": q} for k, v, q in changes]}
    out.update(on_topic=True, **more)
    return out


def read(message, first, second=None):
    """Read a message with a model that answers ``first``, then ``second`` (a second look)."""
    llm = ScriptedLLM([first] + ([second] if second is not None else []))
    with mock.patch.dict(os.environ, {"DIOSCURI_EXAMPLES": "0"}):
        out = parameters.read(message, llm, dict(NOW), design="A1 1D-HP-EC")
    return out, llm


class TestSecondLook(unittest.TestCase):
    """A doubtful reading is read once more with the message's amounts; code keeps the valid one."""

    def test_no_amount_while_the_message_has_one(self):
        """A fifth more read as x1.5 is dropped as vague: read again, x1.2 is kept."""
        msg = "And with a fifth more heat demand?"
        q = "a fifth more heat demand"
        out, llm = read(
            msg, reading(("heat_demand_scale", 1.5, q)), reading(("heat_demand_scale", 1.2, q))
        )
        self.assertEqual(out.changes, {"heat_demand_scale": 1.2})
        self.assertEqual([c.purpose for c in llm.calls], ["parameters", "parameters_again"])
        self.assertEqual(out.second_look["kept"], "second")
        self.assertIn("no amount", out.second_look["why"][0])
        self.assertEqual(out.second_look["amounts"][0]["means"], "x1.2")
        self.assertEqual(len(out.extra_calls), 1)
        # The model is shown the amounts, as code read them, and the doubt.
        notes = llm_prompt(msg, reading(("heat_demand_scale", 1.5, q)))
        self.assertIn("“a fifth more”: x1.2", notes)
        self.assertIn("A second look", notes)

    def test_a_key_the_words_do_not_fit(self):
        """A return read as the supply is refused (below the return): read again as the return.

        And a price in €/MWh read as the CO2 price (EUR/t): the units do not fit, read again.
        """
        msg = "Return temperature 50 C, what happens?"
        q = "Return temperature 50 C"
        out, llm = read(msg, reading(("heat_supply_c", 50, q)), reading(("heat_return_c", 50, q)))
        self.assertEqual(out.changes, {"heat_return_c": 50.0})
        self.assertEqual(out.second_look["kept"], "second")
        self.assertEqual(out.dropped, [])
        self.assertEqual(out.second_look["first"]["changes"], {})
        msg, q = "And gas at 45 €/MWh?", "gas at 45 €/MWh"
        out, _ = read(
            msg, reading(("carbon_eur_per_t", 45, q)), reading(("gas_eur_per_mwh", 45, q))
        )
        self.assertEqual(out.changes, {"gas_eur_per_mwh": 45.0})
        self.assertIn("not a value in EUR/t", out.second_look["why"][0])

    def test_a_value_none_of_the_amounts_gives(self):
        """80 l/s kept as 80 m3/h (its number is in the quote) is 288 m3/h: read again."""
        msg = "What if the flow cap were 80 l/s?"
        q = "the flow cap were 80 l/s"
        out, _ = read(msg, reading(("flow_max_m3h", 80, q)), reading(("flow_max_m3h", 288, q)))
        self.assertEqual(out.changes, {"flow_max_m3h": 288.0})
        self.assertIn("288", out.second_look["why"][0])

    def test_nothing_read_while_the_message_gives_an_amount(self):
        """Nothing read from "En met gas op 4,5 ct/kWh?": read again, gas at 45 €/MWh."""
        msg = "En met gas op 4,5 ct/kWh?"
        out, _ = read(msg, reading(), reading(("gas_eur_per_mwh", 45, "gas op 4,5 ct/kWh")))
        self.assertEqual(out.changes, {"gas_eur_per_mwh": 45.0})
        self.assertEqual(out.steps[0].do, "what_if")
        self.assertIn("no change was read", out.second_look["why"][0])

    def test_an_invalid_second_reading_keeps_the_first(self):
        """The same misreading again, or a reading that loses a change: the first is kept."""
        msg = "Return temperature 50 C, what happens?"
        q = "Return temperature 50 C"
        first = reading(("heat_supply_c", 50, q))
        out, llm = read(msg, first, reading(("heat_supply_c", 50, q)))
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(out.second_look["kept"], "first")
        self.assertEqual(out.crossed, ["heat_supply_c"])  # still asked about, as before
        self.assertEqual(len(out.extra_calls), 1)
        # A second reading that drops the gas price the first had right is not kept either.
        msg = "Return temperature 50 C and gas at 40 €/MWh"
        first = reading(("heat_supply_c", 50, q), ("gas_eur_per_mwh", 40, "gas at 40 €/MWh"))
        out, _ = read(msg, first, reading(("heat_return_c", 50, q)))
        self.assertEqual(out.second_look["kept"], "first")
        self.assertEqual(out.changes, {"gas_eur_per_mwh": 40.0})

    def test_the_users_own_conflicts_stay_asked_about(self):
        """The user's own conflicts are asked about, as before.

        Both values of a pair given across each other are not read again; a value out of its
        range moved to another key that takes it is not kept.
        """
        msg = "Cooling at 18 °C supply and 12 °C return"
        first = reading(
            ("cool_supply_c", 18, "18 °C supply"), ("cool_return_c", 12, "12 °C return")
        )
        out, llm = read(msg, first)
        self.assertEqual(
            (len(llm.calls), sorted(out.crossed)), (1, ["cool_return_c", "cool_supply_c"])
        )
        msg, q = "Design it with a heating return of 105 °C.", "a heating return of 105 °C"
        out, llm = read(msg, reading(("heat_return_c", 105, q)), reading(("heat_supply_c", 105, q)))
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(out.second_look["kept"], "first")
        self.assertEqual(out.changes, {})
        self.assertIn("outside", out.dropped[0])
        # The same amount in its own unit, corrected on its key, is kept (176 °F is 80 °C).
        msg, q = "What if the supply were 176 °F?", "the supply were 176 °F"
        out, _ = read(msg, reading(("heat_supply_c", 176, q)), reading(("heat_supply_c", 80, q)))
        self.assertEqual(out.changes, {"heat_supply_c": 80.0})

    def test_no_doubt_no_second_call(self):
        """A reading that fits the message's amounts costs one call; so does a question."""
        msg = "What if the heating return were 50 °C?"
        out, llm = read(msg, reading(("heat_return_c", 50, "heating return were 50 °C")))
        self.assertEqual((len(llm.calls), out.second_look), (1, None))
        out, llm = read("Why did you choose these wells?", reading())
        self.assertEqual(len(llm.calls), 1)
        # A number the message asks about ("where does 87 °C come from?") is not a change.
        out, llm = read("Where does the 87 °C come from?", reading(origin_of=["87 °C"]))
        self.assertEqual(len(llm.calls), 1)

    def test_switched_off_and_a_failed_call(self):
        """DIOSCURI_SECOND_LOOK=0 makes no second call; a failed one keeps the first reading."""
        msg, q = "And with a fifth more heat demand?", "a fifth more heat demand"
        with mock.patch.dict(os.environ, {"DIOSCURI_SECOND_LOOK": "0"}):
            out, llm = read(msg, reading(("heat_demand_scale", 1.5, q)))
        self.assertEqual((len(llm.calls), out.second_look), (1, None))
        out, llm = read(msg, reading(("heat_demand_scale", 1.5, q)), RuntimeError("timed out"))
        self.assertEqual(out.second_look["kept"], "first")
        self.assertIn("timed out", out.second_look["error"])
        self.assertEqual(out.vague, {"heat_demand_scale": (1.5, q)})

    def test_the_agent_records_it(self):
        """The run's summary and the reading step say why the message was read again."""
        from gemini_agent import Agent, Session
        from unit_test.gemini_agent.test_agent import FULL_BRIEF, fake_intake, run

        def model(purpose, messages):
            said = messages[-1]["content"].split("Message: ")[-1]
            if "Return temperature" in said and purpose == "parameters":
                return reading(("heat_supply_c", 50, "Return temperature 50 C"))
            if purpose == "parameters_again":
                return reading(("heat_return_c", 50, "Return temperature 50 C"))
            return fake_intake(purpose, messages)

        agent = Agent(ScriptedLLM(model))
        s = Session()
        run(agent, s, FULL_BRIEF)
        events = run(agent, s, "Return temperature 50 C, what happens?")
        look = s.last["parameters"]["second_look"]
        self.assertEqual(look["kept"], "second")
        self.assertEqual(s.last["parameters"]["changes"], {"heat_return_c": 50.0})
        self.assertEqual(s.last["behaviour"], "design")
        step = next(
            e for e in events if e["type"] == "STEP_FINISHED" and e["stepName"] == "parameters"
        )
        self.assertEqual(step["metadata"]["second_look"]["kept"], "second")
        usage = [e["value"]["purpose"] for e in events if e.get("name") == "usage"]
        self.assertIn("parameters_again", usage)


def llm_prompt(message, first):
    """Return the second look's prompt for a first reading (the model's second answer: none)."""
    seen = []

    def model(purpose, messages):
        seen.append(messages[-1]["content"])
        return first

    with mock.patch.dict(os.environ, {"DIOSCURI_EXAMPLES": "0"}):
        parameters.read(message, ScriptedLLM(model), dict(NOW), design="A1 1D-HP-EC")
    return seen[-1]


def fake_embedder(texts):
    """Embed by a few words: one dimension each for gas, return and demand."""
    words = ("gas", "return", "demand")
    return [[float(w in t.lower()) + 0.01 * i for i, w in enumerate(words)] for t in texts]


class TestWorkedExamples(unittest.TestCase):
    """DIOSCURI_EXAMPLES=1 adds the three nearest checked readings to the prompt."""

    def setUp(self):
        """Write a small index of three examples."""
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "examples.npz"
        messages = ["gas at 40 €/MWh", "a 45 °C return", "double the demand"]
        readings = [
            '{"changes": [{"key": "gas_eur_per_mwh", "value": 40}]}',
            '{"changes": [{"key": "heat_return_c", "value": 45}]}',
            '{"changes": [{"key": "heat_demand_scale", "value": 2}]}',
        ]
        reading_examples.save(self.path, messages, readings, fake_embedder(messages), "fake")
        reading_examples.load.cache_clear()
        self.patches = [
            mock.patch.object(reading_examples, "INDEX", self.path),
            mock.patch.object(reading_examples, "EMBEDDER", fake_embedder),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        """Remove the index."""
        for p in self.patches:
            p.stop()
        reading_examples.load.cache_clear()
        self.dir.cleanup()

    def prompt(self, message, env):
        """Return the reading's prompt for a message under an environment."""
        seen = []

        def model(purpose, messages):
            seen.append(messages[-1]["content"])
            return reading()

        with mock.patch.dict(os.environ, dict(env, DIOSCURI_SECOND_LOOK="0")):
            parameters.read(message, ScriptedLLM(model), dict(NOW))
        return seen[0]

    def test_off_by_default(self):
        """Without the flag the prompt has no examples."""
        env = {k: v for k, v in os.environ.items() if k != "DIOSCURI_EXAMPLES"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(reading_examples.enabled())
            self.assertNotIn("Examples of readings", self.prompt("What if gas cost 50?", {}))

    def test_on_the_nearest_first(self):
        """With the flag, the nearest example comes first, before the message."""
        text = self.prompt("What if the gas price were 50?", {"DIOSCURI_EXAMPLES": "1"})
        block = text.split("Examples of readings", 1)[1].split("Message: What if", 1)[0]
        self.assertTrue(block.split("Message: ", 2)[1].startswith("gas at 40 €/MWh"))
        self.assertEqual(block.count("Reading: "), 3)
        with mock.patch.dict(os.environ, {"DIOSCURI_EXAMPLES": "1", "DIOSCURI_SECOND_LOOK": "0"}):
            out = parameters.read("What if gas cost 50?", ScriptedLLM([reading()]), dict(NOW))
        self.assertEqual(out.examples, 3)

    def test_no_embedder_no_examples(self):
        """An embedding that fails leaves the reading without examples, and without a word."""

        def broken(texts):
            raise ConnectionError("no Ollama")

        with mock.patch.object(reading_examples, "EMBEDDER", broken):
            text = self.prompt("What if gas cost 50?", {"DIOSCURI_EXAMPLES": "1"})
        self.assertNotIn("Examples of readings", text)

    def test_evaluation_prompts_are_left_out(self):
        """No example of the shipped index is near-identical to an evaluation prompt."""
        root = Path(__file__).resolve().parents[2]
        prompts = reading_examples.eval_prompts(
            sorted((root / "hackathon/evals/scenarios").glob("*.yaml"))
        )
        self.assertGreater(len(prompts), 100)
        self.assertTrue(reading_examples.leaks("What if gas cost 45 €/MWh?", prompts))
        self.assertTrue(reading_examples.leaks("what if gas cost 45 EUR/MWh", prompts))
        self.assertFalse(reading_examples.leaks("Please set the flow cap to 150 m3/h.", prompts))
        reading_examples.load.cache_clear()
        shipped = reading_examples.load(root / "src/gemini_agent/data/reading_examples.npz")
        self.assertIsNotNone(shipped)
        self.assertGreater(len(shipped.messages), 1000)
        leaked = [m for m in shipped.messages if reading_examples.leaks(m, prompts)]
        self.assertEqual(leaked, [])


class TestShortPrompts(unittest.TestCase):
    """Short prompts only for the models trained on them; an override either way."""

    def short(self, name, env=None):
        """Return whether a model of this name reads with the short prompts."""
        env = env or {}
        with mock.patch.dict(os.environ, env):
            if not env:
                os.environ.pop("DIOSCURI_SHORT_PROMPTS", None)
            return parameters.short_for(ScriptedLLM(lambda *a: {}, model=name))

    def test_the_tagged_models(self):
        """Castor and pollux latest and r2 (and untagged); r3 and others get the full prompts."""
        for name in (
            "dioscuri-castor",
            "dioscuri-pollux",
            "dioscuri-castor:latest",
            "dioscuri-pollux:latest",
            "dioscuri-castor:r2",
            "dioscuri-pollux:r2",
        ):
            self.assertTrue(self.short(name), name)
        for name in ("dioscuri-pollux:r3", "dioscuri-castor:r3", "dioscuri-new", "qwen3.5:9b"):
            self.assertFalse(self.short(name), name)

    def test_the_override(self):
        """DIOSCURI_SHORT_PROMPTS forces the short (1) or the full (0) prompts."""
        self.assertTrue(self.short("dioscuri-pollux:r3", {"DIOSCURI_SHORT_PROMPTS": "1"}))
        self.assertTrue(self.short("qwen3.5:9b", {"DIOSCURI_SHORT_PROMPTS": "1"}))
        self.assertFalse(self.short("dioscuri-pollux:r2", {"DIOSCURI_SHORT_PROMPTS": "0"}))


if __name__ == "__main__":
    unittest.main()
