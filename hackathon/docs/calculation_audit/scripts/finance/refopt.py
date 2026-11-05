from common import *
from dioscuri_plant import investor
d, s = lead_session()
base_ref = s.reference
print('search ref', base_ref.economics.lcoh_eur_per_mwh, base_ref.economics.lcoc_eur_per_mwh, base_ref.economics.capex_meur, base_ref.economics.co2_t_per_year)
seen=set()
for e in s.candidates:
    r = e.brief.rules or {}
    key = tuple(sorted(r.items()))
    if not r or key in seen: continue
    seen.add(key)
    ref = engine.reference(e.brief, None)
    items = [it['item'] for it in (ref.economics.capex_items or [])]
    prices = engine.prices_for(None, e.brief)
    case = investor.investor_case(engine.plant_of(e.alternative), e.year, e.economics, engine.rules_for(e.brief), prices, ref.economics, investor.InvestorTerms())
    case0 = investor.investor_case(engine.plant_of(e.alternative), e.year, e.economics, engine.rules_for(e.brief), prices, base_ref.economics, investor.InvestorTerms())
    print(e.alternative.uid, e.alternative.code, r, '| ref LCOH', ref.economics.lcoh_eur_per_mwh, 'LCOC', ref.economics.lcoc_eur_per_mwh, 'capex', ref.economics.capex_meur, 'items', items, '| investor NPV (tab)', case.npv_meur, 'vs with plain ref', case0.npv_meur, '| co2 saving stored', e.economics.co2_saving_vs_gas, 'vs tab ref', round(1-e.economics.co2_t_per_year/ref.economics.co2_t_per_year,4))
