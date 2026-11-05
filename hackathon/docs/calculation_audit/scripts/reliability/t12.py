from common import *
import numpy as np
bad=0; n=0
for e in CANDS:
    a=e['alternative']
    if a['role'] not in ('chosen','candidate'): continue
    A = Alternative(**a); b = DesignBrief(**e['brief']); r = engine.rules_for(b)
    p = engine.plant_of(A)
    d = engine.demand_of(b)
    y = dp.simulate_year(p, d, engine.doublet_model(r), r)
    probs=[]
    if not (1 <= p.n_doublets <= 3): probs.append('n_doublets')
    for i,db in enumerate(y.doublets):
        on = np.array(db['on'], bool); fl = np.array(db['flow_m3h'])[on]
        if on.sum() > 330: probs.append(f'days {on.sum()}')
        if fl.size and (fl.min() < 50-1e-6 or fl.max() > 300+1e-6): probs.append(f'flow {fl.min()}-{fl.max()}')
        tw = np.array([x for x in db['wellhead_c'] if x is not None]); ri = np.array([x for x in db['reinjection_c'] if x is not None])
        if tw.size and (tw-ri).max() > 40+1e-6: probs.append(f'dT {(tw-ri).max():.2f}')
    if max(y.daily_mw['heat']['short'])>1e-6 or max(y.daily_mw['cool']['short'])>1e-6: probs.append('short')
    if r.supply_c if hasattr(r,'supply_c') else False: pass
    n+=1
    if probs or y.violations:
        bad+=1; print(a['uid'], a['code'], probs, y.violations[:2])
print('checked', n, 'bad', bad, 'heat supply', RULES.heat_supply_c, 'cool supply', RULES.cool_supply_c)
