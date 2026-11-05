// The Sensitivity tab's numbers: which parameters start selected, how a parameter's range is shown
// and typed (a fraction-valued rate shows as %, is typed as %, and is sent as a fraction), the
// request built from the picks, and the result reshaped for the tornado, the spider and the
// swing heatmap. Pure functions, tested in params.test.ts.

import { fmtNum, type SensOutput, type SensParam, type Sensitivity, type SensitivityRequest } from "../../workbench";

export const GROUPS: { id: SensParam["group"]; label: string }[] = [
  { id: "subsurface", label: "Subsurface" },
  { id: "demand", label: "Demand" },
  { id: "prices", label: "Prices" },
  { id: "costs", label: "Costs" },
  { id: "equipment", label: "Equipment" },
];

export const SAMPLES = { min: 50, max: 500, step: 50, default: 200 };

// ------------------------------------------------------------------ the default picks

/**
 * What the tab starts with: the heating return temperature (not given by the organisers), the
 * reservoir temperature, the electricity and gas prices, and the capital costs. Found by key or
 * label, so a catalogue with other keys still starts with them; any it doesn't have is skipped.
 */
const DEFAULTS: RegExp[] = [/heat(ing)?.?return/i, /reservoir.?temp|^reservoir_delta/i, /electricity/i, /gas.?price|^gas_eur/i, /capital|capex|well.?cost/i];

export function defaultSelection(params: SensParam[]): string[] {
  const out: string[] = [];
  for (const re of DEFAULTS) {
    const p = params.find((x) => !out.includes(x.key) && (re.test(x.key) || re.test(x.label)));
    if (p) out.push(p.key);
  }
  return out;
}

export const DEFAULT_OUTPUTS = ["lcoh"];

// ------------------------------------------------------------------ units: shown vs sent

/**
 * A rate sent as a fraction (the discount rate, 0.03..0.08) is shown and typed in %. A
 * catalogue that already speaks % (3..9) is left alone.
 */
export function isFractionPercent(p: SensParam): boolean {
  const rate = p.key === "discount_rate" || /\brate\b/i.test(p.label);
  return rate && Math.max(Math.abs(p.low), Math.abs(p.high)) <= 1;
}

/** Shown value = sent value × factor. */
export function displayFactor(p: SensParam): number {
  return isFractionPercent(p) ? 100 : 1;
}

/** The unit beside the inputs: "%" for a fraction-valued rate, "×" for a scale. */
export function displayUnit(p: SensParam): string {
  if (isFractionPercent(p)) return "%";
  if (p.kind === "scale") return "×";
  return p.unit;
}

const clean = (v: number) => Number(v.toPrecision(12));

export const toDisplay = (p: SensParam, sent: number) => clean(sent * displayFactor(p));
export const toSent = (p: SensParam, shown: number) => clean(shown / displayFactor(p));

/** What the kind means, for the row's help line. */
export function kindText(p: SensParam): string {
  if (p.kind === "delta") return "added to the design's value";
  if (p.kind === "scale") return "times the design's value (1 = as is)";
  return "replaces the value";
}

export function kindTag(p: SensParam): string {
  return p.kind === "delta" ? "change" : p.kind === "scale" ? "scale" : "value";
}

/** Up to `digits` decimals, trailing zeros dropped, a real minus: 0.8, 5.25, −10, 1,500. */
export function trimNum(v: number, digits = 2): string {
  if (!Number.isFinite(v)) return "–";
  const s = Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-US") : String(Number(v.toFixed(digits)));
  return s.replace(/^-/, "−");
}

/** A parameter's value (as sent) for labels: "−10 °C", "0.8×", "60 €/MWh", "5.25%", "10 D·m". */
export function fmtParam(p: SensParam, sent: number): string {
  const v = toDisplay(p, sent);
  const unit = displayUnit(p);
  if (p.kind === "delta") return `${v > 0 ? "+" : ""}${trimNum(v)}${unit ? ` ${unit}` : ""}`;
  if (unit === "×") return `${trimNum(v)}×`;
  if (unit === "%") return `${trimNum(v)}%`;
  return `${trimNum(v, Math.abs(v) < 1 ? 3 : 1)}${unit ? ` ${unit}` : ""}`;
}

/** The catalogue's groups in the picker's order: the known ones first, then any other by its name. */
export function paramGroups(catalogue: SensParam[]): { id: string; label: string; params: SensParam[] }[] {
  const ids = [...GROUPS.map((g) => g.id as string), ...catalogue.map((p) => p.group).filter((g) => !GROUPS.some((k) => k.id === g))];
  return [...new Set(ids)]
    .map((id) => ({ id, label: GROUPS.find((g) => g.id === id)?.label ?? (id ? id.charAt(0).toUpperCase() + id.slice(1) : "Other"), params: catalogue.filter((p) => p.group === id) }))
    .filter((g) => g.params.length > 0);
}

/**
 * Picks kept from before, checked against the catalogue the server sends now: parameters and
 * outputs it no longer has are dropped (an older server's "transmissivity", say), and with no
 * output left the first it has is measured.
 */
export function keepKnown<T extends { rows: ParamRow[]; outputs: string[] }>(picks: T, catalogue: { parameters: SensParam[]; outputs: SensOutput[] }): T {
  const params = new Set(catalogue.parameters.map((p) => p.key));
  const outs = new Set<string>(catalogue.outputs.map((o) => o.key));
  const rows = picks.rows.filter((r) => params.has(r.key));
  const kept = picks.outputs.filter((o) => outs.has(o));
  const outputs = kept.length ? kept : catalogue.outputs.slice(0, 1).map((o) => o.key);
  if (rows.length === picks.rows.length && outputs.length === picks.outputs.length && outputs.every((o, i) => o === picks.outputs[i])) return picks;
  return { ...picks, rows, outputs };
}

// ------------------------------------------------------------------ the rows being edited

/** A selected parameter: its range as typed (in the shown unit). */
export interface ParamRow {
  key: string;
  low: string;
  high: string;
}

/** A number as typed: "−10", "-10", "0,5", " 3 " → a number; anything else → null. */
export function parseNum(s: string): number | null {
  const t = s.trim().replace(/[−–]/g, "-").replace(",", ".");
  if (!t || !/^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(t)) return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

/** "−10", "1.2", "5.25" for an input. */
export function fmtInput(v: number): string {
  const s = String(clean(v));
  return s.startsWith("-") ? `−${s.slice(1)}` : s;
}

export function newRow(p: SensParam): ParamRow {
  return { key: p.key, low: fmtInput(toDisplay(p, p.low)), high: fmtInput(toDisplay(p, p.high)) };
}

/** Whether a row still has the catalogue's range. */
export function isDefaultRange(p: SensParam, row: ParamRow): boolean {
  const lo = parseNum(row.low);
  const hi = parseNum(row.high);
  return lo != null && hi != null && toSent(p, lo) === clean(p.low) && toSent(p, hi) === clean(p.high);
}

export function rowError(row: ParamRow): string | null {
  const lo = parseNum(row.low);
  const hi = parseNum(row.high);
  if (lo == null || hi == null) return "Type a number for both ends.";
  if (!(lo < hi)) return "Low must be below high.";
  return null;
}

/** Add or remove a parameter, keeping the order picked. */
export function toggleRow(rows: ParamRow[], p: SensParam): ParamRow[] {
  return rows.some((r) => r.key === p.key) ? rows.filter((r) => r.key !== p.key) : [...rows, newRow(p)];
}

// Colours follow the parameter, never its rank: a slot is taken when it's added and freed when
// it's removed, so removing one never repaints the others.
export function assignSlots(slots: Record<string, number>, keys: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const k of keys) if (k in slots) out[k] = slots[k];
  for (const k of keys) {
    if (k in out) continue;
    const used = new Set(Object.values(out));
    let s = 0;
    while (used.has(s)) s++;
    out[k] = s;
  }
  return out;
}

// ------------------------------------------------------------------ the request

export interface McSetting {
  on: boolean;
  samples: number;
}

/**
 * The model runs a request costs, as the server counts them: the base design, the two ends of each
 * parameter's range (the tornado), three points inside each range (the spider's other three), and
 * the Monte Carlo samples.
 */
export function runCount(params: number, samples: number): { base: number; ends: number; inside: number; samples: number; total: number } {
  const p = Math.max(0, params);
  const n = Math.max(0, samples);
  return { base: 1, ends: 2 * p, inside: 3 * p, samples: n, total: 1 + 5 * p + n };
}

/** The request for the picks; null while a range is invalid or nothing is picked. */
export function buildRequest(
  threadId: string,
  design: string,
  catalogue: SensParam[],
  rows: ParamRow[],
  outputs: string[],
  mc: McSetting,
): SensitivityRequest | null {
  if (!rows.length || !outputs.length) return null;
  const parameters: SensitivityRequest["parameters"] = [];
  for (const row of rows) {
    const p = catalogue.find((x) => x.key === row.key);
    if (!p || rowError(row)) return null;
    parameters.push({ key: p.key, low: toSent(p, parseNum(row.low)!), high: toSent(p, parseNum(row.high)!) });
  }
  const samples = mc.on ? Math.min(SAMPLES.max, Math.max(SAMPLES.min, Math.round(mc.samples))) : 0;
  return { threadId, design, parameters, outputs: [...outputs], samples };
}

/** The same picks give the same key, whatever order they were picked in. */
export function configKey(req: SensitivityRequest, designSig = ""): string {
  const params = [...req.parameters].sort((a, b) => a.key.localeCompare(b.key)).map((p) => `${p.key}:${p.low}:${p.high}`);
  const outs = [...req.outputs].sort();
  return JSON.stringify([req.threadId, req.design, designSig, params, outs, req.samples ?? 0]);
}

// ------------------------------------------------------------------ the result, reshaped

export interface TornadoRow {
  key: string;
  label: string;
  /** The output with the parameter at the low and the high end of its range. */
  low: number | null;
  high: number | null;
  base: number | null;
  swing: number;
}

/** One output's tornado, the biggest swing first (the server sorts by the first output only). */
export function tornadoRows(result: Sensitivity, output: string): TornadoRow[] {
  const base = result.base[output] ?? null;
  return result.tornado
    .map((t, i) => {
      const low = t.low[output] ?? null;
      const high = t.high[output] ?? null;
      const swing = low != null && high != null ? Math.abs(high - low) : 0;
      return { key: t.key, label: t.label, low, high, base, swing, i };
    })
    .sort((a, b) => b.swing - a.swing || a.i - b.i)
    .map(({ i: _i, ...row }) => row);
}

/** Where x sits in [lo, hi], from −100 (low end) to +100 (high end). */
export function rangePosition(x: number, lo: number, hi: number): number {
  if (!(hi > lo)) return 0;
  return clean(((x - lo) / (hi - lo)) * 200 - 100);
}

export interface SpiderLine {
  key: string;
  label: string;
  points: { pos: number; x: number; y: number }[];
}

/** The spider's lines for one output: x is the position in each parameter's own range. */
export function spiderLines(result: Sensitivity, output: string): SpiderLine[] {
  const labels = new Map(result.tornado.map((t) => [t.key, t.label]));
  return result.spider
    .map((s) => {
      const xs = s.points.map((p) => p.x);
      const lo = Math.min(...xs);
      const hi = Math.max(...xs);
      const points = s.points
        .filter((p) => p.values[output] != null)
        .map((p) => ({ pos: rangePosition(p.x, lo, hi), x: p.x, y: p.values[output] }));
      return { key: s.key, label: labels.get(s.key) ?? s.key, points };
    })
    .filter((l) => l.points.length > 0);
}

/**
 * Each parameter's share of an output's one-at-a-time swing (its swing over the sum of all the
 * swings), for the heatmap: output → parameter → 0..1. An output nothing moves gets all zeros.
 */
export function swingShares(result: Sensitivity, outputs: string[]): Record<string, Record<string, number>> {
  const out: Record<string, Record<string, number>> = {};
  for (const o of outputs) {
    const rows = tornadoRows(result, o);
    const total = rows.reduce((s, r) => s + r.swing, 0);
    out[o] = Object.fromEntries(rows.map((r) => [r.key, total > 0 ? r.swing / total : 0]));
  }
  return out;
}

/** The outputs a result has, in the order asked. */
export function resultOutputs(result: Sensitivity, asked: string[]): string[] {
  const have = new Set(Object.keys(result.base));
  return asked.filter((o) => have.has(o));
}

/** An output's value: "42.4 €/MWh", "80.9%", "2" (a count, such as the caps broken, has no unit). */
export function fmtOut(o: SensOutput | undefined, v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return "–";
  const s = fmtNum(v, digits).replace(/^-/, "−");
  if (!o?.unit) return s;
  return o.unit === "%" ? `${s}%` : `${s} ${o.unit}`;
}

/** An output in a sentence: "cost of heat", "number of caps broken" (a count has no unit). */
export function outputName(o: SensOutput): string {
  return o.unit ? lowerFirst(o.label) : `number of ${lowerFirst(o.label)}`;
}

/** "Reservoir temperature" → "reservoir temperature", leaving "CO₂ price" and "NPV …" alone. */
export function lowerFirst(s: string): string {
  return /^[A-Z][a-z]/.test(s) ? s[0].toLowerCase() + s.slice(1) : s;
}

// ------------------------------------------------------------------ Monte Carlo, in words

/** Which way is better for each output. */
export const OUTPUT_BETTER: Record<string, "lower" | "higher"> = {
  lcoh: "lower",
  lcoc: "lower",
  lcoe: "lower",
  violations: "lower",
  capex_meur: "lower",
  co2_saving_pct: "higher",
  heat_coverage: "higher",
  npv_meur: "higher",
};

/** The share of the samples below v, read off the histogram (linear within a bin). */
export function shareBelow(h: { edges: number[]; counts: number[] }, v: number): number {
  const total = h.counts.reduce((s, c) => s + c, 0);
  if (!total) return 0;
  let below = 0;
  h.counts.forEach((c, i) => {
    const a = h.edges[i];
    const b = h.edges[i + 1];
    if (v >= b) below += c;
    else if (v > a) below += (c * (v - a)) / (b - a);
  });
  return Math.min(1, Math.max(0, below / total));
}

/**
 * Where the base case sits among the samples, and whether the uncertainty mostly works for the
 * design or against it: "worse" when more than 60% of the samples come out worse than the base.
 */
export function baseVerdict(h: { edges: number[]; counts: number[] }, base: number, output: string): { above: number; below: number; leaning: "worse" | "better" | "even" } {
  const below = shareBelow(h, base);
  const above = 1 - below;
  const better = OUTPUT_BETTER[output] ?? "lower";
  const worse = better === "lower" ? above : below;
  return { above, below, leaning: worse > 0.6 ? "worse" : worse < 0.4 ? "better" : "even" };
}
