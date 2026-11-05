"""Where the GEMINI well solve stops balancing, and what the search does then; half-open GEMINI check."""
from dataclasses import replace

import dioscuri_plant as dp
from dioscuri_plant.types import open_interval
from gemini_agent import engine, workbench
from gemini_agent.contract import DesignBrief
from gemini_agent.tools import gemini as G

R = dp.Rules()
for k in (10.0, 9.0, 8.5, 8.0, 5.0):
    rt = replace(R, permeability_md=k)
    try:
        p = G.doublet_point(300, 2500, rt)
        print(k, "D.m", k * 100 / 1000, "ok inj whp", round(p["injection_wellhead_bar"], 1))
    except Exception as e:
        print(k, "D.m", k * 100 / 1000, "EXC", type(e).__name__)

for k in (8.0,):
    try:
        out = engine.search(DesignBrief(rules={"permeability_md": k}))
        print("search k", k, "chosen", out.chosen.alternative.code if out.chosen else None,
              "notes", out.notes[:3])
    except Exception as e:
        print("search k", k, "EXC", type(e).__name__, str(e)[:150])

# Half-open producer: what the GEMINI check compares with.
d = {"producer_open": "upper"}
proj = G.plant_project([d], R, 10.0)
res = workbench.run_gemini(proj)
gem = res["outputs"]["producer_well"]["esp_power_el"] / 1e6
check_side = G.doublet_point(300, 2500, R, "fixed")["esp_mw"]
p_mid, p_len = open_interval(2500, "upper", 100)
year_side = G.doublet_model(R)(300, p_mid, p_len)["esp_mw"]
print("half-open producer ESP: GEMINI", round(gem, 4), "check's plant", round(check_side, 4),
      "year model", round(year_side, 4))
