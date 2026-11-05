// The inputs card's form (InputsCard) and the doublets' stop dates, as plain functions: the
// text in each field, what is wrong with it, what changed, and the answers that Run sends. The
// checks come in three levels (``checkCard``): what blocks the run (an empty box, not a number,
// outside the model's range, physically impossible), a warning (outside the challenge's caps or
// typical values: it still runs) and a note (what follows, what it is linked to). They mirror
// the server's (card_edits.py, stops.py), which has the last word: what it refuses comes back
// to the card on its field and nothing runs.

import type { CardContext, InputField, InputRow, InputToggle, RecordColumn } from "../agent/types";

export const YEAR = 2027;
export const DAYS = 365;
const DAY_MS = 86_400_000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** A field as typed: a number or a list of numbers as text, a choice, several options, or a
 * `records` field's boxes (one list of texts per record, in the columns' order). */
export type Draft = string | string[] | string[][];
type Value = InputField["value"];

const fmt = (x: number) => (Number.isFinite(x) ? String(Number(x.toPrecision(6))) : "");
const isOptions = (f: InputField) => f.kind === "list" && !!f.options?.length;
export const isRecords = (f: InputField) => f.kind === "records";

/** A number as the card says it: thousands with a comma, a minus sign. */
export const fmtNum = (x: number) => (Math.abs(x) >= 1000 ? Number(x.toPrecision(6)).toLocaleString("en-GB") : fmt(x)).replace(/^-/, "−");

/** A value in the form's units as the field's text. */
export function fieldText(f: InputField, v: Value): Draft {
  if (isRecords(f)) {
    const cols = f.columns ?? [];
    return (Array.isArray(v) ? v : []).map((r) => cols.map((c) => {
      const x = r && typeof r === "object" ? (r as Record<string, unknown>)[c.key] : undefined;
      return x == null || x === "" ? "" : fmt(Number(x));
    }));
  }
  if (isOptions(f)) return Array.isArray(v) ? v.map(String) : [];
  if (f.kind === "list") return Array.isArray(v) ? v.map((x) => fmt(Number(x))).join(", ") : "";
  if (f.kind === "choice") return v == null ? "" : String(v);
  return v == null || v === "" ? "" : fmt(Number(v));
}

/** Every field of the rows, in order. */
export function fieldsOf(rows: InputRow[]): InputField[] {
  return rows.flatMap((r) => r.fields ?? []);
}

/** The fields' text: the value now, or the value the server refused (in the form's units). */
export function initialDraft(rows: InputRow[], asked: Record<string, unknown> = {}): Record<string, Draft> {
  const out: Record<string, Draft> = {};
  for (const f of fieldsOf(rows)) {
    const raw = asked[f.key];
    const v = f.key in asked ? (f.kind === "number" && typeof raw === "number" ? raw * (f.scale ?? 1) : (raw as Value)) : f.value;
    out[f.key] = fieldText(f, v);
  }
  return out;
}

/** A number as typed ("5,2" is 5.2), or null. */
export function readNumber(text: string): number | null {
  const t = text.trim().replace(/\s+/g, "").replace(",", ".").replace("−", "-");
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(t)) return null;
  const x = Number(t);
  return Number.isFinite(x) ? x : null;
}

function readList(text: string): (number | null)[] {
  return text
    .split(/[;,\s]+/)
    .filter(Boolean)
    .map(readNumber);
}

/** The words for a number outside the model's range. */
function outside(x: number, low: number | undefined, high: number | undefined, unit: string): string | null {
  return (low != null && x < low - 1e-9) || (high != null && x > high + 1e-9) ? `Between ${fmt(low ?? x)} and ${fmt(high ?? x)}${unit}.` : null;
}

/**
 * May a records field's box be left empty? The first column (a record's identity, an aquifer's
 * depth) never; the others when the field gives a `new_item`: the server fills them (the known
 * aquifer's value, the pressure the brine column's at that depth: aquifers._filled).
 */
export const cellOptional = (f: InputField, j: number) => j > 0 && !!f.new_item;

/** What is wrong with one box of a `records` field, or null. */
export function cellProblem(c: RecordColumn, text: string, optional = false): string | null {
  if (!text.trim()) return optional ? null : "Required: give a value.";
  const x = readNumber(text);
  if (x == null) return "Give a number.";
  return outside(x, c.low, c.high, c.unit ? ` ${c.unit}` : "");
}

/** What is wrong with a field as typed, in plain words, or null. */
export function fieldProblem(f: InputField, d: Draft): string | null {
  if (f.kind === "choice") return (f.options ?? []).includes(String(d)) ? null : "Pick one of the options.";
  if (isOptions(f)) return (Array.isArray(d) ? (d as string[]) : []).every((x) => f.options!.includes(x)) ? null : "Pick from the options.";
  const unit = f.unit ? ` ${f.unit}` : "";
  if (isRecords(f)) {
    const recs = Array.isArray(d) ? (d as string[][]) : [];
    const what = (f.label || "record").toLowerCase().replace(/s$/, "");
    if (f.min_items != null && recs.length < f.min_items) return `Give at least ${f.min_items} ${what}${f.min_items === 1 ? "" : "s"}.`;
    if (f.max_items != null && recs.length > f.max_items) return `At most ${f.max_items} ${what}s.`;
    const cols = f.columns ?? [];
    for (let i = 0; i < recs.length; i++)
      for (let j = 0; j < cols.length; j++) {
        const bad = cellProblem(cols[j], recs[i]?.[j] ?? "", cellOptional(f, j));
        if (bad) return `${what[0].toUpperCase()}${what.slice(1)} ${i + 1}, ${cols[j].label.toLowerCase()}: ${bad[0].toLowerCase()}${bad.slice(1)}`;
      }
    return aquiferProblem(f, recs);
  }
  if (f.kind === "list") {
    const xs = readList(typeof d === "string" ? d : "");
    if (!xs.length) return "Required: give at least one depth.";
    if (xs.some((x) => x == null)) return "Give numbers, separated by commas.";
    for (const x of xs) {
      const bad = outside(x!, f.low, f.high, unit);
      if (bad) return bad;
    }
    return null;
  }
  const text = typeof d === "string" ? d : "";
  if (!text.trim()) return "Required: give a value.";
  const x = readNumber(text);
  if (x == null) return "Give a number.";
  if (f.whole && Math.abs(x - Math.round(x)) > 1e-9) return "Give a whole number.";
  return outside(x, f.low, f.high, unit);
}

// ------------------------------------------------------------------ the aquifers (records)
// The contract's columns (plan of 4 Nov): checked as the server checks them (aquifers.problems).

const LITHOSTATIC_BAR_PER_M = 0.23;
const HYDROSTATIC_SPREAD = 0.15;
const isAquifers = (f: InputField) => isRecords(f) && ["depth_m", "thickness_m", "pressure_bar"].every((k) => f.columns?.some((c) => c.key === k));

/** The aquifers as numbers by column (a box left empty: the server's fill, else null). */
function aquiferRows(f: InputField, recs: string[][], density = 1030): Record<string, number | null>[] {
  const cols = f.columns ?? [];
  const known = f.value && Array.isArray(f.value) ? (f.value[0] as Record<string, number | null> | undefined) : undefined;
  return recs.map((r) => {
    const out: Record<string, number | null> = Object.fromEntries(cols.map((c, j) => [c.key, readNumber(r[j] ?? "")]));
    for (const c of cols) {
      if (out[c.key] != null || c.key === "depth_m" || out.depth_m == null) continue;
      out[c.key] = c.key === "pressure_bar" ? (density * 9.81 * out.depth_m) / 1e5 : (f.new_item?.[c.key] ?? known?.[c.key] ?? null);
    }
    return out;
  });
}

/** What makes the aquifers unusable together (as aquifers.problems): near the surface, a pressure above the rock's weight, two overlapping. */
export function aquiferProblem(f: InputField, recs: string[][]): string | null {
  if (!isAquifers(f)) return null;
  const rows = aquiferRows(f, recs);
  for (let n = 0; n < rows.length; n++) {
    const { depth_m: d, thickness_m: h, pressure_bar: p } = rows[n];
    if (d == null || h == null) continue;
    if (d - h / 2 < 100) return `Aquifer ${n + 1}, thickness: ${fmt(h)} m around ${fmtNum(d)} m would reach within 100 m of the surface.`;
    if (p != null && p > LITHOSTATIC_BAR_PER_M * d) return `Aquifer ${n + 1}, pressure: ${fmt(p)} bar at ${fmtNum(d)} m is more than the rock above it weighs (about ${fmtNum(Math.round(LITHOSTATIC_BAR_PER_M * d))} bar).`;
  }
  const order = rows.map((r, i) => [r, i] as const).filter(([r]) => r.depth_m != null && r.thickness_m != null).sort((a, b) => a[0].depth_m! - b[0].depth_m!);
  for (let k = 1; k < order.length; k++) {
    const [a, i] = order[k - 1];
    const [b, j] = order[k];
    if (b.depth_m! - a.depth_m! < (a.thickness_m! + b.thickness_m!) / 2)
      return `Aquifers ${Math.min(i, j) + 1} and ${Math.max(i, j) + 1} overlap (${fmtNum(a.depth_m!)} m and ${fmtNum(b.depth_m!)} m): give them depths further apart, or thinner layers.`;
  }
  return null;
}

/** Warnings on the aquifers as typed (as aquifers.problems): a pressure far from the brine column's. */
export function aquiferWarnings(f: InputField, recs: string[][], density = 1030): string[] {
  if (!isAquifers(f)) return [];
  const typed = aquiferRows(f, recs.map((r) => r.map((t) => t)), density);
  return typed.flatMap((r, n) => {
    const given = readNumber(recs[n]?.[(f.columns ?? []).findIndex((c) => c.key === "pressure_bar")] ?? "");
    if (r.depth_m == null || given == null) return [];
    const column = (density * 9.81 * r.depth_m) / 1e5;
    if (Math.abs(given - column) <= HYDROSTATIC_SPREAD * column) return [];
    return [`Aquifer ${n + 1}: ${fmt(given)} bar is ${Math.round((Math.abs(given - column) / column) * 100)} % ${given > column ? "above" : "below"} the brine column's ${fmtNum(Math.round(column))} bar at ${fmtNum(r.depth_m)} m; possible, but rare in Dutch aquifers.`];
  });
}

/**
 * The warnings the old Aquifer boxes had, on each aquifer as typed (as the server's
 * card_edits.record_warnings): rock too tight to flow, else each value outside its typical
 * values; the same words for several aquifers said once.
 */
export function recordWarnings(f: InputField, recs: string[][]): string[] {
  if (!isRecords(f)) return [];
  const cols = f.columns ?? [];
  const rows = isAquifers(f) ? aquiferRows(f, recs) : recs.map((r) => Object.fromEntries(cols.map((c, j) => [c.key, readNumber(r[j] ?? "")])));
  const said = new Map<string, number[]>();
  const put = (words: string, n: number) => said.set(words, [...(said.get(words) ?? []), n]);
  rows.forEach((r, i) => {
    const k = r.permeability_md;
    const h = r.thickness_m;
    const tight = k != null && h != null ? tightRock({ permeability_md: k, reservoir_thickness_m: h }) : null;
    if (tight) put(`: ${tight[0].toLowerCase()}${tight.slice(1)}`, i + 1);
    for (const c of cols) {
      const x = r[c.key];
      if (!c.typical || x == null || (tight && c.key === "permeability_md")) continue;
      if (x < c.typical[0] - 1e-9 || x > c.typical[1] + 1e-9) put(`, ${c.label.toLowerCase()}: outside the typical ${fmtNum(c.typical[0])} to ${fmtNum(c.typical[1])}${c.unit ? ` ${c.unit}` : ""}: check it is right.`, i + 1);
    }
  });
  const numbered = (ns: number[]) => (ns.length === 1 ? `Aquifer ${ns[0]}` : `Aquifers ${ns.slice(0, -1).join(", ")} and ${ns[ns.length - 1]}`);
  return [...said].map(([words, ns]) => numbered(ns) + words);
}

/** A records field's value in words: "3 aquifers: 2,500 m (known), 3,000 m and 3,500 m". */
export function recordsWords(f: InputField, d: Draft): string {
  const recs = Array.isArray(d) ? (d as string[][]) : [];
  const what = (f.label || "record").toLowerCase().replace(/s$/, "");
  const first = f.columns?.[0];
  const items = recs.map((r, i) => {
    const x = readNumber(r?.[0] ?? "");
    const v = x == null ? "?" : `${fmtNum(x)}${first?.unit ? ` ${first.unit}` : ""}`;
    return f.kinds?.[i] === "known" && i === 0 ? `${v} (known)` : v;
  });
  const list = items.length > 1 ? `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}` : (items[0] ?? "none");
  return `${recs.length} ${what}${recs.length === 1 ? "" : "s"}: ${list}`;
}

/** What changed in a records field, one line per record: a value, a record added or removed. */
export function recordsChanges(f: InputField, d: Draft): { label: string; was: string; now: string }[] {
  const now = Array.isArray(d) ? (d as string[][]) : [];
  const was = fieldText(f, f.value) as string[][];
  const cols = f.columns ?? [];
  const what = (f.label || "record").replace(/s$/, "");
  const cell = (t: string, j: number) => (t.trim() ? `${fmtNum(readNumber(t) ?? NaN) || t}${cols[j]?.unit ? ` ${cols[j].unit}` : ""}` : "auto");
  // Same count: by place. Otherwise matched by the first column (an aquifer's depth).
  const pairs: [number | null, number | null][] = [];
  if (now.length === was.length) now.forEach((_, i) => pairs.push([i, i]));
  else {
    const free = new Set(was.map((_, i) => i));
    now.forEach((r, i) => {
      const k = [...free].find((w) => (was[w][0] ?? "").trim() === (r[0] ?? "").trim());
      if (k != null) free.delete(k);
      pairs.push([k ?? null, i]);
    });
    for (const k of free) pairs.push([k, null]);
  }
  const out: { label: string; was: string; now: string }[] = [];
  for (const [w, n] of pairs) {
    if (w == null && n != null) out.push({ label: `${what} ${n + 1}`, was: "none", now: `added at ${cell(now[n][0] ?? "", 0)}` });
    else if (n == null && w != null) out.push({ label: `${what} ${w + 1}`, was: cell(was[w][0] ?? "", 0), now: "removed" });
    else if (w != null && n != null)
      cols.forEach((c, j) => {
        const a = was[w][j] ?? "";
        const b = now[n][j] ?? "";
        const x = readNumber(a);
        const y = readNumber(b);
        if (x == null || y == null ? a.trim() !== b.trim() : Math.abs(x - y) > 1e-9) out.push({ label: `${what} ${n + 1} · ${c.label.toLowerCase()}`, was: cell(a, j), now: cell(b, j) });
      });
  }
  return out;
}

/** The value a field stands for, in the server's units (the form's ÷ scale); undefined when not valid. */
export function fieldValue(f: InputField, d: Draft): number | string | (number | string)[] | Record<string, number | null>[] | undefined {
  if (fieldProblem(f, d)) return undefined;
  if (f.kind === "choice") return String(d);
  if (isOptions(f)) return [...(d as string[])];
  // An empty box goes as null: the server fills it (cellOptional).
  if (isRecords(f)) return (d as string[][]).map((r) => Object.fromEntries((f.columns ?? []).map((c, j) => [c.key, readNumber(r[j] ?? "") as number])));
  if (f.kind === "list") return readList(d as string).map((x) => x!);
  const x = readNumber(d as string)!;
  return f.scale ? Number((x / f.scale).toPrecision(12)) : x;
}

/** A number as typed in the form's units (no ÷ scale), or null. */
export function formNumber(f: InputField | undefined, d: Draft | undefined): number | null {
  if (!f || typeof d !== "string" || f.kind !== "number") return null;
  return readNumber(d);
}

/** True when two texts of a field stand for different values (numbers compared as numbers). */
export function draftsDiffer(f: InputField, d: Draft, now: Draft): boolean {
  if (isRecords(f)) {
    const a = d as string[][];
    const b = now as string[][];
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return true;
    return a.some((r, i) => r.some((t, j) => {
      const x = readNumber(t);
      const y = readNumber(b[i]?.[j] ?? "");
      return x == null || y == null ? t.trim() !== (b[i]?.[j] ?? "").trim() : Math.abs(x - y) > 1e-9;
    }));
  }
  if (isOptions(f)) return [...((d as string[]) ?? [])].sort().join("|") !== [...((now as string[]) ?? [])].sort().join("|");
  if (f.kind === "choice") return String(d) !== String(now);
  if (f.kind === "list") {
    const a = readList(d as string);
    const b = readList(now as string);
    return a.length !== b.length || a.some((x, i) => x == null || Math.abs(x - (b[i] ?? NaN)) > 1e-9);
  }
  const x = readNumber(d as string);
  const y = readNumber(now as string);
  return x == null || y == null ? String(d).trim() !== String(now).trim() : Math.abs(x - y) > 1e-9;
}

/** True when the field as typed differs from the value now. */
export function fieldChanged(f: InputField, d: Draft): boolean {
  return draftsDiffer(f, d, fieldText(f, f.value));
}

// ------------------------------------------------------------------ the project's defaults (5 Nov)
// Each field carries the project's own value (`default`): a value that differs is marked and can
// be put back on its own; "Reset to defaults" asks the server to put back every input.

/** True when the server sent the field's default (older servers did not). */
export const hasDefault = (f: InputField) => f.default !== undefined;

/** The field's default as its text. */
export function defaultDraft(f: InputField): Draft {
  return fieldText(f, f.default ?? null);
}

/** True when the field as typed is not the project's own value. */
export function differsFromDefault(f: InputField, d: Draft): boolean {
  return hasDefault(f) && draftsDiffer(f, d, defaultDraft(f));
}

/** The keys of the fields whose value, as typed, is not the project's own. */
export function offDefaultKeys(rows: InputRow[], draft: Record<string, Draft>): string[] {
  return fieldsOf(rows)
    .filter((f) => differsFromDefault(f, f.key in draft ? draft[f.key] : fieldText(f, f.value)))
    .map((f) => f.key);
}

/** The default in words, as the field shows a value ("60 °C", "1 to 3 (the search picks)"). */
export function defaultWords(f: InputField): string {
  const t = defaultDraft(f);
  if (isRecords(f)) return recordsWords(f, t);
  if (f.kind === "choice") return f.words?.[String(t)] ?? String(t);
  if (Array.isArray(t)) return (t as string[]).map((x) => f.words?.[x] ?? x).join(", ") || "none";
  return `${t || "empty"}${t && f.unit ? ` ${f.unit}` : ""}`;
}

/**
 * Whether "Reset to defaults" has anything to put back: a box typed away from its default, a
 * switch or the Maintenance section changed on the card, or the server's inputs not at the
 * project's own (`at_defaults` false: a value from the message, or one no box shows).
 */
export function canReset(rows: InputRow[], draft: Record<string, Draft>, atDefaults: boolean | undefined, switchesChanged = false): boolean {
  return atDefaults === false || switchesChanged || offDefaultKeys(rows, draft).length > 0;
}

/** The keys of the fields that changed. */
export function changedKeys(rows: InputRow[], draft: Record<string, Draft>): string[] {
  return fieldsOf(rows)
    .filter((f) => f.key in draft && fieldChanged(f, draft[f.key]))
    .map((f) => f.key);
}

/** Each field's value in the server's units, as typed (the value now where a box is not valid). */
function valuesOf(rows: InputRow[], draft: Record<string, Draft>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const f of fieldsOf(rows)) {
    if (f.kind !== "number") continue;
    const v = f.key in draft ? fieldValue(f, draft[f.key]) : undefined;
    const now = typeof f.value === "number" ? f.value / (f.scale ?? 1) : undefined;
    const x = typeof v === "number" ? v : now;
    if (x != null) out[f.key] = x;
  }
  return out;
}

/** Rock over the aquifer (about 2,300 kg/m³): a pore pressure above its weight would crack it. */
export const ROCK_BAR_PER_M = (2300 * 9.81) / 1e5;

/**
 * What is physically impossible in a set of values (server units), by key; a pair's message on
 * both its keys. The same as the server's ``card_edits.impossible``: these block the run.
 */
export function impossible(v: Record<string, number>, depthM = 2500): Record<string, string> {
  const out: Record<string, string> = {};
  const has = (...k: string[]) => k.every((x) => typeof v[x] === "number" && Number.isFinite(v[x]));
  if (has("heat_supply_c", "heat_return_c") && v.heat_return_c >= v.heat_supply_c) {
    out.heat_return_c = `The return must be below the supply (${fmt(v.heat_supply_c)} °C): the water comes back cooler than it left.`;
    out.heat_supply_c = `The supply must be above the return (${fmt(v.heat_return_c)} °C).`;
  }
  if (has("cool_supply_c", "cool_return_c") && v.cool_return_c <= v.cool_supply_c) {
    out.cool_return_c = `The return must be above the supply (${fmt(v.cool_supply_c)} °C): the water warms up in the buildings.`;
    out.cool_supply_c = `The supply must be below the return (${fmt(v.cool_return_c)} °C).`;
  }
  if (has("flow_min_m3h", "flow_max_m3h") && v.flow_min_m3h > v.flow_max_m3h) {
    out.flow_min_m3h = `The lowest flow can't be above the flow cap (${fmt(v.flow_max_m3h)} m³/h).`;
    out.flow_max_m3h = `The flow cap can't be below the lowest flow (${fmt(v.flow_min_m3h)} m³/h).`;
  }
  if (has("pump_efficiency") && v.pump_efficiency >= 1) out.pump_efficiency = "No pump turns all its electricity into lift: give less than 100 %.";
  if (has("gas_ch4_fraction", "gas_co2_fraction") && v.gas_ch4_fraction + v.gas_co2_fraction > 1 + 1e-9) {
    out.gas_ch4_fraction = out.gas_co2_fraction = `Methane and CO₂ make ${fmt((v.gas_ch4_fraction + v.gas_co2_fraction) * 100)} % of the gas: more than all of it.`;
  }
  const rock = ROCK_BAR_PER_M * depthM;
  if (has("reservoir_pressure_bar") && v.reservoir_pressure_bar > rock) {
    out.reservoir_pressure_bar = `More than the weight of the rock above the aquifer (about ${Math.round(rock)} bar at ${fmtNum(depthM)} m): the rock would crack open.`;
  }
  return out;
}

/** A warning for a number as typed (form units): outside the challenge's cap, else its typical values. */
export function fieldWarning(f: InputField, x: number | null): string | null {
  if (x == null || f.kind !== "number") return null;
  const cap = f.cap;
  if (cap && ((cap.low != null && x < cap.low - 1e-9) || (cap.high != null && x > cap.high + 1e-9))) return `${cap.words ?? "Outside the challenge's caps"}: the design will not meet the challenge.`;
  const t = f.typical;
  if (t && (x < t[0] - 1e-9 || x > t[1] + 1e-9)) return `Outside the typical ${fmtNum(t[0])} to ${fmtNum(t[1])}${f.unit ? ` ${f.unit}` : ""}: check it is right.`;
  return null;
}

/** Below this permeability × thickness (D·m) the wells barely flow (card_edits.TIGHT_DM). */
export const TIGHT_DM = 2;

/** A warning when the rock is too tight for a doublet (as the server's card_edits.tight_rock). */
export function tightRock(v: Record<string, number>): string | null {
  const k = v.permeability_md;
  const h = v.reservoir_thickness_m;
  if (k == null || h == null || (k * h) / 1000 >= TIGHT_DM) return null;
  return `The rock lets very little brine through (k × h = ${Number(((k * h) / 1000).toPrecision(2))} D·m; a doublet needs a few): the search may find no design, and below about 0.5 D·m the plant can't be balanced at all.`;
}

/** What blocks the run, by key: each field as typed, and the pairs that are impossible together. */
export function draftProblems(rows: InputRow[], draft: Record<string, Draft>, depthM = 2500): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of fieldsOf(rows)) {
    if (!(f.key in draft)) continue;
    const bad = fieldProblem(f, draft[f.key]);
    if (bad) out[f.key] = bad;
  }
  const values = valuesOf(rows, draft);
  for (const [k, why] of Object.entries(impossible(values, depthM))) if (!out[k] && fieldsOf(rows).some((f) => f.key === k)) out[k] = why;
  return out;
}

export type Level = "block" | "warn" | "note";
export interface Issue {
  level: Level;
  text: string;
}

/** The production temperature (°C) for values in server units: surface + change + gradient × depth. */
export function productionC(v: Record<string, number>, ctx: CardContext): number | null {
  if (ctx.surface_c == null || ctx.depth_m == null || v.gradient_c_per_km == null) return null;
  return ctx.surface_c + (v.reservoir_change_k ?? 0) + (v.gradient_c_per_km * ctx.depth_m) / 1000;
}

const r0 = (x: number) => fmtNum(Math.round(x));
const r1 = (x: number) => fmtNum(Math.round(x * 10) / 10);
const r2 = (x: number) => fmtNum(Math.round(x * 100) / 100);

/**
 * What follows from the values as typed (server units), by key: the production temperature
 * from the gradient, the injection floor from the cooling cap, hydrostatic pressure, one
 * doublet's heat at the cap, the demand scaled. Cheap sums for the card's notes.
 */
export function consequences(v: Record<string, number>, ctx: CardContext): Record<string, string> {
  const out: Record<string, string> = {};
  const t = productionC(v, ctx);
  const depthKm = (ctx.depth_m ?? 0) / 1000;
  if (t != null) {
    const change = v.reservoir_change_k ? ` ${v.reservoir_change_k > 0 ? "+" : "−"} ${fmt(Math.abs(v.reservoir_change_k))}` : "";
    const words = `Brine at the producer: ${fmt(ctx.surface_c!)} + ${fmt(v.gradient_c_per_km)} °C/km × ${fmt(depthKm)} km${change} = ${r0(t)} °C.`;
    out.gradient_c_per_km = words;
    out.reservoir_change_k = words;
    if (v.max_brine_cooling_k != null) out.max_brine_cooling_k = `Injected at ${r0(t - v.max_brine_cooling_k)} °C or warmer (${r0(t)} − ${fmt(v.max_brine_cooling_k)}).`;
    if (v.heat_supply_c != null && t - 2 < v.heat_supply_c) out.heat_supply_c = `The brine (${r0(t)} °C) is cooler than this supply: a heat pump or the boiler lifts the rest.`;
    else if (v.heat_supply_c != null) out.heat_supply_c = `The brine (${r0(t)} °C) is hot enough for this supply through the heat exchanger alone.`;
  }
  if (v.operating_days != null) {
    const off = Math.max(0, DAYS - Math.round(v.operating_days));
    out.operating_days = `Each doublet is off ${off} day${off === 1 ? "" : "s"} a year; set when under Maintenance.`;
  }
  if (v.reservoir_pressure_bar != null && ctx.depth_m) {
    const rho = v.brine_density_kg_m3 ?? 1030;
    const hydro = 1.01325 + (rho * 9.81 * ctx.depth_m) / 1e5;
    out.reservoir_pressure_bar = `Hydrostatic at ${fmtNum(ctx.depth_m)} m: about ${r0(hydro)} bar (${Math.round((v.reservoir_pressure_bar / hydro) * 100)} % of it).`;
  }
  if (v.permeability_md != null && v.reservoir_thickness_m != null) {
    const kh = (v.permeability_md * v.reservoir_thickness_m) / 1000;
    const words = `Transmissivity k × h = ${r1(kh)} D·m${kh < 5 ? ": low for a doublet" : kh >= 10 ? ": good for a doublet" : ""}.`;
    out.permeability_md = words;
  }
  if (v.flow_max_m3h != null && v.max_brine_cooling_k != null) {
    const mw = ((v.flow_max_m3h / 3600) * (v.brine_density_kg_m3 ?? 1030) * (v.brine_cp_j_kg_k ?? 3990) * v.max_brine_cooling_k) / 1e6;
    out.flow_max_m3h = `One doublet at the cap, its brine cooled ${fmt(v.max_brine_cooling_k)} K: about ${r1(mw)} MW of heat.`;
    if (v.brine_cp_j_kg_k != null) out.brine_cp_j_kg_k = `One doublet at ${fmt(v.flow_max_m3h)} m³/h cooled ${fmt(v.max_brine_cooling_k)} K: about ${r1(mw)} MW.`;
    if (v.brine_density_kg_m3 != null) out.brine_density_kg_m3 = out.brine_cp_j_kg_k ?? "";
  }
  if (v.gas_liquid_ratio != null && v.flow_max_m3h != null) {
    const gas = v.gas_liquid_ratio * v.flow_max_m3h;
    const ch4 = gas * (v.gas_ch4_fraction ?? 0.8);
    out.gas_liquid_ratio = `At ${fmt(v.flow_max_m3h)} m³/h: ${r0(gas)} Nm³/h of gas, ${r0(ch4)} of it methane (about ${r1((ch4 * 35.8) / 3600)} MW of fuel for the boiler).`;
  }
  if (v.heat_demand_scale != null && ctx.heat_gwh != null) out.heat_demand_scale = `${fmtNum(ctx.heat_gwh)} GWh × ${fmt(v.heat_demand_scale)} = ${r2(ctx.heat_gwh * v.heat_demand_scale)} GWh a year, peak ${r1((ctx.heat_peak_mw ?? 0) * v.heat_demand_scale)} MW.`;
  if (v.cool_demand_scale != null && ctx.cool_gwh) out.cool_demand_scale = `${fmtNum(ctx.cool_gwh)} GWh × ${fmt(v.cool_demand_scale)} = ${r2(ctx.cool_gwh * v.cool_demand_scale)} GWh a year, peak ${r1((ctx.cool_peak_mw ?? 0) * v.cool_demand_scale)} MW.`;
  for (const k of Object.keys(out)) if (!out[k]) delete out[k];
  return out;
}

/** The review's figures: what the values as typed give, each with its icon. */
export function followTiles(v: Record<string, number>, ctx: CardContext): { icon: string; tint: string; value: string; label: string }[] {
  const out: { icon: string; tint: string; value: string; label: string }[] = [];
  const t = productionC(v, ctx);
  if (t != null) out.push({ icon: "thermo", tint: "heat", value: `${r0(t)} °C`, label: "brine at the producer" });
  if (t != null && v.max_brine_cooling_k != null) out.push({ icon: "well", tint: "cold", value: `≥ ${r0(t - v.max_brine_cooling_k)} °C`, label: "injected back" });
  if (v.flow_max_m3h != null && v.max_brine_cooling_k != null) {
    const mw = ((v.flow_max_m3h / 3600) * (v.brine_density_kg_m3 ?? 1030) * (v.brine_cp_j_kg_k ?? 3990) * v.max_brine_cooling_k) / 1e6;
    out.push({ icon: "flow", tint: "violet", value: `${r1(mw)} MW`, label: "from one doublet at the cap" });
  }
  if (v.operating_days != null) out.push({ icon: "calendar", tint: "violet", value: `${Math.max(0, DAYS - Math.round(v.operating_days))} days`, label: "off for each doublet" });
  return out;
}

/**
 * Every field's issues as typed, by key, most serious first: what blocks the run (with the
 * server's refusals not edited since), a warning, and a note (what follows, else what it is
 * linked to). ``serverErrors``: the server's reasons, shown until the box is edited.
 */
export function checkCard(rows: InputRow[], draft: Record<string, Draft>, ctx: CardContext = {}, serverErrors: Record<string, string> = {}): Record<string, Issue[]> {
  const out: Record<string, Issue[]> = {};
  const blocks = draftProblems(rows, draft, ctx.depth_m ?? 2500);
  const values = valuesOf(rows, draft);
  const follows = consequences(values, ctx);
  for (const f of fieldsOf(rows)) {
    const list: Issue[] = [];
    const block = blocks[f.key] ?? serverErrors[f.key];
    if (block) list.push({ level: "block", text: block });
    else if (isRecords(f)) {
      // The server's warnings on the records as they are; as typed, the same rule worked out here.
      const d = draft[f.key] as string[][] | undefined;
      const typed = d ?? (fieldText(f, f.value) as string[][]);
      const warns = [...recordWarnings(f, typed), ...(d && fieldChanged(f, d) ? aquiferWarnings(f, d, values.brine_density_kg_m3 ?? 1030) : (f.warnings ?? []))];
      for (const w of warns) list.push({ level: "warn", text: w });
    } else {
      // Rock too tight to flow says more than "outside the typical values".
      const warn = (f.key === "permeability_md" ? tightRock(values) : null) ?? fieldWarning(f, formNumber(f, draft[f.key]));
      if (warn) list.push({ level: "warn", text: warn });
    }
    // What follows, worked out as it is typed (what it is linked to is behind "more").
    const note = follows[f.key];
    if (note) list.push({ level: "note", text: note });
    if (list.length) out[f.key] = list;
  }
  return out;
}

/** Warnings for the switches as set: a seasonal store needs a store size. */
export function toggleWarnings(state: Record<string, { on: boolean; text: string }>): Record<string, string> {
  const out: Record<string, string> = {};
  if (state.storage_ates?.on && !(state.storage_mwh?.on && Number(state.storage_mwh.text.replace(",", ".")) > 0))
    out.storage_ates = "A seasonal store needs a size: switch on the heat store and give its MWh, or this does nothing.";
  return out;
}

/** The changes Run sends: each changed field's value, in the server's units. */
export function changesOf(rows: InputRow[], draft: Record<string, Draft>): Record<string, unknown> {
  const fields = new Map(fieldsOf(rows).map((f) => [f.key, f]));
  const out: Record<string, unknown> = {};
  for (const key of changedKeys(rows, draft)) {
    const v = fieldValue(fields.get(key)!, draft[key]);
    if (v !== undefined) out[key] = v;
  }
  return out;
}

// ------------------------------------------------------------------ the doublets' stops

/** One date range of a doublet's stops, as the date inputs hold it ("2027-07-09"). */
export interface StopRange {
  from: string;
  to: string;
}

/** One doublet's stops: one block from a start date, or several ranges. */
export interface DoubletStops {
  kind: "block" | "ranges";
  start: string;
  ranges: StopRange[];
}

/** Dioscuri's weeks ("quiet"), or the user's dates for every doublet ("mine"). */
export interface StopsState {
  mode: "quiet" | "mine";
  doublets: DoubletStops[];
}

const JAN1 = Date.UTC(YEAR, 0, 1);

/** A 0-based day of the year as an input's date, "2027-07-09". */
export function dateOf(day: number): string {
  return new Date(JAN1 + day * DAY_MS).toISOString().slice(0, 10);
}

/** An input's date as a 0-based day of 2027 (outside the year: below 0 or above 364), or null. */
export function dayOf(date: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date ?? "");
  if (!m) return null;
  const day = Math.round((Date.UTC(+m[1], +m[2] - 1, +m[3]) - JAN1) / DAY_MS);
  return dateOf(day) === date ? day : null;
}

/** A 0-based day as "9 Jul". */
export function dayName(day: number): string {
  const d = new Date(JAN1 + day * DAY_MS);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** The days off each doublet needs: 365 − the operating days. */
export const daysOff = (operatingDays: number) => Math.max(0, DAYS - Math.round(operatingDays));

/**
 * The stop editor as the card opens: the user's dates (those the server refused, else those it
 * runs with), else Dioscuri's suggestion to start from.
 */
export function initialStops(t: InputToggle, refused?: unknown): StopsState {
  const off = daysOff(t.operating_days ?? 330);
  const n = Math.max(1, Math.min(3, t.doublets ?? 3));
  const given = isStops(refused) ? refused : (t.stops ?? []);
  const doublets = Array.from({ length: n }, (_, k): DoubletStops => {
    const mine = given[k];
    if (mine?.length) {
      const one = mine.length === 1 && mine[0][1] - mine[0][0] + 1 === off;
      return { kind: one ? "block" : "ranges", start: dateOf(mine[0][0]), ranges: mine.map(([a, b]) => ({ from: dateOf(a), to: dateOf(b) })) };
    }
    const s = t.suggested?.[k]?.[0]?.[0] ?? Math.min(DAYS - off, 150 + k * off);
    return { kind: "block", start: dateOf(s), ranges: [{ from: dateOf(s), to: dateOf(Math.min(DAYS - 1, s + Math.max(off, 1) - 1)) }] };
  });
  return { mode: given.some((g) => g?.length) ? "mine" : "quiet", doublets };
}

function isStops(v: unknown): v is number[][][] {
  return Array.isArray(v) && v.every((d) => Array.isArray(d) && d.every((r) => Array.isArray(r) && r.length === 2 && r.every((x) => typeof x === "number")));
}

/** One doublet's stops as [first, last] days (0-based); null where a date is missing. */
export function rangesOf(d: DoubletStops, off: number): ([number, number] | null)[] {
  if (d.kind === "block") {
    const s = dayOf(d.start);
    return [s == null ? null : [s, s + off - 1]];
  }
  return d.ranges.map((r) => {
    const a = dayOf(r.from);
    const b = dayOf(r.to);
    return a == null || b == null ? null : [a, b];
  });
}

/** How many days one doublet's valid ranges take. */
export function daysOf(ranges: ([number, number] | null)[]): number {
  return ranges.reduce((n, r) => n + (r ? Math.max(0, r[1] - r[0] + 1) : 0), 0);
}

/**
 * What is wrong with one doublet's dates, or null: in 2027, in order, no overlap. ``block``: the
 * doublet's own days off for one block (else the cap's). Fewer days off than the cap leaves is no
 * problem with the Maintenance section (``relaxed``): the cap is relaxed, and the card says so.
 */
export function doubletProblem(d: DoubletStops, operatingDays: number, block?: number, relaxed = false): string | null {
  const off = block ?? daysOff(operatingDays);
  if (d.kind === "block" && off === 0) return `At ${operatingDays} days no stop is needed: give ranges, or let Dioscuri choose.`;
  const rs = rangesOf(d, off);
  if (!rs.length) return "Add a range.";
  if (rs.some((r) => r == null)) return "Pick a date for every range.";
  const ranges = (rs as [number, number][]).slice().sort((x, y) => x[0] - y[0]);
  for (const [a, b] of ranges) {
    if (d.kind === "block" && b > DAYS - 1) return `The stop must end by 31 Dec: start by ${dayName(DAYS - off)}.`;
    if (a < 0 || b > DAYS - 1) return `Keep every date in ${YEAR}.`;
    if (a > b) return "A range ends before it starts.";
  }
  for (let i = 1; i < ranges.length; i++) {
    if (ranges[i][0] <= ranges[i - 1][1]) return `${dayName(ranges[i - 1][0])} to ${dayName(ranges[i - 1][1])} and ${dayName(ranges[i][0])} to ${dayName(ranges[i][1])} overlap.`;
  }
  const total = daysOf(ranges);
  const need = daysOff(operatingDays);
  if (!relaxed && total < need) return `${total} of ${need} days off: the ${operatingDays}-day cap needs ${need - total} more.`;
  return null;
}

/** Each doublet's problem (all null with Dioscuri's weeks). */
export function stopsProblems(s: StopsState, operatingDays: number, blocks?: number[], relaxed = false): (string | null)[] {
  return s.doublets.map((d, k) => (s.mode === "quiet" ? null : doubletProblem(d, operatingDays, blocks?.[k], relaxed)));
}

/** Days two doublets are off together, in words (a note, not a problem: the boiler covers them). */
export function stopsTogether(s: StopsState, operatingDays: number): string | null {
  if (s.mode === "quiet") return null;
  const off = daysOff(operatingDays);
  const sets = s.doublets.map((d) => {
    const days = new Set<number>();
    for (const r of rangesOf(d, off)) if (r) for (let i = r[0]; i <= r[1]; i++) days.add(i);
    return days;
  });
  const notes: string[] = [];
  for (let a = 0; a < sets.length; a++)
    for (let b = a + 1; b < sets.length; b++) {
      const n = [...sets[a]].filter((i) => sets[b].has(i)).length;
      if (n) notes.push(`doublets ${a + 1} and ${b + 1} are both off on ${n} day${n === 1 ? "" : "s"}`);
    }
  return notes.length ? `${notes.join("; ")}: the other units cover those days.` : null;
}

/** The answer: "[]" for Dioscuri's weeks, else every doublet's [first, last] ranges, in order. */
export function stopsAnswer(s: StopsState, operatingDays: number, blocks?: number[]): string {
  if (s.mode === "quiet") return "[]";
  const off = daysOff(operatingDays);
  return JSON.stringify(s.doublets.map((d, k) => (rangesOf(d, blocks?.[k] ?? off).filter(Boolean) as [number, number][]).sort((x, y) => x[0] - y[0])));
}

/** The operating days the stops are checked against: the form's when changed and valid. */
export function operatingDaysOf(rows: InputRow[], draft: Record<string, Draft>, fallback: number): number {
  const f = fieldsOf(rows).find((x) => x.key === "operating_days");
  if (!f || !(f.key in draft)) return fallback;
  const v = fieldValue(f, draft[f.key]);
  return typeof v === "number" ? Math.round(v) : fallback;
}

// ------------------------------------------------------------------ maintenance (2 Nov)

/** A unit type's yearly service on the card: off, Dioscuri's quietest weeks, or the user's dates. */
export type ServiceMode = "off" | "auto" | "dates";

export interface ServiceUnit {
  unit: string;
  label: string;
  /** Days a service takes when Dioscuri picks the weeks. */
  days: number;
  /** Several equal units (a boiler or chiller bank): each date range takes one of them out. */
  bank: boolean;
  mode: ServiceMode;
  ranges: StopRange[];
}

/** The Maintenance section as the card opens: each doublet's days off, each unit's service. */
export interface MaintenanceState {
  daysOff: string[];
  units: ServiceUnit[];
}

const rangeOf = ([a, b]: number[]): StopRange => ({ from: dateOf(a), to: dateOf(b) });

export function initialMaintenance(t: InputToggle): MaintenanceState {
  const n = Math.max(1, Math.min(3, t.doublets ?? 3));
  const def = t.default_days_off ?? daysOff(t.operating_days ?? 330);
  const days = Array.from({ length: n }, (_, k) => String(t.days_off?.[k] ?? def));
  const units = (t.units ?? []).map((u) => ({ ...u, mode: (["off", "auto", "dates"].includes(u.mode) ? u.mode : "off") as ServiceMode, ranges: (u.ranges ?? []).map(rangeOf) }));
  return { daysOff: days, units };
}

/** The doublets the card's Maintenance lists: the count typed on the card ("Doublets" 1 to 3),
 * else the count the card opened with. "1 to 3" (empty) keeps all three (2 Nov: one doublet
 * typed in, Maintenance still asked for three). */
export function doubletCount(draft: Record<string, Draft>, editing: boolean, opened: number): number {
  const raw = editing ? draft.n_doublets : undefined;
  const n = typeof raw === "string" && /^\s*[123]\s*$/.test(raw) ? Number(raw) : opened;
  return Math.max(1, Math.min(3, n));
}

/** The stops for ``n`` doublets: the first ``n`` kept, new ones from Dioscuri's suggestion. */
export function stopsFor(s: StopsState, n: number, t: InputToggle): StopsState {
  if (s.doublets.length === n) return s;
  const fresh = initialStops({ ...t, doublets: n, stops: [] });
  return { ...s, doublets: Array.from({ length: n }, (_, k) => s.doublets[k] ?? fresh.doublets[k]) };
}

/** The days off for ``n`` doublets: the first ``n`` kept, new ones at the default. */
export function maintenanceFor(m: MaintenanceState, n: number, t: InputToggle): MaintenanceState {
  if (m.daysOff.length === n) return m;
  const def = String(t.default_days_off ?? daysOff(t.operating_days ?? 330));
  return { ...m, daysOff: Array.from({ length: n }, (_, k) => m.daysOff[k] ?? def) };
}

/** A doublet's days off as a whole number, or null when it can't be read. */
export function daysOffOf(text: string): number | null {
  const t = text.trim();
  if (!/^\d{1,3}$/.test(t)) return null;
  const v = Number(t);
  return v >= 1 && v <= DAYS - 100 ? v : null;
}

/** What is wrong with a doublet's days off, or null. */
export function daysOffProblem(text: string): string | null {
  return daysOffOf(text) == null ? `A whole number of days, 1 to ${DAYS - 100}.` : null;
}

/** A note (not a problem) when a doublet is off fewer days than the cap leaves: it is relaxed. */
export function relaxedNote(days: number, def: number, operatingDays: number): string | null {
  return days < def ? `Fewer than ${def}: the doublet may run ${DAYS - days} days, more than the ${operatingDays}-day cap. The cap is relaxed for this design, and every design says it is outside the challenge's cap.` : null;
}

/** What is wrong with a unit's dates, or null: each range in the year, in order, none overlapping. */
export function serviceProblem(u: ServiceUnit): string | null {
  if (u.mode !== "dates") return null;
  if (!u.ranges.length) return "Add a range, or let Dioscuri pick the weeks.";
  const rs: [number, number][] = [];
  for (const r of u.ranges) {
    const a = dayOf(r.from);
    const b = dayOf(r.to);
    if (a == null || b == null) return "Pick a date for every range.";
    if (a < 0 || b > DAYS - 1) return `Keep every date in ${YEAR}.`;
    if (a > b) return "A range ends before it starts.";
    rs.push([a, b]);
  }
  rs.sort((x, y) => x[0] - y[0]);
  for (let i = 1; i < rs.length; i++) if (rs[i][0] <= rs[i - 1][1]) return `${dayName(rs[i - 1][0])} to ${dayName(rs[i - 1][1])} and ${dayName(rs[i][0])} to ${dayName(rs[i][1])} overlap.`;
  return null;
}

/** The Maintenance answers that changed from how the card opened (nothing when nothing changed). */
export function maintenanceAnswers(now: MaintenanceState, was: MaintenanceState, def: number, quiet: boolean): Record<string, string> {
  const out: Record<string, string> = {};
  const days = now.daysOff.map((d) => daysOffOf(d) ?? def);
  const before = was.daysOff.map((d) => daysOffOf(d) ?? def);
  // With the user's dates the ranges say each doublet's days off; the lengths are Dioscuri's weeks'.
  if (quiet && days.join() !== before.join()) out.doublet_days_off = JSON.stringify(days.every((d) => d === def) ? [] : days);
  const plan = (s: MaintenanceState) =>
    s.units.map((u) => ({ unit: u.unit, mode: u.mode, ranges: u.mode === "dates" ? u.ranges.map((r) => [dayOf(r.from) ?? 0, dayOf(r.to) ?? 0]) : [] }));
  const p = plan(now);
  // A unit with no stop is left out of the plan (the engine's default is no stop), unless it had
  // one when the card opened: then "off" is said, so a stop asked for in the message is undone.
  const opened = new Map(was.units.map((u) => [u.unit, u.mode]));
  if (JSON.stringify(p) !== JSON.stringify(plan(was))) out.service_plan = JSON.stringify(p.filter((x) => x.mode !== "off" || (opened.get(x.unit) ?? "off") !== "off"));
  return out;
}

/** Each doublet's stop length for "My dates" in one block: its own days off. */
export function blockDays(m: MaintenanceState | null, k: number, def: number): number {
  return (m && daysOffOf(m.daysOff[k] ?? "")) ?? def;
}
