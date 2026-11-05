// The year's CO₂ by the unit that lets it out (Year.co2_by_unit_t, from the plant model's own
// factors: the parts add up to the design's CO₂ total). A bar of the shares, each part labelled
// where it is wide enough, then the units as a list (name, a bar of its share, tonnes, share);
// hover or focus a part for its figures. The PDF report draws the same (report_pdf._co2).

import { useState } from "react";

import { useWidth } from "../../components/LineChart";
import { AskButton, ProvenanceChip, fmtNum, type Design, type Provenance } from "../../workbench";
import { INK, co2Parts, co2Share, type Co2Part } from "./model";
import { Panel, TableToggle } from "./parts";

/** White or the ink on a fill, whichever has the higher contrast (WCAG). */
function inkOn(hex: string): string {
  const lum = (h: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const fill = lum(hex);
  return 1.05 / (fill + 0.05) >= (fill + 0.05) / (lum(INK) + 0.05) ? "#fff" : INK;
}

const t = (v: number) => fmtNum(v, 0);

/** The words a part says on hover, focus and to a screen reader. */
function partWords(p: Co2Part, design: Design): { title: string; rows: string[] } {
  const rows = [`${t(p.t)} t CO₂ a year, ${co2Share(p.share)} of the plant's total`, p.how ? p.how[0].toUpperCase() + p.how.slice(1) : ""];
  if (p.key === "boiler") {
    const bought = design.year.co2_t?.purchased_gas ?? 0;
    if (bought > 0 && p.t - bought > 0.5) rows.push(`${t(bought)} t from the gas it buys, ${t(p.t - bought)} t from the brine's methane`);
  }
  return { title: p.label, rows: rows.filter(Boolean) };
}

export function Co2Panel({ design, prov }: { design: Design; prov: Provenance }) {
  const [table, setTable] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const [wrap, width] = useWidth(640);
  const split = co2Parts(design.year);
  if (!split) return null;
  const { parts, total, none } = split;
  const e = design.economics;
  const ref = e.reference_co2_t_per_year;
  const top = parts.reduce((a, p) => (p.t > a.t ? p : a), parts[0]);
  const shown = parts.find((p) => p.key === hover) ?? null;
  const tip = shown ? partWords(shown, design) : null;
  // The tooltip sits over the middle of its part: where the parts before it end, plus half of it.
  const before = shown ? parts.slice(0, parts.indexOf(shown)).reduce((a, p) => a + p.share, 0) : 0;
  const at = shown ? Math.min(0.85, Math.max(0.15, before + shown.share / 2)) : 0;
  const summary = `The year's ${t(total)} t of CO₂ by unit: ${parts.map((p) => `${p.label} ${t(p.t)} t (${co2Share(p.share)})`).join(", ")}.${none.length ? ` No CO₂ from: ${none.join(", ")}.` : ""}`;
  return (
    <Panel
      title="CO₂ by unit over the year"
      sub="Each unit's share of the plant's CO₂ a year: the gas it burns, the brine's own CO₂ let out, and the grid's CO₂ on the electricity it draws."
      delay={0.15}
      className="co2-panel"
      aside={
        <>
          <ProvenanceChip source={prov} detail="The year's gas and electricity, with the plant model's CO₂ factors" />
          <TableToggle on={table} onChange={setTable} />
          <AskButton
            compact
            label="Ask about this chart"
            context={`${design.code}'s CO₂ by unit on the Energy tab`}
            question={`The ${top.label.toLowerCase()} lets out ${co2Share(top.share)} of the CO₂. What would cut it most?`}
          />
        </>
      }
    >
      <p className="co2-total">
        <strong>{t(total)}</strong>
        <span className="co2-unit">t CO₂ a year</span>
        {ref > 0 && e.versus_reference && (
          <span className="co2-vs">
            {fmtNum(Math.abs(e.co2_saving_pct), 0)}% {e.co2_saving_pct >= 0 ? "less" : "more"} than the gas reference ({t(ref)} t)
          </span>
        )}
      </p>
      {table ? (
        <div className="ftable-wrap" role="region" aria-label="CO₂ by unit, t a year" tabIndex={0}>
          <table className="ftable">
            <thead>
              <tr>
                <th scope="col">Unit</th>
                <th scope="col">Where its CO₂ comes from</th>
                <th scope="col" className="n">
                  t CO₂ a year
                </th>
                <th scope="col" className="n">
                  Share
                </th>
              </tr>
            </thead>
            <tbody>
              {parts.map((p) => (
                <tr key={p.key}>
                  <td>{p.label}</td>
                  <td>{p.how}</td>
                  <td className="n">{t(p.t)}</td>
                  <td className="n">{co2Share(p.share)}</td>
                </tr>
              ))}
              <tr className="co2-sum">
                <td>All units</td>
                <td />
                <td className="n">{t(total)}</td>
                <td className="n">100%</td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <>
          <div className="co2-plot" ref={wrap} onPointerLeave={() => setHover(null)}>
            <div className="co2-bar ta-grow" role="list" aria-label={summary}>
              {parts.map((p) => {
                const words = partWords(p, design);
                const label = `${fmtNum(p.share * 100, 0)}%`;
                // The share inside the part when it fits: 7.5 px a character and 16 px of padding.
                const fits = p.share * (width - 2 * (parts.length - 1)) >= label.length * 7.5 + 16;
                return (
                  <span
                    key={p.key}
                    role="listitem"
                    className={`co2-seg${hover && hover !== p.key ? " is-dim" : ""}`}
                    style={{ flexGrow: p.share, background: p.color, color: inkOn(p.color) }}
                    tabIndex={0}
                    aria-label={`${words.title}: ${words.rows.join("; ")}`}
                    onPointerEnter={() => setHover(p.key)}
                    onFocus={() => setHover(p.key)}
                    onBlur={() => setHover(null)}
                  >
                    {fits && <span aria-hidden="true">{label}</span>}
                  </span>
                );
              })}
            </div>
            {tip && shown && (
              <div className="ee-tip co2-tip" style={{ left: `${at * 100}%` }} aria-hidden="true">
                <span className="ee-tip-title">
                  <span className="ee-swatch" style={{ background: shown.color }} /> {tip.title}
                </span>
                {tip.rows.map((r) => (
                  <span key={r} className="ee-tip-sub">
                    {r}
                  </span>
                ))}
              </div>
            )}
          </div>
          <ul className="co2-list">
            {parts.map((p) => (
              <li key={p.key} className={hover && hover !== p.key ? "is-dim" : undefined} onPointerEnter={() => setHover(p.key)} onPointerLeave={() => setHover(null)}>
                <span className="co2-name">
                  <span className="ee-swatch" style={{ background: p.color }} aria-hidden="true" />
                  {p.label}
                </span>
                <span className="co2-track" aria-hidden="true">
                  <span className="ta-grow" style={{ width: `${Math.max(0.4, p.share * 100)}%`, background: p.color }} />
                </span>
                <span className="co2-t">
                  {t(p.t)} <span className="co2-u">t</span>
                </span>
                <span className="co2-share">{co2Share(p.share)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {none.length > 0 && <p className="ee-foot">No CO₂ from: {none.map((n, i) => (i ? ", " : "") + (/^[A-Z][a-z]/.test(n) ? n[0].toLowerCase() + n.slice(1) : n)).join("")}.</p>}
    </Panel>
  );
}
