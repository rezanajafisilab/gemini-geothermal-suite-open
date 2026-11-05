"""Several aquifers, each with its own rock, pressure and gas-liquid ratio (4 Nov).

Each doublet sees the aquifer it is drilled into (``Rules.aquifer_at``): its flow, pressures
and pumps from that aquifer's thickness, permeability and pressure, and its brine's gas from
that aquifer's gas-liquid ratio. One aquifer gives what it gave before.
"""

import unittest
from dataclasses import replace

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant.economics import capex_items
from dioscuri_plant.year import gas_flow
from gemini_agent import engine
from gemini_agent.contract import DesignBrief

KNOWN = 2500.0
OTHER = 3100.0


def _rules(glr_other: float = 0.8, **other) -> dp.Rules:
    """Return the challenge's rules with a second aquifer at 3,100 m (its own gas)."""
    base = engine.rules_for(DesignBrief())
    a = dp.Aquifer(
        OTHER,
        other.get("thickness_m", 80.0),
        other.get("permeability_md", 400.0),
        other.get("pressure_bar", base.hydrostatic_bar(OTHER)),
        glr_other,
    )
    return replace(base, other_aquifers=(a,))


def _plant(gas: str = "buy") -> dp.Plant:
    """Return two doublets, one in each aquifer, with a boiler and chillers to meet the year."""
    specs = (dp.Doublet(depth_m=KNOWN), dp.Doublet(depth_m=OTHER, train=1))
    return dp.Plant(
        2,
        depth_m=KNOWN,
        doublet_specs=specs,
        boiler_mw=30.0,
        chiller_mw=12.0,
        electric_boiler_mw=30.0 if gas != "buy" else 0.0,
        gas=gas,
    )


def _year(rules: dp.Rules, plant: dp.Plant):
    demand = engine.demand_of(DesignBrief())
    year = dp.simulate_year(plant, demand, engine.doublet_model(rules), rules)
    return year, dp.economics(plant, year, dp.Prices(), rules=rules)


class TestEachDoubletItsAquifer(unittest.TestCase):
    """Which aquifer a depth is in, and the rules a doublet there sees."""

    def test_the_rules_a_doublet_sees(self):
        """Its aquifer's rock, pressure and gas; the known one and an assumed depth unchanged."""
        rules = _rules(1.2)
        self.assertEqual([a.depth_m for a in rules.aquifers()], [KNOWN, OTHER])
        there = rules.aquifer_at(OTHER)
        self.assertEqual(
            (there.reservoir_thickness_m, there.permeability_md, there.gas_liquid_ratio),
            (80.0, 400.0, 1.2),
        )
        self.assertEqual(there.other_aquifers, ())  # the doublet sees only its own
        self.assertIs(rules.aquifer_at(KNOWN), rules)
        self.assertIs(rules.aquifer_at(3500.0), rules)  # assumed: the known one's rock
        self.assertEqual((rules.aquifer_index(OTHER + 30), rules.aquifer_index(3500.0)), (1, None))
        # A well open over the lower half of the other aquifer is still in it.
        self.assertEqual(rules.aquifer_index(OTHER + 20.0), 1)

    def test_one_ratio_keeps_the_total_flow(self):
        """With one gas-liquid ratio the gas is the total flow times it, as before."""
        rules = _rules(0.8)
        flows = np.array([[100.0, 0.0], [50.0, 300.0]])
        specs = (dp.Doublet(depth_m=KNOWN), dp.Doublet(depth_m=OTHER))
        q, ratio = gas_flow(flows, specs, rules)
        self.assertEqual((q.tolist(), ratio), ([150.0, 300.0], 0.8))
        q, ratio = gas_flow(flows, specs, _rules(2.0))
        self.assertEqual((q.tolist(), ratio), ([180.0, 600.0], 1.0))  # 100 x 0.8 + 50 x 2


class TestGasByAquifer(unittest.TestCase):
    """Two aquifers with different gas-liquid ratios: each doublet's gas is its aquifer's."""

    @classmethod
    def setUpClass(cls):
        """Run the same plant with the second aquifer's brine at 0.8 and at 2.0 Nm3/m3."""
        cls.low = _year(_rules(0.8), _plant())
        cls.high = _year(_rules(2.0), _plant())

    def test_each_doublet_brings_its_aquifers_gas(self):
        """Doublet 2's gas grows 2.5 times; doublet 1's (the known aquifer) does not change."""
        a, b = (y.doublet_summary for y, _ in (self.low, self.high))
        self.assertEqual([r["aquifer"] for r in b], [1, 2])
        self.assertEqual([r["gas_liquid_ratio"] for r in b], [0.8, 2.0])
        self.assertEqual(a[0]["gas_nm3"], b[0]["gas_nm3"])
        self.assertAlmostEqual(b[1]["gas_nm3"] / a[1]["gas_nm3"], 2.5, places=3)
        for r in b:  # each doublet's gas is its brine times its aquifer's ratio
            self.assertAlmostEqual(r["gas_nm3"], r["brine_m3"] * r["gas_liquid_ratio"], -1)

    def test_more_gas_more_burnt_and_more_co2(self):
        """The richer aquifer's gas is burnt in the boiler (less gas bought), and its CO2 shows."""
        (y0, e0), (y1, e1) = self.low, self.high
        total0 = y0.produced_gas_burned_gwh + y0.produced_gas_flared_gwh
        total1 = y1.produced_gas_burned_gwh + y1.produced_gas_flared_gwh
        self.assertGreater(total1, total0 * 1.4)
        self.assertLess(y1.purchased_gas_gwh, y0.purchased_gas_gwh)
        self.assertGreater(y1.co2_t["produced_gas"], y0.co2_t["produced_gas"])
        self.assertNotAlmostEqual(e0.lcoe_eur_per_mwh, e1.lcoe_eur_per_mwh, places=2)

    def test_sold_gas_and_its_cleaning_follow_the_aquifer(self):
        """Sold to the grid, the richer aquifer sells more and pays more to clean it."""
        (y0, e0), (y1, e1) = (_year(_rules(r), _plant("sell")) for r in (0.8, 2.0))
        self.assertGreater(y1.produced_gas_sold_gwh, y0.produced_gas_sold_gwh * 1.4)

        def line(e, item):
            return sum(v for name, _, v in e.lines if name == item)

        self.assertGreater(line(e1, "Gas cleaning and injection"), line(e0, "Gas cleaning"))
        self.assertLess(line(e1, "Gas sold"), line(e0, "Gas sold"))  # more revenue (negative)

    def test_the_bubble_point_follows_the_gas(self):
        """More gas dissolved: a higher bubble point, so the ESP must sit deeper."""
        a, b = (y.doublet_summary[1] for y, _ in (self.low, self.high))
        self.assertGreater(b["bubble_point_bar"], a["bubble_point_bar"])
        self.assertGreater(b["esp_setting_m"], a["esp_setting_m"])


class TestRockByAquifer(unittest.TestCase):
    """The thickness and permeability of each doublet's own aquifer set its wells."""

    def test_flow_and_pumps_follow_the_rock(self):
        """A thin, tight second aquifer: a lower productivity, more pumping for the same flow."""
        plant = dp.Plant(1, depth_m=OTHER, boiler_mw=30.0, chiller_mw=12.0)
        tight, _ = _year(_rules(thickness_m=30.0, permeability_md=50.0), plant)
        good, _ = _year(_rules(thickness_m=150.0, permeability_md=800.0), plant)
        t, g = tight.doublet_summary[0], good.doublet_summary[0]
        self.assertEqual((t["thickness_m"], g["thickness_m"]), (30.0, 150.0))
        self.assertLess(t["pi_m3h_per_bar"], g["pi_m3h_per_bar"])
        self.assertGreater(t["esp_head_full_bar"], g["esp_head_full_bar"])

    def test_wells_priced_at_their_own_aquifer(self):
        """A producer open over the upper half is priced half its own aquifer's thickness up."""
        rules = _rules(thickness_m=40.0)
        plant = dp.Plant(
            1,
            depth_m=OTHER,
            doublet_specs=(dp.Doublet(depth_m=OTHER, producer_open="upper"),),
        )
        items = capex_items(plant, dp.Prices(), 10.0, rules)
        notes = " ".join(str(i.get("note", "")) for i in items if i["item"] == "Wells")
        self.assertIn(f"priced at {OTHER - 20:,.0f} m TVD", notes)


class TestOneAquiferAsBefore(unittest.TestCase):
    """An aquifer described with the values an assumed depth had changes nothing."""

    def test_the_same_year_and_cost(self):
        """3,000 m as an assumed depth and as an aquifer with the known one's rock: identical."""
        from dioscuri_plant.doublet import reservoir_pressure_bar

        base = engine.rules_for(DesignBrief())
        same = dp.Aquifer(
            3000.0,
            base.reservoir_thickness_m,
            base.permeability_md,
            reservoir_pressure_bar(3000.0, base),
            base.gas_liquid_ratio,
        )
        plant = dp.Plant(2, depth_m=3000.0, heat_pump_mw=3.0, boiler_mw=25.0, chiller_mw=12.0)
        y0, e0 = _year(base, plant)
        y1, e1 = _year(replace(base, other_aquifers=(same,)), plant)
        self.assertEqual(e0.lcoe_eur_per_mwh, e1.lcoe_eur_per_mwh)
        self.assertEqual(y0.heat_split_gwh, y1.heat_split_gwh)
        self.assertEqual(y0.co2_t, y1.co2_t)
        self.assertEqual(y1.doublet_summary[0]["aquifer"], 2)


if __name__ == "__main__":
    unittest.main()
