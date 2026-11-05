// The library table: one row per design, a page at a time. A checkbox ticks a design for the
// side by side (four at most); every figure column sorts (aria-sort says how); the recommended
// design wears a teal edge and tag. With all scenarios on screen, rows sit under a header per
// scenario and sort within it. A row's chevron opens its details: the plant in words, why it lost
// or the cap it broke, sizes, money and the worst one-unit-out case, with links into the tabs.

import { Fragment } from "react";

import { Chevron } from "../../components/Icons";
import { MenuButton, menuProps, type MenuTarget } from "../../menu";
import type { LibraryRow } from "../../workbench";
import { DesignName, FailTag, KIND_CLASS, OpenLinks, PickTags, ReliabilityBadge, ScenarioChip, VsGas, designLabel, type OpenTab } from "./bits";
import { flagWords } from "./flags";
import { KIND_WORD, fixed, fmtEur, fmtMeur, fmtT, fmtVsGas, isValid, reliabilityText, scenarioKey, signed, tidy, worstText, type ScenarioGroup, type Sort, type SortKey } from "./library";

interface Props {
  rows: LibraryRow[];
  sort: Sort;
  onSort: (key: SortKey) => void;
  selected: string[];
  onToggle: (id: string) => void;
  /** Four are ticked: the rest can't be. */
  full: boolean;
  /** All scenarios on screen: a header row per scenario. */
  grouped: boolean;
  groups: ScenarioGroup[];
  expanded: string | null;
  onExpand: (id: string | null) => void;
  onOpen: (r: LibraryRow, tab: OpenTab) => void;
  opening: string | null;
  caption: string;
  /** A row's context menu (right-click, Shift+F10, the ⋯ button). */
  rowMenu?: (r: LibraryRow) => MenuTarget;
  /** A column header's context menu: sort, and the filter that column has. */
  colMenu?: (key: SortKey | null, label: string) => MenuTarget | null;
}

interface Col {
  key: SortKey | null;
  label: string;
  unit?: string;
  num?: boolean;
  title?: string;
  className: string;
}

const COLS: Col[] = [
  { key: "rank", label: "Design", className: "c-design", title: "By name: within a search the number is its rank, A1 its best overall" },
  { key: null, label: "Scenario", className: "c-scn" },
  { key: null, label: "Picks", className: "c-picks" },
  { key: "lcoe", label: "Cost of heat and cold", unit: "€/MWh", num: true, className: "c-cost" },
  { key: "co2", label: "CO₂", unit: "t a year", num: true, className: "c-co2" },
  { key: "capex", label: "Capital", unit: "M€", num: true, className: "c-capex" },
  { key: "n1", label: "One unit out", unit: "N-1", num: true, className: "c-n1", title: "Cases where one unit out leaves a day short; N-1 ✓ when none does" },
  { key: "npv", label: "NPV vs gas", unit: "M€", num: true, className: "c-npv" },
];
const SPAN = COLS.length + 1;

function SortGlyph({ dir }: { dir: "asc" | "desc" | null }) {
  return (
    <svg className={`lib-sort-glyph${dir ? " is-on" : ""}`} width="9" height="12" viewBox="0 0 9 12" aria-hidden="true">
      <path d="M4.5 1 8 5H1z" opacity={dir === "asc" ? 1 : 0.3} />
      <path d="M4.5 11 1 7h7z" opacity={dir === "desc" ? 1 : 0.3} />
    </svg>
  );
}

/** Where a design came from: "A1 re-run under this change", "your edit of A1", "a variant of 2D-HP-AB". */
function parentWords(r: LibraryRow): string {
  const p = r.parent ?? "";
  if (r.origin === "what_if") return `${p} re-run under this scenario's change`;
  if (r.origin === "user") return `Your edit of ${p}`;
  return `A variant of ${p}`;
}

function Detail({ r, onOpen, opening }: { r: LibraryRow; onOpen: Props["onOpen"]; opening: string | null }) {
  const sizes = Object.entries(r.sizes_mw ?? {})
    .filter(([, v]) => typeof v === "number" && v > 0)
    .map(([k, v]) => `${k.replace(/_/g, " ")} ${fixed(v, 1)}`);
  const flags = (r.flags ?? []).map(flagWords);
  const m = r.money;
  const worst = worstText(r.firm);
  const why = !isValid(r) ? (r.violations?.length ? r.violations.map(tidy).join("; ") : tidy(r.reason) || "It broke a cap.") : tidy(r.reason);
  return (
    <div className="lib-detail-grid">
      <div className="lib-detail-main">
        <p className="lib-detail-name">{r.name}</p>
        {flags.length > 0 && <p className="lib-detail-small">{flags.join("; ")}</p>}
        {r.parent && <p className="lib-detail-small">{parentWords(r)}</p>}
        {why && (
          <p className={`lib-detail-why${isValid(r) ? "" : " is-bad"}`}>
            <span>{isValid(r) ? (r.recommended || r.role === "chosen" ? "Why it was picked" : "Why it was not the pick") : "The cap it broke"}</span>
            {why}
          </p>
        )}
        <OpenLinks r={r} onOpen={onOpen} opening={opening} />
      </div>
      <dl className="lib-detail-facts">
        <div>
          <dt>Cost</dt>
          <dd>
            heat and cold {fmtEur(r.lcoe)} · heat {fmtEur(r.lcoh)} · cold {fmtEur(r.lcoc)} €/MWh
          </dd>
        </div>
        <div>
          <dt>Against gas</dt>
          <dd>
            heat {fmtVsGas(r.vs_gas_pct?.heat)} · cold {fmtVsGas(r.vs_gas_pct?.cold)} · together {fmtVsGas(r.vs_gas_pct?.total)}
          </dd>
        </div>
        {m && (
          <div>
            <dt>Money</dt>
            <dd>
              NPV {signed(m.npv_meur, 1)} M€ · payback {m.payback_years == null ? "never" : `${fixed(m.payback_years, 1)} years`} discounted
              {m.irr != null ? ` · IRR ${fixed(m.irr * 100, 1)}%` : ""}
            </dd>
          </div>
        )}
        <div>
          <dt>One unit out</dt>
          <dd>
            {reliabilityText(r.firm)}
            {worst ? `; worst: ${worst}` : ""}
          </dd>
        </div>
        <div>
          <dt>Plant</dt>
          <dd>
            {r.n_doublets} doublet{r.n_doublets === 1 ? "" : "s"} · {r.wells ?? "–"} wells · {fixed(r.depth_m, 0)} m{sizes.length ? ` · ${sizes.join(" · ")} MW` : ""}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function LibraryTable({ rows, sort, onSort, selected, onToggle, full, grouped, groups, expanded, onExpand, onOpen, opening, caption, rowMenu, colMenu }: Props) {
  const sel = new Set(selected);
  const groupOf = new Map(groups.map((g) => [g.key, g]));
  return (
    <div className="lib-table-wrap">
      <table className="lib-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="c-pick">
              <span className="sr-only">Tick to compare</span>
            </th>
            {COLS.map((c) => {
              const on = c.key != null && sort.key === c.key;
              const ariaSort = c.key == null ? undefined : on ? (sort.dir === "asc" ? "ascending" : "descending") : "none";
              const inner = (
                <>
                  <span className="lib-th-label">{c.label}</span>
                  {c.unit && <span className="lib-th-unit">{c.unit}</span>}
                </>
              );
              return (
                <th key={c.label} scope="col" className={`${c.className}${c.num ? " lib-num" : ""}`} aria-sort={ariaSort} title={c.title} {...(colMenu ? menuProps(() => colMenu(c.key, c.label)) : {})}>
                  {c.key ? (
                    <button type="button" className={`lib-sort${on ? " is-on" : ""}`} onClick={() => onSort(c.key!)}>
                      <span className="lib-th-text">{inner}</span>
                      <SortGlyph dir={on ? sort.dir : null} />
                    </button>
                  ) : (
                    <span className="lib-th-text">{inner}</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const key = scenarioKey(r.scenario);
            const head = grouped && (i === 0 || scenarioKey(rows[i - 1].scenario) !== key);
            const g = groupOf.get(key);
            const on = sel.has(r.id);
            const open = expanded === r.id;
            const detailId = `lib-detail-${i}`;
            return (
              <Fragment key={r.id}>
                {head && (
                  <tr className="lib-group-row">
                    <th scope="colgroup" colSpan={SPAN}>
                      <span className={`lib-kind ${KIND_CLASS[g?.kind ?? ""] ?? ""}`}>{KIND_WORD[g?.kind ?? ""] ?? g?.kind}</span>
                      <strong>{g?.short ?? r.scenario.label}</strong>
                      <span className="lib-muted">
                        {g?.count ?? ""} design{g?.count === 1 ? "" : "s"}, sorted within this scenario only
                      </span>
                    </th>
                  </tr>
                )}
                <tr className={`lib-row${r.recommended ? " is-rec" : ""}${on ? " is-on" : ""}${isValid(r) ? "" : " is-failed"}${open ? " is-open" : ""}`} {...(rowMenu ? menuProps(() => rowMenu(r)) : {})}>
                  <td className="c-pick">
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={!on && full}
                      onChange={() => onToggle(r.id)}
                      aria-label={`Tick ${designLabel(r)} to compare`}
                      title={!on && full ? "Four designs are ticked: untick one first" : undefined}
                    />
                  </td>
                  <td className="c-design">
                    <div className="lib-design-cell">
                      <button type="button" className="lib-expand" aria-expanded={open} aria-controls={open ? detailId : undefined} onClick={() => onExpand(open ? null : r.id)} aria-label={`Details of ${designLabel(r)}`}>
                        <Chevron open={open} />
                      </button>
                      <div className="lib-design-text">
                        <span className="lib-design-line">
                          <DesignName r={r} />
                          {r.recommended && <span className="tag tag-teal lib-rec-tag">recommended</span>}
                          <FailTag r={r} />
                        </span>
                        <span className="lib-desc" title={r.name}>
                          {r.name}
                        </span>
                      </div>
                      {rowMenu && <MenuButton small target={() => rowMenu(r)} label={`More for ${designLabel(r)}`} className="lib-more" />}
                    </div>
                  </td>
                  <td className="c-scn">
                    <ScenarioChip r={r} />
                  </td>
                  <td className="c-picks">
                    <PickTags r={r} />
                  </td>
                  <td className="c-cost lib-num">
                    <strong className="lib-headline">{fmtEur(r.lcoe)}</strong>
                    <VsGas frac={r.vs_gas_pct?.total} />
                  </td>
                  <td className="c-co2 lib-num">{fmtT(r.co2_t)}</td>
                  <td className="c-capex lib-num">{fmtMeur(r.capex_meur)}</td>
                  <td className="c-n1 lib-num">
                    <ReliabilityBadge r={r} />
                  </td>
                  <td className="c-npv lib-num">{r.money ? signed(r.money.npv_meur, 1) : <span className="lib-muted">–</span>}</td>
                </tr>
                {open && (
                  <tr className="lib-detail-row" id={detailId}>
                    <td />
                    <td colSpan={SPAN - 1}>
                      <Detail r={r} onOpen={onOpen} opening={opening} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
