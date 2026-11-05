"""Before the first design the user checks the inputs; what-ifs change any input the model has."""

import unittest

from gemini_agent import Agent
from gemini_agent.agent import Session
from gemini_agent.llm import ScriptedLLM
from gemini_agent.reporter import CHANGE_OPTION, RUN_OPTION
from unit_test.gemini_agent.test_agent import FULL_BRIEF, custom, fake_intake, run


class TestConfirmInputs(unittest.TestCase):
    """The first design of a chat shows what was read and assumed, and waits for a yes."""

    def setUp(self):
        """Make a scripted agent and a new conversation."""
        self.agent = Agent(ScriptedLLM(fake_intake))
        self.s = Session()

    def test_the_card_comes_first_with_sources(self):
        """Every row says where it comes from; nothing is designed yet."""
        ev = run(self.agent, self.s, FULL_BRIEF, confirm=False)
        card = custom(ev, "confirm_inputs")
        self.assertIsNotNone(card)
        self.assertEqual(self.s.pending["kind"], "confirm")
        self.assertIsNone(self.s.chosen)
        labels = {r["label"]: r for r in card["rows"]}
        self.assertIn("GEMINI_Heating_Demand_Daily_2027.csv", labels["Heat"]["source"])
        self.assertEqual(labels["Temperature"]["kind"], "derived")
        self.assertEqual(labels["Heating network"]["kind"], "assumed")
        self.assertEqual(card["options"], [RUN_OPTION, CHANGE_OPTION])
        self.assertEqual(ev[-1]["outcome"]["interrupts"][0]["reason"], "confirm")

    def test_the_button_runs_the_design_once(self):
        """Run: the design follows; a second request does not ask again."""
        run(self.agent, self.s, FULL_BRIEF, confirm=False)
        run(self.agent, self.s, answers={"confirm": RUN_OPTION}, confirm=False)
        self.assertEqual(self.s.last["behaviour"], "design")
        self.assertIsNotNone(self.s.chosen)
        run(
            self.agent,
            self.s,
            "Design the heating and cooling without heat pumps.",
            confirm=False,
        )
        self.assertEqual(self.s.last["behaviour"], "design")

    def test_a_typed_yes_runs_it(self):
        """A reply in words is read by the model, not by a list of words."""
        run(self.agent, self.s, FULL_BRIEF, confirm=False)
        run(self.agent, self.s, "yes, go ahead", confirm=False)
        self.assertEqual(self.s.last["behaviour"], "design")

    def test_a_typed_change_shows_the_card_again(self):
        """Use a 50 °C heating return: the card again, with the change marked."""
        run(self.agent, self.s, FULL_BRIEF, confirm=False)
        ev = run(self.agent, self.s, "use a heating return of 50 °C", confirm=False)
        card = custom(ev, "confirm_inputs")
        self.assertIn("heat_return_c", card["changed"])
        heating = next(r for r in card["rows"] if r["label"] == "Heating network")
        self.assertIn("return 50 °C", heating["value"])
        run(self.agent, self.s, answers={"confirm": RUN_OPTION}, confirm=False)
        self.assertEqual(self.s.chosen.brief.heating.return_c, 50.0)

    def test_change_button_asks_what_to_change(self):
        """The second button keeps the card open and asks what to change."""
        run(self.agent, self.s, FULL_BRIEF, confirm=False)
        run(self.agent, self.s, answers={"confirm": CHANGE_OPTION}, confirm=False)
        self.assertEqual(self.s.pending["kind"], "confirm")
        self.assertIn("What should I change?", self.s.last["answer"])


class TestWhatIf(unittest.TestCase):
    """A what-if on any input: the same plant under the change, and the search again."""

    @classmethod
    def setUpClass(cls):
        """One design to ask about."""
        cls.agent = Agent(ScriptedLLM(fake_intake))
        cls.s = Session()
        # At the known aquifer, where a lower return lets the exchanger give more (at 3,500 m
        # the brine leaves at the 40 K cap whatever the return).
        cls.s.brief = cls.s.brief.model_copy(update={"doublet_depths_m": [2500.0]})
        run(cls.agent, cls.s, FULL_BRIEF)
        cls.base = cls.s.chosen

    def test_a_lower_heating_return_is_run(self):
        """The screenshot's question runs the design with a 50 °C return and searches again."""
        searches = len(self.s.searches)
        run(
            self.agent,
            self.s,
            "What happens to the design if we lower the heating return temperature to 50 °C?",
        )
        self.assertEqual(self.s.last["behaviour"], "design")
        new = self.s.ledger[-1]
        self.assertEqual(new.brief.heating.return_c, 50.0)
        self.assertEqual(new.changes, {"heat_return_c": 50.0})
        self.assertEqual(new.alternative.sizes_mw, self.base.alternative.sizes_mw)
        self.assertGreater(new.year.heat_split_gwh["geo"], self.base.year.heat_split_gwh["geo"])
        self.assertEqual(len(self.s.searches), searches + 1)
        self.assertIn("what-if", self.s.searches[-1]["label"])
        self.assertIn("Searching again under the change picks", self.s.last["answer"])
        self.assertIs(self.s.chosen, self.base)  # the design talked about stays the same

    def test_what_is_not_modelled_is_said(self):
        """A solar field is not an input of the model: said plainly, nothing is run."""
        n = len(self.s.ledger)
        run(self.agent, self.s, "What if we add a solar field to the design?")
        self.assertEqual(len(self.s.ledger), n)
        self.assertIn("I can't vary a solar field", self.s.last["answer"])


if __name__ == "__main__":
    unittest.main()


class TestPanelFixes(unittest.TestCase):
    """Fixes from the review panel of 31 Oct."""

    def test_a_relaxed_cap_is_still_checked_against_the_challenge(self):
        """365 days asked: the design is run so, and the 330-day check fails and says why."""
        from gemini_agent import engine
        from gemini_agent.contract import DesignBrief

        out = engine.search(DesignBrief(rules={"operating_days": 365}))
        check = next(c for c in out.chosen.verification.checks if "days" in c.name)
        self.assertEqual(check.name, "At most 330 days per doublet")
        self.assertFalse(check.passed)
        self.assertIn("365 days as you asked", check.detail)

    def test_a_later_search_keeps_the_first_pick(self):
        """Two searches with the same code: two designs, the later one named by its search."""
        from gemini_agent import reporter

        s = Session()
        run(Agent(ScriptedLLM(fake_intake)), s, FULL_BRIEF)
        first = s.chosen.model_copy(deep=True)
        later = first.model_copy(deep=True)
        later.alternative.attempt, later.alternative.uid = "S3", "C1"
        self.assertEqual(
            reporter.design_id(first), f"{first.alternative.uid} · {first.alternative.code}"
        )
        self.assertEqual(reporter.design_id(later), f"C1 · {first.alternative.code}")
        older = first.model_copy(deep=True)  # saved before names: the code and its search
        older.alternative.attempt, older.alternative.uid = "S3", ""
        self.assertEqual(reporter.design_id(older), f"{first.alternative.code} · S3")

    def test_units_people_use_are_read(self):
        """12 ct/kWh, zwei, 140 °F and 50 l/s are read; 500 °C is reported, not used."""
        from gemini_agent import parameters as p

        def read(key, value, quote):
            r = p.check({"changes": [{"key": key, "value": value, "quote": quote}]}, quote)
            return r.changes, r.unread

        self.assertEqual(
            read("electricity_eur_per_mwh", 120, "12 ct/kWh")[0], {"electricity_eur_per_mwh": 120.0}
        )
        self.assertEqual(read("n_doublets", 2, "zwei Dubletten")[0], {"n_doublets": 2})
        self.assertEqual(read("heat_return_c", 60, "a 140 °F return")[0], {"heat_return_c": 60.0})
        self.assertEqual(read("flow_max_m3h", 180, "50 l/s")[0], {"flow_max_m3h": 180.0})
        changes, unread = read("heat_return_c", 500, "a 500 °C return")
        self.assertEqual(changes, {})
        self.assertIn("outside", unread[0][1])

    def test_gemini_loop_agrees_with_the_plant_model(self):
        """Pumps at 70 %, the train sized for its flow: no negative pressure, same powers."""
        from gemini_agent import workbench
        from gemini_agent.tools import gemini

        for doublets in ([{}], [{}, {}], [{"injectors": 2}, {"train": 1}]):
            res = workbench.run_gemini(gemini.plant_project(doublets, None, 10.0))
            self.assertTrue(res["ok"])
            self.assertEqual(res["warnings"], [])
            esp = sum(
                v.get("esp_power_el", 0)
                for k, v in res["outputs"].items()
                if k.startswith("producer")
            )
            # 0.450 MW a doublet at 300 m3/h since the doublet's index (11.7 m3/h/bar, 4 Nov
            # audit): 4.97 bar more drawdown than the single well's 14.5 (0.391 MW before).
            self.assertAlmostEqual(esp / 1e6, 0.450 * len(doublets), delta=0.01)

    def test_money_facts_for_the_answerer(self):
        """The gas reference, yearly totals, payback and prices are computed by code."""
        from gemini_agent import answer, engine
        from gemini_agent.contract import DesignBrief

        lines = " ".join(answer.money_lines(engine.search(DesignBrief()).chosen))
        self.assertIn("with gas, so cheaper than gas", lines)
        self.assertIn("discounted payback", lines)
        self.assertIn("Not in these costs", lines)

    def test_a_blank_message_costs_no_model_call(self):
        """Spaces only: asked like any unreadable message, with no model call."""
        s = Session()
        llm = ScriptedLLM(fake_intake)
        run(Agent(llm), s, "   ")
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("empty", s.last["answer"])
        self.assertEqual(llm.calls, [])
