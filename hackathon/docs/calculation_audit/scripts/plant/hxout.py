import sys
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
from dioscuri_plant.components import heat_pump_on_source
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
for hp in (0.5, 5.0):
    p = dp.Plant(n_doublets=1, depth_m=3000.0, heat_pump_mw=hp, boiler_mw=30.0, chiller_mw=15.0, boiler_units=3, chiller_units=3,
                 outages=(('heat exchanger', 0, 364),))
    y = dp.simulate_year(p, demand, model, rules)
    print(f'HP {hp} MW, HX out all year: hp GWh {y.heat_split_gwh["hp"]}, hp el GWh {y.electricity_gwh["hp"]}, year COP {y.heat_pump_cop}')
# direct: 0.5 MW from brine at 100.71 C, 300 m3/h, sink 100 C
cb = 300*1030*3990/3600/1e6
print(heat_pump_on_source(np.array([0.5]), np.array([100.71]), np.array([cb]), 100.0, 60.71, 0.5))
print(heat_pump_on_source(np.array([0.3]), np.array([105.0]), np.array([cb]), 100.0, 65.0, 0.5))
