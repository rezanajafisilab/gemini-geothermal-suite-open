// The inputs card's pages (InputsCard): a step bar of icons (each page with a red dot when
// something on it blocks the run and an amber one for a warning), then the page's rows, each
// with its icon, a one-line explanation and where its value comes from as a chip. Each
// parameter is a box with its unit, one short line of explanation ("more" opens the rest: its
// typical values, what it is linked to, what it changes in the design, the model's range and the
// challenge's), a bar of its range, and its issues as it is typed (blocks the run, warning, what
// follows). A box linked to a value the user set says so. A row's switches sit in the row; a row
// with nothing to change says why. The banner lists what the user set and what each one affects.

import { Fragment, useState, type ReactNode } from "react";

import { textWithFiles } from "../agent/markdown";
import type { InputField, InputRow, InputToggle, RecordColumn } from "../agent/types";
import { type Draft, type Issue, cellOptional, cellProblem, defaultDraft, defaultWords, differsFromDefault, fieldText, fmtNum, hasDefault, isRecords, recordsWords } from "./inputsForm";
import { Ico, PAGE_ICON, ROW_ICON } from "./InputsIcons";
import { FileRef } from "./Markdown";

export const REVIEW = "review";

/** The card's pages: their short name on the step bar, title and one sentence of intro. */
export const PAGE_WORDS: Record<string, { short: string; title: string; intro: string }> = {
  demand: { short: "Demand", title: "Demand", intro: "The district's heat and cold, read from the demand files. Scale them to test a district that grows or shrinks." },
  reservoir: { short: "Reservoir", title: "Reservoir and wells", intro: "The aquifer the wells produce from: its rock, its temperature, and the depths the wells may reach." },
  brine: { short: "Brine", title: "Brine and gas", intro: "What comes up the well: the brine, the gas in it, and what is done with that gas." },
  limits: {
    short: "Limits",
    title: "Limits",
    intro: "The caps every design must keep, and when the doublets stop for maintenance. Outside the challenge's caps a design still runs, but it does not meet the challenge.",
  },
  networks: { short: "Networks", title: "Networks", intro: "The district networks' temperatures, and the heat their pipes lose on the way." },
  prices: { short: "Prices", title: "Prices", intro: "The prices every design is costed and compared with." },
  request: { short: "Request", title: "Your request", intro: "What you asked for: what “best” means, how many doublets, units left out, and the plant's options." },
  [REVIEW]: { short: "Review", title: "Review and run", intro: "What you changed, what still needs fixing, and the warnings. Run when it looks right." },
};
// Limits after the request: the doublets asked for there are the ones Maintenance lists.
const DEFAULT_PAGES = ["demand", "reservoir", "brine", "networks", "prices", "request", "limits"];
const PAGE_OF_GROUP: Record<string, string> = {
  Demand: "demand",
  Reservoir: "reservoir",
  "Reservoir and wells": "reservoir",
  "Brine and gas": "brine",
  Caps: "limits",
  Limits: "limits",
  Maintenance: "limits",
  Networks: "networks",
  Costs: "prices",
  Prices: "prices",
  "Plant options": "request",
  "Your request": "request",
};
const PAGE_OF_TOGGLE: Record<string, string> = {
  network_length_km: "networks",
  maintenance: "limits",
  stops: "limits",
  doublet_stops: "limits",
  grid_by_month: "prices",
  co2_reinjection: "brine",
  flare_brine_gas: "brine",
};

export const pageOfRow = (r: InputRow) => r.page ?? PAGE_OF_GROUP[r.group] ?? "request";
export const pageOfToggle = (t: InputToggle) => t.page ?? PAGE_OF_TOGGLE[t.id] ?? (t.kind === "maintenance" || t.kind === "stops" ? "limits" : "request");

/** The pages in order, as the server lists them (else the card's), those with nothing left out. */
export function pagesOf(rows: InputRow[], toggles: InputToggle[], listed?: { id: string; title: string }[]): { id: string; title: string }[] {
  const ids = listed?.length ? listed.map((p) => p.id) : DEFAULT_PAGES;
  const extra = [...rows.map(pageOfRow), ...toggles.map(pageOfToggle)].filter((p) => !ids.includes(p));
  const used = new Set([...rows.map(pageOfRow), ...toggles.map(pageOfToggle)]);
  return [...ids, ...new Set(extra)]
    .filter((id) => used.has(id))
    .map((id) => ({ id, title: listed?.find((p) => p.id === id)?.title ?? PAGE_WORDS[id]?.title ?? id }));
}

/** Where a row's value comes from, in words: a source line instead of a badge. */
export const SOURCE_WORDS: Record<string, string> = {
  data: "Read from the files",
  fixed: "From the challenge",
  derived: "Worked out",
  assumed: "Assumed by Dioscuri",
  asked: "Your request",
};

export function SourceLine({ row, mine }: { row: InputRow; mine: boolean }) {
  const kind = mine ? "mine" : row.kind in SOURCE_WORDS ? row.kind : "other";
  const words = mine ? "You changed it" : (SOURCE_WORDS[row.kind] ?? row.kind);
  const detail = !mine && row.source && !(row.kind === "asked" && /^(you|your message)$/.test(row.source)) ? row.source : "";
  return (
    <span className={`ic-src src-${kind}`}>
      <b>
        <i aria-hidden="true" />
        {words}
      </b>
      {detail && (
        <span className="ic-src-detail" title={detail}>
          {textWithFiles(detail).map((n, i) => (n.type === "file" ? <FileRef key={i} name={n.name} /> : <span key={i}>{n.type === "text" ? n.text.replace(/^[,;\s]+/, "") : ""}</span>))}
        </span>
      )}
    </span>
  );
}

/** Each page's state for the step bar and the review: what blocks, what warns, what changed. */
export interface PageState {
  blocks: number;
  warns: number;
  changed: number;
}

/** A text's first sentence, and the rest ("" when it is one sentence). */
export function firstSentence(text: string): [string, string] {
  const m = text.match(/^(.+?[.!?])\s+(\S[\s\S]*)$/);
  return m ? [m[1], m[2]] : [text, ""];
}

export function StepBar({ pages, current, states, onPick, uid }: { pages: { id: string; title: string }[]; current: string; states: Record<string, PageState>; onPick: (id: string) => void; uid: string }) {
  const all = [...pages, { id: REVIEW, title: PAGE_WORDS[REVIEW].title }];
  return (
    <div className="ic-steps" role="tablist" aria-label="The inputs, page by page">
      {all.map((p, i) => {
        const st = states[p.id] ?? { blocks: 0, warns: 0, changed: 0 };
        const on = p.id === current;
        const mark = st.blocks ? "block" : st.warns ? "warn" : "";
        const said = [st.blocks ? `${st.blocks} to fix` : "", st.warns ? `${st.warns} warning${st.warns === 1 ? "" : "s"}` : "", st.changed ? `${st.changed} changed` : ""].filter(Boolean).join(", ");
        return (
          <button
            key={p.id}
            type="button"
            role="tab"
            id={`${uid}-tab-${p.id}`}
            aria-selected={on}
            aria-controls={`${uid}-panel`}
            className={`ic-step${on ? " on" : ""}${p.id === REVIEW ? " review" : ""}${st.changed ? " changed" : ""}`}
            title={said ? `${p.title}: ${said}` : p.title}
            onClick={() => onPick(p.id)}
          >
            <span className={`ic-step-ico t-${(PAGE_ICON[p.id] ?? ["info", "ink"])[1]}`} aria-hidden="true">
              <Ico name={(PAGE_ICON[p.id] ?? ["info"])[0]} size={14} boxed={false} />
            </span>
            <span className="sr-only">{`${i + 1}. `}</span>
            <span className="ic-step-name">{PAGE_WORDS[p.id]?.short ?? p.title}</span>
            {mark && <span className={`ic-dot ${mark}`} aria-hidden="true" />}
            {said && <span className="sr-only">: {said}</span>}
          </button>
        );
      })}
    </div>
  );
}

/** One issue line: blocks the run (red, an alert), a warning (amber), or a note. */
export function IssueLine({ issue, id }: { issue: Issue; id?: string }) {
  return (
    <p id={id} className={`ic-msg ${issue.level}`} role={issue.level === "block" ? "alert" : undefined}>
      <span className="ic-msg-icon" aria-hidden="true">
        {issue.level === "block" ? (
          <svg width="14" height="14" viewBox="0 0 16 16">
            <circle cx="8" cy="8" r="7" fill="currentColor" />
            <path d="M8 4.4v4.4" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
            <circle cx="8" cy="11.3" r="1" fill="#fff" />
          </svg>
        ) : issue.level === "warn" ? (
          <svg width="14" height="14" viewBox="0 0 16 16">
            <path d="M8 1.6 15 14H1z" fill="currentColor" strokeLinejoin="round" />
            <path d="M8 6v3.8" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" />
            <circle cx="8" cy="11.8" r=".95" fill="#fff" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 16 16">
            <path d="M2.5 8h8M8 4.5 11.5 8 8 11.5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      <span className="sr-only">{issue.level === "block" ? "Blocks the run: " : issue.level === "warn" ? "Warning: " : "Note: "}</span>
      <span>{issue.text}</span>
    </p>
  );
}

/** "More": the rest of the explanation, typical values, the links both ways, what it changes, the ranges. */
function MorePanel({ f, rest, edit, id }: { f: InputField; rest: string; edit: FieldEdit; id: string }) {
  const range = f.low != null && f.high != null ? `${fmtNum(f.low)} to ${fmtNum(f.high)}${f.unit ? ` ${f.unit}` : ""}` : "";
  const linked = (f.linked ?? []).filter((k) => edit.names[k]);
  return (
    <div className="ic-more-panel ta-rise" id={id}>
      {rest && <p>{rest}</p>}
      <dl>
        {f.typical_words && (
          <>
            <dt>Typical</dt>
            <dd>{f.typical_words}</dd>
          </>
        )}
        {f.depends && (
          <>
            <dt>How</dt>
            <dd>{f.depends}</dd>
          </>
        )}
        {linked.length > 0 && (
          <>
            <dt>Linked to</dt>
            <dd className="ic-chip-list">
              {linked.map((k) => (
                <button key={k} type="button" className="ic-chip link" onClick={() => edit.go(k)}>
                  {edit.names[k]}
                </button>
              ))}
            </dd>
          </>
        )}
        {f.affects?.length ? (
          <>
            <dt>Changes</dt>
            <dd className="ic-chip-list">
              {f.affects.map((a) => (
                <span key={a} className="ic-chip out">
                  {a}
                </span>
              ))}
            </dd>
          </>
        ) : null}
        {range && (
          <>
            <dt>Accepted</dt>
            <dd>{range}</dd>
          </>
        )}
        {f.cap?.words && (
          <>
            <dt>Challenge</dt>
            <dd>{f.cap.words}</dd>
          </>
        )}
      </dl>
    </div>
  );
}

/** The model's range as a slim bar: the typical values shaded, the challenge's cap marked, the value a dot. */
export function RangeBar({ f, x, level }: { f: InputField; x: number | null; level: string }) {
  if (f.low == null || f.high == null || f.high <= f.low) return null;
  const lo = f.low;
  const hi = f.high;
  const log = lo > 0 && hi / lo >= 100;
  const pos = (v: number) => {
    const p = log ? (Math.log(Math.max(v, lo)) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) : (v - lo) / (hi - lo);
    return Math.max(0, Math.min(1, p)) * 100;
  };
  const t = f.typical;
  const cap = f.cap;
  const capAt = cap ? (cap.high ?? cap.low) : undefined;
  return (
    <span className={`ic-bar${log ? " log" : ""}`} aria-hidden="true">
      <span className="ic-bar-track">
        {t && <span className="ic-bar-typical" style={{ left: `${pos(t[0])}%`, width: `${Math.max(1.5, pos(t[1]) - pos(t[0]))}%` }} />}
        {capAt != null && <span className="ic-bar-cap" style={{ left: `${pos(capAt)}%` }} />}
        {x != null && Number.isFinite(x) && <span className={`ic-bar-dot ${level}`} style={{ left: `${pos(x)}%` }} />}
      </span>
      <span className="ic-bar-ends">
        <span>{fmtNum(lo)}</span>
        {t && <span className="ic-bar-key">typical</span>}
        {capAt != null && <span className="ic-bar-key cap">challenge</span>}
        <span>
          {fmtNum(hi)}
          {f.unit && f.unit.length <= 6 ? ` ${f.unit}` : ""}
        </span>
      </span>
    </span>
  );
}

export interface FieldEdit {
  draft: Record<string, Draft>;
  issues: Record<string, Issue[]>;
  changed: Set<string>;
  disabled: boolean;
  put: (key: string, value: Draft) => void;
  /** Each box's name ("Heating network · Return"), for the links. */
  names: Record<string, string>;
  /** The values the user set in the message (and on the card), and the boxes linked to each. */
  yours: Set<string>;
  linkedTo: Record<string, string[]>;
  /** Go to a box (its page, the cursor in it). */
  go: (key: string) => void;
  /** The brine's temperature at a depth from the gradient as typed (an aquifer's note). */
  tempAt?: (depthM: number) => number | null;
}

/** One parameter: its name, one line of explanation and "more", its box and range bar, its issues. */
export function ParamField({ f, edit, uid }: { f: InputField; edit: FieldEdit; uid: string }) {
  const [open, setOpen] = useState(false);
  const d = edit.draft[f.key] ?? "";
  const issues = edit.issues[f.key] ?? [];
  const top = issues.find((i) => i.level !== "note");
  const changed = edit.changed.has(f.key);
  const mine = edit.yours.has(f.key) && !changed;
  const level = top?.level ?? (changed ? "changed" : mine ? "mine" : "ok");
  const msgId = `${uid}-msg`;
  const helpId = `${uid}-help`;
  const wide = isRecords(f) || (f.kind === "list" && !!f.options?.length) || (f.kind === "choice" && (f.options?.length ?? 0) > 4);
  const was = changed && !isRecords(f) ? wasText(f) : "";
  const x = f.kind === "number" && typeof d === "string" ? numOf(d) : null;
  const [line, rest] = firstSentence(f.help ?? "");
  const links = (edit.linkedTo[f.key] ?? []).filter((k) => k !== f.key);
  // Not the project's own value (5 Nov): a dot, and a button that puts the default back. When
  // the card had the default, "was …" would say the same: the default's button says it alone.
  const offDefault = differsFromDefault(f, d);
  const valueIsDefault = hasDefault(f) && !differsFromDefault(f, fieldText(f, f.value));
  const hasMore = !!(rest || f.typical_words || f.depends || f.linked?.length || f.affects?.length || f.cap);
  return (
    <div className={`ic-field lvl-${level}${wide ? " wide" : ""}`} data-key={f.key}>
      <div className="ic-field-text">
        <span className="ic-field-name-line">
          {isRecords(f) || (f.kind === "list" && f.options?.length) || f.kind === "choice" ? (
            <span className="ic-field-name" id={`${uid}-name`}>
              {f.label}
            </span>
          ) : (
            <label className="ic-field-name" id={`${uid}-name`} htmlFor={uid}>
              {f.label}
            </label>
          )}
          {changed && !(offDefault && valueIsDefault) && <span className="ic-was">{was ? `was ${was}` : "changed"}</span>}
          {mine && (
            <span className="ic-chip mine">
              <Ico name="pen" size={11} boxed={false} />
              from your message
            </span>
          )}
          {links.map((k) => (
            <button key={k} type="button" className="ic-chip linked" title={`Linked to ${edit.names[k]}, which you set`} onClick={() => edit.go(k)}>
              <Ico name="link" size={11} boxed={false} />
              your {edit.names[k]?.split(" · ").pop()?.toLowerCase()}
            </button>
          ))}
          {offDefault && (
            <span className="ic-default">
              <span className="ic-default-dot" aria-hidden="true" />
              <span className="sr-only">Not the default. </span>
              <button type="button" className="ic-default-btn" disabled={edit.disabled} title={`Back to the default: ${defaultWords(f)}`} aria-label={`Reset ${f.label} to the default, ${defaultWords(f)}`} onClick={() => edit.put(f.key, defaultDraft(f))}>
                <Ico name="undo" size={11} boxed={false} />
                {isRecords(f) ? "default list" : `default ${defaultWords(f)}`}
              </button>
            </span>
          )}
        </span>
        {(line || hasMore) && (
          <span className="ic-help" id={helpId}>
            {line}
            {hasMore && (
              <button type="button" className="ic-more-btn" aria-expanded={open} aria-controls={`${uid}-more`} onClick={() => setOpen(!open)}>
                {open ? "less" : "more"}
              </button>
            )}
          </span>
        )}
      </div>
      <div className="ic-field-control">
        <Control f={f} d={d} edit={edit} uid={uid} invalid={top?.level === "block"} describedBy={`${top ? msgId : ""} ${line ? helpId : ""}`.trim() || undefined} />
        {f.kind === "number" && <RangeBar f={f} x={x} level={top?.level ?? "ok"} />}
        {f.kind === "list" && !f.options?.length && f.low != null && (
          <span className="ic-list-hint">
            each {fmtNum(f.low)} to {fmtNum(f.high ?? f.low)} {f.unit}, commas between
          </span>
        )}
      </div>
      {issues.length > 0 && (
        <div className="ic-issues">
          {issues.map((i, k) => (
            <IssueLine key={k} issue={i} id={k === 0 && i.level !== "note" ? msgId : undefined} />
          ))}
        </div>
      )}
      {open && <MorePanel f={f} rest={rest} edit={edit} id={`${uid}-more`} />}
    </div>
  );
}

const numOf = (t: string) => {
  const s = t.trim().replace(",", ".").replace("−", "-");
  return s && /^[-+]?(\d+\.?\d*|\.\d+)$/.test(s) ? Number(s) : null;
};

/** The value before the change, as the field shows it ("200 mD", "lowest cost"). */
export function wasText(f: InputField): string {
  const t = fieldText(f, f.value);
  if (f.kind === "choice") return f.words?.[String(t)] ?? String(t);
  if (Array.isArray(t)) return (t as string[]).map((x) => f.words?.[x] ?? x).join(", ") || "none";
  return `${t || "empty"}${t && f.unit ? ` ${f.unit}` : ""}`;
}

function Control({ f, d, edit, uid, invalid, describedBy }: { f: InputField; d: Draft; edit: FieldEdit; uid: string; invalid: boolean; describedBy?: string }) {
  if (f.kind === "choice") {
    const opts = f.options ?? [];
    if (opts.length <= 4)
      return (
        <span className="ic-seg" role="radiogroup" aria-labelledby={`${uid}-name`}>
          {opts.map((o) => (
            <label key={o} className={String(d) === o ? "on" : ""}>
              <input type="radio" name={uid} value={o} checked={String(d) === o} disabled={edit.disabled} onChange={() => edit.put(f.key, o)} />
              {f.words?.[o] ?? o}
            </label>
          ))}
        </span>
      );
    return (
      <span className="ic-select">
        <select id={uid} value={String(d)} disabled={edit.disabled} aria-labelledby={`${uid}-name`} aria-invalid={invalid} aria-describedby={describedBy} onChange={(e) => edit.put(f.key, e.target.value)}>
          {opts.map((o) => (
            <option key={o} value={o}>
              {f.words?.[o] ?? o}
            </option>
          ))}
        </select>
      </span>
    );
  }
  if (f.kind === "list" && f.options?.length) {
    const picked = new Set(Array.isArray(d) ? (d as string[]) : []);
    return (
      <span className={`ic-chips${f.key === "exclude" ? " neg" : ""}`} role="group" aria-labelledby={`${uid}-name`}>
        {f.options.map((o) => (
          <label key={o} className={picked.has(o) ? "on" : ""}>
            <input type="checkbox" checked={picked.has(o)} disabled={edit.disabled} onChange={(e) => edit.put(f.key, e.target.checked ? [...picked, o] : [...picked].filter((x) => x !== o))} />
            {f.words?.[o] ?? o}
          </label>
        ))}
      </span>
    );
  }
  if (isRecords(f)) return <RecordsField f={f} d={Array.isArray(d) ? (d as string[][]) : []} edit={edit} uid={uid} />;
  return (
    <span className={`ic-box${invalid ? " bad" : ""}`}>
      <input
        id={uid}
        type="text"
        inputMode={f.kind === "list" ? "text" : "decimal"}
        autoComplete="off"
        spellCheck={false}
        value={String(d)}
        placeholder={f.required ? "required" : undefined}
        disabled={edit.disabled}
        aria-invalid={invalid}
        aria-required={f.required || undefined}
        aria-describedby={describedBy}
        onChange={(e) => edit.put(f.key, e.target.value)}
      />
      {f.unit && <span className="unit">{f.unit}</span>}
    </span>
  );
}

const KIND_WORDS: Record<string, string> = { known: "known", assumed: "assumed", given: "yours" };

/**
 * A `records` field: a small table, a row per record (an aquifer), a box per column; add and
 * remove. Each record says what it is (the server's `kinds` and `notes`; one added here is
 * "new"); a box the server fills when left empty shows "auto".
 */
export function RecordsField({ f, d, edit, uid }: { f: InputField; d: string[][]; edit: FieldEdit; uid: string }) {
  const cols: RecordColumn[] = f.columns ?? [];
  const what = (f.label || "record").toLowerCase().replace(/s$/, "");
  const max = f.max_items ?? Infinity;
  const min = f.min_items ?? 0;
  const was = fieldText(f, f.value) as string[][];
  const put = (rows: string[][]) => edit.put(f.key, rows);
  const add = () => {
    // A new record starts from the server's new_item (an aquifer: the known one's rock, its
    // depth to give), else from the last one's values.
    const last = d[d.length - 1];
    const start = f.new_item;
    put([...d, cols.map((c, j) => (start ? (start[c.key] == null ? "" : String(start[c.key])) : (last?.[j] ?? "")))]);
  };
  // Which of the server's records a row is: by place while none was added or removed.
  const sameRows = d.length === was.length;
  const note = (i: number, r: string[]) => {
    const depth = Number((r[0] ?? "").replace(",", "."));
    const moved = !sameRows || (r[0] ?? "").trim() !== (was[i]?.[0] ?? "").trim();
    if (!moved && f.notes?.[i]) return f.notes[i];
    const t = Number.isFinite(depth) && r[0]?.trim() ? edit.tempAt?.(depth) : null;
    return t != null ? `about ${Math.round(t)} °C from the gradient` : "";
  };
  return (
    <div className="ic-records">
      <table>
        <thead>
          <tr>
            <th scope="col">
              <span className="sr-only">{f.label}</span>
            </th>
            {cols.map((c) => (
              <th key={c.key} scope="col" title={c.help}>
                {c.label}
                {c.unit && <small>{c.unit}</small>}
              </th>
            ))}
            <th scope="col">
              <span className="sr-only">Remove</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {d.map((r, i) => {
            const kind = sameRows ? f.kinds?.[i] : i === 0 ? f.kinds?.[0] : undefined;
            const isNew = i >= was.length || (!sameRows && i > 0 && !was.some((w) => (w[0] ?? "").trim() === (r[0] ?? "").trim()));
            const words = isNew ? "new" : kind ? (KIND_WORDS[kind] ?? kind) : i === 0 ? "known" : "";
            const n = note(i, r);
            return (
              <Fragment key={i}>
                <tr className={n ? "has-note" : undefined}>
                  <th scope="row">
                    {i + 1}
                    {words && <small className={`ic-rec-kind k-${isNew ? "new" : (kind ?? "known")}`}>{words}</small>}
                  </th>
                  {cols.map((c, j) => {
                    const t = r[j] ?? "";
                    const optional = cellOptional(f, j);
                    const bad = cellProblem(c, t, optional);
                    return (
                      <td key={c.key}>
                        <input
                          id={i === 0 && j === 0 ? uid : `${uid}-${i}-${c.key}`}
                          className={bad ? "bad" : t.trim() || !optional ? "" : "auto"}
                          type="text"
                          inputMode="decimal"
                          autoComplete="off"
                          value={t}
                          placeholder={optional ? "auto" : "required"}
                          disabled={edit.disabled}
                          aria-label={`${what} ${i + 1}, ${c.label}${c.unit ? ` (${c.unit})` : ""}`}
                          aria-invalid={!!bad}
                          title={
                            bad ??
                            (optional && !t.trim()
                              ? c.key === "pressure_bar"
                                ? "Left empty: the brine column's pressure at this depth"
                                : "Left empty: the known aquifer's value"
                              : c.low != null && c.high != null
                                ? `${fmtNum(c.low)} to ${fmtNum(c.high)}${c.unit ? ` ${c.unit}` : ""}`
                                : undefined)
                          }
                          onChange={(e) => put(d.map((row, k) => (k === i ? row.map((x, m) => (m === j ? e.target.value : x)) : row)))}
                        />
                      </td>
                    );
                  })}
                  <td>
                    {d.length > Math.max(min, 1) && i > 0 && (
                      <button type="button" className="ic-rec-remove" disabled={edit.disabled} aria-label={`Remove ${what} ${i + 1}`} onClick={() => put(d.filter((_, k) => k !== i))}>
                        ×
                      </button>
                    )}
                  </td>
                </tr>
                {n && (
                  <tr className="ic-rec-note">
                    <td />
                    <td colSpan={cols.length + 1}>{n}</td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      {d.length < max && (
        <button type="button" className="link-btn ic-rec-add" disabled={edit.disabled} onClick={add}>
          + Add {/^[aeiou]/.test(what) ? "an" : "a"} {what}
        </button>
      )}
      {f.new_item && <span className="ic-list-hint">Boxes left “auto” take the known {what}’s value (the pressure: the brine column’s at its depth).</span>}
    </div>
  );
}

export interface ToggleState {
  on: boolean;
  /** The amount typed for a switch with a size (a network's km, solar MWp, a store's MWh). */
  text: string;
}

/** A switch that needs an amount when on: the network's length, the panels' or the store's size. */
export const hasAmount = (t: InputToggle) => t.kind === "km" || t.kind === "amount";

/** What is wrong with a switch's amount, or null. */
export function amountProblem(t: InputToggle, s: ToggleState | undefined): string | null {
  if (!hasAmount(t) || !s?.on) return null;
  if (!s.text.trim()) return `Required: give the ${t.kind === "km" ? "length" : "size"}, or switch it off.`;
  const v = Number(s.text.replace(",", "."));
  if (!Number.isFinite(v) || v <= 0) return "Give a number above 0.";
  if (t.max != null && v > t.max) return `At most ${fmtNum(t.max)} ${t.unit ?? "km"}.`;
  if (t.min != null && v < t.min) return `At least ${fmtNum(t.min)} ${t.unit ?? "km"}.`;
  return null;
}

/** One switch: the control, its label and hint, the amount when it needs one, its warning and "More". */
export function ToggleRow({ t, s, onChange, warning, refused, disabled, id }: { t: InputToggle; s: ToggleState; onChange: (next: Partial<ToggleState>) => void; warning?: string; refused?: string; disabled: boolean; id: string }) {
  const [open, setOpen] = useState(false);
  const box = `${id}-${t.id}-on`;
  const bad = amountProblem(t, s) ?? refused ?? null;
  const more: [string, string][] = [
    ["What it does", t.help ?? ""],
    ["Typical", t.typical_words ?? ""],
    ["Linked to", t.depends ?? ""],
  ];
  return (
    <div className={`inputs-opt ic-toggle${s.on ? " on" : ""}`} data-key={t.id}>
      <label className="inputs-opt-switch" htmlFor={box}>
        <input id={box} type="checkbox" role="switch" checked={s.on} disabled={disabled} aria-describedby={t.hint ? `${box}-hint` : undefined} onChange={(e) => onChange({ on: e.target.checked })} />
        <span className="inputs-opt-track" aria-hidden="true">
          <span className="inputs-opt-thumb" />
        </span>
      </label>
      <div className="inputs-opt-text">
        <label className="inputs-opt-label" htmlFor={box}>
          {t.label}
        </label>
        {(t.hint || more.some(([, v]) => v)) && (
          <span id={`${box}-hint`} className="inputs-opt-hint">
            {t.hint}
            {more.some(([, v]) => v) && (
              <button type="button" className="ic-more-btn" aria-expanded={open} aria-controls={`${box}-more`} onClick={() => setOpen(!open)}>
                {open ? "less" : "more"}
              </button>
            )}
          </span>
        )}
        {hasAmount(t) && s.on && (
          <span className="inputs-opt-km ta-rise">
            <label htmlFor={`${id}-${t.id}`}>{t.kind === "km" ? "Length" : "Size"}</label>
            <span className={`ic-box small${bad ? " bad" : ""}`}>
              <input
                id={`${id}-${t.id}`}
                type="text"
                inputMode="decimal"
                autoComplete="off"
                placeholder={t.example ?? "e.g. 5"}
                value={s.text}
                disabled={disabled}
                aria-invalid={!!bad}
                onChange={(e) => onChange({ text: e.target.value })}
              />
              <span className="unit">{t.unit ?? "km"}</span>
            </span>
          </span>
        )}
        {bad && <IssueLine issue={{ level: "block", text: bad }} />}
        {warning && <IssueLine issue={{ level: "warn", text: warning }} />}
        {open && (
          <div className="ic-more-panel ta-rise" id={`${box}-more`}>
            <dl>
              {more
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <Fragment key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </Fragment>
                ))}
            </dl>
          </div>
        )}
      </div>
    </div>
  );
}

/** One row of a page: its icon, name, one line of what it is and where its value comes from; its value as read; its boxes or switches. */
/** A row's title on the card where it differs from the server's label (4 Nov: the stops row
 * holds every unit's stops, so it is called Maintenance). */
export const ROW_TITLE: Record<string, string> = { "Doublet stops": "Maintenance" };

export function RowBlock({ row, mine, children, uid }: { row: InputRow; mine: boolean; children?: ReactNode; uid: string }) {
  const info = !row.fields?.length && !row.toggles?.length;
  const [icon, tint] = ROW_ICON[row.label] ?? PAGE_ICON[row.page ?? ""] ?? ["info", "ink"];
  const [line, rest] = firstSentence(row.help ?? "");
  const [open, setOpen] = useState(false);
  return (
    <section className={`ic-row${mine || row.changed ? " changed" : ""}${info ? " info" : ""}`} aria-labelledby={`${uid}-h`}>
      <div className="ic-row-head">
        <Ico name={icon} tint={tint} />
        <div className="ic-row-titles">
          <h4 id={`${uid}-h`}>{ROW_TITLE[row.label] ?? row.label}</h4>
          {line && (
            <span className="ic-row-help">
              {line}
              {rest && (
                <button type="button" className="ic-more-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
                  {open ? "less" : "more"}
                </button>
              )}
            </span>
          )}
          {open && rest && <span className="ic-row-help ic-row-more ta-rise">{rest}</span>}
        </div>
        <SourceLine row={row} mine={mine} />
      </div>
      <p className="ic-row-value">
        <span className="ic-asread">as read</span>
        {row.value}
      </p>
      {info && row.locked && (
        <p className="ic-row-why">
          <Ico name="info" size={13} boxed={false} />
          {row.locked}
        </p>
      )}
      {children}
    </section>
  );
}

/** What the user set, and what each value affects: other boxes (to go to) and the design. */
export function YoursBanner({ keys, fields, edit, origin }: { keys: string[]; fields: Map<string, InputField>; edit: FieldEdit; origin: (key: string) => string }) {
  const [open, setOpen] = useState(true);
  if (!keys.length) return null;
  const value = (f: InputField) => {
    const d = edit.draft[f.key];
    if (isRecords(f)) return recordsWords(f, d ?? []);
    if (f.kind === "choice") return f.words?.[String(d)] ?? String(d);
    if (Array.isArray(d)) return (d as unknown[]).length ? (d as string[]).map((x) => (typeof x === "string" ? (f.words?.[x] ?? x) : "")).join(", ") : "none";
    return `${String(d ?? "")}${f.unit ? ` ${f.unit}` : ""}`;
  };
  return (
    <section className={`ic-yours${open ? "" : " folded"}`} aria-label="What you set and what it affects">
      <div className="ic-yours-head">
        <Ico name="pen" tint="teal" size={14} />
        <b>{keys.length === 1 ? "You set 1 input" : `You set ${keys.length} inputs`}</b>
        <span className="ic-yours-sub">{open ? "each changes other inputs and the design:" : keys.map((k) => fields.get(k)?.label ?? k).join(", ")}</span>
        <button type="button" className="ic-more-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "hide" : "show"}
        </button>
      </div>
      {open && (
        <ul>
          {keys.map((k) => {
            const f = fields.get(k);
            if (!f) return null;
            const linked = (f.linked ?? []).filter((x) => edit.names[x]);
            return (
              <li key={k}>
                <button type="button" className="ic-chip mine strong" title={origin(k)} onClick={() => edit.go(k)}>
                  {edit.names[k]} <b>{value(f)}</b>
                </button>
                <span className="ic-yours-arrow" aria-hidden="true">→</span>
                <span className="ic-chip-list">
                  {linked.slice(0, 3).map((x) => (
                    <button key={x} type="button" className="ic-chip link" onClick={() => edit.go(x)}>
                      <Ico name="link" size={11} boxed={false} />
                      {edit.names[x]}
                    </button>
                  ))}
                  {linked.length > 3 && (
                    <span className="ic-chip link" title={linked.slice(3).map((x) => edit.names[x]).join(", ")}>
                      +{linked.length - 3} more linked
                    </span>
                  )}
                  {(f.affects ?? []).map((a) => (
                    <span key={a} className="ic-chip out">
                      {a}
                    </span>
                  ))}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
