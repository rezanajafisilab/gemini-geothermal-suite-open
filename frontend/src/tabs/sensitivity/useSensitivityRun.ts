// Runs a sensitivity request and remembers each configuration's result for the visit, so picking a
// configuration run before shows its result at once. A change of configuration while a run is on
// its way cancels it; so does leaving the tab.

import { useCallback, useEffect, useRef, useState } from "react";

import { runSensitivity, type ApiError, type Sensitivity, type SensitivityRequest } from "../../workbench";

export interface RunEntry {
  key: string;
  data: Sensitivity;
  fixture: boolean;
  /** When it finished (ms since epoch). */
  at: number;
  /** The run's place among this visit's runs: 1, 2, 3 … */
  n: number;
}

const cache = new Map<string, RunEntry>();
/** The last result shown per conversation, kept while another configuration has none yet. */
const lastShown = new Map<string, RunEntry>();
let runCount = 0;

export interface SensitivityRun {
  /** The result of this configuration, else the last one shown (then `stale`). */
  result: RunEntry | null;
  stale: boolean;
  pending: boolean;
  /** When the pending run started (performance.now()). */
  startedAt: number | null;
  error: ApiError | null;
  run: () => void;
  cancel: () => void;
  /** Runs finished this visit. */
  runs: number;
}

export function useSensitivityRun(threadId: string, req: SensitivityRequest | null, key: string | null): SensitivityRun {
  const ctrl = useRef<{ c: AbortController; key: string } | null>(null);
  const [pending, setPending] = useState<{ key: string; at: number } | null>(null);
  const [error, setError] = useState<{ key: string; error: ApiError } | null>(null);
  const [, setTick] = useState(0);

  const cancel = useCallback(() => {
    ctrl.current?.c.abort();
    ctrl.current = null;
    setPending(null);
  }, []);

  // A new configuration cancels a run of another one.
  useEffect(() => {
    if (ctrl.current && ctrl.current.key !== key) cancel();
  }, [key, cancel]);
  useEffect(() => () => ctrl.current?.c.abort(), []);

  const run = useCallback(() => {
    if (!req || !key) return;
    ctrl.current?.c.abort();
    const c = new AbortController();
    ctrl.current = { c, key };
    setPending({ key, at: performance.now() });
    setError(null);
    void runSensitivity(req, c.signal).then((res) => {
      if (c.signal.aborted) return;
      ctrl.current = null;
      setPending(null);
      if (res.ok) {
        const entry: RunEntry = { key, data: res.data, fixture: res.fixture, at: Date.now(), n: ++runCount };
        cache.set(key, entry);
        lastShown.set(threadId, entry);
        setTick((t) => t + 1);
      } else {
        setError({ key, error: res });
      }
    });
  }, [req, key, threadId]);

  const own = key ? (cache.get(key) ?? null) : null;
  if (own && lastShown.get(threadId) !== own) lastShown.set(threadId, own);
  const result = own ?? lastShown.get(threadId) ?? null;
  return {
    result,
    stale: !own && !!result,
    pending: !!pending && pending.key === key,
    startedAt: pending?.at ?? null,
    error: error && error.key === key ? error.error : null,
    run,
    cancel,
    runs: runCount,
  };
}

/** Whether a configuration has a result already (no need to run it). */
export function hasResult(key: string | null): boolean {
  return !!key && cache.has(key);
}
