// The monthly chart's rows and the comparison's order and labels, on the recorded numbers.

import { describe, expect, it } from "vitest";

import type { ComparedDesign } from "../agent/types";
import { METRICS, compareRows, whatIfLabel } from "./ComparisonCard";
import { monthRows } from "./MonthlyChart";

const DEMAND = [9.952, 8.624, 8.049, 5.596, 3.398, 1.397, 0.569, 0.963, 2.394, 4.799, 6.959, 9.057];

describe("monthly energy", () => {
  it("adds up each month's sources and finds no shortfall within rounding", () => {
    const rows = monthRows(
      {
        demand: DEMAND,
        geo: [6.021, 5.439, 6.021, 5.388, 3.398, 1.397, 0.569, 0.963, 2.394, 4.784, 5.824, 6.021],
        hp: [3.049, 2.743, 2.026, 0.207, 0, 0, 0, 0, 0, 0.015, 1.136, 2.841],
        boiler: [0.881, 0.442, 0.002, 0, 0, 0, 0, 0, 0, 0, 0, 0.194],
      },
      ["geo", "hp", "boiler"],
    )!;
    expect(rows).toHaveLength(12);
    expect(rows[0].parts.map((p) => p.key)).toEqual(["geo", "hp", "boiler"]);
    expect(rows[0].supplied).toBeCloseTo(9.951, 3);
    expect(rows.every((r) => r.short === 0)).toBe(true);
  });

  it("marks a month short when the supply misses the demand, and tolerates a missing source", () => {
    const rows = monthRows({ demand: DEMAND, geo: DEMAND.map((d, i) => (i === 0 ? d - 2 : d)) }, ["geo", "hp"])!;
    expect(rows[0].short).toBeCloseTo(2, 6);
    expect(rows[0].parts[1]).toEqual({ key: "hp", gwh: 0 });
    expect(rows.slice(1).every((r) => r.short === 0)).toBe(true);
  });

  it("needs twelve months of demand", () => {
    expect(monthRows({ demand: [1, 2, 3] }, ["geo"])).toBeNull();
    expect(monthRows(undefined, ["geo"])).toBeNull();
  });
});

const design = (code: string, extra: Partial<ComparedDesign> = {}): ComparedDesign => ({
  code,
  name: code,
  verified: true,
  lcoh: 40,
  lcoc: 58,
  co2_saving_pct: 80,
  heat_coverage_pct: 100,
  cool_coverage_pct: 100,
  capex_meur: 20,
  reservoir_delta_c: 0,
  reference: false,
  source: "mock",
  ...extra,
});

describe("designs compared", () => {
  it("puts the chosen design first, once, and keeps the rest in order", () => {
    const rows = compareRows({ chosen: "A2", designs: [design("A1"), design("A4", { reference: true }), design("A2"), design("A2", { reservoir_delta_c: 0 })] });
    expect(rows.map((r) => [r.design.code, r.chosen, r.index])).toEqual([
      ["A2", true, 2],
      ["A1", false, 0],
      ["A4", false, 1],
      ["A2", false, 3],
    ]);
    expect(compareRows({ chosen: null, designs: [design("A1"), design("A2")] }).every((r) => !r.chosen)).toBe(true);
  });

  it("labels a what-if by its reservoir change", () => {
    expect(whatIfLabel(design("A1", { reservoir_delta_c: -10 }))).toBe("what-if: reservoir −10 °C");
    expect(whatIfLabel(design("A1", { reservoir_delta_c: 5.5 }))).toBe("what-if: reservoir +5.5 °C");
    expect(whatIfLabel(design("A1"))).toBeNull();
  });

  it("has no cost of heat or CO₂ for a design that delivers no heat, nor cost of cold without cold", () => {
    const get = (id: string, d: ComparedDesign) => METRICS.find((m) => m.id === id)!.get(d);
    const none = design("A3", { heat_coverage_pct: 0, lcoh: 9999, cool_coverage_pct: 0 });
    expect(get("lcoh", none)).toBeNull();
    expect(get("co2", none)).toBeNull();
    expect(get("lcoc", none)).toBeNull();
    expect(get("capex", none)).toBe(20);
    expect(get("lcoc", design("A1", { lcoc: null }))).toBeNull();
  });
});
