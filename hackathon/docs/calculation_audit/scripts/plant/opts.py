import sys
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
lead = dp.Plant(n_doublets=1, depth_m=3000.0, heat_pump_mw=0.5, boiler_mw=30.0, chiller_mw=15.0, boiler_units=3, chiller_units=3, reliable=True)
def show(tag, y):
    hs = y.heat_split_gwh; cs = y.cool_split_gwh
    srcs = hs['geo']+hs['hp']+hs['boiler']+hs['electric_boiler']
    print(f"--- {tag}: dem {y.heat_demand_gwh} deliv {y.heat_delivered_gwh} sum_src {srcs:.3f} cov {y.heat_coverage} short_pk {y.peak_shortfall_mw} bal {y.balance_error}")
    print('   heat', hs, '\n   cool', cs, '\n   el', y.electricity_gwh, 'gas', y.purchased_gas_gwh, y.produced_gas_burned_gwh, y.produced_gas_flared_gwh, y.produced_gas_sold_gwh)
    print('   co2', y.co2_t, '\n   viol', y.violations[:3], 'stops', y.stop_ranges, 'svc', y.service[:6])
    if y.storage: print('   storage', y.storage)
    if y.solar: print('   solar', y.solar)
    if y.network: print('   network', y.network)
base = replace(rules, free_cooling=1.0)
show('lead', dp.simulate_year(lead, demand, model, base))
show('lead+service', dp.simulate_year(lead, demand, model, replace(base, planned_service=1.0)))
show('lead+net5km', dp.simulate_year(lead, demand, model, replace(base, network_length_km=5.0)))
show('lead+tank2000', dp.simulate_year(lead, demand, model, replace(base, storage_mwh=2000.0)))
show('lead+ates', dp.simulate_year(lead, demand, model, replace(base, storage_mwh=20000.0, storage_ates=1.0)))
show('lead+solar3', dp.simulate_year(lead, demand, model, replace(base, solar_mwp=3.0)))
show('lead+gridmonth', dp.simulate_year(lead, demand, model, replace(base, grid_by_month=1.0)))
show('lead sell', dp.simulate_year(replace(lead, gas='sell'), demand, model, base))
show('lead produced-only', dp.simulate_year(replace(lead, gas='produced'), demand, model, base))
