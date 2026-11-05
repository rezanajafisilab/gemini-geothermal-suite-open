import numpy as np
from pathlib import Path
from dioscuri_plant import Demand, Plant, Rules, simulate_year, stub_doublet, Components, economics, Prices
D = Path('src/gemini_agent/data/challenge')
dem = Demand.from_csv(D/'GEMINI_Heating_Demand_Daily_2027.csv', D/'GEMINI_Cooling_Demand_Daily_2027.csv')
heat, cool = dem.arrays()
for depth, grad in ((3000, 30.0), (2500, 30.0), (1800, 30.0), (2500, 20.0)):
    r = Rules(gradient_c_per_km=grad)
    p = Plant(1, depth_m=depth, heat_pump_mw=2, boiler_mw=30, absorption_mw=6, chiller_mw=10)
    y = simulate_year(p, dem, stub_doublet, r)
    abs_ = np.array(y.daily_mw['cool']['abs'])
    print(f'depth {depth} grad {grad}: wellhead {y.wellhead_c:.1f} C, generator out {y.wellhead_c-15:.1f} C; abs cold {y.cool_split_gwh["abs"]:.2f} GWh at COP {y.absorption_cop}; '
          f'days abs on {(abs_>0).sum()}; violations {[v[:60] for v in y.violations]}; warnings {[w[:60] for w in y.warnings]}')
    # hand: brine heat for abs = abs/0.75
    print('   brine heat for cooling GWh', round(y.cool_split_gwh['abs']/0.75,3), 'max cooling K', y.max_brine_cooling_k, 'min reinj', y.min_reinjection_c)
