"""Fixes from the 4 Nov audit of the physics: wells, dispatch, stops, heat pump."""

import math
import unittest

import numpy as np

from dioscuri_plant import Rules
from dioscuri_plant.components import MIN_LIFT_K, heat_pump_cop, heat_pump_on_source
from dioscuri_plant.doublet import productivity_index_m3h_per_bar, stub_doublet
from dioscuri_plant.year import dispatch, stop_ranges


class TestDoubletIndex(unittest.TestCase):
    """The index of a doublet at steady state: 2 pi k h / (mu ln(L / r_w))."""

    def test_hand_value(self):
        """The challenge's aquifer, 1,500 m apart: 11.70 m3/h/bar."""
        r = Rules()
        kh = 200 * 9.869e-16 * 100
        hand = 2 * math.pi * kh / (0.4e-3 * math.log(1500 / 0.10795)) * 3600 * 1e5
        self.assertAlmostEqual(productivity_index_m3h_per_bar(r), hand, places=6)
        self.assertAlmostEqual(productivity_index_m3h_per_bar(r), 11.70, places=2)

    def test_wider_spacing_lowers_it(self):
        """Wells further apart: more pressure for the same flow."""
        near = productivity_index_m3h_per_bar(Rules(well_spacing_m=1000))
        far = productivity_index_m3h_per_bar(Rules(well_spacing_m=2000))
        self.assertGreater(near, far)

    def test_stub_injection_pump_from_return_pressure(self):
        """The stub boosts from the surface plant's 4 bar, as GEMINI's path."""
        p = stub_doublet(300, 2500)
        to_mw = 300 / 3600 * 1e5 / 0.7 / 1e6
        self.assertAlmostEqual(p["injector_pump_mw"], (p["injection_wellhead_bar"] - 4.0) * to_mw)


class TestSecondAquiferPressure(unittest.TestCase):
    """A second aquifer's pressure is bar(g), like every other path."""

    def test_gauge_like_the_rest(self):
        """The brine column, no atmosphere added."""
        r = Rules(second_aquifer_depth_m=3100.0)
        second = [a for a in r.aquifers() if abs(a.depth_m - 3100.0) < 1][0]
        self.assertAlmostEqual(second.pressure_bar, 1030 * 9.81 * 3100 / 1e5, places=2)


class TestDispatchByDay(unittest.TestCase):
    """Equal shares are filled day by day from that day's smallest cap."""

    def test_injector_out_is_symmetric(self):
        """A doublet with a halved cap that day goes first; the other takes the rest."""
        want = np.array([440.0, 440.0])
        allowed = np.ones((2, 2), dtype=bool)
        caps_a = np.array([[300.0, 300.0], [150.0, 300.0]])
        caps_b = caps_a[::-1]
        qa = dispatch(want, allowed, caps_a, [0, 1], 50.0)
        qb = dispatch(want, allowed, caps_b, [0, 1], 50.0)
        self.assertAlmostEqual(qa[:, 0].sum(), 440.0)
        self.assertAlmostEqual(qb[:, 0].sum(), 440.0)
        np.testing.assert_allclose(qa[:, 0], qb[::-1, 0])
        np.testing.assert_allclose(qa[:, 1], [220.0, 220.0])


class TestStopsPerDoublet(unittest.TestCase):
    """Each doublet keeps its own stop."""

    def test_no_shift_when_one_doublet_has_no_stop(self):
        """Doublet 1 has no days off, doublet 2 forty: doublet 2 stops."""
        need = np.ones(365)
        ranges = stop_ranges(need, 2, 365, lengths=(0, 40))
        self.assertEqual(ranges[0], [])
        self.assertEqual(len(ranges[1]), 1)
        a, b = ranges[1][0]
        self.assertEqual(b - a + 1, 40)


class TestHeatPumpLift(unittest.TestCase):
    """The Carnot COP over at least a 10 K lift."""

    def test_finite_at_no_lift(self):
        """A source as hot as the supply: 18.7, not infinite."""
        cop = float(heat_pump_cop(100.0, 100.71))
        self.assertAlmostEqual(cop, 0.5 * 373.15 / MIN_LIFT_K)
        self.assertTrue(np.isfinite(heat_pump_cop(100.0, 105.0)))

    def test_normal_lift_unchanged(self):
        """Lifting from 65 °C to 100 °C is as before."""
        self.assertAlmostEqual(float(heat_pump_cop(100.0, 65.0)), 0.5 * 373.15 / 35.0)

    def test_hot_source_uses_electricity(self):
        """Brine straight from the well still costs electricity."""
        heat, _, cop, el = heat_pump_on_source(
            np.array([0.5]), np.array([100.71]), np.array([0.3425]), 100.0, np.array([60.7]), 0.5
        )
        self.assertGreater(float(el[0]), 0.0)
        self.assertLessEqual(float(cop[0]), 0.5 * 373.15 / MIN_LIFT_K + 1e-9)


if __name__ == "__main__":
    unittest.main()
