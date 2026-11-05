"""Producer nodal-solve robustness: sweep ESP frequency / wellhead pressure / PI /
roughness on doublet_plant.json and flag (i) exceptions, (ii) solutions where the
ESP intake pressure was clamped to 0 bar (nodal_solver.py:67 max(0.0, ...)),
(iii) solutions far outside the ESP polynomial's sensible range (head<=0 or
power<=0 or efficiency > 100%).

  python 05_nodal_robustness.py <tree>
"""

import copy
import itertools
import json
import sys
from pathlib import Path

import numpy as np

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / "src"))

from gemini_model.pump.esp import ESP  # noqa: E402
from gemini_simulator.well_components import ProducerWell  # noqa: E402

proj = json.loads((TREE / "simulator_examples/projects/doublet_plant.json").read_text())
base = proj["components"]["producer_well"]["parameters"]

print("=== ESP curve of doublet_plant.json (10 stages) evaluated over the default nodal bracket 0.01-700 m3/h")
esp = ESP()
esp.update_parameters(base["esp"])
for f in (50, 65):
    print(f"  {f} Hz:")
    for q in (0, 50, 100, 150, 200, 250, 300, 400, 500, 600, 700):
        esp.calculate_output({"pump_freq": f, "pump_flow": q / 3600})
        y = esp.get_output()
        print(f"    Q={q:4d} m3/h head={y['pump_head']/1e5:8.2f} bar power={y['pump_power']/1e3:9.1f} kW eff={y['pump_eff']:8.1f} %")

print()
print("=== Sweep of ProducerWell (doublet_plant.json producer)")
rows = []
for f, pwh, pi, k in itertools.product((40, 50, 60, 65, 70), (3.0, 10.0, 20.0), (5.0, 10.0, 30.0), (0.01, 4.5e-5)):
    p = copy.deepcopy(base)
    p.update({"esp_freq_hz": f, "productivity_index_m3h_per_bar": pi, "roughness_m": k})
    w = ProducerWell()
    w.update_parameters(p)
    try:
        w.calculate_output({"wellhead_pressure": pwh, "wellhead_temperature": 80.0})
        y = w.get_output()
        esp.calculate_output({"pump_freq": f, "pump_flow": y["flow_rate_m3s"]})
        e = esp.get_output()
        flags = []
        if y["esp_intake_pressure"] is not None and y["esp_intake_pressure"] <= 1e-9:
            flags.append("ESP_intake_clamped_to_0")
        if e["pump_head"] <= 0 or e["pump_power"] <= 0 or e["pump_eff"] > 100 or e["pump_eff"] < 0:
            flags.append("ESP_curve_out_of_range")
        rows.append((f, pwh, pi, k, round(y["flow_rate"], 1), round(y["esp_intake_pressure"], 2),
                     round(e["pump_head"] / 1e5, 1), round(e["pump_power"] / 1e3, 1), round(e["pump_eff"], 1), flags))
    except Exception as ex:  # noqa
        rows.append((f, pwh, pi, k, "EXC", type(ex).__name__, str(ex)[:70]))

n_exc = sum(1 for r in rows if r[4] == "EXC")
n_clamp = sum(1 for r in rows if r[4] != "EXC" and "ESP_intake_clamped_to_0" in r[-1])
n_range = sum(1 for r in rows if r[4] != "EXC" and "ESP_curve_out_of_range" in r[-1])
print(f"  cases={len(rows)} exceptions={n_exc} intake-clamped={n_clamp} ESP-curve-out-of-range={n_range}")
print("  (freq Hz, Pwh bar, PI m3/h/bar, roughness m) -> Q m3/h, ESP_in bar, head bar, power kW, eff %, flags")
for r in rows:
    if r[4] == "EXC" or r[-1]:
        print("   ", r)
