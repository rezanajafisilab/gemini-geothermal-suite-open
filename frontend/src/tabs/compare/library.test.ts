// The design library's logic: numbers as shown, scenarios (what-ifs with the same change are one),
// the filters, sorting (never across scenarios), pages, ticking (four at most), links that name
// designs, the side by side (best marked only within one scenario), the chart's helpers, the
// rows an older server's payload makes (and the fixtures' own library, offline), and the store
// opening a design into the tabs.

import { describe, expect, it, vi } from "vitest";

import { loadFixtures, type Attempt, type Candidate, type Design, type LibraryRow, type Workbench } from "../../workbench";
import { WorkbenchStore } from "../../workbench/store";
import {
  ALL,
  compareSections,
  compareUid,
  defaultScenario,
  filterRows,
  filtersActive,
  fixed,
  fmtT,
  fmtVsGas,
  gasCost,
  libraryOf,
  markBest,
  matchesQuery,
  n1Met,
  nextSort,
  orderScenarios,
  pageOf,
  reliabilityText,
  resolveIds,
  ringOf,
  scenarioKey,
  scenariosIn,
  scenariosOf,
  signed,
  sortRows,
  tidy,
  toggleSelected,
  worstText,
  type LibraryFilter,
} from "./library";

const BASE = { id: "S1", n: 1, kind: "base", label: "Base case" };
const GAS = { id: "S2", n: 2, kind: "what_if", label: "What-if: gas price 30 EUR/MWh" };
const COLD = { id: "S3", n: 3, kind: "what_if", label: "What-if: reservoir -10 K" };
const USER = { id: "user", n: 0, kind: "user", label: "Your designs" };

const firm = (short: number, cases = 5) => ({ cases, short, worst: short ? { unit: "the boiler", side: "heat", mw: 20.77, day: "28 Jan" } : null, spare_heat_mw: 10.4, spare_cool_mw: 5 });

function row(uid: string, extra: Partial<LibraryRow> = {}): LibraryRow {
  const code = extra.code ?? "1D-HP-EC";
  return {
    id: `${uid} · ${code}`,
    uid,
    code,
    name: `Plant ${uid}`,
    scenario: BASE,
    origin: "agent",
    role: "candidate",
    picks: [],
    recommended: false,
    in_tabs: false,
    reliable: false,
    n_doublets: 1,
    depth_m: 2500,
    topup: "heat_pump",
    cooling: "electric",
    sizes_mw: { heat_exchanger: 7.2, heat_pump: 2, boiler: 20.8, absorption: 0, chillers: 10 },
    lcoe: 70,
    lcoh: 75,
    lcoc: 42,
    co2_t: 14000,
    co2_saving_pct: 42,
    capex_meur: 30,
    wells: 2,
    verified: true,
    violations: [],
    reason: "",
    vs_gas_pct: { heat: -0.2, cold: 0.3, total: -0.15 },
    money: { extra_capex_meur: 25, savings_meur_per_year: 3.6, payback_years: 9, simple_payback_years: 6.9, npv_meur: 26, irr: 0.14, years: 30 },
    firm: firm(0),
    ...extra,
  };
}

// A chat as the server sends it: the base search, a what-if search and the what-if of A1 under
// the same change, a reservoir what-if, and your design.
const A1 = row("A1", { code: "1D-HP-EC-N1", role: "chosen", picks: ["best"], recommended: true, in_tabs: true, reliable: true, lcoe: 69.8 });
const A2 = row("A2", { code: "1D-HP-AB-N1", picks: ["reliable"], reliable: true, lcoe: 69.77, capex_meur: 31.5 });
const A11 = row("A11", { code: "1D-HP-AB", picks: ["cost"], lcoe: 68.13, firm: firm(5, 6), money: { ...A1.money!, npv_meur: 29.4 } });
const A35 = row("A35", { code: "3D-HP-EC", picks: ["co2"], n_doublets: 3, lcoe: 80.3, co2_t: 10045, capex_meur: 65.3, firm: firm(8, 9) });
const A40 = row("A40", { code: "2D-DH-EC", role: "failed", n_doublets: 2, lcoe: 60, violations: ["Heat short of 100 °C supply on 52 days"], firm: null });
const B1 = row("B1", { code: "1D-BO-EC-N1", scenario: GAS, role: "chosen", picks: ["best", "reliable"], in_tabs: true, lcoe: 53.4 });
const B2 = row("B2", { code: "1D-HP-EC-N1", scenario: GAS, lcoe: 54.9 });
const W1 = row("W1", { code: "1D-HP-EC-N1", scenario: GAS, origin: "what_if", role: "what_if", in_tabs: true, lcoe: 56.2 });
const C1 = row("C1", { code: "1D-HP-EC-N1", scenario: COLD, role: "chosen", picks: ["best"], in_tabs: true, lcoe: 78.4, firm: firm(1) });
const U1 = row("U1", { code: "U1", scenario: USER, origin: "user", role: "user", in_tabs: true, n_doublets: 2, lcoe: 74.2, money: null });
const ROWS = [A1, A2, A11, A35, A40, B1, B2, C1, W1, U1];

const attempt = (n: number, at: number, message: string): Attempt => ({
  id: `S${n}`,
  n,
  at,
  message,
  label: "",
  objective: "cost",
  chosen: null,
  repriced: false,
  candidates: [],
  reference: null,
});
const ATTEMPTS = [attempt(1, 1000, "Design heating and cooling"), attempt(2, 2000, "what if gas cost 30 €/MWh?"), attempt(3, 3000, "reservoir 10 K colder?")];

const NONE: LibraryFilter = { scenario: ALL, picksOnly: false, doublets: [], reliableOnly: false, validOnly: false, query: "" };
const ids = (rows: LibraryRow[]) => rows.map((r) => r.uid);

describe("numbers as shown", () => {
  it("writes fixed decimals with thousands and a real minus", () => {
    expect(fixed(69.8, 1)).toBe("69.8");
    expect(fixed(70, 1)).toBe("70.0");
    expect(fixed(-3.14, 1)).toBe("−3.1");
    expect(fmtT(14333.9)).toBe("14,334");
    expect(fixed(-0.04, 1)).toBe("0.0");
    expect(fixed(null, 1)).toBe("–");
  });

  it("signs NPVs and percentages against gas", () => {
    expect(signed(29.42, 1)).toBe("+29.4");
    expect(signed(-1.5, 1)).toBe("−1.5");
    expect(signed(0.01, 1)).toBe("0.0");
    expect(fmtVsGas(-0.1733)).toBe("−17.3%");
    expect(fmtVsGas(0.3439)).toBe("+34.4%");
    expect(fmtVsGas(null)).toBe("–");
  });

  it("tidies the server's words", () => {
    expect(tidy("What-if: gas price 30 EUR/MWh")).toBe("What-if: gas price 30 €/MWh");
    expect(tidy("reservoir -10 K; -1.7 €/MWh (68.1 against 69.8), CO2")).toBe("reservoir −10 K; −1.7 €/MWh (68.1 against 69.8), CO₂");
    expect(tidy("chillers 9 -> 10 MW")).toBe("chillers 9 → 10 MW");
    expect(tidy("2D-HP-EC")).toBe("2D-HP-EC");
  });

  it("says one unit out in words", () => {
    expect(reliabilityText(firm(0))).toBe("N-1 met");
    expect(reliabilityText(firm(5, 6))).toBe("5 of 6 cases short");
    expect(reliabilityText(null)).toBe("–");
    expect(worstText(firm(1))).toBe("the boiler out leaves heat 20.8 MW short on 28 Jan");
    expect(n1Met(A1)).toBe(true);
    expect(n1Met(A11)).toBe(false);
    // A what-if can break a plan sized for N-1: the cases decide, not the sizing.
    expect(n1Met({ reliable: true, firm: firm(1) })).toBe(false);
    expect(n1Met({ reliable: true, firm: null })).toBe(true);
  });
});

describe("scenarios", () => {
  const groups = scenariosOf(ROWS, ATTEMPTS);

  it("makes the search under a change and the design re-run under it one scenario", () => {
    expect(W1.scenario.id).toBe(GAS.id); // the server tags the re-run with the search's id
    const gas = groups.find((g) => g.key === scenarioKey(GAS))!;
    expect(gas).toMatchObject({ label: "What-if: gas price 30 €/MWh", short: "gas price 30 €/MWh", n: 2, count: 3 });
    expect(gas.ids).toEqual(["S2"]);
    expect(gas.attempt?.message).toBe("what if gas cost 30 €/MWh?");
    expect(groups.map((g) => g.label)).toEqual(["Base case", "What-if: gas price 30 €/MWh", "What-if: reservoir −10 K", "Your designs"]);
  });

  it("orders newest or oldest first, with your designs last either way", () => {
    expect(orderScenarios(groups, "newest").map((g) => g.n)).toEqual([3, 2, 1, 0]);
    expect(orderScenarios(groups, "oldest").map((g) => g.kind)).toEqual(["base", "what_if", "what_if", "user"]);
  });

  it("starts on the base case, else the one with the recommended design", () => {
    expect(defaultScenario(groups)).toBe("S1");
    expect(groups.find((g) => g.key === "S1")?.recommended).toBe(true);
    const noBase = scenariosOf([B1, { ...C1, recommended: true }]);
    expect(defaultScenario(noBase)).toBe(scenarioKey(COLD));
    expect(defaultScenario([])).toBeNull();
  });

  it("lists the scenarios of some rows", () => {
    expect(scenariosIn([A1, A2], groups).map((g) => g.key)).toEqual(["S1"]);
    expect(scenariosIn([A1, W1], groups)).toHaveLength(2);
  });
});

describe("filters", () => {
  it("keeps one scenario, or all of them", () => {
    expect(ids(filterRows(ROWS, { ...NONE, scenario: "S1" }))).toEqual(["A1", "A2", "A11", "A35", "A40"]);
    expect(ids(filterRows(ROWS, { ...NONE, scenario: scenarioKey(GAS) }))).toEqual(["B1", "B2", "W1"]);
    expect(filterRows(ROWS, NONE)).toHaveLength(ROWS.length);
  });

  it("keeps the picks (and the recommended design), the doublets asked for, N-1 met, met every cap", () => {
    expect(ids(filterRows(ROWS, { ...NONE, scenario: "S1", picksOnly: true }))).toEqual(["A1", "A2", "A11", "A35"]);
    expect(ids(filterRows(ROWS, { ...NONE, doublets: [2, 3] }))).toEqual(["A35", "A40", "U1"]);
    expect(ids(filterRows(ROWS, { ...NONE, scenario: "S1", reliableOnly: true }))).toEqual(["A1", "A2"]);
    expect(ids(filterRows(ROWS, { ...NONE, scenario: "S1", validOnly: true }))).toEqual(["A1", "A2", "A11", "A35"]);
    expect(filtersActive(NONE)).toBe(false);
    expect(filtersActive({ ...NONE, query: " x " })).toBe(true);
  });

  it("searches names, codes, scenarios and picks, every word, CO2 as CO₂", () => {
    expect(matchesQuery(A11, "a11")).toBe(true);
    expect(matchesQuery(A11, "1d-hp-ab cheapest")).toBe(true);
    expect(matchesQuery(A35, "lowest co2")).toBe(true);
    expect(matchesQuery(B1, "gas 30")).toBe(true);
    expect(matchesQuery(A40, "broke a cap")).toBe(true);
    expect(matchesQuery(A1, "recommended")).toBe(true);
    expect(matchesQuery(A1, "boiler absorption")).toBe(false);
    expect(ids(filterRows(ROWS, { ...NONE, query: "1D-HP-EC-N1" }))).toEqual(["A1", "B2", "C1", "W1"]);
  });
});

describe("sorting", () => {
  const base = filterRows(ROWS, { ...NONE, scenario: "S1" });

  it("puts names in the search's order: A2 before A11", () => {
    expect(compareUid("A2", "A11")).toBeLessThan(0);
    expect(compareUid("B1", "A40")).toBeGreaterThan(0);
    expect(ids(sortRows([A11, A40, A2, A1, A35], { key: "rank", dir: "asc" }))).toEqual(["A1", "A2", "A11", "A35", "A40"]);
    expect(ids(sortRows(base, { key: "rank", dir: "desc" }))).toEqual(["A40", "A35", "A11", "A2", "A1"]);
  });

  it("sorts by a figure, missing values last both ways", () => {
    const rows = [...base, row("A50", { lcoe: null, money: null })];
    expect(ids(sortRows(rows, { key: "lcoe", dir: "asc" }))).toEqual(["A40", "A11", "A2", "A1", "A35", "A50"]);
    expect(ids(sortRows(rows, { key: "lcoe", dir: "desc" }))).toEqual(["A35", "A1", "A2", "A11", "A40", "A50"]);
    expect(ids(sortRows(rows, { key: "npv", dir: "desc" })).slice(0, 2)).toEqual(["A11", "A1"]);
    expect(ids(sortRows(rows, { key: "npv", dir: "desc" })).at(-1)).toBe("A50");
  });

  it("ranks one unit out by cases short, then by cost", () => {
    expect(ids(sortRows(base, { key: "n1", dir: "asc" }))).toEqual(["A2", "A1", "A11", "A35", "A40"]);
  });

  it("never ranks across scenarios when grouped", () => {
    const groups = orderScenarios(scenariosOf(ROWS, ATTEMPTS), "oldest");
    const at = new Map(groups.map((g, i) => [g.key, i]));
    const sorted = sortRows(ROWS, { key: "lcoe", dir: "asc" }, (r) => at.get(scenarioKey(r.scenario)) ?? 0);
    expect(ids(sorted)).toEqual(["A40", "A11", "A2", "A1", "A35", "B1", "B2", "W1", "C1", "U1"]);
  });

  it("clicks a column to its better end first, then the other way", () => {
    expect(nextSort({ key: "rank", dir: "asc" }, "npv")).toEqual({ key: "npv", dir: "desc" });
    expect(nextSort({ key: "rank", dir: "asc" }, "lcoe")).toEqual({ key: "lcoe", dir: "asc" });
    expect(nextSort({ key: "lcoe", dir: "asc" }, "lcoe")).toEqual({ key: "lcoe", dir: "desc" });
  });
});

describe("pages", () => {
  const many = Array.from({ length: 503 }, (_, i) => i);

  it("cuts 25 a page and clamps to the last", () => {
    expect(pageOf(many, 0)).toMatchObject({ page: 0, from: 1, to: 25 });
    expect(pageOf(many, 20)).toMatchObject({ page: 20, from: 501, to: 503 });
    expect(pageOf(many, 99)).toMatchObject({ page: 20 });
    expect(pageOf([], 3)).toMatchObject({ page: 0, from: 0, to: 0, rows: [] });
  });

  it("filters and sorts 500 designs quickly", () => {
    const rows = Array.from({ length: 500 }, (_, i) => row(`A${i + 1}`, { lcoe: 50 + ((i * 37) % 100) / 3, scenario: i % 2 ? BASE : GAS }));
    const t = performance.now();
    for (let k = 0; k < 20; k++) sortRows(filterRows(rows, { ...NONE, query: "plant" }), { key: "lcoe", dir: "asc" });
    expect((performance.now() - t) / 20).toBeLessThan(20);
  });
});

describe("ticking", () => {
  it("ticks and unticks, and refuses a fifth", () => {
    expect(toggleSelected([], "a")).toEqual({ selected: ["a"], refused: false });
    expect(toggleSelected(["a", "b"], "a")).toEqual({ selected: ["b"], refused: false });
    const four = ["a", "b", "c", "d"];
    expect(toggleSelected(four, "e")).toEqual({ selected: four, refused: true });
    expect(toggleSelected(four, "c").selected).toEqual(["a", "b", "d"]);
  });

  it("finds the designs a link names: by id, by name, by code (the recommended first)", () => {
    expect(resolveIds(["A11 · 1D-HP-AB", "a2"], ROWS)).toEqual(["A11 · 1D-HP-AB", "A2 · 1D-HP-AB-N1"]);
    expect(resolveIds(["1D-HP-EC-N1"], ROWS)).toEqual(["A1 · 1D-HP-EC-N1"]);
    expect(resolveIds(["nope", "B1", "B1 · 1D-BO-EC-N1"], ROWS)).toEqual(["B1 · 1D-BO-EC-N1"]);
    expect(resolveIds(["A1", "A2", "A11", "A35", "A40"], ROWS)).toHaveLength(4);
  });
});

describe("side by side", () => {
  const line = (sections: ReturnType<typeof compareSections>, key: string) => sections.flatMap((s) => s.lines).find((l) => l.key === key)!;

  it("marks the best of each figure within one scenario, ties as shown included", () => {
    const s = compareSections([A1, A2, A11], true);
    expect(line(s, "lcoe").best).toEqual([false, false, true]);
    // 69.8 and 69.77 both show 69.8 … but A11 is cheaper still; equal capitals tie.
    expect(line(s, "capex").best).toEqual([true, false, true]);
    expect(line(s, "npv").best).toEqual([false, false, true]);
    expect(line(s, "n1").best).toEqual([true, true, false]);
    expect(line(s, "n1").text).toEqual(["N-1 met", "N-1 met", "5 of 6 cases short"]);
    expect(line(s, "worst").text).toEqual(["none", "none", "the boiler out leaves heat 20.8 MW short on 28 Jan"]);
    expect(line(s, "doublets").best).toEqual([false, false, false]);
  });

  it("marks nothing when not ranked (designs from different scenarios)", () => {
    const s = compareSections([A1, B1], false);
    expect(s.flatMap((x) => x.lines).every((l) => l.best.every((b) => !b))).toBe(true);
  });

  it("needs two values that differ as shown", () => {
    const l = { key: "x", label: "x", unit: "", better: "lower" as const, values: [69.8, 69.77, null], text: ["69.8", "69.8", "–"], best: [false, false, false], digits: 1 };
    expect(markBest(l).best).toEqual([false, false, false]);
    expect(markBest({ ...l, values: [1, null, null] }).best).toEqual([false, false, false]);
  });

  it("says 'never' for a payback that never comes, '–' with no money", () => {
    const never = row("A9", { money: { ...A1.money!, payback_years: null } });
    expect(line(compareSections([never, U1], true), "payback").text).toEqual(["never", "–"]);
  });
});

describe("chart helpers", () => {
  it("works the gas plant's cost back from 'against gas' (the median)", () => {
    const rows = [row("A1", { lcoe: 70, vs_gas_pct: { heat: null, cold: null, total: 70 / 82 - 1 } }), row("A2", { lcoe: 41, vs_gas_pct: { heat: null, cold: null, total: -0.5 } }), row("A3", { lcoe: 82, vs_gas_pct: { heat: null, cold: null, total: 0 } })];
    expect(gasCost(rows, "lcoe")).toBeCloseTo(82, 6);
    expect(gasCost([row("A1", { vs_gas_pct: null })], "lcoe")).toBeNull();
  });

  it("draws more cases short as a thicker, darker ring", () => {
    const [one, five, many] = [ringOf(1), ringOf(5), ringOf(20)];
    expect(one.width).toBeLessThan(five.width);
    expect(five.width).toBeLessThan(many.width);
    expect(many).toEqual(ringOf(8));
    const sum = (c: string) => c.match(/\d+/g)!.map(Number).reduce((a, b) => a + b, 0);
    expect(sum(five.color)).toBeLessThan(sum(one.color));
  });
});

describe("rows from an older server", () => {
  const cand = (code: string, role: string, lcoe: number): Candidate => ({
    code,
    name: code,
    role,
    reason: "",
    n_doublets: 2,
    depth_m: 2500,
    topup: "heat_pump",
    cooling: "absorption",
    sizes_mw: {},
    lcoh: lcoe + 2,
    lcoc: 40,
    lcoe,
    co2_t: 9000,
    co2_saving_pct: 60,
    capex_meur: 40,
    heat_coverage_pct: 100,
    cool_coverage_pct: 100,
    rounds: 1,
    changes: [],
    violations: [],
    verified: true,
  });
  const design = { id: "2D-HP-AB", code: "2D-HP-AB", name: "Two doublets", origin: "agent", chosen: true, reservoir_delta_c: 0, verified: true, plant: { n_doublets: 2, depth_m: 2500, sizes_mw: {} }, economics: { lcoe: 50, lcoh: 52, lcoc: 40, capex_meur: 40, co2_t_per_year: 9000, co2_saving_pct: 60, versus_reference: { extra_capex_meur: 30, savings_meur_per_year: 3, payback_years: 11, npv_meur: 12, cash_flow_meur: [0, 1, 2] } }, year: {} } as unknown as Design;
  const whatIf = { ...design, id: "2D-HP-AB · reservoir -5 K", origin: "what_if", chosen: false, change_label: "reservoir -5 K" } as Design;

  it("passes the server's library through", () => {
    expect(libraryOf({ library: [A1], designs: [] })).toEqual([A1]);
    expect(libraryOf(null)).toEqual([]);
  });

  it("offline, the fixtures' own library: every design on the tabs, the pick recommended", async () => {
    const wb = (await loadFixtures()).workbench;
    const rows = libraryOf(wb);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows).toBe(wb.library);
    for (const d of wb.designs) expect(rows.find((r) => r.id === d.id)?.in_tabs, d.id).toBe(true);
    expect(rows.filter((r) => r.recommended).map((r) => r.id)).toEqual([wb.designs[0].id]);
  });

  it("makes rows from the searches and the designs, against the search's gas plant", () => {
    const a: Attempt = { ...attempt(1, 0, ""), candidates: [cand("2D-HP-AB", "chosen", 50), cand("1D-HP-AB", "candidate", 55), cand("REF", "reference", 82)], reference: cand("REF", "reference", 82) };
    const rows = libraryOf({ attempts: [a], designs: [design, whatIf] } as Pick<Workbench, "attempts" | "designs">);
    expect(rows.map((r) => [r.id, r.scenario.kind, r.in_tabs, r.recommended])).toEqual([
      ["2D-HP-AB", "base", true, true],
      ["1D-HP-AB (S1)", "base", false, false],
      ["2D-HP-AB · reservoir -5 K", "what_if", true, false],
    ]);
    expect(rows[1].vs_gas_pct?.total).toBeCloseTo(55 / 82 - 1, 6);
    expect(rows[2].scenario.label).toBe("What-if: reservoir -5 K");
    expect(rows[2].money?.npv_meur).toBe(12);
  });
});

describe("opening a design into the tabs (the store)", () => {
  const wb = (designs: Design[], library: LibraryRow[]): Workbench => ({ threadId: "t1", physics: "gemini", gemini: null, assumptions: {} as Workbench["assumptions"], designs, library });
  const d = (id: string) => ({ id, code: id, name: id, origin: "agent", parent: null, chosen: false, reservoir_delta_c: 0, checks: [], verified: true }) as unknown as Design;

  it("adds the design the server opened, so the picker lists it, and marks its row", async () => {
    const api = {
      getWorkbench: vi.fn(async () => ({ ok: true as const, data: wb([d(A1.id)], [A1, A11]), fixture: false })),
      openDesign: vi.fn(async (body: { id: string }) => ({ ok: true as const, data: { design: d(body.id) }, fixture: false })),
    };
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    await s.load();
    const res = await s.openDesign(A11.id);
    expect(res.ok).toBe(true);
    expect(api.openDesign).toHaveBeenCalledWith({ threadId: "t1", id: A11.id });
    expect(s.entry().workbench?.designs.map((x) => x.id)).toEqual([A1.id, A11.id]);
    expect(s.entry().workbench?.library?.find((r) => r.id === A11.id)?.in_tabs).toBe(true);
    // Already in the tabs: no request.
    await s.openDesign(A1.id);
    expect(api.openDesign).toHaveBeenCalledTimes(1);
  });

  it("leaves the designs as they were when the server can't open it", async () => {
    const api = {
      getWorkbench: vi.fn(async () => ({ ok: true as const, data: wb([d(A1.id)], [A1]), fixture: false })),
      openDesign: vi.fn(async () => ({ ok: false as const, status: 404, message: "no design", offline: false })),
    };
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    await s.load();
    const res = await s.openDesign("Z9");
    expect(res.ok).toBe(false);
    expect(s.entry().workbench?.designs).toHaveLength(1);
  });
});
