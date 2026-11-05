"""The inputs card keeps its values until the user confirms something valid (5 Nov).

"Add a 4th doublet at 100 m" at the inputs card left one aquifer at 100 m on it (the small
reader's depth past the reasoning reading's refusal), and "get back to default values" then ran
a design with it. The models read the meaning (scripted here); code checks the result: the limits,
an add against a replacement, and what a reset puts back.
"""

import unittest
from unittest import mock

from gemini_agent import Agent, aquifers, card_edits, intake, parameters
from gemini_agent.agent import Session
from gemini_agent.contract import DesignBrief
from gemini_agent.llm import ScriptedLLM
from gemini_agent.reporter import RESET_OPTION, RUN_OPTION
from unit_test.gemini_agent.test_agent import FULL_BRIEF, custom, fake_intake, fake_parameters

DEFAULT_DEPTHS = [2500.0, 3000.0, 3500.0]


def change(key, value, quote, step=0):
    """Return one change of a scripted reading."""
    return {"key": key, "value": value, "quote": quote, "step": step}


class Script:
    """A scripted model: the readings, the confirm decisions and the add-or-replace answers.

    ``readings``: message -> the planner's reading; ``decisions``: reply -> run, change, reset
    or other; ``ops``: message -> add or replace; ``depths``: message -> the small reader's
    depths. Everything else is ``fake_intake``'s.
    """

    def __init__(self, readings=None, decisions=None, ops=None, depths=None):
        """Keep the scripted answers and a record of what was asked."""
        self.readings = readings or {}
        self.decisions = decisions or {}
        self.ops = ops or {}
        self.depths = depths or {}
        self.asked = []  # (purpose, message) of every call

    def __call__(self, purpose, messages):
        """Answer one call as the scripted model would."""
        said = messages[-1]["content"]
        if purpose == "confirm":
            reply = said.split("Reply: ")[-1].strip()
            self.asked.append((purpose, reply))
            return {"decision": self.decisions.get(reply, "other")}
        if purpose in ("parameters", "parameters_again"):
            message = said.split("Message: ", 1)[-1].strip()
            self.asked.append((purpose, message))
            if message in self.readings:
                return self.readings[message]
            return fake_parameters(messages)
        if purpose == "list_op":
            message = said.split("Message: ", 1)[-1].strip()
            self.asked.append((purpose, message))
            return {"op": self.ops.get(message, "unclear")}
        if purpose == "options":
            return {"changes": []}
        out = fake_intake(purpose, messages)
        if purpose == "intake":
            message = said.split("Message: ")[-1].strip()
            out = dict(out, depths_m=self.depths.get(message, []))
        return out


def card_depths(event):
    """Return the aquifers' depths an inputs card shows."""
    for row in event["rows"]:
        for f in row.get("fields") or []:
            if f["key"] == "aquifers":
                return [r["depth_m"] for r in f["value"]]
    return None


def pending_depths(session):
    """Return the aquifers' depths of the card waiting for a go-ahead."""
    return [r["depth_m"] for r in aquifers.value_of(DesignBrief(**session.pending["brief"]))]


ADD_100 = "add a 4th doublet at 100 m"
ADD_4200 = "put one more well pair in at 4,200 metres"
RETURN_50 = "use a heating return of 50 °C"
READINGS = {
    ADD_100: {
        "changes": [
            change("n_doublets", 4, "a 4th doublet"),
            change("aquifer_depths_m", [100], "at 100 m"),
        ],
        "steps": [{"do": "design", "quote": ADD_100}],
    },
    ADD_4200: {
        "changes": [change("aquifer_depths_m", [4200], "at 4,200 metres")],
        "steps": [{"do": "design", "quote": ADD_4200}],
    },
}


class TestARefusedChangeKeepsTheCard(unittest.TestCase):
    """A typed change past a limit: nothing of it applies, the card says why and stays."""

    def setUp(self):
        """Open the challenge's inputs card and leave it waiting."""
        self.script = Script(
            READINGS,
            decisions={ADD_100: "change", ADD_4200: "change", RETURN_50: "change"},
            # The small reader takes "100 m" as a depth (it did on 5 Nov).
            depths={ADD_100: [100]},
        )
        self.agent = Agent(ScriptedLLM(self.script))
        self.s = Session()
        list(self.agent.run(self.s, FULL_BRIEF))
        self.assertEqual(self.s.pending["kind"], "confirm")

    def test_a_4th_doublet_at_100_m(self):
        """Said, not applied: the three aquifers and 1 to 3 doublets stay; read once."""
        ev = list(self.agent.run(self.s, ADD_100))
        card = custom(ev, "confirm_inputs")
        self.assertEqual(card_depths(card), DEFAULT_DEPTHS)
        self.assertEqual(pending_depths(self.s), DEFAULT_DEPTHS)
        brief = DesignBrief(**self.s.pending["brief"])
        self.assertIsNone(brief.n_doublets)
        self.assertEqual(brief.doublet_depths_m, [])
        notice = card["notice"]
        self.assertEqual((notice["kind"], notice["title"]), ("refused", "Nothing changed"))
        said = " ".join(notice["lines"])
        self.assertIn("Doublets 4: outside 1 to 3", said)
        self.assertIn("Well depth 100 m: outside 500 to 7,000 m", said)
        self.assertIn("about 15 °C", said)  # 12 °C + 30 °C/km × 0.1 km
        self.assertIn("3 aquifers at 2,500, 3,000 and 3,500 m", notice["offer"])
        # Nothing on a field: the card's values are the valid ones, so it can run.
        self.assertEqual(card["errors"], {})
        self.assertIn("Nothing changed.", self.s.last["answer"])
        self.assertIsNone(self.s.chosen)
        # One reading of the reply: no second route with the small reader's own values.
        readings = [m for p, m in self.script.asked if p == "parameters"]
        self.assertEqual(readings.count(ADD_100), 1)

    def test_then_run_uses_what_the_card_shows(self):
        """The Run that follows runs the three aquifers, never 100 m."""
        list(self.agent.run(self.s, ADD_100))
        list(self.agent.run(self.s, answers={"confirm": RUN_OPTION}))
        self.assertEqual(self.s.last["behaviour"], "design")
        tried = {float(d.get("depth_m") or 0) for d in self.s.chosen.alternative.doublets}
        self.assertTrue(tried and tried <= set(DEFAULT_DEPTHS))
        self.assertEqual(self.s.chosen.brief.doublet_depths_m, [])

    def test_one_more_well_pair_is_an_add_past_three(self):
        """The model says add; the three there and one more is four: refused, said why."""
        self.script.ops[ADD_4200] = "add"
        ev = list(self.agent.run(self.s, ADD_4200))
        card = custom(ev, "confirm_inputs")
        self.assertEqual(card_depths(card), DEFAULT_DEPTHS)
        said = " ".join(card["notice"]["lines"])
        self.assertIn("there are 3 aquifers already (2,500, 3,000, 3,500 m)", said)
        self.assertIn("at most 3: say which one 4,200 m should replace", said)
        self.assertIn(("list_op", ADD_4200), self.script.asked)

    def test_an_add_keeps_the_aquifers_there(self):
        """With two aquifers, one more joins them: never a list of the new one alone."""
        self.s.pending["brief"]["doublet_depths_m"] = [2500.0, 3000.0]
        self.script.ops[ADD_4200] = "add"
        ev = list(self.agent.run(self.s, ADD_4200))
        card = custom(ev, "confirm_inputs")
        self.assertIsNone(card.get("notice"))
        self.assertEqual(card_depths(card), [2500.0, 3000.0, 4200.0])

    def test_a_replacement_stays_one(self):
        """The model says replace: the depth it names is the list."""
        self.script.ops[ADD_4200] = "replace"
        ev = list(self.agent.run(self.s, ADD_4200))
        self.assertEqual(card_depths(custom(ev, "confirm_inputs")), [4200.0])

    def test_a_change_within_limits_still_applies(self):
        """A 50 °C return: the card again with it, no notice, no list question."""
        ev = list(self.agent.run(self.s, RETURN_50))
        card = custom(ev, "confirm_inputs")
        self.assertIn("heat_return_c", card["changed"])
        self.assertIsNone(card.get("notice"))
        self.assertFalse(card["at_defaults"])
        self.assertNotIn("list_op", [p for p, _ in self.script.asked])


class TestReset(unittest.TestCase):
    """Back to the project's defaults, typed in any words or with the card's button."""

    def setUp(self):
        """Open the card, change the heating return and leave an aquifer list unconfirmed."""
        self.script = Script(
            READINGS,
            decisions={
                RETURN_50: "change",
                "get back to default values": "reset",
                "use the original numbers": "reset",
            },
        )
        self.agent = Agent(ScriptedLLM(self.script))
        self.s = Session()
        list(self.agent.run(self.s, FULL_BRIEF))
        list(self.agent.run(self.s, RETURN_50))
        self.s.pending["brief"]["doublet_depths_m"] = [4200.0]  # an unconfirmed edit
        self.s.pending["brief"]["rules"]["network_length_km"] = 5.0

    def check_reset(self, ev):
        """Check the card again at the defaults, a note of what went back, and nothing run."""
        card = custom(ev, "confirm_inputs")
        self.assertEqual(card_depths(card), DEFAULT_DEPTHS)
        self.assertTrue(card["at_defaults"])
        self.assertEqual(card["notice"]["kind"], "reset")
        put_back = card["notice"]["lines"][0]
        for words in ("heating network return", "aquifers (3 aquifers", "network heat losses"):
            self.assertIn(words, put_back)
        brief = DesignBrief(**self.s.pending["brief"])
        self.assertTrue(card_edits.at_defaults(brief))
        self.assertEqual(brief.heating.return_c, 60.0)  # the project's own network
        self.assertEqual(self.s.pending["kind"], "confirm")
        self.assertEqual(self.s.last["behaviour"], "clarify")
        self.assertIsNone(self.s.chosen)
        return card

    def test_typed_in_any_words(self):
        """The model reads the reply as a reset: code puts back every input."""
        for words in ("get back to default values", "use the original numbers"):
            with self.subTest(words=words):
                self.setUp()
                self.check_reset(list(self.agent.run(self.s, words)))
                self.assertIn("Back to the project's defaults.", self.s.last["answer"])

    def test_the_cards_button(self):
        """The button sends the reset option: no model call reads it."""
        before = len(self.script.asked)
        self.check_reset(list(self.agent.run(self.s, answers={"confirm": RESET_OPTION})))
        self.assertEqual(self.script.asked[before:], [])
        self.assertEqual(self.s.history[-1]["user"], RESET_OPTION)

    def test_run_after_a_reset_runs_the_defaults(self):
        """The run that follows has the 60 °C return and the three aquifers."""
        list(self.agent.run(self.s, "get back to default values"))
        list(self.agent.run(self.s, answers={"confirm": RUN_OPTION}))
        self.assertEqual(self.s.last["behaviour"], "design")
        self.assertEqual(self.s.chosen.brief.heating.return_c, 60.0)
        self.assertEqual(self.s.chosen.brief.doublet_depths_m, [])
        self.assertEqual(self.s.chosen.brief.rules.get("network_length_km", 0.0), 0.0)


class TestMovedAway(unittest.TestCase):
    """A change shown on a card the user then leaves for a new request is not carried on."""

    def test_a_new_request_starts_from_the_chats_inputs(self):
        """The 50 °C return was never run: the new request's card and its run have 60 °C."""
        new = "Design heating and cooling for the district with gas at 45 €/MWh"
        script = Script(decisions={RETURN_50: "change", new: "other"})
        agent = Agent(ScriptedLLM(script))
        s = Session()
        list(agent.run(s, FULL_BRIEF))
        list(agent.run(s, RETURN_50))
        self.assertEqual(DesignBrief(**s.pending["brief"]).heating.return_c, 50.0)
        ev = list(agent.run(s, new))
        card = custom(ev, "confirm_inputs")
        self.assertIsNotNone(card)
        brief = DesignBrief(**s.pending["brief"])
        self.assertEqual(brief.heating.return_c, 60.0)
        self.assertEqual(brief.prices.get("gas_eur_per_mwh"), 45.0)
        list(agent.run(s, answers={"confirm": RUN_OPTION}))
        self.assertEqual(s.chosen.brief.heating.return_c, 60.0)


class TestCodeChecks(unittest.TestCase):
    """The checks behind the readings, without the agent."""

    def test_the_small_reader_keeps_depths_in_range(self):
        """Its 100 m is no depth to drill to: dropped and said in the trace."""
        llm = ScriptedLLM([dict(fake_intake("intake", [{"content": "x"}]), depths_m=[100])])
        out = intake.read_message("add a doublet at 100 m depth", llm)
        self.assertNotIn("doublet_depths_m", out.updates)
        self.assertIn("depth 100 m (outside 500-7000 m)", out.dropped)
        llm = ScriptedLLM([dict(fake_intake("intake", [{"content": "x"}]), depths_m=[])])
        out = intake.read_message("drill the doublets to 3,200 m depth", llm)
        self.assertEqual(out.updates["doublet_depths_m"], [3200.0])

    def test_a_refused_value_keeps_its_value_on_the_first_message(self):
        """The small reader's depth for an input the reasoning reading refused does not stand.

        The small reader is let past its own range here, as a reader that missed it would be.
        """
        msg = "Design heating and cooling with the wells at 8 km depth"
        reading = {
            "changes": [change("aquifer_depths_m", [8000], "at 8 km depth")],
            "steps": [{"do": "design", "quote": msg}],
        }
        agent = Agent(ScriptedLLM(Script({msg: reading}, depths={msg: [8000]})))
        s = Session()
        with mock.patch.object(intake, "_depth_range", return_value=(0.0, 1e5)):
            ev = list(agent.run(s, msg))
        card = custom(ev, "confirm_inputs")
        self.assertEqual(card_depths(card), DEFAULT_DEPTHS)
        # No box holds the depths to try: the refusal is a note at the top, not a block.
        self.assertNotIn("aquifer_depths_m", card["errors"])
        self.assertEqual(card["notice"]["title"], "Not taken")
        self.assertIn("Well depth 8,000 m: outside 500 to 7,000 m", card["notice"]["lines"][0])

    def test_add_or_replace_is_asked_only_when_both(self):
        """A list that keeps every aquifer, or names only those there, needs no question."""
        now = {"aquifers": aquifers.resolved(DesignBrief())}
        r = parameters.Reading(changes={"aquifer_depths_m": [2500.0, 3500.0]})
        self.assertIsNone(parameters.list_drops_and_adds(r, now))
        r = parameters.Reading(changes={"aquifer_depths_m": DEFAULT_DEPTHS + [4000.0]})
        self.assertIsNone(parameters.list_drops_and_adds(r, now))
        r = parameters.Reading(changes={"aquifer_depths_m": [4000.0]})
        self.assertEqual(parameters.list_drops_and_adds(r, now), "aquifer_depths_m")
        new = dict(aquifers.value_of(DesignBrief())[0], depth_m=4000.0)
        r = parameters.Reading(changes={"aquifers": [aquifers.value_of(DesignBrief())[0], new]})
        self.assertEqual(parameters.list_drops_and_adds(r, now), "aquifers")

    def test_an_add_of_records_keeps_each_ones_rock(self):
        """Two aquifers there and one described: all three, the new one's values its own."""
        brief = DesignBrief(doublet_depths_m=[2500.0, 3000.0])
        now = {"aquifers": aquifers.resolved(brief)}
        new = dict(aquifers.value_of(brief)[0], depth_m=4000.0, gas_liquid_ratio=1.2)
        r = parameters.Reading(changes={"aquifers": [aquifers.value_of(brief)[0], new]})
        r.items = [("aquifers", r.changes["aquifers"], 0)]
        parameters.as_added(r, now, "aquifers", "add an aquifer at 4,000 m with a GLR of 1.2")
        rows = r.changes["aquifers"]
        self.assertEqual([x["depth_m"] for x in rows], [2500.0, 3000.0, 4000.0])
        self.assertEqual(rows[2]["gas_liquid_ratio"], 1.2)
        self.assertEqual(r.items[0][1], rows)

    def test_list_op_reads_the_model_and_falls_back_to_unclear(self):
        """Its answer, or unclear when the model gives none of the options."""
        op, _ = parameters.list_op("x", "1: 2500 m", ScriptedLLM([{"op": "add"}]))
        self.assertEqual(op, "add")
        op, _ = parameters.list_op("x", "1: 2500 m", ScriptedLLM([{"op": "both"}]))
        self.assertEqual(op, "unclear")
        op, _ = parameters.list_op("x", "1: 2500 m", ScriptedLLM([RuntimeError("down")]))
        self.assertEqual(op, "unclear")

    def test_confirm_reads_reset(self):
        """The prompt in use offers reset; an answer outside the four is other."""
        from gemini_agent.answer import load

        self.assertIn("reset when", load(parameters.CONFIRM_PROMPT))
        d, _ = parameters.confirm_decision("undo it", ScriptedLLM([{"decision": "reset"}]))
        self.assertEqual(d, "reset")
        d, _ = parameters.confirm_decision("undo it", ScriptedLLM([{"decision": "undo"}]))
        self.assertEqual(d, "other")

    def test_every_field_carries_its_default(self):
        """The card can mark a value that is not the project's own, and put it back."""
        from gemini_agent import CHALLENGE_PROJECT

        brief = parameters.apply(DesignBrief(), {"heat_return_c": 50.0, "gas_eur_per_mwh": 45.0})
        brief = brief.model_copy(update={"doublet_depths_m": [4200.0], "n_doublets": 2})
        from gemini_agent import reporter

        rows = card_edits.with_fields(reporter.inputs_rows(CHALLENGE_PROJECT, brief), brief, None)
        fields = {f["key"]: f for r in rows for f in r.get("fields") or []}
        self.assertEqual(
            (fields["heat_return_c"]["value"], fields["heat_return_c"]["default"]), (50.0, 60.0)
        )
        self.assertEqual(fields["gas_eur_per_mwh"]["value"], 45.0)
        self.assertNotEqual(fields["gas_eur_per_mwh"]["default"], 45.0)
        self.assertEqual(
            (fields["n_doublets"]["value"], fields["n_doublets"]["default"]), ("2", "")
        )
        self.assertEqual([r["depth_m"] for r in fields["aquifers"]["default"]], DEFAULT_DEPTHS)
        self.assertEqual([r["depth_m"] for r in fields["aquifers"]["value"]], [4200.0])
        self.assertFalse(card_edits.at_defaults(brief))
        self.assertTrue(card_edits.at_defaults(card_edits.defaults(brief)))
        self.assertTrue(card_edits.at_defaults(DesignBrief()))


if __name__ == "__main__":
    unittest.main()
