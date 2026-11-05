// The library's chart, one scenario at a time: cost (x: heat and cold, heat only or cold only)
// against CO₂ a year (y), bubble area the capital, and reliability as the fill: solid when any
// one unit can be out and every day is still met (N-1), a hollow ring when some cases leave a
// day short (thicker and darker with more), dashed red when the design broke a cap. The gas
// plant of the scenario is a dashed line: left of it is cheaper than gas. Lower left is cheaper
// and cleaner.
//
// Hover names a design; a click ticks it for the side by side. Keyboard: Tab into the chart,
// arrows move from design to design (cheapest first), Enter or Space ticks. The recommended
// design is drawn last and labelled; ticked ones wear an ink ring and their name.

import { useMemo, useState, type KeyboardEvent } from "react";

import { niceTicks, useWidth } from "../../components/LineChart";
import { isMenuKey, menuProps, openMenuAt, type MenuTarget } from "../../menu";
import type { LibraryRow } from "../../workbench";
import { CHART_X, fixed, fmtEur, fmtMeur, fmtT, fmtVsGas, finite, gasCost, isValid, reliabilityText, ringOf, type ChartX } from "./library";

interface Props {
  rows: LibraryRow[];
  x: ChartX;
  onX: (x: ChartX) => void;
  selected: string[];
  onToggle: (id: string) => void;
  /** The scenario's name, for the title. */
  scenario: string;
  /** Shown, or folded to its title row. */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** A bubble's context menu (right-click, or Shift+F10 on the design the arrows reached). */
  rowMenu?: (r: LibraryRow) => MenuTarget;
}

const H = 330;
const M = { top: 16, right: 16, bottom: 44, left: 66 };
const R_MAX = 17;
const R_MIN = 4.5;
const TEAL = "#0b8fa0";
const INK = "#11181c";
const RED = "#b42318";
const GREY = "#a9b4b8";

interface Point {
  r: LibraryRow;
  x: number;
  y: number;
  cx: number;
  cy: number;
  rad: number;
}

function tickText(v: number, step: number): string {
  return step >= 1 || Number.isInteger(v) ? fixed(v, Math.abs(v) >= 1000 ? 0 : step >= 1 ? 0 : 1) : fixed(v, 1);
}

/** A bubble as reliability fills it. */
function Mark({ p, lit }: { p: Point; lit: boolean }) {
  const { r, cx, cy, rad } = p;
  if (!isValid(r))
    return <circle cx={cx} cy={cy} r={rad} fill="#fff" fillOpacity={0.6} stroke={RED} strokeWidth={1.6} strokeDasharray="3 2.5" />;
  if (!r.firm || !r.firm.cases) return <circle cx={cx} cy={cy} r={rad} fill={GREY} fillOpacity={0.35} stroke={GREY} strokeWidth={1.2} strokeDasharray="2 2" />;
  if (r.firm.short === 0) return <circle cx={cx} cy={cy} r={rad} fill={TEAL} fillOpacity={lit ? 0.95 : 0.78} stroke="#fff" strokeWidth={1.5} />;
  const ring = ringOf(r.firm.short);
  return <circle cx={cx} cy={cy} r={Math.max(2.5, rad - ring.width / 2)} fill="#fff" fillOpacity={0.75} stroke={ring.color} strokeWidth={ring.width} />;
}

/** Labels beside the bubbles that carry one, nudged down where two would overlap. */
function placeLabels(items: { id: string; text: string; cx: number; cy: number; rad: number }[], width: number) {
  const out = new Map<string, { x: number; y: number; anchor: "start" | "end" }>();
  const boxes: { x0: number; x1: number; y0: number; y1: number }[] = [];
  for (const b of [...items].sort((p, q) => p.cy - q.cy)) {
    const w = b.text.length * 6.6 + 4;
    const gap = b.rad + 7;
    const right = b.cx + gap + w < width - 4;
    const x = right ? b.cx + gap : b.cx - gap;
    const x0 = right ? x : x - w;
    let y = b.cy + 4;
    for (let k = 0; k < 6 && boxes.some((o) => x0 < o.x1 && x0 + w > o.x0 && y - 11 < o.y1 && y + 3 > o.y0); k++) y += 14;
    boxes.push({ x0, x1: x0 + w, y0: y - 11, y1: y + 3 });
    out.set(b.id, { x, y, anchor: right ? "start" : "end" });
  }
  return out;
}

export function LibraryChart({ rows, x, onX, selected, onToggle, scenario, open, onOpenChange, rowMenu }: Props) {
  const [wrap, width] = useWidth(820);
  const [hover, setHover] = useState<string | null>(null);
  const [focus, setFocus] = useState<number | null>(null);
  const sel = useMemo(() => new Set(selected), [selected]);

  const chart = useMemo(() => {
    const pts = rows.filter((r) => finite(r[x]) && finite(r.co2_t));
    if (!pts.length) return null;
    const gas = gasCost(pts, x);
    const xs = pts.map((r) => r[x] as number);
    const ys = pts.map((r) => r.co2_t as number);
    const lo = Math.min(...xs, gas ?? Number.POSITIVE_INFINITY);
    const hi = Math.max(...xs, gas ?? Number.NEGATIVE_INFINITY);
    const xPad = Math.max(1, (hi - lo) * 0.06);
    const xt = niceTicks(Math.max(0, lo - xPad), hi + xPad, width < 560 ? 4 : 7);
    const yPad = Math.max(50, (Math.max(...ys) - Math.min(...ys)) * 0.1);
    const yt = niceTicks(Math.max(0, Math.min(...ys) - yPad), Math.max(...ys) + yPad, 5);
    const [x0, x1] = [xt[0], xt[xt.length - 1]];
    const [y0, y1] = [yt[0], yt[yt.length - 1]];
    const pw = Math.max(80, width - M.left - M.right);
    const ph = H - M.top - M.bottom;
    const sx = (v: number) => M.left + ((v - x0) / (x1 - x0 || 1)) * pw;
    const sy = (v: number) => M.top + ph - ((v - y0) / (y1 - y0 || 1)) * ph;
    const maxCap = Math.max(1, ...pts.map((r) => (finite(r.capex_meur) ? r.capex_meur : 0)));
    const points: Point[] = pts.map((r) => {
      const cap = finite(r.capex_meur) ? Math.max(0, r.capex_meur) : 0;
      return { r, x: r[x] as number, y: r.co2_t as number, cx: sx(r[x] as number), cy: sy(r.co2_t as number), rad: Math.max(R_MIN, R_MAX * Math.sqrt(cap / maxCap)) };
    });
    // Keyboard order: cheapest first.
    const order = [...points].sort((a, b) => a.x - b.x || a.y - b.y);
    return { xt, yt, sx, sy, pw, ph, points, order, gas, maxCap };
  }, [rows, x, width]);

  const xButtons = (
    <div className="lib-seg" role="radiogroup" aria-label="Cost on the horizontal axis">
      {(Object.keys(CHART_X) as ChartX[]).map((k) => (
        <button key={k} type="button" role="radio" aria-checked={x === k} className={x === k ? "is-on" : ""} onClick={() => onX(k)}>
          {CHART_X[k].label}
        </button>
      ))}
    </div>
  );

  const head = (
    <header className="lib-card-head">
      <div>
        <h2>Cost against CO₂</h2>
        <p className="lib-card-sub">
          {scenario} · {rows.length} design{rows.length === 1 ? "" : "s"}
          {open ? " · lower left is cheaper and cleaner · click a bubble to tick it" : ""}
        </p>
      </div>
      <div className="lib-chart-tools">
        {open && xButtons}
        <button type="button" className="link-btn lib-fold" aria-expanded={open} onClick={() => onOpenChange(!open)}>
          {open ? "Hide chart" : "Show chart"}
        </button>
      </div>
    </header>
  );

  if (!open)
    return (
      <section className="lib-card lib-chart is-folded" aria-label="Cost against CO₂">
        {head}
      </section>
    );

  if (!chart)
    return (
      <section className="lib-card lib-chart" aria-label="Cost against CO₂">
        {head}
        <p className="lib-note">
          {rows.length ? `None of these designs has a ${CHART_X[x].label.toLowerCase()} cost and a CO₂ figure to plot.` : "No design of this scenario matches the filters."}
        </p>
      </section>
    );

  const { xt, yt, sx, sy, pw, ph, points, order, gas, maxCap } = chart;
  const active = focus != null ? order[focus] : null;
  const shownId = hover ?? active?.r.id ?? null;
  const tip = points.find((p) => p.r.id === shownId) ?? null;
  // The recommended design is named; in a scenario without it, its search's best overall is.
  const hasRec = points.some((p) => p.r.recommended);
  const isBest = (p: Point) => !hasRec && p.r.picks?.includes("best");
  const labelled = points
    .filter((p) => p.r.recommended || isBest(p) || sel.has(p.r.id))
    .map((p) => ({
      id: p.r.id,
      text: `${p.r.uid || p.r.code}${p.r.recommended ? " · recommended" : isBest(p) ? " · best overall" : ""}`,
      cx: p.cx,
      cy: p.cy,
      rad: p.rad,
      rec: p.r.recommended || isBest(p),
    }));
  const labels = placeLabels(labelled, width);
  // Draw order: big first, then ticked, the best overall, the recommended last (on top).
  const top = (p: Point) => (p.r.recommended ? 3 : isBest(p) ? 2 : sel.has(p.r.id) ? 1 : 0);
  const drawn = [...points].sort((a, b) => top(a) - top(b) || b.rad - a.rad);
  const gx = gas != null ? sx(gas) : null;
  const xStep = xt.length > 1 ? xt[1] - xt[0] : 1;

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (isMenuKey(e) && active && rowMenu) {
      const box = e.currentTarget.getBoundingClientRect();
      const at = { left: box.left + active.cx - active.rad, top: box.top + active.cy - active.rad, width: active.rad * 2, height: active.rad * 2 };
      if (openMenuAt(rowMenu(active.r), at, e.currentTarget, true)) e.preventDefault();
      return;
    }
    const last = order.length - 1;
    const cur = focus ?? -1;
    let next: number | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = Math.min(last, cur + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = Math.max(0, cur - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = last;
    else if ((e.key === "Enter" || e.key === " ") && active) {
      e.preventDefault();
      onToggle(active.r.id);
      return;
    }
    if (next != null) {
      e.preventDefault();
      setFocus(next);
    }
  };

  // The size key: two capitals at the chart's own scale.
  const capKey = [maxCap / 4, maxCap].map((c) => Math.max(1, Math.round(c / 5) * 5 || Math.round(c)));
  const rOf = (cap: number) => Math.max(R_MIN, R_MAX * Math.sqrt(cap / maxCap));
  const describe = (p: Point) =>
    `${p.r.id}: ${CHART_X[x].label.toLowerCase()} ${fmtEur(p.x)} €/MWh, CO₂ ${fmtT(p.y)} t a year, capital ${fmtMeur(p.r.capex_meur)} M€, ${reliabilityText(p.r.firm)}${p.r.recommended ? ", recommended" : ""}${sel.has(p.r.id) ? ", ticked" : ""}`;

  return (
    <section className="lib-card lib-chart" aria-label="Cost against CO₂">
      {head}
      <div className="lib-chart-body">
        <div
          className="lib-plot"
          ref={wrap}
          tabIndex={0}
          role="group"
          aria-label={`Chart of ${points.length} designs in ${scenario}. Arrow keys move between designs, cheapest first; Enter ticks one to compare.`}
          onKeyDown={onKey}
          onFocus={() => setFocus((f) => f ?? Math.max(0, order.findIndex((p) => p.r.recommended)))}
          onBlur={() => setFocus(null)}
        >
          <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} aria-hidden="true">
            <g className="lib-grid">
              {yt.map((t) => (
                <line key={`y${t}`} x1={M.left} x2={M.left + pw} y1={sy(t)} y2={sy(t)} />
              ))}
              {xt.map((t) => (
                <line key={`x${t}`} x1={sx(t)} x2={sx(t)} y1={M.top} y2={M.top + ph} />
              ))}
            </g>
            <g className="lib-ticks">
              {yt.map((t) => (
                <text key={`y${t}`} x={M.left - 8} y={sy(t) + 4} textAnchor="end">
                  {fmtT(t)}
                </text>
              ))}
              {xt.map((t, i) => (
                <text key={`x${t}`} x={sx(t)} y={M.top + ph + 18} textAnchor={i === xt.length - 1 ? "end" : i === 0 ? "start" : "middle"}>
                  {tickText(t, xStep)}
                </text>
              ))}
              <text x={M.left + pw} y={H - 6} textAnchor="end" className="lib-axis-title">
                {CHART_X[x].title} →
              </text>
            </g>
            <text className="lib-axis-title" x={14} y={M.top + ph / 2} textAnchor="middle" transform={`rotate(-90 14 ${M.top + ph / 2})`}>
              CO₂, t a year →
            </text>
            {gx != null && (
              <g className="lib-gas">
                <line x1={gx} x2={gx} y1={M.top} y2={M.top + ph} />
                <text x={gx + (gx > M.left + pw - 150 ? -6 : 6)} y={M.top + 12} textAnchor={gx > M.left + pw - 150 ? "end" : "start"}>
                  gas {fmtEur(gas)}
                </text>
              </g>
            )}
            {drawn.map((p) => {
              const lit = shownId === p.r.id;
              const on = sel.has(p.r.id);
              return (
                <g
                  key={p.r.id}
                  data-id={p.r.id}
                  className={`lib-bub${lit ? " is-lit" : ""}${shownId && !lit ? " is-dim" : ""}`}
                  onPointerEnter={() => setHover(p.r.id)}
                  onPointerLeave={() => setHover(null)}
                  onClick={() => onToggle(p.r.id)}
                  {...(rowMenu ? menuProps(() => rowMenu(p.r)) : {})}
                >
                  <circle cx={p.cx} cy={p.cy} r={Math.max(p.rad, 11)} fill="transparent" />
                  {(p.r.recommended || isBest(p)) && <circle cx={p.cx} cy={p.cy} r={p.rad + (on ? 8 : 4.5)} fill="none" stroke={TEAL} strokeWidth={1.75} />}
                  {on && <circle cx={p.cx} cy={p.cy} r={p.rad + 4} fill="none" stroke={INK} strokeWidth={2} />}
                  <Mark p={p} lit={lit} />
                  {active?.r.id === p.r.id && <circle cx={p.cx} cy={p.cy} r={p.rad + 11} fill="none" stroke={INK} strokeWidth={1.5} strokeDasharray="3 3" />}
                </g>
              );
            })}
            <g className="lib-labels">
              {labelled.map((b) => {
                const l = labels.get(b.id)!;
                return (
                  <text key={b.id} x={l.x} y={l.y} textAnchor={l.anchor} className={b.rec ? "is-rec" : undefined}>
                    {b.text}
                  </text>
                );
              })}
            </g>
          </svg>
          {tip && (
            <div className={`lib-tip${tip.cx > width * 0.62 ? " flip" : ""}${tip.cy < H * 0.4 ? " below" : ""}`} style={{ left: tip.cx, top: tip.cy }} role="presentation">
              <strong>
                {tip.r.uid ? `${tip.r.uid} · ` : ""}
                {tip.r.code}
              </strong>
              {tip.r.recommended && <span className="lib-tip-rec">recommended</span>}
              <span className="lib-tip-row">
                <span>{CHART_X[x].label}</span>
                <b>
                  {fmtEur(tip.x)} €/MWh <small>{fmtVsGas(tip.r.vs_gas_pct?.[CHART_X[x].vs])} vs gas</small>
                </b>
              </span>
              <span className="lib-tip-row">
                <span>CO₂</span>
                <b>{fmtT(tip.y)} t a year</b>
              </span>
              <span className="lib-tip-row">
                <span>Capital</span>
                <b>{fmtMeur(tip.r.capex_meur)} M€</b>
              </span>
              <span className="lib-tip-row">
                <span>One unit out</span>
                <b>{isValid(tip.r) ? reliabilityText(tip.r.firm) : "broke a cap"}</b>
              </span>
              <span className="lib-tip-hint">{sel.has(tip.r.id) ? "Ticked · click to untick" : "Click to tick for the side by side"}</span>
            </div>
          )}
          <span className="sr-only" aria-live="polite">
            {active ? describe(active) : ""}
          </span>
        </div>
        <aside className="lib-legend" aria-label="How to read the chart">
          <p className="lib-legend-cap">Fill: one unit out (N-1)</p>
          <span className="lib-legend-row">
            <svg width="22" height="22" aria-hidden="true">
              <circle cx="11" cy="11" r="8" fill={TEAL} fillOpacity={0.78} />
            </svg>
            N-1 met: any one unit out, every day met
          </span>
          <span className="lib-legend-row">
            <svg width="22" height="22" aria-hidden="true">
              <circle cx="11" cy="11" r={8 - ringOf(1).width / 2} fill="#fff" stroke={ringOf(1).color} strokeWidth={ringOf(1).width} />
            </svg>
            1 case short
          </span>
          <span className="lib-legend-row">
            <svg width="22" height="22" aria-hidden="true">
              <circle cx="11" cy="11" r={8 - ringOf(6).width / 2} fill="#fff" stroke={ringOf(6).color} strokeWidth={ringOf(6).width} />
            </svg>
            more cases short: a thicker, darker ring
          </span>
          {points.some((p) => !isValid(p.r)) && (
            <span className="lib-legend-row">
              <svg width="22" height="22" aria-hidden="true">
                <circle cx="11" cy="11" r="8" fill="#fff" stroke={RED} strokeWidth={1.6} strokeDasharray="3 2.5" />
              </svg>
              broke a cap
            </span>
          )}
          {points.some((p) => isValid(p.r) && (!p.r.firm || !p.r.firm.cases)) && (
            <span className="lib-legend-row">
              <svg width="22" height="22" aria-hidden="true">
                <circle cx="11" cy="11" r="8" fill={GREY} fillOpacity={0.35} stroke={GREY} strokeDasharray="2 2" />
              </svg>
              not checked with one unit out
            </span>
          )}
          <p className="lib-legend-cap">Area: capital</p>
          <span className="lib-legend-row">
            <svg width={rOf(capKey[0]) * 2 + rOf(capKey[1]) * 2 + 8} height={rOf(capKey[1]) * 2 + 2} aria-hidden="true">
              <circle cx={rOf(capKey[0]) + 1} cy={rOf(capKey[1]) * 2 + 1 - rOf(capKey[0])} r={rOf(capKey[0])} fill="none" stroke="#8a959e" />
              <circle cx={rOf(capKey[0]) * 2 + 6 + rOf(capKey[1])} cy={rOf(capKey[1]) + 1} r={rOf(capKey[1])} fill="none" stroke="#8a959e" />
            </svg>
            {capKey[0]} and {capKey[1]} M€
          </span>
          <p className="lib-legend-cap">Marks</p>
          <span className="lib-legend-row">
            <svg width="22" height="22" aria-hidden="true">
              <circle cx="11" cy="11" r="5" fill={TEAL} fillOpacity={0.78} />
              <circle cx="11" cy="11" r="9.5" fill="none" stroke={TEAL} strokeWidth={1.75} />
            </svg>
            {hasRec ? "the recommended design" : "the best overall of this scenario"}
          </span>
          <span className="lib-legend-row">
            <svg width="22" height="22" aria-hidden="true">
              <circle cx="11" cy="11" r="5" fill={TEAL} fillOpacity={0.78} />
              <circle cx="11" cy="11" r="9" fill="none" stroke={INK} strokeWidth={2} />
            </svg>
            ticked to compare
          </span>
          {gas != null && (
            <span className="lib-legend-row">
              <svg width="22" height="22" aria-hidden="true">
                <line x1="11" x2="11" y1="2" y2="20" stroke="#8a959e" strokeWidth={1.25} strokeDasharray="4 3" />
              </svg>
              gas boilers and electric chillers: {fmtEur(gas)} €/MWh
            </span>
          )}
        </aside>
      </div>
    </section>
  );
}
