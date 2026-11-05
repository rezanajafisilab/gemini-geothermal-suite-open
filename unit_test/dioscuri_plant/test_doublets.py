"""Doublets that differ: depths, open parts, injectors, flow caps, treatment trains, dispatch."""

import unittest
from pathlib import Path

import numpy as np

from dioscuri_plant import Demand, Doublet, Plant, Prices, Rules, simulate_year, stub_doublet
from dioscuri_plant.economics import capex_items
from dioscuri_plant.search import plant_code, search
from dioscuri_plant.year import dispatch

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
SIZES = dict(heat_pump_mw=4, boiler_mw=20, absorption_mw=2, chiller_mw=8)


class TestDispatch(unittest.TestCase):
    """How a day's brine is shared among the doublets."""

    def test_equal_shares_with_caps(self):
        """400 m3/h on two doublets capped 300 and 150: 250 and 150 (the small one at its cap)."""
        q = dispatch(
            np.array([400.0]), np.ones((2, 1), bool), np.array([300.0, 150.0]), [0, 1], 50.0
        )
        self.assertEqual(q[:, 0].tolist(), [250.0, 150.0])

    def test_base_load_fills_the_first_and_leaves_the_minimum(self):
        """320 m3/h hottest first: 270 and 50 (the second runs at its minimum)."""
        q = dispatch(
            np.array([320.0]), np.ones((2, 1), bool), np.array([300.0, 300.0]), [0, 1], 50.0, "base"
        )
        self.assertEqual(q[:, 0].tolist(), [270.0, 50.0])

    def test_the_fewest_doublets_run(self):
        """200 m3/h needs one doublet; a stopped doublet is passed over."""
        allowed = np.array([[False], [True]])
        q = dispatch(np.array([200.0]), allowed, np.array([300.0, 300.0]), [0, 1], 50.0)
        self.assertEqual(q[:, 0].tolist(), [0.0, 200.0])


class TestDoubletsThatDiffer(unittest.TestCase):
    """A year with two different doublets: each has its own wells, flows and pumps."""

    def test_identical_doublets_give_the_old_answer(self):
        """Two identical doublets set one by one equal ``Plant(2)``."""
        a = simulate_year(Plant(2, **SIZES), DEMAND, stub_doublet)
        b = simulate_year(
            Plant(2, doublet_specs=(Doublet(), Doublet()), **SIZES), DEMAND, stub_doublet
        )
        self.assertEqual(a.heat_split_gwh, b.heat_split_gwh)
        self.assertEqual(a.electricity_gwh, b.electricity_gwh)

    def test_a_half_open_injector_needs_more_pressure(self):
        """Half the open interval halves the injectivity: higher pressure, more pumping."""
        full = simulate_year(Plant(1, **SIZES), DEMAND, stub_doublet)
        half = simulate_year(
            Plant(1, doublet_specs=(Doublet(injector_open="lower"),), **SIZES),
            DEMAND,
            stub_doublet,
        )
        f, h = full.doublet_summary[0], half.doublet_summary[0]
        self.assertAlmostEqual(h["injectivity_m3h_per_bar"] * 2, f["injectivity_m3h_per_bar"], 1)
        self.assertGreater(h["injection_full_bar"], f["injection_full_bar"])
        self.assertGreater(half.electricity_gwh["pumps"], full.electricity_gwh["pumps"])

    def test_a_lower_half_producer_is_warmer(self):
        """The middle of the lower half is 25 m deeper: 0.75 K warmer rock."""
        y = simulate_year(
            Plant(1, doublet_specs=(Doublet(producer_open="lower"),), **SIZES), DEMAND, stub_doublet
        )
        self.assertAlmostEqual(y.doublet_summary[0]["rock_c"], 87.75, places=2)

    def test_two_injectors_share_the_brine(self):
        """Each injector takes half the flow: less injection pumping than one injector."""
        one = simulate_year(Plant(1, **SIZES), DEMAND, stub_doublet)
        two = simulate_year(
            Plant(1, doublet_specs=(Doublet(injectors=2),), **SIZES), DEMAND, stub_doublet
        )
        self.assertLess(
            two.doublet_summary[0]["injection_gwh"], one.doublet_summary[0]["injection_gwh"]
        )

    def test_base_load_runs_the_doublets_at_different_rates(self):
        """Hottest first: one doublet near its cap, the other slower (and cooler at the head)."""
        y = simulate_year(Plant(2, dispatch="base", **SIZES), DEMAND, stub_doublet)
        a, b = y.doublet_summary
        self.assertGreater(a["flow_mean_m3h"], b["flow_mean_m3h"] + 50)
        self.assertEqual(y.violations, [])

    def test_mixed_depths_keep_the_40_k_cap(self):
        """A 3,000 m and a 2,500 m doublet in one heat plant: the hot brine is not overcooled."""
        y = simulate_year(
            Plant(2, doublet_specs=(Doublet(), Doublet(depth_m=3000.0)), **SIZES),
            DEMAND,
            stub_doublet,
        )
        self.assertLessEqual(y.max_brine_cooling_k, 40.0 + 1e-6)
        self.assertFalse(any("cooled by" in v for v in y.violations))

    def test_a_doublet_over_its_own_cap_is_a_violation(self):
        """A cap below 50 m3/h cannot be met: said, per doublet."""
        y = simulate_year(
            Plant(1, doublet_specs=(Doublet(max_flow_m3h=40.0),), **SIZES), DEMAND, stub_doublet
        )
        self.assertTrue(any("Doublet 1 flow" in v for v in y.violations))

    def test_nonsense_is_refused(self):
        """Three injectors, a wrong opening or a spec count that differs are refused."""
        with self.assertRaises(ValueError):
            Doublet(injectors=3)
        with self.assertRaises(ValueError):
            Doublet(producer_open="middle")
        with self.assertRaises(ValueError):
            Plant(2, doublet_specs=(Doublet(),))


class TestCosts(unittest.TestCase):
    """Wells per doublet and treatment trains."""

    def test_a_shared_train_costs_less_than_one_per_doublet(self):
        """Two doublets: one larger train (six-tenths rule) against two."""
        shared = capex_items(Plant(2, boiler_mw=20), Prices(), 20.0)
        apart = capex_items(
            Plant(2, boiler_mw=20, doublet_specs=(Doublet(), Doublet(train=1))), Prices(), 20.0
        )

        def trains(items):
            return sum(i["meur"] for i in items if i["item"] == "Treatment trains")

        self.assertAlmostEqual(trains(shared), 0.6 * 2**0.6, places=2)
        self.assertAlmostEqual(trains(apart), 1.2, places=2)

    def test_an_extra_injector_is_an_extra_well(self):
        """Three wells for a doublet with two injectors."""
        items = capex_items(Plant(1, doublet_specs=(Doublet(injectors=2),)), Prices(), 10.0)
        self.assertEqual(sum(i["size"] for i in items if i["item"] == "Wells"), 3)


class TestSearch(unittest.TestCase):
    """The search tries layouts, sizes each several ways and tries variants of the best."""

    @classmethod
    def setUpClass(cls):
        """Search once with the plain-physics doublet."""
        cls.result = search(DEMAND, stub_doublet, Rules())

    def test_known_aquifer_only_by_default(self):
        """No assumed deeper aquifer unless asked."""
        depths = {d for c in self.result.candidates for d in c.topology.aquifers()}
        self.assertEqual(depths, {2500.0})

    def test_many_sizings_and_variants(self):
        """Hundreds of sizings; the best three get their variants."""
        self.assertGreater(self.result.sizings, 200)
        stage_two = [c for c in self.result.candidates if c.stage == 2]
        self.assertGreaterEqual(len(stage_two), 10)
        self.assertTrue(all(c.reason.startswith("against ") for c in stage_two if c.reason))

    def test_codes_name_the_variants(self):
        """2I two injectors, ST a train per doublet, BL hottest first, PL/IL/IU open halves."""
        codes = {c.topology.code for c in self.result.candidates}
        for flag in ("-2I", "-BL", "-PL", "-IL", "-IU"):
            self.assertTrue(any(flag in c for c in codes), flag)
        plant = Plant(2, doublet_specs=(Doublet(injectors=2), Doublet(train=1)), boiler_mw=5)
        self.assertEqual(plant_code(plant), "2D-BO-NC-2I1-ST")

    def test_a_brief_can_fix_the_build(self):
        """Two doublets described one by one: only their layouts, no variants."""
        specs = (Doublet(injectors=2), Doublet(train=1))
        result = search(DEMAND, stub_doublet, Rules(), fixed={"specs": specs})
        self.assertTrue(all(c.topology.specs == specs for c in result.candidates))
        self.assertFalse(any(c.stage == 2 for c in result.candidates))


if __name__ == "__main__":
    unittest.main()
