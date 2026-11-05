"""Additive cooling screening API; joint annual integration stays deferred."""

from .contracts import (
    CoolingBatchResult,
    CoolingBoundary,
    CoolingContext,
    CoolingDayRequest,
    CoolingDayResult,
    CoolingSettings,
    CoolingSource,
    CoolingWeather,
)
from .evaluate import (
    aggregate_hourly,
    evaluate_cooling_batch,
    evaluate_cooling_day,
    format_cooling_violations,
)

__all__ = [
    "CoolingBatchResult",
    "CoolingBoundary",
    "CoolingContext",
    "CoolingDayRequest",
    "CoolingDayResult",
    "CoolingSettings",
    "CoolingSource",
    "CoolingWeather",
    "aggregate_hourly",
    "evaluate_cooling_batch",
    "evaluate_cooling_day",
    "format_cooling_violations",
]
