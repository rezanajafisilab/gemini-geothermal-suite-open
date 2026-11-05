"""Answerer: the model reads the question and writes the reply; code checks what it wrote.

Every chat reply is written by a model from a context pack (``Block``): who Dioscuri is (the
self card in ``prompts/self_v3.md``), the project's data, the simulated designs, the recent
turns, document passages and, after a tool run, the checked template answer (the draft). The
model returns what it understood, what kind of reply it is (an answer, a multiple-choice
clarification, "this is not a proper question", or "outside what I do"), the reply itself, the
blocks it relied on and a few follow-up questions.

Code then checks the reply:

- every number must come from a block or the user, or be a difference or ratio of two numbers
  the reply itself states (small counts such as "2 options" are allowed);
- the key values of the draft must still be there; when the model dropped one, the draft's
  sentence that carries it is added back;
- a reply that fails gets one retry that names the problem; after that, sentences with an
  unsourced number are dropped, and when too little is left the template is shown instead.

The template is also what the user sees when no model answers, so a stopped model server never
leaves a turn without a reply.
"""

from __future__ import annotations

import itertools
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from gemini_agent import aquifers, reporter
from gemini_agent.intake import PROMPT_DIR, numbers_in
from gemini_agent.llm import (
    LLMCall,
    LLMError,
    ModelUnavailable,
    estimate_tokens,
    prompt_tokens,
    room,
)

# v5: v4 for the challenge engine (no stand-in tools left); v7: the chat's thread (4 Nov).
ANSWER_PROMPT = "answer_v7"
SELF_CARD = "self_v3"  # v2: the challenge engine and projects (v1 described the toy model)
# "unclear": no request or question can be read (cut off, garbled, a bare number); the agent
# asks what was meant, in one reply for all of them (4 Nov: refused, "nonsense" or run).
KINDS = ("answer", "clarify", "unclear", "out_of_scope")
SCOPES = ("project", "general", "out")
# Files whose passages are GEMINI's own documentation and code; the team's notes are plans.
GEMINI_SOURCES = ("src/gemini_documentation", "src/gemini_model", "src/gemini_simulator")
UNITS = re.compile(
    r"\s*(%|°|K\b|MW|kW|GW|GWh|MWh|kWh|€|EUR|M€|km\b|m\b|h\b|hours?|years?|bar|kg|t\b|l/s|m3)",
    re.I,
)
NUM_PREDICT = 1400  # a report-length answer in JSON; 800 cut some off (31 Oct)
# Thinking on hard turns (``DIOSCURI_THINK``, 4 Nov). With a JSON format and a budget, qwen3.5:9b
# thought through all 3,448 tokens of a trade-off question and wrote no JSON (70 s, 11434), so
# the model thinks in a call of its own, cut at this many tokens, and the answer call reads the
# thinking as notes (the prompt keeps room for them).
THINK_TOKENS = int(os.environ.get("DIOSCURI_THINK_TOKENS", "1024"))
THINK_NOTES = (
    "Your notes from thinking it through (the user does not see them; they may stop "
    "mid-sentence; every number in your reply must still come from the context):\n{notes}\n\n"
    "Now write the JSON."
)
# The answer's whole prompt at most, whatever the window: a 16k window is room against a short
# estimate, not leave for a longer prompt (prompt time and tokens count; ``router``).
MAX_PROMPT_TOKENS = 7600
ANSWER_CHARS = 1600
# A citation the model writes after a sentence: "[doc1]", "[A1]", "[data1, doc2]".
CITE_ID = re.compile(r"\s?\[((?:[A-Za-z][\w .-]{0,30}?)(?:\s*,\s*[A-Za-z][\w .-]{0,30}?)*)\]")
# What the chat gets instead: "[^1]", the source card's number.
CITE_MARK = re.compile(r"\[\^\d+\]")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
# The prompt's own parts, which the user never sees ("the context block", "the draft").
INTERNALS = re.compile(
    r"\b(context|draft|data|history|project|self|note|doc) blocks?\b|\bin the context\b|"
    r"\bthe context (says|shows|lists|gives)\b|"
    # "The text states: ...", "the provided data" (1 Nov): the user never saw a text.
    r"\bthe (text|data|sources?|context) (explicitly |also |clearly )?(states?|says|shows|lists|"
    r"gives|"
    r"describes|mentions|quantifies|implies|highlights|notes|indicates|suggests|confirms|"
    r"specifies|reports)\b|\bthe provided (text|data|context)\b|"
    r"\bthe draft\b|\bdraft (values|answer|section)\b",
    re.I,
)
# A sentence that says something cannot be computed or is not there: false when a tool ran.
REFUSAL = re.compile(
    r"\b(cannot|can't|can not|unable to)( yet| currently| now| really)? (calculate|compute|run|"
    r"model|determine|answer|say|switch|turn|enable|include|add|apply|vary)\b|"
    r"\bnot (currently |yet )?modell?ed in this design\b|\bplease enable\b|"
    r"\b(does not|doesn't|do not) (include|model|cover|support)\b|"
    r"\bwithout running a new simulation\b|\bnot available to (switch|turn)\b|"
    r"\bno (data|information) (on|about|for)\b",
    re.I,
)
# A sentence that says Dioscuri did or is doing something: true only when a tool ran.
ACTION_CLAIM = re.compile(
    # Not a run still to come ("Before I run the design, please check ...", "shall I run it?").
    r"(?<!before )(?<!if )(?<!when )(?<!once )(?<!shall )(?<!should )(?<!can )(?<!could )"
    r"(?<!will )(?<!let me )"
    r"\bI(?:'ve| have)? (?:now |just |already )?(?:run|ran) (?:a |the |it|another |new |fresh |"
    r"this |that )|"
    r"\bI(?:'ve| have)? (?:now |just |already )?(?:updated|changed|set|switched|started|"
    r"re-?ran)\b|"
    r"\bI(?:'m| am) (?:now )?(?:running|sizing|designing|updating|starting|re-?running)\b",
    re.I,
)
# A template that reports a run: a claim of one is then true ("I tried 69 plant layouts", a
# what-if's "with its present sizes", "Searching again under the change").
TOOL_RAN = re.compile(
    r"\bI (tried|searched|sized|simulated)\b|\bwith its present sizes\b|\bsearching again\b|"
    r"\bthe search picks\b",
    re.I,
)
# A sentence of the model's own working, written into the answer instead of an answer.
WORKING = re.compile(
    r"^\W*(wait\b|let'?s re-?read|let me (re-?read|check|look|think|re-?check)|"
    r"the (prompt|user) (asks|says|wants)|hmm\b|okay,? so\b|actually,? let|actually,|"
    r"let'?s (break|look|find|work|calculate|check)|to find the\b|we (must|need to) "
    r"(convert|find|calculate|look))",
    re.I,
)
LINE_LEAD = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+|#{1,4}\s+|>\s*)")
# "Based on the provided text, …": a lead-in about the prompt, cut (the sentence stays).
CONTEXT_LEAD = re.compile(
    r"\b(?:based on|according to|from) (?:the )?(?:provided |given )?"
    r"(?:text|context|sources|information|data provided)\s*[,:]\s*",
    re.I,
)
# A rule line tagged "{kind}" goes to the model only with a block of that kind; "{open}" lines
# only when the reply may be more than an answer, "{closed}" only when it may not.
RULE_TAG = re.compile(r"^\{(\w+)\}")
# A message about Dioscuri itself gets the whole self card; others get one line.
ABOUT_US = re.compile(
    r"\b(you|your|yourself|dioscuri|instructions?|how (do i|to) use|help|features?|"
    r"capabilit\w*|limitations?|advantages?|strengths?|weakness\w*|jij|jouw|uw)\b",
    re.I,
)
# A message about the designs gets their full blocks; others get one line per design.
DESIGN_TALK = re.compile(
    r"\b(A\d|D\d|designs?|options?|alternatives?|cost\w*|price|lcoh|lcoc|cheap\w*|"
    r"expensive|co2|co₂|emission\w*|heat pumps?|doublets?|boilers?|chillers?|absorption|"
    r"coverage|covers?|covered|results?|compar\w*|better|best|worse|why|interpret\w*|"
    r"recommend\w*|saving\w*|capex|capital|cop|sizes?|capacity|full-load|split|share|"
    r"ontwerp\w*|kosten)\b",
    re.I,
)
# Who computed a design, as the answerer is told (and repeats).
SOURCES = {
    "gemini+dioscuri_plant": "the wells' pressures and pumps (ESP head, injection pressure) by "
    "GEMINI's well solve (with the team's fixes and the challenge's brine); the productivity "
    "index (from k·h), the heat lost up the well (Ramey), the subsurface checks and the plant "
    "over the year, its checks and costs by Dioscuri's own models, day by day",
    "dioscuri_plant": "Dioscuri's plant model, day by day (no wells: the gas reference)",
}
# Models that can look at an image (Ollama tags).
VISION = re.compile(r"qwen3\.5|qwen2\.5vl|vl\b|vision|llava|gemma3|minicpm-v", re.I)


@dataclass
class Block:
    """One piece of context the model may use and cite.

    Attributes
    ----------
    id : str
        What the model cites (``self``, ``project``, ``A1``, ``doc1``, ``draft`` ...).
    kind : str
        ``self``, ``project``, ``design``, ``facts``, ``draft``, ``result``, ``history``,
        ``doc`` (GEMINI's documentation), ``note`` (the team's notes), ``file`` (a passage of
        an upload) or ``data`` (a file the agent opened and the chat shows).
    text : str
        The content, already trimmed.
    title : str
        Short label (a file and section for passages).
    passage : dict, optional
        The search hit behind a ``doc``, ``note`` or ``file`` block (or the opened file behind
        a ``data`` block), for its source card.
    image : str, optional
        An image file the model sees with the block (vision models only).
    columns : tuple of str
        An opened table's column names: a table in the reply with these columns is a copy of
        the file's rows, which the chat already shows.
    """

    id: str
    kind: str
    text: str
    title: str = ""
    passage: Optional[dict] = None
    image: Optional[str] = None
    columns: Tuple[str, ...] = ()

    def render(self) -> str:
        """Return the block as the prompt shows it."""
        title = f", {self.title}" if self.title else ""
        return f"[{self.id}] ({self.kind}{title}) {self.text}"


@dataclass
class Reply:
    """What the answerer decided and wrote, after the code checks."""

    text: str
    kind: str = "answer"
    scope: str = "project"
    understood: str = ""
    used: List[str] = field(default_factory=list)
    follow_ups: List[str] = field(default_factory=list)
    options: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    calls: List[LLMCall] = field(default_factory=list)
    fallback: bool = False
    unavailable: str = ""
    note: str = ""
    # The correction of the user's premise that leads the reply (code's or the model's): the
    # claim checker leaves it, its numbers are checked already ("Not quite. ... 38 €/MWh was not
    # stated", which no source records, was removed as unsupported on 4 Nov).
    lead: str = ""
    claims: Optional[dict] = None
    # "design": the model judged that the message asks for a design run (the reader missed it);
    # the agent runs the design instead of showing this reply.
    action: str = "none"

    def meta(self) -> dict:
        """Return what the answer step row shows."""
        out = {
            "decided_by": "rules" if self.fallback else "model",
            "understood": self.understood,
            "kind": self.kind,
            "scope": self.scope,
        }
        for key in ("steps", "corrections", "note"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        if self.action != "none":
            out["action"] = self.action
        return out


def load(name: str) -> str:
    """Return a prompt or card from ``prompts/`` (``.txt`` or ``.md``)."""
    for suffix in (".txt", ".md"):
        path = PROMPT_DIR / f"{name}{suffix}"
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(name)


# ------------------------------------------------------------------ the blocks


def about_us(message: str) -> bool:
    """Return True when a message asks about Dioscuri (a polite "could you" does not count)."""
    from gemini_agent.intake import POLITE

    return bool(ABOUT_US.search(POLITE.sub("", message)))


def short_self(models: str = "") -> Block:
    """Return the one-line self note used when the message is not about Dioscuri."""
    text = (
        "Dioscuri designs geothermal heating and cooling for a district on TNO's GEMINI "
        "digital twin."
    )
    return Block("self", "self", text + (" Models in use now: " + models if models else ""))


def designs_line(entries: Sequence[object], chosen=None) -> Block:
    """Return the designs so far in one line each, for turns that are not about them."""
    parts = []
    for e in entries:
        tag = ", chosen" if e is chosen else ""
        tag += ", what-if" if e.brief.reservoir_delta_c else ""
        checks = e.verification.checks
        passed = sum(c.passed for c in checks)
        parts.append(
            f"{e.alternative.code} ({e.alternative.name}{tag}): "
            f"{reporter.num(e.economics.lcoh_eur_per_mwh)} €/MWh heat, "
            f"{reporter.pct(e.year.heat_coverage)} of the heat covered, "
            + (
                f"passed all {len(checks)} physics and cap checks"
                if passed == len(checks)
                else f"failed {len(checks) - passed} of {len(checks)} checks: "
                + "; ".join(c.name for c in checks if not c.passed)
            )
        )
    src = "; ".join(sorted({SOURCES.get(e.year.source, e.year.source) for e in entries}))
    return Block(
        "designs", "design", f"Designs simulated so far ({src}): " + "; ".join(parts) + "."
    )


# A question about money: the design's cost lines go to the answerer.
COST_TALK = re.compile(
    r"€|eur\b|euro|cost|price|lcoh|lcoc|lcoe|capex|opex|cheap|expensive|afford|payback|npv|"
    r"money|budget|invest|saving|save|per home|per house|bill|subsid|sde|gas reference|"
    r"than gas|kosten|prijs|goedkoper|duurder|besparing|investering",
    re.I,
)


def money_lines(entry, assumptions: Optional[dict] = None) -> List[str]:
    """Return the money facts a client asks for, computed by code: totals, gas, payback, prices.

    The gas reference (gas boilers and electric chillers for the same demand), the yearly
    totals, the extra investment against it, the yearly saving, the discounted payback and the
    NPV, the prices in force, and what the costs leave out. Without these the model made up a
    gas cost and said gas was cheaper (31 Oct).
    """
    from gemini_agent import engine
    from gemini_agent.cost_basis import rate_words

    num = reporter.num
    e, y = entry.economics, entry.year
    prices = engine.prices_for(assumptions, entry.brief)
    ref = engine.reference(entry.brief, assumptions)
    versus = engine.versus_reference(entry, ref, prices)
    r = ref.economics
    heat_mwh = y.heat_delivered_gwh * 1000
    cold_mwh = y.cool_delivered_gwh * 1000
    total = (e.lcoh_eur_per_mwh or 0) * heat_mwh + (e.lcoc_eur_per_mwh or 0) * cold_mwh
    ref_total = (r.lcoh_eur_per_mwh or 0) * heat_mwh + (r.lcoc_eur_per_mwh or 0) * cold_mwh
    heat_cmp = "cheaper" if e.lcoh_eur_per_mwh < r.lcoh_eur_per_mwh else "dearer"
    cold_cmp = "cheaper" if (e.lcoc_eur_per_mwh or 0) < (r.lcoc_eur_per_mwh or 0) else "dearer"
    lines = [
        f"Against the gas reference (gas boilers and electric chillers for the same demand, same "
        f"prices): heat costs {num(e.lcoh_eur_per_mwh)} €/MWh against "
        f"{num(r.lcoh_eur_per_mwh)} €/MWh with gas, so {heat_cmp} than gas"
        + (
            f"; cold costs {num(e.lcoc_eur_per_mwh)} €/MWh against "
            f"{num(r.lcoc_eur_per_mwh)} €/MWh, so {cold_cmp} than the reference"
            if cold_mwh and e.lcoc_eur_per_mwh is not None and r.lcoc_eur_per_mwh is not None
            else ""
        )
        + ".",
        f"Total cost of heat and cold a year (capital annuity, O&M, energy and CO2): "
        f"{num(total / 1e6)} M€ against {num(ref_total / 1e6)} M€ with gas.",
        f"Capital: {num(e.capex_meur)} M€ against {num(r.capex_meur)} M€ for the gas "
        f"reference, {num(versus['extra_capex_meur'])} M€ more; running costs "
        f"{num(versus['savings_meur_per_year'])} M€ a year lower; discounted payback "
        + (
            f"in year {versus['payback_years']}"
            if versus["payback_years"]
            else f"not within {versus['years']} years"
        )
        + f"; NPV against gas {num(versus['npv_meur'])} M€ over {versus['years']} years at "
        f"{num(prices.discount_rate * 100)} % real (a cost-saving NPV: no revenue, tax or "
        "subsidy; on both sides each unit is bought again when it wears out, "
        f"{num(abs(versus['reinvest_meur']))} M€ "
        f"{'more' if versus['reinvest_meur'] >= 0 else 'less'} for this design, and what is "
        f"still worth something at year {versus['years']} counts back).",
        _per_home(entry, ref),
        f"CO2: {num(e.co2_t_per_year, 0)} t a year against {num(r.co2_t_per_year, 0)} t with "
        f"gas ({num((e.co2_saving_vs_gas or 0) * 100)} % less).",
        f"Prices in force: gas {num(prices.gas_eur_per_mwh)} €/MWh, electricity "
        f"{num(prices.electricity_eur_per_mwh)} €/MWh, CO2 {num(prices.carbon_eur_per_t)} €/t, "
        f"discount rate {rate_words(prices.discount_rate, bool(entry.alternative.depth_m))}.",
        "Not in these costs: the heat and cold networks and the house connections, SDE++ or other "
        "subsidies, taxes, the heat tariff; so a cost per MWh is the plant's, not the customer's "
        "price.",
    ]
    if not entry.alternative.depth_m:  # the gas plant: its costs are the sale prices below
        return lines
    # The investor's view (``dioscuri_plant.investor``): sales, SDE++ and tax, which the plant's
    # cost above leaves out. Same figures as the Economics tab's investor section.
    from dioscuri_plant import investor

    case = investor.investor_case(
        engine.plant_of(entry.alternative),
        y,
        e,
        engine.rules_for(entry.brief),
        prices,
        r,
        investor.terms_from(assumptions),
    )
    s, cat = case.sde, case.sde["category"]

    def rate(x):
        return f"{num(x * 100)} %" if x is not None else "none (it never earns its capital back)"

    def payback(x):
        return f"in {num(x)} years" if x is not None else f"not within {case.years} years"

    subsidy = (
        f"SDE++ category '{cat['name']}' (basisbedrag {num(s['basis_eur_per_kwh'] * 1000)} "
        f"€/MWh, for {num(s.get('installation_mw', s['capacity_mw']))} MW of "
        f"{s.get('installation', 'geothermal')} capacity) pays on "
        f"{num(s['subsidised_gwh'])} GWh of geothermal heat a year in years {s['first_year']} to "
        f"{s['last_year']} ({s['calendar_years'][0]} to {s['calendar_years'][1]}): "
        f"{num(s['meur_first_year'])} M€ in year 1, {num(s['meur_average'])} M€ a year on "
        "average in 2025 euros; cooling earns none"
        if s["on"]
        else "SDE++ switched off (no subsidy)"
    )
    lines.append(
        "The investor's view (a company that builds and runs the plant, with SDE++ subsidy and "
        "corporate tax; the plant's cost above has neither): it sells heat at "
        f"{num(case.heat_sale_eur_per_mwh)} €/MWh and cold at {num(case.cold_sale_eur_per_mwh)} "
        "€/MWh"
        + (
            " (what the buyer's own gas boilers and electric chillers would cost)"
            if set(case.sale_basis.values()) == {"gas reference"}
            else " (prices set in this chat)"
        )
        + f", {num(case.revenue_heat_meur + case.revenue_cold_meur)} M€ a year, against "
        f"{num(case.opex_meur)} M€ a year of running costs; {subsidy}; corporate tax "
        f"{num(case.tax['rate'] * 100)} %, {num(case.tax['total_meur'])} M€ over {case.years} "
        "years."
    )
    lines.append(
        f"The investor's return after tax: NPV {num(case.npv_meur)} M€ over {case.years} years "
        f"at {num(case.discount_rate * 100)} % real, IRR {rate(case.irr)} real, discounted "
        f"payback {payback(case.payback_years)}"
        + (
            f"; without SDE++: NPV {num(case.without_sde['npv_meur'])} M€, IRR "
            f"{rate(case.without_sde['irr'])}, payback "
            f"{payback(case.without_sde['payback_years'])}"
            if s["on"]
            else " (no SDE++)"
        )
        + (
            f". It needs a basisbedrag of at least "
            f"{num(case.break_even_basis_eur_per_kwh * 1000)} €/MWh to break even."
            if case.break_even_basis_eur_per_kwh is not None
            else (
                ". It would not break even with any SDE++."
                if case.needs_subsidy
                else ". It breaks even without SDE++."
            )
        )
    )
    return lines


def _per_home(entry, ref) -> str:
    """Return the heat a home pays for a year at the plant's cost of heat, and with gas.

    By the number of homes when the user gave it, else a home of ``HOME_MWH`` (the decision
    table's basis); the plant's cost, not the tariff.
    """
    from gemini_agent.reliability import HOME_MWH

    num = reporter.num
    e, r = entry.economics, ref.economics
    homes = getattr(entry.brief, "homes", None)
    if homes:
        mwh = entry.year.heat_delivered_gwh * 1000 / homes
        basis = f"{homes:,} homes, so {num(mwh)} MWh of heat a home"
    else:
        mwh = HOME_MWH
        basis = f"a home using {HOME_MWH:g} MWh of heat a year (a Dutch average; no count given)"
    return (
        f"Per home ({basis}): {num(e.lcoh_eur_per_mwh * mwh, 0)} € a year for its heat at this "
        f"plant's cost of heat, against {num(r.lcoh_eur_per_mwh * mwh, 0)} € with gas boilers "
        "(the plant's cost, before the network, taxes and the tariff)."
    )


def _part(item: object) -> str:
    """Return a cost line's part: "Surface plant (per MW)" is part of "Surface plant"."""
    return str(item).replace(" (per MW)", "")


def cost_parts(lines, gwh: float) -> List[Tuple[str, float]]:
    """Return a side's cost by part, €/MWh delivered, each part once (its lines added).

    A line is (item, kind, M€ a year): the capital and the per-MW capital of the surface plant
    are one part to a reader, as are a unit's fixed and variable O&M. Per MWh: M€ × 1,000 / GWh.
    """
    per: Dict[str, float] = {}
    for ln in lines or []:
        if len(ln) >= 3 and ln[2] is not None and gwh:
            per[_part(ln[0])] = per.get(_part(ln[0]), 0.0) + float(ln[2]) * 1000 / gwh
    return [(k, v) for k, v in per.items() if abs(v) >= 0.05]


def capital_parts(items) -> List[Tuple[str, float]]:
    """Return the capital by part, M€, each part once."""
    per: Dict[str, float] = {}
    for c in items or []:
        if isinstance(c, dict):
            k = _part(c.get("item", c.get("name", "?")))
            per[k] = per.get(k, 0.0) + float(c.get("meur", 0) or 0)
    return [(k, v) for k, v in per.items() if v >= 0.05]


def economics_block(entry, assumptions: Optional[dict] = None) -> Block:
    """Return where a design's cost comes from (its cost lines) and what it means in money."""
    e, y = entry.economics, entry.year
    parts = []
    try:
        parts += money_lines(entry, assumptions)
    except Exception:  # noqa: BLE001 - the money facts are extra; the cost lines still stand
        pass
    for label, lines, total, gwh in (
        ("heat", e.lines_heat, e.lcoh_eur_per_mwh, y.heat_delivered_gwh),
        ("cold", e.lines_cold, e.lcoc_eur_per_mwh, y.cool_delivered_gwh),
    ):
        if not lines or not gwh:
            continue
        items = [f"{k} {reporter.num(v)} €/MWh" for k, v in cost_parts(lines, gwh)]
        parts.append(
            f"The cost of {label}, {reporter.num(total)} €/MWh, is the sum of: "
            + "; ".join(items)
            + "."
        )
    capex = [f"{k} {reporter.num(v)} M€" for k, v in capital_parts(e.capex_items)]
    if capex:
        parts.append(f"Capital {reporter.num(e.capex_meur)} M€: " + "; ".join(capex) + ".")
    parts.append(
        "Yearly costs are the capital's annuity (5.2 % real over each unit's life), fixed and "
        "variable O&M, gas and electricity at sourced prices (the Economics tab lists each "
        "price with its source), divided by the heat or cold delivered; shared costs are split "
        "by the brine heat each side uses."
    )
    return Block(f"{entry.alternative.code} costs", "design", " ".join(parts), "the cost lines")


def runs_block(session) -> Optional[Block]:
    """Return the conversation's design runs, when there are two or more: what each changed.

    "What changed between run A and run B?", "the first design's cost of heat", "the base case"
    (2 Nov: the answerer saw only the last run and said it saw no run A or B).
    """
    from gemini_agent import naming

    searches = list(getattr(session, "searches", None) or [])
    if len(searches) < 2:
        return None
    lines = []
    for i, srch in enumerate(searches):
        name = naming.run_name(srch, i + 1, searches[0])
        cands = [e for e in srch.get("candidates") or [] if e.alternative.role == "chosen"]
        pick = cands[0] if cands else None
        line = f"{name}" + (" (the first run, the base case)" if i == 0 else "")
        if i > 0 and srch.get("brief") and searches[0].get("brief"):
            changed = naming.brief_changes(srch["brief"], searches[0]["brief"])
            if changed:
                from gemini_agent import parameters

                said = parameters.label(
                    {k: v for k, v in changed.items() if k in parameters.CATALOGUE}
                )
                # Run A's own values too: "run A assumed a 60 °C return" had no source and was
                # removed as unsupported (4 Nov).
                was = naming.brief_changes(searches[0]["brief"], srch["brief"])
                was_said = parameters.label(
                    {k: v for k, v in was.items() if k in changed and k in parameters.CATALOGUE}
                )
                had = f"; run A had {was_said}" if was_said else ""
                line += f" (its input changed against run A: {said}{had}; the rest as in run A)"
        if pick is not None:
            e = pick.economics
            line += (
                f": picked {pick.alternative.uid or pick.alternative.code} "
                f"{pick.alternative.code}, {pick.alternative.name}; cost of heat "
                f"{reporter.num(e.lcoh_eur_per_mwh)} €/MWh, heat and cold together "
                f"{reporter.num(e.lcoe_eur_per_mwh or 0)} €/MWh, "
                f"{reporter.num((e.co2_saving_vs_gas or 0) * 100)}% less CO2 than gas"
            )
        else:
            line += ": no design met every cap"
        lines.append(line + ".")
    return Block("runs", "design", " ".join(lines), "the design runs of this chat")


def changes_block(session) -> Optional[Block]:
    """Return what each what-if changed against the design it was run on, worked out by code.

    Before and after, with the difference, for the costs, the CO2 saving and the capital. A
    what-if searched again is a new search's pick, not the change alone: said, with its code.
    5 Nov: "what did the store change?" was answered from the new search's pick (B1, which also
    added 1.3 MWp of solar: heat 66 €/MWh) instead of the store alone (W1: 66.9 €/MWh), and the
    design report had mixed the two.
    """
    ledger = list(getattr(session, "ledger", None) or [])
    by_uid = {e.alternative.uid: e for e in ledger if e.alternative.uid}
    lines = []
    for e in ledger:
        label = getattr(e, "change_label", "") or ""
        if e.alternative.role != "what_if" or not label:
            continue
        base = by_uid.get(str(e.alternative.parent or "").split(" · ")[0])
        if base is None or base is e:
            continue
        x, b = e.economics, base.economics
        name, was = e.alternative.uid or e.alternative.code, base.alternative.uid or "the base"
        if label.endswith(", searched again"):
            what = (
                f"the pick of a new search with {label[: -len(', searched again')]}: a different "
                f"design, {e.alternative.code} against {was}'s {base.alternative.code}, so not "
                "the change alone"
            )
        else:
            # The base's own values of what changed: "50 °C instead of 60 °C" (5 Nov: a true
            # sentence was removed for its "60 °C", which no block gave).
            before = ""
            try:
                from gemini_agent import naming, parameters

                old = naming.brief_changes(base.brief.model_dump(), e.brief.model_dump())
                old = {k: v for k, v in old.items() if k in parameters.CATALOGUE}
                before = parameters.label(old) if old else ""
            except Exception:  # noqa: BLE001 - a brief without the fields: no "instead of"
                before = ""
            instead = f" instead of {was}'s {before}" if before else ""
            what = f"{was} with {label}{instead}, nothing else changed"

        def step(text: str, old: float, new: float, unit: str, digits: int = 1) -> str:
            return (
                f"{text} {reporter.num(old)} → {reporter.num(new)}{unit} "
                f"({new - old:+.{digits}f}{unit if unit != '%' else ' points'})"
            )

        text = f"- {name} ({what}): " + "; ".join(
            [
                step("cost of heat", b.lcoh_eur_per_mwh, x.lcoh_eur_per_mwh, " €/MWh"),
                step(
                    "heat and cold together",
                    b.lcoe_eur_per_mwh or 0.0,
                    x.lcoe_eur_per_mwh or 0.0,
                    " €/MWh",
                ),
                step(
                    "CO2 saving against gas",
                    (b.co2_saving_vs_gas or 0.0) * 100,
                    (x.co2_saving_vs_gas or 0.0) * 100,
                    "%",
                ),
                step("capital", b.capex_meur, x.capex_meur, " M€"),
            ]
        )
        lines.append(("searched again" in label, len(lines), text))
    if not lines:
        return None
    lines = [
        text for _, _, text in sorted(lines)
    ]  # the change alone first, then a new search's pick
    head = (
        "What each what-if changed, before → after against the design it was run on (worked "
        "out by code; quote these, not other designs' figures):\n"
    )
    return Block("changes", "design", head + "\n".join(lines), "what the what-ifs changed")


def why_not(e, best) -> str:
    """Return why a pick is not the best overall, worked out by code, and how it differs.

    The reason is the rule the pick broke (``engine.pick_entries``): the best overall is a
    reliable plan (any one unit can be out), the cheapest with CO2 at the long-term price,
    unless it flares the brine's gas routinely and a plan that flares less is within
    ``engine.FLARE_MARGIN`` of it. Then the differences against the best overall, signed.
    5 Nov: "why didn't you pick the cheapest?" had no reason in the context; the model made one
    up ("it emits more CO2", while the cheapest saves more) and the claim checker removed it.
    """
    if best is None or e is best or "best" in e.alternative.picks:
        return ""
    from gemini_agent import engine, reliability

    a, x, b = e.alternative, e.economics, best.economics
    top = best.alternative.uid or best.alternative.code
    if not a.reliable:
        why = "the best overall must be sized for one unit out (N-1), and this one is not"
    elif (
        e.year.produced_gas_flared_gwh > engine.FLARE_ROUTINE_GWH
        and best.year.produced_gas_flared_gwh <= engine.FLARE_ROUTINE_GWH
    ):
        why = (
            f"flares {reporter.num(e.year.produced_gas_flared_gwh)} GWh of the brine's gas a "
            f"year (routine flaring needs consent), and {top} flares less within "
            f"{engine.FLARE_MARGIN:.0%} of its cost with CO2 at the long-term price"
        )
    else:
        prices = reliability.entry_prices(best)
        more = engine.shadow_cost(e, prices) - engine.shadow_cost(best, prices)
        why = (
            f"{reporter.num(more)} €/MWh dearer than {top} with CO2 at the long-term "
            f"{prices.carbon_long_term_eur_per_t:g} €/t"
            if more > 0
            else "no dearer with CO2 at the long-term price"
        )
    saving = ((x.co2_saving_vs_gas or 0.0) - (b.co2_saving_vs_gas or 0.0)) * 100
    return (
        f"; not the best overall: {why} (against {top}: heat and cold "
        f"{x.lcoe_eur_per_mwh - b.lcoe_eur_per_mwh:+.1f} €/MWh, CO2 saving {saving:+.1f} "
        f"points, capital {x.capex_meur - b.capex_meur:+.1f} M€)"
    )


def search_block(
    candidates: Sequence[object],
    limit: int = 8,
    search: Optional[dict] = None,
    short: bool = False,
) -> Optional[Block]:
    """Return the last design search: how wide it was, the pick, its rivals and why each lost.

    "Why boilers and not heat pumps?", "why not two injectors?" and "why not a separator per
    doublet?" are answered from this: what was compared, by how much, and what the model cannot
    tell apart (``search["notes"]``). ``short``: how wide it was and the picks only, for any
    question once a search ran (4 Nov: "what did the search go through to get here?" named no
    design word, so the model saw no search and said it had run a single design).
    """
    tried = [e for e in candidates if e.alternative.role != "same"]
    if not tried:
        return None
    valid = [e for e in tried if e.alternative.role in ("chosen", "candidate")]
    valid.sort(key=lambda e: (e.alternative.role != "chosen", e.economics.lcoe_eur_per_mwh))
    failed = [e for e in tried if e.alternative.role == "failed"]
    chosen = next((e for e in valid if e.alternative.role == "chosen"), None)
    variants = [e for e in tried if e.alternative.stage == 2]
    lines = []

    from gemini_agent import engine

    def line(e) -> str:
        a = e.alternative
        why = (
            "chosen" if a.role == "chosen" else f"lost: {a.reason}" if a.reason else "met every cap"
        )
        sizes = len(a.sizings)
        sized = f", best of {sizes} sizings" if sizes > 1 else ""
        picks = ", ".join(engine.PICK_NAMES[k] for k in a.picks)
        name = f"{a.uid} {a.code}" if a.uid else a.code
        return (
            f"{name} ({a.name}{'; ' + picks if picks else ''}): "
            f"{reporter.num(e.economics.lcoe_eur_per_mwh)} €/MWh of heat and cold, "
            f"{reporter.num(e.economics.co2_t_per_year, 0)} t CO2 a year, "
            f"{reporter.num(e.economics.capex_meur)} M€{sized}"
            + ("; any one unit can be out" if a.reliable else "")
            + f"; {why}"
        )

    def brief(e) -> str:
        a = e.alternative
        name = f"{a.uid} {a.code}" if a.uid else a.code
        # "The greenest" is the lowest-CO2 pick, not the greenest reliable one (5 Nov).
        picks = ", ".join(
            engine.PICK_NAMES[k] + (" (the greenest)" if k == "co2" else "") for k in a.picks
        )
        x = e.economics
        # The cost of heat and the CO2 saving too: "which designs did the search pick, and what
        # does heat cost in each?" (5 Nov) was answered from other designs' blocks.
        return (
            f"{name} ({picks}): {reporter.num(x.lcoe_eur_per_mwh)} €/MWh of heat and cold "
            f"(heat {reporter.num(x.lcoh_eur_per_mwh)} €/MWh), CO2 saving "
            f"{reporter.pct(x.co2_saving_vs_gas or 0.0)} ({reporter.num(x.co2_t_per_year, 0)} t "
            f"CO2 a year), {reporter.num(x.capex_meur)} M€"
            + ("; any one unit can be out" if a.reliable else "; not sized for one unit out")
            + why_not(e, best)
        )

    shown = set()
    picked = [e for e in valid if e.alternative.picks]
    best = next((e for e in picked if "best" in e.alternative.picks), None)
    # The picks in a line each first: a cut block (``fit``) keeps them (4 Nov: "which designs
    # did the search pick?" was answered with heat pump sizes, the picks cut away).
    for e in [] if short else picked:  # in full: the picks, then the cheapest others
        lines.append(line(e))
        shown.add(e.alternative.code)
    for e in [] if short else valid[:limit]:
        if e.alternative.code in shown:
            continue
        lines.append(line(e))
        shown.add(e.alternative.code)
    # The variants of the pick's layout answer "why not ...?" questions: always listed. They
    # hang off the layout without options or the N-1 plan (1D-HP-EC@3000 for the pick
    # 1D-HP-EC@3000-N1-FC; 4 Nov: "why not two injectors?" had no figure).
    lineage = reporter.lineage(chosen.alternative.code, tried) if chosen is not None else set()
    lineage.add("")
    for e in [] if short else variants:
        if chosen is not None and e.alternative.parent in lineage:
            if e.alternative.code not in shown:
                lines.append(line(e))
                shown.add(e.alternative.code)
    for e in [] if short else failed[:3]:
        lines.append(
            f"{e.alternative.code} ({e.alternative.name}): broke a cap: {e.alternative.reason}"
        )
    sizings = sum(len(e.alternative.sizings) for e in tried)
    years = (search or {}).get("years")
    # The picks come first, one a line, said to be the picks and the only ones (5 Nov: "which
    # designs did the search pick, and what does heat cost in each?" listed the decisions
    # block's alternatives, read after a long sentence on how wide the search was).
    picks_head = (
        "The design search's picks (these are the designs it picked, in this order; any other "
        "design in the context is not a pick):\n"
        + "\n".join(f"- {brief(e)}" for e in picked)
        + "\n"
        if picked
        else ""
    )
    head = picks_head + (
        f"The last design search tried {len(tried)} distinct layouts ({len(variants)} of them "
        f"variants of the best three: two injectors, a treatment train per doublet, wells open "
        f"over half the aquifer), each sized several ways ({sizings} sizings"
        + (f", {years} simulated years" if years else "")
        + f"); {len(valid)} met every cap and {len(failed)} broke one. The picks: best overall "
        "(a reliable plan, cheapest with CO2 at the long-term price), cheapest (lowest cost of "
        "heat and cold), lowest CO2 (the cheapest within 2 % of the least), cheapest reliable "
        "(the cheapest plan where any one unit can be out)."
    )
    if lines:
        head += " In full, the picks first, then the cheapest others: " + "; ".join(lines) + "."
    notes = [n for n in (search or {}).get("notes") or [] if not n.startswith("ranked by")]
    tail = (" Limits of the model: " + "; ".join(notes) + ".") if notes and not short else ""
    return Block("search", "design", head + tail, "the design search")


def decisions_block(chosen, candidates: Sequence[object]) -> Optional[Block]:
    """Return each choice the design made against its best alternative, in €/MWh, by code.

    "Why boilers and not heat pumps?", "why one doublet?", "why not two injectors?" are answered
    from this: the layout's doublets, top-up, cooling, variants and reliable plan, each set
    against the best valid design that chose otherwise (the same objective's search).
    """
    from gemini_agent import engine

    if chosen is None or not candidates:
        return None
    valid = [
        e
        for e in candidates
        if e.alternative.role in ("chosen", "candidate") and e.alternative.code != "REF"
    ]
    plain = [e for e in valid if not e.alternative.reliable]
    a = chosen.alternative
    # Its layout without the reliable plan: the same options first (1D-HP-EC@3000-N1-FC is
    # 1D-HP-EC@3000-FC), else up its parents. 4 Nov: the pick was a plant option of the N-1
    # plan, whose parent is reliable too, so no layout was found and this block went missing.
    codes = [re.sub(r"-N1(?=-|$)", "", a.code)] if a.reliable else []
    parents = {e.alternative.code: e.alternative.parent for e in valid}
    code = a.code
    while code and code not in codes:
        codes.append(code)
        code = parents.get(code, "")
    base = next((e for c in codes for e in plain if e.alternative.code == c), None)
    if base is None:
        return None
    b = base.alternative
    cost = base.economics.lcoe_eur_per_mwh
    num = reporter.num

    def best(pred):
        pool = [e for e in plain if pred(e.alternative) and e is not base]
        return min(pool, key=lambda e: e.economics.lcoe_eur_per_mwh, default=None)

    def vs(e, ref=None) -> str:
        ref = ref or base
        gap = e.economics.lcoe_eur_per_mwh - ref.economics.lcoe_eur_per_mwh
        digits = 2 if abs(gap) < 0.1 else 1
        dt = e.economics.co2_t_per_year - ref.economics.co2_t_per_year
        return (
            f"{e.alternative.code} {num(e.economics.lcoe_eur_per_mwh)} €/MWh "
            f"({'+' if gap >= 0 else '−'}{num(abs(gap), digits)}), "
            f"{'+' if dt >= 0 else '−'}{num(abs(dt), 0)} t CO2 a year"
        )

    lines = [f"Choices of {a.code} ({engine.OBJECTIVE_WORDS.get(chosen.brief.objective, '')})"]
    # The alternatives are no picks: "which designs did the search pick?" listed them (5 Nov).
    lines.append("each against the best layout without it (alternatives, not the search's picks)")
    lines.append(f"its layout {b.code} costs {num(cost)} €/MWh of heat and cold")
    for n in (1, 2, 3):
        if n != b.n_doublets:
            e = best(lambda x, n=n: x.n_doublets == n and x.stage == 1)
            if e is not None:
                lines.append(f"best with {n} doublet{'s' if n > 1 else ''}: {vs(e)}")
    other_top = "boiler" if b.topup == "heat_pump" else "heat_pump"
    e = best(lambda x: x.topup == other_top and x.n_doublets == b.n_doublets and x.stage == 1)
    if e is not None:
        what = "a boiler only (no heat pump)" if other_top == "boiler" else "a heat pump top-up"
        lines.append(f"with {what}: {vs(e)}")
    if b.topup == "heat_pump":
        rows = [r for r in b.sizings if r.get("valid") and r.get("heat_pump_mw")]
        if len(rows) > 1:
            big = max(rows, key=lambda r: r["heat_pump_mw"])
            small = min(rows, key=lambda r: r["heat_pump_mw"])
            lines.append(
                f"heat pump {num(b.sizes_mw.get('heat_pump', 0))} MW; "
                f"a {num(big['heat_pump_mw'])} MW "
                f"heat pump gives {num(big['lcoe'])} €/MWh, a {num(small['heat_pump_mw'])} MW one "
                f"{num(small['lcoe'])} (the boiler covers what the heat pump does not)"
            )
    other_cool = "electric" if b.cooling == "absorption" else "absorption"
    e = best(
        lambda x: x.cooling == other_cool
        and x.n_doublets == b.n_doublets
        and x.topup == b.topup
        and x.stage == 1
    )
    if e is not None:
        what = "electric chillers only" if other_cool == "electric" else "an absorption chiller"
        lines.append(f"with {what}: {vs(e)}")
    root = b.parent or b.code  # the variants are of the layout without options
    ref = next((e for e in plain if e.alternative.code == root), base)
    for e in plain:
        if e.alternative.stage == 2 and e.alternative.parent == root and e.alternative.effect:
            lines.append(f"{e.alternative.code}: {e.alternative.effect}; {vs(e, ref)}")
    if a.reliable:
        extra = chosen.economics.capex_meur - base.economics.capex_meur
        gap = chosen.economics.lcoe_eur_per_mwh - cost
        lines.append(
            f"the reliable plan adds {num(extra)} M€ and {num(gap)} €/MWh so that any one unit "
            f"can be out (boiler {a.boiler_units} units of "
            f"{num(a.sizes_mw.get('boiler', 0) / max(a.boiler_units, 1))} MW)"
        )
    return Block("decisions", "design", "; ".join(lines) + ".", "the design's choices, by code")


def self_block(models: str = "") -> Block:
    """Return the self card, with the models in use now when given."""
    text = load(SELF_CARD)
    if models:
        text += "\nModels in use now: " + models
    return Block("self", "self", text)


def passage_kind(source: str, attachments: Iterable[str] = ()) -> str:
    """Return ``file`` for an upload, ``doc`` for GEMINI's documentation, ``note`` otherwise."""
    if source in set(attachments) or not ("/" in source or "\\" in source):
        return "file"
    if source.replace("\\", "/").startswith(GEMINI_SOURCES):
        return "doc"
    return "note"


def passage_blocks(passages: Sequence[object], attachments: Iterable[str] = ()) -> List[Block]:
    """Return blocks for the usable search hits (instruction-like passages are never shown)."""
    out = []
    names = list(attachments)
    for p in passages:
        if getattr(p, "suspicious", False):
            continue
        kind = passage_kind(p.source, names)
        n = sum(b.kind == kind for b in out) + 1
        prefix = {"doc": "doc", "note": "note", "file": "file"}[kind]
        title = Path(p.source).name + (f", {p.section}" if p.section else "")
        out.append(Block(f"{prefix}{n}", kind, _flat(p.text, 650), title, p.as_dict()))
    return out


def data_block(view, n: int = 1) -> Block:
    """Return an opened file (``files.FileView``) for the answerer, and its source card."""
    passage = {
        "source": view.name,
        "section": "project file" if view.origin == "project" else "your upload",
        "text": _flat(view.summary(), 400),
        "score": 1.0,
        "suspicious": False,
        "kind": "data",
        "file": view.name,
    }
    image = view.path if view.kind == "image" else None
    columns = tuple(c["name"] for c in view.table["columns"]) if view.table else ()
    return Block(f"data{n}", "data", view.summary(), view.name, passage, image, columns)


def history_block(turns: Sequence[dict], keep: int = 3, text: str = "") -> Optional[Block]:
    """Return the conversation so far, so "and the cost?" or "the second one" make sense.

    ``text``: the chat's thread (``thread.py``: one line per earlier turn, the last exchanges,
    the design under discussion, the last list shown, the open question); without it, the last
    ``keep`` exchanges alone.
    """
    if text:
        return Block("history", "history", text, "the conversation so far")
    if not turns:
        return None
    lines = []
    for t in list(turns)[-keep:]:
        lines.append(f"User: {_flat(t.get('user', ''), 160)}")
        if t.get("reply"):
            # A refusal or a question back says so, so "why?" next is answered from it.
            kind = HISTORY_KINDS.get(t.get("kind", ""), "")
            who = f"Dioscuri ({kind})" if kind else "Dioscuri"
            lines.append(f"{who}: {_flat(CITE_MARK.sub('', t['reply']), 240)}")
    return Block("history", "history", " | ".join(lines), "earlier in this conversation")


HISTORY_KINDS = {
    "reject": "declined: it read the message as asking to skip the simulator or the checks",
    "refuse": "declined as outside what it does",
    "clarify": "asked a question back",
    "report_infeasible": "found no design that meets every cap",
    "design": "ran the design tools",
}


SPLIT_NAMES = {
    "geo": "the doublet directly",
    "hp": "the heat pump",
    "boiler": "the peak boiler",
    "abs": "the absorption chiller",
    "chill": "electric chillers",
    "free": "free cooling on the towers",
}


def design_block(entry, chosen: bool = False) -> Block:
    """Return a simulated design: its values, where its heat and cold come from, its checks.

    Parameters
    ----------
    entry : LedgerEntry
        The design.
    chosen : bool
        It is the design the conversation is about (the latest recommendation or pick).

    Returns
    -------
    Block
        Cited by the design's code (``A1``; a what-if version gets ``A1 what-if``).
    """
    from gemini_agent import lookup

    y, alt, v = entry.year, entry.alternative, entry.verification
    delta = entry.brief.reservoir_delta_c
    label = getattr(entry, "change_label", "")
    what_if = bool(label or delta)
    parts = [
        f"{alt.code}, {alt.name}"
        + (" (the current design)" if chosen and not what_if else "")
        + (" (a what-if of the design, not the design itself)" if what_if else "")
    ]
    if label:
        parts.append(f"what-if: {label}")
    elif delta:
        change = "warmer" if delta > 0 else "colder"
        parts.append(f"what-if with the reservoir {reporter.num(abs(delta))} °C {change}")
    parts.append(SOURCES.get(y.source, f"results from {y.source} tools"))
    facts = lookup.design_facts(entry)
    # The long facts are for lookups; the block says them elsewhere (shares, wells notes).
    values = "; ".join(
        f"{lookup.LABELS[k]} {f.value}" for k, f in facts.items() if k not in lookup.LONG_FACTS
    )
    lines = [", ".join(parts) + ". " + values + "."]
    lines += design_notes(entry)
    sized = sizing_note(entry)
    if sized:
        lines.append(sized)
    for split, total in ((y.heat_split_gwh, y.heat_delivered_gwh), (y.cool_split_gwh, None)):
        total = total or sum(split.values())
        if split and total:
            shares = [
                f"{SPLIT_NAMES.get(k, k)} {reporter.pct(gwh / total)}"
                for k, gwh in split.items()
                if gwh > 0
            ]
            what = "Heat" if split is y.heat_split_gwh else "Cold"
            lines.append(f"{what} from: " + ", ".join(shares) + ".")
    failed = [c.name for c in v.checks if not c.passed]
    checks = f"Checks: {sum(c.passed for c in v.checks)} of {len(v.checks)} passed"
    lines.append(checks + (f"; not met: {'; '.join(failed)}." if failed else "."))
    if entry.brief.excluded:
        lines.append("The user ruled out: " + ", ".join(entry.brief.excluded) + ".")
    block_id = alt.code + (" what-if" if delta or label else "")
    return Block(block_id, "design", " ".join(lines))


def design_notes(entry) -> List[str]:
    """Return where a design's temperatures come from and what its units are connected to.

    Without these the model guesses: on 30 Oct it explained a 101 °C wellhead from an 87 °C
    reservoir as the brine "heating up on the way up", when the wells were 3,000 m deep.
    """
    from gemini_agent import projects

    y, alt = entry.year, entry.alternative
    out: List[str] = []
    if alt.depth_m and alt.n_doublets:
        try:
            rules = projects.registry().rules(entry.brief.project_id)
        except KeyError:
            rules = None
        if rules is not None:
            out += _wells_notes(entry, rules)
    el = y.electricity_gwh or {}
    links = []
    if alt.sizes_mw.get("chillers"):
        links.append(
            f"the electric chillers draw {reporter.num(el.get('chillers', 0))} GWh/yr from the "
            "grid and reject their heat to cooling towers"
        )
    if alt.sizes_mw.get("absorption"):
        links.append("the absorption chiller is driven by the brine and rejects to cooling towers")
    if alt.sizes_mw.get("heat_pump"):
        links.append(
            f"the heat pump takes the brine after the exchanger as its source and draws "
            f"{reporter.num(el.get('hp', 0))} GWh/yr from the grid"
        )
    gas = getattr(alt, "gas", "buy")
    if alt.sizes_mw.get("boiler") and gas == "buy":
        links.append(
            f"the boiler burns the produced gas first ({reporter.num(y.produced_gas_burned_gwh)} "
            f"GWh/yr) and buys the rest ({reporter.num(y.purchased_gas_gwh)} GWh/yr)"
        )
    elif alt.sizes_mw.get("boiler"):
        links.append(
            f"no gas is bought: a small boiler burns only the brine's own gas "
            f"({reporter.num(y.produced_gas_burned_gwh)} GWh/yr)"
        )
    if gas == "sell":
        elsewhere = (y.co2_t or {}).get("sold_gas_elsewhere", 0.0)
        links.append(
            f"the brine's gas is cleaned and sold to the gas grid "
            f"({reporter.num(getattr(y, 'produced_gas_sold_gwh', 0.0) or 0.0)} GWh/yr of methane): "
            f"its CO2 when the buyer burns it ({reporter.num(elsewhere, 0)} t a year) is not in "
            "this plant's CO2"
        )
    if alt.sizes_mw.get("electric_boiler"):
        links.append(
            f"the electric boiler ({reporter.num(alt.sizes_mw['electric_boiler'])} MW) heats what "
            f"the heat pump and any gas boiler cannot, drawing "
            f"{reporter.num(el.get('electric_boiler', 0))} GWh/yr from the grid"
        )
    if alt.n_doublets:
        links.append(
            f"the well pumps (ESP and injection) draw {reporter.num(el.get('pumps', 0))} GWh/yr"
        )
    if links:
        out.append("Connections: " + "; ".join(links) + ".")
    out += network_notes(y)
    why = heat_split_why(entry)
    if why:
        out.append(why)
    if alt.n_doublets and alt.depth_m:  # what failures cost a year, whether a spare ESP pays
        from gemini_agent import reliability

        failures = reliability.failure_costs_note(entry)
        if failures:
            out.append(failures)
    oper = getattr(y, "operability", None)
    if oper:  # minimum loads and trips: what the daily dispatch hides
        from dioscuri_plant import operability

        out += operability.warnings(oper)
        trips = oper.get("trips") or {}
        if alt.n_doublets and trips.get("boiler_gwh"):
            out.append(
                f"ESP trips (assumed {trips['per_doublet_year']:g} a doublet a year, "
                f"{trips['hours_each']:g} hours each to restart) move about "
                f"{reporter.num(trips['boiler_gwh'], 2)} GWh a year to the boiler."
            )
    if alt.sizes_mw.get("chillers") or alt.sizes_mw.get("absorption"):  # the cooling check
        from gemini_agent import cooling_check

        try:
            out += cooling_check.words(cooling_check.check(entry))
        except Exception:  # noqa: BLE001 - the notes stand without it
            pass
    out += option_notes(entry)
    check = getattr(entry, "gemini", None)
    if check and check.get("rows"):
        bits = [
            f"{r['quantity']} {reporter.num(r['gemini'], 2)} against {reporter.num(r['plant'], 2)}"
            f" {r['unit']} ({'agrees' if r['agree'] else 'differs'})"
            for r in check["rows"]
        ]
        out.append(
            f"GEMINI check (GEMINI's own run of the brine loop at full flow against the plant "
            f"model; agree within 5 %, or 1 K): {check['agree']} of {check['total']} agree: "
            + "; ".join(bits)
            + "."
        )
    return out


def option_notes(entry) -> List[str]:
    """Return what the plant's options (free cooling, solar, a store, the grid by month) did.

    The search tries them on its own since 3 Nov; without these the answers named a code
    suffix (-FC, -PV1.7, -ATES) and could not say what it bought.
    """
    from gemini_agent import engine

    y, out = entry.year, []
    free = (getattr(y, "cool_split_gwh", None) or {}).get("free", 0.0)
    if getattr(y, "free_cooling_mw", 0.0):
        out.append(
            f"Free cooling: on cold enough days the cooling towers cool the network directly, "
            f"before the chillers: {reporter.num(free)} GWh a year (up to "
            f"{reporter.num(y.free_cooling_mw)} MW), the chillers' power saved on those days."
        )
    solar = getattr(y, "solar", None)
    if solar:
        out.append(
            f"Own solar ({reporter.num(solar['mwp'])} MWp): {reporter.num(solar['generated_gwh'])}"
            f" GWh a year, {reporter.num(solar['used_gwh'])} used by the plant and "
            f"{reporter.num(solar['sold_gwh'])} sold back; the grid's CO2 is counted on the "
            f"{reporter.num(solar['bought_gwh'])} GWh still bought."
        )
    store = getattr(y, "storage", None)
    if store and store.get("boiler_saved_gwh"):
        ates = store.get("kind") == "HT-ATES"
        kind = "a seasonal high-temperature aquifer store (HT-ATES)" if ates else "a hot-water tank"
        when = ("in summer", "in winter") if ates else ("on mild days", "on cold ones")
        out.append(
            f"Heat store, {kind}: it takes the doublets' spare heat {when[0]} "
            f"({reporter.num(store['charged_gwh'])} GWh a year) and gives "
            f"{reporter.num(store['given_gwh'])} GWh back {when[1]}, losing "
            f"{reporter.num(store['lost_gwh'])} GWh; the top-up units make "
            f"{reporter.num(store['boiler_saved_gwh'])} GWh a year less."
        )
    elif store:
        out.append("Heat store: tried, but the doublets had no spare heat for it to move.")
    try:
        by_month = getattr(engine.rules_for(entry.brief), "grid_by_month", 0.0)
    except Exception:  # noqa: BLE001 - a project not in the registry
        by_month = 0.0
    if by_month:
        out.append(
            "Grid CO2 month by month (Ember's 2024 shape for the Netherlands on the yearly "
            "figure): winter electricity counts dirtier, summer cleaner."
        )
    return out


ALREADY_NOTE = {
    "free_cooling": "Free cooling",
    "solar_mwp": "Own solar",
    "storage_mwh": "Heat store",
    "storage_ates": "Heat store",
    "grid_by_month": "Grid CO2 month by month",
}


def already_text(entry, keys: Sequence[str]) -> str:
    """Return that the design already has the options asked for, with what each does."""
    from gemini_agent import parameters

    notes = option_notes(entry)
    lines = []
    for key in keys:
        start = ALREADY_NOTE.get(key)
        note = next((n for n in notes if start and n.startswith(start)), "")
        if note and note not in lines:
            lines.append(note)
        elif not note:
            label = re.sub(r"\s*\(.*\)$", "", parameters.CATALOGUE[key].label)
            lines.append(f"{label}: on.")
    if not lines:
        return ""
    alt = entry.alternative
    return f"The design {alt.uid or alt.code} already has this. " + " ".join(lines)


def heat_split_why(entry) -> str:
    """Return why the heat splits between the doublets and the top-up units, from the design.

    On 1 Nov the answer blamed the N-1 sizing for half the heat coming from gas; the split is
    set by what the brine can give and by the heat pump size the search found cheapest, and
    N-1 only adds standby capacity.
    """
    from gemini_agent import engine

    y, alt = entry.year, entry.alternative
    split = y.heat_split_gwh or {}
    total = sum(v for v in split.values() if v) or 0.0
    if not (alt.n_doublets and total and y.hex_outlet_c):
        return ""
    rules = engine.rules_for(entry.brief)
    ts, tr = rules.heat_supply_c, rules.heat_return_c
    lift = max(0.0, min(1.0, (y.hex_outlet_c - tr) / (ts - tr))) if ts > tr else 0.0
    num, pct = reporter.num, reporter.pct
    boiler = split.get("boiler", 0.0) + split.get("electric_boiler", 0.0)
    hp = (alt.sizes_mw or {}).get("heat_pump", 0.0)
    text = (
        f"Why the heat splits as it does: the exchanger gives at most {num(y.hex_mw, 2)} MW "
        f"({alt.n_doublets} doublet{'s' if alt.n_doublets != 1 else ''} at up to "
        f"{num(rules.flow_max_m3h, 0)} m3/h each), and it "
        f"can heat the {num(tr)} °C return only to {num(y.hex_outlet_c)} °C (the brine at the "
        f"wellhead less the exchanger's approach), {pct(lift)} of the way to {num(ts)} °C; the "
        f"heat demand peaks at {num(y.peak_heat_mw)} MW."
    )
    best: Dict[float, float] = {}
    for r in alt.sizings or []:
        if r.get("valid") and r.get("heat_pump_mw") is not None:
            mw = float(r["heat_pump_mw"])
            best[mw] = min(best.get(mw, float("inf")), float(r["lcoe"]))
    if hp:
        text += f" The heat pump ({num(hp)} MW) takes the brine after the exchanger as its source."
    if len(best) >= 2:
        low, high = min(best), max(best)
        least = min(best.values())
        mine = next((c for mw, c in best.items() if abs(mw - hp) < 0.05), None)
        text += f" The search tried heat pumps from {num(low)} to {num(high)} MW: "
        if mine is not None and mine - least < 0.1:
            text += f"{num(hp)} MW was among the cheapest ({num(mine)} €/MWh of heat and cold"
        else:
            cheapest = min(best, key=best.get)
            text += f"{num(cheapest)} MW was the cheapest ({num(least)} €/MWh of heat and cold"
        text += (
            f", against {num(best[high])} €/MWh at {num(high)} MW: past that, the extra capital, "
            "O&M and electricity cost more than the gas and CO2 a larger heat pump saves)."
            if best[high] - least >= 0.1
            else ")."
        )
    text += (
        f" The boiler covers the rest: {num(boiler)} GWh, {pct(boiler / total)} of the year's "
        "heat. A reliable plan (N-1) adds standby units only; it does not change where the heat "
        "comes from."
    )
    return text


def network_notes(y) -> List[str]:
    """Say what the district network and the planned service do to a design, when modelled."""
    num = reporter.num
    out = []
    net = getattr(y, "network", None)
    if net:
        share = reporter.pct(net["heat_loss_share"])
        out.append(
            f"District network: a {num(net['length_km'])} km trunk (DN{net['heat_dn']} "
            f"pre-insulated pipes, U {num(net['heat_u_w_mk'], 2)} W/m·K, ground "
            f"{num(net['ground_c'])} °C) loses {num(net['heat_loss_gwh'], 2)} GWh of heat a year "
            f"({share} of the heat), which the plant makes as well; the plant supplies up to "
            f"{num(net['supply_c_max'])} °C (at low summer flow; "
            f"{num(net['supply_c_peak_day'])} °C on the peak day) so the buildings get the supply "
            f"temperature; the network pumps draw {num(net['pump_gwh'], 2)} GWh a year. The "
            f"cooling network gains {num(net['cool_free_gwh'], 2)} GWh of free cooling from the "
            "colder ground. The trunk's own cost is the same for every design and the gas "
            "reference, so it is left out."
        )
    service = getattr(y, "service", None) or []
    if service:
        out.append(
            "Planned service (each unit once a year, in its quietest weeks, built into the year): "
            + "; ".join(f"{u} {_date(int(a))} to {_date(int(b))}" for u, a, b in service)
            + "."
        )
    return out


def sizing_note(entry) -> str:
    """Say which unit sizes the search tried for this layout and what each cost.

    "Why a boiler and not a bigger heat pump?" is answered from this: the heat pump's sizes
    and the absorption chiller's shares of the cooling peak, each at its best cost.
    """
    rows = [r for r in entry.alternative.sizings if r.get("valid")]
    if len(rows) < 2:
        return ""
    num = reporter.num
    parts = []
    for key, size, label in (
        ("heat_pump_share", "heat_pump_mw", "heat pump"),
        ("absorption_share", "absorption_mw", "absorption chiller"),
    ):
        best: Dict[float, dict] = {}
        for r in rows:
            share = r.get(key)
            if share is None:
                continue
            if share not in best or r["lcoe"] < best[share]["lcoe"]:
                best[share] = r
        if len(best) < 2:
            continue
        shown = "; ".join(
            f"{num(r[size])} MW {num(r['lcoe'])} €/MWh"
            for _, r in sorted(best.items(), key=lambda kv: kv[1][size])
        )
        parts.append(f"{label} sizes tried (best cost of heat and cold at each): {shown}")
    if not parts:
        return ""
    alt = entry.alternative
    whose = (
        f"Sizing of {alt.parent or alt.code}, the layout of {alt.code} before its reliable plan "
        "added the backup boiler and chiller units"
        if alt.reliable
        else f"Sizing of {alt.code}"
    )
    return (
        f"{whose}: "
        + ". ".join(parts)
        + ". The boiler covers what the doublets and the heat pump do not (its size follows); "
        "the electric chillers cover the cooling the absorption chiller does not."
    )


def _wells_notes(entry, rules) -> List[str]:
    """Say where each doublet is drilled, how it is built and how it runs over the year."""
    from gemini_agent import engine
    from gemini_agent import stops as stop_dates

    y, alt = entry.year, entry.alternative
    num = reporter.num
    specs = alt.doublets or [{"depth_m": alt.depth_m, "injectors": 1, "train": 0}]
    rows = (y.plant or {}).get("doublets") or []
    known_m = rules.reservoir_depth_m
    described = engine.rules_for(entry.brief)  # with the aquifers the user described

    def where(depth: float) -> str:
        if abs(depth - known_m) < 1e-6:
            return f"the known aquifer at {num(known_m, 0)} m"
        if described.aquifer_index(depth):  # one the user described: its own rock and gas
            return aquifers.label(depth, entry.brief, described)
        return (
            f"an assumed aquifer at {num(depth, 0)} m (the known one is at {num(known_m, 0)} m, "
            f"{num(rules.reservoir_temperature_c())} °C; the requirements allow other depths with "
            "the gradient and hydrostatic pressure but describe no aquifer there)"
        )

    def rock(depth: float) -> str:
        return (
            f"{num(rules.reservoir_temperature_c(depth))} °C "
            f"({num(rules.surface_temperature_c)} °C + {num(rules.gradient_c_per_km)} °C/km × "
            f"{depth / 1000:g} km)"
        )

    plain = all(
        float(d.get("depth_m") or alt.depth_m) == float(specs[0].get("depth_m") or alt.depth_m)
        and (d.get("producer_open") or "full") == "full"
        and (d.get("injector_open") or "full") == "full"
        and int(d.get("injectors") or 1) == 1
        for d in specs
    )
    trains = len({int(d.get("train") or 0) for d in specs})
    out = []
    if plain:
        depth = float(specs[0].get("depth_m") or alt.depth_m)
        res = rules.reservoir_temperature_c(depth)
        thick = described.aquifer_at(depth).reservoir_thickness_m  # its own aquifer's
        text = (
            f"Wells: {alt.n_doublets} doublet(s) in {where(depth)}, each a producer and an "
            f"injector open over the whole {num(thick)} m of the aquifer; "
            f"rock temperature there {rock(depth)}; brine at the wellhead {num(y.wellhead_c)} °C "
            f"({num(res - y.wellhead_c)} K lost up the well at full flow, more when slow); "
            f"reinjected at {num(y.reinjection_c)} °C at the coldest."
        )
        out.append(text)
    else:
        parts = []
        for i, d in enumerate(specs):
            row = rows[i] if i < len(rows) else {}
            depth = float(d.get("depth_m") or alt.depth_m)
            n_inj = int(d.get("injectors") or 1)
            p_open, i_open = d.get("producer_open") or "full", d.get("injector_open") or "full"
            parts.append(
                f"doublet {i + 1} in {where(depth)}: producer open over "
                f"{'the whole aquifer' if p_open == 'full' else f'its {p_open} half'}"
                + (f" (middle {num(row['producer_mid_m'], 0)} m)" if row else "")
                + f", {n_inj} injector{'s' if n_inj > 1 else ''} open over "
                + ("the whole aquifer" if i_open == "full" else f"its {i_open} half")
                + (
                    f"; rock {num(row['rock_c'])} °C, wellhead {num(row['wellhead_full_c'])} °C "
                    f"at full flow; injection {num(row['injection_full_bar'])} bar at full flow"
                    if row
                    else f"; rock {rock(depth)}"
                )
            )
        out.append("Wells: " + "; ".join(parts) + f". Reinjected at {num(y.reinjection_c)} °C.")
    if alt.n_doublets > 1:
        dispatch = (
            "the hottest doublet first, up to its cap (base load); the next takes the rest"
            if alt.dispatch == "base"
            else "in equal shares (the least pumping)"
        )
        sharing = (
            "one shared treatment train (separator and filters)"
            if trains == 1
            else f"{trains} treatment trains"
        )
        out.append(
            f"Each day the fewest doublets that carry the brine run, at least 50 m3/h each (the "
            f"hottest first; doublet 1 first when they are alike), so a doublet that is only "
            f"needed on cold days runs fewer days. Running doublets share the brine {dispatch}; "
            f"their brine meets in one heat plant after {sharing}; the doublets' planned stops: "
            f"{stop_dates.summary(y, entry.brief) or 'none'}."
        )
    if rows:
        out.append(
            "Over the year: "
            + "; ".join(
                f"doublet {r['doublet']} runs {r['days_on']} days at {num(r['flow_mean_m3h'])} "
                f"m3/h on average (cap {num(r['cap_m3h'], 0)}), its pumps "
                f"{num((r.get('esp_gwh') or 0) + (r.get('injection_gwh') or 0), 2)} GWh"
                for r in rows
            )
            + "."
        )
    if rows:
        wells = []
        for r in rows:
            wells.append(
                f"doublet {r['doublet']}: productivity index {num(r['pi_m3h_per_bar'])} m3/h/bar "
                f"(injectivity {num(r['injectivity_m3h_per_bar'])}), ESP head "
                f"{num(r['esp_head_full_bar'])} bar and injection wellhead "
                f"{num(r['injection_full_bar'])} bar at its cap of {num(r['cap_m3h'], 0)} m3/h; "
                f"heat lost up the producer {num(r['well_loss_full_k'])} K at the cap"
                + (
                    f"; cold water reaches the producer after {num(r['breakthrough_years'], 0)} "
                    f"years (Gringarten-Sauty, 1.5 km spacing, porosity 0.20; the life is 30); "
                    f"gas bubble point {num(r['bubble_point_bar'])} bar, so the ESP sits at "
                    f"{num(r['esp_setting_m'], 0)} m or deeper (at most 1,000 m allowed); "
                    f"injection pressure at the top of the reservoir {num(r['injection_top_bar'])} "
                    f"bar against SodM's limit of {num(r['injection_limit_bar'])} bar"
                    if r.get("breakthrough_years") is not None
                    else ""
                )
            )
        out.append(
            "Wells (pressures and pumps from GEMINI's well solve; the index, the heat loss and the "
            "subsurface checks from Dioscuri's models): "
            + "; ".join(wells)
            + ". The index is steady radial inflow from k·h (permeability × the open length) "
            "with skin 0, a 500 m drainage radius and an 8.5 in (0.108 m radius) well, both "
            "assumed; a half-open well has half the index. Heat loss up the producer: Ramey "
            "(1962), the rock warmed for one year, about 0.9 K at 300 m3/h and 5 K at 50 m3/h at "
            "2,500 m, falling with years. Wellhead 5 bar at the separator (the gas comes out of "
            "solution below about 40-45 bar, in the upper few hundred metres; that flash is not "
            "modelled). The breakthrough is an analytical estimate for one doublet; not modelled: "
            "how the producer cools after it, interference between doublets, the sinking of the "
            "cold injected water."
        )
    for w in y.warnings or []:
        out.append(w)
    return out


MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)  # 2027, the demand year
# Month words in English, Dutch, German and French (their first letters), for dates in messages.
MONTH_WORDS = {
    "jan": 0, "feb": 1, "fév": 1, "fev": 1, "mar": 2, "maa": 2, "mrt": 2, "mär": 2, "apr": 3,
    "avr": 3, "may": 4, "mei": 4, "mai": 4, "jun": 5, "juin": 5, "jul": 6, "juil": 6, "aug": 7,
    "aoû": 7, "aou": 7, "sep": 8, "oct": 9, "okt": 9, "nov": 10, "dec": 11, "dez": 11, "déc": 11,
}  # fmt: skip
_MON = (
    r"(jan|feb|f[ée]v|mar|maa|mrt|m[äa]r|apr|avr|may|mei|mai|jun|juin|jul|juil|aug|ao[ûu]|sep|"
    r"sept|oct|okt|nov|dec|dez|d[ée]c)[a-zäëéèû]*\.?"
)
_ORD = r"(?:st|nd|rd|th|e|ste|de|er)?"
_TO = r"(?:-|–|to|until|till|through|tot(?:\s+en\s+met)?|t/m|bis|au|jusqu'au)"
DAY_FIRST = re.compile(
    rf"\b(\d{{1,2}}){_ORD}\.?(?:\s*{_TO}\s*(\d{{1,2}}){_ORD}\.?)?\s+(?:of\s+)?" rf"{_MON}(?![a-z])",
    re.I,
)
MONTH_FIRST = re.compile(
    rf"\b{_MON}\s+(\d{{1,2}}){_ORD}(?:\s*{_TO}\s*(\d{{1,2}}){_ORD})?\b",
    re.I,
)
# A span over two months: "9 Jul to 12 Aug", "Jul 9 - Aug 12" (2 Nov: read as two single days).
SPAN_DAY_FIRST = re.compile(
    rf"\b(\d{{1,2}}){_ORD}\.?\s+(?:of\s+)?{_MON}(?![a-z])\s*{_TO}\s*(\d{{1,2}}){_ORD}\.?\s+"
    rf"(?:of\s+)?(jan|feb|f[ée]v|mar|maa|mrt|m[äa]r|apr|avr|may|mei|mai|jun|juin|jul|juil|aug|"
    rf"ao[ûu]|sep|sept|oct|okt|nov|dec|dez|d[ée]c)[a-zäëéèû]*\.?",
    re.I,
)
SPAN_MONTH_FIRST = re.compile(
    rf"\b{_MON}\s+(\d{{1,2}}){_ORD}\s*{_TO}\s*(jan|feb|f[ée]v|mar|maa|mrt|m[äa]r|apr|avr|may|"
    rf"mei|mai|jun|juin|jul|juil|aug|ao[ûu]|sep|sept|oct|okt|nov|dec|dez|d[ée]c)[a-zäëéèû]*\.?"
    rf"\s+(\d{{1,2}}){_ORD}\b",
    re.I,
)
ISO_DAY = re.compile(r"\b2027-(\d\d)-(\d\d)\b")
SLASH_DAY = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(?:20)?27)?\b")  # 19/7: day, then month
MONTH_ALONE = re.compile(
    r"\b(january|januari|januar|janvier|february|februari|februar|f[ée]vrier|march|maart|"
    r"m[äa]rz|mars|april|avril|june|juni|juin|july|juli|juillet|august|augustus|ao[ûu]t|"
    r"september|septembre|october|oktober|octobre|november|novembre|december|dezember|"
    r"d[ée]cembre|mei)\b"
    r"|\b(?:in|of|during|for|through|early|late|mid|im|en)\s+(may|mai)\b",
    re.I,
)


def month_of(word: str) -> int:
    """Return the month (0-11) of a month word in English, Dutch, German or French."""
    w = word.lower().rstrip(".")
    for key in sorted(MONTH_WORDS, key=len, reverse=True):
        if w.startswith(key):
            return MONTH_WORDS[key]
    raise ValueError(word)


MAX_DAY_ROWS = 14


def _day_index(month: int, day: int) -> Optional[int]:
    if not (0 <= month < 12 and 1 <= day <= MONTH_DAYS[month]):
        return None
    return sum(MONTH_DAYS[:month]) + day - 1


def _date(i: int) -> str:
    month = 0
    while i >= MONTH_DAYS[month]:
        i -= MONTH_DAYS[month]
        month += 1
    return f"{i + 1} {MONTHS[month].capitalize()}"


def named_days(message: str, limit: int = MAX_DAY_ROWS) -> Tuple[List[int], List[int]]:
    """Return the days (0-based, 2027) and the months (0-11) a message names.

    "28 January", "Jan 28", "25 to 31 January", "2027-01-28"; a month alone ("in November")
    gives the month. Parsing only: what the question is about is the model's job. At most
    ``limit`` days.
    """
    days: List[int] = []
    # Spans over two months first, taken out so their ends are not read as single days.
    for pattern, order in ((SPAN_DAY_FIRST, (1, 2, 3, 4)), (SPAN_MONTH_FIRST, (2, 1, 4, 3))):
        for m in pattern.finditer(message):
            d1, m1, d2, m2 = (m.group(k) for k in order)
            a = _day_index(month_of(m1), int(d1))
            b = _day_index(month_of(m2), int(d2))
            if a is not None and b is not None:  # over New Year: to 31 Dec, from 1 Jan
                days += (
                    list(range(a, b + 1)) if a <= b else list(range(a, 365)) + list(range(b + 1))
                )
        message = pattern.sub(" ", message)
    for m in DAY_FIRST.finditer(message):
        month = month_of(m.group(3))
        first, last = int(m.group(1)), int(m.group(2) or m.group(1))
        days += [i for d in range(first, last + 1) if (i := _day_index(month, d)) is not None]
    for m in MONTH_FIRST.finditer(message):
        month = month_of(m.group(1))
        first, last = int(m.group(2)), int(m.group(3) or m.group(2))
        days += [i for d in range(first, last + 1) if (i := _day_index(month, d)) is not None]
    for m in ISO_DAY.finditer(message):
        i = _day_index(int(m.group(1)) - 1, int(m.group(2)))
        if i is not None:
            days.append(i)
    for m in SLASH_DAY.finditer(message):
        i = _day_index(int(m.group(2)) - 1, int(m.group(1)))
        if i is not None:
            days.append(i)
    days = sorted(set(days))[:limit]
    named = {_date(i).split()[1].lower() for i in days}
    months = []
    for m in MONTH_ALONE.finditer(message):
        k = month_of(m.group(1) or m.group(2))
        if MONTHS[k] not in named and k not in months:
            months.append(k)
    return days, months


def _day_row(y, i: int) -> str:
    """One day of a design's year: each unit's MW and each doublet's flow."""

    def num(x, digits=2):
        return reporter.num(x, digits)

    d = y.daily_mw or {}
    h, c = d.get("heat", {}), d.get("cool", {})

    def at(part: dict, key: str) -> float:
        values = part.get(key) or []
        return float(values[i]) if i < len(values) else 0.0

    heat = (
        f"heat {num(at(h, 'demand'))} MW = exchanger {num(at(h, 'geo'))} + heat pump "
        f"{num(at(h, 'hp'))} + boiler {num(at(h, 'boiler'))}"
    )
    if at(h, "short") > 1e-3:
        heat += f", {num(at(h, 'short'))} MW short"
    cold = (
        f"cold {num(at(c, 'demand'))} MW = "
        + (f"free cooling {num(at(c, 'free'))} + " if at(c, "free") > 1e-3 else "")
        + f"absorption {num(at(c, 'abs'))} + chillers {num(at(c, 'chill'))}"
    )
    if at(c, "short") > 1e-3:
        cold += f", {num(at(c, 'short'))} MW short"
    from gemini_agent import stops as stop_dates

    wells = []
    stops = stop_dates.ranges_of(y)  # one block per doublet, or the user's ranges
    for k, row in enumerate(y.doublets or []):
        flow = float((row.get("flow_m3h") or [0.0] * 365)[i])
        if flow > 0:
            twh = (row.get("wellhead_c") or [None] * 365)[i]
            tre = (row.get("reinjection_c") or [None] * 365)[i]
            extra = f", wellhead {num(twh)} °C" if twh is not None else ""
            extra += f", reinjected at {num(tre)} °C" if tre is not None else ""
            wells.append(f"doublet {k + 1} {num(flow)} m3/h{extra}")
        elif stop_dates.stopped(stops, k, i):
            wells.append(f"doublet {k + 1} in its stop")
        else:
            wells.append(f"doublet {k + 1} idle (not needed)")
    return f"{_date(i)}: {heat}; {cold}; " + ", ".join(wells) + "."


def _month_row(y, month: int) -> str:
    """One month of a design's year: demand range, each doublet's days and flow, the boiler."""

    def num(x, digits=1):
        return reporter.num(x, digits)

    first = sum(MONTH_DAYS[:month])
    days = range(first, first + MONTH_DAYS[month])
    d = y.daily_mw or {}
    h = d.get("heat", {})
    demand = [float(h.get("demand", [0] * 365)[i]) for i in days]
    boiler = [float(h.get("boiler", [0] * 365)[i]) for i in days]
    wells = []
    for k, row in enumerate(y.doublets or []):
        flows = [float(row["flow_m3h"][i]) for i in days if row["flow_m3h"][i] > 0]
        wells.append(
            f"doublet {k + 1} runs {len(flows)} of {len(days)} days"
            + (f" at {num(min(flows))}-{num(max(flows))} m3/h" if flows else "")
        )
    short = sum(1 for i in days if float(h.get("short", [0] * 365)[i]) > 1e-3)
    return (
        f"{MONTHS[month].capitalize()}: heat demand {num(min(demand))}-{num(max(demand))} MW; "
        + "; ".join(wells)
        + f"; boiler {num(min(boiler))}-{num(max(boiler))} MW"
        + (f"; heat short on {short} days" if short else "")
        + "."
    )


def _starts(on: Sequence[bool]) -> int:
    return sum(1 for i, o in enumerate(on) if o and (i == 0 or not on[i - 1]))


NOT_IN_DESIGN = (
    "Not in this design or not modelled (say so; never describe them as there): heat storage "
    "or buffer tanks, a gas holder or a flare (the produced gas is burned in the boiler; with "
    "the boiler out the doublets would have to stop, venting methane is not acceptable), "
    "standby units, unit counts and minimum loads (each unit is one machine), hourly peaks "
    "(daily means only), trips, start-ups and ramping, network losses and pumping."
)
NOT_IN_RELIABLE = NOT_IN_DESIGN.replace(
    "standby units, unit counts and minimum loads (each unit is one machine)",
    "minimum loads of the units, two units out at once",
)


def not_modelled(entry) -> str:
    """Return what this design has not, or the model does not do, from the design itself.

    Fixed text said "network losses … not modelled" with the network switched on (1 Nov).
    """
    y, alt = entry.year, entry.alternative
    gas = getattr(alt, "gas", "buy")
    if gas == "sell":
        flare = "a gas holder or a flare (the brine's gas is cleaned and sold to the grid)"
    else:
        flare = (
            "a gas holder or a flare (the brine's gas is burned in the boiler; with the boiler "
            "out the doublets would have to stop, venting methane is not acceptable)"
        )
    parts = ["heat storage or buffer tanks", flare]
    parts.append(
        "minimum loads of the units, two units out at once"
        if alt.reliable
        else "standby units, unit counts and minimum loads (each unit is one machine)"
    )
    parts += ["hourly peaks (daily means only)", "trips, start-ups and ramping"]
    # Options the model has but this design runs without: modelled, only switched off (1 Nov:
    # "network losses are not modelled" beside a what-if that had switched the service on).
    off = []
    if not getattr(y, "network", None):
        off.append("the district network's losses and pumping (needs the trunk's length in km)")
    if not getattr(y, "service", None):
        off.append("each unit's yearly service")
    text = (
        "Not in this design or not modelled (say so; never describe them as there): "
        + ", ".join(parts)
        + "."
    )
    if off:
        text += (
            " Modelled but switched off in this design (the user can switch them on in chat or "
            "on the inputs card, and the year runs again): " + "; ".join(off) + "."
        )
    return text


def operations_block(entry, message: str = "") -> Optional[Block]:
    """Return how a design runs: firm capacity, the peak days, stops and starts, named days.

    The operator panel (31 Oct) got "covers 100 % of heating demand even if one production
    pump is lost" (7.2 MW short in truth), the wrong doublet on 19 July, a buffer tank and
    vented methane: the answerer had only yearly figures. These are the design's own numbers.
    """
    from gemini_agent import engine

    y, alt = entry.year, entry.alternative
    if not alt.n_doublets or not y.daily_mw:
        return None

    def num(x, digits=2):
        return reporter.num(x, digits)

    lines = []
    firm = engine.firm(entry) or {}
    peak = firm.get("peak") or {}
    if peak:
        lines.append(
            "Peak days: "
            + "; ".join(
                f"{'heat' if side == 'heat' else 'cold'} on {p['day']}, demand "
                f"{num(p['demand_mw'])} MW, the plant can give {num(p['capacity_mw'])} MW "
                f"(spare {num(p['spare_mw'])} MW)"
                for side, p in peak.items()
            )
            + "."
        )
    cases = []
    demand = {"heat": (y.daily_mw.get("heat") or {}), "cool": (y.daily_mw.get("cool") or {})}
    boiler = demand["heat"].get("boiler") or []
    size = alt.sizes_mw.get("boiler") or 0.0
    for o in firm.get("outages") or []:
        parts = []
        for side, word in (("heat", "heat"), ("cool", "cold")):
            x = o[side]
            if not x["days_short"]:
                continue
            i = x.get("worst_index")
            need = demand[side].get("demand") or []
            share = x["worst_mw"] / need[i] if i is not None and i < len(need) and need[i] else 0
            text = (
                f"{word} demand NOT met on {x['days_short']} days; worst {x['worst_day']}, "
                f"{num(x['worst_mw'])} MW short ({reporter.pct(share)} of that day's demand)"
            )
            if (
                side == "heat"
                and o["unit"] != "the boiler"
                and i is not None
                and i < len(boiler)
                and size
            ):
                if boiler[i] >= 0.99 * size:
                    text += ", the boiler already at full output that day"
            parts.append(text)
        unit = o["unit"]
        if unit.startswith("doublet"):
            unit += " (its producer, ESP or injector lost)"
        cases.append(f"{unit} out: " + ("; ".join(parts) or "all demand still met every day"))
    if cases:
        lines.append(
            "One unit out (N-1; the year run again with that unit out all year, the model has "
            "no trips: a trip of a few days is short only on the days it overlaps these): "
            + " | ".join(cases)
            + "."
        )
        heat = y.heat_delivered_gwh or 1.0
        boiler_days = sum(1 for v in (y.daily_mw.get("heat", {}).get("boiler") or []) if v > 1e-3)
        share = reporter.pct(y.heat_split_gwh.get("boiler", 0) / heat)
        if alt.sizes_mw.get("boiler") and alt.reliable:
            n = alt.boiler_units
            lines.append(
                f"This is a reliable plan: the boiler is {n} units of "
                f"{num(alt.sizes_mw['boiler'] / n)} MW ({num(alt.sizes_mw['boiler'])} MW in all) "
                f"and the electric chillers {alt.chiller_units} units, sized so that any one unit "
                f"of the plant can be out and every day is still met. The boiler gives {share} of "
                f"the year's heat and fires on {boiler_days} days."
            )
        elif alt.sizes_mw.get("boiler"):
            lines.append(
                f"The boiler gives {share} of the year's heat and fires on {boiler_days} days: it "
                "is the peak boiler, sized for the peak day with the doublets running, not a "
                "standby (the reliable plan of this layout adds the cover)."
            )
    h = (y.daily_mw.get("heat") or {}).get("demand") or []
    c = (y.daily_mw.get("cool") or {}).get("demand") or []
    picks = []
    if h:
        picks.append(int(max(range(len(h)), key=lambda i: h[i])))
    if c and any(c):
        picks.append(int(max(range(len(c)), key=lambda i: c[i])))
    days, months = named_days(message)
    rows = [_day_row(y, i) for i in sorted(set(picks + days))]
    lines.append(
        "Days ("
        + ("peak days and the days asked about" if days else "the peak days")
        + "): "
        + " ".join(rows)
    )
    lines += [_month_row(y, m) for m in months[:3]]
    from gemini_agent import stops as stop_dates

    stops = [
        f"doublet {k + 1} {stop_dates.span_words(r)}"
        for k, r in enumerate(stop_dates.ranges_of(y))
        if r
    ]
    starts = [
        f"doublet {k + 1} {_starts(r.get('on') or [])} start(s), {sum(r.get('on') or [])} days on"
        for k, r in enumerate(y.doublets or [])
    ]
    if stops:
        lines.append(
            "When the doublets stop (each runs at most the operating days the cap allows; the stop "
            "is also the window for their yearly maintenance; the user can move it to dates of "
            "their own on the inputs card, 'When the doublets stop', or by asking for a new "
            f"design) ({stop_dates.summary(y, entry.brief)}): " + "; ".join(stops) + "."
        )
    if starts:
        lines.append("Over the year: " + "; ".join(starts) + ".")
    lines.append(not_modelled(entry))
    if alt.n_doublets and alt.depth_m:  # spares and failures are questions of operation too
        from gemini_agent import reliability

        failures = reliability.failure_costs_note(entry)
        if failures:
            lines.append(failures)
    label = getattr(entry, "change_label", "")
    if label:
        # The what-if's own operation (1 Nov: its stop dates were read as the design's).
        lines.insert(0, f"In the what-if ({label}), not the design as it is:")
        return Block(f"{alt.code} what-if operation", "design", " ".join(lines))
    return Block(f"{alt.code} operation", "design", " ".join(lines))


GEMINI_TALK = re.compile(
    r"\bgemini\b|\btab\b|component|mixer|splitter|adder|separator|filter|\bloop\b|connection|"
    r"booster|\bchp\b|tubing|p&id|diagram|header",
    re.I,
)
GEMINI_ROLES = {
    "producer_well": "a producer: GEMINI's reservoir inflow (IPR), the well's tubing segments "
    "(DPDT) and the ESP, solved for the flow at the wellhead pressure",
    "mixer": "joins brine streams (flow-weighted temperature): a group's producers before "
    "their treatment train, or the trains before the heat exchanger",
    "separator": "takes the produced gas out of the brine (at the gas-liquid ratio of the "
    "aquifers its doublets produce from)",
    "filter": "removes particles before and after the heat exchanger (pressure drop)",
    "heat_exchanger": "passes the brine's heat to the heating network (counterflow)",
    "splitter": "shares the cooled brine among the injectors, each doublet its share",
    "injector_well": "an injector with its injection pump at 70 % efficiency",
    "adder": "sums the separated gas of several treatment trains for the boiler",
    "boiler": "burns the separated gas and heats the network after the exchanger",
}


def gemini_block(entry) -> Optional[Block]:
    """Return what the GEMINI project tab shows for a design: its loop, part by part.

    "Why is the mixer there?", "why no booster pump?": the components come from the design's
    own GEMINI project (``tools.gemini.plant_project``), so the answer names what is there.
    """
    from gemini_agent import engine
    from gemini_agent.tools import gemini as gem

    alt = entry.alternative
    if not alt.n_doublets or not alt.depth_m:
        return None
    rules = engine.rules_for(entry.brief)
    specs = alt.doublets or [{"depth_m": alt.depth_m} for _ in range(alt.n_doublets)]
    proj = gem.plant_project(specs, rules, alt.sizes_mw.get("boiler", 0.0))
    comps = proj["components"]
    parts = ", ".join(f"{name} ({c['type']})" for name, c in comps.items())
    used = []
    for kind, role in GEMINI_ROLES.items():
        n = sum(c["type"] == kind for c in comps.values())
        if n:
            used.append(f"{kind} ×{n}: {role}" if n > 1 else f"{kind}: {role}")
    absent = []
    types = {c["type"] for c in comps.values()}
    if "mixer" not in types:
        absent.append("no mixer: one producer per treatment train and one train")
    if "splitter" not in types:
        absent.append("no splitter: one injector")
    if "adder" not in types:
        absent.append("no adder: one separator (it sums the gas of several trains)")
    if "boiler" not in types:
        absent.append("no boiler: the design has none")
    text = (
        f"The GEMINI project tab shows {alt.code}'s brine loop as GEMINI itself simulates it, "
        f"one GEMINI component per piece of equipment, in the order the brine flows: {parts}. "
        "In this design: "
        + "; ".join(used)
        + ". "
        + ("Not needed here: " + "; ".join(absent) + ". " if absent else "")
        + "GEMINI types never in these designs: booster_pump (the treatment train is sized for "
        "a 1 bar drop at its design flow, so the producers' 5 bar wellhead pressure reaches the "
        "injection pumps at 4 bar, as the plant model assumes) and chp (the gas "
        "goes to the boiler). The tubing type (well, DPDT) is not a separate box: GEMINI's "
        "producer and injector wells contain it, with the reservoir inflow and the ESP. GEMINI "
        "has no heat pump, chiller or absorption model, so those are in the Plant view only. The "
        "ESP is GEMINI's example pump scaled to each producer's flow and head at the challenge's "
        "70 % (the example pump suits about 150 m3/h; its head is negative at 300 m3/h). The "
        "Plant view is the whole plant over the year from Dioscuri's model; the GEMINI view is "
        "one operating point at "
        "full flow, run on GEMINI's solver with 'Run on GEMINI'."
    )
    return Block("gemini", "design", text, "the design's GEMINI project")


def latest_designs(ledger: Sequence[object], chosen=None, limit: int = 4) -> List[object]:
    """Return the current design first, then the latest other designs (one per code)."""
    out: List[object] = []
    seen = set()
    order = ([chosen] if chosen is not None else []) + list(reversed(list(ledger)))
    for entry in order:
        key = (
            entry.alternative.code,
            entry.brief.reservoir_delta_c or 0,
            getattr(entry, "change_label", ""),
        )
        if key in seen or len(out) >= limit:
            continue
        seen.add(key)
        out.append(entry)
    return out


def design_blocks(ledger: Sequence[object], chosen=None, limit: int = 4) -> List[Block]:
    """Return blocks for the current design and the latest other designs (one per code)."""
    return [design_block(e, chosen=e is chosen) for e in latest_designs(ledger, chosen, limit)]


EQUIPMENT = {"heat_pump": "heat pumps", "boiler": "boilers", "chiller": "electric chillers"}


def brief_text(brief, project) -> str:
    """Return the brief in one plain paragraph, for the model's prompts."""
    from gemini_agent import engine

    parts = []
    # The challenge fixes the supplies and gives no returns; a user's project states both. The
    # defaults are said too: "which return did you assume?" had no 60 °C to answer from (S28).
    given = "(the project's own)" if getattr(project, "id", "challenge") != "challenge" else None
    heating = brief.heating or engine.DEFAULT_HEATING
    cooling = brief.cooling or engine.DEFAULT_COOLING
    assumed = "(supply fixed by the challenge, return assumed: not given in the requirements)"

    def net(name, t):  # "supply 100 °C, return 60 °C": "100/60 °C" was read as no return
        return f"{name} network supply {t.supply_c:g} °C, return {t.return_c:g} °C"

    parts.append(f"{net('heating', heating)} {given or assumed}")
    if brief.wants_cooling is not False:
        parts.append(f"{net('cooling', cooling)} {given or assumed}")
    if brief.reservoir_temp_c is not None:
        at = f" at {brief.reservoir_depth_m:g} m" if brief.reservoir_depth_m else ""
        parts.append(f"reservoir {brief.reservoir_temp_c:g} °C{at}")
    if project.has_heat_profile:
        own = getattr(project, "id", "challenge") != "challenge"
        parts.append(
            "daily heat and cold demand from "
            + (
                f"the project's files ({', '.join(project.files)})"
                if own
                else "the organisers' files"
            )
        )
    parts.append("1 to 3 doublets, 50-300 m3/h each, brine cooled by at most 40 K, 330 days")
    if brief.n_doublets:
        parts.append(f"{brief.n_doublets} doublet(s) asked for")
    if brief.excluded:
        parts.append("ruled out: " + ", ".join(EQUIPMENT[x] for x in brief.excluded))
    return "; ".join(parts) + "."


def project_block(project, brief, sheet: Optional[Dict[str, object]] = None) -> Block:
    """Return what is known before any design: the project's files, the brief, the reservoir."""
    from gemini_agent import lookup

    files = ", ".join(project.files) or "none"
    lines = [f"Project: {project.name}. Files: {files}."]
    lines += demand_lines(project)
    lines.append("What the conversation knows: " + brief_text(brief, project))
    for k, f in (sheet or {}).items():
        detail = f" ({f.detail})" if f.detail else ""
        lines.append(f"{lookup.LABELS[k]}: {f.value}{detail}; source: {f.source}.")
    return Block("project", "project", " ".join(lines))


def demand_lines(project) -> List[str]:
    """Return what the project's demand files hold, read by code (totals, peaks and their days)."""
    if not project.has_heat_profile:
        return []
    from gemini_agent import engine

    try:
        d = engine.demand_summary(getattr(project, "id", "challenge"))
    except Exception:  # noqa: BLE001 - a project removed meanwhile: its names are enough
        return []
    names = d["source"].split(", ")
    out = []
    for i, (what, total, peak, day) in enumerate(
        (
            ("heat", d["annual_heat_gwh"], d["peak_heat_mw"], d["peak_heat_day"]),
            ("cold", d["annual_cool_gwh"], d["peak_cool_mw"], d["peak_cool_day"]),
        )
    ):
        name = names[i] if i < len(names) and names[i] else "no file"
        if total <= 0:
            out.append(f"Daily {what} demand: none ({name}).")
            continue
        out.append(
            f"Daily {what} demand ({name}): 365 daily means in MW, {reporter.num(total)} GWh a "
            f"year, peak {reporter.num(peak)} MW on {day}."
        )
    return out


def _flat(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


PASSAGES = ("doc", "note", "file")
AUX_DESIGN = ("search", "runs", "decisions", "gemini", "designs")
MIN_HISTORY_CHARS = 900  # the history's end (the last exchange, the focus, the list) stays


def blocks_tokens(blocks: Sequence[Block]) -> int:
    """Return about how many tokens the blocks take in the prompt."""
    return sum(estimate_tokens(b.render()) + 1 for b in blocks)


def _whole_design(b: Block) -> bool:
    """Return True for a design's own block (not its costs, its operation or a list)."""
    return (
        b.kind == "design"
        and b.id not in AUX_DESIGN
        and not b.id.endswith((" costs", " operation"))
    )


def _cut(b: Block, chars: int, keep_end: bool = False) -> Block:
    """Return the block cut to ``chars`` at a word (its end kept with ``keep_end``)."""
    from dataclasses import replace

    text = b.text
    if len(text) <= chars:
        return b
    if keep_end:
        text = "…" + text[len(text) - chars :].split(" ", 1)[-1]
    else:
        text = text[:chars].rsplit(" ", 1)[0] + " …"
    return replace(b, text=text)


def _cut_lines(b: Block, chars: int) -> Block:
    """Return a list block cut to ``chars``: its first line and its last lines stay."""
    from dataclasses import replace

    if len(b.text) <= chars:
        return b
    lines = b.text.split("\n")
    keep: List[str] = []
    for line in reversed(lines[1:]):
        if len(lines[0]) + sum(len(x) + 1 for x in keep) + len(line) + 3 > chars:
            break
        keep.insert(0, line)
    return replace(b, text="\n".join([lines[0], "…"] + keep))


def _cut_history(b: Block, chars: int) -> Block:
    """Return the conversation cut to ``chars``, its middle given up.

    Its first line (the turn count), the chat's first two questions (T1, T2: "what did I ask
    first?" must not be answered from the earliest turn left, 4 Nov) and its latest lines stay.
    """
    from dataclasses import replace

    if len(b.text) <= chars:
        return b
    lines = b.text.split("\n")
    if len(lines) < 3 or len(lines[0]) > chars // 2:
        return _cut(b, chars, keep_end=True)
    first = [k for k, x in enumerate(lines) if re.match(r"T[12] user: ", x)]
    opening = [lines[k] for k in first]
    rest = [x for k, x in enumerate(lines[1:], 1) if k not in first and x != "…"]

    def size(xs: Sequence[str]) -> int:
        return sum(len(x) + 1 for x in xs)

    if size(opening) > chars // 3:  # long: only what the user asked in them
        opening = [x.split(" → ", 1)[0] for x in opening]
    if size(opening) > chars // 3:
        opening = []
    head = [lines[0]] + opening + ["…"]
    tail: List[str] = []
    for line in reversed(rest):
        if size(head) + size(tail) + len(line) + 1 > chars:
            break
        tail.insert(0, line)
    return replace(b, text="\n".join(head + tail))


def fit(blocks: Sequence[Block], budget: int) -> List[Block]:
    """Return the blocks that fit the budget, giving up the least useful context first.

    In order, until it fits: passages after the first two; the other designs cut to their
    values; the design search and the runs cut, the GEMINI block; the first two passages; the
    conversation cut to its latest part; the choices cut; the other designs; the cost and
    operation lines cut; last the self card, the project and the current design (the first
    design block) cut, and the conversation to its last lines. The draft and opened files
    stay whole, and every block keeps its start.

    Parameters
    ----------
    blocks : sequence of Block
        In prompt order.
    budget : int
        Tokens the context may take (``llm.estimate_tokens`` of each rendered block).

    Returns
    -------
    list of Block
        The blocks to send, in their order.
    """
    keep = list(blocks)
    if blocks_tokens(keep) <= budget:
        return keep
    passages = [b for b in keep if b.kind in PASSAGES]
    designs = [b for b in keep if _whole_design(b)]
    others = designs[1:]

    def by_id(name: str) -> List[Block]:
        return [b for b in keep if b.id == name]

    def swap(old: Block, new: Optional[Block]) -> None:
        if old in keep:
            i = keep.index(old)
            if new is None:
                keep.pop(i)
            else:
                keep[i] = new

    steps: List[Tuple[str, object, int]] = []
    steps += [("drop", b, 0) for b in reversed(passages[2:])]
    steps += [("cut", b, 420) for b in reversed(others)]
    steps += [("cut", b, SEARCH_CUT) for b in by_id("search")]  # the head and every pick
    steps += [("cut", b, 900) for b in by_id("runs")]
    steps += [("cut", b, 900) for b in by_id("changes")]
    steps += [("cut", b, 900) for b in by_id("state")]  # the chat's state (``chat_state``)
    steps += [("drop", b, 0) for b in by_id("gemini")]
    # What the plant can do (``capabilities``): its head, the options, before any design fact.
    steps += [("cut", b, 500) for b in by_id("capabilities")]
    steps += [("drop", b, 0) for b in reversed(passages[:2])]
    steps += [("tail", b, n) for b in by_id("history") for n in (2600, MIN_HISTORY_CHARS)]
    steps += [("end", b, 700) for b in by_id("turns")]  # the latest messages stay
    # The state's head (the designs in the order they came up) stays: "the second one".
    steps += [("cut", b, 450) for b in by_id("state")]
    steps += [("cut", b, 700) for b in by_id("decisions")]
    steps += [("drop", b, 0) for b in reversed(others)]
    steps += [("cut", b, 250) for b in by_id("capabilities")]
    # The cost and operation lines keep their first 2,000 characters (the totals, the peak days
    # and one unit out) before the design search goes: since the chat's state and the capability
    # card joined the context (4 Nov), "what did the search go through?" lost its block.
    steps += [
        ("cut", b, 2000)
        for b in keep
        if b.kind == "design" and b.id.endswith((" costs", " operation"))
    ]
    steps += [("drop", b, 0) for name in ("search", "runs", "changes") for b in by_id(name)]
    steps += [
        ("cut", b, 1500)
        for b in keep
        if b.kind == "design" and b.id.endswith((" costs", " operation"))
    ]
    # Last, rather than a prompt the window refuses (and the template in its place): the full
    # self card, the project, the current design and the history's end, cut shorter.
    steps += [("cut", b, 1800) for b in keep if b.kind == "self"]
    steps += [("cut", b, 1400) for b in keep if b.kind == "project"]
    steps += [("cut", b, 3000) for b in designs[:1]]
    steps += [("tail", b, 500) for b in by_id("history")]
    done: List[Tuple[str, Block]] = []  # each step taken, with the block as it was before
    for how, block, size in steps:
        now = next((b for b in keep if b.id == block.id), None)
        if now is None:
            continue
        if how == "drop":
            swap(now, None)
        elif how == "tail":
            swap(now, _cut_history(now, size))
        elif how == "end":
            swap(now, _cut_lines(now, size))
        else:
            swap(now, _cut(now, size))
        done.append((how, now))
        if blocks_tokens(keep) <= budget:
            break
    return _put_back(keep, blocks, done, budget)


# A dropped block that comes back cut: the design search with its picks and their why-not lines,
# the runs with their figures (``_put_back``).
PUT_BACK_CUT = {"search": 2800, "changes": 900, "runs": 900}
SEARCH_CUT = PUT_BACK_CUT["search"]


def _put_back(
    keep: List[Block], blocks: Sequence[Block], done: Sequence[Tuple[str, Block]], budget: int
) -> List[Block]:
    """Return the blocks with what still fits put back after ``fit``'s steps.

    The steps are greedy: a block dropped early stays out even when a later cut frees room
    enough for it. 5 Nov: "which designs did the search pick?" dropped the search (4,000
    tokens) before the current design was cut to 3,000 characters, and went out at 3,446
    tokens of 5,083 with no picks, so the model listed other designs as the picks. First the
    dropped blocks come back (the search and the runs first, cut to ``PUT_BACK_CUT``), then the
    cuts are undone, the latest first, each when it fits.
    """
    order = {b.id: i for i, b in enumerate(blocks)}

    def with_(block: Block) -> List[Block]:
        out = [b for b in keep if b.id != block.id] + [block]
        return sorted(out, key=lambda b: order.get(b.id, len(order)))

    present = {b.id for b in keep}
    dropped = [b for how, b in done if how == "drop" and b.id not in present]
    dropped.sort(key=lambda b: (b.id not in PUT_BACK_CUT, order.get(b.id, len(order))))
    for gone in dropped:
        whole = next((b for b in blocks if b.id == gone.id), gone)
        tries = [_cut(whole, PUT_BACK_CUT[gone.id])] if gone.id in PUT_BACK_CUT else []
        for block in tries + [gone]:
            trial = with_(block)
            if blocks_tokens(trial) <= budget:
                keep = trial
                break
    for how, before in reversed(done):
        if how == "drop" or not any(b.id == before.id for b in keep):
            continue
        trial = [before if b.id == before.id else b for b in keep]
        if blocks_tokens(trial) <= budget:
            keep = trial
    return keep


# ----------------------------------------------------------------- the checks


def contains(text: str, item: str) -> bool:
    """Return True when ``text`` gives ``item``: its numbers, or the words if it has none.

    An item that starts with "~" is a long fact (every well check, the cost by part): any one
    of its numbers will do, since a question asks about a part of it.
    """
    if item.startswith("~"):
        said = numbers_in(text)
        return any(any(abs(n - x) < 1e-9 for x in said) for n in numbers_in(item[1:]))
    numbers = numbers_in(item)
    if not numbers:
        return item.lower() in text.lower()
    said = numbers_in(text)
    return all(any(abs(n - x) < 1e-9 for x in said) for n in numbers)


def _numbers_with_units(text: str) -> List[Tuple[float, bool]]:
    """Return each loose number in ``text`` and whether a unit follows it."""
    out = []
    for m in re.finditer(r"(?<![A-Za-z\d.])\d+(?:[.,]\d+)*", text):
        for n in numbers_in(m.group(0)):
            out.append((n, bool(UNITS.match(text, m.end()))))
    return out


def unsourced(text: str, facts: reporter.Facts) -> List[float]:
    """Return the numbers in ``text`` that no block, user message or calculation supports.

    A number passes when ``facts`` has it, when it is a difference, sum, ratio or percentage
    change of two sourced numbers that ``text`` itself states (rounded as written), or when it
    is a small count (at most 5, with no unit after it).

    Parameters
    ----------
    text : str
        The reply.
    facts : reporter.Facts
        Number register of the context and the user's message.

    Returns
    -------
    list of float
        The numbers with no support.
    """
    text = EXPONENT.sub("", strip_cites(text))  # 10^{6}: a power of ten, not a value
    loose = [n for n in facts.ungrounded(text) if n not in CONSTANTS]
    if not loose:
        return []
    units = {n: unit for n, unit in _numbers_with_units(text)}
    # A derived number counts only with its operands in the same sentence or table row: across
    # a whole reply, 87 - 20 = 67 would excuse an invented "67 °C" (30 Oct).
    allowed = set()
    for segment in _segments(text):
        here = [n for n, _ in _numbers_with_units(segment)]
        stated = [n for n in here if n not in loose]
        worked = bool(ARITHMETIC.search(segment))
        for n in here:
            if n not in loose:
                continue
            tol = 0.5 if n == int(n) else 0.05
            if any(abs(n - d) <= tol for d in _derived(stated)):
                allowed.add(n)
            elif worked and _chained(n, [x for x in here if x != n], loose):
                allowed.add(n)
    out = []
    for n in loose:
        if n == int(n) and n <= 5 and not units.get(n, False):
            continue
        if n in allowed:
            continue
        out.append(n)
    return out


def _segments(text: str) -> List[str]:
    """Split a reply into table rows and sentences (what a derived number may lean on)."""
    out: List[str] = []
    for line in text.split("\n"):
        if TABLE_ROW.match(line) or TABLE_RULE.match(line):
            out.append(line)
            continue
        lead = LINE_LEAD.match(line)
        out.extend(sentences(line[len(lead.group(0)) :] if lead else line))
    return out


# Unit conversions and physical constants a worked formula may use without a source.
CONSTANTS = {10.0, 24.0, 60.0, 100.0, 1000.0, 3600.0, 8760.0, 273.15, 9.81, 3.6, 1e6}
EXPONENT = re.compile(r"\^\{?-?\d+\}?")
ARITHMETIC = re.compile(r"[×*·/=≈]|\\times|\\cdot|\\frac|\\approx")


def _chained(n: float, operands: Sequence[float], loose: Sequence[float]) -> bool:
    """Return True when ``n`` is the product of the sentence's other numbers (some divided).

    A worked formula ("1030 × 300/3600 × 3990 × 40 ≈ 13.7 MW") shows every operand, each
    sourced or a constant; its result, rounded as written and in W, kW or MW, passes.
    """
    ops = [x for x in operands if x and x not in loose][:7]
    if len(ops) < 2:
        return False
    for signs in itertools.product((0, 1, -1), repeat=len(ops)):
        if sum(1 for x in signs if x) < 2:
            continue
        value = 1.0
        for x, sign in zip(ops, signs):
            value *= x**sign
        for scale in (1.0, 1e-3, 1e-6, 1e3, 1e6):
            if abs(value * scale - n) <= 0.01 * abs(n) + 1e-9:
                return True
    return False


# A calculation written out in a reply ("86.1 °C - 40 K = 52.1 °C", "6.5 + 1.7 + … = 75.7"):
# its numbers, each maybe with a unit, joined by + - × / and ending in "=" and its result.
SUM_NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])|(?<![\w.])\d+(?:\.\d+)?")
SUM_GAP = re.compile(r"^[^\d=;:!?]{0,14}?\s*(?P<op>[+\-−×÷/]|(?:(?<=\s)|^)[x*](?=\s|$))\s*\(?\s*$")
SUM_RESULT = re.compile(
    r"^\s*(?:≈|~|\\approx)?\s*\$?\s*\**\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
)
SUM_SCALES = (1.0, 1e3, 1e-3, 1e6, 1e-6, 100.0, 0.01)
# Words between a calculation's numbers mean it is prose ("on 2027-01-28 the COP = 3.2").
SUM_WORDS = re.compile(r"\b(the|a|an|and|or|of|is|are|was|so|at|on|in|with|for|to|by|from)\b", re.I)


def _plain_math(text: str) -> str:
    """Return text with its LaTeX as plain signs: a text command's words, "×" for times."""
    t = re.sub(r"\\(?:text|mathrm|textbf)\{([^}]*)\}", r"\1", text)
    t = re.sub(r"\\(?:times|cdot)", "×", t)
    t = t.replace("\\approx", "≈").replace("\\%", "%").replace("\\,", " ").replace("$", "")
    t = re.sub(r"\*\*|__", "", t)  # bold, not a product
    return t.replace("−", "-").replace("–", "-")


def wrong_sums(text: str) -> List[Tuple[str, float, float]]:
    """Return each calculation in ``text`` whose result is wrong: (as written, right, written).

    Only plain chains of + - × / are read; one with a fraction, brackets or anything else is
    left alone. Rounding passes: the operands' last digits, and the result written in other
    units (W for MW, % for a share).
    """
    out = []
    for line in _plain_math(text).splitlines():
        if "\\frac" in line:
            continue
        for part in re.split(r"(?<=[!?;])\s+|(?<=\D[.:])\s+", line):
            pieces = part.split("=")
            for k in range(1, len(pieces)):
                left, right = pieces[k - 1], pieces[k]
                res = SUM_RESULT.match(right)
                nums = list(SUM_NUMBER.finditer(left))
                if not res or len(nums) < 2:
                    continue
                # From the last number back: each gap must be a unit and one operator.
                terms, ops = [nums[-1]], []
                for prev in reversed(nums[:-1]):
                    between = left[prev.end() : terms[0].start()]
                    gap = SUM_GAP.match(between)
                    # "2027-01-28" and "50-300" are a date and a range, not a subtraction.
                    if not gap or SUM_WORDS.search(between) or between == "-":
                        break
                    terms.insert(0, prev)
                    ops.insert(0, gap.group("op"))
                tail = left[nums[-1].end() :]
                if (
                    not ops
                    or "(" in tail
                    or ")" in left[terms[0].start() :]
                    or len(tail.strip()) > 14
                    or SUM_WORDS.search(tail)
                ):
                    continue
                values = [float(m.group(0).replace(",", "")) for m in terms]
                expr = str(values[0])
                for op, v in zip(ops, values[1:]):
                    expr += {"−": "-", "×": "*", "x": "*", "÷": "/"}.get(op, op) + str(v)
                try:
                    right_value = float(eval(expr, {"__builtins__": {}}))  # noqa: S307 - digits
                except ZeroDivisionError:
                    continue
                stated = float(res.group(1).replace(",", ""))
                digits = [len(m.group(0).split(".")[1]) if "." in m.group(0) else 0 for m in terms]
                slack = sum(0.5 * 10**-d for d in digits) + 0.5 * 10 ** -(
                    len(res.group(1).split(".")[1]) if "." in res.group(1) else 0
                )
                ok = any(
                    abs(right_value * f - stated) <= max(slack * f, 0.02 * abs(stated)) + 1e-9
                    for f in SUM_SCALES
                )
                if not ok:
                    written = left[terms[0].start() :].strip() + " = " + res.group(1)
                    out.append((written, right_value, stated))
    return out


def _derived(stated: Sequence[float]) -> Iterable[float]:
    for a, b in itertools.permutations(set(stated), 2):
        yield abs(a - b)
        yield a + b
        if b:
            yield a / b
            yield a / b * 100
            yield abs(a - b) / b * 100


def sentences(text: str) -> List[str]:
    """Split a reply where sentences end; quotes and brackets stay with their sentence."""
    return [s for s in re.split(r"(?<=[.!?\]])\s+(?=[A-Z“(\"'*])", text.strip()) if s]


def strip_cites(text: str) -> str:
    """Return ``text`` without citation markers, whose digits are not values."""
    return CITE_ID.sub("", CITE_MARK.sub("", text))


def keep_sourced(text: str, facts: reporter.Facts) -> str:
    """Drop what carries an unsourced number, keeping the Markdown around the rest.

    A table row goes whole; in a list item, a heading or a paragraph line only the sentences
    with such a number go. A table with no rows left loses its header too.
    """
    out: List[str] = []
    for line in text.split("\n"):
        if TABLE_ROW.match(line) or TABLE_RULE.match(line):
            if TABLE_RULE.match(line) or not unsourced(line, facts):
                out.append(line)
            continue
        lead = LINE_LEAD.match(line)
        prefix = lead.group(0) if lead else ""
        body = line[len(prefix) :]
        if not body.strip():
            out.append(line if not prefix else "")
            continue
        kept = [x for x in sentences(body) if not unsourced(x, facts)]
        if kept:
            out.append(prefix + " ".join(kept))
    lines: List[str] = []
    for i, line in enumerate(out):
        nxt = out[i + 1] if i + 1 < len(out) else ""
        after = out[i + 2] if i + 2 < len(out) else ""
        if TABLE_RULE.match(line) and not _row(nxt):
            continue
        if _row(line) and TABLE_RULE.match(nxt) and not _row(after):
            continue  # a header with no rows under it
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def drop_copies(text: str, blocks: Sequence[Block]) -> Tuple[str, bool]:
    """Remove tables that copy an opened file's rows, with the line that leads into them.

    Returns
    -------
    tuple of (str, bool)
        The text and whether a copy was removed.
    """
    known = {_cell(c) for b in blocks for c in b.columns}
    if not known:
        return text, False
    lines = text.split("\n")
    out: List[str] = []
    i, removed = 0, False
    while i < len(lines):
        if _row(lines[i]) and i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1]):
            head = [_cell(c) for c in lines[i].strip().strip("|").split("|")]
            end = i + 2
            while end < len(lines) and TABLE_ROW.match(lines[end]):
                end += 1
            if len([h for h in head if h in known]) >= min(2, len(head)):
                while out and not out[-1].strip():
                    out.pop()
                if out and out[-1].rstrip().endswith(":"):
                    out.pop()  # "Here is the table:"
                i, removed = end, True
                continue
        out.append(lines[i])
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip(), removed


def _cell(text: str) -> str:
    """Return a column name as compared: no unit in brackets, no Markdown, lower case."""
    text = re.sub(r"[*`_]", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"[\[(].*?[\])]", "", text)).strip().lower()


def _row(line: str) -> bool:
    return bool(TABLE_ROW.match(line)) and not TABLE_RULE.match(line)


def cite(text: str, blocks: Sequence[Block], used: Sequence[str]) -> Tuple[str, List[Block]]:
    """Turn the model's ``[doc1]`` citations into the chat's numbered ``[^1]`` markers.

    Parameters
    ----------
    text : str
        The checked reply.
    blocks : sequence of Block
        The context pack.
    used : sequence of str
        The ids the model listed as used.

    Returns
    -------
    tuple of (str, list of Block)
        The text, and the blocks with a source card in card order: the ones cited in the text
        first, then the other used ones. Citations of blocks without a card (the project, a
        design, the draft) and of ids that do not exist are removed.
    """
    by_id = {b.id.lower(): b for b in blocks}
    by_title = {b.title.lower(): b for b in blocks if b.kind == "data"}
    order: List[Block] = []
    first: Dict[tuple, Block] = {}  # passages from the same place share one card

    def card(b: Block) -> Block:
        where = (b.passage.get("source"), b.passage.get("section"))
        return first.setdefault(where, b)

    def number(match: re.Match) -> str:
        marks = []
        for raw in match.group(1).split(","):
            key = raw.strip().lower()
            b = by_id.get(key)
            named = b is None and key in by_title  # "[heating_profile.csv]" keeps the name
            b = b or by_title.get(key)
            if b is None:
                if key in by_id or re.fullmatch(r"(doc|note|file|data)\d+|draft|self", key):
                    continue
                return match.group(0)  # brackets that are not a citation
            if b.passage is None:
                continue
            b = card(b)
            if b not in order:
                order.append(b)
            mark = f"[^{order.index(b) + 1}]"
            if mark not in marks:
                marks.append((f" {b.title}" if named else "") + mark)
        return "".join(marks)

    text = CITE_ID.sub(number, text)
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    for u in used:
        b = by_id.get(u.lower())
        if b is not None and b.passage is not None and card(b) not in order:
            order.append(card(b))
    return text.strip(), order


# ------------------------------------------------------------------ the call


def schema(
    ids: Sequence[str], reasoning: bool, kinds: Sequence[str] = KINDS, run: bool = False
) -> dict:
    """Return the reply's JSON schema; ``used`` may only name blocks that exist.

    ``run``: the model may ask for a design run instead of answering (``"run"``).
    """
    props = {
        "understood": {"type": "string", "maxLength": 200},
        "premises": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "said": {"type": "string", "maxLength": 120},
                    "agrees": {"type": "boolean"},
                    "right": {"type": "string", "maxLength": 200},
                },
                "required": ["said", "agrees", "right"],
            },
            "maxItems": 3,
        },
        "kind": {"type": "string", "enum": list(kinds)},
        "scope": {"type": "string", "enum": list(SCOPES)},
        "answer": {"type": "string", "maxLength": ANSWER_CHARS},
        "options": {
            "type": "array",
            "items": {"type": "string", "maxLength": 120},
            "maxItems": 4,
        },
        "used": {"type": "array", "items": {"type": "string", "enum": list(ids)}, "maxItems": 6},
        "follow_ups": {
            "type": "array",
            "items": {"type": "string", "maxLength": 100},
            "maxItems": 3,
        },
    }
    order = ["understood", "premises", "kind", "scope", "answer", "options", "used", "follow_ups"]
    if run:
        props["run"] = {"type": "string", "enum": ["none", "design"]}
        order.insert(order.index("used") + 1, "run")
    if "clarify" not in kinds:
        props.pop("options")
        order.remove("options")
    if reasoning:
        props = {"steps": _steps(), **props}
        order = ["steps"] + order
    return {"type": "object", "properties": props, "required": order}


def _steps() -> dict:
    return {
        "type": "array",
        "items": {"type": "string", "maxLength": 140},
        "minItems": 1,
        "maxItems": 3,
    }


# What the rules say of the challenge district that a user's project states for itself.
OWN_PROJECT = (
    ("every day of 2027", "every day of the year"),
    (
        "say what was assumed (the network return temperatures are not given)",
        "say what was assumed (the project gives its own network temperatures)",
    ),
)


def rules(
    blocks: Sequence[Block],
    kinds: Sequence[str] = KINDS,
    own_project: bool = False,
    run: bool = False,
) -> str:
    """Return the answer prompt with only the rules that apply to these blocks and kinds.

    ``own_project``: the conversation is in a user's project, not the challenge district.
    ``run``: the model may ask for a design run (the ``{run}`` rule).
    """
    tags = {b.kind for b in blocks} | {"open" if len(kinds) > 1 else "closed"}
    if run:
        tags.add("run")
    out = []
    for line in load(ANSWER_PROMPT).splitlines():
        m = RULE_TAG.match(line)
        if m is None or m.group(1) in tags:
            out.append(RULE_TAG.sub("", line))
    text = "\n".join(out)
    for old, new in OWN_PROJECT if own_project else ():
        text = text.replace(old, new)
    return text


def messages(
    message: str,
    blocks: Sequence[Block],
    reasoning: bool,
    vision: bool = False,
    kinds: Sequence[str] = KINDS,
    own_project: bool = False,
    run: bool = False,
) -> List[dict]:
    """Return the chat messages: the rules, then the context, then the user's message.

    With ``vision``, the images of the blocks go with the user's message (at most two).
    """
    system = rules(blocks, kinds, own_project, run)
    if reasoning:
        system += (
            "\nsteps: before answering, up to 3 short reasoning steps (under 20 words each): "
            "what is asked, which blocks answer it, what follows."
        )
    context = "\n".join(b.render() for b in blocks)
    user = f"Context:\n{context}\n\nUser's message: {message}"
    turn = {"role": "user", "content": user}
    images = [b.image for b in blocks if b.image and Path(b.image).is_file()][:2]
    if vision and images:
        turn["images"] = [Path(i).read_bytes() for i in images]
    return [{"role": "system", "content": system}, turn]


def budget(llm, reasoning: bool, message: str = "", think: bool = False) -> int:
    """Return the tokens the context blocks may take.

    The window's room after the answer (and the notes of the thinking, with ``think``), the
    rules and the message, and never more than ``MAX_PROMPT_TOKENS`` in all: the 16k window
    of a GPU keeps the whole context beside the notes, an 8k one gives up some of it. The
    rules of the code-written values (``ROOM_OF_THEIR_OWN``) are not counted: a turn with
    values gets room for them on top (``answer``), and a turn without them keeps its context.
    """
    rules = estimate_tokens(_counted_rules()) + estimate_tokens(message) + 160
    notes = THINK_TOKENS + 60 if think else 0
    total = min(room(llm, NUM_PREDICT + notes) - 40, MAX_PROMPT_TOKENS)
    return max(500, total - rules - (60 if reasoning else 0))


# Blocks that come with room of their own: the values code wrote for the question are added on
# top of the context, with their rule, never in place of it. 5 Nov: counted in the budget, the
# "values" rule cut 260-450 tokens of context from every answer, values or not, and with it the
# facts the claim checker needed ("a gradient of 30 °C/km" removed; the gas reference a
# design's CO2 saving is worked out from).
ROOM_OF_THEIR_OWN = ("values",)


def _counted_rules() -> str:
    """Return the answer prompt without the rules of blocks that have room of their own."""
    return "\n".join(
        line
        for line in load(ANSWER_PROMPT).splitlines()
        if not ((m := RULE_TAG.match(line)) and m.group(1) in ROOM_OF_THEIR_OWN)
    )


def own_room(blocks: Sequence[Block]) -> int:
    """Return the tokens the blocks with room of their own take, with their rules."""
    own = [b for b in blocks if b.kind in ROOM_OF_THEIR_OWN]
    if not own:
        return 0
    rules = [
        line
        for line in load(ANSWER_PROMPT).splitlines()
        if (m := RULE_TAG.match(line)) and m.group(1) in {b.kind for b in own}
    ]
    return blocks_tokens(own) + estimate_tokens("\n".join(rules))


def think_first(llm, msgs: List[dict], out: "Reply") -> List[dict]:
    """Let the model think about the answer's prompt; return the prompt with its notes added.

    The thinking is a call of its own with no format, cut at ``THINK_TOKENS``; its record (the
    thinking shortened) joins ``out.calls``. Nothing is added when the call fails or the model
    does not think: the answer is then written as on any turn.
    """
    if not callable(getattr(llm, "think", None)):
        return msgs
    try:
        thought, after, call = llm.think("think", msgs, THINK_TOKENS)
    except LLMError as err:
        if err.call is not None:
            out.calls.append(err.call)
        out.corrections.append("the thinking call failed: answered without it")
        return msgs
    out.calls.append(call)
    notes = (thought.strip() + ("\n\n" + after.strip() if after.strip() else "")).strip()
    if not notes:
        return msgs
    return msgs + [{"role": "user", "content": THINK_NOTES.format(notes=notes)}]


def answer(
    llm,
    message: str,
    blocks: Sequence[Block],
    facts: reporter.Facts,
    fallback: str,
    must: Sequence[str] = (),
    reasoning: bool = False,
    kinds: Sequence[str] = KINDS,
    own_project: bool = False,
    run: bool = False,
    only: Sequence[str] = (),
    costs: Sequence[Tuple[float, Optional[float], float]] = (),
    plans: Sequence[Tuple[str, str, bool, str]] = (),
    premises: Sequence[str] = (),
    judge_premises: bool = False,
    drafted: bool = True,
    theirs: Sequence[Tuple[str, Sequence[str]]] = (),
    think: bool = False,
    revise: Optional[Tuple[str, str]] = None,
) -> Reply:
    """Let the model write the reply from the blocks, then check it.

    ``only``: the design codes the reply may name (a comparison's); naming another one is
    asked again, then the checked draft is shown.

    Parameters
    ----------
    llm : OllamaLLM or ScriptedLLM
        The answering model.
    message : str
        What the user wrote.
    blocks : sequence of Block
        The context pack, in prompt order.
    facts : reporter.Facts
        Number register; the numbers of every block are added to it here.
    fallback : str
        The checked template answer, shown when the model fails (every number in it is
        already registered).
    must : sequence of str
        Key values the reply must keep (for example ``"41 €/MWh"``).
    reasoning : bool
        Ask for up to three reasoning steps first.
    kinds : sequence of str
        The kinds of reply allowed (only ``"answer"`` after a tool run).
    own_project : bool
        The conversation is in a user's project (its year and networks are its own).
    run : bool
        The model may ask for a design run instead of answering (``Reply.action``).
    premises : sequence of str
        The message's words that state something as given; the model checks each first.
    judge_premises : bool
        No planner read the message (before a design, a message about Dioscuri, a why): the
        model's own premises count, so a wrong statement is still said to be wrong first.
    theirs : sequence of (str, sequence of str)
        Values the question asked for as other designs have them, with those designs' names:
        a sentence that gives one without naming its design says it of the design asked about
        (4 Nov: "the cheapest saves 60.6 %", the recommended design's figure; it saves 64 %).
    drafted : bool
        ``fallback`` is a checked answer. Without one (a free answer, a summary of the chat) a
        cost still mislabelled after the retry loses its sentences, not the whole reply: the
        generic "couldn't confirm" stood for "sum up what we found" (4 Nov).
    think : bool
        Let the model think before it writes the answer (``DIOSCURI_THINK``, hard turns on a
        GPU): a call of its own with no format, at most ``THINK_TOKENS`` (``think_first``),
        whose thinking the answer call reads as notes. The thinking is never in the reply; its
        call record keeps it, shortened.
    revise : (str, str), optional
        The reply as first written and what to change (the reply check's rewrite): the same
        prompt, then that reply and the instruction, one call (purpose ``rewrite``) and the
        same checks as any answer.

    Returns
    -------
    Reply
        The reply to show and how it was decided.
    """
    vision = bool(VISION.search(str(getattr(llm, "model", ""))))
    asked = message
    if premises:  # what the reasoning model found the message states as given
        asked += (
            "\n\n(Stated as given; check each against the context first: "
            + "; ".join(f"“{p}”" for p in premises)
            + ")"
        )
    think = think and revise is None
    blocks = fit(blocks, budget(llm, reasoning, asked, think) + own_room(blocks))
    msgs = messages(asked, blocks, reasoning, vision, kinds, own_project, run)
    over = prompt_tokens(msgs) - room(llm, NUM_PREDICT + (THINK_TOKENS + 60 if think else 0))
    if over > 0:  # the rules, the steps or an image took more than the budget allowed for
        blocks = fit(blocks, max(300, blocks_tokens(blocks) - over - 80))
        msgs = messages(asked, blocks, reasoning, vision, kinds, own_project, run)
    if revise is not None:
        # The same prompt (its start is cached), then the first reply and what to change.
        again = [
            {"role": "assistant", "content": revise[0][:ANSWER_CHARS]},
            {"role": "user", "content": revise[1]},
        ]
        over = prompt_tokens(msgs + again) - room(llm, NUM_PREDICT)
        if over > 0:
            fewer = fit(blocks, max(300, blocks_tokens(blocks) - over - 80))
            msgs = messages(asked, fewer, reasoning, vision, kinds, own_project, run)
        msgs = msgs + again
    for b in blocks:  # the history too: "you first asked about 200 GWh" quotes the user
        facts.put(b.text)
    ids = [b.id for b in blocks]
    out = Reply(fallback, fallback=True)
    if think:
        msgs = think_first(llm, msgs, out)
    raw: Dict[str, object] = {}
    first_understood = ""
    first_premises = None
    shape = schema(ids, reasoning, kinds, run)
    purpose = "rewrite" if revise is not None else "answer"
    for attempt in range(1 if revise is not None else 2):
        try:
            raw, call = llm.structured(purpose, msgs, shape, NUM_PREDICT)
        except LLMError as err:
            if err.call is not None:
                out.calls.append(err.call)
            out.unavailable = str(err) if isinstance(err, ModelUnavailable) else ""
            gone = "isn't available" if out.unavailable else "gave no usable reply"
            out.note = f"the answering model {gone}; showed the checked template"
            return out
        out.calls.append(call)
        if run and raw.get("run") == "design":
            # The model judged that a design was asked for: the agent runs it (the reply's
            # one sentence is not shown; the design's own reply follows).
            out.action, out.fallback = "design", False
            out.understood = str(raw.get("understood", "")).strip()
            out.kind, out.scope = "answer", "project"
            return out
        problems = (
            _problems(raw, facts, must, fallback)
            + _strangers(raw, only)
            + _swaps(raw, costs)
            + _n1_claims(raw, plans)
            + _theirs_problems(raw, theirs)
        )
        if not problems or not str(raw.get("answer", "")).strip():
            break  # an empty reply is not worth a retry: the template is shown
        if attempt == 0:
            # What the user asked, as first understood: the retry's "understood" describes the
            # correction ("You want the JSON again with …"), which the steps would show.
            first_understood = str(raw.get("understood", "")).strip()
            first_premises = raw.get("premises")
            again = [
                {"role": "assistant", "content": str(raw.get("answer", ""))[:ANSWER_CHARS]},
                {"role": "user", "content": "Write the JSON again. " + " ".join(problems)},
            ]
            over = prompt_tokens(msgs + again) - room(llm, NUM_PREDICT)
            if over > 0:  # the retry's two messages need room too: less context for it
                fewer = fit(blocks, max(300, blocks_tokens(blocks) - over - 80))
                msgs = messages(asked, fewer, reasoning, vision, kinds, own_project, run)
            msgs = msgs + again
            out.corrections.append("asked the model again: " + " ".join(problems))
    if first_understood:
        raw = dict(raw, understood=first_understood)
    if first_premises is not None:  # the retry's premises read the correction, not the user
        raw = dict(raw, premises=first_premises)
    # A correction code made (the draft opens with it) always leads; else the model's own
    # judgement of the premises, unless its reply already opens with "No".
    code_lead = fallback.split("\n\n")[0] if fallback.startswith("**Not quite.**") else ""
    # The model's own premises count only when the reasoning model found the message states
    # some (1 Nov: "could we move the stop to August?" got "Not quite. It is already ...").
    lead = code_lead or (premise_lead(raw, facts, message) if premises or judge_premises else "")
    text = str(raw.get("answer", "")).strip()
    if lead and text:
        bare = lead.replace("**Not quite.** ", "")
        for copy in (lead, bare, *sentences(bare)):
            text = text.replace(copy, "")
        text = re.sub(r"^\W*not quite\W*", "", text, flags=re.I).strip()
        # A reply that already opens with "No" and gives the right values says it itself.
        said = DISAGREES.match(text) and all(contains(text, n) for n in numbers_of(bare))
        if not said:
            out.corrections.append("put the correction of the user's premise first")
            raw = dict(raw, answer=(lead + "\n\n" + text).strip())
            out.lead = lead
        else:
            out.lead = (sentences(text) or [""])[0]
    elif text and DISAGREES.match(text) and _corrects(text, "", raw, facts, message):
        # The reply opens with "No" on a premise of the message, and its own verdict is sound
        # (the user's words and figures; the right values from a source, which the reply
        # gives): that opening is its answer, kept from the claim checker as a lead is (5 Nov:
        # "No, the design does not meet an 80 % CO2 reduction target" was removed, the 59.7 %
        # after it kept). Nothing is added: the model's own premises lead only as above.
        out.lead = (sentences(text) or [""])[0]
    if lead and not code_lead and fallback:
        fallback = lead + "\n\n" + fallback
    if raw.get("kind") == "clarify" and _corrects(
        str(raw.get("answer", "")), code_lead, raw, facts, message
    ):
        # A premise shown false is corrected in this turn, never only asked about: the
        # correction leads and the model's question follows it, as an answer (4 Nov: "the
        # aquifer sits at 3,500 m and 120 °C, so we can skip the heat pump?" got "would you like
        # to proceed with the official inputs?" as the turn's question; 5 Nov: "with an 80 %
        # CO2 cut, do we meet the 2030 goals?" said "59.7 %, not 80 %", as a question).
        raw = dict(raw, kind="answer")
        out.corrections.append("answered with the correction; the model's question follows it")
    others = theirs_sentences(str(raw.get("answer", "")), theirs)
    if others:
        kept = [x for x in sentences(str(raw.get("answer", ""))) if x not in others]
        out.corrections.append("removed another design's figure said of this one")
        raw = dict(raw, answer=" ".join(kept))
    still = _swaps(raw, costs) + _n1_claims(raw, plans)
    if still and not drafted and not _n1_claims(raw, plans):
        wrong = {m.group(1) for x in still for m in EUR_MWH.finditer(x)}
        kept = [
            x
            for x in sentences(str(raw.get("answer", "")))
            if not any(m.group(1) in wrong for m in EUR_MWH.finditer(x))
        ]
        if kept and len(" ".join(kept)) > 40:
            out.corrections.append("labels still wrong after the retry: those sentences removed")
            raw = dict(raw, answer=" ".join(kept))
            still = []
    if still and fallback and str(raw.get("answer", "")).strip():
        # A cost still called another one, or a design still called reliable when it is not,
        # after the retry: the code's own text goes out instead (1 Nov: 30.6 M€ of capital
        # called the yearly cost, and 42.1 €/MWh of cold called the cost of heat).
        out.corrections.append("labels still wrong after the retry: the checked draft shown")
        raw = dict(raw, answer=fallback)
    if raw.get("kind") == "nonsense":  # the older name of "unclear"
        raw = dict(raw, kind="unclear")
    if str(raw.get("kind", "answer")) not in kinds:
        raw = dict(raw, kind="answer")
    if _strangers(raw, only):  # still names a design that is not compared: the code's draft
        out.corrections.append("named designs outside the comparison: the checked draft shown")
        raw = dict(raw, answer=fallback)
    return _finish(out, raw, blocks, facts, fallback, must, message)


EUR_MWH = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:€|EUR)\s*/\s*MWh", re.I)


def numbers_of(text: str) -> List[str]:
    """Return each number in ``text`` as written, for ``contains``."""
    return re.findall(r"\d+(?:[.,]\d+)*", text)


DISAGREES = re.compile(r"^\W*(no\b|not quite|not exactly|not really|that is not|that's not)", re.I)


def states_quantity(text: str) -> bool:
    """Return True when a text states a figure: digits, or a number in words ("three")."""
    from gemini_agent.parameters import COUNTS, WORDS

    if numbers_in(text):
        return True
    words = set(re.findall(r"[^\W\d_]+", text.lower())) - {"a", "an"}
    return bool(words & (set(WORDS) | set(COUNTS)))


def _corrects(text: str, code_lead: str, raw: dict, facts: reporter.Facts, message: str) -> bool:
    """Return True when a reply corrects a premise of the message: it gives the right figures.

    The correction is code's (``code_lead``: a fact contradicts a number the message states),
    or the model's own verdict on the message's premises when code finds it sound
    (``premise_lead``: the user's own words and figures, the right values from a source). The
    reply must give every figure of that correction; when the model's right values are in
    words no lead would show, their figures that a source gives and the user did not say.
    """
    right = code_lead or premise_lead(raw, facts, message)
    figures = numbers_of(right.replace("**Not quite.** ", ""))
    if not right:
        # The model's right values in words a lead would not show ("... the 2030 target is not
        # in the context"): its figures that a source gives and the user did not say.
        said = set(numbers_in(message))
        figures = [
            n
            for p in _users_premises(raw, message)
            for n in re.findall(r"(?<![A-Za-z\d.,])\d+(?:[.,]\d+)*", str(p.get("right", "")))
            if not unsourced(n, facts) and not set(numbers_in(n)) & said
        ]
    return bool(text.strip() and figures) and all(contains(text, n) for n in figures)


def _users_premises(raw: dict, message: str = "") -> List[dict]:
    """Return the premises the model found wrong that are this message's own words and figures.

    With ``message``, the numbers the model quotes as said must be in it (4 Nov: "what did I
    ask first?" got a correction of the first turn's 200 GWh), and most of the words.
    """
    out = []
    said_here = {round(x, 2) for x in numbers_in(message)} if message else None
    words_here = set(re.findall(r"[a-z]{3,}", message.lower())) if message else set()
    for p in raw.get("premises") or []:
        if not isinstance(p, dict) or p.get("agrees") is not False:
            continue
        if not states_quantity(str(p.get("said", ""))):
            # A premise with no figure ("you drilled deeper than the aquifer", "you didn't pick
            # the cheapest") is no value a source can settle: the model's verdict on it is not
            # led with "Not quite" (4 Nov: both got one, wrongly). The reply may still disagree.
            continue
        quoted = {round(x, 2) for x in numbers_in(str(p.get("said", "")))}
        if said_here is not None and quoted - said_here:
            continue
        words = set(re.findall(r"[a-z]{3,}", str(p.get("said", "")).lower()))
        if message and (not words or len(words & words_here) < 0.7 * len(words)):
            # Not the user's own words: a plain question ("what does heat cost?") is no
            # premise, whatever the model listed (4 Nov: "Not quite. The cost of heat is ...").
            continue
        out.append(p)
    return out


def premise_lead(raw: dict, facts: reporter.Facts, message: str = "") -> str:
    """Return "Not quite." and the right values, for the user's premises the model found wrong.

    Only a correction whose every number a source gives is kept; one that agrees is not said.
    With ``message``, only premises of this message: the numbers the model quotes as said must
    be in it (4 Nov: "what did I ask first?" got a correction of the first turn's 200 GWh).
    """
    rights = []
    for p in _users_premises(raw, message):
        right = " ".join(str(p.get("right", "")).split()).strip()
        # Plain sentences only: no "The text states ...", no working, no "No." on its own, and
        # no last words cut off at the length limit.
        kept = []
        for x in sentences(right):
            x = re.sub(r"^\W*(no|yes)\b[.,:;]?\s*", "", x, flags=re.I).strip()
            x = CONTEXT_LEAD.sub("", x).strip()
            if not x or INTERNALS.search(x) or WORKING.search(x):
                continue
            if re.search(r"\bthe user\b|\"", x, re.I):  # "The user's claim is wrong."
                continue
            if not x.endswith((".", "!", "?", ")")):
                break  # cut off
            kept.append(x)
        right = " ".join(kept[:2])
        if not right or not numbers_in(right) or unsourced(right, facts):
            continue
        rights.append(right[0].upper() + right[1:])
    return ("**Not quite.** " + " ".join(dict.fromkeys(rights))) if rights else ""


def _swaps(raw: dict, costs: Sequence[Tuple[float, Optional[float], float]]) -> List[str]:
    """Return a correction when a cost of heat and cold is given as the cost of heat, or back.

    Also when the costs of heat and of cold per MWh are added up (they never add).

    ``costs``: (heat, cold, heat and cold) €/MWh of the designs the reply may name. A sentence
    that speaks of heat alone with a figure that is only ever a heat-and-cold cost (or the other
    way round) is a swap.
    """
    if not costs:
        return []
    text = str(raw.get("answer", ""))
    both = {round(c[2], 1) for c in costs}
    heat = {round(c[0], 1) for c in costs}
    cold = {round(c[1], 1) for c in costs if c[1] is not None}
    real = both | heat | cold
    # Costs per MWh of heat and of cold never add up: their sum is no cost of anything.
    sums = {round(c[0] + c[1], 1): c[2] for c in costs if c[1] is not None}
    found = []
    for sent in sentences(text):
        for m in EUR_MWH.finditer(sent):
            # What the figure is called: the words just before it, after any earlier figure.
            before = sent[: m.start()]
            last = list(EUR_MWH.finditer(before))
            low = before[last[-1].end() :].lower() if last else before.lower()
            # Only the clause the figure sits in: "... together (heat 75.7" names heat alone.
            low = re.split(r"[(;,:]", low[-60:])[-1]
            together = "heat and cold" in low or "together" in low or "combined" in low
            heat_only = "heat" in low and "cold" not in low and not together
            x = round(float(m.group(1).replace(",", ".")), 1)
            if x in sums and x not in real:
                found.append(
                    f"{reporter.num(x)} €/MWh adds the cost of heat to the cost of cold, but costs "
                    f"per MWh do not add: heat and cold together cost {reporter.num(sums[x])} €/MWh"
                )
            elif heat_only and x in cold and x not in heat and x not in both:
                found.append(f"{reporter.num(x)} €/MWh is the cost of cold, not of heat")
            elif together and x in cold and x not in both and x not in heat:
                found.append(f"{reporter.num(x)} €/MWh is the cost of cold alone")
            elif heat_only and x in both and x not in heat:
                found.append(f"{reporter.num(x)} €/MWh is a cost of heat and cold together")
            elif together and x in heat and x not in both:
                found.append(f"{reporter.num(x)} €/MWh is the cost of heat alone")
    if not found:
        return []
    return ["Fix the cost labels: " + "; ".join(sorted(set(found))) + "."]


# A sentence that credits a design with surviving any one unit out.
N1_CLAIM = re.compile(
    r"\bN-1\b|any (single |one )?unit (can|could|may) (be out|fail)|"
    r"(handle|survive|cope with|withstand)s? (a |any )?(single )?(unit|equipment) (failure|outage)",
    re.I,
)
NEGATED = re.compile(
    r"\b(not|isn't|aren't|lacks?|never|cannot|falls? short|unlike)\b|n't\b|\bno (N-1|unit)", re.I
)


def _n1_claims(raw: dict, plans: Sequence[Tuple[str, str, bool, str]]) -> List[str]:
    """Return a correction when a design that is not a reliable plan is called one.

    ``plans``: (code, name, reliable, cases short in words) of the designs the reply may name.
    On 1 Nov "A1 can handle unit failures (N-1)" was said of a design 5 of 6 cases short.
    """
    if not plans:
        return []
    found = []
    for sent in sentences(str(raw.get("answer", ""))):
        if not N1_CLAIM.search(sent) or NEGATED.search(sent):
            continue
        named = [
            p
            for p in plans
            if p[0] in sent or (p[1] and re.search(rf"\b{re.escape(p[1])}\b", sent))
        ]
        if named and not any(p[2] for p in named):
            p = named[0]
            found.append(f"{p[1] or p[0]} is not sized for one unit out ({p[3]})")
    if not found:
        return []
    return ["Fix the reliability claims: " + "; ".join(sorted(set(found))) + "."]


DESIGN_CODE = re.compile(
    r"\b[123]D-(?:HP|BO|DH)-(?:AB|EC|NC)(?:@\d{3,5}(?:\+\d{3,5})*)?"
    r"(?:-(?:2I\d*|ST\d*|BL|PL\d*|PU\d*|IL\d*|IU\d*|N1|EB|GS|FC|PV\d+(?:\.\d+)?|TS\d+|ATES))*\b"
)


# A design's handle in a reply ("A27", "W1"); "CO2" and the like are not handles.
DESIGN_HANDLE = re.compile(r"\b(?!CO2\b|CH4\b|N1\b|H2\b|O2\b|PV\d)([A-Z]{1,2}\d{1,3})\b(?!\.\d)")


# The prompt's parts named as a lead-in: "According to the text, ", "The data shows that ".
INTERNAL_LEAD = re.compile(
    r"^\W*(according to|based on|as (shown|stated|given) (in|by)|from) (the )?(provided )?"
    r"(text|context|data|draft|sources?|blocks?)[^,:]*[,:]\s*|"
    r"^\W*the (provided )?(text|data|context|draft|sources?) (explicitly |clearly |also )?"
    r"(states?|says|shows|lists|gives|mentions|indicates|notes|reports)( that)?\s+",
    re.I,
)


def _without_internals(sentence: str) -> str:
    """Return a sentence without its lead-in about the prompt, or "" when that is all it is."""
    out = INTERNAL_LEAD.sub("", sentence).strip()
    if not out or INTERNALS.search(out):
        return ""
    return out[0].upper() + out[1:]


def _strangers(raw: dict, only: Sequence[str]) -> List[str]:
    """Return a correction when the reply names designs other than ``only`` (none when empty).

    Codes ("1D-BO-EC@3500") and handles ("A27") both count (2 Nov: a question about the
    design's cost of heat brought in the cheapest and the greenest designs).
    """
    if not only:
        return []
    text = str(raw.get("answer", ""))
    named = set(DESIGN_CODE.findall(text)) | set(DESIGN_HANDLE.findall(text))
    extra = sorted(named - set(only))
    if not extra:
        return []
    return [
        f"Talk only about the design or designs the question is about; do not name "
        f"{', '.join(extra)} or any other design it did not ask about."
    ]


def theirs_sentences(text: str, theirs: Sequence[Tuple[str, Sequence[str]]]) -> List[str]:
    """Return the sentences that give another design's value without naming that design."""
    out = []
    for x in sentences(text):
        low = x.lower()
        for value, names in theirs:
            if contains(x, value) and not any(n.lower() in low for n in names if n):
                out.append(x)
                break
    return out


def _theirs_problems(raw: dict, theirs: Sequence[Tuple[str, Sequence[str]]]) -> List[str]:
    found = theirs_sentences(str(raw.get("answer", "")), theirs)
    if not found:
        return []
    said = "; ".join(
        f"{v} is {names[0]}'s"
        for v, names in theirs
        if names and any(contains(x, v) for x in found)
    )
    return [
        f"{said}, not the value of the design the question is about: give that design's own "
        "value from the draft, or name the other design when you set the two side by side."
    ]


def add_back(text: str, fallback: str, must: Sequence[str]) -> Tuple[str, List[str]]:
    """Add the draft's sentences for key values the text lost (two at most); return it and them.

    Returns the text unchanged and the values still missing when a value has no sentence of
    its own in the draft, or more than two sentences would be needed.
    """
    dropped = [m for m in must if not contains(text, m)]
    if not text or not dropped:
        return text, dropped
    back = [next((s for s in sentences(fallback) if contains(s, m)), "") for m in dropped]
    back = list(dict.fromkeys(back))
    if all(back) and len(back) <= 2:
        joint = "\n\n" if "\n" in text else " "
        return text.rstrip() + joint + " ".join(back), []
    return text, dropped


def _rounded_from(n: float, facts: reporter.Facts) -> str:
    """Return the context's values that a number rounds, as a note for the retry ("" if none).

    5 Nov: "a reduction of about 63 %" (the context: 63.1 %) was asked again, and the retry
    dropped it and called the design's 9,007 t of emissions its saving. Named, the context's
    own value can be written as it stands.
    """
    if n == int(n) and n < 10:
        return ""  # a small whole number is likelier a count ("six doublets") than a rounding
    step = 0.5 if n == int(n) else 0.05
    near = sorted(
        (x for x in facts.allowed if x != n and abs(x - n) < step), key=lambda x: abs(x - n)
    )
    if not near:
        return ""
    return " (the context has " + " or ".join(reporter.num(x, 2) for x in near[:2]) + ")"


def _problems(
    raw: dict, facts: reporter.Facts, must: Sequence[str], fallback: str = ""
) -> List[str]:
    text = str(raw.get("answer", "")).strip()
    if not text:
        return ["The answer was empty."]
    problems = []
    bad = unsourced(text, facts)
    if bad:
        listed = ", ".join(reporter.num(n, 2) + _rounded_from(n, facts) for n in bad)
        problems.append(
            f"These numbers are not in the context: {listed}. Leave them out or use the "
            "context's values."
        )
    for written, right, _ in wrong_sums(text):
        problems.append(
            f"Your calculation {written} does not add up (it gives {reporter.num(right, 2)}): "
            "correct it from the context's values or leave it out. The user has not seen this "
            "note; do not mention it."
        )
    # A dropped value is worth a retry only when the draft has no short sentence to add back
    # (``_finish`` adds up to two); a retry that only asks for values confused the 9b on 30 Oct
    # ("You want the JSON response with specific draft values kept"). Source names are added back.
    dropped = [m for m in must if numbers_in(m) and not contains(text, m)]
    back = [next((s for s in sentences(fallback) if contains(s, m)), "") for m in dropped]
    if dropped and all(back) and len(set(back)) <= 2:
        dropped = []
    if dropped and raw.get("kind", "answer") == "answer":
        problems.append("Keep these values from the draft: " + ", ".join(dropped) + ".")
    return problems


def _finish(
    out: Reply,
    raw: dict,
    blocks: Sequence[Block],
    facts: reporter.Facts,
    fallback: str,
    must: Sequence[str],
    message: str = "",
) -> Reply:
    text = str(raw.get("answer", "")).strip()
    kind = str(raw.get("kind", "answer"))
    kind = kind if kind in KINDS else "answer"
    scope = str(raw.get("scope", "project"))
    scope = scope if scope in SCOPES else "project"
    ids = {b.id for b in blocks}
    options = [str(o).strip() for o in raw.get("options") or [] if str(o).strip()]
    options = list(dict.fromkeys(options))[:4]
    if kind == "unclear":
        # The message could not be read: the agent says so and asks, in its own words for every
        # such message (``reporter.unreadable_text``), so nothing else here applies.
        out.text, out.fallback, out.kind, out.scope = text, False, "unclear", scope
        out.understood = str(raw.get("understood", "")).strip()
        return out
    if kind == "clarify" and (len(options) < 2 or "?" not in text):
        kind, options = "answer", []
        out.corrections.append("a clarification needs a question and two readings: an answer")
    elif kind != "clarify":
        options = []
    if kind == "out_of_scope":
        scope = "out"
    # A field name of the JSON left in the reply ("**used**:" on its own line, 1 Nov).
    text = re.sub(
        r"^\s*\**(used|follow_ups|understood|kind|scope|premises)\**\s*:?\s*$",
        "",
        text,
        flags=re.M | re.I,
    ).strip()
    text, copied = drop_copies(text, blocks)
    if copied:
        out.corrections.append("removed a copy of the file's rows; the chat shows the table")
    if CONTEXT_LEAD.search(text):
        text = CONTEXT_LEAD.sub(lambda m: "", text)
        text = re.sub(
            r"(^|[.!?]\s+|\n\s*(?:[-*]\s+)?)([a-z])",
            lambda m: m.group(1) + m.group(2).upper(),
            text,
        )
        out.corrections.append("cut a lead-in about the prompt's text")
    # The model's own working is not an answer ("Wait, let me re-read carefully …", 1 Nov).
    # "I have updated the return to 55 °C, I am now sizing a plan" when nothing ran (1 Nov):
    # an action is claimed only when the code's draft reports one.
    if any(b.kind == "draft" for b in blocks) and not REFUSAL.search(fallback or ""):
        # A tool ran for this turn: "I cannot calculate it", "it is not modelled" contradicts
        # the card under the reply (1 Nov: a what-if ran with the yearly service, and the reply
        # said the design "does not include" it and could not be calculated).
        refused = [x for x in sentences(text) if REFUSAL.search(x)]
        if refused:
            # All of it a refusal: nothing is left, and the checked template shows instead.
            for x in refused:
                text = text.replace(x, "")
            text = re.sub(r"[ \t]{2,}", " ", text).strip()
            text = re.sub(r"^(however|but|instead|that said|still),?\s+", "", text, flags=re.I)
            text = text[:1].upper() + text[1:]
            out.corrections.append("removed a refusal that the tool's result contradicts")
    claimed = [x for x in sentences(text) if ACTION_CLAIM.search(x)]
    ran = ACTION_CLAIM.search(fallback or "") or TOOL_RAN.search(fallback or "")
    if claimed and not ran and len(claimed) < len(sentences(text)):
        for x in claimed:
            text = text.replace(x, "")
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        out.corrections.append("removed a claim of an action that did not run")
    working = [x for x in sentences(text) if WORKING.search(x)]
    if working and len(working) < len(sentences(text)):
        for x in working:
            text = text.replace(x, "")
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        out.corrections.append("removed the model's working, which is not an answer")
    if len(str(raw.get("answer", ""))) >= ANSWER_CHARS - 5:
        # Cut at the length limit mid-sentence: end at the last full sentence.
        end = max(text.rfind(". "), text.rfind(".\n"), text.rfind("!"), text.rfind("?"))
        if end > len(text) // 2 and not text.rstrip().endswith((".", "!", "?", "|", ")")):
            text = text[: end + 1].rstrip()
            out.corrections.append("cut a reply that stopped mid-sentence at its last full one")
    inside = [x for x in sentences(text) if INTERNALS.search(x)]
    if inside and len(inside) < len(sentences(text)):
        # "It appears in the context block": the user never sees the prompt's parts. A sentence
        # that carries a figure loses only the lead-in ("the text shows the boiler gives
        # 28.1%" kept "the boiler gives 28.1%"; 2 Nov, the whole answer had gone).
        for x in inside:
            kept = _without_internals(x)
            text = text.replace(x, kept if kept and numbers_in(kept) else "")
        text = re.sub(r"[ \t]{2,}", " ", text).strip()
        out.corrections.append("removed talk of the prompt's blocks, which the user can't see")
    bad = unsourced(text, facts)
    if bad:
        listed = ", ".join(reporter.num(n, 2) for n in bad)
        out.corrections.append(f"removed sentences with numbers no source gives ({listed})")
        text = keep_sourced(text, facts)
    wrong = wrong_sums(text)
    if wrong:
        # Still wrong after the retry (2 Nov: "86.1 °C - 40 K = 52.1 °C"): the lines that show
        # it go; the rest of the reply stands.
        lines = text.split("\n")
        kept = [ln for ln in lines if not wrong_sums(ln)]
        if any(ln.strip() for ln in kept):
            text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
            listed = "; ".join(w for w, _, _ in wrong)
            out.corrections.append(f"removed a calculation that does not add up ({listed})")
    dropped = [m for m in must if not contains(text, m)] if kind == "answer" else []
    if text and dropped:
        text, still = add_back(text, fallback, must)
        if not still:
            out.corrections.append(
                "added back from the checked answer: " + ", ".join(m.lstrip("~") for m in dropped)
            )
        dropped = still
    if len(strip_cites(text)) < 12 or dropped:
        out.note = "the model's answer failed the checks; showed the checked template"
        out.text, out.fallback = fallback, True
        out.kind, out.scope = "answer", "project"
        out.understood = str(raw.get("understood", ""))
        return out
    out.text, out.fallback = text, False
    out.kind, out.scope = kind, scope
    out.understood = str(raw.get("understood", "")).strip()
    out.used = [u for u in dict.fromkeys(str(u) for u in raw.get("used") or []) if u in ids]
    out.follow_ups = [str(f).strip() for f in raw.get("follow_ups") or [] if str(f).strip()][:3]
    out.options = options
    out.steps = [str(s) for s in raw.get("steps") or []][:3]
    if out.kind == "clarify":
        known = "\n".join(b.text for b in blocks if b.kind == "history")
        offered = answer_then_offer(out.text, known, message)
        if offered is not None:
            # A complete answer that ends with an offer ("No, it has one doublet. Would you like
            # a design with three?"): the answer, with the offer's choices as follow-ups.
            out.text, out.kind = offered, "answer"
            out.follow_ups = list(dict.fromkeys(out.options + out.follow_ups))[:3]
            out.options = []
            out.corrections.append("an answer that ended with an offer: the offer is a follow-up")
    return out


def answer_then_offer(text: str, known: str = "", message: str = "") -> Optional[str]:
    """Return a reply's answer without the question it ends with, or None for a question back.

    It is an answer when its first sentence states something and what comes before the first
    question gives a figure or a design's id (5 Nov: "No, the recommended design uses only one
    doublet. Would you like ...?" was a question back), or tells what the conversation holds:
    two words of the chat's history (``known``) the message does not have ("We were discussing
    outside air instead of the chillers. Shall we go on with that?" after "what were we
    discussing before the weather?"). "I cannot see what you mean. Could you say which
    design?" stays a question.
    """
    body = strip_cites(text or "").strip()
    first = sentences(body)[:1]
    if not first or first[0].rstrip("*_ ").endswith("?"):
        return None
    q = body.find("?")
    if q < 0:
        return None
    start = max(body.rfind(". ", 0, q), body.rfind(".\n", 0, q), body.rfind("\n", 0, q))
    if start < 0:
        return None
    head = body[: start + 1].rstrip()
    if len(head) < 40:
        return None
    if re.search(r"\d", head):
        return head
    from gemini_agent.chat_state import _words

    told = (_words(head) & _words(known)) - _words(message)
    return head if len(told) >= 2 else None
