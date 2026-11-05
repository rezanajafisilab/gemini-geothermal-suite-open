// The chat's state machine: user actions and AG-UI events in, a list of turns out.
// Pure and synchronous, so it is tested directly on recorded streams (reducer.test.ts).
//
// A turn is one user message plus every run it takes to answer it: a run that stops to ask
// (RUN_FINISHED with an interrupt) and the run that continues once the answers are sent share
// one turn, one steps group and one answer, as on the canvas.

import type { Action, AgEvent, AnswerMeta, Ask, ChatState, Check, ClaimsMeta, Clarification, Comparison, CompareView, ConfirmInputs, DecisionView, FailureView, ReportView, FileView, PlanView, UncertaintyView, GenAttempt, Generation, ModelResult, Passage, Reply, ResultCard, Search, Step, StepKind, Turn, TurnAttachment, Unavailable, UsageCall } from "./types";

export function emptyChat(threadId: string): ChatState {
  return { threadId, turns: [] };
}

export function newTurn(id: string, message: string, at: number, reasoning = false, attachments?: TurnAttachment[], designs?: { id: string; text: string }[]): Turn {
  // (asks, sources and attempts start empty and are added as they arrive)
  return {
    id,
    message,
    // Only a message that carried files has the field, so older saved chats read the same.
    ...(attachments?.length ? { attachments } : {}),
    ...(designs?.length ? { designs } : {}),
    createdAt: at,
    activeSince: at,
    reasoning,
    status: "running",
    runs: [],
    steps: [],
    messages: [],
    usage: [],
    cards: [],
  };
}

export function reduce(state: ChatState, action: Action): ChatState {
  switch (action.type) {
    case "send": {
      // A new message while a question is open drops that question (the agent does too).
      const turns = state.turns.map((t) =>
        t.status === "waiting"
          ? {
              ...t,
              status: "done" as const,
              skipped: true,
              asks: (t.asks ?? []).map((a, i, all) => (i === all.length - 1 && !a.answers ? { ...a, skipped: true } : a)),
              steps: t.steps.map((s) => (s.status === "waiting" ? { ...s, status: "stopped" as const } : s)),
            }
          : t,
      );
      return { ...state, turns: [...turns, newTurn(action.turnId, action.message, action.at, action.reasoning, action.attachments, action.designs)] };
    }
    case "attachments": {
      // The uploads that were still running when the message went settled: the message shows
      // the files the server has now (and their passage counts); a failed one goes back to the composer.
      const i = state.turns.findIndex((t) => t.id === action.turnId);
      if (i < 0) return state;
      const turns = state.turns.slice();
      const { attachments: _old, ...rest } = turns[i];
      turns[i] = action.attachments.length ? { ...rest, attachments: action.attachments } : rest;
      return { ...state, turns };
    }
    case "answer":
      return updateLast(state, (t) => ({
        ...t,
        answers: action.answers,
        asks: (t.asks ?? []).map((a, i, all) => (i === all.length - 1 ? { ...a, answers: action.answers } : a)),
        activeSince: action.at,
        status: "running",
        error: undefined,
        steps: t.steps.map((s) => (s.status === "waiting" ? { ...s, status: "done" } : s)),
      }));
    case "stopped":
      return updateLast(state, (t) =>
        t.status === "running"
          ? {
              ...t,
              status: "stopped",
              steps: t.steps.map((s) => (s.status === "active" ? { ...s, status: "stopped" } : s)),
            }
          : t,
      );
    case "failed":
      return updateLast(state, (t) => ({
        ...t,
        status: "error",
        error: { message: action.message, code: action.code },
        steps: t.steps.map((s) => (s.status === "active" ? { ...s, status: "error" } : s)),
      }));
    case "event":
      return updateLast(state, (t) => applyEvent(t, action.event));
    default:
      return state;
  }
}

function updateLast(state: ChatState, fn: (t: Turn) => Turn): ChatState {
  const n = state.turns.length;
  if (!n) return state;
  const last = state.turns[n - 1];
  const next = fn(last);
  if (next === last) return state;
  return { ...state, turns: [...state.turns.slice(0, n - 1), next] };
}

const KINDS: StepKind[] = ["model", "tool", "check", "ask", "plan", "report"];

/** Apply one AG-UI event to the turn it belongs to. Unknown events leave the turn unchanged. */
export function applyEvent(t: Turn, e: AgEvent): Turn {
  const run = Math.max(0, t.runs.length - 1);
  switch (e.type) {
    case "RUN_STARTED":
      return {
        ...t,
        status: t.status === "stopped" ? t.status : "running",
        runs: [...t.runs, { runId: e.runId, startedAt: e.timestamp, tokens: 0 }],
      };

    case "STEP_STARTED": {
      const md = e.metadata ?? {};
      const kind = KINDS.includes(md.kind as StepKind) ? (md.kind as StepKind) : "tool";
      const step: Step = {
        key: `${run}:${e.stepName}:${t.steps.length}`,
        name: e.stepName,
        label: md.label || e.stepName,
        kind,
        code: md.code ?? null,
        status: "active",
        run,
        startedAt: e.timestamp,
        meta: {},
        tools: [],
      };
      return { ...t, steps: [...t.steps, step] };
    }

    case "STEP_FINISHED": {
      const i = findLastIndex(t.steps, (s) => s.name === e.stepName && s.status === "active");
      if (i < 0) return t;
      const { seconds, ...meta } = (e.metadata ?? {}) as Record<string, unknown> & { seconds?: number };
      // A tool step with failed calls ticks off red; the run carries on without those designs.
      const failed = (typeof meta.failed === "number" && meta.failed > 0) || meta.passed === false;
      return replaceStep(t, i, (s) => ({
        ...s,
        status: failed ? "error" : "done",
        seconds: typeof seconds === "number" ? seconds : s.seconds,
        meta: { ...s.meta, ...meta },
      }));
    }

    case "TOOL_CALL_START": {
      const call = { id: e.toolCallId, name: e.toolCallName, args: "", done: false };
      const i = findLastIndex(t.steps, (s) => s.status === "active");
      if (i < 0) return t;
      return replaceStep(t, i, (s) => ({ ...s, tools: [...s.tools, call] }));
    }

    case "TOOL_CALL_ARGS":
      return updateTool(t, e.toolCallId, (c) => ({ ...c, args: c.args + e.delta }));

    case "TOOL_CALL_END":
      return updateTool(t, e.toolCallId, (c) => ({ ...c, done: true }));

    case "TOOL_CALL_RESULT": {
      const body = parseJson(e.content);
      const error = body && typeof body.error === "string" ? body.error : undefined;
      const cached = body ? body.cached === true : undefined;
      return updateTool(t, e.toolCallId, (c) => ({ ...c, result: e.content, error, cached, done: true }));
    }

    case "TEXT_MESSAGE_START":
      if (t.messages.some((m) => m.id === e.messageId)) return t;
      return claimReply({ ...t, messages: [...t.messages, { id: e.messageId, run, text: "", steps: t.steps.length }] }, e.messageId, run);

    case "TEXT_MESSAGE_CONTENT": {
      const has = t.messages.some((m) => m.id === e.messageId);
      if (has) return { ...t, messages: t.messages.map((m) => (m.id === e.messageId ? { ...m, text: m.text + e.delta } : m)) };
      return claimReply({ ...t, messages: [...t.messages, { id: e.messageId, run, text: e.delta, steps: t.steps.length }] }, e.messageId, run);
    }

    case "TEXT_MESSAGE_END":
      return t;

    case "CUSTOM":
      return applyCustom(t, e.name, e.value, run);

    case "RUN_ERROR":
      return {
        ...t,
        status: "error",
        error: { message: e.message, code: e.code },
        steps: t.steps.map((s) => (s.status === "active" ? { ...s, status: "error" } : s)),
      };

    case "RUN_FINISHED": {
      const summary = e.result;
      const tokens =
        summary && (summary.prompt_tokens != null || summary.output_tokens != null)
          ? (summary.prompt_tokens ?? 0) + (summary.output_tokens ?? 0)
          : (e.usage ?? []).reduce((a, u) => a + (u.totalTokens ?? 0), 0);
      const outcome = e.outcome?.type ?? "success";
      const runs = t.runs.length
        ? t.runs.map((r, i) => (i === t.runs.length - 1 ? { ...r, outcome, summary, tokens } : r))
        : [{ runId: e.runId, outcome, summary, tokens }];
      // A run that already failed (RUN_ERROR) or was stopped keeps that status.
      if (t.status === "error" || t.status === "stopped") return { ...t, runs };
      const waiting = outcome === "interrupt";
      const steps = t.steps.map((s) => {
        if (s.status !== "active" && !(waiting && s.kind === "ask" && s.run === run)) return s;
        return { ...s, status: waiting && s.kind === "ask" ? ("waiting" as const) : ("done" as const) };
      });
      return { ...t, runs, steps, status: waiting ? "waiting" : "done" };
    }

    default:
      return t;
  }
}

function applyCustom(t: Turn, name: string, value: unknown, run: number): Turn {
  switch (name) {
    case "usage":
      return value && typeof value === "object" ? { ...t, usage: [...t.usage, value as UsageCall] } : t;
    case "clarification":
      return {
        ...t,
        clarification: value as Clarification,
        clarificationRun: run,
        answers: undefined,
        asks: [...(t.asks ?? []), { run, value: value as Clarification }],
      };
    case "sources":
      // One list per run. The answerer sends the passages its reply cited after the text; that
      // list replaces any earlier one of the same run (a search step's), never another run's.
      return Array.isArray(value)
        ? { ...t, sources: [...(t.sources ?? []).filter((s) => s.run !== run), { run, passages: value as Passage[] }] }
        : t;
    case "file": {
      // One card per file and run: the same file sent again replaces its card.
      if (!value || typeof value !== "object" || typeof (value as FileView).name !== "string") return t;
      const file = value as FileView;
      const files = (t.files ?? []).filter((f) => !(f.run === run && f.file.name === file.name));
      return { ...t, files: [...files, { run, file }] };
    }
    case "answer": {
      if (!value || typeof value !== "object") return t;
      // Sent right after its reply's text, or just before it (then the next message claims it).
      // Right after: the run's last message, unclaimed, with no step started since it began.
      const last = t.messages[t.messages.length - 1];
      const taken = new Set((t.replies ?? []).map((r) => r.message));
      const fresh = last && last.run === run && !taken.has(last.id) && (last.steps ?? t.steps.length) === t.steps.length;
      const reply: Reply = { run, message: fresh ? last.id : undefined, value: value as AnswerMeta };
      return { ...t, replies: [...(t.replies ?? []), reply] };
    }
    case "modelgen_attempt":
      return value && typeof value === "object" ? { ...t, attempts: [...(t.attempts ?? []), value as GenAttempt] } : t;
    case "model_result":
      return value && typeof value === "object" ? { ...t, results: [...(t.results ?? []), { run, value: value as ModelResult }] } : t;
    case "model_approval":
      return value && typeof value === "object" ? { ...t, generation: value as Generation } : t;
    case "result":
      return { ...t, result: value as ResultCard, cards: [...(t.cards ?? []), { run, result: value as ResultCard }] };
    case "comparison": {
      // One per run: a comparison sent again in the same run replaces the earlier one.
      const v = value as Comparison | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.designs)) return t;
      return { ...t, comparisons: [...(t.comparisons ?? []).filter((c) => c.run !== run), { run, value: v }] };
    }
    case "failure": {
      const v = value as FailureView | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.events)) return t;
      return { ...t, failures: [...(t.failures ?? []), { run, value: v }] };
    }
    case "plan": {
      const v = value as PlanView | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.steps)) return t;
      return { ...t, plans: [...(t.plans ?? []).filter((p) => p.run !== run), { run, value: v }] };
    }
    case "uncertainty": {
      const v = value as UncertaintyView | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.tornado)) return t;
      return { ...t, uncertainties: [...(t.uncertainties ?? []), { run, value: v }] };
    }
    case "report": {
      const v = value as ReportView | null;
      if (!v || typeof v !== "object" || typeof v.url !== "string") return t;
      return { ...t, reports: [...(t.reports ?? []), { run, value: v }] };
    }
    case "decision": {
      const v = value as DecisionView | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.rows)) return t;
      return { ...t, decisions: [...(t.decisions ?? []), { run, value: v }] };
    }
    case "compare": {
      const v = value as CompareView | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.designs) || !Array.isArray(v.rows)) return t;
      return { ...t, compares: [...(t.compares ?? []), { run, value: v }] };
    }
    case "candidates": {
      const v = value as Search | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.candidates)) return t;
      return { ...t, searches: [...(t.searches ?? []).filter((s) => s.run !== run), { run, value: v }] };
    }
    case "confirm_inputs": {
      // Sent right after the same inputs as a Markdown table: the card takes that message's place.
      const v = value as ConfirmInputs | null;
      if (!v || typeof v !== "object" || !Array.isArray(v.rows)) return t;
      const last = t.messages[t.messages.length - 1];
      const message = last && last.run === run ? last.id : undefined;
      const confirm = { run, value: { ...v, changed: Array.isArray(v.changed) ? v.changed : [], kinds: v.kinds ?? {} }, ...(message ? { message } : {}) };
      return { ...t, confirms: [...(t.confirms ?? []).filter((c) => c.run !== run), confirm] };
    }
    case "checks": {
      if (!Array.isArray(value)) return t;
      const cards = (t.cards ?? []).slice();
      const i = cards.length - 1;
      if (i >= 0 && cards[i].run === run) cards[i] = { ...cards[i], checks: value as Check[] };
      return { ...t, checks: value as Check[], cards };
    }
    case "suggestions":
      return Array.isArray(value) ? { ...t, suggestions: value.map(String) } : t;
    case "model_unavailable":
      return value && typeof value === "object" ? { ...t, unavailable: { ...(value as Unavailable), run } } : t;
    default:
      return t;
  }
}

/** A new message takes the run's answer event that arrived before it, if one is waiting. */
function claimReply(t: Turn, id: string, run: number): Turn {
  const i = (t.replies ?? []).findIndex((r) => r.run === run && !r.message);
  if (i < 0) return t;
  const replies = t.replies!.slice();
  replies[i] = { ...replies[i], message: id };
  return { ...t, replies };
}

function parseJson(text: string): Record<string, unknown> | null {
  try {
    const v = JSON.parse(text);
    return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function replaceStep(t: Turn, i: number, fn: (s: Step) => Step): Turn {
  const steps = t.steps.slice();
  steps[i] = fn(steps[i]);
  return { ...t, steps };
}

function updateTool(t: Turn, id: string, fn: (c: Step["tools"][number]) => Step["tools"][number]): Turn {
  const i = t.steps.findIndex((s) => s.tools.some((c) => c.id === id));
  if (i < 0) return t;
  return replaceStep(t, i, (s) => ({ ...s, tools: s.tools.map((c) => (c.id === id ? fn(c) : c)) }));
}

function findLastIndex<T>(list: T[], pred: (x: T) => boolean): number {
  for (let i = list.length - 1; i >= 0; i--) if (pred(list[i])) return i;
  return -1;
}

// ------------------------------------------------------------------ selectors

/** What the turn's answer says: every message except the clarification's intro line. */
export function answerText(t: Turn): string {
  const intro = t.clarification?.intro?.trim();
  return t.messages
    .map((m) => m.text.trim())
    .filter((text) => text && text !== intro)
    .join("\n\n");
}

/** The designs a run left out (a failed tool or physics check), as [code, reason]; the last run by default. */
export function leftOut(t: Turn, run = t.runs.length - 1): [string, string][] {
  const list = t.runs[run]?.summary?.left_out ?? [];
  return list.map((item) => {
    const at = item.indexOf(": ");
    return at > 0 ? [item.slice(0, at), item.slice(at + 2)] : ["", item];
  });
}

/** The answer without its closing "Left out: ..." sentence, which the UI draws as rows. */
export function withoutLeftOut(text: string): string {
  const at = text.lastIndexOf(" Left out: ");
  return at >= 0 ? text.slice(0, at).trim() : text;
}

/**
 * The text a run sent, without the clarification's intro line, and without the Markdown table
 * an inputs card replaces (the table stays when the card's event is missing).
 */
export function runText(t: Turn, run: number): string {
  const intro = t.clarification?.intro?.trim();
  const replaced = runConfirm(t, run)?.message;
  return t.messages
    .filter((m) => m.run === run && m.id !== replaced)
    .map((m) => m.text.trim())
    .filter((text) => text && text !== intro)
    .join("\n\n");
}

/**
 * The inputs card of a run, when the run both sent the inputs (CUSTOM "confirm_inputs") and
 * asked to run with them (clarification kind "confirm"); with the message it replaces.
 */
export function runConfirm(t: Turn, run: number): { value: ConfirmInputs; message?: string } | undefined {
  const c = findLast(t.confirms ?? [], (x) => x.run === run);
  if (!c) return undefined;
  const asked = asksOf(t).some((a) => a.run === run && a.value.kind === "confirm");
  return asked ? c : undefined;
}

export type ConfirmReply = "run" | "change" | "refused" | "reset" | "other" | "reading";

/**
 * How the agent read a typed reply to an inputs card: the "confirm" step of the turn that
 * reply started ("run", "change", "reset" or "other"; "refused" for a change the next card
 * refused), "reading" while that step is still working, and undefined when that turn has no
 * such step (the reply was not read as an answer to the card).
 */
export function confirmReplyOf(next: Turn | undefined): ConfirmReply | undefined {
  if (!next) return undefined;
  const step = next.steps.find((s) => s.name === "confirm");
  if (!step) return next.status === "running" && !next.steps.length ? "reading" : undefined;
  if (step.status === "active") return "reading";
  const d = step.meta.decision;
  // A change the card refused (5 Nov): the next card says "Nothing changed" at its top.
  if (d === "change" && (next.confirms ?? []).some((c) => c.value.notice?.kind === "refused")) return "refused";
  return d === "run" || d === "change" || d === "reset" || d === "other" ? d : undefined;
}

/** The model a decision step used, from the usage call with the step's purpose. */
export function stepModel(t: Turn, step: Step): string | undefined {
  // A decision made by another step's call (the reader judging whether to reason) names it.
  if (typeof step.meta.model === "string" && step.meta.model) return step.meta.model;
  return [...t.usage].reverse().find((u) => u.purpose === step.name && u.ok)?.model;
}

/** True when the run refused an off-topic message by the keyword screen, with no model call. */
export function screened(t: Turn, run: number): boolean {
  return t.runs[run]?.summary?.screened === true;
}

/** The behaviour of the turn's last finished run (design, clarify, refuse, reject, ...). */
export function behaviour(t: Turn): string | undefined {
  for (let i = t.runs.length - 1; i >= 0; i--) {
    const b = t.runs[i].summary?.behaviour;
    if (b) return b;
  }
  return undefined;
}

export interface Totals {
  tokens: number;
  promptTokens: number;
  outputTokens: number;
  seconds: number;
  llmCalls: number;
  steps: number;
  toolCalls: number;
  cacheHits: number;
  toolErrors: number;
  /** GPU energy measured while the runs ran, Wh (0: not measured). */
  energyWh: number;
}

export const ZERO: Totals = { tokens: 0, promptTokens: 0, outputTokens: 0, seconds: 0, llmCalls: 0, steps: 0, toolCalls: 0, cacheHits: 0, toolErrors: 0, energyWh: 0 };

export function turnTotals(t: Turn): Totals {
  const sum = (f: (s: NonNullable<Turn["runs"][number]["summary"]>) => number | undefined) =>
    t.runs.reduce((a, r) => a + (r.summary ? (f(r.summary) ?? 0) : 0), 0);
  return {
    tokens: t.runs.reduce((a, r) => a + r.tokens, 0),
    promptTokens: sum((s) => s.prompt_tokens),
    outputTokens: sum((s) => s.output_tokens),
    seconds: sum((s) => s.seconds),
    llmCalls: sum((s) => s.llm_calls),
    steps: t.steps.length,
    toolCalls: sum((s) => s.tool_calls),
    cacheHits: sum((s) => s.cache_hits),
    toolErrors: sum((s) => s.tool_errors),
    energyWh: sum((s) => s.energy_wh),
  };
}

export function chatTotals(c: ChatState): Totals {
  return c.turns.map(turnTotals).reduce(
    (a, b) => Object.fromEntries(Object.keys(ZERO).map((k) => [k, a[k as keyof Totals] + b[k as keyof Totals]])) as unknown as Totals,
    { ...ZERO },
  );
}

export type ChatStatus = "idle" | "running" | "waiting" | "done" | "error" | "stopped";

/** The chat's live status for the sidebar: that of its last turn. */
export function chatStatus(c: ChatState): ChatStatus {
  const last = c.turns[c.turns.length - 1];
  return last ? last.status : "idle";
}

/** Replay a whole recorded stream onto a chat (tests and fixture mode). */
export function replay(state: ChatState, events: AgEvent[]): ChatState {
  return events.reduce((s, event) => reduce(s, { type: "event", event }), state);
}

/** The asks of a turn (older saved turns have only the latest clarification). */
export function asksOf(t: Turn): Ask[] {
  if (t.asks?.length) return t.asks;
  return t.clarification ? [{ run: t.clarificationRun ?? 0, value: t.clarification, answers: t.answers, skipped: t.skipped }] : [];
}

/** The passages a run cited. */
export function runSources(t: Turn, run: number): Passage[] {
  return (t.sources ?? []).filter((s) => s.run === run).flatMap((s) => s.passages);
}

/** The files a run opened, in the order they came. */
export function runFiles(t: Turn, run: number): FileView[] {
  return (t.files ?? []).filter((f) => f.run === run).map((f) => f.file);
}

/** How the answerer read and wrote a run's reply (its last "answer" event), if it wrote one. */
export function runReply(t: Turn, run: number): AnswerMeta | undefined {
  return findLast(t.replies ?? [], (r) => r.run === run)?.value;
}

export type ReplyChip = "general" | "out_of_scope" | "nonsense" | "fallback";

/**
 * What a reply says about itself under its text: general background (not from this project's
 * data), outside the scope, not a question, or the checked template. None for a project answer.
 */
export function replyChips(meta?: AnswerMeta): ReplyChip[] {
  if (!meta) return [];
  const out: ReplyChip[] = [];
  if (meta.kind === "out_of_scope") out.push("out_of_scope");
  else if (meta.kind === "nonsense") out.push("nonsense");
  else if (meta.scope === "general" && meta.kind !== "clarify") out.push("general");
  if (meta.fallback) out.push("fallback");
  return out;
}

/** The answer event that belongs to one text message. */
export function messageReply(t: Turn, messageId: string): AnswerMeta | undefined {
  return (t.replies ?? []).find((r) => r.message === messageId)?.value;
}

function findLast<T>(list: T[], pred: (x: T) => boolean): T | undefined {
  const i = findLastIndex(list, pred);
  return i < 0 ? undefined : list[i];
}

/** The design search a run made, if it made one. */
export function runSearch(t: Turn, run: number): Search | undefined {
  return findLast(t.searches ?? [], (s) => s.run === run)?.value;
}

/** The failure what-ifs a run sent. */
export function runFailures(t: Turn, run: number): FailureView[] {
  return (t.failures ?? []).filter((f) => f.run === run).map((f) => f.value);
}

/** The plan card of a run (its latest statuses), if it ran a plan. */
export function runPlan(t: Turn, run: number): PlanView | undefined {
  return findLast(t.plans ?? [], (p) => p.run === run)?.value;
}

/** The uncertainty cards a run sent. */
export function runUncertainties(t: Turn, run: number): UncertaintyView[] {
  return (t.uncertainties ?? []).filter((u) => u.run === run).map((u) => u.value);
}

/** The operator's reports a run made. */
export function runReports(t: Turn, run: number): ReportView[] {
  return (t.reports ?? []).filter((r) => r.run === run).map((r) => r.value);
}

/** The decision tables a run sent. */
export function runDecisions(t: Turn, run: number): DecisionView[] {
  return (t.decisions ?? []).filter((d) => d.run === run).map((d) => d.value);
}

/** The side-by-side tables a run sent. */
export function runCompares(t: Turn, run: number): CompareView[] {
  return (t.compares ?? []).filter((c) => c.run === run).map((c) => c.value);
}

/** The designs a run compared, if it sent a comparison of two or more. */
export function runComparison(t: Turn, run: number): Comparison | undefined {
  const v = findLast(t.comparisons ?? [], (c) => c.run === run)?.value;
  return v && v.designs.length >= 2 ? v : undefined;
}

export interface Claims {
  /** The claim checker's step, when the run had one. */
  step?: Step;
  skipped: boolean;
  checked: number;
  supported: number;
  general: number;
  removed: number;
  sentences: string[];
  /** Sentences reworded to say only what the sources say: [as written, as it now reads]. */
  reworded: [string, string][];
  note?: string;
}

/**
 * What the claim checker did to a run's reply: from its step's metadata, or from the answer
 * event's `claims` when the step is missing. None when the run had no claim check.
 */
export function runClaims(t: Turn, run: number): Claims | undefined {
  const step = findLast(t.steps, (s) => s.run === run && s.name === "claims");
  const fromAnswer = runReply(t, run)?.claims;
  if (!step && !fromAnswer) return undefined;
  const m = (step?.meta ?? {}) as ClaimsMeta;
  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : undefined);
  const sentences = (Array.isArray(m.removed_sentences) ? m.removed_sentences : (fromAnswer?.removed ?? [])).map(String);
  return {
    step,
    skipped: m.decided_by === "skipped",
    checked: num(m.checked) ?? num(fromAnswer?.checked) ?? 0,
    supported: num(m.supported) ?? 0,
    general: num(m.general) ?? 0,
    removed: num(m.removed) ?? sentences.length,
    sentences,
    reworded: (Array.isArray(m.reworded_sentences) ? m.reworded_sentences : [])
      .filter((p): p is [string, string] => Array.isArray(p) && p.length === 2)
      .map(([a, b]) => [String(a), String(b)] as [string, string]),
    note: typeof m.note === "string" && m.note ? m.note : undefined,
  };
}

/** The generated-model results a run sent. */
export function runResults(t: Turn, run: number): ModelResult[] {
  return (t.results ?? []).filter((r) => r.run === run).map((r) => r.value);
}
