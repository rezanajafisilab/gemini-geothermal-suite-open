// The chart's scales: round y ticks, month ticks for a year of dates, and colours that follow
// the series (heat warm, cooling cool) within the validated first three slots.

import { describe, expect, it } from "vitest";

import { dateTicks, niceTicks, seriesColors } from "./LineChart";

describe("line chart scales", () => {
  it("gives round y ticks that cover the values", () => {
    expect(niceTicks(0, 16.22)).toEqual([0, 5, 10, 15, 20]);
    expect(niceTicks(-4.3, 22.1)).toEqual([-5, 0, 5, 10, 15, 20, 25]);
    expect(niceTicks(0, 0.84)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
    expect(niceTicks(5, 5)[0]).toBe(0);
  });

  it("ticks a year of dates by month, thinning them when the plot is narrow", () => {
    const lo = Date.UTC(2025, 0, 1);
    const hi = Date.UTC(2025, 11, 27);
    expect(dateTicks(lo, hi, 12).map((t) => t.label)).toEqual(["Jan 2025", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]);
    expect(dateTicks(lo, hi, 5).map((t) => t.label)).toEqual(["Jan 2025", "Apr", "Jul", "Oct"]);
    expect(dateTicks(lo, lo + 10 * 864e5, 6).map((t) => t.label)[0]).toBe("1 Jan");
  });

  it("colours heat warm and cooling cool, the rest in order", () => {
    const [blue, orange, aqua] = ["#2a78d6", "#eb6834", "#1baf7a"];
    expect(seriesColors(["heat_demand_mw", "hot_water_mw", "t_outdoor_c"])).toEqual([orange, aqua, blue]);
    expect(seriesColors(["cool_demand_mw", "t_outdoor_c"])).toEqual([blue, aqua]);
    expect(seriesColors(["a", "b", "c"])).toEqual([blue, orange, aqua]);
  });
});
