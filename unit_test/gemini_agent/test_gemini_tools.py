"""GEMINI's own solver behind the tools: the fixed copy, the challenge doublet, the bug impact."""

import unittest

from gemini_agent import engine, gemini_runtime
from gemini_agent.contract import DesignBrief
from gemini_agent.tools import gemini


class TestRuntime(unittest.TestCase):
    """The fixed GEMINI is the release plus exactly the team's patch files."""

    def test_every_patch_applies_and_both_versions_load(self):
        """All patches apply to this release; the two versions are separate modules."""
        fixed, released = gemini_runtime.load("fixed"), gemini_runtime.load("asis")
        self.assertEqual(fixed.patches, [p.name for p in gemini_runtime.patches()])
        self.assertEqual(released.patches, [])
        self.assertTrue(fixed.HeatpumpBasic.__module__.startswith("gemini_model_fixed."))
        self.assertTrue(released.HeatpumpBasic.__module__.startswith("gemini_model."))

    def test_a_patch_that_no_longer_fits_fails_loudly(self):
        """A hunk whose context is not in the file is refused, not applied elsewhere."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.py").write_text("a = 1\nb = 2\n")
            bad = "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n a = 1\n-b = 3\n+b = 4\n"
            with self.assertRaises(gemini_runtime.PatchError):
                gemini_runtime.apply_patch(bad, Path(tmp))


class TestChallengeDoublet(unittest.TestCase):
    """The challenge's doublet on GEMINI's well solve, with the brine (patch 11)."""

    def test_pumps_rise_with_flow_and_the_well_cools_the_brine_more_at_low_flow(self):
        """More flow, more pump head; the brine loses about 1 K at full flow, more when slow."""
        low, high = gemini.doublet_point(100, 2500), gemini.doublet_point(300, 2500)
        self.assertLess(low["esp_head_bar"], high["esp_head_bar"])
        self.assertLess(low["injection_wellhead_bar"], high["injection_wellhead_bar"])
        self.assertAlmostEqual(high["wellhead_c"], 87.0 - 0.9, delta=0.1)  # Ramey, a year in
        self.assertAlmostEqual(low["wellhead_c"], 87.0 - 2.65, delta=0.1)
        self.assertAlmostEqual(high["pi_m3h_per_bar"], 11.7, delta=0.1)  # a doublet, L = 1,500 m

    def test_the_project_view_runs_at_the_design_flow(self):
        """Two doublets as a GEMINI project give 300 m3/h each on GEMINI's own solver.

        The brine of both producers joins in a mixer, runs through one surface plant and is
        shared again between the injectors; with a boiler, GEMINI's boiler burns the gas.
        """
        project = gemini.challenge_project(2500, 2, boiler_mw=5.0)
        self.assertEqual(
            list(project["components"]),
            [
                "producer_well_1",
                "producer_well_2",
                "brine_mixer",
                "separator",
                "filter_a",
                "heat_exchanger",
                "filter_b",
                "boiler",
                "brine_splitter",
                "injector_well_1",
                "injector_well_2",
            ],
        )
        out = gemini.run(project)
        self.assertAlmostEqual(out["flow_m3h"], 600.0, delta=1.0)
        self.assertGreater(out["injector_pump_mw"], 0.2)
        one = gemini.run(gemini.challenge_project(2500, 1))
        self.assertAlmostEqual(one["flow_m3h"], 300.0, delta=0.5)
        self.assertAlmostEqual(out["hex_duty_mw"], 2 * one["hex_duty_mw"], delta=0.05)

    def test_heat_pump_point_respects_carnot(self):
        """The fixed GEMINI heat pump stays below its Carnot COP at the top-up point."""
        hp = gemini.heat_pump_point(65.0, 600.0, 81.0, 100.0, 5.0)
        carnot = (100 + 273.15) / (100 - hp["source_out_c"])
        self.assertLess(hp["cop"], carnot)


class TestBugImpact(unittest.TestCase):
    """What GEMINI as released would have given for a challenge design."""

    def test_released_code_misses_the_injector_pump_and_the_heat_pumps_co2(self):
        """Released: a quarter of the injection pump (friction sign), a heat pump with no CO2."""
        outcome = engine.search(DesignBrief(doublet_depths_m=[2500.0]))
        design = next(e for e in engine.ranked(outcome) if e.alternative.heat_pump)
        rows = {r["quantity"]: r for r in engine.bug_impact(design)}
        pump = rows["Injection pump electricity"]
        self.assertLess(pump["released"], 0.3 * pump["fixed"])
        co2 = rows["Heat pump CO₂"]
        self.assertEqual(co2["released"], 0.0)
        self.assertGreater(co2["fixed"], 0.0)


if __name__ == "__main__":
    unittest.main()
