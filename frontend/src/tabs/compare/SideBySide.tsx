// The ticked designs side by side (two to four): a column per design (its name, scenario, picks
// and links into the tabs) and a row per figure, in sections. With every design from the same
// scenario the best of each ranked row is marked; when their scenarios differ an amber banner
// says so and nothing is marked, since their figures rest on different assumptions.

import { forwardRef } from "react";

import { Cross } from "../../components/Icons";
import type { LibraryRow } from "../../workbench";
import { DesignName, FailTag, OpenLinks, PickTags, ScenarioChip, designLabel, type OpenTab } from "./bits";
import { compareSections, scenarioKey, type ScenarioGroup } from "./library";

interface Props {
  rows: LibraryRow[];
  /** The scenarios of the rows (one when they share it). */
  scenarios: ScenarioGroup[];
  onRemove: (id: string) => void;
  onClose: () => void;
  onOpen: (r: LibraryRow, tab: OpenTab) => void;
  opening: string | null;
  error: string | null;
}

export const SideBySide = forwardRef<HTMLElement, Props>(function SideBySide({ rows, scenarios, onRemove, onClose, onOpen, opening, error }, ref) {
  const same = new Set(rows.map((r) => scenarioKey(r.scenario))).size <= 1;
  const sections = compareSections(rows, same);
  return (
    <section ref={ref} className="lib-card lib-sbs ta-rise" aria-labelledby="lib-sbs-title" tabIndex={-1}>
      <header className="lib-card-head">
        <div>
          <h2 id="lib-sbs-title">Side by side</h2>
          <p className="lib-card-sub">
            {rows.length} designs
            {same && scenarios[0] ? ` · all in ${scenarios[0].label} · the best of each figure is marked` : ""}
          </p>
        </div>
        <button type="button" className="lib-icon-btn ta-btn" onClick={onClose} aria-label="Close the side by side">
          <Cross size={11} />
        </button>
      </header>
      {!same && (
        <div className="lib-banner is-amber" role="note">
          <strong>Different scenarios.</strong> These designs come from {scenarios.length} scenarios ({scenarios.map((s) => s.label).join("; ")}). Their figures rest on
          different assumptions (prices, reservoir, what “best” means), so no figure is marked best. To rank designs, compare designs of one scenario.
        </div>
      )}
      {error && (
        <div className="lib-banner is-red" role="alert">
          {error}
        </div>
      )}
      <div className="lib-sbs-scroll">
        <table className="lib-sbs-table">
          <caption className="sr-only">
            {rows.map(designLabel).join(", ")} side by side{same ? ", with the best of each figure marked" : ""}
          </caption>
          <colgroup>
            <col className="lib-sbs-labelcol" />
            {rows.map((r) => (
              <col key={r.id} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th scope="col" className="lib-sbs-corner">
                <span className="sr-only">Figure</span>
              </th>
              {rows.map((r) => (
                <th key={r.id} scope="col" className={`lib-sbs-head${r.recommended ? " is-rec" : ""}`}>
                  <div className="lib-sbs-name">
                    <DesignName r={r} small={false} />
                    <button type="button" className="lib-icon-btn small" onClick={() => onRemove(r.id)} aria-label={`Untick ${designLabel(r)}`} title="Untick">
                      <Cross size={9} />
                    </button>
                  </div>
                  <p className="lib-sbs-desc" title={r.name}>
                    {r.name}
                  </p>
                  <div className="lib-sbs-tags">
                    <ScenarioChip r={r} />
                    {r.recommended && <span className="tag tag-teal">recommended</span>}
                    <FailTag r={r} />
                    <PickTags r={r} />
                  </div>
                  <OpenLinks r={r} onOpen={onOpen} opening={opening} />
                </th>
              ))}
            </tr>
          </thead>
          {sections.map((s) => (
            <tbody key={s.title}>
              <tr className="lib-sbs-section">
                <th scope="rowgroup" colSpan={rows.length + 1}>
                  {s.title}
                </th>
              </tr>
              {s.lines.map((l) => (
                <tr key={l.key} className={l.headline ? "is-headline" : undefined}>
                  <th scope="row">
                    <span className="lib-sbs-label">
                      {l.label}
                      {l.unit && <span className="lib-th-unit"> {l.unit}</span>}
                    </span>
                    {l.hint && <span className="lib-sbs-hint">{l.hint}</span>}
                  </th>
                  {l.text.map((t, i) => (
                    <td key={rows[i].id} className={`${l.values[i] != null || l.key === "worst" ? "" : "is-none"}${l.best[i] ? " is-best" : ""}${l.key === "worst" ? " is-text" : ""}`}>
                      {t}
                      {l.best[i] && (
                        <span className="lib-best" aria-label="best of these">
                          best
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </section>
  );
});
