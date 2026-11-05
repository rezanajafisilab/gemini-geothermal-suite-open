from common import *
import math
from dioscuri_plant import investor
from dioscuri_plant.economics import crf
d, s = lead_session()
c = s.chosen
ref = engine.reference(c.brief, None)
prices = engine.prices_for(None, c.brief)
rules = engine.rules_for(c.brief)
plant = engine.plant_of(c.alternative)
print('ref LCOH', ref.economics.lcoh_eur_per_mwh, 'LCOC', ref.economics.lcoc_eur_per_mwh, 'capex', ref.economics.capex_meur, 'opex', ref.economics.opex_meur_per_year)
terms = investor.InvestorTerms()
case = investor.investor_case(plant, c.year, c.economics, rules, prices, ref.economics, terms)
import json
print('heat price', case.heat_sale_eur_per_mwh, 'cold', case.cold_sale_eur_per_mwh)
print('rev', case.revenue_heat_meur, case.revenue_cold_meur, 'opex', case.opex_meur, 'capex', case.capex_meur, 'reinvest', case.reinvest_meur, 'left', case.value_left_meur)
print('sde', {k:v for k,v in case.sde.items() if k!='category'}, case.sde['category']['key'])
print('tax', case.tax)
print('NPV', case.npv_meur, 'IRR', case.irr, 'payback', case.payback_years, 'without', case.without_sde, 'break_even', case.break_even_basis_eur_per_kwh)
for r in case.flows[:4]+case.flows[14:18]+case.flows[24:]: print(r)
v = engine.versus_reference(c, ref, prices)
print('versus', {k:v[k] for k in v if k!='cash_flow_meur'})
pickle.dump(dict(case=case, ref=ref), open(HERE+'/inv.pkl','wb'))
