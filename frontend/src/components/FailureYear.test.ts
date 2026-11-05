// Failures over a year on the failure card: the expected cost as sent, a bar per unit (parts
// stacked), the spare ESP's verdict as a chip, and units too small to draw counted, not drawn.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { FailureView, FailureYear } from "../agent/types";
import { FailureCard } from "./FailureCard";
import { FailureYearStrip, unitTitle } from "./FailureYear";

const unit = (over: Partial<FailureYear["units"][number]>): FailureYear["units"][number] => ({
  unit: "heat pump",
  label: "Heat pump",
  words: "the heat pump",
  failures_per_year: 0.046,
  repair_days: 0.604,
  out_days: 0.028,
  running_keur: 0.05,
  lost_mwh: 0,
  lost_keur: 0,
  repair_keur: 0,
  total_keur: 0.05,
  ...over,
});

const year: FailureYear = {
  total_keur: 982,
  range_keur: [393, 1964.3],
  lost_mwh: 1285.6,
  lost_heat_mwh: 1284,
  lost_cold_mwh: 1.5,
  lost_eur_per_mwh: 122,
  stress_keur: 13681,
  stress_eur_per_mwh: 10000,
  with_spare_keur: 222.4,
  with_spare_mwh: 77.3,
  units: [
    unit({ unit: "doublet 1", label: "ESP, doublet 1", words: "the ESP of doublet 1", failures_per_year: 0.5, repair_days: 120, out_days: 60, running_keur: 650.19, lost_mwh: 1283.17, lost_keur: 156.55, repair_keur: 175, total_keur: 981.73 }),
    unit({}),
  ],
  spare_esp: {
    per_year: 0.5,
    swap_days: 7,
    no_spare_days: 120,
    price_meur: 0.3,
    life_years: 30,
    yearly_keur: 20,
    saving_keur: 759.7,
    saving_mwh: 1208.3,
    net_keur: 739.7,
    worth: true,
    break_even_per_year: 0.0131,
    stress_net_keur: 12675.5,
    range: { low: { per_year: 0.2, net_keur: 283.9 }, high: { per_year: 1, net_keur: 1499.4 } },
    every: "once every 2 years",
    break_even_every: "once every 76 years",
  },
  skipped: ["the shared treatment train"],
  notes: [],
};

describe("failures over a year", () => {
  const html = renderToStaticMarkup(createElement(FailureYearStrip, { value: year }));

  it("shows the expected cost, its range and the cost with a spare", () => {
    expect(html).toContain("Failures over a year");
    expect(html).toContain("982 <span class=\"tile-unit\">k€/yr</span>");
    expect(html).toContain("393–1,964 k€ over the failure rates · 222 k€ with a spare");
  });

  it("shows the heat and cold not delivered, its value and the stress line", () => {
    expect(html).toContain("1,286 <span class=\"tile-unit\">MWh/yr</span>");
    expect(html).toContain("valued at 122 €/MWh (lost sale) · 13,681 k€/yr at 10,000 €/MWh");
  });

  it("gives the spare ESP's verdict as a chip", () => {
    expect(html).toContain('class="tag tag-ok"');
    expect(html).toContain(">Spare ESP pays<");
    expect(html).toContain("+740 <span class=\"tile-unit\">k€/yr</span>");
    expect(html).toContain("more often than once every 76 years; taken: once every 2 years");
  });

  it("draws a bar per unit with its parts stacked, and counts the small ones", () => {
    expect(html.match(/class="fy-row"/g)?.length).toBe(1);
    expect(html).toContain("ESP, doublet 1");
    expect(html).toContain('class="fy-seg fy-running" style="width:66.2');
    expect(html).toContain("1 more unit under 0.5 k€ a year each.");
    expect(html).toContain("No failure data, not counted: the shared treatment train.");
    expect(html).toContain("heat and cold not delivered");
  });

  it("a bar's title says its parts and how often the unit fails", () => {
    expect(unitTitle(year.units[0])).toBe(
      "ESP, doublet 1: 982 k€ a year (gas, power and CO₂ 650, heat and cold not delivered 157, repairs 175); 0.5 failures a year, out 120 days each",
    );
    expect(unitTitle(year.units[1])).toContain("out 14 h each");
  });

  it("a spare not worth it gets an amber chip", () => {
    const no = { ...year, spare_esp: { ...year.spare_esp!, worth: false, net_keur: -12 } };
    const out = renderToStaticMarkup(createElement(FailureYearStrip, { value: no }));
    expect(out).toContain('class="tag tag-amber"');
    expect(out).toContain("Spare ESP not worth it");
    expect(out).toContain("−12");
  });

  it("the failure card shows the strip when the agent sent it", () => {
    const v: FailureView = {
      design: "A9 · 1D-HP-AB",
      code: "1D-HP-AB",
      events: [{ unit: "doublet 1", words: "doublet 1 (its producer or ESP)", first: 9, last: 23, from: "10 Jan", to: "24 Jan", days: 15, how: "asked", assumed: "" }],
      failed: {
        heat: { days_short: 15, worst_mw: 6, worst_day: "22 Jan", short_gwh: 1.69 },
        cool: { days_short: 0, worst_mw: 0, worst_day: null, short_gwh: 0 },
        days: [],
        boiler_full: true,
        extra_gas_gwh: 2.41,
        extra_co2_t: 242,
        extra_cost_keur: 120,
      },
      needed: true,
      remedies: [],
      best: null,
    };
    expect(renderToStaticMarkup(createElement(FailureCard, { value: v }))).not.toContain("Failures over a year");
    expect(renderToStaticMarkup(createElement(FailureCard, { value: { ...v, yearly: year } }))).toContain("Failures over a year");
  });
});
