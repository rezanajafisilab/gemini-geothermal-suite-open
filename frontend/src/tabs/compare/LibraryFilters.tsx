// The library's filters, on one row above the table: the scenario (one control for any number of
// searches), all designs or only the searches' picks, doublets, N-1 met only, met every cap
// only, and a search box. "Reset" clears all but the scenario.

import { Tick } from "../../components/Icons";
import { filtersActive, type LibraryFilter, type ScenarioGroup } from "./library";
import { ScenarioSelect } from "./ScenarioSelect";

interface Props {
  filter: LibraryFilter;
  onFilter: (change: Partial<LibraryFilter>) => void;
  groups: ScenarioGroup[];
  total: number;
  order: "newest" | "oldest";
  onOrder: (o: "newest" | "oldest") => void;
  /** Doublet counts the library has. */
  doublets: number[];
  /** The library has designs that buy no gas (the gas-free filter is offered). */
  gasFree?: boolean;
  onReset: () => void;
}

function Check({ on, label, title, onClick }: { on: boolean; label: string; title: string; onClick: () => void }) {
  return (
    <button type="button" className={`lib-check ta-btn${on ? " is-on" : ""}`} aria-pressed={on} title={title} onClick={onClick}>
      <span className="lib-check-box" aria-hidden="true">
        {on && <Tick size={10} color="#fff" />}
      </span>
      {label}
    </button>
  );
}

export function LibraryFilters({ filter, onFilter, groups, total, order, onOrder, doublets, gasFree = false, onReset }: Props) {
  const toggleDoublet = (n: number) => onFilter({ doublets: filter.doublets.includes(n) ? filter.doublets.filter((x) => x !== n) : [...filter.doublets, n].sort() });
  return (
    <div className="lib-filters ta-rise" role="search" aria-label="Filter the designs">
      <ScenarioSelect groups={groups} value={filter.scenario} total={total} order={order} onOrder={onOrder} onChange={(scenario) => onFilter({ scenario })} />
      <div className="lib-seg" role="radiogroup" aria-label="Which designs">
        <button type="button" role="radio" aria-checked={!filter.picksOnly} className={!filter.picksOnly ? "is-on" : ""} onClick={() => onFilter({ picksOnly: false })}>
          All designs
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={filter.picksOnly}
          className={filter.picksOnly ? "is-on" : ""}
          title="Only each search's picks (best overall, cheapest, lowest CO₂, cheapest reliable, greenest reliable, gas-free) and the recommended design"
          onClick={() => onFilter({ picksOnly: true })}
        >
          Picks only
        </button>
      </div>
      {doublets.length > 1 && (
        <div className="lib-doublets" role="group" aria-label="Doublets">
          <span className="lib-filter-cap" aria-hidden="true">
            Doublets
          </span>
          {doublets.map((n) => (
            <button
              key={n}
              type="button"
              className={`lib-pill ta-btn${filter.doublets.includes(n) ? " is-on" : ""}`}
              aria-pressed={filter.doublets.includes(n)}
              aria-label={`${n} doublet${n === 1 ? "" : "s"}`}
              onClick={() => toggleDoublet(n)}
            >
              {n}
            </button>
          ))}
        </div>
      )}
      <Check on={filter.reliableOnly} label="N-1 met" title="Only designs where any one unit can be out and every day is still met" onClick={() => onFilter({ reliableOnly: !filter.reliableOnly })} />
      <Check on={filter.validOnly} label="Met every cap" title="Hide designs that broke a cap of the challenge" onClick={() => onFilter({ validOnly: !filter.validOnly })} />
      {gasFree && (
        <Check
          on={!!filter.gasFreeOnly}
          label="Gas-free"
          title="Only designs that buy no gas: an electric boiler for the peaks, the brine's own gas burnt in a small boiler or sold to the gas grid"
          onClick={() => onFilter({ gasFreeOnly: !filter.gasFreeOnly })}
        />
      )}
      {filtersActive(filter) && (
        <button type="button" className="link-btn lib-reset" onClick={onReset} title="Clear the filters; the scenario stays" aria-label="Reset the filters">
          Reset
        </button>
      )}
      <label className="lib-search">
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="7" cy="7" r="4.8" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="m10.6 10.6 3.4 3.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <span className="sr-only">Search designs</span>
        <input type="search" placeholder="Search A1, 2D-HP, boiler…" value={filter.query} onChange={(e) => onFilter({ query: e.target.value })} />
      </label>
    </div>
  );
}
