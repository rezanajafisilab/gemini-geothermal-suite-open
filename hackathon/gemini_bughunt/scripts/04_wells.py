"""Well / reservoir checks.

 A. DPDT single-phase vs. hand calculation (2.5 km vertical, 100-200 m3/h).
 B. Injection friction sign: DPDT direction="down" with +Q (what the simulator
    passes) vs -Q (what gemini_framework's injection-well module passes).
 C. Impact on the two example projects + a hydrostatic-reservoir doublet:
    injector wellhead pressure / injector pump power as-is vs. friction-sign fixed.
 D. Roughness default 0.01 m vs 4.5e-5 m (new steel): friction dp, producer
    flow, ESP power, injector pressure.
 E. Temperature drop sign/magnitude (production "up" from bottomhole).

  PYTHONPATH=<tree>/src python 04_wells.py <tree>
"""

import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / "src"))

import gemini_simulator.nodal_solver as ns  # noqa: E402
from gemini_model.fluid.pvt_water_stp import PVTConstantSTP  # noqa: E402
from gemini_model.well.pressure_drop import DPDT  # noqa: E402
from gemini_simulator.project_loader import build_project  # noqa: E402
from gemini_simulator.well_flow import _build_dpdt  # noqa: E402

G, RHO, MU = 9.81, 1000.0, 1e-3


def hand_dp(q_m3h, d, L, k):
    v = q_m3h / 3600 / (math.pi / 4 * d**2)
    re = RHO * v * d / MU
    f = 0.25 / math.log10(k / (3.7 * d) + 5.74 / re**0.9) ** 2
    return f * RHO * L / d * v**2 / 2, RHO * G * L, f, re


def dpdt(d, L, k, q_m3s, direction, p0=10e5, t0=273.15 + 80, tamb=273.15 + 20, ncell=1):
    w = DPDT()
    w.update_parameters({
        "diameter": np.full(ncell, d), "length": np.full(ncell, L / ncell),
        "angle": np.full(ncell, np.pi / 2), "roughness": np.full(ncell, k),
        "friction_correlation": "darcy_weisbach", "friction_correlation_2p": "BeggsBrill",
        "correction_factors": [1, 0]})
    w.PVT = PVTConstantSTP()
    w.calculate_output({"pressure": p0, "temperature": t0, "temperature_ambient": tamb,
                        "flowrate": q_m3s, "direction": direction}, None)
    return w.get_output()


print("=== A. DPDT vs hand calc: vertical L=2500 m, ID=0.2 m (~8\"), k=4.5e-5 m, water 1000 kg/m3, 1 mPa.s")
for q in (100, 150, 200):
    fr, gr, f, re = hand_dp(q, 0.2, 2500, 4.5e-5)
    y = dpdt(0.2, 2500, 4.5e-5, q / 3600, "up", p0=250e5)
    print(f"  Q={q} m3/h: hand fric={fr/1e5:.2f} bar grav={gr/1e5:.2f} bar (f={f:.4f}, Re={re:.3g});"
          f" DPDT fric={y['pressuredrop_fric_output']/1e5:.2f} grav={y['pressuredrop_grav_output']/1e5:.2f};"
          f" p_wh from p_bh=250 bar: {y['pressure_output']/1e5:.2f} bar")

print()
print("=== B. Injection (flow DOWN the well), wellhead 20 bar, Q=150 m3/h, L=2500 m, ID 0.2 m, k=4.5e-5")
fr, gr, *_ = hand_dp(150, 0.2, 2500, 4.5e-5)
print(f"  correct p_bh = p_wh + rho*g*h - dp_fric = {20 + gr/1e5 - fr/1e5:.2f} bar")
for sign in (+1, -1):
    y = dpdt(0.2, 2500, 4.5e-5, sign * 150 / 3600, "down", p0=20e5)
    print(f"  DPDT direction='down', flowrate={'+' if sign > 0 else '-'}Q: p_bh = {y['pressure_output']/1e5:.2f} bar"
          f" (fric term {y['pressuredrop_fric_output']/1e5:+.2f} bar)")
print("  simulator nodal_solver._well_bottomhole_pressure_injection passes +Q (see nodal_solver.py:146-153)")
print("  gemini_framework .../injectionwell/calculate_bottomhole_pressure.py:61 passes -Q")


def _inj_fixed(dpdt_, flow_rate, wellhead_pressure, wellhead_temperature):
    u = {"pressure": wellhead_pressure, "temperature": wellhead_temperature,
         "temperature_ambient": wellhead_temperature, "flowrate": -flow_rate, "direction": "down"}
    dpdt_.calculate_output(u, None)
    return dpdt_.get_output()["pressure_output"]


ORIG_INJ = ns._well_bottomhole_pressure_injection


def run_project(project, fixed_sign=False, roughness=None):
    project = copy.deepcopy(project)
    if roughness is not None:
        for w in ("producer_well", "injector_well"):
            project["components"][w]["parameters"]["roughness_m"] = roughness
    ns._well_bottomhole_pressure_injection = _inj_fixed if fixed_sign else ORIG_INJ
    try:
        s = build_project(project)
        s.run()
    finally:
        ns._well_bottomhole_pressure_injection = ORIG_INJ
    g = s.get_output
    return {
        "Q_m3h": g("producer_well", "flow_rate"),
        "ESP_kW": g("producer_well", "esp_power_el") / 1e3,
        "ESP_in_bar": g("producer_well", "esp_intake_pressure"),
        "inj_Pwh_bar": g("injector_well", "wellhead_pressure"),
        "inj_pump_kW": g("injector_well", "power_el") / 1e3,
    }


print()
print("=== C/D. Example projects: as-is vs friction-sign fix vs roughness")
projects = {p: json.loads((TREE / "simulator_examples" / "projects" / p).read_text())
            for p in ("doublet_plant.json", "parallel_hex_plant.json")}

# A hydrostatic-reservoir doublet (typical Dutch Rotliegend/Delft-sandstone-like), built from doublet_plant.json
hyd = copy.deepcopy(projects["doublet_plant.json"])
for w, tvd in (("producer_well", 2500), ("injector_well", 2500)):
    p = hyd["components"][w]["parameters"]
    p["trajectory_table"] = [{"MD": 0, "TVD": 0, "ID": 0.2}, {"MD": 2500, "TVD": 2500, "ID": 0.2}]
    p["reservoir_pressure_bar"] = 1.0 + RHO * G * tvd / 1e5  # hydrostatic ~246 bar
    p["productivity_index_m3h_per_bar"] = 15.0
hyd["components"]["producer_well"]["parameters"]["esp_depth_m"] = 600
projects["hydrostatic_2500m_doublet (derived)"] = hyd

for name, proj in projects.items():
    rough_given = proj["components"]["producer_well"]["parameters"].get("roughness_m", "default 0.01")
    print(f"-- {name}  (roughness_m in file: {rough_given})")
    for label, kw in (("as-is", {}), ("friction sign fixed", {"fixed_sign": True}),
                      ("roughness 4.5e-5 m", {"roughness": 4.5e-5}),
                      ("roughness 4.5e-5 + sign fixed", {"roughness": 4.5e-5, "fixed_sign": True})):
        try:
            r = run_project(proj, **kw)
            print(f"   {label:32s} Q={r['Q_m3h']:7.2f} m3/h  ESP={r['ESP_kW']:7.1f} kW  ESP_in={r['ESP_in_bar']:7.2f} bar"
                  f"  inj_Pwh={r['inj_Pwh_bar']:8.3f} bar  inj_pump={r['inj_pump_kW']:7.1f} kW")
        except Exception as e:  # noqa
            print(f"   {label:32s} EXCEPTION {type(e).__name__}: {e}")

print()
print("=== D2. Friction dp over the example wells at their solved flow, k=0.01 m vs 4.5e-5 m")
for name in ("doublet_plant.json", "parallel_hex_plant.json"):
    proj = projects[name]
    q = run_project(proj)["Q_m3h"]
    from gemini_simulator.well_flow import _resolve_trajectory_segments
    for w in ("producer_well", "injector_well"):
        segs = _resolve_trajectory_segments(proj["components"][w]["parameters"])
        out = []
        for k in (0.01, 4.5e-5):
            d = _build_dpdt(segs, roughness=k)
            d.calculate_output({"pressure": 10e5, "temperature": 353.15, "temperature_ambient": 353.15,
                                "flowrate": q / 3600, "direction": "down"}, None)
            out.append(d.get_output()["pressuredrop_fric_output"] / 1e5)
        print(f"   {name:24s} {w:14s} Q={q:6.1f} m3/h: dp_fric(k=0.01 m)={out[0]:6.2f} bar,"
              f" dp_fric(k=4.5e-5 m)={out[1]:5.2f} bar, ratio={out[0]/out[1]:.1f}x")

print()
print("=== E. Temperature along a 2500 m producer ('up' from bottomhole 90 C, ambient const 20 C, U=10 W/m2K hard-coded)")
for q in (50, 100, 150, 200):
    for ncell in (1, 25):
        y = dpdt(0.2, 2500, 4.5e-5, q / 3600, "up", p0=250e5, t0=273.15 + 90, ncell=ncell)
        # exact solution of m*cp*dT/dz = -U*pi*D*(T-Tamb)
        ua = 10 * math.pi * 0.2 * 2500
        mcp = q / 3600 * 1000 * 4217.4
        t_exact = 20 + 70 * math.exp(-ua / mcp)
        print(f"  Q={q:3d} m3/h ncell={ncell:2d}: T_wh={y['temperature_output']-273.15:6.2f} C"
              f" (exact exp. {t_exact:6.2f} C)")
y = dpdt(0.2, 2500, 4.5e-5, 5 / 3600, "up", p0=250e5, t0=273.15 + 90, ncell=1)
print(f"  low flow 5 m3/h, 1 cell: T_wh={y['temperature_output']-273.15:.1f} C  (below 20 C ambient => explicit-Euler overshoot)")
