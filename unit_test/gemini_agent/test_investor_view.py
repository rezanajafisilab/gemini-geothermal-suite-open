"""The investor's view through the app and the chat: its block, its inputs, its money lines."""

import tempfile
import unittest

from fastapi.testclient import TestClient

from gemini_agent import Agent
from gemini_agent.llm import ScriptedLLM
from gemini_agent.server import create_app
from unit_test.gemini_agent.test_agent import FULL_BRIEF, fake_intake


class TestInvestorView(unittest.TestCase):
    """One conversation with a design; the Economics tab's investor section and its inputs."""

    @classmethod
    def setUpClass(cls):
        """Run one design in a conversation."""
        cls.tmp = tempfile.TemporaryDirectory()
        cls.agent = Agent(ScriptedLLM(fake_intake), trace_dir=cls.tmp.name)
        cls.client = TestClient(create_app(cls.agent))
        cls.client.post("/api/run", json={"threadId": "inv", "message": FULL_BRIEF})
        cls.client.post(
            "/api/run",
            json={"threadId": "inv", "answers": {"confirm": "Run the design with these inputs"}},
        )
        cls.wb = cls.client.get("/api/workbench", params={"threadId": "inv"}).json()

    @classmethod
    def tearDownClass(cls):
        """Remove the traces."""
        cls.tmp.cleanup()

    def put(self, changes):
        """Return the response to a change of assumptions."""
        return self.client.put("/api/assumptions", json={"threadId": "inv", "assumptions": changes})

    def test_the_chosen_design_has_an_investor_block(self):
        """Sales, SDE++ and tax, a row a year, NPV and IRR; the plant's cost is unchanged."""
        econ = self.wb["designs"][0]["economics"]
        inv = econ["investor"]
        self.assertEqual(len(inv["flows"]), inv["years"] + 1)
        self.assertTrue(inv["sde"]["on"])
        self.assertGreater(inv["sde"]["meur_first_year"], 0)
        self.assertTrue(inv["sde"]["category"]["key"].startswith("base_"))
        self.assertAlmostEqual(inv["flows"][-1]["cumulative"], inv["npv_meur"], delta=0.01)
        self.assertGreater(inv["npv_meur"], inv["without_sde"]["npv_meur"])
        self.assertEqual(
            [i["key"] for i in inv["inputs"]][:2],
            ["heat_sale_eur_per_mwh", "cold_sale_eur_per_mwh"],
        )
        self.assertTrue(inv["notes"])

    def test_sale_price_changes_the_investor_not_the_plant(self):
        """A higher heat price raises the investor's NPV; the cost of heat stays; null resets."""
        before = self.wb["designs"][0]["economics"]
        high = self.put({"heat_sale_eur_per_mwh": 120}).json()["designs"][0]["economics"]
        self.assertEqual(high["lcoh"], before["lcoh"])
        self.assertGreater(high["investor"]["npv_meur"], before["investor"]["npv_meur"])
        heat = high["investor"]["inputs"][0]
        self.assertEqual((heat["value"], heat["changed"]), (120.0, True))
        back = self.put({"heat_sale_eur_per_mwh": None}).json()["designs"][0]["economics"]
        self.assertEqual(back["investor"]["npv_meur"], before["investor"]["npv_meur"])

    def test_subsidy_switch_and_category(self):
        """SDE++ off gives the case without it; a chosen category is used; nonsense is a 422."""
        before = self.wb["designs"][0]["economics"]["investor"]
        off = self.put({"sde_on": False}).json()["designs"][0]["economics"]["investor"]
        self.assertEqual(off["npv_meur"], before["without_sde"]["npv_meur"])
        self.assertTrue(all(f["sde"] == 0 for f in off["flows"]))
        picked = self.put({"sde_on": None, "sde_category": "base_ge20"}).json()
        cat = picked["designs"][0]["economics"]["investor"]["sde"]["category"]
        self.assertEqual(cat["key"], "base_ge20")
        self.assertEqual(self.put({"sde_category": "huge"}).status_code, 422)
        self.assertEqual(self.put({"heat_sale_eur_per_mwh": -5}).status_code, 422)
        self.put({"sde_category": None})

    def test_money_lines_carry_the_investors_figures(self):
        """The chat's money facts name the investor's view, its SDE++ and its return."""
        from gemini_agent import answer, engine
        from gemini_agent.contract import DesignBrief

        out = engine.search(DesignBrief())
        text = " ".join(answer.money_lines(out.chosen))
        self.assertIn("The investor's view", text)
        self.assertIn("SDE++ category", text)
        self.assertIn("The investor's return after tax: NPV", text)
        self.assertNotIn("investor", " ".join(answer.money_lines(out.reference)))


if __name__ == "__main__":
    unittest.main()
