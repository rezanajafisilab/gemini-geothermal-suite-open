"""The year model's subsurface side: flows, 40 K cap, brine energy, pumps, gas and CO2."""
import numpy as np

import dioscuri_plant as dp
from dioscuri_plant.components import Components, CO2_KG_PER_NM3, LHV_CH4_MJ_PER_NM3
from gemini_agent import engine
from gemini_agent.contract import DesignBrief

brief = DesignBrief()
R = engine.rules_for(brief)
print("rules", R.heat_return_c, R.brine_cp_j_kg_k, R.well_spacing_m, R.porosity, R.operating_days)
demand = engine.demand_of(brief)
model = engine.doublet_model(R)
C = Components()
heat, cool = demand.arrays()
print("demand GWh", heat.sum() * 24 / 1000, cool.sum() * 24 / 1000, heat.max(), cool.max())

designs = {
    "1D-HP": dp.Plant(1, heat_pump_mw=3.0, boiler_mw=30.0, chiller_mw=12.0),
    "2D-HP": dp.Plant(2, heat_pump_mw=5.0, boiler_mw=30.0, chiller_mw=12.0),
    "2D@2500+3500": dp.Plant(2, doublet_specs=(dp.Doublet(2500.0), dp.Doublet(3500.0)),
                             heat_pump_mw=5.0, boiler_mw=30.0, chiller_mw=12.0),
    "1D@3500": dp.Plant(1, depth_m=3500.0, heat_pump_mw=3.0, boiler_mw=30.0, chiller_mw=12.0),
    "3D-base": dp.Plant(3, heat_pump_mw=6.0, boiler_mw=30.0, chiller_mw=12.0, dispatch="base"),
    "2D-2inj-AB": dp.Plant(2, doublet_specs=(dp.Doublet(injectors=2), dp.Doublet(injectors=2)),
                           heat_pump_mw=4.0, absorption_mw=4.0, boiler_mw=30.0, chiller_mw=8.0),
}
for name, plant in designs.items():
    y = dp.simulate_year(plant, demand, model, R)
    flows = np.array([d["flow_m3h"] for d in y.doublets])
    on = np.array([d["on"] for d in y.doublets])
    twh = np.array([[t if t is not None else np.nan for t in d["wellhead_c"]] for d in y.doublets])
    rein = np.array([[t if t is not None else np.nan for t in d["reinjection_c"]] for d in y.doublets])
    cooling = np.nanmax(twh - rein)
    running = flows[on]
    days_on = on.sum(axis=1)
    # brine-side energy: sum over doublets of cb_i*(twh_i - t_reinj)
    cb = flows / 3600 * R.brine_density_kg_m3 * R.brine_cp_j_kg_k / 1e6
    brine_mw = np.nansum(np.where(on, cb * (twh - rein), 0.0), axis=0)
    dh = y.daily_mw["heat"]
    dc = y.daily_mw["cool"]
    hp = np.array(dh["hp"]); hp_el = np.array(y.daily_mw["power"]["hp"])
    absc = np.array(dc["abs"])
    side = np.array(dh["geo"]) + hp - hp_el + absc / C.absorption_cop
    bal = np.max(np.abs(brine_mw - side))
    # gas and CO2
    gas = flows.sum() * 24 * R.gas_liquid_ratio
    ch4_gwh = gas * R.gas_ch4_fraction * LHV_CH4_MJ_PER_NM3 / 3600 / 1000
    co2_native_t = gas * R.gas_co2_fraction * CO2_KG_PER_NM3 / 1000
    co2_ch4_t = gas * R.gas_ch4_fraction * CO2_KG_PER_NM3 / 1000
    pumps = y.electricity_gwh["pumps"]
    print(f"\n{name}: days_on {days_on.tolist()} flow range {running.min():.1f}-{running.max():.1f} "
          f"max cooling {cooling:.2f} K (reported {y.max_brine_cooling_k}) brine-balance err {bal:.2e} MW")
    print(f"  heat split {y.heat_split_gwh} pumps {pumps} GWh, peak brine heat {y.peak_brine_heat_mw}")
    print(f"  CH4 {ch4_gwh:.3f} GWh vs burned+flared+sold "
          f"{y.produced_gas_burned_gwh + y.produced_gas_flared_gwh + y.produced_gas_sold_gwh:.3f}; "
          f"CO2 produced {y.co2_t['produced_gas']} vs hand {co2_native_t + co2_ch4_t:.1f}")
    print("  violations", y.violations)
    for row in y.doublet_summary:
        print("  ", {k: row.get(k) for k in ("doublet", "depth_m", "wellhead_full_c", "esp_head_full_bar",
                                              "injection_full_bar", "breakthrough_years", "esp_setting_m",
                                              "injection_top_bar", "injection_limit_bar", "flow_year_mean_m3h",
                                              "esp_gwh", "injection_gwh", "reservoir_pressure_bar")})
