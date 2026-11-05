"""Brine density is not configurable in the simulator's well path: well_flow._build_dpdt
always attaches PVTConstantSTP() (rho=1000 kg/m3, mu=1e-3 Pa.s). Quantify the effect for a
2500 m doublet whose reservoir pressure is hydrostatic for a 1080 kg/m3 brine.

  python 12_brine_density.py <tree>
"""
import json, sys
from pathlib import Path
TREE = Path(sys.argv[1]); sys.path.insert(0, str(TREE / "src"))
from gemini_model.fluid import pvt_water_stp as pvt
from gemini_simulator.well_flow import solve_primary_flow_m3h, producer_esp_power_w, solve_injector_wellhead_pressure_bar

base = json.loads((TREE / "simulator_examples/projects/doublet_plant.json").read_text())["components"]
traj = [{"MD": 0, "TVD": 0, "ID": 0.2}, {"MD": 2500, "TVD": 2500, "ID": 0.2}]
rho_b = 1080.0
pres = 1.0 + rho_b * 9.81 * 2500 / 1e5
prod = dict(base["producer_well"]["parameters"], trajectory_table=traj, reservoir_pressure_bar=pres,
            productivity_index_m3h_per_bar=15.0, roughness_m=4.5e-5)
for k in ("esp", "esp_depth_m", "esp_freq_hz"):
    prod.pop(k)  # natural flow (no ESP) isolates the hydrostatic effect
inj = dict(base["injector_well"]["parameters"], trajectory_table=traj, reservoir_pressure_bar=pres,
           productivity_index_m3h_per_bar=15.0, roughness_m=4.5e-5)
orig_init = pvt.PVTConstantSTP.__init__
for rho in (1000.0, rho_b):
    def init(self, _rho=rho):
        orig_init(self)
        self.parameters["RHOL"] = _rho
    pvt.PVTConstantSTP.__init__ = init
    try:
        q = solve_primary_flow_m3h(prod, 3.0, 80.0)
    except ValueError:
        q = 0.0  # no natural flow
    pinj = solve_injector_wellhead_pressure_bar(inj, 150.0, 40.0)
    print(f"well-model density {rho:.0f} kg/m3 (reservoir hydrostatic for {rho_b:.0f}, p_res={pres:.1f} bar):"
          f" producer natural-flow Q={q:.1f} m3/h at Pwh=3 bar;"
          f" injector Pwh at 150 m3/h = {pinj:.2f} bar")
pvt.PVTConstantSTP.__init__ = orig_init
