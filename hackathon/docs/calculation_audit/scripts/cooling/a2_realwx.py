"""Free cooling with real KNMI De Bilt weather vs the typical year (code's formula)."""
import sys, numpy as np
from pathlib import Path
from dioscuri_plant import Demand, weather
SP = Path('/tmp/dioscuri-audit/cooling')
D = Path('src/gemini_agent/data/challenge')
dem = Demand.from_csv(D/'GEMINI_Heating_Demand_Daily_2027.csv', D/'GEMINI_Cooling_Demand_Daily_2027.csv')
heat, cool = dem.arrays()

def psat(t):  # Pa, Magnus over water
    return 611.2*np.exp(17.62*t/(243.12+t))
def wetbulb(t, td, p):
    """Psychrometric wet bulb (C) from dry bulb, dew point, pressure Pa (bisection)."""
    e = psat(td); lo = np.minimum(td, t) - 1; hi = t.copy()
    for _ in range(50):
        tw = 0.5*(lo+hi)
        # psychrometer equation, ventilated: e = esat(tw) - A*P*(t - tw), A=6.62e-4 1/K
        f = psat(tw) - 6.62e-4*p*(t-tw) - e
        hi = np.where(f > 0, tw, hi); lo = np.where(f > 0, lo, tw)
    return 0.5*(lo+hi)

rows = []
for line in open(SP/'knmi_dl/x/uurgeg_260_2021-2030.txt'):
    if not line.startswith('  260,'): continue
    f = [s.strip() for s in line.split(',')]
    if f[7]=='' or f[9]=='' or f[14]=='': continue
    rows.append((int(f[1]), int(f[2]), float(f[7])/10, float(f[9])/10, float(f[14])*10))
a = np.array(rows)
wb_all = wetbulb(a[:,2], a[:,3], a[:,4])
span = 5.0
def free_share(wb):
    return np.clip((25 - (wb + 6.0))/span, 0, 1)
typ = weather.typical_year()['wet_bulb_c']
print('typical year: free GWh %.3f of %.3f; peak-day share %.2f' % ((free_share(typ)*cool).sum()*24/1000, cool.sum()*24/1000, free_share(typ)[199]))
for yr in (2021, 2022, 2023, 2024, 2025):
    m = (a[:,0]//10000 == yr)
    dates = a[m,0].astype(int); wb = wb_all[m]
    ud = np.unique(dates)
    # drop Feb 29
    ud = np.array([d for d in ud if not (d % 10000 == 229)])
    if len(ud) != 365: print(yr, 'days', len(ud)); continue
    wbd = np.array([wb[dates == d].mean() for d in ud])
    wbh = np.array([wb[dates == d] for d in ud], dtype=object)
    fd = (free_share(wbd)*cool).sum()*24/1000
    fh = sum((free_share(np.asarray(h)).mean())*c for h, c in zip(wbh, cool))*24/1000
    # demand-weighted: what if the cooling load follows the hours' warmth (load prop. to max(0,wb-? )) - skip
    print(f'{yr}: daily-mean wb free {fd:.3f} GWh ({fd/23.7425:.1%}); hourly wb, flat load {fh:.3f} GWh ({fh/23.7425:.1%}); '
          f'19 Jul daily wb {wbd[199]:.1f} C share {free_share(wbd)[199]:.2f}; max daily wb {wbd.max():.1f}; '
          f'Jun-Aug mean wb {wbd[151:243].mean():.1f} (typ {typ[151:243].mean():.1f})')
    np.save(SP/f'wbd_{yr}.npy', wbd)
