from common import *
import time
from dioscuri_plant import failure_costs as fc, montecarlo as mc
d, s = lead_session()
e = next(x for x in s.candidates if x.alternative.uid=='A33')
plant, year, rules, prices, demand, model = rebuild(e)
out = fc.failure_costs(plant, demand, model, rules, prices=prices, base=year)
print('A33 analytic: no spare total', out['total_keur'], 'grid', out['grid_keur'], '| with spare total', out['with_spare']['total_keur'], 'grid', out['with_spare']['grid_keur'], '| grid info', out['grid'])
for u in out['units']: print('  ', {k:u[k] for k in ('label','failures_per_year','out_days','running_keur','grid_keur','grid_break_share','lost_keur','repair_keur','total_keur')})
for spare in (False, True):
    r = mc.unplanned(plant, demand, model, rules, prices, years=1000, spare_esp=spare)
    print('MC spare', spare, 'total mean', round(r['total_keur']['mean'],1), 'extra', round(r['extra_keur']['mean'],1), 'repair', round(r['repair_keur']['mean'],1), 'lost', round(r['lost_keur'],1), 'p90 total', round(r['total_keur']['p90'],1))
