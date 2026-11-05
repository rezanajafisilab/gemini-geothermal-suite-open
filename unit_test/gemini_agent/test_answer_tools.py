"""Tests for the three tools on the answer path (4 Nov), with scripted models.

1. Value answers written by code (``DIOSCURI_CODE_FACTS``): the asked values of the design under
   discussion lead the reply as "In short" lines, with the design named.
2. The reply check (``DIOSCURI_REPLY_CHECK``): one evaluator call; on a fail one rewrite, kept
   only when it is not worse.
3. Thinking on hard turns (``DIOSCURI_THINK``): a thinking call of its own, read by the answer
   call as notes; never on the CPU.
"""

import copy
import os
import re
import unittest
from types import SimpleNamespace
from unittest import mock

from gemini_agent import Agent, Session, answer, claims, lookup, policies, reply_check, reporter
from gemini_agent.answer import Block, Reply
from gemini_agent.llm import LLMError, OllamaLLM, ScriptedLLM, shorten_thinking
from gemini_agent.reporter import Facts
from unit_test.gemini_agent.test_agent import (
    FULL_BRIEF,
    confirmed,
    deep_model,
    fake_answer,
    fake_intake,
    run,
)

PASS = {"first": True, "missing": [], "fix": ""}


def scripted(answer_text=None, check=None, rewrite=None, think="notes", seen=None, model="m"):
    """Return a scripted model: the reader's fakes, plus the answer, check, rewrite and thinking.

    ``seen`` collects ``(purpose, messages)`` of every call.
    """

    def reply(purpose, messages):
        if seen is not None:
            seen.append((purpose, messages))
        if purpose == "reply_check":
            return check if check is not None else PASS
        if purpose == "rewrite":
            return fake_answer(messages, text=rewrite)
        if purpose == "think":
            return think
        if purpose == "answer" and answer_text is not None:
            return fake_answer(messages, text=answer_text)
        return fake_intake(purpose, messages)

    return ScriptedLLM(reply, model=model)


def env(**flags):
    """Return a patch of the tools' flags (``None`` removes one)."""
    names = {
        "facts": "DIOSCURI_CODE_FACTS",
        "check": "DIOSCURI_REPLY_CHECK",
        "think": "DIOSCURI_THINK",
    }
    base = {k: v for k, v in os.environ.items() if k not in names.values()}
    base.update({names[k]: v for k, v in flags.items() if v is not None})
    return mock.patch.dict(os.environ, base, clear=True)


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


class TestValueLines(Designed):
    """Tool 1: code writes the values a question asks for, named with their design."""

    def test_a_value_question_leads_with_the_code_line(self):
        """A value question leads with the chosen design's cost of heat, in code's words."""
        s, seen = self.session(), []
        with env(facts="1"):
            run(Agent(scripted(seen=seen)), s, "What is the LCOH?")
        lcoh = reporter.num(s.chosen.economics.lcoh_eur_per_mwh)
        line = f"- Cost of heat ({reporter.design_id(s.chosen)}): **{lcoh} €/MWh**"
        self.assertTrue(s.last["answer"].startswith("**In short**\n" + line + "\n\n"))
        self.assertEqual(s.last["code_facts"]["keys"], ["lcoh"])
        self.assertEqual(s.last["ungrounded"], [])
        prompt = next(m for p, m in seen if p == "answer")[1]["content"]
        self.assertIn("[values] (values, shown above the reply) " + line, prompt)
        rules = next(m for p, m in seen if p == "answer")[0]["content"]
        self.assertIn('A "values" block holds the values asked for', rules)

    def test_the_cost_of_heat_and_cold_is_not_the_cost_of_heat(self):
        """Asked for heat and cold together, the line gives that cost, not the heat's."""
        s = self.session()
        with env(facts="1"):
            run(Agent(scripted()), s, "What is the cost of heat and cold together?")
        lcoe = reporter.num(s.chosen.economics.lcoe_eur_per_mwh)
        self.assertIn("- Cost of heat and cold together (A1 · ", s.last["answer"])
        self.assertIn(f"**{lcoe} €/MWh**", s.last["answer"].split("\n\n")[0])
        self.assertNotIn("- Cost of heat (", s.last["answer"])

    def test_the_line_is_the_design_asked_about(self):
        """A question about A2 (picked with @) gives A2's value, named A2."""
        s = self.session()
        with env(facts="1"):
            run(Agent(scripted()), s, "What is the LCOH?", designs=["A2"])
        head = s.last["answer"].split("\n\n")[0]
        self.assertIn("- Cost of heat (A2 · ", head)
        a2 = next(e for e in s.candidates if e.alternative.uid == "A2")
        self.assertIn(f"**{reporter.num(a2.economics.lcoh_eur_per_mwh)} €/MWh**", head)

    def test_off_by_flag(self):
        """With ``DIOSCURI_CODE_FACTS=0`` the reply is as before: no lines."""
        s = self.session()
        with env(facts="0"):
            run(Agent(scripted()), s, "What is the LCOH?")
        self.assertNotIn("In short", s.last["answer"])
        self.assertNotIn("code_facts", s.last)

    def test_the_template_shown_instead_has_no_line(self):
        """When the model fails, the checked template (which states the value) stands alone."""
        s = self.session()

        def gone(purpose, messages):
            if purpose == "answer":
                raise LLMError("no reply")
            return fake_intake(purpose, messages)

        with env(facts="1"):
            run(Agent(ScriptedLLM(gone)), s, "What is the LCOH?")
        self.assertTrue(s.last["answer"].startswith("The cost of heat is"))
        self.assertNotIn("In short", s.last["answer"])

    def test_a_message_with_premises_gets_no_line(self):
        """5 Nov: "so the boilers only cover around 25 %?" led with "heat demand covered: 100 %".

        The values a message states are checked first (its premises); the key read for such a
        message is a guess at the quantity, so code writes no value line for it.
        """
        said = "So the gas boiler covers only a quarter of the heat?"

        def reply(purpose, messages):
            if purpose == "parameters" and said in messages[-1]["content"]:
                return {"changes": [], "premises": ["the gas boiler covers a quarter of the heat"]}
            return fake_intake(purpose, messages)

        for message, premises in ((said, True), ("What is the LCOH?", False)):
            s = self.session()
            with env(facts="1"):
                run(Agent(ScriptedLLM(reply)), s, message)
            self.assertEqual("code_facts" in s.last, not premises, message)
            self.assertEqual(s.last["answer"].startswith("**In short**"), not premises, message)

    def test_the_values_rule_takes_no_context_from_a_turn_without_values(self):
        """5 Nov: the rule, counted in every answer's budget, cut 260-450 tokens of context.

        A turn without values keeps the budget it had before the rule; a turn with values gets
        room for the block and its rule on top.
        """
        llm = SimpleNamespace(options={"num_ctx": 16384}, model="m")
        rules = answer.load(answer.ANSWER_PROMPT)
        self.assertIn('{values}- A "values" block', rules)
        without = "\n".join(x for x in rules.splitlines() if not x.startswith("{values}"))
        expected = min(answer.room(llm, answer.NUM_PREDICT) - 40, answer.MAX_PROMPT_TOKENS) - (
            answer.estimate_tokens(without) + answer.estimate_tokens("q") + 160
        )
        self.assertEqual(answer.budget(llm, False, "q"), expected)
        values = Block("values", "values", "- Cost of heat (A1): **64.7 €/MWh**")
        design = Block("A1", "design", "A1: cost of heat 64.7 €/MWh. " * 20)
        self.assertEqual(answer.own_room([design]), 0)
        room = answer.own_room([design, values])
        self.assertGreater(room, answer.blocks_tokens([values]))
        # Every block fits in the budget plus the room of the values: none is cut for them.
        blocks = [design, values]
        fitted = answer.fit(blocks, answer.blocks_tokens([design]) + room)
        self.assertEqual(fitted, blocks)

    def test_only_the_designs_own_values_asked_for(self):
        """No line for project values, another design's sheet or values that were not asked."""
        s = self.session()
        a1 = s.chosen
        a2 = next(e for e in s.candidates if e.alternative.uid == "A2")
        sheet = lookup.design_facts(a1)
        lines = lookup.value_lines(["lcoh"], sheet, a1)
        self.assertEqual([k for _, k in lines], ["lcoh"])  # lcoe, lcoc are there, not asked
        self.assertEqual(lookup.value_lines(["lcoh"], lookup.design_facts(a2), a1), [])
        self.assertEqual(lookup.value_lines(["lcoh"], sheet, None), [])
        project = {"reservoir_temp": lookup.Fact("reservoir_temp", "87 °C", "the requirements")}
        self.assertEqual(lookup.value_lines(["reservoir_temp"], project, a1), [])
        long = {"well_checks": lookup.Fact("well_checks", "x " * 200, a1.alternative.code)}
        self.assertEqual(lookup.value_lines(["well_checks"], long, a1), [])

    def test_a_long_value_gives_its_headline(self):
        """The investor's view is one line: NPV, IRR and payback."""
        s = self.session()
        money = lookup.money_facts(s.chosen, s.assumptions)
        ((line, key),) = lookup.value_lines(["investor"], money, s.chosen)
        self.assertEqual(key, "investor")
        self.assertRegex(line, r"NPV after tax [\d.,-]+ M€, IRR [\d.]+% real, payback [\d.]+ years")
        self.assertLess(len(line), 200)

    def test_the_claim_checker_reads_the_values_with_the_rest(self):
        """The values block is a source ranked with the rest: the draft holds them first.

        Put first, it pushed the project's facts past the checker's budget (5 Nov).
        """
        blocks = [
            Block("project", "project", "Gradient 30 °C/km."),
            Block("A1", "design", "A1: cost of heat 64.7 €/MWh."),
            Block("values", "values", "- Cost of heat (A1): **64.7 €/MWh**"),
            Block("draft", "draft", "The cost of heat is 64.7 €/MWh."),
            Block("self", "self", "Dioscuri."),
        ]
        order = [b.id for b in claims.sources(blocks, [])]
        self.assertEqual(order, ["draft", "A1", "values", "project", "self"])
        s, seen = self.session(), []
        with env(facts="1"):
            agent = Agent(scripted(answer_text="It is A1's heat cost.", seen=seen))
            agent.check_claims = "always"
            run(agent, s, "What is the LCOH?")
        checked = next(m for p, m in seen if p == "claims")[1]["content"]
        # The draft, read first, holds the value asked for: the checker never misses it.
        self.assertTrue(checked.split("Sources:\n", 1)[1].startswith("[draft]"))
        self.assertIn(
            "[draft] (draft, the checked answer) The cost of heat is 64.7 €/MWh.", checked
        )


class TestReplyCheck(Designed):
    """Tool 2: one evaluator call; one rewrite on a fail; a worse rewrite is discarded."""

    QUESTION = "What is the cost of heat, and is it cheap?"

    def ask(self, answer_text, check, rewrite=None, flag="1"):
        """Run the question with a scripted answer, check and rewrite; return the session."""
        s = self.session()
        with env(check=flag, facts="1"):  # written with the "In short" lines on (``words``)
            run(Agent(scripted(answer_text, check, rewrite)), s, self.QUESTION)
        return s

    @staticmethod
    def words(s):
        """Return the reply after the code-written "In short" lines."""
        return s.last["answer"].split("\n\n", 1)[1]

    def lcoh(self):
        """Return the chosen design's cost of heat as the replies write it."""
        return f"{reporter.num(self.base.chosen.economics.lcoh_eur_per_mwh)} €/MWh"

    def test_a_failing_check_rewrites_once(self):
        """The first sentence does not answer: one rewrite, kept, with the check's tokens."""
        first = f"A1 has a heat pump top-up. Its heat costs {self.lcoh()}."
        better = f"Its heat costs {self.lcoh()}, from A1's heat pump top-up."
        fail = {"first": False, "missing": [], "fix": "Open with the cost of heat."}
        s = self.ask(first, fail, better)
        self.assertTrue(self.words(s).startswith(better))
        self.assertEqual(s.last["calls"].count("reply_check: m"), 1)
        self.assertEqual(s.last["calls"].count("rewrite: m"), 1)
        record = s.last["reply_check"]
        self.assertEqual((record["verdict"], record["rewrite"]), ("fail", "kept"))
        self.assertGreaterEqual(record["calls"], 2)
        self.assertGreater(record["prompt_tokens"], 0)
        self.assertEqual(s.last["ungrounded"], [])

    def test_the_rewrite_is_told_why_and_keeps_the_prompt(self):
        """The rewrite is the answer's prompt, then the first reply and the check's reason."""
        seen = []
        s = self.session()
        fail = {"first": False, "missing": [], "fix": "Open with the cost of heat."}
        first, then = f"A1 is fine. Heat costs {self.lcoh()}.", f"Heat: {self.lcoh()}."
        with env(check="1"):
            run(Agent(scripted(first, fail, then, seen=seen)), s, self.QUESTION)
        asked = next(m for p, m in seen if p == "answer")
        again = next(m for p, m in seen if p == "rewrite")
        self.assertEqual(again[: len(asked)], asked)
        self.assertEqual(again[-2]["role"], "assistant")
        self.assertIn("Open with the cost of heat.", again[-1]["content"])

    def test_a_rewrite_that_loses_a_number_is_discarded(self):
        """A rewrite without the first reply's figure is worse: the first reply stands."""
        first = f"A1 has a heat pump top-up. Its heat costs {self.lcoh()}."
        fail = {"first": False, "missing": [], "fix": "Say whether heat is cheap first."}
        s = self.ask(first, fail, "Yes, the heat is cheap for a geothermal plant.")
        self.assertTrue(self.words(s).startswith(first))
        self.assertTrue(s.last["reply_check"]["rewrite"].startswith("discarded: the rewrite lost"))

    def test_an_empty_rewrite_is_discarded(self):
        """An empty rewrite fails the answer's checks: the first reply stands."""
        first = f"A1 has a heat pump top-up. Its heat costs {self.lcoh()}."
        fail = {"first": False, "missing": [], "fix": "Open with the cost."}
        s = self.ask(first, fail, "")
        self.assertTrue(self.words(s).startswith(first))
        self.assertIn("discarded", s.last["reply_check"]["rewrite"])

    def test_a_pass_needs_no_rewrite(self):
        """A reply that answers first is left as it is: one call."""
        first = f"Its heat costs {self.lcoh()}."
        s = self.ask(first, PASS)
        self.assertEqual(s.last["reply_check"]["verdict"], "pass")
        self.assertNotIn("rewrite", s.last["reply_check"])
        self.assertNotIn("rewrite: m", s.last["calls"])

    def test_not_for_run_reports_refusals_or_the_cpu_default(self):
        """A design report and a refusal are not checked; nor is any reply by default off a GPU."""
        with env(check="1"):
            s = confirmed(Session())
            run(Agent(scripted()), s, FULL_BRIEF)
            self.assertNotIn("reply_check: m", s.last["calls"])
            run(Agent(scripted()), s, "What will the weather be in Paris tomorrow?")
            self.assertNotIn("reply_check: m", s.last["calls"])
        s = self.ask(f"Heat costs {self.lcoh()}.", PASS, flag=None)  # ScriptedLLM: no GPU
        self.assertNotIn("reply_check", s.last)
        cpu = scripted(f"Heat costs {self.lcoh()}.")
        cpu.device = "cpu"
        s = self.session()
        with env():
            run(Agent(cpu), s, self.QUESTION)
        self.assertNotIn("reply_check", s.last)

    def test_missing_items_must_be_the_users_words_and_unsaid(self):
        """Code keeps only what the message names and the reply does not give."""
        message = "If we add 5 MWp of solar, what does heat cost?"
        listed = {"first": True, "missing": ["5 MWp of solar", "a heat store"], "fix": "x"}
        llm = ScriptedLLM([listed, listed])
        v = reply_check.check(llm, message, "heat's cost with solar", "Heat costs 64.7 €/MWh.")
        self.assertEqual(
            (v.missing, v.dropped, v.failed), (["5 MWp of solar"], ["a heat store"], True)
        )
        v = reply_check.check(llm, message, "", "With 5 MWp of solar, heat costs 64.7 €/MWh.")
        self.assertEqual((v.missing, v.failed), ([], False))
        told = reply_check.Verdict(first=False, missing=["5 MWp of solar"])
        self.assertIn("“5 MWp of solar”", reply_check.instruction(told))

    def test_a_failed_check_leaves_the_reply(self):
        """No verdict (the call failed): nothing is rewritten."""
        v = reply_check.check(ScriptedLLM([LLMError("down")]), "q?", "", "a.")
        self.assertFalse(v.failed)
        self.assertEqual(v.meta()["verdict"], "unchecked")

    def test_worse_compares_the_numbers_said(self):
        """Lost figures make a rewrite worse; codes, handles and citation marks do not count."""
        first = Reply("A1 · 1D-HP-EC@3000-N1-FC costs 64.7 €/MWh [^1].", fallback=False)
        same = Reply("At 64.7 €/MWh, A1 (1D-HP-EC@3000-N1-FC) is the pick.", fallback=False)
        lost = Reply("A1 (1D-HP-EC@3000-N1-FC) is the pick, as computed.", fallback=False)
        self.assertEqual(reply_check.worse(first, same), "")
        self.assertIn("64.7", reply_check.worse(first, lost))
        self.assertIn("failed", reply_check.worse(first, Reply("x", fallback=True)))
        self.assertIn("empty", reply_check.worse(first, Reply("At 64.7.", fallback=False)))

    def test_flags_and_defaults(self):
        """All three off unless set (5 Nov); set, thinking still never runs on the CPU."""
        devices = ("gpu", "cpu", "auto")
        with env():
            self.assertFalse(policies.code_facts())
            self.assertEqual([policies.reply_check(d) for d in devices], [False, False, False])
            self.assertEqual([policies.thinks(d) for d in devices], [False, False, False])
        with env(facts="1", check="on"):
            self.assertTrue(policies.code_facts())
            self.assertEqual([policies.reply_check(d) for d in devices], [True, True, True])
        with env(think="auto"):
            self.assertFalse(policies.thinks("gpu"))
        with env(facts="0", check="1", think="1"):
            self.assertFalse(policies.code_facts())
            self.assertTrue(policies.reply_check("cpu"))
            self.assertEqual([policies.thinks(d) for d in devices], [True, False, True])
        with env(check="off", think="no"):
            self.assertFalse(policies.reply_check("gpu"))
            self.assertFalse(policies.thinks("gpu"))


class TestEvidenceBeforeRemoval(unittest.TestCase):
    """5 Nov: true sentences were removed when their evidence was past the checker's budget."""

    GRADIENT = Block(
        "project",
        "project",
        "Reservoir: midpoint 2,500 m, 87 °C (12 °C at the surface and a gradient of 30 °C/km). "
        "Design limits: 1 to 3 doublets; 50 to 300 m3/h a doublet.",
    )

    def checker(self, seen, quote):
        """Return a checker that flags every sentence and quotes ``quote`` if it can see it."""

        def reply(purpose, messages):
            seen.append((purpose, messages))
            listed = messages[-1]["content"]
            n = len(re.findall(r"^\d+\. ", listed.split("\n\n")[-1], re.M))
            if purpose == "claims":
                return {"verdicts": ["unsupported"] * n}
            return {"quotes": [quote if quote in listed else ""] * n}

        return ScriptedLLM(reply, model="qwen3.5:9b")

    def test_the_checker_reaches_every_block_the_writer_saw(self):
        """A sentence whose evidence is past the budget is kept when the evidence backs it."""
        filler = [Block(f"D{i}", "design", "other figures of the plant " * 220) for i in range(4)]
        blocks = filler + [self.GRADIENT]
        text = "The design assumes a geothermal gradient of 30 °C/km."
        seen = []
        found = claims.check(
            self.checker(seen, "12 °C at the surface and a gradient of 30 °C/km"), text, blocks, []
        )
        judged = next(m for p, m in seen if p == "claims")[-1]["content"].split("Reply:")[0]
        self.assertNotIn("30 °C/km", judged)  # past the checker's budget
        quoted = next(m for p, m in seen if p == "claims_quote")[-1]["content"]
        self.assertTrue(quoted.split("Sources:\n", 1)[1].startswith("[evidence]"))
        self.assertEqual(found.removed, [])
        self.assertEqual(found.text, text)

    def test_a_sentence_no_line_backs_still_goes(self):
        """The evidence is a chance to quote, not a pass: no quote, the sentence goes."""
        seen = []
        text = "The design assumes a geothermal gradient of 45 °C/km."
        found = claims.check(
            self.checker(seen, "a gradient of 45 °C/km"), text, [self.GRADIENT], []
        )
        self.assertEqual(found.removed, [text])

    def test_the_evidence_is_the_nearest_lines_never_the_conversation(self):
        """Each flagged sentence's best lines from every block; what was said is no evidence."""
        said = Block("history", "history", "User: the boiler covers 34.5% of the year's heat.")
        design = Block("A1", "design", "the boiler covers the rest: 38.5 GWh, 34.5% of the heat.")
        near = claims.evidence(
            ["No, the boiler covers 34.5% of the year's heat.", "We cannot drill five doublets."],
            [said, self.GRADIENT, design],
        )
        self.assertIn("- the boiler covers the rest: 38.5 GWh, 34.5% of the heat.", near)
        self.assertIn("Design limits: 1 to 3 doublets;", near)
        self.assertNotIn("User:", near)
        self.assertEqual(claims.evidence(["Hello there."], [said]), "")


class TestQuotes(unittest.TestCase):
    """5 Nov: true sentences lost because a real quote was elided or written with CO₂."""

    SOURCES = (
        "cost of heat 64.7 €/MWh; heat pump COP 5.1; cost of cold 30.4 €/MWh. "
        "CO₂ saving against gas 59.7%."
    )

    def test_an_elided_quote_counts_when_each_part_is_real(self):
        """Every part of four words or more must be in the sources; a made-up part fails."""
        self.assertTrue(
            claims.quoted("cost of heat 64.7 €/MWh; ... cost of cold 30.4", self.SOURCES)
        )
        self.assertTrue(claims.quoted("cost of heat 64.7 €/MWh...", self.SOURCES))
        self.assertFalse(
            claims.quoted("cost of heat 64.7 €/MWh; ... cost of cold 99", self.SOURCES)
        )
        self.assertFalse(claims.quoted("... 64.7 ...", self.SOURCES))

    def test_subscripts_read_as_digits(self):
        """A quote's CO2 is the sources' CO₂; the 2 of CO2 is no figure to match."""
        self.assertTrue(claims.quoted("CO2 saving against gas 59.7%", self.SOURCES))
        near = claims.evidence(
            ["The design does not reach an 80% CO2 saving."],
            [Block("A1", "design", "CO₂ saving 59.7%. Pumps 3.8 GWh. 2 doublets were tried.")],
        )
        self.assertTrue(near.startswith("- CO₂ saving 59.7%."))


class TestRoundedNumberRetry(unittest.TestCase):
    """5 Nov: "about 63 %" (the context: 63.1 %) was asked again with no hint of the value."""

    def test_the_retry_names_the_value_a_number_rounds(self):
        """The retry note gives the context's own value; a number near none gets no note."""
        facts = Facts()
        facts.put("CO2: 9,007 t a year against 24,392 t with gas (63.1 % less).")
        self.assertEqual(answer._rounded_from(63, facts), " (the context has 63.1)")
        self.assertEqual(answer._rounded_from(70, facts), "")
        facts.put("The chillers give 5.73 MW.")
        self.assertEqual(answer._rounded_from(6, facts), "")  # "six doublets" is no 5.73
        problems = answer._problems({"answer": "It cuts CO2 by about 63 %."}, facts, [])
        self.assertIn(
            "These numbers are not in the context: 63 (the context has 63.1).", problems[0]
        )


class TestCorrectionBeforeQuestion(unittest.TestCase):
    """A premise code shows false is corrected in the turn; a question may follow, never alone."""

    def reply(self, kind):
        """Return the answerer's JSON: a "No" and a question, as ``kind``."""
        return {
            "understood": "x",
            "kind": kind,
            "scope": "project",
            "answer": "No: the reservoir is at 2,500 m. Shall I use 2,500 m or another depth?",
            "options": ["2,500 m", "another depth"],
            "used": ["project"],
            "follow_ups": [],
        }

    def test_a_clarifying_reply_to_a_false_premise_answers(self):
        """The code's correction stands: the reply is an answer, the question stays after it."""
        project = Block("project", "project", "Reservoir: midpoint 2,500 m, 87 °C.")
        llm = ScriptedLLM(lambda p, m: self.reply("clarify"), model="qwen3.5:9b")
        fallback = "**Not quite.** The reservoir midpoint depth is 2,500 m."
        out = answer.answer(llm, "It sits at 3,500 m, so ...?", [project], Facts(), fallback)
        self.assertEqual(out.kind, "answer")
        self.assertTrue(out.text.startswith("No: the reservoir is at 2,500 m."))
        self.assertIn("Shall I use 2,500 m or another depth?", out.text)
        # With no correction by code the model's question stands as its question.
        out = answer.answer(llm, "Which depth?", [project], Facts(), "The depth is 2,500 m.")
        self.assertEqual(out.kind, "clarify")

    def test_the_models_own_sound_correction_counts_too(self):
        """5 Nov: "59.7 %, not 80 %" then a question was a clarifying reply; now an answer."""
        project = Block("project", "project", "A1 saves 59.7% of CO2 against gas.")
        message = "With an 80 % CO2 cut, do we meet the 2030 goals?"
        premise = {"said": message, "agrees": False, "right": "A1 saves 59.7% of CO2 against gas."}

        def reply(text):
            return dict(self.reply("clarify"), answer=text, premises=[premise])

        said = "A1 saves 59.7% of CO2 against gas, not 80%. Which 2030 goal do you mean?"
        llm = ScriptedLLM(lambda p, m: reply(said), model="qwen3.5:9b")
        out = answer.answer(llm, message, [project], Facts(message), "A1 saves 59.7%.")
        self.assertEqual(out.kind, "answer")
        self.assertEqual(out.text, said)  # no "Not quite." added: the reply says it itself
        # A bare question, without the right figure, stays the question it is.
        bare = "Which 2030 goal do you mean: the national one or the city's?"
        llm = ScriptedLLM(lambda p, m: reply(bare), model="qwen3.5:9b")
        out = answer.answer(llm, message, [project], Facts(message), "A1 saves 59.7%.")
        self.assertEqual(out.kind, "clarify")

    def test_the_right_figures_count_whatever_the_words_around_them(self):
        """5 Nov: the right values "59.7 % ...; the 2030 target is not in the context"."""
        project = Block("project", "project", "A1 saves 59.7% of CO2 against gas.")
        message = "With an 80 % CO2 cut, do we meet the 2030 goals?"
        right = "A1 saves 59.7% of CO2; the 2030 target value is not in the context."
        premise = {"said": "With an 80 % CO2 cut", "agrees": False, "right": right}
        said = "A1 cuts CO2 by 59.7% against gas. Which 2030 target do you mean?"
        raw = dict(self.reply("clarify"), answer=said, premises=[premise])
        llm = ScriptedLLM(lambda p, m: raw, model="qwen3.5:9b")
        out = answer.answer(llm, message, [project], Facts(message), "A1 saves 59.7%.")
        self.assertEqual(out.kind, "answer")
        self.assertEqual(out.text, said)

    def test_a_sound_no_opening_is_kept_from_the_claim_checker(self):
        """5 Nov: "No, the design does not meet an 80 % target" was removed; it is the answer."""
        project = Block("project", "project", "A1 saves 59.7% of CO2 against gas.")
        message = "With an 80 % CO2 cut, do we meet the 2030 goals?"
        premise = {"said": message, "agrees": False, "right": "A1 saves 59.7% of CO2 against gas."}
        said = "No, A1 does not reach an 80% cut. It saves 59.7% of CO2 against gas."
        raw = dict(self.reply("answer"), answer=said, premises=[premise])
        llm = ScriptedLLM(lambda p, m: raw, model="qwen3.5:9b")
        out = answer.answer(llm, message, [project], Facts(message), "A1 saves 59.7%.")
        self.assertEqual(out.text, said)  # nothing added
        self.assertEqual(out.lead, "No, A1 does not reach an 80% cut.")
        # Without a sound verdict (no premises read) there is no lead to keep.
        llm = ScriptedLLM(lambda p, m: dict(raw, premises=[]), model="qwen3.5:9b")
        out = answer.answer(llm, message, [project], Facts(message), "A1 saves 59.7%.")
        self.assertEqual(out.lead, "")


class FakeClient:
    """An Ollama client that records each chat call and answers with thinking."""

    def __init__(self, content='{"a": 1}', thinking="I weigh A1 against A2."):
        """Keep what each call answers."""
        self.content, self.thinking, self.calls = content, thinking, []

    def chat(self, **kwargs):
        """Record the call and return a response with content and thinking."""
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content, thinking=self.thinking)
        return SimpleNamespace(
            message=message,
            prompt_eval_count=100,
            eval_count=300,
            load_duration=0,
            prompt_eval_duration=10**8,
            eval_duration=2 * 10**9,
        )


class TestThinking(unittest.TestCase):
    """Tool 3: hard turns think in a call of their own; the answer reads the notes."""

    def client(self, **kw):
        """Return a model client on the fake server."""
        llm = OllamaLLM(model="qwen3.5:9b", host="http://127.0.0.1:9", num_ctx=16384)
        llm._client = FakeClient(**kw)
        return llm

    def test_the_think_call_sends_think_and_no_format(self):
        """``think`` asks for thinking, with no format; the record keeps it shortened."""
        llm = self.client(content="", thinking="step " * 600)
        thought, after, call = llm.think("think", [{"role": "user", "content": "q"}], 1024)
        sent = llm._client.calls[-1]
        self.assertIs(sent["think"], True)
        self.assertNotIn("format", sent)
        self.assertEqual(sent["options"]["num_predict"], 1024)
        self.assertEqual((thought.strip(), after), (("step " * 600).strip(), ""))
        self.assertTrue(call.think)
        self.assertIn("characters left out", call.thinking)
        self.assertLess(len(call.thinking), 1300)
        self.assertGreater(call.thinking_tokens, 0)

    def test_answers_never_think_and_never_carry_thinking(self):
        """A formatted call sends ``think=False``; thinking left in the content is moved out."""
        llm = self.client(content='<think>hmm</think>{"a": 2}', thinking="")
        raw, call = llm.structured("answer", [{"role": "user", "content": "q"}], {}, 50)
        self.assertIs(llm._client.calls[-1]["think"], False)
        self.assertEqual(raw, {"a": 2})
        self.assertEqual((call.think, call.thinking), (False, "hmm"))
        self.assertEqual(shorten_thinking("short"), "short")

    def deep(self, seen, think="Compare A1 with the gas reference first."):
        """Return a reasoning model that also thinks (``deep_model`` plus a thinking call)."""
        inner = deep_model()._script

        def reply(purpose, messages):
            seen.append((purpose, messages))
            if purpose == "think":
                if isinstance(think, Exception):
                    raise think
                return think
            return inner(purpose, messages)

        return ScriptedLLM(reply, model="deep")

    def turn(self, seen, reasoning=True, flag="1", device=None, notes=None):
        """Run the design request; return the session."""
        deep = self.deep(seen, notes if notes is not None else "Compare A1 with gas first.")
        if device:
            deep.device = device
        s = confirmed(Session())
        agent = Agent(ScriptedLLM(fake_intake), reasoning_llm=deep)
        with env(think=flag):
            list(agent.run(s, FULL_BRIEF, reasoning=reasoning))
        return s

    def test_a_hard_turn_thinks_before_the_answer(self):
        """Reasoning on: a thinking call, then the answer call reads its notes; the reply never."""
        seen = []
        s = self.turn(seen)
        purposes = [p for p, _ in seen]
        self.assertEqual(purposes[purposes.index("answer") - 1], "think")
        asked = next(m for p, m in seen if p == "answer")
        self.assertEqual(asked[-1]["role"], "user")
        self.assertIn("Compare A1 with gas first.", asked[-1]["content"])
        self.assertEqual(next(m for p, m in seen if p == "think"), asked[:-1])
        self.assertNotIn("Compare A1 with gas first", s.last["answer"])
        self.assertIn("think: deep", s.last["calls"])
        self.assertIn("thinking_tokens", s.last["thinking"])

    def test_no_thinking_off_hard_turns_on_the_cpu_or_by_default(self):
        """Reasoning off, a CPU model, or no flag on an unknown device: no thinking call."""
        for kw in ({"reasoning": False}, {"device": "cpu"}, {"flag": None}):
            seen = []
            s = self.turn(seen, **kw)
            self.assertNotIn("think", [p for p, _ in seen], kw)
            self.assertNotIn("thinking", s.last)

    def test_a_failed_thinking_call_still_answers(self):
        """The thinking call fails: the answer is written as on any turn."""
        seen = []
        s = self.turn(seen, notes=LLMError("cut"))
        asked = next(m for p, m in seen if p == "answer")
        self.assertFalse(any("notes from thinking" in m["content"] for m in asked))
        self.assertEqual(s.last["behaviour"], "design")

    def test_the_prompt_keeps_room_for_the_notes(self):
        """An 8k window gives up context for the notes; a 16k one has room for both."""
        small = SimpleNamespace(options={"num_ctx": 8192})
        self.assertEqual(
            answer.budget(small, True, "q") - answer.budget(small, True, "q", think=True),
            answer.THINK_TOKENS + 60,
        )
        large = SimpleNamespace(options={"num_ctx": 16384})
        self.assertEqual(answer.budget(large, True, "q"), answer.budget(large, True, "q", True))


if __name__ == "__main__":
    unittest.main()
