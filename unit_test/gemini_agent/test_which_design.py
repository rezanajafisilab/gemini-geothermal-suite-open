"""No design by default (3 Nov): the cards a message asks for, and asking which design."""

import types
import unittest

from gemini_agent import parameters
from unit_test.gemini_agent.test_naming import designed


class TestReading(unittest.TestCase):
    """The reading carries the cards asked for and whether the answer needs a design."""

    def test_needs(self):
        """What the reply needs sets the cards asked for, about_design and new_design."""
        cases = {
            "how_the_design_was_found": (["search"], False, False),
            "designs_side_by_side": (["comparison"], False, False),
            "about_one_existing_design": ([], True, False),
            "new_design_run": ([], False, True),
            "no_particular_design": ([], False, False),
        }
        for needs, (show, about, new) in cases.items():
            r = parameters.check({"needs": needs}, "Hello")
            self.assertEqual((r.show, r.about_design, r.new_design), (show, about, new), needs)
        self.assertIsNone(parameters.check({"needs": "chart"}, "Hello").about_design)

    def test_read_needs_from_a_model(self):
        """Its own short call; an unknown answer is None."""
        from gemini_agent.llm import ScriptedLLM

        llm = ScriptedLLM(lambda purpose, msgs: {"needs": "new_design_run"})
        self.assertEqual(parameters.read_needs("Another one, please", llm)[0], "new_design_run")
        llm = ScriptedLLM(lambda purpose, msgs: {"needs": "dance"})
        self.assertIsNone(parameters.read_needs("Another one, please", llm)[0])


class TestWhichDesign(unittest.TestCase):
    """A question about "the design" in a chat with several asks which, picks as options."""

    @classmethod
    def setUpClass(cls):
        """Design once."""
        cls.agent, cls.s = designed()

    def reading(self, **kw):
        """Return a reading as the model would give it."""
        base = dict(about_design=True, designs=[], steps=[], changes={}, failures=[])
        base.update(kw)
        return types.SimpleNamespace(**base)

    def test_asks_with_the_picks(self):
        """The picks, one option a design, each with its handle and code."""
        self.agent._picked = []
        options = self.agent._which_design(self.s, self.reading(), "What does heat cost?")
        if len({e.alternative.code for e in self.s.candidates if e.alternative.picks}) < 2:
            self.assertEqual(options, [])
            return
        self.assertGreaterEqual(len(options), 2)
        label, did = options[0]
        self.assertRegex(label, r"^[A-Z]\d+ · .+ \(.+\)$")
        self.assertIn("·", did)
        self.assertEqual(len({o[1] for o in options}), len(options))

    def test_no_ask_when_named_or_not_about_a_design(self):
        """@ or a design in the words, a general question, or a new design: no question back."""
        self.agent._picked = []
        for reading in (
            self.reading(about_design=False),
            self.reading(designs=["A1"]),
            self.reading(steps=[parameters.Step("design", "design it again")]),
        ):
            self.assertEqual(self.agent._which_design(self.s, reading, "What does it cost?"), [])
        self.agent._picked = [self.s.chosen]
        self.assertEqual(self.agent._which_design(self.s, self.reading(), "What does it cost?"), [])
        self.agent._picked = []


if __name__ == "__main__":
    unittest.main()


class TestAnotherDesign(unittest.TestCase):
    """Another design, in any words: the inputs card, ready to edit (3 Nov)."""

    def test_new_design_opens_the_card(self):
        """The reading says a new design is asked: the card, not a reply in words."""
        from gemini_agent import Agent, Session
        from gemini_agent.llm import ScriptedLLM
        from unit_test.gemini_agent.test_agent import custom, fake_intake, run
        from unit_test.gemini_agent.test_understanding import model

        def reply(purpose, messages):
            out = fake_intake(purpose, messages)
            if purpose == "needs":
                said = messages[-1]["content"]
                return {"needs": "new_design_run" if "another" in said else "no_particular_design"}
            if purpose == "route":
                return {"run_design": False}
            return out

        agent = Agent(model(), reasoning_llm=ScriptedLLM(reply, model="qwen3.5:9b"))
        s = Session()
        run(agent, s, "Design a geothermal heating and cooling system for this district.")
        events = run(agent, s, "Could I set up another one myself, with different choices?")
        card = custom(events, "confirm_inputs")
        self.assertIsNotNone(card)
        self.assertIsNotNone(card.get("again"))


class TestNamedInWords(unittest.TestCase):
    """Designs named without picking them: by code, by @id in any case, a drawn design."""

    @classmethod
    def setUpClass(cls):
        """Design once."""
        from unit_test.gemini_agent.test_naming import designed

        cls.agent, cls.s = designed()

    def test_code_and_at_ids(self):
        """4 Nov: a code typed without @ and "@a33" were not read; an e-mail is no id."""
        from gemini_agent.agent import named_in

        other = next(e for e in self.s.candidates if e.alternative.picks and e is not self.s.chosen)
        code, uid = other.alternative.code, other.alternative.uid
        self.assertEqual(named_in(f"what does {code} cost?", self.s), [other])
        self.assertEqual(named_in(f"what does {code.lower()} cost?", self.s), [other])
        self.assertEqual(named_in(f"and @{uid.lower()}?", self.s), [other])
        self.assertEqual(named_in(f"write to a@{uid.lower()} please", self.s), [])

    def test_a_drawn_design_is_opened_once(self):
        """The id @X3 opens the sweep's third drawn design (row 2) into the chat, once."""
        from gemini_agent.agent import named_in

        # Three rows of the challenge's sweep of 4 Nov, as the search keeps them.
        cols = ["doublets", "depth_m", "flow_cap_m3h", "heat_pump_mw", "boiler_mw"]
        cols += ["electric_boiler_mw", "absorption_mw", "chiller_mw", "gas", "lcoe", "lcoh"]
        cols += ["co2_t", "co2_saving_pct", "capex_meur", "broken"]
        rows = [
            [
                2,
                2800.0,
                100.0,
                8.4,
                4.2,
                19.2,
                0.6,
                0.0,
                "buy",
                134.13,
                134.34,
                11570.0,
                52.5,
                57.12,
                "cold",
            ],
            [
                3,
                3100.0,
                260.0,
                9.2,
                14.3,
                0.0,
                0.0,
                12.0,
                "produced",
                82.7,
                92.09,
                5080.0,
                79.1,
                89.46,
                "",
            ],
            [
                3,
                2900.0,
                280.0,
                5.3,
                4.9,
                4.5,
                3.7,
                0.0,
                "produced",
                83.34,
                77.04,
                6893.0,
                71.7,
                81.49,
                "cold",
            ],
        ]
        self.s.searches[-1]["sweep"] = {"columns": cols, "rows": rows}
        before = len(self.s.ledger)
        first = named_in("what does @X3 cost?", self.s)
        self.assertEqual([e.alternative.uid for e in first], ["X3"])
        self.assertEqual(named_in("and X3 again", self.s), first)
        self.assertEqual(len(self.s.ledger), before + 1)
