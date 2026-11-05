// The Sensitivity tab's rules: the default picks, the discount rate shown in % and sent as a
// fraction, the request built from the picks, the cache key, the colour slots, and the result
// reshaped (tornado by swing, spider positions −100…+100, shares of the swing).

import { describe, expect, it } from "vitest";

import type { SensOutput, SensParam, Sensitivity } from "../../workbench";
import {
  assignSlots,
  baseVerdict,
  buildRequest,
  configKey,
  defaultSelection,
  displayUnit,
  fmtOut,
  fmtParam,
  isDefaultRange,
  isFractionPercent,
  keepKnown,
  lowerFirst,
  newRow,
  outputName,
  paramGroups,
  parseNum,
  rangePosition,
  rowError,
  runCount,
  shareBelow,
  spiderLines,
  swingShares,
  toDisplay,
  toSent,
  toggleRow,
  tornadoRows,
} from "./params";

const P = (key: string, label: string, unit: string, group: SensParam["group"], low: number, high: number, kind: SensParam["kind"]): SensParam => ({
  key,
  label,
  unit,
  group,
  low,
  high,
  kind,
  description: "",
});

// The server's catalogue (src/gemini_agent/workbench.py PARAMETERS).
const LIVE: SensParam[] = [
  P("heat_return", "Heating return temperature", "°C", "demand", 45, 70, "absolute"),
  P("cool_return", "Cooling return temperature", "°C", "demand", 22, 30, "absolute"),
  P("reservoir_temp", "Reservoir temperature", "°C", "subsurface", -10, 5, "delta"),
  P("permeability", "Permeability", "mD", "subsurface", 100, 300, "absolute"),
  P("depth", "Doublet depth", "m", "subsurface", 2000, 3500, "absolute"),
  P("operating_days", "Operating days per doublet", "days", "subsurface", 300, 365, "absolute"),
  P("heat_demand", "Heat demand", "×", "demand", 0.8, 1.2, "scale"),
  P("cool_demand", "Cooling demand", "×", "demand", 0.8, 1.2, "scale"),
  P("gas_price", "Gas price", "€/MWh", "prices", 25, 70, "absolute"),
  P("electricity_price", "Electricity price", "€/MWh", "prices", 80, 220, "absolute"),
  P("carbon_price", "CO₂ price", "€/t", "prices", 0, 150, "absolute"),
  P("capex", "Capital costs", "×", "costs", 0.8, 1.3, "scale"),
  P("discount_rate", "Discount rate", "", "costs", 0.03, 0.08, "absolute"),
];

// A catalogue with other keys (the discount rate already in %).
const OTHER_KEYS: SensParam[] = [
  P("reservoir_delta_c", "Reservoir temperature", "°C", "subsurface", -10, 5, "delta"),
  P("return_c", "Heating return temperature", "°C", "demand", 45, 70, "absolute"),
  P("electricity_eur_per_mwh", "Electricity price", "€/MWh", "prices", 60, 160, "absolute"),
  P("gas_eur_per_mwh", "Gas", "€/MWh", "prices", 25, 70, "absolute"),
  P("discount_rate", "Discount rate", "%", "costs", 3, 9, "absolute"),
  P("well_capex_scale", "Well cost", "×", "costs", 0.7, 1.5, "scale"),
];

const rate = LIVE.find((p) => p.key === "discount_rate")!;
const byKey = (key: string) => LIVE.find((p) => p.key === key)!;

describe("the default picks", () => {
  it("are the heating return, the reservoir temperature, electricity and gas prices and capital costs", () => {
    expect(defaultSelection(LIVE)).toEqual(["heat_return", "reservoir_temp", "electricity_price", "gas_price", "capex"]);
  });

  it("are found by label in a catalogue with other keys", () => {
    expect(defaultSelection(OTHER_KEYS)).toEqual(["return_c", "reservoir_delta_c", "electricity_eur_per_mwh", "gas_eur_per_mwh", "well_capex_scale"]);
  });

  it("skip what the catalogue doesn't have", () => {
    expect(defaultSelection(LIVE.filter((p) => p.key !== "heat_return"))).toEqual(["reservoir_temp", "electricity_price", "gas_price", "capex"]);
  });
});

describe("the catalogue", () => {
  it("groups the parameters in a fixed order, a group the client doesn't know by its own name", () => {
    const groups = paramGroups([...LIVE, P("pump_eff", "Pump efficiency", "", "equipment", 0.6, 0.8, "absolute"), P("grid_co2", "Grid CO₂", "t/MWh", "emissions", 0.1, 0.3, "absolute")]);
    expect(groups.map((g) => g.label)).toEqual(["Subsurface", "Demand", "Prices", "Costs", "Equipment", "Emissions"]);
    expect(groups[1].params.map((p) => p.key)).toEqual(["heat_return", "cool_return", "heat_demand", "cool_demand"]);
  });

  it("drops picks it no longer has, keeping the rest as they were", () => {
    const outputs: SensOutput[] = [
      { key: "lcoh", label: "Cost of heat", unit: "€/MWh" },
      { key: "lcoe", label: "Cost of heat and cold", unit: "€/MWh" },
      { key: "violations", label: "Caps broken", unit: "" },
    ];
    const picks = { rows: [newRow(byKey("reservoir_temp")), { key: "transmissivity", low: "10", high: "60" }], outputs: ["lcoe", "supply_temp"], mc: { on: true, samples: 200 } };
    const kept = keepKnown(picks, { parameters: LIVE, outputs });
    expect(kept.rows.map((r) => r.key)).toEqual(["reservoir_temp"]);
    expect(kept.outputs).toEqual(["lcoe"]);
    expect(kept.mc).toBe(picks.mc);
    expect(keepKnown({ ...picks, outputs: ["npv"] }, { parameters: LIVE, outputs }).outputs).toEqual(["lcoh"]);
    const fine = { rows: [newRow(byKey("gas_price"))], outputs: ["lcoh", "violations"] };
    expect(keepKnown(fine, { parameters: LIVE, outputs })).toBe(fine);
  });
});

describe("percent and fraction", () => {
  it("shows a fraction-valued rate in %", () => {
    expect(isFractionPercent(rate)).toBe(true);
    expect(displayUnit(rate)).toBe("%");
    expect(toDisplay(rate, 0.0525)).toBe(5.25);
    expect(toSent(rate, 5.25)).toBe(0.0525);
    expect(toSent(rate, 3)).toBe(0.03);
    expect(newRow(rate)).toEqual({ key: "discount_rate", low: "3", high: "8" });
    expect(fmtParam(rate, 0.0525)).toBe("5.25%");
  });

  it("leaves a rate already in % alone", () => {
    const fx = OTHER_KEYS.find((p) => p.key === "discount_rate")!;
    expect(isFractionPercent(fx)).toBe(false);
    expect(toSent(fx, 5)).toBe(5);
    expect(newRow(fx)).toEqual({ key: "discount_rate", low: "3", high: "9" });
  });

  it("formats changes with a sign, scales with ×, values with their unit", () => {
    expect(fmtParam(byKey("reservoir_temp"), -10)).toBe("−10 °C");
    expect(fmtParam(byKey("reservoir_temp"), 5)).toBe("+5 °C");
    expect(fmtParam(byKey("heat_demand"), 0.8)).toBe("0.8×");
    expect(fmtParam(byKey("electricity_price"), 150)).toBe("150 €/MWh");
    expect(fmtParam(byKey("permeability"), 200)).toBe("200 mD");
    expect(fmtParam(byKey("heat_return"), 60)).toBe("60 °C");
    expect(newRow(byKey("reservoir_temp"))).toEqual({ key: "reservoir_temp", low: "−10", high: "5" });
    expect(newRow(byKey("heat_return"))).toEqual({ key: "heat_return", low: "45", high: "70" });
  });
});

describe("typing a range", () => {
  it("reads minus signs and commas", () => {
    expect(parseNum("−10")).toBe(-10);
    expect(parseNum("-2.5")).toBe(-2.5);
    expect(parseNum("0,8")).toBe(0.8);
    expect(parseNum(" 3 ")).toBe(3);
    expect(parseNum("")).toBeNull();
    expect(parseNum("abc")).toBeNull();
    expect(parseNum("1.2.3")).toBeNull();
  });

  it("wants low below high", () => {
    expect(rowError({ key: "x", low: "1", high: "2" })).toBeNull();
    expect(rowError({ key: "x", low: "2", high: "2" })).toMatch(/below/);
    expect(rowError({ key: "x", low: "", high: "2" })).toMatch(/number/);
  });

  it("knows a changed range from the catalogue's", () => {
    expect(isDefaultRange(rate, newRow(rate))).toBe(true);
    expect(isDefaultRange(rate, { key: "discount_rate", low: "4", high: "8" })).toBe(false);
  });

  it("adds and removes parameters, keeping the order picked", () => {
    let rows = toggleRow([], byKey("electricity_price"));
    rows = toggleRow(rows, byKey("reservoir_temp"));
    expect(rows.map((r) => r.key)).toEqual(["electricity_price", "reservoir_temp"]);
    rows = toggleRow(rows, byKey("electricity_price"));
    expect(rows.map((r) => r.key)).toEqual(["reservoir_temp"]);
  });
});

describe("the request", () => {
  const rows = [newRow(byKey("reservoir_temp")), { key: "discount_rate", low: "4", high: "7.5" }];

  it("sends the ranges in the server's units, the rate as a fraction", () => {
    const req = buildRequest("t1", "A1", LIVE, rows, ["lcoe", "violations"], { on: true, samples: 200 });
    expect(req).toEqual({
      threadId: "t1",
      design: "A1",
      parameters: [
        { key: "reservoir_temp", low: -10, high: 5 },
        { key: "discount_rate", low: 0.04, high: 0.075 },
      ],
      outputs: ["lcoe", "violations"],
      samples: 200,
    });
  });

  it("sends no samples without Monte Carlo and keeps samples within 50..500", () => {
    expect(buildRequest("t1", "A1", LIVE, rows, ["lcoh"], { on: false, samples: 200 })!.samples).toBe(0);
    expect(buildRequest("t1", "A1", LIVE, rows, ["lcoh"], { on: true, samples: 900 })!.samples).toBe(500);
    expect(buildRequest("t1", "A1", LIVE, rows, ["lcoh"], { on: true, samples: 10 })!.samples).toBe(50);
  });

  it("is null while a range is wrong or nothing is picked", () => {
    expect(buildRequest("t1", "A1", LIVE, [{ key: "reservoir_temp", low: "5", high: "−5" }], ["lcoh"], { on: false, samples: 0 })).toBeNull();
    expect(buildRequest("t1", "A1", LIVE, [], ["lcoh"], { on: false, samples: 0 })).toBeNull();
    expect(buildRequest("t1", "A1", LIVE, rows, [], { on: false, samples: 0 })).toBeNull();
  });

  it("gives the same cache key whatever the order picked, another for another range", () => {
    const a = buildRequest("t1", "A1", LIVE, rows, ["lcoh", "npv_meur"], { on: true, samples: 200 })!;
    const b = buildRequest("t1", "A1", LIVE, [...rows].reverse(), ["npv_meur", "lcoh"], { on: true, samples: 200 })!;
    const c = buildRequest("t1", "A1", LIVE, [newRow(byKey("reservoir_temp")), newRow(rate)], ["lcoh", "npv_meur"], { on: true, samples: 200 })!;
    expect(configKey(a)).toBe(configKey(b));
    expect(configKey(a)).not.toBe(configKey(c));
    expect(configKey(a, "v1")).not.toBe(configKey(a, "v2"));
  });
});

describe("colour slots", () => {
  it("keep each parameter's slot when others come and go", () => {
    const s1 = assignSlots({}, ["a", "b", "c"]);
    expect(s1).toEqual({ a: 0, b: 1, c: 2 });
    const s2 = assignSlots(s1, ["a", "c"]);
    expect(s2).toEqual({ a: 0, c: 2 });
    const s3 = assignSlots(s2, ["a", "c", "d"]);
    expect(s3).toEqual({ a: 0, c: 2, d: 1 });
  });
});

describe("the result, reshaped", () => {
  const result: Sensitivity = {
    design: "A1",
    seconds: 1.7,
    runs: 31,
    base: { lcoh: 42.4, heat_coverage: 100 },
    tornado: [
      { key: "capex", label: "Capital costs", low: { lcoh: 35.8, heat_coverage: 100 }, high: { lcoh: 52.1, heat_coverage: 100 } },
      { key: "reservoir_temp", label: "Reservoir temperature", low: { lcoh: 68.4, heat_coverage: 96 }, high: { lcoh: 40.5, heat_coverage: 100 } },
      { key: "permeability", label: "Permeability", low: { lcoh: 42.7, heat_coverage: 99 }, high: { lcoh: 41.6, heat_coverage: 100 } },
    ],
    spider: [
      {
        key: "reservoir_temp",
        points: [-10, -5, 0, 5, 10].map((x, i) => ({ x, values: { lcoh: [68.4, 44.3, 42.4, 41.3, 40.5][i], heat_coverage: 100 } })),
      },
      {
        key: "discount_rate",
        points: [0.03, 0.0425, 0.055, 0.0675, 0.08].map((x) => ({ x, values: { lcoh: 40 + x * 100 } })),
      },
    ],
    monte_carlo: null,
  };

  it("sorts the tornado by the swing of the output shown", () => {
    expect(tornadoRows(result, "lcoh").map((r) => r.key)).toEqual(["reservoir_temp", "capex", "permeability"]);
    const top = tornadoRows(result, "lcoh")[0];
    expect(top.swing).toBeCloseTo(27.9);
    expect(top.base).toBe(42.4);
    expect(tornadoRows(result, "heat_coverage").map((r) => r.key)).toEqual(["reservoir_temp", "permeability", "capex"]);
  });

  it("puts each parameter's range on −100…+100", () => {
    expect(rangePosition(-10, -10, 10)).toBe(-100);
    expect(rangePosition(0, -10, 10)).toBe(0);
    expect(rangePosition(10, -10, 10)).toBe(100);
    expect(rangePosition(1500, 1500, 3500)).toBe(-100);
    expect(rangePosition(3000, 1500, 3500)).toBe(50);
    expect(rangePosition(5, 5, 5)).toBe(0);
    const lines = spiderLines(result, "lcoh");
    expect(lines.map((l) => l.points.map((p) => p.pos))).toEqual([
      [-100, -50, 0, 50, 100],
      [-100, -50, 0, 50, 100],
    ]);
    expect(lines[0].label).toBe("Reservoir temperature");
    expect(lines[1].points[0]).toEqual({ pos: -100, x: 0.03, y: 43 });
    // An output a parameter's points don't have leaves that line out.
    expect(spiderLines(result, "heat_coverage").map((l) => l.key)).toEqual(["reservoir_temp"]);
  });

  it("shares out each output's swing", () => {
    const s = swingShares(result, ["lcoh", "heat_coverage"]);
    const sum = Object.values(s.lcoh).reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1);
    expect(s.lcoh.reservoir_temp).toBeGreaterThan(s.lcoh.capex);
    expect(s.heat_coverage.capex).toBe(0);
  });

  it("lowercases labels for questions, but not CO₂ or NPV", () => {
    expect(lowerFirst("Reservoir temperature")).toBe("reservoir temperature");
    expect(lowerFirst("CO₂ price")).toBe("CO₂ price");
    expect(lowerFirst("NPV against gas")).toBe("NPV against gas");
  });
});

describe("the outputs", () => {
  it("read in a sentence, a count as a number of", () => {
    expect(outputName({ key: "lcoe", label: "Cost of heat and cold", unit: "€/MWh" })).toBe("cost of heat and cold");
    expect(outputName({ key: "violations", label: "Caps broken", unit: "" })).toBe("number of caps broken");
    expect(outputName({ key: "co2_saving_pct", label: "CO₂ saving against gas", unit: "%" })).toBe("CO₂ saving against gas");
  });

  it("format with their unit, a count without one", () => {
    expect(fmtOut({ key: "lcoe", label: "Cost of heat and cold", unit: "€/MWh" }, 49.31)).toBe("49.3 €/MWh");
    expect(fmtOut({ key: "co2_saving_pct", label: "CO₂ saving against gas", unit: "%" }, 78.6)).toBe("78.6%");
    expect(fmtOut({ key: "violations", label: "Caps broken", unit: "" }, 2)).toBe("2");
    expect(fmtOut(undefined, null)).toBe("–");
  });

  it("know which way is better, the new ones too", () => {
    const h = { edges: [0, 1, 2, 3], counts: [60, 30, 10] };
    // Most samples break fewer caps than a base of 2: the uncertainty works for the design.
    expect(baseVerdict(h, 2, "violations")).toMatchObject({ leaning: "better" });
    expect(baseVerdict(h, 0.5, "lcoe")).toMatchObject({ leaning: "worse" });
  });
});

describe("Monte Carlo in words", () => {
  const h = { edges: [30, 40, 50, 60], counts: [10, 60, 30] };

  it("reads the share below a value off the histogram", () => {
    expect(shareBelow(h, 30)).toBe(0);
    expect(shareBelow(h, 40)).toBeCloseTo(0.1);
    expect(shareBelow(h, 45)).toBeCloseTo(0.4);
    expect(shareBelow(h, 99)).toBe(1);
  });

  it("says whether the uncertainty works against the design", () => {
    // A cost: most samples above the base is bad news.
    expect(baseVerdict(h, 38, "lcoh")).toMatchObject({ leaning: "worse" });
    expect(baseVerdict(h, 55, "lcoh")).toMatchObject({ leaning: "better" });
    // A saving: most samples above the base is good news.
    expect(baseVerdict(h, 38, "co2_saving_pct")).toMatchObject({ leaning: "better" });
    expect(baseVerdict(h, 45, "lcoh")).toMatchObject({ leaning: "even" });
  });
});

describe("the runs a request costs", () => {
  it("counts the base, five per parameter and the samples, as the server does", () => {
    // The server reported 226 model runs for five parameters and 200 samples.
    expect(runCount(5, 200)).toEqual({ base: 1, ends: 10, inside: 15, samples: 200, total: 226 });
    expect(runCount(1, 0).total).toBe(6);
    expect(runCount(0, 0).total).toBe(1);
  });
});
