// The plant on a canvas (React Flow): a card per part with its solver badge, today's load and its
// key values, and pipes coloured by what they carry (brine one brown-grey, its temperature in the
// label) and as wide as the MW they carry on the chosen day; electricity (dotted amber) and the
// heat the towers take (dashed cyan) are thin lines that fade when idle. Each doublet's wells sit
// in a frame, each well's card with its flow and temperature on the day, its depth and open part;
// the reservoir band under them draws the aquifer and each well's open part at its depth. A pipe
// that passes over another leaves a gap in the one below (a bridge). The day lives in a context,
// so stepping through the year redraws the cards and pipes without rebuilding the graph.
//
// SEMANTIC ZOOM. Zoomed out (below FAR_ZOOM, as the fit is on a laptop's page) each card shows
// only its name and one value, drawn larger so they read at 12 px or more on screen; the detail
// rows come back when zoomed in. The zoom is a CSS variable on the canvas (ZoomWatch), so zooming
// restyles the cards without rendering them again.

import { createContext, memo, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import {
  Background,
  BackgroundVariant,
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  applyNodeChanges,
  useReactFlow,
  useStore,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeChange,
  type FitViewOptions,
  type NodeProps,
  type PanelPosition,
  type ReactFlowInstance,
} from "@xyflow/react";

import { isMenuKey, menuProps, openMenuAt, type MenuTarget } from "../../menu";
import type { Design, GraphEdge, GraphNode } from "../../workbench";
import { FitControls, FitWhenReady } from "./fit";
import { alertWords, type NodeAlert } from "./issues";
import { SeverityIcon } from "./IssuesPanel";
import {
  BAND_TOP,
  EDGE_COLORS,
  GUTTER,
  HANDLE_AT,
  LAYER_GAP,
  LAYER_H,
  OFF_MW,
  RESERVOIR_FACTS_H,
  WELL_NARROW_W,
  baseLoadDoublet,
  brineColor,
  cardSubline,
  cardValues,
  depthY,
  doubletOf,
  doubletRow,
  doubletsText,
  edgeIdle,
  edgeMw,
  farName,
  fmtValue,
  gasModeOf,
  iconOf,
  injectorsOf,
  isAssumedReservoir,
  isDemand,
  isThin,
  isWell,
  maxPipeMw,
  metaOf,
  onDay,
  onRun,
  openingWords,
  partNote,
  pipePoints,
  pipeWidth,
  hopHalo,
  hoppedPath,
  sectionHeight,
  seriesOf,
  shortLabel,
  stoppedOn,
  trainMembers,
  trainYear,
  viaPoints,
  wellDay,
  wellOpening,
  wellShort,
  type BandWell,
  type Bridge,
  type CardHandle,
  type LaidGroup,
  type LaidNode,
  type PlantLayout,
  type Side,
  type Via,
} from "./plant";

/** The canvas: a light grey surface with a grid of small dots, like a design tool's. */
export const CANVAS_BG = "#f6f8f8";
export const CANVAS_DOT = "#d3d9da";
export const CANVAS_GAP = 22;
export function CanvasDots({ id }: { id: string }) {
  return <Background id={id} variant={BackgroundVariant.Dots} gap={CANVAS_GAP} size={1.1} color={CANVAS_DOT} bgColor={CANVAS_BG} />;
}

interface PlantCtx {
  design: Design;
  day: number;
  maxMw: number;
  nodes: Map<string, GraphNode>;
  motion: boolean;
  /** Each part's alert (issues.ts alertsByNode): a glow round its card and a mark on it. */
  alerts: Map<string, NodeAlert>;
  /** The parts of the issue last picked in the list: ringed. */
  spot: ReadonlySet<string>;
}
const Ctx = createContext<PlantCtx | null>(null);
const usePlant = () => useContext(Ctx)!;

const NO_ALERTS = new Map<string, NodeAlert>();
const NO_SPOT: ReadonlySet<string> = new Set();

/** A card's classes for its alert: the glow's colour, its pulse (with motion), the picked ring. */
function useAlert(id: string): { cls: string; badge: ReactNode } {
  const { alerts, spot, motion } = usePlant();
  const a = alerts.get(id);
  if (!a) return { cls: spot.has(id) ? " spot" : "", badge: null };
  const words = alertWords(a, id);
  const cls = ` alert is-${a.limitOnly ? "limit" : a.severity}${motion && a.severity === "critical" ? " pulse" : ""}${spot.has(id) ? " spot" : ""}`;
  const badge = (
    <span className={`dz-alert-badge is-${a.severity}`} role="img" aria-label={words} title={words}>
      <SeverityIcon severity={a.severity} limit={a.limitOnly} size={18} />
    </span>
  );
  return { cls, badge };
}

type PlantNodeData = { laid: LaidNode };
type PlantNodeT = Node<PlantNodeData, "part">;
type FrameData = { group: LaidGroup };
type FrameNodeT = Node<FrameData, "frame" | "frameLabel">;
type CanvasNodeT = PlantNodeT | FrameNodeT;
type PipeData = { edge: GraphEdge; label: boolean; clearance?: number; via?: Via; bridges?: Bridge[] };
type PipeEdgeT = Edge<PipeData, "pipe">;

// ------------------------------------------------------------------ load ring

export function LoadRing({ value, size = 30, stroke = 4, color, label }: { value: number; size?: number; stroke?: number; color: string; label?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.min(1, Math.max(0, value));
  return (
    <svg className="dz-ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef2f2" strokeWidth={stroke} />
      {v > 0.002 && (
        <circle
          className="dz-ring-arc"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(v * c).toFixed(2)} ${c.toFixed(2)}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      )}
    </svg>
  );
}

// ------------------------------------------------------------------ node

const SIDES: [Side, Position][] = [
  ["t", Position.Top],
  ["r", Position.Right],
  ["b", Position.Bottom],
  ["l", Position.Left],
];
const POSITION_OF: Record<Side, Position> = { t: Position.Top, r: Position.Right, b: Position.Bottom, l: Position.Left };
/** The handles off a side's middle (plant.ts HANDLE_AT): a quarter or three quarters along it. */
const OFFSET_HANDLES: CardHandle[] = ["tq", "rq", "t3", "b3", "r3", "l3"];
const offsetStyle = (h: CardHandle) => {
  const side = h[0] as Side;
  const at = `${HANDLE_AT[h] * 100}%`;
  return side === "t" || side === "b" ? { left: at } : { top: at };
};

/** Every handle a card offers: each side's middle, and the points along a side the router uses. */
function CardHandles({ lanes = [] }: { lanes?: number[] }) {
  return (
    <>
      {SIDES.map(([id, pos]) => (
        <Handle key={`s-${id}`} id={`s-${id}`} type="source" position={pos} isConnectable={false} className="dz-hidden-handle" />
      ))}
      {SIDES.map(([id, pos]) => (
        <Handle key={`t-${id}`} id={`t-${id}`} type="target" position={pos} isConnectable={false} className="dz-hidden-handle" />
      ))}
      {/* Off the middle of a side: a unit rising into a corridor clear of the drop from above ("tq"),
          and the thin lines, three quarters along, beside the pipe that uses the middle. */}
      {OFFSET_HANDLES.map((h) => (
        <Handle key={`s-${h}`} id={`s-${h}`} type="source" position={POSITION_OF[h[0] as Side]} isConnectable={false} className="dz-hidden-handle" style={offsetStyle(h)} />
      ))}
      {OFFSET_HANDLES.map((h) => (
        <Handle key={`t-${h}`} id={`t-${h}`} type="target" position={POSITION_OF[h[0] as Side]} isConnectable={false} className="dz-hidden-handle" style={offsetStyle(h)} />
      ))}
      {lanes.map((y, k) => (
        <Handle key={`lane-${k}`} id={`lane-${k}`} type="target" position={Position.Left} isConnectable={false} className="dz-hidden-handle" style={{ top: y }} />
      ))}
    </>
  );
}

/** What a part does on the day: its MW, its load (0..1), and whether it is off. */
export function partToday(design: Design, node: GraphNode, day: number) {
  const s = seriesOf(design, node);
  if (!s) return null;
  const mw = onDay(s.values, day);
  return { mw, load: s.capacity > 0 ? mw / s.capacity : 0, off: mw < OFF_MW, series: s };
}

/** What the band says when the wells go deeper than the aquifer the challenge describes. */
export function assumedNote(v: Record<string, number>): string {
  return `The known aquifer is at ${fmtValue(v.known_depth_m)} m and ${fmtValue(v.known_temperature_c)} °C; the requirements allow deeper wells with the same gradient, so this one is assumed: ${fmtValue(v.temperature_c)} °C and a hydrostatic ${fmtValue(v.pressure_bar)} bar.`;
}

const PRODUCER_RED = "#c24e1c";
const INJECTOR_BLUE = "#2363a6";

/** "2,450–2,550 m". */
const range = (a: number, b: number) => `${fmtValue(a)}–${fmtValue(b)} m`;

/** A well's open part in a word or two: on a narrow card, and in the band zoomed out ("P2 lower"). */
const OPEN_SHORT: Record<string, string> = { full: "full", upper: "upper half", lower: "lower half" };
const OPEN_WORD: Record<string, string> = { full: "full", upper: "upper", lower: "lower" };

/**
 * The reservoir as a band of rock under the wells. On the left, the aquifer (100 m, or one layer
 * per aquifer when doublets reach different ones) with its top and base, each well's shaft coming
 * down from its card and its open part as a bar at its depth, labelled; the reservoir's facts at
 * the right, or in a row under the aquifer when the wells take the width. When the wells go
 * deeper than the known aquifer, the band says the values are assumed, and from what.
 */
function ReservoirBand({ laid, selected }: { laid: LaidNode; selected: boolean }) {
  const v = laid.node.values;
  const assumed = isAssumedReservoir(laid.node);
  const wells: BandWell[] = laid.wells ?? [];
  const aquifers = laid.aquifers?.length ? laid.aquifers : [v.depth_m];
  const thickness = v.thickness_m || 100;
  const several = aquifers.length > 1;
  const sectionW = laid.band?.section ?? 0;
  const below = laid.band?.facts === "below";
  const sectionH = sectionHeight(aquifers.length);
  const layerTop = (i: number) => BAND_TOP + i * (LAYER_H + LAYER_GAP);
  const facts: [string, string][] = [
    ["Temperature", `${fmtValue(v.temperature_c)} °C`],
    [several ? "Deepest aquifer" : "Depth", `${fmtValue(v.depth_m)} m`],
    [assumed ? "Pressure (hydrostatic)" : "Pressure", `${fmtValue(v.pressure_bar)} bar`],
    ["Rock", `${fmtValue(v.permeability_md)} mD × ${fmtValue(v.thickness_m)} m`],
    ["Productivity", `${fmtValue(v.pi_m3h_per_bar)} m³/h per bar`],
  ];
  const infoStyle = !wells.length ? undefined : below ? { left: 16, right: 16, top: sectionH, height: RESERVOIR_FACTS_H } : { left: sectionW + 18, height: sectionH };
  return (
    <div className={`dz-reservoir${selected ? " sel" : ""}${assumed ? " assumed" : ""}${wells.length ? " has-wells" : ""}${below ? " facts-below" : ""}`} style={{ width: laid.width, height: laid.height }}>
      {wells.map((w) =>
        w.kind === "producer" ? (
          <Handle key={w.id} id={`s-res-${w.id}`} type="source" position={Position.Top} isConnectable={false} className="dz-hidden-handle" style={{ left: w.x }} />
        ) : (
          <Handle key={w.id} id={`t-res-${w.id}`} type="target" position={Position.Top} isConnectable={false} className="dz-hidden-handle" style={{ left: w.x }} />
        ),
      )}
      {wells.length > 0 && (
        <svg className="dz-section" width={sectionW} height={sectionH} aria-hidden="true">
          {aquifers.map((a, i) => {
            const y = layerTop(i);
            return (
              <g key={a}>
                <rect className="dz-aquifer" x={GUTTER - 8} y={y} width={sectionW - GUTTER + 8} height={LAYER_H} rx={3} />
                <line className="dz-aquifer-mid" x1={GUTTER - 8} x2={sectionW} y1={y + LAYER_H / 2} y2={y + LAYER_H / 2} />
                <text className="dz-depth" x={GUTTER - 13} y={y + 8} textAnchor="end">
                  {fmtValue(a - thickness / 2)} m
                </text>
                <text className="dz-depth" x={GUTTER - 13} y={y + LAYER_H} textAnchor="end">
                  {fmtValue(a + thickness / 2)} m
                </text>
                {several && (
                  <text className="dz-depth is-name" x={GUTTER - 13} y={y + LAYER_H / 2 + 4} textAnchor="end">
                    aquifer
                  </text>
                )}
              </g>
            );
          })}
          {several &&
            aquifers.slice(1).map((a, i) => (
              <text key={`gap-${a}`} className="dz-depth is-gap" x={GUTTER - 13} y={layerTop(i + 1) - LAYER_GAP / 2 + 4} textAnchor="end">
                ≈
              </text>
            ))}
          {wells.map((w) => {
            const y0 = depthY(w.top_m, aquifers, thickness);
            const y1 = depthY(w.base_m, aquifers, thickness);
            const color = w.kind === "producer" ? PRODUCER_RED : INJECTOR_BLUE;
            const mid = (y0 + y1) / 2;
            // The last well's label goes left of its shaft when it would run past the aquifer.
            const flip = w.x + 90 > sectionW;
            return (
              <g key={w.id}>
                <line className="dz-shaft" x1={w.x} x2={w.x} y1={0} y2={y0} stroke={color} />
                <rect x={w.x - 4.5} y={y0} width={9} height={Math.max(3, y1 - y0)} rx={2.5} fill={color} />
                <text className="dz-open-label dz-near-only" x={w.x + (flip ? -11 : 11)} y={mid - 2} textAnchor={flip ? "end" : "start"}>
                  <tspan fontWeight={650}>{w.short}</tspan> {w.opening === "full" ? "fully open" : `${w.opening} half open`}
                </text>
                <text className="dz-open-range dz-near-only" x={w.x + (flip ? -11 : 11)} y={mid + 11} textAnchor={flip ? "end" : "start"}>
                  {range(w.top_m, w.base_m)}
                </text>
                <text className="dz-open-far dz-far-only" x={w.x + (flip ? -10 : 10)} y={mid} textAnchor={flip ? "end" : "start"}>
                  <tspan fontWeight={700}>{w.short}</tspan> {OPEN_WORD[w.opening] ?? w.opening}
                </text>
              </g>
            );
          })}
        </svg>
      )}
      <div className="dz-reservoir-info" style={infoStyle}>
        <div className="dz-reservoir-head">
          <span className="dz-reservoir-name">{laid.node.label}</span>
          {assumed && <span className="dz-reservoir-flag">assumed</span>}
          <span className="dz-solver is-gemini" title="GEMINI's reservoir inflow (IPR) and well model use these values">
            GEMINI
          </span>
        </div>
        <dl className="dz-reservoir-facts">
          {facts.map(([k, text], i) => (
            <div key={k} className={i === 0 ? "is-key" : undefined}>
              <dt>{k}</dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
      </div>
      {assumed && <p className="dz-reservoir-note">{assumedNote(v)}</p>}
    </div>
  );
}

function SolverBadge({ gemini }: { gemini: boolean }) {
  return (
    <span className={`dz-solver ${gemini ? "is-gemini" : "is-dioscuri"}`} title={gemini ? "Computed by GEMINI's solver (with the team's fixes)" : "Dioscuri's plant model: the year, day by day, and the costs"}>
      {gemini ? "GEMINI" : "Dioscuri"}
    </span>
  );
}

function PartIcon({ type, node }: { type: string; node?: GraphNode }) {
  const meta = metaOf(type);
  return (
    <span className="dz-part-icon" aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 16 16">
        <path d={node ? iconOf(node) : meta.icon} fill="none" stroke={meta.color} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

/** A card's name: its label, and the short name shown zoomed out (one of the two is hidden by CSS). */
function PartName({ node, label, narrow = false }: { node: GraphNode; label: string; narrow?: boolean }) {
  const far = farName(node, narrow);
  return (
    <span className="dz-part-name" title={node.label}>
      {far === label ? (
        label
      ) : (
        <>
          <span className="dz-near-only">{label}</span>
          <span className="dz-far-only">{far}</span>
        </>
      )}
    </span>
  );
}

/**
 * A well: its flow on the day (its share when two injectors split a doublet's brine) against its
 * cap, the producer's wellhead (the injector's reinjection) temperature that day, where it is open
 * and its mean flow over the days it runs. A narrow card (many wells) goes by its short name
 * ("I1A", as in the band) and puts the temperature on the line under the flow.
 */
function WellCard({ laid, selected }: { laid: LaidNode; selected: boolean }) {
  const { design, day } = usePlant();
  const n = laid.node;
  const meta = metaOf(n.type);
  const producer = n.type === "producer_well";
  const narrow = laid.width < WELL_NARROW_W;
  const d = doubletOf(n);
  const row = doubletRow(design, d);
  const today = wellDay(design, n, day);
  const off = today ? !today.on : false;
  const opening = wellOpening(n, row, design.plant.reservoir?.thickness_m ?? 100);
  const injectors = producer ? 1 : injectorsOf(design, d);
  const v = n.values;
  const temp = today ? today.temperature : producer ? v.wellhead_c : v.reinjection_c;
  const hasTemp = temp != null && Number.isFinite(temp);
  const mean = v.flow_mean_m3h;
  const stopped = off && stoppedOn(design, d, day);
  const alert = useAlert(n.id);
  const second = producer
    ? [Number.isFinite(mean) ? `mean ${fmtValue(mean)} m³/h` : null, !narrow && Number.isFinite(v.days_on) ? `${fmtValue(v.days_on)} days` : null]
    : [Number.isFinite(mean) ? `mean ${fmtValue(mean)} m³/h` : null, !narrow && injectors > 1 ? `1 of ${injectors}` : null];
  const first = narrow
    ? [hasTemp ? `${fmtValue(temp)} °C` : null, OPEN_SHORT[opening] ?? opening]
    : [Number.isFinite(v.depth_m) ? `${fmtValue(v.depth_m)} m` : null, openingWords(opening)];
  return (
    <div
      className={`dz-part dz-well${narrow ? " narrow" : ""}${off ? " off" : ""}${selected ? " sel" : ""}${alert.cls}`}
      style={{ width: laid.width, height: laid.height, ["--part" as string]: meta.color, ["--part-tint" as string]: meta.tint }}
    >
      <CardHandles />
      {alert.badge}
      <div className="dz-part-head">
        <PartIcon type={n.type} />
        <PartName node={n} label={narrow ? wellShort(n) : shortLabel(n.label)} narrow={narrow} />
        <SolverBadge gemini={n.solver === "gemini"} />
      </div>
      <div className="dz-part-main">
        <span className="dz-part-num">
          <strong>{today ? fmtValue(today.flow) : Number.isFinite(mean) ? fmtValue(mean) : "–"}</strong>
          <span>{today ? `m³/h${off ? (stopped ? ", stopped" : ", off") : ""}` : "m³/h mean"}</span>
        </span>
        {!narrow && hasTemp && <span className="dz-well-temp">{fmtValue(temp)} °C</span>}
        {today && <LoadRing value={today.load} size={26} stroke={4} color={meta.color} />}
      </div>
      <div className="dz-part-sub dz-well-sub">{first.filter(Boolean).join(" · ")}</div>
      <div className="dz-part-sub dz-well-sub is-quiet">{second.filter(Boolean).join(" · ")}</div>
    </div>
  );
}

/** A treatment train: the brine through it on the day (its doublets' together) against their caps. */
function TrainCard({ laid, selected }: { laid: LaidNode; selected: boolean }) {
  const { design, day } = usePlant();
  const n = laid.node;
  const meta = metaOf(n.type);
  const members = trainMembers(design.graph, n.id);
  const year = trainYear(design, n.id);
  const flow = year ? onDay(year.flow, day) : null;
  const off = flow != null && flow < 0.05;
  const alert = useAlert(n.id);
  return (
    <div
      className={`dz-part${off ? " off" : ""}${selected ? " sel" : ""}${alert.cls}`}
      style={{ width: laid.width, height: laid.height, ["--part" as string]: meta.color, ["--part-tint" as string]: meta.tint }}
    >
      <CardHandles />
      {alert.badge}
      <div className="dz-part-head">
        <PartIcon type={n.type} />
        <PartName node={n} label={n.label} />
      </div>
      <div className="dz-part-main">
        {flow != null ? (
          <span className="dz-part-num">
            <strong>{fmtValue(flow)}</strong>
            <span>m³/h{off ? ", off" : ""}</span>
          </span>
        ) : (
          <span className="dz-part-num">
            <strong className="dz-part-word">Brine</strong>
          </span>
        )}
        <SolverBadge gemini={n.solver === "gemini"} />
        {year && <LoadRing value={year.cap > 0 ? (flow ?? 0) / year.cap : 0} color={meta.color} />}
      </div>
      <div className="dz-part-sub">
        {doubletsText(members).replace(/^d/, "D")} · separator, filters
      </div>
    </div>
  );
}

const PartNode = memo(function PartNode({ data, selected }: NodeProps<PlantNodeT>) {
  const { design, day } = usePlant();
  const { laid } = data;
  const n = laid.node;
  const alert = useAlert(n.id);
  if (n.type === "reservoir") return <ReservoirBand laid={laid} selected={!!selected} />;
  if (isWell(n.type)) return <WellCard laid={laid} selected={!!selected} />;
  if (n.type === "treatment") return <TrainCard laid={laid} selected={!!selected} />;
  const meta = metaOf(n.type);
  const today = partToday(design, n, day);
  const values = cardValues(n, today ? 2 : 3);
  const demand = isDemand(n.type);
  const badge = <SolverBadge gemini={n.solver === "gemini"} />;
  const sold = n.type === "gas" && gasModeOf(n) === "sell";
  let main: ReactNode = null;
  if (sold)
    // Sold, the gas leaves the plant: the year's methane, out to the gas grid (the card's name says so).
    main = (
      <>
        <span className="dz-part-num">
          <strong>{fmtValue(n.values.sold_gwh ?? 0)}</strong>
          <span>GWh/yr</span>
        </span>
        {badge}
      </>
    );
  else if (today && !today.series.follows)
    main = (
      <>
        <span className="dz-part-num">
          <strong>{fmtValue(today.mw)}</strong>
          <span>MW{today.off && !demand ? ", off" : ""}</span>
        </span>
        {badge}
        <LoadRing value={today.load} color={meta.color} />
      </>
    );
  else if (today?.series.follows)
    main = (
      <>
        <span className="dz-part-num">
          <strong className="dz-part-word">{n.type === "gas" && (n.values as Record<string, number>).flare_all ? "Flared" : today.off ? "Idle" : "Burning"}</strong>
        </span>
        {badge}
      </>
    );
  else if (values[0]) {
    const [num, ...unit] = values[0].text.split(" ");
    main = (
      <>
        <span className="dz-part-num">
          <strong>{num}</strong>
          <span>
            {unit.join(" ")} {values[0].label.toLowerCase()}
          </span>
        </span>
        {badge}
      </>
    );
  } else main = badge;
  const bank = bankOf(n, today?.mw);
  return (
    <div
      className={`dz-part${today?.off ? " off" : ""}${selected ? " sel" : ""}${demand ? " demand" : ""}${alert.cls}`}
      style={{ width: laid.width, height: laid.height, ["--part" as string]: meta.color, ["--part-tint" as string]: meta.tint }}
    >
      <CardHandles lanes={laid.lanes} />
      {alert.badge}
      <div className="dz-part-head">
        <PartIcon type={n.type} node={n} />
        <PartName node={n} label={n.label} />
      </div>
      <div className="dz-part-main">
        {main}
        {bank && (
          <span className="dz-bank" title={bank.title} aria-label={bank.title}>
            {Array.from({ length: bank.units }, (_, i) => (
              <i key={i} className={i < bank.running ? "on" : "standby"} />
            ))}
          </span>
        )}
      </div>
      <div className="dz-part-sub" title={partNote(design, n) ?? undefined}>
        {cardSubline(n, today ? values : values.slice(1))}
      </div>
    </div>
  );
});

/** A bank of equal units (a reliable plan's boilers or chillers): how many run, how many stand by.
 * On a day: the units that day's output needs; on the year view: those the peak needs. */
export function bankOf(node: GraphNode, mw?: number): { units: number; running: number; title: string } | null {
  const v = node.values as Record<string, number>;
  if (!["boiler", "chillers", "electric_boiler"].includes(node.type)) return null;
  const units = Number(v.units);
  const each = Number(v.unit_mw);
  if (!Number.isFinite(units) || units < 2 || !Number.isFinite(each) || each <= 0) return null;
  const peak = Number.isFinite(v.most_mw) ? Number(v.most_mw) : NaN;
  const need = mw ?? (Number.isFinite(peak) ? peak : (units - 1) * each);
  const running = Math.min(units, Math.max(0, Math.ceil(need / each - 1e-6)));
  const name = node.type === "chillers" ? "chiller" : node.type === "electric_boiler" ? "electric boiler" : "boiler";
  const spare = units - running;
  const when = mw == null ? "at the year's peak" : "this day";
  const title =
    `${units} ${name} units of ${fmtValue(each)} MW: ${running} run ${when}` +
    (spare > 0 ? `, ${spare} stand${spare === 1 ? "s" : ""} by` : "") +
    (v.n1 ? "; any one unit can be out and every day is still met" : "");
  return { units, running, title };
}

/** A doublet's frame round its wells, behind everything. */
const FrameNode = memo(function FrameNode({ data }: NodeProps<FrameNodeT>) {
  const { design, day } = usePlant();
  const g = data.group;
  return <div className={`dz-doublet${stoppedOn(design, g.doublet, day) ? " is-stopped" : ""}`} style={{ width: g.width, height: g.height }} />;
});

/**
 * A doublet's name on its frame (and whether it runs first, or is stopped that day): a node of its
 * own, over the pipes, so the brine dropping into the wells passes under it rather than through it.
 */
const FrameLabel = memo(function FrameLabel({ data }: NodeProps<FrameNodeT>) {
  const { design, day } = usePlant();
  const g = data.group;
  const first = baseLoadDoublet(design) === g.doublet;
  const stopped = stoppedOn(design, g.doublet, day);
  return (
    <div className="dz-doublet-head" style={{ width: g.width }}>
      <span className="dz-doublet-label">
        {g.label}
        {first && (
          <span className="dz-doublet-tag" title="The hottest doublet runs first, up to its cap; the others take the rest">
            runs first
          </span>
        )}
        {stopped && (
          <span className="dz-doublet-tag is-off" title="In its planned stop: each doublet stops at least 365 − its operating days a year">
            stopped
          </span>
        )}
      </span>
    </div>
  );
});

// ------------------------------------------------------------------ pipe

const sideOf = (p: Position): Side => (p === Position.Top ? "t" : p === Position.Right ? "r" : p === Position.Bottom ? "b" : "l");

/**
 * The dash of a thin line: electricity dotted (round caps on a zero dash), the towers' heat
 * dashed. Both periods divide the 36 px of the marching loop (DesignTab.css dz-march).
 */
const DASH: Partial<Record<GraphEdge["kind"], string>> = { electricity: "0 6", reject: "8 4" };
/** The white halo either side of a hop (px): it cuts the pipe below where the hop passes over. */
const BRIDGE_GAP = 3;
/** How far an electricity tap reaches out from its unit (px). */
const TAP = 13;

/**
 * Electricity is a utility, not a process flow (as on a P&ID): each unit that draws it gets a
 * short tap from its handle ending in the grid's mark, and the Grid card holds the totals. No
 * dotted line runs across the plant to cross the pipes.
 */
function ElectricTap({ x, y, side, off, title }: { x: number; y: number; side: Side; off: boolean; title: string }) {
  const [dx, dy] = side === "t" ? [0, -1] : side === "b" ? [0, 1] : side === "l" ? [-1, 0] : [1, 0];
  const ex = x + dx * TAP;
  const ey = y + dy * TAP;
  return (
    <g className={`dz-tap${off ? " off" : ""}`}>
      <title>{title}</title>
      <path d={`M${x},${y} L${ex},${ey}`} className="dz-tap-lead" style={{ stroke: EDGE_COLORS.electricity }} />
      <circle cx={ex + dx * 7} cy={ey + dy * 7} r={7} className="dz-tap-mark" style={{ stroke: EDGE_COLORS.electricity }} />
      <path
        d={`M${ex + dx * 7 + 1},${ey + dy * 7 - 4} l-3 4.4h2.6l-1 3.6 3-4.4h-2.6z`}
        style={{ fill: EDGE_COLORS.electricity }}
      />
    </g>
  );
}

const PipeEdge = memo(function PipeEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<PipeEdgeT>) {
  const { design, day, maxMw, nodes, motion } = usePlant();
  const e = data!.edge;
  const sSide = sideOf(sourcePosition);
  const tSide = sideOf(targetPosition);
  const route = data!.via ? viaPoints(sourceX, sourceY, sSide, targetX, targetY, tSide, data!.via) : pipePoints(sourceX, sourceY, sSide, targetX, targetY, tSide, data!.clearance);
  // A hop still on this pipe's run (a card moved by hand may have taken the crossing away).
  const bridges = (data!.bridges ?? []).filter((b) => onRun(route.pts, b));
  const path = hoppedPath(route.pts, 12, bridges);
  const { labelX, labelY } = route;
  const mw = edgeMw(design, e, nodes, day);
  const brine = e.kind === "brine";
  const carries = e.kind === "network" || e.kind === "cold";
  const thin = isThin(e.kind);
  // Nothing through it today (a stopped doublet, a unit that is off): still and faded.
  const off = ((carries || thin || e.kind === "gas") && mw != null && mw < OFF_MW) || edgeIdle(design, e, nodes, day);
  const color = brine ? brineColor(e.temperature_c) : EDGE_COLORS[e.kind];
  const width = brine ? 7 : carries ? pipeWidth(mw ?? 0, maxMw) : e.kind === "gas" ? 3 : e.kind === "reject" ? 2 : 2.6;
  if (e.kind === "electricity") {
    const words = mw != null ? `${fmtValue(mw)} MW on this day` : "";
    return <ElectricTap x={targetX} y={targetY} side={tSide} off={off} title={`Electricity from the grid${words ? `: ${words}` : ""}${e.label ? ` (${e.label})` : ""}`} />;
  }
  const label = !data!.label
    ? null
    : brine
    ? e.temperature_c != null
      ? `${fmtValue(e.temperature_c)} °C`
      : null
    : carries && mw != null && !off
      ? `${fmtValue(mw)} MW`
      : null;
  return (
    <>
      {bridges.length > 0 && <path className="dz-bridge" d={hopHalo(bridges)} style={{ strokeWidth: width + 2 * BRIDGE_GAP }} />}
      <BaseEdge
        id={id}
        path={path}
        className={`dz-pipe kind-${e.kind}${off ? " off" : ""}${thin && !off && motion ? " marching" : ""}`}
        style={{ stroke: color, strokeWidth: width, strokeDasharray: DASH[e.kind] ?? (off ? "4 5" : undefined) }}
        interactionWidth={14}
      />
      {motion && (brine || carries) && !off && <path d={path} className="dz-pipe-flow" style={{ strokeWidth: brine ? 2.5 : Math.max(1.6, width * 0.32) }} />}
      {label && (
        <EdgeLabelRenderer>
          <div className={`dz-pipe-label${brine ? " brine" : ""}`} style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}>
            {!brine && <span className="dz-key-dot" style={{ background: color }} />}
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

const nodeTypes = { part: PartNode, frame: FrameNode, frameLabel: FrameLabel };
const edgeTypes = { pipe: PipeEdge };

/** Below this zoom the cards show only their name and one value (the semantic zoom, DesignTab.css). */
export const FAR_ZOOM = 0.7;

/**
 * Puts the canvas's zoom on its element: `--dz-z` (the CSS sizes the zoomed-out text by it, so it
 * reads the same on screen) and `data-zoom` ("far" below FAR_ZOOM, else "near").
 */
function ZoomWatch() {
  const zoom = useStore((s) => s.transform[2]);
  const dom = useStore((s) => s.domNode);
  useLayoutEffect(() => {
    if (!dom) return;
    dom.style.setProperty("--dz-z", String(Math.max(0.05, zoom)));
    dom.dataset.zoom = zoom < FAR_ZOOM ? "far" : "near";
  }, [dom, zoom]);
  return null;
}

// ------------------------------------------------------------------ canvas

function edgeAria(e: GraphEdge, labels: Map<string, string>): string {
  const what = { brine: "Brine", network: "Heat", cold: "Cold", gas: "Gas", electricity: "Electricity", reject: "Heat rejected" }[e.kind] ?? e.kind;
  const t = e.temperature_c != null ? ` at ${fmtValue(e.temperature_c)} °C` : "";
  const year = isThin(e.kind) && e.label ? `, ${e.label}` : "";
  return `${what} from ${labels.get(e.source) ?? e.source} to ${labels.get(e.target) ?? e.target}${t}${year}`;
}

interface CanvasProps {
  design: Design;
  layout: PlantLayout;
  /** The fit never zooms out further than this (phones pan instead). */
  minZoom: number;
  /** Room to leave around the plant when fitting it (fractions, or px per side in full screen). */
  fitPadding: FitViewOptions["padding"];
  /** Changes when the canvas or the panels over it change: the plant is fitted again. */
  fitKey: string;
  /** Where the zoom buttons go (and, placed by hand, where exactly and which way they run). */
  controls: PanelPosition;
  controlsStyle?: CSSProperties;
  controlsOrientation?: "horizontal" | "vertical";
  day: number;
  selected: string | null;
  onSelect: (id: string) => void;
  positions: Record<string, { x: number; y: number }>;
  onMoved: (id: string, at: { x: number; y: number }) => void;
  motion: boolean;
  /** A unit's or well's context menu (right-click, Shift+F10 on the focused card). */
  nodeMenu?: (id: string) => MenuTarget | null;
  /** The canvas's own menu, given its "fit the view". */
  canvasMenu?: (fit: () => void) => MenuTarget | null;
  /** Each part's alert (issues.ts): a glow round its card and a mark on it. */
  alerts?: Map<string, NodeAlert>;
  /** The parts of the issue picked in the list: ringed. */
  spot?: ReadonlySet<string>;
  /** Centre the view on these parts (an issue picked), each time `at` changes. */
  focus?: { ids: string[]; at: number } | null;
}

/** Centres the view on some parts (an issue picked in the list), in the fit's clear area. */
function FocusOn({ focus, padding, motion }: { focus?: { ids: string[]; at: number } | null; padding: FitViewOptions["padding"]; motion: boolean }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (!focus?.ids.length) return;
    // After the fit a layout change asks for in the same frame (FitWhenReady waits a frame too).
    let inner = 0;
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => void fitView({ nodes: focus.ids.map((id) => ({ id })), padding, maxZoom: 1.1, duration: motion ? 450 : 0 }));
    });
    return () => {
      cancelAnimationFrame(outer);
      cancelAnimationFrame(inner);
    };
    // The padding is read when the focus changes; a new object each render must not move it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.at, fitView]);
  return null;
}

export function PlantCanvas({ design, layout, minZoom, fitPadding, fitKey, controls, controlsStyle, controlsOrientation, day, selected, onSelect, positions, onMoved, motion, nodeMenu, canvasMenu, alerts = NO_ALERTS, spot = NO_SPOT, focus }: CanvasProps) {
  const graphNodes = useMemo(() => new Map(design.graph.nodes.map((n) => [n.id, n])), [design.graph]);
  const maxMw = useMemo(() => maxPipeMw(design, design.graph), [design]);
  const labels = useMemo(() => new Map(design.graph.nodes.map((n) => [n.id, n.label])), [design.graph]);

  const [nodes, setNodes] = useState<CanvasNodeT[]>(() => [
    // The doublets' frames, behind their wells: not picked, not moved.
    ...layout.groups.map(
      (g): FrameNodeT => ({
        id: `frame-${g.id}`,
        type: "frame",
        position: { x: g.x, y: g.y },
        data: { group: g },
        selectable: false,
        draggable: false,
        focusable: false,
        zIndex: -1,
        ariaLabel: `${g.label}: ${g.wells.map((w) => labels.get(w) ?? w).join(", ")}`,
      }),
    ),
    // Their names, over the pipes (the frame says it to a screen reader already).
    ...layout.groups.map(
      (g): FrameNodeT => ({
        id: `label-${g.id}`,
        type: "frameLabel",
        position: { x: g.x, y: g.y },
        data: { group: g },
        selectable: false,
        draggable: false,
        focusable: false,
        zIndex: 3,
        domAttributes: { "aria-hidden": true },
      }),
    ),
    ...layout.nodes.map((l): PlantNodeT => {
      // A well stays inside its doublet's frame when dragged (its open part is drawn under it).
      const g = layout.groups.find((x) => x.wells.includes(l.id));
      const extent: [[number, number], [number, number]] | undefined = g
        ? [
            [g.x, g.y],
            [g.x + g.width, g.y + g.height],
          ]
        : undefined;
      return {
        id: l.id,
        type: "part",
        position: positions[l.id] ?? { x: l.x, y: l.y },
        ...(extent ? { extent } : {}),
        data: { laid: l },
        selected: l.id === selected,
        ariaLabel: `${l.node.label}${l.node.solver === "gemini" ? ", computed by GEMINI" : ""}. Press Enter to inspect.`,
      };
    }),
  ]);
  // Brine says each temperature once at each end: the pipes leaving one part at one temperature
  // carry one label, and so do the pipes into one part (the producers' brine into a shared train,
  // every injector's down into the reservoir).
  const labelled = useMemo(() => {
    const seen = new Set<string>();
    const out = new Set<string>();
    for (const l of layout.edges) {
      const keys = l.edge.kind === "brine" ? [`from:${l.edge.source}@${l.edge.temperature_c}`, `into:${l.edge.target}@${l.edge.temperature_c}`] : [l.id];
      const said = keys.some((k) => seen.has(k));
      for (const k of keys) seen.add(k);
      if (!said) out.add(l.id);
    }
    return out;
  }, [layout]);
  const edges = useMemo<PipeEdgeT[]>(
    () =>
      layout.edges.map((l) => ({
        id: l.id,
        type: "pipe",
        source: l.edge.source,
        target: l.edge.target,
        sourceHandle: `s-${l.sourceHandle}`,
        targetHandle: l.targetHandle.startsWith("lane") ? l.targetHandle : `t-${l.targetHandle}`,
        data: { edge: l.edge, label: labelled.has(l.id), clearance: l.clearance, via: l.via, bridges: l.bridges },
        selectable: false,
        focusable: false,
        ariaLabel: edgeAria(l.edge, labels),
        // Drawn in layers (plant.ts LaidEdge.layer): the brine over the rest; in a layer, in order.
        zIndex: l.layer >= 2 ? 1 : 0,
      })),
    [layout, labels, labelled],
  );

  const onNodesChange = useCallback(
    (changes: NodeChange<CanvasNodeT>[]) => {
      const picked = changes.find((c) => c.type === "select" && c.selected);
      // Clicking the empty canvas would clear the pick; the inspector keeps showing it, so keep it.
      const kept = picked ? changes : changes.filter((c) => c.type !== "select");
      if (picked && picked.type === "select") onSelect(picked.id);
      setNodes((ns) => applyNodeChanges(kept, ns));
      for (const c of changes) if (c.type === "position" && c.position && c.dragging === false) onMoved(c.id, c.position);
    },
    [onSelect, onMoved],
  );

  // Keep the canvas's selection in step with a pick made elsewhere (the inspector's list).
  const synced = useMemo(() => nodes.map((n) => (n.type !== "part" || n.selected === (n.id === selected) ? n : { ...n, selected: n.id === selected })), [nodes, selected]);

  const ctx = useMemo<PlantCtx>(() => ({ design, day, maxMw, nodes: graphNodes, motion, alerts, spot }), [design, day, maxMw, graphNodes, motion, alerts, spot]);

  // Context menus: a card's (the frames and the reservoir's band have none of their own), and the
  // canvas's with "fit the view" (the fit the zoom buttons do, with this view's padding).
  const flow = useRef<ReactFlowInstance<CanvasNodeT, PipeEdgeT> | null>(null);
  const fit = () => void flow.current?.fitView({ padding: fitPadding, minZoom, duration: 200 });
  const paneTarget = () => canvasMenu?.(fit) ?? null;
  const onNodeMenu = (e: ReactMouseEvent, n: CanvasNodeT) => {
    if (n.type !== "part" || !nodeMenu) return;
    menuProps(() => nodeMenu(n.id)).onContextMenu(e as ReactMouseEvent<HTMLElement>);
  };
  const onPaneMenu = (e: ReactMouseEvent | MouseEvent) => {
    const t = paneTarget();
    if (t && openMenuAt(t, { x: e.clientX, y: e.clientY }, null)) e.preventDefault();
  };

  return (
    <Ctx.Provider value={ctx}>
      <ReactFlow<CanvasNodeT, PipeEdgeT>
        nodes={synced}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onNodeDragStop={(_, n) => n.type === "part" && onMoved(n.id, n.position)}
        onInit={(inst) => (flow.current = inst)}
        onNodeContextMenu={onNodeMenu}
        onPaneContextMenu={onPaneMenu}
        onKeyDown={(e) => {
          if (!isMenuKey(e)) return;
          const card = (document.activeElement as Element | null)?.closest<HTMLElement>(".react-flow__node");
          const id = card?.getAttribute("data-id");
          const t = id && nodeMenu ? nodeMenu(id) : paneTarget();
          const at = card ?? e.currentTarget;
          if (t && openMenuAt(t, at.getBoundingClientRect(), at, true)) {
            e.preventDefault();
            e.stopPropagation();
          }
        }}
        nodesConnectable={false}
        edgesFocusable={false}
        minZoom={0.25}
        maxZoom={1.6}
        zoomOnScroll={false}
        panOnScroll={false}
        preventScrolling={false}
        deleteKeyCode={null}
        selectionKeyCode={null}
        multiSelectionKeyCode={null}
        ariaLabelConfig={{ "node.a11yDescription.default": "Press Enter to inspect this part; arrow keys move it." }}
      >
        <CanvasDots id="plant-dots" />
        <FitControls position={controls} style={controlsStyle} orientation={controlsOrientation} padding={fitPadding} minZoom={minZoom} />
        <FitWhenReady padding={fitPadding} minZoom={minZoom} again={fitKey} />
        <FocusOn focus={focus} padding={fitPadding} motion={motion} />
        <ZoomWatch />
      </ReactFlow>
    </Ctx.Provider>
  );
}
