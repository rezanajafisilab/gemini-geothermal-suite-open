// "Designs in this chat" (2 Nov): a strip at the top of the chat that keeps the conversation's
// design attempts in view. Folded, it counts the runs and designs and shows the shortlist and the
// latest picks; open, it lists each run (newest first) with the request that started it (a click
// goes to that message) and its picks, then the what-ifs and the user's designs. Each design:
// open it in the Design tab, ask about it (it becomes the composer's @ chip), star it.

import { useEffect, useRef, useState } from "react";

import type { Turn } from "../agent/types";
import { itemText, type DesignItem } from "../workbench/designList";
import { go } from "../workbench/route";
import { workbench } from "../workbench/store";
import type { Attempt } from "../workbench/types";
import { Chevron } from "./Icons";

interface Props {
  items: DesignItem[];
  attempts: Attempt[];
  turns: Turn[];
  onAsk: (d: DesignItem) => void;
}

const fmt = (v: number | null) => (v == null ? "" : `${v.toFixed(1)} €/MWh`);

/** The chat's message that started a run (its first 200 characters were kept with the run). */
function turnOf(a: Attempt, turns: Turn[]): Turn | undefined {
  const m = (a.message ?? "").trim();
  if (!m) return undefined;
  return [...turns].reverse().find((t) => t.message.trim().startsWith(m.slice(0, 120)));
}

function Row({ d, onAsk }: { d: DesignItem; onAsk: (d: DesignItem) => void }) {
  const open = async () => {
    const ok = d.inTabs || (await workbench.openDesign(d.id)).ok;
    if (ok) go("design", d.id);
  };
  return (
    <li className="ds-row">
      <span className="uid-chip small">{d.uid}</span>
      <span className="ds-label" title={`${itemText(d)} · ${d.code} · ${d.name}`}>
        {d.label}
        <span className="ds-sub">{d.code}</span>
      </span>
      <span className="ds-num">{fmt(d.lcoe)}</span>
      {d.recommended && <span className="tag tag-ok">chosen</span>}
      <span className="ds-acts">
        <button type="button" className="link-btn" onClick={() => void open()}>
          Open
        </button>
        <button type="button" className="link-btn" onClick={() => onAsk(d)} title={`Ask about ${d.uid}: it becomes the message's @ chip`}>
          Ask
        </button>
        <button
          type="button"
          className={`ds-star${d.starred ? " on" : ""}`}
          aria-pressed={d.starred}
          aria-label={d.starred ? `Take ${d.uid} off the shortlist` : `Star ${d.uid}`}
          onClick={() => void workbench.setMeta(d.id, { starred: !d.starred })}
        >
          {d.starred ? "★" : "☆"}
        </button>
      </span>
    </li>
  );
}

export function DesignsStrip({ items, attempts, turns, onAsk }: Props) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLElement>(null);
  useEffect(() => {
    // Open, the list is a panel over the chat: a click elsewhere or Escape closes it.
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  const runs = [...attempts].sort((a, b) => b.n - a.n);
  const latest = runs[0];
  const shortlist = items.filter((d) => d.starred);
  const picks = items.filter((d) => d.recommended || (d.origin === "agent" && d.picks.length > 0 && latest && d.run?.id === latest.id));
  const chips = [...new Map([...shortlist, ...picks].map((d) => [d.id, d])).values()].slice(0, 3);
  const whatIfs = items.filter((d) => d.origin === "what_if");
  const yours = items.filter((d) => d.origin === "user");
  const counted = items.filter((d) => d.origin !== "agent" || d.picks.length > 0 || d.recommended || d.starred).length;

  return (
    <section ref={box} className={`ds card${open ? " open" : ""}`} aria-label="Designs in this chat">
      <div className="ds-bar">
        <button type="button" className="ds-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          <strong>Designs in this chat</strong>
          <span className="ds-count">
            {runs.length} {runs.length === 1 ? "run" : "runs"} · {counted} {counted === 1 ? "design" : "designs"}
            {whatIfs.length ? ` · ${whatIfs.length} what-if${whatIfs.length === 1 ? "" : "s"}` : ""}
          </span>
          <Chevron open={open} />
        </button>
        {!open && (
          <span className="ds-chips">
            {chips.map((d) => (
              <button key={d.id} type="button" className="ds-chip" title={`Ask about ${itemText(d)}`} onClick={() => onAsk(d)}>
                {d.starred && <span className="wb-star-on">★</span>}
                <span className="uid-chip small">{d.uid}</span>
                <span className="ds-chip-text">{d.label}</span>
              </button>
            ))}
          </span>
        )}
      </div>
      {open && (
        <div className="ds-body">
          {shortlist.length > 0 && (
            <div className="ds-group">
              <h3>Your shortlist</h3>
              <ul>
                {shortlist.map((d) => (
                  <Row key={d.id} d={d} onAsk={onAsk} />
                ))}
              </ul>
            </div>
          )}
          {runs.map((a) => {
            const mine = items.filter((d) => d.run?.id === a.id && d.origin === "agent" && (d.picks.length > 0 || d.recommended));
            const rest = items.filter((d) => d.run?.id === a.id && d.origin === "agent").length - mine.length;
            const turn = turnOf(a, turns);
            return (
              <div key={a.id} className="ds-group">
                <h3>
                  {a.name ?? `Run ${a.letter ?? a.n}`}
                  {turn && (
                    <button
                      type="button"
                      className="link-btn ds-jump"
                      title="Go to the message that started this run"
                      onClick={() => document.querySelector(`[data-turn="${CSS.escape(turn.id)}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" })}
                    >
                      “{turn.message.length > 60 ? `${turn.message.slice(0, 59)}…` : turn.message}”
                    </button>
                  )}
                </h3>
                {mine.length > 0 ? (
                  <ul>
                    {mine.map((d) => (
                      <Row key={d.id} d={d} onAsk={onAsk} />
                    ))}
                  </ul>
                ) : (
                  <p className="ds-none">No design met every cap in this run.</p>
                )}
                {rest > 0 && (
                  <button type="button" className="link-btn ds-more" onClick={() => go("compare")}>
                    {rest} more designs of this run in Compare →
                  </button>
                )}
              </div>
            );
          })}
          {whatIfs.length > 0 && (
            <div className="ds-group">
              <h3>What-ifs</h3>
              <ul>
                {whatIfs.map((d) => (
                  <Row key={d.id} d={d} onAsk={onAsk} />
                ))}
              </ul>
            </div>
          )}
          {yours.length > 0 && (
            <div className="ds-group">
              <h3>Your designs</h3>
              <ul>
                {yours.map((d) => (
                  <Row key={d.id} d={d} onAsk={onAsk} />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
