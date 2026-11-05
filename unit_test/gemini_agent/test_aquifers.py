"""Several aquifers (4 Nov): the brief's list, the inputs card's row, the chat's changes.

A tester asked why each doublet's depth can be set but not its gas-liquid ratio. Each aquifer
now has its own depth, thickness, permeability, pressure and gas-liquid ratio; the search puts
each doublet in one, and the results, the checks and the answers say which.
"""

import json
import unittest

from gemini_agent import Agent, aquifers, card_edits, engine, lookup, parameters, verifier
from gemini_agent.agent import Session
from gemini_agent.contract import AquiferSpec, DesignBrief
from gemini_agent.llm import ScriptedLLM
from gemini_agent.reporter import RUN_OPTION
from unit_test.gemini_agent.test_agent import FULL_BRIEF, custom, fake_intake, run

PROJECT = Session().project
KNOWN = {
    "depth_m": 2500.0,
    "thickness_m": 100.0,
    "permeability_md": 200.0,
    "pressure_bar": 250.0,
    "gas_liquid_ratio": 0.8,
}
SECOND = {
    "depth_m": 3100.0,
    "thickness_m": 80.0,
    "permeability_md": 400.0,
    "pressure_bar": 313.23,
    "gas_liquid_ratio": 2.5,
}


def two_aquifers(**brief) -> DesignBrief:
    """Return the challenge with a second aquifer of its own rock and much more gas."""
    return DesignBrief(aquifers=[AquiferSpec(**KNOWN), AquiferSpec(**SECOND)], **brief)


def edit(changes, brief=None):
    """Return what the card's answers do to a brief (the challenge's by default)."""
    answers = {"confirm": RUN_OPTION, "changes": json.dumps(changes)}
    return card_edits.read(answers, brief or DesignBrief(), PROJECT)


def reading(message, edits, brief=None, key="aquifers"):
    """Return the planner's checked reading of a message, the model scripted to these edits."""
    brief = brief or DesignBrief()
    rules = engine.rules_for(brief)
    now = parameters.values_now(brief, None, rules, engine.prices_for(None, brief))
    raw = {"changes": [{"key": key, "value": edits, "quote": message}]}
    llm = ScriptedLLM(lambda purpose, msgs: raw)
    return parameters.read(message, llm, now), now


class TestTheList(unittest.TestCase):
    """The aquifers each project has without a list, and the older settings mapped onto it."""

    def test_the_projects_aquifers(self):
        """The challenge: the known aquifer and the same rock assumed 500 and 1,000 m deeper."""
        rows = aquifers.resolved(DesignBrief())
        self.assertEqual([r["kind"] for r in rows], ["known", "assumed", "assumed"])
        self.assertEqual([r["depth_m"] for r in rows], [2500.0, 3000.0, 3500.0])
        self.assertEqual({k: rows[0][k] for k in aquifers.KEYS}, KNOWN)
        for pid, depth, glr in (("trias-westland", 2336.0, 0.8), ("hal-leyweg", 2025.0, 1.0)):
            rows = aquifers.resolved(DesignBrief(project_id=pid))
            self.assertEqual(
                [(r["kind"], r["depth_m"], r["gas_liquid_ratio"]) for r in rows],
                [("known", depth, glr)],
            )

    def test_older_settings_map_onto_it(self):
        """Depths asked, and the second aquifer of a saved session (2 Nov), become the list."""
        rows = aquifers.resolved(DesignBrief(doublet_depths_m=[3000.0]))
        self.assertEqual([(r["kind"], r["depth_m"]) for r in rows], [("assumed", 3000.0)])
        old = {
            "second_aquifer_depth_m": 3200.0,
            "second_aquifer_thickness_m": 40.0,
            "second_aquifer_permeability_md": 400.0,
        }
        rows = aquifers.resolved(DesignBrief(rules=old))
        self.assertEqual(
            [(r["kind"], r["depth_m"]) for r in rows], [("known", 2500), ("given", 3200)]
        )
        self.assertEqual((rows[1]["thickness_m"], rows[1]["permeability_md"]), (40.0, 400.0))
        # The planner's older keys add the aquifer to the list (the assumed ones give way).
        brief = parameters.apply(DesignBrief(), {"second_aquifer_depth_m": 3200.0})
        self.assertEqual([a.depth_m for a in brief.aquifers], [2500.0, 3200.0])
        # Beside the list (the options call read it again), the same aquifer, not one more.
        listed = [KNOWN, dict(SECOND, gas_liquid_ratio=1.2)]
        both = {"aquifers": listed, "second_aquifer_depth_m": 3100.0}
        brief = parameters.apply(DesignBrief(doublet_depths_m=[3100.0]), both)
        self.assertEqual([a.gas_liquid_ratio for a in brief.aquifers], [0.8, 1.2])
        self.assertEqual(brief.doublet_depths_m, [2500.0, 3100.0])

    def test_a_saved_session_loads(self):
        """A session saved before the list (no ``aquifers``) loads; one saved with it keeps it."""
        s = Session()
        data = s.to_dict()
        data["brief"].pop("aquifers", None)
        self.assertEqual(Session.from_dict(data).brief.aquifers, [])
        s.brief = two_aquifers()
        back = Session.from_dict(json.loads(json.dumps(s.to_dict())))
        self.assertEqual([a.gas_liquid_ratio for a in back.brief.aquifers], [0.8, 2.5])
        s.remember(DesignBrief(aquifers=[AquiferSpec(**SECOND)]))  # the project's: it stays
        self.assertEqual([a.depth_m for a in s.brief.aquifers], [3100.0])

    def test_the_rules_each_doublet_sees(self):
        """The list's known aquifer sets the reservoir; the other one is its own."""
        rules = engine.rules_for(two_aquifers())
        self.assertEqual(rules.reservoir_depth_m, 2500.0)
        self.assertEqual(rules.aquifer_at(3100.0).gas_liquid_ratio, 2.5)
        self.assertEqual(rules.aquifer_at(2500.0).gas_liquid_ratio, 0.8)
        self.assertEqual(aquifers.search_depths(two_aquifers()), (2500.0, 3100.0))
        # A what-if of the known aquifer's permeability still applies on top of the list.
        what_if = two_aquifers(rules={"permeability_md": 300.0})
        self.assertEqual(engine.rules_for(what_if).permeability_md, 300.0)
        self.assertEqual(engine.rules_for(what_if).aquifer_at(3100.0).permeability_md, 400.0)


class TestTheDefaultDesign(unittest.TestCase):
    """One aquifer (or the project's list given back as it is) gives the same designs."""

    def test_the_default_design_does_not_change(self):
        """The challenge's pick and its cost, as before the list (b9be350), and as a list."""
        default = engine.search(DesignBrief())
        self.assertEqual(default.chosen.alternative.code, "1D-HP-EC@3000-N1-FC")
        # 56.66 until 4 Nov; 58.70 after that day's audit (the same pick): free cooling on De
        # Bilt's real hours, the towers' pumps and water counted, the doublet's productivity
        # index (11.7 m3/h/bar, not 14.5).
        self.assertAlmostEqual(default.chosen.economics.lcoe_eur_per_mwh, 58.70, places=2)
        same = DesignBrief(aquifers=[AquiferSpec(**r) for r in aquifers.value_of(DesignBrief())])
        listed = engine.search(same)
        self.assertEqual(listed.chosen.alternative.code, default.chosen.alternative.code)
        self.assertEqual(
            listed.chosen.economics.lcoe_eur_per_mwh, default.chosen.economics.lcoe_eur_per_mwh
        )
        self.assertEqual(listed.picks, default.picks)

    def test_the_real_projects_do_not_change(self):
        """Trias Westland and HAL Leyweg, one aquifer each, as before."""
        for pid, code, lcoe in (
            # Since the 4 Nov audit (the doublet's index, the towers), with the tests' plain
            # doublet and no sweep; the app (GEMINI, the sweep) picks 3D-HP-NC-N1-PV5.5 at 62.93.
            ("trias-westland", "2D-HP-NC-2I-N1-PV6.5", 63.02),
            ("hal-leyweg", "1D-HP-NC-N1-PV0.6", 82.68),
        ):
            chosen = engine.search(DesignBrief(project_id=pid)).chosen
            self.assertEqual(chosen.alternative.code, code)
            self.assertAlmostEqual(chosen.economics.lcoe_eur_per_mwh, lcoe, places=2)


class TestTwoAquifers(unittest.TestCase):
    """A search with a second aquifer whose brine holds three times the gas."""

    @classmethod
    def setUpClass(cls):
        """Search two doublets over both aquifers."""
        cls.outcome = engine.search(two_aquifers(n_doublets=2))
        cls.mixed = [
            e
            for e in cls.outcome.candidates
            if len({d["depth_m"] for d in e.alternative.doublets}) == 2
        ]

    def test_the_search_puts_doublets_in_each(self):
        """Layouts with both doublets in one aquifer and with one in each are tried."""
        layouts = {
            tuple(d["depth_m"] for d in e.alternative.doublets) for e in self.outcome.candidates
        }
        self.assertIn((2500.0, 3100.0), layouts)
        self.assertIn((2500.0, 2500.0), layouts)
        self.assertTrue(any("3,100 m (as given)" in n for n in self.outcome.notes))

    def test_each_doublets_gas_and_the_check(self):
        """Doublet 2's brine brings 2.5 Nm3/m3; the verifier sums the doublets' gas."""
        e = self.mixed[0]
        rows = e.year.plant["doublets"]
        self.assertEqual(
            [(r["aquifer"], r["gas_liquid_ratio"]) for r in rows], [(1, 0.8), (2, 2.5)]
        )
        check = next(c for c in e.verification.checks if "each doublet's aquifer" in c.name)
        self.assertTrue(check.passed, check.detail)
        self.assertIn("doublet 2 2.5 Nm3/m3 (aquifer 2)", check.detail)
        self.assertTrue(verifier.physics_ok(e.verification))

    def test_answers_say_which_aquifer(self):
        """The design's well depth names each doublet's aquifer and its rock and gas."""
        e = self.mixed[0]
        text = lookup.design_facts(e)["well_depth"].value
        self.assertIn("aquifer 2 at 3,100 m", text)
        self.assertIn("gas-liquid ratio 2.5", text)
        self.assertIn("doublet 2 at 3,100 m", text)
        words = aquifers.doublets_words(e.alternative.doublets, e.brief)
        self.assertIn("doublet 1 into aquifer 1 at 2,500 m (the known aquifer)", words)


class TestTheCard(unittest.TestCase):
    """The Aquifers row: one records field, its checks, and a change sent back."""

    @classmethod
    def setUpClass(cls):
        """Show the card of a new chat."""
        cls.card = custom(
            run(Agent(ScriptedLLM(fake_intake)), Session(), FULL_BRIEF, confirm=False),
            "confirm_inputs",
        )
        cls.rows = {r["label"]: r for r in cls.card["rows"]}

    def test_the_row_and_its_field(self):
        """The contract with the card: records, five columns with a help each, 1 to 3 items."""
        self.assertNotIn("Wells drilled into", self.rows)
        self.assertNotIn("Second aquifer", self.rows)
        (field,) = self.rows["Aquifers"]["fields"]
        self.assertEqual(
            {k: field[k] for k in ("key", "kind", "min_items", "max_items")},
            {"key": "aquifers", "kind": "records", "min_items": 1, "max_items": 3},
        )
        self.assertEqual([c["key"] for c in field["columns"]], list(aquifers.KEYS))
        for c in field["columns"]:
            self.assertLessEqual({"key", "label", "unit", "low", "high", "help"}, set(c))
            self.assertGreater(len(c["help"]), 40)
        # The card adds the catalogue's typical values (the old Aquifer boxes' warnings).
        typical = {c["key"]: c.get("typical") for c in field["columns"]}
        self.assertEqual(typical["permeability_md"], [50.0, 1000.0])
        self.assertIsNone(typical["pressure_bar"])  # warned of as far from the brine column's
        self.assertEqual(field["value"][0], KNOWN)
        self.assertEqual(field["kinds"], ["known", "assumed", "assumed"])
        # The gas-liquid ratio is each aquifer's now: the Brine row no longer holds it (its other
        # values stay editable there) and says where to change it.
        brine = self.rows["Brine"]
        self.assertNotIn("gas_liquid_ratio", [f["key"] for f in brine.get("fields", [])])
        self.assertIn("Aquifers row", brine.get("help", "") + brine.get("locked", ""))

    def test_a_change_goes_round(self):
        """The list sent back as it is changes nothing; a ratio changed is that aquifer's."""
        value = aquifers.value_of(DesignBrief())
        self.assertEqual(edit({"aquifers": value}).changed, [])
        value[1]["gas_liquid_ratio"] = 1.5
        out = edit({"aquifers": value})
        self.assertEqual((out.changed, out.errors), (["aquifers"], {}))
        self.assertEqual([a.gas_liquid_ratio for a in out.brief.aquifers], [0.8, 1.5, 0.8])
        self.assertEqual(out.brief.doublet_depths_m, [2500.0, 3000.0, 3500.0])
        rules = engine.rules_for(out.brief)
        self.assertEqual(rules.aquifer_at(3000.0).gas_liquid_ratio, 1.5)
        field = aquifers.card_field(out.brief)
        self.assertEqual(field["value"][1]["gas_liquid_ratio"], 1.5)
        self.assertEqual(field["kinds"], ["known", "given", "given"])

    def test_each_value_is_checked_and_named(self):
        """Out of range, overlapping, too many, no aquifer: refused, naming aquifer and column."""
        value = aquifers.value_of(DesignBrief())
        value[1]["gas_liquid_ratio"] = 12
        out = edit({"aquifers": value})
        self.assertEqual(
            out.errors, {"aquifers": "Aquifer 2, gas-liquid ratio: between 0 and 10 Nm³/m³."}
        )
        self.assertEqual(out.brief.aquifers, [])
        value = aquifers.value_of(DesignBrief())
        value[2]["depth_m"] = 3040.0  # 40 m below aquifer 2, both 100 m thick
        self.assertIn("Aquifers 2 and 3 overlap", edit({"aquifers": value}).errors["aquifers"])
        four = aquifers.value_of(DesignBrief()) + [dict(KNOWN, depth_m=4200.0)]
        self.assertIn("At most 3 aquifers", edit({"aquifers": four}).errors["aquifers"])
        self.assertIn("at least one", edit({"aquifers": []}).errors["aquifers"])
        value = [dict(KNOWN, pressure_bar=700.0)]  # more than the rock above it weighs
        self.assertIn("Aquifer 1, pressure", edit({"aquifers": value}).errors["aquifers"])

    def test_an_added_row_with_empty_boxes(self):
        """Left empty: the known aquifer's rock and gas, the brine column's pressure there."""
        field = aquifers.card_field(DesignBrief())
        new = dict(field["new_item"], depth_m=3300.0)
        self.assertIsNone(field["new_item"]["pressure_bar"])
        out = edit({"aquifers": [KNOWN, dict(new, thickness_m=None)]})
        self.assertEqual(out.errors, {})
        added = out.brief.aquifers[1]
        self.assertEqual((added.thickness_m, added.gas_liquid_ratio), (100.0, 0.8))
        self.assertAlmostEqual(added.pressure_bar, 1030 * 9.81 * 3300 / 1e5, 1)
        no_depth = edit({"aquifers": [KNOWN, field["new_item"]]})
        self.assertEqual(no_depth.errors, {"aquifers": "Aquifer 2, depth: give a number."})

    def test_a_pressure_far_from_hydrostatic_is_a_warning(self):
        """Possible, but rare: accepted, with a word on the field."""
        value = [KNOWN, dict(SECOND, pressure_bar=420.0)]
        out = edit({"aquifers": value})
        self.assertEqual(out.errors, {})
        self.assertIn("Aquifer 2: 420 bar is 34% above", out.warnings["aquifers"])
        self.assertTrue(aquifers.card_field(out.brief)["warnings"])

    def test_the_known_aquifer_is_changed_on_the_tables_first_line(self):
        """One place per value (4 Nov): the first line's permeability is the known aquifer's.

        The Aquifer row has no boxes of its own any more; it says where to change it.
        """
        value = aquifers.value_of(DesignBrief())
        value[0]["permeability_md"] = 300.0
        value[1]["gas_liquid_ratio"] = 1.5
        out = edit({"aquifers": value})
        self.assertEqual(out.errors, {})
        self.assertEqual([a.permeability_md for a in out.brief.aquifers], [300.0, 200.0, 200.0])
        self.assertEqual(engine.rules_for(out.brief).permeability_md, 300.0)
        self.assertNotIn("fields", self.rows["Aquifer"])
        self.assertIn("first line is this aquifer", self.rows["Aquifer"]["locked"])
        # The chat's reading still lands there.
        said = parameters.apply(DesignBrief(), {"permeability_md": 300.0})
        self.assertEqual(aquifers.value_of(said)[0]["permeability_md"], 300.0)


class TestTheChat(unittest.TestCase):
    """The planner's reading of the aquifers (the model scripted; code checks every value)."""

    def test_the_prompt_in_use_says_how(self):
        """The reading prompt in use explains aquifer edits (4 Nov: a newer prompt had lost it)."""
        from gemini_agent.answer import load

        for name in (parameters.PROMPT, parameters.SHORT_PROMPT):
            self.assertIn('{"aquifer": its number now', load(name), name)

    def test_an_aquifer_added(self):
        """It takes the known one's rock, the brine column's pressure; the assumed ones go."""
        msg = "Add an aquifer at 3,100 m with a gas-liquid ratio of 1.2"
        r, _ = reading(msg, [{"aquifer": None, "depth_m": 3100, "gas_liquid_ratio": 1.2}])
        self.assertEqual(r.dropped, [])
        rows = r.changes["aquifers"]
        self.assertEqual([x["depth_m"] for x in rows], [2500.0, 3100.0])
        self.assertEqual(rows[1]["gas_liquid_ratio"], 1.2)
        self.assertEqual(rows[1]["thickness_m"], 100.0)
        self.assertAlmostEqual(rows[1]["pressure_bar"], 1030 * 9.81 * 3100 / 1e5, 1)
        self.assertEqual([s.do for s in r.steps], ["design"])
        brief = parameters.apply(DesignBrief(), r.changes)
        self.assertEqual(engine.rules_for(brief).aquifer_at(3100.0).gas_liquid_ratio, 1.2)
        self.assertIn("3,100 m (gas-liquid ratio 1.2)", parameters.label(r.changes))

    def test_one_aquifer_changed_and_one_kept_alone(self):
        """The second aquifer's thickness; then the deeper one alone."""
        brief = two_aquifers()
        r, _ = reading(
            "The second aquifer is 80 m thick", [{"aquifer": 2, "thickness_m": 80}], brief
        )
        self.assertEqual(r.changes, {})  # it already is
        r, _ = reading(
            "The second aquifer is 60 m thick", [{"aquifer": 2, "thickness_m": 60}], brief
        )
        self.assertEqual([x["thickness_m"] for x in r.changes["aquifers"]], [100.0, 60.0])
        r, _ = reading("Use only the deeper aquifer", [{"aquifer": 2, "only": True}], brief)
        self.assertEqual([x["depth_m"] for x in r.changes["aquifers"]], [3100.0])
        r, _ = reading("Drop the shallow one", [{"aquifer": 1, "remove": True}], brief)
        self.assertEqual([x["depth_m"] for x in r.changes["aquifers"]], [3100.0])

    def test_aquifers_named_as_the_model_names_them(self):
        """By depth, and "keep only" as a removal of the rest with the kept one restated."""
        brief = two_aquifers()
        thin = [dict(SECOND, aquifer=None, thickness_m=60)]  # a "new" one at aquifer 2's depth
        r, _ = reading("Make the deeper layer 60 m thick", thin, brief)
        self.assertEqual([x["thickness_m"] for x in r.changes["aquifers"]], [100.0, 60.0])
        keep = [{"aquifer": None, "remove": True}, dict(SECOND, aquifer=2)]
        r, _ = reading("Keep just the 3,100 m one", keep, brief)
        self.assertEqual([x["depth_m"] for x in r.changes["aquifers"]], [3100.0])
        # Removed by a wrong number but restated by its depth: kept.
        muddled = [{"aquifer": 2, "remove": True}, dict(SECOND, aquifer=3)]
        r, _ = reading(
            "Only the 3,100 m aquifer", [{"aquifer": None, "remove": True}] + muddled, brief
        )
        self.assertEqual([x["depth_m"] for x in r.changes["aquifers"]], [3100.0])
        # A removal of nothing in particular, alone, changes nothing.
        r, _ = reading("Remove it", [{"aquifer": None, "remove": True}], brief)
        self.assertEqual(r.changes, {})

    def test_edits_in_several_items_are_one_list(self):
        """An aquifer added in one item and the assumed ones dropped in two more: one design."""
        msg = (
            "There is a second aquifer at 3,100 m whose brine holds 1.2 Nm3 of gas per m3. "
            "Design the plant using both aquifers."
        )
        both = "Design the plant using both aquifers."
        changes = [
            {
                "key": "aquifers",
                "value": [{"depth_m": 3100, "gas_liquid_ratio": 1.2}],
                "quote": msg,
            },
            {"key": "aquifers", "value": [{"aquifer": 2, "remove": True}], "quote": both},
            {"key": "aquifers", "value": [{"aquifer": 3, "remove": True}], "quote": both},
        ]
        now = parameters.values_now(
            DesignBrief(), None, engine.rules_for(DesignBrief()), engine.prices_for(None)
        )
        r = parameters.check({"changes": changes, "steps": [{"do": "design"}]}, msg, now)
        self.assertEqual([x["depth_m"] for x in r.changes["aquifers"]], [2500.0, 3100.0])
        self.assertEqual([s.do for s in r.steps], ["design"])

    def test_a_step_written_as_a_change_is_not_left_unread(self):
        """The 9B wrote {"key": "design"} beside the aquifer: no reason to read options again."""
        msg = "Add an aquifer at 3,100 m and design the plant"
        changes = [
            {"key": "aquifers", "value": [{"depth_m": 3100}], "quote": "an aquifer at 3,100 m"},
            {"key": "design", "value": True, "quote": "design the plant"},
        ]
        _, now = reading("x", [])
        r = parameters.check({"changes": changes}, msg, now)
        self.assertEqual((list(r.changes), r.dropped), (["aquifers"], []))
        self.assertFalse(parameters.wants_options(r))

    def test_numbers_the_message_does_not_give_are_dropped(self):
        """A ratio the model made up, an aquifer that does not exist, a new one without depth."""
        r, _ = reading(
            "Add the deeper sandstone at 3,100 m", [{"depth_m": 3100, "gas_liquid_ratio": 2}]
        )
        self.assertEqual(r.changes, {})
        self.assertIn("gas-liquid ratio 2 is not in the message", r.dropped[0])
        self.assertTrue(r.unread)
        r, _ = reading(
            "Aquifer 3 is 50 m thick", [{"aquifer": 3, "thickness_m": 50}], two_aquifers()
        )
        self.assertIn("needs its depth", r.dropped[0])
        # Values the aquifer already has need no backing: the model may copy the list.
        msg = "Give aquifer 2 a gas-liquid ratio of 1.5"
        copied = dict(SECOND, aquifer=2, gas_liquid_ratio=1.5)
        r, _ = reading(msg, [copied], two_aquifers())
        self.assertEqual([x["gas_liquid_ratio"] for x in r.changes["aquifers"]], [0.8, 1.5])

    def test_the_catalogue_shows_the_list(self):
        """The model sees each aquifer, numbered, with what it is."""
        _, now = reading("x", [])
        text = parameters.catalogue_text(now, ["aquifers"])
        self.assertIn("1: 2500 m, 100 m thick, 200 mD, 250 bar, gas-liquid ratio 0.8 (known)", text)
        self.assertIn("3: 3500 m", text)
        self.assertIn("aquifers=1: 2500 m", parameters.catalogue_short(now))

    def test_a_what_if_moves_the_doublets_with_their_aquifer(self):
        """A doublet in an aquifer whose depth moved goes with it; one in a dropped one moves."""
        from gemini_agent.contract import Alternative

        alt = Alternative(
            code="2D",
            name="x",
            depth_m=2500.0,
            n_doublets=2,
            doublets=[{"depth_m": 2500.0}, {"depth_m": 3100.0}],
        )
        before = [KNOWN, SECOND]
        moved = aquifers.move_doublets(alt, before, [KNOWN, dict(SECOND, depth_m=3300.0)])
        self.assertEqual([d["depth_m"] for d in moved.doublets], [2500.0, 3300.0])
        alone = aquifers.move_doublets(alt, before, [SECOND])
        self.assertEqual([d["depth_m"] for d in alone.doublets], [3100.0, 3100.0])
        self.assertIs(aquifers.move_doublets(alt, before, before), alt)


if __name__ == "__main__":
    unittest.main()
