// The command palette (3 Nov, shadcn's Command): ⌘K or Ctrl+K anywhere opens a box to find a
// screen, a design of this chat or an action, typed and picked with the keys. Nothing it lists is
// new: each row does what its button elsewhere does.

import { useEffect, useMemo, useRef, useState } from "react";

import { EXPORTS, previewExport } from "../workbench/exports";
import { designItems } from "../workbench/designList";
import { TAB_GROUPS, TAB_META, go, type TabId } from "../workbench/route";
import { useWorkbench } from "../workbench/store";
import { Modal } from "./Modal";

interface Item {
  id: string;
  group: string;
  label: string;
  hint?: string;
  keys?: string;
  run: () => void;
}

export function CommandPalette({ onNewChat }: { onNewChat: () => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const wb = useWorkbench();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
        setQuery("");
        setActive(0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (open) setTimeout(() => input.current?.focus(), 0);
  }, [open]);

  const items = useMemo(() => {
    const out: Item[] = [];
    const design = wb.selected;
    for (const g of TAB_GROUPS)
      for (const t of g.tabs)
        out.push({ id: `tab-${t}`, group: "Screens", label: TAB_META[t].label, hint: TAB_META[t].hint, run: () => go(t as TabId, TAB_META[t].scope === "design" ? (design?.id ?? null) : null) });
    out.push({ id: "new-chat", group: "Actions", label: "New chat", hint: "Start a new conversation in this project", run: onNewChat });
    if (design && wb.threadId && !wb.fixture)
      for (const x of EXPORTS)
        out.push({ id: `export-${x.kind}`, group: "Actions", label: `${x.label} of ${design.uid || design.code}`, hint: `${x.hint} · a preview first`, run: () => previewExport(x.kind, wb.threadId!, design.id) });
    for (const d of designItems(wb.workbench).slice(0, 200))
      out.push({
        id: `design-${d.id}`,
        group: "Designs",
        label: `${d.uid} · ${d.label}`,
        hint: `${d.code}${d.lcoe != null ? ` · ${d.lcoe.toFixed(1)} €/MWh` : ""}`,
        run: async () => {
          const id = d.inTabs ? d.id : (await wb.openDesign(d.id)).ok ? d.id : null;
          if (id) go("design", id);
        },
      });
    return out;
  }, [wb, onNewChat]);

  const shown = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    return items.filter((i) => words.every((w) => `${i.label} ${i.hint ?? ""} ${i.group}`.toLowerCase().includes(w))).slice(0, 40);
  }, [items, query]);

  if (!open) return null;
  const pick = (i: Item | undefined) => {
    if (!i) return;
    setOpen(false);
    i.run();
  };
  let group = "";
  return (
    <Modal label="Find a screen, a design or an action" onClose={() => setOpen(false)} className="cmdk">
      <div className="cmdk-find">
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M10.5 10.5 14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <input
          ref={input}
          value={query}
          placeholder="Find a screen, a design (A1, cheapest, 2D-HP…) or an action"
          aria-label="Find"
          role="combobox"
          aria-expanded="true"
          aria-controls="cmdk-list"
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") (e.preventDefault(), setActive((a) => Math.min(shown.length - 1, a + 1)));
            else if (e.key === "ArrowUp") (e.preventDefault(), setActive((a) => Math.max(0, a - 1)));
            else if (e.key === "Enter") (e.preventDefault(), pick(shown[active]));
          }}
        />
        <kbd>esc</kbd>
      </div>
      <ul id="cmdk-list" className="cmdk-list" role="listbox" aria-label="Results">
        {shown.length === 0 && <li className="cmdk-empty">Nothing matches “{query}”.</li>}
        {shown.map((i, k) => {
          const head = i.group !== group ? (group = i.group) : null;
          return (
            <li key={i.id} role="presentation">
              {head && <span className="cmdk-group">{head}</span>}
              <button type="button" role="option" aria-selected={k === active} className={`cmdk-item${k === active ? " on" : ""}`} onMouseMove={() => k !== active && setActive(k)} onClick={() => pick(i)}>
                <span className="cmdk-label">{i.label}</span>
                {i.hint && <span className="cmdk-hint">{i.hint}</span>}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="cmdk-foot">
        <kbd>↑</kbd>
        <kbd>↓</kbd> move <kbd>↵</kbd> open · <kbd>⌘K</kbd> or <kbd>Ctrl K</kbd> anywhere
      </p>
    </Modal>
  );
}
