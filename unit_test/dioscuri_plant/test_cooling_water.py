"""Free cooling on real hours, the towers' water and pumps, the absorption chiller's drive (4 Nov).

Each test pins the corrected behaviour against a hand calculation:

- free cooling's share of a day is the mean of the clipped share over De Bilt's real hours
  (KNMI 2021-2025), not the share of a smoothed day's wet bulb;
- the towers' make-up and blow-down water come from all the heat they reject, free cooling's
  included, and are priced on the cold side;
- the towers' electricity is their fans and their condenser-water pumps;
- the absorption chiller gives no cold when the brine is below 80 °C.
"""

import unittest
from dataclasses import replace
from functools import lru_cache

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant import weather
from dioscuri_plant.components import ABSORPTION_MIN_DRIVE_C, chiller_cop, tower_water_m3
from dioscuri_plant.economics import SOURCES
from dioscuri_plant.year import _absorption_warnings, free_share
from gemini_agent import engine
from gemini_agent.contract import DesignBrief

PICK = dp.Plant(1, depth_m=3000, heat_pump_mw=0.5, boiler_mw=30, chiller_mw=15)


def _setup(rules=None):
    rules = rules or engine.rules_for(DesignBrief())
    return rules, engine.demand_of(DesignBrief()), engine.doublet_model(rules)


@lru_cache(maxsize=1)
def _pick():
    """Return the challenge pick's year with free cooling on, its rules and its economics."""
    rules, demand, model = _setup()
    rules = replace(rules, free_cooling=1.0)
    y = dp.simulate_year(PICK, demand, model, rules)
    return y, rules, dp.economics(PICK, y, dp.Prices(), rules=rules)


class TestHourlyWetBulb(unittest.TestCase):
    """KNMI De Bilt, hour by hour, 2021-2025: the file and its shape."""

    def test_the_file(self):
        """1,825 days of 24 hours, one decimal, KNMI credited; 29 February left out."""
        text = weather.HOURLY_FILE.read_text(encoding="utf-8")
        self.assertIn("KNMI", text.splitlines()[0] + text.splitlines()[1])
        rows = [r for r in text.splitlines() if r[:1].isdigit()]
        self.assertEqual(len(rows), 5 * 365)
        self.assertTrue(rows[0].startswith("2021-01-01,"))
        self.assertFalse(any(r.startswith("2024-02-29") for r in rows))
        self.assertEqual(len(rows[0].split(",")), 25)
        self.assertTrue(all(len(x.split(".")[1]) == 1 for x in rows[0].split(",")[1:]))

    def test_shape_and_summer(self):
        """Each calendar day's 120 hours; real summers reach wet bulbs the normals never do."""
        wb = weather.hourly_wet_bulb()
        self.assertEqual(wb.shape, (365, 120))
        typical = weather.typical_year()["wet_bulb_c"]
        self.assertLess(typical.max(), 16.0)
        self.assertGreater(wb.max(), 20.0)
        # Row d holds day d of every year: 1 January 2021's first hour is the file's first value.
        first = [r for r in weather.HOURLY_FILE.read_text().splitlines() if r[:1].isdigit()][0]
        self.assertAlmostEqual(wb[0, 0], float(first.split(",")[1]))


class TestFreeShare(unittest.TestCase):
    """The day's share is the mean over its hours of the clipped share."""

    def test_hand_calculation(self):
        """16 July and 15 January: clip((25 - (wb + 6)) / 5, 0, 1), averaged by hand."""
        wb = weather.hourly_wet_bulb()
        share = free_share(25.0, 20.0, 6.0)
        for d in (15, 196):
            hand = sum(min(max((25.0 - (w + 6.0)) / 5.0, 0.0), 1.0) for w in wb[d]) / 120
            self.assertAlmostEqual(share[d], hand, 12)
        self.assertEqual(share[15], 1.0)  # winter: all of it
        self.assertLess(share[196], 1.0)  # summer: part of it

    def test_challenge_pick(self):
        """The pick's free cold, 17.3 GWh of 23.7: within 2021-2025's years (16.9-17.8 GWh).

        The smoothed year gave 21.0 GWh (the audit of 4 Nov).
        """
        y, rules, _ = _pick()
        cool = np.asarray(y.daily_mw["cool"]["demand"])
        free = np.asarray(y.daily_mw["cool"]["free"])
        hand = free_share(rules.cool_return_c, rules.cool_supply_c, 6.0) * cool
        np.testing.assert_allclose(free, hand, atol=1e-3)
        self.assertGreater(y.cool_split_gwh["free"], 16.9)
        self.assertLess(y.cool_split_gwh["free"], 17.8)
        self.assertAlmostEqual(y.cool_delivered_gwh, y.cool_demand_gwh, 2)
        self.assertFalse(y.violations)


class TestTowers(unittest.TestCase):
    """The towers' fans, pumps and water, on all the heat they reject."""

    def test_water_per_mw_by_hand(self):
        """1 MW for a day: 86,400 MJ x 0.8 / 2.45 MJ/kg = 28.2 m3 evaporated; 5 cycles."""
        evap, blow, makeup = tower_water_m3(1.0, dp.Components())
        self.assertAlmostEqual(float(evap), 86400 * 0.8 / 2.45 / 1000, 9)
        self.assertAlmostEqual(float(blow), float(evap) / 4, 9)
        self.assertAlmostEqual(float(makeup), float(evap) * 1.25, 9)

    def test_pick_by_hand(self):
        """Rejected = chillers' cold and electricity + free cold; pumps 0.5 %, fans 1.25 %."""
        y, rules, _ = _pick()
        comp = dp.Components()
        cop = chiller_cop(rules.cool_supply_c, 35.0, 0.5, 2.0)
        chill = np.asarray(y.daily_mw["cool"]["chill"])
        free = np.asarray(y.daily_mw["cool"]["free"])
        rejected = chill * (1 + 1 / cop) + free  # MW a day
        heat = rejected * 1.005  # the pumps' heat goes into the water
        towers_gwh = float(np.sum(0.0125 * heat + 0.005 * rejected)) * 24 / 1000
        self.assertAlmostEqual(y.electricity_gwh["towers"], towers_gwh, 2)
        evap_m3 = float(np.sum(heat)) * 24 * 3600 * 0.8 / 2450  # MWh x 3,600 MJ, 2.45 MJ/kg
        water = y.tower_water_m3
        self.assertAlmostEqual(water["evaporation"] / evap_m3, 1.0, 3)
        self.assertAlmostEqual(water["blowdown"] / (evap_m3 / 4), 1.0, 3)
        self.assertAlmostEqual(water["makeup"], water["evaporation"] + water["blowdown"], -1)
        # Free cooling is most of it: about 35,000 m3, not the chillers' 4,700 alone.
        self.assertGreater(water["makeup"], 30_000)
        self.assertEqual(comp.tower_pump_mw_el_per_mw, 0.005)

    def test_water_is_priced_on_the_cold_side(self):
        """Make-up at 1.64 €/m3 and blow-down at 0.40 €/m3, a cold-side line with sources."""
        y, _, econ = _pick()
        p = dp.Prices()
        line = dict(((i, k), m) for i, k, m in econ.lines_cold)[
            ("Water: cooling towers", "variable")
        ]
        hand = (y.tower_water_m3["makeup"] * 1.64 + y.tower_water_m3["blowdown"] * 0.40) / 1e6
        self.assertAlmostEqual(line, hand, 4)
        self.assertEqual((p.water_supply_eur_per_m3, p.blowdown_disposal_eur_per_m3), (1.64, 0.40))
        self.assertIn("WML", SOURCES["water_supply_eur_per_m3"])
        self.assertIn("Assumed", SOURCES["blowdown_disposal_eur_per_m3"])
        self.assertFalse(any(i == "Water: cooling towers" for i, _, _ in econ.lines_heat))

    def test_no_towers_no_water(self):
        """A design without chillers or absorption has no towers: no water, no line."""
        rules, demand, model = _setup()
        y = dp.simulate_year(dp.Plant(1, boiler_mw=30.0), demand, model, rules)
        self.assertEqual(y.tower_water_m3["makeup"], 0.0)
        econ = dp.economics(dp.Plant(1, boiler_mw=30.0), y, dp.Prices(), rules=rules)
        self.assertFalse(any(i.startswith("Water") for i, _, _ in econ.lines))


class TestAbsorptionDrive(unittest.TestCase):
    """The absorption chiller needs the brine at 80 °C (75 °C hot-water loop + 5 K)."""

    def test_limit_is_the_kernels(self):
        """80 °C, from the cooling component model's absorption settings."""
        from gemini_model.cooling_common.config import AbsorptionSettings

        a = AbsorptionSettings()
        self.assertEqual(ABSORPTION_MIN_DRIVE_C, a.hot_supply_c + a.hx_approach_k)
        self.assertEqual(dp.Components().absorption_min_drive_c, 80.0)

    def test_too_cold_gives_nothing(self):
        """At 1,800 m (about 65 °C) no absorption cold, a warning, the chillers do the rest."""
        rules, demand, model = _setup()
        plant = dp.Plant(1, depth_m=1800, heat_pump_mw=2, boiler_mw=30, absorption_mw=6)
        cold = dp.simulate_year(replace(plant, chiller_mw=20), demand, model, rules)
        self.assertLess(cold.wellhead_c, 80.0)
        self.assertEqual(cold.cool_split_gwh["abs"], 0.0)
        self.assertTrue(any("absorption chiller gives no cold" in w for w in cold.warnings))
        self.assertAlmostEqual(cold.cool_delivered_gwh, cold.cool_demand_gwh, 2)
        # With too few chillers the shortfall is a cooling violation, as before.
        short = dp.simulate_year(replace(plant, chiller_mw=4), demand, model, rules)
        self.assertTrue(any(v.startswith("Cooling short") for v in short.violations))

    def test_hot_enough_runs(self):
        """At 3,000 m the brine drives it: absorption cold, no such warning."""
        rules, demand, model = _setup()
        plant = dp.Plant(
            1, depth_m=3000, heat_pump_mw=2, boiler_mw=30, absorption_mw=6, chiller_mw=10
        )
        y = dp.simulate_year(plant, demand, model, rules)
        self.assertGreater(y.wellhead_c, 80.0)
        self.assertGreater(y.cool_split_gwh["abs"], 0.0)
        self.assertFalse(any("absorption chiller gives no cold" in w for w in y.warnings))

    def test_slow_days_warning(self):
        """Hot at full flow, too cold on two slow days: those days are named."""
        plant = dp.Plant(1, absorption_mw=6)
        comp = dp.Components()
        twh_day = np.full(365, 85.0)
        twh_day[[10, 11]] = 78.0
        runs = twh_day >= 80.0
        out = _absorption_warnings(plant, comp, np.ones(365), 85.0, twh_day, np.ones(365), runs)
        self.assertEqual(len(out), 1)
        self.assertIn("on 2 day(s)", out[0])
        self.assertIn("78.0 °C", out[0])


if __name__ == "__main__":
    unittest.main()
