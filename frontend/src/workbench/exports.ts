// The exports of a design (3 Nov): the operator's report and the permit and subsidy pack (PDF),
// and the GEMINI project (JSON). Each opens a preview first (components/ExportPreview).

import { openExport, type ExportRequest } from "../components/ExportPreview";

export type ExportKind = "report" | "permits" | "gemini";

export const EXPORTS: { kind: ExportKind; label: string; hint: string }[] = [
  { kind: "report", label: "Operator's report", hint: "PDF, about six A4 pages: the year, N-1, failures, limits" },
  { kind: "permits", label: "Permit and subsidy pack", hint: "PDF: the production plan's figures, SDE++, environment" },
  { kind: "gemini", label: "GEMINI project", hint: "JSON that GEMINI's own loader reads and runs" },
];

/** A design's export as a preview request (``id`` the design's id, "A1 · 1D-BO-EC"). */
export function exportRequest(kind: ExportKind, threadId: string, id: string): ExportRequest {
  const q = new URLSearchParams({ threadId, id });
  const code = (id.split(" · ").pop() || "design").replace(/[^\w.-]+/g, "-");
  const meta = EXPORTS.find((e) => e.kind === kind)!;
  if (kind === "gemini") return { title: meta.label, subject: id, url: `/api/gemini.json?${q}`, filename: `dioscuri-${code}.gemini.json`, kind: "json" };
  if (kind === "permits") return { title: meta.label, subject: id, url: `/api/permits.pdf?${q}`, filename: `dioscuri-${code}-permits.pdf`, kind: "pdf" };
  return { title: meta.label, subject: id, url: `/api/report.pdf?${q}`, filename: `dioscuri-${code}.pdf`, kind: "pdf" };
}

/** Show a design's export (its preview, then Save). */
export function previewExport(kind: ExportKind, threadId: string, id: string): void {
  openExport(exportRequest(kind, threadId, id));
}
