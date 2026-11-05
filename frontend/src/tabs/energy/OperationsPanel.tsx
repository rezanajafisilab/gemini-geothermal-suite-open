// The operator's week: each day's setpoints from the design's year (operations.ts). A week at a
// time, moved with the arrows or picked from the month buttons; the week or the whole year
// downloads as CSV for the plant's control room.

import { useMemo, useState } from "react";

import { fmtNum, type Design, type Provenance, ProvenanceChip } from "../../workbench";
import { MONTH_START, MONTHS } from "./model";
import { operatingPlan, planCsv, type PlanDay } from "./operations";
import { Panel } from "./parts";

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const mw = (v: number) => (v > 0.005 ? fmtNum(v, v < 10 ? 1 : 0) : "–");

export function OperationsPanel({ design, prov }: { design: Design; prov: Provenance }) {
  // The coldest week first: the one an operator plans hardest.
  const coldest = useMemo(() => {
    const d = design.year.daily_mw?.heat?.demand ?? [];
    const i = d.length ? d.indexOf(Math.max(...d)) : 0;
    return Math.max(0, Math.min(358, i - 3));
  }, [design]);
  const [start, setStart] = useState<number | null>(null);
  const from = start ?? coldest;
  const plan = useMemo(() => operatingPlan(design, from, 7), [design, from]);
  const hasCold = design.year.cool_demand_gwh > 0;
  const k = design.year.doublets?.length ?? 0;
  const code = design.code.replace(/[^\w.-]+/g, "-");
  return (
    <Panel
      title="Operating plan"
      sub="Each day's setpoints from the design's year: what each doublet pumps and at what temperatures, what each unit makes, and the days that need care."
      aside={
        <>
          <ProvenanceChip source={prov} detail="The year's dispatch, day by day" />
          <button type="button" className="btn btn-soft ta-btn ta-soft op-dl" onClick={() => download(`dioscuri-${code}-week.csv`, planCsv(design, plan))}>
            This week (CSV)
          </button>
          <button type="button" className="btn btn-soft ta-btn ta-soft op-dl" onClick={() => download(`dioscuri-${code}-year.csv`, planCsv(design, operatingPlan(design, 0, 365)))}>
            The year (CSV)
          </button>
        </>
      }
      delay={0.16}
      className="op-panel"
    >
      <div className="op-nav" role="group" aria-label="Which week">
        <button type="button" className="op-step ta-btn" aria-label="The week before" disabled={from <= 0} onClick={() => setStart(Math.max(0, from - 7))}>
          ‹
        </button>
        <strong className="op-week">
          {plan[0]?.label} – {plan[plan.length - 1]?.label}
        </strong>
        <button type="button" className="op-step ta-btn" aria-label="The week after" disabled={from >= 358} onClick={() => setStart(Math.min(358, from + 7))}>
          ›
        </button>
        <span className="op-months">
          {MONTHS.map((m, i) => (
            <button key={m} type="button" className={`op-month ta-btn${from >= MONTH_START[i] && from < (MONTH_START[i + 1] ?? 365) ? " on" : ""}`} onClick={() => setStart(MONTH_START[i])}>
              {m}
            </button>
          ))}
          <button type="button" className={`op-month ta-btn${start == null ? " on" : ""}`} onClick={() => setStart(null)} title="The week around the year's peak heat">
            Peak
          </button>
        </span>
      </div>
      <div className="op-scroll">
        <table className="op-table">
          <thead>
            <tr>
              <th scope="col">Day</th>
              <th scope="col">Heat MW</th>
              <th scope="col">Geothermal</th>
              <th scope="col">Heat pump</th>
              <th scope="col">Boiler</th>
              {hasCold && <th scope="col">Cold MW</th>}
              {hasCold && <th scope="col">Free · abs · chillers</th>}
              {Array.from({ length: k }, (_, j) => (
                <th key={j} scope="col">
                  Doublet {j + 1}
                  <span className="op-th-sub">m³/h · in → out °C</span>
                </th>
              ))}
              <th scope="col">Power MW</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {plan.map((p: PlanDay) => (
              <tr key={p.day} className={p.notes.length ? "op-flag" : undefined}>
                <th scope="row">{p.label}</th>
                <td>{mw(p.heat.demand)}</td>
                <td>{mw(p.heat.geo)}</td>
                <td>{mw(p.heat.hp)}</td>
                <td>{mw(p.heat.boiler + p.heat.electric_boiler)}</td>
                {hasCold && <td>{mw(p.cold.demand)}</td>}
                {hasCold && (
                  <td>
                    {mw(p.cold.free)} · {mw(p.cold.abs)} · {mw(p.cold.chill)}
                  </td>
                )}
                {p.doublets.map((d, j) => (
                  <td key={j} className={d.on ? undefined : "op-off"}>
                    {d.on ? (
                      <>
                        {fmtNum(d.flow, 0)} · {d.wellhead != null ? fmtNum(d.wellhead) : "–"} → {d.reinjection != null ? fmtNum(d.reinjection) : "–"}
                        {d.atCap && (
                          <span className="op-cap" title={`The brine is cooled to the ${design.plant.max_brine_cooling_k ?? 40} K cap: the doublet gives all it can`}>
                            at cap
                          </span>
                        )}
                      </>
                    ) : (
                      "off"
                    )}
                  </td>
                ))}
                <td>{mw(p.electricity)}</td>
                <td className="op-notes">{p.notes.join("; ") || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
