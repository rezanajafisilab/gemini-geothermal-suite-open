// How sure a design's result is (CUSTOM `uncertainty`): the cost of heat and cold and the NPV
// against gas from P10 to P90 over the Monte Carlo runs, the share of runs that beat gas, and a
// tornado of what moves the cost most. Every figure is from the sensitivity runs.

import type { UncertaintyView } from "../agent/types";
import { fmtNum } from "../workbench/format";
import { menuProps } from "../menu";

export function UncertaintyCard({ value }: { value: UncertaintyView }) {
  const t = value.tornado;
  const lo = Math.min(...t.map((x) => Math.min(x.lcoe_low, x.lcoe_high)), value.base.lcoe ?? Infinity);
  const hi = Math.max(...t.map((x) => Math.max(x.lcoe_low, x.lcoe_high)), value.base.lcoe ?? -Infinity);
  const span = hi - lo || 1;
  const at = (x: number) => `${((x - lo) / span) * 100}%`;
  return (
    <section className="card compare-card uncertainty-card ta-rise" aria-label={`How sure: ${value.design}`}>
      <div className="compact-head">
        <span className="compact-kicker">How sure</span>
        <span className="alt-code" {...menuProps({ kind: "design", design: { id: value.design } })}>{value.design}</span>
        {value.samples ? <span className="note">{value.samples} runs</span> : null}
      </div>
      <div className="compact-figures">
        {value.lcoe && (
          <span className="compact-figure">
            <span className="tile-label">Cost of heat and cold, P10–P90</span>
            <strong className="compact-value">
              {fmtNum(value.lcoe.p10)}–{fmtNum(value.lcoe.p90)} <span className="tile-unit">€/MWh</span>
            </strong>
            <span className="delta">median {fmtNum(value.lcoe.p50)}</span>
          </span>
        )}
        {value.npv && (
          <span className="compact-figure">
            <span className="tile-label">NPV against gas, P10–P90</span>
            <strong className="compact-value">
              {fmtNum(value.npv.p10)}–{fmtNum(value.npv.p90)} <span className="tile-unit">M€</span>
            </strong>
            <span className={`delta ${value.npv.above_zero >= 0.5 ? "good" : "bad"}`}>beats gas in {fmtNum(value.npv.above_zero * 100, 0)} % of runs</span>
          </span>
        )}
      </div>
      {t.length > 0 && (
        <div className="tornado" role="img" aria-label={`What moves the cost most: ${t.map((x) => `${x.label} ${fmtNum(x.lcoe_low)} to ${fmtNum(x.lcoe_high)} €/MWh`).join("; ")}`}>
          {t.map((x) => {
            const a = Math.min(x.lcoe_low, x.lcoe_high);
            const b = Math.max(x.lcoe_low, x.lcoe_high);
            return (
              <div key={x.key} className="tornado-row">
                <span className="tornado-label">
                  {x.label}
                  <span className="muted">
                    {" "}
                    {fmtNum(x.from)}–{fmtNum(x.to)} {x.unit}
                  </span>
                </span>
                <span className="tornado-track">
                  <span className="tornado-bar" style={{ left: at(a), width: `calc(${at(b)} - ${at(a)})` }} />
                  {value.base.lcoe != null && <span className="tornado-base" style={{ left: at(value.base.lcoe) }} />}
                </span>
                <span className="tornado-range">
                  {fmtNum(x.lcoe_low)}–{fmtNum(x.lcoe_high)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
