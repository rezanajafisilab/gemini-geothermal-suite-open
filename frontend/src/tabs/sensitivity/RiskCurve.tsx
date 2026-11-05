// The N-1 or risk figure (4 Nov: it was a stretched 400 × 110 drawing, blurry, with no axes): the
// days short of heat a year at each backup size tried, drawn at the figure's own pixel width so
// it stays crisp. The x axis is the backup's size in MW; the y axis the days short of heat a
// year, on a log scale (the sizes near the target differ by hundredths of a day, the smallest by
// days), with no days short on a row of its own at the foot. The dashed line is one day in ten
// years; the N-1 size and the size by risk are marked and named. Each dot reads out on hover or
// focus; a table under the figure (for screen readers) has every size tried.

import { useState } from "react";

import { niceTicks, useWidth } from "../../components/LineChart";
import type { RiskView } from "../../workbench";

const HEIGHT = 250;
const TOP = 18;
const RIGHT = 18;
const BOTTOM = 46;
const LEFT = 62;
const ZERO_GAP = 18; // the "none" row under the log scale's lowest decade

const fmt = (x: number, d = 0) => x.toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: 0 });
/** Days as read: three decimals under one day, else one; "none" for 0. */
export const daysWords = (d: number) => (d <= 0 ? "none" : d < 0.01 ? "under 0.01" : fmt(d, d < 1 ? 3 : 1));

export interface RiskGeometry {
  width: number;
  left: number;
  right: number;
  top: number;
  /** The log scale's foot (its lowest decade) and the row of no days short under it. */
  floorY: number;
  zeroY: number;
  x: (mw: number) => number;
  y: (days: number) => number;
  xTicks: number[];
  /** The y ticks: 0 (none) then each decade, with their labels. */
  yTicks: { days: number; label: string }[];
  points: { mw: number; days: number }[];
}

/** The figure's scales and ticks at a width (pure: the tests read it). */
export function riskGeometry(view: RiskView, width: number): RiskGeometry {
  const points = [...view.tried].map(([mw, days]) => ({ mw, days: Math.max(0, days) })).sort((a, b) => a.mw - b.mw);
  const mws = [...points.map((p) => p.mw), view.n1_mw, view.risk_mw];
  const lo = Math.min(...mws);
  const hi = Math.max(...mws);
  const pad = (hi - lo || 1) * 0.04;
  const x0 = lo - pad;
  const x1 = hi + pad;
  const right = width - RIGHT;
  const x = (mw: number) => LEFT + ((mw - x0) / (x1 - x0)) * (right - LEFT);
  const xTicks = niceTicks(lo, hi, Math.max(2, Math.min(7, Math.floor((right - LEFT) / 70)))).filter((t) => t >= x0 && t <= x1);

  // Decades from below the smallest days short (and the target) to above the largest.
  const positive = [...points.map((p) => p.days), view.at_risk.lole_days, view.at_n1.lole_days].filter((d) => d > 0);
  const minExp = Math.max(-3, Math.floor(Math.log10(Math.min(view.target_days, ...positive))));
  const maxExp = Math.max(minExp + 1, Math.ceil(Math.log10(Math.max(view.target_days * 10, ...positive))));
  const zeroY = HEIGHT - BOTTOM;
  const floorY = zeroY - ZERO_GAP;
  const y = (days: number) => (days <= 0 ? zeroY : floorY - ((Math.max(minExp, Math.log10(days)) - minExp) / (maxExp - minExp)) * (floorY - TOP));
  const yTicks = [{ days: 0, label: "0" }];
  for (let e = minExp; e <= maxExp; e++) yTicks.push({ days: 10 ** e, label: fmt(10 ** e, Math.max(0, -e)) });
  return { width, left: LEFT, right, top: TOP, floorY, zeroY, x, y, xTicks, yTicks, points };
}

type Box = [number, number, number, number]; // x0, y0, x1, y1

/**
 * Where a mark's name goes: the first place beside the point (above or below, left or right, a
 * step further out) whose text keeps clear of the line, the dots and the boxes already taken, and
 * inside the plot; else the place that touches least. The text's width is estimated.
 */
export function placeName(px: number, py: number, text: string, line: [number, number][], taken: Box[], plot: Box): { x: number; y: number; anchor: "start" | "end"; box: Box } {
  const w = text.length * 6.6;
  const h = 13;
  const spots: [number, number, "start" | "end"][] = [
    [-9, -12, "end"],
    [-9, 21, "end"],
    [9, -12, "start"],
    [9, 21, "start"],
    [-12, 4, "end"],
    [12, 4, "start"],
    [-5, -30, "end"],
    [5, -30, "start"],
    [-5, -48, "end"],
    [5, -48, "start"],
  ];
  // The line as points every 3 px, the dots with them.
  const marks: [number, number][] = [];
  line.forEach(([x, y], i) => {
    marks.push([x, y]);
    const next = line[i + 1];
    if (!next) return;
    const steps = Math.ceil(Math.hypot(next[0] - x, next[1] - y) / 3);
    for (let k = 1; k < steps; k++) marks.push([x + ((next[0] - x) * k) / steps, y + ((next[1] - y) * k) / steps]);
  });
  let best: { x: number; y: number; anchor: "start" | "end"; box: Box } | null = null;
  let fewest = Infinity;
  for (const [dx, dy, anchor] of spots) {
    const x = px + dx;
    const y = py + dy;
    const box: Box = anchor === "end" ? [x - w, y - h + 3, x, y + 3] : [x, y - h + 3, x + w, y + 3];
    const outside = box[0] < plot[0] || box[2] > plot[2] || box[1] < plot[1] || box[3] > plot[3];
    const hits = marks.filter(([mx, my]) => mx >= box[0] - 3 && mx <= box[2] + 3 && my >= box[1] - 3 && my <= box[3] + 3).length + taken.filter((t) => !(t[2] < box[0] || t[0] > box[2] || t[3] < box[1] || t[1] > box[3])).length * 50 + (outside ? 1000 : 0);
    if (hits === 0) return { x, y, anchor, box };
    if (hits < fewest) (fewest = hits), (best = { x, y, anchor, box });
  }
  return best!;
}

export function RiskCurve({ view }: { view: RiskView }) {
  const [wrap, width] = useWidth(560);
  const [hover, setHover] = useState<number | null>(null);
  const g = riskGeometry(view, width);
  const unit = view.unit_words;
  const ty = g.y(view.target_days);
  const xy = g.points.map((p) => [g.x(p.mw), g.y(p.days)] as [number, number]);
  // Between sizes with days short the line is solid; into the row of none (off the log scale)
  // it is dashed.
  const solid = g.points
    .map((p, i) => (i && p.days > 0 && g.points[i - 1].days > 0 ? `M${xy[i - 1][0].toFixed(1)} ${xy[i - 1][1].toFixed(1)}L${xy[i][0].toFixed(1)} ${xy[i][1].toFixed(1)}` : ""))
    .join("");
  const broken = g.points
    .map((p, i) => (i && (p.days <= 0 || g.points[i - 1].days <= 0) ? `M${xy[i - 1][0].toFixed(1)} ${xy[i - 1][1].toFixed(1)}L${xy[i][0].toFixed(1)} ${xy[i][1].toFixed(1)}` : ""))
    .join("");
  const n1 = { x: g.x(view.n1_mw), y: g.y(view.at_n1.lole_days) };
  const risk = { x: g.x(view.risk_mw), y: g.y(view.at_risk.lole_days) };
  const same = Math.abs(view.n1_mw - view.risk_mw) < 1e-6;
  // The names: the target's at the left over its line, then N-1's and the risk's, each clear of
  // the line and of the names before it.
  const plot: Box = [g.left, g.top - 4, g.right, g.zeroY + 2];
  const targetText = `One day in ten years (${fmt(view.target_days, 2)} a year)`;
  const targetBox: Box = [g.left + 6, ty - 17, g.left + 6 + targetText.length * 6.2, ty - 3];
  const n1Text = `${same ? "N-1 and by risk" : "N-1"} · ${fmt(view.n1_mw, 1)} MW`;
  const n1Name = placeName(n1.x, n1.y, n1Text, xy, [targetBox], plot);
  const riskText = `By risk · ${fmt(view.risk_mw, 1)} MW`;
  const riskName = same ? null : placeName(risk.x, risk.y, riskText, xy, [targetBox, n1Name.box], plot);
  const tip = hover != null ? g.points[hover] : null;
  return (
    <figure className="risk-curve" aria-labelledby="risk-curve-cap">
      <div ref={wrap} className="risk-plot">
        <svg width={width} height={HEIGHT} role="img" aria-label={`Days short of heat a year against the ${unit}'s size, ${fmt(g.points[0]?.mw ?? 0, 1)} to ${fmt(g.points.at(-1)?.mw ?? 0, 1)} MW. N-1: ${fmt(view.n1_mw, 1)} MW, ${daysWords(view.at_n1.lole_days)} days. By risk: ${fmt(view.risk_mw, 1)} MW, ${daysWords(view.at_risk.lole_days)} days.`}>
          {/* The y axis: a log scale of days, and the row of none at its foot. */}
          {g.yTicks.map((t) => {
            const yy = g.y(t.days);
            return (
              <g key={t.label}>
                <line x1={g.left} x2={g.right} y1={yy} y2={yy} className={t.days === 0 ? "lc-axis" : "lc-grid"} />
                <text x={g.left - 8} y={yy} dy="0.32em" textAnchor="end" className="lc-tick">
                  {t.label}
                </text>
              </g>
            );
          })}
          <text className="risk-axis-name" transform={`translate(14 ${(g.top + g.zeroY) / 2}) rotate(-90)`} textAnchor="middle">
            Days short of heat a year
          </text>
          {/* The x axis: the backup's size. */}
          {g.xTicks.map((t) => (
            <g key={t}>
              <line x1={g.x(t)} x2={g.x(t)} y1={g.zeroY} y2={g.zeroY + 4} className="lc-axis" />
              <text x={g.x(t)} y={g.zeroY + 17} textAnchor="middle" className="lc-tick">
                {fmt(t, 1)}
              </text>
            </g>
          ))}
          <text className="risk-axis-name" x={(g.left + g.right) / 2} y={HEIGHT - 6} textAnchor="middle">
            Backup size: the {unit}, MW
          </text>
          {/* One day in ten years. */}
          <line x1={g.left} x2={g.right} y1={ty} y2={ty} className="risk-target" />
          <text x={g.left + 6} y={ty - 6} className="risk-target-name">
            {targetText}
          </text>
          <path d={solid} className="risk-line" />
          <path d={broken} className="risk-line is-broken" />
          {g.points.map((p, i) => (
            <circle key={p.mw} cx={g.x(p.mw)} cy={g.y(p.days)} r={4} className={`risk-dot${hover === i ? " is-hover" : ""}`} />
          ))}
          {/* N-1 and the size by risk, marked and named. */}
          <circle cx={n1.x} cy={n1.y} r={6.5} className="risk-mark n1" />
          <text x={n1Name.x} y={n1Name.y} textAnchor={n1Name.anchor} className="risk-mark-name">
            {n1Text}
          </text>
          {riskName && (
            <>
              <circle cx={risk.x} cy={risk.y} r={6.5} className="risk-mark pick" />
              <text x={riskName.x} y={riskName.y} textAnchor={riskName.anchor} className="risk-mark-name">
                {riskText}
              </text>
            </>
          )}
          {/* Hit areas: bigger than the dots, each reads out its size and days. */}
          {g.points.map((p, i) => (
            <circle
              key={`hit-${p.mw}`}
              cx={g.x(p.mw)}
              cy={g.y(p.days)}
              r={12}
              fill="transparent"
              tabIndex={0}
              aria-label={`${fmt(p.mw, 2)} MW: ${daysWords(p.days)} days short a year`}
              onPointerEnter={() => setHover(i)}
              onPointerLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
            />
          ))}
        </svg>
        {tip && (
          <div className={`lc-tip risk-tip${g.x(tip.mw) > width * 0.6 ? " flip" : ""}`} style={{ left: g.x(tip.mw), top: Math.max(0, g.y(tip.days) - 30) }} aria-hidden="true">
            <span className="lc-tip-x">{fmt(tip.mw, 2)} MW</span>
            <span className="lc-tip-row">
              <strong>{daysWords(tip.days)}</strong>
              <span className="lc-tip-unit">days short a year</span>
            </span>
          </div>
        )}
      </div>
      <figcaption id="risk-curve-cap">Each dot is a {unit} size run over the drawn years. Under the dashed line, heat runs short less than one day in ten years.</figcaption>
      <table className="sr-only">
        <caption>Days short of heat a year at each {unit} size tried</caption>
        <thead>
          <tr>
            <th scope="col">Size, MW</th>
            <th scope="col">Days short a year</th>
          </tr>
        </thead>
        <tbody>
          {g.points.map((p) => (
            <tr key={p.mw}>
              <td>{fmt(p.mw, 2)}</td>
              <td>{daysWords(p.days)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
