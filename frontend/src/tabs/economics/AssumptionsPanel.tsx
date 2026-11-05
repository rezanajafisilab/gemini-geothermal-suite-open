// The conversation's cost assumptions: every price, unit cost, O&M cost and lifetime the server
// lists, grouped as it groups them, each with its default, a "changed" mark, a reset and the
// source it comes from. Edits wait until Apply, which sends one PUT /api/assumptions; the server
// recomputes every design's economics. "Reset all" puts every assumption back to its default.
//
// The form lives in a slide-over drawer (AssumptionsDrawer) opened from a toolbar button that says
// its state (AssumptionsBar, with the key prices beside it). The edits are held by the tab
// (useAssumptionsForm), so closing the drawer keeps them: a compact Apply bar (ApplyBar) stays in
// sight at the bottom of the page until they are applied or discarded.

import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";

import { Cross, Retry, Spinner } from "../../components/Icons";
import { AskButton, type ApiResult, type Assumptions, type AssumptionsPatch, type Workbench } from "../../workbench";
import {
  buildPatch,
  changedCount,
  defaultOf,
  fieldsFor,
  groupsFor,
  isChanged,
  parseField,
  resetAllPatch,
  same,
  toDisplay,
  valueOf,
  type Draft,
  type FieldDef,
} from "./assumptions";
import { lowerFirst } from "../sensitivity/params";

type Apply = (patch: AssumptionsPatch) => Promise<ApiResult<Workbench>>;

export interface AssumptionsForm {
  edits: Record<string, string>;
  draft: Draft;
  /** Assumptions that differ from their defaults (applied). */
  nChanged: number;
  /** Edits that would change a value (not applied yet). */
  nDraft: number;
  nErrors: number;
  /** Anything typed, even back to the applied value. */
  touched: boolean;
  pending: null | "apply" | "reset";
  error: string | null;
  done: string | null;
  edit: (f: FieldDef, text: string) => void;
  resetField: (f: FieldDef) => void;
  discard: () => void;
  applyDraft: () => void;
  resetAll: () => void;
}

const EMPTY_DRAFT: Draft = { patch: {}, errors: {}, changes: [] };

/** The edits and what Apply / Reset all do with them; `a` is null until the workbench has loaded. */
export function useAssumptionsForm(a: Assumptions | null, apply: Apply): AssumptionsForm {
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<null | "apply" | "reset">(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const draft = a ? buildPatch(edits, a) : EMPTY_DRAFT;
  const nErrors = Object.keys(draft.errors).length;
  const nChanged = a ? changedCount(a) : 0;
  const nDraft = draft.changes.length;

  // The "applied" note goes after a while; the button and the charts say the rest.
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(null), 6000);
    return () => clearTimeout(t);
  }, [done]);

  const send = async (patch: AssumptionsPatch, kind: "apply" | "reset", count: number) => {
    setPending(kind);
    setError(null);
    setDone(null);
    const res = await apply(patch);
    setPending(null);
    if (res.ok) {
      setEdits({});
      setDone(kind === "reset" ? "Every assumption is back at its default; the costs are recomputed." : `Applied ${count} change${count === 1 ? "" : "s"}; the costs are recomputed for every design.`);
    } else {
      setError(res.offline ? "The agent server isn't answering; nothing changed." : res.message);
    }
  };

  return {
    edits,
    draft,
    nChanged,
    nDraft,
    nErrors,
    touched: Object.keys(edits).length > 0,
    pending,
    error,
    done,
    edit: (f, text) => {
      setDone(null);
      setEdits((e) => ({ ...e, [f.id]: text }));
    },
    resetField: (f) => {
      const def = a ? defaultOf(a, f) : undefined;
      if (def == null) return;
      setDone(null);
      setEdits((e) => ({ ...e, [f.id]: toDisplay(def, f) }));
    },
    discard: () => {
      setEdits({});
      setError(null);
    },
    applyDraft: () => {
      if (!nDraft || nErrors || pending) return;
      void send(draft.patch, "apply", nDraft);
    },
    resetAll: () => {
      if (pending || !a) return;
      if (!nChanged) {
        setEdits({});
        return;
      }
      void send(resetAllPatch(a), "reset", nChanged);
    },
  };
}

/** One line on what the form is doing: an error, Applying, edits waiting, or what was done. */
function statusText(form: AssumptionsForm): { text: string; tone: "error" | "pending" | "plain" } | null {
  if (form.error) return { text: form.error, tone: "error" };
  if (form.pending) return { text: form.pending === "reset" ? "Resetting…" : "Recomputing every design…", tone: "pending" };
  if (form.nErrors) return { text: `Fix ${form.nErrors} value${form.nErrors === 1 ? "" : "s"} first`, tone: "error" };
  if (form.nDraft) return { text: `${form.nDraft} change${form.nDraft === 1 ? "" : "s"} not applied yet`, tone: "plain" };
  if (form.touched) return { text: "Nothing to apply: the values are as they were", tone: "plain" };
  if (form.done) return { text: form.done, tone: "plain" };
  return null;
}

function Status({ form }: { form: AssumptionsForm }) {
  const s = statusText(form);
  return (
    <span className="ec-status" role="status" aria-live="polite">
      {s?.tone === "error" ? (
        <span className="ec-error">{s.text}</span>
      ) : s?.tone === "pending" ? (
        <span className="ec-pending">
          <Spinner size={14} /> {s.text}
        </span>
      ) : (
        (s?.text ?? "")
      )}
    </span>
  );
}

function ApplyButton({ form }: { form: AssumptionsForm }) {
  return (
    <button type="button" className="btn btn-ink ta-btn ta-ink" disabled={!form.nDraft || form.nErrors > 0 || form.pending != null} onClick={form.applyDraft}>
      {form.pending === "apply" ? <Spinner size={14} light /> : null}
      {form.pending === "apply" ? "Applying" : form.nDraft ? `Apply ${form.nDraft}` : "Apply"}
    </button>
  );
}

/** Sliders: the assumptions button's glyph. */
function Sliders({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2 4.5h7M13 4.5h1M2 11.5h2M8 11.5h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="11" cy="4.5" r="1.9" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="6" cy="11.5" r="1.9" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

/**
 * The toolbar above the charts: the Assumptions button, which says whether anything differs from
 * the defaults, and the prices the costs were computed with (the server's "prices" group: energy,
 * CO₂ and the discount rate), each opening the drawer at its field.
 */
export function AssumptionsBar({
  a,
  form,
  open,
  onOpen,
  buttonRef,
}: {
  a: Assumptions;
  form: AssumptionsForm;
  open: boolean;
  onOpen: (field?: string) => void;
  buttonRef: RefObject<HTMLButtonElement | null>;
}) {
  const fields = fieldsFor(a).filter((f) => f.group === "prices");
  const state = form.nChanged ? `${form.nChanged} changed` : "all at defaults";
  return (
    <div className="ec-toolbar ta-rise" style={{ animationDelay: ".05s" }}>
      <button
        ref={buttonRef}
        type="button"
        className={`ec-assume-btn ta-btn${form.nChanged ? " is-changed" : ""}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => onOpen()}
      >
        <Sliders />
        <span className="ec-assume-btn-label">Assumptions</span>
        <span className="ec-assume-btn-sep" aria-hidden="true">
          ·
        </span>
        <span className="ec-assume-btn-state">
          {form.nChanged > 0 && <span className="ec-dot" aria-hidden="true" />}
          {state}
        </span>
        {form.nDraft > 0 && <span className="ec-edited">{form.nDraft} not applied</span>}
      </button>
      <ul className="ec-keys" aria-label="The costs are computed with">
        {fields.map((f) => {
          const changed = isChanged(a, f);
          const v = toDisplay(valueOf(a, f), f);
          return (
            <li key={f.id}>
              <button
                type="button"
                className={`ec-key ta-btn${changed ? " is-changed" : ""}`}
                title={`Change ${lowerFirst(f.label)}${f.source ? `. Source: ${f.source}` : ""}`}
                onClick={() => onOpen(f.id)}
              >
                {changed && <span className="ec-dot" aria-hidden="true" />}
                <span className="ec-key-label">{f.label}</span>
                <strong>{v}</strong>
                {f.unit && <span className="ec-key-unit">{f.unit}</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** While edits wait (or Apply is on its way), a compact bar that stays at the bottom of the page. */
export function ApplyBar({ form, onReview }: { form: AssumptionsForm; onReview: () => void }) {
  const show = form.touched || form.pending != null || form.error != null || form.done != null;
  if (!show) return null;
  const busy = form.pending != null;
  return (
    <div className={`ec-applybar ta-rise${form.done && !form.touched && !busy ? " is-done" : ""}`} role="region" aria-label="Assumption changes">
      {form.nDraft > 0 && !busy && <span className="ec-dot is-draft" aria-hidden="true" />}
      <Status form={form} />
      {(form.touched || busy) && (
        <span className="ec-applybar-actions">
          <ApplyButton form={form} />
          {form.touched && (
            <button type="button" className="btn btn-soft ta-btn ta-soft" disabled={busy} onClick={form.discard}>
              Discard
            </button>
          )}
        </span>
      )}
      <button type="button" className="link-btn ec-applybar-review" onClick={onReview}>
        {form.touched ? "Review" : "Open assumptions"}
      </button>
    </div>
  );
}

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled]), select, textarea')).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  );
}

/**
 * The form as a slide-over from the right, over a scrim: Esc, the close button or a click on the
 * scrim closes it; Tab stays inside; focus goes to the close button (or the field asked for) and
 * back to the opener on close. Rendered into <body> (under a .tab-economics wrapper for its styles)
 * so no transformed ancestor clips it.
 */
export function AssumptionsDrawer({
  a,
  form,
  code,
  focusField,
  onClose,
  returnTo,
}: {
  a: Assumptions;
  form: AssumptionsForm;
  code: string;
  /** A field id to focus when it opens. */
  focusField?: string | null;
  onClose: () => void;
  returnTo: RefObject<HTMLElement | null>;
}) {
  const uid = useId();
  const box = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const before = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const target = (focusField && box.current?.querySelector<HTMLElement>(`[data-field="${CSS.escape(focusField)}"]`)) || box.current?.querySelector<HTMLElement>("[data-autofocus]");
    target?.focus();
    if (target instanceof HTMLInputElement) target.select();
    const onKey = (e: KeyboardEvent) => {
      if (!box.current) return;
      if (e.key === "Escape") {
        e.preventDefault();
        close.current();
      } else if (e.key === "Tab") {
        const items = focusables(box.current);
        if (!items.length) return e.preventDefault();
        const first = items[0];
        const last = items[items.length - 1];
        const inside = box.current.contains(document.activeElement);
        if (e.shiftKey && (document.activeElement === first || !inside)) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && (document.activeElement === last || !inside)) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    const ret = returnTo.current;
    return () => {
      document.removeEventListener("keydown", onKey);
      const back = before && before.isConnected && before !== document.body ? before : ret;
      back?.focus();
    };
    // Focus once, when it opens.
  }, []);

  const fields = fieldsFor(a);
  return createPortal(
    <div className="tab-economics ec-drawer-root">
      <div className="ec-scrim" aria-hidden="true" onMouseDown={() => close.current()} />
      <aside ref={box} className="ec-drawer" role="dialog" aria-modal="true" aria-labelledby={`${uid}-h`} aria-busy={form.pending != null}>
        <header className="ec-assume-head">
          <div className="ec-assume-titles">
            <h2 id={`${uid}-h`}>Assumptions</h2>
            <p>
              {form.nChanged ? (
                <>
                  <span className="ec-dot" aria-hidden="true" />
                  {form.nChanged} changed from the default
                </>
              ) : (
                "All at their defaults"
              )}
              {form.nDraft > 0 && <span className="ec-edited">{form.nDraft} not applied</span>}
            </p>
          </div>
          <button type="button" className="ec-drawer-x ta-btn ta-soft" aria-label="Close" title="Close (Esc)" data-autofocus onClick={() => close.current()}>
            <Cross size={11} />
          </button>
        </header>

        <div className="ec-assume-body">
          <p className="ec-assume-lead">Apply recomputes the costs of every design in this chat; the physics stays as it is. Closing keeps what you typed.</p>
          {groupsFor(fields).map((g) => (
            <fieldset key={g.id} className="ec-group">
              <legend>{g.label}</legend>
              {g.fields.map((f) => (
                <Field
                  key={f.id}
                  f={f}
                  a={a}
                  text={form.edits[f.id]}
                  error={form.draft.errors[f.id]}
                  pending={form.pending != null}
                  onEdit={(t) => form.edit(f, t)}
                  onReset={() => form.resetField(f)}
                />
              ))}
            </fieldset>
          ))}
          {a.notes?.length > 0 && (
            <div className="ec-notes">
              <h3>Notes</h3>
              <ul>
                {a.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          )}
          <AskButton context={`the cost assumptions on the Economics tab (${code} selected)`} question={`Which of these assumptions matters most for ${code}'s cost of heat?`} label="Ask which ones matter" />
        </div>

        <footer className="ec-assume-foot">
          <Status form={form} />
          <div className="ec-assume-actions">
            <ApplyButton form={form} />
            {form.touched && (
              <button type="button" className="btn btn-soft ta-btn ta-soft" disabled={form.pending != null} onClick={form.discard}>
                Discard
              </button>
            )}
            <button type="button" className="link-btn ec-reset-all" disabled={form.pending != null || (!form.nChanged && !form.touched)} onClick={form.resetAll}>
              <Retry size={13} /> Reset all
            </button>
          </div>
        </footer>
      </aside>
    </div>,
    document.body,
  );
}

function Field({
  f,
  a,
  text,
  error,
  pending,
  onEdit,
  onReset,
}: {
  f: FieldDef;
  a: Assumptions;
  text: string | undefined;
  error: string | undefined;
  pending: boolean;
  onEdit: (t: string) => void;
  onReset: () => void;
}) {
  const id = useId();
  const current = valueOf(a, f);
  const def = defaultOf(a, f);
  const shown = text ?? toDisplay(current, f);
  const changed = isChanged(a, f);
  // Compared as numbers, so "790000" typed over "790,000" is no edit.
  const typed = text != null ? parseField(text, f) : null;
  const edited = typed != null && !(typed.ok && current != null && same(typed.value, current));
  const atDefault = def != null && (typed ? typed.ok && same(typed.value, def) : current != null && same(current, def));
  const defText = def != null ? `${toDisplay(def, f)}${f.unit ? ` ${f.unit}` : ""}` : null;
  return (
    <div className={`ec-field${changed ? " changed" : ""}${edited ? " edited" : ""}${error ? " invalid" : ""}`}>
      <div className="ec-field-row">
        <label htmlFor={id} className="ec-field-label">
          {f.label}
          {changed && !edited && (
            <span className="ec-changed" title={`Changed from the default (${defText})`}>
              <span className="ec-dot" aria-hidden="true" />
              changed
            </span>
          )}
          {edited && <span className="ec-edited">not applied</span>}
        </label>
        <span className="ec-input">
          <input
            id={id}
            data-field={f.id}
            type="text"
            inputMode={f.integer ? "numeric" : "decimal"}
            autoComplete="off"
            spellCheck={false}
            value={shown}
            disabled={pending}
            aria-invalid={!!error}
            aria-describedby={`${id}-help${error ? ` ${id}-err` : ""}`}
            onChange={(e) => onEdit(e.target.value)}
          />
          <span className="ec-input-unit">{f.unit}</span>
        </span>
      </div>
      <div className="ec-field-foot">
        <span id={`${id}-help`} className="ec-help">
          {defText && <>Default {defText}</>}
          {defText && f.source && " · "}
          {f.source}
        </span>
        {!atDefault && def != null && (
          <button type="button" className="link-btn ec-reset" disabled={pending} onClick={onReset} aria-label={`Reset ${f.label} to its default, ${defText}`}>
            Reset
          </button>
        )}
      </div>
      {error && (
        <p id={`${id}-err`} className="ec-field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
