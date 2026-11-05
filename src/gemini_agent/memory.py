"""What the user asked Dioscuri to remember: their name, how to address them, how to answer.

A user's test on 5 Nov: "please call me by my name" in the first message, then a design, and
the replies stopped using the name; asked "do you remember my name?", the true sentence "I
remember your name from our first conversation" was removed by the claim checker (the name was
in no source it weighed), and "why did you stop?" got a muddled answer. The turn log had the
message, but nothing marked it as a standing request, and nothing kept it for later chats.

Here a short model call reads each typed message for a standing request or a fact about the
user to keep (``read``): their name, their role, how to address them, the language, units or
length of answers. Code checks what it returns (``checked``): the note must come from the
message's own words, be short, and be new. Notes live with the project (``Store``), so every
chat of a project shares them; each chat keeps its own conversation, designs and inputs. With
no store (the evaluations, the CLI) they live with the conversation (``Session.notes``), so
separate chats never see each other's.

The answerer gets them as a ``notes`` block in every reply's context (never cut), with its own
rule line, and the claim checker reads them first: a sentence that uses or recalls them is
backed. The user can see and remove them in the app (``GET``/``DELETE
/api/projects/{id}/memory``). Values for the design (a depth, a price) are not notes: they go
through the inputs card.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from gemini_agent.llm import LLMCall, LLMError

MAX_NOTES = 12  # kept per project; the oldest go first
NOTE_CHARS = 120
TITLE = (
    "what the user asked Dioscuri to remember, in their own words (shared by every chat in this "
    "project; a reply follows it and may say it: their name, how to address them, how to answer)"
)
PROMPT = (
    "You read one message a user sent to Dioscuri, an assistant that designs geothermal heating "
    "and cooling plants. Say whether it asks Dioscuri to remember something about the user for "
    "the rest of the conversation, or to keep doing something in every reply: their name or how "
    "to address them, their role or organisation, the language, units, tone or length of the "
    "answers. Write it as a short note in the user's own terms, for example 'call the user "
    "Sam' or 'answer in Dutch'. Leave it empty for anything else: a question, a design "
    "request, values for the design (depths, prices, temperatures, doublets), an opinion, or "
    "small talk. Also give the numbers of the earlier notes the message asks to drop or "
    'change ("stop calling me that", "actually my name is ..."), in any words or language. '
    'A question or complaint about a note drops nothing ("do you remember my name?", "why '
    'did you stop calling me Sam?" keep the note). Most messages drop nothing: a question, a '
    'design request, an answer to Dioscuri ("yes", "looks right, go ahead", "run it"). Reply '
    "with JSON only."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "remember": {"type": "string", "maxLength": NOTE_CHARS},
        "forget": {"type": "array", "items": {"type": "integer"}, "maxItems": MAX_NOTES},
    },
    "required": ["remember", "forget"],
}
STOP = set(
    "the a an and or to of in on for with from by as at is are be please me my i you your user "
    "users call called keep always every reply replies answer answers dioscuri remember note "
    "name named that this from now".split()
)


@dataclass
class Note:
    """One thing to remember, with where it came from."""

    text: str  # "call the user Reza"
    said: str  # the message it came from, short
    thread: str = ""  # the chat it was said in
    turn: int = 0
    at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        """Return a note saved by ``asdict`` (unknown keys ignored)."""
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def on() -> bool:
    """Return True unless ``DIOSCURI_NOTES=0`` turns the memory reading off."""
    return os.environ.get("DIOSCURI_NOTES", "1").strip().lower() not in ("0", "false", "off")


def _flat(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _words(text: str) -> set:
    return {w for w in re.findall(r"[^\W\d_]{3,}", (text or "").lower()) if w not in STOP}


def checked(remember: str, message: str, notes: Sequence[Note]) -> str:
    """Return the note to keep, or "" (code's checks on what the model read).

    The note must be short, carry a word of the message itself (a name, a language: the model
    may not add what was not said), and not repeat a note already kept.
    """
    text = _flat(remember, NOTE_CHARS).strip(" .;")
    if len(text) < 4:
        return ""
    if not (_words(text) & _words(message)):
        return ""
    same = _words(text)
    for n in notes:
        if n.text.lower() == text.lower() or (same and _words(n.text) == same):
            return ""
    return text


FEW = set(
    "the a an and or to of in on for with from by as at is are be it that this me my you "
    "your".split()
)


def _stems(text: str) -> set:
    return {w[:4] for w in re.findall(r"[^\W\d_]{3,}", (text or "").lower()) if w not in FEW}


def touches(message: str, note: Note) -> bool:
    """Return True when a message may drop a note: it shares a word with the note or its source.

    On 5 Nov the 9B dropped "call the user Sam" for "Looks right, go ahead.", and the design
    reply lost the name. "Stop calling me Sam" and "actually my name is Ali" share a word with
    the note or the message it came from (stems of four letters: "calling" and "call"); a
    go-ahead shares none. A note the reading cannot drop can still be forgotten in the sidebar.
    """
    return bool(_stems(message) & (_stems(note.text) | _stems(note.said)))


def read(message: str, notes: Sequence[Note], llm) -> Tuple[str, List[int], Optional[LLMCall], str]:
    """Return the note a message asks to keep, the notes it cancels, the call and any error.

    Parameters
    ----------
    message : str
        The user's message.
    notes : sequence of Note
        What is remembered already (numbered from 1 in the prompt).
    llm : OllamaLLM or ScriptedLLM
        The model that reads it (the reader).

    Returns
    -------
    tuple of (str, list of int, LLMCall or None, str)
        The checked note ("" when none), the indexes (from 0) of the notes to forget, the call
        and the error ("" when the call worked).
    """
    if not message.strip() or llm is None:
        return "", [], None, ""
    listed = "\n".join(f"{i}. {n.text}" for i, n in enumerate(notes, 1)) or "none"
    msgs = [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"Earlier notes:\n{listed}\n\nMessage: {_flat(message, 1500)}"},
    ]
    try:
        raw, call = llm.structured("memory", msgs, SCHEMA, 60)
    except LLMError as err:
        return "", [], err.call, str(err)
    except Exception as err:  # noqa: BLE001 - a help, never a reason for a turn to fail
        return "", [], None, f"{type(err).__name__}: {err}"
    raw = raw if isinstance(raw, dict) else {}
    drop = []
    for k in raw.get("forget") or []:
        if isinstance(k, int) and 1 <= k <= len(notes) and k - 1 not in drop:
            if touches(message, notes[k - 1]):
                drop.append(k - 1)
    said = str(raw.get("remember") or "")
    if any(_flat(said, NOTE_CHARS).strip(" .;").lower() == notes[i].text.lower() for i in drop):
        return "", [], call, ""  # the same note again: nothing changes
    keep = checked(said, message, [n for i, n in enumerate(notes) if i not in drop])
    return keep, drop, call, ""


def block_text(notes: Sequence[Note], thread: str = "", turn: int = 0) -> str:
    """Return the notes as the answerer reads them ("" when none).

    ``turn``: the turn being answered; a note it gave is marked "said in this message", so a
    message that only asks to remember something is answered by saying so (5 Nov: "call me
    Alex instead" got "would you like to continue discussing the design?").
    """
    lines = []
    for n in notes:
        if n.thread == thread and turn and n.turn == turn:
            where = "said in this message"
        elif n.thread == thread and n.turn:
            where = f"T{n.turn} of this chat"
        else:
            where = "another chat of this project" if n.thread != thread else "this chat"
        lines.append(f"- {n.text} (the user wrote «{_flat(n.said, 140)}», {where})")
    return "\n".join(lines)


SAFE = re.compile(r"[^A-Za-z0-9_.-]")


class Store:
    """The notes of every project, one JSON file each, under one folder (thread-safe)."""

    def __init__(self, folder):
        """Use ``folder`` (made when the first note is saved)."""
        self.folder = Path(folder)
        self._lock = threading.Lock()

    def _path(self, project_id: str) -> Path:
        name = SAFE.sub("_", project_id or "challenge")[:80] or "challenge"
        return self.folder / f"{name}.json"

    def notes(self, project_id: str) -> List[Note]:
        """Return a project's notes, oldest first ([] when none or unreadable)."""
        path = self._path(project_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [Note.from_dict(d) for d in data.get("notes", []) if isinstance(d, dict)]

    def save(self, project_id: str, notes: Sequence[Note]) -> None:
        """Write a project's notes (the last ``MAX_NOTES``); remove the file when none."""
        path = self._path(project_id)
        with self._lock:
            if not notes:
                path.unlink(missing_ok=True)
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            body = {"project": project_id, "notes": [asdict(n) for n in list(notes)[-MAX_NOTES:]]}
            tmp.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, path)

    def forget(self, project_id: str, note_id: Optional[str] = None) -> int:
        """Remove one note (by id), or all when ``note_id`` is None; return how many went."""
        notes = self.notes(project_id)
        left = [n for n in notes if note_id is not None and n.id != note_id]
        self.save(project_id, left)
        return len(notes) - len(left)


def default_folder() -> Path:
    """Return where the app keeps the notes (``DIOSCURI_MEMORY``)."""
    runs = Path(__file__).resolve().parents[2] / "hackathon" / "evals" / "runs"
    return Path(os.environ.get("DIOSCURI_MEMORY", runs / "memory"))


def view(notes: Sequence[Note]) -> List[dict]:
    """Return the notes as the app shows them."""
    return [
        {"id": n.id, "text": n.text, "said": n.said, "thread": n.thread, "turn": n.turn, "at": n.at}
        for n in notes
    ]
