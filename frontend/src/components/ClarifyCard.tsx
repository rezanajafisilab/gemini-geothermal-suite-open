// The one clarifying question (CUSTOM `clarification`): every missing input at once, each with
// its proposed default. Options become segmented pickers, the rest text fields. Continue sends
// the answers on the same thread and the run carries on without another model call.

import { useMemo, useState, type FormEvent } from "react";

import { parseOption } from "../agent/numbers";
import type { Ask, DecisionDetail, Question, Turn } from "../agent/types";
import { Arrow } from "./Icons";
import { fmtNum } from "./ResultCard";

interface Props {
  turn: Turn;
  onSubmit: (answers: Record<string, string>) => void;
}

/** The colour square a question carries: heat, cold, or neutral. */
export function questionColor(id: string, onDark = false): string {
  if (/^dh_|heat/.test(id)) return onDark ? "#F0743E" : "#C24E1C";
  if (/^dc_|cool/.test(id)) return onDark ? "#5B9BF0" : "#2363A6";
  return onDark ? "#9AA8AF" : "#7856C4";
}

function numbersIn(text: string): number[] {
  return (text.match(/-?\d+(?:[.,]\d+)?/g) ?? []).map((n) => Number(n.replace(",", ".")));
}

export function validate(q: Question, raw: string): string | null {
  const v = raw.trim();
  const required = q.required !== false;
  if (!v) return required ? "Needed to continue." : null;
  if (q.options?.includes(v) || v === q.default) return null;
  const nums = numbersIn(v);
  if (/_supply_return_c$/.test(q.id)) {
    if (nums.length < 2) return "Give supply and return, for example 75/45 °C.";
    const [supply, ret] = nums;
    if (q.id.startsWith("dh") && supply <= ret) return "The supply must be hotter than the return.";
    if (q.id.startsWith("dc") && supply >= ret) return "The supply must be colder than the return.";
    return null;
  }
  if (!nums.length) return "Enter a number.";
  return null;
}

function split(intro: string): [string, string] {
  const m = intro.match(/^(.+?[.!?])\s+(.*)$/s);
  return m ? [m[1], m[2]] : [intro, ""];
}

export function ClarifyCard({ turn, onSubmit }: Props) {
  const questions = useMemo(() => turn.clarification?.questions ?? [], [turn.clarification]);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(questions.map((q) => [q.id, q.default ?? ""])),
  );
  const [custom, setCustom] = useState<Record<string, boolean>>({});
  const [tried, setTried] = useState(false);
  const errors = Object.fromEntries(questions.map((q) => [q.id, validate(q, values[q.id] ?? "")]));
  const answered = questions.filter((q) => (values[q.id] ?? "").trim() && !errors[q.id]).length;
  const [title, hint] = split(turn.clarification?.intro ?? "A few inputs are missing.");
  const askAt = turn.steps.findIndex((s) => s.kind === "ask") + 1;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (questions.some((q) => errors[q.id])) {
      const first = questions.find((q) => errors[q.id]);
      document.getElementById(`q-${turn.id}-${first?.id}`)?.focus();
      return;
    }
    const answers: Record<string, string> = {};
    for (const q of questions) {
      const v = (values[q.id] ?? "").trim();
      if (v) answers[q.id] = v;
    }
    onSubmit(answers);
  };

  const set = (id: string, v: string) => setValues((s) => ({ ...s, [id]: v }));

  return (
    <form className="ask ta-rise" aria-labelledby={`ask-${turn.id}`} onSubmit={submit} noValidate>
      <div className="ask-head">
        <span className="icon-box" style={{ background: "#FBEACB" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <rect x="4.4" y="3.5" width="2.4" height="9" rx="1" fill="#8A5A00" />
            <rect x="9.2" y="3.5" width="2.4" height="9" rx="1" fill="#8A5A00" />
          </svg>
        </span>
        <h2 id={`ask-${turn.id}`}>{title}</h2>
        {askAt > 0 && (
          <span style={{ marginLeft: "auto", fontSize: 12.5, color: "#7A5000", fontWeight: 550 }}>Paused at step {askAt}</span>
        )}
      </div>
      <div className="ask-body">
        <div className="ask-grid">
          {questions.map((q) => {
            const opts = q.options ?? [];
            const segmented = opts.length >= 2 && !custom[q.id];
            const err = tried ? errors[q.id] : null;
            const fid = `q-${turn.id}-${q.id}`;
            return (
              <fieldset key={q.id} className="field">
                <legend>
                  <span className="sq" style={{ background: questionColor(q.id) }} />
                  {q.label}
                  {q.required !== false && !q.default && (
                    <span className="req" aria-hidden="true">
                      *
                    </span>
                  )}
                </legend>
                {segmented ? (
                  <Segmented id={fid} options={opts} value={values[q.id] ?? ""} onPick={(v) => set(q.id, v)} />
                ) : (
                  <div className={`input-box${err ? " invalid" : ""}`}>
                    <input
                      id={fid}
                      type="text"
                      inputMode={/_supply_return_c$/.test(q.id) ? "text" : "decimal"}
                      aria-required={q.required !== false}
                      aria-invalid={!!err}
                      aria-describedby={`${fid}-hint ${fid}-err`}
                      value={values[q.id] ?? ""}
                      placeholder={q.default ?? (/_supply_return_c$/.test(q.id) ? "e.g. 75/45 °C" : "e.g. 40")}
                      onChange={(e) => set(q.id, e.target.value)}
                    />
                  </div>
                )}
                {opts.length === 1 && !segmented && (
                  <span style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    <button type="button" className="followup ta-btn ta-chip" style={{ padding: "4px 10px", fontSize: 13 }} onClick={() => set(q.id, opts[0])}>
                      {opts[0]}
                    </button>
                  </span>
                )}
                <span className="field-foot">
                  <span id={`${fid}-hint`}>{q.hint}</span>
                  {opts.length >= 2 && (
                    <button
                      type="button"
                      className="link-btn"
                      onClick={() => {
                        const next = !custom[q.id];
                        setCustom((c) => ({ ...c, [q.id]: next }));
                        if (!next && !opts.includes(values[q.id] ?? "")) set(q.id, q.default ?? opts[0]);
                        if (next) setTimeout(() => document.getElementById(fid)?.focus(), 0);
                      }}
                    >
                      {custom[q.id] ? "Pick a typical value" : "Other value"}
                    </button>
                  )}
                </span>
                <p id={`${fid}-err`} className="err" role="alert">
                  {err}
                </p>
              </fieldset>
            );
          })}
        </div>
        <div className="ask-foot">
          <span className="progress">
            <span style={{ display: "inline-flex", gap: 4 }} aria-hidden="true">
              {questions.map((q) => (
                <i key={q.id} style={{ background: (values[q.id] ?? "").trim() && !errors[q.id] ? "#0B8FA0" : "#DCE3E3" }} />
              ))}
            </span>
            {hint || `${answered} of ${questions.length} answered`}
          </span>
          <button type="submit" className="btn btn-ink ta-btn ta-ink">
            Continue
          </button>
        </div>
      </div>
    </form>
  );
}

function Segmented({ id, options, value, onPick }: { id: string; options: string[]; value: string; onPick: (v: string) => void }) {
  const idx = Math.max(0, options.indexOf(value));
  const n = options.length;
  return (
    <div className="seg" role="radiogroup" id={id} tabIndex={-1}>
      <span
        className="seg-thumb ta-thumb"
        style={{ left: `calc(4px + ${idx} * (100% - 8px) / ${n})`, width: `calc((100% - 8px) / ${n})`, opacity: options.includes(value) ? 1 : 0 }}
      />
      {options.map((o, i) => (
        <button
          key={o}
          type="button"
          role="radio"
          aria-checked={o === value}
          tabIndex={o === value || (!options.includes(value) && i === 0) ? 0 : -1}
          style={{ fontWeight: o === value ? 650 : 450 }}
          onClick={() => onPick(o)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
              e.preventDefault();
              const next = options[(i + (e.key === "ArrowRight" ? 1 : n - 1)) % n];
              onPick(next);
              const btns = (e.currentTarget.parentElement?.querySelectorAll("button") ?? []) as NodeListOf<HTMLButtonElement>;
              btns[options.indexOf(next)]?.focus();
            }
          }}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

/** The sent answers, as a reply bubble with the heat and cold colours. */
export function AnswersBubble({ ask }: { ask: Ask }) {
  const answers = ask.answers ?? {};
  const qs = ask.value.questions ?? [];
  const items = Object.entries(answers).map(([id, v]) => ({ id, v, label: qs.find((q) => q.id === id)?.label ?? id }));
  return (
    <div className="user-row ta-rise">
      <span className="answers-bubble" aria-label="Your answers">
        {items.map((a) => (
          <span key={a.id} title={a.label}>
            <span className="sq" style={{ background: questionColor(a.id, true) }} />
            {a.v}
          </span>
        ))}
      </span>
    </div>
  );
}

/**
 * A mid-run decision (clarification kind "decision"): nothing met the brief, the fixes were
 * simulated, and the user picks how to go on. One card per option, the recommended one marked;
 * Continue sends {"decision": "<option text>"} on the same thread.
 */
export function DecisionCard({ turn, onSubmit }: Props) {
  const q = turn.clarification?.questions[0];
  const details = Array.isArray(turn.clarification?.details) ? (turn.clarification!.details as DecisionDetail[]) : null;
  // The agent describes each option (details); older servers only send the option strings.
  const options = useMemo(
    () =>
      details
        ? details.map((d) => ({
            text: d.option,
            label: d.name ?? d.option,
            code: d.code,
            summary:
              d.fix === "keep"
                ? ""
                : `${fmtNum(pct(d))}% of the heat` + (d.lcoh != null ? ` at ${fmtNum(d.lcoh)} €/MWh` : ", no heat delivered"),
            coverage: d.fix === "keep" ? undefined : pct(d),
            recommended: !!d.recommended,
          }))
        : (q?.options ?? []).map((o) => ({ ...parseOption(o), code: undefined as string | undefined, recommended: o === q?.default })),
    [q, details],
  );
  const [picked, setPicked] = useState<string>(q?.default ?? q?.options?.[0] ?? "");
  if (!q) return null;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (picked) onSubmit({ [q.id]: picked });
  };
  const best = Math.max(...options.map((o) => o.coverage ?? 0), 1);
  return (
    <form className="ask ta-rise" aria-labelledby={`ask-${turn.id}`} onSubmit={submit}>
      <div className="ask-head">
        <span className="icon-box" style={{ background: "#FBEACB" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M8 2.2v4.6M8 6.8 4 11M8 6.8l4 4.2M4 11v2.8M12 11v2.8" fill="none" stroke="#8A5A00" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <h2 id={`ask-${turn.id}`}>{q.label}</h2>
        <span style={{ marginLeft: "auto", fontSize: 12.5, color: "#7A5000", fontWeight: 550 }}>Your decision</span>
      </div>
      <div className="ask-body" style={{ gap: 14 }}>
        <fieldset className="field" style={{ gap: 6 }}>
          <legend className="sr-only">{q.label}</legend>
          {options.map((o, i) => {
            const on = picked === o.text;
            const rec = o.recommended;
            const keep = !o.summary;
            return (
              <label key={o.text} className={`decision ta-row${on ? " on" : ""}${keep ? " keep" : ""}`}>
                <input type="radio" name={`decision-${turn.id}`} value={o.text} checked={on} onChange={() => setPicked(o.text)} className="sr-only" />
                <span className="decision-key" aria-hidden="true">
                  {i + 1}
                </span>
                <span className="decision-main">
                  <span className="decision-label">
                    {o.code && <span className="alt-code">{o.code}</span>}
                    {o.label}
                  </span>
                  {o.summary && (
                    <span className="decision-facts">
                      <span className="decision-bar" aria-hidden="true">
                        <span style={{ width: `${Math.min(100, ((o.coverage ?? 0) / best) * 100)}%`, background: (o.coverage ?? 0) >= 99.95 ? "#C24E1C" : "#E3A33B" }} />
                      </span>
                      <span className="decision-summary">{o.summary}</span>
                    </span>
                  )}
                </span>
                {rec && <span className="tag tag-teal">Recommended</span>}
              </label>
            );
          })}
        </fieldset>
        <div className="ask-foot">
          <span className="progress">{q.hint}</span>
          <button type="submit" className="btn btn-ink ta-btn ta-ink" disabled={!picked}>
            Continue
          </button>
        </div>
      </div>
    </form>
  );
}

const pct = (d: DecisionDetail) => d.heat_coverage_pct ?? (d.heat_coverage ?? 0) * 100;

/**
 * The model didn't understand the message (clarification kind "choice") and offers readings.
 * Each option is a complete request, so one click sends it ({"choice": "<option>"}); there is no
 * Continue and no default. Typing a new message instead simply starts a new turn. Keys 1–n pick.
 */
export function ChoiceCard({ ask, id, onSubmit }: { ask: Ask; id: string; onSubmit: (answers: Record<string, string>) => void }) {
  const q = ask.value.questions[0];
  const options = q?.options ?? [];
  const [sent, setSent] = useState(false);
  const [other, setOther] = useState("");
  // An "Other" box when the agent offers one (which design: a handle or a name typed in).
  const otherHint = typeof (ask.value as { other?: unknown }).other === "string" ? ((ask.value as { other?: string }).other as string) : null;
  if (!q) return null;
  const pick = (o: string) => {
    if (sent || !o.trim()) return;
    setSent(true);
    onSubmit({ [q.id]: o.trim() });
  };
  return (
    <section
      className="ask ta-rise"
      aria-labelledby={`choice-${id}`}
      onKeyDown={(e) => {
        const n = Number(e.key);
        if (Number.isInteger(n) && n >= 1 && n <= options.length && !e.altKey && !e.ctrlKey && !e.metaKey) {
          e.preventDefault();
          pick(options[n - 1]);
        }
      }}
    >
      <div className="ask-head">
        <span className="icon-box" style={{ background: "#FBEACB" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M5.6 6a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.2.9-1.2 1.7v.4" fill="none" stroke="#8A5A00" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="8" cy="12.9" r="1" fill="#8A5A00" />
          </svg>
        </span>
        <h2 id={`choice-${id}`}>{ask.value.intro || q.label}</h2>
        <span style={{ marginLeft: "auto", fontSize: 12.5, color: "#7A5000", fontWeight: 550 }}>Your choice</span>
      </div>
      <div className="ask-body" style={{ gap: 12 }}>
        <div className="choice-list" role="group" aria-label={q.label}>
          {options.map((o, i) => (
            <button key={o} type="button" className="decision choice ta-row" disabled={sent} onClick={() => pick(o)}>
              <span className="decision-key" aria-hidden="true">
                {i + 1}
              </span>
              <span className="decision-label">{o}</span>
              <span className="choice-go" aria-hidden="true">
                <Arrow />
              </span>
            </button>
          ))}
        </div>
        {otherHint && (
          <form
            className="choice-other"
            onSubmit={(e) => {
              e.preventDefault();
              pick(other);
            }}
          >
            <label className="sr-only" htmlFor={`choice-${id}-other`}>
              {otherHint}
            </label>
            <span className="input-box">
              <input id={`choice-${id}-other`} type="text" placeholder={otherHint} value={other} disabled={sent} onChange={(e) => setOther(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
              <button type="submit" className="inputs-send" aria-label="Send" disabled={sent || !other.trim()}>
                <Arrow />
              </button>
            </span>
          </form>
        )}
        <span className="choice-hint">
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
            <path d="M2.5 4.5h11v7h-11zM5 7h.01M8 7h.01M11 7h.01M5.5 9.4h5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {q.hint || "Pick one, or type your own question."}
        </span>
      </div>
    </section>
  );
}

/** The option the user picked (a decision, an offer, an approval), as a reply bubble. */
export function ChoiceBubble({ ask }: { ask: Ask }) {
  const q = ask.value.questions[0];
  const choice = ask.answers?.[q?.id ?? ""] ?? Object.values(ask.answers ?? {})[0] ?? "";
  const details = Array.isArray(ask.value.details) ? (ask.value.details as DecisionDetail[]) : null;
  const d = details?.find((x) => x.option === choice);
  const label = d?.name ?? (ask.value.kind === "decision" ? parseOption(choice).label : choice);
  // The first option is the yes (approve, write it); the others decline. A decision or a
  // choice has no no: every option is a way to go on.
  const yes = ask.value.kind === "decision" || ask.value.kind === "choice" || !q?.options || q.options.indexOf(choice) === 0;
  return (
    <div className="user-row ta-rise">
      <span className="answers-bubble" aria-label="Your choice">
        <span>
          {yes ? (
            <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="#7FD6A2" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 10 10" aria-hidden="true">
              <path d="M2 2l6 6M8 2 2 8" stroke="#F19A92" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          )}
          {d?.code && <span className="alt-code dark">{d.code}</span>}
          {label}
        </span>
      </span>
    </div>
  );
}
