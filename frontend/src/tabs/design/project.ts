// Editing a GEMINI project (the GEMINI project view), kept free of React so it can be tested.
// Every function returns a new project and leaves its argument alone.
//
// GEMINI wires `connections` in the order given (gemini_simulator/project_loader.py), so a new
// connection always goes at the END and the others keep their order. A connection carries one
// port pair (predecessor_output / successor_input) or several (`ports`); the canvas draws one
// edge per pair.

import type { CatalogueType, GeminiOutputs, GeminiProject } from "../../workbench";

type Connection = GeminiProject["connections"][number];

export interface PortEdge {
  /** Stable while the project doesn't change: `${connection}:${pair}`. */
  id: string;
  connection: number;
  pair: number;
  source: string;
  target: string;
  out: string;
  in: string;
}

const clone = <T>(v: T): T => structuredClone(v);

/** The port pairs of a connection, whichever way it is written. */
export function pairsOf(c: Connection): [string, string][] {
  if (Array.isArray(c.ports)) return c.ports.filter((p) => Array.isArray(p) && p.length >= 2).map((p) => [String(p[0]), String(p[1])]);
  if (c.predecessor_output != null && c.successor_input != null) return [[String(c.predecessor_output), String(c.successor_input)]];
  return [];
}

/** One edge per port pair, in the project's order. */
export function projectEdges(p: GeminiProject): PortEdge[] {
  const out: PortEdge[] = [];
  p.connections.forEach((c, i) => {
    pairsOf(c).forEach(([o, n], j) => out.push({ id: `${i}:${j}`, connection: i, pair: j, source: c.predecessor, target: c.successor, out: o, in: n }));
  });
  return out;
}

/** A name not used yet: the type itself, else type_2, type_3 … */
export function uniqueName(p: GeminiProject, base: string): string {
  const clean = base.replace(/[^\w-]+/g, "_") || "component";
  if (!(clean in p.components)) return clean;
  for (let i = 2; ; i++) if (!(`${clean}_${i}` in p.components)) return `${clean}_${i}`;
}

/** The catalogue's default parameters for a type (null defaults left out: GEMINI keeps its own). */
export function defaultParameters(t: Pick<CatalogueType, "parameters">): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const p of t.parameters) if (p.default !== null && p.default !== undefined) out[p.key] = clone(p.default);
  return out;
}

/** Adds a component of a catalogue type with its default parameters and a unique name. */
export function addComponent(p: GeminiProject, t: Pick<CatalogueType, "type" | "parameters">, name?: string): { project: GeminiProject; name: string } {
  const n = name && !(name in p.components) ? name : uniqueName(p, t.type);
  const params = defaultParameters(t);
  const component: GeminiProject["components"][string] = { type: t.type };
  if (Object.keys(params).length) component.parameters = params;
  return { project: { ...p, components: { ...p.components, [n]: component } }, name: n };
}

/**
 * Connects an output of `source` to an input of `target`: a new connection at the end of the
 * list. Unchanged when the pair is already there, or source and target are the same component.
 */
export function connect(p: GeminiProject, source: string, out: string, target: string, input: string): GeminiProject {
  if (source === target || !(source in p.components) || !(target in p.components) || !out || !input) return p;
  const exists = projectEdges(p).some((e) => e.source === source && e.target === target && e.out === out && e.in === input);
  if (exists) return p;
  return { ...p, connections: [...p.connections, { predecessor: source, successor: target, ports: [[out, input]] }] };
}

/** Removes port pairs (matched by their ends, so indices may shift meanwhile); an emptied connection goes. */
export function removePairs(p: GeminiProject, pairs: Pick<PortEdge, "source" | "target" | "out" | "in">[]): GeminiProject {
  if (!pairs.length) return p;
  const gone = (c: Connection, o: string, n: string) => pairs.some((e) => e.source === c.predecessor && e.target === c.successor && e.out === o && e.in === n);
  const connections: Connection[] = [];
  for (const c of p.connections) {
    if (Array.isArray(c.ports)) {
      const keep = c.ports.filter((pp) => !gone(c, String(pp[0]), String(pp[1])));
      if (keep.length === c.ports.length) connections.push(c);
      else if (keep.length) connections.push({ ...c, ports: keep });
    } else if (!(c.predecessor_output != null && gone(c, String(c.predecessor_output), String(c.successor_input)))) {
      connections.push(c);
    }
  }
  return { ...p, connections };
}

/** Removes components with their boundary inputs and every connection to or from them. */
export function removeComponents(p: GeminiProject, names: string[]): GeminiProject {
  if (!names.length) return p;
  const drop = new Set(names);
  const components = Object.fromEntries(Object.entries(p.components).filter(([n]) => !drop.has(n)));
  return {
    ...p,
    components,
    boundary_inputs: p.boundary_inputs.filter((b) => !drop.has(b.component)),
    connections: p.connections.filter((c) => !drop.has(c.predecessor) && !drop.has(c.successor)),
  };
}

/** Renames a component everywhere it appears (keeps the order of components and connections). */
export function renameComponent(p: GeminiProject, from: string, to: string): GeminiProject {
  const name = to.trim();
  if (!name || name === from || name in p.components || !(from in p.components)) return p;
  const components = Object.fromEntries(Object.entries(p.components).map(([n, c]) => [n === from ? name : n, c]));
  return {
    ...p,
    components,
    boundary_inputs: p.boundary_inputs.map((b) => (b.component === from ? { ...b, component: name } : b)),
    connections: p.connections.map((c) => ({ ...c, predecessor: c.predecessor === from ? name : c.predecessor, successor: c.successor === from ? name : c.successor })),
  };
}

export function setParameter(p: GeminiProject, name: string, key: string, value: unknown): GeminiProject {
  const c = p.components[name];
  if (!c) return p;
  return { ...p, components: { ...p.components, [name]: { ...c, parameters: { ...(c.parameters ?? {}), [key]: value } } } };
}

/** Sets a boundary input's value (adds it when the component has none for that key). */
export function setBoundary(p: GeminiProject, component: string, key: string, value: number): GeminiProject {
  const i = p.boundary_inputs.findIndex((b) => b.component === component && b.key === key);
  if (i < 0) return { ...p, boundary_inputs: [...p.boundary_inputs, { component, key, value }] };
  const boundary_inputs = p.boundary_inputs.slice();
  boundary_inputs[i] = { ...boundary_inputs[i], value };
  return { ...p, boundary_inputs };
}

export function removeBoundary(p: GeminiProject, component: string, key: string): GeminiProject {
  return { ...p, boundary_inputs: p.boundary_inputs.filter((b) => !(b.component === component && b.key === key)) };
}

export interface Ports {
  inputs: { key: string; connected: boolean; boundary: number | null; unit: string }[];
  outputs: { key: string; connected: boolean; unit: string }[];
}

/** A component's ports: those its connections and boundary inputs use, then the rest of the catalogue's. */
export function componentPorts(p: GeminiProject, name: string, t: CatalogueType | undefined): Ports {
  const edges = projectEdges(p);
  const usedIn = edges.filter((e) => e.target === name).map((e) => e.in);
  const usedOut = edges.filter((e) => e.source === name).map((e) => e.out);
  const bounds = p.boundary_inputs.filter((b) => b.component === name);
  const type = p.components[name]?.type ?? "";
  // A splitter or an adder carries whatever feeds it: its ports take the unit of what comes in.
  const fed = type === "splitter" || type === "adder" ? feedUnit(p, name, edges) : "";
  const unitIn = (k: string) => fed || portUnit(type, k, t?.inputs.find((x) => x.key === k)?.unit);
  const unitOut = (k: string) => fed || portUnit(type, k, t?.outputs.find((x) => x.key === k)?.unit);
  const inKeys = uniq([...usedIn, ...bounds.map((b) => b.key), ...(t?.inputs.map((x) => x.key) ?? [])]);
  const outKeys = uniq([...usedOut, ...(t?.outputs.map((x) => x.key) ?? [])]);
  return {
    inputs: inKeys.map((key) => {
      const b = bounds.find((x) => x.key === key);
      return { key, connected: usedIn.includes(key), boundary: b && typeof b.value === "number" ? b.value : null, unit: unitIn(key) };
    }),
    outputs: outKeys.map((key) => ({ key, connected: usedOut.includes(key), unit: unitOut(key) })),
  };
}

const uniq = (xs: string[]) => [...new Set(xs)];

/** The unit of the first port feeding a component (a splitter's brine, an adder's gas). */
function feedUnit(p: GeminiProject, name: string, edges: PortEdge[]): string {
  const e = edges.find((x) => x.target === name);
  if (!e) return "";
  const type = p.components[e.source]?.type ?? "";
  return portUnit(type, e.out, guessUnit(e.out));
}

/** The unit GEMINI's code means by a port's name, as the server's catalogue guesses it. */
function guessUnit(key: string): string {
  const k = key.toLowerCase();
  if (/mass_flow/.test(k)) return "kg/s";
  if (/temperature/.test(k)) return "°C";
  if (/_pa$/.test(k)) return "Pa";
  if (/pressure/.test(k)) return "bar";
  if (/m3h$/.test(k)) return "m³/h";
  if (/flow/.test(k)) return "m³/s";
  if (/^power|heat_duty|_power_el$/.test(k)) return "W";
  return "";
}

/**
 * The unit of a port. The catalogue guesses units from the key's name; where GEMINI's code says
 * otherwise, this wins (the producer's flow_rate is m³/h, its flow_rate_m3s is m³/s).
 */
export function portUnit(type: string, key: string, catalogueUnit?: string): string {
  if (type === "producer_well" && key === "flow_rate") return "m³/h";
  if (type === "injector_well" && key === "flow_rate") return "m³/h";
  if (/_m3s$/.test(key)) return "m³/s";
  if (/_m3h$/.test(key)) return "m³/h";
  // The catalogue reads any "flow" as m³/s; a mass flow is kg/s (the separated gas).
  if (/mass_flow/.test(key)) return "kg/s";
  return catalogueUnit ?? "";
}

// ------------------------------------------------------------------ outputs

/** The outputs a node shows after a run, in order of preference (the first few that exist). */
const KEY_OUTPUTS: string[][] = [
  ["flow_rate_m3h", "flow_rate"],
  ["temperature_out", "primary_temperature_out"],
  ["secondary_temperature_out"],
  ["heat_duty"],
  ["esp_power_el", "power_el"],
  ["wellhead_pressure"],
];

/** The outputs that say most about each kind of component, in order. */
const KEY_BY_TYPE: Record<string, string[]> = {
  mixer: ["flow", "temperature"],
  separator: ["flow_rate_m3h", "temperature_out", "pressure_out", "gas_mass_flow_rate"],
  filter: ["flow_rate_m3h", "temperature_out", "pressure_out"],
  boiler: ["power_th", "temperature_out", "emission"],
  adder: ["output"],
  injector_well: ["wellhead_pressure", "power_el", "flow_rate_m3s"],
};

export function keyOutputs(type: string, outputs: Record<string, number> | undefined, max = 4): string[] {
  if (!outputs) return [];
  if (type === "splitter") return Object.keys(outputs).filter((k) => /^output_\d+$/.test(k)).slice(0, Math.max(max, 3));
  const own = KEY_BY_TYPE[type];
  if (own) return own.filter((k) => k in outputs).slice(0, max);
  const keys: string[] = [];
  for (const group of KEY_OUTPUTS) {
    const k = group.find((g) => g in outputs && !(isPower(g) && outputs[g] === 0));
    // flow_rate on a separator or filter is m³/s; flow_rate_m3h is the same flow, easier to read.
    if (k && !(k === "flow_rate" && type !== "producer_well" && "flow_rate_m3h" in outputs)) keys.push(k);
    if (keys.length >= max) break;
  }
  return keys;
}

const isPower = (k: string) => /power_el$|heat_duty/.test(k);

/** A value for reading: W as MW or kW, Pa as bar, the rest as it comes. */
export function readOutput(type: string, key: string, value: number, catalogueUnit?: string): { text: string; unit: string } {
  const unit = portUnit(type, key, catalogueUnit);
  if (unit === "W") {
    if (Math.abs(value) >= 1e5) return { text: num(value / 1e6), unit: "MW" };
    return { text: num(value / 1e3), unit: "kW" };
  }
  if (unit === "Pa") return { text: num(value / 1e5), unit: "bar" };
  // Brine flows read as m³/h, as everywhere else in the app.
  if (unit === "m³/s") return { text: num(value * 3600), unit: "m³/h" };
  return { text: num(value), unit };
}

/** A value that can't be right: a pressure below zero (bar or Pa) is below vacuum. */
export function impossibleOutput(type: string, key: string, value: number, catalogueUnit?: string): string | null {
  const unit = portUnit(type, key, catalogueUnit ?? guessUnit(key));
  if ((unit === "bar" || unit === "Pa") && value < 0) return "below zero: not physical (the pressure drop exceeds what the brine had)";
  return null;
}

function num(v: number): string {
  if (!Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  if (a >= 1000) return Math.round(v).toLocaleString("en-US");
  if (a === 0) return "0";
  if (a < 0.01) return String(Number(v.toPrecision(2))).replace("-", "−");
  const digits = a >= 10 ? 1 : a >= 1 ? 2 : 3;
  return String(Number(v.toFixed(digits))).replace("-", "−");
}

/** Fixed against released: the change in %, and whether it is big (10 % or more). */
export function compareOutput(fixed: number, released: number | undefined): { pct: number | null; text: string; big: boolean } | null {
  if (released == null || !Number.isFinite(released) || !Number.isFinite(fixed)) return null;
  if (fixed === released) return { pct: 0, text: "same", big: false };
  if (Math.abs(released) < 1e-9) return { pct: null, text: "from 0", big: true };
  const pct = ((fixed - released) / Math.abs(released)) * 100;
  const big = Math.abs(pct) >= 10;
  const a = Math.abs(pct);
  const text = a >= 1000 ? `${pct > 0 ? ">+" : "<−"}999%` : `${pct > 0 ? "+" : pct < 0 ? "−" : ""}${a >= 10 ? Math.round(a) : a.toFixed(1)}%`;
  return { pct, text, big };
}

// ------------------------------------------------------------------ layout

export const PNODE_W = 252;
const PCOL_GAP = 84;
const PROW_GAP = 84;

/**
 * Where to draw each component: layered left to right along the connections (longest path from a
 * component nothing feeds), stacked within a layer. More than `maxPerRow` layers wrap into bands
 * one under the other (a chain of six reads as two rows of three), so the canvas needn't zoom out
 * to a strip. `heights` estimates each node's height.
 */
export function layoutProject(p: GeminiProject, heights: (name: string) => number, maxPerRow = 4): Record<string, { x: number; y: number }> {
  const names = Object.keys(p.components);
  const preds = new Map<string, Set<string>>(names.map((n) => [n, new Set()]));
  for (const c of p.connections) if (preds.has(c.successor) && preds.has(c.predecessor) && c.successor !== c.predecessor) preds.get(c.successor)!.add(c.predecessor);
  const layer = new Map<string, number>();
  const visiting = new Set<string>();
  const depth = (n: string): number => {
    if (layer.has(n)) return layer.get(n)!;
    if (visiting.has(n)) return 0; // a loop: cut it here
    visiting.add(n);
    let d = 0;
    for (const q of preds.get(n) ?? []) d = Math.max(d, depth(q) + 1);
    visiting.delete(n);
    layer.set(n, d);
    return d;
  };
  names.forEach(depth);
  const layers = Math.max(0, ...layer.values()) + 1;
  const bands = Math.ceil(layers / Math.max(1, maxPerRow));
  const perRow = Math.ceil(layers / bands);
  // Stack within each (band, column); a band is as tall as its tallest stack.
  const stack = new Map<string, number>();
  const placed: { n: string; band: number; col: number; y: number }[] = [];
  for (const n of names) {
    const l = layer.get(n) ?? 0;
    const band = Math.floor(l / perRow);
    const col = l % perRow;
    const k = `${band}:${col}`;
    const y = stack.get(k) ?? 0;
    placed.push({ n, band, col, y });
    stack.set(k, y + heights(n) + 40);
  }
  const bandH = Array.from({ length: bands }, (_, b) => Math.max(0, ...[...stack.entries()].filter(([k]) => k.startsWith(`${b}:`)).map(([, v]) => v - 40)));
  const bandY = bandH.map((_, b) => bandH.slice(0, b).reduce((a, h) => a + h + PROW_GAP, 0));
  const out: Record<string, { x: number; y: number }> = {};
  for (const { n, band, col, y } of placed) out[n] = { x: col * (PNODE_W + PCOL_GAP), y: bandY[band] + y };
  return out;
}

/** A rough height of a component node (header, ports, outputs), for the layout. */
export function estimateHeight(ports: Ports, outputs: number): number {
  const bound = ports.inputs.filter((x) => x.boundary != null).length;
  return 64 + Math.max(1, ports.inputs.length + bound * 0.8, ports.outputs.length) * 22 + (outputs ? 16 + outputs * 34 : 0);
}

/** The ports a node shows when compact: those in use (connected or fixed), else all of them. */
export function compactPorts(ports: Ports): Ports {
  const inputs = ports.inputs.filter((x) => x.connected || x.boundary != null);
  const outputs = ports.outputs.filter((x) => x.connected);
  if (!inputs.length && !outputs.length) return ports;
  return { inputs, outputs };
}

// ------------------------------------------------------------------ what each component is

/** A 16 × 16 stroke icon and a colour per GEMINI type (the Plant view's colours where they match). */
export const COMPONENT_META: Record<string, { label: string; icon: string; color: string }> = {
  producer_well: { label: "Producer well", icon: "M8 14V3M4.5 6.5 8 3l3.5 3.5", color: "#c24e1c" },
  injector_well: { label: "Injector well", icon: "M8 2v11M4.5 9.5 8 13l3.5-3.5", color: "#2363a6" },
  // Two flows joining into one; one flow parting into several.
  mixer: { label: "Mixer", icon: "M2 3.5c3.5 0 4 4.5 6 4.5M2 12.5c3.5 0 4-4.5 6-4.5h6M11.5 5.5 14 8l-2.5 2.5", color: "#4f6b7a" },
  splitter: { label: "Splitter", icon: "M2 8h5c2 0 2.5-4.5 6.5-4.5M7 8c2 0 2.5 4.5 6.5 4.5M7 8h6.5", color: "#4f6b7a" },
  adder: { label: "Adder", icon: "M12 3.5H4.5l4 4.5-4 4.5H12", color: "#7856c4" },
  separator: { label: "Gas separator", icon: "M5 5.2a3 3 0 0 1 6 0V13H5zM8 1.6v1.6M5 9.4h6", color: "#4f6b7a" },
  filter: { label: "Filter", icon: "M2.5 3h11L9.5 8.5V13l-3-1.5v-3z", color: "#4f6b7a" },
  heat_exchanger: { label: "Heat exchanger", icon: "M2.5 5.5h11M10.5 2.5l3 3-3 3M13.5 10.5h-11M5.5 7.5l-3 3 3 3", color: "#c24e1c" },
  heatpump: { label: "Heat pump", icon: "M12.6 6.2A5 5 0 0 0 3.6 5.4M3.4 9.8a5 5 0 0 0 9 .8M12.8 2.8v3.6H9.2M3.2 13.2V9.6h3.6", color: "#e3a33b" },
  boiler: { label: "Boiler", icon: "M8 1.8c2.2 3 4.2 4.6 4.2 7.6a4.2 4.2 0 0 1-8.4 0C3.8 6.8 6 5.6 8 1.8z", color: "#7856c4" },
};
const PART_ICON = { label: "", icon: "M3 3h10v10H3z", color: "#66727c" };
export const componentMeta = (type: string) => COMPONENT_META[type] ?? { ...PART_ICON, label: type.replace(/_/g, " ") };

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/**
 * What a component does in this loop, in a few words, from its name and its connections:
 * "doublet 2", "joins 2 producers", "train 1", "shares the brine among 3 injectors".
 */
export function componentRole(p: GeminiProject, name: string): string {
  const c = p.components[name];
  if (!c) return "";
  const preds = uniq(p.connections.filter((x) => x.successor === name).map((x) => x.predecessor));
  const succs = uniq(p.connections.filter((x) => x.predecessor === name).map((x) => x.successor));
  const typeOf = (n: string) => p.components[n]?.type ?? "";
  const tail = /_(\d+)([a-z]?)$/i.exec(name);
  switch (c.type) {
    case "producer_well":
    case "injector_well":
      return tail ? `doublet ${tail[1]}${tail[2] ? `, ${tail[2].toUpperCase()}` : ""}` : "the doublet";
    case "mixer": {
      const n = preds.length;
      if (preds.every((x) => typeOf(x) === "producer_well")) return `joins ${plural(n, "producer")}`;
      if (preds.every((x) => typeOf(x) === "filter")) return `joins ${plural(n, "treatment train")}`;
      return `joins ${plural(n, "flow")}`;
    }
    case "splitter": {
      const inj = succs.filter((x) => typeOf(x) === "injector_well").length;
      return inj ? `shares the brine among ${plural(inj, "injector")}` : `splits into ${plural(succs.length, "flow")}`;
    }
    case "adder": {
      const seps = preds.filter((x) => typeOf(x) === "separator").length;
      return seps ? `adds the gas of ${plural(seps, "separator")}` : `adds ${plural(preds.length, "input")}`;
    }
    case "separator":
    case "filter":
      if (name.startsWith("filter_b")) return "after the exchanger";
      return tail ? `treatment train ${tail[1]}` : "the treatment train";
    case "heat_exchanger":
      return "brine to the heating network";
    case "boiler":
      return succs.length || preds.some((x) => typeOf(x) === "adder" || typeOf(x) === "separator") ? "burns the separated gas" : "";
    default:
      return "";
  }
}

// ------------------------------------------------------------------ the brine loop's layout

/** The brine loop's columns, in the order the brine flows; the gas side runs under the line. */
const STAGE_OF: [RegExp, number][] = [
  [/^producer_well/, 0],
  [/^brine_mixer/, 1],
  [/^separator/, 2],
  [/^filter_a/, 3],
  [/^brine_header/, 4],
  [/^heat_exchanger/, 5],
  [/^filter_b/, 6],
  [/^brine_splitter/, 7],
  [/^injector_well/, 8],
];
const GAS_STAGE: [RegExp, number][] = [
  [/^gas_adder/, 4],
  [/^boiler/, 5],
];

/** Whether a project is a brine loop the loop layout knows (producers to injectors). */
export function isBrineLoop(p: GeminiProject): boolean {
  const types = Object.values(p.components).map((c) => c.type);
  return types.includes("producer_well") && types.includes("injector_well");
}

/**
 * Where to draw each component of a brine loop: one column per step of the brine's way, in the
 * order the server lists them (producers, each treatment train's mixer, separator and filter in a
 * lane of its own, the header, the exchanger, the second filter, the splitter, the injectors), the
 * producers and the injectors stacked, each train's parts level with its producers, the shared
 * parts in the middle, and the gas side (the adder, the boiler) under the line. Components the
 * user added go one column after what feeds them, in a lane below.
 */
export function layoutLoop(p: GeminiProject, heights: (name: string) => number): Record<string, { x: number; y: number }> {
  const names = Object.keys(p.components);
  const typeOf = (n: string) => p.components[n]?.type ?? "";
  const preds = new Map<string, string[]>(names.map((n) => [n, uniq(p.connections.filter((c) => c.successor === n && c.predecessor in p.components && c.predecessor !== n).map((c) => c.predecessor))]));
  const stageByName = (n: string, table: [RegExp, number][]) => table.find(([re]) => re.test(n))?.[1];
  const producers = names.filter((n) => typeOf(n) === "producer_well");
  const injectors = names.filter((n) => typeOf(n) === "injector_well");
  const pLane = new Map(producers.map((n, i) => [n, i]));
  const centre = (producers.length - 1) / 2;

  const stage = new Map<string, number>();
  const lane = new Map<string, number>();
  const gas = new Set<string>();
  for (const n of names) {
    const t = typeOf(n);
    let st = stageByName(n, STAGE_OF);
    if (st == null && t === "producer_well") st = 0;
    if (st == null && t === "injector_well") st = 8;
    const g = st == null ? stageByName(n, GAS_STAGE) : undefined;
    if (g != null) {
      stage.set(n, g);
      gas.add(n);
    } else if (st != null) stage.set(n, st);
  }
  // The producers upstream of a component (through its train's mixer, separator and filter).
  const upstream = (n: string, seen = new Set<string>()): string[] => {
    if (seen.has(n)) return [];
    seen.add(n);
    if (pLane.has(n)) return [n];
    return uniq((preds.get(n) ?? []).flatMap((q) => upstream(q, seen)));
  };
  for (const n of names) {
    const st = stage.get(n);
    if (st == null || gas.has(n)) continue;
    if (st === 0) lane.set(n, pLane.get(n) ?? 0);
    else if (st === 8) lane.set(n, centre - (injectors.length - 1) / 2 + injectors.indexOf(n));
    else if (st <= 3) {
      const ups = upstream(n).map((q) => pLane.get(q)!);
      lane.set(n, ups.length ? ups.reduce((a, b) => a + b, 0) / ups.length : centre);
    } else lane.set(n, centre);
  }
  const mainMax = Math.max(0, ...[...lane.entries()].filter(([n]) => (stage.get(n) ?? 0) < 8).map(([, l]) => l));
  const gasLane = mainMax + 1;
  for (const n of gas) lane.set(n, gasLane);
  // Anything else (added by hand): a column after what feeds it, a lane under the rest.
  let spare = gasLane + (gas.size ? 1 : 0);
  const depth = (n: string, seen = new Set<string>()): number => {
    if (stage.has(n)) return stage.get(n)!;
    if (seen.has(n)) return 0;
    seen.add(n);
    return Math.max(-1, ...(preds.get(n) ?? []).map((q) => depth(q, seen))) + 1;
  };
  for (const n of names) {
    if (stage.has(n)) continue;
    stage.set(n, depth(n));
    lane.set(n, spare++);
  }
  // Squeeze out the columns no component uses; one lane is as tall as the tallest component.
  const used = [...new Set(stage.values())].sort((a, b) => a - b);
  const col = new Map(used.map((s, i) => [s, i]));
  const pitch = Math.max(120, ...names.map(heights)) + 44;
  const minLane = Math.min(0, ...lane.values());
  const out: Record<string, { x: number; y: number }> = {};
  for (const n of names) {
    const cy = (lane.get(n)! - minLane) * pitch + pitch / 2;
    out[n] = { x: col.get(stage.get(n)!)! * (PNODE_W + PCOL_GAP), y: Math.round(cy - heights(n) / 2) };
  }
  return out;
}

// ------------------------------------------------------------------ import

/** Reads a project from JSON text; a sentence saying what's wrong when it can't. */
export function parseProject(text: string): { project: GeminiProject } | { error: string } {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (err) {
    return { error: `That isn't JSON: ${(err as Error).message}` };
  }
  const problem = projectProblem(data);
  return problem ? { error: problem } : { project: normalise(data as GeminiProject) };
}

function normalise(p: GeminiProject): GeminiProject {
  return { ...p, boundary_inputs: p.boundary_inputs ?? [], connections: p.connections ?? [] };
}

/** What makes `data` not a GEMINI project, or null when it is one. */
export function projectProblem(data: unknown): string | null {
  if (!data || typeof data !== "object" || Array.isArray(data)) return "A GEMINI project is a JSON object with components, boundary_inputs and connections.";
  const p = data as Record<string, unknown>;
  if (!p.components || typeof p.components !== "object" || Array.isArray(p.components)) return "It has no components object.";
  const components = p.components as Record<string, unknown>;
  for (const [name, c] of Object.entries(components)) {
    if (!c || typeof c !== "object" || typeof (c as Record<string, unknown>).type !== "string") return `Component ${name} has no type.`;
  }
  if (p.boundary_inputs != null && !Array.isArray(p.boundary_inputs)) return "boundary_inputs must be a list.";
  for (const b of (p.boundary_inputs as unknown[]) ?? []) {
    const x = b as Record<string, unknown>;
    if (!x || typeof x.component !== "string" || typeof x.key !== "string") return "Each boundary input needs a component and a key.";
    if (!(x.component in components)) return `A boundary input is for ${x.component}, which isn't a component.`;
  }
  if (p.connections != null && !Array.isArray(p.connections)) return "connections must be a list.";
  for (const c of (p.connections as unknown[]) ?? []) {
    const x = c as Record<string, unknown>;
    if (!x || typeof x.predecessor !== "string" || typeof x.successor !== "string") return "Each connection needs a predecessor and a successor.";
    if (!(x.predecessor in components)) return `A connection starts at ${x.predecessor}, which isn't a component.`;
    if (!(x.successor in components)) return `A connection ends at ${x.successor}, which isn't a component.`;
    const hasPorts = Array.isArray(x.ports) && x.ports.every((pp) => Array.isArray(pp) && pp.length === 2 && pp.every((k) => typeof k === "string"));
    const hasPair = typeof x.predecessor_output === "string" && typeof x.successor_input === "string";
    if (!hasPorts && !hasPair) return `The connection ${x.predecessor} → ${x.successor} needs ports or predecessor_output and successor_input.`;
  }
  return null;
}

/** A short fingerprint of a project, to tell whether a run's outputs are still for what's on screen. */
export function projectKey(p: GeminiProject): string {
  return JSON.stringify(p);
}

/** The outputs of one component in both runs (fixed, released). */
export function outputsOf(run: { outputs: GeminiOutputs; released: { outputs: GeminiOutputs } | null } | null, name: string) {
  return { fixed: run?.outputs[name], released: run?.released?.outputs[name] };
}
