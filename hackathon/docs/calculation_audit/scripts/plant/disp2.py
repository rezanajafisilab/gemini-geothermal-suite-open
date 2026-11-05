import sys
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from dioscuri_plant.year import dispatch
caps2 = np.array([[300.0, 300.0], [300.0, 150.0]])
q2 = dispatch(np.array([400.0, 400.0]), np.ones((2,2), bool), caps2, [0,1], 50.0, 'equal')
print('equal caps, d1 halved on day 2, want 400 ->', q2.tolist(), 'sums', q2.sum(axis=0))
q3 = dispatch(np.array([400.0, 400.0]), np.ones((2,2), bool), caps2, [0,1], 50.0, 'base')
print('base ->', q3.tolist(), q3.sum(axis=0))
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
specs = (dp.Doublet(depth_m=3000.0, injectors=2), dp.Doublet(depth_m=3000.0, injectors=2))
p = dp.Plant(n_doublets=2, doublet_specs=specs, heat_pump_mw=1.0, boiler_mw=30.0, chiller_mw=10.0)
y0 = dp.simulate_year(p, demand, model, rules)
y1 = dp.simulate_year(replace(p, outages=(('injector 2', 0, 364),)), demand, model, rules)
y2 = dp.simulate_year(replace(p, outages=(('injector 1', 0, 364),)), demand, model, rules)
for t, y in (('none', y0), ('inj2 out', y1), ('inj1 out', y2)):
    f = np.array([d['flow_m3h'] for d in y.doublets])
    print(t, y.heat_split_gwh['geo'], y.heat_split_gwh['boiler'], 'flow day 27', f[:,27], 'brine', y.brine_m3)
H = np.array(demand.heat_mw)
for t, y in (('inj2 out', y1), ('inj1 out', y2)):
    f = np.array([d['flow_m3h'] for d in y.doublets]); tot = f.sum(axis=0)
    cw = H/40; want = cw/ (1030*3990/3600/1e6)
    mid = np.where((want > 310) & (want < 440) & (f > 0).all(axis=0))[0]
    print(t, 'days with 300<want<450 and both on:', len(mid), 'example', [(int(d), round(want[d]), f[:, d].tolist()) for d in mid[:3]])
