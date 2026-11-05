"""The aquifers a design's wells can be drilled into: the brief's list, the card's row, the chat.

A project has one known aquifer (its reservoir). The user may describe others, up to three in
all, each with its own midpoint depth, thickness, permeability, pressure and gas-liquid ratio
(``DesignBrief.aquifers``, the first the known one when it is kept). The search puts each doublet
in one of them, as it tried depths before; the plant model gives each doublet its aquifer's
rock, pressure and gas (``dioscuri_plant.Rules.aquifer_at``).

Without a list, the project's depths stand: the known aquifer and, for the challenge, the same
rock assumed 500 and 1,000 m deeper (``projects.depths``); the older ``doublet_depths_m`` and
``second_aquifer_*`` settings map onto the same list (``resolved``). An aquifer the user
describes replaces the assumed ones.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import dioscuri_plant as dp
from gemini_agent.contract import AquiferSpec, DesignBrief

MAX = 3  # aquifers in all
# The card's columns: key, label, unit, low, high, help (plain words).
COLUMNS: Tuple[Tuple[str, str, str, float, float, str], ...] = (
    (
        "depth_m",
        "Depth",
        "m",
        500,
        7000,
        "The middle of the water-bearing layer, measured straight down from the surface. Deeper "
        "brine is hotter (the gradient gives its temperature), but the wells cost more.",
    ),
    (
        "thickness_m",
        "Thickness",
        "m",
        5,
        1000,
        "How thick the water-bearing layer is. A thicker layer lets the brine flow into the "
        "wells more easily, so the pumps need less power.",
    ),
    (
        "permeability_md",
        "Permeability",
        "mD",
        1,
        10000,
        "How easily water flows through the rock, in millidarcy. Higher means the same flow "
        "with less pumping; Dutch geothermal sandstones have about 100 to 1,000 mD.",
    ),
    (
        "pressure_bar",
        "Pressure",
        "bar",
        20,
        800,
        "The water pressure in the layer at its middle. It is usually close to the weight of "
        "the brine above it, about 0.1 bar per metre; it sets how hard the pumps work.",
    ),
    (
        "gas_liquid_ratio",
        "Gas-liquid ratio",
        "Nm³/m³",
        0,
        10,
        "How much gas (mostly methane, some CO₂) comes out of each cubic metre of brine, in "
        "normal cubic metres. More gas means more to burn, sell or flare, and more CO₂.",
    ),
)
KEYS = tuple(c[0] for c in COLUMNS)
NAMES = {c[0]: c[1].lower() for c in COLUMNS}
UNITS = {c[0]: c[2] for c in COLUMNS}
# The known aquifer's values in the brief's rules (a what-if of one of them): the aquifers list
# replaces them, and the older second aquifer's fields.
KNOWN_RULES = {
    "thickness_m": "reservoir_thickness_m",
    "permeability_md": "permeability_md",
    "pressure_bar": "reservoir_pressure_bar",
    "gas_liquid_ratio": "gas_liquid_ratio",
}
SECOND_RULES = (
    "second_aquifer_depth_m",
    "second_aquifer_thickness_m",
    "second_aquifer_permeability_md",
)
SAME_DEPTH_M = 1.0  # midpoints this close are the same aquifer
LITHOSTATIC_BAR_PER_M = 0.23  # the rock above: no aquifer's pressure is higher
HYDROSTATIC_SPREAD = 0.15  # off the brine column by more than this: worth a word


# ------------------------------------------------------------------ the brief and the rules


def known_depth(brief: DesignBrief) -> float:
    """Return the project's known aquifer's midpoint (m), whatever the brief describes."""
    from gemini_agent import projects

    try:
        return float(projects.registry().rules(brief.project_id).reservoir_depth_m)
    except KeyError:
        return float(dp.Rules().reservoir_depth_m)


def rules_update(brief: DesignBrief, base: dp.Rules) -> Dict[str, object]:
    """Return the ``Rules`` fields the brief's aquifers set (``engine.rules_for`` uses them).

    The aquifer at the known one's midpoint sets the reservoir's values; the others become
    ``other_aquifers``, a value not given taking the known aquifer's (the pressure: the brine
    column's at its depth). The list replaces the older second aquifer.
    """
    if not brief.aquifers:
        return {}
    known = float(base.reservoir_depth_m)
    out: Dict[str, object] = {k: 0.0 for k in SECOND_RULES}
    others = []
    for a in brief.aquifers:
        if abs(float(a.depth_m) - known) < SAME_DEPTH_M:
            for key, field in KNOWN_RULES.items():
                value = getattr(a, key)
                # A value as the card showed it (rounded) is the project's own, not a change.
                if value is not None and not _shown_as(value, getattr(base, field), key):
                    out[field] = float(value)
            continue
        pressure = a.pressure_bar
        if pressure is not None and _shown_as(
            pressure, default_pressure(a.depth_m, base), "pressure_bar"
        ):
            pressure = None  # the brine column's, as shown rounded: the model's own value
        others.append(
            dp.Aquifer(
                float(a.depth_m),
                float(a.thickness_m if a.thickness_m is not None else base.reservoir_thickness_m),
                float(a.permeability_md if a.permeability_md is not None else base.permeability_md),
                float(pressure if pressure is not None else default_pressure(a.depth_m, base)),
                float(
                    a.gas_liquid_ratio if a.gas_liquid_ratio is not None else base.gas_liquid_ratio
                ),
            )
        )
    out["other_aquifers"] = tuple(others)
    return out


def default_pressure(depth_m: float, rules: dp.Rules) -> float:
    """Return the pressure an aquifer at this depth has unless told: the doublet model's.

    In the known aquifer its own; elsewhere the brine column's (``doublet.reservoir_pressure_bar``).
    """
    from dioscuri_plant.doublet import reservoir_pressure_bar

    return float(reservoir_pressure_bar(float(depth_m), rules))


def search_depths(brief: DesignBrief, rules: Optional[dp.Rules] = None) -> Tuple[float, ...]:
    """Return the depths the search drills to: the brief's, its aquifers', else the project's."""
    from gemini_agent import engine, projects

    if brief.doublet_depths_m:
        return tuple(float(d) for d in brief.doublet_depths_m)
    if brief.aquifers:
        return tuple(float(a.depth_m) for a in brief.aquifers)
    rules = rules if rules is not None else engine.rules_for(brief)
    return tuple(projects.depths(rules, brief.project_id))


def resolved(brief: DesignBrief, rules: Optional[dp.Rules] = None) -> List[Dict[str, object]]:
    """Return each aquifer the search will try, with all five values and what it is.

    Each: ``depth_m``, ``thickness_m``, ``permeability_md``, ``pressure_bar``,
    ``gas_liquid_ratio``, and ``kind``: ``known`` (the project's aquifer), ``given`` (one the
    user described) or ``assumed`` (the known one's rock at another depth).
    """
    from gemini_agent import engine

    rules = rules if rules is not None else engine.rules_for(brief)
    known = known_depth(brief)
    described = rules.aquifers()
    out = []
    for d in search_depths(brief, rules):
        i = rules.aquifer_index(d)
        if i is None:
            a = dp.Aquifer(
                float(d),
                rules.reservoir_thickness_m,
                rules.permeability_md,
                default_pressure(d, rules),
                rules.gas_liquid_ratio,
            )
            kind = "assumed"
        else:
            a = described[i]
            kind = "known" if abs(a.depth_m - known) < SAME_DEPTH_M else "given"
        out.append({**record(a), "kind": kind})
    return out


DIGITS = {"depth_m": 1, "thickness_m": 1, "permeability_md": 1, "pressure_bar": 2}
DIGITS["gas_liquid_ratio"] = 3


def record(a: dp.Aquifer) -> Dict[str, float]:
    """Return an aquifer as the card's record: the five values, rounded as shown."""
    return {k: _round(getattr(a, k), DIGITS[k]) for k in KEYS}


def _round(x: float, digits: int = 1) -> float:
    return float(round(float(x), digits))


def _shown_as(value: object, exact: float, key: str) -> bool:
    """Return True when a value is the exact one as ``record`` rounds it."""
    return abs(float(value) - float(exact)) <= 0.5 * 10 ** -DIGITS[key] + 1e-9


def value_of(brief: DesignBrief, rules: Optional[dp.Rules] = None) -> List[Dict[str, float]]:
    """Return the aquifers as the card and the planner show them: the five values each."""
    return [{k: r[k] for k in KEYS} for r in resolved(brief, rules)]


def same(a: Sequence[Dict[str, object]], b: Sequence[Dict[str, object]]) -> bool:
    """Return True when two lists hold the same aquifers (each value within its rounding)."""
    if len(a or []) != len(b or []):
        return False
    for x, y in zip(a, b):
        for k in KEYS:
            try:
                if abs(float(x.get(k)) - float(y.get(k))) > 0.006:
                    return False
            except (TypeError, ValueError):
                return False
    return True


def put(brief: DesignBrief, records: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """Return the brief's fields for a new list of aquifers (``parameters.apply`` sets them).

    The list sets the depths the search tries; the known aquifer's values in the brief's rules
    (an earlier what-if) and the older second aquifer give way to it.
    """
    rules = {
        k: v
        for k, v in (brief.rules or {}).items()
        if k not in KNOWN_RULES.values() and k not in SECOND_RULES
    }
    clean = [{k: float(r[k]) for k in KEYS} for r in records]
    return {
        "aquifers": [AquiferSpec(**r) for r in clean],
        "doublet_depths_m": [r["depth_m"] for r in clean],
        "rules": rules,
    }


# ------------------------------------------------------------------ checks


def problems(records: Sequence[Dict[str, object]], rules: dp.Rules) -> Tuple[List[str], List[str]]:
    """Return what makes a list of aquifers unusable, and what is worth a word about it.

    Each value in its column's range (naming the aquifer and the column), one to three
    aquifers, none overlapping another, and a pressure the rock can hold. A pressure far from
    the brine column's is a warning: possible, but rare.
    """
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(records, (list, tuple)) or not records:
        return ["Give at least one aquifer."], warnings
    if len(records) > MAX:
        errors.append(f"At most {MAX} aquifers.")
    for n, r in enumerate(records, start=1):
        if not isinstance(r, dict):
            errors.append(f"Aquifer {n}: give its values.")
            continue
        for key, name, unit, low, high, _ in COLUMNS:
            value = r.get(key)
            try:
                x = float(value)
            except (TypeError, ValueError):
                errors.append(f"Aquifer {n}, {name.lower()}: give a number.")
                if key == "depth_m":
                    break  # the rest follows from it (an empty box: the depth's own)
                continue
            if x != x or not low - 1e-9 <= x <= high + 1e-9:
                errors.append(f"Aquifer {n}, {name.lower()}: between {low:g} and {high:g} {unit}.")
    if errors:
        return errors, warnings
    rows = [{k: float(r[k]) for k in KEYS} for r in records]
    for n, r in enumerate(rows, start=1):
        d, h, p = r["depth_m"], r["thickness_m"], r["pressure_bar"]
        if d - h / 2 < 100:
            errors.append(
                f"Aquifer {n}, thickness: {h:g} m around {d:,.0f} m would reach within 100 m of "
                "the surface."
            )
        rock = LITHOSTATIC_BAR_PER_M * d
        if p > rock:
            errors.append(
                f"Aquifer {n}, pressure: {p:g} bar at {d:,.0f} m is more than the rock above "
                f"it weighs (about {rock:,.0f} bar)."
            )
            continue
        column = rules.hydrostatic_bar(d)
        if abs(p - column) > HYDROSTATIC_SPREAD * column:
            word = "above" if p > column else "below"
            warnings.append(
                f"Aquifer {n}: {p:g} bar is {abs(p - column) / column:.0%} {word} the brine "
                f"column's {column:,.0f} bar at {d:,.0f} m; possible, but rare in Dutch aquifers. "
                "The pumps are worked out with it as given."
            )
    order = sorted(range(len(rows)), key=lambda i: rows[i]["depth_m"])
    for i, j in zip(order, order[1:]):
        a, b = rows[i], rows[j]
        if b["depth_m"] - a["depth_m"] < (a["thickness_m"] + b["thickness_m"]) / 2:
            errors.append(
                f"Aquifers {min(i, j) + 1} and {max(i, j) + 1} overlap ({a['depth_m']:,.0f} m "
                f"and {b['depth_m']:,.0f} m, {a['thickness_m']:g} and {b['thickness_m']:g} m "
                "thick): give them depths further apart, or thinner layers."
            )
    return errors, warnings


# ------------------------------------------------------------------ the inputs card


def card_field(brief: DesignBrief, rules: Optional[dp.Rules] = None) -> Dict[str, object]:
    """Return the card's ``records`` field for the aquifers (the plan's contract with the card).

    One record per aquifer (``KEYS``), the first the known one; columns with their unit, range
    and a plain help text; what each aquifer is (``kinds``, ``notes``) and any warning.
    """
    from gemini_agent import engine

    rules = rules if rules is not None else engine.rules_for(brief)
    rows = resolved(brief, rules)
    value = [{k: r[k] for k in KEYS} for r in rows]
    _, warnings = problems(value, rules)
    return {
        "key": "aquifers",
        "label": "Aquifers",
        "kind": "records",
        "hint": "The aquifers the wells can be drilled into, each with its own rock and gas",
        "help": (
            "The water-bearing rock layers the doublets can be drilled into, up to three. The "
            "first is the project's known aquifer; each has its own depth, thickness, "
            "permeability, pressure and gas in the brine, and each doublet uses its own's."
        ),
        "columns": [
            {"key": k, "label": label, "unit": unit, "low": low, "high": high, "help": text}
            for k, label, unit, low, high, text in COLUMNS
        ],
        "value": value,
        "min_items": 1,
        "max_items": MAX,
        "kinds": [r["kind"] for r in rows],
        "notes": [kind_words(r, rules) for r in rows],
        "warnings": warnings,
        # An aquifer added on the card starts as the known one at another depth; a box left
        # empty is the known one's value (the pressure: the brine column's at its depth).
        "new_item": {
            **{k: v for k, v in record(rules.known_aquifer()).items() if k != "depth_m"},
            "depth_m": None,
            "pressure_bar": None,
        },
    }


def row_words(brief: DesignBrief, rules: dp.Rules, challenge: bool) -> Tuple[str, str, str]:
    """Return the inputs card's Aquifers row: its value, where it comes from, and its kind."""
    rows = resolved(brief, rules)
    parts = []
    for n, r in enumerate(rows, start=1):
        what = {"known": "the known aquifer", "given": "yours", "assumed": "assumed"}[r["kind"]]
        if r["kind"] == "assumed":
            rock = "the known aquifer's rock"
        else:
            rock = (
                f"{float(r['thickness_m']):g} m thick, {float(r['permeability_md']):g} mD, "
                f"gas-liquid ratio {float(r['gas_liquid_ratio']):g} Nm³/m³"
            )
        parts.append(
            f"{n}. {float(r['depth_m']):,.0f} m ({what}): {rock}, "
            f"{float(r['pressure_bar']):,.0f} bar, "
            f"{rules.reservoir_temperature_c(float(r['depth_m'])):.0f} °C from the gradient"
        )
    asked = bool(brief.aquifers or brief.doublet_depths_m)
    assumed = any(r["kind"] == "assumed" for r in rows)
    source = (
        "you"
        if asked
        else (
            "the organisers (2 Nov): a depth change is acceptable; deeper ones assume the known "
            "aquifer's rock"
            if challenge and assumed
            else "Dioscuri: no other aquifer is described"
        )
    )
    return "; ".join(parts), source, "asked" if asked else "assumed"


def kind_words(row: Dict[str, object], rules: dp.Rules) -> str:
    """Return what an aquifer of the list is, in a few words."""
    temp = rules.reservoir_temperature_c(float(row["depth_m"]))
    what = {
        "known": "the project's aquifer",
        "given": "described by you",
        "assumed": "assumed: the known aquifer's rock at this depth",
    }[str(row.get("kind") or "given")]
    return f"{what}; {temp:.0f} °C from the gradient"


def _filled(row: Dict[str, object], rules: dp.Rules) -> Dict[str, object]:
    """Return a card's record with its empty boxes filled (a new row starts so, ``new_item``).

    The known aquifer's values, and the brine column's pressure at its depth.
    """
    out = dict(row)
    known = record(rules.known_aquifer())
    for key in KEYS:
        if out.get(key) not in (None, "") or key == "depth_m":
            continue
        try:
            depth = float(out.get("depth_m"))
        except (TypeError, ValueError):
            continue  # its depth is refused on its own
        out[key] = _round(rules.hydrostatic_bar(depth), 2) if key == "pressure_bar" else known[key]
    return out


def read_card(value: object, brief: DesignBrief) -> Tuple[Optional[list], str, List[str]]:
    """Check the card's aquifers: (the records to apply or None, why refused, warnings).

    The records are None, without a reason, when they are the aquifers there already are.
    """
    from gemini_agent import engine

    rules = engine.rules_for(brief)
    if not isinstance(value, list):
        return None, "Give the aquifers as a list.", []
    value = [_filled(r, rules) if isinstance(r, dict) else r for r in value]
    errors, warnings = problems(value, rules)
    if errors:
        return None, " ".join(errors), warnings
    clean = [{k: float(r[k]) for k in KEYS} for r in value]
    if same(clean, value_of(brief, rules)):
        return None, "", warnings
    return clean, "", warnings


# ------------------------------------------------------------------ the chat's changes

# How the reading writes a change of the aquifers (the catalogue's ``aquifers`` value): a list
# of edits, each {"aquifer": its number in the list now (null: a new one), "remove": true,
# "only": true, and the values the message gives}.
EDIT_WORDS = (
    "a list of edits, each {aquifer: its number in the list now, or null to add one; remove: "
    "true to drop it; only: true to keep only it; and any of depth_m, thickness_m, "
    "permeability_md, pressure_bar, gas_liquid_ratio the message gives}"
)


def now_text(rows: Sequence[Dict[str, object]]) -> str:
    """Return the aquifers now as the planner's catalogue lists them, one clause each."""
    parts = []
    for n, r in enumerate(rows or [], start=1):
        kind = r.get("kind")
        tag = {"known": " (known)", "assumed": " (assumed)"}.get(str(kind), "")
        parts.append(
            f"{n}: {float(r['depth_m']):g} m, {float(r['thickness_m']):g} m thick, "
            f"{float(r['permeability_md']):g} mD, {float(r['pressure_bar']):g} bar, gas-liquid "
            f"ratio {float(r['gas_liquid_ratio']):g}{tag}"
        )
    return "; ".join(parts)


def from_reading(
    value: object, message: str, now: Sequence[Dict[str, object]], rules: dp.Rules
) -> Tuple[Optional[List[Dict[str, object]]], str]:
    """Return the aquifers after the reading's edits, checked; (None, why) when they fail.

    An edit names an aquifer by its number, or by its depth when that is one's depth (the
    model often restates it). Every value that changes must be in the message (as written or
    converted, ``parameters._backed``). ``remove`` drops the aquifer named; without one named,
    it drops every aquifer the other edits do not name (the model's way of "keep only these");
    an aquifer another edit keeps or changes is never dropped. ``only`` keeps the one named
    alone. A new aquifer takes the known one's values for what the message does not give, the
    brine column's pressure at its depth, and replaces the assumed ones; a depth moved carries
    its pressure with the brine column.
    """
    from gemini_agent.parameters import _backed

    edits = value if isinstance(value, list) else [value]
    edits = [e for e in edits if isinstance(e, dict)]
    if not edits:
        return None, "no aquifer change read"
    rows = [dict(r) for r in now or []]
    base = next((r for r in rows if r.get("kind") == "known"), rows[0] if rows else None)
    if base is None:
        base = {**record(rules.known_aquifer()), "kind": "known"}
    # Each edit: which aquifer (0-based, None: a new one or none), its flags and its values.
    plan: List[Tuple[Optional[int], set, Dict[str, float]]] = []
    for e in edits:
        which = _named(e, rows)
        flagged = {k for k in ("remove", "only") if str(e.get(k)).lower() == "true"}
        # A value the aquifer (a new one: the known one) has already is no change: the model
        # may copy the list; only what changes must be the message's.
        was = rows[which] if which is not None else base
        values: Dict[str, float] = {}
        for key in KEYS:
            if e.get(key) in (None, ""):
                continue
            try:
                x = float(e[key])
            except (TypeError, ValueError):
                return None, f"{NAMES[key]} is not a number"
            new_depth = key == "depth_m" and which is None
            if abs(x - float(was[key])) < 1e-6 and not new_depth:
                continue
            if not _backed([x], message):
                return None, f"the {NAMES[key]} {x:g} is not in the message"
            values[key] = x
        if which is None and flagged and _number(e.get("aquifer")) is not None:
            return None, f"there is no aquifer {_number(e.get('aquifer'))} to drop or keep"
        plan.append((which, flagged, values))
    kept = {w for w, f, _ in plan if w is not None and "remove" not in f}
    only = [w for w, f, _ in plan if w is not None and "only" in f]
    drop = {w for w, f, _ in plan if w is not None and "remove" in f} - kept
    if any(w is None and "remove" in f for w, f, _ in plan) and kept:
        drop |= set(range(len(rows))) - kept  # "remove" with none named: all but those named
    added: List[Dict[str, object]] = []
    for which, flagged, values in plan:
        if which is not None:
            if values:
                rows[which] = _changed(rows[which], values, rules)
            continue
        if flagged:
            continue  # dropping or keeping no aquifer in particular: done above
        if "depth_m" not in values:
            return None, "a new aquifer needs its depth"
        new = {k: base[k] for k in KEYS}
        new["pressure_bar"] = _round(rules.hydrostatic_bar(values["depth_m"]), 2)
        new.update(values)
        new["kind"] = "given"
        added.append(new)
    if only:
        rows = [rows[i] for i in sorted(set(only))]
    else:
        rows = [r for i, r in enumerate(rows) if i not in drop]
    if added:
        rows = [r for r in rows if r.get("kind") != "assumed"] + added
    if not rows:
        return None, "that leaves no aquifer to drill into"
    clean = [{k: float(r[k]) for k in KEYS} for r in rows]
    errors, _ = problems(clean, rules)
    if errors:
        return None, errors[0][0].lower() + errors[0][1:].rstrip(".")
    return clean, ""


def _named(edit: Dict[str, object], rows: Sequence[Dict[str, object]]) -> Optional[int]:
    """Return which aquifer of the list an edit names (0-based): by its depth, else its number."""
    try:
        at = float(edit.get("depth_m"))
    except (TypeError, ValueError):
        at = None
    if at is not None:
        for i, r in enumerate(rows):
            if abs(float(r["depth_m"]) - at) < SAME_DEPTH_M:
                return i
    n = _number(edit.get("aquifer"))
    return n - 1 if n is not None and n <= len(rows) else None


def _number(value: object) -> Optional[int]:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return None
    return n if n >= 1 else None


def _changed(
    row: Dict[str, object], values: Dict[str, float], rules: dp.Rules
) -> Dict[str, object]:
    """Return an aquifer with the message's values; a new depth moves its pressure with it."""
    out = dict(row)
    if "depth_m" in values and "pressure_bar" not in values:
        shift = rules.hydrostatic_bar(values["depth_m"]) - rules.hydrostatic_bar(
            float(row["depth_m"])
        )
        out["pressure_bar"] = _round(float(row["pressure_bar"]) + shift, 2)
    out.update(values)
    if out.get("kind") == "assumed":
        out["kind"] = "given"  # described now
    return out


def second_edits(
    changes: Dict[str, object], brief: DesignBrief
) -> Optional[List[Dict[str, object]]]:
    """Return the aquifers after the older second-aquifer changes (``second_aquifer_*``).

    The depth adds the aquifer (or moves the one described), the thickness and permeability
    change it; none of them without an aquifer to change is None (nothing to apply).
    """
    from gemini_agent import engine

    rules = engine.rules_for(brief)
    rows = resolved(brief, rules)
    target = next((i for i, r in enumerate(rows) if r["kind"] == "given"), None)
    depth = changes.get("second_aquifer_depth_m")
    values = {
        k: float(changes[f"second_aquifer_{k}"])
        for k in ("thickness_m", "permeability_md")
        if changes.get(f"second_aquifer_{k}") is not None
    }
    if depth is not None and float(depth) <= 0:
        rows = [r for r in rows if r["kind"] != "given"]  # "no second aquifer"
        return [{k: r[k] for k in KEYS} for r in rows] or None
    if target is None and depth is None:
        return None
    if target is None:
        known = next((r for r in rows if r["kind"] == "known"), rows[0])
        new = {k: known[k] for k in KEYS}
        new.update(
            depth_m=float(depth),
            pressure_bar=_round(rules.hydrostatic_bar(float(depth)), 2),
            **values,
        )
        rows = [r for r in rows if r["kind"] != "assumed"] + [{**new, "kind": "given"}]
    else:
        if depth is not None:
            values["depth_m"] = float(depth)
        rows[target] = _changed(rows[target], values, rules)
    return [{k: float(r[k]) for k in KEYS} for r in rows]


# ------------------------------------------------------------------ words


def words(records: Sequence[Dict[str, object]]) -> str:
    """Return a list of aquifers in a few words, for a what-if's name and the chat's record."""
    parts = []
    for r in records or []:
        parts.append(
            f"{float(r['depth_m']):,.0f} m (gas-liquid ratio {float(r['gas_liquid_ratio']):g})"
        )
    if not parts:
        return "no aquifer"
    head = "aquifer at " if len(parts) == 1 else "aquifers at "
    return head + (
        " and ".join(parts) if len(parts) < 3 else ", ".join(parts[:-1]) + " and " + parts[-1]
    )


def label(depth_m: float, brief: DesignBrief, rules: Optional[dp.Rules] = None) -> str:
    """Return the aquifer a doublet at this depth is drilled into, in words.

    "aquifer 1 at 2,500 m (the known one)", "aquifer 2 at 3,100 m (yours: 80 m thick, 400 mD,
    gas-liquid ratio 1.2)", "an assumed aquifer at 3,000 m (the known one's rock)".
    """
    from gemini_agent import engine

    rules = rules if rules is not None else engine.rules_for(brief)
    rows = resolved(brief, rules)
    d = float(depth_m)
    n = next(
        (i + 1 for i, r in enumerate(rows) if abs(float(r["depth_m"]) - d) < SAME_DEPTH_M), None
    )
    i = rules.aquifer_index(d)
    if i is None:
        return (
            f"aquifer {n} at {d:,.0f} m (assumed: the known aquifer's rock there)"
            if n
            else f"an assumed aquifer at {d:,.0f} m (the known aquifer's rock there)"
        )
    a = rules.aquifers()[i]
    if abs(a.depth_m - known_depth(brief)) < SAME_DEPTH_M:
        what = "the known aquifer"
    else:
        what = (
            f"{a.thickness_m:g} m thick, {a.permeability_md:g} mD, {a.pressure_bar:.0f} bar, "
            f"gas-liquid ratio {a.gas_liquid_ratio:g}"
        )
    return f"aquifer {n or i + 1} at {a.depth_m:,.0f} m ({what})"


def where_words(brief: DesignBrief, rules: Optional[dp.Rules] = None) -> str:
    """Return where the search drills, in words ("in the known aquifer at 2,500 m and ...")."""
    rows = resolved(brief, rules)
    groups = []
    for kind, one, many in (
        ("known", "the known aquifer", "the known aquifer"),
        ("given", "the aquifer you described", "the aquifers you described"),
        ("assumed", "an assumed aquifer", "assumed aquifers"),
    ):
        depths = [float(r["depth_m"]) for r in rows if r["kind"] == kind]
        if depths:
            name = one if len(depths) == 1 and kind != "assumed" else many
            groups.append(f"{name} at " + ", ".join(f"{d:,.0f} m" for d in depths))
    return ("in " + " and ".join(groups)) if groups else ""


def doublets_words(doublets: Sequence[Dict[str, object]], brief: DesignBrief) -> str:
    """Return which aquifer each doublet of a design is drilled into, in one sentence."""
    from gemini_agent import engine

    rules = engine.rules_for(brief)
    depths = [float(d.get("depth_m") or 0.0) for d in doublets or []]
    depths = [d for d in depths if d > 0]
    if not depths:
        return ""
    if len(set(depths)) == 1:
        lead = "the doublet is" if len(depths) == 1 else f"all {len(depths)} doublets are"
        return f"{lead} drilled into {label(depths[0], brief, rules)}"
    return "; ".join(
        f"doublet {k} into {label(d, brief, rules)}" for k, d in enumerate(depths, start=1)
    )


def move_doublets(alt, before: Sequence[Dict[str, object]], after: Sequence[Dict[str, object]]):
    """Return a design whose doublets follow their aquifers to the new list (a what-if).

    A doublet in an aquifer that moved goes with it (matched by position: the list's edits keep
    each aquifer's place); one in an aquifer no longer there goes to the first that is.
    """
    if not alt.doublets or not after:
        return alt
    old = [float(r["depth_m"]) for r in before or []]
    new = [float(r["depth_m"]) for r in after]
    moved = []
    changed = False
    for d in alt.doublets:
        depth = float(d.get("depth_m") or alt.depth_m)
        if any(abs(depth - x) < SAME_DEPTH_M for x in new):
            moved.append(dict(d))
            continue
        k = next((i for i, x in enumerate(old) if abs(depth - x) < SAME_DEPTH_M), None)
        to = new[k] if k is not None and k < len(new) and len(old) == len(new) else new[0]
        moved.append(dict(d, depth_m=to))
        changed = True
    if not changed:
        return alt
    return alt.model_copy(
        update={"doublets": moved, "depth_m": float(moved[0].get("depth_m") or alt.depth_m)}
    )
