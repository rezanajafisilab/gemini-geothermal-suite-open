"""Where a number comes from (2 Nov): code finds which figure a number is and how it was found.

"Where does the 30 MW come from?" got "I couldn't confirm an answer" or the circular "three 10 MW
units" (1 Nov). Each figure's working comes from the design itself: the boilers' N-1 sizing, the
cost of heat by its lines, the brine's temperatures from the rock's.
"""

import unittest

from gemini_agent import provenance
from gemini_agent.intake import numbers_in
from unit_test.gemini_agent.test_agent import run
from unit_test.gemini_agent.test_naming import designed


def reply(events):
    """Return the text of a turn's reply."""
    return "".join(e.get("delta", "") for e in events if e["type"] == "TEXT_MESSAGE_CONTENT")


class TestOrigins(unittest.TestCase):
    """The working of a design's figures, from the design."""

    @classmethod
    def setUpClass(cls):
        """Design once for the class (scripted models)."""
        cls.agent, cls.s = designed()
        cls.e = cls.s.chosen
        cls.boiler = cls.e.alternative.sizes_mw["boiler"]

    def test_asks_origin(self):
        """Any wording that asks for a number's origin; a number is needed."""
        for text in (
            f"Where does the {self.boiler:g} MW come from?",
            "How was the 75.7 calculated?",
            "how did you get 69.8 €/MWh",
            "What is the 52.1 °C based on?",
        ):
            self.assertTrue(provenance.asks_origin(text), text)
        for text in ("Where does the heat come from?", "What does it cost?"):
            self.assertFalse(provenance.asks_origin(text), text)

    def test_the_unit_picks_the_figure(self):
        """A number two figures give (30 MW of boilers, 30.4 €/MWh of cold): its unit picks."""
        self.assertEqual(
            provenance._units("the 30 MW, 30.4 €/MWh, 36 M€ and 1,200 MWh"),
            {30.0: "MW", 30.4: "€/MWh", 36.0: "M€"},
        )
        keys = [k for k, *_ in provenance.origins(self.e, f"Where is {self.boiler:g} MW from?")]
        self.assertIn("boiler_size", keys)
        self.assertFalse([k for k in keys if k.startswith("lco")])

    def test_boiler_size_by_its_sizing(self):
        """The boilers' size is explained by the N-1 sizing, with numbers other than the size."""
        if self.e.alternative.boiler_units < 2:
            self.skipTest("the design has one boiler unit")
        text, must, _ = provenance.draft(self.e, f"Where does the {self.boiler:g} MW come from?")
        self.assertIn("N-1", text)
        # The case that sets it leads: the only doublet out, the boilers carry the peak alone.
        self.assertTrue(text.startswith("The size is set by the N-1 rule"))
        self.assertIn("doublet out", must)
        # The working is not the figure asked about again: a normal year's most.
        normal = [m for m in must if m.startswith("~")]
        self.assertTrue(normal and all(abs(x - self.boiler) > 0.1 for x in numbers_in(normal[0])))

    def test_cost_of_heat_is_the_sum_of_its_lines(self):
        """The cost of heat is its lines per MWh; they add up to it."""
        lcoh = self.e.economics.lcoh_eur_per_mwh
        text, _, _ = provenance.draft(self.e, f"How was the {lcoh} calculated?")
        self.assertIn("The cost of heat", text)
        line = text.split("is the sum of: ", 1)[1].split(". ", 1)[0]
        parts = [numbers_in(p)[-1] for p in line.split("; ")]
        self.assertAlmostEqual(sum(parts), lcoh, delta=0.1 * len(parts))
        # A part named twice in the economics (capital and per-MW capital) shows once.
        names = [p.rsplit(" ", 2)[0] for p in line.split("; ")]
        self.assertEqual(len(names), len(set(names)))

    def test_capital_is_the_sum_of_its_items(self):
        """The capital is its items."""
        capex = self.e.economics.capex_meur
        text, _, _ = provenance.draft(self.e, f"Where does the {capex:.1f} M€ come from?")
        self.assertIn("The capital", text)

    def test_reinjection_from_the_rock(self):
        """The brine's temperatures come from the rock's and the well's losses."""
        t = round(self.e.year.reinjection_c, 1)
        text, _, _ = provenance.draft(self.e, f"Why is the reinjection {t} °C?")
        self.assertIn("The rock at", text)

    def test_reinjection_names_its_day_and_what_set_it(self):
        """The coldest reinjection is told by its day, its brine and what limited the cooling."""
        t = round(self.e.year.reinjection_c, 1)
        text, must, _ = provenance.draft(self.e, f"What is the {t} °C reinjection based on?")
        self.assertIn("coldest the brine goes back", text)
        self.assertRegex(text, r"(?i)the \d+ K cap|That is the cap")
        self.assertGreaterEqual(len(must), 2)  # the wellhead and the cooling (and a low flow)

    def test_unknown_number(self):
        """A number the design does not give has no origin to tell."""
        self.assertIsNone(provenance.draft(self.e, "Where does the 999 come from?"))

    def test_the_agent_answers_with_the_working(self):
        """In the chat, the reply keeps the working, not only the figure."""
        if self.e.alternative.boiler_units < 2:
            self.skipTest("the design has one boiler unit")
        ev = run(
            self.agent,
            self.s,
            f"Where does the {self.boiler:g} MW in “The plant uses three boilers” come from?",
        )
        text = reply(ev)
        self.assertIn("boiler_size", self.s.last.get("provenance") or [])
        self.assertIn("N-1", text)


class TestReplyChecks(unittest.TestCase):
    """Checks every reply gets: calculations that add up, LaTeX read whole."""

    def test_wrong_sums(self):
        """A calculation whose result is wrong is found; rounding, units and dates pass."""
        from gemini_agent.answer import wrong_sums

        wrong = wrong_sums("Calculation: $86.1\\text{ °C} - 40\\text{ K} = 52.1\\text{ °C}$.")
        self.assertEqual(len(wrong), 1)
        self.assertAlmostEqual(wrong[0][1], 46.1)
        self.assertTrue(wrong_sums("6.5 + 1.7 + 0.4 + 24.4 = **75.7 €/MWh**"))
        for fine in (
            "3 x 10 MW = 30 MW",
            "37.4% + 19.7% + 42.9% = 100%",
            "111.7 GWh × 75.7 €/MWh = 8.46 M€",
            "On 2027-01-28 the COP = 3.2.",
            "1,030 × 2 = 2,060",
            "6.5 + 6.9 + 0.4 + 2.6 + 1.5 + 10.9 + 0.6 + 1.2 + 8.6 + 5.2 + 24.4 + 5.3 + 1.8 = 75.7",
        ):
            self.assertEqual(wrong_sums(fine), [], fine)

    def test_latex_in_json(self):
        """A text command in the model's JSON stays a command, not a tab and "ext"."""
        import json

        from gemini_agent.llm import latex_escapes

        raw = '{"a": "$86.1\\text{ °C} \\times 2$ \\\\text kept\\nnext"}'
        self.assertEqual(
            json.loads(latex_escapes(raw))["a"], "$86.1\\text{ °C} \\times 2$ \\text kept\nnext"
        )


if __name__ == "__main__":
    unittest.main()
