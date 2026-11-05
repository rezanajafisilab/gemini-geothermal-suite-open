"""The plant over a year: what runs each day, at daily resolution (365 steps).

Heating (network from its return to 100 °C, every day):

1. The brine preheats the network in a counterflow heat exchanger, to the wellhead
   temperature minus the approach (about 81 °C). Brine flow is set to balance the exchanger
   (brine and network heat-capacity rates equal), so the brine leaves at the network return
   plus the approach.
2. The top-up to 100 °C comes from the heat pump, whose evaporator cools the brine further
   (never more than 40 K below the wellhead, the challenge's cap), then the boiler.
3. When the doublets cannot carry the network's flow (peak days, stops), the rest of the
   network bypasses them and the boiler heats it from the return.

Cooling (network from its return to 20 °C): free cooling on the towers when it is on, then
the absorption chiller, driven by brine that bypasses the heat exchanger (and then feeds the
heat pump's evaporator) when the brine is hot enough for its hot-water loop
(``Components.absorption_min_drive_c``, 80 °C), then the electric chillers. Every MW the
towers reject (free cooling, the chillers' cold and electricity, the absorption chiller's cold
and driving heat) costs their fans' and condenser pumps' electricity and their water
(evaporation and blow-down, ``components.tower_water_m3``).

Doublets: each stops for 365 - ``operating_days`` days in one block, staggered across the
doublets in the weeks that need the least brine (unless the plant gives the days, or the user
gives a doublet's dates, ``Rules.doublet_stops``: one block or several ranges). Each day
the fewest doublets that carry the brine run, at least 50 m3/h each and at most each one's cap:
in equal shares (``dispatch="equal"``, the least pumping) or the hottest doublet first up to its
cap (``"base"``, the warmest brine: slow brine loses more heat up the well). Each doublet has its
own depth, open intervals and injectors (``Plant.specs``), so its own wellhead temperature and
pumps (the doublet model, GEMINI's well solve, at its flow). The brine of all doublets meets in
the heat plant: one mixed temperature feeds the exchanger, and each doublet's brine is cooled
from its own wellhead temperature to the common reinjection temperature (the 40 K cap is per
doublet). Separate treatment trains (separators, filters) change the cost, not the heat.

Failures (``Plant.outages``): a unit out on given days gives nothing those days. A doublet out
(its producer or ESP) or its treatment train stops its brine; one of two injectors out halves
the doublet's flow; the heat exchanger out leaves the brine only to the heat pump and the
absorption chiller; one of several boiler or chiller units out takes its share of the capacity.
The planned stops stay where they were; the other units cover what they can.
"""

from __future__ import annotations

import math
from dataclasses import replace
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from dioscuri_plant import operability, weather
from dioscuri_plant.components import (
    CH4_GWP100,
    CH4_KG_PER_NM3,
    CO2_KG_PER_NM3,
    FLARE_DESTRUCTION,
    Components,
    chiller_cop,
    heat_pump_cop,
    heat_pump_on_source,
    produced_gas,
    tower_water_m3,
)
from dioscuri_plant.doublet import reservoir_pressure_bar
from dioscuri_plant.network import network as network_effect
from dioscuri_plant.service import windows as service_windows
from dioscuri_plant.subsurface import check as subsurface_check
from dioscuri_plant.types import (
    DAYS,
    Demand,
    Doublet,
    DoubletModel,
    Plant,
    Rules,
    YearResult,
    daily_sum,
    open_interval,
)

SOURCE = "dioscuri_plant 0.1"
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)  # 2027
MONTH = np.repeat(np.arange(12), MONTH_DAYS)
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
GRID_POINTS = 11  # flows at which the doublet model is solved; daily values interpolate


def _days_off(i: int, operating_days: int, lengths: Optional[Sequence[int]]) -> int:
    """Return doublet ``i``'s days off: its own (``Rules.stop_days_off``), else the cap's."""
    if lengths and i < len(lengths) and lengths[i]:
        return max(0, min(int(lengths[i]), DAYS - 1))
    return DAYS - operating_days


def stop_windows(
    need: np.ndarray,
    n: int,
    operating_days: int,
    fixed: Optional[Sequence[int]] = None,
    lengths: Optional[Sequence[int]] = None,
) -> List[Tuple[int, int]]:
    """Return each doublet's stop as (first day, last day), 0-based and inclusive.

    Parameters
    ----------
    need : array
        A daily measure of what the doublets would deliver (the brine they would carry).
    n : int
        Number of doublets.
    operating_days : int
        Days each doublet may run.
    fixed : sequence of int, optional
        First stop day per doublet; otherwise the quietest blocks, not overlapping.
    lengths : sequence of int, optional
        Each doublet's own days off (``Rules.stop_days_off``); else 365 - ``operating_days``.

    Returns
    -------
    list of (int, int)
        One block per doublet; empty when no stop is needed.
    """
    offs = [_days_off(i, operating_days, lengths) for i in range(n)]
    if n == 0 or max(offs, default=0) <= 0:
        return []
    if fixed is not None:
        return [(int(s), min(int(s) + offs[i] - 1, DAYS - 1)) for i, s in enumerate(fixed)]
    chosen: List[Tuple[int, int]] = []
    for i in range(n):
        off = offs[i]
        if off <= 0:
            continue
        sums = np.convolve(need, np.ones(off), mode="valid")  # each block of `off` days
        for start in np.argsort(sums, kind="stable"):
            end = int(start) + off - 1
            if all(end < a or start > b for a, b in chosen):
                chosen.append((int(start), end))
                break
    return chosen


def stop_ranges(
    need: np.ndarray,
    n: int,
    operating_days: int,
    fixed: Optional[Sequence[int]] = None,
    given: Sequence[Sequence[Tuple[int, int]]] = (),
    lengths: Optional[Sequence[int]] = None,
) -> List[List[Tuple[int, int]]]:
    """Return each doublet's stops as a list of (first day, last day), 0-based and inclusive.

    A doublet with dates in ``given`` (the user's, ``Rules.doublet_stops``) stops on exactly
    those days, in one block or several; every other doublet stops as ``stop_windows`` places it
    (from ``fixed``, else the quietest block that overlaps no other doublet's stops).

    Returns
    -------
    list of list of (int, int)
        One list per doublet (empty when it does not stop).
    """
    if n == 0:
        return []
    mine: List[Optional[List[Tuple[int, int]]]] = [
        sorted((int(a), int(b)) for a, b in given[i]) if i < len(given) and given[i] else None
        for i in range(n)
    ]
    # Placed doublet by doublet below, not through ``stop_windows``: its list skips a doublet
    # with no days off, so the blocks after it would shift to the wrong doublets (4 Nov audit).
    out = [m if m is not None else [] for m in mine]
    if fixed is not None:
        return [
            (
                m
                if m is not None
                else [
                    (
                        int(fixed[i]),
                        min(int(fixed[i]) + _days_off(i, operating_days, lengths) - 1, DAYS - 1),
                    )
                ]
            )
            for i, m in enumerate(mine)
        ]
    for i in range(n):
        if mine[i] is not None:
            continue
        off = _days_off(i, operating_days, lengths)
        if off <= 0:
            continue
        sums = np.convolve(need, np.ones(off), mode="valid")
        taken = [r for rows in out for r in rows]
        for start in np.argsort(sums, kind="stable"):
            end = int(start) + off - 1
            if all(end < a or start > b for a, b in taken):
                out[i] = [(int(start), end)]
                break
    return out


def gas_flow(flows: np.ndarray, specs: Sequence[Doublet], rules: Rules) -> Tuple[np.ndarray, float]:
    """Return a brine flow and the gas-liquid ratio that give the doublets' gas together.

    Each doublet's brine carries its own aquifer's gas: with one ratio for all, the total flow
    and that ratio; else the doublets' flows weighted by their ratios, and 1.
    """
    flows = np.asarray(flows, dtype=float).reshape(len(specs), -1) if len(specs) else flows
    if not len(specs):
        return np.zeros(DAYS), rules.gas_liquid_ratio
    ratios = [rules.aquifer_at(s.depth_m).gas_liquid_ratio for s in specs]
    if all(r == ratios[0] for r in ratios):
        return flows.sum(axis=0), ratios[0]
    return (flows * np.asarray(ratios, dtype=float)[:, None]).sum(axis=0), 1.0


def _point(doublet: DoubletModel, flow: float, mid_m: float, open_m: float, rules: Rules):
    """Call the doublet model; the open length only when the well is not open over the whole."""
    if abs(open_m - rules.reservoir_thickness_m) < 1e-9:
        return doublet(float(flow), float(mid_m))
    return doublet(float(flow), float(mid_m), float(open_m))


def doublet_curves(doublet: DoubletModel, spec: Doublet, rules: Rules):
    """Solve one doublet at a dozen flows up to its cap; daily values interpolate.

    Returns
    -------
    tuple
        Flows (m3/h); wellhead temperature (°C), ESP power and injection pumps' power (MW, all
        injectors of the doublet) at those flows; the producer's point at its cap (dict).
    """
    cap = spec.cap_m3h(rules)
    grid = np.linspace(rules.flow_min_m3h, max(cap, rules.flow_min_m3h), GRID_POINTS)
    rules = rules.aquifer_at(spec.depth_m)  # the rock of the aquifer it is drilled into
    p_mid, p_len = open_interval(spec.depth_m, spec.producer_open, rules.reservoir_thickness_m)
    i_mid, i_len = open_interval(spec.depth_m, spec.injector_open, rules.reservoir_thickness_m)
    prod = [_point(doublet, q, p_mid, p_len, rules) for q in grid]
    inj = [_point(doublet, q / spec.injectors, i_mid, i_len, rules) for q in grid]
    wellhead = np.array([float(p["wellhead_c"]) for p in prod])
    esp = np.array([float(p.get("esp_mw", 0.0)) for p in prod])
    pumps = spec.injectors * np.array([float(p.get("injector_pump_mw", 0.0)) for p in inj])
    return grid, wellhead, esp, pumps, dict(prod[-1], injection=inj[-1])


@lru_cache(maxsize=1024)
def _curves(doublet: DoubletModel, spec: Doublet, rules: Rules):
    grid, wellhead, esp, pumps, point = doublet_curves(doublet, spec, rules)
    for a in (grid, wellhead, esp, pumps):
        a.setflags(write=False)  # shared between years: never changed in place
    return grid, wellhead, esp, pumps, point


def cached_curves(doublet: DoubletModel, spec: Doublet, rules: Rules):
    """Return ``doublet_curves``, solved once per doublet model, doublet and rules.

    A search runs thousands of years over a few dozen doublets (2 Nov: 14,000 solutions, 18 s
    of a 42 s search, for some 100 distinct ones); the year's own values never change them.
    """
    try:
        grid, wellhead, esp, pumps, point = _curves(doublet, spec, rules)
    except TypeError:  # an unhashable doublet model or rules: solved each time
        return doublet_curves(doublet, spec, rules)
    return grid, wellhead, esp, pumps, dict(point)


def dispatch(
    q_total: np.ndarray,
    allowed: np.ndarray,
    caps: np.ndarray,
    order: Sequence[int],
    qmin,
    mode: str = "equal",
) -> np.ndarray:
    """Share each day's brine among the doublets; return the flows (n x days, m3/h).

    The fewest doublets run, taken in ``order`` among those allowed that day, whose caps carry
    the brine; each runs at ``qmin`` at least (more brine than asked for, then): one value, or
    one per doublet (its own floor). ``equal``: equal shares, a doublet at its cap passing the
    rest on; ``base``: each in order up to its cap, leaving the minimum flow for those after
    it. ``caps`` is one per doublet, or one per doublet and day (an injector out halves a
    doublet's cap on those days).
    """
    n = len(caps)
    q = np.zeros((n, q_total.size))
    if n == 0:
        return q
    floors = np.broadcast_to(np.asarray(qmin, dtype=float).reshape(-1), (n,))
    caps = np.broadcast_to(np.asarray(caps, dtype=float).reshape(n, -1), (n, q_total.size))
    on = np.zeros((n, q_total.size), dtype=bool)
    carried = np.zeros(q_total.size)
    for i in order:
        on[i] = allowed[i] & (q_total > 1e-9) & (carried < q_total - 1e-9)
        carried = carried + np.where(allowed[i], caps[i], 0.0)
    remaining = q_total.copy()
    if mode == "base":
        ordered = np.array(list(order))
        # The floors of the running doublets from position k on.
        later = (on[ordered] * floors[ordered][:, None])[::-1].cumsum(axis=0)[::-1]
        for k, i in enumerate(order):
            after = later[k] - on[i] * floors[i]
            qi = np.maximum(np.minimum(caps[i], remaining - after), floors[i])
            q[i] = np.where(on[i], qi, 0.0)
            remaining = remaining - q[i]
    else:
        # Water-filling, day by day from the doublet with that day's smallest cap: one whose
        # injector is out on some days goes first on those days, and the others take the rest
        # (sorted by the year's largest cap, it could come last and leave brine unused).
        left = on.sum(axis=0).astype(float)
        ranks = np.argsort(caps, axis=0, kind="stable")
        days = np.arange(q_total.size)
        for k in range(n):
            i = ranks[k]
            share = np.where(left > 0, remaining / np.maximum(left, 1.0), 0.0)
            run = on[i, days]
            qi = np.maximum(np.minimum(caps[i, days], share), floors[i])
            q[i, days] = np.where(run, qi, 0.0)
            remaining = remaining - q[i, days]
            left = left - run
    return q


@lru_cache(maxsize=64)
def free_share(return_c: float, supply_c: float, approach_k: float) -> np.ndarray:
    """Return free cooling's expected share of each day's cold, 365 values in 0..1.

    In an hour the towers' water, ``approach_k`` above the wet bulb, cools the network's
    return to the supply when it is cold enough, part of the way otherwise:
    share = clip((return - (wet bulb + approach)) / (return - supply), 0, 1). The share is
    clipped, so it is taken hour by hour and averaged over the calendar day's 120 hours of
    2021-2025 at De Bilt (``weather.hourly_wet_bulb``), the load flat over the day: the expected
    share for a typical year. A smoothed year's daily wet bulb would overstate it.
    """
    water = weather.hourly_wet_bulb() + approach_k
    span = max(return_c - supply_c, 1e-6)
    share = np.clip((return_c - water) / span, 0.0, 1.0).mean(axis=1)
    share.setflags(write=False)
    return share


def free_cooling(cool: np.ndarray, plant: Plant, rules: Rules, comp: Components) -> np.ndarray:
    """Return the cold the towers give each day without the chillers, MW.

    The towers' water, ``free_cooling_approach_k`` above the wet bulb, cools the network's
    return through a plate exchanger: all the way to the supply when it is cold enough, part
    of the way otherwise (the chillers finish it), never more than the towers can reject. The
    share of each day is the expected one over De Bilt's real hours (``free_share``).
    """
    share = free_share(
        float(rules.cool_return_c), float(rules.cool_supply_c), float(comp.free_cooling_approach_k)
    )
    cop = chiller_cop(
        rules.cool_supply_c,
        comp.chiller_condensing_c,
        comp.chiller_eta,
        comp.chiller_evap_approach_k,
    )
    towers = plant.chiller_mw * (1 + 1 / cop) + plant.absorption_mw * (1 + 1 / comp.absorption_cop)
    return np.minimum(share * cool, towers)


def own_solar(electricity: np.ndarray, mwp: float, comp: Components) -> Tuple[np.ndarray, ...]:
    """Return the panels' daily output, the part the plant uses, and the part sold, MW.

    The output follows the KNMI radiation, scaled to ``solar_full_load_hours`` a year. The
    panels give it in daylight only: the plant uses at most what it draws in those hours.
    """
    wx = weather.typical_year()
    shape = wx["global_kwh_m2"] / wx["global_kwh_m2"].sum()
    out = mwp * comp.solar_full_load_hours * shape / 24.0
    used = np.minimum(out, electricity * wx["daylight_h"] / 24.0)
    return out, used, out - used


def simulate_year(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
) -> YearResult:
    """Run one year of a design at daily resolution and check the challenge's hard caps.

    With a hot-water store (``Rules.storage_mwh``), the year is run twice: see
    ``with_storage``. The rest is ``_simulate_year``.
    """
    if getattr(rules, "storage_mwh", 0.0) > 0 and plant.n_doublets > 0 and any(demand.heat_mw):
        return with_storage(plant, demand, doublet, rules, components)
    return _simulate_year(plant, demand, doublet, rules, components)


def with_storage(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules,
    comp: Components = Components(),
) -> YearResult:
    """Run a year with a hot-water store that moves heat to the days the geothermal is short.

    The year is first run without it. On the days the doublets (and the heat pump) give all
    they can, or stand still, every MWh the store gives back is a MWh less from the boiler. On
    the other days they have room: the store takes heat then, as much as keeps them within
    their best day's output (the boiler still tops up its share, as on any day), as fast as its
    exchangers allow (DEA: 2.9 MW per 175 MWh), losing 0.2 % of its heat a day. The year runs
    again with the moved heat, the store starting as full as it ends the year (a cycle). Daily
    steps: heat moved within a day (the evening peak) is not counted, so the store's value is
    on the low side. When it saves no boiler heat, the first year stands.
    """
    bare = replace(rules, storage_mwh=0.0)
    first = _simulate_year(plant, demand, doublet, bare, comp)
    h = first.daily_mw["heat"]
    load = np.asarray(h["demand"], dtype=float)
    base = np.asarray(h["geo"], dtype=float) + np.asarray(h["hp"], dtype=float)
    boiler = np.asarray(h["boiler"]) + np.asarray(h["electric_boiler"]) + np.asarray(h["short"])
    best = 0.97 * float(base.max(initial=0.0))
    # Short days: the geothermal at its best, or stopped, and the boiler running.
    short = ((base >= best) | (base <= 1e-6)) & (boiler > 1e-6)
    share = np.where(load > 1e-9, base / np.maximum(load, 1e-9), 0.0)
    room = np.where(
        short | (base <= 1e-6), 0.0, np.maximum(best - base, 0.0) / np.maximum(share, 0.05)
    )
    size = float(rules.storage_mwh)
    summary: dict = {"capacity_mwh": size, "charged_gwh": 0.0, "given_gwh": 0.0, "lost_gwh": 0.0}
    if not short.any() or not room.any():
        first.storage = {**summary, "boiler_saved_gwh": 0.0, "note": "nothing to move"}
        return first
    ates = bool(getattr(rules, "storage_ates", 0.0))
    power = comp.ates_mw if ates else size * comp.storage_mw_per_mwh
    # A tank loses a little every day; an aquifer store gives back a share of what went in.
    keep = 1.0 if ates else 1.0 - comp.storage_loss_per_day
    into = comp.ates_recovery if ates else 1.0

    def run(level: float):
        take, give, levels = np.zeros(DAYS), np.zeros(DAYS), np.zeros(DAYS)
        for d in range(DAYS):
            level *= keep
            if short[d]:
                give[d] = min(boiler[d], power, level / 24.0)
                level -= give[d] * 24.0
            else:
                take[d] = min(room[d], power, (size - level) / 24.0 / into)
                level += take[d] * 24.0 * into
            levels[d] = level
        return take, give, levels

    _, _, levels = run(0.0)
    take, give, levels = run(float(levels[-1]))
    shifted = np.asarray(demand.heat_mw, dtype=float) + take - give
    moved = Demand(tuple(shifted), tuple(demand.cool_mw), tuple(demand.dates))
    second = _simulate_year(plant, moved, doublet, bare, comp)
    saved = (
        first.heat_split_gwh["boiler"]
        + first.heat_split_gwh.get("electric_boiler", 0.0)
        - second.heat_split_gwh["boiler"]
        - second.heat_split_gwh.get("electric_boiler", 0.0)
    )
    if saved <= 0.01:
        first.storage = {**summary, "boiler_saved_gwh": 0.0, "note": "nothing to move"}
        return first
    lost = daily_sum(take) - daily_sum(give)
    # The buildings get their heat; the store's losses are heat made but not sold.
    second.heat_demand_gwh = round(second.heat_demand_gwh - lost, 3)
    second.heat_delivered_gwh = round(second.heat_delivered_gwh - lost, 3)
    second.storage = {
        **summary,
        "charged_gwh": round(daily_sum(take), 3),
        "given_gwh": round(daily_sum(give), 3),
        "lost_gwh": round(lost, 3),
        "boiler_saved_gwh": round(saved, 3),
        "full_cycles": round(daily_sum(give) * 1000 / size, 1) if size else 0.0,
        "power_mw": round(power, 2),
        "kind": "HT-ATES" if ates else "tank",
    }
    second.daily_mw["storage"] = {
        "take": np.round(take, 3).tolist(),
        "give": np.round(give, 3).tolist(),
        "level_mwh": np.round(levels, 1).tolist(),
    }
    return second


def _simulate_year(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
) -> YearResult:
    """Run one year of a design at daily resolution and check the challenge's hard caps.

    Parameters
    ----------
    plant : Plant
        The design.
    demand : Demand
        Daily heat and cold demand.
    doublet : callable
        ``doublet(flow_m3h, depth_m)`` -> wellhead temperature, ESP and injector pump power.
    rules : Rules
        Fixed inputs and hard caps.
    components : Components
        Unit performance parameters.

    Returns
    -------
    YearResult
        Daily power by source, energy, electricity, gas, CO2 and every broken cap.
    """
    heat, cool = demand.arrays()
    n, comp = plant.n_doublets, components
    ts0, tr0 = rules.heat_supply_c, rules.heat_return_c  # the buildings' (design) temperatures
    ts, tr = ts0, tr0  # the plant's, day by day when the network is modelled
    net = network_effect(heat, cool, rules)
    if net is not None:
        # The plant carries the network's losses and supplies hotter so the buildings get ts0.
        heat, cool = net["heat_load"], net["cool_load"]
        ts, tr = net["supply_c"], net["return_c"]
    cool_all = cool  # the network's cold; ``cool`` is what the absorption and chillers make
    free_cold = np.zeros(DAYS)
    if (
        getattr(rules, "free_cooling", 0.0)
        and cool.any()
        and (plant.chiller_mw > 0 or plant.absorption_mw > 0)
    ):
        free_cold = free_cooling(cool, plant, rules, comp)
        cool = cool - free_cold
    unit_cb = float(rules.brine_mw_per_k(1.0))  # MW/K per m3/h of brine
    qmin = rules.flow_min_m3h
    zeros = np.zeros(DAYS)

    # Each doublet, solved at a dozen flows (GEMINI is not called 365 times). The wellhead
    # temperature falls with the flow (the brine loses more heat up the well when slow): the
    # flow is planned with the full-flow values, then each day's delivery uses each doublet's
    # temperature at its flow that day.
    specs = plant.specs()
    caps = np.array([s.cap_m3h(rules) for s in specs]) if n > 0 else np.zeros(0)
    curves = [cached_curves(doublet, s, rules) for s in specs]
    if n > 0:
        full = np.array([c[1][-1] for c in curves])  # wellhead at each doublet's cap
        twh = float(np.sum(full * caps) / np.sum(caps))  # the design value, to plan the flow
        order = [int(i) for i in np.argsort(-full, kind="stable")]  # hottest first
    else:
        full, twh, order = np.zeros(0), 0.0, []

    # What the brine is asked for each day: the balanced exchanger, the absorption chiller.
    cw = heat / (ts - tr)  # network heat-capacity rate, MW/K
    tx = min(twh - plant.hex_approach_k, ts0)  # network temperature after the exchanger

    # The absorption chiller's hot-water loop needs the brine at 80 °C or more: below that it
    # gives no cold, and is not given brine.
    abs_hot = twh >= comp.absorption_min_drive_c

    def absorption_want(cap: np.ndarray) -> np.ndarray:
        """Return the brine (MW/K) the absorption chiller asks for each day, at this capacity."""
        if n > 0 and plant.absorption_mw > 0 and abs_hot:
            return np.minimum(cool, cap) / comp.absorption_cop / comp.absorption_brine_drop_k
        return zeros

    abs_cap = np.where(plant.out("absorption"), 0.0, plant.absorption_mw)
    cb_abs_want = absorption_want(abs_cap)
    if n > 0 and tx > tr0:
        # The balanced exchanger: the brine cools as much as the network warms. When the
        # network warms by more than the brine may cool (a 50 °C return heated to 100 °C, the
        # cap 40 K), the brine must flow faster by that ratio: planned balanced, it was cut
        # by the cap and the boiler made up the rest (2 Nov: 6 GWh a year at 3,500 m).
        lift = np.maximum(tx - tr, 1e-9)
        cb_heat_want = cw * np.maximum(lift / rules.max_brine_cooling_k, 1.0)
    elif n > 0 and plant.heat_pump_mw > 0:
        # Brine too cold to preheat the network: it is the heat pump's source only, cooled
        # as far as the cap allows; the flow its evaporator needs.
        floor0 = max(twh - rules.max_brine_cooling_k, comp.heat_pump_min_source_c)
        cop0 = max(float(heat_pump_cop(ts0, floor0, comp.heat_pump_eta)), 1.0 + 1e-6)
        evap = np.minimum(heat, plant.heat_pump_mw) * (1 - 1 / cop0)
        cb_heat_want = evap / max(twh - floor0, 1e-6)
    else:
        cb_heat_want = zeros

    # The doublets' stops come first; the units' planned service is placed around them (a
    # heating unit is never serviced while a doublet stands).
    ranges = stop_ranges(
        cb_heat_want + cb_abs_want,
        n,
        rules.operating_days,
        plant.stop_start_day,
        getattr(rules, "doublet_stops", ()),
        getattr(rules, "stop_days_off", ()),
    )
    stops = [r[0] for r in ranges if r]  # each doublet's first stop (``stop_days``)
    plan = {str(u): (str(m), tuple(r)) for u, m, r in getattr(rules, "service_plan", ())}
    service = (
        service_windows(
            heat,
            cool,
            plant.boiler_units if plant.boiler_mw > 0 else 0,
            plant.chiller_units if plant.chiller_mw > 0 else 0,
            plant.electric_boiler_units if plant.electric_boiler_mw > 0 else 0,
            stops=[r for rows in ranges for r in rows],
            plan=plan,
            auto=bool(getattr(rules, "planned_service", 0)),
            has={
                "heat pump": plant.heat_pump_mw > 0,
                "heat exchanger": n > 0,
                "absorption": plant.absorption_mw > 0,
            },
        )
        if getattr(rules, "planned_service", 0) or plan
        else ()
    )
    if service:
        plant = replace(plant, outages=tuple(plant.outages) + service)
    # Each unit's capacity day by day: nothing on the days it is out, a unit's share less when
    # one of several is out.
    hp_cap = np.where(plant.out("heat pump"), 0.0, plant.heat_pump_mw)
    boiler_cap = np.where(plant.out("boiler"), 0.0, plant.boiler_mw) * np.where(
        plant.out("boiler unit"), 1 - 1 / plant.boiler_units, 1.0
    )
    eboiler_cap = np.where(plant.out("electric boiler"), 0.0, plant.electric_boiler_mw) * np.where(
        plant.out("electric boiler unit"), 1 - 1 / plant.electric_boiler_units, 1.0
    )
    chiller_cap = np.where(plant.out("chillers"), 0.0, plant.chiller_mw) * np.where(
        plant.out("chiller unit"), 1 - 1 / plant.chiller_units, 1.0
    )
    if service:  # the absorption chiller's own service window
        abs_cap = np.where(plant.out("absorption"), 0.0, plant.absorption_mw)
        cb_abs_want = absorption_want(abs_cap)
    hex_out = plant.out("heat exchanger")

    allowed = np.ones((n, DAYS), dtype=bool)
    for i, rows in enumerate(ranges):
        for first, last in rows:
            allowed[i, first : last + 1] = False
    # Failures: a doublet or its train out stops it; one of two injectors out halves its cap
    # (with one injector the doublet stops). The pumps' energy those days is read from the
    # doublet's curves at the lower flow, an approximation for a few days.
    caps_day = np.repeat(caps[:, None], DAYS, axis=1) if n > 0 else np.zeros((0, DAYS))
    trains = plant.train_numbers()
    for i, spec in enumerate(specs):
        allowed[i] &= ~(plant.out(f"doublet {i + 1}") | plant.out(f"train {trains[i]}"))
        injector = plant.out(f"injector {i + 1}")
        if spec.injectors == 2:
            caps_day[i] = np.where(injector, np.maximum(caps[i] / 2, qmin), caps[i])
        else:
            allowed[i] &= ~injector

    cb_max = (allowed * caps_day).sum(axis=0) * unit_cb if n > 0 else zeros
    cb_heat = np.minimum(cb_heat_want, cb_max)
    cb_abs = np.minimum(cb_abs_want, cb_max - cb_heat)
    q_want = (cb_heat + cb_abs) / unit_cb
    floors = np.array([s.floor_m3h(rules) for s in specs]) if n > 0 else np.zeros(0)
    flows = dispatch(q_want, allowed, caps_day, order, floors, plant.dispatch)
    on = flows > 0
    q_total = flows.sum(axis=0) if n > 0 else zeros
    cb_heat = cb_heat + (q_total - q_want) * unit_cb  # the minimum flow's extra brine passes
    # the exchanger and leaves warmer

    # Each doublet's wellhead temperature at its flow; the brine mixes in the heat plant. On
    # days without flow the design value stands (nothing depends on it).
    if n > 0:
        twh_each = np.array([np.interp(flows[i], curves[i][0], curves[i][1]) for i in range(n)])
        twh_day = np.where(
            q_total > 0, (flows * twh_each).sum(axis=0) / np.maximum(q_total, 1e-12), twh
        )
        twh_hot = np.where(q_total > 0, np.where(on, twh_each, -np.inf).max(axis=0), twh)
    else:
        twh_each, twh_day, twh_hot = np.zeros((0, DAYS)), zeros, zeros
    tx_day = np.minimum(twh_day - plant.hex_approach_k, ts)

    # Heating: exchanger, heat pump on the brine, boiler.
    # Network flow through the exchanger (none when the brine is colder than the return).
    cw1 = np.where((tx_day > tr) & ~hex_out, np.minimum(cw, cb_heat), 0.0)
    # The hottest running doublet's brine may be cooled by 40 K at most. When the doublets'
    # temperatures differ (other depths, or one running slow), the mixed brine would leave the
    # exchanger too cold for it: less network water goes through the exchanger then, so the
    # brine leaves warmer, and the rest of the network is heated by the top-up.
    t_floor = twh_hot - rules.max_brine_cooling_k
    lift = np.maximum(tx_day - tr, 1e-9)
    cw1 = np.minimum(cw1, cb_heat * np.maximum(twh_day - t_floor, 0.0) / lift)
    q_hex = cw1 * np.maximum(tx_day - tr, 0.0)
    tb1 = np.where(cb_heat > 0, twh_day - q_hex / np.maximum(cb_heat, 1e-12), twh_day)
    q_top = np.where(tx_day > tr, cw1 * (ts - tx_day), 0.0)
    q_bypass = (cw - cw1) * (ts - tr)
    # The days the mixed brine is hot enough to drive the absorption chiller (it is planned with
    # the full-flow wellhead temperature; slow brine arrives cooler). On the other days its
    # brine passes the generator without giving heat, and the chiller makes no cold.
    abs_runs = twh_day >= comp.absorption_min_drive_c
    t_gen_out = np.where(abs_runs, twh_day - comp.absorption_brine_drop_k, twh_day)
    cb_src = cb_heat + cb_abs
    t_mix = np.where(
        cb_src > 0, (cb_heat * tb1 + cb_abs * t_gen_out) / np.maximum(cb_src, 1e-12), twh_day
    )
    # The hottest running doublet's brine is cooled the most: it sets the 40 K floor.
    floor = np.maximum(t_floor, comp.heat_pump_min_source_c)
    # The produced gas is burnt whether or not its heat is used (flared otherwise), so the
    # boiler takes it first: the network that bypasses the doublets, then the top-up.
    # Each doublet's brine brings its own aquifer's gas (``Rules.aquifer_at``).
    ch4_mw, ch4_nm3h, co2_nm3h = produced_gas(
        *gas_flow(flows, specs, rules), rules.gas_ch4_fraction, rules.gas_co2_fraction
    )
    burns = plant.burn_produced_gas and plant.gas != "sell" and not rules.flare_brine_gas
    free_heat = ch4_mw * comp.boiler_efficiency if burns else zeros
    if plant.gas != "buy":  # no gas bought: the boiler has only the brine's gas to burn
        boiler_cap = np.minimum(boiler_cap, free_heat)
    free = np.minimum(np.minimum(free_heat, boiler_cap), q_bypass + q_top)
    # The heat pump takes what is left, the exchanger's top-up first, then the water that
    # bypasses the doublets (its COP is set by the 100 °C it delivers and its source).
    left = q_top + q_bypass - free
    if n > 0 and plant.heat_pump_mw > 0:
        hp_want = np.minimum(left, hp_cap)
        hp, t_out, _cop, hp_el = heat_pump_on_source(
            hp_want, t_mix, cb_src, ts, floor, comp.heat_pump_eta
        )
    else:
        hp, t_out, hp_el = zeros, t_mix, zeros
    boiler_want = q_top + q_bypass - hp
    boiler = np.minimum(boiler_want, boiler_cap)
    # The electric boiler after the gas boiler: it heats what the gas boiler cannot.
    eboiler = np.minimum(boiler_want - boiler, eboiler_cap)
    eboiler_el = eboiler / comp.electric_boiler_efficiency
    heat_short = np.maximum(boiler_want - boiler - eboiler, 0.0)
    reinjection = np.where(q_total > 0, t_out, np.nan)

    # Cooling: absorption on the brine, then electric chillers.
    abs_cold = np.where(
        abs_runs,
        np.minimum(cb_abs * comp.absorption_brine_drop_k * comp.absorption_cop, cool),
        0.0,
    )
    chill_want = cool - abs_cold
    chill = np.minimum(chill_want, chiller_cap)
    cool_short = np.maximum(chill_want - chill, 0.0)
    cop_ch = chiller_cop(
        rules.cool_supply_c,
        comp.chiller_condensing_c,
        comp.chiller_eta,
        comp.chiller_evap_approach_k,
    )
    chill_el = chill / cop_ch
    # The towers reject the absorption chiller's cold and driving heat, the chillers' cold and
    # electricity, and free cooling's cold; their condenser pumps add 0.5 % (and that heat), the
    # fans 1.25 % of all of it. The water: evaporation, blow-down and make-up, m3 a day.
    rejected = abs_cold * (1 + 1 / comp.absorption_cop) + chill + chill_el + free_cold
    tower_pumps_el = comp.tower_pump_mw_el_per_mw * rejected
    tower_heat = rejected + tower_pumps_el
    tower_el = comp.tower_mw_el_per_mw * tower_heat + tower_pumps_el
    evaporation_m3, blowdown_m3, makeup_m3 = tower_water_m3(tower_heat, comp)

    # Pumps at each running doublet's flow, from the doublet model.
    esp_each = np.array(
        [np.where(on[i], np.interp(flows[i], curves[i][0], curves[i][2]), 0.0) for i in range(n)]
    ).reshape(n, DAYS)
    inj_each = np.array(
        [np.where(on[i], np.interp(flows[i], curves[i][0], curves[i][3]), 0.0) for i in range(n)]
    ).reshape(n, DAYS)
    pump_el = (esp_each + inj_each).sum(axis=0) if n > 0 else zeros

    # Gas: the boiler burns the produced gas first; what is left is flared. Sold, it is cleaned
    # (its CO2 let out) and its methane goes to the grid: the buyer burns it, not the plant.
    fuel = boiler / comp.boiler_efficiency
    used = np.minimum(fuel, ch4_mw) if burns else zeros
    sold = ch4_mw if plant.gas == "sell" else zeros
    flared = ch4_mw - used - sold
    purchased = np.maximum(fuel - used, 0.0)

    net_pump = net["pump_mw"] if net is not None else zeros
    electricity = hp_el + chill_el + tower_el + pump_el + net_pump + eboiler_el
    co2_purchased = daily_sum(purchased) * 1000 * comp.gas_t_co2_per_mwh
    # The brine's own CO2 is let out, unless it is dissolved back into the injected brine; the
    # methane's CO2 when burnt (on site, or flared) is let out either way.
    native = zeros if rules.co2_reinjection else co2_nm3h
    vented = native if plant.gas == "sell" else ch4_nm3h + native
    co2_produced = float(np.sum(vented)) * 24 * CO2_KG_PER_NM3 / 1000
    co2_reinjected = (
        float(np.sum(co2_nm3h)) * 24 * CO2_KG_PER_NM3 / 1000 if rules.co2_reinjection else 0.0
    )
    grid = comp.grid_t_co2_per_mwh if rules.grid_t_co2_per_mwh is None else rules.grid_t_co2_per_mwh
    solar, bought = None, electricity
    if getattr(rules, "solar_mwp", 0.0) > 0:
        pv, pv_used, pv_sold = own_solar(electricity, float(rules.solar_mwp), comp)
        bought = electricity - pv_used
        solar = {
            "mwp": float(rules.solar_mwp),
            "generated_gwh": round(daily_sum(pv), 3),
            "used_gwh": round(daily_sum(pv_used), 3),
            "sold_gwh": round(daily_sum(pv_sold), 3),
            "bought_gwh": round(daily_sum(bought), 3),
        }
    if getattr(rules, "grid_by_month", 0.0):
        shape = np.asarray(comp.grid_month_shape, dtype=float)[MONTH]
        co2_electricity = daily_sum(bought * shape) * 1000 * grid
    else:
        shape = np.ones(DAYS)
        co2_electricity = daily_sum(bought) * 1000 * grid
    # The same CO2 by the unit that lets it out, with the same factors: the gas boiler burns
    # the bought gas and the brine's methane it takes each day, the flare the methane left over,
    # the brine's own CO2 goes out at the gas separator, and each electricity user carries its
    # share of the day's bought electricity (after own solar).
    nm3h_to_t = 24 * CO2_KG_PER_NM3 / 1000  # t of CO2 a year per Nm3/h on one day
    methane = ch4_nm3h if plant.gas != "sell" else zeros  # sold: the buyer burns it
    to_boiler = np.where(ch4_mw > 0, used / np.maximum(ch4_mw, 1e-12), 0.0)
    co2_boiler_ch4 = float(np.sum(methane * to_boiler)) * nm3h_to_t
    share = np.where(electricity > 0, bought / np.maximum(electricity, 1e-12), 0.0) * shape
    by_power = {
        key: daily_sum(el * share) * 1000 * grid
        for key, el in (
            ("electric_boiler", eboiler_el),
            ("hp", hp_el),
            ("pumps", pump_el),
            ("chillers", chill_el),
            ("towers", tower_el),
            ("network", net_pump),
        )
    }
    co2_by_unit = tenths(
        {
            "boiler": co2_purchased + co2_boiler_ch4,
            "electric_boiler": by_power["electric_boiler"],
            "hp": by_power["hp"],
            "pumps": by_power["pumps"],
            "flare": float(np.sum(methane)) * nm3h_to_t - co2_boiler_ch4,
            "brine_co2": float(np.sum(native)) * nm3h_to_t,
            "chillers": by_power["chillers"],
            "towers": by_power["towers"],
            "network": by_power["network"],
        },
        co2_purchased + co2_produced + co2_electricity,
    )
    # The methane a flare lets through, as CO2-equivalent (not in the CO2 total).
    flared_nm3h = np.where(ch4_mw > 0, flared / np.maximum(ch4_mw, 1e-12), 0.0) * ch4_nm3h
    slip_t = float(np.sum(flared_nm3h)) * 24 * (1 - FLARE_DESTRUCTION) * CH4_KG_PER_NM3 / 1000

    doublets = [
        {
            "flow_m3h": flows[i].round(2).tolist(),
            "on": on[i].tolist(),
            "reinjection_c": [
                round(float(r), 2) if o else None for r, o in zip(reinjection, on[i])
            ],
            "wellhead_c": [round(float(t), 2) if o else None for t, o in zip(twh_each[i], on[i])],
        }
        for i in range(n)
    ]
    summary = _doublet_summary(
        specs, rules, curves, flows, on, twh_each, reinjection, esp_each, inj_each
    )

    violations = _violations(
        plant, rules, heat, cool_all, heat_short, cool_short, on, flows, caps, twh_each, reinjection
    )
    for row in summary:  # the subsurface checks (``subsurface.py``)
        violations += [f"Doublet {row['doublet']}: {x}." for x in row["subsurface_problems"]]
    warnings = [
        f"Doublet {i + 1} never runs: the others carry all the brine."
        for i in range(n)
        if not on[i].any()
    ]
    warnings += _absorption_warnings(plant, comp, cool, twh, twh_day, cb_abs, abs_runs)
    flared_gwh = daily_sum(flared)
    if flared_gwh > 0.05:
        # Flaring is regulated (SodM's review of 2026: Mijnbouwbesluit art. 38 and 84; the EU
        # Methane Regulation 2024/1787 lists when venting or flaring is allowed, flaring first,
        # and every event is reported): said whenever a design flares, not only on request.
        warnings.append(
            f"{flared_gwh:.1f} GWh of the brine's gas is flared a year"
            + (
                " (all of it: the switch is on)"
                if rules.flare_brine_gas
                else " (when the boiler needs less than the brine gives)"
            )
            + ": routine flaring needs consent under the Mijnbouwbesluit (art. 38 and 84), and "
            "the EU Methane Regulation 2024/1787 allows it only in the situations it lists; "
            "selling the gas avoids it."
        )
    # Minimum loads and trips (``operability``): counted, not dispatched.
    oper = operability.check(
        {
            "boiler": boiler,
            "heat_pump": hp,
            "electric_boiler": eboiler,
            "chillers": chill,
            "absorption": abs_cold,
        },
        {
            "boiler": plant.boiler_mw / max(plant.boiler_units, 1),
            "heat_pump": plant.heat_pump_mw,
            "electric_boiler": plant.electric_boiler_mw / max(plant.electric_boiler_units, 1),
            "chillers": plant.chiller_mw / max(plant.chiller_units, 1),
            "absorption": plant.absorption_mw,
        },
        q_hex,
        n,
    )
    delivered = q_hex + hp + boiler + eboiler
    balance = np.abs(delivered - (heat - heat_short)) / np.maximum(heat, 1e-9)
    balance_cool = np.abs(abs_cold + chill - (cool - cool_short)) / np.maximum(cool, 1e-9)
    worst = float(max(balance.max(initial=0.0), balance_cool.max(initial=0.0)))
    if worst > 1e-3:
        violations.append(f"The daily energy balance is off by {worst:.2%} on its worst day.")

    daily = {
        "heat": {
            "demand": heat,
            "geo": q_hex,
            "hp": hp,
            "boiler": boiler,
            "electric_boiler": eboiler,
            "short": heat_short,
        },
        "cool": {
            "demand": cool_all,
            "free": free_cold,
            "abs": abs_cold,
            "chill": chill,
            "short": cool_short,
        },
        # Electricity drawn from the grid and heat rejected to the towers, for the canvas.
        "power": {
            "hp": hp_el,
            "chillers": chill_el,
            "towers": tower_el,
            "pumps": pump_el,
            "electric_boiler": eboiler_el,
        },
        "reject": {
            "abs": abs_cold * (1 + 1 / comp.absorption_cop),
            "chillers": chill + chill_el,
            "free": free_cold,
        },
    }
    monthly = {
        side: {
            k: (np.bincount(MONTH, weights=v, minlength=12) * 24 / 1000).round(3).tolist()
            for k, v in series.items()
        }
        for side, series in daily.items()
        if side in ("heat", "cool")
    }
    hp_energy = daily_sum(hp)
    brine_heat = (
        daily_sum(q_hex) + daily_sum(hp - hp_el) + daily_sum(abs_cold / comp.absorption_cop)
    )
    geo_capacity = float(np.sum(caps)) * unit_cb * rules.max_brine_cooling_k
    heat_delivered = daily_sum(delivered)
    cool_delivered = daily_sum(abs_cold + chill + free_cold)
    return YearResult(
        plant=plant,
        source=SOURCE,
        heat_demand_gwh=round(daily_sum(heat), 3),
        cool_demand_gwh=round(daily_sum(cool_all), 3),
        heat_delivered_gwh=round(heat_delivered, 3),
        cool_delivered_gwh=round(cool_delivered, 3),
        heat_coverage=round(heat_delivered / max(daily_sum(heat), 1e-9), 4),
        cool_coverage=(
            round(cool_delivered / max(daily_sum(cool_all), 1e-9), 4) if cool_all.any() else 1.0
        ),
        heat_split_gwh={
            "geo": round(daily_sum(q_hex), 3),
            "hp": round(hp_energy, 3),
            "recovery_hp": 0.0,
            "boiler": round(daily_sum(boiler), 3),
            "electric_boiler": round(daily_sum(eboiler), 3),
            "chp": 0.0,
        },
        cool_split_gwh={
            "abs": round(daily_sum(abs_cold), 3),
            "chill": round(daily_sum(chill), 3),
            "recovery_hp": 0.0,
            "free": round(daily_sum(free_cold), 3),
        },
        peak_heat_mw=round(float(heat.max()), 3),
        peak_cool_mw=round(float(cool_all.max()), 3),
        daily_mw={s: {k: np.round(v, 3).tolist() for k, v in d.items()} for s, d in daily.items()},
        monthly_gwh=monthly,
        doublets=doublets,
        electricity_gwh={
            "hp": round(daily_sum(hp_el), 3),
            "recovery_hp": 0.0,
            "chillers": round(daily_sum(chill_el), 3),
            "pumps": round(daily_sum(pump_el), 3),
            "towers": round(daily_sum(tower_el), 3),
            "network": round(daily_sum(net_pump), 3),
            "electric_boiler": round(daily_sum(eboiler_el), 3),
        },
        purchased_gas_gwh=round(daily_sum(purchased), 3),
        produced_gas_burned_gwh=round(daily_sum(used), 3),
        produced_gas_flared_gwh=round(daily_sum(flared), 3),
        produced_gas_sold_gwh=round(daily_sum(sold), 3),
        free_cooling_mw=round(float(free_cold.max(initial=0.0)), 3),
        tower_water_m3={
            "evaporation": round(float(np.sum(evaporation_m3)), 0),
            "blowdown": round(float(np.sum(blowdown_m3)), 0),
            "makeup": round(float(np.sum(makeup_m3)), 0),
        },
        operability=oper,
        solar=solar,
        co2_t={
            "purchased_gas": round(co2_purchased, 1),
            "produced_gas": round(co2_produced, 1),
            "electricity": round(co2_electricity, 1),
            "total": round(co2_purchased + co2_produced + co2_electricity, 1),
            # The brine's own CO2 dissolved back into the injected brine (not in the total).
            "reinjected": round(co2_reinjected, 1),
            # The flare's unburnt methane, t CO2-equivalent over 100 years (not in the total).
            "methane_slip_co2e": round(slip_t * CH4_GWP100, 1),
            # The bought gas's supply chain, t CO2-equivalent (life cycle; not in the total).
            "upstream_gas_co2e": round(
                daily_sum(purchased) * 1000 * comp.gas_upstream_t_co2e_per_mwh, 1
            ),
            # Not the plant's: the methane it sells, burnt by whoever buys it (not in the total).
            "sold_gas_elsewhere": round(
                daily_sum(sold) * 1000 * comp.gas_t_co2_per_mwh if plant.gas == "sell" else 0.0, 1
            ),
        },
        co2_by_unit_t=co2_by_unit,
        violations=violations,
        wellhead_c=round(twh, 2),  # at full flow (the design value)
        wellhead_min_c=round(float(np.min(twh_each[on])) if n > 0 and on.any() else twh, 2),
        reservoir_c=(
            round(float(np.sum(caps * [d["rock_c"] for d in summary]) / np.sum(caps)), 2)
            if n > 0
            else 0.0
        ),
        max_brine_cooling_k=(
            round(float(np.nanmax(np.where(on, twh_each - reinjection, np.nan), initial=0.0)), 2)
            if n > 0 and on.any()
            else 0.0
        ),
        min_reinjection_c=round(float(np.nanmin(reinjection, initial=twh)), 2) if n > 0 else 0.0,
        heat_pump_cop=round(hp_energy / max(daily_sum(hp_el), 1e-9), 3) if hp_energy > 0 else 0.0,
        chiller_cop=round(float(cop_ch), 3),
        absorption_cop=comp.absorption_cop if plant.absorption_mw > 0 else 0.0,
        full_load_hours=round(brine_heat * 1000 / geo_capacity, 0) if geo_capacity else 0.0,
        brine_m3=round(float(np.sum(q_total)) * 24, 0),
        peak_shortfall_mw={
            "heat": round(float(heat_short.max()), 3),
            "cool": round(float(cool_short.max()), 3),
        },
        peak_brine_heat_mw=round(
            float(np.max(q_hex + hp - hp_el + abs_cold / comp.absorption_cop, initial=0.0)), 3
        ),
        stop_days=stops,
        stop_ranges=[list(r) for r in ranges],
        balance_error=round(worst, 6),
        doublet_summary=summary,
        warnings=warnings,
        network=net["summary"] if net is not None else None,
        service=list(service),
    )


def tenths(parts: Dict[str, float], total: float) -> Dict[str, float]:
    """Return parts rounded to 0.1 that add up to the total rounded to 0.1, to the tenth.

    Each part is rounded down, and the tenths left over go to the parts that lost the most
    (largest remainder), so a split of ``co2_t["total"]`` adds up to it as printed.

    Parameters
    ----------
    parts : dict of str to float
        The parts (negative ones count as 0).
    total : float
        Their sum, unrounded.

    Returns
    -------
    dict of str to float
        The same keys, in the same order, each a multiple of 0.1.
    """
    raw = {k: max(float(v), 0.0) * 10 for k, v in parts.items()}
    out = {k: math.floor(v + 1e-9) for k, v in raw.items()}
    left = int(round(round(total, 1) * 10)) - sum(out.values())
    order = sorted(raw, key=lambda k: out[k] - raw[k])  # the largest remainder first
    step = 1 if left > 0 else -1
    while left and order:
        for k in order if step > 0 else reversed(order):
            if left == 0:
                break
            if step < 0 and out[k] == 0:
                continue
            out[k] += step
            left -= step
        if step < 0 and not any(out.values()):
            break
    return {k: round(v / 10, 1) for k, v in out.items()}


def _absorption_warnings(plant, comp, cool, twh, twh_day, cb_abs, abs_runs) -> List[str]:
    """Return a warning when the brine is too cold to drive the absorption chiller."""
    if plant.absorption_mw <= 0 or plant.n_doublets == 0 or not np.any(cool > 0):
        return []
    need = comp.absorption_min_drive_c
    if twh < need:
        return [
            f"The absorption chiller gives no cold: the brine reaches the plant at {twh:.1f} °C, "
            f"below the {need:.0f} °C its hot-water loop needs (the loop's supply plus the "
            "exchanger's approach); the chillers cover what they can."
        ]
    lost = (cb_abs > 0) & ~abs_runs
    if not lost.any():
        return []
    return [
        f"The absorption chiller gives no cold on {int(lost.sum())} day(s): the brine runs slow "
        f"and reaches the plant below the {need:.0f} °C its hot-water loop needs (lowest "
        f"{float(np.min(twh_day[lost])):.1f} °C); the chillers cover what they can."
    ]


def _day(i: int) -> str:
    month = int(MONTH[i])
    day = i - int(np.sum(MONTH_DAYS[:month])) + 1
    return f"{day} {MONTH_NAMES[month]}"


def _doublet_summary(specs, rules, curves, flows, on, twh_each, reinjection, esp_each, inj_each):
    """Return one row per doublet: its set-up, flows, temperatures and pumps' energy."""
    rows = []
    base = rules
    for i, spec in enumerate(specs):
        rules = base.aquifer_at(spec.depth_m)  # the rock of the aquifer it is drilled into
        which = base.aquifer_index(spec.depth_m)
        p_mid, p_len = open_interval(spec.depth_m, spec.producer_open, rules.reservoir_thickness_m)
        i_mid, i_len = open_interval(spec.depth_m, spec.injector_open, rules.reservoir_thickness_m)
        days = int(on[i].sum())
        running = flows[i][on[i]]
        point = curves[i][4]
        cooled = (twh_each[i] - reinjection)[on[i]]
        rows.append(
            {
                "doublet": i + 1,
                "depth_m": spec.depth_m,
                "producer_open": spec.producer_open,
                "injector_open": spec.injector_open,
                "producer_mid_m": p_mid,
                "producer_open_m": p_len,
                "injector_mid_m": i_mid,
                "injector_open_m": i_len,
                "injectors": spec.injectors,
                "train": spec.train,
                "cap_m3h": spec.cap_m3h(rules),
                "rock_c": round(rules.reservoir_temperature_c(p_mid), 2),
                "wellhead_full_c": round(float(curves[i][1][-1]), 2),
                "wellhead_min_c": round(float(twh_each[i][on[i]].min()), 2) if days else None,
                "well_loss_full_k": round(float(point.get("well_loss_k", 0.0)), 2),
                "days_on": days,
                "flow_mean_m3h": round(float(running.mean()), 1) if days else 0.0,
                "flow_year_mean_m3h": round(float(flows[i].sum() / DAYS), 1),
                "brine_m3": round(float(flows[i].sum()) * 24, 0),
                "max_cooling_k": round(float(cooled.max()), 2) if days else 0.0,
                "esp_gwh": round(daily_sum(esp_each[i]), 3),
                "injection_gwh": round(daily_sum(inj_each[i]), 3),
                "esp_head_full_bar": round(float(point.get("esp_head_bar", 0.0)), 2),
                "injection_full_bar": round(
                    float(point["injection"].get("injection_wellhead_bar", 0.0)), 2
                ),
                "pi_m3h_per_bar": round(float(point.get("pi_m3h_per_bar", 0.0)), 2),
                "injectivity_m3h_per_bar": round(
                    float(point["injection"].get("pi_m3h_per_bar", 0.0)), 2
                ),
                # The aquifer it is drilled into (``Rules.aquifers``, 1 the known one; None
                # an assumed one) and that aquifer's rock, pressure and gas.
                "aquifer": None if which is None else which + 1,
                "aquifer_depth_m": spec.depth_m if which is None else rules.reservoir_depth_m,
                "thickness_m": rules.reservoir_thickness_m,
                "permeability_md": rules.permeability_md,
                "reservoir_pressure_bar": round(
                    float(reservoir_pressure_bar(spec.depth_m, rules)), 2
                ),
                "gas_liquid_ratio": rules.gas_liquid_ratio,
                "gas_nm3": round(float(flows[i].sum()) * 24 * rules.gas_liquid_ratio, 0),
            }
        )
        sub = subsurface_check(
            spec,
            rules,
            p_mid,
            float(point.get("pi_m3h_per_bar", 0.0)),
            float(point["injection"].get("pi_m3h_per_bar", 0.0)),
            float(curves[i][1][-1]),
            float(running.max()) if days else 0.0,
            float(flows[i].sum() / DAYS),
        )
        rows[-1].update({k: v for k, v in sub.items() if k != "problems"})
        rows[-1]["subsurface_problems"] = sub["problems"]
    return rows


def _violations(plant, rules, heat, cool, heat_short, cool_short, on, flows, caps, twh, reinj):
    """Return one plain sentence per broken hard cap, with the worst day and value."""
    out: List[str] = []
    if heat_short.max(initial=0.0) > 1e-6:
        d = int(np.argmax(heat_short))
        days = int(np.sum(heat_short > 1e-6))
        out.append(
            f"Heat short of 100 °C supply on {days} day(s): worst {heat_short[d]:.2f} MW on "
            f"{_day(d)} (demand {heat[d]:.2f} MW)."
        )
    if cool_short.max(initial=0.0) > 1e-6:
        d = int(np.argmax(cool_short))
        days = int(np.sum(cool_short > 1e-6))
        out.append(
            f"Cooling short of 20 °C supply on {days} day(s): worst {cool_short[d]:.2f} MW on "
            f"{_day(d)} (demand {cool[d]:.2f} MW)."
        )
    for i in range(plant.n_doublets):
        days_on = int(on[i].sum())
        if days_on > rules.operating_days:
            out.append(f"Doublet {i + 1} runs {days_on} days, more than {rules.operating_days}.")
        running = flows[i][on[i]]
        if running.size and (
            running.min() < rules.flow_min_m3h - 1e-6 or running.max() > caps[i] + 1e-6
        ):
            out.append(
                f"Doublet {i + 1} flow {running.min():.0f}-{running.max():.0f} m3/h is outside "
                f"{rules.flow_min_m3h:.0f}-{caps[i]:.0f} m3/h."
            )
        cooling = np.where(on[i], twh[i] - reinj, np.nan)
        if on[i].any() and np.nanmax(cooling) > rules.max_brine_cooling_k + 1e-6:
            d = int(np.nanargmax(cooling))
            out.append(
                f"Brine of doublet {i + 1} cooled by {cooling[d]:.1f} K on {_day(d)}, more than "
                f"{rules.max_brine_cooling_k:.0f} K."
            )
    return out
