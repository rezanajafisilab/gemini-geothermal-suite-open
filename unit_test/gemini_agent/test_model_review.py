"""The model fixes of the 1 Nov science review: picks, gas-free trains, grid cliff, centring.

E3: the best-overall pick weighs every layout's sizing that is best by its own measure.
E4: the gas-free stage tries a treatment train per doublet; no unit grows for nothing.
E5: a failure that pushes the electric boiler past 600 hours costs the year's grid contract.
E6: SDE++ pays for geothermal heat, not the heat pump's electricity.
E13: the Monte Carlo draws centre on the design's own case and say where it sits.
"""

import unittest
from functools import lru_cache
from types import SimpleNamespace

import dioscuri_plant as dp
from gemini_agent import answer, engine, reliability, reporter, workbench
from gemini_agent.contract import DesignBrief
from gemini_agent.parameters import Failure


@lru_cache(maxsize=None)
def challenge(*excluded: str) -> engine.Outcome:
    """Return the search at the known aquifer (with these units ruled out), run once.

    The review's cases (31 Oct) are the 2,500 m designs; since 2 Nov the default also tries
    3,000 and 3,500 m, so the search is pinned to the known aquifer here.
    """
    return engine.search(DesignBrief(excluded=list(excluded), doublet_depths_m=[2500.0]))


class TestBestOverallSizing(unittest.TestCase):
    """Each layout's reliable plan also from its sizing cheapest with CO2 at 137 €/t (E3)."""

    @classmethod
    def setUpClass(cls):
        """Search once for the default brief."""
        cls.outcome = challenge()
        cls.prices = engine.prices_for(None, DesignBrief(doublet_depths_m=[2500.0]))

    def plans(self):
        """Return the valid reliable plans."""
        return [
            e
            for e in self.outcome.candidates
            if e.alternative.reliable and e.alternative.role in ("chosen", "candidate")
        ]

    def test_the_best_is_a_bigger_heat_pump(self):
        """A1's layout with a 3.3 MW heat pump: 69.83 €/MWh, 12,967 t, 75.87 against 76.37."""
        best = engine.picked(self.outcome, "best")
        self.assertIs(best, self.outcome.chosen)
        twins = [e for e in self.plans() if e.alternative.code == best.alternative.code]
        self.assertEqual(len(twins), 2)  # the cheapest sizing's plan and this one
        other = next(e for e in twins if e is not best)
        self.assertGreater(best.alternative.sizes_mw["heat_pump"], 3.0)
        self.assertAlmostEqual(other.alternative.sizes_mw["heat_pump"], 2.0, places=6)
        self.assertLess(best.economics.co2_t_per_year, other.economics.co2_t_per_year - 1000)
        self.assertLess(
            engine.shadow_cost(best, self.prices), engine.shadow_cost(other, self.prices)
        )
        self.assertTrue(best.alternative.effect.startswith(engine.SHADOW_SIZING))
        self.assertTrue(any("sizing that is cheapest with CO2" in n for n in self.outcome.notes))

    def test_best_by_its_own_measure(self):
        """No reliable plan is cheaper with CO2 at the long-term price than the best."""
        best = engine.picked(self.outcome, "best")
        low = min(engine.shadow_cost(e, self.prices) for e in self.plans())
        self.assertAlmostEqual(engine.shadow_cost(best, self.prices), low, places=9)

    def test_each_pick_tags_one_design(self):
        """Two plans share a code, but each pick names one design, the one ``picked`` returns."""
        for key in engine.PICKS:
            tagged = [e for e in self.outcome.candidates if key in e.alternative.picks]
            self.assertEqual(len(tagged), 1, key)
            self.assertIs(engine.picked(self.outcome, key), tagged[0])

    def test_no_second_sizing_without_a_long_term_weight(self):
        """With CO2 already at the long-term price, only the cheapest sizing is planned."""
        cand = next(
            c
            for c in dp.search(
                engine.demand(),
                engine.doublet_model(dp.Rules()),
                layouts=[dp.Topology(1, "heat_pump", "electric")],
                stage_two=False,
            ).candidates
        )
        rules = dp.Rules()
        model = engine.doublet_model(rules)
        ref = None
        flat = dp.Prices(carbon_eur_per_t=137.0)
        got = list(engine.shadow_sizings([cand], engine.demand(), model, rules, flat, (), ref))
        self.assertEqual([n for _, n in got], [""])
        weighted = list(
            engine.shadow_sizings([cand], engine.demand(), model, rules, dp.Prices(), (), ref)
        )
        self.assertEqual(len(weighted), 2)
        self.assertGreater(weighted[1][0].plant.heat_pump_mw, cand.plant.heat_pump_mw)


class TestGasFreeTrains(unittest.TestCase):
    """Gas-free plans with a treatment train per doublet (E4)."""

    @classmethod
    def setUpClass(cls):
        """Search once for the default brief and once with the gas boiler ruled out."""
        cls.outcome = challenge()
        cls.no_boiler = challenge("boiler")

    def test_layouts(self):
        """Two or more doublets sharing a train: each mode again with a train each."""
        two = dp.Topology(2)
        self.assertEqual(
            engine.gas_free_layouts(two, ("produced", "sell")),
            [
                ("produced", "shared"),
                ("sell", "shared"),
                ("produced", "separate"),
                ("sell", "separate"),
            ],
        )
        self.assertEqual(len(engine.gas_free_layouts(two, ("sell",), {"trains": "shared"})), 1)
        self.assertEqual(len(engine.gas_free_layouts(dp.Topology(1), ("sell",))), 1)

    def test_a_train_each_needs_a_smaller_electric_boiler(self):
        """The gas-free pick has a train per doublet: 17 MW of electric boiler, not 30."""
        free = engine.picked(self.outcome, "gas_free")
        self.assertIn("ST", free.alternative.flags)
        self.assertLess(free.alternative.sizes_mw["electric_boiler"], 20.0)
        shared = next(
            e
            for e in self.outcome.candidates
            if e.alternative.code == free.alternative.code.replace("-ST", "")
        )
        self.assertEqual(shared.alternative.sizes_mw["electric_boiler"], 30.0)
        self.assertLess(free.economics.lcoe_eur_per_mwh, shared.economics.lcoe_eur_per_mwh - 4.0)

    def test_no_heat_pump_grown_for_nothing(self):
        """Gas boiler ruled out: no reliable plan grows a heat pump to hundreds of MW."""
        for e in self.no_boiler.candidates:
            self.assertLess(e.alternative.sizes_mw.get("heat_pump", 0.0), 50.0, e.alternative.code)
        failed = [
            e
            for e in self.no_boiler.candidates
            if e.alternative.reliable and e.alternative.role == "failed"
        ]
        self.assertTrue(failed)
        self.assertTrue(all("covers" in e.alternative.reason for e in failed))


class TestFailureGrid(unittest.TestCase):
    """A failure card and the yearly failure costs count the 600-hour grid contract (E5)."""

    @classmethod
    def setUpClass(cls):
        """Run the shared-train gas-free plan with doublet 1 out from 5 January to 4 May."""
        outcome = challenge()
        cls.entry = next(e for e in outcome.candidates if e.alternative.code == "2D-HP-AB-N1-EB-GS")
        cls.result = reliability.run_failure(cls.entry, [Failure("doublet 1", 4, 123)])

    def test_the_event_breaks_the_contract(self):
        """849 hours > 600: the grid charge rises by about 3 M€ and is in the card's cost."""
        f = self.result["failed"]
        self.assertGreater(f["electric_boiler_hours"], 600.0)
        self.assertLess(f["electric_boiler_hours_normal"], 600.0)
        self.assertGreater(f["extra_grid_keur"], 2500.0)
        self.assertGreater(f["extra_cost_keur"], f["extra_grid_keur"])
        text = reliability.failure_text(self.result, reporter.Facts(""), None)
        self.assertIn("600-hour contract", text)
        self.assertIn("its own", text)

    def test_the_yearly_cost_counts_it(self):
        """The ESPs' yearly cost carries the grid charge, and the words say so."""
        view = self.result["yearly"]
        self.assertGreater(view["grid_keur"], 500.0)
        self.assertTrue(all("grid_keur" in u for u in view["units"]))
        self.assertIn("grid charge", reliability.failure_costs_text(view, reporter.Facts("")))
        self.assertTrue(any("treatment train" in n for n in view["notes"]))


class TestFailureNumbersSourced(unittest.TestCase):
    """Every number in a failure reply is code's, the remedies' sizes and the code's depths too."""

    def test_cheapest_boiler_out_three_weeks(self):
        """The cheapest design's boiler out for 21 January days: a standby boiler of its size.

        4 Nov (S59): "With a standby boiler of 16.4 MW" and "1D-BO-EC@3500-FC" were reported
        as unsourced 16.4 and 3500.
        """
        cheapest = engine.picked(engine.search(DesignBrief()), "cost")  # deeper wells too
        result = reliability.run_failure(cheapest, [Failure("boiler", days=21)])
        facts = reporter.Facts("")
        text = reliability.failure_text(result, facts, None)
        names = " ".join(r["name"] for r in result["remedies"])
        self.assertRegex(names, r"\d", "a remedy names its size")
        text = f"{reporter.design_id(cheapest)}: {text}"
        self.assertEqual(answer.unsourced(text, facts), [], text)  # the agent's check


class TestInvestorHeat(unittest.TestCase):
    """SDE++ on the recommended design: geothermal heat only (E6)."""

    def test_the_heat_pumps_electricity_earns_nothing(self):
        """Eligible = exchanger + heat pump output - its electricity; capped at 6,000 h."""
        best = engine.picked(challenge(), "best")
        y = best.year
        ref = engine.reference(best.brief, None)
        case = dp.investor.investor_case(
            engine.plant_of(best.alternative),
            y,
            best.economics,
            engine.rules_for(best.brief),
            engine.prices_for(None, best.brief),
            ref.economics,
        )
        want = y.heat_split_gwh["geo"] + y.heat_split_gwh["hp"] - y.electricity_gwh["hp"]
        self.assertAlmostEqual(case.sde["eligible_gwh"], want, places=2)


class TestCentredUncertainty(unittest.TestCase):
    """The Monte Carlo draws are most likely at the case's own values (E13)."""

    @classmethod
    def setUpClass(cls):
        """Search once; the chosen design in a conversation-like session."""
        cls.outcome = challenge()
        for k, e in enumerate(engine.ranked(cls.outcome), 1):  # names, as the agent gives them
            e.alternative.uid = f"A{k}"
        cls.best = cls.outcome.chosen
        cls.session = SimpleNamespace(
            ledger=list(cls.outcome.candidates),
            assumptions={"gas_eur_per_mwh": 50.0},
            chosen=cls.best,
        )

    def test_base_values(self):
        """A change is 0, a factor 1, a price the chat's own, the return temperature 60 °C."""
        e, a = self.best, self.session.assumptions
        self.assertEqual(workbench.base_value(e, a, "reservoir_temp"), 0.0)
        self.assertEqual(workbench.base_value(e, a, "capex"), 1.0)
        self.assertEqual(workbench.base_value(e, a, "gas_price"), 50.0)
        self.assertEqual(workbench.base_value(e, {}, "gas_price"), dp.Prices().gas_eur_per_mwh)
        self.assertEqual(workbench.base_value(e, a, "heat_return"), 60.0)
        self.assertIsNone(workbench.base_value(e, a, "nonsense"))

    def test_draws_centre_on_the_case_and_say_where_it_sits(self):
        """Triangular draws around the case; its percentile is in the card and the words."""
        params = [
            {"key": "gas_price", "low": 40.0, "high": 100.0},
            {"key": "capex", "low": 0.8, "high": 1.3},
            {"key": "reservoir_temp", "low": -10.0, "high": 5.0},
        ]
        s = workbench.sensitivity(
            self.session, workbench.design_id(self.best), params, ["lcoe"], samples=40
        )
        mc = s["monte_carlo"]
        self.assertEqual(mc["modes"], {"gas_price": 50.0, "capex": 1.0, "reservoir_temp": 0.0})
        out = mc["outputs"]["lcoe"]
        self.assertTrue(0.0 <= out["base_percentile"] <= 1.0)
        self.assertAlmostEqual(out["base"], s["base"]["lcoe"], places=3)
        known = {p["key"]: p for p in workbench.sensitivity_parameters()["parameters"]}
        card = reliability.uncertainty_card(s, known)
        self.assertEqual(card["base_percentile"]["lcoe"], out["base_percentile"])
        text = reliability.uncertainty_text(card, reporter.Facts(""))
        self.assertIn("most likely at the design's own value", text)
        self.assertIn(f"P{round(out['base_percentile'] * 100)}", text)

    def test_a_case_outside_its_range_is_drawn_uniformly(self):
        """A mode outside the range is not used: the input is drawn uniformly."""
        params = [{"key": "gas_price", "low": 80.0, "high": 100.0}]  # the chat's 50 is below
        s = workbench.sensitivity(
            self.session, workbench.design_id(self.best), params, ["lcoe"], samples=5
        )
        self.assertIsNone(s["monte_carlo"]["modes"]["gas_price"])


if __name__ == "__main__":
    unittest.main()
