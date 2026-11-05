"""The maintenance the user sets (2 Nov): each doublet's days off, and each unit's yearly service.

The doublets' stop may be longer (or, with the cap relaxed, shorter) than the 35 days the
330-day cap leaves; each unit type's service is off, in the quietest weeks, or on the user's
dates, and a unit the design does not have is never serviced.
"""

import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet
from dioscuri_plant.service import windows
from dioscuri_plant.year import stop_ranges, stop_windows

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
HEAT = np.asarray(DEMAND.heat_mw)
COOL = np.asarray(DEMAND.cool_mw)


class TestDaysOff(unittest.TestCase):
    """Each doublet's own days off, placed by Dioscuri in its quietest block."""

    def test_each_doublet_its_own_length(self):
        """Doublet 1 off 50 days, doublet 2 the 35 the cap leaves; the blocks do not overlap."""
        (a1, b1), (a2, b2) = stop_windows(HEAT, 2, 330, lengths=(50, 0))
        self.assertEqual(b1 - a1 + 1, 50)
        self.assertEqual(b2 - a2 + 1, 35)
        self.assertTrue(b1 < a2 or b2 < a1)

    def test_without_lengths_nothing_changes(self):
        """No lengths: exactly the blocks of before."""
        self.assertEqual(stop_windows(HEAT, 2, 330, lengths=()), stop_windows(HEAT, 2, 330))
        self.assertEqual(
            stop_ranges(HEAT, 2, 330, lengths=None), [[w] for w in stop_windows(HEAT, 2, 330)]
        )

    def test_the_year_runs_a_doublet_for_its_days(self):
        """A 50-day stop: the doublet runs at most 315 days of the year."""
        rules = replace(Rules(), stop_days_off=(50,))
        plant = Plant(1, heat_pump_mw=4, boiler_mw=30, chiller_mw=12)
        year = simulate_year(plant, DEMAND, stub_doublet, rules)
        self.assertLessEqual(sum(year.doublets[0]["on"]), 315)
        a, b = year.stop_ranges[0][0]
        self.assertEqual(b - a + 1, 50)


class TestServicePlan(unittest.TestCase):
    """Each unit type's service: off, Dioscuri's quietest weeks, or the user's dates."""

    def test_dates_off_and_auto(self):
        """The heat pump on the user's dates, the boiler off, the chillers in their quiet weeks."""
        plan = {"heat pump": ("dates", [(120, 133)]), "boiler": ("off", [])}
        w = windows(HEAT, COOL, boiler_units=3, chiller_units=2, plan=plan, auto=True)
        self.assertIn(("heat pump", 120, 133), w)
        self.assertFalse(any(u.startswith("boiler") for u, _, _ in w))
        self.assertEqual(sum(1 for u, _, _ in w if u == "chiller unit"), 2)

    def test_auto_off_only_the_planned_units(self):
        """Service switched off: only the unit types the user planned are taken out."""
        plan = {"heat exchanger": ("auto", [])}
        w = windows(HEAT, COOL, boiler_units=3, chiller_units=2, plan=plan, auto=False)
        self.assertEqual([u for u, _, _ in w], ["heat exchanger"])

    def test_a_bank_takes_dates_in_turn_and_the_rest_in_quiet_weeks(self):
        """Two dates for a 3-unit boiler: units 1 and 2 on them, unit 3 in the quietest week."""
        plan = {"boiler": ("dates", [(150, 156), (160, 166)])}
        w = [
            x
            for x in windows(HEAT, COOL, boiler_units=3, chiller_units=0, plan=plan, auto=False)
            if x[0] == "boiler unit"
        ]
        self.assertEqual(w[:2], [("boiler unit", 150, 156), ("boiler unit", 160, 166)])
        self.assertEqual(len(w), 3)

    def test_a_unit_the_design_lacks_gets_no_window(self):
        """No heat pump in the design: no heat pump service, whatever the plan says."""
        plan = {"heat pump": ("dates", [(120, 133)])}
        w = windows(
            HEAT, COOL, boiler_units=1, chiller_units=1, plan=plan, has={"heat pump": False}
        )
        self.assertFalse(any(u == "heat pump" for u, _, _ in w))


if __name__ == "__main__":
    unittest.main()
