"""Independent conservation, boundary, API and scalar/vector checks."""

import builtins
import json
from dataclasses import asdict, replace

import numpy as np
import pytest

from dioscuri_plant.cooling import (
    CoolingBoundary,
    CoolingDayRequest,
    CoolingWeather,
    aggregate_hourly,
    evaluate_cooling_batch,
    evaluate_cooling_day,
    format_cooling_violations,
)
from gemini_model.absorption_chiller import AbsorptionChiller
from gemini_model.cooling_common.kernel import cooling_kernel
from gemini_model.cooling_common.physics import counterflow_hx, pump_power_w, water_rates_m3h
from gemini_model.cooling_tower import CoolingTower
from gemini_model.electric_chiller import ElectricChiller


def test_hand_electric_and_full_boundary(wet_settings):
    """One MW, COP 5: 0.2 MW compression and 1.2 MW condenser core."""
    s = replace(wet_settings, electric=replace(wet_settings.electric, cop=5), chilled_pump_ratio=0)
    result = evaluate_cooling_day(CoolingDayRequest("2027-07-19", 1), s, CoolingBoundary())
    v = result.values
    assert v["compressor_mw"] == pytest.approx(0.2)
    assert v["tower_reject_mw"] == pytest.approx(1.2 * (1 + 0.005))
    assert v["cool_mw"] == pytest.approx(1)
    assert v["energy_residual_mw"] == pytest.approx(0, abs=1e-12)
    assert "WATER_SUPPLY_NOT_CHECKED" in result.diagnostics
    assert v["emission"] == 0  # central plant owns grid CO2
    json.dumps(asdict(result), allow_nan=False)


@pytest.mark.parametrize("cycles,makeup_factor", [(3, 1.5), (5, 1.25), (6, 1.2)])
def test_water_hand_balance(wet_settings, cycles, makeup_factor):
    """1 MWh rejected: independently convert 0.8 MWh to latent evaporation."""
    w = replace(wet_settings.water, cycles=cycles)
    evap, blow, makeup = water_rates_m3h(1e6, w)
    assert evap == pytest.approx(1.1755102040816328)
    assert blow + evap == pytest.approx(makeup)
    assert makeup == pytest.approx(evap * makeup_factor)


@pytest.mark.parametrize("limit", [0, 1.0, None])
def test_water_cap_recalculates_service(wet_settings, limit):
    """Finite water supply reduces real cold, electricity and rejected heat together."""
    s = replace(wet_settings, water=replace(wet_settings.water, max_makeup_water_m3h=limit))
    r = evaluate_cooling_day(CoolingDayRequest("test", 10), s, CoolingBoundary())
    v = r.values
    assert v["cool_mw"] + v["cool_unmet_mw"] == pytest.approx(10)
    assert abs(v["energy_residual_mw"]) < 1e-10
    if limit is not None:
        assert v["makeup_m3h"] <= limit + 1e-10
        assert v["cool_unmet_mw"] > 0
        assert "WATER_LIMIT" in r.diagnostics
    else:
        assert "WATER_SUPPLY_NOT_CHECKED" in r.diagnostics


def test_absorption_circuits_and_source_budget(wet_settings, hot_boundary):
    """Generator, brine, hot water and rejection close independently."""
    s = replace(wet_settings, option="absorption", chilled_pump_ratio=0)
    r = evaluate_cooling_day(CoolingDayRequest("test", 10), s, hot_boundary)
    v = r.values
    assert v["abs_mw"] == pytest.approx(4)
    assert v["drive_mw"] == pytest.approx(4 / 0.7)
    assert v["abs_internal_mw"] == pytest.approx(0.04)
    assert v["chill_mw"] == pytest.approx(6)
    assert v["brine_outlet_temperature_c"] == pytest.approx(
        86.1 - v["drive_mw"] * 1e6 / (1030 * 3990 * 900 / 3600)
    )
    assert v["hot_return_temperature_c"] == pytest.approx(
        75 - v["drive_mw"] * 1e6 / (1000 * 4180 * 900 / 3600)
    )
    assert v["brine_outlet_temperature_c"] - v["hot_return_temperature_c"] >= 5
    assert abs(v["energy_residual_mw"]) < 1e-10
    assert v["well_loss_k"] == 0.9 and v["wellhead_c"] == 86.1


@pytest.mark.parametrize(
    "failure", ["no_heat", "zero_ua", "low_grade", "hot_flow", "brine_flow", "tight_return"]
)
def test_abs_source_failures_use_backup(wet_settings, hot_boundary, failure):
    """No generator heat survives a closed source, infeasible grade or flow."""
    s = replace(wet_settings, option="absorption")
    b = hot_boundary
    if failure == "no_heat":
        b = replace(b, source=replace(b.source, allocated_heat_mw=0))
    elif failure == "zero_ua":
        s = replace(s, absorption=replace(s.absorption, hx_ua_w_k=0))
    elif failure == "low_grade":
        b = replace(b, source=replace(b.source, wellhead_c=79))
    elif failure == "hot_flow":
        b = replace(b, source=replace(b.source, hot_flow_m3h=0))
    elif failure == "brine_flow":
        b = replace(b, source=replace(b.source, brine_flow_m3h=0))
    else:
        b = replace(b, source=replace(b.source, brine_return_min_c=86.1))
    v = evaluate_cooling_day(CoolingDayRequest("test", 5), s, b).values
    assert v["abs_mw"] == 0 and v["drive_mw"] == 0
    assert v["chill_mw"] == pytest.approx(5)


def test_abs_air_backup_and_shared_water(wet_settings, hot_boundary):
    """Zero tower water still permits explicitly installed air backup."""
    s = replace(
        wet_settings,
        option="absorption",
        electric=replace(wet_settings.electric, condenser="air", cop=4),
        water=replace(wet_settings.water, max_makeup_water_m3h=0),
    )
    v = evaluate_cooling_day(CoolingDayRequest("test", 8), s, hot_boundary).values
    assert v["cool_mw"] == pytest.approx(8) and v["abs_mw"] == 0
    assert v["tower_reject_mw"] == 0 and v["makeup_m3h"] == 0


def test_actual_outlet_and_zero_flow(wet_settings):
    """Capacity shortfall returns warmer actual water; zero flow has no outlet."""
    s = replace(wet_settings, electric=replace(wet_settings.electric, capacity_w=1e6))
    r = evaluate_cooling_day(CoolingDayRequest("test", 10), s, CoolingBoundary())
    assert r.values["chilled_supply_temperature_c"] > 24
    assert r.values["cool_unmet_mw"] > 9
    z = evaluate_cooling_day(
        CoolingDayRequest("test", 10, chilled_flow_m3h=0), s, CoolingBoundary()
    )
    assert z.values["cool_mw"] == 0 and z.values["chilled_supply_temperature_c"] is None
    json.dumps(asdict(z), allow_nan=False)


@pytest.mark.parametrize("option", ["water", "air", "absorption"])
def test_vector_scalar_parity_and_hourly_peaks(wet_settings, hot_boundary, option):
    """Numerical path is identical across off/limited/backup states, not only rated duty."""
    e = replace(wet_settings.electric, condenser="air" if option == "air" else "water")
    s = replace(wet_settings, option=option, electric=e)
    q = np.array([0, 1, 5, 15.0])
    batch = evaluate_cooling_batch(CoolingDayRequest("days", q), s, hot_boundary)
    for i, power in enumerate(q):
        day = evaluate_cooling_day(CoolingDayRequest(str(i), power), s, hot_boundary)
        for k in ("cool_mw", "drive_mw", "el_mw", "makeup_m3h", "energy_residual_mw"):
            assert day.values[k] == pytest.approx(batch.values[k][i], abs=1e-10)
    db = np.full((4, 24), 25.0)
    db[-1, -1] = 50
    weather = CoolingWeather(db, np.full_like(db, 20), fixed_daily_boundary=True)
    hourly = evaluate_cooling_batch(CoolingDayRequest("days", q), s, hot_boundary, weather)
    summary = aggregate_hourly(hourly)
    assert hourly.values["cool_mw"].shape == (4, 24)
    assert summary["daily_mwh"]["cool_mwh"][1] == pytest.approx(24)
    if option == "air":
        assert summary["daily_masks"]["ELECTRIC_ENVELOPE"][-1]
        assert summary["daily_mwh"]["cool_unmet_mwh"][-1] > 0
    with pytest.raises(ValueError, match="fixed_daily_boundary"):
        evaluate_cooling_batch(
            CoolingDayRequest("days", q),
            s,
            hot_boundary,
            replace(weather, fixed_daily_boundary=False),
        )


def test_per_flow_boundary_points_are_not_recorrected(wet_settings, hot_boundary):
    """Team-provided 300/150/100/50 points are explicit fixtures, not a Ramey fit."""
    s = replace(wet_settings, option="absorption")
    flows, temps, losses = (
        np.array([300, 150, 100, 50]),
        np.array([86.1, 85.2, 84.3, 81.8]),
        np.array([0.9, 1.8, 2.7, 5.2]),
    )
    source = replace(
        hot_boundary.source, brine_flow_m3h=flows, wellhead_c=temps, well_loss_k=losses
    )
    r = evaluate_cooling_batch(
        CoolingDayRequest("points", np.ones(4) * 5), s, replace(hot_boundary, source=source)
    )
    np.testing.assert_array_equal(r.values["wellhead_c"], temps)
    np.testing.assert_array_equal(r.values["well_loss_k"], losses)
    assert np.all(np.diff(r.values["drive_mw"]) < 0)


def test_pump_and_counterflow_independent_checks():
    """Pump SI conversion, exchanger direction, equal-C branch and reversal."""
    assert pump_power_w(100 / 3600, 1e5, 0.7) == pytest.approx(3968.253968253968)
    r = counterflow_hx(16, 6, 41800, 41800, 20000)
    expected = 20000 / (1 + 20000 / 41800) * 10
    assert r["power_transfer_w"] == pytest.approx(expected)
    assert 6 < r["outlet_a_c"] < 16 and 6 < r["outlet_b_c"] < 16
    rev = counterflow_hx(6, 16, 41800, 41800, 20000)
    assert rev["outlet_a_c"] == pytest.approx(r["outlet_b_c"])
    assert counterflow_hx(16, 6, 0, 41800, 20000)["power_transfer_w"] == 0
    assert counterflow_hx(16, 6, 41800, 41800, 0)["power_transfer_w"] == 0


def test_near_infinite_ua_respects_allocated_heat(wet_settings, hot_boundary):
    """G=Ch limit must not erroneously close an otherwise feasible source valve."""
    s = replace(
        wet_settings,
        option="absorption",
        absorption=replace(wet_settings.absorption, hx_ua_w_k=1e20),
    )
    b = replace(
        hot_boundary,
        source=replace(
            hot_boundary.source, brine_flow_m3h=5000, hot_flow_m3h=300, allocated_heat_mw=1
        ),
    )
    v = evaluate_cooling_day(CoolingDayRequest("test", 3), s, b).values
    assert v["drive_mw"] == pytest.approx(1)
    assert v["abs_mw"] == pytest.approx(0.7 / 1.01)


@pytest.mark.parametrize("flow,gen,cold", [(300, 3.424750, 2.397325), (900, 10.274250, 7.191975)])
def test_current_cp_hand_bounds_consumed_by_model(wet_settings, hot_boundary, flow, gen, cold):
    """Rules cp=3990 with 10 K allocated drop, before external pump feedback."""
    s = replace(
        wet_settings,
        option="absorption",
        chilled_pump_ratio=0,
        absorption=replace(
            wet_settings.absorption,
            capacity_w=10e6,
            hx_ua_w_k=1e8,
            hot_supply_c=70,
            hot_min_c=65,
            hot_return_min_c=55,
        ),
    )
    b = replace(
        hot_boundary,
        source=replace(
            hot_boundary.source, brine_flow_m3h=flow, brine_return_min_c=76.1, allocated_heat_mw=20
        ),
    )
    v = evaluate_cooling_day(CoolingDayRequest("fixed boundary test", 10), s, b).values
    assert v["drive_mw"] == pytest.approx(gen)
    assert v["abs_mw"] == pytest.approx(cold)
    assert v["brine_outlet_temperature_c"] == pytest.approx(76.1)


@pytest.mark.parametrize("model_type", [ElectricChiller, AbsorptionChiller])
def test_staticmodel_snapshot_no_state(wet_settings, model_type):
    """GEMINI accessor works; active outputs cannot persist after an off call."""
    model = model_type()
    s = (
        replace(wet_settings, option="absorption")
        if model_type is AbsorptionChiller
        else wet_settings
    )
    model.update_parameters({"settings": s})
    u = dict(
        request_w=1e6, supply_c=20, return_c=25, chilled_flow_m3s=1, dry_bulb_c=25, wet_bulb_c=20
    )
    model.calculate_output(u)
    assert model.get_output()["power_cool"] == pytest.approx(1e6)
    model.calculate_output(dict(u, request_w=0))
    assert model.get_output()["power_el"] == 0
    json.dumps(model.get_output(), allow_nan=False)


def test_standalone_tower_uses_shared_limits(wet_settings):
    """Standalone wrapper enforces same zero-water limit and clears stale heat."""
    m = CoolingTower()
    m.update_parameters({"settings": wet_settings})
    m.calculate_output({"core_rejection_w": 1e6, "wet_bulb_c": 20})
    assert m.output["power_reject"] == pytest.approx(1.005e6)
    m.update_parameters(
        {
            "settings": replace(
                wet_settings, water=replace(wet_settings.water, max_makeup_water_m3h=0)
            )
        }
    )
    m.calculate_output({"core_rejection_w": 1e6, "wet_bulb_c": 20})
    assert m.output["power_reject"] == 0 and m.output["power_reject_unmet"] == 1e6


def test_pure_runtime_and_reject_bad_data(wet_settings, monkeypatch):
    """No runtime file access; bad data is distinct from physical unmet load."""

    def denied(*args, **kwargs):
        raise AssertionError("Runtime attempted I/O")

    monkeypatch.setattr(builtins, "open", denied)
    evaluate_cooling_day(CoolingDayRequest("test", 1), wet_settings, CoolingBoundary())
    for power in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            cooling_kernel(power, 20, 25, 1, 25, 20, wet_settings)
    with pytest.raises(ValueError, match="free cooling"):
        evaluate_cooling_day(
            CoolingDayRequest("test", 1),
            replace(wet_settings, free_cooling_enabled=True),
            CoolingBoundary(),
        )


def test_dated_hourly_shortfall_text(wet_settings):
    """Failure formatting retains the exact model date and hour-ending index."""
    s = replace(wet_settings, water=replace(wet_settings.water, max_blowdown_m3h=0))
    r = evaluate_cooling_batch(
        CoolingDayRequest(["2027-07-19"], [1]),
        s,
        CoolingBoundary(),
        CoolingWeather(np.full((1, 24), 25), np.full((1, 24), 20), fixed_daily_boundary=True),
    )
    failures = format_cooling_violations(r)
    assert len(failures) == 24
    assert failures[-1].startswith("2027-07-19 hour ending UTC 24")
    assert "unmet 1 MW" in failures[-1]


def test_subzero_pure_water_sink_is_not_assumed_liquid(wet_settings):
    """A wet-bulb-plus-approach estimate cannot certify a frozen water circuit."""
    r = evaluate_cooling_day(
        CoolingDayRequest("winter screening", 1),
        wet_settings,
        CoolingBoundary(dry_bulb_c=-3, wet_bulb_c=-5),
    )
    assert r.values["cool_mw"] == 0
    assert r.values["makeup_m3h"] == 0
    assert "SINK_FREEZE_RISK" in r.diagnostics
    assert r.violations
