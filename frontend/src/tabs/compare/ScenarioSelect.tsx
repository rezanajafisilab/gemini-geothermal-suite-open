// The scenario filter: one control however many searches and what-ifs the chat ran. A button
// with the scenario on screen and its count; its menu lists "All scenarios" and every scenario
// (newest or oldest first) with its kind, the search behind it, when it ran and what was asked,
// and how many designs it has. With many scenarios the menu has a filter box. Keyboard: arrows,
// Home/End, Enter picks, Escape closes.

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { Chevron, Tick } from "../../components/Icons";
import { useOnScreen } from "../../workbench/components/DesignPicker";
import { KIND_CLASS } from "./bits";
import { ALL, KIND_WORD, orderScenarios, type ScenarioGroup } from "./library";
import { attemptTime } from "./search";

interface Props {
  groups: ScenarioGroup[];
  value: string;
  /** Every design of the chat (the "All scenarios" count). */
  total: number;
  order: "newest" | "oldest";
  onOrder: (o: "newest" | "oldest") => void;
  onChange: (key: string) => void;
}

interface Option {
  key: string;
  label: string;
  kind: string;
  count: number;
  meta: string;
  recommended: boolean;
}

/** "Search 2 · 14:30 · “what if gas cost 30 €/MWh?”": where a scenario came from. */
export function scenarioMeta(g: ScenarioGroup): string {
  const a = g.attempt;
  const msg = a?.message?.trim();
  const quote = msg ? `“${msg.length > 64 ? `${msg.slice(0, 62).trimEnd()}…` : msg}”` : "";
  if (g.kind === "user") return "your edits on the Design tab";
  return [g.n ? `Search ${g.n}` : "a design re-run under the change", attemptTime(a?.at), quote].filter(Boolean).join(" · ");
}

export function ScenarioSelect({ groups, value, total, order, onOrder, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  useOnScreen(open, menu);
  const uid = useId();
  const optId = (i: number) => `${uid}-opt-${i}`;
  const searchable = groups.length > 6;

  const options = useMemo<Option[]>(() => {
    const all: Option = { key: ALL, label: "All scenarios", kind: "all", count: total, meta: "grouped by scenario, never ranked across them", recommended: false };
    const rest = orderScenarios(groups, order).map((g) => ({ key: g.key, label: g.short, kind: g.kind, count: g.count, meta: scenarioMeta(g), recommended: g.recommended }));
    // Typed "-" finds a real minus, "co2" finds CO₂.
    const fold = (t: string) => t.toLowerCase().replace(/−/g, "-").replace(/₂/g, "2");
    const q = fold(query.trim());
    const hit = (o: Option) => !q || fold(`${o.kind.replace("_", "-")} ${o.label} ${o.meta}`).includes(q);
    return [all, ...rest].filter((o) => o.key === ALL || hit(o));
  }, [groups, order, total, query]);

  const current = options.find((o) => o.key === value) ?? (value === ALL ? options[0] : null);
  const group = groups.find((g) => g.key === value);
  const shown = value === ALL ? { label: "All scenarios", kind: "all", count: total } : group ? { label: group.short, kind: group.kind, count: group.count } : { label: "Pick a scenario", kind: "all", count: 0 };

  useEffect(() => {
    if (!open) return;
    (searchable ? input.current : list.current)?.focus();
    const away = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open, searchable]);

  // Keep the active option in view, scrolling the list only (never the page).
  useEffect(() => {
    const box = list.current;
    const opt = open ? document.getElementById(`${uid}-opt-${active}`) : null;
    if (!box || !opt) return;
    const top = opt.offsetTop - box.offsetTop;
    if (top < box.scrollTop) box.scrollTop = top;
    else if (top + opt.offsetHeight > box.scrollTop + box.clientHeight) box.scrollTop = top + opt.offsetHeight - box.clientHeight;
  }, [active, open, uid]);

  const openMenu = () => {
    setQuery("");
    const i = Math.max(0, options.findIndex((o) => o.key === value));
    setActive(i);
    setOpen(true);
  };
  const close = (focus = true) => {
    setOpen(false);
    if (focus) button.current?.focus();
  };
  const pick = (o: Option | undefined) => {
    if (!o) return;
    onChange(o.key);
    close();
  };

  const onKey = (e: KeyboardEvent) => {
    const last = options.length - 1;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((i) => Math.min(last, i + 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => Math.max(0, i - 1));
        break;
      case "Home":
        if (e.target === list.current) {
          e.preventDefault();
          setActive(0);
        }
        break;
      case "End":
        if (e.target === list.current) {
          e.preventDefault();
          setActive(last);
        }
        break;
      case "Enter":
        e.preventDefault();
        pick(options[active]);
        break;
      case "Escape":
        e.preventDefault();
        close();
        break;
      case "Tab":
        close(false);
        break;
    }
  };

  return (
    <div className="lib-scn-select" ref={root}>
      <button
        ref={button}
        type="button"
        className={`lib-scn-button ta-btn${open ? " is-open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${uid}-list` : undefined}
        aria-label={`Scenario: ${group && value !== ALL ? group.label : shown.label}, ${shown.count} design${shown.count === 1 ? "" : "s"}. Change`}
        onClick={() => (open ? close() : openMenu())}
        onKeyDown={(e) => {
          if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
            e.preventDefault();
            openMenu();
          }
        }}
      >
        <span className="lib-scn-cap">Scenario</span>
        <span className={`lib-kind ${KIND_CLASS[shown.kind] ?? ""}`}>{shown.kind === "all" ? "All" : (KIND_WORD[shown.kind] ?? shown.kind)}</span>
        <strong className="lib-scn-label">{shown.label}</strong>
        <span className="lib-count">{shown.count}</span>
        <Chevron open={open} />
      </button>
      {open && (
        <div ref={menu} className="lib-scn-menu" onKeyDown={onKey}>
          <div className="lib-scn-menu-head">
            <span>
              {groups.length} scenario{groups.length === 1 ? "" : "s"}
            </span>
            <div className="lib-seg small" role="radiogroup" aria-label="Order">
              {(["newest", "oldest"] as const).map((o) => (
                <button key={o} type="button" role="radio" aria-checked={order === o} className={order === o ? "is-on" : ""} onClick={() => onOrder(o)}>
                  {o === "newest" ? "Newest first" : "Oldest first"}
                </button>
              ))}
            </div>
          </div>
          {searchable && (
            <input
              ref={input}
              type="search"
              className="lib-scn-filter"
              placeholder="Filter scenarios"
              aria-label="Filter scenarios"
              aria-controls={`${uid}-list`}
              aria-activedescendant={options[active] ? optId(active) : undefined}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
            />
          )}
          <ul
            ref={list}
            id={`${uid}-list`}
            role="listbox"
            tabIndex={-1}
            aria-label="Scenarios"
            aria-activedescendant={options[active] ? optId(active) : undefined}
            className="lib-scn-list"
          >
            {options.map((o, i) => {
              const on = o.key === current?.key;
              return (
                <li
                  key={o.key}
                  id={optId(i)}
                  role="option"
                  aria-selected={on}
                  className={`lib-scn-opt${i === active ? " is-active" : ""}${on ? " is-on" : ""}${o.key === ALL ? " is-all" : ""}`}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(o)}
                >
                  <span className="lib-scn-tick" aria-hidden="true">
                    {on && <Tick size={12} />}
                  </span>
                  <span className={`lib-kind ${KIND_CLASS[o.kind] ?? ""}`}>{o.kind === "all" ? "All" : (KIND_WORD[o.kind] ?? o.kind)}</span>
                  <span className="lib-scn-text">
                    <span className="lib-scn-name">
                      {o.label}
                      {o.recommended && <span className="lib-scn-rec">has the recommended design</span>}
                    </span>
                    <span className="lib-scn-meta">{o.meta}</span>
                  </span>
                  <span className="lib-count" aria-label={`${o.count} designs`}>
                    {o.count}
                  </span>
                </li>
              );
            })}
          </ul>
          {options.length === 1 && query && <p className="lib-scn-none">No scenario matches “{query}”.</p>}
        </div>
      )}
    </div>
  );
}
