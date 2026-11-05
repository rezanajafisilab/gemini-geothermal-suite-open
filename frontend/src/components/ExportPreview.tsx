// An export shown before it is saved (3 Nov): the operator's report and the permit and subsidy
// pack as the PDF itself, the GEMINI project as its JSON laid out (each top-level part folds). The
// file is fetched once; Save writes that same file, so what was seen is what is kept. Any part of
// the app opens one with openExport({...}); the host (in App) draws it.

import { useEffect, useMemo, useState } from "react";

import { Download, Spinner } from "./Icons";
import { Modal } from "./Modal";

export interface ExportRequest {
  /** What it is, in words ("Operator's report"). */
  title: string;
  /** The design it is of ("A1 · 1D-BO-EC@3500-N1"). */
  subject: string;
  /** The server's address for the file. */
  url: string;
  filename: string;
  kind: "pdf" | "json";
}

type Listener = (r: ExportRequest) => void;
const listeners = new Set<Listener>();

/** Show an export's preview (the host in App draws it). */
export function openExport(r: ExportRequest): void {
  listeners.forEach((l) => l(r));
}

/** The preview on screen, if any: mounted once, at the app's root. */
export function ExportHost() {
  const [req, setReq] = useState<ExportRequest | null>(null);
  useEffect(() => {
    const l: Listener = (r) => setReq(r);
    listeners.add(l);
    return () => void listeners.delete(l);
  }, []);
  return req ? <ExportPreview req={req} onClose={() => setReq(null)} /> : null;
}

type Loaded = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; blob: Blob; url: string; json?: unknown };

export function ExportPreview({ req, onClose }: { req: ExportRequest; onClose: () => void }) {
  const [file, setFile] = useState<Loaded>({ state: "loading" });
  useEffect(() => {
    let alive = true;
    let made: string | null = null;
    fetch(req.url)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.text().catch(() => "")) || `HTTP ${r.status}`);
        const blob = await r.blob();
        const json = req.kind === "json" ? JSON.parse(await blob.text()) : undefined;
        made = URL.createObjectURL(blob);
        if (alive) setFile({ state: "ready", blob, url: made, json });
      })
      .catch((e: Error) => alive && setFile({ state: "error", message: readable(e.message) }));
    return () => {
      alive = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [req]);
  const save = () => {
    if (file.state !== "ready") return;
    const a = document.createElement("a");
    a.href = file.url;
    a.download = req.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };
  return (
    <Modal label={`${req.title}: preview`} onClose={onClose} className="xp-modal">
      <header className="xp-head">
        <span className={`xp-badge ${req.kind}`}>{req.kind === "pdf" ? "PDF" : "JSON"}</span>
        <div className="xp-titles">
          <h2>{req.title}</h2>
          <span className="xp-sub">
            {req.subject} · <span className="xp-file">{req.filename}</span>
            {file.state === "ready" && ` · ${size(file.blob.size)}`}
          </span>
        </div>
      </header>
      <div className="xp-body">
        {file.state === "loading" && (
          <div className="xp-wait" role="status">
            <Spinner size={18} />
            Making the file…
          </div>
        )}
        {file.state === "error" && (
          <p className="xp-error" role="alert">
            Couldn't make it: {file.message}
          </p>
        )}
        {file.state === "ready" && req.kind === "pdf" && <iframe className="xp-pdf" title={`${req.title} of ${req.subject}`} src={`${file.url}#view=FitH`} />}
        {file.state === "ready" && req.kind === "json" && <JsonTree value={file.json} />}
      </div>
      <footer className="xp-foot">
        <span className="xp-note">{req.kind === "pdf" ? "This is the file that will be saved." : "Load it in GEMINI with gemini_simulator.project_loader.load_project(path)."}</span>
        <button type="button" className="btn btn-soft ta-btn ta-soft" onClick={onClose}>
          Close
        </button>
        <button type="button" className="btn btn-ink ta-btn ta-ink" disabled={file.state !== "ready"} onClick={save}>
          <Download size={14} />
          Save
        </button>
      </footer>
    </Modal>
  );
}

function size(n: number): string {
  return n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function readable(text: string): string {
  try {
    const d = JSON.parse(text);
    return typeof d.detail === "string" ? d.detail : text;
  } catch {
    return text;
  }
}

/** A JSON value laid out: objects and arrays fold (the top level open), strings and numbers coloured. */
export function JsonTree({ value }: { value: unknown }) {
  return (
    <div className="xp-json" role="tree" aria-label="The file's contents">
      <JsonNode name={null} value={value} depth={0} />
    </div>
  );
}

function JsonNode({ name, value, depth }: { name: string | null; value: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 1);
  const entries = useMemo(() => (value && typeof value === "object" ? Object.entries(value as Record<string, unknown>) : null), [value]);
  const key = name != null && <span className="xp-k">{name}</span>;
  if (!entries) {
    const cls = typeof value === "string" ? "xp-s" : typeof value === "number" ? "xp-n" : "xp-b";
    const text = typeof value === "string" ? `"${value.length > 160 ? `${value.slice(0, 160)}…` : value}"` : String(value);
    return (
      <div className="xp-row" role="treeitem">
        {key}
        {key && <span className="xp-p">: </span>}
        <span className={cls}>{text}</span>
      </div>
    );
  }
  const list = Array.isArray(value);
  const brace = list ? ["[", "]"] : ["{", "}"];
  // Long lists of numbers (a year's daily flows) read as one line.
  const numbers = list && entries.length > 12 && entries.every(([, v]) => typeof v === "number");
  return (
    <div className="xp-row" role="treeitem" aria-expanded={numbers ? undefined : open}>
      {!numbers && (
        <button type="button" className="xp-fold" aria-label={open ? "Fold" : "Open"} onClick={() => setOpen(!open)}>
          {open ? "▾" : "▸"}
        </button>
      )}
      {key}
      {key && <span className="xp-p">: </span>}
      {numbers ? (
        <span className="xp-n" title={entries.map(([, v]) => v).join(", ")}>
          [{entries.length} values: {(entries.slice(0, 6).map(([, v]) => v) as number[]).join(", ")}, …]
        </span>
      ) : open ? (
        <>
          <span className="xp-p">{brace[0]}</span>
          <div className="xp-kids" role="group">
            {entries.map(([k, v]) => (
              <JsonNode key={k} name={list ? null : k} value={v} depth={depth + 1} />
            ))}
          </div>
          <span className="xp-p">{brace[1]}</span>
        </>
      ) : (
        <button type="button" className="xp-more" onClick={() => setOpen(true)}>
          {brace[0]} {entries.length} {list ? "items" : "keys"} {brace[1]}
        </button>
      )}
    </div>
  );
}
