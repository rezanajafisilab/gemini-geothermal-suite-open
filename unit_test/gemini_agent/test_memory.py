"""Tests for what the user asks Dioscuri to remember, and the claim checker's rewrites (5 Nov).

A user's test on 5 Nov: "please call me by my name", a design, and the replies stopped using
the name; "do you remember my name?" lost its true sentence to the claim checker.
"""

import re
import tempfile
import unittest
from pathlib import Path

from gemini_agent import Agent, Session
from gemini_agent import answer as answering
from gemini_agent import claims
from gemini_agent import memory as remembered
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import fake_intake, run

SAID = "Hi! My name is Reza. Please call me by my name from now on."


def model(memory=None, answers=None, verdicts=None, quotes=None, fixed=None, seen=None):
    """Return a scripted model: given replies per purpose, the well-behaved fakes otherwise."""
    answers = list(answers or [])
    memory = list(memory or [])

    def reply(purpose, messages):
        if seen is not None:
            seen.append((purpose, messages))
        if purpose == "memory":
            return memory.pop(0) if memory else {"remember": "", "forget": []}
        if purpose == "answer" and answers:
            return answers.pop(0)
        if purpose == "claims" and verdicts is not None:
            listed = messages[-1]["content"].split("Reply:\n", 1)[1]
            n = len(re.findall(r"^\d+\. ", listed, re.M))
            return {"verdicts": (verdicts + ["supported"] * n)[:n]}
        if purpose == "claims_quote" and quotes is not None:
            return {"quotes": quotes, "fixed": fixed or [""] * len(quotes)}
        return fake_intake(purpose, messages)

    return ScriptedLLM(reply, model="qwen3.5:9b")


def answer(text, used=("project",)):
    """Return an answerer's JSON reply."""
    return {
        "understood": "x",
        "kind": "answer",
        "scope": "project",
        "answer": text,
        "used": list(used),
        "follow_ups": [],
        "run": "none",
    }


class TestChecked(unittest.TestCase):
    """Code keeps a note only when it comes from the message, is short and is new."""

    def test_a_note_from_the_message_is_kept(self):
        """A note from the message is kept."""
        self.assertEqual(remembered.checked("call the user Reza", SAID, []), "call the user Reza")

    def test_a_note_with_nothing_of_the_message_is_dropped(self):
        """A note with nothing of the message is dropped."""
        self.assertEqual(remembered.checked("call the user Sam", SAID, []), "")
        self.assertEqual(remembered.checked("", SAID, []), "")

    def test_a_note_kept_already_is_not_kept_twice(self):
        """A note kept already is not kept twice."""
        old = [remembered.Note("Call the user Reza.", SAID)]
        self.assertEqual(remembered.checked("call the user Reza", SAID, old), "")

    def test_read_returns_the_note_and_what_it_cancels(self):
        """Read returns the note and what it cancels."""
        notes = [remembered.Note("call the user Reza", SAID)]
        llm = model(memory=[{"remember": "call the user Ali", "forget": [1, 7]}])
        keep, drop, call, error = remembered.read("Actually, my name is Ali.", notes, llm)
        self.assertEqual((keep, drop, error), ("call the user Ali", [0], ""))
        self.assertIsNotNone(call)


class TestForget(unittest.TestCase):
    """A note goes only for a message that touches it (5 Nov: "go ahead" dropped the name)."""

    NOTE = remembered.Note("call the user Sam", "Hi! My name is Sam. Please call me Sam.")

    def test_a_go_ahead_drops_nothing(self):
        """A go-ahead the model read as a cancel keeps the note."""
        llm = model(memory=[{"remember": "", "forget": [1]}])
        self.assertEqual(remembered.read("Looks right, go ahead.", [self.NOTE], llm)[:2], ("", []))

    def test_a_request_to_stop_drops_it(self):
        """A request to stop or change it shares a word with the note, and drops it."""
        self.assertTrue(remembered.touches("Please stop calling me Sam.", self.NOTE))
        self.assertTrue(remembered.touches("Actually, my name is Alex.", self.NOTE))
        self.assertFalse(remembered.touches("yes, run it", self.NOTE))

    def test_the_same_note_again_changes_nothing(self):
        """Saying the same thing again neither drops nor adds."""
        llm = model(memory=[{"remember": "call the user Sam", "forget": [1]}])
        self.assertEqual(remembered.read("Call me Sam.", [self.NOTE], llm)[:2], ("", []))


class TestStore(unittest.TestCase):
    """A project's notes are one file; every chat of the project reads them."""

    def test_save_read_forget(self):
        """Save read forget."""
        with tempfile.TemporaryDirectory() as d:
            store = remembered.Store(d)
            self.assertEqual(store.notes("challenge"), [])
            a, b = remembered.Note("call the user Reza", SAID), remembered.Note(
                "answer briefly", "x"
            )
            store.save("challenge", [a, b])
            self.assertEqual([n.text for n in store.notes("challenge")], [a.text, b.text])
            self.assertEqual(store.notes("other"), [])
            self.assertEqual(store.forget("challenge", a.id), 1)
            self.assertEqual([n.id for n in store.notes("challenge")], [b.id])
            self.assertEqual(store.forget("challenge"), 1)
            self.assertFalse(any(Path(d).iterdir()))

    def test_a_project_id_cannot_leave_the_folder(self):
        """A project id cannot leave the folder."""
        with tempfile.TemporaryDirectory() as d:
            store = remembered.Store(Path(d) / "memory")
            store.save("../../evil", [remembered.Note("call the user Reza", SAID)])
            made = list((Path(d) / "memory").iterdir())
            self.assertEqual(len(made), 1)
            self.assertNotIn("/", made[0].name.replace(".json", ""))


class TestAgentRemembers(unittest.TestCase):
    """The agent keeps the note, puts it in every reply's context and shows a row for it."""

    def test_a_note_is_kept_and_reaches_the_next_answer(self):
        """A note is kept and reaches the next answer."""
        seen = []
        llm = model(
            memory=[{"remember": "call the user Reza", "forget": []}],
            answers=[
                answer("Hello Reza, noted."),
                answer("Reza, heat costs what the design says."),
            ],
            seen=seen,
        )
        agent, s = Agent(llm, check_claims="off"), Session()
        events = run(agent, s, SAID)
        rows = [e for e in events if e["type"] == "STEP_FINISHED" and e["stepName"] == "memory"]
        self.assertEqual(rows[0]["metadata"]["remembered"], "call the user Reza")
        self.assertFalse(rows[0]["metadata"]["shared"])
        self.assertEqual([n["text"] for n in s.notes], ["call the user Reza"])
        custom = [e for e in events if e["type"] == "CUSTOM" and e["name"] == "memory"]
        self.assertEqual(custom[0]["value"]["notes"][0]["text"], "call the user Reza")
        seen.clear()
        run(agent, s, "How are you today?")
        prompts = [m for p, m in seen if p == "answer"]
        self.assertTrue(prompts)
        text = "\n".join(x["content"] for x in prompts[-1])
        self.assertIn("call the user Reza", text)
        self.assertIn('A "notes" block holds what the user asked you to remember', text)

    def test_without_a_note_the_rule_line_stays_out(self):
        """Without a note the rule line stays out."""
        seen = []
        llm = model(answers=[answer("Hello.")], seen=seen)
        run(Agent(llm, check_claims="off"), Session(), "How are you today?")
        text = "\n".join(x["content"] for p, m in seen if p == "answer" for x in m)
        self.assertNotIn('"notes" block', text)

    def test_a_project_store_is_shared_by_its_chats(self):
        """A project store is shared by its chats."""
        with tempfile.TemporaryDirectory() as d:
            store = remembered.Store(d)
            llm = model(memory=[{"remember": "call the user Reza", "forget": []}])
            agent = Agent(llm, check_claims="off", memory=store)
            first, second = Session(thread_id="t1"), Session(thread_id="t2")
            run(agent, first, SAID)
            self.assertEqual(first.notes, [])  # kept with the project, not the chat
            self.assertEqual(agent._notes(second)[0].text, "call the user Reza")
            block = agent._notes_block(second)
            self.assertIn("another chat of this project", block.text)

    def test_a_cancelled_note_is_forgotten(self):
        """A cancelled note is forgotten."""
        llm = model(
            memory=[
                {"remember": "call the user Reza", "forget": []},
                {"remember": "", "forget": [1]},
            ]
        )
        agent, s = Agent(llm, check_claims="off"), Session()
        run(agent, s, SAID)
        events = run(agent, s, "Please stop calling me Reza.")
        self.assertEqual(s.notes, [])
        rows = [e for e in events if e["type"] == "STEP_STARTED" and e["stepName"] == "memory"]
        self.assertEqual(rows[0]["metadata"]["label"], "Forget: call the user Reza")


class TestClaimsMend(unittest.TestCase):
    """The checker mends a sentence that is close but worded wrong, rather than remove it."""

    BLOCKS = [
        answering.Block("project", "project", "Heat demand 111.7 GWh a year; peak 30 MW."),
        answering.Block(
            "turns",
            "history",
            "The user's earlier messages:\nT1: «Hi! My name is Reza. Please call me by my name.»",
        ),
    ]

    def test_a_close_sentence_is_reworded(self):
        """A close sentence is reworded."""
        text = "The district needs about 111.7 GWh of heat a year, with a peak of 35 MW."
        llm = model(
            verdicts=["unsupported"],
            quotes=["Heat demand 111.7 GWh a year; peak 30 MW."],
            fixed=["The district needs about 111.7 GWh of heat a year, with a peak of 30 MW."],
        )
        found = claims.check(llm, text, self.BLOCKS, ["project"])
        self.assertEqual(found.removed, [])
        self.assertEqual(len(found.reworded), 1)
        self.assertIn("peak of 30 MW", found.text)
        self.assertNotIn("35 MW", found.text)
        self.assertEqual(found.meta()["reworded"], 1)

    def test_a_rewrite_with_a_number_from_nowhere_is_refused(self):
        """A rewrite with a number from nowhere is refused."""
        text = "The district needs about 111.7 GWh of heat a year, with a peak of 35 MW."
        llm = model(
            verdicts=["unsupported"],
            quotes=["Heat demand 111.7 GWh a year; peak 30 MW."],
            fixed=["The district needs about 111.7 GWh of heat a year, with a peak of 32 MW."],
        )
        found = claims.check(llm, text, self.BLOCKS, ["project"])
        self.assertEqual(found.reworded, [])
        self.assertEqual(found.removed, [text])

    def test_the_conversation_is_never_evidence(self):
        """The conversation is never evidence."""
        blocks = [answering.Block("history", "history", "User: the peak is 99 MW.\nDioscuri: ok")]
        self.assertEqual(claims.evidence(["The peak is 99 MW."], blocks), "")

    def test_notes_are_evidence(self):
        """Notes are evidence."""
        notes = answering.Block(
            "notes", "notes", "- call the user Reza (the user wrote «I'm Reza»)"
        )
        self.assertIn("Reza", claims.evidence(["I remember your name, Reza."], [notes]))

    def test_notes_are_read_first(self):
        """Notes are read first."""
        notes = answering.Block("notes", "notes", "- call the user Reza", remembered.TITLE)
        order = claims.sources([*self.BLOCKS, notes], [])
        self.assertEqual(order[0].id, "notes")


if __name__ == "__main__":
    unittest.main()
