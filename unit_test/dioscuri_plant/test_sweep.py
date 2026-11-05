"""The design-space sweep (2 Nov): Latin hypercube designs, failures kept, the best refined."""

import os
import unittest
from unittest import mock

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant import explore
from dioscuri_plant.search import Topology, improve
from gemini_agent import engine
from gemini_agent.contract import DesignBrief


def setting():
    """Return the challenge's demand, doublet model, rules, prices and gas reference."""
    brief = DesignBrief()
    rules = engine.rules_for(brief)
    demand = engine.demand_of(brief)
    model = engine.doublet_model(rules)
    prices = engine.prices_for(None, brief)
    rounds, year = improve(Topology(0), demand, model, rules, dp.Components())
    ref = (year, dp.economics(rounds[-1].plant, year, prices, rules=rules))
    return demand, model, rules, prices, ref


class TestDraw(unittest.TestCase):
    """How the designs are drawn."""

    def test_latin_hypercube_strata(self):
        """Every dimension has exactly one point in each of its n strata."""
        u = explore.latin_hypercube(50, 4, np.random.default_rng(1))
        for j in range(4):
            self.assertEqual(sorted((u[:, j] * 50).astype(int)), list(range(50)))

    def test_excluded_units_and_ranges(self):
        """A unit ruled out is never drawn; depths and flow caps fall on their steps."""
        demand, _, rules, _, _ = setting()
        plants, ranges = explore.draw(
            400, demand, rules, excluded=("heat_pump",), depths=(2500.0, 3500.0)
        )
        self.assertTrue(all(p.heat_pump_mw == 0 for p in plants))
        self.assertTrue(all(2500 <= p.depth_m <= 3500 and p.depth_m % 100 == 0 for p in plants))
        flows = {d.max_flow_m3h for p in plants for d in p.doublet_specs}
        self.assertTrue(all(f % 10 == 0 and f <= rules.flow_max_m3h for f in flows))
        self.assertEqual({p.n_doublets for p in plants}, {1, 2, 3})
        self.assertEqual(ranges["depth_m"], (2500.0, 3500.0))


class TestGrid(unittest.TestCase):
    """Every grid value is drawn as often as the others, the two ends too (4 Nov)."""

    def test_on_grid_bins(self):
        """2,500-3,500 m in 100 m steps: 11 values, each one eleventh of the unit draws.

        By hand: 1,100 draws evenly over [0, 1) put 100 in each of the 11 bins. Rounding to the
        nearest step gave 2,500 m and 3,500 m 50 each and the nine between 111 each.
        """
        from collections import Counter

        u = (np.arange(1100) + 0.5) / 1100
        got = Counter(explore.on_grid(x, 2500.0, 3500.0, 100.0) for x in u)
        self.assertEqual(sorted(got), [2500.0 + 100.0 * k for k in range(11)])
        self.assertEqual(set(got.values()), {100})
        self.assertEqual(explore.on_grid(0.0, 100.0, 300.0, 10.0), 100.0)
        self.assertEqual(explore.on_grid(0.999999, 100.0, 300.0, 10.0), 300.0)
        self.assertEqual(explore.on_grid(0.5, 2500.0, 2500.0, 100.0), 2500.0)

    def test_draw_counts(self):
        """In the Latin hypercube each depth and each flow cap gets exactly its share."""
        from collections import Counter

        demand, _, rules, _, _ = setting()
        lo, hi = max(rules.flow_min_m3h + 50.0, 100.0), rules.flow_max_m3h
        flows = int(round((hi - lo) / 10.0)) + 1
        n = 11 * flows * 2
        plants, _ = explore.draw(n, demand, rules, depths=(2500.0, 3500.0))
        depth = Counter(p.depth_m for p in plants)
        flow = Counter(p.doublet_specs[0].max_flow_m3h for p in plants)
        self.assertEqual(set(depth.values()), {n // 11})
        self.assertEqual(set(flow.values()), {n // flows})
        self.assertEqual(min(flow), lo)
        self.assertEqual(max(flow), hi)

    def test_levels_drawn_alike(self):
        """Three aquifers described: each a third of the time (the nearest gave 1/4, 1/2, 1/4)."""
        from collections import Counter

        demand, _, rules, _, _ = setting()
        plants, _ = explore.draw(
            300, demand, rules, depths=(2500.0, 3500.0), levels=(2500.0, 3000.0, 3500.0)
        )
        self.assertEqual(
            Counter(p.depth_m for p in plants), {2500.0: 100, 3000.0: 100, 3500.0: 100}
        )


def _point(lcoe: float, co2: float) -> explore.Point:
    return explore.Point(1, 2500.0, 300.0, 0, 0, 0, 0, 0, "buy", lcoe, lcoe, co2, 0.5, 10.0, "")


class TestFront(unittest.TestCase):
    """The front keeps no dominated point; the refined points span it end to end (4 Nov)."""

    def test_tie_on_cost(self):
        """Two at 50 €/MWh: the one with less CO2 dominates the other, which is not kept."""
        pts = [_point(50.0, 100.0), _point(50.0, 90.0), _point(60.0, 80.0)]
        self.assertEqual(explore.front_of(pts), [1, 2])

    def test_spread_keeps_both_ends(self):
        """By position on the front: the cheapest and the lowest-CO2 always, evenly between.

        The shipped front of 7 (cheapest first) with 6 to refine: positions 0, 1.2, 2.4, 3.6,
        4.8, 6 round to 0, 1, 2, 4, 5, 6. Sorting by point number before the cut dropped 4940,
        the lowest-CO2 point.
        """
        front = [1139, 4677, 3192, 1764, 328, 1596, 4940]
        self.assertEqual(explore.spread(front, 6), [1139, 4677, 3192, 328, 1596, 4940])
        self.assertEqual(explore.spread([7, 0, 1, 2, 3, 4, 5, 6], 6), [7, 0, 2, 3, 5, 6])
        self.assertEqual(explore.spread([3, 1], 6), [3, 1])
        self.assertEqual(explore.spread(front, 2), [1139, 4940])
        self.assertEqual(explore.spread(front, 0), [])


class TestExplore(unittest.TestCase):
    """Every design is kept; the front and the refined designs."""

    @classmethod
    def setUpClass(cls):
        """Sweep once, small, in this process."""
        demand, model, rules, prices, ref = setting()
        cls.x = explore.explore(
            demand, model, rules, dp.Components(), prices, ref, n=300, workers=1, refine_top=3
        )

    def test_failures_are_kept(self):
        """Feasible and failed designs are both kept, each failure with its cap."""
        self.assertEqual(len(self.x.points), 300)
        self.assertGreater(self.x.feasible, 0)
        failed = self.x.failures()
        self.assertGreater(sum(failed.values()), 0)
        self.assertTrue(set(failed) <= set(explore.BROKEN_WORDS))
        view = self.x.as_dict()
        self.assertEqual(len(view["rows"][0]), len(view["columns"]))

    def test_front(self):
        """Along the front, cost rises as CO2 falls; no feasible design beats a front point."""
        pts = self.x.points
        front = [pts[i] for i in self.x.front]
        self.assertTrue(
            all(a.lcoe <= b.lcoe and a.co2_t > b.co2_t for a, b in zip(front, front[1:]))
        )
        for f in front:
            self.assertFalse(
                any(p.ok and p.lcoe < f.lcoe - 1e-9 and p.co2_t < f.co2_t - 1e-9 for p in pts)
            )

    def test_refined_meet_every_cap(self):
        """A refined design meets every cap and is a stage-3 candidate from the sweep."""
        self.assertTrue(self.x.refined)
        for c in self.x.refined:
            self.assertEqual(c.year.violations, [])
            self.assertEqual((c.stage, c.effect), (3, "from the design-space sweep"))


class TestInTheSearch(unittest.TestCase):
    """The search runs the sweep when ``DIOSCURI_SWEEP`` asks for designs."""

    def test_search_keeps_the_sweep(self):
        """The outcome carries the sweep; its refined designs are candidates; a note says so."""
        with mock.patch.dict(os.environ, {"DIOSCURI_SWEEP": "300"}):
            out = engine.search(DesignBrief())
        self.assertEqual(len(out.sweep["rows"]), 300)
        self.assertTrue(any("Latin hypercube" in n for n in out.notes))
        swept = [e for e in out.candidates if e.alternative.effect == "from the design-space sweep"]
        self.assertTrue(swept)


if __name__ == "__main__":
    unittest.main()
