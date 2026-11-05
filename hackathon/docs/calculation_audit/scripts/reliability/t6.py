from common import *
from dataclasses import replace
from dioscuri_plant import failure_costs as fc
from dioscuri_plant.economics import crf
for uid, attr, risk in (('A1','boiler_mw',26.72), ('A33','electric_boiler_mw',15.94)):
    a, e = alt(uid)
    b = DesignBrief(**e['brief']); r = engine.rules_for(b)
    p = engine.plant_of(a)
    q = replace(p, **{attr: risk})
    ref = engine.reference(b)
    out=[]
    for x in (p,q):
        y = dp.simulate_year(x, DEMAND, MODEL, r)
        ec = dp.economics(x, y, PRICES, rules=r)
        out.append((ec.capex_meur, ec.lcoe_eur_per_mwh, fc.grid_meur(y, PRICES), {n: round(m,4) for n,k,m in ec.lines if 'oiler' in n or 'rid' in n}))
    print(uid, 'N1', out[0]); print(uid, 'risk', out[1])
    print('  capex diff', out[0][0]-out[1][0], 'grid diff M€/yr', out[0][2]-out[1][2])
    mwh=(y.heat_delivered_gwh+y.cool_delivered_gwh)*1000
    print('  lcoe diff', out[0][1]-out[1][1], '=> M€/yr', (out[0][1]-out[1][1])*mwh/1e6)
print('crf', crf(PRICES.discount_rate, 25), crf(PRICES.discount_rate, 30))
