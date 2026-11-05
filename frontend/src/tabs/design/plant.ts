// The Plant view's logic, kept free of React so it can be tested: where each part of the plant
// sits on the canvas, how a pipe is drawn, what each part does on a day of the year, which of the
// verifier's checks are about it, and the design-level edits the backend accepts.
//
// LAYOUT. The graph has no positions, so the parts are placed by type, in rows that suit a canvas
// a little wider than tall (about 1.6 : 1), the surface plant on top and the wells under it:
//
//   top row        absorption chiller, electric chillers, cooling towers ──┐ cold lanes ──→ cooling demand
//   middle row     gas, gas boiler, electric boiler, grid               ──┐ heat lanes ──→ heat demand
//   brine row      treatment trains (stacked) → heat exchanger → heat pump ┘
//   lanes          the brine back from the heat pump (one lane), then one lane per treatment train
//                  (its producers' brine on the way up), then the grid's line to the well pumps
//   wells          ┌ Doublet 1 ┐┌ Doublet 2 ┐ …   at full width; narrower cards when there are many
//                  │ inj  prod ││ inj  prod │
//   ground         the reservoir: one band under the wells, the aquifer tall enough that a well open
//                  over its upper or lower half reads apart from one fully open; its facts at the
//                  right, or under the aquifer when the wells leave no room
//
// Each doublet is a framed group: its injector(s), then its producer. A producer's brine rises to
// its train's lane, runs left past the plant and up into the train's left side; the brine back
// from the heat pump (or the exchanger) drops into the top lane and from it into each injector. A
// pipe that has to cross another (an injector's drop over a train's lane, the drive brine to the
// absorption chiller over the gas to the boiler) is drawn with a bridge: a gap in the pipe below.
//
// A demand node sits at the right on its corridor, the gap between two rows. Each unit that
// feeds it drops (or rises) into a lane of its own and runs right into its own handle, so pipes
// never cross: units above take the upper lanes, the rightmost one highest; units below take the
// lower lanes, the leftmost one nearest the middle. Empty columns are squeezed out.
//
// THIN LINES. Electricity (the grid to every unit that draws it) and the heat the chillers send
// to the towers are thin lines (dotted and dashed). They may cross a pipe but never a card: each
// one takes the first route of a short list that passes through no card (down to the wells along
// their own run over the frames, straight, an L or a Z, round the outside of the rows, up a column
// gap), and arrives three quarters along a side so it stays clear of the pipe that uses the
// side's middle.

import type { Design, DesignChanges, DesignCheck, Dispatch, DoubletChange, DoubletSpec, GasMode, Graph, GraphEdge, GraphNode, Opening, PlantDoublet, PowerUser, Provenance, RejectSource } from "../../workbench";
import { provenanceOf } from "../../workbench";

// ------------------------------------------------------------------ geometry

export const NODE_W = 184;
export const NODE_H = 96;
export const COL_GAP = 60;
export const COL_W = NODE_W + COL_GAP;
export const LANE = 26;
/** Room between a row and the first (or last) lane of the corridor next to it. */
const LANE_PAD = 18;
/** The least room between two rows. */
export const CORRIDOR_MIN = 56;
/** A corridor's height for its lanes: LANE apart, LANE_PAD clear of the rows. */
export const corridorH = (lanes: number) => Math.max(CORRIDOR_MIN, (Math.max(1, lanes) - 1) * LANE + 2 * LANE_PAD);
const DEMAND_MIN_H = 96;
/** Demand cards are a little wider: "Cooling demand" and its badge. */
export const DEMAND_W = 204;

/** A well's card at its widest: narrower than a unit's and a line taller (its depth, open part and mean flow). */
export const WELL_W = 172;
/** The narrowest a well's card gets, when many wells share the width (it then shows a little less). */
export const WELL_MIN_W = 120;
/** Below this width a well's card is laid out narrow (PlantCanvas WellCard): its short name, the temperature under the flow. */
export const WELL_NARROW_W = WELL_W;
/** The narrowest the cards may get to leave the reservoir's facts room beside the aquifer. */
const WELL_FACTS_MIN_W = 150;
export const WELL_H = 112;
/** Between two wells of a doublet, between two doublets, and a doublet's frame around its wells. */
export const WELL_GAP = 10;
export const GROUP_GAP = 20;
export const GROUP_PAD = 8;
/** The doublet frame's label row, above its wells. */
export const GROUP_HEAD = 24;
/** Room left of the wells for the reservoir band's depth scale. */
export const GUTTER = 58;
/** Between two treatment trains stacked in their column. */
export const TRAIN_GAP = 18;
/** Between the risers of the producers' brine left of the trains. */
const DESCENT = 16;

export type Side = "t" | "r" | "b" | "l";
/**
 * A handle on a card: a side's middle, or a point along it. "tq" is the top a quarter in (a unit
 * rising into a corridor clear of the drop from the unit above); "rq" the right side a quarter
 * down (the gas of a lower treatment train coming in); "t3", "b3", "r3" and "l3" are three
 * quarters along a side (a thin line beside the pipe that uses the middle, or the brine back into
 * an injector).
 */
export type CardHandle = Side | "tq" | "rq" | "t3" | "b3" | "r3" | "l3";
/** A source handle: a card's, or "res-<well>" (the reservoir band's top, under that producer). */
export type SourceHandle = CardHandle | `res-${string}`;
/** A target handle: a card's, a demand's lane, or "res-<well>" (the band's top, under that injector). */
export type TargetHandle = CardHandle | `lane-${number}` | `res-${string}`;
type Row = "top" | "mid" | "brine";

export const handleSide = (h: CardHandle): Side => h[0] as Side;
/** Where along its side a handle sits (0..1), as PlantCanvas places it. */
export const HANDLE_AT: Record<CardHandle, number> = { t: 0.5, r: 0.5, b: 0.5, l: 0.5, tq: 0.26, rq: 0.26, t3: 0.74, b3: 0.74, r3: 0.74, l3: 0.74 };

/** A handle's point on a laid card. */
export function handlePoint(n: Pick<LaidNode, "x" | "y" | "width" | "height">, h: CardHandle): [number, number] {
  const f = HANDLE_AT[h];
  switch (handleSide(h)) {
    case "t":
      return [n.x + n.width * f, n.y];
    case "b":
      return [n.x + n.width * f, n.y + n.height];
    case "l":
      return [n.x, n.y + n.height * f];
    case "r":
      return [n.x + n.width, n.y + n.height * f];
  }
}

/**
 * Where each known type goes: its row and its plant column (counted from the treatment trains),
 * before empty columns are squeezed out. The wells are laid apart, under the plant.
 */
const SLOTS: Record<string, { row: Row; col: number }> = {
  // The brine runs left to right along the plant's lowest row, over the wells.
  treatment: { row: "brine", col: 0 },
  heat_exchanger: { row: "brine", col: 1 },
  heatpump: { row: "brine", col: 2 },
  // Over it, the gas over the trains it comes from (straight up), the gas boiler beside it, the
  // electric boiler next to the grid (a straight wire, its lane into the heat demand the
  // highest), and the grid at the right end, under the towers: an L to the heat pump and to the
  // chillers, straight up to the towers, straight down to the wells.
  gas: { row: "mid", col: 0 },
  boiler: { row: "mid", col: 1 },
  electric_boiler: { row: "mid", col: 2 },
  grid: { row: "mid", col: 3 },
  // Cooling on top: the absorption chiller over the boiler, the electric chillers, the towers.
  absorption: { row: "top", col: 1 },
  chillers: { row: "top", col: 2 },
  tower: { row: "top", col: 3 },
};

export const isDemand = (type: string) => type === "demand_heat" || type === "demand_cold";
export const isWell = (type: string) => type === "producer_well" || type === "injector_well";

export interface LaidNode {
  id: string;
  node: GraphNode;
  x: number;
  y: number;
  width: number;
  height: number;
  /** For demand nodes: the y of each lane handle, from the node's top ("lane-0", "lane-1" …). */
  lanes: number[];
  /** For the reservoir band: each well's shaft and open part (x from the band's left). */
  wells?: BandWell[];
  /** For the reservoir band: the aquifer(s) it draws, shallowest first. */
  aquifers?: number[];
  /** For the reservoir band with wells: how wide its aquifer section is, and where its facts go. */
  band?: { section: number; facts: "right" | "below" };
}

/** A well as the reservoir band draws it: its shaft at `x`, open from `top_m` to `base_m`. */
export interface BandWell {
  id: string;
  kind: "producer" | "injector";
  /** "P1", "I1A". */
  short: string;
  doublet: number;
  x: number;
  /** The aquifer it is in (its middle), m TVD. */
  aquifer_m: number;
  top_m: number;
  base_m: number;
  opening: Opening;
}

/** A doublet's frame round its wells. */
export interface LaidGroup {
  id: string;
  doublet: number;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  wells: string[];
}

/** A pipe's route through a lane: up (or down) to `y`, along it, and into the target, down at `x` when given. */
export interface Via {
  y: number;
  x?: number;
}

/** Where a pipe passes over another: a gap is cut in the one below, along this pipe's run. */
export interface Bridge {
  x: number;
  y: number;
  /** The run of the pipe on top: horizontal or vertical. */
  dir: "h" | "v";
}

export interface LaidEdge {
  id: string;
  edge: GraphEdge;
  sourceHandle: SourceHandle;
  targetHandle: TargetHandle;
  /** For a line that leaves and arrives on the same side: how far out it goes before running across. */
  clearance?: number;
  /** For a pipe through a lane between the plant and the wells (and the grid's line to the well pumps). */
  via?: Via;
  /** Pipes it passes over (drawn with a gap in the pipe below). */
  bridges?: Bridge[];
  /** Drawing order: thin lines 0, heat, cold and gas 1, brine 2, the brine back to the injectors 3. */
  layer: number;
}

/**
 * The reservoir band: its header row, one aquifer layer (100 m, drawn 76 px tall so a half-open
 * well is 38 px against a fully open one's 76), the gap between two layers, the bottom.
 */
export const BAND_TOP = 14;
export const LAYER_H = 76;
export const LAYER_GAP = 22;
const BAND_BOTTOM = 14;
export const RESERVOIR_H = BAND_TOP + LAYER_H + BAND_BOTTOM;
export const RESERVOIR_NOTE_H = 30;
/** The reservoir's facts in a row under the aquifer, when the wells leave no room at its right. */
export const RESERVOIR_FACTS_H = 46;
/** The room the facts need at the aquifer's right (one per line). */
export const RESERVOIR_FACTS_W = 230;
/** Between the doublets' frames and the band: the wells' shafts and their temperatures. */
const RESERVOIR_GAP = 30;
/** Room right of a well's shaft in the band for its label: "P1 fully open", "P2 lower half open". */
const openLabelW = (o: Opening) => (o === "full" ? 94 : 120);

/** The reservoir is extrapolated from the known aquifer when the wells go deeper than it. */
export const isAssumedReservoir = (node: Pick<GraphNode, "values">) => !!node.values.assumed;
/** The aquifer section's height: one layer per aquifer. */
export const sectionHeight = (aquifers = 1) => RESERVOIR_H + Math.max(0, aquifers - 1) * (LAYER_H + LAYER_GAP);
/** The band's height: the section, the facts' row when under it, and a line for the note on an assumed aquifer. */
export const reservoirHeight = (node: Pick<GraphNode, "values">, aquifers = 1, factsBelow = false) =>
  sectionHeight(aquifers) + (factsBelow ? RESERVOIR_FACTS_H : 0) + (isAssumedReservoir(node) ? RESERVOIR_NOTE_H : 0);

/** Where a depth sits in the band (px from the band's top), on the layer of its aquifer. */
export function depthY(depth_m: number, aquifers: number[], thickness_m: number): number {
  const half = thickness_m / 2;
  let i = aquifers.findIndex((a) => depth_m >= a - half - 1e-6 && depth_m <= a + half + 1e-6);
  if (i < 0) i = aquifers.reduce((best, a, k) => (Math.abs(a - depth_m) < Math.abs(aquifers[best] - depth_m) ? k : best), 0);
  const top = aquifers[i] - half;
  const f = Math.min(1, Math.max(0, (depth_m - top) / (thickness_m || 1)));
  return BAND_TOP + i * (LAYER_H + LAYER_GAP) + f * LAYER_H;
}

// ------------------------------------------------------------------ thin lines

/** How far a thin line goes above the top row before running across. */
export const ABOVE = 24;
/** Below the brine row: halfway to the first lane. */
export const BELOW = LANE_PAD / 2;
/** A thin line keeps this far from any card it passes. */
const MARGIN = 6;

type Route = { sourceHandle: CardHandle; targetHandle: CardHandle; clearance?: number; via?: Via };
const isCardHandle = (h: string): h is CardHandle => h in HANDLE_AT;

/** The corners of a route between two laid cards (pipePoints between their handles); [] when an end is not a card's handle. */
export function routePoints(s: LaidNode, t: LaidNode, route: Pick<LaidEdge, "sourceHandle" | "targetHandle" | "clearance" | "via">): [number, number][] {
  if (!isCardHandle(route.sourceHandle) || !isCardHandle(route.targetHandle)) return [];
  const [sx, sy] = handlePoint(s, route.sourceHandle);
  const [tx, ty] = handlePoint(t, route.targetHandle);
  const sSide = handleSide(route.sourceHandle);
  const tSide = handleSide(route.targetHandle);
  if (route.via) return viaPoints(sx, sy, sSide, tx, ty, tSide, route.via).pts;
  return pipePoints(sx, sy, sSide, tx, ty, tSide, route.clearance).pts;
}

/** Whether an axis-aligned segment comes within MARGIN of a card. */
function segmentHits(ax: number, ay: number, bx: number, by: number, c: LaidNode): boolean {
  return Math.max(ax, bx) >= c.x - MARGIN && Math.min(ax, bx) <= c.x + c.width + MARGIN && Math.max(ay, by) >= c.y - MARGIN && Math.min(ay, by) <= c.y + c.height + MARGIN;
}

/** Whether a route passes through no card: a segment may touch only the card at its own end. */
export function routeClear(pts: [number, number][], s: LaidNode, t: LaidNode, cards: LaidNode[]): boolean {
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, ay] = pts[i];
    const [bx, by] = pts[i + 1];
    for (const c of cards) {
      if ((c === s && i === 0) || (c === t && i === pts.length - 2)) continue;
      if (segmentHits(ax, ay, bx, by, c)) return false;
    }
  }
  return true;
}

/**
 * The route of a thin line between two cards: the first of these that passes through no card.
 * Down to a well (the grid to the well pumps): straight down to the wires' run over the doublets'
 * frames, along it, and down into the well three quarters along its top. Straight when the cards
 * share a column or a row; an L or a Z like the other pipes, into the far end of the target's
 * side; else round the outside, under the lower row first when either card is on the brine row
 * (over the top row otherwise), or up a column gap.
 */
export function thinRoute(s: LaidNode, t: LaidNode, cards: LaidNode[], lowRow: boolean, wiresY: number | null = null): Route {
  const sameCol = Math.abs(s.x - t.x) < 1;
  const sameRow = Math.abs(s.y - t.y) < 1;
  const below = t.y > s.y;
  const right = t.x > s.x;
  const routes: Route[] = [];
  if (wiresY != null && isWell(t.node.type) && !isWell(s.node.type) && wiresY > s.y + s.height) routes.push({ sourceHandle: "b", targetHandle: "t3", via: { y: wiresY } });
  if (sameCol) routes.push(below ? { sourceHandle: "b3", targetHandle: "t3" } : { sourceHandle: "t3", targetHandle: "b3" });
  if (sameRow) routes.push(right ? { sourceHandle: "r", targetHandle: "l" } : { sourceHandle: "l", targetHandle: "r" });
  if (!sameCol && !sameRow) routes.push(right ? { sourceHandle: "r", targetHandle: "l3" } : { sourceHandle: "l", targetHandle: "r3" });
  const under: Route = { sourceHandle: "b", targetHandle: "b3", clearance: BELOW };
  const over: Route = { sourceHandle: "t", targetHandle: "t", clearance: ABOVE };
  routes.push(...(lowRow ? [under, over] : [over, under]), { sourceHandle: "r", targetHandle: "r3", clearance: COL_GAP / 2 }, { sourceHandle: "l", targetHandle: "l3", clearance: COL_GAP / 2 });
  return routes.find((r) => routeClear(routePoints(s, t, r), s, t, cards)) ?? routes[0];
}

export interface PlantLayout {
  nodes: LaidNode[];
  edges: LaidEdge[];
  /** The doublets' frames (drawn behind their wells). */
  groups: LaidGroup[];
  width: number;
  height: number;
}

export interface LayoutOptions {
  /** Each doublet as it ran (Plant.doublets): the aquifer each well opens into, for the band. */
  doublets?: PlantDoublet[] | null;
}

/** The doublet a well belongs to: its value, else the number in its id (producer_2, injector_1a). */
export function doubletOf(n: Pick<GraphNode, "id" | "values">): number {
  const v = n.values?.doublet;
  if (typeof v === "number" && Number.isFinite(v) && v >= 1) return Math.round(v);
  const m = /_(\d+)[a-z]?$/i.exec(n.id);
  return m ? Number(m[1]) : 1;
}

/** "Producer 2, lower half open" → "Producer 2": the card's title (the open part has its own line). */
export const shortLabel = (label: string) => label.split(",")[0].trim();

/** "P1", "I1A": a well in a few letters, for the band. */
export function wellShort(n: Pick<GraphNode, "id" | "type" | "values">): string {
  const letter = /_\d+([a-z])$/i.exec(n.id)?.[1]?.toUpperCase() ?? "";
  return `${n.type === "producer_well" ? "P" : "I"}${doubletOf(n)}${letter}`;
}

/** Names short enough to read zoomed out (a dozen letters), by type. */
const FAR_NAMES: Record<string, string> = {
  heat_exchanger: "Exchanger",
  heatpump: "Heat pump",
  boiler: "Gas boiler",
  electric_boiler: "E-boiler",
  absorption: "Absorption",
  chillers: "Chillers",
  tower: "Towers",
  grid: "Grid",
  gas: "Gas",
  demand_heat: "Heat demand",
  demand_cold: "Cold demand",
  reservoir: "Reservoir",
};

/** The gas node zoomed out, by what the plant does with its gas. */
const GAS_FAR: Record<GasMode, string> = { buy: "Gas", produced: "Brine gas", sell: "Gas sold" };

/** A part's name zoomed out: "Exchanger", "Train 2", "Producer 1" (or "P1" on a narrow card). */
export function farName(n: Pick<GraphNode, "id" | "type" | "label" | "values"> & Partial<Pick<GraphNode, "gas">>, narrow = false): string {
  if (isWell(n.type)) return narrow ? wellShort(n) : shortLabel(n.label);
  if (n.type === "gas") return GAS_FAR[gasModeOf(n)];
  if (n.type === "treatment") {
    const k = /(\d+)\s*$/.exec(n.label)?.[1];
    return k ? `Train ${k}` : "Treatment";
  }
  return FAR_NAMES[n.type] ?? shortLabel(n.label);
}

/** Natural order of ids: injector_1a < injector_1b < injector_2 < train_10. */
const byIdNatural = (a: { id: string }, b: { id: string }) => a.id.localeCompare(b.id, "en", { numeric: true });

/**
 * A well's open part: full, upper or lower half, from its doublet's row, else its label, else its
 * open length against the aquifer's thickness (a half above or below the aquifer's middle).
 */
export function wellOpening(n: Pick<GraphNode, "type" | "label" | "values">, row?: Pick<PlantDoublet, "producer_open" | "injector_open" | "depth_m"> | null, thickness_m = 100): Opening {
  const fromRow = row ? (n.type === "producer_well" ? row.producer_open : row.injector_open) : null;
  if (fromRow === "full" || fromRow === "upper" || fromRow === "lower") return fromRow;
  if (/lower half/i.test(n.label)) return "lower";
  if (/upper half/i.test(n.label)) return "upper";
  const open = n.values.open_m;
  if (typeof open === "number" && open < thickness_m - 1e-6) {
    const aquifer = row?.depth_m;
    if (typeof aquifer === "number" && typeof n.values.depth_m === "number") return n.values.depth_m > aquifer ? "lower" : "upper";
  }
  return "full";
}

/** "fully open", "lower half open", "upper half open". */
export const openingWords = (o: Opening | string) => (o === "lower" ? "lower half open" : o === "upper" ? "upper half open" : "fully open");

/** Lays the plant out (see the top of the file). Pure: the same graph gives the same layout. */
export function layoutPlant(graph: Pick<Graph, "nodes" | "edges">, opts: LayoutOptions = {}): PlantLayout {
  const nodes = graph.nodes;
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const typeOf = (id: string) => byId.get(id)?.type ?? "";
  const demandIds = new Set(nodes.filter((n) => isDemand(n.type)).map((n) => n.id));
  const reservoir = nodes.find((n) => n.type === "reservoir");
  const thickness = reservoir?.values.thickness_m || 100;
  const rows = opts.doublets ?? [];
  const rowOf = (d: number) => rows.find((r) => r.doublet === d) ?? rows[d - 1] ?? null;

  // 1. The doublets: each a group of its injector(s), then its producer, left to right.
  const wells = nodes.filter((n) => isWell(n.type));
  const numbers = [...new Set(wells.map(doubletOf))].sort((a, b) => a - b);
  const groups = numbers.map((d) => {
    const mine = wells.filter((w) => doubletOf(w) === d);
    return { d, members: [...mine.filter((w) => w.type === "injector_well").sort(byIdNatural), ...mine.filter((w) => w.type === "producer_well").sort(byIdNatural)] };
  });
  const hasWells = wells.length > 0;

  // 2. The treatment trains, top to bottom in the order of their first doublet; the train each producer feeds.
  const producers = groups.flatMap((g) => g.members.filter((w) => w.type === "producer_well"));
  const feeds = new Map<string, string>();
  for (const e of graph.edges) if (e.kind === "brine" && typeOf(e.source) === "producer_well" && typeOf(e.target) === "treatment") feeds.set(e.source, e.target);
  const firstOf = (trainId: string) => {
    const i = producers.findIndex((p) => feeds.get(p.id) === trainId);
    return i < 0 ? Number.POSITIVE_INFINITY : i;
  };
  const trains = nodes.filter((n) => n.type === "treatment").sort((a, b) => firstOf(a.id) - firstOf(b.id) || byIdNatural(a, b));
  const K = trains.length;
  const trainRank = new Map(trains.map((t, i) => [t.id, i]));

  // 3. A row and a plant column for every other node; unknown types go to the middle row, at the right.
  const slot = new Map<string, { row: Row; col: number }>();
  let extra = 4;
  for (const n of nodes) {
    if (demandIds.has(n.id) || n.type === "reservoir" || isWell(n.type)) continue;
    slot.set(n.id, SLOTS[n.type] ?? { row: "mid", col: extra++ });
  }
  const used = [...new Set([...slot.values()].map((s) => s.col))].sort((a, b) => a - b);
  const colOf = new Map(used.map((c, i) => [c, i]));
  // Left of the trains: the risers of the producers' brine, one per train.
  const plantX = hasWells ? DESCENT * Math.max(1, K) + 14 : 0;
  const demandX = plantX + used.length * COL_W + 8;
  const plantRight = demandIds.size ? demandX + DEMAND_W : plantX + Math.max(1, used.length) * COL_W - COL_GAP;

  // 4. Rows, top down: cooling, its corridor (the cold lanes), the middle row, the heat corridor,
  //    the brine row (the trains stacked in their column).
  const has = (row: Row) => [...slot.values()].some((s) => s.row === row);
  const coldDemand = nodes.find((n) => n.type === "demand_cold");
  const heatDemand = nodes.find((n) => n.type === "demand_heat");
  const incoming = (id: string | undefined) => (id ? graph.edges.filter((e) => e.target === id && byId.has(e.source)) : []);
  const coldIn = incoming(coldDemand?.id);
  const heatIn = incoming(heatDemand?.id);
  const demandH = (n: number) => Math.max(DEMAND_MIN_H, (n - 1) * LANE + 64);
  const coldH = demandH(coldIn.length);
  const heatH = demandH(heatIn.length);

  let y = has("top") ? NODE_H : 0;
  const coldCorr = has("top") || coldDemand ? corridorH(coldIn.length) : 0;
  const coldY = y + coldCorr / 2; // the cold corridor's middle
  y += coldCorr;
  const midY = y;
  if (has("mid")) y += NODE_H;
  const heatCorr = corridorH(heatIn.length);
  // The two demands sit one over the other at the right: kept apart.
  const heatY = Math.max(y + heatCorr / 2, coldDemand && heatDemand ? coldY + coldH / 2 + heatH / 2 + 24 : 0);
  const unitY = heatY + heatCorr / 2;
  const trainsH = K ? K * NODE_H + (K - 1) * TRAIN_GAP : 0;
  const brineBottom = has("brine") ? unitY + Math.max(NODE_H, trainsH) : unitY;
  const rowY: Record<Row, number> = { top: 0, mid: midY, brine: unitY };

  // 5. Lanes between the plant and the wells: the brine back to the injectors on top, then one per
  //    train (its producers' brine on the way up), then the grid's line to the well pumps.
  const isReturn = (e: GraphEdge) => e.kind === "brine" && typeOf(e.target) === "injector_well" && typeOf(e.source) !== "reservoir";
  const hasReturn = hasWells && graph.edges.some(isReturn);
  const hotLane = new Map<string, number>();
  for (const e of graph.edges) if (e.kind === "brine" && typeOf(e.source) === "producer_well" && typeOf(e.target) !== "reservoir") hotLane.set(e.id, trainRank.get(e.target) ?? 0);
  const nHot = hotLane.size ? Math.max(...hotLane.values()) + 1 : 0;
  const nLanes = hasWells ? (hasReturn ? 1 : 0) + nHot : 0;
  const laneY = Array.from({ length: nLanes }, (_, i) => brineBottom + LANE_PAD + i * LANE);
  const returnY = hasReturn ? laneY[0] : null;
  const hotY = (k: number) => laneY[(hasReturn ? 1 : 0) + k];
  const wired = hasWells && graph.edges.some((e) => isThin(e.kind) && isWell(typeOf(e.target)) && !isWell(typeOf(e.source)));
  const lastLane = nLanes ? laneY[nLanes - 1] : brineBottom;
  const wiresY = wired ? lastLane + (nLanes ? LANE - 4 : LANE_PAD) : null;
  const framesY = (wiresY ?? lastLane) + (nLanes || wired ? 16 : LANE_PAD);
  const wellsY = framesY + GROUP_HEAD;

  // 6. The wells at full width, under the plant: each card as wide as it can be (WELL_W at most)
  //    with the reservoir's facts beside the aquifer; narrower, when there are many, filling the
  //    plant's width (the facts then go under the aquifer), down to WELL_MIN_W.
  const gaps = groups.reduce((a, g) => a + Math.max(0, g.members.length - 1), 0);
  const overhead = GUTTER + groups.length * 2 * GROUP_PAD + Math.max(0, groups.length - 1) * GROUP_GAP + gaps * WELL_GAP;
  const fit = (room: number) => Math.min(WELL_W, Math.floor((room - overhead) / Math.max(1, wells.length)));
  const withFacts = fit(plantRight - RESERVOIR_FACTS_W - 18 - 32);
  const wellW = withFacts >= WELL_FACTS_MIN_W ? withFacts : Math.max(WELL_MIN_W, fit(plantRight));
  const wellX = new Map<string, number>();
  const laidGroups: LaidGroup[] = [];
  let gx = GUTTER + GROUP_PAD;
  for (const g of groups) {
    const start = gx;
    for (const w of g.members) {
      wellX.set(w.id, gx);
      gx += wellW + WELL_GAP;
    }
    const end = gx - WELL_GAP;
    laidGroups.push({ id: `doublet-${g.d}`, doublet: g.d, label: `Doublet ${g.d}`, x: start - GROUP_PAD, y: framesY, width: end - start + 2 * GROUP_PAD, height: GROUP_HEAD + WELL_H + GROUP_PAD, wells: g.members.map((w) => w.id) });
    gx = end + GROUP_PAD + GROUP_GAP + GROUP_PAD;
  }
  const wellsRight = hasWells ? Math.max(...[...wellX.values()].map((x) => x + wellW)) : 0;

  const laid = new Map<string, LaidNode>();
  for (const w of wells) laid.set(w.id, { id: w.id, node: w, x: wellX.get(w.id)!, y: wellsY, width: wellW, height: WELL_H, lanes: [] });
  for (const n of nodes) {
    const s = slot.get(n.id);
    if (!s) continue;
    const stack = n.type === "treatment" ? (trainRank.get(n.id) ?? 0) * (NODE_H + TRAIN_GAP) : 0;
    laid.set(n.id, { id: n.id, node: n, x: plantX + colOf.get(s.col)! * COL_W, y: rowY[s.row] + stack, width: NODE_W, height: NODE_H, lanes: [] });
  }

  // 7. Lanes into each demand: from above (rightmost first, highest), then from below (leftmost first).
  const edges: LaidEdge[] = [];
  const laneEdge = new Map<string, { k: number; above: boolean }>();
  const placeDemand = (demand: GraphNode | undefined, ins: GraphEdge[], corridorY: number) => {
    if (!demand) return;
    const centre = (id: string) => (laid.get(id)?.x ?? 0) + (laid.get(id)?.width ?? NODE_W) / 2;
    const aboveOf = (e: GraphEdge) => (laid.get(e.source)?.y ?? 0) < corridorY;
    const above = ins.filter(aboveOf).sort((a, b) => centre(b.source) - centre(a.source));
    const below = ins.filter((e) => !aboveOf(e)).sort((a, b) => centre(a.source) - centre(b.source));
    const order = [...above, ...below];
    const h = demandH(order.length);
    const y = corridorY - h / 2;
    const lanes = order.map((_, k) => h / 2 + (k - (order.length - 1) / 2) * LANE);
    order.forEach((e, k) => laneEdge.set(e.id, { k, above: aboveOf(e) }));
    laid.set(demand.id, { id: demand.id, node: demand, x: demandX, y, width: DEMAND_W, height: h, lanes });
  };
  placeDemand(coldDemand, coldIn, coldY);
  placeDemand(heatDemand, heatIn, heatY);
  // Demand nodes of a type not handled above (a second one, say): stack them under the rest.
  let spare = heatY + heatH / 2 + 40;
  for (const n of nodes) {
    if (laid.has(n.id) || n.type === "reservoir") continue;
    laid.set(n.id, { id: n.id, node: n, x: demandX, y: spare, width: DEMAND_W, height: NODE_H, lanes: [] });
    spare += NODE_H + 40;
  }

  // 8. The reservoir: a band under everything, each well's open part drawn at its depth, its facts
  //    at the right of the aquifer, or under it when the wells leave no room.
  if (reservoir) {
    const cards = [...laid.values()];
    const floor = hasWells ? framesY + GROUP_HEAD + WELL_H + GROUP_PAD : Math.max(0, ...cards.map((l) => l.y + l.height));
    const left = hasWells ? 0 : Math.min(...cards.map((l) => l.x));
    const right = Math.max(left + 2 * NODE_W, plantRight, wellsRight + GROUP_PAD);
    const bandWells: BandWell[] = groups.flatMap((g) =>
      g.members.map((w) => {
        const row = rowOf(g.d);
        const mid = Number.isFinite(w.values.depth_m) ? w.values.depth_m : row?.depth_m ?? reservoir.values.depth_m ?? 0;
        const open = Number.isFinite(w.values.open_m) ? w.values.open_m : thickness;
        const opening = wellOpening(w, row, thickness);
        const aquifer = typeof row?.depth_m === "number" ? row.depth_m : opening === "full" ? mid : opening === "lower" ? mid - thickness / 4 : mid + thickness / 4;
        return {
          id: w.id,
          kind: w.type === "producer_well" ? ("producer" as const) : ("injector" as const),
          short: wellShort(w),
          doublet: g.d,
          x: wellX.get(w.id)! + wellW / 2 - left,
          aquifer_m: aquifer,
          top_m: mid - open / 2,
          base_m: mid + open / 2,
          opening,
        };
      }),
    );
    const aquifers = [...new Set(bandWells.map((w) => w.aquifer_m))].sort((a, b) => a - b);
    if (!aquifers.length && Number.isFinite(reservoir.values.depth_m)) aquifers.push(reservoir.values.depth_m);
    // The aquifer reaches past the last well far enough for its label.
    const lastWell = bandWells[bandWells.length - 1];
    const section = hasWells ? Math.max(wellsRight + GROUP_PAD - left, lastWell ? lastWell.x + openLabelW(lastWell.opening) : 0) : 0;
    const factsBelow = hasWells && right - left - section - 18 < RESERVOIR_FACTS_W;
    laid.set(reservoir.id, {
      id: reservoir.id,
      node: reservoir,
      x: left,
      y: floor + RESERVOIR_GAP,
      width: Math.max(right, left + section) - left,
      height: reservoirHeight(reservoir, Math.max(1, aquifers.length), factsBelow),
      lanes: [],
      wells: bandWells,
      aquifers,
      band: hasWells ? { section, facts: factsBelow ? "below" : "right" } : undefined,
    });
  }

  // 9. Handles for every edge.
  const cards = [...laid.values()];
  const descentX = (target: LaidNode) => target.x - DESCENT * (1 + (trainRank.get(target.id) ?? 0));
  for (const e of graph.edges) {
    const s = laid.get(e.source);
    const t = laid.get(e.target);
    if (!s || !t) continue;
    if (isThin(e.kind)) {
      const lowRow = [s, t].some((n) => slot.get(n.id)?.row === "brine");
      edges.push({ id: e.id, edge: e, ...thinRoute(s, t, cards, lowRow, wiresY), layer: 0 });
      continue;
    }
    const layer = e.kind === "brine" ? (isReturn(e) ? 3 : 2) : 1;
    if (s.node.type === "reservoir") {
      edges.push({ id: e.id, edge: e, sourceHandle: `res-${t.id}`, targetHandle: "b", layer });
      continue;
    }
    if (t.node.type === "reservoir") {
      edges.push({ id: e.id, edge: e, sourceHandle: "b", targetHandle: `res-${s.id}`, layer });
      continue;
    }
    const lane = laneEdge.get(e.id);
    if (lane) {
      edges.push({ id: e.id, edge: e, sourceHandle: lane.above ? "b" : "tq", targetHandle: `lane-${lane.k}`, layer });
      continue;
    }
    if (isReturn(e) && returnY != null) {
      // Down into the top lane, and into the injector three quarters along its top, clear of the
      // doublet's name on the frame.
      edges.push({ id: e.id, edge: e, sourceHandle: "b", targetHandle: "t3", via: { y: returnY }, layer });
      continue;
    }
    const hot = hotLane.get(e.id);
    if (hot != null) {
      // Up to the train's lane, left past the plant, up and into the train's left side.
      edges.push({ id: e.id, edge: e, sourceHandle: "t", targetHandle: "l", via: { y: hotY(hot), x: descentX(t) }, layer });
      continue;
    }
    if (e.kind === "gas" && s.node.type === "treatment" && Math.abs(s.x - t.x) < 1 && t.y < s.y) {
      // The top train sends its gas straight up; one under it goes round the trains above it.
      const between = trains.some((o) => o.id !== s.id && (laid.get(o.id)?.y ?? 0) < s.y && (laid.get(o.id)?.y ?? 0) > t.y);
      edges.push(between ? { id: e.id, edge: e, sourceHandle: "r3", targetHandle: "rq", clearance: 12, layer } : { id: e.id, edge: e, sourceHandle: "t", targetHandle: "b", layer });
      continue;
    }
    const sameCol = Math.abs(s.x - t.x) < 1;
    if (t.x > s.x + 1) edges.push({ id: e.id, edge: e, sourceHandle: "r", targetHandle: "l", layer });
    else if (sameCol) edges.push({ id: e.id, edge: e, sourceHandle: t.y > s.y ? "b" : "t", targetHandle: t.y > s.y ? "t" : "b", layer });
    else edges.push({ id: e.id, edge: e, sourceHandle: t.y > s.y ? "b" : "t", targetHandle: "r", layer });
  }
  // Drawn in layers (a later pipe lies over an earlier one), and each crossing gets its bridge.
  const ordered = edges.map((e, i) => ({ e, i })).sort((a, b) => a.e.layer - b.e.layer || a.i - b.i).map((x) => x.e);
  addBridges(ordered, laid);

  const all = [...laid.values()];
  const width = Math.max(0, ...all.map((n) => n.x + n.width));
  const height = Math.max(0, ...all.map((n) => n.y + n.height));
  return { nodes: nodes.map((n) => laid.get(n.id)!), edges: ordered, groups: laidGroups, width, height };
}

// ------------------------------------------------------------------ crossings

/** A handle's point on a laid node: a card's handle, a demand's lane, or a well's place on the band. */
export function endPoint(n: LaidNode, h: SourceHandle | TargetHandle): { x: number; y: number; side: Side } {
  if (h.startsWith("lane-")) return { x: n.x, y: n.y + (n.lanes[Number(h.slice(5))] ?? n.height / 2), side: "l" };
  if (h.startsWith("res-")) {
    const w = n.wells?.find((x) => x.id === h.slice(4));
    return { x: n.x + (w ? w.x : n.width / 2), y: n.y, side: "t" };
  }
  const [x, y] = handlePoint(n, h as CardHandle);
  return { x, y, side: handleSide(h as CardHandle) };
}

/** The corners of a laid edge, as PipeEdge draws it. */
export function laidEdgePoints(e: LaidEdge, laid: Map<string, LaidNode>): [number, number][] {
  const s = laid.get(e.edge.source);
  const t = laid.get(e.edge.target);
  if (!s || !t) return [];
  const a = endPoint(s, e.sourceHandle);
  const b = endPoint(t, e.targetHandle);
  if (e.via) return viaPoints(a.x, a.y, a.side, b.x, b.y, b.side, e.via).pts;
  return pipePoints(a.x, a.y, a.side, b.x, b.y, b.side, e.clearance).pts;
}

/** Where a horizontal and a vertical segment cross, both well inside their ends (corners and joints don't count). */
function crossing(h: [[number, number], [number, number]], v: [[number, number], [number, number]], end = 4): [number, number] | null {
  const [hx0, hx1] = [Math.min(h[0][0], h[1][0]), Math.max(h[0][0], h[1][0])];
  const hy = h[0][1];
  const [vy0, vy1] = [Math.min(v[0][1], v[1][1]), Math.max(v[0][1], v[1][1])];
  const vx = v[0][0];
  if (vx <= hx0 + end || vx >= hx1 - end || hy <= vy0 + end || hy >= vy1 - end) return null;
  return [vx, hy];
}

/** The pipes each pipe passes over: for every crossing, a bridge on the one drawn later (on top). */
export function addBridges(ordered: LaidEdge[], laid: Map<string, LaidNode>): void {
  const segs = ordered.map((e) => {
    if (isThin(e.edge.kind)) return [];
    const pts = laidEdgePoints(e, laid);
    const out: { a: [number, number]; b: [number, number]; dir: "h" | "v" }[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i];
      const b = pts[i + 1];
      if (Math.abs(a[1] - b[1]) < 0.5 && Math.abs(a[0] - b[0]) > 0.5) out.push({ a, b, dir: "h" });
      else if (Math.abs(a[0] - b[0]) < 0.5 && Math.abs(a[1] - b[1]) > 0.5) out.push({ a, b, dir: "v" });
    }
    return out;
  });
  for (let top = 0; top < ordered.length; top++) {
    const bridges: Bridge[] = [];
    for (let under = 0; under < top; under++) {
      for (const p of segs[top])
        for (const q of segs[under]) {
          if (p.dir === q.dir) continue;
          const x = p.dir === "h" ? crossing([p.a, p.b], [q.a, q.b]) : crossing([q.a, q.b], [p.a, p.b]);
          if (x && !bridges.some((b) => Math.hypot(b.x - x[0], b.y - x[1]) < 1)) bridges.push({ x: x[0], y: x[1], dir: p.dir });
        }
    }
    if (bridges.length) ordered[top].bridges = bridges;
    else delete ordered[top].bridges;
  }
}

/** Whether a point lies on a route's run in the given direction (a bridge still on its pipe). */
export function onRun(pts: [number, number][], b: Bridge, tol = 1): boolean {
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, ay] = pts[i];
    const [bx, by] = pts[i + 1];
    if (b.dir === "h" && Math.abs(ay - by) < tol && Math.abs(ay - b.y) < tol && b.x > Math.min(ax, bx) && b.x < Math.max(ax, bx)) return true;
    if (b.dir === "v" && Math.abs(ax - bx) < tol && Math.abs(ax - b.x) < tol && b.y > Math.min(ay, by) && b.y < Math.max(ay, by)) return true;
  }
  return false;
}

// ------------------------------------------------------------------ pipes

const horizontal = (s: Side) => s === "l" || s === "r";

/**
 * The corners of an orthogonal pipe from a source handle to a target handle, and where its label
 * goes. Opposite sides: a step at mid-x (or mid-y); vertical → horizontal: an L; the same side on
 * both: out past the farther handle by `clearance`, across, and back (a U round the outside).
 */
export function pipePoints(sx: number, sy: number, sSide: Side, tx: number, ty: number, tSide: Side, clearance = ABOVE): { pts: [number, number][]; labelX: number; labelY: number } {
  const pts: [number, number][] = [[sx, sy]];
  let labelX = (sx + tx) / 2;
  let labelY = (sy + ty) / 2;
  if (sSide === tSide) {
    if (horizontal(sSide)) {
      const mx = sSide === "l" ? Math.min(sx, tx) - clearance : Math.max(sx, tx) + clearance;
      pts.push([mx, sy], [mx, ty]);
      labelX = mx;
    } else {
      const my = sSide === "t" ? Math.min(sy, ty) - clearance : Math.max(sy, ty) + clearance;
      pts.push([sx, my], [tx, my]);
      labelY = my;
    }
  } else if (horizontal(sSide) && horizontal(tSide)) {
    if (Math.abs(sy - ty) > 0.5) {
      const mx = (sx + tx) / 2;
      pts.push([mx, sy], [mx, ty]);
      // On the step, a quarter of the way from the target's height: in the corridor next to the
      // target's row rather than level with the row between (the drive brine up to the
      // absorption chiller would put it on the gas pipe it bridges).
      labelY = ty + (sy - ty) / 4;
    }
  } else if (!horizontal(sSide) && horizontal(tSide)) {
    pts.push([sx, ty]);
    // On the run along the lane, a little past the corner, so the labels of neighbouring lanes
    // stand apart.
    labelX = sx + Math.min(Math.max((tx - sx) * 0.42, 40), Math.abs(tx - sx) - 36);
    labelY = ty;
    if (tx < sx) labelX = sx - Math.min(Math.max((sx - tx) * 0.42, 40), Math.abs(sx - tx) - 36);
  } else if (horizontal(sSide) && !horizontal(tSide)) {
    pts.push([tx, sy]);
    labelX = (sx + tx) / 2;
    labelY = sy;
  } else if (Math.abs(sx - tx) > 0.5) {
    const my = (sy + ty) / 2;
    pts.push([sx, my], [tx, my]);
  }
  pts.push([tx, ty]);
  return { pts, labelX, labelY };
}

/**
 * The corners of a pipe through a lane: out of the source's side to the lane's height, along it,
 * then into the target: straight down (or up) into a top or bottom handle, or down at `via.x` and
 * across into a side handle. The label sits on the run along the lane.
 */
export function viaPoints(sx: number, sy: number, _sSide: Side, tx: number, ty: number, tSide: Side, via: Via): { pts: [number, number][]; labelX: number; labelY: number } {
  const pts: [number, number][] = [[sx, sy], [sx, via.y]];
  if (horizontal(tSide)) {
    const dx = via.x ?? (tSide === "l" ? tx - DESCENT : tx + DESCENT);
    pts.push([dx, via.y], [dx, ty]);
    pts.push([tx, ty]);
    return { pts, labelX: sx + (dx - sx) * 0.5, labelY: via.y };
  }
  pts.push([tx, via.y], [tx, ty]);
  return { pts, labelX: sx + (tx - sx) * 0.5, labelY: via.y };
}

/** pipePoints as an SVG path with rounded corners. */
export function pipePath(sx: number, sy: number, sSide: Side, tx: number, ty: number, tSide: Side, radius = 12, clearance = ABOVE): { path: string; labelX: number; labelY: number } {
  const { pts, labelX, labelY } = pipePoints(sx, sy, sSide, tx, ty, tSide, clearance);
  return { path: roundedPath(pts, radius), labelX, labelY };
}

/** A hop's radius (px): wide enough to clear the widest pipe below (11 px) with a gap. */
export const HOP_R = 9;

/**
 * The straight run from (x0, y0) to (x1, y1) with a hop (a half circle over the pipe below) at
 * each crossing on it, in the order the run meets them. Horizontal runs hop up, vertical runs hop
 * left, whichever way they go, so every crossing on the canvas reads the same.
 */
function hopRun(x0: number, y0: number, x1: number, y1: number, hops: Bridge[], r: number, r1: (v: number) => number): string {
  const h = Math.abs(y1 - y0) < 0.5;
  const v = Math.abs(x1 - x0) < 0.5;
  if (!h && !v) return ` L${r1(x1)},${r1(y1)}`;
  const sign = h ? Math.sign(x1 - x0) : Math.sign(y1 - y0);
  const along = (b: Bridge) => (h ? b.x : b.y);
  const lo = Math.min(h ? x0 : y0, h ? x1 : y1) + r;
  const hi = Math.max(h ? x0 : y0, h ? x1 : y1) - r;
  const here = hops
    .filter((b) => b.dir === (h ? "h" : "v") && (h ? Math.abs(b.y - y0) < 1 : Math.abs(b.x - x0) < 1) && along(b) >= lo && along(b) <= hi)
    .sort((a, b) => sign * (along(a) - along(b)));
  let d = "";
  for (const b of here) {
    if (h) {
      // Moving right, a clockwise arc goes over the top; moving left, an anticlockwise one.
      d += ` L${r1(b.x - sign * r)},${r1(y0)} A${r} ${r} 0 0 ${sign > 0 ? 1 : 0} ${r1(b.x + sign * r)},${r1(y0)}`;
    } else {
      d += ` L${r1(x0)},${r1(b.y - sign * r)} A${r} ${r} 0 0 ${sign > 0 ? 0 : 1} ${r1(x0)},${r1(b.y + sign * r)}`;
    }
  }
  return `${d} L${r1(x1)},${r1(y1)}`;
}

/** `roundedPath` with a hop over the pipe below at each of `hops` (the crossings on this pipe). */
export function hoppedPath(pts: [number, number][], radius: number, hops: Bridge[], r = HOP_R): string {
  if (!hops.length) return roundedPath(pts, radius);
  const r1 = (v: number) => Math.round(v * 10) / 10;
  let d = `M${r1(pts[0][0])},${r1(pts[0][1])}`;
  let [penX, penY] = pts[0];
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1];
    const [cx, cy] = pts[i];
    const [nx, ny] = pts[i + 1];
    const inLen = Math.hypot(cx - px, cy - py);
    const outLen = Math.hypot(nx - cx, ny - cy);
    const rr = Math.min(radius, inLen / 2, outLen / 2);
    if (rr < 0.5) {
      d += hopRun(penX, penY, cx, cy, hops, r, r1);
      [penX, penY] = [cx, cy];
      continue;
    }
    const ax = cx - ((cx - px) / inLen) * rr;
    const ay = cy - ((cy - py) / inLen) * rr;
    const bx = cx + ((nx - cx) / outLen) * rr;
    const by = cy + ((ny - cy) / outLen) * rr;
    d += hopRun(penX, penY, ax, ay, hops, r, r1) + ` Q${r1(cx)},${r1(cy)} ${r1(bx)},${r1(by)}`;
    [penX, penY] = [bx, by];
  }
  const last = pts[pts.length - 1];
  return `${d}${hopRun(penX, penY, last[0], last[1], hops, r, r1)}`;
}

/** The hops alone (a white halo under them cuts the pipe below where the hop passes over it). */
export function hopHalo(hops: Bridge[], r = HOP_R): string {
  return hops
    .map((b) =>
      b.dir === "h" ? `M${b.x - r},${b.y} A${r} ${r} 0 0 1 ${b.x + r},${b.y}` : `M${b.x},${b.y - r} A${r} ${r} 0 0 0 ${b.x},${b.y + r}`,
    )
    .join(" ");
}

export function roundedPath(pts: [number, number][], radius: number): string {
  const r1 = (v: number) => Math.round(v * 10) / 10;
  let d = `M${r1(pts[0][0])},${r1(pts[0][1])}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1];
    const [cx, cy] = pts[i];
    const [nx, ny] = pts[i + 1];
    const inLen = Math.hypot(cx - px, cy - py);
    const outLen = Math.hypot(nx - cx, ny - cy);
    const r = Math.min(radius, inLen / 2, outLen / 2);
    if (r < 0.5) {
      d += ` L${r1(cx)},${r1(cy)}`;
      continue;
    }
    const ax = cx - ((cx - px) / inLen) * r;
    const ay = cy - ((cy - py) / inLen) * r;
    const bx = cx + ((nx - cx) / outLen) * r;
    const by = cy + ((ny - cy) / outLen) * r;
    d += ` L${r1(ax)},${r1(ay)} Q${r1(cx)},${r1(cy)} ${r1(bx)},${r1(by)}`;
  }
  const last = pts[pts.length - 1];
  return `${d} L${r1(last[0])},${r1(last[1])}`;
}

// ------------------------------------------------------------------ colours and kinds

/**
 * Brine colour: one neutral brown-grey (the rock's water), darker when hot and lighter when cold,
 * on the challenge's range (105 °C and up the darkest, 45 °C and down, about the 40 K cap below
 * the wellhead, the lightest). It never takes the heating network's orange or the cooling
 * network's blue: the temperature is in the pipe's label.
 */
export const BRINE_HOT = 105;
export const BRINE_COLD = 45;
const BRINE_DARK: [number, number, number] = [112, 86, 62];
const BRINE_LIGHT: [number, number, number] = [166, 152, 136];
export function brineColor(t: number | null): string {
  if (t == null || !Number.isFinite(t)) return "rgb(139,121,103)";
  const f = Math.min(1, Math.max(0, (BRINE_HOT - t) / (BRINE_HOT - BRINE_COLD)));
  const c = BRINE_DARK.map((v, i) => Math.round(v + (BRINE_LIGHT[i] - v) * f));
  return `rgb(${c.join(",")})`;
}

export interface TypeMeta {
  /** The series colour (the Energy tab's): the part's identity, never its text. */
  color: string;
  tint: string;
  /** A 16 × 16 stroke icon. */
  icon: string;
  /** A short noun for its output: "heat", "cold". */
  makes?: "heat" | "cold";
}

const ICONS = {
  producer: "M8 14V3M4.5 6.5 8 3l3.5 3.5",
  injector: "M8 2v11M4.5 9.5 8 13l3.5-3.5",
  absorption: "M8 1.8v12.4M2.6 4.9l10.8 6.2M2.6 11.1l10.8-6.2",
  hex: "M2.5 5.5h11M10.5 2.5l3 3-3 3M13.5 10.5h-11M5.5 7.5l-3 3 3 3",
  hp: "M12.6 6.2A5 5 0 0 0 3.6 5.4M3.4 9.8a5 5 0 0 0 9 .8M12.8 2.8v3.6H9.2M3.2 13.2V9.6h3.6",
  chillers: "M9.2 1.8 3.8 9h4.1l-1.1 5.2L12.2 7H8.1z",
  boiler: "M8 1.8c2.2 3 4.2 4.6 4.2 7.6a4.2 4.2 0 0 1-8.4 0C3.8 6.8 6 5.6 8 1.8z",
  // The boiler's flame with a lightning bolt in it: heat made from electricity.
  electricBoiler: "M8 1.8c2.2 3 4.2 4.6 4.2 7.6a4.2 4.2 0 0 1-8.4 0C3.8 6.8 6 5.6 8 1.8zM9 5.9 6.7 9.5h2.6l-1.9 3",
  house: "M2.5 8 8 3.2 13.5 8M4.2 6.7V13h7.6V6.7",
  gas: "M3 13.5h10M5 13.5V6.5l3-3 3 3v7M8 9.5v2",
  // Gas leaving the plant: an arrow into the gas grid's pipe.
  gasOut: "M2.5 8h8M7.5 4.8 10.7 8l-3.2 3.2M13.5 2.8v10.4",
  grid: "M5 2.5 3 8h4l-2 5.5M11 2.5v11M9 5h4M9 9h4",
  // A hyperbolic tower with its plume.
  tower: "M4.6 14.4 6.1 8.2c.8-1 3-1 3.8 0l1.5 6.2zM6.1 8.2h3.8M5.4 5.6c.9-1.2 4.3-1.2 5.2 0M6.4 3.2c.6-.8 2.6-.8 3.2 0",
  // A separator vessel with its gas outlet on top, and a filter mesh under it.
  train: "M5 5.2a3 3 0 0 1 6 0V13H5zM8 1.6v1.6M5 9.4h6M6.6 11.2h2.8",
  part: "M3 3h10v10H3z",
};

export const TYPE_META: Record<string, TypeMeta> = {
  producer_well: { color: "#c24e1c", tint: "#fcede6", icon: ICONS.producer },
  reservoir: { color: "#8a5a2b", tint: "#f6efe7", icon: ICONS.producer },
  injector_well: { color: "#2363a6", tint: "#e8effb", icon: ICONS.injector },
  heat_exchanger: { color: "#c24e1c", tint: "#fcede6", icon: ICONS.hex, makes: "heat" },
  heatpump: { color: "#e3a33b", tint: "#fbf1dc", icon: ICONS.hp, makes: "heat" },
  boiler: { color: "#7856c4", tint: "#efe9fa", icon: ICONS.boiler, makes: "heat" },
  // Raspberry: a heat colour apart from the exchanger's orange and the gas boiler's violet (the
  // Energy tab's, validated with them for colour-blind readers).
  electric_boiler: { color: "#c8378a", tint: "#fbe9f3", icon: ICONS.electricBoiler, makes: "heat" },
  absorption: { color: "#2363a6", tint: "#e8effb", icon: ICONS.absorption, makes: "cold" },
  chillers: { color: "#139fbf", tint: "#e2f4f8", icon: ICONS.chillers, makes: "cold" },
  demand_heat: { color: "#c24e1c", tint: "#fcede6", icon: ICONS.house },
  demand_cold: { color: "#2363a6", tint: "#e8effb", icon: ICONS.house },
  gas: { color: "#7856c4", tint: "#efe9fa", icon: ICONS.gas },
  grid: { color: "#66727c", tint: "#eef2f2", icon: ICONS.grid },
  tower: { color: "#5b7f94", tint: "#e9f0f4", icon: ICONS.tower },
  // A treatment train only degasses and filters the brine: a quiet slate, not a heat colour.
  treatment: { color: "#4f6b7a", tint: "#e9f0f3", icon: ICONS.train },
};
export const metaOf = (type: string): TypeMeta => TYPE_META[type] ?? { color: "#66727c", tint: "#eef2f2", icon: ICONS.part };

/** A part's icon: its type's, but sold gas leaves the plant (an arrow into the gas grid). */
export const iconOf = (n: Pick<GraphNode, "type"> & Partial<Pick<GraphNode, "gas">>): string => (n.type === "gas" && gasModeOf(n) === "sell" ? ICONS.gasOut : metaOf(n.type).icon);

export const EDGE_COLORS: Record<GraphEdge["kind"], string> = {
  brine: "#c24e1c",
  network: "#c24e1c",
  cold: "#2363a6",
  gas: "#7856c4",
  // Electricity: amber, dotted (PlantCanvas DASH).
  electricity: "#d08a0e",
  // The heat the chillers send to the towers: cyan, dashed, apart from the cold network's blue.
  reject: "#0fa3c2",
};

/** Thin lines: electricity (dotted), and the heat the towers take (dashed). */
export const isThin = (kind: GraphEdge["kind"]) => kind === "electricity" || kind === "reject";

// ------------------------------------------------------------------ the year

/** What a series measures: heat or cold given, electricity drawn, or heat rejected to the towers. */
export type SeriesKind = "heat" | "cold" | "power" | "reject";

/** The daily series (365 values, MW) that drives a node, its size, and what it stands for. */
export interface NodeSeries {
  values: number[];
  /** What 100 % on the load ring means: the unit's size, or the demand's peak (the year's peak for the grid and the towers). */
  capacity: number;
  /** For words: "heat given", "electricity drawn" … */
  kind: SeriesKind;
  /** The node only shows the series (gas follows the boiler); no load ring. */
  follows?: boolean;
}

/** Words for a series on a day: "heat given", "cold needed", "electricity drawn", "heat rejected". */
export function seriesWords(kind: SeriesKind, demand: boolean): string {
  switch (kind) {
    case "heat":
      return demand ? "heat needed" : "heat given";
    case "cold":
      return demand ? "cold needed" : "cold given";
    case "power":
      return "electricity drawn";
    case "reject":
      return "heat rejected";
  }
}

/** The sum, day by day, of the 365-day series in a record (null when there is none). */
export function sumSeries(rec: Partial<Record<string, number[]>> | undefined): number[] | null {
  const lists = Object.values(rec ?? {}).filter((v): v is number[] => Array.isArray(v) && v.length > 0);
  if (!lists.length) return null;
  const n = Math.max(...lists.map((v) => v.length));
  const out = new Array<number>(n).fill(0);
  for (const v of lists) for (let i = 0; i < v.length; i++) out[i] += v[i] ?? 0;
  return out;
}

/** The electricity a unit draws, by its type (the wells' pumps are counted at the producer). */
const POWER_OF: Record<string, PowerUser> = { heatpump: "hp", chillers: "chillers", tower: "towers", producer_well: "pumps", injector_well: "pumps", electric_boiler: "electric_boiler" };
/** The heat a chiller sends to the towers, by its type. */
const REJECT_OF: Record<string, RejectSource> = { absorption: "abs", chillers: "chillers" };

/** The electricity a unit draws, day by day (null when the server didn't send it). */
export function powerOf(design: Design, type: string): number[] | null {
  const key = POWER_OF[type];
  const v = key ? design.year.daily_mw?.power?.[key] : undefined;
  return v && v.length ? v : null;
}

/** The heat a chiller sends to the towers, day by day. */
export function rejectOf(design: Design, type: string): number[] | null {
  const key = REJECT_OF[type];
  const v = key ? design.year.daily_mw?.reject?.[key] : undefined;
  return v && v.length ? v : null;
}

/** What the plant does with gas, from its gas node (buy when it doesn't say). */
export const gasModeOf = (node: Partial<Pick<GraphNode, "gas">> | null | undefined): GasMode => (node?.gas === "sell" || node?.gas === "produced" ? node.gas : "buy");

export function seriesOf(design: Design, node: Pick<GraphNode, "type"> & Partial<Pick<GraphNode, "values" | "gas">>): NodeSeries | null {
  const d = design.year.daily_mw;
  const s = design.plant.sizes_mw;
  const peak = (v: number[]) => Math.max(0, ...v);
  const pick = (values: number[] | null | undefined, capacity: number, kind: SeriesKind, follows = false): NodeSeries | null =>
    values && values.length ? { values, capacity: capacity > 0 ? capacity : peak(values), kind, follows } : null;
  switch (node.type) {
    case "heat_exchanger":
      return pick(d?.heat?.geo, s.heat_exchanger, "heat");
    case "heatpump":
      return pick(d?.heat?.hp, s.heat_pump, "heat");
    case "boiler":
      return pick(d?.heat?.boiler, s.boiler, "heat");
    case "electric_boiler":
      return pick(d?.heat?.electric_boiler ?? zerosLike(d?.heat?.demand), s.electric_boiler ?? node.values?.power_mw ?? 0, "heat");
    case "absorption":
      return pick(d?.cool?.abs, s.absorption, "cold");
    case "chillers":
      return pick(d?.cool?.chill, s.chillers, "cold");
    case "demand_heat":
      return pick(d?.heat?.demand, design.year.peak_heat_mw, "heat");
    case "demand_cold":
      return pick(d?.cool?.demand, design.year.peak_cool_mw, "cold");
    case "gas":
      // Sold, the gas goes to the grid all year (no daily series): the card shows the year's.
      return gasModeOf(node) === "sell" ? null : pick(d?.heat?.boiler, s.boiler, "heat", true);
    // The grid: everything that draws electricity, together; the towers: everything they take.
    case "grid":
      return pick(sumSeries(d?.power), 0, "power");
    case "tower":
      return pick(sumSeries(d?.reject), 0, "reject");
    default:
      return null;
  }
}

/** A year of zeros as long as a series (an electric boiler that never ran is sent no series). */
function zerosLike(values: number[] | undefined): number[] | undefined {
  return values?.length ? new Array<number>(values.length).fill(0) : undefined;
}

/** The value of a 365-day series on a day (1..365), 0 past its end. */
export const onDay = (values: number[], day: number) => values[Math.min(values.length, Math.max(1, Math.round(day))) - 1] ?? 0;

/** Below this a unit counts as off for the day. */
export const OFF_MW = 0.005;

/**
 * The MW an edge carries on a day: a pipe into a demand carries what its source gives; gas what
 * the boiler burns; electricity what the unit at its end draws; a line to the towers what the
 * chiller at its start rejects. Brine, and anything without a daily series, keeps the yearly figure.
 */
export function edgeMw(design: Design, edge: GraphEdge, nodes: Map<string, GraphNode>, day: number): number | null {
  const target = nodes.get(edge.target);
  const source = nodes.get(edge.source);
  const today = (values: number[] | null) => (values ? onDay(values, day) : edge.mw);
  switch (edge.kind) {
    case "electricity":
      return today(target ? powerOf(design, target.type) : null);
    case "reject":
      return today(source ? rejectOf(design, source.type) : null);
    case "gas":
      return today(target ? (seriesOf(design, target)?.values ?? null) : null);
    case "network":
    case "cold":
      if (!target || !isDemand(target.type) || !source) return edge.mw;
      return today(seriesOf(design, source)?.values ?? null);
    default:
      return edge.mw;
  }
}

/**
 * Whether a unit does nothing on a day (1..365): a well whose doublet is not running (its stop, or
 * not needed), a treatment train with no brine, a unit giving no heat or cold. Grid, towers and
 * demands are never idle here (their own lines say how much they carry).
 */
export function nodeIdle(design: Design, node: GraphNode, day: number): boolean {
  if (isWell(node.type)) {
    const w = wellDay(design, node, day);
    return !!w && !w.on;
  }
  if (node.type === "treatment") {
    const t = trainYear(design, node.id);
    return !!t && onDay(t.flow, day) <= 0.05;
  }
  if (node.type === "demand_heat" || node.type === "demand_cold" || node.type === "gas") return false;
  const s = seriesOf(design, node);
  return !!s && onDay(s.values, day) < OFF_MW;
}

/**
 * Whether a line carries nothing on a day: brine to or from an idle unit (a stopped doublet's
 * wells, a heat pump that is off), electricity to an idle unit, or a heat or cold pipe below the
 * smallest flow drawn. Idle lines are drawn still and faded, never with moving dots.
 */
export function edgeIdle(design: Design, edge: GraphEdge, nodes: Map<string, GraphNode>, day: number): boolean {
  const source = nodes.get(edge.source);
  const target = nodes.get(edge.target);
  if (edge.kind === "network" || edge.kind === "cold" || edge.kind === "gas" || edge.kind === "electricity" || edge.kind === "reject") {
    const mw = edgeMw(design, edge, nodes, day);
    if (mw != null && mw < OFF_MW) return true;
  }
  if (edge.kind === "network" || edge.kind === "cold") return false;
  return (!!source && nodeIdle(design, source, day)) || (!!target && nodeIdle(design, target, day));
}

/** The largest MW any heat or cold pipe carries over the year: the full stroke width. */
export function maxPipeMw(design: Design, graph: Pick<Graph, "nodes" | "edges">): number {
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  let max = 0;
  for (const e of graph.edges) {
    if (e.kind !== "network" && e.kind !== "cold") continue;
    const source = nodes.get(e.source);
    const s = source ? seriesOf(design, source) : null;
    max = Math.max(max, e.mw ?? 0, ...(s ? s.values : []));
  }
  return max || 1;
}

/** Stroke width for a pipe carrying `mw` (2 px when idle, up to 11 px at the year's largest). */
export const pipeWidth = (mw: number, max: number) => 2 + 9 * Math.min(1, Math.max(0, mw) / max);

/** Share of the year's heat or cold a unit gives (0..1), or a demand's coverage. */
export function yearShare(design: Design, type: string): { share: number; of: string } | null {
  const y = design.year;
  const heat = y.heat_delivered_gwh || y.heat_demand_gwh;
  const cold = y.cool_delivered_gwh || y.cool_demand_gwh;
  switch (type) {
    case "heat_exchanger":
      return heat ? { share: y.heat_split_gwh.geo / heat, of: "of the heat" } : null;
    case "heatpump":
      return heat ? { share: y.heat_split_gwh.hp / heat, of: "of the heat" } : null;
    case "boiler":
      return heat ? { share: y.heat_split_gwh.boiler / heat, of: "of the heat" } : null;
    case "electric_boiler":
      return heat ? { share: (y.heat_split_gwh.electric_boiler ?? 0) / heat, of: "of the heat" } : null;
    case "absorption":
      return cold ? { share: y.cool_split_gwh.abs / cold, of: "of the cold" } : null;
    case "chillers":
      return cold ? { share: y.cool_split_gwh.chill / cold, of: "of the cold" } : null;
    case "demand_heat":
      return { share: y.heat_coverage, of: "covered" };
    case "demand_cold":
      return { share: y.cool_coverage, of: "covered" };
    default:
      return null;
  }
}

/** Day of the year (1..365) as "22 Jan". */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MLEN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
export const MONTH_STARTS = MLEN.map((_, i) => MLEN.slice(0, i).reduce((a, b) => a + b, 0) + 1);
export const MONTH_NAMES = MONTHS;
export function dateLabel(day: number): string {
  let r = Math.min(365, Math.max(1, Math.round(day))) - 1;
  let m = 0;
  while (r >= MLEN[m]) {
    r -= MLEN[m];
    m += 1;
  }
  return `${r + 1} ${MONTHS[m]}`;
}
export function seasonOf(day: number): string {
  let m = 0;
  while (m < 11 && day >= MONTH_STARTS[m + 1]) m += 1;
  return m === 11 || m < 2 ? "Winter" : m < 5 ? "Spring" : m < 8 ? "Summer" : "Autumn";
}

/** The day (1..365) a series peaks, or null when it is flat zero. */
export function peakDay(values: number[] | undefined): number | null {
  if (!values?.length) return null;
  let best = 0;
  for (let i = 1; i < values.length; i++) if (values[i] > values[best]) best = i;
  return values[best] > 0 ? best + 1 : null;
}

// ------------------------------------------------------------------ wells and trains over the year

/** A doublet's row of the plant (Plant.doublets), by its number. */
export function doubletRow(design: Design, d: number): PlantDoublet | null {
  const rows = design.plant?.doublets ?? [];
  return rows.find((r) => r.doublet === d) ?? rows[d - 1] ?? null;
}

/** How many injectors share a doublet's brine (1 or 2). */
export function injectorsOf(design: Design, d: number): number {
  const row = doubletRow(design, d);
  if (row && row.injectors >= 1) return row.injectors;
  return Math.max(1, design.graph.nodes.filter((x) => x.type === "injector_well" && doubletOf(x) === d).length);
}

/** A doublet's flow cap, m³/h: its row's, else its producer's, else the plant's. */
export function capOf(design: Design, d: number): number {
  const row = doubletRow(design, d);
  if (row && row.cap_m3h > 0) return row.cap_m3h;
  const prod = design.graph.nodes.find((x) => x.type === "producer_well" && doubletOf(x) === d);
  return prod?.values.flow_m3h || design.plant?.flow_m3h || 300;
}

/** Whether a day (1..365) falls in one of a doublet's planned stops (one block, or the user's ranges). */
export function stoppedOn(design: Design, d: number, day: number): boolean {
  const ranges = design.year?.stop_ranges ?? design.plant?.stop_ranges;
  const mine = ranges?.length ? (ranges[d - 1] ?? []) : [(design.year?.stop_days ?? design.plant?.stop_days ?? [])[d - 1]];
  return mine.some((stop) => !!stop && stop.length >= 2 && day - 1 >= stop[0] && day - 1 <= stop[1]);
}

/** A well over the year, day by day: its flow (an injector's share of its doublet's), its cap, on, its temperature. */
export interface WellYear {
  flow: number[];
  cap: number;
  on: boolean[];
  /** The producer's wellhead, the injector's reinjection, °C (null on days off). */
  temperature: (number | null)[];
}

export function wellYear(design: Design, node: Pick<GraphNode, "id" | "type" | "values">): WellYear | null {
  if (!isWell(node.type)) return null;
  const d = doubletOf(node);
  const y = design.year?.doublets?.[d - 1];
  if (!y || !Array.isArray(y.flow_m3h) || !y.flow_m3h.length) return null;
  const share = node.type === "injector_well" ? 1 / injectorsOf(design, d) : 1;
  const temps = node.type === "producer_well" ? y.wellhead_c : y.reinjection_c;
  return {
    flow: y.flow_m3h.map((v) => (Number.isFinite(v) ? v * share : 0)),
    cap: capOf(design, d) * share,
    on: y.on ?? y.flow_m3h.map((v) => v > 0),
    temperature: (temps ?? []).map((v) => (typeof v === "number" && Number.isFinite(v) ? v : null)),
  };
}

/** What a well does on a day (1..365). */
export interface WellDay {
  flow: number;
  cap: number;
  /** cap > 0: the share of its cap. */
  load: number;
  on: boolean;
  /** In its doublet's 35-day stop. */
  stopped: boolean;
  temperature: number | null;
}

export function wellDay(design: Design, node: Pick<GraphNode, "id" | "type" | "values">, day: number): WellDay | null {
  const w = wellYear(design, node);
  if (!w) return null;
  const i = Math.min(w.flow.length, Math.max(1, Math.round(day))) - 1;
  const flow = w.flow[i] ?? 0;
  const on = (w.on[i] ?? flow > 0) && flow > 0.05;
  return { flow, cap: w.cap, load: w.cap > 0 ? flow / w.cap : 0, on, stopped: stoppedOn(design, doubletOf(node), i + 1), temperature: on ? (w.temperature[i] ?? null) : null };
}

/** The doublets whose producers feed a treatment train (from the graph's brine pipes). */
export function trainMembers(graph: Pick<Graph, "nodes" | "edges">, trainId: string): number[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const out = graph.edges
    .filter((e) => e.target === trainId && byId.get(e.source)?.type === "producer_well")
    .map((e) => doubletOf(byId.get(e.source)!));
  return [...new Set(out)].sort((a, b) => a - b);
}

/** The brine through a treatment train, day by day (its doublets' flows added up), and its most. */
export function trainYear(design: Design, trainId: string): { flow: number[]; cap: number } | null {
  const members = trainMembers(design.graph, trainId);
  const lists = members.map((d) => design.year?.doublets?.[d - 1]?.flow_m3h).filter((v): v is number[] => Array.isArray(v) && v.length > 0);
  if (!lists.length) return null;
  const n = Math.max(...lists.map((v) => v.length));
  const flow = new Array<number>(n).fill(0);
  for (const v of lists) for (let i = 0; i < v.length; i++) flow[i] += Number.isFinite(v[i]) ? v[i] : 0;
  return { flow, cap: members.reduce((a, d) => a + capOf(design, d), 0) };
}

/** "doublet 1", "doublets 1 and 2", "doublets 1, 2 and 3". */
export function doubletsText(ds: number[]): string {
  if (!ds.length) return "no doublet";
  if (ds.length === 1) return `doublet ${ds[0]}`;
  return `doublets ${ds.slice(0, -1).join(", ")} and ${ds[ds.length - 1]}`;
}

/**
 * The doublet that runs first when the hottest goes first (dispatch "base"): the one with the
 * hottest wellhead at full flow (the first of equals), as the plant model orders them.
 */
export function baseLoadDoublet(design: Design): number | null {
  if ((design.plant?.dispatch ?? design.dispatch) !== "base") return null;
  const rows = design.plant?.doublets ?? [];
  if (rows.length < 2) return null;
  let best = rows[0];
  for (const r of rows) if (r.wellhead_full_c > best.wellhead_full_c + 1e-9) best = r;
  return best.doublet;
}

/** Mean of the finite values of a list (null when none). */
export function meanOf(values: (number | null | undefined)[]): number | null {
  const v = values.filter((x): x is number => typeof x === "number" && Number.isFinite(x));
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

// ------------------------------------------------------------------ checks and provenance

const CHECK_WORDS: Record<string, RegExp> = {
  producer_well: /brine|wellhead|well\b/i,
  injector_well: /reinjection|brine cools/i,
  heat_exchanger: /heat exchanger|temperature cross|brine gives/i,
  heatpump: /heat pump|carnot/i,
  boiler: /(?<!electric )boiler/i,
  electric_boiler: /electric boiler/i,
  absorption: /absorption/i,
  chillers: /electric chiller|\bchillers\b/i,
  demand_heat: /heat adds up|more heat than demand|heat coverage|heating supply/i,
  demand_cold: /cold adds up|more cold than demand|cold coverage|cooling return/i,
  grid: /electricity|\bgrid\b/i,
  tower: /cooling tower|rejected|heat out/i,
  treatment: /separat|filter|produced gas/i,
};
const UNIT_CHECK = /size allows/i;
const UNITS = new Set(["heat_exchanger", "heatpump", "boiler", "electric_boiler", "absorption", "chillers"]);

/** The verifier's checks that are about a node, by the words in their names. */
export function relatedChecks(type: string, checks: DesignCheck[]): DesignCheck[] {
  const words = CHECK_WORDS[type];
  return checks.filter((c) => (words && words.test(c.name)) || (UNITS.has(type) && UNIT_CHECK.test(c.name)));
}

/** Who computed a node: GEMINI's solver, or Dioscuri's own model (the design's provenance). */
export function nodeProvenance(design: Design, node: GraphNode): Provenance {
  if (node.solver === "gemini") return "gemini";
  if (node.type === "absorption" || node.type === "chillers" || node.type === "tower" || node.type === "demand_cold") return provenanceOf(design, "cooling");
  return provenanceOf(design, "year");
}

// ------------------------------------------------------------------ values

const VALUE_LABELS: Record<string, string> = {
  depth_m: "Depth",
  wellhead_c: "Wellhead",
  flow_m3h: "Flow cap",
  esp_mw: "ESP",
  reinjection_c: "Reinjection",
  pump_mw: "Injector pump",
  power_mw: "Size",
  cold_gwh: "Cold a year",
  heat_gwh: "Heat a year",
  brine_out_c: "Brine out",
  cop: "COP",
  carnot_cop: "Carnot COP",
  peak_mw: "Peak",
  covered_pct: "Covered",
  temperature_out_c: "Out",
  temperature_in_c: "In",
  ua_kw_per_k: "UA",
  electricity_mw: "Electricity",
  source_out_c: "Source out",
  annual_gwh: "A year",
  supply_c: "Supply",
  return_c: "Return",
  efficiency: "Efficiency",
  drive_c: "Drive",
  doublets: "Doublets",
  esp_head_bar: "ESP head",
  wellhead_bar: "Injection pressure",
  network_out_c: "Network out",
  produced_gwh: "Produced gas",
  bought_gwh: "Bought gas",
  flared_gwh: "Flared gas",
  sold_gwh: "Sold to the gas grid",
  buyer_co2_t: "Buyer's CO₂",
  vented_co2_t: "CO₂ let out here",
  electric_boiler_gwh: "Electric boiler",
  units: "Units",
  electricity_gwh: "Electricity a year",
  chillers_gwh: "Chillers",
  pumps_gwh: "Well pumps",
  heat_pump_gwh: "Heat pump",
  towers_gwh: "Cooling towers",
  co2_t: "CO₂ a year",
  rejected_gwh: "Heat rejected a year",
  free_cooling_gwh: "Free cooling a year",
  permeability_md: "Permeability",
  thickness_m: "Thickness",
  pi_m3h_per_bar: "Productivity",
  known_depth_m: "Known aquifer depth",
  known_temperature_c: "Known aquifer temperature",
  doublet: "Doublet",
  open_m: "Open part",
  rock_c: "Rock at its depth",
  wellhead_min_c: "Wellhead, slowest day",
  flow_mean_m3h: "Mean flow",
  days_on: "Days on",
  esp_gwh: "ESP electricity",
  pump_gwh: "Injection pump",
  gas_gwh: "Separated gas",
  assumed: "Assumed",
};
export const valueLabel = (key: string) => VALUE_LABELS[key] ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

/** Flags among a node's values that are not figures to list (the inspector leaves them out). */
export const isFlagValue = (key: string) => key === "assumed";

/** A number with sensible digits: 2,500 · 86 · 9.25 · 0.195. */
export function fmtValue(v: number): string {
  if (!Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  if (a >= 1000) return Math.round(v).toLocaleString("en-US");
  const digits = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
  const r = Number(v.toFixed(digits));
  return String(r);
}

export function fmtWithUnit(v: number, unit: string | undefined): string {
  const u = (unit ?? "").trim();
  if (!u) return fmtValue(v);
  if (u === "%") return `${fmtValue(v)}%`;
  return `${fmtValue(v)} ${u}`;
}

/** The two or three values a node's card shows, in order. */
const CARD_KEYS: Record<string, string[]> = {
  producer_well: ["wellhead_c", "temperature_out_c", "flow_m3h", "depth_m"],
  injector_well: ["reinjection_c", "temperature_in_c", "pump_mw"],
  heat_exchanger: ["power_mw", "brine_out_c", "temperature_out_c"],
  heatpump: ["power_mw", "cop"],
  boiler: ["power_mw", "efficiency"],
  electric_boiler: ["power_mw", "units"],
  absorption: ["power_mw", "cop"],
  chillers: ["power_mw", "cop"],
  demand_heat: ["peak_mw", "covered_pct", "supply_c"],
  demand_cold: ["peak_mw", "covered_pct", "supply_c"],
  grid: ["electricity_gwh", "co2_t"],
  tower: ["rejected_gwh", "free_cooling_gwh", "electricity_gwh"],
};

export function cardValues(node: GraphNode, max = 3): { key: string; label: string; text: string }[] {
  const keys = CARD_KEYS[node.type] ?? Object.keys(node.values);
  const out: { key: string; label: string; text: string }[] = [];
  for (const k of keys) {
    const v = node.values[k];
    if (v == null || !Number.isFinite(v)) continue;
    // "Wellhead" and "Out" say the same on a producer: show one.
    if (k === "temperature_out_c" && out.some((o) => o.key === "wellhead_c")) continue;
    if (k === "temperature_in_c" && out.some((o) => o.key === "reinjection_c")) continue;
    out.push({ key: k, label: valueLabel(k), text: k === "cop" || k === "carnot_cop" ? `COP ${fmtValue(v)}` : fmtWithUnit(v, node.units[k]) });
    if (out.length >= max) break;
  }
  return out;
}

/** The electricity users the grid card lists, largest first: "well pumps 3.7 · chillers 2.8 GWh/yr". */
const GRID_USERS: [string, string][] = [
  ["pumps_gwh", "well pumps"],
  ["chillers_gwh", "chillers"],
  ["heat_pump_gwh", "heat pump"],
  ["electric_boiler_gwh", "e-boiler"],
  ["towers_gwh", "towers"],
];

/**
 * The line under a card's figure: what the values say, in a few words. The gas card says where
 * the gas comes from, the grid card who draws its electricity, the towers card what they take
 * and use; the rest list their values (a size, a peak, a coverage).
 */
export function cardSubline(node: GraphNode, values: { key: string; text: string }[]): string {
  const v = node.values;
  if (node.type === "gas") {
    const mode = gasModeOf(node);
    if (mode === "sell") return Number.isFinite(v.buyer_co2_t) ? `Buyer's CO₂ ${fmtValue(v.buyer_co2_t)} t, not ours` : "Cleaned, to the gas grid";
    return mode === "produced" ? "Brine gas only, none bought" : "Produced gas first, then bought";
  }
  if ((node.type === "boiler" || node.type === "chillers") && Number.isFinite(v.units) && v.units > 1) {
    // A reliable plan's bank: its equal units, and whether any one can be out (its own N-1 check).
    const each = Number.isFinite(v.unit_mw) ? ` × ${fmtValue(v.unit_mw)} MW` : " units";
    return `${fmtValue(v.units)}${each}${v.n1 ? " · one can be out" : ""}`;
  }
  if (node.type === "electric_boiler") {
    const size = Number.isFinite(v.power_mw) ? `${fmtValue(v.power_mw)} MW` : "";
    return Number.isFinite(v.units) && v.units > 1 ? `${size} in ${fmtValue(v.units)} units` : `${size} size`;
  }
  if (node.type === "grid") {
    const users = GRID_USERS.filter(([k]) => (v[k] ?? 0) > 0.0005).sort((a, b) => v[b[0]] - v[a[0]]);
    if (users.length) return `${users.map(([k, name]) => `${name} ${fmtValue(v[k])}`).join(" · ")} ${node.units[users[0][0]] || "GWh/yr"}`;
  }
  if (node.type === "tower" && Number.isFinite(v.rejected_gwh)) {
    const used = Number.isFinite(v.electricity_gwh) ? ` · ${fmtWithUnit(v.electricity_gwh, node.units.electricity_gwh)} of electricity` : "";
    // Free cooling: the towers cool the network directly on cool days.
    const free = (v.free_cooling_gwh ?? 0) > 0 ? ` · ${fmtWithUnit(v.free_cooling_gwh, node.units.free_cooling_gwh)} free cooling` : "";
    return `${fmtWithUnit(v.rejected_gwh, node.units.rejected_gwh)} rejected${free}${used}`;
  }
  return values
    .map((x) => (x.key === "power_mw" ? `${x.text} size` : x.key === "peak_mw" ? `peak ${x.text}` : x.key === "covered_pct" ? `${x.text} covered` : x.text))
    .join(" · ");
}

/** "0.17", "1,240": a figure in a sentence. */
const said = (v: number | undefined) => (typeof v === "number" && Number.isFinite(v) ? fmtValue(v) : "–");

/**
 * What a part does, in a sentence, where the card has no room for it (its tooltip, and a note in
 * the inspector): where the gas goes and whose CO₂ it is when sold, and what the electric boiler
 * heats. Every figure is the design's own; null for the other parts.
 */
export function partNote(design: Design, node: Pick<GraphNode, "type" | "values"> & Partial<Pick<GraphNode, "gas">>): string | null {
  const v = node.values;
  if (node.type === "gas") {
    const mode = gasModeOf(node);
    if (mode === "sell") {
      const total = design.year.co2_t?.total ?? design.economics.co2_t_per_year;
      return (
        `The brine's gas is cleaned and sold to the gas grid: ${said(v.sold_gwh)} GWh of methane a year, none burnt here. ` +
        `Whoever buys it burns it: ${said(v.buyer_co2_t)} t of CO₂ a year, the buyer's, not in this plant's ${said(total)} t.`
      );
    }
    const flared = (v.flared_gwh ?? 0) > 0.0005 ? ` ${said(v.flared_gwh)} GWh a year the boiler can't use is flared.` : "";
    if (v.flare_all) return `All the brine's gas is flared (${said(v.flared_gwh)} GWh a year, the switch is on): the boiler buys all its gas, ${said(v.bought_gwh)} GWh a year. Routine flaring needs consent (Mijnbouwbesluit art. 38).`;
    if (mode === "produced") return `No gas is bought: the gas boiler burns only the brine's own gas, ${said(v.produced_gwh)} GWh a year.${flared}`;
    return `The boiler burns the brine's own gas first (${said(v.produced_gwh)} GWh a year), then buys gas (${said(v.bought_gwh)} GWh a year).${flared}`;
  }
  if ((node.type === "boiler" || node.type === "chillers") && Number.isFinite(v.units) && v.units > 1) {
    const what = node.type === "boiler" ? "gas boiler" : "electric chillers";
    const each = Number.isFinite(v.unit_mw) ? ` of ${said(v.unit_mw)} MW each` : "";
    return v.n1
      ? `The ${what} is built as ${said(v.units)} equal units${each}, sized so that any one unit of the plant can be out (a doublet, the heat pump, one of these units …) and every day is still met: the spare capacity is in the units.`
      : `The ${what} is built as ${said(v.units)} equal units${each}, but with this design's sizes one unit out leaves some days short: it is not a reliable plan.`;
  }
  if (node.type === "electric_boiler") {
    const share = yearShare(design, "electric_boiler");
    // It runs last, after every other heat source the plant has.
    const before = (
      [
        ["heat_exchanger", "the exchanger"],
        ["heatpump", "the heat pump"],
        ["boiler", "the gas boiler"],
      ] as const
    )
      .filter(([t]) => design.graph.nodes.some((n) => n.type === t))
      .map(([, w]) => w);
    const others = before.length > 1 ? `${before.slice(0, -1).join(", ")} and ${before[before.length - 1]}` : (before[0] ?? "the rest of the plant");
    const units = (v.units ?? 1) > 1 ? `, built as ${said(v.units)} equal units so one can be out` : "";
    return (
      `Heats what ${others} cannot, from grid electricity: ` +
      `${said(v.heat_gwh)} GWh of heat a year${share ? ` (${fmtValue(share.share * 100)}% of the heat)` : ""} for ${said(v.electricity_gwh)} GWh of electricity. ` +
      `${said(v.power_mw)} MW${units}.`
    );
  }
  return null;
}

// ------------------------------------------------------------------ edits

/** One doublet in the edit form, as typed. */
export interface DoubletForm {
  /** The aquifer's middle, m. */
  depth_m: string;
  producer_open: Opening;
  injector_open: Opening;
  injectors: 1 | 2;
  /** A treatment train of its own (else it shares one with the other doublets that share). */
  own_train: boolean;
  /** Its own flow cap, m³/h; empty: the challenge's 300. */
  max_flow_m3h: string;
  /** The least it runs at, m³/h; empty or absent: the challenge's 50. */
  min_flow_m3h?: string;
}

/** The design-level edits the backend accepts (contract ``DesignChanges``), as typed. */
export interface EditForm {
  name: string;
  reservoir_delta_c: string;
  heat_pump_mw: string;
  boiler_mw: string;
  absorption_mw: string;
  chiller_mw: string;
  return_c: string;
  cool_return_c: string;
  /** Each doublet, one by one (1 to 3). */
  doublets: DoubletForm[];
  /** How the doublets share the brine: equal shares, or the hottest first. */
  dispatch: Dispatch;
}

export type EditKey = "reservoir_delta_c" | "heat_pump_mw" | "boiler_mw" | "absorption_mw" | "chiller_mw" | "return_c" | "cool_return_c";
/** What a design is now, in the edit form's terms. */
export type EditBase = Record<EditKey, number | null> & { doublets: DoubletChange[]; dispatch: Dispatch };

/** The challenge's flow cap, m³/h: a doublet at it shows an empty cap field. */
export const FLOW_CAP = 300;
/** The challenge's minimum flow of a running doublet, m³/h: an empty "at least" field. */
export const FLOW_MIN = 50;
const OPENINGS: Opening[] = ["full", "upper", "lower"];
const opening = (v: unknown): Opening => (OPENINGS.includes(v as Opening) ? (v as Opening) : "full");

/** Each doublet's set-up: the design's own list, else its rows, else n identical doublets at its depth. */
export function baseDoublets(design: Design): DoubletChange[] {
  const p = design.plant;
  const specs: Partial<DoubletSpec>[] = design.doublets?.length ? design.doublets : p.doublets?.length ? p.doublets : [];
  if (specs.length)
    return specs.map((d) => ({
      depth_m: Number(d.depth_m) || p.depth_m || 2500,
      producer_open: opening(d.producer_open),
      injector_open: opening(d.injector_open),
      injectors: Number(d.injectors) >= 2 ? 2 : 1,
      max_flow_m3h: typeof d.max_flow_m3h === "number" && d.max_flow_m3h > 0 && d.max_flow_m3h < FLOW_CAP ? d.max_flow_m3h : null,
      min_flow_m3h: typeof d.min_flow_m3h === "number" && d.min_flow_m3h > FLOW_MIN ? d.min_flow_m3h : null,
      train: Number(d.train) || 0,
    }));
  const n = p.n_doublets ?? (p.depth_m ? 1 : 0);
  return Array.from({ length: n }, () => ({ depth_m: p.depth_m, producer_open: "full" as const, injector_open: "full" as const, injectors: 1 as const, max_flow_m3h: null, min_flow_m3h: null, train: 0 }));
}

/** Whether a doublet is the only one on its train. */
const ownTrain = (ds: Pick<DoubletChange, "train">[], i: number) => ds.filter((d) => d.train === ds[i].train).length === 1;

export function editBase(design: Design): EditBase {
  const p = design.plant;
  const dispatch = (p.dispatch ?? design.dispatch) === "base" ? "base" : "equal";
  return {
    reservoir_delta_c: design.reservoir_delta_c,
    heat_pump_mw: p.sizes_mw.heat_pump,
    boiler_mw: p.sizes_mw.boiler,
    absorption_mw: p.sizes_mw.absorption,
    chiller_mw: p.sizes_mw.chillers,
    return_c: p.heating_return_c ?? null,
    cool_return_c: p.cooling_return_c ?? null,
    doublets: baseDoublets(design),
    dispatch,
  };
}

/** A number as the form shows it, without float noise (3.9000000000000004 → "3.9"). */
const str = (v: number | null) => (v == null ? "" : String(Number(v.toPrecision(12))));

export const EDIT_KEYS: EditKey[] = ["reservoir_delta_c", "heat_pump_mw", "boiler_mw", "absorption_mw", "chiller_mw", "return_c", "cool_return_c"];

/** A doublet of the base in the form's terms. */
export function doubletForm(d: DoubletChange, all: DoubletChange[], i: number): DoubletForm {
  return {
    depth_m: str(d.depth_m),
    producer_open: d.producer_open,
    injector_open: d.injector_open,
    injectors: d.injectors,
    own_train: all.length > 1 && ownTrain(all, i),
    max_flow_m3h: d.max_flow_m3h == null ? "" : str(d.max_flow_m3h),
    min_flow_m3h: d.min_flow_m3h == null ? "" : str(d.min_flow_m3h),
  };
}

export function editForm(design: Design): EditForm {
  const b = editBase(design);
  const form = { name: `${design.id}, edited`, doublets: b.doublets.map((d, i) => doubletForm(d, b.doublets, i)), dispatch: b.dispatch } as EditForm;
  for (const k of EDIT_KEYS) form[k] = str(b[k]);
  return form;
}

/** A new doublet for the form: a copy of the last one (or the known aquifer, fully open). */
export function newDoublet(form: EditForm): DoubletForm {
  const last = form.doublets[form.doublets.length - 1];
  return last ? { ...last, own_train: false } : { depth_m: "2500", producer_open: "full", injector_open: "full", injectors: 1, own_train: false, max_flow_m3h: "", min_flow_m3h: "" };
}

/** The limits the backend enforces, as the form explains them. */
const LIMITS: Partial<Record<EditKey, [number, number, string]>> = {
  heat_pump_mw: [0, 60, "0 to 60 MW."],
  boiler_mw: [0, 60, "0 to 60 MW."],
  absorption_mw: [0, 20, "0 to 20 MW."],
  chiller_mw: [0, 20, "0 to 20 MW."],
  return_c: [30, 90, "Between 30 and 90 °C, below the 100 °C supply."],
  cool_return_c: [21, 35, "Between 21 and 35 °C, above the 20 °C supply."],
  reservoir_delta_c: [-30, 30, "Within ±30 °C."],
};

export type DoubletErrors = Partial<Record<"depth_m" | "max_flow_m3h" | "min_flow_m3h", string>>;
export type EditErrors = Partial<Record<EditKey, string>> & { doublets?: DoubletErrors[]; count?: string };

const toNumber = (raw: string) => Number(raw.trim().replace("−", "-").replace(/,/g, ""));

/**
 * The doublets as the backend takes them, from the form: trains numbered in doublet order (one
 * shared train for the doublets without their own), with a sentence per field that can't be sent.
 */
export function formDoublets(form: Pick<EditForm, "doublets">): { doublets: DoubletChange[]; errors: DoubletErrors[] } {
  const errors: DoubletErrors[] = form.doublets.map(() => ({}));
  let next = 0;
  let shared: number | null = null;
  const doublets = form.doublets.map((d, i) => {
    const depth = toNumber(d.depth_m);
    if (!d.depth_m.trim() || !Number.isFinite(depth)) errors[i].depth_m = "A depth in metres.";
    else if (depth < 500 || depth > 7000) errors[i].depth_m = "Between 500 and 7,000 m.";
    let cap: number | null = null;
    if (d.max_flow_m3h.trim()) {
      cap = toNumber(d.max_flow_m3h);
      if (!Number.isFinite(cap)) errors[i].max_flow_m3h = "Not a number.";
      else if (cap < 50 || cap > FLOW_CAP) errors[i].max_flow_m3h = "50 to 300 m³/h.";
      else if (cap === FLOW_CAP) cap = null;
    }
    let least: number | null = null;
    if ((d.min_flow_m3h ?? "").trim()) {
      least = toNumber(d.min_flow_m3h ?? "");
      const top = cap ?? FLOW_CAP;
      if (!Number.isFinite(least)) errors[i].min_flow_m3h = "Not a number.";
      else if (least < FLOW_MIN || least > top) errors[i].min_flow_m3h = `${FLOW_MIN} to ${top} m³/h (the cap).`;
      else if (least === FLOW_MIN) least = null;
    }
    let train: number;
    if (d.own_train || form.doublets.length === 1) train = next++;
    else {
      if (shared == null) shared = next++;
      train = shared;
    }
    return { depth_m: depth, producer_open: d.producer_open, injector_open: d.injector_open, injectors: d.injectors, max_flow_m3h: cap, min_flow_m3h: least, train };
  });
  return { doublets, errors };
}

/** Which doublets share a train, as groups of their positions (so numbering doesn't matter). */
function trainGroups(ds: Pick<DoubletChange, "train">[]): string {
  const groups = new Map<number, number[]>();
  ds.forEach((d, i) => groups.set(d.train, [...(groups.get(d.train) ?? []), i]));
  return [...groups.values()].map((g) => g.join("+")).sort().join("|");
}

/** Whether two doublet lists are the same plant (depths, open parts, injectors, caps, who shares a train). */
export function sameDoublets(a: DoubletChange[], b: DoubletChange[]): boolean {
  if (a.length !== b.length) return false;
  const same = a.every(
    (d, i) =>
      Math.abs(d.depth_m - b[i].depth_m) < 1e-9 &&
      d.producer_open === b[i].producer_open &&
      d.injector_open === b[i].injector_open &&
      d.injectors === b[i].injectors &&
      (d.max_flow_m3h ?? FLOW_CAP) === (b[i].max_flow_m3h ?? FLOW_CAP) &&
      (d.min_flow_m3h ?? FLOW_MIN) === (b[i].min_flow_m3h ?? FLOW_MIN),
  );
  return same && trainGroups(a) === trainGroups(b);
}

/**
 * The changes to send: only what differs from the base. An empty field means "as it is"; the
 * doublets go as a whole list when any of them changed, and the dispatch when it changed (with
 * two doublets or more). `errors` holds a sentence per field that can't be sent.
 */
export function diffChanges(base: EditBase, form: EditForm): { changes: DesignChanges; errors: EditErrors } {
  const changes: DesignChanges = {};
  const errors: EditErrors = {};
  for (const k of EDIT_KEYS) {
    const raw = form[k].trim().replace("−", "-");
    if (!raw) continue;
    const v = Number(raw);
    if (!Number.isFinite(v)) {
      errors[k] = "Not a number.";
      continue;
    }
    const lim = LIMITS[k];
    if (lim && (v < lim[0] || v > lim[1])) errors[k] = lim[2];
    const was = base[k];
    if (was == null || Math.abs(v - was) > 1e-9) changes[k] = v;
  }
  if (form.doublets.length < 1 || form.doublets.length > 3) errors.count = "1 to 3 doublets.";
  const { doublets, errors: rowErrors } = formDoublets(form);
  if (rowErrors.some((e) => Object.keys(e).length)) errors.doublets = rowErrors;
  if (!sameDoublets(doublets, base.doublets)) changes.doublets = doublets;
  if (doublets.length > 1 && form.dispatch !== base.dispatch) changes.dispatch = form.dispatch;
  return { changes, errors };
}

/** Whether the form has anything that can't be sent. */
export const hasErrors = (e: EditErrors) => Object.keys(e).some((k) => (k === "doublets" ? (e.doublets ?? []).some((r) => Object.keys(r).length) : true));

const EDIT_LABELS: Record<EditKey, [string, string]> = {
  reservoir_delta_c: ["Reservoir", "°C"],
  heat_pump_mw: ["Heat pump", "MW"],
  boiler_mw: ["Gas boiler", "MW"],
  absorption_mw: ["Absorption chiller", "MW"],
  chiller_mw: ["Electric chillers", "MW"],
  return_c: ["Heating return", "°C"],
  cool_return_c: ["Cooling return", "°C"],
};

const OPEN_WORDS: Record<Opening, string> = { full: "fully open", upper: "open over the upper half", lower: "open over the lower half" };
export const DISPATCH_WORDS: Record<Dispatch, string> = { equal: "equal shares", base: "the hottest first" };
const metres = (v: number) => `${fmtValue(v)} m`;

/** One line per doublet that changed: "Doublet 2: producer open over the lower half (was fully open)". */
export function describeDoublets(base: DoubletChange[], next: DoubletChange[]): string[] {
  const lines: string[] = [];
  const n = Math.max(base.length, next.length);
  for (let i = 0; i < n; i++) {
    const a = base[i];
    const b = next[i];
    const name = `Doublet ${i + 1}`;
    if (!b) {
      lines.push(`${name} removed`);
      continue;
    }
    const facts = (d: DoubletChange) => [`aquifer at ${metres(d.depth_m)}`, d.producer_open !== "full" ? `producer ${OPEN_WORDS[d.producer_open]}` : "", d.injectors === 2 ? "2 injectors" : "", d.injector_open !== "full" ? `injector${d.injectors === 2 ? "s" : ""} ${OPEN_WORDS[d.injector_open]}` : "", d.max_flow_m3h ? `at most ${fmtValue(d.max_flow_m3h)} m³/h` : "", d.min_flow_m3h ? `at least ${fmtValue(d.min_flow_m3h)} m³/h` : ""].filter(Boolean).join(", ");
    if (!a) {
      lines.push(`${name} added: ${facts(b)}`);
      continue;
    }
    const parts: string[] = [];
    if (Math.abs(a.depth_m - b.depth_m) > 1e-9) parts.push(`aquifer at ${metres(b.depth_m)} (was ${metres(a.depth_m)})`);
    if (a.producer_open !== b.producer_open) parts.push(`producer ${OPEN_WORDS[b.producer_open]} (was ${OPEN_WORDS[a.producer_open].replace("open over the ", "")})`);
    if (a.injectors !== b.injectors) parts.push(`${b.injectors} injector${b.injectors === 2 ? "s" : ""} (was ${a.injectors})`);
    if (a.injector_open !== b.injector_open) parts.push(`injector${b.injectors === 2 ? "s" : ""} ${OPEN_WORDS[b.injector_open]} (was ${OPEN_WORDS[a.injector_open].replace("open over the ", "")})`);
    if ((a.max_flow_m3h ?? FLOW_CAP) !== (b.max_flow_m3h ?? FLOW_CAP)) parts.push(`at most ${fmtValue(b.max_flow_m3h ?? FLOW_CAP)} m³/h (was ${fmtValue(a.max_flow_m3h ?? FLOW_CAP)})`);
    if ((a.min_flow_m3h ?? FLOW_MIN) !== (b.min_flow_m3h ?? FLOW_MIN)) parts.push(`at least ${fmtValue(b.min_flow_m3h ?? FLOW_MIN)} m³/h (was ${fmtValue(a.min_flow_m3h ?? FLOW_MIN)})`);
    if (parts.length) lines.push(`${name}: ${parts.join("; ")}`);
  }
  if (next.length > 1 && trainGroups(base.slice(0, next.length)) !== trainGroups(next)) {
    const groups = new Map<number, number[]>();
    next.forEach((d, i) => groups.set(d.train, [...(groups.get(d.train) ?? []), i + 1]));
    const trains = [...groups.values()];
    lines.push(trains.length === 1 ? "Treatment: one train for all the doublets" : `Treatment: ${trains.length} trains (${trains.map((g) => (g.length > 1 ? `doublets ${g.join(" and ")}` : `doublet ${g[0]}`)).join("; ")})`);
  }
  return lines;
}

/** One line per change for the summary: "Heat pump 3.9 → 0 MW", "Doublet 2: …", "Dispatch …". */
export function describeChanges(base: EditBase, changes: DesignChanges): string[] {
  const n = (v: number | null | undefined) => (v == null ? "default" : fmtValue(v));
  const lines: string[] = [];
  if (changes.doublets) lines.push(...describeDoublets(base.doublets, changes.doublets));
  if (changes.dispatch) lines.push(`Dispatch: ${DISPATCH_WORDS[changes.dispatch]} (was ${DISPATCH_WORDS[base.dispatch]})`);
  for (const k of EDIT_KEYS) {
    const v = changes[k];
    if (v == null) continue;
    const [label, unit] = EDIT_LABELS[k];
    const after = k === "reservoir_delta_c" ? signed(v) : n(v);
    const before = k === "reservoir_delta_c" ? signed(base[k] ?? 0) : n(base[k]);
    lines.push(`${label} ${before} → ${after}${unit ? ` ${unit}` : ""}`);
  }
  return lines;
}

const signed = (v: number) => (v > 0 ? `+${fmtValue(v)}` : v < 0 ? `−${fmtValue(-v)}` : "0");

/** The headline numbers of a design against its parent, for the diff after a run. */
export interface DiffRow {
  key: string;
  label: string;
  unit: string;
  before: number | null;
  after: number | null;
  /** +1 when a rise is good, −1 when a rise is bad. */
  good: 1 | -1;
  pct?: boolean;
}

export function diffRows(parent: Design, child: Design): DiffRow[] {
  return [
    { key: "lcoh", label: "Cost of heat", unit: "€/MWh", before: parent.economics.lcoh, after: child.economics.lcoh, good: -1 },
    { key: "heat", label: "Heat covered", unit: "%", before: parent.year.heat_coverage * 100, after: child.year.heat_coverage * 100, good: 1, pct: true },
    { key: "co2", label: "CO₂ saving", unit: "%", before: parent.economics.co2_saving_pct, after: child.economics.co2_saving_pct, good: 1, pct: true },
    { key: "capex", label: "Capital", unit: "M€", before: parent.economics.capex_meur, after: child.economics.capex_meur, good: -1 },
  ];
}
