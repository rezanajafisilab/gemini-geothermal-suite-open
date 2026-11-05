"""The district network between the plant and the buildings: heat lost and gained on the way.

Off by default (``Rules.network_length_km`` = 0: the plant delivers to the buildings at its
gate). With a trunk of length L (km), supply and return each run in one pre-insulated steel pipe
buried in ground at ``Rules.ground_temperature_c``:

- the pipe is sized for the peak flow at ``DESIGN_VELOCITY_M_S`` (district-heating mains are
  designed for about 1.5-2.5 m/s), rounded up to a standard DN;
- each pipe loses U (W/m/K) times its length times (water - ground) temperature, with
  ``U = 0.20 + 0.0008 x DN`` W/m/K: a rule of thumb for series-2 pre-insulated single pipes
  (about 0.28 at DN100, 0.36 at DN200, 0.52 at DN400; assumed, from manufacturers' tables);
- the supply arrives colder by loss / (mass flow x cp): the plant supplies that much hotter so
  the buildings still get the supply temperature (at low summer flow the drop is largest; the
  flow never falls below ``MIN_FLOW_SHARE`` of the peak, a bypass keeps the line warm);
- the return arrives colder too, and the plant heats from there; the heat lost is extra load;
- pumping: ``FRICTION_PA_PER_M`` at the design flow in each pipe, scaling with the flow squared.

The cooling network has the same trunk: at 20/25 °C in ground at 10 °C it loses heat to the
ground, which helps (the chilled water arrives colder); the gain is negative load.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np

from dioscuri_plant.types import Rules

WATER_RHO = 965.0  # kg/m3 at about 80 °C
WATER_CP = 4186.0  # J/(kg K)
DESIGN_VELOCITY_M_S = 2.0
FRICTION_PA_PER_M = 100.0  # design pressure drop of a main (50-150 Pa/m)
MIN_FLOW_SHARE = 0.10
STANDARD_DN = (50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800)


def u_value(dn: int) -> float:
    """Return a series-2 pre-insulated single pipe's heat loss coefficient, W/(m K)."""
    return 0.20 + 0.0008 * dn


def pipe_dn(peak_mw: float, delta_k: float) -> int:
    """Return the standard DN that carries the peak at the design velocity."""
    m = peak_mw * 1e6 / (WATER_CP * max(delta_k, 1e-6))
    area = m / WATER_RHO / DESIGN_VELOCITY_M_S
    d_mm = math.sqrt(4 * area / math.pi) * 1000
    return next((dn for dn in STANDARD_DN if dn >= d_mm), STANDARD_DN[-1])


def _pair(load, supply_c, return_c, length_m, ground_c, pump_eff):
    """One network pair's daily loss (MW, + lost), temperature changes and pumping (MW)."""
    load = np.asarray(load, dtype=float)
    delta = abs(supply_c - return_c)
    peak = float(load.max()) if load.size else 0.0
    if peak <= 0:
        zero = np.zeros_like(load)
        return {"dn": 0, "u": 0.0, "loss": zero, "drop_s": zero, "drop_r": zero, "pump": zero}
    dn = pipe_dn(peak, delta)
    u = u_value(dn)
    loss_s = u * length_m * (supply_c - ground_c) / 1e6  # MW, + when the water loses heat
    loss_r = u * length_m * (return_c - ground_c) / 1e6
    m_peak = peak * 1e6 / (WATER_CP * delta)
    m_day = np.maximum(load * 1e6 / (WATER_CP * delta), MIN_FLOW_SHARE * m_peak)
    drop_s = loss_s * 1e6 / (m_day * WATER_CP)  # K the supply loses on the way
    drop_r = loss_r * 1e6 / (m_day * WATER_CP)
    dp = 2 * length_m * FRICTION_PA_PER_M * (m_day / m_peak) ** 2  # Pa, both pipes
    pump = m_day / WATER_RHO * dp / pump_eff / 1e6  # MW electric
    return {
        "dn": dn,
        "u": u,
        "loss": np.full_like(load, loss_s + loss_r),
        "drop_s": drop_s,
        "drop_r": drop_r,
        "pump": pump,
    }


def network(heat, cool, rules: Rules) -> Optional[Dict[str, object]]:
    """Return the trunk's effect on the plant day by day, or None when the network is off.

    Returns
    -------
    dict
        ``heat_load`` and ``cool_load`` (MW at the plant, the buildings' demand plus what the
        network loses or gains), ``supply_c`` (the plant's heating supply, °C, per day),
        ``return_c`` (the return reaching the plant), ``cool_supply_c`` and ``cool_return_c``,
        ``pump_mw`` (electric, both networks) and a ``summary`` for the record.
    """
    length_m = float(getattr(rules, "network_length_km", 0.0) or 0.0) * 1000
    if length_m <= 0:
        return None
    ground, eff = rules.ground_temperature_c, rules.pump_efficiency
    h = _pair(heat, rules.heat_supply_c, rules.heat_return_c, length_m, ground, eff)
    c = _pair(cool, rules.cool_supply_c, rules.cool_return_c, length_m, ground, eff)
    heat = np.asarray(heat, dtype=float)
    cool = np.asarray(cool, dtype=float)
    # Cooling: the network loses heat to colder ground (the chilled water arrives colder): that
    # is cooling the plant need not make. Never below zero load.
    cool_load = np.where(cool > 0, np.maximum(cool - c["loss"], 0.0), 0.0)
    supply = rules.heat_supply_c + h["drop_s"]
    out = {
        "heat_load": heat + h["loss"],
        "cool_load": cool_load,
        "supply_c": supply,
        "return_c": rules.heat_return_c - h["drop_r"],
        "cool_supply_c": rules.cool_supply_c - np.where(cool > 0, c["drop_s"], 0.0),
        "cool_return_c": rules.cool_return_c - np.where(cool > 0, c["drop_r"], 0.0),
        "pump_mw": h["pump"] + np.where(cool > 0, c["pump"], 0.0),
    }
    out["summary"] = {
        "length_km": length_m / 1000,
        "heat_dn": h["dn"],
        "cool_dn": c["dn"],
        "heat_u_w_mk": round(h["u"], 3),
        "heat_loss_mw": round(float(h["loss"][0]) if np.size(h["loss"]) else 0.0, 3),
        "heat_loss_gwh": round(float(np.sum(h["loss"])) * 24 / 1000, 3),
        "heat_loss_share": round(float(np.sum(h["loss"])) / max(float(np.sum(heat)), 1e-9), 4),
        # Cooling the colder ground gives for free (the chilled water arrives colder).
        "cool_free_gwh": round(float(np.sum(np.minimum(c["loss"], cool))) * 24 / 1000, 3),
        "supply_c_max": round(float(supply.max()), 2),
        "supply_c_peak_day": round(float(supply[int(np.argmax(heat))]), 2),
        "pump_gwh": round(float(np.sum(out["pump_mw"])) * 24 / 1000, 3),
        "ground_c": ground,
    }
    return out
