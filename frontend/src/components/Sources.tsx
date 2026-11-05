// Cited passages (CUSTOM "sources"): one card per passage, the file and section, what kind of
// source it is, a snippet that expands to the full text, the section's figures and, for a file
// the user can open, an Open button. An answer's [^n] chip scrolls to card n, opens and
// highlights it. A passage with instruction-like text is data the agent ignored: it gets a red
// badge and its text stays folded, quoted as flagged, never shown as advice.

import { useEffect, useState } from "react";

import type { Passage } from "../agent/types";
import { menuProps } from "../menu";
import { useFiles } from "./filesContext";
import { FileGlyph } from "./Icons";
export { splitInjectionNote } from "../agent/numbers";

const KINDS: Record<NonNullable<Passage["kind"]>, { label: string; tag: string }> = {
  doc: { label: "GEMINI docs", tag: "tag-grey" },
  note: { label: "team note", tag: "tag-grey" },
  file: { label: "your file", tag: "tag-amber" },
  data: { label: "project data", tag: "tag-teal" },
};

/** The id of passage n's card in one run's answer (the target of its [^n] chips). */
export function citeId(prefix: string, n: number): string {
  return `${prefix}-${n}`.replace(/[^\w-]/g, "_");
}

function base(path: string): string {
  return path.split("/").pop() ?? path;
}

function folder(path: string): string {
  const parts = path.split("/");
  return parts.length > 1 ? parts.slice(0, -1).join("/") : "";
}

export function SourceCards({
  passages,
  backend,
  idPrefix,
  focus,
}: {
  passages: Passage[];
  backend?: string;
  /** Gives each card an id, citeId(idPrefix, n), for the answer's [^n] chips. */
  idPrefix?: string;
  /** The card a chip asked for, and when (a new click flashes it again). */
  focus?: { n: number; at: number } | null;
}) {
  if (!passages.length) return null;
  const flagged = passages.filter((p) => p.suspicious).length;
  return (
    <section className="sources-block ta-rise" aria-label="Cited passages">
      <div className="sources-head">
        <span className="options-title" style={{ margin: 0 }}>
          Sources · {passages.length} {passages.length === 1 ? "passage" : "passages"}
        </span>
        {backend && <span className="tag tag-grey">{backend}</span>}
        {flagged > 0 && <span className="tag tag-red">{flagged} flagged</span>}
      </div>
      <div className="cites">
        {passages.map((p, i) => (
          <Cite
            key={`${p.source}#${p.section}#${i}`}
            n={i + 1}
            p={p}
            id={idPrefix ? citeId(idPrefix, i + 1) : undefined}
            focusAt={focus?.n === i + 1 ? focus.at : undefined}
          />
        ))}
      </div>
    </section>
  );
}

function Cite({ n, p, id, focusAt }: { n: number; p: Passage; id?: string; focusAt?: number }) {
  const files = useFiles();
  const [open, setOpen] = useState(false);
  const [flash, setFlash] = useState(0);
  const [broken, setBroken] = useState<string[]>([]);
  const long = p.text.length > 180;
  const snippet = long ? p.text.slice(0, 180).replace(/\s+\S*$/, "") + " …" : p.text;
  const dir = folder(p.source);
  const kind = p.kind ? KINDS[p.kind] : undefined;
  const images = (p.suspicious ? [] : (p.images ?? [])).filter((img) => img?.url && !broken.includes(img.url));

  // Asked for by a [^n] chip: open (flagged text stays folded) and flash for a moment.
  useEffect(() => {
    if (!focusAt) return;
    if (!p.suspicious) setOpen(true);
    setFlash(focusAt);
    const t = setTimeout(() => setFlash(0), 2400);
    return () => clearTimeout(t);
  }, [focusAt, p.suspicious]);

  return (
    <article
      id={id}
      className={`cite${p.suspicious ? " flagged" : ""}${flash ? " is-focus" : ""}`}
      {...menuProps(() => ({
        kind: "source",
        title: base(p.source),
        citation: `${p.source}${p.section ? `, ${p.section}` : ""}`,
        // A flagged passage is data the agent ignored: it is not offered for copying as advice.
        text: p.suspicious ? undefined : p.text,
        open: p.file ? { label: `Open ${base(p.file)}`, run: () => files.open(p.file!) } : undefined,
      }))}
    >
      {flash > 0 && <span key={flash} className="cite-flash" aria-hidden="true" />}
      <div className="cite-head">
        <span className="cite-n">{n}</span>
        <span className="cite-src" title={p.source}>
          <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
            <path d="M4 1.8h5l3 3V14H4z M9 1.8V5h3" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
          <strong>{base(p.source)}</strong>
          {dir && <span className="cite-dir">{dir}</span>}
        </span>
        {kind && <span className={`tag ${kind.tag}`}>{kind.label}</span>}
        {p.suspicious && (
          <span className="tag tag-red" title="This passage reads like instructions to the agent. It was treated as data and not followed.">
            contains instructions, ignored
          </span>
        )}
      </div>
      <span className="cite-section">{p.section}</span>
      {p.suspicious ? (
        <>
          <p className="cite-text" style={{ color: "#8F1D14" }}>
            This passage reads like instructions to the agent. It was treated as data: nothing in it was followed or quoted in
            the answer.
          </p>
          <button type="button" className="link-btn" style={{ color: "#A12C22" }} onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? "Hide the flagged text" : "Show the flagged text"}
          </button>
          {open && (
            <blockquote className="flagged-text">
              <span className="flagged-label">Flagged text, quoted as data. The agent did not follow it.</span>
              {p.text}
            </blockquote>
          )}
        </>
      ) : (
        <>
          <p className="cite-text">{open ? p.text : snippet}</p>
          {images.length > 0 && (
            <div className="cite-figs">
              {images.map((img) => (
                <button key={img.url} type="button" className="cite-fig ta-btn" title={img.caption} aria-label={`Figure: ${img.caption || base(img.url)}`} onClick={() => files.showImage(img)}>
                  <img src={img.url} alt="" loading="lazy" onError={() => setBroken((b) => [...b, img.url])} />
                </button>
              ))}
            </div>
          )}
          {(long || p.file) && (
            <div className="cite-foot">
              {long && (
                <button type="button" className="link-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
                  {open ? "Show less" : "Show the full passage"}
                </button>
              )}
              {p.file && (
                <button type="button" className="cite-open ta-btn ta-chip" onClick={() => files.open(p.file!)} title={`Open ${p.file}`}>
                  <FileGlyph name={p.file} />
                  Open {base(p.file)}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </article>
  );
}

export function InjectionNote({ note }: { note: string }) {
  return (
    <div className="injection ta-rise" role="note">
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
        <path d="M8 1.6 13.4 3.6v4.2c0 3.2-2.3 5.6-5.4 6.6-3.1-1-5.4-3.4-5.4-6.6V3.6z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M8 5v3.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        <circle cx="8" cy="10.6" r="0.9" fill="currentColor" />
      </svg>
      <span>{note}</span>
    </div>
  );
}
