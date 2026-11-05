from common import *
from dioscuri_plant import montecarlo as mc
xs=[e for e in CANDS if e['alternative']['gas']=='produced' and e['alternative']['role'] in ('chosen','candidate')]
print('produced-gas valid entries', len(xs))
xs.sort(key=lambda e: (not e['alternative']['reliable'], e['economics']['lcoe_eur_per_mwh']))
for e in xs[:3]:
    a=e['alternative']; print(a['uid'], a['code'], a['reliable'], a['sizes_mw'], a['boiler_units'], a['electric_boiler_units'])
e = xs[0]; A = Alternative(**e['alternative']); b = DesignBrief(**e['brief']); r = engine.rules_for(b)
p = engine.plant_of(A)
out = mc.risk_sizing(p, DEMAND, MODEL, r)
print('risk sizing unit', out['unit'], 'n1', out['n1_mw'], 'risk', out['risk_mw'], 'tried', out['tried'])
