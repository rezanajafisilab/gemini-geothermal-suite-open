"""What failures cost a design a year on average, and what a spare ESP is worth.

Each unit fails ``per_year`` times a year and is out for its repair time (``RATES``; every
figure with its source in ``SOURCES``). A failure costs three things: the extra running cost
while the unit is out (the other units' gas and electricity, and the gas's CO2 at the carbon
price, against the normal year), the heat and cold not delivered (valued per MWh), and the
repair.

What a failure costs depends on when it starts: an ESP lost in January leaves the boiler to
carry the winter; one lost during the doublet's summer stop costs nothing. The expected cost
averages over every start day of the year, and the daily model makes that one run per unit.
With the unit out all year, each day's extra cost is what one day out costs on that day. Days
do not depend on each other: the planned stops stay where they are and nothing stores heat
from one day to the next. So an outage of ``d`` days, averaged over all 365 start days
(wrapping round the year's end), costs ``d / 365`` of the all-year run's extra cost. A repair
shorter than a day counts its share of a day in the same way.

    expected yearly cost of a unit = units x failures a year x (repair days / 365 x
        (extra running cost + MWh not delivered x value, from the all-year run) + repair cost)

This is the first-order expectation. A failure while the unit is still out is not ruled out,
which overstates by about (failures a year x repair time in years): about 16 % for an ESP
without a spare (0.5 a year, 120 days) and under 1 % for the rest. Two units out at once are
not run together.

One cost is not linear in the days out: the electric boiler's grid contract. A boiler that runs
at most 600 hours a year at its peak pays Liander's 600-hour contract; one hour more and the
standard charge applies to the whole year (``economics.grid_capacity_meur``). An outage that
makes the electric boiler carry more can cross that line, so its grid cost is worked out per
start day: the year with the unit out on those days (each day from the all-year run, the others
from the normal year), its electric boiler hours and charge, averaged over every start day and
taken once per failure:

    expected yearly grid cost of a unit = units x failures a year x average over start days of
        (the year's grid charge with that outage - the normal year's)

The 600-hour rule is per connection (its kWh / its peak kW): the backup electric boiler is
assumed to have its own connection, apart from the heat pump, pumps and chillers that run
all year.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Mapping, Optional

import numpy as np

from dioscuri_plant.components import Components
from dioscuri_plant.economics import GRID_600H, Prices, crf, economics, grid_capacity_meur
from dioscuri_plant.firm import NO_SPARE_ESP_DAYS, SPARE_ESP_MEUR, SPARE_ESP_SWAP_DAYS, cases
from dioscuri_plant.types import DAYS, Demand, DoubletModel, Plant, Rules, YearResult
from dioscuri_plant.year import simulate_year

# What heat or cold not delivered is worth. No official Dutch value exists for heat, so the
# default is the lost sale: a floor, not what going without heat costs the people affected.
LOST_EUR_PER_MWH = 122.0
STRESS_EUR_PER_MWH = 10_000.0  # a planning study's penalty, as a stress line
ESP_REPAIR_MEUR = 0.35  # one ESP swap: the pump, pulling the old one and running the new one
SPARE_HOLDING_KEUR = 0.0  # storing and testing a spare ESP: no published figure
# Economics lines that change when a unit is out: fuel, electricity, CO2, variable O&M. Fixed
# O&M and capital belong to the plant as built. The electric boiler's grid charge (a fixed line)
# changes too when an outage pushes it past the 600-hour contract: counted apart (``grid_*``),
# since it is not linear in the days out.
RUNNING_KINDS = ("variable", "electricity", "gas", "carbon")
GRID_LINE = "Electric boiler grid capacity"  # the economics line of the grid charge


@dataclass(frozen=True)
class Rate:
    """How often one unit fails, how long it is out, and what a repair costs.

    ``low`` and ``high`` are the failure rate's range; ``no_spare_days`` is the time out when
    no spare is on the shelf (ESPs only).
    """

    per_year: float
    repair_days: float
    repair_meur: float = 0.0
    low: float = 0.0
    high: float = 0.0
    no_spare_days: Optional[float] = None


RATES: Dict[str, Rate] = {
    "esp": Rate(0.5, SPARE_ESP_SWAP_DAYS, ESP_REPAIR_MEUR, 0.2, 1.0, NO_SPARE_ESP_DAYS),
    "heat exchanger": Rate(0.012, 10.3 / 24, low=0.003, high=0.012),
    "heat pump": Rate(0.046, 14.5 / 24, low=0.046, high=0.146),
    "boiler": Rate(0.042, 3.1 / 24, low=0.042, high=0.129),
    "electric boiler": Rate(0.042, 3.1 / 24, low=0.042, high=0.129),
    "chillers": Rate(0.046, 14.5 / 24, low=0.046, high=0.146),
    "absorption": Rate(0.172, 11.7 / 24, low=0.172, high=0.172),
}

_TM = (
    "US Army TM 5-698-5, Survey of reliability and availability information for power "
    "distribution, power generation and HVAC components (2006), App. B"
)
SOURCES: Dict[str, str] = {
    "esp": (
        "Failures: 0.5 a year (range 0.2-1.0). Dutch geothermal ESPs run 1-2 years on average "
        "(Kombrink, GeoExpro, 14 Apr 2026, from a Dutch ESP workshop); design life 5-7 years "
        "(Shoeibi Omrani, TNO, SPE webinar 9 Oct 2024) gives the low end."
    ),
    "esp_swap_days": (
        f"{SPARE_ESP_SWAP_DAYS} days out with a spare on the shelf: 1-2 weeks with a spare and a "
        "workover unit booked, 2-3 days at best (van 't Spijker & Ungemach, Definition of ESP "
        "design and selection workflow, Kennisagenda Aardwarmte 2016, p.20); Wayland Energy's "
        "pull took 6 days and heat was back a week later (HortiDaily, 14 Sep 2021)"
    ),
    "esp_no_spare_days": (
        f"{NO_SPARE_ESP_DAYS} days out without a spare: 3-6 months to get a new pump (6 months "
        "for a German geothermal well's ESP, Halliburton case study 'Rapid response GeoESP "
        "saves money'); 4 months taken"
    ),
    "esp_repair_meur": (
        f"{ESP_REPAIR_MEUR} M€ per swap (range 0.25-0.5): 190-300 k€ in 2016 € for the pump, "
        "pulling and running in (van 't Spijker & Ungemach 2016, Table 6), about +30 % to "
        "2025 €; Halliburton's ceiling 0.5 M€ per well. Lost heat not included."
    ),
    "spare_esp_meur": (
        f"{SPARE_ESP_MEUR} M€ for the spare pump set: 140-240 k€ in 2016 € (van 't Spijker & "
        "Ungemach 2016, Table 6: 35-60 k€ a year over a 4-year life), about 180-310 k€ in "
        "2025 €; the upper end taken"
    ),
    "spare_esp_holding": (
        "Storing and testing a spare ESP: no published figure found; 0 used. The report "
        "recommends a spare per operator, on site or at the vendor (pp.20-21)."
    ),
    "spare_esp_life": (
        "The spare's price is spread over the doublets' life at the discount rate: once used it "
        "is replaced, so the shelf holds one pump for the project's life"
    ),
    "heat exchanger": (
        f"Heat exchangers (all types): 0.012 failures a year, 10.3 h to repair ({_TM}); plate "
        "exchangers are not listed apart; shell and tube coils 0.003 a year"
    ),
    "heat pump": (
        "No failure rate is published for large heat pumps (Danish Energy Agency 2026, sheet 40: "
        "forced outage 0 %, range 0-5 %). A heat pump is the same machine as an electric "
        f"chiller, so the centrifugal chiller's 0.046 a year and 14.5 h are used ({_TM}); "
        "reciprocating 0.146 a year as the high end"
    ),
    "boiler": (
        f"Hot-water boilers: 0.042 failures a year, 3.1 h to repair, 358 unit-years ({_TM}); "
        "all boilers including steam 0.129 a year (43.3 h) as the high end. Danish Energy "
        "Agency 2026, sheet 44: forced outage 1 %"
    ),
    "electric boiler": (
        "No failure rate is published for electric boilers; the hot-water boiler's 0.042 a "
        f"year and 3.1 h are used ({_TM}). The Danish Energy Agency 2026 gives electric and gas "
        "boilers the same forced outage (1 %)"
    ),
    "chillers": (
        f"Centrifugal electric chillers: 0.046 failures a year, 14.5 h to repair ({_TM}); "
        "reciprocating 0.146 a year (12.1 h) as the high end"
    ),
    "absorption": f"Absorption chillers: 0.172 failures a year, 11.7 h to repair ({_TM})",
    "treatment train": (
        "No failure rate found for a geothermal treatment train (degassing separator and "
        "filters): neither US Army TM 5-698-5 nor DEA 2026 lists one (DEA gives the whole "
        "geothermal plant a 2 % forced outage). Not counted. A shared train out stops every "
        "doublet it serves: it is the case that sizes the gas-free reliable plans"
    ),
    "grid_600h": (
        "Liander 2026: a connection that runs at most 600 hours a year at its peak (its kWh / "
        "its peak kW) pays the 600-hour contract; above that the standard tariff applies to the "
        "whole year. The rule is per connection: the backup electric boiler is assumed to have "
        "its own, apart from the heat pump, pumps and chillers, which run about 8,000 hours a "
        "year"
    ),
    "repairs": (
        "Repairs of the boiler, chillers, heat pump and heat exchanger: no cost per failure "
        "is published; routine repairs are in each unit's fixed O&M, so 0 is added here"
    ),
    "lost_eur_per_mwh": (
        f"{LOST_EUR_PER_MWH:g} €/MWh: the lost sale, ACM's highest variable heat tariff 2026 "
        "(40.97 €/GJ incl. VAT, 121.9 €/MWh excl. VAT). A floor, not the social cost: no "
        "official Dutch value exists for heat not delivered. Production failures are exempt "
        "from outage compensation (Energie-Nederland model Compensatieregeling warmte, art. 3). "
        "Cold is valued the same (no cold tariff found)."
    ),
    "stress_eur_per_mwh": (
        f"{STRESS_EUR_PER_MWH:,.0f} €/MWh: the penalty for unserved heat in a district-heating "
        "planning model (arXiv 2211.00934), meant to make a shortfall a last resort"
    ),
}


def kind(unit: str) -> Optional[str]:
    """Return a ``firm.cases`` outage unit's key in ``RATES``, or None without failure data."""
    if unit.startswith("doublet "):
        return "esp"
    for name in ("electric boiler", "boiler", "chiller"):
        if unit in (name, f"{name} unit", f"{name}s"):
            return "chillers" if name == "chiller" else name
    return unit if unit in ("heat exchanger", "heat pump", "absorption") else None


def count(plant: Plant, unit: str) -> int:
    """Return how many equal units an outage case stands for (one of several out)."""
    if unit.endswith(" unit"):
        attr = unit[: -len(" unit")].replace(" ", "_") + "_units"
        return int(getattr(plant, attr, 1) or 1)
    return 1


def label(plant: Plant, unit: str) -> str:
    """Return a unit as the card shows it: "ESP, doublet 1", "Boiler (3 units)"."""
    if unit.startswith("doublet "):
        return f"ESP, doublet {unit.split()[-1]}"
    names = {
        "heat exchanger": "Heat exchanger",
        "heat pump": "Heat pump",
        "boiler": "Boiler",
        "electric boiler": "Electric boiler",
        "chillers": "Electric chillers",
        "chiller": "Electric chillers",
        "absorption": "Absorption chiller",
    }
    if unit.endswith(" unit"):
        return f"{names[unit[: -len(' unit')]]} ({count(plant, unit)} units)"
    return names.get(unit, unit)


def running_meur(year: YearResult, prices: Prices, rules: Optional[Rules] = None) -> float:
    """Return a year's running cost, M€: fuel, electricity, CO2 and variable O&M."""
    e = economics(year.plant, year, prices, rules=rules)
    return float(sum(m for _, k, m in e.lines if k in RUNNING_KINDS))


def grid_meur(year: YearResult, prices: Prices) -> float:
    """Return a year's electric boiler grid charge, M€ (``economics.grid_capacity_meur``)."""
    return float(grid_capacity_meur(year.plant, year, prices))


def electric_boiler_hours(year: YearResult) -> float:
    """Return the electric boiler's hours a year at its peak, as the 600-hour contract counts.

    Its electricity over the year divided by its largest day's (the model is daily); 0 when
    it never runs.
    """
    daily = np.asarray(year.daily_mw.get("power", {}).get("electric_boiler") or [0.0])
    peak = float(daily.max(initial=0.0))
    return year.electricity_gwh.get("electric_boiler", 0.0) * 1000 / peak if peak > 0 else 0.0


def grid_inputs(
    plant: Plant, base: YearResult, out: YearResult, prices: Prices
) -> Optional[Dict[str, object]]:
    """Return what ``grid_change_meur`` needs for a unit's outage, or None without an e-boiler.

    The electric boiler's electricity day by day in the normal year and with the unit out all
    year, the connection's contracted kW and the two contracts' prices.
    """
    if plant.electric_boiler_mw <= 0:
        return None
    power = "power"
    return {
        "base_mw": list(base.daily_mw.get(power, {}).get("electric_boiler") or [0.0] * DAYS),
        "out_mw": list(out.daily_mw.get(power, {}).get("electric_boiler") or [0.0] * DAYS),
        "contracted_kw": plant.electric_boiler_mw / Components().electric_boiler_efficiency * 1e3,
        "standard_eur_per_kw": prices.electric_boiler_grid_eur_per_kw,
        "h600_eur_per_kw": prices.electric_boiler_grid_600h_eur_per_kw,
        "week_eur_per_kw": prices.electric_boiler_grid_600h_week_eur_per_kw,
    }


def _window_weights(days: float) -> np.ndarray:
    """Return a (DAYS, DAYS) matrix: row s, each day's share of an outage from day s.

    Whole days count 1, a part day its share; an outage runs on past the year's end into its
    start (one contract year, as the start days are averaged round the year).
    """
    days = min(max(float(days), 0.0), float(DAYS))
    whole = int(np.floor(days))
    w = np.zeros(DAYS)
    w[:whole] = 1.0
    if whole < DAYS:
        w[whole] = days - whole
    offset = (np.arange(DAYS)[None, :] - np.arange(DAYS)[:, None]) % DAYS
    return w[offset]


def _grid_charges(daily_mw: np.ndarray, grid: Mapping[str, object]) -> np.ndarray:
    """Return each row's yearly grid charge, M€, from its electric boiler's daily power."""
    peak = daily_mw.max(axis=1)
    hours = np.where(peak > 0, daily_mw.sum(axis=1) * 24 / np.maximum(peak, 1e-12), 0.0)
    weeks = np.maximum.reduceat(daily_mw, np.arange(0, DAYS, 7), axis=1).sum(axis=1) * 1000
    kw = float(grid["contracted_kw"])
    standard = float(grid["standard_eur_per_kw"]) * kw / 1e6
    h600 = (float(grid["h600_eur_per_kw"]) * kw + float(grid["week_eur_per_kw"]) * weeks) / 1e6
    return np.where(hours > GRID_600H, standard, h600)


def grid_change_meur(grid: Optional[Mapping[str, object]], days: float) -> float:
    """Return what one outage of ``days`` adds to the year's grid charge, M€, on average.

    For every start day the year is the normal one with the outage's days from the all-year
    run; its electric boiler hours decide the contract (``GRID_600H``). The average over the
    start days less the normal year's charge; 0 without an electric boiler.
    """
    if not grid or days <= 0:
        return 0.0
    base = np.asarray(grid["base_mw"], dtype=float)
    out = np.asarray(grid["out_mw"], dtype=float)
    daily = base[None, :] + _window_weights(days) * (out - base)[None, :]
    return float(_grid_charges(daily, grid).mean() - _grid_charges(base[None, :], grid)[0])


def grid_break_share(grid: Optional[Mapping[str, object]], days: float) -> float:
    """Return the share of start days on which an outage of ``days`` breaks the 600 hours."""
    if not grid or days <= 0:
        return 0.0
    base = np.asarray(grid["base_mw"], dtype=float)
    out = np.asarray(grid["out_mw"], dtype=float)
    daily = base[None, :] + _window_weights(days) * (out - base)[None, :]
    peak = daily.max(axis=1)
    hours = np.where(peak > 0, daily.sum(axis=1) * 24 / np.maximum(peak, 1e-12), 0.0)
    return float(np.mean(hours > GRID_600H))


def _short_mwh(year: YearResult, side: str) -> float:
    return float(np.sum(year.daily_mw[side]["short"])) * 24.0


def outage_runs(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
    prices: Prices = Prices(),
    base: Optional[YearResult] = None,
) -> List[Dict[str, object]]:
    """Run the year with each unit out all year, against the normal year.

    One run per ``firm.cases`` unit (each doublet, the heat exchanger, the heat pump, a boiler
    or chiller unit ...); a unit without failure data is listed with ``kind`` None.

    Parameters
    ----------
    plant, demand, doublet, rules, components, prices
        The design and its conditions.
    base : YearResult, optional
        The design's normal year, when already run.

    Returns
    -------
    list of dict
        Per unit: ``unit``, ``name`` (in words), ``kind`` (key of ``RATES``), ``count`` (equal
        units), ``label``, and over the whole year out: ``running_meur`` (extra running cost),
        ``heat_mwh`` and ``cold_mwh`` (not delivered, beyond the normal year's), and ``grid``
        (``grid_inputs``: None without an electric boiler).
    """
    base = base or simulate_year(plant, demand, doublet, rules, components)
    base_cost = running_meur(base, prices, rules)
    heat0, cold0 = _short_mwh(base, "heat"), _short_mwh(base, "cool")
    out: List[Dict[str, object]] = []
    for name, unit in cases(plant):
        row: Dict[str, object] = {"unit": unit, "name": name, "kind": kind(unit)}
        if row["kind"] is not None:
            out_all_year = replace(plant, outages=tuple(plant.outages) + ((unit, 0, DAYS - 1),))
            y = simulate_year(out_all_year, demand, doublet, rules, components)
            row.update(
                count=count(plant, unit),
                label=label(plant, unit),
                running_meur=running_meur(y, prices, rules) - base_cost,
                heat_mwh=max(_short_mwh(y, "heat") - heat0, 0.0),
                cold_mwh=max(_short_mwh(y, "cool") - cold0, 0.0),
                grid=grid_inputs(plant, base, y, prices),
            )
        out.append(row)
    return out


def words(run: Dict[str, object]) -> str:
    """Return a unit of ``outage_runs`` in words, all its equal units together."""
    unit = str(run["unit"])
    if run["kind"] == "esp":
        return f"the ESP of {unit}"
    if unit.endswith(" unit"):
        return f"the {run['count']} {unit[: -len(' unit')]} units"
    return str(run["name"])


def _r(x: float, digits: int) -> float:
    return round(x, digits) + 0.0  # no "-0.0" for a tiny saving


def _rates(rates: Optional[Mapping[str, Rate]]) -> Dict[str, Rate]:
    return {**RATES, **(rates or {})}


def expected_cost(
    runs: List[Dict[str, object]],
    lost_eur_per_mwh: float = LOST_EUR_PER_MWH,
    spare_esp: bool = False,
    rates: Optional[Mapping[str, Rate]] = None,
    stress_eur_per_mwh: float = STRESS_EUR_PER_MWH,
) -> Dict[str, object]:
    """Return the expected yearly cost of failures from ``outage_runs``, per unit and in all.

    Parameters
    ----------
    runs : list of dict
        ``outage_runs`` of the design.
    lost_eur_per_mwh : float
        What a MWh of heat or cold not delivered is worth.
    spare_esp : bool
        A spare ESP is on the shelf: a doublet is out for the swap, not the wait for a pump.
    rates : dict of Rate, optional
        Failure rates replacing ``RATES`` by key.
    stress_eur_per_mwh : float
        The value of lost heat for the stress line.

    Returns
    -------
    dict
        ``units`` (largest first: ``unit``, ``label``, ``words``, ``count``, ``per_year``,
        ``repair_days``, ``failures_per_year``, ``out_days`` a year, ``running_keur``,
        ``grid_keur`` (the grid charge when an outage breaks the 600-hour contract),
        ``grid_break_share`` (of start days), ``lost_mwh``, ``lost_keur``, ``repair_keur``,
        ``total_keur``, ``stress_keur``), ``total_keur``, ``grid_keur``, ``range_keur`` (each
        unit at its low and high failure rate),
        ``lost_mwh``, ``lost_heat_mwh``, ``lost_cold_mwh``, ``stress_keur``, ``skipped`` (units
        without failure data, in words), ``lost_eur_per_mwh``, ``stress_eur_per_mwh``,
        ``spare_esp``.
    """
    table = _rates(rates)
    units, skipped = [], []
    low = high = 0.0
    heat = cold = 0.0
    for r in runs:
        if r["kind"] is None:
            skipped.append(str(r["name"]))
            continue
        rate = table[str(r["kind"])]
        days = rate.repair_days
        if rate.no_spare_days is not None and not spare_esp:
            days = rate.no_spare_days
        n = int(r["count"]) * rate.per_year  # failures a year
        share = n * days / DAYS  # the all-year run's share
        h, c = share * float(r["heat_mwh"]), share * float(r["cold_mwh"])
        running = share * float(r["running_meur"]) * 1000
        grid = n * grid_change_meur(r.get("grid"), days) * 1000  # once per failure, not linear
        repair = n * rate.repair_meur * 1000
        total = running + grid + (h + c) * lost_eur_per_mwh / 1000 + repair
        heat, cold = heat + h, cold + c
        if rate.per_year > 0:
            low += total * rate.low / rate.per_year
            high += total * rate.high / rate.per_year
        units.append(
            {
                "unit": r["unit"],
                "label": r["label"],
                "words": words(r),
                "count": r["count"],
                "per_year": rate.per_year,
                "repair_days": _r(days, 3),
                "failures_per_year": _r(n, 4),
                "out_days": _r(n * days, 3),
                "running_keur": _r(running, 2),
                "grid_keur": _r(grid, 2),
                "grid_break_share": _r(grid_break_share(r.get("grid"), days), 3),
                "lost_mwh": _r(h + c, 2),
                "lost_keur": _r((h + c) * lost_eur_per_mwh / 1000, 2),
                "repair_keur": _r(repair, 2),
                "total_keur": _r(total, 2),
                "stress_keur": _r(running + grid + (h + c) * stress_eur_per_mwh / 1000 + repair, 2),
            }
        )
    units.sort(key=lambda u: -float(u["total_keur"]))
    total = sum(float(u["total_keur"]) for u in units)
    return {
        "units": units,
        "total_keur": round(total, 1),
        "grid_keur": round(sum(float(u["grid_keur"]) for u in units), 1),
        "range_keur": [round(low, 1), round(high, 1)],
        "lost_mwh": round(heat + cold, 1),
        "lost_heat_mwh": round(heat, 1),
        "lost_cold_mwh": round(cold, 1),
        "stress_keur": round(sum(float(u["stress_keur"]) for u in units), 1),
        "skipped": skipped,
        "lost_eur_per_mwh": lost_eur_per_mwh,
        "stress_eur_per_mwh": stress_eur_per_mwh,
        "spare_esp": spare_esp,
    }


def spare_yearly_keur(
    prices: Prices = Prices(),
    price_meur: float = SPARE_ESP_MEUR,
    holding_keur: float = SPARE_HOLDING_KEUR,
) -> float:
    """Return a spare ESP's yearly cost, k€: its price over the doublets' life, plus holding."""
    return price_meur * crf(prices.discount_rate, prices.wells_life_years) * 1000 + holding_keur


def spare_esp_worth(
    runs: List[Dict[str, object]],
    prices: Prices = Prices(),
    lost_eur_per_mwh: float = LOST_EUR_PER_MWH,
    rates: Optional[Mapping[str, Rate]] = None,
    price_meur: float = SPARE_ESP_MEUR,
    holding_keur: float = SPARE_HOLDING_KEUR,
    stress_eur_per_mwh: float = STRESS_EUR_PER_MWH,
) -> Optional[Dict[str, object]]:
    """Return what a spare ESP on the shelf is worth a year, or None without doublets.

    It saves the days between the swap and the wait for a new pump at each failure, on every
    doublet (one spare fits them all; two failing at once are not counted), and the grid charge
    those days would add by pushing the electric boiler past the 600-hour contract. The pump
    bought at each failure is the same with or without it, so the repair cost drops out. Its
    cost is ``spare_yearly_keur``.

    Returns
    -------
    dict
        ``per_year`` (ESP failures a year per doublet), ``swap_days``, ``no_spare_days``,
        ``price_meur``, ``yearly_keur`` (its cost), ``holding_keur``, ``saving_keur`` (failure
        costs it saves), ``saving_mwh`` (heat and cold it keeps delivered), ``net_keur``,
        ``worth`` (net above 0), ``break_even_per_year`` (the failure rate where it pays; None
        when it never does), ``stress_net_keur`` (lost heat at the stress value), ``range``
        (``low`` and ``high``: the failure rate and the net).
    """
    esp = _rates(rates)["esp"]
    doublets = [r for r in runs if r["kind"] == "esp"]
    if not doublets or esp.no_spare_days is None:
        return None
    gap = (esp.no_spare_days - esp.repair_days) / DAYS
    lost = sum(float(r["heat_mwh"]) + float(r["cold_mwh"]) for r in doublets)
    running = sum(float(r["running_meur"]) for r in doublets) * 1000
    grid = 1000 * sum(  # the grid charge a failure adds without the spare, less with it
        grid_change_meur(r.get("grid"), esp.no_spare_days)
        - grid_change_meur(r.get("grid"), esp.repair_days)
        for r in doublets
    )
    per_rate = gap * (running + lost * lost_eur_per_mwh / 1000) + grid  # k€ per failure a year
    per_rate_stress = gap * (running + lost * stress_eur_per_mwh / 1000) + grid
    cost = spare_yearly_keur(prices, price_meur, holding_keur)
    lam = esp.per_year
    return {
        "per_year": lam,
        "swap_days": esp.repair_days,
        "no_spare_days": esp.no_spare_days,
        "price_meur": price_meur,
        "life_years": prices.wells_life_years,
        "discount_rate": prices.discount_rate,
        "yearly_keur": round(cost, 1),
        "holding_keur": holding_keur,
        "saving_keur": round(lam * per_rate, 1),
        "saving_mwh": round(lam * gap * lost, 1),
        "net_keur": round(lam * per_rate - cost, 1),
        "worth": lam * per_rate > cost,
        "break_even_per_year": round(cost / per_rate, 4) if per_rate > 0 else None,
        "stress_net_keur": round(lam * per_rate_stress - cost, 1),
        "range": {
            "low": {"per_year": esp.low, "net_keur": round(esp.low * per_rate - cost, 1)},
            "high": {"per_year": esp.high, "net_keur": round(esp.high * per_rate - cost, 1)},
        },
    }


def failure_costs(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
    prices: Prices = Prices(),
    lost_eur_per_mwh: float = LOST_EUR_PER_MWH,
    rates: Optional[Mapping[str, Rate]] = None,
    base: Optional[YearResult] = None,
) -> Dict[str, object]:
    """Return what failures cost a design a year on average, and what a spare ESP is worth.

    Parameters
    ----------
    plant, demand, doublet, rules, components, prices
        The design and its conditions.
    lost_eur_per_mwh : float
        What a MWh of heat or cold not delivered is worth (default: the lost sale, a floor).
    rates : dict of Rate, optional
        Failure rates replacing ``RATES`` by key.
    base : YearResult, optional
        The design's normal year, when already run.

    Returns
    -------
    dict
        ``expected_cost`` without a spare ESP (as designed: no spare is in the capital), plus
        ``with_spare`` (the same with one: ``total_keur``, ``lost_mwh``, ``units``),
        ``spare_esp`` (``spare_esp_worth``) and ``notes`` (what is and is not counted).
    """
    base = base or simulate_year(plant, demand, doublet, rules, components)
    runs = outage_runs(plant, demand, doublet, rules, components, prices, base)
    out = expected_cost(runs, lost_eur_per_mwh, False, rates)
    spare = expected_cost(runs, lost_eur_per_mwh, True, rates)
    out["with_spare"] = {
        k: spare[k] for k in ("total_keur", "lost_mwh", "stress_keur", "units", "grid_keur")
    }
    out["spare_esp"] = spare_esp_worth(runs, prices, lost_eur_per_mwh, rates)
    notes = [
        f"heat and cold not delivered valued at {lost_eur_per_mwh:g} €/MWh"
        + (", the lost sale: a floor, not the social cost" if lost_eur_per_mwh <= 200 else ""),
        "only the ESP swap has a repair cost; the other units' repairs are in their fixed O&M",
        "the ESP swaps overlap PBL's ESP provision in the geothermal fixed O&M, so this is "
        "not added to the cost of heat",
    ]
    out["grid"] = None
    if plant.electric_boiler_mw > 0:
        hours = electric_boiler_hours(base)
        out["grid"] = {
            "hours": round(hours, 1),
            "limit_hours": GRID_600H,
            "hours_left": round(GRID_600H - hours, 1),
            "contract": "600-hour" if hours <= GRID_600H else "standard",
            "meur": round(grid_meur(base, prices), 3),
        }
        if hours <= GRID_600H:
            notes.append(
                f"the electric boiler runs {hours:,.0f} hours a year at its peak, "
                f"{GRID_600H - hours:,.0f} under the grid's 600-hour contract; an outage that "
                "pushes it past 600 loses the contract for the whole year: counted per start "
                f"day ({out['grid_keur']:,.0f} k€ a year on average without a spare ESP, "
                f"{spare['grid_keur']:,.0f} k€ with one). The 600 hours are per connection: the "
                "backup electric boiler is assumed to have its own"
            )
    if out["skipped"]:
        notes.append(
            "no failure data, not counted: "
            + ", ".join(out["skipped"])
            + (
                " (no published failure rate for a treatment train)"
                if any("train" in x for x in out["skipped"])
                else ""
            )
        )
    out["notes"] = notes
    return out
