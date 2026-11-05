"""One Python process for the whole app: the agent's event stream plus the built front end.

Run it with ``python -m gemini_agent.server`` (port 8000) and open http://127.0.0.1:8000.

- ``POST /api/run`` with ``{"threadId", "message"}`` or ``{"threadId", "answers"}`` streams
  the run's AG-UI events as server-sent events (``data: <json>``, one per event). The agent
  decides per message whether to reason (the larger model plans, picks fixes and explains);
  ``"reasoning": true`` or ``false`` forces it. ``"device": "cpu"`` keeps every model off the
  GPU (``"auto"``, the default when a GPU is found, uses it). ``"size": "9b"`` or ``"4b"`` picks
  the model; ``"auto"`` (the default) takes the first that fits: the 9B on the GPU, the 4B on
  the GPU, the 9B on the CPU, the 4B on the CPU.
- ``GET /api/health`` says which models are configured, on which device, whether Ollama
  answers and whether each model is pulled (with the command that fixes it when not), and
  which model plays each role on the GPU and on the CPU (``profiles``).
- ``GET /api/models`` says how far loading the models has got (``warmup``): ``ready``, the
  ``state`` (``idle``, ``loading``, ``ready``, ``failed``), ``loaded`` of ``total``, the
  ``seconds`` so far, a failure's ``message`` and ``hint``, and each model's roles, name,
  device, size, state, seconds and message. The server starts loading them at start
  (``DIOSCURI_WARMUP=0`` leaves it to the first message).
- ``GET /api/projects`` lists the projects (the organisers' district first); ``POST
  /api/projects`` (form: ``name``, ``heat`` and optionally ``cool`` CSV files, the reservoir's
  ``depth_m`` and ``temperature_c``, optionally ``pressure_bar``, ``permeability_md``,
  ``thickness_m`` and the networks' ``heat_supply_c`` ... ``cool_return_c``) adds one;
  ``DELETE /api/projects/{id}`` removes one; ``POST /api/projects/profile`` (form: ``file``,
  ``kind``) reads a demand file for the form's preview. A run's ``"projectId"`` says which
  project a new conversation is in (the organisers' district when it is left out).
- ``POST /api/attachments`` (form: ``threadId``, ``file``) attaches a file to a conversation;
- ``GET /api/files?threadId=&name=`` returns a project file or an upload (``&view=1``: the
  table, chart, text or image view the chat shows); ``GET /api/doc-image?path=`` a figure
  from the documentation;
  its searches then include it (documents are data: instruction-like text is flagged).
- ``GET /api/threads/{threadId}`` returns what the session knows (brief, ledger summary);
  ``DELETE /api/threads/{threadId}`` removes a conversation: its run stops, and its session, its
  uploads, its trace and what the agent holds for it go from memory and disk (``forget``).
  Removing a project removes its conversations the same way;
- the tabs' endpoints (``/api/workbench``, ``/api/assumptions``, ``/api/designs``,
  ``/api/gemini/*``, ``/api/sensitivity*``, ``/api/trace``, ``/api/evidence``) are described in
  ``hackathon/docs/workbench_api.md``;
- ``GET /api/transcript?run=&case=`` returns one eval case's full transcript (read-only).
- ``GET /api/projects/{id}/memory`` lists what the user asked Dioscuri to remember in a project
  (``memory``: their name, how to answer), shared by its chats; ``DELETE`` with ``?id=``
  forgets one note, without it all of them.
- ``GET /api/lead`` returns the recommended design for the challenge district (``lead``: computed
  on the first request, kept on disk), or ``{"state": "computing"}``; ``POST /api/lead/open`` with
  ``{"threadId"}`` puts it into an empty conversation. The app no longer opens on it (5 Nov: a new
  chat starts empty); the report's scripts read it. ``GET /api/cost-basis?threadId=&design=``
  says what a design's cost includes and how far it moves (``cost_basis``).
- ``/`` serves ``frontend/dist`` when it has been built (ADR-0003: the bundle is committed,
  so judges need only Python and Ollama).

Sessions are kept in memory and saved as JSON after every turn (``DIOSCURI_SESSIONS``), so a
restarted server picks a conversation up where it stopped.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse as _JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gemini_agent import Agent, Session, cost_basis, engine, files, lead
from gemini_agent import memory as remembered
from gemini_agent import projects, workbench
from gemini_agent.agent import THREAD_ID
from gemini_agent.contract import ProjectData
from gemini_agent.docs import DocIndex
from gemini_agent.modelgen import Registry
from gemini_agent.router import Router
from gemini_agent.warmup import Warmup

ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get("DIOSCURI_FRONTEND", ROOT / "frontend" / "dist"))
RUNS = ROOT / "hackathon" / "evals" / "runs"
TRACES = Path(os.environ.get("DIOSCURI_TRACES", RUNS / "traces"))
SESSIONS = Path(os.environ.get("DIOSCURI_SESSIONS", RUNS / "sessions"))
# What an attachment may be: types the document reader or the file views understand.
ATTACH_TYPES = (".pdf", ".md", ".txt", ".rst", ".csv", ".tex", ".json", ".xlsx") + tuple(
    files.IMAGE_TYPES
)
ATTACH_MAX_MB = 20


def finite(value):
    """Return ``value`` with every NaN or infinite float replaced by None (JSON's null)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(v) for v in value]
    return value


class JSONResponse(_JSONResponse):
    """JSON whose NaN and infinite numbers are sent as null.

    On 3 Nov a single NaN in the design-space sweep made ``/api/sweep`` fail with a server error
    (JSON has no NaN); every response now goes through ``finite``.
    """

    def render(self, content) -> bytes:  # noqa: D102
        return super().render(finite(content))


class AssumptionsRequest(BaseModel):
    """Body of ``PUT /api/assumptions``."""

    threadId: str
    assumptions: Dict[str, object]


class DesignRequest(BaseModel):
    """Body of ``POST /api/designs``."""

    threadId: str
    base: str
    name: Optional[str] = None
    changes: Dict[str, object] = {}


class OpenRequest(BaseModel):
    """Body of ``POST /api/designs/open``."""

    threadId: str
    id: str


class MetaRequest(BaseModel):
    """Body of ``POST /api/designs/meta``: a design's own name, and whether it is starred."""

    threadId: str
    id: str
    name: Optional[str] = None  # "" clears it
    starred: Optional[bool] = None


class GeminiRunRequest(BaseModel):
    """Body of ``POST /api/gemini/run``."""

    project: Dict[str, object]
    compare_released: bool = False


class SensitivityRequest(BaseModel):
    """Body of ``POST /api/sensitivity``."""

    threadId: str
    design: str
    parameters: list
    outputs: list = ["lcoh"]
    samples: int = 0


class LeadOpenRequest(BaseModel):
    """Body of ``POST /api/lead/open``."""

    threadId: str


class RunRequest(BaseModel):
    """Body of ``POST /api/run``."""

    threadId: Optional[str] = None
    message: Optional[str] = None
    # The designs the user picked for this message (@ in the composer): the question is about them.
    designs: Optional[List[str]] = None
    answers: Optional[Dict[str, str]] = None
    reasoning: Optional[bool] = None  # None: the agent decides per message
    device: Optional[Literal["auto", "cpu"]] = None
    # The model: "auto" (the first that fits: 9B GPU, 4B GPU, 9B CPU, 4B CPU), "9b" or "4b".
    size: Optional[Literal["auto", "9b", "4b"]] = None
    projectId: Optional[str] = None  # a new conversation's project; None: the challenge


def create_app(
    agent: Optional[Agent] = None,
    router: Optional[Router] = None,
    warmup: Optional[Warmup] = None,
) -> FastAPI:
    """Return the app; pass an ``Agent`` to use a different model client (tests use a script).

    Parameters
    ----------
    agent : Agent, optional
        The agent to serve; by default one on the local Ollama models.
    router : Router, optional
        The model router (for the health check's devices); made with the default agent.
    warmup : Warmup, optional
        Loads the models and reports how far it got (``GET /api/models``); made with the
        default agent, else the agent's own. ``main`` starts it.

    Returns
    -------
    FastAPI
        The application.
    """
    if agent is None:
        device = os.environ.get("DIOSCURI_DEVICE", "auto")
        router = router or Router(device=device)
        warmup = warmup or Warmup(router, log=lambda line: print(line, flush=True))
        docs = DocIndex(device=device)
        docs.refresh()  # builds in the background; searches use keywords until it is ready
        agent = Agent(
            router.fast,
            trace_dir=str(TRACES),
            session_dir=str(SESSIONS),
            docs=docs,
            registry=Registry(),
            router=router,
            warmup=warmup,
            memory=remembered.Store(remembered.default_folder()),
        )
    router = router or agent.router
    warmup = warmup or getattr(agent, "warmup", None)
    sessions: Dict[str, Session] = {}
    # One run at a time: the agent keeps a run's state (its steps, calls, summary) on itself,
    # so two chats streaming at once would mix them. Runs queue; the tabs' reads do not wait.
    run_lock = threading.Lock()
    # The runs streaming or queued now, by thread: each has a flag that stops it at its next
    # event (a removed conversation). Threads removed while a run of theirs was still going are
    # cleared again when it stops, since it may have written its trace or session meanwhile.
    stops: Dict[str, List[threading.Event]] = {}
    removed: set = set()
    app = FastAPI(title="Dioscuri agent")
    # The recommended design for the challenge, computed on the first GET /api/lead (the app
    # no longer opens on it; ``DIOSCURI_LEAD_AT_START=1`` computes it at start as before).
    leader = lead.Lead(agent._record_search, spawn=True)
    app.state.lead = leader
    app.state.warmup = warmup

    @app.get("/api/health")
    def health() -> dict:
        """Report both models, their devices, whether they can answer and how to fix them."""
        ready, fix = agent.llm.available()
        deep = router.reasoning() if router else agent._deep()
        deep_ready, deep_fix = deep.available()
        devices = router.info() if router else {}
        writer = router.answerer() if router else agent.llm
        writer_ready, writer_fix = (deep_ready, deep_fix) if writer is deep else (ready, fix)
        return {
            "model": agent.llm.model,
            "device": devices.get("fast", {}).get("device", "cpu"),
            "ollama": fix != "ollama serve",
            "ready": ready,
            "fix": fix,
            "reasoning": {
                "model": deep.model,
                "device": devices.get("reasoning", {}).get("device", "cpu"),
                "ready": deep_ready,
                "fix": deep_fix,
            },
            "answer": {
                "model": writer.model,
                "device": devices.get("answer", {}).get("device", "cpu"),
                "ready": writer_ready,
                "fix": writer_fix,
            },
            "gpu": devices.get("gpu", ""),
            "default_device": router.device if router else "auto",
            "default_size": router.size if router else "auto",
            "profiles": router.profiles() if router else {},
            "attachments": {"types": list(ATTACH_TYPES), "max_mb": ATTACH_MAX_MB},
        }

    @app.get("/api/models")
    def models() -> dict:
        """Report how far loading the models has got (the app bar's chip polls it)."""
        if warmup is None:  # a scripted agent: nothing to load
            return {"ready": True, "state": "ready", "loaded": 0, "total": 0, "models": []}
        return warmup.status()

    def find(thread_id: str) -> Optional[Session]:
        """Return the session from memory, or from disk after a restart."""
        if thread_id not in sessions and agent.session_dir:
            saved = Session.load(agent.session_dir, thread_id)
            if saved is not None:
                sessions[thread_id] = saved
        return sessions.get(thread_id)

    def thread_paths(thread_id: str) -> List[Path]:
        """Return where the server keeps a conversation on disk, whether or not it is there.

        The session (and its unfinished write), the folder of its uploads and its trace: the
        same folders the endpoints write and read, each named by the exact thread id.
        """
        if not THREAD_ID.match(thread_id):  # a name on disk: plain ids only
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        kept = Path(agent.session_dir or SESSIONS)
        traces = Path(agent.trace_dir or TRACES)
        return [
            kept / f"{thread_id}.json",
            kept / f"{thread_id}.tmp",
            kept / thread_id,
            traces / f"{thread_id}.jsonl",
        ]

    def forget(thread_id: str) -> List[str]:
        """Remove a conversation from memory and disk; return the files that went.

        What the agent holds for it (its uploads' passages) goes only when no run of it is
        going: a run still uses it, and clears it when it stops.
        """
        sessions.pop(thread_id, None)
        if not stops.get(thread_id):
            agent.forget(thread_id)
        gone = []
        for path in thread_paths(thread_id):
            if path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                continue
            gone.append(path.name)
        return gone

    def project_threads(project_id: str) -> List[str]:
        """Return the conversations of a project the server knows, in memory or saved."""
        found = {t for t, s in list(sessions.items()) if s.project.id == project_id}
        if agent.session_dir and agent.session_dir.is_dir():
            for path in agent.session_dir.glob("*.json"):
                if path.stem in found or not THREAD_ID.match(path.stem):
                    continue
                try:
                    data = json.loads(path.read_text("utf-8"))
                except (OSError, ValueError):
                    continue
                if (data.get("project") or {}).get("id") == project_id:
                    found.add(path.stem)
        return sorted(found)

    def remove_thread(thread_id: str) -> dict:
        """Stop a conversation's runs and remove it (``DELETE /api/threads/{id}``)."""
        going = stops.get(thread_id) or []
        for stop in going:
            stop.set()
        if going:
            removed.add(thread_id)
        return {"threadId": thread_id, "stopped": len(going), "removed": forget(thread_id)}

    def project_data(project_id: Optional[str]) -> Optional[ProjectData]:
        """Return a project's data for a new conversation (None: the organisers' district)."""
        if not project_id:
            return None
        try:
            return projects.registry().data(project_id)
        except KeyError:
            raise HTTPException(404, f"no project {project_id!r} on this server")

    def in_project(session: Session, project: Optional[ProjectData]) -> Session:
        """Put a conversation that has not started in its project (a tab may have made it)."""
        if project is not None and session.project.id != project.id:
            try:
                session.use_project(project)
            except ValueError as err:
                raise HTTPException(409, str(err))
        return session

    @app.get("/api/projects")
    def list_projects() -> JSONResponse:
        """Return the projects: the organisers' district, then the ones users added."""
        reg = projects.registry()
        return JSONResponse({"projects": [reg.view(r.id) for r in reg.list()]})

    @app.post("/api/projects", status_code=201)
    async def create_project(
        name: str = Form(...),
        heat: UploadFile = File(...),
        cool: Optional[UploadFile] = File(None),
        depth_m: Optional[str] = Form(None),
        temperature_c: Optional[str] = Form(None),
        pressure_bar: Optional[str] = Form(None),
        permeability_md: Optional[str] = Form(None),
        thickness_m: Optional[str] = Form(None),
        heat_supply_c: Optional[str] = Form(None),
        heat_return_c: Optional[str] = Form(None),
        cool_supply_c: Optional[str] = Form(None),
        cool_return_c: Optional[str] = Form(None),
        heat_unit: Optional[str] = Form(None),
        cool_unit: Optional[str] = Form(None),
    ) -> JSONResponse:
        """Add a project from its demand files, its reservoir and its networks.

        ``heat_unit`` and ``cool_unit`` answer the unit question of a file whose header names
        none and whose values are too large for MW (``projects.UnitQuestion``).
        """
        limit = projects.MAX_UPLOAD_MB * 2**20 + 1
        heat_file = (heat.filename or "heating.csv", await heat.read(limit))
        cool_file = (cool.filename or "cooling.csv", await cool.read(limit)) if cool else None
        values = {
            "depth_m": depth_m,
            "temperature_c": temperature_c,
            "pressure_bar": pressure_bar,
            "permeability_md": permeability_md,
            "thickness_m": thickness_m,
            "heat_supply_c": heat_supply_c,
            "heat_return_c": heat_return_c,
            "cool_supply_c": cool_supply_c,
            "cool_return_c": cool_return_c,
        }
        reg = projects.registry()
        try:
            record = reg.create(
                name, heat_file, cool_file, values, {"heat": heat_unit, "cool": cool_unit}
            )
        except projects.ProjectError as err:
            raise HTTPException(422, str(err))
        return JSONResponse({"project": reg.view(record.id)}, status_code=201)

    @app.post("/api/projects/profile")
    async def project_profile(
        file: UploadFile = File(...), kind: str = Form("heat"), unit: Optional[str] = Form(None)
    ) -> dict:
        """Read a demand file the way a new project would, for the form's preview."""
        data = await file.read(projects.MAX_UPLOAD_MB * 2**20 + 1)
        try:
            return projects.preview(file.filename or "profile.csv", data, kind, unit)
        except projects.ProjectError as err:
            raise HTTPException(422, str(err))

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str) -> dict:
        """Remove a project the user added: its files, its conversations, what it remembered."""
        try:
            projects.registry().delete(project_id)
        except KeyError:
            raise HTTPException(404, f"no project {project_id!r} on this server")
        except projects.ProjectError as err:
            raise HTTPException(422, str(err))
        threads = [remove_thread(t)["threadId"] for t in project_threads(project_id)]
        agent.forget("project:" + project_id)  # its documents' passages (``agent.project_key``)
        if getattr(agent, "memory", None) is not None:
            agent.memory.forget(project_id)
        return {"ok": True, "threads": threads}

    @app.get("/api/projects/{project_id}/memory")
    def get_memory(project_id: str) -> dict:
        """Return what the user asked Dioscuri to remember in this project (every chat's)."""
        store = getattr(agent, "memory", None)
        notes = store.notes(project_id) if store is not None else []
        return {
            "projectId": project_id,
            "shared": store is not None,
            "notes": remembered.view(notes),
        }

    @app.delete("/api/projects/{project_id}/memory")
    def forget_memory(project_id: str, id: Optional[str] = None) -> dict:  # noqa: A002
        """Forget one note (``?id=``) or all of a project's; return what is left."""
        store = getattr(agent, "memory", None)
        if store is None:
            raise HTTPException(404, "this server keeps no project memory")
        gone = store.forget(project_id, id)
        if id is not None and not gone:
            raise HTTPException(404, f"no note {id!r} in project {project_id!r}")
        return {
            "projectId": project_id,
            "forgot": gone,
            "notes": remembered.view(store.notes(project_id)),
        }

    @app.post("/api/run")
    def run(req: RunRequest) -> StreamingResponse:
        """Stream one run of the agent as server-sent events."""
        if not req.message and req.answers is None:
            raise HTTPException(400, "send a message or answers")
        if req.threadId and not THREAD_ID.match(req.threadId):
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        if req.threadId in removed:
            raise HTTPException(409, "this conversation was removed")
        project = project_data(req.projectId)
        session = find(req.threadId) if req.threadId else None
        if session is None:
            session = Session(project=project, thread_id=req.threadId)
            sessions[session.thread_id] = session
        in_project(session, project)

        def stream():
            thread_id = session.thread_id
            stop = threading.Event()
            stops.setdefault(thread_id, []).append(stop)
            run_lock.acquire()
            events = None
            try:
                if stop.is_set():  # removed while it waited for its turn
                    return
                events = agent.run(
                    session,
                    req.message,
                    answers=req.answers,
                    reasoning=req.reasoning,
                    device=req.device,
                    designs=req.designs,
                    size=req.size,
                )
                for event in events:
                    if stop.is_set():
                        break
                    yield "data: " + json.dumps(
                        finite(event), ensure_ascii=False, default=str
                    ) + "\n\n"
            finally:
                try:
                    if events is not None:
                        events.close()
                    going = stops.get(thread_id) or []
                    if stop in going:
                        going.remove(stop)
                    if not going:
                        stops.pop(thread_id, None)
                        if thread_id in removed:  # what the run wrote after the removal goes too
                            removed.discard(thread_id)
                            forget(thread_id)
                finally:
                    run_lock.release()

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.post("/api/attachments")
    async def attach(
        threadId: str = Form(...),  # noqa: N803
        file: UploadFile = File(...),
        projectId: Optional[str] = Form(None),  # noqa: N803
    ) -> dict:
        """Save an uploaded file with the conversation and index it for its searches."""
        if not THREAD_ID.match(threadId):
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        project = project_data(projectId)
        name = Path(file.filename or "attachment").name
        if not re.fullmatch(r"[\w.() -]{1,120}", name):
            raise HTTPException(400, "file name: letters, digits, spaces and . _ - ( ) only")
        if Path(name).suffix.lower() not in ATTACH_TYPES:
            raise HTTPException(415, "file type: only " + ", ".join(ATTACH_TYPES) + " can be read")
        session = find(threadId)
        if session is None:
            session = Session(project=project, thread_id=threadId)
            sessions[threadId] = session
        in_project(session, project)
        folder = (agent.session_dir or SESSIONS) / threadId
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        data = await file.read(ATTACH_MAX_MB * 2**20 + 1)
        if len(data) > ATTACH_MAX_MB * 2**20:
            raise HTTPException(413, f"file too large: at most {ATTACH_MAX_MB} MB")
        path.write_bytes(data)
        try:
            chunks = agent.attach(session, path, name)
        except ImportError as err:
            raise HTTPException(415, f"can't read {name}: {err}")
        if agent.session_dir:
            session.save(agent.session_dir)
        return {"threadId": threadId, "name": name, "chunks": chunks}

    @app.get("/api/files", response_model=None)
    def file(
        threadId: str,  # noqa: N803
        name: str,
        view: bool = False,
        projectId: Optional[str] = None,  # noqa: N803
        inline: bool = False,
    ):
        """Return a project file or an upload: raw, as the chat's view, or to show.

        ``view=1``: the chat's view; ``inline=1``: for the browser to show (a PDF in a preview).
        """
        if not THREAD_ID.match(threadId):
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        session = find(threadId) or Session(project=project_data(projectId), thread_id=threadId)
        found = files.find(name, session.project, session.attachments)
        if found is None:
            raise HTTPException(404, f"{name} is not on the server")
        path, origin = found
        if view:
            url = files.url_for(threadId, Path(name).name)
            if projectId:  # a chat not started yet: the link must name its project too
                url += "&projectId=" + projectId
            try:
                shown = files.read(path, Path(name).name, origin, url)
            except Exception as err:  # noqa: BLE001 - an unreadable file is the user's to see
                raise HTTPException(422, f"can't read {name}: {type(err).__name__}: {err}")
            return JSONResponse(shown.as_dict())
        return FileResponse(
            path,
            media_type=files.media_type(path),
            filename=path.name,
            content_disposition_type="inline" if inline else "attachment",
        )

    @app.get("/api/doc-image")
    def doc_image(path: str) -> FileResponse:
        """Return a figure from GEMINI's documentation or the team's notes."""
        image = files.doc_image_path(ROOT, path)
        if image is None:
            raise HTTPException(404, "no such figure in the documentation")
        return FileResponse(image, media_type=files.media_type(image))

    def session_for(thread_id: str) -> Session:
        if not THREAD_ID.match(thread_id):
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        session = find(thread_id)
        if session is None:
            session = Session(thread_id=thread_id)
            sessions[thread_id] = session
        return session

    def saved(session: Session) -> None:
        if agent.session_dir:
            session.save(agent.session_dir)

    @app.get("/api/workbench")
    def get_workbench(threadId: str) -> JSONResponse:  # noqa: N803
        """Return the conversation's designs as the tabs show them."""
        return JSONResponse(workbench.workbench(session_for(threadId)))

    @app.get("/api/sweep")
    def get_sweep(threadId: str, search: Optional[str] = None) -> JSONResponse:  # noqa: N803
        """Return a search's design-space sweep (every design drawn) for the Compare map."""
        view = workbench.sweep_view(session_for(threadId), search)
        if view is None:
            raise HTTPException(404, "no design-space sweep in this conversation")
        return JSONResponse(view)

    @app.put("/api/assumptions")
    def put_assumptions(req: AssumptionsRequest) -> JSONResponse:
        """Change the conversation's cost assumptions; economics is recomputed."""
        session = session_for(req.threadId)
        try:
            workbench.put_assumptions(session, req.assumptions)
        except ValueError as err:
            raise HTTPException(422, str(err))
        saved(session)
        return JSONResponse(workbench.workbench(session))

    @app.post("/api/designs")
    def post_design(req: DesignRequest) -> JSONResponse:
        """Run a design edited on the tabs end to end and keep it with the conversation."""
        session = session_for(req.threadId)
        try:
            design = workbench.create_design(session, req.base, req.changes, req.name)
        except KeyError:
            raise HTTPException(404, f"no design {req.base!r} in this conversation")
        except ValueError as err:
            raise HTTPException(422, str(err))
        saved(session)
        return JSONResponse({"design": design})

    @app.post("/api/designs/open")
    def open_design(req: OpenRequest) -> JSONResponse:
        """Bring a design of any search into the tabs (Compare's library, a chat link)."""
        session = session_for(req.threadId)
        try:
            design = workbench.open_design(session, req.id)
        except KeyError:
            raise HTTPException(404, f"no design {req.id!r} in this conversation")
        saved(session)
        return JSONResponse({"design": design})

    @app.post("/api/designs/meta")
    def design_meta(req: MetaRequest) -> JSONResponse:
        """Give a design the user's own name, or star it (the shortlist); the workbench back."""
        session = session_for(req.threadId)
        try:
            workbench.set_meta(session, req.id, req.name, req.starred)
        except KeyError:
            raise HTTPException(404, f"no design {req.id!r} in this conversation")
        except ValueError as err:
            raise HTTPException(422, str(err))
        saved(session)
        return JSONResponse(workbench.workbench(session))

    @app.delete("/api/designs")
    def delete_design(threadId: str, id: str) -> dict:  # noqa: N803, A002
        """Remove a design made on the tabs."""
        session = session_for(threadId)
        try:
            workbench.delete_design(session, id)
        except KeyError:
            raise HTTPException(404, f"no design {id!r} in this conversation")
        except ValueError as err:
            raise HTTPException(422, str(err))
        saved(session)
        return {"ok": True}

    @app.get("/api/gemini/catalogue")
    def gemini_catalogue() -> JSONResponse:
        """Return the GEMINI component types a project can use."""
        return JSONResponse({"types": workbench.catalogue()})

    @app.post("/api/gemini/run")
    def gemini_run(req: GeminiRunRequest) -> JSONResponse:
        """Run a GEMINI project on the fixed GEMINI (and the release, when asked)."""
        return JSONResponse(workbench.run_gemini(req.project, req.compare_released))

    @app.get("/api/sensitivity/parameters")
    def sensitivity_parameters() -> JSONResponse:
        """Return the parameters a sensitivity run can vary and its outputs."""
        return JSONResponse(workbench.sensitivity_parameters())

    @app.post("/api/sensitivity")
    def post_sensitivity(req: SensitivityRequest) -> JSONResponse:
        """Vary the chosen parameters around a design."""
        session = session_for(req.threadId)
        try:
            out = workbench.sensitivity(
                session, req.design, req.parameters, req.outputs, req.samples
            )
        except KeyError:
            raise HTTPException(404, f"no design {req.design!r} in this conversation")
        except ValueError as err:
            raise HTTPException(422, str(err))
        return JSONResponse(out)

    @app.get("/api/risk")
    def get_risk(threadId: str, design: str, spare: int = 0) -> JSONResponse:  # noqa: N803
        """Return a design's backup sized by risk (one day short in ten years) beside N-1.

        ``spare``: 1 draws the years with a spare ESP on the shelf; 0 (as built) without one.
        """
        session = session_for(threadId)
        try:
            return JSONResponse(workbench.risk_view(session, design, bool(spare)))
        except KeyError:
            raise HTTPException(404, f"no design {design!r} in this conversation")
        except ValueError as err:
            raise HTTPException(422, str(err))

    @app.get("/api/outages")
    def get_outages(
        threadId: str, design: str, spare: int = 0, years: int = 1000  # noqa: N803
    ) -> JSONResponse:
        """Return a design's unplanned outages over 1,000 drawn years, and the worst case."""
        session = session_for(threadId)
        try:
            return JSONResponse(workbench.outages(session, design, bool(spare), years))
        except KeyError:
            raise HTTPException(404, f"no design {design!r} in this conversation")
        except ValueError as err:
            raise HTTPException(422, str(err))

    @app.get("/api/trace")
    def get_trace(threadId: str) -> JSONResponse:  # noqa: N803
        """Return the conversation's runs from its trace."""
        if not THREAD_ID.match(threadId):
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        folder = agent.trace_dir or TRACES
        return JSONResponse({"runs": workbench.trace(folder, threadId)})

    @app.get("/api/lead")
    def get_lead() -> JSONResponse:
        """Return the recommended design for the challenge, or that it is still computing."""
        return JSONResponse(leader.view())

    @app.post("/api/lead/open")
    def open_lead(req: LeadOpenRequest) -> JSONResponse:
        """Put the recommended design's search into an empty conversation (tabs and chat)."""
        if not THREAD_ID.match(req.threadId):
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        old = find(req.threadId)
        if old is not None and lead.has_lead(old):
            return JSONResponse({"threadId": req.threadId, "design": lead.design_of(old)})
        if old is not None and (old.turns or old.ledger or old.searches):
            raise HTTPException(409, "this conversation has started: open the design in a new one")
        if old is not None and old.project.id != projects.CHALLENGE:
            raise HTTPException(409, "the recommended design is the challenge district's")
        session = leader.session_for(req.threadId, keep=old)
        if session is None:
            raise HTTPException(409, "the recommended design is still being computed")
        sessions[req.threadId] = session
        saved(session)
        return JSONResponse({"threadId": req.threadId, "design": lead.design_of(session)})

    @app.get("/api/cost-basis")
    def get_cost_basis(threadId: str, design: str) -> JSONResponse:  # noqa: N803
        """Return what a design's cost includes and leaves out, and how far it moves."""
        session = session_for(threadId)
        try:
            entry = workbench.find(session, design)
        except KeyError:
            raise HTTPException(404, f"no design {design!r} in this conversation")
        a = workbench.price_changes(session.assumptions)
        priced = engine.reprice(entry, a) if a else entry
        return JSONResponse(cost_basis.basis(priced, a))

    @app.get("/api/evidence")
    def get_evidence() -> JSONResponse:
        """Return the test runs, the benchmarks and GEMINI's bug impact."""
        return JSONResponse(workbench.evidence(RUNS))

    @app.get("/api/transcript")
    def get_transcript(run: str, case: str) -> JSONResponse:
        """Return one eval case's full transcript (``workbench.transcript``), read-only."""
        try:
            data = workbench.transcript(RUNS, run, case)
        except ValueError as err:
            raise HTTPException(400, str(err))
        if data is None:
            raise HTTPException(404, f"no transcript of {case!r} in run {run!r}")
        return JSONResponse(data)

    @app.get("/api/report.pdf", response_model=None)
    def get_report(threadId: str, id: Optional[str] = None):  # noqa: N803, A002
        """Return the operator's report of a design (the chosen one by default) as a PDF."""
        from fastapi.responses import Response

        from gemini_agent import report_pdf

        session = session_for(threadId)
        try:
            entry = report_pdf.target(session, id)
            pdf = report_pdf.build(session, id)
        except KeyError:
            raise HTTPException(
                404, f"no design {id!r} in this conversation" if id else "no design chosen yet"
            )
        name = report_pdf.filename(entry)
        return Response(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/api/permits.pdf", response_model=None)
    def get_permit_pack(threadId: str, id: Optional[str] = None):  # noqa: N803, A002
        """Return a design's permit and subsidy pack as a PDF (``permit_pack``)."""
        from fastapi.responses import Response

        from gemini_agent import permit_pack, report_pdf

        session = session_for(threadId)
        try:
            entry = report_pdf.target(session, id)
            pdf = permit_pack.build(session, id)
        except KeyError:
            raise HTTPException(
                404, f"no design {id!r} in this conversation" if id else "no design chosen yet"
            )
        return Response(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{permit_pack.filename(entry)}"'
            },
        )

    @app.get("/api/gemini.json", response_model=None)
    def get_gemini_export(threadId: str, id: Optional[str] = None):  # noqa: N803, A002
        """Return a design's brine loop as a GEMINI project file (``gemini_export``)."""
        import json

        from fastapi.responses import Response

        from gemini_agent import gemini_export, report_pdf

        session = session_for(threadId)
        try:
            entry = report_pdf.target(session, id)
        except KeyError:
            raise HTTPException(
                404, f"no design {id!r} in this conversation" if id else "no design chosen yet"
            )
        proj = gemini_export.project(report_pdf._with_days(entry, session))
        if proj is None:
            raise HTTPException(422, "this design has no doublet, so nothing for GEMINI")
        return Response(
            json.dumps(finite(proj), indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{gemini_export.filename(entry)}"'
            },
        )

    @app.get("/api/threads/{thread_id}")
    def thread(thread_id: str) -> JSONResponse:
        """Return what one conversation knows: its brief, its open question and its ledger."""
        session = find(thread_id) if THREAD_ID.match(thread_id) else None
        if session is None:
            raise HTTPException(404, "unknown thread")
        return JSONResponse(
            {
                "threadId": thread_id,
                "project": session.project.model_dump(),
                "brief": session.brief.model_dump(),
                "pending": session.pending,
                "ledger": [
                    {
                        "alternative": e.alternative.code,
                        "lcoh": e.economics.lcoh_eur_per_mwh,
                        "verified": e.verification.passed,
                    }
                    for e in session.ledger
                ],
                "last": session.last,
                "turns": session.turns,
                "attachments": [a["name"] for a in session.attachments],
            }
        )

    @app.delete("/api/threads/{thread_id}")
    def delete_thread(thread_id: str) -> JSONResponse:
        """Remove a conversation: its run stops, and all the server keeps of it goes.

        Its session, its uploads, its trace and what the agent holds for it (its designs, cost
        assumptions and runs live in the session and the trace). An unknown thread has
        nothing to remove: the answer is the same, with nothing removed.
        """
        if not THREAD_ID.match(thread_id):
            raise HTTPException(400, "threadId: letters, digits, - and _ only (at most 64)")
        return JSONResponse(dict(remove_thread(thread_id), ok=True))

    if DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            """Serve the built front end (any unknown path gets index.html)."""
            target = DIST / path
            if path and target.is_file():
                return FileResponse(target)
            return FileResponse(DIST / "index.html")

    return app


def free_port(first: int, tries: int = 20) -> int:
    """Return ``first``, or the next port after it that nothing listens on."""
    import socket

    for port in range(first, first + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return first


def lead_at_start() -> bool:
    """Return whether the server computes the recommended design when it starts.

    Off by default since 5 Nov: a new chat starts empty, and nothing on screen reads it. Set
    ``DIOSCURI_LEAD_AT_START=1`` to have ``GET /api/lead`` ready at once.
    """
    return os.environ.get("DIOSCURI_LEAD_AT_START", "0") == "1"


def main() -> None:
    """Serve the app on http://127.0.0.1:8000, or the next free port after it.

    ``DIOSCURI_PORT`` sets the first port to try. ``DIOSCURI_OPEN=1`` (the start scripts) opens
    the app in the browser once it is up. A busy port is no longer an error for testers (Ali,
    3 Nov): the app takes the next free one and says where it is.
    """
    import uvicorn

    asked = int(os.environ.get("DIOSCURI_PORT", 8000))
    port = free_port(asked)
    url = f"http://127.0.0.1:{port}"
    app = create_app()
    if port != asked:
        print(f"Port {asked} is in use, so Dioscuri takes port {port}.", flush=True)
    print(f"Dioscuri is at {url} (keep this window open while you use it).", flush=True)
    if lead_at_start():
        app.state.lead.start()  # the recommended design, in the background
    if os.environ.get("DIOSCURI_WARMUP", "1") != "0" and app.state.warmup is not None:
        # The first message would wait 10-60 s on a laptop for its model to load: load them now.
        app.state.warmup.start()
    if os.environ.get("DIOSCURI_OPEN") == "1":
        import threading
        import webbrowser

        threading.Timer(2.0, webbrowser.open, [url]).start()
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
