"""Subsurface checks per doublet: cold water at the producer, gas at the ESP, injection pressure.

Three checks the year model does not make by itself, each from textbook formulas and the
challenge's inputs (the assumed values are named here and in ``Rules``):

1. **Thermal breakthrough.** The cooled brine spreads from the injector and reaches the
   producer after ``t = pi/3 (rho c)_aq H L^2 / ((rho c)_w Q)`` (Gringarten & Sauty 1975,
   J. Geophys. Res. 80(35), 4956-4962: a single doublet in a confined aquifer, no heat from
   the rocks above and below, so on the early side). ``Q`` is the brine one injector takes,
   averaged over the year; ``H`` the aquifer's thickness, ``L`` the well spacing. It should
   come after the doublet's 30-year life (PBL, SDE++ 2026). Neighbouring doublets' plumes are
   not in it.
2. **Gas at the ESP.** The brine holds 0.8 Nm3 of gas per m3 (80 % CH4, 20 % CO2) in solution
   down there; below the bubble point it comes out, and free gas at the ESP's intake damages
   it. The bubble point is Henry's law at the wellhead temperature (IAPWS G7-04 Henry
   constants, salted out by the brine's NaCl, Setschenow, at 0.85 mol/kg): about 43 bar at
   86 °C. The ESP is set deep enough that its intake stays 5 bar above that at the doublet's
   highest flow:
   ``z = mid - (p_res - Q/PI - p_bubble) / (rho g + friction per m)``. Dutch doublets set
   their ESPs at about 800 m (Oil Dynamics, 300 m3/h at 90 °C, 2020); deeper than
   ``ESP_MAX_SETTING_M`` needs a longer pump chamber than we allow.
3. **Injection pressure.** SodM's guideline value for the fluid pressure at the top of the
   reservoir is 0.135 bar per metre of depth (SodM, "Protocol bepaling maximale
   injectiedrukken bij aardwarmtewinning", version 2, quoted in TNO note AGE 15-10.072,
   2015): the lowest expected horizontal stress in the seals, with a thermal correction and a
   margin. The injector's pressure there is the reservoir's plus ``Q/II`` at its highest flow.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from dioscuri_plant.doublet import G, friction_bar, reservoir_pressure_bar
from dioscuri_plant.types import Doublet, Rules

LIFE_YEARS = 30  # PBL, SDE++ 2026: technical lifetime of a doublet
ROCK_RHO_C_J_M3K = 2.25e6  # sandstone grains: 2,650 kg/m3 x 850 J/(kg K)
SODM_BAR_PER_M = 0.135
ESP_MAX_SETTING_M = 1000.0  # our limit for the pump chamber; Dutch practice about 800 m
NM3_MOL = 0.022414  # m3 of gas per mol at 0 °C and 1 atm
WATER_MOL_KG = 1 / 0.018015
# NaCl molality that gives the brine's 1,030 kg/m3 at surface conditions (Batzle & Wang 1992:
# about 0.85 mol/kg); more salt holds less gas, so the bubble point is higher.
SALINITY_MOL_KG = 0.85
# The ESP's intake is kept this far above the bubble point (pump vendors' practice: free gas
# starts before the bubble point is reached at the intake's own turbulence).
ESP_MARGIN_BAR = 5.0
# IAPWS G7-04 (2004): ln(kH / p_w) = A/Tr + B tau^0.355 / Tr + C Tr^-0.41 exp(tau).
HENRY = {"ch4": (-10.44708, 4.66491, 12.12986), "co2": (-8.55445, 4.01195, 9.52345)}
SETSCHENOW = {"ch4": 0.12, "co2": 0.10}  # kg/mol, log10: solubility / 10^(k m) in NaCl brine
T_CRIT_K = 647.096


def water_vapour_bar(t_c: float) -> float:
    """Return water's vapour pressure, bar (Antoine, NIST constants, 1-150 °C)."""
    a, b, c = (8.07131, 1730.63, 233.426) if t_c <= 100 else (8.14019, 1810.94, 244.485)
    return 10 ** (a - b / (c + t_c)) * 133.322 / 1e5


def henry_pa(gas: str, t_c: float) -> float:
    """Return a gas's Henry constant in water, Pa per mole fraction (IAPWS G7-04)."""
    a, b, c = HENRY[gas]
    tr = (t_c + 273.15) / T_CRIT_K
    tau = 1 - tr
    ln = a / tr + b * tau**0.355 / tr + c * tr**-0.41 * math.exp(tau)
    return math.exp(ln) * water_vapour_bar(t_c) * 1e5


def bubble_point_bar(t_c: float, rules: Rules = Rules()) -> float:
    """Return the pressure below which the brine's gas comes out of solution, bar (absolute).

    Each gas's partial pressure is what keeps its share dissolved (Henry's law, less soluble in
    brine than in water); the bubble point is their sum plus water's vapour pressure.
    """
    water_kg = rules.brine_density_kg_m3 / (1 + 0.041)  # kg of water per m3 of brine
    water_mol = water_kg * WATER_MOL_KG
    total = 0.0
    for gas, share in (("ch4", rules.gas_ch4_fraction), ("co2", rules.gas_co2_fraction)):
        mol = rules.gas_liquid_ratio * share / NM3_MOL  # per m3 of brine
        salted = 10 ** (SETSCHENOW[gas] * SALINITY_MOL_KG)
        total += mol / water_mol * henry_pa(gas, t_c) * salted
    return total / 1e5 + water_vapour_bar(t_c)


def breakthrough_years(flow_m3h: float, injectors: int, rules: Rules = Rules()) -> Optional[float]:
    """Return the years until the cooled brine reaches the producer (Gringarten & Sauty 1975)."""
    q = flow_m3h / max(injectors, 1) / 3600.0
    if q <= 0:
        return None
    water = rules.brine_density_kg_m3 * rules.brine_cp_j_kg_k
    aquifer = rules.porosity * water + (1 - rules.porosity) * ROCK_RHO_C_J_M3K
    seconds = math.pi / 3 * aquifer * rules.reservoir_thickness_m * rules.well_spacing_m**2
    return seconds / (water * q) / (365.25 * 86400)


def esp_setting_m(
    flow_m3h: float, mid_m: float, pi_m3h_bar: float, bubble_bar: float, rules: Rules = Rules()
) -> float:
    """Return the shallowest ESP setting depth that keeps its intake above the bubble point, m.

    Pressures are gauge (the challenge's 250 bar(g)); the bubble point is absolute, so 1 bar
    comes off it.
    """
    drawdown = flow_m3h / max(pi_m3h_bar, 1e-9)
    above = reservoir_pressure_bar(mid_m, rules) - drawdown - (bubble_bar - 1.0 + ESP_MARGIN_BAR)
    per_m = rules.brine_density_kg_m3 * G / 1e5 + friction_bar(flow_m3h, 1.0, rules)
    return max(mid_m - above / per_m, 0.0)


def check(
    spec: Doublet,
    rules: Rules,
    producer_mid_m: float,
    pi_m3h_bar: float,
    injectivity_m3h_bar: float,
    wellhead_c: float,
    max_flow_m3h: float,
    mean_flow_m3h: float,
) -> Dict[str, object]:
    """Return one doublet's subsurface checks (see the module's notes).

    Parameters
    ----------
    spec : Doublet
        Its set-up (injectors, open parts).
    rules : Rules
        The reservoir, the brine, the spacing and porosity.
    producer_mid_m : float
        The middle of the producer's open part, m TVD.
    pi_m3h_bar, injectivity_m3h_bar : float
        Productivity and injectivity of the doublet's wells (one injector's).
    wellhead_c : float
        The brine's temperature at the ESP (its wellhead temperature).
    max_flow_m3h, mean_flow_m3h : float
        The doublet's highest daily flow and its flow averaged over the year (0 when idle).

    Returns
    -------
    dict
        ``breakthrough_years``, ``bubble_point_bar``, ``esp_setting_m``,
        ``injection_top_bar``, ``injection_limit_bar``, and ``problems`` (sentences).
    """
    top = rules.reservoir_depth_m - rules.reservoir_thickness_m / 2
    if abs(spec.depth_m - rules.reservoir_depth_m) > rules.reservoir_thickness_m / 2:
        top = spec.depth_m - rules.reservoir_thickness_m / 2  # an assumed aquifer
    years = breakthrough_years(mean_flow_m3h, spec.injectors, rules)
    bubble = bubble_point_bar(wellhead_c, rules)
    setting = esp_setting_m(max_flow_m3h, producer_mid_m, pi_m3h_bar, bubble, rules)
    per_injector = max_flow_m3h / spec.injectors
    injection = reservoir_pressure_bar(top, rules) + per_injector / max(injectivity_m3h_bar, 1e-9)
    limit = SODM_BAR_PER_M * top
    problems: List[str] = []
    if max_flow_m3h <= 0:
        return {"problems": problems}
    if years is not None and years < LIFE_YEARS:
        problems.append(
            f"cold water reaches the producer after {years:.0f} years, before its "
            f"{LIFE_YEARS}-year life"
        )
    if setting > ESP_MAX_SETTING_M:
        problems.append(
            f"the ESP must sit at {setting:,.0f} m to keep the gas in solution (bubble point "
            f"{bubble:.0f} bar), deeper than {ESP_MAX_SETTING_M:,.0f} m"
        )
    if injection > limit:
        problems.append(
            f"injection pressure at the top of the reservoir {injection:.0f} bar, above "
            f"SodM's {limit:.0f} bar (0.135 bar/m)"
        )
    return {
        "breakthrough_years": round(years, 1) if years is not None else None,
        "bubble_point_bar": round(bubble, 1),
        "esp_setting_m": round(setting, 0),
        "injection_top_bar": round(injection, 1),
        "injection_limit_bar": round(limit, 1),
        "problems": problems,
    }


def max_flow_m3h(
    spec: Doublet,
    rules: Rules,
    producer_mid_m: float,
    pi_m3h_bar: float,
    injectivity_m3h_bar: float,
    wellhead_c: float,
) -> float:
    """Return the highest flow a doublet can run at within the ESP and injection limits, m3/h.

    The injection limit is linear in the flow; the ESP's setting depth is found by halving (its
    friction term grows with the flow). The doublet's own cap bounds both.
    """
    cap = spec.cap_m3h(rules)
    top = rules.reservoir_depth_m - rules.reservoir_thickness_m / 2
    if abs(spec.depth_m - rules.reservoir_depth_m) > rules.reservoir_thickness_m / 2:
        top = spec.depth_m - rules.reservoir_thickness_m / 2
    room = SODM_BAR_PER_M * top - reservoir_pressure_bar(top, rules)
    q_inj = max(room, 0.0) * injectivity_m3h_bar * spec.injectors
    bubble = bubble_point_bar(wellhead_c, rules)

    def deep(q: float) -> bool:
        return esp_setting_m(q, producer_mid_m, pi_m3h_bar, bubble, rules) > ESP_MAX_SETTING_M

    lo, hi = 0.0, cap
    if deep(hi):
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if deep(mid) else (mid, hi)
        q_esp = lo
    else:
        q_esp = cap
    return min(cap, q_inj, q_esp)
