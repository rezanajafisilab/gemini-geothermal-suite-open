"""Pump electricity of a year by hand at each day's flow; the flash at the separator."""
import math

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant import subsurface as S
from gemini_agent import engine
from gemini_agent.contract import DesignBrief

R = engine.rules_for(DesignBrief())
demand = engine.demand_of(DesignBrief())
model = engine.doublet_model(R)
rho, g = 1030.0, 9.81
PI = 14.513091


def fric(q, L=2500.0):
    v = q / 3600 / (math.pi * 0.2159 ** 2 / 4)
    return 0.015 * L / 0.2159 * rho * v * v / 2 / 1e5


for plant in (dp.Plant(1, heat_pump_mw=3.0, boiler_mw=30.0, chiller_mw=12.0),
              dp.Plant(2, doublet_specs=(dp.Doublet(injectors=2), dp.Doublet()), heat_pump_mw=4.0,
                       boiler_mw=30.0, chiller_mw=12.0)):
    y = dp.simulate_year(plant, demand, model, R)
    tot = 0.0
    for d, spec in zip(y.doublets, plant.specs()):
        for q in d["flow_m3h"]:
            if q <= 0:
                continue
            head = 5 + rho * g * 2500 / 1e5 + fric(q) - (250 - q / PI)
            qi = q / spec.injectors
            inj = max(250 + qi / PI + fric(qi) - rho * g * 2500 / 1e5 - 4.0, 0.0)
            tot += (head * q + spec.injectors * inj * qi) * 1e5 / 3600 / 0.7 / 1e6 * 24 / 1000
    print(plant.n_doublets, "doublets: year pumps", y.electricity_gwh["pumps"], "hand", round(tot, 3))

# Flash at the separator (5 bar(g), wellhead temperature 86.1 C) with the code's Henry constants.
T = 86.1
P = (5.0 + 1.01325) * 1e5
water = 1030 / 1.041 / 0.018015
n = {"ch4": 0.8 * 0.8 / 0.022414, "co2": 0.8 * 0.2 / 0.022414}
k = {gs: S.henry_pa(gs, T) * 10 ** (S.SETSCHENOW[gs] * S.SALINITY_MOL_KG) for gs in n}
yw = S.water_vapour_bar(T) * 1e5 / P
lo, hi = 1e-9, 1e3
for _ in range(200):
    V = 0.5 * (lo + hi)
    s = sum(n[gs] / (V + water * P / k[gs]) for gs in n)
    if s > 1 - yw:
        lo = V
    else:
        hi = V
V = 0.5 * (lo + hi)
for gs in n:
    gas = n[gs] / (V + water * P / k[gs]) * V
    print(gs, "freed at the separator", round(gas / n[gs], 3))
