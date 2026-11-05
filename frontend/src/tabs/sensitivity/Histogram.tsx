// All the picked parameters drawn together (uniform within each range): the spread of an output
// as a histogram, the bins between P10 and P90 in the accent and the tails lighter, with P10, P50
// and P90 marked and the base case beside them. Each bin is a hit target with its range and count.
// Below: P10, P50, P90, the mean and the spread as figures (the chart's table view).

import { useEffect, useRef, useState } from "react";

import { niceTicks, useWidth } from "../../components/LineChart";
import type { MonteCarloOutput, SensOutput } from "../../workbench";
import { BAND, OUT_OF_BAND } from "./colors";
import { OUTPUT_BETTER, baseVerdict, fmtOut, lowerFirst, trimNum } from "./params";

interface Props {
  mc: MonteCarloOutput;
  output: SensOutput | undefined;
  base: number | null;
  samples: number;
  /** Alone in its row: the figures and the summary sit beside the plot. */
  wide?: boolean;
}

/** A figure for the stat tiles: the number, its unit small beside it. */
function Stat({ v, output, points = false }: { v: number; output: SensOutput | undefined; points?: boolean }) {
  const unit = output?.unit === "%" ? (points ? " points" : "%") : output?.unit ? ` ${output.unit}` : "";
  return (
    <>
      {trimNum(v, 1)}
      {unit && <small>{unit}</small>}
    </>
  );
}

/** The spread in words: where 8 in 10 samples land, and whether the base case is optimistic. */
function Summary({ mc, output, base }: { mc: MonteCarloOutput; output: SensOutput | undefined; base: number | null }) {
  const key = output?.key ?? "lcoh";
  const name = output ? lowerFirst(output.label) : "result";
  const v = base == null ? null : baseVerdict(mc.histogram, base, key);
  const lowerBetter = (OUTPUT_BETTER[key] ?? "lower") === "lower";
  const pct = (x: number) => `${Math.round(x * 100)}%`;
  return (
    <p className="sen-summary">
      8 in 10 samples give {fmtOut(output, mc.p10)} to {fmtOut(output, mc.p90)}.{" "}
      {v && base != null && v.leaning === "worse" && (
        <>
          <strong>Uncertainty mostly works against this design:</strong> {pct(lowerBetter ? v.above : v.below)} of the samples give a {lowerBetter ? "higher" : "lower"} {name} than the
          base case ({fmtOut(output, base)}).
        </>
      )}
      {v && base != null && v.leaning === "better" && (
        <>
          <strong>Uncertainty mostly works for this design:</strong> {pct(lowerBetter ? v.below : v.above)} of the samples give a {lowerBetter ? "lower" : "higher"} {name} than the
          base case ({fmtOut(output, base)}).
        </>
      )}
      {v && base != null && v.leaning === "even" && (
        <>
          The base case ({fmtOut(output, base)}) sits near the middle: {pct(v.above)} of the samples above it, {pct(v.below)} below.
        </>
      )}
    </p>
  );
}

/** The plot's height; when wide, it grows to the height of the figures beside it (up to H_MAX). */
const H_MIN = 210;
const H_MAX = 320;

/** A column from the baseline up to `top`, its top corners rounded (4px or less), square at the base. */
function column(x0: number, x1: number, top: number, bottom: number): string {
  const r = Math.max(0, Math.min(4, (x1 - x0) / 2, bottom - top));
  return `M${x0},${bottom} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x1 - r} Q${x1},${top} ${x1},${top + r} V${bottom} Z`;
}
const M = { top: 30, right: 14, bottom: 30, left: 36 };

export function Histogram({ mc, output, base, samples, wide = false }: Props) {
  const [wrap, width] = useWidth(520);
  const [hover, setHover] = useState<number | null>(null);
  const { edges, counts } = mc.histogram;
  const flat = mc.p10 === mc.p90 || counts.filter((c) => c > 0).length <= 1;
  // Wide, the figures sit beside the plot: the plot takes their height, so the two end level.
  const side = useRef<HTMLDivElement>(null);
  const [sideH, setSideH] = useState(0);
  const beside = wide && !flat;
  useEffect(() => {
    const el = side.current;
    if (!beside || !el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setSideH(Math.round(el.getBoundingClientRect().height)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [beside]);
  const H = beside && sideH > 0 ? Math.max(H_MIN, Math.min(H_MAX, sideH)) : H_MIN;
  const total = counts.reduce((s, c) => s + c, 0) || 1;

  const lo = Math.min(edges[0], base ?? edges[0]);
  const hi = Math.max(edges[edges.length - 1], base ?? edges[0]);
  const xt = niceTicks(lo, hi, width < 420 ? 4 : 6).filter((t) => t >= lo - (hi - lo) * 0.02 && t <= hi + (hi - lo) * 0.02);
  const pw = width - M.left - M.right;
  const ph = H - M.top - M.bottom;
  const sx = (v: number) => M.left + ((v - lo) / (hi - lo || 1)) * pw;
  const maxCount = Math.max(...counts, 1);
  const yt = niceTicks(0, maxCount, 3);
  const yMax = yt[yt.length - 1];
  const sy = (c: number) => M.top + ph - (c / yMax) * ph;

  const marks = [
    { id: "p10", label: "P10", v: mc.p10 },
    { id: "p50", label: "P50", v: mc.p50 },
    { id: "p90", label: "P90", v: mc.p90 },
  ];
  // Spread the three labels so they never sit on each other.
  const labelX: number[] = [];
  for (const m of marks) {
    let x = sx(m.v);
    const prev = labelX[labelX.length - 1];
    if (prev != null && x - prev < 34) x = prev + 34;
    labelX.push(Math.min(x, width - 18));
  }

  return (
    <div className={`sen-hist${beside ? " is-wide" : ""}`}>
      <div className="sen-hist-main" ref={wrap}>
      {flat ? (
        <p className="sen-note">
          Every sample gives {fmtOut(output, mc.p50)}: none of these ranges moves the {output ? lowerFirst(output.label) : "output"}.
        </p>
      ) : (
        <div className="sen-hist-plot" style={{ height: H }}>
          <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} role="img" aria-label={`${samples} samples of the ${output ? lowerFirst(output.label) : "output"}: P10 ${fmtOut(output, mc.p10)}, P50 ${fmtOut(output, mc.p50)}, P90 ${fmtOut(output, mc.p90)}`}>
            <g className="sen-grid">
              {yt.map((t) => (
                <line key={t} x1={M.left} x2={M.left + pw} y1={sy(t)} y2={sy(t)} />
              ))}
            </g>
            <g className="sen-ticks">
              {yt.map((t) => (
                <text key={t} x={M.left - 6} y={sy(t) + 4} textAnchor="end">
                  {t}
                </text>
              ))}
              {xt.map((t) => (
                <text key={t} x={sx(t)} y={H - 10} textAnchor="middle">
                  {trimNum(t, 1)}
                </text>
              ))}
            </g>
            {counts.map((c, i) => {
              const x0 = sx(edges[i]) + 1;
              const x1 = sx(edges[i + 1]) - 1;
              const mid = (edges[i] + edges[i + 1]) / 2;
              const inBand = mid >= mc.p10 && mid <= mc.p90;
              return (
                <g key={i} className={`sen-bin${hover === i ? " is-hover" : ""}`}>
                  {c > 0 && <path d={column(x0, x1, sy(c), M.top + ph)} fill={inBand ? BAND : OUT_OF_BAND} />}
                  <rect
                    x={x0 - 1}
                    y={M.top}
                    width={Math.max(1, x1 - x0 + 2)}
                    height={ph}
                    fill="transparent"
                    onPointerEnter={() => setHover(i)}
                    onPointerLeave={() => setHover(null)}
                  />
                </g>
              );
            })}
            <line className="sen-axis" x1={M.left} x2={M.left + pw} y1={M.top + ph} y2={M.top + ph} />
            {marks.map((m, i) => (
              <g key={m.id} className={`sen-mark sen-mark-${m.id}`}>
                <line x1={sx(m.v)} x2={sx(m.v)} y1={M.top - 6} y2={M.top + ph} />
                <text x={labelX[i]} y={M.top - 12} textAnchor="middle">
                  {m.label}
                </text>
              </g>
            ))}
            {base != null && (
              <g className="sen-mark sen-mark-base">
                <line x1={sx(base)} x2={sx(base)} y1={M.top + 8} y2={M.top + ph} />
                <text x={sx(base) + (sx(base) > width - 60 ? -6 : 6)} y={M.top + 20} textAnchor={sx(base) > width - 60 ? "end" : "start"}>
                  base
                </text>
              </g>
            )}
          </svg>
          {hover != null && (
            <div className={`sen-tip sen-hist-tip${sx(edges[hover]) > width * 0.6 ? " flip" : ""}`} style={{ left: sx((edges[hover] + edges[hover + 1]) / 2) }} role="status">
              <strong className="sen-tip-head">
                {trimNum(edges[hover], 1)} to {fmtOut(output, edges[hover + 1])}
              </strong>
              <span className="sen-tip-row">
                <strong>{counts[hover]}</strong>
                <span>
                  samples, {trimNum((counts[hover] / total) * 100, 0)}%
                </span>
              </span>
            </div>
          )}
        </div>
      )}
      </div>
      <div className="sen-hist-side" ref={side}>
      {!flat && <Summary mc={mc} output={output} base={base} />}
      <dl className="sen-stats">
        <div>
          <dt>P10</dt>
          <dd>
            <Stat v={mc.p10} output={output} />
          </dd>
        </div>
        <div className="is-mid">
          <dt>P50</dt>
          <dd>
            <Stat v={mc.p50} output={output} />
          </dd>
        </div>
        <div>
          <dt>P90</dt>
          <dd>
            <Stat v={mc.p90} output={output} />
          </dd>
        </div>
        <div>
          <dt>mean</dt>
          <dd>
            <Stat v={mc.mean} output={output} />
          </dd>
        </div>
        <div>
          <dt>P10 to P90</dt>
          <dd>
            <Stat v={mc.p90 - mc.p10} output={output} points />
          </dd>
        </div>
      </dl>
      {!flat && (
        <div className="sen-legend" aria-hidden="true">
          <span>
            <i style={{ background: BAND }} />
            between P10 and P90
          </span>
          <span>
            <i style={{ background: OUT_OF_BAND }} />
            the 10% tails
          </span>
          <span>
            {samples} samples, uniform within each range
          </span>
        </div>
      )}
      </div>
    </div>
  );
}
