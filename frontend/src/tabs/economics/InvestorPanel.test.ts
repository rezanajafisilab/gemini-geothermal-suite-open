// The investor's section: it shows the server's figures as sent (tiles, SDE++ card, cash flow,
// inputs), stacks each year's money in above the line and out below, and turns typed sale prices
// into the PUT /api/assumptions patch.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ApiResult, Design, Investor, InvestorFlow, Workbench } from "../../workbench";
import { ChoicesPanel, InvestorSection, InvestorTiles, SdePanel, salePatch, stackYear } from "./InvestorPanel";

const flow = (year: number, over: Partial<InvestorFlow> = {}): InvestorFlow => ({
  year,
  revenue_heat: year ? 10.3 : 0,
  revenue_cold: year ? 0.859 : 0,
  sde: 0,
  opex: year ? -7.364 : 0,
  capital: year ? 0 : -30.638,
  value_left: 0,
  tax: 0,
  net: 0,
  cumulative: 0,
  ...over,
});

const INV: Investor = {
  years: 3,
  discount_rate: 0.052,
  inflation: 0.02,
  heat_sale_eur_per_mwh: 92.24,
  cold_sale_eur_per_mwh: 36.17,
  sale_basis: { heat: "gas reference", cold: "gas reference" },
  heat_sold_gwh: 111.668,
  cold_sold_gwh: 23.743,
  revenue_heat_meur: 10.3,
  revenue_cold_meur: 0.859,
  opex_meur: 7.364,
  capex_meur: 30.638,
  reinvest_meur: 0,
  value_left_meur: 0,
  sde: {
    on: true,
    category: {
      key: "base_lt12",
      name: "Diepe geothermie <12 MWth (basislast)",
      label: "Deep geothermal, base load, under 12 MW",
      basis_eur_per_kwh: 0.0799,
      full_load_hours: 6000,
      min_mw: 0,
      max_mw: 12,
      ets_eur_per_kwh: 0.0114,
      ets_from: 2028,
      by_size: true,
      source: "PBL, SDE++ 2026 advice (Lensink & Eggink, publication 5698-1, 1 July 2026), Table 11.7a p.136",
    },
    chosen_by: "size",
    fits: true,
    capacity_mw: 10.61,
    flow_m3h: 300,
    brine_cooling_k: 30.98,
    eligible_gwh: 56.679,
    cap_gwh: 63.659,
    subsidised_gwh: 56.679,
    capped: false,
    basis_eur_per_kwh: 0.0799,
    correction_eur_per_kwh: 0.0196,
    floor_eur_per_kwh: 0.0131,
    ets_eur_per_kwh: 0.0114,
    ets_from_year: 2,
    per_kwh_first: 0.0603,
    per_kwh_later: 0.0489,
    first_year: 1,
    last_year: 2,
    calendar_years: [2027, 2028],
    meur_first_year: 3.351,
    meur_average: 2.416,
    total_meur: 6.0,
  },
  tax: { rate: 0.258, rate_low: 0.19, band_meur: 0.2, depreciation_years: 15, total_meur: 3.5, first_tax_year: 1 },
  flows: [
    flow(0, { net: -30.638, cumulative: -30.638 }),
    flow(1, { sde: 3.351, tax: -1.314, net: 5.832, cumulative: -25.094 }),
    flow(2, { sde: 2.664, tax: -1.147, net: 5.312, cumulative: -20.294 }),
    flow(3, { tax: -0.969, net: 2.826, cumulative: -17.88 }),
  ],
  npv_meur: 34.8,
  irr: 0.1606,
  payback_years: 7.0,
  without_sde: { npv_meur: 15.98, irr: 0.097, payback_years: 13.0 },
  break_even_basis_eur_per_kwh: null,
  needs_subsidy: false,
  notes: ["The plant's cost of heat has no subsidy, no tax and no sale."],
  sources: {},
  inputs: [
    { key: "heat_sale_eur_per_mwh", label: "Heat sale price", unit: "€/MWh", value: 92.24, default: 92.24, changed: false, kind: "number", source: "The gas reference's cost of heat" },
    { key: "cold_sale_eur_per_mwh", label: "Cold sale price", unit: "€/MWh", value: 36.17, default: 36.17, changed: false, kind: "number", source: "The gas reference's cost of cold" },
    {
      key: "sde_category",
      label: "SDE++ category",
      unit: "",
      value: "auto",
      default: "auto",
      changed: false,
      kind: "choice",
      source: "PBL",
      options: [
        { key: "auto", label: "By the plant's capacity (base load)" },
        { key: "base_ge20", label: "Deep geothermal, base load, 20 MW or more", name: "Diepe geothermie ≥20 MWth (basislast)", basis_eur_per_kwh: 0.0627, full_load_hours: 6000 },
      ],
    },
    { key: "sde_on", label: "SDE++ subsidy", unit: "", value: true, default: true, changed: false, kind: "switch", source: "RVO" },
  ],
};

const design = (investor: Investor | null | undefined) => ({ code: "A1", economics: { lcoh: 75.69, lcoc: 42.11, investor } }) as unknown as Design;
const apply = async (): Promise<ApiResult<Workbench>> => ({ ok: false, status: 0, message: "", offline: true });
const html = (el: Parameters<typeof renderToStaticMarkup>[0]) => renderToStaticMarkup(el).replace(/<!-- -->/g, "");

describe("stackYear", () => {
  it("stacks money in up from zero and money out down, skipping zeros", () => {
    const segs = stackYear(INV.flows[1]);
    expect(segs.map((s) => s.key)).toEqual(["revenue_heat", "revenue_cold", "sde", "opex", "tax"]);
    expect(segs[1].from).toBeCloseTo(10.3);
    expect(segs[2].to).toBeCloseTo(10.3 + 0.859 + 3.351);
    expect(segs[3]).toMatchObject({ from: 0, to: -7.364 });
    expect(segs[4].to).toBeCloseTo(-7.364 - 1.314);
  });
});

describe("salePatch", () => {
  it("sends a typed price, null when back at the default, and refuses what isn't a price", () => {
    expect(salePatch({ heat_sale_eur_per_mwh: "120" }, INV.inputs).patch).toEqual({ heat_sale_eur_per_mwh: 120 });
    expect(salePatch({ heat_sale_eur_per_mwh: "92.24" }, INV.inputs).patch).toEqual({});
    const changed = INV.inputs.map((it) => (it.key === "cold_sale_eur_per_mwh" ? { ...it, value: 50, changed: true } : it));
    expect(salePatch({ cold_sale_eur_per_mwh: "36.17" }, changed).patch).toEqual({ cold_sale_eur_per_mwh: null });
    expect(salePatch({ heat_sale_eur_per_mwh: "cheap" }, INV.inputs).errors.heat_sale_eur_per_mwh).toBe("Not a number");
    expect(salePatch({ heat_sale_eur_per_mwh: "-3" }, INV.inputs).errors.heat_sale_eur_per_mwh).toMatch(/At least/);
  });
});

describe("InvestorTiles", () => {
  it("shows the NPV, IRR and payback after tax, SDE++ in year 1 and whether it needs SDE++, as sent", () => {
    const out = html(createElement(InvestorTiles, { inv: INV }));
    expect(out).toContain("NPV after tax");
    expect(out).toContain("+34.8");
    expect(out).toContain("over 3 years at 5.2 % real; without SDE++ +16.0 M€");
    expect(out).toContain("16.1");
    expect(out).toContain("cost of capital 5.2 %");
    expect(out).toContain("7.0");
    expect(out).toContain("without SDE++ 13.0 years");
    expect(out).toContain("3.35");
    expect(out).toContain("years 1–2 (2027–2028)");
    expect(out).toContain("breaks even without it");
  });

  it("names the basisbedrag needed when it doesn't break even", () => {
    const inv = { ...INV, npv_meur: -3, needs_subsidy: true, break_even_basis_eur_per_kwh: 0.0912 };
    const out = html(createElement(InvestorTiles, { inv }));
    expect(out).toContain("Yes");
    expect(out).toContain("breaks even at a basisbedrag of 91.2 €/MWh (category: 79.9)");
    expect(out).toContain("−3.0");
  });
});

describe("SdePanel", () => {
  it("shows the category, its basisbedrag and hours, the capacity and the source", () => {
    const out = html(createElement(SdePanel, { inv: INV, prov: "dioscuri" }));
    expect(out).toContain("Deep geothermal, base load, under 12 MW");
    expect(out).toContain("Diepe geothermie &lt;12 MWth (basislast)");
    expect(out).toContain("79.9");
    expect(out).toContain("6,000");
    expect(out).toContain("10.6");
    expect(out).toContain("chosen by capacity");
    expect(out).toContain("Table 11.7a p.136");
    expect(out).toContain("Paid 48.9 €/MWh (60.3 in year 1)");
    expect(out).toContain("CO₂ correction 11.4, from year 2 (2028)");
    expect(out).toContain("56.7");
  });
});

describe("ChoicesPanel", () => {
  it("lists the sale prices with their revenue, the SDE++ switch and the categories", () => {
    const out = html(createElement(ChoicesPanel, { inv: INV, setAssumptions: apply }));
    expect(out).toContain('value="92.24"');
    expect(out).toContain("10.30 M€ a year");
    expect(out).toContain("Default 36.2 €/MWh, the gas plant&#x27;s cost");
    expect(out).toContain("By the plant&#x27;s capacity (base load)");
    expect(out).toContain("Deep geothermal, base load, 20 MW or more · 62.7 €/MWh, 6,000 h");
    expect(out).toContain('aria-checked="true"');
  });
});

describe("InvestorSection", () => {
  it("is a section of its own with the chart, its SDE++ years and the notes", () => {
    const out = html(createElement(InvestorSection, { design: design(INV), prov: "dioscuri", setAssumptions: apply }));
    expect(out).toContain("Investor&#x27;s view (with subsidy and tax)");
    expect(out).toContain("Separate from the plant&#x27;s cost");
    expect(out).toContain("SDE++ years 1–2 (2027–2028)");
    expect(out).toContain("Year 0 is building: −30.6 M€");
    expect(out).toContain("How the investor&#x27;s figures are worked out");
  });

  it("says the gas plant sets the sale prices, and shows nothing for an older server", () => {
    const gas = html(createElement(InvestorSection, { design: design(null), prov: "dioscuri", setAssumptions: apply }));
    expect(gas).toContain("A1 is the gas plant.");
    expect(gas).toContain("75.7 €/MWh");
    expect(html(createElement(InvestorSection, { design: design(undefined), prov: "dioscuri", setAssumptions: apply }))).toBe("");
  });
});
