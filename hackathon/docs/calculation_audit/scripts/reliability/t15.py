from common import *
from dioscuri_plant import firm
a, e = alt('A107'); b = DesignBrief(**e['brief']); r = engine.rules_for(b)
p = engine.plant_of(a)
print(a.code, p.electric_boiler_mw, p.electric_boiler_units, p.boiler_mw, p.gas)
events = [("electric boiler", 20, 34)]
failed = firm.failure(p, DEMAND, MODEL, events, r)
print('failed short', failed.peak_shortfall_mw)
for rem in firm.remedies(p, DEMAND, MODEL, events, failed, r):
    print(rem['key'], rem['name'], '-> still short', rem['year'].peak_shortfall_mw)
