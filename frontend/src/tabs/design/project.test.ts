import { beforeAll, describe, expect, it } from "vitest";

import { loadFixtures, type CatalogueType, type GeminiProject, type GeminiRun } from "../../workbench";
import {
  addComponent,
  compactPorts,
  compareOutput,
  componentPorts,
  componentRole,
  connect,
  impossibleOutput,
  isBrineLoop,
  keyOutputs,
  layoutLoop,
  layoutProject,
  portUnit,
  parseProject,
  projectEdges,
  readOutput,
  removeComponents,
  removePairs,
  renameComponent,
  setBoundary,
  uniqueName,
} from "./project";

const project = (): GeminiProject => ({
  components: {
    producer_well: { type: "producer_well", parameters: { esp_freq_hz: 65 } },
    filter_a: { type: "filter" },
    heat_exchanger: { type: "heat_exchanger" },
    injector_well: { type: "injector_well" },
  },
  boundary_inputs: [
    { component: "producer_well", key: "wellhead_pressure", value: 3 },
    { component: "heat_exchanger", key: "secondary_temperature_in", value: 40 },
  ],
  connections: [
    { predecessor: "producer_well", successor: "filter_a", ports: [["flow_rate_m3s", "flow_rate"], ["temperature_out", "temperature"]] },
    { predecessor: "filter_a", successor: "heat_exchanger", predecessor_output: "temperature_out", successor_input: "primary_temperature_in" },
    { predecessor: "heat_exchanger", successor: "injector_well", ports: [["primary_temperature_out", "wellhead_temperature"]] },
  ],
});

const filterType: CatalogueType = {
  type: "filter",
  label: "Filter",
  group: "surface",
  description: "",
  inputs: [
    { key: "flow_rate", unit: "m³/s", description: "" },
    { key: "pressure", unit: "bar", description: "" },
  ],
  outputs: [
    { key: "flow_rate", unit: "m³/s", description: "" },
    { key: "pressure_out", unit: "bar", description: "" },
  ],
  parameters: [
    { key: "base_resistance", unit: "", default: 36, description: "" },
    { key: "nested", unit: "", default: { a: [1, 2] }, description: "" },
    { key: "unset", unit: "", default: null, description: "" },
  ],
};

describe("projectEdges", () => {
  it("draws one edge per port pair, in order, whichever way a connection is written", () => {
    const e = projectEdges(project());
    expect(e.map((x) => `${x.source}.${x.out}->${x.target}.${x.in}`)).toEqual([
      "producer_well.flow_rate_m3s->filter_a.flow_rate",
      "producer_well.temperature_out->filter_a.temperature",
      "filter_a.temperature_out->heat_exchanger.primary_temperature_in",
      "heat_exchanger.primary_temperature_out->injector_well.wellhead_temperature",
    ]);
    expect(e.map((x) => x.id)).toEqual(["0:0", "0:1", "1:0", "2:0"]);
  });
});

describe("addComponent", () => {
  it("adds a component with the catalogue's defaults and a unique name", () => {
    const p = project();
    const a = addComponent(p, filterType);
    expect(a.name).toBe("filter");
    expect(a.project.components.filter).toEqual({ type: "filter", parameters: { base_resistance: 36, nested: { a: [1, 2] } } });
    const b = addComponent(a.project, filterType);
    expect(b.name).toBe("filter_2");
    expect(uniqueName(b.project, "filter")).toBe("filter_3");
    // The defaults are copies, and the original project is left alone.
    (b.project.components.filter_2.parameters!.nested as { a: number[] }).a.push(3);
    expect(filterType.parameters[1].default).toEqual({ a: [1, 2] });
    expect(Object.keys(p.components)).not.toContain("filter");
  });
});

describe("connect", () => {
  it("appends a new connection at the end and keeps the order of the others", () => {
    const p = project();
    const q = connect(p, "filter_a", "pressure_out", "heat_exchanger", "pressure_in");
    expect(q.connections.slice(0, 3)).toEqual(p.connections);
    expect(q.connections[3]).toEqual({ predecessor: "filter_a", successor: "heat_exchanger", ports: [["pressure_out", "pressure_in"]] });
    expect(p.connections).toHaveLength(3);
  });

  it("ignores a pair that is already there, a loop on one component, and unknown components", () => {
    const p = project();
    expect(connect(p, "producer_well", "temperature_out", "filter_a", "temperature")).toBe(p);
    expect(connect(p, "filter_a", "flow_rate", "filter_a", "flow_rate")).toBe(p);
    expect(connect(p, "nowhere", "x", "filter_a", "flow_rate")).toBe(p);
  });
});

describe("delete", () => {
  it("removes one port pair, keeping the rest of its connection and the order", () => {
    const p = project();
    const q = removePairs(p, [{ source: "producer_well", target: "filter_a", out: "flow_rate_m3s", in: "flow_rate" }]);
    expect(q.connections).toHaveLength(3);
    expect(q.connections[0].ports).toEqual([["temperature_out", "temperature"]]);
    expect(q.connections[1]).toBe(p.connections[1]);
  });

  it("drops a connection once its last pair goes (either form)", () => {
    const p = project();
    const q = removePairs(p, [
      { source: "filter_a", target: "heat_exchanger", out: "temperature_out", in: "primary_temperature_in" },
      { source: "heat_exchanger", target: "injector_well", out: "primary_temperature_out", in: "wellhead_temperature" },
    ]);
    expect(q.connections.map((c) => `${c.predecessor}>${c.successor}`)).toEqual(["producer_well>filter_a"]);
  });

  it("removes a component with its boundary inputs and connections; the rest keep their order", () => {
    const p = project();
    const q = removeComponents(p, ["filter_a"]);
    expect(Object.keys(q.components)).toEqual(["producer_well", "heat_exchanger", "injector_well"]);
    expect(q.connections.map((c) => `${c.predecessor}>${c.successor}`)).toEqual(["heat_exchanger>injector_well"]);
    expect(q.boundary_inputs).toHaveLength(2);
    const r = removeComponents(p, ["producer_well"]);
    expect(r.boundary_inputs.map((b) => b.component)).toEqual(["heat_exchanger"]);
  });

  it("then a new connection still goes at the end", () => {
    const q = connect(removeComponents(project(), ["filter_a"]), "producer_well", "temperature_out", "heat_exchanger", "primary_temperature_in");
    expect(q.connections.map((c) => `${c.predecessor}>${c.successor}`)).toEqual(["heat_exchanger>injector_well", "producer_well>heat_exchanger"]);
  });
});

describe("renameComponent and boundaries", () => {
  it("renames everywhere, keeping the order", () => {
    const q = renameComponent(project(), "filter_a", "strainer");
    expect(Object.keys(q.components)).toEqual(["producer_well", "strainer", "heat_exchanger", "injector_well"]);
    expect(q.connections[0].successor).toBe("strainer");
    expect(q.connections[1].predecessor).toBe("strainer");
    expect(renameComponent(project(), "filter_a", "heat_exchanger").components.filter_a).toBeDefined();
  });

  it("sets a boundary value, or adds one", () => {
    const p = project();
    expect(setBoundary(p, "producer_well", "wellhead_pressure", 4).boundary_inputs[0].value).toBe(4);
    expect(setBoundary(p, "filter_a", "pressure", 2).boundary_inputs[2]).toEqual({ component: "filter_a", key: "pressure", value: 2 });
  });
});

describe("componentPorts", () => {
  it("lists the ports in use first, then the catalogue's, with boundary values", () => {
    const ports = componentPorts(project(), "filter_a", filterType);
    expect(ports.inputs.map((x) => x.key)).toEqual(["flow_rate", "temperature", "pressure"]);
    expect(ports.inputs[0]).toMatchObject({ connected: true, boundary: null, unit: "m³/s" });
    expect(ports.outputs.map((x) => [x.key, x.connected])).toEqual([
      ["temperature_out", true],
      ["flow_rate", false],
      ["pressure_out", false],
    ]);
    expect(componentPorts(project(), "producer_well", undefined).inputs).toEqual([{ key: "wellhead_pressure", connected: false, boundary: 3, unit: "" }]);
  });

  it("keeps only the ports in use when compact, all of them for a component not wired yet", () => {
    const compact = compactPorts(componentPorts(project(), "filter_a", filterType));
    expect(compact.inputs.map((x) => x.key)).toEqual(["flow_rate", "temperature"]);
    expect(compact.outputs.map((x) => x.key)).toEqual(["temperature_out"]);
    const lone = componentPorts(addComponent(project(), filterType).project, "filter", filterType);
    expect(compactPorts(lone)).toEqual(lone);
  });
});

describe("layoutProject", () => {
  it("lays components out left to right along the connections", () => {
    const pos = layoutProject(project(), () => 100);
    expect(pos.producer_well.x).toBeLessThan(pos.filter_a.x);
    expect(pos.filter_a.x).toBeLessThan(pos.heat_exchanger.x);
    expect(pos.heat_exchanger.x).toBeLessThan(pos.injector_well.x);
    const extra = layoutProject(addComponent(project(), filterType).project, () => 100);
    expect(extra.filter).toEqual({ x: 0, y: 140 });
  });

  it("wraps a long chain into bands: six in a row become two rows of three", () => {
    let p: GeminiProject = { components: {}, boundary_inputs: [], connections: [] };
    const names = ["a", "b", "c", "d", "e", "f"];
    for (const n of names) p = addComponent(p, filterType, n).project;
    for (let i = 1; i < names.length; i++) p = connect(p, names[i - 1], "flow_rate", names[i], "flow_rate");
    const pos = layoutProject(p, () => 100);
    expect(pos.a.y).toBe(pos.c.y);
    expect(pos.d.x).toBe(pos.a.x);
    expect(pos.d.y).toBeGreaterThan(pos.a.y + 100);
    expect(pos.f.x).toBe(pos.c.x);
  });
});

describe("parseProject", () => {
  it("reads a project and says plainly what's wrong with a bad one", () => {
    expect("project" in parseProject(JSON.stringify(project()))).toBe(true);
    expect(parseProject("{")).toMatchObject({ error: expect.stringMatching(/isn't JSON/) });
    expect(parseProject("[]")).toMatchObject({ error: expect.stringMatching(/JSON object/) });
    const bad = { ...project(), connections: [{ predecessor: "producer_well", successor: "ghost", ports: [["a", "b"]] }] };
    expect(parseProject(JSON.stringify(bad))).toEqual({ error: "A connection ends at ghost, which isn't a component." });
  });
});

describe("outputs", () => {
  it("picks the key outputs and reads W as MW", () => {
    const out = { flow_rate: 195.5, flow_rate_m3s: 0.054, temperature_out: 86, esp_power_el: 195352, power_el: 195352, pressure_out: 3 };
    expect(keyOutputs("producer_well", out)).toEqual(["flow_rate", "temperature_out", "esp_power_el"]);
    expect(keyOutputs("filter", { flow_rate: 0.05, flow_rate_m3h: 195, temperature_out: 84, power_el: 0 })).toEqual(["flow_rate_m3h", "temperature_out"]);
    expect(readOutput("producer_well", "esp_power_el", 195352, "W")).toEqual({ text: "0.195", unit: "MW" });
    expect(readOutput("producer_well", "flow_rate", 195.47, "m³/s")).toEqual({ text: "195.5", unit: "m³/h" });
    expect(readOutput("injector_well", "wellhead_pressure_pa", 4205291, "Pa")).toEqual({ text: "42.1", unit: "bar" });
  });

  it("compares fixed with released and flags big differences", () => {
    expect(compareOutput(195.5, 116.8)).toMatchObject({ text: "+67%", big: true });
    expect(compareOutput(86, 86)).toMatchObject({ text: "same", big: false });
    expect(compareOutput(42.05, 0.001)).toMatchObject({ text: ">+999%", big: true });
    expect(compareOutput(1, 0)).toMatchObject({ text: "from 0", big: true });
    expect(compareOutput(1, undefined)).toBeNull();
  });
});

// ------------------------------------------------------------------ the brine loop (the real fixtures)

describe("the brine loop as GEMINI runs it", () => {
  // U1: two doublets sharing one treatment train; U2: two doublets, a train each.
  let shared: GeminiProject;
  let trains: GeminiProject;
  let run: GeminiRun;
  beforeAll(async () => {
    const f = await loadFixtures();
    shared = f.workbench.designs.find((d) => d.id === "U1")!.graph.gemini_project!;
    trains = f.workbench.designs.find((d) => d.id === "U2")!.graph.gemini_project!;
    run = f.geminiRunTrains;
  });
  const h = () => 200;

  it("lays it out the way the brine flows: producers, each train in its lane, the shared parts, the injectors", () => {
    expect(isBrineLoop(trains)).toBe(true);
    const pos = layoutLoop(trains, h);
    const x = (n: string) => pos[n].x;
    const y = (n: string) => pos[n].y;
    const chain = ["producer_well_1", "separator_1", "filter_a_1", "brine_header", "heat_exchanger", "filter_b", "brine_splitter", "injector_well_1a"];
    for (let i = 1; i < chain.length; i++) expect(x(chain[i]), chain[i]).toBeGreaterThan(x(chain[i - 1]));
    // Each train level with its producer; the two trains in lanes one above the other.
    expect(y("separator_1")).toBe(y("producer_well_1"));
    expect(y("filter_a_2")).toBe(y("producer_well_2"));
    expect(y("separator_2")).toBeGreaterThan(y("separator_1"));
    // The shared parts between the two lanes; the injectors stacked, centred on them.
    expect(y("heat_exchanger")).toBe((y("producer_well_1") + y("producer_well_2")) / 2);
    expect(x("injector_well_1a")).toBe(x("injector_well_2"));
    expect(y("injector_well_1b") - y("injector_well_1a")).toBe(y("injector_well_2") - y("injector_well_1b"));
    expect((y("injector_well_1a") + y("injector_well_2")) / 2).toBe(y("heat_exchanger"));
    // The gas side under the line.
    expect(y("gas_adder")).toBeGreaterThan(y("producer_well_2"));
    expect(y("boiler")).toBe(y("gas_adder"));
    expect(x("boiler")).toBe(x("heat_exchanger"));
  });

  it("joins a shared train's producers in a mixer level between them, and squeezes out unused columns", () => {
    const pos = layoutLoop(shared, h);
    expect(pos.brine_mixer.y).toBe((pos.producer_well_1.y + pos.producer_well_2.y) / 2);
    expect(pos.brine_mixer.x).toBeGreaterThan(pos.producer_well_1.x);
    // No header in a one-train loop: the exchanger comes right after the first filter.
    expect(pos.heat_exchanger.x - pos.filter_a.x).toBe(pos.filter_a.x - pos.separator.x);
  });

  it("says what each component does there", () => {
    expect(componentRole(trains, "brine_header")).toBe("joins 2 treatment trains");
    expect(componentRole(shared, "brine_mixer")).toBe("joins 2 producers");
    expect(componentRole(trains, "brine_splitter")).toBe("shares the brine among 3 injectors");
    expect(componentRole(trains, "gas_adder")).toBe("adds the gas of 2 separators");
    expect(componentRole(trains, "separator_2")).toBe("treatment train 2");
    expect(componentRole(trains, "injector_well_1b")).toBe("doublet 1, B");
    expect(componentRole(trains, "filter_b")).toBe("after the exchanger");
  });

  it("shows the outputs that say most about a mixer, a splitter and an adder, in units that read", () => {
    expect(keyOutputs("mixer", run.outputs.brine_header)).toEqual(["flow", "temperature"]);
    expect(keyOutputs("splitter", run.outputs.brine_splitter)).toEqual(["output_0", "output_1", "output_2"]);
    expect(keyOutputs("adder", run.outputs.gas_adder)).toEqual(["output"]);
    // The splitter shares filter_b's m³/h; the adder adds the separators' kg/s of gas.
    const splitter = componentPorts(trains, "brine_splitter", undefined);
    expect(splitter.outputs.find((o) => o.key === "output_2")?.unit).toBe("m³/h");
    expect(componentPorts(trains, "gas_adder", undefined).outputs.find((o) => o.key === "output")?.unit).toBe("kg/s");
    expect(portUnit("separator", "gas_mass_flow_rate", "m³/s")).toBe("kg/s");
    expect(readOutput("mixer", "flow", 0.1666, "m³/s")).toEqual({ text: "599.8", unit: "m³/h" });
  });

  it("flags a pressure that can't be: below zero", () => {
    expect(impossibleOutput("filter", "pressure_out", -1.62, "bar")).toMatch(/not physical/);
    expect(impossibleOutput("filter", "pressure_out_pa", -161791, "Pa")).toMatch(/not physical/);
    expect(impossibleOutput("filter", "pressure_out", 1.7, "bar")).toBeNull();
    expect(impossibleOutput("producer_well", "temperature_out", -1, "°C")).toBeNull();
  });

  it("keeps the layered layout for anything that isn't a brine loop", () => {
    expect(isBrineLoop(project())).toBe(true);
    const chain: GeminiProject = { components: { a: { type: "filter" }, b: { type: "filter" } }, boundary_inputs: [], connections: [] };
    expect(isBrineLoop(chain)).toBe(false);
  });
});
