"""Write the daily demand of the two real-project districts (Trias Westland, HAL Leyweg).

Neither project publishes a daily demand. Each profile takes its shape from the challenge
district's 2027 heat profile (its day-to-day swings come from a real year's weather) and is
scaled to a stated yearly total:

- HAL Leyweg (The Hague): 4,000 homes (the city's figure for the network's growth) at 12 MWh
  of heat a home a year (CBS: about 1,200 m3 of gas a home), 48 GWh.
- Trias Westland: the second doublet's 30 growers on about 100 ha of greenhouses (Trias
  Westland's expansion, ThinkGeoEnergy 2020). A greenhouse also needs heat in summer (nights,
  dehumidifying): 40 % of each day's heat is a constant base, 60 % follows the challenge
  shape. 1.0 GJ per m2 a year is assumed (no published figure was found), 278 GWh.

Neither has cooling. Run from the repository root:

    PYTHONPATH=src python hackathon/scripts/make_real_projects.py
"""

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src" / "gemini_agent" / "data"


def shape() -> tuple:
    """Return the challenge's dates and its heat profile scaled to a mean of 1."""
    import dioscuri_plant as dp

    d = dp.Demand.from_csv(
        DATA / "challenge" / "GEMINI_Heating_Demand_Daily_2027.csv",
        DATA / "challenge" / "GEMINI_Cooling_Demand_Daily_2027.csv",
    )
    heat = np.asarray(d.heat_mw, dtype=float)
    return d.dates, heat / heat.mean()


def write(folder: str, name: str, dates, mw: np.ndarray) -> None:
    """Write a heat profile and an all-zero cooling profile, as the challenge's files are."""
    out = DATA / folder
    lines = ["date,heating_demand_MWth"] + [f"{d},{x:.4f}" for d, x in zip(dates, mw)]
    (out / f"{name}_Heating_Demand_Daily_2027.csv").write_text("\n".join(lines) + "\n")
    lines = ["date,cooling_demand_MWcool"] + [f"{d},0.0000" for d in dates]
    (out / f"{name}_Cooling_Demand_Daily_2027.csv").write_text("\n".join(lines) + "\n")
    print(f"{folder}: {mw.sum() * 24 / 1000:.1f} GWh, peak {mw.max():.1f} MW")


def main() -> None:
    """Write both projects' profiles."""
    dates, s = shape()
    hal_gwh = 4000 * 12.0 / 1000
    write("hal_leyweg", "HAL_Leyweg", dates, s * hal_gwh * 1000 / 8760)
    trias_gwh = 100 * 10_000 * 1.0 / 3.6 / 1000  # 100 ha at 1.0 GJ/m2 -> GWh
    greenhouse = 0.4 + 0.6 * s
    write("trias_westland", "Trias_Westland", dates, greenhouse * trias_gwh * 1000 / 8760)


if __name__ == "__main__":
    main()
