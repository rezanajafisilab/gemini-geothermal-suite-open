// Each doublet over the year: its daily flow as an area up to its cap (dashed), its wellhead
// temperature as a line on its own scale, its planned stops shaded; the mean flow, the days it ran
// and the wellhead's range beside it. Doublets that run at different rates (the hottest first, or
// a producer open over half the aquifer) show it at a glance.

import { useMemo } from "react";

import { useWidth } from "../../components/LineChart";
import { AskButton, ProvenanceChip, fmtNum, type Design, type Provenance } from "../../workbench";
import { MONTH_START, MONTHS, doubletYears, type DoubletYear } from "./model";
import { Key, Panel } from "./parts";

const FLOW = "#C24E1C";
const TEMP = "#11181C";
const H = 86;
const PAD = { top: 8, right: 44, bottom: 18, left: 40 };

function DoubletChart({ d, tLo, tHi }: { d: DoubletYear; tLo: number; tHi: number }) {
  const [wrap, width] = useWidth(640);
  const n = d.flow.length;
  const pw = Math.max(10, width - PAD.left - PAD.right);
  const ph = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (n <= 1 ? 0 : (i / (n - 1)) * pw);
  const top = Math.max(d.cap, ...d.flow) || 1;
  const yF = (v: number) => PAD.top + ph - (v / top) * ph;
  const yT = (t: number) => PAD.top + ph - ((t - tLo) / (tHi - tLo || 1)) * ph;
  const area = useMemo(() => {
    if (!n) return "";
    const line = d.flow.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${yF(v).toFixed(1)}`).join("");
    return `${line}L${x(n - 1).toFixed(1)} ${yF(0)}L${x(0).toFixed(1)} ${yF(0)}Z`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, width]);
  const temp = useMemo(() => {
    let out = "";
    let pen = false;
    d.wellhead.forEach((t, i) => {
      if (t == null) {
        pen = false;
        return;
      }
      out += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${yT(t).toFixed(1)}`;
      pen = true;
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, width, tLo, tHi]);
  const label = `Doublet ${d.doublet}: ${d.daysOn} days on, mean ${d.mean == null ? "–" : fmtNum(d.mean, 0)} m³/h against a cap of ${fmtNum(d.cap, 0)} m³/h; wellhead ${d.tMin == null ? "–" : `${fmtNum(d.tMin)} to ${fmtNum(d.tMax ?? d.tMin)} °C`}`;
  return (
    <div className="en-dchart" ref={wrap}>
      <svg width={width} height={H} role="img" aria-label={label}>
        {d.stops.map(([a, b]) => (
          <rect key={a} className="en-dstop" x={x(a)} y={PAD.top} width={Math.max(1, x(b) - x(a))} height={ph} />
        ))}
        {MONTH_START.slice(1).map((m) => (
          <line key={m} className="en-dgrid" x1={x(m)} x2={x(m)} y1={PAD.top} y2={PAD.top + ph} />
        ))}
        <path d={area} fill={FLOW} fillOpacity={0.28} stroke={FLOW} strokeWidth={1.2} />
        <line className="en-dcap" x1={PAD.left} x2={PAD.left + pw} y1={yF(d.cap)} y2={yF(d.cap)} />
        <path d={temp} fill="none" stroke={TEMP} strokeWidth={1.4} />
        <text className="en-daxis" x={PAD.left - 6} y={yF(d.cap) + 4} textAnchor="end">
          {fmtNum(d.cap, 0)}
        </text>
        <text className="en-daxis" x={PAD.left - 6} y={yF(0) + 4} textAnchor="end">
          0
        </text>
        <text className="en-daxis" x={PAD.left + pw + 6} y={yT(tHi) + 4}>
          {fmtNum(tHi)}°
        </text>
        <text className="en-daxis" x={PAD.left + pw + 6} y={yT(tLo) + 4}>
          {fmtNum(tLo)}°
        </text>
        {MONTHS.map((m, i) => (
          <text key={m} className="en-daxis" x={x(MONTH_START[i] + 15)} y={H - 4} textAnchor="middle">
            {m[0]}
          </text>
        ))}
      </svg>
    </div>
  );
}

/** ", each stops 35 days", or ", each stops on its own dates" when the user's ranges differ. */
export function stopWords(ds: DoubletYear[]): string {
  const days = new Set(ds.filter((d) => d.stops.length).map((d) => d.stops.reduce((n, [a, b]) => n + b - a + 1, 0)));
  if (!days.size) return "";
  const split = ds.some((d) => d.stops.length > 1);
  return days.size === 1 ? `, each stops ${[...days][0]} days${split ? " (on the dates given)" : ""}` : ", each stops on its own dates";
}

export function DoubletsPanel({ design, prov }: { design: Design; prov: Provenance }) {
  const ds = useMemo(() => doubletYears(design.year, design.plant), [design.year, design.plant]);
  if (!ds.length) return null;
  // One temperature scale for every doublet, so their wellheads compare.
  const temps = ds.flatMap((d) => [d.tMin, d.tMax]).filter((t): t is number => t != null);
  const lo = temps.length ? Math.floor(Math.min(...temps) - 0.5) : 0;
  const hi = temps.length ? Math.ceil(Math.max(...temps) + 0.5) : 1;
  const base = (design.plant.dispatch ?? design.dispatch) === "base";
  return (
    <Panel
      title="The doublets over the year"
      sub={`Daily brine flow against each doublet's cap, and its wellhead temperature; ${base ? "the hottest doublet runs first" : "the doublets share the brine equally"}${stopWords(ds)}.`}
      delay={0.16}
      aside={
        <>
          <ProvenanceChip source={prov} detail="The year's dispatch, with each well's GEMINI solve" />
          <AskButton compact label="Ask about this chart" context={`the doublets of ${design.code} over the year on the Energy tab`} question="Why do the doublets run at different rates?" />
        </>
      }
    >
      <div className="ee-legend">
        <Key color={FLOW}>Brine flow, m³/h</Key>
        <Key color={TEMP} line>
          Wellhead, °C
        </Key>
        <Key swatchClass="en-dstop-key">Its planned stop</Key>
      </div>
      <ul className="en-doublets">
        {ds.map((d) => (
          <li key={d.doublet} className="en-doublet">
            <div className="en-dfacts">
              <strong>Doublet {d.doublet}</strong>
              <span>
                {d.mean == null ? "never runs" : `${fmtNum(d.mean, 0)} m³/h mean`} · {d.daysOn} days
              </span>
              <span>{d.tMin == null ? "no wellhead data" : `${fmtNum(d.tMin)}–${fmtNum(d.tMax ?? d.tMin)} °C at the wellhead`}</span>
            </div>
            <DoubletChart d={d} tLo={lo} tHi={hi} />
          </li>
        ))}
      </ul>
    </Panel>
  );
}
