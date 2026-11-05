"""Run the pick-like design with/without free cooling; hand-check cooling numbers."""
import numpy as np
from pathlib import Path
from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet, Components
from dioscuri_plant import weather
from dioscuri_plant.components import chiller_cop
D = Path('src/gemini_agent/data/challenge')
dem = Demand.from_csv(D/'GEMINI_Heating_Demand_Daily_2027.csv', D/'GEMINI_Cooling_Demand_Daily_2027.csv')
heat, cool = dem.arrays()
print('cool GWh', cool.sum()*24/1000, 'peak', cool.max(), 'day', cool.argmax(), 'days>0', (cool>0).sum(), 'both', ((cool>0)&(heat>0)).sum())
wx = weather.typical_year(); wb = wx['wet_bulb_c']; db = wx['dry_bulb_c']
print('typical wb max', wb.max(), 'db max', db.max(), 'wb on 19 Jul (idx 199)', wb[199], 'db', db[199])
# monthly cooling
MD=(31,28,31,30,31,30,31,31,30,31,30,31); M=np.repeat(np.arange(12),MD)
print('cool GWh by month', np.round(np.bincount(M,weights=cool)*24/1000,2))
# hand cop
c = Components()
cop_hand = 0.5*(18+273.15)/(35-18)
print('chiller COP hand', cop_hand, 'code', chiller_cop(20,35,0.5,2))
# hand free cooling
water = wb + 6.0
share = np.clip((25-water)/5, 0, 1)
print('free share on cooling days: mean weighted', (share*cool).sum()/cool.sum())
for fc in (0.0, 1.0):
    p = Plant(1, depth_m=3000, heat_pump_mw=0.5, boiler_mw=30, chiller_mw=15, chiller_units=3, boiler_units=3)
    y = simulate_year(p, dem, stub_doublet, Rules(free_cooling=fc))
    cs = y.cool_split_gwh; el = y.electricity_gwh
    print(f'\nFC={fc}', cs, 'chiller el', el['chillers'], 'towers', el['towers'], 'cop', y.chiller_cop, 'viol', y.violations[:3])
    dm = y.daily_mw
    chill = np.array(dm['cool']['chill']); free = np.array(dm['cool']['free'])
    rej = np.array(dm['reject']['chillers']) + np.array(dm['reject']['free'])
    print('  hand chill el', (chill/cop_hand).sum()*24/1000, ' hand towers', 0.0125*(chill*(1+1/cop_hand)+free).sum()*24/1000)
    print('  free on 19 Jul', free[199], 'chill', chill[199], 'co2 el t', y.co2_t['electricity'])
    print('  free_cooling_mw', y.free_cooling_mw)
