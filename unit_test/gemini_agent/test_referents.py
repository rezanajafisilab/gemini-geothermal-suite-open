"""Messages that refer to nothing, and replies that answer then ask (5 Nov, scripted models).

1. A message whose words name nothing ("3?", "42"): code asks what its number is for, with
   choices, whatever the reader called it (it was answered with a guess).
2. A design the answerer routed for words whose referent the reading left open ("use the
   setting we talked about" in a chat with none): asked, nothing run (it ran a design).
3. A reply that tells what the chat holds and then asks is an answer; the question is a chip.
"""

import copy
import unittest

from gemini_agent import Agent, Session, clarify
from gemini_agent.answer import answer_then_offer
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import (
    FULL_BRIEF,
    confirmed,
    fake_answer,
    fake_intake,
    run,
)


def scripted(intent=None, answer=None, parameters=None, seen=None):
    """Return the reader's fakes with the intent, the answer and the parameters reading set."""

    def reply(purpose, messages):
        if seen is not None:
            seen.append(purpose)
        if purpose == "answer" and answer is not None:
            return answer(messages) if callable(answer) else fake_answer(messages, text=answer)
        if purpose == "parameters" and parameters is not None:
            return parameters
        out = fake_intake(purpose, messages)
        if intent is not None and isinstance(out, dict) and "intent" in out:
            out["intent"] = intent
        return out

    return ScriptedLLM(reply)


class TestNamesNothing(unittest.TestCase):
    """Code tells a bare number from a message that says what it is about."""

    def test_numbers_and_sounds_name_nothing(self):
        """Numbers, signs and sounds name nothing; any word that could name a setting does."""
        for message in ("3?", "42", "hmm 70", "70?"):
            self.assertTrue(clarify.names_nothing(message), message)
        for message in ("3 doublets?", "Run it again with 2.", "What about 3?", "Is that a lot?"):
            self.assertFalse(clarify.names_nothing(message), message)

    def test_a_bare_message_offers_what_its_number_may_set(self):
        """A bare 3 may be the doublets; a unit says what a number is; a word names it."""
        item = clarify.bare_message("3?")
        self.assertEqual(item["quote"], "3")
        self.assertIn("n_doublets", item["could_be"])
        self.assertIsNone(clarify.bare_message("2 GWh"))
        self.assertIsNone(clarify.bare_message("3 doublets?"))
        self.assertEqual(clarify.bare_message("42")["could_be"], [])  # no setting holds it

    def test_the_setting_the_last_what_if_changed_is_the_referent(self):
        """A bare 3 right after a what-if on the doublets is that setting: left to the reading."""
        self.assertIsNone(clarify.bare_message("3?", earlier=["n_doublets"]))


class TestAnswerThenAsk(unittest.TestCase):
    """A reply that tells what the chat holds, then asks, is an answer."""

    HISTORY = "T8: «Could we cool with outside air instead of chillers?» (answered)"

    def test_what_the_chat_holds_then_a_question_is_an_answer(self):
        """C4.t10: the topic before the weather, then an offer: the answer, the offer a chip."""
        head = answer_then_offer(
            "We were discussing whether to replace the electric chillers with outside air "
            "cooling. Would you like to explore that option further?",
            self.HISTORY,
            "Sorry, back to the plant. What were we discussing before the weather?",
        )
        self.assertTrue(head.startswith("We were discussing whether to replace"))
        self.assertTrue(head.endswith("cooling."))

    def test_a_question_back_stays_one(self):
        """Saying what could not be read, then asking, is a question back, history or not."""
        said = "I cannot tell what you mean by that thing from before. Which do you mean?"
        self.assertIsNone(answer_then_offer(said, self.HISTORY, "Do that thing from before."))
        self.assertIsNone(answer_then_offer(said, "", "Do that thing from before."))


class Designed(unittest.TestCase):
    """One designed conversation, copied for each test."""

    @classmethod
    def setUpClass(cls):
        """Design the challenge district once."""
        cls.base = confirmed(Session())
        run(Agent(ScriptedLLM(fake_intake)), cls.base, FULL_BRIEF)

    def session(self):
        """Return a fresh copy of the designed conversation."""
        return copy.deepcopy(self.base)


class TestBareNumberAfterADesign(Designed):
    """A bare number is asked about with choices, read as a question or as a change."""

    def test_a_bare_number_read_as_a_question_is_asked_about(self):
        """A bare 3 read as a question: what is 3, with the doublets offered; no answer written."""
        s, seen = self.session(), []
        run(Agent(scripted(intent="question", seen=seen)), s, "3?")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertTrue(any("doublets" in c.lower() for c in s.last["choices"]), s.last["choices"])
        self.assertNotIn("answer", seen)
        self.assertNotIn("parameters", seen)

    def test_a_number_no_setting_holds_is_a_message_that_cannot_be_read(self):
        """A bare 42 after a design: the reply for an unreadable message asks; nothing guessed."""
        s, seen = self.session(), []
        run(Agent(scripted(intent="question", seen=seen)), s, "42")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("“42”", s.last["answer"])
        self.assertNotIn("answer", seen)

    def test_a_number_that_answers_a_question_asked_is_not(self):
        """A number typed while a question is open is read against it, not asked about again."""
        s = self.session()
        s.pending = {"kind": "options", "options": ["2", "3"], "question": "How many doublets?"}
        agent = Agent(scripted(intent="question"))
        list(agent.run(s, "3?"))
        self.assertNotEqual(s.last.get("answer"), None)
        self.assertNotIn("What should be 3", s.last.get("answer") or "")


class TestNothingToResolveTo(unittest.TestCase):
    """A run for words whose referent the chat does not hold is asked about, not run."""

    def test_the_setting_we_talked_about_in_a_new_chat(self):
        """U23: the answerer routes a design; the reading left the words open: asked, no run."""

        def routes(messages):
            out = fake_answer(messages, text="I will run the design now.")
            out["run"] = "design"
            return out

        open_item = {"quote": "the setting we talked about", "could_be": []}
        reading = {"changes": [], "doublets": [], "unsupported": [], "open": [open_item]}
        s, seen = confirmed(Session()), []
        agent = Agent(scripted(intent="question", answer=routes, parameters=reading, seen=seen))
        list(agent.run(s, "Use the setting we talked about."))
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("can't find a setting we talked about", s.last["answer"])
        self.assertIsNone(s.chosen)
        self.assertTrue(s.last["choices"])


if __name__ == "__main__":
    unittest.main()
