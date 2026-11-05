"""The investor's view: SDE++ category and cap, tax on profit, cash flow and return by hand."""

import unittest
from dataclasses import replace
from types import SimpleNamespace

from dioscuri_plant import Plant, Prices, Rules
from dioscuri_plant import investor as inv
from dioscuri_plant.economics import crf

RULES = Rules()
PRICES = Prices()
# Brine at one doublet's cap: 300 m3/h x 1,030 kg/m3 x 3,990 J/(kg K) = 0.342475 MW/K.
MW_PER_K = 300 / 3600 * 1030 * 3990 / 1e6
# Hand checks without inflation: euros of the day are today's euros.
FLAT = inv.InvestorTerms(inflation=0.0)


def year(geo=40.0, hp=0.0, boiler=10.0, heat=50.0, cold=0.0, cooling=40.0, network=None, hp_el=0.0):
    """Return a year with the fields the investor's case reads (GWh, K)."""
    return SimpleNamespace(
        heat_split_gwh={"geo": geo, "hp": hp, "boiler": boiler},
        electricity_gwh={"hp": hp_el},
        heat_delivered_gwh=heat,
        cool_delivered_gwh=cold,
        max_brine_cooling_k=cooling,
        network=network,
    )


def econ(items=None, opex=1.0):
    """Return the costs the investor's case reads: capital items and running costs a year."""
    items = items if items is not None else [{"meur": 15.0, "life_years": 30}]
    return SimpleNamespace(capex_items=items, opex_meur_per_year=opex)


REF = SimpleNamespace(lcoh_eur_per_mwh=80.0, lcoc_eur_per_mwh=40.0)


def case(plant=Plant(1), y=None, e=None, terms=FLAT, ref=REF, prices=PRICES):
    """Return the investor's case of a design (one doublet by default)."""
    return inv.investor_case(plant, y or year(), e or econ(), RULES, prices, ref, terms)


class TestCategory(unittest.TestCase):
    """The SDE++ category follows the plant's geothermal capacity."""

    def test_capacity_is_the_brine_at_the_cap_flow(self):
        """One doublet at 300 m3/h: 13.70 MW at 40 K, 10.62 MW at 31 K; never past 40 K."""
        mw, k, flow = inv.thermal_capacity(Plant(1), RULES, year(cooling=40.0))
        self.assertAlmostEqual(mw, MW_PER_K * 40, places=6)
        self.assertEqual((k, flow), (40.0, 300.0))
        self.assertAlmostEqual(
            inv.thermal_capacity(Plant(1), RULES, year(cooling=31))[0], 10.617, 3
        )
        self.assertEqual(inv.thermal_capacity(Plant(1), RULES, year(cooling=55))[1], 40.0)
        self.assertEqual(inv.thermal_capacity(Plant(0), RULES, year())[0], 0.0)
        self.assertAlmostEqual(inv.thermal_capacity(Plant(2), RULES, None)[0], MW_PER_K * 80, 6)

    def test_category_by_capacity(self):
        """Under 12 MW 79.9, 12 to 20 MW 69.6, from 20 MW 62.7 €/MWh; 6,000 h each."""
        for mw, key, basis in (
            (8.0, "base_lt12", 0.0799),
            (11.99, "base_lt12", 0.0799),
            (12.0, "base_12_20", 0.0696),
            (19.99, "base_12_20", 0.0696),
            (20.0, "base_ge20", 0.0627),
            (27.4, "base_ge20", 0.0627),
        ):
            c = inv.category_for(mw)
            self.assertEqual((c.key, c.basis_eur_per_kwh, c.full_load_hours), (key, basis, 6000))
        self.assertEqual(case(Plant(2)).sde["category"]["key"], "base_ge20")
        self.assertEqual(case(Plant(1), year(cooling=31)).sde["category"]["key"], "base_lt12")

    def test_a_chosen_category_is_used_and_checked(self):
        """A category the user picks is used, and said when the plant is outside its range."""
        c = case(terms=replace(FLAT, sde_category="ht_hp_lt12"))
        self.assertEqual(c.sde["category"]["key"], "ht_hp_lt12")
        self.assertEqual(c.sde["chosen_by"], "you")
        self.assertFalse(c.sde["fits"])  # no heat pump: the installation is 0 MW
        self.assertIn("outside this category's size range", " ".join(c.notes))
        big = case(Plant(1, heat_pump_mw=13.0), terms=replace(FLAT, sde_category="ht_hp_lt12"))
        self.assertFalse(big.sde["fits"])  # a 13 MW heat pump is not under 12 MW
        base = case(terms=replace(FLAT, sde_category="base_lt12"))
        self.assertFalse(base.sde["fits"])  # 13.7 MW of brine is not under 12 MW
        with self.assertRaises(ValueError):
            inv.category_for(10.0, "nonsense")


class TestSubsidy(unittest.TestCase):
    """SDE++ per kWh, its floor, the CO2 part from 2028 and the 6,000-hour cap."""

    def test_basis_less_the_correction_and_the_co2_part_from_2028(self):
        """69.6 - 19.6 = 50.0 €/MWh in 2027; 69.6 - 19.6 - 11.4 = 38.6 €/MWh from 2028."""
        c = inv.BY_KEY["base_12_20"]
        self.assertAlmostEqual(inv.subsidy_eur_per_kwh(c, 1, FLAT), 0.0500, places=6)
        self.assertAlmostEqual(inv.subsidy_eur_per_kwh(c, 2, FLAT), 0.0386, places=6)
        self.assertAlmostEqual(inv.subsidy_eur_per_kwh(c, 15, FLAT), 0.0386, places=6)

    def test_the_correction_never_falls_below_the_floor(self):
        """Cheap gas (TTF 10 €/MWh): the correction is the floor, 13.1 €/MWh, not 7.0."""
        cheap = replace(FLAT, ttf_eur_per_kwh=0.010)
        c = inv.BY_KEY["base_lt12"]
        self.assertAlmostEqual(inv.correction_eur_per_kwh(c, 1, cheap), 0.0131, places=6)
        self.assertAlmostEqual(inv.subsidy_eur_per_kwh(c, 1, cheap), 0.0799 - 0.0131, places=6)
        dear = replace(FLAT, ttf_eur_per_kwh=0.2)  # the correction above the basisbedrag
        self.assertEqual(inv.subsidy_eur_per_kwh(c, 1, dear), 0.0)

    def test_subsidised_heat_is_capped_at_6000_hours(self):
        """100 GWh of geothermal heat, 13.70 MW x 6,000 h = 82.2 GWh earns subsidy."""
        c = case(y=year(geo=80.0, hp=20.0, heat=110.0))
        cap = MW_PER_K * 40 * 6000 / 1000
        self.assertTrue(c.sde["capped"])
        self.assertAlmostEqual(c.sde["eligible_gwh"], 100.0, places=3)
        self.assertAlmostEqual(c.sde["subsidised_gwh"], cap, places=3)
        self.assertAlmostEqual(c.flows[1]["sde"], cap * 0.05, places=3)
        self.assertIn("SDE++ is capped", " ".join(c.notes))

    def test_only_geothermal_heat_for_15_years(self):
        """The boiler's heat and the cold earn nothing; years 16 to 30 get no subsidy."""
        c = case(y=year(geo=40.0, hp=5.0, boiler=60.0, heat=105.0, cold=20.0, hp_el=1.5))
        self.assertAlmostEqual(c.sde["subsidised_gwh"], 40.0 + 5.0 - 1.5, places=6)
        self.assertEqual([f["sde"] > 0 for f in c.flows].count(True), 15)
        self.assertEqual((c.sde["first_year"], c.sde["last_year"]), (1, 15))
        self.assertEqual(c.sde["calendar_years"], [2027, 2041])
        self.assertEqual(c.flows[16]["sde"], 0.0)

    def test_inflation_shrinks_the_subsidy_in_todays_euros(self):
        """2 % a year from the prices' 2025: year 2 (2028)'s 1.544 M€ is 1.544 / 1.02^3."""
        c = case(terms=inv.InvestorTerms())
        self.assertAlmostEqual(c.flows[2]["sde"], 40 * 0.0386 / 1.02**3, places=3)
        self.assertAlmostEqual(c.flows[2]["revenue_heat"], 4.0, places=6)  # sold at today's price

    def test_year_one_is_two_years_after_the_prices(self):
        """Costs in 2025 euros, year 1 is 2027: its euros of the day are 2025's x 1.02^2.

        Year 1 by hand: sales less running costs 3 M€ (2025) = 3 x 1.0404 = 3.1212 of the
        day; SDE++ 2.0; the 15 M€ built in 2026 (x 1.02) written off over 15 years, 1.02.
        Profit 4.1012, tax 0.2 x 0.19 + 3.9012 x 0.258 = 1.044510 of the day. In 2025 euros:
        SDE++ 2.0 / 1.0404 = 1.922338, tax 1.003951; net 4 - 1 + 1.922338 - 1.003951 =
        3.918387.
        """
        c = case(terms=inv.InvestorTerms())
        self.assertAlmostEqual(c.flows[1]["sde"], 2.0 / 1.02**2, places=3)
        self.assertAlmostEqual(c.flows[1]["tax"], -1.044510 / 1.0404, places=3)
        self.assertAlmostEqual(c.flows[1]["net"], 3.918387, places=3)
        # Prices of 2026 would put year 1 one year on (the old indexing): 2.0 / 1.02.
        old = case(terms=inv.InvestorTerms(price_year=2026))
        self.assertAlmostEqual(old.flows[1]["sde"], 2.0 / 1.02, places=3)
        self.assertIn("All money in 2025 euros", " ".join(c.notes))


class TestHeatPumpHeat(unittest.TestCase):
    """SDE++ pays for geothermal heat, not the heat pump's electricity (review E6)."""

    def test_base_load_pays_the_brine_heat_not_the_heat_pumps_electricity(self):
        """Exchanger 40 GWh + heat pump 15 GWh of which 4 GWh electricity: 51 GWh eligible."""
        c = case(Plant(1, heat_pump_mw=2.0), y=year(geo=40.0, hp=15.0, hp_el=4.0, heat=70.0))
        self.assertEqual(c.sde["category"]["key"], "base_12_20")
        self.assertAlmostEqual(c.sde["eligible_gwh"], 51.0, places=6)
        self.assertAlmostEqual(c.sde["subsidised_gwh"], 51.0, places=6)
        self.assertEqual(c.sde["installation"], "geothermal")
        self.assertAlmostEqual(c.flows[1]["sde"], 51.0 * 0.05, places=3)
        self.assertIn("heat pump's electricity (4 GWh)", " ".join(c.notes))

    def test_with_heat_pump_the_heat_pump_is_the_installation(self):
        """With heat pump ('met warmtepomp'): the 2 MW heat pump is the capacity, 12 GWh at most."""
        terms = replace(FLAT, sde_category="ht_hp_lt12")
        c = case(Plant(1, heat_pump_mw=2.0), y=year(geo=40.0, hp=15.0, hp_el=4.0), terms=terms)
        self.assertEqual(c.sde["installation"], "heat pump")
        self.assertAlmostEqual(c.sde["installation_mw"], 2.0, places=6)
        self.assertAlmostEqual(c.sde["eligible_gwh"], 55.0, places=6)  # source and heat pump
        self.assertAlmostEqual(c.sde["cap_gwh"], 12.0, places=6)
        self.assertAlmostEqual(c.sde["subsidised_gwh"], 12.0, places=6)
        self.assertTrue(c.sde["capped"] and c.sde["fits"])
        self.assertAlmostEqual(c.sde["capacity_mw"], MW_PER_K * 40, places=2)  # the brine's
        per_kwh = inv.subsidy_eur_per_kwh(inv.BY_KEY["ht_hp_lt12"], 1, terms)
        self.assertAlmostEqual(c.flows[1]["sde"], 12.0 * per_kwh, places=3)
        self.assertIn("2 MW × 6,000 h", " ".join(c.notes))

    def test_a_heat_pump_category_needs_a_heat_pump(self):
        """No heat pump: nothing subsidised in a 'with heat pump' category."""
        terms = replace(FLAT, sde_category="ht_hp_ge12")
        c = case(Plant(1), y=year(geo=40.0), terms=terms)
        self.assertEqual(c.sde["subsidised_gwh"], 0.0)
        self.assertFalse(c.sde["fits"])


class TestTax(unittest.TestCase):
    """Corporate tax: two rates, on profit only, losses carried forward."""

    def test_two_rates(self):
        """1 M€ of profit: 0.2 x 19 % + 0.8 x 25.8 % = 0.2444 M€; 0.1 M€: 19 %."""
        self.assertAlmostEqual(inv.corporate_tax(1.0, FLAT), 0.2444, places=6)
        self.assertAlmostEqual(inv.corporate_tax(0.1, FLAT), 0.019, places=6)
        self.assertEqual(inv.corporate_tax(-3.0, FLAT), 0.0)

    def test_losses_carried_forward(self):
        """A 1 M€ loss wipes out the next 1 M€ of profit: tax only on the 0.5 M€ after it."""
        self.assertEqual(inv.taxes([0.0, -1.0, 0.5, 1.0], FLAT)[:3], [0.0, 0.0, 0.0])
        self.assertAlmostEqual(inv.taxes([0.0, -1.0, 0.5, 1.0], FLAT)[3], 0.038 + 0.3 * 0.258, 6)

    def test_no_profit_no_tax(self):
        """Sales below the running costs, no subsidy: a loss every year, no tax ever."""
        c = case(e=econ(opex=6.0), terms=replace(FLAT, sde_on=False))
        self.assertTrue(all(f["tax"] == 0.0 for f in c.flows))
        self.assertEqual(c.tax["total_meur"], 0.0)
        self.assertIsNone(c.tax["first_tax_year"])


class TestCashFlow(unittest.TestCase):
    """The whole case against a hand calculation."""

    def test_by_hand(self):
        """15 M€, 4 M€ of heat sold, 1 M€ running, 40 GWh subsidised in 12-20 MW.

        Year 1: profit 4 - 1 + 2.0 - 1 (write-off) = 4.0, tax 0.038 + 3.8 x 0.258 = 1.0184.
        Years 2-15: profit 3 + 1.544 - 1 = 3.544, tax 0.900752. Years 16-30: profit 3, tax
        0.7604. NPV at 5.2 %: 33.353 M€.
        """
        c = case()
        self.assertEqual(c.sde["category"]["key"], "base_12_20")
        self.assertAlmostEqual(c.revenue_heat_meur, 4.0, places=6)
        self.assertAlmostEqual(c.flows[1]["sde"], 2.0, places=3)
        self.assertAlmostEqual(c.flows[1]["tax"], -1.0184, places=3)
        self.assertAlmostEqual(c.flows[1]["net"], 3.9816, places=3)
        self.assertAlmostEqual(c.flows[2]["net"], 3.643248, places=3)
        self.assertAlmostEqual(c.flows[16]["tax"], -0.7604, places=3)
        self.assertAlmostEqual(c.flows[30]["net"], 2.2396, places=3)
        self.assertAlmostEqual(c.flows[0]["net"], -15.0, places=6)
        self.assertAlmostEqual(c.npv_meur, 33.35, places=2)
        self.assertEqual(c.value_left_meur, 0.0)  # the wells last the 30 years

    def test_npv_irr_and_payback_agree_with_the_flows(self):
        """The NPV is the flows discounted; at the IRR they add up to zero; payback in between."""
        c = case(terms=inv.InvestorTerms())
        net = [f["net"] for f in c.flows]
        self.assertAlmostEqual(inv.npv(net, PRICES.discount_rate), c.npv_meur, places=1)
        self.assertAlmostEqual(c.flows[-1]["cumulative"], c.npv_meur, places=1)
        self.assertAlmostEqual(inv.npv(net, c.irr), 0.0, delta=0.01)
        self.assertGreater(c.irr, PRICES.discount_rate)  # NPV > 0
        before = c.flows[int(c.payback_years)]["cumulative"]
        after = c.flows[int(c.payback_years) + 1]["cumulative"]
        self.assertLess(before, 0)
        self.assertGreaterEqual(after, 0)

    def test_simple_flows(self):
        """-100 then 110: IRR 10 %; 20 back of 100: a negative IRR, no payback; none back."""
        self.assertAlmostEqual(inv.irr([-100.0, 110.0]), 0.10, places=4)
        self.assertAlmostEqual(inv.discounted_payback([-100.0, 210.0], 0.0), 0.5, places=6)
        self.assertLess(inv.irr([-100.0, 10.0, 10.0]), 0.0)
        self.assertIsNone(inv.discounted_payback([-100.0, 10.0, 10.0], 0.05))
        self.assertIsNone(inv.irr([-100.0, -10.0]))

    def test_units_bought_again_cost_their_annuities(self):
        """A 20-year unit is bought at 0 and 20; its value at 30 leaves the annuities' worth."""
        items = [{"meur": 10.0, "life_years": 20}]
        r = PRICES.discount_rate
        spend, left, buys = inv.capital_flows(items, 30, r)
        self.assertEqual(buys, [(0, 10.0), (20, 10.0)])
        self.assertAlmostEqual(left, 10.0 * crf(r, 20) * inv.annuity_factor(r, 10), places=9)
        present = inv.npv(spend, r) - left / (1 + r) ** 30
        self.assertAlmostEqual(present, 10.0 * crf(r, 20) * inv.annuity_factor(r, 30), places=9)
        c = case(e=econ(items=items))
        self.assertAlmostEqual(c.flows[20]["capital"], -10.0, places=6)
        self.assertAlmostEqual(c.flows[30]["value_left"], round(left, 3), places=6)

    def test_sale_prices_default_to_the_gas_reference_and_can_be_set(self):
        """Heat at the reference's 80 €/MWh, cold at 40 €/MWh; the user's prices replace them."""
        c = case(y=year(cold=10.0))
        self.assertEqual((c.heat_sale_eur_per_mwh, c.cold_sale_eur_per_mwh), (80.0, 40.0))
        self.assertAlmostEqual(c.revenue_cold_meur, 0.4, places=6)
        mine = case(y=year(cold=10.0), terms=replace(FLAT, heat_sale_eur_per_mwh=100.0))
        self.assertAlmostEqual(mine.revenue_heat_meur, 5.0, places=6)
        self.assertEqual(mine.sale_basis, {"heat": "yours", "cold": "gas reference"})
        lost = case(y=year(network={"heat_loss_gwh": 5.0}))
        self.assertAlmostEqual(lost.heat_sold_gwh, 45.0, places=6)  # losses are not sold


class TestNoSubsidy(unittest.TestCase):
    """Designs without SDE++, and the subsidy that would break even."""

    def test_no_wells_no_subsidy(self):
        """A plant without doublets has no geothermal heat: no SDE++, no break-even basis."""
        c = case(Plant(0), y=year(geo=0.0, hp=0.0, cooling=0.0))
        self.assertEqual(c.sde["subsidised_gwh"], 0.0)
        self.assertTrue(all(f["sde"] == 0.0 for f in c.flows))
        self.assertIsNone(c.break_even_basis_eur_per_kwh)

    def test_switched_off_equals_the_case_without(self):
        """SDE++ off: the same NPV as the case's own 'without SDE++' figures."""
        off = case(terms=replace(FLAT, sde_on=False))
        on = case()
        self.assertTrue(all(f["sde"] == 0.0 for f in off.flows))
        self.assertEqual(off.npv_meur, on.without_sde["npv_meur"])
        self.assertLess(off.npv_meur, on.npv_meur)
        self.assertIn("switched off", " ".join(off.notes))

    def test_break_even_basisbedrag(self):
        """A plant that loses money without subsidy breaks even at the basisbedrag found."""
        dear = econ(items=[{"meur": 60.0, "life_years": 30}])
        c = case(e=dear)
        self.assertTrue(c.needs_subsidy)
        be = c.break_even_basis_eur_per_kwh
        self.assertIsNotNone(be)
        self.assertGreater(be, 0.0196 + 0.0114)  # above the correction, or it pays nothing
        at = case(e=dear, terms=replace(FLAT, sde_basis_eur_per_kwh=be))
        self.assertAlmostEqual(at.npv_meur, 0.0, delta=0.02)
        self.assertIsNone(case().break_even_basis_eur_per_kwh)  # pays without subsidy


class TestOverrides(unittest.TestCase):
    """A conversation's choices: checked, and turned into terms."""

    def test_terms_from_assumptions(self):
        """Known keys change the terms; prices of the plant and None are left alone."""
        t = inv.terms_from(
            {
                "heat_sale_eur_per_mwh": "95",
                "sde_on": False,
                "sde_category": "base_ge20",
                "cold_sale_eur_per_mwh": None,
                "gas_eur_per_mwh": 50.0,
            }
        )
        self.assertEqual(t.heat_sale_eur_per_mwh, 95.0)
        self.assertFalse(t.sde_on)
        self.assertEqual(t.sde_category, "base_ge20")
        self.assertIsNone(t.cold_sale_eur_per_mwh)

    def test_bad_values_are_refused(self):
        """A negative price, an unknown category or a word for on/off is a ValueError."""
        for key, value in (
            ("heat_sale_eur_per_mwh", -1),
            ("heat_sale_eur_per_mwh", "cheap"),
            ("cold_sale_eur_per_mwh", True),
            ("sde_category", "big"),
            ("sde_on", "maybe"),
            ("other", 1),
        ):
            with self.assertRaises(ValueError):
                inv.override(key, value)
        self.assertEqual(inv.override("sde_on", "false"), False)

    def test_view_lists_what_can_change(self):
        """The app gets the four inputs with their defaults and the category choices."""
        t = replace(FLAT, heat_sale_eur_per_mwh=90.0)
        v = inv.view(case(terms=t), t, REF)
        keys = [i["key"] for i in v["inputs"]]
        self.assertEqual(keys, list(inv.OVERRIDES))
        heat = v["inputs"][0]
        self.assertEqual((heat["value"], heat["default"], heat["changed"]), (90.0, 80.0, True))
        options = v["inputs"][2]["options"]
        self.assertEqual(options[0]["key"], "auto")
        self.assertEqual(len(options), len(inv.CATEGORIES) + 1)
        self.assertEqual(len(v["flows"]), PRICES.wells_life_years + 1)


if __name__ == "__main__":
    unittest.main()
