"""A design's issues for the Design tab's alerts: each tied to the parts of its drawing."""

import unittest

from gemini_agent import Agent, engine, issues, parameters, reliability, workbench
from gemini_agent.agent import Session
from gemini_agent.llm import ScriptedLLM
from unit_test.gemini_agent.test_agent import FULL_BRIEF, fake_intake, run


def daily(entry):
    """Return the entry with its year day by day (a design kept without it is run again)."""
    return entry if entry.year.daily_mw is not None else engine.reprice(entry, {})


def with_year(entry, **changes):
    """Return a copy of the entry whose year has these fields changed."""
    year = entry.year.model_copy(deep=True)
    for key, value in changes.items():
        setattr(year, key, value)
    return entry.model_copy(update={"year": year})


def short_days(entry, side="heat"):
    """Return the days a side is short in the entry's year (as ``issues.SHORT_MW`` counts)."""
    return [i for i, v in enumerate(entry.year.daily_mw[side]["short"]) if v > issues.SHORT_MW]


class TestDesignIssues(unittest.TestCase):
    """The challenge's pick, the same with half its boiler, and failures asked about on both."""

    @classmethod
    def setUpClass(cls):
        """Run the pick, then a design with half its boiler (short of heat in late January)."""
        cls.s = Session()
        run(Agent(ScriptedLLM(fake_intake)), cls.s, FULL_BRIEF)
        cls.base = daily(cls.s.chosen)
        cls.base_id = workbench.design_id(cls.base)
        boiler = cls.base.alternative.sizes_mw["boiler"]
        made = workbench.create_design(cls.s, cls.base_id, {"boiler_mw": round(boiler / 2, 1)})
        cls.weak = daily(workbench.find(cls.s, made["id"]))
        cls.weak_id = made["id"]
        cls.graph = workbench.graph_view(cls.weak)

    def failure(self, entry, unit, first, last):
        """Return a failure what-if on a design as the agent keeps it (``session.failures``)."""
        fail = parameters.Failure(unit=unit, first=first, last=last)
        return dict(reliability.run_failure(entry, [fail], {}), message="what if it fails?")

    def test_the_pick_meets_demand_and_has_no_issues(self):
        """A design that meets every day, with nothing asked about it, has no issues."""
        self.assertEqual(short_days(self.base), [])
        view = workbench.design_view(self.s, self.base)
        self.assertEqual(view["issues"], [])
        self.assertEqual(view["broken_days"], [])

    def test_too_small_a_boiler_is_the_cause_of_its_short_days(self):
        """Days short with nothing out fall on the top-up unit; the units flat out are named."""
        days = short_days(self.weak)
        self.assertTrue(days, "half the boiler should leave days short")
        found = issues.design_issues(self.weak, self.graph)
        self.assertEqual(len(found), 1)
        i = found[0]
        self.assertEqual(
            (i["kind"], i["severity"], i["cause"]), ("heat_short", "critical", "capacity")
        )
        self.assertEqual(i["units"], ["boiler", "demand_heat"])
        self.assertEqual(i["unit"], "Gas boiler")
        self.assertTrue(set(i["limit"]) & {"hex", "heat_pump"}, i["limit"])
        self.assertNotIn("boiler", i["limit"])
        self.assertEqual((i["first"], i["last"], i["days"]), (days[0], days[-1], len(days)))
        short = self.weak.year.daily_mw["heat"]["short"]
        self.assertEqual(i["day"], max(days, key=lambda d: short[d]))
        self.assertTrue(
            i["what"].startswith(f"Heat short on {len(days)} days in January"), i["what"]
        )
        self.assertIn(f"up to {issues._mw(max(short))} MW", i["what"])
        self.assertEqual(i["when"], issues.when_words(days))
        self.assertIn("Not enough capacity", i["why"])
        self.assertFalse(i["what_if"])

    def test_the_design_view_carries_the_issues_and_the_broken_days(self):
        """The Design tab's payload has the issues and the red bands of the year strip."""
        view = workbench.design_view(self.s, self.weak)
        self.assertEqual([i["kind"] for i in view["issues"]], ["heat_short"])
        self.assertEqual(view["issues"][0]["id"], "heat_short-1")
        drawn = {n["id"] for n in view["graph"]["nodes"]}
        self.assertTrue(set(view["issues"][0]["units"]) <= drawn)
        self.assertEqual([b["kind"] for b in view["broken_days"]], ["heat_short"])

    def test_a_failure_that_leaves_days_short_is_red_on_its_unit(self):
        """A failure asked about on the design: its unit and the demand, its days, a what-if."""
        failed = self.failure(self.weak, "doublet 1", 9, 23)
        found = issues.design_issues(self.weak, self.graph, [failed])
        i = next(x for x in found if x["kind"] == "failure")
        self.assertEqual(i["severity"], "critical")
        self.assertEqual(i["units"], ["producer_1", "demand_heat"])
        self.assertTrue(i["what_if"])
        self.assertEqual((i["first"], i["last"], i["when"]), (9, 23, "10–24 Jan"))
        self.assertIn("Doublet 1 (its producer or ESP) out: heat short on", i["what"])
        # Only the window's days count (the design is short on other days of its own).
        n = sum(1 for d in failed["failed"]["days"] if d["heat_short_mw"] > 1e-3)
        self.assertIn(f"heat short on {n} day", i["what"])
        self.assertTrue(9 <= i["day"] <= 23)
        self.assertEqual(i["asked"], "what if it fails?")
        # The design's own shortfall comes first: it is not a what-if.
        self.assertEqual(found[0]["kind"], "heat_short")

    def test_a_failure_the_plant_covers_is_amber(self):
        """A unit out that the rest of the plant covers: a warning on that unit alone."""
        failed = self.failure(self.base, "heat pump", 0, 30)
        i = issues.design_issues(self.base, workbench.graph_view(self.base), [failed])[0]
        self.assertEqual((i["kind"], i["severity"]), ("failure", "warning"))
        self.assertEqual(i["units"], ["heat_pump"])
        self.assertIn("the rest of the plant covers it", i["what"])
        self.assertEqual(i["when"], "1–31 Jan")

    def test_failures_on_other_designs_are_left_out(self):
        """A failure asked about on one design is not another's issue; the latest of a kind is."""
        on_base = self.failure(self.base, "doublet 1", 9, 23)
        found = issues.design_issues(self.weak, self.graph, [on_base])
        self.assertEqual([i["kind"] for i in found], ["heat_short"])
        twice = [self.failure(self.weak, "doublet 1", 9, 23)] * 2
        found = issues.design_issues(self.weak, self.graph, twice)
        self.assertEqual(sum(i["kind"] == "failure" for i in found), 1)

    def test_a_planned_stop_on_the_short_days_is_their_cause(self):
        """A doublet in its planned stop on a short day: the doublet, not the boiler."""
        days = short_days(self.weak)
        d = [dict(x) for x in self.weak.year.doublets]
        d[0]["on"] = [False if k in days else v for k, v in enumerate(d[0]["on"])]
        entry = with_year(self.weak, doublets=d, stop_ranges=[[[days[0], days[-1]]]])
        i = issues.design_issues(entry, self.graph)[0]
        self.assertEqual((i["kind"], i["cause"]), ("heat_short", "out"))
        self.assertEqual(i["units"], ["producer_1", "demand_heat"])
        self.assertEqual(i["unit"], "Producer 1")
        self.assertIn("Doublet 1 is in its planned stop", i["why"])

    def test_planned_service_on_the_short_days_is_their_cause(self):
        """A unit out for its planned service on a short day is the cause."""
        days = short_days(self.weak)
        entry = with_year(self.weak, service=[["heat pump", days[0], days[-1]]])
        i = issues.design_issues(entry, self.graph)[0]
        self.assertEqual(i["units"], ["heat_pump", "demand_heat"])
        self.assertIn("The heat pump is out for its planned service", i["why"])

    def test_brine_cooled_past_the_cap_is_amber_on_the_injector(self):
        """The brine cooled past the cap on some days: a warning on the doublet's injector."""
        d = [dict(x) for x in self.weak.year.doublets]
        limit = engine.rules_for(self.weak.brief).max_brine_cooling_k
        d[0]["wellhead_c"] = [100.0] * 365
        d[0]["reinjection_c"] = [
            100.0 - limit - (5.0 if 40 <= k <= 44 else 0.0) for k in range(365)
        ]
        entry = with_year(self.weak, doublets=d, daily_mw=self.base.year.daily_mw)
        found = issues.design_issues(entry, self.graph)
        self.assertEqual(len(found), 1)
        i = found[0]
        self.assertEqual((i["kind"], i["severity"]), ("cap", "warning"))
        self.assertEqual(i["units"], ["injector_1"])
        self.assertEqual(i["when"], "10–14 Feb")
        self.assertIn("cooled by up to 45 K on 5 days in February", i["what"])

    def test_a_cap_broken_over_the_year_is_on_its_doublet(self):
        """A doublet run more days than the cap: amber on its producer, over the year."""
        text = "Doublet 1 runs 340 days, more than 330."
        entry = with_year(self.base, violations=[text, "Something else is off."])
        found = issues.design_issues(entry, workbench.graph_view(self.base))
        self.assertEqual([i["units"] for i in found], [["producer_1"], []])
        self.assertEqual(found[0]["what"], "Runs 340 days, more than 330")
        self.assertEqual(
            (found[0]["when"], found[0]["first"], found[0]["day"]), ("over the year", None, None)
        )
        self.assertEqual(found[1]["unit"], "The plant")

    def test_outage_units_map_to_the_drawing(self):
        """Each plant outage unit names its part of the drawing; one not drawn names none."""
        parts = issues.Parts(self.graph)
        self.assertEqual(parts.node_of("doublet 1"), "producer_1")
        self.assertEqual(parts.node_of("injector 1"), "injector_1")
        self.assertEqual(parts.node_of("train 1", [1]), "train_1")
        self.assertEqual(parts.node_of("boiler unit"), "boiler")
        self.assertEqual(parts.node_of("Heat Exchanger"), "hex")
        self.assertIsNone(parts.node_of("doublet 3"))  # one doublet
        self.assertIsNone(parts.node_of("absorption"))  # none in this design
        self.assertIsNone(parts.node_of("the moon"))


class TestWords(unittest.TestCase):
    """When and in which months, in words."""

    def test_when(self):
        """Runs of days, one month or two; many runs in short."""
        self.assertEqual(issues.when_words([25, 26, 27, 28]), "26–29 Jan")
        self.assertEqual(issues.when_words([5]), "6 Jan")
        self.assertEqual(issues.when_words([30, 31, 32]), "31 Jan – 2 Feb")
        self.assertEqual(issues.when_words([1, 2, 10]), "2–3 Jan, 11 Jan")
        self.assertEqual(issues.when_words([1, 3, 5, 7, 9]), "5 periods, 2 Jan – 10 Jan")
        self.assertEqual(issues.when_words([]), "")

    def test_months(self):
        """One month, two, three, or how many."""
        self.assertEqual(issues.months_words([3, 20]), "in January")
        self.assertEqual(issues.months_words([25, 40]), "in January and February")
        self.assertEqual(issues.months_words([10, 40, 360]), "in January, February and December")
        self.assertEqual(issues.months_words([10, 40, 70, 100]), "over 4 months")


if __name__ == "__main__":
    unittest.main()
