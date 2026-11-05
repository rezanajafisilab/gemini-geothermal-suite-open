"""The recommended design, the cost basis and the caught-and-fixed list.

The app no longer opens on the recommended design (5 Nov: a new chat starts empty); the
server still gives it on ``GET /api/lead``, which the report's scripts read.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from gemini_agent import Agent, caught, cost_basis, engine, lead
from gemini_agent.agent import Session
from gemini_agent.llm import ScriptedLLM
from gemini_agent.server import create_app
from unit_test.gemini_agent.test_agent import fake_intake

ROOT = Path(__file__).resolve().parents[2]


class TestLead(unittest.TestCase):
    """The default brief's search, run once, kept on disk and put into a conversation."""

    @classmethod
    def setUpClass(cls):
        """Compute the recommendation once into a temporary cache."""
        cls.tmp = tempfile.TemporaryDirectory()
        cls.agent = Agent(ScriptedLLM(fake_intake), trace_dir=cls.tmp.name)
        cls.path = Path(cls.tmp.name) / "lead.json"
        cls.lead = lead.Lead(cls.agent._record_search, cls.path)
        cls.data = cls.lead.wait(600)
        cls.view = cls.lead.view()

    @classmethod
    def tearDownClass(cls):
        """Remove the cache."""
        cls.tmp.cleanup()

    def test_it_is_the_search_on_a_new_conversations_brief(self):
        """The design is what engine.search picks for the challenge's default brief."""
        self.assertEqual(self.view["state"], "ready")
        outcome = engine.search(Session().brief, {})
        self.assertEqual(self.view["design"]["code"], outcome.chosen.alternative.code)
        self.assertEqual(self.view["design"]["uid"], "A1")
        self.assertTrue(self.view["design"]["chosen"])

    def test_a_line_per_hard_cap(self):
        """Six caps, in order, each with the verifier's own pass or fail and detail."""
        keys = [c["key"] for c in self.view["caps"]]
        self.assertEqual(keys, ["doublets", "flow", "brine", "days", "heat", "cold"])
        checks = {c["name"]: c for c in self.view["design"]["checks"]}
        for c in self.view["caps"]:
            self.assertIn(c["passed"], (True, False))
            self.assertTrue(c["detail"])
        self.assertTrue(all(c["passed"] for c in self.view["caps"]))
        self.assertEqual(self.view["checks"]["total"], len(checks))
        self.assertIn("Flow 50–300 m³/h per doublet", [c["label"] for c in self.view["caps"]])

    def test_an_assumed_aquifer_is_said(self):
        """Wells away from the known aquifer's depth carry the engine's note that it is assumed."""
        known = engine.rules_for(Session().brief).reservoir_depth_m
        if self.view["design"]["plant"]["depth_m"] != known:
            self.assertIn("assume the same aquifer", self.view["assumed"])
        else:
            self.assertIsNone(self.view["assumed"])

    def test_the_year_is_day_by_day(self):
        """The view carries the Energy tab's 365 days of heat and of cold."""
        daily = self.view["design"]["year"]["daily_mw"]
        self.assertEqual(len(daily["heat"]["demand"]), 365)
        self.assertEqual(len(daily["cool"]["demand"]), 365)

    def test_kept_on_disk_and_loaded_without_computing(self):
        """A second start reads the cache; a stale fingerprint is computed again."""
        again = lead.Lead(self.agent._record_search, self.path)
        again.start()
        self.assertIsNone(again._thread)
        self.assertEqual(again.view()["design"]["code"], self.view["design"]["code"])
        stale = dict(self.data, fingerprint="0" * 16)
        other = Path(self.tmp.name) / "stale.json"
        other.write_text(json.dumps(stale, default=str), "utf-8")
        fresh = lead.Lead(self.agent._record_search, other)
        self.assertIsNone(fresh._load())

    def test_put_into_a_conversation(self):
        """The conversation holds the search (S1, A1 ...) and the design chosen."""
        s = self.lead.session_for("t-lead")
        self.assertEqual(s.thread_id, "t-lead")
        self.assertTrue(lead.has_lead(s))
        self.assertEqual(s.chosen.alternative.code, self.view["design"]["code"])
        self.assertEqual(s.searches[0]["id"], "S1")
        # The chat's context says the design was shown, so "this design" is the recommended one.
        self.assertEqual(s.history[0]["kind"], "design")
        self.assertIn(s.chosen.alternative.code, s.history[0]["reply"])

    def test_the_cost_basis_comes_with_it(self):
        """The first screen says the basis and how far the cost moves."""
        b = self.view["basis"]
        self.assertEqual(b["rate"]["value"], 0.052)
        self.assertIn("Table 6.3", b["rate"]["source"])
        self.assertTrue(b["swings"])


class TestCostBasis(unittest.TestCase):
    """What a cost includes and leaves out, and each swing from the real economics."""

    @classmethod
    def setUpClass(cls):
        """Search the default brief once."""
        cls.entry = engine.search(Session().brief, {}).chosen
        cls.b = cost_basis.basis(cls.entry, {})

    def test_the_parts_add_up_to_the_headline(self):
        """Every part's €/MWh sums to the cost of heat and cold."""
        total = sum(p["eur_per_mwh"] for p in self.b["includes"])
        self.assertAlmostEqual(total, self.entry.economics.lcoe_eur_per_mwh, delta=0.05)
        self.assertEqual(self.b["includes"][0]["kind"], "capital")

    def test_the_district_network_is_left_out(self):
        """The basis says the network's pipes are not in the cost."""
        out = [x["item"] for x in self.b["excludes"]]
        self.assertIn("The district network", out)
        self.assertIn("SDE++, sales and corporate tax", out)

    def test_swings_are_repriced_by_the_economics(self):
        """A lower discount rate costs less and a higher one more, as engine.reprice says."""
        rate = next(s for s in self.b["swings"] if s["key"] == "discount_rate")
        low = engine.reprice(self.entry, {"discount_rate": 0.03}).economics.lcoe_eur_per_mwh
        self.assertEqual(rate["low"]["lcoe"], low)
        self.assertLess(rate["low"]["lcoe"], self.entry.economics.lcoe_eur_per_mwh)
        self.assertGreater(rate["high"]["lcoe"], self.entry.economics.lcoe_eur_per_mwh)
        keys = {s["key"] for s in self.b["swings"]}
        self.assertTrue({"electricity_eur_per_mwh", "gas_eur_per_mwh", "carbon_eur_per_t"} <= keys)
        spans = [abs(s["high"]["lcoe"] - s["low"]["lcoe"]) for s in self.b["swings"]]
        self.assertEqual(spans, sorted(spans, reverse=True))

    def test_lifetimes_of_the_units_it_has(self):
        """The lives listed are those of the design's own units."""
        labels = [x["label"] for x in self.b["lifetimes"]]
        self.assertEqual(labels[0], "Wells and surface plant")
        self.assertEqual(self.b["lifetimes"][0]["years"], 30)


class TestLeadEndpoints(unittest.TestCase):
    """GET /api/lead, POST /api/lead/open and GET /api/cost-basis."""

    @classmethod
    def setUpClass(cls):
        """Make an app whose recommendation is computed into a temporary cache."""
        cls.tmp = tempfile.TemporaryDirectory()
        agent = Agent(ScriptedLLM(fake_intake), trace_dir=cls.tmp.name)
        app = create_app(agent)
        app.state.lead.path = Path(cls.tmp.name) / "lead.json"
        app.state.lead.wait(600)
        cls.app = app
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        """Remove the cache."""
        cls.tmp.cleanup()

    def test_computed_in_a_process_of_its_own(self):
        """The server's search runs in its own process (no fork from a busy server), on disk."""
        self.assertTrue(self.app.state.lead.spawn)
        self.assertTrue(self.app.state.lead.path.is_file())
        self.assertEqual(self.client.get("/api/lead").json()["state"], "ready")

    def test_open_it_in_an_empty_conversation(self):
        """The tabs then show the design; opening it again gives the same one."""
        view = self.client.get("/api/lead").json()
        self.assertEqual(view["state"], "ready")
        r = self.client.post("/api/lead/open", json={"threadId": "lead-t1"})
        self.assertEqual(r.status_code, 200)
        design = r.json()["design"]
        wb = self.client.get("/api/workbench", params={"threadId": "lead-t1"}).json()
        self.assertEqual(wb["designs"][0]["id"], design)
        self.assertTrue(wb["designs"][0]["chosen"])
        again = self.client.post("/api/lead/open", json={"threadId": "lead-t1"}).json()
        self.assertEqual(again["design"], design)

    def test_cost_basis_of_a_design(self):
        """The Economics tab's basis for a design of the conversation."""
        design = self.client.post("/api/lead/open", json={"threadId": "lead-t2"}).json()["design"]
        b = self.client.get("/api/cost-basis", params={"threadId": "lead-t2", "design": design})
        self.assertEqual(b.status_code, 200)
        self.assertTrue(b.json()["swings"])
        missing = self.client.get("/api/cost-basis", params={"threadId": "lead-t2", "design": "x"})
        self.assertEqual(missing.status_code, 404)

    def test_not_into_a_conversation_that_has_started(self):
        """A conversation with designs of its own is not overwritten."""
        self.client.post("/api/run", json={"threadId": "lead-t3", "message": "hello"})
        r = self.client.post("/api/lead/open", json={"threadId": "lead-t3"})
        self.assertEqual(r.status_code, 409)


class TestCaughtAndFixed(unittest.TestCase):
    """The list is factual where it can be checked: ids, sources, commits' form, tests."""

    @classmethod
    def setUpClass(cls):
        """Read the list."""
        cls.items = caught.items()

    def test_every_item_is_complete(self):
        """What failed, how it was found (a file that exists), the fix and a reference."""
        ids = [it["id"] for it in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        for it in self.items:
            for key in ("title", "failed", "found", "fix"):
                self.assertTrue(it[key], f"{it['id']}: {key}")
            self.assertTrue((ROOT / it["found_in"].split("#")[0]).exists(), it["found_in"])
            if it["status"] == "fixed":
                self.assertTrue(it["commit"] or it["adr"] or it["patch"], it["id"])
            if it["commit"]:
                self.assertRegex(it["commit"], r"^[0-9a-f]{7,40}$")
            if it["patch"]:
                self.assertTrue((ROOT / "hackathon/gemini_bughunt/patches" / it["patch"]).exists())
            self.assertIn(it["status"], ("fixed", "avoided"))

    def test_physics_codes_are_only_gemini_bugs(self):
        """F1-F10 are GEMINI's physics bugs; the agent's failures have labels of their own."""
        for it in self.items:
            if re.match(r"^F\d+$", it["id"]):
                self.assertEqual(it["group"], "gemini")
        self.assertEqual(
            {f"F{i}" for i in range(1, 11)}, {it["id"] for it in self.items if it["id"][0] == "F"}
        )

    def test_guarding_tests_exist(self):
        """Every test named is defined in its file."""
        for it in self.items:
            for t in it["tests"]:
                path, *names = t.split("::")
                text = (ROOT / path).read_text("utf-8")
                self.assertIn(f"def {names[-1]}(", text, t)
                if len(names) > 1:
                    self.assertIn(f"class {names[0]}", text, t)

    def test_the_report_is_written_from_the_same_file(self):
        """hackathon/docs/caught_and_fixed.md matches the data (python -m gemini_agent.caught)."""
        self.assertEqual(caught.REPORT.read_text("utf-8"), caught.markdown())

    def test_no_personal_names(self):
        """The list names the team, never a teammate."""
        text = caught.DATA.read_text("utf-8")
        self.assertNotRegex(text, r"\bAli\b")
