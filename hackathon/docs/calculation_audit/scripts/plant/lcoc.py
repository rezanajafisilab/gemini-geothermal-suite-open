import sys
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
from dioscuri_plant.components import Components
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules); prices = engine.prices_for({}, brief)
ref = dp.simulate_year(dp.Plant(n_doublets=0, boiler_mw=30.0, chiller_mw=10.0), demand, model, rules)
refe = dp.economics(dp.Plant(n_doublets=0, boiler_mw=30.0, chiller_mw=10.0), ref, prices, rules=rules)
lead = dp.Plant(n_doublets=1, depth_m=3000.0, heat_pump_mw=0.5, boiler_mw=30.0, chiller_mw=15.0, boiler_units=3, chiller_units=3, reliable=True)
r = replace(rules, free_cooling=1.0)
for ap in (6.0, 6.6, 7.0):
    y = dp.simulate_year(lead, demand, model, r, replace(Components(), free_cooling_approach_k=ap))
    e = dp.economics(lead, y, prices, reference=(ref, refe), rules=r)
    print(f'approach {ap}: free {y.cool_split_gwh["free"]} GWh, LCOH {e.lcoh_eur_per_mwh} LCOC {e.lcoc_eur_per_mwh} LCOE {e.lcoe_eur_per_mwh} CO2 {e.co2_t_per_year} saving {e.co2_saving_vs_gas}')
print('ref co2', ref.co2_t['total'])
