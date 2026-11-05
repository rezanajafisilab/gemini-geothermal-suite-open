// The quick-ask box: "Ask about this" (and the menu's other questions) open a small box where the
// menu was, with the question started; Send switches to the chat and sends it. On the chat tab
// itself the question goes into the composer as before.

import type { OpenMenu } from "./store";

export interface QuickAsk {
  id: number;
  text: string;
  /** What it is about, in the box's head ("A1 · 1D-HP-EC-N1"). */
  about?: string;
  /** Where the menu was: the box opens there. */
  at: OpenMenu["at"] | null;
}

let state: QuickAsk | null = null;
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((fn) => fn());

export const quickAskStore = {
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  getSnapshot: () => state,
};

export function openQuickAsk(text: string, about?: string, at: OpenMenu["at"] | null = null): void {
  state = { id: ++seq, text, about, at };
  emit();
}

export function closeQuickAsk(): void {
  if (!state) return;
  state = null;
  emit();
}

/** The menu an item ran from: its head and place, for the box that item opens. */
let lastRun: { about?: string; at: OpenMenu["at"] | null } = { at: null };

export function noteMenuRun(about: string | undefined, at: OpenMenu["at"] | null): void {
  lastRun = { about, at };
}

export function lastMenuRun(): { about?: string; at: OpenMenu["at"] | null } {
  return lastRun;
}
