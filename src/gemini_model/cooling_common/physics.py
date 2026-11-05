"""Traceable SI pump, counterflow HX and tower-water equations from 03/11."""

import numpy as np


def nonnegative(name, value):
    """Validate finite nonnegative scalar/array data without modifying it."""
    a = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(a)) or np.any(a < 0):
        raise ValueError(f"{name} must be finite and nonnegative")
    return a


def pump_power_w(flow_m3s, pressure_drop_pa, efficiency):
    """Return flow * differential pressure / total efficiency, W (03)."""
    if not np.isfinite(efficiency) or not 0 < efficiency <= 1:
        raise ValueError("Pump efficiency must be in (0,1]")
    return nonnegative("flow_m3s", flow_m3s) * nonnegative("dp_pa", pressure_drop_pa) / efficiency


def hx_conductance_w_k(capacity_a_w_k, capacity_b_w_k, ua_w_k):
    """Return epsilon*Cmin for a counterflow HX, stable at Cr=1 and zero flow."""
    ca, cb, ua = np.broadcast_arrays(
        nonnegative("C_a", capacity_a_w_k),
        nonnegative("C_b", capacity_b_w_k),
        nonnegative("UA", ua_w_k),
    )
    cmin, cmax = np.minimum(ca, cb), np.maximum(ca, cb)
    cr = np.divide(cmin, cmax, out=np.zeros_like(cmin), where=cmax > 0)
    ntu = np.divide(ua, cmin, out=np.zeros_like(cmin), where=cmin > 0)
    exp_term = np.exp(-ntu * (1 - cr))
    numerator = -np.expm1(-ntu * (1 - cr))
    epsilon = np.divide(
        numerator, 1 - cr * exp_term, out=np.zeros_like(cmin), where=np.abs(1 - cr) > 1e-8
    )
    epsilon = np.where(np.abs(1 - cr) <= 1e-8, ntu / (1 + ntu), epsilon)
    return epsilon * cmin


def counterflow_hx(
    temperature_a_c, temperature_b_c, capacity_a_w_k, capacity_b_w_k, ua_w_k, approach_k=0.0
):
    """Transfer heat from the hotter port, preserving port order and both pinches."""
    if approach_k < 0 or not np.isfinite(approach_k):
        raise ValueError("Nonnegative approach required")
    ta, tb, ca, cb = np.broadcast_arrays(
        temperature_a_c, temperature_b_c, capacity_a_w_k, capacity_b_w_k
    )
    if not np.all(np.isfinite(ta)) or not np.all(np.isfinite(tb)):
        raise ValueError("Finite temperatures required")
    g = hx_conductance_w_k(ca, cb, ua_w_k)
    q = np.minimum(
        g * np.abs(ta - tb), np.minimum(ca, cb) * np.maximum(0, np.abs(ta - tb) - approach_k)
    )
    signed = np.sign(ta - tb) * q
    da = np.divide(signed, ca, out=np.zeros_like(q), where=ca > 0)
    db = np.divide(signed, cb, out=np.zeros_like(q), where=cb > 0)
    return {"power_transfer_w": q, "outlet_a_c": ta - da, "outlet_b_c": tb + db}


def water_rates_m3h(rejection_w, settings):
    """Return evaporation, blowdown, makeup m3/h; no drift, specification 11."""
    w = settings
    if w.cycles <= 1 or not 0 <= w.latent_fraction <= 1:
        raise ValueError("Invalid cycles/latent fraction")
    if w.density_kg_m3 <= 0 or w.latent_heat_j_kg <= 0:
        raise ValueError("Positive water properties required")
    evaporation = (
        nonnegative("tower rejection W", rejection_w)
        * 3600
        * w.latent_fraction
        / (w.density_kg_m3 * w.latent_heat_j_kg)
    )
    blowdown = evaporation / (w.cycles - 1)
    return evaporation, blowdown, evaporation + blowdown
