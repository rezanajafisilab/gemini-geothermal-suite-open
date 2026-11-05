// Failures over a year, on the failure card: what failures cost the design a year on average
// (expected over every start day), unit by unit, the heat and cold not delivered, and whether a
// spare ESP pays. Every figure is the agent's (reliability.yearly_view); only bar widths are
// worked out here.

import type { FailureYear } from "../agent/types";
import { fmtNum, fmtSigned } from "../workbench/format";

type Unit = FailureYear["units"][number];
type Part = "running_keur" | "grid_keur" | "lost_keur" | "repair_keur";

/** The three parts of a unit's cost, in the order they are stacked. */
/** A unit's cost of one part, k€ a year (the grid charge is absent on older replies). */
const part = (u: Unit, key: Part): number => u[key] ?? 0;

export const PARTS: { key: Part; label: string; cls: string }[] = [
  { key: "running_keur", label: "gas, power and CO₂", cls: "fy-running" },
  { key: "grid_keur", label: "grid charge (past 600 hours)", cls: "fy-grid" },
  { key: "lost_keur", label: "heat and cold not delivered", cls: "fy-lost" },
  { key: "repair_keur", label: "repairs", cls: "fy-repair" },
];

/** Units costing less than this a year are counted, not drawn. */
export const DRAWN_KEUR = 0.5;

/** A small number without trailing zeros: 0.5, 0.046, 0.126. */
function rate(x: number): string {
  const s = fmtNum(x, 3);
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}

function outFor(days: number): string {
  return days < 1 ? `${fmtNum(days * 24, 0)} h` : `${fmtNum(days, 0)} days`;
}

/** A unit's bar, in words: its parts, how often it fails and for how long. */
export function unitTitle(u: Unit): string {
  const parts = PARTS.filter((p) => p.key !== "grid_keur" || part(u, p.key) > 0)
    .map((p) => `${p.label} ${fmtNum(part(u, p.key), 0)}`)
    .join(", ");
  return `${u.label}: ${fmtNum(u.total_keur, 0)} k€ a year (${parts}); ${rate(u.failures_per_year)} failures a year, out ${outFor(u.repair_days)} each`;
}

export function FailureYearStrip({ value }: { value: FailureYear }) {
  const drawn = value.units.filter((u) => u.total_keur >= DRAWN_KEUR);
  const small = value.units.length - drawn.length;
  const widest = Math.max(0.01, ...drawn.map((u) => PARTS.reduce((s, p) => s + Math.max(0, part(u, p.key)), 0)));
  const shown = PARTS.filter((p) => drawn.some((u) => part(u, p.key) > 0));
  const spare = value.spare_esp;
  const [lo, hi] = value.range_keur;
  return (
    <section className="failure-year" aria-label="Failures over a year">
      <div className="failure-year-head">
        <span className="failure-year-kicker">Failures over a year</span>
        <span className="failure-year-sub">expected, on average over every start day</span>
        {spare && (
          <span
            className={`tag ${spare.worth ? "tag-ok" : "tag-amber"}`}
            title={`A spare ESP (${fmtNum(spare.price_meur, 2)} M€, ${fmtNum(spare.yearly_keur, 0)} k€ a year): the doublet back in ${fmtNum(spare.swap_days, 0)} days instead of ${fmtNum(spare.no_spare_days, 0)}. It pays if an ESP fails more often than ${spare.break_even_every ?? "never"}; taken: ${spare.every}.`}
          >
            {spare.worth ? "Spare ESP pays" : "Spare ESP not worth it"}
          </span>
        )}
      </div>
      <div className="compact-figures">
        <span className="compact-figure">
          <span className="tile-label">{spare ? "Cost, no spare ESP" : "Cost"}</span>
          <strong className="compact-value">
            {fmtNum(value.total_keur, 0)} <span className="tile-unit">k€/yr</span>
          </strong>
          <span className="delta">
            {fmtNum(lo, 0)}–{fmtNum(hi, 0)} k€ over the failure rates{spare ? ` · ${fmtNum(value.with_spare_keur, 0)} k€ with a spare` : ""}
          </span>
        </span>
        <span className="compact-figure">
          <span className="tile-label">Not delivered</span>
          <strong className={`compact-value${value.lost_mwh >= 0.5 ? " bad" : ""}`}>
            {fmtNum(value.lost_mwh, 0)} <span className="tile-unit">MWh/yr</span>
          </strong>
          <span className="delta">
            valued at {fmtNum(value.lost_eur_per_mwh, 0)} €/MWh (lost sale) · {fmtNum(value.stress_keur, 0)} k€/yr at {fmtNum(value.stress_eur_per_mwh, 0)} €/MWh
          </span>
        </span>
        {spare && (
          <span className="compact-figure">
            <span className="tile-label">Spare ESP, {fmtNum(spare.price_meur, 2)} M€</span>
            <strong className={`compact-value${spare.worth ? " fy-good" : ""}`}>
              {fmtSigned(spare.net_keur, 0)} <span className="tile-unit">k€/yr</span>
            </strong>
            <span className="delta">
              saves {fmtNum(spare.saving_keur, 0)} for {fmtNum(spare.yearly_keur, 0)} k€/yr · back in {fmtNum(spare.swap_days, 0)} days, not {fmtNum(spare.no_spare_days, 0)}
            </span>
          </span>
        )}
      </div>
      {drawn.length > 0 && (
        <ul className="fy-bars" aria-label="Cost a year by unit">
          {drawn.map((u) => (
            <li key={u.unit} className="fy-row" title={unitTitle(u)}>
              <span className="fy-label">{u.label}</span>
              <span className="fy-track" aria-hidden="true">
                {shown.map((p) =>
                  part(u, p.key) > 0 ? <span key={p.key} className={`fy-seg ${p.cls}`} style={{ width: `${(part(u, p.key) / widest) * 100}%` }} /> : null,
                )}
              </span>
              <span className="fy-value">{fmtNum(u.total_keur, 0)} k€</span>
            </li>
          ))}
        </ul>
      )}
      {shown.length > 0 && (
        <div className="fy-legend">
          {shown.map((p) => (
            <span key={p.key} className="fy-key">
              <span className={`fy-swatch ${p.cls}`} aria-hidden="true" />
              {p.label}
            </span>
          ))}
        </div>
      )}
      {(small > 0 || value.skipped.length > 0) && (
        <p className="note fy-note">
          {small > 0 ? `${small} more ${small === 1 ? "unit" : "units"} under ${fmtNum(DRAWN_KEUR, 1)} k€ a year each.` : ""}
          {value.skipped.length > 0 ? ` No failure data, not counted: ${value.skipped.join(", ")}.` : ""}
        </p>
      )}
    </section>
  );
}
