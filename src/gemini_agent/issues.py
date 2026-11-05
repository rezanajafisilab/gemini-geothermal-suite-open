"""What goes wrong in a design's year, part by part: the Design tab's alerts (5 Nov).

Each issue names the parts of the drawing it concerns by their node ids (``workbench.graph_view``:
``producer_1``, ``hex``, ``heat_pump``, ``boiler``, ``chillers``, ``demand_heat`` ...), the main
one first, so the canvas can mark them and list the issue beside the drawing. Three kinds:

- demand not met (``heat_short``, ``cool_short``): the days heat or cold is short in the plant
  model's year, grouped by what caused them on each day. A unit out for its planned service, or a
  doublet in its planned stop, is the cause when one is out that day; otherwise the plant gave
  all it could and the cause is its top-up unit (the last one the dispatch calls on). The units
  that ran flat out on those days are listed as at their limit.
- a failure asked about in the chat on this design (``failure``; ``reliability.run_failure``, kept
  in ``session.failures``): the unit out on its days, and whether the rest of the plant covered it.
- a broken cap that is not a shortfall (``cap``): a doublet's brine cooled past the cap on some
  days, a doublet run more days than the cap allows, or its flow outside the range.

``critical`` when demand goes unmet (red on the canvas), ``warning`` otherwise (amber).
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from gemini_agent import engine, reporter
from gemini_agent.contract import LedgerEntry
from gemini_agent.stops import MONTH_DAYS, day_name, ranges_of

SHORT_MW = 0.01  # a day counts as short above this (as ``workbench.broken_days``)
FULL = 0.98  # a unit at or above this share of what it can give that day is at its limit
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December",
)  # fmt: skip
SIDES = {
    "heat": ("Heat", "demand_heat"),
    "cool": ("Cooling", "demand_cold"),
}
# A plant outage unit (``dioscuri_plant.types.OUTAGE_UNITS`` and "doublet 1" ...) -> its node id.
UNIT_NODES = {
    "heat exchanger": "hex",
    "heat pump": "heat_pump",
    "boiler": "boiler",
    "boiler unit": "boiler",
    "electric boiler": "electric_boiler",
    "electric boiler unit": "electric_boiler",
    "chillers": "chillers",
    "chiller unit": "chillers",
    "absorption": "absorption",
}
HEAT_UNITS = ("heat exchanger", "heat pump", "boiler", "boiler unit", "electric boiler")
HEAT_UNITS += ("electric boiler unit",)
COOL_UNITS = ("chillers", "chiller unit", "absorption")
# The units the dispatch calls on in turn, side by side: the last one is the top-up.
MERIT = {
    "heat": ("hex", "heat_pump", "boiler", "electric_boiler"),
    "cool": ("absorption", "chillers"),
}
SERVICE_WORDS = {
    "heat exchanger": "the heat exchanger",
    "heat pump": "the heat pump",
    "boiler": "the boiler",
    "boiler unit": "one boiler unit",
    "electric boiler": "the electric boiler",
    "electric boiler unit": "one electric boiler unit",
    "chillers": "the chillers",
    "chiller unit": "one chiller unit",
    "absorption": "the absorption chiller",
}


def month_of(day: int) -> int:
    """Return the month (0-11) of a 0-based day of 2027."""
    m, i = 0, int(day)
    while m < 11 and i >= MONTH_DAYS[m]:
        i -= MONTH_DAYS[m]
        m += 1
    return m


def runs(days: Iterable[int]) -> List[Tuple[int, int]]:
    """Return days as sorted (first, last) runs of consecutive days."""
    out: List[List[int]] = []
    for d in sorted(set(int(x) for x in days)):
        if out and d == out[-1][1] + 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [(a, b) for a, b in out]


def when_words(days: Sequence[int]) -> str:
    """Return when days fall in words: "28 Jan", "26–29 Jan", "30 Jan – 2 Feb, 9 Feb".

    More than three runs: "5 periods, 3 Jan – 20 Feb".
    """
    spans = runs(days)
    if not spans:
        return ""

    def one(a: int, b: int) -> str:
        if a == b:
            return day_name(a)
        if month_of(a) == month_of(b):
            return f"{day_name(a).split(' ')[0]}–{day_name(b)}"
        return f"{day_name(a)} – {day_name(b)}"

    if len(spans) > 3:
        return f"{len(spans)} periods, {day_name(spans[0][0])} – {day_name(spans[-1][1])}"
    return ", ".join(one(a, b) for a, b in spans)


def months_words(days: Sequence[int]) -> str:
    """Return the months the days fall in: "in January", "in January and February"."""
    months = sorted({month_of(d) for d in days})
    names = [MONTH_NAMES[m] for m in months]
    if not names:
        return ""
    if len(names) > 3:
        return f"over {len(names)} months"
    if len(names) == 1:
        return f"in {names[0]}"
    return "in " + ", ".join(names[:-1]) + " and " + names[-1]


def _mw(x: float) -> str:
    return reporter.num(x, 2 if abs(x) < 1 else 1)


def _days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def _join(words: Sequence[str]) -> str:
    words = list(words)
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


class Parts:
    """The drawing's parts of one design: node ids, labels, and each doublet's wells and train."""

    def __init__(self, graph: dict):
        """Index the graph's nodes and edges."""
        nodes = graph.get("nodes") or []
        self.ids = [n["id"] for n in nodes]
        self.labels = {n["id"]: n.get("label", n["id"]) for n in nodes}
        self.injectors: Dict[int, List[str]] = {}
        for n in nodes:
            if n.get("type") == "injector_well":
                k = int((n.get("values") or {}).get("doublet") or 0)
                self.injectors.setdefault(k, []).append(n["id"])
        # Each doublet's treatment train: the node its producer's brine goes to.
        self.train_of: Dict[int, str] = {}
        for e in graph.get("edges") or []:
            m = re.fullmatch(r"producer_(\d+)", str(e.get("source")))
            if m and str(e.get("target", "")).startswith("train_"):
                self.train_of[int(m.group(1))] = e["target"]

    def has(self, node: Optional[str]) -> bool:
        """Return True when the drawing has this part."""
        return node is not None and node in self.labels

    def label(self, node: str) -> str:
        """Return the label of a part: "Gas boiler", "Producer 1"."""
        return self.labels.get(node, node)

    def node_of(self, unit: str, trains: Sequence[int] = ()) -> Optional[str]:
        """Return the node of a plant outage unit ("doublet 1", "boiler unit"), or None.

        ``trains``: each doublet's treatment train number (``Plant.train_numbers``), to find the
        train "train 2" is; without them a train is found by its doublet of the same number.
        """
        unit = str(unit).strip().lower()
        if unit in UNIT_NODES:
            node = UNIT_NODES[unit]
            return node if self.has(node) else None
        kind, _, k = unit.rpartition(" ")
        if not k.isdigit():
            return None
        k_int = int(k)
        if kind == "doublet":
            node = f"producer_{k_int}"
        elif kind == "injector":
            node = (self.injectors.get(k_int) or [None])[0]
        elif kind == "train":
            members = [i + 1 for i, t in enumerate(trains) if t == k_int] or [k_int]
            node = next((self.train_of[i] for i in members if i in self.train_of), None)
        else:
            return None
        return node if self.has(node) else None


def _trains(entry: LedgerEntry) -> List[int]:
    """Return each doublet's treatment train number, 1, 2 ... in order of first use."""
    seen: Dict[int, int] = {}
    return [
        seen.setdefault(int(d.get("train") or 0), len(seen) + 1)
        for d in entry.alternative.doublets or []
    ]


def _issue(
    kind: str,
    severity: str,
    units: Sequence[str],
    parts: Parts,
    what: str,
    when: str,
    days: Sequence[int] = (),
    day: Optional[int] = None,
    why: str = "",
    limit: Sequence[str] = (),
    unit: str = "",
    **extra,
) -> dict:
    units = list(dict.fromkeys(u for u in units if parts.has(u)))
    limit = [u for u in dict.fromkeys(limit) if parts.has(u) and u not in units]
    out = {
        "id": "",
        "kind": kind,
        "severity": severity,
        "units": units,
        "limit": limit,
        "unit": unit or (parts.label(units[0]) if units else "The plant"),
        "what": what,
        "why": why,
        "when": when,
        "first": min(days) if days else None,
        "last": max(days) if days else None,
        "day": day if day is not None else (min(days) if days else None),
        "days": len(set(days)),
        "what_if": False,
    }
    out.update(extra)
    return out


# ------------------------------------------------------------------ demand not met


def _caps_by_day(entry: LedgerEntry) -> Dict[str, List[float]]:
    """Return what each surface unit can give each day, MW: its size, less a unit out."""
    y, alt = entry.year, entry.alternative
    sizes = alt.sizes_mw or {}
    service = [(str(u), int(a), int(b)) for u, a, b in (y.service or [])]

    def cap(size: float, whole: str, one: str = "", units: int = 1) -> List[float]:
        out = []
        for d in range(365):
            share = 1.0
            for u, a, b in service:
                if a <= d <= b and u == whole:
                    share = 0.0
                elif a <= d <= b and one and u == one and units > 1:
                    share = min(share, 1 - 1 / units)
            out.append(size * share)
        return out

    return {
        "hex": cap(sizes.get("heat_exchanger", y.hex_mw or 0.0), "heat exchanger"),
        "heat_pump": cap(sizes.get("heat_pump", y.heat_pump_mw or 0.0), "heat pump"),
        "boiler": cap(sizes.get("boiler", 0.0), "boiler", "boiler unit", alt.boiler_units),
        "electric_boiler": cap(
            sizes.get("electric_boiler", 0.0),
            "electric boiler",
            "electric boiler unit",
            alt.electric_boiler_units,
        ),
        "chillers": cap(sizes.get("chillers", 0.0), "chillers", "chiller unit", alt.chiller_units),
        "absorption": cap(sizes.get("absorption", 0.0), "absorption"),
    }


# The daily series of each unit, side by side (``YearResult.daily_mw``).
SERIES = {
    "heat": {
        "hex": "geo",
        "heat_pump": "hp",
        "boiler": "boiler",
        "electric_boiler": "electric_boiler",
    },
    "cool": {"absorption": "abs", "chillers": "chill"},
}


def _at_limit(entry: LedgerEntry, side: str, day: int, caps: Dict[str, List[float]]) -> List[str]:
    """Return the units of a side that give all they can on a day (node ids)."""
    y = entry.year
    daily = (y.daily_mw or {}).get(side) or {}
    out = []
    for node, key in SERIES[side].items():
        values = daily.get(key) or []
        can = caps[node][day] if node in caps else 0.0
        if can > 0 and day < len(values) and values[day] >= FULL * can:
            out.append(node)
    if side == "heat" or (y.absorption_mw or 0) > 0:
        rows = (y.plant or {}).get("doublets") or []
        for k, d in enumerate(y.doublets or []):
            flow = d.get("flow_m3h") or []
            top = float((rows[k] if k < len(rows) else {}).get("cap_m3h") or 0.0)
            if top > 0 and day < len(flow) and flow[day] >= FULL * top:
                out.append(f"producer_{k + 1}")
    return out


def _out_on(entry: LedgerEntry, side: str, day: int, parts: Parts) -> List[Tuple[str, str]]:
    """Return the units out on a day that feed a side: (node id, why in words)."""
    y = entry.year
    out: List[Tuple[str, str]] = []
    feeds = HEAT_UNITS if side == "heat" else COOL_UNITS
    for u, a, b in y.service or []:
        if int(a) <= day <= int(b) and str(u) in feeds:
            node = parts.node_of(str(u))
            if node:
                words = SERVICE_WORDS.get(str(u), str(u))
                out.append((node, f"{words[0].upper()}{words[1:]} is out for its planned service"))
    if side == "heat" or (y.absorption_mw or 0) > 0:
        stops = ranges_of(y)
        for k, d in enumerate(y.doublets or []):
            on = d.get("on") or []
            if day < len(on) and not on[day]:
                planned = k < len(stops) and any(a <= day <= b for a, b in stops[k])
                out.append(
                    (
                        f"producer_{k + 1}",
                        (
                            f"Doublet {k + 1} is in its planned stop"
                            if planned
                            else f"Doublet {k + 1} is off"
                        ),
                    )
                )
    return [(n, w) for n, w in out if parts.has(n)]


def _top_up(side: str, parts: Parts, limit: Sequence[str]) -> Optional[str]:
    """Return the unit a shortfall from too little capacity falls on: the last one called on."""
    order = [u for u in MERIT[side] if parts.has(u)]
    at = [u for u in order if u in limit]
    if at:
        return at[-1]
    return order[-1] if order else None


def shortfalls(entry: LedgerEntry, parts: Parts) -> List[dict]:
    """Return the days heat or cold is short, one issue per side and cause.

    Each day's cause: the units out that day (planned service, a doublet's planned stop), or,
    with none out, too little capacity (the top-up unit). ``limit`` lists the units at their
    limit on any of the issue's days.
    """
    y = entry.year
    daily = y.daily_mw or {}
    caps = None
    out: List[dict] = []
    for side, (word, demand_node) in SIDES.items():
        short = list((daily.get(side) or {}).get("short") or [])
        days = [i for i, v in enumerate(short) if v > SHORT_MW]
        if not days:
            continue
        caps = caps or _caps_by_day(entry)
        groups: Dict[tuple, dict] = {}
        for d in days:
            out_units = _out_on(entry, side, d, parts)
            limit = _at_limit(entry, side, d, caps)
            key = tuple(n for n, _ in out_units) or ("capacity",)
            g = groups.setdefault(key, {"days": [], "limit": [], "why": []})
            g["days"].append(d)
            g["limit"] += limit
            g["why"] += [w for _, w in out_units]
        for key, g in groups.items():
            gdays = g["days"]
            worst_day = max(gdays, key=lambda i: short[i])
            worst = short[worst_day]
            limit = list(dict.fromkeys(g["limit"]))
            if key == ("capacity",):
                main = _top_up(side, parts, limit)
                units = [main] if main else []
                at = [parts.label(u).lower() for u in limit if parts.has(u)]
                why = "Not enough capacity" + (
                    f": {_join(at)} {'runs' if len(at) == 1 else 'run'} flat out" if at else ""
                )
                cause = "capacity"
            else:
                units = list(key)
                why = "; ".join(dict.fromkeys(g["why"]))
                cause = "out"
            n = len(gdays)
            what = (
                f"{word} short on {_days(n)} {months_words(gdays)}, up to {_mw(worst)} MW"
            ).replace("  ", " ")
            out.append(
                _issue(
                    f"{side}_short",
                    "critical",
                    units + [demand_node],
                    parts,
                    what,
                    when_words(gdays),
                    gdays,
                    day=worst_day,
                    why=why,
                    limit=limit,
                    worst_mw=round(float(worst), 2),
                    cause=cause,
                )
            )
    return out


# ------------------------------------------------------------------ failures asked about


def _short_in(failed: dict, side: str, window: Sequence[int]) -> Tuple[int, float, Optional[int]]:
    """Return a failure's days short on one side inside its window, the worst MW and its day.

    The failed year's own count covers the whole year (a design short on other days too would
    add them): the window's days (``failed["days"]``, up to 31) are counted when they are all
    there; a longer window takes the year's count.
    """
    key = "heat_short_mw" if side == "heat" else "cool_short_mw"
    rows = failed.get("days")
    if rows is not None and len(window) <= 31:
        names = {day_name(d): d for d in window}
        short = [
            (names[x["day"]], float(x.get(key) or 0.0))
            for x in rows
            if x.get("day") in names and float(x.get(key) or 0.0) > 1e-3
        ]
        if not short:
            return 0, 0.0, None
        at, worst = max(short, key=lambda t: t[1])
        return len(short), worst, at
    s = failed.get(side) or {}
    index = s.get("worst_index")
    return (
        int(s.get("days_short") or 0),
        float(s.get("worst_mw") or 0.0),
        int(index) if index is not None else None,
    )


def failures(entry: LedgerEntry, results: Sequence[dict], parts: Parts) -> List[dict]:
    """Return the failure what-ifs run on this design (``reliability.run_failure`` results).

    The latest of each set of failures; ``critical`` when demand went unmet, ``warning`` when the
    rest of the plant covered it.
    """
    from gemini_agent.reliability import unit_words

    did = reporter.design_id(entry)
    trains = _trains(entry)
    latest: Dict[tuple, dict] = {}
    for r in results or []:
        if not isinstance(r, dict) or r.get("design") != did:
            continue
        events = r.get("events") or []
        key = tuple((e.get("unit"), e.get("first"), e.get("last")) for e in events)
        if key:
            latest.pop(key, None)
            latest[key] = r
    out = []
    for r in latest.values():
        events = r["events"]
        failed = r.get("failed") or {}
        nodes = [parts.node_of(str(e.get("unit")), trains) for e in events]
        units = [n for n in nodes if n]
        days = sorted({d for e in events for d in range(int(e["first"]), int(e["last"]) + 1)})
        said = []
        worst_day = None
        worst_mw = 0.0
        for side, (word, demand_node) in SIDES.items():
            n, worst, at = _short_in(failed, side, days)
            if n:
                said.append(f"{word.lower()} short on {_days(n)}, up to {_mw(worst)} MW")
                units.append(demand_node)
                if worst > worst_mw and at is not None:
                    worst_mw, worst_day = worst, at
        names = _join([unit_words(str(e.get("unit"))) for e in events])
        out_words = f"{names[0].upper()}{names[1:]} out" if names else "A unit out"
        if said:
            what = f"{out_words}: {'; '.join(said)}"
        else:
            gas = float(failed.get("extra_gas_gwh") or 0.0)
            what = f"{out_words}: the rest of the plant covers it" + (
                f", with {reporter.num(gas, 1)} GWh more gas" if gas >= 0.05 else ""
            )
        limit = ["boiler"] if failed.get("boiler_full") else []
        out.append(
            _issue(
                "failure",
                "critical" if said else "warning",
                units,
                parts,
                what[0].upper() + what[1:],
                when_words(days),
                days,
                day=worst_day,
                why="A what-if from the chat: the drawing shows the design without it",
                limit=limit,
                unit=parts.label(units[0]) if units else "The plant",
                what_if=True,
                asked=str(r.get("message") or "")[:160],
            )
        )
    return out


# ------------------------------------------------------------------ caps broken


def caps_broken(entry: LedgerEntry, parts: Parts) -> List[dict]:
    """Return the broken caps that are not a shortfall: the brine, the days run, the flow."""
    y = entry.year
    out = []
    limit = engine.rules_for(entry.brief).max_brine_cooling_k
    for k, d in enumerate(y.doublets or []):
        wh, rj = d.get("wellhead_c") or [], d.get("reinjection_c") or []
        days = [
            i
            for i, (a, b) in enumerate(zip(wh, rj))
            if a is not None and b is not None and a - b > limit + 0.05
        ]
        if days:
            worst = max(days, key=lambda i: wh[i] - rj[i])
            units = parts.injectors.get(k + 1) or [f"producer_{k + 1}"]
            most = reporter.num(wh[worst] - rj[worst], 1)
            out.append(
                _issue(
                    "cap",
                    "warning",
                    units,
                    parts,
                    f"Brine of doublet {k + 1} cooled by up to {most} K on {_days(len(days))} "
                    f"{months_words(days)}",
                    when_words(days),
                    days,
                    day=worst,
                    why=f"The challenge caps it at {reporter.num(limit, 0)} K",
                )
            )
    for v in y.violations or []:
        text = str(v).strip()
        if re.match(r"(Heat|Cooling) short|Brine of doublet", text):
            continue  # the shortfalls and the brine are above, with their days
        m = re.match(r"Doublet (\d+)(?::| )\s*(.*)", text)
        node = f"producer_{m.group(1)}" if m else None
        what = text.rstrip(".")
        if m:
            what = m.group(2).rstrip(".")
            what = what[0].upper() + what[1:] if what else text
        out.append(
            _issue(
                "cap",
                "warning",
                [node] if node else [],
                parts,
                what,
                "over the year",
                why="A cap of the challenge",
            )
        )
    return out


# ------------------------------------------------------------------ all of them


def design_issues(
    entry: LedgerEntry, graph: dict, failure_results: Optional[Sequence[dict]] = None
) -> List[dict]:
    """Return a design's issues, the worst first: each with the drawing's parts it concerns.

    Parameters
    ----------
    entry : LedgerEntry
        The design, with its year.
    graph : dict
        Its drawing (``workbench.graph_view``): the node ids the issues name.
    failure_results : sequence of dict, optional
        The chat's failure what-ifs (``session.failures``); those run on this design are kept.

    Returns
    -------
    list of dict
        ``id``, ``kind`` (heat_short, cool_short, failure, cap), ``severity`` (critical,
        warning), ``units`` (node ids, the main one first), ``limit`` (node ids at their limit),
        ``unit`` (the main part in words), ``what``, ``why``, ``when`` (words), ``first``,
        ``last`` and ``day`` (0-based days of 2027, the worst for ``day``; None for a whole
        year), ``days`` (how many), ``what_if``.
    """
    parts = Parts(graph)
    out = shortfalls(entry, parts) + failures(entry, failure_results or [], parts)
    out += caps_broken(entry, parts)
    rank = {"critical": 0, "warning": 1}
    out.sort(
        key=lambda i: (
            rank.get(i["severity"], 2),
            i["what_if"],
            i["first"] if i["first"] is not None else 999,
        )
    )
    for k, i in enumerate(out):
        i["id"] = f"{i['kind']}-{k + 1}"
    return out
