// Full screen for the Design tab's canvases, and the sizing that keeps the tab free of dead space.
//
// FULL SCREEN. The view (Plant or GEMINI project) becomes a fixed overlay over the whole window
// (and, when the browser allows it, real full screen); the canvas fills it and every tool floats
// over it as a panel you can fold away: the view switch and the design picker, the year player,
// the palette, Run with GEMINI, the inspector. On a wide window the Plant's inspector docks at the
// right instead (the canvas ends where it starts, so it covers nothing), with the legend under it;
// the canvas is fitted again to what the panels leave free, measured. F toggles it (outside text
// fields), Esc leaves.
//
// FILL. Out of full screen, a view's stage is as tall as the window leaves below it (never less
// than a sensible minimum), so the canvas and the panels beside it end level instead of a short
// column next to a tall one.

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type ReactNode, type RefObject } from "react";

import { DesignPicker, type Design } from "../../workbench";

export type View = "plant" | "gemini";

export interface FullScreen {
  full: boolean;
  enter: () => void;
  exit: () => void;
  view: View;
  setView: (v: View) => void;
  design: Design | null;
}

const NONE: FullScreen = { full: false, enter: () => undefined, exit: () => undefined, view: "plant", setView: () => undefined, design: null };
const Ctx = createContext<FullScreen>(NONE);
export const FullScreenProvider = Ctx.Provider;
export const useFullScreen = () => useContext(Ctx);

const editable = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName);
};

/** Full-screen state for the element `target` (the view): F toggles, Esc leaves. */
export function useFullScreenState(target: RefObject<HTMLElement | null>) {
  const [full, setFull] = useState(false);
  const browser = useRef(false);
  const enter = useCallback(() => {
    setFull(true);
    const el = target.current;
    // Real full screen when the browser allows it; the overlay works without it.
    if (el && typeof el.requestFullscreen === "function" && !document.fullscreenElement) {
      el.requestFullscreen({ navigationUI: "hide" })
        .then(() => {
          browser.current = true;
        })
        .catch(() => {
          browser.current = false;
        });
    }
  }, [target]);
  const exit = useCallback(() => {
    setFull(false);
    if (browser.current && document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    browser.current = false;
  }, []);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || editable(e.target)) return;
      if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        if (full) exit();
        else enter();
      } else if (e.key === "Escape" && full) {
        e.preventDefault();
        exit();
      }
    };
    // The browser leaves its full screen on Esc itself: leave the overlay with it.
    const change = () => {
      if (!document.fullscreenElement && browser.current) {
        browser.current = false;
        setFull(false);
      }
    };
    window.addEventListener("keydown", key);
    document.addEventListener("fullscreenchange", change);
    return () => {
      window.removeEventListener("keydown", key);
      document.removeEventListener("fullscreenchange", change);
    };
  }, [full, enter, exit]);

  // Leaving the tab leaves full screen.
  useEffect(() => () => {
    if (browser.current && document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
  }, []);
  return { full, enter, exit };
}

// ------------------------------------------------------------------ controls

function ExpandIcon({ out }: { out: boolean }) {
  return out ? (
    <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M6 2.5v3.5H2.5M10 2.5v3.5h3.5M6 13.5V10H2.5M10 13.5V10h3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M2.5 6V2.5H6M13.5 6V2.5H10M2.5 10v3.5H6M13.5 10v3.5H10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** "Full screen" (or "Exit full screen"), with its shortcut in the tooltip. */
export function FullButton({ className }: { className?: string }) {
  const { full, enter, exit } = useFullScreen();
  return (
    <button
      type="button"
      className={`dz-full-btn ta-btn ta-chip${className ? ` ${className}` : ""}`}
      onClick={full ? exit : enter}
      aria-keyshortcuts={full ? "Escape" : "F"}
      title={full ? "Exit full screen (Esc)" : "Full screen (F)"}
    >
      <ExpandIcon out={full} />
      {full ? "Exit full screen" : "Full screen"}
    </button>
  );
}

const VIEWS: { id: View; label: string }[] = [
  { id: "plant", label: "Plant" },
  { id: "gemini", label: "GEMINI project" },
];

/** Plant | GEMINI project. */
export function ViewSwitch({ compact = false }: { compact?: boolean }) {
  const { view, setView, design } = useFullScreen();
  const at = VIEWS.findIndex((v) => v.id === view);
  return (
    <div className={`seg dz-views${compact ? " mini" : ""}`} role="tablist" aria-label="Views of the design">
      <span
        className="seg-thumb ta-thumb"
        style={{ left: `calc(${compact ? 3 : 4}px + ${at} * (100% - ${compact ? 6 : 8}px) / ${VIEWS.length})`, width: `calc((100% - ${compact ? 6 : 8}px) / ${VIEWS.length})` }}
      />
      {VIEWS.map((v) => (
        <button
          key={v.id}
          type="button"
          role="tab"
          id={compact ? undefined : `dz-tab-${v.id}`}
          aria-selected={view === v.id}
          aria-controls="dz-view"
          style={{ fontWeight: view === v.id ? 650 : 450 }}
          onClick={() => setView(v.id)}
        >
          {v.label}
          {v.id === "gemini" && design && !design.graph.gemini_project && <span className="sr-only"> (none for this design)</span>}
        </button>
      ))}
    </div>
  );
}

/** The top of a view in full screen: which design, which view, and the way out. */
export function FullBar({ children }: { children?: ReactNode }) {
  return (
    <div className="dz-fbar-row">
      <DesignPicker />
      <ViewSwitch compact />
      {children}
      <FullButton className="dz-fbar-exit" />
    </div>
  );
}

/** A panel's fold button in full screen; `toward` is the edge the panel folds to. */
export function FoldButton({ open, onToggle, label, toward }: { open: boolean; onToggle: () => void; label: string; toward: "left" | "right" | "down" }) {
  const turn = { right: 0, down: 90, left: 180 }[toward] + (open ? 0 : 180);
  return (
    <button type="button" className="dz-fold ta-btn ta-chip" aria-expanded={open} onClick={onToggle} title={`${open ? "Fold away" : "Show"} ${label}`}>
      <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" style={{ transform: `rotate(${turn}deg)` }}>
        <path d="M6 3.5 10.5 8 6 12.5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className={open ? "sr-only" : undefined}>{open ? `Fold away ${label}` : label}</span>
    </button>
  );
}

// ------------------------------------------------------------------ sizes

function scrollParent(el: HTMLElement): HTMLElement | null {
  for (let p = el.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowY;
    if ((o === "auto" || o === "scroll") && p.scrollHeight >= p.clientHeight) return p;
  }
  return null;
}

/**
 * The height that takes an element from where it starts to the bottom of the window (its scroll
 * container), less `bottom`, and at least `min`. Re-measured when the window or what sits above
 * it changes size.
 */
export function useFill<T extends HTMLElement>(min: number, bottom = 20): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [h, setH] = useState(min);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const scroller = scrollParent(el);
      const top = scroller ? el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop : el.getBoundingClientRect().top + window.scrollY;
      const viewH = scroller ? scroller.clientHeight : window.innerHeight;
      const next = Math.max(min, Math.round(viewH - top - bottom));
      setH((old) => (Math.abs(old - next) > 1 ? next : old));
    };
    measure();
    window.addEventListener("resize", measure);
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    if (el.parentElement) ro?.observe(el.parentElement);
    return () => {
      window.removeEventListener("resize", measure);
      ro?.disconnect();
    };
  }, [min, bottom]);
  return [ref, h];
}

/** An element's size, "860x430", for refitting a canvas when it changes. */
export function useSize<T extends HTMLElement>(): [RefObject<T | null>, { w: number; h: number }] {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => {
      const w = Math.round(e.contentRect.width);
      const h = Math.round(e.contentRect.height);
      setSize((s) => (s.w === w && s.h === h ? s : { w, h }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size];
}

/**
 * An element's outer size (border box), "0x0" while it is not there. `on` says when it may have
 * appeared, gone or moved (a panel shown only in full screen, or put elsewhere), so it is looked
 * up again.
 */
export function useBox<T extends HTMLElement>(on: boolean | string): [RefObject<T | null>, { w: number; h: number }] {
  const ref = useRef<T>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      setBox((b) => (b.w || b.h ? { w: 0, h: 0 } : b));
      return;
    }
    const measure = () => {
      const r = el.getBoundingClientRect();
      const w = Math.round(r.width);
      const h = Math.round(r.height);
      setBox((b) => (b.w === w && b.h === h ? b : { w, h }));
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [on]);
  return [ref, box];
}

/** True while the window is at least `px` wide (a media query, so it follows resizing). */
export function useMinWidth(px: number): boolean {
  const query = `(min-width: ${px}px)`;
  const subscribe = useCallback(
    (fn: () => void) => {
      const m = typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query) : null;
      m?.addEventListener("change", fn);
      return () => m?.removeEventListener("change", fn);
    },
    [query],
  );
  return useSyncExternalStore(subscribe, () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : true), () => true);
}

/** True on a phone-sized window (panels start folded in full screen there). */
export const narrowWindow = () => typeof window !== "undefined" && window.innerWidth < 760;
