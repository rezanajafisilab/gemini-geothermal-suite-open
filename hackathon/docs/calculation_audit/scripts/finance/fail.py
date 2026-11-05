from common import *
import time, json
from dioscuri_plant import failure_costs as fc, montecarlo as mc
d, s = lead_session()
c = s.chosen
plant, year, rules, prices, demand, model = rebuild(c)
t=time.time()
out = fc.failure_costs(plant, demand, model, rules, prices=prices, base=year)
print('analytic total (no spare)', out['total_keur'], 'with spare', out['with_spare']['total_keur'], 'range', out['range_keur'], 'lost MWh', out['lost_mwh'], out['with_spare']['lost_mwh'], time.time()-t)
for u in out['units']: print('  ', {k:u[k] for k in ('label','failures_per_year','out_days','running_keur','grid_keur','lost_mwh','lost_keur','repair_keur','total_keur')})
print('spare', {k:v for k,v in out['spare_esp'].items()})
print('notes', out['notes'])
for spare in (True, False):
    t=time.time()
    r = mc.unplanned(plant, demand, model, rules, prices, years=1000, spare_esp=spare)
    print('MC spare', spare, 'secs', round(time.time()-t,1))
    for k in ('extra_keur','repair_keur','total_keur','heat_mwh'):
        print('   ', k, {kk: round(v,2) for kk,v in r[k].items()})
    print('    lost_keur', r['lost_keur'], 'failures', r['failures'], 'worst', r['worst'])
