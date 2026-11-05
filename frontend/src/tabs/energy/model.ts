// The Energy tab's data: a design's year (Design.year) turned into what the charts draw. Pure
// functions, tested in model.test.ts.
//
//   dayRows      the 365 days of one side (heat or cold): each source's MW, the demand, the gap
//   stackTops    the stacked areas' tops per source
//   durationRows the same days, highest demand first (the load-duration curve)
//   sideShares   each source's share of what was supplied over the year

import type { Design, Year } from "../../workbench";

export type Side = "heat" | "cool";

/**
 * The sources of each side, in stacking (dispatch) order: the base load at the bottom. The
 * electric boiler runs last, after the gas boiler (a gas-free design's peaks); a design without
 * one simply has nothing in its band.
 */
export const SIDE_KEYS: Record<Side, string[]> = { heat: ["geo", "hp", "boiler", "electric_boiler"], cool: ["free", "abs", "chill"] };

/**
 * Names and colours: the chat's result card's (ResultCard.tsx), so every chart reads as one. The
 * electric boiler's raspberry passes the dataviz checks against the other three heat colours,
 * every pair (colour-blind separation and normal vision).
 */
export const SOURCE_META: Record<string, { label: string; color: string }> = {
  geo: { label: "Geothermal", color: "#C24E1C" },
  hp: { label: "Heat pump", color: "#E3A33B" },
  boiler: { label: "Gas boiler", color: "#7856C4" },
  electric_boiler: { label: "Electric boiler", color: "#C8378A" },
  free: { label: "Free cooling", color: "#3C9D7A" },
  abs: { label: "Absorption chiller", color: "#2363A6" },
  chill: { label: "Electric chillers", color: "#139FBF" },
};

export const INK = "#11181C";

/** The heat the plant can give at once, MW: every heat unit's size (the electric boiler's from its card when the plant view leaves it out). */
export function heatInstalled(design: Pick<Design, "plant" | "graph">): number {
  const p = design.plant;
  const s = p.sizes_mw;
  const eb = s.electric_boiler ?? design.graph?.nodes.find((n) => n.type === "electric_boiler")?.values.power_mw ?? 0;
  return (s.heat_exchanger || 0) + (p.heat_pump ? s.heat_pump || 0 : 0) + (p.boiler ? s.boiler || 0 : 0) + (eb || 0);
}

/** What draws electricity from the grid, in a fixed order, with the colour of the part that draws it. */
export const POWER_META: { key: string; label: string; color: string }[] = [
  { key: "hp", label: "Heat pump", color: "#E3A33B" },
  { key: "electric_boiler", label: "Electric boiler", color: "#C8378A" },
  { key: "pumps", label: "Well pumps", color: "#8B7967" },
  { key: "chillers", label: "Electric chillers", color: "#139FBF" },
  { key: "towers", label: "Cooling towers", color: "#5B7F94" },
  { key: "network", label: "Network pumps", color: "#A3ADB5" },
  { key: "recovery_hp", label: "Recovery heat pump", color: "#B9852F" },
];

/** The year's grid electricity by user (Year.electricity_gwh), the ones that draw any, in POWER_META's order; unknown users last, in grey. */
export function powerParts(year: Pick<Year, "electricity_gwh">): { key: string; label: string; color: string; gwh: number }[] {
  const el = year.electricity_gwh ?? {};
  const known = POWER_META.map((m) => ({ ...m, gwh: num(el[m.key]) }));
  const other = Object.keys(el)
    .filter((k) => !POWER_META.some((m) => m.key === k))
    .map((k) => ({ key: k, label: k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()), color: "#B3BAB2", gwh: num(el[k]) }));
  return [...known, ...other].filter((p) => p.gwh > 0.0005);
}

const powerColor = (key: string) => POWER_META.find((m) => m.key === key)?.color ?? "#B3BAB2";

/**
 * The units that let out CO₂, in the order of Year.co2_by_unit_t (the PDF report's too): heat,
 * the wells and the brine's gas, cold, the network. A unit drawn elsewhere on the tab keeps its
 * colour there; the flare and the brine's own CO₂ have their own (checked against their
 * neighbours with the dataviz palette validator).
 */
export const CO2_META: { key: string; label: string; color: string; how: string }[] = [
  { key: "boiler", label: "Gas boiler", color: SOURCE_META.boiler.color, how: "burns the bought gas and the brine's methane" },
  { key: "electric_boiler", label: "Electric boiler", color: SOURCE_META.electric_boiler.color, how: "grid electricity" },
  { key: "hp", label: "Heat pump", color: SOURCE_META.hp.color, how: "grid electricity" },
  { key: "pumps", label: "Well pumps", color: powerColor("pumps"), how: "grid electricity: the ESPs and injection pumps" },
  { key: "flare", label: "Flare", color: "#9C4A1E", how: "burns the brine's methane the boiler does not take" },
  { key: "brine_co2", label: "Brine's own CO₂", color: "#5E9C3A", how: "the brine's CO₂, let out at the gas separator" },
  { key: "chillers", label: "Electric chillers", color: SOURCE_META.chill.color, how: "grid electricity" },
  { key: "towers", label: "Cooling towers", color: powerColor("towers"), how: "grid electricity: fans and pumps" },
  { key: "network", label: "Network pumps", color: powerColor("network"), how: "grid electricity" },
];

export interface Co2Part {
  key: string;
  label: string;
  color: string;
  how: string;
  /** t CO₂ a year. */
  t: number;
  /** Of the plant's total, 0..1. */
  share: number;
}

/**
 * The year's CO₂ by unit (Year.co2_by_unit_t): the units that let any out, in CO2_META's order
 * (unknown ones last, in grey), their total, and the names of the units that let out none. Null
 * for a design saved before the split, or one that lets out nothing.
 */
export function co2Parts(year: Pick<Year, "co2_by_unit_t">): { parts: Co2Part[]; total: number; none: string[] } | null {
  const split = year.co2_by_unit_t;
  if (!split) return null;
  const known = CO2_META.map((m) => ({ ...m, t: num(split[m.key]) }));
  const other = Object.keys(split)
    .filter((k) => !CO2_META.some((m) => m.key === k))
    .map((k) => ({ key: k, label: k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()), color: "#B3BAB2", how: "", t: num(split[k]) }));
  const all = [...known, ...other];
  const total = all.reduce((a, x) => a + Math.max(0, x.t), 0);
  if (!(total > 0)) return null;
  return {
    parts: all.filter((x) => x.t > 0).map((x) => ({ ...x, share: x.t / total })),
    total,
    none: all.filter((x) => !(x.t > 0)).map((x) => x.label),
  };
}

/** A share as the CO₂ chart writes it: "61.3%", "<0.1%" for a sliver. */
export function co2Share(f: number): string {
  if (f > 0 && f < 0.0005) return "<0.1%";
  const r = Math.round(f * 1000) / 10;
  return `${Number.isInteger(r) ? r : r.toFixed(1)}%`;
}

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
/** The day index (0-based) each month starts on, in a 365-day year. */
export const MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

export interface DayRow {
  /** 0-based day of the year (0 = 1 January). */
  day: number;
  demand: number;
  /** MW per source, in the order of the keys asked for; never negative. */
  parts: number[];
  supplied: number;
  /** MW of the demand not met; 0 when the supply covers it (within rounding). */
  unmet: number;
}

const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);

/** The gap between demand and supply that counts as not met: past rounding (10 kW or 0.5 %). */
export function unmetOf(demand: number, supplied: number): number {
  const gap = demand - supplied;
  return gap > Math.max(0.01, demand * 0.005) ? gap : 0;
}

/**
 * The days of one side: each source's MW in `keys` order, the demand and the gap. A missing or
 * short series counts as 0; the demand's length sets the number of days ([] without one).
 */
export function dayRows(side: Record<string, unknown> | undefined, keys: string[]): DayRow[] {
  const demand = side?.demand;
  if (!Array.isArray(demand)) return [];
  return demand.map((d, day) => {
    const parts = keys.map((k) => {
      const list = side?.[k];
      return Array.isArray(list) ? Math.max(0, num(list[day])) : 0;
    });
    const supplied = parts.reduce((a, b) => a + b, 0);
    const dem = Math.max(0, num(d));
    return { day, demand: dem, parts, supplied, unmet: unmetOf(dem, supplied) };
  });
}

/** The rows of a design's side, with the side's own source keys. */
export function sideRows(year: Year, side: Side): DayRow[] {
  return dayRows(year.daily_mw?.[side] as unknown as Record<string, unknown> | undefined, SIDE_KEYS[side]);
}

/**
 * The stacked areas' tops: tops[k][i] is the sum of sources 0..k on row i, so source k is the
 * band between tops[k - 1] (or 0) and tops[k].
 */
export function stackTops(rows: DayRow[], nKeys: number): number[][] {
  const tops: number[][] = Array.from({ length: nKeys }, () => new Array<number>(rows.length));
  rows.forEach((r, i) => {
    let cum = 0;
    for (let k = 0; k < nKeys; k++) {
      cum += r.parts[k] ?? 0;
      tops[k][i] = cum;
    }
  });
  return tops;
}

/**
 * The load-duration curve: the same days, highest demand first (ties by date), each keeping its
 * own supply, so the stack shows what covers the load at each level. A new array; rows unchanged.
 */
export function durationRows(rows: DayRow[]): DayRow[] {
  return rows.slice().sort((a, b) => b.demand - a.demand || a.day - b.day);
}

/** The indices of the keys that supply anything over the year. */
export function activeIndices(rows: DayRow[], nKeys: number): number[] {
  const out: number[] = [];
  for (let k = 0; k < nKeys; k++) if (rows.some((r) => (r.parts[k] ?? 0) > 0)) out.push(k);
  return out;
}

/** Each source's share of the supply over the year (0..1), and the share of the demand not met. */
export function sideShares(rows: DayRow[], nKeys: number): { parts: number[]; unmet: number } {
  const demand = rows.reduce((a, r) => a + r.demand, 0);
  const parts = new Array<number>(nKeys).fill(0);
  for (const r of rows) for (let k = 0; k < nKeys; k++) parts[k] += r.parts[k] ?? 0;
  const supplied = parts.reduce((a, b) => a + b, 0);
  const unmet = rows.reduce((a, r) => a + r.unmet, 0);
  return { parts: parts.map((p) => (supplied > 0 ? p / supplied : 0)), unmet: demand > 0 ? unmet / demand : 0 };
}

/** The row with the highest demand (the first such day); -1 with none. */
export function peakIndex(rows: DayRow[]): number {
  let best = -1;
  rows.forEach((r, i) => {
    if (best < 0 || r.demand > rows[best].demand) best = i;
  });
  return best;
}

/** "14 Jan" for day index 13. */
export function dayLabel(day: number): string {
  const d = Math.max(0, Math.min(364, Math.round(day)));
  let m = 11;
  while (m > 0 && MONTH_START[m] > d) m--;
  return `${d - MONTH_START[m] + 1} ${MONTHS[m]}`;
}

/** The month (0..11) a day index falls in. */
export function monthOf(day: number): number {
  let m = 11;
  while (m > 0 && MONTH_START[m] > day) m--;
  return m;
}

/** The days the supply falls short, as runs of consecutive days [first, last]. */
export function shortRuns(rows: DayRow[]): [number, number][] {
  const out: [number, number][] = [];
  rows.forEach((r, i) => {
    if (r.unmet <= 0) return;
    const last = out[out.length - 1];
    if (last && last[1] === i - 1) last[1] = i;
    else out.push([i, i]);
  });
  return out;
}

/**
 * A question worth asking about a side's year, from its numbers: why a peak source runs in the
 * month it runs most, else how the base source carries the year.
 */
export function yearQuestion(rows: DayRow[], keys: string[], side: Side): string {
  if (!rows.length) return side === "heat" ? "How is the heat supplied over the year?" : "How is the cold supplied over the year?";
  const monthly = (k: number) => {
    const m = new Array<number>(12).fill(0);
    for (const r of rows) m[monthOf(r.day)] += r.parts[k] ?? 0;
    return m;
  };
  // The topmost source that runs at all: the one that tops up the peak.
  for (let k = keys.length - 1; k >= 1; k--) {
    const m = monthly(k);
    const most = m.indexOf(Math.max(...m));
    if (m[most] > 0) return `Why ${does(keys[k])} the ${sourceName(keys[k])} run in ${MONTH_NAMES[most]}?`;
  }
  return `Can the ${sourceName(keys[0])} cover the whole year on its own?`;
}

const sourceName = (key: string) => SOURCE_META[key]?.label.toLowerCase() ?? key;
const does = (key: string) => (key === "chill" ? "do" : "does");

// ------------------------------------------------------------------ doublets over the year

export interface DoubletYear {
  /** 1, 2, 3. */
  doublet: number;
  /** m³/h each day (0 when off). */
  flow: number[];
  /** The producer's wellhead each day, °C (null when off or not sent). */
  wellhead: (number | null)[];
  on: boolean[];
  /** Its flow cap, m³/h. */
  cap: number;
  /** Mean flow over the days it runs, m³/h (null when it never runs). */
  mean: number | null;
  daysOn: number;
  /** The wellhead's range over the days it runs, °C. */
  tMin: number | null;
  tMax: number | null;
  /** Its (first) planned stop, [first, last] day (0-based), when the server sent it. */
  stop: [number, number] | null;
  /** Every planned stop, [first, last] days: one block, or the user's several ranges. */
  stops: [number, number][];
}

/** Each doublet's planned stops, [first, last] days (0-based): `stop_ranges`, else one block per doublet (`stop_days`). */
export function stopRanges(year: Pick<Year, "stop_days" | "stop_ranges"> | null | undefined): [number, number][][] {
  const ranges = year?.stop_ranges;
  if (ranges?.length) return ranges.map((r) => (r ?? []).filter((x) => x && x.length >= 2).map((x) => [x[0], x[1]] as [number, number]));
  return (year?.stop_days ?? []).map((s) => (s && s.length >= 2 ? [[s[0], s[1]] as [number, number]] : []));
}

/**
 * Each doublet over the year from Design.year.doublets: the flow, the wellhead temperature and
 * what they add up to. The cap is the doublet's row's (Plant.doublets), else the plant's.
 */
export function doubletYears(year: Year, plant?: { doublets?: { doublet: number; cap_m3h: number }[]; flow_m3h?: number | null } | null): DoubletYear[] {
  return (year.doublets ?? []).map((d, i) => {
    const flow = (d.flow_m3h ?? []).map((v) => (Number.isFinite(v) ? Math.max(0, v) : 0));
    const on = flow.map((v, k) => (d.on?.[k] ?? v > 0) && v > 0.05);
    const wellhead = flow.map((_, k) => {
      const t = d.wellhead_c?.[k];
      return on[k] && typeof t === "number" && Number.isFinite(t) ? t : null;
    });
    const running = flow.filter((_, k) => on[k]);
    const temps = wellhead.filter((t): t is number => t != null);
    const row = plant?.doublets?.find((r) => r.doublet === i + 1) ?? plant?.doublets?.[i];
    const stops = stopRanges(year)[i] ?? [];
    return {
      doublet: i + 1,
      flow,
      wellhead,
      on,
      cap: row?.cap_m3h || plant?.flow_m3h || Math.max(0, ...flow),
      mean: running.length ? running.reduce((a, b) => a + b, 0) / running.length : null,
      daysOn: running.length,
      tMin: temps.length ? Math.min(...temps) : null,
      tMax: temps.length ? Math.max(...temps) : null,
      stop: stops[0] ?? null,
      stops,
    };
  });
}
