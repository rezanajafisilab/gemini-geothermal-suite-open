"""The tabs' new views (2 Nov): the design-space map and the unplanned outages."""

import os
import unittest
from unittest import mock

from gemini_agent import workbench
from gemini_agent.reporter import design_id
from unit_test.gemini_agent.test_naming import designed


class TestViews(unittest.TestCase):
    """What the Compare map and the Sensitivity tab's outages card get."""

    @classmethod
    def setUpClass(cls):
        """Design once with a small sweep."""
        with mock.patch.dict(os.environ, {"DIOSCURI_SWEEP": "300"}):
            cls.agent, cls.s = designed()

    def test_sweep_view(self):
        """Every drawn design as a row; the search's designs as marks; its size in the runs."""
        view = workbench.sweep_view(self.s)
        self.assertEqual(len(view["rows"]), 300)
        self.assertEqual(len(view["rows"][0]), len(view["columns"]))
        self.assertTrue(any(m["role"] == "chosen" for m in view["marks"]))
        self.assertTrue(all("co2_t" in m for m in view["marks"]))
        run = workbench.workbench(self.s)["attempts"][0]
        self.assertEqual(run["swept"]["designs"], 300)
        self.assertNotIn("sweep", run)  # the rows come from their own endpoint only

    def test_outages_view(self):
        """1,000 years of the chosen design, the worst case dated, the rates' sources."""
        out = workbench.outages(self.s, design_id(self.s.chosen), years=200)
        self.assertEqual(out["years"], 200)
        self.assertIn("from", out["worst"])
        self.assertIn("esp", out["sources"])
        with self.assertRaises(KeyError):
            workbench.outages(self.s, "Z9 · nothing")
        self.assertFalse(out["spare_esp"])  # as built: no design pays for a spare ESP
        self.assertIn("grid_keur", out)

    def test_risk_view_prices_both_plans_a_year(self):
        """N-1 and the size by risk, both in k€ a year: capital annuity, O&M, grid (4 Nov).

        By hand for a gas boiler: capital = MW x 0.075 M€/MW x CRF(5.2 %, 25 years) and fixed
        O&M per MW; "What N-1 buys" is the whole design's yearly cost at the N-1 size less at
        the risk size. Before 4 Nov it set the one-off M€ against k€ a year.
        """
        from dioscuri_plant.economics import crf

        chosen = self.s.chosen
        out = workbench.risk_view(self.s, design_id(chosen))
        self.assertFalse(out["spare_esp"])
        self.assertEqual(out["spare_keur_per_year"], 0.0)
        self.assertIn("no spare ESP", out["source"])
        prices = workbench.engine.prices_for(self.s.assumptions or None, chosen.brief)
        gas = out["unit"] == "boiler_mw"
        per = prices.boiler_meur_per_mw if gas else prices.electric_boiler_meur_per_mw
        life = prices.boiler_life_years if gas else prices.electric_boiler_life_years
        self.assertEqual(out["annuity"]["life_years"], life)
        for plan in (out["n1_plan"], out["risk_plan"]):
            hand = round(plan["mw"] * per, 3) * crf(prices.discount_rate, life) * 1000
            self.assertAlmostEqual(plan["capital_keur"], hand, delta=0.1)
            self.assertAlmostEqual(
                plan["backup_keur"],
                plan["capital_keur"] + plan["om_keur"] + plan["grid_keur"],
                delta=0.15,
            )
        self.assertEqual(out["n1_plan"]["mw"], out["n1_mw"])
        diff = (out["n1_plan"]["design_meur"] - out["risk_plan"]["design_meur"]) * 1000
        self.assertAlmostEqual(out["n1_extra_keur_per_year"], diff, delta=0.2)
        self.assertGreaterEqual(out["n1_extra_keur_per_year"], 0.0)
        if out["risk_mw"] == out["n1_mw"]:
            self.assertEqual(out["n1_extra_keur_per_year"], 0.0)
        spare = workbench.risk_view(self.s, design_id(chosen), spare_esp=True)
        self.assertTrue(spare["spare_esp"])
        self.assertGreater(spare["spare_keur_per_year"], 0.0)
        self.assertLessEqual(spare["risk_mw"], out["risk_mw"])  # 7 days out, not 120

    def test_cheapest_reliable(self):
        """The "reliable" pick is named "cheapest reliable"; "most reliable" still finds it."""
        from gemini_agent import engine, naming, reliability

        self.assertEqual(engine.PICK_NAMES["reliable"], "cheapest reliable")
        self.assertEqual(naming.PICK_WORDS["reliable"], "Cheapest reliable")
        pick = next(e for e in self.s.candidates if "reliable" in e.alternative.picks)
        cheapest = next(e for e in self.s.candidates if "cost" in e.alternative.picks)
        for name in ("cheapest reliable", "most reliable", "the cheapest reliable one"):
            found, _ = reliability.resolve([name], self.s)
            self.assertIs(found[0], pick, name)
        self.assertIs(reliability.resolve(["the cheapest"], self.s)[0][0], cheapest)
        green = next(
            (e for e in self.s.candidates if "green_reliable" in e.alternative.picks), None
        )
        if green is not None:
            self.assertIs(reliability.resolve(["greenest reliable"], self.s)[0][0], green)
        # Read from the words: "the cheapest reliable" is not also "the cheapest".
        from gemini_agent.agent import named_in

        for text in (
            "How does it compare with the most reliable one?",
            "And the cheapest reliable?",
        ):
            self.assertEqual(named_in(text, self.s), [pick], text)

    def test_ranked_under_the_search_prices(self):
        """``ranked`` orders "best" with the prices the search ran under, not the defaults."""
        from types import SimpleNamespace

        from gemini_agent import engine

        seen = []

        def shadow(e, prices):
            seen.append(prices)
            return e.economics.lcoe_eur_per_mwh

        def entry(lcoe):
            alt = SimpleNamespace(role="candidate", reliable=True)
            return SimpleNamespace(
                alternative=alt, economics=SimpleNamespace(lcoe_eur_per_mwh=lcoe)
            )

        mine = engine.prices_for({"carbon_eur_per_t": 300.0})
        a, b = entry(60.0), entry(50.0)
        outcome = engine.Outcome(None, [a, b], None, "best", None, prices=mine)
        with mock.patch.object(engine, "shadow_cost", shadow):
            self.assertEqual(engine.ranked(outcome), [b, a])
        self.assertTrue(seen and all(p is mine for p in seen))


if __name__ == "__main__":
    unittest.main()
