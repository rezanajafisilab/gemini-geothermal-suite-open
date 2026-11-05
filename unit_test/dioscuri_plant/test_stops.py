"""The doublets' planned stops on the user's dates: one block or several ranges per doublet."""

import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet
from dioscuri_plant.year import stop_ranges, stop_windows

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
TWO = Plant(2, heat_pump_mw=12, boiler_mw=8, absorption_mw=4, chiller_mw=7)
# Doublet 1 off 30 Jun - 19 Jul and 19 Aug - 2 Sep (20 + 15 = 35 days); doublet 2 not given.
MINE = (((180, 199), (230, 244)),)


def days_on(year, k):
    """Return the days doublet ``k`` (0-based) ran."""
    return [i for i, on in enumerate(year.doublets[k]["on"]) if on]


class TestStopRanges(unittest.TestCase):
    """Where each doublet stops: Dioscuri's quietest block, or the user's dates."""

    def test_without_dates_the_blocks_are_dioscuris(self):
        """Nothing given: one block per doublet, exactly as before (stop_windows)."""
        need = np.asarray(DEMAND.heat_mw)
        self.assertEqual(stop_ranges(need, 2, 330), [[w] for w in stop_windows(need, 2, 330)])
        self.assertEqual(stop_ranges(need, 0, 330), [])

    def test_given_dates_stand_and_the_rest_avoid_them(self):
        """Doublet 1 on its two ranges; doublet 2 in the quietest block that overlaps neither."""
        need = np.asarray(DEMAND.heat_mw)
        ranges = stop_ranges(need, 2, 330, given=MINE)
        self.assertEqual(ranges[0], [(180, 199), (230, 244)])
        (a, b) = ranges[1][0]
        self.assertEqual(b - a + 1, 35)
        self.assertTrue(all(b < x or a > y for x, y in ranges[0]))
        # Dates for a doublet the design does not have are left out.
        self.assertEqual(len(stop_ranges(need, 1, 330, given=MINE + (((10, 44),),))), 1)

    def test_at_365_days_only_the_given_dates_stop(self):
        """No stop is needed at 365 operating days; a doublet with dates still stops on them."""
        need = np.ones(365)
        self.assertEqual(stop_ranges(need, 2, 365, given=MINE), [list(MINE[0]), []])


class TestYearOnTheUsersDates(unittest.TestCase):
    """A year run on the user's stop dates."""

    @classmethod
    def setUpClass(cls):
        """One year on Dioscuri's blocks and one on the user's ranges."""
        cls.base = simulate_year(TWO, DEMAND, stub_doublet)
        cls.mine = simulate_year(TWO, DEMAND, stub_doublet, replace(Rules(), doublet_stops=MINE))

    def test_the_doublet_is_off_on_every_day_asked(self):
        """No flow on any of the 35 days; the year reports both ranges."""
        on = set(days_on(self.mine, 0))
        off = set(range(180, 200)) | set(range(230, 245))
        self.assertFalse(on & off)
        self.assertEqual(self.mine.stop_ranges[0], [(180, 199), (230, 244)])
        self.assertEqual(self.mine.stop_days[0], (180, 199))  # its first stop, for older readers
        self.assertEqual(len(self.base.stop_ranges), 2)
        self.assertEqual([r[0] for r in self.base.stop_ranges], self.base.stop_days)

    def test_the_cap_holds_and_the_balance_closes(self):
        """Each doublet runs at most 330 days; the year is as sound as Dioscuri's own."""
        for k in range(2):
            self.assertLessEqual(len(days_on(self.mine, k)), 330)
        self.assertFalse([v for v in self.mine.violations if "more than 330" in v])
        self.assertLess(self.mine.balance_error, 1e-6)

    def test_too_few_days_off_breaks_the_cap_and_says_so(self):
        """20 days off where the cap needs 35: the doublet runs over 330 days, a violation."""
        short = simulate_year(
            Plant(1, heat_pump_mw=12, boiler_mw=25, absorption_mw=4, chiller_mw=7),
            DEMAND,
            stub_doublet,
            replace(Rules(), doublet_stops=(((180, 199),),)),
        )
        ran = len(days_on(short, 0))
        self.assertGreater(ran, 330)
        self.assertIn(f"Doublet 1 runs {ran} days, more than 330.", short.violations)

    def test_failures_keep_the_users_stops(self):
        """A failure year (the doublet's train out a week) leaves the stops where they were."""
        out = simulate_year(
            replace(TWO, outages=(("doublet 2", 20, 26),)),
            DEMAND,
            stub_doublet,
            replace(Rules(), doublet_stops=MINE),
        )
        self.assertEqual(out.stop_ranges, self.mine.stop_ranges)
        self.assertFalse(set(days_on(out, 0)) & (set(range(180, 200)) | set(range(230, 245))))


if __name__ == "__main__":
    unittest.main()
