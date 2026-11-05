"""Follow-up questions under a reply: only questions the evals ask, fitting what was asked.

A suggestion is a click away from a message, so it must work: on 1 Nov the model's own
follow-ups led to refusals ("Can you show the hourly profile?"). Every question here is a
wording of an eval scenario (``hackathon/evals/scenarios``; ``test_suggest`` checks it), so the
suite runs each one. The reply's topic (the values asked for, the figures explained, the kind of
turn) picks the list; the design's own numbers fill it ("Where does the 30 MW of boilers come
from?"); a question the chat already asked is left out. Dutch and German replies get their own
tested questions; other languages keep the model's follow-ups.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from gemini_agent.reporter import num

# The values a reply is about (``lookup`` keys, ``provenance`` figures) and their topic.
TOPICS: Dict[str, str] = {
    **dict.fromkeys(("lcoh", "lcoc", "lcoe", "capex", "cost_split", "investor"), "cost"),
    **dict.fromkeys(("co2_saving", "co2_sources", "gas_flows"), "co2"),
    **dict.fromkeys(
        (
            "boiler_size",
            "chiller_size",
            "heat_pump_size",
            "hex_size",
            "heat_split",
            "electric_boiler_size",
            "absorption_size",
            "heat_pump_cop",
        ),
        "size",
    ),
    **dict.fromkeys(
        (
            "wellhead_temp",
            "reinjection_temp",
            "reservoir_temp",
            "known_rock_temp",
            "well_checks",
            "reservoir_depth",
        ),
        "brine",
    ),
    "operating_days": "maintenance",
    "failure_costs": "reliability",
}

# Per topic, (question, what the design needs for it to make sense). The questions are eval
# wordings, character for character (placeholders as in chat.yaml).
CATALOGUE: Dict[str, List[Tuple[str, str]]] = {
    "design": [
        ("Break the {lcoh} €/MWh down for me.", ""),
        ("What do you mean by N-1?", "reliable"),
        ("Why didn't you pick the cheapest?", "cheapest_differs"),
        ("What if the heating return were 50 degrees?", ""),
    ],
    "cost": [
        ("What share of the yearly cost is gas?", ""),
        ("What is in the {capex} M€ capex?", ""),
        ("What if gas cost 4 ct/kWh?", ""),
        ("What's the cost of heat and cold together?", "cold"),
    ],
    "co2": [
        ("How was the {co2_saving} CO2 saving calculated?", ""),
        ("What about the cheapest one, how much CO2 does it save?", "cheapest_differs"),
        ("What if electricity cost 12 ct/kWh?", ""),
    ],
    "size": [
        ("Where does the {boiler_mw} MW of boilers come from?", "boilers"),
        ("Why is the heat exchanger {hex_mw} MW?", ""),
        ("How much of the heat comes from the gas boiler?", "boilers"),
    ],
    "brine": [
        ("Why does the brine go back at {reinjection} °C?", ""),
        ("How hot is the brine at the wellhead?", ""),
        ("What if the reservoir were 10 K colder?", ""),
    ],
    "maintenance": [
        ("Why is the maintenance stop where it is?", "stops"),
        ("When does the doublet stop?", "stops"),
        ("Can it keep everyone warm if one unit fails?", ""),
    ],
    "reliability": [
        ("Can it keep everyone warm if one unit fails?", ""),
        ("What do you mean by N-1?", "reliable"),
        ("Why didn't you pick the cheapest?", "cheapest_differs"),
    ],
    "what_if": [
        ("What if the heating return were 50 degrees?", ""),
        ("What if the reservoir were 10 K colder?", ""),
        ("What if the heat demand grew by 20%?", ""),
    ],
}
LANGUAGES: Dict[str, List[Tuple[str, str]]] = {
    "nl": [
        ("Wat kost de warmte?", ""),
        ("Waar komt de {boiler_mw} MW van de ketels vandaan?", "boilers"),
        ("Wat als de gasprijs 45 €/MWh is?", ""),
    ],
    "de": [
        ("Was kostet die Wärme?", ""),
        ("Wie viel CO2 spart das Design?", ""),
        ("Was passiert, wenn die Förderpumpe (ESP) ausfällt?", ""),
    ],
}


def values(entry) -> Dict[str, str]:
    """Return a design's figures as the questions write them."""
    y, a, e = entry.year, entry.alternative, entry.economics
    sizes = a.sizes_mw or {}
    return {
        "lcoh": num(e.lcoh_eur_per_mwh),
        "capex": num(e.capex_meur, 0 if e.capex_meur >= 10 else 1),
        "co2_saving": num((e.co2_saving_vs_gas or 0) * 100) + "%",
        "boiler_mw": num(sizes.get("boiler", 0)),
        "hex_mw": num(y.hex_mw, 2),
        "reinjection": num(y.reinjection_c),
    }


def _meets(need: str, entry, session) -> bool:
    a, y = entry.alternative, entry.year
    sizes = a.sizes_mw or {}
    if need == "reliable":
        return bool(a.reliable)
    if need == "boilers":
        return sizes.get("boiler", 0) > 0
    if need == "heat_pump":
        return sizes.get("heat_pump", 0) > 0
    if need == "cold":
        return (y.cool_delivered_gwh or 0) > 0
    if need == "stops":
        return bool(y.stop_ranges and any(y.stop_ranges))
    if need == "cheapest_differs":
        from gemini_agent import reliability

        found, _ = reliability.resolve(["cheapest"], session)
        return bool(found) and found[0] is not entry
    return True


def topics_of(keys: Sequence[str], intent: str = "") -> List[str]:
    """Return a reply's topics, the most specific first: its values', then the turn's kind."""
    out = [TOPICS[k] for k in keys if k in TOPICS]
    if intent in ("what_if", "failure"):
        out.append("what_if" if intent == "what_if" else "reliability")
    out.append("design")
    return list(dict.fromkeys(out))


def pick(
    session,
    entry,
    keys: Sequence[str] = (),
    intent: str = "",
    language: str = "en",
    asked: Sequence[str] = (),
    n: int = 3,
) -> Optional[List[str]]:
    """Return up to ``n`` tested follow-ups for a reply about ``entry``; None: none apply.

    None also for a language without tested questions (the model's follow-ups stay).
    """
    if entry is None:
        return None
    if language in LANGUAGES:
        pool = list(LANGUAGES[language])
    elif language not in ("en", "", None):
        return None
    else:
        pool = [q for t in topics_of(keys, intent) for q in CATALOGUE.get(t, [])]
    figures = values(entry)
    seen = {a.strip().lower() for a in asked if a}
    out: List[str] = []
    for text, need in pool:
        if not _meets(need, entry, session):
            continue
        for key, value in figures.items():
            text = text.replace("{" + key + "}", value)
        if text.lower() in seen or text in out:
            continue
        out.append(text)
        if len(out) == n:
            break
    return out or None
