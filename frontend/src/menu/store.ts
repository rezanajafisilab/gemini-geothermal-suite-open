// The menu on screen (one at a time) and the short toast an item leaves ("Link copied"). A small
// store read with useSyncExternalStore, like the app's others; menuProps and MenuButton open a
// menu, the host (ContextMenu.tsx) draws it.

import type { Box } from "./keys";
import type { MenuTarget } from "./types";

export interface OpenMenu {
  /** Changes with every opening (the host focuses the first item again). */
  id: number;
  target: MenuTarget;
  /** A point (right-click, long press) or an element's box (a key, the ⋯ button). */
  at: { x: number; y: number } | Box;
  /** Focus goes back here when the menu closes. */
  opener: HTMLElement | null;
  /** Opened from the keyboard: the first item is focused and ringed. */
  keyboard: boolean;
}

export interface MenuState {
  menu: OpenMenu | null;
  toast: { id: number; text: string; tone: "ok" | "bad" } | null;
}

let state: MenuState = { menu: null, toast: null };
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((fn) => fn());

export const menuStore = {
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  getSnapshot: () => state,
};

export function showMenu(target: MenuTarget, at: OpenMenu["at"], opener: HTMLElement | null, keyboard = false): void {
  state = { ...state, menu: { id: ++seq, target, at, opener, keyboard } };
  emit();
}

/** Close the menu; `refocus` returns focus to what opened it (Escape, Tab, a key). */
export function hideMenu(refocus = false): void {
  const m = state.menu;
  if (!m) return;
  state = { ...state, menu: null };
  emit();
  // Back to what opened it, or the nearest thing round it that takes focus (a picker's list for its row).
  const back = m.opener?.isConnected ? m.opener.closest<HTMLElement>("button, a[href], input, select, textarea, [tabindex]") : null;
  if (refocus && back) back.focus({ preventScroll: true });
}

export function isMenuOpen(): boolean {
  return state.menu !== null;
}

let toastTimer: ReturnType<typeof setTimeout> | null = null;

export function showToast(text: string, tone: "ok" | "bad" = "ok"): void {
  state = { ...state, toast: { id: ++seq, text, tone } };
  emit();
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    state = { ...state, toast: null };
    emit();
  }, tone === "bad" ? 5000 : 2200);
}
