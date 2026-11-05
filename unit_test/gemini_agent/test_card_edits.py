"""The inputs card as a form, and the doublets' stop dates: fields, code checks, the run."""

import io
import json
import unittest
from datetime import date

try:
    from pypdf import PdfReader
except ImportError:  # the reader is only needed to look inside the PDF
    PdfReader = None

from gemini_agent import Agent, answer, card_edits, lookup, report_pdf, stops
from gemini_agent.agent import Session
from gemini_agent.contract import DesignBrief
from gemini_agent.llm import ScriptedLLM
from gemini_agent.reporter import RUN_OPTION
from unit_test.gemini_agent.test_agent import FULL_BRIEF, custom, fake_intake, run

PROJECT = Session().project  # the organisers' district
# The known aquifer, as the Aquifers table's first line shows it.
KNOWN = {
    "depth_m": 2500.0,
    "thickness_m": 100.0,
    "permeability_md": 200.0,
    "pressure_bar": 250.0,
    "gas_liquid_ratio": 0.8,
}
# Doublet 1 off 30 Jun - 19 Jul and 19 Aug - 2 Sep: 20 + 15 = 35 days.
DATES = [[[180, 199], [230, 244]]]


def edit(changes=None, dates=None, brief=None):
    """Return what the card's answers do to a brief (the challenge's by default)."""
    answers = {"confirm": RUN_OPTION}
    if changes is not None:
        answers["changes"] = json.dumps(changes)
    if dates is not None:
        answers["doublet_stops"] = json.dumps(dates)
    return card_edits.read(answers, brief or DesignBrief(), PROJECT)


class TestTheForm(unittest.TestCase):
    """What the card offers to change, and why the rest is read-only."""

    @classmethod
    def setUpClass(cls):
        """Show the card of a new chat."""
        cls.card = custom(
            run(Agent(ScriptedLLM(fake_intake)), Session(), FULL_BRIEF, confirm=False),
            "confirm_inputs",
        )
        cls.rows = {r["label"]: r for r in cls.card["rows"]}

    def fields(self, label):
        """Return a row's fields by key."""
        return {f["key"]: f for f in self.rows[label].get("fields") or []}

    def test_planner_parameters_are_fields_with_the_catalogues_range(self):
        """The supply (warned about: the challenge's) and the return, unit, range, value now."""
        heat = self.fields("Heating network")
        self.assertEqual(list(heat), ["heat_supply_c", "heat_return_c"])
        self.assertEqual(heat["heat_supply_c"]["cap"]["low"], 100)
        self.assertIn("requires heat at 100 °C", heat["heat_supply_c"]["cap"]["words"])
        self.assertEqual(
            {k: heat["heat_return_c"][k] for k in ("kind", "unit", "low", "high", "value")},
            {"kind": "number", "unit": "°C", "low": 20, "high": 95, "value": 60},
        )
        # One place per value (4 Nov): the known aquifer is changed in the Aquifers table's
        # first line; its own row says so, on the card.
        self.assertEqual(self.fields("Aquifer"), {})
        self.assertIn("first line is this aquifer", self.rows["Aquifer"]["locked"])
        table = self.fields("Aquifers")["aquifers"]
        self.assertEqual(table["kinds"][0], "known")
        typical = {c["key"]: c.get("typical") for c in table["columns"]}
        self.assertEqual(typical["permeability_md"], [50.0, 1000.0])
        self.assertIn("gradient_c_per_km", self.fields("Temperature"))
        self.assertEqual(self.fields("Operating days")["operating_days"]["high"], 365)
        rate = self.fields("Prices")["discount_rate"]  # a fraction, shown in per cent
        self.assertEqual((rate["unit"], rate["scale"], rate["high"]), ("%", 100.0, 30.0))
        design = self.fields("Design for")
        self.assertEqual(design["n_doublets"]["value"], "")
        self.assertIn("gas_free", design["objective"]["options"])
        self.assertEqual(design["exclude"]["words"]["heat_pump"], "heat pumps")

    def test_every_row_can_be_changed_or_says_why_not(self):
        """Fields, or the switches it holds; a row with neither says why, on the card."""
        self.assertIn("brine_cp_j_kg_k", self.fields("Heat capacity"))
        self.assertEqual(self.rows["Units' yearly service"]["toggles"], ["maintenance"])
        self.assertEqual(self.rows["Doublet stops"]["toggles"], ["maintenance"])
        self.assertEqual(
            self.rows["The brine's gas"]["toggles"], ["flare_brine_gas", "co2_reinjection"]
        )
        self.assertEqual(self.rows["Network heat losses"]["toggles"], ["network_length_km"])
        self.assertIn("free_cooling", self.rows["Free cooling, solar, heat store"]["toggles"])
        self.assertEqual(self.rows["Doublet stops"]["kind"], "assumed")
        for row in self.card["rows"]:
            self.assertTrue(
                row.get("fields") or row.get("toggles") or row.get("locked"), row["label"]
            )
            self.assertNotIn("locked", row) if row.get("fields") or row.get("toggles") else None

    def test_pages(self):
        """Every row and switch on a page, in the card's order; the review is the card's own."""
        pages = [p["id"] for p in self.card["pages"]]
        self.assertEqual(
            pages, ["demand", "reservoir", "brine", "networks", "prices", "request", "limits"]
        )
        self.assertEqual([p["title"] for p in self.card["pages"]][1], "Reservoir and wells")
        self.assertEqual(self.rows["Aquifer"]["page"], "reservoir")
        self.assertEqual(self.rows["The brine's gas"]["page"], "brine")
        self.assertEqual(self.rows["Doublets and flow"]["page"], "limits")
        self.assertEqual(self.rows["Doublet stops"]["page"], "limits")
        self.assertEqual(self.rows["Design for"]["page"], "request")
        for row in self.card["rows"]:
            self.assertIn(row["page"], pages)
        for t in self.card["toggles"]:
            self.assertIn(t["page"], pages)

    def test_every_field_is_explained(self):
        """What it is and what it changes; typical values for numbers; the challenge's caps."""
        for row in self.card["rows"]:
            for f in row.get("fields") or []:
                self.assertTrue(f.get("help"), f["key"])
                if f["kind"] == "number" and f["key"] != "n_doublets":
                    self.assertTrue(f.get("typical") and f.get("typical_words"), f["key"])
                    self.assertTrue(f.get("required"), f["key"])
        cooling = self.fields("Doublets and flow")["max_brine_cooling_k"]
        self.assertIn("can't be more than this below the production temperature", cooling["help"])
        self.assertEqual(cooling["cap"]["high"], 40)
        self.assertEqual(self.fields("Doublets and flow")["flow_max_m3h"]["cap"]["high"], 300)
        self.assertEqual(self.fields("Operating days")["operating_days"]["cap"]["high"], 330)
        pump = self.fields("Doublets and flow")["pump_efficiency"]  # per cent, like its range
        self.assertEqual((pump["cap"]["low"], pump["typical"]), (70, [50, 80]))
        visc = self.fields("Brine")["brine_viscosity_pa_s"]
        self.assertEqual((visc["unit"], visc["value"], visc["scale"]), ("mPa·s", 0.4, 1000.0))
        for t in self.card["toggles"]:
            if t["id"] != "maintenance":
                self.assertTrue(t.get("help"), t["id"])

    def test_the_default_card_warns_of_nothing(self):
        """The challenge's own values are inside their caps and typical ranges."""
        self.assertEqual(self.card["warnings"], {})
        ctx = self.card["context"]
        self.assertEqual((ctx["surface_c"], ctx["depth_m"], ctx["heat_peak_mw"]), (12, 2500, 30))

    def test_the_stop_dates_control(self):
        """Maintenance: the doublets' stops, then every unit type's service.

        Dioscuri's weeks by default; three doublets, 35 days off each, a start for "My dates";
        each unit type's service off by default.
        """
        t = next(t for t in self.card["toggles"] if t["id"] == "maintenance")
        self.assertEqual((t["kind"], t["value"], t["stops"]), ("maintenance", 0.0, []))
        self.assertEqual((t["days_off"], t["default_days_off"]), ([35, 35, 35], 35))
        self.assertEqual([u["mode"] for u in t["units"]], ["off"] * 6)
        self.assertEqual(
            t["units"][1],
            {
                "unit": "heat pump",
                "label": "Heat pump",
                "days": 14,
                "bank": False,
                "mode": "off",
                "ranges": [],
            },
        )
        self.assertEqual((t["doublets"], t["operating_days"], t["year"]), (3, 330, 2027))
        blocks = [d[0] for d in t["suggested"]]
        self.assertEqual([b - a + 1 for a, b in blocks], [35, 35, 35])
        self.assertIsNone(stops.check(t["suggested"], 330))
        self.assertEqual(self.card["errors"], {})


class TestTheChecks(unittest.TestCase):
    """The card's changes go through the planner's checks and code's own."""

    def test_changes_in_range_are_applied(self):
        """A return, a rate in per cent (sent as a fraction), a unit left out, what best means."""
        out = edit({"heat_return_c": 50, "discount_rate": 0.06, "exclude": ["heat_pump"]})
        self.assertEqual(out.errors, {})
        self.assertEqual(out.brief.heating.return_c, 50.0)
        self.assertEqual(out.brief.prices["discount_rate"], 0.06)
        self.assertEqual(out.brief.excluded, ["heat_pump"])
        self.assertEqual(out.changed, ["discount_rate", "exclude", "heat_return_c"])
        self.assertEqual(edit({"objective": "cost"}).brief.objective, "cost")
        allowed = edit({"exclude": []}, brief=out.brief)
        self.assertEqual((allowed.brief.excluded, allowed.changed), ([], ["exclude"]))

    def test_out_of_range_is_refused_on_its_field(self):
        """90 °C/km: refused with the range, in the form's units; nothing else is lost."""
        out = edit({"gradient_c_per_km": 90, "heat_return_c": 50})
        self.assertEqual(out.errors, {"gradient_c_per_km": "Between 10 and 80 °C/km."})
        self.assertEqual(out.asked, {"gradient_c_per_km": 90})
        self.assertNotIn("gradient_c_per_km", out.brief.rules)
        self.assertEqual(out.brief.heating.return_c, 50.0)
        # The known aquifer's rock, in the table's first line: 20,000 mD refused with its range.
        first = dict(KNOWN, permeability_md=20000)
        table = edit({"aquifers": [first]}).errors["aquifers"]
        self.assertIn("Aquifer 1, permeability: between 1 and 10000 mD.", table)
        # Its old boxes are gone from the card: sent anyway, they are refused.
        self.assertIn(
            "type the change instead", edit({"permeability_md": 300}).errors["permeability_md"]
        )
        self.assertEqual(
            edit({"discount_rate": 0.5}).errors["discount_rate"], "Between 0 and 30 %."
        )
        self.assertEqual(
            edit({"operating_days": 300.5}).errors["operating_days"], "Give a whole number."
        )

    def test_values_that_do_not_fit_together_are_refused(self):
        """A cooling return below its 20 °C supply; a lowest flow above the cap."""
        self.assertEqual(list(edit({"cool_return_c": 15}).errors), ["cool_return_c"])
        self.assertIn(
            "must be above the supply (20 °C)", edit({"cool_return_c": 15}).errors["cool_return_c"]
        )
        self.assertIn("flow_min_m3h", edit({"flow_min_m3h": 250, "flow_max_m3h": 200}).errors)
        # Equal is one fixed rate: allowed.
        self.assertEqual(edit({"flow_min_m3h": 300}).errors, {})

    def test_physically_impossible_values_are_refused(self):
        """A pump of 100 %, more gas than all of it, a pressure above the rock's weight."""
        self.assertIn("less than 100 %", edit({"pump_efficiency": 1.0}).errors["pump_efficiency"])
        self.assertIn("110 %", edit({"gas_ch4_fraction": 0.9}).errors["gas_ch4_fraction"])
        # The rock's weight, on the known aquifer's line of the table.
        rock = edit({"aquifers": [dict(KNOWN, pressure_bar=700)]}).errors["aquifers"]
        self.assertIn("more than the rock above it weighs (about 575 bar)", rock)
        self.assertIn("give a value", edit({"gradient_c_per_km": None}).errors["gradient_c_per_km"])
        self.assertIn("give a value", edit({"gradient_c_per_km": ""}).errors["gradient_c_per_km"])
        # A heating supply below the return: on the supply, the field that changed.
        low = edit({"heat_supply_c": 55}).errors
        self.assertEqual(list(low), ["heat_supply_c"])
        both = card_edits.impossible({"heat_supply_c": 55, "heat_return_c": 60})
        self.assertEqual(sorted(both), ["heat_return_c", "heat_supply_c"])

    def test_outside_the_challenge_runs_with_a_warning(self):
        """A 90 °C supply and a 400 m³/h cap are taken; the card warns the challenge is missed."""
        out = edit({"heat_supply_c": 90, "flow_max_m3h": 400, "brine_cp_j_kg_k": 4100})
        self.assertEqual(out.errors, {})
        self.assertEqual(out.brief.heating.supply_c, 90.0)
        self.assertEqual(out.brief.rules["brine_cp_j_kg_k"], 4100)
        from gemini_agent import engine, reporter

        self.assertEqual(engine.rules_for(out.brief).brine_cp_j_kg_k, 4100)
        rows = card_edits.with_fields(reporter.inputs_rows(PROJECT, out.brief), out.brief, PROJECT)
        warned = card_edits.warnings(rows)
        self.assertIn("will not meet the challenge", warned["heat_supply_c"])
        self.assertIn("at most 300 m³/h", warned["flow_max_m3h"])
        self.assertNotIn("brine_cp_j_kg_k", warned)  # 4,100 is typical
        cp = next(r for r in rows if r["label"] == "Heat capacity")
        self.assertEqual((cp["kind"], cp["source"]), ("asked", "you"))
        design_for = next(r for r in rows if r["label"] == "Design for")
        self.assertNotIn("brine cp", design_for["value"])
        # Outside the typical values, on the table's line (the assumed aquifers share the rock).
        rare = edit({"aquifers": [dict(KNOWN, permeability_md=3000)]}).brief
        hot = card_edits.with_fields(reporter.inputs_rows(PROJECT, rare), rare, PROJECT)
        self.assertEqual(
            card_edits.warnings(hot)["aquifers"],
            "Aquifer 1, permeability: outside the typical 50 to 1,000 mD: check it is right.",
        )

    def test_what_the_card_does_not_offer_is_refused(self):
        """An input without a field, and words that are not JSON."""
        self.assertIn("homes", edit({"homes": 500}).errors)
        bad = card_edits.read({"confirm": RUN_OPTION, "changes": "{"}, DesignBrief(), PROJECT)
        self.assertIn("changes", bad.errors)

    def test_the_doublet_count_can_go_back_to_the_search(self):
        """'1 to 3' clears a count the user gave; a count is set as a whole number."""
        self.assertIsNone(
            edit({"n_doublets": ""}, brief=DesignBrief(n_doublets=2)).brief.n_doublets
        )
        self.assertEqual(edit({"n_doublets": "3"}).brief.n_doublets, 3)

    def test_stop_dates_are_checked_against_the_cap(self):
        """In 2027, no overlap, at least 365 - operating days; with the days the card sets."""
        good = edit(dates=DATES)
        self.assertEqual((good.brief.doublet_stops, good.changed), (DATES, ["doublet_stops"]))
        # Fewer days off than the cap leaves: allowed, the cap relaxed to what they need (the
        # designs are still checked against the challenge's 330 days).
        short = edit(dates=[[[180, 199]]])
        self.assertNotIn("doublet_stops", short.errors)
        self.assertEqual(short.brief.doublet_stops, [[[180, 199]]])
        self.assertEqual(short.brief.rules["operating_days"], 345)
        self.assertIn("operating_days", short.changed)
        self.assertIn("overlap", edit(dates=[[[180, 199], [190, 214]]]).errors["doublet_stops"])
        self.assertIn("2027", edit(dates=[[[350, 384]]]).errors["doublet_stops"])
        # 300 operating days set on the same card: 65 days off needed.
        self.assertIn("the 65", edit({"operating_days": 300}, DATES).errors["doublet_stops"])
        self.assertIn("could not be read", edit(dates=[[[1.5, 40]]]).errors["doublet_stops"])

    def test_only_a_real_change_is_a_change(self):
        """The card always sends the dates; Dioscuri's weeks again is no change."""
        self.assertFalse(card_edits.asks_change({"doublet_stops": "[]"}, DesignBrief()))
        self.assertFalse(card_edits.asks_change({"changes": "{}"}, DesignBrief()))
        self.assertTrue(card_edits.asks_change({"doublet_stops": json.dumps(DATES)}, DesignBrief()))
        mine = DesignBrief(doublet_stops=DATES)
        self.assertTrue(card_edits.asks_change({"doublet_stops": "[]"}, mine))


class TestTheRun(unittest.TestCase):
    """Confirm and run: the changed card, the design on the dates, later designs keep them."""

    @classmethod
    def setUpClass(cls):
        """Refuse a change, then run the card's changes on the user's dates."""
        cls.agent = Agent(ScriptedLLM(fake_intake))
        cls.s = Session()
        run(cls.agent, cls.s, FULL_BRIEF, confirm=False)
        refused = {"confirm": RUN_OPTION, "changes": json.dumps({"gradient_c_per_km": 90})}
        cls.refused = run(cls.agent, cls.s, answers=refused, confirm=False)
        cls.chosen_after_refusal = cls.s.chosen
        answers = {
            "confirm": RUN_OPTION,
            "changes": json.dumps({"heat_return_c": 50}),
            "doublet_stops": json.dumps(DATES),
        }
        cls.events = run(cls.agent, cls.s, answers=answers, confirm=False)
        cls.entry = cls.s.chosen
        cls.said = cls.s.history[-1]["user"]  # the chat's record of the answer

    def test_a_refused_change_shows_the_card_again_and_runs_nothing(self):
        """The reason on the field, the value the user gave, the question open."""
        card = custom(self.refused, "confirm_inputs")
        self.assertEqual(card["errors"], {"gradient_c_per_km": "Between 10 and 80 °C/km."})
        self.assertEqual(card["asked"], {"gradient_c_per_km": 90})
        self.assertIsNone(self.chosen_after_refusal)

    def test_the_rows_that_ran_are_marked(self):
        """The applied card: the heating network and the stops changed, no question after it."""
        card = custom(self.events, "confirm_inputs")
        self.assertTrue(card["applied"])
        changed = [r["label"] for r in card["rows"] if r["changed"]]
        self.assertEqual(changed, ["Heating network", "Doublet stops"])
        stops_row = next(r for r in card["rows"] if r["label"] == "Doublet stops")
        self.assertIn(
            "doublet 1: 30 Jun to 19 Jul and 19 Aug to 2 Sep (35 days)", stops_row["value"]
        )
        self.assertEqual(
            self.said,
            f"{RUN_OPTION} (heating return temperature 50 °C; doublet stops on your dates)",
        )

    def test_the_design_runs_on_the_dates(self):
        """The year: doublet 1 off on both ranges; the check says the dates were the user's."""
        y = self.entry.year
        self.assertEqual(self.entry.brief.doublet_stops, DATES)
        self.assertEqual(y.stop_ranges[0], DATES[0])
        on = y.doublets[0]["on"]
        self.assertFalse(any(on[i] for i in list(range(180, 200)) + list(range(230, 245))))
        check = next(c for c in self.entry.verification.checks if "days per doublet" in c.name)
        self.assertTrue(check.passed)
        self.assertIn("on your dates", check.detail)

    def test_what_is_said_about_the_stops(self):
        """The operations block, the facts sheet: both ranges, and whose dates they are."""
        block = answer.operations_block(self.entry)
        text = block.text if hasattr(block, "text") else str(block)
        self.assertIn("doublet 1 30 Jun to 19 Jul and 19 Aug to 2 Sep", text)
        self.assertIn("35 days each, on your dates", text)
        fact = lookup.design_facts(self.entry)["operating_days"].value
        self.assertIn("stopped 30 Jun to 19 Jul and 19 Aug to 2 Sep", fact)
        self.assertEqual(stops.ranges_of(self.entry.year)[0], [(180, 199), (230, 244)])

    @unittest.skipIf(PdfReader is None, "pypdf is not installed")
    def test_the_report_lists_each_range(self):
        """The planned stops table: a row per range, why there: the user's dates."""
        pdf = report_pdf.build(self.s, today=date(2026, 10, 31))
        text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("Planned stops of the doublets", text)
        self.assertIn("30 Jun", text)
        self.assertIn("19 Aug", text)
        self.assertIn("your dates", text)

    def test_a_later_design_keeps_the_dates(self):
        """The dates are the project's, like the switches: the next design of the chat uses them."""
        self.assertEqual(self.s.brief.doublet_stops, DATES)
        run(self.agent, self.s, "Design the heating and cooling without heat pumps.", confirm=False)
        self.assertEqual(self.s.ledger[-1].brief.doublet_stops, DATES)
        self.assertEqual(self.s.ledger[-1].year.stop_ranges[0], DATES[0])


class TestTheWords(unittest.TestCase):
    """The stops in words, and the card's JSON read strictly."""

    def test_spans_and_summaries(self):
        """One block, several ranges; Dioscuri's or the user's."""
        self.assertEqual(stops.span_words([(189, 223)]), "9 Jul to 12 Aug")
        self.assertEqual(
            stops.span_words([(0, 6), (100, 101), (364, 364)]),
            "1 Jan to 7 Jan, 11 Apr to 12 Apr and 31 Dec to 31 Dec",
        )
        mine = DesignBrief(doublet_stops=DATES)
        value, source, kind = stops.row(mine, 330)
        self.assertEqual((source, kind), ("you", "asked"))
        self.assertIn("any other doublet in the quietest weeks", value)
        self.assertEqual(stops.row(DesignBrief(), 330)[2], "assumed")

    def test_parse(self):
        """At most three doublets, whole days in pairs; empty doublets at the end dropped."""
        self.assertEqual(stops.parse("[]"), [])
        self.assertEqual(stops.parse([[[5, 39]], []]), [[[5, 39]]])
        for bad in ("[[[1, 2, 3]]]", "[[[1.5, 3]]]", "[[], [], [], [[1, 35]]]", "{}"):
            with self.assertRaises(ValueError):
                stops.parse(bad)


if __name__ == "__main__":
    unittest.main()


class TestMaintenance(unittest.TestCase):
    """The Maintenance section: each doublet's days off and each unit type's yearly service."""

    def read(self, **answers):
        """Return what the section's answers do to the challenge's brief."""
        sent = {"confirm": RUN_OPTION}
        sent.update({k: json.dumps(v) for k, v in answers.items()})
        return card_edits.read(sent, DesignBrief(), PROJECT)

    def test_days_off_per_doublet(self):
        """50 days for doublet 1: kept as the doublet's own; the cap unchanged."""
        out = self.read(doublet_days_off=[50, 35, 35])
        self.assertEqual(out.brief.rules["stop_days_off"], [50, 35, 35])
        self.assertEqual(out.changed, ["doublet_days_off"])
        self.assertTrue(card_edits.asks_change({"doublet_days_off": "[50, 35, 35]"}, DesignBrief()))

    def test_fewer_days_off_relaxes_the_cap(self):
        """20 days off: allowed, the doublet may run 345 days (still checked against 330)."""
        out = self.read(doublet_days_off=[20, 35, 35])
        self.assertEqual(out.brief.rules["operating_days"], 345)
        self.assertIn("operating_days", out.changed)

    def test_service_plan(self):
        """The heat pump on the user's dates, the boilers in their quiet weeks."""
        plan = [
            {"unit": "heat pump", "mode": "dates", "ranges": [[120, 133]]},
            {"unit": "boiler", "mode": "auto", "ranges": []},
        ]
        out = self.read(service_plan=plan)
        self.assertEqual(
            out.brief.rules["service_plan"],
            [["heat pump", "dates", [[120, 133]]], ["boiler", "auto", []]],
        )
        self.assertEqual(out.errors, {})

    def test_bad_plans_are_said(self):
        """Dates without a range, a unit the card does not list: said, nothing applied."""
        no_range = self.read(service_plan=[{"unit": "heat pump", "mode": "dates", "ranges": []}])
        self.assertIn("at least one range", no_range.errors["service_plan"])
        self.assertNotIn("service_plan", no_range.brief.rules or {})
        self.assertIn(
            "unknown unit",
            self.read(service_plan=[{"unit": "kettle", "mode": "auto", "ranges": []}]).errors[
                "service_plan"
            ],
        )

    def test_a_raised_cap_goes_back_when_not_needed(self):
        """20 days off raised the cap to 345; 35 days again puts the challenge's 330 back."""
        raised = self.read(doublet_days_off=[20, 35, 35]).brief
        self.assertEqual(raised.rules["operating_days"], 345)
        sent = {"confirm": RUN_OPTION, "doublet_days_off": json.dumps([])}
        back = card_edits.read(sent, raised, PROJECT)
        self.assertEqual(back.brief.rules["operating_days"], 330)
        self.assertNotIn("stops_relaxed", back.brief.rules)

    def test_a_cap_the_user_set_stands(self):
        """300 operating days set on the same card with 35 days off: said, not raised."""
        sent = {"confirm": RUN_OPTION, "changes": json.dumps({"operating_days": 300})}
        sent["doublet_days_off"] = json.dumps([35, 35, 35])
        out = card_edits.read(sent, DesignBrief(), PROJECT)
        self.assertIn("fewer than the 65", out.errors["doublet_days_off"])


class TestWhenThePlantCannotBalance(unittest.TestCase):
    """Ali, 3 Nov: "the system cannot converge ... hard to understand what was wrong"."""

    def test_the_likely_input_and_where_to_change_it(self):
        """Tight rock: the root finder's error, said as the rock, with the card's page."""
        from gemini_agent import parameters, reporter

        tight = parameters.apply(DesignBrief(), {"permeability_md": 5, "reservoir_thickness_m": 20})
        text = reporter.search_failed_text("f(a) and f(b) must have different signs", tight)
        self.assertTrue(text.startswith("The plant could not be balanced"))
        self.assertIn("5 mD × thickness 20 m = 0.1 D·m", text)
        self.assertIn("Reservoir and wells", text)
        self.assertIn("The model said: f(a) and f(b) must have different signs", text)
        # The card warns before the run, on the aquifers' table (the form's rule too); the
        # message's rock lands in the known aquifer, which the assumed ones share.
        rows = card_edits.with_fields(reporter.inputs_rows(PROJECT, tight), tight, PROJECT)
        warned = card_edits.warnings(rows)["aquifers"]
        self.assertTrue(warned.startswith("Aquifers 1, 2 and 3: the rock lets very little brine"))
        self.assertIn("k × h = 0.1 D·m", warned)
        # Nothing odd in the inputs: a limit of the model, said as such.
        plain = reporter.search_failed_text("did not converge", DesignBrief())
        self.assertIn("likely a limit of the model", plain)
        other = reporter.search_failed_text("KeyError: 'x'", DesignBrief())
        self.assertIn("a fault of the model, not your inputs", other)

    def test_the_agent_says_it_instead_of_search_failed(self):
        """The search raising, as it does for 0.5 D·m: the reply says why and what to change."""
        from unittest import mock

        from gemini_agent import engine

        agent = Agent(ScriptedLLM(fake_intake))
        s = Session()
        run(agent, s, FULL_BRIEF, confirm=False)
        answers = {  # the known aquifer's rock, on the table's first line
            "confirm": RUN_OPTION,
            "changes": json.dumps({"aquifers": [dict(KNOWN, permeability_md=5, thickness_m=20)]}),
        }
        boom = ValueError("f(a) and f(b) must have different signs")
        with mock.patch.object(engine, "search", side_effect=boom):
            events = run(agent, s, answers=answers, confirm=False)
        said = "".join(e.get("delta", "") for e in events if e["type"] == "TEXT_MESSAGE_CONTENT")
        self.assertIn("The plant could not be balanced", said)
        self.assertIn("0.1 D·m", said)
        self.assertNotIn("The design search failed, so I won't design", said)


class TestTheSwitches(unittest.TestCase):
    """The card's switches are checked by code too: the server has the last word."""

    def test_amounts_in_range_are_applied_others_refused(self):
        """5 km and 2 MWp are taken; 60 km, 'lots' and -1 are refused with the range."""
        ok, refused = card_edits.read_toggles(
            {"network_length_km": "5", "solar_mwp": "2", "free_cooling": "1"}, DesignBrief()
        )
        self.assertEqual(refused, {})
        self.assertEqual(
            (ok.rules["network_length_km"], ok.rules["solar_mwp"], ok.rules["free_cooling"]),
            (5.0, 2.0, 1.0),
        )
        _, refused = card_edits.read_toggles(
            {"network_length_km": "60", "storage_mwh": "lots", "solar_mwp": "-1"}, DesignBrief()
        )
        self.assertEqual(refused["network_length_km"], "Between 0.1 and 50 km, or 0 for none.")
        self.assertEqual(refused["storage_mwh"], "Give a number.")
        self.assertIn("0 or more", refused["solar_mwp"])

    def test_a_refused_amount_shows_the_card_again(self):
        """Run with a 60 km network: nothing runs, the reason on the switch."""
        agent = Agent(ScriptedLLM(fake_intake))
        s = Session()
        run(agent, s, FULL_BRIEF, confirm=False)
        events = run(
            agent, s, answers={"confirm": RUN_OPTION, "network_length_km": "60"}, confirm=False
        )
        card = custom(events, "confirm_inputs")
        self.assertEqual(
            card["errors"], {"network_length_km": "Between 0.1 and 50 km, or 0 for none."}
        )
        self.assertIsNone(s.chosen)


class TestWhatYouSet(unittest.TestCase):
    """The values a message set are the user's; the card says what each one affects."""

    def test_yours_and_the_links_both_ways(self):
        """A 50 °C return and a 250 m3/h cap differ from the project's: they are the user's."""
        from gemini_agent import parameters

        brief = parameters.apply(DesignBrief(), {"heat_return_c": 50, "flow_max_m3h": 250})
        self.assertEqual(card_edits.yours(brief), ["flow_max_m3h", "heat_return_c"])
        self.assertEqual(card_edits.yours(DesignBrief()), [])
        # Linked both ways: the cooling cap names the return; the return names the supply.
        self.assertIn("max_brine_cooling_k", parameters.linked_both_ways("heat_return_c"))
        self.assertIn("heat_return_c", parameters.linked_both_ways("max_brine_cooling_k"))
        spec = card_edits.field_of("heat_return_c", "Return", 50)
        self.assertIn("the heat pump's size and efficiency", spec["affects"])
        for key, p in parameters.CATALOGUE.items():
            for other in p.linked:
                self.assertIn(other, parameters.CATALOGUE, f"{key} links to {other}")


class TestTheAquifersField(unittest.TestCase):
    """Stream M's records field carries the catalogue's links like every other field."""

    def test_links_and_what_it_changes(self):
        """The gradient and the rock are linked to the aquifers, both ways."""
        from gemini_agent import reporter

        rows = card_edits.with_fields(
            reporter.inputs_rows(PROJECT, DesignBrief()), DesignBrief(), PROJECT
        )
        fields = {f["key"]: f for r in rows for f in r.get("fields") or []}
        self.assertIn("gradient_c_per_km", fields["aquifers"]["linked"])
        self.assertIn("the brine's temperature", fields["aquifers"]["affects"])
        self.assertIn("aquifers", fields["gradient_c_per_km"]["linked"])


class TestRefusedInTheMessage(unittest.TestCase):
    """A value the first message gives and code refuses is on the card, not dropped unsaid."""

    def test_heating_supply_under_its_return(self):
        """4 Nov (a teammate's test): "heated temperature should be 50" vanished from the card."""
        from gemini_agent import Agent, Session
        from gemini_agent.llm import ScriptedLLM
        from unit_test.gemini_agent.test_agent import custom, fake_intake, run

        msg = (
            "design a geothermal system: heated temperature should be 50 and cooled "
            "temperature should be 10C."
        )

        def script(purpose, messages):
            if purpose == "parameters":
                return {
                    "changes": [
                        {
                            "key": "heat_supply_c",
                            "value": 50,
                            "quote": "heated temperature should be 50",
                        },
                        {
                            "key": "cool_supply_c",
                            "value": 10,
                            "quote": "cooled temperature should be 10C",
                        },
                    ],
                    "doublets": [],
                    "unsupported": [],
                    "failures": [],
                    "designs": [],
                    "asks_for": [],
                    "premises": [],
                    "origin_of": [],
                    "on_topic": True,
                    "objective": None,
                    "steps": [{"do": "design"}],
                }
            return fake_intake(purpose, messages)

        agent = Agent(ScriptedLLM(script))
        s = Session()
        events = run(agent, s, msg, confirm=False)
        card = custom(events, "confirm_inputs")
        self.assertIn("heat_supply_c", card["errors"])
        self.assertEqual(card["asked"]["heat_supply_c"], 50.0)
        self.assertIn("I did not take the heating supply temperature of 50 °C", s.last["answer"])
        self.assertEqual((s.pending or {}).get("kind"), "confirm")
