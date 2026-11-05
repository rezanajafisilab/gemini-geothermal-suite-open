// Picking designs for a message (2 Nov): "@" in the composer opens the conversation's designs,
// filtered as you type (handle, words, code, run); a pick becomes a chip above the input and goes
// with the message, so the agent answers about those designs, not about whichever is current.
// Two or more picked: "Compare them" opens the Compare tab with them side by side. With nothing
// picked, a line says which design a question is about, and how to pick another.

import { useEffect, useRef } from "react";

import { designSections, itemText, type DesignItem } from "../workbench/designList";

/** The "@word" being typed at the caret: where it starts and what follows the @, or null. */
export function mentionAt(text: string, caret: number): { start: number; query: string } | null {
  const before = text.slice(0, caret);
  const m = /(^|\s)@([\w.\-·]{0,40})$/.exec(before);
  return m ? { start: before.length - m[2].length - 1, query: m[2] } : null;
}

/** The text with the "@word" at the caret taken out (the pick shows as a chip instead). */
export function withoutMention(text: string, at: { start: number; query: string }): string {
  const end = at.start + 1 + at.query.length;
  return (text.slice(0, at.start) + text.slice(end)).replace(/\s{2,}/g, " ").replace(/^\s+/, "");
}

export function MentionList({ items, query, active, onActive, onPick, id }: { items: DesignItem[]; query: string; active: number; onActive: (i: number) => void; onPick: (d: DesignItem) => void; id: string }) {
  const sections = designSections(items, query, 30);
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    document.getElementById(`${id}-m-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, id]);
  let n = -1;
  return (
    <div className="mention-pop ta-rise" role="presentation">
      <ul ref={list} id={`${id}-mentions`} className="mention-list" role="listbox" aria-label="Designs to ask about">
        {sections.length === 0 && <li className="mention-empty">No design matches “{query}”.</li>}
        {sections.map((sec) => (
          <li key={sec.key} role="presentation">
            <span className="mention-cap">{sec.title}</span>
            <ul role="group" aria-label={sec.title}>
              {sec.items.map((d) => {
                n += 1;
                const i = n;
                return (
                  <li
                    key={d.id}
                    id={`${id}-m-${i}`}
                    role="option"
                    aria-selected={i === active}
                    className={`mention-opt${i === active ? " active" : ""}`}
                    onMouseMove={() => i !== active && onActive(i)}
                    // Mouse down, not click: the input keeps its focus.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      onPick(d);
                    }}
                  >
                    <span className="uid-chip small">{d.uid}</span>
                    <span className="mention-text">
                      {d.starred && <span className="wb-star-on">★ </span>}
                      {d.label}
                      <span className="mention-sub">
                        {d.code}
                        {d.lcoe != null ? ` · ${d.lcoe.toFixed(1)} €/MWh` : ""}
                        {d.recommended ? " · chosen" : ""}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
      <div className="mention-foot" aria-hidden="true">
        <kbd>↑</kbd>
        <kbd>↓</kbd> move <kbd>↵</kbd> pick <kbd>esc</kbd> close
      </div>
    </div>
  );
}

/** The flat order of the list's options (what ↑ ↓ step through). */
export const mentionOrder = (items: DesignItem[], query: string): DesignItem[] => designSections(items, query, 30).flatMap((s) => s.items);

export function PickedChips({ picked, onRemove, onCompare, about }: { picked: DesignItem[]; onRemove: (id: string) => void; onCompare: () => void; about: DesignItem | null }) {
  if (!picked.length)
    // No design by default (3 Nov): @ one, or the agent asks which a question is about.
    return about ? (
      <p className="about-line">
        Type <kbd className="about-at">@</kbd> to say which design a question is about; without it, I will ask
      </p>
    ) : null;
  return (
    <div className="picked-row" role="group" aria-label="Designs this message is about">
      <span className="picked-cap">About</span>
      {picked.map((d) => (
        <span key={d.id} className="picked-chip" title={`${itemText(d)} · ${d.code}`}>
          <span className="uid-chip small">{d.uid}</span>
          <span className="picked-text">{d.label}</span>
          <button type="button" className="picked-x" aria-label={`Not about ${d.uid}`} onClick={() => onRemove(d.id)}>
            ×
          </button>
        </span>
      ))}
      {picked.length >= 2 && (
        <button type="button" className="link-btn picked-compare" onClick={onCompare}>
          Compare them →
        </button>
      )}
    </div>
  );
}
