"""The recommended design for the challenge: the default search, run once and kept.

The design the chat would give for the organisers' district (``engine.search`` on a new
conversation's brief), with a pass or fail per hard cap and its year. The app opened on it until
5 Nov; a new chat now starts empty, and the report's scripts read it (``GET /api/lead``). It is
computed once, in the background on the first request (at the server's start with
``DIOSCURI_LEAD_AT_START=1``), and kept on disk (``DIOSCURI_LEAD``) under a fingerprint of the
code and data it depends on, so a change of the model computes it again.

``Lead.session_for`` puts that search into an empty conversation, as if the chat had run it, so
the tabs show the design and the chat can be asked about it. ``python -m gemini_agent.lead``
writes the cache ahead (a release can ship it: the fingerprint matches while the code does).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from gemini_agent import cost_basis, engine, projects, reporter, workbench

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(
    os.environ.get(
        "DIOSCURI_LEAD", ROOT / "hackathon" / "evals" / "runs" / "lead" / "challenge.json"
    )
)
VERSION = 1
MESSAGE = "The recommended design for the challenge district (computed when the app started)"
OPENED = "Show the recommended design for the challenge district."

# The challenge's hard caps, as the verifier names its checks (``verifier.verify``), in order.
CAPS = (
    ("doublets", re.compile(r"^One to three doublets")),
    ("flow", re.compile(r"^Flow .* per doublet")),
    ("brine", re.compile(r"^Brine cooled by at most")),
    ("days", re.compile(r"^At most \d+ days per doublet")),
    ("heat", re.compile(r"^Heat at .* every day")),
    ("cold", re.compile(r"^Cold at .* every day")),
)


def _files() -> List[Path]:
    """Return the files the recommendation depends on: the models, the engine, the data."""
    src = ROOT / "src"
    out = sorted((src / "dioscuri_plant").glob("*.py"))
    out += sorted((src / "dioscuri_plant" / "data").glob("*"))  # the weather (free cooling)
    out += [
        src / "gemini_agent" / n
        for n in (
            "engine.py",
            "verifier.py",
            "contract.py",
            "projects.py",
            "reporter.py",
            "workbench.py",
            "cost_basis.py",
            "lead.py",
        )
    ]
    out += sorted(Path(projects.CHALLENGE_DIR).glob("*"))
    return [p for p in out if p.is_file()]


def fingerprint() -> str:
    """Return a hash of the code and data the recommendation depends on, and the settings."""
    h = hashlib.sha256(f"v{VERSION}".encode())
    for p in _files():
        h.update(p.name.encode())
        h.update(p.read_bytes())
    for key in ("DIOSCURI_SWEEP", "DIOSCURI_PHYSICS"):
        h.update(f"{key}={os.environ.get(key, '')}".encode())
    return h.hexdigest()[:16]


def caps(entry) -> List[dict]:
    """Return the challenge's hard caps for a design: label, passed, the verifier's detail."""
    out = []
    for key, pattern in CAPS:
        check = next((c for c in entry.verification.checks if pattern.match(c.name)), None)
        if check is None:
            continue
        out.append(
            {
                "key": key,
                "label": (
                    check.name.replace("m3/h", "m³/h").replace("-", "–", 1)
                    if key == "flow"
                    else check.name
                ),
                "passed": bool(check.passed),
                "detail": check.detail.replace("m3/h", "m³/h").replace("m3 ", "m³ "),
            }
        )
    return out


def compute(record: Callable) -> dict:
    """Run the default search and return the cache: the summary and a conversation holding it.

    Parameters
    ----------
    record : callable
        ``record(session, outcome, brief, message)``: keeps the search in a conversation as the
        chat does (``Agent._record_search``: S1, the names A1, A2 ...).

    Returns
    -------
    dict
        ``{"fingerprint", "computed_at", "seconds", "summary", "session"}``.
    """
    from gemini_agent.agent import Session

    start = time.perf_counter()
    session = Session(thread_id="lead")
    brief = session.brief
    outcome = engine.search(brief, {})
    session.candidates = outcome.candidates
    session.reference = outcome.reference
    record(session, outcome, brief, MESSAGE)
    session.searches[-1]["card"] = reporter.candidates_payload(outcome)
    session.searches[-1]["lead"] = True
    if outcome.chosen is not None:
        session.ledger.append(outcome.chosen)
        session.chosen = outcome.chosen
        # The chat's context: the design was shown, with the reply the chat writes for a search,
        # so "this design" in the first question is the recommended one.
        session.history = [
            {
                "user": OPENED,
                "reply": reporter.challenge_answer(outcome, reporter.Facts(OPENED)),
                "kind": "design",
            }
        ]
    seconds = round(time.perf_counter() - start, 1)
    return {
        "version": VERSION,
        "fingerprint": fingerprint(),
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": seconds,
        "summary": summary(session, outcome),
        "session": session.to_dict(),
    }


def summary(session, outcome) -> dict:
    """Return the recommendation's view: the design, its caps, its cost basis and the picks."""
    chosen = outcome.chosen
    s = engine.summary(outcome)
    search = {
        "layouts": s["candidates"],
        "valid": s["valid"],
        "years": s["years"],
        "picks": [
            {
                "pick": k,
                "label": engine.PICK_NAMES[k],
                "uid": e.alternative.uid,
                "code": e.alternative.code,
                "lcoe": e.economics.lcoe_eur_per_mwh,
                "co2_t": round(e.economics.co2_t_per_year or 0.0),
            }
            for k in engine.PICKS
            for e in [next((x for x in outcome.candidates if k in x.alternative.picks), None)]
            if e is not None
        ],
    }
    if chosen is None:
        return {"found": False, "search": search}
    view = workbench.design_view(session, chosen)
    # Wells deeper than the aquifer the requirements describe assume that aquifer there: said.
    known = outcome.rules.reservoir_depth_m
    deeper = any(d.get("depth_m", known) != known for d in chosen.alternative.doublets or []) or (
        chosen.alternative.depth_m and chosen.alternative.depth_m != known
    )
    assumed = next((n for n in outcome.notes if n.startswith("Depths other than")), None)
    return {
        "found": True,
        "design": view,
        "assumed": assumed if deeper else None,
        "words": engine.plant_name(engine.plant_of(chosen.alternative), outcome.rules),
        "caps": caps(chosen),
        "checks": {
            "passed": sum(c.passed for c in chosen.verification.checks),
            "total": len(chosen.verification.checks),
        },
        "basis": cost_basis.basis(chosen, {}),
        "search": search,
    }


class Lead:
    """The recommendation, computed once in the background and kept on disk.

    ``spawn`` (the server) computes it in a process of its own (``python -m gemini_agent.lead``):
    the search forks worker processes (``dioscuri_plant.parallel.pmap``), and a fork from a
    server busy with other threads (the document index being built at start) can hang a worker
    until pmap's 300 s timeout (3 Nov: the first screen waited five minutes). A process of its
    own has one thread when it forks. Without ``spawn`` (tests) it runs in a thread here.
    """

    def __init__(self, record: Callable, path: Optional[Path] = None, spawn: bool = False):
        """Keep the search with ``record`` (``Agent._record_search``); cache at ``path``."""
        self.record = record
        self.spawn = spawn
        self.path = Path(path) if path is not None else CACHE
        self._data: Optional[dict] = None
        self._error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._started = 0.0

    def _load(self) -> Optional[dict]:
        try:
            data = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return None
        if data.get("version") != VERSION or data.get("fingerprint") != fingerprint():
            return None
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, default=str), "utf-8")
        tmp.replace(self.path)

    def _spawned(self) -> dict:
        """Compute in a process of its own, which writes the cache; return what it wrote."""
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "src"), str(ROOT)] + [p for p in [env.get("PYTHONPATH")] if p]
        )
        done = subprocess.run(
            [sys.executable, "-m", "gemini_agent.lead", str(self.path)],
            env=env,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if done.returncode != 0:
            last = (done.stderr or done.stdout or "").strip().splitlines()[-1:] or ["no output"]
            raise RuntimeError(f"the computation stopped: {last[0]}")
        data = self._load()
        if data is None:
            raise RuntimeError("the computation wrote no matching result")
        return data

    def _run(self) -> None:
        try:
            if self.spawn:
                self._data = self._spawned()
            else:
                data = compute(self.record)
                self._write(data)
                self._data = data
        except Exception as err:  # noqa: BLE001 - said by GET /api/lead, the chat still works
            log.exception("the recommended design could not be computed")
            self._error = f"{type(err).__name__}: {err}"

    def start(self) -> None:
        """Load the cache, or compute it in the background (once)."""
        with self._lock:
            if self._data is not None or self._thread is not None:
                return
            self._data = self._load()
            if self._data is not None:
                return
            self._started = time.time()
            self._thread = threading.Thread(target=self._run, name="dioscuri-lead", daemon=True)
            self._thread.start()

    def wait(self, timeout: Optional[float] = None) -> Optional[dict]:
        """Start if needed and wait for the result (tests, scripts); None when not done."""
        self.start()
        if self._thread is not None:
            self._thread.join(timeout)
        return self._data

    def view(self) -> dict:
        """Return the recommendation's view, or the state while it computes."""
        self.start()
        if self._data is not None:
            return dict(
                self._data["summary"],
                state="ready",
                computed_at=self._data["computed_at"],
                seconds=self._data["seconds"],
            )
        if self._error:
            return {"state": "error", "error": self._error}
        return {"state": "computing", "since": round(time.time() - self._started, 1)}

    def session_for(self, thread_id: str, keep=None):
        """Return a conversation with the recommendation's search in it, or None until it is ready.

        ``keep`` is the conversation it replaces (empty): its uploads and prices stay.
        """
        from gemini_agent.agent import Session

        if self._data is None:
            return None
        session = Session.from_dict(dict(self._data["session"], thread_id=thread_id))
        if keep is not None:
            session.attachments = list(keep.attachments)
            session.flagged = list(keep.flagged)
            session.assumptions = dict(keep.assumptions or {})
        return session


def has_lead(session) -> bool:
    """Return whether a conversation holds the recommendation's search."""
    return any(s.get("lead") for s in session.searches or [])


def design_of(session) -> Optional[str]:
    """Return the id of the recommended design in a conversation, if it holds it."""
    return workbench.design_id(session.chosen) if session.chosen is not None else None


def plain(data: Dict) -> Dict:
    """Return the summary without the year's day-by-day series (for a short print)."""
    out = dict(data)
    if "design" in out:
        out["design"] = {k: v for k, v in out["design"].items() if k not in ("year", "graph")}
    return out


def main(argv: Optional[List[str]] = None) -> None:
    """Compute the recommendation and write the cache (at the path given, else ``CACHE``).

    The server runs this in a process of its own; run it by hand to write the cache ahead
    (e.g. before a release zip is made).
    """
    from gemini_agent.agent import Agent

    args = sys.argv[1:] if argv is None else argv
    # ``_record_search`` keeps a search on a session and uses nothing of the agent itself.
    lead = Lead(lambda *a: Agent._record_search(None, *a), Path(args[0]) if args else None)
    data = lead.wait()
    if data is None:
        raise SystemExit(f"not computed: {lead.view().get('error')}")
    print(f"wrote {lead.path} ({data['seconds']} s, fingerprint {data['fingerprint']})")


if __name__ == "__main__":
    main()
