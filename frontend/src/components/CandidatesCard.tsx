// "How I got here": the design search behind a reply. A scatter of every candidate (the cost of
// heat and cold against its CO₂), the chosen one ringed and the gas reference marked, then the
// list: the chosen one, its closest rivals with why each lost, and the ones that broke a cap.

import { useMemo, useState } from "react";

import type { Search, SearchCandidate } from "../agent/types";
import { hrefFor } from "../workbench";
import { Arrow } from "./Icons";

const W = 560;
const H = 190;
const PAD = { l: 46, r: 14, t: 12, b: 34 };
const fmt = (v: number, d = 1) => v.toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: 0 });
const SHOWN = 4;

function axis(lo: number, hi: number, n = 4): number[] {
  const step = (hi - lo) / n;
  return Array.from({ length: n + 1 }, (_, i) => lo + i * step);
}

function Scatter({ value }: { value: Search }) {
  const [hover, setHover] = useState<string | null>(null);
  const valid = value.candidates.filter((c) => c.role !== "failed");
  const all = [...valid, value.reference];
  const xMax = Math.max(...all.map((c) => c.co2_t)) * 1.05 || 1;
  const yLo = Math.min(...all.map((c) => c.lcoe)) * 0.92;
  const yHi = Math.max(...all.map((c) => c.lcoe)) * 1.04;
  const x = (v: number) => PAD.l + (v / xMax) * (W - PAD.l - PAD.r);
  const y = (v: number) => H - PAD.b - ((v - yLo) / (yHi - yLo || 1)) * (H - PAD.t - PAD.b);
  const shown = hover ? all.find((c) => c.code === hover) : undefined;
  return (
    <figure className="cands-plot">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Every candidate: cost of heat and cold against CO₂ a year">
        {axis(yLo, yHi).map((v) => (
          <g key={`y${v}`}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="cands-grid" />
            <text x={PAD.l - 6} y={y(v) + 4} textAnchor="end" className="cands-tick">
              {fmt(v, 0)}
            </text>
          </g>
        ))}
        {axis(0, xMax).map((v) => (
          <text key={`x${v}`} x={x(v)} y={H - PAD.b + 16} textAnchor="middle" className="cands-tick">
            {fmt(v / 1000, 0)}k
          </text>
        ))}
        <text x={(W + PAD.l) / 2} y={H - 4} textAnchor="middle" className="cands-axis">
          CO₂, t a year
        </text>
        <text x={12} y={(H - PAD.b) / 2} textAnchor="middle" className="cands-axis" transform={`rotate(-90 12 ${(H - PAD.b) / 2})`}>
          €/MWh, heat and cold
        </text>
        <rect
          x={x(value.reference.co2_t) - 5}
          y={y(value.reference.lcoe) - 5}
          width={10}
          height={10}
          className="cands-ref"
          onPointerEnter={() => setHover(value.reference.code)}
          onPointerLeave={() => setHover(null)}
        />
        {/* The chosen design drawn last, so no other point covers it (SVG has no z-index). */}
        {[...valid].sort((a, b) => Number(a.role === "chosen") - Number(b.role === "chosen")).map((c, i) => (
          <circle
            key={`${i}-${c.code}`}
            cx={x(c.co2_t)}
            cy={y(c.lcoe)}
            r={c.role === "chosen" ? 7 : 4.5}
            className={`cands-dot${c.role === "chosen" ? " chosen" : ""}${hover === c.code ? " hover" : ""}`}
            onPointerEnter={() => setHover(c.code)}
            onPointerLeave={() => setHover(null)}
          >
            <title>{`${c.code}: ${fmt(c.lcoe)} €/MWh, ${fmt(c.co2_t, 0)} t CO₂`}</title>
          </circle>
        ))}
      </svg>
      <figcaption className="cands-hover" aria-live="polite">
        {shown ? (
          <>
            <b>{shown.code === "REF" ? "Gas reference" : shown.code}</b> {fmt(shown.lcoe)} €/MWh · {fmt(shown.co2_t, 0)} t CO₂ · {fmt(shown.capex_meur)} M€
          </>
        ) : (
          <span>
            <i className="cands-key chosen" /> chosen <i className="cands-key" /> met every cap <i className="cands-key ref" /> gas reference
          </span>
        )}
      </figcaption>
    </figure>
  );
}

function Row({ c }: { c: SearchCandidate }) {
  const mark = c.role === "chosen" ? "★" : c.role === "failed" ? "✗" : "✓";
  return (
    <li className={`cands-row ${c.role}`}>
      <span className="cands-mark" aria-hidden="true">
        {mark}
      </span>
      <span className="cands-main">
        <span className="cands-line">
          <code>{c.code}</code>
          <span className="cands-name">{c.name}</span>
        </span>
        {c.role === "chosen" ? (
          <span className="cands-why">
            Picked{c.rounds > 1 && c.changes.length ? ` after ${c.changes.join("; ")}` : ""}
          </span>
        ) : (
          c.reason && <span className="cands-why">{c.reason}</span>
        )}
      </span>
      <span className="cands-num">
        <b>{fmt(c.lcoe)}</b> €/MWh
      </span>
      <span className="cands-num">{c.role === "failed" ? "—" : `−${fmt(c.co2_saving_pct, 0)}% CO₂`}</span>
    </li>
  );
}

export function CandidatesCard({ value }: { value: Search }) {
  const [open, setOpen] = useState(false);
  const { valid, failed } = useMemo(
    () => ({
      valid: value.candidates.filter((c) => c.role !== "failed"),
      failed: value.candidates.filter((c) => c.role === "failed"),
    }),
    [value],
  );
  const s = value.summary;
  const rows = open ? valid : valid.slice(0, SHOWN);
  const ref = value.reference;
  return (
    <section className="card cands ta-rise" style={{ animationDelay: ".2s" }} aria-label="How the design was found">
      <div className="cands-head">
        <span className="cands-title">How I got here</span>
        <span className="chips">
          <span className="chip">{s.candidates} candidates</span>
          {s.improved > 0 && <span className="chip">{s.improved} enlarged to meet every day</span>}
          {s.failed > 0 && <span className="chip chip-red">{s.failed} broke a cap</span>}
          <span className="chip chip-teal">{value.objective === "co2" ? "ranked by CO₂" : "ranked by cost"}</span>
        </span>
      </div>
      <Scatter value={value} />
      <ol className="cands-list">
        {rows.map((c, i) => (
          <Row key={`${i}-${c.code}`} c={c} />
        ))}
      </ol>
      {valid.length > SHOWN && (
        <button type="button" className="link-btn cands-more" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Show fewer" : `Show all ${valid.length} that met every cap`}
        </button>
      )}
      {failed.length > 0 && (
        <details className="cands-failed">
          <summary>{failed.length} broke a cap and were dropped</summary>
          <ol className="cands-list">
            {failed.map((c, i) => (
              <Row key={`${i}-${c.code}`} c={c} />
            ))}
          </ol>
        </details>
      )}
      <p className="cands-ref-line">
        Baseline: gas boilers and electric chillers, {fmt(ref.lcoh)} €/MWh for heat, {fmt(ref.co2_t, 0)} t CO₂ a year.
        {value.notes.length > 1 && ` ${value.notes.slice(1).join(" ")}.`}
      </p>
      <nav className="card-links" aria-label="The search in the tabs">
        <a href={hrefFor("compare")}>
          All of them in Compare <Arrow size={12} />
        </a>
        <a href={hrefFor("trace")}>
          Each step in Trace <Arrow size={12} />
        </a>
      </nav>
    </section>
  );
}
