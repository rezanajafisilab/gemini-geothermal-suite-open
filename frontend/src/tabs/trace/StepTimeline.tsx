// A run's steps in order on one time scale: one row per step with its kind, the model that ran
// it, a bar from where it started to where it ended, its time and the facts it reported. The
// kind chips above filter the rows (the scale stays, so bars compare across filters). A row
// opens to show its call and everything its metadata says.

import { useState } from "react";

import { menuProps } from "../../menu";
import type { TraceRun } from "../../workbench";
import { JsonView } from "./JsonView";
import { fmtSec, kindCounts, kindInfo, stepFacts, stepModel, timeline } from "./model";

interface Props {
  run: TraceRun;
  /** The kind shown, or null for all. */
  kind: string | null;
  onKind: (kind: string | null) => void;
}

export function StepTimeline({ run, kind, onKind }: Props) {
  const tl = timeline(run.steps, run.seconds);
  const kinds = kindCounts(run.steps);
  const rows = kind ? tl.rows.filter((r) => (r.step.kind || "other") === kind) : tl.rows;
  const [open, setOpen] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });

  return (
    <section className="tr-card" aria-labelledby="tr-steps-h">
      <div className="tr-card-head">
        <h2 id="tr-steps-h">Steps</h2>
        <span className="tr-muted">
          {run.steps.length} step{run.steps.length === 1 ? "" : "s"} one after another, {fmtSec(tl.total)} in all. Select a step for its details.
        </span>
      </div>
      {kinds.length > 1 && (
        <div className="tr-kinds" role="group" aria-label="Show steps of one kind">
          <button type="button" className="tr-kind ta-btn" aria-pressed={kind === null} onClick={() => onKind(null)}>
            All <b>{run.steps.length}</b>
          </button>
          {kinds.map(({ info, count }) => (
            <button key={info.key} type="button" className="tr-kind ta-btn" aria-pressed={kind === info.key} onClick={() => onKind(kind === info.key ? null : info.key)}>
              <span className="tr-swatch" style={{ background: info.color }} aria-hidden="true" />
              {info.label} <b>{count}</b>
            </button>
          ))}
        </div>
      )}
      {run.steps.length === 0 ? (
        <p className="tr-none">This run recorded no steps.</p>
      ) : (
        <div className="tr-tl">
          <div className="tr-tl-axis" aria-hidden="true">
            <span />
            <span className="tr-tl-ticks">
              {tl.ticks.map((t) => (
                <span key={t.value} style={{ left: `${t.left}%` }} className={t.left > 96 ? "end" : t.left < 2 ? "start" : undefined}>
                  {t.label}
                </span>
              ))}
            </span>
            <span className="tr-tl-unit">time</span>
          </div>
          <ol className="tr-steps">
            {rows.map((r) => {
              const s = r.step;
              const info = kindInfo(s.kind);
              const model = stepModel(s);
              const facts = stepFacts(s);
              const isOpen = open.has(r.index);
              const frac = tl.total > 0 ? (Number(s.seconds) || 0) / tl.total : 0;
              const share = frac > 0 && frac < 0.005 ? "<1%" : `${Math.round(frac * 100)}%`;
              const metaKeys = Object.keys(s.meta ?? {}).length;
              const end = r.start + (Number(s.seconds) || 0);
              return (
                <li
                  key={`${r.index}-${s.name}`}
                  className={`tr-step${isOpen ? " is-open" : ""}`}
                  {...menuProps(() => ({
                    kind: "step",
                    label: s.label || s.name,
                    code: s.code,
                    json: JSON.stringify({ name: s.name, kind: s.kind, seconds: s.seconds, code: s.code, meta: s.meta }, null, 2),
                    details: { open: isOpen, toggle: () => toggle(r.index) },
                  }))}
                >
                  <button type="button" className="tr-step-btn" aria-expanded={isOpen} onClick={() => toggle(r.index)}>
                    <span className="tr-step-main">
                      <span className="tr-step-title">
                        <span className="tr-step-i" aria-hidden="true">
                          {r.index + 1}
                        </span>
                        <span className="tr-step-label">{s.label || s.name}</span>
                      </span>
                      <span className="tr-step-tags">
                        <span className="tr-kind-chip">
                          <span className="tr-swatch" style={{ background: info.color }} aria-hidden="true" />
                          {info.label}
                        </span>
                        {model && <span className="tr-model">{model}</span>}
                        {s.code && <code className="tr-code">{s.code}</code>}
                      </span>
                      {facts.length > 0 && (
                        <span className="tr-facts">
                          {facts.map((f) => (
                            <span key={f.text} className={`tag tag-${f.tone}`}>
                              {f.text}
                            </span>
                          ))}
                        </span>
                      )}
                    </span>
                    <span className="tr-track" aria-hidden="true">
                      {tl.ticks.map((t) => (
                        <span key={t.value} className="tr-grid" style={{ left: `${t.left}%` }} />
                      ))}
                      <span
                        className={`tr-bar${s.kind === "ask" ? " is-dot" : ""}`}
                        style={{ left: `${r.left}%`, width: s.kind === "ask" ? undefined : `${r.width}%`, background: info.color }}
                      />
                      <span className="tr-tip" style={{ left: `${Math.min(80, Math.max(20, r.left + r.width / 2))}%` }}>
                        {fmtSec(r.start)} → {fmtSec(end)} · {share} of the run
                      </span>
                    </span>
                    <span className="tr-step-sec">{fmtSec(Number(s.seconds) || 0)}</span>
                  </button>
                  {isOpen && (
                    <div className="tr-step-detail ta-rise">
                      <p className="tr-step-when">
                        Started at {fmtSec(r.start)}, ended at {fmtSec(end)}: {share} of the run. Step <code>{s.name}</code>, kind <code>{s.kind || "none"}</code>.
                      </p>
                      {s.code && <pre className="tr-pre">{s.code}</pre>}
                      {metaKeys > 0 ? <JsonView label="What the step reported" value={s.meta} openDepth={1} /> : <p className="tr-muted">The step reported nothing else.</p>}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}
