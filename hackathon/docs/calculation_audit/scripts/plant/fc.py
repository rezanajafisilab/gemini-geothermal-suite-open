import sys
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
from dioscuri_plant import weather
from dioscuri_plant.year import MONTH
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
H, C = demand.arrays()
wx = weather.typical_year()
wb = wx['wet_bulb_c']
print('monthly mean wb', np.round(np.bincount(MONTH, wb)/np.bincount(MONTH), 2))
print('monthly cold GWh', np.round(np.bincount(MONTH, C)*24/1000, 2))
share = np.clip((25 - (wb + 6))/5, 0, 1)
print('monthly FC share (cold-weighted)', np.round(np.bincount(MONTH, share*C)/np.maximum(np.bincount(MONTH, C), 1e-9), 2))
print('wb on 19 Jul (day 199)', wb[199], 'share', share[199])
# diurnal test: hourly wb = daily + A*sin, load = daily*(1 + B*sin) in phase
for A, B in ((1.5, 0.3), (2.0, 0.5), (3.0, 0.5)):
    h = np.arange(24); s = np.sin(2*np.pi*(h-9)/24)  # peak 15:00
    fc_h = 0.0
    for d in range(365):
        wbh = wb[d] + A*s; lh = C[d]*(1 + B*s)
        fc_h += np.sum(np.clip((25-(wbh+6))/5, 0, 1)*lh)/24
    print(f'diurnal wb +-{A} K, load +-{B*100:.0f}%: free GWh {fc_h*24/1000:.2f} vs daily-mean {np.sum(share*C)*24/1000:.2f}')
lead = dp.Plant(n_doublets=1, depth_m=3000.0, heat_pump_mw=0.5, boiler_mw=30.0, chiller_mw=15.0, boiler_units=3, chiller_units=3)
from dioscuri_plant.components import Components
for ap in (6.0, 8.0, 10.0):
    y = dp.simulate_year(lead, demand, model, replace(rules, free_cooling=1.0), replace(Components(), free_cooling_approach_k=ap))
    print('approach', ap, 'free', y.cool_split_gwh['free'], 'el total', round(sum(y.electricity_gwh.values()),3), 'co2', y.co2_t['total'])
y0 = dp.simulate_year(lead, demand, model, rules)
print('no FC: el', round(sum(y0.electricity_gwh.values()),3), 'co2', y0.co2_t['total'])
# outage overlap: two boiler units out on the same day
p = replace(lead, outages=(('boiler unit', 0, 364), ('boiler unit', 20, 26)))
y = dp.simulate_year(p, demand, model, rules)
print('2 of 3 boiler units out days 20-26: boiler MW day 25', y.daily_mw['heat']['boiler'][25], 'demand', H[25], 'short', y.daily_mw['heat']['short'][25])
# solar hourly check: plant load flat over 24h, PV with sine over daylight
for mwp in (1.0, 3.0, 6.0):
    yS = dp.simulate_year(lead, demand, model, replace(rules, free_cooling=1.0, solar_mwp=mwp))
    el = sum(np.array(v) for v in yS.daily_mw['power'].values())
    out = mwp*855*(wx['global_kwh_m2']/wx['global_kwh_m2'].sum())  # MWh per day
    used_h = 0.0
    for d in range(365):
        L = wx['daylight_h'][d]; t = np.linspace(0, L, 200); prof = np.sin(np.pi*t/L); prof = prof/np.trapz(prof, t)*out[d]
        used_h += np.trapz(np.minimum(prof, el[d]), t)
    print(f'solar {mwp} MWp: code used {yS.solar["used_gwh"]} GWh, hourly-shape used {used_h/1000:.3f} GWh, gen {yS.solar["generated_gwh"]}')
