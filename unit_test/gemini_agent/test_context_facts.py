"""Tests for the context the answerer gets (5 Nov): what fits, why each pick lost, what changed.

1. ``answer.fit`` puts back what fits after its greedy steps: a block dropped early (the
   design search) comes back cut when a later cut freed the room.
2. ``answer.why_not``: each search pick says, by code, why it is not the best overall.
3. ``answer.changes_block``: each what-if before → after against the design it was run on.
"""

import copy
import unittest

from gemini_agent import Agent, Session, answer, reporter
from gemini_agent.answer import Block
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import FULL_BRIEF, confirmed, fake_intake, run


def words(n: int, word: str = "word") -> str:
    """Return ``n`` words, about ``n`` tokens."""
    return " ".join([word] * n)


class TestPutBack(unittest.TestCase):
    """A dropped block comes back when a later cut freed room enough for it."""

    def test_the_search_comes_back_when_the_design_cut_freed_room(self):
        """The picks are dropped before the design is cut; once it is, the picks fit again."""
        picks = "The design search's picks: " + words(300, "pick") + " " + words(1500, "rest")
        blocks = [
            Block("self", "self", "Dioscuri."),
            Block("A1", "design", words(1600, "design")),
            Block("search", "design", picks),
            Block("draft", "draft", "The cost of heat is 64.7 €/MWh."),
        ]
        # Room for the design cut to 3,000 characters and the picks cut, not for the design whole.
        cut_design = answer._cut(blocks[1], 3000)
        cut_search = answer._cut(blocks[2], answer.SEARCH_CUT)
        budget = answer.blocks_tokens([blocks[0], cut_design, cut_search, blocks[3]]) + 20
        kept = answer.fit(blocks, budget)
        ids = [b.id for b in kept]
        self.assertIn("search", ids)  # before 5 Nov: dropped, though it fitted at the end
        self.assertEqual(ids, ["self", "A1", "search", "draft"])  # in their order
        self.assertLessEqual(answer.blocks_tokens(kept), budget)
        search = next(b for b in kept if b.id == "search")
        self.assertTrue(search.text.startswith("The design search's picks: pick"))

    def test_nothing_changes_when_everything_fits(self):
        """A pack under the budget goes out as it is."""
        blocks = [Block("self", "self", "Dioscuri."), Block("search", "design", "picks")]
        self.assertEqual(answer.fit(blocks, 1000), blocks)

    def test_an_earlier_cut_is_undone_when_a_later_one_freed_room(self):
        """The capability card, cut early, comes back whole once the design cut freed room."""
        blocks = [
            Block("self", "self", "Dioscuri."),
            Block("A1", "design", words(1600, "design")),
            Block("capabilities", "self", words(150, "option")),
        ]
        cut_design = answer._cut(blocks[1], 3000)
        budget = answer.blocks_tokens([blocks[0], cut_design, blocks[2]]) + 5
        kept = answer.fit(blocks, budget)
        self.assertLessEqual(answer.blocks_tokens(kept), budget)
        self.assertEqual(next(b for b in kept if b.id == "capabilities").text, blocks[2].text)


class Designed(unittest.TestCase):
    """One designed conversation (a scripted model, the real search), copied for each test."""

    @classmethod
    def setUpClass(cls):
        """Design the challenge district once."""
        cls.base = confirmed(Session())
        run(Agent(ScriptedLLM(fake_intake)), cls.base, FULL_BRIEF)

    def session(self):
        """Return a fresh copy of the designed conversation."""
        return copy.deepcopy(self.base)


class TestWhyNot(Designed):
    """Each pick says why it is not the best overall: the rule it broke, then the differences."""

    def test_every_other_pick_has_its_reason(self):
        """The best overall has no why-not line; every other pick has one, against it."""
        s = self.session()
        block = answer.search_block(s.candidates, search=s.searches[-1])
        head = block.text.split("The last design search")[0]
        picks = [e for e in s.candidates if e.alternative.picks]
        best = next(e for e in picks if "best" in e.alternative.picks)
        top = best.alternative.uid
        for e in picks:
            line = next(x for x in head.splitlines() if x.startswith(f"- {e.alternative.uid} "))
            if e is best:
                self.assertNotIn("not the best overall", line)
                continue
            self.assertIn("not the best overall: ", line)
            self.assertIn(f"(against {top}: heat and cold ", line)
            if not e.alternative.reliable:
                self.assertIn("must be sized for one unit out (N-1)", line)

    def test_the_differences_are_worked_out(self):
        """The signed difference of the cost of heat and cold against the best overall."""
        s = self.session()
        picks = [e for e in s.candidates if e.alternative.picks]
        best = next(e for e in picks if "best" in e.alternative.picks)
        other = next(e for e in picks if e is not best)
        line = answer.why_not(other, best)
        d = other.economics.lcoe_eur_per_mwh - best.economics.lcoe_eur_per_mwh
        self.assertIn(f"heat and cold {d:+.1f} €/MWh", line)
        self.assertEqual(answer.why_not(best, best), "")


class TestChanges(Designed):
    """A what-if before → after, against the design it was run on, worked out by code."""

    def what_if(self, s, uid, label, heat_up):
        """Return a copy of the chosen design as a what-if with a dearer cost of heat."""
        base = s.chosen
        e = base.model_copy(deep=True)
        e.alternative.uid = uid
        e.alternative.role = "what_if"
        e.alternative.parent = reporter.design_id(base)
        e.change_label = label
        e.economics.lcoh_eur_per_mwh = base.economics.lcoh_eur_per_mwh + heat_up
        return e

    def test_the_change_alone_first_then_a_new_search(self):
        """W1 (the store alone) before B1 (a new search's pick, a different design)."""
        s = self.session()
        base = s.chosen
        b1 = self.what_if(s, "B1", "heat store at the plant 2000 MWh, searched again", 1.3)
        b1.alternative.code = base.alternative.code + "-PV1.3-TS2000"
        w1 = self.what_if(s, "W1", "heat store at the plant 2000 MWh", 2.2)
        s.ledger = list(s.ledger) + [b1, w1]
        text = answer.changes_block(s).text
        was = reporter.num(base.economics.lcoh_eur_per_mwh)
        now = reporter.num(w1.economics.lcoh_eur_per_mwh)
        self.assertIn(f"cost of heat {was} → {now} €/MWh (+2.2 €/MWh)", text)
        self.assertLess(text.index("- W1 "), text.index("- B1 "))
        self.assertIn("nothing else changed", text.split("- B1 ")[0])
        self.assertIn("so not the change alone", text.split("- B1 ")[1])

    def test_no_block_without_a_what_if(self):
        """A conversation with no what-if has no changes block."""
        self.assertIsNone(answer.changes_block(self.session()))


if __name__ == "__main__":
    unittest.main()
