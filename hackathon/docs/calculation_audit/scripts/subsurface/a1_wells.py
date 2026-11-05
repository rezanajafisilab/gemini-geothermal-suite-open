"""Hand physics vs the code: reservoir, PI, ESP, injection, Ramey, bubble point, breakthrough."""
import math

import dioscuri_plant as dp
from dioscuri_plant import doublet as D
from dioscuri_plant import subsurface as S
from gemini_agent.tools import gemini as G

R = dp.Rules()
g = 9.81
rho, mu, cp = 1030.0, 0.4e-3, 3990.0


def hand_pi(h=100.0, k_md=200.0, re=500.0, rw=0.2159 / 2):
    kh = k_md * 9.869233e-16 * h
    return 2 * math.pi * kh / (mu * (math.log(re / rw) - 0.75)) * 3600 * 1e5


def hand_pres(z):
    if abs(z - 2500) <= 50:
        return 250 + rho * g * (z - 2500) / 1e5
    return rho * g * z / 1e5


def hand_fric(q, L, f=0.015, d=0.2159):
    v = q / 3600 / (math.pi * d * d / 4)
    return f * L / d * rho * v * v / 2 / 1e5


def colebrook(q, d=0.2159, eps=4.5e-5):
    v = q / 3600 / (math.pi * d * d / 4)
    re = rho * v * d / mu
    f = 0.02
    for _ in range(50):
        f = (-2 * math.log10(eps / d / 3.7 + 2.51 / (re * math.sqrt(f)))) ** -2
    return f, re


def hand_ramey(q, L, days=365.0):
    w = q / 3600 * rho * cp
    f = math.log(2 * math.sqrt(1e-6 * days * 86400) / 0.156) - 0.29
    A = w / (2 * math.pi) * (1 / (0.10795 * 30) + f / 2.5)
    gg = 0.03
    return gg * L - gg * A * (1 - math.exp(-L / A))


print("== reservoir T and p ==")
for z in (2450, 2500, 2550, 2551, 3000, 3500):
    print(z, "T", R.reservoir_temperature_c(z), "hand", 12 + 30 * z / 1000,
          "p", round(D.reservoir_pressure_bar(z, R), 3), "hand", round(hand_pres(z), 3))

print("== PI ==", D.productivity_index_m3h_per_bar(R), "hand", hand_pi(),
      "half-open", D.productivity_index_m3h_per_bar(R, 50.0), hand_pi(50))
# Steady dipole (source-sink pair at spacing L): each well sees ln(L/rw)
kh = 200 * 9.869233e-16 * 100
pi_dipole = 2 * math.pi * kh / (mu * math.log(1500 / 0.10795)) * 3.6e8
print("PI dipole ln(L/rw)", pi_dipole)

print("== friction ==")
for q in (50, 150, 300):
    f, re = colebrook(q)
    print(q, "code", round(D.friction_bar(q, 2500, R), 3), "colebrook f", round(f, 4), "Re", round(re),
          "fric(f)", round(hand_fric(q, 2500, f), 3))

print("== Ramey loss ==")
for q in (50, 150, 300):
    print(q, round(D.well_loss_k(q, 2500, R), 3), "hand", round(hand_ramey(q, 2500), 3))

print("== doublet points: GEMINI fixed vs stub vs hand ==")
for z in (2500, 3000, 3500):
    for q in (50, 150, 300):
        gp = G.doublet_point(q, z, R)
        sp = D.stub_doublet(q, z, rules=R)
        pi = hand_pi()
        pres = hand_pres(z)
        col = rho * g * z / 1e5
        fr = hand_fric(q, z)
        head = 5 + col + fr - (pres - q / pi)
        inj = pres + q / pi + fr - col
        print(f"z={z} q={q}: twh G {gp['wellhead_c']:.2f} hand {12+0.03*z-hand_ramey(q,z):.2f} | "
              f"ESP head G {gp['esp_head_bar']:.2f} stub {sp['esp_head_bar']:.2f} hand {head:.2f} | "
              f"ESP MW G {gp['esp_mw']:.4f} hand {head*1e5*q/3600/0.7/1e6:.4f} | "
              f"inj whp G {gp['injection_wellhead_bar']:.2f} stub {sp['injection_wellhead_bar']:.2f} hand {inj:.2f} | "
              f"inj MW G {gp['injector_pump_mw']:.4f} hand(4 bar) {max(inj-4,0)*1e5*q/3600/0.7/1e6:.4f} stub {sp['injector_pump_mw']:.4f}")

print("== bubble point and ESP setting ==")
for t in (60, 80, 86.1, 100, 116):
    print(t, "pb", round(S.bubble_point_bar(t, R), 2), "pv", round(S.water_vapour_bar(t), 3),
          "kH CH4 GPa", round(S.henry_pa("ch4", t) / 1e9, 3), "kH CO2 GPa", round(S.henry_pa("co2", t) / 1e9, 3))
pi = D.productivity_index_m3h_per_bar(R)
for z in (2500, 3000, 3500):
    twh = R.reservoir_temperature_c(z) - D.well_loss_k(300, z, R)
    pb = S.bubble_point_bar(twh, R)
    s = S.esp_setting_m(300, z, pi, pb, R)
    per_m = rho * g / 1e5 + hand_fric(300, 1.0)
    hand = z - (hand_pres(z) - 300 / pi - (pb - 1 + 5)) / per_m
    print(z, "twh", round(twh, 2), "pb", round(pb, 2), "setting", round(s, 1), "hand", round(hand, 1),
          "gemini esp depth", G.esp_depth(z, 300, R))

print("== breakthrough ==")
for q, n in ((300, 1), (200.8, 1), (300, 2)):
    t = S.breakthrough_years(q, n, R)
    rcw = rho * cp
    rca = 0.2 * rcw + 0.8 * 2.25e6
    hand = math.pi / 3 * rca * 100 * 1500 ** 2 / (rcw * q / n / 3600) / (365.25 * 86400)
    print(q, n, round(t, 2), "hand", round(hand, 2))

print("== SodM ==")
top = 2450
inj = D.reservoir_pressure_bar(top, R) + 300 / pi
print("inj at top", round(inj, 2), "limit", 0.135 * top)
print("max_flow", S.max_flow_m3h(dp.Doublet(), R, 2500, pi, pi, 86.1))

print("== brine MW/K ==", float(R.brine_mw_per_k(300)), "hand", 300 / 3600 * rho * cp / 1e6,
      "x40 =", float(R.brine_mw_per_k(300)) * 40)
