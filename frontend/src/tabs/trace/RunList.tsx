// The conversation's runs as a strip of cards across the top of the page, newest first (it scrolls
// sideways when there are many): what was asked, when, how it ended, how long and how many tokens
// it took. Picking one shows it in full below. The arrow keys (and Home / End) move along the
// strip; only the run on screen is a tab stop.

import { useEffect, useRef, type KeyboardEvent } from "react";

import type { TraceRun } from "../../workbench";
import { deviceLabel, fmtInt, fmtSec, fmtWhen, outcomeLabel, outcomeTone, startedMs } from "./model";

interface Props {
  runs: TraceRun[];
  selected: string | null;
  onSelect: (runId: string) => void;
}

export function RunList({ runs, selected, onSelect }: Props) {
  const list = useRef<HTMLOListElement>(null);
  const at = Math.max(0, runs.findIndex((r) => r.runId === selected));

  // Keep the run on screen in view in the strip (a new run, or one picked with the keys); only
  // the strip scrolls, never the page.
  useEffect(() => {
    const ol = list.current;
    const el = ol?.querySelector<HTMLElement>('[aria-current="true"]');
    if (!ol || !el) return;
    const a = ol.getBoundingClientRect();
    const b = el.getBoundingClientRect();
    if (b.left < a.left) ol.scrollLeft -= a.left - b.left + 8;
    else if (b.right > a.right) ol.scrollLeft += b.right - a.right + 8;
  }, [selected]);

  const onKey = (e: KeyboardEvent<HTMLOListElement>) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    const to = e.key === "Home" ? 0 : e.key === "End" ? runs.length - 1 : step != null ? Math.min(runs.length - 1, Math.max(0, at + step)) : null;
    if (to == null) return;
    e.preventDefault();
    if (to === at) return;
    onSelect(runs[to].runId);
    list.current?.querySelectorAll<HTMLButtonElement>(".tr-run")[to]?.focus();
  };

  return (
    <nav className="tr-runs" aria-label="Runs in this chat">
      <div className="tr-runs-head">
        <h2>Runs</h2>
        <span className="tr-muted">
          {runs.length === 1 ? "1 message" : `${runs.length} messages`}, newest first
          {runs.length > 1 && <span className="tr-keys-hint"> · ← → to step through them</span>}
        </span>
      </div>
      <ol ref={list} className="tr-run-list" onKeyDown={onKey}>
        {runs.map((r, i) => {
          const on = i === at;
          const ms = startedMs(r.started);
          const tokens = (r.tokens?.prompt ?? 0) + (r.tokens?.output ?? 0);
          return (
            <li key={r.runId}>
              <button
                type="button"
                className={`tr-run ta-btn${on ? " is-on" : ""}`}
                aria-current={on ? "true" : undefined}
                tabIndex={on ? 0 : -1}
                onClick={() => onSelect(r.runId)}
              >
                <span className="tr-run-top">
                  <span className="tr-run-n" aria-hidden="true">
                    {runs.length - i}
                  </span>
                  <time dateTime={ms ? new Date(ms).toISOString() : undefined} title={ms ? new Date(ms).toLocaleString("en-GB") : undefined}>
                    {fmtWhen(ms)}
                  </time>
                  <span className={`tag tag-${outcomeTone(r.outcome)}`}>{outcomeLabel(r.outcome)}</span>
                  <span className="tr-run-sec">{fmtSec(r.seconds)}</span>
                </span>
                <span className="tr-run-msg">{r.message || <em>No message recorded (the run didn't finish).</em>}</span>
                <span className="tr-run-meta">
                  <span>{r.mode === "reasoning" ? "reasoning" : "fast"}</span>
                  <span aria-hidden="true">·</span>
                  <span>{deviceLabel(r)}</span>
                  <span aria-hidden="true">·</span>
                  <span>{fmtInt(tokens)} tokens</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
