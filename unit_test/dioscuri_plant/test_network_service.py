"""The district network's losses and the units' planned service, in the year model."""

import unittest
from dataclasses import replace
from pathlib import Path

from dioscuri_plant import Demand, Plant, Prices, Rules, economics, simulate_year, stub_doublet
from dioscuri_plant.network import network, pipe_dn, u_value
from dioscuri_plant.service import windows

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
PLANT = Plant(1, heat_pump_mw=2.0, boiler_mw=31.2, chiller_mw=15.0, boiler_units=3, chiller_units=3)


class TestNetwork(unittest.TestCase):
    """A trunk to the district: sized for the peak, losing heat, supplying hotter."""

    def test_off_by_default(self):
        """No length, no network: delivered at the plant's gate."""
        heat, cool = DEMAND.arrays()
        self.assertIsNone(network(heat, cool, Rules()))
        self.assertIsNone(simulate_year(PLANT, DEMAND, stub_doublet, Rules()).network)

    def test_pipe_and_losses(self):
        """30 MW at 40 K needs about DN350; 5 km lose a few percent; summer supply hotter."""
        self.assertEqual(pipe_dn(30.0, 40.0), 350)
        self.assertAlmostEqual(u_value(350), 0.48)
        heat, cool = DEMAND.arrays()
        net = network(heat, cool, replace(Rules(), network_length_km=5.0))
        s = net["summary"]
        self.assertTrue(0.01 < s["heat_loss_share"] < 0.05)
        self.assertGreater(s["supply_c_max"], s["supply_c_peak_day"])
        self.assertGreater(s["supply_c_peak_day"], 100.0)
        self.assertTrue((net["heat_load"] > heat).all())

    def test_costs_more_per_mwh_delivered(self):
        """The losses are made by the plant and paid per MWh the buildings get."""
        rules = replace(Rules(), network_length_km=5.0)
        base = simulate_year(PLANT, DEMAND, stub_doublet, Rules())
        far = simulate_year(PLANT, DEMAND, stub_doublet, rules)
        self.assertFalse(far.violations)
        e0 = economics(PLANT, base, Prices(), rules=Rules())
        e1 = economics(PLANT, far, Prices(), rules=rules)
        self.assertGreater(e1.lcoe_eur_per_mwh, e0.lcoe_eur_per_mwh)
        self.assertGreater(far.electricity_gwh["network"], 0.0)


class TestService(unittest.TestCase):
    """Each unit out once a year, in its quietest weeks, no two heating units together."""

    def test_windows(self):
        """Heating units in summer, cooling units in winter, a boiler bank one unit at a time."""
        heat, cool = DEMAND.arrays()
        w = windows(heat, cool, boiler_units=3, chiller_units=3)
        names = [u for u, _, _ in w]
        self.assertEqual(names.count("boiler unit"), 3)
        self.assertEqual(names.count("chiller unit"), 3)
        hp = next((a, b) for u, a, b in w if u == "heat pump")
        self.assertTrue(150 <= hp[0] <= 250)  # summer
        heating = sorted(
            (a, b) for u, a, b in w if u in ("heat pump", "boiler unit", "heat exchanger")
        )
        self.assertTrue(all(x[1] < y[0] for x, y in zip(heating, heating[1:])))

    def test_no_heating_service_while_a_doublet_stands(self):
        """A doublet's stop counts as taken: no heating unit is serviced inside it (E14)."""
        heat, cool = DEMAND.arrays()
        stop = (189, 223)  # the quiet summer weeks the heating units would take otherwise
        w = windows(heat, cool, boiler_units=1, stops=[stop])
        heating = [(a, b) for u, a, b in w if u in ("heat pump", "boiler", "heat exchanger")]
        self.assertEqual(len(heating), 3)
        self.assertTrue(all(b < stop[0] or a > stop[1] for a, b in heating))
        free = windows(heat, cool, boiler_units=1)
        self.assertTrue(
            any(not (b < stop[0] or a > stop[1]) for u, a, b in free if u != "chillers")
        )

    def test_the_year_places_service_around_the_stops(self):
        """In the year, the stops come first: the same stops, the service around them."""
        one = Plant(1, heat_pump_mw=2.0, boiler_mw=31.2, absorption_mw=3.0, chiller_mw=15.0)
        on = simulate_year(one, DEMAND, stub_doublet, replace(Rules(), planned_service=1.0))
        off = simulate_year(one, DEMAND, stub_doublet, Rules())
        self.assertEqual(on.stop_ranges, off.stop_ranges)
        stops = [r for rows in on.stop_ranges for r in rows]
        heating = [
            (a, b) for u, a, b in on.service if u in ("heat pump", "boiler", "heat exchanger")
        ]
        self.assertTrue(heating)
        for a, b in heating:
            self.assertTrue(all(b < x or a > y for x, y in stops), (a, b, stops))
        self.assertFalse(on.violations)

    def test_built_into_the_year(self):
        """Switched on, the year carries the windows and still meets every day."""
        y = simulate_year(PLANT, DEMAND, stub_doublet, replace(Rules(), planned_service=1.0))
        self.assertTrue(y.service)
        self.assertFalse(y.violations)


if __name__ == "__main__":
    unittest.main()
