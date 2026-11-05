"""Solver behaviour checks.

 1. Recycle loop (closed secondary loop): one run() = one Gauss-Seidel sweep, no
    convergence check -> silently non-converged result.
 2. Connection order: same JSON with connections in a different order.
 3. Missing boundary input / wrong key -> what error does the user get?

  python 08_solver.py <tree>
"""

import copy
import json
import random
import sys
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / "src"))

from gemini_simulator.project_loader import build_project  # noqa: E402

print("=== 1. Closed secondary loop: HEX secondary out -> 'consumer' (Filter used as fixed 15 K temperature drop)")
print("       -> back to HEX secondary inlet. Seed return temperature 40 C.")
loop = {
    "components": {
        "hex": {"type": "heat_exchanger", "parameters": {"flow_resistance": 0, "flow_configuration": "counter",
                                                          "heat_transfer_coefficient": 250000}},
        "consumer": {"type": "filter", "parameters": {"base_resistance": 0, "fouling_coeff_a": 0,
                                                       "fouling_coeff_b": 0, "temperature_drop": 15}},
    },
    "boundary_inputs": [
        {"component": "hex", "key": "pressure_in", "value": 5.0},
        {"component": "hex", "key": "primary_temperature_in", "value": 80.0},
        {"component": "hex", "key": "primary_flow_rate", "value": 150 / 3600},
        {"component": "hex", "key": "secondary_flow_rate", "value": 150 / 3600},
        {"component": "hex", "key": "secondary_temperature_in", "value": 40.0},  # seed
        {"component": "consumer", "key": "pressure", "value": 5.0},
        {"component": "consumer", "key": "flow_rate", "value": 150 / 3600},
    ],
    "connections": [
        {"predecessor": "hex", "successor": "consumer", "predecessor_output": "secondary_temperature_out",
         "successor_input": "temperature"},
        {"predecessor": "consumer", "successor": "hex", "predecessor_output": "temperature_out",
         "successor_input": "secondary_temperature_in"},
    ],
}
for nsteps in (1, 2, 5, 20, 100):
    s = build_project(copy.deepcopy(loop))
    s.run(time_vector=list(range(nsteps)))
    h = s.get_output("hex")
    tin = s.history["hex"]["input"][-1]["secondary_temperature_in"]
    print(f"  run(time_vector of {nsteps:3d} steps): last step T_sec_in={tin:6.2f} C,"
          f" T_sec_out={h['secondary_temperature_out']:6.2f} C, duty={h['heat_duty']/1e6:6.3f} MW,"
          f" loop residual (T_out-15 - T_in)={h['secondary_temperature_out']-15-tin:+.3f} K")
print("  -> a single steady-state run() returns the first sweep; nothing warns that the loop is not closed.")

print()
print("=== 2. doublet_plant.json with connections shuffled (same physics, different declared order)")
proj = json.loads((TREE / "simulator_examples/projects/doublet_plant.json").read_text())
s = build_project(proj)
s.run()
ref = (s.get_output("water_mixer", "temperature"), s.get_output("injector_well", "wellhead_pressure"))
print(f"  declared order: T_s_out={ref[0]:.3f} C")
random.seed(1)
outcomes = {}
for trial in range(30):
    p = copy.deepcopy(proj)
    random.shuffle(p["connections"])
    try:
        s = build_project(p)
        s.run()
        t = round(s.get_output("water_mixer", "temperature"), 3)
        outcomes.setdefault(f"ran, T_s_out={t}", 0)
        outcomes[f"ran, T_s_out={t}"] += 1
    except Exception as e:  # noqa
        k = f"{type(e).__name__}: {e}"[:90]
        outcomes[k] = outcomes.get(k, 0) + 1
for k, v in sorted(outcomes.items(), key=lambda kv: -kv[1]):
    print(f"  {v:2d} x {k}")
print("  shuffled, run(time_vector=range(5)) (stale inputs from previous sweep are re-used):")
outcomes = {}
random.seed(1)
for trial in range(30):
    p = copy.deepcopy(proj)
    random.shuffle(p["connections"])
    # seed every input that a shuffled order may read before it is produced
    try:
        s = build_project(p)
        s.run(time_vector=list(range(5)))
        t = round(s.get_output("water_mixer", "temperature"), 3)
        outcomes[f"ran, T_s_out={t}"] = outcomes.get(f"ran, T_s_out={t}", 0) + 1
    except Exception as e:  # noqa
        k = f"{type(e).__name__}: {e}"[:90]
        outcomes[k] = outcomes.get(k, 0) + 1
for k, v in sorted(outcomes.items(), key=lambda kv: -kv[1]):
    print(f"  {v:2d} x {k}")

print()
print("=== 3. Producer wellhead pressure too high for the ESP/reservoir (no root in bracket)")
p = copy.deepcopy(proj)
for b in p["boundary_inputs"]:
    if b["component"] == "producer_well" and b["key"] == "wellhead_pressure":
        b["value"] = 60.0
try:
    s = build_project(p)
    s.run()
    print("  ran:", s.get_output("producer_well", "flow_rate"))
except Exception as e:  # noqa
    print(f"  {type(e).__name__}: {e}")
