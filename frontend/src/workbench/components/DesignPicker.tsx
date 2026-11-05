// The design picker: a pill with the design the one-design tabs show, and a list of every design
// of the conversation (2 Nov): the shortlist (the stars), the latest run's picks, what-ifs, the
// user's designs; typing finds any design of any run. Each row: its handle (A1), what it is in
// words (or the user's name), its code and run, and a star. A design not yet in the tabs opens
// there when picked. Picking changes the route (#energy/A2), so back and forward step through.

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";

import { Chevron, Tick } from "../../components/Icons";
import { designItems, designSections, type DesignItem } from "../designList";
import { MenuButton, isMenuKey, menuProps, openMenuAt, type MenuTarget } from "../../menu";
import { originLabel, statusWords } from "../format";
import { TAB_META, go, useRoute, type TabId } from "../route";
import { useWorkbench } from "../store";
import type { Design } from "../types";
import "./workbench.css";

interface Props {
  /** The tab whose route a pick changes (default: the tab on screen). */
  tab?: TabId;
  /** Called with the picked id instead of changing the route. */
  onPick?: (id: string) => void;
  /** Leave designs out of the menu, e.g. the gas reference. */
  filter?: (d: Design) => boolean;
}

export function DesignStatus({ design }: { design: Design }) {
  const failed = design.checks.filter((c) => !c.passed).map((c) => c.name);
  if (design.verified && !failed.length)
    return (
      <span className="wb-verified">
        <Tick size={12} />
        verified
      </span>
    );
  // What happened in words (Ali, 3 Nov: "not verified" said nothing): the check, or how many.
  return (
    <span className="wb-fails" title={failed.length ? `Fails: ${failed.join("; ")}` : undefined}>
      {statusWords(failed, design.verified)}
    </span>
  );
}

/** A design's context menu target: open it in the tabs, compare it, ask about it (menu/registry.ts). */
export const designTarget = (d: Design): MenuTarget => ({ kind: "design", design: { id: d.id, name: d.uid || d.code, sub: d.uid && d.uid !== d.code ? `${d.code} · ${d.name}` : d.name } });

/**
 * Keeps a dropdown inside the window: when it would run past the right edge, `--menu-shift`
 * moves it left (it opens under its button, as wide as the window allows).
 */
export function useOnScreen(open: boolean, menu: RefObject<HTMLElement | null>, margin = 16) {
  useLayoutEffect(() => {
    const el = menu.current;
    if (!open || !el) return;
    el.style.setProperty("--menu-shift", "0px");
    const r = el.getBoundingClientRect();
    const over = r.right - (window.innerWidth - margin);
    if (over > 0) el.style.setProperty("--menu-shift", `${-Math.min(over, Math.max(0, r.left - margin))}px`);
  }, [open, menu, margin]);
}

export function DesignPicker({ tab, onPick, filter }: Props) {
  const wb = useWorkbench();
  const route = useRoute();
  const current = wb.selected;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActiveState] = useState(0);
  // The key handler reads the latest index even before React re-renders (fast typing).
  const activeRef = useRef(0);
  const setActive = (i: number) => {
    activeRef.current = i;
    setActiveState(i);
  };
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const uid = useId();
  const optId = (i: number) => `${uid}-opt-${i}`;
  useOnScreen(open, pop);

  const hidden = new Set(filter ? wb.designs.filter((d) => !filter(d)).map((d) => d.id) : []);
  const items = designItems(wb.workbench).filter((i) => !hidden.has(i.id));
  const sections = designSections(items, query);
  const flat = sections.flatMap((x) => x.items);

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    const away = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  useEffect(() => {
    if (open) document.getElementById(optId(active))?.scrollIntoView({ block: "nearest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, active]);

  if (!wb.designs.length || !current) return null;

  const show = () => {
    setQuery("");
    const all = designSections(items, "").flatMap((x) => x.items);
    setActive(Math.max(0, all.findIndex((d) => d.id === current.id)));
    setOpen(true);
  };
  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) button.current?.focus();
  };
  const pick = async (d: DesignItem) => {
    close();
    if (d.id === current.id) return;
    // A design of an earlier run, or one the tabs don't have yet: it opens there first.
    const id = d.inTabs ? d.id : ((await wb.openDesign(d.id)).ok ? d.id : null);
    if (!id) return;
    if (onPick) return onPick(id);
    const t = tab ?? route.tab;
    if (TAB_META[t].scope === "design") go(t, id);
    else wb.select(id);
  };
  const star = (d: DesignItem) => void wb.setMeta(d.id, { starred: !d.starred });
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    const last = flat.length - 1;
    const at = activeRef.current;
    if (isMenuKey(e)) {
      const row = document.getElementById(optId(at));
      const d = flat[at];
      if (row && d) {
        const full = wb.designs.find((x) => x.id === d.id);
        const target: MenuTarget = full ? designTarget(full) : { kind: "design", design: { id: d.id, name: d.uid, sub: d.label } };
        if (openMenuAt(target, row.getBoundingClientRect(), input.current, true)) e.preventDefault();
      }
      return;
    }
    const moves: Record<string, () => void> = {
      ArrowDown: () => setActive(Math.min(last, at + 1)),
      ArrowUp: () => setActive(Math.max(0, at - 1)),
      PageDown: () => setActive(Math.min(last, at + 8)),
      PageUp: () => setActive(Math.max(0, at - 8)),
      Enter: () => flat[at] && void pick(flat[at]),
      Escape: () => close(),
    };
    if (e.key === "Tab") return close(false);
    if (e.altKey && e.key.toLowerCase() === "s" && flat[at]) {
      e.preventDefault();
      return star(flat[at]);
    }
    const move = moves[e.key];
    if (!move) return;
    e.preventDefault();
    move();
  };
  const label = current.label || current.name;
  let n = -1;

  return (
    <div className="wb-picker" ref={root}>
      <button
        ref={button}
        type="button"
        className="wb-pick-btn ta-btn ta-chip"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Design: ${current.uid ? `${current.uid}, ` : ""}${label}, ${current.code}${current.origin === "what_if" ? `, ${originLabel(current)}` : ""}. Change`}
        onClick={() => (open ? close() : show())}
        {...menuProps(() => designTarget(current), {
          onKeyDown: (e) => {
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              show();
            }
          },
        })}
      >
        {current.uid && current.uid !== current.code && <span className="uid-chip">{current.uid}</span>}
        <span className="wb-pick-text">
          <span className="wb-pick-name" title={current.name}>
            {current.starred && <span className="wb-star-on" aria-label="starred">★ </span>}
            {label}
          </span>
          <span className="wb-pick-sub">
            <span className="wb-code small">{current.code}</span>
            <DesignStatus design={current} />
            {current.chosen && <span>· chosen</span>}
          </span>
        </span>
        <Chevron open={open} />
      </button>
      <MenuButton target={() => designTarget(current)} label={`More for ${current.uid || current.code}: open, compare, ask, rename, star`} className="wb-pick-more" />
      {open && (
        <div ref={pop} className="wb-menu wb-pop ta-rise">
          <div className="wb-find">
            <input
              ref={input}
              type="search"
              value={query}
              placeholder="Find a design: A1, cheapest, gas-free, 2D-HP…"
              aria-label="Find a design"
              role="combobox"
              aria-expanded="true"
              aria-controls={`${uid}-list`}
              aria-activedescendant={flat[active] ? optId(active) : undefined}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={onKey}
            />
          </div>
          <ul id={`${uid}-list`} className="wb-list" role="listbox" aria-label="Designs in this chat">
            {sections.length === 0 && (
              <li className="wb-empty" role="presentation">
                No design matches “{query}”.
              </li>
            )}
            {sections.map((sec) => (
              <li key={sec.key} role="presentation">
                <span className="wb-menu-cap">{sec.title}</span>
                <ul role="group" aria-label={sec.title} className="wb-group">
                  {sec.items.map((d) => {
                    n += 1;
                    const i = n;
                    const selected = d.id === current.id;
                    const full = wb.designs.find((x) => x.id === d.id);
                    return (
                      <li
                        key={d.id}
                        id={optId(i)}
                        role="option"
                        aria-selected={selected}
                        className={`wb-opt${i === active ? " active" : ""}`}
                        onMouseMove={() => i !== active && setActive(i)}
                        onClick={() => void pick(d)}
                        {...menuProps(() => (full ? designTarget(full) : { kind: "design", design: { id: d.id, name: d.uid, sub: d.label } }))}
                      >
                        <span className="wb-opt-id">
                          <span className="uid-chip small">{d.uid}</span>
                        </span>
                        <span className="wb-opt-main">
                          <span className="wb-opt-name" title={`${d.label} · ${d.name}`}>
                            {d.label}
                            <span className="wb-opt-sub">
                              {d.code}
                              {d.run ? ` · ${d.run.name}` : ""}
                            </span>
                          </span>
                          <span className="wb-opt-tags">
                            {d.lcoe != null && <span className="wb-opt-num">{d.lcoe.toFixed(1)} €/MWh</span>}
                            {d.recommended && <span className="tag tag-ok">chosen</span>}
                            {!d.verified && (
                              <span className="tag tag-amber" title={d.failed.length ? `Fails: ${d.failed.join("; ")}` : undefined}>
                                {statusWords(d.failed, d.verified)}
                              </span>
                            )}
                            {!d.inTabs && <span className="tag tag-grey">opens in the tabs</span>}
                          </span>
                        </span>
                        <span
                          role="button"
                          tabIndex={-1}
                          className={`wb-star${d.starred ? " on" : ""}`}
                          aria-label={d.starred ? `Take ${d.uid} off the shortlist` : `Star ${d.uid}: add it to the shortlist`}
                          aria-pressed={d.starred}
                          title={d.starred ? "On your shortlist (Alt+S)" : "Add to your shortlist (Alt+S)"}
                          onClick={(e) => {
                            e.stopPropagation();
                            star(d);
                          }}
                        >
                          {d.starred ? "★" : "☆"}
                        </span>
                        <span className="wb-check">{selected && <Tick size={14} />}</span>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
          <div className="wb-pop-foot">
            <span>
              <kbd>↑</kbd>
              <kbd>↓</kbd> move <kbd>↵</kbd> open <kbd>Alt</kbd>
              <kbd>S</kbd> star
            </span>
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                close(false);
                go("compare");
              }}
            >
              All designs in Compare →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
