"""Worked examples for the parameters reading: the nearest checked readings of other messages.

With ``DIOSCURI_EXAMPLES=1`` (off by default, to compare with and without), the reading's
prompt gets the three messages of a small index nearest the user's, each with the reading that
was checked for it (``Examples of readings``). The index (``data/reading_examples.npz``) holds
messages, their readings and their embeddings; ``hackathon/scripts/build_reading_examples.py``
builds it from the fine-tuning data, leaving out every message near an evaluation prompt
(``leaks``). The user's message is embedded by Ollama with the index's own model; without the
model, the server or the index, the reading has no examples and says nothing about it.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

INDEX = Path(__file__).resolve().parent / "data" / "reading_examples.npz"
FORMAT = 1
K = 3
POOL = 50  # the nearest by meaning, re-ranked by the kinds of amount they share
SAME_KIND = 0.05
RETRY_SECONDS = 60.0  # after a failed embedding, how long the reading goes without examples
EMBED_TIMEOUT = 10.0
# Room kept in the window for a second look's notes (``parameters.notes_block``).
NOTES_TOKENS = 400

# Tests set a stand-in: ``f(texts) -> vectors``. None: Ollama with the index's model.
EMBEDDER: Optional[Callable[[List[str]], List[List[float]]]] = None
_failed_at = -1e9
_lock = threading.Lock()


def enabled() -> bool:
    """Return True when ``DIOSCURI_EXAMPLES=1`` asks for worked examples in the reading."""
    return os.environ.get("DIOSCURI_EXAMPLES", "0").strip().lower() in ("1", "true", "yes", "on")


def block(examples: Sequence[Tuple[str, str]]) -> str:
    """Return the prompt's block of worked examples ("" without any)."""
    if not examples:
        return ""
    lines = ["Examples of readings (other messages, and what was read from each):"]
    for message, reading in examples:
        lines.append(f"Message: {message}\nReading: {reading}")
    return "\n".join(lines) + "\n\n"


def dimensions(message: str) -> List[str]:
    """Return the kinds of amount a message gives ("energy_price", "factor" ...), sorted."""
    from gemini_agent import quantities

    return sorted({q.dimension for q in quantities.extract(message) if q.clear})


class Index:
    """The examples: messages, their readings and unit-length embeddings (one row each).

    ``dims``: the kinds of amount each message gives (``dimensions``). Among the nearest by
    meaning, an example with the same kinds of amount as the message ranks higher (a price in
    ct/kWh, a share "a fifth more"): the form of the amounts is what the reading must get right.
    """

    def __init__(self, messages, readings, vectors, model: str, dims=None):
        """Keep the examples; ``vectors`` is an (n, d) float array, normalised here."""
        import numpy as np

        v = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(v, axis=1, keepdims=True)
        self.vectors = v / np.where(norms > 0, norms, 1.0)
        self.messages = list(messages)
        self.readings = list(readings)
        self.model = model
        self.dims = [set(d) for d in dims] if dims else [set(dimensions(m)) for m in messages]

    def nearest(
        self, vector: Sequence[float], k: int = K, dims: Iterable[str] = ()
    ) -> List[Tuple[str, str]]:
        """Return the ``k`` examples nearest a (query) embedding, nearest first.

        With ``dims`` (the message's kinds of amount), each kind an example shares adds
        ``SAME_KIND`` to its similarity, among the ``POOL`` nearest.
        """
        import numpy as np

        q = np.asarray(vector, dtype=np.float32)
        n = float(np.linalg.norm(q))
        if not n or q.shape[0] != self.vectors.shape[1]:
            return []
        scores = self.vectors @ (q / n)
        pool = np.argsort(-scores)[:POOL]
        wanted = set(dims)
        ranked = sorted(
            pool, key=lambda i: -(scores[i] + SAME_KIND * min(2, len(wanted & self.dims[i])))
        )
        return [(self.messages[i], self.readings[i]) for i in ranked[:k]]


def save(path: Path, messages, readings, vectors, model: str, source: str = "") -> None:
    """Write an index: int8 embeddings and the examples as JSON, compressed (about 1-2 MB)."""
    import numpy as np

    v = np.asarray(vectors, dtype=np.float32)
    v = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
    meta = {
        "format": FORMAT,
        "model": model,
        "source": source,
        "examples": [
            {"message": m, "reading": r, "dims": dimensions(m)} for m, r in zip(messages, readings)
        ],
    }
    raw = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        np.savez_compressed(
            f,
            vectors=np.round(v * 127).astype(np.int8),
            meta=np.frombuffer(raw, dtype=np.uint8),
        )


@lru_cache(maxsize=4)
def load(path: Path = INDEX) -> Optional[Index]:
    """Return the index at ``path``, or None when it is missing or unreadable."""
    try:
        import numpy as np

        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(bytes(data["meta"]).decode("utf-8"))
            vectors = data["vectors"].astype(np.float32) / 127.0
    except Exception:  # noqa: BLE001 - no index, no examples
        return None
    if meta.get("format") != FORMAT:
        return None
    ex = meta.get("examples") or []
    dims = [e.get("dims", []) for e in ex] if all("dims" in e for e in ex) else None
    return Index(
        [e["message"] for e in ex], [e["reading"] for e in ex], vectors, meta["model"], dims
    )


def query_prefix(model: str) -> str:
    """Return the embedding model's prefix for a query ("" when it has none).

    The user's message is the query (``docs.PREFIXES``); the examples are embedded without one.
    """
    from gemini_agent.docs import PREFIXES

    return next((q for name, (q, _) in PREFIXES.items() if model.startswith(name)), "")


@lru_cache(maxsize=2)
def _ollama(model: str) -> Callable[[List[str]], List[List[float]]]:
    from ollama import Client

    from gemini_agent.llm import DEFAULT_HOST

    client = Client(host=DEFAULT_HOST, timeout=EMBED_TIMEOUT)

    def embed(texts: List[str]) -> List[List[float]]:
        # The document search's options (``docs.DocIndex``): the same, so no reload between.
        return list(client.embed(model=model, input=texts, options={"num_ctx": 512}).embeddings)

    return embed


def nearest(
    message: str, k: int = K, index: Optional[Index] = None, embed=None
) -> List[Tuple[str, str]]:
    """Return the ``k`` worked examples nearest a message ([] when none can be found).

    Parameters
    ----------
    message : str
        The user's message.
    k : int
        How many examples.
    index : Index, optional
        The examples; the shipped index when omitted.
    embed : callable, optional
        ``embed(texts) -> vectors``; ``EMBEDDER``, else Ollama with the index's model.

    Returns
    -------
    list of (str, str)
        (message, reading JSON) pairs, nearest first.
    """
    global _failed_at
    index = index if index is not None else load(INDEX)
    if index is None or not message.strip():
        return []
    embed = embed or EMBEDDER
    prefix = ""
    if embed is None:
        if time.monotonic() - _failed_at < RETRY_SECONDS:
            return []
        embed, prefix = _ollama(index.model), query_prefix(index.model)
    try:
        vector = embed([prefix + message])[0]
    except Exception:  # noqa: BLE001 - the server or the model is missing: no examples
        with _lock:
            _failed_at = time.monotonic()
        return []
    return index.nearest(vector, k, dimensions(message))


def for_reading(message: str, build: Callable[[list], List[dict]], llm, k: int = K) -> list:
    """Return the examples for a reading, as many as fit its window ([] when switched off).

    ``build(examples)`` returns the reading's messages with those examples; examples are left
    out, farthest first, until the prompt fits with the answer and a second look's notes.
    """
    if not enabled():
        return []
    from gemini_agent.llm import prompt_tokens, room
    from gemini_agent.parameters import READING_TOKENS

    examples = nearest(message, k)
    limit = room(llm, READING_TOKENS) - NOTES_TOKENS
    while examples and prompt_tokens(build(examples)) > limit:
        examples = examples[:-1]
    return examples


# ------------------------------------------------------------------ evaluation prompts left out

PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def normalise(text: str) -> str:
    """Return a message in lower case, its placeholders and punctuation out, spaces single."""
    text = PLACEHOLDER.sub(" ", text or "").lower().replace("’", "'")
    return " ".join(re.findall(r"[a-zà-ÿ0-9]+(?:[.,][0-9]+)?", text))


def near_duplicate(a: str, b: str, overlap: float = 0.7, ratio: float = 0.9) -> bool:
    """Return True when two messages are near-identical.

    That is the same normalised text, a token overlap (Jaccard) of at least ``overlap``, or a
    character similarity of at least ``ratio``.
    """
    import difflib

    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if len(ta & tb) / len(ta | tb) >= overlap:
        return True
    matcher = difflib.SequenceMatcher(None, na, nb, autojunk=False)
    return matcher.real_quick_ratio() >= ratio and matcher.ratio() >= ratio


def eval_prompts(paths: Iterable[Path]) -> List[str]:
    """Return every user prompt of evaluation suites (``prompt``, ``wordings`` and ``say``)."""
    import yaml

    found: List[str] = []

    def walk(x, key=None):
        if isinstance(x, dict):
            for k2, v in x.items():
                walk(v, k2)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
        elif isinstance(x, str) and key in ("prompt", "wordings", "say"):
            found.append(x)

    for path in paths:
        with open(path, encoding="utf-8") as f:
            walk(yaml.safe_load(f))
    return found


def leaks(message: str, prompts: Sequence[str]) -> bool:
    """Return True when a message is near-identical to any evaluation prompt."""
    return any(near_duplicate(message, p) for p in prompts)
