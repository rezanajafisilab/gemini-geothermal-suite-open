// The eval runs: one headline tile per run (scenarios passed, tokens, time), and the scenario
// matrix (rows = test scenarios, columns = runs) with pass or fail in each cell. Hover or focus a
// cell for what was expected and what the agent did; select it to keep the details below.

import { useEffect, useState } from "react";

import type { EvalScenario } from "../../workbench";
import { behaviourLabel, fmtDate, median, type Matrix, type MatrixRow, type MatrixRun } from "./model";
import { go } from "../../workbench/route";

const fmtInt = (n: number) => (Number.isFinite(n) ? Math.round(n).toLocaleString("en-US") : "–");

function fmtSec(s: number): string {
  if (!Number.isFinite(s)) return "–";
  if (s < 10) return `${s.toFixed(1)} s`;
  if (s < 60) return `${Math.round(s)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${Math.round(s - m * 60)} s`;
}

function PassIcon({ ok, size = 18 }: { ok: boolean; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden="true" className="ev-icon">
      <circle cx="9" cy="9" r="9" fill={ok ? "#E3F5EA" : "#FBE3E0"} />
      {ok ? (
        <path d="M5.3 9.3 7.8 11.8 12.8 6.3" fill="none" stroke="#0F7A3D" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <path d="M6.3 6.3l5.4 5.4M11.7 6.3l-5.4 5.4" fill="none" stroke="#B42318" strokeWidth="1.9" strokeLinecap="round" />
      )}
    </svg>
  );
}

// ------------------------------------------------------------------ headline tiles

export function EvalTiles({ matrix, onShow }: { matrix: Matrix; onShow: (rowId: string, col: number) => void }) {
  return (
    <section className="ev-tiles" aria-label="Eval runs">
      {matrix.runs.map((r, col) => {
        const sc = r.run.scenarios;
        const medTokens = median(sc.map((s) => s.tokens));
        const medSec = median(sc.map((s) => s.seconds));
        return (
          <div key={r.key} className="ev-tile">
            <div className="ev-tile-head">
              <span className="ev-tile-label">{r.label} run</span>
              <code className="ev-model">{r.run.answerer}</code>
            </div>
            <span className="ev-tile-value">
              <strong>{r.run.passed}</strong>
              <span>of {r.run.total} scenarios passed</span>
            </span>
            <span className="ev-pips" aria-hidden="true">
              {sc.map((s) => (
                <i key={s.id} className={s.ok ? "ok" : "fail"} />
              ))}
            </span>
            <dl className="ev-tile-stats">
              <div>
                <dt>Tokens</dt>
                <dd>{fmtInt(r.run.tokens)}</dd>
                <dd className="ev-sub">{fmtInt(medTokens)} a scenario</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{fmtSec(r.run.seconds)}</dd>
                <dd className="ev-sub">{fmtSec(medSec)} a scenario</dd>
              </div>
            </dl>
            <span className="ev-tile-foot">
              {r.failed.length ? (
                <>
                  Failed:{" "}
                  {r.failed.map((id, i) => (
                    <span key={id}>
                      {i > 0 && ", "}
                      <button type="button" className="link-btn ev-link" onClick={() => onShow(id, col)}>
                        {matrix.rows.find((x) => x.id === id)?.num ?? id} {matrix.rows.find((x) => x.id === id)?.name}
                      </button>
                    </span>
                  ))}
                </>
              ) : (
                "Every scenario passed"
              )}
              <span className="ev-when">{fmtDate(r.when)}</span>
            </span>
          </div>
        );
      })}
    </section>
  );
}

// ------------------------------------------------------------------ the matrix

interface Tip {
  row: MatrixRow;
  col: number;
  /** The cell it points at (to follow it when the page scrolls). */
  el: HTMLElement;
  x: number;
  y: number;
  below: boolean;
}

/** Where the tooltip of a cell goes: above it, or below near the top of the window; null when off screen. */
function place(row: MatrixRow, col: number, el: HTMLElement): Tip | null {
  const r = el.getBoundingClientRect();
  if (r.bottom < 0 || r.top > window.innerHeight || !el.isConnected) return null;
  const half = Math.min(140, window.innerWidth / 2 - 8);
  const x = Math.min(window.innerWidth - half - 8, Math.max(half + 8, r.left + r.width / 2));
  const below = r.top < 170;
  return { row, col, el, x, y: below ? r.bottom + 8 : r.top - 8, below };
}

interface Props {
  matrix: Matrix;
  selected: { rowId: string; col: number } | null;
  onSelect: (s: { rowId: string; col: number } | null) => void;
}

export function EvalMatrix({ matrix, selected, onSelect }: Props) {
  const [onlyFails, setOnlyFails] = useState(false);
  const [tip, setTip] = useState<Tip | null>(null);
  const failures = matrix.rows.filter((r) => r.failures > 0).length;
  const rows = onlyFails ? matrix.rows.filter((r) => r.failures > 0) : matrix.rows;

  const anchor = tip?.el ?? null;
  useEffect(() => {
    if (!anchor) return;
    // Follow the cell when the page scrolls (focusing an off-screen cell scrolls it in).
    const follow = () => setTip((t) => (t ? place(t.row, t.col, t.el) : null));
    window.addEventListener("scroll", follow, true);
    window.addEventListener("resize", follow);
    return () => {
      window.removeEventListener("scroll", follow, true);
      window.removeEventListener("resize", follow);
    };
  }, [anchor]);

  const show = (row: MatrixRow, col: number, el: HTMLElement) => setTip(place(row, col, el));

  const sel = selected ? matrix.rows.find((r) => r.id === selected.rowId) ?? null : null;

  return (
    <section id="ev-scenarios" className="ev-card" aria-labelledby="ev-mx-h">
      <div className="ev-card-head">
        <h2 id="ev-mx-h">Test scenarios</h2>
        <span className="ev-muted">
          {matrix.rows.length} scenarios, each run on {matrix.runs.length === 1 ? "one device" : `${matrix.runs.length} set-ups`}. Pass: the expected behaviour, every number from a tool.
        </span>
        {failures > 0 && (
          <button type="button" className="ev-toggle ta-btn" aria-pressed={onlyFails} onClick={() => setOnlyFails(!onlyFails)}>
            Only failures <b>{failures}</b>
          </button>
        )}
      </div>
      <div className="ev-scroll">
        <table className="ev-matrix">
          <thead>
            <tr>
              <th scope="col" className="ev-c-num">
                <span className="sr-only">Number</span>
              </th>
              <th scope="col" className="ev-c-name">
                Scenario
              </th>
              <th scope="col" className="ev-c-exp">
                Expected
              </th>
              {matrix.runs.map((r) => (
                <th key={r.key} scope="col" className="ev-c-run">
                  <span className="ev-run-h">
                    <strong>{r.label}</strong>
                    <span>
                      {r.run.passed}/{r.run.total}
                    </span>
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className={selected?.rowId === row.id ? "is-sel" : undefined}>
                <td className="ev-c-num">{row.num}</td>
                <th scope="row" className="ev-c-name">
                  {row.name}
                </th>
                <td className="ev-c-exp">
                  <span className="ev-exp">{behaviourLabel(row.expected)}</span>
                </td>
                {row.cells.map((c, col) => (
                  <td key={matrix.runs[col].key} className="ev-c-run">
                    {c ? (
                      <button
                        type="button"
                        className={`ev-cell${c.ok ? "" : " is-fail"}${selected?.rowId === row.id && selected.col === col ? " is-on" : ""}`}
                        aria-pressed={selected?.rowId === row.id && selected.col === col}
                        aria-label={`${row.num} ${row.name}, ${matrix.runs[col].label} run: ${c.ok ? "passed" : "failed"}. Expected ${behaviourLabel(c.expected)}, got ${behaviourLabel(c.got) || "nothing"}; ${c.calls} model calls, ${fmtInt(c.tokens)} tokens, ${fmtSec(c.seconds)}.`}
                        onPointerEnter={(e) => show(row, col, e.currentTarget)}
                        onPointerLeave={() => setTip(null)}
                        onFocus={(e) => show(row, col, e.currentTarget)}
                        onBlur={() => setTip(null)}
                        onClick={() => {
                          onSelect(selected?.rowId === row.id && selected.col === col ? null : { rowId: row.id, col });
                          setTip(null);
                        }}
                      >
                        <PassIcon ok={c.ok} />
                        <span className="ev-cell-txt">{c.ok && c.got === c.expected ? fmtSec(c.seconds) : behaviourLabel(c.got) || "–"}</span>
                      </button>
                    ) : (
                      <span className="ev-cell-none" title="Not in this run">
                        –
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td className="ev-c-num" />
              <th scope="row" className="ev-c-name">
                Run total
              </th>
              <td className="ev-c-exp" />
              {matrix.runs.map((r) => (
                <td key={r.key} className="ev-c-run">
                  <span className="ev-foot">
                    <strong>
                      {r.run.passed} of {r.run.total}
                    </strong>
                    <span>{fmtInt(r.run.tokens)} tokens</span>
                    <span>{fmtSec(r.run.seconds)}</span>
                  </span>
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="ev-detail" aria-live="polite">
        {sel ? <ScenarioDetail row={sel} runs={matrix.runs} col={selected!.col} /> : <p className="ev-muted">Select a cell to keep its details here; hover or focus one for a quick look.</p>}
      </div>

      {tip && (
        <div className={`ev-tip${tip.below ? " below" : ""}`} style={{ left: tip.x, top: tip.y }} role="tooltip">
          <TipBody row={tip.row} run={matrix.runs[tip.col]} cell={tip.row.cells[tip.col]!} />
        </div>
      )}
    </section>
  );
}

function TipBody({ row, run, cell }: { row: MatrixRow; run: MatrixRun; cell: EvalScenario }) {
  return (
    <>
      <span className="ev-tip-head">
        <PassIcon ok={cell.ok} size={15} />
        <strong>
          {row.num} {row.name}
        </strong>
      </span>
      <span className="ev-tip-run">
        {run.label} run · {run.run.answerer}
      </span>
      <span className="ev-tip-grid">
        <span>Expected</span>
        <b>{behaviourLabel(cell.expected)}</b>
        <span>Got</span>
        <b>{behaviourLabel(cell.got) || "–"}</b>
        <span>Model calls</span>
        <b>{cell.calls}</b>
        <span>Tokens</span>
        <b>{fmtInt(cell.tokens)}</b>
        <span>Time</span>
        <b>{fmtSec(cell.seconds)}</b>
      </span>
    </>
  );
}

/** "20261103T225252Z_qwen3-1.7b_auto.jsonl" → the run's name in the transcripts folder. */
export const runStem = (file: string) => file.replace(/\.jsonl$/, "");

/** Open a case's transcript: "#evidence/<run>/<case>", so it can be linked to and Back closes it. */
export const openTranscript = (file: string, caseId: string) => go("evidence", `${runStem(file)}/${caseId}`);

function ScenarioDetail({ row, runs, col }: { row: MatrixRow; runs: MatrixRun[]; col: number }) {
  const maxTok = Math.max(1, ...row.cells.map((c) => c?.tokens ?? 0));
  const maxSec = Math.max(0.001, ...row.cells.map((c) => c?.seconds ?? 0));
  const cell = row.cells[col];
  return (
    <div className="ev-sd ta-rise" key={`${row.id}-${col}`}>
      <div className="ev-sd-head">
        <span className="ev-muted">{row.num}</span>
        <strong>{row.name}</strong>
        <span className="ev-exp">expected: {behaviourLabel(row.expected)}</span>
        {cell && !cell.ok && cell.got === cell.expected && !cell.failed?.length && (
          <span className="ev-muted">The behaviour matched, but a check failed (a number not from a tool, or a physics check).</span>
        )}
        {cell && !cell.ok && !!cell.failed?.length && <span className="ev-muted">Failed: {cell.failed.map((f) => f.replace(/_/g, " ")).join("; ")}.</span>}
      </div>
      <div className="ev-sd-grid" role="table" aria-label={`${row.name} in each run`}>
        <div role="row" className="ev-sd-row ev-sd-cap">
          <span role="columnheader">Run</span>
          <span role="columnheader">Result</span>
          <span role="columnheader">Calls</span>
          <span role="columnheader">Tokens</span>
          <span role="columnheader">Time</span>
          <span role="columnheader">
            <span className="sr-only">Transcript</span>
          </span>
        </div>
        {runs.map((r, i) => {
          const c = row.cells[i];
          return (
            <div role="row" key={r.key} className={`ev-sd-row${i === col ? " is-on" : ""}`}>
              <span role="cell" className="ev-sd-run">
                <strong>{r.label}</strong> <code className="ev-model">{r.run.answerer}</code>
              </span>
              {c ? (
                <>
                  <span role="cell" className={`ev-sd-res${c.ok ? "" : " is-fail"}`}>
                    <PassIcon ok={c.ok} size={16} />
                    {c.ok ? "passed" : "failed"}, got {behaviourLabel(c.got) || "nothing"}
                  </span>
                  <span role="cell" className="ev-sd-n">
                    {c.calls}
                  </span>
                  <span role="cell" className="ev-sd-bar">
                    <i style={{ width: `${(c.tokens / maxTok) * 100}%` }} />
                    <b>{fmtInt(c.tokens)}</b>
                  </span>
                  <span role="cell" className="ev-sd-bar">
                    <i style={{ width: `${(c.seconds / maxSec) * 100}%` }} />
                    <b>{fmtSec(c.seconds)}</b>
                  </span>
                  <span role="cell" className="ev-sd-tx">
                    {c.transcript && (
                      <button type="button" className="link-btn ev-link" onClick={() => openTranscript(r.run.file, c.id)}>
                        Open transcript
                      </button>
                    )}
                  </span>
                </>
              ) : (
                <span role="cell" className="ev-muted ev-sd-missing">
                  Not in this run
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
