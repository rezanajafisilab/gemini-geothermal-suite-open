// "Export" on the one-design tabs (3 Nov): one button for the design's files, each opening its
// preview first (the operator's report, the permit and subsidy pack, the GEMINI project).

import { useEffect, useRef, useState } from "react";

import { Chevron, Download } from "../../components/Icons";
import { EXPORTS, previewExport, type ExportKind } from "../exports";
import { useWorkbench } from "../store";
import { useOnScreen } from "./DesignPicker";
import "./workbench.css";

const ICONS: Record<ExportKind, string> = {
  report: "M4 1.8h5.4L12.5 5v9.2H4zM9.2 2v3.2h3.2M6 8.2h4.4M6 10.6h4.4",
  permits: "M3.5 2h9v12h-9zM5.8 5.2h4.4M5.8 7.8h4.4M5.8 10.4h2.6",
  gemini: "M5.5 2.5C3.8 2.5 4 4.5 4 6S2.5 8 2.5 8 4 8.5 4 10s-.2 3.5 1.5 3.5M10.5 2.5c1.7 0 1.5 2 1.5 3.5s1.5 2 1.5 2-1.5.5-1.5 2 .2 3.5-1.5 3.5",
};

export function ExportMenu() {
  const wb = useWorkbench();
  const design = wb.selected;
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  useOnScreen(open, pop);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  if (!wb.threadId || !design || wb.fixture) return null;
  const items = EXPORTS.filter((x) => (x.kind === "gemini" ? !!design.graph?.gemini_project : x.kind === "permits" ? design.plant.depth_m > 0 : true));
  return (
    <div className="xm" ref={root}>
      <button type="button" className="wb-btn ta-btn ta-chip" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Download size={14} />
        Export
        <Chevron open={open} />
      </button>
      {open && (
        <div ref={pop} className="xm-pop ta-rise" role="menu" aria-label={`Export ${design.uid || design.code}`}>
          {items.map((x) => (
            <button
              key={x.kind}
              type="button"
              role="menuitem"
              className="xm-item"
              onClick={() => {
                setOpen(false);
                previewExport(x.kind, wb.threadId!, design.id);
              }}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path d={ICONS[x.kind]} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="xm-text">
                <span className="xm-label">{x.label}</span>
                <span className="xm-hint">{x.hint}</span>
              </span>
            </button>
          ))}
          <span className="xm-foot">Each opens as a preview; save it from there.</span>
        </div>
      )}
    </div>
  );
}
