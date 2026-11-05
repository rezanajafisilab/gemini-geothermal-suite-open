// The Energy tab with an electric boiler: its own heat band in the stack (after the gas boiler),
// its colour and name, the heat installed with it, and the grid electricity by user.

import { describe, expect, it } from "vitest";

import type { Design, Year } from "../../workbench";
import { monthRows } from "../../components/MonthlyChart";
import { POWER_META, SIDE_KEYS, SOURCE_META, activeIndices, heatInstalled, powerParts, sideRows, sideShares } from "./model";

// 2D-HP-AB-EB-GS's year (engine.search, 31 Oct), three days of it.
const year = {
  heat_split_gwh: { geo: 57.884, hp: 53.612, boiler: 0, electric_boiler: 0.172 },
  daily_mw: {
    heat: { demand: [20, 30, 4], geo: [12, 12, 4], hp: [8, 12, 0], boiler: [0, 0, 0], electric_boiler: [0, 6, 0] },
    cool: { demand: [0, 0, 1], abs: [0, 0, 1], chill: [0, 0, 0] },
  },
  electricity_gwh: { hp: 13.646, recovery_hp: 0, chillers: 2.221, pumps: 4.135, towers: 0.403, network: 0, electric_boiler: 0.174 },
} as unknown as Year;

describe("the electric boiler in the Energy tab", () => {
  it("stacks last, after the gas boiler, in its own colour and name", () => {
    expect(SIDE_KEYS.heat).toEqual(["geo", "hp", "boiler", "electric_boiler"]);
    expect(SOURCE_META.electric_boiler).toEqual({ label: "Electric boiler", color: "#C8378A" });
    expect(SOURCE_META.boiler.label).toBe("Gas boiler");
    const colours = SIDE_KEYS.heat.map((k) => SOURCE_META[k].color);
    expect(new Set(colours).size).toBe(colours.length);
  });

  it("is a band of the day-by-day stack and of the shares, shown only when it runs", () => {
    const rows = sideRows(year, "heat");
    expect(rows[1].parts).toEqual([12, 12, 0, 6]);
    expect(rows[1].unmet).toBe(0);
    expect(activeIndices(rows, 4)).toEqual([0, 1, 3]);
    expect(sideShares(rows, 4).parts[3]).toBeCloseTo(6 / 54, 6);
    // A design without one (an older server, or one that buys gas): nothing in its band.
    const old = { daily_mw: { heat: { demand: [5], geo: [3], hp: [1], boiler: [1] } } } as unknown as Year;
    expect(sideRows(old, "heat")[0].parts).toEqual([3, 1, 1, 0]);
  });

  it("is a source of the months too", () => {
    const months = (v: number) => new Array(12).fill(v);
    const rows = monthRows({ demand: months(10), geo: months(6), hp: months(3), boiler: months(0), electric_boiler: months(1) }, ["geo", "hp", "boiler", "electric_boiler"])!;
    expect(rows[0].parts.map((p) => p.key)).toEqual(["geo", "hp", "boiler", "electric_boiler"]);
    expect(rows.every((r) => r.short === 0)).toBe(true);
  });

  it("counts in the heat installed, from the plant's sizes or else from its card", () => {
    const plant = { heat_pump: true, boiler: false, sizes_mw: { heat_exchanger: 14.46, heat_pump: 13, boiler: 0, absorption: 1, chillers: 13.5 } };
    const card = { nodes: [{ id: "electric_boiler", type: "electric_boiler", values: { power_mw: 2.6 } }] };
    expect(heatInstalled({ plant, graph: card } as unknown as Design)).toBeCloseTo(14.46 + 13 + 2.6, 6);
    expect(heatInstalled({ plant: { ...plant, sizes_mw: { ...plant.sizes_mw, electric_boiler: 30 } }, graph: card } as unknown as Design)).toBeCloseTo(14.46 + 13 + 30, 6);
    expect(heatInstalled({ plant, graph: { nodes: [] } } as unknown as Design)).toBeCloseTo(27.46, 6);
  });
});

describe("grid electricity", () => {
  it("lists who draws it, the electric boiler among them, in a fixed order, leaving out who draws none", () => {
    const parts = powerParts(year);
    expect(parts.map((p) => [p.key, p.gwh])).toEqual([
      ["hp", 13.646],
      ["electric_boiler", 0.174],
      ["pumps", 4.135],
      ["chillers", 2.221],
      ["towers", 0.403],
    ]);
    expect(parts.find((p) => p.key === "electric_boiler")!.color).toBe(SOURCE_META.electric_boiler.color);
    expect(parts.reduce((a, p) => a + p.gwh, 0)).toBeCloseTo(20.579, 6);
  });

  it("keeps a user it doesn't know, last, and nothing without a year's electricity", () => {
    const parts = powerParts({ electricity_gwh: { hp: 1, heat_tracing: 0.5 } } as unknown as Year);
    expect(parts.map((p) => p.label)).toEqual(["Heat pump", "Heat tracing"]);
    expect(powerParts({} as Year)).toEqual([]);
    expect(new Set(POWER_META.map((m) => m.color)).size).toBe(POWER_META.length);
  });
});
