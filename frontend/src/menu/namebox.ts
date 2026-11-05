// The name box: "Give it a name" on a design's menu opens a one-line box where the menu was;
// Enter keeps the name (empty takes it away), Escape leaves it as it was.

import type { OpenMenu } from "./store";

export interface NameBox {
  id: number;
  /** The design's id ("A1 · 1D-HP-EC-N1") and handle ("A1"). */
  design: string;
  handle: string;
  current: string;
  at: OpenMenu["at"] | null;
}

let state: NameBox | null = null;
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((fn) => fn());

export const nameBoxStore = {
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  getSnapshot: () => state,
};

export function openNameBox(design: string, current: string | null, at: OpenMenu["at"] | null): void {
  state = { id: ++seq, design, handle: design.split(" · ")[0], current: current ?? "", at };
  emit();
}

export function closeNameBox(): void {
  if (!state) return;
  state = null;
  emit();
}
