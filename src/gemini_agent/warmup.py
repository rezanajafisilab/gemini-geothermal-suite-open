"""Load the local models before the first message needs them, and say how far it got.

A model that is not in memory yet is loaded by its first call: 10-60 s on a laptop (CPU only, or
a 16 GB GPU), during which the chat said nothing. At start the server loads the models this
machine will use, in the order a message calls them (the reading model first, then the
reasoning model when it is another one), in a background thread and with Ollama's keep-alive
(``OllamaLLM.warm``). ``GET /api/models`` reports each model's state (``waiting``, ``loading``,
``ready``, ``failed``) for the app bar's chip, and a run that finds its model out of memory
(still loading, or unloaded by Ollama since) loads it first, as a row of its own.

The models come from the router's public clients (``reader``, ``answerer``, ``reasoning``) for a
device, one per model and context window: a different ``num_ctx`` makes Ollama reload a model,
so two clients that differ only in their window are two loads. Whether a model is in memory is
read from Ollama's ``/api/ps`` (2 s timeout): its name, its window (``context_length``) and, for
a client kept off the GPU, that none of it is on the GPU.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from gemini_agent.llm import DEFAULT_HOST

PS_TIMEOUT = 2.0  # seconds for /api/ps and /api/tags: cheap reads, asked about once a second
RETRY_SECONDS = 10.0  # a failed warm-up is tried again this long after (Ollama started later)
# The router's clients a message uses, in the order it calls them (the reader reads it first).
ROLES = ("reader", "answerer", "reasoning")
STATES = ("waiting", "loading", "ready", "failed")


def tag_of(model: str) -> str:
    """Return a model's full tag as Ollama lists it (``name`` becomes ``name:latest``)."""
    return model if ":" in model else model + ":latest"


def base_url(host: Optional[str] = None) -> str:
    """Return the Ollama server's URL with its scheme."""
    url = (host or DEFAULT_HOST).rstrip("/")
    return url if url.startswith("http") else f"http://{url}"


def _get(host: Optional[str], path: str, timeout: float) -> Optional[dict]:
    import httpx

    try:
        r = httpx.get(f"{base_url(host)}{path}", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except (httpx.HTTPError, ValueError):
        return None


def loaded_models(host: Optional[str] = None, timeout: float = PS_TIMEOUT) -> Optional[dict]:
    """Return the models Ollama holds in memory now, by tag (``/api/ps``).

    Returns
    -------
    dict or None
        Each loaded model's ``/api/ps`` record (``size``, ``size_vram``, ``context_length``) by
        tag; None when Ollama does not answer.
    """
    data = _get(host, "/api/ps", timeout)
    if data is None:
        return None
    out = {}
    for m in data.get("models") or []:
        if isinstance(m, dict):
            for name in {m.get("name"), m.get("model")} - {None, ""}:
                out[tag_of(str(name))] = m
    return out


def pulled_sizes(host: Optional[str] = None, timeout: float = PS_TIMEOUT) -> Optional[dict]:
    """Return the bytes on disk of each pulled model, by tag (``/api/tags``); None when down."""
    data = _get(host, "/api/tags", timeout)
    if data is None:
        return None
    out = {}
    for m in data.get("models") or []:
        if isinstance(m, dict):
            for name in {m.get("name"), m.get("model")} - {None, ""}:
                out[tag_of(str(name))] = int(m.get("size") or 0)
    return out


def failure(model: str, error: str) -> Tuple[str, str, str]:
    """Return why a model could not be loaded: a reason, a short message and what to do.

    Parameters
    ----------
    model : str
        The model's tag.
    error : str
        The failed call's error text.

    Returns
    -------
    tuple of (str, str, str)
        ``reason`` (``not_running``, ``not_pulled``, ``timeout``, ``memory`` or ``error``),
        the message for the chip and the hint (short: the chip shows both; Ollama is retried
        every ``RETRY_SECONDS``, so starting it is enough).
    """
    text = error.lower()
    if "not found" in text:
        return "not_pulled", f"{model} is not downloaded", f"Run: ollama pull {model}"
    if "connect" in text or "refused" in text or "connection" in text:
        return "not_running", "Ollama is not running", "Start it with: ollama serve"
    if "timed out" in text or "timeout" in text:
        return "timeout", f"{model} took too long to load", "Send a message to try again"
    if "memory" in text:
        return "memory", f"Not enough memory for {model}", "Close other programs, or pick CPU"
    return "error", f"{model} could not be loaded", error[:120]


def size_text(size_bytes: int) -> str:
    """Return a model's size as people read it (``6.6 GB``, ``850 MB``), or ``""``."""
    if size_bytes <= 0:
        return ""
    gb = size_bytes / 1e9
    return f"{gb:.1f} GB" if gb >= 1 else f"{size_bytes / 1e6:.0f} MB"


@dataclass(eq=False)
class ModelLoad:
    """One model (and context window) to load: what it is for, where it goes, how far it got."""

    model: str
    num_ctx: int
    device: str  # "gpu" or "cpu": where the router runs it
    cpu_only: bool  # the client keeps every layer off the GPU (num_gpu=0)
    client: Any = field(repr=False)
    roles: List[str] = field(default_factory=list)
    state: str = "waiting"
    size_bytes: int = 0  # on disk (/api/tags): about what it takes in memory
    memory_bytes: int = 0  # in memory (/api/ps), once loaded
    started: Optional[float] = None
    finished: Optional[float] = None
    message: str = ""
    hint: str = ""
    reason: str = ""
    # What /api/ps said once we had loaded it (Ollama may set the window or the GPU share itself).
    seen_ctx: int = 0
    seen_vram: int = 0
    logged: str = ""  # the last failure said in the terminal (a retry does not repeat it)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def where(self) -> str:
        """Return where the model is loaded, in words (``GPU memory`` or ``RAM``)."""
        return "GPU memory" if self.device == "gpu" else "RAM"

    def label(self) -> str:
        """Return the working view's row: ``Load qwen3.5:9b into GPU memory (6.6 GB, ...)``.

        A model that was loaded and is not any more (Ollama unloaded it for another) is loaded
        "again", not "first time only".
        """
        size = size_text(self.size_bytes)
        if self.state == "ready":
            return f"Load {self.model} into {self.where} again" + (f" ({size})" if size else "")
        note = f"{size}, first time only" if size else "first time only"
        return f"Load {self.model} into {self.where} ({note})"

    def seconds(self, now: float) -> Optional[float]:
        """Return the seconds the load has taken so far, or took; None before it starts."""
        if self.started is None:
            return None
        return round((self.finished if self.finished is not None else now) - self.started, 1)

    def in_memory(self, ps: dict) -> bool:
        """Return True when ``/api/ps`` shows this model loaded as this client would call it."""
        info = ps.get(tag_of(self.model))
        if info is None:
            return False
        ctx = int(info.get("context_length") or 0)
        if ctx and self.num_ctx and ctx not in (self.num_ctx, self.seen_ctx):
            return False  # loaded with another window: the call would reload it
        vram = int(info.get("size_vram") or 0)
        if self.cpu_only and vram > 0:
            return False  # loaded on the GPU: a CPU-only call reloads it
        if not self.cpu_only and self.seen_vram > 0 and vram == 0:
            return False  # we had it on the GPU; it was reloaded on the CPU since
        return True

    def as_dict(self, now: float) -> dict:
        """Return the record ``GET /api/models`` sends for this model."""
        return {
            "model": self.model,
            "roles": list(self.roles),
            "device": self.device,
            "num_ctx": self.num_ctx,
            "state": self.state,
            "size_gb": round(self.size_bytes / 1e9, 2) if self.size_bytes else None,
            "memory_gb": round(self.memory_bytes / 1e9, 2) if self.memory_bytes else None,
            "seconds": self.seconds(now),
            "message": self.message,
            "hint": self.hint,
            "label": self.label(),
        }


class Warmup:
    """Loads the models a message will need, in the background, and reports their state.

    Parameters
    ----------
    router : Router
        Hands out the model clients (``reader``, ``answerer``, ``reasoning``, ``device_of``).
    host : str, optional
        Ollama server URL (``/api/ps``, ``/api/tags``); the router's, else ``$OLLAMA_HOST``.
    log : callable, optional
        Called with a line for the terminal when a model is loaded or fails.
    clock : callable
        Seconds, for the timings (tests pass their own).
    """

    def __init__(
        self,
        router,
        host: Optional[str] = None,
        log: Optional[Callable[[str], None]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Keep the router; nothing is loaded until ``start`` or a run asks."""
        self.router = router
        self.host = host or getattr(router, "_host", None) or DEFAULT_HOST
        self._log = log
        self._clock = clock
        self._lock = threading.Lock()
        self._loads: Dict[Tuple[str, int, bool], ModelLoad] = {}
        self._sizes: Optional[dict] = None
        self._thread: Optional[threading.Thread] = None
        self._started: Optional[float] = None
        self._last_try = 0.0

    # ------------------------------------------------------------ the models

    def _clients(self, device: Optional[str]) -> List[Tuple[str, Any]]:
        out = []
        for role in ROLES:
            pick = getattr(self.router, role, None)
            if not callable(pick):
                continue
            try:
                client = pick(device)
            except Exception:  # noqa: BLE001 - a role the router cannot fill is left out
                continue
            if callable(getattr(client, "warm", None)):  # an Ollama client, not a script
                out.append((role, client))
        return out

    def needed(self, device: Optional[str] = None) -> List[ModelLoad]:
        """Return the models a message on ``device`` uses, in the order it calls them.

        One record per model and context window (and CPU-only or not): two roles that share
        a client, or a model with the same window, are one load.
        """
        out: List[ModelLoad] = []
        for role, client in self._clients(device):
            options = getattr(client, "options", None) or {}
            cpu_only = getattr(client, "device", "auto") == "cpu"
            key = (client.model, int(options.get("num_ctx") or 0), cpu_only)
            with self._lock:
                load = self._loads.get(key)
                if load is None:
                    where = self._device_of(client, device)
                    load = ModelLoad(client.model, key[1], where, cpu_only, client)
                    load.size_bytes = (self._sizes or {}).get(tag_of(client.model), 0)
                    self._loads[key] = load
            if role not in load.roles:
                load.roles.append(role)
            if load not in out:
                out.append(load)
        return out

    def _device_of(self, client, device: Optional[str]) -> str:
        try:
            return self.router.device_of(client, device)
        except Exception:  # noqa: BLE001 - an older router: the client's own setting
            return "cpu" if getattr(client, "device", "auto") == "cpu" else "gpu"

    def _sizes_now(self) -> None:
        sizes = pulled_sizes(self.host)
        if sizes is None:
            return
        self._sizes = sizes
        with self._lock:
            loads = list(self._loads.values())
        for load in loads:
            load.size_bytes = sizes.get(tag_of(load.model), load.size_bytes)

    # --------------------------------------------------------------- loading

    def start(self) -> None:
        """Load the default device's models in a background thread; never raises or blocks."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._started = self._last_try = self._clock()
            self._thread = threading.Thread(target=self._warm_all, name="dioscuri-warmup")
            self._thread.daemon = True
            self._thread.start()

    def _warm_all(self) -> None:
        try:
            loads = self.needed()
            ps = loaded_models(self.host)
            if ps is None:  # a failure stays one until Ollama answers (no flash of "loading")
                for load in loads:
                    if load.state != "ready":
                        self._fail(load, "ConnectionError: Ollama does not answer")
                return
            self._sizes_now()
            for load in loads:
                if load.state == "failed":
                    load.state, load.message, load.hint, load.reason = "waiting", "", "", ""
            for load in loads:
                if load.state == "ready":
                    continue
                if load.in_memory(ps):
                    self._mark_loaded(load, ps, already=True)
                    continue
                self.ensure(load)
        except Exception as err:  # noqa: BLE001 - the warm-up must never stop the server
            if self._log:
                self._log(f"Model warm-up stopped: {type(err).__name__}: {err}")

    def missing(self, device: Optional[str] = None) -> List[ModelLoad]:
        """Return the models a run on ``device`` needs that are not in memory now.

        A model the warm-up is loading counts as missing (the run waits for it). When Ollama
        does not answer nothing is reported: the run's own call says what is wrong.
        """
        loads = self.needed(device)
        ps = loaded_models(self.host)
        if ps is None:
            return []
        if self._sizes is None:
            self._sizes_now()
        out = []
        for load in loads:
            if load.state != "loading" and load.in_memory(ps):
                if load.state != "ready":
                    self._mark_loaded(load, ps, already=True)
                continue
            out.append(load)
        return out

    def ensure(self, load: ModelLoad) -> bool:
        """Load one model now, or wait while another thread loads it; True when it is loaded.

        Parameters
        ----------
        load : ModelLoad
            A record from ``needed`` or ``missing``.

        Returns
        -------
        bool
            True when the model is in memory; False when the load failed (``load.message``
            and ``load.hint`` say why).
        """
        asked = self._clock()
        with load.lock:  # one load of a model at a time; a second caller waits for the first
            if load.state == "ready":
                if load.finished is not None and load.finished >= asked:
                    return True  # loaded while this caller waited
                if load.in_memory(loaded_models(self.host) or {}):
                    return True  # loaded just before this caller asked
            load.state, load.started, load.finished = "loading", self._clock(), None
            load.message, load.hint, load.reason = f"Loading into {load.where}", "", ""
            if self._sizes is not None and tag_of(load.model) not in self._sizes:
                self._sizes_now()  # pulled since the list was read?
                if self._sizes is not None and tag_of(load.model) not in self._sizes:
                    self._fail(load, f"model '{load.model}' not found")
                    return False
            try:
                load.client.warm()
            except Exception as err:  # noqa: BLE001 - Ollama down, model missing, timeout
                self._fail(load, str(err))
                return False
            ps = loaded_models(self.host) or {}
            self._mark_loaded(load, ps, already=False)
            return True

    def _mark_loaded(self, load: ModelLoad, ps: dict, already: bool) -> None:
        info = ps.get(tag_of(load.model)) or {}
        load.seen_ctx = int(info.get("context_length") or load.seen_ctx or 0)
        load.seen_vram = int(info.get("size_vram") or 0)
        load.memory_bytes = int(info.get("size") or 0)
        now = self._clock()
        if already and load.started is None:
            load.started = now
        load.finished = now
        load.state = "ready"
        load.hint, load.reason = "", ""
        took = load.seconds(now) or 0.0
        load.message = "Already in memory" if already else f"Loaded in {took:.1f} s"
        load.logged = ""
        if self._log and not already:
            self._log(f"Loaded {load.model} into {load.where} in {took:.1f} s.")

    def _fail(self, load: ModelLoad, error: str) -> None:
        load.reason, load.message, load.hint = failure(load.model, error)
        load.state = "failed"
        load.finished = self._clock()
        if load.started is None:
            load.started = load.finished
        line = f"Could not load {load.model}: {load.message}. {load.hint}"
        if self._log and line != load.logged:
            self._log(line)
        load.logged = line

    # ---------------------------------------------------------------- status

    def status(self) -> dict:
        """Return what ``GET /api/models`` sends: each model's state and the overall one.

        Returns
        -------
        dict
            ``ready`` (bool), ``state`` (``idle`` before a warm-up was asked for, ``loading``,
            ``ready`` or ``failed``), ``loaded`` of ``total``, ``seconds`` since the warm-up
            started, the first failure's ``message`` and ``hint``, the default ``device``, and
            ``models``: each model's roles, name, device, size, state, seconds and message.
        """
        loads = self.needed()
        if any(load.state == "waiting" for load in loads):
            ps = loaded_models(self.host)
            for load in loads:
                if ps and load.state == "waiting" and load.in_memory(ps):
                    self._mark_loaded(load, ps, already=True)
        now = self._clock()
        failed = [load for load in loads if load.state == "failed"]
        ready = [load for load in loads if load.state == "ready"]
        if failed:
            state = "failed"
        elif len(ready) == len(loads):
            state = "ready"
        elif self._started is not None:
            state = "loading"
        else:
            state = "idle"
        idle = self._thread is None or not self._thread.is_alive()
        if state == "failed" and idle and now - self._last_try >= RETRY_SECONDS:
            self.start()  # Ollama may be running now, or the model pulled: try again
        first = next(
            (f for f in failed if f.reason == "not_running"), failed[0] if failed else None
        )
        ends = [load.finished for load in loads if load.finished is not None]
        until = max(ends) if state == "ready" and ends else now
        return {
            "ready": state == "ready",
            "state": state,
            "loaded": len(ready),
            "total": len(loads),
            "seconds": round(until - self._started, 1) if self._started is not None else None,
            "message": first.message if first else "",
            "hint": first.hint if first else "",
            "device": getattr(self.router, "device", "auto"),
            "models": [load.as_dict(now) for load in loads],
        }
