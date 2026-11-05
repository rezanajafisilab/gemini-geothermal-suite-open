import { describe, expect, it } from "vitest";

import type { CostLine, Design } from "../../workbench";
import {
  capexRows,
  cashFlow,
  co2Split,
  costSteps,
  firstNonNegative,
  horizonOf,
  kindMeta,
  kindTotals,
  lcoeOf,
  paybackText,
  prettyText,
  roundToTotal,
  valueAt,
} from "./model";

const line = (item: string, kind: CostLine["kind"], eur: number, meur = 0): CostLine => ({ item, kind, meur_per_year: meur, eur_per_mwh: eur });

// 2D-BO-EC@3000's heat lines as the server sends them (52.10 €/MWh, LCOH 52.1): the surface plant
// twice (per doublet and per MW), the O&M of two units fixed and variable, CO2 in ASCII.
const HEAT = [
  line("Wells", "capital", 15.21, 1.6988),
  line("Surface plant", "capital", 4.11, 0.4591),
  line("Surface plant", "capital", 5.07, 0.5661),
  line("Boiler", "capital", 0.26, 0.0293),
  line("Geothermal O&M", "fixed", 17.89, 1.9973),
  line("Geothermal O&M", "variable", 0.56, 0.0622),
  line("Boiler O&M", "fixed", 0.12, 0.0131),
  line("Boiler O&M", "variable", 0.14, 0.0155),
  line("Electricity: pumps", "electricity", 6.13, 0.6847),
  line("Gas", "gas", 0.06, 0.0068),
  line("CO2: gas", "carbon", 0.01, 0.0015),
  line("CO2: produced gas", "carbon", 2.54, 0.2834),
];

describe("roundToTotal", () => {
  it("rounds so the parts add up to the rounded total", () => {
    const out = roundToTotal([0.15, 0.15, 0.15], 0.45, 1);
    expect(out.reduce((a, b) => a + b, 0)).toBeCloseTo(0.5); // 0.45 rounds to 0.5
    const heat = roundToTotal(
      HEAT.map((l) => l.eur_per_mwh),
      52.1,
    );
    expect(heat.reduce((a, b) => a + b, 0)).toBeCloseTo(52.1, 9);
    // Each label moves by less than one step.
    heat.forEach((v, i) => expect(Math.abs(v - HEAT[i].eur_per_mwh)).toBeLessThan(0.1));
  });

  it("handles negative parts", () => {
    const out = roundToTotal([5.26, -1.13, 2.24], 6.37, 1);
    expect(out.reduce((a, b) => a + b, 0)).toBeCloseTo(6.4, 9);
  });

  it("rounds each on its own when the parts are far from the total", () => {
    expect(roundToTotal([1.04, 2.06], 50, 1)).toEqual([1, 2.1]);
    expect(roundToTotal([], 3)).toEqual([]);
  });
});

describe("costSteps", () => {
  it("makes a waterfall whose labels add up to the LCOH", () => {
    const w = costSteps(HEAT, 52.1);
    expect(w.total).toBe(52.1);
    expect(w.sum).toBeCloseTo(52.1, 9);
    expect(w.steps.reduce((a, s) => a + s.label, 0)).toBeCloseTo(52.1, 9);
    expect(w.steps.map((s) => s.item)).not.toContain("Not itemised");
  });

  it("merges an item sent twice, names the kind of an item with two, and writes CO₂", () => {
    const w = costSteps(HEAT, 52.1);
    expect(w.steps.map((s) => s.item)).toEqual([
      "Wells",
      "Surface plant",
      "Boiler",
      "Geothermal O&M, fixed",
      "Boiler O&M, fixed",
      "Geothermal O&M, variable",
      "Boiler O&M, variable",
      "Electricity: pumps",
      "Gas",
      "CO₂: gas",
      "CO₂: produced gas",
    ]);
    const surface = w.steps.find((s) => s.item === "Surface plant")!;
    expect(surface.raw).toBeCloseTo(9.18, 9);
    expect(surface.meurPerYear).toBeCloseTo(1.0252, 9);
  });

  it("chains each step from the end of the one before", () => {
    const w = costSteps(HEAT, 52.1);
    expect(w.steps[0].start).toBe(0);
    for (let i = 1; i < w.steps.length; i++) expect(w.steps[i].start).toBeCloseTo(w.steps[i - 1].end, 9);
    expect(w.steps[w.steps.length - 1].end).toBeCloseTo(52.1, 9);
    expect(w.domain[0]).toBe(0);
    expect(w.domain[1]).toBeCloseTo(52.1, 9);
  });

  it("groups the lines by kind, keeping the server's order within a kind", () => {
    const w = costSteps([line("Gas", "gas", 10), line("Wells", "capital", 5), line("CO2: gas", "carbon", 2), line("Chiller O&M", "fixed", 1), line("Heat pump", "capital", 3)], 21);
    expect(w.steps.map((s) => s.item)).toEqual(["Wells", "Heat pump", "Chiller O&M", "Gas", "CO₂: gas"]);
  });

  it("leaves out lines of nothing, and names no kind for an item whose other line is left out", () => {
    const w = costSteps([line("Wells", "capital", 10), line("Gas", "gas", 0), line("Boiler O&M", "fixed", 0.5), line("Boiler O&M", "variable", 0.001)], 10.5);
    expect(w.steps.map((s) => s.item)).toEqual(["Wells", "Boiler O&M"]);
  });

  it("adds a step for what the lines don't explain", () => {
    const w = costSteps([line("Wells", "capital", 10), line("Electricity: pumps", "electricity", 5)], 18);
    const last = w.steps[w.steps.length - 1];
    expect(last.item).toBe("Not itemised");
    expect(last.raw).toBeCloseTo(3);
    expect(w.steps.reduce((a, s) => a + s.label, 0)).toBeCloseTo(18, 9);
  });

  it("uses the lines' own sum without a total", () => {
    const w = costSteps([line("Wells", "capital", 10.04), line("Electricity: pumps", "electricity", 5.03)], null);
    expect(w.total).toBeCloseTo(15.07);
    expect(w.steps.reduce((a, s) => a + s.label, 0)).toBeCloseTo(15.1, 9);
  });

  it("widens the range for a negative line", () => {
    const w = costSteps([line("Wells", "capital", 2), line("Heat sold back", "network", -5)], -3);
    expect(w.domain[0]).toBeCloseTo(-3);
    expect(w.domain[1]).toBeCloseTo(2);
  });
});

describe("kinds", () => {
  it("sums the rounded labels by kind, in kind order, adding up to the total", () => {
    const k = kindTotals(costSteps(HEAT, 52.1).steps);
    expect(k.map((x) => x.kind)).toEqual(["capital", "fixed", "variable", "electricity", "gas", "carbon"]);
    expect(k.reduce((a, x) => a + x.value, 0)).toBeCloseTo(52.1, 9);
    // Capital is 24.65 €/MWh as sent; its rounded labels stay within one step of that.
    expect(Math.abs(k[0].value - 24.65)).toBeLessThanOrEqual(0.1 + 1e-9);
  });

  it("names every kind the server sends; one it doesn't know is Other", () => {
    for (const kind of ["capital", "fixed", "variable", "electricity", "gas", "carbon"]) expect(kindMeta(kind).label).not.toBe("Other");
    expect(kindMeta("calibration").label).toBe("Other");
    expect(kindMeta("variable").label).toBe("Variable O&M");
  });

  it("writes the server's ASCII CO2 and arrows properly", () => {
    expect(prettyText("CO2: produced gas")).toBe("CO₂: produced gas");
    expect(prettyText("chillers 4 -> 6.9 MW")).toBe("chillers 4 → 6.9 MW");
    expect(prettyText("CO2price")).toBe("CO2price");
  });
});

describe("lcoeOf", () => {
  const d = (lcoh: number, lcoc: number | null, heat: number, cold: number, lcoe?: number) =>
    ({ economics: { lcoh, lcoc, lcoe }, year: { heat_delivered_gwh: heat, cool_delivered_gwh: cold } }) as unknown as Design;

  it("takes the server's cost of heat and cold together", () => {
    expect(lcoeOf(d(52.1, 36.17, 111.7, 23.7, 49.31))).toBe(49.31);
  });

  it("else weights the costs of heat and of cold by what each delivers", () => {
    expect(lcoeOf(d(52.1, 36.17, 100, 20))).toBeCloseTo((52.1 * 100 + 36.17 * 20) / 120, 9);
    expect(lcoeOf(d(52.1, null, 100, 0))).toBeCloseTo(52.1, 9);
    expect(lcoeOf(d(52.1, null, 100, 20))).toBeNull();
    expect(lcoeOf(d(52.1, 36.17, 0, 0))).toBeNull();
  });
});

describe("capexRows", () => {
  it("sorts the items largest first with size × unit cost, one unit in the singular, and the life", () => {
    const rows = capexRows([
      { item: "Surface plant (per MW)", size: 24.658, unit: "MW", meur_per_unit: 0.345, meur: 8.507, life_years: 30 },
      { item: "Wells", size: 4, unit: "wells", meur_per_unit: 6.38, meur: 25.53, life_years: 30 },
      { item: "Surface plant", size: 1, unit: "doublets", meur_per_unit: 3.45, meur: 3.45, life_years: 30 },
      { item: "Boiler", size: 5.4, unit: "MW", meur_per_unit: 0.075, meur: 0.405 },
    ]);
    expect(rows.map((r) => r.item)).toEqual(["Wells", "Surface plant (per MW)", "Surface plant", "Boiler"]);
    expect(rows[0].detail).toBe("4 wells × 6.38 M€ per well");
    expect(rows[1].detail).toBe("24.66 MW × 0.345 M€/MW");
    expect(rows[2].detail).toBe("1 doublet × 3.45 M€ per doublet");
    expect(rows[0].life).toBe(30);
    expect(rows[3].life).toBeNull();
    expect(rows.reduce((a, r) => a + r.share, 0)).toBeCloseTo(1);
  });

  it("keeps items that come more than once apart: wells with their notes, trains numbered, keys unique", () => {
    const rows = capexRows([
      { item: "Wells", size: 3, unit: "wells", meur_per_unit: 5.48, meur: 16.44, life_years: 30, note: "1 producer(s), 2 injector(s), priced at 2,500 m TVD" },
      { item: "Wells", size: 1, unit: "wells", meur_per_unit: 5.2, meur: 5.2, life_years: 30, note: "1 producer(s), 0 injector(s), priced at 2,450 m TVD" },
      { item: "Treatment trains", size: 1, unit: "trains", meur_per_unit: 0.6, meur: 0.6, life_years: 30 },
      { item: "Treatment trains", size: 1, unit: "trains", meur_per_unit: 0.6, meur: 0.6, life_years: 30 },
      { item: "Boiler", size: 5.4, unit: "MW", meur_per_unit: 0.075, meur: 0.405 },
    ]);
    expect(new Set(rows.map((r) => r.key)).size).toBe(5);
    expect(rows.map((r) => [r.item, r.note])).toEqual([
      ["Wells", "1 producer(s), 2 injector(s), priced at 2,500 m TVD"],
      ["Wells", "1 producer(s), 0 injector(s), priced at 2,450 m TVD"],
      ["Treatment trains", "1 of 2"],
      ["Treatment trains", "2 of 2"],
      ["Boiler", null],
    ]);
    expect(rows[2].detail).toBe("1 train × 0.6 M€ per train");
    expect(rows.reduce((a, r) => a + r.meur, 0)).toBeCloseTo(23.245, 6);
  });
});

describe("cashFlow", () => {
  const flow = [-21.692, -18.903, -16.254, -13.736, -11.344, -9.07, -6.91, -4.86, -2.91, -1.06, 0.7, 2.37];

  it("finds the payback year and the crossing", () => {
    const c = cashFlow({ extra_capex_meur: 21.69, savings_meur_per_year: 2.9, payback_years: 10, npv_meur: 2.37, cash_flow_meur: flow });
    expect(c.payback).toBe(10);
    expect(c.crossing).toBeGreaterThan(9);
    expect(c.crossing).toBeLessThan(10);
    expect(c.npv).toBe(2.37);
    expect(c.min).toBe(-21.692);
    expect(c.points[1].delta).toBeCloseTo(2.789);
  });

  it("works the payback out when the server leaves it out, and says never when it never does", () => {
    expect(firstNonNegative(flow)).toBe(10);
    const never = cashFlow({ extra_capex_meur: 16, savings_meur_per_year: 1, payback_years: null, npv_meur: -1.47, cash_flow_meur: [-16, -10, -5, -1.47] });
    expect(never.payback).toBeNull();
    expect(never.crossing).toBeNull();
    expect(never.max).toBe(0);
  });

  it("runs over the server's horizon", () => {
    expect(horizonOf({ extra_capex_meur: 1, savings_meur_per_year: 1, payback_years: 1, npv_meur: 1, cash_flow_meur: Array.from({ length: 31 }, (_, i) => i - 1) })).toBe(30);
    expect(horizonOf(null)).toBeNull();
  });
});

describe("a fractional payback", () => {
  const pts = [-10, -4, 2, 8].map((value, year) => ({ year, value }));

  it("interpolates the value between years", () => {
    expect(valueAt(pts, 1.5)).toBeCloseTo(-1);
    expect(valueAt(pts, 2)).toBe(2);
    expect(valueAt(pts, 3)).toBe(8);
    expect(valueAt(pts, 3.5)).toBeNull();
    expect(valueAt(pts, -1)).toBeNull();
  });

  it("reads as a year or a number of years", () => {
    expect(paybackText(10)).toBe("in year 10");
    expect(paybackText(7.7)).toBe("after 7.7 years");
  });
});

describe("co2Split", () => {
  // 2D-BO-EC@3000's year as the server sends it.
  const year = {
    co2_t: { purchased_gas: 19.8, produced_gas: 3835.2, electricity: 1358.1, total: 5213.2 },
    electricity_gwh: { hp: 0, recovery_hp: 0, chillers: 2.773, pumps: 3.687, towers: 0.331 },
  };
  const design = (y: object) => ({ year: y, economics: {} }) as unknown as Design;

  it("splits the CO₂ into gas bought, gas from the brine and each use of grid power", () => {
    const s = co2Split(design(year))!;
    expect(s.sources.map((x) => x.item)).toEqual(["Gas bought for the boiler", "Gas from the brine", "Well pumps", "Electric chillers", "Cooling towers"]);
    expect(s.total).toBeCloseTo(5213.1, 6);
    expect(s.gas).toBeCloseTo(3855, 6);
    expect(s.grid).toBe(1358.1);
    const pumps = s.sources.find((x) => x.key === "pumps")!;
    expect(pumps.t).toBeCloseTo((1358.1 * 3.687) / 6.791, 6);
    expect(pumps).toMatchObject({ fuel: "grid", color: "#C24E1C" });
    expect(s.sources[1]).toMatchObject({ fuel: "brine" });
  });

  it("counts the heat pump's power, and power it can't name", () => {
    const s = co2Split(design({ co2_t: { purchased_gas: 0, produced_gas: 0, electricity: 100 }, electricity_gwh: { hp: 3, recovery_hp: 1, pumps: 4, heaters: 2 } }))!;
    expect(s.sources.map((x) => [x.item, Math.round(x.t)])).toEqual([
      ["Well pumps", 40],
      ["Heat pump", 40],
      ["Other electricity", 20],
    ]);
  });

  it("reads the economics' breakdown when the year has none, and draws nothing without one", () => {
    const fromEconomics = { year: {}, economics: { co2_t: { purchased_gas: 10, produced_gas: 0, electricity: 0 } } } as unknown as Design;
    expect(co2Split(fromEconomics)!.sources.map((x) => x.key)).toEqual(["purchased_gas"]);
    expect(co2Split(design({}))).toBeNull();
    expect(co2Split(design({ co2_t: { purchased_gas: 0, produced_gas: 0, electricity: 0, total: 0 } }))).toBeNull();
  });
});
