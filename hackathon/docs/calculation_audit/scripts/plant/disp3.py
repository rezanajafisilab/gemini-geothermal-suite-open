import sys
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
H = np.array(demand.heat_mw)
specs = (dp.Doublet(depth_m=3000.0, injectors=2), dp.Doublet(depth_m=3000.0, injectors=2))
p = dp.Plant(n_doublets=2, doublet_specs=specs, heat_pump_mw=1.0, boiler_mw=30.0, chiller_mw=10.0)
for unit in ('injector 1', 'injector 2'):
    y = dp.simulate_year(replace(p, outages=((unit, 40, 80),)), demand, model, rules)
    f = np.array([d['flow_m3h'] for d in y.doublets])
    w = slice(40, 81)
    want = H/40/(1030*3990/3600/1e6)
    print(unit, 'out days 40-80: geo', y.heat_split_gwh['geo'], 'boiler', y.heat_split_gwh['boiler'],
          'brine in window', round(f[:, w].sum()*24), 'example day 50 want', round(want[50]), 'flows', f[:, 50].tolist())
