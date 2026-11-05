// The menu's keyboard and placement, as pure functions (tested in keys.test.ts without a DOM).
// Keys: arrows move (wrapping, over disabled items), Home and End, Enter or Space runs the item,
// Escape and Tab close, a letter jumps to the next item starting with it. Placement: at the
// pointer (or under the element it opened from), flipped and clamped so it is never off-screen.

export interface NavItem {
  label: string;
  disabled?: boolean;
}

export type NavResult = { active: number } | { run: number } | { close: true };

const enabled = (items: NavItem[]) => items.map((it, i) => (it.disabled ? -1 : i)).filter((i) => i >= 0);

/** The first item that can be run (-1 when none can). */
export function firstEnabled(items: NavItem[]): number {
  return enabled(items)[0] ?? -1;
}

/** What a key does in a menu whose item `active` has focus; null: not the menu's key. */
export function menuKey(key: string, active: number, items: NavItem[], shift = false): NavResult | null {
  const ok = enabled(items);
  const at = ok.indexOf(active);
  switch (key) {
    case "ArrowDown":
      return ok.length ? { active: ok[(at + 1) % ok.length] } : null;
    case "ArrowUp":
      return ok.length ? { active: ok[at <= 0 ? ok.length - 1 : at - 1] } : null;
    case "Home":
    case "PageUp":
      return ok.length ? { active: ok[0] } : null;
    case "End":
    case "PageDown":
      return ok.length ? { active: ok[ok.length - 1] } : null;
    case "Enter":
    case " ":
      return active >= 0 && !items[active]?.disabled ? { run: active } : null;
    case "Escape":
    case "Tab":
      return { close: true };
    case "F10":
      return shift ? { close: true } : null;
    case "ContextMenu":
      return { close: true };
  }
  if (key.length === 1 && /\S/.test(key)) {
    const k = key.toLowerCase();
    const start = active >= 0 ? active : -1;
    for (let n = 1; n <= items.length; n++) {
      const i = (start + n + items.length) % items.length;
      if (!items[i].disabled && items[i].label.replace(/^[“"]/, "").toLowerCase().startsWith(k)) return { active: i };
    }
  }
  return null;
}

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Where the menu goes: at a point (a right-click, a long press) it opens down and to the right,
 * flipping left or up where it would leave the window; under an element (a key, the ⋯ button) it
 * opens below it, or above when there is no room. Always inside the window, `margin` from its
 * edges; a menu taller than the window starts at the top (it scrolls inside).
 */
export function placeMenu(at: { x: number; y: number } | Box, size: { w: number; h: number }, view: { w: number; h: number }, margin = 8): { left: number; top: number } {
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi));
  const maxLeft = Math.max(margin, view.w - size.w - margin);
  const maxTop = Math.max(margin, view.h - size.h - margin);
  if ("x" in at) {
    const left = at.x + size.w > view.w - margin ? at.x - size.w : at.x;
    const top = at.y + size.h > view.h - margin ? at.y - size.h : at.y;
    return { left: clamp(left, margin, maxLeft), top: clamp(top, margin, maxTop) };
  }
  const below = at.top + at.height + 4;
  const above = at.top - size.h - 4;
  const top = below + size.h <= view.h - margin || above < margin ? below : above;
  return { left: clamp(at.left, margin, maxLeft), top: clamp(top, margin, maxTop) };
}

/** Shift+F10 or the context-menu key: open the menu of the focused thing. */
export function isMenuKey(e: { key: string; shiftKey: boolean }): boolean {
  return e.key === "ContextMenu" || (e.shiftKey && e.key === "F10");
}
