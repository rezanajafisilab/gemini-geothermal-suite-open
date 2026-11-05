"""Failures and comparisons by code: what a unit out does, what would help, designs side by side.

A failure what-if ("what if the ESP of doublet 1 fails from 10 to 24 January?") runs the design's
year with that unit out on those days (``dioscuri_plant.firm.failure``), and again with each
remedy that could help (``firm.remedies``: more boiler, more chillers, a spare ESP). Without
dates but with a length ("for three weeks"), the worst start in the year is found by running
every one; without either ("if we lose a production pump"), the unit is out all year, the
one-unit-out case. The answer's numbers all come from these runs; the model only words them.

``compare`` sets designs side by side, each figure from its ledger entry, and says which is
lower on each line.
"""

from __future__ import annotations

import logging
from dataclasses import fields, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import dioscuri_plant as dp
from dioscuri_plant import failure_costs as fcost
from dioscuri_plant.components import Components
from dioscuri_plant.firm import SPARE_ESP_MEUR, SPARE_ESP_SWAP_DAYS, failure, remedies, shortfall
from dioscuri_plant.types import DAYS
from gemini_agent import engine, reporter
from gemini_agent.contract import LedgerEntry
from gemini_agent.tools.gemini import doublet_model

GAS_T_CO2 = Components().gas_t_co2_per_mwh  # t CO2 per MWh of gas burned
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
UNIT_WORDS = {
    "heat exchanger": "the heat exchanger",
    "heat pump": "the heat pump",
    "boiler": "the boiler",
    "boiler unit": "one boiler unit",
    "chillers": "the electric chillers",
    "chiller unit": "one chiller unit",
    "absorption": "the absorption chiller",
}


def day_name(i: int) -> str:
    """Return a 0-based day of 2027 as "10 Jan"."""
    m = 0
    while i >= MONTH_DAYS[m]:
        i -= MONTH_DAYS[m]
        m += 1
    return f"{i + 1} {MONTHS[m]}"


def unit_words(unit: str) -> str:
    """Return an outage unit in words: "doublet 1 (its producer or ESP)", "the heat pump"."""
    kind, _, k = unit.rpartition(" ")
    if kind == "doublet":
        return f"doublet {k} (its producer or ESP)"
    if kind == "injector":
        return f"an injector of doublet {k}"
    if kind == "train":
        return f"treatment train {k}"
    return UNIT_WORDS.get(unit, unit)


def _context(entry: LedgerEntry, assumptions: Optional[dict]):
    rules = engine.rules_for(entry.brief)
    return (
        engine.plant_of(entry.alternative),
        engine.demand_of(entry.brief),
        doublet_model(rules),
        rules,
        engine.prices_for(assumptions, entry.brief),
    )


def _short_gwh(year) -> float:
    return sum(float(np.sum(year.daily_mw[s]["short"])) for s in ("heat", "cool")) * 24 / 1000


def worst_start(
    plant, demand, model, rules, unit: str, days: int, window: Tuple[int, int] = (0, DAYS - 1)
) -> Tuple[int, int]:
    """Return the worst and the mildest first day for a unit out ``days`` days in a row.

    Worst is the most energy not delivered, then (when every start is covered) the most gas
    bought; mildest the least. The days stay inside ``window`` (a month the message named).
    """
    starts = range(window[0], max(window[0], window[1] - days + 1) + 1)
    heat, cool = (np.asarray(x) for x in demand.arrays())
    need = heat + cool
    cost = []
    for a in starts:
        y = failure(plant, demand, model, [(unit, a, a + days - 1)], rules)
        # Ties (nothing short, the same gas) go to the window with the most demand.
        tie = float(need[a : a + days].sum()) * 1e-6
        cost.append(_short_gwh(y) * 1e3 + y.purchased_gas_gwh + tie)
    return starts[int(np.argmax(cost))], starts[int(np.argmin(cost))]


def run_failure(
    entry: LedgerEntry, failures: Sequence[object], assumptions: Optional[dict] = None
) -> Dict[str, object]:
    """Run a design through the failures asked about, and through each remedy.

    Parameters
    ----------
    entry : LedgerEntry
        The design.
    failures : sequence of parameters.Failure
        The units out: dated, a length only (the worst start is taken), or neither (all year).
    assumptions : dict, optional
        The conversation's prices.

    Returns
    -------
    dict
        ``design``, ``events`` (unit, words, first and last day, how the days were set),
        ``failed`` (the shortfall per side, the days short in the window, extra gas, CO2 and
        running cost against the normal year), ``remedies`` (each with what is still short,
        whether it covers every day, its capital and yearly cost), ``needed`` and ``best``.
    """
    plant, demand, model, rules, prices = _context(entry, assumptions)
    events: List[Tuple[str, int, int]] = []
    shown: List[Dict[str, object]] = []
    for f in failures:
        how = "asked"
        planned = getattr(f, "planned", False)
        if f.dated and f.days and f.days < f.last - f.first + 1:
            worst, mild = worst_start(
                plant, demand, model, rules, f.unit, int(f.days), (int(f.first), int(f.last))
            )
            first, other = (mild, worst) if planned else (worst, mild)
            last = first + int(f.days) - 1
            span = f"between {day_name(int(f.first))} and {day_name(int(f.last))}"
            how = (
                f"the mildest {f.days} days {span} for planned work (from {day_name(other)} "
                "they would be worst)"
                if planned
                else f"the worst {f.days} days {span} (from {day_name(other)} they would be "
                "mildest)"
            )
        elif f.dated:
            first, last = int(f.first), int(f.last)
        elif f.days:
            worst, mild = worst_start(plant, demand, model, rules, f.unit, int(f.days))
            first, other = (mild, worst) if planned else (worst, mild)
            last = first + int(f.days) - 1
            how = (
                f"the mildest {f.days} days of the year for planned work (from {day_name(other)} "
                "they would be worst)"
                if planned
                else f"the worst {f.days} days of the year (from {day_name(other)} they would be "
                "mildest)"
            )
        else:
            first, last, how = 0, DAYS - 1, "all year (one unit out)"
        events.append((f.unit, first, last))
        shown.append(
            {
                "unit": f.unit,
                "words": unit_words(f.unit),
                "first": first,
                "last": last,
                "from": day_name(first),
                "to": day_name(last),
                "days": last - first + 1,
                "how": how,
                "assumed": getattr(f, "assumed", ""),
            }
        )
    base_year = dp.simulate_year(plant, demand, model, rules)
    failed = failure(plant, demand, model, events, rules)
    ref = None
    base_econ = dp.economics(plant, base_year, prices, reference=ref, rules=rules)
    lost = shortfall("failed", failed)
    window = sorted({d for _, a, b in events for d in range(a, b + 1)})
    days = []
    for d in window:
        h = failed.daily_mw["heat"]
        c = failed.daily_mw["cool"]
        if h["short"][d] > 1e-3 or c["short"][d] > 1e-3:
            days.append(
                {
                    "day": day_name(d),
                    "heat_demand_mw": round(h["demand"][d], 2),
                    "heat_short_mw": round(h["short"][d], 2),
                    "boiler_mw": round(h["boiler"][d], 2),
                    "cool_short_mw": round(c["short"][d], 2),
                }
            )
    boiler_full = any(
        d["boiler_mw"] >= 0.99 * plant.boiler_mw for d in days if plant.boiler_mw and d["boiler_mw"]
    )
    # The electric boiler's grid charge jumps for the whole year when the outage pushes it past
    # the 600-hour contract (a fixed line, so not in the running costs).
    grid = (
        fcost.grid_meur(failed, prices) - fcost.grid_meur(base_year, prices)
        if plant.electric_boiler_mw > 0
        else 0.0
    )
    out: Dict[str, object] = {
        "design": reporter.design_id(entry),
        "code": entry.alternative.code,
        "events": shown,
        "failed": {
            "heat": lost["heat"],
            "cool": lost["cool"],
            "days": days[:31],
            "boiler_full": boiler_full,
            "extra_gas_gwh": round(failed.purchased_gas_gwh - base_year.purchased_gas_gwh, 3),
            "extra_co2_t": round(failed.co2_t["total"] - base_year.co2_t["total"], 1),
            # Running costs and the grid charge's change: the fixed O&M follows the plant as
            # built, not the year's peak brine (with a doublet out all year it fell, a saving
            # that is not there).
            "extra_cost_keur": round(
                (
                    fcost.running_meur(failed, prices, rules)
                    - fcost.running_meur(base_year, prices, rules)
                    + grid
                )
                * 1000,
                1,
            ),
            "extra_grid_keur": round(grid * 1000, 1),
            "electric_boiler_hours": (
                round(fcost.electric_boiler_hours(failed), 0)
                if plant.electric_boiler_mw > 0
                else None
            ),
            "electric_boiler_hours_normal": (
                round(fcost.electric_boiler_hours(base_year), 0)
                if plant.electric_boiler_mw > 0
                else None
            ),
            "grid_limit_hours": fcost.GRID_600H,
        },
    }
    needed = lost["heat"]["days_short"] > 0 or lost["cool"]["days_short"] > 0
    rows = []
    out["spare_esp"] = None
    if not needed:
        # Nothing short, but a spare ESP still shortens a doublet's outage: the gas it saves.
        for r in remedies(
            plant, demand, model, events, failed, rules, excluded=entry.brief.excluded
        ):
            if r["key"] == "spare_esp":
                saved = failed.purchased_gas_gwh - r["year"].purchased_gas_gwh
                out["spare_esp"] = {
                    "name": r["name"],
                    "gas_saved_gwh": round(saved, 3),
                    "co2_saved_t": round(failed.co2_t["total"] - r["year"].co2_t["total"], 1),
                    # All running costs (gas, its CO2, the pumps' power, gas sold), as the
                    # failure's own extra cost: gas and CO2 alone overstated it.
                    "money_saved_keur": round(
                        (
                            fcost.running_meur(failed, prices, rules)
                            - fcost.running_meur(r["year"], prices, rules)
                            + fcost.grid_meur(failed, prices)
                            - fcost.grid_meur(r["year"], prices)
                        )
                        * 1000,
                        1,
                    ),
                    "yearly_keur": round(fcost.spare_yearly_keur(prices), 1),
                    "capex_meur": SPARE_ESP_MEUR,
                }
    if needed:
        mwh = (base_year.heat_delivered_gwh + base_year.cool_delivered_gwh) * 1000
        for r in remedies(
            plant, demand, model, events, failed, rules, excluded=entry.brief.excluded
        ):
            after = shortfall(r["key"], r["year"])
            row = {
                "key": r["key"],
                "name": r["name"],
                "heat_short_mw": after["heat"]["worst_mw"],
                "cool_short_mw": after["cool"]["worst_mw"],
                "short_gwh": round(after["heat"]["short_gwh"] + after["cool"]["short_gwh"], 3),
                "covers": after["heat"]["days_short"] == 0 and after["cool"]["days_short"] == 0,
            }
            if r["key"] == "spare_esp":
                # The spare is fitted at the next failure anyway: its cost is the capital tied up
                # (its price over the doublets' life, as in the failures over a year).
                yearly = fcost.spare_yearly_keur(prices)
                row.update(capex_meur=SPARE_ESP_MEUR, yearly_keur=round(yearly, 1))
            else:
                p = r["plant"]
                y = dp.simulate_year(p, demand, model, rules)
                e = dp.economics(p, y, prices, rules=rules)
                row.update(
                    capex_meur=round(e.capex_meur - base_econ.capex_meur, 3),
                    yearly_keur=round(
                        (e.lcoe_eur_per_mwh - base_econ.lcoe_eur_per_mwh) * mwh / 1000, 1
                    ),
                    lcoe_delta=round(e.lcoe_eur_per_mwh - base_econ.lcoe_eur_per_mwh, 2),
                )
            rows.append(row)
    covering = [r for r in rows if r["covers"]]
    best = min(covering, key=lambda r: r["yearly_keur"], default=None)
    if best is None and rows:
        best = min(rows, key=lambda r: r["short_gwh"])
    out.update(needed=needed, remedies=rows, best=best["key"] if best else None)
    # Failures over a year on average: what they cost, and what a spare ESP is worth.
    out["yearly"] = _yearly_safe(entry, assumptions, base_year)
    return out


def failure_text(
    result: Dict[str, object], facts: reporter.Facts, plan: Optional[LedgerEntry]
) -> str:
    """Return the failure what-if in words, every number from ``run_failure``.

    ``plan`` is the reliable plan of the same layout from the last search, when there is one.
    """
    num = reporter.num
    ev = result["events"]
    parts = []
    for e in ev:
        when = (
            "all year"
            if e["days"] >= DAYS
            else f"from {facts.put(e['from'])} to {facts.put(e['to'])} "
            f"({facts.put(str(e['days']))} days)"
        )
        note = ""
        if e["how"].startswith(("the worst", "the mildest")):
            note = f", {facts.put(e['how'])}"  # code's words: its days and dates are facts
        parts.append(f"{e['words']} out {when}{note}")
    head = f"With {' and '.join(parts)}, {result['design']}"
    f = result["failed"]
    said = []
    for side, word in (("heat", "heat"), ("cool", "cold")):
        x = f[side]
        if x["days_short"]:
            said.append(
                f"{word} demand is NOT met on {facts.put(str(x['days_short']))} days: worst "
                f"{facts.put(x['worst_day'])}, {facts.put(num(x['worst_mw']))} MW short; "
                f"{facts.put(num(x['short_gwh'], 2))} GWh not delivered"
            )
    if not said:
        text = (
            f"{head} still meets heat and cold every day: the other units cover it. No spare is "
            "needed to keep everyone supplied."
        )
        if f["extra_gas_gwh"] > 0.001:
            text += (
                f" It burns {facts.put(num(f['extra_gas_gwh'], 2))} GWh more gas, "
                f"{facts.put(num(f['extra_co2_t'], 0))} t more CO₂ (running costs "
                f"{facts.put(num(f['extra_cost_keur'], 0))} k€ more for the year)."
            )
        text += _grid_words(f, facts)
        esp = result.get("spare_esp")
        if esp and esp["gas_saved_gwh"] > 0.001:
            text += (
                f" {esp['name'][0].upper()}{esp['name'][1:]} would save "
                f"{facts.put(num(esp['gas_saved_gwh'], 2))} GWh of that gas "
                f"({facts.put(num(esp['money_saved_keur'], 0))} k€ of running costs) for about "
                f"{facts.put(num(esp['yearly_keur'], 0))} k€ a year of capital tied up in it."
            )
        return _with_yearly(text, result, facts)
    text = f"{head}: " + "; ".join(said) + "."
    if f["boiler_full"]:
        text += " The boiler is already at full output on those days."
    if f["extra_gas_gwh"] > 0.001:
        text += (
            f" Meanwhile it burns {facts.put(num(f['extra_gas_gwh'], 2))} GWh more gas "
            f"({facts.put(num(f['extra_co2_t'], 0))} t more CO₂)."
        )
    elif f["extra_cost_keur"] < 0:
        text += (
            f" Running costs fall by {facts.put(num(-f['extra_cost_keur'], 0))} k€ only because "
            "that heat or cold is not delivered (unserved energy is not priced)."
        )
    text += _grid_words(f, facts)
    rows = result["remedies"]
    if rows:
        out_days = max(e["days"] for e in ev)
        bits = []
        for r in rows:
            if r["key"] == "spare_esp":
                what = (
                    f"With a spare ESP on the shelf the doublet is back after "
                    f"{facts.put(str(SPARE_ESP_SWAP_DAYS))} days instead of "
                    f"{facts.put(str(out_days))}"
                )
                cost = (
                    f"it costs about {facts.put(num(r['yearly_keur'], 0))} k€ a year in capital "
                    f"tied up ({facts.put(num(r['capex_meur'], 2))} M€; the pump is fitted at the "
                    "next failure anyway)"
                )
            else:
                what = f"With {facts.put(r['name'])}"  # its size is code's (16.4 MW)
                cost = (
                    f"it costs {facts.put(num(r['capex_meur'], 2))} M€ of capital, "
                    f"{facts.put(num(r['lcoe_delta'], 2))} €/MWh more in a normal year"
                )
            effect = (
                "every day is met"
                if r["covers"]
                else f"heat is still short on the first days, by up to "
                f"{facts.put(num(max(r['heat_short_mw'], r['cool_short_mw'])))} MW "
                f"({facts.put(num(r['short_gwh'], 2))} GWh instead of "
                f"{facts.put(num(f['heat']['short_gwh'] + f['cool']['short_gwh'], 2))})"
            )
            bits.append(f"{what}, {effect}; {cost}.")
        text += " A spare or backup is needed to keep everyone supplied. " + " ".join(bits)
        best = next((r for r in rows if r["key"] == result["best"]), None)
        if best is not None:
            text += (
                f" The cheapest that {'covers every day' if best['covers'] else 'helps most'} is "
                f"{facts.put(best['name'])}."
            )
    if plan is not None:
        text += (
            f" The reliable plan of this layout, {reporter.design_id(plan)}, is sized so that "
            f"any one unit can be out ({facts.put(num(plan.economics.lcoe_eur_per_mwh))} €/MWh)."
        )
    if any(e["assumed"] for e in ev):
        text += " I took " + "; ".join(facts.put(e["assumed"]) for e in ev if e["assumed"]) + "."
    return _with_yearly(text, result, facts)


def _grid_words(failed: Dict[str, object], facts: reporter.Facts) -> str:
    """Return the electric boiler's hours against the 600-hour grid contract, or ""."""
    hours = failed.get("electric_boiler_hours")
    if hours is None:
        return ""
    num = reporter.num
    limit = float(failed.get("grid_limit_hours") or fcost.GRID_600H)
    normal = failed.get("electric_boiler_hours_normal") or 0.0
    grid = float(failed.get("extra_grid_keur") or 0.0)
    if grid > 0.5:
        return (
            f" The electric boiler runs {facts.put(num(hours, 0))} hours at its peak this year "
            f"({facts.put(num(normal, 0))} in a normal year), past the grid's "
            f"{facts.put(num(limit, 0))}-hour contract: the year's grid charge rises by "
            f"{facts.put(num(grid, 0))} k€, so the year costs "
            f"{facts.put(num(failed['extra_cost_keur'], 0))} k€ more in running costs and grid "
            "charge (the 600 hours are per connection: the backup electric boiler is assumed to "
            "have its own)."
        )
    if hours > 0 and hours <= limit:
        return (
            f" The electric boiler runs {facts.put(num(hours, 0))} hours at its peak this year, "
            f"within the grid's {facts.put(num(limit, 0))}-hour contract "
            f"({facts.put(num(limit - hours, 0))} hours to spare)."
        )
    return ""


def _with_yearly(text: str, result: Dict[str, object], facts: reporter.Facts) -> str:
    """Return a failure answer with what failures cost over a year, when it was run."""
    line = failure_costs_text(result.get("yearly"), facts)
    return f"{text}\n\n{line}" if line else text


def failure_must(result: Dict[str, object]) -> List[str]:
    """Return the values a reworded failure answer must keep."""
    out = []
    for side in ("heat", "cool"):
        x = result["failed"][side]
        if x["days_short"]:
            out.append(f"{reporter.num(x['worst_mw'])} MW")
    return out


# ------------------------------------------------------------------ comparisons

ROWS = (
    # key, label, unit, digits, lower is better
    ("lcoe", "Cost of heat and cold", "€/MWh", 1, True),
    ("lcoh", "Cost of heat", "€/MWh", 1, True),
    ("lcoc", "Cost of cold", "€/MWh", 1, True),
    ("co2_t", "CO₂", "t/yr", 0, True),
    ("vs_gas", "Against gas", "%", 0, True),
    ("capex", "Capital", "M€", 1, True),
    ("npv", "NPV against gas", "M€", 1, False),
    ("payback", "Pays back (discounted)", "years", 0, True),
    ("wells", "Wells", "", 0, True),
    ("boiler", "Boiler", "MW", 1, None),
    ("heat_pump", "Heat pump", "MW", 1, None),
    ("chillers", "Electric chillers", "MW", 1, None),
    ("spare_heat", "Spare heat on the peak day", "MW", 1, False),
    ("n1", "One unit out: cases short", "", 0, True),
)


def values(e: LedgerEntry, assumptions: Optional[dict] = None) -> Dict[str, Optional[float]]:
    """Return the figures a comparison shows for one design, money at its own conditions."""
    firm = engine.firm(e) or {}
    money: Dict[str, object] = {}
    vs: Dict[str, Optional[float]] = {}
    if e.alternative.depth_m:
        ref = engine.reference(e.brief, assumptions)
        money = engine.versus_reference(e, ref, engine.prices_for(assumptions, e.brief))
        vs = engine.against_gas(e, ref)
    cases = firm.get("outages") or []
    peak = (firm.get("peak") or {}).get("heat") or {}
    s = e.alternative.sizes_mw
    return {
        "lcoe": e.economics.lcoe_eur_per_mwh,
        "lcoh": e.economics.lcoh_eur_per_mwh,
        "lcoc": e.economics.lcoc_eur_per_mwh,
        "co2_t": e.economics.co2_t_per_year,
        "capex": e.economics.capex_meur,
        "vs_gas": round(vs["total"] * 100, 1) if vs.get("total") is not None else None,
        "npv": money.get("npv_meur"),
        "payback": money.get("payback_years"),
        "wells": float(sum(1 + int(d.get("injectors") or 1) for d in e.alternative.doublets)),
        "boiler": s.get("boiler", 0.0),
        "heat_pump": s.get("heat_pump", 0.0),
        "chillers": s.get("chillers", 0.0),
        "spare_heat": peak.get("spare_mw"),
        "n1": (
            float(sum(1 for o in cases if o["heat"]["days_short"] or o["cool"]["days_short"]))
            if cases
            else None
        ),
    }


def compare(
    entries: Sequence[LedgerEntry], assumptions: Optional[dict] = None
) -> Dict[str, object]:
    """Return designs side by side: one row per figure, the lowest (or highest) marked.

    Returns
    -------
    dict
        ``designs`` (id, code, name, picks, scenario), ``rows`` (key, label, unit, values, best
        index) and ``mixed`` (True when they come from different conditions: no row is marked).
    """
    vals = [values(e, assumptions) for e in entries]
    scenes = [scenario_words(e) for e in entries]
    mixed = len(set(scenes)) > 1
    rows = []
    for key, label, unit, digits, lower in ROWS:
        xs = [v[key] for v in vals]
        known = [(i, x) for i, x in enumerate(xs) if x is not None]
        best = None
        same = len({round(x, digits) for _, x in known}) > 1
        money_row = key in ("lcoe", "lcoh", "lcoc", "vs_gas", "npv", "payback")
        if lower is not None and len(known) > 1 and same and not (mixed and money_row):
            pick = min if lower else max
            best = pick(known, key=lambda t: t[1])[0]
        rows.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "digits": digits,
                "values": [None if x is None else round(x, digits) for x in xs],
                "best": best,
            }
        )
    return {
        "designs": [
            {
                "id": reporter.design_id(e),
                "code": e.alternative.code,
                "name": e.alternative.name,
                "picks": list(e.alternative.picks),
                "reliable": e.alternative.reliable,
                "scenario": scenes[i],
            }
            for i, e in enumerate(entries)
        ],
        "rows": rows,
        "mixed": mixed,
    }


def scenario_words(e: LedgerEntry) -> str:
    """Return the conditions a design was run under, in words ("base case", "gas 30 €/MWh")."""
    if e.change_label:
        return e.change_label.replace(", searched again", "")
    return "base case"


def compare_text(table: Dict[str, object], facts: reporter.Facts, markdown: bool = False) -> str:
    """Return a comparison in words (the card shows the table), or as a Markdown table too.

    Each design's headline figures in one line, then which is lowest on each.
    """
    names = [d["id"] for d in table["designs"]]
    rows = {r["key"]: r for r in table["rows"]}
    if not markdown:
        parts = []
        for i, name in enumerate(names):
            bits = []
            for key, unit in (
                ("lcoe", "€/MWh of heat and cold"),
                ("co2_t", "t CO₂ a year"),
                ("capex", "M€ of capital"),
                ("n1", "one-unit-out cases short"),
            ):
                v = rows[key]["values"][i]
                if v is not None:
                    bits.append(f"{facts.put(reporter.num(v, rows[key]['digits']))} {unit}")
            parts.append(f"{name}: " + ", ".join(bits))
        said = [
            f"{rows[k]['label'].lower()}: {names[rows[k]['best']]}"
            for k in ("lcoe", "co2_t", "capex", "n1")
            if rows[k]["best"] is not None
        ]
        return "; ".join(parts) + "." + (" Lowest " + "; ".join(said) + "." if said else "")
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for r in table["rows"]:
        if all(v is None for v in r["values"]):
            continue
        cells = []
        for i, v in enumerate(r["values"]):
            cell = "–" if v is None else facts.put(reporter.num(v, r["digits"]))
            if r["best"] == i:
                cell = f"**{cell}**"
            cells.append(cell)
        unit = f" ({r['unit']})" if r["unit"] else ""
        lines.append(f"| {r['label']}{unit} | " + " | ".join(cells) + " |")
    rows = {r["key"]: r for r in table["rows"]}
    said = []
    for key in ("lcoe", "co2_t", "capex", "n1"):
        r = rows[key]
        if r["best"] is not None:
            said.append(f"{r['label'].lower()}: {names[r['best']]}")
    text = "\n".join(lines)
    if said:
        text += "\n\nLowest " + "; ".join(said) + " (bold in the table)."
    return text


def resolve(names: Sequence[str], session) -> Tuple[List[LedgerEntry], List[str]]:
    """Return the designs a message names (ids, codes, picks), and the names not found.

    Ids (A1, W2) and codes match the conversation's designs and the last search's candidates;
    the picks' names ("the cheapest", "cheapest reliable" or "most reliable", "greenest
    reliable", "best overall", "lowest CO2") the last search's picks; "the what-if" the latest
    what-if; "the pick" the chosen design. A name with "reliab" in it is a reliable pick before
    anything else ("cheapest reliable" is not the cheapest; "greenest reliable" not the lowest
    CO2).
    """
    # The conversation's designs, then the last search's candidates, then every earlier one's.
    pool: List[LedgerEntry] = list(session.ledger) + [
        e for e in session.candidates or [] if e.alternative.role in ("chosen", "candidate")
    ]
    pool += [
        e
        for srch in reversed(getattr(session, "searches", None) or [])
        for e in srch.get("candidates") or []
        if e.alternative.role in ("chosen", "candidate") and all(e is not x for x in pool)
    ]
    own = {str(v).lower(): k for k, v in (getattr(session, "design_names", None) or {}).items()}
    found: List[LedgerEntry] = []
    missing: List[str] = []
    picks = {}
    for e in session.candidates or []:
        for k in e.alternative.picks:
            picks.setdefault(k, e)
    words = (
        ("gas-free", "gas_free"),
        ("cheap", "cost"),
        ("co2", "co2"),
        ("carbon", "co2"),
        ("green", "co2"),
        ("emission", "co2"),
        ("reliab", "reliable"),
        ("best", "best"),
        ("recommend", "best"),
    )
    for name in names:
        n = name.strip().lower()
        from gemini_agent.reporter import design_id

        hit = (
            next((e for e in pool if design_id(e).lower() == n), None)
            or next((e for e in pool if e.alternative.uid and e.alternative.uid.lower() == n), None)
            or next((e for e in pool if own.get(n) == design_id(e)), None)
            or next((e for e in reversed(pool) if e.alternative.code.lower() == n), None)
        )
        if hit is None and "reliab" in n:
            green = any(w in n for w in ("green", "co2", "carbon", "emission"))
            k = "green_reliable" if green and "green_reliable" in picks else "reliable"
            hit = picks.get(k)
        if hit is None:
            for w, k in words:
                if w in n and k in picks:
                    hit = picks[k]
                    break
        if hit is None and "what" in n and "if" in n:
            hit = next(
                (e for e in reversed(session.ledger) if e.alternative.role == "what_if"), None
            )
        if hit is None and ("pick" in n or "chosen" in n or "current" in n):
            hit = session.chosen
        if hit is None:
            missing.append(name)
        elif all(hit is not f for f in found):
            found.append(hit)
    return found, missing


PICK_HINTS = {  # a design the reader named by its pick, in the message's words
    "cost": ("cheap", "goedkoop", "günstig", "billig"),
    "co2": ("co2", "co₂", "carbon", "green", "emission", "groen", "grün"),
    "reliable": ("reliab", "betrouwba", "zuverlässig"),
    "green_reliable": ("green", "groen", "grün"),
    "gas_free": ("gas-free", "gas free", "no gas", "gasvrij", "gasfrei", "all-electric"),
    "best": ("best overall", "recommended", "aanbevolen", "empfohlen"),
}


def target(names: Sequence[str], message: str, session) -> Optional[LedgerEntry]:
    """Return the design a failure question is about: one the message names, else the current.

    The reader lists designs it saw, the current one too; only one the message names by its id,
    its code or its pick ("the cheapest") is taken.
    """
    text = message.lower()
    found, _ = resolve(names, session)
    for e in found:
        a = e.alternative
        if (a.uid and a.uid.lower() in text) or a.code.lower() in text:
            return e
        if any(w in text for k in a.picks for w in PICK_HINTS.get(k, ())):
            return e
    if not found:  # the reader named none: a pick of the last search the message names
        for e in session.candidates or []:
            if e.alternative.picks and e.alternative.picks != ["best"]:
                if any(w in text for k in e.alternative.picks for w in PICK_HINTS.get(k, ())):
                    return e
    return session.chosen


def reliable_of(entry: LedgerEntry, candidates: Sequence[LedgerEntry]) -> Optional[LedgerEntry]:
    """Return the reliable plan of a design's layout from the search, if there is one."""
    if entry.alternative.reliable:
        return entry
    code = entry.alternative.code + "-N1"
    plans = [
        e for e in candidates or [] if e.alternative.code == code and e.alternative.role != "failed"
    ]
    # A layout may have two plans (its cheapest sizing and the one best with CO2 at the
    # long-term price): the one built on this design's heat pump first.
    hp = (entry.alternative.sizes_mw or {}).get("heat_pump")
    same = [e for e in plans if (e.alternative.sizes_mw or {}).get("heat_pump") == hp]
    return (same or plans or [None])[0]


def failure_verdict(result: Dict[str, object], facts: reporter.Facts) -> str:
    """Return a failure's conclusion in one line: short or not, and what covers it cheapest."""
    f = result["failed"]
    ev = "; ".join(f"{e['words']} out {e['from']}-{e['to']}" for e in result["events"])
    if not result.get("needed"):
        return f"{ev}: {result['design']} still meets every day; no spare is needed."
    worst = max(f["heat"]["worst_mw"], f["cool"]["worst_mw"])
    best = next((r for r in result.get("remedies") or [] if r["key"] == result.get("best")), None)
    text = (
        f"{ev}: {result['design']} is short by up to {facts.put(reporter.num(worst))} MW "
        f"({facts.put(reporter.num(f['heat']['short_gwh'] + f['cool']['short_gwh'], 2))} GWh)"
    )
    if best is not None:
        text += (
            f"; the cheapest that {'covers it' if best['covers'] else 'helps most'}: {best['name']}"
        )
    return text + "."


def compare_verdict(table: Dict[str, object], facts: reporter.Facts) -> str:
    """Return a comparison's conclusion in one line: which is lowest on cost, CO2, capital, N-1."""
    names = [d["id"] for d in table["designs"]]
    rows = {r["key"]: r for r in table["rows"]}
    said = []
    for key, words in (
        ("lcoe", "cheapest"),
        ("co2_t", "least CO₂"),
        ("capex", "least capital"),
        ("n1", "fewest one-unit-out cases short"),
    ):
        r = rows.get(key)
        if r is not None and r["best"] is not None:
            said.append(f"{words}: {names[r['best']]}")
    return ("; ".join(said) + ".") if said else ""


# ------------------------------------------------------------------ the decision summary

HOME_MWH = 12.0  # a Dutch home's heat a year (CBS: about 1,200 m3 of gas), when no count is given


def decision(session) -> Optional[Dict[str, object]]:
    """Return the decision table for a client: gas, the recommended design and the other picks.

    Per option: capital, cost of heat and cold and against gas, the yearly bill, the heat cost
    per home, CO2 and its cut, the share of heat from the gas boiler, N-1, and the cost per tonne
    of CO2 avoided against gas. Every figure from the designs' runs.
    """
    chosen = session.chosen
    if chosen is None:
        return None
    pool = [e for e in session.candidates or [] if e.alternative.role in ("chosen", "candidate")]
    picks = {}
    for e in pool:
        for k in e.alternative.picks:
            picks.setdefault(k, e)
    order = [("recommended", chosen)] + [
        (k, picks[k]) for k in ("cost", "co2", "reliable") if k in picks
    ]
    ref = engine.reference(chosen.brief, session.assumptions or None)
    homes = chosen.brief.homes
    home_words = (
        f"per home ({homes:,} homes)" if homes else f"per home of {HOME_MWH:g} MWh of heat a year"
    )
    names = {
        "recommended": "Recommended",
        "cost": "Cheapest",
        "co2": "Lowest CO₂",
        "reliable": "Cheapest reliable",
    }
    rows: List[Dict[str, object]] = []
    seen = set()

    def row(label, e, is_ref=False):
        y, ec = e.year, e.economics
        heat_mwh = (y.heat_delivered_gwh or 0) * 1000
        cold_mwh = (y.cool_delivered_gwh or 0) * 1000
        yearly = ec.lcoe_eur_per_mwh * (heat_mwh + cold_mwh) / 1e6  # M€ a year, capital included
        heat_bill = ec.lcoh_eur_per_mwh * heat_mwh
        per_home = heat_bill / homes if homes else ec.lcoh_eur_per_mwh * HOME_MWH
        heat = y.heat_delivered_gwh or 1.0
        firm = reporter.firm_view(e) if not is_ref else None
        return {
            "label": label,
            "id": "gas boilers and electric chillers" if is_ref else reporter.design_id(e),
            "capex_meur": round(ec.capex_meur, 1),
            "lcoe": round(ec.lcoe_eur_per_mwh, 1),
            "vs_gas": None if is_ref else engine.against_gas(e, ref).get("total"),
            "yearly_meur": round(yearly, 2),
            "per_home_eur": round(per_home, 0),
            "co2_t": round(ec.co2_t_per_year, 0),
            "co2_cut": None if is_ref else round(ec.co2_saving_vs_gas or 0.0, 3),
            "gas_share": round((y.heat_split_gwh or {}).get("boiler", 0.0) / heat, 3),
            "n1": None if is_ref else (firm or {}).get("short", None),
            "eur_per_t": None,
            "reliable": False if is_ref else e.alternative.reliable,
        }

    gas = row("Gas (today's way)", ref, is_ref=True)
    rows.append(gas)
    for key, e in order:
        k = reporter.design_id(e)
        if k in seen:
            for r in rows:
                if r["id"] == k:
                    r["label"] += f" · {names[key].lower()}"
            continue
        seen.add(k)
        r = row(names[key], e)
        cut_t = gas["co2_t"] - r["co2_t"]
        r["eur_per_t"] = (
            round((r["yearly_meur"] - gas["yearly_meur"]) * 1e6 / cut_t, 0) if cut_t > 0 else None
        )
        rows.append(r)
    return {"rows": rows, "home_words": home_words, "homes": homes}


def decision_text(table: Dict[str, object], facts: reporter.Facts) -> str:
    """Return a short memo for a council from the decision table, every number from it."""
    num = reporter.num
    rows = table["rows"]
    gas, rec = rows[0], rows[1]
    lines = []
    cut = rec["co2_cut"] or 0.0
    lines.append(
        f"We recommend {rec['id']}. It delivers heat and cold for "
        f"{facts.put(num(rec['lcoe']))} €/MWh ({facts.put(_vs(rec['vs_gas']))} than gas boilers "
        f"and electric chillers at {facts.put(num(gas['lcoe']))} €/MWh), cuts CO₂ by "
        f"{facts.put(reporter.pct(cut))} ({facts.put(num(gas['co2_t'] - rec['co2_t'], 0))} t a "
        f"year) and needs {facts.put(num(rec['capex_meur']))} M€ of capital."
    )
    if rec["n1"] == 0:
        lines.append("It keeps every building supplied when any one unit fails.")
    lines.append(
        f"Heat costs about {facts.put(num(rec['per_home_eur'], 0))} € a year {table['home_words']} "
        f"(gas: {facts.put(num(gas['per_home_eur'], 0))} €). The gas boiler still makes "
        f"{facts.put(reporter.pct(rec['gas_share']))} of the heat, on the coldest days and when a "
        "unit is out."
    )
    for r in rows[2:]:
        extra = []
        if r["eur_per_t"] is not None:
            per_t = facts.put(num(abs(r["eur_per_t"]), 0))
            extra.append(
                f"saves {per_t} € for each tonne of CO₂ avoided against gas"
                if r["eur_per_t"] < 0
                else f"costs {per_t} € per tonne of CO₂ avoided against gas"
            )
        if r["n1"]:
            extra.append(f"not covered for one unit out ({facts.put(str(r['n1']))} cases)")
        lines.append(
            f"{r['label']}: {r['id']}, {facts.put(num(r['lcoe']))} €/MWh, "
            f"{facts.put(num(r['co2_t'], 0))} t CO₂ a year, {facts.put(num(r['capex_meur']))} M€"
            + (f" ({'; '.join(extra)})" if extra else "")
            + "."
        )
    return " ".join(lines[:3]) + "\n\n" + "\n".join(f"- {x}" for x in lines[3:])


def _vs(frac: Optional[float]) -> str:
    if frac is None:
        return "the same"
    p = round(abs(frac) * 100)
    return "the same" if p == 0 else f"{p} % {'cheaper' if frac < 0 else 'dearer'}"


# ------------------------------------------------------------------ uncertainty


def uncertainty_card(result: Dict[str, object], known: Dict[str, dict]) -> Dict[str, object]:
    """Return a sensitivity run as the chat's card: the ranges and what moves the cost most."""
    mc = (result.get("monte_carlo") or {}).get("outputs") or {}
    base = result.get("base") or {}
    tornado = []
    for t in (result.get("tornado") or [])[:6]:
        lo, hi = t["low"].get("lcoe"), t["high"].get("lcoe")
        if lo is None or hi is None:
            continue
        p = known.get(t["key"], {})
        tornado.append(
            {
                "key": t["key"],
                "label": t["label"],
                "unit": p.get("unit", ""),
                "kind": p.get("kind", "absolute"),
                "from": p.get("low"),
                "to": p.get("high"),
                "lcoe_low": round(lo, 2),
                "lcoe_high": round(hi, 2),
            }
        )
    run = result.get("monte_carlo") or {}
    card = {
        "design": result.get("design"),
        "base": {k: base.get(k) for k in ("lcoe", "npv_meur", "co2_saving_pct")},
        "lcoe": mc.get("lcoe"),
        "npv": mc.get("npv_meur"),
        "co2": mc.get("co2_saving_pct"),
        "samples": run.get("samples"),
        # Where the design's own case sits among the runs (0.5: the median).
        "base_percentile": {
            k: (mc.get(m) or {}).get("base_percentile")
            for k, m in (("lcoe", "lcoe"), ("npv", "npv_meur"), ("co2", "co2_saving_pct"))
        },
        "draw": run.get("draw") or "uniform",
        "tornado": tornado,
        "seconds": result.get("seconds"),
    }
    card["verdict"] = ""
    return card


def _swing(t: Dict[str, object], facts: reporter.Facts) -> str:
    """Return an input's swing in its own unit: "the gas price from 25 to 70 €/MWh".

    A change ("the reservoir 10 °C colder to 5 °C warmer") or a factor ("capital ×0.8 to ×1.3")
    as such, so a reader never takes the cost it gives for the input's own range.
    """
    name, lo, hi, unit = t["label"].lower(), t.get("from"), t.get("to"), t.get("unit") or ""
    if lo is None or hi is None:
        return name
    lo, hi = float(lo), float(hi)
    if t.get("kind") == "delta":

        def side(x):
            return f"{facts.put(f'{abs(x):g}')} {unit} {'colder' if x < 0 else 'warmer'}"

        return f"{name} {side(lo)} to {side(hi)} than expected"
    if t.get("kind") == "scale" or unit in ("×", "x"):
        return f"{name} ×{facts.put(f'{lo:g}')} to ×{facts.put(f'{hi:g}')}"
    if not unit and hi < 1:  # a rate: 0.03 is 3 %
        return f"{name} from {facts.put(reporter.pct(lo))} to {facts.put(reporter.pct(hi))}"
    return f"{name} from {facts.put(f'{lo:g}')} to {facts.put(f'{hi:g}')} {unit}".rstrip()


def uncertainty_text(card: Dict[str, object], facts: reporter.Facts) -> str:
    """Return the ranges in words: P10-P90 of the cost and NPV, the chance it beats gas.

    The text says the inputs were drawn independently: no correlation between them (gas and
    electricity prices, or the capital costs, do not move together), as ``workbench.
    sensitivity`` draws them.
    """
    num = reporter.num
    lines = []
    lc, npv = card.get("lcoe"), card.get("npv")
    if lc:
        centred = str(card.get("draw", "")).startswith("triangular")
        lines.append(
            f"Over {facts.put(str(card['samples']))} runs with prices, costs and the reservoir "
            "drawn across their ranges"
            # Drawn one by one (``workbench.sensitivity``): gas and electricity prices, or the
            # capital costs, never move together here, which may make the range too narrow.
            + (
                ", each most likely at the design's own value and drawn independently of the "
                "others"
                if centred
                else ", each independently of the others"
            )
            + " (no correlation between them)"
            + f", {card['design']}'s cost of heat and cold is "
            f"{facts.put(num(lc['p10']))} to {facts.put(num(lc['p90']))} €/MWh (P10 to P90; "
            f"median {facts.put(num(lc['p50']))})."
        )
        at = (card.get("base_percentile") or {}).get("lcoe")
        own = (card.get("base") or {}).get("lcoe")
        if at is not None and own is not None:
            where = round(float(at) * 100)
            side = (
                "the ranges reach further on the dear side than the cheap side, so more runs "
                "cost more than the case"
                if lc["p50"] > own + 1e-9 and where < 45
                else (
                    "the ranges reach further on the cheap side, so more runs cost less than "
                    "the case"
                    if lc["p50"] < own - 1e-9 and where > 55
                    else "it sits near the middle of the runs"
                )
            )
            lines.append(
                f"The design's own case, {facts.put(num(own))} €/MWh, is at "
                f"P{facts.put(str(where))} of the runs: {side}."
            )
    if npv:
        lines.append(
            f"Its NPV against gas is {facts.put(num(npv['p10']))} to "
            f"{facts.put(num(npv['p90']))} M€ (median {facts.put(num(npv['p50']))}); it beats gas "
            f"in {facts.put(reporter.pct(npv['above_zero']))} of the runs."
        )
    top = card.get("tornado") or []
    if top:
        bits = [
            f"{_swing(t, facts)} gives a cost of heat and cold of "
            f"{facts.put(num(t['lcoe_low']))} to {facts.put(num(t['lcoe_high']))} €/MWh"
            for t in top[:3]
        ]
        lines.append("What moves the cost most: " + "; ".join(bits) + ".")
    card["verdict"] = lines[0] if lines else ""
    return " ".join(lines)


# ------------------------------------------------------------------ failures over a year

log = logging.getLogger(__name__)
_COSTS: Dict[tuple, Dict[str, object]] = {}  # failure costs per design and conditions
_COSTS_MAX = 64
VIEW_UNIT_KEYS = (
    "unit",
    "label",
    "words",
    "failures_per_year",
    "repair_days",
    "out_days",
    "running_keur",
    "grid_keur",
    "grid_break_share",
    "lost_mwh",
    "lost_keur",
    "repair_keur",
    "total_keur",
)
VIEW_SPARE_KEYS = (
    "per_year",
    "swap_days",
    "no_spare_days",
    "price_meur",
    "life_years",
    "yearly_keur",
    "saving_keur",
    "saving_mwh",
    "net_keur",
    "worth",
    "break_even_per_year",
    "stress_net_keur",
    "range",
)


def entry_prices(entry: LedgerEntry) -> dp.Prices:
    """Return the prices a design was priced at (its economics' assumptions)."""
    known = {f.name for f in fields(dp.Prices)}
    got = {
        k: a["value"]
        for k, a in (getattr(entry.economics, "assumptions", None) or {}).items()
        if k in known and isinstance(a, dict) and a.get("value") is not None
    }
    return replace(dp.Prices(), **got) if got else engine.prices_for(None, entry.brief)


def failure_costs(
    entry: LedgerEntry,
    assumptions: Optional[dict] = None,
    lost_eur_per_mwh: float = fcost.LOST_EUR_PER_MWH,
    base: Optional[dp.YearResult] = None,
) -> Dict[str, object]:
    """Return what failures cost a design a year on average, and what a spare ESP is worth.

    What the chat answers "what do failures cost?" or "is a spare ESP worth it?" from: each
    unit's failures a year and repair time (``dioscuri_plant.failure_costs.RATES``), the year
    run with it out, averaged over every start day. Computed once per design and conditions.

    Parameters
    ----------
    entry : LedgerEntry
        The design.
    assumptions : dict, optional
        The conversation's prices; the design's own when not given.
    lost_eur_per_mwh : float
        What a MWh of heat or cold not delivered is worth (default: the lost sale, a floor).
    base : YearResult, optional
        The design's normal year, when already run.

    Returns
    -------
    dict
        ``dioscuri_plant.failure_costs.failure_costs``, with ``design`` and ``code``.
    """
    plant = engine.plant_of(entry.alternative)
    rules = engine.rules_for(entry.brief)
    demand = engine.demand_of(entry.brief)
    prices = engine.prices_for(assumptions, entry.brief) if assumptions else entry_prices(entry)
    key = (
        repr(plant),
        repr(rules),
        repr(prices),
        hash((demand.heat_mw, demand.cool_mw)),
        float(lost_eur_per_mwh),
    )
    if key not in _COSTS:
        if len(_COSTS) >= _COSTS_MAX:
            _COSTS.pop(next(iter(_COSTS)))
        _COSTS[key] = fcost.failure_costs(
            plant,
            demand,
            doublet_model(rules),
            rules,
            prices=prices,
            lost_eur_per_mwh=lost_eur_per_mwh,
            base=base,
        )
    return {**_COSTS[key], "design": reporter.design_id(entry), "code": entry.alternative.code}


def yearly_view(costs: Optional[Dict[str, object]]) -> Optional[Dict[str, object]]:
    """Return failures over a year as the failure card shows them (None when not run)."""
    if not costs:
        return None
    esp = costs.get("spare_esp")
    spare = None
    if esp:
        be = esp["break_even_per_year"]
        spare = {k: esp[k] for k in VIEW_SPARE_KEYS}
        spare["every"] = _every(esp["per_year"], reporter.Facts())  # "once every 2 years"
        spare["break_even_every"] = _every(be, reporter.Facts()) if be else None
    return {
        "total_keur": costs["total_keur"],
        "range_keur": costs["range_keur"],
        "lost_mwh": costs["lost_mwh"],
        "lost_heat_mwh": costs["lost_heat_mwh"],
        "lost_cold_mwh": costs["lost_cold_mwh"],
        "lost_eur_per_mwh": costs["lost_eur_per_mwh"],
        "stress_keur": costs["stress_keur"],
        "stress_eur_per_mwh": costs["stress_eur_per_mwh"],
        "with_spare_keur": costs["with_spare"]["total_keur"],
        "with_spare_mwh": costs["with_spare"]["lost_mwh"],
        "grid_keur": costs.get("grid_keur", 0.0),
        "with_spare_grid_keur": costs["with_spare"].get("grid_keur", 0.0),
        "grid": costs.get("grid"),
        "units": [{k: u.get(k, 0.0) for k in VIEW_UNIT_KEYS} for u in costs["units"]],
        "spare_esp": spare,
        "skipped": list(costs["skipped"]),
        "notes": list(costs["notes"]),
    }


def _yearly_safe(
    entry: LedgerEntry, assumptions: Optional[dict] = None, base: Optional[dp.YearResult] = None
) -> Optional[Dict[str, object]]:
    try:
        return yearly_view(failure_costs(entry, assumptions, base=base))
    except Exception:  # the average cost never stops a failure answer or a design's context
        log.exception("failure costs of %s", entry.alternative.code)
        return None


def _every(rate: float, facts: reporter.Facts) -> str:
    """Return a failure rate in words: "once every 2 years", "once a year", "3 times a year"."""
    if rate <= 0:
        return "never"
    if rate >= 1.5:
        return f"{facts.put(reporter.num(rate, 1))} times a year"
    years = 1.0 / rate
    if round(years) <= 1:
        return "once a year"
    return f"once every {facts.put(reporter.num(years, 0))} years"


def failure_costs_text(view: Optional[Dict[str, object]], facts: reporter.Facts) -> str:
    """Return failures over a year in words, every number from ``yearly_view``.

    The expected cost a year (without a spare ESP, as designed), the unit that costs most,
    the heat and cold not delivered and its value, and whether a spare ESP pays.
    """
    if not view:
        return ""
    num = reporter.num
    spare = view.get("spare_esp")
    units = [u for u in view["units"] if u["total_keur"] >= 0.5]
    if not units:
        return (
            f"On average over a year, failures cost about {facts.put(num(view['total_keur']))} k€."
        )
    top = units[0]
    basis = " without a spare ESP" if spare else ""
    how = ""
    if str(top["unit"]).startswith("doublet "):
        how = (
            f", failing {_every(top['failures_per_year'], facts)}"
            f" and out {facts.put(num(top['repair_days'], 0))} days each time"
        )
    text = (
        f"On average over a year, failures cost about {facts.put(num(view['total_keur'], 0))} k€"
        f"{basis} ({top['words']} most: {facts.put(num(top['total_keur'], 0))} k€{how})"
    )
    grid = float(view.get("grid_keur") or 0.0)
    if grid >= 0.5:
        share = float(top.get("grid_break_share") or 0.0)
        text += (
            f", of which {facts.put(num(grid, 0))} k€ is the electric boiler's grid charge: an "
            "outage that pushes it past 600 hours a year loses the grid's 600-hour contract for "
            "the whole year"
            + (
                f" ({facts.put(reporter.pct(share))} of {top['words']}'s outages do)"
                if share > 0
                else ""
            )
        )
    if view["lost_mwh"] >= 0.5:
        text += (
            f"; {facts.put(num(view['lost_mwh'], 0))} MWh of heat and cold is not delivered a "
            f"year, valued at {facts.put(num(view['lost_eur_per_mwh'], 0))} €/MWh (the lost "
            f"sale, a floor; at {facts.put(num(view['stress_eur_per_mwh'], 0))} €/MWh failures "
            f"would cost {facts.put(num(view['stress_keur'], 0))} k€ a year)"
        )
    text += "."
    if spare:
        cost = (
            f"{facts.put(num(spare['yearly_keur'], 0))} k€ a year of capital "
            f"({facts.put(num(spare['price_meur'], 2))} M€)"
        )
        be = spare["break_even_per_year"]
        pays = (
            f"it pays as long as an ESP fails more often than {_every(be, facts)}"
            if be
            else "it never pays here: a doublet out costs nothing extra"
        )
        if spare["worth"]:
            text += (
                f" A spare ESP on the shelf is worth about {facts.put(num(spare['net_keur'], 0))}"
                f" k€ a year: the doublet is back in {facts.put(num(spare['swap_days'], 0))} days "
                f"instead of {facts.put(num(spare['no_spare_days'], 0))}, which saves "
                f"{facts.put(num(spare['saving_keur'], 0))} k€ a year for {cost}; with it "
                f"failures cost about {facts.put(num(view['with_spare_keur'], 0))} k€ a year. "
                f"{pays[0].upper()}{pays[1:]}."
            )
        else:
            text += (
                f" A spare ESP is not worth it at {_every(spare['per_year'], facts)}: it saves "
                f"{facts.put(num(spare['saving_keur'], 0))} k€ a year for {cost}; {pays}."
            )
    return text


def failure_costs_note(entry: LedgerEntry) -> Optional[str]:
    """Return failures over a year as one line of a design's context (``answer.design_notes``)."""
    view = _yearly_safe(entry)
    if not view:
        return None
    lo, hi = view["range_keur"]
    return (
        "Failures over a year (expected, averaged over every start day; failure rates and "
        "repair times from US Army TM 5-698-5 for the boiler, chillers, heat pump and heat "
        "exchanger, and Dutch ESP run lives of 1-2 years): "
        + failure_costs_text(view, reporter.Facts())
        + f" Over the failure rates' ranges: {reporter.num(lo, 0)} to {reporter.num(hi, 0)} k€ a "
        "year."
    )
