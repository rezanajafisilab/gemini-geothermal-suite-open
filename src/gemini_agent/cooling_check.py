"""A design's cooling run through Ali's component model (``gemini_model.cooling_common``).

Our year model (``dioscuri_plant.year``) gives the electric chillers a Carnot-based COP and the
towers a fixed power and water per MW rejected. Ali's kernel (from ``ali/cooling-components``,
merged 2 Nov) models the towers' water (evaporation, blow-down, make-up), their fans and pumps,
and the limits each unit works within. This runs it on the design's own cold from the electric
chillers (and the absorption chiller), and the towers' kernel on free cooling's cold, which the
same towers reject, and sets the two side by side, like the GEMINI check: it does not change
the design.

The compressors run at our chillers' COP (4 Nov; before, at the kernel's screening value of 6),
so the comparison isolates the towers' and the water's physics and the units' limits.

Weather: the project's weather when given (``weather``); without it, De Bilt's wet bulb hour by
hour in 2021-2025 (KNMI; ``dioscuri_plant.weather.hourly_wet_bulb``): each day's cold runs
flat over that calendar day's 120 hours and the results are their mean, since the towers'
limits are clipped in the wet bulb. The wet bulb stands in for the dry bulb, which only an
air-cooled condenser would use. The check must run without weather data (the user, 2 Nov), and
says which weather it used.

Settings agreed with Ali (2 Nov): the chilled-water pumps are the network's, not the plant's
(ratio 0).

Absorption chiller (2 Nov): the kernel's "absorption" option, fed with the brine our year model
gives it each day (its share from the heat side: the generator's heat over a 15 K drop), the
design's wellhead temperature, and a clean hot-water loop at 75/65 °C between the brine and the
generator through an exchanger sized for the peak (NTU 4). The electric chillers take the rest.
Ali's thermal COP (0.7) is lower than ours (0.75), so the same brine gives less cold there.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from dioscuri_plant import weather
from dioscuri_plant.weather import KNMI_RH, KNMI_T, MONTH_DAYS, wet_bulb  # noqa: F401

WEATHER_SOURCE = weather.HOURLY_SOURCE


def typical_weather() -> Dict[str, np.ndarray]:
    """Return 365 days of dry and wet bulb (°C) from the KNMI normals (``dioscuri_plant``)."""
    wx = weather.typical_year()
    return {"dry_bulb_c": wx["dry_bulb_c"], "wet_bulb_c": wx["wet_bulb_c"]}


def hourly_weather() -> Dict[str, np.ndarray]:
    """Return De Bilt's wet bulb (°C) of each day's 120 hours of 2021-2025, (365, 120).

    The dry bulb is the wet bulb: only an air-cooled condenser uses it (the kernel asks for it
    and checks that the wet bulb is not above it).
    """
    wb = weather.hourly_wet_bulb()
    return {"dry_bulb_c": wb, "wet_bulb_c": wb}


def check(entry, weather: Optional[Dict[str, np.ndarray]] = None) -> Optional[dict]:
    """Return the design's chillers and towers as Ali's kernel runs them, or None.

    None when the design has no electric or absorption chillers. Values per year: cold made
    (GWh), compressor and auxiliary electricity (GWh), towers' water (m³), the absorption
    chiller's cold and the brine heat that drives it, against our year model's; and the days
    any limit was hit, by limit.
    """
    from dioscuri_plant import Components
    from gemini_agent import engine
    from gemini_model.cooling_common.config import (
        AbsorptionSettings,
        CoolingSettings,
        ElectricSettings,
        TowerSettings,
    )
    from gemini_model.cooling_common.kernel import cooling_kernel
    from gemini_model.cooling_common.tower import tower_kernel

    a, y = entry.alternative, entry.year
    sizes = a.sizes_mw or {}
    chillers = float(sizes.get("chillers", 0.0) or 0.0)
    absorb = float(sizes.get("absorption", 0.0) or 0.0)
    daily = (y.daily_mw or {}).get("cool") or {}
    chill_cold = np.asarray(daily.get("chill") or [], dtype=float)
    abs_cold = np.asarray(daily.get("abs") or np.zeros(365), dtype=float)
    free_cold = np.asarray(daily.get("free") or np.zeros(365), dtype=float)
    if chill_cold.size != 365:
        return None
    if abs_cold.size != 365:
        abs_cold = np.zeros(365)
    if free_cold.size != 365:
        free_cold = np.zeros(365)
    with_abs = absorb > 0 and abs_cold.sum() > 0
    if chillers <= 0 and not with_abs:
        return None
    cold = chill_cold + abs_cold  # what the chillers make; free cooling's goes to the towers
    rules = engine.rules_for(entry.brief)
    wx = weather or hourly_weather()
    source = "the project's weather files" if weather is not None else WEATHER_SOURCE
    # Each day's values over its hours (hourly weather: one column an hour), as daily means.
    hourly = np.ndim(wx["wet_bulb_c"]) == 2
    col = (lambda a: np.asarray(a, dtype=float)[:, None]) if hourly else np.asarray  # noqa: E731
    day = (lambda a: np.asarray(a).mean(axis=1)) if hourly else np.asarray  # noqa: E731
    cop = float(y.chiller_cop or 0.0) or ElectricSettings().cop  # ours (4 Nov)
    abs_settings = AbsorptionSettings()
    rejected_peak = chillers * 1e6 * (1 + 1 / cop) + (
        absorb * 1e6 * (1 + 1 / abs_settings.cop_th + abs_settings.internal_ratio)
        if with_abs
        else 0.0
    )
    brine = None
    if with_abs:
        # The brine our year model gives the absorption chiller each day, and the clean
        # hot-water loop that carries it to the generator (75 °C out, 65 °C back).
        comp = Components()
        ours_cop = float(y.absorption_cop or comp.absorption_cop)
        drive = abs_cold / ours_cop * 1e6  # W
        cb = drive / comp.absorption_brine_drop_k  # W/K
        loop = 1000.0 * 4180.0 * (abs_settings.hot_supply_c - abs_settings.hot_return_min_c)
        hot_flow = float(drive.max()) / loop  # m3/s, sized for the peak
        wellhead = float(y.wellhead_c)
        abs_settings = AbsorptionSettings(
            capacity_w=absorb * 1e6, hx_ua_w_k=4.0 * float(cb.max(initial=0.0))
        )
        brine = {
            "wellhead_c": wellhead,
            "brine_capacity_w_k": col(cb),
            "brine_return_min_c": wellhead - float(rules.max_brine_cooling_k),
            "allocated_heat_w": col(drive),
            "hot_flow_m3s": hot_flow,
        }
    settings = CoolingSettings(
        option="absorption" if with_abs else "water",
        electric=ElectricSettings(capacity_w=chillers * 1e6, cop=cop),
        absorption=abs_settings,
        # Towers sized for the chillers' peak with a tenth to spare; circulation for a 5 K range.
        tower=TowerSettings(
            capacity_w=1.1 * rejected_peak,
            circulation_m3s=1.1 * rejected_peak / (1000.0 * 4180.0 * 5.0),
        ),
        chilled_pump_ratio=0.0,
    )
    supply = np.full(365, float(rules.cool_supply_c))
    ret = np.full(365, float(rules.cool_return_c))
    flow = cold * 1e6 / (1000.0 * 4180.0 * np.maximum(ret - supply, 1e-6))
    raw = cooling_kernel(
        col(cold * 1e6),
        col(supply),
        col(ret),
        col(flow),
        wx["dry_bulb_c"],
        wx["wet_bulb_c"],
        settings,
        source=brine,
    )
    out = {k: day(v) for k, v in raw.items() if k != "masks"}
    out["masks"] = {k: np.asarray(v).any(axis=1) if hourly else v for k, v in raw["masks"].items()}
    # Free cooling's cold goes through the same towers: its heat, their pumps and fans, water.
    free = {
        k: day(v) for k, v in tower_kernel(col(free_cold * 1e6), wx["wet_bulb_c"], settings).items()
    }
    for k in ("evaporation_m3h", "blowdown_m3h", "makeup_m3h"):
        out[k] = out[k] + free[k]
    out["power_towers"] = out["power_towers"] + free["power_el"]
    out["power_el"] = out["power_el"] + free["power_el"]
    gwh = lambda w: float(np.sum(w)) * 24 / 1e9  # noqa: E731 - W a day to GWh a year
    m3 = lambda h: float(np.sum(h)) * 24  # noqa: E731 - m³/h a day to m³ a year
    power = (y.daily_mw or {}).get("power") or {}
    ours_chill = float(np.sum(power.get("chillers") or [0.0])) * 24 / 1000
    ours_towers = float(np.sum(power.get("towers") or [0.0])) * 24 / 1000
    limits: Dict[str, int] = {}
    quiet = {
        "WATER_SUPPLY_NOT_CHECKED",
        "DISCHARGE_NOT_CHECKED",
        "RETURN_NOT_VALIDATED",
        "SUPPLIER_MAP_NOT_VALIDATED",
    }
    for name, mask in (out.get("masks") or {}).items():
        # The absorption chiller's limits only on the days our model ran it (its brine).
        running = abs_cold > 0 if name.startswith("ABS_") else cold > 0
        days = int(np.sum(np.asarray(mask, dtype=bool) & running))
        if days and name not in quiet:
            limits[name] = days
    absorption = None
    if with_abs:
        absorption = {
            "cold_gwh": round(gwh(out["power_abs"]), 3),
            "drive_gwh": round(gwh(out["power_drive"]), 3),
            "cop": abs_settings.cop_th,
            "ours_cold_gwh": round(float(np.sum(abs_cold)) * 24 / 1000, 3),
            "ours_drive_gwh": round(float(np.sum(abs_cold / ours_cop)) * 24 / 1000, 3),
            "ours_cop": round(ours_cop, 2),
            "hot_loop_c": [abs_settings.hot_supply_c, abs_settings.hot_return_min_c],
        }
    water = getattr(y, "tower_water_m3", None) or {}
    return {
        "model": "Dioscuri's cooling component model (screening, constant COP)",
        "weather": source,
        "cop": round(cop, 2),
        "cold_gwh": round(gwh(out["power_cool"]), 2),
        "unmet_gwh": round(gwh(out["power_cool_unmet"]), 3),
        # Free cooling's cold, which the towers reject too, and what they could not (frost:
        # the kernel's towers have no freeze control and reject nothing at 0 °C water).
        "free_gwh": round(float(np.sum(free_cold)) * 24 / 1000, 2),
        "free_unmet_gwh": round(gwh(free["power_reject_unmet"]), 3),
        "compressor_gwh": round(gwh(out["power_compressor"]), 3),
        "towers_gwh": round(gwh(out["power_towers"]), 3),
        "electricity_gwh": round(gwh(out["power_el"]), 3),
        "makeup_water_m3": round(m3(out["makeup_m3h"]), 0),
        "evaporation_m3": round(m3(out["evaporation_m3h"]), 0),
        "blowdown_m3": round(m3(out["blowdown_m3h"]), 0),
        "ours": {
            "cold_gwh": round(float(np.sum(cold)) * 24 / 1000, 2),
            "chillers_gwh": round(ours_chill, 3),
            "towers_gwh": round(ours_towers, 3),
            "chiller_cop": round(float(y.chiller_cop or 0.0), 2),
            "makeup_water_m3": water.get("makeup"),
        },
        "absorption": absorption,
        "limits": limits,
        "not_checked": [],
    }


def words(result: Optional[dict]) -> List[str]:
    """Return the check in sentences, for the design's notes and the report."""
    if not result:
        return []
    ours = result["ours"]
    free = result.get("free_gwh") or 0.0
    towers = f"towers (they also reject free cooling's {free:g} GWh)" if free else "towers"
    ours_water = ours.get("makeup_water_m3")
    out = [
        f"Dioscuri's cooling component model, run on the chillers' "
        f"{result['cold_gwh']:g} GWh of cold "
        f"({result['weather']}) at our chillers' COP of {result['cop']:g}, so that only the "
        f"towers, their water and the units' limits are compared: compressors "
        f"{result['compressor_gwh']:g} GWh against our {ours['chillers_gwh']:g} GWh; {towers} "
        f"{result['towers_gwh']:g} GWh against our {ours['towers_gwh']:g} GWh; the towers take "
        f"{result['makeup_water_m3']:,.0f} m³ of make-up water a year "
        f"({result['evaporation_m3']:,.0f} m³ evaporated, {result['blowdown_m3']:,.0f} m³ blown "
        "down)" + (f", against our {ours_water:,.0f} m³." if ours_water else ".")
    ]
    ab = result.get("absorption")
    if ab:
        out.append(
            f"Its absorption chiller makes {ab['cold_gwh']:g} GWh of cold from {ab['drive_gwh']:g} "
            f"GWh of brine heat at a COP of {ab['cop']:g} (ours: {ab['ours_cold_gwh']:g} GWh from "
            f"{ab['ours_drive_gwh']:g} GWh at {ab['ours_cop']:g}), through a hot-water loop at "
            f"{ab['hot_loop_c'][0]:g}/{ab['hot_loop_c'][1]:g} °C."
        )
    if result["unmet_gwh"] > 0.001:
        out.append(f"It leaves {result['unmet_gwh']:g} GWh of cold unmet.")
    if (result.get("free_unmet_gwh") or 0.0) > 0.001:
        out.append(
            f"Its towers have no freeze control: in frost they reject none of free cooling's "
            f"heat ({result['free_unmet_gwh']:g} GWh a year), which ours do."
        )
    if result["limits"]:
        hit = ", ".join(
            f"{k.lower().replace('_', ' ')} on {v} days" for k, v in result["limits"].items()
        )
        out.append(f"Limits it reports: {hit}.")
    if result["not_checked"]:
        out.append("Not checked yet: " + "; ".join(result["not_checked"]) + ".")
    return out
