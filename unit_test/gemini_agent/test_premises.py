"""Tests for the 1 Nov regression round: premises, stop dates, long facts and refusals.

The challengers' questions that went wrong: "the cost of heat is 69.8, correct?" was agreed
with, "could we move the stop to August?" could not be run, "what share of the yearly cost is
gas?" had no fact to answer from, and a reply refused a what-if that had run.
"""

import unittest
from types import SimpleNamespace

from gemini_agent import answer as answering
from gemini_agent import lookup, parameters, reporter
from gemini_agent.contract import DesignBrief
from gemini_agent.lookup import Fact

SOURCE = "1D-HP-EC-N1 (simulate_year and economics)"


def sheet():
    """Return a design's facts as the lookup gives them (the values of 1 Nov's A1)."""
    return {
        "lcoh": Fact("lcoh", "75.7 €/MWh", SOURCE),
        "lcoe": Fact("lcoe", "69.8 €/MWh", SOURCE),
        "lcoc": Fact("lcoc", "42.1 €/MWh", SOURCE),
        "co2_saving": Fact("co2_saving", "46.8%", SOURCE),
        "doublets": Fact("doublets", "1", SOURCE),
        "operating_days": Fact(
            "operating_days", "doublet 1: 330 days, stopped 9 Jul to 12 Aug", SOURCE
        ),
        "heat_split": Fact(
            "heat_split",
            "the geothermal heat exchanger 41.8 GWh (37.4%); the heat pump 22 GWh (19.7%); the "
            "gas boiler 48 GWh (42.9%) of 111.7 GWh of heat a year",
            SOURCE,
        ),
    }


class PremiseChecks(unittest.TestCase):
    """Code corrects a number a fact contradicts; the rest is paired for the model."""

    def test_cost_of_heat_and_cold_given_as_cost_of_heat(self):
        """69.8 €/MWh called the cost of heat is corrected with what it is."""
        lead, notes = lookup.premise_checks(
            ["the cost of heat is 69.8", "the boiler gives about a quarter"],
            sheet(),
            ["lcoh", "heat_split"],
        )
        self.assertEqual(
            lead,
            "**Not quite.** The cost of heat is 75.7 €/MWh; 69.8 €/MWh is the cost of heat and "
            "cold together.",
        )
        # The premise without a number goes to the model with the heat split, not the cost.
        self.assertIn("gas boiler 48 GWh (42.9%)", notes[1])
        self.assertNotIn("75.7", notes[1])

    def test_doublet_count_and_co2(self):
        """A wrong doublet count and CO2 saving are corrected; no value of another kind."""
        lead, _ = lookup.premise_checks(["the plant uses 3 doublets"], sheet(), ["capex"])
        self.assertEqual(lead, "**Not quite.** The number of doublets is 1.")
        lead, _ = lookup.premise_checks(["the 35% CO2 saving"], sheet(), ["co2_saving"])
        # 35 is also a number of days: a value of another kind is never offered instead.
        self.assertEqual(lead, "**Not quite.** The CO₂ saving against gas is 46.8%.")

    def test_a_units_share_of_the_heat_is_not_the_coverage(self):
        """4 Nov: "the gas boiler covers about 21% of the heat" got "covered is 100%"."""
        facts = dict(sheet(), heat_coverage=Fact("heat_coverage", "100% (111.7 of 111.7 GWh)", ""))
        said = "You told me the gas boiler covers about 21% of the heat, correct?"
        self.assertEqual(lookup.wanted(said), ["heat_split"])
        lead, notes = lookup.premise_checks(
            ["the gas boiler covers about 21% of the heat"], facts, ["heat_split"]
        )
        self.assertEqual(lead, "")  # the split is a long fact: the model judges it
        self.assertIn("gas boiler 48 GWh (42.9%)", notes[0])
        self.assertNotIn("100%", notes[0])

    def test_a_right_premise_is_not_corrected(self):
        """A premise the facts give is only paired, never corrected."""
        lead, notes = lookup.premise_checks(["the cost of heat is 75.7"], sheet(), ["lcoh"])
        self.assertEqual(lead, "")
        self.assertEqual(notes, ["“the cost of heat is 75.7” against cost of heat: 75.7 €/MWh"])

    def test_model_premise_lead_keeps_plain_sourced_sentences(self):
        """The model's correction keeps plain sentences whose numbers a source gives."""
        facts = reporter.Facts("")
        facts.put("42.9% 48 GWh 111.7 GWh")
        raw = {
            "premises": [
                {"said": "the cost is 70", "agrees": True, "right": "The cost is 69.8 €/MWh."},
                {
                    "said": "the boiler gives a third of the heat",
                    "agrees": False,
                    "right": "No. The text states the boiler gives 48 GWh. The boiler gives "
                    "42.9% of the heat. The user's claim is wrong. This is about 43% (48/111.7",
                },
            ]
        }
        self.assertEqual(
            answering.premise_lead(raw, facts), "**Not quite.** The boiler gives 42.9% of the heat."
        )
        raw["premises"][1]["right"] = "The boiler gives 12.5% of the heat."  # no source has it
        self.assertEqual(answering.premise_lead(raw, facts), "")

    def test_a_premise_without_a_figure_is_not_led(self):
        """Only a premise that states a figure gets code's "Not quite" (4 Nov, T04 and S39)."""
        facts = reporter.Facts("")
        facts.put("54.0 €/MWh")
        raw = {
            "premises": [
                {
                    "said": "you didn't pick the cheapest",
                    "agrees": False,
                    "right": "The cheapest design costs 54.0 €/MWh.",
                }
            ]
        }
        self.assertEqual(answering.premise_lead(raw, facts), "")
        raw["premises"][0]["said"] = "the cheapest costs 60"
        self.assertTrue(answering.premise_lead(raw, facts).startswith("**Not quite.**"))
        self.assertTrue(answering.states_quantity("it has three doublets"))
        self.assertFalse(answering.states_quantity("you drilled deeper than the aquifer"))


class StopDates(unittest.TestCase):
    """The doublets' stop moved from chat: code reads the days from the words."""

    NOW = {"operating_days": 330, "n_doublets": 2}

    def test_month_keeps_the_stop_length(self):
        """A month starts the stop on its first day and keeps its 35 days."""
        stops, why = parameters.stop_dates("move the stop to August", "", self.NOW)
        self.assertEqual((stops, why), ([[[212, 246]], [[212, 246]]], ""))
        self.assertEqual(parameters.stops_label(stops), "the doublets stopped 1 Aug to 4 Sep")

    def test_one_doublet_on_given_days(self):
        """A named doublet gets the dates alone."""
        stops, _ = parameters.stop_dates("doublet 2 off 1 to 21 July", "", self.NOW)
        self.assertEqual(stops, [[], [[181, 201]]])
        self.assertEqual(parameters.stops_label(stops), "doublet 2 stopped 1 Jul to 21 Jul")

    def test_start_and_length(self):
        """A start and a length give the stop's days."""
        stops, _ = parameters.stop_dates("from 10 July for three weeks", "", self.NOW)
        self.assertEqual(stops[0], [[190, 210]])

    def test_no_date_is_said(self):
        """Words without a date give no stop and say why."""
        stops, why = parameters.stop_dates("stop it in winter", "stop it in winter", self.NOW)
        self.assertEqual(stops, [])
        self.assertIn("no dates", why)

    def test_planner_change_is_checked_and_applied(self):
        """The planner's stop change is read by code, applied to the brief and named."""
        raw = {
            "changes": [{"key": "doublet_stops", "value": "August", "quote": "move it to August"}],
            "steps": [{"do": "what_if", "quote": "move it to August", "changes": []}],
        }
        r = parameters.check(raw, "Could we move it to August?", {"n_doublets": 1}, True)
        self.assertEqual(r.changes, {"doublet_stops": [[[212, 246]]]})
        brief = parameters.apply(DesignBrief(), r.changes)
        self.assertEqual(brief.doublet_stops, [[[212, 246]]])
        self.assertEqual(parameters.label(r.changes), "the doublet stopped 1 Aug to 4 Sep")


class CO2Floor(unittest.TestCase):
    """A floor on the CO2 cut ("at least 50 % less CO2") is not the lowest-CO2 design."""

    def test_objective_co2_with_a_percentage_becomes_a_floor(self):
        """The planner's "co2" with a percentage of CO2 in the words becomes the floor."""
        raw = {"objective": "co2", "steps": [{"do": "what_if", "quote": "x", "changes": []}]}
        message = "The council promised at least 50% less CO2 than gas. Could they live with it?"
        r = parameters.check(raw, message, {}, True)
        self.assertEqual(r.changes, {"min_co2_saving": 0.5})
        self.assertEqual(parameters.label(r.changes), "a CO2 cut of at least 50% against gas")

    def test_lowest_co2_stays_an_objective(self):
        """Without a percentage it is what the design should be best at."""
        raw = {"objective": "co2", "steps": [{"do": "design", "quote": "x", "changes": []}]}
        r = parameters.check(raw, "Which design has the lowest CO2?", {}, False)
        self.assertEqual(r.changes, {"objective": "co2"})


class LongFacts(unittest.TestCase):
    """Long facts read as headings, count as kept with any of their numbers, and the cost split."""

    def test_heading_and_any_number(self):
        """A long fact opens with its heading and is kept by any of its numbers."""
        facts = reporter.Facts("")
        text = reporter.question_text(["heat_split"], sheet(), facts, "1D-HP-EC-N1")
        self.assertTrue(text.startswith("Heat over the year by source: the geothermal"))
        self.assertNotIn("The the", text)
        value = "~" + sheet()["heat_split"].value
        self.assertTrue(answering.contains("The boiler gives 42.9% of the heat.", value))
        self.assertFalse(answering.contains("The boiler gives a lot.", value))

    def test_cost_split(self):
        """The yearly cost by part, with shares, and the gas sold as a credit."""
        e = SimpleNamespace(
            lines_heat=[
                ["Wells", "capital", 1.5],
                ["Gas", "gas", 2.0],
                ["Boiler O&M", "fixed", 0.3],
                ["Boiler O&M", "variable", 0.2],
                ["Gas sold", "gas", -0.5],
            ],
            lines_cold=[["Electricity: chillers", "electricity", 1.0]],
        )
        self.assertEqual(
            lookup._cost_split(e),
            "5 M€ a year in all: gas bought 2 M€ (40%); capital (each unit's annuity) 1.5 M€ "
            "(30%); electricity 1 M€ (20%); O&M (fixed and variable) 0.5 M€ (10%); less 0.5 M€ a "
            "year for the brine's gas sold (net 4.5 M€)",
        )

    def test_cost_share_and_heat_and_cold_patterns(self):
        """The patterns find the cost split, the joint cost, the heat split, breakthrough."""
        self.assertIn("cost_split", lookup.wanted("What share of the yearly cost is gas?"))
        self.assertEqual(lookup.wanted("What is the cost of heat and cold?"), ["lcoe"])
        self.assertIn("heat_split", lookup.wanted("the boiler gives about a quarter of the heat"))
        self.assertIn("well_checks", lookup.wanted("When does cold water reach the producer?"))


class Refusals(unittest.TestCase):
    """A reply that only refuses a what-if that ran shows the checked result instead."""

    def test_refusal_only_reply_falls_back(self):
        """A reply that only refuses shows the checked result."""
        facts = reporter.Facts("")
        draft = "With the yearly service switched on, the cost is 88.2 €/MWh."
        facts.put(draft)
        blocks = [answering.Block("draft", "draft", draft)]
        raw = {
            "answer": "The design does not model these features. I cannot calculate the cost "
            "without running a new simulation.",
            "kind": "answer",
            "scope": "project",
        }
        out = answering._finish(answering.Reply(draft), raw, blocks, facts, draft, [], "")
        self.assertTrue(out.fallback)
        self.assertEqual(out.text, draft)


if __name__ == "__main__":
    unittest.main()


class PromptKeys(unittest.TestCase):
    """The reasoning model's prompt offers every value a question can ask for (2 Nov)."""

    def test_every_fact_key_is_in_the_prompt(self):
        """The combined cost and the doublet count were missing from the static list."""
        from pathlib import Path

        text = (Path(lookup.__file__).parent / "prompts" / f"{parameters.PROMPT}.txt").read_text(
            encoding="utf-8"
        )
        line = next(x for x in text.splitlines() if x.startswith("asks_for: "))
        self.assertEqual([k for k in lookup.FACT_KEYS if f"{k} (" not in line], [])
