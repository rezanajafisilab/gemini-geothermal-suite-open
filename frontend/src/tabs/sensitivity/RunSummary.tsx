// The selection in short, beside the parameter list: what is varied and measured, and the model
// runs it costs, split by what each part draws (the base design, the tornado's range ends, the
// spider's points inside the ranges, the Monte Carlo samples), with a time estimate from the last
// run. The parameters' colours are their lines' in the spider.

import type { SensParam } from "../../workbench";
import { BAND, LOW, slotColor } from "./colors";
import { lowerFirst, runCount, trimNum, type McSetting, type ParamRow } from "./params";

const PART_COLORS = { base: "#11181c", ends: LOW, inside: "#2a78d6", samples: BAND };

interface Props {
  rows: ParamRow[];
  slots: Record<string, number>;
  catalogue: Map<string, SensParam>;
  /** The outputs measured, by name. */
  outputs: string[];
  mc: McSetting;
  /** Seconds per model run in the last run, for an estimate. */
  secondsPerRun: number | null;
}

export function RunSummary({ rows, slots, catalogue, outputs, mc, secondsPerRun }: Props) {
  const p = rows.length;
  const c = runCount(p, mc.on ? mc.samples : 0);
  const parts = [
    { key: "base", label: "Base design", detail: null, n: c.base },
    { key: "ends", label: "One at a time", detail: `${p} × 2 range ends`, n: c.ends },
    { key: "inside", label: "Across each range", detail: `${p} × 3 points inside`, n: c.inside },
    { key: "samples", label: "All together", detail: mc.on ? "Monte Carlo samples" : "Monte Carlo off", n: c.samples },
  ] as const;
  const secs = secondsPerRun != null && secondsPerRun > 0 ? secondsPerRun * c.total : null;
  return (
    <div className="sen-side-block sen-sum" role="group" aria-labelledby="sen-sum-h">
      <div className="sen-sum-head">
        <h2 id="sen-sum-h">This run</h2>
        <span className="sen-sum-total">
          <strong>{c.total}</strong> model runs{secs != null && <> · about {secs < 10 ? trimNum(secs, 1) : Math.round(secs)} s</>}
        </span>
      </div>
      <p className="sen-sum-sel">
        <span className="sen-sum-dots" aria-hidden="true">
          {rows.map((r) => (
            <i key={r.key} style={{ background: slotColor(slots[r.key]) }} title={catalogue.get(r.key)?.label ?? r.key} />
          ))}
        </span>
        {p === 1 ? "1 parameter" : `${p} parameters`} varied, {outputs.length === 1 ? lowerFirst(outputs[0]) : `${outputs.length} outputs`} measured
      </p>
      <span className="sen-sum-bar" role="img" aria-label={`${c.total} model runs: ${parts.map((x) => `${x.label.toLowerCase()} ${x.n}`).join(", ")}`}>
        {parts
          .filter((x) => x.n > 0)
          .map((x) => (
            <span key={x.key} style={{ flexGrow: x.n, background: PART_COLORS[x.key] }} />
          ))}
      </span>
      <ul className="sen-sum-parts" aria-hidden="true">
        {parts.map((x) => (
          <li key={x.key} className={x.n ? undefined : "is-off"}>
            <i style={{ background: PART_COLORS[x.key] }} />
            <span className="sen-sum-label">
              {x.label}
              {x.detail && <span>{x.detail}</span>}
            </span>
            <strong>{x.n}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
