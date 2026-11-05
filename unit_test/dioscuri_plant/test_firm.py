"""Firm capacity: the year with one unit out, and the spare on the peak day."""

import unittest
from pathlib import Path

from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet
from dioscuri_plant.firm import bank_need, failure, outages, peak_margin, reliable, remedies

DATA = Path(__file__).resolve().parents[2] / "src" / "gemini_agent" / "data" / "challenge"
DEMAND = Demand.from_csv(
    DATA / "GEMINI_Heating_Demand_Daily_2027.csv", DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
)
PLANT = Plant(2, heat_pump_mw=3.9, boiler_mw=11.7, absorption_mw=1.0, chiller_mw=9.0)


class TestFirm(unittest.TestCase):
    """Every unit is taken out once; a bigger boiler covers a lost doublet."""

    @classmethod
    def setUpClass(cls):
        """Run the outages once for the challenge-sized plant."""
        cls.rules = Rules()
        cls.cases = {o["unit"]: o for o in outages(PLANT, DEMAND, stub_doublet, cls.rules)}

    def test_each_unit_once(self):
        """Two doublets, the brine side, the heat pump, the boiler and both chillers."""
        self.assertEqual(
            sorted(self.cases),
            sorted(
                [
                    "doublet 1",
                    "doublet 2",
                    "the shared treatment train",
                    "the heat exchanger",
                    "the heat pump",
                    "the boiler",
                    "the electric chillers",
                    "the absorption chiller",
                ]
            ),
        )

    def test_a_lost_doublet_leaves_winter_short(self):
        """One doublet out: heat short on winter days, worst on the coldest day."""
        heat = self.cases["doublet 1"]["heat"]
        self.assertGreater(heat["days_short"], 0)
        self.assertGreater(heat["worst_mw"], 1.0)
        self.assertTrue(heat["worst_day"].endswith(("Jan", "Feb", "Dec")))

    def test_a_bigger_boiler_covers_it(self):
        """With the boiler sized for the lost doublet, heat is met every day."""
        worst = self.cases["doublet 1"]["heat"]["worst_mw"]
        big = Plant(
            2, heat_pump_mw=3.9, boiler_mw=11.7 + worst + 0.1, absorption_mw=1.0, chiller_mw=9.0
        )
        cases = {o["unit"]: o for o in outages(big, DEMAND, stub_doublet, self.rules)}
        self.assertEqual(cases["doublet 1"]["heat"]["days_short"], 0)

    def test_peak_spare(self):
        """The spare on the peak heat day is what a bigger boiler adds."""
        a = peak_margin(PLANT, DEMAND, stub_doublet, self.rules)["heat"]
        b = peak_margin(
            Plant(2, heat_pump_mw=3.9, boiler_mw=16.7, absorption_mw=1.0, chiller_mw=9.0),
            DEMAND,
            stub_doublet,
            self.rules,
        )["heat"]
        self.assertEqual(a["day"], "28 Jan")
        self.assertAlmostEqual(b["spare_mw"] - a["spare_mw"], 5.0, places=1)


class TestFailures(unittest.TestCase):
    """Units out on given days; the reliable plan; what helps."""

    @classmethod
    def setUpClass(cls):
        """Use the challenge's rules."""
        cls.rules = Rules()

    def test_dated_outage_short_only_then(self):
        """Doublet 1 out 10-24 January: heat short on some of those days, none outside."""
        y = failure(PLANT, DEMAND, stub_doublet, [("doublet 1", 9, 23)], self.rules)
        short = y.daily_mw["heat"]["short"]
        self.assertTrue(any(short[d] > 0.1 for d in range(9, 24)))
        self.assertTrue(all(short[d] < 1e-6 for d in range(365) if not 9 <= d <= 23))

    def test_heat_exchanger_out_keeps_the_heat_pump(self):
        """With the exchanger out the heat pump still runs on the brine."""
        y = failure(PLANT, DEMAND, stub_doublet, [("heat exchanger", 0, 30)], self.rules)
        self.assertEqual(max(y.daily_mw["heat"]["geo"][:31]), 0.0)
        self.assertGreater(max(y.daily_mw["heat"]["hp"][:31]), 1.0)

    def test_one_of_two_injectors(self):
        """One of two injectors out halves the doublet's flow on those days."""
        from dioscuri_plant import Doublet

        two = Plant(
            1,
            heat_pump_mw=3.9,
            boiler_mw=30.0,
            chiller_mw=10.0,
            doublet_specs=(Doublet(injectors=2),),
        )
        y = failure(two, DEMAND, stub_doublet, [("injector 1", 0, 30)], self.rules)
        self.assertLessEqual(max(y.doublets[0]["flow_m3h"][:31]), 150.0 + 1e-6)

    def test_reliable_plan_holds(self):
        """The reliable plan meets every day with any one unit out, and costs more boiler."""
        plan, rounds, last = reliable(PLANT, DEMAND, stub_doublet, self.rules)
        self.assertTrue(plan.reliable)
        self.assertEqual(plan.boiler_units, 3)
        self.assertGreater(plan.boiler_mw, PLANT.boiler_mw)
        self.assertTrue(all(o["heat"]["days_short"] == 0 for o in last))
        self.assertTrue(all(o["cool"]["days_short"] == 0 for o in last))
        self.assertFalse(simulate_year(plan, DEMAND, stub_doublet, self.rules).violations)

    def test_a_unit_that_cannot_close_the_gap_is_not_grown(self):
        """No boiler allowed: the heat pump cannot cover a doublet out (no brine), so it stays.

        The plan does not hold and says which case is not covered, instead of a heat pump
        grown to hundreds of MW (review E4).
        """
        hp_only = Plant(1, heat_pump_mw=8.0, chiller_mw=15.0)
        plan, rounds, last = reliable(
            hp_only, DEMAND, stub_doublet, self.rules, excluded=("boiler", "electric_boiler")
        )
        self.assertEqual(plan.heat_pump_mw, 8.0)
        self.assertTrue(any("not covered" in str(r.get("stopped", "")) for r in rounds))
        lost = next(o for o in last if o["unit"] == "doublet 1")
        self.assertGreater(lost["heat"]["days_short"], 0)

    def test_remedies(self):
        """A bigger boiler covers a January ESP failure; a spare ESP shortens it."""
        events = [("doublet 1", 9, 23)]
        y = failure(PLANT, DEMAND, stub_doublet, events, self.rules)
        out = {r["key"]: r for r in remedies(PLANT, DEMAND, stub_doublet, events, y, self.rules)}
        self.assertEqual(out["boiler"]["year"].peak_shortfall_mw["heat"], 0.0)
        self.assertLess(
            sum(out["spare_esp"]["year"].daily_mw["heat"]["short"]),
            sum(y.daily_mw["heat"]["short"]),
        )


class TestBankRemedies(unittest.TestCase):
    """A bank with one of its units out grows by u / (u - 1) of the gap (4 Nov)."""

    @classmethod
    def setUpClass(cls):
        """Use the challenge's rules."""
        cls.rules = Rules()

    def test_bank_need(self):
        """10 MW short with one of 3 units out: 15 MW, since only 2/3 of it is there."""
        self.assertEqual(bank_need(10.0, 3, True), 15.0)
        self.assertEqual(bank_need(10.0, 3, False), 10.0)
        self.assertEqual(bank_need(10.0, 1, True), 10.0)

    def test_doublet_and_a_boiler_unit_out(self):
        """The best design's case: doublet 1 and one of 3 boiler units out, 21 Jan to 4 Feb.

        By hand: the heat pump has no brine, so 2/3 of 30 MW (20 MW) meets a 30 MW peak (28
        Jan): 10 MW short. 10 MW more (40 MW, 26.7 MW left) was still 3.3 MW short; the bank
        must be 1.5 x 30 = 45 MW: 15 MW more.
        """
        plant = Plant(1, heat_pump_mw=3.9, boiler_mw=30.0, boiler_units=3, chiller_mw=12.0)
        events = [("doublet 1", 20, 34), ("boiler unit", 20, 34)]
        y = failure(plant, DEMAND, stub_doublet, events, self.rules)
        peak = max(DEMAND.heat_mw[20:35])
        self.assertAlmostEqual(peak, 30.0, delta=0.05)
        self.assertAlmostEqual(y.peak_shortfall_mw["heat"], peak - 20.0, delta=0.01)
        out = {r["key"]: r for r in remedies(plant, DEMAND, stub_doublet, events, y, self.rules)}
        boiler = out["boiler"]
        self.assertAlmostEqual(boiler["added_mw"], 1.5 * (peak - 20.0), delta=0.1)
        self.assertEqual(boiler["plant"].boiler_units, 3)
        self.assertEqual(boiler["year"].peak_shortfall_mw["heat"], 0.0)

    def test_failed_electric_boiler_gets_a_twin(self):
        """A single electric boiler that fails cannot be grown to cover itself: a standby twin.

        No gas bought, so the electric boiler is the backup; growing the one that is out (as
        until 4 Nov) helped nothing.
        """
        plant = Plant(1, heat_pump_mw=3.9, electric_boiler_mw=20.0, chiller_mw=12.0, gas="sell")
        events = [("electric boiler", 20, 34)]
        y = failure(plant, DEMAND, stub_doublet, events, self.rules)
        self.assertGreater(y.peak_shortfall_mw["heat"], 1.0)
        out = {r["key"]: r for r in remedies(plant, DEMAND, stub_doublet, events, y, self.rules)}
        self.assertNotIn("electric_boiler", out)
        twin = out["standby_electric_boiler"]
        self.assertEqual(twin["plant"].electric_boiler_units, 2)
        self.assertEqual(twin["plant"].electric_boiler_mw, 40.0)
        self.assertEqual(twin["events"], [("electric boiler unit", 20, 34)])
        self.assertEqual(twin["year"].peak_shortfall_mw["heat"], 0.0)


class TestSubsurface(unittest.TestCase):
    """Breakthrough, the bubble point at the ESP and SodM's injection limit."""

    def test_challenge_doublet_passes(self):
        """At 200 mD and 300 m3/h every check passes; the bubble point is about 42 bar."""
        from dioscuri_plant.subsurface import breakthrough_years, bubble_point_bar

        self.assertAlmostEqual(bubble_point_bar(86.0), 43.4, delta=1.0)
        self.assertGreater(breakthrough_years(300.0, 1), 30)
        y = simulate_year(PLANT, DEMAND, stub_doublet, Rules())
        self.assertFalse([v for v in y.violations if "Doublet" in v])
        row = y.doublet_summary[0]
        self.assertLess(row["esp_setting_m"], 1000)
        self.assertLess(row["injection_top_bar"], row["injection_limit_bar"])

    def test_tight_reservoir_fails_then_search_caps_the_flow(self):
        """At 40 mD the ESP and injection limits break at full flow; the cap fixes them."""
        from dioscuri_plant.search import Topology, improve

        tight = Rules(permeability_md=40.0)
        y = simulate_year(PLANT, DEMAND, lambda q, d, o=None: stub_doublet(q, d, o, tight), tight)
        self.assertTrue(any("ESP" in v or "injection" in v for v in y.violations))
        rounds, year = improve(
            Topology(2), DEMAND, lambda q, d, o=None: stub_doublet(q, d, o, tight), tight
        )
        self.assertFalse(year.violations)
        self.assertLess(rounds[-1].plant.specs()[0].cap_m3h(tight), 300.0)


if __name__ == "__main__":
    unittest.main()
