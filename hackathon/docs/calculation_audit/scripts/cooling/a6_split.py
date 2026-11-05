import numpy as np
from pathlib import Path
from dioscuri_plant import Demand, weather
from dioscuri_plant.weather import _daily, MONTH_DAYS
SP = Path('/tmp/dioscuri-audit/cooling')
D = Path('src/gemini_agent/data/challenge')
dem = Demand.from_csv(D/'GEMINI_Heating_Demand_Daily_2027.csv', D/'GEMINI_Cooling_Demand_Daily_2027.csv')
_, cool = dem.arrays()
f = lambda wb: (np.clip((25-(wb+6))/5, 0, 1)*cool).sum()*24/1000
M = np.repeat(np.arange(12), MONTH_DAYS)
allyrs = np.mean([np.load(SP/f'wbd_{y}.npy') for y in range(2021, 2026)], axis=0)
for yr in range(2021, 2026):
    wbd = np.load(SP/f'wbd_{yr}.npy')
    sm = _daily(np.bincount(M, weights=wbd)/np.array(MONTH_DAYS))   # same smoothing as the code
    print(yr, 'actual daily %.2f GWh, same year smoothed monthly %.2f GWh' % (f(wbd), f(sm)))
print('typical (code) %.2f' % f(weather.typical_year()['wet_bulb_c']))
# peak day: 10 MW on 19 Jul; typical wb
typ = weather.typical_year()['wet_bulb_c']
print('wb on 19 Jul typical %.2f; real 2021-25: %s' % (typ[199], [round(float(np.load(SP/f"wbd_{y}.npy")[199]),1) for y in range(2021,2026)]))
# Stull vs psychrometric for July normal
from dioscuri_plant.weather import wet_bulb
print('Stull July normal', wet_bulb(np.array(18.3), np.array(76.5)))
