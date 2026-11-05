// One run in full: what was asked and how it ended (the reply as the chat shows it, Markdown), the
// totals, the steps on a time scale, the model calls beside their tokens (one row height, totals
// level at the bottom), and every tool call with its arguments and result.

import { useState, type ReactNode } from "react";

import { Chevron, DoneIcon, FailIcon } from "../../components/Icons";
import { Markdown } from "../../components/Markdown";
import type { TraceRun } from "../../workbench";
import { JsonView } from "./JsonView";
import { StepTimeline } from "./StepTimeline";
import { argSummary, deviceLabel, fmtInt, fmtSec, outcomeLabel, outcomeTone, resultFlags, runTotals, startedMs, toolGroups, type ToolCall } from "./model";

interface Props {
  run: TraceRun;
  /** 1 for the chat's first message. */
  number: number;
  kind: string | null;
  onKind: (kind: string | null) => void;
}

/** The reply is read here, not worked with: no number links back to a step, no source cards. */
const noop = () => {};
const never = () => false;

/** Prompt and output tokens: the two series of the token bars (prompt teal, output amber). */
const PROMPT = "#11949F";
const OUTPUT = "#D9962B";

export function RunDetail({ run, number, kind, onKind }: Props) {
  const t = runTotals(run);
  const ms = startedMs(run.started);
  return (
    <div className="tr-detail" aria-label={`Run ${number}`}>
      <section className="tr-card tr-ask" aria-label="The message">
        <div className="tr-ask-meta">
          <span className="tr-muted">Message {number}</span>
          <span className={`tag tag-${outcomeTone(run.outcome)}`}>{outcomeLabel(run.outcome)}</span>
          <span className="tag tag-grey">{run.mode === "reasoning" ? "reasoning mode" : "fast mode"}</span>
          <span className="tag tag-grey">{deviceLabel(run)}</span>
          {ms > 0 && <time className="tr-muted" dateTime={new Date(ms).toISOString()}>{new Date(ms).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time>}
          <code className="tr-runid" title="Run id">
            {run.runId}
          </code>
        </div>
        <p className="tr-bubble">{run.message || "No message recorded: the run didn't finish."}</p>
        {run.answer && (
          <div className="tr-reply">
            <span className="tr-muted">Reply{run.answer_model ? ` · ${run.answer_model}` : ""}</span>
            <Markdown text={run.answer} className="tr-md" cites={0} onCite={noop} hasSource={never} onSource={noop} />
          </div>
        )}
      </section>

      <section className="tr-tiles" aria-label="Totals">
        <Tile label="Model calls" value={String(t.calls)} sub={t.models.length ? t.models.join(", ") : "none: rules and tools only"} warn={t.failedCalls ? `${t.failedCalls} failed` : undefined} />
        <Tile label="Tokens" value={fmtInt(t.tokens)} sub={`${fmtInt(t.prompt)} in · ${fmtInt(t.output)} out`}>
          <SplitBar parts={[t.prompt, t.output]} colors={[PROMPT, OUTPUT]} label={`${fmtInt(t.prompt)} prompt tokens, ${fmtInt(t.output)} output tokens`} />
        </Tile>
        <Tile label="Time" value={fmtSec(t.seconds)} sub={t.seconds > 0 ? `${fmtSec(t.modelSeconds)} in model calls (${Math.round(Math.min(1, t.modelSeconds / t.seconds) * 100)}%)` : "not recorded"}>
          <SplitBar parts={[Math.min(t.modelSeconds, t.seconds), Math.max(0, t.seconds - t.modelSeconds)]} colors={[PROMPT, "#C9D2D4"]} label={`${fmtSec(t.modelSeconds)} in model calls of ${fmtSec(t.seconds)}`} />
        </Tile>
        <Tile label="Tool calls" value={String(t.toolCalls)} sub={t.toolCalls ? (t.cached ? `${t.cached} from cache` : "none from cache") : "no tools called"} />
      </section>

      <StepTimeline key={run.runId} run={run} kind={kind} onKind={onKind} />

      <div className="tr-two">
        <ModelCalls run={run} />
        <TokensByCall totals={t} />
      </div>

      <ToolCalls key={`tools-${run.runId}`} run={run} />
    </div>
  );
}

function Tile({ label, value, sub, warn, children }: { label: string; value: string; sub: string; warn?: string; children?: ReactNode }) {
  return (
    <div className="tr-tile">
      <span className="tr-tile-label">{label}</span>
      <span className="tr-tile-value">
        <strong>{value}</strong>
        {warn && <span className="tag tag-red">{warn}</span>}
      </span>
      {children}
      <span className="tr-tile-sub">{sub}</span>
    </div>
  );
}

/** A thin bar split into parts (a 2px gap between them), for a tile. */
function SplitBar({ parts, colors, label }: { parts: number[]; colors: string[]; label: string }) {
  const sum = parts.reduce((a, b) => a + b, 0);
  if (!(sum > 0)) return null;
  return (
    <span className="tr-split" role="img" aria-label={label}>
      {parts.map((p, i) =>
        p > 0 ? <span key={i} style={{ flexGrow: p, background: colors[i] }} /> : null,
      )}
    </span>
  );
}

function ModelCalls({ run }: { run: TraceRun }) {
  const t = runTotals(run);
  return (
    <section className="tr-card" aria-labelledby="tr-calls-h">
      <div className="tr-card-head">
        <h2 id="tr-calls-h">Model calls</h2>
        <span className="tr-muted">Every call to a local language model, in order</span>
      </div>
      {run.calls.length === 0 ? (
        <p className="tr-none">No model was called: rules and tools answered this one.</p>
      ) : (
        <div className="tr-scroll">
          <table className="tr-table">
            <thead>
              <tr>
                <th scope="col">Purpose</th>
                <th scope="col">Model</th>
                <th scope="col" className="is-num">
                  Prompt
                </th>
                <th scope="col" className="is-num">
                  Output
                </th>
                <th scope="col" className="is-num">
                  Time
                </th>
                <th scope="col" className="ok">
                  <span className="sr-only">Answered</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {run.calls.map((c, i) => (
                <tr key={i}>
                  <td>{c.purpose || "call"}</td>
                  <td>
                    <code className="tr-model">{c.model || "–"}</code>
                  </td>
                  <td className="is-num">{fmtInt(Number(c.prompt_tokens) || 0)}</td>
                  <td className="is-num">{fmtInt(Number(c.output_tokens) || 0)}</td>
                  <td className="is-num">{fmtSec(Number(c.seconds) || 0)}</td>
                  <td className="ok">
                    {c.ok === false ? (
                      <span title="The model didn't answer">
                        <FailIcon size={18} />
                        <span className="sr-only">no answer</span>
                      </span>
                    ) : (
                      <span title="Answered">
                        <DoneIcon size={18} />
                        <span className="sr-only">answered</span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            {run.calls.length > 1 && (
              <tfoot>
                <tr>
                  <th scope="row" colSpan={2}>
                    {run.calls.length} calls
                  </th>
                  <td className="is-num">{fmtInt(t.prompt)}</td>
                  <td className="is-num">{fmtInt(t.output)}</td>
                  <td className="is-num">{fmtSec(t.modelSeconds)}</td>
                  <td />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </section>
  );
}

/** Tokens per call purpose: one bar each, prompt then output, on one scale. */
function TokensByCall({ totals }: { totals: ReturnType<typeof runTotals> }) {
  const rows = totals.byPurpose;
  const max = Math.max(1, ...rows.map((r) => r.total));
  return (
    <section className="tr-card" aria-labelledby="tr-tok-h">
      <div className="tr-card-head">
        <h2 id="tr-tok-h">Tokens by call</h2>
        <span className="tr-legend" aria-hidden="true">
          <span>
            <i style={{ background: PROMPT }} />
            prompt
          </span>
          <span>
            <i style={{ background: OUTPUT }} />
            output
          </span>
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="tr-none">No tokens: no model was called.</p>
      ) : (
        <>
        <ul className="tr-tok">
          {rows.map((r) => (
            <li key={r.purpose} className="tr-tok-row">
              <span className="tr-tok-name">
                {r.purpose}
                {r.calls > 1 && <span className="tr-muted"> ×{r.calls}</span>}
              </span>
              <span className="tr-tok-track" role="img" aria-label={`${r.purpose}: ${fmtInt(r.prompt)} prompt and ${fmtInt(r.output)} output tokens`}>
                <span className="tr-tok-bar" style={{ width: `${(r.total / max) * 100}%` }}>
                  {r.prompt > 0 && <span style={{ flexGrow: r.prompt, background: PROMPT }} />}
                  {r.output > 0 && <span style={{ flexGrow: r.output, background: OUTPUT }} />}
                </span>
              </span>
              <span className="tr-tok-n">
                <strong>{fmtInt(r.total)}</strong>
                <span className="tr-muted">
                  {fmtInt(r.prompt)} + {fmtInt(r.output)}
                </span>
              </span>
            </li>
          ))}
        </ul>
        <div className="tr-tok-total">
          <span className="tr-tok-name">{totals.calls === 1 ? "1 call" : `${totals.calls} calls`}</span>
          <span className="tr-tok-track" role="img" aria-label={`In all ${fmtInt(totals.prompt)} prompt and ${fmtInt(totals.output)} output tokens`}>
            <span className="tr-tok-bar is-total">
              {totals.prompt > 0 && <span style={{ flexGrow: totals.prompt, background: PROMPT }} />}
              {totals.output > 0 && <span style={{ flexGrow: totals.output, background: OUTPUT }} />}
            </span>
          </span>
          <span className="tr-tok-n">
            <strong>{fmtInt(totals.prompt + totals.output)}</strong>
            <span className="tr-muted">
              {fmtInt(totals.prompt)} + {fmtInt(totals.output)}
            </span>
          </span>
        </div>
        </>
      )}
    </section>
  );
}

function ToolCalls({ run }: { run: TraceRun }) {
  const groups = toolGroups(run);
  const [open, setOpen] = useState<Set<number>>(new Set());
  const all = run.tools.length > 0 && open.size === run.tools.length;
  const toggle = (i: number) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });
  return (
    <section className="tr-card" aria-labelledby="tr-tools-h">
      <div className="tr-card-head">
        <h2 id="tr-tools-h">Tool calls</h2>
        <span className="tr-muted">The physics, cost and search tools with their arguments and results</span>
        {run.tools.length > 1 && (
          <button type="button" className="link-btn tr-head-link" onClick={() => setOpen(all ? new Set() : new Set(run.tools.map((_, i) => i)))}>
            {all ? "Fold all" : "Open all"}
          </button>
        )}
      </div>
      {run.tools.length === 0 ? (
        <p className="tr-none">No tool was called in this run.</p>
      ) : (
        <div className="tr-tool-groups">
          {groups.map((g) => (
            <div key={g.title} className="tr-tool-group">
              <h3>
                {g.title}
                <span className="tr-muted"> · {g.calls.length} call{g.calls.length === 1 ? "" : "s"}</span>
              </h3>
              <ul className="tr-tool-list">
                {g.calls.map(({ call, index }) => (
                  <ToolRow key={index} call={call} open={open.has(index)} onToggle={() => toggle(index)} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ToolRow({ call, open, onToggle }: { call: ToolCall; open: boolean; onToggle: () => void }) {
  const flags = resultFlags(call.result);
  const args = argSummary(call.args);
  return (
    <li className={`tr-tool${open ? " is-open" : ""}`}>
      <button type="button" className="tr-tool-btn" aria-expanded={open} onClick={onToggle}>
        <code className="tr-tool-sig">
          <b>{call.name}</b>({args})
        </code>
        <span className="tr-tool-flags">
          {flags.map((f) => (
            <span key={f.text} className={`tag tag-${f.tone}`}>
              {f.text}
            </span>
          ))}
          <Chevron open={open} />
        </span>
      </button>
      {open && (
        <div className="tr-tool-body ta-rise">
          <JsonView label="Arguments" value={call.args} openDepth={1} />
          <JsonView label="Result" value={call.result} openDepth={2} />
        </div>
      )}
    </li>
  );
}
