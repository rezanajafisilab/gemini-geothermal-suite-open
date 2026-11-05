from common import *
pr = PRICES; extra = max(0.0, pr.carbon_long_term_eur_per_t - pr.carbon_eur_per_t)
def sh(e):
    y=e['year']; ec=e['economics']; mwh=(y['heat_delivered_gwh']+y['cool_delivered_gwh'])*1000
    return ec['lcoe_eur_per_mwh'] + extra*ec['co2_t_per_year']/mwh
valid=[e for e in CANDS if e['alternative']['role'] in ('chosen','candidate')]
plans={}
for e in valid:
    a=e['alternative']
    if a['reliable']: plans.setdefault(a['parent'], []).append(e)
plain=sorted([e for e in valid if not e['alternative']['reliable']], key=sh)
for e in plain[:15]:
    a=e['alternative']
    code=a['code']
    has = [p['alternative']['code'] for p in valid if p['alternative']['reliable'] and p['alternative']['parent']==code.split('-FC')[0].split('-PV')[0]]
    print(a['uid'], code, 'parent', a['parent'], 'lcoe', round(e['economics']['lcoe_eur_per_mwh'],2), 'shadow', round(sh(e),2), 'flared', round(e['year']['produced_gas_flared_gwh'],2), 'stage', a['stage'], 'plans for this code:', has[:3])
