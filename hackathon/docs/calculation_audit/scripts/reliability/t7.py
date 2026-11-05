from common import *
from dioscuri_plant import montecarlo as mc
rel = sorted([e for e in CANDS if e['alternative']['reliable'] and e['alternative']['role'] in ('chosen','candidate')], key=lambda e: e['economics']['lcoe_eur_per_mwh'])
res=[]
for e in rel[:12]:
    a = Alternative(**e['alternative']); b = DesignBrief(**e['brief']); r = engine.rules_for(b)
    p = engine.plant_of(a)
    u = mc.unplanned(p, DEMAND, MODEL, r, PRICES, years=1000, spare_esp=False)
    res.append((a.uid, a.code, a.picks, round(e['economics']['lcoe_eur_per_mwh'],2), round(u['heat_mwh']['mean'],3), round(u['cold_mwh']['mean'],3), u['heat_mwh']['share_above_zero']))
for x in res: print(x)
