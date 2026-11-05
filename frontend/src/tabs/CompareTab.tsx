// The Compare tab: the chat's design library. Every design of the conversation (each search's
// candidates, every what-if and your own) in one table, one scenario at a time: a scenario is the
// assumptions a figure was computed under (the base case, "gas at 30 €/MWh", "reservoir −10 K"),
// so figures are only ranked within one. Filters on top (scenario, picks, doublets, N-1 met, met
// every cap, a search box), a chart of the scenario (cost against CO₂, area capital, fill N-1),
// the table (sortable, a page at a time), and a tray of up to four ticked designs that opens
// them side by side. A link #compare/<ids joined by "|"> (compare/link.ts) ticks designs and
// opens the side by side; the chat emits such links. What you pick is kept per conversation for
// the visit, so leaving the tab and coming back shows the same view.

import "./CompareTab.css";

import { useEffect, useMemo, useRef, useState } from "react";

import type { MenuTarget } from "../menu";
import { AskButton, TabFrame, go, useRoute, useWorkbench, type LibraryRow } from "../workbench";
import { KIND_CLASS, designLabel, type OpenTab } from "./compare/bits";
import { CompareTray } from "./compare/CompareTray";
import {
  ALL,
  KIND_WORD,
  PAGE_SIZE,
  defaultScenario,
  filterRows,
  fmtEur,
  isGasFree,
  libraryOf,
  nextSort,
  orderScenarios,
  pageCount,
  pageOf,
  passesFilters,
  resolveIds,
  scenarioKey,
  scenariosIn,
  scenariosOf,
  sortRows,
  toggleSelected,
  type ChartX,
  type LibraryFilter,
  type ScenarioGroup,
  type Sort,
  type SortKey,
} from "./compare/library";
import { LibraryChart } from "./compare/LibraryChart";
import { SweepMap } from "./compare/SweepMap";
import { LibraryFilters } from "./compare/LibraryFilters";
import { LibraryTable } from "./compare/LibraryTable";
import { compareIds } from "./compare/link";
import { scenarioMeta } from "./compare/ScenarioSelect";
import { attemptsOf } from "./compare/search";
import { SideBySide } from "./compare/SideBySide";
import { noteTray } from "./compare/tray";

interface View {
  /** A scenario group's key, ALL, or null for the default (the base case). */
  scenario: string | null;
  order: "newest" | "oldest";
  picksOnly: boolean;
  doublets: number[];
  reliableOnly: boolean;
  validOnly: boolean;
  gasFreeOnly: boolean;
  query: string;
  sort: Sort;
  page: number;
  selected: string[];
  /** The side by side is open. */
  compare: boolean;
  x: ChartX;
  /** The chart is shown (else folded to its title). */
  chart: boolean;
  expanded: string | null;
}

const FRESH: View = {
  scenario: null,
  order: "newest",
  picksOnly: false,
  doublets: [],
  reliableOnly: false,
  validOnly: false,
  gasFreeOnly: false,
  query: "",
  sort: { key: "rank", dir: "asc" },
  page: 0,
  selected: [],
  compare: false,
  x: "lcoe",
  chart: true,
  expanded: null,
};

const memory = new Map<string, View>();

const SORT_WORDS: Record<SortKey, string> = {
  rank: "name (the search's rank)",
  lcoe: "cost of heat and cold",
  co2: "CO₂",
  capex: "capital",
  n1: "cases short with one unit out",
  npv: "NPV against gas",
};

const sameIds = (a: string[], b: string[]) => a.length === b.length && a.every((x, i) => x === b[i]);

/** What the page's figures rest on: the scenario on screen, or a warning with all of them. */
function ScenarioStrip({ scenario, group, groups, rows }: { scenario: string; group: ScenarioGroup | undefined; groups: ScenarioGroup[]; rows: LibraryRow[] }) {
  if (scenario === ALL)
    return (
      <div className="lib-banner is-amber ta-rise" role="note">
        <strong>All {groups.length} scenarios.</strong> Their figures come from different assumptions (prices, reservoir, what “best” means). The table groups them by
        scenario and sorts within each; nothing is ranked across them. The chart shows one scenario at a time.
      </div>
    );
  if (!group) return null;
  const mine = rows.filter((r) => scenarioKey(r.scenario) === group.key);
  const whatIfs = mine.filter((r) => r.origin === "what_if").map((r) => (r.parent ? `${r.uid || r.code} (${r.parent.split(" · ")[0]})` : r.uid || r.code));
  const repriced = mine.some((r) => r.scenario.repriced);
  const meta = scenarioMeta(group);
  return (
    <p className="lib-strip ta-rise">
      <span className={`lib-kind ${KIND_CLASS[group.kind] ?? ""}`}>{KIND_WORD[group.kind] ?? group.kind}</span>
      <strong>{group.short}</strong>
      {meta && <span className="lib-strip-meta">{meta}</span>}
      {whatIfs.length > 0 && (
        <span className="lib-strip-meta">
          with {whatIfs.join(", ")}: {whatIfs.length === 1 ? "a design" : "designs"} re-run under this change
        </span>
      )}
      <span className="lib-strip-note">
        Every figure below uses this scenario's assumptions; picks and sorting rank within it only.
        {repriced ? " Costs are at your prices from the Economics tab; the picks are the ones the search made at its own prices." : ""}
      </span>
    </p>
  );
}

function Pager({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) {
  const count = pageCount(total);
  if (count <= 1) return null;
  return (
    <nav className="lib-pager" aria-label="Pages of designs">
      <button type="button" className="lib-page-btn ta-btn" disabled={page === 0} onClick={() => onPage(page - 1)}>
        ‹ Previous
      </button>
      <span className="lib-page-of" aria-live="polite">
        Page {page + 1} of {count}
      </span>
      <button type="button" className="lib-page-btn ta-btn" disabled={page >= count - 1} onClick={() => onPage(page + 1)}>
        Next ›
      </button>
    </nav>
  );
}

export default function CompareTab() {
  const wb = useWorkbench();
  const route = useRoute();
  const key = wb.threadId ?? "";
  const [saved, setSaved] = useState(() => ({ key, view: memory.get(key) ?? FRESH }));
  // Another conversation: its own view (adjusted while rendering, so no frame shows the old one).
  let view = saved.view;
  if (saved.key !== key) {
    view = memory.get(key) ?? FRESH;
    setSaved({ key, view });
  }
  const setView = (change: (v: View) => View) =>
    setSaved((s) => {
      const next = change(s.view);
      memory.set(s.key, next);
      noteTray(s.key, next.selected);
      return { key: s.key, view: next };
    });

  const rows = useMemo(() => libraryOf(wb.workbench), [wb.workbench]);
  const attempts = useMemo(() => attemptsOf(wb.workbench), [wb.workbench]);
  const groups = useMemo(() => scenariosOf(rows, attempts), [rows, attempts]);
  const byId = useMemo(() => new Map(rows.map((r) => [r.id, r])), [rows]);
  const scenario = view.scenario === ALL ? ALL : view.scenario && groups.some((g) => g.key === view.scenario) ? view.scenario : (defaultScenario(groups) ?? ALL);
  const group = groups.find((g) => g.key === scenario);
  const filter: LibraryFilter = { scenario, picksOnly: view.picksOnly, doublets: view.doublets, reliableOnly: view.reliableOnly, validOnly: view.validOnly, gasFreeOnly: view.gasFreeOnly, query: view.query };
  const filtered = useMemo(() => filterRows(rows, filter), [rows, scenario, view.picksOnly, view.doublets, view.reliableOnly, view.validOnly, view.gasFreeOnly, view.query]);
  const ordered = useMemo(() => orderScenarios(groups, view.order), [groups, view.order]);
  const sorted = useMemo(() => {
    const at = new Map(ordered.map((g, i) => [g.key, i]));
    return sortRows(filtered, view.sort, scenario === ALL ? (r) => at.get(scenarioKey(r.scenario)) ?? 0 : undefined);
  }, [filtered, view.sort, scenario, ordered]);
  const page = pageOf(sorted, view.page);
  const doublets = useMemo(() => [...new Set(rows.map((r) => r.n_doublets).filter((n) => n > 0))].sort(), [rows]);
  const gasFree = useMemo(() => rows.some(isGasFree), [rows]);
  // Matches of the search box in the other scenarios, so a narrow view doesn't hide them silently.
  const elsewhere = scenario !== ALL && view.query.trim() ? rows.filter((r) => scenarioKey(r.scenario) !== scenario && passesFilters(r, filter)).length : 0;

  const selectedRows = view.selected.map((id) => byId.get(id)).filter((r): r is LibraryRow => !!r);
  const selScenarios = scenariosIn(selectedRows, groups);
  const mixed = selScenarios.length > 1;
  const full = selectedRows.length >= 4;

  // ---------------------------------------------------------------- the link: #compare/<ids>
  const linkKey = `${key}|${route.tab === "compare" ? (route.design ?? "") : ""}`;
  const applied = useRef<string | null>(null);
  useEffect(() => {
    if (route.tab !== "compare" || !route.design || !rows.length || applied.current === linkKey) return;
    applied.current = linkKey;
    const ids = resolveIds(compareIds(route.design), rows);
    if (!ids.length) return;
    const scen = scenariosIn(
      ids.map((id) => byId.get(id)!),
      groups,
    );
    setView((v) => (sameIds(v.selected, ids) ? v : { ...v, selected: ids, scenario: scen.length === 1 ? scen[0].key : ALL, compare: ids.length >= 2, page: 0, expanded: null }));
  }, [linkKey, rows, byId, groups, route.tab, route.design]);

  /** Tick or untick designs, and keep the address in step so it can be copied (no new history entry). */
  const select = (ids: string[]) => {
    setView((v) => ({ ...v, selected: ids, compare: v.compare && ids.length >= 2 }));
    const design = ids.length ? ids.join("|") : null;
    applied.current = `${key}|${design ?? ""}`;
    go("compare", design, { replace: true });
  };

  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 3500);
    return () => clearTimeout(t);
  }, [notice]);
  const toggle = (id: string) => {
    const res = toggleSelected(view.selected.filter((x) => byId.has(x)), id);
    if (res.refused) setNotice("Four designs are ticked: untick one first");
    else select(res.selected);
  };

  // ---------------------------------------------------------------- the side by side
  const panel = useRef<HTMLElement>(null);
  const [scrollTo, setScrollTo] = useState(0);
  useEffect(() => {
    const el = panel.current;
    if (!scrollTo || !el) return;
    // Scroll the tab's own scroller (scrollIntoView would also move the app's frame).
    let box = el.parentElement;
    while (box && !/(auto|scroll)/.test(getComputedStyle(box).overflowY)) box = box.parentElement;
    if (box) {
      const top = el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop - 16;
      const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      box.scrollTo({ top, behavior: reduce ? "auto" : "smooth" });
    }
    el.focus({ preventScroll: true });
  }, [scrollTo]);
  const showSideBySide = view.compare && selectedRows.length >= 2;
  const openSideBySide = () => {
    setView((v) => ({ ...v, compare: true }));
    setScrollTo((n) => n + 1);
  };

  // ---------------------------------------------------------------- opening a design in the tabs
  const [opening, setOpening] = useState<string | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);
  const onOpen = async (r: LibraryRow, tab: OpenTab) => {
    setOpenError(null);
    if (r.in_tabs) return go(tab, r.id);
    setOpening(r.id);
    const res = await wb.openDesign(r.id);
    setOpening(null);
    if (res.ok) go(tab, res.data.design.id);
    else setOpenError(`Couldn't open ${designLabel(r)}: ${res.message}`);
  };

  // ---------------------------------------------------------------- changes
  const onFilter = (change: Partial<LibraryFilter>) =>
    setView((v) => ({
      ...v,
      ...("scenario" in change ? { scenario: change.scenario ?? null } : {}),
      ...("picksOnly" in change ? { picksOnly: !!change.picksOnly } : {}),
      ...("doublets" in change ? { doublets: change.doublets ?? [] } : {}),
      ...("reliableOnly" in change ? { reliableOnly: !!change.reliableOnly } : {}),
      ...("validOnly" in change ? { validOnly: !!change.validOnly } : {}),
      ...("gasFreeOnly" in change ? { gasFreeOnly: !!change.gasFreeOnly } : {}),
      ...("query" in change ? { query: change.query ?? "" } : {}),
      page: 0,
    }));
  const onReset = () => setView((v) => ({ ...v, picksOnly: false, doublets: [], reliableOnly: false, validOnly: false, gasFreeOnly: false, query: "", page: 0 }));
  const onSort = (k: SortKey) => setView((v) => ({ ...v, sort: nextSort(v.sort, k), page: 0 }));

  // ---------------------------------------------------------------- context menus
  /** A design's menu here: the tray ticks in place, and its scenario can be the only one shown. */
  const rowMenu = (r: LibraryRow): MenuTarget => {
    const own = scenarioKey(r.scenario);
    return {
      kind: "design",
      design: { id: r.id, name: r.uid || r.code, sub: r.uid ? `${r.code} · ${r.name}` : r.name },
      tray: { ticked: view.selected.includes(r.id), toggle: () => toggle(r.id), full },
      onlyScenario: scenario !== own ? () => onFilter({ scenario: own }) : undefined,
    };
  };
  /** A column's menu: sort it either way, and its filter where the toolbar has one. */
  const colMenu = (k: SortKey | null, label: string): MenuTarget | null => {
    const sort = k ? { dir: view.sort.key === k ? view.sort.dir : null, set: (dir: "asc" | "desc") => setView((v) => ({ ...v, sort: { key: k, dir }, page: 0 })) } : undefined;
    const filter =
      k === "n1"
        ? { label: "Show only designs with N-1 met", on: view.reliableOnly, toggle: () => onFilter({ reliableOnly: !view.reliableOnly }) }
        : label === "Picks"
          ? { label: "Show the picks only", on: view.picksOnly, toggle: () => onFilter({ picksOnly: !view.picksOnly }) }
          : k === "rank"
            ? { label: "Show only designs that met every cap", on: view.validOnly, toggle: () => onFilter({ validOnly: !view.validOnly }) }
            : undefined;
    return sort || filter ? { kind: "column", label, sort, filter } : null;
  };

  // ---------------------------------------------------------------- ask
  const askContext =
    selectedRows.length >= 2
      ? `the designs ticked on the Compare tab${mixed ? " (from different scenarios)" : group ? `, all in ${group.label}` : ""}: ${selectedRows.map((r) => `${designLabel(r)} ${fmtEur(r.lcoe)} €/MWh`).join(", ")}`
      : `the designs of ${group?.label ?? "this chat"} on the Compare tab: ${sorted
          .slice(0, 5)
          .map((r) => `${designLabel(r)} ${fmtEur(r.lcoe)} €/MWh`)
          .join(", ")}`;
  const askQuestion =
    selectedRows.length >= 2 ? `Which of ${selectedRows.map((r) => r.uid || r.code).join(", ")} should we build, and why?` : "which one should we build, and why?";

  const ready = !!wb.workbench && rows.length > 0;
  const label = scenario === ALL ? "all scenarios" : (group?.label ?? "");
  const total = sorted.length;

  return (
    <TabFrame
      scope="designs"
      status={ready ? { kind: "ready" } : undefined}
      className="tab-compare"
      title="Compare designs"
      lead="Every design from this chat's searches and what-ifs. Pick a scenario, tick up to four designs, and compare them side by side."
      actions={<AskButton context={askContext} question={askQuestion} label={selectedRows.length >= 2 ? "Ask which to build" : "Ask which is best"} className="cmp-ask" />}
      toolbar={
        <LibraryFilters
          filter={filter}
          onFilter={onFilter}
          groups={groups}
          total={rows.length}
          order={view.order}
          onOrder={(order) => setView((v) => ({ ...v, order }))}
          doublets={doublets}
          gasFree={gasFree}
          onReset={onReset}
        />
      }
    >
      <ScenarioStrip scenario={scenario} group={group} groups={groups} rows={rows} />
      {openError && (
        <div className="lib-banner is-red" role="alert">
          {openError}
        </div>
      )}
      {showSideBySide && (
        <SideBySide
          ref={panel}
          rows={selectedRows}
          scenarios={selScenarios}
          onRemove={(id) => select(view.selected.filter((x) => x !== id))}
          onClose={() => setView((v) => ({ ...v, compare: false }))}
          onOpen={onOpen}
          opening={opening}
          error={null}
        />
      )}
      {scenario !== ALL ? (
        <LibraryChart
          rows={filtered}
          x={view.x}
          onX={(x) => setView((v) => ({ ...v, x }))}
          selected={view.selected}
          onToggle={toggle}
          scenario={group?.label ?? ""}
          open={view.chart}
          onOpenChange={(chart) => setView((v) => ({ ...v, chart }))}
          rowMenu={rowMenu}
        />
      ) : (
        <section className="lib-card lib-chart is-off" aria-label="Chart">
          <p className="lib-note">
            The chart shows one scenario at a time, so it never puts figures from different assumptions on one scale.{" "}
            <button type="button" className="link-btn" onClick={() => onFilter({ scenario: defaultScenario(groups) ?? undefined })}>
              Show the {groups.find((g) => g.key === defaultScenario(groups))?.label ?? "first scenario"}
            </button>
          </p>
        </section>
      )}
      {scenario !== ALL && group?.attempt?.swept && wb.threadId && <SweepMap threadId={wb.threadId} search={group.attempt.id} selected={view.selected} onToggle={toggle} />}
      <section className="lib-card lib-library" aria-labelledby="lib-table-title">
        <header className="lib-card-head">
          <div>
            <h2 id="lib-table-title">Designs</h2>
            <p className="lib-card-sub">
              {total ? `${page.from}–${page.to} of ${total}` : "None"} in {label}
              {total > 1 ? ` · sorted by ${SORT_WORDS[view.sort.key]}${scenario === ALL ? " within each scenario" : ""}` : ""}
              {selectedRows.length === 0 && total > 0 ? " · tick up to four to compare" : ""}
            </p>
          </div>
          {elsewhere > 0 && (
            <button type="button" className="link-btn" onClick={() => onFilter({ scenario: ALL })}>
              {elsewhere} more match{elsewhere === 1 ? "" : "es"} in other scenarios
            </button>
          )}
        </header>
        {total ? (
          <LibraryTable
            rows={page.rows}
            sort={view.sort}
            onSort={onSort}
            selected={view.selected}
            onToggle={toggle}
            full={full}
            grouped={scenario === ALL}
            groups={groups}
            expanded={view.expanded}
            onExpand={(id) => setView((v) => ({ ...v, expanded: id }))}
            onOpen={onOpen}
            opening={opening}
            caption={`Designs in ${label}, sorted by ${SORT_WORDS[view.sort.key]}, ${view.sort.dir === "asc" ? "ascending" : "descending"}. Page ${page.page + 1} of ${pageCount(total, PAGE_SIZE)}.`}
            rowMenu={rowMenu}
            colMenu={colMenu}
          />
        ) : (
          <div className="lib-empty">
            <p>No design in {label} matches these filters.</p>
            <button type="button" className="btn btn-soft ta-btn" onClick={onReset}>
              Reset filters
            </button>
          </div>
        )}
        <Pager page={page.page} total={total} onPage={(p) => setView((v) => ({ ...v, page: p }))} />
      </section>
      <CompareTray
        rows={selectedRows}
        mixed={mixed}
        notice={notice}
        open={showSideBySide}
        onRemove={(id) => select(view.selected.filter((x) => x !== id))}
        onClear={() => select([])}
        onCompare={openSideBySide}
      />
    </TabFrame>
  );
}
