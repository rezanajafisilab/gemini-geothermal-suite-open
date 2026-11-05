// A year of daily values as a small area chart with the chosen day marked: the year player's strip
// (heat above the middle line, cold below; a slider you drag, click or step with the keys) and the
// inspector's sparkline (one series; click to pick a day). Hovering reads the day under the pointer.

import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { MONTH_NAMES, MONTH_STARTS, dateLabel, fmtValue } from "./plant";

export interface StripSeries {
  label: string;
  values: number[];
  /** The mark's colour; text never wears it. */
  color: string;
}

interface Props {
  /** One series fills up from the bottom; two mirror: the first above the middle, the second below. */
  series: StripSeries[];
  day: number;
  onDay: (day: number) => void;
  height: number;
  /** A keyboard slider (the year player); otherwise a picture you can click. */
  slider?: boolean;
  label: string;
  unit?: string;
  /** Month names under the strip. */
  months?: boolean;
  className?: string;
  /** Days a cap is broken: red bands over the strip (0-based first and last day). */
  marks?: { first: number; last: number; text: string }[];
}

const W = 1000;
const DAYS = 365;

function areaPath(values: number[], max: number, base: number, span: number, dir: 1 | -1): string {
  if (!values.length || max <= 0) return "";
  const n = Math.min(DAYS, values.length);
  const pts: string[] = [];
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * W;
    const y = base - dir * Math.min(1, Math.max(0, values[i]) / max) * span;
    pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return `M0,${base} L${pts.join(" L")} L${W},${base} Z`;
}

export function YearStrip({ series, day, onDay, height, slider = false, label, unit = "MW", months = false, className, marks = [] }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [hover, setHover] = useState<number | null>(null);
  const mirror = series.length === 2;
  const paths = useMemo(() => {
    if (mirror) {
      const half = height / 2;
      return series.map((s, i) => areaPath(s.values, Math.max(0, ...s.values), half, half - 3, i === 0 ? 1 : -1));
    }
    const max = Math.max(0, ...series.flatMap((s) => s.values));
    return series.map((s) => areaPath(s.values, max, height, height - 4, 1));
  }, [series, height, mirror]);

  const dayAt = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r || r.width <= 0) return day;
    return Math.min(DAYS, Math.max(1, Math.round(((clientX - r.left) / r.width) * (DAYS - 1)) + 1));
  };
  const down = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    dragging.current = true;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    onDay(dayAt(e.clientX));
  };
  const move = (e: PointerEvent<HTMLDivElement>) => {
    const d = dayAt(e.clientX);
    setHover(d);
    if (dragging.current) onDay(d);
  };
  const up = () => {
    dragging.current = false;
  };
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    const steps: Record<string, number> = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -30, PageUp: 30 };
    let next: number | null = null;
    if (e.key in steps) next = day + steps[e.key];
    else if (e.key === "Home") next = 1;
    else if (e.key === "End") next = DAYS;
    if (next == null) return;
    e.preventDefault();
    onDay(((next - 1 + DAYS) % DAYS) + 1);
  };

  const pct = (d: number) => ((d - 1) / (DAYS - 1)) * 100;
  const shown = hover ?? null;
  const readout = shown != null && (
    <span className="dz-strip-tip" style={{ left: `${pct(shown)}%`, transform: `translateX(${pct(shown) > 70 ? "-100%" : pct(shown) < 30 ? "0" : "-50%"})` }} aria-hidden="true">
      <strong>{dateLabel(shown)}</strong>
      {series.map((s) => (
        <span key={s.label} className="dz-strip-tip-row">
          <span className="dz-key-line" style={{ background: s.color }} />
          <b>
            {fmtValue(s.values[shown - 1] ?? 0)} {unit}
          </b>
          <span>{s.label}</span>
        </span>
      ))}
    </span>
  );

  const a11y = slider
    ? {
        role: "slider",
        tabIndex: 0,
        "aria-label": label,
        "aria-valuemin": 1,
        "aria-valuemax": DAYS,
        "aria-valuenow": day,
        "aria-valuetext": dateLabel(day),
        onKeyDown: key,
      }
    : { role: "img", "aria-label": label };

  return (
    <div className={`dz-strip${slider ? " is-slider" : ""}${className ? ` ${className}` : ""}`}>
      <div
        ref={box}
        className="dz-strip-plot"
        style={{ height }}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        onPointerLeave={() => setHover(null)}
        {...a11y}
      >
        <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" aria-hidden="true">
          {paths.map((d, i) => d && <path key={i} d={d} fill={series[i].color} fillOpacity={mirror ? 0.78 : 0.82} />)}
          {marks.map((m) => {
            const x0 = (m.first / (DAYS - 1)) * W;
            const w = Math.max(4, ((m.last - m.first + 1) / (DAYS - 1)) * W);
            return (
              <g key={`${m.first}-${m.text}`} className="ys-mark">
                <rect x={x0} y={0} width={w} height={height} fill="var(--red, #b42318)" fillOpacity={0.16} />
                <rect x={x0} y={0} width={w} height={3} fill="var(--red, #b42318)" />
              </g>
            );
          })}
          {mirror && <line x1="0" x2={W} y1={height / 2} y2={height / 2} stroke="#fff" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />}
          {!mirror && <line x1="0" x2={W} y1={height - 0.5} y2={height - 0.5} stroke="#dce3e3" strokeWidth="1" vectorEffect="non-scaling-stroke" />}
        </svg>
        {shown != null && <span className="dz-strip-hover" style={{ left: `${pct(shown)}%` }} aria-hidden="true" />}
        <span className="dz-strip-mark" style={{ left: `${pct(day)}%` }} aria-hidden="true" />
        {slider && <span className="dz-strip-knob" style={{ left: `${pct(day)}%` }} aria-hidden="true" />}
        {readout}
      </div>
      {months && (
        <div className="dz-strip-months" aria-hidden="true">
          {MONTH_STARTS.map((s, i) => (
            <span key={s} style={{ left: `${pct(s)}%` }}>
              {MONTH_NAMES[i]}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
