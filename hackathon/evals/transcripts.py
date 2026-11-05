"""Full transcripts of the eval cases, for the judges to open in the app.

The run's JSONL keeps one line per case: its verdict and the last run's summary. A transcript
keeps the whole case: each thing the user sent (a message, the answers to a card, an upload)
and every AG-UI event the agent sent back, so the app can show the chat again read-only (the
Evidence tab's "Open transcript") with each step, tool call and its result, model call (model,
tokens, seconds) and card. They are written to ``runs/transcripts/<run>/<case>.json``; the
server reads them with ``gemini_agent.workbench.transcript``.

``Recorder`` wraps the agent the eval drives, so the runner itself changes little: it calls
``take`` after each case and ``write`` with the case's record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from gemini_agent import events as ev

# A tool result is shown as JSON in the steps; one past this size is cut (a search's full
# candidate list is in its card).
MAX_TOOL_CHARS = 8_000
# A search's card has every candidate (200 and more): the first ones, the chosen and the
# picks are kept whole; the others keep what the card's scatter plots (cost, CO2, role).
FULL_CANDIDATES = 12
SCATTER_KEYS = (
    "code",
    "uid",
    "id",
    "role",
    "picks",
    "reliable",
    "n_doublets",
    "depth_m",
    "lcoe",
    "lcoh",
    "lcoc",
    "co2_t",
    "co2_saving_pct",
    "capex_meur",
    "checks",
    "violations",
)


class Recorder:
    """The agent, with each exchange of the current case kept for its transcript.

    Parameters
    ----------
    agent : gemini_agent.Agent
        The agent the eval runs; every other attribute is the agent's own.
    """

    def __init__(self, agent):
        """Wrap ``agent``."""
        self.agent = agent
        self.exchanges: list = []
        self.upload = None  # what an upload case's New project gave (``badinput``)
        self.skip = False  # no chat: the case's project was not made

    def __getattr__(self, name):
        """Pass everything else to the agent (``attach``, ``models`` ...)."""
        return getattr(self.agent, name)

    def run(self, session, message: Optional[str] = None, answers=None, **kwargs):
        """Run a turn as ``Agent.run`` does, keeping what was sent and every event."""
        if self.skip:
            return
        user: dict = {"answers": dict(answers)} if answers is not None else {"message": message}
        if kwargs.get("designs"):
            user["designs"] = list(kwargs["designs"])
        events: list = []
        self.exchanges.append({"user": user, "events": events})
        for event in self.agent.run(session, message, answers, **kwargs):
            events.append(lean(event))
            yield event

    def add(self, user: dict, events: list) -> None:
        """Keep an exchange the agent did not run (an upload the app checked)."""
        self.exchanges.append({"user": user, "events": [lean(e) for e in events]})

    def take(self) -> list:
        """Return the exchanges kept since the last call, and start again."""
        out, self.exchanges = self.exchanges, []
        return out


def lean(event: dict) -> dict:
    """Return the event as kept: a very long tool result is cut, a search's card slimmed."""
    if event.get("type") == "CUSTOM" and event.get("name") == "candidates":
        value = event.get("value")
        if isinstance(value, dict) and isinstance(value.get("candidates"), list):
            slim = [
                (
                    c
                    if i < FULL_CANDIDATES or c.get("picks") or c.get("role") == "chosen"
                    else {k: c[k] for k in SCATTER_KEYS if k in c}
                )
                for i, c in enumerate(value["candidates"])
            ]
            return dict(event, value=dict(value, candidates=slim))
    if event.get("type") == "TOOL_CALL_RESULT":
        content = event.get("content")
        if isinstance(content, str) and len(content) > MAX_TOOL_CHARS:
            return dict(
                event,
                content=json.dumps(
                    {
                        "cut": f"{len(content):,} characters; the first {MAX_TOOL_CHARS:,}",
                        "start": content[:MAX_TOOL_CHARS],
                    }
                ),
            )
    return event


def app_reply(text: str, thread_id: str = "eval", outcome: str = "clarify") -> list:
    """Return the events of a reply the app gave without the agent (an upload's check)."""
    run_id = "app"
    return [
        ev.run_started(thread_id, run_id),
        *ev.text_message(f"{run_id}-msg", text),
        ev.run_finished(thread_id, run_id, result={"behaviour": outcome, "answer": text}),
    ]


def write(folder: Path, scenario: dict, row: dict, exchanges: list, project=None) -> Path:
    """Write one case's transcript and return its path.

    Parameters
    ----------
    folder : Path
        ``runs/transcripts/<run>``.
    scenario : dict
        The case as run (placeholders filled).
    row : dict
        The case's record in the run's JSONL (verdict, checks, the last run's summary).
    exchanges : list of dict
        ``Recorder.take()``: what the user sent and the events of each run.
    project : ProjectData, optional
        The project the chat was in.
    """
    result = row.get("result") or {}
    data = {
        "version": 1,
        "run": folder.name,
        "case": row["id"],
        "base": scenario.get("base"),
        "after": scenario.get("after"),
        "group": scenario.get("group"),
        "prompt": row.get("prompt"),
        "attachment": scenario.get("attachment"),
        "upload": scenario.get("upload"),
        "expect": scenario.get("expect") or {},
        "check_names": scenario.get("checks") or [],
        "model": row.get("model"),
        "device": row.get("device"),
        "reasoning": row.get("reasoning"),
        "expected": row.get("expected"),
        "got": result.get("behaviour"),
        "pass": row.get("pass"),
        "behaviour_ok": row.get("behaviour_ok"),
        "checks": row.get("checks") or {},
        "truth": result.get("truth"),
        "verified": result.get("verified"),
        "wall_seconds": row.get("wall_seconds"),
        "project": ({"id": project.id, "name": project.name} if project is not None else None),
        "exchanges": exchanges,
    }
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{row['id']}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
    return path
