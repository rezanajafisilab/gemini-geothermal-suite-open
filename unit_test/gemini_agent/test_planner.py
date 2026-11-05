"""The planner's reading checked by code: steps, changes per step, failures, folded habits."""

import unittest

from gemini_agent import parameters as P


class TestPlanReading(unittest.TestCase):
    """What the model's reading becomes once code has checked it."""

    def test_two_values_of_one_parameter_are_two_steps(self):
        """Two values of one parameter ("50 °C, and what if it were 45 °C?"): two what-ifs."""
        r = P.check(
            {
                "changes": [
                    {"key": "heat_return_c", "value": 50, "quote": "return were 50 °C", "step": 0},
                    {"key": "heat_return_c", "value": 45, "quote": "45 °C", "step": 0},
                ],
                "steps": [{"do": "what_if"}],
            },
            "What if the heating return were 50 °C, and what if it were 45 °C?",
            {"heat_return_c": 60.0},
        )
        self.assertEqual([s.do for s in r.steps], ["what_if", "what_if"])
        self.assertEqual(
            (r.changes_for(0), r.changes_for(1)), ({"heat_return_c": 50.0}, {"heat_return_c": 45.0})
        )

    def test_step_changes_and_stray_failures_are_gathered(self):
        """Values under the step, a failure's dates under changes: both land where code reads."""
        r = P.check(
            {
                "changes": [
                    {
                        "key": "failures",
                        "value": [
                            {"unit": "chiller", "from": "", "to": "", "days": 7, "quote": "x"}
                        ],
                        "quote": "x",
                    }
                ],
                "failures": [{"unit": "chiller", "quote": "the chillers are out for a week"}],
                "steps": [
                    {"do": "what_if", "quote": "q", "changes": []},
                    {"do": "failure", "quote": "the chillers are out for a week", "changes": []},
                ],
            },
            "the chillers are out for a week, problem?",
            {},
        )
        self.assertEqual([s.do for s in r.steps], ["failure"])  # the empty what-if was an echo
        self.assertEqual((r.failures[0].unit, r.failures[0].days), ("chillers", 7))

    def test_condition_only_design_is_a_what_if_when_designed(self):
        """A condition alone ("drop the return by 10 K") with a design there is a what-if."""
        r = P.check(
            {
                "changes": [
                    {"key": "heat_return_c", "value": 50, "quote": "drop the return temp by 10 K"}
                ],
                "steps": [{"do": "design"}],
            },
            "drop the return temp by 10 K",
            {"heat_return_c": 60.0},
            designed=True,
        )
        self.assertEqual([s.do for s in r.steps], ["what_if"])

    def test_dates_in_other_languages(self):
        """Dutch and German day ranges are read as days, not as a network's temperatures."""
        for msg in (
            "Wat gebeurt er als de warmtepomp van 3 tot 17 februari uitvalt?",
            "Was passiert, wenn die Wärmepumpe vom 3. bis 17. Februar ausfällt?",
        ):
            r = P.check(
                {"failures": [{"unit": "heat pump", "quote": msg}], "steps": [{"do": "failure"}]},
                msg,
                {},
            )
            self.assertEqual((r.failures[0].first, r.failures[0].last), (33, 47), msg)

    def test_a_duration_in_a_named_month_is_a_window(self):
        """A duration in a named month ("three weeks in January"): 21 days, worst start by code."""
        msg = "what if the boiler trips for three weeks in January"
        r = P.check(
            {
                "failures": [
                    {
                        "unit": "boiler",
                        "from": "01-01",
                        "to": "01-21",
                        "quote": "the boiler trips for three weeks in January",
                    }
                ],
                "steps": [{"do": "failure"}],
            },
            msg,
            {},
        )
        f = r.failures[0]
        self.assertEqual((f.first, f.last, f.days), (0, 30, 21))

    def test_planned_maintenance_flag(self):
        """Planned work is marked, so the mildest days are taken."""
        msg = "We want to take the heat pump out for 10 days of maintenance"
        r = P.check(
            {
                "failures": [
                    {
                        "unit": "heat pump",
                        "days": 10,
                        "planned": True,
                        "quote": "take the heat pump out for 10 days of maintenance",
                    }
                ],
                "steps": [{"do": "failure"}],
            },
            msg,
            {},
        )
        self.assertTrue(r.failures[0].planned)
        self.assertEqual(r.failures[0].days, 10)

    def test_doublet_name_is_not_a_count(self):
        """A doublet's name ("the ESP of doublet 1") never sets one doublet."""
        r = P.check(
            {"changes": [{"key": "n_doublets", "value": 1, "quote": "the ESP of doublet 1"}]},
            "what if the ESP of doublet 1 fails",
            {},
        )
        self.assertNotIn("n_doublets", r.changes)


if __name__ == "__main__":
    unittest.main()


class TestObjectiveField(unittest.TestCase):
    """What the design should be best at comes in its own field, checked by code."""

    def test_a_design_request_sets_it(self):
        """A design request ("the cheapest plant you can find") sets objective cost on its step."""
        r = P.check(
            {"changes": [], "objective": "cost", "steps": [{"do": "design", "quote": "x"}]},
            "Give me the cheapest plant you can find",
            {},
        )
        self.assertEqual(
            (r.changes, r.changes_for(0)), ({"objective": "cost"}, {"objective": "cost"})
        )

    def test_a_question_about_existing_designs_does_not(self):
        """Once designs exist, 'which has the lowest CO2?' is answered, not searched again."""
        r = P.check(
            {"changes": [], "objective": "co2", "steps": [{"do": "answer", "quote": "x"}]},
            "which of the designs has the lowest co2?",
            {},
            designed=True,
        )
        self.assertNotIn("objective", r.changes)

    def test_null_and_unknown_are_ignored(self):
        """Null (not said) and a value outside the options set nothing."""
        for goal in (None, "fastest"):
            r = P.check(
                {"changes": [], "objective": goal, "steps": [{"do": "design"}]}, "design it", {}
            )
            self.assertNotIn("objective", r.changes)


class TestCompareWithTheCurrent(unittest.TestCase):
    """A comparison that names one other existing design sets it against the current one."""

    def test_one_other_design_is_compared_with_the_current(self):
        """4 Nov: "how does it compare with the most reliable one?" ran no comparison."""
        from gemini_agent.agent import planned
        from unit_test.gemini_agent.test_naming import designed

        _, s = designed()
        other = next((e for e in s.candidates if e.alternative.picks and e is not s.chosen), None)
        if other is None or s.chosen is None:
            self.skipTest("one design only")
        msg = "How does it compare with that one?"
        uid = other.alternative.uid or other.alternative.code
        r = P.Reading(designs=[uid], steps=[P.Step("compare", msg)])
        self.assertTrue(planned(r, s, msg))
        self.assertEqual([st.do for st in r.steps], ["compare"])
        mine = s.chosen.alternative.uid or s.chosen.alternative.code
        r = P.Reading(designs=[mine], steps=[P.Step("compare", msg)])
        self.assertFalse(planned(r, s, msg))  # the current design alone: nothing to compare
        r = P.Reading(designs=[uid], changes={"n_doublets": 2}, steps=[P.Step("compare", msg)])
        self.assertFalse(planned(r, s, msg))  # a new option to run: the search compares
