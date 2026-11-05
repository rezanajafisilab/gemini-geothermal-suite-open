"""Intake: one structured model call reads the request, then code checks what it read.

The model (call 1 in ADR-0002) judges whether the message is about our job, what is wanted
and which numbers the user gave. Code then refuses to trust anything the user did not
actually write: every number must appear in the message, network temperatures are read by
pattern next to the words for heating or cooling, and exclusions come from negations in the
text. In our first CPU test a 1.7B model copied the heating temperatures into cooling and
reported nothing missing; these checks are why such a slip cannot reach a design.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from gemini_agent import lookup
from gemini_agent.contract import DesignBrief, NetworkTemps, ProjectData, Question
from gemini_agent.llm import LLMCall, LLMError, ModelUnavailable

INTENTS = ["design", "compare", "what_if", "explain", "question", "about", "greeting", "other"]

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_VERSION = os.environ.get("DIOSCURI_INTAKE_PROMPT", "intake_v3")


def load_prompt(version: str = PROMPT_VERSION) -> Tuple[str, List[Tuple[str, dict]]]:
    """Return a versioned intake prompt: its system text and its worked examples.

    Prompts live in ``prompts/`` as ``<version>.txt`` and ``<version>_examples.json`` so a
    change is a new version that the eval runs can compare, not an edit hidden in code.

    Parameters
    ----------
    version : str
        File stem, for example ``"intake_v1"``.

    Returns
    -------
    tuple of (str, list of (str, dict))
        The system prompt and the (message, reply) example pairs.
    """
    system = (PROMPT_DIR / f"{version}.txt").read_text(encoding="utf-8").strip()
    examples = json.loads((PROMPT_DIR / f"{version}_examples.json").read_text(encoding="utf-8"))
    return system, [(ex["message"], ex["reply"]) for ex in examples]


SYSTEM_PROMPT, EXAMPLES = load_prompt()

SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean"},
        "intent": {"type": "string", "enum": INTENTS},
        "asks_for": {"type": "array", "items": {"type": "string", "enum": lookup.FACT_KEYS}},
        "bypass": {"type": "boolean"},
        "think": {"type": "boolean"},
        "annual_heat_gwh": {"type": ["number", "null"]},
        "annual_cool_gwh": {"type": ["number", "null"]},
        "reservoir_depth_m": {"type": ["number", "null"]},
        "reservoir_temp_c": {"type": ["number", "null"]},
        "depths_m": {"type": "array", "items": {"type": "number"}},
        "reservoir_change_c": {"type": ["number", "null"]},
    },
    "required": [
        "relevant",
        "intent",
        "asks_for",
        "bypass",
        "think",
        "annual_heat_gwh",
        "annual_cool_gwh",
        "reservoir_depth_m",
        "reservoir_temp_c",
        "depths_m",
        "reservoir_change_c",
    ],
}

_I = re.IGNORECASE
STRONG_WORDS = re.compile(
    r"geotherm|doublet|district (heat|cool)|heat[- ]?pump|reservoir|aquifer|chiller|"
    r"warmtenet|koudenet|aardwarmte|warmtepomp|lcoh|lcoc|lcoe|injection|wellhead|\besp\b|"
    r"\bn-1\b|best overall|gas-free|sde\+\+|brine|dublette|\bsole\b|erdwärme|wärmepumpe|"
    r"(heating|cooling|warmte|koude)\b[\w\s-]{0,30}\b(system|network|plant|design|demand|supply|"
    r"net|systeem|installatie)",
    _I,
)
WEAK_WORDS = re.compile(
    r"\b(heat\w*|cool\w*|warmte\w*|koud\w*|koel\w*|energy|energie|"
    r"design|ontwerp\w*|system|systeem|demand|vraag\w*|wijk|district)\b",
    _I,
)
HEAT_WORDS = re.compile(r"heat\w*|\bdh\b|warmte\w*|verwarm\w*", _I)
COOL_WORDS = re.compile(r"cool\w*|cold|\bdc\b|koud\w*|koel\w*", _I)
BYPASS_WORDS = re.compile(
    r"ignore (the |all |any )?(simulat\w*|verif\w*|check\w*|physics|model\w*)|"
    r"skip (the |all )?(simulat\w*|verif\w*|check\w*)|just (tell|say|write|report)|"
    r"without (running|checking|simulating)|negeer",
    _I,
)
COP_CLAIM = re.compile(r"\bCOP\b\D{0,12}(\d+(?:[.,]\d+)?)", _I)
DUTCH_WORDS = re.compile(
    r"\b(de|het|een|voor|met|deze|wijk|ontwerp|warmte|koude|graden|" r"systeem|gegeven)\b", _I
)
PAIR = re.compile(
    r"(?<![\d/.\-–])(\d{1,3}(?:[.,]\d)?)\s*(?:/|-|–|to|tot)\s*(\d{1,3}(?:[.,]\d)?)(?!\d)\s*"
    r"(?:°\s*C\b|°C|C\b|graden)?"
    # "from 10 to 24 January", "10/01": dates, not a network's temperatures
    r"(?!\s*(?:of\s+)?(?:jan|feb|f[ée]v|mar|maa|mrt|m[äa]r|apr|avr|may|mei|mai|jun|jul|aug|"
    r"ao[ûu]|sep|oct|okt|nov|dec|dez|d[ée]c)[a-zäëéèû]*\b)(?![/.\-–]\d)",
    _I,
)
# "2,500 m" (a thousands separator), "2.5 km", "2,5 km" (a Dutch decimal), "3000 m".
DEPTH = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:[.,]\d+)?)\s*(km|m)\b", _I)
DOUBLETS = re.compile(
    r"\b(a single|single|one|1|two|2|three|3)\s+(?:[\w.,]+\s+){0,2}?doublets?\b", _I
)
COUNTS = {"a single": 1, "single": 1, "one": 1, "1": 1, "two": 2, "2": 2, "three": 3, "3": 3}
GWH = re.compile(r"(\d+(?:[.,]\d+)?)\s*GWh", _I)
# "no boilers", "without heat pumps", "remove the boiler", "get rid of the gas boiler".
NEGATION = re.compile(
    r"\b(no|without|zonder|geen|excluding|exclude|remove|drop|get rid of|take out|leave out|"
    r"scrap|ditch|verwijder|haal .{0,12} weg)\b([^.;:\n]{0,80})",
    _I,
)
EQUIPMENT = {
    "heat_pump": re.compile(r"heat[- ]?pumps?|warmtepomp", _I),
    "boiler": re.compile(r"boilers?|ketels?|\bgas\b", _I),
    "chiller": re.compile(r"chillers?|koelmachines?", _I),
}
FOSSIL_FREE = re.compile(r"fossil[- ]free|fossielvrij|no fossil", _I)
COVERAGE = re.compile(r"(\d{2,3})\s*%", _I)
CHANGE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:°\s*)?(?:C|K|degrees?|graden)?\s*"
    r"(colder|cooler|lower|warmer|hotter|higher|kouder)",
    _I,
)
GREETING = re.compile(
    r"^\W*(hi|hello|hey|hoi|hallo|good (morning|afternoon|evening)|goedemorgen|goedemiddag|"
    r"thanks|thank you|bedankt|dank je( wel)?|cheers)\b[\s\w]{0,15}\W*$",
    _I,
)
THANKS = re.compile(r"thank|bedankt|dank je|cheers", _I)
ABOUT = re.compile(
    r"\b(who are you|what are you|who made you|what can you do|what do you do|how do you work|"
    r"what is dioscuri|introduce yourself|wie ben je|wat ben je|wat kun je|wat kan je)\b|"
    r"^\W*help\W*$",
    _I,
)
# "About" means about us: "you" outside a polite "could you ...", or the name.
SELF_REF = re.compile(r"\b(you|your|yourself|dioscuri|jij|jouw|uw)\b", _I)
POLITE = re.compile(
    r"\b(could|can|would|will|kun|kunt|wil) (you|je|u)( please)? (explain|tell|describe|give|"
    r"show|list|summari[sz]e|walk|uitleggen|vertellen)\b",
    _I,
)
EXPLAIN_START = re.compile(
    r"^\W*(explain|how (does|do|is|are|was|were)|why|what does|leg uit|hoe (werkt|wordt)|waarom)\b",
    _I,
)
COMPARE_WORDS = re.compile(r"\bcompar\w*|\bversus\b|\bvs\.?\b|\bagainst\b|vergelijk", _I)
WHAT_IF_WORDS = re.compile(r"what (happens )?if|what-if|wat als|stel dat", _I)
# "Which design gives the lowest CO2?", "the cheapest system": a search, ranked by that.
BEST_DESIGN = re.compile(
    r"\b(which|what)\b.{0,30}\b(design|system|plant|option)s?\b.{0,40}"
    r"\b(lowest|least|cheapest|best|greenest|lowest-cost)\b|"
    r"\b(lowest|least|cheapest|greenest)\b.{0,30}\b(design|system|plant)\b",
    _I,
)


WANTS_SYSTEM = re.compile(
    r"\b(need|want|plan|build|propose)\b.{0,40}\b(heat|cool|system|network)", _I
)


def asks_design(message: str) -> bool:
    """Return True when a message asks for a design (design, size, compare, "we need ...")."""
    return bool(lookup.DESIGN_VERBS.search(message) or WANTS_SYSTEM.search(message))


def numbers_in(text: str) -> List[float]:
    """Return every number written in a text, reading ``2,400`` as 2400 and ``6,5`` as 6.5.

    Parameters
    ----------
    text : str
        The message.

    Returns
    -------
    list of float
        All numbers found, in order.
    """
    out = []
    for token in re.findall(r"\d+(?:[.,]\d+)*", text):
        if re.fullmatch(r"\d{1,3}(,\d{3})+", token):
            out.append(float(token.replace(",", "")))
        else:
            try:
                out.append(float(token.replace(",", ".", 1).replace(",", "")))
            except ValueError:
                continue
    return out


CONTEXT = {
    "annual": (re.compile(r"^\s*(GWh|MWh|TWh)", _I), None),
    "depth": (
        re.compile(r"^\s*(km|m|metres|meters)\b", _I),
        re.compile(r"doublet|well|deep|depth|diep|put|bore|reservoir", _I),
    ),
    "reservoir_depth": (
        re.compile(r"^\s*(km|m|metres|meters)\b", _I),
        re.compile(r"reservoir|aquifer|formation", _I),
    ),
    "reservoir_temp": (
        re.compile(r"^\s*(°\s*C|C\b|degrees|graden)", _I),
        re.compile(r"reservoir|aquifer|formation|brine|bottom|well|put|bron", _I),
    ),
}
PLAUSIBLE = {"reservoir_depth_m": (300.0, 7000.0), "reservoir_temp_c": (30.0, 250.0)}


def _pair_spans(text: str) -> List[tuple]:
    out = []
    for m in PAIR.finditer(text):
        supply = float(m.group(1).replace(",", "."))
        ret = float(m.group(2).replace(",", "."))
        if _kind_from_range(supply, ret):
            out.append(m.span())
    return out


def _in_context(text: str, value: Optional[float], kind: str, spans: Sequence[tuple]) -> bool:
    """Return True if ``value`` is written in ``text`` in the role ``kind``.

    The number must appear with its unit right after it (``GWh``, ``km``, ``°C``), near a
    word for that quantity, and outside any network temperature pair: a ``40`` that is the
    return temperature of ``70/40 °C`` is not 40 GWh of demand.
    """
    if value is None:
        return False
    unit, words = CONTEXT[kind]
    targets = [abs(value)] + ([abs(value) / 1000] if kind in ("depth", "reservoir_depth") else [])
    for m in re.finditer(r"\d+(?:[.,]\d+)*", text):
        if any(start <= m.start() < end for start, end in spans):
            continue
        n = numbers_in(m.group(0))
        if not n or not any(abs(n[0] - t) < 1e-6 * max(1.0, t) for t in targets):
            continue
        if not unit.search(text[m.end() : m.end() + 12]):
            continue
        if words and not words.search(text[max(0, m.start() - 40) : m.end() + 40]):
            continue
        return True
    return False


def _kind_from_range(supply: float, ret: float) -> Optional[str]:
    if 35 <= supply <= 130 and 15 <= ret < supply:
        return "heating"
    if 2 <= supply <= 20 and supply < ret <= 30:
        return "cooling"
    return None


def network_temperatures(text: str) -> Dict[str, NetworkTemps]:
    """Read supply/return pairs such as ``70/40 °C`` and tie each to heating or cooling.

    Heating pairs (supply 35-130 °C, return below supply) and cooling pairs (supply 2-20 °C,
    return above supply, at most 30 °C) cannot overlap, so the numbers decide which network
    a pair belongs to; a value can never move from heating to cooling. A pair that fits
    neither range is ignored.

    Parameters
    ----------
    text : str
        The message.

    Returns
    -------
    dict
        ``{"heating": NetworkTemps, "cooling": NetworkTemps}``, either key may be absent.
    """
    found: Dict[str, NetworkTemps] = {}
    for m in PAIR.finditer(text):
        supply = float(m.group(1).replace(",", "."))
        ret = float(m.group(2).replace(",", "."))
        kind = _kind_from_range(supply, ret)
        if kind is not None:
            found.setdefault(kind, NetworkTemps(supply_c=supply, return_c=ret))
    return found


def excluded_equipment(text: str) -> List[str]:
    """Return the equipment the message rules out (``no heat pumps``, ``fossil-free``...).

    Parameters
    ----------
    text : str
        The message.

    Returns
    -------
    list of str
        Any of ``heat_pump``, ``boiler``, ``chiller``.
    """
    out = set()
    for m in NEGATION.finditer(text):
        for name, pattern in EQUIPMENT.items():
            if pattern.search(m.group(2)):
                out.add(name)
    if FOSSIL_FREE.search(text):
        out.add("boiler")
    return sorted(out)


def doublet_counts(text: str) -> List[int]:
    """Return the distinct numbers of doublets a message names, in order ("2 doublets or 1")."""
    out: List[int] = []
    for m in DOUBLETS.finditer(text):
        n = COUNTS[m.group(1).lower()]
        if n not in out:
            out.append(n)
    return out


def _depth_range() -> Tuple[float, float]:
    """Return the depths a well may be drilled to: the planner's (``aquifer_depths_m``)."""
    from gemini_agent.parameters import CATALOGUE

    p = CATALOGUE["aquifer_depths_m"]
    return float(p.low), float(p.high)


def _depths(text: str) -> List[float]:
    out = []
    for m in DEPTH.finditer(text):
        context = text[max(0, m.start() - 30) : m.end() + 30].lower()
        if not re.search(r"doublet|well|deep|depth|diep|put|bore|aquifer|reservoir", context):
            continue
        after = text[m.end() : m.end() + 14].lower()
        if re.match(r"\s*(thick|dik|long|lang|wide|breed|apart|spacing)", after):
            continue  # "100 m thickness", "1,500 m apart": not a well depth
        raw = m.group(1)
        # "2,500" is two thousand five hundred; "2,5" is two and a half.
        number = raw.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", raw) else raw
        value = float(number.replace(",", "."))
        value = value * 1000 if m.group(2).lower() == "km" else value
        if value >= 300:  # shallower is no geothermal well (a thickness, a pipe, a distance)
            out.append(value)
    return out


def _annual(text: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m in GWH.finditer(text):
        value = float(m.group(1).replace(",", "."))
        before = text[max(0, m.start() - 50) : m.start()]
        last = {
            "annual_heat_gwh": max([x.end() for x in HEAT_WORDS.finditer(before)] or [-1]),
            "annual_cool_gwh": max([x.end() for x in COOL_WORDS.finditer(before)] or [-1]),
        }
        key = max(last, key=last.get)
        if last[key] < 0:
            after = text[m.end() : m.end() + 25]
            key = (
                "annual_cool_gwh"
                if COOL_WORDS.search(after)
                else "annual_heat_gwh" if HEAT_WORDS.search(after) else ""
            )
        if key:
            out.setdefault(key, value)
    return out


def _coverage(text: str) -> Optional[float]:
    for m in COVERAGE.finditer(text):
        context = text[max(0, m.start() - 40) : m.end() + 40].lower()
        after = text[m.end() : m.end() + 25].lower()
        if re.search(r"\b(more|less|higher|lower|extra|increase|growth|grow|meer|minder)\b", after):
            continue  # "20 % more heat demand" scales the demand; it is not a coverage
        if re.search(r"cover|meet|dek\b|gedekt|abgedeckt", context):
            return min(1.0, float(m.group(1)) / 100)
    return None


@dataclass
class IntakeResult:
    """What intake decided about one message.

    ``screened`` means a greeting or "who are you" was recognised without a model call (the
    answerer still writes the reply);
    ``unavailable`` holds the reason when the model could not be reached at all; ``asks_for``
    lists the values a question asks about (``lookup.FACT_KEYS``);
    ``think`` is the reader's judgement that the reply must weigh options (the agent turns
    reasoning on for it, within code rules).
    """

    relevant: bool
    bypass: bool
    intent: str
    language: str
    updates: Dict[str, object] = field(default_factory=dict)
    dropped: List[str] = field(default_factory=list)
    cop_claim: Optional[float] = None
    call: Optional[LLMCall] = None
    llm_ok: bool = True
    screened: bool = False
    unavailable: str = ""
    asks_for: List[str] = field(default_factory=list)
    think: bool = False
    # ``bypass`` is a suspicion (the reader's flag, or words such as "ignore the simulator");
    # ``confirm_bypass`` asks a larger model before anything is refused. ``bypass_words``: the
    # message itself says it, so the request is declined even when no model can confirm.
    bypass_words: bool = False


SCREEN_PROMPT = "screen_v1"
SCREEN_SCHEMA = {
    "type": "object",
    "properties": {
        "skip_checks": {"type": "boolean"},
        "asked": {"type": "string", "maxLength": 200},
    },
    "required": ["skip_checks", "asked"],
}


@dataclass
class Screen:
    """A larger model's verdict on a suspected request to skip the checks."""

    skip_checks: bool
    asked: str = ""
    call: Optional[LLMCall] = None
    decided_by: str = "model"


def confirm_bypass(message: str, llm, words: bool) -> Screen:
    """Ask whether a message really asks to skip the simulator or its checks.

    The small reader flags such requests loosely ("give me the full report" is not one), so a
    refusal needs this second, focused judgement. When no model answers, only a message that
    says so in plain words (``words``) is declined.

    Parameters
    ----------
    message : str
        The user's message.
    llm : OllamaLLM or ScriptedLLM
        The model that judges (the reasoning model).
    words : bool
        The message itself asks to ignore or skip the simulator or the checks.

    Returns
    -------
    Screen
        The verdict and, in the model's words, what the message asks for.
    """
    from gemini_agent.answer import load

    msgs = [
        {"role": "system", "content": load(SCREEN_PROMPT)},
        {"role": "user", "content": message},
    ]
    try:
        raw, call = llm.structured("screen", msgs, SCREEN_SCHEMA, 80)
    except LLMError as err:
        return Screen(words, "", err.call, decided_by="rules")
    if not isinstance(raw.get("skip_checks"), bool):
        return Screen(words, "", call, decided_by="rules")
    return Screen(raw["skip_checks"], " ".join(str(raw.get("asked") or "").split())[:200], call)


ROUTE_PROMPT = "route_v1"
ROUTE_SCHEMA = {
    "type": "object",
    "properties": {"run_design": {"type": "boolean"}},
    "required": ["run_design"],
}


def wants_design(
    message: str, llm, designs: str = "none", thread: str = ""
) -> Tuple[bool, Optional[LLMCall]]:
    """Ask a larger model whether a message the reader did not route asks for a design run.

    Used when the answerer is too small to make this call itself (on the CPU the answerer is
    the reader's model). False when no model answers: the message is then answered.

    Parameters
    ----------
    message : str
        The user's message.
    llm : OllamaLLM or ScriptedLLM
        The model that judges (the reasoning model).
    designs : str
        The designs made so far in the conversation (their codes), or "none".
    thread : str
        The chat's thread (``thread.py``): what "it" or "do that again" refers to.

    Returns
    -------
    tuple of (bool, LLMCall or None)
        Whether to run the design, and the call.
    """
    from gemini_agent.answer import load

    earlier = f"Conversation so far:\n{thread}\n\n" if thread else ""
    msgs = [
        {"role": "system", "content": load(ROUTE_PROMPT)},
        {
            "role": "user",
            "content": f"Designs made so far: {designs}.\n{earlier}Message: {message}",
        },
    ]
    try:
        raw, call = llm.structured("route", msgs, ROUTE_SCHEMA, 20)
    except LLMError as err:
        return False, err.call
    return raw.get("run_design") is True, call


def messages_for(message: str, thread: str = "") -> List[dict]:
    """Return the chat messages for the intake call (static prefix first, so it caches).

    Parameters
    ----------
    message : str
        The user's message.
    thread : str
        The chat's thread, short (``thread.py``); without one the message goes alone, as in the
        worked examples.

    Returns
    -------
    list of dict
        System prompt, the worked examples and the message.
    """
    out = [{"role": "system", "content": SYSTEM_PROMPT}]
    for user, reply in EXAMPLES:
        out.append({"role": "user", "content": user})
        out.append({"role": "assistant", "content": json.dumps(reply)})
    if thread:
        # The chat so far, only to read a short follow-up ("and the cold?", "the second one",
        # "yes, run it"); code takes numbers from the message alone (``read_message``).
        message = (
            "Earlier in this chat (only to understand what the message refers to; read the "
            f"message itself):\n{thread}\n\nMessage: {message}"
        )
    out.append({"role": "user", "content": message})
    return out


def language_of(message: str) -> str:
    """Return ``"nl"`` for a Dutch message (three Dutch function words or more), else ``"en"``."""
    return "nl" if len(DUTCH_WORDS.findall(message)) >= 3 else "en"


RESERVOIR_WORDS = re.compile(
    r"reservoir|aquifer|\brock\b|formation|geothermal (water|source)|reservoirtemperatuur",
    re.I,
)
INJECTATE_WORDS = re.compile(r"inject|reinject|return(ed)? brine|cooled brine|teruggevoerd", re.I)


def _about_reservoir(message: str, match) -> bool:
    """Return True when the sentence of a "N °C colder/warmer" says it of the reservoir."""
    start = max(message.rfind(".", 0, match.start()), message.rfind("?", 0, match.start())) + 1
    ends = [i for i in (message.find(".", match.end()), message.find("?", match.end())) if i >= 0]
    sentence = message[start : min(ends) if ends else len(message)]
    return bool(RESERVOIR_WORDS.search(sentence)) and not INJECTATE_WORDS.search(sentence)


def read_message(
    message: str, llm, project: Optional[ProjectData] = None, thread: str = ""
) -> IntakeResult:
    """Run the intake call and check its output against the message.

    Parameters
    ----------
    message : str
        The user's message.
    llm : OllamaLLM or ScriptedLLM
        The model client.
    project : ProjectData, optional
        What the project already holds (used to decide whether cooling is wanted).
    thread : str
        The chat's thread, short: helps the model read a follow-up; numbers are still taken
        from the message alone.

    Returns
    -------
    IntakeResult
        Relevance, intent, the trusted brief updates and the values that were dropped.
    """
    project = project or ProjectData()
    strong, weak = bool(STRONG_WORDS.search(message)), bool(WEAK_WORDS.search(message))
    language = language_of(message)
    if not strong:
        meta = "greeting" if GREETING.search(message) else "about" if ABOUT.search(message) else ""
        if meta:
            return IntakeResult(
                relevant=True, bypass=False, intent=meta, language=language, screened=True
            )
    raw: Dict[str, object] = {}
    call: Optional[LLMCall] = None
    llm_ok = True
    try:
        raw, call = llm.structured("intake", messages_for(message, thread), SCHEMA)
    except ModelUnavailable as err:
        return IntakeResult(
            relevant=True,
            bypass=False,
            intent="other",
            language=language,
            call=err.call,
            llm_ok=False,
            unavailable=str(err),
        )
    except LLMError as err:
        call, llm_ok = err.call, False
    dropped: List[str] = []

    # Domain words decide when present; otherwise the model does (code rules if it failed).
    relevant = strong or (bool(raw.get("relevant")) if llm_ok else weak)
    bypass_words = bool(BYPASS_WORDS.search(message))
    bypass = bypass_words or bool(raw.get("bypass"))  # a suspicion: see ``confirm_bypass``

    updates: Dict[str, object] = {}
    temps = network_temperatures(message)
    if "heating" in temps:
        updates["heating"] = temps["heating"]
    if "cooling" in temps:
        updates["cooling"] = temps["cooling"]

    spans = _pair_spans(message)
    annual = _annual(message)
    for key in ("annual_heat_gwh", "annual_cool_gwh"):
        value = annual.get(key)
        if value is None and raw.get(key) is not None:
            if _in_context(message, raw[key], "annual", spans):
                value = float(raw[key])
            else:
                dropped.append(f"{key}={raw[key]} (not written as a demand)")
        if value is not None:
            updates[key] = value

    depths = _depths(message)
    if not depths:
        for value in raw.get("depths_m") or []:
            if _in_context(message, value, "depth", spans):
                depths.append(float(value))
            else:
                dropped.append(f"depth {value} m (not written as a depth)")
    # Only depths the planner's catalogue allows (5 Nov: the model's 100 m for "a 4th doublet
    # at 100 m" replaced the aquifers on the inputs card, past the reasoning reading's refusal).
    low, high = _depth_range()
    for value in [d for d in depths if not low <= d <= high]:
        dropped.append(f"depth {value:g} m (outside {low:g}-{high:g} m)")
    depths = [d for d in depths if low <= d <= high]
    if depths:
        updates["doublet_depths_m"] = depths
    for key, kind in (
        ("reservoir_depth_m", "reservoir_depth"),
        ("reservoir_temp_c", "reservoir_temp"),
    ):
        if raw.get(key) is not None:
            low, high = PLAUSIBLE[key]
            if not low <= float(raw[key]) <= high:
                dropped.append(f"{key}={raw[key]} (outside {low:g}-{high:g})")
            elif _in_context(message, raw[key], kind, spans):
                updates[key] = float(raw[key])
            else:
                dropped.append(f"{key}={raw[key]} (not written as one)")

    change = CHANGE.search(message)
    if change and not _about_reservoir(message, change):
        # "the injected brine is 30-40 K colder" describes the injectate: no reservoir change
        # (31 Oct panel). The reasoning model's reading decides those; this rule only takes a
        # sentence about the reservoir itself.
        dropped.append(f"'{change.group(0)}' (not said of the reservoir)")
        change = None
    if change:
        size = float(change.group(1).replace(",", "."))
        colder = change.group(2).lower() in ("colder", "cooler", "lower", "kouder")
        updates["reservoir_delta_c"] = -size if colder else size
    elif raw.get("reservoir_change_c"):
        dropped.append(f"reservoir change {raw['reservoir_change_c']} (no wording for it)")

    excluded = excluded_equipment(message)
    if excluded:
        updates["excluded"] = excluded
    counts = doublet_counts(message)
    if len(counts) == 1:
        updates["n_doublets"] = counts[0]
    elif len(counts) > 1:
        updates["n_doublets"] = None  # "2 doublets or 1 doublet?": the search tries both
    coverage = _coverage(message)
    if coverage is not None:
        updates["min_heat_coverage"] = coverage
        updates["min_cool_coverage"] = coverage
    updates["wants_cooling"] = bool(COOL_WORDS.search(message)) or project.has_cool_profile

    intent = str(raw.get("intent") or "design")
    if intent not in INTENTS:
        intent = "design"
    # With the chat's thread in its prompt the small model names values from earlier turns
    # ("what did I ask first?" read as the reservoir, 4 Nov): then only the message's own words.
    # The model's values still say the message is a question (the intent below); they are not
    # looked up when it read a thread.
    asks_for = lookup.wanted(message, [str(k) for k in raw.get("asks_for") or []])
    own = lookup.wanted(message) if thread else asks_for
    if WHAT_IF_WORDS.search(message) or "reservoir_delta_c" in updates:
        intent = "what_if"
    elif len(depths) >= 2 or COMPARE_WORDS.search(message):
        intent = "compare"
    elif asks_for and lookup.is_question(message) and intent not in ("explain", "about"):
        intent = "question"
    elif EXPLAIN_START.search(message) and not lookup.DESIGN_VERBS.search(message):
        intent = "explain"
    elif intent == "question" and not asks_for and not lookup.is_question(message):
        intent = "design"
    elif intent in ("other", "greeting", "about") and relevant and asks_design(message):
        # Only a request for a design becomes one; anything else goes to the answerer.
        intent = "design"
    if intent in ("question", "explain", "other") and BEST_DESIGN.search(message):
        intent = "design"  # a search for the best design, not a value of the current one
    if intent == "design" and not (strong or asks_design(message) or temps or annual or depths):
        intent = "other"  # "give me instructions" or letter mash is not a design request
    if intent == "about" and not SELF_REF.search(POLITE.sub("", message)):
        intent = "explain"  # "could you explain geothermal energy?" is about the topic

    cop = COP_CLAIM.search(message)
    return IntakeResult(
        relevant=relevant,
        bypass=bypass and relevant,
        bypass_words=bypass_words,
        intent=intent,
        language=language,
        updates=updates,
        dropped=dropped,
        cop_claim=float(cop.group(1).replace(",", ".")) if cop else None,
        call=call,
        llm_ok=llm_ok,
        # An "explain" keeps them too: a why-question about the design looks up its heat split.
        asks_for=own if intent in ("question", "explain") else [],
        think=bool(raw.get("think")) and llm_ok,
    )


HEATING_OPTIONS = ["80/50 °C", "70/40 °C", "60/30 °C"]
COOLING_OPTIONS = ["6/12 °C", "8/14 °C", "16/19 °C"]


def missing_inputs(brief: DesignBrief, project: ProjectData) -> List[Question]:
    """Return the inputs a design still needs, each with a proposed default where one is safe.

    Parameters
    ----------
    brief : DesignBrief
        What is known so far.
    project : ProjectData
        What the project's files already provide.

    Returns
    -------
    list of Question
        Empty when the design can go ahead; otherwise the items of ONE clarifying question.
    """
    out: List[Question] = []
    if not (project.has_heat_profile or brief.annual_heat_gwh or project.annual_heat_gwh):
        out.append(
            Question(
                id="heat_demand",
                label="Heat demand",
                hint="Annual GWh, or attach an hourly profile (CSV or XLSX).",
            )
        )
    if brief.wants_cooling and not (
        project.has_cool_profile or brief.annual_cool_gwh or project.annual_cool_gwh
    ):
        out.append(
            Question(
                id="cool_demand",
                label="Cooling demand",
                hint="Annual GWh, or attach an hourly profile.",
                required=False,
                default="no cooling",
            )
        )
    if brief.heating is None:
        out.append(
            Question(
                id="dh_supply_return_c",
                label="Heating network, supply and return",
                options=HEATING_OPTIONS,
                default="70/40 °C",
                hint="Typical for a new network.",
            )
        )
    if brief.wants_cooling and brief.cooling is None:
        out.append(
            Question(
                id="dc_supply_return_c",
                label="Cooling network, supply and return",
                options=COOLING_OPTIONS,
                default="6/12 °C",
                hint="Typical for building cooling.",
            )
        )
    has_reservoir = project.has_reservoir or brief.reservoir_temp_c or brief.reservoir_depth_m
    if not has_reservoir and not brief.doublet_depths_m and not brief.aquifers:
        out.append(
            Question(
                id="reservoir_depth_or_temperature",
                label="Reservoir",
                hint="Depth or temperature; the estimate is a regional average.",
                options=["2,500 m, 87 °C (regional estimate)"],
                default="2,500 m, 87 °C (regional estimate)",
            )
        )
        out.append(
            Question(
                id="transmissivity_or_pi",
                label="Reservoir transmissivity",
                hint="From a well test; it sets the flow the doublet can give.",
                options=["30 Dm (typical)"],
                default="30 Dm (typical)",
            )
        )
    return out


def apply_answers(brief: DesignBrief, answers: Dict[str, str]) -> DesignBrief:
    """Return the brief updated with the user's answers to a clarifying question.

    Parameters
    ----------
    brief : DesignBrief
        The brief before the answers.
    answers : dict
        Question id to the chosen or typed value, for example ``{"dh_supply_return_c":
        "70/40 °C"}``.

    Returns
    -------
    DesignBrief
        A new brief with the answers applied.
    """
    data = brief.model_dump()
    for key, value in answers.items():
        text = str(value)
        nums = numbers_in(text)
        if key in ("dh_supply_return_c", "dc_supply_return_c") and len(nums) >= 2:
            data["heating" if key.startswith("dh") else "cooling"] = {
                "supply_c": nums[0],
                "return_c": nums[1],
            }
        elif key == "heat_demand" and nums:
            data["annual_heat_gwh"] = nums[0]
        elif key == "cool_demand":
            if nums:
                data["annual_cool_gwh"] = nums[0]
            else:
                data["wants_cooling"] = False
        elif key == "reservoir_depth_or_temperature" and nums:
            for n in nums:
                if n >= 300:
                    data["reservoir_depth_m"] = n
                elif 30 <= n <= 250:
                    data["reservoir_temp_c"] = n
        elif key == "transmissivity_or_pi" and nums:
            data["transmissivity_dm"] = nums[0]
    return DesignBrief(**data)
