"""Independent EUR accounting, missing-value and scope/basis checks."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from dioscuri_plant.cooling_costs import (
    ConversionStep,
    CoolingCostRecord,
    CoolingWaterPrices,
    InstalledCoolingItem,
    capital_recovery_factor,
    convert_to_eur2025,
    cooling_direct_cost,
    refrigerant_leakage_co2e_t,
)


def record(**changes):
    """Explicit analyst test record; no market quotation or universal lifetime."""
    r = CoolingCostRecord(
        "chiller",
        "electric_water",
        "test_assumption",
        status="analyst_scenario",
        capex_meur_per_mw=1.0,
        capex_intercept_meur=0,
        fixed_om_eur_per_mw_year=2000,
        variable_om_eur_per_mwh=2,
        lifetime_years=25,
        capacity_min_mw=0.1,
        capacity_max_mw=20,
        includes_tower=False,
        installed_scope=True,
    )
    return replace(r, **changes)


def price(**changes):
    """User price test scenario in EUR-2025, all four fields explicit."""
    return replace(CoolingWaterPrices(1, 0.2, 0.3, 100, source_id="user_test"), **changes)


def run(items, wet=False, prices=None, **changes):
    """Supply already priced central electricity; no absorption heat charge."""
    args = dict(
        items=items,
        electricity_cost_eur=500,
        makeup_m3=100 if wet else 0,
        blowdown_m3=20 if wet else 0,
        water_prices=prices or price(),
        delivered_cold_mwh=1000,
        requested_cold_mwh=1000,
        wet_tower_installed=wet,
    )
    args.update(changes)
    return cooling_direct_cost(**args)


def test_annuity_hand_and_zero_rate():
    """Independent published pack check, avoiding mirrored formulas."""
    assert capital_recovery_factor(25) == pytest.approx(0.072381365451, abs=1e-12)
    assert capital_recovery_factor(20, 0) == 0.05
    with pytest.raises(ValueError):
        capital_recovery_factor(0)


def test_installed_cost_fixed_variable_and_partial_scope():
    """Annual capex/fixed use installed MW even with very little dispatched energy."""
    result = run([InstalledCoolingItem(record(), 2, 10)])
    assert result.capex_meur == 2
    assert result.lines_eur_per_year["chiller:capital"] == pytest.approx(144762.730902, abs=1e-5)
    assert result.lines_eur_per_year["chiller:fixed_om"] == 4000
    assert result.lines_eur_per_year["chiller:variable_om"] == 20
    assert result.known_subtotal_eur_per_year == sum(result.lines_eur_per_year.values())
    assert result.direct_eur_per_mwh == pytest.approx(result.known_subtotal_eur_per_year / 1000)
    assert result.scope.startswith("partial_cooling_direct")


def test_tower_native_rejection_basis_and_water_once():
    """Tower O&M uses its 12 MW/1200 MWh rejected, not a chiller cold capacity."""
    tower = record(item_id="tower", technology="tower", basis="rejection")
    result = run(
        [InstalledCoolingItem(record(), 10, 1000), InstalledCoolingItem(tower, 12, 1200, "shared")],
        wet=True,
    )
    assert result.lines_eur_per_year["tower:fixed_om"] == 24000
    assert result.lines_eur_per_year["tower:variable_om"] == 2400
    assert result.lines_eur_per_year["water_supply_eur_per_m3"] == 100
    assert result.lines_eur_per_year["water_treatment_eur_per_m3"] == 20
    assert result.lines_eur_per_year["blowdown_disposal_eur_per_m3"] == 6
    assert result.lines_eur_per_year["water_fixed_eur_per_year"] == 100


def test_bundled_tower_and_combined_water():
    """One package and one combined service cannot be costed twice."""
    package = InstalledCoolingItem(record(includes_tower=True), 10, 1000, "shared")
    result = run(
        [package],
        wet=True,
        prices=price(water_treatment_eur_per_m3=None, combined_supply_treatment=True),
    )
    assert not result.missing
    tower = InstalledCoolingItem(
        record(item_id="tower", technology="tower", basis="rejection"), 12, 1200, "shared"
    )
    with pytest.raises(ValueError, match="twice"):
        run([package, tower], wet=True)
    with pytest.raises(ValueError, match="Combined"):
        run([package], wet=True, prices=price(combined_supply_treatment=True))
    with pytest.raises(ValueError, match="bundled"):
        run([InstalledCoolingItem(record(includes_water_service=True), 10, 1000)], wet=True)


@pytest.mark.parametrize(
    "missing",
    ["capex_meur_per_mw", "lifetime_years", "fixed_om_eur_per_mw_year", "variable_om_eur_per_mwh"],
)
def test_missing_cost_is_not_zero(missing):
    """Known subtotal remains available; missing cost suppresses intensity."""
    result = run([InstalledCoolingItem(record(**{missing: None}), 10, 1000)])
    assert result.direct_eur_per_mwh is None
    assert any(missing in m for m in result.missing)
    assert result.known_subtotal_eur_per_year > 0


def test_missing_water_off_fixed_charges_zero_delivery():
    """Installed water fixed service remains when off; no division by zero."""
    package = InstalledCoolingItem(record(includes_tower=True), 10, 0, "tower")
    result = run(
        [package], wet=True, makeup_m3=0, blowdown_m3=0, delivered_cold_mwh=0, requested_cold_mwh=0
    )
    assert result.lines_eur_per_year["water_fixed_eur_per_year"] == 100
    assert result.direct_eur_per_mwh is None and result.coverage is None
    missing = run([package], wet=True, prices=CoolingWaterPrices())
    assert "water_supply_eur_per_m3" in missing.missing


def test_no_silent_currency_or_capacity_extrapolation():
    """A monetary label cannot relabel dollars; out-of-domain records remain partial."""
    with pytest.raises(ValueError, match="EUR-2025"):
        run([InstalledCoolingItem(record(currency="USD"), 10, 1000)])
    result = run([InstalledCoolingItem(record(capacity_max_mw=1), 10, 1000)])
    assert "chiller:capacity_out_of_domain" in result.missing
    assert result.direct_eur_per_mwh is None


def test_explicit_conversion_chain_and_separate_leakage():
    """DEA uplift applies once to appropriate EUR-2020 data, not all cost sources."""
    assert convert_to_eur2025(
        100, [ConversionStep(1.168, "D015", "DEA EUR-2020 to EUR-2025")]
    ) == pytest.approx(116.8)
    assert convert_to_eur2025(200, [ConversionStep(0.5, "test_fx", "EUR per USD test only")]) == 100
    assert refrigerant_leakage_co2e_t(10, 100, 0.02, 2000) == 40
    with pytest.raises(ValueError):
        refrigerant_leakage_co2e_t(10, 100, 2, 2000)


def test_missing_conversion_and_capacity_domain_stay_partial():
    """Native dollar data cannot become complete EUR cost simply by naming a field."""
    r = record(original_currency="USD", original_price_year=2022, capacity_max_mw=None)
    result = run([InstalledCoolingItem(r, 10, 1000)])
    assert "chiller:conversion_chain" in result.missing
    assert "chiller:capacity_domain" in result.missing
    assert result.direct_eur_per_mwh is None


def test_normalised_source_data_retains_gaps_and_factor_direction():
    """Published reference normalisation is reproducible without inventing tower scope."""
    path = Path(__file__).resolve().parents[2] / "hackathon/docs/cooling/COOLING_COST_DATA.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    records = {r["item_id"]: r for r in data["records"]}
    water = records["water_compression_unit_reference"]["derived_eur2025"]["400_ton"]
    assert water["capex_meur_per_mw"] == pytest.approx(0.16663601916184612)
    assert water["fixed_om_eur_per_mw_year"] == pytest.approx(8926.929597956043)
    assert records["absorption_reference"]["derived_eur2025"]["capex_meur_per_mw"] == pytest.approx(
        0.7322895968641947
    )
    assert records["tower_alone"]["available_native_reference"]["final_eur2025_value"] is None
    assert records["absorption_reference"]["derived_eur2025"]["economic_lifetime_years"] is None
    assert data["source_reconciliation"]
