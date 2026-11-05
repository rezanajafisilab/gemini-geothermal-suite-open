// What the menus need to know about the plant and its money: which field of the edit panel sizes a
// unit, which Energy series and cost lines are a unit's, which price a cost line uses, and which
// Sensitivity parameter varies a cost line or a number in a reply. Pure lookups (tested in
// domain.test.ts); a lookup that finds nothing means the menu leaves that item out.

import type { Side } from "./types";

/** The edit panel's field for a unit (EditPanel's input ids end in it), and the item's words. */
export function editFieldOf(node: { type: string; doublet?: number }): { field: string; label: string } | null {
  switch (node.type) {
    case "heatpump":
      return { field: "heat_pump_mw", label: "Change its size" };
    case "boiler":
      return { field: "boiler_mw", label: "Change its size" };
    case "absorption":
      return { field: "absorption_mw", label: "Change its size" };
    case "chillers":
      return { field: "chiller_mw", label: "Change its size" };
    case "producer_well":
    case "injector_well":
      return { field: `d${Math.max(0, (node.doublet ?? 1) - 1)}-cap`, label: "Change its doublet's flow cap" };
    case "reservoir":
      return { field: "reservoir_delta_c", label: "Change its temperature" };
    case "demand_heat":
      return { field: "return_c", label: "Change the heating return" };
    case "demand_cold":
      return { field: "cool_return_c", label: "Change the cooling return" };
    default:
      return null;
  }
}

/** A unit's line on the Energy tab: its side and its series (null: the side's whole stack). */
export function seriesOfUnit(type: string): { side: Side; series: string | null } | null {
  switch (type) {
    case "reservoir":
    case "producer_well":
    case "injector_well":
    case "treatment":
    case "heat_exchanger":
      return { side: "heat", series: "geo" };
    case "heatpump":
      return { side: "heat", series: "hp" };
    case "boiler":
    case "gas":
      return { side: "heat", series: "boiler" };
    case "electric_boiler":
      return { side: "heat", series: "electric_boiler" };
    case "absorption":
      return { side: "cool", series: "abs" };
    case "chillers":
      return { side: "cool", series: "chill" };
    case "demand_heat":
      return { side: "heat", series: null };
    case "demand_cold":
    case "tower":
      return { side: "cool", series: null };
    default:
      return null;
  }
}

/** "CO₂: gas" and "CO2: gas" read the same. */
const fold = (s: string) => s.toLowerCase().replace(/₂/g, "2").replace(/\s+/g, " ").trim();

const UNIT_COSTS: Record<string, RegExp> = {
  reservoir: /^wells$/,
  producer_well: /^wells$|^electricity: pumps/,
  injector_well: /^wells$|^electricity: pumps/,
  treatment: /^treatment/,
  heat_exchanger: /^surface plant|^geothermal o&m/,
  heatpump: /^heat pump|^electricity: heat pump/,
  boiler: /^boiler|^gas$|^co2: gas/,
  gas: /^gas$|^co2: (produced )?gas|brine gas/,
  electric_boiler: /^electric boiler|^electricity: electric boiler/,
  absorption: /^absorption/,
  chillers: /^electric chillers|^chiller|^electricity: chillers/,
  tower: /cooling towers/,
  grid: /^electricity/,
};

/** The design's cost lines that belong to a unit (as the design names them), in its order. */
export function costItemsFor(type: string, items: string[]): string[] {
  const re = UNIT_COSTS[type];
  if (!re) return [];
  return [...new Set(items.filter((it) => re.test(fold(it))))];
}

/** The assumption (a key of the server's prices) a cost line uses, when the conversation has it. */
export function priceKeyOf(line: { item: string; kind: string }, keys: Iterable<string>): string | null {
  const have = new Set(keys);
  const it = fold(line.item);
  const pick = (...cands: string[]) => cands.find((k) => have.has(k)) ?? null;
  // The electric boiler before the gas boiler: "electric boiler" contains "boiler".
  const unit = /electric boiler/.test(it)
    ? "electric_boiler"
    : /heat pump/.test(it)
      ? "heat_pump"
      : /boiler/.test(it)
        ? "boiler"
        : /absorption/.test(it)
          ? "absorption"
          : /chiller/.test(it)
            ? "chiller"
            : /geothermal/.test(it)
              ? "geothermal"
              : null;
  switch (line.kind) {
    case "electricity":
      return pick("electricity_eur_per_mwh");
    case "gas":
      return /sold|sale/.test(it) ? pick("gas_sale_eur_per_mwh") : pick("gas_eur_per_mwh");
    case "carbon":
      return pick("carbon_eur_per_t");
    case "capital":
      if (/^wells?$/.test(it)) return pick("well_scale", "well_per_m_eur");
      if (/treatment/.test(it)) return pick("treatment_train_meur");
      if (/surface plant/.test(it)) return pick("surface_meur_per_mw", "surface_per_doublet_meur");
      return unit && unit !== "geothermal" ? pick(`${unit}_meur_per_mw`) : null;
    case "fixed":
      return unit ? pick(`${unit}_fixed_eur_per_kw`, `${unit}_fixed_eur_per_mw`) : null;
    case "variable":
      return unit ? pick(`${unit}_variable_eur_per_mwh`) : null;
    default:
      return null;
  }
}

/** The Sensitivity parameter that varies a cost line (the server's catalogue keys). */
export function sensParamOfCost(line: { item: string; kind: string }): string | null {
  switch (line.kind) {
    case "electricity":
      return "electricity_price";
    case "gas":
      return /sold|sale/.test(fold(line.item)) ? null : "gas_price";
    case "carbon":
      return "carbon_price";
    case "capital":
      return "capex";
    default:
      return null;
  }
}

/**
 * The Sensitivity parameter a number in a reply is, from its unit and the words just before it in
 * its sentence ("gas at 30 €/MWh", "a 50 °C heating return", "a reservoir 10 K colder"). A cost
 * of heat or a share of the demand is a result, not a parameter: null.
 */
export function sensParamOfNumber(text: string, unit: string, before: string, after = ""): string | null {
  const cut = before.lastIndexOf(". ");
  const sentence = fold(before.slice(Math.max(cut >= 0 ? cut + 2 : 0, before.length - 80)));
  const near = `${sentence} ${fold(after).slice(0, 30)}`;
  const cold = /cool|cold|chill/.test(near);
  if (text.includes("/") && unit === "°C") return cold ? "cool_return" : "heat_return";
  switch (unit) {
    case "€/MWh":
      if (/\bgas\b(?! plant)(?! boiler)/.test(sentence) && !/cost of (heat|cold)|cheaper|dearer/.test(sentence)) return "gas_price";
      if (/electricity|power price/.test(sentence)) return "electricity_price";
      return null;
    case "°C":
      if (/return/.test(near)) return cold ? "cool_return" : "heat_return";
      if (/reservoir|aquifer/.test(near)) return "reservoir_temp";
      return null;
    case "K":
      return /reservoir|aquifer|colder|warmer|hotter/.test(near) ? "reservoir_temp" : null;
    case "%":
      return /discount|wacc/.test(sentence) ? "discount_rate" : null;
    case "GWh":
    case "MWh":
      return /demand/.test(near) ? (cold ? "cool_demand" : "heat_demand") : null;
    default:
      return null;
  }
}
