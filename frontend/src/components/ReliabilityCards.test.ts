// The cards for picks, firm capacity, a what-if's new search, failures and side-by-side tables:
// they show the agent's figures as sent, and mark what the agent marked.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { CompareView, FailureView, ResultCard as Card } from "../agent/types";
import { CompareCard } from "./CompareCard";
import { FailureCard } from "./FailureCard";
import { ResultCard, compactFigures } from "./ResultCard";

const base: Card = {
  alternative: "1D-HP-EC-N1",
  uid: "A1",
  name: "1 doublet at 2,500 m, heat pump top-up with a backup boiler, electric chillers",
  verified: true,
  checks: { passed: 11, total: 11 },
  kpis: [
    { id: "lcoe", label: "Cost of heat and cold", value: 69.8, unit: "€/MWh" },
    { id: "heat_coverage", label: "Heat covered", value: 100, unit: "%" },
    { id: "cool_coverage", label: "Cold covered", value: 100, unit: "%" },
    { id: "lcoh", label: "Cost of heat", value: 75.7, unit: "€/MWh" },
    { id: "lcoc", label: "Cost of cold", value: 42.1, unit: "€/MWh" },
  ],
  heat_split_gwh: { geo: 40 },
  cool_split_gwh: { chill: 23.7 },
  sizes_mw: {},
  picks: [
    { key: "best", label: "best overall", uid: "A1", code: "1D-HP-EC-N1", id: "A1 · 1D-HP-EC-N1", chosen: true, lcoe: 69.8, lcoh: 75.7, lcoc: 42.1, co2_t: 14103, co2_saving_pct: 42.1, capex_meur: 31.1, reliable: true, n1_short: 0, rule: "best" },
    { key: "cost", label: "cheapest", uid: "A9", code: "1D-HP-AB", id: "A9 · 1D-HP-AB", chosen: false, lcoe: 68.13, lcoh: 72.3, lcoc: 50, co2_t: 14334, co2_saving_pct: 41, capex_meur: 29.5, reliable: false, n1_short: 5, rule: "cost" },
  ],
  firm: {
    peak: { heat: { day: "28 Jan", demand_mw: 30, capacity_mw: 40.4, spare_mw: 10.4 } },
    cases: [{ unit: "doublet 1", short: false, side: "heat", worst_mw: 0, worst_day: null, days_short: 0, short_gwh: 0 }],
    short: 0,
    reliable: true,
    boiler_units: 3,
    chiller_units: 3,
  },
};

describe("names, picks and firm capacity", () => {
  const html = renderToStaticMarkup(createElement(ResultCard, { card: base }));

  it("leads with the design's name and the cost of heat and cold", () => {
    expect(html).toContain('class="uid-chip"');
    expect(html).toContain(">A1<");
    expect(html.indexOf("Cost of heat and cold")).toBeLessThan(html.indexOf("Heat covered"));
    expect(html).toContain("heat 75.7 · cold 42.1 €/MWh");
  });

  it("shows each pick with its cost and whether one unit can be out", () => {
    expect(html).toContain("best overall");
    expect(html).toContain("recommended");
    expect(html).toContain("one unit out: 5 cases short");
    expect(html).toContain("any one unit out: met");
  });

  it("says the spare on the peak day and that every case is met", () => {
    expect(html).toContain("+10.4 MW");
    expect(html).toContain("all 1 cases met every day (boiler 3 units, chillers 3 units)");
  });

  it("a what-if says whether the pick changes", () => {
    const what: Card = {
      ...base,
      view: "compact",
      against: base,
      picks: [],
      research: { code: "2D-HP-EC-N1", uid: "B1", id: "B1 · 2D-HP-EC-N1", lcoe: 72.3, base_code: "1D-HP-EC-N1", base_id: "A1 · 1D-HP-EC-N1", changed: true, objective: "best" },
    };
    const out = renderToStaticMarkup(createElement(ResultCard, { card: what }));
    expect(out).toContain("The pick changes");
    expect(out).toContain("B1 · 2D-HP-EC-N1");
    expect(compactFigures(what)[1].label).toBe("Cost of heat and cold");
  });
});

describe("failure and comparison cards", () => {
  it("a failure shows the shortfall, the remedies and marks the cheapest that covers it", () => {
    const v: FailureView = {
      design: "A9 · 1D-HP-AB",
      code: "1D-HP-AB",
      events: [{ unit: "doublet 1", words: "doublet 1 (its producer or ESP)", first: 9, last: 23, from: "10 Jan", to: "24 Jan", days: 15, how: "asked", assumed: "" }],
      failed: {
        heat: { days_short: 15, worst_mw: 6, worst_day: "22 Jan", short_gwh: 1.69 },
        cool: { days_short: 0, worst_mw: 0, worst_day: null, short_gwh: 0 },
        days: [{ day: "10 Jan", heat_demand_mw: 25, heat_short_mw: 3, boiler_mw: 20.8, cool_short_mw: 0 }],
        boiler_full: true,
        extra_gas_gwh: 2.41,
        extra_co2_t: 242,
        extra_cost_keur: 120,
      },
      needed: true,
      remedies: [
        { key: "boiler", name: "6.1 MW more boiler", heat_short_mw: 0, cool_short_mw: 0, short_gwh: 0, covers: true, capex_meur: 0.46, yearly_keur: 47, lcoe_delta: 0.35 },
        { key: "spare_esp", name: "a spare ESP on the shelf", heat_short_mw: 4.2, cool_short_mw: 0, short_gwh: 0.25, covers: false, capex_meur: 0.24, yearly_keur: 13 },
      ],
      best: "boiler",
    };
    const out = renderToStaticMarkup(createElement(FailureCard, { value: v }));
    expect(out).toContain("A spare or backup is needed");
    expect(out).toContain("15 days short");
    expect(out).toContain("cheapest that covers it");
    expect(out).toContain("still 4.2 MW short at worst");
  });

  it("a comparison marks the best of each row as sent", () => {
    const v: CompareView = {
      designs: [
        { id: "A9 · 1D-HP-AB", code: "1D-HP-AB", name: "", picks: ["cost"], reliable: false },
        { id: "A2 · 1D-HP-AB-N1", code: "1D-HP-AB-N1", name: "", picks: ["reliable"], reliable: true },
      ],
      rows: [{ key: "lcoe", label: "Cost of heat and cold", unit: "€/MWh", digits: 1, values: [68.1, 69.8], best: 0 }],
    };
    const out = renderToStaticMarkup(createElement(CompareCard, { value: v }));
    expect(out).toContain('<td class="best">68.1</td>');
    expect(out).toContain("cheapest reliable");
  });
});
