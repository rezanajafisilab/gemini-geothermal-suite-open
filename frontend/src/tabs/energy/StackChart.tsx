// A stacked area of daily MW by source with the demand as a line and any shortfall hatched, drawn
// by hand in SVG. The year chart passes the days in date order; the load-duration curve passes
// them highest demand first. A crosshair reads every source at the day under the pointer, or at
// the day picked with the arrow keys (Shift: a week, Page Up/Down: a month).

import { useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";

import { niceTicks, useWidth } from "../../components/LineChart";
import { isMenuKey, menuProps, openMenuAt, type MenuTarget } from "../../menu";
import { fmtNum } from "../../workbench";
import { INK, SOURCE_META, stackTops, type DayRow } from "./model";
import { HatchPattern, useSvgId } from "./parts";

export interface XTick {
  /** Row index (fractional allowed). */
  at: number;
  label: string;
  /** Draw a vertical grid line here. */
  grid?: boolean;
}

interface Props {
  rows: DayRow[];
  /** The source keys, in the order of each row's parts (bottom of the stack first). */
  keys: string[];
  /** Which keys to draw (the ones that supply anything). */
  active: number[];
  height: number;
  ticks: (plotWidth: number, n: number) => XTick[];
  /** The readout's title and sub line for row i. */
  title: (row: DayRow, i: number) => string;
  sub?: (row: DayRow, i: number) => string | null;
  /** What the chart shows, for screen readers (the keys are described there too). */
  summary: string;
  /** Label the highest-demand point (the year chart). */
  markPeak?: boolean;
  /** Under the x axis. */
  xCaption?: string;
  /** A day's context menu (right-click on the chart, or Shift+F10 on the day the arrows read), with the day's values in words. */
  dayMenu?: (row: DayRow, i: number, values: string) => MenuTarget | null;
}

const TOP = 14;
const BOTTOM = 24;
const RIGHT = 10;
const MW = (v: number) => fmtNum(v, v >= 10 ? 1 : 2);

export function StackChart({ rows, keys, active, height, ticks, title, sub, summary, markPeak = false, xCaption, dayMenu }: Props) {
  const [wrap, width] = useWidth(720);
  const [hover, setHover] = useState<number | null>(null);
  const hatch = useSvgId("short");
  const n = rows.length;

  const geo = useMemo(() => {
    const top = Math.max(0, ...rows.map((r) => Math.max(r.demand, r.supplied)));
    const yt = niceTicks(0, top || 1, height < 200 ? 3 : 4);
    const ymax = yt[yt.length - 1] || 1;
    const ylabels = yt.map((t) => fmtNum(t));
    const left = Math.max(28, Math.max(...ylabels.map((l) => l.length)) * 6.6 + 12);
    const pw = Math.max(10, width - left - RIGHT);
    const ph = height - TOP - BOTTOM;
    const x = (i: number) => left + (n <= 1 ? pw / 2 : (i / (n - 1)) * pw);
    const y = (v: number) => TOP + ph - (Math.max(0, v) / ymax) * ph;
    const tops = stackTops(rows, keys.length);
    const line = (vals: number[]) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
    const back = (vals: number[]) =>
      vals
        .map((_, j) => {
          const i = vals.length - 1 - j;
          return `L${x(i).toFixed(1)} ${y(vals[i]).toFixed(1)}`;
        })
        .join("");
    const zeros = new Array<number>(n).fill(0);
    const layers = active.map((k, j) => {
      const below = j === 0 ? zeros : tops[active[j - 1]];
      return { key: keys[k], top: tops[k], d: `${line(tops[k])}${back(below)}Z` };
    });
    const supplied = rows.map((r) => r.supplied);
    const shortTop = rows.map((r) => (r.unmet > 0 ? r.demand : r.supplied));
    const anyShort = rows.some((r) => r.unmet > 0);
    return {
      yt,
      ylabels,
      left,
      pw,
      ph,
      x,
      y,
      layers,
      shortPath: anyShort ? `${line(shortTop)}${back(supplied)}Z` : null,
      demandPath: line(rows.map((r) => r.demand)),
      xticks: ticks(pw, n),
    };
  }, [rows, keys, active, width, height, n, ticks]);

  if (!n) return null;
  const { yt, ylabels, left, pw, ph, x, y, layers, shortPath, demandPath, xticks } = geo;

  const pick = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - box.left;
    const i = Math.round(((px - left) / pw) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };
  const dayTarget = (i: number) => (dayMenu ? dayMenu(rows[i], i, readout(rows[i], i, keys, active.slice().reverse(), title, sub)) : null);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (isMenuKey(e) && hover != null) {
      const t = dayTarget(hover);
      const box = e.currentTarget.getBoundingClientRect();
      if (t && openMenuAt(t, { left: box.left + x(hover) - 1, top: box.top + TOP, width: 2, height: ph }, e.currentTarget, true)) e.preventDefault();
      return;
    }
    const step = e.shiftKey ? 7 : 1;
    const moves: Record<string, number> = { ArrowLeft: -step, ArrowRight: step, PageUp: -30, PageDown: 30 };
    if (e.key in moves) setHover((h) => Math.max(0, Math.min(n - 1, (h ?? (moves[e.key] > 0 ? -1 : n)) + moves[e.key])));
    else if (e.key === "Home") setHover(0);
    else if (e.key === "End") setHover(n - 1);
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  const peak = markPeak ? rows.reduce((b, r, i) => (r.demand > rows[b].demand ? i : b), 0) : -1;
  const row = hover != null ? rows[hover] : null;
  const hx = hover != null ? x(hover) : 0;
  const shown = active.slice().reverse();
  const live = row && hover != null ? readout(row, hover, keys, shown, title, sub) : "";
  const peakRight = peak >= 0 && x(peak) < left + pw - 150;

  return (
    <div ref={wrap} className="ee-stack">
      <div
        className="ee-plot"
        tabIndex={0}
        role="group"
        aria-label={`${summary} Arrow keys read one day at a time.`}
        onKeyDown={onKey}
        onBlur={() => setHover(null)}
      >
        <svg
          width={width}
          height={height}
          aria-hidden="true"
          onPointerMove={pick}
          onPointerDown={pick}
          onPointerLeave={() => setHover(null)}
          onContextMenu={(e) => {
            const box = e.currentTarget.getBoundingClientRect();
            const t = dayTarget(Math.max(0, Math.min(n - 1, Math.round(((e.clientX - box.left - left) / pw) * (n - 1)))));
            if (t) menuProps(t).onContextMenu(e);
          }}
        >
          <defs>
            <HatchPattern id={hatch} />
          </defs>
          {yt.map((t, k) => (
            <g key={t}>
              <line x1={left} x2={left + pw} y1={y(t)} y2={y(t)} className={t === 0 ? "lc-axis" : "lc-grid"} />
              <text x={left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="lc-tick">
                {ylabels[k]}
              </text>
            </g>
          ))}
          {xticks
            .filter((t) => t.grid)
            .map((t) => (
              <line key={`g${t.at}`} x1={x(t.at)} x2={x(t.at)} y1={TOP} y2={TOP + ph} className="lc-grid" />
            ))}
          {layers.map((l) => (
            <path key={l.key} d={l.d} fill={SOURCE_META[l.key]?.color ?? "#B3BAB2"} />
          ))}
          {/* The 2px surface gap between stacked bands. */}
          {layers.slice(0, -1).map((l) => (
            <path key={`sep-${l.key}`} d={l.top.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("")} fill="none" stroke="#fff" strokeWidth={1.5} strokeLinejoin="round" />
          ))}
          {shortPath && <path d={shortPath} fill={`url(#${hatch})`} />}
          <path d={demandPath} fill="none" stroke="#fff" strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" opacity={0.85} />
          <path d={demandPath} fill="none" stroke={INK} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {peak >= 0 && hover == null && (
            <g>
              <circle cx={x(peak)} cy={y(rows[peak].demand)} r={4} fill={INK} stroke="#fff" strokeWidth={2} />
              <text x={x(peak) + (peakRight ? 7 : -7)} y={y(rows[peak].demand) - 9} textAnchor={peakRight ? "start" : "end"} className="lc-label">
                Peak {MW(rows[peak].demand)} MW, {title(rows[peak], peak)}
              </text>
            </g>
          )}
          {xticks.map((t) => (
            <text key={`t${t.at}-${t.label}`} x={x(t.at)} y={height - 6} textAnchor="middle" className="lc-tick">
              {t.label}
            </text>
          ))}
          {row && hover != null && (
            <g>
              <line x1={hx} x2={hx} y1={TOP - 4} y2={TOP + ph} className="lc-cross" />
              {shown.map((k) => {
                const v = stackTop(row, k);
                return (row.parts[k] ?? 0) > 0 ? <circle key={k} cx={hx} cy={y(v)} r={3.5} fill={SOURCE_META[keys[k]]?.color} stroke="#fff" strokeWidth={2} /> : null;
              })}
              <circle cx={hx} cy={y(row.demand)} r={4} fill={INK} stroke="#fff" strokeWidth={2} />
            </g>
          )}
        </svg>
        {row && hover != null && (
          <div className={`ee-tip${hx > left + pw * 0.6 ? " flip" : ""}`} style={{ left: hx }} aria-hidden="true">
            <span className="ee-tip-title">{title(row, hover)}</span>
            {sub && sub(row, hover) && <span className="ee-tip-sub">{sub(row, hover)}</span>}
            {shown.map((k) => (
              <span key={k} className="ee-tip-row">
                <svg width="12" height="6" viewBox="0 0 12 6" aria-hidden="true">
                  <path d="M1 3h10" stroke={SOURCE_META[keys[k]]?.color} strokeWidth="2.4" strokeLinecap="round" />
                </svg>
                <strong>{MW(row.parts[k] ?? 0)}</strong>
                <span className="u">MW</span>
                <span className="n">{SOURCE_META[keys[k]]?.label ?? keys[k]}</span>
              </span>
            ))}
            <span className="ee-tip-row total">
              <svg width="12" height="6" viewBox="0 0 12 6" aria-hidden="true">
                <path d="M1 3h10" stroke={INK} strokeWidth="2.4" strokeLinecap="round" />
              </svg>
              <strong>{MW(row.demand)}</strong>
              <span className="u">MW</span>
              <span className="n">Demand</span>
            </span>
            {row.unmet > 0 && (
              <span className="ee-tip-row short">
                <span className="ee-swatch ee-hatch" aria-hidden="true" />
                <strong>{MW(row.unmet)}</strong>
                <span className="n">MW not covered</span>
              </span>
            )}
          </div>
        )}
        <span className="ee-sr" aria-live="polite">
          {live}
        </span>
      </div>
      {xCaption && <p className="ee-xcap">{xCaption}</p>}
    </div>
  );

  function stackTop(r: DayRow, k: number) {
    let cum = 0;
    for (const j of active) {
      cum += r.parts[j] ?? 0;
      if (j === k) break;
    }
    return cum;
  }
}

function readout(row: DayRow, i: number, keys: string[], shown: number[], title: Props["title"], sub: Props["sub"]): string {
  const parts = shown.map((k) => `${SOURCE_META[keys[k]]?.label ?? keys[k]} ${MW(row.parts[k] ?? 0)} MW`).join(", ");
  const s = sub?.(row, i);
  return `${title(row, i)}${s ? ` (${s})` : ""}: ${parts}; demand ${MW(row.demand)} MW${row.unmet > 0 ? `, ${MW(row.unmet)} MW not covered` : ""}.`;
}
