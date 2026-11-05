"""Write De Bilt's hourly wet bulb, 2021-2025, from KNMI's hourly station data (4 Nov).

Free cooling's share of a day is a clipped, nonlinear function of the wet bulb, so a smoothed
year (monthly normals spread over the days) overstates it: the model needs the real hours.

Input: KNMI's hourly data of De Bilt (station 260), "uurgeg_260_2021-2030.txt" from
https://www.knmi.nl/nederland-nu/klimatologie/uurgegevens (KNMI, Uurgegevens van het weer in
Nederland). Its columns: T (dry bulb at 1.5 m) and TD (dew point) in 0.1 °C, P (air pressure
reduced to sea level; De Bilt is 2 m above it) in 0.1 hPa; HH the hour ending, in UT.

The wet bulb is the psychrometric one: the temperature Tw at which
e_s(Tw) - A * P * (T - Tw) = e_s(TD), with the ventilated psychrometer's A = 6.62e-4 1/K and
the saturation pressure over water e_s(t) = 611.2 exp(17.62 t / (243.12 + t)) Pa (Magnus, WMO
2008 CIMO guide, annex 4.B), solved by bisection. A missing hour takes its neighbours' mean.

Output: ``src/dioscuri_plant/data/wet_bulb_de_bilt_2021_2025.csv``: one row a day, the date
then the 24 hours' wet bulb (°C, one decimal, hours ending 01-24 UT); 29 February left out,
so each year has 365 days. Run from the repository root:

    python hackathon/scripts/build_wet_bulb.py path/to/uurgeg_260_2021-2030.txt
"""

import argparse
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "src" / "dioscuri_plant" / "data" / "wet_bulb_de_bilt_2021_2025.csv"
YEARS = range(2021, 2026)
A_PSYCHRO = 6.62e-4  # 1/K, ventilated (Assmann) psychrometer


def saturation_pa(t):
    """Return the saturation vapour pressure over water, Pa (Magnus, WMO 2008)."""
    return 611.2 * np.exp(17.62 * t / (243.12 + t))


def wet_bulb(t, td, p_pa):
    """Return the psychrometric wet bulb (°C) from dry bulb, dew point (°C) and pressure (Pa)."""
    e = saturation_pa(td)
    lo, hi = np.minimum(td, t) - 1.0, np.asarray(t, dtype=float).copy()
    for _ in range(50):  # 50 halvings: far below 0.01 K
        tw = 0.5 * (lo + hi)
        f = saturation_pa(tw) - A_PSYCHRO * p_pa * (t - tw) - e
        hi = np.where(f > 0, tw, hi)
        lo = np.where(f > 0, lo, tw)
    return 0.5 * (lo + hi)


def read(path: Path) -> dict:
    """Return {date: 24 hourly (T, TD, P) rows} for the years wanted, gaps as NaN."""
    cols = None
    days: dict = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        if line.startswith("# STN"):
            cols = [c.strip() for c in line[2:].split(",")]
            continue
        if cols is None or not line.strip().startswith("260,"):
            continue
        f = dict(zip(cols, (s.strip() for s in line.split(","))))
        date, hour = f["YYYYMMDD"], int(f["HH"])
        if int(date[:4]) not in YEARS or date[4:] == "0229":
            continue

        def value(key, scale):
            return float(f[key]) * scale if f.get(key) else np.nan

        row = days.setdefault(date, np.full((24, 3), np.nan))
        row[hour - 1] = (value("T", 0.1), value("TD", 0.1), value("P", 10.0))
    return days


def build(path: Path) -> np.ndarray:
    """Write the CSV and return the wet bulb, (days, 24)."""
    days = read(path)
    dates = sorted(days)
    if len(dates) != 365 * len(YEARS):
        raise SystemExit(f"{len(dates)} days read, {365 * len(YEARS)} expected")
    hourly = np.concatenate([days[d] for d in dates])  # (hours, 3)
    for k in range(3):  # a missing hour: from its neighbours
        x = hourly[:, k]
        gap = np.isnan(x)
        if gap.any():
            x[gap] = np.interp(np.flatnonzero(gap), np.flatnonzero(~gap), x[~gap])
    wb = wet_bulb(hourly[:, 0], np.minimum(hourly[:, 1], hourly[:, 0]), hourly[:, 2])
    wb = np.minimum(wb, hourly[:, 0]).reshape(len(dates), 24)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    head = (
        "# Wet bulb (°C) at De Bilt (KNMI station 260), hourly, 2021-2025; 29 Feb left out.\n"
        "# Source: KNMI, Uurgegevens van het weer in Nederland (T, TD, P); psychrometric wet\n"
        "# bulb (A = 6.62e-4 1/K, Magnus over water). hackathon/scripts/build_wet_bulb.py.\n"
        "date," + ",".join(f"h{h:02d}" for h in range(1, 25)) + "\n"
    )
    rows = [
        f"{d[:4]}-{d[4:6]}-{d[6:]}," + ",".join(f"{v:.1f}" for v in wb[i]) + "\n"
        for i, d in enumerate(dates)
    ]
    OUT.write_text(head + "".join(rows), encoding="utf-8")
    return wb


def main() -> None:
    """Build the file from the KNMI hourly data given."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("knmi", type=Path, help="KNMI hourly file of station 260 (uurgeg_260_...)")
    wb = build(ap.parse_args().knmi)
    print(f"{OUT}: {wb.shape[0]} days, wet bulb {wb.min():.1f} to {wb.max():.1f} °C")


if __name__ == "__main__":
    main()
