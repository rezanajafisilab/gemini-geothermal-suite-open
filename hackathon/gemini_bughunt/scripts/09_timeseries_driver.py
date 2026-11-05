"""Driving the (steady-state) simulator with an 8760-hour profile.

The Solver has run(time_vector) and calls component.set_time(t) on any component
that defines it, but no shipped component uses set_time and boundary inputs are
constant. Three ways to drive it hourly are timed here:

 A. custom ProfileSource component (set_time) registered at runtime -> ONE
    solver.run(time_vector=range(8760)) call
 B. plain Python loop: set_boundary_input(...) + run([t]) per hour
 C. demand-following: per hour, brentq on the secondary flow so that the
    secondary network delivers the hourly heat demand (several solves per hour)

  python 09_timeseries_driver.py <tree>
"""

import copy
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / "src"))

from gemini_model.model_abstract import StaticModel  # noqa: E402
from gemini_simulator import kpi  # noqa: E402
from gemini_simulator.project_loader import build_project  # noqa: E402
from gemini_simulator.registry import COMPONENT_REGISTRY  # noqa: E402

# Synthetic Dutch-like hourly heat demand (MW): degree-hour model + daily shape
hours = np.arange(8760)
t_amb = 10.5 - 7.5 * np.cos(2 * np.pi * (hours / 24 - 15) / 365) - 3 * np.cos(2 * np.pi * (hours % 24 - 15) / 24)
demand_mw = 0.6 + 0.45 * np.clip(16.0 - t_amb, 0, None)  # base (DHW) + space heating
demand_mw = np.minimum(demand_mw, 9.0)
print(f"demand profile: min {demand_mw.min():.2f} MW, max {demand_mw.max():.2f} MW, annual {demand_mw.sum()/1e3:.1f} GWh")

RHO, CP = 1050.0, 4200.0
T_S_IN = 20.0
# naive mapping: secondary flow proportional to demand (design 8 MW at 140 m3/h)
qs_m3h = np.clip(demand_mw / 8.0 * 140.0, 10.0, 200.0)


class ProfileSource(StaticModel):
    """Outputs parameters['values'][t] after set_time(t)."""

    def __init__(self):
        super().__init__()
        self._t = 0

    def set_time(self, t):
        self._t = int(t)

    def calculate_output(self, u, x=None):
        self.output["value"] = self.parameters["values"][self._t]


COMPONENT_REGISTRY["profile_source"] = ProfileSource

proj = json.loads((TREE / "simulator_examples/projects/doublet_plant.json").read_text())

# ---- A
pa = copy.deepcopy(proj)
pa["components"]["qs_profile"] = {"type": "profile_source", "parameters": {"values": list(qs_m3h / 3600)}}
pa["connections"].insert(0, {"predecessor": "qs_profile", "successor": "secondary_splitter",
                             "predecessor_output": "value", "successor_input": "input"})
s = build_project(pa)
t0 = time.perf_counter()
hist = s.run(time_vector=list(hours))
ta = time.perf_counter() - t0
t_mix = np.array([o["temperature"] for o in hist["water_mixer"]["output"]])
p_plant = qs_m3h / 3600 * RHO * CP * (t_mix - T_S_IN) / 1e6
print(f"A. ProfileSource + one run(range(8760)): {ta:.1f} s ({ta/8760*1e3:.2f} ms/h);"
      f" delivered {p_plant.sum()/1e3:.1f} GWh/yr, T_s_out range {t_mix.min():.1f}-{t_mix.max():.1f} C")

# ---- B
s = build_project(copy.deepcopy(proj))
t0 = time.perf_counter()
for h in hours:
    s.set_boundary_input("secondary_splitter", "input", qs_m3h[h] / 3600)
    s.run(time_vector=[h])
tb = time.perf_counter() - t0
print(f"B. Python loop set_boundary_input + run([t]): {tb:.1f} s ({tb/8760*1e3:.2f} ms/h);"
      f" history length {len(s.history['water_mixer']['output'])}")

# ---- C demand following on 500 sampled hours
s = build_project(copy.deepcopy(proj))
nsolve = 0


def delivered(qs_m3s):
    global nsolve
    nsolve += 1
    s.set_boundary_input("secondary_splitter", "input", qs_m3s)
    s.run()
    return kpi.plant_thermal_power_w(s, qs_m3s, T_S_IN) / 1e6


sample = hours[::17][:500]
unmet = 0
t0 = time.perf_counter()
for h in sample:
    target = demand_mw[h]
    lo, hi = 1 / 3600, 400 / 3600
    if delivered(hi) < target:
        unmet += 1
        continue
    brentq(lambda q: delivered(q) - target, lo, hi, xtol=1e-6)
tc = time.perf_counter() - t0
print(f"C. demand-following (brentq on secondary flow): {len(sample)} h in {tc:.1f} s,"
      f" {nsolve/len(sample):.1f} solves/h, {tc/len(sample)*1e3:.1f} ms/h -> ~{tc/len(sample)*8760/60:.1f} min for 8760 h;"
      f" unmet hours {unmet}")
print(f"   memory note: run() keeps full input/output history for every component at every step"
      f" (history entries now: {len(s.history['producer_well']['output'])})")
