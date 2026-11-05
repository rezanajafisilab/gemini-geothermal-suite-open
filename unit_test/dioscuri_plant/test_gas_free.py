"""Gas-free designs: an electric boiler, the brine's gas burnt in a small boiler or sold."""

import unittest
from dataclasses import replace
from pathlib import Path

from dioscuri_plant import Demand, Plant, Prices, Rules, economics, simulate_year, stub_doublet
from dioscuri_plant.economics import grid_capacity_meur
from dioscuri_plant.firm import reliable
from dioscuri_plant.search import plant_code

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
GAS = Plant(1, heat_pump_mw=2.0, boiler_mw=31.2, chiller_mw=15.0)


class TestGasModes(unittest.TestCase):
    """What each gas mode buys, burns, sells and emits."""

    def test_produced_buys_no_gas(self):
        """Only the brine's gas is burnt; the electric boiler heats the rest, every day met."""
        p = replace(GAS, gas="produced", boiler_mw=1.5, electric_boiler_mw=30.0)
        y = simulate_year(p, DEMAND, stub_doublet, Rules())
        self.assertEqual(y.purchased_gas_gwh, 0.0)
        self.assertGreater(y.produced_gas_burned_gwh, 0.0)
        self.assertGreater(y.heat_split_gwh["electric_boiler"], 0.0)
        self.assertFalse(y.violations)
        # Its electricity is the heat over 0.99.
        self.assertAlmostEqual(
            y.electricity_gwh["electric_boiler"], y.heat_split_gwh["electric_boiler"] / 0.99, 2
        )

    def test_sell_burns_nothing_and_counts_the_buyer_apart(self):
        """Sold, the methane leaves the plant's CO2; the buyer's is said, not added."""
        sell = replace(GAS, gas="sell", boiler_mw=0.0, electric_boiler_mw=31.2)
        burn = replace(GAS, gas="produced", boiler_mw=1.5, electric_boiler_mw=30.0)
        ys = simulate_year(sell, DEMAND, stub_doublet, Rules())
        yb = simulate_year(burn, DEMAND, stub_doublet, Rules())
        self.assertEqual((ys.produced_gas_burned_gwh, ys.produced_gas_flared_gwh), (0.0, 0.0))
        self.assertGreater(ys.produced_gas_sold_gwh, 0.0)
        self.assertLess(ys.co2_t["produced_gas"], yb.co2_t["produced_gas"])  # only its CO2 let out
        self.assertGreater(ys.co2_t["sold_gas_elsewhere"], 0.0)
        parts = ("purchased_gas", "produced_gas", "electricity")
        self.assertAlmostEqual(ys.co2_t["total"], sum(ys.co2_t[k] for k in parts), 0)
        e = economics(sell, ys, Prices())
        lines = {i: m for i, _, m in e.lines}
        self.assertLess(lines["Gas sold"], 0.0)  # a revenue
        self.assertGreater(lines["Gas cleaning and injection"], 0.0)

    def test_codes(self):
        """EB: no gas bought; GS: the gas sold."""
        self.assertEqual(
            plant_code(replace(GAS, gas="produced", electric_boiler_mw=30.0)), "1D-HP-EC-EB"
        )
        self.assertEqual(
            plant_code(replace(GAS, gas="sell", electric_boiler_mw=30.0)), "1D-HP-EC-EB-GS"
        )


class TestGridContract(unittest.TestCase):
    """A backup electric boiler takes the 600-hour contract; a working one the standard."""

    def test_few_hours_cheap_many_hours_standard(self):
        """Short of 600 hours at its peak: about 24 €/kW a year and weekly peaks."""
        idle = replace(GAS, electric_boiler_mw=30.0)  # behind a full gas boiler: never runs
        busy = replace(
            GAS, gas="produced", boiler_mw=1.5, heat_pump_mw=0.0, electric_boiler_mw=30.0
        )
        yi = simulate_year(idle, DEMAND, stub_doublet, Rules())
        yb = simulate_year(busy, DEMAND, stub_doublet, Rules())
        kw = 30.0 / 0.99 * 1000
        self.assertAlmostEqual(grid_capacity_meur(busy, yb), 123.0 * kw / 1e6, 3)
        self.assertEqual(yi.heat_split_gwh["electric_boiler"], 0.0)
        self.assertAlmostEqual(grid_capacity_meur(idle, yi), 23.94 * kw / 1e6, 3)


class TestReliableGasFree(unittest.TestCase):
    """The reliable plan of a gas-free design grows the electric boiler, as equal units."""

    def test_grows_the_electric_boiler(self):
        """The gas boiler stays at the brine's gas; three electric units cover any one out."""
        p = replace(GAS, gas="produced", boiler_mw=1.5, electric_boiler_mw=20.0)
        plan, rounds, last = reliable(p, DEMAND, stub_doublet, Rules())
        self.assertEqual((plan.boiler_mw, plan.electric_boiler_units), (1.5, 3))
        self.assertGreaterEqual(plan.electric_boiler_mw, 20.0)
        self.assertTrue(all(o["heat"]["days_short"] == 0 for o in last))


if __name__ == "__main__":
    unittest.main()
