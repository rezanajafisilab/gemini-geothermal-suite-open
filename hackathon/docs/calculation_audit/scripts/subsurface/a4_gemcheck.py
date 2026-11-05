"""The GEMINI check's plant-side figures for two-injector doublets and for another aquifer."""
from dataclasses import replace

import dioscuri_plant as dp
from dioscuri_plant.types import open_interval
from dioscuri_plant import doublet as D
from gemini_agent import workbench
from gemini_agent.tools import gemini as G

R = dp.Rules()


def compare(doublets, rules):
    proj = G.plant_project(doublets, rules, 10.0)
    res = workbench.run_gemini(proj)
    out = res["outputs"]
    print("ok", res["ok"], res.get("error"), res["warnings"])
    specs = [dp.Doublet(depth_m=float(d.get("depth_m", 2500.0)), injectors=int(d.get("injectors", 1)),
                        producer_open=d.get("producer_open", "full")) for d in doublets]
    many = len(specs) > 1
    for i, d in enumerate(specs):
        sfx = f"_{i + 1}" if many else ""
        cap = d.cap_m3h(rules)
        # as engine.gemini_check does it
        point = G.doublet_point(cap, d.depth_m, rules, "fixed")
        # as the year model does it
        here = rules.aquifer_at(d.depth_m)
        p_mid, p_len = open_interval(d.depth_m, d.producer_open, here.reservoir_thickness_m)
        model = G.doublet_model(rules)
        prod = model(cap, p_mid, None if p_len == here.reservoir_thickness_m else p_len)
        inj = model(cap / d.injectors, d.depth_m)
        gem_esp = float(out.get(f"producer_well{sfx}", {}).get("esp_power_el", 0)) / 1e6
        gem_inj = sum(float(v.get("power_el") or 0) / 1e6 for k, v in out.items() if k.startswith(f"injector_well{sfx}"))
        injs = [k for k in out if k.startswith(f"injector_well{sfx}")]
        print(f" doublet {i+1}: GEMINI ESP {gem_esp:.4f} | check's plant {point['esp_mw']:.4f} | year model {prod['esp_mw']:.4f}")
        print(f"   GEMINI inj {gem_inj:.4f} | check's plant {point['injector_pump_mw'] * d.injectors:.4f} | "
              f"year model {inj['injector_pump_mw'] * d.injectors:.4f}")
        print(f"   inj whp GEMINI {[round(out[k].get('wellhead_pressure', 0), 2) for k in injs]} | check's plant "
              f"{point['injection_wellhead_bar']:.2f} | year model {inj['injection_wellhead_bar']:.2f}")
    hx = out.get("heat_exchanger", {})
    print(" HEX duty GEMINI", hx.get("heat_duty", 0) / 1e6, "brine out", hx.get("primary_temperature_out"))


print("== two injectors ==")
compare([{"injectors": 2}], R)
print("== another aquifer: 3,100 m, 400 mD, 330 bar ==")
r2 = replace(R, other_aquifers=(dp.Aquifer(3100.0, 80.0, 400.0, 330.0, 1.2),))
compare([{"depth_m": 3100.0}], r2)
print("== plain ==")
compare([{}], R)
