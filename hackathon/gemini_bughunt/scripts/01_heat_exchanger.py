"""HeatExchanger physics checks: effectiveness <= 1, energy balance, no temperature
cross, and direction of heat flow when the secondary inlet is the hotter stream
(cooling / heat-rejection use, or a district-heating return hotter than a cooled
geothermal primary).

  PYTHONPATH=<tree>/src python 01_heat_exchanger.py
"""

import itertools
import math

from gemini_model.heat_exchanger.heat_exchanger import HeatExchanger

RHO, CP = 1050.0, 4200.0


def run(cfg, ua, tp, ts, qp_m3h, qs_m3h):
    hx = HeatExchanger()
    hx.update_parameters(
        {"flow_resistance": 0.0, "flow_configuration": cfg, "heat_transfer_coefficient": ua}
    )
    hx.calculate_output(
        {
            "pressure_in": 5.0,
            "primary_temperature_in": tp,
            "secondary_temperature_in": ts,
            "primary_flow_rate": qp_m3h / 3600,
            "secondary_flow_rate": qs_m3h / 3600,
        }
    )
    return hx.get_output()


print("=== 1. Sweep (primary hotter than secondary, normal heating duty)")
viol = []
n = 0
for cfg, ua, tp, ts, qp, qs in itertools.product(
    ("counter", "parallel"),
    (1e3, 5e4, 2.5e5, 1e6, 1e8),
    (40.0, 80.0, 120.0),
    (10.0, 30.0),
    (10.0, 150.0),
    (1.0, 50.0, 149.999999, 150.0, 300.0),
):
    y = run(cfg, ua, tp, ts, qp, qs)
    n += 1
    cp_ = RHO * CP * qp / 3600
    cs_ = RHO * CP * qs / 3600
    q = y["heat_duty"]
    qmax = min(cp_, cs_) * (tp - ts)
    eps = q / qmax
    bal = cp_ * (tp - y["primary_temperature_out"]) - cs_ * (y["secondary_temperature_out"] - ts)
    cross = (
        cfg == "parallel" and y["secondary_temperature_out"] > y["primary_temperature_out"] + 1e-6
    ) or (y["secondary_temperature_out"] > tp + 1e-6) or (y["primary_temperature_out"] < ts - 1e-6)
    if eps > 1 + 1e-9 or eps < -1e-12 or abs(bal) > 1e-6 * max(1, q) or cross:
        viol.append((cfg, ua, tp, ts, qp, qs, eps, bal, y))
print(f"cases={n}, violations={len(viol)}")
for v in viol[:5]:
    print("  VIOLATION", v[:8])

print()
print("=== 2. Near-balanced counter-flow (Cr -> 1) continuity check")
for qs in (149.0, 149.99, 149.9999, 150.0, 150.0001, 150.01):
    y = run("counter", 2.5e5, 80.0, 20.0, 150.0, qs)
    print(f"  Qs={qs:<9} eps={y['heat_duty']/(min(150, qs)/3600*RHO*CP*60):.6f}  Q={y['heat_duty']/1e6:.4f} MW")

print()
print("=== 3. Secondary inlet HOTTER than primary inlet (e.g. cooling / heat rejection)")
print("    expected: heat flows from secondary (hot) to primary (cold):")
print("    primary_out > primary_in, secondary_out < secondary_in")
for cfg in ("counter", "parallel"):
    tp, ts = 20.0, 60.0
    y = run(cfg, 2.5e5, tp, ts, 150.0, 150.0)
    print(
        f"  {cfg:8s}: Tp_in={tp} -> Tp_out={y['primary_temperature_out']:.2f} C;"
        f"  Ts_in={ts} -> Ts_out={y['secondary_temperature_out']:.2f} C;"
        f"  heat_duty={y['heat_duty']/1e6:.3f} MW"
    )
# district cooling flavour: chilled water primary 6 C, building return secondary 16 C
y = run("counter", 2.5e5, 6.0, 16.0, 100.0, 100.0)
print(
    f"  cooling case: chilled primary 6 C -> {y['primary_temperature_out']:.2f} C,"
    f" building return 16 C -> {y['secondary_temperature_out']:.2f} C  (should be ~>6 and <16)"
)
