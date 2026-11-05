"""Producer nodal residual scan: the default bracket (0.01-700 m3/h) runs far past
the ESP polynomial's valid range, so the residual p_well(Q) - p_res(Q) can have
several roots and brentq may return one where the ESP head polynomial is garbage
and the ESP intake pressure is clamped to 0 bar (nodal_solver.py:67).

  python 11_nodal_multiple_roots.py <tree>
"""

import copy
import json
import sys
from pathlib import Path

import numpy as np

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / "src"))

from gemini_model.pump.esp import ESP  # noqa: E402
from gemini_model.reservoir.inflow_performance import IPR  # noqa: E402
from gemini_simulator import nodal_solver as ns  # noqa: E402
from gemini_simulator.well_flow import (  # noqa: E402
    _build_dpdt,
    _resolve_trajectory_segments,
    _split_trajectory_at_depth,
    solve_primary_flow_m3h,
)

proj = json.loads((TREE / "simulator_examples/projects/doublet_plant.json").read_text())
base = proj["components"]["producer_well"]["parameters"]

cases = {
    "doublet_plant.json producer as shipped": dict(base),
    "same, roughness_m=4.5e-5": dict(base, roughness_m=4.5e-5),
    "2500 m hydrostatic, ID 0.2 m, PI 15, k=4.5e-5": dict(
        base, roughness_m=4.5e-5, reservoir_pressure_bar=246.25, productivity_index_m3h_per_bar=15.0,
        esp_depth_m=600, trajectory_table=[{"MD": 0, "TVD": 0, "ID": 0.2}, {"MD": 2500, "TVD": 2500, "ID": 0.2}]),
}

for name, cfg in cases.items():
    ipr = IPR()
    ipr.update_parameters({"type": "production_reservoir", "reservoir_pressure": cfg["reservoir_pressure_bar"] * 1e5,
                           "productivity_index": cfg["productivity_index_m3h_per_bar"] / 3.6e8})
    segs = _resolve_trajectory_segments(cfg)
    top, bot = _split_trajectory_at_depth(segs, cfg["esp_depth_m"])
    k = cfg.get("roughness_m", 0.01)
    dt, db = _build_dpdt(top, roughness=k), _build_dpdt(bot, roughness=k)
    esp = ESP()
    esp.update_parameters(cfg["esp"])
    qs = np.linspace(0.01, 700, 2000)
    res, clamp = [], []
    for q in qs:
        pw = ns._well_bottomhole_pressure_production(dt, db, esp, q / 3600, 3e5, 353.15, 293.15, cfg["esp_freq_hz"])
        ipr.calculate_output({"flow": q / 3600}, None)
        res.append(pw - ipr.get_output()["bottomhole_pressure"])
        # was the intake clamped?
        dt.calculate_output({"pressure": 3e5, "temperature": 353.15, "temperature_ambient": 293.15,
                             "flowrate": q / 3600, "direction": "down"}, None)
        esp.calculate_output({"pump_freq": cfg["esp_freq_hz"], "pump_flow": q / 3600})
        clamp.append(dt.get_output()["pressure_output"] - esp.get_output()["pump_head"] <= 0)
    res = np.array(res)
    roots = [round(float(qs[i]), 1) for i in range(len(qs) - 1) if np.sign(res[i]) != np.sign(res[i + 1])]
    q_sol = solve_primary_flow_m3h(cfg, 3.0, 80.0)
    i = int(np.argmin(abs(qs - q_sol)))
    esp.calculate_output({"pump_freq": cfg["esp_freq_hz"], "pump_flow": q_sol / 3600})
    y = esp.get_output()
    print(f"{name}:")
    print(f"   sign changes of residual on 0.01-700 m3/h at Q ~ {roots}")
    print(f"   brentq solution Q={q_sol:.1f} m3/h; ESP head there={y['pump_head']/1e5:.1f} bar,"
          f" eff={y['pump_eff']:.0f} %, intake clamped to 0: {bool(clamp[i])}")
