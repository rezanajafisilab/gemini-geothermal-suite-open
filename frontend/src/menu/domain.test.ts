// The lookups behind the menus: a unit's edit field, Energy series and cost lines; a cost line's
// price and Sensitivity parameter; the Sensitivity parameter a number in a reply is.

import { describe, expect, it } from "vitest";

import { costItemsFor, editFieldOf, priceKeyOf, sensParamOfCost, sensParamOfNumber, seriesOfUnit } from "./domain";

const KEYS = [
  "electricity_eur_per_mwh",
  "gas_eur_per_mwh",
  "carbon_eur_per_t",
  "well_scale",
  "treatment_train_meur",
  "surface_meur_per_mw",
  "heat_pump_meur_per_mw",
  "boiler_meur_per_mw",
  "electric_boiler_meur_per_mw",
  "chiller_meur_per_mw",
  "geothermal_fixed_eur_per_kw",
  "geothermal_variable_eur_per_mwh",
  "heat_pump_fixed_eur_per_mw",
  "boiler_variable_eur_per_mwh",
  "chiller_fixed_eur_per_mw",
  "gas_sale_eur_per_mwh",
];

// The fixture design's cost lines (src/fixtures/workbench.json, A1).
const LINES = ["Wells", "Surface plant", "Treatment trains", "Heat pump", "Boiler", "Geothermal O&M", "Heat pump O&M", "Boiler O&M", "Electricity: heat pump", "Electricity: pumps", "Gas", "CO2: gas", "CO2: produced gas", "Electric chillers", "Chiller O&M", "Electricity: chillers", "Electricity: cooling towers"];

describe("a unit of the plant", () => {
  it("opens the edit panel on its own field", () => {
    expect(editFieldOf({ type: "heatpump" })).toEqual({ field: "heat_pump_mw", label: "Change its size" });
    expect(editFieldOf({ type: "chillers" })?.field).toBe("chiller_mw");
    expect(editFieldOf({ type: "injector_well", doublet: 2 })?.field).toBe("d1-cap");
    expect(editFieldOf({ type: "demand_cold" })?.field).toBe("cool_return_c");
    expect(editFieldOf({ type: "heat_exchanger" })).toBeNull();
    expect(editFieldOf({ type: "electric_boiler" })).toBeNull();
  });

  it("has its series on the Energy tab", () => {
    expect(seriesOfUnit("heatpump")).toEqual({ side: "heat", series: "hp" });
    expect(seriesOfUnit("producer_well")).toEqual({ side: "heat", series: "geo" });
    expect(seriesOfUnit("chillers")).toEqual({ side: "cool", series: "chill" });
    expect(seriesOfUnit("demand_heat")).toEqual({ side: "heat", series: null });
    expect(seriesOfUnit("grid")).toBeNull();
  });

  it("has its own cost lines, by the names the design gives them", () => {
    expect(costItemsFor("heatpump", LINES)).toEqual(["Heat pump", "Heat pump O&M", "Electricity: heat pump"]);
    expect(costItemsFor("boiler", LINES)).toEqual(["Boiler", "Boiler O&M", "Gas", "CO2: gas"]);
    expect(costItemsFor("producer_well", LINES)).toEqual(["Wells", "Electricity: pumps"]);
    expect(costItemsFor("chillers", LINES)).toEqual(["Electric chillers", "Chiller O&M", "Electricity: chillers"]);
    expect(costItemsFor("tower", LINES)).toEqual(["Electricity: cooling towers"]);
    expect(costItemsFor("absorption", LINES)).toEqual([]);
  });
});

describe("a cost line", () => {
  it("uses a price the conversation has, else none", () => {
    expect(priceKeyOf({ item: "Electricity: heat pump", kind: "electricity" }, KEYS)).toBe("electricity_eur_per_mwh");
    expect(priceKeyOf({ item: "CO₂: gas", kind: "carbon" }, KEYS)).toBe("carbon_eur_per_t");
    expect(priceKeyOf({ item: "Gas", kind: "gas" }, KEYS)).toBe("gas_eur_per_mwh");
    expect(priceKeyOf({ item: "Brine gas sold", kind: "gas" }, KEYS)).toBe("gas_sale_eur_per_mwh");
    expect(priceKeyOf({ item: "Wells", kind: "capital" }, KEYS)).toBe("well_scale");
    expect(priceKeyOf({ item: "Heat pump", kind: "capital" }, KEYS)).toBe("heat_pump_meur_per_mw");
    expect(priceKeyOf({ item: "Electric boiler", kind: "capital" }, KEYS)).toBe("electric_boiler_meur_per_mw");
    expect(priceKeyOf({ item: "Electric chillers", kind: "capital" }, KEYS)).toBe("chiller_meur_per_mw");
    expect(priceKeyOf({ item: "Geothermal O&M", kind: "fixed" }, KEYS)).toBe("geothermal_fixed_eur_per_kw");
    expect(priceKeyOf({ item: "Heat pump O&M", kind: "fixed" }, KEYS)).toBe("heat_pump_fixed_eur_per_mw");
    expect(priceKeyOf({ item: "Boiler O&M", kind: "variable" }, KEYS)).toBe("boiler_variable_eur_per_mwh");
    expect(priceKeyOf({ item: "Heat pump O&M", kind: "variable" }, KEYS)).toBeNull();
    expect(priceKeyOf({ item: "Electricity", kind: "electricity" }, [])).toBeNull();
  });

  it("is varied in Sensitivity by its price or the capital costs", () => {
    expect(sensParamOfCost({ item: "Gas", kind: "gas" })).toBe("gas_price");
    expect(sensParamOfCost({ item: "Electricity: chillers", kind: "electricity" })).toBe("electricity_price");
    expect(sensParamOfCost({ item: "CO2: gas", kind: "carbon" })).toBe("carbon_price");
    expect(sensParamOfCost({ item: "Wells", kind: "capital" })).toBe("capex");
    expect(sensParamOfCost({ item: "Boiler O&M", kind: "fixed" })).toBeNull();
    expect(sensParamOfCost({ item: "Brine gas sold", kind: "gas" })).toBeNull();
  });
});

describe("a number in a reply", () => {
  it("is a parameter by its unit and the words before it in its sentence", () => {
    expect(sensParamOfNumber("30 €/MWh", "€/MWh", "What if gas cost ")).toBe("gas_price");
    expect(sensParamOfNumber("120 €/MWh", "€/MWh", "With electricity at ")).toBe("electricity_price");
    expect(sensParamOfNumber("50 °C", "°C", "With a ", " heating return")).toBe("heat_return");
    expect(sensParamOfNumber("16 °C", "°C", "a cooling return of ")).toBe("cool_return");
    expect(sensParamOfNumber("70/40 °C", "°C", "with ", " heating")).toBe("heat_return");
    expect(sensParamOfNumber("10 K", "K", "a reservoir ", " colder")).toBe("reservoir_temp");
    expect(sensParamOfNumber("5.2%", "%", "at a discount rate of ")).toBe("discount_rate");
  });

  it("is a result, not a parameter, when it is a cost or a share", () => {
    expect(sensParamOfNumber("42.4 €/MWh", "€/MWh", "The cost of heat and cold is ")).toBeNull();
    expect(sensParamOfNumber("41 €/MWh", "€/MWh", "Gas boilers alone. A1 is 17% cheaper than gas at ")).toBeNull();
    expect(sensParamOfNumber("100%", "%", "It covers ")).toBeNull();
    expect(sensParamOfNumber("12.3 MW", "MW", "The heat pump is ")).toBeNull();
  });
});
