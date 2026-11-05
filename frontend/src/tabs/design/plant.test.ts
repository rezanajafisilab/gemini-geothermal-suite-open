import { describe, expect, it } from "vitest";

import type { Design, DesignCheck, GraphEdge, GraphNode } from "../../workbench";
import {
  ABOVE,
  COL_W,
  NODE_H,
  NODE_W,
  RESERVOIR_H,
  RESERVOIR_NOTE_H,
  brineColor,
  cardSubline,
  depthY,
  describeChanges,
  diffChanges,
  edgeMw,
  editBase,
  editForm,
  farName,
  hasErrors,
  layoutPlant,
  pipePath,
  relatedChecks,
  reservoirHeight,
  routeClear,
  routePoints,
  seriesOf,
  sumSeries,
  type EditForm,
  type LaidEdge,
  type LaidNode,
} from "./plant";

const node = (id: string, type: string, values: Record<string, number> = {}): GraphNode => ({ id, type, label: id, solver: "dioscuri", values, units: {} });
const edge = (source: string, target: string, kind: GraphEdge["kind"], mw: number | null = null, temperature_c: number | null = null): GraphEdge => ({
  id: `${source}-${target}`,
  source,
  target,
  kind,
  mw,
  temperature_c,
  label: "",
});

// A1 as the backend draws it (gemini_agent/workbench.py graph_view): absorption hangs off the producer.
const A1 = {
  nodes: [
    node("producer", "producer_well"),
    node("injector", "injector_well"),
    node("absorption", "absorption"),
    node("hex", "heat_exchanger"),
    node("heat_pump", "heatpump"),
    node("gas", "gas"),
    node("boiler", "boiler"),
    node("chillers", "chillers"),
    node("demand_heat", "demand_heat"),
    node("demand_cold", "demand_cold"),
  ],
  edges: [
    edge("producer", "absorption", "brine", null, 86),
    edge("producer", "hex", "brine", null, 86),
    edge("hex", "heat_pump", "brine", null, 45.4),
    edge("heat_pump", "injector", "brine", null, 30),
    edge("gas", "boiler", "gas"),
    edge("hex", "demand_heat", "network", 5.99, 70),
    edge("heat_pump", "demand_heat", "network", 1.06, 70),
    edge("boiler", "demand_heat", "network", 0, 70),
    edge("absorption", "demand_cold", "cold", 0.84, 6),
    edge("chillers", "demand_cold", "cold", 0.73, 6),
  ],
};

// Every part at once, with the grid and the towers (gemini_agent/workbench.py graph_view, 30 Oct).
const FULL = {
  nodes: [
    node("reservoir", "reservoir", { depth_m: 3000, temperature_c: 102, pressure_bar: 303, assumed: 1, known_depth_m: 2500, known_temperature_c: 87 }),
    node("producer", "producer_well"),
    node("injector", "injector_well"),
    node("absorption", "absorption"),
    node("hex", "heat_exchanger"),
    node("heat_pump", "heatpump"),
    node("gas", "gas"),
    node("boiler", "boiler"),
    node("chillers", "chillers"),
    node("grid", "grid"),
    node("tower", "tower"),
    node("demand_heat", "demand_heat"),
    node("demand_cold", "demand_cold"),
  ],
  edges: [
    edge("reservoir", "producer", "brine", null, 102),
    edge("producer", "absorption", "brine", null, 101),
    edge("producer", "hex", "brine", null, 101),
    edge("hex", "heat_pump", "brine", null, 65),
    edge("heat_pump", "injector", "brine", null, 40),
    edge("injector", "reservoir", "brine", null, 40),
    edge("gas", "boiler", "gas"),
    edge("hex", "demand_heat", "network", 11),
    edge("heat_pump", "demand_heat", "network", 3),
    edge("boiler", "demand_heat", "network", 1),
    edge("absorption", "demand_cold", "cold", 1),
    edge("chillers", "demand_cold", "cold", 2),
    edge("chillers", "tower", "reject", 3),
    edge("absorption", "tower", "reject", 2),
    edge("grid", "chillers", "electricity", 0.3),
    edge("grid", "heat_pump", "electricity", 1),
    edge("grid", "producer", "electricity", 0.4),
    edge("grid", "tower", "electricity", 0.04),
  ],
};

/** The same plant topped up by a boiler alone: nothing between the grid and the chillers. */
const NO_PUMP = {
  nodes: FULL.nodes.filter((n) => n.id !== "heat_pump"),
  edges: [...FULL.edges.filter((e) => e.source !== "heat_pump" && e.target !== "heat_pump"), edge("hex", "injector", "brine", null, 65)],
};

const by = (nodes: LaidNode[]) => new Map(nodes.map((n) => [n.id, n]));
const overlaps = (a: LaidNode, b: LaidNode) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
const handles = (e: LaidEdge) => [e.sourceHandle, e.targetHandle, e.clearance];

describe("layoutPlant", () => {
  const lay = layoutPlant(A1);
  const n = by(lay.nodes);

  // Changed for the canvas's aspect (31 Oct): the surface plant in rows on top, the brine line its
  // lowest row, and the doublet under it at full width (it was on the left of the brine row).
  it("runs the brine line along the plant's lowest row and puts the doublet under it (injector, then producer)", () => {
    const line = ["hex", "heat_pump"].map((id) => n.get(id)!);
    expect(line[1].x).toBeGreaterThan(line[0].x);
    expect(line[1].y).toBe(line[0].y);
    const inj = n.get("injector")!;
    const prod = n.get("producer")!;
    expect(inj.x).toBeLessThan(prod.x);
    expect(inj.y).toBe(prod.y);
    for (const id of ["hex", "heat_pump", "absorption", "boiler", "gas", "chillers"]) expect(n.get(id)!.y + NODE_H, id).toBeLessThan(inj.y);
    expect(lay.groups.map((g) => g.wells)).toEqual([["injector", "producer"]]);
  });

  it("puts cooling on top, the boiler over the heat exchanger, and feeds the absorption chiller up from the producer's lane", () => {
    const abs = n.get("absorption")!;
    expect(abs.x).toBe(n.get("hex")!.x);
    expect(abs.y).toBeLessThan(n.get("boiler")!.y);
    expect(n.get("boiler")!.y).toBeLessThan(n.get("hex")!.y);
    expect(n.get("boiler")!.x).toBe(n.get("hex")!.x);
    const feed = lay.edges.find((e) => e.id === "producer-absorption")!;
    expect([feed.sourceHandle, feed.targetHandle]).toEqual(["t", "l"]);
    expect(feed.via!.x).toBeLessThan(abs.x);
  });

  it("puts the demands at the right, the cold one over the heat one, gas left of the boiler, and nothing on top of anything", () => {
    const right = Math.max(...lay.nodes.filter((x) => !x.id.startsWith("demand")).map((x) => x.x));
    expect(n.get("demand_heat")!.x).toBeGreaterThan(right);
    expect(n.get("demand_cold")!.x).toBeGreaterThan(right);
    expect(n.get("demand_cold")!.y + n.get("demand_cold")!.height).toBeLessThan(n.get("demand_heat")!.y);
    expect(n.get("gas")!.x).toBeLessThan(n.get("boiler")!.x);
    expect(n.get("gas")!.y).toBe(n.get("boiler")!.y);
    for (const a of lay.nodes) for (const b of lay.nodes) if (a !== b) expect(overlaps(a, b), `${a.id} / ${b.id}`).toBe(false);
  });

  it("gives every pipe into a demand its own lane, units above first (rightmost highest), then below", () => {
    const heat = lay.edges.filter((e) => e.edge.target === "demand_heat");
    const lane = (src: string) => heat.find((e) => e.edge.source === src)!.targetHandle;
    // The boiler is over the heat corridor; the heat exchanger and the heat pump under it, leftmost first.
    expect(lane("boiler")).toBe("lane-0");
    expect(lane("hex")).toBe("lane-1");
    expect(lane("heat_pump")).toBe("lane-2");
    expect(heat.find((e) => e.edge.source === "boiler")!.sourceHandle).toBe("b");
    expect(heat.find((e) => e.edge.source === "hex")!.sourceHandle).toBe("tq");
    const d = n.get("demand_heat")!;
    expect(d.lanes).toHaveLength(3);
    expect(d.lanes[0]).toBeLessThan(d.lanes[1]);
    // The lanes are inside the node and run between the middle row and the brine row.
    const laneY = d.lanes.map((l) => d.y + l);
    for (const y of laneY) {
      expect(y).toBeGreaterThan(n.get("boiler")!.y + NODE_H);
      expect(y).toBeLessThan(n.get("hex")!.y);
    }
  });

  it("joins the brine line side to side", () => {
    const e = lay.edges.find((x) => x.id === "hex-heat_pump")!;
    expect([e.sourceHandle, e.targetHandle]).toEqual(["r", "l"]);
  });

  it("squeezes out empty columns: the gas reference has no well", () => {
    const ref = layoutPlant({
      nodes: [node("gas", "gas"), node("boiler", "boiler"), node("chillers", "chillers"), node("demand_heat", "demand_heat"), node("demand_cold", "demand_cold")],
      edges: [edge("gas", "boiler", "gas"), edge("boiler", "demand_heat", "network", 7), edge("chillers", "demand_cold", "cold", 1.5)],
    });
    const m = by(ref.nodes);
    expect(m.get("gas")!.x).toBe(0);
    expect(m.get("boiler")!.x).toBe(COL_W);
    expect(m.get("chillers")!.x).toBe(2 * COL_W);
    expect(m.get("demand_heat")!.x).toBeGreaterThan(m.get("chillers")!.x + NODE_W);
    for (const a of ref.nodes) for (const b of ref.nodes) if (a !== b) expect(overlaps(a, b)).toBe(false);
  });

  it("is the same for the same graph, and keeps unknown types on the canvas", () => {
    expect(layoutPlant(A1)).toEqual(lay);
    const odd = layoutPlant({ nodes: [...A1.nodes, node("grid", "grid"), node("x", "mystery")], edges: A1.edges });
    expect(odd.nodes.map((x) => x.id)).toContain("x");
    for (const a of odd.nodes) for (const b of odd.nodes) if (a !== b) expect(overlaps(a, b), `${a.id} / ${b.id}`).toBe(false);
  });
});

describe("the grid, the towers and their thin lines", () => {
  const full = layoutPlant(FULL);
  const n = by(full.nodes);
  const laidEdge = (lay: ReturnType<typeof layoutPlant>, id: string) => lay.edges.find((e) => e.id === id)!;

  it("puts the towers on the top row next to the chillers, and the grid under the towers, over the heat pump's row", () => {
    expect(n.get("tower")!.y).toBe(n.get("chillers")!.y);
    expect(n.get("tower")!.x).toBe(n.get("chillers")!.x + COL_W);
    expect(n.get("grid")!.x).toBe(n.get("tower")!.x);
    expect(n.get("grid")!.y).toBe(n.get("boiler")!.y);
    expect(n.get("grid")!.y + NODE_H).toBeLessThan(n.get("heat_pump")!.y);
    for (const a of full.nodes) for (const b of full.nodes) if (a !== b) expect(overlaps(a, b), `${a.id} / ${b.id}`).toBe(false);
  });

  it("runs every electricity and tower line clear of every card", () => {
    for (const lay of [full, layoutPlant(NO_PUMP)]) {
      const m = by(lay.nodes);
      const thin = lay.edges.filter((e) => e.edge.kind === "electricity" || e.edge.kind === "reject");
      expect(thin.length).toBeGreaterThanOrEqual(5);
      for (const e of thin) {
        const s = m.get(e.edge.source)!;
        const t = m.get(e.edge.target)!;
        const pts = routePoints(s, t, e);
        expect(pts.length, e.id).toBeGreaterThanOrEqual(2);
        expect(routeClear(pts, s, t, lay.nodes), e.id).toBe(true);
      }
    }
  });

  it("goes straight up to the towers, and in an L through the column gap to the heat pump and to the chillers", () => {
    expect(handles(laidEdge(full, "grid-tower"))).toEqual(["t3", "b3", undefined]);
    expect(handles(laidEdge(full, "grid-heat_pump"))).toEqual(["l", "r3", undefined]);
    expect(handles(laidEdge(full, "grid-chillers"))).toEqual(["l", "r3", undefined]);
    expect(handles(laidEdge(layoutPlant(NO_PUMP), "grid-chillers"))).toEqual(["l", "r3", undefined]);
  });

  it("reaches the well pumps along their own run over the doublet, and takes the absorption chiller's heat over the top", () => {
    const toPumps = laidEdge(full, "grid-producer");
    expect(handles(toPumps)).toEqual(["b", "t3", undefined]);
    // The run is under the plant and over the wells (and the brine lanes), not along the band.
    expect(toPumps.via!.y).toBeGreaterThan(n.get("heat_pump")!.y + NODE_H);
    expect(toPumps.via!.y).toBeLessThan(n.get("producer")!.y);
    const lanes = full.edges.filter((e) => e.edge.kind === "brine" && e.via).map((e) => e.via!.y);
    expect(toPumps.via!.y).toBeGreaterThan(Math.max(...lanes));
    expect(handles(laidEdge(full, "chillers-tower"))).toEqual(["r", "l", undefined]);
    expect(handles(laidEdge(full, "absorption-tower"))).toEqual(["t", "t", ABOVE]);
  });

  it("works for the gas plant too: no wells, the towers next to the chillers and the grid under them", () => {
    const ref = layoutPlant({
      nodes: [node("gas", "gas"), node("boiler", "boiler"), node("chillers", "chillers"), node("grid", "grid"), node("tower", "tower"), node("demand_heat", "demand_heat"), node("demand_cold", "demand_cold")],
      edges: [edge("gas", "boiler", "gas"), edge("boiler", "demand_heat", "network", 7), edge("chillers", "demand_cold", "cold", 1.5), edge("chillers", "tower", "reject", 2), edge("grid", "chillers", "electricity", 0.2), edge("grid", "tower", "electricity", 0.02)],
    });
    const m = by(ref.nodes);
    expect(m.get("tower")!.x).toBe(m.get("chillers")!.x + COL_W);
    expect(m.get("grid")!.x).toBe(m.get("tower")!.x);
    expect(handles(laidEdge(ref, "grid-chillers"))).toEqual(["l", "r3", undefined]);
    expect(handles(laidEdge(ref, "grid-tower"))).toEqual(["t3", "b3", undefined]);
    for (const e of ref.edges.filter((x) => x.edge.kind === "electricity" || x.edge.kind === "reject")) {
      expect(routeClear(routePoints(m.get(e.edge.source)!, m.get(e.edge.target)!, e), m.get(e.edge.source)!, m.get(e.edge.target)!, ref.nodes), e.id).toBe(true);
    }
  });

  it("makes the reservoir band taller when the aquifer is assumed, for its note", () => {
    expect(reservoirHeight(FULL.nodes[0])).toBe(RESERVOIR_H + RESERVOIR_NOTE_H);
    expect(reservoirHeight(node("r", "reservoir", { depth_m: 2500 }))).toBe(RESERVOIR_H);
    expect(n.get("reservoir")!.height).toBe(RESERVOIR_H + RESERVOIR_NOTE_H);
  });
});

describe("the band, the names zoomed out and the brine's colour", () => {
  it("draws the aquifer tall enough that a half-open well reads apart from a fully open one", () => {
    expect(RESERVOIR_H).toBeGreaterThanOrEqual(90);
    expect(RESERVOIR_H).toBeLessThanOrEqual(120);
    const half = depthY(2550, [2500], 100) - depthY(2500, [2500], 100);
    expect(half).toBeGreaterThanOrEqual(35);
  });

  it("names each part in a dozen letters or fewer zoomed out", () => {
    const named = (id: string, type: string, label = id) => farName({ id, type, label, values: {} });
    expect(named("hex", "heat_exchanger")).toBe("Exchanger");
    expect(named("train_2", "treatment", "Treatment train 2")).toBe("Train 2");
    expect(named("train_1", "treatment", "Treatment train")).toBe("Treatment");
    expect(named("producer_2", "producer_well", "Producer 2, lower half open")).toBe("Producer 2");
    expect(farName({ id: "injector_1a", type: "injector_well", label: "Injector 1A", values: { doublet: 1 } }, true)).toBe("I1A");
    for (const n of FULL.nodes) expect(farName(n).length, n.id).toBeLessThanOrEqual(12);
  });

  it("keeps the brine one brown-grey at every temperature, never the networks' orange or blue", () => {
    for (const t of [20, 45, 56, 75, 87, 105, 130, null]) {
      const [r, g, b] = brineColor(t).match(/\d+/g)!.map(Number);
      expect(r, String(t)).toBeGreaterThanOrEqual(g);
      expect(g, String(t)).toBeGreaterThanOrEqual(b);
      expect(r - b, String(t)).toBeLessThanOrEqual(60);
    }
    expect(brineColor(105)).not.toBe(brineColor(45));
  });
});

describe("pipePath", () => {
  it("draws a straight pipe between two handles at one height", () => {
    expect(pipePath(0, 10, "r", 100, 10, "l").path).toBe("M0,10 L100,10");
  });

  it("drops then runs along the lane (an L with a rounded corner), the label on the run", () => {
    const p = pipePath(100, 0, "b", 400, 200, "l", 12);
    expect(p.path).toBe("M100,0 L100,188 Q100,200 112,200 L400,200");
    expect(p.labelY).toBe(200);
    expect(p.labelX).toBeGreaterThan(100);
    expect(p.labelX).toBeLessThan(400);
  });

  it("steps at mid-x between rows", () => {
    expect(pipePath(0, 100, "r", 200, 0, "l", 0).path).toBe("M0,100 L100,100 L100,0 L200,0");
  });

  it("goes round the outside when both handles are on the same side, the label on the far run", () => {
    const over = pipePath(100, 0, "t", 300, 0, "t", 0, 24);
    expect(over.path).toBe("M100,0 L100,-24 L300,-24 L300,0");
    expect([over.labelX, over.labelY]).toEqual([200, -24]);
    expect(pipePath(100, 50, "r", 100, 10, "r", 0, 30).path).toBe("M100,50 L130,50 L130,10 L100,10");
    expect(pipePath(100, 50, "b", 20, 40, "b", 0, 24).path).toBe("M100,50 L100,74 L20,74 L20,40");
    expect(pipePath(100, 50, "l", 300, 10, "l", 0, 30).path).toBe("M100,50 L70,50 L70,10 L300,10");
  });
});

describe("relatedChecks", () => {
  const checks: DesignCheck[] = [
    "Heat adds up",
    "Heat pump COP below the Carnot limit",
    "Brine cools along its path",
    "Reinjection at or above 30 °C",
    "No temperature cross in the heat exchanger",
    "No unit gives more than its size allows",
    "Absorption chiller driven hot enough",
    "Heat coverage at least 95%",
    "Cold coverage at least 95%",
  ].map((name) => ({ name, passed: true, detail: "" }));
  const names = (type: string) => relatedChecks(type, checks).map((c) => c.name);

  it("matches by words in the check's name", () => {
    expect(names("heatpump")).toEqual(["Heat pump COP below the Carnot limit", "No unit gives more than its size allows"]);
    expect(names("injector_well")).toEqual(["Brine cools along its path", "Reinjection at or above 30 °C"]);
    expect(names("demand_heat")).toEqual(["Heat adds up", "Heat coverage at least 95%"]);
    expect(names("absorption")).toContain("Absorption chiller driven hot enough");
    expect(names("chillers")).not.toContain("Absorption chiller driven hot enough");
    expect(names("gas")).toEqual([]);
  });
});

// ------------------------------------------------------------------ edits

const design = (): Design =>
  ({
    id: "A1",
    code: "A1",
    reservoir_delta_c: 0,
    plant: { depth_m: 2500, heat_pump: true, boiler: true, absorption: true, chillers: true, transmissivity_dm: null, sizes_mw: { heat_exchanger: 9, heat_pump: 4, boiler: 0.5, absorption: 2, chillers: 2.5 } },
    year: {
      peak_heat_mw: 14,
      peak_cool_mw: 4,
      daily_mw: {
        heat: { demand: [1, 2], geo: [1, 1], hp: [0, 1], boiler: [0, 0] },
        cool: { demand: [0, 1], abs: [0, 1], chill: [0, 0] },
        power: { hp: [0, 0.5], chillers: [0.1, 0.3], towers: [0.01, 0.04], pumps: [0.4, 0.4] },
        reject: { abs: [0, 1], chillers: [0.5, 2] },
      },
    },
    graph: { nodes: A1.nodes, edges: A1.edges, gemini_project: null },
  }) as unknown as Design;

// Changed with the doublets (30 Oct): the form edits each doublet (depth, open parts, injectors,
// own train, cap) in place of one "Doublets" count and one "Well depth"; they go as `doublets`.
describe("design edits", () => {
  const depth = (form: EditForm, i: number, v: string) => ({ ...form, doublets: form.doublets.map((d, j) => (j === i ? { ...d, depth_m: v } : d)) });

  it("starts from the design: its doublets one by one, the dispatch and each unit's size", () => {
    const b = editBase(design());
    expect(b).toMatchObject({ heat_pump_mw: 4, boiler_mw: 0.5, return_c: null, dispatch: "equal" });
    expect(b.doublets).toEqual([{ depth_m: 2500, producer_open: "full", injector_open: "full", injectors: 1, max_flow_m3h: null, min_flow_m3h: null, train: 0 }]);
    const f = editForm(design());
    expect(f).toMatchObject({ name: "A1, edited", boiler_mw: "0.5", return_c: "", dispatch: "equal" });
    expect(f.doublets).toEqual([{ depth_m: "2500", producer_open: "full", injector_open: "full", injectors: 1, own_train: false, max_flow_m3h: "", min_flow_m3h: "" }]);
  });

  it("sends only what differs from the base", () => {
    const d = design();
    const base = editBase(d);
    expect(diffChanges(base, editForm(d))).toEqual({ changes: {}, errors: {} });
    const form = { ...depth(editForm(d), 0, "3000"), boiler_mw: "0", reservoir_delta_c: "−5" };
    const { changes, errors } = diffChanges(base, form);
    expect(errors).toEqual({});
    expect(changes).toEqual({ boiler_mw: 0, reservoir_delta_c: -5, doublets: [{ depth_m: 3000, producer_open: "full", injector_open: "full", injectors: 1, max_flow_m3h: null, min_flow_m3h: null, train: 0 }] });
    expect(describeChanges(base, changes)).toEqual(["Doublet 1: aquifer at 3,000 m (was 2,500 m)", "Reservoir 0 → −5 °C", "Gas boiler 0.5 → 0 MW"]);
  });

  it("says what can't be sent", () => {
    const d = design();
    const base = editBase(d);
    expect(diffChanges(base, depth(editForm(d), 0, "9000")).errors.doublets?.[0].depth_m).toMatch(/7,000/);
    expect(diffChanges(base, depth(editForm(d), 0, "deep")).errors.doublets?.[0].depth_m).toBe("A depth in metres.");
    const four = { ...editForm(d), doublets: Array.from({ length: 4 }, () => editForm(d).doublets[0]) };
    expect(diffChanges(base, four).errors.count).toMatch(/1 to 3/);
    expect(diffChanges(base, { ...editForm(d), return_c: "100" }).errors.return_c).toMatch(/below the 100 °C supply/);
    const capped = { ...editForm(d), doublets: [{ ...editForm(d).doublets[0], max_flow_m3h: "400" }] };
    expect(diffChanges(base, capped).errors.doublets?.[0].max_flow_m3h).toMatch(/50 to 300/);
    expect(hasErrors(diffChanges(base, capped).errors)).toBe(true);
    expect(hasErrors(diffChanges(base, editForm(d)).errors)).toBe(false);
  });
});

describe("seriesOf", () => {
  it("maps units to the dispatch: heat exchanger = geo, heat pump = hp, absorption = abs", () => {
    const d = design();
    expect(seriesOf(d, { type: "heat_exchanger" })).toMatchObject({ values: [1, 1], capacity: 9, kind: "heat" });
    expect(seriesOf(d, { type: "heatpump" })!.values).toEqual([0, 1]);
    expect(seriesOf(d, { type: "absorption" })).toMatchObject({ values: [0, 1], kind: "cold" });
    expect(seriesOf(d, { type: "demand_heat" })!.capacity).toBe(14);
    expect(seriesOf(d, { type: "producer_well" })).toBeNull();
  });

  it("adds up what draws electricity for the grid, and what the towers take, the year's peak as 100 %", () => {
    const d = design();
    const round = (v: number[]) => v.map((x) => Math.round(x * 1000) / 1000);
    const grid = seriesOf(d, { type: "grid" })!;
    expect(round(grid.values)).toEqual([0.51, 1.24]);
    expect(grid.capacity).toBeCloseTo(1.24);
    expect(grid.kind).toBe("power");
    expect(seriesOf(d, { type: "tower" })).toMatchObject({ values: [0.5, 3], capacity: 3, kind: "reject" });
    expect(sumSeries(undefined)).toBeNull();
    expect(sumSeries({ a: [1, 2], b: [3] })).toEqual([4, 2]);
    // An older server without the series: no ring, the card shows its values.
    const old = design();
    delete (old.year.daily_mw as { power?: unknown }).power;
    expect(seriesOf(old, { type: "grid" })).toBeNull();
  });
});

describe("edgeMw", () => {
  const d = design();
  const nodes = new Map(FULL.nodes.map((x) => [x.id, x]));
  const on = (id: string, day: number) => edgeMw(d, FULL.edges.find((e) => e.id === id)!, nodes, day);

  it("follows the day: electricity by the unit at its end, the towers' heat by the chiller at its start", () => {
    expect(on("grid-chillers", 1)).toBe(0.1);
    expect(on("grid-chillers", 2)).toBe(0.3);
    expect(on("grid-producer", 2)).toBe(0.4);
    expect(on("grid-tower", 2)).toBe(0.04);
    expect(on("chillers-tower", 2)).toBe(2);
    expect(on("absorption-tower", 1)).toBe(0);
  });

  it("keeps the yearly figure for brine, and when the server sent no daily series", () => {
    expect(on("producer-hex", 2)).toBeNull();
    const old = design();
    delete (old.year.daily_mw as { power?: unknown }).power;
    expect(edgeMw(old, FULL.edges.find((e) => e.id === "grid-chillers")!, nodes, 2)).toBe(0.3);
  });
});

describe("cardSubline", () => {
  const gridNode: GraphNode = { ...node("grid", "grid", { electricity_gwh: 6.79, chillers_gwh: 2.77, pumps_gwh: 3.69, heat_pump_gwh: 0, towers_gwh: 0.33, co2_t: 1358 }), units: { pumps_gwh: "GWh/yr" } };

  it("lists who draws the grid's electricity, largest first, leaving out who draws none", () => {
    expect(cardSubline(gridNode, [])).toBe("well pumps 3.69 · chillers 2.77 · towers 0.33 GWh/yr");
  });

  it("says what the towers take and use, where the gas comes from, and lists the rest", () => {
    const tower: GraphNode = { ...node("tower", "tower", { rejected_gwh: 26.5, electricity_gwh: 0.331 }), units: { rejected_gwh: "GWh/yr", electricity_gwh: "GWh/yr" } };
    expect(cardSubline(tower, [])).toBe("26.5 GWh/yr rejected · 0.331 GWh/yr of electricity");
    expect(cardSubline(node("gas", "gas"), [])).toBe("Produced gas first, then bought");
    expect(cardSubline(node("hp", "heatpump"), [{ key: "power_mw", text: "4 MW" }, { key: "cop", text: "COP 4.3" }])).toBe("4 MW size · COP 4.3");
  });
});

describe("crossings: hops over the pipe below", () => {
  it("puts a half circle on the run at each crossing, always over the top or to the left", async () => {
    const { hoppedPath, hopHalo, roundedPath, HOP_R } = await import("./plant");
    const pts: [number, number][] = [
      [0, 0],
      [100, 0],
      [100, 80],
    ];
    expect(hoppedPath(pts, 12, [])).toBe(roundedPath(pts, 12));
    const d = hoppedPath(pts, 12, [{ x: 40, y: 0, dir: "h" }, { x: 100, y: 50, dir: "v" }]);
    expect(d).toContain(`L${40 - HOP_R},0 A${HOP_R} ${HOP_R} 0 0 1 ${40 + HOP_R},0`);
    expect(d).toContain(`L100,${50 - HOP_R} A${HOP_R} ${HOP_R} 0 0 0 100,${50 + HOP_R}`);
    // Going the other way, the hop still goes over the top.
    const back = hoppedPath([[100, 0], [0, 0]], 12, [{ x: 40, y: 0, dir: "h" }]);
    expect(back).toContain(`A${HOP_R} ${HOP_R} 0 0 0 ${40 - HOP_R},0`);
    expect(hopHalo([{ x: 40, y: 0, dir: "h" }])).toBe(`M${40 - HOP_R},0 A${HOP_R} ${HOP_R} 0 0 1 ${40 + HOP_R},0`);
  });
});
