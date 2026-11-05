// The GEMINI project view's inspector: the component picked (its parameters, boundary inputs,
// a way to connect it without dragging, and, after a run, every output against the released
// GEMINI), or the connection picked.

import { useEffect, useId, useState } from "react";

import type { CatalogueType, GeminiProject, GeminiRun } from "../../workbench";
import {
  compareOutput,
  componentMeta,
  componentPorts,
  componentRole,
  connect,
  impossibleOutput,
  projectEdges,
  readOutput,
  removeBoundary,
  removeComponents,
  removePairs,
  renameComponent,
  setBoundary,
  setParameter,
} from "./project";
import type { Selection } from "./ProjectCanvas";

interface Props {
  project: GeminiProject;
  selection: Selection;
  types: Map<string, CatalogueType>;
  run: GeminiRun | null;
  stale: boolean;
  compare: boolean;
  onChange: (p: GeminiProject) => void;
  onSelection: (s: Selection) => void;
}

// ------------------------------------------------------------------ one parameter

function ParamField({ name, k, value, unit, onCommit }: { name: string; k: string; value: unknown; unit?: string; onCommit: (v: unknown) => void }) {
  const id = useId();
  const kind = typeof value === "number" ? "number" : typeof value === "boolean" ? "boolean" : typeof value === "string" ? "string" : "json";
  const show = (v: unknown) => (kind === "json" ? JSON.stringify(v, null, 2) : String(v ?? ""));
  const [text, setText] = useState(show(value));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setText(show(value));
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const commit = () => {
    if (kind === "number") {
      const v = Number(text.trim().replace("−", "-"));
      if (!text.trim() || !Number.isFinite(v)) return setError("A number, please.");
      setError(null);
      if (v !== value) onCommit(v);
    } else if (kind === "string") {
      if (text !== value) onCommit(text);
    } else if (kind === "json") {
      try {
        const v = JSON.parse(text);
        setError(null);
        if (JSON.stringify(v) !== JSON.stringify(value)) onCommit(v);
      } catch (err) {
        setError(`Not valid JSON: ${(err as Error).message}`);
      }
    }
  };

  if (kind === "boolean")
    return (
      <label className="dz-param check">
        <input type="checkbox" checked={value as boolean} onChange={(e) => onCommit(e.target.checked)} />
        <span>{k}</span>
      </label>
    );
  return (
    <div className={`dz-param${kind === "json" ? " json" : ""}`}>
      <label htmlFor={id}>
        {k}
        {unit && <span className="dz-muted"> {unit}</span>}
      </label>
      {kind === "json" ? (
        <textarea
          id={id}
          value={text}
          spellCheck={false}
          rows={Math.min(10, text.split("\n").length)}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-err` : undefined}
          onChange={(e) => {
            setText(e.target.value);
            setError(null);
          }}
          onBlur={commit}
        />
      ) : (
        <input
          id={id}
          type="text"
          inputMode={kind === "number" ? "decimal" : undefined}
          value={text}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-err` : undefined}
          onChange={(e) => setText(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        />
      )}
      {error && (
        <span id={`${id}-err`} className="dz-field-err">
          {error}
        </span>
      )}
      <span className="sr-only">{`${name} parameter`}</span>
    </div>
  );
}

// ------------------------------------------------------------------ inspector

export function ComponentInspector({ project, selection, types, run, stale, compare, onChange, onSelection }: Props) {
  const uid = useId();
  const [rename, setRename] = useState<string | null>(null);
  const [link, setLink] = useState({ out: "", target: "", input: "" });
  const [bKey, setBKey] = useState("");

  if (selection?.kind === "edge") {
    const e = projectEdges(project).find((x) => x.id === selection.id);
    if (!e) return <p className="dz-muted">Pick a component or a connection on the canvas.</p>;
    return (
      <div className="dz-ci">
        <div className="dz-ci-head">
          <h2>Connection</h2>
          <span className="dz-muted">
            number {e.connection + 1} of {project.connections.length} in GEMINI's wiring order
          </span>
        </div>
        <p className="dz-wire-desc">
          <code>{e.source}</code>.<code>{e.out}</code>
          <span aria-hidden="true"> → </span>
          <span className="sr-only"> to </span>
          <code>{e.target}</code>.<code>{e.in}</code>
        </p>
        <button
          type="button"
          className="btn btn-soft ta-btn ta-soft dz-btn-sm dz-danger"
          onClick={() => {
            onChange(removePairs(project, [e]));
            onSelection(null);
          }}
        >
          Delete this connection
        </button>
      </div>
    );
  }

  const name = selection?.kind === "node" ? selection.id : null;
  const comp = name ? project.components[name] : null;
  if (!name || !comp) return <ProjectOverview project={project} types={types} onSelection={onSelection} />;

  const t = types.get(comp.type);
  const ports = componentPorts(project, name, t);
  const params = Object.entries(comp.parameters ?? {}).filter(([k]) => !k.startsWith("_"));
  const unset = (t?.parameters ?? []).filter((p) => !(comp.parameters && p.key in comp.parameters));
  const bounds = project.boundary_inputs.filter((b) => b.component === name);
  const free = ports.inputs.filter((p) => !p.connected && p.boundary == null).map((p) => p.key);
  const fixed = run?.outputs[name];
  const released = compare ? run?.released?.outputs[name] : undefined;
  const others = Object.keys(project.components).filter((n) => n !== name);
  const targetPorts = link.target ? componentPorts(project, link.target, types.get(project.components[link.target]?.type ?? "")).inputs : [];
  const own = typeof comp._description === "string" ? comp._description : null;
  const role = componentRole(project, name);
  const meta = componentMeta(comp.type);

  return (
    <div className="dz-ci">
      <div className="dz-ci-head">
        {rename != null ? (
          <form
            className="dz-rename"
            onSubmit={(e) => {
              e.preventDefault();
              const next = renameComponent(project, name, rename);
              if (next !== project) {
                onChange(next);
                onSelection({ kind: "node", id: rename.trim() });
              }
              setRename(null);
            }}
          >
            <label htmlFor={`${uid}-name`} className="sr-only">
              New name
            </label>
            <input id={`${uid}-name`} value={rename} onChange={(e) => setRename(e.target.value)} autoFocus pattern="[\w\-]+" title="Letters, digits, _ and -" />
            <button type="submit" className="link-btn">
              Save
            </button>
            <button type="button" className="link-btn" onClick={() => setRename(null)}>
              Cancel
            </button>
          </form>
        ) : (
          <h2>
            {name}{" "}
            <button type="button" className="link-btn" onClick={() => setRename(name)} aria-label={`Rename ${name}`}>
              Rename
            </button>
          </h2>
        )}
        <span className="dz-muted dz-ci-kind">
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path d={meta.icon} fill="none" stroke={meta.color} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {t?.label ?? meta.label} · <code>{comp.type}</code>
          {role ? ` · ${role}` : ""}
        </span>
        {own && <p className="dz-ci-desc">{own}</p>}
        {t?.description && <p className={`dz-ci-desc${own ? " is-type" : ""}`}>{own ? `${t.label}: ${t.description}` : t.description}</p>}
      </div>

      {fixed && (
        <section className={`dz-ci-sec${stale ? " stale" : ""}`}>
          <h3>
            Outputs{stale ? " (before your last edit)" : ""}
            {released ? " · fixed against released" : ""}
          </h3>
          <div className="dz-table-wrap">
          <table className="dz-out-table">
            <thead>
              <tr>
                <th scope="col">Output</th>
                <th scope="col">Fixed</th>
                {released && <th scope="col">Released</th>}
                {released && <th scope="col">Δ</th>}
              </tr>
            </thead>
            <tbody>
              {Object.entries(fixed).map(([k, v]) => {
                const unit = ports.outputs.find((o) => o.key === k)?.unit;
                const f = readOutput(comp.type, k, v, unit);
                const r = released && k in released ? readOutput(comp.type, k, released[k], unit) : null;
                const cmp = released ? compareOutput(v, released[k]) : null;
                const bad = impossibleOutput(comp.type, k, v, unit);
                return (
                  <tr key={k} className={`${cmp?.big ? "big" : ""}${bad ? " bad" : ""}`}>
                    <th scope="row">{k}</th>
                    <td title={bad ?? undefined}>
                      {f.text} <span className="dz-muted">{f.unit}</span>
                      {bad && <span className="dz-out-bad"> not physical</span>}
                    </td>
                    {released && <td>{r ? (r.unit === f.unit ? r.text : `${r.text} ${r.unit}`) : "–"}</td>}
                    {released && <td>{cmp?.text ?? "–"}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </section>
      )}

      <section className="dz-ci-sec">
        <h3>Boundary inputs</h3>
        {bounds.length ? (
          <ul className="dz-blist">
            {bounds.map((b) => (
              <li key={b.key}>
                <ParamField name={name} k={b.key} value={b.value} unit={ports.inputs.find((p) => p.key === b.key)?.unit} onCommit={(v) => typeof v === "number" && onChange(setBoundary(project, name, b.key, v))} />
                <button type="button" className="dz-x" aria-label={`Remove the boundary input ${b.key}`} onClick={() => onChange(removeBoundary(project, name, b.key))}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="dz-muted">None: every input it reads comes from another component.</p>
        )}
        {free.length > 0 && (
          <form
            className="dz-inline-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!bKey) return;
              onChange(setBoundary(project, name, bKey, 0));
              setBKey("");
            }}
          >
            <label htmlFor={`${uid}-bkey`} className="sr-only">
              Input to fix
            </label>
            <select id={`${uid}-bkey`} value={bKey} onChange={(e) => setBKey(e.target.value)}>
              <option value="">Fix an input…</option>
              {free.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
            <button type="submit" className="btn btn-soft ta-btn ta-soft dz-btn-sm" disabled={!bKey}>
              Add
            </button>
          </form>
        )}
      </section>

      <section className="dz-ci-sec">
        <h3>Parameters</h3>
        {params.length ? (
          <div className="dz-params">
            {params.map(([k, v]) => (
              <ParamField key={k} name={name} k={k} value={v} unit={t?.parameters.find((p) => p.key === k)?.unit} onCommit={(nv) => onChange(setParameter(project, name, k, nv))} />
            ))}
          </div>
        ) : (
          <p className="dz-muted">None set: GEMINI uses its defaults.</p>
        )}
        {unset.length > 0 && (
          <details className="dz-unset">
            <summary>
              {unset.length} more in the catalogue, at GEMINI's defaults
            </summary>
            <ul>
              {unset.map((p) => (
                <li key={p.key}>
                  <code>{p.key}</code>
                  <button type="button" className="link-btn" disabled={p.default == null} onClick={() => onChange(setParameter(project, name, p.key, structuredClone(p.default)))}>
                    Set
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <section className="dz-ci-sec">
        <h3>Connect an output</h3>
        <form
          className="dz-connect"
          onSubmit={(e) => {
            e.preventDefault();
            if (!link.out || !link.target || !link.input) return;
            onChange(connect(project, name, link.out, link.target, link.input));
            setLink({ out: "", target: "", input: "" });
          }}
        >
          <label>
            <span>Output</span>
            <select value={link.out} onChange={(e) => setLink({ ...link, out: e.target.value })}>
              <option value="">Choose…</option>
              {ports.outputs.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.key}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>To</span>
            <select value={link.target} onChange={(e) => setLink({ ...link, target: e.target.value, input: "" })}>
              <option value="">Choose…</option>
              {others.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Input</span>
            <select value={link.input} onChange={(e) => setLink({ ...link, input: e.target.value })} disabled={!link.target}>
              <option value="">Choose…</option>
              {targetPorts.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.key}
                  {p.connected ? " (already fed)" : ""}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn btn-soft ta-btn ta-soft dz-btn-sm" disabled={!link.out || !link.target || !link.input}>
            Connect
          </button>
        </form>
        <p className="dz-field-hint">New connections go at the end: GEMINI wires them in order.</p>
      </section>

      <button
        type="button"
        className="btn btn-soft ta-btn ta-soft dz-btn-sm dz-danger"
        onClick={() => {
          onChange(removeComponents(project, [name]));
          onSelection(null);
        }}
      >
        Delete {name}
      </button>
    </div>
  );
}

// ------------------------------------------------------------------ nothing picked: the project

/** With nothing picked: the components (pick one) and the connections in GEMINI's wiring order. */
function ProjectOverview({ project, types, onSelection }: { project: GeminiProject; types: Map<string, CatalogueType>; onSelection: (s: Selection) => void }) {
  const edges = projectEdges(project);
  const names = Object.keys(project.components);
  return (
    <div className="dz-ci">
      {typeof project._description === "string" && <p className="dz-ci-desc">{project._description}</p>}
      <p className="dz-muted">
        Pick a component to edit its parameters and boundary inputs. Drag from an output (right) to an input (left) to connect two; select a component or a connection and press Delete to remove it.
      </p>
      <section className="dz-ci-sec">
        <h3>Components · {names.length}</h3>
        <ul className="dz-overview">
          {names.map((n) => {
            const bounds = project.boundary_inputs.filter((b) => b.component === n).length;
            return (
              <li key={n}>
                <button type="button" className="dz-ov-item" onClick={() => onSelection({ kind: "node", id: n })}>
                  <code>{n}</code>
                  <span className="dz-muted">
                    {types.get(project.components[n].type)?.label ?? componentMeta(project.components[n].type).label}
                    {componentRole(project, n) ? ` · ${componentRole(project, n)}` : ""}
                    {bounds ? ` · ${bounds} fixed input${bounds === 1 ? "" : "s"}` : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      <section className="dz-ci-sec">
        <h3>Wiring order · {project.connections.length}</h3>
        <ol className="dz-overview dz-wiring">
          {project.connections.map((c, i) => {
            const first = edges.find((e) => e.connection === i);
            const pairs = edges.filter((e) => e.connection === i).length;
            return (
              <li key={i}>
                <button type="button" className="dz-ov-item" disabled={!first} onClick={() => first && onSelection({ kind: "edge", id: first.id })}>
                  <span>
                    <code>{c.predecessor}</code> → <code>{c.successor}</code>
                  </span>
                  <span className="dz-muted">
                    {pairs} port{pairs === 1 ? "" : "s"}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
        <p className="dz-field-hint">GEMINI wires connections in this order; new ones go at the end.</p>
      </section>
    </div>
  );
}
