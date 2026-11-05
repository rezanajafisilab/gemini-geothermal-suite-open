from common import *
from dioscuri_plant import firm
bad=0; n=0
for e in CANDS:
    a=e['alternative']
    if not a['reliable'] or a['role'] not in ('chosen','candidate'): continue
    A = Alternative(**a); b = DesignBrief(**e['brief']); r = engine.rules_for(b)
    p = engine.plant_of(A)
    outs = firm.outages(p, engine.demand_of(b), engine.doublet_model(r), r)
    short=[(o['unit'], o['heat']['worst_mw'], o['cool']['worst_mw']) for o in outs if o['heat']['days_short'] or o['cool']['days_short']]
    y = dp.simulate_year(p, engine.demand_of(b), engine.doublet_model(r), r)
    n+=1
    if short or y.violations:
        bad+=1; print(a['uid'], a['code'], b.rules, short, y.violations[:2])
print('checked', n, 'bad', bad)
