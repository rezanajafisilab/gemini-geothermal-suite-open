"""The chat's thread, kept by code: what the conversation is about, for every model call.

A teammate's long test on 3 Nov showed the chat losing the thread. Only the answerer saw earlier
turns (two exchanges, cut to 240 characters, and dropped first when the prompt was full); the
readings that decide what a message asks (intake, parameters, options, needs, route, confirm)
saw none. "And with 45 °C?", "the second one" or "back to the original design" could not be
read.

After every turn code notes, with no extra model call:

- **focus**: the design under discussion (a what-if just run, a design a question named, the
  pick of a new search);
- **shown**: the last list the chat showed, in order (the designs a reply named, the options of
  a question), so the model can resolve "the second one";
- **question**: the question Dioscuri left open, with its options;
- **stated**: what the user stated as given and whether Dioscuri corrected it;
- **lines**: one line per turn, what was asked and what was done or answered, with the reply's
  opening (its key numbers); a prompt shows the last twelve (and the answerer the first two,
  so "what did I ask first?" has an answer).

``text`` renders it, with the last exchanges in full, for a prompt; each caller gives its own
size. The models read it; code never decides from it what a message means.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

LINES = 12  # one line per turn: the last twelve go in a prompt
KEPT = 40  # lines kept with the session (the chat's first turns can still be shown)
STATED = 8  # the user's statements kept
SHOWN = 6  # the items of the last list kept
# A design's handle in a reply ("A1", "W2", "B14"): not CO2, N1 or a PV option.
HANDLE = re.compile(r"(?<![-@.\w])([A-Z]{1,2}\d{1,4})\b(?!\.\d)")
NOT_HANDLES = {"CO2", "CH4", "N1", "N2", "H2", "O2", "S1", "S2"}
MARKUP = re.compile(r"\*\*|__|`|^#+\s*|\[\^\d+\]", re.M)
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$", re.M)


def flat(text: str, limit: int) -> str:
    """Return text on one line, without Markdown marks and tables, cut at a word to ``limit``."""
    text = TABLE_LINE.sub(" ", text or "")
    text = MARKUP.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


@dataclass
class Thread:
    """What the conversation is about, kept by code after every turn (see the module)."""

    focus: str = ""  # "W1 · 1D-HP-EC-N1 (what-if of A1: gas price 45 €/MWh)"
    focus_id: str = ""  # its id (``reporter.design_id``), for code
    shown: List[str] = field(default_factory=list)  # the last list shown, in order
    shown_what: str = ""  # "designs the last reply named", "options of the question" ...
    question: str = ""  # the open question and its options, "" when none
    stated: List[str] = field(default_factory=list)  # "T3: «the boiler gives a quarter» ..."
    lines: List[str] = field(default_factory=list)  # one per turn, the last ``KEPT``

    def to_dict(self) -> dict:
        """Return the thread as plain data (saved with the session)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "Thread":
        """Return the thread saved by ``to_dict`` (an empty one for older sessions)."""
        data = data or {}
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)

    def note(
        self,
        n: int,
        user: str,
        reply: str,
        did: str,
        focus: Optional[tuple] = None,
        listed: Sequence[str] = (),
        listed_what: str = "",
        question: str = "",
        stated: Sequence[str] = (),
    ) -> None:
        """Record turn ``n``: its line, the focus, the list shown, the open question, statements.

        Parameters
        ----------
        n : int
            The turn's number in the conversation.
        user : str
            What the user wrote (or clicked).
        reply : str
            Dioscuri's reply as shown.
        did : str
            What Dioscuri did, in a few words ("ran the what-if W1 on A1: gas price 45 €/MWh").
        focus : tuple of (str, str), optional
            The design under discussion after this turn (its label, its id); None keeps the
            one there was.
        listed : sequence of str
            The list this turn showed, in order (two items or more), or nothing.
        listed_what : str
            What that list is.
        question : str
            The question left open (with its options), "" when none.
        stated : sequence of str
            What the user stated as given this turn, each with what Dioscuri made of it.
        """
        line = f"T{n} user: «{flat(user, 120)}» → Dioscuri {did}"
        lead = flat(reply, 180)
        if lead:
            line += f": «{lead}»"
        self.lines = (self.lines + [line])[-KEPT:]
        if focus is not None and focus[0]:
            self.focus, self.focus_id = focus
        if len(listed) >= 2:
            self.shown = list(listed)[:SHOWN]
            self.shown_what = listed_what or "designs the reply named"
        self.question = question
        if stated:
            self.stated = (self.stated + [f"T{n}: {s}" for s in stated])[-STATED:]

    def text(
        self,
        history: Sequence[dict] = (),
        exchanges: int = 3,
        user_chars: int = 300,
        reply_chars: int = 500,
        lines: int = LINES,
        limit: int = 0,
        first: int = 0,
    ) -> str:
        """Return the thread for a prompt; "" when the conversation has no earlier turn.

        Parameters
        ----------
        history : sequence of dict
            The session's last exchanges (``{"user", "reply", "kind"}``).
        exchanges : int
            How many of the last exchanges go in with their words (the rest as one line each).
        user_chars, reply_chars : int
            How much of each of those exchanges' message and reply.
        lines : int
            How many earlier turns go in as one line each (before the exchanges).
        limit : int
            Characters the text may take (0: no limit); the oldest lines go first, then the
            exchanges are cut shorter, then dropped one by one, the last one kept.
        first : int
            How many of the chat's first turns go in as lines even when older than ``lines``.

        Returns
        -------
        str
            The thread, or "" before the first exchange.
        """
        recent = [h for h in list(history)[-exchanges:] if h.get("user") or h.get("reply")]
        before = self.lines[: max(0, len(self.lines) - len(recent))]
        older = before[-lines:] if lines else []
        opening = [x for x in before[:first] if x not in older]  # the chat's first turns
        if not (recent or older or self.focus or self.question):
            return ""

        def number(line: str) -> int:
            m = TURN.match(line)
            return int(m.group(1)) if m else 0

        # The exchanges are the last turns noted (the ones before the current message).
        last = [number(x) for x in self.lines[-len(recent) :]] if recent else []
        total = number(self.lines[-1]) if self.lines else len(recent)

        def render(older: List[str], recent: List[dict], uc: int, rc: int) -> str:
            out: List[str] = []
            shown = {number(x) for x in opening + older} | set(last[-len(recent) :])
            hidden = [k for k in range(1, total + 1) if k not in shown]
            head = f"This chat has had {total} turns before this message (T1 to T{total})"
            if hidden:
                head += f"; not shown here: {spans(hidden)} (say you cannot see them if asked)"
            out.append(head + ".")
            if opening or older:
                out.append("Earlier turns, one line each:")
                out += opening + (["…"] if opening and older else []) + older
            if recent:
                out.append("The last exchanges:")
                numbers = last[-len(recent) :]
                for k, h in enumerate(recent):
                    at = f" (T{numbers[k]})" if k < len(numbers) and numbers[k] else ""
                    out.append(f"User{at}: {flat(h.get('user', ''), uc)}")
                    if h.get("reply"):
                        kind = KINDS.get(h.get("kind", ""), "")
                        who = f"Dioscuri ({kind})" if kind else "Dioscuri"
                        out.append(f"{who}: {flat(h['reply'], rc)}")
            if self.focus:
                out.append(f"Design under discussion: {self.focus}.")
            if self.shown:
                items = "; ".join(f"{i}. {s}" for i, s in enumerate(self.shown, 1))
                out.append(f"Last list shown ({self.shown_what}): {items}.")
            if self.question:
                out.append(f"Open question from Dioscuri: {self.question}")
            if self.stated:
                out.append("What the user stated as given: " + "; ".join(self.stated) + ".")
            return "\n".join(out)

        uc, rc = user_chars, reply_chars
        out = render(older, recent, uc, rc)
        while limit and len(out) > limit:
            # The middle goes first: the chat's first turns stay while others can go.
            loose = [x for x in older if number(x) > first]
            if loose:
                older = [x for x in older if x is not loose[0]]
            elif older:
                older = older[1:]
            elif opening:
                opening = opening[1:]
            elif rc > 160:
                uc, rc = max(120, uc * 2 // 3), max(160, rc * 2 // 3)
            elif len(recent) > 1:
                recent = recent[1:]
            else:
                out = out[: limit - 1].rsplit("\n", 1)[0]
                break
            out = render(older, recent, uc, rc)
        return out


TURN = re.compile(r"^T(\d+) ")


def spans(numbers: Sequence[int]) -> str:
    """Return turn numbers as spans: [2, 3, 4, 7] gives "T2-T4, T7"."""
    out: List[str] = []
    for k in sorted(numbers):
        if out and out[-1][1] == k - 1:
            out[-1][1] = k
        else:
            out.append([k, k])
    return ", ".join(f"T{a}" if a == b else f"T{a}-T{b}" for a, b in out)


# What a reply was, for the exchanges ("Dioscuri (asked a question back): …").
KINDS = {
    "reject": "declined: it read the message as asking to skip the simulator or the checks",
    "refuse": "declined as outside what it does",
    "clarify": "asked a question back",
    "report_infeasible": "found no design that meets every cap",
    "design": "ran the design tools",
    "nonsense": "said the message was not a proper question",
}


def designs_named(text: str, names: Dict[str, str]) -> List[str]:
    """Return the designs a reply names, in the order it names them first (labels).

    ``names`` maps every handle and code of the conversation's designs to its label; a code
    counts only where it stands alone (not as a part of a longer code).
    """
    found: List[tuple] = []
    for m in HANDLE.finditer(text or ""):
        key = m.group(1)
        if key in names and key not in NOT_HANDLES:
            found.append((m.start(), names[key]))
    for key, label in names.items():
        if "-" not in key:
            continue
        for m in re.finditer(rf"(?<![\w@-]){re.escape(key)}(?![\w@-])", text or ""):
            found.append((m.start(), label))
            break
    out: List[str] = []
    for _, label in sorted(found):
        if label not in out:
            out.append(label)
    return out
