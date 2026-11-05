"""Dutch weather at De Bilt (KNMI station 260): a typical year day by day, and real hours.

The plant model must run without weather data (the user, 2 Nov): free cooling, the cooling
check and own solar take this weather when a project has no weather files.

- The typical year (``typical_year``): KNMI climate normals 1991-2020, "klimtab_9120_260"
  (klimaatatlas, stationsdata): each month's mean temperature (°C), mean relative humidity (%)
  and global radiation (kJ/cm² a month), spread over its days by interpolating between the
  months' middles; the wet bulb by Stull (2011); the day's length from the sun's declination
  at 52.1° N. Smooth: right for what is linear in the weather (solar radiation, day length).
- The real hours (``hourly_wet_bulb``): the wet bulb of every hour of 2021-2025 (KNMI,
  Uurgegevens van het weer in Nederland: dry bulb, dew point and pressure, the psychrometric
  wet bulb; ``data/wet_bulb_de_bilt_2021_2025.csv``, built by
  ``hackathon/scripts/build_wet_bulb.py``). For what is clipped or nonlinear in the wet bulb
  (free cooling's share, the towers' limits): a smoothed year never goes above 15.5 °C wet
  bulb and overstates free cooling (4 Nov: 21.0 GWh of 23.7 on the challenge pick, against
  16.9-17.8 GWh hour by hour in 2021-2025).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict

import numpy as np

KNMI_T = (3.6, 3.9, 6.5, 9.8, 13.4, 16.2, 18.3, 17.9, 14.7, 10.9, 7.0, 4.2)
KNMI_RH = (86.7, 84.0, 79.4, 74.0, 73.7, 75.4, 76.5, 78.9, 83.4, 86.2, 89.0, 88.6)
# Global radiation on the horizontal, kJ/cm² a month (364.8 a year: about 1,013 kWh/m²).
KNMI_GLOBAL_KJ_CM2 = (7.3, 12.9, 26.7, 42.4, 54.2, 55.1, 55.3, 46.9, 31.4, 18.8, 8.4, 5.4)
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
LATITUDE_DEG = 52.1
HOURLY_FILE = Path(__file__).resolve().parent / "data" / "wet_bulb_de_bilt_2021_2025.csv"
HOURLY_SOURCE = (
    "De Bilt's wet bulb hour by hour, 2021-2025 (KNMI, Uurgegevens van het weer in Nederland, "
    "station 260: dry bulb, dew point and pressure; psychrometric wet bulb)"
)
TYPICAL_SOURCE = (
    "a typical year at De Bilt: KNMI climate normals 1991-2020 (monthly mean temperature, "
    "relative humidity and global radiation, klimtab_9120_260), spread over the days; wet bulb "
    "by Stull (2011)"
)
SOURCE = (
    "KNMI, De Bilt: the wet bulb hour by hour in 2021-2025 for free cooling and the cooling "
    "towers (KNMI hourly station data, psychrometric wet bulb); the climate normals 1991-2020 "
    "spread over the days for the radiation and the dry bulb"
)


def wet_bulb(t: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Return the wet-bulb temperature (°C) from dry bulb and relative humidity (Stull 2011)."""
    return (
        t * np.arctan(0.151977 * np.sqrt(rh + 8.313659))
        + np.arctan(t + rh)
        - np.arctan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * np.arctan(0.023101 * rh)
        - 4.686035
    )


def _daily(monthly) -> np.ndarray:
    """Return 365 daily values between the months' middles (periodic, linear)."""
    mid = np.cumsum((0,) + MONTH_DAYS[:-1]) + np.array(MONTH_DAYS) / 2.0
    days = np.arange(365) + 0.5
    x = np.concatenate([mid - 365, mid, mid + 365])
    return np.interp(days, x, np.tile(np.asarray(monthly, dtype=float), 3))


def daylight_hours() -> np.ndarray:
    """Return each day's length, hours, at De Bilt's latitude (the sun's declination)."""
    n = np.arange(365) + 1
    decl = np.radians(23.44) * np.sin(2 * np.pi * (284 + n) / 365)
    lat = np.radians(LATITUDE_DEG)
    cos_w = np.clip(-np.tan(lat) * np.tan(decl), -1.0, 1.0)
    return 24.0 * np.arccos(cos_w) / np.pi


@lru_cache(maxsize=1)
def _typical() -> Dict[str, tuple]:
    t = _daily(KNMI_T)
    rh = _daily(KNMI_RH)
    # The month's radiation as a daily mean (kWh/m² a day), then rescaled to the year's total.
    per_day = np.array(KNMI_GLOBAL_KJ_CM2) * 10 / 3.6 / np.array(MONTH_DAYS)
    ghi = _daily(per_day)
    ghi *= sum(KNMI_GLOBAL_KJ_CM2) * 10 / 3.6 / ghi.sum()
    return {
        "dry_bulb_c": tuple(t),
        "wet_bulb_c": tuple(np.minimum(wet_bulb(t, rh), t)),
        "global_kwh_m2": tuple(ghi),
        "daylight_h": tuple(daylight_hours()),
    }


def typical_year() -> Dict[str, np.ndarray]:
    """Return 365 days of dry and wet bulb (°C), global radiation (kWh/m²) and day length (h)."""
    return {k: np.array(v) for k, v in _typical().items()}


@lru_cache(maxsize=1)
def _hourly() -> np.ndarray:
    rows = []
    for line in HOURLY_FILE.read_text(encoding="utf-8").splitlines():
        if line and line[0].isdigit():
            rows.append([float(x) for x in line.split(",")[1:]])
    wb = np.array(rows)  # (years x 365 days, 24 hours)
    years = wb.shape[0] // 365
    # Each calendar day's hours of all the years side by side: (365, years x 24).
    out = wb.reshape(years, 365, 24).transpose(1, 0, 2).reshape(365, years * 24)
    out.setflags(write=False)
    return out


def hourly_wet_bulb() -> np.ndarray:
    """Return the wet bulb (°C) of each calendar day's hours, 2021-2025, as (365, 120).

    Row d holds day d's 24 hours (ending 01-24 UT) of 2021, then of 2022, ... 2025; 29 February
    is left out. Averaging a nonlinear function of the wet bulb over a row gives its expected
    value on that day of a typical year.
    """
    return np.array(_hourly())
