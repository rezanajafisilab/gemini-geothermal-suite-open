// One request's state for a tab, e.g. the trace or the evidence:
//   const trace = useResource((signal) => getTrace(threadId, signal), [threadId]);
// It refetches when the deps change, drops the answers of superseded requests, and `reload`
// asks again (keeping the data on screen meanwhile).

import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";

import type { ApiError, ApiResult } from "./api";

export interface Resource<T> {
  status: "loading" | "ready" | "error";
  data: T | null;
  error: ApiError | null;
  /** The data came from the fixture files. */
  fixture: boolean;
  /** A reload is on its way (the data on screen stays meanwhile). */
  refreshing: boolean;
  reload: () => void;
}

export function useResource<T>(fetcher: (signal: AbortSignal) => Promise<ApiResult<T>>, deps: DependencyList): Resource<T> {
  const [state, setState] = useState<Omit<Resource<T>, "reload">>({ status: "loading", data: null, error: null, fixture: false, refreshing: false });
  const [tick, setTick] = useState(0);
  const latest = useRef(fetcher);
  latest.current = fetcher;

  useEffect(() => {
    const ctrl = new AbortController();
    setState((s) => (s.data ? { ...s, refreshing: true } : { ...s, status: "loading", error: null }));
    void latest.current(ctrl.signal).then((res) => {
      if (ctrl.signal.aborted) return;
      setState((s) =>
        res.ok
          ? { status: "ready", data: res.data, error: null, fixture: res.fixture, refreshing: false }
          : { ...s, status: s.data ? "ready" : "error", error: res, refreshing: false },
      );
    });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the caller's deps decide when to refetch
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}
