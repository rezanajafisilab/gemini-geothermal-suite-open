import sys
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
H, C = demand.arrays()
r50 = replace(rules, heat_return_c=50.0)
model = engine.doublet_model(r50)
p = dp.Plant(n_doublets=1, depth_m=3500.0, boiler_mw=30.0, chiller_mw=10.0)
y = dp.simulate_year(p, demand, model, r50)
geo = np.array(y.daily_mw['heat']['geo']); on = np.array(y.doublets[0]['on']); f = np.array(y.doublets[0]['flow_m3h'])
twh = np.array([w if w is not None else np.nan for w in y.doublets[0]['wellhead_c']])
ucb = 1030*3990/3600/1e6
# hand: brine may give at most q*ucb*40; network needs H; HX heats network fully to 100 (twh-5 > 100)
hand = np.where(on, np.minimum(H, f*ucb*40), 0)
print('3500 m, return 50: geo GWh', y.heat_split_gwh['geo'], 'hand', round(hand.sum()*24/1000, 3), 'maxcool', y.max_brine_cooling_k, 'viol', y.violations)
print('  max |diff| MW', np.nanmax(np.abs(geo - hand)))
ref = dp.simulate_year(dp.Plant(n_doublets=0, boiler_mw=30.0, chiller_mw=10.0), demand, model, rules)
print('gas ref: boiler', ref.heat_split_gwh['boiler'], 'gas', ref.purchased_gas_gwh, 'hand', round(H.sum()*24/1000/0.95, 3), 'co2', ref.co2_t,
      'hand co2 gas', round(H.sum()*24/0.95*0.202, 1), 'hand el', round((C.sum()*24/1000)*(1/8.5632 + 0.0125*(1+1/8.5632)), 3), ref.electricity_gwh)
