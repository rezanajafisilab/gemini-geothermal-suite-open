// The six picks and the gas-free designs in the library: their labels and rules, the flags in
// words (EB, GS), the "Gas-free" filter, the search box and the electric boiler's size line.

import { describe, expect, it } from "vitest";

import { flagMeaning } from "../../agent/numbers";
import type { LibraryRow } from "../../workbench";
import { FAMILY_NAMES, codeParts, flagWords } from "./flags";
import { ALL, PICKS, PICK_LABEL, PICK_RULE, compareSections, filterRows, filtersActive, isGasFree, matchesQuery, picksOf, type LibraryFilter } from "./library";

const BASE = { id: "S1", n: 1, kind: "base", label: "Base case" };

function row(uid: string, code: string, extra: Partial<LibraryRow> = {}): LibraryRow {
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
    n_doublets: 2,
    depth_m: 2500,
    topup: "heat_pump",
    cooling: "absorption",
    sizes_mw: { heat_exchanger: 14.46, heat_pump: 9.8, boiler: 3.7, absorption: 1, chillers: 13.5 },
    lcoe: 90,
    lcoh: 95,
    lcoc: 50,
    co2_t: 7500,
    co2_saving_pct: 60,
    capex_meur: 60,
    verified: true,
    violations: [],
    vs_gas_pct: null,
    money: null,
    firm: null,
    flags: codeParts(code).flags,
    ...extra,
  };
}

// The challenge's search of 31 Oct (engine.search(DesignBrief())): its six picks.
const BEST = row("A1", "1D-HP-EC-N1", { picks: ["best"], n_doublets: 1, lcoe: 77.4 });
const FREE = row("A3", "2D-HP-AB-N1-EB", { picks: ["gas_free"], reliable: true, lcoe: 92.7, sizes_mw: { heat_exchanger: 14.46, heat_pump: 9.8, boiler: 3.7, absorption: 1, chillers: 13.5, electric_boiler: 30 } });
const SOLD = row("A4", "2D-HP-AB-N1-EB-GS", { picks: ["green_reliable"], reliable: true, lcoe: 101.68, sizes_mw: { heat_exchanger: 14.46, heat_pump: 13, boiler: 0, absorption: 1, chillers: 13.5, electric_boiler: 30 } });
const GREEN = row("A5", "2D-HP-AB-EB-GS", { picks: ["co2"], lcoe: 87.55, flags: undefined });
const ROWS = [BEST, FREE, SOLD, GREEN, row("A9", "2D-HP-AB")];
const NONE: LibraryFilter = { scenario: ALL, picksOnly: false, doublets: [], reliableOnly: false, validOnly: false, query: "" };

describe("the six picks", () => {
  it("lists the greenest reliable and the gas-free picks, each with a label and its rule", () => {
    expect(PICKS).toEqual(["best", "cost", "co2", "reliable", "green_reliable", "gas_free"]);
    for (const p of PICKS) {
      expect(PICK_LABEL[p], p).toBeTruthy();
      expect(PICK_RULE[p], p).toBeTruthy();
    }
    expect(PICK_LABEL.gas_free).toBe("gas-free");
    expect(PICK_RULE.gas_free).toMatch(/buys no gas/);
    expect(picksOf(row("A6", "2D-HP-AB", { picks: ["gas_free", "best", "green_reliable"] }))).toEqual(["best", "green_reliable", "gas_free"]);
  });
});

describe("gas-free designs", () => {
  it("are the ones flagged EB (from their flags, or their code when the row has none)", () => {
    expect([BEST, FREE, SOLD, GREEN].map(isGasFree)).toEqual([false, true, true, true]);
  });

  it("say what EB and GS mean, in the library and on the chat's cards", () => {
    expect(flagWords("EB")).toMatch(/^no gas bought: an electric boiler for the peaks/);
    expect(flagWords("GS")).toBe("the brine's gas cleaned and sold to the gas grid (nothing burnt on site)");
    expect([FAMILY_NAMES.EB, FAMILY_NAMES.GS]).toEqual(["gas-free", "gas sold"]);
    expect(flagMeaning("EB")).toMatch(/^Gas-free: no gas bought/);
    expect(flagMeaning("GS")).toMatch(/the buyer's CO₂ is not counted here/);
  });

  it("can be the only ones shown, and the filter counts as one narrowing the list", () => {
    expect(filterRows(ROWS, { ...NONE, gasFreeOnly: true }).map((r) => r.uid)).toEqual(["A3", "A4", "A5"]);
    expect(filterRows(ROWS, NONE)).toHaveLength(5);
    expect(filtersActive({ ...NONE, gasFreeOnly: true })).toBe(true);
    expect(filtersActive(NONE)).toBe(false);
  });

  it("are found by the search box: gas-free, the flags' words, the pick", () => {
    expect(ROWS.filter((r) => matchesQuery(r, "gas-free")).map((r) => r.uid)).toEqual(["A3", "A4", "A5"]);
    expect(ROWS.filter((r) => matchesQuery(r, "sold to the gas grid")).map((r) => r.uid)).toEqual(["A4", "A5"]);
    expect(ROWS.filter((r) => matchesQuery(r, "greenest")).map((r) => r.uid)).toEqual(["A4"]);
  });

  it("show the electric boiler's size side by side, the gas boiler named as such", () => {
    const plant = compareSections([BEST, FREE, SOLD], false).find((s) => s.title === "Plant")!;
    const eb = plant.lines.find((l) => l.key === "size_electric_boiler")!;
    expect(eb.label).toBe("Electric boiler");
    expect(eb.text).toEqual(["–", "30.0", "30.0"]);
    expect(plant.lines.find((l) => l.key === "size_boiler")!.label).toBe("Gas boiler");
  });
});
