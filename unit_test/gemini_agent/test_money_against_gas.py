"""Money against gas: replacements in the NPV, one gas reference, the best-overall rule in words.

The audit of 4 Nov found the NPV against gas left out the units bought again (an electric
boiler of 20 years bought again in year 20), a design with free cooling measured against a gas
plant that had it too, the reply's rule for "best overall" without its flaring step, the
known-aquifer comparison naming a design with a doublet at 3,500 m, and the capital-cost
sensitivity missing four capital items. Each is pinned here, by hand where it can be.
"""

import unittest
from dataclasses import fields
from types import SimpleNamespace

from dioscuri_plant.economics import SOURCES, Prices, crf
from dioscuri_plant.investor import annuity_factor
from gemini_agent import cost_basis, engine, reliability, reporter, workbench
from gemini_agent.contract import DesignBrief


def money(items, opex):
    """Return an entry with only what ``versus_reference`` reads: capital items, running costs."""
    return SimpleNamespace(economics=SimpleNamespace(capex_items=items, opex_meur_per_year=opex))


class TestNpvAgainstGas(unittest.TestCase):
    """The NPV against gas buys each unit again when it wears out, on both sides."""

    def test_by_hand(self):
        """Design: wells 20 M€ (30 years), electric boiler 10 M€ (20), 1 M€ a year to run.

        Gas: boilers 2 M€ (25 years), 4 M€ a year. At 5 %, over 30 years:
        -28 at year 0, +3 a year (x 15.372: 46.12), -10 in year 20 (the boiler again:
        -3.77 today), +2 in year 25 (gas's boilers again: +0.59), and at year 30 what is left,
        each the rest of its annuity: the boiler's 10 of 20 years, 0.8024 x 7.7217 = 6.20 M€,
        less gas's 20 of 25, 0.1419 x 12.462 = 1.77 M€: +4.43, +1.02 today. NPV 15.96 M€;
        the old sum, -28 + 46.12, was 18.12 M€.
        """
        r, n = 0.05, 30
        design = money(
            [{"meur": 20.0, "life_years": 30}, {"meur": 10.0, "life_years": 20}], opex=1.0
        )
        gas = money([{"meur": 2.0, "life_years": 25}], opex=4.0)
        v = engine.versus_reference(design, gas, Prices(discount_rate=r), years=n)
        left = 10.0 * crf(r, 20) * annuity_factor(r, 10) - 2.0 * crf(r, 25) * annuity_factor(r, 20)
        hand = (
            -28.0
            + 3.0 * annuity_factor(r, n)
            - 10.0 / (1 + r) ** 20
            + 2.0 / (1 + r) ** 25
            + left / (1 + r) ** n
        )
        self.assertAlmostEqual(v["npv_meur"], round(hand, 2), places=2)
        self.assertAlmostEqual(hand, 15.96, delta=0.01)  # the old 18.12 left out the re-buys
        self.assertNotAlmostEqual(v["npv_meur"], -28.0 + 3.0 * annuity_factor(r, n), places=1)
        self.assertEqual(v["extra_capex_meur"], 28.0)
        self.assertEqual(v["reinvest_meur"], 8.0)  # 10 bought again, less gas's 2
        self.assertAlmostEqual(v["value_left_meur"], round(left, 2), places=2)
        self.assertAlmostEqual(v["cash_flow_meur"][-1], v["npv_meur"], places=2)
        self.assertEqual(len(v["cash_flow_meur"]), n + 1)
        # The year-20 re-buy shows in the cumulative flow, and payback is its first year >= 0.
        flow = v["cash_flow_meur"]
        self.assertAlmostEqual(flow[20] - flow[19], 3.0 / 1.05**20 - 10.0 / 1.05**20, places=3)
        first = next(t for t, x in enumerate(flow) if t > 0 and x >= 0)
        self.assertEqual(v["payback_years"], first)

    def test_irr_makes_the_flows_worth_nothing(self):
        """The IRR is the rate at which the same flows, re-buys and value left, add to zero."""
        design = money([{"meur": 12.0, "life_years": 20}], opex=1.0)
        gas = money([], opex=2.5)
        v = engine.versus_reference(design, gas, Prices(discount_rate=0.05), years=30)
        rate = v["irr"]
        left = 12.0 * crf(0.05, 20) * annuity_factor(0.05, 10)
        flows = [-12.0] + [1.5] * 30
        flows[20] -= 12.0
        flows[30] += left
        npv = sum(f / (1 + rate) ** t for t, f in enumerate(flows))
        # The value left is worked out at the plant's rate (5 %), so at the IRR the flows still
        # sum to (about) nothing.
        self.assertAlmostEqual(npv, 0.0, delta=0.01)

    def test_no_irr_without_extra_capital_or_payback(self):
        """No IRR when the design costs no more up front, or never earns its capital back."""
        self.assertIsNone(engine.irr([1.0, 1.0]))
        self.assertIsNone(engine.irr([-10.0, 0.1, 0.1]))
        self.assertAlmostEqual(engine.irr([-100.0, 110.0]), 0.10, places=3)


class TestCapitalKeys(unittest.TestCase):
    """One list of capital costs for "capital ×1.3", in the chat and on the Sensitivity tab."""

    def test_every_capital_cost_is_listed(self):
        """Every ``Prices`` field in M€ (per MW, MWh, doublet or train) and the wells' scale."""
        capital = {f.name for f in fields(Prices) if "meur" in f.name} | {"well_scale"}
        self.assertEqual(set(engine.CAPEX_KEYS), capital)
        self.assertEqual(list(workbench.CAPEX_KEYS), list(engine.CAPEX_KEYS))

    def test_scaled_prices_scale_every_capital_cost(self):
        """``capex_scale`` 1.3 multiplies each, the electric boiler and the store included."""
        base, scaled = Prices(), engine.prices_for({"capex_scale": 1.3})
        for k in ("electric_boiler_meur_per_mw", "treatment_train_meur", "storage_meur_per_mwh"):
            self.assertAlmostEqual(getattr(scaled, k), getattr(base, k) * 1.3, places=9)


class TestBasisWords(unittest.TestCase):
    """The discount rate's basis and the uncertainty's independent draws are said."""

    def test_rate_is_after_tax_without_tax_in_the_cost(self):
        """5.2 % real, PBL's after-tax WACC; no corporate tax in the cost of heat."""
        self.assertIn("after tax", SOURCES["discount_rate"])
        words = cost_basis.rate_words(0.052)
        self.assertEqual(
            words,
            "5.2 % real, PBL's after-tax WACC; corporate tax is not in the cost of heat; the "
            "investor case adds it",
        )
        self.assertIn("set in this chat", cost_basis.rate_words(0.08))

    def test_uncertainty_says_the_draws_are_independent(self):
        """The ranges' sentence says each input is drawn on its own, with no correlation."""
        card = {
            "design": "A1",
            "samples": 100,
            "draw": "triangular, most likely at the design's own value",
            "lcoe": {"p10": 50.0, "p50": 55.0, "p90": 60.0},
            "base": {"lcoe": 55.0},
            "base_percentile": {"lcoe": 0.5},
        }
        text = reliability.uncertainty_text(card, reporter.Facts(""))
        self.assertIn("independently of the others (no correlation between them)", text)


def fake(code, lcoe, flared, reliable=True, co2=1000.0, depths=(2500.0,), role="candidate"):
    """Return a design with what the picks and the depth note read."""
    return SimpleNamespace(
        alternative=SimpleNamespace(
            code=code,
            uid=code,
            role=role,
            reliable=reliable,
            gas="buy",
            depth_m=depths[0],
            doublets=[{"depth_m": d} for d in depths],
        ),
        economics=SimpleNamespace(lcoe_eur_per_mwh=lcoe, co2_t_per_year=co2, co2_saving_vs_gas=0.5),
        year=SimpleNamespace(
            heat_delivered_gwh=100.0, cool_delivered_gwh=0.0, produced_gas_flared_gwh=flared
        ),
    )


class TestFlaringRule(unittest.TestCase):
    """The plan the flaring step passed over for best overall is found, as the pick works."""

    def test_the_plan_set_aside_is_named(self):
        """A flares 4 GWh and is cheapest; B flares 0.3 GWh within 3 %: B is picked, A passed."""
        a, b = fake("A", 60.0, 4.0), fake("B", 61.0, 0.3)
        prices = Prices()
        picks = engine.pick_entries([a, b], prices)
        self.assertIs(picks["best"], b)
        self.assertIs(engine.flaring_passed_over([a, b], b, prices), a)

    def test_nothing_set_aside_when_the_cheapest_does_not_flare(self):
        """The cheapest flares under 1 GWh, or nothing flares less within 3 %: no pass-over."""
        prices = Prices()
        a, b = fake("A", 60.0, 0.5), fake("B", 61.0, 0.3)
        self.assertIsNone(engine.flaring_passed_over([a, b], a, prices))
        c, d = fake("C", 60.0, 4.0), fake("D", 70.0, 0.3)  # D is 17 % dearer
        self.assertIs(engine.pick_entries([c, d], prices)["best"], c)
        self.assertIsNone(engine.flaring_passed_over([c, d], c, prices))


class TestKnownAquifer(unittest.TestCase):
    """Every well at the known depth, and like with like."""

    def test_a_doublet_deeper_is_not_at_the_known_aquifer(self):
        """2,500 + 3,500 m is not at the known aquifer; a reliable pick meets reliable plans."""
        mixed = fake("2D@2500+3500", 50.0, 0.0, reliable=True, depths=(2500.0, 3500.0))
        plain = fake("1D@2500", 55.0, 0.0, reliable=False)
        plan = fake("1D@2500-N1", 58.0, 0.0, reliable=True)
        pick = fake("1D@3000-N1", 56.0, 0.0, reliable=True, depths=(3000.0,), role="chosen")
        out = SimpleNamespace(tried=[mixed, plain, plan, pick])
        self.assertEqual(reporter.at_known_aquifer(out, pick, 2500.0), (plan, True))
        # Without a reliable plan there, the cheapest design, said to be the cheapest.
        out = SimpleNamespace(tried=[mixed, plain, pick])
        self.assertEqual(reporter.at_known_aquifer(out, pick, 2500.0), (plain, False))


class TestOneGasReference(unittest.TestCase):
    """One search: every design, options or not, against the same gas plant."""

    @classmethod
    def setUpClass(cls):
        """Search the challenge once."""
        cls.outcome = engine.search(DesignBrief())
        cls.options = [
            e
            for e in cls.outcome.candidates
            if e.alternative.role in ("chosen", "candidate") and e.brief.rules
        ]

    def test_options_meet_the_plain_reference(self):
        """A design with free cooling or solar: its reference is the search's, without them."""
        self.assertTrue(self.options)
        plain = self.outcome.reference.economics
        for e in self.options[:4]:
            ref = engine.reference(e.brief).economics
            self.assertAlmostEqual(ref.co2_t_per_year, plain.co2_t_per_year, places=3)
            self.assertAlmostEqual(ref.lcoc_eur_per_mwh, plain.lcoc_eur_per_mwh, places=3)
            saving = 1 - e.economics.co2_t_per_year / ref.co2_t_per_year
            self.assertAlmostEqual(e.economics.co2_saving_vs_gas, saving, places=3)

    def test_repricing_keeps_the_saving(self):
        """Run again (``reprice``), an option design keeps its CO2 saving against gas."""
        e = self.options[0]
        again = engine.reprice(e, {}, with_firm=False)
        self.assertAlmostEqual(
            again.economics.co2_saving_vs_gas, e.economics.co2_saving_vs_gas, places=3
        )

    def test_reply_states_the_flaring_rule(self):
        """The rule in the reply has the flaring step; a plan it set aside is named."""
        text = reporter.challenge_answer(self.outcome, reporter.Facts(""))
        self.assertIn("unless that plan flares more than 1 GWh", text)
        prices = engine.prices_for(None, self.outcome.chosen.brief)
        passed = engine.flaring_passed_over(self.outcome.candidates, self.outcome.chosen, prices)
        if passed is not None:
            self.assertIn(f"The flaring rule decided it: {reporter.design_id(passed)}", text)

    def test_capital_sensitivity_scales_all_capital(self):
        """Capital ×1.3 on the Sensitivity tab equals ``capex_scale`` 1.3, and is not doubled."""
        e = next(
            (x for x in self.outcome.candidates if x.alternative.sizes_mw.get("electric_boiler")),
            self.outcome.chosen,
        )
        base = e.economics.capex_meur
        tab = workbench._evaluate(e, {}, {"capex": 1.3}, ["capex_meur"])["capex_meur"]
        chat = engine.reprice(e, {"capex_scale": 1.3}, with_firm=False).economics.capex_meur
        self.assertAlmostEqual(tab, chat, delta=0.01)
        self.assertAlmostEqual(tab, base * 1.3, delta=0.05)
        once = workbench._evaluate(e, {"capex_scale": 1.3}, {"capex": 1.0}, ["capex_meur"])
        self.assertAlmostEqual(once["capex_meur"], base * 1.3, delta=0.05)

    def test_demand_swing_scales_the_gas_plant_too(self):
        """The NPV for 20 % more heat is against gas for 20 % more heat."""
        e = self.outcome.chosen
        got = workbench._evaluate(e, {}, {"heat_demand": 1.2}, ["npv_meur"])["npv_meur"]
        design = engine.evaluate(e.alternative, e.brief, {}, scale=(1.2, 1.0), with_firm=False)
        gas = engine.reference(e.brief.model_copy(update={"demand_scale": [1.2, 1.0]}))
        want = engine.versus_reference(design, gas, engine.prices_for({}, e.brief))["npv_meur"]
        self.assertAlmostEqual(got, want, places=2)


if __name__ == "__main__":
    unittest.main()
