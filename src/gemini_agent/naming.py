"""How runs and designs are named for people: a short handle and words that say what it is.

The handles stay as they are (``A1``: run A's first design; ``W1``: a what-if; ``U1``: yours).
A number like "2.1" would be read as a value by the checks that tie every number of a reply to
a source, so runs are lettered. Each run gets words ("Run B · What-if: 50 °C heating return"),
and each design a label ("Best overall", "A1 + 50 °C heating return", "Rank 7 in run A"), or
the name the user gave it.
"""

from __future__ import annotations

import re
from typing import Optional

PICK_WORDS = {
    "best": "Best overall",
    "cost": "Cheapest",
    "co2": "Lowest CO₂",
    "reliable": "Cheapest reliable",
    "green_reliable": "Greenest reliable",
    "gas_free": "Gas-free",
}
PICK_ORDER = tuple(PICK_WORDS)


def letter(n: int) -> str:
    """Return a run's letter from its number (1-based): A, B ... Z, AA, AB ..."""
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def brief_changes(brief: dict, base: dict) -> dict:
    """Return what a search's brief changed against the first one's, as parameter changes.

    "Design it again with a 50 °C heating return" is {"heat_return_c": 50.0}: its run is named
    by that, not by what best means (both runs were "Best overall" on 2 Nov).
    """
    out: dict = {}
    for side, keys in (("heating", ("heat_supply_c", "heat_return_c")),):
        a, b = brief.get(side) or {}, base.get(side) or {}
        for field, key in zip(("supply_c", "return_c"), keys):
            if a.get(field) is not None and a.get(field) != b.get(field):
                out[key] = a.get(field)
    a, b = brief.get("cooling") or {}, base.get("cooling") or {}
    for field, key in (("supply_c", "cool_supply_c"), ("return_c", "cool_return_c")):
        if a.get(field) is not None and a.get(field) != b.get(field):
            out[key] = a.get(field)
    if brief.get("objective") != base.get("objective"):
        out["objective"] = brief.get("objective")
    if brief.get("n_doublets") != base.get("n_doublets") and brief.get("n_doublets"):
        out["n_doublets"] = brief.get("n_doublets")
    if list(brief.get("doublet_depths_m") or []) != list(base.get("doublet_depths_m") or []):
        if brief.get("doublet_depths_m"):
            out["aquifer_depths_m"] = list(brief["doublet_depths_m"])
    if (brief.get("aquifers") or []) != (base.get("aquifers") or []) and brief.get("aquifers"):
        out["aquifers"] = list(brief["aquifers"])
    if sorted(brief.get("excluded") or []) != sorted(base.get("excluded") or []):
        out["exclude"] = list(brief.get("excluded") or [])
    if (brief.get("reservoir_delta_c") or 0) != (base.get("reservoir_delta_c") or 0):
        out["reservoir_change_k"] = brief.get("reservoir_delta_c") or 0
    rules, rules0 = brief.get("rules") or {}, base.get("rules") or {}
    for key, value in rules.items():
        if rules0.get(key) != value and not isinstance(value, (list, tuple, dict)):
            out[key] = value
    return out


def run_name(search: dict, n: int, first: Optional[dict] = None) -> str:
    """Return a run's name: "Run A · Base case", "Run B · Heating return 50 °C".

    ``first``: the conversation's first search, whose brief a later run is named against.
    """
    label = str(search.get("label") or "")
    if label.startswith("what-if: "):
        words = "What-if: " + label[len("what-if: ") :].split(" · ")[0]
    elif n == 1:
        words = "Base case"
    else:
        words = ""
        if first is not None and search.get("brief") and first.get("brief"):
            from gemini_agent import parameters

            changes = {
                k: v
                for k, v in brief_changes(search["brief"], first["brief"]).items()
                if k in parameters.CATALOGUE
            }
            if changes:
                said = parameters.label(changes)
                words = said[0].upper() + said[1:]
        if not words:
            words = label.split(" · ")[0].capitalize() if label else f"Search {n}"
    return f"Run {letter(n)} · {words}"


def handle_of(design_id: str) -> str:
    """Return a design's handle from its id ("A1 · 1D-HP-EC-N1" → "A1")."""
    return str(design_id).split(" · ")[0].strip()


def design_label(entry, names: Optional[dict] = None) -> str:
    """Return the words that say what a design is, or the user's own name for it."""
    from gemini_agent.reporter import design_id

    names = names or {}
    own = names.get(design_id(entry))
    if own:
        return own
    a = entry.alternative
    parent = handle_of(a.parent) if a.parent else ""
    if a.role == "what_if" or getattr(entry, "change_label", ""):
        change = getattr(entry, "change_label", "") or "a change"
        return f"{parent} + {change}" if parent else f"What-if: {change}"
    if a.role == "user":
        return f"Your design, from {parent}" if parent else "Your design"
    picks = [PICK_WORDS[p] for p in PICK_ORDER if p in (a.picks or [])]
    if picks:
        return " · ".join(picks)
    if getattr(a, "stage", 0) == 2 and parent:
        return f"Variant of {parent}"
    m = re.match(r"([A-Z]+)(\d+)$", a.uid or "")
    if m:
        return f"Rank {m.group(2)} in run {m.group(1)}"
    return a.name
