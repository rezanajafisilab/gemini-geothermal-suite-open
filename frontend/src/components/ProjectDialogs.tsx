// "New project": a district from a year of demand and the reservoir below it. Each file is read by
// the server as soon as it is picked (the reader the project itself will use), so its totals, a
// sparkline and any problem show before anything is made. And the dialog that removes a project.

import { useEffect, useId, useRef, useState, type DragEvent } from "react";

import { HttpError, createProject, previewProfile, type ProfilePreview, type ProjectInfo } from "../agent/client";
import type { Project } from "../state/projects";
import { Cross, FileGlyph, Spinner } from "./Icons";
import { Modal } from "./Modal";

type Kind = "heat" | "cool";
type Picked =
  | { file: File; state: "reading" }
  | { file: File; state: "ok"; preview: ProfilePreview; unit?: string }
  | { file: File; state: "error"; error: string };

interface Field {
  key: string;
  label: string;
  unit: string;
  placeholder: string;
  required?: boolean;
}

const RESERVOIR: Field[] = [
  { key: "depth_m", label: "Depth", unit: "m", placeholder: "e.g. 2500", required: true },
  { key: "temperature_c", label: "Temperature", unit: "°C", placeholder: "e.g. 87", required: true },
  { key: "permeability_md", label: "Permeability", unit: "mD", placeholder: "200" },
  { key: "thickness_m", label: "Net thickness", unit: "m", placeholder: "100" },
  { key: "pressure_bar", label: "Pressure", unit: "bar", placeholder: "hydrostatic" },
];

const NETWORKS: Field[] = [
  { key: "heat_supply_c", label: "Heating supply", unit: "°C", placeholder: "100" },
  { key: "heat_return_c", label: "Heating return", unit: "°C", placeholder: "60" },
  { key: "cool_supply_c", label: "Cooling supply", unit: "°C", placeholder: "20" },
  { key: "cool_return_c", label: "Cooling return", unit: "°C", placeholder: "25" },
];

// The requirements' reservoir (28 Oct), to start from.
const CHALLENGE_RESERVOIR: Record<string, string> = { depth_m: "2500", temperature_c: "87", permeability_md: "200", thickness_m: "100", pressure_bar: "250" };

const fmt = (v: number, d = 1) => v.toLocaleString("en-GB", { maximumFractionDigits: d });

/** A number as typed: blank is "not given", a decimal comma is a decimal point. */
export function parseNumber(text: string): number | null | undefined {
  const t = text.trim().replace(",", ".");
  if (!t) return undefined;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

export function Spark({ values, color, width = 96, height = 24 }: { values: number[]; color: string; width?: number; height?: number }) {
  if (values.length < 2) return null;
  const max = Math.max(...values) || 1;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * width).toFixed(1)},${(height - 1 - (v / max) * (height - 3)).toFixed(1)}`);
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} width={width} height={height} preserveAspectRatio="none" aria-hidden="true">
      <path d={`M0,${height} L${pts.join(" L")} L${width},${height} Z`} fill={color} opacity={0.13} />
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** A file whose unit the server had to ask about, and the user has not picked yet. */
const unitAsked = (p: Picked | null) => p?.state === "ok" && !!p.preview.unit_question && !p.unit;

function ProfileDrop({ kind, picked, onPick, onClear, onUnit, fallback }: { kind: Kind; picked: Picked | null; onPick: (f: File) => void; onClear: () => void; onUnit: (unit: string) => void; fallback?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const id = useId();
  const title = kind === "heat" ? "Heating demand" : "Cooling demand";
  const color = kind === "heat" ? "var(--heat)" : "var(--cold)";
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onPick(file);
  };
  return (
    <div
      className={`np-drop${over ? " over" : ""}${picked?.state === "error" ? " bad" : ""}${picked?.state === "ok" ? " ok" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
    >
      <input
        ref={input}
        id={id}
        type="file"
        accept=".csv,.txt,.tsv,text/csv"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPick(file);
          e.target.value = "";
        }}
      />
      <div className="np-drop-head">
        <span className="np-drop-title">
          <i className="np-swatch" style={{ background: color }} aria-hidden="true" />
          <span>
            {title}
            {kind === "heat" && (
              <span className="req" aria-hidden="true">
                *
              </span>
            )}
          </span>
          {kind === "cool" && <span className="np-optional">optional</span>}
        </span>
        {picked && (
          <button type="button" className="np-clear ta-btn ta-soft" aria-label={`Remove ${picked.file.name}`} title="Remove" onClick={onClear}>
            <Cross size={9} />
          </button>
        )}
      </div>
      {!picked && (
        <label htmlFor={id} className="np-drop-empty">
          <span className="np-drop-cta">Drop a CSV here or choose a file</span>
          <span className="note">{fallback ?? "365 daily or 8,760 hourly values; MW, kW, MWh or kWh from the header"}</span>
        </label>
      )}
      {picked && (
        <div className="np-drop-file">
          <span className="np-file-name">
            {picked.state === "reading" ? <Spinner size={13} /> : <FileGlyph name={picked.file.name} size={13} />}
            <span>{picked.file.name}</span>
          </span>
          {picked.state === "ok" && (
            <>
              <Spark values={picked.preview.weekly_mw} color={color} width={300} height={44} />
              <span className="np-file-sum">
                <b>{fmt(picked.preview.annual_gwh)} GWh</b> a year · peak <b>{fmt(picked.preview.peak_mw)} MW</b> · column <code>{picked.preview.column}</code>
              </span>
              {picked.preview.notes.map((n) => (
                <span key={n} className="note np-file-note">
                  {n}
                </span>
              ))}
              {unitAsked(picked) && (
                <span className="np-unit-ask" role="group" aria-label="Which unit is it?">
                  <span className="err">{picked.preview.unit_question!.text}</span>
                  <span className="np-unit-opts">
                    {picked.preview.unit_question!.options.map((u) => (
                      <button key={u} type="button" className="ta-btn ta-chip" onClick={() => onUnit(u)}>
                        {u}
                      </button>
                    ))}
                  </span>
                </span>
              )}
            </>
          )}
          {picked.state === "error" && (
            <span className="err" role="alert">
              {picked.error}
            </span>
          )}
          {picked.state !== "reading" && (
            <label htmlFor={id} className="link-btn np-change">
              Choose another file
            </label>
          )}
        </div>
      )}
    </div>
  );
}

function NumberField({ field, value, onChange, invalid }: { field: Field; value: string; onChange: (v: string) => void; invalid: boolean }) {
  const id = useId();
  return (
    <label className="np-field" htmlFor={id}>
      <span className="np-label">
        {field.label}
        {field.required && (
          <span className="req" aria-hidden="true">
            *
          </span>
        )}
      </span>
      <span className={`input-box np-input${invalid ? " invalid" : ""}`}>
        <input id={id} type="text" inputMode="decimal" aria-required={field.required} aria-invalid={invalid} value={value} placeholder={field.placeholder} onChange={(e) => onChange(e.target.value)} />
        <span className="np-unit">{field.unit}</span>
      </span>
    </label>
  );
}

export function NewProjectDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (info: ProjectInfo) => void }) {
  const [name, setName] = useState("");
  const [heat, setHeat] = useState<Picked | null>(null);
  const [cool, setCool] = useState<Picked | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reads = useRef(new Map<Kind, AbortController>());
  useEffect(() => {
    const current = reads.current;
    return () => current.forEach((c) => c.abort());
  }, []);

  const pick = (kind: Kind) => (file: File, unit?: string) => {
    const set = kind === "heat" ? setHeat : setCool;
    reads.current.get(kind)?.abort();
    const ctrl = new AbortController();
    reads.current.set(kind, ctrl);
    set({ file, state: "reading" });
    setError(null);
    previewProfile(file, kind, ctrl.signal, unit).then(
      (preview) => !ctrl.signal.aborted && set({ file, state: "ok", preview, unit }),
      (err) => !ctrl.signal.aborted && set({ file, state: "error", error: err instanceof HttpError ? err.message : "The file couldn't be read." }),
    );
  };
  // The unit picked for a file the server asked about: read again in it.
  const unitFor = (kind: Kind) => (unit: string) => {
    const p = kind === "heat" ? heat : cool;
    if (p) pick(kind)(p.file, unit);
  };
  const clear = (kind: Kind) => () => {
    reads.current.get(kind)?.abort();
    (kind === "heat" ? setHeat : setCool)(null);
  };

  const parsed = Object.fromEntries([...RESERVOIR, ...NETWORKS].map((f) => [f.key, parseNumber(values[f.key] ?? "")]));
  const invalid = (f: Field) => parsed[f.key] === null;
  const missing = [
    !name.trim() && "a name",
    heat?.state !== "ok" && "a heating demand file",
    parsed.depth_m == null && "the reservoir's depth",
    parsed.temperature_c == null && "its temperature",
  ].filter(Boolean) as string[];
  const bad = [...RESERVOIR, ...NETWORKS].filter(invalid).map((f) => f.label.toLowerCase());
  if (unitAsked(heat) || unitAsked(cool)) missing.push("the unit of the demand file");
  const ready = !missing.length && !bad.length && cool?.state !== "reading" && cool?.state !== "error" && !busy;
  const coolNote =
    heat?.state === "ok" && heat.preview.cool_column
      ? "Left empty: the cooling column of the heating file is used."
      : "Left empty: the district gets no cooling.";

  const submit = async () => {
    if (!ready || heat?.state !== "ok") return;
    const form = new FormData();
    form.append("name", name.trim());
    form.append("heat", heat.file, heat.file.name);
    if (cool?.state === "ok") form.append("cool", cool.file, cool.file.name);
    if (heat.unit) form.append("heat_unit", heat.unit);
    if (cool?.state === "ok" && cool.unit) form.append("cool_unit", cool.unit);
    for (const [k, v] of Object.entries(parsed)) if (typeof v === "number") form.append(k, String(v));
    setBusy(true);
    setError(null);
    try {
      onCreated(await createProject(form));
    } catch (err) {
      setError(err instanceof HttpError ? err.message : "The project couldn't be made.");
      setBusy(false);
    }
  };

  return (
    <Modal label="New project" onClose={onClose} className="modal-project">
      <form
        className="np"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <header className="np-head">
          <h2>New project</h2>
          <p className="note">
            A district: a year of daily heat and cold demand and the reservoir below it. The challenge's caps hold for every project (1–3 doublets, 50–300 m³/h, brine cooled by at most 40 K, 330 days).
          </p>
        </header>
        <label className="np-field np-name">
          <span className="np-label">
            Name
            <span className="req" aria-hidden="true">
              *
            </span>
          </span>
          <span className="input-box">
            <input type="text" value={name} maxLength={80} placeholder="e.g. Riccarton campus" aria-required="true" onChange={(e) => setName(e.target.value)} />
          </span>
        </label>
        <div className="np-cols">
          <section className="np-col" aria-label="Demand">
            <h3>Demand</h3>
            <ProfileDrop kind="heat" picked={heat} onPick={pick("heat")} onClear={clear("heat")} onUnit={unitFor("heat")} />
            <ProfileDrop kind="cool" picked={cool} onPick={pick("cool")} onClear={clear("cool")} onUnit={unitFor("cool")} fallback={coolNote} />
          </section>
          <section className="np-col" aria-label="Reservoir and networks">
            <div className="np-h3-row">
              <h3>Reservoir</h3>
              <button type="button" className="link-btn" onClick={() => setValues((v) => ({ ...v, ...CHALLENGE_RESERVOIR }))}>
                Use the challenge's
              </button>
            </div>
            <div className="np-grid">
              {RESERVOIR.map((f) => (
                <NumberField key={f.key} field={f} value={values[f.key] ?? ""} invalid={invalid(f)} onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))} />
              ))}
            </div>
            <h3>Networks</h3>
            <div className="np-grid">
              {NETWORKS.map((f) => (
                <NumberField key={f.key} field={f} value={values[f.key] ?? ""} invalid={invalid(f)} onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))} />
              ))}
            </div>
            <p className="note np-defaults">Blank fields take the value shown. Returns are assumptions the Sensitivity tab can vary.</p>
          </section>
        </div>
        <footer className="np-foot">
          <span className={error ? "err" : "note"} role={error ? "alert" : undefined}>
            {error ?? (bad.length ? `Not a number: ${bad.join(", ")}.` : missing.length ? `Still needed: ${missing.join(", ")}.` : "Ready. The agent will design on this district's data.")}
          </span>
          <span className="np-actions">
            <button type="button" className="btn btn-soft ta-btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-ink ta-btn" disabled={!ready}>
              {busy && <Spinner size={14} light />}
              Create project
            </button>
          </span>
        </footer>
      </form>
    </Modal>
  );
}

export function RemoveProjectDialog({ project, chats, onClose, onRemoved }: { project: Project; chats: number; onClose: () => void; onRemoved: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal label={`Remove ${project.name}`} onClose={onClose} className="modal-confirm">
      <h2 className="confirm-title">Remove “{project.name}”?</h2>
      <p className="note">
        {chats === 0 ? "Its files go from the server." : `Its files and its ${chats === 1 ? "chat go" : `${chats} chats go`}, with their designs, runs and uploaded files.`} This can't be undone. The
        challenge district stays.
      </p>
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      <div className="np-actions" style={{ justifyContent: "flex-end", marginTop: 14 }}>
        <button type="button" className="btn btn-soft ta-btn" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-ink btn-danger ta-btn"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onRemoved();
            } catch (err) {
              setError(err instanceof HttpError ? err.message : "The project couldn't be removed.");
              setBusy(false);
            }
          }}
        >
          {busy && <Spinner size={14} light />}
          Remove project
        </button>
      </div>
    </Modal>
  );
}
