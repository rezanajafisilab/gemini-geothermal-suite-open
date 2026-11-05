"""Shared vectorised cooling calculation, SI units; equations in specification 03.

Absorption-first is an explicit component policy under supplied boundaries. This does
not schedule wells or allocate heating. Constant-COP envelopes are analyst scenarios.
Chilled/CW pump heat feedback is solved algebraically for linear auxiliary proxies;
hot-pump and fan heat goes to ambient. No iterations, caches, I/O or model calls.
"""

import numpy as np

from .config import validate_settings
from .physics import hx_conductance_w_k, nonnegative, water_rates_m3h
from .tower import tower_budget


def _temperature(name, value):
    a = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(a)) or np.any(a <= -273.15):
        raise ValueError(f"{name} must be finite Celsius above absolute zero")
    return a


def _within(value, low, high):
    return (value >= low) & (value <= high)


def cooling_kernel(
    request_w,
    supply_c,
    return_c,
    chilled_flow_m3s,
    dry_bulb_c,
    wet_bulb_c,
    settings,
    source=None,
    availability=1.0,
):
    """Evaluate scalar or broadcast arrays using a single W-based path.

    Parameters
    ----------
    request_w, supply_c, return_c, chilled_flow_m3s : array_like
        Requested service W, target/return C and actual supplied chilled-loop m3/s.
    dry_bulb_c, wet_bulb_c : array_like
        Consistent weather; wet inlet estimate = wet bulb + tower approach.
    settings : CoolingSettings
        Explicit installed capacities, envelopes and screening parameters.
    source : dict, optional
        wellhead_c (already corrected), brine_capacity_w_k (caller rho*flow*Rules.cp),
        brine_return_min_c (remaining whole-plant budget), allocated_heat_w and
        clean hot_flow_m3s. Optional well_loss_k is diagnostic only.
    availability : array_like
        Equipment available fraction, [0,1]. Does not imply well operation.

    Returns
    -------
    dict
        Numeric inventories/masks, with undefined outlet masks instead of NaNs.
    """
    validate_settings(settings)
    s, e, a, t = settings, settings.electric, settings.absorption, settings.tower
    q, ts, tr, flow, db, wb, av = np.broadcast_arrays(
        nonnegative("request_w", request_w),
        _temperature("supply", supply_c),
        _temperature("return", return_c),
        nonnegative("chilled flow", chilled_flow_m3s),
        _temperature("dry bulb", dry_bulb_c),
        _temperature("wet bulb", wet_bulb_c),
        nonnegative("availability", availability),
    )
    if np.any(av > 1) or np.any(wb > db + 0.001):
        raise ValueError("Availability exceeds one or wet bulb exceeds dry bulb")
    if np.any((q > 0) & (tr <= ts)):
        raise ValueError("Positive cooling requires return above target")
    zero = np.zeros_like(q)
    wet_option = s.option != "air"
    cw_in = wb + t.approach_k
    c_chw = flow * s.water.density_kg_m3 * s.water_cp_j_kg_k
    service_cap = np.minimum(q, c_chw * np.maximum(0, tr - ts))
    pump_factor = 1 + s.chilled_pump_ratio * s.chilled_pump_heat_to_water

    # One physical shared tower budget, including condenser pump heat and water caps.
    tower_cap, cw_in, c_cw, water_cap, thermal_cap = tower_budget(wb, av, s)
    tower_factor = 1 + t.pump_ratio * t.pump_heat_to_water

    gen_limit = zero
    hot_flow = zero
    cb = zero
    wh = zero
    loss = zero
    hot_valid = np.zeros_like(q, dtype=bool)
    source_supplied = source is not None
    if source_supplied:
        wh = np.broadcast_to(_temperature("wellhead", source["wellhead_c"]), q.shape)
        cb = np.broadcast_to(
            nonnegative("brine heat capacity flow", source["brine_capacity_w_k"]), q.shape
        )
        br_min = np.broadcast_to(
            _temperature("brine return minimum", source["brine_return_min_c"]), q.shape
        )
        allocated = np.broadcast_to(
            nonnegative("allocated heat", source["allocated_heat_w"]), q.shape
        )
        hot_flow = np.broadcast_to(nonnegative("hot flow", source["hot_flow_m3s"]), q.shape)
        loss = np.broadcast_to(
            nonnegative("well loss diagnostic", source.get("well_loss_k", 0.0)), q.shape
        )
        ch = hot_flow * s.water.density_kg_m3 * s.water_cp_j_kg_k
        conductance = hx_conductance_w_k(cb, ch, a.hx_ua_w_k)
        # HX inlet clean water = hot_supply - Q/Ch. Solve Q <= G*(Twh-Tclean_in).
        g_over_ch = np.divide(conductance, ch, out=np.zeros_like(q), where=ch > 0)
        ua_limit = np.divide(
            conductance * np.maximum(0, wh - a.hot_supply_c),
            1 - g_over_ch,
            out=allocated.copy(),
            where=(1 - g_over_ch) > 0,
        )
        inv_cb = np.divide(1.0, cb, out=np.zeros_like(q), where=cb > 0)
        inv_ch = np.divide(1.0, ch, out=np.zeros_like(q), where=ch > 0)
        pinch_limit = np.divide(
            np.maximum(0, wh - a.hot_supply_c - a.hx_approach_k),
            inv_cb - inv_ch,
            out=allocated.copy(),
            where=inv_cb > inv_ch,
        )
        hot_valid = (
            (wh >= a.hot_supply_c + a.hx_approach_k)
            & (ch > 0)
            & (cb > 0)
            & _within(a.hot_supply_c, a.hot_min_c, a.hot_max_c)
        )
        gen_limit = np.minimum.reduce(
            [
                allocated,
                cb * np.maximum(0, wh - br_min),
                ua_limit,
                pinch_limit,
                ch * max(0, a.hot_supply_c - a.hot_return_min_c),
            ]
        )
        gen_limit = np.where(hot_valid, gen_limit, 0.0)

    abs_valid = (
        _within(cw_in, a.sink_min_c, a.sink_max_c)
        & _within(ts, a.supply_min_c, a.supply_max_c)
        & hot_valid
    )
    abs_reject_ratio = pump_factor * (1 + 1 / a.cop_th + a.internal_ratio)
    abs_tower_ratio = abs_reject_ratio * tower_factor
    qa = zero
    if s.option == "absorption":
        qa = np.minimum.reduce(
            [
                service_cap,
                np.full_like(q, a.capacity_w) * av / pump_factor,
                gen_limit * a.cop_th / pump_factor,
                tower_cap / abs_tower_ratio,
            ]
        )
        qa = np.where(abs_valid, qa, 0.0)

    electric_sink = cw_in if e.condenser == "water" else db
    electric_valid = _within(electric_sink, e.sink_min_c, e.sink_max_c) & _within(
        ts, e.supply_min_c, e.supply_max_c
    )
    electric_reject_ratio = pump_factor * (1 + 1 / e.cop)
    remaining_tower = np.maximum(0, tower_cap - qa * abs_tower_ratio)
    qe = np.minimum(np.maximum(0, service_cap - qa), e.capacity_w * av / pump_factor)
    if e.condenser == "water":
        qe = np.minimum(qe, remaining_tower / (electric_reject_ratio * tower_factor))
    qe = np.where(electric_valid, qe, 0.0)

    delivered = qa + qe
    gen = qa * pump_factor / a.cop_th
    comp = qe * pump_factor / e.cop
    internal = qa * pump_factor * a.internal_ratio
    abs_core = qa * pump_factor + gen + internal
    elec_core = qe * pump_factor + comp
    wet_core = abs_core + (elec_core if e.condenser == "water" else zero)
    cw_pump = wet_core * t.pump_ratio
    tower_reject = wet_core + cw_pump * t.pump_heat_to_water
    tower_fan = tower_reject * t.fan_ratio
    air_reject = elec_core if e.condenser == "air" else zero
    air_fan = air_reject * e.air_fan_ratio
    hot_pump = gen * a.hot_pump_ratio
    chilled_pump = delivered * s.chilled_pump_ratio
    chillers = comp + internal + air_fan + hot_pump + chilled_pump
    towers = tower_fan + cw_pump
    ambient = (
        air_fan
        + tower_fan
        + hot_pump
        + chilled_pump * (1 - s.chilled_pump_heat_to_water)
        + cw_pump * (1 - t.pump_heat_to_water)
    )
    evap, blow, makeup = water_rates_m3h(tower_reject, s.water)
    actual_supply = tr - np.divide(delivered, c_chw, out=np.zeros_like(q), where=c_chw > 0)
    hot_c = hot_flow * s.water.density_kg_m3 * s.water_cp_j_kg_k
    hot_out = a.hot_supply_c - np.divide(gen, hot_c, out=np.zeros_like(q), where=hot_c > 0)
    brine_out = wh - np.divide(gen, cb, out=np.zeros_like(q), where=cb > 0)
    cw_out = cw_in + np.divide(tower_reject, c_cw, out=np.zeros_like(q), where=c_cw > 0)
    unmet = q - delivered
    masks = {
        "COOLING_UNMET": unmet > (1 + 0.001 * q),
        "CHILLED_FLOW_LIMIT": (q > service_cap + 1),
        "ELECTRIC_ENVELOPE": (q > qa + 1) & ~electric_valid,
        "ABS_HOT_LIMIT": (q > 0) & (s.option == "absorption") & (gen_limit <= 0),
        "ABS_ENVELOPE": (q > 0) & (s.option == "absorption") & ~abs_valid,
        "SINK_CAPACITY": (q > 0) & wet_option & (unmet > 1) & (tower_reject >= tower_cap - 1),
        "SINK_FREEZE_RISK": (q > 0) & wet_option & (cw_in <= 0),
        "WATER_LIMIT": (q > 0)
        & wet_option
        & (water_cap < thermal_cap)
        & (tower_reject >= water_cap - 1),
        "WATER_SUPPLY_NOT_CHECKED": (tower_reject > 0) & (s.water.max_makeup_water_m3h is None),
        "DISCHARGE_NOT_CHECKED": (tower_reject > 0) & (s.water.max_blowdown_m3h is None),
        "RETURN_NOT_VALIDATED": q > 0,
        "SUPPLIER_MAP_NOT_VALIDATED": q > 0,
    }
    result = {
        "power_cool": delivered,
        "power_cool_unmet": unmet,
        "power_abs": qa,
        "power_chill": qe,
        "power_free": zero,
        "power_recovery_hp": zero,
        "power_drive": gen,
        "power_compressor": comp,
        "power_abs_internal": internal,
        "power_chilled_pump": chilled_pump,
        "power_hot_pump": hot_pump,
        "power_cw_pump": cw_pump,
        "power_tower_fan": tower_fan,
        "power_air_fan": air_fan,
        "power_chillers": chillers,
        "power_towers": towers,
        "power_el": chillers + towers,
        "power_tower_reject": tower_reject,
        "power_air_reject": air_reject,
        "power_reject": tower_reject + air_reject,
        "power_aux_to_ambient": ambient,
        "power_th": zero,
        "emission": zero,
        "evaporation_m3h": evap,
        "blowdown_m3h": blow,
        "makeup_m3h": makeup,
        "chilled_supply_temperature_c": actual_supply,
        "chilled_outlet_defined": flow > 0,
        "hot_return_temperature_c": hot_out,
        "hot_outlet_defined": gen > 0,
        "brine_outlet_temperature_c": brine_out,
        "brine_outlet_defined": gen > 0,
        "cw_inlet_temperature_c": cw_in,
        "cw_return_temperature_c": cw_out,
        "cw_outlet_defined": tower_reject > 0,
        "wellhead_c": wh,
        "well_loss_k": loss,
        "chilled_flow_m3s": flow,
        "hot_flow_m3s": hot_flow,
        "tower_limit_w": tower_cap,
        "energy_residual_w": delivered
        + gen
        + chillers
        + towers
        - tower_reject
        - air_reject
        - ambient,
        "masks": masks,
    }
    if any(not np.all(np.isfinite(v)) for k, v in result.items() if k != "masks"):
        raise ValueError("Numerical overflow: operating inputs exceed the supported numeric range")
    return result
