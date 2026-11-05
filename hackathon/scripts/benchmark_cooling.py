"""Reproducible component timing only; no annual dispatch or sensitivity execution."""

import json
import platform
import statistics
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import scipy

from dioscuri_plant.cooling import (
    CoolingBoundary,
    CoolingDayRequest,
    CoolingSettings,
    CoolingSource,
    CoolingWeather,
    evaluate_cooling_batch,
)
from gemini_model.cooling_common.config import AbsorptionSettings, ElectricSettings, TowerSettings
from gemini_model.cooling_common.kernel import cooling_kernel


def benchmark(repeats=100):
    """Time representative loaded 365-day/(365,24) arrays; record independent gates."""
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "repeats": repeats,
        "statistic": "median per call after 10 warmups",
        "scope": (
            "kernel and pure adapter including validation; "
            "no I/O, well solves or string diagnostics"
        ),
        "joint_m5_end_to_end_ms": None,
        "cases": [],
    }
    settings = CoolingSettings(
        electric=ElectricSettings(capacity_w=12e6),
        absorption=AbsorptionSettings(capacity_w=4e6, hx_ua_w_k=1e6),
        tower=TowerSettings(capacity_w=30e6, circulation_m3s=1),
    )
    for option in ("water", "air", "absorption"):
        s = replace(
            settings,
            option=option,
            electric=replace(
                settings.electric,
                condenser="air" if option == "air" else "water",
                cop=4 if option == "air" else 6,
            ),
        )
        for shape in [(365,), (365, 24)]:
            load = np.resize(np.array([0, 1, 4, 8, 15.0]), shape)
            db, wb = np.full(shape, 25.0), np.full(shape, 20.0)
            source = dict(
                wellhead_c=86.1,
                brine_capacity_w_k=1030 * 3990 * 900 / 3600,
                brine_return_min_c=70,
                allocated_heat_w=10e6,
                hot_flow_m3s=900 / 3600,
                well_loss_k=0.9,
            )
            b = CoolingBoundary(source=CoolingSource(86.1, 900, 1030, 3990, 70, 10, 900, 0.9))
            calls = {
                "kernel": lambda: cooling_kernel(
                    load * 1e6, 20, 25, load * 1e6 / (1000 * 4180 * 5), db, wb, s, source
                ),
                "adapter": lambda: evaluate_cooling_batch(
                    CoolingDayRequest("synthetic intervals", load),
                    s,
                    b,
                    CoolingWeather(db, wb, fixed_daily_boundary=True),
                ),
            }
            times = {}
            for name, call in calls.items():
                for _ in range(10):
                    call()
                samples = []
                for _ in range(repeats):
                    start = time.perf_counter_ns()
                    call()
                    samples.append((time.perf_counter_ns() - start) / 1e6)
                times[name + "_median_ms"] = statistics.median(samples)
            result["cases"].append({"option": option, "shape": shape, **times})
    return result


if __name__ == "__main__":
    evidence = benchmark()
    path = Path(__file__).resolve().parents[1] / "docs/cooling/PERFORMANCE_EVIDENCE.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
