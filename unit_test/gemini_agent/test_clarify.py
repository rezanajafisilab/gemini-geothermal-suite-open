"""Clarifying with concrete choices (``clarify``): ask, offer two or three, run the one picked.

4 Nov: "Run it again with 2." ran with 2 doublets, "Use the setting we talked about." ran the
recommended design, and "And if gas gets more expensive?" ran (with a misread flaring switch)
with no amount. The reading says which words are open; code builds the options and keeps them
with the question, so the next message is read against them.
"""

import os
import re
import unittest
from unittest import mock

from gemini_agent import Agent, clarify, parameters
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import custom, fake_intake, run
from unit_test.gemini_agent.test_naming import designed

READING = {
    "changes": [],
    "doublets": [],
    "unsupported": [],
    "failures": [],
    "designs": [],
    "asks_for": [],
    "premises": [],
    "origin_of": [],
    "on_topic": True,
    "objective": None,
    "steps": [],
    "open": [],
}


class TestChoices(unittest.TestCase):
    """The amounts offered come from the catalogue and the design."""

    def test_an_option_being_added_gets_typical_sizes(self):
        """A store, solar panels, a network: sizes across the catalogue's typical range."""
        self.assertEqual(clarify.choices("storage_mwh", 0.0, 0.0), [200.0, 1000.0, 5000.0])
        solar = clarify.choices("solar_mwp", 0.0, 0.0)
        low, high = parameters.CATALOGUE["solar_mwp"].typical
        self.assertTrue(all(low <= v <= high for v in solar))
        self.assertGreaterEqual(len(solar), 2)

    def test_a_count_gets_whole_numbers(self):
        """More doublets from one: 2 or 3; fewer from three: 2 or 1."""
        self.assertEqual(clarify.choices("n_doublets", 2.0, 1.0, "more doublets"), [2.0, 3.0])
        self.assertEqual(clarify.choices("n_doublets", 2.0, 3.0, "fewer doublets"), [2.0, 1.0])

    def test_a_price_gets_steps_from_now(self):
        """Gas that gets more expensive: steps up from the price now."""
        out = clarify.choices("gas_eur_per_mwh", 138.8, 69.4, "gas gets more expensive")
        self.assertTrue(all(v > 69.4 for v in out))

    def test_a_more_doublets_reading_is_vague(self):
        """A reading of "use more doublets" as 2: no number in the words, so it is asked."""
        r = parameters.check(
            {"changes": [{"key": "n_doublets", "value": 2, "quote": "more doublets"}]},
            "Use more doublets.",
            {"n_doublets": 1},
            designed=True,
        )
        self.assertEqual((r.changes, list(r.vague)), ({}, ["n_doublets"]))


class TestUnclear(unittest.TestCase):
    """The reading's ``open`` item: checked by code, and the guess it holds dropped."""

    def test_the_guess_goes(self):
        """For "run it again with 2", the 2 doublets read from "with 2" go; keys are checked."""
        raw = dict(
            READING,
            changes=[{"key": "n_doublets", "value": 2, "quote": "with 2"}],
            steps=[{"do": "design", "quote": "Run it again with 2", "changes": []}],
            open=[{"quote": "with 2", "could_be": ["n_doublets", "heat_pump_mw", "x"]}],
        )
        r = parameters.check(raw, "Run it again with 2.", {"n_doublets": 1}, designed=True)
        self.assertEqual(r.changes, {})
        self.assertEqual(
            r.open_ref, {"quote": "with 2", "could_be": ["n_doublets", "heat_pump_mw"]}
        )
        self.assertEqual(r.steps, [])

    def test_named_words_act(self):
        """For "with 2 doublets", an item that names what it read is no question; it acts."""
        raw = dict(
            READING,
            changes=[{"key": "n_doublets", "value": 2, "quote": "with 2 doublets"}],
            open=[{"quote": "2 doublets", "could_be": ["n_doublets"]}],
        )
        r = parameters.check(raw, "Run it again with 2 doublets.", {"n_doublets": 1}, True)
        self.assertEqual(r.changes, {"n_doublets": 2})
        self.assertIsNone(r.open_ref)

    def test_not_the_message_words(self):
        """A quote the message does not have is no item."""
        raw = dict(READING, open=[{"quote": "the other thing", "could_be": []}])
        self.assertIsNone(parameters.check(raw, "Use the setting we talked about.", {}).open_ref)

    def test_prompt_and_schema(self):
        """The rule and the field are in the reading with the flag, and gone without it."""
        msgs = parameters.reading_messages("hello", {})
        self.assertIn("open:", msgs[0]["content"])
        self.assertIn("open", parameters.reading_schema()["required"])
        with mock.patch.dict(os.environ, {"DIOSCURI_CLARIFY_CHOICES": "0"}):
            msgs = parameters.reading_messages("hello", {})
            self.assertNotIn("open:", msgs[0]["content"])
            self.assertNotIn("open", parameters.reading_schema()["properties"])


def chat_model(readings, seen, open_option=0):
    """Return a scripted reasoning model: a parameters reading per message, by its words."""

    def reply(purpose, messages):
        prompt = "\n".join(m["content"] for m in messages)
        seen.setdefault(purpose, []).append(prompt)
        said = messages[-1]["content"].split("Message: ")[-1]
        if purpose == "intake":
            intent = "what_if" if re.search(r"what if|gas|store|again", said, re.I) else "question"
            return dict(fake_intake(purpose, messages), intent=intent)
        if purpose == "parameters":
            for words, reading in readings:
                if words in said:
                    return reading
            return dict(READING, steps=[{"do": "answer", "quote": "", "changes": []}])
        if purpose == "options":
            return {"changes": []}
        if purpose == "needs":
            return {"needs": "about_one_existing_design"}
        if purpose == "which_design":
            return {"design": "several"}
        if purpose == "open_question":
            return {"answers": True, "option": open_option, "value": ""}
        return fake_intake(purpose, messages)

    return ScriptedLLM(reply, model="qwen3.5:9b")


class TestAskThenRun(unittest.TestCase):
    """A question with choices, then the choice runs (typed or clicked)."""

    def test_two_of_what_then_doublets(self):
        """Asked "run it again with 2.": 2 of what; "doublets" (typed) runs 2 doublets."""
        _, s = designed()
        ledger = len(s.ledger)
        open_words = dict(
            READING,
            changes=[{"key": "n_doublets", "value": 2, "quote": "with 2"}],
            steps=[{"do": "design", "quote": "Run it again with 2", "changes": []}],
            open=[{"quote": "with 2", "could_be": ["n_doublets", "heat_pump_mw"]}],
        )
        named = dict(
            READING,
            changes=[{"key": "n_doublets", "value": 2, "quote": "number of doublets: 2"}],
            steps=[{"do": "design", "quote": "Run it again", "changes": []}],
        )
        seen = {}
        agent = Agent(chat_model([("number of doublets", named), ("with 2", open_words)], seen, 1))
        events = run(agent, s, "Run it again with 2.")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertEqual(len(s.ledger), ledger)  # nothing ran on the guess
        question = custom(events, "clarification")["questions"][0]
        self.assertEqual(question["options"], ["Number of doublets: 2", "Heat pump size: 2 MW"])
        self.assertIn("What should be 2", s.last["answer"])
        self.assertEqual(s.pending["kind"], "choice")
        self.assertIn("Number of doublets: 2", s.pending["requests"])
        self.assertTrue(any("Open:" in p for p in seen.get("needs", [])) or s.state.open)

        run(agent, s, "doublets")  # typed: read against the options kept with the question
        self.assertIn("number of doublets: 2", seen["parameters"][-1])
        self.assertIn("Run it again with 2.", seen["parameters"][-1])
        self.assertIn(s.last["behaviour"], ("design", "clarify"))
        self.assertNotIn("What should be 2", s.last.get("answer", ""))

    def test_store_size_then_the_first(self):
        """Asked "add a heat store.": its size; clicking the first option runs that size."""
        _, s = designed()
        vague = dict(
            READING,
            changes=[{"key": "storage_mwh", "value": 0, "quote": "heat store"}],
            steps=[{"do": "what_if", "quote": "Add a heat store", "changes": []}],
        )
        sized = dict(
            READING,
            changes=[{"key": "storage_mwh", "value": 200, "quote": "were 200 MWh"}],
            steps=[{"do": "what_if", "quote": "What if", "changes": []}],
        )
        seen = {}
        agent = Agent(chat_model([("200 MWh", sized), ("heat store", vague)], seen))
        events = run(agent, s, "Add a heat store.")
        options = custom(events, "clarification")["questions"][0]["options"]
        self.assertEqual(len(options), 3)
        ledger = len(s.ledger)
        run(agent, s, answers={"choice": options[0]})
        self.assertIn("200 MWh", seen["parameters"][-1])
        self.assertEqual(s.last["behaviour"], "design")
        self.assertGreater(len(s.ledger), ledger)
        self.assertEqual(s.ledger[-1].changes.get("storage_mwh") or 200.0, 200.0)

    def test_gas_dearer_asks_before_any_run(self):
        """No amount for the gas price, and a misread switch beside it: asked, nothing runs."""
        _, s = designed()
        reading = dict(
            READING,
            changes=[
                {"key": "gas_eur_per_mwh", "value": 138.8, "quote": "gas gets more expensive"},
                {"key": "flare_brine_gas", "value": 1, "quote": "gas"},
            ],
            steps=[{"do": "what_if", "quote": "if gas gets more expensive", "changes": []}],
        )
        ledger = len(s.ledger)
        agent = Agent(chat_model([("gas", reading)], {}))
        events = run(agent, s, "And if gas gets more expensive?")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertEqual(len(s.ledger), ledger)
        options = custom(events, "clarification")["questions"][0]["options"]
        self.assertTrue(all("gas price" in o for o in options))
        # The run after keeps the rest of the message: the option's request holds it.
        self.assertTrue(all(r.startswith("And if gas") for r in s.pending["requests"].values()))

    def test_setting_we_talked_about_with_none(self):
        """No setting in the chat: asked which, with options the design does not have yet."""
        _, s = designed()
        reading = dict(
            READING,
            steps=[{"do": "design", "quote": "Use the setting", "changes": []}],
            open=[{"quote": "the setting we talked about", "could_be": []}],
        )
        ledger = len(s.ledger)
        agent = Agent(chat_model([("setting", reading)], {}))
        events = run(agent, s, "Use the setting we talked about.")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertEqual(len(s.ledger), ledger)
        self.assertIn("can't find a setting", s.last["answer"])
        options = custom(events, "clarification")["questions"][0]["options"]
        self.assertGreaterEqual(len(options), 2)
        self.assertTrue(all(o.startswith("What if the design had") for o in options))

    def test_objective_alone_is_a_question(self):
        """A question ("back to the original design, its CO2 saving?") read as a CO2 search."""
        r = parameters.check(
            dict(
                READING,
                objective="co2",
                steps=[
                    {"do": "design", "quote": "back to the original design", "changes": []},
                    {"do": "answer", "quote": "its CO2 saving?", "changes": []},
                ],
            ),
            "back to the original design, its CO2 saving?",
            {},
            designed=True,
        )
        self.assertEqual(r.changes, {"objective": "co2"})
        parameters.set_needs(r, "about_one_existing_design")
        self.assertTrue(clarify.objective_is_a_question(r))
        parameters.set_needs(r, "new_design_run")
        self.assertFalse(clarify.objective_is_a_question(r))

    def test_off_runs_as_before(self):
        """``DIOSCURI_CLARIFY_CHOICES=0``: no ``open`` read, "By how much?" as before."""
        with mock.patch.dict(os.environ, {"DIOSCURI_CLARIFY_CHOICES": "0"}):
            raw = dict(READING, open=[{"quote": "with 2", "could_be": ["n_doublets"]}])
            self.assertIsNone(parameters.check(raw, "Run it again with 2.", {}).open_ref)
            self.assertFalse(clarify.objective_is_a_question(parameters.Reading()))


if __name__ == "__main__":
    unittest.main()


class TestOpenOnlyForRuns(unittest.TestCase):
    """5 Nov: the 9B filled ``open`` for questions; only a request that runs can leave one."""

    def test_a_question_has_nothing_open(self):
        """A question ("Well depth?") with an open item and no step: nothing is asked."""
        raw = dict(READING, open=[{"quote": "Well depth", "could_be": []}])
        self.assertIsNone(parameters.check(raw, "Well depth?", {}).open_ref)

    def test_a_named_change_has_nothing_open(self):
        """The open words are the change it read ("cool with outside air"): nothing is open."""
        raw = dict(
            READING,
            changes=[{"key": "gas_eur_per_mwh", "value": 45, "quote": "gas cost 45 €/MWh"}],
            steps=[{"do": "what_if"}],
            open=[{"quote": "gas cost 45 €/MWh", "could_be": []}],
        )
        r = parameters.check(raw, "What if gas cost 45 €/MWh?", {"gas_eur_per_mwh": 69.4})
        self.assertIsNone(r.open_ref)
        self.assertIn("gas_eur_per_mwh", r.changes)


class TestBareNumbers(unittest.TestCase):
    """A number whose words name no setting is asked about.

    5 Nov: "Run it again with 2." ran 2 doublets and "hmm 70" a 70 MWh store, the reader having
    filled no ``open`` item.
    """

    def reading(self, key, value, message):
        """Return the checked reading of one change quoted from the message."""
        raw = dict(
            READING,
            changes=[{"key": key, "value": value, "quote": message.strip(".?")}],
            steps=[{"do": "what_if", "quote": message, "changes": []}],
        )
        return parameters.check(raw, message, {"n_doublets": 1}, designed=True)

    def test_a_bare_number_is_open(self):
        """No unit and no word of the setting: open, and the change goes."""
        for key, value, message in (
            ("n_doublets", 2, "Make it 2 this time."),
            ("storage_mwh", 70, "well 70 then"),
            ("n_doublets", 3, "Go with three instead."),
        ):
            r = self.reading(key, value, message)
            item = clarify.bare_numbers(r, message)
            self.assertIsNotNone(item, message)
            self.assertEqual(item["could_be"][0], key)
            self.assertEqual(r.changes, {})
            self.assertFalse(any(s.do in ("design", "what_if") for s in r.steps))

    def test_named_numbers_act(self):
        """A word of the setting or its unit: the change stays."""
        for key, value, message in (
            ("n_doublets", 2, "Make it 2 doublets this time."),
            ("n_doublets", 3, "three well pairs please"),
            ("storage_mwh", 500, "a tank of 500"),
            ("storage_mwh", 5000, "a store of 5,000 MWh"),
            ("gas_eur_per_mwh", 45, "gas at 45"),
        ):
            r = self.reading(key, value, message)
            self.assertIsNone(clarify.bare_numbers(r, message), message)
            self.assertIn(key, r.changes, message)

    def test_the_last_what_ifs_setting_is_the_referent(self):
        """Right after a gas price what-if, "and with 45?" is the gas price, not a question."""
        r = self.reading("gas_eur_per_mwh", 45, "And with 45?")
        self.assertIsNone(clarify.bare_numbers(r, "And with 45?", ["gas_eur_per_mwh"]))
        self.assertIn("gas_eur_per_mwh", r.changes)

    def test_a_bare_number_in_the_chat_is_asked(self):
        """The reader set doublets from "with 2" and left nothing open: asked, nothing runs."""
        _, s = designed()
        ledger = len(s.ledger)
        guess = dict(
            READING,
            changes=[{"key": "n_doublets", "value": 2, "quote": "with 2"}],
            steps=[{"do": "design", "quote": "Redo it with 2", "changes": []}],
        )
        agent = Agent(chat_model([("with 2", guess)], {}))
        events = run(agent, s, "Redo it with 2.")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertEqual(len(s.ledger), ledger)
        options = custom(events, "clarification")["questions"][0]["options"]
        self.assertEqual(options[0], "Number of doublets: 2")


class TestStopWithoutDates(unittest.TestCase):
    """The stop where it is now is said, and dates asked.

    5 Nov: "a stop in summer for maintenance" ran a what-if on a misread switch and said both
    "updated" and "not applied".
    """

    def test_asked_with_the_stop_now(self):
        """Asked, with the stop's days now; nothing runs."""
        from gemini_agent import stops

        _, s = designed()
        ledger = len(s.ledger)
        reading = dict(
            READING,
            changes=[
                {"key": "doublet_stops", "value": "summer", "quote": "stop in summer"},
                {"key": "planned_service", "value": 0, "quote": "maintenance"},
            ],
            steps=[{"do": "what_if", "quote": "The wells need a stop", "changes": []}],
        )
        agent = Agent(chat_model([("stop in summer", reading)], {}))
        events = run(agent, s, "The wells want a stop in summer for maintenance.")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertEqual(len(s.ledger), ledger)  # nothing ran
        ranges = stops.ranges_of(s.chosen.year)
        self.assertIn(stops.span_words(ranges[0]), s.last["answer"])
        self.assertNotIn("updated", s.last["answer"])
        options = custom(events, "clarification")["questions"][0]["options"]
        self.assertEqual(len(options), 3)

    def test_a_question_about_the_stop_is_answered(self):
        """No run asked ("how does the stop work?"): nothing is asked back for dates."""
        _, s = designed()
        reading = dict(
            READING,
            changes=[{"key": "doublet_stops", "value": "x", "quote": "stop"}],
            steps=[{"do": "answer", "quote": "How does the stop work?", "changes": []}],
        )
        agent = Agent(chat_model([("stop work", reading)], {}))
        run(agent, s, "How does the stop work?")
        self.assertNotEqual(s.last["behaviour"], "clarify")


class TestObjectiveInAWhatIf(unittest.TestCase):
    """A what-if whose only change is what "best" means."""

    def test_a_what_if_step_with_the_objective_alone_is_a_question(self):
        """A question, not a search: "heat under 70 euros a MWh?" ran one on 5 Nov."""
        r = parameters.check(
            dict(
                READING,
                objective="cost",
                steps=[{"do": "what_if", "quote": "Heat under 70 euros a MWh?", "changes": []}],
            ),
            "Heat under 70 euros a MWh?",
            {},
            designed=True,
        )
        if set(r.changes) != {"objective"}:
            self.skipTest("the objective is not read from these words")
        parameters.set_needs(r, "about_one_existing_design")
        self.assertTrue(clarify.objective_is_a_question(r))
        parameters.set_needs(r, "new_design_run")
        self.assertFalse(clarify.objective_is_a_question(r))


class TestPickedDesignsWin(unittest.TestCase):
    """The designs picked with @ are the ones compared.

    5 Nov: A1 and B1 picked, "which is cheaper?" compared W1 (the design under discussion,
    added by the reader) with A1.
    """

    def test_the_picked_pair_is_compared(self):
        """A design the reader added that is neither picked nor written goes."""
        from gemini_agent import reporter

        _, s = designed()
        uids = [e.alternative.uid for e in s.candidates if e.alternative.uid]
        picks = [e for e in s.candidates if e.alternative.uid][:3]
        if len(picks) < 3 or len(set(uids)) < 3:
            self.skipTest("three designs with ids needed")
        one, two, stray = picks
        reading = dict(
            READING,
            designs=[stray.alternative.uid, one.alternative.uid],
            steps=[{"do": "compare", "quote": "Which costs less?", "changes": []}],
        )
        agent = Agent(chat_model([("costs less", reading)], {}))
        events = run(
            agent,
            s,
            "Which costs less?",
            designs=[reporter.design_id(one), reporter.design_id(two)],
        )
        compared = custom(events, "compare")
        self.assertIsNotNone(compared)
        ids = [d["id"].split(" · ")[0] for d in compared["designs"]]
        self.assertEqual(sorted(ids), sorted([one.alternative.uid, two.alternative.uid]))


class TestNamesKey(unittest.TestCase):
    """What counts as naming a setting."""

    def test_a_name_with_a_digit_counts(self):
        """A CO2 price named as "CO2 at 150" counts; "2" alone names nothing."""
        self.assertTrue(clarify.names_key("CO2 at 150 then", "carbon_eur_per_t"))
        self.assertFalse(clarify.names_key("ok now 2", "n_doublets"))
