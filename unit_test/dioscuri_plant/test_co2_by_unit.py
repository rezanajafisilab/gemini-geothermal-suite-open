"""The year's CO2 by the unit that lets it out: the parts add up to the total (5 Nov)."""

import unittest
from dataclasses import replace

import dioscuri_plant as dp
from dioscuri_plant.year import tenths
from gemini_agent import engine
from gemini_agent.contract import DesignBrief

UNITS = (
    "boiler",
    "electric_boiler",
    "hp",
    "pumps",
    "flare",
    "brine_co2",
    "chillers",
    "towers",
    "network",
)
ELECTRIC = ("electric_boiler", "hp", "pumps", "chillers", "towers", "network")


def _setup():
    rules = engine.rules_for(DesignBrief())
    return rules, engine.demand_of(DesignBrief()), engine.doublet_model(rules)


class TestTenths(unittest.TestCase):
    """Parts rounded to 0.1 that add up to the rounded total."""

    def test_largest_remainder(self):
        """0.36 + 0.36 + 0.38 = 1.1: rounded each would give 1.2; the split gives 1.1."""
        out = tenths({"a": 0.36, "b": 0.36, "c": 0.38}, 1.1)
        self.assertEqual(list(out), ["a", "b", "c"])
        self.assertAlmostEqual(sum(out.values()), 1.1, places=9)
        self.assertEqual(out["c"], 0.4)

    def test_zeros_and_a_total_below_the_parts(self):
        """All zero stays zero; a part's float noise never makes the sum pass the total."""
        self.assertEqual(tenths({"a": 0.0, "b": 0.0}, 0.0), {"a": 0.0, "b": 0.0})
        out = tenths({"a": 5.04999999, "b": 0.05000001}, 5.1)
        self.assertAlmostEqual(sum(out.values()), 5.1, places=9)
        self.assertTrue(all(v >= 0 for v in out.values()))


class TestCo2ByUnit(unittest.TestCase):
    """Every design: the same factors as the total, split by unit, to the tenth."""

    @classmethod
    def setUpClass(cls):
        """Run a one-doublet design with a heat pump, a boiler and both chillers."""
        cls.rules, cls.demand, model = _setup()
        cls.model = staticmethod(model)  # a function: not a method of the test
        cls.plant = dp.Plant(
            1, heat_pump_mw=6.0, boiler_mw=24.0, absorption_mw=2.0, chiller_mw=10.0
        )
        cls.year = dp.simulate_year(cls.plant, cls.demand, cls.model, cls.rules)

    def assertSplit(self, y):
        """Check the fixed keys, none negative, adding up to the total; gas, electricity apart."""
        split, co2 = y.co2_by_unit_t, y.co2_t
        self.assertEqual(tuple(split), UNITS)
        self.assertTrue(all(v >= 0 for v in split.values()), split)
        self.assertAlmostEqual(sum(split.values()), co2["total"], places=6)
        # Each origin within the rounding of its parts (0.05 t each).
        gas = split["boiler"] + split["flare"] + split["brine_co2"]
        self.assertAlmostEqual(gas, co2["purchased_gas"] + co2["produced_gas"], delta=0.2)
        el = sum(split[k] for k in ELECTRIC)
        self.assertAlmostEqual(el, co2["electricity"], delta=0.35)
        self.assertGreaterEqual(split["boiler"], co2["purchased_gas"] - 0.1)

    def test_a_design_with_a_boiler_and_chillers(self):
        """Each electricity user carries the grid's CO2 on its own electricity."""
        y = self.year
        self.assertSplit(y)
        grid = dp.Components().grid_t_co2_per_mwh
        for key in ("hp", "pumps", "chillers", "towers"):
            self.assertAlmostEqual(
                y.co2_by_unit_t[key], y.electricity_gwh[key] * 1000 * grid, delta=0.3, msg=key
            )
        self.assertGreater(y.co2_by_unit_t["boiler"], 0)
        self.assertGreater(y.co2_by_unit_t["brine_co2"], 0)
        self.assertEqual(y.co2_by_unit_t["electric_boiler"], 0.0)

    def test_the_gas_reference(self):
        """No doublet: all of it from the boiler and the chillers' electricity."""
        y = dp.simulate_year(dp.Plant(0, boiler_mw=31.0, chiller_mw=10.5), self.demand, self.model)
        self.assertSplit(y)
        for key in ("flare", "brine_co2", "hp", "pumps"):
            self.assertEqual(y.co2_by_unit_t[key], 0.0, key)

    def test_flared_sold_and_reinjected_gas(self):
        """Flared: the methane's CO2 at the flare. Sold: the buyer's. Reinjected: none let out."""
        flare = dp.simulate_year(
            self.plant, self.demand, self.model, replace(self.rules, flare_brine_gas=1.0)
        )
        self.assertSplit(flare)
        self.assertGreater(flare.co2_by_unit_t["flare"], 0)
        self.assertAlmostEqual(
            flare.co2_by_unit_t["boiler"], flare.co2_t["purchased_gas"], delta=0.1
        )
        sold = dp.simulate_year(
            replace(self.plant, gas="sell"), self.demand, self.model, self.rules
        )
        self.assertSplit(sold)
        self.assertEqual(sold.co2_by_unit_t["flare"], 0.0)
        self.assertAlmostEqual(sold.co2_by_unit_t["brine_co2"], sold.co2_t["produced_gas"], 1)
        back = dp.simulate_year(
            self.plant, self.demand, self.model, replace(self.rules, co2_reinjection=1.0)
        )
        self.assertSplit(back)
        self.assertEqual(back.co2_by_unit_t["brine_co2"], 0.0)

    def test_solar_the_grid_by_month_a_store_and_a_network(self):
        """Own solar and the monthly grid factor shift the electricity's CO2; parts still add up."""
        for change in (
            {"solar_mwp": 5.0},
            {"grid_by_month": 1.0},
            {"storage_mwh": 1000.0},
            {"network_length_km": 8.0},
        ):
            y = dp.simulate_year(self.plant, self.demand, self.model, replace(self.rules, **change))
            with self.subTest(change=change):
                self.assertSplit(y)
        net = dp.simulate_year(
            self.plant, self.demand, self.model, replace(self.rules, network_length_km=8.0)
        )
        self.assertGreater(net.co2_by_unit_t["network"], 0)

    def test_a_gas_free_design(self):
        """An electric boiler in place of the gas one carries its electricity's CO2."""
        plant = dp.Plant(1, heat_pump_mw=6.0, electric_boiler_mw=24.0, chiller_mw=12.0)
        y = dp.simulate_year(plant, self.demand, self.model, self.rules)
        self.assertSplit(y)
        self.assertGreater(y.co2_by_unit_t["electric_boiler"], 0)

    def test_the_agent_passes_it_on(self):
        """The agent's entry keeps the split, and the tabs' design view sends it."""
        from gemini_agent import workbench
        from gemini_agent.agent import Session

        entry = engine.reference(DesignBrief(), {})
        y = entry.year
        self.assertEqual(tuple(y.co2_by_unit_t), UNITS)
        self.assertAlmostEqual(sum(y.co2_by_unit_t.values()), y.co2_t["total"], places=6)
        view = workbench.design_view(Session(), entry)
        self.assertEqual(view["year"]["co2_by_unit_t"], y.co2_by_unit_t)


if __name__ == "__main__":
    unittest.main()
