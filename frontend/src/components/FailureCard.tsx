// A failure what-if (CUSTOM `failure`): units out on given days, what the design delivers through
// them and what would help. Every figure comes from the agent's runs of the year with the unit
// out and with each remedy; nothing is computed here except bar widths.

import type { FailureView } from "../agent/types";
import { fmtNum } from "../workbench/format";
import { FailureYearStrip } from "./FailureYear";
import { DoneIcon, FailIcon } from "./Icons";
import { menuProps } from "../menu";

export function FailureCard({ value }: { value: FailureView }) {
  const f = value.failed;
  const worstDay = Math.max(0.01, ...f.days.map((d) => d.heat_short_mw + d.cool_short_mw));
  const verdict = value.needed ? "A spare or backup is needed" : "No spare needed";
  return (
    <section className="card failure-card ta-rise" aria-label={`Failure what-if on ${value.design}`}>
      <div className="compact-head">
        <span className="compact-kicker failure-kicker">Failure</span>
        {value.events.map((e) => (
          <span key={e.unit + e.first} className="change-chip">
            {e.words} out {e.days >= 365 ? "all year" : `${e.from} – ${e.to}`}
          </span>
        ))}
        <span className="compact-on">
          on <span className="alt-code" {...menuProps({ kind: "design", design: { id: value.design } })}>{value.design}</span>
        </span>
        <span className={`tag ${value.needed ? "tag-red" : "tag-ok"}`}>{verdict}</span>
      </div>
      {value.events.some((e) => e.how !== "asked") && (
        <p className="note failure-how">{value.events.map((e) => (e.how !== "asked" ? `${e.words}: ${e.how}` : "")).filter(Boolean).join("; ")}</p>
      )}
      <div className="compact-figures">
        {(["heat", "cool"] as const).map((side) => {
          const x = f[side];
          return (
            <span key={side} className="compact-figure">
              <span className="tile-label">{side === "heat" ? "Heat" : "Cold"}</span>
              <strong className={`compact-value${x.days_short ? " bad" : ""}`}>{x.days_short ? `${x.days_short} days short` : "met every day"}</strong>
              {x.days_short > 0 && (
                <span className="delta bad">
                  worst {fmtNum(x.worst_mw)} MW on {x.worst_day} · {fmtNum(x.short_gwh, 2)} GWh not delivered
                </span>
              )}
            </span>
          );
        })}
        <span className="compact-figure">
          <span className="tile-label">Extra gas</span>
          <strong className="compact-value">
            {fmtNum(f.extra_gas_gwh, 2)} <span className="tile-unit">GWh</span>
          </strong>
          <span className="delta">
            {fmtNum(f.extra_co2_t, 0)} t CO₂ · {fmtNum(f.extra_cost_keur, 0)} k€
          </span>
        </span>
      </div>
      {f.days.length > 0 && (
        <div className="failure-days" role="img" aria-label={`Shortfall day by day: ${f.days.map((d) => `${d.day} ${fmtNum(d.heat_short_mw + d.cool_short_mw)} MW`).join(", ")}`}>
          {f.days.map((d) => (
            <span key={d.day} className="failure-day" title={`${d.day}: ${fmtNum(d.heat_short_mw)} MW heat short of ${fmtNum(d.heat_demand_mw)} MW; boiler ${fmtNum(d.boiler_mw)} MW`}>
              <span className="failure-bar" style={{ height: `${Math.max(4, ((d.heat_short_mw + d.cool_short_mw) / worstDay) * 44)}px` }} />
            </span>
          ))}
          <span className="failure-axis">
            <span>{f.days[0].day}</span>
            <span>{f.days[f.days.length - 1].day}</span>
          </span>
        </div>
      )}
      {value.remedies.length > 0 && (
        <table className="remedies">
          <caption className="sr-only">What would help through the same days</caption>
          <thead>
            <tr>
              <th scope="col">What would help</th>
              <th scope="col">Through those days</th>
              <th scope="col">Cost</th>
            </tr>
          </thead>
          <tbody>
            {value.remedies.map((r) => (
              <tr key={r.key} className={r.key === value.best ? "best" : undefined}>
                <th scope="row">
                  {r.covers ? <DoneIcon size={14} /> : <FailIcon size={14} />} {r.name}
                  {r.key === value.best && <span className="pick-mark">cheapest that {r.covers ? "covers it" : "helps most"}</span>}
                </th>
                <td>{r.covers ? "every day met" : `still ${fmtNum(Math.max(r.heat_short_mw, r.cool_short_mw))} MW short at worst`}</td>
                <td>
                  {fmtNum(r.capex_meur, 2)} M€ · {fmtNum(r.yearly_keur, 0)} k€/yr
                  {r.lcoe_delta != null ? ` (+${fmtNum(r.lcoe_delta, 2)} €/MWh)` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {value.spare_esp && value.spare_esp.gas_saved_gwh > 0.001 && (
        <p className="note">
          {value.spare_esp.name}: saves {fmtNum(value.spare_esp.gas_saved_gwh, 2)} GWh of gas ({fmtNum(value.spare_esp.money_saved_keur, 0)} k€ of running costs) for about {fmtNum(value.spare_esp.yearly_keur, 0)} k€ a year of capital tied up.
        </p>
      )}
      {value.yearly && <FailureYearStrip value={value.yearly} />}
      {value.reliable_plan && <p className="note">The reliable plan of this layout, {value.reliable_plan}, is sized so that any one unit can be out.</p>}
    </section>
  );
}
