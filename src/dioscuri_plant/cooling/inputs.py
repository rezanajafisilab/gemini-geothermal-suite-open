"""Explicit file-ingestion layer; evaluators never call these I/O functions.

Strict date/hour joins preserve original demand. Prepared wet bulb is retained;
no runtime weather fetching, interpolation or psychrometric recomputation.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .contracts import CoolingWeather


@dataclass(frozen=True)
class DemandInputs:
    """Validated arrays for conversion to Reza's existing Demand class at M5."""

    dates: tuple[str, ...]
    heat_mw: np.ndarray
    cool_mw: np.ndarray


@dataclass(frozen=True)
class WeatherInputs:
    """Validated paired scenario, retaining source rows and daily extrema."""

    hourly: CoolingWeather
    daily_screening: CoolingWeather
    hourly_rows: tuple[dict, ...]
    daily_rows: tuple[dict, ...]
    source_id: str


def _read(path, columns):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if (
            reader.fieldnames is None
            or len(reader.fieldnames) != len(columns)
            or set(reader.fieldnames) != set(columns)
        ):
            raise ValueError(f"{path}: expected exact columns {columns}")
        rows = list(reader)
    if any(None in r or any(v is None or v == "" for v in r.values()) for r in rows):
        raise ValueError(f"{path}: missing/extra CSV values")
    return rows


def _number(row, field):
    try:
        value = float(row[field])
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Invalid numeric {field}") from exc
    if not np.isfinite(value):
        raise ValueError(f"Nonfinite {field}")
    return value


def _calendar(year):
    start = date(year, 1, 1)
    return tuple(str(start + timedelta(days=i)) for i in range((date(year + 1, 1, 1) - start).days))


def load_demand_csvs(heat_csv, cool_csv, year=2027):
    """Read/join complete demand calendars by date, preserving MW and all days."""
    dates = _calendar(year)
    arrays = []
    for path, field in ((heat_csv, "heating_demand_MWth"), (cool_csv, "cooling_demand_MWcool")):
        rows = _read(path, ("date", field))
        mapping = {r["date"]: _number(r, field) for r in rows}
        if len(rows) != len(mapping) or set(mapping) != set(dates):
            raise ValueError("Demand has duplicate, missing or mismatched calendar dates")
        values = np.array([mapping[d] for d in dates])
        if np.any(values < 0):
            raise ValueError("Demand must be nonnegative")
        values.setflags(write=False)
        arrays.append(values)
    return DemandInputs(dates, *arrays)


def load_weather_csvs(
    hourly_csv,
    daily_csv,
    demand,
    source_year=2025,
    station_id=260,
    source_id="KNMI_DeBilt_2025_mapped_2027",
):
    """Validate every row, UTC endpoint, source key, copied load and daily statistic."""
    hcols = (
        "date,hour_ending_utc,timestamp_start_utc,timestamp_end_utc,dry_bulb_c,"
        "relative_humidity_pct,wet_bulb_c,dew_point_c,pressure_msl_pa,"
        "heating_demand_MWth,cooling_demand_MWcool,source_date,"
        "source_observation_time_utc,station_id,source_weather_year"
    ).split(",")
    dcols = (
        "date,dry_bulb_mean_c,dry_bulb_min_c,dry_bulb_max_c,relative_humidity_mean_pct,"
        "wet_bulb_mean_c,wet_bulb_min_c,wet_bulb_max_c,dew_point_mean_c,pressure_msl_mean_pa,"
        "heating_demand_MWth,cooling_demand_MWcool,source_date,station_id,"
        "source_weather_year,weather_hours"
    ).split(",")
    hourly = _read(hourly_csv, hcols)
    daily = _read(daily_csv, dcols)
    n = len(demand.dates)
    if len(hourly) != n * 24 or len(daily) != n:
        raise ValueError("Incomplete weather calendar")
    hmap, dmap = {}, {}
    for r in hourly:
        hour = _number(r, "hour_ending_utc")
        if hour != int(hour) or not 1 <= hour <= 24:
            raise ValueError("Hour ending must be integer 1..24")
        key = (r["date"], int(hour))
        if key in hmap:
            raise ValueError("Duplicate weather hour")
        hmap[key] = r
    for r in daily:
        if r["date"] in dmap:
            raise ValueError("Duplicate daily weather")
        dmap[r["date"]] = r
    keys = [(d, h) for d in demand.dates for h in range(1, 25)]
    if set(hmap) != set(keys) or set(dmap) != set(demand.dates):
        raise ValueError("Weather and demand calendars differ")

    arrays = {
        k: np.empty((n, 24))
        for k in (
            "dry_bulb_c",
            "wet_bulb_c",
            "relative_humidity_pct",
            "dew_point_c",
            "pressure_msl_pa",
        )
    }
    for i, d in enumerate(demand.dates):
        dr = dmap[d]
        if _number(dr, "weather_hours") != 24:
            raise ValueError("Daily weather must summarise 24 hours")
        source_date = date.fromisoformat(d).replace(year=source_year)
        for r in [dr] + [hmap[(d, h)] for h in range(1, 25)]:
            if (
                r["source_date"] != str(source_date)
                or _number(r, "source_weather_year") != source_year
                or _number(r, "station_id") != station_id
            ):
                raise ValueError("Inconsistent station/source date/year")
            for field, values in [
                ("heating_demand_MWth", demand.heat_mw),
                ("cooling_demand_MWcool", demand.cool_mw),
            ]:
                if _number(r, field) != values[i]:
                    raise ValueError("Copied weather demand differs from authoritative demand")
        for h in range(1, 25):
            r = hmap[(d, h)]
            start = datetime.fromisoformat(d).replace(tzinfo=timezone.utc) + timedelta(hours=h - 1)
            end = start + timedelta(hours=1)
            source_end = datetime.combine(
                source_date, datetime.min.time(), timezone.utc
            ) + timedelta(hours=h)
            for field, expected in [
                ("timestamp_start_utc", start),
                ("timestamp_end_utc", end),
                ("source_observation_time_utc", source_end),
            ]:
                if datetime.fromisoformat(r[field].replace("Z", "+00:00")) != expected:
                    raise ValueError(f"Inconsistent UTC interval {d}/{h}: {field}")
            for field, values in arrays.items():
                values[i, h - 1] = _number(r, field)
        for field, stat, dfield in [
            ("dry_bulb_c", np.mean, "dry_bulb_mean_c"),
            ("dry_bulb_c", np.min, "dry_bulb_min_c"),
            ("dry_bulb_c", np.max, "dry_bulb_max_c"),
            ("wet_bulb_c", np.mean, "wet_bulb_mean_c"),
            ("wet_bulb_c", np.min, "wet_bulb_min_c"),
            ("wet_bulb_c", np.max, "wet_bulb_max_c"),
            ("relative_humidity_pct", np.mean, "relative_humidity_mean_pct"),
            ("dew_point_c", np.mean, "dew_point_mean_c"),
            ("pressure_msl_pa", np.mean, "pressure_msl_mean_pa"),
        ]:
            if abs(stat(arrays[field][i]) - _number(dr, dfield)) > 0.000501:
                raise ValueError(f"Daily weather statistic mismatch: {d}/{dfield}")
    if (
        np.any(arrays["wet_bulb_c"] > arrays["dry_bulb_c"] + 0.001)
        or np.any((arrays["relative_humidity_pct"] < 0) | (arrays["relative_humidity_pct"] > 100))
        or np.any(arrays["pressure_msl_pa"] <= 0)
    ):
        raise ValueError("Weather physical range check failed")
    for array in arrays.values():
        array.setflags(write=False)
    return WeatherInputs(
        CoolingWeather(arrays["dry_bulb_c"], arrays["wet_bulb_c"], "hourly", True, source_id),
        CoolingWeather(
            np.array([_number(dmap[d], "dry_bulb_mean_c") for d in demand.dates]),
            np.array([_number(dmap[d], "wet_bulb_mean_c") for d in demand.dates]),
            "daily_screening",
            False,
            source_id,
        ),
        tuple(hmap[k] for k in keys),
        tuple(dmap[d] for d in demand.dates),
        source_id,
    )
