// Automatic model generation: the offer (a spec for a missing component model), the attempts
// (the sandbox's self-correction loop), the approval (code, test table, checks) and, once
// approved, the model's operating points. Nothing runs without the user's two yeses.

import { useMemo, useState, type FormEvent, type ReactNode } from "react";

import type { Ask, GenAttempt, Generation, ModelResult, OfferDetail } from "../agent/types";
import { DoneIcon, FailIcon, Tick } from "./Icons";
import { fmtNum } from "./ResultCard";

const article = (word: string) => (/^[aeiou]/i.test(word) ? "an" : "a");

/** "drive_temp_c [°C]" -> ["drive_temp_c", "°C"]. */
export function splitQuantity(q: string): [string, string] {
  const m = q.match(/^(.*?)\s*\[(.*)\]$/);
  return m ? [m[1], m[2] === "-" ? "" : m[2]] : [q, ""];
}

/** "drive_temp_c" -> "drive temp" (the unit is shown apart). */
export function quantityLabel(name: string): string {
  return name.replace(/_(c|mw|mwh|kw|gwh|m|k|pct|eur)$/i, "").replace(/_/g, " ");
}

function unitsOf(offer?: OfferDetail): Record<string, string> {
  const out: Record<string, string> = {};
  for (const q of [...(offer?.inputs ?? []), ...(offer?.outputs ?? [])]) {
    const [name, unit] = splitQuantity(q);
    out[name] = unit;
  }
  return out;
}

function ModelIcon({ color = "#0A6F7C" }: { color?: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 1.8 13.4 4.9v6.2L8 14.2 2.6 11.1V4.9zM2.6 4.9 8 8l5.4-3.1M8 8v6.2" fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

// ------------------------------------------------------------------ offer

export function OfferCard({ ask, active, onSubmit }: { ask: Ask; active: boolean; onSubmit: (answers: Record<string, string>) => void }) {
  const q = ask.value.questions[0];
  const offer = ask.value.details as OfferDetail | undefined;
  const [yes, no] = q?.options ?? ["Yes", "No"];
  const title = offer ? `Write ${article(offer.title)} ${offer.title.toLowerCase()} model?` : q?.label;
  const send = (choice: string) => (e?: FormEvent) => {
    e?.preventDefault();
    onSubmit({ [q.id]: choice });
  };
  return (
    <section className={`card gen ta-rise${active ? "" : " gen-done"}`} aria-label="Offer to write a model">
      <div className="gen-head">
        <span className="icon-box" style={{ background: "#E2F3F5" }}>
          <ModelIcon />
        </span>
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <h2>{title}</h2>
          <span className="note">No model for this component yet. Here is the spec it would be written and tested against.</span>
        </div>
        <span className="tag tag-amber" style={{ marginLeft: "auto" }}>
          {active ? "Your call" : ask.answers ? "Answered" : "Skipped"}
        </span>
      </div>
      {offer && (
        <div className="gen-body">
          <div className="spec-io">
            <SpecList title="Inputs" items={offer.inputs} tone="in" />
            <span className="spec-arrow" aria-hidden="true">
              <svg width="28" height="16" viewBox="0 0 28 16">
                <path d="M2 8h22M18 3l6 5-6 5" fill="none" stroke="#9DB4B6" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <SpecList title="Outputs" items={offer.outputs} tone="out" />
          </div>
          <details className="spec-physics" open={active}>
            <summary>
              Physics it must follow <span className="note">· {offer.physics.length} rules</span>
            </summary>
            <ol>
              {offer.physics.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ol>
          </details>
          {offer.sources.length > 0 && (
            <div className="spec-sources">
              {offer.sources.map((s) => (
                <span key={s} className="spec-source">
                  <BookIcon />
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
      {active && (
        <form className="gen-foot" onSubmit={send(yes)}>
          <span className="note">{q?.hint}</span>
          <span style={{ display: "inline-flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-soft ta-btn ta-soft" onClick={send(no)}>
              {no}
            </button>
            <button type="submit" className="btn btn-ink ta-btn ta-ink">
              <ModelIcon color="#FFFFFF" />
              {yes}
            </button>
          </span>
        </form>
      )}
    </section>
  );
}

function SpecList({ title, items, tone }: { title: string; items: string[]; tone: "in" | "out" }) {
  return (
    <div className="spec-list">
      <span className="spec-title">{title}</span>
      <div className="spec-chips">
        {items.map((q) => {
          const [name, unit] = splitQuantity(q);
          return (
            <span key={q} className={`spec-chip ${tone}`} title={name}>
              {quantityLabel(name)}
              {unit && <i>{unit}</i>}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function BookIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none", marginTop: 2 }}>
      <path d="M2.5 3.2c2-.8 3.8-.6 5.5.6 1.7-1.2 3.5-1.4 5.5-.6v9.4c-2-.8-3.8-.6-5.5.6-1.7-1.2-3.5-1.4-5.5-.6zM8 3.8v9.4" fill="none" stroke="#66727C" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

// ------------------------------------------------------------------ attempts

/** The self-correction loop at a glance: one pill per attempt, red until one passes. */
export function AttemptTrack({ attempts }: { attempts: GenAttempt[] }) {
  if (!attempts.length) return null;
  return (
    <ol className="track" aria-label="Attempts">
      {attempts.map((a, i) => (
        <li key={a.number} className={a.passed ? "ok" : "bad"}>
          {i > 0 && <span className="track-line" aria-hidden="true" />}
          <span className="track-pill">
            {a.passed ? <DoneIcon size={16} /> : <FailIcon size={16} />}
            Attempt {a.number}
            <span className="track-why">{a.passed ? passedText(a) : firstProblem(a)}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function passedText(a: GenAttempt): string {
  const n = a.checks.length;
  return `${n} of ${n} checks`;
}

export function firstProblem(a: GenAttempt): string {
  if (a.violations.length) return `sandbox rule: ${a.violations[0]}`;
  if (a.error) return a.error;
  if (a.case_errors.length) return a.case_errors[0].replace(/^.*?: line \d+: /, "");
  const failed = a.checks.find((c) => !c.passed);
  return failed ? `failed: ${failed.name}` : "failed";
}

// ------------------------------------------------------------------ approval

type Tab = "code" | "table" | "checks";

export function ApprovalCard({
  ask,
  generation,
  offer,
  active,
  onSubmit,
}: {
  ask: Ask;
  generation?: Generation;
  offer?: OfferDetail;
  active: boolean;
  onSubmit: (answers: Record<string, string>) => void;
}) {
  const q = ask.value.questions[0];
  const [approve, reject] = q?.options ?? ["Approve", "Reject"];
  const [tab, setTab] = useState<Tab>("code");
  const units = useMemo(() => unitsOf(offer), [offer]);
  if (!generation) return null;
  const g = generation;
  const tokens = typeof g.tokens === "number" ? g.tokens : (g.tokens.prompt ?? 0) + (g.tokens.output ?? 0);
  const passed = g.checks.filter((c) => c.passed).length;
  const outputs = new Set(
    offer ? offer.outputs.map((o) => splitQuantity(o)[0]) : Object.keys(g.attempts.find((a) => a.outputs?.length)?.outputs?.[0] ?? {}),
  );
  const answered = ask.answers?.[q.id];
  const title = offer ? `Use this ${offer.title.toLowerCase()} model?` : ask.value.intro;
  const tabs: [Tab, string][] = [
    ["code", "Code"],
    ["table", `Test table · ${g.table.length}`],
    ["checks", `Checks · ${passed}/${g.checks.length}`],
  ];
  return (
    <section className={`card gen ta-rise${active ? "" : " gen-done"}`} aria-label="Approve the generated model">
      <div className="gen-head">
        <span className="icon-box" style={{ background: g.passed ? "#E3F5EA" : "#FCE9E7" }}>
          <ModelIcon color={g.passed ? "#0F7A3D" : "#A12C22"} />
        </span>
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <h2>{title}</h2>
          <span className="note">Tested in the sandbox. Nothing runs in a design until you approve it.</span>
        </div>
        <span className={`tag ${answered ? (answered === approve ? "tag-ok" : "tag-red") : "tag-amber"}`} style={{ marginLeft: "auto" }}>
          {answered ? (answered === approve ? "Approved" : "Rejected") : active ? "Your approval" : "Not answered"}
        </span>
      </div>
      <div className="gen-body">
        <div className="gen-stats">
          <Stat label="Written by" value={g.model} mono />
          <Stat label="Attempts" value={String(g.attempts.length)} />
          <Stat label="Checks" value={`${passed} / ${g.checks.length}`} good={passed === g.checks.length} />
          <Stat label="Test cases" value={String(g.table.length)} />
          <Stat label="Cost" value={`${tokens.toLocaleString("en-US")} tokens`} sub={`${fmtNum(g.seconds)} s`} />
        </div>
        <AttemptTrack attempts={g.attempts} />
        <div className="seg tabs" role="tablist" aria-label="Generated model">
          <span
            className="seg-thumb ta-thumb"
            style={{ left: `calc(4px + ${tabs.findIndex(([id]) => id === tab)} * (100% - 8px) / ${tabs.length})`, width: `calc((100% - 8px) / ${tabs.length})` }}
          />
          {tabs.map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} style={{ fontWeight: tab === id ? 650 : 450 }} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </div>
        {tab === "code" && <CodeView code={g.code} label={`${g.component}.py`} />}
        {tab === "table" && <TestTable rows={g.table} outputs={outputs} units={units} />}
        {tab === "checks" && (
          <ul className="gen-checks">
            {g.checks.map((c) => (
              <li key={c.name} className={c.passed ? "" : "fail"}>
                {c.passed ? <DoneIcon size={16} /> : <FailIcon size={16} />}
                <span>
                  <span className="sr-only">{c.passed ? "Passed: " : "Failed: "}</span>
                  {c.name}
                </span>
                <span className="check-detail">{c.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {active && (
        <div className="gen-foot">
          <span className="note">{q?.hint}</span>
          <span style={{ display: "inline-flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-soft ta-btn ta-soft" onClick={() => onSubmit({ [q.id]: reject })}>
              {reject}
            </button>
            <button type="button" className="btn btn-ink ta-btn ta-ink" onClick={() => onSubmit({ [q.id]: approve })} disabled={!g.passed}>
              <Tick color="#FFFFFF" />
              {approve}
            </button>
          </span>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, sub, mono, good }: { label: string; value: string; sub?: string; mono?: boolean; good?: boolean }) {
  return (
    <div className="gen-stat">
      <span className="tile-label">{label}</span>
      <strong style={{ fontFamily: mono ? "var(--mono)" : undefined, fontSize: mono ? 14 : 18, color: good ? "#0F7A3D" : undefined }}>{value}</strong>
      {sub && <span className="tile-sub">{sub}</span>}
    </div>
  );
}

// A small Python highlighter: comments, strings, keywords and numbers. React escapes the text.
const KEYWORDS = new Set(
  "def return if elif else for while in and or not import from as with try except raise pass None True False lambda min max abs float int".split(" "),
);
const TOKEN = /(#.*$)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|\b(\d+(?:\.\d+)?(?:e[-+]?\d+)?)\b|\b([A-Za-z_]\w*)\b/gm;

function highlight(line: string): ReactNode[] {
  const out: ReactNode[] = [];
  let at = 0;
  for (const m of line.matchAll(TOKEN)) {
    const i = m.index ?? 0;
    if (i > at) out.push(line.slice(at, i));
    const [whole, comment, str, num, word] = m;
    if (comment) out.push(<span key={i} className="tk-c">{whole}</span>);
    else if (str) out.push(<span key={i} className="tk-s">{whole}</span>);
    else if (num) out.push(<span key={i} className="tk-n">{whole}</span>);
    else if (word && KEYWORDS.has(word)) out.push(<span key={i} className="tk-k">{whole}</span>);
    else out.push(whole);
    at = i + whole.length;
  }
  if (at < line.length) out.push(line.slice(at));
  return out;
}

/** Read-only code with line numbers. */
export function CodeView({ code, label }: { code: string; label: string }) {
  const lines = code.replace(/\s+$/, "").split("\n");
  return (
    <figure className="codeview">
      <figcaption>
        <span>{label}</span>
        <span className="note">{lines.length} lines · read-only</span>
      </figcaption>
      <pre>
        <code>
          {lines.map((l, i) => (
            <span key={i} className="cl">
              <span className="ln" aria-hidden="true">
                {i + 1}
              </span>
              <span className="lc">{highlight(l)}</span>
              {"\n"}
            </span>
          ))}
        </code>
      </pre>
    </figure>
  );
}

function cell(v: unknown): string {
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en-US") : fmtNum(v, Math.abs(v) < 1 ? 3 : 2);
  if (v == null) return "–";
  return String(v);
}

/** The inputs and outputs at every reference case; outputs in teal. */
export function TestTable({
  rows,
  outputs,
  units,
  assumed,
}: {
  rows: Record<string, unknown>[];
  outputs: Set<string>;
  units: Record<string, string>;
  assumed?: Set<string>[];
}) {
  if (!rows.length) return null;
  const keys = Object.keys(rows[0]);
  const ins = keys.filter((k) => !outputs.has(k));
  const outs = keys.filter((k) => outputs.has(k));
  return (
    <div className="ttable-wrap">
      <table className="ttable">
        <thead>
          <tr>
            {ins.map((k) => (
              <th key={k} className="in">
                {quantityLabel(k)}
                {units[k] && <i>{units[k]}</i>}
              </th>
            ))}
            {outs.map((k, j) => (
              <th key={k} className={`out${j === 0 ? " first" : ""}`}>
                {quantityLabel(k)}
                {units[k] && <i>{units[k]}</i>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {ins.map((k) => (
                <td key={k} className={assumed?.[i]?.has(k) ? "assumed" : undefined} title={assumed?.[i]?.has(k) ? "Assumed from the spec's defaults" : undefined}>
                  {cell(r[k])}
                </td>
              ))}
              {outs.map((k, j) => (
                <td key={k} className={`out${j === 0 ? " first" : ""}`}>
                  {cell(r[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** After approval: the model run at the design's conditions (CUSTOM "model_result"). */
export function OperatingPoints({ result }: { result: ModelResult }) {
  if (!result.cases.length || !result.outputs.length) return null;
  const rows = result.cases.map((c, i) => ({ ...c, ...(result.outputs[i] ?? {}) }));
  const outputs = new Set(Object.keys(result.outputs[0] ?? {}));
  const assumed = (result.assumed ?? []).map((a) => new Set(a));
  const anyAssumed = assumed.some((a) => a.size > 0);
  const units = Object.fromEntries(Object.entries(result.units ?? {}).map(([k, u]) => [k, u === "-" ? "" : u]));
  const passed = result.checks.filter((c) => c.passed).length;
  return (
    <section className="card points ta-rise" aria-label="Operating points of the generated model">
      <div className="points-head">
        <span className="options-title">
          Operating points of the {result.title.toLowerCase()} model you approved
        </span>
        <span style={{ display: "inline-flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {result.checks.length > 0 && (
            <span className={`tag ${passed === result.checks.length ? "tag-ok" : "tag-red"}`}>
              {passed} of {result.checks.length} checks
            </span>
          )}
          {anyAssumed && (
            <span className="note" style={{ fontSize: 12.5 }}>
              <span className="assumed-key" /> assumed from the spec's defaults
            </span>
          )}
        </span>
      </div>
      {rows.length <= 3 ? (
        <PointsTable cases={result.cases} outputs={result.outputs} units={units} assumed={assumed} />
      ) : (
        <TestTable rows={rows} outputs={outputs} units={units} assumed={assumed} />
      )}
      {result.warnings?.map((w) => (
        <span key={w} className="step-sub" style={{ color: "#8A5A00" }}>
          {w}
        </span>
      ))}
    </section>
  );
}

/** A few cases read best transposed: one row per quantity, one column per case. */
function PointsTable({
  cases,
  outputs,
  units,
  assumed,
}: {
  cases: Record<string, unknown>[];
  outputs: Record<string, unknown>[];
  units: Record<string, string>;
  assumed: Set<string>[];
}) {
  const ins = Object.keys(cases[0] ?? {});
  const outs = Object.keys(outputs[0] ?? {});
  const head = (k: string) => (
    <th scope="row">
      {quantityLabel(k)}
      {units[k] && <i>{units[k]}</i>}
    </th>
  );
  return (
    <div className="ttable-wrap">
      <table className="ttable ptable">
        <thead>
          <tr>
            <th />
            {cases.map((_, i) => (
              <th key={i}>{cases.length > 1 ? `Case ${i + 1}` : "Value"}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="group">
            <th colSpan={cases.length + 1}>Inputs</th>
          </tr>
          {ins.map((k) => (
            <tr key={k}>
              {head(k)}
              {cases.map((c, i) => (
                <td key={i} className={assumed[i]?.has(k) ? "assumed" : undefined} title={assumed[i]?.has(k) ? "Assumed from the spec's defaults" : undefined}>
                  {cell(c[k])}
                </td>
              ))}
            </tr>
          ))}
          <tr className="group out">
            <th colSpan={cases.length + 1}>Outputs</th>
          </tr>
          {outs.map((k) => (
            <tr key={k}>
              {head(k)}
              {outputs.map((o, i) => (
                <td key={i} className="out">
                  {cell(o[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
