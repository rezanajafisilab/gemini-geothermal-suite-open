// The menu's keyboard (arrows wrap over disabled items, Home/End, a letter, Enter/Space, Escape
// and Tab) and its placement (flipped and clamped, never off-screen).

import { describe, expect, it } from "vitest";

import { firstEnabled, isMenuKey, menuKey, placeMenu } from "./keys";

const items = [{ label: "Open in Design" }, { label: "Open in Energy", disabled: true }, { label: "Add to the Compare tray" }, { label: "Copy its link" }, { label: "“Why this design?”" }];

describe("the menu's keys", () => {
  it("arrows move and wrap, skipping disabled items", () => {
    expect(menuKey("ArrowDown", 0, items)).toEqual({ active: 2 });
    expect(menuKey("ArrowDown", 4, items)).toEqual({ active: 0 });
    expect(menuKey("ArrowUp", 2, items)).toEqual({ active: 0 });
    expect(menuKey("ArrowUp", 0, items)).toEqual({ active: 4 });
  });

  it("from no item (a menu opened with the mouse) the arrows start at either end", () => {
    expect(menuKey("ArrowDown", -1, items)).toEqual({ active: 0 });
    expect(menuKey("ArrowUp", -1, items)).toEqual({ active: 4 });
  });

  it("Home and End go to the first and last item that can run", () => {
    const ends = [{ label: "a", disabled: true }, { label: "b" }, { label: "c" }, { label: "d", disabled: true }];
    expect(menuKey("Home", 2, ends)).toEqual({ active: 1 });
    expect(menuKey("End", 1, ends)).toEqual({ active: 2 });
    expect(firstEnabled(ends)).toBe(1);
    expect(firstEnabled([{ label: "x", disabled: true }])).toBe(-1);
  });

  it("Enter and Space run the active item, not a disabled one, nor none", () => {
    expect(menuKey("Enter", 2, items)).toEqual({ run: 2 });
    expect(menuKey(" ", 0, items)).toEqual({ run: 0 });
    expect(menuKey("Enter", 1, items)).toBeNull();
    expect(menuKey("Enter", -1, items)).toBeNull();
  });

  it("Escape, Tab and the menu key again close it", () => {
    expect(menuKey("Escape", 0, items)).toEqual({ close: true });
    expect(menuKey("Tab", 0, items)).toEqual({ close: true });
    expect(menuKey("F10", 0, items, true)).toEqual({ close: true });
    expect(menuKey("F10", 0, items, false)).toBeNull();
    expect(menuKey("ContextMenu", 0, items)).toEqual({ close: true });
  });

  it("a letter jumps to the next item starting with it, quotes ignored, disabled skipped", () => {
    expect(menuKey("c", 0, items)).toEqual({ active: 3 });
    expect(menuKey("o", 0, items)).toEqual({ active: 0 });
    expect(menuKey("w", 0, items)).toEqual({ active: 4 });
    expect(menuKey("A", -1, items)).toEqual({ active: 2 });
    expect(menuKey("z", 0, items)).toBeNull();
    expect(menuKey("Shift", 0, items)).toBeNull();
  });

  it("Shift+F10 and the context-menu key open a menu", () => {
    expect(isMenuKey({ key: "F10", shiftKey: true })).toBe(true);
    expect(isMenuKey({ key: "ContextMenu", shiftKey: false })).toBe(true);
    expect(isMenuKey({ key: "F10", shiftKey: false })).toBe(false);
    expect(isMenuKey({ key: "Enter", shiftKey: true })).toBe(false);
  });
});

describe("where the menu goes", () => {
  const view = { w: 1024, h: 768 };
  const size = { w: 280, h: 360 };

  it("opens at the pointer, down and to the right", () => {
    expect(placeMenu({ x: 100, y: 120 }, size, view)).toEqual({ left: 100, top: 120 });
  });

  it("flips left at the right edge and up at the bottom", () => {
    expect(placeMenu({ x: 900, y: 600 }, size, view)).toEqual({ left: 620, top: 240 });
  });

  it("stays inside the window by a margin, even at a corner", () => {
    expect(placeMenu({ x: 1020, y: 2 }, size, view)).toEqual({ left: 736, top: 8 });
    expect(placeMenu({ x: 150, y: 300 }, { w: 280, h: 900 }, view)).toEqual({ left: 150, top: 8 });
    expect(placeMenu({ x: 4, y: 4 }, size, { w: 200, h: 200 })).toEqual({ left: 8, top: 8 });
  });

  it("under an element (a key, the ⋯ button) it opens below, or above when there is no room", () => {
    expect(placeMenu({ left: 200, top: 100, width: 28, height: 28 }, size, view)).toEqual({ left: 200, top: 132 });
    expect(placeMenu({ left: 200, top: 700, width: 28, height: 28 }, size, view)).toEqual({ left: 200, top: 336 });
    expect(placeMenu({ left: 950, top: 100, width: 28, height: 28 }, size, view).left).toBe(736);
  });
});
