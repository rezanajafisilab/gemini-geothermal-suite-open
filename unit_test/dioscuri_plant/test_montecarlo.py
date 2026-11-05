"""Unplanned outages over drawn years (2 Nov): random failures, each year run, the worst case."""

import unittest
from unittest import mock

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant import failure_costs, montecarlo
from dioscuri_plant.failure_costs import RATES
from dioscuri_plant.firm import NO_SPARE_ESP_DAYS, SPARE_ESP_SWAP_DAYS
from gemini_agent import engine
from gemini_agent.contract import DesignBrief


def setting():
    """Return the challenge's demand, doublet model, rules and prices."""
    brief = DesignBrief()
    rules = engine.rules_for(brief)
    return engine.demand_of(brief), engine.doublet_model(rules), rules, dp.Prices()


class TestDraw(unittest.TestCase):
    """How the failures are drawn."""

    def test_rates_on_average(self):
        """Over many years an ESP fails about as often as its rate says."""
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)
        years = montecarlo.draw_years(plant, years=4000, seed=3)
        esp = sum(f.get("doublet 1", 0) for _, _, f in years) / len(years)
        self.assertAlmostEqual(esp, RATES["esp"].per_year, delta=0.05)
        for events, _, _ in years:
            for _, first, last in events:
                self.assertTrue(0 <= first <= last <= 364)

    def test_as_built_no_spare(self):
        """By default a failed ESP keeps its doublet out 120 days; with a spare, 7 (4 Nov)."""
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)

        def esp_days(spare):
            years = montecarlo.draw_years(plant, years=400, seed=5, spare_esp=spare)
            out = []
            for events, _, _ in years:
                days = sum(b - a + 1 for u, a, b in events if u == "doublet 1")
                if days:
                    out.append(days)
            return out

        self.assertEqual(
            montecarlo.draw_years(plant, years=50, seed=5),
            montecarlo.draw_years(plant, years=50, seed=5, spare_esp=False),
        )
        # Each failure 120 days (split at 31 December when it runs past it), or 7 with a spare.
        no_spare = esp_days(False)
        self.assertIn(NO_SPARE_ESP_DAYS, no_spare)
        self.assertTrue(all(d % NO_SPARE_ESP_DAYS == 0 for d in no_spare))
        spare = esp_days(True)
        self.assertIn(SPARE_ESP_SWAP_DAYS, spare)
        self.assertTrue(all(d % SPARE_ESP_SWAP_DAYS == 0 for d in spare))

    def test_coldest_window(self):
        """The worst case starts where 35 days in a row need the most heat."""
        demand, _, _, _ = setting()
        start = montecarlo.coldest_window(demand)
        heat = np.asarray(demand.heat_mw)
        best = max(range(365 - 35 + 1), key=lambda i: heat[i : i + 35].sum())
        self.assertEqual(start, best)


class TestUnplanned(unittest.TestCase):
    """A plant sized for one unit out never runs short; one that is not, sometimes does."""

    def test_backed_up_and_not(self):
        """Boilers that carry the peak alone: never short; a small boiler: short in some years."""
        demand, model, rules, prices = setting()
        peak = float(max(demand.heat_mw))
        firm = dp.Plant(1, boiler_mw=peak, boiler_units=3, chiller_mw=12.0, chiller_units=3)
        thin = dp.Plant(1, boiler_mw=0.5 * peak, chiller_mw=12.0)
        a = montecarlo.unplanned(firm, demand, model, rules, prices, years=300)
        b = montecarlo.unplanned(thin, demand, model, rules, prices, years=300)
        self.assertEqual(a["heat_mwh"]["share_above_zero"], 0.0)
        self.assertGreater(b["heat_mwh"]["share_above_zero"], 0.0)
        self.assertGreater(b["worst"]["heat_mwh"], 0.0)
        self.assertEqual(sum(b["histogram"]["years"]), 300)
        # As built (no spare ESP) each pump failure lasts months: with a spare, failures cost
        # less (4 Nov: the default was the spare, which no design pays for).
        self.assertFalse(b["spare_esp"])
        c = montecarlo.unplanned(thin, demand, model, rules, prices, years=300, spare_esp=True)
        self.assertLess(c["total_keur"]["mean"], b["total_keur"]["mean"])


class TestRiskBasis(unittest.TestCase):
    """The risk size: as built (no spare ESP), and the unit that backs the plant up (4 Nov)."""

    def test_backup_of(self):
        """Gas bought: the gas boiler; no gas bought: the electric boiler, even beside a gas one."""
        self.assertEqual(montecarlo.backup_of(dp.Plant(1, boiler_mw=30.0)), "boiler_mw")
        self.assertEqual(
            montecarlo.backup_of(dp.Plant(1, electric_boiler_mw=20.0)), "electric_boiler_mw"
        )
        for gas in ("produced", "sell"):
            plant = dp.Plant(1, boiler_mw=5.5, electric_boiler_mw=25.4, gas=gas)
            self.assertEqual(montecarlo.backup_of(plant), "electric_boiler_mw")

    def test_produced_gas_plant_sizes_its_electric_boiler(self):
        """A36's case: the 5.5 MW brine-gas boiler stays, the electric backup is the one sized."""
        demand, model, rules, _ = setting()
        peak = float(max(demand.heat_mw))
        plant = dp.Plant(
            1,
            depth_m=3500.0,
            boiler_mw=5.5,
            electric_boiler_mw=peak,
            electric_boiler_units=3,
            chiller_mw=12.0,
            gas="produced",
        )
        r = montecarlo.risk_sizing(plant, demand, model, rules, years=60, steps=2)
        self.assertEqual(r["unit"], "electric_boiler_mw")
        self.assertEqual(r["n1_mw"], peak)
        self.assertFalse(r["spare_esp"])

    def test_spare_lowers_the_days_short(self):
        """A thin backup runs short more often without a spare ESP than with one."""
        demand, model, rules, _ = setting()
        thin = dp.Plant(1, depth_m=3500.0, boiler_mw=0.6 * float(max(demand.heat_mw)))
        built = montecarlo.lole(thin, demand, model, rules, years=200)
        spare = montecarlo.lole(thin, demand, model, rules, years=200, spare_esp=True)
        self.assertGreater(built["lole_days"], spare["lole_days"])

    def test_shared_train_not_drawn(self):
        """Two doublets on one treatment train: the train has no failure rate and is said so."""
        plant = dp.Plant(2, boiler_mw=30.0)
        self.assertEqual(montecarlo.not_drawn(plant), ["the shared treatment train"])
        self.assertEqual(montecarlo.not_drawn(dp.Plant(1, boiler_mw=30.0)), [])


class TestGridInTheYears(unittest.TestCase):
    """Each drawn year counts the electric boiler's grid charge, as ``failure_costs`` does."""

    def test_agrees_with_failure_costs(self):
        """The gas-free pick's layout (A33): the Monte Carlo mean matches the expected cost.

        With ESP failures rare (0.05 a year per doublet) two in one year almost never happen,
        so the first-order expectation of ``failure_costs`` and the drawn years' mean agree
        within the drawing's noise; the grid charge is half of it (an ESP out 120 days pushes
        the electric boiler past the 600-hour contract). Before 4 Nov the drawn years left the
        grid charge out (529 k€ against 258 here). At the real rate (0.5) the drawn years count
        the jump once a year and ``failure_costs`` once per failure, so it is higher there.
        """
        demand, model, rules, prices = setting()
        specs = tuple(dp.Doublet(depth_m=3400.0, max_flow_m3h=270.0) for _ in range(2))
        plant = dp.Plant(
            2,
            depth_m=3400.0,
            doublet_specs=specs,
            gas="sell",
            absorption_mw=0.23,
            chiller_mw=14.7,
            chiller_units=3,
            electric_boiler_mw=30.0,
            electric_boiler_units=3,
            reliable=True,
        )
        esp = RATES["esp"]
        rare = failure_costs.Rate(
            0.05, esp.repair_days, esp.repair_meur, no_spare_days=esp.no_spare_days
        )
        with mock.patch.dict(RATES, {"esp": rare}):
            expected = failure_costs.failure_costs(plant, demand, model, rules, prices=prices)
            drawn = montecarlo.unplanned(plant, demand, model, rules, prices, years=4000)
        self.assertGreater(expected["grid_keur"], 0.3 * expected["total_keur"])
        self.assertAlmostEqual(
            drawn["total_keur"]["mean"], expected["total_keur"], delta=0.05 * expected["total_keur"]
        )
        self.assertAlmostEqual(
            drawn["grid_keur"]["mean"], expected["grid_keur"], delta=0.1 * expected["grid_keur"]
        )


if __name__ == "__main__":
    unittest.main()
