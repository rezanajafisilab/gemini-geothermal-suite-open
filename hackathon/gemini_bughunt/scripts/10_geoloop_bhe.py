"""geoloop branch: BHEGeoloop smoke test, energy balance, per-step cost growth and
behaviour inside gemini_simulator.Solver.

Needs Python 3.12 + geoloop==1.1.0. Run from an empty scratch dir (the default
config has base_dir="output"):
  PYTHONPATH=<geoloop-tree>/src python3.12 10_geoloop_bhe.py
"""

import time
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from gemini_model.bhe_geoloop.bhe_geoloop import BHEGeoloop  # noqa: E402
from gemini_simulator.solver import Solver  # noqa: E402

CP_W = 4180.0

print("=== 1. Stand-alone, default config (100 m single U-tube, TIN mode, Tin=5 C, m=0.45 kg/s)")
m = BHEGeoloop()
m.initialize_state({})
sp = m._single_run.sim_params
print(f"  geoloop dt = {sp.dt:.0f} s ({sp.dt/3600:.0f} h per model step); Tg={m._config.Tg} C, Tgrad={m._config.Tgrad} C/100m?")
times = []
for k in range(1, 41):
    t0 = time.perf_counter()
    m.calculate_output({"mass_flow_rate": 0.45, "inlet_temperature": 5.0})
    times.append(time.perf_counter() - t0)
    y = m.get_output()
    if k in (1, 2, 5, 10, 20, 40):
        q_fluid = 0.45 * CP_W * (y["outlet_temperature"] - y["inlet_temperature"])
        print(f"  step {k:2d}: T_out={y['outlet_temperature']:.3f} C, Q_b={y['heat_extracted']:.1f} W,"
              f" m*cp*(Tout-Tin)={q_fluid:.1f} W, pump={y['pump_power']:.2f} W,"
              f" T_b,mean={y['mean_borehole_wall_temperature']:.3f} C, wall-time {times[-1]*1e3:.0f} ms,"
              f" history len={len(m.state['mass_flow_rate_hist'])}")
print(f"  per-step wall time grows: step1 {times[0]*1e3:.0f} ms -> step40 {times[-1]*1e3:.0f} ms"
      f" (whole history re-simulated every call)")

print()
print("=== 2. Same model inside gemini_simulator.Solver (DynamicModel path), 5 solver time steps")
m2 = BHEGeoloop()
calls = {"calc": 0, "upd": 0}
orig_calc, orig_upd = m2.calculate_output, m2.update_state


def calc(u, x=None):
    calls["calc"] += 1
    return orig_calc(u, x)


def upd(u, x):
    calls["upd"] += 1
    return orig_upd(u, x)


m2.calculate_output, m2.update_state = calc, upd
s = Solver({"bhe": m2})
s.set_boundary_input("bhe", "mass_flow_rate", 0.45)
s.set_boundary_input("bhe", "inlet_temperature", 5.0)
s.run(time_vector=[0, 1, 2, 3, 4])
print(f"  solver steps=5 -> calculate_output calls={calls['calc']}, update_state calls={calls['upd']},"
      f" geoloop history length={len(m2.state['mass_flow_rate_hist'])} (expected 5)")
print(f"  solver-recorded outputs T_out: {[round(o['outlet_temperature'], 3) for o in s.history['bhe']['output']]}")

print()
print("=== 3. Hourly use: nled=1 -> dt")
m3 = BHEGeoloop()
m3.update_parameters({"nled": 1})
m3.initialize_state({})
print(f"  nled=1 -> geoloop dt = {m3._single_run.sim_params.dt:.0f} s")
t0 = time.perf_counter()
n = 200
for k in range(n):
    m3.calculate_output({"mass_flow_rate": 0.45, "inlet_temperature": 5.0})
el = time.perf_counter() - t0
print(f"  {n} hourly steps in {el:.1f} s; last step T_out={m3.get_output()['outlet_temperature']:.3f} C")

print()
print("=== 4. POWER mode (heat load prescribed)")
m4 = BHEGeoloop()
m4.update_parameters({"run_type": "POWER"})
m4.initialize_state({})
try:
    for k in range(3):
        m4.calculate_output({"mass_flow_rate": 0.45, "heat_load": 3000.0})
    y = m4.get_output()
    print(f"  POWER ok: T_in={y['inlet_temperature']:.3f} T_out={y['outlet_temperature']:.3f} Q_b={y['heat_extracted']:.1f} W")
except Exception as e:  # noqa
    print(f"  POWER mode EXCEPTION {type(e).__name__}: {e}")
