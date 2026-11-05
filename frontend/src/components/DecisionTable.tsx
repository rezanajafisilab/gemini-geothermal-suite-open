// The options for a decision (CUSTOM `decision`): today's gas plant, the recommended design and
// the other picks, with what a council asks: money up front and a year, per home, CO₂, how much
// heat still comes from gas, whether a failure is covered, and the cost per tonne avoided.

import type { DecisionView } from "../agent/types";
import { fmtNum } from "../workbench/format";
import { menuProps } from "../menu";

const vsWords = (x: number | null) => (x == null ? "" : Math.round(Math.abs(x) * 100) === 0 ? "as gas" : `${Math.round(Math.abs(x) * 100)} % ${x < 0 ? "cheaper" : "dearer"}`);

export function DecisionTable({ value }: { value: DecisionView }) {
  const cols: { key: string; label: string; cell: (r: DecisionView["rows"][number]) => string }[] = [
    { key: "capex", label: "Capital", cell: (r) => `${fmtNum(r.capex_meur)} M€` },
    { key: "lcoe", label: "Heat and cold", cell: (r) => `${fmtNum(r.lcoe)} €/MWh${r.vs_gas != null ? ` · ${vsWords(r.vs_gas)}` : ""}` },
    { key: "year", label: "A year", cell: (r) => `${fmtNum(r.yearly_meur, 2)} M€` },
    { key: "home", label: "Heat per home", cell: (r) => `${fmtNum(r.per_home_eur, 0)} €` },
    { key: "co2", label: "CO₂", cell: (r) => `${fmtNum(r.co2_t, 0)} t${r.co2_cut != null ? ` · −${fmtNum(r.co2_cut * 100, 0)} %` : ""}` },
    { key: "gas", label: "Heat from gas", cell: (r) => `${fmtNum(r.gas_share * 100, 0)} %` },
    { key: "n1", label: "A unit fails", cell: (r) => (r.n1 == null ? "–" : r.n1 === 0 ? "covered" : `${r.n1} cases short`) },
    { key: "per_t", label: "Per t CO₂ avoided", cell: (r) => (r.eur_per_t == null ? "–" : r.eur_per_t < 0 ? `saves ${fmtNum(-r.eur_per_t, 0)} €` : `${fmtNum(r.eur_per_t, 0)} €`) },
  ];
  return (
    <section className="card compare-card decision-card ta-rise" aria-label="The options for a decision">
      <div className="table-scroll">
        <table className="compare-table">
          <caption className="sr-only">Today's gas plant against the recommended design and the other picks</caption>
          <thead>
            <tr>
              <th scope="col">Option</th>
              {cols.map((c) => (
                <th key={c.key} scope="col">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.rows.map((r, i) => (
              <tr key={r.id} className={i === 1 ? "recommended" : undefined} {...(i > 0 && r.id ? menuProps({ kind: "design", design: { id: r.id, sub: r.label } }) : {})}>
                <th scope="row">
                  <span className="decision-label">{r.label}</span>
                  <span className="muted">{r.id}</span>
                </th>
                {cols.map((c) => (
                  <td key={c.key}>{c.cell(r)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">Heat per home: {value.home_words}. Every figure is from the designs' own runs; the gas plant is gas boilers and electric chillers under the same conditions.</p>
    </section>
  );
}
