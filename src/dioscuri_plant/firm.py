"""Firm capacity: one unit out (N-1), the spare on the peak day, a reliable plan, failures.

``outages`` runs the year again with each unit out all year in turn: each doublet (its producer,
ESP or injector), a treatment train that serves several doublets, the heat exchanger, the heat
pump, the boiler (or one of its units), the chillers (or one unit) and the absorption chiller.
A trip of a few days is short on at most the days these runs list.

``reliable`` sizes a design so that any one of those can be out and every day is still met:
the boiler and the electric chillers are built as ``UNITS`` equal units and grow until no
outage leaves a day short (the challenge does not ask for this; it is the "reliable plan").

``failure`` runs a design with units out on given days (a what-if), and ``remedies`` the same
with what would help: a bigger boiler or more chillers for the worst gap (a bank with one of its
units out grows by ``units / (units - 1)`` of the gap, as in ``reliable``), a standby twin of a
single boiler, electric boiler or chiller set that fails, and a spare ESP on the shelf for a
doublet that fails.
"""

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from dioscuri_plant.components import Components
from dioscuri_plant.types import DAYS, Demand, DoubletModel, Plant, Rules, YearResult
from dioscuri_plant.year import _day, simulate_year

UNITS = 3  # equal units a reliable plan's boiler and chillers are built as
MAX_ROUNDS = 6
# A failed ESP (sources in ``failure_costs.SOURCES``). With a spare on the shelf and a workover
# unit booked, the doublet is back in 1-2 weeks: 2-3 days at best (van 't Spijker & Ungemach
# 2016, p.20), about a week seen at Wayland Energy (2021); 7 days taken. The spare is the pump
# set alone: 140-240 k€ in 2016 € (same report, Table 6: 35-60 k€ a year over a 4-year life),
# about 180-310 k€ in 2025 € (+30 % Dutch CPI); the upper end taken. Without a spare the
# doublet waits for a new pump: 3-6 months (6 months for a German well's ESP, Halliburton case
# study); 4 months taken.
SPARE_ESP_SWAP_DAYS = 7
SPARE_ESP_MEUR = 0.3
NO_SPARE_ESP_DAYS = 120


def _up(x: float, step: float = 0.1) -> float:
    return float(np.ceil(max(x, 0.0) / step - 1e-9) * step)


def bank_need(gap_mw: float, units: int, own_unit_out: bool) -> float:
    """Return how much a bank of ``units`` equal units must grow to close a gap of ``gap_mw``.

    With one of its own units out, only ``(units - 1) / units`` of what is added is there, so it
    grows by ``gap x units / (units - 1)``; otherwise by the gap. One unit alone cannot cover
    its own outage (a standby twin does): the gap is returned.
    """
    if own_unit_out and units > 1:
        return gap_mw * units / (units - 1)
    return gap_mw


def _need(
    failed: YearResult, side: str, events: Sequence[Tuple[str, int, int]], bank: str, units: int
) -> float:
    """Return what a bank must grow by to close a failed year's worst gap on one side, MW.

    Day by day: on the days one of the bank's own units (``bank``: "boiler unit") is out, the
    gap counts ``units / (units - 1)`` times (``bank_need``).
    """
    short = np.asarray(failed.daily_mw[side]["short"], dtype=float)
    out = np.zeros(len(short), dtype=bool)
    for unit, first, last in events:
        if unit == bank:
            out[max(first, 0) : last + 1] = True
    need = [bank_need(float(x), units, bool(o)) for x, o in zip(short, out)]
    return max(need, default=0.0)


def cases(plant: Plant) -> List[Tuple[str, str]]:
    """Return the N-1 cases of a design: (name in words, outage unit)."""
    out = []
    for i in range(plant.n_doublets):
        out.append((f"doublet {i + 1}", f"doublet {i + 1}"))
    trains = plant.train_numbers()
    for k in sorted(set(trains)):
        members = [i + 1 for i, t in enumerate(trains) if t == k]
        if len(members) > 1:  # one doublet's own train is the doublet's case
            name = (
                "the shared treatment train"
                if len(set(trains)) == 1
                else f"treatment train {k} (doublets {' and '.join(map(str, members))})"
            )
            out.append((name, f"train {k}"))
    if plant.n_doublets:
        out.append(("the heat exchanger", "heat exchanger"))
    if plant.heat_pump_mw > 0:
        out.append(("the heat pump", "heat pump"))
    if plant.boiler_mw > 0:
        out.append(
            ("the boiler", "boiler")
            if plant.boiler_units == 1
            else (f"one of the {plant.boiler_units} boiler units", "boiler unit")
        )
    if plant.electric_boiler_mw > 0:
        out.append(
            ("the electric boiler", "electric boiler")
            if plant.electric_boiler_units == 1
            else (
                f"one of the {plant.electric_boiler_units} electric boiler units",
                "electric boiler unit",
            )
        )
    if plant.chiller_mw > 0:
        out.append(
            ("the electric chillers", "chillers")
            if plant.chiller_units == 1
            else (f"one of the {plant.chiller_units} chiller units", "chiller unit")
        )
    if plant.absorption_mw > 0:
        out.append(("the absorption chiller", "absorption"))
    return out


def shortfall(name: str, year: YearResult) -> Dict[str, object]:
    """Return a year's shortfall per side: days short, worst MW and day, GWh not delivered."""
    out: Dict[str, object] = {"unit": name}
    for side in ("heat", "cool"):
        short = np.asarray(year.daily_mw[side]["short"], dtype=float)
        days = short > 1e-3
        worst = int(np.argmax(short))
        out[side] = {
            "days_short": int(days.sum()),
            "worst_mw": round(float(short.max()), 2),
            "worst_day": _day(worst) if days.any() else None,
            "worst_index": worst if days.any() else None,
            "short_gwh": round(float(short.sum()) * 24 / 1000, 3),
        }
    return out


def _all_year(plant: Plant, unit: str) -> Plant:
    return replace(plant, outages=plant.outages + ((unit, 0, DAYS - 1),))


def outages(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
) -> List[Dict[str, object]]:
    """Return the year's shortfall with each unit out in turn (``cases``).

    Returns
    -------
    list of dict
        Per case: ``unit`` (its name) and, for ``heat`` and ``cool``, ``days_short``,
        ``worst_mw``, ``worst_day`` ("28 Jan"), ``worst_index`` (0-based day), ``short_gwh``.
    """
    return [
        shortfall(name, simulate_year(_all_year(plant, unit), demand, doublet, rules, components))
        for name, unit in cases(plant)
    ]


def peak_margin(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
) -> Dict[str, Dict[str, object]]:
    """Return what the plant can give on its peak heat and cold days, and the spare.

    The peak day's demand is raised far above the plant's reach and the year run again; what
    the plant delivers that day is its capacity there (every other day is unchanged).

    Returns
    -------
    dict
        ``heat`` and ``cool``: ``day``, ``demand_mw``, ``capacity_mw``, ``spare_mw``.
    """
    heat, cool = (np.array(a) for a in demand.arrays())
    out = {}
    for side, values in (("heat", heat), ("cool", cool)):
        if not values.any():
            continue
        i = int(np.argmax(values))
        raised = values.copy()
        raised[i] = 10 * values[i] + 100.0
        d = Demand(
            tuple(raised if side == "heat" else heat),
            tuple(raised if side == "cool" else cool),
            demand.dates,
        )
        y = simulate_year(plant, d, doublet, rules, components)
        parts = y.daily_mw[side]
        given = sum(parts[k][i] for k in parts if k not in ("demand", "short"))
        out[side] = {
            "day": _day(i),
            "demand_mw": round(float(values[i]), 2),
            "capacity_mw": round(float(given), 2),
            "spare_mw": round(float(given - values[i]), 2),
        }
    return out


def reliable(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
    excluded: Sequence[str] = (),
    units: int = UNITS,
) -> Tuple[Plant, List[Dict[str, object]], List[Dict[str, object]]]:
    """Size a design so that any one unit can be out all year and every day is still met.

    The boiler and the electric chillers become ``units`` equal units. Each round runs every
    case of ``cases``; the boiler grows by the worst heat gap and the chillers by the worst cold
    gap (by ``units / (units - 1)`` of it when the gap comes from one of their own units, since
    the others must carry it). Excluded units are not grown: the heat pump stands in for a
    boiler and the absorption chiller for the chillers, where they can.

    A unit grows only while growing it closes the gap: when the worst gap of its side shrinks
    by less than a tenth of what was added (a heat pump or absorption chiller with no brine,
    as with a doublet or a shared treatment train out), the growth is taken back and that
    side stops growing. The plan then does not hold, and the last round's outages say which
    cases are not covered (no unit grown to hundreds of MW for a case it cannot cover).

    Returns
    -------
    tuple
        The reliable plant (``reliable=True``), each round's sizes and worst gaps (``stopped``:
        a growth taken back, in words), and the last round's outages (all met when the plan
        holds).
    """
    # With no gas bought the gas boiler burns only the brine's gas: the electric boiler is the
    # one that grows, as equal units.
    electric = plant.gas != "buy"
    p = replace(
        plant,
        boiler_units=1 if electric else units,
        electric_boiler_units=units if electric else plant.electric_boiler_units,
        chiller_units=units,
        reliable=True,
    )
    heat_bank = "electric boiler unit" if electric else "boiler unit"
    rounds: List[Dict[str, object]] = []
    last: List[Dict[str, object]] = []

    def run_cases(plant_now: Plant) -> Tuple[float, float, List[Dict[str, object]]]:
        need_heat = need_cool = 0.0
        rows = []
        for name, unit in cases(plant_now):
            y = simulate_year(_all_year(plant_now, unit), demand, doublet, rules, components)
            rows.append(shortfall(name, y))
            heat, cool = y.peak_shortfall_mw["heat"], y.peak_shortfall_mw["cool"]
            need_heat = max(need_heat, bank_need(heat, units, unit == heat_bank))
            need_cool = max(need_cool, bank_need(cool, units, unit == "chiller unit"))
        return need_heat, need_cool, rows

    stuck: Dict[str, str] = {}  # side -> the unit whose growth did not close its gap
    grown: Dict[str, Tuple[str, float, float]] = {}  # side -> (size key, size before, gap before)
    ran = None  # the plant ``last`` belongs to
    for _ in range(MAX_ROUNDS):
        need_heat, need_cool, last = run_cases(p)
        ran = p
        rounds.append(
            {
                "boiler_mw": p.boiler_mw,
                "electric_boiler_mw": p.electric_boiler_mw,
                "chiller_mw": p.chiller_mw,
                "heat_pump_mw": p.heat_pump_mw,
                "absorption_mw": p.absorption_mw,
                "worst_heat_mw": round(need_heat, 2),
                "worst_cool_mw": round(need_cool, 2),
            }
        )
        # A growth that did not close its side's gap is taken back; that side grows no more.
        back: Dict[str, float] = {}
        said = []
        for side, need in (("heat", need_heat), ("cool", need_cool)):
            if side not in grown:
                continue
            key, before, was = grown[side]
            added = getattr(p, key) - before
            if need > 1e-3 and need > was - max(0.05, 0.1 * added):
                stuck[side] = key
                back[key] = before
                said.append(
                    f"{key[: -len('_mw')].replace('_', ' ')} {getattr(p, key):g} MW left the "
                    f"worst {side} gap at {need:.2f} MW (from {was:.2f}): back to {before:g} MW, "
                    "not covered"
                )
        grown = {}
        if back:
            rounds[-1]["stopped"] = "; ".join(said)
            p = replace(p, **back)
            continue  # the cases again, at the sizes before
        if need_heat <= 1e-3 and need_cool <= 1e-3:
            break
        grow = {}
        if need_heat > 1e-3 and "heat" not in stuck:
            key = None
            if electric and "electric_boiler" not in excluded:  # "boiler": the gas boiler
                key = "electric_boiler_mw"
            elif not electric and "boiler" not in excluded:
                key = "boiler_mw"
            elif p.heat_pump_mw > 0 and "heat_pump" not in excluded:
                key = "heat_pump_mw"
            if key is not None:
                grow[key] = _up(getattr(p, key) + need_heat)
                grown["heat"] = (key, getattr(p, key), need_heat)
        if need_cool > 1e-3 and "cool" not in stuck:
            key = None
            if "chiller" not in excluded:
                key = "chiller_mw"
            elif p.absorption_mw > 0:
                key = "absorption_mw"
            if key is not None:
                grow[key] = _up(getattr(p, key) + need_cool)
                grown["cool"] = (key, getattr(p, key), need_cool)
        if not grow:
            break  # nothing the brief allows can grow (or close the gap): the plan does not hold
        p = replace(p, **grow)
    if ran is not p:  # the rounds ran out after a change: the cases of the plant returned
        _, _, last = run_cases(p)
    return p, rounds, last


def failure(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    events: Sequence[Tuple[str, int, int]],
    rules: Rules = Rules(),
    components: Components = Components(),
) -> YearResult:
    """Return the design's year with these units out on these days (``Plant.outages``)."""
    return simulate_year(
        replace(plant, outages=tuple(plant.outages) + tuple(events)),
        demand,
        doublet,
        rules,
        components,
    )


def remedies(
    plant: Plant,
    demand: Demand,
    doublet: DoubletModel,
    events: Sequence[Tuple[str, int, int]],
    failed: YearResult,
    rules: Rules = Rules(),
    components: Components = Components(),
    excluded: Sequence[str] = (),
) -> List[Dict[str, object]]:
    """Return what would help through these failures, each run through the same days.

    A bigger boiler by the worst heat gap, more chillers by the worst cold gap (each only when
    there is a gap and the unit is allowed); a bank with one of its own units out on the gap's
    days grows by ``units / (units - 1)`` of it (``bank_need``), as the reliable plan does. A
    single boiler, electric boiler or chiller set that fails cannot be grown to cover itself: a
    standby twin of it takes over. With no gas bought the electric boiler is the one grown (the
    gas boiler has only the brine's gas). For each doublet out longer than a swap, a spare ESP
    on the shelf (the doublet back after ``SPARE_ESP_SWAP_DAYS``).

    Until 4 Nov a bank was grown by the gap alone (on the challenge's best design, doublet 1
    and one of three boiler units out in late January: 10 MW more, still 3.3 MW short; 15 MW
    closes it), and a failed single electric boiler was itself grown.

    Returns
    -------
    list of dict
        ``key``, ``name`` (in words), ``plant`` (the design with the remedy), ``events`` (the
        failures with it), ``year``, ``added_mw`` or ``capex_meur``.
    """
    out: List[Dict[str, object]] = []
    heat = failed.peak_shortfall_mw["heat"]
    cool = failed.peak_shortfall_mw["cool"]
    units = {u for u, _, _ in events}
    for unit, key, units_key, word, bank in (
        ("boiler", "boiler_mw", "boiler_units", "boiler", "boiler unit"),
        (
            "electric boiler",
            "electric_boiler_mw",
            "electric_boiler_units",
            "electric boiler",
            "electric boiler unit",
        ),
        ("chillers", "chiller_mw", "chiller_units", "chiller set", "chiller unit"),
    ):
        size = getattr(plant, key)
        if unit in units and size > 0 and getattr(plant, units_key) == 1:
            # The failed unit cannot grow: a standby twin of it takes over (two equal units,
            # one of them out on those days).
            twin = replace(plant, **{key: 2 * size, units_key: 2})
            out.append(
                {
                    "key": f"standby_{unit.replace(' ', '_')}",
                    "name": f"a standby {word} of {size:g} MW",
                    "plant": twin,
                    "events": [(bank if u == unit else u, a, b) for u, a, b in events],
                    "added_mw": size,
                }
            )

    def grown(key: str, units_key: str, bank: str, side: str, word: str, rid: str) -> None:
        n = int(getattr(plant, units_key) or 1)
        more = _up(_need(failed, side, events, bank, n))
        p = replace(plant, **{key: _up(getattr(plant, key) + more)})
        bank_words = f", {n} units" if n > 1 else ""
        out.append(
            {
                "key": rid,
                "name": f"{more:g} MW more {word} ({getattr(p, key):g} MW in all{bank_words})",
                "plant": p,
                "events": list(events),
                "added_mw": more,
            }
        )

    if heat > 1e-3 and "electric_boiler" not in excluded and plant.gas != "buy":
        # No gas bought: the gas boiler has only the brine's gas, so the electric boiler grows
        # (unless it is the single unit that failed: its standby twin is above).
        if "electric boiler" not in units or plant.electric_boiler_mw <= 0:
            grown(
                "electric_boiler_mw",
                "electric_boiler_units",
                "electric boiler unit",
                "heat",
                "electric boiler",
                "electric_boiler",
            )
    elif heat > 1e-3 and "boiler" not in excluded and "boiler" not in units:
        grown("boiler_mw", "boiler_units", "boiler unit", "heat", "boiler", "boiler")
    if cool > 1e-3 and "chiller" not in excluded and "chillers" not in units:
        grown(
            "chiller_mw", "chiller_units", "chiller unit", "cool", "electric chillers", "chillers"
        )
    esp = [e for e in events if e[0].startswith("doublet ")]
    if any(last - first + 1 > SPARE_ESP_SWAP_DAYS for _, first, last in esp):
        swapped = [
            (u, a, min(b, a + SPARE_ESP_SWAP_DAYS - 1)) if u.startswith("doublet ") else (u, a, b)
            for u, a, b in events
        ]
        out.append(
            {
                "key": "spare_esp",
                "name": f"a spare ESP on the shelf (the doublet back after {SPARE_ESP_SWAP_DAYS} "
                "days)",
                "plant": plant,
                "events": swapped,
                "capex_meur": SPARE_ESP_MEUR,
            }
        )
    for r in out:
        r["year"] = failure(r["plant"], demand, doublet, r["events"], rules, components)
    return out


def worst_case(plant: Plant) -> Optional[str]:
    """Return the reliable plan's note on what it does not cover, or None."""
    if not plant.reliable:
        return None
    return (
        "two units out at once, or an outage of the wells' common pipework, is not covered; "
        "the boiler and chillers each come as "
        f"{plant.boiler_units} equal units"
    )
