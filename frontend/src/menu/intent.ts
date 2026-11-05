// What a menu asked another tab to show when it opens: the Energy tab on one series, the Economics
// tab with some cost lines picked out, the Sensitivity tab with a parameter added. A tab takes its
// intent once (useIntent), when it mounts or, already on screen, when the intent is set.

import { useEffect, useRef } from "react";

import type { Side } from "./types";

export interface Intents {
  energy: { side: Side; series: string | null };
  economics: { highlight: string[] };
  sensitivity: { param: string };
}

const pending: Partial<Intents> = {};
const listeners = new Set<() => void>();

export function setIntent<K extends keyof Intents>(key: K, value: Intents[K]): void {
  pending[key] = value;
  for (const fn of [...listeners]) fn();
}

/** The intent for a tab, taken (it is gone afterwards); null when there is none. */
export function takeIntent<K extends keyof Intents>(key: K): Intents[K] | null {
  const v = pending[key];
  delete pending[key];
  return (v as Intents[K] | undefined) ?? null;
}

/** Calls `fn` with the tab's intent: at mount if one is waiting, and whenever one is set later. */
export function useIntent<K extends keyof Intents>(key: K, fn: (value: Intents[K]) => void): void {
  const latest = useRef(fn);
  latest.current = fn;
  useEffect(() => {
    const check = () => {
      if (!(key in pending)) return;
      const v = takeIntent(key);
      if (v) latest.current(v);
    };
    check();
    listeners.add(check);
    return () => {
      listeners.delete(check);
    };
  }, [key]);
}
