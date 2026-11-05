"""Where a number comes from: the derivation of a design's figure, from the design itself.

"Where does the 30 MW come from?" (1 Nov) got "I couldn't confirm an answer" or a circular "three
10 MW units": the context held the size, not how it was found. This module finds which of the
design's figures a number is (a unit's size, a cost, a temperature, the CO2 saving) and says how
it was worked out, with the numbers that set it: the boiler's size by the one-unit-out sizing,
the heat pump's by the sizing sweep, the exchanger's by the brine flow, the costs by their lines.
A number it cannot place is looked up in the design's notes, and the sentences holding it are
given as they are.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from gemini_agent.intake import numbers_in

# A question about where a figure comes from (any wording that asks for its origin or its working).
ASKS_ORIGIN = re.compile(
    r"where (does|do|did|is|are) .{0,120}\b(come from|from)\b|"
    r"\bhow\b.{0,40}\b(calculat|comput|work(ed)? out|deriv|get|got|arriv|size[sd]?\b|"
    r"find|found|obtain|come up with)|"
    r"(what|which) is .{0,40} based on|\bbased on what\b|why (is|was|are) .{0,60}\d|"
    r"^\W*(why|how come|waarom|warum|wieso|pourquoi)\b[^?.]{0,40}\d|"
    r"\b(waar komt|woher kommt|d'o[ùu] vient)\b|"
    r"origin of|source of the|breakdown of|\bbreak\b.{0,30}\bdown\b|\bmade up of\b|"
    r"\bmakes? up\b|\bconsists? of\b",
    re.I,
)


def _rounded(x: float, y: float) -> bool:
    """Return True when ``x`` is ``y`` rounded to a whole number ("36 M€" for 36.2 M€)."""
    return float(x).is_integer() and abs(y) >= 10 and round(y) == x


def _close(x: float, y: float) -> bool:
    return abs(x - y) <= max(0.051, 0.005 * abs(y))


# A number written with its unit ("30 MW", "30.4 €/MWh"): which of the design's figures it is
# when two match (4 Nov: the boilers' 30 MW and the cost of cold's 30.4 €/MWh).
WITH_UNIT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(€\s*/\s*MWh|EUR\s*/\s*MWh|M€|MW(?!h)|°C|%)", re.I)


def _units(message: str) -> dict:
    """Return {number: unit} for the numbers the message writes with a unit."""
    out = {}
    for n, unit in WITH_UNIT.findall(message):
        out[float(n.replace(",", ""))] = "€/MWh" if "mwh" in unit.lower() else unit.upper()
    return out


def _num(x: float, digits: int = 1) -> str:
    from gemini_agent.reporter import num

    return num(x, digits)


def _peak(entry) -> Tuple[float, str]:
    """Return the heat demand's peak (MW) and its day ("28 Jan")."""
    from gemini_agent import stops

    d = (entry.year.daily_mw or {}).get("heat") or {}
    demand = list(d.get("demand") or [])
    if not demand:
        return entry.year.peak_heat_mw, ""
    i = max(range(len(demand)), key=lambda k: demand[k])
    return float(demand[i]), stops.day_name(i)


def _most(entry, side: str, key: str) -> Tuple[float, str]:
    """Return a unit's largest daily output over the year (MW) and its day."""
    from gemini_agent import stops

    v = list(((entry.year.daily_mw or {}).get(side) or {}).get(key) or [])
    if not v:
        return 0.0, ""
    i = max(range(len(v)), key=lambda k: v[k])
    return float(v[i]), stops.day_name(i)


def _bank(
    entry, unit: str, size: float, units: int, side: str, key: str, demand: str
) -> Tuple[str, List[str]]:
    """Explain a boiler's or chillers' size: the N-1 case that sets it, then a normal year.

    The case that sets the size leads: for one doublet's boilers, the doublet out (its
    exchanger and heat pump then give nothing, so the boilers carry the peak alone).
    """
    a = entry.alternative
    most, day = _most(entry, side, key)
    normal = (
        f"In a normal year the {unit} gives at most {_num(most, 2)} MW ({day})." if most else ""
    )
    out, must = [], []
    if a.reliable and units > 1:
        each = size / units
        peak, pday = _peak(entry)
        if side == "heat" and a.n_doublets == 1 and size >= peak - 0.5:
            hp = " and the heat pump (its heat comes from the brine)" if a.heat_pump else ""
            out.append(
                f"The size is set by the N-1 rule (the plant must meet every day with any one "
                f"unit out), in its hardest case: with the only doublet out, the exchanger{hp} "
                f"give nothing, so the boilers must cover the {_num(peak)} MW peak ({pday}) by "
                f"themselves. That is {_num(size)} MW, built as {units} units of {_num(each)} MW."
            )
            must.append("doublet out")
        else:
            out.append(
                f"The size is set by the N-1 rule: the units were grown until every day is met "
                f"with any one unit of the plant out (a {unit} unit or a doublet). That gives "
                f"{_num(size)} MW, built as {units} units of {_num(each)} MW."
            )
        if normal:
            out.append(normal.replace("In a normal year", "In a normal year, with nothing out,"))
            if size - most > 0.5:
                must.append(_either(most))
        out.append(
            f"With one {unit} unit out, the other {units - 1} give {_num(size - each)} MW, which "
            f"with the rest of the plant still meets {demand}."
        )
    elif size:
        out.append(
            f"It covers what the doublets and the other units do not, so its size follows the "
            f"largest gap of the year: {_num(size)} MW."
        )
        if normal:
            out.append(normal)
            must.append(_either(most))
    return " ".join(out), must


def _either(x: float) -> str:
    """Return a value the reply must give, as written or rounded ("~19.47 19.5")."""
    return "~" + " ".join(dict.fromkeys((_num(x, 2), _num(x, 1), _num(x, 0))))


def _day_of(series: Sequence[Optional[float]], pick=min) -> Optional[int]:
    """Return the day (0-based) of a daily series' lowest (or highest) value, skipping gaps."""
    days = [i for i, v in enumerate(series or []) if v is not None]
    return pick(days, key=lambda i: series[i]) if days else None


def _brine_temps(entry, key: str) -> Tuple[str, List[str]]:
    """Explain the rock's, the wellhead's or the reinjection temperature from the year."""
    from gemini_agent import engine, stops

    y, a = entry.year, entry.alternative
    rules = engine.rules_for(entry.brief)
    rock = rules.reservoir_temperature_c(a.depth_m)
    out = [
        f"The rock at {_num(a.depth_m, 0)} m is {_num(rock)} °C (the surface's "
        f"{_num(rules.surface_temperature_c)} °C plus {_num(rules.gradient_c_per_km)} °C/km)."
    ]
    must = [_either(rock)]
    if key == "reservoir_temp":
        working = (rules.surface_temperature_c, rules.gradient_c_per_km)
        return out[0], ["~" + " ".join(_num(x) for x in working)]
    out.append(
        f"The brine reaches the wellhead at {_num(y.wellhead_c)} °C at full flow: it loses "
        "heat on its way up the well (Ramey's model), more when it flows slowly."
    )
    if key == "wellhead_temp":
        return " ".join(out), must
    rows = [d for d in (y.doublets or []) if d.get("reinjection_c")]
    cap = rules.max_brine_cooling_k  # the cap (the year's own field is the most it cooled)
    best = None
    for i, d in enumerate(rows):
        k = _day_of(d["reinjection_c"])
        if k is not None and (best is None or d["reinjection_c"][k] < best[2]):
            best = (i, k, d["reinjection_c"][k])
    if best is None:
        out.append(f"It goes back at {_num(y.reinjection_c)} °C at the coldest.")
        return " ".join(out), must
    i, k, cold = best
    d = rows[i]
    top = (d.get("wellhead_c") or [None] * 365)[k] or y.wellhead_c
    flow = (d.get("flow_m3h") or [0.0] * 365)[k]
    which = f"doublet {i + 1}" if len(rows) > 1 else "the doublet"
    out = out[:1] + [
        f"{_num(cold)} °C is the coldest the brine goes back in the year, on {stops.day_name(k)}: "
        f"that day {which} brings up {_num(flow, 0)} m3/h at {_num(top)} °C, and "
        + (
            "the exchanger and then the heat pump cool"
            if (a.sizes_mw or {}).get("heat_pump", 0) > 0
            else "the exchanger cools"
        )
        + f" it by {_num(top - cold)} K."
    ]
    must = [_either(top), _either(top - cold)]
    hp_size = (a.sizes_mw or {}).get("heat_pump", 0.0)
    hp_day = (((y.daily_mw or {}).get("heat") or {}).get("hp") or [0.0] * 365)[k]
    floor = top - cap
    if abs(cold - floor) <= 0.3:
        out.append(f"That is the cap: the brine may be cooled by at most {_num(cap)} K.")
    elif hp_size and hp_day >= 0.98 * hp_size:
        out.append(
            f"The heat pump runs at its full {_num(hp_size)} MW that day, so its size sets how "
            f"cold the brine goes back, not the {_num(cap)} K cap (which would allow "
            f"{_num(floor)} °C)."
        )
    elif hp_size:
        top_flow = max((max(r.get("flow_m3h") or [0.0]) for r in rows), default=0.0)
        slow = (
            f" The flow is low that day ({_num(flow, 0)} m3/h against up to "
            f"{_num(top_flow, 0)}), so the heat taken from it cools each m3 more."
            if top_flow and flow < 0.6 * top_flow
            else ""
        )
        out.append(
            f"The heat pump gives {_num(hp_day)} MW that day, all the heat asked of it.{slow} "
            f"The {_num(cap)} K cap would allow {_num(floor)} °C."
        )
        if slow:
            must.append(_either(flow))
    else:
        out.append(
            f"Only the exchanger cools it: it heats the network's {_num(rules.heat_return_c)} °C "
            f"return, so the brine cannot leave much colder than that; the {_num(cap)} K cap "
            f"would allow {_num(floor)} °C."
        )
    return " ".join(out), must


def _hex(entry) -> Tuple[str, List[str]]:
    """Explain the exchanger's size: the most heat it passes in a day of the year."""
    from gemini_agent import engine, stops

    y = entry.year
    rules = engine.rules_for(entry.brief)
    geo = list(((y.daily_mw or {}).get("heat") or {}).get("geo") or [])
    k = _day_of(geo, max)
    if k is None:
        return "", []
    flow = sum(((d.get("flow_m3h") or [0.0] * 365)[k] or 0.0) for d in (y.doublets or []))
    return (
        f"The exchanger is sized for the most heat it passes in a day of the year: "
        f"{_num(geo[k], 2)} MW on {stops.day_name(k)}, when {_num(flow, 0)} m3/h of brine at "
        f"about {_num(y.wellhead_c)} °C heat the network's {_num(rules.heat_return_c)} °C return "
        f"towards {_num(y.hex_outlet_c)} °C (the wellhead less the exchanger's approach).",
        [_either(flow)] if flow else [],
    )


def explain(entry, key: str) -> Tuple[str, List[str]]:
    """Return how one of a design's figures was found, and the values the reply must keep.

    ("", []) when this module has no account of the figure.
    """
    from gemini_agent import answer as answering

    y, a, e = entry.year, entry.alternative, entry.economics
    sizes = a.sizes_mw or {}
    if key == "boiler_size":
        return _bank(
            entry,
            "gas boiler",
            sizes.get("boiler", 0.0),
            int(getattr(a, "boiler_units", 1) or 1),
            "heat",
            "boiler",
            "the heat demand",
        )
    if key == "chiller_size":
        return _bank(
            entry,
            "electric chillers",
            sizes.get("chillers", 0.0),
            int(getattr(a, "chiller_units", 1) or 1),
            "cool",
            "chill",
            "the cold demand",
        )
    if key in ("heat_pump_size", "heat_split"):
        why = answering.heat_split_why(entry)
        costs = re.findall(r"\d+(?:\.\d+)? €/MWh", why)
        return why, (["~" + " ".join(costs)] if costs else [])
    if key == "hex_size":
        return _hex(entry)
    if key in ("lcoh", "lcoc", "lcoe", "capex"):
        return _costs(entry, key)
    if key == "co2_saving":
        from gemini_agent.lookup import _co2_sources

        sources = _co2_sources(y, e)
        return (
            "The CO2 saving compares the design's CO2 over the year with gas boilers and electric "
            f"chillers for the same demand at the same prices: {sources}.",
            ["~" + sources] if numbers_in(sources) else [],
        )
    if key in ("wellhead_temp", "reinjection_temp", "reservoir_temp"):
        return _brine_temps(entry, key)
    if key == "known_rock_temp":
        from gemini_agent import engine

        rules = engine.rules_for(entry.brief)
        d, known = rules.reservoir_depth_m, rules.reservoir_temperature_c(rules.reservoir_depth_m)
        here = rules.reservoir_temperature_c(a.depth_m)
        return (
            f"{_num(known)} °C is the known aquifer's temperature at its midpoint, "
            f"{_num(d, 0)} m: the surface's {_num(rules.surface_temperature_c)} °C plus "
            f"{_num(rules.gradient_c_per_km)} °C/km × {_num(d / 1000, 2)} km (the challenge "
            f"gives the gradient, not the temperature). This design's wells go to "
            f"{_num(a.depth_m, 0)} m, an assumed aquifer with the same properties, where the "
            f"same gradient gives {_num(here)} °C.",
            [
                "~"
                + " ".join(_num(x) for x in (rules.gradient_c_per_km, rules.surface_temperature_c))
            ],
        )
    return "", []


def _costs(entry, key: str) -> Tuple[str, List[str]]:
    """Return how a cost was found (its parts, or the capital's), and its two largest parts."""
    from gemini_agent.answer import capital_parts, cost_parts

    y, e = entry.year, entry.economics
    heat, cold = y.heat_delivered_gwh, y.cool_delivered_gwh
    if key == "lcoe":
        return (
            f"The cost of heat and cold together, {_num(e.lcoe_eur_per_mwh or 0)} €/MWh, is the "
            f"year's cost of both divided by all the MWh delivered ({_num(heat)} GWh of heat and "
            f"{_num(cold)} GWh of cold): the cost of heat is {_num(e.lcoh_eur_per_mwh)} €/MWh "
            f"and the cost of cold {_num(e.lcoc_eur_per_mwh or 0)} €/MWh.",
            [_either(e.lcoh_eur_per_mwh), _either(e.lcoc_eur_per_mwh or 0)],
        )
    if key == "capex":
        parts = capital_parts(e.capex_items)
        text = (
            f"The capital, {_num(e.capex_meur)} M€, is the sum of: "
            + "; ".join(f"{k} {_num(v)} M€" for k, v in parts)
            + ". The Economics tab gives each unit cost with its source (the wells: ThermoGIS v3)."
        )
    else:
        side, total, lines, gwh = (
            ("heat", e.lcoh_eur_per_mwh, e.lines_heat, heat)
            if key == "lcoh"
            else ("cold", e.lcoc_eur_per_mwh or 0, e.lines_cold, cold)
        )
        parts = cost_parts(lines, gwh)
        text = (
            f"The cost of {side}, {_num(total)} €/MWh, is the sum of: "
            + "; ".join(f"{k} {_num(v)} €/MWh" for k, v in parts)
            + ". Each part is a year's cost (the capital's annuity at 5.2 % real over each "
            "unit's life, fixed and variable O&M, gas and electricity at sourced prices, CO2 at "
            "the carbon price) divided by the MWh delivered; shared costs are split by the brine "
            "heat each side uses."
        )
    top = sorted(parts, key=lambda kv: -abs(kv[1]))[:2]
    return text, [_either(v) for _, v in top]


UNITS = {
    "boiler_size": "MW",
    "chiller_size": "MW",
    "heat_pump_size": "MW",
    "hex_size": "MW",
    "lcoh": "€/MWh",
    "lcoc": "€/MWh",
    "lcoe": "€/MWh",
    "capex": "M€",
    "co2_saving": "%",
    "wellhead_temp": "°C",
    "reinjection_temp": "°C",
    "reservoir_temp": "°C",
    "known_rock_temp": "°C",
    "heat_split": "%",
}


# The design's figures this module can account for, with how each is shown in the facts.
def figures(entry) -> List[Tuple[str, float]]:
    """Return (key, value) for each figure of a design whose origin ``explain`` can give."""
    y, a, e = entry.year, entry.alternative, entry.economics
    sizes = a.sizes_mw or {}
    out = [
        ("boiler_size", sizes.get("boiler", 0.0)),
        ("chiller_size", sizes.get("chillers", 0.0)),
        ("heat_pump_size", sizes.get("heat_pump", 0.0)),
        ("hex_size", y.hex_mw),
        ("lcoh", e.lcoh_eur_per_mwh),
        ("lcoc", e.lcoc_eur_per_mwh or 0.0),
        ("lcoe", e.lcoe_eur_per_mwh or 0.0),
        ("capex", e.capex_meur),
        ("co2_saving", (e.co2_saving_vs_gas or 0.0) * 100),
        ("wellhead_temp", y.wellhead_c),
        ("reinjection_temp", y.reinjection_c),
    ]
    # The heat split's shares (the boiler's 42.9 %): why the heat pump is sized as it is.
    split, heat = y.heat_split_gwh or {}, y.heat_delivered_gwh or 0.0
    if heat and a.heat_pump:
        out += [("heat_split", v / heat * 100) for v in split.values() if v]
    try:
        from gemini_agent import engine

        rules = engine.rules_for(entry.brief)
        rock = rules.reservoir_temperature_c(a.depth_m)
        out.append(("reservoir_temp", rock))
        # The known aquifer's own temperature (87 °C), when the wells go deeper than it.
        known = rules.reservoir_temperature_c(rules.reservoir_depth_m)
        if abs(known - rock) > 0.5:
            out.append(("known_rock_temp", known))
    except Exception:  # noqa: BLE001 - the other figures still stand
        pass
    boilers = int(getattr(a, "boiler_units", 1) or 1)
    if boilers > 1 and sizes.get("boiler"):
        out.append(("boiler_size", sizes["boiler"] / boilers))
    chillers = int(getattr(a, "chiller_units", 1) or 1)
    if chillers > 1 and sizes.get("chillers"):
        out.append(("chiller_size", sizes["chillers"] / chillers))
    return [(k, float(v)) for k, v in out if v]


def sentences_with(number: float, texts: Sequence[str], limit: int = 2) -> List[str]:
    """Return the sentences of ``texts`` that give ``number`` (the design's notes, its blocks)."""
    from gemini_agent.answer import sentences

    out = []
    for t in texts:
        for s in sentences(t):
            if any(_close(number, x) for x in numbers_in(s)) and s not in out:
                out.append(s)
                if len(out) >= limit:
                    return out
    return out


def origins(
    entry, message: str, texts: Sequence[str] = (), numbers: Optional[Sequence[float]] = None
) -> List[Tuple[str, str, str, List[str]]]:
    """Return (the figure's key, the number as asked, how it was found, the values to keep).

    The message's own quote may hold several numbers ("three boilers (totalling 30 MW)"); each
    one the design gives is explained once. Numbers no figure matches are looked up in ``texts``.
    ``numbers``: the ones the reasoning model read as asked about (else every number given).
    """
    asked = [x for x in (numbers if numbers else numbers_in(message)) if x > 0]
    out: List[Tuple[str, str, str, List[str]]] = []
    seen = set()
    figs = figures(entry)
    units = _units(message)
    for x in asked:
        keys = [k for k, v in figs if _close(x, v) or _rounded(x, v)]
        if x in units:  # the unit the message gives picks among them, when one has it
            keys = [k for k in keys if UNITS.get(k) == units[x]] or keys
        for k in keys:
            if k in seen:
                continue
            text, must = explain(entry, k)
            if text:
                seen.add(k)
                unit = UNITS.get(k, "")
                what = f"{_num(x, 2)}{'' if unit == '%' else ' '}{unit}".strip()
                out.append((k, what, text, must))
        if not keys and numbers:
            # Only for a number the reasoning model read as asked about: the design's notes
            # that give it (a pattern's guess would put them before a better answer).
            found = sentences_with(x, texts)
            if found:
                out.append(("notes", _num(x, 2), " ".join(found), []))
    return out


def asks_origin(message: str) -> bool:
    """Return True when a message asks where a number comes from (and gives one)."""
    return bool(ASKS_ORIGIN.search(message)) and any(x > 0 for x in numbers_in(message))


def draft(
    entry, message: str, texts: Sequence[str] = (), numbers: Optional[Sequence[float]] = None
) -> Optional[Tuple[str, List[str], List[str]]]:
    """Return the checked answer to "where does X come from?", the values to keep, the figures.

    Each figure's working must survive the model's rewording: the reply keeps at least one of
    the numbers that set it (not only the figure asked about, which would be circular).
    None when no number of the message is one of the design's.
    """
    found = origins(entry, message, texts, numbers)
    if not found:
        return None
    # One figure: its working alone. Several: each under its own line, so a sentence added
    # back to the model's reply never carries a heading.
    if len(found) == 1:
        text = found[0][2]
    else:
        text = "\n\n".join(f"**The {what}**\n{how}" for _, what, how, _ in found)
    return text, [m for *_, must in found for m in must], [k for k, *_ in found]
