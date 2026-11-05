// Designs side by side (CUSTOM `compare`): one row per figure, every value from the agent's ledger,
// the lowest (or highest, for spare capacity) of each row marked. Nothing is computed here.

import type { CompareView } from "../agent/types";
import { fmtNum } from "../workbench/format";
import { compareHref } from "../tabs/compare/link";
import { Arrow } from "./Icons";
import { menuProps } from "../menu";

const PICK_NAMES: Record<string, string> = { best: "best overall", cost: "cheapest", co2: "lowest CO₂", reliable: "cheapest reliable", green_reliable: "greenest reliable", gas_free: "gas-free" };

export function CompareCard({ value }: { value: CompareView }) {
  return (
    <section className="card compare-card ta-rise" aria-label="Designs side by side">
      {value.mixed && (
        <p className="compare-mixed" role="note">
          These designs were run under different conditions ({[...new Set(value.designs.map((d) => d.scenario ?? "base case"))].join(" · ")}): their costs and money are not ranked against each other.
        </p>
      )}
      <div className="table-scroll">
        <table className="compare-table">
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-only">Figure</span>
              </th>
              {value.designs.map((d) => (
                <th key={d.id} scope="col" title={d.name} {...menuProps({ kind: "design", design: { id: d.id, sub: d.name } })}>
                  <span className="alt-code">{d.id}</span>
                  {d.scenario && d.scenario !== "base case" && <span className="compare-scene">{d.scenario}</span>}
                  {d.picks.map((p) => (
                    <span key={p} className="pick-mark">
                      {PICK_NAMES[p] ?? p}
                    </span>
                  ))}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.rows
              .filter((r) => r.values.some((v) => v != null))
              .map((r) => (
                <tr key={r.key}>
                  <th scope="row">
                    {r.label}
                    {r.unit && <span className="muted"> {r.unit}</span>}
                  </th>
                  {r.values.map((v, i) => (
                    <td key={i} className={r.best === i ? "best" : undefined}>
                      {v == null ? "–" : fmtNum(v, r.digits)}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <p className="note">Bold: the lowest of the row (the most, for NPV and spare capacity). Every figure is from the designs' own runs.</p>
      <nav className="card-links" aria-label="These designs in the Compare tab">
        <a href={compareHref(value.designs.map((d) => d.id))}>
          Open in Compare <Arrow size={12} />
        </a>
      </nav>
    </section>
  );
}
