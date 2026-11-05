// The Compare tab's design library: every design of the chat (each search's candidates, every
// what-if and your own) as one list, grouped by scenario (the assumptions a figure was computed
// under), filtered, sorted and ticked for a side-by-side comparison. Pure functions, tested in
// library.test.ts; the components only draw what these return.
//
// The one rule: figures from different scenarios are never ranked against each other. With one
// scenario on screen, sorting ranks; with all of them, rows are grouped by scenario and sorted
// within each group, and the side by side marks no "best" when its designs' scenarios differ.

import type { Attempt, Candidate, Design, LibraryFirm, LibraryRow, LibraryScenario, Workbench } from "../../workbench";
import { codeParts, flagWords } from "./flags";

// ------------------------------------------------------------------ numbers

const MINUS = "−";

export const finite = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

/** A fixed number of decimals, thousands separated, with a real minus: "69.8", "14,334", "−3.1". */
export function fixed(v: number | null | undefined, digits: number): string {
  if (!finite(v)) return "–";
  const s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return Number(s.replace(/,/g, "")) === 0 ? s : `${v < 0 ? MINUS : ""}${s}`;
}

/** With its sign: "+29.4", "−3.1", "0.0". */
export function signed(v: number | null | undefined, digits: number): string {
  if (!finite(v)) return "–";
  const s = fixed(Math.abs(v), digits);
  return Number(s.replace(/,/g, "")) === 0 ? s : `${v < 0 ? MINUS : "+"}${s}`;
}

/** €/MWh: one decimal. */
export const fmtEur = (v: number | null | undefined) => fixed(v, 1);
/** Tonnes: whole numbers. */
export const fmtT = (v: number | null | undefined) => fixed(v, 0);
/** M€: one decimal. */
export const fmtMeur = (v: number | null | undefined) => fixed(v, 1);

/** A signed fraction against gas as a percentage: −0.1733 → "−17.3%" (null: "–"). */
export function fmtVsGas(frac: number | null | undefined): string {
  return finite(frac) ? `${signed(frac * 100, 1)}%` : "–";
}

/** The server's words as the page shows them: CO₂, "→", real minus signs, "€" for "EUR". */
export function tidy(s: string | null | undefined): string {
  return (s ?? "")
    .replace(/\bCO2\b/g, "CO₂")
    .replace(/\bco2\b/g, "CO₂")
    .replace(/\s*->\s*/g, " → ")
    .replace(/(^|[\s(:])-(?=\d)/g, `$1${MINUS}`)
    .replace(/\bEUR\b/g, "€");
}

// ------------------------------------------------------------------ picks and reliability

export const PICKS = ["best", "cost", "co2", "reliable", "green_reliable", "gas_free"] as const;

export const PICK_LABEL: Record<string, string> = {
  best: "best overall",
  cost: "cheapest",
  co2: "lowest CO₂",
  reliable: "cheapest reliable",
  green_reliable: "greenest reliable",
  gas_free: "gas-free",
};

/** How each pick is chosen within its search (engine.py OBJECTIVE_WORDS), for the tags' titles and the legend. */
export const PICK_RULE: Record<string, string> = {
  best: "a reliable plan, cheapest with CO₂ at the long-term price of 137 €/t",
  cost: "the lowest cost of heat and cold",
  co2: "the least CO₂ (the cheapest within 2% of the lowest)",
  reliable: "the cheapest plan that still meets every day with any one unit out (N-1)",
  green_reliable: "of the plans that meet every day with any one unit out, the least CO₂ (the cheapest within 2%)",
  gas_free: "the cheapest design that buys no gas (an electric boiler for the peaks), a reliable plan when one holds",
};

/** A row's variant flags: its own, else its code's. */
export const flagsOf = (r: Pick<LibraryRow, "code" | "flags">) => (r.flags?.length ? r.flags : codeParts(r.code).flags);

/** Buys no gas: the brine's own gas in a small boiler, or sold to the gas grid, and an electric boiler (flag EB). */
export const isGasFree = (r: Pick<LibraryRow, "code" | "flags">) => flagsOf(r).includes("EB");

/** A row's picks in the fixed order, unknown ones left out. */
export const picksOf = (r: Pick<LibraryRow, "picks">) => PICKS.filter((p) => r.picks?.includes(p));

/** Met every cap (not a failed candidate, no broken cap). */
export const isValid = (r: Pick<LibraryRow, "role" | "violations">) => r.role !== "failed" && !r.violations?.length;

/**
 * Any one unit can be out and every day is still met: from the one-unit-out cases when the
 * server ran them (a what-if can break a plan sized for it), else from how it was sized.
 */
export function n1Met(r: Pick<LibraryRow, "firm" | "reliable">): boolean {
  return r.firm ? r.firm.short === 0 : !!r.reliable;
}

/** "N-1 met", "1 of 5 cases short", or "–" with no cases. */
export function reliabilityText(firm: LibraryFirm | null | undefined): string {
  if (!firm || !firm.cases) return "–";
  return firm.short === 0 ? "N-1 met" : `${firm.short} of ${firm.cases} case${firm.cases === 1 ? "" : "s"} short`;
}

/** The worst one-unit-out case in words: "the boiler out leaves heat 20.8 MW short on 28 Jan". */
export function worstText(firm: LibraryFirm | null | undefined): string | null {
  const w = firm?.worst;
  if (!w) return null;
  const side = w.side === "cool" ? "cold" : w.side;
  return `${w.unit} out leaves ${side} ${fixed(w.mw, 1)} MW short${w.day ? ` on ${w.day}` : ""}`;
}

// ------------------------------------------------------------------ scenarios

export interface ScenarioGroup {
  /** What the filter keeps: what-ifs with the same change are one scenario, whichever search made them. */
  key: string;
  /** "Base case", "What-if: gas price 30 EUR/MWh". */
  label: string;
  /** For chips: "Base case", "gas price 30 EUR/MWh". */
  short: string;
  kind: string;
  /** The (newest) search in it, 0 for none. */
  n: number;
  /** The server's scenario ids it gathers. */
  ids: string[];
  count: number;
  /** Older first; standalone what-ifs and your designs after the searches. */
  order: number;
  /** The search that ran under it, for its time and the request. */
  attempt: Attempt | null;
  /** It holds the chat's current design. */
  recommended: boolean;
}

const norm = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();

/** The group a scenario falls in: the server's id (a what-if re-run carries the id of the search run under the same change). */
export function scenarioKey(s: LibraryScenario): string {
  return s.id;
}

/** A scenario's label for chips: the base case as is, a what-if by its change. */
export function scenarioShort(s: Pick<LibraryScenario, "kind" | "label">): string {
  if (s.kind === "what_if") return tidy(s.label.replace(/^what-if:\s*/i, ""));
  return tidy(s.label);
}

export const KIND_WORD: Record<string, string> = { base: "Base", what_if: "What-if", search: "Search", user: "Yours" };

/** The scenarios of the rows, oldest first (by search), standalone what-ifs then your designs last. */
export function scenariosOf(rows: LibraryRow[], attempts: Attempt[] = []): ScenarioGroup[] {
  const byKey = new Map<string, ScenarioGroup & { first: number }>();
  rows.forEach((r, i) => {
    const key = scenarioKey(r.scenario);
    let g = byKey.get(key);
    if (!g) {
      g = {
        key,
        label: tidy(r.scenario.label),
        short: scenarioShort(r.scenario),
        kind: r.scenario.kind,
        n: 0,
        ids: [],
        count: 0,
        order: 0,
        attempt: null,
        recommended: false,
        first: i,
      };
      byKey.set(key, g);
    }
    g.count++;
    if (!g.ids.includes(r.scenario.id)) g.ids.push(r.scenario.id);
    if (r.scenario.n > g.n) {
      g.n = r.scenario.n;
      g.attempt = attempts.find((a) => a.id === r.scenario.id) ?? g.attempt;
    }
    if (r.recommended) g.recommended = true;
  });
  const groups = [...byKey.values()];
  const maxN = Math.max(0, ...groups.map((g) => g.n));
  for (const g of groups) g.order = g.kind === "user" ? Number.MAX_SAFE_INTEGER - (rows.length - g.first) : g.n > 0 ? g.n : maxN + 1 + g.first;
  return groups.sort((a, b) => a.order - b.order).map(({ first: _first, ...g }) => g);
}

/** The groups newest first or oldest first; your designs stay last either way. */
export function orderScenarios(groups: ScenarioGroup[], order: "newest" | "oldest"): ScenarioGroup[] {
  const user = groups.filter((g) => g.kind === "user");
  const rest = groups.filter((g) => g.kind !== "user").sort((a, b) => (order === "newest" ? b.order - a.order : a.order - b.order));
  return [...rest, ...user];
}

/** The scenario shown first: the base case, else the one with the chat's design, else the newest. */
export function defaultScenario(groups: ScenarioGroup[]): string | null {
  return (groups.find((g) => g.kind === "base") ?? groups.find((g) => g.recommended) ?? orderScenarios(groups, "newest")[0])?.key ?? null;
}

// ------------------------------------------------------------------ filter

export interface LibraryFilter {
  /** A scenario group's key, or "all". */
  scenario: string;
  picksOnly: boolean;
  /** Empty: any number. */
  doublets: number[];
  reliableOnly: boolean;
  validOnly: boolean;
  /** Only the designs that buy no gas (unset: all). */
  gasFreeOnly?: boolean;
  query: string;
}

export const ALL = "all";

/** Lower-case, CO₂ as co2, "·" as a space: what the search box compares. */
const fold = (s: string) => s.toLowerCase().replace(/₂/g, "2").replace(/[·|]/g, " ").replace(/−/g, "-");

/** Every word of the query is somewhere in the design's name, code, scenario, picks or why it lost. */
export function matchesQuery(r: LibraryRow, query: string): boolean {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const hay = fold(
    [
      r.id,
      r.uid,
      r.code,
      r.name,
      r.scenario.label,
      ...picksOf(r).map((p) => PICK_LABEL[p]),
      ...flagsOf(r).map(flagWords),
      isGasFree(r) ? "gas-free no gas" : "",
      r.recommended ? "recommended" : "",
      isValid(r) ? "" : "broke a cap failed",
      r.reason ?? "",
    ].join(" "),
  );
  return words.every((w) => hay.includes(w));
}

/** Whether a row passes every filter but the scenario. */
export function passesFilters(r: LibraryRow, f: Omit<LibraryFilter, "scenario">): boolean {
  if (f.picksOnly && !picksOf(r).length && !r.recommended) return false;
  if (f.doublets.length && !f.doublets.includes(r.n_doublets)) return false;
  if (f.reliableOnly && !n1Met(r)) return false;
  if (f.validOnly && !isValid(r)) return false;
  if (f.gasFreeOnly && !isGasFree(r)) return false;
  return matchesQuery(r, f.query);
}

export function filterRows(rows: LibraryRow[], f: LibraryFilter): LibraryRow[] {
  return rows.filter((r) => (f.scenario === ALL || scenarioKey(r.scenario) === f.scenario) && passesFilters(r, f));
}

/** Filters narrower than the defaults (the scenario aside). */
export const filtersActive = (f: LibraryFilter) => f.picksOnly || f.doublets.length > 0 || f.reliableOnly || f.validOnly || !!f.gasFreeOnly || f.query.trim() !== "";

// ------------------------------------------------------------------ sort

export type SortKey = "rank" | "lcoe" | "co2" | "capex" | "n1" | "npv";
export type SortDir = "asc" | "desc";
export interface Sort {
  key: SortKey;
  dir: SortDir;
}

/** The direction a column sorts in first: the better end on top. */
export const FIRST_DIR: Record<SortKey, SortDir> = { rank: "asc", lcoe: "asc", co2: "asc", capex: "asc", n1: "asc", npv: "desc" };

/** A name's letter and number: "A11" → ["A", 11], so A2 comes before A11. */
function uidParts(uid: string): [string, number, string] {
  const m = /^([A-Za-z]*)(\d*)(.*)$/.exec(uid ?? "") ?? ["", "", "", ""];
  return [m[1].toUpperCase(), m[2] ? Number(m[2]) : Number.POSITIVE_INFINITY, m[3]];
}

/** A1, A2 … A11, B1 …: within a search the number is its rank (A1 its best overall). */
export function compareUid(a: string, b: string): number {
  const [la, na, ra] = uidParts(a);
  const [lb, nb, rb] = uidParts(b);
  return la.localeCompare(lb) || (na === nb ? 0 : na < nb ? -1 : 1) || ra.localeCompare(rb);
}

export function sortValue(r: LibraryRow, key: SortKey): number | null {
  switch (key) {
    case "rank":
      return null;
    case "lcoe":
      return finite(r.lcoe) ? r.lcoe : null;
    case "co2":
      return finite(r.co2_t) ? r.co2_t : null;
    case "capex":
      return finite(r.capex_meur) ? r.capex_meur : null;
    case "n1":
      return r.firm && r.firm.cases ? r.firm.short : null;
    case "npv":
      return finite(r.money?.npv_meur) ? r.money!.npv_meur : null;
  }
}

/**
 * The rows in order. Missing values go last whichever way; ties fall back to the name. With
 * `group` (all scenarios on screen), rows stay within their scenario, in the given order of the
 * groups, and sort inside it: a sort never ranks across scenarios.
 */
export function sortRows(rows: LibraryRow[], sort: Sort, group?: (r: LibraryRow) => number): LibraryRow[] {
  const sign = sort.dir === "asc" ? 1 : -1;
  const byName = (a: LibraryRow, b: LibraryRow) => compareUid(a.uid || a.id, b.uid || b.id) || a.id.localeCompare(b.id);
  return [...rows].sort((a, b) => {
    if (group) {
      const g = group(a) - group(b);
      if (g) return g;
    }
    if (sort.key === "rank") return sign * byName(a, b);
    const va = sortValue(a, sort.key);
    const vb = sortValue(b, sort.key);
    if (va == null || vb == null) return va == null && vb == null ? byName(a, b) : va == null ? 1 : -1;
    // N-1: fewer cases short first, then the cheaper.
    const tie = sort.key === "n1" ? (finite(a.lcoe) && finite(b.lcoe) ? a.lcoe - b.lcoe : 0) : 0;
    return sign * (va - vb) || tie || byName(a, b);
  });
}

/** Click a column: the better end first; again: the other way. */
export function nextSort(cur: Sort, key: SortKey): Sort {
  if (cur.key !== key) return { key, dir: FIRST_DIR[key] };
  return { key, dir: cur.dir === "asc" ? "desc" : "asc" };
}

// ------------------------------------------------------------------ pages

export const PAGE_SIZE = 25;

export function pageCount(total: number, size = PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / size));
}

/** The rows of a page (clamped to the last page). */
export function pageOf<T>(rows: T[], page: number, size = PAGE_SIZE): { rows: T[]; page: number; from: number; to: number } {
  const p = Math.min(Math.max(0, page), pageCount(rows.length, size) - 1);
  const from = p * size;
  const slice = rows.slice(from, from + size);
  return { rows: slice, page: p, from: rows.length ? from + 1 : 0, to: from + slice.length };
}

// ------------------------------------------------------------------ selection

export const MAX_SELECTED = 4;

/** Tick or untick a design; a fifth is refused (the list stays as it was). */
export function toggleSelected(selected: string[], id: string, max = MAX_SELECTED): { selected: string[]; refused: boolean } {
  if (selected.includes(id)) return { selected: selected.filter((x) => x !== id), refused: false };
  if (selected.length >= max) return { selected, refused: true };
  return { selected: [...selected, id], refused: false };
}

/**
 * The library's designs a link names, in its order, at most four: by id ("A1 · 1D-HP-EC-N1"),
 * else by name ("A1"), else by code (the chat's design first). Unknown names are left out.
 */
export function resolveIds(wanted: string[], rows: LibraryRow[], max = MAX_SELECTED): string[] {
  const out: string[] = [];
  for (const w of wanted) {
    const want = norm(w);
    const hit =
      rows.find((r) => norm(r.id) === want) ??
      rows.find((r) => norm(r.uid) === want) ??
      [...rows.filter((r) => norm(r.code) === want)].sort((a, b) => Number(b.recommended) - Number(a.recommended) || Number(b.in_tabs) - Number(a.in_tabs))[0];
    if (hit && !out.includes(hit.id)) out.push(hit.id);
    if (out.length >= max) break;
  }
  return out;
}

/** The scenario groups of some rows (in the groups' order). */
export function scenariosIn(rows: LibraryRow[], groups: ScenarioGroup[]): ScenarioGroup[] {
  const keys = new Set(rows.map((r) => scenarioKey(r.scenario)));
  return groups.filter((g) => keys.has(g.key));
}

// ------------------------------------------------------------------ side by side

export type Better = "lower" | "higher" | null;

export interface CompareLine {
  key: string;
  label: string;
  unit: string;
  better: Better;
  /** One per design, in the selection's order (null: not known). */
  values: (number | null)[];
  text: string[];
  /** The best of the line (ties all marked); none when it is not ranked. */
  best: boolean[];
  /** The headline (cost of heat and cold). */
  headline?: boolean;
  /** Small print under the label. */
  hint?: string;
  /** The decimals shown: values equal as shown tie for best. */
  digits: number;
}

export interface CompareSection {
  title: string;
  lines: CompareLine[];
}

const pct = (v: number | null | undefined) => (finite(v) ? v * 100 : null);

function line(
  rows: LibraryRow[],
  key: string,
  label: string,
  unit: string,
  better: Better,
  get: (r: LibraryRow) => number | null | undefined,
  fmt: (v: number | null, r: LibraryRow) => string,
  extra: Partial<CompareLine> = {},
): CompareLine {
  const values = rows.map((r) => {
    const v = get(r);
    return finite(v) ? v : null;
  });
  return { key, label, unit, better, values, text: values.map((v, i) => fmt(v, rows[i])), best: rows.map(() => false), digits: 1, ...extra };
}

/**
 * Marks the best of each ranked line: the lowest or highest shown value, ties included, when at
 * least two designs have one and they differ as shown.
 */
export function markBest(l: CompareLine): CompareLine {
  if (!l.better) return l;
  const scale = 10 ** l.digits;
  const shown = l.values.map((v) => (v == null ? null : Math.round(v * scale) / scale));
  const have = shown.filter((v): v is number => v != null);
  if (have.length < 2 || have.every((v) => v === have[0])) return l;
  const target = l.better === "lower" ? Math.min(...have) : Math.max(...have);
  return { ...l, best: shown.map((v) => v === target) };
}

const sizeLine = (rows: LibraryRow[], key: string, label: string) =>
  line(rows, `size_${key}`, label, "MW", null, (r) => r.sizes_mw?.[key], (v) => (v == null || v === 0 ? "–" : fixed(v, 1)));

/**
 * Every figure of the designs side by side, in sections. `rank`: mark the best of each line
 * (only when every design is from the same scenario).
 */
export function compareSections(rows: LibraryRow[], rank: boolean): CompareSection[] {
  const money = (get: (m: NonNullable<LibraryRow["money"]>) => number | null | undefined) => (r: LibraryRow) => (r.money ? get(r.money) : null);
  const sections: CompareSection[] = [
    {
      title: "Cost",
      lines: [
        line(rows, "lcoe", "Cost of heat and cold", "€/MWh", "lower", (r) => r.lcoe, (v) => fmtEur(v), { headline: true }),
        line(rows, "lcoh", "Cost of heat", "€/MWh", "lower", (r) => r.lcoh, (v) => fmtEur(v)),
        line(rows, "lcoc", "Cost of cold", "€/MWh", "lower", (r) => r.lcoc, (v) => fmtEur(v)),
        line(rows, "vs_gas", "Against gas, heat and cold", "%", "lower", (r) => pct(r.vs_gas_pct?.total), (v) => (v == null ? "–" : `${signed(v, 1)}%`), {
          hint: "against gas boilers and electric chillers of the same scenario",
        }),
      ],
    },
    {
      title: "CO₂",
      lines: [
        line(rows, "co2", "CO₂", "t a year", "lower", (r) => r.co2_t, (v) => fmtT(v), { digits: 0 }),
        line(rows, "co2_saving", "CO₂ saving against gas", "%", "higher", (r) => r.co2_saving_pct, (v) => (v == null ? "–" : `${fixed(v, 1)}%`)),
      ],
    },
    {
      title: "Money against gas",
      lines: [
        line(rows, "capex", "Capital", "M€", "lower", (r) => r.capex_meur, (v) => fmtMeur(v)),
        line(rows, "savings", "Savings a year", "M€", "higher", money((m) => m.savings_meur_per_year), (v) => (v == null ? "–" : fixed(v, 1))),
        line(rows, "npv", "NPV against gas", "M€", "higher", money((m) => m.npv_meur), (v) => (v == null ? "–" : signed(v, 1))),
        line(rows, "payback", "Payback, discounted", "years", "lower", money((m) => m.payback_years), (v, r) => (v == null ? (r.money ? "never" : "–") : fixed(v, 1))),
        line(rows, "irr", "IRR", "%", "higher", money((m) => pct(m.irr)), (v) => (v == null ? "–" : `${fixed(v, 1)}%`)),
      ],
    },
    {
      title: "Reliability",
      lines: [
        line(rows, "n1", "One unit out (N-1)", "", "lower", (r) => (r.firm && r.firm.cases ? r.firm.short : null), (_v, r) => reliabilityText(r.firm), {
          hint: "cases that leave a day short; 0 is N-1 met",
          digits: 0,
        }),
        {
          key: "worst",
          label: "Worst case",
          unit: "",
          better: null,
          values: rows.map(() => null),
          text: rows.map((r) => worstText(r.firm) ?? (r.firm ? "none" : "–")),
          best: rows.map(() => false),
          digits: 0,
        },
        line(rows, "spare_heat", "Spare heat on the peak day", "MW", "higher", (r) => r.firm?.spare_heat_mw, (v) => (v == null ? "–" : fixed(v, 1))),
        line(rows, "spare_cool", "Spare cold on the peak day", "MW", "higher", (r) => r.firm?.spare_cool_mw, (v) => (v == null ? "–" : fixed(v, 1))),
      ],
    },
    {
      title: "Plant",
      lines: [
        line(rows, "doublets", "Doublets", "", null, (r) => r.n_doublets, (v) => (v == null ? "–" : String(v)), { digits: 0 }),
        line(rows, "wells", "Wells", "", null, (r) => r.wells, (v) => (v == null ? "–" : String(v)), { digits: 0 }),
        line(rows, "depth", "Depth", "m", null, (r) => r.depth_m, (v) => (v == null ? "–" : fixed(v, 0)), { digits: 0 }),
        sizeLine(rows, "heat_exchanger", "Heat exchanger"),
        sizeLine(rows, "heat_pump", "Heat pump"),
        sizeLine(rows, "boiler", "Gas boiler"),
        sizeLine(rows, "electric_boiler", "Electric boiler"),
        sizeLine(rows, "absorption", "Absorption chiller"),
        sizeLine(rows, "chillers", "Electric chillers"),
      ],
    },
  ];
  return sections.map((s) => ({ ...s, lines: rank ? s.lines.map(markBest) : s.lines }));
}

// ------------------------------------------------------------------ chart

export type ChartX = "lcoe" | "lcoh" | "lcoc";

export const CHART_X: Record<ChartX, { label: string; title: string; vs: "total" | "heat" | "cold" }> = {
  lcoe: { label: "Heat and cold", title: "Cost of heat and cold, €/MWh", vs: "total" },
  lcoh: { label: "Heat", title: "Cost of heat, €/MWh", vs: "heat" },
  lcoc: { label: "Cold", title: "Cost of cold, €/MWh", vs: "cold" },
};

/** The gas plant's cost on the chart's axis, worked back from the rows' "against gas" (the median, so one odd row can't move it). */
export function gasCost(rows: LibraryRow[], x: ChartX): number | null {
  const vs = CHART_X[x].vs;
  const est = rows
    .map((r) => {
      const v = r[x];
      const f = r.vs_gas_pct?.[vs];
      return finite(v) && finite(f) && f > -1 ? v / (1 + f) : null;
    })
    .filter((v): v is number => v != null)
    .sort((a, b) => a - b);
  if (!est.length) return null;
  const mid = Math.floor(est.length / 2);
  return est.length % 2 ? est[mid] : (est[mid - 1] + est[mid]) / 2;
}

/** The ring of a design short with one unit out: thicker and darker with more cases short. */
export function ringOf(short: number): { width: number; color: string } {
  const k = Math.min(Math.max(short, 1), 8);
  const t = (k - 1) / 7;
  const mix = (a: number, b: number) => Math.round(a + (b - a) * t);
  // From a light teal (#5fb3bf) to the app's teal (#0a6f7c).
  return { width: 1.4 + 0.3 * (k - 1), color: `rgb(${mix(95, 10)}, ${mix(179, 111)}, ${mix(191, 124)})` };
}

// ------------------------------------------------------------------ the rows from an older server

const SCENARIO_OF_ATTEMPT = (a: Attempt): LibraryScenario => {
  const label = a.label ?? "";
  if (/^what-if: /i.test(label)) return { id: a.id, n: a.n, kind: "what_if", label: `What-if: ${label.slice(9).split(" · ")[0]}` };
  return { id: a.id, n: a.n, kind: a.n === 1 ? "base" : "search", label: a.n === 1 ? "Base case" : `Search ${a.n}: ${label}` };
};

const vsGas = (v: number | null | undefined, ref: number | null | undefined) => (finite(v) && finite(ref) && ref > 0 ? v / ref - 1 : null);

type CandidateExtra = Candidate & { id?: string; uid?: string; picks?: string[]; reliable?: boolean };

/**
 * The library: the server's, else made from the searches and designs an older server (or the
 * fixtures) sends, with what can be known: no one-unit-out cases, money only for designs.
 */
export function libraryOf(wb: Pick<Workbench, "library" | "attempts" | "designs"> | null | undefined): LibraryRow[] {
  if (!wb) return [];
  if (wb.library) return wb.library;
  const rows: LibraryRow[] = [];
  const seen = new Set<string>();
  const designIds = new Set(wb.designs.map((d) => d.id));
  const attempts = [...(wb.attempts ?? [])].sort((a, b) => a.n - b.n);
  for (const a of attempts) {
    const scenario = SCENARIO_OF_ATTEMPT(a);
    const ref = a.reference;
    for (const c of a.candidates as CandidateExtra[]) {
      if (c.role === "reference" || c.role === "same") continue;
      const id = c.id ?? (c.role === "chosen" && designIds.has(c.code) ? c.code : `${c.code} (${a.id})`);
      if (seen.has(id)) continue;
      seen.add(id);
      rows.push({
        id,
        uid: c.uid ?? "",
        code: c.code,
        name: c.name,
        scenario,
        origin: "agent",
        role: c.role,
        picks: c.picks ?? [],
        recommended: wb.designs.some((d) => d.id === id && d.chosen),
        in_tabs: designIds.has(id),
        reliable: !!c.reliable,
        n_doublets: c.n_doublets,
        depth_m: c.depth_m,
        flags: c.flags,
        topup: c.topup,
        cooling: c.cooling,
        sizes_mw: c.sizes_mw,
        lcoe: c.lcoe,
        lcoh: c.lcoh,
        lcoc: c.lcoc,
        co2_t: c.co2_t,
        co2_saving_pct: c.co2_saving_pct,
        capex_meur: c.capex_meur,
        wells: c.wells,
        trains: c.trains,
        verified: c.verified,
        violations: c.violations ?? [],
        reason: c.reason,
        vs_gas_pct: ref ? { heat: vsGas(c.lcoh, ref.lcoh), cold: vsGas(c.lcoc, ref.lcoc), total: vsGas(c.lcoe, ref.lcoe) } : null,
        money: null,
        firm: null,
      });
    }
  }
  for (const d of wb.designs) {
    if (seen.has(d.id)) continue;
    seen.add(d.id);
    rows.push(designRow(d));
  }
  return rows;
}

function designRow(d: Design): LibraryRow {
  const e = d.economics;
  const v = e?.versus_reference;
  const what = d.change_label || (d.reservoir_delta_c ? `reservoir ${signed(d.reservoir_delta_c, 0)} K` : "what-if");
  const scenario: LibraryScenario =
    d.origin === "user" ? { id: "user", n: 0, kind: "user", label: "Your designs" } : d.origin === "what_if" ? { id: `w:${what}`, n: 0, kind: "what_if", label: `What-if: ${what}` } : { id: "S1", n: 1, kind: "base", label: "Base case" };
  return {
    id: d.id,
    uid: d.uid ?? "",
    code: d.code,
    name: d.name,
    scenario,
    origin: d.origin,
    role: d.role ?? (d.chosen ? "chosen" : d.origin),
    picks: d.picks ?? [],
    recommended: d.chosen,
    in_tabs: true,
    reliable: !!d.reliable,
    n_doublets: d.plant?.n_doublets ?? 0,
    depth_m: d.plant?.depth_m ?? 0,
    flags: d.flags,
    topup: d.plant?.topup ?? null,
    cooling: d.plant?.cooling ?? null,
    sizes_mw: { ...(d.plant?.sizes_mw ?? {}) },
    lcoe: e?.lcoe ?? null,
    lcoh: e?.lcoh ?? null,
    lcoc: e?.lcoc ?? null,
    co2_t: e?.co2_t_per_year ?? null,
    co2_saving_pct: e?.co2_saving_pct ?? null,
    capex_meur: e?.capex_meur ?? null,
    wells: d.plant?.wells ?? null,
    trains: d.plant?.trains ?? null,
    verified: d.verified,
    violations: d.year?.violations ?? [],
    vs_gas_pct: null,
    money: v ? { extra_capex_meur: v.extra_capex_meur, savings_meur_per_year: v.savings_meur_per_year, payback_years: v.payback_years, simple_payback_years: null, npv_meur: v.npv_meur, irr: null, years: Math.max(0, v.cash_flow_meur.length - 1) } : null,
    firm: null,
  };
}
