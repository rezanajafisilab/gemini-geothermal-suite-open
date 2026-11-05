from common import *
from dioscuri_plant import montecarlo as mc
orig = mc.draw_years
mc.draw_years = lambda plant, years=1000, seed=11, spare_esp=True: orig(plant, years, seed, False)
for uid in ('A1','A33'):
    a, e = alt(uid); b = DesignBrief(**e['brief']); r = engine.rules_for(b)
    p = engine.plant_of(a)
    out = mc.risk_sizing(p, DEMAND, MODEL, r, steps=8)
    print(uid, 'NO spare: n1', out['n1_mw'], 'risk', out['risk_mw'], 'at_risk', out['at_risk'], 'tried', out['tried'])
