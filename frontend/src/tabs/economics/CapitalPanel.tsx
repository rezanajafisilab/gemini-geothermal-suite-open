// What it takes to build: one bar per capital item, largest first, with its size × unit cost and
// the life it is paid off over; the total (and how much more than the gas plant) pinned to the
// bottom of the card, level with the CO₂ card's end.

import { AskButton, ProvenanceChip, type Design, type Provenance } from "../../workbench";
import { Panel } from "../energy/parts";
import { eur, meur, signed } from "./format";
import { KIND_META, capexRows } from "./model";

interface Props {
  design: Design;
  prov: Provenance;
  /** The gas plant, by name: "gas boilers and electric chillers". */
  reference: string;
  delay?: number;
}

export function CapitalPanel({ design, prov, reference, delay }: Props) {
  const e = design.economics;
  const rows = capexRows(e.capex_items ?? []);
  const max = Math.max(0, ...rows.map((r) => r.meur));
  const top = rows[0];
  const v = e.versus_reference;
  // The gas plant's own capital: the design's less the extra it costs.
  const gas = v && Number.isFinite(v.extra_capex_meur) ? e.capex_meur - v.extra_capex_meur : null;
  const label = (r: (typeof rows)[number]) => `${r.item}${r.note ? ` (${r.note})` : ""} ${meur(r.meur)} M€ (${r.detail}${r.life ? `, paid off over ${r.life} years` : ""})`;
  return (
    <Panel
      title="Capital"
      sub={`${eur(e.capex_meur)} M€ to build, item by item`}
      delay={delay}
      className="ec-fill"
      aside={
        <>
          <ProvenanceChip source={prov} detail="Sizes from the design, unit costs and lives from the assumptions (sourced)" />
          <AskButton
            compact
            label="Ask about this chart"
            context={`${design.code}'s capital, ${eur(e.capex_meur)} M€, on the Economics tab`}
            question={top ? `What drives the cost of the ${top.item.toLowerCase()}, and how could it come down?` : undefined}
          />
        </>
      }
    >
      {rows.length ? (
        <ol className="ec-bars ec-spread" aria-label={`Capital: ${rows.map(label).join(", ")}.`}>
          {rows.map((r) => (
            <li key={r.key} className="ec-bar-row">
              <span className="ec-bar-label">
                <span className="ec-wf-item">
                  {r.item}
                  {r.note && <span className="ec-bar-note"> · {r.note}</span>}
                </span>
                <span className="ec-bar-detail">
                  {r.detail}
                  {r.life ? ` · ${r.life} yr` : ""}
                </span>
              </span>
              <span className="ec-bar-track" aria-hidden="true">
                <span className="ec-bar ta-grow" style={{ width: `max(2px, ${max > 0 ? (r.meur / max) * 100 : 0}%)`, background: KIND_META.capital.color }} />
              </span>
              <span className="ec-wf-value">
                {meur(r.meur)} <span className="ec-unit">M€</span>
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="ee-foot ec-none">No capital items for this design.</p>
      )}
      <div className="ec-panel-end ec-total">
        <span className="ec-total-label">
          Capital
          {v ? (
            <span className="ec-total-note">
              {signed(v.extra_capex_meur)} M€ against {reference}
              {gas != null ? ` (${eur(gas)} M€)` : ""}
            </span>
          ) : (
            <span className="ec-total-note">the gas plant the others are measured against</span>
          )}
        </span>
        <span className="ec-wf-value">
          <strong>{eur(e.capex_meur)}</strong> <span className="ec-unit">M€</span>
        </span>
      </div>
    </Panel>
  );
}
