// The discounted cumulative cash flow against the gas plant (boilers and electric chillers), year
// 0 to the server's horizon: the extra capital at year 0, then each year's saving on running
// costs, less the units bought again when they wear out (on both sides), and the value left at the
// end, discounted.
// Below zero is washed red (still paying back), above green; the payback year is marked and the
// NPV labelled at the end. A crosshair (pointer or arrow keys) reads each year; Table lists them.

import { useState, type KeyboardEvent, type PointerEvent } from "react";

import { niceTicks, useWidth } from "../../components/LineChart";
import { AskButton, ProvenanceChip, type Design, type Provenance } from "../../workbench";
import { Panel, TableToggle, useSvgId } from "../energy/parts";
import { eur, signed } from "./format";
import { cashFlow, paybackText, valueAt, type CashFlow } from "./model";

const HEIGHT = 250;
const TOP = 28;
const BOTTOM = 26;
const RIGHT = 14;
const LINE = "#0A6F7C";

interface Props {
  design: Design;
  prov: Provenance;
  /** Fraction, e.g. 0.0525. */
  rate: number | null;
  /** The gas plant, by name: "gas boilers and electric chillers". */
  reference: string | null;
  delay?: number;
}

const DETAIL = "Extra capital and the yearly saving on running costs against the gas plant, both from Dioscuri's plant model";

export function CashFlowPanel({ design, prov, rate, reference, delay }: Props) {
  const [table, setTable] = useState(false);
  const v = design.economics.versus_reference;
  const ref = reference ?? "the gas plant";
  if (!v)
    return (
      <Panel title="Cash flow against gas" delay={delay} aside={<ProvenanceChip source={prov} detail={DETAIL} />}>
        <p className="ec-ref-note">
          <strong>{design.code} is the gas plant.</strong> The other designs' payback and NPV are their cash flow against this one: extra capital up
          front, then cheaper running each year, with the units bought again when they wear out and the value left at the end.
        </p>
      </Panel>
    );
  const c = cashFlow(v);
  const years = c.points.length - 1;
  const question =
    c.payback != null ? `Why does ${design.code} take ${Math.round(c.payback * 10) / 10} years to pay back against gas?` : `Why doesn't ${design.code} pay back against gas within ${years} years?`;
  return (
    <Panel
      title="Cash flow against gas"
      sub={`Extra capital against ${ref} at year 0, then each year's saving on running costs${rate != null ? `, discounted at ${eur(rate * 100, 2).replace(/\.?0+$/, "")}%` : ", discounted"}`}
      delay={delay}
      aside={
        <>
          <ProvenanceChip source={prov} detail={DETAIL} />
          <TableToggle on={table} onChange={setTable} />
          <AskButton compact label="Ask about this chart" context={`${design.code}'s cash flow against gas on the Economics tab (NPV ${signed(c.npv)} M€)`} question={question} />
        </>
      }
    >
      <div className="ee-legend">
        <span className="ee-key">
          <svg width="16" height="8" viewBox="0 0 16 8" aria-hidden="true">
            <path d="M1 4h14" stroke={LINE} strokeWidth="2.2" strokeLinecap="round" />
          </svg>
          Cumulative, discounted, M€
        </span>
        <span className="ee-key">
          <span className="ee-swatch" style={{ background: "rgba(180,35,24,.16)" }} aria-hidden="true" />
          still paying back
        </span>
        <span className="ee-key">
          <span className="ee-swatch" style={{ background: "rgba(43,168,102,.2)" }} aria-hidden="true" />
          ahead of gas
        </span>
      </div>
      {table ? <FlowTable c={c} /> : <FlowChart c={c} code={design.code} />}
    </Panel>
  );
}

function FlowChart({ c, code }: { c: CashFlow; code: string }) {
  const [wrap, width] = useWidth(700);
  const [hover, setHover] = useState<number | null>(null);
  const above = useSvgId("above");
  const below = useSvgId("below");
  const n = c.points.length;
  if (n < 2) return <p className="ee-foot">No cash flow to draw.</p>;
  const yt = niceTicks(c.min, c.max, 4);
  const ymin = Math.min(yt[0], c.min);
  const ymax = Math.max(yt[yt.length - 1], c.max);
  const ylabels = yt.map((t) => eur(t, 0));
  const left = Math.max(30, Math.max(...ylabels.map((l) => l.length)) * 6.6 + 12);
  const pw = Math.max(10, width - left - RIGHT);
  const ph = HEIGHT - TOP - BOTTOM;
  const last = n - 1;
  const x = (t: number) => left + (t / last) * pw;
  const y = (v: number) => TOP + ((ymax - v) / (ymax - ymin || 1)) * ph;
  const line = c.points.map((p, i) => `${i ? "L" : "M"}${x(p.year).toFixed(1)} ${y(p.value).toFixed(1)}`).join("");
  const area = `${line}L${x(last).toFixed(1)} ${y(0).toFixed(1)}L${x(0).toFixed(1)} ${y(0).toFixed(1)}Z`;
  const step = last <= 12 ? 1 : last <= 30 ? 5 : 10;
  const xt: number[] = [];
  for (let t = 0; t <= last; t += step) xt.push(t);
  if (xt[xt.length - 1] !== last && last - xt[xt.length - 1] >= step / 2) xt.push(last);
  else if (xt[xt.length - 1] !== last) xt[xt.length - 1] = last;

  const pick = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const t = Math.round(((e.clientX - box.left - left) / pw) * last);
    setHover(Math.max(0, Math.min(last, t)));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const d = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
    if (d) setHover((h) => Math.max(0, Math.min(last, (h ?? (d > 0 ? -1 : n)) + d)));
    else if (e.key === "Home") setHover(0);
    else if (e.key === "End") setHover(last);
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  const p0 = c.points[0];
  const pn = c.points[last];
  const pbValue = c.payback != null ? valueAt(c.points, c.payback) : null;
  const pb = c.payback != null && pbValue != null ? { year: c.payback, value: pbValue } : null;
  const pbX = pb ? x(pb.year) : 0;
  const pbAnchor = pb ? (pbX < left + 70 ? "start" : pbX > left + pw - 70 ? "end" : "middle") : "middle";
  const hp = hover != null ? c.points[hover] : null;
  const hx = hp ? x(hp.year) : 0;
  const summary =
    `${code}'s cumulative discounted cash flow against gas over ${last} years, in M€: ${eur(p0.value)} at year 0, ` +
    (c.payback != null ? `paying back ${paybackText(c.payback)}, ` : "never back above zero, ") +
    `${signed(pn.value)} at the end (the NPV). Arrow keys read one year at a time.`;

  return (
    <div ref={wrap}>
      <div className="ee-plot" tabIndex={0} role="group" aria-label={summary} onKeyDown={onKey} onBlur={() => setHover(null)}>
        <svg width={width} height={HEIGHT} aria-hidden="true" onPointerMove={pick} onPointerDown={pick} onPointerLeave={() => setHover(null)}>
          <defs>
            <clipPath id={above}>
              <rect x={0} y={0} width={width} height={Math.max(0, y(0))} />
            </clipPath>
            <clipPath id={below}>
              <rect x={0} y={y(0)} width={width} height={Math.max(0, HEIGHT - y(0))} />
            </clipPath>
          </defs>
          {yt.map((t, k) => (
            <g key={t}>
              <line x1={left} x2={left + pw} y1={y(t)} y2={y(t)} className="lc-grid" />
              <text x={left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="lc-tick">
                {ylabels[k]}
              </text>
            </g>
          ))}
          <path d={area} fill="#2BA866" fillOpacity={0.16} clipPath={`url(#${above})`} />
          <path d={area} fill="#B42318" fillOpacity={0.1} clipPath={`url(#${below})`} />
          <line x1={left} x2={left + pw} y1={y(0)} y2={y(0)} className="lc-axis" />
          {pb && (
            <g>
              <line x1={pbX} x2={pbX} y1={TOP - 8} y2={y(pb.value)} stroke="#66727C" strokeWidth={1} shapeRendering="crispEdges" />
              <text x={pbX} y={TOP - 13} textAnchor={pbAnchor} className="lc-label ec-strong">
                Pays back {paybackText(pb.year)}
              </text>
            </g>
          )}
          <path d={line} fill="none" stroke={LINE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {pb && <circle cx={pbX} cy={y(pb.value)} r={4} fill={LINE} stroke="#fff" strokeWidth={2} />}
          <circle cx={x(0)} cy={y(p0.value)} r={4} fill={LINE} stroke="#fff" strokeWidth={2} />
          <circle cx={x(last)} cy={y(pn.value)} r={4.5} fill={LINE} stroke="#fff" strokeWidth={2} />
          {hover == null && (
            <>
              <text x={x(0) + 10} y={y(p0.value)} dy="0.35em" className="lc-label">
                {eur(p0.value)} M€ extra capital
              </text>
              <text x={x(last) - 6} y={y(pn.value) - 12} textAnchor="end" className="lc-label ec-strong">
                NPV {signed(pn.value)} M€
              </text>
            </>
          )}
          {!pb && hover == null && (
            <text x={left + pw / 2} y={TOP - 13} textAnchor="middle" className="lc-label ec-strong ec-bad">
              Doesn't pay back within {last} years
            </text>
          )}
          {xt.map((t) => (
            <text key={t} x={x(t)} y={HEIGHT - 8} textAnchor="middle" className={`lc-tick${hover === t ? " on" : ""}`}>
              {t}
            </text>
          ))}
          {hp && (
            <g>
              <line x1={hx} x2={hx} y1={TOP - 4} y2={TOP + ph} className="lc-cross" />
              <circle cx={hx} cy={y(hp.value)} r={4.5} fill={LINE} stroke="#fff" strokeWidth={2} />
            </g>
          )}
        </svg>
        {hp && (
          <div className={`ee-tip${hx > left + pw * 0.6 ? " flip" : ""}`} style={{ left: hx }} aria-hidden="true">
            <span className="ee-tip-title">Year {hp.year}</span>
            <span className="ee-tip-row">
              <strong>{signed(hp.value, 2)}</strong>
              <span className="u">M€</span>
              <span className="n">so far, discounted</span>
            </span>
            <span className="ee-tip-row">
              <strong>{signed(hp.delta, 2)}</strong>
              <span className="u">M€</span>
              <span className="n">{hp.year === 0 ? "extra capital" : "saved that year"}</span>
            </span>
          </div>
        )}
        <span className="ee-sr" aria-live="polite">
          {hp ? `Year ${hp.year}: ${signed(hp.value, 2)} M€ so far, ${signed(hp.delta, 2)} M€ ${hp.year === 0 ? "of extra capital" : "saved that year"}.` : ""}
        </span>
      </div>
      <p className="ee-xcap">Years after building</p>
    </div>
  );
}

function FlowTable({ c }: { c: CashFlow }) {
  return (
    <div className="ftable-wrap" role="region" aria-label="Cash flow against gas by year, M€" tabIndex={0}>
      <table className="ftable">
        <thead>
          <tr>
            <th scope="col">Year</th>
            <th scope="col" className="n">
              That year, discounted
            </th>
            <th scope="col" className="n">
              So far
            </th>
          </tr>
        </thead>
        <tbody>
          {c.points.map((p) => (
            <tr key={p.year}>
              <td>{p.year}</td>
              <td className="n">{signed(p.delta, 2)}</td>
              <td className="n">{signed(p.value, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
