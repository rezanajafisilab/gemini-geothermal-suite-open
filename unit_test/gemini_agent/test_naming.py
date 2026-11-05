"""Keeping track of designs (2 Nov): names in words, the user's names and stars, @ picks.

Runs and designs are named in words; the user's own names and stars are kept; the designs picked
with @ in the composer are what a question is about.
"""

import unittest

from gemini_agent import Agent, Session, naming, reliability, workbench
from gemini_agent.llm import ScriptedLLM
from gemini_agent.reporter import design_id
from unit_test.gemini_agent.test_agent import fake_intake, run
from unit_test.gemini_agent.test_understanding import model


def designed():
    """Return an agent and a session with the challenge designed once (scripted models)."""

    def reply(purpose, messages):
        return fake_intake(purpose, messages)

    agent = Agent(model(), reasoning_llm=ScriptedLLM(reply, model="qwen3.5:9b"))
    s = Session()
    run(agent, s, "Design a geothermal heating and cooling system for this district.")
    return agent, s


class TestNames(unittest.TestCase):
    """What a run and a design are called."""

    @classmethod
    def setUpClass(cls):
        """Design once for the class."""
        cls.agent, cls.s = designed()
        cls.wb = workbench.workbench(cls.s)

    def test_run_letters_and_names(self):
        """The first search is run A, the base case; its designs' handles start with A."""
        self.assertEqual(naming.letter(1), "A")
        self.assertEqual(naming.letter(27), "AA")
        run_a = self.wb["attempts"][0]
        self.assertEqual((run_a["letter"], run_a["name"]), ("A", "Run A · Base case"))
        row = next(r for r in self.wb["library"] if r["recommended"])
        self.assertEqual(row["scenario"]["name"], "Run A · Base case")

    def test_design_labels(self):
        """The chosen design is named by its picks; a design that is no pick by its rank."""
        chosen = self.s.chosen
        self.assertIn("Best overall", naming.design_label(chosen))
        other = next(
            r for r in self.wb["library"] if r["origin"] == "agent" and not r["picks"] and r["uid"]
        )
        self.assertRegex(other["label"], r"^(Rank \d+ in run A|Variant of A\d+)$")
        self.assertFalse(other["starred"])


class TestNamesAndStars(unittest.TestCase):
    """The user's own names and stars: kept, shown, and read in messages."""

    def setUp(self):
        """Design afresh for each test (names and stars change the session)."""
        self.agent, self.s = designed()
        self.chosen = design_id(self.s.chosen)

    def test_rename_and_star(self):
        """A name of the user's replaces the words; a star puts it on the shortlist."""
        workbench.set_meta(self.s, self.chosen, "Our pick", True)
        wb = workbench.workbench(self.s)
        d = next(x for x in wb["designs"] if x["id"] == self.chosen)
        self.assertEqual((d["label"], d["user_name"], d["starred"]), ("Our pick", "Our pick", True))
        workbench.set_meta(self.s, self.chosen, "", False)
        d = next(x for x in workbench.workbench(self.s)["designs"] if x["id"] == self.chosen)
        self.assertEqual((d["user_name"], d["starred"]), (None, False))

    def test_bad_meta_is_refused(self):
        """An unknown design or a name too long is refused."""
        with self.assertRaises(KeyError):
            workbench.set_meta(self.s, "Z9 · nothing", "x", None)
        with self.assertRaises(ValueError):
            workbench.set_meta(self.s, self.chosen, "x" * 61, None)

        """The user's name finds the design; names and stars come back with the session."""
        """ "Our pick" finds the design; names and stars come back with the session."""
        workbench.set_meta(self.s, self.chosen, "Our pick", True)
        found, missing = reliability.resolve(["our pick"], self.s)
        self.assertEqual([design_id(e) for e in found], [self.chosen])
        back = Session.from_dict(self.s.to_dict())
        self.assertEqual(
            (back.design_names, back.starred), ({self.chosen: "Our pick"}, [self.chosen])
        )

    def test_a_picked_design_is_what_the_question_is_about(self):
        """Picked with @, an earlier run's design is the one a value is looked up on."""
        other = next(
            e for e in self.s.candidates if e.alternative.role == "candidate" and e.alternative.uid
        )
        run(self.agent, self.s, "What does it cost?", designs=[design_id(other)])
        self.assertIs(self.agent._focus, other)


if __name__ == "__main__":
    unittest.main()
