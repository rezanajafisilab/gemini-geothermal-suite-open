"""Reporter: writes every answer from templates filled with tool results.

No model writes numbers. Each number is put into the text through ``Facts.put``, which
remembers it; ``Facts.ungrounded`` then lists any number in the final text that came from
neither a tool result nor the user's own message (it should always be empty). Replies to
off-topic messages and clarifying questions also exist in Dutch.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, List, Optional, Sequence, Set, Tuple

from gemini_agent.contract import DesignBrief, LedgerEntry, Question
from gemini_agent.intake import numbers_in
from gemini_agent.verifier import carnot_cop

# A design's code ("1D-HP-EC@3000-N1-FC", "3D-HP-EC@2500+3000+3000-EB-GS"): a name, so its
# depths after "@" are not numbers to check (4 Nov: "@3000" was flagged as an unsourced 3000).
DESIGN_CODE = re.compile(r"(?<![\w-])\d+D-[A-Za-z0-9@+\-]*[A-Za-z0-9]")

DESIGN_SUGGESTIONS = [
    "What if the reservoir is 10 °C colder?",
    "Which design has the lowest CO₂?",
    "Compare a 2.5 km and a 3.5 km doublet",
]
KEEP_LIMITS = {
    "en": "Keep my limits and report the shortfall",
    "nl": "Houd mijn grenzen aan en meld het tekort",
}
REFUSE_SUGGESTIONS = {
    "en": [
        "Design heating and cooling for this district",
        "Compare well depths",
        "What does the reservoir temperature change?",
    ],
    "nl": [
        "Ontwerp warmte en koude voor deze wijk",
        "Vergelijk boordieptes",
        "Wat doet de reservoirtemperatuur?",
    ],
}


class Facts:
    """Collects every number put into an answer, to prove the answer is grounded."""

    def __init__(self, user_text: str = ""):
        """Start with the numbers the user wrote, which may be quoted back.

        Parameters
        ----------
        user_text : str
            The user's message.
        """
        self.allowed: Set[float] = set(numbers_in(user_text))

    def put(self, text: str) -> str:
        """Return ``text`` unchanged after recording the numbers in it.

        Parameters
        ----------
        text : str
            A formatted value, for example ``"41 €/MWh"``.

        Returns
        -------
        str
            The same text.
        """
        self.allowed.update(numbers_in(text))
        return text

    def ungrounded(self, text: str) -> List[float]:
        """Return the numbers in ``text`` that were never put in through ``put``.

        Parameters
        ----------
        text : str
            The final answer.

        Returns
        -------
        list of float
            Numbers with no source; empty when the answer is grounded. Digits glued to a
            letter (handles such as ``A1``) and design codes (``1D-HP-EC@3000-N1-FC``) are
            names, not numbers, and are skipped.
        """
        text = DESIGN_CODE.sub(" ", text)
        loose = " ".join(m.group(0) for m in re.finditer(r"(?<![A-Za-z\d.])\d+(?:[.,]\d+)*", text))
        return [
            n
            for n in numbers_in(loose)
            if not any(abs(n - a) <= 1e-9 * max(1.0, a) for a in self.allowed)
        ]


def pct(x: float) -> str:
    """Return a share as a short percentage (``100%``, ``97.5%``)."""
    if x >= 0.9995:
        return "100%"
    return f"{x * 100:.1f}".rstrip("0").rstrip(".") + "%"


def num(x: float, digits: int = 1) -> str:
    """Return a number with at most ``digits`` decimals and thousands separators.

    Rounded half up, as the app's ``toFixed`` does: Python's half-even wrote 64.25 €/MWh as
    "64.2" in the chat while the card showed "64.3" (UI review, 31 Oct).
    """
    try:
        if abs(float(x)) >= 1000:
            digits = 0  # thousands as whole numbers, as the app's fmtNum writes them
        x = float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-digits), ROUND_HALF_UP))
    except (InvalidOperation, ValueError, OverflowError):
        pass
    text = f"{x:,.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _shares(entry: LedgerEntry) -> Dict[str, float]:
    total = entry.year.heat_delivered_gwh or 1.0
    return {k: v / total for k, v in entry.year.heat_split_gwh.items()}


def comparison(entries: Sequence[LedgerEntry], chosen: Optional[LedgerEntry]) -> dict:
    """Return the designs side by side, for the chat's comparison chart.

    Parameters
    ----------
    entries : sequence of LedgerEntry
        The designs to compare (one per code, the chosen one first).
    chosen : LedgerEntry, optional
        The recommended or picked design.

    Returns
    -------
    dict
        ``chosen`` (its code) and ``designs``: code, name, verified, the costs of heat and
        cold (€/MWh), CO₂ saving against gas (%), heat and cold covered (%), capital (M€),
        the reservoir shift of a what-if, and the tools' source.
    """
    out = []
    for e in entries:
        out.append(
            {
                "code": e.alternative.code,
                "name": e.alternative.name,
                "verified": e.verification.passed,
                # The checks it fails, by name: the card says what happened (Ali, 3 Nov).
                "failed": [c.name for c in e.verification.checks if not c.passed],
                "lcoh": e.economics.lcoh_eur_per_mwh,
                "lcoc": e.economics.lcoc_eur_per_mwh,
                "co2_saving_pct": round(e.economics.co2_saving_vs_gas * 100, 1),
                "heat_coverage_pct": round(e.year.heat_coverage * 100, 1),
                "cool_coverage_pct": round(e.year.cool_coverage * 100, 1),
                "capex_meur": e.economics.capex_meur,
                "reservoir_delta_c": e.brief.reservoir_delta_c or 0.0,
                "reference": not e.alternative.heat_pump and e.alternative.depth_m == 0,
                "source": e.year.source,
            }
        )
    return {"chosen": chosen.alternative.code if chosen else None, "designs": out}


def design_id(entry: LedgerEntry) -> str:
    """Return a design's id, unique in a conversation: its name (A1, W1 ...) and its code.

    ``A1 · 1D-HP-EC-N1`` (the first search's pick), ``W1 · 1D-HP-EC-N1`` (a what-if). Designs
    saved before names existed keep the older id: the code and what sets it apart (a what-if's
    change, a later search's ``S3``).
    """
    a = entry.alternative
    if a.uid:
        return a.uid if a.uid == a.code else f"{a.uid} · {a.code}"
    if entry.change_label:
        return f"{a.code} · {entry.change_label}"
    d = entry.brief.reservoir_delta_c or 0.0
    if d:
        return f"{a.code} {'+' if d > 0 else '−'}{abs(d):g} °C"
    if a.attempt and a.attempt != "S1" and a.role in ("chosen", "candidate", "what_if"):
        return f"{a.code} · {a.attempt}"
    return a.code


def result_card(entry: LedgerEntry) -> dict:
    """Return the structured result the UI draws as a card.

    Parameters
    ----------
    entry : LedgerEntry
        The chosen design.

    Returns
    -------
    dict
        Name, verification and KPIs, heat and cold splits, and equipment sizes.
    """
    y, e, v = entry.year, entry.economics, entry.verification
    return {
        "alternative": entry.alternative.code,
        "uid": entry.alternative.uid,
        "name": entry.alternative.name,
        "source": y.source,
        "verified": v.passed,
        "checks": {"passed": sum(c.passed for c in v.checks), "total": len(v.checks)},
        "failed": [c.name for c in v.checks if not c.passed],
        "kpis": [
            {
                # The headline: what the search ranks by (heat and cold together).
                "id": "lcoe",
                "label": "Cost of heat and cold",
                "value": e.lcoe_eur_per_mwh,
                "unit": "€/MWh",
            },
            {
                "id": "heat_coverage",
                "label": "Heat covered",
                "value": round(y.heat_coverage * 100, 1),
                "unit": "%",
            },
            {
                "id": "cool_coverage",
                "label": "Cold covered",
                "value": round(y.cool_coverage * 100, 1),
                "unit": "%",
            },
            {"id": "lcoh", "label": "Cost of heat", "value": e.lcoh_eur_per_mwh, "unit": "€/MWh"},
            {"id": "lcoc", "label": "Cost of cold", "value": e.lcoc_eur_per_mwh, "unit": "€/MWh"},
            {
                "id": "co2",
                "label": "CO₂ against gas",
                "value": round(-e.co2_saving_vs_gas * 100, 1),
                "unit": "%",
            },
            {
                "id": "flh",
                "label": "Doublet in use",
                "value": y.full_load_hours,
                "unit": "full-load hours",
            },
        ],
        "heat_split_gwh": y.heat_split_gwh,
        "cool_split_gwh": y.cool_split_gwh,
        "monthly_gwh": y.monthly_gwh,
        "sizes_mw": {
            "heat_exchanger": y.hex_mw,
            "heat_pump": y.heat_pump_mw,
            "boiler": y.boiler_mw,
            "absorption": y.absorption_mw,
            "chillers": y.chiller_mw,
        },
        "temperatures_c": {
            "wellhead": y.wellhead_c,
            "heat_exchanger_out": y.hex_outlet_c,
            "reinjection": y.reinjection_c,
        },
        "demand_gwh": {"heat": y.heat_demand_gwh, "cold": y.cool_demand_gwh},
        # What sets this design apart: a what-if's change, the variant flags, each doublet.
        "design_id": design_id(entry),
        "change_label": entry.change_label,
        "changes": entry.changes,
        "flags": entry.alternative.flags,
        "doublets": entry.alternative.doublets,
        "dispatch": entry.alternative.dispatch,
        "picks": [],
        "my_picks": list(entry.alternative.picks),
        "reliable": entry.alternative.reliable,
        "firm": firm_view(entry),
        "vs_gas_pct": vs_gas(entry),
        "gemini_check": _gemini_check(entry),
        "cooling_check": _cooling_check(entry),
        "network": y.network,
        "service": [
            {"unit": u, "from": _day_words(int(a)), "to": _day_words(int(b))}
            for u, a, b in (y.service or [])
        ],
        "solar": y.solar,
        "storage": y.storage,
        "operability": y.operability,
    }


def _gemini_check(entry: LedgerEntry) -> Optional[dict]:
    """Return GEMINI's run of the design's brine loop against the plant model (or None)."""
    from gemini_agent import engine

    try:
        return engine.gemini_check(entry)
    except Exception:  # noqa: BLE001 - the card shows the design without the check
        return None


def _cooling_check(entry: LedgerEntry) -> Optional[dict]:
    """Return Ali's cooling model run on the design's chillers and towers (or None)."""
    from gemini_agent import cooling_check

    try:
        return cooling_check.check(entry)
    except Exception:  # noqa: BLE001 - the card shows the design without the check
        return None


def _day_words(i: int) -> str:
    from gemini_agent.answer import _date

    return _date(i)


def vs_gas(entry: LedgerEntry) -> Optional[dict]:
    """Return a design's costs against the gas reference of its own conditions, as fractions."""
    from gemini_agent import engine

    if not entry.alternative.n_doublets:
        return None
    try:
        ref = engine.reference(entry.brief)
    except Exception:  # noqa: BLE001 - a card without the comparison rather than none
        return None
    return engine.against_gas(entry, ref)


def firm_view(entry: LedgerEntry) -> Optional[dict]:
    """Return the card's firm capacity: the spare on the peak days and the one-unit-out cases."""
    from gemini_agent import engine

    firm = engine.firm(entry) if entry.alternative.n_doublets else None
    if not firm:
        return None
    cases = []
    for o in firm.get("outages") or []:
        side = "heat" if o["heat"]["worst_mw"] >= o["cool"]["worst_mw"] else "cool"
        x = o[side]
        cases.append(
            {
                "unit": o["unit"],
                "short": bool(o["heat"]["days_short"] or o["cool"]["days_short"]),
                "side": side,
                "worst_mw": x["worst_mw"],
                "worst_day": x["worst_day"],
                "days_short": x["days_short"],
                "short_gwh": round(o["heat"]["short_gwh"] + o["cool"]["short_gwh"], 3),
            }
        )
    return {
        "peak": firm.get("peak") or {},
        "cases": cases,
        "short": sum(c["short"] for c in cases),
        "reliable": entry.alternative.reliable,
        "boiler_units": entry.alternative.boiler_units,
        "chiller_units": entry.alternative.chiller_units,
    }


def picks_view(candidates: Sequence[LedgerEntry]) -> List[dict]:
    """Return the search's picks for the card (``engine.PICKS``), each with its figures."""
    from gemini_agent import engine

    out = []
    for key in engine.PICKS:
        e = next((x for x in candidates if key in x.alternative.picks), None)
        if e is None:
            continue
        firm = firm_view(e) or {}
        out.append(
            {
                "key": key,
                "label": engine.PICK_NAMES[key],
                "uid": e.alternative.uid,
                "code": e.alternative.code,
                "id": design_id(e),
                "chosen": e.alternative.role == "chosen",
                "lcoe": e.economics.lcoe_eur_per_mwh,
                "lcoh": e.economics.lcoh_eur_per_mwh,
                "lcoc": e.economics.lcoc_eur_per_mwh,
                "co2_t": e.economics.co2_t_per_year,
                "co2_saving_pct": round((e.economics.co2_saving_vs_gas or 0.0) * 100, 1),
                "capex_meur": e.economics.capex_meur,
                "reliable": e.alternative.reliable,
                "n1_short": firm.get("short"),
                "rule": engine.OBJECTIVE_WORDS[key],
                "vs_gas_pct": vs_gas(e),
            }
        )
    return out


def research_view(base: LedgerEntry, best: Optional[LedgerEntry]) -> Optional[dict]:
    """Return what a what-if's new search picks against the design it changed, for its card."""
    if best is None:
        return None
    return {
        "code": best.alternative.code,
        "uid": best.alternative.uid,
        "id": design_id(best),
        "lcoe": best.economics.lcoe_eur_per_mwh,
        "base_code": base.alternative.code,
        "base_id": design_id(base),
        "changed": best.alternative.code != base.alternative.code,
        "objective": best.brief.objective,
    }


def design_answer(best: LedgerEntry, others: Sequence[LedgerEntry], facts: Facts) -> str:
    """Return the answer for a feasible design.

    Parameters
    ----------
    best : LedgerEntry
        The recommended design.
    others : sequence of LedgerEntry
        The other feasible alternatives, cheapest first.
    facts : Facts
        Number register.

    Returns
    -------
    str
        Two or three short sentences.
    """
    y, e = best.year, best.economics
    text = f"{best.alternative.code} covers {facts.put(pct(y.heat_coverage))} of the heat"
    if best.brief.wants_cooling and y.cool_demand_gwh > 0:
        text += f" and {facts.put(pct(y.cool_coverage))} of the cold"
    text += f" at {facts.put(num(e.lcoh_eur_per_mwh))} €/MWh for heat"
    if best.brief.wants_cooling and e.lcoc_eur_per_mwh is not None:
        text += f" and {facts.put(num(e.lcoc_eur_per_mwh))} €/MWh for cold"
    text += f", with {facts.put(pct(e.co2_saving_vs_gas))} less CO₂ than gas."
    if y.cooling_gain > 0.01:
        text += (
            " Summer cooling from the same brine keeps the doublet busy "
            f"{facts.put(pct(y.cooling_gain))} longer."
        )
    if others:
        ranked = sorted(others, key=lambda o: o.economics.lcoh_eur_per_mwh)[:2]
        nxt = ", ".join(
            f"{o.alternative.code}{' (gas reference)' if o.alternative.code == 'A4' else ''} at "
            f"{facts.put(num(o.economics.lcoh_eur_per_mwh))} €/MWh"
            for o in ranked
        )
        text += f" For comparison: {nxt}."
    return text


def compare_answer(entries: Sequence[LedgerEntry], facts: Facts) -> str:
    """Return the answer for a comparison of two or more alternatives.

    Parameters
    ----------
    entries : sequence of LedgerEntry
        The simulated alternatives (any order).
    facts : Facts
        Number register.

    Returns
    -------
    str
        One sentence per alternative and one on why the cheaper one wins.
    """
    ranked = sorted(entries, key=lambda x: x.economics.lcoh_eur_per_mwh)
    parts = [
        f"{facts.put(x.alternative.name)}: "
        f"{facts.put(num(x.economics.lcoh_eur_per_mwh))} €/MWh for heat, "
        f"{facts.put(pct(x.economics.co2_saving_vs_gas))} less CO₂ than gas, "
        f"{facts.put(pct(x.year.heat_coverage))} of the heat covered."
        for x in ranked
    ]
    win, lose = ranked[0], ranked[-1]
    if len(ranked) > 1:
        diff = lose.economics.lcoh_eur_per_mwh - win.economics.lcoh_eur_per_mwh
        sw, sl = _shares(win), _shares(lose)
        parts.append(
            f"The {facts.put(win.alternative.name)} is cheaper by "
            f"{facts.put(num(diff))} €/MWh: it takes "
            f"{facts.put(pct(sw['geo']))} of its heat straight from the brine, while the "
            f"{facts.put(lose.alternative.name)} needs heat pumps for "
            f"{facts.put(pct(sl['hp']))} and a boiler "
            f"for {facts.put(pct(sl['boiler']))}."
        )
    return " ".join(parts)


def what_if_answer(
    base: LedgerEntry,
    new: LedgerEntry,
    facts: Facts,
    label: str = "",
    best: Optional[LedgerEntry] = None,
) -> str:
    """Return the answer for a what-if: the same design under the change, and the new search.

    Parameters
    ----------
    base : LedgerEntry
        The design before the change.
    new : LedgerEntry
        The same design (with any change to the plant itself) under the change.
    facts : Facts
        Number register.
    label : str
        The change in words ("heating return temperature 50 °C").
    best : LedgerEntry, optional
        What the search picks under the change, when it was run.

    Returns
    -------
    str
        What moves and why, and whether another design is now better.
    """
    if not label and new.brief.reservoir_delta_c:
        d = new.brief.reservoir_delta_c
        label = f"the reservoir {num(abs(d))} °C {'colder' if d < 0 else 'warmer'}"
    sb, sn = _shares(base), _shares(new)
    eb, en = base.economics, new.economics
    lines = [
        f"With {facts.put(label)}, {base.alternative.code} with its present sizes covers "
        f"{facts.put(pct(new.year.heat_coverage))} of the heat"
        + (
            f" and {facts.put(pct(new.year.cool_coverage))} of the cold"
            if new.year.cool_demand_gwh
            else ""
        )
        + f". Heat and cold cost {facts.put(num(en.lcoe_eur_per_mwh or 0))} €/MWh (was "
        f"{facts.put(num(eb.lcoe_eur_per_mwh or 0))}); the CO₂ saving against gas is "
        f"{facts.put(pct(en.co2_saving_vs_gas))} (was {facts.put(pct(eb.co2_saving_vs_gas))})."
    ]
    lines.append(
        f"The heat exchanger gives {facts.put(pct(sn['geo']))} of the heat (was "
        f"{facts.put(pct(sb['geo']))}), the heat pump {facts.put(pct(sn['hp']))} (was "
        f"{facts.put(pct(sb['hp']))}) and the boiler {facts.put(pct(sn['boiler']))} (was "
        f"{facts.put(pct(sb['boiler']))})."
    )
    if "doublet_stops" in (getattr(new, "changes", None) or {}):
        # "Could we move the stop to August?" (1 Nov): the reply took the what-if's dates for
        # the design's own; both are said.
        from gemini_agent import stops as stop_dates

        def when(entry: LedgerEntry) -> str:
            return "; ".join(
                f"doublet {k + 1} {stop_dates.span_words(r)}"
                for k, r in enumerate(stop_dates.ranges_of(entry.year))
                if r
            )

        if when(base):
            lines.insert(
                1,
                f"{base.alternative.code} as designed stops {facts.put(when(base))} "
                f"({stop_dates.summary(base.year, base.brief)}); in this what-if it stops "
                f"{facts.put(when(new))}.",
            )
    if new.year.reinjection_c and base.year.reinjection_c:
        lines.append(
            f"The brine goes back at {facts.put(num(new.year.reinjection_c))} °C at the "
            f"coldest (was {facts.put(num(base.year.reinjection_c))} °C)."
        )
    if new.year.violations:
        lines.append(f"With these sizes it breaks a cap: {facts.put(new.year.violations[0])}")
    money = _money_against_gas(new)
    was = _money_against_gas(base)
    if money and was:
        lines.append(
            f"Against gas under the change (gas boilers and chillers at the same prices): NPV "
            f"{facts.put(num(money['npv_meur']))} M€ (was {facts.put(num(was['npv_meur']))} M€), "
            + (
                f"paying back in year {facts.put(str(money['payback_years']))}"
                if money.get("payback_years")
                else "never paying back in 30 years"
            )
            + "."
        )
    if best is not None:
        same = best.alternative.code == base.alternative.code
        lines.append(
            f"Searching again under the change picks {best.alternative.code} at "
            f"{facts.put(num(best.economics.lcoe_eur_per_mwh or 0))} €/MWh"
            + (
                " (the same layout, sized for the change)."
                if same
                else f" instead of {base.alternative.code}: {best.alternative.name}."
            )
        )
    return " ".join(lines)


def search_for_answer(base: LedgerEntry, new: LedgerEntry, facts: Facts, label: str) -> str:
    """Return the answer when a change asks for another kind of design ("a gas-free version").

    The search's pick under the change set against the design: its cost, CO2, capital, where
    its heat comes from, whether any one unit can be out, and its money against gas.
    """
    eb, en = base.economics, new.economics
    gap = (en.lcoe_eur_per_mwh or 0) - (eb.lcoe_eur_per_mwh or 0)
    rel = gap / eb.lcoe_eur_per_mwh if eb.lcoe_eur_per_mwh else 0.0
    co2 = (en.co2_t_per_year - eb.co2_t_per_year) / eb.co2_t_per_year if eb.co2_t_per_year else 0
    names = {"geo": "the exchanger", "hp": "the heat pump", "boiler": "the gas boiler"}
    names["electric_boiler"] = "the electric boiler"
    split = new.year.heat_split_gwh or {}
    heat = sum(split.values()) or 1.0
    parts = [f"{names.get(k, k)} {facts.put(pct(v / heat))}" for k, v in split.items() if v > 0]
    floor = new.brief.min_co2_saving
    lines = []
    if floor:
        # "At least 50 % less CO2: could they live with the cheapest?" (1 Nov): say first
        # whether the design asked about meets it, then the search's pick under it.
        had = eb.co2_saving_vs_gas or 0.0
        lines.append(
            f"{design_id(base)} cuts CO₂ against gas by {facts.put(pct(had))}, "
            + ("which meets" if had >= floor - 1e-9 else "short of")
            + f" the {facts.put(pct(floor))} asked."
        )
    missed = bool(floor) and (en.co2_saving_vs_gas or 0.0) < floor - 1e-9
    lines += [
        (
            f"No design the search tried cuts CO₂ by {facts.put(pct(floor))}; without that "
            f"floor it picks {design_id(new)}: {new.alternative.name}."
            if missed
            else f"For {facts.put(label)} the search picks {design_id(new)}: "
            f"{new.alternative.name}."
        ),
        f"Heat and cold cost {facts.put(num(en.lcoe_eur_per_mwh or 0))} €/MWh against "
        f"{facts.put(num(eb.lcoe_eur_per_mwh or 0))} for {design_id(base)} "
        f"({facts.put(f'{gap:+.1f}')} €/MWh, {facts.put(f'{rel * 100:+.0f}')} %); CO₂ "
        f"{facts.put(num(en.co2_t_per_year, 0))} t a year against "
        f"{facts.put(num(eb.co2_t_per_year, 0))} ({facts.put(f'{co2 * 100:+.0f}')} %); capital "
        f"{facts.put(num(en.capex_meur))} M€ against {facts.put(num(eb.capex_meur))} M€.",
        "Its heat comes from " + ", ".join(parts) + ".",
        (
            "Any one unit can be out and every day is still met."
            if new.alternative.reliable
            else "It is not sized for one unit out."
        ),
    ]
    money, was = _money_against_gas(new), _money_against_gas(base)
    if money and was:
        lines.append(
            f"Against gas: NPV {facts.put(num(money['npv_meur']))} M€ (against "
            f"{facts.put(num(was['npv_meur']))} M€ for {design_id(base)})."
        )
    return " ".join(lines)


def _money_against_gas(entry: LedgerEntry) -> Optional[dict]:
    """Return a design's NPV and payback against the gas reference of its own conditions."""
    from gemini_agent import engine

    if not entry.alternative.depth_m:
        return None
    try:
        ref = engine.reference(entry.brief)
        return engine.versus_reference(entry, ref, engine.prices_for(None, entry.brief))
    except Exception:  # noqa: BLE001 - the what-if is said without its money
        return None


def unsupported_note(asks: Sequence[str]) -> str:
    """Return what a request asked for that the model cannot do, in a few words."""
    return "; ".join(a for a in asks if a)


def unsupported_text(asks: Sequence[str], chosen: Optional[LedgerEntry]) -> str:
    """Say plainly which asked changes the model cannot make, and what it can change."""
    what = unsupported_note(asks) or "that"
    text = (
        f"I can't vary {what}: my plant model has no input for it, so any number I gave would "
        "be a guess. I can change the networks' temperatures, the reservoir (temperature, "
        "permeability, thickness, pressure), the challenge's caps (operating days, flow limits, "
        "the 40 K cooling limit), the demand, the prices and costs (the electricity price "
        "among them), the number of doublets and how each is built (two injectors, a treatment "
        "train per doublet, which part of the aquifer the wells are open to, base-load "
        "dispatch), the units' sizes, gas-free plants or selling the brine's gas, the district "
        "network's heat losses, the yearly service and the doublets' stop dates, and what is "
        "ruled out. Ask for any of these and I'll run it."
    )
    if chosen is not None and chosen.year.electricity_gwh:
        # For scale, what the design draws from the grid and what that emits (1 Nov: "a solar
        # park to run the heat pump" got a new search instead).
        y = chosen.year
        el = y.electricity_gwh
        total = sum(v for v in el.values() if v)
        co2 = y.co2_t or {}
        text += (
            f" For scale: {chosen.alternative.code} draws {num(total)} GWh of electricity a year "
            f"(the heat pump {num(el.get('hp', 0.0))} GWh), which gives "
            f"{num(co2.get('electricity', 0.0), 0)} t of its {num(co2.get('total', 0.0), 0)} t "
            "of CO2 a year (grid electricity at 0.20 t/MWh, a fixed factor in the model)."
        )
    return text


def service_words(rules) -> Tuple[str, bool]:
    """Return each unit type's yearly service in words, and whether the user set any of it."""
    from dioscuri_plant.service import DAYS_OUT
    from gemini_agent import stops
    from gemini_agent.card_edits import SERVICE_UNITS

    plan = {str(u): (str(m), list(r)) for u, m, r in (rules.service_plan or ())}
    auto = bool(rules.planned_service)
    parts = []
    for unit, label, bank in SERVICE_UNITS:
        mode, ranges = plan.get(unit, ("auto" if auto else "off", []))
        each = " a unit" if bank else ""
        if mode == "dates":
            parts.append(f"{label.lower()} on your dates ({stops.span_words(ranges)})")
        elif mode == "auto":
            parts.append(f"{label.lower()} {DAYS_OUT[unit]} days{each} in its quietest weeks")
    if not parts:
        return "none: only the doublets' stops", bool(plan)
    return "; ".join(parts) + " (units a design does not have are left out)", bool(plan) or auto


def again_text(last: dict) -> str:
    """Say that these inputs already ran, and that a change gives another design."""
    label = str(last.get("label") or "").strip()
    run = f" ({last.get('id')}: {label})" if label else ""
    return (
        f"These are the inputs of the last search{run}. The search is deterministic: the same "
        "inputs give the same designs. Change any input below to get another design, then run it."
    )


def change_input_text() -> str:
    """Ask what to change on the inputs card."""
    return (
        'What should I change? For example "a 50 °C heating return", "two injectors per '
        'doublet", "a separate separator for each doublet" or "gas at 45 €/MWh". I\'ll '
        "show the inputs again with your change before I run the design."
    )


def explain_answer(entry: LedgerEntry, facts: Facts) -> str:
    """Return a short explanation of the summer cascade of a design.

    Parameters
    ----------
    entry : LedgerEntry
        The design to explain.
    facts : Facts
        Number register.

    Returns
    -------
    str
        How the brine is used in winter and in summer.
    """
    y = entry.year
    text = (
        f"In winter the brine leaves the well at {facts.put(num(y.wellhead_c))} °C, heats the "
        f"network through the heat exchanger down to {facts.put(num(y.hex_outlet_c))} °C, and "
        f"the heat pump takes it on to {facts.put(num(y.reinjection_c))} °C."
    )
    if y.absorption_mw > 0:
        text += (
            f" In summer the same brine drives a {facts.put(num(y.absorption_mw))} MW "
            f"absorption chiller, so the doublet works {facts.put(pct(y.cooling_gain))} "
            "longer each year."
        )
    return text


def refuse_text(language: str) -> str:
    """Return the reply to an off-topic message."""
    if language == "nl":
        return (
            "Dat valt buiten mijn taak: ik ontwerp geothermische warmte en koude voor een "
            "wijk, en elk getal komt uit een simulator. Probeer een van deze vragen."
        )
    return (
        "That's outside what I do: I design geothermal heating and cooling for a district, "
        "and every number comes from a simulator. Try one of these instead."
    )


def unavailable_text(model: str, fix: str, language: str, facts: Facts) -> str:
    """Return the reply when the local model cannot be reached.

    Parameters
    ----------
    model : str
        The configured model tag.
    fix : str
        The command that fixes it (``ollama serve`` or ``ollama pull <model>``).
    language : str
        ``"en"`` or ``"nl"``.
    facts : Facts
        Number register (the tag may contain digits).

    Returns
    -------
    str
        What is wrong and what to run.
    """
    model, fix = facts.put(model), facts.put(fix)
    if not fix:
        if language == "nl":
            return f"Het lokale model {model} antwoordde niet op tijd. Stel je vraag opnieuw."
        return (
            f"The local model {model} didn't answer in time (the model server may be busy). "
            "Please ask again."
        )
    if language == "nl":
        return (
            f"Ik kan je vraag nu niet lezen: het lokale model {model} is niet beschikbaar. "
            f"Voer `{fix}` uit en stel je vraag opnieuw."
        )
    return (
        f"I can't read your request right now: the local model {model} isn't available. "
        f"Run `{fix}` and ask again."
    )


def left_out_text(left_out: Sequence[Tuple[str, str]], facts: Facts) -> str:
    """Return the sentence naming designs that were left out and why (empty when none were).

    Parameters
    ----------
    left_out : sequence of (str, str)
        Design code and reason, for example ``("A2", "simulate_year failed: ...")``.
    facts : Facts
        Number register (reasons may quote check thresholds).

    Returns
    -------
    str
        For example ``" Left out: A2 (simulate_year failed: depth outside the model)."``.
    """
    if not left_out:
        return ""
    return " Left out: " + "; ".join(f"{code} ({facts.put(why)})" for code, why in left_out) + "."


def reject_text(
    message: str, brief: DesignBrief, facts: Facts, cop_claim: Optional[float] = None
) -> str:
    """Return the reply to a request to skip the simulator or the checks.

    Parameters
    ----------
    message : str
        The user's message (to see which claims it makes).
    brief : DesignBrief
        The brief (heating supply temperature for the Carnot limit).
    facts : Facts
        Number register.
    cop_claim : float, optional
        A COP the message asked to report.

    Returns
    -------
    str
        Why the request is declined, with the physics behind it.
    """
    supply = brief.heating.supply_c if brief.heating else 70.0
    source = 30.0
    limit = carnot_cop(supply, source)
    real = 0.42 * limit
    text = (
        "I can't do that: every number I report comes from the simulator and passes the "
        "physics checks."
    )
    if cop_claim is not None or re.search(r"\bCOP\b|heat[- ]?pump", message, re.IGNORECASE):
        text += (
            f" A heat pump taking heat at {facts.put(num(source))} °C and delivering "
            f"{facts.put(num(supply))} °C cannot beat a COP of {facts.put(num(limit))} "
            f"(the Carnot limit); real machines reach about {facts.put(num(real))}, which is "
            "what the model uses."
        )
    if re.search(r"absorption|cooling tower|koeltoren", message, re.IGNORECASE):
        text += (
            " An absorption chiller has to reject its driving heat as well as the heat it "
            "removes, so it always needs a cooling tower or dry cooler."
        )
    return text


def clarify_text(questions: Sequence[Question], language: str) -> str:
    """Return the line above the clarifying question card.

    Parameters
    ----------
    questions : sequence of Question
        The items being asked.
    language : str
        ``"en"`` or ``"nl"``.

    Returns
    -------
    str
        One sentence.
    """
    n = len(questions)
    no_default = sum(1 for q in questions if q.default is None)
    if language == "nl":
        text = f"Voordat ik ontwerp, heb ik {n} gegeven{'s' if n > 1 else ''} nodig."
        return text + (
            " Elk heeft een voorstel: neem het over of pas het aan."
            if not no_default
            else f" Voor {no_default} is er geen veilige standaardwaarde."
        )
    text = f"Before I design, I need {n} input{'s' if n > 1 else ''}."
    if no_default:
        return text + f" {no_default} {'has' if no_default == 1 else 'have'} no safe default."
    return text + " Each has a proposed default: accept it or change it."


def infeasible_text(
    best: LedgerEntry, options: Sequence[Tuple[str, LedgerEntry]], facts: Facts
) -> str:
    """Return the answer when no design meets the brief, with options that would.

    Parameters
    ----------
    best : LedgerEntry
        The closest design under the user's limits.
    options : sequence of (str, LedgerEntry)
        Relaxed designs and their labels.
    facts : Facts
        Number register.

    Returns
    -------
    str
        The shortfall, why, and the options.
    """
    y, b = best.year, best.brief
    need = facts.put(pct(b.min_heat_coverage))
    limits = []
    names = {"heat_pump": "heat pumps", "boiler": "boilers", "chiller": "chillers"}
    if b.excluded:
        items = [names[x] for x in b.excluded]
        limits.append(
            "no " + (", ".join(items[:-1]) + " or " + items[-1] if len(items) > 1 else items[0])
        )
    limit_text = f" with {', '.join(limits)}" if limits else ""
    short = max(0.0, y.heat_demand_gwh - y.heat_delivered_gwh)
    if best.alternative.rounds:  # the challenge: every cap, every day
        if b.n_doublets:
            limits.insert(0, f"{facts.put(str(b.n_doublets))} doublet(s)")
            limit_text = f" with {', '.join(limits)}"
        text = f"No design meets every cap on every day of the year{limit_text}."
        if y.violations:
            text += f" The closest one breaks this: {facts.put(y.violations[0])}"
        text += (
            f" The {facts.put(best.alternative.name)} covers "
            f"{facts.put(pct(y.heat_coverage))} of the heat, {facts.put(num(short))} GWh a year "
            "short."
        )
    else:
        text = (
            f"No design meets {need} of the heat{limit_text}. "
            f"The {facts.put(best.alternative.name)} covers "
            f"{facts.put(pct(y.heat_coverage))} of the heat, {facts.put(num(short))} GWh a "
            "year short."
        )
    supply = b.heating.supply_c if b.heating else 70.0
    if 0 < best.alternative.depth_m and y.wellhead_c < supply + 5:
        text += (
            f" Its brine reaches only {facts.put(num(y.wellhead_c))} °C at the wellhead, below "
            f"the {facts.put(num(supply))} °C the network needs."
        )
    if options:
        text += " Options:"
        for label, opt in options:
            text += f" {facts.put(label)}: " + option_summary(opt, facts) + "."
    return text


def option_summary(entry: LedgerEntry, facts: Facts) -> str:
    """Return "97% of the heat at 44 €/MWh" for an option (or "no heat" when it gives none)."""
    if entry.year.heat_delivered_gwh <= 0:
        return "no heat at all"
    return (
        f"{facts.put(pct(entry.year.heat_coverage))} of the heat at "
        f"{facts.put(num(entry.economics.lcoh_eur_per_mwh))} €/MWh"
    )


def decision_question(
    options: Sequence[Tuple[str, LedgerEntry]], keep: str, recommended: str, language: str
) -> Question:
    """Return the mid-run question that lets the user pick how to go on when nothing fits.

    Parameters
    ----------
    options : sequence of (str, LedgerEntry)
        The simulated options and their labels.
    keep : str
        The label of the choice to keep the user's limits.
    recommended : str
        The label proposed as the default.
    language : str
        ``"en"`` or ``"nl"``.

    Returns
    -------
    Question
        One required multiple-choice question.
    """
    facts = Facts()
    choices = [f"{label} ({option_summary(e, facts)})" for label, e in options] + [keep]
    default = next((c for c in choices if c.startswith(recommended)), keep)
    if language == "nl":
        label, hint = (
            "Hoe wil je verder?",
            "Ik simuleer de gekozen optie volledig en controleer hem.",
        )
    else:
        label, hint = "How should I go on?", "I'll run the full checks on the option you pick."
    return Question(id="decision", label=label, hint=hint, options=choices, default=default)


def chosen_text(entry: LedgerEntry, facts: Facts, need: Optional[float] = None) -> str:
    """Return the answer after the user picked an option (``need``: the coverage asked for)."""
    text = f"You chose the {facts.put(entry.alternative.name)}. " + design_answer(entry, [], facts)
    if need is not None and entry.year.heat_coverage < need - 1e-6:
        text += (
            f" That is below the {facts.put(pct(need))} of the heat you asked for; the rest "
            "would have to come from outside this system."
        )
    return text


# A root finder or solver that found no answer: the plant model could not balance the wells.
NO_SOLUTION = re.compile(
    r"different signs|converge|no solution|iteration|singular|nan|not finite|root", re.I
)


def search_failed_text(error: str, brief: DesignBrief, what: str = "search") -> str:
    """Return why a design could not be made, in plain words, and what to change on the card.

    Ali, 3 Nov: "sometimes the system cannot converge ... it was hard to understand what was
    wrong in the platform or inputs". A solver that finds no answer means the plant model could
    not balance the wells at these inputs: the inputs most likely to blame are named from the
    rules (a rock too tight to flow, a pressure far from hydrostatic, brine too cool), with the
    card's page to change them on; anything else is said as a fault of the model, not the inputs.

    Parameters
    ----------
    error : str
        The tool's error message.
    brief : DesignBrief
        The brief the search ran on.
    what : str
        ``"search"`` (the design search) or ``"wells"`` (GEMINI's well solve).
    """
    from gemini_agent import engine

    rules = engine.rules_for(brief)
    kh = rules.permeability_md * rules.reservoir_thickness_m / 1000.0
    depth = rules.reservoir_depth_m
    hydro = 1.01325 + rules.brine_density_kg_m3 * 9.81 * depth / 1e5
    temp = rules.reservoir_temperature_c()
    causes = []
    if kh < 2.0:
        causes.append(
            f"the rock lets very little brine through: permeability {num(rules.permeability_md)} "
            f"mD × thickness {num(rules.reservoir_thickness_m)} m = {num(kh, 2)} D·m, where a "
            "doublet needs a few D·m (the challenge's aquifer has 20). Change: a higher "
            "permeability or a thicker aquifer (inputs card, Reservoir and wells)"
        )
    if rules.reservoir_pressure_bar < 0.7 * hydro:
        causes.append(
            f"the reservoir pressure, {num(rules.reservoir_pressure_bar)} bar, is far below "
            f"hydrostatic (about {num(hydro, 0)} bar at {num(depth, 0)} m), so the brine barely "
            "rises in the well. Change: the pressure (Reservoir and wells)"
        )
    if rules.flow_min_m3h > 0.8 * rules.flow_max_m3h:
        causes.append(
            f"the lowest flow, {num(rules.flow_min_m3h)} m³/h, leaves the doublets almost no room "
            f"below the {num(rules.flow_max_m3h)} m³/h cap. Change: a lower lowest flow (Limits)"
        )
    if temp <= rules.heat_return_c:
        causes.append(
            f"the brine, {num(temp)} °C at the producer, is no warmer than the heating return "
            f"({num(rules.heat_return_c)} °C). Change: the gradient or the reservoir's "
            "temperature (Reservoir and wells), or a colder return (Networks)"
        )
    solver = bool(NO_SOLUTION.search(error or ""))
    head = (
        "The plant could not be balanced: the well model found no flow at which the pumps, "
        "the rock and the injection pressure agree"
        if solver
        else (
            "GEMINI's well solve failed"
            if what == "wells"
            else "The design search stopped on an error in the plant model"
        )
    )
    if causes:
        text = f"{head}, so I could not design. Most likely because " + "; and ".join(causes) + "."
    elif solver:
        text = (
            f"{head}, so I could not design. None of the inputs looks out of the ordinary, so "
            "this is likely a limit of the model: try a lower flow cap or another depth, and "
            "tell the team the inputs you used."
        )
    else:
        text = f"{head}, so I could not design. This is a fault of the model, not your inputs."
    return text + f"\n\n_The model said: {error}_" if error else text


def keep_limits_text(best: LedgerEntry, facts: Facts) -> str:
    """Return the answer when the user keeps their limits after a shortfall."""
    return (
        f"I'll keep your limits. The best design under them, the "
        f"{facts.put(best.alternative.name)}, covers {facts.put(pct(best.year.heat_coverage))} of "
        "the heat; the rest would have to come from outside this system."
    )


def about_text(language: str, models: Dict[str, str], facts: Facts) -> str:
    """Return who Dioscuri is, what it does and how (asked "who are you?").

    Parameters
    ----------
    language : str
        ``"en"`` or ``"nl"``.
    models : dict
        ``fast`` and ``reasoning`` model tags.
    facts : Facts
        Number register (model tags contain digits).

    Returns
    -------
    str
        A short self-introduction.
    """
    fast, deep = facts.put(models.get("fast", "")), facts.put(models.get("reasoning", ""))
    if language == "nl":
        return (
            "Ik ben Dioscuri. Ik ontwerp geothermische warmte en koude voor een wijk op TNO's "
            "GEMINI digital twin. Ik lees je vraag, vraag één keer naar wat ontbreekt, simuleer "
            "de opties met fysische modellen, controleer elk ontwerp (energiebalans, Carnot-grens, "
            "temperaturen) en leg de uitkomst uit. Elk getal komt uit een simulatie of van jou. "
            f"Ik draai lokaal: {fast} leest je berichten; in de redeneermodus plant en legt "
            f"{deep} uit."
        )
    return (
        "I'm Dioscuri. I design geothermal heating and cooling for a district on TNO's GEMINI "
        "digital twin. I read your request, ask once for anything missing, simulate the options "
        "with physics tools, check every design (energy balance, the Carnot limit, temperatures) "
        "and explain the result. Every number comes from a simulation or from you, and I can "
        f"look up the project's data. I run locally: {fast} reads your messages, and in "
        f"reasoning mode {deep} plans the study and explains the result."
    )


def same_search_text(last: dict, chosen: LedgerEntry, runner, facts: Facts) -> str:
    """Return the reply when a design search is asked for again with the same inputs.

    It asks what to try instead, so it claims no run: nothing ran for this message (4 Nov:
    "I ran this search already" opened questions that ran nothing).
    """
    a, e = chosen.alternative, chosen.economics
    text = (
        f"Search {last['id']} ({last.get('label', 'the same brief')}) had these inputs "
        f"already, and the same inputs give the same answer: **{a.code}**, {a.name}, at "
        f"{_money(e.lcoh_eur_per_mwh, facts)} of heat. The search is deterministic, so another "
        "attempt only changes something when an input changes."
    )
    if runner is not None:
        r = runner.alternative
        text += (
            f" The runner-up was {r.code} ({r.name}), "
            f"{facts.put(num(runner.economics.lcoe_eur_per_mwh))} €/MWh of heat and cold "
            f"against {facts.put(num(e.lcoe_eur_per_mwh))}."
        )
    return text + " What would you like to try?"


def unreadable_text(message: str, language: str = "en") -> str:
    """Return the reply to a message no request can be read from: what, then a short question.

    The same for every such message (cut off, garbled, a bare number, empty), whichever
    reading found it unreadable; nothing is run or changed for it.
    """
    said = " ".join((message or "").split())
    if len(said) > 80:
        said = said[:79].rsplit(" ", 1)[0] + "…"
    if language == "nl":
        if not said:
            return "Je bericht was leeg. Wat wil je dat ik doe?"
        return f"Ik kon geen vraag of verzoek lezen in “{said}”. Wat wil je dat ik doe?"
    if not said:
        return "Your message was empty. What would you like me to do?"
    return f"I couldn't read a request or a question in “{said}”. What would you like me to do?"


def unconfirmed_text(removed: int, kept: bool) -> str:
    """Return the note shown when the claim check removed most of a reply."""
    if kept:
        return (
            f"_I left out {removed} more statement{'s' if removed != 1 else ''} I couldn't "
            "confirm from the project's data, its documents or my sources._"
        )
    return (
        "I couldn't confirm an answer to that from the project's data, its documents or my "
        "sources, so I won't guess. Ask me to open one of the project's files, or to run a "
        "design, and I'll answer from what that shows."
    )


def greeting_text(language: str, thanks: bool = False) -> str:
    """Return the reply to a greeting or (``thanks``) a thank-you."""
    if language == "nl":
        if thanks:
            return "Graag gedaan. Vraag gerust verder over het ontwerp."
        return (
            "Hallo! Ik ontwerp geothermische warmte en koude voor deze wijk. Waarmee kan ik helpen?"
        )
    if thanks:
        return "You're welcome. Ask me anything else about the design."
    return (
        "Hello! I design geothermal heating and cooling for this district. Ask me to design a "
        "system, compare options or look up a value."
    )


def question_text(
    keys: Sequence[str], sheet: Dict[str, object], facts: Facts, design: str = ""
) -> str:
    """Return the answer to a question about values, one sentence per value.

    Parameters
    ----------
    keys : sequence of str
        The fact keys asked for (``lookup.FACT_KEYS``).
    sheet : dict of str to lookup.Fact
        What is known.
    facts : Facts
        Number register.
    design : str
        Code of the latest design, if there is one (a value it lacks is equipment it has none of).

    Returns
    -------
    str
        The values with their sources, then what isn't known yet and why.
    """
    from gemini_agent.lookup import HEADINGS, LABELS, PROJECT_KEYS

    def name(key: str) -> str:
        return re.sub(r"^the ", "", HEADINGS[key], flags=re.I) if key in HEADINGS else LABELS[key]

    parts, missing = [], []
    for key in dict.fromkeys(keys):  # each value once, in the order asked
        fact = sheet.get(key)
        if fact is None:
            missing.append(key)
            continue
        detail = f" ({facts.put(fact.detail)})" if fact.detail else ""
        source = facts.put(fact.source)
        if key == "operating_days":
            parts.append(f"Each doublet ran: {facts.put(fact.value)}. Source: {source}.")
            continue
        if key in HEADINGS:
            value = str(fact.value).rstrip(" .")
            parts.append(f"{HEADINGS[key]}: {facts.put(value)}{detail}. Source: {source}.")
            continue
        parts.append(f"The {LABELS[key]} is {facts.put(fact.value)}{detail}. Source: {source}.")
    lacking = [k for k in missing if k not in PROJECT_KEYS]
    if lacking and design:
        parts.append(f"Design {design} has no " + ", ".join(name(k) for k in lacking) + ".")
    elif lacking:
        parts.append(
            "I don't have the "
            + ", ".join(name(k) for k in lacking)
            + " yet: no design has been simulated in this conversation. Ask me to design the "
            "system first."
        )
    project = [k for k in missing if k in PROJECT_KEYS]
    if project:
        parts.append(
            "The project data doesn't give the " + ", ".join(name(k) for k in project) + "."
        )
    return " ".join(parts)


def _snippet(text: str, limit: int = 240) -> str:
    """Return the first sentences of a passage, at most ``limit`` characters."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: end + 1] if end > 80 else cut.rsplit(" ", 1)[0]) + " …"


def docs_text(passages: Sequence[object], facts: Facts, attached: bool = False) -> str:
    """Return quotes from the best passages with their sources (flagged passages are skipped).

    Parameters
    ----------
    passages : sequence of docs.Passage
        Search results, best first.
    facts : Facts
        Number register (quoted numbers come from a cited document).
    attached : bool
        The passages come from the user's attached files.

    Returns
    -------
    str
        One or two quotes, or a sentence saying nothing was found.
    """
    usable = [p for p in passages if not p.suspicious][:2]
    if not usable:
        return "I found nothing on that in GEMINI's documentation or the attached files."
    quotes = []
    for p in usable:
        where = facts.put(p.source + (f", {p.section}" if p.section else ""))
        quotes.append(f"“{facts.put(_snippet(p.text))}” ({where})")
    intro = "The attached file says:" if attached else "Here is what the documentation says:"
    return intro + " " + " ".join(quotes)


def file_text(views: Sequence[object], missing: Sequence[str], facts: Facts) -> str:
    """Return what the opened files hold, for when no model writes the reply.

    Parameters
    ----------
    views : sequence of files.FileView
        The files the chat shows.
    missing : sequence of str
        Files the message named that are not on the server.
    facts : Facts
        Number register (the views' values are registered here).

    Returns
    -------
    str
        One or two sentences per file: its size and span, the range of its first measured
        column and its total.
    """
    from gemini_agent.files import fmt

    out = []
    for v in views:
        if v.kind == "image":
            out.append(f"Here is {v.name}.")
            continue
        if not v.table:
            out.append(f"Here is the start of {v.name}." if v.text else f"{v.name} has no preview.")
            continue
        line = f"{v.name} has {v.table['total_rows']} rows"
        if v.span:
            line += f", from {v.span[0]} to {v.span[1]}"
        line += "."
        if v.stats:
            st = v.stats[0]
            unit = f" {st['unit']}" if st["unit"] else ""
            line += (
                f" {st['column']} runs from {fmt(st['min'])} to {fmt(st['max'])}{unit} "
                f"(mean {fmt(st['mean'])}{unit})."
            )
        for t in v.totals[:1]:
            line += f" Over the file that is {fmt(t['value'])} {t['unit']}."
        if v.note:
            line += f" {v.note}"
        out.append(line)
    for name in missing:
        out.append(f"{name} is listed in the project, but the file is not on the server.")
    text = " ".join(out) or "There is no file to show."
    facts.put(text)
    return text


def injection_text(passages: Sequence[object]) -> str:
    """Return the warning for documents that contain instruction-like text."""
    names = ", ".join(sorted({p.source for p in passages if p.suspicious}))
    return (
        f" Note: {names} contains text that reads like instructions to me. I treated it as "
        "data and did not follow it."
    )


GENERATE = {
    "en": ("Yes, write and test the model", "No, answer without it"),
    "nl": ("Ja, schrijf en test het model", "Nee, antwoord zonder"),
}
APPROVE = {"en": ("Approve and use it", "Reject it"), "nl": ("Goedkeuren en gebruiken", "Afwijzen")}
_UNIT_SUFFIX = re.compile(r"_(c|mw|mwh|gwh|m|kw)$")


def attempts(n: int) -> str:
    """Return ``"1 attempt"`` or ``"3 attempts"``."""
    return f"{n} attempt" + ("" if n == 1 else "s")


def article(noun: str) -> str:
    """Return ``"an"`` before a vowel sound and ``"a"`` otherwise (``an adsorption chiller``)."""
    return "an" if noun[:1].lower() in "aeiou" else "a"


def _quantity(name: str) -> str:
    """Return a field name as words, without its unit suffix (``drive_temp_c`` -> drive temp)."""
    return _UNIT_SUFFIX.sub("", name).replace("_", " ")


def _value(x: float, unit: str, facts: Facts) -> str:
    """Return ``"0.48 MW"``, or a bare number for a ratio, registered in ``facts``."""
    text = num(x, 2)
    return facts.put(text if unit in ("-", "") else f"{text} {unit}")


def generated_failed_text(spec, result, facts: Facts) -> str:
    """Return the answer when no generated model passed its checks."""
    last = result.attempts[-1] if result.attempts else None
    problems = "; ".join(last.problems()[:3]) if last else "no reply"
    return (
        f"I couldn't get {article(spec.title)} {spec.title.lower()} model that passes its "
        "checks in "
        f"{facts.put(attempts(len(result.attempts)))}. The last one failed on: "
        f"{facts.put(problems)}. Nothing was saved, and the design stays as it was."
    )


def generated_ready_text(spec, result, facts: Facts) -> str:
    """Return the message that asks the user to approve a generated model."""
    checks = result.checks or []
    passed = sum(1 for c in checks if c.passed)
    tokens = result.tokens
    tokens = sum(tokens.values()) if isinstance(tokens, dict) else tokens
    title = spec.title.lower()
    return (
        f"I wrote {article(title)} {title} model with {facts.put(result.model)} in "
        f"{facts.put(attempts(len(result.attempts)))} ({facts.put(f'{tokens:,}')} "
        f"tokens). In the sandbox it passes {facts.put(str(passed))} of "
        f"{facts.put(str(len(checks)))} checks on {facts.put(str(len(spec.cases)))} reference "
        "cases. The code and the test table are below. Approve it to use it in this design?"
    )


def generated_text(spec, evaluation, facts: Facts) -> str:
    """Return the answer from a registered generated model run at the design's conditions.

    Parameters
    ----------
    spec : ComponentSpec
        What the model computes (inputs and outputs with units).
    evaluation : modelgen.Evaluation
        The model run in the sandbox, with defaults filled and per-case checks.
    facts : Facts
        Number register (every output is a tool number).

    Returns
    -------
    str
        One sentence per operating point, the assumed inputs, the checks and the source.
    """
    units = {q.name: q.unit for q in list(spec.inputs) + list(spec.outputs)}
    parts = []
    for i, (case, out) in enumerate(zip(evaluation.cases, evaluation.outputs)):
        given = [k for k in spec.arguments if k not in evaluation.assumed[i]]
        at = ", ".join(f"{_quantity(k)} {_value(case[k], units[k], facts)}" for k in given)
        gives = ", ".join(
            f"{_quantity(q.name)} {_value(out[q.name], q.unit, facts)}" for q in spec.outputs
        )
        lead = f"With the {spec.title.lower()} model you approved, at" if i == 0 else "At"
        parts.append(f"{lead} {at or 'its default inputs'}: {gives}.")
    assumed = sorted({k for names in evaluation.assumed for k in names})
    if assumed:
        defaults = spec.defaults()
        parts.append(
            "Assumed from the spec's defaults: "
            + ", ".join(f"{_quantity(k)} {_value(defaults[k], units[k], facts)}" for k in assumed)
            + "."
        )
    failed = [c.name for c in evaluation.checks if not c.passed]
    if failed:
        parts.append("Checks that failed at these points: " + "; ".join(failed) + ".")
    else:
        parts.append(f"All {facts.put(str(len(evaluation.checks)))} per-case checks pass.")
    parts.extend(facts.put(w) for w in evaluation.warnings)
    parts.append("Source: the generated model, run in the sandbox (not a GEMINI model).")
    return " ".join(parts)


def generated_must(spec, evaluation) -> List[str]:
    """Return what a reworded generated-model answer must keep (outputs, assumptions, source)."""
    units = {q.name: q.unit for q in list(spec.inputs) + list(spec.outputs)}
    main = spec.outputs[0].name
    keep = [f"{num(out[main], 2)} {units[main]}" for out in evaluation.outputs]
    defaults = spec.defaults()
    for k in sorted({k for names in evaluation.assumed for k in names}):
        keep.append(f"{num(defaults[k], 2)} {units[k]}")
    return list(dict.fromkeys(keep)) + ["generated model"]


def unknown_question_text(sheet: Dict[str, object]) -> str:
    """Return the reply when it is unclear which value a question asks for."""
    from gemini_agent.lookup import LABELS

    known = ", ".join(LABELS[k] for k in list(sheet)[:6])
    return (
        "I couldn't tell which value you mean. I can report, for example: "
        + (known or "the reservoir, the demand and, after a design, its costs and sizes")
        + "."
    )


def key_values(entry: LedgerEntry, behaviour: str) -> List[str]:
    """Return the values an answer about this design must keep when it is reworded.

    A design answer keeps its heat coverage and cost of heat; a shortfall keeps how much heat
    is missing.
    """
    y = entry.year
    if behaviour == "report_infeasible":
        return [f"{num(max(0.0, y.heat_demand_gwh - y.heat_delivered_gwh))} GWh"]
    return [pct(y.heat_coverage), f"{num(entry.economics.lcoh_eur_per_mwh)} €/MWh"]


def checks_summary(entry: LedgerEntry) -> List[dict]:
    """Return the verifier checks of a design as plain dicts for the UI."""
    return [c.model_dump() for c in entry.verification.checks]


# ------------------------------------------------------------------ the challenge's designs

CHALLENGE_SUGGESTIONS = [
    "What if the heating return were 50 °C?",
    "Which design has the lowest CO₂?",
    "Why not two injectors per doublet?",
]


def challenge_suggestions(entry: Optional[LedgerEntry]) -> List[str]:
    """Return follow-up questions that fit the design just shown."""
    if entry is None:
        return list(CHALLENGE_SUGGESTIONS)
    a = entry.alternative
    cold = (
        "Why absorption and not only electric chillers?"
        if a.sizes_mw.get("absorption")
        else "Why electric chillers and not absorption?"
    )
    wells = (
        "Why not a separate treatment train per doublet?"
        if a.n_doublets > 1
        else "Why not two injectors?"
    )
    return ["What if the heating return were 50 °C?", cold, wells]


TOPUP_WORDS = {"heat_pump": "a heat pump on the brine", "boiler": "a gas boiler"}


def _money(x: Optional[float], facts: Facts) -> str:
    return facts.put(f"{num(x)} €/MWh") if x is not None else "n/a"


def challenge_answer(outcome, facts: Facts) -> str:
    """Return the draft reply for a search: one design, how the agent got there, assumptions.

    Parameters
    ----------
    outcome : engine.Outcome
        The search with its chosen design (not None).
    facts : Facts
        Number register.

    Returns
    -------
    str
        A short Markdown answer: the pick, the search, the runner-up, the lowest-CO₂ option and
        the assumptions.
    """
    from gemini_agent import engine

    best = outcome.chosen
    e, a = best.economics, best.alternative
    s = engine.summary(outcome)
    checks = len(best.verification.checks)
    passed = sum(c.passed for c in best.verification.checks)
    failed = [c.name for c in best.verification.checks if not c.passed]
    verdict = (
        f"passes all {facts.put(str(checks))} checks"
        if not failed
        else f"passes {facts.put(str(passed))} of {facts.put(str(checks))} checks (fails: "
        + "; ".join(failed)
        + ")"
    )
    year = "2027" if best.brief.project_id == "challenge" else "the year"
    cold = best.year.cool_demand_gwh > 0  # a user's district may have no cooling demand
    heat_at = facts.put(f"{num(outcome.rules.heat_supply_c)} °C")
    prices = engine.prices_for(None, best.brief)
    long_term = f"{facts.put(num(prices.carbon_long_term_eur_per_t, 0))} €/t"
    why = {
        # The rule as ``engine.pick_entries`` applies it, the flaring step included.
        "best": "the best overall: a reliable plan (any one unit can be out and every day is "
        f"still met) and, of those, the cheapest when CO₂ counts at {long_term} (the long-term "
        "price), unless that plan flares more than "
        f"{facts.put(num(engine.FLARE_ROUTINE_GWH))} GWh of the brine's gas a year (routine "
        "flaring needs consent): then the cheapest plan that flares at most that, if one costs "
        f"at most {facts.put(pct(engine.FLARE_MARGIN))} more on that measure",
        "cost": "the cheapest for heat and cold together",
        "co2": "the lowest CO₂ (the cheapest within 2 % of the least)",
        "reliable": "the cheapest reliable plan: any one unit can be out and every day is "
        "still met; of those plans, the cheapest",
        "green_reliable": "the greenest reliable plan: any one unit can be out and every day is "
        "still met; of those plans, the least CO₂ (the cheapest within 2 %)",
        "gas_free": "the cheapest design that buys no gas: heat pumps for the heat, an electric "
        "boiler for the peaks and as backup",
    }[outcome.objective]
    if outcome.objective == "best" and not a.reliable:  # ``pick_entries``: no plan holds
        why = (
            "the best overall: no reliable plan (any one unit out and every day still met) "
            "meets every cap, so the cheapest for heat and cold together"
        )
    text = f"I recommend **{a.name}** ({design_id(best)}), {why}."
    passed = (
        engine.flaring_passed_over(outcome.candidates, best, prices, best.brief.min_co2_saving)
        if outcome.objective == "best"
        else None
    )
    if passed is not None:  # the flaring step changed the pick: say which plan it set aside
        text += (
            f" The flaring rule decided it: {design_id(passed)} costs "
            f"{_money(engine.shadow_cost(passed, prices), facts)} with CO₂ at {long_term} "
            f"against {_money(engine.shadow_cost(best, prices), facts)} for this one, but flares "
            f"{facts.put(num(passed.year.produced_gas_flared_gwh))} GWh of the brine's gas a "
            "year, which needs consent (Mijnbouwbesluit, art. 38); this one flares "
            f"{facts.put(num(best.year.produced_gas_flared_gwh))} GWh."
        )
    if cold:
        text += (
            f" It meets heat at {heat_at} "
            f"and cold at {facts.put(f'{num(outcome.rules.cool_supply_c)} °C')} every day of "
            f"{year} for {_money(e.lcoe_eur_per_mwh, facts)} of heat and cold together "
            f"(heat {_money(e.lcoh_eur_per_mwh, facts)}, "
            f"cold {_money(e.lcoc_eur_per_mwh, facts)}), "
            f"with {facts.put(pct(e.co2_saving_vs_gas))} less CO₂ than gas boilers and electric "
            f"chillers, and {verdict}."
        )
    else:
        text += (
            f" It meets heat at {heat_at} "
            f"every day of {year} for {_money(e.lcoh_eur_per_mwh, facts)} of heat (the project "
            f"has no cooling demand), with {facts.put(pct(e.co2_saving_vs_gas))} less CO₂ than "
            f"gas boilers, and {verdict}."
        )
    y = best.year
    heat = y.heat_delivered_gwh or 1.0
    split = y.heat_split_gwh
    text += (
        f" Its heat: the geothermal exchanger {facts.put(pct(split.get('geo', 0) / heat))}, the "
        f"heat pump {facts.put(pct(split.get('hp', 0) / heat))}, the gas boiler "
        f"{facts.put(pct(split.get('boiler', 0) / heat))} (it burns the produced gas first and "
        f"buys {facts.put(num(y.purchased_gas_gwh))} GWh of gas a year)."
    )
    rules = outcome.rules
    shown = [facts.put(num(d, 0)) for d in s["depths"] if d > 0]
    depths = (", ".join(shown[:-1]) + " and " + shown[-1] if len(shown) > 1 else shown[0]) + " m"
    known_only = all(abs(d - rules.reservoir_depth_m) < 1e-6 for d in s["depths"] if d > 0)
    where = f"in the known aquifer at {depths}" if known_only else f"in aquifers at {depths}"
    text += (
        f"\n\nI tried {facts.put(str(s['layouts']))} plant layouts (1 to 3 doublets {where}, "
        f"a heat pump or a boiler to reach {heat_at}"
        + (", absorption or electric chillers" if cold else "")
        + ", doublets sharing the brine equally or the hottest first), sized each several "
        f"ways ({facts.put(num(s['sizings'], 0))} sizings, {facts.put(num(s['years'], 0))} "
        "simulated years) on GEMINI's well solve and our plant model, then tried "
        f"{facts.put(str(s['variants']))} variants of the best three: two injectors per doublet, "
        "a treatment train per doublet, wells open over half the aquifer."
    )
    if s["improved"]:
        text += (
            f" {facts.put(str(s['improved']))} layouts broke a cap at first (a day short of heat "
            "or cold) and were enlarged until every day was met."
        )
    if s["failed"]:
        text += f" {facts.put(str(s['failed']))} could not meet every cap and were dropped."
    line = lineage(a.code, outcome.tried)
    variants = [
        x
        for x in outcome.tried
        if x.alternative.stage == 2 and x.alternative.parent in line and x.alternative.reason
    ]
    if variants:
        # Each against its own layout: the pick may add a plant option and the N-1 plan to it
        # (1D-HP-EC@3000-N1-FC; its variants are of 1D-HP-EC@3000).
        root = variants[0].alternative.parent
        ref = next((x for x in outcome.tried if x.alternative.code == root), best)
        text += (
            f" Against its layout {ref.alternative.code}: "
            + "; ".join(f"{x.alternative.code} {_variant_gap(x, ref, facts)}" for x in variants[:3])
            + "."
        )
    plans = [x for x in outcome.tried if x.alternative.reliable]
    if plans:
        text += (
            f" {facts.put(str(len(plans)))} layouts (the cheapest, the best of each doublet count "
            "and the lowest-CO₂ one) were "
            "also sized as reliable plans: the boiler and the chillers as equal units, grown "
            "until any one unit out (a doublet, a treatment train, the exchanger, the heat pump, "
            "a boiler or chiller unit) leaves every day met."
        )
    text += "\n\n" + picks_text(outcome, facts)
    returns = f"{facts.put(f'{num(rules.heat_return_c)} °C')} for heating" + (
        f" and {facts.put(f'{num(rules.cool_return_c)} °C')} for cooling" if cold else ""
    )
    days = f"at most {facts.put(str(rules.operating_days))} operating days per doublet"
    challenge = best.brief.project_id == "challenge"
    if challenge:
        text += (
            f"\n\nAssumed: network returns of {returns} (not given; the Sensitivity tab shows "
            f"their effect), and {days}."
        )
        if known_only:
            text += (
                " The wells stay in the 100 m aquifer the requirements describe; a deeper "
                "aquifer is only an assumption, which I try when you ask for it."
            )
    else:  # a user's project states its networks
        text += (
            f"\n\nThe project's network returns are {returns} (the Sensitivity tab shows their "
            f"effect); the challenge's caps hold, with {days}."
        )
    off = sorted({d for d in _depths(best) if abs(d - rules.reservoir_depth_m) > 1e-6})
    if a.depth_m and off:  # any doublet away from the known aquifer
        known = num(rules.reservoir_depth_m, 0)
        reach = _and([facts.put(num(d, 0)) for d in off]) + " m"
        temps = _and([facts.put(num(rules.reservoir_temperature_c(d))) for d in off]) + " °C"
        text += (
            f"\n\n**Note the depth:** the known aquifer is at {known} m "
            f"({facts.put(f'{num(rules.reservoir_temperature_c())} °C')}); this design's wells "
            f"reach {reach} and assume the same aquifer there, {temps} by the "
            f"gradient and hydrostatic pressure"
            + (", as the requirements allow." if challenge else ".")
        )
        k, same = at_known_aquifer(outcome, best, rules.reservoir_depth_m)
        if k is not None:
            gap = k.economics.lcoe_eur_per_mwh - e.lcoe_eur_per_mwh
            what = "the cheapest reliable plan" if same else "the cheapest design"
            caveat = ", but it is not sized for one unit out" if a.reliable and not same else ""
            text += (
                f" With every well in the known aquifer, {what} is {design_id(k)} "
                f"({k.alternative.name}) for {_money(k.economics.lcoh_eur_per_mwh, facts)} of "
                f"heat, {facts.put(num(abs(gap)))} €/MWh {'more' if gap >= 0 else 'less'} for "
                f'heat and cold together{caveat}; ask for "wells at {known} m only" to search '
                "there alone."
            )
    return text


def at_known_aquifer(
    outcome, best: LedgerEntry, known_m: float
) -> Tuple[Optional[LedgerEntry], bool]:
    """Return the cheapest design with every well in the known aquifer, and if it is reliable.

    A doublet at 2,500 m and one at 3,500 m is not at the known aquifer. Like with like: for
    a reliable pick, the cheapest reliable plan there when one holds (``True``), else the
    cheapest design there (``False``). ``(None, False)`` when no design keeps to that depth.
    """
    there = [
        x
        for x in outcome.tried
        if x.alternative.role in ("chosen", "candidate")
        and x.alternative.depth_m
        and all(abs(d - known_m) < 1e-6 for d in _depths(x))
    ]
    plans = [x for x in there if x.alternative.reliable] if best.alternative.reliable else []
    pool = plans or there
    if not pool:
        return None, False
    return min(pool, key=lambda x: x.economics.lcoe_eur_per_mwh or 0.0), bool(plans)


def _depths(entry: LedgerEntry) -> List[float]:
    """Return the depth of each of a design's doublets (the first one's for older entries)."""
    a = entry.alternative
    rows = [float(d.get("depth_m") or a.depth_m or 0.0) for d in a.doublets or []]
    return rows or [float(a.depth_m or 0.0)]


def _and(words: Sequence[str]) -> str:
    """Join "a", "b" and "c" as "a, b and c"."""
    return ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else "".join(words)


def picks_text(outcome, facts: Facts) -> str:
    """Return the search's picks in a few lines, each with what sets it apart."""
    from gemini_agent import engine

    lines = []
    best = engine.picked(outcome, "best")
    prices = engine.prices_for(None, best.brief) if best is not None else None
    passed = (
        engine.flaring_passed_over(outcome.candidates, best, prices, best.brief.min_co2_saving)
        if best is not None
        else None
    )
    for key in engine.PICKS:
        x = engine.picked(outcome, key)
        if x is None:
            continue
        ex = x.economics
        cost = f"{_money(ex.lcoe_eur_per_mwh, facts)} for heat and cold"
        if prices is not None and (key == "best" or x is passed):
            # The best-overall measure, where it is compared: the pick and the plan it passed.
            cost += (
                f" ({facts.put(num(engine.shadow_cost(x, prices)))} with CO₂ at "
                f"{facts.put(num(prices.carbon_long_term_eur_per_t, 0))} €/t)"
            )
        bits = [
            cost,
            f"{facts.put(num(ex.co2_t_per_year, 0))} t CO₂ a year",
            f"{facts.put(num(ex.capex_meur))} M€ of capital",
        ]
        if not x.alternative.reliable:
            worst = engine.worst_outage(x)
            bits.append(
                "not sized for one unit out" + (f" ({worst.lstrip(': ')})" if worst else "")
            )
        else:
            bits.append("any one unit can be out")
        flared = x.year.produced_gas_flared_gwh or 0.0
        if flared > engine.FLARE_ROUTINE_GWH:
            bits.append(
                f"flares {facts.put(num(flared))} GWh of the brine's gas a year (routine "
                "flaring needs consent)" + (", so not the best overall" if x is passed else "")
            )
        mark = " (recommended)" if x.alternative.role == "chosen" else ""
        lines.append(
            f"- **{engine.PICK_NAMES[key].capitalize()}**{mark}: {design_id(x)}, " + ", ".join(bits)
        )
    return "The picks:\n" + "\n".join(lines) if lines else ""


def lineage(code: str, entries: Sequence[LedgerEntry]) -> set:
    """Return a design's code and its parents' among ``entries`` (the search's designs).

    A pick such as 1D-HP-EC@3000-N1-FC is a plant option of an N-1 plan of the layout
    1D-HP-EC@3000; the variants of the search (two injectors, ...) are of that layout.
    """
    parents = {e.alternative.code: e.alternative.parent for e in entries}
    out: set = set()
    while code and code not in out:
        out.add(code)
        code = parents.get(code, "")
    return out


def _variant_gap(x: LedgerEntry, best: LedgerEntry, facts: Facts) -> str:
    """Say what a variant of the pick costs more, in a few words."""
    gap = (x.economics.lcoe_eur_per_mwh or 0.0) - (best.economics.lcoe_eur_per_mwh or 0.0)
    flags = set(x.alternative.flags) - set(best.alternative.flags)
    what = {
        "2I": "two injectors",
        "ST": "a treatment train per doublet",
        "PL": "the producer open over the lower half",
        "IL": "the injector open over the lower half",
        "IU": "the injector open over the upper half",
    }
    words = ", ".join(what.get(f, f) for f in sorted(flags)) or "the variant"
    return f"({words}) {facts.put(num(gap))} €/MWh more"


def candidates_payload(outcome) -> dict:
    """Return the search for the chat's "how I got here" card and the Compare tab.

    Parameters
    ----------
    outcome : engine.Outcome
        The search.

    Returns
    -------
    dict
        ``objective``, ``chosen`` (code), ``reference`` and ``candidates``: each with its
        role, the reason it lost, its costs, CO₂, capital, its rounds and the caps it broke.
    """
    from gemini_agent import engine

    def row(x) -> dict:
        a, e, y = x.alternative, x.economics, x.year
        return {
            "code": a.code,
            "uid": a.uid,
            "id": design_id(x),
            "picks": list(a.picks),
            "reliable": a.reliable,
            "name": a.name,
            "role": a.role,
            "reason": a.reason,
            "n_doublets": a.n_doublets,
            "depth_m": a.depth_m,
            "topup": a.topup,
            "cooling": a.cooling,
            "sizes_mw": a.sizes_mw,
            "lcoh": e.lcoh_eur_per_mwh,
            "lcoc": e.lcoc_eur_per_mwh,
            "lcoe": e.lcoe_eur_per_mwh,
            "co2_t": e.co2_t_per_year,
            "co2_saving_pct": round((e.co2_saving_vs_gas or 0.0) * 100, 1),
            "capex_meur": e.capex_meur,
            "rounds": len(a.rounds),
            "changes": [r["change"] for r in a.rounds if r.get("change")],
            "violations": list(y.violations),
            "checks": {
                "passed": sum(c.passed for c in x.verification.checks),
                "total": len(x.verification.checks),
            },
        }

    ref = outcome.reference
    return {
        "objective": outcome.objective,
        "chosen": outcome.chosen.alternative.code if outcome.chosen else None,
        "picks": dict(getattr(outcome, "picks", {}) or {}),
        "reference": row(ref),
        "candidates": [row(x) for x in engine.ranked(outcome)],
        "summary": engine.summary(outcome),
        "notes": outcome.notes,
    }


def compare_challenge(outcome, facts: Facts, by: str = "depth") -> str:
    """Return the draft reply for a comparison: the best design for each option compared.

    Parameters
    ----------
    outcome : engine.Outcome
        The search over the options the user named.
    facts : Facts
        Number register.
    by : {"depth", "doublets"}
        What the user compared.

    Returns
    -------
    str
        One line per option (its best design and numbers), then which wins and why.
    """
    from gemini_agent import engine

    valid = [e for e in engine.ranked(outcome) if e.alternative.role in ("chosen", "candidate")]
    groups = {}
    for e in valid:
        key = e.alternative.depth_m if by == "depth" else e.alternative.n_doublets
        groups.setdefault(key, e)  # ranked: the first is the group's best
    label = (lambda k: f"{num(k, 0)} m") if by == "depth" else (lambda k: f"{k} doublet(s)")
    lines = []
    for key, e in sorted(groups.items()):
        ec = e.economics
        lines.append(
            f"- **{facts.put(label(key))}**: best is {e.alternative.code} ({e.alternative.name}), "
            f"{_money(ec.lcoh_eur_per_mwh, facts)} for heat, {_money(ec.lcoc_eur_per_mwh, facts)} "
            f"for cold, {facts.put(pct(ec.co2_saving_vs_gas))} less CO₂ than gas."
        )
    text = "\n".join(lines) if lines else "None of the options meets every cap."
    if outcome.chosen is not None and len(groups) > 1:
        best = outcome.chosen
        key = best.alternative.depth_m if by == "depth" else best.alternative.n_doublets
        others = [g for k, g in groups.items() if k != key]
        gap = min(o.economics.lcoe_eur_per_mwh for o in others) - best.economics.lcoe_eur_per_mwh
        text += (
            f"\n\n{facts.put(label(key))} wins: {facts.put(num(gap))} €/MWh cheaper for heat "
            "and cold together. Its brine reaches "
            f"{facts.put(f'{num(best.year.wellhead_c)} °C')} at the wellhead, which sets how much "
            "heat comes straight from the exchanger."
        )
    return text


# ------------------------------------------------------------------ inputs to confirm

RUN_OPTION = "Run the design with these inputs"
CHANGE_OPTION = "Change an input first"
# The card's "Reset to defaults" button (5 Nov): the inputs back to the project's own values.
RESET_OPTION = "Reset the inputs to the defaults"
KINDS = {
    "data": "read from the files",
    "fixed": "fixed by the requirements",
    "derived": "worked out by Dioscuri",
    "assumed": "Dioscuri's assumption",
    "asked": "your request",
}


ROW_OF_KEY = {
    "heat_supply_c": "Heating network",
    "heat_return_c": "Heating network",
    "cool_supply_c": "Cooling network",
    "cool_return_c": "Cooling network",
    "electricity_eur_per_mwh": "Prices",
    "gas_eur_per_mwh": "Prices",
    "carbon_eur_per_t": "Prices",
    "discount_rate": "Prices",
    "heat_demand_scale": "Scaled",
    "cool_demand_scale": "Scaled",
    "aquifer_depths_m": "Aquifers",
    "aquifers": "Aquifers",
    "doublet_stops": "Doublet stops",
    # The brine's properties (the inputs card's own): their rows, not "Design for".
    "brine_density_kg_m3": "Brine",
    "brine_viscosity_pa_s": "Brine",
    "gas_ch4_fraction": "Brine",
    "gas_co2_fraction": "Brine",
    "brine_cp_j_kg_k": "Heat capacity",
}


def changed_rows(keys: Sequence[str]) -> List[str]:
    """Return the inputs card's rows a set of changed parameters touches."""
    return sorted({ROW_OF_KEY.get(k, "Design for") for k in keys})


def inputs_rows(project, brief: DesignBrief) -> List[Dict[str, str]]:
    """Return what a design will use, row by row, each with where it comes from.

    Shown before the first design of a conversation, so the user confirms what was read from
    the project's files and what is assumed.

    Parameters
    ----------
    project : ProjectData
        The project (its files, its reservoir).
    brief : DesignBrief
        The request as read (with any changes the user asked for).

    Returns
    -------
    list of dict
        ``group``, ``label``, ``value``, ``source`` and ``kind`` (see ``KINDS``) per row.
    """
    from dioscuri_plant import Prices
    from gemini_agent import engine, projects

    rows: List[Dict[str, str]] = []
    challenge = project.id == projects.CHALLENGE
    pdf = next((f for f in project.files if f.lower().endswith(".pdf")), "the requirements")
    # A real project built in (Trias Westland, HAL Leyweg): its published sources per figure.
    cited = (projects.BUILTINS.get(project.id) or {}).get("sources") or {}

    def row(group, label, value, source, kind, key=None):
        if key in cited:
            source, kind = cited[key]
        rows.append(
            {"group": group, "label": label, "value": value, "source": source, "kind": kind}
        )

    d = engine.demand_summary(project.id)
    heat_file = next((f for f in project.files if "heat" in f.lower()), d["source"])
    cool_file = next((f for f in project.files if "cool" in f.lower()), d["source"])
    row(
        "Demand",
        "Heat",
        f"{num(d['annual_heat_gwh'], 2)} GWh a year, peak {num(d['peak_heat_mw'])} MW on "
        f"{d['peak_heat_day']}",
        heat_file,
        "data",
        "demand",
    )
    if d["annual_cool_gwh"]:
        row(
            "Demand",
            "Cold",
            f"{num(d['annual_cool_gwh'], 2)} GWh a year, peak {num(d['peak_cool_mw'])} MW on "
            f"{d['peak_cool_day']}",
            cool_file,
            "data",
        )
    scale = brief.demand_scale or [1.0, 1.0]
    if any(abs(x - 1.0) > 1e-9 for x in scale):
        row("Demand", "Scaled", f"heat ×{scale[0]:g}, cold ×{scale[1]:g}", "you", "asked")

    rules = engine.rules_for(brief)
    where = f"{pdf}, section 3.1" if challenge else f"project {project.name}, as entered"
    row(
        "Reservoir",
        "Aquifer",
        f"midpoint {num(rules.reservoir_depth_m, 0)} m TVD, {num(rules.reservoir_thickness_m)} m "
        f"thick, {num(rules.permeability_md)} mD, {num(rules.reservoir_pressure_bar)} bar",
        where,
        "fixed" if challenge else "data",
        "reservoir",
    )
    row(
        "Reservoir",
        "Temperature",
        f"{num(rules.reservoir_temperature_c())} °C = {num(rules.surface_temperature_c)} °C + "
        f"{num(rules.gradient_c_per_km)} °C/km × {num(rules.reservoir_depth_m / 1000, 2)} km",
        f"from the gradient in {where}" if challenge else where,
        "derived" if challenge else "data",
        "reservoir",
    )
    # Every aquifer the wells may be drilled into, each with its own rock and gas (the card's
    # records field, ``aquifers.card_field``); it replaced "Wells drilled into" and "Second
    # aquifer" (4 Nov).
    from gemini_agent import aquifers

    row("Reservoir", "Aquifers", *aquifers.row_words(brief, rules, challenge))
    # The gas-liquid ratio is each aquifer's: said so when they differ.
    ratios = {float(a["gas_liquid_ratio"]) for a in aquifers.resolved(brief, rules)}
    glr = (
        f"gas {num(rules.gas_liquid_ratio)} Nm³/m³"
        if ratios <= {float(rules.gas_liquid_ratio)}
        else "gas " + ", ".join(f"{num(x)}" for x in sorted(ratios)) + " Nm³/m³ by aquifer"
    )
    row(
        "Brine and gas",
        "Brine",
        f"{num(rules.brine_density_kg_m3, 0)} kg/m³, {num(rules.brine_viscosity_pa_s * 1000, 2)} "
        f"mPa·s; {glr}, {pct(rules.gas_ch4_fraction)} CH₄ / "
        f"{pct(rules.gas_co2_fraction)} CO₂",
        f"{pdf}, section 3.2" if challenge else where,
        "fixed" if challenge else "data",
        "brine",
    )
    cp_mine = "brine_cp_j_kg_k" in (brief.rules or {})
    row(
        "Brine and gas",
        "Heat capacity",
        f"{num(rules.brine_cp_j_kg_k, 0)} J/(kg·K)",
        (
            "you"
            if cp_mine
            else "not given; Sharqawy, Lienhard & Zubair 2010 for brine of 1,030 kg/m³"
        ),
        "asked" if cp_mine else "assumed",
        None if cp_mine else "heat_capacity",
    )
    caps = engine.project_caps(brief)
    relaxed = [
        f"{label} {getattr(rules, key):g} (cap {getattr(caps, key):g})"
        for key, label in (
            ("flow_min_m3h", "minimum flow"),
            ("flow_max_m3h", "maximum flow"),
            ("max_brine_cooling_k", "brine cooling"),
            ("operating_days", "operating days"),
        )
        if getattr(rules, key) != getattr(caps, key)
    ]
    if relaxed:
        row(
            "Caps",
            "Relaxed by you",
            "; ".join(relaxed) + ": designs are still checked against the caps",
            "your message",
            "asked",
        )
    row(
        "Caps",
        "Doublets and flow",
        f"1 to 3 doublets; {num(caps.flow_min_m3h, 0)} to {num(caps.flow_max_m3h, 0)} m³/h "
        f"per doublet; brine cooled by at most {num(caps.max_brine_cooling_k, 0)} K; pumps "
        f"{pct(caps.pump_efficiency)}",
        f"{pdf}, 'Design and operating constraints'" if challenge else "the challenge's caps",
        "fixed",
        "caps",
    )
    row(
        "Caps",
        "Operating days",
        f"at most {caps.operating_days} days a year per doublet; the plant serves all 365",
        (
            "the organisers (2 Nov): the geothermal source is available 330 days a year, the "
            "system runs all year"
            if challenge
            else "the requirements' '330 daily steps', read as a cap"
        ),
        "fixed" if challenge else "assumed",
        "operating_days",
    )
    heating = brief.heating or engine.DEFAULT_HEATING
    cooling = brief.cooling or engine.DEFAULT_COOLING
    for label, temps, base in (
        ("Heating network", heating, engine.DEFAULT_HEATING),
        ("Cooling network", cooling, engine.DEFAULT_COOLING),
    ):
        if label == "Cooling network" and not d["annual_cool_gwh"]:
            continue  # no cold to deliver
        # A built-in project's own network, unless the user changed it.
        own = cited and label == "Heating network" and project.heating == temps
        row(
            "Networks",
            label,
            f"supply {num(temps.supply_c)} °C, return {num(temps.return_c)} °C",
            (
                "the supply is fixed by the requirements; the return is not given"
                if temps == base
                else "you"
            ),
            "assumed" if temps == base else "asked",
            "heating" if own else None,
        )
    rules = engine.rules_for(brief)
    km = float(rules.network_length_km or 0.0)
    row(
        "Networks",
        "Network heat losses",
        (
            f"on: a {num(km)} km trunk from the plant to the buildings; the pipes are sized for "
            "the peak, lose heat to the ground (10 °C), and the plant supplies hotter so the "
            "buildings get the supply temperature"
            if km > 0
            else "off: heat and cold are delivered at the plant's gate"
        ),
        "you" if km > 0 else "Dioscuri's default",
        "asked" if km > 0 else "assumed",
    )
    mine = bool(rules.co2_reinjection or rules.flare_brine_gas)
    row(
        "Brine and gas",
        "The brine's gas",
        (
            "all flared (the boiler buys all its gas)"
            if rules.flare_brine_gas
            else "burnt in the boiler first, the rest flared"
        )
        + (
            "; its own CO₂ dissolved back into the injected brine (scrubbed from the separated "
            "gas at pressure; about 25 €/t)"
            if rules.co2_reinjection
            else "; its own CO₂ let out at the separator"
        ),
        "you" if mine else "Dioscuri's default",
        "asked" if mine else "assumed",
    )
    extras = [
        text
        for on, text in (
            (rules.free_cooling, "free cooling on the towers"),
            (rules.grid_by_month, "the grid's CO₂ by month"),
            (rules.solar_mwp, f"{num(rules.solar_mwp)} MWp of solar panels"),
            (
                rules.storage_mwh,
                f"a {num(rules.storage_mwh, 0)} MWh "
                + ("seasonal aquifer store (HT-ATES)" if rules.storage_ates else "hot-water store"),
            ),
        )
        if on
    ]
    row(
        "Plant options",
        "Free cooling, solar, heat store",
        "; ".join(extras) if extras else "none of them",
        "you" if extras else "Dioscuri's default",
        "asked" if extras else "assumed",
    )
    from gemini_agent import stops

    row("Maintenance", "Doublet stops", *stops.row(brief, rules.operating_days))
    words, mine = service_words(rules)
    row(
        "Maintenance",
        "Units' yearly service",
        words,
        "you" if mine else "Dioscuri's default",
        "asked" if mine else "assumed",
    )
    prices = engine.prices_for(None, brief)
    default = Prices()
    changed = [
        k
        for k in ("electricity_eur_per_mwh", "gas_eur_per_mwh", "carbon_eur_per_t", "discount_rate")
        if getattr(prices, k) != getattr(default, k)
    ]
    row(
        "Costs",
        "Prices",
        f"electricity {num(prices.electricity_eur_per_mwh)} €/MWh, gas "
        f"{num(prices.gas_eur_per_mwh)} €/MWh, CO₂ {num(prices.carbon_eur_per_t)} €/t, discount "
        f"rate {pct(prices.discount_rate)}",
        "you" if changed else "Eurostat 2025 (Netherlands), EU ETS 2025, PBL SDE++ 2026",
        "asked" if changed else "assumed",
    )
    ask = [engine.OBJECTIVE_WORDS.get(brief.objective, brief.objective)]
    ask.append(
        f"{len(brief.doublets)} doublets as described"
        if brief.doublets
        else f"{brief.n_doublets} doublet(s)" if brief.n_doublets else "1 to 3 doublets"
    )
    built = engine.built_words(brief)
    if built:
        ask.append(built)
    if brief.excluded:
        ask.append("no " + ", ".join(engine.excluded_names(brief)))
    for key, value in (brief.rules or {}).items():
        if key not in (
            "network_length_km",
            "planned_service",
            "co2_reinjection",
            "flare_brine_gas",
            "free_cooling",
            "grid_by_month",
            "solar_mwp",
            "storage_mwh",
            "storage_ates",
            "stop_days_off",
            "service_plan",
            "stops_relaxed",
            "brine_density_kg_m3",
            "brine_viscosity_pa_s",
            "brine_cp_j_kg_k",
            "gas_ch4_fraction",
            "gas_co2_fraction",
        ):
            # (those have their own rows)
            ask.append(f"{key.replace('_', ' ')} {value:g}")
    row("Your request", "Design for", "; ".join(ask), "your message", "asked")
    return rows


def inputs_text(rows: List[Dict[str, str]]) -> str:
    """Return the inputs to confirm as a short intro and a table (the chat's fallback)."""
    lines = [
        "Before I run the design, please check what I read and what I assume. Run it as it "
        "is, or tell me what to change.",
        "",
        "| Input | Value | From |",
        "|---|---|---|",
    ]
    for r in rows:
        mark = " (assumed)" if r["kind"] == "assumed" else ""
        lines.append(f"| {r['label']} | {r['value']}{mark} | {r['source']} |")
    return "\n".join(lines)


# ------------------------------------------------------------------ verdicts (code's conclusions)


def _against_gas_words(frac: Optional[float]) -> str:
    if frac is None:
        return ""
    p = round(abs(frac) * 100)
    return "the same as gas" if p == 0 else f"{p} % {'cheaper' if frac < 0 else 'dearer'} than gas"


def caps_past(entry: Optional[LedgerEntry], facts: Facts) -> str:
    """Return a line for the hard caps a request let a design go past.

    A request may run a design past the project's caps ("400 m³/h a doublet"); the verifier
    still holds it to the caps and its check says what was asked (``verifier.verify_plant``).
    On 3 Nov a reply to that request said "the cap is respected" under a failed flow check,
    and another said the doublet ran at 400 m³/h when it never passed 300. This line, from the
    checks alone, says which: the cap broken, or kept anyway. Empty when nothing was asked.
    """
    if entry is None:
        return ""
    asked = [
        c
        for c in entry.verification.checks
        if c.requirement and "as you asked, the cap is" in c.detail
    ]
    if not asked:
        return ""
    broken = [c for c in asked if not c.passed]
    kept = [c for c in asked if c.passed]
    out = []
    if broken:
        said = "; ".join(f"{c.name} ({facts.put(c.detail)})" for c in broken)
        out.append(
            f"This design breaks the project's hard cap{'s' if len(broken) > 1 else ''}, as "
            f"asked: {said}. It shows what the change would give; it could not be built under "
            "the challenge's rules."
        )
    if kept:
        said = "; ".join(f"{c.name} ({facts.put(c.detail)})" for c in kept)
        out.append(
            f"You asked to go past the project's cap{'s' if len(kept) > 1 else ''}, but the "
            f"design keeps within {'them' if len(kept) > 1 else 'it'} anyway: {said}."
        )
    return " ".join(out)


def design_verdict(entry: LedgerEntry, facts: Facts) -> str:
    """Return a design's conclusion in one line: what it is, its cost, gas, N-1, CO2."""
    e = entry.economics
    vs = vs_gas(entry) or {}
    firm = firm_view(entry) or {}
    n1 = (
        "any one unit can be out"
        if firm and not firm.get("short")
        else (
            f"one unit out leaves days short in {firm.get('short')} of "
            f"{len(firm.get('cases') or [])} cases"
            if firm
            else ""
        )
    )
    bits = [
        f"{facts.put(num(e.lcoe_eur_per_mwh))} €/MWh of heat and cold"
        + (
            f" ({facts.put(_against_gas_words(vs.get('total')))})"
            if vs.get("total") is not None
            else ""
        ),
        f"{facts.put(pct(e.co2_saving_vs_gas))} less CO₂ than gas",
    ]
    if n1:
        bits.append(facts.put(n1))
    return f"**{design_id(entry)}**: " + "; ".join(bits) + "."


def what_if_verdict(
    base: Optional[LedgerEntry], new: LedgerEntry, research: Optional[dict], facts: Facts
) -> str:
    """Return a what-if's conclusion in one line: the cost under the change, N-1, the pick."""
    if base is None:
        return ""
    label = new.change_label or "the change"
    was, now = base.economics.lcoe_eur_per_mwh, new.economics.lcoe_eur_per_mwh
    text = (
        f"With {label}: {design_id(base)} costs {facts.put(num(now))} €/MWh of heat and cold "
        f"(was {facts.put(num(was))})"
    )
    fb, fn = firm_view(base) or {}, firm_view(new) or {}
    if fb and fn and not fb.get("short") and fn.get("short"):
        text += f"; it is no longer N-1 ({facts.put(str(fn['short']))} one-unit-out cases short)"
    if research:
        if research.get("changed"):
            text += (
                f"; searching again, the pick changes to {research['id']} at "
                f"{facts.put(num(research['lcoe']))} €/MWh"
            )
        else:
            text += f"; searching again, the pick stays ({facts.put(num(research['lcoe']))} €/MWh)"
    return text + "."
