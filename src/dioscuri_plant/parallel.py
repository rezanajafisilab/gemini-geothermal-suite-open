"""Run independent plant years in worker processes: layouts, sweeps, one-unit-out checks.

A search runs thousands of years that do not depend on each other. Worker processes are forked
with the shared state (the demand, the doublet model, the rules), so only the items and the
results travel. ``DIOSCURI_WORKERS`` sets how many (default: one per CPU, at most 8); 1 runs
everything in the calling process. On any trouble (no fork on this system, a timeout) the work
runs in the calling process instead, with the same results.
"""

from __future__ import annotations

import os
from typing import Any, Callable, List, Sequence

_STATE: dict = {}


def _init(state: dict) -> None:
    _STATE.clear()
    _STATE.update(state)


def _call(job) -> Any:
    fn, item = job
    return fn(_STATE, item)


def workers() -> int:
    """Return how many processes to use (``DIOSCURI_WORKERS``, else one per CPU up to 8)."""
    raw = os.environ.get("DIOSCURI_WORKERS")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            return 1
    return min(8, os.cpu_count() or 1)


def pmap(
    fn: Callable[[dict, Any], Any],
    items: Sequence[Any],
    state: dict,
    min_items: int = 16,
    timeout: float = 300.0,
) -> List[Any]:
    """Return ``[fn(state, item) for item in items]``, in worker processes when worth it.

    ``fn`` must be a module-level function (it is sent by name). Results keep the items' order.
    """
    items = list(items)
    n = workers()
    if n > 1 and len(items) >= min_items:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor

        ex = None
        try:
            ctx = mp.get_context("fork")
            size = max(1, len(items) // (n * 4))
            ex = ProcessPoolExecutor(n, mp_context=ctx, initializer=_init, initargs=(state,))
            out = list(ex.map(_call, [(fn, x) for x in items], chunksize=size, timeout=timeout))
            ex.shutdown(wait=True)
            return out
        except Exception:  # noqa: BLE001 - the same work, run here
            # A worker that hangs (a lock held by another thread when it was forked) must not
            # hang the caller: the pool is dropped without waiting and its processes ended.
            if ex is not None:
                procs = list(getattr(ex, "_processes", {}).values())
                ex.shutdown(wait=False, cancel_futures=True)
                for p in procs:
                    if p.is_alive():
                        p.terminate()
    return [fn(state, x) for x in items]
