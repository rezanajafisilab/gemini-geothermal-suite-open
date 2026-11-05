"""The plant over a year: balances close every day, caps are reported, hand checks agree."""

import time
import unittest
from pathlib import Path

import numpy as np

from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet
from dioscuri_plant.components import heat_pump_cop, heat_pump_on_source, produced_gas
from dioscuri_plant.year import stop_windows

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
TWO = Plant(2, heat_pump_mw=12, boiler_mw=8, absorption_mw=4, chiller_mw=7)


class TestDemand(unittest.TestCase):
    """The organisers' files, read as they are."""

    def test_totals_and_peaks_match_the_requirements(self):
        """111.67 GWh and 30 MW of heat, 23.74 GWh and 10 MW of cold."""
        heat, cool = DEMAND.arrays()
        self.assertAlmostEqual(heat.sum() * 24 / 1000, 111.67, places=1)
        self.assertAlmostEqual(cool.sum() * 24 / 1000, 23.74, places=1)
        self.assertAlmostEqual(heat.max(), 30.0, places=1)
        self.assertEqual(DEMAND.dates[int(heat.argmax())], "2027-01-28")
        self.assertEqual(DEMAND.dates[int(cool.argmax())], "2027-07-19")


class TestComponents(unittest.TestCase):
    """Each formula against a hand calculation."""

    def test_heat_pump_cop_is_a_fraction_of_carnot(self):
        """COP = 0.5 x 373.15 / (100 - 50) = 3.73."""
        self.assertAlmostEqual(float(heat_pump_cop(100, 50, 0.5)), 0.5 * 373.15 / 50, places=6)

    def test_heat_pump_on_the_brine_balances_its_evaporator(self):
        """The heat taken from the brine is heat x (1 - 1/COP) at the outlet it reaches."""
        heat, t_out, cop, el = heat_pump_on_source(
            np.array([5.0]), np.array([65.0]), np.array([0.5]), 100.0, 46.0, 0.5
        )
        self.assertAlmostEqual(float(0.5 * (65 - t_out[0])), float(heat[0] - el[0]), places=4)
        self.assertAlmostEqual(float(cop[0]), float(heat_pump_cop(100, t_out[0], 0.5)), places=6)

    def test_produced_gas_of_a_full_doublet(self):
        """300 m3/h x 0.8 x 0.8 = 192 Nm3/h of CH4, about 1.9 MW."""
        mw, ch4, co2 = produced_gas(np.array([300.0]), 0.8, 0.8, 0.2)
        self.assertAlmostEqual(float(ch4[0]), 192.0)
        self.assertAlmostEqual(float(co2[0]), 48.0)
        self.assertAlmostEqual(float(mw[0]), 192 * 35.8 / 3600, places=6)


class TestYear(unittest.TestCase):
    """A year of a two-doublet design with the stub doublet."""

    @classmethod
    def setUpClass(cls):
        """Run the year once."""
        cls.year = simulate_year(TWO, DEMAND, stub_doublet)

    def test_every_day_balances(self):
        """Heat and cold delivered equal the sources each day (0.1 % at most)."""
        self.assertLess(self.year.balance_error, 1e-3)
        h = self.year.daily_mw["heat"]
        for d in range(365):
            sources = h["geo"][d] + h["hp"][d] + h["boiler"][d]
            self.assertAlmostEqual(sources + h["short"][d], h["demand"][d], places=2)

    def test_caps_hold_and_none_are_reported(self):
        """Flows in 50-300 m3/h, brine cooled by at most 40 K, 330 days each."""
        self.assertEqual(self.year.violations, [])
        self.assertLessEqual(self.year.max_brine_cooling_k, 40.0 + 1e-6)
        for d in self.year.doublets:
            flows = [f for f, on in zip(d["flow_m3h"], d["on"]) if on]
            self.assertGreaterEqual(min(flows), 50.0 - 1e-6)
            self.assertLessEqual(max(flows), 300.0 + 1e-6)
            self.assertLessEqual(sum(d["on"]), 330)

    def test_a_short_plant_reports_the_day_and_the_gap(self):
        """One doublet and a small boiler: the January peak is short, said in a sentence."""
        year = simulate_year(
            Plant(1, heat_pump_mw=4, boiler_mw=5, chiller_mw=10), DEMAND, stub_doublet
        )
        self.assertTrue(any("Heat short" in v and "MW on" in v for v in year.violations))
        self.assertGreater(year.peak_shortfall_mw["heat"], 0)

    def test_the_gas_reference_burns_gas_for_all_heat(self):
        """No doublet: the boiler covers 111.67 GWh at its efficiency, and the gas has its CO2."""
        from dioscuri_plant import Components

        ref = simulate_year(Plant(0, boiler_mw=31, chiller_mw=10.5), DEMAND, stub_doublet)
        self.assertAlmostEqual(ref.heat_split_gwh["boiler"], 111.67, places=1)
        eff = Components().boiler_efficiency
        self.assertAlmostEqual(ref.purchased_gas_gwh, 111.668 / eff, places=1)
        self.assertAlmostEqual(
            ref.co2_t["purchased_gas"], ref.purchased_gas_gwh * 1000 * 0.202, places=0
        )

    def test_produced_gas_is_burnt_before_the_heat_pump_runs(self):
        """The gas would be flared anyway, so the boiler takes it first."""
        self.assertGreater(
            self.year.produced_gas_burned_gwh, 10 * self.year.produced_gas_flared_gwh
        )

    def test_stops_are_staggered_in_quiet_weeks(self):
        """Two doublets stop for 35 days each, never together."""
        (a0, a1), (b0, b1) = self.year.stop_days
        self.assertEqual((a1 - a0 + 1, b1 - b0 + 1), (35, 35))
        self.assertTrue(a1 < b0 or b1 < a0)
        self.assertEqual(stop_windows(np.ones(365), 1, 365), [])

    def test_a_year_is_fast(self):
        """Well under 50 ms a year, so the agent can search hundreds of designs."""
        start = time.perf_counter()
        for _ in range(10):
            simulate_year(TWO, DEMAND, stub_doublet)
        self.assertLess((time.perf_counter() - start) / 10, 0.05)

    def test_rules_change_the_answer(self):
        """A colder network return lets the brine give more heat directly."""
        cold = simulate_year(TWO, DEMAND, stub_doublet, Rules(heat_return_c=50.0))
        self.assertGreater(cold.heat_split_gwh["geo"], self.year.heat_split_gwh["geo"])

    def test_nonsense_is_refused(self):
        """Five doublets are not a design."""
        with self.assertRaises(ValueError):
            Plant(5)


class TestGeminiDoublet(unittest.TestCase):
    """GEMINI's well solve (with the brine, patch 11) agrees with the hand physics."""

    def test_gemini_and_hand_physics_agree_within_one_percent(self):
        """ESP head and injection pressure at 300 m3/h."""
        from gemini_agent.tools.gemini import doublet_point

        g, s = doublet_point(300, 2500), stub_doublet(300, 2500)
        self.assertAlmostEqual(g["esp_head_bar"], s["esp_head_bar"], delta=0.01 * s["esp_head_bar"])
        self.assertAlmostEqual(
            g["injection_wellhead_bar"],
            s["injection_wellhead_bar"],
            delta=0.01 * s["injection_wellhead_bar"],
        )


if __name__ == "__main__":
    unittest.main()
