"""A stand-in Ollama server for tests: ``/api/ps``, ``/api/tags`` and ``/api/chat`` on a port.

It answers over real HTTP, so the Ollama client and the warm-up run as they do against Ollama,
without loading a model. A chat call to a model that is not loaded as asked (another window,
or on the GPU for a CPU-only call) loads it first: after ``load_seconds``, and only once the
gate is open (``hold`` closes it, so a test can see a model "loading"; ``release`` opens it).
A structured call gets the smallest object its JSON schema allows.

Run it alone (``python -m unit_test.gemini_agent.fake_ollama --port 11500 --load-seconds 30``)
to try the app's loading states without Ollama.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional, Union

# Bytes on disk, as Ollama 0.40 lists them (3 Nov).
PULLED = {
    "qwen3:1.7b": 1_359_293_444,
    "qwen3.5:4b": 3_324_173_934,
    "qwen3.5:9b": 6_550_825_550,
}


def tag_of(model: str) -> str:
    """Return a model's full tag (``name`` becomes ``name:latest``)."""
    return model if ":" in model else model + ":latest"


def minimal(schema) -> object:
    """Return the smallest value a JSON schema allows (first enum value, zero, empty)."""
    if not isinstance(schema, dict):
        return None
    for key in ("anyOf", "oneOf", "allOf"):
        if schema.get(key):
            return minimal(schema[key][0])
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "null")
    if kind == "object":
        props = schema.get("properties") or {}
        return {k: minimal(v) for k, v in props.items()}
    return {"string": "", "number": 0, "integer": 0, "boolean": False, "array": []}.get(kind)


class FakeOllama:
    """A fake Ollama server on ``127.0.0.1`` (a free port unless one is given).

    Parameters
    ----------
    pulled : dict, optional
        Bytes on disk by tag: the models it has (``PULLED`` by default).
    load_seconds : float
        How long loading a model takes.
    reply : str or callable, optional
        A text call's answer, or ``f(body) -> str``; structured calls get ``minimal(schema)``.
    port : int
        0 picks a free port.
    """

    def __init__(
        self,
        pulled: Optional[Dict[str, int]] = None,
        load_seconds: float = 0.0,
        reply: Union[str, Callable[[dict], str]] = "ok",
        port: int = 0,
    ):
        """Bind the port; ``start`` serves it."""
        self.pulled = dict(PULLED if pulled is None else pulled)
        self.loaded: Dict[str, dict] = {}
        self.load_seconds = load_seconds
        self.reply = reply
        self.chats: list = []
        self.gate = threading.Event()
        self.gate.set()
        self._lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self._thread: Optional[threading.Thread] = None

    # ----------------------------------------------------------- the state

    def put(self, model: str, num_ctx: int, gpu: bool = True) -> None:
        """Mark a model loaded with this window, on the GPU or not."""
        size = self.pulled.get(tag_of(model), 1_000_000_000)
        record = {
            "name": tag_of(model),
            "model": tag_of(model),
            "size": size,
            "size_vram": size if gpu else 0,
            "context_length": num_ctx,
            "expires_at": "2319-02-14T10:00:00Z",
        }
        with self._lock:
            self.loaded[tag_of(model)] = record

    def evict(self, model: str) -> None:
        """Unload a model, as Ollama does when it needs the memory."""
        with self._lock:
            self.loaded.pop(tag_of(model), None)

    def hold(self) -> None:
        """Make loads wait until ``release``."""
        self.gate.clear()

    def release(self) -> None:
        """Let waiting loads finish."""
        self.gate.set()

    def _loaded_as(self, model: str, num_ctx: int, cpu: bool) -> bool:
        with self._lock:
            info = self.loaded.get(tag_of(model))
        if info is None or info["context_length"] != num_ctx:
            return False
        return not (cpu and info["size_vram"] > 0)

    # ------------------------------------------------------------- serving

    def start(self) -> "FakeOllama":
        """Serve in a background thread; return self."""
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop serving and free the port."""
        self.release()
        self.server.shutdown()
        self.server.server_close()

    def __enter__(self) -> "FakeOllama":
        """Start on entering a ``with`` block."""
        return self.start()

    def __exit__(self, *exc) -> None:
        """Stop on leaving it."""
        self.stop()

    def _chat(self, body: dict) -> tuple:
        model = str(body.get("model", ""))
        options = body.get("options") or {}
        self.chats.append(body)
        if tag_of(model) not in self.pulled:
            return 404, {"error": f"model '{model}' not found"}
        num_ctx = int(options.get("num_ctx") or 4096)
        cpu = options.get("num_gpu") == 0
        load_ns = 0
        if not self._loaded_as(model, num_ctx, cpu):
            start = time.perf_counter()
            self.gate.wait(timeout=60)
            time.sleep(self.load_seconds)
            self.put(model, num_ctx, gpu=not cpu)
            load_ns = int((time.perf_counter() - start) * 1e9)
        fmt = body.get("format")
        if isinstance(fmt, dict):
            content = json.dumps(minimal(fmt))
        elif fmt == "json":
            content = "{}"
        else:
            content = self.reply(body) if callable(self.reply) else self.reply
        return 200, {
            "model": model,
            "created_at": "2026-11-04T12:00:00Z",
            "message": {"role": "assistant", "content": content},
            "done": True,
            "done_reason": "stop",
            "total_duration": load_ns + 2_000_000,
            "load_duration": load_ns,
            "prompt_eval_count": 8,
            "prompt_eval_duration": 1_000_000,
            "eval_count": 1,
            "eval_duration": 1_000_000,
        }

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # noqa: D102 - quiet
                pass

            def _send(self, status: int, data: dict) -> None:
                raw = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802, D102
                if self.path == "/api/ps":
                    with fake._lock:
                        models = list(fake.loaded.values())
                    self._send(200, {"models": models})
                elif self.path == "/api/tags":
                    tags = [{"name": t, "model": t, "size": s} for t, s in fake.pulled.items()]
                    self._send(200, {"models": tags})
                elif self.path == "/api/version":
                    self._send(200, {"version": "0.40.12"})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802, D102
                size = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(size) or b"{}")
                except ValueError:
                    return self._send(400, {"error": "bad JSON"})
                if self.path == "/api/chat":
                    return self._send(*fake._chat(body))
                if self.path in ("/api/embed", "/api/embeddings"):
                    return self._send(404, {"error": "model not found"})
                return self._send(404, {"error": "not found"})

        return Handler


def main() -> None:
    """Serve the fake on a port until stopped (for trying the app's loading states)."""
    import argparse

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=11500)
    p.add_argument("--load-seconds", type=float, default=30.0)
    args = p.parse_args()
    fake = FakeOllama(load_seconds=args.load_seconds, port=args.port, reply="Hello.").start()
    print(f"Fake Ollama at {fake.url} (loads take {args.load_seconds:.0f} s)", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        fake.stop()


if __name__ == "__main__":
    main()
