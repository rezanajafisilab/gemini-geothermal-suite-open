import numpy as np
from types import SimpleNamespace as NS
from pathlib import Path
from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet
from gemini_agent import cooling_check
D = Path('src/gemini_agent/data/challenge')
dem = Demand.from_csv(D/'GEMINI_Heating_Demand_Daily_2027.csv', D/'GEMINI_Cooling_Demand_Daily_2027.csv')
def run(p, rules, label):
    y = simulate_year(p, dem, stub_doublet, rules)
    entry = NS(alternative=NS(sizes_mw={'chillers': p.chiller_mw, 'absorption': p.absorption_mw}), year=y, brief=None)
    r = cooling_check.check(entry)
    print('\n==', label, '| year cool split', y.cool_split_gwh, '| el', {k: y.electricity_gwh[k] for k in ('chillers','towers')})
    for k in ('cold_gwh','unmet_gwh','compressor_gwh','towers_gwh','electricity_gwh','makeup_water_m3','evaporation_m3','blowdown_m3','ours','absorption','limits'):
        print('  ', k, r[k])
    # hand: water from all tower rejection in the year model incl. free cooling
    rej = sum(np.array(v) for v in y.daily_mw['reject'].values())
    gwh = rej.sum()*24/1000
    evap = gwh*1e9*3600*0.8/(1000*2.45e6)/3600  # m3: GWh->Wh *3600 J/Wh ... careful
    evap = gwh*1e9*3600*0.8/(1000*2.45e6)
    print('   year-model rejection incl free GWh %.3f -> evap %.0f m3, makeup %.0f m3 (5 cycles)' % (gwh, evap, evap*1.25))
    for w in cooling_check.words(r): print('   >', w)
pick = Plant(1, depth_m=3000, heat_pump_mw=0.5, boiler_mw=30, chiller_mw=15, chiller_units=3, boiler_units=3)
run(pick, Rules(free_cooling=1.0), 'pick-like EC N-1 with FC')
run(pick, Rules(), 'pick-like EC N-1 no FC')
ab = Plant(1, depth_m=2500, heat_pump_mw=2, boiler_mw=30, absorption_mw=6, chiller_mw=10)
run(ab, Rules(), 'absorption 6 + chillers 10 @2500')
ab18 = Plant(1, depth_m=1800, heat_pump_mw=2, boiler_mw=30, absorption_mw=6, chiller_mw=10)
run(ab18, Rules(), 'absorption 6 + chillers 10 @1800')
