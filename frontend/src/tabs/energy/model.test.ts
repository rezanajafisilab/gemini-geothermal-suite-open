import { describe, expect, it } from "vitest";

import type { Year } from "../../workbench";
import { CO2_META, activeIndices, co2Parts, co2Share, dayLabel, dayRows, doubletYears, durationRows, monthOf, peakIndex, shortRuns, sideShares, stackTops, stopRanges, unmetOf, yearQuestion } from "./model";

const KEYS = ["geo", "hp", "boiler"];

describe("dayRows", () => {
  it("reads each source in key order and works out the gap", () => {
    const rows = dayRows({ demand: [10, 4, 2], geo: [6, 4, 2], hp: [3, 0, 0], boiler: [1, 0, 0] }, KEYS);
    expect(rows.map((r) => r.parts)).toEqual([
      [6, 3, 1],
      [4, 0, 0],
      [2, 0, 0],
    ]);
    expect(rows.map((r) => r.supplied)).toEqual([10, 4, 2]);
    expect(rows.every((r) => r.unmet === 0)).toBe(true);
    expect(rows.map((r) => r.day)).toEqual([0, 1, 2]);
  });

  it("counts a missing or short source as 0, never negative", () => {
    const rows = dayRows({ demand: [5, 5], geo: [3], hp: [-1, "x"] }, KEYS);
    expect(rows[0].parts).toEqual([3, 0, 0]);
    expect(rows[1].parts).toEqual([0, 0, 0]);
    expect(rows[1].unmet).toBe(5);
  });

  it("has no rows without a demand series", () => {
    expect(dayRows(undefined, KEYS)).toEqual([]);
    expect(dayRows({ geo: [1, 2] }, KEYS)).toEqual([]);
  });
});

describe("unmetOf", () => {
  it("ignores rounding but keeps a real gap", () => {
    expect(unmetOf(13.88, 13.879)).toBe(0); // 1 kW under: rounding
    expect(unmetOf(10, 9.96)).toBe(0); // 0.4 %: rounding
    expect(unmetOf(10, 9)).toBeCloseTo(1);
    expect(unmetOf(2, 3)).toBe(0); // over-supply is not a gap
  });
});

describe("stackTops", () => {
  it("stacks each source on the ones below it", () => {
    const rows = dayRows({ demand: [10, 4], geo: [6, 4], hp: [3, 0], boiler: [1, 0] }, KEYS);
    expect(stackTops(rows, 3)).toEqual([
      [6, 4],
      [9, 4],
      [10, 4],
    ]);
  });

  it("puts the top of the last layer on the supplied total", () => {
    const rows = dayRows({ demand: [8, 8], geo: [2, 5], hp: [2, 1], boiler: [3, 0] }, KEYS);
    const tops = stackTops(rows, 3);
    expect(tops[2]).toEqual(rows.map((r) => r.supplied));
  });
});

describe("durationRows", () => {
  const rows = dayRows({ demand: [3, 9, 5, 9, 1], geo: [3, 6, 5, 6, 1], hp: [0, 3, 0, 3, 0], boiler: [0, 0, 0, 0, 0] }, KEYS);
  const sorted = durationRows(rows);

  it("sorts the days by demand, highest first, ties by date", () => {
    expect(sorted.map((r) => r.demand)).toEqual([9, 9, 5, 3, 1]);
    expect(sorted.map((r) => r.day)).toEqual([1, 3, 2, 0, 4]);
  });

  it("keeps each day's own supply with it", () => {
    expect(sorted[0].parts).toEqual([6, 3, 0]);
    expect(sorted[3].parts).toEqual([3, 0, 0]);
  });

  it("leaves the date order alone", () => {
    expect(rows.map((r) => r.day)).toEqual([0, 1, 2, 3, 4]);
  });

  it("stacks in the same source order as the year", () => {
    const tops = stackTops(sorted, 3);
    expect(tops[0]).toEqual([6, 6, 5, 3, 1]);
    expect(tops[1]).toEqual([9, 9, 5, 3, 1]);
  });
});

describe("shares, peaks and gaps", () => {
  const rows = dayRows({ demand: [10, 10, 2, 10], geo: [6, 6, 2, 6], hp: [4, 2, 0, 2], boiler: [0, 0, 0, 0] }, KEYS);

  it("gives each source's share of the supply and the share not met", () => {
    const s = sideShares(rows, 3);
    expect(s.parts[0]).toBeCloseTo(20 / 28);
    expect(s.parts[1]).toBeCloseTo(8 / 28);
    expect(s.parts[2]).toBe(0);
    expect(s.unmet).toBeCloseTo(4 / 32);
  });

  it("lists the sources that supply anything", () => {
    expect(activeIndices(rows, 3)).toEqual([0, 1]);
  });

  it("finds the first day of the highest demand", () => {
    expect(peakIndex(rows)).toBe(0);
    expect(peakIndex([])).toBe(-1);
  });

  it("groups short days into runs", () => {
    expect(shortRuns(rows)).toEqual([[1, 1], [3, 3]]);
    const run = dayRows({ demand: [5, 5, 5, 1], geo: [1, 1, 1, 1] }, KEYS);
    expect(shortRuns(run)).toEqual([[0, 2]]);
  });
});

describe("dates", () => {
  it("labels days of a 365-day year", () => {
    expect(dayLabel(0)).toBe("1 Jan");
    expect(dayLabel(31)).toBe("1 Feb");
    expect(dayLabel(58)).toBe("28 Feb");
    expect(dayLabel(59)).toBe("1 Mar");
    expect(dayLabel(364)).toBe("31 Dec");
    expect(monthOf(200)).toBe(6);
  });
});

describe("yearQuestion", () => {
  it("asks why the peak source runs in its busiest month", () => {
    const demand = new Array(365).fill(1);
    const boiler = new Array(365).fill(0);
    boiler[10] = 2; // January
    const rows = dayRows({ demand, geo: demand, hp: new Array(365).fill(0), boiler }, KEYS);
    expect(yearQuestion(rows, KEYS, "heat")).toBe("Why does the gas boiler run in January?");
  });

  it("uses the plural for the chillers", () => {
    const demand = new Array(365).fill(1);
    const rows = dayRows({ demand, abs: new Array(365).fill(0), chill: demand }, ["abs", "chill"]);
    expect(yearQuestion(rows, ["abs", "chill"], "cool")).toBe("Why do the electric chillers run in January?");
  });
});

describe("doubletYears", () => {
  const year = {
    stop_days: [[2, 3], [0, 0]],
    doublets: [
      { flow_m3h: [300, 250, 0, 0, 120], on: [true, true, false, false, true], reinjection_c: [56, 56, null, null, 58], wellhead_c: [86.1, 86, null, null, 85.2] },
      { flow_m3h: [0, 300, 300, 300, 300], on: [false, true, true, true, true], reinjection_c: [null, 56, 56, 56, 56] },
    ],
  } as unknown as Year;

  it("reads each doublet's flow, days on, mean and wellhead range, and its stop", () => {
    const [a, b] = doubletYears(year, { doublets: [{ doublet: 1, cap_m3h: 300 }, { doublet: 2, cap_m3h: 200 }] });
    expect(a).toMatchObject({ doublet: 1, cap: 300, daysOn: 3, tMin: 85.2, tMax: 86.1, stop: [2, 3] });
    expect(a.mean).toBeCloseTo(670 / 3, 9);
    expect(a.wellhead).toEqual([86.1, 86, null, null, 85.2]);
    // An older server sends no wellhead: no range, the rest as before.
    expect(b).toMatchObject({ doublet: 2, cap: 200, daysOn: 4, mean: 300, tMin: null, tMax: null });
    expect(doubletYears({} as Year)).toEqual([]);
  });

  it("reads every planned stop: one block each (stop_days), or the user's ranges (stop_ranges)", () => {
    expect(doubletYears(year).map((d) => d.stops)).toEqual([[[2, 3]], [[0, 0]]]);
    const mine = { ...year, stop_ranges: [[[0, 1], [3, 3]], []] } as unknown as Year;
    const [a, b] = doubletYears(mine);
    expect(a.stops).toEqual([
      [0, 1],
      [3, 3],
    ]);
    expect(a.stop).toEqual([0, 1]);
    expect(b).toMatchObject({ stops: [], stop: null });
    expect(stopRanges(null)).toEqual([]);
  });
});


describe("co2Parts", () => {
  const split = { boiler: 8133.0, electric_boiler: 0, hp: 92.1, pumps: 760.9, flare: 52.8, brine_co2: 553.4, chillers: 149.8, towers: 86.0, network: 0 };

  it("keeps the units that let out CO₂ in the fixed order, adding up to the total", () => {
    const out = co2Parts({ co2_by_unit_t: split })!;
    expect(out.parts.map((p) => p.key)).toEqual(["boiler", "hp", "pumps", "flare", "brine_co2", "chillers", "towers"]);
    expect(out.total).toBeCloseTo(9828, 6);
    expect(out.parts.reduce((a, p) => a + p.share, 0)).toBeCloseTo(1, 9);
    expect(out.none).toEqual(["Electric boiler", "Network pumps"]);
    // One colour per unit, none twice.
    expect(new Set(CO2_META.map((m) => m.color)).size).toBe(CO2_META.length);
  });

  it("puts an unknown unit last in grey, and has nothing without a split or any CO₂", () => {
    const out = co2Parts({ co2_by_unit_t: { hp: 10, recovery_hp: 5 } })!;
    expect(out.parts.map((p) => p.key)).toEqual(["hp", "recovery_hp"]);
    expect(out.parts[1].label).toBe("Recovery hp");
    expect(co2Parts({})).toBeNull();
    expect(co2Parts({ co2_by_unit_t: { boiler: 0 } })).toBeNull();
  });

  it("writes shares with one decimal, a sliver as <0.1%", () => {
    expect(co2Share(0.8275)).toBe("82.8%");
    expect(co2Share(0.5)).toBe("50%");
    expect(co2Share(0.00004)).toBe("<0.1%");
    expect(co2Share(0)).toBe("0%");
  });
});
