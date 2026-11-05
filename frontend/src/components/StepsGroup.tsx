// The agent's process as rows that tick off: one row per step, live while the run streams.

import { useEffect, useRef } from "react";

import { DEVICE_NAMES } from "../agent/models";
import { DESIGN_CODE, doubletLines, shownValue } from "../agent/numbers";
import { answerText, asksOf, behaviour, runClaims, runReply, screened, stepModel, turnTotals } from "../agent/reducer";
import type { AnswerMeta, DoubletBuild, Step, Turn } from "../agent/types";
import { KEEP_OPEN } from "../state/flags";
import { AgentsPanel } from "./AgentsPanel";
import { fmtSeconds, fmtTokens, fmtWh } from "./Header";
import { Chevron, DoneIcon, FailIcon, Spinner, StoppedIcon, ThinkingDots, WaitingIcon } from "./Icons";

interface Props {
  turn: Turn;
  open: boolean;
  onToggle: () => void;
  focusKey: string | null;
  now: number;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function StepsGroup({ turn, open, onToggle, focusKey, now }: Props) {
  const totals = turnTotals(turn);
  const active = [...turn.steps].reverse().find((s) => s.status === "active");
  const offline = turn.usage.some((u) => !u.ok);
  const b = behaviour(turn);
  const live = totals.seconds + Math.max(0, (now - turn.activeSince) / 1000);

  let icon = <ThinkingDots />;
  // Before the first step: the message's files may still be uploading (the run waits for them).
  const uploading = !turn.runs.length && turn.attachments?.some((a) => a.uploading);
  let title = active?.label ?? (turn.steps.length ? "Working" : uploading ? "Uploading your files" : "Reading your request");
  let busy = true;
  const chips: { text: string; tone?: "amber" | "red" | "teal"; title?: string }[] = [];
  if (turn.reasoning || turn.runs.some((r) => r.summary?.reasoning)) chips.push({ text: "reasoning", tone: "teal" });
  switch (turn.status) {
    case "running":
      chips.push({ text: plural(turn.steps.length, "step", "steps") }, { text: fmtSeconds(live) });
      break;
    case "waiting": {
      const n = turn.clarification?.questions.length ?? 1;
      icon = <WaitingIcon />;
      const kind = turn.clarification?.kind;
      title =
        kind === "decision"
          ? "Waiting for your decision"
          : kind === "offer"
            ? "Waiting for your go-ahead"
            : kind === "approval"
              ? "Waiting for your approval"
              : kind === "choice"
                ? "Waiting for your choice"
                : kind === "confirm"
                  ? // After "Change an input first" the agent waits for the change itself.
                    asksOf(turn).at(-1)?.answers
                    ? "Waiting for what to change"
                    : "Waiting for your go-ahead on the inputs"
                  : `Waiting for ${plural(n, "input", "inputs")}`;
      busy = false;
      chips.push({ text: plural(turn.steps.length, "step", "steps") }, { text: fmtSeconds(totals.seconds) });
      break;
    }
    case "done":
      icon = turn.unavailable ? <WaitingIcon /> : <DoneIcon />;
      title = turn.unavailable
        ? "Couldn't read the request"
        : `${b === "refuse" || b === "reject" || b === "nonsense" ? "Answered in" : "Worked for"} ${fmtSeconds(totals.seconds)}`;
      busy = false;
      chips.push(
        { text: plural(turn.steps.length, "step", "steps") },
        { text: totals.llmCalls ? plural(totals.llmCalls, "model call", "model calls") : "no model call" },
        { text: `${fmtTokens(totals.tokens)} tokens` },
      );
      // Measured on the GPU while the turn ran (none on the CPU switch).
      if (totals.energyWh > 0)
        chips.push({ text: fmtWh(totals.energyWh), title: "GPU energy measured while this turn ran (the whole GPU, so an upper bound)" });
      break;
    case "error":
      icon = <FailIcon />;
      title = "Stopped on an error";
      busy = false;
      chips.push({ text: plural(turn.steps.length, "step", "steps") });
      break;
    case "stopped":
      icon = <StoppedIcon />;
      title = "Stopped";
      busy = false;
      chips.push({ text: plural(turn.steps.filter((s) => s.status === "done").length, "step", "steps") + " done" });
      break;
  }
  if (totals.toolErrors > 0) chips.push({ text: plural(totals.toolErrors, "tool failed", "tools failed"), tone: "red" });
  if (turn.status === "done" && totals.cacheHits > 0) chips.push({ text: plural(totals.cacheHits, "cache hit", "cache hits") });
  if (offline) chips.push({ text: turn.unavailable?.fallback ? "rules took over" : "model unavailable", tone: "amber" });

  return (
    <section className="card steps ta-rise" aria-label="Agent steps">
      <button type="button" className="steps-head" onClick={onToggle} aria-expanded={open}>
        {icon}
        <span className={`steps-title${busy ? " ta-shimmer" : ""}`} aria-live="polite">
          {title}
        </span>
        <span className="chips">
          {chips.map((c) => (
            <span key={c.text} className={`chip${c.tone ? ` chip-${c.tone}` : ""}`} title={c.title}>
              {c.text}
            </span>
          ))}
          <Chevron open={open} />
        </span>
      </button>
      <div className="ta-collapse" style={{ gridTemplateRows: open ? "1fr" : "0fr", opacity: open ? 1 : 0 }}>
        <div>
          <AgentsPanel turn={turn} />
          <ol>
            {turn.steps.map((s) => (
              <StepRow key={s.key} step={s} turn={turn} focus={s.key === focusKey} />
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function StepRow({ step, turn, focus }: { step: Step; turn: Turn; focus: boolean }) {
  const icon =
    step.status === "done" ? (
      <DoneIcon />
    ) : step.status === "active" ? (
      <Spinner />
    ) : step.status === "waiting" ? (
      <WaitingIcon />
    ) : step.status === "error" ? (
      <FailIcon />
    ) : (
      <StoppedIcon />
    );
  const { tags, subs, chips } = details(step, turn);
  const alts = alternatives(step, turn);
  const decided = typeof step.meta.decided_by === "string" ? step.meta.decided_by : undefined;
  // The answerer's step: the model that wrote the reply and where it ran, or the template.
  const reply = step.name === "answer" ? runReply(turn, step.run) : undefined;
  // The claim checker: a model reads the reply's sentences against its sources.
  const claims = step.name === "claims";
  const writer = step.name === "answer" || claims ? writerOf(step, turn, reply) : null;
  const right =
    step.status === "done" && step.seconds != null
      ? fmtSeconds(step.seconds)
      : step.status === "waiting"
        ? "paused"
        : step.status === "stopped"
          ? "stopped"
          : "";
  return (
    <li
      className={`step ta-row${step.status === "error" ? " is-error" : ""}${focus ? " is-focus" : ""}`}
      data-step={step.name}
      id={`step-${turn.id}-${step.key.replace(/[^\w-]/g, "_")}`}
    >
      {icon}
      <span className="step-main">
        <span className="step-line">
          <span className={`step-label${step.status === "active" ? " ta-shimmer" : ""}`}>
            {step.status === "error" && <span className="sr-only">Failed: </span>}
            {step.label}
          </span>
          {step.code && <code className="code">{step.code}</code>}
          {claims && decided === "skipped" ? (
            <span className="tag tag-grey">skipped</span>
          ) : writer && decided ? (
            decided === "model" ? (
              <span className="tag tag-teal">{writer}</span>
            ) : (
              <span className="tag tag-grey">checked template</span>
            )
          ) : decided ? (
            decided === "model" ? (
              <span className="tag tag-teal">{stepModel(turn, step) ?? "model"} decided</span>
            ) : (
              <span className="tag tag-grey">rules decided</span>
            )
          ) : (
            step.kind === "model" &&
            (screened(turn, step.run) && step.name !== "answer" && !claims ? <span className="tag tag-grey">keyword screen</span> : <span className="tag tag-teal">model call</span>)
          )}
          {step.kind === "ask" && <span className="tag tag-amber">your input</span>}
          {tags.map((t) => (
            <span key={t.text} className={`tag tag-${t.tone}`}>
              {t.text}
            </span>
          ))}
        </span>
        {alts.length > 0 && (
          <span className="alts">
            {alts.map((a) => (
              <span key={a.code + a.name} className="alt">
                {a.code && <b>{a.code}</b>}
                {a.name}
              </span>
            ))}
          </span>
        )}
        {chips.length > 0 && (
          <span className="alts" aria-label={chipsLabel(step)}>
            {chips.map((c) => (
              <span key={c.code + c.name} className={`alt${c.mono ? " alt-mono" : ""}`} title={c.title}>
                {c.code && <b>{c.code}</b>}
                {c.name}
              </span>
            ))}
          </span>
        )}
        {subs.map((t) => (
          <span key={t.text} className="step-sub" style={t.color ? { color: t.color } : undefined}>
            {t.text}
          </span>
        ))}
        {(decided || reply) && !claims && <Decision step={step} reply={reply} />}
        {claims && step.status !== "active" && <ClaimsDetail step={step} turn={turn} open={focus} />}
        {step.name.startsWith("modelgen-") && <GenNote step={step} />}
      </span>
      <span className="step-right" style={step.status === "error" ? { color: "#A12C22", fontWeight: 650 } : undefined}>
        {right}
      </span>
    </li>
  );
}

/**
 * The claim checker's account: how many sentences it checked and, folded, the ones it took out
 * of the reply, struck through. Opened when the reply's "claims removed" chip points here.
 */
function ClaimsDetail({ step, turn, open }: { step: Step; turn: Turn; open: boolean }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (open && ref.current) ref.current.open = true;
  }, [open]);
  const c = runClaims(turn, step.run);
  if (!c) return null;
  if (c.skipped)
    return <span className="step-sub">{c.note ? `Skipped: ${c.note.replace(/\.$/, "")}.` : "Skipped: the reply was sent unchecked."}</span>;
  const checked = plural(c.checked, "claim", "claims");
  const general = c.general > 0 ? ` (${c.general} as general background)` : "";
  const note = c.note && <span className="step-sub" style={{ color: "#8A5A00" }}>{c.note}</span>;
  if (!c.checked) return <span className="step-sub">No claims to check.{note}</span>;
  const mended = c.reworded.length;
  if ((!c.removed || !c.sentences.length) && !mended)
    return (
      <>
        <span className="step-sub">
          {c.removed ? `${checked} checked · ${c.removed} removed` : `${checked} checked, all supported${general}`}
        </span>
        {note}
      </>
    );
  return (
    <details ref={ref} className="reasoning claims" open={KEEP_OPEN || undefined}>
      <summary>
        <span>
          {checked} checked
          {mended > 0 && <> · {mended} reworded</>}
          {c.removed > 0 && (
            <>
              {" "}
              · <span className="claims-removed-n">{c.removed} removed</span>
            </>
          )}
        </span>
      </summary>
      {mended > 0 && (
        <>
          <span className="claims-why">Close to the sources but worded wrong, so {mended === 1 ? "it was" : "they were"} reworded to say only what the sources say.</span>
          <ul className="claims-list claims-mended">
            {c.reworded.map(([was, now]) => (
              <li key={was}>
                <span className="sr-only">Was: </span>
                <del>{was}</del>
                <span className="sr-only"> Now: </span>
                <ins>{now}</ins>
              </li>
            ))}
          </ul>
        </>
      )}
      {c.sentences.length > 0 && (
        <>
          <span className="claims-why">Not supported by the sources, so {c.sentences.length === 1 ? "it was" : "they were"} taken out of the reply.</span>
          <ul className="claims-list">
            {c.sentences.map((t) => (
              <li key={t}>
                <span className="sr-only">Removed: </span>
                <del>{t}</del>
              </li>
            ))}
          </ul>
        </>
      )}
      {note}
    </details>
  );
}

/** Which design a tool call was for, from its arguments ({"alternative": {"code": "A2"}} or "A2"). */
function callTarget(args: string): string | null {
  try {
    const a = JSON.parse(args);
    const alt = a?.alternative;
    if (typeof alt === "string") return alt;
    if (alt && typeof alt.code === "string") return alt.code;
    if (typeof a?.depth_m === "number") return `${a.depth_m} m`;
  } catch {
    /* args still streaming */
  }
  return null;
}

/** The plan's alternatives, paired with their codes (from the call, or the run's summary). */
function alternatives(step: Step, turn: Turn): { code: string; name: string }[] {
  const names = step.meta.alternatives;
  if (!Array.isArray(names) || !names.length) return [];
  let codes = Array.isArray(step.meta.codes) ? step.meta.codes.map(String) : [];
  if (codes.length !== names.length)
    codes = (step.code?.match(/\(([^)]*)\)/)?.[1] ?? "").split(",").map((c) => c.trim()).filter((c) => /^[A-Z]\d+$/.test(c));
  if (codes.length !== names.length) codes = turn.runs[step.run]?.summary?.plan ?? [];
  return names.map((name, i) => ({ code: codes.length === names.length ? codes[i] : "", name: String(name) }));
}

/** "qwen3.5:9b · GPU": the answer step's model and device, from its metadata or the answer event. */
function writerOf(step: Step, turn: Turn, reply?: AnswerMeta): string {
  const m = step.meta;
  const model = (typeof m.model === "string" && m.model) || reply?.model || stepModel(turn, step) || "model";
  const device = (typeof m.device === "string" ? m.device : reply?.device) as keyof typeof DEVICE_NAMES | undefined;
  return device && DEVICE_NAMES[device] ? `${model} · ${DEVICE_NAMES[device]}` : model;
}

const WHOLE_CODE = new RegExp(`^(?:${DESIGN_CODE.source})$`);
const BLOCKS: Record<string, string> = {
  self: "what Dioscuri is",
  draft: "the checked draft",
  designs: "the designs so far",
  search: "the design search",
  history: "earlier messages",
  gemini: "the design's GEMINI project",
  facts: "project data",
  project: "project data",
};
const PASSAGES: Record<string, string> = { doc: "passage", note: "team note", file: "your file", data: "data file" };

/** What an answer drew on: context blocks ("self", "draft"), designs ("2D-HP-AB"), passages ("doc1"). */
export function usedLabel(id: string): { code?: string; name: string } {
  if (BLOCKS[id]) return { name: BLOCKS[id] };
  if (/^[A-Z]\d+$/.test(id) || WHOLE_CODE.test(id)) return { code: id, name: "design" };
  const costs = id.match(/^(.+) costs$/);
  if (costs) return { code: costs[1], name: "cost lines" };
  const passage = id.match(/^(doc|note|file|data)(\d+)$/);
  if (passage) return { code: `${passage[1]} ${passage[2]}`, name: PASSAGES[passage[1]] };
  return { name: id };
}

/** A generation attempt: what the model says it wrote (or changed after a failed attempt). */
function GenNote({ step }: { step: Step }) {
  const reason = typeof step.meta.reason === "string" ? step.meta.reason : "";
  if (!reason) return null;
  return (
    <details className="reasoning" open={KEEP_OPEN || undefined}>
      <summary>What the model says it {/^the previous|fixed|corrected/i.test(reason) ? "changed" : "wrote"}</summary>
      <p className="gen-reason">{reason}</p>
    </details>
  );
}

const FIXES: Record<string, string> = {
  allow: "allow the ruled-out equipment",
  deeper: "a deeper doublet",
  cascade: "the standard cascade",
};

/**
 * A decision step's account: why (reason), how (the model's reasoning steps, folded), what code
 * changed in the model's choice (corrections, marked "checked by code") and why rules took over.
 */
function Decision({ step, reply }: { step: Step; reply?: AnswerMeta }) {
  const m = step.meta as Record<string, unknown>;
  const reason = typeof m.reason === "string" ? m.reason : "";
  const lines = Array.isArray(m.steps) ? m.steps.map(String) : [];
  // The answer step's corrections, and the answer event's (the same list, or the event's alone).
  const corrections = [...new Set([...(Array.isArray(m.corrections) ? m.corrections.map(String) : []), ...(reply?.corrections ?? [])])];
  const note = typeof m.note === "string" ? m.note : "";
  const tries = Array.isArray(m.try) ? m.try.map(String) : [];
  const understood = (typeof m.understood === "string" && m.understood) || reply?.understood || "";
  const used = reply?.used ?? [];
  const answer = step.name === "answer";
  return (
    <span className="decision-detail">
      {understood && (
        <span className="understood">
          <span className="understood-label">Understood</span>
          <span>{understood}</span>
        </span>
      )}
      {used.length > 0 && (
        <span className="alts" aria-label="What the answer drew on">
          <span className="alts-label">Drew on</span>
          {used.map((u) => {
            const l = usedLabel(u);
            return (
              <span key={u} className={`alt${l.code ? "" : " plain"}`}>
                {l.code && <b>{l.code}</b>}
                {l.name}
              </span>
            );
          })}
        </span>
      )}
      {reason && <span className="decision-reason">{reason}</span>}
      {tries.length > 0 && (
        <span className="alts">
          {tries.map((t) => (
            <span key={t} className="alt">
              <b>try</b>
              {FIXES[t] ?? t}
            </span>
          ))}
        </span>
      )}
      {lines.length > 0 && (
        <details className="reasoning" open={KEEP_OPEN || undefined}>
          <summary>
            Reasoning <span className="note">· {lines.length} {lines.length === 1 ? "step" : "steps"}</span>
          </summary>
          <ol>
            {lines.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ol>
        </details>
      )}
      {corrections.map((c) => (
        <span key={c} className="correction">
          <span className="by-code">
            <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 1.6 13.4 3.6v4.2c0 3.2-2.3 5.6-5.4 6.6-3.1-1-5.4-3.4-5.4-6.6V3.6z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              <path d="M5.6 8.1 7.3 9.8l3.2-3.4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            checked by code
          </span>
          <span>{c}</span>
        </span>
      ))}
      {note && (
        <span className="step-sub" style={{ color: "#8A5A00" }}>
          {answer ? (step.meta.decided_by === "rules" ? `Checked template shown: ${note.replace(/\.$/, "")}.` : note) : `Rules took over: ${note}.`}
        </span>
      )}
    </span>
  );
}

type Tone = "teal" | "amber" | "ok" | "red" | "grey";

export interface StepChip {
  code: string;
  name: string;
  title?: string;
  /** A parameter key, set in the code font. */
  mono?: boolean;
}

export interface StepDetails {
  tags: { text: string; tone: Tone }[];
  subs: { text: string; color?: string }[];
  /** What the step read or found, as chips under its label (changes, doublets, a pick). */
  chips: StepChip[];
}

function chipsLabel(step: Step): string {
  if (step.name === "parameters") return "What the message sets or changes";
  if (step.name === "search") return "What the search picks";
  return "Details";
}

const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x) => x != null && x !== "").map((x) => (typeof x === "string" ? x : shownValue(x))) : []);

const CONFIRMED: Record<string, { tag: string; tone: Tone; sub: string }> = {
  run: { tag: "run the design", tone: "ok", sub: "Read as a go-ahead: the design runs with the inputs shown." },
  change: { tag: "change an input", tone: "amber", sub: "Read as a change to the inputs: they are shown again with it." },
  other: { tag: "not about the inputs", tone: "grey", sub: "Read as a new message: the inputs card is set aside." },
};

/** The search a tool step ran, from its call's result: what it tried and what it picked. */
function searchOf(step: Step): { chosen?: string; candidates?: number; valid?: number } | null {
  const raw = step.tools.find((c) => c.name === "search_designs" && c.result)?.result;
  if (!raw) return null;
  try {
    const r = (JSON.parse(raw) as { result?: { chosen?: unknown; summary?: { candidates?: unknown; valid?: unknown } } }).result;
    if (!r || typeof r !== "object") return null;
    const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : undefined);
    return { chosen: typeof r.chosen === "string" && r.chosen ? r.chosen : undefined, candidates: num(r.summary?.candidates), valid: num(r.summary?.valid) };
  } catch {
    return null;
  }
}

/** The extra facts a step reports (STEP_FINISHED metadata), as tags, chips and one-line notes. */
export function details(step: Step, turn: Turn): StepDetails {
  const m = step.meta as Record<string, unknown>;
  const tags: { text: string; tone: Tone }[] = [];
  const subs: { text: string; color?: string }[] = [];
  const chips: StepChip[] = [];
  if (step.name === "parameters" && step.status !== "active") {
    // What the reader took from the message, each change as the key it set and its value.
    const changes = m.changes && typeof m.changes === "object" && !Array.isArray(m.changes) ? Object.entries(m.changes as Record<string, unknown>) : [];
    for (const [key, value] of changes) chips.push({ code: key, name: `→ ${shownValue(value)}`, mono: true });
    const lines = doubletLines(Array.isArray(m.doublets) ? (m.doublets as DoubletBuild[]) : [], "described");
    for (const line of lines) {
      const at = line.indexOf(": ");
      chips.push({ code: line.slice(0, at), name: line.slice(at + 2), title: "A doublet as the message describes it" });
    }
    const unsupported = strings(m.unsupported);
    const dropped = strings(m.dropped);
    if (!changes.length && !lines.length && !unsupported.length) tags.push({ text: "nothing to change", tone: "grey" });
    if (unsupported.length) subs.push({ text: `Not in the model, so not changed: ${unsupported.join("; ")}`, color: "#8A5A00" });
    for (const d of dropped) subs.push({ text: `Set aside by the checks: ${d}`, color: "#8A5A00" });
  }
  if (step.name === "confirm" && step.status !== "active") {
    const said = CONFIRMED[typeof m.decision === "string" ? m.decision : ""];
    if (said) {
      tags.push({ text: said.tag, tone: said.tone });
      subs.push({ text: said.sub });
    }
  }
  if (step.name === "load_model") {
    // Loading a model into memory before the first call (warmup.py): once, then it stays.
    if (step.status === "active") subs.push({ text: "Only the first message waits for this: the model then stays in memory." });
    else if (typeof m.error === "string" && m.error) subs.push({ text: typeof m.hint === "string" && m.hint ? `${m.error}. ${m.hint}` : m.error, color: "#8F1D14" });
    else tags.push({ text: "in memory", tone: "ok" });
  }
  if (step.name === "inputs") {
    if (typeof m.rows === "number") tags.push({ text: plural(m.rows, "input", "inputs"), tone: "grey" });
    if (typeof m.assumed === "number" && m.assumed > 0) tags.push({ text: `${m.assumed} assumed`, tone: "amber" });
  }
  if (step.name === "edits") {
    // The inputs card's own changes, checked by code (card_edits.py).
    if (Array.isArray(m.changed) && m.changed.length) tags.push({ text: `${plural(m.changed.length, "change", "changes")} applied`, tone: "grey" });
    if (Array.isArray(m.refused) && m.refused.length) tags.push({ text: `${m.refused.length} refused`, tone: "amber" });
  }
  if (step.name === "search") {
    const found = searchOf(step);
    if (found?.candidates != null) tags.push({ text: found.valid != null && found.valid !== found.candidates ? `${found.valid} of ${found.candidates} designs meet the caps` : plural(found.candidates, "design", "designs"), tone: "grey" });
    if (found?.chosen) {
      const base = turn.steps.find((s) => s.run === step.run && s.name === "plan")?.meta.reused;
      chips.push({ code: found.chosen, name: found.chosen === base ? "picked again, sized for the change" : "the best under the change" });
    }
  }
  if (step.kind === "model") {
    const call = turn.usage.find((u) => u.purpose === step.name) ?? turn.usage[0];
    // The keyword screen reads the request; the answerer still writes the reply with a model.
    if (step.name !== "answer" && step.name !== "claims" && (screened(turn, step.run) || m.screened === true)) subs.push({ text: "Read by keyword rules; no model call was needed." });
    else if (call && !call.ok) subs.push({ text: "The model didn't answer.", color: "#8A5A00" });
    else if (typeof m.tokens === "number" && m.tokens > 0) tags.push({ text: `${fmtTokens(m.tokens)} tokens`, tone: "grey" });
  }
  const cached = step.tools.filter((c) => c.cached).length;
  if (cached) tags.push({ text: cached === step.tools.length ? "from cache" : `${cached} of ${step.tools.length} from cache`, tone: "teal" });
  const broken = step.tools.filter((c) => c.error);
  if (broken.length) {
    tags.push({ text: `${broken.length} of ${step.tools.length} failed`, tone: "red" });
    for (const c of broken) subs.push({ text: `${callTarget(c.args) ?? c.name}: ${c.error}`, color: "#8F1D14" });
  }
  if (Array.isArray(m.not_modelled) && m.not_modelled.length)
    subs.push({ text: `Not modelled yet: ${m.not_modelled.join("; ")}`, color: "#8A5A00" });
  if (typeof m.reused === "string") subs.push({ text: `Reused ${m.reused} from earlier in this chat` });
  if (typeof m.passed === "number" && typeof m.total === "number")
    tags.push({ text: `${m.passed} of ${m.total} pass`, tone: m.passed === m.total ? "ok" : "red" });
  if (step.name.startsWith("modelgen-")) {
    const n = Number(step.name.slice(9));
    const attempt = (turn.attempts ?? []).find((a) => a.number === n);
    if (m.passed === true) {
      const k = attempt?.checks.length;
      tags.push({ text: k ? `passed ${k} of ${k} checks` : "passed", tone: "ok" });
    } else if (m.passed === false) tags.push({ text: "failed in the sandbox", tone: "red" });
    if (attempt?.sandbox_seconds != null) tags.push({ text: `sandbox ${fmtSeconds(attempt.sandbox_seconds)}`, tone: "grey" });
    const problems = Array.isArray(m.problems) ? m.problems.map(String) : [];
    for (const p of problems.slice(0, 3)) subs.push({ text: p, color: "#8F1D14" });
    if (problems.length > 3) subs.push({ text: `… and ${problems.length - 3} more`, color: "#8F1D14" });
  }
  if (step.name === "register" && typeof m.saved === "boolean") tags.push(m.saved ? { text: "saved", tone: "ok" } : { text: "not saved", tone: "red" });
  if (step.name === "use_model") {
    if (typeof m.cases === "number") tags.push({ text: plural(m.cases, "case", "cases"), tone: "grey" });
    if (m.passed === true) tags.push({ text: "checks pass", tone: "ok" });
  }
  if (step.name === "docs") {
    if (step.tools.some((c) => /"only_attached":\s*true/.test(c.args))) tags.push({ text: "attachments only", tone: "teal" });
    if (typeof m.passages === "number") tags.push({ text: plural(m.passages, "passage", "passages"), tone: "grey" });
    if (typeof m.backend === "string") tags.push({ text: m.backend, tone: "grey" });
    if (typeof m.suspicious === "number" && m.suspicious > 0) tags.push({ text: `${m.suspicious} flagged, ignored`, tone: "red" });
  }
  if (Array.isArray(m.found)) for (const k of m.found) tags.push({ text: `found ${String(k).replace(/_/g, " ")}`, tone: "ok" });
  if (Array.isArray(m.missing)) for (const k of m.missing) tags.push({ text: `no ${String(k).replace(/_/g, " ")} yet`, tone: "amber" });
  if (typeof m.options === "number") tags.push({ text: plural(m.options, "option", "options"), tone: "grey" });
  if (Array.isArray(m.ungrounded) && (m.ungrounded.length || /\d/.test(answerText(turn))))
    tags.push(
      m.ungrounded.length
        ? { text: `${plural(m.ungrounded.length, "number", "numbers")} not traced`, tone: "red" }
        : { text: "every number traced", tone: "ok" },
    );
  if (step.status === "error" && !broken.length && turn.error) subs.push({ text: turn.error.message, color: "#8F1D14" });
  return { tags, subs, chips };
}
