import time
from common import *
from dataclasses import replace
from dioscuri_plant import montecarlo as mc, failure_costs as fc
import numpy as np

def lole_nospare(plant, demand, model, rules, years=1000, seed=11):
    state = {"plant": plant, "demand": demand, "doublet": model, "rules": rules, "components": dp.Components()}
    bd, bm = mc._days_short(state, ())
    drawn = mc.draw_years(plant, years, seed, False)
    days=[]; mwh=[]
    cache={}
    for ev,_,_ in drawn:
        if not ev: days.append(bd); mwh.append(bm); continue
        if ev not in cache: cache[ev]=mc._days_short(state, ev)
        d,m = cache[ev]; days.append(d); mwh.append(m)
    return float(np.mean(days)), float(np.mean(mwh))

for uid in ('A1','A33'):
    a, e = alt(uid)
    b = DesignBrief(**e['brief']); r = engine.rules_for(b)
    p = engine.plant_of(a)
    t=time.perf_counter()
    out = mc.risk_sizing(p, DEMAND, MODEL, r)
    print(uid, a.code, 'n1', out['n1_mw'], 'risk', out['risk_mw'], 'at_n1', out['at_n1'], 'at_risk', out['at_risk'], 'tried', out['tried'], round(time.perf_counter()-t,1),'s')
    q = replace(p, **{out['unit']: out['risk_mw']})
    print('   at risk size, NO spare ESP: lole days, eens MWh =', lole_nospare(q, DEMAND, MODEL, r))
    print('   at N-1 size, NO spare ESP:', lole_nospare(p, DEMAND, MODEL, r))
    per_mw = PRICES.boiler_meur_per_mw if out['unit']=='boiler_mw' else PRICES.electric_boiler_meur_per_mw
    print('   capex saved M€', (out['n1_mw']-out['risk_mw'])*per_mw, 'per_mw', per_mw)
