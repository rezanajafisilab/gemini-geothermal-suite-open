// The GEMINI project as an editable graph (React Flow): a node per component with its input ports
// on the left and output ports on the right (boundary inputs as value pills you can edit), an
// edge per connected port pair. Connect two ports to add a connection (at the end of the list),
// select and press Delete (or Backspace) to remove. After a run each node shows its key outputs,
// and with the comparison on, GEMINI-as-released's value and the difference.

import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, useState, type DragEvent, type RefObject } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  Position,
  ReactFlow,
  applyNodeChanges,
  ReactFlowProvider,
  getSmoothStepPath,
  useConnection,
  useInternalNode,
  useReactFlow,
  useUpdateNodeInternals,
  type Connection,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeChange,
  type FitViewOptions,
  type NodeProps,
  type PanelPosition,
} from "@xyflow/react";

import type { CatalogueType, GeminiProject, GeminiRun } from "../../workbench";
import { FitControls, FitWhenReady } from "./fit";
import { CanvasDots } from "./PlantCanvas";
import {
  PNODE_W,
  compactPorts,
  compareOutput,
  componentMeta,
  componentPorts,
  componentRole,
  estimateHeight,
  impossibleOutput,
  isBrineLoop,
  keyOutputs,
  layoutLoop,
  layoutProject,
  projectEdges,
  readOutput,
  type Ports,
} from "./project";

interface ProjectCtx {
  /** Every port of every component, not only those in use. */
  allPorts: boolean;
  run: GeminiRun | null;
  stale: boolean;
  compare: boolean;
  types: Map<string, CatalogueType>;
  onBoundary: (component: string, key: string, value: number) => void;
}
const Ctx = createContext<ProjectCtx | null>(null);
const useProject = () => useContext(Ctx)!;

type CompData = { name: string; type: string; label: string; role: string; description: string | null; ports: Ports };
export type CompNodeT = Node<CompData, "component">;
type PortData = { out: string; in: string };
type PortEdgeT = Edge<PortData, "port">;

// ------------------------------------------------------------------ boundary pill

function BoundaryPill({ component, port }: { component: string; port: { key: string; boundary: number | null; unit: string } }) {
  const { onBoundary } = useProject();
  const [text, setText] = useState(String(port.boundary));
  const [bad, setBad] = useState(false);
  useEffect(() => setText(String(port.boundary)), [port.boundary]);
  const commit = () => {
    const v = Number(text.replace("−", "-"));
    if (!text.trim() || !Number.isFinite(v)) {
      setBad(true);
      return;
    }
    setBad(false);
    if (v !== port.boundary) onBoundary(component, port.key, v);
  };
  return (
    <span className={`dz-bpill nodrag${bad ? " bad" : ""}`} title="A boundary input: a fixed value, not fed by another component">
      <input
        aria-label={`${component} ${port.key}, boundary value${port.unit ? ` in ${port.unit}` : ""}`}
        value={text}
        inputMode="decimal"
        size={Math.max(3, Math.min(9, text.length))}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") {
            setText(String(port.boundary));
            setBad(false);
          }
        }}
      />
      {port.unit && <span>{port.unit}</span>}
    </span>
  );
}

// ------------------------------------------------------------------ node

const ComponentNode = memo(function ComponentNode({ id, data, selected }: NodeProps<CompNodeT>) {
  const { run, stale, compare, allPorts } = useProject();
  const { name, type, label, role, description } = data;
  const meta = componentMeta(type);
  // Compact (the ports in use) unless asked, picked, or while a wire is being drawn.
  const connecting = useConnection((c) => c.inProgress);
  const full = allPorts || selected || connecting;
  const ports = full ? data.ports : compactPorts(data.ports);
  const hidden = data.ports.inputs.length + data.ports.outputs.length - ports.inputs.length - ports.outputs.length;
  const update = useUpdateNodeInternals();
  useEffect(() => update(id), [full, id, update]);
  const fixed = run?.outputs[name];
  const released = compare ? run?.released?.outputs[name] : undefined;
  const keys = keyOutputs(type, fixed);
  const unitOf = (k: string) => data.ports.outputs.find((o) => o.key === k)?.unit;
  return (
    <div className={`dz-comp${selected ? " sel" : ""}`} style={{ width: PNODE_W }}>
      <div className="dz-comp-head" title={description ?? undefined}>
        <span className="dz-comp-icon" aria-hidden="true" style={{ ["--comp" as string]: meta.color }}>
          <svg width="15" height="15" viewBox="0 0 16 16">
            <path d={meta.icon} fill="none" stroke={meta.color} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span className="dz-comp-titles">
          <span className="dz-comp-name">{name}</span>
          <span className="dz-comp-type">
            {label}
            {role ? ` · ${role}` : ""}
          </span>
        </span>
      </div>
      <div className="dz-comp-ports">
        <div className="dz-comp-col">
          {ports.inputs.map((p) => (
            <div key={p.key} className={`dz-port in${p.connected ? " used" : ""}${p.boundary != null ? " bound" : ""}`}>
              <Handle type="target" position={Position.Left} id={`in:${p.key}`} className="dz-handle" aria-label={`${name} input ${p.key}`} />
              <span className="dz-port-key" title={p.unit ? `${p.key} (${p.unit})` : p.key}>
                {p.key}
              </span>
              {p.boundary != null && <BoundaryPill component={name} port={p} />}
            </div>
          ))}
        </div>
        <div className="dz-comp-col out">
          {ports.outputs.map((p) => (
            <div key={p.key} className={`dz-port out${p.connected ? " used" : ""}`}>
              <span className="dz-port-key" title={p.unit ? `${p.key} (${p.unit})` : p.key}>
                {p.key}
              </span>
              <Handle type="source" position={Position.Right} id={`out:${p.key}`} className="dz-handle" aria-label={`${name} output ${p.key}`} />
            </div>
          ))}
        </div>
      </div>
      {hidden > 0 && <div className="dz-comp-more">+{hidden} more port{hidden === 1 ? "" : "s"}</div>}
      {keys.length > 0 && (
        <div className={`dz-comp-out${stale ? " stale" : ""}`}>
          {keys.map((k) => {
            const f = readOutput(type, k, fixed![k], unitOf(k));
            const r = released && k in released ? readOutput(type, k, released[k], unitOf(k)) : null;
            const cmp = released ? compareOutput(fixed![k], released[k]) : null;
            const bad = impossibleOutput(type, k, fixed![k], unitOf(k));
            return (
              <div key={k} className={`dz-out-row${cmp?.big ? " big" : ""}${bad ? " bad" : ""}`} title={bad ? `${k}: ${bad}` : undefined}>
                <span className="dz-out-key">{k}</span>
                <span className="dz-out-val">
                  <strong>{f.text}</strong> {f.unit}
                  {bad && <span className="dz-out-bad"> not physical</span>}
                </span>
                {r && cmp && (
                  <span className="dz-out-rel">
                    released {r.text} {r.unit} · <b>{cmp.text}</b>
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

// ------------------------------------------------------------------ edge

const PortEdge = memo(function PortEdge({ id, source, target, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, selected }: EdgeProps<PortEdgeT>) {
  // A wire back to the start of the next band runs in the gap above that band, not through nodes.
  const t = useInternalNode(target);
  const s = useInternalNode(source);
  const back = targetX < sourceX - 24 && t && s && t.internals.positionAbsolute.y > s.internals.positionAbsolute.y + 40;
  const centerY = back ? t.internals.positionAbsolute.y - 26 : undefined;
  const [path, labelX, labelY] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 10, offset: 18, centerY });
  return (
    <>
      <BaseEdge id={id} path={path} className={`dz-wire${selected ? " sel" : ""}`} interactionWidth={16} />
      {selected && data && (
        <EdgeLabelRenderer>
          <div className="dz-wire-label" style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}>
            {data.out} → {data.in}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

const nodeTypes = { component: ComponentNode };
const edgeTypes = { port: PortEdge };

// ------------------------------------------------------------------ canvas

export type Selection = { kind: "node"; id: string } | { kind: "edge"; id: string } | null;

interface Props {
  /** Room to leave around the project when fitting it (a fraction, or px per side in full screen). */
  fitPadding: FitViewOptions["padding"];
  /** Changes when the canvas or the panels over it change: the project is fitted again. */
  fitKey: string;
  /** Where the zoom buttons go. */
  controls: PanelPosition;
  /** Layers per band before the layout wraps (2 on a phone). */
  perRow: number;
  /** The fit never zooms out further than this (phones pan instead). */
  minZoom: number;
  allPorts: boolean;
  project: GeminiProject;
  types: Map<string, CatalogueType>;
  run: GeminiRun | null;
  stale: boolean;
  compare: boolean;
  positions: Record<string, { x: number; y: number }>;
  onPositions: (fn: (p: Record<string, { x: number; y: number }>) => Record<string, { x: number; y: number }>) => void;
  selection: Selection;
  onSelection: (s: Selection) => void;
  onConnect: (source: string, out: string, target: string, input: string) => void;
  onDelete: (nodes: string[], edges: { source: string; target: string; out: string; in: string }[]) => void;
  onBoundary: (component: string, key: string, value: number) => void;
  /** A palette item dropped on the canvas at a flow position. */
  onDropType: (type: string, at: { x: number; y: number }) => void;
  /** Set by the canvas: where the middle of the view is, for components added with a click. */
  centreRef: RefObject<(() => { x: number; y: number }) | null>;
}

export const DRAG_TYPE = "application/x-gemini-type";

/** The canvas, with a React Flow store of its own (a remount starts it afresh, fit included). */
export function ProjectCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <ProjectCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

function ProjectCanvasInner(props: Props) {
  const { fitPadding, fitKey, controls, perRow, minZoom, allPorts, project, types, run, stale, compare, positions, onPositions, selection, onSelection, onConnect, onDelete, onBoundary, onDropType, centreRef } = props;
  const flow = useReactFlow<CompNodeT, PortEdgeT>();
  const wrap = useRef<HTMLDivElement>(null);

  const desired = useMemo(() => {
    const names = Object.keys(project.components);
    const portsOf = new Map(names.map((n) => [n, componentPorts(project, n, types.get(project.components[n].type))]));
    const height = (n: string) => estimateHeight(compactPorts(portsOf.get(n)!), Math.max(3, keyOutputs(project.components[n].type, run?.outputs[n]).length));
    // A brine loop is laid out the way the brine flows, trains in lanes; anything else in layers.
    const auto = isBrineLoop(project) ? layoutLoop(project, height) : layoutProject(project, height, perRow);
    return names.map((n) => {
      const c = project.components[n];
      const type = c.type;
      const label = types.get(type)?.label ?? componentMeta(type).label;
      const role = componentRole(project, n);
      return {
        id: n,
        type: "component" as const,
        position: positions[n] ?? auto[n],
        data: { name: n, type, label, role, description: typeof c._description === "string" ? c._description : null, ports: portsOf.get(n)! },
        ariaLabel: `${n}, ${label}${role ? `, ${role}` : ""}`,
      };
    });
    // Positions only seed new nodes; moving a node doesn't rebuild the others.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, types, perRow]);

  const [nodes, setNodes] = useState<CompNodeT[]>(() => desired);
  useEffect(() => {
    setNodes((prev) => {
      const before = new Map(prev.map((n) => [n.id, n]));
      return desired.map((d) => {
        const old = before.get(d.id);
        if (old && old.data === d.data) return old;
        return old ? { ...old, data: d.data, ariaLabel: d.ariaLabel } : { ...d, position: positions[d.id] ?? d.position };
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desired]);

  const edges = useMemo<PortEdgeT[]>(
    () =>
      projectEdges(project).map((e) => ({
        id: e.id,
        type: "port",
        source: e.source,
        target: e.target,
        sourceHandle: `out:${e.out}`,
        targetHandle: `in:${e.in}`,
        data: { out: e.out, in: e.in },
        selected: selection?.kind === "edge" && selection.id === e.id,
        ariaLabel: `Connection ${e.source} ${e.out} to ${e.target} ${e.in}`,
      })),
    [project, selection],
  );

  const synced = useMemo(
    () => nodes.map((n) => {
      const sel = selection?.kind === "node" && selection.id === n.id;
      return n.selected === sel ? n : { ...n, selected: sel };
    }),
    [nodes, selection],
  );

  const onNodesChange = useCallback(
    (changes: NodeChange<CompNodeT>[]) => {
      // Removing goes through onDelete (the project); selection through onSelection.
      const kept = changes.filter((c) => c.type !== "remove" && c.type !== "select");
      const picked = changes.find((c) => c.type === "select" && c.selected);
      if (picked && picked.type === "select") onSelection({ kind: "node", id: picked.id });
      if (kept.length) setNodes((ns) => applyNodeChanges(kept, ns));
      const moved = changes.filter((c) => c.type === "position" && c.position && c.dragging === false);
      if (moved.length)
        onPositions((p) => {
          const next = { ...p };
          for (const c of moved) if (c.type === "position" && c.position) next[c.id] = c.position;
          return next;
        });
    },
    [onSelection, onPositions],
  );

  useEffect(() => {
    centreRef.current = () => {
      const r = wrap.current?.getBoundingClientRect();
      if (!r) return { x: 0, y: 0 };
      const p = flow.screenToFlowPosition({ x: r.left + r.width / 2, y: r.top + r.height / 2 });
      return { x: p.x - PNODE_W / 2, y: p.y - 60 };
    };
  });

  const ctx = useMemo<ProjectCtx>(() => ({ allPorts, run, stale, compare, types, onBoundary }), [allPorts, run, stale, compare, types, onBoundary]);

  const drop = (e: DragEvent) => {
    const type = e.dataTransfer.getData(DRAG_TYPE);
    if (!type) return;
    e.preventDefault();
    const p = flow.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    onDropType(type, { x: p.x - PNODE_W / 2, y: p.y - 20 });
  };

  return (
    <Ctx.Provider value={ctx}>
      <div
        ref={wrap}
        className="dz-canvas-inner"
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes(DRAG_TYPE)) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
          }
        }}
        onDrop={drop}
      >
        <ReactFlow<CompNodeT, PortEdgeT>
          nodes={synced}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={(changes) => {
            const picked = changes.find((c) => c.type === "select" && c.selected);
            if (picked && picked.type === "select") onSelection({ kind: "edge", id: picked.id });
          }}
          onPaneClick={() => onSelection(null)}
          onConnect={(c: Connection) => {
            if (!c.sourceHandle?.startsWith("out:") || !c.targetHandle?.startsWith("in:")) return;
            onConnect(c.source, c.sourceHandle.slice(4), c.target, c.targetHandle.slice(3));
          }}
          isValidConnection={(c) => c.source !== c.target}
          onDelete={({ nodes: ns, edges: es }) =>
            onDelete(
              ns.map((n) => n.id),
              es.map((e) => ({ source: e.source, target: e.target, out: (e.data as PortData).out, in: (e.data as PortData).in })),
            )
          }
          deleteKeyCode={["Delete", "Backspace"]}
          multiSelectionKeyCode={null}
          selectionKeyCode={null}
          minZoom={0.2}
          maxZoom={1.6}
          zoomOnScroll={false}
          panOnScroll={false}
          preventScrolling={false}
          connectionRadius={24}
          ariaLabelConfig={{
            "node.a11yDescription.default": "Press Enter to select this component; Delete removes it.",
            "edge.a11yDescription.default": "Press Enter to select this connection; Delete removes it.",
          }}
        >
          <CanvasDots id="project-dots" />
          <FitControls position={controls} orientation={controls === "bottom-center" ? "horizontal" : "vertical"} />
          <FitWhenReady padding={fitPadding} minZoom={minZoom} again={fitKey} />
        </ReactFlow>
      </div>
    </Ctx.Provider>
  );
}
