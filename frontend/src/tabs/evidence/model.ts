// The Evidence tab's arithmetic, kept apart from the components so it can be tested: the
// scenario matrix of the eval runs, the benchmark tables' cleanup, and GEMINI's bug impact as a
// relative error on a diverging bar.

import type { Benchmark, EvalRun, EvalScenario, Evidence } from "../../workbench";

// ------------------------------------------------------------------ eval runs

const DEVICE_ORDER = ["gpu", "auto", "cpu"];
const DEVICE_LABEL: Record<string, string> = { gpu: "GPU", cpu: "CPU", auto: "Auto" };

export function deviceName(device: string): string {
  return DEVICE_LABEL[device.toLowerCase()] ?? (device || "–");
}

/** "2026-10-29T08:15:00Z" or the runs' file stamp "20261029T081500Z" → a Date (null if neither). */
export function parseWhen(when: string): Date | null {
  if (!when) return null;
  const compact = when.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?$/);
  const d = compact ? new Date(Date.UTC(+compact[1], +compact[2] - 1, +compact[3], +compact[4], +compact[5], +compact[6])) : new Date(when);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "29 Oct 2026, 17:45". */
export function fmtDate(d: Date | null): string {
  if (!d) return "–";
  return `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}, ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
}

const WORDS: Record<string, string> = { gemini: "GEMINI", gpu: "GPU", cpu: "CPU", esp: "ESP", co2: "CO₂", hp: "HP" };

/** "S10_dutch_prompt" → { num: "S10", name: "Dutch prompt" }; "S07_what_if_reservoir" → "What-if reservoir". */
export function scenarioName(id: string): { num: string; name: string } {
  const m = id.match(/^([A-Za-z]?\d+)[_\s-]+(.*)$/);
  const num = m ? m[1] : "";
  const words = (m ? m[2] : id).split(/[_\s]+/).filter(Boolean).map((w) => WORDS[w.toLowerCase()] ?? w.toLowerCase());
  let name = words.join(" ").replace(/\bwhat if\b/, "what-if");
  name = name ? name[0].toUpperCase() + name.slice(1) : id;
  return { num, name };
}

/** "clarify_or_design" → "clarify or design"; "answer_or_about_or_clarify" → "answer, about or clarify". */
export function behaviourLabel(b: string): string {
  const parts = b.split("_or_").map((p) => p.replace(/_/g, " "));
  return parts.length <= 1 ? parts[0] ?? "" : `${parts.slice(0, -1).join(", ")} or ${parts[parts.length - 1]}`;
}

export interface MatrixRun {
  key: string;
  run: EvalRun;
  device: string;
  label: string;
  when: Date | null;
  failed: string[];
}

export interface MatrixRow {
  id: string;
  num: string;
  name: string;
  /** The expected behaviour (the first run's; the runs share the scenario files). */
  expected: string;
  /** One cell per run, in the runs' order; null where that run has no such scenario. */
  cells: (EvalScenario | null)[];
  failures: number;
}

export interface Matrix {
  runs: MatrixRun[];
  rows: MatrixRow[];
}

/** S2 before S10: compare ids by their numbers, then by the rest. */
function byId(a: string, b: string): number {
  return a.localeCompare(b, "en", { numeric: true, sensitivity: "base" });
}

/**
 * Rows = every scenario any run has (in id order), columns = the runs (GPU, auto, CPU, then
 * any other device; newest first within a device). A cell is that run's result, or null.
 */
export function buildMatrix(evals: EvalRun[]): Matrix {
  const order = (d: string) => {
    const i = DEVICE_ORDER.indexOf(d.toLowerCase());
    return i < 0 ? DEVICE_ORDER.length : i;
  };
  const sorted = evals
    .map((run, i) => ({ run, i, when: parseWhen(run.when) }))
    .sort((a, b) => order(a.run.device) - order(b.run.device) || (b.when?.getTime() ?? 0) - (a.when?.getTime() ?? 0) || a.i - b.i);
  const seen = new Map<string, number>();
  const runs: MatrixRun[] = sorted.map(({ run, i, when }) => {
    const base = run.label || deviceName(run.device);
    const n = (seen.get(base) ?? 0) + 1;
    seen.set(base, n);
    return { key: `${run.file || i}`, run, device: run.device, label: n > 1 ? `${base} ${n}` : base, when, failed: run.scenarios.filter((s) => !s.ok).map((s) => s.id) };
  });
  const ids = [...new Set(runs.flatMap((r) => r.run.scenarios.map((s) => s.id)))].sort(byId);
  const rows = ids.map((id) => {
    const cells = runs.map((r) => r.run.scenarios.find((s) => s.id === id) ?? null);
    const first = cells.find((c) => c) as EvalScenario;
    const { num, name } = scenarioName(id);
    return { id, num, name, expected: first.expected, cells, failures: cells.filter((c) => c && !c.ok).length };
  });
  return { runs, rows };
}

/** The median of a run's per-scenario values (tokens, seconds). */
export function median(values: number[]): number {
  const v = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!v.length) return NaN;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

// ------------------------------------------------------------------ benchmarks

/** "1. Reader: ten models ([ADR-0002](../docs/…))" → { text: "Reader: ten models", refs: ["ADR-0002"] }. */
export function cleanTitle(title: string): { text: string; refs: string[] } {
  const refs: string[] = [];
  let text = title.replace(/\[([^\]]+)\]\([^)]*\)/g, (_, label: string) => {
    refs.push(label);
    return "";
  });
  text = text
    .replace(/\(\s*(,\s*)*\)/g, "")
    .replace(/^\s*\d+\.\s+/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  return { text: text || title, refs };
}

/** Markdown left in a cell: links to their text, `code` and **bold** to plain text. */
export function cleanCell(v: string | number): string {
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en-US") : String(v);
  return v
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

const NUMERIC = [
  /^[~≈<>]?\s*[−-]?\d[\d,]*(\.\d+)?\s*(%|s|ms|min|GB|MB|kB|×)?$/,
  /^\d+\s*(\/|of)\s*\d+$/,
  /^\d+(\.\d+)?\s*[–-]\s*\d+(\.\d+)?\s*(s|%)?$/,
];

/** A cell that reads as a number ("601", "2.2", "45 s", "11/11", "8 of 8", "2–10"). */
export function isNumeric(v: string | number): boolean {
  if (typeof v === "number") return Number.isFinite(v);
  const s = v.trim();
  return !!s && NUMERIC.some((re) => re.test(s));
}

/** Per column: right-align it (every filled cell is a number, and it isn't the first column). */
export function numericColumns(b: Benchmark): boolean[] {
  return b.columns.map((_, c) => {
    if (c === 0) return false;
    const cells = b.rows.map((r) => r[c]).filter((v) => v !== undefined && v !== null && String(v).trim() !== "");
    return cells.length > 0 && cells.every(isNumeric);
  });
}

/** A cell split around model ids ("qwen3:1.7b", "qwen3.5:9b") so they can be set in mono. */
export function splitModels(text: string): { text: string; model: boolean }[] {
  const out: { text: string; model: boolean }[] = [];
  const re = /\b[a-z][a-z0-9.-]*:\d[\w.-]*[a-z0-9]/gi;
  let at = 0;
  for (const m of text.matchAll(re)) {
    if (m.index! > at) out.push({ text: text.slice(at, m.index), model: false });
    out.push({ text: m[0], model: true });
    at = m.index! + m[0].length;
  }
  if (at < text.length) out.push({ text: text.slice(at), model: false });
  return out;
}

// ------------------------------------------------------------------ GEMINI's bug impact

/**
 * How far the released GEMINI is from the fixed one, as a fraction of the fixed value:
 * (released − fixed) / |fixed|. 0 when both are 0; ±Infinity when only the fixed one is 0
 * (no scale to measure against); null when either is missing.
 */
export function relativeError(released: number | null, fixed: number | null): number | null {
  if (released === null || fixed === null || !Number.isFinite(released) || !Number.isFinite(fixed)) return null;
  if (fixed === 0) return released === 0 ? 0 : released > 0 ? Infinity : -Infinity;
  return (released - fixed) / Math.abs(fixed);
}

export interface DivergingBar {
  side: "neg" | "pos" | "none";
  /** Percent of the half track (0..100). */
  width: number;
  /** Beyond the scale: drawn to the end with a break mark. */
  clipped: boolean;
}

/** The bar of a relative error on a track from −limit to +limit (default ±100%). */
export function divergingBar(err: number | null, limit = 1): DivergingBar {
  if (err === null || err === 0 || Number.isNaN(err)) return { side: "none", width: 0, clipped: false };
  const clipped = Math.abs(err) > limit;
  return { side: err < 0 ? "neg" : "pos", width: clipped ? 100 : (Math.abs(err) / limit) * 100, clipped };
}

/** "+350%", "−40%", "0%", "from 0", "–". */
export function fmtError(err: number | null): string {
  if (err === null || Number.isNaN(err)) return "–";
  if (!Number.isFinite(err)) return "from 0";
  const pct = err * 100;
  if (Math.abs(pct) < 0.5) return "0%";
  const r = Math.abs(pct) >= 10 ? Math.round(pct) : Math.round(pct * 10) / 10;
  return `${r < 0 ? "−" : "+"}${Math.abs(r).toLocaleString("en-US")}%`;
}

/** A value with sensible digits: 314.69 → "314.7", 0.166 → "0.166", 0.0 → "0", null → "–". */
export function fmtValue(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "–";
  if (v === 0) return "0";
  const a = Math.abs(v);
  const digits = a >= 10 ? 1 : a >= 1 ? 2 : 3;
  const s = v.toFixed(digits).replace(/\.?0+$/, "");
  return (a >= 1000 ? Number(s).toLocaleString("en-US") : s).replace(/^-/, "−");
}

/** "m3/h" → "m³/h". */
export function fmtUnit(unit: string): string {
  return unit.replace(/m3\b/g, "m³").replace(/m2\b/g, "m²").replace(/CO2/g, "CO₂");
}

export interface BugRef {
  text: string;
  /** "F10" when the cause names one of the bugs. */
  code: string | null;
  /** The patch that fixes it (by its F code, or its number "(08)"), when found. */
  patch: { file: string; title: string } | null;
}

/** Split at commas and semicolons outside brackets: "F2 root; Carnot (10)", "flow (F10, F5)". */
function splitTop(s: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let cur = "";
  for (const ch of s) {
    if (ch === "(") depth++;
    if (ch === ")") depth = Math.max(0, depth - 1);
    if ((ch === "," || ch === ";") && depth === 0) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map((x) => x.trim()).filter(Boolean);
}

/** The bug causes of a row as chips, each tied to the patch that fixes it when it can be found. */
export function bugRefs(bugs: string, patches: Evidence["gemini"]["patches"]): BugRef[] {
  const byCode = (code: string) => patches.find((p) => new RegExp(`\\b${code}\\b`).test(p.title)) ?? null;
  const byNumber = (n: string) => patches.find((p) => p.file.startsWith(`${n.padStart(2, "0")}_`)) ?? null;
  return splitTop(bugs).map((text) => {
    const code = text.match(/^(F\d+)\b/)?.[1] ?? null;
    const num = text.match(/\((\d{1,2})\)\s*$/)?.[1];
    const patch = code ? byCode(code) : num ? byNumber(num) : null;
    return { text, code, patch };
  });
}

/** A patch's title without its trailing bug code, and the code: "Injector well: friction sign — F3". */
export function patchTitle(title: string): { text: string; code: string | null } {
  const m = title.match(/^(.*?)\s*[—–-]\s*(F\d+)\s*$/);
  return m ? { text: m[1], code: m[2] } : { text: title, code: null };
}
