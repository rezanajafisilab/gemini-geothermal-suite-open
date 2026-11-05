from common import *
from dioscuri_plant import explore as ex
from dioscuri_plant.search import improve, Topology
srch = S['searches'][-1]; sw = srch['sweep']
cols = sw['columns']; rows = sw['rows']
ref_rounds, ref_year = improve(Topology(0), DEMAND, MODEL, RULES)
ref_econ = dp.economics(ref_rounds[-1].plant, ref_year, PRICES, rules=RULES)
ex._init({"demand": DEMAND, "doublet": MODEL, "rules": RULES, "components": dp.Components(), "prices": PRICES, "reference": (ref_year, ref_econ)})
for i in (4940, 1596):
    r = rows[i]
    pt = ex.Point(*(r[:9]), lcoe=r[9], lcoh=r[10], co2_t=r[11], co2_saving=r[12]/100, capex_meur=r[13], broken=r[14])
    p0, run0 = ex._run_one(ex._plant_of(pt))
    print(i, 'as drawn rerun: lcoe', round(p0.lcoe,2), 'co2', round(p0.co2_t,1), 'ok', p0.ok)
    plant, years = ex.refine(pt)
    p1, run = ex._run_one(plant)
    print(i, 'refined', plant.n_doublets, plant.depth_m, plant.doublet_specs[0].max_flow_m3h, plant.heat_pump_mw, plant.boiler_mw, plant.electric_boiler_mw, plant.absorption_mw, plant.chiller_mw, plant.gas, '-> lcoe', round(p1.lcoe,2), 'co2', round(p1.co2_t,1), 'ok', p1.ok, 'years', years)
