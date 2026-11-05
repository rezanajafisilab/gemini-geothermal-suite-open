import { describe, expect, it } from "vitest";

import { dayName, operatingPlan, planCsv } from "./operations";
import type { Design } from "../../workbench";

const days = (v: number) => Array.from({ length: 365 }, () => v);

const design = {
  code: "1D-BO-EC",
  plant: { depth_m: 2500, max_brine_cooling_k: 40 },
  year: {
    cool_demand_gwh: 1,
    daily_mw: {
      heat: { demand: days(20), geo: days(12), hp: days(0), boiler: days(8), electric_boiler: days(0), short: days(0) },
      cool: { demand: days(5), free: days(4), abs: days(0), chill: days(1), short: days(0) },
      power: { pumps: days(1), chillers: days(0.2) },
    },
    doublets: [{ flow_m3h: days(250), on: days(1).map(() => true), wellhead_c: days(86), reinjection_c: days(47) }],
    stop_ranges: [[[10, 12]]],
  },
} as unknown as Design;

describe("the operating plan", () => {
  it("sets out each day's figures from the year, with a stop and a cap within reach", () => {
    const plan = operatingPlan(design, 7, 7);
    expect(plan).toHaveLength(7);
    expect(plan[0].label).toBe(dayName(7));
    expect(plan[0].heat).toMatchObject({ demand: 20, geo: 12, boiler: 8 });
    expect(plan[0].doublets[0]).toMatchObject({ flow: 250, wellhead: 86, reinjection: 47, cooled: 39, atCap: false });
    expect(plan[0].electricity).toBeCloseTo(1.2);
    expect(plan[3].notes).toContain("Doublet 1 stopped (maintenance)");
    expect(plan[0].notes).toEqual([]);
    const hot = { ...design, year: { ...design.year, doublets: [{ ...design.year.doublets![0], reinjection_c: days(45.8) }] } } as Design;
    expect(operatingPlan(hot, 0, 1)[0].doublets[0].atCap).toBe(true);
  });

  it("writes the plan as CSV, one row a day", () => {
    const csv = planCsv(design, operatingPlan(design, 0, 365)).trim().split("\n");
    expect(csv).toHaveLength(366);
    expect(csv[0]).toContain("doublet_1_flow_m3h");
    expect(csv[1].startsWith("2027-01-01,20.00,12.00")).toBe(true);
  });
});
