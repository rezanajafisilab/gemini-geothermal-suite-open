// The GEMINI project view: the project GEMINI's solver ran for this design, as an editable graph.
// Add components from the catalogue (click or drag), connect ports, edit parameters and boundary
// inputs, then run it on GEMINI with the team's fixes, optionally against GEMINI as released (the
// bugs' impact, e.g. the injector's wellhead pressure). Reset, export and import the JSON.

import { useCallback, useId, useMemo, useRef, useState, type CSSProperties } from "react";
import type { FitViewOptions } from "@xyflow/react";

import { Download, Spinner } from "../../components/Icons";
import { EmptyState, getCatalogue, runGemini, useResource, type CatalogueType, type Design, type GeminiProject, type GeminiRun } from "../../workbench";
import { ComponentInspector } from "./ComponentInspector";
import { FoldButton, FullBar, FullButton, narrowWindow, useFill, useFullScreen, useSize } from "./fullscreen";
import { DRAG_TYPE, ProjectCanvas, type Selection } from "./ProjectCanvas";
import { useRemembered } from "./remember";
import { addComponent, compareOutput, connect, keyOutputs, parseProject, projectKey, readOutput, removeComponents, removePairs, setBoundary } from "./project";

const GROUPS: { key: CatalogueType["group"]; label: string }[] = [
  { key: "wells", label: "Wells" },
  { key: "surface", label: "Surface" },
  { key: "heat", label: "Heat" },
  { key: "flow", label: "Flow" },
];

interface RunState {
  result: GeminiRun;
  key: string;
  compared: boolean;
}

// ------------------------------------------------------------------ palette

function Palette({ types, status, onAdd }: { types: CatalogueType[]; status: "loading" | "ready" | "error"; onAdd: (t: CatalogueType) => void }) {
  if (status === "loading") return <p className="dz-muted dz-palette-note">Loading GEMINI's components…</p>;
  if (!types.length) return <p className="dz-muted dz-palette-note">GEMINI's catalogue isn't available, so components can't be added; the project can still be edited and run.</p>;
  return (
    <nav className="dz-palette" aria-label="GEMINI components: click to add, or drag onto the canvas">
      {GROUPS.map((g) => {
        const items = types.filter((t) => t.group === g.key);
        if (!items.length) return null;
        return (
          <div key={g.key} className="dz-palette-group">
            <span className="dz-insp-cap">{g.label}</span>
            <ul>
              {items.map((t) => (
                <li key={t.type}>
                  <button
                    type="button"
                    className="dz-pal-item ta-btn ta-chip"
                    draggable
                    title={t.description || t.type}
                    aria-label={`Add a ${t.label}`}
                    onDragStart={(e) => {
                      e.dataTransfer.setData(DRAG_TYPE, t.type);
                      e.dataTransfer.effectAllowed = "copy";
                    }}
                    onClick={() => onAdd(t)}
                  >
                    <span className="dz-pal-plus" aria-hidden="true">
                      +
                    </span>
                    {t.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

// ------------------------------------------------------------------ run summary

function biggest(run: GeminiRun, project: GeminiProject, types: Map<string, CatalogueType>, n = 3) {
  if (!run.released) return [];
  const rows: { name: string; key: string; fixed: string; released: string; text: string; abs: number }[] = [];
  for (const [name, out] of Object.entries(run.outputs)) {
    const rel = run.released.outputs[name];
    const type = project.components[name]?.type ?? "";
    if (!rel) continue;
    for (const key of keyOutputs(type, out, 6)) {
      const cmp = compareOutput(out[key], rel[key]);
      if (!cmp?.big) continue;
      const unit = types.get(type)?.outputs.find((o) => o.key === key)?.unit;
      const f = readOutput(type, key, out[key], unit);
      const r = readOutput(type, key, rel[key], unit);
      rows.push({ name, key, fixed: `${f.text} ${f.unit}`, released: `${r.text} ${r.unit}`, text: cmp.text, abs: cmp.pct == null ? 1e5 : Math.abs(cmp.pct) });
    }
  }
  return rows.sort((a, b) => b.abs - a.abs).slice(0, n);
}

// ------------------------------------------------------------------ view

export function ProjectView({ design, scope }: { design: Design; scope: string }) {
  const base = design.graph.gemini_project;
  if (!base)
    return (
      <EmptyState
        title={`${design.code} has no GEMINI project`}
        hint={
          design.plant.depth_m === 0
            ? "It has no well (the gas reference), so GEMINI's solver has nothing to run. Pick a geothermal design."
            : "The server sent no GEMINI project for it: run the design again from the chat."
        }
      />
    );
  return <ProjectEditor design={design} base={base} scope={scope} />;
}

function ProjectEditor({ design, base, scope }: { design: Design; base: GeminiProject; scope: string }) {
  const uid = useId();
  const baseKey = useMemo(() => projectKey(base), [base]);
  const [saved, setSaved] = useRemembered<{ base: string; project: GeminiProject }>(scope, "project", () => ({ base: baseKey, project: structuredClone(base) }));
  // The design was recomputed since (same id, new project): start again from the new one.
  const project = saved.base === baseKey ? saved.project : base;
  const setProject = useCallback((p: GeminiProject) => setSaved({ base: baseKey, project: p }), [setSaved, baseKey]);
  const [positions, setPositions] = useRemembered<Record<string, { x: number; y: number }>>(scope, "project-positions", {});
  const [selection, setSelection] = useRemembered<Selection>(scope, "project-selection", null);
  const [compare, setCompare] = useRemembered(scope, "compare", true);
  const [allPorts, setAllPorts] = useRemembered("*", "all-ports", false);
  const [run, setRun] = useRemembered<RunState | null>(scope, "run", null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [paste, setPaste] = useState<{ open: boolean; text: string; error: string | null }>({ open: false, text: "", error: null });
  const [canvasKey, setCanvasKey] = useState(0);
  const file = useRef<HTMLInputElement>(null);
  const centre = useRef<(() => { x: number; y: number }) | null>(null);
  const added = useRef(0);
  const { full } = useFullScreen();
  const [stageRef, fill] = useFill<HTMLDivElement>(440);
  const [canvasRef, size] = useSize<HTMLDivElement>();
  const [barRef, bar] = useSize<HTMLDivElement>();
  const narrow = size.w > 0 && size.w < 600;
  const [barOpen, setBarOpen] = useRemembered("*", "full-bar", true);
  const [paletteOpen, setPaletteOpen] = useRemembered("*", "full-palette", () => !narrowWindow());
  const [sideOpen, setSideOpen] = useRemembered("*", "full-gside", () => !narrowWindow());

  const catalogue = useResource((signal) => getCatalogue(signal), []);
  const types = useMemo(() => new Map((catalogue.data?.types ?? []).map((t) => [t.type, t])), [catalogue.data]);
  const edited = projectKey(project) !== baseKey;
  const stale = !!run && run.key !== projectKey(project);
  const result = run?.result ?? null;

  const change = useCallback((p: GeminiProject) => setProject(p), [setProject]);
  const add = (t: CatalogueType, at?: { x: number; y: number }) => {
    const { project: next, name } = addComponent(project, t);
    const c = at ?? centre.current?.() ?? { x: 0, y: 0 };
    const nudge = at ? 0 : (added.current++ % 5) * 24;
    setPositions((p) => ({ ...p, [name]: { x: c.x + nudge, y: c.y + nudge } }));
    setProject(next);
    setSelection({ kind: "node", id: name });
  };
  const onBoundary = useCallback((component: string, key: string, value: number) => setProject(setBoundary(project, component, key, value)), [project, setProject]);

  const doRun = async () => {
    setRunning(true);
    setError(null);
    const key = projectKey(project);
    const res = await runGemini({ project, compare_released: compare });
    setRunning(false);
    if (!res.ok) {
      setError(res.offline ? "The agent server isn't answering; nothing was run." : res.message);
      return;
    }
    setRun({ result: res.data, key, compared: compare });
  };

  const load = (text: string): string | null => {
    const r = parseProject(text);
    if ("error" in r) return r.error;
    setProject(r.project);
    setPositions({});
    setSelection(null);
    setRun(null);
    setCanvasKey((k) => k + 1);
    return null;
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(project, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${design.code.replace(/[^\w-]+/g, "_")}-gemini-project${edited ? "-edited" : ""}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const n = Object.keys(project.components).length;
  const top = result && result.ok && result.released?.ok ? biggest(result, project, types) : [];

  const runControls = (
    <>
      <button type="button" className="btn btn-ink ta-btn ta-ink" onClick={() => void doRun()} disabled={running || n === 0}>
        {running && <Spinner size={16} light />}
        {running ? "Running…" : "Run with GEMINI"}
      </button>
      <label className="dz-toggle compact">
        <input type="checkbox" role="switch" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
        <span className="dz-switch" aria-hidden="true" />
        <span className="dz-toggle-text">
          <span>Compare with GEMINI as released</span>
        </span>
      </label>
    </>
  );

  const fileControls = (
    <div className="dz-gem-file">
      {edited && <span className="tag tag-amber">edited</span>}
      <span className="dz-muted">
        {n} component{n === 1 ? "" : "s"} · {project.connections.length} connection{project.connections.length === 1 ? "" : "s"}
      </span>
      <label className="dz-toggle compact" title="Every port of every component, not only those in use">
        <input type="checkbox" role="switch" checked={allPorts} onChange={(e) => setAllPorts(e.target.checked)} />
        <span className="dz-switch" aria-hidden="true" />
        <span className="dz-toggle-text">
          <span>Every port</span>
        </span>
      </label>
      {confirmReset ? (
        <span className="dz-diff-confirm">
          <span>Discard your edits?</span>
          <button
            type="button"
            className="btn btn-soft ta-btn ta-soft dz-btn-sm dz-danger"
            onClick={() => {
              setProject(structuredClone(base));
              setPositions({});
              setSelection(null);
              setRun(null);
              setConfirmReset(false);
              setCanvasKey((k) => k + 1);
            }}
          >
            Reset
          </button>
          <button type="button" className="btn btn-soft ta-btn ta-soft dz-btn-sm" onClick={() => setConfirmReset(false)}>
            Keep
          </button>
        </span>
      ) : (
        <button type="button" className="btn btn-soft ta-btn ta-soft dz-btn-sm" disabled={!edited} onClick={() => setConfirmReset(true)}>
          Reset to {design.code}'s
        </button>
      )}
      <button type="button" className="btn btn-soft ta-btn ta-soft dz-btn-sm" onClick={exportJson}>
        <Download size={14} />
        Export
      </button>
      <button type="button" className="btn btn-soft ta-btn ta-soft dz-btn-sm" onClick={() => file.current?.click()}>
        Import
      </button>
      <button type="button" className="link-btn" aria-expanded={paste.open} onClick={() => setPaste((p) => ({ ...p, open: !p.open, error: null }))}>
        Paste JSON
      </button>
      <input
        ref={file}
        type="file"
        accept="application/json,.json"
        className="sr-only"
        tabIndex={-1}
        aria-label="Import a GEMINI project file"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          const err = load(await f.text());
          setError(err ? `${f.name}: ${err}` : null);
        }}
      />
    </div>
  );

  // In full screen the drawing is fitted to the part of the window the panels leave free.
  const fitPadding: FitViewOptions["padding"] = full
    ? narrow
      ? { top: `${bar.h + 24}px`, right: "12px", bottom: "64px", left: "12px" }
      : { top: `${bar.h + 28}px`, right: sideOpen ? "360px" : "64px", bottom: "64px", left: paletteOpen ? "200px" : "64px" }
    : 0.08;
  const fitKey = `${size.w}x${size.h}:${full}:${sideOpen}:${paletteOpen}:${full ? bar.h : 0}`;

  return (
    <div className={`dz-gem${full && !sideOpen ? " side-folded" : ""}${full && !paletteOpen ? " palette-folded" : ""}`}>
      <div ref={barRef} className={`dz-card dz-gem-bar${full ? " dz-float" : ""}`}>
        {full ? (
          <FullBar>
            {runControls}
            <FoldButton open={barOpen} onToggle={() => setBarOpen((o) => !o)} label="Project tools" toward="down" />
          </FullBar>
        ) : (
          <div className="dz-gem-run">{runControls}</div>
        )}
        {(!full || barOpen) && fileControls}
        {(!full || barOpen) && paste.open && (
          <form
            className="dz-paste"
            onSubmit={(e) => {
              e.preventDefault();
              const err = load(paste.text);
              setPaste(err ? { ...paste, error: err } : { open: false, text: "", error: null });
            }}
          >
            <label htmlFor={`${uid}-paste`}>A GEMINI project (the JSON of simulator_examples/projects/*.json)</label>
            <textarea id={`${uid}-paste`} rows={6} spellCheck={false} value={paste.text} onChange={(e) => setPaste({ ...paste, text: e.target.value, error: null })} aria-invalid={!!paste.error} />
            {paste.error && <span className="dz-field-err">{paste.error}</span>}
            <div className="dz-edit-actions">
              <button type="submit" className="btn btn-soft ta-btn ta-soft dz-btn-sm" disabled={!paste.text.trim()}>
                Load it
              </button>
            </div>
          </form>
        )}
        <RunStatus run={run} stale={stale} error={error} top={full && !barOpen ? [] : top} />
        {(!full || barOpen) && (
          <p className="dz-gem-legend">
            <span className="dz-gem-legend-dot" aria-hidden="true" />
            GEMINI simulates the brine loop at full flow; the heat pump, chillers and absorption chiller are not GEMINI models (Plant view).
          </p>
        )}
      </div>

      <div ref={stageRef} className="dz-stage dz-gem-stage" style={{ "--dz-fill": `${fill}px` } as CSSProperties}>
        <aside className={`dz-card dz-gem-palette${full ? " dz-float" : ""}${full && !paletteOpen ? " folded" : ""}`} aria-label="Add a component">
          <div className="dz-side-head">
            {(!full || paletteOpen) && <span className="dz-side-title">Add a component</span>}
            {full && <FoldButton open={paletteOpen} onToggle={() => setPaletteOpen((o) => !o)} label="Components" toward="left" />}
          </div>
          {(!full || paletteOpen) && (
            <div className="dz-side-body">
              <Palette types={catalogue.data?.types ?? []} status={catalogue.data ? "ready" : catalogue.status} onAdd={(t) => add(t)} />
            </div>
          )}
        </aside>
        <section className="dz-card dz-canvas-card dz-gem-canvas" aria-label={`GEMINI project of ${design.code}`}>
          <div className="dz-canvas" ref={canvasRef}>
            <ProjectCanvas
              key={`${canvasKey}-${narrow ? "n" : "w"}`}
              perRow={narrow ? 2 : 4}
              minZoom={narrow ? 0.45 : 0.2}
              fitPadding={fitPadding}
              fitKey={fitKey}
              controls={full && !narrow ? "bottom-center" : "bottom-right"}
              allPorts={allPorts}
              project={project}
              types={types}
              run={result && result.ok ? result : null}
              stale={stale}
              compare={!!run?.compared}
              positions={positions}
              onPositions={setPositions}
              selection={selection}
              onSelection={(sel) => {
                setSelection(sel);
                if (sel && full) setSideOpen(true);
              }}
              onConnect={(s, o, t, i) => setProject(connect(project, s, o, t, i))}
              onDelete={(ns, es) => {
                setProject(removeComponents(removePairs(project, es), ns));
                setSelection(null);
              }}
              onBoundary={onBoundary}
              onDropType={(type, at) => {
                const t = types.get(type);
                if (t) add(t, at);
              }}
              centreRef={centre}
            />
            {!full && <FullButton className="dz-canvas-full" />}
          </div>
        </section>
        <aside className={`dz-card dz-side dz-gem-side${full ? " dz-float" : ""}${full && !sideOpen ? " folded" : ""}`} aria-label="Component">
          {full && (
            <div className="dz-side-head">
              {sideOpen && <span className="dz-side-title">{selection?.kind === "node" ? selection.id : selection?.kind === "edge" ? "Connection" : "The project"}</span>}
              <FoldButton open={sideOpen} onToggle={() => setSideOpen((o) => !o)} label="Inspector" toward="right" />
            </div>
          )}
          {(!full || sideOpen) && (
            <div className="dz-side-body">
              <ComponentInspector project={project} selection={selection} types={types} run={result && result.ok ? result : null} stale={stale} compare={!!run?.compared} onChange={change} onSelection={setSelection} />
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function RunStatus({ run, stale, error, top }: { run: RunState | null; stale: boolean; error: string | null; top: ReturnType<typeof biggest> }) {
  if (error)
    return (
      <p role="alert" className="dz-error">
        <strong>The run didn't happen.</strong> {error}
      </p>
    );
  if (!run) return <p className="dz-muted dz-gem-hint">Run it to see GEMINI's outputs on every component.</p>;
  const r = run.result;
  return (
    <div className="dz-gem-result" aria-live="polite">
      {r.ok ? (
        <div className="dz-gem-ok">
          <strong>Solved in {r.seconds < 1 ? `${Math.round(r.seconds * 1000)} ms` : `${r.seconds.toFixed(1)} s`}</strong>
          <span>
            {" "}
            on GEMINI fixed with{" "}
            <details className="dz-patches">
              <summary>
                {r.patches.length} patch{r.patches.length === 1 ? "" : "es"}
              </summary>
              <ul>
                {r.patches.map((p) => (
                  <li key={p}>
                    <code>{p.replace(/\.diff$/, "")}</code>
                  </li>
                ))}
              </ul>
            </details>
          </span>
          {stale && <span className="tag tag-amber">edited since: run again</span>}
        </div>
      ) : (
        <p role="alert" className="dz-error">
          <strong>GEMINI (fixed) couldn't solve this project.</strong> {r.error}
        </p>
      )}
      {run.compared && r.released && !r.released.ok && (
        <p className="dz-error soft">
          <strong>GEMINI as released couldn't solve it.</strong> {r.released.error}
        </p>
      )}
      {top.length > 0 && (
        <div className="dz-impact">
          <span className="dz-insp-cap">Where the fixes change the answer most</span>
          <ul>
            {top.map((t) => (
              <li key={`${t.name}.${t.key}`}>
                <code>
                  {t.name}.{t.key}
                </code>{" "}
                <strong>{t.fixed}</strong> fixed against {t.released} released{t.text !== "from 0" && <b className="dz-impact-pct"> ({t.text})</b>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {run.compared && r.ok && r.released?.ok && !top.length && <p className="dz-muted">The released GEMINI gives the same key outputs (within 10%).</p>}
    </div>
  );
}
