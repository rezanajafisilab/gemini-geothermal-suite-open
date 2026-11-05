// The inputs card (CUSTOM "confirm_inputs", then a clarification of kind "confirm"): before the
// first design of a chat the agent shows every input it will use, on pages (Demand, Reservoir
// and wells, Brine and gas, Networks, Prices, Your request, Limits) and a review page. Every
// box can be changed at once; each says what it is, where its value comes from, and its issues
// as it is typed: what blocks the run (red), a warning (amber: it still runs) and what follows
// (InputsPage, inputsForm.checkCard). Run sends {"confirm": <first option>} with the switches,
// the Maintenance section and the changed boxes ({"changes": "<json>"}); the server checks them
// again (what it refuses comes back as a new card, the reasons on the boxes). Run is on the
// review page only; every other page has Back and Next. What the user set in the message is
// marked, with what it affects (a banner, and a mark on each linked box). The box at the foot
// sends a normal chat message, which the agent reads as a reply to the card. Once answered the
// card folds to one line that says what happened (with the rows as they ran), and can be opened
// again. Without the "confirm_inputs" event (an older server) the card shows the agent's table.

import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";

import { textWithFiles } from "../agent/markdown";
import type { ConfirmReply } from "../agent/reducer";
import type { Ask, CardNotice, ConfirmInputs, InputRow, InputToggle, Turn } from "../agent/types";
import { Arrow, Spinner } from "./Icons";
import { Ico } from "./InputsIcons";
import "./InputsCard.css";
import {
  type FieldEdit,
  type PageState,
  type ToggleState,
  PAGE_WORDS,
  ParamField,
  REVIEW,
  RowBlock,
  SOURCE_WORDS,
  StepBar,
  ToggleRow,
  YoursBanner,
  amountProblem,
  hasAmount,
  pageOfRow,
  pageOfToggle,
  pagesOf,
  wasText,
} from "./InputsPage";
import { MaintenanceEditor } from "./Maintenance";
import {
  type Draft,
  type Issue,
  type MaintenanceState,
  type StopsState,
  canReset,
  changedKeys,
  changesOf,
  checkCard,
  dateOf,
  followTiles,
  productionC,
  recordsChanges,
  dayName,
  dayOf,
  daysOf,
  daysOff,
  daysOffProblem,
  daysOffOf,
  doubletCount,
  fieldText,
  fieldsOf,
  fieldValue,
  initialDraft,
  initialMaintenance,
  initialStops,
  maintenanceAnswers,
  maintenanceFor,
  operatingDaysOf,
  rangesOf,
  serviceProblem,
  stopsAnswer,
  stopsFor,
  stopsProblems,
  stopsTogether,
  toggleWarnings,
  YEAR,
} from "./inputsForm";
import { FileRef, Markdown } from "./Markdown";

export { hasAmount, type ToggleState };

/**
 * The event a card sends (bubbling, cancelable) to have its top scrolled into view: the chat's
 * scroller handles it (App), and cancels it; uncaught, the card scrolls itself.
 */
export const REVEAL_TOP = "dioscuri:reveal-top";

/** Bring a card's top into view: the chat's scroller moves (App), else the browser's own. */
export function revealTop(el: HTMLElement | null) {
  if (!el) return;
  const handled = !el.dispatchEvent(new Event(REVEAL_TOP, { bubbles: true, cancelable: true }));
  if (!handled) el.scrollIntoView?.({ block: "start", behavior: "smooth" });
}

export const RUN_OPTION = "Run the design with these inputs";
export const CHANGE_OPTION = "Change an input first";
/** The card's "Reset to defaults" (5 Nov): the server puts every input back to the project's own. */
export const RESET_OPTION = "Reset the inputs to the defaults";
export const CONFIRM_EDITS = "Run with your changes";
const PLACEHOLDER = "Or type what to change, e.g. a 50 °C heating return";

/** The kinds in the order the overview lists them, with the words the agent uses for each. */
export const KINDS: { id: string; words: string }[] = [
  { id: "data", words: "read from the files" },
  { id: "fixed", words: "fixed by the requirements" },
  { id: "derived", words: "worked out by Dioscuri" },
  { id: "assumed", words: "Dioscuri's assumption" },
  { id: "asked", words: "your request" },
];

export interface InputGroup {
  name: string;
  rows: InputRow[];
}

/** The rows by group, groups in the order they first appear (the agent sends them in order). */
export function groupRows(rows: InputRow[]): InputGroup[] {
  const groups: InputGroup[] = [];
  for (const row of rows) {
    const name = row.group || "Other";
    let g = groups.find((x) => x.name === name);
    if (!g) groups.push((g = { name, rows: [] }));
    g.rows.push(row);
  }
  return groups;
}

/** How many rows of each kind, known kinds first in their order, then any other kind. */
export function kindCounts(rows: InputRow[], kinds: Record<string, string> = {}): { id: string; words: string; n: number }[] {
  const ids = [...KINDS.map((k) => k.id), ...rows.map((r) => r.kind).filter((k) => !KINDS.some((x) => x.id === k))];
  return [...new Set(ids)]
    .map((id) => ({ id, words: kinds[id] ?? KINDS.find((k) => k.id === id)?.words ?? id, n: rows.filter((r) => r.kind === id).length }))
    .filter((k) => k.n > 0);
}

/** The run and change options: the card's, else the question's, else the agent's defaults. */
export function confirmOptions(ask: Ask, inputs?: ConfirmInputs): [string, string] {
  const q = ask.value.questions?.[0];
  const list = inputs?.options?.length && inputs.options.length >= 2 ? inputs.options : q?.options && q.options.length >= 2 ? q.options : [RUN_OPTION, CHANGE_OPTION];
  return [list[0], list[1]];
}

/**
 * What a card's answer led to, in the run right after the card's: the rows that ran (a
 * "confirm_inputs" marked applied: Run with changes), or the card again with the changes the
 * server refused (its `errors`). Undefined when Run changed nothing.
 */
export function afterInputs(turn: Turn, run: number): ConfirmInputs | undefined {
  return (turn.confirms ?? []).find((c) => c.run === run + 1 && (c.value.applied || Object.keys(c.value.errors ?? {}).length))?.value;
}

export type SummaryTone = "ok" | "amber" | "grey" | "busy";

/**
 * The folded card's line: what the answer did. A click on Run or Change answers the card; a
 * message sent instead (`skipped`) is read by the next turn's "confirm" step (`reply`). An
 * unanswered card that nothing skipped is a question the agent no longer has (it restarted).
 */
export function confirmSummary(ask: Ask, options: [string, string], reply?: ConfirmReply, skipped = true, after?: ConfirmInputs): { tone: SummaryTone; title: string; note?: string } {
  const id = ask.value.questions?.[0]?.id ?? "confirm";
  const answer = (ask.answers?.[id] ?? Object.values(ask.answers ?? {})[0] ?? "").trim();
  if (answer && Object.keys(after?.errors ?? {}).length) return { tone: "amber", title: "Not run yet", note: "a change was refused: see the card below" };
  if (answer === RESET_OPTION) return { tone: "grey", title: "Inputs reset", note: "back to the project's defaults" };
  if (answer) {
    // As the agent reads it: the run option, or anything that starts with "run".
    if (answer === options[0] || /^run\b/i.test(answer)) {
      const n = Object.keys(parseObject(ask.answers?.changes)).length;
      return n ? { tone: "ok", title: "Inputs confirmed", note: "with your changes" } : { tone: "ok", title: "Inputs confirmed" };
    }
    if (answer === options[1]) return { tone: "amber", title: "Changing an input" };
    return { tone: "grey", title: "You replied", note: `“${answer}”` };
  }
  if (!skipped) return { tone: "grey", title: "Inputs not confirmed", note: "the question is no longer open" };
  if (reply === "run") return { tone: "ok", title: "Inputs confirmed", note: "by your message" };
  if (reply === "change") return { tone: "amber", title: "Changing an input", note: "as your message asks" };
  if (reply === "reset") return { tone: "grey", title: "Inputs reset", note: "back to the project's defaults, as your message asks" };
  if (reply === "refused") return { tone: "amber", title: "Nothing changed", note: "your change could not be taken: see the card below" };
  if (reply === "reading") return { tone: "busy", title: "Reading your reply" };
  if (reply === "other") return { tone: "grey", title: "Inputs not confirmed", note: "your message asked something else" };
  return { tone: "grey", title: "Inputs not confirmed", note: "you sent a new message" };
}

function parseObject(text: string | undefined): Record<string, unknown> {
  try {
    const v = text ? JSON.parse(text) : {};
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch {
    return {};
  }
}

/** The intro's first sentence, the card's title; the rest of the intro is the table fallback. */
export function splitIntro(intro: string): [string, string] {
  const text = intro.trim();
  const m = text.match(/^([^\n]+?[.!?])(?:\s+|$)([\s\S]*)$/);
  return m ? [m[1], m[2].trim()] : [text.split("\n")[0], text.split("\n").slice(1).join("\n").trim()];
}

/** Each switch's state from the card's values (a switch with an amount is on when it is above 0). */
export function initialToggles(toggles: InputToggle[]): Record<string, ToggleState> {
  return Object.fromEntries(toggles.map((t) => [t.id, { on: t.value > 0, text: hasAmount(t) && t.value > 0 ? String(t.value) : "" }]));
}

/** A switch with an amount that is on needs an amount above 0 (and within its range) to run. */
export function togglesReady(toggles: InputToggle[], state: Record<string, ToggleState>): boolean {
  return toggles.every((t) => !amountProblem(t, state[t.id]));
}

/** The answers the switches send with Run: {network_length_km: "5", planned_service: "1"}. */
export function toggleAnswers(toggles: InputToggle[], state: Record<string, ToggleState>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const t of toggles) {
    const s = state[t.id];
    if (!s || t.kind === "stops") continue;
    out[t.id] = hasAmount(t) ? (s.on ? String(Number(s.text.replace(",", ".")) || 0) : "0") : s.on ? "1" : "0";
  }
  return out;
}

/** A switch's state in words ("on", "5 km", "off"). */
function toggleWords(t: InputToggle, s: ToggleState | undefined): string {
  if (!s?.on) return "off";
  return hasAmount(t) ? `${s.text || "?"} ${t.unit ?? "km"}` : "on";
}

/** One change of the card, for the review: where it is, what it was, what it is now. */
export interface ChangeLine {
  key: string;
  page: string;
  label: string;
  was: string;
  now: string;
}

/** The changed boxes and switches, in the pages' order. */
export function changeLines(rows: InputRow[], draft: Record<string, Draft>, toggles: InputToggle[], set: Record<string, ToggleState>, start: Record<string, ToggleState>): ChangeLine[] {
  const keys = new Set(changedKeys(rows, draft));
  const out: ChangeLine[] = [];
  for (const row of rows)
    for (const f of row.fields ?? []) {
      if (!keys.has(f.key)) continue;
      const d = draft[f.key];
      if (f.kind === "records") {
        // One line per record changed: a value, an aquifer added or removed.
        for (const c of recordsChanges(f, d)) out.push({ key: f.key, page: pageOfRow(row), label: c.label, was: c.was, now: c.now });
        continue;
      }
      const now =
        f.kind === "records"
          ? `${(d as string[][]).length} ${f.label.toLowerCase()}, edited`
          : f.kind === "choice"
            ? (f.words?.[String(d)] ?? String(d))
            : Array.isArray(d)
              ? (d as string[]).map((x) => f.words?.[x] ?? x).join(", ") || "none"
              : `${String(d).trim() || "empty"}${String(d).trim() && f.unit ? ` ${f.unit}` : ""}`;
      out.push({ key: f.key, page: pageOfRow(row), label: f.label === row.label ? f.label : `${row.label} · ${f.label}`, was: f.kind === "records" ? `${fieldText(f, f.value).length}` : wasText(f), now });
    }
  for (const t of toggles) {
    const a = toggleWords(t, start[t.id]);
    const b = toggleWords(t, set[t.id]);
    if (a !== b) out.push({ key: t.id, page: pageOfToggle(t), label: t.label, was: a, now: b });
  }
  return out;
}

interface Props {
  ask: Ask;
  /** The rows to show; missing when the server sent only the Markdown table (the intro). */
  inputs?: ConfirmInputs;
  /** What the answer led to (afterInputs): the rows that ran, shown folded, or a refusal. */
  after?: ConfirmInputs;
  /** Unique within the chat, for the card's ids. */
  id: string;
  active: boolean;
  /** A message was sent instead of an answer, and how the agent read it (the next turn's "confirm" step). */
  skipped?: boolean;
  reply?: ConfirmReply;
  /** A run is streaming: nothing can be sent. */
  running: boolean;
  onAnswer: (answers: Record<string, string>) => void;
  onSend: (text: string) => void;
  /** Open on this page (tests, a link to an input). */
  page?: string;
}

const none = () => false;
const noop = () => {};
const MAINT_KEYS = ["doublet_stops", "doublet_days_off", "service_plan"];

export function InputsCard({ ask, inputs, after, id, active, skipped = false, reply, running, onAnswer, onSend, page: startPage }: Props) {
  const options = confirmOptions(ask, inputs);
  const qid = ask.value.questions?.[0]?.id ?? "confirm";
  const [title, rest] = splitIntro(ask.value.intro || "Before I run the design, please check what I read and what I assume.");
  const rows = useMemo(() => inputs?.rows ?? [], [inputs]);
  const allToggles = inputs?.toggles ?? [];
  const toggles = allToggles.filter((t) => t.kind !== "stops" && t.kind !== "maintenance");
  // The Maintenance section (the doublets' stops and the units' service); "stops" from older servers.
  const stopsToggle = allToggles.find((t) => t.kind === "maintenance" || t.kind === "stops");
  const serverErrors = inputs?.errors ?? {};
  const ctx = inputs?.context ?? {};
  const pages = pagesOf(rows, allToggles, inputs?.pages);
  const [sent, setSent] = useState(false);
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [start] = useState<Record<string, ToggleState>>(() => initialToggles(toggles));
  const [set, setSet] = useState<Record<string, ToggleState>>(start);
  const [draft, setDraft] = useState<Record<string, Draft>>(() => initialDraft(rows, inputs?.asked));
  const [stale, setStale] = useState<Record<string, boolean>>({}); // server errors the user has edited since
  const [stopsAll, setStops] = useState<StopsState | null>(() => (stopsToggle ? initialStops(stopsToggle, inputs?.asked?.doublet_stops) : null));
  const [maintStart] = useState<MaintenanceState | null>(() => (stopsToggle?.kind === "maintenance" ? initialMaintenance(stopsToggle) : null));
  const [maintAll, setMaint] = useState<MaintenanceState | null>(maintStart);
  // The page open: where the server refused something, else the first (or the one asked for).
  const [page, setPage] = useState<string>(() => {
    if (startPage) return startPage;
    const bad = Object.keys(serverErrors)[0];
    if (bad && MAINT_KEYS.includes(bad)) return "limits";
    const row = bad ? rows.find((r) => r.fields?.some((f) => f.key === bad)) : undefined;
    const sw = bad ? allToggles.find((t) => t.id === bad) : undefined;
    return row ? pageOfRow(row) : sw ? pageOfToggle(sw) : (pages[0]?.id ?? REVIEW);
  });
  // A box to put the cursor in once its page shows: a key, "bad" (the first marked) or "first".
  const [focus, setFocus] = useState<string | null>(null);
  const cardRef = useRef<HTMLElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  // Next was pressed: once its page shows, the card's top comes into view (only on Next: Back and
  // the step bar leave the view where it is).
  const toTop = useRef(false);
  const uid = useId().replace(/:/g, "");
  useEffect(() => {
    if (!toTop.current) return;
    toTop.current = false;
    revealTop(cardRef.current);
  }, [page]);
  useEffect(() => {
    if (!focus || !panelRef.current) return;
    const panel = panelRef.current;
    const sel = "input:not([type=hidden]):not([disabled]), select:not([disabled])";
    const target = focus === "bad" ? panel.querySelector<HTMLElement>("[aria-invalid=true]") : panel.querySelector<HTMLElement>(`[data-key="${focus}"] input, [data-key="${focus}"] select`);
    (target ?? panel.querySelector<HTMLElement>(sel))?.focus({ preventScroll: true });
    setFocus(null);
  }, [focus, page]);

  if (!active) {
    const s = confirmSummary(ask, options, reply, skipped, after);
    const shown = after?.applied ? after : inputs;
    const all = shown?.rows ?? [];
    const changed = all.filter((r) => r.changed).length;
    const assumed = all.filter((r) => r.kind === "assumed").length;
    const count = all.length ? `${all.length} inputs${assumed ? ` · ${assumed} assumed` : ""}${changed ? ` · ${changed} changed` : ""}` : "";
    const body = shown ? <InputsTable inputs={shown} /> : rest ? <Markdown className="inputs-md" text={rest} cites={0} onCite={noop} hasSource={none} onSource={noop} /> : null;
    return (
      <section className={`card inputs-done tone-${s.tone} ta-rise`} aria-label={`${s.title}${s.note ? `, ${s.note}` : ""}`}>
        <div className="inputs-done-line">
          <SummaryIcon tone={s.tone} />
          <strong>{s.title}</strong>
          {s.note && <span className="note">{s.note}</span>}
          {count && <span className="chip">{count}</span>}
          {body && (
            <button type="button" className="link-btn inputs-show" aria-expanded={open} aria-controls={`${id}-rows`} onClick={() => setOpen(!open)}>
              {open ? "Hide the inputs" : "Show the inputs"}
            </button>
          )}
        </div>
        {open && body && (
          <div id={`${id}-rows`} className="inputs-done-body">
            {body}
          </div>
        )}
      </section>
    );
  }

  const off = sent || running;
  const keys = changedKeys(rows, draft);
  const changed = new Set(keys);
  const live = Object.fromEntries(Object.entries(serverErrors).filter(([k]) => !MAINT_KEYS.includes(k) && !stale[k]));
  const issues = checkCard(rows, draft, ctx, live);
  // A refusal of a key no box shows (the card's changes unreadable): said under the pages.
  const loose = Object.entries(live).filter(([k]) => !fieldsOf(rows).some((f) => f.key === k) && !toggles.some((t) => t.id === k));
  // A switch's amount the server refused (until it is edited), as its own check would say.
  const toggleBad = (t: InputToggle) => amountProblem(t, set[t.id]) ?? live[t.id] ?? null;
  const tWarn = toggleWarnings(set);
  const opDays = operatingDaysOf(rows, draft, stopsToggle?.operating_days ?? 330);
  // Days off are counted from the challenge's cap (330: 35 days), not from a cap raised earlier for
  // the user's own days off; from the operating days typed on this card, when changed here.
  const capOps = changed.has("operating_days") ? opDays : (stopsToggle?.cap_operating_days ?? opDays);
  const defOff = Math.max(0, 365 - capOps);
  const nDoublets = doubletCount(draft, true, stopsToggle?.doublets ?? 3);
  const stops = stopsAll && stopsToggle ? stopsFor(stopsAll, nDoublets, stopsToggle) : stopsAll;
  const maint = maintAll && stopsToggle ? maintenanceFor(maintAll, nDoublets, stopsToggle) : maintAll;
  const blocks = maint ? maint.daysOff.map((d) => daysOffOf(d) ?? defOff) : undefined;
  const stopIssues = stops ? stopsProblems(stops, maint ? capOps : opDays, blocks, !!maint) : [];
  const maintIssues = maint ? [...(stops?.mode === "quiet" ? maint.daysOff.map(daysOffProblem) : []), ...maint.units.map(serviceProblem)] : [];
  const maintBad = [...stopIssues, ...maintIssues].filter(Boolean).length;
  const maintAnswers = maint && maintStart ? maintenanceAnswers(maint, maintStart, defOff, stops?.mode !== "mine") : {};
  const stopsSent = stops ? stopsAnswer(stops, opDays, blocks) : "[]";
  const maintChanged = Object.keys(maintAnswers).length > 0 || (stops ? stopsSent !== stopsAnswer(stopsAll ?? stops, opDays, blocks) || (stops.mode === "mine") !== (stopsToggle?.stops?.length ? true : false) : false);
  const lines = changeLines(rows, draft, toggles, set, start);

  // Each page: what blocks, what warns, what changed (the step bar's dots, the review's lists).
  const states: Record<string, PageState> = {};
  const add = (p: string, k: keyof PageState, n = 1) => {
    states[p] = states[p] ?? { blocks: 0, warns: 0, changed: 0 };
    states[p][k] += n;
  };
  const blocking: { key: string; page: string; label: string; text: string }[] = [];
  const warned: { key: string; page: string; label: string; text: string }[] = [];
  for (const row of rows)
    for (const f of row.fields ?? []) {
      const p = pageOfRow(row);
      const top = (issues[f.key] ?? []).find((i) => i.level !== "note");
      const label = f.label === row.label ? f.label : `${row.label} · ${f.label}`;
      if (top?.level === "block") (add(p, "blocks"), blocking.push({ key: f.key, page: p, label, text: top.text }));
      if (top?.level === "warn") (add(p, "warns"), warned.push({ key: f.key, page: p, label, text: top.text }));
      if (changed.has(f.key)) add(p, "changed");
    }
  for (const t of toggles) {
    const p = pageOfToggle(t);
    const bad = toggleBad(t);
    if (bad) (add(p, "blocks"), blocking.push({ key: t.id, page: p, label: t.label, text: bad }));
    if (tWarn[t.id]) (add(p, "warns"), warned.push({ key: t.id, page: p, label: t.label, text: tWarn[t.id] }));
  }
  for (const l of lines) if (!changed.has(l.key)) add(l.page, "changed");
  if (stopsToggle) {
    const p = pageOfToggle(stopsToggle);
    if (maintBad) (add(p, "blocks", maintBad), blocking.push({ key: "maintenance", page: p, label: "Maintenance", text: [...stopIssues, ...maintIssues].find(Boolean)! }));
    if (maintChanged) add(p, "changed");
  }
  for (const [k, why] of loose) blocking.push({ key: k, page: REVIEW, label: "Your changes", text: why });
  const nBlocks = blocking.length;
  const nChanged = lines.length + (maintChanged ? 1 : 0); // a line per change (a records field: per record)
  const ready = nBlocks === 0;

  const go = (p: string, f: string | null = null) => {
    setPage(p);
    setFocus(f);
  };
  const answers = (extra: Record<string, string> = {}) => ({
    [qid]: options[0],
    ...toggleAnswers(toggles, set),
    ...(stops ? { doublet_stops: stopsSent } : {}),
    ...maintAnswers,
    ...extra,
  });
  const run = () => {
    if (off) return;
    if (!ready) {
      // Take the user to the first thing to fix, the cursor in its box.
      const first = blocking[0];
      return go(first.page, first.page === REVIEW ? null : first.key === "maintenance" ? "bad" : first.key);
    }
    setSent(true);
    const changes = changesOf(rows, draft);
    onAnswer(answers(Object.keys(changes).length ? { changes: JSON.stringify(changes) } : {}));
  };
  // "Reset to defaults": the server puts every input back to the project's own and shows the
  // card again, so no change the user did not confirm can run (5 Nov). Only when the server
  // knows it (`at_defaults` sent) and something differs.
  const resettable = inputs?.at_defaults !== undefined && rows.length > 0;
  const toReset = resettable && canReset(rows, draft, inputs?.at_defaults, lines.some((l) => !changed.has(l.key)) || maintChanged);
  const reset = () => {
    if (off || !toReset) return;
    setSent(true);
    onAnswer({ [qid]: RESET_OPTION });
  };
  const say = (e: FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || running || sent) return;
    setSent(true);
    onSend(t);
  };
  // Each box's name and page; what the user set (in the message: the server's `yours`, and on
  // this card) and the boxes linked to each, both ways.
  const names: Record<string, string> = {};
  const pageOfKey: Record<string, string> = {};
  const fieldMap = new Map<string, NonNullable<InputRow["fields"]>[number]>();
  for (const r of rows)
    for (const f of r.fields ?? []) {
      names[f.key] = f.label === r.label ? f.label : `${r.label} · ${f.label}`;
      pageOfKey[f.key] = pageOfRow(r);
      fieldMap.set(f.key, f);
    }
  const yours = (inputs?.yours ?? []).filter((k) => fieldMap.has(k));
  const linkedTo: Record<string, string[]> = {};
  for (const k of new Set([...yours, ...keys])) for (const j of fieldMap.get(k)?.linked ?? []) (linkedTo[j] = linkedTo[j] ?? []).push(k);
  const edit: FieldEdit = {
    draft,
    issues,
    changed,
    disabled: off,
    put: (key: string, value: Draft) => {
      setDraft((d) => ({ ...d, [key]: value }));
      setStale((s) => ({ ...s, [key]: true }));
    },
    names,
    yours: new Set(yours),
    linkedTo,
    go: (key: string) => pageOfKey[key] && go(pageOfKey[key], key),
    tempAt: (depthM: number) => productionC(valuesFor(rows, draft), { ...ctx, depth_m: depthM }),
  };
  const origin = (k: string) => (Object.keys(serverErrors).length && inputs?.changed?.includes(k) ? "Set on the card" : "From your message");
  const at = Math.max(0, pages.findIndex((p) => p.id === page));
  const prev = page === REVIEW ? pages[pages.length - 1] : at > 0 ? pages[at - 1] : null;
  const next = page === REVIEW ? null : (pages[at + 1] ?? { id: REVIEW, title: PAGE_WORDS[REVIEW].title });
  const words = PAGE_WORDS[page] ?? { title: pages.find((p) => p.id === page)?.title ?? page, intro: "" };
  const stopsError = serverErrors.doublet_stops && !stale.doublet_stops ? serverErrors.doublet_stops : null;
  const maintError = (["doublet_days_off", "service_plan"] as const).map((k) => (serverErrors[k] && !stale[k] ? serverErrors[k] : null)).find(Boolean) ?? null;
  const maintenance = stops && stopsToggle && (maint ? (
    <MaintenanceEditor
      toggle={stopsToggle}
      stops={stops}
      maint={maint}
      operatingDays={capOps}
      problems={stopIssues}
      serverError={stopsError ?? maintError}
      onStops={(s) => (setStops(s), setStale((x) => ({ ...x, doublet_stops: true })))}
      onMaint={(m) => (setMaint(m), setStale((x) => ({ ...x, doublet_days_off: true, service_plan: true })))}
      id={id}
    />
  ) : (
    <StopsEditor toggle={stopsToggle} state={stops} operatingDays={opDays} problems={stopIssues} serverError={stopsError} onChange={(s) => (setStops(s), setStale((x) => ({ ...x, doublet_stops: true })))} id={id} />
  ));
  const putToggle = (key: string, nextState: Partial<ToggleState>) => {
    setSet((s) => ({ ...s, [key]: { ...(s[key] ?? { on: false, text: "" }), ...nextState } }));
    setStale((x) => ({ ...x, [key]: true }));
  };
  const toggleRow = (t: InputToggle) => <ToggleRow key={t.id} t={t} s={set[t.id] ?? { on: false, text: "" }} onChange={(n) => putToggle(t.id, n)} warning={tWarn[t.id]} refused={live[t.id]} disabled={off} id={id} />;
  const follows = followTiles(valuesFor(rows, draft), ctx);

  return (
    <section ref={cardRef} className="ask inputs-card ic ta-rise" aria-labelledby={`${id}-title`}>
      <div className="ask-head">
        <span className="icon-box" style={{ background: "#FBEACB" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M6.6 4.4h6.4M6.6 8h6.4M6.6 11.6h6.4" fill="none" stroke="#8A5A00" strokeWidth="1.6" strokeLinecap="round" />
            <path d="m2.6 4.3.9.9 1.6-1.8M2.6 7.9l.9.9 1.6-1.8M2.6 11.5l.9.9 1.6-1.8" fill="none" stroke="#8A5A00" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <h2 id={`${id}-title`}>{title}</h2>
        {nChanged > 0 && <span className="tag tag-teal">{nChanged === 1 ? "1 change" : `${nChanged} changes`}</span>}
        <span className="ask-aside">Your go-ahead</span>
      </div>
      <div className="ask-body inputs-body">
        {inputs?.again && (
          <p className="inputs-again" role="note">
            <strong>Same inputs as {inputs.again.search}</strong>
            {inputs.again.label ? <span className="inputs-again-label"> · {inputs.again.label}</span> : null}
            <br />
            The search is deterministic, so these inputs give the same designs. Change any input to get another design, then run it.
          </p>
        )}
        {inputs?.notice && <NoticeBanner notice={inputs.notice} id={id} />}
        {inputs && rows.length > 0 ? (
          <>
            <YoursBanner keys={yours} fields={fieldMap} edit={edit} origin={origin} />
            <StepBar pages={pages} current={page} states={states} onPick={(p) => go(p)} uid={id} />
            <div className="ic-page ta-rise" key={page} role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-tab-${page}`} ref={panelRef}>
              <div className="ic-page-head">
                <h3>{words.title}</h3>
                {words.intro && <p>{words.intro}</p>}
              </div>
              {page === REVIEW ? (
                <Review lines={lines} maintChanged={maintChanged} blocking={blocking} warned={warned} follows={follows} pages={pages} go={go} />
              ) : (
                <PageRows rows={orderRows(rows.filter((r) => pageOfRow(r) === page))} toggles={allToggles.filter((t) => pageOfToggle(t) === page)} all={rows} edit={edit} toggleRow={toggleRow} maintenance={maintenance} uid={`${uid}-${page}`} />
              )}
            </div>
          </>
        ) : (
          rest && <Markdown className="inputs-md" text={rest} cites={0} onCite={noop} hasSource={none} onSource={noop} />
        )}
        <div className="ic-foot">
          <div className="ic-nav">
            {prev && (
              <button type="button" className="btn btn-soft ta-btn ta-soft ic-back" onClick={() => go(prev.id)}>
                <span aria-hidden="true">←</span> {PAGE_WORDS[prev.id]?.short ?? prev.title}
              </button>
            )}
            {resettable && (
              <button type="button" className="ic-reset-all" disabled={off || !toReset} onClick={reset} title={toReset ? "Put every input back to the project's own value; the card shows again before anything runs" : "Every input is the project's own"}>
                <Ico name="undo" size={13} boxed={false} />
                {toReset ? "Reset to defaults" : "At the defaults"}
              </button>
            )}
          </div>
          <div className="inputs-actions ic-go" role="group" aria-label={ask.value.questions?.[0]?.label ?? "Run the design with these inputs?"}>
            <span className={`ic-status${ready ? "" : " bad"}`} role="status">
              {!ready ? (
                <>
                  <span className="ic-dot-inline block" aria-hidden="true" />
                  {nBlocks === 1 ? "1 input to fix" : `${nBlocks} inputs to fix`}
                </>
              ) : (
                <>
                  {nChanged > 0 && <span className="ic-dot-inline changed" aria-hidden="true" />}
                  {nChanged ? (nChanged === 1 ? "1 change" : `${nChanged} changes`) : "Nothing changed"}
                  {warned.length > 0 && (
                    <>
                      <span className="ic-dot-inline warn" aria-hidden="true" />
                      {warned.length === 1 ? "1 warning" : `${warned.length} warnings`}
                    </>
                  )}
                </>
              )}
            </span>
            {next && inputs && rows.length > 0 ? (
              <button
                type="button"
                className="btn btn-ink ta-btn ta-ink ic-next"
                onClick={() => {
                  toTop.current = true;
                  go(next.id);
                }}
              >
                {next.id === REVIEW ? "Review and run" : `Next: ${PAGE_WORDS[next.id]?.short ?? next.title}`} <span aria-hidden="true">→</span>
              </button>
            ) : (
              <button type="button" className={`btn btn-ink ta-btn ta-ink ic-run${ready ? "" : " is-blocked"}`} disabled={off} onClick={run}>
                {ready ? <Ico name="check" size={15} boxed={false} /> : null}
                {!ready ? "Show what to fix" : nChanged ? CONFIRM_EDITS : options[0]}
              </button>
            )}
          </div>
        </div>
        <form className="inputs-say" onSubmit={say}>
          <label className="sr-only" htmlFor={`${id}-say`}>
            Or type what to change; it is sent as a message
          </label>
          <span className="input-box">
            <input id={`${id}-say`} type="text" value={text} placeholder={PLACEHOLDER} disabled={off} onChange={(e) => setText(e.target.value)} />
            <button type="submit" className="inputs-send" aria-label="Send what to change" disabled={off || !text.trim()}>
              <Arrow size={14} />
            </button>
          </span>
        </form>
      </div>
    </section>
  );
}

/** What a typed reply did, at the card's top: refused (nothing changed) or back to the defaults. */
export function NoticeBanner({ notice, id }: { notice: CardNotice; id: string }) {
  const refused = notice.kind === "refused";
  return (
    <section className={`ic-notice ${refused ? "refused" : "reset"}`} role={refused ? "alert" : "status"} aria-labelledby={`${id}-notice`}>
      <Ico name={refused ? "info" : "undo"} tint={refused ? "amber" : "teal"} size={14} />
      <div className="ic-notice-text">
        <b id={`${id}-notice`}>{notice.title}</b>
        {notice.lines.length > 0 && (
          <ul>
            {notice.lines.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        )}
        {notice.offer && <p>{notice.offer}</p>}
      </div>
    </section>
  );
}

/** A page's rows in the server's order, the rows with only switches after the others. */
function orderRows(rows: InputRow[]): InputRow[] {
  const rank = (r: InputRow) => (!r.fields?.length && r.toggles?.length ? 1 : 0);
  return rows.map((r, i) => [r, i] as const).sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(([r]) => r);
}

/** Each number as typed, in the server's units (the value now where a box is not valid). */
function valuesFor(rows: InputRow[], draft: Record<string, Draft>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const f of fieldsOf(rows)) {
    if (f.kind !== "number") continue;
    const v = f.key in draft ? fieldValue(f, draft[f.key]) : undefined;
    const x = typeof v === "number" ? v : typeof f.value === "number" ? f.value / (f.scale ?? 1) : undefined;
    if (x != null) out[f.key] = x;
  }
  return out;
}

/** A page's rows, each with its boxes and switches; switches no row holds come after them. */
function PageRows({ rows, toggles, all, edit, toggleRow, maintenance, uid }: { rows: InputRow[]; toggles: InputToggle[]; all: InputRow[]; edit: FieldEdit; toggleRow: (t: InputToggle) => ReactNode; maintenance: ReactNode; uid: string }) {
  const shown = new Set<string>();
  const byId = new Map(toggles.map((t) => [t.id, t]));
  const claimed = new Set(all.flatMap((r) => r.toggles ?? []));
  const isMaint = (t?: InputToggle) => !!t && (t.kind === "maintenance" || t.kind === "stops");
  const blocks = rows.map((row, i) => {
    const ids = (row.toggles ?? []).filter((t) => byId.has(t));
    // A second row of the Maintenance section (the units' service): the section shows it.
    if (ids.length && !row.fields?.length && ids.every((t) => shown.has(t))) return null;
    const mine = (row.fields ?? []).some((f) => edit.changed.has(f.key));
    return (
      <RowBlock key={`${row.label}-${i}`} row={row} mine={mine} uid={`${uid}-r${i}`}>
        {(row.fields ?? []).map((f) => (
          <ParamField key={f.key} f={f} edit={edit} uid={`${uid}-${f.key}`} />
        ))}
        {ids.map((tid) => {
          if (shown.has(tid)) return null;
          shown.add(tid);
          const t = byId.get(tid)!;
          return isMaint(t) ? <div key={tid} className="ic-maint">{maintenance}</div> : toggleRow(t);
        })}
      </RowBlock>
    );
  });
  const rest = toggles.filter((t) => !shown.has(t.id) && !claimed.has(t.id));
  return (
    <div className="ic-rows">
      {blocks}
      {rest.length > 0 && (
        <section className="ic-row ic-row-opts" aria-label="Options">
          {rest.map((t) => (isMaint(t) ? <div key={t.id} className="ic-maint">{maintenance}</div> : toggleRow(t)))}
        </section>
      )}
    </div>
  );
}

/** The review: what changed (was → now), what blocks the run, the warnings, and what follows. */
function Review({ lines, maintChanged, blocking, warned, follows, pages, go }: { lines: ChangeLine[]; maintChanged: boolean; blocking: { key: string; page: string; label: string; text: string }[]; warned: { key: string; page: string; label: string; text: string }[]; follows: { icon: string; tint: string; value: string; label: string }[]; pages: { id: string; title: string }[]; go: (p: string, f?: string | null) => void }) {
  const pageName = (p: string) => PAGE_WORDS[p]?.short ?? pages.find((x) => x.id === p)?.title ?? p;
  const goto = (p: string, key: string) => (p === REVIEW ? null : (
    <button type="button" className="link-btn ic-goto" onClick={() => go(p, key === "maintenance" ? "bad" : key)}>
      {pageName(p)} <span aria-hidden="true">→</span>
    </button>
  ));

  const nChanged = lines.length + (maintChanged ? 1 : 0);
  return (
    <div className="ic-review">
      <div className="ic-tiles">
        <div className={`ic-tile${nChanged ? " teal" : ""}`}>
          <b>{nChanged}</b>
          <span>{nChanged === 1 ? "change" : "changes"}</span>
        </div>
        <div className={`ic-tile${blocking.length ? " red" : " ok"}`}>
          <b>{blocking.length}</b>
          <span>to fix</span>
        </div>
        <div className={`ic-tile${warned.length ? " amber" : ""}`}>
          <b>{warned.length}</b>
          <span>{warned.length === 1 ? "warning" : "warnings"}</span>
        </div>
      </div>
      {blocking.length > 0 && (
        <section className="ic-review-block red">
          <h4>To fix before it can run</h4>
          <ul>
            {blocking.map((b) => (
              <li key={b.key}>
                <span className="ic-review-what">
                  <b>{b.label}</b> {b.text}
                </span>
                {goto(b.page, b.key)}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="ic-review-block">
        <h4>What you changed</h4>
        {nChanged ? (
          <ul>
            {lines.map((l, i) => (
              <li key={`${l.key}-${i}`}>
                <span className="ic-review-what">
                  <b>{l.label}</b> <span className="ic-was-now">{l.was}</span> <span aria-hidden="true">→</span>
                  <span className="sr-only"> to </span> <span className="ic-now">{l.now}</span>
                </span>
                {goto(l.page, l.key)}
              </li>
            ))}
            {maintChanged && (
              <li>
                <span className="ic-review-what">
                  <b>Maintenance</b> the doublets' stops or the units' service, as you set them
                </span>
                {goto("limits", "maintenance")}
              </li>
            )}
          </ul>
        ) : (
          <p className="ic-review-none">Nothing: the design runs on the inputs as read.</p>
        )}
      </section>
      {warned.length > 0 && (
        <section className="ic-review-block amber">
          <h4>Warnings (it still runs)</h4>
          <ul>
            {warned.map((w) => (
              <li key={w.key}>
                <span className="ic-review-what">
                  <b>{w.label}</b> {w.text}
                </span>
                {goto(w.page, w.key)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {follows.length > 0 && (
        <section className="ic-review-block">
          <h4>What follows</h4>
          <div className="ic-follow-tiles">
            {follows.map((t) => (
              <div key={t.label} className="ic-follow">
                <Ico name={t.icon} tint={t.tint} size={15} />
                <span className="ic-follow-text">
                  <b>{t.value}</b>
                  <small>{t.label}</small>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

/** The inputs by group, read-only (the folded card): an overview bar of where they come from, then each row. */
export function InputsTable({ inputs }: { inputs: ConfirmInputs }) {
  const groups = groupRows(inputs.rows);
  const counts = kindCounts(inputs.rows, inputs.kinds);
  const total = inputs.rows.length;
  const uid = useId();
  return (
    <div className="inputs-table">
      <div className="inputs-overview">
        <span className="inputs-bar" role="img" aria-label={`${total} inputs: ${counts.map((k) => `${k.n} ${k.words}`).join(", ")}`}>
          {counts.map((k) => (
            <span key={k.id} className={`kind-${KINDS.some((x) => x.id === k.id) ? k.id : "other"}`} style={{ flexGrow: k.n }} />
          ))}
        </span>
        <span className="inputs-legend" aria-hidden="true">
          {counts.map((k) => (
            <span key={k.id}>
              <i className={`kind-${KINDS.some((x) => x.id === k.id) ? k.id : "other"}`} />
              <b>{k.n}</b> {k.words}
            </span>
          ))}
        </span>
      </div>
      {groups.map((g, gi) => (
        <section key={g.name} className="inputs-group" aria-labelledby={`${uid}-g${gi}`}>
          <h3 id={`${uid}-g${gi}`} className="inputs-group-name">
            {g.name}
          </h3>
          <ul className="inputs-rows">
            {g.rows.map((r, i) => (
              <InputLine key={`${r.label}-${i}`} row={r} words={inputs.kinds?.[r.kind] ?? KINDS.find((k) => k.id === r.kind)?.words ?? r.kind} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function InputLine({ row, words }: { row: InputRow; words: string }) {
  const known = KINDS.some((k) => k.id === row.kind);
  const source = row.source && (
    <span className="inputs-source" title={row.source}>
      <span className="sr-only">From </span>
      {textWithFiles(row.source).map((n, i) => (n.type === "file" ? <FileRef key={i} name={n.name} /> : <span key={i}>{n.type === "text" ? n.text : ""}</span>))}
    </span>
  );
  return (
    <li className={`inputs-row${row.changed ? " changed" : ""}`}>
      <span className="inputs-label">
        {row.label}
        {row.changed && <span className="tag tag-amber inputs-changed">changed</span>}
      </span>
      <span className="inputs-value">
        <span>{row.value}</span>
        {source}
      </span>
      <span className={`inputs-kind kind-${known ? row.kind : "other"}`} title={words}>
        {SOURCE_WORDS[row.kind] ?? row.kind}
        <span className="sr-only">: {words}</span>
      </span>
    </li>
  );
}

export type { Issue };

/** When the doublets stop: Dioscuri's quietest weeks, or the user's dates, per doublet one block or several ranges. */
function StopsEditor({
  toggle,
  state,
  operatingDays,
  problems,
  serverError,
  onChange,
  id,
}: {
  toggle: InputToggle;
  state: StopsState;
  operatingDays: number;
  problems: (string | null)[];
  serverError: string | null;
  onChange: (s: StopsState) => void;
  id: string;
}) {
  const off = daysOff(operatingDays);
  const together = stopsTogether(state, operatingDays);
  const put = (k: number, next: Partial<StopsState["doublets"][number]>) => onChange({ ...state, doublets: state.doublets.map((d, i) => (i === k ? { ...d, ...next } : d)) });
  const min = dateOf(0);
  const max = dateOf(364);
  return (
    <div className={`inputs-opt inputs-stops${state.mode === "mine" ? " on" : ""}`} role="group" aria-labelledby={`${id}-stops`}>
      <span className="inputs-opt-icon" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 16 16">
          <rect x="2" y="3" width="12" height="11" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
          <path d="M2 6.5h12M5.5 1.8v2.6M10.5 1.8v2.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          <path d="M5 9.5h6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </span>
      <div className="inputs-opt-text">
        <span className="inputs-opt-label" id={`${id}-stops`}>
          {toggle.label}
        </span>
        <span className="inputs-opt-hint">
          365 − {operatingDays} operating days = <b>{off} days off</b> for each doublet
        </span>
        <span className="inputs-stops-mode" role="radiogroup" aria-label="Who places the stops">
          {(
            [
              ["quiet", "Quietest weeks (Dioscuri chooses)"],
              ["mine", "My dates"],
            ] as const
          ).map(([mode, words]) => (
            <label key={mode} className={state.mode === mode ? "on" : ""}>
              <input type="radio" name={`${id}-stops-mode`} value={mode} checked={state.mode === mode} onChange={() => onChange({ ...state, mode })} />
              {words}
            </label>
          ))}
        </span>
        {state.mode === "mine" && (
          <div className="inputs-stops-list">
            {state.doublets.map((d, k) => {
              const ranges = rangesOf(d, off);
              const total = daysOf(ranges);
              const bad = problems[k];
              const errId = `${id}-stop-${k}-err`;
              return (
                <div key={k} className={`inputs-stop${bad ? " bad" : ""}`}>
                  <div className="inputs-stop-head">
                    <strong>Doublet {k + 1}</strong>
                    <span className="inputs-stop-kind" role="radiogroup" aria-label={`Doublet ${k + 1}: one block or several ranges`}>
                      {(
                        [
                          ["block", "One block"],
                          ["ranges", "Several ranges"],
                        ] as const
                      ).map(([kind, words]) => (
                        <label key={kind} className={d.kind === kind ? "on" : ""}>
                          <input
                            type="radio"
                            name={`${id}-stop-${k}-kind`}
                            value={kind}
                            checked={d.kind === kind}
                            onChange={() =>
                              put(k, kind === "ranges" && d.kind === "block" ? { kind, ranges: blockAsRanges(d.start, off) } : kind === "block" && d.ranges[0] ? { kind, start: d.ranges[0].from } : { kind })
                            }
                          />
                          {words}
                        </label>
                      ))}
                    </span>
                    <span className={`inputs-stop-total${total < off ? " short" : ""}`}>
                      {total} of {off} days
                    </span>
                  </div>
                  {d.kind === "block" ? (
                    <div className="inputs-stop-range">
                      <label htmlFor={`${id}-stop-${k}-start`}>From</label>
                      <input id={`${id}-stop-${k}-start`} type="date" min={min} max={max} value={d.start} aria-invalid={!!bad} aria-describedby={bad ? errId : undefined} onChange={(e) => put(k, { start: e.target.value })} />
                      <span className="inputs-stop-to">{ranges[0] ? `to ${dayName(ranges[0][1])}${ranges[0][1] > 364 ? ` ${YEAR + 1}` : ""}` : ""}</span>
                    </div>
                  ) : (
                    <>
                      {d.ranges.map((r, j) => (
                        <div key={j} className="inputs-stop-range">
                          <label htmlFor={`${id}-stop-${k}-${j}-from`}>From</label>
                          <input id={`${id}-stop-${k}-${j}-from`} type="date" min={min} max={max} value={r.from} aria-invalid={!!bad} onChange={(e) => put(k, { ranges: d.ranges.map((x, i) => (i === j ? { ...x, from: e.target.value } : x)) })} />
                          <label htmlFor={`${id}-stop-${k}-${j}-to`}>to</label>
                          <input id={`${id}-stop-${k}-${j}-to`} type="date" min={min} max={max} value={r.to} aria-invalid={!!bad} onChange={(e) => put(k, { ranges: d.ranges.map((x, i) => (i === j ? { ...x, to: e.target.value } : x)) })} />
                          <span className="inputs-stop-days">{rangeDays(r)}</span>
                          {d.ranges.length > 1 && (
                            <button type="button" className="inputs-stop-remove" aria-label={`Remove range ${j + 1} of doublet ${k + 1}`} onClick={() => put(k, { ranges: d.ranges.filter((_, i) => i !== j) })}>
                              ×
                            </button>
                          )}
                        </div>
                      ))}
                      <button type="button" className="link-btn inputs-stop-add" onClick={() => put(k, { ranges: [...d.ranges, nextRange(d, off)] })}>
                        + Add a range
                      </button>
                    </>
                  )}
                  {bad && (
                    <span id={errId} className="inputs-field-error" role="alert">
                      {bad}
                    </span>
                  )}
                </div>
              );
            })}
            {together && <span className="inputs-opt-hint">{together[0].toUpperCase() + together.slice(1)}</span>}
            <span className="inputs-opt-hint">Doublets the design does not build are left out.</span>
          </div>
        )}
        {serverError && (
          <span className="inputs-field-error" role="alert">
            {serverError}
          </span>
        )}
      </div>
    </div>
  );
}

/** A block as one range the user can then split. */
function blockAsRanges(start: string, off: number) {
  const s = dayOf(start) ?? 180;
  return [{ from: dateOf(s), to: dateOf(Math.min(364, s + Math.max(off, 1) - 1)) }];
}

/** A new range a week after the doublet's last one. */
function nextRange(d: StopsState["doublets"][number], off: number) {
  const last = Math.max(...d.ranges.map((r) => dayOf(r.to) ?? 0), 0);
  const a = Math.min(364, last + 8);
  return { from: dateOf(a), to: dateOf(Math.min(364, a + Math.max(0, Math.min(6, off - 1)))) };
}

function rangeDays(r: { from: string; to: string }): string {
  const a = dayOf(r.from);
  const b = dayOf(r.to);
  return a == null || b == null || b < a ? "" : `${b - a + 1} day${b === a ? "" : "s"}`;
}

function SummaryIcon({ tone }: { tone: SummaryTone }) {
  if (tone === "busy") return <Spinner size={16} />;
  const color = tone === "ok" ? "#0F7A3D" : tone === "amber" ? "#8A5A00" : "#66727C";
  const bg = tone === "ok" ? "#E3F5EA" : tone === "amber" ? "#FBEACB" : "#EEF2F2";
  return (
    <span className="icon-box inputs-done-icon" style={{ background: bg }} aria-hidden="true">
      <svg width="14" height="14" viewBox="0 0 16 16">
        {tone === "ok" ? (
          <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        ) : tone === "amber" ? (
          <path d="M10.6 2.6l2.8 2.8-7.6 7.6-3.4.6.6-3.4z" fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
        ) : (
          <path d="M4 8h8" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
        )}
      </svg>
    </span>
  );
}
