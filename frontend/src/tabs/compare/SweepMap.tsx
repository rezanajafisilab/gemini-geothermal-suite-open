// The design space of one search (2 Nov; redesigned 3 Nov). Thousands of designs drawn by Latin
// hypercube, each run for a year as drawn. Two views:
//
// - Map: x the cost of heat and cold, y the CO₂ a year (lower left is cheaper and cleaner). Designs
//   that meet every cap are dots, the ones that break a cap faint rings; the dashed line joins the
//   feasible designs no other beats on both cost and CO₂; the search's own designs sit on top with
//   their handles. Drag a box to zoom in (double-click or Reset to zoom out); click a dot to see it,
//   open it in the tabs or tick it for the side by side. "Colour by" colours the dots by whether
//   they meet the caps, by their doublets, or by their depth.
// - List: every drawn design as a row (sortable, paged), feasible first, with Open and Tick.
//
// Above both: what the sweep varied, with each range. Under the map: what drives the cost, the
// cheapest feasible design across each parameter's range.
//
// Drawn on a canvas: 5,000 SVG circles made the tab slow to scroll.

import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";

import { niceTicks, useWidth } from "../../components/LineChart";
import { getSweep, go, useWorkbench, type SweepView } from "../../workbench";

const H = 360;
const M = { top: 14, right: 16, bottom: 44, left: 70 };
const TEAL = "#0b8fa0";
const INK = "#11181c";
const GREY = "#9aa6ab";
const DOUBLET_COLOURS = ["#0b8fa0", "#c27c0e", "#6f5bd3"];
const PAGE = 25;
type ColourBy = "caps" | "doublets" | "depth";
type Domain = { x0: number; x1: number; y0: number; y1: number };

interface Drawn {
  i: number;
  cx: number;
  cy: number;
  ok: boolean;
}

const col = (v: SweepView, name: string) => v.columns.indexOf(name);
const fmt = (x: number, d = 1) => x.toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: 0 });

/** A depth's colour: light to dark teal over the sweep's depth range. */
function depthColour(depth: number, lo: number, hi: number): string {
  const t = hi > lo ? (depth - lo) / (hi - lo) : 0.5;
  const l = 72 - t * 42;
  return `hsl(188 70% ${l}%)`;
}

const UNIT_WORDS: [string, string][] = [
  ["heat_pump_mw", "heat pump"],
  ["boiler_mw", "gas boiler"],
  ["electric_boiler_mw", "electric boiler"],
  ["absorption_mw", "absorption"],
  ["chiller_mw", "chillers"],
];

/** What a row is, in words: "2 doublets at 3,100 m (280 m³/h) · heat pump 3.2 MW · …". */
export function rowWords(v: SweepView, r: (number | string)[]): string {
  const n = Number(r[col(v, "doublets")]);
  const parts = [`${n} doublet${n === 1 ? "" : "s"} at ${fmt(Number(r[col(v, "depth_m")]), 0)} m (cap ${fmt(Number(r[col(v, "flow_cap_m3h")]), 0)} m³/h)`];
  for (const [k, w] of UNIT_WORDS) {
    const mw = Number(r[col(v, k)]);
    if (mw > 0) parts.push(`${w} ${fmt(mw)} MW`);
  }
  parts.push(gasWords(String(r[col(v, "gas")])));
  return parts.join(" · ");
}

const gasWords = (gas: string) => (gas === "buy" ? "gas bought" : gas === "produced" ? "only the brine's gas" : "the brine's gas sold");

/** The designs no other beats on both cost and CO₂: the drawn ones that meet every cap and the
 * search's own, as [€/MWh, t CO₂ a year], cheapest first. */
export function frontOf(v: SweepView): [number, number][] {
  const lc = col(v, "lcoe");
  const co = col(v, "co2_t");
  const br = col(v, "broken");
  const all: [number, number][] = [
    ...v.rows.filter((r) => !r[br]).map((r) => [Number(r[lc]), Number(r[co])] as [number, number]),
    ...v.marks.map((m) => [m.lcoe, m.co2_t] as [number, number]),
  ].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const out: [number, number][] = [];
  let least = Infinity;
  for (const p of all) {
    if (p[1] < least - 1e-9) {
      out.push(p);
      least = p[1];
    }
  }
  return out;
}

const PICK_WORDS: Record<string, string> = {
  best: "Best overall",
  cost: "Cheapest",
  co2: "Lowest CO₂",
  reliable: "Cheapest reliable",
  green_reliable: "Greenest reliable",
  gas_free: "Gas-free",
};

/** What the sweep varied: each parameter with its range, in words. */
export function variedParameters(v: SweepView): { key: string; label: string; range: string }[] {
  const dc = col(v, "doublets");
  const counts = [...new Set(v.rows.map((r) => Number(r[dc])))].sort();
  const gases = [...new Set(v.rows.map((r) => String(r[col(v, "gas")])))];
  const r = (k: string, unit: string, d = 0) => {
    const [lo, hi] = v.ranges[k] ?? [0, 0];
    return lo === hi ? `${fmt(lo, d)} ${unit}` : `${fmt(lo, d)}–${fmt(hi, d)} ${unit}`;
  };
  return [
    { key: "doublets", label: "Doublets", range: counts.join(", ") },
    { key: "depth_m", label: "Depth", range: r("depth_m", "m") },
    { key: "flow_cap_m3h", label: "Flow cap", range: r("flow_cap_m3h", "m³/h") },
    ...UNIT_WORDS.map(([k, w]) => ({ key: k, label: w[0].toUpperCase() + w.slice(1), range: `0 or ${r(k, "MW", 1)}` })),
    { key: "gas", label: "The brine's gas", range: gases.map(gasWords).join(" · ") },
  ];
}

/** The cheapest feasible design across a parameter's range, in up to ``bins`` steps. */
export function cheapestBy(v: SweepView, key: string, bins = 10): { x: number; cost: number; n: number }[] {
  const k = col(v, key);
  const lc = col(v, "lcoe");
  const br = col(v, "broken");
  const ok = v.rows.filter((r) => !r[br]);
  if (!ok.length) return [];
  const xs = ok.map((r) => Number(r[k]));
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  const discrete = new Set(xs).size <= bins;
  const at = (x: number) => (discrete || hi === lo ? x : lo + (Math.min(bins - 1, Math.floor(((x - lo) / (hi - lo)) * bins)) + 0.5) * ((hi - lo) / bins));
  const best = new Map<number, { cost: number; n: number }>();
  for (const r of ok) {
    const x = at(Number(r[k]));
    const c = Number(r[lc]);
    const b = best.get(x);
    best.set(x, { cost: b ? Math.min(b.cost, c) : c, n: (b?.n ?? 0) + 1 });
  }
  return [...best.entries()].map(([x, b]) => ({ x, ...b })).sort((a, b) => a.x - b.x);
}

/** Label positions beside the marks that carry one, nudged down where two would overlap. */
function placeLabels(items: { id: string; text: string; cx: number; cy: number }[], width: number) {
  const out = new Map<string, { x: number; y: number; anchor: "start" | "end" }>();
  const boxes: { x0: number; x1: number; y0: number; y1: number }[] = [];
  for (const b of [...items].sort((p, q) => p.cy - q.cy)) {
    const w = b.text.length * 6.4 + 4;
    const right = b.cx + 10 + w < width - 4;
    const x = right ? b.cx + 10 : b.cx - 10;
    const x0 = right ? x : x - w;
    let y = b.cy + 4;
    for (let k = 0; k < 8 && boxes.some((o) => x0 < o.x1 && x0 + w > o.x0 && y - 11 < o.y1 && y + 3 > o.y0); k++) y += 14;
    boxes.push({ x0, x1: x0 + w, y0: y - 11, y1: y + 3 });
    out.set(b.id, { x, y, anchor: right ? "start" : "end" });
  }
  return out;
}

interface Props {
  threadId: string;
  search: string;
  onToggle: (id: string) => void;
  selected: string[];
}

export function SweepMap({ threadId, search, onToggle, selected }: Props) {
  const wb = useWorkbench();
  const [view, setView] = useState<SweepView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);
  const [mode, setMode] = useState<"map" | "list">("map");
  const [by, setBy] = useState<ColourBy>("caps");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  const [pinned, setPinned] = useState<{ i: number; x: number; y: number } | null>(null);
  const [zoom, setZoom] = useState<Domain | null>(null);
  const [brush, setBrush] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [wrap, width] = useWidth(820);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawn = useRef<Drawn[]>([]);

  useEffect(() => {
    const ctl = new AbortController();
    setView(null);
    setError(null);
    setZoom(null);
    setPinned(null);
    void getSweep(threadId, search, ctl.signal).then((r) => {
      if (ctl.signal.aborted) return;
      if (r.ok) setView(r.data);
      else setError(r.message);
    });
    return () => ctl.abort();
  }, [threadId, search]);

  const scale = useMemo(() => {
    if (!view) return null;
    const lc = col(view, "lcoe");
    const co = col(view, "co2_t");
    if (zoom) return { xt: niceTicks(zoom.x0, zoom.x1, 6), yt: niceTicks(zoom.y0, zoom.y1, 5), lc, co, dom: zoom };
    const ok = view.rows.filter((r) => !r[col(view, "broken")]);
    const xs = [...ok.map((r) => Number(r[lc])), ...view.marks.map((m) => m.lcoe)].sort((a, b) => a - b);
    const ys = ok.map((r) => Number(r[co]) / 1000).sort((a, b) => a - b);
    if (!xs.length || !ys.length) return null;
    // The feasible designs' 1st to 99th percentile: a few extreme ones would squash the rest.
    const q = (a: number[], p: number) => a[Math.min(a.length - 1, Math.max(0, Math.round(p * (a.length - 1))))];
    const x0 = Math.min(q(xs, 0.01), ...view.marks.map((m) => m.lcoe));
    const x1 = Math.max(q(xs, 0.99), ...view.marks.map((m) => m.lcoe));
    const xt = niceTicks(x0 - (x1 - x0) * 0.04, x1 + (x1 - x0) * 0.04, 6);
    const yt = niceTicks(Math.max(0, q(ys, 0) - 0.5), q(ys, 1) + 0.5, 5);
    return { xt, yt, lc, co, dom: { x0: xt[0], x1: xt.at(-1)!, y0: yt[0], y1: yt.at(-1)! } };
  }, [view, zoom]);

  const w = width;
  const iw = w - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const sx = (x: number) => (scale ? M.left + ((x - scale.dom.x0) / (scale.dom.x1 - scale.dom.x0)) * iw : 0);
  const sy = (y: number) => (scale ? M.top + ih - ((y - scale.dom.y0) / (scale.dom.y1 - scale.dom.y0)) * ih : 0);
  const ix = (px: number) => (scale ? scale.dom.x0 + ((px - M.left) / iw) * (scale.dom.x1 - scale.dom.x0) : 0);
  const iy = (py: number) => (scale ? scale.dom.y0 + ((M.top + ih - py) / ih) * (scale.dom.y1 - scale.dom.y0) : 0);

  useEffect(() => {
    const c = canvas.current;
    if (!c || !view || !scale || !open || mode !== "map") return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.round(w * dpr);
    c.height = Math.round(H * dpr);
    const g = c.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, H);
    const br = col(view, "broken");
    const dc = col(view, "doublets");
    const dp = col(view, "depth_m");
    const [dlo, dhi] = view.ranges.depth_m ?? [0, 0];
    const out: Drawn[] = [];
    const inside = (x: number, y: number) => x >= M.left && x <= M.left + iw && y >= M.top && y <= M.top + ih;
    g.save();
    g.beginPath();
    g.rect(M.left, M.top, iw, ih);
    g.clip();
    // Failed designs first, faint, so the feasible ones read on top.
    for (const pass of ["failed", "ok"] as const) {
      view.rows.forEach((r, i) => {
        const broken = String(r[br] || "");
        if ((pass === "ok") !== !broken) return;
        if (broken ? hidden.has(broken) : hidden.has("ok")) return;
        if (r[scale.lc] == null || r[scale.co] == null) return; // no cost: nowhere on the map
        const cx = sx(Number(r[scale.lc]));
        const cy = sy(Number(r[scale.co]) / 1000);
        if (!inside(cx, cy)) return;
        out.push({ i, cx, cy, ok: !broken });
        g.beginPath();
        g.arc(cx, cy, broken ? 2.2 : zoom ? 3.2 : 2.4, 0, Math.PI * 2);
        if (broken) {
          g.strokeStyle = GREY;
          g.globalAlpha = 0.35;
          g.lineWidth = 0.8;
          g.stroke();
        } else {
          g.fillStyle = by === "doublets" ? DOUBLET_COLOURS[(Number(r[dc]) - 1) % 3] : by === "depth" ? depthColour(Number(r[dp]), dlo, dhi) : TEAL;
          g.globalAlpha = 0.55;
          g.fill();
        }
      });
    }
    g.globalAlpha = 1;
    // The front: the feasible designs no other beats on both cost and CO₂.
    const front = frontOf(view);
    if (front.length > 1 && !hidden.has("ok")) {
      g.beginPath();
      front.forEach(([lcoe, co2], k) => {
        const x = sx(lcoe);
        const y = sy(co2 / 1000);
        if (k) g.lineTo(x, y);
        else g.moveTo(x, y);
      });
      g.strokeStyle = INK;
      g.lineWidth = 1.4;
      g.setLineDash([5, 3]);
      g.stroke();
      g.setLineDash([]);
    }
    g.restore();
    drawn.current = out;
  }, [view, scale, w, iw, ih, by, hidden, open, mode, zoom]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error)
    return (
      <section className="lib-card lib-sweep" aria-label="Design space">
        <p className="lib-note">The design-space map isn't available: {error}</p>
      </section>
    );

  const nearest = (x: number, y: number): Drawn | null => {
    let best: Drawn | null = null;
    let d2 = 64;
    for (const p of drawn.current) {
      const d = (p.cx - x) ** 2 + (p.cy - y) ** 2;
      if (d < d2) {
        d2 = d;
        best = p;
      }
    }
    return best;
  };
  const local = (e: MouseEvent<HTMLDivElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - box.left, y: e.clientY - box.top };
  };
  const onDown = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as Element).closest(".sweep-mark, .sweep-card")) return;
    const p = local(e);
    setBrush({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
  };
  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!view || !scale) return;
    const p = local(e);
    if (brush) {
      setBrush({ ...brush, x1: p.x, y1: p.y });
      return;
    }
    const best = nearest(p.x, p.y);
    setHover(best ? { i: best.i, x: best.cx, y: best.cy } : null);
  };
  const onUp = (e: MouseEvent<HTMLDivElement>) => {
    if (!brush) return;
    const p = local(e);
    const dx = Math.abs(p.x - brush.x0);
    const dy = Math.abs(p.y - brush.y0);
    setBrush(null);
    if (dx > 8 && dy > 8) {
      // A box: zoom into it.
      setZoom({ x0: ix(Math.min(p.x, brush.x0)), x1: ix(Math.max(p.x, brush.x0)), y0: iy(Math.max(p.y, brush.y0)), y1: iy(Math.min(p.y, brush.y0)) });
      setPinned(null);
      return;
    }
    // A click: show the design under it.
    const best = nearest(p.x, p.y);
    setPinned(best ? { i: best.i, x: best.cx, y: best.cy } : null);
  };

  const sweepId = (i: number) => `${search}·sweep·${i}`;
  /** Bring a drawn design into the tabs; its id there. */
  const bring = async (i: number): Promise<string | null> => {
    setBusy(sweepId(i));
    setMessage(null);
    const res = await wb.openDesign(sweepId(i));
    setBusy(null);
    if (!res.ok) {
      setMessage(`Couldn't open it: ${res.message}`);
      return null;
    }
    return res.data.design.id;
  };
  const openIn = async (i: number, tab: "design" | "energy" | "economics") => {
    const id = await bring(i);
    if (id) go(tab, id);
  };
  const tick = async (i: number) => {
    const id = await bring(i);
    if (!id) return;
    await wb.refresh();
    onToggle(id);
    setMessage("Ticked: it is in the tray below for the side by side.");
  };

  const counts = view ? { ok: view.feasible, ...view.failures } : {};
  const total = view?.rows.length ?? 0;
  const tip = hover && view && !pinned ? view.rows[hover.i] : null;
  const card = pinned && view ? view.rows[pinned.i] : null;
  const labelOf = (m: SweepView["marks"][number]) => `${m.uid} · ${m.picks.map((k) => PICK_WORDS[k] ?? k).join(", ") || "ticked"}`;
  const labels =
    view && scale
      ? placeLabels(
          view.marks
            .filter((m) => m.role === "chosen" || m.picks.length > 0 || selected.includes(m.id))
            .map((m) => ({ id: m.id, text: labelOf(m), cx: sx(m.lcoe), cy: sy(m.co2_t / 1000) }))
            .filter((m) => m.cx >= M.left && m.cx <= M.left + iw && m.cy >= M.top && m.cy <= M.top + ih),
          w,
        )
      : new Map<string, { x: number; y: number; anchor: "start" | "end" }>();

  return (
    <section className={`lib-card lib-sweep${open ? "" : " is-folded"}`} aria-labelledby="sweep-title">
      <header className="lib-card-head sweep-head">
        <div>
          <h2 id="sweep-title">
            <button type="button" className="sweep-fold" aria-expanded={open} onClick={() => setOpen(!open)}>
              Design space
            </button>
          </h2>
          <p className="lib-card-sub">
            {view
              ? `${fmt(total, 0)} designs drawn evenly across every choice below and run for a year each; ${fmt(view.feasible, 0)} meet every cap. The search's ${view.marks.length} designs are its best sizing of each layout; these are the space around them.`
              : "Loading the designs…"}
          </p>
        </div>
        {view && open && (
          <div className="sweep-views" role="tablist" aria-label="Show the designs as">
            {(["map", "list"] as const).map((k) => (
              <button key={k} type="button" role="tab" aria-selected={mode === k} className={`seg${mode === k ? " on" : ""}`} onClick={() => setMode(k)}>
                {k === "map" ? "Map" : `List (${fmt(total, 0)})`}
              </button>
            ))}
          </div>
        )}
      </header>
      {open && view && (
        <>
          <div className="sweep-varied" aria-label="What the sweep varied">
            <span className="sweep-varied-cap">Varied</span>
            {variedParameters(view).map((p) => (
              <span key={p.key} className="sweep-param">
                <span className="k">{p.label}</span>
                <span className="v">{p.range}</span>
              </span>
            ))}
          </div>
          <div className="sweep-chips" role="group" aria-label="Show or hide designs">
            {Object.entries(counts).map(([k, n]) => (
              <button
                key={k}
                type="button"
                className={`sweep-chip${hidden.has(k) ? " off" : ""}${k === "ok" ? " is-ok" : ""}`}
                aria-pressed={!hidden.has(k)}
                title={hidden.has(k) ? "Show them" : "Hide them"}
                onClick={() => {
                  const next = new Set(hidden);
                  if (next.has(k)) next.delete(k);
                  else next.add(k);
                  setHidden(next);
                }}
              >
                <span className="sweep-dot" aria-hidden="true" />
                {k === "ok" ? "Meet every cap" : view.broken_words[k] ?? k} <span className="sweep-n">{fmt(Number(n), 0)}</span>
              </button>
            ))}
          </div>
          {message && (
            <p className="sweep-msg" role="status">
              {message}
            </p>
          )}
        </>
      )}
      {open && mode === "map" && (
        <>
          {view && (
            <div className="sweep-bar">
              <div className="sweep-colour" role="radiogroup" aria-label="Colour the dots by">
                <span className="sweep-colour-cap">Colour by</span>
                {(["caps", "doublets", "depth"] as const).map((k) => (
                  <button key={k} type="button" role="radio" aria-checked={by === k} className={`seg${by === k ? " on" : ""}`} onClick={() => setBy(k)}>
                    {k === "caps" ? "Meets the caps" : k === "doublets" ? "Doublets" : "Depth"}
                  </button>
                ))}
                <span className="sweep-key" aria-hidden="true">
                  {by === "caps" && (
                    <>
                      <i className="lg-dot" /> meets every cap <i className="lg-ring" /> breaks one
                    </>
                  )}
                  {by === "doublets" &&
                    DOUBLET_COLOURS.map((c, k) => (
                      <span key={c}>
                        <i style={{ background: c, borderRadius: 99 }} /> {k + 1}
                      </span>
                    ))}
                  {by === "depth" && (
                    <>
                      {fmt(view.ranges.depth_m?.[0] ?? 0, 0)} m
                      <i className="lg-grad" />
                      {fmt(view.ranges.depth_m?.[1] ?? 0, 0)} m
                    </>
                  )}
                </span>
              </div>
              <span className="sweep-hint">
                Drag a box to zoom · click a dot to open it
                {zoom && (
                  <button type="button" className="link-btn" onClick={() => setZoom(null)}>
                    Reset zoom
                  </button>
                )}
              </span>
            </div>
          )}
          <div
            ref={wrap}
            className={`sweep-body${brush ? " brushing" : ""}`}
            onMouseDown={onDown}
            onMouseMove={onMove}
            onMouseUp={onUp}
            onMouseLeave={() => {
              setHover(null);
              setBrush(null);
            }}
            onDoubleClick={() => setZoom(null)}
          >
            <canvas ref={canvas} style={{ width: w, height: H }} aria-hidden="true" />
            {view && scale && (
              <svg className="sweep-axes" width={w} height={H} role="img" aria-label={`Cost against CO₂ for ${total} drawn designs`}>
                {scale.xt.map((t) => (
                  <g key={`x${t}`}>
                    <line x1={sx(t)} x2={sx(t)} y1={M.top} y2={M.top + ih} className="grid" />
                    <text x={sx(t)} y={M.top + ih + 16} textAnchor="middle" className="tick">
                      {fmt(t, 0)}
                    </text>
                  </g>
                ))}
                {scale.yt.map((t) => (
                  <g key={`y${t}`}>
                    <line x1={M.left} x2={M.left + iw} y1={sy(t)} y2={sy(t)} className="grid" />
                    <text x={M.left - 8} y={sy(t) + 4} textAnchor="end" className="tick">
                      {fmt(t, 1)}
                    </text>
                  </g>
                ))}
                <text x={M.left + iw / 2} y={H - 6} textAnchor="middle" className="axis">
                  Cost of heat and cold, €/MWh
                </text>
                <text transform={`translate(16 ${M.top + ih / 2}) rotate(-90)`} textAnchor="middle" className="axis">
                  CO₂ a year, kt
                </text>
                {view.marks.map((m) => {
                  const cx = sx(m.lcoe);
                  const cy = sy(m.co2_t / 1000);
                  if (!(cx >= M.left && cx <= M.left + iw && cy >= M.top && cy <= M.top + ih)) return null;
                  const pick = m.role === "chosen";
                  const on = selected.includes(m.id);
                  const at = labels.get(m.id);
                  return (
                    <g
                      key={m.id}
                      className={`sweep-mark${pick ? " is-pick" : ""}${on ? " is-on" : ""}${m.swept ? " is-swept" : ""}`}
                      onClick={() => onToggle(m.id)}
                      role="button"
                      aria-label={`${m.uid}: ${fmt(m.lcoe)} €/MWh, ${fmt(m.co2_saving_pct)}% less CO₂${on ? ", ticked" : ""}`}
                    >
                      <title>{`${m.uid} · ${m.code}${m.picks.length ? ` · ${m.picks.join(", ")}` : ""}\n${fmt(m.lcoe)} €/MWh · ${fmt(m.co2_saving_pct)}% less CO₂ than gas${m.reliable ? " · any one unit can be out" : ""}\nClick to tick it for the side by side`}</title>
                      {m.swept ? (
                        <rect x={cx - 4.5} y={cy - 4.5} width={9} height={9} transform={`rotate(45 ${cx} ${cy})`} />
                      ) : (
                        <circle cx={cx} cy={cy} r={pick ? 6.5 : m.picks.length || on ? 5 : 3.2} />
                      )}
                      {at && (
                        <text x={at.x} y={at.y} textAnchor={at.anchor} className="sweep-label">
                          {labelOf(m)}
                        </text>
                      )}
                    </g>
                  );
                })}
                {pinned && <circle cx={pinned.x} cy={pinned.y} r={6} className="sweep-pinned" />}
                {brush && <rect x={Math.min(brush.x0, brush.x1)} y={Math.min(brush.y0, brush.y1)} width={Math.abs(brush.x1 - brush.x0)} height={Math.abs(brush.y1 - brush.y0)} className="sweep-brush" />}
              </svg>
            )}
            {tip && view && hover && (
              <div className="sweep-tip" style={{ left: Math.min(hover.x + 12, w - 280), top: Math.max(4, hover.y - 64) }} role="tooltip">
                <strong>
                  {fmt(Number(tip[col(view, "lcoe")]))} €/MWh · {fmt(Number(tip[col(view, "co2_saving_pct")]))}% less CO₂ than gas
                </strong>
                <span>{rowWords(view, tip)}</span>
                <span className="sweep-okline">{tip[col(view, "broken")] ? `Breaks a cap: ${view.broken_words[String(tip[col(view, "broken")])]}` : "Click to open it or tick it"}</span>
              </div>
            )}
            {card && view && pinned && (
              <div className="sweep-card ta-rise" style={{ left: Math.min(pinned.x + 14, w - 320), top: Math.min(Math.max(4, pinned.y - 40), H - 190) }} role="dialog" aria-label={`Drawn design ${pinned.i + 1}`}>
                <button type="button" className="sweep-card-x" aria-label="Close" onClick={() => setPinned(null)}>
                  ×
                </button>
                <span className="sweep-card-id">Drawn design X{pinned.i + 1}</span>
                <strong>
                  {fmt(Number(card[col(view, "lcoe")]))} €/MWh · {fmt(Number(card[col(view, "co2_saving_pct")]))}% less CO₂ · {fmt(Number(card[col(view, "capex_meur")]))} M€
                </strong>
                <span>{rowWords(view, card)}</span>
                {card[col(view, "broken")] ? (
                  <span className="sweep-broken">Breaks a cap: {view.broken_words[String(card[col(view, "broken")])]}</span>
                ) : (
                  <span className="sweep-okline">Meets every cap as drawn (sizes not trimmed; not checked with a unit out)</span>
                )}
                <span className="sweep-card-acts">
                  <button type="button" className="btn btn-soft ta-btn ta-soft" disabled={busy === sweepId(pinned.i)} onClick={() => void openIn(pinned.i, "design")}>
                    {busy === sweepId(pinned.i) ? "Running its year…" : "Open in Design"}
                  </button>
                  <button type="button" className="btn btn-soft ta-btn ta-soft" disabled={!!busy} onClick={() => void tick(pinned.i)}>
                    Tick to compare
                  </button>
                </span>
              </div>
            )}
          </div>
          {view && <DriversPanel view={view} />}
          {view && (
            <p className="lib-note sweep-foot">
              Drawn by Latin hypercube (each range cut into {fmt(total, 0)} strata, each drawn once) in {fmt(view.seconds, 1)} s. The best feasible ones, each unit shrunk while every cap held, joined {view.search.name}&rsquo;s designs (the table, &ldquo;from the design-space sweep&rdquo;).
            </p>
          )}
        </>
      )}
      {open && mode === "list" && view && <SweepList view={view} busy={busy} onOpen={(i) => void openIn(i, "design")} onTick={(i) => void tick(i)} />}
    </section>
  );
}

/** What drives the cost: the cheapest design that meets every cap, across each parameter's range. */
function DriversPanel({ view }: { view: SweepView }) {
  const keys: [string, string, string][] = [
    ["doublets", "Doublets", ""],
    ["depth_m", "Depth", "m"],
    ["flow_cap_m3h", "Flow cap", "m³/h"],
    ["heat_pump_mw", "Heat pump", "MW"],
    ["boiler_mw", "Gas boiler", "MW"],
    ["electric_boiler_mw", "Electric boiler", "MW"],
    ["absorption_mw", "Absorption", "MW"],
    ["chiller_mw", "Chillers", "MW"],
  ];
  const series = keys.map(([k, label, unit]) => ({ k, label, unit, pts: cheapestBy(view, k) })).filter((s) => s.pts.length > 1);
  if (!series.length) return null;
  const all = series.flatMap((s) => s.pts.map((p) => p.cost));
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const W = 170;
  const Hs = 70;
  return (
    <div className="sweep-drivers">
      <h3>What drives the cost</h3>
      <p className="lib-note">The cheapest design that meets every cap, across each choice&rsquo;s range (same scale in each, {fmt(lo, 0)}–{fmt(hi, 0)} €/MWh): a steep line is a choice that matters.</p>
      <div className="sweep-drivers-grid">
        {series.map((s) => {
          const x0 = s.pts[0].x;
          const x1 = s.pts.at(-1)!.x;
          const px = (x: number) => 6 + ((x - x0) / (x1 - x0 || 1)) * (W - 12);
          const py = (c: number) => 6 + (1 - (c - lo) / (hi - lo || 1)) * (Hs - 12);
          const best = s.pts.reduce((a, b) => (b.cost < a.cost ? b : a));
          return (
            <figure key={s.k} className="sweep-driver">
              <figcaption>
                {s.label}
                <span>
                  best at {fmt(best.x, s.k === "doublets" ? 0 : 0)} {s.unit}: {fmt(best.cost)} €/MWh
                </span>
              </figcaption>
              <svg width={W} height={Hs} role="img" aria-label={`${s.label}: the cheapest feasible design ${s.pts.map((p) => `${fmt(p.x, 0)} ${s.unit} ${fmt(p.cost)} €/MWh`).join(", ")}`}>
                <path d={s.pts.map((p, i) => `${i ? "L" : "M"}${px(p.x).toFixed(1)} ${py(p.cost).toFixed(1)}`).join("")} className="drv-line" />
                {s.pts.map((p) => (
                  <circle key={p.x} cx={px(p.x)} cy={py(p.cost)} r={p === best ? 3.6 : 2.2} className={p === best ? "drv-best" : "drv-dot"}>
                    <title>{`${fmt(p.x, 0)} ${s.unit}: ${fmt(p.cost)} €/MWh (${p.n} feasible designs)`}</title>
                  </circle>
                ))}
              </svg>
              <span className="drv-axis">
                <span>{fmt(x0, 0)}</span>
                <span>{fmt(x1, 0)}</span>
              </span>
            </figure>
          );
        })}
      </div>
    </div>
  );
}

type ListSort = "lcoe" | "co2_saving_pct" | "capex_meur";

/** Every drawn design as a row: feasible first, sortable, 25 a page, with Open and Tick. */
function SweepList({ view, busy, onOpen, onTick }: { view: SweepView; busy: string | null; onOpen: (i: number) => void; onTick: (i: number) => void }) {
  const [sort, setSort] = useState<ListSort>("lcoe");
  const [onlyOk, setOnlyOk] = useState(true);
  const [onlyFront, setOnlyFront] = useState(false);
  const [page, setPage] = useState(0);
  const br = col(view, "broken");
  const front = useMemo(() => new Set(view.front), [view]);
  const rows = useMemo(() => {
    const k = col(view, sort);
    const idx = view.rows.map((_, i) => i).filter((i) => (!onlyOk || !view.rows[i][br]) && (!onlyFront || front.has(i)));
    const dir = sort === "co2_saving_pct" ? -1 : 1;
    return idx.sort((a, b) => dir * (Number(view.rows[a][k]) - Number(view.rows[b][k])));
  }, [view, sort, onlyOk, onlyFront, br, front]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const shown = rows.slice(page * PAGE, page * PAGE + PAGE);
  const v = (i: number, k: string) => Number(view.rows[i][col(view, k)]);
  return (
    <div className="sweep-list">
      <div className="sweep-list-tools">
        <label>
          <input type="checkbox" checked={onlyOk} onChange={(e) => (setOnlyOk(e.target.checked), setPage(0))} /> Meet every cap
        </label>
        <label>
          <input type="checkbox" checked={onlyFront} onChange={(e) => (setOnlyFront(e.target.checked), setPage(0))} /> None beats them on cost and CO₂
        </label>
        <span className="sweep-list-n">
          {fmt(rows.length, 0)} designs · page {page + 1} of {pages}
        </span>
      </div>
      <div className="sweep-list-scroll">
        <table className="sweep-table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Doublets · depth · cap</th>
              <th scope="col">Units</th>
              {(
                [
                  ["lcoe", "€/MWh"],
                  ["co2_saving_pct", "CO₂ cut"],
                  ["capex_meur", "Capital"],
                ] as [ListSort, string][]
              ).map(([k, label]) => (
                <th key={k} scope="col" aria-sort={sort === k ? (k === "co2_saving_pct" ? "descending" : "ascending") : "none"}>
                  <button type="button" className={`sweep-sort${sort === k ? " on" : ""}`} onClick={() => (setSort(k), setPage(0))}>
                    {label}
                  </button>
                </th>
              ))}
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((i) => {
              const units = UNIT_WORDS.filter(([k]) => v(i, k) > 0)
                .map(([k, w]) => `${w} ${fmt(v(i, k))}`)
                .join(" · ");
              return (
                <tr key={i} className={view.rows[i][br] ? "is-broken" : undefined}>
                  <td className="mono">
                    X{i + 1}
                    {front.has(i) && <span className="sweep-front" title="None beats it on both cost and CO₂"> ★</span>}
                  </td>
                  <td>
                    {v(i, "doublets")} × {fmt(v(i, "depth_m"), 0)} m · {fmt(v(i, "flow_cap_m3h"), 0)} m³/h
                  </td>
                  <td className="sweep-units">
                    {units || "none"} · {gasWords(String(view.rows[i][col(view, "gas")]))}
                  </td>
                  <td className="num">{fmt(v(i, "lcoe"))}</td>
                  <td className="num">{fmt(v(i, "co2_saving_pct"))} %</td>
                  <td className="num">{fmt(v(i, "capex_meur"))} M€</td>
                  <td className="sweep-acts">
                    <button type="button" className="link-btn" disabled={!!busy} onClick={() => onOpen(i)}>
                      {busy === `${view.search.id}·sweep·${i}` ? "Running…" : "Open"}
                    </button>
                    <button type="button" className="link-btn" disabled={!!busy} onClick={() => onTick(i)}>
                      Tick
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="sweep-pager">
        <button type="button" className="btn btn-soft ta-btn" disabled={page === 0} onClick={() => setPage(page - 1)}>
          ‹ Previous
        </button>
        <button type="button" className="btn btn-soft ta-btn" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>
          Next ›
        </button>
      </div>
    </div>
  );
}
