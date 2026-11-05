// The cost basis (the Economics tab), the waterfall's shares, and the caught-and-fixed
// rows: what they say, from the server's numbers.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { shareText } from "../tabs/economics/CostPanel";
import { CaughtFixed } from "../tabs/evidence/CaughtFixed";
import type { Caught, CostBasis } from "../workbench/basis";
import { CostBasisView, Tornado } from "./CostBasis";

// cost_basis.basis on the challenge's recommended design (3 Nov), trimmed.
const BASIS: CostBasis = {
  design: "1D-HP-EC@3000-N1-FC",
  headline: { lcoe: 56.66, lcoh: 63.72, lcoc: 23.46, capex_meur: 34.19 },
  method: "Levelised cost.",
  includes: [
    { item: "Wells: drilling, casing and the ESP", kind: "capital", eur_per_mwh: 6.27, share: 0.1107 },
    { item: "Operation and maintenance", kind: "o&m", eur_per_mwh: 13.77, share: 0.243 },
    { item: "Gas bought at 69.4 €/MWh", kind: "gas", eur_per_mwh: 15.16, share: 0.2676 },
  ],
  excludes: [{ item: "The district network", why: "Pipes to the buildings are not priced." }],
  rate: { value: 0.052, label: "5.2 % real", source: "PBL, SDE++ 2026 advice, Table 6.3" },
  lifetimes: [{ label: "Wells and surface plant", years: 30 }],
  prices: [{ label: "Electricity", value: "185.7 €/MWh", source: "Eurostat" }],
  split: { heat_share: 1, text: "Shared by brine heat.", headline: "Heat and cold together." },
  swings: [
    { key: "gas_eur_per_mwh", label: "Gas price", base: "69.4 €/MWh", low: { value: "35 €/MWh", lcoe: 49.08, lcoh: 54.52, lcoc: 23.46 }, high: { value: "104 €/MWh", lcoe: 64.24, lcoh: 72.91, lcoc: 23.46 } },
    { key: "wells_life_years", label: "Life of the wells", base: "30 years", low: { value: "20 years", lcoe: 59.71, lcoh: 67.42, lcoc: 23.46 }, high: { value: "40 years", lcoe: 55.3, lcoh: 62.0, lcoc: 23.46 } },
  ],
  note: "Each swing reprices this same plant.",
};

describe("cost basis", () => {
  it("says what is in and out, the rate, and every swing", () => {
    const html = renderToStaticMarkup(createElement(CostBasisView, { basis: BASIS }));
    expect(html).toContain("56.7 €/MWh");
    expect(html).toContain("The district network");
    expect(html).toContain("5.2 % real");
    expect(html).toContain("Gas price");
    expect(html).toContain("6.3 €/MWh");
  });
  it("puts the cheaper case left and the dearer right, whichever input made it", () => {
    const html = renderToStaticMarkup(createElement(Tornado, { swings: BASIS.swings, base: 56.66 }));
    // A longer life is cheaper: 40 years on the left (cheap) end, 20 years on the right.
    const life = html.slice(html.lastIndexOf("Life of the wells"));
    expect(life.indexOf("40 years")).toBeLessThan(life.indexOf("20 years"));
    expect(html).toContain("56.7 €/MWh as designed");
  });
  it("keeps the compact view to the bar until asked", () => {
    const html = renderToStaticMarkup(createElement(CostBasisView, { basis: BASIS, compact: true }));
    expect(html).not.toContain("<strong>The district network.</strong>");
    expect(html).toContain('title="Pipes to the buildings are not priced."');
    expect(html).toContain("Every part, and why each item is left out");
  });
});

describe("a cost line's share", () => {
  it("is a whole percent of the side's cost", () => {
    expect(shareText(18.7, 110)).toBe("17 %");
    expect(shareText(0.2, 63.7)).toBe("<1 %");
    expect(shareText(-2, 63.7)).toBe("−3 %");
    expect(shareText(5, 0)).toBe("–");
  });
});

describe("caught and fixed", () => {
  const caught: Caught = {
    updated: "2026-11-03",
    total: 2,
    guarded: 1,
    avoided: 1,
    groups: [{ key: "gemini", label: "GEMINI's physics code", total: 2, guarded: 1 }],
    items: [
      { id: "F1", group: "gemini", group_label: "GEMINI's physics code", title: "Heat exchanger moved heat from cold to hot", failed: "x", found: "Bug hunt", found_in: "hackathon/gemini_bughunt/README.md#F1", fix: "Patch 01", commit: "9d28750", adr: null, patch: "01_heat_exchanger_signed_duty.diff", tests: ["unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies"], status: "fixed", source_label: null },
      { id: "F6", group: "gemini", group_label: "GEMINI's physics code", title: "Recycle loops were not converged", failed: "y", found: "Bug hunt", found_in: "hackathon/gemini_bughunt/README.md#F6", fix: "No loop", commit: null, adr: null, patch: null, tests: [], status: "avoided", source_label: null },
    ],
  };
  it("lists each failure with its guard, avoided ones said so", () => {
    const html = renderToStaticMarkup(createElement(CaughtFixed, { caught }));
    expect(html).toContain("2 failures we found and fixed");
    expect(html).toContain("1 test");
    expect(html).toContain("no test");
    expect(html).toContain("avoided, not patched");
  });
});
