"""Additive cooling seam only; annual public classes/functions remain with Reza.

No Rules, Plant, Prices, YearResult or Economics copies are introduced. Brine cp is
required from the actual Rules instance when constructing a CoolingSource.
"""

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from gemini_model.cooling_common.config import CoolingSettings


@dataclass(frozen=True)
class CoolingDayRequest:
    """Scalar/array request in MW and C; date labels follow the evaluated intervals."""

    date: object
    requested_cold_mw: object
    supply_c: object = 20.0
    return_c: object = 25.0
    chilled_flow_m3h: object | None = None


@dataclass(frozen=True)
class CoolingSource:
    """One allocated brine branch, with per-flow adapter temperatures used once.

    Use separate calls/branches for unlike wellhead temperatures; do not give every
    parallel branch the complete flow. return_min_c is the remaining plant budget,
    not a fresh 40 K allocation. Hydraulic/source feasibility stays with the caller.
    """

    wellhead_c: object
    brine_flow_m3h: object
    brine_density_kg_m3: float
    brine_cp_j_kg_k: float
    brine_return_min_c: object
    allocated_heat_mw: object
    hot_flow_m3h: object
    well_loss_k: object = 0.0
    source_id: str = "explicit_provisional_boundary"


@dataclass(frozen=True)
class CoolingWeather:
    """Already-loaded weather; daily boundaries need explicit hourly broadcasting."""

    dry_bulb_c: object
    wet_bulb_c: object
    mode: str = "hourly"
    fixed_daily_boundary: bool = False
    source_id: str = "explicit_weather"


@dataclass(frozen=True)
class CoolingBoundary:
    """Explicit equipment/source/weather boundary; no hidden well calls."""

    dry_bulb_c: object = 25.0
    wet_bulb_c: object = 20.0
    source: CoolingSource | None = None
    availability: object = 1.0
    source_id: str = "explicit_provisional_boundary"


@dataclass(frozen=True)
class ReturnCheckRequest:
    """Provisional optional joint-M5 return-validator request, SI pressure."""

    doublet_id: str
    date: str
    flow_m3h: float
    reinjection_c: float
    injection_inlet_pressure_pa: float
    adapter_version: str


@dataclass(frozen=True)
class ReturnCheckResult:
    """Proposed return evidence; pump replaces a prior estimate, never adds twice."""

    validated: bool = False
    required_injection_pressure_pa: float | None = None
    injector_pump_mw: float | None = None
    violations: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoolingContext:
    """Provider seam for joint integration; component kernels never invoke it."""

    heating_provider: Callable | None = None
    return_validator: Callable[[ReturnCheckRequest], ReturnCheckResult] | None = None
    version: str = "proposed_m0_v1"


@dataclass
class CoolingBatchResult:
    """Array inventories; powers in MW, water m3/h, C and m3/h in named keys."""

    values: dict[str, np.ndarray]
    masks: dict[str, np.ndarray]
    dates: object
    weather_mode: str
    source_ids: tuple[str, ...]
    validation_level: str = "screening_uncoupled"
    effective_treatment_assumed: bool = True
    model_level: str = "constant_cop_screening"


@dataclass
class CoolingDayResult:
    """JSON-safe scalar inventories and dated diagnoses at the additive seam."""

    date: str
    values: dict
    diagnostics: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    validation_level: str = "screening_uncoupled"
    weather_mode: str = "explicit_boundary"
    source_ids: tuple[str, ...] = ()
    model_level: str = "constant_cop_screening"


__all__ = [
    "CoolingSettings",
    "CoolingDayRequest",
    "CoolingSource",
    "CoolingWeather",
    "CoolingBoundary",
    "CoolingContext",
    "CoolingDayResult",
    "CoolingBatchResult",
]
