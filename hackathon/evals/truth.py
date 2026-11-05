"""Checks that a design is right, read again from its year, not from what the agent says.

The verifier (``gemini_agent.verifier``) checks every design the agent shows; an eval that only
reads its verdict trusts the code it tests. These checks read the design's own year (the daily
flows, temperatures and shortfalls the plant model wrote) against the challenge's requirements,
written out here from the organisers' document:

- 1 to 3 doublets; 50 to 300 m³/h per running doublet; the brine cooled by at most 40 K;
  at most 330 days a year per doublet;
- heat delivered at 100 °C and cold at 20 °C, every day of the year;
- the known demand (``unit_test/dioscuri_plant/test_year.py``): 111.67 GWh of heat and
  23.74 GWh of cold a year, a 30 MW heat peak; a design that meets every day delivers both.

``of`` returns the findings for one eval case (kept in the case's record), ``checks`` turns
them into the named checks the eval table shows, one per cap, and ``quoted_totals`` reads the
yearly demand a reply quotes.
"""

from __future__ import annotations

import re
from typing import List, Optional

# The challenge's hard caps (the organisers' requirements, 28 Oct).
DOUBLETS = (1, 3)
FLOW_M3H = (50.0, 300.0)
BRINE_COOLING_K = 40.0
OPERATING_DAYS = 330
HEAT_SUPPLY_C = 100.0
COOL_SUPPLY_C = 20.0
# The challenge district's demand files, read by hand (test_year.py).
HEAT_GWH = 111.67
COOL_GWH = 23.74
PEAK_HEAT_MW = 30.0
# How far a total may be from the known one: 0.5 % (the files' own rounding is 0.01 GWh).
TOLERANCE = 0.005
SHORT_MW = 1e-3  # a day is met when it is short by less than 1 kW

CAP_NAMES = {
    "doublets": "cap: 1 to 3 doublets",
    "flow": "cap: 50 to 300 m³/h a doublet",
    "brine": "cap: brine cooled by at most 40 K",
    "days": "cap: at most 330 days a doublet",
    "heat": "cap: heat at 100 °C every day",
    "cold": "cap: cold at 20 °C every day",
}
KNOWN_NAMES = {
    "demand": "known: 111.67 GWh heat, 23.74 GWh cold, 30 MW peak read",
    "heat": "known: 111.67 GWh of heat delivered",
    "cold": "known: 23.74 GWh of cold delivered",
}


def entry_of(session, result: dict):
    """Return the design the turn showed (its code in ``result["alternative"]``), or None."""
    code = result.get("alternative")
    if not code:
        return None
    for e in reversed(list(session.ledger)):
        if e.alternative.code == code:
            return e
    chosen = getattr(session, "chosen", None)
    return chosen if chosen is not None and chosen.alternative.code == code else None


def _row(key: str, ok: Optional[bool], found: str, names: dict) -> dict:
    return {"key": key, "name": names[key], "ok": ok, "found": found}


def caps(entry) -> List[dict]:
    """Return one finding per hard cap of a design, from its year's daily values.

    ``ok`` is None when the year does not have what the cap needs (a design kept without its
    daily values).
    """
    y, alt = entry.year, entry.alternative
    out = []
    n = int(alt.n_doublets or 0)
    out.append(_row("doublets", DOUBLETS[0] <= n <= DOUBLETS[1], f"{n} doublet(s)", CAP_NAMES))
    doublets = y.doublets or []
    if n and doublets:
        flows = [f for d in doublets for f, on in zip(d["flow_m3h"], d["on"]) if on]
        lo, hi = (min(flows), max(flows)) if flows else (0.0, 0.0)
        out.append(
            _row(
                "flow",
                bool(flows) and FLOW_M3H[0] - 1e-6 <= lo and hi <= FLOW_M3H[1] + 1e-6,
                f"{lo:.0f} to {hi:.0f} m³/h on running days",
                CAP_NAMES,
            )
        )
        drops = [
            w - r
            for d in doublets
            for w, r, on in zip(d.get("wellhead_c") or [], d.get("reinjection_c") or [], d["on"])
            if on
        ]
        worst = max(drops) if drops else None
        out.append(
            _row(
                "brine",
                None if worst is None else worst <= BRINE_COOLING_K + 1e-6,
                "no temperatures kept" if worst is None else f"at most {worst:.1f} K",
                CAP_NAMES,
            )
        )
        days = max(sum(bool(x) for x in d["on"]) for d in doublets)
        out.append(_row("days", days <= OPERATING_DAYS, f"{days} days at most", CAP_NAMES))
    elif n:
        for key in ("flow", "brine", "days"):
            out.append(_row(key, None, "the year's doublet days were not kept", CAP_NAMES))
    daily = y.daily_mw or {}
    brief = entry.brief
    heat_c = brief.heating.supply_c if brief.heating else HEAT_SUPPLY_C
    cool_c = brief.cooling.supply_c if brief.cooling else COOL_SUPPLY_C
    for key, kind, temp, ok_temp in (
        ("heat", "heat", heat_c, heat_c >= HEAT_SUPPLY_C - 1e-6),
        ("cold", "cool", cool_c, cool_c <= COOL_SUPPLY_C + 1e-6),
    ):
        short = (daily.get(kind) or {}).get("short")
        if short is None:
            out.append(_row(key, None, "the daily values were not kept", CAP_NAMES))
            continue
        missed = [i for i, s in enumerate(short) if s > SHORT_MW]
        said = f"supplied at {temp:g} °C; " + (
            "met every day"
            if not missed
            else f"short on {len(missed)} day(s), up to {max(short):.2f} MW"
        )
        out.append(_row(key, ok_temp and not missed, said, CAP_NAMES))
    return out


def _near(got: float, want: float) -> bool:
    return abs(got - want) <= TOLERANCE * want


def known(entry, any_project: bool = False) -> List[dict]:
    """Return the known demand's findings: read right, and delivered in full.

    Only for the challenge district (or, with ``any_project``, a project made from its
    demand) at its own demand: a what-if that scales the demand has other totals.
    """
    brief = entry.brief
    if (brief.project_id != "challenge" and not any_project) or any(
        abs(float(s) - 1.0) > 1e-9 for s in brief.demand_scale or [1.0, 1.0]
    ):
        return []
    daily = entry.year.daily_mw or {}
    heat, cool = daily.get("heat") or {}, daily.get("cool") or {}
    if not heat.get("demand") or not cool.get("demand"):
        return []
    h_dem = sum(heat["demand"]) * 24 / 1000
    c_dem = sum(cool["demand"]) * 24 / 1000
    peak = max(heat["demand"])
    h_got = sum(d - s for d, s in zip(heat["demand"], heat.get("short") or [0.0] * 365)) * 24e-3
    c_got = sum(d - s for d, s in zip(cool["demand"], cool.get("short") or [0.0] * 365)) * 24e-3
    return [
        _row(
            "demand",
            _near(h_dem, HEAT_GWH) and _near(c_dem, COOL_GWH) and _near(peak, PEAK_HEAT_MW),
            f"{h_dem:.2f} GWh heat, {c_dem:.2f} GWh cold, peak {peak:.2f} MW",
            KNOWN_NAMES,
        ),
        _row("heat", _near(h_got, HEAT_GWH), f"{h_got:.2f} GWh", KNOWN_NAMES),
        _row("cold", _near(c_got, COOL_GWH), f"{c_got:.2f} GWh", KNOWN_NAMES),
    ]


# A sentence about the yearly demand; one about what a unit gives is about something else.
DEMAND_WORDS = re.compile(r"\bdemand|\bneeds?\b|\brequire", re.I)
UNIT_WORDS = re.compile(
    r"geotherm|boiler|heat pump|chiller|absorption|exchanger|doublet|covers?|suppl(y|ies)|"
    r"\bsaves?\b|short",
    re.I,
)
GWH = re.compile(r"(?<![\d.])(\d{1,3}(?:[.,]\d{1,3})?)\s*GWh", re.I)


def quoted_totals(answer: str) -> List[dict]:
    """Return the yearly demand figures a reply gives, each right or wrong.

    A figure within 5 % of a known total is read as that total: "111.7 GWh" and "112 GWh" are
    the heat demand rounded, "110 GWh of demand" is wrong. A figure further away is taken for
    another quantity, and a sentence about what a unit gives ("geothermal covers 108 GWh") is
    not read.
    """
    said = []
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", answer or ""):
        if not DEMAND_WORDS.search(sentence) or UNIT_WORDS.search(sentence):
            continue
        for m in GWH.finditer(sentence):
            text = m.group(1).replace(",", ".")
            got = float(text)
            places = len(text.split(".")[1]) if "." in text else 0
            for want in (HEAT_GWH, COOL_GWH):
                if abs(got - want) <= 0.05 * want:
                    ok = abs(round(want, places) - got) < 1e-9
                    said.append({"text": m.group(0), "known": want, "ok": ok})
    return said


def of(session, result: dict, known_demand: bool = False) -> Optional[dict]:
    """Return what a case's design and reply are, against the challenge's truth.

    ``design`` is the design the turn showed (None when it showed none), ``caps`` and
    ``known`` its findings, ``quotes`` the yearly demand figures the reply gives.
    ``known_demand``: the case's project was made from the challenge's demand (an upload).
    """
    out: dict = {"design": None, "caps": [], "known": [], "quotes": []}
    entry = entry_of(session, result)
    if entry is not None:
        out["design"] = entry.alternative.uid or entry.alternative.code
        out["caps"] = caps(entry)
        out["known"] = known(entry, known_demand)
    if getattr(session.project, "id", "challenge") == "challenge":
        out["quotes"] = quoted_totals(result.get("answer") or "")
    return out


def checks(scenario: dict, result: dict) -> dict:
    """Return the named checks a scenario asks for: ``hard_caps`` and ``known_totals``.

    Each cap is its own check, so a failed case says which cap broke. A scenario that asks for
    them on a turn that showed no design fails them (``hard_caps: no design shown``). Every
    case whose reply quotes the yearly demand also gets ``totals quoted right``.
    """
    found = result.get("truth") or {}
    asked = set(scenario.get("checks") or [])
    out: dict = {}
    for check, key in (("hard_caps", "caps"), ("known_totals", "known")):
        if check not in asked:
            continue
        rows = found.get(key) or []
        if not rows:
            out[f"{check}: no design shown"] = False if not found.get("design") else None
        for r in rows:
            out[r["name"]] = r["ok"]
    if found.get("quotes"):
        out["totals quoted right"] = all(q["ok"] for q in found["quotes"])
    return out
