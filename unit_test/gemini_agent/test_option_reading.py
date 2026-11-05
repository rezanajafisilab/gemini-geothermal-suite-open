"""The plant's options read again on their own (3 Nov) when the long reading leaves them."""

import unittest

from gemini_agent import parameters
from gemini_agent.llm import ScriptedLLM

NOW = {k: 0.0 for k in parameters.OPTION_KEYS}


def scripted(changes):
    """Return a model that answers the options call with these changes."""
    return ScriptedLLM(lambda purpose, msgs: {"changes": changes})


class TestOptionReading(unittest.TestCase):
    """What the options call adds, and when it is asked."""

    def test_asked_only_when_something_is_left(self):
        """Something not modelled, a dropped change or a what-if with no change."""
        r = parameters.Reading()
        self.assertFalse(parameters.wants_options(r))
        r.unsupported = ["a 2 GWh buffer tank"]
        self.assertTrue(parameters.wants_options(r))
        idle = parameters.Reading(steps=[parameters.Step("what_if", "")])
        self.assertTrue(parameters.wants_options(idle))
        idle.changes = {"gas_eur_per_mwh": 40.0}
        self.assertFalse(parameters.wants_options(idle))
        self.assertFalse(parameters.wants_options(parameters.Reading(ok=False, dropped=["x"])))

    def test_a_store_in_gwh_replaces_the_unsupported_item(self):
        """'A 2 GWh buffer tank' is the store at 2,000 MWh, no longer not modelled."""
        msg = "Would a 2 GWh buffer tank cut the boiler's gas?"
        extra, _ = parameters.read_options(
            msg,
            scripted([{"key": "storage_mwh", "value": 2000, "quote": "a 2 GWh buffer tank"}]),
            NOW,
        )
        self.assertEqual(extra.changes, {"storage_mwh": 2000.0})
        r = parameters.Reading(unsupported=["a 2 GWh buffer tank"])
        self.assertEqual(parameters.merge_options(r, extra), ["storage_mwh"])
        self.assertEqual((r.changes, r.unsupported), ({"storage_mwh": 2000.0}, []))

    def test_checks_still_apply(self):
        """A size not in the words, or a key outside the options, is not taken."""
        msg = "Would a buffer tank cut the boiler's gas?"
        extra, _ = parameters.read_options(
            msg,
            scripted(
                [
                    {"key": "storage_mwh", "value": 5000, "quote": "a buffer tank"},
                    {"key": "gas_eur_per_mwh", "value": 1, "quote": "gas"},
                ]
            ),
            NOW,
        )
        self.assertEqual(extra.changes, {})
        self.assertIn("storage_mwh", extra.vague)  # asked for its size, never run with 5,000

    def test_switch_joins_the_what_if_step(self):
        """Winter electricity dirtier than summer's is the grid by month, in the what-if."""
        msg = "What changes if winter electricity is dirtier than summer's?"
        extra, _ = parameters.read_options(
            msg,
            scripted(
                [
                    {
                        "key": "grid_by_month",
                        "value": 1,
                        "quote": "winter electricity is dirtier than summer's",
                    }
                ]
            ),
            NOW,
        )
        r = parameters.Reading(
            steps=[parameters.Step("answer", ""), parameters.Step("what_if", "")]
        )
        parameters.merge_options(r, extra)
        self.assertEqual(r.changes, {"grid_by_month": 1.0})
        self.assertEqual(r.step_of["grid_by_month"], 1)

    def test_a_key_one_letter_off_is_read(self):
        """The model's slip in a key is put right, and said."""
        msg = "Suppose another sandstone at 3,200 m, 40 m thick with 400 mD."
        r = parameters.check(
            {
                "changes": [
                    {"key": "second_aquiper_permeability_md", "value": 400, "quote": "400 mD"}
                ]
            },
            msg,
            NOW,
        )
        self.assertEqual(r.changes, {"second_aquifer_permeability_md": 400.0})
        self.assertTrue(r.corrections)


class TestAlready(unittest.TestCase):
    """An option asked for that the design already has is said, with what it does."""

    def test_reading_records_it(self):
        """Free cooling on, asked for again: no change, and recorded as already so."""
        now = dict(NOW, free_cooling=1.0)
        msg = "Would cooling with outside air in winter, before the chillers, help?"
        r = parameters.check(
            {"changes": [{"key": "free_cooling", "value": 1, "quote": "cooling with outside air"}]},
            msg,
            now,
        )
        self.assertEqual((r.changes, r.already), ({}, ["free_cooling"]))
        self.assertFalse(parameters.wants_options(r, asks_change=True))

    def test_answer_leads_with_it(self):
        """The design's free cooling, its GWh, said first."""
        from gemini_agent import answer
        from unit_test.gemini_agent.test_naming import designed

        _, s = designed()
        entry = s.chosen
        if not entry.year.free_cooling_mw:
            self.skipTest("the chosen design has no free cooling")
        text = answer.already_text(entry, ["free_cooling"])
        self.assertIn("already has this", text)
        self.assertIn("Free cooling", text)
        self.assertIn("GWh", text)


class TestShortPrompts(unittest.TestCase):
    """Dioscuri's fine-tuned models read with the short prompts and key=value parameters."""

    def test_short_for_the_twins_only(self):
        """dioscuri-castor and dioscuri-pollux get the short form; the base models do not."""
        for name, short in (("dioscuri-castor", True), ("dioscuri-pollux:latest", True)):
            self.assertEqual(parameters.short_for(ScriptedLLM(lambda *a: {}, model=name)), short)
        self.assertFalse(parameters.short_for(ScriptedLLM(lambda *a: {}, model="qwen3.5:9b")))

    def test_short_messages(self):
        """The short form lists key=value and is far shorter than the full prompt."""
        now = dict(NOW, heat_return_c=60.0)
        full = parameters.reading_messages("What if the return were 50 °C?", now)
        short = parameters.reading_messages("What if the return were 50 °C?", now, short=True)
        self.assertIn("heat_return_c=60 [", short[1]["content"])
        size = sum(len(m["content"]) for m in short)
        self.assertLess(size, 0.3 * sum(len(m["content"]) for m in full))


if __name__ == "__main__":
    unittest.main()
