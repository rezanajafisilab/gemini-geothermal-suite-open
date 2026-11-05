"""ESP affinity-law check.

Affinity laws: Q2 = Q1*(f2/f1), H2 = H1*(f2/f1)^2, P2 = P1*(f2/f1)^3, so the head at
flow Q and frequency f is H(Q,f) = (f/60)^2 * H60(Q*60/f). gemini_model.pump.esp
evaluates (f/60)^2 * H60(Q) (no flow rescaling), see esp.py:303-321. Consequence:
at fixed Q, efficiency scales like 60/f (exceeds 100% at low frequency).

  python 06_esp_affinity.py <tree>
"""

import copy
import json
import sys
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE / "src"))

from gemini_model.pump.esp import ESP  # noqa: E402
from gemini_simulator.well_components import ProducerWell  # noqa: E402

proj = json.loads((TREE / "simulator_examples/projects/doublet_plant.json").read_text())
base = proj["components"]["producer_well"]["parameters"]

orig_head, orig_power = ESP.head_function, ESP.power_function


def head_affine(self, pump_flow, freq):
    return orig_head(self, pump_flow * 60.0 / freq, freq)


def power_affine(self, pump_flow, freq):
    return orig_power(self, pump_flow * 60.0 / freq, freq)


esp = ESP()
esp.update_parameters(base["esp"])
print("Efficiency at the 60 Hz best-efficiency flow (code as-is):")
for f in (40, 50, 60, 70):
    esp.calculate_output({"pump_freq": f, "pump_flow": 200 / 3600})
    print(f"  f={f} Hz, Q=200 m3/h: eff={esp.get_output()['pump_eff']:.1f} %")

print()
print("Producer nodal solve (doublet_plant.json, Pwh=3 bar), code vs affinity-correct ESP:")
print("  f Hz | Q_code m3/h  P_code kW | Q_affine m3/h  P_affine kW | dQ %   dP %")
for f in (40, 45, 50, 55, 60, 65, 70):
    res = []
    for patched in (False, True):
        ESP.head_function = head_affine if patched else orig_head
        ESP.power_function = power_affine if patched else orig_power
        p = copy.deepcopy(base)
        p["esp_freq_hz"] = f
        w = ProducerWell()
        w.update_parameters(p)
        try:
            w.calculate_output({"wellhead_pressure": 3.0, "wellhead_temperature": 80.0})
            res.append((w.output["flow_rate"], w.output["esp_power_el"] / 1e3))
        except Exception as e:  # noqa
            res.append((float("nan"), float("nan")))
    ESP.head_function, ESP.power_function = orig_head, orig_power
    (qa, pa), (qb, pb) = res
    print(f"  {f:3d}  | {qa:9.1f}  {pa:9.1f} | {qb:11.1f}  {pb:11.1f} | {100*(qa-qb)/qb:+6.1f} {100*(pa-pb)/pb:+6.1f}")
