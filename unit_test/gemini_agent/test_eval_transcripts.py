"""The eval harness's own checks, in hackathon/evals.

Transcripts kept and served (transcripts.py), designs read against the truth (truth.py), and
cases that start with a bad upload (badinput.py).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from gemini_agent import CHALLENGE_PROJECT, Agent, Session, engine, projects, workbench
from gemini_agent.contract import DesignBrief
from gemini_agent.llm import ScriptedLLM

EVALS = Path(__file__).resolve().parents[2] / "hackathon" / "evals"
sys.path.insert(0, str(EVALS))

import badinput  # noqa: E402
import transcripts  # noqa: E402
import truth  # noqa: E402

from unit_test.gemini_agent.test_agent import FULL_BRIEF, confirmed, fake_intake  # noqa: E402

try:
    from fastapi.testclient import TestClient
except ImportError:  # the server is optional for the model and simulator tests
    TestClient = None


def designed() -> Session:
    """Return a conversation with the challenge's design chosen (the toy model)."""
    outcome = engine.search(DesignBrief())
    s = Session()
    s.ledger.append(outcome.chosen)
    s.chosen = outcome.chosen
    return s


class TestTruth(unittest.TestCase):
    """Each hard cap and the known demand, read again from the design's year."""

    @classmethod
    def setUpClass(cls):
        """Design the challenge once."""
        cls.session = designed()
        cls.code = cls.session.chosen.alternative.code

    def test_every_cap_by_name_and_the_known_totals(self):
        """The challenge's design keeps every cap and delivers 111.67 and 23.74 GWh."""
        found = truth.of(self.session, {"alternative": self.code})
        self.assertEqual(
            [c["key"] for c in found["caps"]], ["doublets", "flow", "brine", "days", "heat", "cold"]
        )
        self.assertTrue(all(c["ok"] for c in found["caps"]), found["caps"])
        self.assertTrue(all(k["ok"] for k in found["known"]), found["known"])
        checks = truth.checks({"checks": ["hard_caps", "known_totals"]}, {"truth": found})
        self.assertEqual(len(checks), 9)
        self.assertIn("cap: 50 to 300 m³/h a doublet", checks)

    def test_a_broken_cap_is_named(self):
        """A doublet run at 400 m³/h fails the flow cap, and only it."""
        entry = self.session.chosen.model_copy(deep=True)
        d = entry.year.doublets[0]
        d["flow_m3h"] = [400.0 if on else f for f, on in zip(d["flow_m3h"], d["on"])]
        rows = {c["key"]: c for c in truth.caps(entry)}
        self.assertFalse(rows["flow"]["ok"])
        self.assertIn("400", rows["flow"]["found"])
        self.assertTrue(rows["brine"]["ok"])

    def test_a_turn_without_a_design_fails_the_checks_it_asked_for(self):
        """hard_caps on a reply that showed no design is a fail, not a pass."""
        found = truth.of(self.session, {"answer": "No design."})
        checks = truth.checks({"checks": ["hard_caps"]}, {"truth": found})
        self.assertEqual(checks, {"hard_caps: no design shown": False})

    def test_quoted_totals(self):
        """Read 111.7 and 112 GWh as the demand rounded, 110 GWh as wrong, a unit's share not."""
        said = truth.quoted_totals(
            "The heat demand is 111.7 GWh a year (112 GWh rounded) and the cold demand 24 GWh. "
            "A demand of 110 GWh a year is assumed. Geothermal covers 108 GWh of the demand."
        )
        self.assertEqual([(q["text"], q["ok"]) for q in said][-1], ("110 GWh", False))
        self.assertEqual(sum(q["ok"] for q in said), 3)
        self.assertNotIn("108 GWh", [q["text"] for q in said])


class TestTranscripts(unittest.TestCase):
    """A case's whole conversation is kept, then served read-only."""

    def test_recorded_written_and_served(self):
        """The recorder keeps each message and answer with its events; the server returns it."""
        agent = transcripts.Recorder(Agent(ScriptedLLM(fake_intake)))
        s = confirmed(Session())
        list(agent.run(s, FULL_BRIEF))
        exchanges = agent.take()
        self.assertEqual(agent.take(), [])
        self.assertEqual(exchanges[0]["user"], {"message": FULL_BRIEF})
        types = {e["type"] for e in exchanges[0]["events"]}
        self.assertTrue(
            {"RUN_STARTED", "STEP_STARTED", "TOOL_CALL_RESULT", "RUN_FINISHED"} <= types
        )
        with tempfile.TemporaryDirectory() as runs:
            folder = Path(runs) / "transcripts" / "20261103T000000Z_test"
            row = {
                "id": "S01_full_brief",
                "prompt": FULL_BRIEF,
                "model": "scripted",
                "device": "cpu",
                "reasoning": "",
                "expected": "design",
                "pass": True,
                "behaviour_ok": True,
                "checks": {"verifier_pass": True},
                "wall_seconds": 1.0,
                "result": dict(s.last, truth=truth.of(s, s.last)),
            }
            path = transcripts.write(folder, {"expect": {"behaviour": "design"}}, row, exchanges)
            self.assertEqual(path.name, "S01_full_brief.json")
            self.assertLess(path.stat().st_size, 400_000)
            back = workbench.transcript(Path(runs), folder.name, "S01_full_brief")
            self.assertEqual(back["got"], "design")
            self.assertEqual(len(back["runs"]), 1)
            self.assertTrue(back["runs"][0]["tools"])
            self.assertIsNone(workbench.transcript(Path(runs), folder.name, "S99"))
            with self.assertRaises(ValueError):
                workbench.transcript(Path(runs), "..", "S01_full_brief")
            if TestClient is not None:
                from gemini_agent import server

                saved, server.RUNS = server.RUNS, Path(runs)
                try:
                    client = TestClient(server.create_app(Agent(ScriptedLLM(fake_intake))))
                    q = {"run": folder.name, "case": "S01_full_brief"}
                    self.assertEqual(
                        client.get("/api/transcript", params=q).json()["case"], q["case"]
                    )
                    q["case"] = "S99"
                    self.assertEqual(client.get("/api/transcript", params=q).status_code, 404)
                    q["run"] = "../x"
                    self.assertEqual(client.get("/api/transcript", params=q).status_code, 400)
                finally:
                    server.RUNS = saved

    def test_a_search_card_is_slimmed_and_a_long_result_cut(self):
        """Past the first candidates, only what the scatter plots is kept."""
        cands = [{"code": f"C{i}", "name": "x" * 200, "lcoe": 1.0, "co2_t": 2.0} for i in range(40)]
        cands[30]["picks"] = ["cost"]
        event = {"type": "CUSTOM", "name": "candidates", "value": {"candidates": cands}}
        slim = transcripts.lean(event)["value"]["candidates"]
        self.assertIn("name", slim[0])
        self.assertNotIn("name", slim[20])
        self.assertIn("name", slim[30])  # a pick stays whole
        self.assertEqual(len(cands[20]), 4)  # the recorded event itself is not changed
        long = {"type": "TOOL_CALL_RESULT", "content": json.dumps({"x": "y" * 50_000})}
        cut = json.loads(transcripts.lean(long)["content"])
        self.assertIn("cut", cut)


class TestBadInput(unittest.TestCase):
    """A case that starts with New project: refused, asked, or made."""

    def setUp(self):
        """Keep the app's registry, to put back after."""
        self.saved = projects.registry()
        badinput._FOLDER.clear()

    def tearDown(self):
        """Put the app's registry back."""
        projects._REGISTRY = self.saved
        badinput._FOLDER.clear()

    def upload(self, **spec):
        """Run the upload of a case and return the recorder and the project."""
        agent = transcripts.Recorder(Agent(ScriptedLLM(fake_intake)))
        project = badinput.upload({"upload": spec}, agent, CHALLENGE_PROJECT)
        return agent, project

    def test_a_year_of_364_days_is_refused(self):
        """The fixture lacks 31 December: refused, saying 364 and 365; no chat runs."""
        agent, project = self.upload(heat="hackathon/evals/scenarios/fixtures/heating_364_days.csv")
        self.assertTrue(agent.skip)
        self.assertEqual(project.id, "challenge")
        out = badinput.outcome(agent)
        self.assertEqual(out["behaviour"], "upload_rejected")
        self.assertIn("364 values", out["answer"])
        self.assertTrue(badinput.CHECKS["upload_rejected"](out))
        self.assertEqual(list(agent.run(Session(), "Design it")), [])

    def test_kw_without_a_unit_is_asked_then_made(self):
        """The fixture in kW: asked; with the answer, made with the challenge's totals."""
        heat = "hackathon/evals/scenarios/fixtures/heating_no_unit.csv"
        agent, _ = self.upload(heat=heat)
        out = badinput.outcome(agent)
        self.assertEqual((out["behaviour"], out["asked"]), ("clarify", ["heat_unit"]))
        agent, project = self.upload(heat=heat, answers={"heat_unit": "kW"})
        self.assertFalse(agent.skip)
        self.assertEqual(agent.upload["totals"]["annual_heat_gwh"], 111.67)
        self.assertNotEqual(project.id, "challenge")
        self.assertEqual(len(agent.take()), 2)  # the question, then the answer

    def test_a_cooling_return_below_its_supply_is_refused(self):
        """The form's values go through the same check as the app's."""
        agent, _ = self.upload(
            heat="src/gemini_agent/data/challenge/GEMINI_Heating_Demand_Daily_2027.csv",
            values={"cool_supply_c": 20, "cool_return_c": 15},
        )
        self.assertIn("warmer than its supply", badinput.outcome(agent)["answer"])

    def test_the_flow_cap_must_be_said(self):
        """Name the 300 m³/h cap, and say it is broken when the design breaks it."""
        broken = {"truth": {"caps": [{"key": "flow", "ok": False}]}}
        check = badinput.CHECKS["flow_cap_said"]
        self.assertFalse(check(dict(broken, answer="Runs at 400 m³/h; the cap is respected.")))
        self.assertTrue(check(dict(broken, answer="400 m³/h breaks the 300 m³/h cap.")))
        kept = {"truth": {"caps": [{"key": "flow", "ok": True}]}}
        self.assertFalse(check(dict(kept, answer="It runs at 400 m³/h.")))
        self.assertTrue(check(dict(kept, answer="It stays within 300 m³/h anyway.")))


if __name__ == "__main__":
    unittest.main()
