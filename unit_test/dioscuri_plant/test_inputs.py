"""All-row ingestion checks with optional preserved local sources and corrupt data."""

import csv
import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from dioscuri_plant.cooling.inputs import load_demand_csvs, load_weather_csvs


def write_csv(path, field, rows):
    """Write a synthetic test input; never mutate source files."""
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", field])
        writer.writerows(rows)


def test_demand_join_by_date_and_invalid_inputs(tmp_path):
    """Row order is irrelevant; duplicate/missing/nonfinite/negative data is rejected."""
    days = [str(date(2027, 1, 1) + timedelta(days=i)) for i in range(365)]
    heat, cool = tmp_path / "heat.csv", tmp_path / "cool.csv"
    hr = [(d, 10) for d in days]
    cr = [(d, 3) for d in reversed(days)]
    write_csv(heat, "heating_demand_MWth", hr)
    write_csv(cool, "cooling_demand_MWcool", cr)
    demand = load_demand_csvs(heat, cool)
    assert demand.dates == tuple(days)
    assert demand.cool_mw.sum() * 24 == 26280
    for bad in [
        cr[:-1],
        cr + [cr[0]],
        [(days[0], "-1")] + cr[1:],
        [(days[0], "nan")] + cr[1:],
        [(days[0], "inf")] + cr[1:],
    ]:
        write_csv(cool, "cooling_demand_MWcool", bad)
        with pytest.raises(ValueError):
            load_demand_csvs(heat, cool)


def test_duplicate_csv_columns_are_not_a_valid_schema(tmp_path):
    """Duplicated known columns cannot pass an exact-schema check."""
    path = tmp_path / "bad.csv"
    path.write_text("date,heating_demand_MWth,date\n2027-01-01,1,2027-01-01\n")
    with pytest.raises(ValueError, match="exact columns"):
        load_demand_csvs(path, path)


@pytest.fixture
def preserved_inputs():
    """Local organiser data is intentionally git-ignored; synthetic tests always run."""
    root = Path(__file__).resolve().parents[2]
    source = root / "hackathon/data/raw"
    heat = source / "challenge/GEMINI_Heating_Demand_Daily_2027.csv"
    cool = source / "challenge/GEMINI_Cooling_Demand_Daily_2027.csv"
    hourly = source / "weather/knmi_debilt_2025/GEMINI_Weather_Hourly_2027_KNMI_DeBilt_2025.csv"
    daily = source / "weather/knmi_debilt_2025/GEMINI_Weather_Daily_2027_KNMI_DeBilt_2025.csv"
    if not all(p.exists() for p in (heat, cool, hourly, daily)):
        pytest.skip("Original raw input pack is local/ignored; see M0_EVIDENCE.json")
    return heat, cool, hourly, daily


@pytest.fixture
def synthetic_inputs(tmp_path):
    """Complete small-schema weather scenario, so weather checks also run in CI."""
    days = [date(2027, 1, 1) + timedelta(days=i) for i in range(365)]
    heat, cool, hourly, daily = [
        tmp_path / name for name in ("heat.csv", "cool.csv", "hourly.csv", "daily.csv")
    ]
    write_csv(heat, "heating_demand_MWth", [(str(d), 10) for d in days])
    write_csv(cool, "cooling_demand_MWcool", [(str(d), 3) for d in reversed(days)])
    hrows, drows = [], []
    for d in days:
        source = d.replace(year=2025)
        common = dict(
            date=str(d),
            heating_demand_MWth=10,
            cooling_demand_MWcool=3,
            source_date=str(source),
            station_id=260,
            source_weather_year=2025,
        )
        drows.append(
            dict(
                common,
                dry_bulb_mean_c=15,
                dry_bulb_min_c=15,
                dry_bulb_max_c=15,
                relative_humidity_mean_pct=50,
                wet_bulb_mean_c=10,
                wet_bulb_min_c=10,
                wet_bulb_max_c=10,
                dew_point_mean_c=5,
                pressure_msl_mean_pa=101325,
                weather_hours=24,
            )
        )
        for h in range(1, 25):
            start = datetime.combine(d, datetime.min.time(), timezone.utc) + timedelta(hours=h - 1)
            source_end = datetime.combine(source, datetime.min.time(), timezone.utc) + timedelta(
                hours=h
            )
            hrows.append(
                dict(
                    common,
                    hour_ending_utc=h,
                    timestamp_start_utc=start.isoformat(),
                    timestamp_end_utc=(start + timedelta(hours=1)).isoformat(),
                    dry_bulb_c=15,
                    relative_humidity_pct=50,
                    wet_bulb_c=10,
                    dew_point_c=5,
                    pressure_msl_pa=101325,
                    source_observation_time_utc=source_end.isoformat(),
                )
            )
    for path, rows in [(hourly, hrows), (daily, drows)]:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(reversed(rows))
    return heat, cool, hourly, daily


def test_complete_synthetic_weather_join(synthetic_inputs):
    """Shuffled hourly/daily rows join correctly without relying on raw test data."""
    heat, cool, hourly, daily = synthetic_inputs
    result = load_weather_csvs(hourly, daily, load_demand_csvs(heat, cool))
    assert result.hourly.dry_bulb_c.shape == (365, 24)
    assert result.hourly_rows[-1]["hour_ending_utc"] == "24"
    assert result.daily_screening.wet_bulb_c.tolist() == [10.0] * 365


def test_original_hashes_demand_and_full_weather(preserved_inputs):
    """Verify unchanged sources and every hourly/daily record, not just first/last."""
    expected = [
        "f5ab8feeb33721bbe6e0e5a4f84c4076de30c7c58b71987838b800761c913efb",
        "e0ceec2332cd708ca1f97dd3cf6141521058e83e05406b628a758ad15bc3d47a",
        "d0a357572ffab16dbfeab8eb33e4e66794402e79bdb2f55246f21e360f778c1f",
        "2b51c2d848db73bf3d79c57b1cee6a7cb2852f8844966178062d64465943113b",
    ]
    for path, digest in zip(preserved_inputs, expected):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    heat, cool, hourly, daily = preserved_inputs
    demand = load_demand_csvs(heat, cool)
    assert demand.heat_mw.sum() * 24 == pytest.approx(111667.680)
    assert demand.cool_mw.sum() * 24 == pytest.approx(23742.528)
    assert (demand.cool_mw > 0).sum() == 219
    assert demand.dates[np.argmax(demand.cool_mw)] == "2027-07-19"
    weather = load_weather_csvs(hourly, daily, demand)
    assert weather.hourly.dry_bulb_c.shape == (365, 24)
    assert weather.hourly_rows[-1]["timestamp_end_utc"] == "2028-01-01T00:00:00Z"
    assert weather.hourly_rows[-1]["source_observation_time_utc"] == "2026-01-01T00:00:00Z"
    assert weather.daily_screening.mode == "daily_screening"


@pytest.mark.parametrize(
    "corruption", ["duplicate", "missing", "hour24", "nan", "copy", "rh", "wb", "daily_mean"]
)
def test_corrupt_weather_rejected(synthetic_inputs, tmp_path, corruption):
    """Corrupt temporary copies, preserving originals and their input meaning."""
    heat, cool, hourly, daily = synthetic_inputs
    with hourly.open(newline="") as f:
        reader = csv.DictReader(f)
        columns, rows = reader.fieldnames, list(reader)
    with daily.open(newline="") as f:
        dr = csv.DictReader(f)
        dcols, drows = dr.fieldnames, list(dr)
    if corruption == "duplicate":
        rows[100] = rows[99].copy()
    elif corruption == "missing":
        rows.pop(100)
    elif corruption == "hour24":
        rows[23]["timestamp_end_utc"] = "2027-01-01T00:00:00Z"
    elif corruption == "nan":
        rows[100]["dry_bulb_c"] = "nan"
    elif corruption == "copy":
        rows[100]["cooling_demand_MWcool"] = "1000"
    elif corruption == "rh":
        rows[100]["relative_humidity_pct"] = "101"
    elif corruption == "wb":
        rows[100]["wet_bulb_c"] = "100"
    else:
        drows[100]["dry_bulb_mean_c"] = "100"
    paths = [tmp_path / "bad_hourly.csv", tmp_path / "bad_daily.csv"]
    for p, cols, records in zip(paths, [columns, dcols], [rows, drows]):
        with p.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(records)
    with pytest.raises(ValueError):
        load_weather_csvs(*paths, load_demand_csvs(heat, cool))
