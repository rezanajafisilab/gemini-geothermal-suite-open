// A file's columns as a line chart (FileView.chart), drawn by hand in SVG: one y axis, month
// ticks for dates, a crosshair that reads every series at the nearest x (mouse or arrow keys),
// and legend toggles. Series of another unit than the axis's are off: picking one swaps the axis,
// never a second one. The Table tab is the chart's table view.
//
// Colours are the dataviz reference palette (validated on the white card; the app has no dark
// theme). Blue reads as cold and orange as heat here, as in the result card's splits, so cooling
// and heat series take those two slots; any three lines on screen stay within the first three
// slots, which pass all-pairs.

import { useEffect, useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";

import type { FileView } from "../agent/types";

type Chart = NonNullable<FileView["chart"]>;

const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const MAX_SERIES = PALETTE.length;
const HEIGHT = 260;
const TOP = 24;
const RIGHT = 14;
const BOTTOM = 26;

export function seriesColors(names: string[]): string[] {
  const role: number[] = names.map((n) => (/cool|cold|chill/i.test(n) ? 0 : /heat/i.test(n) ? 1 : -1));
  const order = role.some((r) => r >= 0) ? [2, 0, 1, 3, 4, 5, 6, 7] : [0, 1, 2, 3, 4, 5, 6, 7];
  const taken = new Set<number>();
  const slots = role.map((r) => (r >= 0 && !taken.has(r) ? (taken.add(r), r) : -1));
  return slots.map((s) => {
    if (s < 0) {
      s = order.find((k) => !taken.has(k)) ?? 0;
      taken.add(s);
    }
    return PALETTE[s];
  });
}

/** Round tick values covering lo..hi, about `count` of them. */
export function niceTicks(lo: number, hi: number, count = 5): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1];
  if (hi === lo) {
    hi = lo + (Math.abs(lo) || 1);
    lo = lo > 0 ? 0 : lo - 1;
  }
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const f = raw / mag;
  const step = (f >= Math.sqrt(50) ? 10 : f >= Math.sqrt(10) ? 5 : f >= Math.sqrt(2) ? 2 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.floor(lo / step) * step; v <= Math.ceil(hi / step) * step + step / 2; v += step) out.push(Number(v.toFixed(10)));
  return out;
}

function fmtTick(v: number, step: number): string {
  if (Math.abs(v) >= 1000) return `${Number((v / 1000).toFixed(Math.abs(step) >= 1000 ? 0 : 1))}K`;
  const digits = Math.max(0, Math.min(3, -Math.floor(Math.log10(Math.abs(step) || 1))));
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtValue(v: number): string {
  const a = Math.abs(v);
  return v.toLocaleString("en-US", { maximumFractionDigits: a >= 1000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 3 });
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY = 864e5;

/** Ticks for a date axis (ms, UTC): years, months, days or hours, as the span asks. */
export function dateTicks(lo: number, hi: number, max: number): { at: number; label: string }[] {
  const span = (hi - lo) / DAY;
  const out: { at: number; label: string }[] = [];
  const d0 = new Date(lo);
  if (span > 3 * 365) {
    for (let y = d0.getUTCFullYear() + (Date.UTC(d0.getUTCFullYear(), 0, 1) < lo ? 1 : 0); Date.UTC(y, 0, 1) <= hi; y++)
      out.push({ at: Date.UTC(y, 0, 1), label: String(y) });
  } else if (span > 50) {
    const y0 = d0.getUTCFullYear();
    let m = d0.getUTCMonth() + (Date.UTC(y0, d0.getUTCMonth(), 1) < lo ? 1 : 0);
    for (let at = Date.UTC(y0, m, 1); at <= hi; at = Date.UTC(y0, ++m, 1)) {
      const d = new Date(at);
      const first = out.length === 0 || d.getUTCMonth() === 0;
      out.push({ at, label: first ? `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` : MONTHS[d.getUTCMonth()] });
    }
  } else if (span > 2) {
    const step = [1, 2, 7, 14].find((s) => span / s <= max) ?? 28;
    for (let at = Math.ceil(lo / DAY) * DAY; at <= hi; at += step * DAY) {
      const d = new Date(at);
      out.push({ at, label: `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}` });
    }
  } else {
    const hours = (hi - lo) / 36e5;
    const step = [1, 2, 3, 6, 12].find((s) => hours / s <= max) ?? 24;
    for (let at = Math.ceil(lo / (step * 36e5)) * step * 36e5; at <= hi; at += step * 36e5)
      out.push({ at, label: `${String(new Date(at).getUTCHours()).padStart(2, "0")}:00` });
  }
  // Too many for the width: keep every k-th (months by quarters or halves).
  if (out.length <= max) return out;
  const k = [2, 3, 4, 6, 12].find((s) => Math.ceil(out.length / s) <= max) ?? Math.ceil(out.length / max);
  return out.filter((_, i) => i % k === 0);
}

function xLabel(chart: Chart, i: number): string {
  const v = chart.x_values[i];
  if (chart.x_type === "date" && typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const d = new Date(`${v}T00:00:00Z`);
    return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  }
  if (typeof v === "number") return chart.x_type === "index" ? `#${v}` : fmtValue(v);
  return String(v);
}

export function useWidth(fallback: number) {
  // A callback ref: a chart folded away and shown again is a new element, and is watched again
  // (3 Nov: the design-space map came back 240 px wide). A width of 0 (folded) is not kept.
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.floor(entry.contentRect.width);
      if (w > 0) setWidth(Math.max(240, w));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, width] as const;
}

export function LineChart({ chart }: { chart: Chart }) {
  const series = chart.series.slice(0, MAX_SERIES);
  const colors = useMemo(() => seriesColors(chart.series.slice(0, MAX_SERIES).map((s) => s.name)), [chart]);
  const [shown, setShown] = useState<number[]>(() => series.map((s, i) => (s.unit === series[0]?.unit ? i : -1)).filter((i) => i >= 0));
  const [hover, setHover] = useState<number | null>(null);
  const [wrap, width] = useWidth(640);
  const n = chart.x_values.length;

  const xs = useMemo(() => {
    if (chart.x_type === "date") {
      const t = chart.x_values.map((v) => (typeof v === "number" ? v : Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(v) ? `${v}T00:00:00Z` : v)));
      if (t.every(Number.isFinite)) return { at: t, kind: "date" as const };
    }
    if (chart.x_type === "number") {
      const t = chart.x_values.map(Number);
      if (t.every(Number.isFinite)) return { at: t, kind: "number" as const };
    }
    return { at: chart.x_values.map((_, i) => i), kind: "index" as const };
  }, [chart]);
  if (!n || !series.length) return <p className="fempty">No values to plot.</p>;

  const unit = series[shown[0]]?.unit ?? "";
  const visible = shown.map((i) => ({ i, s: series[i], color: colors[i] }));
  const values = visible.flatMap((v) => v.s.values.filter((x): x is number => x != null && Number.isFinite(x)));
  const lo = Math.min(0, ...values);
  const hi = Math.max(0, ...values);
  const yt = niceTicks(lo, hi, 5);
  const ystep = yt.length > 1 ? yt[1] - yt[0] : 1;
  const ylabels = yt.map((t) => fmtTick(t, ystep));
  const left = Math.max(30, Math.max(...ylabels.map((l) => l.length), unit.length) * 6.6 + 12);
  const pw = width - left - RIGHT;
  const ph = HEIGHT - TOP - BOTTOM;
  const x0 = Math.min(...xs.at);
  const x1 = Math.max(...xs.at);
  const sx = (v: number) => left + (x1 === x0 ? pw / 2 : ((v - x0) / (x1 - x0)) * pw);
  const sy = (v: number) => TOP + ph - ((v - yt[0]) / (yt[yt.length - 1] - yt[0] || 1)) * ph;
  const maxTicks = Math.max(2, Math.floor(pw / 56));
  const xt =
    xs.kind === "date"
      ? dateTicks(x0, x1, maxTicks)
      : niceTicks(x0, x1, Math.min(6, maxTicks))
          .filter((t) => t >= x0 && t <= x1)
          .map((t) => ({ at: t, label: fmtTick(t, 1) }));

  const path = (vals: (number | null)[]) => {
    let d = "";
    let pen = false;
    vals.forEach((v, k) => {
      if (v == null || !Number.isFinite(v) || k >= n) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${sx(xs.at[k]).toFixed(1)} ${sy(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };

  // Direct labels at the line ends, when there are few lines and their ends stay apart.
  const ends = visible.map((v) => {
    let k = v.s.values.length - 1;
    while (k >= 0 && v.s.values[k] == null) k--;
    return k >= 0 ? { ...v, x: sx(xs.at[k]), y: sy(v.s.values[k] as number) } : null;
  });
  const endsApart =
    visible.length > 1 &&
    visible.length <= 4 &&
    ends.every((a, k) => a && ends.every((b, j) => j === k || !b || Math.abs(a.y - b.y) >= 16));

  const toggle = (i: number) => {
    if (shown.includes(i)) {
      if (shown.length > 1) setShown(shown.filter((k) => k !== i));
    } else if (series[i].unit !== unit) setShown([i]);
    else setShown([...shown, i].sort((a, b) => a - b));
  };

  const nearest = (px: number) => {
    let best = 0;
    for (let k = 1; k < n; k++) if (Math.abs(sx(xs.at[k]) - px) < Math.abs(sx(xs.at[best]) - px)) best = k;
    return best;
  };
  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setHover(nearest(left + ((e.clientX - r.left) / r.width) * pw));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const k = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
    if (k) setHover((h) => Math.max(0, Math.min(n - 1, (h ?? (k > 0 ? -1 : n)) + k)));
    else if (e.key === "Home") setHover(0);
    else if (e.key === "End") setHover(n - 1);
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  const hx = hover != null ? sx(xs.at[hover]) : 0;
  const names = visible.map((v) => v.s.name).join(", ");
  return (
    <div className="lchart">
      {series.length > 1 ? (
        <div className="lc-legend" role="group" aria-label="Series">
          {series.map((s, i) => {
            const on = shown.includes(i);
            const swap = !on && s.unit !== unit;
            return (
              <button
                key={s.name}
                type="button"
                className={`lc-key ta-btn${on ? " on" : ""}`}
                aria-pressed={on}
                title={swap ? `Plot ${s.name} (${s.unit}) instead: one axis at a time` : on ? (shown.length > 1 ? `Hide ${s.name}` : undefined) : `Show ${s.name}`}
                onClick={() => toggle(i)}
              >
                <svg width="14" height="8" viewBox="0 0 14 8" aria-hidden="true">
                  <path d="M1 4h12" stroke={on ? colors[i] : "#B9C3C6"} strokeWidth="2.4" strokeLinecap="round" />
                </svg>
                {s.name}
                {s.unit && <span className="lc-key-unit">{s.unit}</span>}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="lc-title">
          {series[0]?.name}
          {unit && <span className="lc-key-unit">{unit}</span>}
          <span className="lc-key-unit">by {chart.x}</span>
        </div>
      )}
      <div
        ref={wrap}
        className="lc-plot"
        tabIndex={0}
        role="group"
        aria-label={`Chart of ${names}. Arrow keys read the values one ${chart.x} at a time.`}
        onKeyDown={onKey}
        onBlur={() => setHover(null)}
      >
        <svg width={width} height={HEIGHT} role="img" aria-label={`Line chart of ${names} (${unit}) by ${chart.x}, ${n} points from ${xLabel(chart, 0)} to ${xLabel(chart, n - 1)}. The Table tab has the rows.`}>
          {yt.map((t, k) => (
            <g key={t}>
              <line x1={left} x2={width - RIGHT} y1={sy(t)} y2={sy(t)} className={t === 0 ? "lc-axis" : "lc-grid"} />
              <text x={left - 8} y={sy(t)} dy="0.32em" textAnchor="end" className="lc-tick">
                {ylabels[k]}
              </text>
            </g>
          ))}
          {unit && (
            <text x={left - 8} y={10} textAnchor="end" className="lc-unit">
              {unit}
            </text>
          )}
          {xt.map((t) => {
            const x = sx(t.at);
            return (
              <text key={t.at} x={x} y={HEIGHT - 8} textAnchor={x > width - 36 ? "end" : "middle"} className="lc-tick">
                {t.label}
              </text>
            );
          })}
          {visible.map((v) => (
            <path key={v.i} d={path(v.s.values)} fill="none" stroke={v.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {endsApart &&
            ends.map(
              (e) =>
                e && (
                  <text key={e.i} x={Math.min(e.x, width - RIGHT) - 2} y={e.y - 8} textAnchor="end" className="lc-label">
                    {e.s.name}
                  </text>
                ),
            )}
          {hover != null && (
            <g pointerEvents="none">
              <line x1={hx} x2={hx} y1={TOP} y2={TOP + ph} className="lc-cross" />
              {visible.map((v) => {
                const val = v.s.values[hover];
                return val == null ? null : <circle key={v.i} cx={hx} cy={sy(val)} r={4} fill={v.color} stroke="#fff" strokeWidth={2} />;
              })}
            </g>
          )}
          <rect
            x={left}
            y={TOP}
            width={Math.max(0, pw)}
            height={ph}
            fill="transparent"
            onPointerMove={onMove}
            onPointerDown={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
        {hover != null && (
          <div className={`lc-tip${hx > width * 0.6 ? " flip" : ""}`} style={{ left: hx }} aria-live="polite">
            <span className="lc-tip-x">{xLabel(chart, hover)}</span>
            {visible.map((v) => {
              const val = v.s.values[hover];
              return (
                <span key={v.i} className="lc-tip-row">
                  <svg width="12" height="6" viewBox="0 0 12 6" aria-hidden="true">
                    <path d="M1 3h10" stroke={v.color} strokeWidth="2.4" strokeLinecap="round" />
                  </svg>
                  <strong>{val == null ? "–" : fmtValue(val)}</strong>
                  <span className="lc-tip-unit">{v.s.unit}</span>
                  <span className="lc-tip-name">{v.s.name}</span>
                </span>
              );
            })}
          </div>
        )}
      </div>
      {chart.series.length > MAX_SERIES && <span className="note">{chart.series.length - MAX_SERIES} more columns are in the table.</span>}
    </div>
  );
}
