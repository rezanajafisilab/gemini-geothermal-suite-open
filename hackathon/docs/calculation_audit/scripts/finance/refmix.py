from common import *
from dioscuri_plant import investor
from dataclasses import replace
d, s = lead_session()
c = s.chosen
prices = engine.prices_for(None, c.brief); rules = engine.rules_for(c.brief); plant = engine.plant_of(c.alternative)
ref_fc = engine.reference(c.brief, None)
ref_search = s.reference
for name, ref in (('ref with FC (Economics tab, chat)', ref_fc), ('search ref, no FC (CO2 saving basis)', ref_search)):
    case = investor.investor_case(plant, c.year, c.economics, rules, prices, ref.economics, investor.InvestorTerms())
    print(name, 'ref LCOH', ref.economics.lcoh_eur_per_mwh, 'LCOC', ref.economics.lcoc_eur_per_mwh, 'CO2', ref.economics.co2_t_per_year, '-> NPV', case.npv_meur, 'IRR', case.irr, 'payback', case.payback_years, 'saving', round(1-c.economics.co2_t_per_year/ref.economics.co2_t_per_year,4))
    v = engine.versus_reference(c, ref, prices); print('   versus NPV', v['npv_meur'], 'payback', v['payback_years'], 'cold cmp design', c.economics.lcoc_eur_per_mwh)
# inflation-index offset: prices are 2025 EUR, year 1 = 2027. Emulate by shifting nominal conversion by one year:
# equivalent to deflating SDE and write-offs by one more year relative to real costs -> scale sde basis & correction and capex write-off
# Here: emulate with first_year unchanged but inflation applied as (1+i)^(t+1): approximate by scaling SDE and write-offs by 1/1.02 (one year) and 1/1.0404 (two years)
import math
base = investor.investor_case(plant, c.year, c.economics, rules, prices, ref_fc.economics, investor.InvestorTerms())
for k, f in ((1, 1/1.02), (2, 1/1.0404)):
    t = replace(investor.InvestorTerms(), sde_basis_eur_per_kwh=None)
    # scale the category basis and correction by f (SDE amounts are nominal; in 2025 EUR they are worth f as much)
    cat = investor.category_for(base.sde['capacity_mw'])
    t2 = replace(t, sde_basis_eur_per_kwh=cat.basis_eur_per_kwh*f, ttf_eur_per_kwh=t.ttf_eur_per_kwh*f, correction_floor_eur_per_kwh=t.correction_floor_eur_per_kwh*f)
    import dioscuri_plant.investor as inv
    old = inv.ETS2
    case = investor.investor_case(plant, c.year, c.economics, rules, prices, ref_fc.economics, t2)
    print(f'offset {k} yr (SDE only; ETS part not scaled): NPV', case.npv_meur, 'vs', base.npv_meur, 'IRR', case.irr, 'vs', base.irr)
