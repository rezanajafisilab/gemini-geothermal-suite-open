"""One numerical tower budget shared by standalone and system evaluation."""

import numpy as np

from .config import validate_settings
from .physics import nonnegative, water_rates_m3h


def tower_budget(wet_bulb_c, availability, settings):
    """Return available rejection W, inlet C, Cwater W/K and limiting budgets."""
    t, w = settings.tower, settings.water
    wb, av = np.broadcast_arrays(wet_bulb_c, availability)
    inlet = wb + t.approach_k
    cwater = t.circulation_m3s * w.density_kg_m3 * settings.water_cp_j_kg_k
    thermal = np.minimum(t.capacity_w * av, cwater * np.maximum(0, t.max_return_c - inlet))
    # Pure-water baseline has no freeze/bypass controller: subzero liquid is unsupported.
    thermal = np.where(inlet > 0.0, thermal, 0.0)
    _, blow_per_w, makeup_per_w = water_rates_m3h(1.0, w)
    water = np.full_like(inlet, t.capacity_w, dtype=float)
    for limit, rate in ((w.max_makeup_water_m3h, makeup_per_w), (w.max_blowdown_m3h, blow_per_w)):
        if limit is not None and rate > 0:
            water = np.minimum(water, limit / rate)
    return np.minimum(thermal, water), inlet, cwater, water, thermal


def tower_kernel(core_rejection_w, wet_bulb_c, settings, availability=1.0):
    """Reject supplied core heat plus CW pump heat, with explicit unmet duty."""
    validate_settings(settings)
    core, wb, av = np.broadcast_arrays(
        nonnegative("core heat", core_rejection_w),
        wet_bulb_c,
        nonnegative("availability", availability),
    )
    if not np.all(np.isfinite(wb)) or np.any(wb <= -273.15) or np.any(av > 1):
        raise ValueError("Finite wet bulb and availability <=1 required")
    cap, inlet, cwater, _, _ = tower_budget(wb, av, settings)
    t = settings.tower
    accepted = np.minimum(core, cap / (1 + t.pump_ratio * t.pump_heat_to_water))
    pump = accepted * t.pump_ratio
    rejection = accepted + pump * t.pump_heat_to_water
    fan = rejection * t.fan_ratio
    evap, blow, makeup = water_rates_m3h(rejection, settings.water)
    return {
        "power_reject": rejection,
        "power_core_accepted": accepted,
        "power_reject_unmet": core - accepted,
        "power_el": pump + fan,
        "power_cw_pump": pump,
        "power_tower_fan": fan,
        "power_th": np.zeros_like(core),
        "emission": np.zeros_like(core),
        "cw_inlet_temperature_c": inlet,
        "cw_return_temperature_c": inlet
        + np.divide(rejection, cwater, out=np.zeros_like(core), where=cwater > 0),
        "evaporation_m3h": evap,
        "blowdown_m3h": blow,
        "makeup_m3h": makeup,
    }
