"""Historical report_screen_v1 only: USD/UK arithmetic is not production defaults."""

from pathlib import Path

import numpy as np
import pytest

from dioscuri_plant.cooling import (
    CoolingBoundary,
    CoolingDayRequest,
    CoolingSettings,
    CoolingSource,
    evaluate_cooling_batch,
)
from dioscuri_plant.cooling.inputs import load_demand_csvs
from gemini_model.cooling_common.config import AbsorptionSettings, ElectricSettings, TowerSettings


@pytest.mark.parametrize(
    "option,expected_el,expected_gen,expected_makeup",
    [
        ("water", 4682.026521600, 0, 40701.476571429),
        ("air", 6766.620480000, 0, 0),
        ("absorption", 2711.255954743, 22144.285714286, 69671.625376093),
    ],
)
def test_report_fixture_only(option, expected_el, expected_gen, expected_makeup):
    """Reproduce report inventories with expressly omitted external pump feedback."""
    path = Path(__file__).resolve().parents[2] / "hackathon/data/raw/challenge"
    if not (path / "GEMINI_Heating_Demand_Daily_2027.csv").exists():
        pytest.skip("Local ignored original challenge input required for report regression")
    demand = load_demand_csvs(
        path / "GEMINI_Heating_Demand_Daily_2027.csv", path / "GEMINI_Cooling_Demand_Daily_2027.csv"
    )
    s = CoolingSettings(
        option=option,
        electric=ElectricSettings(
            capacity_w=10e6,
            cop=4 if option == "air" else 6,
            condenser="air" if option == "air" else "water",
        ),
        absorption=AbsorptionSettings(capacity_w=4e6, hx_ua_w_k=1e8),
        tower=TowerSettings(capacity_w=100e6, circulation_m3s=100, pump_heat_to_water=0),
        chilled_pump_heat_to_water=0,
    )
    # Ample finite source is an uncoupled report test, not a geothermal design.
    b = CoolingBoundary(source=CoolingSource(100, 10000, 1030, 3990, 80, 100, 10000))
    r = evaluate_cooling_batch(CoolingDayRequest(demand.dates, demand.cool_mw), s, b)
    assert np.sum(r.values["el_mw"]) * 24 == pytest.approx(expected_el, rel=1e-10)
    assert np.sum(r.values["drive_mw"]) * 24 == pytest.approx(expected_gen, abs=1e-6)
    assert np.sum(r.values["makeup_m3h"]) * 24 == pytest.approx(
        expected_makeup, rel=1e-10, abs=1e-6
    )
