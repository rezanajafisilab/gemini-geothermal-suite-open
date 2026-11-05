from common import *
pr = PRICES
extra = max(0.0, pr.carbon_long_term_eur_per_t - pr.carbon_eur_per_t)
print('carbon', pr.carbon_eur_per_t, 'long', pr.carbon_long_term_eur_per_t, 'extra', extra)
rows=[]
for e in CANDS:
    a=e['alternative']
    if a['role'] not in ('chosen','candidate'): continue
    y=e['year']; ec=e['economics']
    mwh=(y['heat_delivered_gwh']+y['cool_delivered_gwh'])*1000
    sh = ec['lcoe_eur_per_mwh'] + extra*ec['co2_t_per_year']/mwh
    rows.append((a['uid'], a['code'], a['reliable'], ec['lcoe_eur_per_mwh'], ec['co2_t_per_year'], sh, y.get('produced_gas_flared_gwh'), a['picks'], a['gas']))
print('valid', len(rows))
rel=[r for r in rows if r[2]]
plain=[r for r in rows if not r[2]]
print('top reliable by shadow:')
for r in sorted(rel, key=lambda r:r[5])[:6]: print('  ', r)
print('top plain by lcoe:')
for r in sorted(plain, key=lambda r:r[3])[:4]: print('  ', r)
print('min co2 overall:')
for r in sorted(rows, key=lambda r:r[4])[:6]: print('  ', r)
print('roles:', {k: sum(1 for e in CANDS if e['alternative']['role']==k) for k in set(e['alternative']['role'] for e in CANDS)})
