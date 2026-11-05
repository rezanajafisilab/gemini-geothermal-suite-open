// The Trace tab's arithmetic, kept apart from the components so it can be tested: the run
// order, the step timeline on one time scale, the totals, the facts a step reports, and the
// export file.

import type { TraceRun, TraceStep } from "../../workbench";

export type ToolCall = TraceRun["tools"][number];
export type ModelCall = TraceRun["calls"][number];

// ------------------------------------------------------------------ runs

/** A run's start in milliseconds. The server sends ms; older traces and the fixtures send seconds. */
export function startedMs(started: number): number {
  if (!Number.isFinite(started) || started <= 0) return 0;
  return started < 1e12 ? started * 1000 : started;
}

/** Newest first; runs that started at the same moment keep the server's order. */
export function sortRuns(runs: TraceRun[]): TraceRun[] {
  return runs
    .map((r, i) => ({ r, i, t: startedMs(r.started) }))
    .sort((a, b) => b.t - a.t || b.i - a.i)
    .map((x) => x.r);
}

/**
 * The run to show: the one picked if it's still there, else the newest. `follow` (nothing
 * picked by hand) always shows the newest, so a new chat run takes over the page.
 */
export function pickRun(sorted: TraceRun[], picked: string | null, follow: boolean): TraceRun | null {
  if (!sorted.length) return null;
  if (!follow && picked) return sorted.find((r) => r.runId === picked) ?? sorted[0];
  return sorted[0];
}

const DEVICES: Record<string, string> = { gpu: "GPU", cpu: "CPU" };

/** "GPU", "CPU", or for "auto" the device its steps ran on ("GPU (auto)"). */
export function deviceLabel(run: Pick<TraceRun, "device" | "steps">): string {
  const d = (run.device || "").toLowerCase();
  if (DEVICES[d]) return DEVICES[d];
  const used = [...new Set(run.steps.map((s) => String(s.meta.device ?? "").toLowerCase()).filter((x) => DEVICES[x]))];
  if (d === "auto" || !d) return used.length === 1 ? `${DEVICES[used[0]]}${d ? " (auto)" : ""}` : d ? "auto" : "–";
  return run.device;
}

export type Tone = "teal" | "amber" | "ok" | "red" | "grey";

/** The chip of a run's outcome (the behaviour the agent chose). */
export function outcomeTone(outcome: string): Tone {
  const o = outcome.toLowerCase();
  if (!o) return "grey";
  if (o === "design" || o === "what_if") return "teal";
  if (o.startsWith("clarify") || o === "ask" || o === "offer" || o === "decision") return "amber";
  if (/refuse|reject|nonsense|infeasible|error/.test(o)) return "red";
  return "grey";
}

/** "report_infeasible" → "report infeasible"; "" (no RUN_FINISHED) → "unfinished". */
export function outcomeLabel(outcome: string): string {
  return outcome ? outcome.replace(/_/g, " ") : "unfinished";
}

// ------------------------------------------------------------------ the step timeline

export interface TimelineRow {
  step: TraceStep;
  index: number;
  /** Seconds from the run's start (the steps run one after another). */
  start: number;
  /** Percent of the scale. */
  left: number;
  width: number;
}

export interface Timeline {
  /** The scale's end in seconds: the run's time, or the steps' sum if that is longer. */
  total: number;
  rows: TimelineRow[];
  /** Round ticks from 0 to the scale's end. */
  ticks: { value: number; left: number; label: string }[];
}

const STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600];

/** A round tick step that gives at most `max` intervals over `total`. */
export function tickStep(total: number, max = 5): number {
  if (!(total > 0)) return 1;
  return STEPS.find((s) => total / s <= max) ?? Math.ceil(total / max / 600) * 600;
}

function tickLabel(v: number, step: number): string {
  if (v === 0) return "0";
  const digits = step >= 1 ? 0 : step >= 0.1 ? 1 : 2;
  return `${v.toFixed(digits)} s`;
}

/**
 * Every step on one time scale. Steps run one after another, so each starts where the last
 * ended; the scale is the run's time (or the steps' sum when longer), so the bars of all steps,
 * filtered or not, can be compared by length.
 */
export function timeline(steps: TraceStep[], runSeconds: number): Timeline {
  let at = 0;
  const raw = steps.map((step, index) => {
    const s = Math.max(0, Number(step.seconds) || 0);
    const row = { step, index, start: at, seconds: s };
    at += s;
    return row;
  });
  const total = Math.max(Number(runSeconds) || 0, at);
  const pct = (v: number) => (total > 0 ? (v / total) * 100 : 0);
  const rows = raw.map(({ step, index, start, seconds }) => ({ step, index, start, left: pct(start), width: pct(seconds) }));
  const step = tickStep(total);
  const ticks: Timeline["ticks"] = [];
  if (total > 0)
    for (let i = 0; i * step <= total + 1e-9; i++) {
      const v = i * step;
      ticks.push({ value: v, left: pct(v), label: tickLabel(v, step) });
    }
  return { total, rows, ticks };
}

// ------------------------------------------------------------------ step kinds

export interface KindInfo {
  key: string;
  label: string;
  /** The bar's colour (checked with the dataviz validator; "tool" is the neutral grey of plain code). */
  color: string;
}

/** The kinds in legend order. Colours: a validated categorical set, plus grey for plain code. */
export const KINDS: KindInfo[] = [
  { key: "model", label: "Model", color: "#11949F" },
  { key: "tool", label: "Tool", color: "#7A858D" },
  { key: "plan", label: "Plan", color: "#7856C4" },
  { key: "check", label: "Check", color: "#1E9150" },
  { key: "report", label: "Report", color: "#3F7FE0" },
  { key: "ask", label: "Ask you", color: "#B87A1E" },
];

export function kindInfo(kind: string): KindInfo {
  return KINDS.find((k) => k.key === kind) ?? { key: kind || "other", label: kind ? kind[0].toUpperCase() + kind.slice(1) : "Other", color: "#9AA6AE" };
}

/** The kinds a run's steps use, in legend order (unknown kinds last), with their counts. */
export function kindCounts(steps: TraceStep[]): { info: KindInfo; count: number }[] {
  const counts = new Map<string, number>();
  for (const s of steps) counts.set(s.kind || "other", (counts.get(s.kind || "other") ?? 0) + 1);
  const known = KINDS.filter((k) => counts.has(k.key)).map((info) => ({ info, count: counts.get(info.key)! }));
  const other = [...counts.keys()].filter((k) => !KINDS.some((x) => x.key === k)).map((k) => ({ info: kindInfo(k), count: counts.get(k)! }));
  return [...known, ...other];
}

// ------------------------------------------------------------------ what a step reports

/** "qwen3:1.7b · GPU" from a step's metadata, or null when no model ran it. */
export function stepModel(step: TraceStep): string | null {
  const m = step.meta;
  const model = typeof m.model === "string" ? m.model : null;
  if (!model) return null;
  const d = typeof m.device === "string" ? DEVICES[m.device.toLowerCase()] : undefined;
  return d ? `${model} · ${d}` : model;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The key facts a step's metadata reports, as short chips (tokens, who decided, checks, claims…). */
export function stepFacts(step: TraceStep): { text: string; tone: Tone }[] {
  const m = step.meta;
  const out: { text: string; tone: Tone }[] = [];
  const tokens = num(m.tokens);
  if (tokens) out.push({ text: plural(tokens, "token"), tone: "grey" });
  if (m.screened === true) out.push({ text: "keyword screen", tone: "grey" });
  if (typeof m.intent === "string" && m.intent) out.push({ text: `intent: ${m.intent.replace(/_/g, " ")}`, tone: "grey" });
  if (m.decided_by === "model") out.push({ text: "model decided", tone: "teal" });
  else if (m.decided_by === "rules") out.push({ text: "rules decided", tone: "grey" });
  else if (m.decided_by === "skipped") out.push({ text: "skipped", tone: "grey" });
  if (Array.isArray(m.corrections) && m.corrections.length) out.push({ text: plural(m.corrections.length, "correction"), tone: "amber" });
  const checked = num(m.checked);
  if (checked !== null) {
    out.push({ text: `${plural(checked, "claim")} checked`, tone: "grey" });
    const removed = num(m.removed) ?? 0;
    out.push(removed ? { text: `${removed} removed`, tone: "red" } : { text: "none removed", tone: "ok" });
  }
  const passed = num(m.passed);
  const total = num(m.total);
  if (passed !== null && total !== null) out.push({ text: `${passed} of ${total} pass`, tone: passed === total ? "ok" : "red" });
  const calls = num(m.calls);
  if (calls !== null) out.push({ text: plural(calls, "call"), tone: "grey" });
  const failed = num(m.failed);
  if (failed) out.push({ text: `${failed} failed`, tone: "red" });
  const passages = num(m.passages);
  if (passages !== null) out.push({ text: plural(passages, "passage"), tone: "grey" });
  const suspicious = num(m.suspicious);
  if (suspicious) out.push({ text: `${suspicious} flagged`, tone: "red" });
  if (Array.isArray(m.ungrounded)) out.push(m.ungrounded.length ? { text: `${plural(m.ungrounded.length, "number")} not traced`, tone: "red" } : { text: "every number traced", tone: "ok" });
  else {
    const ungrounded = num(m.ungrounded);
    if (ungrounded !== null) out.push(ungrounded ? { text: `${plural(ungrounded, "number")} not traced`, tone: "red" } : { text: "every number traced", tone: "ok" });
  }
  if (Array.isArray(m.missing)) for (const k of m.missing) out.push({ text: `no ${String(k).replace(/_/g, " ")}`, tone: "amber" });
  for (const key of ["solver", "source"] as const) {
    const v = m[key];
    if (v === "gemini") out.push({ text: "GEMINI", tone: "teal" });
    else if (v === "dioscuri") out.push({ text: "Dioscuri", tone: "teal" });
  }
  return out;
}

// ------------------------------------------------------------------ tools

/** The function a step's code calls: "solve_doublet(depth_m=2500)" → "solve_doublet". */
export function codeFunction(code: string | null): string | null {
  const m = code?.match(/^\s*([A-Za-z_][\w.]*)\s*\(/);
  return m ? m[1] : null;
}

/** A tool call's arguments in a line: depth_m=2500, alternative=A1, query="…". */
export function argSummary(args: unknown, max = 3): string {
  if (args === null || args === undefined) return "";
  if (typeof args !== "object") return short(JSON.stringify(args));
  if (Array.isArray(args)) return `${args.length} item${args.length === 1 ? "" : "s"}`;
  const parts: string[] = [];
  for (const [k, v] of Object.entries(args as Record<string, unknown>)) {
    if (parts.length >= max) break;
    if (typeof v === "string") parts.push(`${k}=${short(JSON.stringify(v))}`);
    else if (typeof v === "number" || typeof v === "boolean") parts.push(`${k}=${v}`);
    else if (v && typeof v === "object" && typeof (v as Record<string, unknown>).code === "string") parts.push(`${k}=${(v as Record<string, unknown>).code}`);
  }
  return parts.join(", ");
}

const short = (s: string, n = 42) => (s.length > n ? `${s.slice(0, n - 1)}…"` : s);

/** What a tool call's result says about itself: from the cache, an error, who computed it. */
export function resultFlags(result: unknown): { text: string; tone: Tone }[] {
  if (!result || typeof result !== "object" || Array.isArray(result)) return [];
  const r = result as Record<string, unknown>;
  const out: { text: string; tone: Tone }[] = [];
  if (r.cached === true) out.push({ text: "from cache", tone: "teal" });
  if (r.error) out.push({ text: "error", tone: "red" });
  const inner = r.result && typeof r.result === "object" ? (r.result as Record<string, unknown>) : r;
  const src = typeof inner.source === "string" ? inner.source : "";
  if (src.startsWith("gemini")) out.push({ text: src === "gemini" ? "GEMINI" : "GEMINI + Dioscuri", tone: "teal" });
  else if (src === "dioscuri_plant") out.push({ text: "Dioscuri", tone: "teal" });
  return out;
}

/**
 * The run's tool calls grouped by the step that made them (matched by the function its code
 * calls), in step order; calls no step names come last under "Other tool calls".
 */
export function toolGroups(run: TraceRun): { title: string; step: TraceStep | null; calls: { call: ToolCall; index: number }[] }[] {
  const left = run.tools.map((call, index) => ({ call, index }));
  const groups: { title: string; step: TraceStep | null; calls: { call: ToolCall; index: number }[] }[] = [];
  for (const step of run.steps) {
    const fn = codeFunction(step.code);
    if (!fn) continue;
    const mine = left.filter((t) => t.call.name === fn);
    if (!mine.length) continue;
    groups.push({ title: step.label || step.name, step, calls: mine });
    for (const t of mine) left.splice(left.indexOf(t), 1);
  }
  if (left.length) groups.push({ title: groups.length ? "Other tool calls" : "Tool calls", step: null, calls: left });
  return groups;
}

// ------------------------------------------------------------------ totals

export interface RunTotals {
  calls: number;
  failedCalls: number;
  prompt: number;
  output: number;
  tokens: number;
  seconds: number;
  modelSeconds: number;
  toolCalls: number;
  cached: number;
  models: string[];
  /** Tokens per call purpose (intake, answer, claims …), in the order the calls were made. */
  byPurpose: { purpose: string; calls: number; prompt: number; output: number; total: number }[];
}

export function runTotals(run: TraceRun): RunTotals {
  const byPurpose = new Map<string, RunTotals["byPurpose"][number]>();
  let prompt = 0;
  let output = 0;
  let modelSeconds = 0;
  for (const c of run.calls) {
    const p = Number(c.prompt_tokens) || 0;
    const o = Number(c.output_tokens) || 0;
    prompt += p;
    output += o;
    modelSeconds += Number(c.seconds) || 0;
    const key = c.purpose || "call";
    const g = byPurpose.get(key) ?? { purpose: key, calls: 0, prompt: 0, output: 0, total: 0 };
    g.calls += 1;
    g.prompt += p;
    g.output += o;
    g.total += p + o;
    byPurpose.set(key, g);
  }
  // A run cut short has no usage events; fall back to its own token count.
  if (!run.calls.length) {
    prompt = run.tokens?.prompt ?? 0;
    output = run.tokens?.output ?? 0;
  }
  return {
    calls: run.calls.length,
    failedCalls: run.calls.filter((c) => c.ok === false).length,
    prompt,
    output,
    tokens: prompt + output,
    seconds: Number(run.seconds) || 0,
    modelSeconds,
    toolCalls: run.tools.length,
    cached: run.tools.filter((t) => resultFlags(t.result).some((f) => f.text === "from cache")).length,
    models: [...new Set(run.calls.map((c) => c.model).filter(Boolean))],
    byPurpose: [...byPurpose.values()],
  };
}

// ------------------------------------------------------------------ export

export interface TraceExport {
  kind: "dioscuri-trace";
  threadId: string | null;
  exported: string;
  runs: TraceRun[];
}

/** The JSON file of one run or all of them, as the server sent them. */
export function exportPayload(threadId: string | null, runs: TraceRun[], now = new Date()): TraceExport {
  return { kind: "dioscuri-trace", threadId, exported: now.toISOString(), runs };
}

/** "dioscuri-trace-<thread>-<run>.json" or "dioscuri-trace-<thread>.json"; safe for any file system. */
export function exportName(threadId: string | null, runId?: string): string {
  const safe = (s: string) => s.replace(/[^\w.-]+/g, "_").slice(0, 40);
  return `dioscuri-trace-${safe(threadId || "chat")}${runId ? `-${safe(runId)}` : ""}.json`;
}

/** Save `data` as a JSON file (the browser's download). */
export function downloadJson(name: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ------------------------------------------------------------------ formatting

/** "3.5 s", "0.26 s", "0 s", "1 min 5 s". */
export function fmtSec(s: number): string {
  if (!Number.isFinite(s) || s <= 0) return "0 s";
  if (s < 0.01) return "<0.01 s";
  if (s < 1) return `${s.toFixed(2)} s`;
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${Math.round(s - m * 60)} s`;
}

/** 2463 → "2,463"; 12900 → "12.9K" with compact. */
export function fmtInt(n: number, compact = false): string {
  if (!Number.isFinite(n)) return "–";
  if (compact && Math.abs(n) >= 10000) return `${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}K`;
  return Math.round(n).toLocaleString("en-US");
}

/** "18:38" today, "28 Oct, 18:38" another day. */
export function fmtWhen(ms: number, now = Date.now()): string {
  if (!ms) return "–";
  const d = new Date(ms);
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  const sameDay = new Date(now).toDateString() === d.toDateString();
  return sameDay ? time : `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })}, ${time}`;
}
