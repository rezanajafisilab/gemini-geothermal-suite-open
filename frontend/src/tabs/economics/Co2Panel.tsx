// CO₂ a year: the design against the gas plant, on one scale, with the saving; then where the
// design's own CO₂ comes from (the year's breakdown: gas bought for the boiler, the gas that comes
// up with the brine, and each use of grid power), pinned to the bottom of the card so it lines up
// with the Capital card beside it.

import { AskButton, ProvenanceChip, type Design, type Provenance } from "../../workbench";
import { Panel } from "../energy/parts";
import { eur, tonnes } from "./format";
import { co2Split, type Co2Source, type Co2Split } from "./model";

const GOOD = "#2BA866";
const BAD = "#B42318";
const REF = "#9AA5AB";

/** A word on each source beside its name (the bought gas's name says it all). */
const FUEL: Record<Co2Source["fuel"], string | null> = { gas: null, brine: "burnt or flared", grid: "grid" };

export function Co2Panel({
  design,
  prov,
  carbonPrice,
  delay,
}: {
  design: Design;
  prov: Provenance;
  /** €/t, from the assumptions. */
  carbonPrice: number | null;
  delay?: number;
}) {
  const e = design.economics;
  const isRef = e.versus_reference == null;
  const ours = e.co2_t_per_year;
  const ref = e.reference_co2_t_per_year;
  const max = Math.max(ours, ref, 1);
  const saved = ref - ours;
  const better = saved >= 0;
  const split = co2Split(design);
  const rows = isRef
    ? [{ label: "Gas plant (this design)", t: ours, color: REF }]
    : [
        { label: `${design.code}, this design`, t: ours, color: better ? GOOD : BAD },
        { label: "Gas boilers and electric chillers", t: ref, color: REF },
      ];
  return (
    <Panel
      title="CO₂ a year"
      sub={isRef ? "The gas boilers and electric chillers every other design is measured against" : "This design against gas boilers and electric chillers, same demand"}
      delay={delay}
      className="ec-fill"
      aside={
        <>
          <ProvenanceChip source={prov} detail="Gas burnt, the gas that comes up with the brine, and grid electricity, each with its CO₂ factor" />
          <AskButton
            compact
            label="Ask about this chart"
            context={`${design.code}'s CO₂, ${tonnes(ours)} t a year${isRef ? "" : ` against ${tonnes(ref)} t for gas`}, on the Economics tab`}
            question={isRef ? "Where does the gas plant's CO₂ come from?" : `Where do ${design.code}'s remaining ${tonnes(ours)} t of CO₂ a year come from?`}
          />
        </>
      }
    >
      <ol className="ec-bars" aria-label={rows.map((r) => `${r.label}: ${tonnes(r.t)} t CO₂ a year`).join("; ")}>
        {rows.map((r) => (
          <li key={r.label} className="ec-bar-row">
            <span className="ec-bar-label">
              <span className="ec-wf-item">{r.label}</span>
            </span>
            <span className="ec-bar-track" aria-hidden="true">
              <span className="ec-bar ta-grow" style={{ width: `max(2px, ${(r.t / max) * 100}%)`, background: r.color }} />
            </span>
            <span className="ec-wf-value">
              {tonnes(r.t)} <span className="ec-unit">t</span>
            </span>
          </li>
        ))}
      </ol>
      {!isRef && (
        <p className={`ec-co2-saving ${better ? "good" : "bad"}`}>
          <strong>
            {better ? "−" : "+"}
            {eur(Math.abs(e.co2_saving_pct))}%
          </strong>
          <span>{better ? `${tonnes(saved)} t of CO₂ a year less than gas` : `${tonnes(-saved)} t of CO₂ a year more than gas`}</span>
        </p>
      )}
      <div className="ec-panel-end">
        {split && <Co2Sources split={split} code={design.code} />}
        <p className="ee-foot">
          {carbonPrice != null && carbonPrice > 0
            ? `Gas CO₂ is priced at ${eur(carbonPrice)} €/t in these costs; the grid's CO₂ is already in the electricity price (EU ETS).`
            : "CO₂ isn't priced in the costs (0 €/t): set a CO₂ price in the assumptions to count it."}
        </p>
      </div>
    </Panel>
  );
}

/** One bar of the design's CO₂ split by source, a key under it, and the gas / grid totals. */
function Co2Sources({ split, code }: { split: Co2Split; code: string }) {
  const pct = (t: number) => `${Math.round((t / split.total) * 100)}%`;
  const label = `Where ${code}'s ${tonnes(split.total)} t come from: ${split.sources.map((s) => `${s.item.toLowerCase()}${FUEL[s.fuel] ? ` (${FUEL[s.fuel]})` : ""} ${tonnes(s.t)} t`).join(", ")}.`;
  return (
    <div className="ec-co2-src">
      <div className="ec-co2-src-head">
        <h3>Where {code}'s CO₂ comes from</h3>
        <span className="ec-co2-sides">
          {split.gas > 0 && (
            <>
              gas <strong>{tonnes(split.gas)} t</strong>
            </>
          )}
          {split.gas > 0 && split.grid > 0 && " · "}
          {split.grid > 0 && (
            <>
              electricity <strong>{tonnes(split.grid)} t</strong>
            </>
          )}
        </span>
      </div>
      <span className="ec-co2-bar" role="img" aria-label={label}>
        {split.sources.map((s) => (
          <span key={s.key} className="ta-grow" style={{ flexGrow: s.t, background: s.color }} title={`${s.item}: ${tonnes(s.t)} t`} />
        ))}
      </span>
      <ul className="ec-co2-keys" aria-hidden="true">
        {split.sources.map((s) => (
          <li key={s.key}>
            <span className="ee-swatch" style={{ background: s.color }} />
            <span className="ec-co2-key-name">
              {s.item}
              {FUEL[s.fuel] && <span className="ec-co2-fuel">{FUEL[s.fuel]}</span>}
            </span>
            <span className="ec-co2-key-t">
              {tonnes(s.t)} t <span className="ec-unit">{pct(s.t)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
