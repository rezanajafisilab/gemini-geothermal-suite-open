"""Failures over a year: the expected cost per unit, and what a spare ESP is worth."""

import time
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from dioscuri_plant import Demand, Plant, Prices, Rules, simulate_year, stub_doublet
from dioscuri_plant.economics import crf, grid_capacity_meur
from dioscuri_plant.failure_costs import (
    DAYS,
    RATES,
    SOURCES,
    _grid_charges,
    _window_weights,
    electric_boiler_hours,
    expected_cost,
    failure_costs,
    grid_break_share,
    grid_change_meur,
    outage_runs,
    running_meur,
    spare_esp_worth,
    spare_yearly_keur,
)
from dioscuri_plant.firm import SPARE_ESP_MEUR, failure, reliable

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
PLANT = Plant(2, heat_pump_mw=3.9, boiler_mw=11.7, absorption_mw=1.0, chiller_mw=9.0)


def unit(costs, name):
    """Return one unit's row of ``expected_cost``."""
    return next(u for u in costs["units"] if u["unit"] == name)


class TestExpectedCost(unittest.TestCase):
    """Each unit's failures a year x what one costs, averaged over the start days."""

    @classmethod
    def setUpClass(cls):
        """Run each unit out all year once for the challenge-sized plant."""
        cls.rules, cls.prices = Rules(), Prices()
        cls.runs = outage_runs(PLANT, DEMAND, stub_doublet, cls.rules, prices=cls.prices)
        cls.costs = expected_cost(cls.runs)

    def test_every_unit_with_data_and_the_rest_named(self):
        """Both doublets' ESPs and every surface unit; the shared train has no failure data."""
        names = {u["unit"] for u in self.costs["units"]}
        self.assertEqual(
            names,
            {
                "doublet 1",
                "doublet 2",
                "heat exchanger",
                "heat pump",
                "boiler",
                "chillers",
                "absorption",
            },
        )
        self.assertEqual(self.costs["skipped"], ["the shared treatment train"])
        for key in RATES:
            self.assertIn(key, SOURCES)

    def test_by_hand(self):
        """ESP of doublet 1: 0.5 a year x (120/365 x the all-year cost + the swap)."""
        run = next(r for r in self.runs if r["unit"] == "doublet 1")
        esp = RATES["esp"]
        lost = run["heat_mwh"] + run["cold_mwh"]
        want = esp.per_year * (
            esp.no_spare_days / DAYS * (run["running_meur"] * 1000 + lost * 122.0 / 1000)
            + esp.repair_meur * 1000
        )
        got = unit(self.costs, "doublet 1")
        self.assertAlmostEqual(got["total_keur"], want, places=1)
        self.assertAlmostEqual(got["repair_keur"], 0.5 * 350.0, places=6)
        self.assertAlmostEqual(got["out_days"], 60.0, places=6)
        self.assertGreater(got["running_keur"], 0)  # the boiler burns gas for the lost brine

    def test_a_unit_that_never_fails_costs_nothing(self):
        """The boiler at 0 failures a year: nothing a year, nothing not delivered."""
        never = expected_cost(self.runs, rates={"boiler": replace(RATES["boiler"], per_year=0.0)})
        boiler = unit(never, "boiler")
        self.assertEqual(boiler["total_keur"], 0.0)
        self.assertEqual(boiler["lost_mwh"], 0.0)
        self.assertAlmostEqual(
            never["total_keur"],
            self.costs["total_keur"] - unit(self.costs, "boiler")["total_keur"],
            delta=0.1,
        )

    def test_doubling_the_failure_rate_doubles_the_cost(self):
        """Twice the failures a year: twice each unit's cost and twice the MWh not delivered."""
        twice = {k: replace(r, per_year=2 * r.per_year) for k, r in RATES.items()}
        double = expected_cost(self.runs, rates=twice)
        for u in self.costs["units"]:
            self.assertAlmostEqual(
                unit(double, u["unit"])["total_keur"], 2 * u["total_keur"], delta=0.02
            )
        self.assertAlmostEqual(double["total_keur"], 2 * self.costs["total_keur"], delta=0.2)
        self.assertAlmostEqual(double["lost_mwh"], 2 * self.costs["lost_mwh"], delta=0.2)

    def test_the_average_over_start_days(self):
        """Five 73-day outages that tile the year cost what the all-year run costs.

        So d days out, averaged over every start day, cost d/365 of the all-year run: the
        days of the daily model do not depend on each other.
        """
        base = simulate_year(PLANT, DEMAND, stub_doublet, self.rules)
        base_cost = running_meur(base, self.prices, self.rules)
        run = next(r for r in self.runs if r["unit"] == "doublet 1")
        total = 0.0
        for k in range(5):
            y = failure(PLANT, DEMAND, stub_doublet, [("doublet 1", 73 * k, 73 * k + 72)])
            total += running_meur(y, self.prices, self.rules) - base_cost
        self.assertAlmostEqual(total, run["running_meur"], delta=0.002)

    def test_a_spare_shortens_the_esp_outages(self):
        """With a spare on the shelf the ESPs are out 7 days, not 120: less cost, less lost."""
        spare = expected_cost(self.runs, spare_esp=True)
        self.assertEqual(unit(spare, "doublet 1")["repair_days"], RATES["esp"].repair_days)
        self.assertLess(spare["total_keur"], self.costs["total_keur"])
        self.assertLess(spare["lost_mwh"], self.costs["lost_mwh"])

    def test_the_stress_value(self):
        """At 10,000 €/MWh only the heat and cold not delivered are worth more."""
        stress = expected_cost(self.runs, lost_eur_per_mwh=10_000.0)
        self.assertAlmostEqual(stress["total_keur"], self.costs["stress_keur"], delta=0.3)
        self.assertGreater(self.costs["stress_keur"], self.costs["total_keur"])

    def test_equal_units_count_each(self):
        """A boiler of three equal units: three units that fail, one out at a time."""
        three = replace(PLANT, boiler_units=3, boiler_mw=3 * PLANT.boiler_mw)
        costs = expected_cost(outage_runs(three, DEMAND, stub_doublet, self.rules))
        boilers = unit(costs, "boiler unit")
        self.assertAlmostEqual(boilers["failures_per_year"], 3 * RATES["boiler"].per_year)
        self.assertIn("3 boiler units", boilers["words"])


class TestSpareEsp(unittest.TestCase):
    """A spare ESP pays when the days it saves cost more than its capital."""

    @classmethod
    def setUpClass(cls):
        """Run the outages once."""
        cls.prices = Prices()
        cls.runs = outage_runs(PLANT, DEMAND, stub_doublet, Rules(), prices=cls.prices)

    def worth(self, per_year):
        """Return the spare's verdict at an ESP failure rate."""
        rates = {"esp": replace(RATES["esp"], per_year=per_year)}
        return spare_esp_worth(self.runs, self.prices, rates=rates)

    def test_its_yearly_cost(self):
        """Its price over the doublets' 30 years at 5.2 %: about 20 k€ a year."""
        want = SPARE_ESP_MEUR * crf(0.052, 30) * 1000
        self.assertAlmostEqual(spare_yearly_keur(self.prices), want, places=6)
        self.assertAlmostEqual(self.worth(0.5)["yearly_keur"], want, places=1)

    def test_its_value_falls_with_the_failure_rate(self):
        """Fewer failures, less saved; with none it only costs its capital."""
        nets = [self.worth(lam)["net_keur"] for lam in (1.0, 0.5, 0.2, 0.0)]
        self.assertEqual(nets, sorted(nets, reverse=True))
        zero = self.worth(0.0)
        self.assertLess(zero["net_keur"], 0)
        self.assertAlmostEqual(zero["net_keur"], -zero["yearly_keur"], places=6)
        self.assertFalse(zero["worth"])

    def test_break_even(self):
        """At the break-even failure rate it saves what it costs."""
        base = self.worth(0.5)
        self.assertTrue(base["worth"])
        even = self.worth(base["break_even_per_year"])
        self.assertAlmostEqual(even["net_keur"], 0.0, delta=0.2)
        self.assertLess(base["break_even_per_year"], 0.5)

    def test_no_doublet_no_spare(self):
        """The gas reference has no ESP to keep a spare for."""
        gas = Plant(0, boiler_mw=40.0, chiller_mw=12.0)
        self.assertIsNone(spare_esp_worth(outage_runs(gas, DEMAND, stub_doublet)))


# A gas-free plant whose electric boiler is a backup: under 600 hours a year at its peak.
GAS_FREE = Plant(
    2,
    heat_pump_mw=13.0,
    absorption_mw=6.0,
    chiller_mw=10.0,
    electric_boiler_mw=30.0,
    electric_boiler_units=3,
    gas="sell",
)


class TestGridContract(unittest.TestCase):
    """An outage that pushes the electric boiler past 600 hours costs the year's contract."""

    @classmethod
    def setUpClass(cls):
        """Run each unit of the gas-free plant out all year once."""
        cls.base = simulate_year(GAS_FREE, DEMAND, stub_doublet, Rules())
        cls.runs = outage_runs(GAS_FREE, DEMAND, stub_doublet, Rules(), base=cls.base)
        cls.esp = next(r for r in cls.runs if r["unit"] == "doublet 1")

    def test_a_backup_under_600_hours(self):
        """Normally the electric boiler runs well under 600 hours: the 600-hour contract."""
        hours = electric_boiler_hours(self.base)
        self.assertLess(hours, 600.0)
        kw = 30.0 / 0.99 * 1000
        self.assertLess(grid_capacity_meur(GAS_FREE, self.base), 123.0 * kw / 1e6)

    def test_each_start_day_as_its_own_year(self):
        """The year spliced from the all-year run equals the year run with the outage itself."""
        grid = self.esp["grid"]
        base = np.asarray(grid["base_mw"])
        out = np.asarray(grid["out_mw"])
        rows = _window_weights(120)
        for start in (4, 150):  # a winter outage breaks the 600 hours, a summer one does not
            spliced = base + rows[start] * (out - base)
            event = failure(GAS_FREE, DEMAND, stub_doublet, [("doublet 1", start, start + 119)])
            self.assertAlmostEqual(
                _grid_charges(spliced[None, :], grid)[0],
                grid_capacity_meur(GAS_FREE, event),
                places=9,
            )
        winter = failure(GAS_FREE, DEMAND, stub_doublet, [("doublet 1", 4, 123)])
        self.assertGreater(electric_boiler_hours(winter), 600.0)
        self.assertAlmostEqual(grid_capacity_meur(GAS_FREE, winter), 0.123 * 30.0 / 0.99, 6)

    def test_the_cliff_averaged_over_start_days(self):
        """About half the 120-day ESP outages break it: +1.6 M€ per failure on average."""
        grid = self.esp["grid"]
        share = grid_break_share(grid, 120)
        self.assertTrue(0.2 < share < 0.9)
        jump = 123.0 * 30.0 / 0.99 - grid_capacity_meur(GAS_FREE, self.base) * 1e3  # k€
        self.assertAlmostEqual(grid_change_meur(grid, 120) * 1e3, share * jump, delta=0.05 * jump)
        self.assertLess(grid_change_meur(grid, 7), grid_change_meur(grid, 120) / 10)
        self.assertEqual(grid_change_meur(grid, 0), 0.0)
        self.assertEqual(grid_change_meur(None, 120), 0.0)

    def test_counted_in_the_expected_cost(self):
        """The ESP's yearly cost carries the grid charge, once per failure; the total adds up."""
        costs = expected_cost(self.runs)
        row = unit(costs, "doublet 1")
        esp = RATES["esp"]
        self.assertAlmostEqual(
            row["grid_keur"], esp.per_year * grid_change_meur(self.esp["grid"], 120) * 1e3, 1
        )
        self.assertAlmostEqual(
            row["total_keur"],
            row["running_keur"] + row["grid_keur"] + row["lost_keur"] + row["repair_keur"],
            places=1,
        )
        self.assertAlmostEqual(
            costs["grid_keur"], sum(u["grid_keur"] for u in costs["units"]), places=0
        )
        self.assertGreater(row["grid_keur"], 0.5 * row["running_keur"])  # as large as the gas

    def test_a_spare_saves_the_grid_charge_too(self):
        """With the cliff the spare ESP saves more than the running costs alone."""
        bare = [dict(r, grid=None) for r in self.runs]
        with_grid = spare_esp_worth(self.runs)
        without = spare_esp_worth(bare)
        self.assertGreater(with_grid["saving_keur"], without["saving_keur"] + 100.0)

    def test_said_in_the_notes(self):
        """The notes give the hours, the 600-hour rule per connection and the train not counted."""
        out = failure_costs(GAS_FREE, DEMAND, stub_doublet)
        text = " ".join(out["notes"])
        self.assertIn("600-hour contract", text)
        self.assertIn("its own", text)  # the backup's own connection
        self.assertIn("not counted: the shared treatment train", text)
        self.assertEqual(out["grid"]["contract"], "600-hour")
        self.assertGreater(out["grid"]["hours_left"], 0.0)
        self.assertGreater(out["grid_keur"], 0.0)
        for key in ("grid_600h", "treatment train"):
            self.assertIn(key, SOURCES)


class TestDesigns(unittest.TestCase):
    """A design's failures in one call, fast; a reliable plan leaves less heat undelivered."""

    def test_reliable_plan_loses_less_heat(self):
        """Any one unit out still meets every day: failures leave less heat not delivered."""
        plan, _, _ = reliable(PLANT, DEMAND, stub_doublet, Rules())
        cheap = failure_costs(PLANT, DEMAND, stub_doublet)
        safe = failure_costs(plan, DEMAND, stub_doublet)
        self.assertGreater(cheap["lost_heat_mwh"], 0.0)
        self.assertLess(safe["lost_heat_mwh"], cheap["lost_heat_mwh"])
        self.assertLess(safe["stress_keur"], cheap["stress_keur"])

    def test_one_design_in_well_under_a_second(self):
        """Each unit out once and the normal year: a few runs of a few ms."""
        start = time.perf_counter()
        out = failure_costs(PLANT, DEMAND, stub_doublet)
        self.assertLess(time.perf_counter() - start, 1.0)
        self.assertIn("with_spare", out)
        self.assertTrue(out["spare_esp"]["worth"])
        self.assertTrue(any("floor" in n for n in out["notes"]))


if __name__ == "__main__":
    unittest.main()
