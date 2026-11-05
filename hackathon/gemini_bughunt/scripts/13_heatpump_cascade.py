"""Realistic geothermal + heat-pump cascade wired through the simulator: the HEX
primary outlet feeds a heat pump's evaporator (source), whose minimum source
outlet temperature (Ts_in_minimum) is the re-injection temperature limit.
HeatpumpBasic is not in COMPONENT_REGISTRY, so it is registered at runtime.

  python 13_heatpump_cascade.py <tree>
"""

import copy
import json
import sys
import warnings
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / "src"))
warnings.filterwarnings("ignore")

from gemini_model.heatpump.heatpump_basic import HeatpumpBasic  # noqa: E402
from gemini_simulator.project_loader import build_project  # noqa: E402
from gemini_simulator.registry import COMPONENT_REGISTRY  # noqa: E402

print("'heatpump' in registry as shipped:", "heatpump" in COMPONENT_REGISTRY)
COMPONENT_REGISTRY["heatpump"] = HeatpumpBasic

proj = json.loads((TREE / "simulator_examples/projects/doublet_plant.json").read_text())
for ts_min in (10.0, 30.0):
    for hot_m3h in (40.0, 80.0):
        p = copy.deepcopy(proj)
        p["components"]["hp"] = {"type": "heatpump", "parameters": {
            "mode": "carnot", "eta_carnot": 0.5, "Th_out_target": 75.0, "Ts_in_minimum": ts_min}}
        p["boundary_inputs"] += [{"component": "hp", "key": "Th_in", "value": 45.0},
                                 {"component": "hp", "key": "hot_flow_rate", "value": hot_m3h / 3600}]
        p["connections"].append({"predecessor": "heat_exchanger", "successor": "hp", "ports": [
            ["primary_temperature_out", "Ts_in"], ["primary_flow_rate", "source_flow_rate"]]})
        s = build_project(p)
        s.run()
        y = s.get_output("hp")
        q_src = s.get_output("producer_well", "flow_rate") / 3600 * 1000 * 4181 * (
            s.get_output("heat_exchanger", "primary_temperature_out") - y["Ts_out"])
        print(f"Ts_min={ts_min:4.1f} C, sink 45->75 C at {hot_m3h:4.0f} m3/h, source = HEX primary out"
              f" {s.get_output('heat_exchanger', 'primary_temperature_out'):.1f} C @ {s.get_output('producer_well', 'flow_rate'):.0f} m3/h:"
              f" COP={y['COP']:.2f} Th_out={y['Th_out']:.1f} C Ts_out={y['Ts_out']:.1f} C"
              f" Q_cond={y['power_th']/1e6:.2f} MW W_el={y['power_el']/1e6:.2f} MW (source can give {q_src/1e6:.2f} MW)")
