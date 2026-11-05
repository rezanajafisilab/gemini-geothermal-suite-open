"""Reply check: one evaluator call reads a finished reply against the question (4 Nov).

An evaluator-optimizer step. After the answer is written and its claims are checked, a reply
to a question (not a run report, a clarifying question or a refusal) gets one short structured
call that asks two things:

- does its first sentence answer what the message asks (the value, the yes or no, the design
  named)?
- does it speak about everything the message names ("5 MWp of solar", a second question)?

On a fail the answerer rewrites the reply once, told why (``answer.answer`` with ``revise``);
the rewrite goes through the same code checks and the claim checker as any answer. Code keeps
the first reply when the rewrite is worse: it failed the checks, is empty or is no answer, or
lost a number the first one gave (``worse``).

The model reads the meaning; code only checks what the model lists. A "missing" item must be in
the user's own words (``in_message``), and one whose figures the reply already gives is not
missing (``spoken_of``). No phrasing is matched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from gemini_agent.answer import DESIGN_CODE, load, strip_cites
from gemini_agent.intake import numbers_in
from gemini_agent.llm import LLMCall, LLMError

PROMPT = "reply_check_v1"
NUM_PREDICT = 200
REPLY_CHARS = 2400  # the reply as the check reads it, at most (an answer is 1,600 or less)
WORD = re.compile(r"[^\W\d_]{3,}")
# A number as a reply states it: not inside a handle ("A1") or a design code (``DESIGN_CODE``).
LOOSE_NUMBER = re.compile(r"(?<![A-Za-z\d.])\d+(?:[.,]\d+)*")


@dataclass
class Verdict:
    """What the check found: the first sentence answers or not, and what the reply missed."""

    first: bool = True
    missing: List[str] = field(default_factory=list)
    fix: str = ""
    # Listed by the model as missing, dropped by code: not the user's words, or already given.
    dropped: List[str] = field(default_factory=list)
    call: Optional[LLMCall] = None
    error: str = ""

    @property
    def failed(self) -> bool:
        """Return True when the reply should be rewritten (never when the check itself failed)."""
        return not self.error and (not self.first or bool(self.missing))

    def meta(self) -> dict:
        """Return what the step row and the run summary show."""
        if self.error:
            return {"verdict": "unchecked", "error": self.error}
        out = {
            "verdict": "fail" if self.failed else "pass",
            "answers_first": self.first,
            "missing": list(self.missing),
        }
        if self.fix and self.failed:
            out["fix"] = self.fix
        if self.dropped:
            out["not_missing"] = list(self.dropped)
        return out


def schema() -> dict:
    """Return the check's JSON schema."""
    return {
        "type": "object",
        "properties": {
            "first": {"type": "boolean"},
            "missing": {
                "type": "array",
                "items": {"type": "string", "maxLength": 80},
                "maxItems": 3,
            },
            "fix": {"type": "string", "maxLength": 240},
        },
        "required": ["first", "missing", "fix"],
    }


def _words(text: str) -> set:
    return {w.lower() for w in WORD.findall(text or "")}


def in_message(item: str, message: str) -> bool:
    """Return True when an item the check lists is in the user's own words.

    Its figures must all be in the message, and most of its words (the check lists what the
    message names, never what it does not).
    """
    said = {round(x, 6) for x in numbers_in(message)}
    if any(round(x, 6) not in said for x in numbers_in(item)):
        return False
    words = _words(item)
    if not words:
        return bool(numbers_in(item))
    return len(words & _words(message)) >= 0.6 * len(words)


def spoken_of(item: str, reply: str) -> bool:
    """Return True when the reply gives an item's figures with one of its words.

    Only an item with a figure is judged by code ("5 MWp of solar" when the reply says "5 MWp
    of solar panels"); without one, the model's judgement stands.
    """
    figures = numbers_in(item)
    if not figures:
        return False
    stated = {round(x, 6) for x in numbers_in(reply)}
    return all(round(x, 6) in stated for x in figures) and bool(_words(item) & _words(reply))


def check(llm, message: str, understood: str, shown: str) -> Verdict:
    """Ask the model whether a reply answers the message first and speaks of what it names.

    Parameters
    ----------
    llm : OllamaLLM or ScriptedLLM
        The model that wrote the reply (the device's model).
    message : str
        The user's message.
    understood : str
        What the answerer understood the message to ask (it settles "and the cold?").
    shown : str
        The reply as the user will see it (the "In short" value lines first).

    Returns
    -------
    Verdict
        The verdict; ``error`` when the call failed (the reply then stands as it is).
    """
    user = (
        f"User's message: {message}\n\n"
        f"What it asks, as the writer understood it: {understood or '(not said)'}\n\n"
        f"Reply:\n{shown[:REPLY_CHARS]}"
    )
    msgs = [{"role": "system", "content": load(PROMPT)}, {"role": "user", "content": user}]
    try:
        raw, call = llm.structured("reply_check", msgs, schema(), NUM_PREDICT)
    except LLMError as err:
        return Verdict(call=err.call, error=str(err))
    out = Verdict(call=call)
    if not isinstance(raw, dict):
        out.error = "the check gave no verdict"
        return out
    out.first = raw.get("first") is not False  # only a clear "no" fails
    for item in raw.get("missing") or []:
        item = " ".join(str(item).split()).strip(" .\"'“”")
        if not item:
            continue
        if not in_message(item, message) or spoken_of(item, shown):
            out.dropped.append(item)
        else:
            out.missing.append(item)
    out.fix = " ".join(str(raw.get("fix") or "").split())
    return out


def instruction(verdict: Verdict) -> str:
    """Return what the answerer is told when the reply is rewritten."""
    parts = ["Write the JSON again: the reply does not answer the user's message as asked."]
    if verdict.fix:
        parts.append(verdict.fix.rstrip(".") + ".")
    elif not verdict.first:
        parts.append("Its first sentence must answer what the message asks.")
    if verdict.missing:
        parts.append("Also speak about " + "; ".join(f"“{m}”" for m in verdict.missing) + ".")
    parts.append(
        "Keep every number, design name and citation of your reply as written, and add no "
        "number the context does not give."
    )
    return " ".join(parts)


def figures(text: str) -> set:
    """Return the numbers a reply states (not citation marks, handles or design codes)."""
    plain = DESIGN_CODE.sub(" ", strip_cites(text or ""))
    found = " ".join(m.group(0) for m in LOOSE_NUMBER.finditer(plain))
    return {round(x, 6) for x in numbers_in(found)}


def worse(first, second) -> str:
    """Return why a rewrite is worse than the first reply, or "" when it may replace it.

    Parameters
    ----------
    first, second : answer.Reply
        The reply as first written and checked, and its rewrite after the same checks.

    Returns
    -------
    str
        The reason to keep the first reply: the rewrite fell back to the template (its checks
        failed), is no answer, is (nearly) empty, or lost a number the first reply gave.
    """
    if second.fallback:
        return "the rewrite failed the answer's checks"
    if second.action != "none" or second.kind != "answer":
        return "the rewrite is not an answer"
    if len(re.sub(r"[^\w]", "", strip_cites(second.text or ""))) < 20:
        return "the rewrite is empty"
    lost = figures(first.text) - figures(second.text)
    if lost:
        listed = ", ".join(f"{x:g}" for x in sorted(lost))
        return f"the rewrite lost numbers the first reply gave ({listed})"
    return ""
