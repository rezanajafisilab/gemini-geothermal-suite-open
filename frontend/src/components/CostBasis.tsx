// A design's cost basis, said plainly where its cost is shown: what the €/MWh includes (a bar of
// its parts) and leaves out, the discount rate, the lifetimes and prices, how heat and cold share
// the costs, and how far the cost moves when one assumption changes (a tornado). Every number is
// the server's (src/gemini_agent/cost_basis.py: the same plant repriced by the real economics).
// `compact` (a short view) keeps the bar, the left-out items, the terms and the tornado;
// the Economics tab shows every part and why each item is left out.

import "./CostBasis.css";

import { useState } from "react";

import type { BasisSwing, CostBasis } from "../workbench/basis";

const KIND: Record<string, { label: string; color: string }> = {
  capital: { label: "Capital", color: "#0a6f7c" },
  "o&m": { label: "Operation and maintenance", color: "#5aa6ae" },
  electricity: { label: "Electricity", color: "#e3a33b" },
  gas: { label: "Gas", color: "#7856c4" },
  carbon: { label: "CO₂", color: "#8a959e" },
  credit: { label: "Gas sold", color: "#2ba866" },
};
const kindOf = (k: string) => KIND[k] ?? { label: k, color: "#b3bab2" };

const one = (v: number | null | undefined) => (v == null || !Number.isFinite(v) ? "–" : v.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
const pct = (f: number) => (f > 0 && f < 0.005 ? "<1 %" : `${Math.round(f * 100)} %`);

interface Props {
  basis: CostBasis;
  compact?: boolean;
  /** Which cost the tornado moves: heat and cold together (the headline), or one side. */
  measure?: "lcoe" | "lcoh" | "lcoc";
}

export function CostBasisView({ basis, compact = false, measure = "lcoe" }: Props) {
  const [all, setAll] = useState(!compact);
  const parts = basis.includes.filter((p) => p.share > 0);
  const credit = basis.includes.filter((p) => p.share < 0);
  const head = basis.headline.lcoe ?? basis.headline.lcoh;
  // The bar by kind (capital, O&M, energy, CO₂), with every part listed under it.
  const kinds: { kind: string; share: number; eur: number }[] = [];
  for (const p of parts) {
    const k = kinds.find((x) => x.kind === p.kind);
    if (k) {
      k.share += p.share;
      k.eur += p.eur_per_mwh;
    } else kinds.push({ kind: p.kind, share: p.share, eur: p.eur_per_mwh });
  }
  return (
    <div className={`cb${compact ? " cb-compact" : ""}`}>
      <section className="cb-block" aria-label="What the cost includes">
        <h4 className="cb-h">
          What the <strong>{one(head)} €/MWh</strong> includes
        </h4>
        <div className="cb-bar" role="img" aria-label={kinds.map((k) => `${kindOf(k.kind).label} ${pct(k.share)}`).join(", ")}>
          {kinds.map((k) => (
            <span key={k.kind} className="ta-grow" style={{ width: `${k.share * 100}%`, background: kindOf(k.kind).color }} title={`${kindOf(k.kind).label}: ${one(k.eur)} €/MWh (${pct(k.share)})`} />
          ))}
        </div>
        <div className="cb-keys">
          {kinds.map((k) => (
            <span key={k.kind} className="cb-key">
              <i style={{ background: kindOf(k.kind).color }} />
              {kindOf(k.kind).label}{" "}
              <b>
                {one(k.eur)} <small>({pct(k.share)})</small>
              </b>
            </span>
          ))}
        </div>
        {all && (
          <ul className="cb-parts">
            {[...parts, ...credit].map((p) => (
              <li key={p.item} title={p.note}>
                <i style={{ background: kindOf(p.kind).color }} aria-hidden="true" />
                <span className="cb-part">{p.item}</span>
                <span className="cb-num">
                  {one(p.eur_per_mwh)} €/MWh <small>({p.share < 0 ? `−${pct(-p.share)}` : pct(p.share)})</small>
                </span>
              </li>
            ))}
          </ul>
        )}
        {compact && (
          <button type="button" className="link-btn cb-more" aria-expanded={all} onClick={() => setAll((v) => !v)}>
            {all ? "Fewer details" : "Every part, and why each item is left out"}
          </button>
        )}
      </section>

      <section className="cb-block" aria-label="What the cost leaves out">
        <h4 className="cb-h">Left out</h4>
        {all ? (
          <ul className="cb-out">
            {basis.excludes.map((x) => (
              <li key={x.item}>
                <Cross />
                <span>
                  <strong>{x.item}.</strong> {x.why}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="cb-chips">
            {basis.excludes.map((x) => (
              <span key={x.item} className="cb-chip cb-chip-out" title={x.why}>
                <Cross />
                {x.item}
              </span>
            ))}
          </div>
        )}
      </section>

      <section className="cb-block" aria-label="On these terms">
        <h4 className="cb-h">On these terms</h4>
        <div className="cb-chips">
          <span className="cb-chip" title={basis.rate.source}>
            Discount rate <b>{basis.rate.label}</b>
            <small>PBL SDE++ 2026, Table 6.3</small>
          </span>
          {basis.lifetimes.map((l) => (
            <span key={l.label} className="cb-chip">
              {l.label} <b>{l.years} years</b>
            </span>
          ))}
          {basis.prices.map((p) => (
            <span key={p.label} className="cb-chip" title={p.source}>
              {p.label} <b>{p.value}</b>
            </span>
          ))}
        </div>
        <p className="cb-text">
          {compact ? "" : `${basis.method} `}
          {basis.split.headline} {basis.split.text}
        </p>
      </section>

      {basis.swings.length > 0 && (
        <section className="cb-block" aria-label="How far the cost moves">
          <h4 className="cb-h">How far it moves</h4>
          <Tornado swings={basis.swings} base={measure === "lcoe" ? head : measure === "lcoh" ? basis.headline.lcoh : basis.headline.lcoc} measure={measure} />
          <p className="cb-text cb-muted">{basis.note}</p>
        </section>
      )}
    </div>
  );
}

function Cross() {
  return (
    <svg className="cb-x" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      <circle cx="6" cy="6" r="5.4" fill="none" stroke="currentColor" strokeWidth="1.1" />
      <path d="M4 4l4 4M8 4l-4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

/** Each assumption's low and high case as a bar around the base cost: cheaper teal, dearer amber. */
export function Tornado({ swings, base, measure = "lcoe" }: { swings: BasisSwing[]; base: number | null | undefined; measure?: "lcoe" | "lcoh" | "lcoc" }) {
  const rows = swings
    .map((s) => ({ s, lo: s.low[measure], hi: s.high[measure] }))
    .filter((r): r is { s: BasisSwing; lo: number; hi: number } => r.lo != null && r.hi != null && Number.isFinite(r.lo) && Number.isFinite(r.hi));
  if (!rows.length || base == null) return null;
  const values = rows.flatMap((r) => [r.lo, r.hi]).concat(base);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.04 || 1;
  const a = min - pad;
  const span = max + pad - a;
  const x = (v: number) => ((v - a) / span) * 100;
  const summary = rows.map((r) => `${r.s.label}: ${r.s.low.value} gives ${one(r.lo)}, ${r.s.high.value} gives ${one(r.hi)} €/MWh`).join("; ");
  return (
    <div className="cb-tornado" role="img" aria-label={`Cost of ${measure === "lcoe" ? "heat and cold" : measure === "lcoh" ? "heat" : "cold"} at ${one(base)} €/MWh. ${summary}.`}>
      {rows.map(({ s, lo, hi }) => {
        const cheap = Math.min(lo, hi);
        const dear = Math.max(lo, hi);
        const cheapCase = lo <= hi ? s.low : s.high;
        const dearCase = lo <= hi ? s.high : s.low;
        return (
          <div key={s.key} className="cb-trow">
            <span className="cb-tlabel">
              {s.label}
              <small>{s.base}</small>
            </span>
            <span className="cb-track" aria-hidden="true">
              <span className="cb-base" style={{ left: `${x(base)}%` }} />
              <span className="cb-seg cb-cheap ta-grow" style={{ left: `${x(cheap)}%`, width: `${Math.max(0.4, x(base) - x(cheap))}%` }} />
              <span className="cb-seg cb-dear ta-grow" style={{ left: `${x(base)}%`, width: `${Math.max(0.4, x(dear) - x(base))}%` }} />
              <span className="cb-end cb-end-l" style={{ right: `${100 - x(cheap)}%` }}>
                {cheapCase.value} <b>{one(cheap)}</b>
              </span>
              <span className="cb-end cb-end-r" style={{ left: `${x(dear)}%` }}>
                <b>{one(dear)}</b> {dearCase.value}
              </span>
            </span>
          </div>
        );
      })}
      <div className="cb-trow" aria-hidden="true">
        <span />
        <span className="cb-taxis">
          <span style={{ left: `${x(base)}%` }}>{one(base)} €/MWh as designed</span>
        </span>
      </div>
    </div>
  );
}
