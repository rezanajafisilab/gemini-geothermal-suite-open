"""The conversation's running state, kept by code: designs, questions, decisions, numbers.

The thread (``thread.py``, ADR-0018) keeps what the chat is about now: the design under
discussion, the last list shown, the open question, one line per turn. On 4 Nov the long chats
still lost track of what came before it (``hackathon/evals/scenarios/conversations.yaml``):

- C3: after "put the cheapest and the greenest side by side", "the CO2 saving of the second
  one?" was answered about the recommended design, "and the first one's capital cost?" gave one
  figure for both, and "which of the two would you pick for the least CO2?" named the wrong one;
- C4: "what were we discussing before the weather?" got a vague answer;
- C5: "back to the original design, its CO2 saving?" ran a design instead of answering.

The state is the compact, structured record a model needs to resolve such words (context
engineering: a small state, not the raw history). After every turn code notes, with no model
call:

- **designs**: every design the chat mentioned, in the order it came up, with its id, code,
  pick name (or what-if of which design) and the turn; its figures (cost of heat, CO2 saving,
  capital) are read from the ledger when the state is shown, never from a reply;
- **asked**: the user's questions in order, short (what Dioscuri did with them when it did not
  answer: declined, asked back);
- **decisions**: the design recommended, the inputs confirmed, the what-ifs run;
- **open**: the question Dioscuri left open, with its options;
- **numbers**: the last figures a reply gave that are a design's own (its ledger values), each
  with the design and what it is.

Older questions are compacted, not dropped: the last ``RECENT`` stay word for word, older ones
are cut short, and past ``KEPT`` they fold into one line that says which turns it covers.

``text(state, session, kind)`` renders it for the answerer (``answer``) and the readings
(``reading``); ``annotate`` marks the options of the which-design reading with their place in
the last list shown and in the chat, and their figures, so "the second one", "the first one's",
"the cheaper of the two" or "the original design" can be read by the model. Code never decides
from it what a message means. ``DIOSCURI_CHAT_STATE=0`` turns it off.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from gemini_agent.thread import designs_named, flat

RECENT = 6  # questions shown word for word; older ones shortened
KEPT = 40  # questions kept one by one; older ones fold into ``earlier``
DESIGNS = 12  # designs kept (the first ones stay: "the original design")
NUMBERS = 6  # figures kept
FIGURES = ("lcoh", "lcoe", "lcoc", "capex", "co2_saving", "reinjection_temp", "wellhead_temp")
FIGURES += ("heat_pump_size", "boiler_size", "chiller_size", "absorption_size")
WHAT = {  # how a figure is named in the state
    "lcoh": "cost of heat",
    "lcoe": "cost of heat and cold",
    "lcoc": "cost of cold",
    "capex": "capital cost",
    "co2_saving": "CO2 saving",
    "reinjection_temp": "reinjection temperature",
    "wellhead_temp": "wellhead temperature",
    "heat_pump_size": "heat pump size",
    "boiler_size": "boiler size",
    "chiller_size": "chiller size",
    "absorption_size": "absorption chiller size",
}
# What a turn that did not answer did, after the user's question.
NOT_ANSWERED = {
    "refuse": "declined as off-topic",
    "clarify": "Dioscuri asked back",
    "nonsense": "not a proper question",
    "reject": "declined",
    "error": "hit an error",
}
ORDINALS = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th")


def on() -> bool:
    """Return True unless ``DIOSCURI_CHAT_STATE`` turns the state off."""
    return os.environ.get("DIOSCURI_CHAT_STATE", "1").strip().lower() not in (
        "0",
        "false",
        "off",
        "no",
    )


@dataclass
class ChatState:
    """The conversation's running state (see the module)."""

    designs: List[dict] = field(default_factory=list)  # {"did", "id", "code", "what", "turn"}
    asked: List[list] = field(default_factory=list)  # [turn, question, what was done or ""]
    earlier: str = ""  # questions folded past ``KEPT``: "T1-T12: «…»; «…»"
    decisions: List[str] = field(default_factory=list)  # "T1: recommended A1 · … (best overall)"
    open: List[str] = field(default_factory=list)  # the question left open, with its options
    numbers: List[dict] = field(default_factory=list)  # {"turn", "id", "what", "value"}
    chosen: str = ""  # the recommended design's id, to note a new recommendation once
    confirmed: str = ""  # the inputs' fingerprint confirmed, to note it once

    def to_dict(self) -> dict:
        """Return the state as plain data (saved with the session)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ChatState":
        """Return the state saved by ``to_dict`` (an empty one for older sessions)."""
        data = data or {}
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    def mention(self, did: str, uid: str, code: str, what: str, turn: int) -> None:
        """Note a design the chat mentioned (its first turn stays)."""
        if not did or any(d["did"] == did for d in self.designs):
            return
        self.designs.append(
            {"did": did, "id": uid or code, "code": code, "what": what, "turn": turn}
        )
        if len(self.designs) > DESIGNS:
            # The first designs stay ("the original design"), the middle ones go first.
            self.designs = self.designs[:3] + self.designs[-(DESIGNS - 3) :]

    def ask(self, turn: int, question: str, done: str = "") -> None:
        """Note the user's question; past ``KEPT`` the oldest fold into ``earlier``."""
        if not question.strip():
            return
        self.asked.append([turn, flat(question, 90), done])
        if len(self.asked) > KEPT:
            old, self.asked = self.asked[:-KEPT], self.asked[-KEPT:]
            first = self.earlier.split(":", 1)[0][1:].split("-")[0] if self.earlier else ""
            words = "; ".join(f"«{flat(q, 30)}»" for _, q, _ in old)
            body = (self.earlier.split(": ", 1)[1] + "; " if self.earlier else "") + words
            start = first or str(old[0][0])
            self.earlier = f"T{start}-T{old[-1][0]}: " + flat(body, 400)

    def decide(self, text: str) -> None:
        """Note a decision (the last eight stay)."""
        if text and text not in self.decisions:
            self.decisions = (self.decisions + [text])[-8:]

    def figure(self, turn: int, uid: str, what: str, value: str) -> None:
        """Note a figure a reply gave (the last ``NUMBERS`` stay; a repeat moves to the end)."""
        self.numbers = [n for n in self.numbers if (n["id"], n["what"]) != (uid, what)]
        self.numbers = (self.numbers + [{"turn": turn, "id": uid, "what": what, "value": value}])[
            -NUMBERS:
        ]


def _pool(session) -> List[object]:
    """Return every design of the chat: the ledger, then the searches' candidates."""
    pool = list(session.ledger) + list(session.candidates or [])
    for srch in session.searches or []:
        pool += [e for e in srch.get("candidates") or [] if all(e is not x for x in pool)]
    return [e for e in pool if e.alternative.role not in ("reference", "same", "failed")]


def did_of(entry) -> str:
    """Return a design's id in the conversation (``reporter.design_id``)."""
    from gemini_agent import reporter

    return reporter.design_id(entry)


def original_of(entry, session) -> Optional[object]:
    """Return the design a what-if was run on (its code, not a what-if), or None."""
    if entry is None or entry.alternative.role != "what_if":
        return None
    code = entry.alternative.code
    chosen = session.chosen
    if chosen is not None and chosen.alternative.code == code and chosen is not entry:
        return chosen
    # Not the design itself as a search's candidate: a new search's pick kept as a what-if
    # ("searched again") was said to be "what-if of B1" of itself (5 Nov).
    own = did_of(entry)
    return next(
        (
            e
            for e in _pool(session)
            if e.alternative.code == code and e.alternative.role != "what_if" and did_of(e) != own
        ),
        None,
    )


def what_of(entry, session) -> str:
    """Return what a design is in a few words: its picks, a what-if of which, the user's own."""
    from gemini_agent import engine

    a = entry.alternative
    if a.role == "what_if":
        base = original_of(entry, session)
        on = f" of {base.alternative.uid or base.alternative.code}" if base is not None else ""
        return f"what-if{on}: {entry.change_label or 'a change'}"
    if a.role == "user":
        return "the user's own design"
    picks = [engine.PICK_NAMES[k] for k in a.picks if k in engine.PICK_NAMES]
    run = _run_of(entry, session)
    if picks and run:
        # The list it came in: "best overall of run B" ("the new design", "run B's pick").
        picks[-1] += f" of {run}"
    if session.chosen is not None and did_of(session.chosen) == did_of(entry):
        picks.append("recommended")
    return ", ".join(picks)


def _run_of(entry, session) -> str:
    """Return "run B" for a pick of the chat's second search, "" with one search or none."""
    searches = list(getattr(session, "searches", None) or [])
    if len(searches) < 2:
        return ""
    did = did_of(entry)
    for i, srch in enumerate(searches):
        if any(e is entry or did_of(e) == did for e in srch.get("candidates") or []):
            return f"run {chr(ord('A') + i)}" if i < 26 else ""
    return ""


def figures(entry) -> str:
    """Return a design's cost of heat, CO2 saving and capital, from its ledger values."""
    from gemini_agent import reporter

    e = entry.economics
    return (
        f"heat {reporter.num(e.lcoh_eur_per_mwh)} €/MWh, CO2 saving "
        f"{reporter.pct(e.co2_saving_vs_gas)}, capital {reporter.num(e.capex_meur)} M€"
    )


def note_turn(agent, session, said: str, reply: str, ledger_before: int) -> None:
    """Note the turn that just ended in the session's state (no model call).

    ``agent`` is the ``Agent`` that ran it: the designs the turn was about are its own
    (``_lookup_on``, ``_focus``, ``_picked``), with the designs the reply named after them.
    """
    if not on():
        return
    state = getattr(session, "state", None)
    if state is None:
        state = session.state = ChatState()
    n = session.turns
    pool = _pool(session)
    by_did = {}
    names: Dict[str, str] = {}
    for e in reversed(pool):  # the latest of a code wins
        did = did_of(e)
        by_did.setdefault(did, e)
        if e.alternative.uid:
            names[e.alternative.uid] = did
        if e.alternative.code:
            names[e.alternative.code] = did
    summary = getattr(agent, "_summary", {}) or {}
    behaviour = str(summary.get("behaviour") or "")
    new = [e for e in session.ledger[ledger_before:] if e.alternative.role != "reference"]
    about = [getattr(agent, "_lookup_on", None), getattr(agent, "_focus", None)]
    about += list(getattr(agent, "_picked", None) or []) + new
    if getattr(agent, "_searched_now", False) and session.chosen is not None:
        about.append(session.chosen)
    turn_dids = [did_of(e) for e in about if e is not None]
    named = designs_named(reply, names)  # the reply's designs, in its order (ids)
    if not turn_dids and not named and session.thread.focus_id:
        turn_dids = [session.thread.focus_id]  # a question about the design under discussion
    for did in list(dict.fromkeys(turn_dids + named)):
        e = by_did.get(did) or next((x for x in about if x is not None and did_of(x) == did), None)
        if e is None:
            continue
        base = original_of(e, session)
        if base is not None:  # the design a what-if was run on came up before it
            state.mention(
                did_of(base), base.alternative.uid, base.alternative.code, what_of(base, session), n
            )
        state.mention(did, e.alternative.uid, e.alternative.code, what_of(e, session), n)
    state.ask(n, said, NOT_ANSWERED.get(behaviour, ""))
    # Decisions: a new recommendation, the inputs confirmed, a what-if run.
    if session.chosen is not None and did_of(session.chosen) != state.chosen:
        state.chosen = did_of(session.chosen)
        a = session.chosen.alternative
        picks = what_of(session.chosen, session).replace(", recommended", "")
        state.decide(f"T{n}: recommended {a.uid or a.code}" + (f" ({picks})" if picks else ""))
    confirmed = (getattr(session, "confirmed", None) or {}).get(session.project.id, "")
    if confirmed and confirmed != state.confirmed:
        state.confirmed = confirmed
        state.decide(f"T{n}: the user confirmed the project's inputs")
    for e in new:
        if e.alternative.role == "what_if":
            state.decide(f"T{n}: ran {e.alternative.uid or did_of(e)} ({what_of(e, session)})")
    # The question left open, with its options.
    pending = session.pending or {}
    state.open = []
    if pending:
        options = [str(o) for o in pending.get("options") or []]
        if pending.get("kind") == "decision":
            options = [str(c[0]) for c in pending.get("choices") or []]
        asked = {
            "confirm": "the inputs card: run with these inputs, or say what to change",
            "which_design": "which design the question is about",
        }.get(str(pending.get("kind")), flat(reply, 140))
        if options:
            asked += " Options: " + "; ".join(
                f"{i}. {flat(o, 70)}" for i, o in enumerate(options[:4], 1)
            )
        state.open = [f"T{n}: {asked}"]
    # The figures the reply gave that are its designs' own (their ledger values).
    from gemini_agent import answer as answering
    from gemini_agent import lookup

    said = set()  # a figure two designs share is the first one's (the turn's own first)
    for did in list(dict.fromkeys(turn_dids + named))[:4]:
        e = by_did.get(did)
        if e is None or not reply:
            continue
        try:
            facts = lookup.design_facts(e)
        except Exception:  # noqa: BLE001 - a design without a year: no figures
            continue
        for key in FIGURES:
            f = facts.get(key)
            if f is None or (key, f.value) in said or not re.search(r"\d", f.value):
                continue
            if answering.contains(reply, f.value):
                said.add((key, f.value))
                state.figure(n, e.alternative.uid or e.alternative.code, WHAT[key], f.value)


def _designs_text(state: ChatState, session, with_figures: bool) -> List[str]:
    """Return the designs in the order they came up, one item each."""
    from gemini_agent import reliability

    out = []
    for d in state.designs:
        found, _ = reliability.resolve([d["did"]], session)
        e = found[0] if found else None
        what = d.get("what") or ""
        bits = [x for x in (what, f"T{d['turn']}") if x]
        if with_figures and e is not None:
            bits.append(figures(e))
        out.append(f"{d['id']} · {d['code']} ({'; '.join(bits)})")
    return out


def _questions(state: ChatState) -> str:
    """Return the user's questions: the first two and the last ``RECENT`` word for word."""
    items = []
    total = len(state.asked)
    for k, (turn, question, done) in enumerate(state.asked):
        recent = k < 2 or k >= total - RECENT
        q = question if recent else flat(question, 40)
        items.append(f"T{turn} «{q}»" + (f" ({done})" if done else ""))
    head = f"{state.earlier}; " if state.earlier else ""
    return head + "; ".join(items)


# Words that point to no turn in particular (a question's frame, the chat's usual topics).
COMMON = set(
    "what which when where were was did does have has had that this these those with from "
    "about before after then than they them your you our ask asked question questions said "
    "say tell told discuss discussing discussed talk talking chat right just very first last "
    "again back sorry please design designs plant".split()
)


def _words(text: str) -> set:
    """Return a message's words of four letters or more, but those that point to no turn."""
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in COMMON}


def pointed(state: ChatState, message: str) -> List[int]:
    """Return the earlier turns a message's own words point to: a word only that turn has.

    "What were we discussing before the weather?" shares "weather" with one turn only; the
    model then reads the turns around it (``turns_text``) instead of counting lines.
    """
    said = _words(message)
    if not said or not state.asked:
        return []
    where: Dict[str, List[int]] = {}
    for turn, question, _ in state.asked:
        for w in _words(question) & said:
            where.setdefault(w, []).append(turn)
    found = sorted({ts[0] for ts in where.values() if len(ts) == 1})[:2]
    # A message that repeats an earlier one is not about it: most of its words are that turn's.
    raw = set(re.findall(r"[a-z]{4,}", message.lower()))
    asked = {t: q for t, q, _ in state.asked}
    return [
        t
        for t in found
        if not raw or len(raw & set(re.findall(r"[a-z]{4,}", asked[t].lower()))) < 0.7 * len(raw)
    ]


def _line(turn: int, question: str, done: str) -> str:
    """Return one turn of the log: "T3: «…» (declined as off-topic)"."""
    return f"T{turn}: «{question}»" + (f" ({done})" if done else "")


def pointer_text(state: Optional[ChatState], message: str) -> str:
    """Return the earlier turn a message's own words point to, with its neighbours ("" if none).

    "This message's words point to T9: «the weather?»; just before it: T8: «outside air?»."
    Code finds the turn and its neighbours; the model reads which one the question wants.
    """
    if not on() or state is None or not message:
        return ""
    by_turn = {turn: _line(turn, q, done) for turn, q, done in state.asked}
    out = []
    for t in pointed(state, message):
        near = [
            f"just before it: {by_turn[t - 1]}" if t - 1 in by_turn else "",
            f"just after it: {by_turn[t + 1]}" if t + 1 in by_turn else "",
        ]
        out.append(
            f"This message's words point to {by_turn[t]}; "
            + "; ".join(x for x in near if x)
            + ("." if any(near) else "")
        )
    return " ".join(out)


RELATION_PROMPT = (
    "A user's message names an earlier turn of a chat by its words. Say which turn the message "
    "asks about: the named turn itself, the one just before it, the one just after it, or "
    "none when the message does not ask about the chat's turns (a question about the plant "
    "that only shares a word). Read the meaning, in any words or language. Reply with JSON."
)


def relation(state: Optional[ChatState], message: str, llm) -> Tuple[str, Optional[object]]:
    """Return the turn a question about the chat asks about (a line of the log), and the call.

    Code finds the turn the message's words point to (``pointed``) and its neighbours; the
    model only says which of them the message asks about ("before the weather": the one
    before); code then picks that line (5 Nov: the 9B named the wrong neighbour itself).
    "" when no turn is pointed to, the model says none, or the turn has no such neighbour.
    """
    from gemini_agent.llm import LLMError

    if not on() or state is None or not message or llm is None:
        return "", None
    turns = pointed(state, message)
    if len(turns) != 1:
        return "", None
    t = turns[0]
    by_turn = {turn: _line(turn, q, done) for turn, q, done in state.asked}
    schema = {
        "type": "object",
        "properties": {"turn": {"type": "string", "enum": ["itself", "before", "after", "none"]}},
        "required": ["turn"],
    }
    msgs = [
        {"role": "system", "content": RELATION_PROMPT},
        {"role": "user", "content": f"Named turn: {by_turn[t]}\nMessage: {message}"},
    ]
    try:
        raw, call = llm.structured("chat_turn", msgs, schema, 20)
    except LLMError as err:
        return "", err.call
    except Exception:  # noqa: BLE001 - a help for one kind of question, never a failure
        return "", None
    which = str(raw.get("turn") or "") if isinstance(raw, dict) else ""
    k = {"before": t - 1, "after": t + 1}.get(which)
    return (by_turn.get(k, "") if k is not None else ""), call


def turns_text(state: Optional[ChatState], limit: int = 0, message: str = "") -> str:
    """Return the user's earlier messages, one a line, numbered by turn ("" when none).

    "What were we discussing before the weather?", "which question did I ask right after the
    heat split?" (5 Nov) are lookups in this list: the model reads the turn before or after.
    Joined on one line with the state, the 9B model named the wrong neighbour. ``limit``:
    characters (0: none); the oldest lines go first, the first two stay ("what did I ask
    first?"), and the text says how many it left out.
    """
    if not on() or state is None or not state.asked:
        return ""
    now = state.asked[-1][0] + 1
    lines = [_line(turn, question, done) for turn, question, done in state.asked]
    head = (
        "The user's earlier messages, in the order they were sent (kept by code; "
        f"the message being answered now is T{now}):"
    )
    if state.earlier:
        head += f"\n{state.earlier}"
    pointers = [pointer_text(state, message)] if pointer_text(state, message) else []
    keep = lines
    size = len(head) + sum(len(x) + 1 for x in pointers)
    while limit and len(keep) > 3 and size + sum(len(x) + 1 for x in keep) > limit:
        keep = keep[:2] + keep[3:]  # the oldest after the first two go first
    if len(keep) < len(lines):
        keep = keep[:2] + [f"… ({len(lines) - len(keep)} turns not shown)"] + keep[2:]
    return "\n".join([head] + keep + pointers)


def text(state: Optional[ChatState], session, kind: str = "answer", limit: int = 0) -> str:
    """Return the state for a prompt ("" when off or empty).

    ``answer``: everything, the designs with their figures; ``reading``: the designs (without
    figures: the which-design reading has them on its options), the decisions and the open
    question, without the questions. ``limit``: characters (0: none); the oldest questions are
    cut shorter first, then the figures, then the designs from the middle, never silently: the
    text says what it leaves out.
    """
    if not on() or state is None or not (state.designs or state.asked):
        return ""
    # The questions are the turn log's (``turns_text``), a block of their own;
    # ``kind="answer+questions"`` puts them here as well.
    questions = kind == "answer+questions"
    if questions:
        kind = "answer"
    figures_on = kind == "answer"
    designs = state.designs
    while True:
        lines = ["Conversation state (kept by code):"]
        if designs:
            shown = ChatState(designs=designs)
            items = _designs_text(shown, session, figures_on)
            gone = len(state.designs) - len(designs)
            tail = f" ({gone} more not shown)" if gone else ""
            lines.append("- Designs in the order they came up: " + "; ".join(items) + tail + ".")
        if state.decisions:
            lines.append("- Decided: " + "; ".join(state.decisions[-4:]) + ".")
        if questions and state.asked:
            lines.append("- The user's questions so far: " + _questions(state) + ".")
        # The figures a reply gave, but for those the designs' line already shows.
        listed = {"cost of heat", "CO2 saving", "capital cost"} if figures_on else set()
        said = [
            f"T{x['turn']} {x['id']} {x['what']} {x['value']}"
            for x in state.numbers
            if x["what"] not in listed
        ]
        if said and kind == "answer":
            lines.append("- Figures given lately: " + "; ".join(said) + ".")
        if state.open:
            lines.append("- Open: " + state.open[-1])
        out = "\n".join(lines)
        if not limit or len(out) <= limit:
            return out
        if questions and kind == "answer" and len(state.asked) > RECENT:
            state = ChatState(**dict(state.to_dict(), asked=state.asked[-RECENT:]))
            continue
        if figures_on:
            figures_on = False
            continue
        if len(designs) > 3:
            designs = designs[:1] + designs[-2:] if len(designs) > 4 else designs[:3]
            continue
        return out[: limit - 1].rsplit(" ", 1)[0] + "…"


def annotate(options: Sequence[Tuple[str, str]], session) -> List[str]:
    """Return the which-design options marked with their place in the chat, for the model.

    "A48 · cheapest (1D-BO-EC@3500-FC); 1st in the last list shown; came up at T2; heat 62.7
    €/MWh, CO2 saving 63.1%, capital 34.2 M€". The design under discussion and the original
    design of a what-if under discussion are said so.
    """
    from gemini_agent import reliability

    thread = session.thread
    shown = [x.split(" (")[0] for x in thread.shown]
    state = getattr(session, "state", None)
    came = {d["did"]: d["turn"] for d in (state.designs if state else [])}
    focus = thread.focus_id
    focus_entry = reliability.resolve([focus], session)[0] if focus else []
    base = original_of(focus_entry[0], session) if focus_entry else None
    out = []
    for label, did in options:
        bits = []
        if did == focus:
            bits.append("the design under discussion")
        if base is not None and did == did_of(base):
            bits.append("the original design (before the what-if under discussion)")
        if did in shown and len(shown) >= 2:
            k = shown.index(did)
            bits.append(f"{ORDINALS[k] if k < len(ORDINALS) else k + 1} in the last list shown")
        if did in came:
            bits.append(f"came up at T{came[did]}")
        found = reliability.resolve([did], session)[0]
        if found:
            bits.append(figures(found[0]))
        out.append(label + ("; " + "; ".join(bits) if bits else ""))
    return out


def add_shown(options: List[Tuple[str, str]], session, cap: int = 8) -> List[Tuple[str, str]]:
    """Return the options with the designs of the last list shown and the chat's state added.

    "The second one" may be a design no pick of the latest search (an earlier search's, a
    what-if): it must be an option to be read as one.
    """
    from gemini_agent import reliability

    seen = {did for _, did in options}
    out = list(options)
    state = getattr(session, "state", None)
    wanted = [x.split(" (")[0] for x in session.thread.shown]
    wanted += [d["did"] for d in (state.designs if state else [])]
    for did in wanted:
        if did in seen or len(out) >= cap:
            continue
        found = reliability.resolve([did], session)[0]
        if not found or found[0].alternative.role == "reference":
            continue
        seen.add(did)
        e = found[0]
        what = what_of(e, session) or "a design"
        a = e.alternative
        out.append((f"{a.uid or a.code} · {what} ({a.code})", did))
    return out
