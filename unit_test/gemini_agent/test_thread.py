"""Tests for the chat's thread (4 Nov): kept by code, given to every reading, guarded prompts."""

import unittest

from gemini_agent import Agent, Session, parameters
from gemini_agent.answer import Block, blocks_tokens, fit
from gemini_agent.intake import messages_for
from gemini_agent.llm import (
    ContextOverflow,
    OllamaLLM,
    ScriptedLLM,
    estimate_tokens,
    prompt_tokens,
)
from gemini_agent.thread import Thread, designs_named, flat
from unit_test.gemini_agent.test_agent import FULL_BRIEF, custom, fake_intake, run


class TestThread(unittest.TestCase):
    """What code keeps of a conversation, and how a prompt shows it."""

    def test_note_keeps_lines_focus_list_question(self):
        """Each turn adds one line; the focus, the list and the open question are kept."""
        t = Thread()
        t.note(
            1,
            "Design it",
            "I recommend **A1** · 1D-HP-EC: 75.7 €/MWh.",
            "ran a search",
            ("A1 · 1D-HP-EC (best overall)", "A1 · 1D-HP-EC"),
        )
        t.note(
            2,
            "and the cheapest?",
            "A2 costs 70 €/MWh; A1 costs 75.7.",
            "answered",
            None,
            ["A2 · 1D-BO (cheapest)", "A1 · 1D-HP-EC (best overall)"],
            "named",
        )
        self.assertEqual(len(t.lines), 2)
        self.assertIn("T2 user: «and the cheapest?»", t.lines[1])
        self.assertIn("75.7 €/MWh", t.lines[0])
        self.assertNotIn("**", t.lines[0])
        self.assertEqual(t.focus, "A1 · 1D-HP-EC (best overall)")  # None keeps the focus
        self.assertEqual(t.shown[1], "A1 · 1D-HP-EC (best overall)")
        t.note(
            3,
            "what does it cost?",
            "",
            "asked a question back",
            None,
            [],
            "",
            "which design. Options: 1. A1; 2. A2",
        )
        self.assertIn("Options", t.question)
        self.assertEqual(Thread.from_dict(t.to_dict()), t)
        self.assertEqual(Thread.from_dict(None), Thread())

    def test_lines_are_kept_and_a_prompt_shows_the_last_and_the_first(self):
        """The session keeps the lines; a prompt shows the last twelve and, asked, the first."""
        t = Thread()
        for n in range(1, 20):
            t.note(n, f"q{n}", f"a{n}", "answered")
        self.assertEqual(len(t.lines), 19)
        text = t.text([{"user": "q19", "reply": "a19"}], exchanges=1)
        self.assertNotIn("T6 user", text)
        self.assertIn("T7 user", text)
        text = t.text([{"user": "q19", "reply": "a19"}], exchanges=1, lines=3, first=2)
        self.assertIn("T1 user: «q1»", text)
        self.assertIn("T2 user", text)
        self.assertNotIn("T3 user", text)
        self.assertIn("…\nT16 user", text)
        short = t.text([{"user": "q19", "reply": "a19"}], exchanges=1, lines=3, first=2, limit=200)
        self.assertNotIn("T16 user", short)  # the middle goes before the opening

    def test_text_shows_exchanges_and_earlier_lines_within_a_limit(self):
        """The last exchanges in words, earlier turns as lines; a limit cuts the oldest first."""
        t = Thread()
        history = []
        for n in range(1, 9):
            t.note(n, f"question {n} " + "x " * 40, f"reply {n} " + "y " * 80, "answered")
            history.append(
                {"user": f"question {n} " + "x " * 40, "reply": f"reply {n} " + "y " * 80}
            )
        t.focus = "W1 · 1D-HP-EC (what-if: gas price 45 €/MWh)"
        text = t.text(history[-6:], exchanges=3)
        self.assertIn("Earlier turns", text)
        self.assertIn("The last exchanges", text)
        self.assertIn("User (T8): question 8", text)
        self.assertIn("Design under discussion: W1", text)
        self.assertNotIn("User (T5): question 5", text)  # older turns are one line each
        self.assertIn("T5 user", text)
        short = t.text(history[-6:], exchanges=3, limit=900)
        self.assertLessEqual(len(short), 900)
        self.assertIn("question 8", short)  # the latest stays
        self.assertIn("Design under discussion", short)
        self.assertEqual(Thread().text([]), "")

    def test_designs_named_in_order(self):
        """A reply's designs in the order it names them, by handle or by a code standing alone."""
        names = {
            "A1": "A1 · 1D-HP-EC (best)",
            "1D-HP-EC": "A1 · 1D-HP-EC (best)",
            "A2": "A2 · 1D-BO (cheapest)",
            "1D-BO": "A2 · 1D-BO (cheapest)",
        }
        said = "The cheapest is 1D-BO (A2); A1 costs more. CO2 is lower in A1."
        self.assertEqual(
            designs_named(said, names), ["A2 · 1D-BO (cheapest)", "A1 · 1D-HP-EC (best)"]
        )
        self.assertEqual(designs_named("1D-BO-EC@3500 only", names), [])

    def test_flat(self):
        """One line, no Markdown or tables, cut at a word."""
        self.assertEqual(
            flat("**Yes.**\n\n| a | b |\n|---|---|\nNext   line", 100), "Yes. Next line"
        )
        self.assertEqual(flat("one two three four", 10), "one two…")


class TestGuard(unittest.TestCase):
    """Prompts are measured against the window before they are sent."""

    def test_estimate_counts_digits_as_tokens(self):
        """Digits are a token each; prose about 3.6 characters a token."""
        self.assertGreater(estimate_tokens("1234567890"), estimate_tokens("abcdefghij"))
        self.assertAlmostEqual(estimate_tokens("word " * 100), 500 / 3.6, delta=3)
        self.assertGreater(prompt_tokens([{"content": "x"}, {"content": "y"}]), 10)

    def test_overflow_is_refused_not_sent(self):
        """A prompt that does not fit the window is refused before Ollama can cut its start."""
        llm = OllamaLLM(model="none", num_ctx=1024)

        def no_server(**kw):  # pragma: no cover - the guard must stop it first
            raise AssertionError("sent")

        llm._client.chat = no_server
        with self.assertRaises(ContextOverflow) as caught:
            llm.text("answer", [{"role": "user", "content": "9" * 2000}], 100)
        self.assertIn("does not fit", str(caught.exception))
        self.assertFalse(caught.exception.call.ok)

    def test_fit_gives_up_the_least_useful_first(self):
        """Passages first, then the other designs cut, then the history cut to its end."""
        current = Block("A1", "design", "A1 values " + "1" * 800)
        other = Block("A2", "design", "A2 values " + "2" * 800)
        hist = Block("history", "history", "old " * 400 + "LATEST TURN")
        docs = [Block(f"doc{i}", "doc", "d" * 2000) for i in range(3)]
        blocks = [Block("self", "self", "me"), current, other, hist] + docs
        kept = fit(blocks, blocks_tokens(blocks) - 400)
        self.assertEqual([b.id for b in kept], ["self", "A1", "A2", "history", "doc0", "doc1"])
        kept = fit(blocks, 1200)
        ids = [b.id for b in kept]
        self.assertIn("A1", ids)
        self.assertIn("history", ids)
        self.assertNotIn("doc0", ids)
        self.assertTrue(next(b for b in kept if b.id == "history").text.endswith("LATEST TURN"))
        self.assertEqual(next(b for b in kept if b.id == "A1").text, current.text)  # never cut


class TestReadingsGetTheThread(unittest.TestCase):
    """Every reading call sees the thread; without one its messages are as before."""

    def test_reading_messages_unchanged_without_a_thread(self):
        """The fine-tuned models' form stays exactly as trained when there is no history."""
        now = {"heat_return_c": 40.0}
        before = parameters.reading_messages("hello", now, "A1", "A1 x", short=True)
        self.assertNotIn("Conversation so far", before[1]["content"])
        self.assertTrue(before[1]["content"].endswith("\n\nMessage: hello"))
        after = parameters.reading_messages("and 45 °C?", now, "A1", "A1 x", True, "T1 user: …")
        self.assertIn(
            "Conversation so far:\nT1 user: …\n\nMessage: and 45 °C?", after[1]["content"]
        )
        self.assertEqual(messages_for("hi")[-1]["content"], "hi")
        self.assertIn("Message: hi", messages_for("hi", "T1 …")[-1]["content"])

    def test_open_question_reading(self):
        """A typed reply answers the question with an option, its own words, or not at all."""
        llm = ScriptedLLM(
            [
                {"answers": True, "option": 2, "value": ""},
                {"answers": True, "option": 0, "value": "2 GWh"},
                {"answers": False, "option": 0, "value": ""},
                {"answers": True, "option": 9, "value": ""},
            ]
        )
        ask = ("Which design?", ["A1", "A2"])
        self.assertEqual(parameters.answers_question("the second", *ask, llm)[0], (2, ""))
        self.assertEqual(parameters.answers_question("2 GWh", *ask, llm)[0], (0, "2 GWh"))
        self.assertIsNone(parameters.answers_question("what is N-1?", *ask, llm)[0])
        self.assertIsNone(parameters.answers_question("x", *ask, llm)[0])  # no such option


class TestAgentKeepsTheThread(unittest.TestCase):
    """Across turns, with scripted models."""

    def test_thread_is_noted_saved_and_sent_to_the_reader(self):
        """After a design and a question, the reader's next prompt holds both turns."""
        seen = []

        def script(purpose, messages):
            seen.append((purpose, messages[-1]["content"]))
            return fake_intake(purpose, messages)

        agent = Agent(ScriptedLLM(script))
        s = Session()
        run(agent, s, FULL_BRIEF)
        self.assertEqual(len(s.thread.lines), 1)
        self.assertIn("ran a design search", s.thread.lines[0])
        self.assertTrue(s.thread.focus)
        run(agent, s, "hello there, what next")
        intake_prompts = [c for p, c in seen if p == "intake"]
        self.assertIn("Earlier in this chat", intake_prompts[-1])
        self.assertIn("User (T1): " + FULL_BRIEF, intake_prompts[-1])
        self.assertIn("Design under discussion: A1", intake_prompts[-1])
        again = Session.from_dict(s.to_dict())
        self.assertEqual(again.thread, s.thread)

    def test_typed_reply_answers_the_which_design_question(self):
        """A typed "the cheapest one" after "which design?" picks it and answers the question."""
        agent = Agent(ScriptedLLM(fake_intake))
        s = Session()
        run(agent, s, FULL_BRIEF)
        s.pending = {
            "kind": "which_design",
            "intent": "question",
            "message": "What does it cost?",
            "language": "en",
            "options": ["A1 · best overall (x)", "A2 · cheapest (y)"],
            "ids": {},
        }
        calls = []

        def script(purpose, messages):
            calls.append(purpose)
            if purpose == "open_question":
                return {"answers": True, "option": 2, "value": ""}
            return fake_intake(purpose, messages)

        agent = Agent(ScriptedLLM(script))
        events = run(agent, s, "the cheaper of the two please")
        self.assertEqual([c for c in calls if c != "memory"][0], "open_question")
        self.assertEqual(s.last.get("answered"), ["design"])
        self.assertIsNone(custom(events, "clarification"))


if __name__ == "__main__":
    unittest.main()


class TestDesignMeant(unittest.TestCase):
    """Before "which design?" the model may say from the thread which design is meant."""

    def test_design_meant_reading(self):
        """A design's name from the list, "unclear" (0: ask) or "several" (-1: nothing to ask)."""
        llm = ScriptedLLM(
            [{"design": "A2"}, {"design": "unclear"}, {"design": "several"}, {"design": "Z9"}]
        )
        options = ["A1 · best overall (x)", "A2 · cheapest (y)"]
        self.assertEqual(parameters.design_meant("and the cheap one?", options, llm)[0], 2)
        self.assertEqual(parameters.design_meant("the other one?", options, llm)[0], 0)
        self.assertEqual(parameters.design_meant("what did we see?", options, llm)[0], -1)
        self.assertEqual(parameters.design_meant("x", options, llm)[0], 0)

    def test_the_agent_answers_about_the_design_meant(self):
        """When the model names one, no question back: the answer is about that design."""
        from unit_test.gemini_agent.test_naming import designed

        agent, s = designed()
        picks = {e.alternative.code for e in s.candidates if e.alternative.picks}
        if len(picks) < 2:
            self.skipTest("one pick: nothing to ask")

        def script(purpose, messages):
            if purpose == "needs":
                return {"needs": "about_one_existing_design"}
            if purpose == "which_design":
                listed = messages[-1]["content"].split("Designs:\n", 1)[1]
                second = listed.split("\n")[1]  # "- A2 · cheapest (...)"
                return {"design": second[2:].split(" · ")[0]}
            return fake_intake(purpose, messages)

        agent = Agent(ScriptedLLM(script))
        events = run(agent, s, "What does heat cost there?")
        self.assertIsNone(custom(events, "clarification"))
        self.assertIn("which_design: scripted", s.last["calls"])
        self.assertNotEqual(s.last.get("behaviour"), "clarify")


class TestSearchInEveryAnswer(unittest.TestCase):
    """Once a search ran, the answerer is told how wide it was, whatever the question's words."""

    def test_question_without_design_words_gets_the_search(self):
        """4 Nov: "what did the search go through?" got "I have only run a single design"."""
        from unit_test.gemini_agent.test_naming import designed

        agent, s = designed()
        seen = []

        def script(purpose, messages):
            seen.append((purpose, "\n".join(m["content"] for m in messages)))
            out = fake_intake(purpose, messages)
            if purpose == "intake":
                out = dict(out, intent="explain")
            return out

        agent = Agent(ScriptedLLM(script))
        run(agent, s, "What did the search go through to get here?")
        prompts = [c for p, c in seen if p == "answer"]
        self.assertTrue(prompts)
        self.assertIn("The last design search tried", prompts[-1])
        self.assertIn("The picks: ", prompts[-1])


class TestInputsCardStaysOpen(unittest.TestCase):
    """A side question while the inputs card waits is answered; the card stays open."""

    def test_question_then_typed_go(self):
        """A question "what is the peak?" is answered; then a typed "ok, go ahead" runs it."""

        def script(purpose, messages):
            said = messages[-1]["content"].split("Reply: ")[-1].split("Message: ")[-1]
            if purpose == "confirm":
                return {"decision": "other" if "?" in said else "run"}
            if purpose == "intake" and "?" in said:
                return dict(fake_intake(purpose, messages), intent="question")
            return fake_intake(purpose, messages)

        agent = Agent(ScriptedLLM(script))
        s = Session()
        run(agent, s, FULL_BRIEF, confirm=False)
        self.assertEqual(s.pending["kind"], "confirm")
        run(agent, s, "how big is the heat demand peak?", confirm=False)
        self.assertNotEqual(s.last["behaviour"], "design")
        self.assertEqual((s.pending or {}).get("kind"), "confirm")  # still open
        run(agent, s, "ok, go ahead", confirm=False)
        self.assertEqual(s.last["behaviour"], "design")
        self.assertIsNotNone(s.chosen)


class TestSummaryKeepsItsWords(unittest.TestCase):
    """A free answer with a cost still mislabelled loses that sentence, not the whole reply."""

    def test_mislabelled_cost_sentence_goes(self):
        """Not the generic "couldn't confirm" for "sum up what we found" (4 Nov)."""
        from gemini_agent.answer import answer
        from gemini_agent.reporter import Facts

        said = {
            "understood": "a summary",
            "kind": "answer",
            "scope": "project",
            "answer": "We looked at A1, the recommended design, with 34.2 M€ of capital. "
            "Heat costs 23.5 €/MWh in it.",
            "used": ["A1"],
            "follow_ups": [],
        }
        blocks = [
            Block(
                "A1",
                "design",
                "A1: capital 34.2 M€; cost of heat 63.7 €/MWh; cost of "
                "cold 23.5 €/MWh; heat and cold 56.7 €/MWh.",
            )
        ]
        llm = ScriptedLLM([said, said])
        out = answer(
            llm,
            "Sum up what we found.",
            blocks,
            Facts(),
            "I couldn't confirm.",
            costs=[(63.7, 23.5, 56.7)],
            drafted=False,
        )
        self.assertIn("34.2 M€", out.text)
        self.assertNotIn("23.5", out.text)
        llm = ScriptedLLM([said, said])
        out = answer(
            llm,
            "Sum up what we found.",
            blocks,
            Facts(),
            "Checked draft.",
            costs=[(63.7, 23.5, 56.7)],
        )
        self.assertEqual(out.text, "Checked draft.")  # a checked draft still replaces it


class TestPremisesBeforeADesign(unittest.TestCase):
    """Wrong project facts stated before any design are corrected by code."""

    def test_figures_paired_by_their_unit(self):
        """Each figure of a premise is judged against the one fact in its unit (3,500 m, 120 °C)."""
        from gemini_agent import engine, lookup

        s = Session()
        sheet = lookup.project_facts(s.project, s.brief, engine.demand_summary("challenge"))
        lead, notes = lookup.premise_checks(["the aquifer sits at 3,500 m and 120 °C"], sheet)
        self.assertIn("2,500 m", lead)
        self.assertIn("87 °C", lead)
        lead, _ = lookup.premise_checks(["the aquifer is at 2,500 m and 87 °C"], sheet)
        self.assertEqual(lead, "")
        lead, _ = lookup.premise_checks(["the peak is 45 MW"], sheet)  # two facts in MW: no guess
        self.assertEqual(lead, "")


class TestWhatIfIsAnOption(unittest.TestCase):
    """A what-if keeps its design's code; it is still its own option to pick or to resolve."""

    def test_what_if_with_the_same_code_is_listed_first_when_discussed(self):
        """W1 (same code as A1) is an option, first when it is the design under discussion."""
        import types

        from gemini_agent import reporter
        from unit_test.gemini_agent.test_naming import designed

        agent, s = designed()
        w = s.chosen.model_copy(deep=True)
        w.alternative.uid, w.alternative.role, w.change_label = "W1", "what_if", "gas 45 €/MWh"
        s.ledger.append(w)
        s.thread.focus_id = reporter.design_id(w)
        agent._picked = []
        reading = types.SimpleNamespace(about_design=True, designs=[], steps=[], new_design=None)
        options = agent._which_design(s, reading, "So what does heat cost then?")
        ids = [did for _, did in options]
        self.assertIn(reporter.design_id(w), ids)
        self.assertIn(reporter.design_id(s.chosen), ids)


class TestTurnsNotShown(unittest.TestCase):
    """The thread says how many turns there were and which it does not show."""

    def test_count_and_hidden_turns(self):
        """A question about the first turn is answered or said to be out of sight, not guessed."""
        t = Thread()
        history = []
        for n in range(1, 18):
            t.note(n, f"question {n} " + "x " * 30, f"reply {n} " + "y " * 60, "answered")
            history.append({"user": f"question {n}", "reply": f"reply {n}"})
        text = t.text(history[-6:], exchanges=3, limit=2500, first=2)
        self.assertIn("This chat has had 17 turns before this message", text)
        self.assertIn("T1 user: «question 1", text)
        self.assertRegex(text, r"not shown here: T3-T\d+")
        self.assertIn("User (T17): question 17", text)
        block = Block("history", "history", text)
        cut = fit([Block("self", "self", "me"), block], 300)[1].text
        self.assertTrue(cut.startswith("This chat has had 17 turns"))
        self.assertIn("reply 17", cut)


class TestCorrectionIsKept(unittest.TestCase):
    """The correction of a premise leads the reply and is not sent to the claim checker."""

    def test_lead_is_marked_and_skipped_by_the_checker(self):
        """A claim of what Dioscuri said: "Not quite. ... 63.7 €/MWh" stays first."""
        from gemini_agent import claims
        from gemini_agent.answer import answer
        from gemini_agent.reporter import Facts

        said = {
            "understood": "x",
            "premises": [
                {
                    "said": "heat costs 38 €/MWh",
                    "agrees": False,
                    "right": "The cost of heat "
                    "is 63.7 €/MWh; 38 €/MWh was not stated by Dioscuri.",
                }
            ],
            "kind": "answer",
            "scope": "project",
            "answer": "In A1 the cost of heat is 63.7 €/MWh.",
            "used": ["A1"],
            "follow_ups": [],
        }
        blocks = [Block("A1", "design", "A1: cost of heat 63.7 €/MWh.")]
        message = "You said earlier that heat costs 38 €/MWh, right?"
        out = answer(ScriptedLLM([said]), message, blocks, Facts(message), "t", judge_premises=True)
        self.assertTrue(out.text.startswith("**Not quite.** The cost of heat is 63.7 €/MWh"))
        self.assertTrue(out.lead.startswith("**Not quite.**"))
        checked = claims.candidates(out.text, out.lead)
        self.assertFalse(any("not stated" in c for c in checked))

    def test_premises_of_earlier_turns_are_not_corrected_again(self):
        """A question about the first turn is no premise: its 200 GWh is not corrected again."""
        from gemini_agent.answer import premise_lead
        from gemini_agent.reporter import Facts

        facts = Facts()
        facts.put("Daily heat demand: 111.7 GWh a year.")
        raw = {
            "premises": [
                {
                    "said": "the district needs 200 GWh",
                    "agrees": False,
                    "right": "The district needs 111.7 GWh of heat a year.",
                }
            ]
        }
        self.assertEqual(premise_lead(raw, facts, "What did I ask first?"), "")
        said = "The district needs 200 GWh, right?"
        self.assertIn("111.7 GWh", premise_lead(raw, facts, said))

    def test_a_plain_question_is_no_premise(self):
        """A premise the model lists that is not in the user's words is not corrected."""
        from gemini_agent.answer import premise_lead
        from gemini_agent.reporter import Facts

        facts = Facts()
        facts.put("The cost of heat is 63.7 €/MWh.")
        raw = {
            "premises": [
                {
                    "said": "the cost of heat is something else",
                    "agrees": False,
                    "right": "The cost of heat is 63.7 €/MWh.",
                }
            ]
        }
        self.assertEqual(premise_lead(raw, facts, "What does heat cost?"), "")
