"""A doublet model in plain physics, for tests and for checks against GEMINI's well solve.

The agent uses GEMINI's well solve (``gemini_agent.tools.gemini.doublet_model``); this one
needs only the challenge's inputs and textbook formulas, so a hand calculation can follow it:

- reservoir temperature from the gradient, less the heat lost up the well (Ramey 1962, the
  rock warmed for a year: about 1 K at 300 m3/h, 5 K at 50 m3/h);
- reservoir pressure 250 bar(g) at 2,500 m and the brine's hydrostatic gradient across the
  aquifer's 100 m; hydrostatic at other depths (an assumed aquifer);
- productivity index from k·h for a doublet at steady state (a producer and an injector at the
  well spacing L: each well sees ``Q mu / (2 pi k h) ln(L / r_w)``, no skin), where h is the
  open part of the well (the whole aquifer, or half of it);
- ESP head = wellhead pressure + brine column + friction - (reservoir pressure - drawdown);
- injection pressure = reservoir pressure + build-up + friction - brine column, boosted from
  the surface plant's outlet (``RETURN_BAR``, as GEMINI's path);
- both pumps at the challenge's 70 % hydraulic efficiency.
"""

from __future__ import annotations

import math
from typing import Optional

from dioscuri_plant.types import Rules

G = 9.81
WELL_ID_M = 0.2159  # 8.5 in production casing
# The separator's pressure at the producer's wellhead. The dissolved gas (0.8 Nm3/m3) comes out
# of solution below roughly 40-45 bar, so in the upper few hundred metres of the producer and in
# the separator; that flash is not modelled (all the gas is taken as separated).
WELLHEAD_BAR = 5.0
# The brine at the injection pump's inlet, after the surface plant (gemini_agent.tools.gemini).
RETURN_BAR = 4.0
FRICTION_FACTOR = 0.015  # Darcy, turbulent flow in steel tubing
# Heat lost up the producer (Ramey 1962): the rock around the well warms up over the first
# months, so the loss falls with time and with flow. Rock conductivity and diffusivity are
# typical sedimentary values; the casing-cement conductance and the hole size are a 12.25 in
# hole with an 8.5 in casing. One year of production is the base case (ADR-0008, with Ali).
ROCK_K_W_MK = 2.5
ROCK_ALPHA_M2_S = 1.0e-6
HOLE_RADIUS_M = 0.156
CASING_U_W_M2K = 30.0
PRODUCTION_DAYS = 365.0


def productivity_index_m3h_per_bar(rules: Rules = Rules(), open_m: Optional[float] = None) -> float:
    """Return the productivity (and injectivity) index from k·h, m3/h/bar.

    A doublet at steady state: the producer's sink and the injector's source, ``L`` apart
    (``rules.well_spacing_m``), give each well a pressure change of
    ``Q mu / (2 pi k h) ln(L / r_w)`` (superposition; the far field stays at the reservoir
    pressure), so the index is ``2 pi k h / (mu ln(L / r_w))``: 11.7 m3/h/bar for the
    challenge's aquifer at 1,500 m. No skin. ``open_m`` is the length of the well open to the
    aquifer (its whole thickness by default); a well open over half the aquifer has half the
    index (no partial-penetration skin).
    """
    h = rules.reservoir_thickness_m if open_m is None else min(open_m, rules.reservoir_thickness_m)
    kh = rules.permeability_md * 9.869e-16 * h  # m3
    spacing = max(float(rules.well_spacing_m), 10.0)
    pi = 2 * math.pi * kh / (rules.brine_viscosity_pa_s * math.log(spacing / (WELL_ID_M / 2)))
    return pi * 3600 * 1e5  # m3/(s Pa) -> m3/(h bar)


def reservoir_pressure_bar(depth_m: float, rules: Rules = Rules()) -> float:
    """Return the reservoir pressure at a depth (TVD), bar.

    In the known aquifer (its midpoint +- half its thickness): the requirements' value at the
    midpoint plus the brine's hydrostatic gradient. Elsewhere (an assumed aquifer): hydrostatic,
    as the requirements say for other depths.
    """
    offset = depth_m - rules.reservoir_depth_m
    if abs(offset) <= rules.reservoir_thickness_m / 2 + 1e-6:
        return rules.reservoir_pressure_bar + rules.brine_density_kg_m3 * G * offset / 1e5
    return rules.brine_density_kg_m3 * G * depth_m / 1e5


def friction_bar(flow_m3h: float, depth_m: float, rules: Rules = Rules()) -> float:
    """Return the Darcy-Weisbach friction loss along the well at a flow, bar."""
    area = math.pi * WELL_ID_M**2 / 4
    v = flow_m3h / 3600 / area
    return FRICTION_FACTOR * depth_m / WELL_ID_M * rules.brine_density_kg_m3 * v**2 / 2 / 1e5


def well_loss_k(
    flow_m3h: float, depth_m: float, rules: Rules = Rules(), days: float = PRODUCTION_DAYS
) -> float:
    """Return the temperature the brine loses on its way up a producer, K (Ramey 1962).

    With the rock's time function ``f(t) = ln(2 sqrt(alpha t) / r_hole) - 0.29`` and
    ``A = w cp / (2 pi) (1 / (r_casing U) + f / k_rock)``, the wellhead temperature is
    ``T_res - g L + g A (1 - exp(-L / A))``; the loss is what the gradient would give minus that.
    At 2,500 m after a year: about 0.9 K at 300 m3/h, 1.8 K at 150 and 5 K at 50 m3/h.

    Parameters
    ----------
    flow_m3h : float
        Brine flow up the well.
    depth_m : float
        Reservoir depth (the well's length, vertical well).
    rules : Rules
        Brine density and heat capacity, the geothermal gradient.
    days : float
        Production time; the rock warms with the square root of it.

    Returns
    -------
    float
        Kelvin lost between the reservoir and the wellhead (0 at zero flow is not meaningful:
        the minimum flow of the rules is used below it).
    """
    q = max(float(flow_m3h), rules.flow_min_m3h) / 3600.0
    w_cp = q * rules.brine_density_kg_m3 * rules.brine_cp_j_kg_k
    f = math.log(2 * math.sqrt(ROCK_ALPHA_M2_S * days * 86400) / HOLE_RADIUS_M) - 0.29
    a = w_cp / (2 * math.pi) * (1 / (WELL_ID_M / 2 * CASING_U_W_M2K) + f / ROCK_K_W_MK)
    g = rules.gradient_c_per_km / 1000.0
    return g * depth_m - g * a * (1 - math.exp(-depth_m / a))


def stub_doublet(
    flow_m3h: float, depth_m: float, open_m: Optional[float] = None, rules: Rules = Rules()
) -> dict:
    """Return a doublet's operating point at a brine flow (plain physics, no GEMINI).

    ``depth_m`` is the middle of the wells' open part, ``open_m`` its length (the aquifer's
    thickness by default).

    Returns
    -------
    dict
        ``wellhead_c``, ``esp_mw``, ``injector_pump_mw``, ``esp_head_bar``,
        ``injection_wellhead_bar``, ``gas_nm3h``, ``pi_m3h_per_bar``.
    """
    pi = productivity_index_m3h_per_bar(rules, open_m)
    p_res = reservoir_pressure_bar(depth_m, rules)
    column = rules.brine_density_kg_m3 * G * depth_m / 1e5
    fric = friction_bar(flow_m3h, depth_m, rules)
    head = max(0.0, WELLHEAD_BAR + column + fric - (p_res - flow_m3h / pi))
    inj = max(0.0, p_res + flow_m3h / pi + fric - column)
    to_mw = flow_m3h / 3600 * 1e5 / rules.pump_efficiency / 1e6  # bar -> MW at this flow
    return {
        "wellhead_c": rules.reservoir_temperature_c(depth_m)
        - well_loss_k(flow_m3h, depth_m, rules),
        "well_loss_k": well_loss_k(flow_m3h, depth_m, rules),
        "esp_mw": head * to_mw,
        "injector_pump_mw": max(0.0, inj - RETURN_BAR) * to_mw,
        "esp_head_bar": head,
        "injection_wellhead_bar": inj,
        "gas_nm3h": flow_m3h * rules.gas_liquid_ratio,
        "pi_m3h_per_bar": pi,
    }
