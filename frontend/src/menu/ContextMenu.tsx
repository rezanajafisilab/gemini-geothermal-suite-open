// The app's one context menu. Any element becomes a menu's target with {...menuProps(target)}: it
// opens on a right-click, on Shift+F10 or the context-menu key while the element has focus, and
// on a long press (touch, pen). A "⋯" button (MenuButton) opens the same menu for
// discoverability. The host (mounted once, in main.tsx) draws the menu at the pointer or under
// the element, never off-screen; arrow keys, Home/End, a letter, Enter or Space, Escape; it
// closes on a click outside, a scroll, a resize or another tab, and gives focus back.
// The browser's own menu is never shown: a text box, a link or selected text that no target claims
// gets its own menu here (ContextMenuHost), and anything else nothing at all.

import "./menu.css";

import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore, type KeyboardEvent, type MouseEvent, type PointerEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { workbench } from "../workbench/store";
import { DotsIcon, MenuIcon } from "./icons";
import { firstEnabled, isMenuKey, menuKey, placeMenu, type Box } from "./keys";
import { appOps } from "./ops";
import { NameBoxHost } from "./NameBox";
import { QuickAskHost } from "./QuickAsk";
import { noteMenuRun } from "./quickask";
import { CHAT_HINT, itemsOf, menuFor } from "./registry";
import { hideMenu, isMenuOpen, menuStore, showMenu, type OpenMenu } from "./store";
import type { MenuModel, MenuOps, MenuTarget } from "./types";

export type TargetArg = MenuTarget | null | undefined | (() => MenuTarget | null | undefined);
const resolve = (t: TargetArg): MenuTarget | null => (typeof t === "function" ? t() : t) ?? null;

const rectOf = (el: Element): Box => {
  const r = el.getBoundingClientRect();
  return { left: r.left, top: r.top, width: r.width, height: r.height };
};

/** When a menu last opened: the browser's own contextmenu event for the same key or press is dropped. */
let lastOpen = 0;
/** Pointer events a target nearer the pointer already took (a chip inside an answer). */
const taken = new WeakSet<Event>();
const LONG_PRESS_MS = 520;
const presses = new WeakMap<Element, { timer: ReturnType<typeof setTimeout>; x: number; y: number }>();

/** Open a target's menu (false when it offers nothing, so the browser's menu can stay). */
export function openMenuAt(target: MenuTarget, at: OpenMenu["at"], opener: HTMLElement | null, keyboard = false, ops: MenuOps = appOps): boolean {
  if (!itemsOf(menuFor(target, ops)).length) return false;
  // A design's menu learns the recommended design and the library once the workbench is in.
  void workbench.load();
  showMenu(target, at, opener, keyboard);
  lastOpen = performance.now();
  return true;
}

function endPress(el: Element) {
  const p = presses.get(el);
  if (p) clearTimeout(p.timer);
  presses.delete(el);
}

/** After a long press opened a menu, the click the finger's lift makes is not a click. */
function swallowNextClick() {
  const stop = (e: Event) => {
    e.preventDefault();
    e.stopPropagation();
  };
  window.addEventListener("click", stop, { capture: true, once: true });
  setTimeout(() => window.removeEventListener("click", stop, { capture: true }), 800);
}

export interface MenuHandlers {
  onContextMenu: (e: MouseEvent<HTMLElement | SVGElement>) => void;
  onKeyDown: (e: KeyboardEvent<HTMLElement | SVGElement>) => void;
  onPointerDown: (e: PointerEvent<HTMLElement | SVGElement>) => void;
  onPointerMove: (e: PointerEvent<HTMLElement | SVGElement>) => void;
  onPointerUp: (e: PointerEvent<HTMLElement | SVGElement>) => void;
  onPointerCancel: (e: PointerEvent<HTMLElement | SVGElement>) => void;
}

/**
 * The handlers that make an element a menu's target. `target` may be a function, so a long list
 * builds a target only when one is opened. `own` handlers of the element run first.
 */
export function menuProps(target: TargetArg, own: Partial<Pick<MenuHandlers, "onKeyDown" | "onPointerDown">> = {}): MenuHandlers {
  return {
    onContextMenu: (e) => {
      // A link or a field inside the target gets its own menu (open in a new tab, paste) from the host.
      const inner = (e.target as Element | null)?.closest?.("a[href], input, textarea, select");
      if (inner && inner !== e.currentTarget && (e.currentTarget as Element).contains(inner)) return;
      if (isMenuOpen() && performance.now() - lastOpen < 600) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      const t = resolve(target);
      if (!t) return;
      const el = e.currentTarget as HTMLElement;
      // A key's contextmenu (no button, no pointer) opens under the element; a click at the pointer.
      const pointer = (e.nativeEvent as globalThis.PointerEvent).pointerType;
      const keyboard = e.button !== 2 && !pointer;
      if (openMenuAt(t, keyboard ? rectOf(el) : { x: e.clientX, y: e.clientY }, el, keyboard)) {
        e.preventDefault();
        e.stopPropagation();
      }
    },
    onKeyDown: (e) => {
      own.onKeyDown?.(e);
      if (e.defaultPrevented || !isMenuKey(e)) return;
      const t = resolve(target);
      if (!t) return;
      const el = e.currentTarget as HTMLElement;
      if (openMenuAt(t, rectOf(el), el, true)) {
        e.preventDefault();
        e.stopPropagation();
      }
    },
    onPointerDown: (e) => {
      own.onPointerDown?.(e);
      if (e.pointerType === "mouse" || taken.has(e.nativeEvent)) return;
      taken.add(e.nativeEvent);
      const el = e.currentTarget;
      const x = e.clientX;
      const y = e.clientY;
      endPress(el);
      const timer = setTimeout(() => {
        presses.delete(el);
        const t = resolve(target);
        if (t && openMenuAt(t, { x, y }, el as HTMLElement)) swallowNextClick();
      }, LONG_PRESS_MS);
      presses.set(el, { timer, x, y });
    },
    onPointerMove: (e) => {
      const p = presses.get(e.currentTarget);
      if (p && Math.hypot(e.clientX - p.x, e.clientY - p.y) > 10) endPress(e.currentTarget);
    },
    onPointerUp: (e) => endPress(e.currentTarget),
    onPointerCancel: (e) => endPress(e.currentTarget),
  };
}

// ------------------------------------------------------------------ the ⋯ button

/** "⋯": opens the same menu as a right-click on the thing it sits by. */
export function MenuButton({ target, label, className, small = false }: { target: TargetArg; label: string; className?: string; small?: boolean }) {
  const s = useSyncExternalStore(menuStore.subscribe, menuStore.getSnapshot, menuStore.getSnapshot);
  const ref = useRef<HTMLButtonElement>(null);
  const expanded = !!s.menu && !!ref.current && s.menu.opener === ref.current;
  return (
    <button
      ref={ref}
      type="button"
      className={`cm-more${small ? " small" : ""}${className ? ` ${className}` : ""}`}
      aria-label={label}
      title={label}
      aria-haspopup="menu"
      aria-expanded={expanded}
      onClick={(e) => {
        e.stopPropagation();
        if (expanded) return hideMenu(true);
        const t = resolve(target);
        // Enter or Space (no pointer) opens with the first item ringed.
        if (t && ref.current) openMenuAt(t, rectOf(ref.current), ref.current, e.detail === 0);
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const t = resolve(target);
        if (t && ref.current && !expanded) openMenuAt(t, rectOf(ref.current), ref.current);
      }}
    >
      <DotsIcon size={small ? 14 : 16} />
    </button>
  );
}

// ------------------------------------------------------------------ the menu

interface PanelProps {
  model: MenuModel;
  active: number;
  /** The menu's own id, for its items' ids. */
  uid: string;
  onRun: (i: number) => void;
  onHover: (i: number) => void;
  itemRef?: (i: number, el: HTMLButtonElement | null) => void;
}

/** The menu's look: its head, the items in sections with icons and hints, the keys at the foot. */
export function MenuPanel({ model, active, uid, onRun, onHover, itemRef }: PanelProps) {
  let i = -1;
  const sections: ReactNode[] = model.sections.map((s, si) => (
    <Fragment key={si}>
      {si > 0 && <div role="separator" className="cm-sep" />}
      {s.items.map((it) => {
        i += 1;
        const at = i;
        return (
          <button
            key={it.id}
            ref={itemRef ? (el) => itemRef(at, el) : undefined}
            id={`${uid}-${at}`}
            type="button"
            role="menuitem"
            tabIndex={at === active ? 0 : -1}
            aria-disabled={it.disabled || undefined}
            className={`cm-item${at === active ? " is-active" : ""}`}
            onPointerMove={() => at !== active && onHover(at)}
            onClick={() => onRun(at)}
          >
            <MenuIcon name={it.icon} />
            <span className="cm-label">{it.label}</span>
            {it.why && <span className="cm-why">{it.why}</span>}
            {it.hint &&
              (it.hint === CHAT_HINT ? (
                <span className="cm-hint is-chat" title="Puts a question in the chat for you to edit and send">
                  <svg width="11" height="11" viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M2.5 3.5h11v7.2H7.6L4.6 13.2v-2.5H2.5z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                  </svg>
                  chat
                </span>
              ) : (
                <span className={`cm-hint${it.hint.length === 1 ? " is-key" : ""}`}>{it.hint}</span>
              ))}
          </button>
        );
      })}
    </Fragment>
  ));
  return (
    <>
      <div className="cm-head" aria-hidden="true">
        <span className="cm-title">{model.title}</span>
        {model.sub && <span className="cm-sub">{model.sub}</span>}
      </div>
      {sections}
      <div className="cm-foot" aria-hidden="true">
        <kbd>↑</kbd>
        <kbd>↓</kbd>
        <span>move</span>
        <kbd>↵</kbd>
        <span>choose</span>
        <kbd>esc</kbd>
        <span>close</span>
      </div>
    </>
  );
}

function MenuView({ menu }: { menu: OpenMenu }) {
  // Built again when the workbench changes (the recommended design arrives with it).
  const wb = useSyncExternalStore(workbench.subscribe, workbench.getSnapshot, workbench.getSnapshot);
  const model = useMemo(() => menuFor(menu.target, appOps), [menu, wb]);
  const items = itemsOf(model);
  const [active, setActive] = useState(() => (menu.keyboard ? firstEnabled(items) : -1));
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const els = useRef<(HTMLButtonElement | null)[]>([]);
  const uid = `cm-${menu.id}`;

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    setPos(placeMenu(menu.at, { w: el.offsetWidth, h: el.offsetHeight }, { w: window.innerWidth, h: window.innerHeight }));
  }, [menu, model.sections.length, items.length]);

  useEffect(() => {
    if (!pos) return;
    const el = active >= 0 ? els.current[active] : root.current;
    el?.focus({ preventScroll: true });
  }, [active, pos]);

  useEffect(() => {
    const away = (e: Event) => {
      const t = e.target as Node | null;
      if (root.current?.contains(t) || (t && menu.opener?.contains(t) && menu.opener.classList.contains("cm-more"))) return;
      hideMenu(false);
    };
    const scrolled = (e: Event) => {
      if (!root.current?.contains(e.target as Node)) hideMenu(false);
    };
    const gone = () => hideMenu(false);
    document.addEventListener("pointerdown", away, true);
    window.addEventListener("scroll", scrolled, true);
    window.addEventListener("resize", gone);
    window.addEventListener("blur", gone);
    window.addEventListener("hashchange", gone);
    return () => {
      document.removeEventListener("pointerdown", away, true);
      window.removeEventListener("scroll", scrolled, true);
      window.removeEventListener("resize", gone);
      window.removeEventListener("blur", gone);
      window.removeEventListener("hashchange", gone);
    };
  }, [menu]);

  const run = (i: number) => {
    const it = items[i];
    if (!it || it.disabled) return;
    // A question it starts opens in the quick-ask box, where the menu was and about what it named.
    noteMenuRun(model.sub && model.sub !== model.title ? `${model.title} · ${model.sub}` : model.title, menu.at);
    hideMenu(true);
    void it.run();
  };

  return (
    <div
      ref={root}
      role="menu"
      tabIndex={-1}
      aria-label={model.sub ? `${model.title}, ${model.sub}` : model.title}
      className="cm"
      style={pos ? { left: pos.left, top: pos.top } : { left: 0, top: 0, visibility: "hidden" }}
      onContextMenu={(e) => e.preventDefault()}
      onKeyDown={(e) => {
        const res = menuKey(e.key, active, items, e.shiftKey);
        if (!res) return;
        e.preventDefault();
        e.stopPropagation();
        if ("active" in res) setActive(res.active);
        else if ("run" in res) run(res.run);
        else hideMenu(true);
      }}
    >
      <MenuPanel model={model} active={active} uid={uid} onRun={run} onHover={(i) => !items[i]?.disabled && setActive(i)} itemRef={(i, el) => (els.current[i] = el)} />
    </div>
  );
}

const FIELD = "input, textarea";
/** Input types that hold text a menu can cut, copy and paste. */
const TEXT_TYPES = new Set(["", "text", "search", "email", "url", "tel", "password", "number"]);

/** What a right-click that no target took is about: a text box, a link, selected text, or nothing. */
export function fallbackTarget(el: Element | null, selected: string): MenuTarget | null {
  const field = el?.closest?.(FIELD) as HTMLInputElement | HTMLTextAreaElement | null;
  if (field && (field.tagName === "TEXTAREA" || TEXT_TYPES.has((field.getAttribute("type") ?? "").toLowerCase()))) {
    let start = 0;
    let end = 0;
    try {
      start = field.selectionStart ?? 0;
      end = field.selectionEnd ?? 0;
    } catch {
      /* a number field has no selection */
    }
    const selection = field.value.slice(start, end);
    return { kind: "text", field, selection, start, end, editable: !field.readOnly && !field.disabled };
  }
  const link = el?.closest?.("a[href]") as HTMLAnchorElement | null;
  if (link && !link.getAttribute("href")?.startsWith("#")) return { kind: "link", href: link.href, text: (link.textContent ?? "").trim() };
  if (selected.trim()) return { kind: "selection", text: selected.trim() };
  return null;
}

/** Where the menu and the quick-ask box are drawn: in the full-screen element when there is one. */
function useLayer(): Element | null {
  const [el, setEl] = useState<Element | null>(() => (typeof document === "undefined" ? null : (document.fullscreenElement ?? document.body)));
  useEffect(() => {
    const on = () => setEl(document.fullscreenElement ?? document.body);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);
  return el;
}

/** Draws the menu on screen and the toast an item leaves; mounted once, beside the app. */
export function ContextMenuHost() {
  const s = useSyncExternalStore(menuStore.subscribe, menuStore.getSnapshot, menuStore.getSnapshot);
  // The browser's menu never shows: what no target took gets the text, link or selection menu.
  useEffect(() => {
    const fallback = (e: globalThis.MouseEvent) => {
      if (e.defaultPrevented) return;
      e.preventDefault();
      if (isMenuOpen() && performance.now() - lastOpen < 600) return;
      const t = fallbackTarget(e.target as Element | null, window.getSelection()?.toString() ?? "");
      const opener = (e.target as Element | null)?.closest?.<HTMLElement>("input, textarea, a[href], [tabindex], button") ?? null;
      if (t) openMenuAt(t, { x: e.clientX, y: e.clientY }, opener, e.button !== 2 && !(e as globalThis.PointerEvent).pointerType);
    };
    document.addEventListener("contextmenu", fallback);
    return () => document.removeEventListener("contextmenu", fallback);
  }, []);
  const layer = useLayer();
  if (typeof document === "undefined" || !layer) return null;
  return createPortal(
    <>
      {s.menu && <MenuView key={s.menu.id} menu={s.menu} />}
      <QuickAskHost />
      <NameBoxHost />
      <div className="cm-toast-live" role="status" aria-live="polite">
        {s.toast && (
          <span key={s.toast.id} className={`cm-toast${s.toast.tone === "bad" ? " bad" : ""}`}>
            {s.toast.tone === "ok" && (
              <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M3.5 8.4 6.6 11.4 12.5 5" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            {s.toast.text}
          </span>
        )}
      </div>
    </>,
    layer,
  );
}
