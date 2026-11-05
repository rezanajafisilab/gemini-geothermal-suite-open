"""What the plant model can do (``capabilities``): a card generated from the catalogues.

4 Nov: "Add a heat store", "Can we put PV on it?" and "cooling with outside air before the
chillers" were each answered "not modelled", though the plant has a store, solar panels and
free cooling.
"""

import os
import unittest
from unittest import mock

from gemini_agent import Agent, capabilities, parameters
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
    "steps": [{"do": "answer", "quote": "", "changes": []}],
    "open": [],
}


class TestCard(unittest.TestCase):
    """The card names every option of the plant, from the code's own lists."""

    def test_every_option_is_on_the_card(self):
        """The options, the stops, the units and the economics; each option by its key."""
        card = capabilities.card()
        for key in parameters.OPTION_KEYS + capabilities.STOPS:
            if key != "grid_t_co2_per_mwh":  # with the economics, by its name
                self.assertIn(key, card)
        self.assertIn("grid electricity's CO2", card)
        short = capabilities.answer_card()
        for words in (
            "free cooling",
            "own solar panels (PV)",
            "heat store at the plant",
            "HT-ATES",
            "second aquifer",
            "electric boiler",
            "CO2 reinjection",
            "doublet stops",
            "planned service",
            "gas price",
            "discount rate",
        ):
            self.assertIn(words, short)
        self.assertNotIn("1 on, 0 off", card)  # notes for code are not for a reader

    def test_a_new_option_is_on_the_card(self):
        """A parameter added to the options reading is on the card with its own label."""
        p = parameters.Parameter("Wind turbine at the plant (0: none)", "MW", 0, 50)
        with mock.patch.dict(parameters.CATALOGUE, {"wind_mw": p}):
            with mock.patch.object(
                parameters, "OPTION_KEYS", parameters.OPTION_KEYS + ("wind_mw",)
            ):
                self.assertIn("wind turbine at the plant", capabilities.answer_card())

    def test_cannot_text_lists_the_options(self):
        """The reply for what the model lacks lists the store, solar and free cooling."""
        text = capabilities.unsupported_text(["a wind turbine"])
        self.assertIn("a wind turbine", text)
        for words in ("heat store", "solar", "free cooling", "electric boiler"):
            self.assertIn(words, text)

    def test_off(self):
        """``DIOSCURI_CAPABILITY_CARD=0``: no block for the answerer."""
        self.assertIsNotNone(capabilities.block())
        with mock.patch.dict(os.environ, {"DIOSCURI_CAPABILITY_CARD": "0"}):
            self.assertIsNone(capabilities.block())


def option_model(reading, covers="none", seen=None):
    """Return a scripted reasoning model: this parameters reading, nothing from the options call."""

    def reply(purpose, messages):
        if seen is not None:
            seen.setdefault(purpose, []).append("\n".join(m["content"] for m in messages))
        if purpose == "intake":
            return dict(fake_intake(purpose, messages), intent="question")
        if purpose == "parameters":
            return reading
        if purpose == "options":
            return {"changes": []}
        if purpose == "needs":
            return {"needs": "about_one_existing_design"}
        if purpose == "covers":
            return {"key": covers}
        if purpose == "which_design":
            return {"design": "several"}
        return fake_intake(purpose, messages)

    return ScriptedLLM(reply, model="qwen3.5:9b")


class TestNeverNotModelled(unittest.TestCase):
    """An option filed as not modelled is checked against the card before any "cannot"."""

    def test_pv_asks_its_size(self):
        """Asked "can we put PV on it?": the card says solar panels; their size is asked."""
        _, s = designed()
        reading = dict(READING, unsupported=[{"what": "PV", "quote": "PV"}])
        seen = {}
        agent = Agent(option_model(reading, covers="solar_mwp", seen=seen))
        events = run(agent, s, "Can we put PV on it?")
        self.assertIn("covers", seen)
        self.assertIn("solar_mwp", seen["covers"][0])
        self.assertEqual(s.last["behaviour"], "clarify")
        asked = custom(events, "clarification")
        options = asked["questions"][0]["options"]
        self.assertGreaterEqual(len(options), 2)
        self.assertTrue(all("MWp" in o for o in options))
        self.assertNotIn("can't", s.last["answer"].lower())

    def test_store_and_not_modelled_in_one_reading(self):
        """A store without a size and "heat store" not modelled: the size is asked, no "cannot"."""
        _, s = designed()
        reading = dict(
            READING,
            changes=[{"key": "storage_mwh", "value": 0, "quote": "heat store"}],
            unsupported=[{"what": "heat store", "quote": "heat store"}],
            steps=[{"do": "what_if", "quote": "Add a heat store", "changes": []}],
        )
        seen = {}
        agent = Agent(option_model(reading, seen=seen))
        events = run(agent, s, "Add a heat store to the design.")
        self.assertNotIn("covers", seen)  # the same words as the store: no call needed
        self.assertEqual(s.last["behaviour"], "clarify")
        self.assertIn("What size for the heat store", s.last["answer"])
        options = custom(events, "clarification")["questions"][0]["options"]
        self.assertIn("What if the heat store at the plant were 5,000 MWh?", options)

    def test_something_the_model_lacks_lists_what_it_can(self):
        """A wind turbine is not an option: the reply says so and lists the options."""
        _, s = designed()
        reading = dict(READING, unsupported=[{"what": "a wind turbine", "quote": "wind turbine"}])
        agent = Agent(option_model(reading, covers="none"))
        run(agent, s, "Add a wind turbine to the design.")
        self.assertNotEqual(s.last["behaviour"], "clarify")
        self.assertEqual(s.last.get("unsupported"), ["a wind turbine"])

    def test_answerer_sees_the_card(self):
        """Every answer's context has the card (a question about cooling with outside air)."""
        _, s = designed()
        seen = {}
        agent = Agent(option_model(READING, seen=seen))
        run(agent, s, "Would cooling with outside air in winter, before the chillers, help?")
        self.assertIn("Plant options Dioscuri simulates", seen["answer"][-1])
        self.assertIn("free cooling", seen["answer"][-1])


if __name__ == "__main__":
    unittest.main()


class TestFreeCoolingSaid(unittest.TestCase):
    """What free cooling is, on the answerer's card."""

    def test_the_answer_card_says_free_cooling_is_outside_air(self):
        """Free cooling is the towers on cold outside air.

        5 Nov: "would cooling with outside air in winter, before the chillers, help?" got "I
        cannot simulate outside air ... free cooling (using groundwater)".
        """
        card = capabilities.answer_card()
        head = card.split("free cooling", 1)[1][:200]
        self.assertIn("outside air", head)
        self.assertIn("cooling towers", head)
