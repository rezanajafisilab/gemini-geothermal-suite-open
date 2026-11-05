from common import *
from dioscuri_plant import firm
from dioscuri_plant.search import improve, Topology
from dataclasses import replace
ref_rounds, ref_year = improve(Topology(0), DEMAND, MODEL, RULES)
ref_econ = dp.economics(ref_rounds[-1].plant, ref_year, PRICES, rules=RULES)
specs = tuple(dp.Doublet(depth_m=3300.0, max_flow_m3h=210.0) for _ in range(3))
p = dp.Plant(3, depth_m=3300.0, doublet_specs=specs, gas='sell', heat_pump_mw=0.0, boiler_mw=0.0, electric_boiler_mw=1.35, absorption_mw=0.0, chiller_mw=11.1)
y = dp.simulate_year(p, DEMAND, MODEL, RULES); ec = dp.economics(p, y, PRICES, reference=(ref_year, ref_econ), rules=RULES)
print('4940r', ec.lcoe_eur_per_mwh, ec.co2_t_per_year, y.violations)
q, rounds, last = firm.reliable(p, DEMAND, MODEL, RULES)
yq = dp.simulate_year(q, DEMAND, MODEL, RULES); eq = dp.economics(q, yq, PRICES, reference=(ref_year, ref_econ), rules=RULES)
held = all(o['heat']['days_short']==0 and o['cool']['days_short']==0 for o in last)
print('reliable plan', q.electric_boiler_mw, q.chiller_mw, 'held', held, 'lcoe', eq.lcoe_eur_per_mwh, 'co2', eq.co2_t_per_year, yq.violations)
