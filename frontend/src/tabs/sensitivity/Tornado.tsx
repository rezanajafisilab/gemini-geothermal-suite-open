// The tornado: one row per parameter, the biggest swing on top. From the base value (the spine)
// a violet bar reaches the output with the parameter at the low end of its range and a teal bar
// the output at the high end; the farther end carries its value. Rows are focusable and show both
// ends on hover or focus.

import { useState } from "react";

import { niceTicks } from "../../components/LineChart";
import { menuProps } from "../../menu";
import type { SensOutput, SensParam } from "../../workbench";
import { HIGH, LOW } from "./colors";
import { fmtOut, fmtParam, lowerFirst, trimNum, type TornadoRow } from "./params";

interface Props {
  rows: TornadoRow[];
  output: SensOutput | undefined;
  base: number | null;
  /** Each parameter's range as run (sent units), from the result. */
  ranges: Record<string, [number, number]>;
  catalogue: Map<string, SensParam>;
  /** The design the runs vary: a bar's menu asks a what-if at either end of its range on it. */
  design?: string;
}

export function Tornado({ rows, output, base, ranges, catalogue, design }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  if (base == null || !rows.length) return <p className="sen-note">Nothing to show for this output.</p>;
  const values = rows.flatMap((r) => [r.low, r.high]).filter((v): v is number => v != null);
  const lo0 = Math.min(base, ...values);
  const hi0 = Math.max(base, ...values);
  const span0 = hi0 - lo0 || Math.max(1, Math.abs(base) * 0.1);
  // Room for the end labels on both sides.
  const lo = lo0 - span0 * 0.3;
  const hi = hi0 + span0 * 0.3;
  const at = (v: number) => ((v - lo) / (hi - lo)) * 100;
  const ticks = niceTicks(lo0, hi0, 4).filter((t) => t >= lo && t <= hi);
  const unit = output?.unit === "%" ? "%" : output?.unit ? ` ${output.unit}` : "";
  const delta = (v: number) => `${v - base > 0 ? "+" : ""}${trimNum(v - base, 1)}`;

  return (
    <div className="sen-tornado">
      <div className="sen-legend" aria-hidden="true">
        <span>
          <i style={{ background: LOW }} />
          low end of the range
        </span>
        <span>
          <i style={{ background: HIGH }} />
          high end of the range
        </span>
      </div>
      <div className="sen-tor-rows" role="list" aria-label={`What moves the ${output ? lowerFirst(output.label) : "output"}, biggest swing first`}>
        {rows.map((r) => {
          const p = catalogue.get(r.key);
          const range = ranges[r.key];
          const ends = [
            { side: "low" as const, v: r.low, color: LOW, x: range ? range[0] : null },
            { side: "high" as const, v: r.high, color: HIGH, x: range ? range[1] : null },
          ].filter((e): e is typeof e & { v: number } => e.v != null);
          const len = (v: number) => Math.abs(v - base);
          // The longer bar first, the shorter on top and thinner, so both show on one side.
          const drawn = [...ends].sort((a, b) => len(b.v) - len(a.v));
          const sameSide = ends.length === 2 && Math.sign(ends[0].v - base) === Math.sign(ends[1].v - base);
          const none = r.swing === 0 && ends.every((e) => e.v === base);
          const endText = (e: (typeof ends)[number]) => `${p && e.x != null ? fmtParam(p, e.x) : e.side} gives ${fmtOut(output, e.v)} (${delta(e.v)})`;
          const aria = `${r.label}: ${none ? "no effect" : ends.map(endText).join("; ")}`;
          return (
            <div
              key={r.key}
              role="listitem"
              tabIndex={0}
              className={`sen-tor-row${hover === r.key ? " is-hover" : ""}`}
              aria-label={aria}
              onPointerEnter={() => setHover(r.key)}
              onPointerLeave={() => setHover(null)}
              onFocus={() => setHover(r.key)}
              onBlur={() => setHover(null)}
              {...(design && p && range ? menuProps({ kind: "bar", design, param: r.key, label: r.label, low: fmtParam(p, range[0]), high: fmtParam(p, range[1]) }) : {})}
            >
              <span className="sen-tor-label">
                <span className="sen-tor-name">{r.label}</span>
                {p && range && (
                  <span className="sen-tor-range">
                    {fmtParam(p, range[0])} to {fmtParam(p, range[1])}
                  </span>
                )}
              </span>
              <span className="sen-tor-plot" aria-hidden="true">
                {ticks.map((t) => (
                  <i key={t} className="sen-tor-grid" style={{ left: `${at(t)}%` }} />
                ))}
                {drawn.map((e, k) => {
                  const a = at(Math.min(base, e.v));
                  const b = at(Math.max(base, e.v));
                  const left = e.v < base;
                  const inner = sameSide && k === 1;
                  return (
                    <i
                      key={e.side}
                      className={`sen-tor-bar${left ? " is-left" : ""}${inner ? " is-inner" : ""}`}
                      style={{ left: `${a}%`, width: `${Math.max(b - a, 0.4)}%`, background: e.color }}
                    />
                  );
                })}
                <i className="sen-tor-spine" style={{ left: `${at(base)}%` }} />
                {none ? (
                  <span className="sen-tor-val is-none" style={{ left: `calc(${at(base)}% + 8px)` }}>
                    no effect
                  </span>
                ) : (
                  ends
                    .filter((e) => !sameSide || e === drawn[0])
                    .map((e) => {
                      const left = e.v < base;
                      return (
                        <span
                          key={e.side}
                          className="sen-tor-val"
                          style={left ? { right: `calc(${100 - at(e.v)}% + 6px)` } : { left: `calc(${at(e.v)}% + 6px)` }}
                        >
                          {trimNum(e.v, 1)}
                        </span>
                      );
                    })
                )}
              </span>
              {hover === r.key && !none && (
                <span className="sen-tip sen-tor-tip" role="tooltip">
                  <strong className="sen-tip-head">{r.label}</strong>
                  {ends.map((e) => (
                    <span key={e.side} className="sen-tip-row">
                      <i style={{ background: e.color }} />
                      <span>{p && e.x != null ? fmtParam(p, e.x) : e.side}</span>
                      <strong>{fmtOut(output, e.v)}</strong>
                      <span className="sen-tip-delta">{delta(e.v)}</span>
                    </span>
                  ))}
                  <span className="sen-tip-foot">
                    swing {trimNum(r.swing, 1)}
                    {unit}
                  </span>
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div className="sen-tor-axis" aria-hidden="true">
        <span />
        <span className="sen-tor-ticks">
          {ticks.map((t) => (
            <span key={t} style={{ left: `${at(t)}%` }}>
              {trimNum(t, 1)}
            </span>
          ))}
        </span>
      </div>
      <div className="sen-tor-axis sen-tor-basecap" aria-hidden="true">
        <span />
        <span className="sen-tor-ticks">
          <span className="sen-tor-base" style={{ left: `${at(base)}%` }}>
            base {fmtOut(output, base)}
          </span>
        </span>
      </div>
    </div>
  );
}
