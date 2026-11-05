// The menu component without a browser: what it draws (roles, the active item, disabled items,
// the chat tag, the keys at its foot) and when its handlers open it: Shift+F10 or the menu key
// on the focused element, a right-click at the pointer, not a Shift+right-click, not a target
// that offers nothing.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import { MenuPanel, fallbackTarget, menuProps } from "./ContextMenu";
import { CHAT_HINT } from "./registry";
import { hideMenu, menuStore } from "./store";
import type { MenuModel, MenuTarget } from "./types";

const model: MenuModel = {
  title: "A1",
  sub: "1D-HP-EC-N1",
  sections: [
    { items: [{ id: "open", label: "Open in Design", icon: "design", run: () => {} }] },
    {
      items: [
        { id: "why", label: "Ask “why this design?”", icon: "ask", hint: CHAT_HINT, run: () => {} },
        { id: "resend", label: "Resend on the GPU", icon: "gpu", run: () => {}, disabled: true, why: "when the reply has finished" },
      ],
    },
  ],
};

describe("the menu's look", () => {
  const html = renderToStaticMarkup(createElement(MenuPanel, { model, active: 1, uid: "m", onRun: () => {}, onHover: () => {} }));

  it("draws its items as menu items, the active one in the tab order", () => {
    expect(html.match(/role="menuitem"/g)).toHaveLength(3);
    expect(html).toContain('id="m-1" type="button" role="menuitem" tabindex="0"');
    expect(html).toContain('id="m-0" type="button" role="menuitem" tabindex="-1"');
    expect(html).toContain('class="cm-item is-active"');
  });

  it("separates its sections, says why an item can't run, tags questions put in the chat", () => {
    expect(html).toContain('role="separator"');
    expect(html).toContain('aria-disabled="true"');
    expect(html).toContain("when the reply has finished");
    expect(html).toMatch(/class="cm-hint is-chat"[^>]*>.*chat<\/span>/);
  });

  it("names what was right-clicked and shows its keys", () => {
    expect(html).toContain('<span class="cm-title">A1</span><span class="cm-sub">1D-HP-EC-N1</span>');
    expect(html).toContain("<kbd>esc</kbd>");
  });
});

// A fake element and events: enough for the handlers (no DOM in these tests).
const el = { getBoundingClientRect: () => ({ left: 40, top: 60, width: 80, height: 20 }), focus: () => {} } as unknown as HTMLElement;
function event(over: Record<string, unknown>) {
  const e = {
    key: "",
    shiftKey: false,
    button: 0,
    clientX: 0,
    clientY: 0,
    defaultPrevented: false,
    currentTarget: el,
    nativeEvent: {},
    prevented: false,
    stopped: false,
    preventDefault() {
      e.prevented = true;
      e.defaultPrevented = true;
    },
    stopPropagation() {
      e.stopped = true;
    },
    ...over,
  };
  return e;
}
type Handlers = ReturnType<typeof menuProps>;
const asKey = (e: ReturnType<typeof event>) => e as unknown as Parameters<Handlers["onKeyDown"]>[0];
const asClick = (e: ReturnType<typeof event>) => e as unknown as Parameters<Handlers["onContextMenu"]>[0];

const design: MenuTarget = { kind: "design", design: { id: "A1" } };
const open = () => menuStore.getSnapshot().menu;

describe("opening the menu", () => {
  afterEach(() => hideMenu());

  it("Shift+F10 and the context-menu key open it under the focused element, ready for the arrows", () => {
    for (const key of [{ key: "F10", shiftKey: true }, { key: "ContextMenu" }]) {
      hideMenu();
      const e = event(key);
      menuProps(design).onKeyDown(asKey(e));
      expect(e.prevented).toBe(true);
      expect(open()?.target).toBe(design);
      expect(open()?.keyboard).toBe(true);
      expect(open()?.at).toEqual({ left: 40, top: 60, width: 80, height: 20 });
      expect(open()?.opener).toBe(el);
    }
  });

  it("other keys are left alone, and the element's own key handler runs first", () => {
    const seen: string[] = [];
    const e = event({ key: "ArrowDown" });
    menuProps(design, { onKeyDown: (k) => seen.push(k.key) }).onKeyDown(asKey(e));
    expect(seen).toEqual(["ArrowDown"]);
    expect(e.prevented).toBe(false);
    expect(open()).toBeNull();
  });

  it("a right-click opens it at the pointer and keeps the browser's menu away", () => {
    const e = event({ button: 2, clientX: 300, clientY: 200, nativeEvent: { pointerType: "mouse" } });
    menuProps(() => design).onContextMenu(asClick(e));
    expect(e.prevented).toBe(true);
    expect(e.stopped).toBe(true);
    expect(open()?.at).toEqual({ x: 300, y: 200 });
    expect(open()?.keyboard).toBe(false);
  });

  it("Shift+right-click opens the same menu: the browser's own never shows", () => {
    const e = event({ button: 2, shiftKey: true, clientX: 300, clientY: 200 });
    menuProps(design).onContextMenu(asClick(e));
    expect(e.prevented).toBe(true);
    expect(open()).not.toBeNull();
  });

  it("a link inside the target is left to the host's link menu (open in a new tab)", () => {
    const link = { closest: () => link };
    const card = { ...el, contains: (x: unknown) => x === link } as unknown as HTMLElement;
    const e = event({ button: 2, clientX: 9, clientY: 9, currentTarget: card, target: link });
    menuProps(design).onContextMenu(asClick(e));
    expect(e.prevented).toBe(false);
    expect(open()).toBeNull();
  });

  it("nothing to offer (or no target) keeps the browser's menu too", () => {
    for (const t of [null, { kind: "column", label: "Scenario" } as MenuTarget]) {
      const e = event({ button: 2, clientX: 5, clientY: 5 });
      menuProps(() => t).onContextMenu(asClick(e));
      expect(e.prevented).toBe(false);
      expect(open()).toBeNull();
    }
  });

  it("the browser's own event right after a key opened the menu changes nothing", () => {
    menuProps(design).onKeyDown(asKey(event({ key: "ContextMenu" })));
    const first = open();
    const e = event({ button: 0 });
    menuProps({ kind: "answer", markdown: "x" }).onContextMenu(asClick(e));
    expect(e.prevented).toBe(true);
    expect(open()).toBe(first);
  });
});

describe("what no target took (the host's own menus)", () => {
  const box = (tag: string, type: string | null, value: string, start: number, end: number) => {
    const f = { tagName: tag, value, selectionStart: start, selectionEnd: end, readOnly: false, disabled: false, getAttribute: () => type } as unknown as HTMLInputElement;
    (f as unknown as { closest: (s: string) => unknown }).closest = (sel: string) => (sel.includes("input") ? f : null);
    return f;
  };

  it("a text box gives its selection; a checkbox gives nothing", () => {
    const f = box("INPUT", "text", "hello world", 6, 11);
    expect(fallbackTarget(f, "")).toMatchObject({ kind: "text", selection: "world", start: 6, end: 11, editable: true });
    expect(fallbackTarget(box("INPUT", "checkbox", "", 0, 0), "")).toBeNull();
  });

  it("selected text anywhere else, or nothing at all", () => {
    const plain = { closest: () => null } as unknown as Element;
    expect(fallbackTarget(plain, "  42.9 %  ")).toEqual({ kind: "selection", text: "42.9 %" });
    expect(fallbackTarget(plain, "")).toBeNull();
  });
});

