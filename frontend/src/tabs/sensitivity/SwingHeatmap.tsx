// Which parameter moves which output: each cell is a parameter's share of that output's
// one-at-a-time swing (its swing over the sum of all the swings), one teal hue light to dark,
// the share written in the cell. The output on show is outlined; a column header switches to it.

import type { SensOutput, Sensitivity } from "../../workbench";
import { RAMP_GRADIENT, rampColor } from "./colors";
import { lowerFirst, swingShares, tornadoRows, trimNum } from "./params";

interface Props {
  result: Sensitivity;
  outputs: SensOutput[];
  current: string;
  onPick: (key: string) => void;
}

export function SwingHeatmap({ result, outputs, current, onPick }: Props) {
  const keys = outputs.map((o) => o.key);
  const shares = swingShares(result, keys);
  const order = tornadoRows(result, current);
  return (
    <div className="sen-heat">
      <div className="sen-heat-key" aria-hidden="true">
        0%
        <span style={{ background: RAMP_GRADIENT }} />
        100% of the swing
      </div>
      <div className="sen-heat-scroll">
        <table className="sen-heat-table">
          <thead>
            <tr>
              <th scope="col" className="sen-heat-corner">
                <span className="sr-only">Parameter</span>
              </th>
              {outputs.map((o) => (
                <th key={o.key} scope="col" className={o.key === current ? "is-on" : undefined}>
                  <button type="button" onClick={() => onPick(o.key)} aria-pressed={o.key === current}>
                    {o.label}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {order.map((r) => (
              <tr key={r.key}>
                <th scope="row">{r.label}</th>
                {outputs.map((o) => {
                  const s = shares[o.key]?.[r.key] ?? 0;
                  const { bg, ink } = rampColor(s);
                  return (
                    <td
                      key={o.key}
                      className={o.key === current ? "is-on" : undefined}
                      style={{ background: bg, color: ink }}
                      title={`${r.label}: ${trimNum(s * 100, 0)}% of the swing in the ${lowerFirst(o.label)}`}
                    >
                      {s > 0.005 ? `${trimNum(s * 100, 0)}%` : "–"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
