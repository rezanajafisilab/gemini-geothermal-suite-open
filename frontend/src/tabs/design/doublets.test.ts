// The Plant view with doublets that differ, on the real backend's fixtures (src/fixtures/
// workbench.json): U2 has two doublets built differently (doublet 1 with two injectors, doublet 2
// with its producer open over the lower half and its own treatment train, the hottest first), U1
// two identical doublets on one train in equal shares, the pick (A1 · 1D-HP-EC-N1) one doublet.
// And the shape of the whole: the pick, U1 and a plant of three doublets with two injectors each
// laid out for a laptop's canvas.

import { beforeAll, describe, expect, it } from "vitest";

import { loadFixtures, type Design, type Graph, type GraphEdge, type GraphNode } from "../../workbench";
import {
  WELL_H,
  WELL_MIN_W,
  WELL_W,
  baseLoadDoublet,
  depthY,
  describeChanges,
  diffChanges,
  doubletOf,
  editBase,
  editForm,
  endPoint,
  formDoublets,
  injectorsOf,
  laidEdgePoints,
  layoutPlant,
  routeClear,
  sameDoublets,
  shortLabel,
  stoppedOn,
  trainMembers,
  trainYear,
  wellDay,
  wellOpening,
  wellShort,
  wellYear,
  type LaidNode,
  type PlantLayout,
} from "./plant";

let designs: Design[] = [];
const PICK = "A1 · 1D-HP-EC-N1-FC";
const get = (id: string) => designs.find((d) => d.id === id)!;
const lay = (d: Design) => layoutPlant(d.graph, { doublets: d.plant.doublets });
const byId = (l: PlantLayout) => new Map(l.nodes.map((n) => [n.id, n]));
const overlaps = (a: LaidNode, b: LaidNode) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

beforeAll(async () => {
  designs = (await loadFixtures()).workbench.designs;
});

describe("the layout of doublets that differ (U2)", () => {
  // Changed for the canvas's aspect (31 Oct): the doublets sit under the plant at full width, no
  // longer left of it.
  it("frames each doublet under the plant: its injectors, then its producer", () => {
    const l = lay(get("U2"));
    expect(l.groups.map((g) => [g.label, g.wells])).toEqual([
      ["Doublet 1", ["injector_1a", "injector_1b", "producer_1"]],
      ["Doublet 2", ["injector_2", "producer_2"]],
    ]);
    const n = byId(l);
    const wells = ["injector_1a", "injector_1b", "producer_1", "injector_2", "producer_2"].map((id) => n.get(id)!);
    const xs = wells.map((w) => w.x);
    expect([...xs].sort((a, b) => a - b)).toEqual(xs);
    // Every well inside its frame.
    for (const g of l.groups)
      for (const w of g.wells) {
        expect(n.get(w)!.x).toBeGreaterThanOrEqual(g.x);
        expect(n.get(w)!.x + n.get(w)!.width).toBeLessThanOrEqual(g.x + g.width);
      }
    // The trains, the exchanger and the heat pump above every well.
    const top = Math.min(...wells.map((w) => w.y));
    for (const id of ["train_1", "train_2", "hex", "heat_pump"]) expect(n.get(id)!.y + n.get(id)!.height).toBeLessThan(top);
  });

  it("stacks the treatment trains in one column, train 1 (doublet 1's) on top", () => {
    const n = byId(lay(get("U2")));
    expect(n.get("train_1")!.x).toBe(n.get("train_2")!.x);
    expect(n.get("train_2")!.y).toBeGreaterThan(n.get("train_1")!.y + n.get("train_1")!.height);
  });

  it("puts no card on another", () => {
    const l = lay(get("U2"));
    for (const a of l.nodes) for (const b of l.nodes) if (a !== b) expect(overlaps(a, b), `${a.id} / ${b.id}`).toBe(false);
  });

  it("sends each producer up to its train's lane and the brine back over the wells into every injector", () => {
    const l = lay(get("U2"));
    const e = (id: string) => l.edges.find((x) => x.id === id)!;
    const back = ["heat_pump-injector_1a", "heat_pump-injector_1b", "heat_pump-injector_2"].map(e);
    expect(new Set(back.map((x) => x.via?.y)).size).toBe(1);
    const returnY = back[0].via!.y;
    const hot1 = e("producer_1-train_1");
    const hot2 = e("producer_2-train_2");
    expect(hot1.via && hot2.via).toBeTruthy();
    // The return lane on top, then train 1's lane, then train 2's, all over the wells.
    expect(returnY).toBeLessThan(hot1.via!.y);
    expect(hot1.via!.y).toBeLessThan(hot2.via!.y);
    expect(hot2.via!.y).toBeLessThan(byId(l).get("producer_1")!.y);
    // The brine back is drawn last, over the other pipes.
    expect(Math.max(...back.map((x) => l.edges.indexOf(x)))).toBe(l.edges.length - 1 - l.edges.slice().reverse().findIndex((x) => x.layer === 3));
  });

  it("bridges every crossing of two pipes, on the pipe drawn on top", () => {
    const l = lay(get("U2"));
    const bridged = l.edges.filter((x) => x.bridges?.length);
    expect(bridged.length).toBeGreaterThan(0);
    // Injector 2's drop crosses doublet 1's lane to its train.
    const drop = l.edges.find((x) => x.id === "heat_pump-injector_2")!;
    const pts = laidEdgePoints(drop, new Map(l.nodes.map((n) => [n.id, n])));
    expect(drop.bridges?.some((b) => b.dir === "v" && Math.abs(b.x - pts[pts.length - 1][0]) < 1)).toBe(true);
    // Thin lines get none.
    expect(l.edges.filter((x) => x.layer === 0).every((x) => !x.bridges)).toBe(true);
  });

  it("runs every electricity and tower line clear of every card", () => {
    const l = lay(get("U2"));
    const n = byId(l);
    for (const e of l.edges.filter((x) => x.layer === 0)) {
      const pts = laidEdgePoints(e, n);
      expect(pts.length, e.id).toBeGreaterThanOrEqual(2);
      expect(routeClear(pts, n.get(e.edge.source)!, n.get(e.edge.target)!, l.nodes), e.id).toBe(true);
    }
  });

  it("draws each well's open part in the band at its depth: producer 2 over the lower half", () => {
    const l = lay(get("U2"));
    const band = l.nodes.find((x) => x.node.type === "reservoir")!;
    expect(band.aquifers).toEqual([2500]);
    const w = new Map(band.wells!.map((x) => [x.id, x]));
    expect(w.get("producer_2")).toMatchObject({ short: "P2", opening: "lower", top_m: 2500, base_m: 2550 });
    expect(w.get("producer_1")).toMatchObject({ short: "P1", opening: "full", top_m: 2450, base_m: 2550 });
    expect(w.get("injector_1b")).toMatchObject({ short: "I1B", kind: "injector" });
    // Under its card: the reservoir's handle for a well sits at the well's middle.
    const n = byId(l);
    for (const id of ["producer_2", "injector_1a"]) {
      const card = n.get(id)!;
      const edge = l.edges.find((x) => x.edge.source === "reservoir" ? x.edge.target === id : x.edge.source === id && x.edge.target === "reservoir")!;
      const end = endPoint(band, edge.edge.source === "reservoir" ? edge.sourceHandle : edge.targetHandle);
      expect(end.x).toBeCloseTo(card.x + card.width / 2, 6);
      expect(end.y).toBe(band.y);
    }
    // The lower half is drawn as the lower half of the layer.
    const t = 100;
    expect(depthY(2500, [2500], t)).toBeCloseTo((depthY(2450, [2500], t) + depthY(2550, [2500], t)) / 2, 6);
    expect(depthY(3000, [2500, 3000], t)).toBeGreaterThan(depthY(2550, [2500, 3000], t));
  });
});

describe("two doublets on one train (U1) and one doublet (the pick)", () => {
  it("sends both producers up one shared lane, left past the plant and into the train's left side", () => {
    const l = lay(get("U1"));
    const up = ["producer_1-train_1", "producer_2-train_1"].map((id) => l.edges.find((x) => x.id === id)!);
    const n = byId(l);
    const t = n.get("train_1")!;
    for (const e of up) {
      expect([e.sourceHandle, e.targetHandle]).toEqual(["t", "l"]);
      expect(e.via!.x).toBeLessThan(t.x);
    }
    expect(up[0].via!.y).toBe(up[1].via!.y);
    expect(up[0].via!.y).toBeGreaterThan(t.y + t.height);
    for (const a of l.nodes) for (const b of l.nodes) if (a !== b) expect(overlaps(a, b), `${a.id} / ${b.id}`).toBe(false);
  });

  it("lays one doublet as one frame, the brine back down into it and the producer's up into the train", () => {
    const l = lay(get(PICK));
    expect(l.groups).toHaveLength(1);
    const back = l.edges.find((x) => x.id === "heat_pump-injector_1")!;
    expect([back.sourceHandle, back.targetHandle]).toEqual(["b", "t3"]);
    expect(l.edges.find((x) => x.id === "producer_1-train_1")!.via).toBeDefined();
    const n = byId(l);
    expect(n.get("injector_1")!.height).toBe(WELL_H);
    expect(n.get("injector_1")!.width).toBe(WELL_W);
    expect(n.get("injector_1")!.x).toBeLessThan(n.get("producer_1")!.x);
  });
});

describe("wells and trains over the year", () => {
  it("gives each well its doublet's flow, an injector half of it when there are two", () => {
    const d = get("U2");
    const node = (id: string) => d.graph.nodes.find((x) => x.id === id)!;
    const p1 = wellYear(d, node("producer_1"))!;
    const i1a = wellYear(d, node("injector_1a"))!;
    expect(injectorsOf(d, 1)).toBe(2);
    expect(i1a.flow[0]).toBeCloseTo(p1.flow[0] / 2, 6);
    expect(i1a.cap).toBe(150);
    const today = wellDay(d, node("producer_2"), 1)!;
    expect(today).toMatchObject({ flow: 300, cap: 300, on: true, stopped: false });
    expect(today.temperature).toBeCloseTo(86.84, 2);
    // Doublet 2 stops from day 146 to day 180 (0-based 145 to 179).
    expect(stoppedOn(d, 2, 150)).toBe(true);
    const off = wellDay(d, node("producer_2"), 150)!;
    expect(off).toMatchObject({ flow: 0, on: false, stopped: true, temperature: null });
    // The user's dates: doublet 1 off on two ranges (0-based 180-199 and 230-244), the gap runs.
    const mine = { ...d, year: { ...d.year, stop_ranges: [[[180, 199], [230, 244]], [[145, 179]]] } };
    expect([181, 200, 201, 230, 231, 245, 246].map((day) => stoppedOn(mine, 1, day))).toEqual([true, true, false, false, true, true, false]);
    expect(stoppedOn(mine, 2, 150)).toBe(true);
  });

  it("adds a train's doublets up, and knows which doublet runs first", () => {
    const d = get("U2");
    expect(trainMembers(d.graph, "train_1")).toEqual([1]);
    expect(trainMembers(get("U1").graph, "train_1")).toEqual([1, 2]);
    const shared = get("U1");
    const t = trainYear(shared, "train_1")!;
    expect(t.cap).toBe(600);
    expect(t.flow[0]).toBeCloseTo((shared.year.doublets![0].flow_m3h[0] ?? 0) + (shared.year.doublets![1].flow_m3h[0] ?? 0), 6);
    // Hottest first: doublet 2's producer, open over the lower half, is the hotter one.
    expect(baseLoadDoublet(d)).toBe(2);
    expect(baseLoadDoublet(shared)).toBeNull();
  });

  it("names wells and reads their open part", () => {
    const d = get("U2");
    const p2 = d.graph.nodes.find((x) => x.id === "producer_2")!;
    expect(shortLabel(p2.label)).toBe("Producer 2");
    expect(wellShort(p2)).toBe("P2");
    expect(doubletOf({ id: "injector_3b", values: {} })).toBe(3);
    expect(wellOpening(p2, d.plant.doublets![1])).toBe("lower");
    expect(wellOpening(p2, null)).toBe("lower");
    expect(wellOpening({ type: "producer_well", label: "Producer 1", values: { open_m: 50, depth_m: 2475 } }, { producer_open: "", injector_open: "", depth_m: 2500 })).toBe("upper");
  });
});

describe("editing doublets one by one", () => {
  it("starts from U2's set-up: two injectors on doublet 1, doublet 2 lower half open on its own train, hottest first", () => {
    const d = get("U2");
    const f = editForm(d);
    expect(f.dispatch).toBe("base");
    expect(f.doublets).toEqual([
      { depth_m: "2500", producer_open: "full", injector_open: "full", injectors: 2, own_train: true, max_flow_m3h: "", min_flow_m3h: "" },
      { depth_m: "2500", producer_open: "lower", injector_open: "full", injectors: 1, own_train: true, max_flow_m3h: "", min_flow_m3h: "" },
    ]);
    expect(diffChanges(editBase(d), f)).toEqual({ changes: {}, errors: {} });
    // The backend's sizes carry float noise (a heat pump of 3.3000000000000003 MW); the form doesn't show it.
    expect(f.heat_pump_mw).toBe("3.3");
  });

  it("numbers the trains in doublet order: one each when their own, one shared for the rest", () => {
    const row = { depth_m: "2500", producer_open: "full" as const, injector_open: "full" as const, injectors: 1 as const, max_flow_m3h: "" };
    const trains = (own: boolean[]) => formDoublets({ doublets: own.map((o) => ({ ...row, own_train: o })) }).doublets.map((x) => x.train);
    expect(trains([false, true, false])).toEqual([0, 1, 0]);
    expect(trains([true, true, true])).toEqual([0, 1, 2]);
    expect(trains([false, false])).toEqual([0, 0]);
    // Who shares a train is what counts, not the numbers.
    const a = formDoublets({ doublets: [{ ...row, own_train: true }, { ...row, own_train: true }] }).doublets;
    expect(sameDoublets(a, a.map((x, i) => ({ ...x, train: 5 + i })))).toBe(true);
    expect(sameDoublets(a, a.map((x) => ({ ...x, train: 0 })))).toBe(false);
  });

  it("sends the whole list and the dispatch when they change, and says what changed", () => {
    const d = get("U1");
    const base = editBase(d);
    const f = editForm(d);
    const form = {
      ...f,
      dispatch: "base" as const,
      doublets: [f.doublets[0], { ...f.doublets[1], producer_open: "lower" as const, injectors: 2 as const, own_train: true }, { ...f.doublets[1], depth_m: "3000", max_flow_m3h: "200" }],
    };
    const { changes, errors } = diffChanges(base, form);
    expect(errors).toEqual({});
    expect(changes.dispatch).toBe("base");
    expect(changes.doublets).toEqual([
      { depth_m: 2500, producer_open: "full", injector_open: "full", injectors: 1, max_flow_m3h: null, min_flow_m3h: null, train: 0 },
      { depth_m: 2500, producer_open: "lower", injector_open: "full", injectors: 2, max_flow_m3h: null, min_flow_m3h: null, train: 1 },
      { depth_m: 3000, producer_open: "full", injector_open: "full", injectors: 1, max_flow_m3h: 200, min_flow_m3h: null, train: 0 },
    ]);
    expect(describeChanges(base, changes)).toEqual([
      "Doublet 2: producer open over the lower half (was fully open); 2 injectors (was 1)",
      "Doublet 3 added: aquifer at 3,000 m, at most 200 m³/h",
      "Treatment: 2 trains (doublets 1 and 3; doublet 2)",
      "Dispatch: the hottest first (was equal shares)",
    ]);
    // One doublet: the dispatch isn't sent.
    expect(diffChanges(base, { ...f, doublets: [f.doublets[0]], dispatch: "base" }).changes.dispatch).toBeUndefined();
  });
});

// A plant as the backend draws it (gemini_agent/workbench.py graph_view): its doublets, each with
// one or two injectors, on one treatment train (or one each), and the surface plant of the pick.
function plantGraph(doublets: { injectors: 1 | 2; train?: number }[]): Pick<Graph, "nodes" | "edges"> {
  const node = (id: string, type: string, label: string, values: Record<string, number> = {}): GraphNode => ({ id, type, label, solver: type.endsWith("_well") || type === "treatment" ? "gemini" : "dioscuri", values, units: {} });
  const edges: GraphEdge[] = [];
  const edge = (source: string, target: string, kind: GraphEdge["kind"], temperature_c: number | null = null, mw: number | null = null) =>
    edges.push({ id: `${source}-${target}`, source, target, kind, mw, temperature_c, label: "" });
  const trains = [...new Set(doublets.map((d) => d.train ?? 0))].sort((a, b) => a - b);
  const nodes: GraphNode[] = [node("reservoir", "reservoir", "Reservoir", { depth_m: 2500, temperature_c: 87, thickness_m: 100 })];
  doublets.forEach((d, i) => {
    const k = i + 1;
    const train = `train_${trains.indexOf(d.train ?? 0) + 1}`;
    const injectors = d.injectors === 2 ? [`injector_${k}a`, `injector_${k}b`] : [`injector_${k}`];
    nodes.push(node(`producer_${k}`, "producer_well", `Producer ${k}`, { doublet: k, depth_m: 2500, open_m: 100 }));
    for (const id of injectors) nodes.push(node(id, "injector_well", `Injector ${id.slice(9).toUpperCase()}`, { doublet: k, depth_m: 2500, open_m: 100 }));
    edge("reservoir", `producer_${k}`, "brine", 87);
    edge(`producer_${k}`, train, "brine", 86);
    for (const id of injectors) {
      edge("heat_pump", id, "brine", 56);
      edge(id, "reservoir", "brine", 56);
    }
    edge("grid", `producer_${k}`, "electricity", null, 0.3);
  });
  trains.forEach((_, i) => {
    nodes.push(node(`train_${i + 1}`, "treatment", trains.length > 1 ? `Treatment train ${i + 1}` : "Treatment train"));
    edge(`train_${i + 1}`, "absorption", "brine", 86);
    edge(`train_${i + 1}`, "hex", "brine", 86);
    edge(`train_${i + 1}`, "gas", "gas");
  });
  for (const [id, type, label] of [
    ["absorption", "absorption", "Absorption chiller"],
    ["hex", "heat_exchanger", "Heat exchanger"],
    ["heat_pump", "heatpump", "Heat pump"],
    ["gas", "gas", "Gas"],
    ["boiler", "boiler", "Boiler"],
    ["chillers", "chillers", "Electric chillers"],
    ["grid", "grid", "Grid electricity"],
    ["tower", "tower", "Cooling towers"],
    ["demand_heat", "demand_heat", "Heat demand"],
    ["demand_cold", "demand_cold", "Cooling demand"],
  ])
    nodes.push(node(id, type, label));
  edge("hex", "heat_pump", "brine");
  edge("gas", "boiler", "gas");
  edge("chillers", "tower", "reject", null, 2.4);
  edge("absorption", "tower", "reject", null, 1.3);
  edge("grid", "chillers", "electricity", null, 0.25);
  edge("grid", "heat_pump", "electricity", null, 0.6);
  edge("grid", "tower", "electricity", null, 0.05);
  edge("hex", "demand_heat", "network", 100, 6.6);
  edge("heat_pump", "demand_heat", "network", 100, 2.7);
  edge("boiler", "demand_heat", "network", 100, 3.5);
  edge("absorption", "demand_cold", "cold", 20, 0.5);
  edge("chillers", "demand_cold", "cold", 20, 2.2);
  return { nodes, edges };
}

describe("the shape of the whole, for a laptop's canvas", () => {
  // The canvas at 1440 × 900 in full screen is about 1.5 : 1, on the page about 2 : 1; the plant
  // used to be 3 : 1 and fitted at half size.
  const aspect = (l: PlantLayout) => l.width / l.height;
  const three = layoutPlant(plantGraph([{ injectors: 2 }, { injectors: 2 }, { injectors: 2 }]));

  it("lays the pick (one doublet), two doublets (U1) and three doublets of two injectors each about as wide as a canvas", () => {
    const pick = lay(get(PICK));
    const two = lay(get("U1"));
    for (const [name, l] of [["pick", pick], ["two doublets", two], ["three doublets", three]] as const) {
      expect(aspect(l), name).toBeGreaterThan(1.2);
      expect(aspect(l), name).toBeLessThan(2.2);
    }
    // Small enough to read without zooming in full screen: about 0.86 for the pick and for two
    // doublets, 0.75 for three.
    expect(Math.min(1050 / pick.width, 700 / pick.height)).toBeGreaterThanOrEqual(0.85);
    expect(Math.min(1050 / two.width, 700 / two.height)).toBeGreaterThanOrEqual(0.85);
    expect(Math.min(1050 / three.width, 700 / three.height)).toBeGreaterThanOrEqual(0.75);
  });

  it("narrows the wells' cards to fit nine under the plant, and keeps them apart and in their frames", () => {
    const n = byId(three);
    const wells = three.nodes.filter((x) => x.node.type.endsWith("_well"));
    expect(wells).toHaveLength(9);
    for (const w of wells) {
      expect(w.width).toBeGreaterThanOrEqual(WELL_MIN_W);
      expect(w.width).toBeLessThan(WELL_W);
    }
    expect(three.groups.map((g) => g.wells.length)).toEqual([3, 3, 3]);
    for (const a of three.nodes) for (const b of three.nodes) if (a !== b) expect(overlaps(a, b), `${a.id} / ${b.id}`).toBe(false);
    // The band under them all: its facts in a row under the aquifer, the wells taking its width.
    const band = n.get("reservoir")!;
    expect(band.band?.facts).toBe("below");
    expect(band.y).toBeGreaterThan(Math.max(...wells.map((w) => w.y + w.height)));
    expect(band.x + band.width).toBeGreaterThanOrEqual(Math.max(...wells.map((w) => w.x + w.width)));
  });

  it("runs every thin line of the three-doublet plant clear of every card", () => {
    const n = byId(three);
    for (const e of three.edges.filter((x) => x.layer === 0)) {
      const pts = laidEdgePoints(e, n);
      expect(pts.length, e.id).toBeGreaterThanOrEqual(2);
      expect(routeClear(pts, n.get(e.edge.source)!, n.get(e.edge.target)!, three.nodes), e.id).toBe(true);
    }
  });
});
