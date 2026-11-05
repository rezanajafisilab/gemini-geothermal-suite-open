"""Pure MW adapters to the reusable SI kernel; no annual dispatch or ledgers."""

import numpy as np

from gemini_model.cooling_common.kernel import cooling_kernel

from .contracts import CoolingBatchResult, CoolingDayResult


def _plant_values(raw):
    values = {}
    for key, v in raw.items():
        if key == "masks":
            continue
        if key.startswith("power_"):
            values[key.removeprefix("power_") + "_mw"] = v / 1e6
        elif key.endswith("_m3s"):
            values[key.removesuffix("_m3s") + "_m3h"] = v * 3600
        elif key in ("energy_residual_w", "tower_limit_w"):
            values[key.removesuffix("_w") + "_mw"] = v / 1e6
        else:
            values[key] = v
    return values


def evaluate_cooling_batch(requests, settings, boundaries, weather=None):
    """Evaluate scalar/daily/hourly arrays with explicit daily-constant boundaries.

    Daily arrays are expanded along axis 1 only when hourly weather has the same
    number of days and fixed_daily_boundary=True. This is not an energy bank.
    """
    shape = (
        np.shape(weather.dry_bulb_c)
        if weather is not None
        else np.shape(requests.requested_cold_mw)
    )

    def array(v):
        x = np.asarray(v, dtype=float)
        if len(shape) == 2 and x.shape == (shape[0],):
            if weather is None or not weather.fixed_daily_boundary:
                raise ValueError("Hourly broadcast requires fixed_daily_boundary=True")
            x = x[:, None]
        return x

    request_w = array(requests.requested_cold_mw) * 1e6
    supply, ret = array(requests.supply_c), array(requests.return_c)
    flow_sized = requests.chilled_flow_m3h is None
    if flow_sized:
        dt = ret - supply
        if np.any((request_w > 0) & (dt <= 0)):
            raise ValueError("Return must exceed supply for positive cooling")
        flow = np.divide(
            request_w,
            settings.water.density_kg_m3 * settings.water_cp_j_kg_k * dt,
            out=np.zeros_like(request_w + dt),
            where=dt > 0,
        )
    else:
        flow = array(requests.chilled_flow_m3h) / 3600
    source = None
    ids = settings.source_ids + (boundaries.source_id,)
    if boundaries.source is not None:
        b = boundaries.source
        if (
            not np.isfinite(b.brine_density_kg_m3)
            or b.brine_density_kg_m3 <= 0
            or not np.isfinite(b.brine_cp_j_kg_k)
            or b.brine_cp_j_kg_k <= 0
        ):
            raise ValueError("Pass positive density and the actual Rules brine cp")
        source = {
            "wellhead_c": array(b.wellhead_c),
            "brine_capacity_w_k": array(b.brine_flow_m3h)
            / 3600
            * b.brine_density_kg_m3
            * b.brine_cp_j_kg_k,
            "brine_return_min_c": array(b.brine_return_min_c),
            "allocated_heat_w": array(b.allocated_heat_mw) * 1e6,
            "hot_flow_m3s": array(b.hot_flow_m3h) / 3600,
            "well_loss_k": array(b.well_loss_k),
        }
        ids += (b.source_id,)
    db = array(boundaries.dry_bulb_c) if weather is None else array(weather.dry_bulb_c)
    wb = array(boundaries.wet_bulb_c) if weather is None else array(weather.wet_bulb_c)
    if weather is not None and weather.mode not in ("hourly", "daily_screening"):
        raise ValueError("Weather mode must be hourly or daily_screening")
    raw = cooling_kernel(
        request_w,
        supply,
        ret,
        flow,
        db,
        wb,
        settings,
        source=source,
        availability=array(boundaries.availability),
    )
    raw["masks"]["PUMP_FLOW_NOT_VALIDATED"] = np.broadcast_to(flow_sized, raw["power_cool"].shape)
    result = CoolingBatchResult(
        _plant_values(raw),
        raw["masks"],
        requests.date,
        weather.mode if weather else "explicit_boundary",
        ids + ((weather.source_id,) if weather else ()),
    )
    return result


def evaluate_cooling_day(request, settings, boundary):
    """Evaluate one supplied day/point; format diagnostics outside the numeric core."""
    batch = evaluate_cooling_batch(request, settings, boundary)
    if batch.values["cool_mw"].ndim != 0:
        raise ValueError("Day evaluation requires scalar inputs; use batch for arrays")
    values = {k: v.item() for k, v in batch.values.items()}
    for circuit, name in [
        ("chilled", "chilled_supply_temperature_c"),
        ("hot", "hot_return_temperature_c"),
        ("brine", "brine_outlet_temperature_c"),
        ("cw", "cw_return_temperature_c"),
    ]:
        if not values[circuit + "_outlet_defined"]:
            values[name] = None
    codes = [k for k, mask in batch.masks.items() if mask.item()]
    violations = (
        [
            f"{request.date}: requested {float(request.requested_cold_mw):.6g} MW; "
            f'delivered {values["cool_mw"]:.6g} MW, unmet {values["cool_unmet_mw"]:.6g} MW '
            f'(limits: {", ".join(codes)}).'
        ]
        if "COOLING_UNMET" in codes
        else []
    )
    return CoolingDayResult(
        str(request.date), values, codes, violations, source_ids=batch.source_ids
    )


def format_cooling_violations(result):
    """Format dated/hour-ending shortfalls outside the tight numerical path."""
    rows = []
    for index in np.argwhere(result.masks["COOLING_UNMET"]):
        ix = tuple(index)
        dates = result.dates
        label = str(dates) if isinstance(dates, str) else str(dates[ix[0]])
        if len(ix) == 2:
            label += f" hour ending UTC {ix[1]+1:02d}"
        delivered = result.values["cool_mw"][ix]
        unmet = result.values["cool_unmet_mw"][ix]
        codes = [code for code, mask in result.masks.items() if mask[ix]]
        rows.append(
            f"{label}: delivered {delivered:.6g} MW, unmet {unmet:.6g} MW; " f'{", ".join(codes)}.'
        )
    return rows


def aggregate_hourly(result):
    """Summarise 24-hour inventories, preserving peaks/masks without dispatching."""
    values = result.values
    if values["cool_mw"].ndim != 2 or values["cool_mw"].shape[1] != 24:
        raise ValueError("Hourly aggregation requires (days,24) arrays")
    powers = {k: v for k, v in values.items() if k.endswith("_mw") and k != "tower_limit_mw"}
    return {
        "daily_mwh": {k.removesuffix("_mw") + "_mwh": v.sum(axis=1) for k, v in powers.items()},
        "daily_mean_mw": {k: v.mean(axis=1) for k, v in powers.items()},
        "daily_peak_mw": {k: v.max(axis=1) for k, v in powers.items()},
        "daily_water_m3": {
            k.removesuffix("_m3h") + "_m3": values[k].sum(axis=1)
            for k in ("evaporation_m3h", "blowdown_m3h", "makeup_m3h")
        },
        "daily_masks": {k: v.any(axis=1) for k, v in result.masks.items()},
        "hourly_masks": result.masks,
    }
