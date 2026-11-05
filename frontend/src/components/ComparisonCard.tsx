// The designs compared (CUSTOM "comparison"): one row per design, the chosen one first and
// highlighted, as horizontal bars on one zero-based scale for the metric picked above them. Cost
// metrics draw the gas reference's value as a dashed line across the other rows. Every number
// comes from the event; only bar widths are computed here.
//
// One series, so one colour: the chosen design in the accent, the rest grey (the dataviz
// emphasis form). Values sit at the bar ends; hover or focus a row for all of its figures.

import { useState } from "react";

import type { ComparedDesign, Comparison } from "../agent/types";
import { compareHref } from "../tabs/compare/link";
import { Arrow } from "./Icons";
import { fmtNum } from "./ResultCard";
import { statusWords } from "../workbench/format";

type MetricId = "lcoh" | "co2" | "lcoc" | "capex";

interface Metric {
  id: MetricId;
  label: string;
  unit: string;
  /** Costs: lower is better, and the gas reference is drawn as a line. */
  cost: boolean;
  get: (d: ComparedDesign) => number | null;
  /** Which coverage the metric depends on. */
  side: "heat" | "cold";
}

const finite = (v: number | null | undefined) => (typeof v === "number" && Number.isFinite(v) ? v : null);

// A design that delivers no heat (or cold) has no meaningful cost or CO₂ figure for it.
export const METRICS: Metric[] = [
  { id: "lcoh", label: "Cost of heat", unit: "€/MWh", cost: true, side: "heat", get: (d) => (d.heat_coverage_pct > 0 ? finite(d.lcoh) : null) },
  { id: "co2", label: "CO₂ saving", unit: "%", cost: false, side: "heat", get: (d) => (d.heat_coverage_pct > 0 ? finite(d.co2_saving_pct) : null) },
  { id: "lcoc", label: "Cost of cold", unit: "€/MWh", cost: true, side: "cold", get: (d) => (d.cool_coverage_pct > 0 ? finite(d.lcoc) : null) },
  { id: "capex", label: "Capital", unit: "M€", cost: true, side: "heat", get: (d) => finite(d.capex_meur) },
];

const ACCENT = "#0B8FA0";
const GREY = "#B9C3C6";
const GREY_REF = "#D3DADB";

/** The rows in the order drawn: the chosen design first (its first entry), then the rest as sent. */
export function compareRows(c: Comparison): { design: ComparedDesign; chosen: boolean; index: number }[] {
  const pick = c.chosen ? c.designs.findIndex((d) => d.code === c.chosen) : -1;
  const rows = c.designs.map((design, index) => ({ design, chosen: index === pick, index }));
  return pick > 0 ? [rows[pick], ...rows.filter((r) => r.index !== pick)] : rows;
}

/** "what-if: reservoir −10 °C" for a what-if run, else null. */
export function whatIfLabel(d: ComparedDesign): string | null {
  const dt = finite(d.reservoir_delta_c);
  if (!dt) return null;
  return `what-if: reservoir ${dt < 0 ? "−" : "+"}${fmtNum(Math.abs(dt))} °C`;
}

export function ComparisonCard({ value }: { value: Comparison }) {
  const metrics = METRICS.filter((m) => value.designs.some((d) => m.get(d) != null));
  const [pick, setPick] = useState<MetricId>("lcoh");
  const [hover, setHover] = useState<number | null>(null);
  const metric = metrics.find((m) => m.id === pick) ?? metrics[0];
  if (!metric) return null;
  const rows = compareRows(value);
  const ref = value.designs.find((d) => d.reference);
  const refValue = metric.cost && ref ? metric.get(ref) : null;
  const values = rows.map((r) => metric.get(r.design));
  const known = values.filter((v): v is number => v != null);
  const lo = Math.min(0, ...known);
  const hi = Math.max(0, ...known, refValue ?? 0) || 1;
  const pct = (v: number) => ((v - lo) / (hi - lo)) * 100;
  const zero = pct(0);
  const at = metrics.indexOf(metric);
  // The same design as the what-if, at the reservoir as expected: say so, or the two rows read alike.
  const whatIfCodes = new Set(value.designs.filter((d) => whatIfLabel(d)).map((d) => d.code));

  return (
    <section className="card compare ta-rise" style={{ animationDelay: ".16s" }} aria-label="Designs compared">
      <div className="compare-head">
        <span className="compare-title">Designs compared</span>
      </div>
      {metrics.length > 1 && (
        <div className="seg tabs compare-tabs" role="tablist" aria-label="Compare by">
          <span className="seg-thumb ta-thumb" style={{ left: `calc(4px + ${at} * (100% - 8px) / ${metrics.length})`, width: `calc((100% - 8px) / ${metrics.length})` }} />
          {metrics.map((m) => (
            <button
              key={m.id}
              type="button"
              role="tab"
              aria-selected={m === metric}
              title={`${m.label} (${m.unit})`}
              style={{ fontWeight: m === metric ? 650 : 450 }}
              onClick={() => setPick(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      )}
      <span className="compare-scale">
        {metric.label} in {metric.unit}, {metric.cost ? "lower" : "higher"} is better
      </span>

      <ul className="compare-rows">
        {rows.map((r, k) => {
          const d = r.design;
          const v = values[k];
          const whatIf = whatIfLabel(d);
          const asExpected = !whatIf && whatIfCodes.has(d.code);
          const coverage = metric.side === "cold" ? d.cool_coverage_pct : d.heat_coverage_pct;
          const name = d.reference ? d.name.replace(/\s*\(reference\)\s*$/i, "") : d.name;
          const x0 = v == null ? zero : Math.min(zero, pct(v));
          const x1 = v == null ? zero : Math.max(zero, pct(v));
          const neg = v != null && v < 0;
          const label = v == null ? "–" : `${neg ? "−" : ""}${fmtNum(Math.abs(v))}${metric.unit === "%" ? "%" : ""}`;
          const all = [
            `${fmtNum(d.heat_coverage_pct)}% of the heat`,
            d.cool_coverage_pct > 0 ? `${fmtNum(d.cool_coverage_pct)}% of the cold` : "",
          ].filter(Boolean);
          return (
            <li
              key={r.index}
              className={`crow${r.chosen ? " chosen" : ""}${d.reference ? " reference" : ""}`}
              tabIndex={0}
              aria-label={`${d.code} ${name}${r.chosen ? ", chosen" : ""}${d.reference ? ", reference" : ""}${whatIf ? `, ${whatIf}` : ""}${d.verified ? "" : `, ${statusWords(d.failed ?? [], false)}`}: ${metric.label} ${v == null ? "not available" : `${label} ${metric.unit === "%" ? "" : metric.unit}`.trim()}.`}
              onPointerEnter={() => setHover(r.index)}
              onPointerLeave={() => setHover((h) => (h === r.index ? null : h))}
              onFocus={() => setHover(r.index)}
              onBlur={() => setHover((h) => (h === r.index ? null : h))}
            >
              <span className="crow-label">
                <span className="crow-name">
                  <span className="alt-code">{d.code}</span>
                  {name}
                </span>
                <span className="crow-tags">
                  {r.chosen && <span className="tag tag-teal">chosen</span>}
                  {d.reference && <span className="tag tag-grey">reference</span>}
                  {whatIf && <span className="tag tag-teal">{whatIf}</span>}
                  {asExpected && <span className="tag tag-grey">reservoir as expected</span>}
                  {!d.verified && <span className="tag tag-amber">{d.failed?.length ? statusWords(d.failed, false) : "fails checks"}</span>}
                </span>
                {coverage > 0 && coverage < 99.95 && (
                  <span className="crow-note">
                    covers {fmtNum(coverage)}% of the {metric.side}
                  </span>
                )}
              </span>
              <span className={`crow-track${lo < 0 ? " has-neg" : ""}`} aria-hidden="true">
                <span className="crow-inner">
                  {lo < 0 && <span className="crow-zero" style={{ left: `${zero}%` }} />}
                  {v != null && (
                    <span
                      className={`crow-bar ta-grow${neg ? " neg" : ""}`}
                      style={{ left: `${x0}%`, width: `${x1 - x0}%`, background: r.chosen ? ACCENT : d.reference ? GREY_REF : GREY }}
                    />
                  )}
                  {refValue != null && !d.reference && <span className="crow-ref" style={{ left: `${pct(refValue)}%` }} />}
                  <span
                    className={`crow-val${v == null ? " none" : ""}`}
                    style={neg ? { left: `${x0}%`, transform: "translateX(calc(-100% - 6px))" } : { left: `calc(${x1}% + 6px)` }}
                  >
                    {label}
                  </span>
                </span>
              </span>
              {hover === r.index && (
                <span className="lc-tip ctip" role="tooltip">
                  <span className="lc-tip-x">
                    {d.code} {name}
                  </span>
                  {METRICS.map((m) => {
                    const mv = m.get(d);
                    return (
                      <span key={m.id} className="lc-tip-row">
                        <strong>{mv == null ? "–" : `${fmtNum(mv)}`}</strong>
                        <span className="lc-tip-unit">{m.unit}</span>
                        <span className="lc-tip-name">{m.label}</span>
                      </span>
                    );
                  })}
                  <span className="lc-tip-row ctip-cover">Covers {all.join(" and ")}</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {refValue != null && ref && (
        <div className="legend-row">
          <span>
            <svg width="14" height="12" viewBox="0 0 14 12" aria-hidden="true">
              <path d="M7 1v10" stroke="#45515B" strokeWidth="1.5" strokeDasharray="2.5 2" />
            </svg>
            {ref.code} gas reference {fmtNum(refValue)} {metric.unit}
          </span>
        </div>
      )}

      <nav className="card-links" aria-label="The designs in the tabs">
        <a href={compareHref(value.designs.filter((d) => !d.reference).map((d) => d.code))}>
          Open in Compare <Arrow size={12} />
        </a>
      </nav>
    </section>
  );
}
