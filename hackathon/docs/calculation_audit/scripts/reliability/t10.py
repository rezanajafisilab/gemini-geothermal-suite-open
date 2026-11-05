from common import *
from dioscuri_plant import firm
a, e = alt('A1'); b = DesignBrief(**e['brief']); r = engine.rules_for(b)
p = engine.plant_of(a)
events = [("doublet 1", 20, 34), ("boiler unit", 20, 34)]
failed = firm.failure(p, DEMAND, MODEL, events, r)
print('failed peak short', failed.peak_shortfall_mw)
for rem in firm.remedies(p, DEMAND, MODEL, events, failed, r):
    print(rem['key'], rem['name'], rem.get('added_mw'), '-> still short MW', rem['year'].peak_shortfall_mw)
# hand: with doublet out and one of 3 units out, capacity = 2/3*B (HP has no source). demand max in window:
h,_ = DEMAND.arrays(); g = h[20:35].max() - 2/3*p.boiler_mw
print('hand gap', g, 'boiler needed B >=', 1.5*h[20:35].max(), '-> add', 1.5*h[20:35].max()-p.boiler_mw)
