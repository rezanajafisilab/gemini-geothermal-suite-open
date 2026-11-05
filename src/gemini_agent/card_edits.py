"""The inputs card as a form: which rows the user can change, and the changes checked by code.

Before the first design the agent shows the inputs it will use (``reporter.inputs_rows``). A row
that holds parameters of the planner's catalogue (``parameters.CATALOGUE``) carries them as
``fields`` (kind, unit, range and the value now), so the card can turn into a form in place; a
row that is a fact from the files, or a setting with its own switch, stays read-only and says
why (``locked``). What the card sends back with Run (``{"changes": "<json>"}`` and the doublets'
stop dates, ``{"doublet_stops": "<json>"}``) goes through the planner's own checks
(``parameters.check``: a known key, in range) and a few of code's (a return below its supply, the
stop dates in 2027 and long enough) before ``parameters.apply``; what fails comes back to the
card, on its field, and nothing runs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from gemini_agent import aquifers
from gemini_agent import stops as stop_dates
from gemini_agent.contract import DesignBrief

# The card's pages, in order (the last, the review, is the card's own): each row goes to the page
# of its group. A group no page names goes to "Your request". Limits come after the request (4 Nov):
# the doublets asked for there set the Maintenance section's doublets.
PAGES = (
    ("demand", "Demand"),
    ("reservoir", "Reservoir and wells"),
    ("brine", "Brine and gas"),
    ("networks", "Networks"),
    ("prices", "Prices"),
    ("request", "Your request"),
    ("limits", "Limits"),
)
PAGE_OF_GROUP = {
    "Demand": "demand",
    "Reservoir": "reservoir",
    "Reservoir and wells": "reservoir",
    "Brine and gas": "brine",
    "Caps": "limits",
    "Limits": "limits",
    "Maintenance": "limits",
    "Networks": "networks",
    "Costs": "prices",
    "Prices": "prices",
    "Plant options": "request",
    "Your request": "request",
}
# The rows of the card (by label) and the catalogue parameters each one holds, with the short
# name the form shows. The challenge's supply temperatures can be changed too: the card warns
# that the challenge requires 100 °C and 20 °C.
ROW_FIELDS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "Heat": (("heat_demand_scale", "Scale the demand"),),
    "Cold": (("cool_demand_scale", "Scale the demand"),),
    # The known aquifer's thickness, permeability and pressure are changed in the Aquifers table
    # (its first line): one place per value (4 Nov); the Aquifer row says so.
    "Temperature": (
        ("gradient_c_per_km", "Gradient"),
        ("reservoir_change_k", "Warmer (+) or colder (−)"),
    ),
    # Each aquifer's depth, thickness, permeability, pressure and gas-liquid ratio, one record
    # each (``aquifers.card_field``): it replaced "Wells drilled into" (the depths) and the
    # second aquifer, and holds the gas-liquid ratio the Brine row had (4 Nov).
    "Aquifers": (("aquifers", "Aquifers"),),
    "Brine": (
        ("gas_ch4_fraction", "Methane in the gas"),
        ("gas_co2_fraction", "CO₂ in the gas"),
        ("brine_density_kg_m3", "Density"),
        ("brine_viscosity_pa_s", "Viscosity"),
    ),
    "Heat capacity": (("brine_cp_j_kg_k", "Heat capacity"),),
    "Doublets and flow": (
        ("flow_min_m3h", "Lowest flow"),
        ("flow_max_m3h", "Flow cap"),
        ("max_brine_cooling_k", "Brine cooled by at most"),
        ("pump_efficiency", "Pump efficiency"),
    ),
    "Operating days": (("operating_days", "Days a year"),),
    "Heating network": (("heat_supply_c", "Supply"), ("heat_return_c", "Return")),
    "Cooling network": (("cool_supply_c", "Supply"), ("cool_return_c", "Return")),
    "Prices": (
        ("electricity_eur_per_mwh", "Electricity"),
        ("gas_eur_per_mwh", "Gas"),
        ("carbon_eur_per_t", "CO₂"),
        ("discount_rate", "Discount rate"),
    ),
    "Design for": (
        ("objective", "Best means"),
        ("n_doublets", "Doublets"),
        ("exclude", "Leave out"),
    ),
}
# The switches each row holds (``toggles``: their ids); the Maintenance section is one control
# for the doublets' stops and the units' service.
ROW_TOGGLES: Dict[str, Tuple[str, ...]] = {
    "The brine's gas": ("flare_brine_gas", "co2_reinjection"),
    "Network heat losses": ("network_length_km",),
    "Doublet stops": ("maintenance",),
    "Units' yearly service": ("maintenance",),
    "Prices": ("grid_by_month",),
    "Free cooling, solar, heat store": ("free_cooling", "solar_mwp", "storage_mwh", "storage_ates"),
}
UNIT_SHOWN = {
    "m3/h": "m³/h",
    "EUR/MWh": "€/MWh",
    "EUR/t": "€/t",
    "Nm3/m3": "Nm³/m³",
    "x": "times",
    "kg/m3": "kg/m³",
    "J/(kg K)": "J/(kg·K)",
}
# Fractions the form shows in per cent, the viscosity in mPa·s: (scale, unit shown).
SCALED = {
    "discount_rate": (100.0, "%"),
    "pump_efficiency": (100.0, "%"),
    "gas_ch4_fraction": (100.0, "%"),
    "gas_co2_fraction": (100.0, "%"),
    "brine_viscosity_pa_s": (1000.0, "mPa·s"),
}
PERCENT = {k for k, (_, unit) in SCALED.items() if unit == "%"}
UNIT_WORDS = {
    "heat_pump": "heat pumps",
    "boiler": "gas boilers",
    "chiller": "chillers",
    "electric_boiler": "electric boilers",
}
ANY_DOUBLETS = ""  # the n_doublets choice "1 to 3": the search picks
# What a row is, in a sentence the card shows under its name (its parameters have their own).
ROW_HELP = {
    "Heat": "The heat the district's buildings need each day of 2027, from the demand file.",
    "Cold": "The cooling the district's buildings need each day of 2027, from the demand file.",
    "Aquifer": "The porous, water-bearing rock layer the wells produce brine from and inject it "
    "back into.",
    "Temperature": "The brine's temperature at the producer, from the rock's warming with depth.",
    "Wells drilled into": "Where the doublets' wells end: the known aquifer, or assumed ones "
    "at other depths.",
    "Brine": "The salty water the wells produce, and the gas dissolved in it. How much gas "
    "comes with it (the gas-liquid ratio) is each aquifer's own: change it in the Aquifers row.",
    "Heat capacity": "How much heat the brine carries per degree; the challenge does not give it.",
    "The brine's gas": "What the plant does with the gas separated from the brine.",
    "Doublets and flow": "A doublet is a producer and an injector well. These are the limits on "
    "how much brine each pumps and how far it is cooled.",
    "Operating days": "How many days a year each doublet may run; the plant serves all 365.",
    "Heating network": "The pipes that carry hot water from the plant to the buildings (the "
    "supply) and back (the return). Accepted: supply {heat_supply_c}, return {heat_return_c} "
    "and below the supply.",
    "Cooling network": "The pipes that carry chilled water from the plant to the buildings (the "
    "supply) and back, warmer (the return). Accepted: supply {cool_supply_c}, return "
    "{cool_return_c} and above the supply.",
    "Network heat losses": "The heat the district's pipes lose to the ground on the way.",
    "Prices": "What energy and CO₂ cost, and the rate that spreads the investment over the years.",
    "Design for": "What the search looks for, and what it may and may not use.",
    "Free cooling, solar, heat store": "Options the plant can have beside the doublets and the "
    "units.",
    "Doublet stops": "When each doublet is off for maintenance, and every other unit's yearly "
    "service.",
}
# Why a row has nothing to change, by label, then by kind: said on the card, not in a tooltip.
LOCKED_ROWS = {
    "Relaxed by you": "A summary of the limits you changed: change each one above",
    "Scaled": "A summary: change the scale in the Heat and Cold boxes above",
    "Not modelled": "Dioscuri's model has no input for this, so it can't change the design",
    "Second aquifer": "Change it in the Aquifers row",
    "Aquifer": "Change it in the Aquifers table (the first line is this aquifer)",
}
# The aquifers' columns and the catalogue parameter whose typical values they have (the
# pressure's is a warning of its own: far from the brine column's).
COLUMN_TYPICAL = {
    "depth_m": "aquifer_depths_m",
    "thickness_m": "reservoir_thickness_m",
    "permeability_md": "permeability_md",
    "gas_liquid_ratio": "gas_liquid_ratio",
}
LOCKED_KINDS = {
    "data": "Read from the project's files: a fact, not an assumption",
    "fixed": "Given by the challenge's requirements",
    "derived": "Worked out from the other inputs on this page: change those",
    "assumed": "Dioscuri's assumption, with no input of its own: type the change below if it "
    "matters",
    "asked": "Your request: change it in its own boxes",
}
# Rock over the aquifer (about 2,300 kg/m³): a pore pressure above its weight would crack it.
ROCK_BAR_PER_M = 2300 * 9.81 / 1e5


@dataclass
class Edit:
    """What the card's answers did to the brief."""

    brief: DesignBrief
    changed: List[str] = field(default_factory=list)  # catalogue keys, and "doublet_stops"
    errors: Dict[str, str] = field(default_factory=dict)  # by key: why it was refused
    asked: Dict[str, object] = field(default_factory=dict)  # the refused values, shown again
    warnings: Dict[str, str] = field(default_factory=dict)  # by key: accepted, worth a word


def _project_id(project) -> str:
    return getattr(project, "id", None) or "challenge"


def _now(brief: DesignBrief) -> Dict[str, object]:
    """Return each card parameter's value now (the brief's, else the project's)."""
    from gemini_agent import engine, parameters, projects

    rules = engine.rules_for(brief)
    now = parameters.values_now(brief, None, rules, engine.prices_for(None, brief))
    now["n_doublets"] = brief.n_doublets
    now["aquifer_depths_m"] = [
        float(x)
        for x in (list(brief.doublet_depths_m) or list(projects.depths(rules, brief.project_id)))
    ]
    now["exclude"] = list(brief.excluded)
    for key, p in parameters.CATALOGUE.items():
        if p.card_only:  # the brine's properties: the rules' own fields
            now[key] = getattr(rules, p.field or key)
    return now


def _keys(row: Dict[str, object], brief: DesignBrief, project) -> List[Tuple[str, str]]:
    """Return the parameters a row holds that the card may change for this project."""
    out = []
    for key, name in ROW_FIELDS.get(str(row.get("label")), ()):
        if key == "n_doublets" and brief.doublets:
            continue  # set by the doublets the user described one by one
        out.append((key, name))
    return out


def _round(x: float) -> float:
    return float(f"{x:.6g}")


def challenge_caps(brief: DesignBrief) -> Dict[str, Dict[str, object]]:
    """Return the challenge's caps on the card's parameters, in the catalogue's units.

    Each is ``{"low": .., "high": .., "words": ..}`` (either bound may be missing): outside it a
    design does not meet the challenge, though it can still run (the card warns). Only the
    challenge's project has them.
    """
    from gemini_agent import engine, projects

    if brief.project_id != projects.CHALLENGE:
        return {}
    caps = engine.project_caps(brief)
    return {
        "flow_max_m3h": {
            "high": caps.flow_max_m3h,
            "words": f"The challenge allows at most {caps.flow_max_m3h:g} m³/h per doublet",
        },
        "flow_min_m3h": {
            "low": caps.flow_min_m3h,
            "words": f"The challenge's doublets run at {caps.flow_min_m3h:g} m³/h or more",
        },
        "max_brine_cooling_k": {
            "high": caps.max_brine_cooling_k,
            "words": f"The challenge allows the brine to be cooled by at most "
            f"{caps.max_brine_cooling_k:g} K",
        },
        "operating_days": {
            "high": caps.operating_days,
            "words": f"The challenge allows each doublet at most {caps.operating_days} days a "
            "year",
        },
        "pump_efficiency": {
            "low": caps.pump_efficiency,
            "high": caps.pump_efficiency,
            "words": f"The challenge sets the pumps at {caps.pump_efficiency * 100:g} %",
        },
        "heat_supply_c": {
            "low": caps.heat_supply_c,
            "high": caps.heat_supply_c,
            "words": f"The challenge requires heat at {caps.heat_supply_c:g} °C",
        },
        "cool_supply_c": {
            "low": caps.cool_supply_c,
            "high": caps.cool_supply_c,
            "words": f"The challenge requires cold at {caps.cool_supply_c:g} °C",
        },
    }


def field_of(
    key: str, name: str, value: object, cap: Optional[Dict[str, object]] = None
) -> Dict[str, object]:
    """Return one form field: the catalogue's kind, unit, range and words, and the value now.

    ``help`` says what it is and what it changes; ``typical`` (with ``typical_words``) the
    usual values, outside which the card warns; ``depends`` what it is linked to; ``cap`` the
    challenge's limit (``challenge_caps``), outside which the design does not meet the
    challenge. Numbers are in the form's units (a fraction in per cent: ``scale``).
    """
    from gemini_agent import parameters

    p = parameters.CATALOGUE[key]
    spec: Dict[str, object] = {"key": key, "label": name, "kind": p.kind, "hint": p.label}
    spec.update({k: getattr(p, k) for k in ("help", "typical_words", "depends") if getattr(p, k)})
    linked = parameters.linked_both_ways(key)
    if linked:
        spec["linked"] = linked
    if p.affects:
        spec["affects"] = list(p.affects)
    if key == "objective":
        spec.update(
            options=list(p.options),
            words={o: parameters.OBJECTIVE_SHORT.get(o, o) for o in p.options},
            value=str(value or "best"),
        )
    elif key == "n_doublets":
        spec.update(
            kind="choice",
            options=[ANY_DOUBLETS, "1", "2", "3"],
            words={ANY_DOUBLETS: "1 to 3 (the search picks)", "1": "1", "2": "2", "3": "3"},
            value=ANY_DOUBLETS if value is None else str(int(float(value))),
        )
    elif p.kind == "choice":
        spec.update(options=list(p.options), value=str(value))
    elif p.kind == "list" and p.options:
        spec.update(
            options=list(p.options),
            words={o: UNIT_WORDS.get(o, o.replace("_", " ")) for o in p.options},
            value=[str(v) for v in (value or [])],
        )
    elif p.kind == "list":
        spec.update(
            unit=UNIT_SHOWN.get(p.unit, p.unit),
            low=p.low,
            high=p.high,
            value=[_round(float(v)) for v in (value or [])],
            required=True,
        )
    else:
        scale, unit = SCALED.get(key, (1.0, UNIT_SHOWN.get(p.unit, p.unit)))
        spec.update(
            unit=unit,
            low=_round(p.low * scale),
            high=_round(p.high * scale),
            value=None if value is None else _round(float(value) * scale),
            whole=p.unit == "days" or p.target == "search",
            required=True,
        )
        if scale != 1.0:
            spec["scale"] = scale
    if p.typical and "low" in spec:
        scale = float(spec.get("scale", 1.0))
        spec["typical"] = [_round(p.typical[0] * scale), _round(p.typical[1] * scale)]
    if cap:
        scale = float(spec.get("scale", 1.0))
        spec["cap"] = {
            k: (_round(float(v) * scale) if k in ("low", "high") else v) for k, v in cap.items()
        }
    return spec


def _row_help(label: str) -> str:
    """Return a row's sentence, with the catalogue's ranges where it names them."""
    from gemini_agent import parameters

    ranges = {
        k: f"{p.low:g} to {p.high:g} {p.unit}"
        for k, p in parameters.CATALOGUE.items()
        if k.startswith(("heat_", "cool_")) and p.kind == "number"
    }
    return ROW_HELP[label].format(**ranges)


def _links(spec: Dict[str, object]) -> None:
    """Give a field the catalogue's links (both ways) and what it changes, when it lacks them."""
    from gemini_agent import parameters

    key = str(spec.get("key"))
    if key not in parameters.CATALOGUE:
        return
    if "linked" not in spec and parameters.linked_both_ways(key):
        spec["linked"] = parameters.linked_both_ways(key)
    if "affects" not in spec and parameters.CATALOGUE[key].affects:
        spec["affects"] = list(parameters.CATALOGUE[key].affects)


def page_of(row: Dict[str, object]) -> str:
    """Return the card's page a row goes on (by its group)."""
    return PAGE_OF_GROUP.get(str(row.get("group")), "request")


def with_fields(
    rows: List[Dict[str, object]], brief: DesignBrief, project, changed: Sequence[str] = ()
) -> List[Dict[str, object]]:
    """Give each row its page, its form fields or switches, else the reason it has none.

    Parameters
    ----------
    rows : list of dict
        The card's rows (``reporter.inputs_rows``), changed in place.
    brief : DesignBrief
        The brief the rows show.
    project : ProjectData
        The project (the challenge's caps are warned about).
    changed : sequence of str
        Keys the user just changed: the rows that hold them are marked.
    """
    now = _now(brief)
    # Each field's value with every input back at the project's own (``defaults``): the card
    # marks a value that differs from it and can put it back, one field or all (5 Nov).
    base_brief = defaults(brief)
    base = _now(base_brief)
    caps = challenge_caps(brief)
    touched = set(changed)
    shown = {k for row in rows for k in ROW_FIELDS.get(str(row.get("label")), ())}
    elsewhere = {k for k, _ in shown} | {
        "allow",
        "doublet_stops",
        "doublet_days_off",
        "service_plan",
    }
    for row in rows:
        row.setdefault("page", page_of(row))
        keys = _keys(row, brief, project)
        label, kind = str(row.get("label")), str(row.get("kind"))
        if label in ROW_HELP:
            row["help"] = _row_help(label)
        if label in ROW_TOGGLES:
            row["toggles"] = list(ROW_TOGGLES[label])
        if keys:
            row["fields"] = [
                (
                    aquifers.card_field(brief, now.get("_rules"))
                    if k == "aquifers"
                    else field_of(k, name, now.get(k), caps.get(k))
                )
                for k, name in keys
            ]
            for spec in row["fields"]:  # a field made elsewhere (the aquifers): its links too
                _links(spec)
                if spec.get("kind") == "records":
                    _typical_columns(spec)
                    spec["default"] = aquifers.value_of(base_brief, base.get("_rules"))
                else:
                    key = str(spec["key"])
                    spec["default"] = field_of(key, key, base.get(key))["value"]
            held = {k for k, _ in keys} | (
                {"allow"} if any(k == "exclude" for k, _ in keys) else set()
            )
            if row.get("label") == "Design for":
                # It also lists the rules' changes: marked only for its own, or one no row shows.
                row["changed"] = bool(touched & held or touched - elsewhere)
            elif touched & held:
                row["changed"] = True
        elif not row.get("fields") and not row.get("toggles"):
            row["locked"] = LOCKED_ROWS.get(label) or LOCKED_KINDS.get(kind, "Read-only")
        if label == "Doublet stops" and touched & {"doublet_stops", "doublet_days_off"}:
            row["changed"] = True
        if label == "Units' yearly service" and "service_plan" in touched:
            row["changed"] = True
    return rows


def warnings(rows: List[Dict[str, object]]) -> Dict[str, str]:
    """Return the card's warnings for the values its fields hold now, by key.

    A value outside the challenge's cap (the design will not meet the challenge), else outside
    its typical values; a pressure far from hydrostatic. The card shows the same live as the
    user types (``inputsForm.ts``); a warning never stops the run.
    """
    out: Dict[str, str] = {}
    values: Dict[str, float] = {}
    for row in rows:
        for spec in row.get("fields") or []:
            why = _warning(spec, spec.get("value"))
            if why:
                out[str(spec["key"])] = why
            if spec.get("kind") == "number" and spec.get("value") is not None:
                values[str(spec["key"])] = float(spec["value"])
            if spec.get("kind") == "records":
                said = record_warnings(spec, spec.get("value") or []) + list(
                    spec.get("warnings") or []
                )
                if said:
                    out[str(spec["key"])] = " ".join(said)
    tight = tight_rock(values)
    if tight:  # says more than "outside the typical values"
        out["permeability_md"] = tight
    return out


def record_warnings(spec: Dict[str, object], records: Sequence[Dict[str, object]]) -> List[str]:
    """Return the warnings on the aquifers the old Aquifer boxes had: rock too tight, typical.

    Per aquifer: permeability × thickness under ``TIGHT_DM`` (then not also "outside the
    typical"), else each value outside its catalogue's typical values; the same words for
    several aquifers said once ("Aquifers 1 and 2: ..."). The card says the same as it is typed
    (``inputsForm.recordWarnings``).
    """
    cols = {str(c["key"]): c for c in spec.get("columns") or []}
    said: Dict[str, List[int]] = {}  # the words after the aquifers' numbers, and the numbers
    for n, r in enumerate(records, start=1):
        try:
            k, h = float(r.get("permeability_md")), float(r.get("thickness_m"))
        except (TypeError, ValueError):
            k = h = None
        tight = k is not None and h is not None and k * h / 1000 < TIGHT_DM
        if tight:
            words = tight_rock({"permeability_md": k, "reservoir_thickness_m": h})
            said.setdefault(": " + words[0].lower() + words[1:], []).append(n)
        for key, c in cols.items():
            low_high = c.get("typical")
            if not low_high or (tight and key == "permeability_md"):
                continue
            try:
                x = float(r.get(key))
            except (TypeError, ValueError):
                continue
            lo, hi = float(low_high[0]), float(low_high[1])
            if not lo - 1e-9 <= x <= hi + 1e-9:
                unit = f" {c['unit']}" if c.get("unit") else ""
                words = (
                    f", {str(c['label']).lower()}: outside the typical {_fmt(lo)} to "
                    f"{_fmt(hi)}{unit}: check it is right."
                )
                said.setdefault(words, []).append(n)
    return [_numbered(ns) + words for words, ns in said.items()]


def _numbered(ns: Sequence[int]) -> str:
    """Return "Aquifer 2" or "Aquifers 1, 2 and 3"."""
    if len(ns) == 1:
        return f"Aquifer {ns[0]}"
    return "Aquifers " + ", ".join(map(str, ns[:-1])) + f" and {ns[-1]}"


def _typical_columns(spec: Dict[str, object]) -> None:
    """Give the aquifers' columns the catalogue's typical values (``COLUMN_TYPICAL``)."""
    from gemini_agent import parameters

    for c in spec.get("columns") or []:
        p = parameters.CATALOGUE.get(COLUMN_TYPICAL.get(str(c.get("key")), ""))
        if p is not None and p.typical and "typical" not in c:
            c["typical"] = [p.typical[0], p.typical[1]]
            c["typical_words"] = p.typical_words


# Below this the wells barely flow (3 Nov: 1 D·m found no design that meets the caps, 0.5 D·m
# made the well model fail to balance).
TIGHT_DM = 2.0


def tight_rock(values: Dict[str, float]) -> Optional[str]:
    """Return a warning when permeability × thickness is too low for a doublet, else None."""
    k, h = values.get("permeability_md"), values.get("reservoir_thickness_m")
    if k is None or h is None or k * h / 1000 >= TIGHT_DM:
        return None
    return (
        f"The rock lets very little brine through (k × h = {k * h / 1000:.2g} D·m; a doublet "
        "needs a few): the search may find no design, and below about 0.5 D·m the plant can't "
        "be balanced at all."
    )


def _fmt(x: float) -> str:
    return f"{x:,.6g}" if abs(x) >= 1000 else f"{x:.6g}"


def _warning(spec: Dict[str, object], value: object) -> Optional[str]:
    """Return why a field's value (in the form's units) deserves a warning, or None."""
    if spec.get("kind") != "number" or value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    unit = f" {spec['unit']}" if spec.get("unit") else ""
    cap = spec.get("cap") or {}
    low, high = cap.get("low"), cap.get("high")
    if (low is not None and x < float(low) - 1e-9) or (high is not None and x > float(high) + 1e-9):
        return (
            f"{cap.get('words', 'Outside the challenge')}: the design will not meet the challenge."
        )
    typical = spec.get("typical")
    if typical and not float(typical[0]) - 1e-9 <= x <= float(typical[1]) + 1e-9:
        return (
            f"Outside the typical {_fmt(float(typical[0]))} to {_fmt(float(typical[1]))}{unit}: "
            "check it is right."
        )
    return None


def defaults(brief: DesignBrief, project=None) -> DesignBrief:
    """Return the brief with every input back at the project's own values (the card's reset).

    What a conversation knows before its first message (``Session.starting_brief``: the
    project's reservoir and networks), and what the request is for: its site and whether it
    wants cooling. Every value the user set, in a message or on the card, goes: the networks'
    returns, the demand, the aquifers and depths, the doublets, the prices, the switches and the
    stop dates (5 Nov: "get back to default values" ran a design with an aquifer at 100 m the
    user never confirmed). Without the project: the same values, the networks left to it.
    """
    keep = {"site": brief.site, "wants_cooling": brief.wants_cooling}
    if project is None:
        return DesignBrief(project_id=brief.project_id, **keep)
    from gemini_agent.agent import Session

    return Session.starting_brief(project).model_copy(update=keep)


def _switches(brief: DesignBrief) -> Dict[str, object]:
    """Return the card's switches and the Maintenance section's values, by id (for a compare)."""
    out: Dict[str, object] = {}
    for t in toggles(brief):
        if t.get("kind") == "maintenance":
            out["maintenance"] = (t.get("stops"), t.get("days_off"), t.get("units"))
        else:
            out[str(t["id"])] = t.get("value")
    return out


def at_defaults(brief: DesignBrief) -> bool:
    """Return True when every input of the card is the project's own (nothing to reset)."""
    from gemini_agent import parameters

    base = defaults(brief)
    now, own = _now(brief), _now(base)
    if any(
        not parameters._same(now.get(k), own.get(k)) for k in set(now) | set(own) if k != "_rules"
    ):
        return False
    if not aquifers.same(aquifers.value_of(brief), aquifers.value_of(base)):
        return False
    # What the request asks beyond the card's boxes (a CO₂ floor, doublets described one by
    # one, stop dates, how many homes): its own fields, the project's (worked out above) aside.
    own_fields = set(DesignBrief.model_fields) - WORKED_OUT
    if brief.model_dump(include=own_fields) != base.model_dump(include=own_fields):
        return False
    return _switches(brief) == _switches(base)


# The brief's fields ``at_defaults`` compares as values (the networks, the reservoir, the rules,
# the prices, the aquifers), or keeps through a reset (the site, whether cooling is wanted).
WORKED_OUT = {
    "site",
    "wants_cooling",
    "project_id",
    "heating",
    "cooling",
    "reservoir_depth_m",
    "reservoir_temp_c",
    "rules",
    "prices",
    "aquifers",
    "doublet_depths_m",
}


def yours(brief: DesignBrief) -> List[str]:
    """Return the card's parameters the user set: those whose value is not the project's own.

    The card marks them ("from your message") and says what they affect before the run.
    """
    from gemini_agent import parameters

    now, base = _now(brief), _now(DesignBrief(project_id=brief.project_id))
    keys = dict.fromkeys(k for fields in ROW_FIELDS.values() for k, _ in fields)
    return [
        k
        for k in keys
        if k in now
        and not parameters._same(now.get(k), base.get(k))
        and not (k == "n_doublets" and now.get(k) is None)
    ]


def context(brief: DesignBrief) -> Dict[str, object]:
    """Return what the card needs to work out consequences as the user types.

    The production temperature (surface + change + gradient × depth), the injection floor
    (production − the cooling cap), hydrostatic pressure, one doublet's heat at the cap, the
    demand scaled: from these numbers, in the card's own units.
    """
    from gemini_agent import engine, projects

    rules = engine.rules_for(brief)
    try:
        base = projects.registry().rules(brief.project_id)
    except KeyError:
        base = rules
    d = engine.demand_summary(brief.project_id)
    return {
        "surface_c": float(base.surface_temperature_c),
        "depth_m": float(rules.reservoir_depth_m),
        "heat_gwh": float(d["annual_heat_gwh"]),
        "heat_peak_mw": float(d["peak_heat_mw"]),
        "cool_gwh": float(d["annual_cool_gwh"]),
        "cool_peak_mw": float(d["peak_cool_mw"]),
        "rock_bar_per_m": ROCK_BAR_PER_M,
    }


def toggles(brief: DesignBrief) -> List[Dict[str, object]]:
    """Return the card's switches: each with its page, the row it sits in and its words.

    Network heat losses (km), the Maintenance section (the doublets' stops and every unit's
    yearly service), the plant options (free cooling, solar, a store, seasonal), the grid's CO₂
    by month and what is done with the brine's gas. Their values go back with Run, by id.
    """
    from gemini_agent import engine, parameters

    rules = engine.rules_for(brief)
    out: List[Dict[str, object]] = [
        {
            "id": "network_length_km",
            "label": "Include the district network's heat losses",
            "kind": "km",
            "value": float(rules.network_length_km or 0.0),
            "hint": "Length of the trunk from the plant to the buildings",
            "min": 0.1,
            "max": 50,
        },
        # The doublets' stops and every unit's yearly service, in one section (2 Nov).
        maintenance_toggle(brief),
        {
            "id": "free_cooling",
            "label": "Free cooling: the towers cool the network on cool days",
            "kind": "switch",
            "value": float(rules.free_cooling or 0.0),
            "hint": "Through a plate exchanger before the chillers, in the hours the outside "
            "air's wet bulb is 6 K below the cooling return (KNMI De Bilt, 2021-2025)",
        },
        {
            "id": "grid_by_month",
            "label": "Count the grid's CO₂ month by month",
            "kind": "switch",
            "value": float(rules.grid_by_month or 0.0),
            "hint": "Winter's grid is dirtier than summer's (Ember, Netherlands 2024): a heat "
            "pump's winter electricity weighs more",
        },
        {
            "id": "solar_mwp",
            "label": "Put solar panels at the plant",
            "kind": "amount",
            "unit": "MWp",
            "min": 0.1,
            "max": 200,
            "step": 0.1,
            "example": "e.g. 5",
            "value": float(rules.solar_mwp or 0.0),
            "hint": "Their size; the plant uses their power first, the rest is sold",
        },
        {
            "id": "storage_mwh",
            "label": "Add a hot-water heat store",
            "kind": "amount",
            "unit": "MWh",
            "min": 10,
            "max": 50000,
            "step": 10,
            "example": "e.g. 500",
            "value": float(rules.storage_mwh or 0.0),
            "hint": "Its size; it keeps the quiet days' geothermal heat for the boiler's days",
        },
        {
            "id": "storage_ates",
            "label": "Make the store seasonal: a high-temperature aquifer store (HT-ATES)",
            "kind": "switch",
            "value": float(rules.storage_ates or 0.0),
            "hint": "Summer's geothermal heat kept in a shallow aquifer for winter, 60 % back "
            "(as the Middenmeer pilot); give its size above",
        },
        {
            "id": "co2_reinjection",
            "label": "Dissolve the brine's own CO₂ back into the injected brine",
            "kind": "switch",
            "value": float(rules.co2_reinjection or 0.0),
            "hint": "Scrubbed from the separated gas at pressure, about 25 €/t (CarbFix); "
            "the methane still goes to the boiler",
        },
        {
            "id": "flare_brine_gas",
            "label": "Flare all the brine's gas instead of burning it in the boiler",
            "kind": "switch",
            "value": float(rules.flare_brine_gas or 0.0),
            "hint": "The boiler then buys all its gas; routine flaring needs consent "
            "(Mijnbouwbesluit art. 38) and the EU Methane Regulation limits it",
        },
    ]
    rows = {t: label for label, ids in ROW_TOGGLES.items() for t in ids}
    pages = {
        "network_length_km": "networks",
        "maintenance": "limits",
        "free_cooling": "request",
        "grid_by_month": "prices",
        "solar_mwp": "request",
        "storage_mwh": "request",
        "storage_ates": "request",
        "co2_reinjection": "brine",
        "flare_brine_gas": "brine",
    }
    for t in out:
        key = str(t["id"])
        t["page"] = pages.get(key, "request")
        if key in rows:
            t["row"] = rows[key]
        p = parameters.CATALOGUE.get(key)
        if p is not None:
            t.update(
                {k: getattr(p, k) for k in ("help", "typical_words", "depends") if getattr(p, k)}
            )
    return out


def stops_toggle(brief: DesignBrief) -> Dict[str, object]:
    """Return the card's control for when the doublets stop: Dioscuri's weeks, or your dates."""
    from gemini_agent import engine

    rules = engine.rules_for(brief)
    off = max(0, stop_dates.DAYS - int(rules.operating_days))
    n = len(brief.doublets) or brief.n_doublets or stop_dates.MAX_DOUBLETS
    given = [list(map(list, d)) for d in (brief.doublet_stops or [])]
    return {
        "id": "doublet_stops",
        "kind": "stops",
        "label": "When the doublets stop",
        "hint": (f"365 − {rules.operating_days} operating days = {off} days off for each doublet"),
        "value": 1.0 if given else 0.0,
        "stops": given,
        "suggested": suggested(brief, n, int(rules.operating_days)),
        "doublets": int(n),
        "operating_days": int(rules.operating_days),
        "year": stop_dates.YEAR,
    }


# The units whose yearly service the card plans, in the card's order: (unit, label, days, bank).
SERVICE_UNITS = (
    ("heat exchanger", "Heat exchanger", False),
    ("heat pump", "Heat pump", False),
    ("boiler", "Gas boiler", True),
    ("electric boiler", "Electric boiler", True),
    ("chillers", "Electric chillers", True),
    ("absorption", "Absorption chiller", False),
)
SERVICE_MODES = ("off", "auto", "dates")


def maintenance_toggle(brief: DesignBrief) -> Dict[str, object]:
    """Return the card's Maintenance section: the doublets' stops, then each unit's service.

    The doublets' stop comes first (35 days off by default, the 330-day cap's; each doublet its
    own length or dates), then the yearly service of every unit type, whether or not a design
    will have it (a unit the design lacks is not serviced).
    """
    from dioscuri_plant.service import DAYS_OUT
    from gemini_agent import engine

    out = stops_toggle(brief)
    rules = engine.rules_for(brief)
    n = int(out["doublets"])
    default = max(0, stop_dates.DAYS - int(rules.operating_days))
    lengths = list(getattr(rules, "stop_days_off", ()) or [])
    plan = {str(u): (str(m), [list(map(int, r)) for r in rs]) for u, m, rs in rules.service_plan}
    auto = bool(rules.planned_service)
    units = []
    for unit, label, bank in SERVICE_UNITS:
        mode, ranges = plan.get(unit, ("auto" if auto else "off", []))
        units.append(
            {
                "unit": unit,
                "label": label,
                "days": DAYS_OUT[unit],
                "bank": bank,
                "mode": mode if mode in SERVICE_MODES else "off",
                "ranges": ranges,
            }
        )
    out.update(
        id="maintenance",
        kind="maintenance",
        label="Maintenance",
        hint=(
            f"The geothermal source may be off {default} days a year (planned or unplanned "
            "maintenance); the other units cover those days"
        ),
        days_off=[
            int(lengths[i]) if i < len(lengths) and lengths[i] else default for i in range(n)
        ],
        default_days_off=default,
        cap_operating_days=int(engine.project_caps(brief).operating_days),
        units=units,
    )
    return out


def suggested(brief: DesignBrief, n: int, operating_days: int) -> List[List[List[int]]]:
    """Return a start for the user's dates: one block per doublet in the quietest heat weeks."""
    import numpy as np

    from dioscuri_plant.year import stop_windows
    from gemini_agent import engine

    try:
        heat = np.asarray(engine.demand(brief.project_id).heat_mw, dtype=float)
    except Exception:  # a project without a demand yet: the summer
        heat = np.cos(np.linspace(0, 2 * np.pi, stop_dates.DAYS, endpoint=False)) + 1.0
    return [[[a, b]] for a, b in stop_windows(heat, int(n), int(operating_days))]


# The switches Run sends, by id: those with an amount have its range (the card's own), the
# others are on (1) or off (0).
TOGGLE_KEYS = (
    "network_length_km",
    "planned_service",
    "co2_reinjection",
    "flare_brine_gas",
    "free_cooling",
    "grid_by_month",
    "solar_mwp",
    "storage_mwh",
    "storage_ates",
)
TOGGLE_RANGES = {
    "network_length_km": (0.1, 50.0, "km"),
    "solar_mwp": (0.1, 200.0, "MWp"),
    "storage_mwh": (10.0, 50000.0, "MWh"),
}


def read_toggles(answers: Dict[str, str], brief: DesignBrief) -> Tuple[DesignBrief, Dict[str, str]]:
    """Apply the card's switches to the brief, each checked; return it and what was refused.

    An amount must be a number in its range (0 switches it off); a switch is 0 or 1.
    """
    from gemini_agent import parameters

    extra: Dict[str, float] = {}
    refused: Dict[str, str] = {}
    for key in TOGGLE_KEYS:
        if key not in answers:
            continue
        try:
            value = float(answers[key])
        except (TypeError, ValueError):
            refused[key] = "Give a number."
            continue
        if value != value or value < 0:
            refused[key] = "Give a number of 0 or more."
            continue
        low, high, unit = TOGGLE_RANGES.get(key, (0.0, 1.0, ""))
        if value and not low - 1e-9 <= value <= high + 1e-9:
            refused[key] = f"Between {low:g} and {high:,.0f} {unit}, or 0 for none.".replace(
                "  ", " "
            )
            continue
        extra[key] = value if key in TOGGLE_RANGES else float(value >= 0.5)
    return (parameters.apply(brief, extra) if extra else brief), refused


def _quote(value: object) -> str:
    """Return a typed value as the words the planner's checks read (the value is the quote)."""
    if isinstance(value, (list, tuple)):
        return ", ".join(_quote(v) for v in value)
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _range_problem(spec: Dict[str, object], value: object) -> Optional[str]:
    """Return why a value does not fit its field, in the form's own units, or None."""
    kind = spec["kind"]
    if kind == "choice":
        return None if str(value) in spec["options"] else "Pick one of the options."
    if kind == "list" and spec.get("options"):
        bad = [
            v for v in (value if isinstance(value, list) else [value]) if v not in spec["options"]
        ]
        return "Pick from the options." if bad else None
    unit = f" {spec['unit']}" if spec.get("unit") else ""
    scale = float(spec.get("scale", 1.0))
    values = value if kind == "list" else [value]
    if kind == "list" and not values:
        return "Give at least one depth."
    for v in values if isinstance(values, list) else [values]:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "Required: give a value."
        try:
            x = float(v) * scale
        except (TypeError, ValueError):
            return "Give a number."
        if x != x or not spec["low"] - 1e-9 <= x <= spec["high"] + 1e-9:
            return f"Between {spec['low']:g} and {spec['high']:g}{unit}."
        if spec.get("whole") and abs(x - round(x)) > 1e-9:
            return "Give a whole number."
    return None


def _planner_check(key: str, value: object, now: Dict[str, object]) -> Tuple[bool, object, str]:
    """Run one change through the planner's checks: (accepted, the clean value or None, why)."""
    from gemini_agent import parameters

    quote = _quote(value)
    reading = parameters.check(
        {"changes": [{"key": key, "value": value, "quote": quote}]}, quote, now
    )
    if key in reading.changes:
        return True, reading.changes[key], ""
    if key in now and parameters._same(now[key], value):
        return True, None, ""  # the value it has: no change
    why = reading.dropped[-1].split(": ", 1)[-1] if reading.dropped else "not accepted"
    return False, None, why[0].upper() + why[1:] + "."


def _maintenance_now(brief: DesignBrief) -> Tuple[List[int], List[List[object]]]:
    """Return the brief's own days off per doublet and service plan, as the card sends them."""
    rules = dict(brief.rules or {})
    days = [int(x) for x in rules.get("stop_days_off") or []]
    plan = [
        [str(u), str(m), [list(map(int, r)) for r in rs]]
        for u, m, rs in rules.get("service_plan") or []
    ]
    return days, plan


def asks_change(answers: Dict[str, str], brief: DesignBrief) -> bool:
    """Return True when the card's answers change an input or the stop dates (or can't be read)."""
    raw = answers.get("changes")
    if raw and str(raw).strip() not in ("{}", ""):
        return True
    days, plan = _maintenance_now(brief)
    for key, now in (("doublet_days_off", days), ("service_plan", plan)):
        if key in answers:
            try:
                if _read_json(key, answers[key]) != now:
                    return True
            except (TypeError, ValueError):
                return True
    if "doublet_stops" not in answers:
        return False
    try:
        given = stop_dates.parse(answers["doublet_stops"])
    except (TypeError, ValueError):
        return True  # said on the card
    return given != [list(map(list, d)) for d in (brief.doublet_stops or [])]


def _read_json(key: str, raw: object) -> list:
    """Return the card's days off (ints per doublet) or service plan ([unit, mode, ranges]).

    Raises
    ------
    ValueError
        When the value is not what the card sends.
    """
    data = json.loads(raw) if isinstance(raw, str) else raw
    if data in (None, ""):
        return []
    if not isinstance(data, list):
        raise ValueError("a list was expected")
    if key == "doublet_days_off":
        days = [int(round(float(x))) for x in data]
        if any(d < 0 or d > stop_dates.DAYS - 100 for d in days):
            raise ValueError(f"days off must be 0 to {stop_dates.DAYS - 100}")
        return days
    units = {u for u, _, _ in SERVICE_UNITS}
    out = []
    for item in data:
        unit, mode, ranges = (
            (item.get(k) for k in ("unit", "mode", "ranges")) if isinstance(item, dict) else item
        )
        if unit not in units or mode not in SERVICE_MODES:
            raise ValueError(f"unknown unit or mode: {unit} {mode}")
        rows = []
        for r in ranges or []:
            a, b = (int(r[0]), int(r[1]))
            if not 0 <= a <= b < stop_dates.DAYS:
                raise ValueError(f"{unit}: every range must fall in {stop_dates.YEAR}")
            rows.append([a, b])
        if mode == "dates" and not rows:
            raise ValueError(f"{unit}: give at least one range, or let Dioscuri pick the weeks")
        out.append([unit, mode, sorted(rows)])
    return out


def _read_maintenance(
    answers: Dict[str, str], brief: DesignBrief, out: "Edit", fixed_days: bool = False
) -> DesignBrief:
    """Record the Maintenance section's days off and service plan in the brief's rules.

    The cap is raised (or put back) for the days off afterwards, with the dates (``_relax_cap``).
    ``fixed_days`` is kept for callers; the relaxing reads it there.
    """
    rules = dict(brief.rules or {})
    for key, rule in (("doublet_days_off", "stop_days_off"), ("service_plan", "service_plan")):
        if key not in answers:
            continue
        try:
            value = _read_json(key, answers[key])
        except (TypeError, ValueError) as err:
            out.errors[key] = f"Could not read it ({err})."
            continue
        if value != (rules.get(rule) or []):
            rules[rule] = value
            out.changed.append(key)
    if rules != dict(brief.rules or {}):
        brief = brief.model_copy(update={"rules": rules})
    return brief


RELAXED = "stops_relaxed"  # brief.rules: the cap was raised by code for the user's days off


def _relax_cap(brief: DesignBrief, out: "Edit", fixed_days: bool, dates=None) -> DesignBrief:
    """Raise the operating-days cap for the fewest days off a doublet has, or put it back.

    The fewest days off (a doublet's own length, or its dates' total) must leave the rest of the
    year to run: when it leaves more than the cap, the cap is raised to it ("relaxed by you"),
    marked so that it goes back to the challenge's when the days off no longer need it. A cap
    the user set on the same card (``fixed_days``) stands, and too few days off is said.
    """
    from gemini_agent import engine, parameters

    rules = dict(brief.rules or {})
    cap = int(engine.project_caps(brief).operating_days)
    ops = int(engine.rules_for(brief).operating_days)
    stops = dates if dates is not None else (brief.doublet_stops or [])
    offs = [int(d) for d in rules.get("stop_days_off") or [] if d]
    offs += [sum(b - a + 1 for a, b in d) for d in stops if d]
    need = stop_dates.DAYS - min(offs) if offs else None
    if need is not None and need > ops:
        if fixed_days:
            out.errors["doublet_days_off"] = (
                f"{min(offs)} days off is fewer than the {stop_dates.DAYS - ops} your "
                f"{ops} operating days leave."
            )
            return brief
        brief = parameters.apply(brief, {"operating_days": need})
        brief = brief.model_copy(update={"rules": dict(brief.rules or {}, **{RELAXED: True})})
        out.changed.append("operating_days")
    elif rules.get(RELAXED) and not fixed_days and (need is None or need <= cap) and ops != cap:
        # Raised by code earlier, no longer needed: the challenge's cap again.
        rules.pop(RELAXED, None)
        rules["operating_days"] = cap
        brief = brief.model_copy(update={"rules": rules})
        out.changed.append("operating_days")
    return brief


def read(answers: Dict[str, str], brief: DesignBrief, project) -> Edit:
    """Apply the card's changes and stop dates to the brief, each checked; say what was refused.

    Parameters
    ----------
    answers : dict
        The card's answers: ``changes`` (JSON: parameter key to the new value, in the
        catalogue's units) and ``doublet_stops`` (JSON: per doublet, [first, last] days).
    brief : DesignBrief
        The brief the card showed.
    project : ProjectData
        The project.

    Returns
    -------
    Edit
        The brief with what passed, the keys changed, and per key why a value was refused.
    """
    from gemini_agent import engine, parameters

    out = Edit(brief=brief)
    raw = answers.get("changes")
    edits: Dict[str, object] = {}
    if raw:
        try:
            edits = json.loads(raw)
        except (TypeError, ValueError):
            edits = None
        if not isinstance(edits, dict):
            out.errors["changes"] = "The card's changes could not be read: edit them again."
            edits = {}
    specs = {}
    for row in with_fields(_rows_stub(), brief, project):
        for spec in row.get("fields") or []:
            specs[spec["key"]] = spec
    now = _now(brief)
    kept: Dict[str, object] = {}
    for key, value in edits.items():
        spec = specs.get(key)
        if key == "aquifers" and spec is not None:  # records: checked as a list
            records, why, warns = aquifers.read_card(value, brief)
            if why:
                out.errors[key], out.asked[key] = why, value
            elif records is not None:
                kept[key] = records
            if warns and not why:
                out.warnings[key] = " ".join(warns)
            continue
        if spec is None:
            out.errors[key] = "Not an input the card can change: type the change instead."
            out.asked[key] = value
            continue
        if key == "n_doublets" and value in (ANY_DOUBLETS, None):
            if brief.n_doublets is not None:
                kept[key] = None
            continue
        why = _range_problem(spec, value)
        if why is None and key == "exclude":
            before, after = set(brief.excluded), set(value)
            for k, units in (
                ("exclude", sorted(after - before)),
                ("allow", sorted(before - after)),
            ):
                if units:
                    good, clean, why = _planner_check(k, units, now)
                    if not good:
                        break
                    kept[k] = clean
            if why:
                kept.pop("exclude", None)
                kept.pop("allow", None)
        elif why is None:
            if key in SCALED:
                value = float(value)
            good, clean, why = _planner_check(key, value, now)
            if good and clean is not None:
                kept[key] = clean
        if why:
            out.errors[key] = why
            out.asked[key] = edits[key]
    _cross_checks(kept, now, out, edits, float(engine.rules_for(brief).reservoir_depth_m))
    _known_into_aquifers(kept, brief)
    plain = {k: v for k, v in kept.items() if v is not None}
    brief = parameters.apply(brief, plain) if plain else brief
    if "n_doublets" in kept and kept["n_doublets"] is None:
        brief = brief.model_copy(update={"n_doublets": None})
    out.changed = sorted("exclude" if k == "allow" else k for k in kept)
    out.changed = sorted(set(out.changed))
    fixed_days = "operating_days" in kept
    brief = _read_maintenance(answers, brief, out, fixed_days)
    given = None
    if "doublet_stops" in answers:
        try:
            given = stop_dates.parse(answers["doublet_stops"])
        except (TypeError, ValueError) as err:
            out.errors["doublet_stops"] = f"The dates could not be read ({err})."
    # Fewer days off than the cap leaves is allowed: the cap is relaxed for them, and every
    # design still checked against the challenge's (``_relax_cap``).
    brief = _relax_cap(brief, out, fixed_days, given)
    if given is not None:
        why = stop_dates.check(given, int(engine.rules_for(brief).operating_days))
        if why:
            out.errors["doublet_stops"] = why
            out.asked["doublet_stops"] = given
        elif given != [list(map(list, d)) for d in (brief.doublet_stops or [])]:
            brief = brief.model_copy(update={"doublet_stops": given})
            out.changed.append("doublet_stops")
    out.changed = list(dict.fromkeys(out.changed))
    out.brief = brief
    return out


def _rows_stub() -> List[Dict[str, object]]:
    """Return a row per label of ``ROW_FIELDS`` (the fields a card can carry)."""
    return [{"label": label, "kind": "assumed"} for label in ROW_FIELDS]


def _known_into_aquifers(kept: Dict[str, object], brief: DesignBrief) -> None:
    """Put the Aquifer row's changes into the known aquifer's record when both rows changed.

    The aquifers list replaces the known aquifer's values in the brief: changed together, the
    Aquifer row's thickness, permeability or pressure goes into the list's known aquifer.
    """
    if "aquifers" not in kept:
        return
    known = aquifers.known_depth(brief)
    for key, rule in aquifers.KNOWN_RULES.items():
        if rule not in kept or rule == "gas_liquid_ratio":
            continue
        for r in kept["aquifers"]:
            if abs(float(r["depth_m"]) - known) < aquifers.SAME_DEPTH_M:
                r[key] = float(kept[rule])
        kept.pop(rule)
    kept["aquifers"] = kept.pop("aquifers")  # applied last


def _cross_checks(
    kept: Dict[str, object],
    now: Dict[str, object],
    out: Edit,
    edits: Dict[str, object],
    depth_m: Optional[float] = None,
) -> None:
    """Refuse the changes that make the inputs physically impossible (``impossible``)."""
    merged = {**now, **{k: v for k, v in kept.items() if v is not None}}
    for key, why in impossible(merged, depth_m).items():
        if key in kept:  # a value as it was is not this card's change
            out.errors[key] = why
            out.asked[key] = edits.get(key)
            kept.pop(key, None)


def impossible(values: Dict[str, object], depth_m: Optional[float] = None) -> Dict[str, str]:
    """Return what is physically impossible in a set of values (catalogue units), by key.

    A heating return at or above its supply, a cooling return at or below its supply, a lowest
    flow above the flow cap, a pump of 100 % or more, methane and CO₂ over 100 % of the gas, a
    pore pressure above the weight of the rock over the aquifer. A pair's message is on both
    its keys. The card's form (``inputsForm.ts``) checks the same as the user types; these
    block the run. ``depth_m``: the known aquifer's midpoint (2,500 m by default).
    """

    def num(key):
        try:
            return float(values[key])
        except (KeyError, TypeError, ValueError):
            return None

    out: Dict[str, str] = {}
    hs, hr = num("heat_supply_c"), num("heat_return_c")
    if hs is not None and hr is not None and hr >= hs:
        out["heat_return_c"] = (
            f"The return must be below the supply ({hs:g} °C): the water comes back cooler "
            "than it left."
        )
        out["heat_supply_c"] = f"The supply must be above the return ({hr:g} °C)."
    cs, cr = num("cool_supply_c"), num("cool_return_c")
    if cs is not None and cr is not None and cr <= cs:
        out["cool_return_c"] = (
            f"The return must be above the supply ({cs:g} °C): the water warms up in the "
            "buildings."
        )
        out["cool_supply_c"] = f"The supply must be below the return ({cr:g} °C)."
    lo, hi = num("flow_min_m3h"), num("flow_max_m3h")
    if lo is not None and hi is not None and lo > hi:
        out["flow_min_m3h"] = f"The lowest flow can't be above the flow cap ({hi:g} m³/h)."
        out["flow_max_m3h"] = f"The flow cap can't be below the lowest flow ({lo:g} m³/h)."
    eff = num("pump_efficiency")
    if eff is not None and eff >= 1.0:
        out["pump_efficiency"] = (
            "No pump turns all its electricity into lift: give less than 100 %."
        )
    ch4, co2 = num("gas_ch4_fraction"), num("gas_co2_fraction")
    if ch4 is not None and co2 is not None and ch4 + co2 > 1.0 + 1e-9:
        why = f"Methane and CO₂ make {(ch4 + co2) * 100:g} % of the gas: more than all of it."
        out["gas_ch4_fraction"] = out["gas_co2_fraction"] = why
    bar = num("reservoir_pressure_bar")
    depth = depth_m if depth_m is not None else 2500.0
    rock = ROCK_BAR_PER_M * depth
    if bar is not None and bar > rock:
        out["reservoir_pressure_bar"] = (
            f"More than the weight of the rock above the aquifer (about {rock:.0f} bar at "
            f"{depth:,.0f} m): the rock would crack open."
        )
    return out


def changed_words(keys: Sequence[str], brief: DesignBrief) -> str:
    """Return the card's changes in a few words, for the chat's record ("heating return 50 °C")."""
    from gemini_agent import parameters

    now = _now(brief)
    parts = []
    plain = {
        k: now.get(k)
        for k in keys
        if k in parameters.CATALOGUE and k not in ("exclude", "doublet_stops")
    }
    if plain:
        try:
            parts.append(parameters.label(plain))
        except (KeyError, TypeError, ValueError):
            parts.append(", ".join(plain))
    if "exclude" in keys:
        names = [UNIT_WORDS.get(x, x) for x in brief.excluded]
        parts.append("leave out " + (", ".join(names) if names else "nothing"))
    if "doublet_stops" in keys:
        parts.append(
            "doublet stops on your dates" if brief.doublet_stops else "doublet stops by Dioscuri"
        )
    if "doublet_days_off" in keys:
        days = [int(d) for d in (brief.rules or {}).get("stop_days_off") or []]
        parts.append("days off " + ", ".join(map(str, days)) if days else "35 days off")
    if "service_plan" in keys:
        parts.append("the units' service as you set it")
    return "; ".join(p for p in parts if p)


# ------------------------------------------------------------------ what the card says it did

# The names a refusal uses for a few keys whose catalogue labels are long.
NOTICE_NAMES = {
    "aquifer_depths_m": "Well depth",
    "n_doublets": "Doublets",
    "aquifers": "Aquifers",
}


def _notice_name(key: str) -> str:
    from gemini_agent import parameters

    p = parameters.CATALOGUE.get(key)
    if key in NOTICE_NAMES or p is None:
        return NOTICE_NAMES.get(key, key.replace("_", " "))
    return re.sub(r"\s*\(.*\)$", "", p.label)


def _asked_numbers(value: object) -> List[float]:
    """Return the numbers of a refused value as the reading gave it ("[100]", 4.0, [100])."""
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out += _asked_numbers(v)
        return out
    try:
        return _asked_numbers(json.loads(str(value)))
    except (TypeError, ValueError):
        return []


def refused_lines(
    errors: Dict[str, str],
    asked: Dict[str, object],
    unread: Sequence[Tuple[str, str]],
    brief: DesignBrief,
) -> List[str]:
    """Return what a typed change asked for and code refused, one plain line each.

    ``errors`` and ``asked``: a catalogue key's refusal on its merits and the value the message
    gave (``agent.refused_on_card``); ``unread``: the message's words code could not take and
    why (an aquifer list, stop dates, a value that crosses its pair, an add past the limit).
    A depth shallower than the range says how cool the brine is there.
    """
    from gemini_agent import engine, parameters

    rules = engine.rules_for(brief)
    lines: List[str] = []
    labels = []
    for key, why in errors.items():
        p = parameters.CATALOGUE.get(key)
        name = _notice_name(key)
        nums = _asked_numbers(asked.get(key))
        unit = "" if p is None or p.unit in ("", "x", "fraction") else f" {p.unit}"
        if key == "aquifers":
            unit = " m"  # a refused list of aquifers: their depths
        shown = ", ".join(f"{x:,.0f}" if abs(x) >= 1000 else f"{x:g}" for x in nums)
        what = f"{name} {shown}{unit}".strip() if shown else name
        if p is not None and str(why).strip().startswith("outside") and p.kind != "choice":
            why = f"outside {p.low:,.0f} to {p.high:,.0f}{unit}"
            if p.low >= 1:
                why = f"outside {p.low:,g} to {p.high:,g}{unit}"
        line = f"{what}: {str(why).strip()}"
        if key in ("aquifer_depths_m", "reservoir_depth_m") and nums and p is not None:
            shallow = [x for x in nums if x < p.low]
            if shallow:
                temp = rules.reservoir_temperature_c(min(shallow))
                line += (
                    f"; the brine at {min(shallow):,.0f} m is about {temp:.0f} °C, too cool to "
                    "heat the district"
                )
        lines.append(line + ".")
        if p is not None:
            labels.append(p.label.lower())
    for quote, why in unread:
        if any(str(why).lower().startswith(label) for label in labels):
            continue  # said above, from its key
        why = str(why).strip().rstrip(".")
        lines.append(f"“{quote}”: {why[0].upper() + why[1:] if why else why}.")
    return lines


def _doublets_words(brief: DesignBrief) -> str:
    n = len(brief.doublets) or brief.n_doublets
    if not n:
        return "the search picks 1 to 3 doublets"
    return f"{n} doublet{'s' if n != 1 else ''}"


def _aquifers_words(brief: DesignBrief) -> str:
    depths = [float(r["depth_m"]) for r in aquifers.value_of(brief)]
    shown = [f"{d:,.0f}" for d in depths]
    if not shown:
        return "no aquifer"
    if len(shown) == 1:
        return f"1 aquifer at {shown[0]} m"
    listed = ", ".join(shown[:-1]) + " and " + shown[-1]
    return f"{len(shown)} aquifers at {listed} m"


def refused_notice(
    lines: Sequence[str], brief: DesignBrief, title: str = "Nothing changed"
) -> Dict[str, object]:
    """Return the card's note for a typed change refused: nothing changed, what still stands.

    The values stay as they were until the user confirms something valid (5 Nov): the note
    says what was refused and why, what the card still holds, and what can be done. ``title``:
    "Not taken" for a request's refused values beside the ones it took.
    """
    return {
        "kind": "refused",
        "title": title,
        "lines": list(lines),
        "offer": (
            f"The card still has {_aquifers_words(brief)}, and {_doublets_words(brief)}. Change "
            "a value on the card, type another change, or run it as it is."
        ),
    }


# The card's switches in a few words, for what a reset put back.
SWITCH_NOUNS = {
    "network_length_km": "network heat losses",
    "maintenance": "the maintenance plan",
    "free_cooling": "free cooling",
    "grid_by_month": "the grid's CO₂ month by month",
    "solar_mwp": "solar panels",
    "storage_mwh": "the heat store",
    "storage_ates": "the seasonal store",
    "co2_reinjection": "the brine's CO₂ dissolved back",
    "flare_brine_gas": "flaring the brine's gas",
}


def reset_notice(before: DesignBrief, after: DesignBrief) -> Dict[str, object]:
    """Return the card's note after a reset: what went back to the project's own values."""
    from gemini_agent import parameters

    names: List[str] = []
    now, own = _now(before), _now(after)
    for label, fields in ROW_FIELDS.items():
        for key, name in fields:
            if key == "aquifers":
                if not aquifers.same(aquifers.value_of(before), aquifers.value_of(after)):
                    names.append(f"aquifers ({_aquifers_words(after)})")
                continue
            if not parameters._same(now.get(key), own.get(key)) and not (
                key == "n_doublets" and now.get(key) is None
            ):
                shown = name if name == label else f"{label.lower()} {name.lower()}"
                names.append(shown[0].lower() + shown[1:])
    a, b = _switches(before), _switches(after)
    for t in toggles(before):
        key = str(t["id"])
        if a.get(key) != b.get(key):
            names.append(SWITCH_NOUNS.get(key) or str(t["label"])[0].lower() + str(t["label"])[1:])
    if before.doublets and not after.doublets:
        names.append("the doublets you described")
    names = list(dict.fromkeys(names))
    return {
        "kind": "reset",
        "title": "Back to the project's defaults",
        "lines": ["Put back: " + "; ".join(names) + "."] if names else [],
        "offer": "Every input is the project's own value again: run it as it is, or change what "
        "you need first.",
    }
