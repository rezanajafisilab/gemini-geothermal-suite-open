import { describe, expect, it } from "vitest";

import type { SweepView } from "../../workbench";
import { cheapestBy, frontOf, variedParameters } from "./SweepMap";

const columns = ["doublets", "depth_m", "flow_cap_m3h", "heat_pump_mw", "boiler_mw", "electric_boiler_mw", "absorption_mw", "chiller_mw", "gas", "lcoe", "lcoh", "co2_t", "co2_saving_pct", "capex_meur", "broken"];
const row = (n: number, depth: number, lcoe: number, co2: number, broken = "") => [n, depth, 300, 0, 20, 0, 0, 10, "buy", lcoe, lcoe, co2, 50, 40, broken];
const view = {
  columns,
  rows: [row(1, 2500, 70, 9000), row(1, 3000, 60, 9500), row(2, 3000, 65, 7000), row(3, 3500, 90, 6000), row(2, 2500, 40, 5000, "heat")],
  front: [1, 2, 3],
  ranges: { depth_m: [2500, 3500], flow_cap_m3h: [100, 300], heat_pump_mw: [0, 15], boiler_mw: [0, 36], electric_boiler_mw: [0, 36], absorption_mw: [0, 12], chiller_mw: [0, 15] },
  feasible: 4,
  failures: { heat: 1 },
  broken_words: { heat: "heat short on some days" },
  seconds: 1,
  search: { id: "S1", name: "Run A" },
  marks: [],
} as unknown as SweepView;

describe("the design space", () => {
  it("says what the sweep varied, with each range", () => {
    const p = variedParameters(view);
    expect(p.find((x) => x.key === "doublets")?.range).toBe("1, 2, 3");
    expect(p.find((x) => x.key === "depth_m")?.range).toBe("2,500–3,500 m");
    expect(p.find((x) => x.key === "gas")?.range).toBe("gas bought");
  });

  it("finds the cheapest feasible design at each value of a choice, a failed one left out", () => {
    expect(cheapestBy(view, "doublets")).toEqual([
      { x: 1, cost: 60, n: 2 },
      { x: 2, cost: 65, n: 1 },
      { x: 3, cost: 90, n: 1 },
    ]);
  });

  it("joins the feasible designs no other beats on both cost and CO₂", () => {
    expect(frontOf(view)).toEqual([
      [60, 9500],
      [65, 7000],
      [90, 6000],
    ]);
  });
});
