import { describe, expect, it } from "vitest";

import type { AssumptionItem, Assumptions } from "../../workbench";
import {
  assumptionValue,
  buildPatch,
  changedCount,
  defaultOf,
  fieldOf,
  fieldsFor,
  groupsFor,
  isChanged,
  parseField,
  resetAllPatch,
  toDisplay,
  valueOf,
} from "./assumptions";

const item = (key: string, label: string, unit: string, group: string, value: number, source = ""): AssumptionItem => ({
  key,
  label,
  unit,
  group,
  value,
  default: value,
  source,
});

// A part of the server's list (src/gemini_agent/workbench.py, assumptions_view).
const ITEMS: AssumptionItem[] = [
  item("discount_rate", "Discount rate (real)", "", "prices", 0.052, "PBL, SDE++ 2026 advice, Table 6.3: geothermal WACC 5.2 % real"),
  item("electricity_eur_per_mwh", "Electricity", "€/MWh", "prices", 185.7, "Eurostat nrg_pc_205"),
  item("gas_eur_per_mwh", "Gas", "€/MWh", "prices", 69.4),
  item("carbon_eur_per_t", "CO₂ price", "€/t", "prices", 73.9),
  item("well_base_eur", "Well, fixed part", "€", "capital", 790000),
  item("heat_pump_meur_per_mw", "Heat pump", "M€/MW", "capital", 1.2),
  item("heat_pump_fixed_eur_per_mw", "Heat pump O&M, fixed", "€/MW/yr", "o&m", 3200),
  item("wells_life_years", "Wells and surface plant life", "years", "lifetimes", 30),
];

/** The view the server sends, with `changes` applied (values by key too). */
function assumptions(changes: Record<string, number> = {}): Assumptions {
  const items = ITEMS.map((it) => (it.key in changes ? { ...it, value: changes[it.key] } : it));
  return {
    ...Object.fromEntries(items.map((it) => [it.key, it.value])),
    items,
    defaults: Object.fromEntries(ITEMS.map((it) => [it.key, it.default])),
    sources: Object.fromEntries(ITEMS.map((it) => [it.key, it.source])),
    notes: [],
  };
}

const field = (id: string) => fieldsFor(assumptions()).find((f) => f.id === id)!;

describe("the fields", () => {
  it("follow the server's items: label, unit, group, source", () => {
    const f = field("electricity_eur_per_mwh");
    expect(f).toMatchObject({ label: "Electricity", unit: "€/MWh", group: "prices", source: "Eurostat nrg_pc_205", min: 0 });
    expect(fieldsFor(assumptions()).map((x) => x.id)).toEqual(ITEMS.map((it) => it.key));
  });

  it("show the discount rate in percent and lifetimes in whole years", () => {
    expect(field("discount_rate")).toMatchObject({ percent: true, unit: "%", max: 50 });
    expect(field("wells_life_years")).toMatchObject({ integer: true, min: 1 });
    expect(field("gas_eur_per_mwh").percent).toBe(false);
  });

  it("group by the server's groups in a fixed order, an unknown group last", () => {
    const extra = fieldOf(item("network_eur_per_mwh", "Network", "€/MWh", "network", 4));
    const groups = groupsFor([extra, ...fieldsFor(assumptions())]);
    expect(groups.map((g) => g.label)).toEqual(["Prices", "Capital costs", "O&M", "Lifetimes", "Network"]);
    expect(groups[0].fields.map((f) => f.id)).toEqual(["discount_rate", "electricity_eur_per_mwh", "gas_eur_per_mwh", "carbon_eur_per_t"]);
  });

  it("read values and defaults from the items, else by key", () => {
    const a = assumptions({ gas_eur_per_mwh: 80 });
    expect(valueOf(a, field("gas_eur_per_mwh"))).toBe(80);
    expect(defaultOf(a, field("gas_eur_per_mwh"))).toBe(69.4);
    expect(assumptionValue(a, "carbon_eur_per_t")).toBe(73.9);
    expect(assumptionValue({ ...a, items: [] }, "gas_eur_per_mwh")).toBe(80);
    expect(assumptionValue(null, "gas_eur_per_mwh")).toBeNull();
  });
});

describe("shown and typed", () => {
  it("shows rates in percent without float noise, big numbers grouped", () => {
    expect(toDisplay(0.052, field("discount_rate"))).toBe("5.2");
    expect(toDisplay(0.0525, field("discount_rate"))).toBe("5.25");
    expect(toDisplay(69.4, field("gas_eur_per_mwh"))).toBe("69.4");
    expect(toDisplay(790000, field("well_base_eur"))).toBe("790,000");
    expect(toDisplay(3200, field("heat_pump_fixed_eur_per_mw"))).toBe("3,200");
    expect(toDisplay(undefined, field("gas_eur_per_mwh"))).toBe("");
  });

  it("reads percent back as a fraction, a decimal comma, and thousands separators", () => {
    expect(parseField("5.25", field("discount_rate"))).toEqual({ ok: true, value: 0.0525 });
    expect(parseField("7 %", field("discount_rate"))).toEqual({ ok: true, value: 0.07 });
    expect(parseField("3,5", field("discount_rate"))).toEqual({ ok: true, value: 0.035 });
    expect(parseField("790,000", field("well_base_eur"))).toEqual({ ok: true, value: 790000 });
    expect(parseField("1,250.5", field("well_base_eur"))).toEqual({ ok: true, value: 1250.5 });
    expect(parseField("0,05", field("heat_pump_meur_per_mw"))).toEqual({ ok: true, value: 0.05 });
    expect(parseField("60", field("gas_eur_per_mwh"))).toEqual({ ok: true, value: 60 });
  });

  it("round-trips every default", () => {
    const a = assumptions();
    for (const f of fieldsFor(a)) {
      const v = valueOf(a, f)!;
      const p = parseField(toDisplay(v, f), f);
      expect(p.ok && p.value).toBe(v);
    }
  });

  it("says why a value can't be used", () => {
    expect(parseField("", field("gas_eur_per_mwh")).ok).toBe(false);
    expect(parseField("abc", field("gas_eur_per_mwh")).ok).toBe(false);
    expect(parseField("−1", field("gas_eur_per_mwh"))).toEqual({ ok: false, error: "At least 0" });
    expect(parseField("25.5", field("wells_life_years"))).toEqual({ ok: false, error: "A whole number of years" });
    expect(parseField("0", field("wells_life_years"))).toEqual({ ok: false, error: "At least 1" });
    expect(parseField("80", field("discount_rate"))).toEqual({ ok: false, error: "At most 50 %" });
  });
});

describe("buildPatch", () => {
  it("sends only what changed, in API units, by the server's keys", () => {
    const d = buildPatch({ discount_rate: "7", gas_eur_per_mwh: "69.4", wells_life_years: "25", well_base_eur: "800,000" }, assumptions());
    expect(d.patch).toEqual({ discount_rate: 0.07, wells_life_years: 25, well_base_eur: 800000 });
    expect(d.changes).toEqual(["discount_rate", "well_base_eur", "wells_life_years"]);
    expect(d.errors).toEqual({});
  });

  it("sends null for a value back at its default", () => {
    const a = assumptions({ discount_rate: 0.08, gas_eur_per_mwh: 70 });
    const d = buildPatch({ discount_rate: "5.2", gas_eur_per_mwh: "70" }, a);
    expect(d.patch).toEqual({ discount_rate: null });
  });

  it("keeps errors out of the patch", () => {
    const d = buildPatch({ discount_rate: "x", gas_eur_per_mwh: "60" }, assumptions());
    expect(d.patch).toEqual({ gas_eur_per_mwh: 60 });
    expect(Object.keys(d.errors)).toEqual(["discount_rate"]);
  });

  it("is empty with no edits, and ignores keys the server doesn't list", () => {
    expect(buildPatch({}, assumptions())).toEqual({ patch: {}, errors: {}, changes: [] });
    expect(buildPatch({ lifetime_years: "30" }, assumptions()).patch).toEqual({});
  });
});

describe("changed and reset", () => {
  it("marks what differs from the default", () => {
    const a = assumptions({ carbon_eur_per_t: 100, heat_pump_meur_per_mw: 1.0 });
    expect(isChanged(a, field("carbon_eur_per_t"))).toBe(true);
    expect(isChanged(a, field("gas_eur_per_mwh"))).toBe(false);
    expect(isChanged(a, field("heat_pump_meur_per_mw"))).toBe(true);
    expect(changedCount(a)).toBe(2);
  });

  it("resets everything changed to null", () => {
    const a = assumptions({ carbon_eur_per_t: 100, discount_rate: 0.07, wells_life_years: 25 });
    expect(resetAllPatch(a)).toEqual({ discount_rate: null, carbon_eur_per_t: null, wells_life_years: null });
    expect(resetAllPatch(assumptions())).toEqual({});
  });
});
