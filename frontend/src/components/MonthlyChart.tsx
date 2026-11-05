// The result card's month-by-month energy (ResultCard.monthly_gwh), drawn by hand in SVG: one
// stacked column per month of what each source supplied, the demand as a tick on top, and any
// month the supply falls short of it hatched in the yearly bar's "not covered" red. A Heat | Cold
// switch, a readout of every source per month (pointer or arrow keys) and a Table view.
//
// The sources keep the yearly split's colours, so the two read as one. Those pass the dataviz
// checks on the white card; the heat pump's amber is under 3:1 against it, so its values are
// always in the readout and the table, never only in the colour.

import { useId, useState, type KeyboardEvent } from "react";

import type { MonthlyGwh } from "../agent/types";
import { fmtValue, niceTicks, useWidth } from "./LineChart";

type Names = Record<string, { label: string; color: string }>;
type Mode = "heat" | "cool";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
// The electric boiler (a gas-free design's peaks) stacks on top, after the gas boiler: dispatch order.
const SOURCES: Record<Mode, string[]> = { heat: ["geo", "hp", "boiler", "electric_boiler"], cool: ["free", "abs", "chill"] };
const HEIGHT = 200;
const TOP = 20;
const BOTTOM = 22;
const RIGHT = 6;
const GAP = 2;
const INK = "#11181C";

export interface MonthRow {
  parts: { key: string; gwh: number }[];
  supplied: number;
  demand: number;
  /** GWh of the demand not met; 0 when the supply covers it (within rounding). */
  short: number;
}

const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);

/**
 * Twelve months of one side (heat or cold): each source's GWh in stacking order, what they add
 * up to, the demand and the shortfall. Null when the demand isn't twelve months long.
 */
export function monthRows(side: Record<string, unknown> | undefined, keys: string[]): MonthRow[] | null {
  const demand = side?.demand;
  if (!Array.isArray(demand) || demand.length !== 12) return null;
  return demand.map((d, i) => {
    const parts = keys.map((key) => {
      const list = side?.[key];
      return { key, gwh: Array.isArray(list) ? Math.max(0, num(list[i])) : 0 };
    });
    const supplied = parts.reduce((a, p) => a + p.gwh, 0);
    const dem = Math.max(0, num(d));
    // Monthly sums are rounded to the MWh: a few MWh under the demand is still covered.
    const gap = dem - supplied;
    return { parts, supplied, demand: dem, short: gap > Math.max(0.01, dem * 0.005) ? gap : 0 };
  });
}

/** The sources that supplied anything over the year, in stacking order. */
function activeKeys(rows: MonthRow[], keys: string[]): string[] {
  return keys.filter((k) => rows.some((r) => (r.parts.find((p) => p.key === k)?.gwh ?? 0) > 0));
}

function fmtGwh(v: number): string {
  return v === 0 ? "0" : fmtValue(v);
}

/** Table cells: two decimals, so a column's figures line up. */
const cellGwh = (v: number) => (v === 0 ? "0" : v < 0.005 ? "<0.01" : v.toFixed(2));

/** A column segment with its top corners rounded (the data end); square at the bottom. */
function topRounded(x: number, y: number, w: number, h: number, r: number): string {
  r = Math.max(0, Math.min(r, h, w / 2));
  return `M${x} ${y + h}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h}Z`;
}

export function MonthlyChart({ monthly, heat, cold }: { monthly: MonthlyGwh; heat: Names; cold: Names }) {
  const heatRows = monthRows(monthly.heat as unknown as Record<string, unknown>, SOURCES.heat);
  const coolRows = monthRows(monthly.cool as unknown as Record<string, unknown>, SOURCES.cool);
  const hasCold = !!coolRows && coolRows.some((r) => r.demand > 0);
  const [mode, setMode] = useState<Mode>(heatRows ? "heat" : "cool");
  const [table, setTable] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const [wrap, width] = useWidth(600);
  const uid = useId().replace(/[^\w-]/g, "");

  const side: Mode = mode === "cool" && hasCold ? "cool" : heatRows ? "heat" : "cool";
  const rows = side === "heat" ? heatRows : coolRows;
  if (!rows || (side === "cool" && !hasCold)) return null;
  const names = side === "heat" ? heat : cold;
  const keys = activeKeys(rows, SOURCES[side]);
  const label = (k: string) => names[k]?.label ?? k;
  const color = (k: string) => names[k]?.color ?? "#B3BAB2";
  const title = side === "heat" ? "Heat" : "Cold";
  const shortMonths = rows.flatMap((r, i) => (r.short > 0 ? [i] : []));

  const top = Math.max(...rows.map((r) => Math.max(r.demand, r.supplied)), 0);
  const yt = niceTicks(0, top || 1, 4);
  const ymax = yt[yt.length - 1] || 1;
  const ylabels = yt.map((t) => fmtGwh(t));
  const left = Math.max(26, Math.max(...ylabels.map((l) => l.length)) * 6.6 + 10);
  const pw = Math.max(0, width - left - RIGHT);
  const ph = HEIGHT - TOP - BOTTOM;
  const band = pw / 12;
  const barW = Math.max(6, Math.min(24, band * 0.6));
  const tickW = Math.min(band - 2, barW + 8);
  const cx = (i: number) => left + band * (i + 0.5);
  const sy = (v: number) => TOP + ph - (v / ymax) * ph;
  const letters = band < 26;

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const k = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
    if (k) setHover((h) => Math.max(0, Math.min(11, (h ?? (k > 0 ? -1 : 12)) + k)));
    else if (e.key === "Home") setHover(0);
    else if (e.key === "End") setHover(11);
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  const peak = rows.reduce((b, r, i) => (r.demand > rows[b].demand ? i : b), 0);
  const summary =
    `${title} by month in GWh: ${keys.map(label).join(", ")} stacked, with the demand as a tick. ` +
    `The demand peaks in ${MONTH_NAMES[peak]} at ${fmtGwh(rows[peak].demand)} GWh. ` +
    (shortMonths.length
      ? `The supply falls short in ${shortMonths.map((i) => MONTH_NAMES[i]).join(", ")}.`
      : "The supply meets the demand every month.") +
    " Arrow keys read one month at a time; the Table button shows every value.";

  const at = side === "heat" ? 0 : 1;
  const hx = hover != null ? cx(hover) : 0;
  const row = hover != null ? rows[hover] : null;
  return (
    <div ref={wrap} className="mchart" aria-label={`${title} month by month`} role="group">
      <div className="mchart-head">
        <span className="mchart-title">
          {title} by month <span className="lc-key-unit">GWh</span>
        </span>
        <span className="mchart-ctl">
          {heatRows && hasCold && (
            <span className="seg mini" role="tablist" aria-label="Heat or cold">
              <span className="seg-thumb ta-thumb" style={{ left: `calc(4px + ${at} * (100% - 8px) / 2)`, width: "calc((100% - 8px) / 2)" }} />
              {(["heat", "cool"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={side === m}
                  style={{ fontWeight: side === m ? 650 : 450 }}
                  onClick={() => {
                    setMode(m);
                    setHover(null);
                  }}
                >
                  {m === "heat" ? "Heat" : "Cold"}
                </button>
              ))}
            </span>
          )}
          <button
            type="button"
            className="mchart-table ta-btn"
            aria-pressed={table}
            onClick={() => {
              setTable(!table);
              setHover(null);
            }}
          >
            Table
          </button>
        </span>
      </div>

      {table ? (
        <MonthTable title={title} rows={rows} keys={keys} label={label} />
      ) : (
        <div
          className="lc-plot mchart-plot"
          tabIndex={0}
          role="group"
          aria-label={summary}
          onKeyDown={onKey}
          onBlur={() => setHover(null)}
        >
          <svg width={width} height={HEIGHT} aria-hidden="true" onPointerLeave={() => setHover(null)}>
            <defs>
              <pattern id={`short-${uid}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill="#E9928A" />
                <rect width="3" height="6" fill="#B42318" />
              </pattern>
            </defs>
            {hover != null && <rect x={hx - band / 2 + 1} y={TOP - 6} width={band - 2} height={ph + 6} rx={6} className="mchart-hover" />}
            {yt.map((t, k) => (
              <g key={t}>
                <line x1={left} x2={width - RIGHT} y1={sy(t)} y2={sy(t)} className={t === 0 ? "lc-axis" : "lc-grid"} />
                <text x={left - 8} y={sy(t)} dy="0.32em" textAnchor="end" className="lc-tick">
                  {ylabels[k]}
                </text>
              </g>
            ))}
            {rows.map((r, i) => {
              const x = cx(i) - barW / 2;
              const segs: { key: string; fill: string; y0: number; y1: number }[] = [];
              let cum = 0;
              for (const p of r.parts) {
                if (p.gwh <= 0 || !keys.includes(p.key)) continue;
                segs.push({ key: p.key, fill: color(p.key), y0: cum, y1: cum + p.gwh });
                cum += p.gwh;
              }
              if (r.short > 0) segs.push({ key: "short", fill: `url(#short-${uid})`, y0: r.supplied, y1: r.demand });
              const drawn = segs
                .map((s, k) => {
                  const yTop = sy(s.y1);
                  const yBot = sy(s.y0) - (k > 0 ? GAP : 0);
                  return { ...s, yTop, h: yBot - yTop };
                })
                .filter((s) => s.h >= 0.5);
              return (
                <g key={i} opacity={hover != null && hover !== i ? 0.55 : 1}>
                  {drawn.map((s, k) =>
                    k === drawn.length - 1 ? (
                      <path key={s.key} d={topRounded(x, s.yTop, barW, s.h, 4)} fill={s.fill} />
                    ) : (
                      <rect key={s.key} x={x} y={s.yTop} width={barW} height={s.h} fill={s.fill} />
                    ),
                  )}
                  {r.demand > 0 && (
                    <>
                      <line x1={cx(i) - tickW / 2} x2={cx(i) + tickW / 2} y1={sy(r.demand)} y2={sy(r.demand)} stroke="#fff" strokeWidth={5} strokeLinecap="round" />
                      <line x1={cx(i) - tickW / 2} x2={cx(i) + tickW / 2} y1={sy(r.demand)} y2={sy(r.demand)} stroke={INK} strokeWidth={2} strokeLinecap="round" />
                    </>
                  )}
                </g>
              );
            })}
            {rows.map((_, i) => (
              <text key={i} x={cx(i)} y={HEIGHT - 6} textAnchor="middle" className={`lc-tick${hover === i ? " on" : ""}`}>
                {letters ? MONTHS[i][0] : MONTHS[i]}
              </text>
            ))}
            {rows.map((_, i) => (
              <rect
                key={i}
                x={cx(i) - band / 2}
                y={TOP - 6}
                width={band}
                height={ph + BOTTOM + 6}
                fill="transparent"
                onPointerEnter={() => setHover(i)}
                onPointerDown={() => setHover(i)}
              />
            ))}
          </svg>
          {row && hover != null && (
            <div className={`lc-tip mchart-tip${hx > width * 0.55 ? " flip" : ""}`} style={{ left: hx }} aria-live="polite">
              <span className="lc-tip-x">{MONTH_NAMES[hover]}</span>
              {keys
                .slice()
                .reverse()
                .map((k) => (
                  <span key={k} className="lc-tip-row">
                    <svg width="12" height="6" viewBox="0 0 12 6" aria-hidden="true">
                      <path d="M1 3h10" stroke={color(k)} strokeWidth="2.4" strokeLinecap="round" />
                    </svg>
                    <strong>{fmtGwh(row.parts.find((p) => p.key === k)?.gwh ?? 0)}</strong>
                    <span className="lc-tip-unit">GWh</span>
                    <span className="lc-tip-name">{label(k)}</span>
                  </span>
                ))}
              <span className="lc-tip-row mchart-tip-demand">
                <svg width="12" height="6" viewBox="0 0 12 6" aria-hidden="true">
                  <path d="M1 3h10" stroke={INK} strokeWidth="2.4" strokeLinecap="round" />
                </svg>
                <strong>{fmtGwh(row.demand)}</strong>
                <span className="lc-tip-unit">GWh</span>
                <span className="lc-tip-name">Demand</span>
              </span>
              {row.short > 0 && (
                <span className="lc-tip-row mchart-tip-short">
                  <span className="sq gap-fill" style={{ width: 10, height: 10 }} />
                  <strong>{fmtGwh(row.short)}</strong>
                  <span>GWh short: the supply doesn't meet the demand</span>
                </span>
              )}
            </div>
          )}
        </div>
      )}

      <div className="legend-row">
        {keys.map((k) => (
          <span key={k}>
            <span className="sq" style={{ background: color(k) }} />
            {label(k)}
          </span>
        ))}
        <span>
          <svg width="14" height="8" viewBox="0 0 14 8" aria-hidden="true">
            <path d="M1 4h12" stroke={INK} strokeWidth="2.2" strokeLinecap="round" />
          </svg>
          Demand
        </span>
        {shortMonths.length > 0 && (
          <span>
            <span className="sq gap-fill" style={{ width: 10, height: 10 }} />
            <strong style={{ color: "#A12C22", fontWeight: 650 }}>
              Short in {shortMonths.length === 1 ? MONTHS[shortMonths[0]] : `${shortMonths.length} months`}
            </strong>
          </span>
        )}
      </div>
    </div>
  );
}

/** The chart's table view: every month's sources, demand and shortfall. */
function MonthTable({ title, rows, keys, label }: { title: string; rows: MonthRow[]; keys: string[]; label: (k: string) => string }) {
  const sum = (f: (r: MonthRow) => number) => rows.reduce((a, r) => a + f(r), 0);
  const anyShort = rows.some((r) => r.short > 0);
  return (
    <div className="ftable-wrap mchart-tablewrap" role="region" aria-label={`${title} by month`} tabIndex={0}>
      <table className="ftable">
        <thead>
          <tr>
            <th scope="col">Month</th>
            {keys.map((k) => (
              <th key={k} scope="col" className="n">
                {label(k)}
              </th>
            ))}
            <th scope="col" className="n">
              Demand
            </th>
            {anyShort && (
              <th scope="col" className="n">
                Short
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <th scope="row">{MONTHS[i]}</th>
              {keys.map((k) => (
                <td key={k} className="n">
                  {cellGwh(r.parts.find((p) => p.key === k)?.gwh ?? 0)}
                </td>
              ))}
              <td className="n">{cellGwh(r.demand)}</td>
              {anyShort && <td className={`n${r.short > 0 ? " short" : " nil"}`}>{r.short > 0 ? cellGwh(r.short) : "–"}</td>}
            </tr>
          ))}
          <tr className="total">
            <th scope="row">Year</th>
            {keys.map((k) => (
              <td key={k} className="n">
                {cellGwh(sum((r) => r.parts.find((p) => p.key === k)?.gwh ?? 0))}
              </td>
            ))}
            <td className="n">{cellGwh(sum((r) => r.demand))}</td>
            {anyShort && <td className="n short">{cellGwh(sum((r) => r.short))}</td>}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
