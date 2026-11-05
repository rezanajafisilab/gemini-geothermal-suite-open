from common import *
d, s = lead_session()
prices = engine.prices_for(None, s.chosen.brief)
ents=[e for e in s.candidates if e.alternative.role in ('chosen','candidate')]
k2=[e for e in ents if all(abs(float(dd.get('depth_m') or 2500)-2500)<1e-6 for dd in e.alternative.doublets)]
rel=[e for e in k2 if e.alternative.reliable]
print('all-2500 designs', len(k2), 'reliable', len(rel))
for e in sorted(rel, key=lambda e: engine.shadow_cost(e, prices))[:3]:
    print(e.alternative.uid, e.alternative.code, e.economics.lcoe_eur_per_mwh, e.economics.lcoh_eur_per_mwh, round(engine.shadow_cost(e,prices),2), e.year.produced_gas_flared_gwh)
c=min(k2, key=lambda e: e.economics.lcoe_eur_per_mwh); print('cheapest all-2500', c.alternative.code, c.economics.lcoe_eur_per_mwh, c.economics.lcoh_eur_per_mwh, 'gap', round(c.economics.lcoe_eur_per_mwh - s.chosen.economics.lcoe_eur_per_mwh,2))
a93=next(e for e in ents if e.alternative.uid=='A93'); print('A93', a93.economics.lcoh_eur_per_mwh, a93.economics.lcoe_eur_per_mwh, [dd.get('depth_m') for dd in a93.alternative.doublets])
