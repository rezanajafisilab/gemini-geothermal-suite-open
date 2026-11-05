"""The eval's "says" checks read the words of a reply, not its Markdown (4 Nov).

R02_doublet_count_wrong failed on "the plant uses **1** doublet" because the check looked for
"1 doublet": the model was right, the normaliser was not.
"""

import sys
import unittest
from pathlib import Path

EVALS = Path(__file__).resolve().parents[2] / "hackathon" / "evals"


class TestEvalNormaliser(unittest.TestCase):
    """Fix 6: the eval's "says" checks read the words, not the Markdown emphasis."""

    @classmethod
    def setUpClass(cls):
        """Import the eval runner as the suites do."""
        sys.path.insert(0, str(EVALS))
        import run_evals

        cls.ev = run_evals

    def test_emphasis_is_ignored(self):
        """The words "**1** doublet" say "1 doublet"; names with underscores stay."""
        plain = self.ev._same_number_text
        self.assertIn("1 doublet", plain("the plant uses **1** doublet"))
        self.assertIn("one doublet", plain("only *one* doublet"))
        self.assertIn("No, it has 1 doublet.", plain("**No**, it has __1 doublet__."))
        name = "GEMINI_Heating_Demand_Daily_2027.csv"
        self.assertIn(name, plain(f"from {name}"))
        self.assertEqual(plain("2 * 3 and a*b"), "2 * 3 and a*b")

    def test_a_contains_any_check_passes_through_bold(self):
        """R02 failed on "the plant uses **1** doublet" for "1 doublet"; now it passes."""
        scenario = {
            "id": "R02",
            "prompt": "The plant uses 3 doublets, correct?",
            "expect": {"behaviour": "answer", "contains_any": ["1 doublet", "one doublet"]},
        }
        result = {"behaviour": "answer", "answer": "No: the plant uses **1** doublet."}
        verdict = self.ev.judge(scenario, result)
        self.assertTrue(verdict["pass"], verdict["checks"])


if __name__ == "__main__":
    unittest.main()
