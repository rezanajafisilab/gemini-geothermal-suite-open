"""Explicit test equipment/source scenarios; never production ratings."""

import os

import pytest

from dioscuri_plant.cooling import CoolingBoundary, CoolingSettings, CoolingSource
from gemini_model.cooling_common.config import AbsorptionSettings, ElectricSettings, TowerSettings

# The design-space sweep is off in the plant tests that search (``test_sweep`` runs it).
os.environ.setdefault("DIOSCURI_SWEEP", "0")


@pytest.fixture
def wet_settings():
    """Install ample declared screening capacity, flow and finite UA for tests."""
    return CoolingSettings(
        electric=ElectricSettings(capacity_w=12e6),
        absorption=AbsorptionSettings(capacity_w=4e6, hx_ua_w_k=1e6),
        tower=TowerSettings(capacity_w=30e6, circulation_m3s=1.0),
    )


@pytest.fixture
def hot_boundary():
    """Allocated source after heating; cp passed as if from actual Rules."""
    return CoolingBoundary(
        source=CoolingSource(
            wellhead_c=86.1,
            brine_flow_m3h=900,
            brine_density_kg_m3=1030,
            brine_cp_j_kg_k=3990,
            brine_return_min_c=70.0,
            allocated_heat_mw=10.0,
            hot_flow_m3h=900,
            well_loss_k=0.9,
            source_id="fixed_boundary_test_only",
        )
    )
