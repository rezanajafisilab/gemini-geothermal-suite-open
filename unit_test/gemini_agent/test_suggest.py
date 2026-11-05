"""Follow-up suggestions (2 Nov): only questions the evals ask, fitting the reply's topic."""

import unittest
from pathlib import Path

import yaml

from gemini_agent import suggest
from unit_test.gemini_agent.test_agent import custom, run
from unit_test.gemini_agent.test_naming import designed

EVALS = Path(__file__).resolve().parents[2] / "hackathon" / "evals" / "scenarios"


def eval_wordings():
    """Return every prompt and wording of the eval suites, as written (placeholders kept)."""
    out = set()
    for name in ("scenarios.yaml", "chat.yaml"):
        for sc in yaml.safe_load((EVALS / name).read_text(encoding="utf-8")):
            out.add(str(sc.get("prompt", "")).strip())
            out.update(str(w).strip() for w in sc.get("wordings") or [])
    return out


class TestTested(unittest.TestCase):
    """Every suggestion is an eval wording, so the suite runs it."""

    def test_every_suggestion_is_an_eval_wording(self):
        """The catalogue and the language lists hold only wordings the evals ask."""
        wordings = eval_wordings()
        questions = [q for qs in suggest.CATALOGUE.values() for q, _ in qs]
        questions += [q for qs in suggest.LANGUAGES.values() for q, _ in qs]
        missing = [q for q in questions if q not in wordings]
        self.assertEqual(missing, [])


class TestPick(unittest.TestCase):
    """What a reply offers next."""

    @classmethod
    def setUpClass(cls):
        """Design once (scripted models)."""
        cls.agent, cls.s = designed()
        cls.e = cls.s.chosen

    def test_topic_and_numbers(self):
        """A cost question gets cost follow-ups; the design's numbers fill them."""
        got = suggest.pick(self.s, self.e, ["lcoh"])
        self.assertEqual(got[0], "What share of the yearly cost is gas?")
        capex = suggest.values(self.e)["capex"]
        self.assertIn(f"What is in the {capex} M€ capex?", got)
        self.assertNotIn("{", " ".join(got))

    def test_asked_is_left_out(self):
        """A question the chat already asked is not offered again."""
        got = suggest.pick(
            self.s, self.e, ["lcoh"], asked=["what share of the yearly cost is gas?"]
        )
        self.assertNotIn("What share of the yearly cost is gas?", got)

    def test_languages(self):
        """Dutch gets Dutch questions; a language without tested ones keeps the model's."""
        self.assertIn("Wat kost de warmte?", suggest.pick(self.s, self.e, language="nl"))
        self.assertIsNone(suggest.pick(self.s, self.e, language="fr"))

    def test_needs(self):
        """A question that needs a unit the design lacks is not offered."""
        for q, need in suggest.CATALOGUE["size"]:
            if need == "heat_pump" and not (self.e.alternative.sizes_mw or {}).get("heat_pump"):
                self.assertNotIn(q, suggest.pick(self.s, self.e, ["hex_size"]) or [])

    def test_the_chat_offers_them(self):
        """After an answer about the design, the chips are tested questions."""
        ev = run(self.agent, self.s, "What does heat cost?")
        chips = custom(ev, "suggestions") or []
        figures = suggest.values(self.e)
        tested = set()
        for q, _ in [q for qs in suggest.CATALOGUE.values() for q in qs]:
            for key, value in figures.items():
                q = q.replace("{" + key + "}", value)
            tested.add(q)
        self.assertTrue(chips)
        self.assertEqual([c for c in chips if c not in tested], [])


if __name__ == "__main__":
    unittest.main()
