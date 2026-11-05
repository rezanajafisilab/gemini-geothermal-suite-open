import time
from common import *
print('fingerprint now', lead.fingerprint(), 'cache', D['fingerprint'])
h, c = DEMAND.arrays()
print('peak heat', h.max(), 'day', h.argmax(), 'peak cool', c.max(), 'days', len(h), 'sum heat GWh', h.sum()*24/1000, 'cool GWh', c.sum()*24/1000)
print('rules op days', RULES.operating_days, 'flow', RULES.flow_min_m3h, RULES.flow_max_m3h, 'dT', RULES.max_brine_cooling_k, RULES.reservoir_depth_m)
p = plant('A1')
print(p)
t=time.perf_counter(); y = dp.simulate_year(p, DEMAND, MODEL, RULES); print('sim s', time.perf_counter()-t)
t=time.perf_counter(); y = dp.simulate_year(p, DEMAND, MODEL, RULES); print('sim s', time.perf_counter()-t)
print(y.violations, y.peak_shortfall_mw)
