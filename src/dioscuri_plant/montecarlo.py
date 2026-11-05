"""Unplanned outages over many years: random failures, each year run, and the worst case.

``failure_costs`` gives the average yearly cost of failures, one unit at a time. This draws
whole years instead (2 Nov): every unit of the design fails at random through the year at its
rate (``failure_costs.RATES``, each with its source), each failure starting on a random day and
lasting its repair time. Each year with failures is run with those units out, so two at once
and a failure in the coldest week count as they happen. Over 1,000 years this gives how often
heat runs short, how much, and what the failures add to the running cost: the spread, not only
the mean.

A failure shorter than a day (most repairs take hours) puts the unit out for that whole day
with the chance hours / 24, so the days out are right on average at the daily resolution. Two
units of one bank (two of three boilers) out on the same day count as one out: the year model
takes one unit of a bank out at a time; with failure rates of 0.04 a year this is about one
year in ten thousand.

The worst case is set apart: a doublet lost for 35 days (its ESP failed with no workover rig
free, or the yearly stop's length) in the coldest five weeks of the year.

A spare ESP: no design pays for one (``failure_costs`` calls the case without a spare "as
designed"), so the years are drawn without one unless asked: a failed ESP keeps its doublet out
``firm.NO_SPARE_ESP_DAYS`` (120 days), not the ``firm.SPARE_ESP_SWAP_DAYS`` (7 days) of a swap
from the shelf. Until 4 Nov ``lole`` always drew with a spare, so the risk-based backup was
sized for 7-day ESP outages while the design had none.

What a drawn year costs counts the electric boiler's grid charge too: an outage that makes the
electric boiler run past the 600-hour contract puts the whole year on the standard charge
(``economics.grid_capacity_meur``; ``failure_costs`` counts it the same way). Until 4 Nov only
the running cost was counted here, and a gas-free design's failures looked half as dear.

A shared treatment train has no published failure rate (``failure_costs.SOURCES``) and is not
drawn: its outages are in neither the drawn years nor the days short.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Dict, List, Optional, Tuple

import numpy as np

from dioscuri_plant.components import Components
from dioscuri_plant.failure_costs import (
    LOST_EUR_PER_MWH,
    RATES,
    Rate,
    grid_meur,
    kind,
    running_meur,
)
from dioscuri_plant.firm import NO_SPARE_ESP_DAYS, cases
from dioscuri_plant.parallel import pmap
from dioscuri_plant.types import DAYS, Demand, DoubletModel, Plant, Rules, YearResult
from dioscuri_plant.year import simulate_year

YEARS = 1000
WORST_DAYS = 35
Outage = Tuple[str, int, int]


def _units(plant: Plant) -> List[Tuple[str, Rate]]:
    """Return each unit that can fail, once per physical unit, with its rate."""
    out = []
    for _, unit in cases(plant):
        k = kind(unit)
        if k is None:
            continue
        n = 1
        if unit.endswith(" unit"):
            n = int(getattr(plant, unit[: -len(" unit")].replace(" ", "_") + "_units", 1) or 1)
        out += [(unit, RATES[k])] * n
    return out


def not_drawn(plant: Plant) -> List[str]:
    """Return the design's units that are never drawn, in words: those with no failure rate.

    A treatment train shared by several doublets (``firm.cases``): no published rate.
    """
    return [name for name, unit in cases(plant) if kind(unit) is None]


def draw_years(
    plant: Plant, years: int = YEARS, seed: int = 11, spare_esp: bool = False
) -> List[Tuple[Tuple[Outage, ...], float, Dict[str, int]]]:
    """Return each drawn year: its outages (unit, first day, last day), repairs (M€), failures.

    A failure's start is any day of the year; one that runs past 31 December goes on from
    1 January of the same drawn year (each year stands for a typical one). ``spare_esp``: a
    spare ESP on the shelf, so a failed ESP is out for the swap, not the wait for a new pump
    (the design has none unless it says so).
    """
    rng = np.random.default_rng(seed)
    units = _units(plant)
    out = []
    for _ in range(years):
        events: List[Outage] = []
        repairs, failed = 0.0, {}
        for unit, rate in units:
            for _ in range(rng.poisson(rate.per_year)):
                repairs += rate.repair_meur
                failed[unit] = failed.get(unit, 0) + 1
                days = rate.repair_days
                if unit.startswith("doublet ") and not spare_esp:
                    days = float(rate.no_spare_days or NO_SPARE_ESP_DAYS)
                whole = int(math.floor(days)) + (1 if rng.random() < days - math.floor(days) else 0)
                if whole <= 0:
                    continue
                start = int(rng.integers(0, DAYS))
                end = start + whole - 1
                if end < DAYS:
                    events.append((unit, start, end))
                else:
                    events += [(unit, start, DAYS - 1), (unit, 0, min(end - DAYS, DAYS - 1))]
        out.append((tuple(events), repairs, failed))
    return out


def _short(year: YearResult, side: str) -> float:
    return float(np.sum(year.daily_mw[side]["short"])) * 24.0


def _year_with(state: dict, events: Tuple[Outage, ...]) -> Tuple[float, float, float, float]:
    """Return a drawn year's heat and cold not delivered (MWh), running cost and grid charge (M€).

    The grid charge is the electric boiler's (``failure_costs.grid_meur``): it jumps to the
    standard contract for the whole year when the outages push the boiler past 600 hours.
    """
    plant = replace(state["plant"], outages=tuple(state["plant"].outages) + events)
    y = simulate_year(plant, state["demand"], state["doublet"], state["rules"], state["components"])
    running = running_meur(y, state["prices"], state["rules"])
    return _short(y, "heat"), _short(y, "cool"), running, grid_meur(y, state["prices"])


def coldest_window(demand: Demand, days: int = WORST_DAYS) -> int:
    """Return the first day of the ``days`` in a row with the most heat demand."""
    heat = np.asarray(demand.heat_mw, dtype=float)
    sums = np.convolve(heat, np.ones(days), mode="valid")
    return int(np.argmax(sums))


def _stats(x: np.ndarray) -> Dict[str, float]:
    return {
        "mean": float(np.mean(x)),
        "p50": float(np.percentile(x, 50)),
        "p90": float(np.percentile(x, 90)),
        "p99": float(np.percentile(x, 99)),
        "max": float(np.max(x)),
        "share_above_zero": float(np.mean(x > 0.5)),
    }


def unplanned(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules,
    prices,
    components: Components = Components(),
    years: int = YEARS,
    seed: int = 11,
    spare_esp: bool = False,
) -> dict:
    """Return the design's drawn years: heat and cold short, extra running cost, the worst case.

    ``spare_esp``: a spare ESP on the shelf (a doublet out 7 days, not 120); the design has none.

    Returns
    -------
    dict
        ``years``; ``heat_mwh``, ``cold_mwh``, ``extra_keur`` (running cost and the electric
        boiler's grid charge, against the year without failures), ``grid_keur`` (the grid
        charge alone), ``repair_keur``, ``total_keur`` (``_stats`` of each: mean, p50, p90,
        p99, max, share of years above zero); ``histogram`` of heat short (bins in MWh and the
        years in each); ``failures`` (mean failures a year by unit); ``worst`` (a doublet out
        35 days from the coldest window's first day: heat short MWh, extra cost); ``lost_keur``
        (the mean heat and cold short at the lost-sale value); ``not_drawn`` (units with no
        failure rate, in words: a shared treatment train).
    """
    base = simulate_year(plant, demand, doublet, rules, components)
    base_cost = running_meur(base, prices, rules)
    base_grid = grid_meur(base, prices)
    heat0, cold0 = _short(base, "heat"), _short(base, "cool")
    drawn = draw_years(plant, years, seed, spare_esp)
    state = {
        "plant": plant,
        "demand": demand,
        "doublet": doublet,
        "rules": rules,
        "components": components,
        "prices": prices,
    }
    todo = sorted({ev for ev, _, _ in drawn if ev})
    runs = dict(zip(todo, pmap(_year_with, todo, state, min_items=64)))
    heat, cold, extra, grid, repair = [], [], [], [], []
    by_unit: Dict[str, float] = {}
    for ev, repairs, failed in drawn:
        h, c, cost, charge = runs[ev] if ev else (heat0, cold0, base_cost, base_grid)
        heat.append(max(h - heat0, 0.0))
        cold.append(max(c - cold0, 0.0))
        grid.append((charge - base_grid) * 1000)
        extra.append((cost - base_cost + charge - base_grid) * 1000)
        repair.append(repairs * 1000)
        for unit, n in failed.items():
            by_unit[unit] = by_unit.get(unit, 0.0) + n / years
    heat_a, cold_a, extra_a, grid_a = (
        np.array(heat),
        np.array(cold),
        np.array(extra),
        np.array(grid),
    )
    repair_a = np.array(repair)
    top = float(heat_a.max())
    # Years with no heat short in the first bin; the rest in ten bins up to the worst year.
    edges = np.array([0.0, 0.5]) if top <= 0.5 else np.linspace(0.5, top, 11)
    edges = np.concatenate([[0.0], edges]) if top > 0.5 else edges
    counts, _ = np.histogram(heat_a, bins=edges)
    worst: Optional[dict] = None
    if plant.n_doublets:
        start = coldest_window(demand)
        events = (("doublet 1", start, min(start + WORST_DAYS - 1, DAYS - 1)),)
        h, c, cost, charge = _year_with(state, events)
        worst = {
            "unit": "doublet 1",
            "days": WORST_DAYS,
            "first_day": start,
            "heat_mwh": max(h - heat0, 0.0),
            "cold_mwh": max(c - cold0, 0.0),
            "extra_keur": (cost - base_cost + charge - base_grid) * 1000,
            "grid_keur": (charge - base_grid) * 1000,
        }
    return {
        "years": years,
        "spare_esp": spare_esp,
        "heat_mwh": _stats(heat_a),
        "cold_mwh": _stats(cold_a),
        "extra_keur": _stats(extra_a),
        "grid_keur": _stats(grid_a),
        "repair_keur": _stats(repair_a),
        # What the failures cost a year: running cost, repairs, heat and cold at the lost sale.
        "total_keur": _stats(extra_a + repair_a + (heat_a + cold_a) * LOST_EUR_PER_MWH / 1000),
        "lost_keur": float((heat_a.mean() + cold_a.mean()) * LOST_EUR_PER_MWH / 1000),
        "histogram": {"edges_mwh": [float(x) for x in edges], "years": [int(x) for x in counts]},
        "failures": {k: round(v, 3) for k, v in sorted(by_unit.items())},
        "not_drawn": not_drawn(plant),
        "worst": worst,
    }


# The risk-based criterion (3 Nov): at most one day short of heat in ten years, the "one day in
# ten years" loss-of-load expectation that power systems plan their reserve to (LOLE 0.1 day a
# year). N-1 sizes the backup for the largest unit out on the coldest day, however unlikely that
# is; this sizes it for what the drawn years show.
LOLE_TARGET_DAYS = 0.1


def _days_short(state: dict, events: Tuple[Outage, ...]) -> Tuple[int, float]:
    """Return a drawn year's days short of heat and its heat not delivered (MWh)."""
    plant = replace(state["plant"], outages=tuple(state["plant"].outages) + events)
    y = simulate_year(plant, state["demand"], state["doublet"], state["rules"], state["components"])
    short = np.asarray(y.daily_mw["heat"]["short"], dtype=float)
    return int(np.sum(short > 0.01)), float(np.sum(short)) * 24.0


def lole(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules,
    components: Components = Components(),
    years: int = YEARS,
    seed: int = 11,
    spare_esp: bool = False,
) -> Dict[str, float]:
    """Return the days short of heat a year (LOLE) and the heat not delivered (EENS, MWh a year).

    Over the drawn years of ``draw_years`` (each unit failing at its rate; a failed ESP out
    120 days, or 7 with ``spare_esp``); a year without failures counts as the design's own year
    (zero when it meets every day).
    """
    state = {"plant": plant, "demand": demand, "doublet": doublet, "rules": rules}
    state["components"] = components
    base_days, base_mwh = _days_short(state, ())
    drawn = draw_years(plant, years, seed, spare_esp)
    todo = sorted({ev for ev, _, _ in drawn if ev})
    runs = dict(zip(todo, pmap(_days_short, todo, state, min_items=64)))
    days = [runs[ev][0] if ev else base_days for ev, _, _ in drawn]
    mwh = [runs[ev][1] if ev else base_mwh for ev, _, _ in drawn]
    return {
        "lole_days": float(np.mean(days)),
        "eens_mwh": float(np.mean(mwh)),
        "years_short": float(np.mean(np.array(days) > 0)),
        "base_days": base_days,
    }


def backup_of(plant: Plant) -> str:
    """Return the size key of a design's backup boiler: the one risk sizing shrinks.

    The gas boiler when the plant buys gas (the electric boiler when it has no gas boiler).
    With no gas bought (``gas`` "produced" or "sell") the gas boiler burns only the brine's gas
    and cannot back anything up: the electric boiler is the backup, as in ``firm.reliable``.
    Until 4 Nov the gas boiler was taken whenever there was one, and a gas-free design's
    5.5 MW brine-gas boiler was shrunk while its 25 MW electric backup was never sized.
    """
    if plant.gas != "buy":
        return "electric_boiler_mw"
    return "boiler_mw" if plant.boiler_mw > 0 else "electric_boiler_mw"


def risk_sizing(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules,
    components: Components = Components(),
    target_days: float = LOLE_TARGET_DAYS,
    years: int = YEARS,
    steps: int = 6,
    spare_esp: bool = False,
) -> Optional[dict]:
    """Return the smallest backup boiler that keeps the days short within ``target_days``.

    The backup is the unit ``backup_of`` names: the gas boiler when the plant buys gas, else
    the electric boiler. Its size is halved towards the smallest that still meets every day of
    the design's own year, by bisection over ``steps`` sizes; each is run over the same drawn
    years, with the spare ESP state ``spare_esp`` (none, as designed, unless asked). None when
    the design has no backup boiler.

    Returns
    -------
    dict
        ``unit``, ``n1_mw`` (the design's size), ``risk_mw`` (the smallest meeting the target),
        ``target_days``, ``spare_esp``, ``at_n1`` and ``at_risk`` (``lole`` of each),
        ``tried`` (each size's days short a year) and ``not_drawn`` (``not_drawn``).
    """
    attr = backup_of(plant)
    n1 = float(getattr(plant, attr))
    if n1 <= 0:
        return None

    def at(size: float) -> Dict[str, float]:
        return lole(
            replace(plant, **{attr: size}),
            demand,
            doublet,
            rules,
            components,
            years,
            spare_esp=spare_esp,
        )

    top = at(n1)
    tried = [(n1, top)]
    if top["lole_days"] > target_days:  # even the design's own backup misses the target
        return {
            "unit": attr,
            "n1_mw": n1,
            "risk_mw": n1,
            "target_days": target_days,
            "spare_esp": spare_esp,
            "not_drawn": not_drawn(plant),
            "at_n1": top,
            "at_risk": top,
            "tried": [[round(s, 2), r["lole_days"]] for s, r in tried],
        }
    lo, hi, best = 0.0, n1, (n1, top)
    for _ in range(steps):
        mid = (lo + hi) / 2.0
        r = at(mid)
        tried.append((mid, r))
        if r["base_days"] == 0 and r["lole_days"] <= target_days:
            hi, best = mid, (mid, r)
        else:
            lo = mid
    return {
        "unit": attr,
        "n1_mw": n1,
        "risk_mw": round(best[0], 2),
        "target_days": target_days,
        "spare_esp": spare_esp,
        "not_drawn": not_drawn(plant),
        "at_n1": top,
        "at_risk": best[1],
        "tried": [[round(s, 2), r["lole_days"]] for s, r in sorted(tried)],
    }
