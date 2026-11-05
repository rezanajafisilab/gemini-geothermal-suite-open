"""Flow fixes from the eval runs of 4 Nov (qwen3.5:9b and 4b; chat, unclear and long chats).

A clarifying reply claimed a run, an unreadable message was refused, called nonsense or run, a
question asked while the inputs card waited was answered a turn late, the claim checker left
replies empty, and the conversation itself was no source. The models are scripted: each test
gives the readings a model made in those runs and checks what code does with them. (The eval's
own check of a reply's words is in ``test_eval_says.py``.)
"""

import re
import unittest

from gemini_agent import Agent, Session, claims, parameters
from gemini_agent.answer import ACTION_CLAIM, Block
from gemini_agent.llm import ScriptedLLM
from gemini_agent.reporter import RUN_OPTION
from unit_test.gemini_agent.test_agent import FULL_BRIEF, custom, fake_intake, run


def said_in(messages) -> str:
    """Return the message a reading call reads (after the chat's thread)."""
    return messages[-1]["content"].split("Message: ")[-1].split("Reply: ")[-1]


def scripted(**by_purpose):
    """Return a scripted model: ``purpose=f(messages)`` or a dict, the well-behaved fakes else."""

    def reply(purpose, messages):
        got = by_purpose.get(purpose)
        if callable(got):
            got = got(messages)
        if got is not None:
            return got
        return fake_intake(purpose, messages)

    return ScriptedLLM(reply, model="qwen3.5:9b")


def designed(llm) -> tuple:
    """Return an agent on ``llm`` and a chat whose challenge design is done (the toy model)."""
    agent = Agent(llm)
    s = Session()
    run(agent, s, FULL_BRIEF)
    assert s.chosen is not None
    return agent, s


def answer_json(text, used=("project",), kind="answer"):
    """Return an answerer's JSON reply."""
    return {
        "understood": "x",
        "kind": kind,
        "scope": "project",
        "answer": text,
        "options": [],
        "used": list(used),
        "follow_ups": [],
    }


class TestNoRunClaimInAQuestion(unittest.TestCase):
    """Fix 1: a clarifying reply never says a search ran for the message it answers."""

    def test_the_same_search_again_claims_no_run(self):
        """Another attempt confirmed unchanged: the same answer, with no "I ran" in it."""
        llm = scripted(
            intake=lambda m: dict(fake_intake("intake", m), intent="design"),
            route={"run_design": True},
        )
        agent, s = designed(llm)
        run(agent, s, "do another design attempt")
        self.assertEqual(s.pending["kind"], "confirm")
        run(agent, s, answers={"confirm": RUN_OPTION})
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("same inputs give the same answer", s.last["answer"])
        self.assertIsNone(ACTION_CLAIM.search(s.last["answer"]))

    def test_a_count_asked_for_without_one_is_asked(self):
        """Use more doublets, read as a new design: "by how much?", not the last card again."""
        llm = scripted(
            parameters=lambda m: (
                {"changes": [{"key": "n_doublets", "value": 2, "quote": "more doublets"}]}
                if said_in(m) == "Use more doublets."
                else None
            ),
            needs={"needs": "new_design_run"},
        )
        agent, s = designed(llm)
        ev = run(agent, s, "Use more doublets.")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIsNone(custom(ev, "confirm_inputs"))
        self.assertIn("?", s.last["answer"])  # asked (with choices since the clarify merge)
        self.assertIsNone(ACTION_CLAIM.search(s.last["answer"]))
        self.assertEqual(s.pending["kind"], "choice")
        # A count goes one at a time: 2 and 3 doublets from 1, not 1.15.
        amounts = [re.findall(r"\d+(?:\.\d+)?", str(o))[-1] for o in s.pending["options"]]
        self.assertEqual(amounts, ["2", "3"])

    def test_an_option_without_an_amount_is_asked_not_rerun(self):
        """Add solar panels, as a new design: no amount, so asked; the card does not open."""
        llm = scripted(
            parameters=lambda m: (
                {
                    "changes": [{"key": "solar_mwp", "value": 0, "quote": "solar panels"}],
                    "unsupported": [{"what": "solar panels", "quote": "solar panels"}],
                }
                if said_in(m) == "Add solar panels."
                else None
            ),
            needs={"needs": "new_design_run"},
        )
        agent, s = designed(llm)
        n = len(s.ledger)
        ev = run(agent, s, "Add solar panels.")
        self.assertIsNone(custom(ev, "confirm_inputs"))
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("?", s.last["answer"])
        self.assertEqual(len(s.ledger), n)

    def test_an_option_without_an_amount_is_not_called_unmodelled(self):
        """A store asked for with no size, read as unsupported too: asked, not "no store"."""
        message = "Add a heat store to the design."
        llm = scripted(
            intake=lambda m: dict(fake_intake("intake", m), intent="what_if"),
            parameters=lambda m: (
                {
                    "changes": [{"key": "storage_mwh", "value": 0, "quote": "heat store"}],
                    "unsupported": [{"what": "heat store", "quote": "heat store"}],
                    "steps": [{"do": "what_if", "quote": message, "changes": []}],
                }
                if said_in(m) == message
                else None
            ),
            needs={"needs": "new_design_run"},
        )
        agent, s = designed(llm)
        run(agent, s, message)
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("heat store", s.last["answer"])
        self.assertIn("?", s.last["answer"])
        self.assertNotIn("no input", s.last["answer"])

    def test_a_reading_slip_is_not_shown_as_a_refused_value(self):
        """A number the words do not give is the reading's slip, not the user's value."""
        from gemini_agent.agent import refused_on_card

        reading = parameters.Reading(dropped=["n_doublets=2: its number is not in the quote"])
        self.assertEqual(refused_on_card(reading), ({}, {}, []))


class TestUnreadable(unittest.TestCase):
    """Fix 2: one clarifying reply for a message no request can be read from."""

    def test_the_planner_finds_it_unclear_nothing_runs(self):
        """A bare number after a design ("uh 15" read as a 15 MWh store): asked, not run."""
        llm = scripted(
            intake=lambda m: dict(fake_intake("intake", m), intent="what_if"),
            parameters=lambda m: (
                {
                    "changes": [{"key": "storage_mwh", "value": 15, "quote": "15"}],
                    "unclear": True,
                }
                if said_in(m) == "uh 15"
                else None
            ),
        )
        agent, s = designed(llm)
        n, calls = len(s.ledger), len(llm.calls)
        ev = run(agent, s, "uh 15")
        self.assertEqual(len(s.ledger), n)
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("“uh 15”", s.last["answer"])
        self.assertTrue(s.last["answer"].endswith("?"))
        self.assertEqual(s.last["parameters"]["changes"], {})
        self.assertTrue(s.last["parameters"]["unclear"])
        self.assertEqual(s.pending["kind"], "choice")
        self.assertGreaterEqual(len(s.pending["options"]), 2)
        self.assertIsNone(custom(ev, "result"))
        purposes = [c.purpose for c in llm.calls[calls:]]
        self.assertNotIn("options", purposes)  # the plant's options are not read again
        self.assertNotIn("needs", purposes)

    def test_a_cut_off_message_the_answerer_finds_unclear_is_asked(self):
        """Before a design, the answerer reads no request: the same reply, not a refusal."""
        llm = scripted(
            intake=lambda m: dict(fake_intake("intake", m), relevant=False, intent="other"),
            answer=answer_json("You stopped mid-sentence. What did you mean?", kind="unclear"),
        )
        s = Session()
        run(Agent(llm), s, "I was wondering whether the")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("“I was wondering whether the”", s.last["answer"])
        self.assertNotIn("outside what I do", s.last["answer"])
        self.assertEqual(s.pending["kind"], "choice")

    def test_a_real_off_topic_request_is_still_declined(self):
        """The weather is refused politely, as before."""
        s = Session()
        run(Agent(ScriptedLLM(fake_intake)), s, "What will the weather be in Paris tomorrow?")
        self.assertEqual(s.last["behaviour"], "refuse")

    def test_an_unclear_reading_keeps_nothing(self):
        """Code empties a reading the model marks unclear: every change goes to dropped."""
        raw = {
            "changes": [{"key": "storage_mwh", "value": 70, "quote": "70"}],
            "steps": [{"do": "what_if", "quote": "70", "changes": []}],
            "unclear": True,
        }
        out = parameters.check(raw, "hmm 70", designed=True)
        self.assertTrue(out.unclear)
        self.assertEqual((out.changes, out.steps), ({}, []))
        self.assertTrue(any("no readable request" in d for d in out.dropped))
        self.assertIn("unclear", parameters.SCHEMA["required"])
        self.assertFalse(parameters.wants_options(out, asks_change=True))


class TestCardStaysOpen(unittest.TestCase):
    """Fix 3: a question asked while the inputs card waits is answered then; "go ahead" runs."""

    def test_a_side_question_is_answered_and_the_card_waits(self):
        """No design yet: the card, a question read as a design, then "go ahead" runs it."""
        llm = scripted(
            intake=lambda m: dict(fake_intake("intake", m), intent="design"),
            route={"run_design": False},
        )
        agent, s = Agent(llm), Session()
        run(agent, s, FULL_BRIEF, confirm=False)
        self.assertEqual(s.pending["kind"], "confirm")
        ev = run(agent, s, "Tell me the flow cap per doublet first", confirm=False)
        self.assertIsNone(custom(ev, "confirm_inputs"))
        self.assertEqual(s.last["behaviour"], "answer")
        self.assertEqual(s.pending["kind"], "confirm")
        run(agent, s, "Looks right, go ahead.", confirm=False)
        self.assertEqual(s.last["behaviour"], "design")
        self.assertIsNotNone(s.chosen)

    def test_a_question_before_a_design_is_answered_not_carded(self):
        """A question with nothing to run, before a design: answered, no inputs card."""
        llm = scripted(intake=lambda m: dict(fake_intake("intake", m), intent="design"))
        s = Session()
        ev = run(Agent(llm), s, "We can drill up to five doublets, can't we?", confirm=False)
        self.assertIsNone(custom(ev, "confirm_inputs"))
        self.assertEqual(s.last["behaviour"], "answer")
        self.assertIsNone(s.pending)

    def test_a_design_asked_as_a_question_still_opens_the_card(self):
        """The answerer judges "can you design it?" asks for a run: the card opens."""
        llm = scripted(
            intake=lambda m: dict(fake_intake("intake", m), intent="design"),
            answer=dict(answer_json("I will run it."), run="design"),
        )
        s = Session()
        run(Agent(llm), s, "Can you design heating and cooling for this district?", confirm=False)
        self.assertEqual(s.pending["kind"], "confirm")


class TestClaimsKeepWhatIsTrue(unittest.TestCase):
    """Fix 4: the checker reads the design's own facts; a reply is never left empty."""

    @staticmethod
    def checker(messages):
        """Return verdicts: supported only when the sources hold a design's full block."""
        content = messages[-1]["content"]
        n = len(re.findall(r"^\d+\. ", content.split("Reply:\n", 1)[1], re.M))
        full = "Checks: " in content.split("Reply:\n", 1)[0]
        return {"verdicts": ["supported" if full else "unsupported"] * n}

    def test_the_designs_own_facts_back_its_statements(self):
        """A question no pattern takes for one about a design: its facts still reach the check."""
        text = "The store moves spare summer heat into the winter. It trims the boiler's work."
        llm = scripted(
            answer=lambda m: answer_json(text) if "store" in said_in(m) else None,
            claims=self.checker,
            claims_quote={"quotes": ["", ""]},
        )
        agent, s = designed(llm)
        run(agent, s, "What did the store change?")
        self.assertEqual(s.last.get("claims_removed"), [])
        self.assertIn("trims the boiler", s.last["answer"])

    def test_an_emptied_reply_shows_the_checked_template_and_says_so(self):
        """Every sentence removed: the checked template with a note, never "I won't guess"."""
        text = "The store moves spare summer heat into the winter. It trims the boiler's work."
        llm = scripted(
            answer=lambda m: answer_json(text) if "store" in said_in(m) else None,
            claims=lambda m: {"verdicts": ["unsupported", "unsupported"]},
            claims_quote={"quotes": ["", ""]},
        )
        agent, s = designed(llm)
        run(agent, s, "What did the store change?")
        self.assertNotIn("won't guess", s.last["answer"])
        self.assertIn("I left out 2 more statements", s.last["answer"])
        self.assertNotIn("trims the boiler", s.last["answer"])
        # About a design the words name: that design's checked summary is what stands.
        run(agent, s, "What did the store change in the cheapest one?")
        cheapest = next(e for e in s.candidates if "cost" in e.alternative.picks)
        self.assertIn(cheapest.alternative.code, s.last["answer"])
        self.assertIn("I left out 2 more statements", s.last["answer"])


class TestTheChatIsASource(unittest.TestCase):
    """Fix 5: what was said in the chat is a source for questions about the chat."""

    def test_the_checker_reads_dioscuris_earlier_words(self):
        """Dioscuri's earlier replies go to the checker, as what was said, first when used."""
        thread = (
            "This chat has had 2 turns before this message (T1 to T2).\n"
            "The last exchanges:\nUser (T2): What is the reinjection temperature?\n"
            "Dioscuri: The reinjection temperature is 61.6 °C."
        )
        blocks = [
            Block("project", "project", "The district."),
            Block("A1", "design", "1D-HP-EC, reinjection 61.6 °C."),
            Block("history", "history", thread, "the conversation so far"),
        ]
        used = claims.sources(blocks, ["history"], "I said 61.6 °C.")
        self.assertEqual(used[0].id, "history")
        self.assertIn("Dioscuri: The reinjection temperature is 61.6 °C.", used[0].text)
        self.assertIn("prove only that it said them", used[0].render())
        last = claims.sources(blocks, ["project"], "I said 61.6 °C.")
        self.assertEqual(last[-1].id, "history")

    def test_a_statement_about_what_was_said_is_checked_not_asked(self):
        """A statement of what Dioscuri said: no "which design?", but a correction."""
        message = "Earlier you told me the reinjection temperature was 7 °C."
        for intent in ("question", "design"):  # the small reader's two readings of it
            llm = scripted(
                intake=lambda m, i=intent: dict(fake_intake("intake", m), intent=i),
                parameters=lambda m: (
                    {"changes": [], "premises": ["the reinjection temperature was 7 °C"]}
                    if said_in(m) == message
                    else None
                ),
                needs={"needs": "about_one_existing_design"},
                which_design={"design": "unclear"},
                route={"run_design": False},
            )
            agent, s = designed(llm)
            run(agent, s, message)
            self.assertIsNone(s.pending, intent)
            self.assertEqual(s.last["behaviour"], "answer")
            self.assertIn("Not quite", s.last["answer"])

    def test_the_which_design_question_is_the_recorded_reply(self):
        """When the user is asked which design, that question is the turn's reply."""
        llm = scripted(
            parameters=lambda m: {"changes": []} if said_in(m) == "And its cost?" else None,
            needs={"needs": "about_one_existing_design"},
            which_design={"design": "unclear"},
        )
        agent, s = designed(llm)
        # No design under discussion: with one, the model's "unclear" keeps it (5 Nov).
        s.thread.focus_id = ""
        run(agent, s, "And its cost?")
        self.assertEqual(s.pending["kind"], "which_design")
        self.assertEqual(s.last["answer"], "Which design is your question about?")
        self.assertEqual(s.history[-1]["reply"], "Which design is your question about?")


if __name__ == "__main__":
    unittest.main()


class TestWhatIfKeepsTheDesign(unittest.TestCase):
    """5 Nov: "What if gas cost 45 €/MWh?" was asked "which design?" after a design."""

    def test_unclear_design_keeps_the_one_under_discussion(self):
        """The model cannot tell, the message names none: the design under discussion stands."""
        llm = scripted(
            parameters=lambda m: {"changes": []} if said_in(m) == "And its cost?" else None,
            needs={"needs": "about_one_existing_design"},
            which_design={"design": "unclear"},
        )
        agent, s = designed(llm)
        self.assertTrue(s.thread.focus_id)
        run(agent, s, "And its cost?")
        self.assertNotEqual((s.pending or {}).get("kind"), "which_design")
        self.assertNotEqual(s.last["answer"], "Which design is your question about?")
