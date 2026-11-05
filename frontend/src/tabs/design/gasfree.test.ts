// The Plant view of the designs that buy no gas (gemini_agent/workbench.py graph_view, 31 Oct):
// an electric boiler fed by the grid next to it, and the gas node as the plant uses its gas
// (bought, the brine's own only, or sold to the gas grid with the buyer's CO₂ kept apart).

import { describe, expect, it } from "vitest";

import type { Design, DesignCheck, GraphEdge, GraphNode } from "../../workbench";
import {
  COL_W,
  NODE_H,
  TYPE_META,
  cardSubline,
  cardValues,
  edgeMw,
  farName,
  gasModeOf,
  layoutPlant,
  partNote,
  relatedChecks,
  routeClear,
  routePoints,
  seriesOf,
  yearShare,
  type LaidNode,
} from "./plant";

const node = (id: string, type: string, values: Record<string, number> = {}, extra: Partial<GraphNode> = {}): GraphNode => ({ id, type, label: id, solver: "dioscuri", values, units: {}, ...extra });
const edge = (source: string, target: string, kind: GraphEdge["kind"], mw: number | null = null, temperature_c: number | null = null): GraphEdge => ({
  id: `${source}-${target}`,
  source,
  target,
  kind,
  mw,
  temperature_c,
  label: "",
});

/** 2D-HP-AB-N1-EB as drawn: two doublets on one train, the brine's gas in a small boiler, an electric boiler. */
function gasFree(gas: "produced" | "sell") {
  const nodes: GraphNode[] = [
    node("reservoir", "reservoir", { depth_m: 2500, thickness_m: 100 }),
    node("producer_1", "producer_well", { doublet: 1, depth_m: 2500 }),
    node("producer_2", "producer_well", { doublet: 2, depth_m: 2500 }),
    node("injector_1", "injector_well", { doublet: 1, depth_m: 2500 }),
    node("injector_2", "injector_well", { doublet: 2, depth_m: 2500 }),
    node("train_1", "treatment"),
    node("absorption", "absorption", { power_mw: 1 }),
    node("hex", "heat_exchanger", { power_mw: 14.46 }),
    node("heat_pump", "heatpump", { power_mw: 13, cop: 3.9 }),
    gas === "sell"
      ? node("gas", "gas", { sold_gwh: 17.882, buyer_co2_t: 3612.1, vented_co2_t: 882.7, bought_gwh: 0 }, { label: "Gas sold to the grid", gas: "sell" })
      : node("gas", "gas", { produced_gwh: 17.882, bought_gwh: 0, flared_gwh: 0 }, { label: "Gas from the brine", gas: "produced" }),
    ...(gas === "produced" ? [node("boiler", "boiler", { power_mw: 3.7, heat_gwh: 16.988 })] : []),
    node("electric_boiler", "electric_boiler", { power_mw: 30, units: 3, heat_gwh: 0.172, electricity_gwh: 0.174 }),
    node("chillers", "chillers", { power_mw: 13.5 }),
    node("grid", "grid", { electricity_gwh: 20.6, heat_pump_gwh: 13.646, electric_boiler_gwh: 0.174, pumps_gwh: 4.104, chillers_gwh: 2.221, towers_gwh: 0.403 }, { units: { heat_pump_gwh: "GWh/yr" } }),
    node("tower", "tower", { rejected_gwh: 20 }),
    node("demand_heat", "demand_heat"),
    node("demand_cold", "demand_cold"),
  ];
  const edges: GraphEdge[] = [
    edge("reservoir", "producer_1", "brine", null, 89),
    edge("reservoir", "producer_2", "brine", null, 89),
    edge("producer_1", "train_1", "brine", null, 86),
    edge("producer_2", "train_1", "brine", null, 86),
    edge("injector_1", "reservoir", "brine", null, 40),
    edge("injector_2", "reservoir", "brine", null, 40),
    edge("train_1", "absorption", "brine", null, 86),
    edge("train_1", "hex", "brine", null, 86),
    edge("hex", "heat_pump", "brine"),
    edge("heat_pump", "injector_1", "brine", null, 40),
    edge("heat_pump", "injector_2", "brine", null, 40),
    edge("train_1", "gas", "gas"),
    ...(gas === "produced" ? [edge("gas", "boiler", "gas"), edge("boiler", "demand_heat", "network", 1.94, 100)] : []),
    edge("electric_boiler", "demand_heat", "network", 0.02, 100),
    edge("hex", "demand_heat", "network", 6.6, 100),
    edge("heat_pump", "demand_heat", "network", 6.1, 100),
    edge("absorption", "demand_cold", "cold", 0.4, 20),
    edge("chillers", "demand_cold", "cold", 1.2, 20),
    edge("chillers", "tower", "reject", 1.4),
    edge("absorption", "tower", "reject", 0.9),
    edge("grid", "chillers", "electricity", 0.25),
    edge("grid", "heat_pump", "electricity", 1.56),
    edge("grid", "tower", "electricity", 0.05),
    edge("grid", "electric_boiler", "electricity", 0.02),
    edge("grid", "producer_1", "electricity", 0.24),
    edge("grid", "producer_2", "electricity", 0.24),
  ];
  return { nodes, edges };
}

const design = (gas: "produced" | "sell" = "produced", extra: { sizes?: Record<string, number>; heat?: Record<string, number[]> } = {}): Design => {
  const graph = gasFree(gas);
  return {
    id: "A3",
    code: gas === "sell" ? "2D-HP-AB-N1-EB-GS" : "2D-HP-AB-N1-EB",
    reservoir_delta_c: 0,
    plant: { depth_m: 2500, heat_pump: true, boiler: gas === "produced", absorption: true, chillers: true, sizes_mw: { heat_exchanger: 14.46, heat_pump: 13, boiler: gas === "produced" ? 3.7 : 0, absorption: 1, chillers: 13.5, ...extra.sizes } },
    year: {
      heat_demand_gwh: 111.7,
      heat_delivered_gwh: 111.7,
      cool_demand_gwh: 20,
      cool_delivered_gwh: 20,
      heat_split_gwh: { geo: 57.884, hp: 53.612, boiler: 0, electric_boiler: 0.172 },
      cool_split_gwh: { abs: 4, chill: 16 },
      peak_heat_mw: 30,
      peak_cool_mw: 10,
      co2_t: { purchased_gas: 0, produced_gas: 882.7, electricity: 4115.8, total: 4998.5, sold_gas_elsewhere: 3612.1 },
      daily_mw: {
        heat: { demand: [20, 30], geo: [12, 12], hp: [8, 12], boiler: [0, 0], electric_boiler: [0, 6], ...extra.heat },
        cool: { demand: [0, 1], abs: [0, 1], chill: [0, 0] },
        power: { hp: [2, 3], chillers: [0.1, 0.3], towers: [0.01, 0.04], pumps: [0.4, 0.4], electric_boiler: [0, 6.06] },
        reject: { abs: [0, 1], chillers: [0.5, 2] },
      },
    },
    economics: { co2_t_per_year: 4998.5 },
    graph: { ...graph, gemini_project: null },
  } as unknown as Design;
};

const by = (nodes: LaidNode[]) => new Map(nodes.map((n) => [n.id, n]));
const overlaps = (a: LaidNode, b: LaidNode) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

describe("the electric boiler on the canvas", () => {
  const lay = layoutPlant(gasFree("produced"));
  const n = by(lay.nodes);

  it("sits on the middle row between the gas boiler and the grid, over the heat pump, with no extra column", () => {
    const eb = n.get("electric_boiler")!;
    expect(eb.y).toBe(n.get("boiler")!.y);
    expect(eb.y).toBe(n.get("grid")!.y);
    expect(eb.x).toBe(n.get("boiler")!.x + COL_W);
    expect(n.get("grid")!.x).toBe(eb.x + COL_W);
    expect(eb.x).toBe(n.get("heat_pump")!.x);
    expect(eb.y + NODE_H).toBeLessThan(n.get("heat_pump")!.y);
    const without = layoutPlant({ nodes: gasFree("produced").nodes.filter((x) => x.type !== "electric_boiler"), edges: gasFree("produced").edges.filter((e) => e.source !== "electric_boiler" && e.target !== "electric_boiler") });
    expect(lay.width).toBe(without.width);
    for (const a of lay.nodes) for (const b of lay.nodes) if (a !== b) expect(overlaps(a, b), `${a.id} / ${b.id}`).toBe(false);
  });

  it("is wired straight to the grid beside it, and every thin line stays clear of the cards", () => {
    const wire = lay.edges.find((e) => e.id === "grid-electric_boiler")!;
    expect([wire.sourceHandle, wire.targetHandle]).toEqual(["l", "r"]);
    for (const e of lay.edges.filter((x) => x.edge.kind === "electricity" || x.edge.kind === "reject")) {
      const s = n.get(e.edge.source)!;
      const t = n.get(e.edge.target)!;
      expect(routeClear(routePoints(s, t, e), s, t, lay.nodes), e.id).toBe(true);
    }
  });

  it("takes the highest lane into the heat demand (the rightmost unit over the corridor)", () => {
    const pipe = lay.edges.find((e) => e.id === "electric_boiler-demand_heat")!;
    expect([pipe.sourceHandle, pipe.targetHandle]).toEqual(["b", "lane-0"]);
    expect(lay.edges.find((e) => e.id === "boiler-demand_heat")!.targetHandle).toBe("lane-1");
  });

  it("has its own heat colour and icon, apart from the gas boiler's flame and violet", () => {
    const eb = TYPE_META.electric_boiler;
    expect(eb.makes).toBe("heat");
    expect(eb.color).not.toBe(TYPE_META.boiler.color);
    expect(eb.icon).not.toBe(TYPE_META.boiler.icon);
    expect(eb.icon.startsWith(TYPE_META.boiler.icon)).toBe(true); // the flame, with a bolt in it
    expect(farName(node("electric_boiler", "electric_boiler")).length).toBeLessThanOrEqual(12);
    expect(farName(node("boiler", "boiler"))).toBe("Gas boiler");
    expect(["buy", "produced", "sell"].map((gas) => farName(node("gas", "gas", {}, { gas })))).toEqual(["Gas", "Brine gas", "Gas sold"]);
  });
});

describe("the electric boiler over the year", () => {
  it("follows its own heat series against its size, and draws its electricity on its wire", () => {
    const d = design();
    expect(seriesOf(d, d.graph.nodes.find((x) => x.id === "electric_boiler")!)).toMatchObject({ values: [0, 6], capacity: 30, kind: "heat" });
    expect(seriesOf(design("produced", { sizes: { electric_boiler: 30 } }), { type: "electric_boiler" })!.capacity).toBe(30);
    const nodes = new Map(d.graph.nodes.map((x) => [x.id, x]));
    const wire = d.graph.edges.find((e) => e.id === "grid-electric_boiler")!;
    expect(edgeMw(d, wire, nodes, 1)).toBe(0);
    expect(edgeMw(d, wire, nodes, 2)).toBe(6.06);
    expect(edgeMw(d, d.graph.edges.find((e) => e.id === "electric_boiler-demand_heat")!, nodes, 2)).toBe(6);
    // The grid adds it to everything else it supplies.
    expect(seriesOf(d, { type: "grid" })!.values[1]).toBeCloseTo(3 + 0.3 + 0.04 + 0.4 + 6.06, 6);
  });

  it("is an idle unit, not a missing one, when the server sends no series for it", () => {
    const d = design();
    delete (d.year.daily_mw.heat as { electric_boiler?: number[] }).electric_boiler;
    expect(seriesOf(d, d.graph.nodes.find((x) => x.id === "electric_boiler")!)).toMatchObject({ values: [0, 0], capacity: 30 });
  });

  it("gives its share of the year's heat and says what it does in a sentence", () => {
    const d = design();
    expect(yearShare(d, "electric_boiler")!.share).toBeCloseTo(0.172 / 111.7, 6);
    const eb = d.graph.nodes.find((x) => x.id === "electric_boiler")!;
    expect(partNote(d, eb)).toBe(
      "Heats what the exchanger, the heat pump and the gas boiler cannot, from grid electricity: 0.172 GWh of heat a year (0.154% of the heat) for 0.174 GWh of electricity. 30 MW, built as 3 equal units so one can be out.",
    );
    expect(cardSubline(eb, cardValues(eb, 2))).toBe("30 MW in 3 units");
  });

  it("lists it among the grid's users, and keeps its checks apart from the gas boiler's", () => {
    const grid = design().graph.nodes.find((x) => x.id === "grid")!;
    expect(cardSubline(grid, [])).toBe("heat pump 13.6 · well pumps 4.1 · chillers 2.22 · towers 0.403 · e-boiler 0.174 GWh/yr");
    const checks: DesignCheck[] = [
      { name: "No unit gives more than its size allows", passed: true, detail: "" },
      { name: "Boiler burns the produced gas first", passed: true, detail: "" },
      { name: "Electric boiler heats only what the rest cannot", passed: true, detail: "" },
    ];
    expect(relatedChecks("boiler", checks).map((c) => c.name)).toEqual(["No unit gives more than its size allows", "Boiler burns the produced gas first"]);
    expect(relatedChecks("electric_boiler", checks).map((c) => c.name)).toEqual(["No unit gives more than its size allows", "Electric boiler heats only what the rest cannot"]);
  });
});

describe("the gas, by what the plant does with it", () => {
  it("reads the mode off the gas node, buy when it doesn't say", () => {
    expect(gasModeOf(node("gas", "gas", {}, { gas: "sell" }))).toBe("sell");
    expect(gasModeOf(node("gas", "gas", {}, { gas: "produced" }))).toBe("produced");
    expect(gasModeOf(node("gas", "gas"))).toBe("buy");
    expect(gasModeOf(undefined)).toBe("buy");
  });

  it("burns only the brine's own gas, none bought: the card and the note say so", () => {
    const d = design("produced");
    const gas = d.graph.nodes.find((x) => x.id === "gas")!;
    expect(cardSubline(gas, [])).toBe("Brine gas only, none bought");
    expect(partNote(d, gas)).toBe("No gas is bought: the gas boiler burns only the brine's own gas, 17.9 GWh a year.");
    expect(seriesOf(d, gas)).toMatchObject({ follows: true });
  });

  it("sold, goes to the gas grid with no gas boiler, and keeps the buyer's CO₂ out of the plant's", () => {
    const d = design("sell");
    const lay = layoutPlant(d.graph);
    const n = by(lay.nodes);
    expect(n.has("boiler")).toBe(false);
    expect(n.get("gas")!.x).toBe(n.get("train_1")!.x); // straight over the train it comes from
    expect(lay.edges.filter((e) => e.edge.source === "gas")).toEqual([]);
    const gas = d.graph.nodes.find((x) => x.id === "gas")!;
    expect(seriesOf(d, gas)).toBeNull(); // no "Idle": the gas leaves all year
    expect(cardSubline(gas, [])).toBe("Buyer's CO₂ 3,612 t, not ours");
    expect(partNote(d, gas)).toBe(
      "The brine's gas is cleaned and sold to the gas grid: 17.9 GWh of methane a year, none burnt here. Whoever buys it burns it: 3,612 t of CO₂ a year, the buyer's, not in this plant's 4,999 t.",
    );
  });

  it("still says where the gas comes from when the plant buys it", () => {
    const gas = node("gas", "gas", { produced_gwh: 12.95, bought_gwh: 4.2, flared_gwh: 0 }, { gas: "buy" });
    expect(cardSubline(gas, [])).toBe("Produced gas first, then bought");
    expect(partNote(design(), gas)).toBe("The boiler burns the brine's own gas first (12.9 GWh a year), then buys gas (4.2 GWh a year).");
  });
});
