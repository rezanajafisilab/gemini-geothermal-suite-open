// The spider: each parameter swept across its own range, so ranges of any unit share one x axis
// (−100% is the low end, +100% the high end). One line per parameter, coloured by its slot; a
// hairline at the base value. The crosshair snaps to the five positions run and lists every line
// there with the parameter's actual value; arrow keys move it. Hovering a legend entry brings
// its line forward.

import { useState, type KeyboardEvent, type PointerEvent } from "react";

import { niceTicks, useWidth } from "../../components/LineChart";
import type { SensOutput, SensParam } from "../../workbench";
import { slotColor } from "./colors";
import { fmtOut, fmtParam, lowerFirst, trimNum, type SpiderLine } from "./params";

interface Props {
  lines: SpiderLine[];
  output: SensOutput | undefined;
  base: number | null;
  slots: Record<string, number>;
  catalogue: Map<string, SensParam>;
}

const H = 270;
const M = { top: 16, right: 16, bottom: 40, left: 46 };
const POSITIONS = [-100, -50, 0, 50, 100];

export function Spider({ lines, output, base, slots, catalogue }: Props) {
  const [wrap, width] = useWidth(520);
  const [at, setAt] = useState<number | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  if (!lines.length)
    return (
      <div className="sen-spider" ref={wrap}>
        <p className="sen-note">Nothing to show for this output.</p>
      </div>
    );

  const ys = lines.flatMap((l) => l.points.map((p) => p.y)).concat(base != null ? [base] : []);
  const yt = niceTicks(Math.min(...ys), Math.max(...ys), 4);
  const [y0, y1] = [yt[0], yt[yt.length - 1]];
  const pw = width - M.left - M.right;
  const ph = H - M.top - M.bottom;
  const sx = (pos: number) => M.left + ((pos + 100) / 200) * pw;
  const sy = (v: number) => M.top + ph - ((v - y0) / (y1 - y0 || 1)) * ph;
  const color = (key: string) => slotColor(slots[key]);
  const ordered = focus ? [...lines.filter((l) => l.key !== focus), ...lines.filter((l) => l.key === focus)] : lines;

  const snap = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const pos = ((e.clientX - r.left) / r.width) * 200 - 100;
    setAt(POSITIONS.reduce((best, p) => (Math.abs(p - pos) < Math.abs(best - pos) ? p : best), 0));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = at == null ? 2 : POSITIONS.indexOf(at);
    if (e.key === "ArrowRight") setAt(POSITIONS[Math.min(4, i + 1)]);
    else if (e.key === "ArrowLeft") setAt(POSITIONS[Math.max(0, i - 1)]);
    else if (e.key === "Home") setAt(-100);
    else if (e.key === "End") setAt(100);
    else if (e.key === "Escape") setAt(null);
    else return;
    e.preventDefault();
  };

  const tipRows =
    at == null
      ? []
      : lines
          .map((l) => ({ l, p: l.points.find((p) => p.pos === at) }))
          .filter((r): r is { l: SpiderLine; p: SpiderLine["points"][number] } => !!r.p)
          .sort((a, b) => b.p.y - a.p.y);
  const posText = (pos: number) => (pos === 0 ? "middle of each range" : pos === -100 ? "low end of each range" : pos === 100 ? "high end of each range" : `${pos > 0 ? "+" : "−"}${Math.abs(pos)}% of the way`);

  return (
    <div className="sen-spider" ref={wrap}>
      <div
        className="sen-spider-plot"
        tabIndex={0}
        role="group"
        aria-label={`Spider chart of the ${output ? lowerFirst(output.label) : "output"}: ${lines.length} parameters across their ranges. Arrow keys move along the ranges.`}
        onKeyDown={onKey}
        onFocus={() => at == null && setAt(0)}
        onBlur={() => setAt(null)}
      >
        <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} aria-hidden="true">
          <g className="sen-grid">
            {yt.map((t) => (
              <line key={t} x1={M.left} x2={M.left + pw} y1={sy(t)} y2={sy(t)} />
            ))}
            {POSITIONS.map((p) => (
              <line key={p} x1={sx(p)} x2={sx(p)} y1={M.top} y2={M.top + ph} className={p === 0 ? "is-mid" : undefined} />
            ))}
          </g>
          <g className="sen-ticks">
            {yt.map((t) => (
              <text key={t} x={M.left - 8} y={sy(t) + 4} textAnchor="end">
                {trimNum(t, 1)}
              </text>
            ))}
            {POSITIONS.map((p, i) => (
              <text key={p} x={sx(p)} y={M.top + ph + 17} textAnchor={i === 0 ? "start" : i === 4 ? "end" : "middle"}>
                {p === 0 ? "0" : `${p > 0 ? "+" : "−"}${Math.abs(p)}%`}
              </text>
            ))}
            <text x={M.left} y={H - 4} className="sen-axis-title">
              low end
            </text>
            <text x={M.left + pw / 2} y={H - 4} textAnchor="middle" className="sen-axis-title">
              position in each range
            </text>
            <text x={M.left + pw} y={H - 4} textAnchor="end" className="sen-axis-title">
              high end
            </text>
          </g>
          {base != null && <line className="sen-base" x1={M.left} x2={M.left + pw} y1={sy(base)} y2={sy(base)} />}
          {ordered.map((l) => {
            const dim = focus && focus !== l.key;
            return (
              <g key={l.key} className={`sen-line${dim ? " is-dim" : ""}${focus === l.key ? " is-focus" : ""}`}>
                <polyline points={l.points.map((p) => `${sx(p.pos)},${sy(p.y)}`).join(" ")} fill="none" stroke={color(l.key)} />
                {l.points.map((p) => (
                  <circle key={p.pos} cx={sx(p.pos)} cy={sy(p.y)} r={at === p.pos ? 5 : 3.5} fill={color(l.key)} stroke="#fff" strokeWidth={2} />
                ))}
              </g>
            );
          })}
          {at != null && <line className="sen-cross" x1={sx(at)} x2={sx(at)} y1={M.top} y2={M.top + ph} />}
          <rect
            x={M.left}
            y={M.top}
            width={pw}
            height={ph}
            fill="transparent"
            style={{ pointerEvents: "all" }}
            onPointerMove={snap}
            onPointerDown={snap}
            onPointerLeave={() => setAt(null)}
          />
        </svg>
        {at != null && tipRows.length > 0 && (
          <div className={`sen-tip sen-spider-tip${at > 0 ? " flip" : ""}`} style={{ left: sx(at) }} role="status">
            <strong className="sen-tip-head">{posText(at)}</strong>
            {tipRows.map(({ l, p }) => {
              const param = catalogue.get(l.key);
              return (
                <span key={l.key} className="sen-tip-row">
                  <i className="line" style={{ background: color(l.key) }} />
                  <strong>{fmtOut(output, p.y)}</strong>
                  <span>
                    {l.label}
                    {param ? ` ${fmtParam(param, p.x)}` : ""}
                  </span>
                </span>
              );
            })}
          </div>
        )}
      </div>
      <ul className="sen-spider-legend" aria-label="Parameters">
        {lines.map((l) => (
          <li key={l.key} onPointerEnter={() => setFocus(l.key)} onPointerLeave={() => setFocus(null)}>
            <i style={{ background: color(l.key) }} aria-hidden="true" />
            {l.label}
          </li>
        ))}
        {base != null && (
          <li className="sen-base-key">
            <i aria-hidden="true" />
            base {fmtOut(output, base)}
          </li>
        )}
      </ul>
    </div>
  );
}
