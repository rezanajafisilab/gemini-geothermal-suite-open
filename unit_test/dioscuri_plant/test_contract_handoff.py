"""Legacy contract preservation and handoff metadata without duplicate public types."""

import hashlib
import json
from pathlib import Path

from dioscuri_plant.cooling.parameters import parameter_metadata


def test_original_start_here_and_legacy_field_inventory():
    """Keep source bytes and all published names, even though M5 classes are unavailable."""
    root = Path(__file__).resolve().parents[2]
    assert (
        hashlib.sha256((root / "hackathon/docs/cooling/START_HERE.md").read_bytes()).hexdigest()
        == "6188cb393d713f3e0dec3471cdc47c3a349f658f88bd58f7b2af192fed262921"
    )
    contract = json.loads((root / "hackathon/docs/cooling/CONTRACT_HANDOFF.json").read_text())
    assert contract["legacy_fields"]["Rules"] == [
        "heat_supply_c",
        "heat_return_c",
        "cool_supply_c",
        "cool_return_c",
        "flow_min_m3h",
        "flow_max_m3h",
        "max_brine_cooling_k",
        "operating_days",
        "pump_efficiency",
        "brine_density_kg_m3",
        "brine_viscosity_pa_s",
        "brine_cp_j_kg_k",
        "gas_liquid_ratio",
        "gas_ch4_fraction",
        "gas_co2_fraction",
    ]
    assert "recovery_heat_pump_mw" in contract["legacy_fields"]["Plant"]
    assert "cool_delivered_gwh" in contract["legacy_fields"]["YearResult"]
    assert contract["legacy_cold_keys"] == ["abs", "chill", "recovery_hp"]
    assert contract["additive_cold_key"] == "free"


def test_metadata_units_missing_prices_and_no_second_brine_cp_default():
    """Metadata points to actual additive fields; omitted price is never zero."""
    records = {r["binding_path"]: r for r in parameter_metadata()}
    assert records["CoolingSettings.water_cp_j_kg_k"]["unit"] == "J/kg/K"
    assert records["CoolingSettings.absorption.hx_ua_w_k"]["unit"] == "W/K"
    assert records["CoolingSettings.water.max_makeup_water_m3h"]["base"] is None
    # The make-up water and blow-down are priced (4 Nov); treatment stays missing, not zero.
    assert records["Prices.water_supply_eur_per_m3"]["status"] == "sourced"
    assert records["Prices.water_supply_eur_per_m3"]["base"] == 1.64
    assert records["Prices.blowdown_disposal_eur_per_m3"]["status"] == "assumed"
    assert records["Prices.water_treatment_eur_per_m3"]["status"] == "missing"
    assert records["Prices.water_treatment_eur_per_m3"]["base"] is None
    assert not any("brine_cp" in key for key in records)
    assert records["CoolingSettings.free_cooling_enabled"]["sensitivity"] == [False]
