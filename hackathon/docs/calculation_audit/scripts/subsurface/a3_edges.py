"""Edge cases: tight rock, other aquifers (gauge vs absolute), clamps, Henry constants."""
import math
import traceback
from dataclasses import replace

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant import doublet as D
from dioscuri_plant import subsurface as S
from dioscuri_plant.search import subsurface_caps
from gemini_agent import engine
from gemini_agent.tools import gemini as G

R = dp.Rules()
print("Henry 25C CH4 GPa", S.henry_pa("ch4", 25) / 1e9, "CO2", S.henry_pa("co2", 25) / 1e9)

print("== gauge vs absolute for a second aquifer at 3000 m ==")
r2 = replace(R, second_aquifer_depth_m=3000.0)
a = r2.aquifers()
print([x.pressure_bar for x in a], "assumed at 3000:", D.reservoir_pressure_bar(3000, R))
m1 = G.doublet_model(R)(300, 3000.0)
m2 = G.doublet_model(r2)(300, 3000.0)
print("assumed: ESP", m1["esp_mw"], "inj", m1["injector_pump_mw"], "| second_aquifer: ESP", m2["esp_mw"],
      "inj", m2["injector_pump_mw"])

print("== tight rock ==")
for k, h in ((20.0, 20.0), (5.0, 10.0), (1.0, 5.0)):
    rt = replace(R, permeability_md=k, reservoir_thickness_m=h)
    pi = D.productivity_index_m3h_per_bar(rt)
    try:
        p = G.doublet_point(300, 2500, rt)
        print(k, h, "PI", round(pi, 3), "ESP head", round(p["esp_head_bar"], 1), "bhp", round(p["bottomhole_bar"], 1),
              "inj whp", round(p["injection_wellhead_bar"], 1))
    except Exception as e:
        print(k, h, "PI", round(pi, 3), "EXC", type(e).__name__, str(e)[:120])
    try:
        model = G.doublet_model(rt)
        demand = engine.demand_of(engine.DesignBrief()) if hasattr(engine, "DesignBrief") else None
    except Exception:
        pass

from gemini_agent.contract import DesignBrief
demand = engine.demand_of(DesignBrief())
for k, h in ((20.0, 20.0), (5.0, 10.0)):
    rt = replace(R, permeability_md=k, reservoir_thickness_m=h)
    model = G.doublet_model(rt)
    plant = dp.Plant(1, heat_pump_mw=3.0, boiler_mw=30.0, chiller_mw=12.0)
    try:
        y = dp.simulate_year(plant, demand, model, rt)
        row = y.doublet_summary[0]
        print(f"k={k} h={h}: viol {y.violations}")
        print("   pumps GWh", y.electricity_gwh["pumps"], "esp_head_full", row["esp_head_full_bar"],
              "inj_full", row["injection_full_bar"], "setting", row.get("esp_setting_m"),
              "inj_top", row.get("injection_top_bar"), "limit", row.get("injection_limit_bar"))
        capped = subsurface_caps(plant, y, rt)
        print("   caps ->", capped[1] if capped else None)
        if capped:
            y2 = dp.simulate_year(capped[0], demand, model, rt)
            print("   after cap viol", y2.violations, "pumps", y2.electricity_gwh["pumps"])
    except Exception as e:
        print(f"k={k} h={h}: EXC {type(e).__name__}: {str(e)[:200]}")

print("== negative bottomhole pressure ==")
rt = replace(R, permeability_md=2.0, reservoir_thickness_m=10.0)
p = D.stub_doublet(300, 2500, rules=rt)
print("stub PI", p["pi_m3h_per_bar"], "head", p["esp_head_bar"], "inj", p["injection_wellhead_bar"])
