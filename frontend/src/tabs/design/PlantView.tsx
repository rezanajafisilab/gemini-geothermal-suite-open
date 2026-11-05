// The Plant view: the design's plant on a canvas, a year player that drives it (play, or pick a
// day on the strip), and a side panel that inspects the part picked or edits the design.
//
// One stage, two layouts (see DesignTab.css): on the page the canvas and the player fill the
// window's height on the left with the side panel beside them, as tall, scrolling on its own; in
// full screen the canvas fills the window and the bar and the player float over it, each one
// foldable, and the side panel docks at the right (on a window narrower than DOCK_MIN it floats
// over the canvas too). The legend sits at the foot of the side panel whenever that is beside the
// canvas (in full screen it folds away with it), so the player under the canvas is one row and
// the canvas gets the height. The canvas is fitted to what the panels leave free, as measured,
// again each time they change.
//
// The year's issues (a day short of heat, a failure asked about, a broken cap) glow on the parts
// they concern and are listed in a panel on the canvas: in a band at the right on the page (at
// the left in full screen, at the top when the side panel or a phone leaves too little width)
// that the fit keeps clear by its measured size, or in a card of its own under the drawing when
// the canvas is too narrow. A row picks its part, centres it and goes to its day.

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore, type CSSProperties } from "react";

import type { FitViewOptions } from "@xyflow/react";

import { MenuButton, costItemsFor, editFieldOf, seriesOfUnit, type MenuTarget } from "../../menu";
import { useWorkbench, type Design } from "../../workbench";
import { EditPanel } from "./EditPanel";
import { FoldButton, FullBar, FullButton, narrowWindow, useBox, useFill, useFullScreen, useMinWidth, useSize } from "./fullscreen";
import { Inspector } from "./Inspector";
import { IssuesPanel, type IssuesPlacement } from "./IssuesPanel";
import { alertsByNode, issueDay, issueTargets, issueUnit, issuesOf, type DesignIssue } from "./issues";
import { ParentDiff } from "./ParentDiff";
import { PlantCanvas } from "./PlantCanvas";
import { useRemembered } from "./remember";
import { YearStrip } from "./YearStrip";
import { EDGE_COLORS, brineColor, doubletOf, fmtValue, dateLabel, gasModeOf, layoutPlant, peakDay, seasonOf } from "./plant";

/** The size key (Plant.sizes_mw) of the units a "what if it were bigger" question can ask about. */
const SIZE_KEY: Record<string, string> = { heatpump: "heat_pump", boiler: "boiler", electric_boiler: "electric_boiler", absorption: "absorption", chillers: "chillers" };

// ------------------------------------------------------------------ reduced motion

const QUERY = "(prefers-reduced-motion: reduce)";
function subscribe(fn: () => void) {
  const m = typeof window !== "undefined" && window.matchMedia ? window.matchMedia(QUERY) : null;
  m?.addEventListener("change", fn);
  return () => m?.removeEventListener("change", fn);
}
const reducedNow = () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(QUERY).matches : false);
export const useReducedMotion = () => useSyncExternalStore(subscribe, reducedNow, () => false);

// ------------------------------------------------------------------ view

function firstPick(design: Design): string | null {
  const order = ["heat_exchanger", "heatpump", "boiler", "producer_well"];
  for (const t of order) {
    const n = design.graph.nodes.find((x) => x.type === t);
    if (n) return n.id;
  }
  return design.graph.nodes[0]?.id ?? null;
}

function PlayIcon({ playing }: { playing: boolean }) {
  return playing ? (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="3.5" y="2.8" width="3.2" height="10.4" rx="1" fill="currentColor" />
      <rect x="9.3" y="2.8" width="3.2" height="10.4" rx="1" fill="currentColor" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M4.5 2.8v10.4L13 8z" fill="currentColor" />
    </svg>
  );
}

/** From this window width the side panel docks at the right in full screen. */
const DOCK_MIN = 960;
/** From this window width the side panel is beside the canvas on the page (DesignTab.css, 1100 px). */
const BESIDE_MIN = 1101;

/** The issues panel's width (DesignTab.css .dz-issues), its distance from the canvas's edge, and
 * the gap the fit keeps between it and the plant. */
const ISSUES_W = 288;
const ISSUES_EDGE = 12;
const ISSUES_GAP = 16;
/** The least width the plant keeps beside the panel; with less the panel goes above it in full
 * screen, and under the drawing on the page when the canvas has the window's width (beside the
 * side panel the stage's height is fixed, so it stays at the right). */
const PLANT_MIN_W = 400;
/** On the page the panel starts under the full-screen button. */
const ISSUES_TOP = 56;

/** The gas line's name in the legend, by what the plant does with gas. */
const GAS_LEGEND = { buy: "Gas", produced: "The brine's gas (none bought)", sell: "The brine's gas, sold to the gas grid" } as const;

function Legend({ design }: { design: Design }) {
  const kinds = new Set(design.graph.edges.map((e) => e.kind));
  const gas = gasModeOf(design.graph.nodes.find((n) => n.type === "gas"));
  // The design's own brine range: from its reinjection to the reservoir.
  const temps = design.graph.edges.filter((e) => e.kind === "brine" && e.temperature_c != null).map((e) => e.temperature_c!);
  const lo = temps.length ? Math.min(...temps) : 45;
  const hi = temps.length ? Math.max(...temps) : 105;
  return (
    <div className="dz-legend" aria-label="Legend">
      {kinds.has("brine") && (
        <span className="dz-legend-item">
          <span className="dz-legend-brine" style={{ background: `linear-gradient(90deg, ${brineColor(lo)}, ${brineColor(hi)})` }} />
          Brine, {fmtValue(lo)} → {fmtValue(hi)} °C (on the pipe)
        </span>
      )}
      {kinds.has("network") && (
        <span className="dz-legend-item">
          <span className="dz-key-line wide" style={{ background: "#c24e1c" }} />
          Heating network
        </span>
      )}
      {kinds.has("cold") && (
        <span className="dz-legend-item">
          <span className="dz-key-line wide" style={{ background: "#2363a6" }} />
          Cooling network
        </span>
      )}
      {kinds.has("gas") && (
        <span className="dz-legend-item">
          <span className="dz-key-line wide" style={{ background: "#7856c4" }} />
          {GAS_LEGEND[gas]}
        </span>
      )}
      {kinds.has("electricity") && (
        <span className="dz-legend-item">
          <svg className="dz-key-tap" viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="8" cy="8" r="6.4" fill="#fff" stroke={EDGE_COLORS.electricity} strokeWidth="1.5" />
            <path d="M9 4l-3 4.4h2.6l-1 3.6 3-4.4H8z" fill={EDGE_COLORS.electricity} />
          </svg>
          Electricity from the grid (a tap at each unit)
        </span>
      )}
      {kinds.has("reject") && (
        <span className="dz-legend-item">
          <span className="dz-key-line wide dashed" style={{ color: EDGE_COLORS.reject }} />
          Heat to the towers
        </span>
      )}
      {design.graph.nodes.some((n) => n.type === "producer_well") && (
        <span className="dz-legend-item">
          <span className="dz-legend-open" aria-hidden="true">
            <i style={{ background: "#c24e1c" }} />
            <i style={{ background: "#2363a6" }} />
          </span>
          Open part of each well, in the aquifer
        </span>
      )}
      <span className="dz-legend-item dz-legend-note">Width: MW on the day</span>
      <span className="dz-legend-item">
        <span className="dz-solver is-gemini">GEMINI</span>
        <span className="dz-solver is-dioscuri">Dioscuri</span>
        who computed it
      </span>
    </div>
  );
}

export function PlantView({ design, scope, geminiDetail }: { design: Design; scope: string; geminiDetail?: string }) {
  const wb = useWorkbench();
  const { full, enter, exit } = useFullScreen();
  const reduced = useReducedMotion();
  const heatDemand = design.year.daily_mw?.heat?.demand ?? [];
  const coolDemand = design.year.daily_mw?.cool?.demand ?? [];
  const winter = peakDay(heatDemand);
  const summer = peakDay(coolDemand);
  const [day, setDayRaw] = useRemembered(scope, "day", () => winter ?? 22);
  const [picked, setPicked] = useRemembered<string | null>(scope, "node", () => firstPick(design));
  const [positions, setPositions] = useRemembered<Record<string, { x: number; y: number }>>(scope, "positions", {});
  const [side, setSide] = useRemembered<"inspect" | "edit">(scope, "side", "inspect");
  const [sideOpen, setSideOpen] = useRemembered("*", "full-side", () => !narrowWindow());
  const [playerOpen, setPlayerOpen] = useRemembered("*", "full-player", true);
  const [playing, setPlaying] = useState(false);
  const layout = useMemo(() => layoutPlant(design.graph, { doublets: design.plant.doublets }), [design.graph, design.plant.doublets]);
  const [stageRef, fill] = useFill<HTMLDivElement>(500);
  const [canvasRef, size] = useSize<HTMLDivElement>();
  const [barRef, bar] = useBox<HTMLDivElement>(full);
  const [playerRef, player] = useBox<HTMLElement>(full);
  const narrow = size.w > 0 && size.w < 600;
  const wide = useMinWidth(DOCK_MIN);
  const beside = useMinWidth(BESIDE_MIN);
  const dock = full && sideOpen && wide;
  const legendBeside = full || beside;

  // ---------------------------------------------------------------- issues
  const issues = useMemo(() => issuesOf(design), [design]);
  const drawn = useMemo(() => design.graph.nodes.map((n) => n.id), [design.graph]);
  const alerts = useMemo(() => alertsByNode(issues, drawn), [issues, drawn]);
  const [issuesOpen, setIssuesOpen] = useRemembered("*", "issues-open", () => !narrowWindow());
  const [activeIssue, setActiveIssue] = useRemembered<string | null>(scope, "issue", null);
  const [focus, setFocus] = useState<{ ids: string[]; at: number } | null>(null);
  // In full screen the side panel, when it floats, takes the canvas's right (352 px of the fit).
  const sideClear = full && !narrow ? (dock || !sideOpen ? 20 : 352) : 0;
  const roomBeside = (taken: number) => size.w - taken - (ISSUES_W + ISSUES_EDGE + ISSUES_GAP) >= PLANT_MIN_W;
  const placement: IssuesPlacement | null = !issues.length
    ? null
    : full
      ? !narrow && roomBeside(sideClear + 20)
        ? "left"
        : "top"
      : !beside && size.w > 0 && !roomBeside(0.04 * size.w)
        ? "below"
        : "right";
  const [issuesRef, issuesBox] = useBox<HTMLElement>(String(placement));
  const active = issues.find((i) => i.id === activeIssue) ?? null;
  const spot = useMemo(() => new Set(active ? issueTargets(active, drawn) : []), [active, drawn]);

  const node = design.graph.nodes.find((n) => n.id === picked) ?? design.graph.nodes.find((n) => n.id === firstPick(design)) ?? null;
  const setDay = useCallback(
    (d: number) => {
      setPlaying(false);
      setDayRaw(d);
    },
    [setDayRaw],
  );
  const onSelect = useCallback(
    (id: string) => {
      setPicked(id);
      setSide("inspect");
      if (full) setSideOpen(true);
    },
    [setPicked, setSide, setSideOpen, full],
  );
  const onMoved = useCallback((id: string, at: { x: number; y: number }) => setPositions((p) => ({ ...p, [id]: at })), [setPositions]);
  /** An issue picked in the list: its part in the inspector, the view on it, its worst day. */
  const pickIssue = useCallback(
    (issue: DesignIssue) => {
      setActiveIssue(issue.id);
      const unit = issueUnit(issue, drawn);
      if (unit) onSelect(unit);
      const d = issueDay(issue);
      if (d != null) setDay(d);
      const own = issue.units.filter((id) => drawn.includes(id));
      const ids = own.length ? own : issueTargets(issue, drawn);
      if (ids.length) setFocus({ ids, at: Date.now() });
    },
    [drawn, onSelect, setDay, setActiveIssue],
  );

  // ---------------------------------------------------------------- context menus
  // "Change its size": the edit panel, on that unit's field.
  const [editFocus, setEditFocus] = useState<{ field: string; at: number } | null>(null);
  const openEdit = useCallback(
    (field: string) => {
      setSide("edit");
      if (full) setSideOpen(true);
      setEditFocus({ field, at: Date.now() });
    },
    [setSide, setSideOpen, full],
  );
  /** A unit's or well's menu: inspect, change it, a what-if on it, its year and its cost lines. */
  const unitMenu = (id: string): MenuTarget | null => {
    const n = design.graph.nodes.find((x) => x.id === id);
    if (!n) return null;
    const doublet = doubletOf(n);
    const field = editFieldOf({ type: n.type, doublet });
    const series = seriesOfUnit(n.type);
    const days = series ? design.year.daily_mw?.[series.side] : null;
    const lines = [...(design.economics.lines?.heat ?? []), ...(design.economics.lines?.cold ?? [])].map((l) => l.item);
    const sizeKey = SIZE_KEY[n.type];
    return {
      kind: "unit",
      design: { id: design.id, name: design.uid || design.code, sub: design.code },
      node: { id: n.id, type: n.type, label: n.label, doublet },
      sizeMw: sizeKey ? (design.plant.sizes_mw as Record<string, number | undefined>)[sizeKey] : undefined,
      inspect: () => onSelect(n.id),
      edit: field ? { label: field.label, run: () => openEdit(field.field) } : undefined,
      energy: series && days ? series : undefined,
      costs: costItemsFor(n.type, lines),
    };
  };
  const canvasMenu = (fit: () => void): MenuTarget => ({ kind: "canvas", fit, fullScreen: { on: full, toggle: full ? exit : enter } });

  // Play: a day every 70 ms (the year in about 25 s), looping; a week a step with reduced motion.
  useEffect(() => {
    if (!playing) return;
    const step = reduced ? 7 : 1;
    const t = window.setInterval(() => setDayRaw((d) => ((d - 1 + step) % 365) + 1), reduced ? 400 : 70);
    return () => window.clearInterval(t);
  }, [playing, reduced, setDayRaw]);

  const strip = useMemo(
    () => [
      { label: "heat demand", values: heatDemand, color: "#c24e1c" },
      { label: "cooling demand", values: coolDemand, color: "#2363a6" },
    ],
    [heatDemand, coolDemand],
  );
  const hasCold = coolDemand.some((v) => v > 0);
  const jumps = [
    winter && { label: "Winter peak", day: winter },
    summer && { label: "Summer peak", day: summer },
  ].filter(Boolean) as { label: string; day: number }[];

  // In full screen the drawing is fitted to the part of the window the panels leave free: under
  // the bar (and the zoom buttons beside it), over the player, left of the side panel when it
  // floats; the docked one is beside the canvas already.
  const top = bar.h ? bar.h + 24 : 84;
  const bottom = player.h ? player.h + 24 : playerOpen ? 150 : 86;
  // The issues panel's band, kept clear by the fit: its measured width beside the plant, or its
  // height above it (a phone in full screen); none under the drawing.
  const clearW = (placement === "right" || placement === "left") && issuesBox.w ? issuesBox.w + ISSUES_EDGE + ISSUES_GAP : 0;
  const clearH = placement === "top" && issuesBox.h ? issuesBox.h + 12 : 0;
  const fitPadding: FitViewOptions["padding"] = full
    ? narrow
      ? { top: `${clearH ? top + clearH : 96}px`, right: "16px", bottom: playerOpen ? "200px" : "90px", left: "16px" }
      : ({ top: `${top + clearH}px`, right: `${sideClear}px`, bottom: `${bottom}px`, left: clearW ? `${clearW}px` : "20px" } as const)
    : clearW
      ? { top: 0.04, right: `${clearW}px`, bottom: 0.04, left: 0.04 }
      : 0.04;
  const fitKey = `${size.w}x${size.h}:${full}:${sideOpen}:${playerOpen}:${dock}${full ? `:${top}:${bottom}` : ""}:${placement}:${clearW}:${clearH}`;
  // Where the panel sits: under the full-screen button on the page; under the bar in full screen,
  // above the player (it scrolls when the list is longer than the room).
  const issuesStyle: CSSProperties | undefined =
    placement === "right"
      ? { top: ISSUES_TOP, right: ISSUES_EDGE, maxHeight: `calc(100% - ${ISSUES_TOP + ISSUES_EDGE}px)` }
      : placement === "left"
        ? { top, left: ISSUES_EDGE, maxHeight: `calc(100% - ${top + bottom}px)` }
        : placement === "top"
          ? { top, left: ISSUES_EDGE, right: narrow ? ISSUES_EDGE : sideClear, maxHeight: "34%" }
          : undefined;
  const issuesPanel = placement && (
    <IssuesPanel
      panelRef={issuesRef}
      issues={issues}
      open={issuesOpen}
      onToggle={() => setIssuesOpen((o) => !o)}
      active={active?.id ?? null}
      onPick={pickIssue}
      placement={placement}
      style={issuesStyle}
    />
  );
  // The zoom buttons: in full screen in a row beside the bar, out of the drawing's way.
  const controlsBeside = full && !narrow && bar.w > 0;

  const playButton = (
    <button type="button" className="dz-play ta-btn ta-ink" aria-label={playing ? "Pause the year" : "Play the year"} aria-pressed={playing} onClick={() => setPlaying((p) => !p)}>
      <PlayIcon playing={playing} />
    </button>
  );
  const date = (
    <div className="dz-date">
      <strong>{dateLabel(day)}</strong>
      <span>
        {seasonOf(day)} · day {day}
      </span>
    </div>
  );

  return (
    <div className="dz-plant">
      {!full && <ParentDiff design={design} threadId={wb.threadId} />}
      <div
        ref={stageRef}
        className={`dz-stage dz-plant-stage${full && !sideOpen ? " side-folded" : ""}${dock ? " docked" : ""}${placement === "below" ? " has-issues-below" : ""}`}
        style={{ "--dz-fill": `${fill}px` } as CSSProperties}
      >
        {full && (
          <div className="dz-float dz-fbar" ref={barRef}>
            <FullBar />
          </div>
        )}

        <section className="dz-card dz-canvas-card" aria-label={`The plant of ${design.code} on ${dateLabel(day)}`}>
          <div className="dz-canvas" ref={canvasRef}>
            <PlantCanvas
              key={design.id}
              design={design}
              layout={layout}
              minZoom={narrow ? 0.5 : 0.25}
              fitPadding={fitPadding}
              fitKey={fitKey}
              controls={full && !controlsBeside ? "center-left" : "top-left"}
              controlsOrientation={controlsBeside ? "horizontal" : "vertical"}
              controlsStyle={controlsBeside ? { margin: 0, top: 12 + Math.max(0, (bar.h - 28) / 2), left: 12 + bar.w + 12 } : undefined}
              day={day}
              selected={node?.id ?? null}
              onSelect={onSelect}
              positions={positions}
              onMoved={onMoved}
              motion={!reduced}
              nodeMenu={unitMenu}
              canvasMenu={canvasMenu}
              alerts={alerts}
              spot={spot}
              focus={focus}
            />
            {!full && <FullButton className="dz-canvas-full" />}
            {placement !== "below" && issuesPanel}
          </div>
        </section>
        {placement === "below" && issuesPanel}

        <section ref={playerRef} className={`dz-card dz-player-card${full ? " dz-float" : ""}${full && !playerOpen ? " folded" : ""}`} aria-label="The year">
          <div className="dz-player">
            {playButton}
            {date}
            {(!full || playerOpen) && (
              <>
                <div className="dz-player-strip">
                  <YearStrip series={hasCold ? strip : strip.slice(0, 1)} day={day} onDay={setDay} height={44} slider months label="Day of the year" marks={design.broken_days ?? []} />
                </div>
                {jumps.length > 0 && (
                  <div className="dz-jumps" role="group" aria-label="Jump to a day">
                    {jumps.map((j) => (
                      <button key={j.label} type="button" className="dz-chip ta-btn ta-chip" aria-pressed={day === j.day} onClick={() => setDay(j.day)}>
                        {j.label}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
            {full && <FoldButton open={playerOpen} onToggle={() => setPlayerOpen((o) => !o)} label="Year" toward="down" />}
          </div>
          {!legendBeside && <Legend design={design} />}
        </section>

        <aside className={`dz-card dz-side${full ? " dz-float" : ""}${full && !sideOpen ? " folded" : ""}`} aria-label="Inspector">
          <div className="dz-side-head">
            {(!full || sideOpen) && (
              <div className="seg mini dz-side-seg" role="tablist" aria-label="Side panel">
                <span className="seg-thumb ta-thumb" style={{ left: `calc(3px + ${side === "edit" ? 1 : 0} * (100% - 6px) / 2)`, width: "calc((100% - 6px) / 2)" }} />
                <button type="button" role="tab" aria-selected={side === "inspect"} style={{ fontWeight: side === "inspect" ? 650 : 450 }} onClick={() => setSide("inspect")}>
                  Inspect
                </button>
                <button type="button" role="tab" aria-selected={side === "edit"} style={{ fontWeight: side === "edit" ? 650 : 450 }} onClick={() => setSide("edit")}>
                  Edit and run
                </button>
              </div>
            )}
            {node && (!full || sideOpen) && <MenuButton small target={() => unitMenu(node.id)} label={`More for ${node.label}: change it, a what-if, its year, its costs`} className="dz-side-more" />}
            {full && <FoldButton open={sideOpen} onToggle={() => setSideOpen((o) => !o)} label={side === "edit" ? "Edit and run" : node ? node.label : "Inspector"} toward="right" />}
          </div>
          {(!full || sideOpen) && (
            <div className="dz-side-body">
              {side === "inspect" ? (
                node ? (
                  <Inspector design={design} node={node} day={day} onDay={setDay} geminiDetail={geminiDetail} />
                ) : (
                  <p className="dz-muted">This design has no parts to inspect.</p>
                )
              ) : (
                <EditPanel design={design} scope={scope} focus={editFocus} />
              )}
            </div>
          )}
          {legendBeside && (!full || sideOpen) && <Legend design={design} />}
        </aside>
      </div>
    </div>
  );
}
