import sys
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
from dioscuri_plant.year import stop_windows, stop_ranges
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
lead = dp.Plant(n_doublets=1, depth_m=3000.0, heat_pump_mw=0.5, boiler_mw=30.0, chiller_mw=15.0, boiler_units=3, chiller_units=3)
# storage cycle closure
for kind, size in ((0.0, 2000.0), (1.0, 20000.0)):
    y = dp.simulate_year(lead, demand, model, replace(rules, storage_mwh=size, storage_ates=kind))
    lv = y.daily_mw['storage']['level_mwh']
    print('storage', kind, 'start-of-year level (prev end) vs end', lv[0], lv[-1], 'take', sum(y.daily_mw['storage']['take'])*24/1000, 'give', sum(y.daily_mw['storage']['give'])*24/1000)
    print('   peak_heat_mw', y.peak_heat_mw, 'demand max day', max(y.daily_mw['heat']['demand']))
# stop window misalignment edge case
need = np.ones(365)
print('stop_windows op=365 lengths (0,40):', stop_windows(need, 2, 365, None, (0, 40)))
print('stop_ranges  op=365 lengths (0,40):', stop_ranges(need, 2, 365, None, (), (0, 40)))
print('stop_windows op=330 lengths (100,250,100):', stop_windows(need, 3, 330, None, (100, 250, 100)))
p2 = dp.Plant(n_doublets=2, depth_m=3000.0, boiler_mw=30.0, chiller_mw=10.0)
y = dp.simulate_year(p2, demand, model, replace(rules, operating_days=365, stop_days_off=(0, 40)))
print('2D op365 lengths(0,40): stop_ranges', y.stop_ranges, [s['days_on'] for s in y.doublet_summary], y.violations)
# multi-doublet different depths
p3 = dp.Plant(n_doublets=2, doublet_specs=(dp.Doublet(depth_m=2500.0), dp.Doublet(depth_m=3500.0)), heat_pump_mw=3.0, boiler_mw=30.0, chiller_mw=10.0)
for disp in ('equal', 'base'):
    y = dp.simulate_year(replace(p3, dispatch=disp), demand, model, rules)
    print(disp, y.heat_split_gwh, 'maxcool', y.max_brine_cooling_k, [s['max_cooling_k'] for s in y.doublet_summary], [s['wellhead_full_c'] for s in y.doublet_summary], y.violations, y.balance_error)
