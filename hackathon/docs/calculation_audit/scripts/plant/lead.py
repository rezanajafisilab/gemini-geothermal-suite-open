import json, sys, time
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
d = json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/hackathon/evals/runs/lead/challenge.json'))
des = d['summary']['design']
brief = DesignBrief()
rules = engine.rules_for(brief)
print(rules)
demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
plant = dp.Plant(n_doublets=1, depth_m=3000.0, heat_pump_mw=0.5, boiler_mw=30.0, chiller_mw=15.0, boiler_units=3, chiller_units=3, reliable=True)
r = replace(rules, free_cooling=1.0)
t=time.time()
y = dp.simulate_year(plant, demand, model, r)
print('t', time.time()-t)
print(y.heat_split_gwh, y.cool_split_gwh)
print(y.electricity_gwh, y.purchased_gas_gwh, y.produced_gas_burned_gwh, y.produced_gas_flared_gwh)
print(y.co2_t)
print(y.violations, y.stop_ranges, y.wellhead_c, y.heat_pump_cop)
print('cached', des['year']['heat_split_gwh'], des['year']['cool_split_gwh'], des['year']['co2_t'])
