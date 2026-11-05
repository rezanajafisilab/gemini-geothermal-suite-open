"""The agent: a code orchestrator over role-specific models, tools and checks.

``Agent.run`` answers one user turn and yields AG-UI events (``gemini_agent.events``).
The roles (``router.py`` says which model plays each, on which device):

- **Reader.** The small model reads the message (intake): does it need a simulation (design,
  compare, what-if, a missing component model) or an answer from what is known? It also pulls
  out the numbers, which code checks. Greetings and "who are you" skip this call.
- **Planner and reflector.** Which designs to study, which fixes to try when none meets the
  brief (``policies``). Code rules decide in fast mode, the larger model in reasoning mode
  (``reasoning=True``); code checks its choices either way.
- **Engineer and verifier.** Typed tools compute every number (memoised); the verifier checks
  every design. A tool that raises leaves out only the design that needed it, and a design that
  fails a physics check is left out the same way; the answer says which and why.
- **Answerer.** A model writes every reply from a context pack (``answer.py``): who Dioscuri
  is, the project, the simulated designs, recent turns, cited passages and, after a tool run,
  the checked template answer. It may ask a multiple-choice question when a message can mean
  different things, and says so when a message is not a proper question. Code checks every
  number and citation; the template is the fallback.
- **Ask.** A missing input ends the run with one question (an interrupt); so does a shortfall,
  where the user picks a fix or keeps their limits, and an unclear message, where the user picks
  what they meant. ``Agent.run(session, answers=...)`` continues the run.

A session keeps the facts the user gave (network temperatures, demand, reservoir), a ledger of
every evaluated design, which what-if questions reuse, and the last few exchanges; limits such
as "no heat pumps" apply to their own turn only. With a ``session_dir`` every session is saved
as JSON after each turn.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import types
import urllib.parse
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from gemini_agent import answer as answering
from gemini_agent import (
    aquifers,
    capabilities,
    card_edits,
    chat_state,
    claims,
    clarify,
    engine,
)
from gemini_agent import events as ev
from gemini_agent import (
    evidence,
    files,
    intake,
    lookup,
)
from gemini_agent import memory as remembered
from gemini_agent import (
    modelgen,
    parameters,
    policies,
    provenance,
    reliability,
    reply_check,
    reporter,
    suggest,
    verifier,
    workbench,
)
from gemini_agent.contract import DesignBrief, LedgerEntry, ProjectData, Question
from gemini_agent.llm import LLMCall, ModelUnavailable, unavailable_hint, unavailable_reason
from gemini_agent.thread import Thread, designs_named

PERSISTENT = (
    "site",
    "homes",
    "heating",
    "cooling",
    "annual_heat_gwh",
    "annual_cool_gwh",
    "reservoir_depth_m",
    "reservoir_temp_c",
    "transmissivity_dm",
    "doublet_stops",  # the user's dates for the doublets' stops: the project's, like the switches
    "aquifers",  # the aquifers described, each with its own rock and gas: the project's
)
PERSISTENT_RULES = (
    "network_length_km",
    "planned_service",
    "co2_reinjection",
    "flare_brine_gas",
    "free_cooling",
    "grid_by_month",
    "solar_mwp",
    "storage_mwh",
    "storage_ates",
    "second_aquifer_depth_m",
    "second_aquifer_thickness_m",
    "second_aquifer_permeability_md",
    "ground_temperature_c",
    "stop_days_off",  # the Maintenance section's, like the switches: the project's
    "service_plan",
    "stops_relaxed",
)
CHALLENGE_PROJECT = ProjectData(
    name="Challenge district 2027",
    has_heat_profile=True,
    has_cool_profile=True,
    has_reservoir=True,
    files=[
        "GEMINI_Heating_Demand_Daily_2027.csv",
        "GEMINI_Cooling_Demand_Daily_2027.csv",
        "GEMINI_Hackathon_Challenge_Requirements.docx.pdf",
    ],
    annual_heat_gwh=111.67,
    annual_cool_gwh=23.74,
    reservoir_depth_m=2500,
    reservoir_temp_c=87,
)
EXAMPLE_PROJECT = CHALLENGE_PROJECT  # the name older callers import
DOCS_ROOT = Path(__file__).resolve().parents[2]  # the repository: documentation figures
THREAD_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
HISTORY = 6  # exchanges a session keeps in full (prompts show the last three; ``thread``)
PROJECT_DOCS = (".pdf", ".md", ".txt", ".rst")  # a project's files that are searched as text
# What a reply's kind makes of the run's behaviour (evals and traces read it).
KIND_BEHAVIOUR = {"out_of_scope": "refuse", "unclear": "clarify", "clarify": "clarify"}
FILE_NAME = re.compile(r"[\w.-]+\.(?:json|csv|xlsx|pdf|md|txt|tex)\b")
# A message about the conversation's attached files.
ATTACHED = re.compile(
    r"\battach\w*|\b(the|this|that|these|my|our|uploaded) (file|document|datasheet|notes|pdf|"
    r"report|spreadsheet|upload)s?\b|\bbijlage",
    re.I,
)
# "Explain the cascade": the design's own heat path, which the explain template states.
# Other questions about a design ("is it good?", "why is the COP ...") go to the answerer.
ABOUT_DESIGN = re.compile(r"cascade|summer|winter", re.I)
RUNNER_UP = re.compile(r"runner[- ]?up|second[- ]best|next[- ]best|tweede beste", re.I)
# Changes that only say what the search looks for: the plant itself stays as it is.
SEARCH_FOR = {"objective", "allow", "min_co2_saving"}
# A question that opens with "why": the planner does not read it (code explains the choices).
# Words that set one design against another in a why-question.
DESIGN_VS = re.compile(
    r"\b(not|rather than|instead of|over|versus|vs\.?|compared?( to| with)?|than|against|"
    r"stacks? up)\b",
    re.I,
)
WHY_ANY = re.compile(r"\bwhy\b|\bhow come\b|\breason\b", re.I)
WHY_LEAD = re.compile(r"^\s*(why|how come|waarom|hoezo|warum)\b", re.I)
# A question about why something is as it is: never a new design run.
WHY_START = re.compile(
    r"^\s*(why|how come|waarom|hoezo)\b|\bwhy (did|do|does|is|are|was|were)\b", re.I
)
# A design's code in a message ("1D-BO-EC@3500", "U2"), and words that ask to see it.
DESIGN_CODE = re.compile(
    r"\b[123]D-(?:HP|BO|DH)-(?:AB|EC|NC)(?:@\d{3,5}(?:\+\d{3,5})*)?"
    r"(?:-(?:2I\d*|ST\d*|BL|PL\d*|PU\d*|IL\d*|IU\d*))*\b|\bU\d+\b"
)
SHOW_WORDS = re.compile(
    r"\b(show|open|see|display|details?|in full|full|look at|give me|what about|take|use|pick|"
    r"choose|select|go with|laat zien|toon)\b",
    re.I,
)
# A question about the result there is ("is this a good design?"), not a request for a new one.
ABOUT_RESULT = re.compile(
    r"\binterpret|\bis (this|it|that|the design|A\d) (a )?(good|bad|ok|okay|reasonable|right|"
    r"the best)|what does (this|it|that|the result) mean|\bwhy\b",
    re.I,
)


# What a turn did, for the chat's thread, by the reply's behaviour.
THREAD_DID = {
    "answer": "answered",
    "about": "said what Dioscuri is",
    "greeting": "greeted",
    "clarify": "asked a question back",
    "refuse": "declined as off-topic",
    "reject": "declined (asked to skip the simulator or the checks)",
    "design": "reported the design",
    "file": "opened a file",
    "error": "hit an error",
    "model_unavailable": "could not reach its model",
}
# Questions a typed reply may answer (the model decides); the inputs card has its own reading.
OPEN_KINDS = ("which_design", "choice", "decision", "generate", "approval", "inputs")
# Replies after which the inputs card asked before stays open (nothing ran, nothing replaced it).
HELD_OVER = ("answer", "about", "greeting", "refuse", "clarify")
# Letters and digits left after the claim check below which a reply is too little to stand.
NEARLY_EMPTY = 20
# A reply that opens by saying the user's statement is wrong.
CORRECTED = re.compile(r"^\W*(not quite|no\b|not exactly|that is not|that's not|actually)", re.I)


def thread_flat(text: str, limit: int) -> str:
    """Return text on one line, cut to ``limit`` (``thread.flat``)."""
    from gemini_agent.thread import flat

    return flat(text, limit)


def project_fingerprint(project: ProjectData) -> str:
    """Return a short hash of a project's data.

    Inputs confirmed for a project stay confirmed until its data changes.
    """
    raw = json.dumps(project.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def project_key(session: "Session") -> str:
    """Return where a project's documents are kept in the document search."""
    return "project:" + session.project.id


@dataclass
class ToolError:
    """A tool call that raised; the design that needed it is left out with this reason."""

    tool: str
    message: str

    def __str__(self) -> str:
        """Return the reason as the answer states it."""
        return f"{self.tool} failed: {self.message}"


def designs_text(session: "Session", limit: int = 8) -> str:
    """Return the conversation's designs and the last search's picks, one per line, for the reader.

    "A1 1D-HP-EC-N1: best overall (chosen)", "A2 1D-HP-AB: cheapest", "W1 1D-HP-EC-N1: what-if,
    heating return temperature 50 °C".
    """
    rows: List[str] = []
    seen = set()
    picked = [e for e in session.candidates or [] if e.alternative.picks]
    for e in picked + list(reversed(session.ledger)):
        a = e.alternative
        key = (a.uid, a.code, e.change_label)
        if key in seen or not a.code:
            continue
        seen.add(key)
        what = ", ".join(engine.PICK_NAMES[k] for k in a.picks if k in engine.PICK_NAMES)
        if a.role == "what_if":
            what = "what-if" + (f", {e.change_label}" if e.change_label else "")
        elif a.role == "user":
            what = "your design"
        if session.chosen is not None and (
            e is session.chosen
            or (
                a.uid
                and a.uid == session.chosen.alternative.uid
                and a.code == session.chosen.alternative.code
            )
        ):
            what = (what + " " if what else "") + "(the current design)"
        own = (session.design_names or {}).get(reporter.design_id(e))
        if own:  # the user's own name for it: a message may call it that
            what = (what + ", " if what else "") + f'named "{own}" by the user'
        rows.append(f"{a.uid or a.code} {a.code}" + (f": {what}" if what else ""))
        if len(rows) >= limit:
            break
    # The runs, so "run A", "the first design" or "the base case" can be named (2 Nov).
    if len(session.searches or []) > 1:
        from gemini_agent import naming

        for i, srch in enumerate(session.searches):
            chosen = next(
                (e for e in srch.get("candidates") or [] if e.alternative.role == "chosen"), None
            )
            pick = f": picked {chosen.alternative.uid} {chosen.alternative.code}" if chosen else ""
            rows.append(naming.run_name(srch, i + 1, session.searches[0]) + pick)
    # Designs the user named or starred, whatever search they came from.
    for k in list(session.design_names or {}) + list(session.starred or []):
        if len(rows) >= limit + 4 or any(r.startswith(k.split(" · ")[0] + " ") for r in rows):
            continue
        own = (session.design_names or {}).get(k)
        star = " (starred)" if k in (session.starred or []) else ""
        rows.append(
            f"{k.replace(' · ', ' ')}" + (f': named "{own}" by the user' if own else "") + star
        )
    return "\n".join(rows)


def names_designs(message: str, session: "Session") -> int:
    """Return how many designs a message names itself: by id, by code or by a pick's words.

    The planner may list designs the message never named ("a 2.5 km doublet and a 3.5 km
    doublet" listed as A1 and A49 on 1 Nov): a comparison of existing designs needs two named.
    """
    text = message.lower()
    seen = set()
    pool = list(session.ledger) + list(session.candidates or [])
    for e in pool:
        a = e.alternative
        uid = (a.uid or "").lower()
        if (uid and re.search(rf"\b{re.escape(uid)}\b", text)) or a.code.lower() in text:
            seen.add(a.code)
        elif any(w in text for k in a.picks for w in reliability.PICK_HINTS.get(k, ())):
            seen.add(a.code)
    return len(seen)


# How a message refers to one of the picks ("could they live with the cheapest one?"). "The
# cheapest reliable" (the pick's name since 4 Nov) and "the most reliable" are the reliable
# pick, "the greenest reliable" the greenest reliable plan: not the cheapest or the lowest CO2.
DESIGN_REFS = (
    (re.compile(r"\bthe cheap(est|er)\b(?!\s+reliab)", re.I), "cheapest"),
    (
        re.compile(r"\bthe (greenest|cleanest|lowest[- ]co[2₂])\b(?!\s+reliab)", re.I),
        "lowest co2",
    ),
    (re.compile(r"\bthe (most|cheapest) reliable\b", re.I), "most reliable"),
    (re.compile(r"\bthe (greenest|cleanest) reliable\b", re.I), "greenest reliable"),
    (re.compile(r"\bthe gas[- ]free (one|design|plan|option)\b", re.I), "gas-free"),
    (re.compile(r"\bthe (best overall|recommended)\b", re.I), "best overall"),
)
DESIGN_ID = re.compile(r"\b([A-Z]\d{1,3})\b")
# A message about other designs than the current one: the reply may name them.
OTHER_DESIGNS = re.compile(
    r"\b(which|other|another|alternatives?|options?|designs|runs)\b",
    re.I,
)


# A run by its letter or its place: "run A", "the first design", "the base case", "the previous
# run" (2 Nov: "the first design's cost of heat" was looked up on the current one).
RUN_REFS = (
    (re.compile(r"\brun ([a-z])\b", re.I), None),
    (
        re.compile(
            r"\b(first|base[- ]case|original|initial) (design|run|one|plan)\b|" r"\bbase case\b",
            re.I,
        ),
        0,
    ),
    (re.compile(r"\b(previous|earlier|last|old) (design|run|one|plan)\b", re.I), -2),
)


def runs_named(message: str, session: "Session") -> List[LedgerEntry]:
    """Return the picks of the runs a message names ("run A", "the first design")."""
    searches = list(session.searches or [])
    if len(searches) < 2:
        return []
    out: List[LedgerEntry] = []
    for rx, at in RUN_REFS:
        for m in rx.finditer(message):
            if at is None:
                i = ord(m.group(1).upper()) - 65
            else:
                i = at if at >= 0 else len(searches) + at
            if 0 <= i < len(searches):
                pick = next(
                    (
                        e
                        for e in searches[i].get("candidates") or []
                        if e.alternative.role == "chosen"
                    ),
                    None,
                )
                if pick is not None and all(pick is not x for x in out):
                    out.append(pick)
    return out


# A design's code typed in the words ("1D-BO-EC@3500-FC", any case), and an id after @ in any
# case ("@a33"): without @ a lower-case id is too like a word.
CODE_IN_WORDS = re.compile(r"(?<![\w-])\d+D-[A-Z0-9@+\-]*[A-Z0-9]", re.I)
AT_ID = re.compile(r"(?<![\w.])@([A-Za-z]\d{1,3})\b")


def ids_in(message: str, session: "Session") -> List[LedgerEntry]:
    """Return the designs a message names by id or code ("A29", "@a29", "1D-BO-EC@3500-FC").

    Not by a superlative or a run's place: beside designs picked with @, "the cheaper of these
    two" is one of them, not the search's cheapest.
    """
    names = DESIGN_ID.findall(message) + [m.upper() for m in AT_ID.findall(message)]
    names += CODE_IN_WORDS.findall(message)
    names = list(dict.fromkeys(names))
    return reliability.resolve(names, session)[0] if names else []


def named_in(message: str, session: "Session") -> List[LedgerEntry]:
    """Return the designs a message names: by id ("A29", "@a29"), code, pick or run.

    By code: "1D-BO-EC@3500-FC" typed without @ (4 Nov: only the ids were read). By run: "run
    A", "the first design". A drawn design of the design-space sweep ("X12") is opened when it
    is not in the chat yet, as the tabs open it. The planner does not always list these; code
    reads them from the words.
    """
    names = [name for rx, name in DESIGN_REFS if rx.search(message)]
    names += DESIGN_ID.findall(message)
    names += [m.upper() for m in AT_ID.findall(message)]
    names += CODE_IN_WORDS.findall(message)
    names = list(dict.fromkeys(names))
    found, missing = reliability.resolve(names, session) if names else ([], [])
    for name in missing:
        drawn = _drawn(name, session)
        if drawn is not None and all(drawn is not x for x in found):
            found.append(drawn)
    for e in runs_named(message, session):
        if all(e is not x for x in found):
            found.append(e)
    return found


# Refusals of the aquifers' list or the depths to try: said at the inputs card's top, never on a
# field (the aquifers' box holds records, not the depths a message gave).
LIST_ERRORS = ("aquifers", "aquifer_depths_m")


def refused_on_card(reading) -> Tuple[Dict[str, str], Dict[str, object], List[str]]:
    """Return what a reading refused, for the inputs card: why by key, the value asked, words.

    Only a value the message gave for a parameter of the card and code refused on its merits
    (a heating supply under its return, a value outside its range); not a misreading (a quote
    not in the message, a doublet's name taken for a count).
    """
    errors: Dict[str, str] = {}
    asked: Dict[str, object] = {}
    notes: List[str] = []
    for item in getattr(reading, "dropped", None) or []:
        m = re.match(r"^(\w+)=(.+?): (.+)$", str(item))
        if m is None or m.group(1) not in parameters.CATALOGUE:
            continue
        key, raw, why = m.groups()
        misread = (
            "quote is not in the message",
            "not in the quote",
            "names a doublet",
            "efficiency",
        )
        if any(w in why for w in misread):
            # The reading's own slip (a number the words do not give): no value of the user's
            # to show as refused (4 Nov: "I did not take the number of doublets of 2" for "use
            # more doublets").
            continue
        if why == parameters.VAGUE:
            continue  # asked for by its own question ("by how much?")
        try:
            value: object = float(raw)
        except ValueError:
            value = raw
        errors[key], asked[key] = why, value
        p = parameters.CATALOGUE[key]
        said = f"{value:g} {p.unit}".strip() if isinstance(value, float) else str(value)
        notes.append(
            f"I did not take the {p.label.lower()} of {said}: {why}. It is marked on the card: "
            "change it there, or the value it conflicts with."
        )
    return errors, asked, notes


def _drawn(name: str, session: "Session") -> Optional[LedgerEntry]:
    """Return a drawn design of the latest sweep named by its id ("X12"), added to the chat."""
    m = re.fullmatch(r"X(\d+)", name.strip().upper())
    srch = next((x for x in reversed(session.searches or []) if x.get("sweep")), None)
    if m is None or srch is None:
        return None
    from gemini_agent import workbench

    sweep_id = f"{srch['id']}·sweep·{int(m.group(1)) - 1}"  # X1 is the sweep's row 0
    for e in session.ledger:
        if e.alternative.sweep_id == sweep_id:
            return e
    try:
        full = workbench.sweep_entry(session, sweep_id)
    except (KeyError, IndexError, ValueError):
        return None
    full.alternative.sweep_id = sweep_id
    session.ledger.append(full)
    return full


def _current_named(reading: parameters.Reading, session: "Session") -> int:
    """Return 1 when the planner's designs include the current one ("compare it with …")."""
    if session.chosen is None:
        return 0
    found, _ = reliability.resolve(reading.designs, session)
    return int(any(e.alternative.code == session.chosen.alternative.code for e in found))


def planned(
    reading: parameters.Reading, session: "Session", message: str = "", picked: int = 0
) -> bool:
    """Return True when a reading needs the step planner: failures, comparisons, several steps.

    One design or one what-if keeps its own path (the inputs card, the shortfall card); so does
    a comparison of options not yet designed ("a 2.5 km and a 3.5 km doublet"): the search runs
    them.
    """
    kinds = [s.do for s in reading.steps]
    made = "design" in kinds and kinds.index("design") < (
        kinds.index("compare") if "compare" in kinds else 0
    )
    found = reliability.resolve(reading.designs, session)[0]
    # One existing design that is not the current one, and nothing new to run: "how does it
    # compare with the most reliable one?" sets it against the current design (4 Nov: the
    # comparison was dropped, and the reply called the cheapest the most reliable).
    against_current = (
        session.chosen is not None
        and len(found) == 1
        and found[0].alternative.code != session.chosen.alternative.code
        and not reading.changes
        and not reading.doublets
    )
    if (
        "compare" in kinds
        and not made
        and picked < 2  # two picked with @ are what "which of these two?" compares
        and not against_current
        and (
            len(found) < 2
            or (message and names_designs(message, session) + _current_named(reading, session) < 2)
        )
    ):
        reading.steps = [s for s in reading.steps if s.do != "compare"]
        kinds = [s.do for s in reading.steps]
    if reading.failures or set(kinds) & {"compare", "summary", "uncertainty", "report"}:
        return True
    real = [k for k in kinds if k != "answer"]
    return len(real) > 1


def intake_conditions(turn: DesignBrief, before: DesignBrief) -> Dict[str, float]:
    """Return the conditions the reader put in the turn's brief, as catalogue changes.

    A plan's what-if step may get no change from the reasoning model ("check it 10 °C colder"
    read by the reader alone); these stand in for it then.
    """
    out: Dict[str, float] = {}
    if (turn.reservoir_delta_c or 0.0) != (before.reservoir_delta_c or 0.0):
        out["reservoir_change_k"] = float(turn.reservoir_delta_c or 0.0)
    for side, net in (("heat", "heating"), ("cool", "cooling")):
        a, b = getattr(turn, net), getattr(before, net)
        if a is not None and b is not None:
            if a.return_c != b.return_c:
                out[f"{side}_return_c"] = a.return_c
            if a.supply_c != b.supply_c:
                out[f"{side}_supply_c"] = a.supply_c
    return out


CAP_KEYS = (
    "flow_max_m3h",
    "flow_min_m3h",
    "max_brine_cooling_k",
    "operating_days",
    "pump_efficiency",
)


def held_caps(brief: DesignBrief) -> DesignBrief:
    """Return the brief with the challenge's caps back (a run that relaxed one keeps its own)."""
    rules = {k: v for k, v in (brief.rules or {}).items() if k not in CAP_KEYS}
    return brief.model_copy(update={"rules": rules})


def step_label(step: parameters.Step, k: int, reading: parameters.Reading) -> str:
    """Return a plan step in a few words for the plan card: "What-if: heating return 50 °C"."""
    if step.do == "design":
        changes = reading.changes_for(k)
        what = parameters.label(changes) if changes else ""
        return "Design" + (f" with {what}" if what else "")
    if step.do == "what_if":
        what = parameters.label(reading.changes_for(k))
        return f"What-if: {what}" if what else "What-if (no amount read)"
    if step.do == "failure":
        mine = [f for f in reading.failures if f.step == k] or reading.failures
        bits = []
        for f in mine:
            unit = reliability.unit_words(f.unit)
            if f.dated:
                when = f"{reliability.day_name(int(f.first))}-{reliability.day_name(int(f.last))}"
            elif f.days:
                when = f"{f.days} days ({'mildest' if f.planned else 'worst'} start)"
            else:
                when = "all year"
            bits.append(f"{unit} out {when}")
        return ("Maintenance: " if any(f.planned for f in mine) else "Failure: ") + "; ".join(bits)
    if step.do == "compare":
        return "Compare " + (", ".join(reading.designs) or "the designs named")
    if step.do == "summary":
        return "Decision summary for the client"
    if step.do == "uncertainty":
        return "How sure: vary prices, costs and the reservoir"
    if step.do == "report":
        return "Operator's report (PDF)" + (
            f" of {', '.join(reading.designs)}" if reading.designs else ""
        )
    return "Answer"


def plan_dict(reading: parameters.Reading, steps: Sequence[parameters.Step]) -> dict:
    """Return a plan as plain data, to resume it once the inputs are confirmed."""
    return {
        "changes": reading.changes,
        "step_of": reading.step_of,
        "doublets": [d.model_dump() for d in reading.doublets],
        "failures": [f.__dict__ for f in reading.failures],
        "designs": list(reading.designs),
        "steps": [{"do": x.do, "quote": x.quote} for x in steps],
        "items": [list(x) for x in reading.items],
        "asked_steps": reading.asked_steps,
    }


def plan_from(data: dict) -> parameters.Reading:
    """Return the reading a saved plan holds (``plan_dict``)."""
    from gemini_agent.contract import DoubletSpec

    return parameters.Reading(
        changes=dict(data.get("changes") or {}),
        step_of=dict(data.get("step_of") or {}),
        doublets=[DoubletSpec(**d) for d in data.get("doublets") or []],
        failures=[parameters.Failure(**f) for f in data.get("failures") or []],
        designs=list(data.get("designs") or []),
        steps=[parameters.Step(**x) for x in data.get("steps") or []],
        items=[tuple(x) for x in data.get("items") or []],
        asked_steps=int(data.get("asked_steps") or 0),
    )


def search_letter(n: int) -> str:
    """Return the letter of the n-th search (0-based): A, B ... Z, AA, AB ..."""
    out = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def next_uid(session: "Session", prefix: str) -> str:
    """Return the next free id with this prefix (W1, W2 ... for what-ifs, F1 ... failures)."""
    used = {e.alternative.uid for e in session.ledger}
    k = 1
    while f"{prefix}{k}" in used:
        k += 1
    return f"{prefix}{k}"


class Session:
    """One conversation in one project: what is known, the design ledger and any open question.

    Parameters
    ----------
    project : ProjectData, optional
        The project's data; defaults to the example district.
    thread_id : str, optional
        Conversation id; a new one is made when omitted.
    """

    def __init__(self, project: Optional[ProjectData] = None, thread_id: Optional[str] = None):
        """Start an empty conversation."""
        self.thread_id = thread_id or uuid.uuid4().hex[:12]
        self.project = project or CHALLENGE_PROJECT.model_copy(deep=True)
        self.brief = self.starting_brief(self.project)
        self.candidates: List[LedgerEntry] = []  # the last search's candidates
        self.reference: Optional[LedgerEntry] = None  # gas boilers and electric chillers
        self.searches: List[dict] = []  # every design search: {"id", "at", "message", ...}
        self.ledger: List[LedgerEntry] = []
        self.chosen: Optional[LedgerEntry] = None
        self.pending: Optional[dict] = None
        self.last: dict = {}
        self.turns = 0
        self.attachments: List[dict] = []  # {"name", "path"} of files the user attached
        self.flagged: List[str] = []  # files already reported for instruction-like text
        self.history: List[dict] = []  # {"user", "reply"} of the last exchanges
        self.thread = Thread()  # what the chat is about, kept by code (``thread.py``)
        self.state = chat_state.ChatState()  # designs, questions, decisions (``chat_state``)
        self.assumptions: dict = {}  # cost assumptions the user changed (Economics tab)
        self.user_designs: Dict[str, dict] = {}  # code -> {"parent", "name"}, made on the tabs
        self.confirmed: Dict[str, str] = {}  # project id -> fingerprint of the inputs confirmed
        self.failures: List[dict] = []  # failure what-ifs run (reliability.run_failure), last 20
        # The user's own names for designs and the ones they starred (the shortlist), by id.
        self.design_names: Dict[str, str] = {}
        self.starred: List[str] = []
        # What the user asked to remember (``memory``), when no project store keeps it.
        self.notes: List[dict] = []

    @staticmethod
    def starting_brief(project: ProjectData) -> DesignBrief:
        """Return what a conversation knows before its first message: the project's data."""
        known = project.has_reservoir
        profiles = project.has_heat_profile  # a district with its demand: its networks are known
        return DesignBrief(
            project_id=project.id,
            reservoir_depth_m=project.reservoir_depth_m if known else None,
            reservoir_temp_c=project.reservoir_temp_c if known else None,
            # The challenge fixes the supplies (100 °C, 20 °C); the returns are our assumption.
            heating=(project.heating or engine.DEFAULT_HEATING) if profiles else None,
            cooling=(project.cooling or engine.DEFAULT_COOLING) if profiles else None,
        )

    def use_project(self, project: ProjectData) -> None:
        """Move a conversation that has not started yet to another project.

        Its uploads and cost assumptions stay; what it knew of the old project goes.
        """
        if self.turns or self.ledger:
            raise ValueError("a conversation that has started stays in its project")
        self.project = project
        self.brief = self.starting_brief(project)

    def to_dict(self) -> dict:
        """Return everything the session knows as plain JSON-ready data."""
        chosen = next((i for i, e in enumerate(self.ledger) if e is self.chosen), None)
        return {
            "version": 1,
            "thread_id": self.thread_id,
            "project": self.project.model_dump(),
            "brief": self.brief.model_dump(),
            "ledger": [e.model_dump() for e in self.ledger],
            "chosen": chosen,
            "pending": self.pending,
            "last": self.last,
            "turns": self.turns,
            "attachments": self.attachments,
            "flagged": self.flagged,
            "history": self.history,
            "thread": self.thread.to_dict(),
            "state": self.state.to_dict(),
            "assumptions": self.assumptions,
            "user_designs": self.user_designs,
            "confirmed": self.confirmed,
            "failures": self.failures[-20:],
            "design_names": self.design_names,
            "starred": self.starred,
            "notes": self.notes,
            # The search's candidates without their daily series (the chosen one keeps them).
            "candidates": [
                e.model_dump(exclude={"year": {"daily_mw", "doublets"}}) for e in self.candidates
            ],
            "reference": self.reference.model_dump() if self.reference else None,
            "searches": [
                dict(
                    s,
                    candidates=[
                        e.model_dump(exclude={"year": {"daily_mw", "doublets"}})
                        for e in s["candidates"]
                    ],
                    reference=s["reference"].model_dump() if s.get("reference") else None,
                )
                for s in self.searches
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Rebuild a session from ``to_dict`` output.

        Parameters
        ----------
        data : dict
            A saved session.

        Returns
        -------
        Session
            The session, with its ledger and open question.
        """
        session = cls(ProjectData(**data["project"]), data["thread_id"])
        session.brief = DesignBrief(**data["brief"])
        session.ledger = [LedgerEntry(**e) for e in data["ledger"]]
        if data.get("chosen") is not None:
            session.chosen = session.ledger[data["chosen"]]
        session.pending = data.get("pending")
        session.last = data.get("last") or {}
        session.turns = data.get("turns", 0)
        session.attachments = data.get("attachments", [])
        session.flagged = data.get("flagged", [])
        session.history = data.get("history", [])
        session.thread = Thread.from_dict(data.get("thread"))
        session.state = chat_state.ChatState.from_dict(data.get("state"))
        session.assumptions = data.get("assumptions", {})
        session.user_designs = data.get("user_designs", {})
        session.confirmed = data.get("confirmed", {})
        session.failures = list(data.get("failures", []))
        session.design_names = dict(data.get("design_names", {}))
        session.starred = list(data.get("starred", []))
        session.notes = list(data.get("notes", []))
        session.candidates = [LedgerEntry(**e) for e in data.get("candidates") or []]
        if data.get("reference"):
            session.reference = LedgerEntry(**data["reference"])
        for raw in data.get("searches") or []:
            session.searches.append(
                dict(
                    raw,
                    candidates=[LedgerEntry(**e) for e in raw.get("candidates") or []],
                    reference=LedgerEntry(**raw["reference"]) if raw.get("reference") else None,
                )
            )
        return session

    def save(self, folder: Union[str, Path]) -> Path:
        """Write the session to ``<folder>/<thread_id>.json`` (atomically) and return the path."""
        path = Path(folder) / f"{self.thread_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, default=str), "utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, folder: Union[str, Path], thread_id: str) -> Optional["Session"]:
        """Return the saved session with this id, or None when there is none.

        Parameters
        ----------
        folder : str or Path
            Where sessions are saved.
        thread_id : str
            The conversation id (letters, digits, ``-`` and ``_`` only).

        Returns
        -------
        Session or None
            The session, if it was saved.
        """
        path = Path(folder) / f"{thread_id}.json"
        if not THREAD_ID.match(thread_id) or not path.is_file():
            return None
        return cls.from_dict(json.loads(path.read_text("utf-8")))

    def remember(self, brief: DesignBrief) -> None:
        """Keep the lasting facts of a turn's brief (not its one-off limits).

        Parameters
        ----------
        brief : DesignBrief
            The brief used in the turn.
        """
        data = self.brief.model_dump()
        for key in PERSISTENT:
            value = getattr(brief, key)
            if value is not None:
                data[key] = value.model_dump() if hasattr(value, "model_dump") else value
        # The network's length and planned service are the project's settings: they stay.
        kept = {k: v for k, v in (brief.rules or {}).items() if k in PERSISTENT_RULES}
        if kept:
            data["rules"] = dict(data.get("rules") or {}, **kept)
        self.brief = DesignBrief(**data)


class Agent:
    """Runs turns of a conversation.

    Parameters
    ----------
    llm : OllamaLLM or ScriptedLLM
        The reader, which reads every message.
    reasoning_llm : OllamaLLM, ScriptedLLM or callable, optional
        The reasoning model (or a function that returns it, so it is only created when used);
        it plans and picks fixes in reasoning mode. Defaults to ``llm``.
    trace_dir : str or Path, optional
        Folder for one JSONL trace per conversation (every event, with timestamps).
    session_dir : str or Path, optional
        Folder where each session is saved as JSON after every turn.
    docs : docs.DocIndex, optional
        Document search over GEMINI's documentation and the user's attached files.
    generator_llm : OllamaLLM, ScriptedLLM or callable, optional
        The model that writes code for a missing component (defaults to the reasoning model).
    registry : modelgen.Registry, optional
        Where approved generated models are kept; without one, no model is offered.
    answer_llm : OllamaLLM, ScriptedLLM or callable, optional
        The answerer, which writes every reply; defaults to the reasoning model in reasoning
        mode and to ``llm`` otherwise.
    router : Router, optional
        Hands out every role's model for the device a run asks for; when given, it replaces
        ``reasoning_llm``, ``generator_llm`` and ``answer_llm``.
    check_claims : {"auto", "always", "off"}, optional
        When the claim checker reads a reply against its sources. ``"auto"`` (the default,
        or ``$DIOSCURI_CHECK_CLAIMS``): replies written freely from documents, files or the
        self card, and every reply in reasoning mode; a reply that rewords the checked
        template, and a greeting, are not checked.
    warmup : warmup.Warmup, optional
        Loads the models (the server starts it at start). With one, a run whose model is not
        in memory (still loading, or unloaded by Ollama since) loads it first, as a row of its
        own ("Load qwen3.5:9b into GPU memory").
    """

    def __init__(
        self,
        llm,
        reasoning_llm=None,
        trace_dir: Optional[str] = None,
        session_dir: Optional[str] = None,
        docs=None,
        generator_llm=None,
        registry: Optional[modelgen.Registry] = None,
        answer_llm=None,
        router=None,
        check_claims: Optional[str] = None,
        warmup=None,
        memory=None,
    ):
        """Create the agent; tool results are memoised across turns and sessions.

        ``memory``: the projects' notes (``memory.Store``), shared by a project's chats; without
        it a chat keeps its own (``Session.notes``).
        """
        self.llm = llm
        self.router = router
        self.warmup = warmup
        self.memory = memory
        self.check_claims = check_claims or os.environ.get("DIOSCURI_CHECK_CLAIMS", "auto")
        self._answer_llm = answer_llm
        self._fast = llm
        self._device: Optional[str] = None
        self._size: Optional[str] = None
        self._session: Optional[Session] = None
        self._meter: Optional[evidence.PowerMeter] = None
        self._answer_down = False
        self._reasoning_llm = reasoning_llm
        self._generator_llm = generator_llm
        self.registry = registry
        self.docs = docs
        self._attached: set = set()
        self._warnings: List[str] = []
        self.trace_dir = Path(trace_dir) if trace_dir else None
        self.session_dir = Path(session_dir) if session_dir else None
        self._cache: Dict[str, object] = {}
        self._calls: List[LLMCall] = []
        self._summary: dict = {}
        self._tools = {"calls": 0, "cached": 0, "failed": 0}
        self._left_out: List[Tuple[str, str]] = []
        self._reasoning = False
        self._deep_down = False
        self._message = ""

    # ------------------------------------------------------------------ public

    def run(
        self,
        session: Session,
        message: Optional[str] = None,
        answers: Optional[Dict[str, str]] = None,
        reasoning: Optional[bool] = None,
        device: Optional[str] = None,
        designs: Optional[List[str]] = None,
        size: Optional[str] = None,
    ) -> Iterator[dict]:
        """Answer one turn, yielding AG-UI events.

        Parameters
        ----------
        session : Session
            The conversation.
        message : str, optional
            The user's message.
        answers : dict, optional
            Answers to the open question (missing inputs or a decision), by question id; used
            instead of ``message`` to continue an interrupted run.
        reasoning : bool, optional
            Reasoning: the larger model plans and picks fixes, and the answerer writes its
            reasoning steps first. ``None`` (the default) decides per message
            (``policies.wants_reasoning``); True or False forces it (benchmarks).
        device : {"auto", "cpu"}, optional
            Where the models run (with a ``router``): ``"auto"`` uses the GPU when there is
            one. Defaults to the router's device.
        designs : list of str, optional
            The designs the user picked for this message (@ in the composer, ids or handles):
            the question is about them, not the current design.
        size : {"auto", "9b", "4b"}, optional
            The model (with a ``router``, the header's model switch): ``"auto"`` takes the first
            that fits (``Router.reasoning``). Defaults to the router's size.

        Yields
        ------
        dict
            AG-UI events, ending with ``RUN_FINISHED`` (or ``RUN_ERROR``).
        """
        try:
            for event in self._run(session, message, answers, reasoning, device, designs, size):
                if self.trace_dir:
                    self.trace_dir.mkdir(parents=True, exist_ok=True)
                    with open(
                        self.trace_dir / f"{session.thread_id}.jsonl", "a", encoding="utf-8"
                    ) as fh:
                        fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
                yield event
        finally:
            # A stream closed early (the user stopped it) leaves no power sampler running.
            if self._meter is not None:
                self._meter.stop()
                self._meter = None

    def attach(self, session: Session, path: Union[str, Path], name: Optional[str] = None) -> int:
        """Attach a file to a conversation so its searches include it.

        Parameters
        ----------
        session : Session
            The conversation.
        path : str or Path
            The file (PDF, Markdown, text, CSV, JSON; images and spreadsheets are only opened).
        name : str, optional
            Name used in citations; the file name by default.

        Returns
        -------
        int
            Chunks indexed (0 when there is no document search).
        """
        name = name or Path(path).name
        if not any(a["name"] == name for a in session.attachments):
            session.attachments.append({"name": name, "path": str(path)})
        if self.docs is None or Path(name).suffix.lower() in (*files.IMAGE_TYPES, ".xlsx"):
            return 0  # images and spreadsheets are opened as files, not searched
        self._attached.add((session.thread_id, name))
        return self.docs.add_file(session.thread_id, path, name)

    def _index_project(self, session: Session) -> None:
        """Make the project's documents (the requirements PDF ...) searchable in this chat.

        Demand tables are opened as files, not searched: their rows are numbers, which the
        file view and the demand tool read.
        """
        if self.docs is None:
            return
        where = project_key(session)
        for name in session.project.files:
            if (where, name) in self._attached or Path(name).suffix.lower() not in PROJECT_DOCS:
                continue
            path = files.project_path(name, session.project)
            if path is not None:
                try:
                    self.docs.add_file(where, path, name)
                except Exception:  # noqa: BLE001 - an unreadable document is left out
                    continue
                self._attached.add((where, name))

    def forget(self, key: str) -> None:
        """Drop what the agent holds in memory for a conversation (or ``project:<id>``).

        Its files' passages leave the document search, and the conversation of the last run
        is let go when it is this one. Tool results stay: they are kept by their inputs, and
        another conversation may ask for the same design.
        """
        if self.docs is not None:
            self.docs.drop_thread(key)
        self._attached.difference_update({k for k in list(self._attached) if k[0] == key})
        if self._session is not None and self._session.thread_id == key:
            self._session = None

    def models(self) -> Dict[str, str]:
        """Return the reader's, the reasoning model's and the answerer's tags."""
        return {
            "fast": self._fast.model,
            "reasoning": self._deep().model,
            "answer": self._answerer().model,
        }

    # ----------------------------------------------------------------- the run

    def _run(
        self,
        session: Session,
        message: Optional[str],
        answers: Optional[Dict[str, str]],
        reasoning: Optional[bool],
        device: Optional[str] = None,
        designs: Optional[List[str]] = None,
        size: Optional[str] = None,
    ) -> Iterator[dict]:
        run_id = uuid.uuid4().hex[:10]
        start = time.perf_counter()
        # The GPU's energy while the turn runs (nothing on the CPU switch or without a GPU).
        meter = evidence.PowerMeter() if device != "cpu" and self.router is not None else None
        if meter is not None:
            meter.start()
        self._meter = meter
        session.turns += 1
        ledger_before = len(session.ledger)
        self._calls = []
        self._tools = {"calls": 0, "cached": 0, "failed": 0}
        self._left_out = []
        self._auto = reasoning is None
        self._reasoning, self._deep_down, self._answer_down = bool(reasoning), False, False
        self._device = device if self.router is not None else None
        self._size = size if self.router is not None else None  # the header's model switch
        self._fast = self.router.reader(device, size) if self.router is not None else self.llm
        self._session = session
        self._message = message or ""
        self._warnings = []
        self._template_stands = False  # a design question's template may replace a failed reply
        self._planner_keys = False  # the reasoning model named the values the question asks
        self._premises: List[str] = []  # what the message states as given (checked first)
        self._premises_said: List[str] = []  # the same, as the planner read them (the thread's)
        self._origin_of: List[float] = []  # the numbers asked "where does it come from?"
        self._already: List[str] = []  # options asked for that the design already has
        self._asks_change = False  # the small reader took the message for a change or a design
        self._topic_keys: List[str] = []  # the values the reply is about (its follow-ups')
        self._on_topic: Optional[bool] = None  # the reasoning model's reading: about the project?
        self._show: set = set()  # the cards the message asks to see ("search", "comparison")
        self._searched_now = False  # a search ran this turn (its card was sent then)
        self._lookup_on: Optional[LedgerEntry] = None  # the one design a question names
        # The asked values as other designs have them, with their names (``answering.answer``).
        self._theirs: List[Tuple[str, List[str]]] = []
        # The designs the user picked for this message (@): the question is about them.
        self._picked: List[LedgerEntry] = (
            reliability.resolve(list(designs), session)[0] if designs else []
        )
        self._focus: Optional[LedgerEntry] = (
            self._picked[0]
            if len(self._picked) == 1 and self._picked[0] is not session.chosen
            else None
        )
        if self._focus is not None:
            self._lookup_on = self._focus
        self._unsupported_note = ""  # what a design request asked for that is not modelled
        # What the message asked that code refused (a heating supply under its return): shown on
        # the inputs card, on its field and in words (``refused_on_card``).
        self._refused: Tuple[Dict[str, str], Dict[str, object], List[str]] = ({}, {}, [])
        self._said = ""  # an answer in words for the chat's record (the inputs card's changes)
        self._only_designs: List[str] = []  # a comparison's codes: the only ones a reply names
        self._held: Optional[dict] = None  # the inputs card, kept open over a side question
        for a in session.attachments:
            if self.docs is not None and (session.thread_id, a["name"]) not in self._attached:
                if Path(a["path"]).is_file():
                    self.attach(session, a["path"], a["name"])
        self._index_project(session)
        self._summary = {
            "behaviour": None,
            "asked": [],
            "answer": "",
            "ungrounded": [],
            "dropped": [],
            "verified": None,
            "reasoning": bool(reasoning),
            "reasoning_auto": self._auto,
            "device": device or getattr(self.router, "device", None),
            "decided_by": {},
            "message": message or "",
        }
        yield ev.run_started(session.thread_id, run_id)
        interrupt = None
        try:
            yield from self._load_models()
            if answers is not None and session.pending:
                interrupt = yield from self._resume(session, answers)
            else:
                interrupt = yield from self._turn(session, message or "")
            if (
                self._held is not None
                and session.pending is None
                and len(session.ledger) == ledger_before
                and self._summary.get("behaviour") in HELD_OVER
            ):
                session.pending = self._held  # still open: the side question is answered
            if session.pending is not None:
                session.pending["reasoning"] = self._reasoning  # the answer's run goes on alike
        except Exception as err:  # report, never crash the stream
            self._summary["behaviour"] = "error"
            self._summary["error"] = f"{type(err).__name__}: {err}"
            yield ev.run_error(self._summary["error"])
        seconds = time.perf_counter() - start
        usage = self._usage()
        power = meter.stop() if meter is not None else None
        if power is not None:
            self._summary["energy_wh"] = power["gpu_wh"]
            self._summary["energy_source"] = power["source"]
        self._summary.update(
            reasoning=self._reasoning,
            seconds=round(seconds, 3),
            llm_calls=len(self._calls),
            calls=[f"{c.purpose}: {c.model}" for c in self._calls],
            # Each call's prompt tokens, the guard's estimate and the window (4 Nov).
            call_tokens=[
                [c.purpose, c.prompt_tokens, c.estimated_tokens, c.num_ctx] for c in self._calls
            ],
            prompt_tokens=sum(c.prompt_tokens for c in self._calls),
            output_tokens=sum(c.output_tokens for c in self._calls),
            load_seconds=round(sum(c.load_seconds for c in self._calls), 3),
            prompt_seconds=round(sum(c.prompt_seconds for c in self._calls), 3),
            output_seconds=round(sum(c.output_seconds for c in self._calls), 3),
            tool_calls=self._tools["calls"],
            cache_hits=self._tools["cached"],
            tool_errors=self._tools["failed"],
            left_out=[f"{code}: {why}" for code, why in self._left_out],
            user_turns=session.turns,
            model=getattr(self._fast, "model", None),
            prompt_version=intake.PROMPT_VERSION,
            answer_prompt=answering.ANSWER_PROMPT,
        )
        said = message if message is not None else self._said or "; ".join((answers or {}).values())
        turn = {
            "user": said,
            "reply": self._summary.get("answer", ""),
            "kind": self._summary.get("behaviour") or "",
        }
        session.history = (session.history + [turn])[-HISTORY:]
        try:
            self._note_thread(session, said, turn["reply"], ledger_before)
        except Exception as err:  # noqa: BLE001 - the thread is a help, never a reason to fail
            self._summary["thread_error"] = f"{type(err).__name__}: {err}"
        try:
            chat_state.note_turn(self, session, said, turn["reply"], ledger_before)
        except Exception as err:  # noqa: BLE001 - the state is a help, never a reason to fail
            self._summary["state_error"] = f"{type(err).__name__}: {err}"
        session.last = dict(self._summary)
        if self.session_dir:
            session.save(self.session_dir)
        yield ev.run_finished(
            session.thread_id, run_id, interrupt=interrupt, usage=usage, result=self._summary
        )

    def _turn(self, session: Session, message: str) -> Iterator[dict]:
        if not message.strip():
            # Only spaces: nothing to read, no model call; asked like any unreadable message.
            self._summary.update(intent="other", language="en")
            return (yield from self._unreadable(session, message, "en"))
        yield from self._remember(session, message)
        pending = session.pending
        self._asked_before = bool(pending)  # a question was open when the message came
        if pending and pending.get("kind") in OPEN_KINDS:
            # A typed reply to the question left open ("the cheapest one" after "which design?",
            # "2 GWh" after "by how much?"): the model says whether it answers it (4 Nov).
            answers = yield from self._open_answer(session, pending, message)
            if answers is not None:
                session.pending = pending
                return (yield from self._resume(session, answers))
        if pending and pending.get("kind") == "confirm":
            done, out = yield from self._confirm_reply(session, pending, message)
            if done:
                return out
            # A question asked while the inputs card waits: answered, and the card stays open
            # (a later "go ahead" or the card's Run button still runs it).
            self._held = pending
        named = files.named_in(message, session.project, session.attachments)
        if (
            named
            and len(message.split()) <= 25
            and not lookup.DESIGN_VERBS.search(message)
            and files.asks_to_see(message)
        ):
            # "Show heating_profile.csv": code knows the route, so the reader is not called. A
            # long message is a brief that mentions the files (1 Nov: a 190-word brief opened
            # the demand file and the reply claimed a run that never happened): it is read.
            session.pending = None
            self._summary.update(intent="file", language=intake.language_of(message))
            return (yield from self._open(session, message, named))
        read = yield from self._step(
            "intake",
            "Read the request",
            "model",
            None,
            lambda: intake.read_message(
                message, self._fast, session.project, self._thread_context(session, "short")
            ),
            after=lambda r: {
                "tokens": (r.call.prompt_tokens + r.call.output_tokens) if r.call else 0,
                "relevant": r.relevant,
                "intent": r.intent,
                "screened": r.screened,
                "model": getattr(self._fast, "model", ""),
                "device": self._device_of(self._fast),
            },
        )
        if read.call is not None:
            self._calls.append(read.call)
            yield ev.custom("usage", read.call.as_dict())
        self._summary.update(
            intent=read.intent,
            language=read.language,
            dropped=read.dropped,
            screened=read.screened,
        )
        if self._auto and read.call is not None and not read.unavailable:
            yield from self._think(read, message)
        if read.unavailable:
            model = getattr(self._fast, "model", "the model")
            fix = unavailable_hint(model, read.unavailable)
            yield ev.custom(
                "model_unavailable",
                {
                    "model": model,
                    "error": read.unavailable,
                    "fix": fix,
                    "reason": unavailable_reason(read.unavailable),
                },
            )
            facts = reporter.Facts()
            yield from self._reply(
                "model_unavailable",
                reporter.unavailable_text(model, fix, read.language, facts),
                facts,
                write=False,
            )
            return None
        session.pending = None
        asked = ""
        if session.chosen is not None and not self._asked_before and not read.unavailable:
            # A message whose words name nothing ("3?", "42"): its number sets nothing, whatever
            # the reader called it (5 Nov: "3?" read as a question got "a design with three
            # doublets"). What it may be for is asked, with choices; code decides, not a guess.
            recent = [e for e in session.ledger[-3:] if e.alternative.role == "what_if"]
            item = clarify.bare_message(message, [k for e in recent for k in (e.changes or {})])
            if item is not None and len(item["could_be"]) >= 2:
                return (yield from self._ask_referent(session, item, message))
            if item is not None and not item["could_be"]:
                # A number no setting's range holds ("42"): a message no request can be read
                # from, the one reply for those (the answer prompt calls a bare number unclear).
                return (yield from self._unreadable(session, message, read.language))
        if read.bypass:
            read.bypass, asked = yield from self._screen(message, read)
        if named and not read.bypass and not lookup.DESIGN_VERBS.search(message):
            return (yield from self._open(session, message, named))
        about_files = bool(session.attachments and self.docs and ATTACHED.search(message))
        if about_files and not read.bypass and not lookup.DESIGN_VERBS.search(message):
            hits = yield from self._search(session, message, attached=True)
            facts = reporter.Facts(message)
            return (
                yield from self._reply(
                    "answer",
                    reporter.docs_text(hits, facts, attached=True),
                    facts,
                    passages=hits,
                    draft=False,
                )
            )
        turn = DesignBrief(
            **dict(
                session.brief.model_dump(),
                **{
                    k: (v.model_dump() if hasattr(v, "model_dump") else v)
                    for k, v in read.updates.items()
                },
            )
        )
        if read.bypass:
            facts = reporter.Facts(message)
            text = reporter.reject_text(message, turn, facts, read.cop_claim)
            if asked:  # what was understood, so a later "why?" has something to go on
                text = f"You asked me to {asked[0].lower()}{asked[1:].rstrip('.')}. {text}"
            yield from self._reply("reject", text, facts, write=False)
            return None
        spec = modelgen.find_spec(message) if self.registry is not None and read.relevant else None
        # "Could X cover ...?" needs the model; "explain how X works" is a documentation question.
        offer = None
        if spec is not None and not intake.EXPLAIN_START.search(message):
            if spec.name in self.registry.names():
                yield from self._use_model(session, spec, message)
                return None
            offer = spec
        about_design = bool(session.chosen and ABOUT_DESIGN.search(message))
        new_inputs = {k for k in read.updates if k != "wants_cooling"}
        reading: Optional[parameters.Reading] = None
        # Once a design exists the reasoning model reads what may be a change or a failure even
        # when the small reader called it unrelated ("can we still keep everyone warm if ...").
        reads = read.relevant or (session.chosen is not None and read.intent != "greeting")
        if offer is not None and not (reads and self._reads_parameters(session, read, message)):
            return (yield from self._offer_model(session, offer, turn, read.intent, read.language))
        if reads and self._reads_parameters(session, read, message):
            # Once a design exists, a what-if, a question or "other": a plain "design it" sets
            # nothing, but "would cooling with outside air help?" asks about an option (3 Nov).
            self._asks_change = session.chosen is not None and read.intent in (
                "what_if",
                "question",
                "other",
            )
            reading = yield from self._parameters(session, message)
            for key in self._refused[0]:
                # A value the reasoning reading refused on its merits keeps its value: the small
                # reader's own reading of the same input does not bring it back (5 Nov: "a 4th
                # doublet at 100 m" was refused there and still put the aquifers at 100 m).
                p = parameters.CATALOGUE.get(key)
                names = {(p.field or key) if p is not None else key}
                if key in LIST_ERRORS:  # the depths and the aquifers are one list
                    names |= {"doublet_depths_m", "aquifers"}
                for name in names & set(read.updates) & set(DesignBrief.model_fields):
                    read.updates.pop(name)
                    new_inputs.discard(name)
                    turn = turn.model_copy(update={name: getattr(session.brief, name)})
            if reading.ok and reading.unclear:
                # No request can be read from it, even with the chat ("hmm 70", a sentence cut
                # off): asked, never run, refused or answered as something else (4 Nov).
                return (yield from self._unreadable(session, message, read.language))
            # A request whose number or setting has no referent, or a change without its
            # amount: asked with choices it can run at once (``clarify``).
            settled = yield from self._settle(session, reading, message, read.intent)
            if settled is not None:
                return settled
            if reading.ok and reading.already and not (reading.changes or reading.doublets):
                self._already = list(reading.already)
            if offer is not None and not (
                reading.ok and (reading.changes or reading.doublets) and not reading.unsupported
            ):
                # A component the plant lacks is offered as a new model; one the reading maps
                # onto the plant's own parameters runs ("a seasonal aquifer store" is the
                # HT-ATES store since 3 Nov, not a model to write).
                return (
                    yield from self._offer_model(session, offer, turn, read.intent, read.language)
                )
            if reading.ok and reading.call is not None:
                # The reasoning model's reading names the values asked for; the small reader's
                # guess gave "Which heating return did you assume?" the heat pump's COP (S28).
                # The plain patterns are kept beside it: "what share of the yearly cost is gas"
                # was read as the CO2 by source alone (1 Nov). When it names none, none is
                # looked up but what the words name (4 Nov: "what did I ask first?").
                named = [k for k in lookup.wanted(message) if k not in reading.asks_for]
                read.asks_for = (list(reading.asks_for) + named)[:6]
                self._planner_keys = bool(reading.asks_for)
            if reading.ok and reading.premises:
                # "The boiler gives about a quarter, correct?": without reasoning the reply
                # agreed or only listed the values (1 Nov); with it, it says what is wrong.
                self._premises = list(reading.premises)
                self._premises_said = list(reading.premises)
                if not self._reasoning:
                    yield from self._think_harder("the message states values to check first")
            if reading.ok and reading.origin_of:
                self._origin_of = list(reading.origin_of)
            if reading.ok and reading.show:
                self._show = set(reading.show)
            if reading.ok and reading.on_topic is not None:
                self._on_topic = reading.on_topic
                if reading.on_topic is False and not (
                    reading.changes or reading.failures or reading.designs or reading.doublets
                ):
                    # Not about the project: the small reader's guessed values are not looked
                    # up ("what's the capital of Peru?" got the reservoir's temperature).
                    read.asks_for = []
                    self._planner_keys = False
            if reading.crossed and not (reading.changes or reading.doublets or reading.failures):
                # "What if the cooling return is 16 °C?" over a 20 °C supply: nothing to run, so
                # the reply is the question, not an answer that offers to run it (3 Nov, S67).
                return (yield from self._ask_crossed(reading))
            for quote, why in reading.unread:
                self._warnings.append(f"\n\nNot applied: “{quote}” ({why}).")
            if reading.changes or reading.doublets:
                # "Switch on the network heat losses and a yearly service stop": the service
                # runs; the network needs its length, and on 1 Nov nothing said it was left out.
                for key, (_, quote) in reading.vague.items():
                    name = parameters.CATALOGUE[key].label
                    name = re.sub(r"\s*\(.*\)$", "", name[0].lower() + name[1:])
                    self._warnings.append(
                        f"\n\nNot applied: “{quote}” (no amount for the {name}; tell me the "
                        "value and I will run it)."
                    )
            about = self._focus or session.chosen
            if (
                about is not None
                and not reading.changes
                and not reading.failures
                and (self._origin_of or provenance.asks_origin(message))
                and provenance.draft(about, message, (), self._origin_of)
            ):
                # "Where do the 33 M€ come from?" is a question about the design, whatever else
                # the reading listed (2 Nov: filed as unsupported, "the source of 33 M€").
                return (yield from self._talk(session, read, turn, message, result=about))
            if (
                getattr(reading, "new_design", None)
                and session.chosen is not None
                and not reading.failures
                and not any(st.do == "what_if" for st in reading.steps)
            ):
                # "Another design", in any words: the inputs card, ready to edit, or the run
                # with what the message already changes (3 Nov). Before the unsupported route:
                # "start over with different inputs" was filed as a request the model lacks.
                self._summary.update(intent="design", routed_by="reasoning model")
                kept = {k: v for k, v in reading.changes.items() if k not in parameters.SIZE_KEYS}
                if kept or reading.doublets:
                    brief = parameters.apply(turn, kept, reading.doublets)
                    return (
                        yield from self._continue(session, "design", brief, message, read.language)
                    )
                if reading.vague:
                    # "Use more doublets", "some solar please": a change asked for without an
                    # amount is asked about, not the last search's card again (4 Nov: that card,
                    # run as it was, said "I ran this search already").
                    return (yield from self._ask_amount(session, reading, "design"))
                if reading.unsupported:
                    # Something the model does not have: said so, with what it can vary.
                    return (yield from self._unsupported(session, reading, message))
                last = session.searches[-1] if session.searches else None
                return (
                    yield from self._confirm_inputs(
                        session, "design", turn, message, read.language, again=last
                    )
                )
            if (
                session.chosen
                and reading.unsupported
                and not (set(reading.changes) - {"objective"} or reading.doublets)
                and not reading.failures
                and not {s.do for s in reading.steps} & {"compare", "summary", "uncertainty"}
                # An option asked for without an amount is modelled: asked "by how much?"
                # below (4 Nov: "add a heat store" got "the plant model has no store").
                and not reading.vague
            ):
                # "Add a 5 MW solar PV park ... see what that does to the CO2": nothing the model
                # has changes, whatever steps the planner listed (1 Nov: two design runs).
                return (yield from self._unsupported(session, reading, message))
            if self._picked and (
                not reading.designs or self._strays(session, reading.designs, message)
            ):
                # Picked with @: the designs the question is about, whatever the words say, and
                # with the ones the words name. A design the reader added that is neither goes
                # (5 Nov: A1 and B1 picked, "which is cheaper?" compared W1 with A1).
                named = [
                    e
                    for e in self._written(session, message)
                    if all(e is not p for p in self._picked)
                ]
                reading.designs = [
                    e.alternative.uid or e.alternative.code for e in self._picked + named
                ]
            if session.chosen and (reading.designs or named_in(message, session)):
                if reading.designs:
                    found, _ = reliability.resolve(reading.designs, session)
                    words = [] if self._picked else named_in(message, session)
                    if len(words) >= 2 and len(found) == len(words):
                        # Two or more designs the words name by id or pick ("the cheapest and
                        # the greenest"): code's reading of those names wins over the reader's
                        # (5 Nov: "the greenest" read as the greenest reliable pick).
                        mine = {reporter.design_id(e) for e in words}
                        if {reporter.design_id(e) for e in found} != mine:
                            found = words
                            reading.designs = [
                                e.alternative.uid or e.alternative.code for e in found
                            ]
                else:
                    found = named_in(message, session)
                    reading.designs = [e.alternative.uid or e.alternative.code for e in found]
                if (
                    len(self._picked) >= 2
                    and not reading.changes
                    and not reading.failures
                    and not any(st.do in ("compare", "what_if", "design") for st in reading.steps)
                ):
                    # Two or more picked with @ and a question about them: side by side.
                    reading.steps.insert(0, parameters.Step("compare", message))
                if len(found) == 1 and found[0] is not session.chosen:
                    # "Could they live with the cheapest one?": its values, not the current
                    # design's (1 Nov: A1's 46.8 % was said as the cheapest's).
                    self._lookup_on = found[0]
                if (
                    len(found) >= 2
                    and (read.intent == "compare" or DESIGN_VS.search(message))
                    and not any(st.do == "compare" for st in reading.steps)
                ):
                    # "Compare the cheapest with the most reliable", "how does A1 stack up
                    # against A2?": two designs the words name, set side by side.
                    reading.steps.insert(0, parameters.Step("compare", message))
                why_vs = WHY_LEAD.search(message) and DESIGN_VS.search(message)
                if why_vs and len(found) == 1 and found[0] is not session.chosen:
                    if not any(st.do == "compare" for st in reading.steps):
                        # "Why that one and not the cheapest?": the two side by side.
                        reading.steps.insert(0, parameters.Step("compare", message))
                    me = session.chosen.alternative
                    reading.designs = [me.uid or me.code] + list(reading.designs)
                    self._lookup_on = None
            options = self._which_design(session, reading, message)
            if options:
                # No design by default (3 Nov), but the conversation may say which: "how much
                # capital does it need?" right after a reply about A1 (4 Nov). Asked only when
                # the model cannot tell from the message and the thread.
                meant = yield from self._design_meant(session, message, options)
                if meant is None and reading.premises:
                    # "Earlier you told me the reinjection was 37 °C": a statement to check
                    # against the conversation and the design under discussion, not a question
                    # to ask back (4 Nov: "which design?" and an empty reply).
                    meant = False
                if meant is None:
                    return (yield from self._ask_design(session, read, message, options))
                if meant is not False:  # False: about several designs or none, nothing to ask
                    reading.designs = [meant.alternative.uid or meant.alternative.code]
                    self._picked = [meant]
                    if meant is not session.chosen:
                        self._focus = self._lookup_on = meant
            if (
                session.chosen
                and "min_co2_saving" in reading.changes
                and set(reading.changes) <= SEARCH_FOR
                and not reading.doublets
                and not reading.failures
            ):
                # "At least 50 % less CO2: could they live with the cheapest?": the search under
                # the floor, set against the design named (else the current one).
                self._summary.update(intent="what_if")
                return (yield from self._what_if(session, turn, message, reading))
            if (
                session.chosen is None
                and read.intent in ("question", "explain", "other")
                and reading.ok
                and reading.call is not None
                and not (reading.doublets or reading.failures)
                and not {st.do for st in reading.steps} & {"design", "what_if"}
            ):
                # A question before any design, read for what it states (``_reads_parameters``):
                # answered, its figures checked. Values the planner read as settings are checked
                # as stated, not designed with (4 Nov: "the aquifer sits at 3,500 m and 120 °C,
                # so we can skip the heat pump?" was answered on 120 °C).
                changed = {k: v for k, v in reading.changes.items() if k != "objective"}
                stated = [parameters.label({k: v}) for k, v in changed.items()]
                if stated:
                    self._premises = list(self._premises) + stated
                    self._premises_said = list(self._premises)
                    if not self._reasoning:
                        yield from self._think_harder("the message states values to check first")
                return (yield from self._talk(session, read, turn, message))
            if planned(reading, session, message, len(self._picked)):
                return (yield from self._run_plan(session, turn, message, reading, read.language))
            if (
                session.chosen is None
                and read.intent in ("what_if", "design")
                and reading.ok
                and reading.call is not None
                and (reading.premises or ("?" in message and not new_inputs))
                and not (reading.changes or reading.doublets or reading.failures)
                and {st.do for st in reading.steps} <= {"answer"}
            ):
                # Before a design, a question that states facts ("the aquifer sits at 3,500 m,
                # so we can skip the heat pump?") is answered and its statements checked, not
                # run as a design (4 Nov: it opened the inputs card). So is a question the
                # planner read nothing to run from ("we can drill up to five doublets, can't
                # we?" opened the card, and the next turn's run answered it, a turn late): the
                # answerer may still ask for the design run it judges the question wants.
                return (yield from self._talk(session, read, turn, message))
            if not session.chosen and read.intent in ("what_if", "question", "explain", "other"):
                if reading.changes or reading.doublets:
                    read.intent = "design"  # "what if the return were 50 °C?" with no design yet
            if read.intent in ("design", "compare") and (reading.changes or reading.doublets):
                kept = {k: v for k, v in reading.changes.items() if k not in parameters.SIZE_KEYS}
                turn = parameters.apply(turn, kept, reading.doublets)
                new_inputs |= set(kept) | ({"doublets"} if reading.doublets else set())
            elif session.chosen and read.intent not in ("design", "compare"):
                only_objective = reading.unsupported and set(reading.changes) <= {"objective"}
                if (reading.changes or reading.doublets) and not (
                    only_objective and not reading.doublets
                ):
                    self._summary.update(intent="what_if")
                    return (yield from self._what_if(session, turn, message, reading))
                if reading.vague:
                    return (yield from self._ask_amount(session, reading, "what_if"))
                if reading.unsupported:
                    return (yield from self._unsupported(session, reading, message))
            if (
                session.chosen
                and read.intent in ("design", "compare")
                and reading.unsupported
                and not reading.vague  # modelled, with no amount: asked below
                # What "best" means alone is no change to run with a request the model does
                # not cover ("… and see what that does to the CO2" read as lowest CO2).
                and not (
                    set(reading.changes) - {"objective"}
                    or reading.doublets
                    or new_inputs - {"objective"}
                )
            ):
                # "Add a 5 MW solar PV park": not in the model, so say so; a new search would
                # replace the design the user just asked for (1 Nov) and answer nothing.
                return (yield from self._unsupported(session, reading, message))
            if read.intent in ("design", "compare") and reading.vague and not reading.changes:
                return (yield from self._ask_amount(session, reading, "design"))
        if session.chosen and WHY_START.search(message):
            # "Why did you drill to 3,000 m when the aquifer is at 2,500 m?" names depths but
            # asks about the design that exists: no new search for them.
            new_inputs -= {"doublet_depths_m", "n_doublets", "excluded"}
            for key in ("doublet_depths_m", "n_doublets", "excluded"):
                read.updates.pop(key, None)
            turn = turn.model_copy(
                update={
                    k: getattr(session.brief, k)
                    for k in ("doublet_depths_m", "n_doublets", "excluded")
                }
            )
            if not new_inputs:
                return (
                    yield from self._talk(
                        session, read, turn, message, result=self._focus or session.chosen
                    )
                )
        if session.chosen and not new_inputs and ABOUT_RESULT.search(message):
            return (
                yield from self._talk(
                    session, read, turn, message, result=self._focus or session.chosen
                )
            )
        if (
            session.chosen
            and read.intent == "question"
            and read.asks_for
            and set(read.asks_for) <= lookup.PROJECT_KEYS
            and answering.DESIGN_TALK.search(message)
        ):
            # "Why do both doublets have the same settings?" read as a lookup of the reservoir:
            # the design's context answers it, not a sheet of the project's values.
            read.asks_for = []
            return (
                yield from self._talk(
                    session, read, turn, message, result=self._focus or session.chosen
                )
            )
        if session.chosen and read.intent == "what_if":
            # A what-if that changes nothing the model has ("why does the design show 102?"
            # read as one): a question about the design.
            return (
                yield from self._talk(
                    session, read, turn, message, result=self._focus or session.chosen
                )
            )
        shown = self._candidate_asked(session, message)
        if shown is not None:
            return (yield from self._show_candidate(session, shown, message))
        if session.chosen and read.intent in ("design", "compare") and not new_inputs:
            # A design exists and nothing new is asked for: a larger model says whether this
            # is a new run ("another attempt") or a question about what exists.
            if not (yield from self._route(session, message)):
                last = session.searches[-1] if session.searches else None
                if (
                    read.intent == "design"
                    and "?" not in message
                    and last is not None
                    and engine.same_search(last["brief"], turn)
                    # A statement to check is no request ("earlier you told me ... 37 °C").
                    and not (reading is not None and reading.premises)
                ):
                    # "Do another design attempt" is a request, not a question, and changes
                    # nothing (S35, 1 Nov: the reply claimed a fresh search had run): the inputs
                    # card, ready to edit, says the same inputs give the same designs.
                    return (
                        yield from self._confirm_inputs(
                            session, "design", turn, message, read.language, again=last
                        )
                    )
                self._summary.update(intent="question", routed_by="reasoning model")
                return (
                    yield from self._talk(
                        session, read, turn, message, result=self._focus or session.chosen
                    )
                )
        if (
            session.chosen is not None
            and reading is not None
            and reading.ok
            and (reading.premises or reading.about_design)
            and not (reading.changes or reading.doublets or reading.failures)
            and not reading.new_design
            and not {st.do for st in reading.steps} & {"design", "what_if", "compare"}
        ):
            # "It has 2 doublets, hasn't it?": a statement about the design to check, not a
            # request for a 2-doublet design, whatever the small reader made of "2 doublets"
            # (4 Nov: a new search ran). The planner read no change and the reply needs one
            # existing design (``read_needs``), so it is answered.
            return (yield from self._talk(session, read, turn, message))
        if read.relevant and (
            read.intent in ("design", "compare", "what_if")
            or (read.intent == "explain" and about_design)
        ):
            if reading is not None and reading.unsupported:
                self._unsupported_note = reporter.unsupported_note(reading.unsupported)
            return (yield from self._continue(session, read.intent, turn, message, read.language))
        return (yield from self._talk(session, read, turn, message))

    def _ask_crossed(self, reading: "parameters.Reading") -> Iterator[dict]:
        """Say which values cross their pair (a return across its supply) and ask for others.

        Code checks the values (``parameters._crossed``); nothing is run with them.
        """
        facts = reporter.Facts(self._message)
        lines = [f"- “{quote}”: {facts.put(why)}" for quote, why in reading.unread]
        text = "I did not run this, because the values cannot work together:\n" + "\n".join(lines)
        self._summary.update(asked=["value"], crossed=list(reading.crossed))
        yield from self._reply("clarify", text, facts, write=False)
        return None

    def _reads_parameters(self, session: Session, read: intake.IntakeResult, message: str) -> bool:
        """Return whether to ask the reasoning model what a message sets, changes or asks for.

        Every design, comparison and what-if; and, once a design exists, every question: the
        model's plan decides whether it is a change, a failure, a comparison, a decision summary,
        the uncertainty or a plain answer. Never a "why ..." question about the design: it gets
        each choice against its best alternative from code.
        """
        # Only a question that opens with "why" skips it ("why did you drill to 3,000 m?"):
        # "which return did you assume, and why does it matter?" asks for a value first.
        # A why that names another design ("why that one and not the cheapest?") is read: the
        # planner sets the two side by side (1 Nov: the reply denied there was a recommendation).
        why = WHY_LEAD.search(message) and not (
            session.chosen and names_designs(message, session) >= 1 and DESIGN_VS.search(message)
        )
        if read.intent in ("design", "compare", "what_if"):
            return not (session.chosen and why)
        if session.chosen is None and read.relevant and intake.numbers_in(message):
            # Before a design, a question with figures may state the project's facts wrongly
            # ("the district needs about 200 GWh, right?"): the planner lists them (4 Nov).
            return read.intent in ("question", "explain", "other")
        # "About" read by the small model (not matched by pattern) after a design is read too:
        # with the thread, "show me the designs you tried" was labelled about (4 Nov).
        asks = ("question", "explain", "other") + (("about",) if not read.screened else ())
        return bool(session.chosen and read.intent in asks and not why)

    def _parameters(
        self,
        session: Session,
        message: str,
        brief: Optional[DesignBrief] = None,
        card: bool = False,
    ):
        """Ask the reasoning model what the message sets or changes; code checks each change.

        ``card``: a typed reply to the inputs card. A change to the aquifers that drops some
        there and names new ones is then read once more for add or replace (``list_op``), and
        an add keeps every aquifer there (``parameters.as_added``).
        """
        deep = self._deep()
        base = session.chosen
        brief = brief or (base.brief if base is not None else session.brief)
        rules = engine.rules_for(brief)
        prices = engine.prices_for(session.assumptions, brief)
        alt = base.alternative if base is not None else None
        now = parameters.values_now(brief, alt, rules, prices)
        if base is not None and base.year.stop_ranges:  # where the doublets stop now
            now["stop_ranges"] = base.year.stop_ranges
        design = f"{alt.code}, {alt.name}" if alt is not None else ""
        designs = designs_text(session)
        thread = self._thread_context(session, "reading")
        short = self._thread_context(session, "short")
        if session.chosen is not None:  # a follow-up that names no design: the chat's state
            cpu = self._cpu()
            thread = self._with_state(session, thread, message, 450 if cpu else 900)
            short = self._with_state(session, short, message, 350 if cpu else 700)
        reading = yield from self._step(
            "parameters",
            "Read what the message asks: changes, failures, designs, steps",
            "model",
            None,
            lambda: parameters.read(message, deep, now, design, designs, thread),
            after=lambda r: {
                "decided_by": "model" if r.call is not None and r.ok else "rules",
                "changes": r.changes,
                "doublets": [d.model_dump() for d in r.doublets],
                "unsupported": r.unsupported,
                "dropped": r.dropped,
                "failures": [f.__dict__ for f in r.failures],
                "designs": r.designs,
                "steps": [x.do for x in r.steps],
                "second_look": r.second_look,
                "model": getattr(deep, "model", ""),
                "device": self._device_of(deep),
            },
        )
        # The reading's call, and a second look's when the first reading was in doubt.
        for call in [reading.call] + list(reading.extra_calls):
            if call is not None:
                self._calls.append(call)
                yield ev.custom("usage", call.as_dict())
        if parameters.wants_options(reading, self._asks_change):
            # Something filed as not modelled, a change dropped or a what-if with nothing to
            # change: the plant's options read again on their own (3 Nov: "a 2 GWh buffer tank"
            # was not modelled, "winter electricity dirtier than summer's" changed nothing).
            extra, call = yield from self._step(
                "options",
                "Read again which of the plant's options the message sets",
                "model",
                None,
                # No thread: the plant options are the message's own (4 Nov: "can it lose any
                # one unit?" was read, with the chat before it, as switching the service off).
                lambda: parameters.read_options(message, deep, now),
                after=lambda r: {
                    "decided_by": "model" if r[0].ok else "rules",
                    "changes": r[0].changes,
                    "vague": list(r[0].vague),
                    "dropped": r[0].dropped,
                    "model": getattr(deep, "model", ""),
                    "device": self._device_of(deep),
                },
            )
            if call is not None:
                self._calls.append(call)
                yield ev.custom("usage", call.as_dict())
            if extra.ok:
                parameters.merge_options(reading, extra)
        listed = parameters.list_drops_and_adds(reading, now) if card else None
        if listed is not None:
            op, call = yield from self._step(
                "list_op",
                "Read whether the message adds aquifers or replaces them",
                "model",
                None,
                lambda: parameters.list_op(
                    message, aquifers.now_text(now.get("aquifers") or []), deep, short
                ),
                after=lambda r: {
                    "decided_by": "model" if r[1] is not None and r[1].ok else "rules",
                    "op": r[0],
                    "model": getattr(deep, "model", ""),
                    "device": self._device_of(deep),
                },
            )
            if call is not None:
                self._calls.append(call)
                yield ev.custom("usage", call.as_dict())
            if op == "add":
                parameters.as_added(reading, now, listed, message)
        if session.chosen is not None and not reading.unclear:
            # What the reply needs, its own short call (3 Nov): a new design run, one existing
            # design, designs side by side, the search behind one, or none in particular.
            needs, call = yield from self._step(
                "needs",
                "Read what the reply needs: a new design, one design, or none",
                "model",
                None,
                lambda: parameters.read_needs(message, deep, designs, short),
                after=lambda r: {
                    "decided_by": "model" if r[0] else "rules",
                    "needs": r[0],
                    "model": getattr(deep, "model", ""),
                    "device": self._device_of(deep),
                },
            )
            if call is not None:
                self._calls.append(call)
                yield ev.custom("usage", call.as_dict())
            if needs:
                parameters.set_needs(reading, needs)
                if reading.show:
                    self._show = set(reading.show)
        self._refused = refused_on_card(reading)
        self._summary["parameters"] = {
            **({"unclear": True} if reading.unclear else {}),
            "changes": reading.changes,
            "doublets": len(reading.doublets),
            "unsupported": reading.unsupported,
            "dropped": reading.dropped,
            "failures": [f.unit for f in reading.failures],
            "designs": reading.designs,
            "steps": [x.do for x in reading.steps],
        }
        if reading.second_look is not None:  # read again: why, the amounts, which was kept
            self._summary["parameters"]["second_look"] = reading.second_look
        if reading.examples:  # worked examples in the prompt (DIOSCURI_EXAMPLES=1)
            self._summary["parameters"]["examples"] = reading.examples
        return reading

    def _unreadable(self, session: Session, message: str, language: str) -> Iterator[dict]:
        """Say what could not be read and ask what the user wants; nothing runs or changes.

        One reply for every message no request can be read from (cut off, garbled, a bare
        number, empty), whichever reading found it so: the planner (``Reading.unclear``) or the
        answerer (kind ``unclear``). On 4 Nov such messages were refused as off-topic, called
        nonsense, answered, or run ("hmm 70" ran a 70 MWh store). The options are complete
        requests: the tested follow-ups of the design under discussion, else the standard ones.
        """
        language = language if language in reporter.REFUSE_SUGGESTIONS else "en"
        text = reporter.unreadable_text(message, language)
        about = self._focus or session.chosen
        asked = [h.get("user", "") for h in session.history]
        options = (
            suggest.pick(session, about, (), "", language, asked) if about is not None else None
        )
        options = list(options or reporter.REFUSE_SUGGESTIONS[language])
        reply = answering.Reply(
            text, kind="clarify", options=options, understood="a message I could not read"
        )
        yield from self._step(
            "ask",
            "Ask what the message means",
            "ask",
            None,
            lambda: None,
            after=lambda _: {"decided_by": "rules", "reason": "no readable request"},
        )
        yield from ev.text_message(uuid.uuid4().hex[:10], text)
        self._summary.update(behaviour="clarify", answer=text, unreadable=True)
        if self._held is not None:
            return None  # the inputs card is open: its buttons stay the choice (``HELD_OVER``)
        return (yield from self._ask_choice(reply))

    def _ask_amount(self, session: Session, reading: parameters.Reading, kind: str):
        """Ask how much, when a change was asked for without an amount ("a lower return")."""
        key, (guess, quote) = next(iter(reading.vague.items()))
        p = parameters.CATALOGUE[key]
        base = session.chosen
        brief = base.brief if base is not None else session.brief
        now = parameters.values_now(
            brief,
            base.alternative if base is not None else None,
            engine.rules_for(brief),
            engine.prices_for(session.assumptions, brief),
        ).get(key)
        if not isinstance(now, (int, float)):
            now = guess  # not set yet (the search's own range of doublets): the model's guess
        name = re.sub(r"\s*\(.*\)$", "", p.label[0].lower() + p.label[1:])
        unit = "" if p.unit in ("", "x", "fraction") else f" {p.unit}"
        options = []
        for v in parameters.amount_options(key, guess, float(now), quote):
            shown = f"×{v:g}" if p.unit == "x" else f"{v:g}{unit}"
            options.append(
                f"What if the {name} were {shown}?"
                if kind == "what_if"
                else f"Design with the {name} at {shown}"
            )
        text = (
            f"By how much? The {name} is {float(now):g}{unit} now. Pick one, or type the value "
            "you have in mind."
        )
        reply = answering.Reply(
            text, kind="clarify", options=options, understood=f"{name}: how much"
        )
        yield from ev.text_message(uuid.uuid4().hex[:10], text)
        self._summary.update(behaviour="clarify", answer=text, vague=sorted(reading.vague))
        return (yield from self._ask_choice(reply))

    def _unsupported(
        self, session: Session, reading: parameters.Reading, message: str
    ) -> Iterator[dict]:
        """Say plainly that the model cannot vary what was asked, and what it can vary."""
        facts = reporter.Facts(message)
        text = (
            capabilities.unsupported_text(reading.unsupported, session.chosen)
            if capabilities.on()
            else reporter.unsupported_text(reading.unsupported, session.chosen)
        )
        self._summary.update(behaviour="answer", unsupported=reading.unsupported)
        hits: List[object] = []
        if (
            self.docs is not None
            and session.attachments
            and (ATTACHED.search(message) or FILE_NAME.search(message))
        ):
            # "Summarise the attached datasheet and size an absorption chiller from it": the
            # file is read and summarised, beside what the model cannot vary (4 Nov: the reply
            # said no file was provided).
            hits = yield from self._search(session, message, attached=True)
            if hits:  # what the file says first, then what the model cannot vary
                text = reporter.docs_text(hits, facts, attached=True) + "\n\n" + text
        yield from self._reply(
            "answer", text, facts, entry=session.chosen, card_view="none", passages=hits
        )
        return None

    def _confirmed(self, session: Session) -> bool:
        """Return True when the user confirmed this project's inputs in this conversation."""
        return session.confirmed.get(session.project.id) == project_fingerprint(session.project)

    def _confirm_inputs(
        self,
        session: Session,
        intent: str,
        turn: DesignBrief,
        message: str,
        language: str,
        changed: Sequence[str] = (),
        errors: Optional[Dict[str, str]] = None,
        asked: Optional[Dict[str, object]] = None,
        again: Optional[dict] = None,
        notice: Optional[dict] = None,
    ) -> Iterator[dict]:
        """Show what the design will use, read from the project or assumed, and ask to run it.

        ``errors`` and ``asked``: the card's own changes code refused (why, by key, and the
        values the user gave), shown again on their fields. ``again``: the earlier search these
        inputs already ran ("another design"): the card opens ready to edit, and says so.
        ``notice``: what a typed reply to the card did (a change refused, nothing changed; or
        the inputs put back to the project's defaults), said at the card's top and in the text.
        """
        rows = yield from self._step(
            "inputs",
            "Gather the inputs to confirm",
            "tool",
            "inputs(project, brief)",
            lambda: reporter.inputs_rows(session.project, turn),
            after=lambda r: {"rows": len(r), "assumed": sum(x["kind"] == "assumed" for x in r)},
        )
        note = getattr(self, "_unsupported_note", "")
        if note:
            rows.append(
                {
                    "group": "Your request",
                    "label": "Not modelled",
                    "value": note,
                    "source": "your message",
                    "kind": "asked",
                }
            )
        touched = set(reporter.changed_rows(changed))
        for r in rows:
            r["changed"] = r["label"] in touched
        refused_errors, refused_asked, refused_notes = self._refused
        card_edits.with_fields(rows, turn, session.project, changed)  # the card's form
        if errors is None and refused_errors:
            # The message's own values code refused, shown on their fields like a card edit
            # refused (4 Nov: "heated temperature should be 50" was dropped without a word,
            # the heating return of 60 °C being above it).
            errors, asked = dict(refused_errors), dict(refused_asked)
            # A refusal no box of the card holds (the depths to try, the aquifers' list), or
            # one whose value no box can show, is said at the card's top instead: on no field
            # it blocked the run with nothing to fix (5 Nov: "Aquifer depths ... [100]").
            boxes = {f["key"] for r in rows for f in r.get("fields") or []} - set(LIST_ERRORS)
            loose = {k: v for k, v in errors.items() if k not in boxes}
            if loose:
                notes = dict(zip(refused_errors, refused_notes))
                refused_notes = [n for k, n in notes.items() if k not in loose]
                refused_errors = {k: v for k, v in refused_errors.items() if k not in loose}
                errors = dict(refused_errors)
                asked = {k: v for k, v in (asked or {}).items() if k not in loose}
                lines = card_edits.refused_lines(loose, refused_asked, [], turn)
                if notice is None and lines:
                    notice = card_edits.refused_notice(lines, turn, title="Not taken")
        session.pending = {
            "kind": "confirm",
            "intent": intent,
            "brief": turn.model_dump(),
            "message": message,
            "language": language,
            "changed": list(changed),  # the rows that run stay marked (``_apply_card``)
        }
        text = reporter.inputs_text(rows)
        if refused_notes and refused_errors and errors == refused_errors:
            text = " ".join(refused_notes) + "\n\n" + text
        if notice:
            # After the card's own head, so the card keeps its title; the chat's thread has it.
            head, _, table = text.partition("\n\n")
            words = " ".join([str(notice["title"]) + "."] + list(notice.get("lines") or []))
            text = f"{head}\n\n{words} {notice.get('offer', '')}".rstrip() + "\n\n" + table
        if again is not None:  # after the card's own head ("Before I run the design ...")
            text = text + "\n\n" + reporter.again_text(again)
        options = [reporter.RUN_OPTION, reporter.CHANGE_OPTION]
        yield from ev.text_message(uuid.uuid4().hex[:10], text)
        # The switches (network losses, Maintenance, plant options, the brine's gas), each in
        # the row and page it belongs to.
        toggles = card_edits.toggles(turn)
        yield ev.custom(
            "confirm_inputs",
            {
                "rows": rows,
                "changed": list(changed),
                "options": options,
                "kinds": reporter.KINDS,
                "toggles": toggles,
                "errors": dict(errors or {}),
                "asked": dict(asked or {}),
                # The card's pages, its warnings for the values now, and the numbers it works
                # out consequences from as the user types (card_edits).
                "pages": [{"id": k, "title": t} for k, t in card_edits.PAGES],
                "warnings": card_edits.warnings(rows),
                "context": card_edits.context(turn),
                # What the user set (in the message, or earlier): marked, with what it affects.
                "yours": card_edits.yours(turn),
                "again": (
                    {"search": again.get("id"), "label": again.get("label", "")} if again else None
                ),
                # What a typed reply did (refused, or reset), and whether anything differs from
                # the project's own values (the card's "Reset to defaults").
                "notice": notice,
                "at_defaults": card_edits.at_defaults(turn),
            },
        )
        question = Question(
            id="confirm",
            label="Run the design with these inputs?",
            hint='Or type what to change, for example "a 50 °C heating return".',
            options=options,
        )
        yield ev.custom(
            "clarification",
            {"kind": "confirm", "intro": text, "questions": [question.model_dump()]},
        )
        self._summary.update(behaviour="clarify", asked=["confirm"], answer=text)
        return "confirm"

    def _open_answer(self, session: Session, pending: dict, message: str) -> Iterator[dict]:
        """Return the answers a typed reply gives to the open question, or None.

        The model reads the reply against the question and its options (``parameters.
        answers_question``); code maps its pick onto what the question's buttons send.
        """
        kind = str(pending.get("kind"))
        options = [str(o) for o in pending.get("options") or []]
        last = session.history[-1].get("reply", "") if session.history else ""
        question = thread_flat(last, 300) or "Which of these do you mean?"
        inputs: List[Question] = []
        if kind == "which_design":
            question = "Which design is your question about?"
        elif kind == "decision":
            options = [str(c[0]) for c in pending.get("choices") or []]
        elif kind == "inputs":
            brief = DesignBrief(**pending["brief"])
            inputs = intake.missing_inputs(brief, session.project)
            if len(inputs) != 1:
                return None  # several questions in one card: answered on the card
            question, options = inputs[0].label, list(inputs[0].options or [])
        deep = self._deep()
        found, call = yield from self._step(
            "open_question",
            "Read whether the reply answers the open question",
            "model",
            None,
            lambda: parameters.answers_question(
                message, question, options, deep, self._thread_context(session, "short")
            ),
            after=lambda r: {
                "decided_by": "model" if r[1] is not None and r[1].ok else "rules",
                "answers": r[0] is not None,
                "option": r[0][0] if r[0] else 0,
                "model": getattr(deep, "model", ""),
                "device": self._device_of(deep),
            },
        )
        if call is not None:
            self._calls.append(call)
            yield ev.custom("usage", call.as_dict())
        if found is None:
            return None
        option, value = found
        picked = options[option - 1] if option else ""
        if kind == "which_design":
            return {"design": picked or value}
        if kind == "choice":
            # Its own words answer the question the original message raised: both go on.
            return {"choice": picked or f"{pending.get('message', '')} ({value})".strip()}
        if kind == "inputs":
            return {inputs[0].id: picked or value}
        if not picked:
            return None  # a decision or an offer: only its own options run anything
        return {"decision" if kind == "decision" else kind: picked}

    def _confirm_reply(self, session: Session, pending: dict, message: str):
        """Read a typed reply to the inputs card: run, change an input, or something else.

        Returns
        -------
        tuple of (bool, object)
            Whether the reply was handled here, and the run's interrupt.
        """
        deep = self._deep()
        # The card's own button sends its label: nothing to read (typed replies go to the model).
        button = message.strip() == reporter.RUN_OPTION
        decision, call = yield from self._step(
            "confirm",
            "Read the reply to the inputs",
            "model",
            None,
            lambda: (
                ("run", None)
                if button
                else parameters.confirm_decision(
                    message, deep, self._thread_context(session, "short")
                )
            ),
            after=lambda r: {
                "decision": r[0],
                "decided_by": "rules" if button else "model",
                "model": getattr(deep, "model", ""),
                "device": self._device_of(deep),
            },
        )
        if call is not None:
            self._calls.append(call)
            yield ev.custom("usage", call.as_dict())
        brief = DesignBrief(**pending["brief"])
        if decision == "reset":
            # "Get back to the defaults", in any words (the model reads them): the card again
            # with the project's own values, and nothing runs (5 Nov: the reply was read as
            # nothing to change, and the design then ran with an aquifer at 100 m).
            return True, (yield from self._reset_inputs(session, pending))
        if decision == "run":
            session.pending = None
            session.confirmed[session.project.id] = project_fingerprint(session.project)
            self._message = pending["message"]  # the request, not the "yes" that confirmed it
            self._summary.update(intent=pending["intent"])
            if pending.get("plan"):
                out = yield from self._run_plan(
                    session,
                    brief,
                    pending["message"],
                    plan_from(pending["plan"]),
                    pending["language"],
                    confirmed=True,
                )
                return True, out
            out = yield from self._continue(
                session,
                pending["intent"],
                brief,
                pending["message"],
                pending["language"],
                confirmed=True,
            )
            return True, out
        if decision == "change":
            reading = yield from self._parameters(session, message, brief, card=True)
            refused, asked, _ = self._refused
            # The reading's own slips do not hold back what it read right (as before).
            merits = [u for u in reading.unread if not parameters.misread(u[1])]
            lines = card_edits.refused_lines(refused, asked, merits, brief)
            if lines:
                # Something the reply asks for is refused (outside its range, more aquifers or
                # doublets than allowed, values that cannot work together): nothing of it is
                # applied, the card stays as it was and says why (5 Nov: "add a 4th doublet at
                # 100 m" left one aquifer at 100 m on the card, and it later ran).
                self._refused = ({}, {}, [])
                self._summary.update(refused=lines)
                out = yield from self._confirm_inputs(
                    session,
                    pending["intent"],
                    brief,
                    pending["message"],
                    pending["language"],
                    changed=list(pending.get("changed") or []),
                    errors={},
                    notice=card_edits.refused_notice(lines, brief),
                )
                for key in ("plan", "reasoning"):
                    if pending.get(key) and session.pending is not None:
                        session.pending[key] = pending[key]  # the request's steps still wait
                return True, out
            if reading.changes or reading.doublets:
                kept = {k: v for k, v in reading.changes.items() if k not in parameters.SIZE_KEYS}
                brief = parameters.apply(brief, kept, reading.doublets)
                self._unsupported_note = reporter.unsupported_note(reading.unsupported)
                out = yield from self._confirm_inputs(
                    session,
                    pending["intent"],
                    brief,
                    pending["message"],
                    pending["language"],
                    changed=sorted(kept) + (["doublets"] if reading.doublets else []),
                )
                if pending.get("plan") and session.pending is not None:
                    session.pending["plan"] = pending["plan"]  # the request's steps still wait
                return True, out
        return False, None

    def _reset_inputs(self, session: Session, pending: dict) -> Iterator[dict]:
        """Put the inputs card back to the project's defaults and show it again; nothing runs.

        Every change the user made, in the chat or on the card, and not yet run goes, so a
        later Run can only use what the card then shows (``card_edits.defaults``).
        """
        before = DesignBrief(**pending["brief"])
        after = yield from self._step(
            "reset",
            "Put the inputs back to the project's defaults",
            "tool",
            "defaults(brief)",
            lambda: card_edits.defaults(before, session.project),
            after=lambda b: {"decided_by": "rules", "at_defaults": card_edits.at_defaults(b)},
        )
        self._refused = ({}, {}, [])
        self._unsupported_note = ""
        self._said = reporter.RESET_OPTION
        self._summary.update(reset=True)
        out = yield from self._confirm_inputs(
            session,
            pending["intent"],
            after,
            pending["message"],
            pending["language"],
            errors={},
            notice=card_edits.reset_notice(before, after),
        )
        for key in ("plan", "reasoning"):
            if pending.get(key) and session.pending is not None:
                session.pending[key] = pending[key]  # the request's steps still wait
        return out

    def _apply_card(self, session: Session, pending: dict, brief: DesignBrief, answers: dict):
        """Apply the inputs card's own changes and stop dates, each checked by code.

        Returns (through ``yield from``) the brief to run with, or None when something was
        refused: then the card is shown again with the reasons on the fields and nothing runs.
        """
        edit = yield from self._step(
            "edits",
            "Check your changes to the inputs",
            "tool",
            "check(changes)",
            lambda: card_edits.read(answers, brief, session.project),
            after=lambda e: {
                "changed": list(e.changed),
                "refused": sorted(e.errors),
                "decided_by": "rules",
            },
        )
        words = card_edits.changed_words(edit.changed, edit.brief)
        self._said = reporter.RUN_OPTION + (f" ({words})" if words else "")
        # What changed since the first card (an earlier card may have taken some already).
        changed = sorted(set(edit.changed) | set(pending.get("changed") or []))
        if edit.errors:
            yield from self._confirm_inputs(
                session,
                pending["intent"],
                edit.brief,
                pending["message"],
                pending["language"],
                changed=changed,
                errors=edit.errors,
                asked=edit.asked,
            )
            for key in ("plan", "reasoning"):
                if pending.get(key) and session.pending is not None:
                    session.pending[key] = pending[key]  # the request's steps still wait
            return None
        if changed:
            # The rows as they now run, the changed ones marked (the card folds to these).
            rows = reporter.inputs_rows(session.project, edit.brief)
            touched = set(reporter.changed_rows(changed))
            for r in rows:
                r["changed"] = r["label"] in touched
            card_edits.with_fields(rows, edit.brief, session.project, changed)
            yield ev.custom(
                "confirm_inputs",
                {
                    "rows": rows,
                    "changed": changed,
                    "options": [reporter.RUN_OPTION, reporter.CHANGE_OPTION],
                    "kinds": reporter.KINDS,
                    "applied": True,
                },
            )
        return edit.brief

    def _candidate_asked(self, session: Session, message: str) -> Optional[LedgerEntry]:
        """Return the search candidate a message asks to see in full, if it names one.

        "Show the runner-up, 1D-BO-EC@3500, in full": the candidate is in the last search but
        not among the chat's designs yet.
        """
        codes = {e.alternative.code for e in session.ledger}
        if not SHOW_WORDS.search(message):
            return None
        for m in DESIGN_CODE.finditer(message):
            code = m.group(0)
            if code in codes:
                continue
            for e in session.candidates or []:
                if e.alternative.code == code and e.alternative.role != "same":
                    return e
        if RUNNER_UP.search(message) and session.chosen is not None:
            pick = session.chosen.alternative.code
            mine = reporter.lineage(pick, session.candidates or [])
            valid = [
                e
                for e in session.candidates or []
                if e.alternative.role == "candidate"
                and e.alternative.code not in codes
                and not (e.alternative.stage == 2 and e.alternative.parent in mine)
            ]
            valid.sort(key=lambda e: e.economics.lcoe_eur_per_mwh or 0.0)
            return valid[0] if valid else None
        return None

    def _show_candidate(self, session: Session, entry: LedgerEntry, message: str) -> Iterator[dict]:
        """Add a candidate of the last search to the chat's designs and show its card."""
        yield from self._step(
            "plan",
            f"Take {entry.alternative.code} from the last search",
            "plan",
            f"candidates.get({entry.alternative.code!r})",
            lambda: entry,
            after=lambda e: {"decided_by": "rules", "reason": e.alternative.reason or "asked for"},
        )
        full = engine.reprice(entry, session.assumptions or {})  # with its daily series
        full.alternative.attempt = entry.alternative.attempt
        session.ledger.append(full)
        facts = reporter.Facts(message)
        yield from self._reply(
            "design",
            reporter.design_answer(full, [], facts),
            facts,
            entry=full,
            suggestions=reporter.challenge_suggestions(full),
        )
        return None

    def _route(self, session: Session, message: str) -> Iterator[dict]:
        """Ask the reasoning model whether a message the reader did not route wants a design."""
        deep = self._deep()
        made = ", ".join(e.alternative.code for e in session.ledger[-3:]) or "none"
        yes, call = yield from self._step(
            "route",
            "Check whether it asks for a design",
            "model",
            None,
            lambda: intake.wants_design(
                message, deep, made, self._thread_context(session, "short")
            ),
            after=lambda r: {
                "decided_by": "model" if r[1] is not None and r[1].ok else "rules",
                "run_design": r[0],
                "model": getattr(deep, "model", ""),
                "device": self._device_of(deep),
            },
        )
        if call is not None:
            self._calls.append(call)
            yield ev.custom("usage", call.as_dict())
        return yes

    def _same_search(
        self, session: Session, last: dict, brief: DesignBrief, message: str
    ) -> Iterator[dict]:
        """Say the search asked for was run already, and offer what could change.

        The search is deterministic, so running it again gives the same design; the reply says
        that and asks what to try instead, as a choice of complete requests.
        """
        yield from self._step(
            "plan",
            "Same inputs as the last search",
            "plan",
            f"searches.get({last['id']!r})",
            lambda: last,
            after=lambda s: {
                "decided_by": "rules",
                "reason": "same brief: same result",
                "search": s["id"],
            },
        )
        chosen = session.chosen
        mine = reporter.lineage(chosen.alternative.code, session.candidates)
        valid = [
            e
            for e in session.candidates
            if e.alternative.role == "candidate"
            and e.alternative.code != chosen.alternative.code
            and not (e.alternative.stage == 2 and e.alternative.parent in mine)
        ]
        valid.sort(key=lambda e: e.economics.lcoe_eur_per_mwh or 0.0)
        runner = valid[0] if valid else None
        options = []
        if runner is not None:
            options.append(f"Show the runner-up, {runner.alternative.code}, in full")
        options.append(
            "Which design gives the lowest CO2?"
            if brief.objective == "cost"
            else "Which design is cheapest?"
        )
        rules = engine.rules_for(brief)
        if any(d != rules.reservoir_depth_m for d in aquifers.search_depths(brief, rules)):
            options.append(
                f"Design with wells at {rules.reservoir_depth_m:,.0f} m only, the known aquifer"
            )
        else:
            deeper = engine.projects.assumed_depths(rules)[1:]
            options.append(
                "Design again, also trying an assumed deeper aquifer at "
                + " or ".join(f"{d:,.0f} m" for d in deeper)
            )
        if "boiler" not in brief.excluded:
            options.append("Design without gas boilers")
        elif "heat_pump" not in brief.excluded:
            options.append("Design without heat pumps")
        facts = reporter.Facts(message)
        text = reporter.same_search_text(last, chosen, runner, facts)
        reply = answering.Reply(
            text, kind="clarify", options=options[:4], understood="another design attempt"
        )
        yield from ev.text_message(uuid.uuid4().hex[:10], text)
        self._summary.update(behaviour="clarify", answer=text, same_search=last["id"])
        return (yield from self._ask_choice(reply))

    def _record_search(
        self, session: Session, outcome, brief: DesignBrief, message: str, label: str = ""
    ) -> None:
        """Keep a design search as an attempt (``S1``, ``S2`` ...) and tag its candidates with it.

        The Compare tab shows every attempt apart; a candidate's ``attempt`` says which search
        it came from.
        """
        sid = f"S{len(session.searches) + 1}"
        letter = search_letter(len(session.searches))
        for e in outcome.candidates:
            e.alternative.attempt = sid
        for k, e in enumerate(engine.ranked(outcome), 1):  # A1 the pick, A2 the next ...
            e.alternative.uid = f"{letter}{k}"
        outcome.reference.alternative.attempt = sid
        session.searches.append(
            {
                "id": sid,
                "at": time.time(),
                "message": message[:200],
                "objective": brief.objective,
                "label": (f"what-if: {label} · " if label else "") + engine.brief_label(brief),
                "layouts": len(outcome.candidates),
                "sizings": getattr(outcome, "sizings", 0),
                "years": getattr(outcome, "years", 0),
                "notes": list(getattr(outcome, "notes", []) or []),
                "brief": brief.model_dump(),
                "chosen": outcome.chosen.alternative.code if outcome.chosen else None,
                "picks": dict(getattr(outcome, "picks", {}) or {}),
                "candidates": outcome.candidates,
                "reference": outcome.reference,
                # The design-space sweep, for the Compare tab's map (not sent with the tabs).
                "sweep": getattr(outcome, "sweep", None),
            }
        )

    def _screen(self, message: str, read: intake.IntakeResult) -> Iterator[dict]:
        """Confirm a suspected request to skip the checks; return (confirmed, what was asked)."""
        deep = self._deep()
        screen = yield from self._step(
            "screen",
            "Check whether it asks to skip the checks",
            "model",
            None,
            lambda: intake.confirm_bypass(message, deep, read.bypass_words),
            after=lambda r: {
                "decided_by": r.decided_by,
                "skip_checks": r.skip_checks,
                "asked": r.asked,
                "model": getattr(deep, "model", ""),
                "device": self._device_of(deep),
            },
        )
        if screen.call is not None:
            self._calls.append(screen.call)
            yield ev.custom("usage", screen.call.as_dict())
        self._summary["screen"] = {"skip_checks": screen.skip_checks, "asked": screen.asked}
        return screen.skip_checks, screen.asked

    def _open(self, session: Session, message: str, names: Sequence[str]) -> Iterator[dict]:
        """Open the files a message names: the chat shows them, the answerer describes them."""
        facts = reporter.Facts(message)
        views: List[files.FileView] = []
        missing: List[str] = []
        for name in names[:2]:
            view = yield from self._read_file(session, name, message)
            if view is None:
                missing.append(name)
                continue
            views.append(view)
            facts.put(view.summary())
            yield ev.custom("file", view.as_dict())
        passages: List[object] = []
        texts = [v for v in views if v.kind in ("text", "binary")]
        if texts and self.docs is not None:
            # The passages the question needs: from the uploads, or the project's documents.
            uploads = any(v.origin == "attachment" for v in texts)
            passages = yield from self._search(session, message, attached=True, own=not uploads)
        return (
            yield from self._reply(
                "answer",
                reporter.file_text(views, missing, facts),
                facts,
                passages=passages,
                draft=False,
                data=views,
                missing=missing,
                kinds=("answer", "clarify"),
            )
        )

    def _read_file(self, session: Session, name: str, message: str) -> Iterator[dict]:
        """Read one file into a view (a tool step); None when it is not on the server."""
        yield ev.step_started("file", f"Open {name}", "tool", f"read_file({name!r})")
        start = time.perf_counter()
        self._tools["calls"] += 1
        found = files.find(name, session.project, session.attachments)
        view: Optional[files.FileView] = None
        error = "" if found else "the project lists this file, but it is not on the server"
        if found:
            path, origin = found
            try:
                view = files.read(
                    path,
                    name,
                    origin,
                    files.url_for(session.thread_id, name),
                    files.wanted_view(message, path),
                )
            except Exception as err:  # noqa: BLE001 - an unreadable file is reported, not fatal
                error = f"{type(err).__name__}: {err}"
        if error:
            self._tools["failed"] += 1
            content = {"error": error}
        else:
            rows = view.table["total_rows"] if view.table else None
            content = {"kind": view.kind, "rows": rows, "summary": view.summary()}
        yield from ev.tool_call(
            uuid.uuid4().hex[:10],
            "read_file",
            json.dumps({"name": name, "threadId": session.thread_id}),
            json.dumps(content, default=str),
        )
        meta = {"error": error} if error else {"kind": view.kind, "show": view.show}
        if view is not None and view.table:
            meta["rows"] = view.table["total_rows"]
        yield ev.step_finished("file", time.perf_counter() - start, **meta)
        return view

    def _talk(
        self,
        session: Session,
        read: intake.IntakeResult,
        brief: DesignBrief,
        message: str,
        result: Optional[LedgerEntry] = None,
    ) -> Iterator[dict]:
        """Answer from what is known: values, documents, the designs so far, Dioscuri itself.

        ``result`` is the design a question is about ("is this a good design?"): its checked
        summary becomes the draft, so the answer keeps its key numbers.
        """
        facts = reporter.Facts(message)
        passages: List[object] = []
        draft: Optional[str] = None
        must: List[str] = []
        sheet: Dict[str, lookup.Fact] = {}
        # The values asked for: the small reader's for a question, the reasoning model's for any
        # message it named values in ("when does the doublet stop?" read as "other", 1 Nov).
        keys = list(read.asks_for) if read.intent == "question" or self._planner_keys else []
        asked = list(keys)  # the values the reading says the message asks for (code writes them)
        values: List[str] = []
        why = result is not None and bool(WHY_START.search(message))
        if why and not keys:
            # "Why does the design take half its heat from gas?": the heat split and its reason
            # lead the answer; on 1 Nov the reason sat deep in the design block and the reply
            # blamed the N-1 sizing.
            keys = [k for k in read.asks_for if k in lookup.WHY_FACTS]
        if result is not None and set(keys) <= lookup.PROJECT_KEYS and not self._planner_keys:
            # A question about the design answers from its context, not a sheet; unless the
            # reasoning model named the values asked ("which heating return did you assume?").
            keys = asked = []
        full: Dict[str, lookup.Fact] = {}
        about = result or self._lookup_on or self._focus or session.chosen
        origin = (
            provenance.draft(about, message, self._origin_texts(about), self._origin_of)
            if about is not None and (self._origin_of or provenance.asks_origin(message))
            else None
        )
        if (
            about is not None
            and (origin is not None or keys or self._premises)
            and not self._only_designs
            and not OTHER_DESIGNS.search(message)
        ):
            # A question about one design's values: the reply names that design only, and the
            # ones the message names (2 Nov: "heat under 70?" brought in the cheapest and the
            # greenest designs).
            allowed = [about] + named_in(message, session) + list(self._picked)
            self._only_designs = sorted(
                {x for e in allowed for x in (e.alternative.code, e.alternative.uid) if x}
            )
        if origin is not None:
            # "Where does the 30 MW come from?": code finds which of the design's figures the
            # number is and says how it was worked out; the model words it, keeping the working
            # (1 Nov: the reply restated "three 10 MW units", or found no answer).
            draft, must = facts.put(origin[0]), list(origin[1])
            self._summary["provenance"] = list(origin[2])
            self._topic_keys = list(origin[2])
        elif keys:
            self._topic_keys = list(keys)
            full, draft, must = yield from self._lookup(session, brief, keys, facts)
            sheet = {k: f for k, f in full.items() if k in keys}
            if asked and policies.code_facts() and not self._premises:
                # Not for a message that states values of its own ("so the boilers only cover
                # around 25 %?"): the check of its premises leads, and the key read for such a
                # message is a guess at the quantity (5 Nov: "heat demand covered: 100 %" led
                # the reply, and the true "the boiler covers 34.5 %" was removed).
                values, must = self._code_values(asked, full, must, facts)
            if self._lookup_on is not None and self._lookup_on is not session.chosen:
                self._theirs = self._values_elsewhere(session, self._lookup_on, keys)
            about = self._focus or session.chosen
            reason = answering.heat_split_why(about) if about else ""
            if "heat_split" in keys and reason and (why or WHY_ANY.search(message)):
                draft += "\n\n" + facts.put(reason)
                # The costs that decided the heat pump's size stay in the reply (S34, 1 Nov).
                costs = re.findall(r"\d+(?:\.\d+)? €/MWh", reason)
                if costs:
                    must.append("~" + " ".join(costs))
        elif read.intent not in ("about", "greeting") and self.docs is not None:
            # The answerer judges relevance too, so the reader's "unrelated" skips nothing.
            passages = yield from self._search(session, message)
        if (
            not passages
            and self.docs is not None
            and session.attachments
            and (ATTACHED.search(message) or FILE_NAME.search(message))
        ):
            # A message about the attached file is answered with it, whatever values it asks
            # for too (4 Nov: "summarise the attached datasheet and size an absorption chiller
            # from it" read the design's values and never the file: "no file was provided").
            passages = yield from self._search(session, message, attached=True)
        if self._already and session.chosen is not None:
            # "Would cooling with outside air help?" when the design has free cooling: said
            # first, with what it does, never answered as if it were missing (3 Nov).
            lead = answering.already_text(self._lookup_on or session.chosen, self._already)
            if lead:
                draft = facts.put(lead) + ("\n\n" + draft if draft else "")
        if self._premises:
            # What the message states as given, against the facts: a number a fact contradicts
            # is corrected by code first; the rest goes to the model paired with its facts.
            # Before a design, the project's own facts (its demand, its reservoir).
            if not full:
                demand = None
                if session.project.has_heat_profile:
                    out = yield from self._tool(
                        "demand_summary",
                        {"brief": brief.model_dump()},
                        lambda: engine.demand_summary(brief.project_id),
                    )
                    demand = None if isinstance(out, ToolError) else out
                full = lookup.project_facts(session.project, brief, demand)
                if self._lookup_on or session.chosen:
                    full.update(lookup.design_facts(self._lookup_on or session.chosen))
            lead, self._premises = lookup.premise_checks(self._premises, full, keys)
            if lead:
                draft = facts.put(lead) + ("\n\n" + draft if draft else "")
        fallback_only = None
        one = self._lookup_on or self._focus
        if (
            result is None
            and draft is None
            and one is not None
            and read.relevant
            and read.intent not in ("about", "greeting")
        ):
            # A question about one design the words or the conversation named ("what did the
            # store change?" on the what-if): its checked summary stands when the reply fails,
            # not "which value do you mean?" (4 Nov).
            result = one
        if result is not None and draft is None:
            # The design's blocks are the context; its summary is only what shows when the
            # model fails, never a draft to keep (that repeated it under every answer).
            # The design's summary and its physics notes: what shows when the model fails.
            notes = " ".join(answering.design_notes(result))
            fallback_only = reporter.design_answer(result, [], facts)
            if notes:
                fallback_only += "\n\n" + facts.put(notes)
            self._template_stands = True
        if draft is not None:
            fallback, behaviour = draft, "answer"
        elif fallback_only is not None:
            fallback, behaviour = fallback_only, "answer"
        elif read.intent == "about" and read.relevant:
            fallback, behaviour = reporter.about_text(read.language, self.models(), facts), "about"
        elif read.intent == "greeting" and read.relevant:
            thanks = bool(intake.THANKS.search(message))
            fallback, behaviour = reporter.greeting_text(read.language, thanks), "greeting"
        elif passages and read.relevant:
            fallback, behaviour = reporter.docs_text(passages, facts), "answer"
        elif read.relevant:
            sheet = lookup.project_facts(session.project, brief, None)
            fallback, behaviour = reporter.unknown_question_text(sheet), "answer"
        else:
            fallback, behaviour = reporter.refuse_text(read.language), "refuse"
        # The reader routes most design requests; when it missed one ("run the study and
        # write it up"), a larger model may run it: the answerer itself when it is large enough
        # (it then sees the whole context), else the reasoning model with one focused question.
        run = draft is None and not read.screened and read.intent not in ("greeting", "about")
        # With the inputs card open its own Run runs the design: the reply only answers.
        run = run and self._held is None
        route_after = False
        if run and claims.TOO_SMALL.search(getattr(self._answerer(), "model", "")):
            run = False
            # A message the reader found unrelated is answered first: the weather is declined
            # with no extra call, and only an answer about the project asks the question.
            route_after = not read.relevant and self._held is None
            if read.relevant and self._held is None and (yield from self._route(session, message)):
                self._summary.update(intent="design", routed_by="reasoning model")
                return (yield from self._routed_design(session, brief, message, read.language))
        done = yield from self._reply(
            behaviour,
            fallback,
            facts,
            suggestions=reporter.REFUSE_SUGGESTIONS[read.language],
            passages=passages,
            must=must,
            draft=draft is not None,
            sheet=sheet,
            # A greeting or "who are you" matched by pattern can only be answered.
            kinds=("answer",) if read.screened else answering.KINDS,
            off_topic=not read.relevant,
            run=run,
            route_after=route_after,
            values=values,
            question=True,
        )
        if done == "design":
            routed = "reasoning model" if route_after else "answerer"
            self._summary.update(intent="design", routed_by=routed)
            return (yield from self._routed_design(session, brief, message, read.language))
        return done

    def _language(self) -> str:
        """Return the turn's language as read ("en" when not read)."""
        lang = str(self._summary.get("language") or "en")
        return lang if lang in reporter.REFUSE_SUGGESTIONS else "en"

    @staticmethod
    def _origin_texts(entry: LedgerEntry) -> List[str]:
        """Return a design's notes and its block: where a number no figure matches may be."""
        texts = list(answering.design_notes(entry))
        try:
            texts.append(answering.design_block(entry).text)
        except Exception:  # noqa: BLE001 - the notes alone still serve
            pass
        return texts

    def _routed_design(
        self, session: Session, brief: DesignBrief, message: str, language: str
    ) -> Iterator[dict]:
        """Run a design the reader missed and a larger model routed: read its settings first.

        "Give me the cheapest plant you can find" names what best means; the reading that every
        design request gets sets it before the inputs card.
        """
        if "parameters" not in self._summary:
            reading = yield from self._parameters(session, message, brief)
            item = reading.open_ref or reading.open_unrun
            if reading.ok and item and clarify.on() and not (reading.changes or reading.doublets):
                # The reading left open what the words refer to ("the setting we talked about"
                # in a chat with none, 5 Nov: it ran a design "on our agreed settings"). This
                # route runs a design, so the item counts even with no run step read: asked,
                # with the settings this chat ran, or the options; nothing runs.
                return (yield from self._ask_referent(session, item, message))
            kept = {k: v for k, v in reading.changes.items() if k not in parameters.SIZE_KEYS}
            if kept or reading.doublets:
                brief = parameters.apply(brief, kept, reading.doublets)
        return (yield from self._continue(session, "design", brief, message, language))

    def _resume(self, session: Session, answers: Dict[str, str]) -> Iterator[dict]:
        pending, session.pending = session.pending, None
        if self._auto:
            self._reasoning = bool(pending.get("reasoning", False))
        self._message = pending["message"]
        self._summary.update(
            intent=pending["intent"], language=pending["language"], answered=sorted(answers)
        )
        if pending.get("kind") == "which_design":
            # The design picked (or typed): the question is about it, as if picked with @.
            said = (answers.get("design") or "").strip()
            did = (pending.get("ids") or {}).get(said) or said
            found, _ = reliability.resolve([did], session) if did else ([], [])
            if not found and said:
                found = named_in(said, session)
            if not found:
                session.pending = pending  # not a design of this chat: ask again
                return (
                    yield from self._ask_design(
                        session,
                        types.SimpleNamespace(
                            intent=pending["intent"], language=pending["language"]
                        ),
                        pending["message"],
                        list((pending.get("ids") or {}).items()),
                    )
                )
            self._picked = found[:1]
            if found[0] is not session.chosen:
                self._focus = self._lookup_on = found[0]
            return (yield from self._turn(session, pending["message"]))
        if pending.get("kind") == "choice":
            # The picked reading is a complete request: answer it as a new message. An amount
            # or a referent asked with choices runs the full request kept with the option.
            picked = answers.get("choice") or ""
            self._message = (pending.get("requests") or {}).get(picked) or picked
            self._message = self._message or pending["message"]
            return (yield from self._turn(session, self._message))
        if pending.get("kind") == "decision":
            return (yield from self._decided(session, pending, answers.get("decision", "")))
        if pending.get("kind") == "generate":
            return (yield from self._generate(session, pending, answers.get("generate", "")))
        if pending.get("kind") == "approval":
            return (yield from self._approved(session, pending, answers.get("approval", "")))
        if pending.get("kind") == "confirm":
            choice = answers.get("confirm", "")
            brief = DesignBrief(**pending["brief"])
            # The card's switches (network losses, the plant options, the brine's gas), each
            # checked by code: an amount outside its range is refused on the card.
            brief, refused = card_edits.read_toggles(answers, brief)
            if refused and (choice == reporter.RUN_OPTION or choice.lower().startswith("run")):
                yield from self._confirm_inputs(
                    session,
                    pending["intent"],
                    brief,
                    pending["message"],
                    pending["language"],
                    changed=list(pending.get("changed") or []),
                    errors=refused,
                    asked={k: answers.get(k) for k in refused},
                )
                for key in ("plan", "reasoning"):
                    if pending.get(key) and session.pending is not None:
                        session.pending[key] = pending[key]
                return "confirm"
            if choice == reporter.RESET_OPTION:
                # The card's "Reset to defaults": the project's own values, the card again.
                session.pending = pending
                return (yield from self._reset_inputs(session, pending))
            if choice == reporter.RUN_OPTION or choice.lower().startswith("run"):
                if card_edits.asks_change(answers, brief):
                    # The card's own form: its changes and stop dates, checked by code.
                    brief = yield from self._apply_card(session, pending, brief, answers)
                    if brief is None:
                        return "confirm"  # refused: the card again, the reasons on the fields
                session.confirmed[session.project.id] = project_fingerprint(session.project)
                if pending.get("plan"):  # a request of several steps waited for the card
                    return (
                        yield from self._run_plan(
                            session,
                            brief,
                            pending["message"],
                            plan_from(pending["plan"]),
                            pending["language"],
                            confirmed=True,
                        )
                    )
                return (
                    yield from self._continue(
                        session,
                        pending["intent"],
                        brief,
                        pending["message"],
                        pending["language"],
                        confirmed=True,
                    )
                )
            if choice and choice != reporter.CHANGE_OPTION:
                # A typed answer in the card's box: read it like a reply.
                session.pending = pending
                done, out = yield from self._confirm_reply(session, pending, choice)
                if done:
                    return out
                return (yield from self._turn(session, choice))
            session.pending = pending  # still open: the next message says what to change
            facts = reporter.Facts("")
            yield from self._reply(
                "clarify", reporter.change_input_text(), facts, write=False, card_view="none"
            )
            return "confirm"
        turn = intake.apply_answers(DesignBrief(**pending["brief"]), answers)
        return (
            yield from self._continue(
                session, pending["intent"], turn, pending["message"], pending["language"]
            )
        )

    def _continue(
        self,
        session: Session,
        intent: str,
        turn: DesignBrief,
        message: str,
        language: str,
        confirmed: bool = False,
    ) -> Iterator[dict]:
        needs_inputs = not (intent in ("what_if", "explain") and session.chosen)
        questions = intake.missing_inputs(turn, session.project) if needs_inputs else []
        if questions:
            session.pending = {
                "kind": "inputs",
                "intent": intent,
                "brief": turn.model_dump(),
                "message": message,
                "language": language,
            }
            self._summary.update(behaviour="clarify", asked=[q.id for q in questions])
            yield from self._step("ask", "Ask for the missing inputs", "ask", None, lambda: None)
            intro = reporter.clarify_text(questions, language)
            yield from ev.text_message(uuid.uuid4().hex[:10], intro)
            yield ev.custom(
                "clarification",
                {
                    "kind": "inputs",
                    "intro": intro,
                    "questions": [q.model_dump() for q in questions],
                },
            )
            self._summary["answer"] = intro
            return "clarification"
        first_search = intent in ("design", "compare") or (
            intent == "what_if" and not session.chosen
        )
        if first_search and not confirmed and not self._confirmed(session):
            if self._held is not None and engine.same_search(session.brief.model_dump(), turn):
                # The inputs card is open and this message changes none of its inputs: a
                # question asked while it waits, answered now; the card stays open for "go
                # ahead" (C2, 4 Nov: "we can drill up to five doublets, can't we?" showed the
                # card again, and the next turn's run answered it, a turn late).
                read = intake.IntakeResult(
                    relevant=True, bypass=False, intent="question", language=language
                )
                return (yield from self._talk(session, read, turn, message))
            # Before the first design: what was read from the project and what is assumed.
            return (yield from self._confirm_inputs(session, intent, turn, message, language))
        last = session.searches[-1] if session.searches else None
        if (
            first_search
            and not confirmed
            and session.chosen is not None
            and last is not None
            and engine.same_search(last["brief"], turn)
            and not session.attachments
        ):
            # "Another design" with nothing changed: the same inputs give the same designs, so
            # the inputs card opens ready to edit (2 Nov); confirming it as it is says so.
            return (
                yield from self._confirm_inputs(
                    session, intent, turn, message, language, again=last
                )
            )
        session.remember(turn)
        if intent == "what_if" and session.chosen:
            reading = yield from self._parameters(session, message)
            if reading.changes or reading.doublets:
                yield from self._what_if(session, turn, message, reading)
            else:
                read = intake.IntakeResult(relevant=True, bypass=False, intent="question")
                yield from self._talk(
                    session, read, turn, message, result=self._focus or session.chosen
                )
        elif intent == "explain" and session.chosen:
            facts = reporter.Facts(message)
            yield from self._reply(
                "design",
                reporter.explain_answer(session.chosen, facts),
                facts,
                session.chosen,
                card_view="none",
            )
        else:
            return (yield from self._design(session, turn, message, intent, language))
        return None

    # ------------------------------------------------------------- engineering

    def _design(
        self,
        session: Session,
        brief: DesignBrief,
        message: str,
        intent: str,
        language: str,
        reply: bool = True,
    ) -> Iterator[dict]:
        """Design for the challenge: plan, solve, size, run, improve, price and pick.

        The candidates are planned from the brief, the doublets solved on GEMINI, every
        candidate sized and run for the year, those that break a cap improved, the cheapest
        given a reliable plan too, and the valid ones priced and ranked. Without ``reply`` (a
        step of a plan) the draft, the pick and the search come back instead of a reply.
        """
        attached: List[object] = []
        if session.attachments and self.docs is not None:
            attached = yield from self._search(session, message, attached=True)
        objective = brief.objective
        last = session.searches[-1] if session.searches else None
        # The same brief again is not run again, unless the message brings a file into it
        # ("size an absorption chiller from the attached datasheet"): the file may change things.
        about_files = bool(attached) or bool(
            session.attachments and (ATTACHED.search(message) or FILE_NAME.search(message))
        )
        if (
            last is not None
            and session.chosen
            and not about_files
            and engine.same_search(last["brief"], brief)
        ):
            if not reply:  # a plan's design step: the design that exists
                return {"draft": "", "entry": session.chosen, "outcome": None}
            return (yield from self._same_search(session, last, brief, message))
        space = engine.space(brief)
        yield from self._step(
            "plan",
            "Plan the candidates",
            "plan",
            "plan(brief)",
            lambda: space,
            after=lambda s: {
                "decided_by": "rules",
                "reason": s["reason"],
                "candidates": s["count"],
                "excluded": s["excluded"],
            },
        )
        rules = engine.rules_for(brief)
        depths = space["depths"]
        doublets = yield from self._tool_step(
            "doublet",
            "Solve the doublets on GEMINI",
            "gemini.doublet(flow=300 m3/h, depth=" + ", ".join(f"{d:g}" for d in depths) + ")",
            [
                (
                    "solve_doublet",
                    {"depth_m": d, "flow_m3h": rules.flow_max_m3h},
                    (lambda d=d: engine.doublet_summary(d, rules)),
                )
                for d in depths
            ],
        )
        if all(isinstance(x, ToolError) for x in doublets):
            # Said with what most likely caused it, and where to change it (Ali, 3 Nov).
            why = reporter.search_failed_text(doublets[0].message, brief, "wells")
            yield from self._reply("error", why, None)
            return None
        found = yield from self._tool_step(
            "simulate",
            f"Size and run {space['count']} combinations over 2027",
            f"search_designs({space['count']} combinations, objective={objective})",
            [
                (
                    "search_designs",
                    {"brief": brief.model_dump(), "assumptions": session.assumptions},
                    lambda: engine.search(brief, session.assumptions),
                )
            ],
        )
        outcome = found[0]
        if isinstance(outcome, ToolError):
            why = reporter.search_failed_text(outcome.message, brief)
            yield from self._reply("error", why, None)
            return None
        s = engine.summary(outcome)
        tried = outcome.tried
        yield from self._step(
            "verify",
            "Check the challenge's caps",
            "check",
            f"verify_design({len(tried)} candidates)",
            lambda: tried,
            after=lambda es: {
                "passed": sum(verifier.physics_ok(x.verification) for x in es),
                "total": len(es),
                "caps_met": s["valid"],
            },
        )
        improved = [x for x in tried if len(x.alternative.rounds) > 1]
        yield from self._step(
            "improve",
            "Fix what broke and run again",
            "plan",
            f"improve({len(improved)} candidates)",
            lambda: improved,
            after=lambda es: {
                "decided_by": "rules",
                "reason": "Each day short of heat or cold grows the unit that was short by the "
                "worst gap, then the year runs again.",
                "changes": [
                    f"{x.alternative.code}: {r['change']}"
                    for x in es[:6]
                    for r in x.alternative.rounds
                    if r.get("change")
                ],
                "rounds": s["rounds"],
            },
        )
        session.candidates = outcome.candidates
        session.reference = outcome.reference
        self._record_search(session, outcome, brief, message)
        facts = reporter.Facts(message)
        # The search behind the design: kept for the steps and the tabs; drawn as a card in the
        # chat only when the message asks how the design was found (3 Nov).
        searched = reporter.candidates_payload(outcome)
        if session.searches:
            session.searches[-1]["card"] = searched
        self._searched_now = True
        yield ev.custom("candidates", {**searched, "show": "search" in self._show})
        if outcome.chosen is None:
            self._summary.update(verified=False)
            return (
                yield from self._shortfall_challenge(
                    session, outcome, brief, facts, intent, language
                )
            )
        chosen = outcome.chosen
        yield from self._step(
            "rank",
            "Price and pick",
            "plan",
            f"rank({s['valid']} designs, objective={objective})",
            lambda: chosen,
            after=lambda c: {
                "decided_by": "rules",
                "reason": f"{c.alternative.code} has the {engine.OBJECTIVE_WORDS[objective]} of "
                f"the {s['valid']} designs that meet every cap.",
                "chosen": c.alternative.code,
            },
        )
        session.ledger.append(chosen)
        session.chosen = chosen
        yield from self._tool_step(
            "gemini",
            "Check the pick on GEMINI",
            "gemini.run(the pick's brine loop)",
            [
                (
                    "gemini_check",
                    {"design": reporter.design_id(chosen)},
                    lambda: engine.gemini_check(chosen),
                )
            ],
        )
        if (chosen.alternative.sizes_mw or {}).get("chillers"):
            from gemini_agent import cooling_check

            yield from self._tool_step(
                "cooling",
                "Check the cooling on Dioscuri's component model",
                "cooling_kernel(the pick's chillers and towers, De Bilt's hours 2021-2025)",
                [
                    (
                        "cooling_check",
                        {"design": reporter.design_id(chosen)},
                        lambda: cooling_check.check(chosen),
                    )
                ],
            )
        self._summary["plan"] = [x.alternative.code for x in tried]
        self._summary["objective"] = objective
        if intent == "compare" and len(intake.doublet_counts(message)) > 1:
            draft = reporter.compare_challenge(outcome, facts, by="doublets")
        elif (
            intent == "compare"
            and len(aquifers.search_depths(brief)) > 1
            and (brief.doublet_depths_m or brief.aquifers)
        ):
            draft = reporter.compare_challenge(outcome, facts, by="depth")
        else:
            draft = reporter.challenge_answer(outcome, facts)
        if not reply:
            return {"draft": draft, "facts": facts, "entry": chosen, "outcome": outcome}
        yield from self._reply(
            "design",
            draft,
            facts,
            entry=chosen,
            suggestions=reporter.challenge_suggestions(chosen),
            passages=attached,
        )
        return None

    def _shortfall_challenge(
        self,
        session: Session,
        outcome,
        brief: DesignBrief,
        facts: reporter.Facts,
        intent: str,
        language: str,
    ) -> Iterator[dict]:
        """No candidate meets every cap: offer to relax what the user ruled out, and say why."""
        if self._auto and not self._reasoning:
            yield from self._think_harder("No design met every cap, so the choice of fix matters.")
        options = engine.relaxations(brief)
        tried: List[Tuple[str, LedgerEntry]] = []
        yield ev.step_started(
            "options", "Try the brief without each limit", "tool", "search_designs(relaxed)"
        )
        start = time.perf_counter()
        for label, relaxed in options:
            found = yield from self._tool(
                "search_designs",
                {"brief": relaxed.model_dump()},
                lambda relaxed=relaxed: engine.search(relaxed, session.assumptions),
            )
            if not isinstance(found, ToolError) and found.chosen is not None:
                tried.append((label, found.chosen))
        yield ev.step_finished(
            "options", time.perf_counter() - start, options=[t[0] for t in tried]
        )
        failed = outcome.tried
        best = max(failed, key=lambda e: e.year.heat_coverage) if failed else outcome.reference
        if not tried:
            yield from self._reply(
                "report_infeasible", reporter.keep_limits_text(best, facts), facts, entry=best
            )
            return None
        session.ledger.extend(e for _, e in tried)
        keep = reporter.KEEP_LIMITS[language]
        labelled = [(label, e) for label, e in tried]
        cheapest = min(tried, key=lambda t: t[1].economics.lcoe_eur_per_mwh)[0]
        question = reporter.decision_question(labelled, keep, cheapest, language)
        position = {id(e): i for i, e in enumerate(session.ledger)}
        session.ledger.append(best)
        session.pending = {
            "kind": "decision",
            "intent": intent,
            "message": self._message,
            "language": language,
            "choices": [[c, position[id(e)]] for c, (_, e) in zip(question.options, tried)],
            "best": len(session.ledger) - 1,
            "brief": brief.model_dump(),
        }
        details = [
            {
                "option": c,
                "fix": label,
                "code": e.alternative.code,
                "name": e.alternative.name,
                "heat_coverage": e.year.heat_coverage,
                "heat_coverage_pct": round(e.year.heat_coverage * 100, 1),
                "lcoh": e.economics.lcoh_eur_per_mwh,
                "recommended": label == cheapest,
            }
            for c, (label, e) in zip(question.options, tried)
        ] + [{"option": keep, "fix": "keep", "recommended": False}]
        yield from self._reply(
            "report_infeasible",
            reporter.infeasible_text(best, labelled, facts),
            facts,
            entry=best,
        )
        yield ev.custom(
            "clarification",
            {
                "kind": "decision",
                "intro": question.label,
                "questions": [question.model_dump()],
                "details": details,
            },
        )
        self._summary.update(asked=["decision"], recommended=cheapest)
        return "decision"

    def _decided(self, session: Session, pending: dict, choice: str) -> Iterator[dict]:
        """Continue after the user picked an option (or kept their limits)."""
        picked = next(
            (i for c, i in pending["choices"] if choice and (c == choice or c.startswith(choice))),
            None,
        )
        facts = reporter.Facts(pending["message"])
        if picked is None:
            best = session.ledger[pending["best"]]
            yield from self._step("decide", "Keep your limits", "plan", None, lambda: None)
            yield from self._reply(
                "report_infeasible", reporter.keep_limits_text(best, facts), facts, entry=best
            )
            return None
        entry = session.ledger[picked]
        asked = DesignBrief(**pending["brief"]) if pending.get("brief") else entry.brief
        if entry.alternative.rounds:  # a challenge design: checked against the caps already
            session.ledger.append(entry)
            session.chosen = entry
            session.remember(entry.brief)
            yield from self._reply(
                "design",
                reporter.chosen_text(entry, facts, asked.min_heat_coverage),
                facts,
                entry=entry,
                suggestions=reporter.CHALLENGE_SUGGESTIONS,
            )
            return None
        # Checked against what the user asked for, so a smaller coverage shows as unmet.
        checked = yield from self._step(
            "verify",
            "Check the option you picked",
            "check",
            f"verify_design({entry.alternative.code})",
            lambda: verifier.verify(entry.year, entry.economics, asked),
            after=lambda v: {"passed": sum(c.passed for c in v.checks), "total": len(v.checks)},
        )
        if not verifier.physics_ok(checked):
            yield from self._reply("error", "The option you picked failed a physics check.", None)
            return None
        entry = entry.model_copy(update={"verification": checked})
        session.ledger.append(entry)
        session.chosen = entry
        session.remember(entry.brief)
        yield from self._reply(
            "design",
            reporter.chosen_text(entry, facts, asked.min_heat_coverage),
            facts,
            entry=entry,
            suggestions=reporter.DESIGN_SUGGESTIONS,
        )
        return None

    # ------------------------------------------------------- generated models

    def _offer_model(
        self, session: Session, spec, brief: DesignBrief, intent: str, language: str
    ) -> Iterator[dict]:
        """No model exists for this component: offer to write one (the user must say yes)."""
        yes, no = reporter.GENERATE[language]
        generation = uuid.uuid4().hex[:10]
        session.pending = {
            "kind": "generate",
            "generation_id": generation,
            "spec": spec.name,
            "intent": intent,
            "message": self._message,
            "language": language,
            "brief": brief.model_dump(),
            "options": [yes, no],
        }
        question = Question(
            id="generate",
            label=f"Write {reporter.article(spec.title)} {spec.title.lower()} model?",
            hint="Writing and testing take one model call per attempt (at most three).",
            options=[yes, no],
            default=yes,
        )
        facts = reporter.Facts(self._message)
        text = facts.put(spec.offer())
        yield from self._reply("offer_model", text, facts, write=False)
        yield ev.custom(
            "clarification",
            {
                "kind": "offer",
                "generation_id": generation,
                "intro": question.label,
                "questions": [question.model_dump()],
                "details": {
                    "component": spec.name,
                    "title": spec.title,
                    "inputs": [f"{q.name} [{q.unit}]" for q in spec.inputs],
                    "outputs": [f"{q.name} [{q.unit}]" for q in spec.outputs],
                    "physics": spec.physics,
                    "sources": spec.sources,
                },
            },
        )
        self._summary["asked"] = ["generate"]
        return "offer"

    def _generate(self, session: Session, pending: dict, choice: str) -> Iterator[dict]:
        """Write the model, test it in the sandbox (self-correcting), then ask for approval."""
        spec = modelgen.SPECS[pending["spec"]]
        language = pending["language"]
        facts = reporter.Facts(pending["message"])
        if not choice or choice == pending["options"][1]:
            yield from self._reply(
                "answer",
                "Understood: no new model. The design keeps the components it has.",
                facts,
                write=False,
            )
            return None
        llm = self._generator()
        steps = modelgen.iter_generate(spec, llm)
        try:
            while True:
                start = time.perf_counter()
                try:
                    attempt = next(steps)
                except StopIteration as stop:
                    result = stop.value
                    break
                name = f"modelgen-{attempt.number}"
                yield ev.step_started(
                    name,
                    f"Write and test the {spec.title.lower()} model (attempt {attempt.number})",
                    "model",
                    f"generate({spec.func_name}) + sandbox({len(spec.cases)} cases)",
                )
                if attempt.call is not None:
                    self._calls.append(attempt.call)
                    yield ev.custom("usage", attempt.call.as_dict())
                yield ev.custom("modelgen_attempt", attempt.as_dict())
                yield ev.step_finished(
                    name,
                    time.perf_counter() - start,
                    passed=attempt.passed,
                    problems=attempt.problems()[:5],
                    reason=attempt.reason,
                )
        except ModelUnavailable as err:
            model = getattr(llm, "model", "the model")
            fix = unavailable_hint(model, str(err))
            yield ev.custom(
                "model_unavailable",
                {
                    "model": model,
                    "error": str(err),
                    "fix": fix,
                    "reason": unavailable_reason(str(err)),
                },
            )
            yield from self._reply(
                "model_unavailable",
                reporter.unavailable_text(model, fix, language, facts),
                facts,
                write=False,
            )
            return None
        self._summary["generation"] = {
            "component": spec.name,
            "model": result.model,
            "passed": result.passed,
            "attempts": len(result.attempts),
            "tokens": result.tokens,
        }
        if not result.passed:
            yield from self._reply(
                "answer", reporter.generated_failed_text(spec, result, facts), facts, write=False
            )
            return None
        approve, reject = reporter.APPROVE[language]
        session.pending = dict(
            pending, kind="approval", result=result.as_dict(), options=[approve, reject]
        )
        units = {q.name: q.unit for q in list(spec.inputs) + list(spec.outputs)}
        yield ev.custom("model_approval", dict(result.as_dict(), units=units))
        yield from self._reply(
            "approve_model", reporter.generated_ready_text(spec, result, facts), facts, write=False
        )
        question = Question(
            id="approval",
            label=f"Use this {spec.title.lower()} model?",
            hint="Approved code is saved with its test table; code edited later is refused.",
            options=[approve, reject],
        )
        yield ev.custom(
            "clarification",
            {
                "kind": "approval",
                "generation_id": pending.get("generation_id"),
                "intro": question.label,
                "questions": [question.model_dump()],
            },
        )
        self._summary["asked"] = ["approval"]
        return "approval"

    def _approved(self, session: Session, pending: dict, choice: str) -> Iterator[dict]:
        """Register an approved model and use it; a rejected one is dropped."""
        spec = modelgen.SPECS[pending["spec"]]
        facts = reporter.Facts(pending["message"])
        if choice != pending["options"][0]:
            yield from self._reply(
                "answer", "Rejected: the model was not saved.", facts, write=False
            )
            return None
        result = modelgen.GenerationResult.from_dict(pending["result"])
        yield ev.step_started(
            "register", "Save the approved model", "tool", f"registry.save({spec.name!r})"
        )
        start = time.perf_counter()
        path = yield from self._tool(
            "register_model",
            {"component": spec.name, "approved_by": "user", "model": result.model},
            lambda: str(self.registry.save(result, approved_by="user", spec=spec)),
        )
        yield ev.step_finished(
            "register", time.perf_counter() - start, saved=not isinstance(path, ToolError)
        )
        if isinstance(path, ToolError):
            yield from self._reply("error", f"The model could not be saved: {path.message}", None)
            return None
        yield from self._use_model(session, spec, pending["message"])
        return None

    def _use_model(self, session: Session, spec, message: str) -> Iterator[dict]:
        """Run a registered generated model at the latest design's conditions and report it."""
        cases = model_conditions(spec, session)
        sha = self.registry.load(spec.name).meta.get("sha256", "")
        yield ev.step_started(
            "use_model",
            f"Run the {spec.title.lower()} model at this design's conditions",
            "tool",
            f"{spec.func_name}({len(cases)} case(s), sandboxed)",
        )
        start = time.perf_counter()
        evaluation = yield from self._tool(
            f"evaluate_{spec.name}",
            {"model": spec.name, "sha256": sha, "cases": cases},
            lambda: self.registry.evaluate_checked(spec.name, cases),
        )
        failed = isinstance(evaluation, ToolError)
        yield ev.step_finished(
            "use_model",
            time.perf_counter() - start,
            passed=None if failed else evaluation.passed,
            cases=len(cases),
        )
        if not failed:
            yield ev.custom(
                "model_result",
                {
                    "component": spec.name,
                    "title": spec.title,
                    "cases": evaluation.cases,
                    "outputs": evaluation.outputs,
                    "assumed": evaluation.assumed,
                    "units": {q.name: q.unit for q in list(spec.inputs) + list(spec.outputs)},
                    "checks": [c.model_dump() for c in evaluation.checks],
                    "warnings": evaluation.warnings,
                },
            )
        facts = reporter.Facts(message)
        if failed:
            yield from self._reply(
                "error", f"The {spec.title.lower()} model failed: {evaluation.message}", None
            )
            return None
        self._summary["generated_model"] = spec.name
        yield from self._reply(
            "answer",
            reporter.generated_text(spec, evaluation, facts),
            facts,
            must=reporter.generated_must(spec, evaluation),
        )

    def _generator(self):
        """Return the model that writes component code (created on first use)."""
        if self.router is not None:
            return self.router.generator(self._device, self._size)
        g = self._generator_llm
        if g is None:
            return self._deep()
        return g if hasattr(g, "structured") else g()

    def _search_for(
        self,
        session: Session,
        base: LedgerEntry,
        message: str,
        changes: dict,
        label: str,
        reply: bool = True,
    ) -> Iterator[dict]:
        """Search again for what the change asks for; answer with its pick against the design.

        "What would a gas-free version cost?" changes what the search looks for, not the plant:
        running the same plant under it would show the same plant (31 Oct: "a gas-free version
        costs 69.8 €/MWh", the gas design's own cost).
        """
        brief = parameters.apply(held_caps(base.brief), changes, [])
        searched = yield from self._tool_step(
            "search",
            f"Search the designs again for {label}",
            f"search_designs({label})",
            [
                (
                    "search_designs",
                    {"brief": brief.model_dump(), "changes": changes},
                    lambda: engine.search(brief, session.assumptions),
                )
            ],
        )
        outcome = searched[0]
        if isinstance(outcome, ToolError) or outcome.chosen is None:
            yield from self._reply("error", f"No design meets every cap for {label}.", None)
            return None
        self._record_search(session, outcome, brief, message, label=label)
        new = outcome.chosen.model_copy(deep=True)
        new.alternative.role = "what_if"
        new.changes, new.change_label = changes, label
        new.alternative.parent = reporter.design_id(base)
        session.ledger.append(new)
        facts = reporter.Facts(message)
        must = reporter.key_values(new, "design")
        draft = reporter.search_for_answer(base, new, facts, label)
        if not reply:
            return {
                "draft": draft,
                "facts": facts,
                "entry": new,
                "best": None,
                "must": must,
                "research": None,
            }
        yield from self._reply("design", draft, facts, entry=new, card_view="compact", must=must)
        return None

    def _what_if(
        self,
        session: Session,
        brief: DesignBrief,
        message: str,
        reading: parameters.Reading,
        reply: bool = True,
    ) -> Iterator[dict]:
        """Run the design under the asked change, and the search again under it.

        The same plant (with any change to the plant itself: a unit's size, a second injector)
        shows what the change does to this design; the search under the changed conditions
        shows whether another design would now be better. Both are kept: the first as a
        what-if of the design, the second as a new attempt.
        """
        base = session.chosen
        # "Could they live with the cheapest one?": the change runs on the design named.
        if reading.designs:
            found, _ = reliability.resolve(reading.designs, session)
        else:
            found = named_in(message, session)
        if len(found) == 1:
            base = found[0]
        changes = dict(reading.changes)
        label = parameters.label(changes) or "the doublets as described"
        rules = engine.rules_for(base.brief)
        design_changes = {k: v for k, v in changes.items() if k in parameters.DESIGN_KEYS}
        if "exclude" in changes:
            for unit in changes["exclude"]:
                key = {"heat_pump": "heat_pump_mw", "boiler": "boiler_mw", "chiller": "chiller_mw"}
                if unit in key:
                    design_changes[key[unit]] = 0.0
        if changes and set(changes) <= SEARCH_FOR and not reading.doublets:
            # What "best" means, or a unit allowed again: the plant does not change, so the
            # answer is the search's pick under it, set against the design.
            return (yield from self._search_for(session, base, message, changes, label, reply))
        conditions = {
            k: v
            for k, v in changes.items()
            if k not in parameters.DESIGN_KEYS and k not in parameters.SEARCH_ONLY
        }
        new_brief = parameters.apply(base.brief, conditions)
        alt = base.alternative
        if design_changes or reading.doublets:
            if reading.doublets:
                design_changes = dict(design_changes, n_doublets=len(reading.doublets))
            alt = parameters.change_design(alt, design_changes, rules.reservoir_depth_m)
            if reading.doublets:
                alt = alt.model_copy(
                    update={
                        "doublets": [
                            {
                                "depth_m": d.depth_m or rules.reservoir_depth_m,
                                "producer_open": d.producer_open,
                                "injector_open": d.injector_open,
                                "injectors": d.injectors,
                                "max_flow_m3h": d.max_flow_m3h,
                                "train": d.train if d.train is not None else 0,
                            }
                            for d in reading.doublets
                        ]
                    }
                )
        moved = False
        if "aquifers" in changes and not reading.doublets:
            # The design's doublets follow their aquifers (a depth moved, an aquifer dropped).
            before = aquifers.value_of(base.brief)
            after = aquifers.move_doublets(alt, before, changes["aquifers"])
            moved = after is not alt
            alt = after
        yield from self._step(
            "plan",
            f"Run {base.alternative.code} with {label}",
            "plan",
            f"ledger.get({base.alternative.code!r})",
            lambda: base,
            after=lambda b: {"reused": b.alternative.code, "changes": changes},
        )
        found = yield from self._tool_step(
            "simulate",
            "Run the same plant under the change",
            f"simulate_year({base.alternative.code}, {label})",
            [
                (
                    "simulate_year",
                    {"alternative": alt.code, "changes": changes},
                    lambda: engine.evaluate(alt, new_brief, session.assumptions, role="what_if"),
                )
            ],
        )
        new = found[0]
        if isinstance(new, ToolError) or not verifier.physics_ok(new.verification):
            yield from self._reply("error", "I couldn't check the changed design.", None)
            return None
        new.changes, new.change_label = changes, label
        new.alternative.uid = next_uid(session, "W")
        new.alternative.picks = []
        new.alternative.parent = reporter.design_id(base)
        # A reliable plan stays one only if its one-unit-out cases still hold under the change:
        # a smaller boiler, or a reservoir 10 K colder (1 Nov: W3 kept "(N-1)" with one case
        # 1.69 MW short).
        lost = new.alternative.reliable and (reporter.firm_view(new) or {}).get("short") != 0
        if lost:
            new.alternative.reliable = False
        if design_changes or reading.doublets or lost or moved:
            plant = engine.plant_of(new.alternative)
            new.alternative.code = engine.plant_code(plant, rules)
            new.alternative.name = engine.plant_name(plant, rules)
        # The search under the changed conditions and the plant changes asked for. A cap the base
        # design's own run relaxed ("400 m3/h") is not carried into it: caps are experiments.
        redesign_brief = parameters.apply(
            held_caps(base.brief),
            {k: v for k, v in changes.items() if k not in parameters.SIZE_KEYS},
            reading.doublets,
        )
        searched = yield from self._tool_step(
            "search",
            "Search the designs again under the change",
            f"search_designs({label})",
            [
                (
                    "search_designs",
                    {"brief": redesign_brief.model_dump(), "changes": changes},
                    lambda: engine.search(redesign_brief, session.assumptions),
                )
            ],
        )
        outcome = searched[0]
        best = None
        if not isinstance(outcome, ToolError) and outcome.chosen is not None:
            self._record_search(session, outcome, redesign_brief, message, label=label)
            new.alternative.attempt = session.searches[-1]["id"]  # its scenario in Compare
            best = outcome.chosen.model_copy(deep=True)
            best.alternative.role = "what_if"
            best.changes, best.change_label = changes, f"{label}, searched again"
            best.alternative.parent = reporter.design_id(base)
            session.ledger.append(best)
        session.ledger.append(new)  # the what-if asked about, last
        facts = reporter.Facts(message)
        # A what-if keeps what its cost of heat and cold became.
        must = reporter.key_values(new, "design") + [
            f"{reporter.num(new.economics.lcoe_eur_per_mwh or 0)} €/MWh"
        ]
        if best is not None:  # the new search's result is the other half of the answer
            must.append(f"{reporter.num(best.economics.lcoe_eur_per_mwh or 0.0)} €/MWh")
        research = reporter.research_view(base, best)
        draft = reporter.what_if_answer(base, new, facts, label, best)
        if not reply:
            return {
                "draft": draft,
                "facts": facts,
                "entry": new,
                "best": best,
                "must": must,
                "research": research,
            }
        yield from self._reply(
            "design",
            draft,
            facts,
            entry=new,
            card_view="compact",
            must=must,
            card_extra={"research": research} if research else None,
        )
        return None

    # ------------------------------------------------------------- plans of several steps

    def _run_plan(
        self,
        session: Session,
        turn: DesignBrief,
        message: str,
        reading: parameters.Reading,
        language: str,
        confirmed: bool = False,
    ) -> Iterator[dict]:
        """Run a request's steps in order (``parameters.Reading.steps``), then answer once.

        The reasoning model read the steps (design, what-if, failure, compare, answer) with the
        changes and failures of each; code checks the plan (at most three steps, a what-if or a
        failure needs a design, made by an earlier step or before) and runs each step's tool.
        Every step's draft and card goes into one reply.
        """
        steps = list(reading.steps) or [parameters.Step("answer")]
        kinds = [x.do for x in steps]
        if "design" in kinds and session.chosen is None:
            # "A what-if, then design it": nothing to change before the design exists.
            first = kinds.index("design")
            if any(k in ("what_if", "failure", "compare") for k in kinds[:first]):
                steps = [steps[first]] + steps[:first] + steps[first + 1 :]
                kinds = [x.do for x in steps]
                order = {first: 0}
                order.update({i: i + 1 for i in range(first)})
                reading.step_of = {k: order.get(v, v) for k, v in reading.step_of.items()}
                reading.items = [(a, b, order.get(c, c)) for a, b, c in reading.items]
                for f in reading.failures:
                    f.step = order.get(f.step, f.step)
        named = reliability.resolve(reading.designs, session)[0] if session.chosen else []
        if named and "design" in kinds and set(kinds) & {"failure", "what_if", "compare"}:
            # "The cheapest one, pump down 1-14 Feb": a design that exists, not a new search
            # (only the objective would have changed, and with it the recommendation).
            d = kinds.index("design")
            search_keys = [k for k, st in reading.step_of.items() if st == d and k != "objective"]
            if not search_keys:
                steps = [x for x in steps if x.do != "design"]
                reading.changes.pop("objective", None)
                kinds = [x.do for x in steps]
        needs_design = any(k in ("what_if", "failure") for k in kinds)
        if needs_design and session.chosen is None and "design" not in kinds:
            steps.insert(0, parameters.Step("design"))  # nothing to change or fail yet
            kinds = [x.do for x in steps]
        steps = steps[: parameters.MAX_STEPS + (1 if kinds[-1] == "answer" else 0)]
        yield from self._step(
            "plan",
            "Plan the steps",
            "plan",
            "plan(" + ", ".join(kinds) + ")",
            lambda: kinds,
            after=lambda k: {
                "decided_by": "model",
                "steps": k,
                "reason": "the reasoning model read the request as these steps; code checked "
                "that each has what it needs",
            },
        )
        self._summary["steps"] = kinds
        fallback = intake_conditions(turn, session.brief)
        if not confirmed:
            turn = session.brief  # a plan's designs take the planner's changes, not the reader's
        if "what_if" in kinds and "design" in kinds:
            # The reader's conditions belong to the what-if, not to the design before it.
            w = kinds.index("what_if")
            if fallback and not reading.changes_for(w):
                reading.changes.update(fallback)
                reading.step_of.update({k: w for k in fallback})
        if "design" in kinds and not confirmed and not self._confirmed(session):
            first = kinds.index("design")
            brief = parameters.apply(
                turn,
                {
                    k: v
                    for k, v in reading.changes_for(first).items()
                    if k not in parameters.SIZE_KEYS
                },
                reading.doublets,
            )
            out = yield from self._confirm_inputs(session, "design", brief, message, language)
            session.pending["plan"] = plan_dict(reading, steps)
            return out
        drafts: List[str] = []
        cards: List[Tuple[str, dict]] = []
        must: List[str] = []
        skipped: List[str] = []
        verdict: List[str] = []
        facts = reporter.Facts(message)
        entry: Optional[LedgerEntry] = None
        board = [
            {"n": i + 1, "do": x.do, "label": step_label(x, i, reading), "status": "todo"}
            for i, x in enumerate(steps)
        ]
        designed: Optional[LedgerEntry] = None
        if reading.asked_steps > parameters.MAX_STEPS:  # cut at the most a turn runs, not dropped
            self._warnings.append(
                f"\n\nYou asked for {reading.asked_steps} steps; I ran the first "
                f"{len(steps)}. Ask for the rest next."
            )
        yield ev.custom("plan", {"steps": board})
        for k, st in enumerate(steps):
            board[k]["status"] = "done"
            if st.do == "design":
                changes = {
                    key: v
                    for key, v in reading.changes_for(k).items()
                    if key not in parameters.SIZE_KEYS
                }
                brief = parameters.apply(turn, changes, reading.doublets)
                session.remember(brief)
                out = yield from self._design(session, brief, message, "design", language, False)
                if not isinstance(out, dict):
                    return out  # the shortfall card: the plan waits for the user's choice
                if out["draft"]:
                    more = any(x.do != "answer" for x in steps[k + 1 :])
                    # Before a what-if or a failure: the pick in one paragraph (its card has more).
                    drafts.append(out["draft"].split("\n\n")[0] if more else out["draft"])
                    facts.allowed |= out["facts"].allowed
                entry = out["entry"]
                designed = entry  # the plan's own design (a report goes to it, not a what-if)
                if entry is not None:
                    cards.append(("result", self._card_of(entry, "full")))
                    verdict.append(reporter.design_verdict(entry, facts))
            elif st.do == "what_if":
                sub = parameters.Reading(
                    changes=reading.changes_for(k), doublets=reading.doublets, ok=True
                )
                if not sub.changes and not sub.doublets:
                    quote = st.quote or "the what-if"
                    self._warnings.append(
                        f"\n\nNot run: “{quote}”: I could not read a change with an amount from "
                        "it, so I drew no conclusion about it. Say the amount (for example "
                        "“10 °C colder”) and I will run it."
                    )
                    skipped.append("what_if")
                    board[k]["status"] = "skipped"
                    continue
                out = yield from self._what_if(session, turn, message, sub, reply=False)
                if not isinstance(out, dict):
                    return out
                drafts.append(out["draft"])
                facts.allowed |= out["facts"].allowed
                must += out["must"]
                entry = out["entry"]
                card = reporter.result_card(entry)
                card["view"] = "compact"
                if session.chosen is not None and session.chosen is not entry:
                    card["against"] = reporter.result_card(session.chosen)
                if out["research"]:
                    card["research"] = out["research"]
                cards.append(("result", card))
                verdict.append(
                    reporter.what_if_verdict(session.chosen, entry, out["research"], facts)
                )
            elif st.do == "failure":
                mine = [f for f in reading.failures if f.step == k] or list(reading.failures)
                on = reliability.target(reading.designs, message, session)
                out = yield from self._failure(session, mine, message, on)
                if out is None:
                    board[k]["status"] = "skipped"
                    continue
                drafts.append(out["draft"])
                facts.allowed |= out["facts"].allowed
                must += out["must"]
                cards.append(("failure", out["card"]))
                verdict.append(reliability.failure_verdict(out["card"], facts))
            elif st.do == "compare":
                out = yield from self._compare(session, reading.designs, message)
                if out is None:
                    self._warnings.append(
                        "\n\nNot run: the comparison: I found fewer than two of the designs "
                        f"named ({', '.join(reading.designs) or 'none'})."
                    )
                    skipped.append("compare")
                    board[k]["status"] = "skipped"
                    continue
                drafts.append(out["draft"])
                facts.allowed |= out["facts"].allowed
                cards.append(("compare", out["card"]))
                verdict.append(reliability.compare_verdict(out["card"], facts))
                if len(steps) == 1 or all(x.do in ("compare", "answer") for x in steps):
                    self._only_designs = [
                        x
                        for d in out["card"]["designs"]
                        for x in (d.get("code"), str(d.get("id", "")).split(" · ")[0])
                        if x
                    ]
            elif st.do == "uncertainty":
                out = yield from self._uncertainty(session, message)
                if out is None:
                    board[k]["status"] = "skipped"
                    continue
                drafts.append(out["draft"])
                facts.allowed |= out["facts"].allowed
                cards.append(("uncertainty", out["card"]))
                verdict.append(out["card"].get("verdict", ""))
            elif st.do == "summary":
                out = yield from self._decision(session, message)
                if out is None:
                    board[k]["status"] = "skipped"
                    continue
                drafts.append(out["draft"])
                facts.allowed |= out["facts"].allowed
                cards.append(("decision", out["card"]))
            elif st.do == "report":
                # The design the message names; else the plan's own design; else the current.
                on = (
                    reliability.target(reading.designs, message, session)
                    if reading.designs
                    else designed or session.chosen
                )
                out = yield from self._report(session, on)
                if out is None:
                    board[k]["status"] = "skipped"
                    continue
                drafts.append(out["draft"])
                facts.allowed |= out["facts"].allowed
                cards.append(("report", out["card"]))
        yield ev.custom("plan", {"steps": board})
        target = entry if entry is not None else session.chosen
        if skipped and not drafts:
            # Nothing ran: say so, and let no model conclude anything about it.
            yield from self._reply(
                "answer", "I could not run what you asked.", facts, write=False, card_view="none"
            )
            return None
        failure_only = all(x.do in ("failure", "answer", "report") for x in steps) and any(
            x.do in ("failure", "report") for x in steps
        )
        if failure_only and drafts:
            # A failure's days, MW and remedies are shown as code wrote them: worded by the
            # model, replies contradicted their own card 9 times in 15 (panel, 1 Nov).
            yield from self._reply(
                "answer",
                "\n\n".join(d for d in drafts if d),
                facts,
                write=False,
                card_view="none",
                step_cards=cards,
                suggestions=reporter.challenge_suggestions(target) if target is not None else None,
            )
            return None
        if entry is not None:  # the plan's design: its checks and figures for the turn's record
            self._summary.update(
                verified=entry.verification.passed,
                heat_coverage=entry.year.heat_coverage,
                cool_coverage=entry.year.cool_coverage,
                lcoh=entry.economics.lcoh_eur_per_mwh,
                alternative=entry.alternative.code,
            )
        yield from self._reply(
            "design" if entry is not None else "answer",
            "\n\n".join(d for d in drafts if d) or reporter.question_text([], {}, facts, ""),
            facts,
            entry=None,
            entry_for_must=target,
            must=must,
            card_view="none",
            step_cards=cards,
            verdict=[v for v in verdict if v],
            suggestions=reporter.challenge_suggestions(target) if target is not None else None,
        )
        return None

    def _report(self, session: Session, on: Optional[LedgerEntry]) -> Iterator[dict]:
        """Make a design's operator report (PDF) and return its download card.

        The report is built here once (a tool step, so its pages are known and it shows in the
        trace); the card's link has the server build it again for the download.
        """
        from gemini_agent import report_pdf

        base = on or session.chosen
        if base is None:
            return None
        did = reporter.design_id(base)
        if not any(reporter.design_id(e) == did for e in session.ledger):
            workbench.open_design(session, did)  # a search's candidate: into the tabs first
        found = yield from self._tool_step(
            "report",
            f"Write the operator's report of {did}",
            f"report_pdf({did!r})",
            [("report_pdf", {"design": did}, lambda: report_pdf.build(session, did))],
        )
        pdf = found[0]
        if isinstance(pdf, ToolError):
            return None
        pages = max(1, pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages"))
        url = "/api/report.pdf?" + urllib.parse.urlencode(
            {"threadId": session.thread_id, "id": did}
        )
        card = {
            "id": did,
            "code": base.alternative.code,
            "name": base.alternative.name,
            "url": url,
            "file": report_pdf.filename(base),
            "pages": pages,
            "kb": round(len(pdf) / 1024),
            "sections": list(report_pdf.SECTIONS),
        }
        facts = reporter.Facts("")
        draft = (
            f"The operator's report of {did} is ready: {facts.put(str(pages))} A4 pages "
            f"({', '.join(s if s[1:2].isupper() else s.lower() for s in report_pdf.SECTIONS)}). "
            "Download it from the card."
        )
        return {"draft": draft, "facts": facts, "card": card}

    def _plans_of(self, session: Session, entry: Optional[LedgerEntry]) -> list:
        """Return each design the reply may name with whether one unit can be out (code's)."""
        pool = list(session.ledger[-6:]) + list(session.candidates or [])
        if entry is not None:
            pool.append(entry)
        out, seen = [], set()
        for e in pool:
            a = e.alternative
            if a.code in seen or not a.n_doublets:
                continue
            seen.add(a.code)
            firm = reporter.firm_view(e) or {}
            short, cases = firm.get("short"), len(firm.get("cases") or [])
            held = bool(a.reliable) and not short
            words = f"{short} of {cases} one-unit-out cases short" if cases else "not checked"
            out.append((a.code, a.uid, held, words))
        return out

    def _card_of(self, entry: LedgerEntry, view: str) -> dict:
        """Return a design's card as a reply would show it (a plan shows each step's)."""
        card = reporter.result_card(entry)
        if view == "full" and entry.alternative.picks and self._session.candidates:
            card["picks"] = reporter.picks_view(self._session.candidates)
        return card

    def _failure(
        self,
        session: Session,
        failures: Sequence[parameters.Failure],
        message: str,
        on: Optional[LedgerEntry] = None,
    ) -> Iterator[dict]:
        """Run a design (the current one by default) through the failures, and each remedy."""
        base = on or session.chosen
        if base is None or not failures:
            return None
        names = ", ".join(reliability.unit_words(f.unit) for f in failures)
        found = yield from self._tool_step(
            "simulate",
            f"Run {reporter.design_id(base)} with {names} out",
            "simulate_failure(" + ", ".join(f.unit for f in failures) + ")",
            [
                (
                    "simulate_failure",
                    {
                        "alternative": base.alternative.code,
                        "failures": [f.__dict__ for f in failures],
                    },
                    lambda: reliability.run_failure(base, failures, session.assumptions),
                )
            ],
        )
        result = found[0]
        if isinstance(result, ToolError):
            return None
        if base.alternative.n_doublets == 1:
            for e in result["events"]:
                e["assumed"] = ""  # one doublet: no doubt which
        facts = reporter.Facts(message)
        plan = reliability.reliable_of(base, session.candidates)
        draft = reliability.failure_text(result, facts, plan if plan is not base else None)
        result["reliable_plan"] = (
            reporter.design_id(plan) if plan is not None and plan is not base else None
        )
        result["message"] = message[:300]
        session.failures = (session.failures + [result])[-20:]  # for the operator's report
        self._summary["failure"] = {
            "units": [f.unit for f in failures],
            "needed": result["needed"],
            "best": result["best"],
        }
        return {
            "draft": draft,
            "facts": facts,
            "must": reliability.failure_must(result),
            "card": result,
        }

    def _uncertainty(self, session: Session, message: str) -> Iterator[dict]:
        """Vary prices, costs and the reservoir around the current design; ranges by code."""
        base = session.chosen
        if base is None:
            return None
        keys = [
            "gas_price",
            "electricity_price",
            "carbon_price",
            "capex",
            "discount_rate",
            "reservoir_temp",
            "heat_return",
            "permeability",
        ]
        known = {p["key"]: dict(p) for p in workbench.sensitivity_parameters()["parameters"]}
        # Each price's range holds the chat's own price (set in Economics), so the runs vary
        # around the design's case and not beside it.
        prices = engine.prices_for(session.assumptions, base.brief)
        for key, now in (
            ("gas_price", prices.gas_eur_per_mwh),
            ("electricity_price", prices.electricity_eur_per_mwh),
            ("carbon_price", prices.carbon_eur_per_t),
            ("discount_rate", prices.discount_rate),
        ):
            if key in known:
                known[key]["low"] = min(known[key]["low"], now)
                known[key]["high"] = max(known[key]["high"], now)
        # Each input is drawn most likely at the design's own value (a change 0, a factor 1, the
        # chat's prices), so the runs centre on the case and its percentile can be said.
        params = [
            {
                "key": k,
                "low": known[k]["low"],
                "high": known[k]["high"],
                "mode": workbench.base_value(base, session.assumptions, k),
            }
            for k in keys
            if k in known
        ]
        result = yield from self._tool_step(
            "sensitivity",
            f"Vary {len(params)} inputs around {reporter.design_id(base)}",
            f"sensitivity({len(params)} inputs, 200 samples)",
            [
                (
                    "sensitivity",
                    {"design": reporter.design_id(base), "parameters": params},
                    lambda: workbench.sensitivity(
                        session,
                        workbench.design_id(base),
                        params,
                        ["lcoe", "npv_meur", "co2_saving_pct"],
                        samples=200,
                    ),
                )
            ],
        )
        out = result[0]
        if isinstance(out, ToolError):
            return None
        facts = reporter.Facts(message)
        card = reliability.uncertainty_card(out, known)
        return {"draft": reliability.uncertainty_text(card, facts), "facts": facts, "card": card}

    def _decision(self, session: Session, message: str) -> Iterator[dict]:
        """Set the options side by side for a client, with a short memo, every figure by code."""
        table = yield from self._step(
            "decision",
            "Set out the options for the decision",
            "tool",
            "decision_table(gas, recommended, picks)",
            lambda: reliability.decision(session),
            after=lambda t: {"options": len((t or {}).get("rows") or [])},
        )
        if not table:
            return None
        facts = reporter.Facts(message)
        return {"draft": reliability.decision_text(table, facts), "facts": facts, "card": table}

    def _compare(self, session: Session, names: Sequence[str], message: str) -> Iterator[dict]:
        """Set the designs a message names side by side, every figure from the ledger."""
        found, missing = reliability.resolve(names, session)
        if len(found) < 2 and session.chosen is not None and found:
            if all(e is not session.chosen for e in found):
                found = [session.chosen] + found
        if len(found) < 2:
            return None
        table = yield from self._step(
            "compare",
            "Set the designs side by side",
            "tool",
            "compare(" + ", ".join(reporter.design_id(e) for e in found) + ")",
            lambda: reliability.compare(found, session.assumptions or None),
            after=lambda t: {"designs": [d["id"] for d in t["designs"]], "missing": missing},
        )
        facts = reporter.Facts(message)
        draft = reliability.compare_text(table, facts)
        if missing:
            draft += "\n\nNot found: " + ", ".join(missing) + "."
        return {"draft": draft, "facts": facts, "card": table}

    def _lookup(
        self, session: Session, brief: DesignBrief, keys: List[str], facts: reporter.Facts
    ) -> Iterator[dict]:
        """Look up the values a question asks for; return the sheet, the draft and key values."""
        yield ev.step_started(
            "lookup", "Look up the values", "tool", f"lookup({', '.join(keys) or '?'})"
        )
        start = time.perf_counter()
        demand = None
        profiles = session.project.has_heat_profile or bool(brief.annual_heat_gwh)
        if profiles and set(keys) & {"heat_demand", "cool_demand", "peak_heat", "peak_cool"}:
            out = yield from self._tool(
                "demand_summary",
                {"brief": brief.model_dump()},
                lambda: engine.demand_summary(brief.project_id),
            )
            demand = None if isinstance(out, ToolError) else out
        sheet = lookup.project_facts(session.project, brief, demand)
        on = self._lookup_on or session.chosen
        if on is not None:
            sheet.update(lookup.design_facts(on))
            if set(keys) & {"investor", "failure_costs"}:  # computed only when asked
                sheet.update(lookup.money_facts(on, session.assumptions))
        yield ev.step_finished(
            "lookup",
            time.perf_counter() - start,
            found=[k for k in keys if k in sheet],
            missing=[k for k in keys if k not in sheet],
        )
        design = on.alternative.code if on is not None else ""
        draft = reporter.question_text(keys, sheet, facts, design)
        must = [
            ("~" if k in lookup.LONG_FACTS else "") + str(sheet[k].value)
            for k in keys
            if k in sheet
        ] + sorted({f for k in keys if k in sheet for f in FILE_NAME.findall(sheet[k].source)})
        return sheet, draft, must

    def _code_values(
        self,
        keys: Sequence[str],
        sheet: Dict[str, lookup.Fact],
        must: Sequence[str],
        facts: reporter.Facts,
    ) -> Tuple[List[str], List[str]]:
        """Return the asked values as code writes them ("In short" lines), and the values to keep.

        The design is the one the lookup read (``_lookup``). A value its line states whole no
        longer has to be repeated in the model's words (the line leads the reply); a long
        value given only by its headline still does.
        """
        on = self._lookup_on or self._session.chosen
        lines = lookup.value_lines(keys, sheet, on)
        if not lines:
            return [], list(must)
        whole = {
            ("~" if k in lookup.LONG_FACTS else "") + str(sheet[k].value)
            for _, k in lines
            if not sheet[k].short
        }
        self._summary["code_facts"] = {
            "design": reporter.design_id(on),
            "keys": [k for _, k in lines],
        }
        return [facts.put(line) for line, _ in lines], [m for m in must if m not in whole]

    def _search(
        self, session: Session, query: str, attached: bool = False, own: bool = False
    ) -> Iterator[dict]:
        """Search GEMINI's documentation and this conversation's files (a tool step).

        ``attached`` searches only the files the user attached to this conversation; with
        ``own``, only the project's own documents instead.
        """
        label = "Search the attached files" if attached else "Search the documents"
        label = "Search the project's documents" if own else label
        yield ev.step_started("docs", label, "tool", f"search_docs({query!r})")
        start = time.perf_counter()
        hits: List[object] = []
        error = ""
        try:
            where = None if attached else project_key(session)
            thread = project_key(session) if own else session.thread_id
            hits = self.docs.search(
                query, k=4, thread_id=thread, only_attached=attached or own, project=where
            )
            if not (attached or own):
                # The uploads and the project's documents compete with GEMINI's whole corpus;
                # the best matching passage of each is always offered.
                seen = {(p.source, p.section) for p in hits}
                own = []
                for key in (session.thread_id, where):
                    for p in self.docs.search(query, k=1, thread_id=key, only_attached=True):
                        if p.score > 0 and (p.source, p.section) not in seen:
                            own.append(p)
                            seen.add((p.source, p.section))
                hits = hits[: 4 - len(own)] + own
        except Exception as err:  # noqa: BLE001 - search is a help, never a reason to fail
            error = f"{type(err).__name__}: {err}"
        backend = self.docs.info().get("last_backend")
        self._tools["calls"] += 1
        content = {"backend": backend, "passages": [p.as_dict() for p in hits]}
        if error:
            content = {"error": error}
            self._tools["failed"] += 1
        yield from ev.tool_call(
            uuid.uuid4().hex[:10],
            "search_docs",
            json.dumps({"query": query, "threadId": session.thread_id, "only_attached": attached}),
            json.dumps(content, default=str),
        )
        flagged = [p for p in hits if p.suspicious]
        new = [p for p in flagged if p.source not in session.flagged]
        if new:  # once per file and conversation; the source cards keep their badge
            self._warnings.append(reporter.injection_text(new))
            session.flagged.extend(sorted({p.source for p in new}))
        if flagged:
            self._summary["injection_warned"] = True
        yield ev.step_finished(
            "docs",
            time.perf_counter() - start,
            passages=len(hits),
            suspicious=len(flagged),
            backend=backend,
        )
        return hits

    # ---------------------------------------------------------------- plumbing

    def _deep(self):
        """Return the reasoning model client (it may be created here, on first use)."""
        if self.router is not None:
            return self.router.reasoning(self._device, self._size)
        r = self._reasoning_llm
        if r is None:
            return self._fast
        return r if hasattr(r, "structured") else r()

    def _answerer(self):
        """Return the model that writes the replies for this run's device and mode."""
        if self.router is not None:
            return self.router.answerer(self._device, self._reasoning, size=self._size)
        a = self._answer_llm
        if a is not None:
            return a if hasattr(a, "structured") else a()
        return self._deep() if self._reasoning else self._fast

    def _device_of(self, llm) -> str:
        """Return where a model client runs: ``gpu``, ``cpu`` or ``auto`` (unknown)."""
        if self.router is not None:
            return self.router.device_of(llm, self._device)
        return getattr(llm, "device", "auto")

    def _models_line(self) -> str:
        """Return the models in use now, for the self card ("which model are you?")."""
        fast, writer = self._fast, self._answerer()
        where = self._device_of(writer)
        where = {"gpu": "on the GPU", "cpu": "on the CPU"}.get(where, "")
        mode = "on" if self._reasoning else "off"
        return (
            f"{fast.model} reads each message; {writer.model} writes the answers {where}; "
            f"reasoning mode is {mode}."
        ).replace("  ", " ")

    def _load_models(self) -> Iterator[dict]:
        """Load this run's models first when they are not in memory, a row each (``warmup``).

        Nothing is shown when they are loaded, or when Ollama does not answer (the first call
        says so). The load is not one of the turn's model calls: it is kept apart, in the
        summary's ``model_loads``.
        """
        if self.warmup is None:
            return
        loads = []
        for load in self.warmup.missing(self._device):
            yield ev.step_started("load_model", load.label(), "tool", None)
            start = time.perf_counter()
            ok = self.warmup.ensure(load)
            seconds = time.perf_counter() - start
            extra = {"model": load.model, "device": load.device}
            if load.size_bytes:
                extra["size_gb"] = round(load.size_bytes / 1e9, 2)
            if not ok:
                extra.update(failed=1, error=load.message, hint=load.hint)
            yield ev.step_finished("load_model", seconds, **extra)
            loads.append({"model": load.model, "seconds": round(seconds, 3), "ok": ok})
        if loads:
            self._summary["model_loads"] = loads

    def _think(self, read: intake.IntakeResult, message: str) -> Iterator[dict]:
        """Decide whether this message needs reasoning (the reader's judgement within rules)."""
        on, decision = policies.wants_reasoning(read, message)
        self._reasoning = on
        meta = dict(decision.meta(), on=on)
        if decision.decided_by == "model":
            meta["model"] = getattr(self._fast, "model", "")
        label = "Reason it through" if on else "Answer without reasoning"
        yield ev.step_started("think", label, "plan", None)
        yield ev.step_finished("think", 0.0, **meta)
        self._summary["decided_by"]["think"] = decision.decided_by

    def _think_harder(self, why: str) -> Iterator[dict]:
        """Turn reasoning on in the middle of a run, when code finds it is needed after all."""
        self._reasoning = True
        yield ev.step_started("think", "Reason it through", "plan", None)
        yield ev.step_finished("think", 0.0, decided_by="rules", reason=why, on=True)
        self._summary["decided_by"]["think"] = "rules"

    def _shortlist(self, chosen: LedgerEntry) -> List[LedgerEntry]:
        """Return the designs the chat's comparison chart shows.

        The chosen one, the next two of the search, the lowest-CO2 one and the gas reference.
        """
        session = self._session
        mine = reporter.lineage(chosen.alternative.code, session.candidates)
        valid = [
            e
            for e in session.candidates
            if e.alternative.role == "candidate"
            and e.alternative.code != chosen.alternative.code
            and not (e.alternative.stage == 2 and e.alternative.parent in mine)
        ]
        valid.sort(key=lambda e: e.economics.lcoe_eur_per_mwh or 0.0)
        out = [chosen] + valid[:2]
        greenest = min(valid, key=lambda e: e.economics.co2_t_per_year or 0.0, default=None)
        if greenest is not None and greenest not in out:
            out.append(greenest)
        if session.reference is not None:
            out.append(session.reference)
        return out

    def _model_decides(self) -> bool:
        return self._reasoning and not self._deep_down

    def _asked_cards(self) -> Iterator[dict]:
        """Send the cards the message asked to see that the reply has not shown (3 Nov).

        "How did you arrive at this?" shows the last search's card again; "put them side by
        side" the latest designs compared. Each once a turn.
        """
        s = self._session
        if "search" in self._show and not self._searched_now and s.searches:
            card = s.searches[-1].get("card")
            if card:
                yield ev.custom("candidates", {**card, "show": True})
        if "comparison" in self._show and s.chosen is not None:
            designs = answering.latest_designs(s.ledger, s.chosen)
            if s.candidates:
                designs = self._shortlist(s.chosen)
            if len(designs) >= 2:
                yield ev.custom("comparison", reporter.comparison(designs, s.chosen))
        self._show = set()

    # --------------------------------------------------------- the chat's thread

    @staticmethod
    def _label(e: LedgerEntry) -> str:
        """Return a design as the thread names it: "A1 · 1D-HP-EC-N1 (best overall)"."""
        a = e.alternative
        what = [engine.PICK_NAMES[k] for k in a.picks if k in engine.PICK_NAMES]
        if a.role == "what_if":
            what = ["what-if" + (f": {e.change_label}" if e.change_label else "")]
        elif a.role == "user":
            what = ["the user's own design"]
        name = reporter.design_id(e)
        return name + (f" ({', '.join(what)})" if what else "")

    def _thread_names(self, session: Session) -> Dict[str, str]:
        """Return every handle and code of the chat's designs, with the thread's label."""
        pool = list(session.ledger) + list(session.candidates or [])
        for srch in session.searches or []:
            pool += list(srch.get("candidates") or [])
        names: Dict[str, str] = {}
        for e in reversed(pool):  # the latest of a code wins
            a = e.alternative
            if a.role in ("reference", "same", "failed"):
                continue
            label = self._label(e)
            if a.uid:
                names[a.uid] = label
            if a.code:
                names[a.code] = label
        return names

    def _thread_context(self, session: Session, kind: str = "reading") -> str:
        """Return the chat's thread for a prompt of this ``kind``.

        ``reading``: the planner's, about 2,400 characters; ``short``: the small reader's and the
        short calls', about 1,000; ``answer``: the answerer's, about 5,600. On the CPU each is
        about half: there a prompt's every token costs time (about 0.01 s on 8 threads).
        """
        cpu = self._device == "cpu" or (
            self.router is not None and self._device_of(self._deep()) == "cpu"
        )
        if kind == "short":
            return session.thread.text(
                session.history,
                exchanges=2,
                user_chars=160,
                reply_chars=120 if cpu else 200,
                lines=1 if cpu else 3,
                limit=600 if cpu else 1000,
            )
        if kind == "answer":
            return session.thread.text(
                session.history,
                exchanges=2 if cpu else 3,
                user_chars=300,
                reply_chars=400 if cpu else 600,
                lines=6 if cpu else 12,
                limit=2800 if cpu else 5600,
                first=2,
            )
        return session.thread.text(
            session.history,
            exchanges=2 if cpu else 3,
            user_chars=220,
            reply_chars=240 if cpu else 320,
            lines=3 if cpu else 8,
            limit=1200 if cpu else 2400,
        )

    def _note_thread(self, session: Session, said: str, reply: str, ledger_before: int) -> None:
        """Note the turn in the chat's thread: what was done, the design discussed, the list."""
        behaviour = str(self._summary.get("behaviour") or "")
        new = [e for e in session.ledger[ledger_before:] if e.alternative.role != "reference"]
        focus: Optional[LedgerEntry] = None
        what_ifs = [e for e in new if e.alternative.role == "what_if"]
        if what_ifs:
            focus = what_ifs[-1]
            did = f"ran the what-if {self._label(focus)}"
        elif self._searched_now and session.chosen is not None:
            focus = session.chosen
            did = f"ran a design search and picked {self._label(focus)}"
        elif new:
            focus = new[-1]
            did = f"showed {self._label(focus)}"
        else:
            did = THREAD_DID.get(behaviour, behaviour or "replied")
            one = self._lookup_on or self._focus
            if one is None and len(self._picked) == 1:
                one = self._picked[0]
            if one is None:
                named = (self._summary.get("parameters") or {}).get("designs") or []
                found = reliability.resolve(list(named), session)[0] if named else []
                if not found and self._message:
                    found = named_in(self._message, session)
                if len(found) == 1:
                    one = found[0]
            if one is not None:
                focus = one
                did += f" about {reporter.design_id(one)}"
            elif self._summary.get("failure"):
                did += " (a unit-out run)"
        names = self._thread_names(session)
        listed = designs_named(reply, names)
        shown = [x.split(" (")[0] for x in session.thread.shown]
        if focus is None and behaviour == "answer" and len(shown) >= 2 and listed:
            # A question about the last list that named none of it ("which of the two would
            # you pick?"): the design the answer leads with is the one under discussion, so
            # "that one" next is it (5 Nov: the earlier focus was taken).
            lead = listed[0].split(" (")[0]
            if lead in shown:
                found = reliability.resolve([lead], session)[0]
                if found:
                    focus = found[0]
        if focus is None and not session.thread.focus and session.chosen is not None:
            focus = session.chosen
        listed_what = "designs the last reply named, in its order"
        pending = session.pending or {}
        question = ""
        if pending:
            options = [str(o) for o in pending.get("options") or []]
            if pending.get("kind") == "decision":
                options = [str(c[0]) for c in pending.get("choices") or []]
            asked = {
                "confirm": "the inputs card: run the design with these inputs, or say what to "
                "change",
                "which_design": "which design the question is about",
            }.get(str(pending.get("kind")), "")
            question = asked or (thread_flat(reply, 200) if reply else str(pending.get("kind")))
            if options:
                question += " Options: " + "; ".join(
                    f"{i}. {thread_flat(o, 90)}" for i, o in enumerate(options[:6], 1)
                )
            if len(options) >= 2 and len(listed) < 2:
                listed, listed_what = [thread_flat(o, 90) for o in options], "options to pick"
        stated = []
        corrected = bool(CORRECTED.match(thread_flat(reply, 80)))
        for p in self._premises_said:
            note = " (Dioscuri corrected it)" if corrected else ""
            stated.append(f"«{thread_flat(p, 100)}»{note}")
        session.thread.note(
            session.turns,
            said,
            reply,
            did,
            (self._label(focus), reporter.design_id(focus)) if focus is not None else None,
            listed,
            listed_what,
            question,
            stated,
        )

    def _reply(
        self,
        behaviour: str,
        text: str,
        facts: Optional[reporter.Facts],
        entry: Optional[LedgerEntry] = None,
        suggestions: Optional[List[str]] = None,
        passages: Sequence[object] = (),
        must: Sequence[str] = (),
        draft: bool = True,
        write: bool = True,
        sheet: Optional[Dict[str, lookup.Fact]] = None,
        kinds: Sequence[str] = answering.KINDS,
        off_topic: bool = False,
        entry_for_must: Optional[LedgerEntry] = None,
        data: Sequence[files.FileView] = (),
        missing: Sequence[str] = (),
        run: bool = False,
        route_after: bool = False,
        card_view: str = "full",
        step_cards: Sequence[Tuple[str, dict]] = (),
        card_extra: Optional[dict] = None,
        verdict: Sequence[str] = (),
        values: Sequence[str] = (),
        question: bool = False,
    ) -> Iterator[dict]:
        """Send the reply: the answerer writes it from ``text`` and the context, code checks it.

        ``text`` is the checked template. With ``draft`` it is given to the model as the
        answer to keep (after a tool run or a lookup); without, it is only the fallback (the
        model answers from the context). ``write=False`` sends the template as it is (errors,
        rejections, a stopped model). ``off_topic``: the reader found the message unrelated, so
        general background is declined. ``entry_for_must``: a design whose key values the
        answer must keep without showing its card again. ``data``: files the chat shows, which
        the answerer describes (``missing``: named files that are not on the server). Returns
        ``"choice"`` when the model asked the user to pick what they meant, and ``"design"``
        (nothing sent) when ``run`` let the model ask for a design run instead. ``card_view``:
        the design card after the text: ``"full"`` (a design run), ``"compact"`` (a what-if: one row
        against the design it changed) or ``"none"`` (an answer about a design the chat shows).
        ``step_cards``: more cards after it (a plan's steps: ``(event name, payload)``);
        ``card_extra``: fields added to the design card (a what-if's new search).
        ``values``: the values asked for as code wrote them (``lookup.value_lines``): the model
        gets them as a block, and they lead the reply under "In short" unless the checked
        template, which states them, is shown instead. ``question``: the reply answers a
        question (``_talk``), so the reply check may read it (``_check_reply``).
        """
        reply: Optional[answering.Reply] = None
        pack: List[answering.Block] = []
        cited: List[dict] = []
        if write and facts is not None:
            if entry_for_must is not None and not must:
                must = reporter.key_values(entry_for_must, "design")
            reply, pack = yield from self._write(
                behaviour,
                text,
                facts,
                entry,
                passages,
                must,
                draft,
                sheet,
                kinds,
                off_topic,
                data,
                missing,
                run,
                values,
                question,
            )
            if reply.action == "design":
                if self._session.chosen is not None and not (
                    yield from self._route(self._session, self._message)
                ):
                    # A design exists and the focused question says the message asks about it
                    # ("is this a good design?"): answer it, with no run offered this time.
                    return (
                        yield from self._reply(
                            behaviour,
                            text,
                            facts,
                            entry=entry,
                            suggestions=suggestions,
                            passages=passages,
                            must=must,
                            draft=draft,
                            sheet=sheet,
                            kinds=kinds,
                            off_topic=off_topic,
                            entry_for_must=entry_for_must,
                            data=data,
                            missing=missing,
                            card_view=card_view,
                            step_cards=step_cards,
                            card_extra=card_extra,
                            verdict=verdict,
                            values=values,
                            question=question,
                        )
                    )
                return "design"
            if reply.kind == "unclear":
                # The answerer read no request in it (cut off, garbled, a bare number): the one
                # reply for such messages, which runs and changes nothing.
                return (yield from self._unreadable(self._session, self._message, self._language()))
            if route_after and reply.kind == "answer" and reply.scope == "project":
                # The reader called it unrelated, the answerer did not: ask whether it wants a
                # design before showing an answer the small model may have improvised.
                if (yield from self._route(self._session, self._message)):
                    return "design"
            text = reply.text
            if not reply.fallback:
                # "[doc1]" in the model's text becomes "[^1]", the number of its source card.
                text, cards = answering.cite(reply.text, pack, reply.used)
                cited = [self._card(b.passage, b.kind) for b in cards]
                behaviour = KIND_BEHAVIOUR.get(reply.kind, behaviour)
                if behaviour == "refuse" and reply.kind == "answer":
                    behaviour = "answer"
        past = reporter.caps_past(
            entry if entry is not None else entry_for_must, facts or reporter.Facts()
        )
        if values and not (reply is not None and reply.fallback):
            # The values asked for, as code wrote them, first (the template states them itself).
            verdict = [*values, *verdict]
        if past:  # a cap broken on request is said first, whatever the reply says (3 Nov)
            verdict = [past, *verdict]
        if verdict:
            # The conclusions code computed (the pick changed or not, N-1 kept or lost, ...),
            # above the model's words: they can be worded, never contradicted.
            text = "**In short**\n" + "\n".join(f"- {v}" for v in verdict) + "\n\n" + text
        text += reporter.left_out_text(self._left_out, facts or reporter.Facts())
        text += "".join(self._warnings)
        ungrounded = answering.unsourced(text, facts) if facts else []
        yield from self._step(
            "report",
            "Check the answer's numbers",
            "report",
            None,
            lambda: None,
            after=lambda _: {"ungrounded": ungrounded},
        )
        yield from ev.text_message(uuid.uuid4().hex[:10], text)
        if entry is not None and card_view != "none":
            card = reporter.result_card(entry)
            if card_view == "compact":
                base = self._session.chosen
                card["view"] = "compact"
                if base is not None and base is not entry:
                    card["against"] = reporter.result_card(base)
            elif entry.alternative.picks and self._session.candidates:
                card["picks"] = reporter.picks_view(self._session.candidates)
            card.update(card_extra or {})
            yield ev.custom("result", card)
            yield ev.custom("checks", reporter.checks_summary(entry))
            designs = answering.latest_designs(self._session.ledger, entry)
            if entry.alternative.role == "chosen" and self._session.candidates:
                designs = self._shortlist(entry)
            if len(designs) >= 2 and card_view == "full" and "comparison" in self._show:
                # Side by side only when asked: the Compare tab has them (3 Nov).
                yield ev.custom("comparison", reporter.comparison(designs, entry))
                self._show.discard("comparison")
        yield from self._asked_cards()
        for name, payload in step_cards:
            yield ev.custom(name, payload)
        if entry is not None:
            self._summary.update(
                verified=entry.verification.passed,
                heat_coverage=entry.year.heat_coverage,
                cool_coverage=entry.year.cool_coverage,
                lcoh=entry.economics.lcoh_eur_per_mwh,
                alternative=entry.alternative.code,
            )
        if reply is not None and reply.fallback:
            cited = [self._card(p.as_dict()) for p in passages if not p.suspicious][:2]
            cited += [b.passage for b in pack if b.kind == "data"]
        flagged = [self._card(p.as_dict()) for p in passages if p.suspicious]
        if cited or flagged:
            yield ev.custom("sources", cited + flagged)
        self._summary["sources"] = [f"{c['source']} ({c['section']})" for c in cited]
        if reply is not None and reply.follow_ups and reply.kind == "answer":
            suggestions = reply.follow_ups  # off-topic replies keep the standard suggestions
        about = self._focus or (self._session.chosen if self._session is not None else None)
        if about is not None and behaviour != "refuse" and not off_topic and suggestions:
            # Tested follow-ups in place of the model's or the template's (a click must work).
            asked = [h.get("user", "") for h in self._session.history] + [self._message]
            tested = suggest.pick(
                self._session,
                about,
                self._topic_keys,
                str(self._summary.get("intent") or ""),
                str(self._summary.get("language") or "en"),
                asked,
            )
            if tested:
                if reply is not None and reply.follow_ups:
                    self._summary["model_follow_ups"] = list(reply.follow_ups)
                suggestions = tested
        if suggestions and not (reply is not None and reply.kind == "clarify"):
            yield ev.custom("suggestions", suggestions)
        self._summary.update(behaviour=behaviour, answer=text, ungrounded=ungrounded)
        if reply is not None and reply.kind == "clarify":
            return (yield from self._ask_choice(reply))
        return None

    def _write(
        self,
        behaviour: str,
        text: str,
        facts: reporter.Facts,
        entry: Optional[LedgerEntry],
        passages: Sequence[object],
        must: Sequence[str],
        draft: bool,
        sheet: Optional[Dict[str, lookup.Fact]],
        kinds: Sequence[str] = answering.KINDS,
        off_topic: bool = False,
        data: Sequence[files.FileView] = (),
        missing: Sequence[str] = (),
        run: bool = False,
        values: Sequence[str] = (),
        question: bool = False,
    ) -> Iterator[dict]:
        """Run the answerer on the context pack; return the checked reply and the pack.

        ``values``: the code-written value lines (a ``values`` block, and sentences the claim
        checker takes as checked). ``question``: a reply to a question, which the reply check
        may read and have rewritten once. On a hard turn on a GPU the answer call thinks first
        (``policies.thinks``).
        """
        session = self._session
        self._template = text
        llm = self._answerer()
        if any(v.kind == "image" for v in data) and not answering.VISION.search(llm.model):
            llm = self._deep()  # the reasoning model can see images; the small reader cannot
        # Only what the message needs goes in: the whole self card when it is about Dioscuri,
        # the designs in full when it is about them (one line each otherwise).
        message = self._message or ""
        about_us = answering.about_us(message) or self._summary.get("intent") == "about"
        if draft or not about_us:
            pack = [answering.short_self(self._models_line())]
        else:
            pack = [answering.self_block(self._models_line())]
        # "Hello" or "who are you" (matched by pattern) needs the self card, not the project's
        # numbers: fewer tokens, and no reservoir depth to misquote in a greeting.
        light = self._summary.get("screened") and not (draft or data or passages)
        if not sheet and not draft:  # the project's facts, each with where it comes from
            sheet = lookup.project_facts(session.project, session.brief, None)
        if not light:
            pack.append(answering.project_block(session.project, session.brief, sheet))
            # The design the question is about goes first, in full: one the words named
            # ("the cheapest") is a search candidate, not in the ledger (4 Nov: its cost was
            # then removed as unsupported).
            current = entry or self._focus or self._lookup_on or session.chosen
            designs = answering.latest_designs(session.ledger, current)
            if draft and entry is not None:
                # A design report: this design in full; the earlier ones in a line, so the
                # model does not quote an older design's code or numbers for the new one.
                pack.append(answering.design_block(entry, chosen=True))
                ops = answering.operations_block(entry, message)
                if ops is not None:
                    pack.append(ops)
                base = session.chosen
                if getattr(entry, "change_label", "") and base is not None and base is not entry:
                    # A what-if: how the design itself runs too, so its own figures (its stop
                    # dates) are never taken for the what-if's.
                    ops = answering.operations_block(base, message)
                    if ops is not None:
                        pack.append(ops)
                others = [e for e in designs if e is not entry]
                if others:
                    pack.append(answering.designs_line(others, None))
            elif designs and (
                entry is not None
                or answering.DESIGN_TALK.search(message)
                or answering.COST_TALK.search(message)
                or answering.GEMINI_TALK.search(message)
            ):
                pack += [answering.design_block(e, chosen=e is current) for e in designs]
                if current is not None:
                    ops = answering.operations_block(current, message)
                    if ops is not None:
                        pack.append(ops)
                if current is not None and answering.GEMINI_TALK.search(message):
                    gem = answering.gemini_block(current)
                    if gem is not None:
                        pack.append(gem)
                decided = answering.decisions_block(current, session.candidates)
                if decided is not None and entry is None:
                    pack.append(decided)  # each choice against its best alternative
                searched = answering.search_block(
                    session.candidates, search=session.searches[-1] if session.searches else None
                )
                if searched is not None and entry is None:  # a design reply has its own card
                    pack.append(searched)
                if current is not None:  # money in any language ("terugverdientijd", "IRR")
                    pack.append(answering.economics_block(current, session.assumptions))
            elif designs:
                pack.append(answering.designs_line(designs, current))
                if current is not None:
                    pack.append(answering.economics_block(current, session.assumptions))
                    decided = answering.decisions_block(current, session.candidates)
                    if decided is not None:
                        pack.append(decided)
                searched = answering.search_block(
                    session.candidates,
                    search=session.searches[-1] if session.searches else None,
                    short=True,
                )
                if searched is not None:  # how the designs were found, whatever the words
                    pack.append(searched)
                if current is not None:
                    # How the current design runs goes in with any project question: "we lose
                    # one production pump" matched no pattern and got "the town stays warm"
                    # (7.2 MW short in truth) from a model with only the design's name.
                    ops = answering.operations_block(current, message)
                    if ops is not None:
                        pack.append(ops)
        runs = answering.runs_block(session)
        if runs is not None:
            pack.append(runs)
        changed = answering.changes_block(session)
        if changed is not None:  # each what-if before → after, by code
            pack.append(changed)
        noted = self._notes_block(session)
        if noted is not None:
            # What the user asked to remember: every reply, never cut, and first (5 Nov: at the
            # end of a long context, "what does heat cost?" was answered without the name).
            pack.insert(0, noted)
        pack += self._state_blocks(session, light)
        thread = self._thread_context(session, "answer")
        state = getattr(session, "state", None)
        pointer = chat_state.pointer_text(state, self._message or "")
        if thread and pointer:
            # A question about the chat's turns ("what were we discussing before the weather?"):
            # the model says before or after, code picks the turn (5 Nov: the 9B named the turn
            # next to it), and it ends the history, which the answer prompt says answers such
            # questions. Any other message that shares a word with a turn adds nothing.
            asked, call = chat_state.relation(state, self._message or "", self._fast)
            if call is not None:
                self._calls.append(call)
                yield ev.custom("usage", call.as_dict())
            if asked:
                thread += "\n" + pointer + f" The turn this message asks about is {asked}."
        earlier = answering.history_block(session.history, text=thread)
        if earlier is not None:
            pack.append(earlier)
        pack += answering.passage_blocks(passages, [a["name"] for a in session.attachments])
        pack += [answering.data_block(v, i + 1) for i, v in enumerate(data)]
        for name in missing:
            pack.append(
                answering.Block(
                    f"data{len(pack)}",
                    "data",
                    f"{name}: the project lists this file, but it is not on the server, so "
                    "nothing in it can be shown or used.",
                    name,
                )
            )
        if draft:
            pack.append(answering.Block("draft", "draft", text, "the checked answer"))
            if entry is not None and not must:
                must = reporter.key_values(entry, behaviour)
            must = [m for m in must if answering.contains(text, m)]
        if values:
            # The values asked for, as code wrote them: the reply explains them, never restates
            # them with another number (they lead it, under "In short").
            lines = "\n".join("- " + v for v in values)
            pack.append(answering.Block("values", "values", lines, "shown above the reply"))
        # After a tool run the reply must report it; questions may also be unclear or off-topic.
        kinds = ("answer",) if draft else kinds
        yield ev.step_started(
            "answer",
            "Write the answer",
            "model",
            f"answer({', '.join(b.id for b in pack if b.id != 'self')})",
        )
        start = time.perf_counter()
        # A hard turn (reasoning on) on a GPU: the answer call thinks first (``DIOSCURI_THINK``).
        think = self._reasoning and policies.thinks(self._device_of(llm))

        def ask(**more) -> answering.Reply:
            return answering.answer(
                llm,
                self._message,
                pack,
                facts,
                text,
                must,
                self._reasoning,
                kinds=kinds,
                own_project=session.project.id != "challenge",
                run=run,
                only=self._only_designs,
                costs=[
                    (
                        e.economics.lcoh_eur_per_mwh,
                        e.economics.lcoc_eur_per_mwh,
                        e.economics.lcoe_eur_per_mwh,
                    )
                    for e in list(session.ledger[-6:]) + ([entry] if entry is not None else [])
                    if e.economics.lcoe_eur_per_mwh
                ],
                plans=self._plans_of(session, entry),
                premises=self._premises,
                # No planner read this message (a why, a message about us), or it read nothing
                # to run: the answerer's own reading of its premises counts (4 Nov: "you said
                # heat costs 38 €/MWh, right?" got the right value but no "no" when the planner
                # missed the premise). Not with a change to run ("could we move the stop to
                # August?" got "Not quite, it is already ..." on 1 Nov).
                judge_premises=self._judges_premises(),
                drafted=draft,
                theirs=self._theirs,
                **more,
            )

        if self._deep_down and llm is self._deep():
            # The same model already failed this run: show the checked template at once.
            reply = answering.Reply(text, fallback=True, note="the reasoning model isn't available")
        else:
            reply = ask(think=think)
        # About Dioscuri or GEMINI, the simulator it is built on (its tab, its components): never
        # unrelated, whatever the small reader thought ("what does the GEMINI project tab show?").
        said = (reply.understood + " " + reply.text + " " + self._message).lower()
        about_us = "dioscuri" in said or "gemini" in said
        unrelated = self._on_topic is False or (off_topic and self._session.chosen is None)
        if (
            unrelated
            and not reply.fallback
            and reply.kind in ("answer", "clarify")
            # The reasoning model's reading decides whatever scope the answerer claims (2 Nov:
            # a mortgage question was declined in words but marked as a project answer).
            and (reply.scope in ("general", "out") or self._on_topic is False)
            and not about_us
        ):
            # Both readers find it unrelated (with a design in the chat the reasoning model's
            # reading decides: "why did you recommend that one?" is about the design, a film
            # is not; 2 Nov: a film was recommended, a share price "answered").
            reply.corrections.append("unrelated to the project and not about Dioscuri: declined")
            declined = text if behaviour == "refuse" else reporter.refuse_text(self._language())
            reply.kind, reply.scope, reply.text = "out_of_scope", "out", declined
            reply.follow_ups = []
        for call in reply.calls:
            self._calls.append(call)
            yield ev.custom("usage", call.as_dict())
        if reply.unavailable and not self._answer_down:
            self._answer_down = True
            yield ev.custom(
                "model_unavailable",
                {
                    "model": llm.model,
                    "error": reply.unavailable,
                    "fix": unavailable_hint(llm.model, reply.unavailable),
                    "reason": unavailable_reason(reply.unavailable),
                    "fallback": "template",
                },
            )
        meta = dict(reply.meta(), model=llm.model, device=self._device_of(llm))
        thought = [c for c in reply.calls if c.think]
        if thought:
            # The model's own thinking: its tokens and seconds, and whether the budget cut it;
            # the text (shortened) is in the call's usage record, never in the reply.
            meta["thinking"] = self._summary["thinking"] = {
                "ok": all(c.ok for c in thought),
                "thinking_tokens": sum(c.thinking_tokens for c in thought),
                "output_tokens": sum(c.output_tokens for c in thought),
                "cut": any(c.output_tokens >= answering.THINK_TOKENS for c in thought),
                "seconds": round(sum(c.seconds for c in thought), 3),
            }
        yield ev.step_finished("answer", time.perf_counter() - start, **meta)
        self._summary["decided_by"]["answer"] = meta["decided_by"]
        if reply.action == "design":
            return reply, pack  # the design runs next; this reply is never shown
        # A table's summary is written by code; what a document says is the model's reading.
        tables = any(v.kind not in ("text", "binary") for v in data)

        def recheck(r: answering.Reply) -> Iterator[dict]:
            return self._claims_on(
                llm, r, pack, text, draft, behaviour, facts, must, tables, values
            )

        yield from recheck(reply)
        if question and self._checks_reply(reply, behaviour, llm, off_topic):
            reply = yield from self._check_reply(llm, reply, ask, values, recheck)
        self._summary.update(
            answer_kind=reply.kind,
            scope=reply.scope,
            understood=reply.understood,
            answer_model=llm.model,
            answer_fallback=reply.fallback,
            answer_corrections=reply.corrections,
        )
        if reply.fallback and reply.text != text:
            self._summary["draft"] = text
        yield ev.custom(
            "answer",
            {
                "understood": reply.understood,
                "kind": reply.kind,
                "scope": reply.scope,
                "used": reply.used,
                "model": llm.model,
                "device": meta["device"],
                "fallback": reply.fallback,
                "corrections": reply.corrections,
                **({"claims": reply.claims} if reply.claims else {}),
            },
        )
        return reply, pack

    def _claims_on(
        self,
        llm,
        reply: answering.Reply,
        pack: Sequence[answering.Block],
        text: str,
        draft: bool,
        behaviour: str,
        facts: reporter.Facts,
        must: Sequence[str],
        tables: bool,
        values: Sequence[str] = (),
    ) -> Iterator[dict]:
        """Run the claim checker on a reply when it is due; then keep what still has a source.

        The code-written value lines (``values``) are checked already: sentences that repeat
        them are not sent, and the ``values`` block is a source like the draft.
        """
        if not self._checks_claims(reply, draft, tables):
            return
        keep = "\n".join(x for x in (reply.lead, *values) if x)
        yield from self._check_claims(
            llm, reply, pack, text if draft else "", keep, refused=behaviour == "refuse"
        )
        if reply.claims and reply.claims.get("removed") and not reply.fallback:
            # Sentences are gone, and with them the numbers a derived figure leaned on.
            reply.text = answering.keep_sourced(reply.text, facts)
            if draft and must:
                # A removed sentence may have carried the value asked for ("64 %, like the
                # best overall design": the label was wrong, the value right): the draft's
                # sentence for it goes back (4 Nov: only "the cheapest saves 60.6 %", the
                # recommended design's figure, was left).
                back, missing = answering.add_back(reply.text, text, must)
                if back != reply.text and not missing:
                    reply.corrections.append("added back from the checked answer")
                    reply.text = back

    def _checks_reply(
        self, reply: answering.Reply, behaviour: str, llm, off_topic: bool = False
    ) -> bool:
        """Return True when the reply check reads this reply (``DIOSCURI_REPLY_CHECK``).

        Only a reply the model wrote to a question: not the checked template, a clarifying
        question, a refusal, a greeting or a design to run; on by default on a GPU.
        """
        if reply.fallback or reply.kind != "answer" or reply.action != "none" or off_topic:
            return False
        if behaviour not in ("answer", "about") or not reply.text.strip():
            return False
        return policies.reply_check(self._device_of(llm))

    def _check_reply(
        self,
        llm,
        reply: answering.Reply,
        ask: Callable[..., answering.Reply],
        values: Sequence[str],
        recheck: Callable[[answering.Reply], Iterator[dict]],
    ) -> Iterator[dict]:
        """Check that a reply answers the question first and speaks of what it names (once).

        One short call (``reply_check.check``) reads the reply as the user will see it (the
        value lines first). On a fail the answerer rewrites it once with the reason (``ask``
        with ``revise``), and the rewrite gets the same checks and the claim checker
        (``recheck``). Code keeps the first reply when the rewrite is worse (``reply_check.worse``).
        Returns the reply to show; the run summary's ``reply_check`` says what happened.
        """
        yield ev.step_started(
            "reply_check", "Check the reply answers the question", "model", "check_reply(reply)"
        )
        start = time.perf_counter()
        first_calls = len(self._calls)
        if claims.TOO_SMALL.search(getattr(llm, "model", "")):
            note = f"{llm.model} is too small to judge a reply"
            self._summary["reply_check"] = {"ran": False, "note": note}
            yield ev.step_finished("reply_check", 0.0, decided_by="skipped", note=note)
            return reply
        shown = answering.strip_cites(reply.text)
        if values:
            shown = "In short\n" + "\n".join("- " + v.replace("**", "") for v in values)
            shown += "\n\n" + answering.strip_cites(reply.text)
        verdict = reply_check.check(llm, self._message, reply.understood, shown)
        if verdict.call is not None:
            self._calls.append(verdict.call)
            yield ev.custom("usage", verdict.call.as_dict())
        record = dict(verdict.meta(), ran=True)
        if verdict.failed:
            rewrite = ask(revise=(reply.text, reply_check.instruction(verdict)))
            for call in rewrite.calls:
                self._calls.append(call)
                yield ev.custom("usage", call.as_dict())
            saved = {
                k: self._summary[k]
                for k in ("claims_checked", "claims_removed", "claims_fallback", "claims_reworded")
                if k in self._summary
            }
            if not rewrite.fallback and rewrite.action == "none":
                yield from recheck(rewrite)
            why = reply_check.worse(reply, rewrite)
            if why:
                for k in ("claims_checked", "claims_removed", "claims_fallback", "claims_reworded"):
                    self._summary.pop(k, None)
                self._summary.update(saved)
                record["rewrite"] = "discarded: " + why
            else:
                record["rewrite"] = "kept"
                rewrite.understood = reply.understood or rewrite.understood
                rewrite.follow_ups = rewrite.follow_ups or reply.follow_ups
                rewrite.steps = reply.steps or rewrite.steps
                rewrite.corrections = reply.corrections + [
                    "rewritten to answer the question first: " + reply_check.instruction(verdict)
                ]
                reply = rewrite
        used = self._calls[first_calls:]
        record.update(
            calls=len(used),
            prompt_tokens=sum(c.prompt_tokens for c in used),
            output_tokens=sum(c.output_tokens for c in used),
            seconds=round(time.perf_counter() - start, 3),
        )
        self._summary["reply_check"] = record
        meta = {k: v for k, v in record.items() if k not in ("ran", "seconds")}
        decided = "skipped" if verdict.error else "model"
        yield ev.step_finished(
            "reply_check",
            time.perf_counter() - start,
            decided_by=decided,
            model=getattr(llm, "model", ""),
            **meta,
        )
        return reply

    def _judges_premises(self) -> bool:
        """Return True when the answerer's own verdict on the message's premises counts.

        Only when no planner read the message (a why, a message about Dioscuri): when one did,
        its list of premises decides. On 4 Nov a wider rule led "why didn't you pick the
        cheapest?" with "Not quite." (the 1 Nov lesson again).
        """
        return "parameters" not in self._summary

    def _checks_claims(self, reply: answering.Reply, draft: bool, data: bool = False) -> bool:
        """Return True when this reply goes to the claim checker (see ``check_claims``).

        Replies that reword the checked template, describe an opened table or image (``data``:
        its summary is written by code) or greet are not checked in ``"auto"``, unless in
        reasoning mode. A reply about an opened document is checked: it is the model's reading.
        """
        if self.check_claims == "off" or reply.fallback or reply.kind != "answer":
            return False
        if reply.used and set(reply.used) <= {"history"} and not draft:
            # A reply from the conversation alone ("what was the first question I asked?"):
            # what Dioscuri said is in no source the checker reads, so it removed true recalls
            # (4 Nov). Its numbers are still checked against the context.
            return False
        if self.check_claims == "always" or self._reasoning:
            return True
        # With a draft, what the model added around it is checked (its sentences that repeat the
        # draft are not sent): on 1 Nov added sentences mislabelled 30.6 M€ of capital as the
        # yearly cost and confirmed a user's wrong premise unchecked.
        return not data and self._summary.get("intent") != "greeting"

    def _values_elsewhere(
        self, session: Session, on: LedgerEntry, keys: Sequence[str]
    ) -> List[Tuple[str, List[str]]]:
        """Return the asked values as the current and recent designs have them, where they differ.

        Only values with a unit or a share ("60.6%", "56.7 €/MWh"): a bare count is too common
        to tell apart. Each comes with what names its design: its handle, its code, its picks.
        """
        mine = lookup.design_facts(on)
        others = [session.chosen] + answering.latest_designs(session.ledger, on)
        out: List[Tuple[str, List[str]]] = []
        seen = {on.alternative.code}
        for other in others:
            if other is None or other.alternative.code in seen:
                continue
            seen.add(other.alternative.code)
            theirs = lookup.design_facts(other)
            a = other.alternative
            names = [a.uid, a.code] + [engine.PICK_NAMES.get(k, "") for k in a.picks]
            if other is session.chosen:
                names += ["recommend", "current", "chosen", "your design", "our design"]
            for k in keys:
                if k not in theirs or k not in mine or theirs[k].value == mine[k].value:
                    continue
                value = str(theirs[k].value)
                if len(answering.numbers_in(value)) == 1 and re.search(r"[%€°]|[A-Za-z]", value):
                    out.append((value, [n for n in names if n]))
        return out

    def _check_claims(
        self,
        llm,
        reply: answering.Reply,
        pack: Sequence[answering.Block],
        draft: str,
        keep: str = "",
        refused: bool = False,
    ) -> Iterator[dict]:
        """Check the reply's words against its sources; remove what they do not support.

        ``keep``: sentences not to check besides the draft's (the correction of a premise).
        ``refused``: the template is a refusal the answerer overruled (it never stands in).
        The checker also reads the full facts of the designs the reply is about, which the
        answer's own context may have had as one line each (4 Nov: "what did the store
        change?" lost the store's figures, which only the what-if's own block gives).
        """
        yield ev.step_started("claims", "Check the claims", "model", "check_claims(reply)")
        start = time.perf_counter()
        if claims.TOO_SMALL.search(llm.model):
            # A small answerer (the CPU's) is checked by the reasoning model instead.
            llm = self._deep()
        if claims.TOO_SMALL.search(llm.model):
            note = f"{llm.model} is too small to judge claims"
            yield ev.step_finished(
                "claims", 0.0, decided_by="skipped", checked=0, note=note, model=llm.model
            )
            return
        # The user's own words are evidence for restating them ("the council promised at least
        # 50 % less CO2": "this falls short of the required 50 %" was removed on 1 Nov).
        said = answering.Block("message", "history", "User: " + (self._message or ""))
        facts = self._facts_for_claims(reply.text, pack)
        used = list(reply.used)
        if {"turns", "state"} & set(used) and "history" not in used:
            # A reply from the turn log or the chat's state is about the conversation: the
            # checker reads the conversation first (5 Nov: "what was the first thing I asked?"
            # cited the turn log, and the checker, reading the chat last, removed it).
            used.append("history")
        found = claims.check(
            llm,
            reply.text,
            list(pack) + facts + [said],
            used + [b.id for b in facts],  # read first, as if cited
            (draft + "\n\n" + keep).strip(),
        )
        for call in (found.call, found.quote_call):
            if call is not None:
                self._calls.append(call)
                yield ev.custom("usage", call.as_dict())
        left = re.sub(r"\s+", " ", answering.strip_cites(found.text or "")).strip()
        bare = found.fallback and len(re.sub(r"[^\w]", "", left)) < NEARLY_EMPTY
        if found.fallback and (draft or (bare and self._template and not refused)):
            # The reply rewords a tool's checked result, or too little of it is left to stand:
            # show the checked template, and say that statements were left out (4 Nov: an empty
            # reply, and "I won't guess" in place of an answer). (A design question's summary
            # does not stand in for a reply that keeps a real part: it answered none of "do we
            # have a design with spare units?" on 1 Nov; that part is kept below instead.)
            reply.corrections.append("most claims had no source: showed the checked template")
            reply.text = (
                self._template + "\n\n" + reporter.unconfirmed_text(len(found.removed), True)
            )
            reply.fallback = True
            reply.follow_ups = []
        elif found.fallback:
            # No template stands behind this reply (the template may even be a refusal the
            # answerer overruled): keep what was supported and say what could not be.
            reply.corrections.append(
                f"removed {len(found.removed)} of {len(found.checked)} sentence(s) the sources "
                "do not support; kept the rest and said so"
            )
            reply.text = (found.text + "\n\n" if found.text else "") + reporter.unconfirmed_text(
                len(found.removed), bool(found.text)
            )
        elif found.removed or found.reworded:
            if found.removed:
                reply.corrections.append(
                    f"removed {len(found.removed)} sentence(s) the sources do not support"
                )
            if found.reworded:
                reply.corrections.append(
                    f"reworded {len(found.reworded)} sentence(s) to say only what the sources say"
                )
            reply.text = found.text
        reply.claims = {"checked": len(found.checked), "removed": found.removed}
        if found.reworded:
            reply.claims["reworded"] = [[a, b] for a, b in found.reworded]
        self._summary.update(
            claims_checked=len(found.checked),
            claims_removed=found.removed,
            claims_fallback=found.fallback,
            claims_reworded=[[a, b] for a, b in found.reworded],
        )
        meta = dict(found.meta(), model=llm.model, device=self._device_of(llm))
        yield ev.step_finished("claims", time.perf_counter() - start, **meta)

    def _facts_for_claims(
        self, text: str, pack: Sequence[answering.Block]
    ) -> List[answering.Block]:
        """Return the full blocks of the designs a reply is about that its context lacked.

        The design the question is about (picked, named, under discussion) and the designs the
        reply names: a statement their own facts give is supported, whatever the answer's
        context held of them (one line each for a question no pattern took for one about a
        design).
        """
        session = self._session
        have = {b.id for b in pack}
        about = [e for e in [self._lookup_on, self._focus, *self._picked] if e is not None]
        # The designs the reply names by id or code (no sweep design is opened for a check).
        names = list(dict.fromkeys(DESIGN_ID.findall(text) + CODE_IN_WORDS.findall(text)))
        about += reliability.resolve(names, session)[0] if names else []
        if not about and session.chosen is not None:
            about = [session.chosen]  # a question about the design under discussion
        out: List[answering.Block] = []
        for e in about:
            block = answering.design_block(e, chosen=e is session.chosen)
            if block.id in have:
                continue
            have.add(block.id)
            out.append(block)
            ops = answering.operations_block(e, self._message or "")
            if ops is not None and ops.id not in have:
                have.add(ops.id)
                out.append(ops)
        return out[:6]

    def _card(self, passage: dict, kind: str = "") -> dict:
        """Return a source card: the passage, its kind and the figures in its section."""
        card = dict(passage)
        attached = [a["name"] for a in self._session.attachments]
        card.setdefault("kind", kind or answering.passage_kind(card["source"], attached))
        if card["kind"] in ("doc", "note") and not card.get("suspicious"):
            images = files.section_images(DOCS_ROOT, card["source"], card.get("section", ""))
            if images:
                card["images"] = images
        return card

    def _strays(self, session: Session, names: Sequence[str], message: str) -> bool:
        """Return True when the reader named a design the user neither picked (@) nor wrote.

        The designs picked with @ are the user's own choice; the reader may add the design
        under discussion from the thread (5 Nov: A1 and B1 picked, W1 compared).
        """
        found, _ = reliability.resolve(list(names), session)
        own = {reporter.design_id(e) for e in self._picked + self._written(session, message)}
        return any(reporter.design_id(e) not in own for e in found)

    def _written(self, session: Session, message: str) -> List[LedgerEntry]:
        """Return the designs the words name beside the ones picked with @.

        Two or more picked: only ids and codes ("the cheaper of these two" is one of them, not
        the search's cheapest); one picked: picks by name too ("compare it with the cheapest").
        """
        if len(self._picked) >= 2:
            return ids_in(message, session)
        return named_in(message, session)

    def _which_design(self, session: Session, reading, message: str) -> List[Tuple[str, str]]:
        """Return the designs to ask about (label, id), or [] when the question needs no ask.

        Asked when the reading says the answer needs one design, none is named (@, or in the
        words: ``reading.designs``, ``named_in``), the message asks for no new design, and the
        chat has two designs or more to choose from.
        """
        if not getattr(reading, "about_design", None) or self._picked or reading.designs:
            return []
        if getattr(reading, "new_design", None):
            return []
        if any(st.do == "design" for st in reading.steps) or named_in(message, session):
            return []
        out: List[Tuple[str, str]] = []
        seen = set()

        def add(e: LedgerEntry, label: str) -> None:
            # By id, not code: a what-if keeps its design's code (4 Nov: W1 was left out as
            # A1, so "so what does heat cost then?" could not be about it).
            if reporter.design_id(e) in seen or e.alternative.role == "reference":
                return
            seen.add(reporter.design_id(e))
            out.append(
                (
                    f"{e.alternative.uid or e.alternative.code} · {label} "
                    f"({e.alternative.code})",
                    reporter.design_id(e),
                )
            )

        for key in engine.PICKS:  # the latest search's picks, one option a design
            e = next((x for x in session.candidates or [] if key in x.alternative.picks), None)
            if e is not None:
                both = [engine.PICK_NAMES[k] for k in engine.PICKS if k in e.alternative.picks]
                add(e, ", ".join(both))
        for e in reversed(session.ledger):  # what-ifs and the user's own designs, latest first
            if e.alternative.role == "what_if":
                # Said to be one: "back to the design itself, without those what-ifs" got the
                # 45 °C what-if's figure (4 Nov); it has the design's code.
                add(e, "what-if: " + (e.change_label or e.alternative.name or "a change"))
            elif e.alternative.role == "user":
                add(e, e.change_label or e.alternative.name or "your design")
        focus = session.thread.focus_id
        at = next((i for i, (_, did) in enumerate(out) if did == focus), None)
        if at is not None and at >= 6:
            # The design under discussion (a what-if just run) is an option, whatever the cap.
            out.insert(0, out.pop(at))
        if chat_state.on():
            # "The second one" may be no pick of the latest search: the last list's designs
            # and the chat's are options too (``chat_state.add_shown``).
            return chat_state.add_shown(out[:6], session) if len(out) >= 2 else []
        return out[:6] if len(out) >= 2 else []

    def _design_meant(self, session: Session, message: str, options) -> Iterator[dict]:
        """Return the design the conversation says a message is about.

        None when the model cannot tell (the user is asked), False when the message is about
        several designs or none (nothing to ask).
        """
        deep = self._deep()
        focus = session.thread.focus_id
        k, call = yield from self._step(
            "which_design",
            "Read which design the message is about",
            "model",
            None,
            lambda: parameters.design_meant(
                message,
                (
                    chat_state.annotate(options, session)
                    if chat_state.on()
                    else [
                        label + (" (the design under discussion)" if did == focus else "")
                        for label, did in options
                    ]
                ),
                deep,
                self._thread_context(session, "short"),
            ),
            after=lambda r: {
                "decided_by": "model" if r[1] is not None and r[1].ok else "rules",
                "design": options[r[0] - 1][0] if r[0] > 0 else ("several" if r[0] else ""),
                "model": getattr(deep, "model", ""),
                "device": self._device_of(deep),
            },
        )
        if call is not None:
            self._calls.append(call)
            yield ev.custom("usage", call.as_dict())
        if k < 0:
            return False  # several designs or none ("which designs have we looked at?")
        if not k:
            # The model cannot tell, and the message names no design: the design under
            # discussion stands, as when the model picks another one nothing points to (4 Nov:
            # "What if gas cost 45 €/MWh?" and "And with 45 °C?" were asked "which design?").
            if focus and not named_in(message, session):
                kept, _ = reliability.resolve([focus], session)
                if kept:
                    return kept[0]
            return None
        found, _ = reliability.resolve([options[k - 1][1]], session)
        if not found:
            return None
        pick = found[0]
        did = reporter.design_id(pick)
        # A design other than the one under discussion needs something that points to it: the
        # message names it ("the cheapest"), or the last reply listed it ("the second one",
        # "that one"). Else the design under discussion stands (4 Nov: "the CO2 saving is
        # 80 %, isn't it?" was read as about the lowest-CO2 pick).
        named = {reporter.design_id(e) for e in named_in(message, session)}
        shown = any(x.split(" (")[0] == did for x in session.thread.shown)
        if chat_state.on() and not shown:
            # "Back to the original design": the design a what-if under discussion was run on.
            at = reliability.resolve([focus], session)[0] if focus else []
            base = chat_state.original_of(at[0], session) if at else None
            shown = base is not None and reporter.design_id(base) == did
        if focus and did != focus and did not in named and not shown:
            kept, _ = reliability.resolve([focus], session)
            return kept[0] if kept else None
        return pick

    def _ask_design(self, session: Session, read, message: str, options) -> Iterator[dict]:
        """Ask which design the question is about: the chat's designs, and Other for a name."""
        session.pending = {
            "kind": "which_design",
            "intent": self._summary.get("intent", read.intent or "question"),
            "message": message,
            "language": self._summary.get("language", read.language or "en"),
            "options": [label for label, _ in options],
            "ids": {label: did for label, did in options},
        }
        text = "Which design is your question about?"
        question = Question(
            id="design",
            label=text,
            hint="Pick one, or type a design's name or handle (A1, W2 ...).",
            options=[label for label, _ in options],
        )
        yield ev.custom(
            "clarification",
            {
                "kind": "choice",
                "intro": text,
                "questions": [question.model_dump()],
                "other": "Other: a design's handle or name (A1, W2, the cheapest ...)",
            },
        )
        # The question is the reply: the chat's history and thread keep it (an empty reply was
        # recorded on 4 Nov, so the next turn could not see what was asked).
        self._summary.update(behaviour="clarify", asked=["design"], answer=text)
        return "design"

    def _ask_choice(self, reply: answering.Reply) -> Iterator[dict]:
        """Ask the user to pick one of the model's readings of an unclear message."""
        session = self._session
        session.pending = {
            "kind": "choice",
            "intent": self._summary.get("intent", "other"),
            "message": self._message,
            "language": self._summary.get("language", "en"),
            "options": reply.options,
        }
        question = Question(
            id="choice",
            label=reply.text,
            hint="Pick one, or type your own question.",
            options=reply.options,
        )
        yield ev.custom(
            "clarification",
            {"kind": "choice", "intro": reply.text, "questions": [question.model_dump()]},
        )
        self._summary.update(behaviour="clarify", asked=["choice"])
        return "choice"

    # ------------------------------------------------ what the user asked to remember

    def _notes(self, session: Session) -> List[remembered.Note]:
        """Return what the user asked to remember: the project's (shared) or the chat's own."""
        if self.memory is not None:
            return self.memory.notes(session.project.id)
        return [remembered.Note.from_dict(d) for d in getattr(session, "notes", [])]

    def _keep_notes(self, session: Session, notes: Sequence[remembered.Note]) -> None:
        if self.memory is not None:
            self.memory.save(session.project.id, notes)
        else:
            session.notes = [asdict(n) for n in notes][-remembered.MAX_NOTES :]

    def _remember(self, session: Session, message: str) -> Iterator[dict]:
        """Read a typed message for something to remember (one short call) and keep it.

        "Call me Reza" (5 Nov) was in the turn log but nothing marked it as standing: after a
        design the replies dropped the name. The model reads the message; code checks the note
        (``remembered.checked``). A row shows only when something is kept or forgotten.
        """
        if not remembered.on() or intake.GREETING.match(message):
            return  # a bare "hello" or "thanks" (screened by pattern, no call) holds nothing
        notes = self._notes(session)
        start = time.perf_counter()
        keep, drop, call, error = remembered.read(message, notes, self._fast)
        if call is not None:
            self._calls.append(call)
            yield ev.custom("usage", call.as_dict())
        if error:
            self._summary["memory_error"] = error
        if not keep and not drop:
            return
        gone = [notes[i] for i in drop]
        left = [n for i, n in enumerate(notes) if i not in drop]
        if keep:
            said = remembered._flat(message, 160)
            left.append(remembered.Note(keep, said, session.thread_id, session.turns))
        self._keep_notes(session, left)
        label = f"Remember: {keep}" if keep else "Forget: " + "; ".join(n.text for n in gone)
        yield ev.step_started("memory", label, "model", "remember(message)")
        self._summary["remembered"] = keep
        if gone:
            self._summary["forgot"] = [n.text for n in gone]
        yield ev.step_finished(
            "memory",
            time.perf_counter() - start,
            decided_by="model",
            model=getattr(self._fast, "model", ""),
            remembered=keep,
            forgot=[n.text for n in gone],
            shared=self.memory is not None,
        )
        yield ev.custom("memory", {"projectId": session.project.id, "notes": remembered.view(left)})

    def _notes_block(self, session: Session) -> Optional[answering.Block]:
        """Return the notes as a context block (kind ``notes``), or None when there are none."""
        text = remembered.block_text(self._notes(session), session.thread_id, session.turns)
        return answering.Block("notes", "notes", text, remembered.TITLE) if text else None

    # ------------------------------------------------ the chat's state, capabilities, choices

    def _cpu(self) -> bool:
        """Return True when the reasoning model runs on the CPU (prompts kept shorter)."""
        return self._device == "cpu" or (
            self.router is not None and self._device_of(self._deep()) == "cpu"
        )

    def _state_blocks(self, session: Session, light: bool) -> List[answering.Block]:
        """Return the chat's state and the plant's capability card for the answerer."""
        if light:
            return []
        out = []
        state = chat_state.text(
            getattr(session, "state", None),
            session,
            "answer",
            limit=1400 if self._cpu() else 2600,
        )
        if state:
            out.append(answering.Block("state", "history", state, "the conversation's state"))
        turns = chat_state.turns_text(
            getattr(session, "state", None), limit=900 if self._cpu() else 1800
        )
        if turns:
            # The user's messages, numbered: "what did we discuss before X?" is a lookup.
            out.append(answering.Block("turns", "history", turns, "the user's earlier messages"))
        card = capabilities.block()
        if card is not None:
            out.append(card)
        return out

    def _with_state(self, session: Session, thread: str, message: str, limit: int) -> str:
        """Return a reading's thread with the chat's state, for a follow-up naming no design."""
        if not chat_state.on() or named_in(message, session):
            return thread
        state = chat_state.text(getattr(session, "state", None), session, "reading", limit)
        return f"{thread}\n{state}".strip() if state else thread

    def _settle(
        self, session: Session, reading: parameters.Reading, message: str, intent: str = ""
    ) -> Iterator[dict]:
        """Check the reading before anything runs; return the question asked, or None.

        A design step for "best" alone when the reply needs a design that exists is a question
        (``clarify.objective_is_a_question``); what was filed as not modelled is checked
        against the plant's options (``capabilities.covers``); words whose referent is open
        and changes without an amount are asked about, with choices (``clarify``).
        """
        if not reading.ok:
            return None
        if clarify.objective_is_a_question(reading):
            reading.changes.pop("objective", None)
            reading.items = [x for x in reading.items if x[0] != "objective"]
            reading.steps = [st for st in reading.steps if st.do not in ("design", "what_if")] or [
                parameters.Step("answer", message)
            ]
            reading.corrections.append("objective: the reply needs a design that exists")
        if capabilities.on() and reading.unsupported:
            yield from self._covered(session, reading, message)
        if reading.failures or not clarify.on():
            return None
        if (
            session.chosen is not None
            and not (session.pending or getattr(self, "_asked_before", False))
            and not reading.open_ref
        ):
            # A change read from a bare number ("hmm 70", "run it again with 2"): what it sets
            # is asked, unless the chat's latest what-if changed that setting ("and with 45?").
            recent = [e for e in session.ledger[-3:] if e.alternative.role == "what_if"]
            earlier = [k for e in recent for k in (e.changes or {})]
            reading.open_ref = clarify.bare_numbers(reading, message, earlier)
        if reading.open_ref:
            return (yield from self._ask_unclear(session, reading, message))
        if (
            session.chosen is not None
            and any(st.do in ("design", "what_if") for st in reading.steps)
            and any(d.startswith("doublet_stops") and "no dates" in d for d in reading.dropped)
        ):
            # A stop asked for with no dates ("a stop in summer for maintenance"): where it is
            # now, and the dates asked, before anything runs (5 Nov: a what-if ran on a misread
            # switch, and the reply said both "updated" and "not applied").
            asked = yield from self._ask_dates(session, message)
            if asked is not None:
                return asked
        if reading.vague and (session.chosen is not None or intent in ("design", "compare")):
            # Before a design, a question ("how big is a heat store?") is answered, as before.
            return (yield from self._ask_choices(session, reading, message))
        return None

    def _covered(self, session: Session, reading: parameters.Reading, message: str):
        """Put back as plant options what the reading filed as not modelled (in place).

        Words a change without an amount also took ("add a heat store": a store with no size
        and "heat store" not modelled) are that change. Else the model reads once, with the
        capability card, whether an option is meant; a switch is then the change, a size is
        asked for.
        """
        quotes = " ".join(parameters._norm(q) for _, q in reading.vague.values())
        quotes += " " + " ".join(parameters._norm(q) for q in reading.quotes.values())
        kept = [
            u
            for u in reading.unsupported
            if not any(w in quotes for w in re.findall(r"[a-zà-ÿ]{4,}", parameters._norm(u)))
        ]
        if len(kept) < len(reading.unsupported):
            reading.dropped.append("unsupported: the same words as an option read")
            reading.unsupported = kept
        if not reading.unsupported or reading.changes or reading.doublets or reading.vague:
            return None
        deep = self._deep()
        key, call = yield from self._step(
            "covers",
            "Check the plant's options before saying it cannot",
            "model",
            None,
            lambda: capabilities.covers(
                reading.unsupported, message, deep, self._thread_context(session, "short")
            ),
            after=lambda r: {
                "decided_by": "model" if r[1] is not None and r[1].ok else "rules",
                "key": r[0] or "",
                "model": getattr(deep, "model", ""),
                "device": self._device_of(deep),
            },
        )
        if call is not None:
            self._calls.append(call)
            yield ev.custom("usage", call.as_dict())
        if key is None:
            return None
        quote = message.strip()
        if key in parameters.SWITCHES and self._now(session).get(key):
            reading.already.append(key)  # "would free cooling help?" when the design has it
        elif key in parameters.SWITCHES:
            reading.changes[key] = 1.0
            reading.items.append((key, 1.0, 0))
            reading.quotes[key] = quote
        else:
            reading.vague[key] = (0.0, quote)
        reading.dropped.append(f"unsupported {reading.unsupported}: the plant option {key}")
        reading.unsupported = []
        if (reading.changes or reading.vague) and not any(
            st.do in ("what_if", "design") for st in reading.steps
        ):
            kind = "what_if" if session.chosen is not None else "design"
            reading.steps.insert(0, parameters.Step(kind, quote))
        return key

    def _now(self, session: Session) -> Dict[str, object]:
        """Return each parameter's value now (the current design's, or the project's)."""
        base = session.chosen
        brief = base.brief if base is not None else session.brief
        return parameters.values_now(
            brief,
            base.alternative if base is not None else None,
            engine.rules_for(brief),
            engine.prices_for(session.assumptions, brief),
        )

    def _ask_choices(self, session: Session, reading: parameters.Reading, message: str):
        """Ask the amount a change was asked without, with two or three to pick (``clarify``)."""
        key, (guess, quote) = next(iter(reading.vague.items()))
        now = self._now(session).get(key, guess)
        now = float(now) if isinstance(now, (int, float)) else 0.0
        kind = "what_if" if session.chosen is not None else "design"
        others = bool(reading.changes or reading.doublets or len(reading.vague) > 1)
        text, options, requests = clarify.amount_question(
            key, guess, now, quote, kind, message, others
        )
        name = re.sub(r"\s*\(.*\)$", "", parameters.CATALOGUE[key].label).lower()
        return (yield from self._ask_with(text, options, requests, f"{name}: how much"))

    def _ask_unclear(self, session: Session, reading: parameters.Reading, message: str):
        """Ask what the words left open mean, with the likely referents to pick (``clarify``)."""
        return (yield from self._ask_referent(session, reading.open_ref, message))

    def _ask_referent(self, session: Session, item: dict, message: str):
        """Ask what an open item (``clarify``: its quote and the keys it could be) refers to."""
        earlier = []
        for e in reversed(session.ledger):  # the settings the chat's what-ifs ran
            if e.alternative.role == "what_if":
                earlier += [(k, v) for k, v in (e.changes or {}).items()]
        text, options, requests = clarify.referent_question(
            item, message, self._now(session), earlier
        )
        return (yield from self._ask_with(text, options, requests, "what the words refer to"))

    def _ask_dates(self, session: Session, message: str):
        """Ask when a stop asked for without dates should be, saying where it is now."""
        from gemini_agent import stops

        ranges = stops.ranges_of(getattr(session.chosen, "year", None))
        if not ranges or not any(ranges):
            return None
        spans = list(dict.fromkeys(stops.span_words(r) for r in ranges if r))
        where = (
            spans[0]
            if len(spans) == 1
            else "; ".join(
                f"doublet {k + 1}: {stops.span_words(r)}" for k, r in enumerate(ranges) if r
            )
        )
        days = stops.days_off(next(r for r in ranges if r))
        text = (
            f"The doublet's yearly stop is already in its quietest weeks, {where} ({days} days), "
            "and doubles as its maintenance window. Keep it there, or move it? Pick one, or "
            "give the dates."
        )
        options = [f"Keep the stop at {spans[0]}", "Move the stop to August", "Stop 1 to 21 July"]
        requests = {
            options[0]: "When is the doublet's yearly stop, and what does it cost?",
            options[1]: "Move the doublet's yearly stop to August.",
            options[2]: "Stop the doublet from 1 to 21 July.",
        }
        self._summary.update(intent="what_if")
        return (yield from self._ask_with(text, options, requests, "when the stop should be"))

    def _ask_with(self, text: str, options: List[str], requests: Dict[str, str], understood: str):
        """Ask one short question with its options; keep what each option runs."""
        reply = answering.Reply(text, kind="clarify", options=options, understood=understood)
        yield from ev.text_message(uuid.uuid4().hex[:10], text)
        self._summary.update(behaviour="clarify", answer=text, choices=list(options))
        out = yield from self._ask_choice(reply)
        if self._session.pending is not None and requests:
            self._session.pending["requests"] = dict(requests)
        return out

    def _step(
        self,
        name: str,
        label: str,
        kind: str,
        code: Optional[str],
        fn: Callable[[], object],
        after: Optional[Callable[[object], dict]] = None,
    ) -> Iterator[dict]:
        yield ev.step_started(name, label, kind, code)
        start = time.perf_counter()
        out = fn()
        yield ev.step_finished(name, time.perf_counter() - start, **(after(out) if after else {}))
        return out

    def _tool_step(
        self, name: str, label: str, code: str, calls: List[Tuple[str, dict, Callable[[], object]]]
    ) -> Iterator[dict]:
        yield ev.step_started(name, label, "tool", code)
        start = time.perf_counter()
        results = []
        for tool, args, fn in calls:
            out = yield from self._tool(tool, args, fn)
            results.append(out)
        failed = sum(isinstance(r, ToolError) for r in results)
        yield ev.step_finished(name, time.perf_counter() - start, calls=len(calls), failed=failed)
        return results

    def _tool(self, name: str, args: dict, fn: Callable[[], object]) -> Iterator[dict]:
        key = name + json.dumps(args, sort_keys=True, default=str)
        cached = key in self._cache
        self._tools["calls"] += 1
        self._tools["cached"] += cached
        out: object
        if cached:
            out = self._cache[key]
        else:
            try:
                out = self._cache[key] = fn()
            except Exception as err:  # noqa: BLE001 - a broken tool leaves out one design
                self._tools["failed"] += 1
                out = ToolError(name, str(err) or type(err).__name__)
        if isinstance(out, ToolError):
            content = {"cached": False, "error": out.message}
        else:
            if isinstance(out, LedgerEntry):  # a design: its daily series stay out of the trace
                payload = out.model_dump(exclude={"year": {"daily_mw", "doublets"}})
            else:
                payload = out.model_dump() if hasattr(out, "model_dump") else out
            payload = payload.as_dict() if hasattr(payload, "as_dict") else payload
            content = {"cached": cached, "result": payload}
        call_id = uuid.uuid4().hex[:10]
        yield from ev.tool_call(
            call_id, name, json.dumps(args, default=str), json.dumps(content, default=str)
        )
        return out

    def _usage(self) -> List[dict]:
        by_model: Dict[str, dict] = {}
        for c in self._calls:
            u = by_model.setdefault(
                c.model,
                {"model": c.model, "provider": "ollama", "inputTokens": 0, "outputTokens": 0},
            )
            u["inputTokens"] += c.prompt_tokens
            u["outputTokens"] += c.output_tokens
        for u in by_model.values():
            u["totalTokens"] = u["inputTokens"] + u["outputTokens"]
        return list(by_model.values())


def model_conditions(spec, session: Session) -> List[dict]:
    """Return the operating points to run a generated model at, from the latest design.

    The adsorption chiller is driven by the heat-exchanger outlet: its temperature and the heat
    the brine still carries above the reinjection limit come from the chosen design, and it is
    also run 10 K hotter to show how sensitive it is. Other models run at their spec's defaults.

    Parameters
    ----------
    spec : ComponentSpec
        The component.
    session : Session
        The conversation (its chosen design, if any).

    Returns
    -------
    list of dict
        Input values by name; missing inputs take the spec's defaults.
    """
    entry = session.chosen
    if spec.name != "adsorption_chiller" or entry is None:
        return [{}]
    y = entry.year
    drive = y.hex_outlet_c
    case = {"drive_temp_c": drive}
    if y.brine_capacity_mw and y.wellhead_c > verifier.REINJECT_MIN_C:
        share = max(0.0, drive - verifier.REINJECT_MIN_C) / (y.wellhead_c - verifier.REINJECT_MIN_C)
        case["heat_available_mw"] = round(y.brine_capacity_mw * share, 2)
    if entry.brief.cooling is not None:
        case["chilled_water_temp_c"] = entry.brief.cooling.supply_c
    return [case, dict(case, drive_temp_c=drive + 10)]
