from common import *
from dataclasses import replace
from dioscuri_plant import firm
for uid in ('A1','A2','A33','A39'):
    a, e = alt(uid)
    print(uid, a.code, 'parent', a.parent, 'effect', a.effect[:300])
    print('  rounds last change:', a.rounds[-1].get('change') if a.rounds else None)
    b = DesignBrief(**e['brief'])
    print('  brief rules', b.rules)
# A1 checks
p = plant('A1')
outs = firm.outages(p, DEMAND, MODEL, RULES)
for o in outs: print(o['unit'], o['heat'], o['cool'])
print(firm.peak_margin(p, DEMAND, MODEL, RULES))
# minimality: shrink boiler 0.1, chillers 0.1
for k in ('boiler_mw','chiller_mw'):
    q = replace(p, **{k: getattr(p,k)-0.1})
    oo = firm.outages(q, DEMAND, MODEL, RULES)
    print('shrink', k, [ (o['unit'], o['heat']['worst_mw'], o['cool']['worst_mw']) for o in oo if o['heat']['days_short'] or o['cool']['days_short']])
y = dp.simulate_year(p, DEMAND, MODEL, RULES)
i=27
for side in ('heat',):
    print({k: float(v[i]) for k,v in y.daily_mw[side].items()})
