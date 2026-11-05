// A file the agent opened (CUSTOM "file", or GET /api/files?view=1 from a chip): its name, where
// it comes from, its size and a download link, then its views. A table gets its column stats
// and totals above the first rows; the chart is hand-drawn (LineChart); text and JSON read as
// they are; an image opens full size on a click.

import { useState } from "react";

import type { FileView } from "../agent/types";
import { useFiles } from "./filesContext";
import { Download, FileGlyph } from "./Icons";
import { LineChart, fmtValue } from "./LineChart";

type View = "pdf" | "table" | "chart" | "text" | "image";

const LABELS: Record<View, string> = { pdf: "PDF", table: "Table", chart: "Chart", text: "Text", image: "Image" };

/** A PDF's address for the browser's own viewer (the raw file, sent to show, not to save). */
export function pdfUrl(file: FileView): string | null {
  return file.url && /\.pdf$/i.test(file.name) ? `${file.url}${file.url.includes("?") ? "&" : "?"}inline=1` : null;
}

export function fmtBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** The views a file has, in tab order. */
export function viewsOf(file: FileView): View[] {
  const has: Record<View, boolean> = {
    pdf: !!pdfUrl(file),
    table: !!file.table?.columns?.length,
    chart: !!file.chart?.series?.length && !!file.chart.x_values?.length,
    text: typeof file.text === "string",
    image: !!file.image?.url,
  };
  return (Object.keys(LABELS) as View[]).filter((v) => has[v]);
}

const TINT: Record<string, { bg: string; ink: string }> = {
  table: { bg: "#E2F3F5", ink: "#0A6F7C" },
  image: { bg: "#EFEAFB", ink: "#5B3FA6" },
  other: { bg: "#EEF2F2", ink: "#45515B" },
};

export function FileCard({ file, inModal = false }: { file: FileView; inModal?: boolean }) {
  const views = viewsOf(file);
  // A PDF opens as the document itself; its text (what the agent reads) is the next tab.
  const [view, setView] = useState<View | undefined>(views.includes("pdf") ? "pdf" : views.includes(file.show) ? file.show : views[0]);
  const tint = TINT[file.kind === "table" || file.kind === "image" ? file.kind : "other"];
  const t = file.table;
  const facts = [
    fmtBytes(file.size_bytes),
    t ? `${t.total_rows.toLocaleString("en-US")} ${t.total_rows === 1 ? "row" : "rows"} · ${t.columns.length} columns` : "",
    file.image?.width && file.image.height ? `${file.image.width} × ${file.image.height} px` : "",
  ].filter(Boolean);
  const at = view ? views.indexOf(view) : 0;
  return (
    <section className={`filecard${inModal ? " in-modal" : " card ta-rise"}`} aria-label={`File ${file.name}`}>
      <header className="filecard-head">
        <span className="icon-box" style={{ background: tint.bg, color: tint.ink }}>
          <FileGlyph kind={file.kind === "table" || file.kind === "image" ? file.kind : "text"} size={16} />
        </span>
        <div className="filecard-title">
          <span className="filecard-name">
            <strong title={file.name}>{file.name}</strong>
            <span className={`tag ${file.origin === "attachment" ? "tag-amber" : "tag-teal"}`}>{file.origin === "attachment" ? "your upload" : "project file"}</span>
          </span>
          <span className="filecard-facts">{facts.join(" · ")}</span>
        </div>
        {file.url && (
          <a className="btn btn-soft ta-btn ta-soft filecard-dl" href={file.url} download={file.name} title={`Download ${file.name}`}>
            <Download />
            <span className="hide-narrow">Download</span>
          </a>
        )}
      </header>
      {file.note && <p className="filecard-note">{file.note}</p>}
      {views.length > 1 && (
        <div className="seg tabs filecard-tabs" role="tablist" aria-label={`Views of ${file.name}`}>
          <span className="seg-thumb ta-thumb" style={{ left: `calc(4px + ${at} * (100% - 8px) / ${views.length})`, width: `calc((100% - 8px) / ${views.length})` }} />
          {views.map((v) => (
            <button key={v} type="button" role="tab" aria-selected={view === v} style={{ fontWeight: view === v ? 650 : 450 }} onClick={() => setView(v)}>
              {LABELS[v]}
            </button>
          ))}
        </div>
      )}
      {(view === "table" || view === "chart") && <StatStrip file={file} />}
      {view === "table" && t && <FileTable name={file.name} table={t} />}
      {view === "chart" && file.chart && <LineChart chart={file.chart} />}
      {view === "pdf" && <iframe className="fpdf" src={pdfUrl(file)!} title={`${file.name}, as a document`} />}
      {view === "text" && <pre className="ftext">{file.text}</pre>}
      {view === "image" && file.image && <ImageView name={file.name} url={file.image.url} />}
      {!view && <p className="fempty">There is no preview for this kind of file. Download it to open it.</p>}
    </section>
  );
}

/** Totals as bold tiles, then each numeric column's mean with its range. */
function StatStrip({ file }: { file: FileView }) {
  const totals = file.totals ?? [];
  const stats = file.stats ?? [];
  if (!totals.length && !stats.length) return null;
  return (
    <div className="fstats" aria-label="Column statistics">
      {totals.map((t) => (
        <div key={`t-${t.column}-${t.label}`} className="fstat total">
          <span className="fstat-label">{t.label}</span>
          <span className="fstat-value">
            {fmtValue(t.value)}
            <span className="tile-unit"> {t.unit}</span>
          </span>
          <span className="fstat-col">{t.column}</span>
        </div>
      ))}
      {stats.map((s) => {
        const span = s.max - s.min;
        const mean = span > 0 ? Math.min(100, Math.max(0, ((s.mean - s.min) / span) * 100)) : 50;
        return (
          <div key={`s-${s.column}`} className="fstat">
            <span className="fstat-col">{s.column}</span>
            <span className="fstat-mean">
              <span className="fstat-label">mean</span> <strong>{fmtValue(s.mean)}</strong>
              {s.unit && <span className="tile-unit"> {s.unit}</span>}
            </span>
            <span className="frange" aria-hidden="true">
              <i style={{ left: `${mean}%` }} />
            </span>
            <span className="frange-ends">
              <span>
                <span className="sr-only">min </span>
                {fmtValue(s.min)}
              </span>
              <span>
                <span className="sr-only">max </span>
                {fmtValue(s.max)}
              </span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function cell(v: string | number | null | undefined): string {
  if (v == null || v === "") return "–";
  if (typeof v === "number") return Number.isFinite(v) ? v.toLocaleString("en-US", { maximumFractionDigits: 6 }) : String(v);
  return v;
}

function FileTable({ name, table }: { name: string; table: NonNullable<FileView["table"]> }) {
  const { columns, rows, total_rows: total } = table;
  return (
    <div className="ftable-block">
      <div className="ftable-wrap" role="region" aria-label={`The first rows of ${name}`} tabIndex={0}>
        <table className="ftable">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.name} scope="col" className={c.type === "number" ? "n" : undefined}>
                  {c.name}
                  {c.unit && <span className="ftable-unit">{c.unit}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {columns.map((c, j) => (
                  <td key={c.name} className={`${c.type === "number" ? "n" : c.type === "date" ? "d" : ""}${r[j] == null || r[j] === "" ? " empty" : ""}`}>
                    {cell(r[j])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <span className="ftable-foot">
        Showing {rows.length.toLocaleString("en-US")} of {total.toLocaleString("en-US")} rows
        {rows.length < total ? ". Download the file for all of them." : ""}
      </span>
    </div>
  );
}

function ImageView({ name, url }: { name: string; url: string }) {
  const files = useFiles();
  const [broken, setBroken] = useState(false);
  if (broken) return <p className="fempty">The image couldn't be loaded.</p>;
  return (
    <button type="button" className="fimage" title="Open full size" aria-label={`Open ${name} full size`} onClick={() => files.showImage({ url, caption: name })}>
      <img src={url} alt={name} onError={() => setBroken(true)} />
    </button>
  );
}
