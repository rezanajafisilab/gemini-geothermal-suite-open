"""Free cooling, own solar, a hot-water store and the bought gas's upstream CO2 (2 Nov)."""

import unittest
from dataclasses import replace

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant import weather
from dioscuri_plant.economics import SOURCES
from gemini_agent import engine
from gemini_agent.contract import DesignBrief


def _setup():
    rules = engine.rules_for(DesignBrief())
    return rules, engine.demand_of(DesignBrief()), engine.doublet_model(rules)


class TestWeather(unittest.TestCase):
    """The typical KNMI year: its radiation adds up, the wet bulb is below the dry bulb."""

    def test_typical_year(self):
        """364.8 kJ/cm² a year (about 1,013 kWh/m²); days from 8 to 16.5 hours."""
        wx = weather.typical_year()
        self.assertAlmostEqual(wx["global_kwh_m2"].sum(), 364.8 * 10 / 3.6, 1)
        self.assertTrue(np.all(wx["wet_bulb_c"] <= wx["dry_bulb_c"]))
        self.assertLess(wx["daylight_h"].min(), 8.0)
        self.assertGreater(wx["daylight_h"].max(), 16.0)


class TestFreeCooling(unittest.TestCase):
    """The towers take the cold the wet bulb allows, before the chillers."""

    def test_free_cooling_takes_cold_off_the_chillers(self):
        """Cold still met; the chillers' electricity falls; summer days need the chillers."""
        rules, demand, model = _setup()
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)
        off = dp.simulate_year(plant, demand, model, rules)
        on = dp.simulate_year(plant, demand, model, replace(rules, free_cooling=1.0))
        self.assertEqual(off.cool_split_gwh["free"], 0.0)
        self.assertGreater(on.cool_split_gwh["free"], 0.0)
        self.assertAlmostEqual(on.cool_delivered_gwh, off.cool_delivered_gwh, 2)
        self.assertLess(on.electricity_gwh["chillers"], off.electricity_gwh["chillers"])
        self.assertFalse(on.violations)
        free = np.asarray(on.daily_mw["cool"]["free"])
        demand_cool = np.asarray(on.daily_mw["cool"]["demand"])
        july = slice(181, 212)  # the warmest weeks: the wet bulb is too high for all of it
        self.assertLess(free[july].sum(), demand_cool[july].sum())
        econ = dp.economics(plant, on, dp.Prices(), rules=rules)
        self.assertTrue(any(i["item"] == "Free-cooling exchanger" for i in econ.capex_items))

    def test_no_towers_no_free_cooling(self):
        """A design without chillers or absorption has no towers to cool with."""
        rules, demand, model = _setup()
        plant = dp.Plant(1, boiler_mw=30.0)
        on = dp.simulate_year(plant, demand, model, replace(rules, free_cooling=1.0))
        self.assertEqual(on.cool_split_gwh["free"], 0.0)


class TestSolar(unittest.TestCase):
    """Own panels: the plant uses their power in daylight, the rest is sold."""

    def test_solar_cuts_bought_electricity_and_its_co2(self):
        """855 full-load hours; used + sold = made; the grid's CO2 only on what is bought."""
        rules, demand, model = _setup()
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)
        off = dp.simulate_year(plant, demand, model, rules)
        on = dp.simulate_year(plant, demand, model, replace(rules, solar_mwp=5.0))
        sun = on.solar
        self.assertAlmostEqual(sun["generated_gwh"], 5 * 855 / 1000, 2)
        self.assertAlmostEqual(sun["used_gwh"] + sun["sold_gwh"], sun["generated_gwh"], 2)
        self.assertLess(on.co2_t["electricity"], off.co2_t["electricity"])
        used = sum(off.electricity_gwh.values()) - sun["bought_gwh"]
        self.assertAlmostEqual(used, sun["used_gwh"], 2)
        econ = dp.economics(plant, on, dp.Prices(), rules=rules)
        names = [ln[0] for ln in econ.lines]
        self.assertIn("Own solar", names)
        self.assertIn("Electricity: own solar used", names)
        self.assertIn("table 3.3", SOURCES["solar_eur_per_mwh"])


class TestStorage(unittest.TestCase):
    """A hot-water store moves geothermal heat to the boiler's days."""

    def test_store_saves_boiler_heat_and_keeps_the_balance(self):
        """Less boiler heat, the buildings' heat still met, losses counted, never above size."""
        rules, demand, model = _setup()
        plant = dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0)
        off = dp.simulate_year(plant, demand, model, rules)
        on = dp.simulate_year(plant, demand, model, replace(rules, storage_mwh=1000.0))
        st = on.storage
        self.assertGreater(st["boiler_saved_gwh"], 0.0)
        self.assertLess(on.heat_split_gwh["boiler"], off.heat_split_gwh["boiler"])
        self.assertAlmostEqual(st["charged_gwh"] - st["given_gwh"], st["lost_gwh"], 2)
        self.assertAlmostEqual(on.heat_delivered_gwh, off.heat_delivered_gwh, 1)
        level = np.asarray(on.daily_mw["storage"]["level_mwh"])
        self.assertLessEqual(level.max(), 1000.0 + 1e-6)
        self.assertGreaterEqual(level.min(), -1e-6)
        self.assertFalse(on.violations)
        econ = dp.economics(plant, on, dp.Prices(), rules=rules)
        self.assertTrue(any(i["item"] == "Heat store" for i in econ.capex_items))
        self.assertIn("141 Large-scale hot water", SOURCES["storage_meur_per_mwh"])

    def test_nothing_to_move_without_a_boiler_day(self):
        """A design whose geothermal meets every day leaves the store idle, and says so."""
        rules, demand, model = _setup()
        plant = dp.Plant(3, boiler_mw=30.0, chiller_mw=12.0)
        y = dp.simulate_year(plant, demand, model, replace(rules, storage_mwh=500.0))
        if y.heat_split_gwh["boiler"] < 0.01:
            self.assertEqual(y.storage.get("note"), "nothing to move")


class TestUpstreamGas(unittest.TestCase):
    """The bought gas's supply chain, as CO2-equivalent, beside the total."""

    def test_upstream_is_counted_apart(self):
        """54 kg per MWh of gas bought; not in the total."""
        rules, demand, model = _setup()
        y = dp.simulate_year(dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0), demand, model, rules)
        self.assertAlmostEqual(y.co2_t["upstream_gas_co2e"], y.purchased_gas_gwh * 54.0, -1)
        parts = y.co2_t["purchased_gas"] + y.co2_t["produced_gas"] + y.co2_t["electricity"]
        self.assertAlmostEqual(y.co2_t["total"], parts, 0)


class TestOperability(unittest.TestCase):
    """Minimum loads and trips, counted beside the daily dispatch."""

    def test_more_units_cycle_less(self):
        """A boiler built as three units runs below its minimum on fewer days than one."""
        from dioscuri_plant import operability

        rules, demand, model = _setup()
        one = dp.simulate_year(dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0), demand, model, rules)
        three = dp.simulate_year(
            dp.Plant(1, boiler_mw=30.0, chiller_mw=12.0, boiler_units=3), demand, model, rules
        )
        days = lambda y: next(  # noqa: E731
            u["days_below"] for u in y.operability["units"] if u["kind"] == "boiler"
        )
        self.assertLess(days(three), days(one))
        trips = one.operability["trips"]
        self.assertGreater(trips["boiler_gwh"], 0)
        self.assertIn("assumed", one.operability["source"])
        said = " ".join(operability.warnings(one.operability))
        self.assertIn("gas boiler runs below its minimum load", said)


class TestSecondAquifer(unittest.TestCase):
    """A second aquifer: its own rock for the doublets drilled to it, tried by the search."""

    def test_doublets_there_see_its_rock(self):
        """Its permeability and thickness, hydrostatic pressure; the known aquifer unchanged."""
        from gemini_agent import projects

        rules = replace(
            engine.rules_for(DesignBrief()),
            second_aquifer_depth_m=3200.0,
            second_aquifer_thickness_m=40.0,
            second_aquifer_permeability_md=400.0,
        )
        there = rules.aquifer_at(3200.0)
        self.assertEqual((there.permeability_md, there.reservoir_thickness_m), (400.0, 40.0))
        self.assertAlmostEqual(there.reservoir_pressure_bar, 1030 * 9.81 * 3200 / 1e5, 1)  # bar(g)
        self.assertIs(rules.aquifer_at(2500.0), rules)
        self.assertIn(3200.0, projects.depths(rules))
        model = engine.doublet_model(rules)
        demand = engine.demand_of(DesignBrief())
        y = dp.simulate_year(dp.Plant(1, depth_m=3200.0, boiler_mw=30.0), demand, model, rules)
        row = y.doublet_summary[0]
        self.assertEqual(row["producer_open_m"], 40.0)
        plain = dp.simulate_year(
            dp.Plant(1, depth_m=3200.0, boiler_mw=30.0),
            demand,
            engine.doublet_model(engine.rules_for(DesignBrief())),
            engine.rules_for(DesignBrief()),
        )
        # 40 m at 400 mD flows less easily than the assumed 100 m at 200 mD.
        self.assertLess(row["pi_m3h_per_bar"], plain.doublet_summary[0]["pi_m3h_per_bar"])


if __name__ == "__main__":
    unittest.main()


class TestRiskSizing(unittest.TestCase):
    """The backup sized by risk (one day short in ten years) beside its N-1 size."""

    def test_risk_size_is_smaller_and_meets_the_target(self):
        """Smaller than the boiler that covers the peak alone; within the target; days fall."""
        from dioscuri_plant import montecarlo

        rules, demand, model = _setup()
        plant = dp.Plant(1, depth_m=3500.0, boiler_mw=30.0, chiller_mw=12.0)
        r = montecarlo.risk_sizing(plant, demand, model, rules, years=300)
        self.assertLessEqual(r["risk_mw"], r["n1_mw"])
        self.assertLessEqual(r["at_risk"]["lole_days"], montecarlo.LOLE_TARGET_DAYS)
        days = [d for _, d in r["tried"]]
        self.assertGreaterEqual(days[0], days[-1])  # smaller backups run short more often
        self.assertIsNone(montecarlo.risk_sizing(dp.Plant(1), demand, model, rules, years=50))


class TestGridByMonth(unittest.TestCase):
    """The grid's CO2 shaped by month (Ember, Netherlands 2024), the year's level kept."""

    def test_winter_electricity_weighs_more(self):
        """The shape averages one over the year's generation; a winter-heavy load emits more."""
        from dioscuri_plant import Components

        shape = Components().grid_month_shape
        self.assertGreater(shape[10], 1.3)  # November
        self.assertLess(shape[5], 0.8)  # June
        rules, demand, model = _setup()
        plant = dp.Plant(1, heat_pump_mw=8.0, boiler_mw=30.0, chiller_mw=12.0)
        flat = dp.simulate_year(plant, demand, model, rules)
        monthly = dp.simulate_year(plant, demand, model, replace(rules, grid_by_month=1.0))
        self.assertNotEqual(monthly.co2_t["electricity"], flat.co2_t["electricity"])
        self.assertEqual(monthly.co2_t["purchased_gas"], flat.co2_t["purchased_gas"])
