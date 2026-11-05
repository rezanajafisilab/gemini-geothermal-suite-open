// A JSON value as a tree you can fold, pretty-printed, with a copy button for the whole value.
// Objects and arrays open to `openDepth` levels; long strings are cut with a "show all".

import { useState } from "react";

import { Copy, Tick } from "../../components/Icons";

interface Props {
  /** "Arguments", "Result", "Metadata". */
  label: string;
  value: unknown;
  /** Levels open at first (default 1: the top level's members show, nested ones are folded). */
  openDepth?: number;
}

export function JsonView({ label, value, openDepth = 1 }: Props) {
  const [copied, setCopied] = useState(false);
  const text = toText(value);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked: the text is selectable */
    }
  };
  return (
    <div className="tr-json">
      <div className="tr-json-head">
        <span className="tr-json-label">{label}</span>
        <span className="tr-json-size">{sizeOf(value)}</span>
        <button type="button" className="tr-copy ta-btn ta-soft" onClick={copy} aria-label={`Copy ${label.toLowerCase()} as JSON`}>
          {copied ? <Tick size={13} color="#0F7A3D" /> : <Copy size={13} />}
          <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <div className="tr-json-body">
        <Node value={value} depth={0} openDepth={openDepth} last />
      </div>
    </div>
  );
}

function toText(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2) ?? String(value);
  } catch {
    return String(value);
  }
}

function sizeOf(value: unknown): string {
  if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? "" : "s"}`;
  if (value && typeof value === "object") {
    const n = Object.keys(value).length;
    return `${n} key${n === 1 ? "" : "s"}`;
  }
  return "";
}

const LONG = 220;

function Primitive({ value }: { value: unknown }) {
  const [all, setAll] = useState(false);
  if (value === null || value === undefined) return <span className="j-null">null</span>;
  if (typeof value === "number") return <span className="j-num">{String(value)}</span>;
  if (typeof value === "boolean") return <span className="j-bool">{String(value)}</span>;
  const s = String(value);
  if (s.length <= LONG || all) return <span className="j-str">{JSON.stringify(s)}</span>;
  return (
    <>
      <span className="j-str">{JSON.stringify(s.slice(0, LONG)).slice(0, -1)}…"</span>{" "}
      <button type="button" className="j-more" onClick={() => setAll(true)}>
        show all {s.length.toLocaleString("en-US")} characters
      </button>
    </>
  );
}

function Node({ name, value, depth, openDepth, last, inArray = false }: { name?: string; value: unknown; depth: number; openDepth: number; last: boolean; inArray?: boolean }) {
  const isObj = !!value && typeof value === "object";
  const entries: [string, unknown][] = isObj ? (Array.isArray(value) ? value.map((v, i) => [String(i), v] as [string, unknown]) : Object.entries(value as object)) : [];
  const [open, setOpen] = useState(depth < openDepth);
  const comma = last ? "" : ",";
  // Array members show without their index as a key.
  const keyEl = name !== undefined && !inArray && (
    <>
      <span className="j-key">{JSON.stringify(name)}</span>
      <span className="j-punc">: </span>
    </>
  );
  if (!isObj || !entries.length) {
    return (
      <div className="j-row" style={{ paddingLeft: depth * 14 }}>
        <span className="j-toggle-space" />
        {keyEl}
        {isObj ? <span className="j-punc">{Array.isArray(value) ? "[]" : "{}"}</span> : <Primitive value={value} />}
        <span className="j-punc">{comma}</span>
      </div>
    );
  }
  const [o, c] = Array.isArray(value) ? ["[", "]"] : ["{", "}"];
  return (
    <div>
      <div className="j-row" style={{ paddingLeft: depth * 14 }}>
        <button type="button" className="j-toggle" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={name ?? "value"}>
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" style={{ transform: `rotate(${open ? 90 : 0}deg)` }}>
            <path d="M3 1.8 6.6 5 3 8.2" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        {keyEl}
        <span className="j-punc">{o}</span>
        {!open && (
          <>
            <button type="button" className="j-fold" onClick={() => setOpen(true)}>
              {Array.isArray(value) ? `${entries.length} item${entries.length === 1 ? "" : "s"}` : preview(entries)}
            </button>
            <span className="j-punc">
              {c}
              {comma}
            </span>
          </>
        )}
      </div>
      {open && (
        <div>
          {entries.map(([k, v], i) => (
            <Node key={k} name={k} value={v} depth={depth + 1} openDepth={openDepth} last={i === entries.length - 1} inArray={Array.isArray(value)} />
          ))}
          <div className="j-row" style={{ paddingLeft: depth * 14 }}>
            <span className="j-toggle-space" />
            <span className="j-punc">
              {c}
              {comma}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/** The first keys of a folded object: "code, name, depth_m …". */
function preview(entries: [string, unknown][]): string {
  const keys = entries.slice(0, 3).map(([k]) => k);
  return `${keys.join(", ")}${entries.length > 3 ? ` … ${entries.length} keys` : ""}`;
}
