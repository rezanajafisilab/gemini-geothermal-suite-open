// "Edit and run": the design-level changes the backend accepts. Each doublet one by one (its
// aquifer, which half of it the producer and the injectors open, one or two injectors, a treatment
// train of its own, its own flow cap), how the doublets share the brine, the reservoir's
// temperature, each unit's size and the network returns. "Run as new design" runs it end to end
// on the server (GEMINI's wells, the year, costs, the challenge's checks) as a user design (U1, U2
// …), then shows it. Only what differs from the design is sent.

import { useEffect, useId, useState, type ReactNode } from "react";

import { Spinner } from "../../components/Icons";
import { useWorkbench, type Design, type Dispatch, type Opening } from "../../workbench";
import { useRemembered } from "./remember";
import {
  DISPATCH_WORDS,
  FLOW_CAP,
  FLOW_MIN,
  describeChanges,
  diffChanges,
  doubletForm,
  editBase,
  editForm,
  fmtValue,
  gasModeOf,
  hasErrors,
  newDoublet,
  type DoubletForm,
  type EditForm,
  type EditKey,
} from "./plant";

interface Props {
  design: Design;
  scope: string;
  /** A field to focus (a unit's context menu, "Change its size"): its id's end, and when asked. */
  focus?: { field: string; at: number } | null;
}

/** A row of choices as radio buttons. */
function Choice<T extends string | number>({ label, value, options, onChange, changed, disabled }: { label: string; value: T; options: { id: T; text: string; title?: string }[]; onChange: (v: T) => void; changed?: boolean; disabled?: boolean }) {
  return (
    <div className={`dz-choice${changed ? " changed" : ""}`} role="radiogroup" aria-label={label}>
      <span className="dz-choice-label" aria-hidden="true">
        {label}
      </span>
      <span className="dz-choice-opts">
        {options.map((o) => (
          <button key={String(o.id)} type="button" role="radio" aria-checked={o.id === value} title={o.title} className="dz-chip ta-btn ta-chip" disabled={disabled} onClick={() => onChange(o.id)}>
            {o.text}
          </button>
        ))}
      </span>
    </div>
  );
}

const OPENINGS: { id: Opening; text: string; title: string }[] = [
  { id: "full", text: "Full", title: "Open over the whole 100 m of the aquifer" },
  { id: "upper", text: "Upper ½", title: "Open over the upper 50 m: shallower, a little cooler, half the productivity" },
  { id: "lower", text: "Lower ½", title: "Open over the lower 50 m: deeper, a little hotter, half the productivity" },
];

/** How a doublet's flow is set, in words: "as needed, 50 to 300 m³/h", "fixed at 200 m³/h". */
function rateWords(d: { max_flow_m3h: string; min_flow_m3h?: string }): string {
  const cap = Number((d.max_flow_m3h || "").replace(",", ".")) || FLOW_CAP;
  const least = Number((d.min_flow_m3h || "").replace(",", ".")) || FLOW_MIN;
  if (least >= cap) return `Fixed at ${cap} m³/h whenever it runs`;
  return `As the day needs, ${least} to ${cap} m³/h`;
}

export function EditPanel({ design, scope, focus }: Props) {
  const wb = useWorkbench();
  const uid = useId();
  // Asked for a field: focus it, its value selected, in the middle of the panel.
  useEffect(() => {
    if (!focus) return;
    const el = document.getElementById(`${uid}-${focus.field}`) as HTMLInputElement | null;
    if (!el) return;
    el.focus({ preventScroll: true });
    el.select();
    el.scrollIntoView({ block: "center", behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [focus?.at, uid]); // eslint-disable-line react-hooks/exhaustive-deps
  const base = editBase(design);
  const [form, setForm] = useRemembered<EditForm>(scope, "edit-v2", () => editForm(design));
  const [state, setState] = useState<{ kind: "idle" } | { kind: "running" } | { kind: "error"; message: string }>({ kind: "idle" });
  const { changes, errors } = diffChanges(base, form);
  const lines = describeChanges(base, changes);
  const invalid = hasErrors(errors);
  const running = state.kind === "running";
  const hasWells = base.doublets.length > 0;
  // A gas-free design's electric boiler and gas: kept as they are by an edit (not editable yet).
  const eboiler = design.graph.nodes.find((n) => n.type === "electric_boiler");
  const eboilerMw = design.plant.sizes_mw.electric_boiler ?? eboiler?.values.power_mw ?? 0;
  const gasMode = gasModeOf(design.graph.nodes.find((n) => n.type === "gas"));

  const set = <K extends keyof EditForm>(k: K, v: EditForm[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setDoublet = (i: number, patch: Partial<DoubletForm>) => setForm((f) => ({ ...f, doublets: f.doublets.map((d, j) => (j === i ? { ...d, ...patch } : d)) }));
  const addDoublet = () => setForm((f) => (f.doublets.length >= 3 ? f : { ...f, doublets: [...f.doublets, newDoublet(f)] }));
  const removeDoublet = (i: number) => setForm((f) => (f.doublets.length <= 1 ? f : { ...f, doublets: f.doublets.filter((_, j) => j !== i) }));
  const run = async () => {
    if (running || invalid || !lines.length) return;
    setState({ kind: "running" });
    const res = await wb.addDesign(design.id, changes, form.name.trim() || undefined);
    if (!res.ok) {
      setState({ kind: "error", message: res.offline ? "The agent server isn't answering; nothing was run." : res.message });
      return;
    }
    setState({ kind: "idle" });
    setForm(editForm(design));
    wb.select(res.data.design.id);
  };

  const field = (id: string, label: string, unit: string, value: string, onChange: (v: string) => void, opts: { placeholder?: string; hint?: ReactNode; error?: string; changed?: boolean } = {}) => (
    <div className={`dz-field${opts.changed ? " changed" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <span className="dz-input-unit">
        <input
          id={id}
          type="text"
          inputMode="decimal"
          value={value}
          placeholder={opts.placeholder}
          aria-invalid={!!opts.error}
          aria-describedby={opts.error ? `${id}-err` : opts.hint ? `${id}-hint` : undefined}
          onChange={(e) => onChange(e.target.value)}
          disabled={running}
        />
        <span aria-hidden="true">{unit}</span>
      </span>
      {opts.error ? (
        <span id={`${id}-err`} className="dz-field-err">
          {opts.error}
        </span>
      ) : (
        opts.hint && (
          <span id={`${id}-hint`} className="dz-field-hint">
            {opts.hint}
          </span>
        )
      )}
    </div>
  );
  const num = (k: EditKey, label: string, unit: string, opts: { placeholder?: string; hint?: string } = {}) =>
    field(`${uid}-${k}`, label, unit, form[k], (v) => set(k, v), { ...opts, error: errors[k], changed: k in changes });

  // The base's doublet at the same place, to mark what changed.
  const was = (i: number) => (base.doublets[i] ? doubletForm(base.doublets[i], base.doublets, i) : null);

  return (
    <form
      className="dz-edit"
      aria-label={`Edit ${design.code}`}
      onSubmit={(e) => {
        e.preventDefault();
        void run();
      }}
    >
      <p className="dz-edit-lead">
        Change {design.code} and run it as a new design: GEMINI's wells, the year, the costs and the challenge's checks run again on the server. {design.code} stays as it is.
      </p>

      {hasWells && (
        <fieldset disabled={running} className="dz-doublets-edit">
          <legend>Doublets</legend>
          {form.doublets.map((d, i) => {
            const before = was(i);
            const err = errors.doublets?.[i] ?? {};
            return (
              <section key={i} className={`dz-dcard${before ? "" : " is-new"}`} aria-label={`Doublet ${i + 1}`}>
                <header className="dz-dcard-head">
                  <span className="dz-dcard-name">Doublet {i + 1}</span>
                  {!before && <span className="tag tag-teal">new</span>}
                  {form.doublets.length > 1 && (
                    <button type="button" className="link-btn dz-link-danger" onClick={() => removeDoublet(i)} aria-label={`Remove doublet ${i + 1}`}>
                      Remove
                    </button>
                  )}
                </header>
                <div className="dz-field-grid two">
                  {field(`${uid}-d${i}-depth`, "Aquifer depth", "m", d.depth_m, (v) => setDoublet(i, { depth_m: v }), {
                    hint: "Its middle; 500 to 7,000 m",
                    error: err.depth_m,
                    changed: !!before && before.depth_m !== d.depth_m,
                  })}
                  {field(`${uid}-d${i}-cap`, "Flow cap", "m³/h", d.max_flow_m3h, (v) => setDoublet(i, { max_flow_m3h: v }), {
                    placeholder: String(FLOW_CAP),
                    hint: "50 to 300; empty: 300",
                    error: err.max_flow_m3h,
                    changed: !!before && before.max_flow_m3h !== d.max_flow_m3h,
                  })}
                </div>
                <div className="dz-field-grid two">
                  {field(`${uid}-d${i}-min`, "Runs at least", "m³/h", d.min_flow_m3h ?? "", (v) => setDoublet(i, { min_flow_m3h: v }), {
                    placeholder: String(FLOW_MIN),
                    hint: "When it runs; the cap too: one fixed rate",
                    error: err.min_flow_m3h,
                    changed: !!before && (before.min_flow_m3h ?? "") !== (d.min_flow_m3h ?? ""),
                  })}
                  <span className="dz-rate" aria-live="polite">
                    {rateWords(d)}
                  </span>
                </div>
                <Choice label="Producer open" value={d.producer_open} options={OPENINGS} onChange={(v) => setDoublet(i, { producer_open: v })} changed={!!before && before.producer_open !== d.producer_open} disabled={running} />
                <Choice
                  label="Injectors"
                  value={d.injectors}
                  options={[
                    { id: 1, text: "1", title: "One injector takes the doublet's brine back" },
                    { id: 2, text: "2", title: "Two injectors, half the brine each: less injection pressure, one more well to drill" },
                  ]}
                  onChange={(v) => setDoublet(i, { injectors: v })}
                  changed={!!before && before.injectors !== d.injectors}
                  disabled={running}
                />
                <Choice label={d.injectors === 2 ? "Injectors open" : "Injector open"} value={d.injector_open} options={OPENINGS} onChange={(v) => setDoublet(i, { injector_open: v })} changed={!!before && before.injector_open !== d.injector_open} disabled={running} />
                {form.doublets.length > 1 && (
                  <label className={`dz-toggle compact${before && before.own_train !== d.own_train ? " changed" : ""}`}>
                    <input type="checkbox" role="switch" checked={d.own_train} onChange={(e) => setDoublet(i, { own_train: e.target.checked })} />
                    <span className="dz-switch" aria-hidden="true" />
                    <span className="dz-toggle-text">
                      <span>Its own treatment train</span>
                      <span>separator and filters; else it shares one</span>
                    </span>
                  </label>
                )}
              </section>
            );
          })}
          {errors.count && <span className="dz-field-err">{errors.count}</span>}
          <div className="dz-doublets-foot">
            <button type="button" className="btn btn-soft ta-btn ta-soft dz-btn-sm" onClick={addDoublet} disabled={form.doublets.length >= 3}>
              + Add a doublet
            </button>
            <span className="dz-field-hint">1 to 3 doublets</span>
          </div>
          {form.doublets.length > 1 && (
            <Choice<Dispatch>
              label="Share the brine"
              value={form.dispatch}
              options={[
                { id: "equal", text: "Equal shares", title: "Every running doublet gives the same flow: the least pumping" },
                { id: "base", text: "Hottest first", title: "The hottest doublet runs first, up to its cap; the others take the rest: the warmest brine" },
              ]}
              onChange={(v) => set("dispatch", v)}
              changed={form.dispatch !== base.dispatch}
              disabled={running}
            />
          )}
          {num("reservoir_delta_c", "Reservoir change", "°C", { hint: "Below 0: a colder reservoir" })}
        </fieldset>
      )}

      <fieldset disabled={running}>
        <legend>Units (0 MW: not built)</legend>
        <div className="dz-field-grid two">
          {num("heat_pump_mw", "Heat pump", "MW", { hint: "Tops up to 100 °C on the brine" })}
          {num("boiler_mw", "Gas boiler", "MW", { hint: "Burns the produced gas first" })}
          {num("absorption_mw", "Absorption chiller", "MW", { hint: "Driven by the brine" })}
          {num("chiller_mw", "Electric chillers", "MW", { hint: "The rest of the cold" })}
        </div>
        {eboilerMw > 0 && (
          <p className="dz-field-hint dz-edit-foot">
            The electric boiler ({fmtValue(eboilerMw)} MW) and {gasMode === "sell" ? "the gas sold to the grid" : "burning only the brine's own gas"} stay as they are: they can't be changed here yet.
          </p>
        )}
      </fieldset>

      <fieldset disabled={running}>
        <legend>Network returns (supplies fixed at 100 °C and 20 °C)</legend>
        <div className="dz-field-grid two">
          {num("return_c", "Heating return", "°C", { hint: "Not given by the organisers" })}
          {num("cool_return_c", "Cooling return", "°C", { hint: "Not given by the organisers" })}
        </div>
      </fieldset>

      <div className="dz-field">
        <label htmlFor={`${uid}-name`}>Name of the new design</label>
        <input id={`${uid}-name`} type="text" value={form.name} onChange={(e) => set("name", e.target.value)} disabled={running} maxLength={80} />
      </div>

      <div className="dz-edit-summary" aria-live="polite">
        {lines.length ? (
          <>
            <span className="dz-insp-cap">
              {lines.length} change{lines.length === 1 ? "" : "s"} from {design.code}
            </span>
            <ul>
              {lines.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </>
        ) : (
          <span className="dz-muted">No changes yet: edit a value.</span>
        )}
      </div>

      {state.kind === "error" && (
        <p role="alert" className="dz-error">
          <strong>The design didn't run.</strong> {state.message}
        </p>
      )}

      <div className="dz-edit-actions">
        <button type="submit" className="btn btn-ink ta-btn ta-ink" disabled={running || invalid || !lines.length}>
          {running && <Spinner size={16} light />}
          {running ? "Running…" : "Run as new design"}
        </button>
        <button
          type="button"
          className="btn btn-soft ta-btn ta-soft"
          disabled={running || (!lines.length && form.name === editForm(design).name)}
          onClick={() => {
            setForm(editForm(design));
            setState({ kind: "idle" });
          }}
        >
          Reset
        </button>
      </div>
      <p className="dz-field-hint dz-edit-foot">The dispatch: {DISPATCH_WORDS[base.dispatch]} now.</p>
    </form>
  );
}
