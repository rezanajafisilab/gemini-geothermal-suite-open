"""The brine's own CO2 dissolved back into the injected brine (2 Nov)."""

import unittest
from dataclasses import replace

import dioscuri_plant as dp
from dioscuri_plant.economics import SOURCES
from gemini_agent import engine
from gemini_agent.contract import DesignBrief


class TestReinjection(unittest.TestCase):
    """Only the brine's own CO2 goes back; its methane's CO2 is let out either way."""

    def test_native_co2_is_reinjected_and_costed(self):
        """The CO2 let out falls by the brine's own CO2, which is costed per tonne."""
        rules = engine.rules_for(DesignBrief())
        demand = engine.demand_of(DesignBrief())
        model = engine.doublet_model(rules)
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)
        off = dp.simulate_year(plant, demand, model, rules)
        on = dp.simulate_year(plant, demand, model, replace(rules, co2_reinjection=1.0))
        back = on.co2_t["reinjected"]
        self.assertGreater(back, 0)
        self.assertAlmostEqual(off.co2_t["produced_gas"] - on.co2_t["produced_gas"], back, 0)
        # 20 % of the gas is CO2: the methane's CO2 (80 %) is still let out.
        self.assertAlmostEqual(back / off.co2_t["produced_gas"], 0.2, 2)
        econ = dp.economics(plant, on, dp.Prices(), rules=rules)
        lines = [ln for ln in econ.lines_heat + econ.lines_cold if ln[0] == "CO2 reinjection"]
        self.assertTrue(lines)
        self.assertIn("Gunnarsson", SOURCES["co2_reinjection_eur_per_t"])


if __name__ == "__main__":
    unittest.main()


class TestFlaring(unittest.TestCase):
    """All the brine's gas flared (a switch, never chosen by the search), and the note."""

    def test_flaring_all_buys_more_gas_and_is_flagged(self):
        """The boiler buys what the brine's gas gave; any flaring carries the consent note."""
        rules = engine.rules_for(DesignBrief())
        demand = engine.demand_of(DesignBrief())
        model = engine.doublet_model(rules)
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)
        base = dp.simulate_year(plant, demand, model, rules)
        flare = dp.simulate_year(plant, demand, model, replace(rules, flare_brine_gas=1.0))
        self.assertEqual(flare.produced_gas_burned_gwh, 0.0)
        self.assertGreater(flare.purchased_gas_gwh, base.purchased_gas_gwh)
        self.assertGreater(flare.co2_t["total"], base.co2_t["total"])
        self.assertTrue(any("Mijnbouwbesluit" in w for w in flare.warnings))


class TestGridAndSlip(unittest.TestCase):
    """The grid's CO2 as an input; the flare's methane as CO2-equivalent, apart."""

    def test_grid_factor_and_methane_slip(self):
        """Half the grid factor halves the electricity's CO2; flaring lets 2 % methane out."""
        rules = engine.rules_for(DesignBrief())
        demand = engine.demand_of(DesignBrief())
        model = engine.doublet_model(rules)
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)
        base = dp.simulate_year(plant, demand, model, rules)
        half = dp.simulate_year(plant, demand, model, replace(rules, grid_t_co2_per_mwh=0.10))
        self.assertAlmostEqual(half.co2_t["electricity"], base.co2_t["electricity"] / 2, 0)
        flare = dp.simulate_year(plant, demand, model, replace(rules, flare_brine_gas=1.0))
        self.assertGreater(flare.co2_t["methane_slip_co2e"], base.co2_t["methane_slip_co2e"])
        # Not in the CO2 total.
        parts = ("purchased_gas", "produced_gas", "electricity")
        self.assertAlmostEqual(flare.co2_t["total"], sum(flare.co2_t[k] for k in parts), 0)
