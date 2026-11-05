"""Each doublet's own flow (2 Nov): a cap, a minimum, or one fixed rate."""

import unittest

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant.year import dispatch
from gemini_agent import engine
from gemini_agent.contract import DesignBrief


class TestDispatch(unittest.TestCase):
    """The daily share honours each doublet's own minimum."""

    def test_own_minimum(self):
        """Doublet 2 at least 150 m3/h gets 150 on a day of 400 m3/h, hottest first.

        With the usual 50 m3/h minimum it got 100; 200 m3/h needs doublet 1 alone.
        """
        days, allowed, caps = np.array([200.0, 400.0]), np.ones((2, 2), dtype=bool), [300.0, 300.0]
        q = dispatch(days, allowed, np.array(caps), [0, 1], np.array([50.0, 150.0]), "base")
        self.assertEqual(q[:, 0].tolist(), [200.0, 0.0])
        self.assertEqual(q[:, 1].tolist(), [250.0, 150.0])
        usual = dispatch(days, allowed, np.array(caps), [0, 1], 50.0, "base")
        self.assertEqual(usual[:, 1].tolist(), [300.0, 100.0])


class TestYear(unittest.TestCase):
    """A doublet fixed at one rate runs only at that rate."""

    def test_fixed_rate(self):
        """Fixed at 200 m3/h: every running day at 200, never another flow."""
        rules = engine.rules_for(DesignBrief())
        demand = engine.demand_of(DesignBrief())
        model = engine.doublet_model(rules)
        spec = dp.Doublet(max_flow_m3h=200.0, min_flow_m3h=200.0)
        plant = dp.Plant(1, doublet_specs=(spec,), boiler_mw=30.0, chiller_mw=12.0)
        y = dp.simulate_year(plant, demand, model, rules)
        flows = [f for f in y.doublets[0]["flow_m3h"] if f > 0]
        self.assertTrue(flows)
        self.assertTrue(all(abs(f - 200.0) < 1e-6 for f in flows))
        self.assertEqual(y.violations, [])

    def test_minimum_above_cap_is_refused(self):
        """A minimum above the doublet's own cap makes no sense."""
        with self.assertRaises(ValueError):
            dp.Doublet(max_flow_m3h=150.0, min_flow_m3h=200.0)


if __name__ == "__main__":
    unittest.main()
