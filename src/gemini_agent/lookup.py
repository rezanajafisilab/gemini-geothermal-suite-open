"""Lookup: answers to "what is the ..." questions from the project data and the latest design.

Every value the agent can report is a ``Fact`` that names its source (the project's files,
the user, a demand tool or a simulated design), so the answer says where the number comes
from and the grounding check knows it. Which values a question asks for comes from the intake
call (``asks_for``) and from the word patterns below, so a slip by the model on one side is
caught by the other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

_I = re.IGNORECASE
_RES = r"(reservoir|aquifer|formation)\w*"
ALIASES = {
    "reservoir_temp": re.compile(
        rf"{_RES}\s+(\w+\s+){{0,2}}temp|initial temp|how (hot|warm) is the {_RES}|"
        r"reservoirtemperatuur|temperatuur van het reservoir",
        _I,
    ),
    "reservoir_depth": re.compile(rf"{_RES}\s+(\w+\s+){{0,2}}depth|how deep is the {_RES}", _I),
    "heat_demand": re.compile(r"heat(ing)? demand|annual heat|yearly heat|warmtevraag", _I),
    "cool_demand": re.compile(r"(cool(ing)?|cold) demand|koudevraag", _I),
    "peak_heat": re.compile(r"peak (heat|heating)|heat(ing)? peak", _I),
    "peak_cool": re.compile(r"peak (cool|cooling|cold)|(cool(ing)?|cold) peak", _I),
    "heating_temps": re.compile(
        r"heating (network )?(temp|return|supply)|\bdh temp|\bheat(ing)? return", _I
    ),
    "cooling_temps": re.compile(
        r"cooling (network )?(temp|return|supply)|\bdc temp|\bcool(ing)? return", _I
    ),
    "wellhead_temp": re.compile(r"wellhead|production temp", _I),
    "reinjection_temp": re.compile(r"re-?inject|injection temp", _I),
    "hex_size": re.compile(r"heat exchanger|\bhex\b", _I),
    "heat_pump_size": re.compile(r"(size|capacity|how (big|large)).{0,20}heat[- ]?pump", _I),
    "heat_pump_cop": re.compile(r"\bcop\b|coefficient of performance", _I),
    "boiler_size": re.compile(r"(size|capacity|how (big|large)).{0,20}boiler", _I),
    "absorption_size": re.compile(r"(size|capacity|how (big|large)).{0,20}absorption", _I),
    "chiller_size": re.compile(r"(size|capacity|how (big|large)).{0,20}electric chiller", _I),
    "lcoh": re.compile(
        r"\blcoh\b|cost of (the )?heat(?! and)|heat cost|price of heat|heat (\w+ )?cost", _I
    ),
    "lcoe": re.compile(
        r"\blcoe\b|cost of (the )?heat and (the )?(cold|cooling)|heat and cold (together|combined)|"
        r"(combined|overall|average|total) cost per mwh",
        _I,
    ),
    "doublets": re.compile(r"how many doublets|number of doublets", _I),
    # The design's wells, not the known aquifer (2 Nov: 3,500 m wells, the aquifer at 2,500 m).
    "well_depth": re.compile(
        r"how deep (are|do|did|is)\b.{0,20}\b(wells?|doublets?|drill\w*|it|they)|"
        r"(well|drilling|drill) depth|depth of the (wells?|doublets?)|to what depth|"
        r"how (far|deep) .{0,15}drill",
        _I,
    ),
    "lcoc": re.compile(r"\blcoc\b|cost of (the )?(cold|cooling)|(cold|cooling) cost", _I),
    "capex": re.compile(r"capex|capital cost|investment", _I),
    "co2_saving": re.compile(r"co2|co₂|carbon|emission", _I),
    "heat_coverage": re.compile(r"heat coverage|cover\w* .{0,20}heat", _I),
    "cool_coverage": re.compile(r"(cold|cool\w*) coverage|cover\w* .{0,20}(cool|cold)", _I),
    "full_load_hours": re.compile(r"full[- ]load hours|load hours", _I),
    "heat_split": re.compile(
        r"(how much|share|part|fraction|percent|%).{0,50}\bheat\b.{0,40}"
        r"(from|by|boiler|heat pump|exchanger|gas|geotherm)|heat (by|per) source|"
        r"(where|what).{0,25}heat come|heat split|gas share|share of (gas|the boiler)|"
        r"heat (comes? )?from the (gas |electric )?boiler|"
        r"(boiler|heat pump|exchanger|doublet)s? (gives?|provides?|supplies|delivers?|makes?|"
        r"covers?|meets?) .{0,25}\bthe heat\b|"
        r"\b(boilers?|heat pumps?)\b.{0,15}\b(not|rather than|instead of|over)\b.{0,10}"
        r"\b(boilers?|heat pumps?)\b",
        _I,
    ),
    "co2_sources": re.compile(
        r"(co2|co₂|emission\w*).{0,30}(source|from|split|break|come)|"
        r"(source|origin)s? of .{0,12}(co2|co₂|emission)",
        _I,
    ),
    "gas_flows": re.compile(
        r"(produced|brine'?s?|bought|purchased|sold|flared|formation) gas|"
        r"gas (use|volume|flow|bought|sold|burnt|burned)|how much gas",
        _I,
    ),
    "well_checks": re.compile(
        r"injection pressure|sodm|bubble point|esp (depth|setting|head)|breakthrough|"
        r"cold (water|front).{0,30}(reach|arriv|get)|reach\w* the produc|thermal front|"
        r"productivity index|injectivity|pressure (at|in) the (well|reservoir)",
        _I,
    ),
    "cost_split": re.compile(
        r"(share|part|split|breakdown|much) of the (yearly |annual |total )?cost|"
        r"cost (split|breakdown|by part)|(what|where).{0,20}cost come|"
        r"(share|part|much).{0,25}(is|goes to|for) (capital|gas|electricity|o&m|co2)",
        _I,
    ),
    "investor": re.compile(
        r"investor|sde\+?\+?|subsid|\birr\b|net present|\bnpv\b|payback|corporate tax|"
        r"\bvpb\b|sale price|selling price|revenue",
        _I,
    ),
    "failure_costs": re.compile(
        r"(fail\w*|breakdown|outage)s?.{0,30}(cost|a year|per year)|spare esp|spare pump|"
        r"(worth|pay).{0,20}spare",
        _I,
    ),
    "electric_boiler_size": re.compile(
        r"(size|capacity|how (big|large)).{0,20}electric boiler|e-?boiler", _I
    ),
    "operating_days": re.compile(
        r"(days?|dagen).{0,40}\b(run|runs|running|operat\w*|on|active|in use|draait)\b|"
        r"(operating|running|active) days|how (long|often).{0,30}doublet|stop days|35 days|"
        r"\bstops?\b.{0,40}\bdoublet|doublet.{0,40}\bstops?\b|maintenance|onderhoud|wartung",
        _I,
    ),
}
FACT_KEYS = list(ALIASES)
# Facts too long for every design block: looked up when asked for.
LONG_FACTS = {
    "heat_split",
    "co2_sources",
    "gas_flows",
    "well_checks",
    "cost_split",
    "investor",
    "failure_costs",
}
# Facts a why-question about a design looks up first (its reason is added to the answer).
WHY_FACTS = {
    "heat_split",
    "co2_sources",
    "gas_flows",
    "cost_split",
    "operating_days",
    # "Why is the combined cost below the heat cost?" (2 Nov: refused for want of the costs).
    "lcoh",
    "lcoc",
    "lcoe",
}
# How a long fact opens in a lookup answer: "The the year's heat by source (...) is ..." read
# badly on 1 Nov.
HEADINGS = {
    "heat_split": "Heat over the year by source",
    "co2_sources": "CO2 over the year by source",
    "gas_flows": "Gas over the year",
    "well_checks": "Well checks",
    "cost_split": "The yearly cost by part",
    "investor": "The investor's view",
    "failure_costs": "Failure costs over a year",
}
# Values that exist before any design; the rest come from a simulated design.
PROJECT_KEYS = {
    "reservoir_temp",
    "reservoir_depth",
    "heat_demand",
    "cool_demand",
    "peak_heat",
    "peak_cool",
    "heating_temps",
    "cooling_temps",
}
LABELS = {
    "reservoir_temp": "initial reservoir temperature",
    "reservoir_depth": "reservoir depth",
    "heat_demand": "yearly heat demand",
    "cool_demand": "yearly cold demand",
    "peak_heat": "peak heat demand (daily mean)",
    "peak_cool": "peak cold demand (daily mean)",
    "heating_temps": "heating network supply and return",
    "cooling_temps": "cooling network supply and return",
    "wellhead_temp": "brine temperature at the wellhead",
    "reinjection_temp": "reinjection temperature",
    "hex_size": "heat exchanger size",
    "heat_pump_size": "heat pump size",
    "heat_pump_cop": "heat pump COP",
    "boiler_size": "peak boiler size",
    "absorption_size": "absorption chiller size",
    "chiller_size": "electric chiller size",
    "lcoh": "cost of heat",
    "lcoe": "cost of heat and cold together",
    "doublets": "number of doublets",
    "well_depth": "depth the design's wells are drilled to, and the aquifer each doublet is in",
    "lcoc": "cost of cold",
    "capex": "capital cost",
    "co2_saving": "CO₂ saving against gas",
    "heat_coverage": "share of the heat demand covered",
    "cool_coverage": "share of the cold demand covered",
    "full_load_hours": "full-load hours of the doublet",
    "operating_days": "days each doublet ran and when it stops (its yearly maintenance window)",
    "heat_split": "the year's heat by source (exchanger, heat pump, gas boiler, electric boiler)",
    "co2_sources": "the year's CO2 by source (gas bought, the brine's gas, electricity, sold gas)",
    "gas_flows": "gas over the year: the brine's gas burnt, flared or sold, and gas bought",
    "well_checks": (
        "the wells' pressures and checks (injection vs SodM, ESP depth, when cold water "
        "reaches the producer)"
    ),
    "electric_boiler_size": "electric boiler size",
    "cost_split": "the yearly cost by part (capital, gas, electricity, O&M, CO2) and each share",
    "investor": "the investor's view: sale prices, SDE++ (category, amount), tax, NPV, IRR",
    "failure_costs": "what failures cost a year and whether a spare ESP pays",
    "reservoir_inputs": "reservoir inputs",
}
QUESTION_START = re.compile(
    r"^\s*(what|which|how (hot|warm|deep|big|large|much|many|high|low)|is the|are the|tell me|"
    r"give me|wat|hoe|welke|hoeveel)\b",
    _I,
)
DESIGN_VERBS = re.compile(r"\b(design|size|compare|simulate|ontwerp|vergelijk)\b", _I)


@dataclass
class Fact:
    """One reportable value with its unit and where it came from.

    ``short``: a long value's headline in one line (the investor's NPV, IRR and payback), for
    the "In short" line that answers a question about it (``value_lines``).
    """

    key: str
    value: str
    source: str
    detail: str = ""
    short: str = ""


def wanted(message: str, asks_for: Sequence[str] = ()) -> List[str]:
    """Return the fact keys a question asks about, from the model's list and the word patterns.

    Parameters
    ----------
    message : str
        The user's message.
    asks_for : sequence of str
        Keys the intake model named; unknown keys are ignored.

    Returns
    -------
    list of str
        Known keys, the model's first, without repeats.
    """
    keys = [k for k in asks_for if k in ALIASES]
    found = [k for k, rx in ALIASES.items() if rx.search(message) and k not in keys]
    if "heat_split" in found and "heat_coverage" in found and "heat_coverage" not in keys:
        found.remove("heat_coverage")  # "the boiler covers 21 % of the heat": a unit's share
    return keys + found


def is_question(message: str) -> bool:
    """Return True for a request for values rather than for a design."""
    return bool(QUESTION_START.search(message)) and not DESIGN_VERBS.search(message)


def project_facts(project, brief, demand: Optional[dict]) -> Dict[str, Fact]:
    """Return the facts known before any design: reservoir, demand and network temperatures.

    Each fact says where it comes from and how: the challenge's requirements state the
    reservoir's depth, gradient and surface temperature, and Dioscuri works out the
    temperature from them; the networks' supplies are fixed there and their returns are
    assumed; a user's project states its own values.

    Parameters
    ----------
    project : ProjectData
        The project's data (which files it has, the reservoir it states).
    brief : DesignBrief
        What this conversation knows (the user's values override the project's).
    demand : dict, optional
        Output of the ``demand_summary`` tool.

    Returns
    -------
    dict of str to Fact
        Facts by key.
    """
    from gemini_agent import projects
    from gemini_agent.contract import NetworkTemps
    from gemini_agent.engine import DEFAULT_COOLING, DEFAULT_HEATING
    from gemini_agent.reporter import num

    challenge = getattr(project, "id", "challenge") == "challenge"
    pdf = next((f for f in project.files if f.lower().endswith(".pdf")), "the requirements")
    req = f"the challenge requirements ({pdf}"
    origin = f"{req}, section 3.1)" if challenge else f"the project {project.name} (as entered)"
    try:
        rules = projects.registry().rules(getattr(project, "id", "challenge"))
    except KeyError:  # a project removed since the conversation started
        rules = None
    out: Dict[str, Fact] = {}
    if brief.reservoir_temp_c is not None:
        from_project = project.has_reservoir and brief.reservoir_temp_c == project.reservoir_temp_c
        detail = "undisturbed, before production cools it"
        if brief.reservoir_depth_m:
            detail += f", at {num(brief.reservoir_depth_m, 0)} m"
        if brief.reservoir_delta_c:
            change = "warmer" if brief.reservoir_delta_c > 0 else "colder"
            detail += f"; the last what-if assumed {num(abs(brief.reservoir_delta_c))} °C {change}"
        source = origin if from_project else "you"
        if from_project and challenge and rules is not None:
            # The requirements give no temperature: it follows from their gradient.
            source = (
                f"worked out by Dioscuri from {req}, section 3.1), which gives no temperature "
                f"itself: reference surface temperature {num(rules.surface_temperature_c)} °C "
                f"+ geothermal gradient {num(rules.gradient_c_per_km)} °C/km × midpoint depth "
                f"{num(rules.reservoir_depth_m / 1000)} km"
            )
        out["reservoir_temp"] = Fact(
            "reservoir_temp", f"{num(brief.reservoir_temp_c)} °C", source, detail
        )
    if brief.reservoir_depth_m is not None:
        from_project = (
            project.has_reservoir and brief.reservoir_depth_m == project.reservoir_depth_m
        )
        out["reservoir_depth"] = Fact(
            "reservoir_depth",
            f"{num(brief.reservoir_depth_m, 0)} m",
            origin if from_project else "you",
            "midpoint, true vertical depth" if challenge and from_project else "",
        )
    if rules is not None and project.has_reservoir:
        out["reservoir_inputs"] = Fact(
            "reservoir_inputs",
            f"{num(rules.reservoir_pressure_bar)} bar, {num(rules.permeability_md)} mD, "
            f"{num(rules.reservoir_thickness_m)} m thick, {num(rules.gradient_c_per_km)} °C/km",
            origin,
            "pressure, permeability, gross thickness and geothermal gradient; other depths "
            "use hydrostatic pressure and the same gradient",
        )
    if demand:
        source = f"the demand profiles ({demand.get('source') or 'demand_summary'})"
        for key, field, unit in (
            ("heat_demand", "annual_heat_gwh", "GWh a year"),
            ("cool_demand", "annual_cool_gwh", "GWh a year"),
            ("peak_heat", "peak_heat_mw", "MW"),
            ("peak_cool", "peak_cool_mw", "MW"),
        ):
            out[key] = Fact(key, f"{num(demand[field])} {unit}", source)
    for key, temps, base in (
        ("heating_temps", brief.heating, getattr(project, "heating", None) or DEFAULT_HEATING),
        ("cooling_temps", brief.cooling, getattr(project, "cooling", None) or DEFAULT_COOLING),
    ):
        if temps is None:
            continue
        same = isinstance(base, NetworkTemps) and temps == base and project.has_heat_profile
        if same and challenge:
            source = (
                f"{req}, table 'Design and operating constraints') for the supply, which it "
                "fixes; the return is Dioscuri's assumption, since the requirements give none"
            )
        else:
            source = origin if same else "you"
        out[key] = Fact(key, temps.label(), source)
    return out


def design_facts(entry) -> Dict[str, Fact]:
    """Return the facts of a simulated design.

    Parameters
    ----------
    entry : LedgerEntry
        The design.

    Returns
    -------
    dict of str to Fact
        Facts by key; equipment the design does not have is left out.
    """
    from gemini_agent.reporter import num, pct

    y, e, alt = entry.year, entry.economics, entry.alternative
    source = f"{alt.code}, {alt.name} (simulate_year and economics, {y.source} tools)"
    values = {
        "wellhead_temp": (f"{num(y.wellhead_c)} °C", alt.depth_m > 0),
        "reinjection_temp": (f"{num(y.reinjection_c)} °C", alt.depth_m > 0),
        "hex_size": (f"{num(y.hex_mw, 2)} MW", y.hex_mw > 0),
        "heat_pump_size": (f"{num(y.heat_pump_mw)} MW", y.heat_pump_mw > 0),
        "heat_pump_cop": (
            f"{num(y.heat_pump_cop)} (Carnot limit {num(y.heat_pump_carnot_cop)})",
            y.heat_pump_mw > 0,
        ),
        "boiler_size": (f"{num(y.boiler_mw)} MW", y.boiler_mw > 0),
        "absorption_size": (f"{num(y.absorption_mw)} MW", y.absorption_mw > 0),
        "chiller_size": (f"{num(y.chiller_mw)} MW", y.chiller_mw > 0),
        "lcoh": (f"{num(e.lcoh_eur_per_mwh)} €/MWh", y.heat_delivered_gwh > 0),
        "lcoe": (f"{num(e.lcoe_eur_per_mwh or 0)} €/MWh", e.lcoe_eur_per_mwh is not None),
        "doublets": (str(alt.n_doublets), True),
        "well_depth": (_well_depth(entry), alt.n_doublets > 0),
        "lcoc": (f"{num(e.lcoc_eur_per_mwh or 0)} €/MWh", e.lcoc_eur_per_mwh is not None),
        "capex": (f"{num(e.capex_meur)} M€", True),
        "co2_saving": (pct(e.co2_saving_vs_gas), True),
        # With the energy behind the share: "100%" alone answered "how much heat does it
        # deliver, against the demand?" with no GWh (3 Nov, S62).
        "heat_coverage": (
            f"{pct(y.heat_coverage)} ({num(y.heat_delivered_gwh, 2)} of "
            f"{num(y.heat_demand_gwh, 2)} GWh a year)",
            True,
        ),
        "cool_coverage": (
            f"{pct(y.cool_coverage)} ({num(y.cool_delivered_gwh, 2)} of "
            f"{num(y.cool_demand_gwh, 2)} GWh a year)",
            y.cool_demand_gwh > 0,
        ),
        "full_load_hours": (f"{num(y.full_load_hours, 0)} h a year", alt.depth_m > 0),
        "operating_days": (
            _operating_days(y, entry.brief),
            alt.depth_m > 0 and bool(y.doublets),
        ),
        "heat_split": (_heat_split(y), bool(y.heat_split_gwh)),
        "co2_sources": (_co2_sources(y, e), bool(y.co2_t)),
        "cost_split": (_cost_split(e), bool(e.lines_heat or e.lines_cold)),
        "gas_flows": (_gas_flows(y), True),
        "well_checks": (_well_checks(y), alt.depth_m > 0),
        "electric_boiler_size": (
            f"{num((alt.sizes_mw or {}).get('electric_boiler', 0.0))} MW",
            bool((alt.sizes_mw or {}).get("electric_boiler")),
        ),
    }
    out = {k: Fact(k, v, source) for k, (v, present) in values.items() if present}
    if "co2_sources" in out and (y.co2_t or {}).get("total") is not None:
        out["co2_sources"].short = (
            f"{num(y.co2_t['total'], 0)} t of CO2 a year in all, {pct(e.co2_saving_vs_gas)} less "
            "than gas boilers and electric chillers"
        )
    return out


# ------------------------------------------------------------------ value answers written by code

# The "In short" line of a value asked for (``DIOSCURI_CODE_FACTS``): its name, shorter than the
# lookup's own label where that is a sentence.
LINE_LABELS = {
    "lcoe": "Cost of heat and cold together",
    "well_depth": "Well depth",
    "doublets": "Doublets",
    "co2_saving": "CO2 saving against gas",
    "heat_coverage": "Heat demand covered",
    "cool_coverage": "Cold demand covered",
    "full_load_hours": "Full-load hours of the doublet",
    "heat_split": "Heat over the year by source",
    "co2_sources": "CO2 over the year",
    "gas_flows": "Gas over the year",
    "cost_split": "Yearly cost by part",
    "investor": "Investor's view",
}
LINE_CHARS = 260  # a longer value (every well's checks, every failure) stays in the reply's words


def value_lines(keys: Sequence[str], sheet: Dict[str, Fact], entry) -> List[Tuple[str, str]]:
    """Return the "In short" lines for the values a question asks of a design, with their keys.

    Only values the design itself gives (``design_facts``, ``money_facts``; the source names
    the design), in the order asked, each with the design's id: "Cost of heat (A1 ·
    1D-HP-EC@3000-N1-FC): **64.7 €/MWh**". A value too long for one line and without a
    ``short`` headline is left to the reply. Nothing is added that was not asked.

    Parameters
    ----------
    keys : sequence of str
        The values asked for (the reading's ``asks_for``).
    sheet : dict of str to Fact
        What the lookup found (``_lookup``'s full sheet).
    entry : LedgerEntry, optional
        The design the question is about (the one the lookup read).

    Returns
    -------
    list of (str, str)
        Each line and the key it answers.
    """
    from gemini_agent.reporter import design_id

    if entry is None:
        return []
    code = entry.alternative.code
    name = design_id(entry)
    out: List[Tuple[str, str]] = []
    for key in dict.fromkeys(keys):
        fact = sheet.get(key)
        if fact is None or key in PROJECT_KEYS or not str(fact.source).startswith(code):
            continue
        value = " ".join(str(fact.short or fact.value).split()).rstrip(" .;")
        if not value or len(value) > LINE_CHARS:
            continue
        label = LINE_LABELS.get(key) or LABELS[key][:1].upper() + LABELS[key][1:]
        out.append((f"{label} ({name}): **{value}**", key))
    return out


def _heat_split(y) -> str:
    """Return the year's heat by source, in GWh and as shares of the heat delivered."""
    from gemini_agent.reporter import num, pct

    names = {
        "geo": "the geothermal heat exchanger",
        "hp": "the heat pump",
        "boiler": "the gas boiler",
        "electric_boiler": "the electric boiler",
    }
    split = {k: v for k, v in (y.heat_split_gwh or {}).items() if k in names and v and v > 0}
    total = sum(split.values()) or 1.0
    parts = [f"{names[k]} {num(v)} GWh ({pct(v / total)})" for k, v in split.items()]
    return "; ".join(parts) + f" of {num(total)} GWh of heat a year"


COST_PARTS = (
    ("capital", "capital (each unit's annuity)"),
    ("gas", "gas bought"),
    ("electricity", "electricity"),
    ("om", "O&M (fixed and variable)"),
    ("carbon", "CO2 at the carbon price"),
)


def _cost_split(e) -> str:
    """Return the year's cost of heat and cold by part, in M€ and as a share of the total.

    The brine's gas sold is a revenue: said apart as a credit, not as a share of the cost.
    """
    from gemini_agent.reporter import num, pct

    parts: Dict[str, float] = {}
    credit = 0.0
    for item, kind, m in list(e.lines_heat or []) + list(e.lines_cold or []):
        m = float(m)
        if m < 0:
            credit -= m
            continue
        part = "om" if kind in ("fixed", "variable") else str(kind)
        parts[part] = parts.get(part, 0.0) + m
    total = sum(parts.values())
    if not total:
        return ""
    named = dict(COST_PARTS)
    out = [
        f"{named.get(k, k)} {num(v, 2)} M€ ({pct(v / total)})"
        for k, v in sorted(parts.items(), key=lambda kv: -kv[1])
        if v >= 0.005
    ]
    text = f"{num(total, 2)} M€ a year in all: " + "; ".join(out)
    if credit:
        text += (
            f"; less {num(credit, 2)} M€ a year for the brine's gas sold (net "
            f"{num(total - credit, 2)} M€)"
        )
    return text


def _co2_sources(y, e) -> str:
    """Return the year's CO2 by source (and the sold gas's, which is the buyer's)."""
    from gemini_agent.reporter import num, pct

    c = y.co2_t or {}
    out = (
        f"gas bought {num(c.get('purchased_gas', 0), 0)} t; the brine's own gas (burnt, flared "
        f"or its CO2 let out) {num(c.get('produced_gas', 0), 0)} t; grid electricity "
        f"{num(c.get('electricity', 0), 0)} t; total {num(c.get('total', 0), 0)} t a year "
        f"({pct(e.co2_saving_vs_gas)} less than gas boilers and electric chillers)"
    )
    if c.get("methane_slip_co2e"):
        out += (
            f"; the flare lets {num(c['methane_slip_co2e'], 0)} t CO2-equivalent of methane "
            "through unburnt (2 % of what it flares; not in the CO2 total)"
        )
    if c.get("upstream_gas_co2e"):
        out += (
            f"; producing and shipping the gas bought adds about "
            f"{num(c['upstream_gas_co2e'], 0)} t CO2-equivalent a year before it reaches the "
            "plant (54 kg per MWh, co2emissiefactoren.nl; a life-cycle figure, not in the total)"
        )
    if (getattr(y, "solar", None) or {}).get("used_gwh"):
        out += (
            f"; the plant's own solar panels give {num(y.solar['used_gwh'], 1)} GWh of its "
            "electricity, which the grid's CO2 is not counted on"
        )
    if c.get("reinjected"):
        out += (
            f"; the brine's own CO2, {num(c['reinjected'], 0)} t a year, is dissolved back into "
            "the injected brine instead of let out (not counted)"
        )
    if c.get("sold_gas_elsewhere"):
        out += (
            f"; the methane sold to the grid gives {num(c['sold_gas_elsewhere'], 0)} t a year "
            "when the buyer burns it, which is not counted in this plant's total"
        )
    return out


def _gas_flows(y) -> str:
    """Return what happens to gas over the year: the brine's burnt, flared or sold; bought."""
    from gemini_agent.reporter import num

    return (
        f"the brine's gas burnt in the boiler {num(y.produced_gas_burned_gwh or 0)} GWh, flared "
        f"{num(y.produced_gas_flared_gwh or 0)} GWh, sold to the grid "
        f"{num(getattr(y, 'produced_gas_sold_gwh', 0) or 0)} GWh; gas bought "
        f"{num(y.purchased_gas_gwh or 0)} GWh a year (energy of the methane, LHV)"
    )


def _well_checks(y) -> str:
    """Return each doublet's pressures and subsurface checks, from the doublet summary."""
    from gemini_agent.reporter import num

    rows = (y.plant or {}).get("doublets") or []
    out = []
    for d in rows:
        out.append(
            f"doublet {d.get('doublet')}: injection wellhead {num(d.get('injection_full_bar', 0))} "
            f"bar and at the top of the reservoir {num(d.get('injection_top_bar', 0))} bar "
            f"against SodM's limit of {num(d.get('injection_limit_bar', 0))} bar (0.135 bar/m); "
            f"ESP head {num(d.get('esp_head_full_bar', 0))} bar, set at "
            f"{num(d.get('esp_setting_m', 0), 0)} m so its intake stays above the gas bubble point "
            f"of {num(d.get('bubble_point_bar', 0))} bar (plus 5 bar); cold water reaches the "
            f"producer after {num(d.get('breakthrough_years', 0))} years (Gringarten-Sauty, "
            "1.5 km spacing, porosity 0.20; the life is 30); productivity index "
            f"{num(d.get('pi_m3h_per_bar', 0))} m3/h/bar; brine cooled by at most "
            f"{num(d.get('max_cooling_k', 0))} K"
        )
    return "; ".join(out)


def _well_depth(entry) -> str:
    """Return how deep the design's wells go, and whether that is the known aquifer."""
    from gemini_agent import aquifers, engine
    from gemini_agent.reporter import num

    a = entry.alternative
    rules = engine.rules_for(entry.brief)
    known = rules.reservoir_depth_m
    each = [float(d.get("depth_m") or a.depth_m) for d in a.doublets or []] or [a.depth_m]
    depths = sorted(set(each))
    out = []
    for d in depths:
        if abs(d - known) < 1:
            where = "the known aquifer"
        elif rules.aquifer_index(d):  # described by the user: its own rock and gas
            out.append(aquifers.label(d, entry.brief, rules))
            continue
        else:
            where = (
                f"an assumed aquifer {num(d - known, 0)} m below the known one at "
                f"{num(known, 0)} m, with its properties taken as the same"
            )
        out.append(f"{num(d, 0)} m ({where})")
    text = " and ".join(out)
    if len(depths) > 1:  # which doublet is in which
        text += "; " + ", ".join(f"doublet {k} at {num(d, 0)} m" for k, d in enumerate(each, 1))
    return text


def _operating_days(y, brief=None) -> str:
    """Return how many days each doublet ran, with its stop windows and the cap."""
    from gemini_agent import stops as stop_dates
    from gemini_agent.reporter import num

    ranges = stop_dates.ranges_of(y)
    parts = []
    for i, d in enumerate(y.doublets or []):
        on = sum(1 for flag in d.get("on", []) if flag)
        mine = ranges[i] if i < len(ranges) else []
        window = f", stopped {stop_dates.span_words(mine)}" if mine else ""
        parts.append(f"doublet {i + 1}: {num(on, 0)} days{window}")
    said = stop_dates.summary(y, brief)
    tail = f"; its stops: {said}" if said else ""
    # Why the stop sits where it does: the heat demand there against the year's (2 Nov: "why
    # is the maintenance stop where it is?" had no answer).
    demand = list(((y.daily_mw or {}).get("heat") or {}).get("demand") or [])
    first = ranges[0][0] if ranges and ranges[0] else None
    if demand and first is not None and not stop_dates.users(brief, 0):
        a, b = first
        inside = sum(demand[a : b + 1]) / max(1, b - a + 1)
        tail += (
            f". The stop is where the heat demand is lowest: {num(inside)} MW a day on average "
            f"over {stop_dates.span_words([first])}, against {num(sum(demand) / len(demand))} MW "
            f"over the year and {num(max(demand))} MW at the peak, so the boiler covers the "
            "least while the doublet is off"
        )
    return (
        "; ".join(parts)
        + ". A doublet runs only when its brine is needed (the fewest that carry the flow), "
        + "at most 330 days a year (the cap)"
        + tail
    )


def money_facts(entry, assumptions: Optional[dict] = None) -> Dict[str, Fact]:
    """Return the investor's figures and what failures cost a year, as facts for a lookup.

    Both are computed by code (``dioscuri_plant.investor``, ``failure_costs``); on 1 Nov the chat
    said "my plant model has no input for these financial variables" while the tab showed them.
    """
    from gemini_agent import reliability, workbench
    from gemini_agent.reporter import num, pct

    out: Dict[str, Fact] = {}
    alt = entry.alternative
    if not alt.depth_m:
        return out
    source = f"{alt.code}: Dioscuri's investor case and failure economics (code)"
    try:
        v = (workbench.economics_view(entry, assumptions or {}) or {}).get("investor")
    except Exception:  # noqa: BLE001 - a design without an investor case answers without it
        v = None
    if v:
        sde, wo = v.get("sde") or {}, v.get("without_sde") or {}
        cat = (sde.get("category") or {}).get("name", "")
        out["investor"] = Fact(
            "investor",
            f"heat sold at {num(v['heat_sale_eur_per_mwh'])} €/MWh and cold at "
            f"{num(v['cold_sale_eur_per_mwh'])} €/MWh (the gas alternative's own costs); SDE++ "
            f"category {cat} at {num(sde.get('basis_eur_per_kwh', 0) * 1000)} €/MWh, paid on "
            f"{num(sde.get('subsidised_gwh', 0))} GWh a year, {num(sde.get('meur_first_year', 0))} "
            f"M€ in year 1 and {num(sde.get('meur_average', 0))} M€ a year on average over 15 "
            f"years; corporate tax {num((v.get('tax') or {}).get('total_meur', 0))} M€ over "
            f"{v['years']} years; NPV after tax {num(v['npv_meur'])} M€, IRR {pct(v['irr'])} real, "
            f"payback {num(v['payback_years'])} years; without SDE++ NPV "
            f"{num(wo.get('npv_meur', 0))} M€, IRR {pct(wo.get('irr') or 0)}, payback "
            f"{num(wo.get('payback_years') or 0)} years",
            source,
            short=f"NPV after tax {num(v['npv_meur'])} M€, IRR {pct(v['irr'])} real, payback "
            f"{num(v['payback_years'])} years (with SDE++)",
        )
    note = reliability.failure_costs_note(entry)
    if note:
        # The note opens with its own heading ("Failures over a year (...): ..."), which the
        # lookup answer gives already.
        body = re.sub(r"^Failures over a year\s*", "", note).rstrip(" .")
        body = re.sub(r"^\(([^()]*)\):\s*", r"\1. ", body)
        out["failure_costs"] = Fact("failure_costs", body, source)
    return out


# What a premise is about beyond the lookup patterns ("since you used 3 doublets"); not used
# to route questions, where "design with 2 doublets" is a request.
PREMISE_ALIASES = {
    "doublets": re.compile(r"\b\d+\s+doublets?\b", _I),
    # "The doublet runs all 365 days", "never stops", "every day of the year" (2 Nov: answered
    # with the full-load hours).
    "operating_days": re.compile(
        r"\b\d+\s+days\b|every day|all year|all the year|never stops|non-?stop|"
        r"(run|runs|running|operat\w*)\b.{0,30}\b(days?|year)\b",
        _I,
    ),
}
# Counts said in words, so "since you went with two doublets" is checked like "2 doublets"
# (2 Nov: the reply went on about "the two doublets" of a one-doublet design).
COUNT_WORDS = {
    "one": 1,
    "single": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "twee": 2,
    "drie": 3,
    "vier": 4,
    "zwei": 2,
    "drei": 3,
}


def _counts_as_digits(text: str) -> str:
    """Return text with counts in words as digits ("two doublets" → "2 doublets")."""
    words = "|".join(COUNT_WORDS)
    return re.sub(
        rf"\b({words})\b", lambda m: str(COUNT_WORDS[m.group(1).lower()]), text, flags=re.I
    )


def _close(x: float, y: float) -> bool:
    return abs(x - y) <= max(0.051, 0.005 * abs(y))


def premise_checks(
    premises: Sequence[str], sheet: Dict[str, Fact], keys: Sequence[str] = ()
) -> Tuple[str, List[str]]:
    """Return a correction of the premises a fact contradicts, and each paired with its facts.

    The pairs go to the answering model, which judges what code cannot.

    "The cost of heat is 69.8, correct?" gives "**Not quite.** The cost of heat is 75.7 €/MWh;
    69.8 €/MWh is the cost of heat and cold together." Only single values are judged by code; a
    premise about a long fact ("the boiler gives about a quarter") is left to the model, paired
    with that fact.
    """
    from gemini_agent.intake import numbers_in

    def about(p: str) -> List[str]:
        out = [
            k
            for k in sheet
            if (k in ALIASES and ALIASES[k].search(p))
            or (k in PREMISE_ALIASES and PREMISE_ALIASES[k].search(p))
        ]
        if "heat_split" in out:
            # A unit's share of the heat ("the gas boiler covers about 21 % of the heat") is
            # not the plant's coverage (4 Nov: "Not quite. ... covered is 100%").
            out = [k for k in out if k != "heat_coverage"]
        return out

    def unit(value: str) -> str:
        return re.sub(r"^[\d.,\s]+", "", value).strip()

    def by_unit(p: str) -> List[str]:
        """Return the one fact with the unit of a figure the premise states, if only one has it.

        "The aquifer sits at 3,500 m and 120 °C" names no fact by its words, but its "m" and
        "°C" are each the unit of one fact before a design (4 Nov); with several facts in a unit
        (MW after a design) nothing is paired, so nothing is guessed.
        """
        out = []
        for m in re.finditer(r"(\d[\d,.]*)\s*(°C|GWh|MWh|MW|M€|m³/h|m3/h|km|m)\b", p):
            same = [
                k
                for k, f in sheet.items()
                if k not in LONG_FACTS
                and len(str(f.value)) < 40
                and (unit(str(f.value)).split() or [""])[0] == m.group(2)
            ]
            if len(same) == 1 and same[0] not in out:
                out.append(same[0])
        return out

    # Matched with counts as digits; quoted to the model as the user wrote them.
    said_as = {_counts_as_digits(p): p for p in premises}
    claimed = {k for p in said_as for k in about(p)}
    lead: List[str] = []
    notes: List[str] = []
    for p, words in said_as.items():
        # A premise no pattern places is paired with the asked values no other premise took,
        # else by the unit of its figures.
        mine = about(p) or [k for k in keys if k in sheet and k not in claimed]
        each = not mine  # paired by unit: every figure is judged against its own fact
        mine = mine or by_unit(p)
        if not mine:
            notes.append(f"“{words}”")
            continue
        notes.append(
            f"“{words}” against "
            + "; ".join(f"{HEADINGS.get(k, LABELS[k])}: {sheet[k].value}" for k in mine[:2])
        )
        said = numbers_in(p)
        for k in mine:
            value = str(sheet[k].value)
            have = numbers_in(value)
            if k in LONG_FACTS or not said or not have:
                continue
            if any(_close(x, y) for x in said for y in have):
                continue
            # The user's number may be another value of the same kind (69.8 €/MWh is the cost
            # of heat and cold, not of heat).
            other = [
                k2
                for k2, f in sheet.items()
                if k2 != k
                and k2 not in LONG_FACTS
                and len(str(f.value)) < 40
                and unit(str(f.value)) == unit(value)
                and any(_close(x, y) for x in said for y in numbers_in(str(f.value)))
            ]
            text = (
                f"Each doublet's year: {value}"
                if k == "operating_days"
                else f"The {LABELS[k]} is {value}"
            )
            if other:
                text += f"; {sheet[other[0]].value} is the {LABELS[other[0]]}"
            lead.append(text + ".")
            if not each:
                break
    return ("**Not quite.** " + " ".join(dict.fromkeys(lead))) if lead else "", notes
