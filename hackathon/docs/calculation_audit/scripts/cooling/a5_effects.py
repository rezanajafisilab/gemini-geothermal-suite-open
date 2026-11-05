import numpy as np
from pathlib import Path
from dataclasses import replace
import dioscuri_plant.weather as W
from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet, economics, Prices, Components
SP = Path('/tmp/dioscuri-audit/cooling')
D = Path('src/gemini_agent/data/challenge')
dem = Demand.from_csv(D/'GEMINI_Heating_Demand_Daily_2027.csv', D/'GEMINI_Cooling_Demand_Daily_2027.csv')
pick = Plant(1, depth_m=3000, heat_pump_mw=0.5, boiler_mw=30, chiller_mw=15, chiller_units=3, boiler_units=3, reliable=True)
ref = Plant(0, boiler_mw=31, chiller_mw=10.5)
r = Rules(free_cooling=1.0)
yref = simulate_year(ref, dem, stub_doublet, Rules()); eref = economics(ref, yref, Prices())
def show(label, y, e):
    cold = dict((i, m) for i, k, m in e.lines_cold) if False else None
    print(f'{label}: free {y.cool_split_gwh["free"]:.3f} chill {y.cool_split_gwh["chill"]:.3f} GWh; el chill {y.electricity_gwh["chillers"]:.3f} towers {y.electricity_gwh["towers"]:.3f}; '
          f'CO2 el {y.co2_t["electricity"]:.0f} total {y.co2_t["total"]:.0f} t; LCOC {e.lcoc_eur_per_mwh} LCOH {e.lcoh_eur_per_mwh} LCOE {e.lcoe_eur_per_mwh}; capex {e.capex_meur}')
y0 = simulate_year(pick, dem, stub_doublet, r); e0 = economics(pick, y0, Prices(), reference=(yref, eref), rules=r)
show('typical year (as coded)', y0, e0)
print('  cold lines', [(i, k, round(m, 4)) for i, k, m in e0.lines_cold])
cold_cost0 = sum(m for _, _, m in e0.lines_cold)
orig = W.typical_year
for yr in (2021, 2022, 2023, 2024, 2025):
    wbd = np.load(SP/f'wbd_{yr}.npy')
    def patched(wbd=wbd):
        d = orig(); d['wet_bulb_c'] = wbd; return d
    W.typical_year = patched
    y = simulate_year(pick, dem, stub_doublet, r); e = economics(pick, y, Prices(), reference=(yref, eref), rules=r)
    show(f'KNMI {yr} daily wb', y, e)
W.typical_year = orig
# Tower pumps: condenser-water pumps ~1.3 % of rejection on top of fans 1.25 %
c2 = replace(Components(), tower_mw_el_per_mw=0.0125 + 0.013)
y2 = simulate_year(pick, dem, stub_doublet, r, c2); e2 = economics(pick, y2, Prices(), reference=(yref, eref), rules=r)
show('with CW pumps (+1.3 %)', y2, e2)
# water: rejection incl free
rej = sum(np.array(v) for v in y0.daily_mw['reject'].values()).sum()*24/1000
mk = rej*1e9*3600*0.8/(1000*2.45e6)*1.25
cold_mwh = y0.cool_delivered_gwh*1000
for price in (1.0, 2.0, 3.0):
    print(f'water at {price} EUR/m3 all-in: makeup {mk:.0f} m3 -> {mk*price/1e3:.1f} kEUR/yr -> LCOC +{mk*price/cold_mwh:.2f} EUR/MWh ({mk*price/1e6/cold_cost0:.1%} of cold cost {cold_cost0:.3f} MEUR)')
