"""Ali's cooling model run on a design's chillers and towers (2 Nov), without weather files."""

import unittest

import numpy as np

from gemini_agent import cooling_check
from unit_test.gemini_agent.test_naming import designed


class TestWeather(unittest.TestCase):
    """The typical De Bilt year used when the project has no weather files."""

    def test_typical_year(self):
        """365 days; the wet bulb never above the dry bulb; summer warmer than winter."""
        w = cooling_check.typical_weather()
        self.assertEqual(w["dry_bulb_c"].shape, (365,))
        self.assertTrue(np.all(w["wet_bulb_c"] <= w["dry_bulb_c"] + 1e-9))
        self.assertGreater(w["dry_bulb_c"][196], w["dry_bulb_c"][15] + 10)
        # Stull (2011): 20 °C at 50 % is about 13.7 °C wet bulb.
        self.assertAlmostEqual(
            float(cooling_check.wet_bulb(np.array(20.0), np.array(50.0))), 13.7, 1
        )


class TestCheck(unittest.TestCase):
    """The check sets Ali's figures beside ours and adds the towers' water."""

    def test_on_the_chosen_design(self):
        """The cold is the chillers', all met; water and electricity are positive."""
        _, s = designed()
        e = s.chosen
        out = cooling_check.check(e)
        if not (e.alternative.sizes_mw or {}).get("chillers"):
            self.assertIsNone(out)
            return
        self.assertAlmostEqual(out["cold_gwh"], out["ours"]["cold_gwh"], 1)
        self.assertGreater(out["makeup_water_m3"], out["evaporation_m3"])
        self.assertGreater(out["compressor_gwh"], 0)
        self.assertIn("De Bilt", out["weather"])
        self.assertIn("make-up water", " ".join(cooling_check.words(out)))

    def test_absorption_on_the_brine(self):
        """An absorption design: its chiller runs on our brine share, at its own COP."""
        from gemini_agent import engine
        from gemini_agent.agent import Session

        out = engine.search(Session().brief)
        e = next(c for c in out.candidates if (c.alternative.sizes_mw or {}).get("absorption"))
        r = cooling_check.check(e)
        ab = r["absorption"]
        self.assertGreater(ab["cold_gwh"], 0)
        # Ali's thermal COP 0.7 against our 0.75: less cold from the same brine.
        self.assertLessEqual(ab["drive_gwh"], ab["ours_drive_gwh"] + 1e-6)
        self.assertAlmostEqual(ab["cold_gwh"] / ab["drive_gwh"], 0.7, 2)
        self.assertEqual(r["not_checked"], [])
        self.assertIn("absorption chiller makes", " ".join(cooling_check.words(r)))


class TestTowersAndCop(unittest.TestCase):
    """4 Nov: the towers reject free cooling's heat too; the compressors run at our COP."""

    def test_free_cooling_in_the_towers(self):
        """Make-up water and tower power include free cooling and agree with the year model."""
        from dataclasses import replace
        from types import SimpleNamespace

        import dioscuri_plant as dp
        from gemini_agent import engine
        from gemini_agent.contract import DesignBrief

        brief = DesignBrief()
        rules = replace(engine.rules_for(brief), free_cooling=1.0)
        plant = dp.Plant(1, depth_m=3000, heat_pump_mw=0.5, boiler_mw=30, chiller_mw=15)
        y = dp.simulate_year(plant, engine.demand_of(brief), engine.doublet_model(rules), rules)
        entry = SimpleNamespace(
            alternative=SimpleNamespace(sizes_mw={"chillers": 15.0, "absorption": 0.0}),
            year=y,
            brief=brief,
        )
        r = cooling_check.check(entry)
        # Our COP, so the compressors agree; the check isolates the towers and the water.
        self.assertAlmostEqual(r["cop"], y.chiller_cop, 2)
        self.assertAlmostEqual(r["compressor_gwh"], y.electricity_gwh["chillers"], 2)
        self.assertAlmostEqual(r["free_gwh"], y.cool_split_gwh["free"], 2)
        # The same water as the year model (the same constants), free cooling's included.
        self.assertAlmostEqual(r["makeup_water_m3"] / y.tower_water_m3["makeup"], 1.0, 3)
        self.assertAlmostEqual(r["towers_gwh"], y.electricity_gwh["towers"], 2)
        chillers_only = (y.cool_split_gwh["chill"] * (1 + 1 / y.chiller_cop)) * 1000 * 1.47
        self.assertGreater(r["makeup_water_m3"], 3 * chillers_only)
        self.assertIn("hour by hour", r["weather"])
        text = " ".join(cooling_check.words(r))
        self.assertIn("at our chillers' COP", text)
        self.assertIn("free cooling", text)


if __name__ == "__main__":
    unittest.main()
