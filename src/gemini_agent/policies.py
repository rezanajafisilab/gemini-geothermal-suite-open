"""Decision points of a run, with who decided and why (``Decision``, shown as a step row).

Whether a run reasons at all is decided per message (``wants_reasoning``): the reader judges
it while reading the message, and code keeps it off where it cannot help (greetings, values,
files) and switches it on when the message asks to weigh options, or later when no design
meets the brief.

Three tools on the answer path have a flag each (``switch``): value answers written by code
(``DIOSCURI_CODE_FACTS``), the reply check (``DIOSCURI_REPLY_CHECK``, never on the CPU by
default) and thinking on hard turns (``DIOSCURI_THINK``, never on the CPU). All three are off
unless set (5 Nov). Thinking lost more cases than it won, 7 to 4 over the three suites, at 4-16 s
a hard turn. With the memory layer and the claim-check fixes in, the same code with the other two
on scored 181/185, 47/52 and 61/65 against 181, 48 and 61 with all three off, at 3 % more time,
and the "In short" line named the wrong design once ("that one" after a list).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from gemini_agent.llm import LLMCall

# Words that ask to weigh options: the reader may miss them, so code switches reasoning on.
TRADE_OFF = re.compile(
    r"\bwhich (one|design|option|system)?\s*(is|would be|'s) (better|best|cheaper|greener|safer)|"
    r"\btrade-?offs?\b|\bpros and cons\b|\bshould (we|i)\b|\bjustify\b|\bworth it\b|"
    r"\bwhat (would|should) (you|we) (relax|give up|drop|change)\b|\bprioriti[sz]e\b",
    re.IGNORECASE,
)
# Only these can gain from reasoning: values, greetings and "who are you" are answered as is.
REASONING_INTENTS = ("design", "compare", "what_if", "explain")


def wants_reasoning(read, message: str) -> Tuple[bool, "Decision"]:
    """Decide whether a message needs reasoning.

    With reasoning, the larger model plans, picks fixes and explains, and every reply is
    claim-checked. The reader judges it while reading the message (``read.think``); code
    keeps it off for values, greetings, files and off-topic messages, and on when the words
    ask to weigh options. A run that finds no design for the brief turns it on later (the
    agent does that).

    Parameters
    ----------
    read : intake.IntakeResult
        What the reader made of the message.
    message : str
        The message.

    Returns
    -------
    tuple of (bool, Decision)
        Whether to reason, and who decided and why (for the step row).
    """
    if read.screened or not read.relevant or read.bypass or read.intent not in REASONING_INTENTS:
        return False, Decision("rules", "A value, a greeting or a short reply needs no weighing.")
    if read.think:
        return True, Decision("model", "The reader judged that the reply must weigh options.")
    if TRADE_OFF.search(message):
        return True, Decision("rules", "The message asks to weigh options.")
    return False, Decision("model", "A plain request: the tools and checks are enough.")


ON = ("1", "on", "true", "yes")
OFF = ("0", "off", "false", "no")


def switch(name: str, device: str = "auto", default: str = "gpu") -> bool:
    """Return whether a flag's tool runs on this device.

    ``1`` (``on``, ``true``, ``yes``) or ``0`` (``off``, ``false``, ``no``) decide; unset or
    ``auto`` take the default: ``"on"`` always, ``"gpu"`` only when the model runs on a GPU
    (``device`` as the router says: ``gpu``, ``cpu``, or ``auto`` when it is not known).
    """
    value = os.environ.get(name, "auto").strip().lower()
    if value in ON:
        return True
    if value in OFF:
        return False
    return default == "on" or (default == "gpu" and device == "gpu")


def code_facts() -> bool:
    """Return whether code writes the values a question asks for (``DIOSCURI_CODE_FACTS``, off)."""
    return switch("DIOSCURI_CODE_FACTS", default="off")


def reply_check(device: str) -> bool:
    """Return whether a reply is checked for answering first (``DIOSCURI_REPLY_CHECK``, off)."""
    return switch("DIOSCURI_REPLY_CHECK", device, default="off")


def thinks(device: str) -> bool:
    """Return whether a hard turn's answer call thinks first (``DIOSCURI_THINK``; never on CPU).

    Off unless set (5 Nov): with the notes of its thinking, often cut mid-thought, the answer
    asked "which 2030 targets?" or "which is the most reliable?" where the context answered,
    and listed designs the chat had not shown; it won 4 cases and lost 7 over the three suites.
    """
    return device != "cpu" and switch("DIOSCURI_THINK", device, default="off")


@dataclass
class Decision:
    """Who decided a step, why, and what code changed in the model's choice."""

    decided_by: str
    reason: str
    steps: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    note: str = ""
    call: Optional[LLMCall] = None
    unavailable: bool = False

    def meta(self) -> dict:
        """Return the detail the step row shows."""
        out = {"decided_by": self.decided_by, "reason": self.reason}
        for key in ("steps", "corrections", "note"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        return out
