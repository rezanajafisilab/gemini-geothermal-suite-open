from common import *
d, s = lead_session()
prices = engine.prices_for(None, s.chosen.brief)
ents = s.candidates
print('n candidates', len(ents))
ref = s.reference
print('search ref co2', ref.economics.co2_t_per_year, 'LCOC', ref.economics.lcoc_eur_per_mwh, 'brief rules', ref.brief.rules)
print('chosen cached co2 saving', s.chosen.economics.co2_saving_vs_gas, 1-s.chosen.economics.co2_t_per_year/ref.economics.co2_t_per_year)
def show(e):
    a=e.alternative; y=e.year
    print(f"{a.uid:5s} {a.code:32s} role={a.role:9s} rel={a.reliable!s:5s} lcoe={e.economics.lcoe_eur_per_mwh:7.2f} co2={e.economics.co2_t_per_year:8.0f} shadow={engine.shadow_cost(e,prices):7.2f} flared={y.produced_gas_flared_gwh:6.2f} capex={e.economics.capex_meur:6.2f} picks={a.picks} depth={a.depth_m} doublets={[dd.get('depth_m') for dd in a.doublets]}")
valid=[e for e in ents if e.alternative.role in ('chosen','candidate')]
plans=[e for e in valid if e.alternative.reliable]
for e in sorted(plans, key=lambda e: engine.shadow_cost(e,prices))[:8]: show(e)
print('--- plain cheapest')
plain=[e for e in valid if not e.alternative.reliable]
for e in sorted(plain, key=lambda e: e.economics.lcoe_eur_per_mwh)[:5]: show(e)
print('--- lowest co2 plain')
for e in sorted(plain, key=lambda e: e.economics.co2_t_per_year)[:5]: show(e)
print('--- 2D-BO-EC@2500+3500-BL')
for e in ents:
    if e.alternative.code.startswith('2D-BO-EC@2500+3500'): show(e)
print('--- at depth_m 2500 cheapest')
k=[e for e in ents if e.alternative.role in ('chosen','candidate') and abs((e.alternative.depth_m or 0)-2500)<1e-6]
for e in sorted(k, key=lambda e: e.economics.lcoe_eur_per_mwh)[:4]: show(e)
k2=[e for e in k if all(abs(float(dd.get('depth_m') or 2500)-2500)<1e-6 for dd in e.alternative.doublets)]
print('--- truly all wells at 2500')
for e in sorted(k2, key=lambda e: e.economics.lcoe_eur_per_mwh)[:4]: show(e)
print('notes:'); [print(' -', n) for n in s.searches[-1].get('notes', [])] if isinstance(s.searches[-1], dict) else None
print(s.searches[-1].keys() if isinstance(s.searches[-1], dict) else type(s.searches[-1]))
