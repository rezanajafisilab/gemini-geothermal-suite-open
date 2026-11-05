"""Tests for the answerer, its code checks and the model router (no Ollama needed)."""

import unittest

from gemini_agent import Agent, Session
from gemini_agent.answer import (
    Block,
    _swaps,
    answer,
    cite,
    drop_copies,
    fit,
    keep_sourced,
    messages,
    passage_kind,
    unsourced,
)
from gemini_agent.docs import Passage
from gemini_agent.llm import ModelUnavailable, ScriptedLLM
from gemini_agent.reporter import Facts
from gemini_agent.router import Hardware, Router
from unit_test.gemini_agent.test_agent import FULL_BRIEF, custom, fake_claims, fake_intake, run

BLOCKS = [
    Block("self", "self", "Dioscuri designs geothermal heating and cooling."),
    Block("A1", "design", "A1: cost of heat 41 €/MWh; heat coverage 100%."),
    Block("A4", "design", "A4: cost of heat 58 €/MWh."),
]


def reply(text, kind="answer", **extra):
    """Return an answerer reply with this text."""
    return dict(
        {
            "understood": "x",
            "kind": kind,
            "scope": "project",
            "answer": text,
            "options": [],
            "used": ["A1"],
            "follow_ups": [],
        },
        **extra,
    )


class TestChecks(unittest.TestCase):
    """What code accepts in a reply the model wrote."""

    def test_differences_of_stated_numbers_count_as_sourced(self):
        """A difference such as 17 €/MWh is sourced when both 41 and 58 are stated and sourced."""
        facts = Facts()
        facts.put("41 €/MWh and 58 €/MWh")
        self.assertEqual(unsourced("41 €/MWh, 17 €/MWh less than the 58 €/MWh of gas.", facts), [])
        self.assertEqual(unsourced("About 29% cheaper: 41 against 58 €/MWh.", facts), [])
        self.assertEqual(unsourced("It costs 17 €/MWh less.", facts), [17.0])

    def test_small_counts_pass_but_values_do_not(self):
        """A count such as 2 options passes; a value such as 2 MW needs a source."""
        facts = Facts()
        self.assertEqual(unsourced("I see 2 options.", facts), [])
        self.assertEqual(unsourced("A 2 MW chiller.", facts), [2.0])

    def test_unsourced_number_is_retried_then_dropped(self):
        """The model gets one retry naming the number; then the sentence with it is dropped."""
        bad = reply("A1 costs 41 €/MWh. Its COP is 23.7.")
        llm = ScriptedLLM([bad, bad])
        out = answer(llm, "Is A1 good?", BLOCKS, Facts("Is A1 good?"), "A1 costs 41 €/MWh.")
        self.assertEqual(out.text, "A1 costs 41 €/MWh.")
        self.assertFalse(out.fallback)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("23.7", llm.calls and out.corrections[0])

    def test_retry_that_fixes_the_answer_is_used(self):
        """A retry without the invented number is shown as written."""
        llm = ScriptedLLM([reply("COP 23.7."), reply("A1 costs 41 €/MWh, cheaper than A4.")])
        out = answer(llm, "Is A1 good?", BLOCKS, Facts(), "template")
        self.assertEqual(out.text, "A1 costs 41 €/MWh, cheaper than A4.")
        self.assertEqual(out.used, ["A1"])

    def test_dropped_key_value_comes_back_from_the_draft(self):
        """A reply that leaves out the cost of heat gets the draft's sentence back."""
        draft = "A1 covers 100% of the heat. It costs 41 €/MWh."
        good = reply("A1 is the best design.")
        llm = ScriptedLLM([good, good])
        out = answer(llm, "Design", BLOCKS, Facts(), draft, must=["41 €/MWh"])
        self.assertTrue(out.text.startswith("A1 is the best design."))
        self.assertIn("It costs 41 €/MWh.", out.text)

    def test_dropped_source_name_comes_back_without_a_retry(self):
        """Only a dropped value is worth a second call; a source name is simply added back."""
        draft = "It is 87 °C. Source: the project's subsurface data (subsurface.json)."
        llm = ScriptedLLM([reply("The reservoir is at 87 °C.")])
        facts = Facts()
        facts.put(draft)
        out = answer(llm, "T?", BLOCKS, facts, draft, must=["87 °C", "subsurface.json"])
        self.assertEqual(len(out.calls), 1)
        self.assertIn("(subsurface.json)", out.text)

    def test_another_designs_figure_is_asked_again_then_dropped(self):
        """4 Nov: "the cheapest saves 60.6 %", the recommended design's figure (it saves 64 %)."""
        blocks = [
            Block("A47", "design", "A47 (cheapest): CO2 saving against gas 64%."),
            Block("A1", "design", "A1 (best overall): CO2 saving against gas 60.6%."),
        ]
        draft = "The CO₂ saving against gas is 64%. Source: A47."
        theirs = [("60.6%", ["A1", "1D-HP-EC@3000-N1-FC", "best overall", "recommend"])]
        bad = reply("The cheapest design saves **60.6%** of CO₂ against gas.")
        llm = ScriptedLLM([bad, bad])
        out = answer(llm, "And the cheapest?", blocks, Facts(), draft, ["64%"], theirs=theirs)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("60.6% is A1's", out.corrections[0])
        self.assertNotIn("60.6", out.text)
        self.assertIn("64%", out.text)
        # Named, it is a comparison, not a mislabel.
        good = reply("The cheapest saves 64%, more than A1's 60.6%.")
        llm = ScriptedLLM([good])
        out = answer(llm, "And the cheapest?", blocks, Facts(), draft, ["64%"], theirs=theirs)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(out.text, "The cheapest saves 64%, more than A1's 60.6%.")

    def test_add_back_takes_the_drafts_sentence_for_a_lost_value(self):
        """What the claim check removed with a value asked for comes back from the draft."""
        from gemini_agent.answer import add_back

        draft = "The CO₂ saving against gas is 64%. Source: A47."
        self.assertEqual(
            add_back("It meets every cap.", draft, ["64%"]),
            ("It meets every cap. The CO₂ saving against gas is 64%.", []),
        )
        self.assertEqual(add_back("It saves 64%.", draft, ["64%"]), ("It saves 64%.", []))
        self.assertEqual(add_back("It saves.", "No such value.", ["64%"]), ("It saves.", ["64%"]))

    def test_clarify_needs_two_readings(self):
        """A clarification with one option is shown as an ordinary answer."""
        llm = ScriptedLLM([reply("Do you mean A1?", kind="clarify", options=["A1"])])
        out = answer(llm, "that one", BLOCKS, Facts(), "template")
        self.assertEqual((out.kind, out.options), ("answer", []))

    def test_an_answer_marked_clarify_is_an_answer(self):
        """A "clarification" that asks nothing (no question mark) is shown as an answer."""
        llm = ScriptedLLM(
            [reply("The COP is lower because of losses.", "clarify", options=["a", "b"])]
        )
        out = answer(llm, "why?", BLOCKS, Facts(), "template")
        self.assertEqual((out.kind, out.options), ("answer", []))

    def test_an_unreadable_message_is_unclear_whatever_its_words(self):
        """Letter mash and a sentence cut off are one kind: "unclear" (the older "nonsense")."""
        for kind in ("unclear", "nonsense"):
            said = reply("I could not read that. What do you mean?", kind=kind, scope="out")
            for message in ("asdkjh qwe zxcvbn", "Could you make the"):
                out = answer(ScriptedLLM([said]), message, BLOCKS, Facts(), "template")
                self.assertEqual((out.kind, out.fallback), ("unclear", False))

    def test_kinds_are_limited_after_a_tool_run(self):
        """After a design, the reply can only be an answer (the schema and the code agree)."""
        llm = ScriptedLLM([reply("That is not a question.", kind="nonsense")])
        out = answer(llm, "x", BLOCKS, Facts(), "template", kinds=("answer",))
        self.assertEqual(out.kind, "answer")

    def test_missing_model_shows_the_template(self):
        """A stopped server leaves the checked template in place and says why."""
        llm = ScriptedLLM([ModelUnavailable("model 'x' not found")])
        out = answer(llm, "x", BLOCKS, Facts(), "The template.")
        self.assertEqual((out.text, out.fallback), ("The template.", True))
        self.assertIn("not found", out.unavailable)

    def test_context_budget_drops_passages_first(self):
        """When the context is too long, passages go before the designs and the self card.

        The budget is in tokens (4 Nov): 900 letters are about 250.
        """
        docs = [Block(f"doc{i}", "doc", "x" * 900) for i in range(5)]
        kept = fit(BLOCKS + docs, 600)
        self.assertEqual([b.id for b in kept][:3], ["self", "A1", "A4"])
        self.assertLess(len(kept), 8)

    def test_passage_kinds(self):
        """Passages from GEMINI's docs, the team's notes and the user's files are told apart."""
        self.assertEqual(passage_kind("src/gemini_documentation/x.rst"), "doc")
        self.assertEqual(passage_kind("hackathon/docs/cooling_design.md"), "note")
        self.assertEqual(passage_kind("datasheet.md", ["datasheet.md"]), "file")


class TestMarkdown(unittest.TestCase):
    """Tables, lists and citations in the model's reply."""

    def test_invented_table_row_goes_and_the_table_stays(self):
        """A row with an unsourced number is dropped; the header and the other rows stay."""
        facts = Facts()
        facts.put("A1 costs 41 €/MWh. A4 costs 58 €/MWh.")
        text = (
            "Costs:\n\n| Design | Cost |\n|---|---|\n| A1 | 41 €/MWh |\n| A2 | 52 €/MWh |\n\n"
            "- **A1** is cheapest [A1].\n- A2 needs 23.7 MW. It is mock."
        )
        kept = keep_sourced(text, facts)
        self.assertIn("| A1 | 41 €/MWh |", kept)
        self.assertNotIn("52", kept)
        self.assertIn("- **A1** is cheapest [A1].", kept)
        self.assertIn("- It is mock.", kept)

    def test_table_with_no_rows_left_is_removed(self):
        """A header with nothing under it is not shown."""
        kept = keep_sourced("Here:\n\n| D | C |\n|---|---|\n| A9 | 99 €/MWh |\n\nDone.", Facts())
        self.assertEqual(kept, "Here:\n\nDone.")

    def test_copy_of_the_file_rows_is_removed(self):
        """The chat shows the file's table, so a copy of its rows (and its lead-in) goes."""
        data = Block("data1", "data", "y", "h.csv", columns=("date", "heat_demand_mw"))
        text = (
            "Here is the table:\n\n| date | heat_demand_mw |\n|---|---|\n| 2025-01-01 | 13 |"
            "\n\nIt peaks in winter."
        )
        self.assertEqual(drop_copies(text, [data]), ("It peaks in winter.", True))
        other = "| Design | Cost |\n|---|---|\n| A1 | 41 €/MWh |"
        self.assertEqual(drop_copies(other, [data]), (other, False))

    def test_citations_become_card_numbers(self):
        """[doc1] and [data1] become [^n] in card order; ids without a card are removed."""
        doc = Block("doc1", "doc", "x", passage={"source": "a.rst", "section": "s", "text": "t"})
        data = Block("data1", "data", "y", "heat.csv", passage={"source": "heat.csv"})
        text, cards = cite(
            "It is mock [A1]. See [data1]. Docs say so [doc1, data1]. Keep [this].",
            BLOCKS + [doc, data],
            ["doc1"],
        )
        self.assertEqual(text, "It is mock. See[^1]. Docs say so[^2][^1]. Keep [this].")
        self.assertEqual([b.id for b in cards], ["data1", "doc1"])
        self.assertEqual(unsourced(text, Facts()), [])

    def test_images_only_for_models_that_see(self):
        """The image goes with the message for a vision model, never as text."""
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            f.write(b"png")
            f.flush()
            blocks = [Block("data1", "data", "an image", "p.png", image=f.name)]
            self.assertEqual(
                messages("what is it?", blocks, False, vision=True)[-1]["images"], [b"png"]
            )
            self.assertNotIn("images", messages("what is it?", blocks, False)[-1])
            self.assertTrue(Path(f.name).is_file())


class TestClaims(unittest.TestCase):
    """The claim checker reads the reply's words against its sources."""

    def model(self, answer_text, verdicts=None, fail=False):
        """Return a scripted model: the reader, an answer, then the checker's verdicts."""

        def script(purpose, messages):
            if purpose == "claims":
                if fail:
                    return ValueError("bad JSON")  # the script raises it as a failed call
                return verdicts if verdicts is not None else fake_claims(messages)
            if purpose == "answer":
                return dict(reply(answer_text), used=["self"], scope="project")
            return dict(fake_intake(purpose, messages), intent="about")

        return ScriptedLLM(script)

    def test_unsupported_sentence_is_removed(self):
        """A feature the sources do not support is taken out; the rest stays."""
        text = "I design district heating with GEMINI. I also model ATES storage for you."
        s = Session()
        ev = run(Agent(self.model(text)), s, "what can you do for us?")
        self.assertEqual(s.last["answer"], "I design district heating with GEMINI.")
        self.assertEqual(s.last["claims_removed"], ["I also model ATES storage for you."])
        step = next(e for e in ev if e.get("stepName") == "claims" and e["type"] == "STEP_FINISHED")
        self.assertEqual((step["metadata"]["checked"], step["metadata"]["removed"]), (2, 1))
        self.assertEqual(custom(ev, "answer")["claims"]["removed"], s.last["claims_removed"])

    def test_mostly_unsupported_reply_shows_the_template(self):
        """When most claims have no source, the checked template is shown instead."""
        text = "I model ATES storage. ATES runs in every district I design."
        s = Session()
        run(Agent(self.model(text)), s, "what can you do for us?")
        self.assertTrue(s.last["claims_fallback"])
        self.assertNotIn("ATES", s.last["answer"])

    def test_failed_check_keeps_the_reply(self):
        """A checker that gives no usable verdicts leaves the reply as written."""
        text = "I design district heating with GEMINI, and every number comes from a tool."
        s = Session()
        run(Agent(self.model(text, fail=True)), s, "what can you do for us?")
        self.assertEqual(s.last["answer"], text)

    def test_reworded_template_is_not_checked_in_fast_mode(self):
        """A reply anchored by the checked template needs no second call."""
        s = Session()
        run(Agent(ScriptedLLM(fake_intake)), s, FULL_BRIEF)
        self.assertNotIn("claims: scripted", s.last["calls"])

    def test_checker_skips_draft_sentences_and_questions(self):
        """Sentences copied from the draft, table rows and questions are not sent."""
        from gemini_agent.claims import candidates

        draft = "A1 covers 100% of the heat at 41 €/MWh."
        text = (
            "A1 covers 100% of the heat at 41 €/MWh. [A1]\n\n| D | C |\n|---|---|\n| A1 | 41 |\n\n"
            "- The deep well avoids most gas use.\n\nShall I compare it with A2?"
        )
        self.assertEqual(candidates(text, draft), ["The deep well avoids most gas use."])


class TestCharts(unittest.TestCase):
    """The data the chat draws for a design: months and the designs side by side."""

    def test_monthly_energy_adds_up_and_designs_are_compared(self):
        """The months sum to the year; designs side by side only when the message asks (3 Nov)."""

        def reply(purpose, messages):
            if purpose == "needs":
                said = messages[-1]["content"]
                return {"needs": "designs_side_by_side" if "side" in said else "new_design_run"}
            return fake_intake(purpose, messages)

        agent, s = Agent(ScriptedLLM(reply)), Session()
        ev = run(agent, s, FULL_BRIEF)
        card = custom(ev, "result")
        heat = card["monthly_gwh"]["heat"]
        self.assertEqual(len(heat["demand"]), 12)
        self.assertAlmostEqual(sum(heat["geo"]), card["heat_split_gwh"]["geo"], places=1)
        self.assertIsNone(custom(ev, "comparison"))  # the result card alone
        self.assertFalse(custom(ev, "candidates")["show"])
        ev = run(agent, s, "Put the designs side by side, please.")
        compared = custom(ev, "comparison")
        self.assertEqual(compared["chosen"], compared["designs"][0]["code"])
        self.assertTrue(any(d["reference"] for d in compared["designs"]))
        self.assertGreaterEqual(len(compared["designs"]), 2)


class TestRouter(unittest.TestCase):
    """Which model plays each role on each device."""

    def test_gpu_answers_with_the_larger_model_in_both_modes(self):
        """With a 16 GB GPU the 9B model answers; on the CPU the 4B one, in both modes."""
        router = Router(hardware=Hardware("RTX", 16000))
        gpu, cpu = router.profiles()["auto"], router.profiles()["cpu"]
        self.assertEqual(gpu["answer"], {"model": "qwen3.5:9b", "device": "gpu"})
        self.assertEqual(gpu["answer_reasoning"]["model"], "qwen3.5:9b")
        self.assertEqual(cpu["answer"], {"model": "qwen3.5:4b", "device": "cpu"})
        self.assertEqual(cpu["answer_reasoning"], {"model": "qwen3.5:4b", "device": "cpu"})
        self.assertEqual(cpu["fast"]["device"], "cpu")
        self.assertIs(router.reader("cpu"), router.reader("cpu"))

    def test_no_gpu_means_cpu_everywhere(self):
        """Without a GPU both choices run on the CPU."""
        router = Router(hardware=Hardware())
        self.assertEqual(router.profiles()["auto"]["answer"]["device"], "cpu")
        self.assertEqual(router.profiles()["auto"]["gpu"], "")


class TestConversation(unittest.TestCase):
    """The answerer in a conversation: unclear messages, nonsense, citations, memory."""

    def setUp(self):
        """Create an agent on the scripted model."""
        self.agent = Agent(ScriptedLLM(fake_intake))

    def test_unclear_message_offers_readings_and_answers_the_pick(self):
        """An unclear message gets a multiple-choice question; the pick is then answered."""
        s = Session()
        ev = run(self.agent, s, "give me instructions")
        self.assertEqual(ev[-1]["outcome"]["interrupts"][0]["reason"], "choice")
        question = custom(ev, "clarification")
        self.assertEqual(question["kind"], "choice")
        options = question["questions"][0]["options"]
        self.assertEqual(len(options), 2)
        self.assertIsNone(custom(ev, "suggestions"))
        self.assertEqual(s.last["behaviour"], "clarify")
        run(self.agent, s, answers={"choice": options[0]})
        self.assertIsNone(s.pending)
        self.assertEqual(s.history[-1]["user"], options[0])
        self.assertNotEqual(s.last["behaviour"], "clarify")

    def test_question_about_the_result_does_not_redesign(self):
        """A question about the result is answered from the design, not simulated again."""
        s = Session()
        run(self.agent, s, FULL_BRIEF)
        ev = run(self.agent, s, "Interpret the result for me. Is this a good design?")
        self.assertEqual(s.last["behaviour"], "answer")
        self.assertFalse(any(e.get("stepName") == "simulate" for e in ev))

    def test_off_topic_keeps_the_standard_suggestions(self):
        """A declined message offers what Dioscuri can do, not the model's follow-ups."""
        ev = run(self.agent, Session(), "What will the weather be in Paris tomorrow?")
        self.assertNotIn("What next?", custom(ev, "suggestions"))

    def test_unrelated_general_answer_is_declined(self):
        """If the reader found it unrelated, general background (a poem) is not sent."""

        def model(purpose, messages):
            if purpose != "answer":
                return dict(fake_intake(purpose, messages), relevant=False, intent="other")
            return reply("Volcanoes are fiery giants.", scope="general")

        s = Session()
        run(Agent(ScriptedLLM(model)), s, "Write me a poem about volcanoes.")
        self.assertEqual((s.last["behaviour"], s.last["answer_kind"]), ("refuse", "out_of_scope"))
        self.assertNotIn("fiery", s.last["answer"])

    def test_question_about_using_dioscuri_is_not_declined(self):
        """The reader may call "give me instructions" unrelated; the answerer knows better."""

        def model(purpose, messages):
            if purpose != "answer":
                return dict(fake_intake(purpose, messages), relevant=False, intent="other")
            return dict(
                reply("Describe a district, then ask for a design.", scope="general"),
                understood="How to use Dioscuri.",
            )

        s = Session()
        run(Agent(ScriptedLLM(model)), s, "give me instructions")
        self.assertEqual(s.last["answer_kind"], "answer")
        self.assertIn("Describe a district", s.last["answer"])

    def test_polite_you_is_not_a_question_about_us(self):
        """A polite "could you explain ..." is about the topic, so the docs are searched."""
        from gemini_agent import intake

        def model(purpose, messages):
            return dict(fake_intake(purpose, messages), intent="about")

        llm = ScriptedLLM(model)
        msg = "could you please explain overall what is geothermal energy?"
        self.assertEqual(intake.read_message(msg, llm).intent, "explain")
        self.assertEqual(intake.read_message("what are your advantages?", llm).intent, "about")
        mine = "What can you do for our district heating network?"
        self.assertEqual(intake.read_message(mine, llm).intent, "about")  # S14

    def test_letter_mash_is_asked_about(self):
        """Random letters get the one reply for unreadable messages: what, then a question."""
        s = Session()
        ev = run(self.agent, s, "asdkjh qwe zxcvbn")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertEqual(custom(ev, "answer")["kind"], "unclear")
        self.assertIn("“asdkjh qwe zxcvbn”", s.last["answer"])
        self.assertTrue(s.last["answer"].endswith("?"))
        self.assertEqual(custom(ev, "clarification")["kind"], "choice")

    def test_sources_are_only_what_the_answer_cited(self):
        """The source cards list the passages the model relied on, not every hit."""

        def model(purpose, messages):
            if purpose != "answer":
                return fake_intake(purpose, messages)
            return reply("From the notes.", used=["note1"])

        docs = FakeDocs(
            [
                Passage("hackathon/docs/a.md", "A", "Alpha.", 2.0),
                Passage("hackathon/docs/b.md", "B", "Beta.", 1.0),
            ]
        )
        agent = Agent(ScriptedLLM(model), docs=docs)
        s = Session()
        ev = run(agent, s, "Explain how the heat pump COP is computed.")
        self.assertEqual([p["source"] for p in custom(ev, "sources")], ["hackathon/docs/a.md"])

    def test_history_is_kept_and_saved(self):
        """The last exchanges travel with the session, so follow-ups make sense."""
        s = Session()
        run(self.agent, s, FULL_BRIEF)
        run(self.agent, s, "hello")
        self.assertEqual([h["user"] for h in s.history], [FULL_BRIEF, "hello"])
        self.assertEqual(Session.from_dict(s.to_dict()).history, s.history)

    def test_device_choice_picks_the_models(self):
        """A run on the CPU uses the CPU clients of the router."""
        router = Router(hardware=Hardware("RTX", 16000))
        agent = Agent(router.fast, router=router)
        agent._device, agent._reasoning = "cpu", False
        self.assertEqual(agent._answerer().model, "qwen3.5:4b")
        self.assertEqual(agent._device_of(agent._answerer()), "cpu")
        agent._device = "auto"
        self.assertEqual(agent._answerer().model, "qwen3.5:9b")


class FakeDocs:
    """A document search that always returns the same passages."""

    def __init__(self, passages):
        """Keep the passages."""
        self.passages = passages

    def search(self, query, k=4, thread_id=None, only_attached=False, project=None):
        """Return the passages."""
        return self.passages

    def info(self):
        """Say which backend answered."""
        return {"last_backend": "fake"}


if __name__ == "__main__":
    unittest.main()


class TestOperations(unittest.TestCase):
    """The design's own day-level numbers, firm capacity and what it does not have."""

    def test_named_days(self):
        """Dates in several spellings; "may" as a verb is not May."""
        from gemini_agent.answer import named_days

        days, months = named_days(
            "Shift plan for 25 to 31 January, Jan 28 again, and 2027-07-19; the model may not "
            "do failures. What about November?"
        )
        self.assertEqual(days, [24, 25, 26, 27, 28, 29, 30, 199])
        self.assertEqual(months, [10])
        self.assertEqual(named_days("What runs on the 3rd of March?")[0], [61])

    def test_operations_block(self):
        """N-1, the peak days, stops as dates and the not-in-design list reach the answerer."""
        from gemini_agent import engine
        from gemini_agent.answer import operations_block
        from gemini_agent.contract import DesignBrief

        outcome = engine.search(DesignBrief())
        entry = engine.picked(outcome, "cost")  # the cheapest: one unit out leaves days short
        text = operations_block(entry, "What is running on 19 July?").text
        self.assertIn(
            "doublet 1 (its producer, ESP or injector lost) out: heat demand NOT met", text
        )
        self.assertIn("the boiler already at full output", text)
        self.assertIn("19 Jul:", text)
        self.assertRegex(text, r"doublet 1 \d+ \w{3} to \d+ \w{3}")
        self.assertIn("buffer tanks", text)
        self.assertIn("peak boiler", text)
        plan = operations_block(outcome.chosen, "").text  # the best overall: a reliable plan
        self.assertIn("reliable plan", plan)
        self.assertNotIn("NOT met", plan)
        self.assertNotIn("each unit is one machine", plan)


class TestCostLabels(unittest.TestCase):
    """Costs per MWh are labelled right and never added up."""

    COSTS = [(79.7, 42.5, 73.2)]  # heat, cold, heat and cold together, €/MWh

    def test_heat_plus_cold_is_no_cost(self):
        """A sum of heat and cold costs ("combined 122.2 €/MWh") is corrected to both together."""
        fix = _swaps(
            {"answer": "Heat 79.7 €/MWh, cold 42.5 €/MWh, combined 122.2 €/MWh."}, self.COSTS
        )
        self.assertEqual(len(fix), 1)
        self.assertIn("73.2", fix[0])

    def test_right_labels_pass(self):
        """The three real costs with their names need no fix."""
        ok = "Heat 79.7 €/MWh, cold 42.5 €/MWh; heat and cold together 73.2 €/MWh."
        self.assertEqual(_swaps({"answer": ok}, self.COSTS), [])


class TestRunsBlock(unittest.TestCase):
    """The conversation's runs, each against run A."""

    def test_run_a_values_are_given_with_the_change(self):
        """4 Nov: "run A assumed a 60 °C return" was removed for want of a source."""
        from types import SimpleNamespace

        from gemini_agent.answer import runs_block

        base = {"heating": {"supply_c": 100.0, "return_c": 60.0}}
        new = {"heating": {"supply_c": 100.0, "return_c": 50.0}}
        s = SimpleNamespace(
            searches=[{"brief": base, "candidates": []}, {"brief": new, "candidates": []}]
        )
        text = runs_block(s).text
        self.assertIn("heating return temperature 50 °C", text)
        self.assertIn("run A had heating return temperature 60 °C", text)


class TestDecisionsBlock(unittest.TestCase):
    """Each choice of the design against its best alternative."""

    def test_a_reliable_pick_with_a_plant_option_has_its_choices(self):
        """4 Nov: the pick 1D-HP-EC@3000-N1-FC found no layout and the block went missing."""
        from gemini_agent.answer import decisions_block
        from unit_test.gemini_agent.test_naming import designed

        _, s = designed()
        a = s.chosen.alternative
        block = decisions_block(s.chosen, s.candidates)
        self.assertIsNotNone(block, a.code)
        if a.reliable:
            self.assertIn("the reliable plan adds", block.text)
        self.assertIn(f"Choices of {a.code}", block.text)

    def test_the_search_lists_the_variants_of_the_picks_layout(self):
        """4 Nov: "why not two injectors?" got no figure: 1D-HP-EC@3000-2I was not listed."""
        from gemini_agent.answer import search_block
        from unit_test.gemini_agent.test_naming import designed

        _, s = designed()
        variants = [e.alternative.code for e in s.candidates if e.alternative.stage == 2]
        if not variants:
            self.skipTest("no variants in this search")
        text = search_block(s.candidates, search=s.searches[-1]).text
        self.assertTrue(any(code + " (" in text for code in variants), variants)

    def test_a_cut_search_block_keeps_every_pick(self):
        """4 Nov: "which designs did the search pick?" got heat pump sizes: picks cut away."""
        from gemini_agent.answer import _cut, search_block
        from unit_test.gemini_agent.test_naming import designed

        _, s = designed()
        block = search_block(s.candidates, search=s.searches[-1])
        kept = _cut(block, 2000).text
        for e in s.candidates:
            if e.alternative.picks:
                self.assertIn(f"{e.alternative.uid} {e.alternative.code} (", kept)


class TestClaimsBudget(unittest.TestCase):
    """How much of the sources the claim checker reads."""

    def test_a_16k_window_reads_twice_an_8k_one(self):
        """4 Nov: a cited search block crowded out the designs in 14,000 characters."""
        from types import SimpleNamespace

        from gemini_agent.claims import MAX_SOURCE_CHARS, budget

        cpu = SimpleNamespace(options={"num_ctx": 8192})
        gpu = SimpleNamespace(options={"num_ctx": 16384})
        self.assertEqual(budget(cpu), MAX_SOURCE_CHARS)
        self.assertEqual(budget(gpu), 2 * MAX_SOURCE_CHARS)


class TestSearchPicks(unittest.TestCase):
    """The search block's picks."""

    def test_the_picks_come_first_with_their_cost_of_heat(self):
        """The picks, with their cost of heat, open the block.

        5 Nov: "which designs did the search pick, and what does heat cost in each?" listed
        other designs.
        """
        from gemini_agent import reporter
        from gemini_agent.answer import search_block
        from unit_test.gemini_agent.test_naming import designed

        _, s = designed()
        text = search_block(s.candidates, search=s.searches[-1]).text
        head = text.split("The last design search tried")[0]
        picks = [e for e in s.candidates if e.alternative.picks]
        self.assertTrue(picks)
        for e in picks:
            self.assertIn(f"- {e.alternative.uid} {e.alternative.code} (", head)
            self.assertIn(f"heat {reporter.num(e.economics.lcoh_eur_per_mwh)} €/MWh", head)


class TestAnswerThenOffer(unittest.TestCase):
    """An answer that ends with an offer is an answer; the offer's choices are follow-ups."""

    def test_an_answer_with_an_offer(self):
        """5 Nov: "No, ... one doublet. Would you like ...?" was graded a question back."""
        from gemini_agent.answer import answer_then_offer

        said = answer_then_offer(
            "No, the design A1 · 1D-HP-EC@3000-N1-FC has one doublet. Shall I show three?"
        )
        self.assertEqual(said, "No, the design A1 · 1D-HP-EC@3000-N1-FC has one doublet.")

    def test_a_question_back_stays(self):
        """A reply that asks first, or says nothing with a figure, is a question back."""
        from gemini_agent.answer import answer_then_offer

        self.assertIsNone(answer_then_offer("Which figure do you mean? The 34.2 M€ or 64.7?"))
        self.assertIsNone(
            answer_then_offer("I cannot tell what you mean by that. Which design do you mean?")
        )
        self.assertIsNone(answer_then_offer("The cheapest design has 1 doublet."))
