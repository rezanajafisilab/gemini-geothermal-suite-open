"""Real Dutch doublets against their published figures (2 Nov)."""

import unittest

from gemini_agent import validation


class TestBrine(unittest.TestCase):
    """The brine's properties for its salinity (Sharqawy et al. 2010)."""

    def test_seawater_and_brine(self):
        """Seawater (35 g/kg, 20 °C) about 3,999 J/(kg K) and 1,025 kg/m3; saltier, less."""
        self.assertAlmostEqual(validation.brine_cp(35, 20), 3999, delta=5)
        self.assertAlmostEqual(validation.brine_density(35, 20), 1024.8, delta=1.0)
        self.assertLess(validation.brine_cp(140, 60), 3600)


class TestProjects(unittest.TestCase):
    """What agrees, and what is not a check at all."""

    @classmethod
    def setUpClass(cls):
        """Run both projects once."""
        cls.checks = {c["key"]: c for c in validation.all_projects()}

    def test_trias_westland_p50(self):
        """The wellhead and the heat at 525 m3/h agree with the report's P50."""
        rows = {r["quantity"]: r for r in self.checks["trias_westland"]["rows"]}
        self.assertTrue(rows["Brine at the wellhead"]["agree"])
        self.assertTrue(rows["Heat at the published flow"]["agree"])
        self.assertIsNone(rows["COP (heat / pumps)"]["agree"])  # not like for like

    def test_hal_says_what_is_not_a_check(self):
        """The wellhead was calibrated and the heat is the decision's own arithmetic: not judged."""
        rows = {r["quantity"]: r for r in self.checks["hal_leyweg"]["rows"]}
        self.assertIsNone(rows["Brine at the wellhead"]["agree"])
        self.assertIn("not a check", rows["Brine at the wellhead"]["note"])
        self.assertIsNone(rows["Heat at the published flow"]["agree"])


if __name__ == "__main__":
    unittest.main()
