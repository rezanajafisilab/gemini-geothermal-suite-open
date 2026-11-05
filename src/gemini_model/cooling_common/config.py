"""Explicit screening parameters (sources A002/A003/A006/A007/A013).

All temperature envelopes below are analyst screening domains, not supplier ratings.
Capacities/flows default to zero: equipment must be explicitly installed/supplied.
Ratios are W per W of the named duty; water cp is independent of Rules brine cp.
See 03_COMPONENT_EQUATIONS and the parameter handoff for bounds/provenance.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WaterSettings:
    """Effective-treatment/no-drift screening model, specification 11/A013."""

    cycles: float = 5.0
    density_kg_m3: float = 1000.0
    latent_heat_j_kg: float = 2.45e6
    latent_fraction: float = 0.8
    max_makeup_water_m3h: float | None = None
    max_blowdown_m3h: float | None = None


@dataclass(frozen=True)
class ElectricSettings:
    """Compressor-only COP with separate auxiliaries, A006/A007."""

    capacity_w: float = 0.0
    cop: float = 6.0
    condenser: str = "water"
    cop_boundary: str = "compressor_only"
    air_fan_ratio: float = 0.02
    sink_min_c: float = -10.0
    sink_max_c: float = 40.0
    supply_min_c: float = 5.0
    supply_max_c: float = 25.0


@dataclass(frozen=True)
class AbsorptionSettings:
    """Single-effect constant COP; explicit provisional domain, A006/A007."""

    capacity_w: float = 0.0
    cop_th: float = 0.7
    internal_ratio: float = 0.01
    hot_supply_c: float = 75.0
    hot_min_c: float = 70.0
    hot_max_c: float = 95.0
    hot_return_min_c: float = 65.0
    sink_min_c: float = 5.0
    sink_max_c: float = 35.0
    supply_min_c: float = 5.0
    supply_max_c: float = 25.0
    hx_approach_k: float = 5.0
    hx_ua_w_k: float = 0.0
    hot_pump_ratio: float = 0.005


@dataclass(frozen=True)
class TowerSettings:
    """Declared capacity/flow and constant approach; not a tower performance map."""

    capacity_w: float = 0.0
    circulation_m3s: float = 0.0
    approach_k: float = 3.0
    max_return_c: float = 40.0
    fan_ratio: float = 0.0126
    pump_ratio: float = 0.005
    pump_heat_to_water: float = 1.0


@dataclass(frozen=True)
class CoolingSettings:
    """Three options; optional free cooling is deliberately disabled (D002)."""

    option: str = "water"
    electric: ElectricSettings = field(default_factory=ElectricSettings)
    absorption: AbsorptionSettings = field(default_factory=AbsorptionSettings)
    tower: TowerSettings = field(default_factory=TowerSettings)
    water: WaterSettings = field(default_factory=WaterSettings)
    water_cp_j_kg_k: float = 4180.0
    chilled_pump_ratio: float = 0.01
    chilled_pump_heat_to_water: float = 1.0
    free_cooling_enabled: bool = False
    source_ids: tuple[str, ...] = ("A002", "A003", "A006", "A007", "A013")


def validate_settings(s):
    """Reject malformed settings; physical shortfalls are handled by the kernel."""
    import math
    from dataclasses import fields, is_dataclass

    def finite(v):
        if is_dataclass(v):
            for f in fields(v):
                if f.name.endswith("_c") and getattr(v, f.name) <= -273.15:
                    raise ValueError("Temperature settings must be above absolute zero")
                finite(getattr(v, f.name))
        elif isinstance(v, (float, int)) and not math.isfinite(v):
            raise ValueError("Nonfinite setting")

    finite(s)
    if s.option not in ("water", "air", "absorption"):
        raise ValueError("Unknown cooling option")
    if s.free_cooling_enabled:
        raise ValueError("Optional M3 free cooling is not implemented")
    e, a, t, w = s.electric, s.absorption, s.tower, s.water
    if e.condenser not in ("water", "air") or e.cop_boundary != "compressor_only":
        raise ValueError("Use compressor_only COP; package COP requires item reconciliation")
    if s.option in ("water", "air") and e.condenser != s.option:
        raise ValueError("Option and electric condenser must agree")
    if e.cop <= 0 or a.cop_th <= 0 or a.cop_th > 1:
        raise ValueError("Positive electric COP and single-effect thermal COP in (0,1] required")
    if w.cycles <= 1 or not 0 <= w.latent_fraction <= 1:
        raise ValueError("Cycles must exceed one; latent fraction must be in [0,1]")
    if min(w.density_kg_m3, w.latent_heat_j_kg, s.water_cp_j_kg_k) <= 0:
        raise ValueError("Fluid properties must be positive")
    for v in (
        e.capacity_w,
        a.capacity_w,
        a.hx_ua_w_k,
        a.hx_approach_k,
        t.capacity_w,
        t.circulation_m3s,
        t.approach_k,
        t.fan_ratio,
        t.pump_ratio,
        e.air_fan_ratio,
        a.internal_ratio,
        a.hot_pump_ratio,
        s.chilled_pump_ratio,
    ):
        if v < 0:
            raise ValueError(
                "Capacities, flows, approaches and auxiliary ratios must be nonnegative"
            )
    for v in (w.max_makeup_water_m3h, w.max_blowdown_m3h):
        if v is not None and v < 0:
            raise ValueError("Water limits must be nonnegative or None (unchecked)")
    if not 0 <= t.pump_heat_to_water <= 1 or not 0 <= s.chilled_pump_heat_to_water <= 1:
        raise ValueError("Heat fractions must be in [0,1]")
    for lo, hi in (
        (e.sink_min_c, e.sink_max_c),
        (e.supply_min_c, e.supply_max_c),
        (a.hot_min_c, a.hot_max_c),
        (a.sink_min_c, a.sink_max_c),
        (a.supply_min_c, a.supply_max_c),
    ):
        if lo <= -273.15 or hi < lo:
            raise ValueError("Invalid temperature envelope")
    if a.hot_return_min_c <= -273.15 or a.hot_supply_c <= -273.15:
        raise ValueError("Invalid hot-loop temperature")
