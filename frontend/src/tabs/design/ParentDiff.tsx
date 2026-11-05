// A design made from another (your edit, or a what-if) against the design it came from: cost of
// heat, heat covered, CO₂ saving and capital, with arrows that say better or worse. Your own
// designs can be deleted here.

import { useState } from "react";

import { Spinner } from "../../components/Icons";
import { fmtNum, useWorkbench, type Design } from "../../workbench";
import { forget } from "./remember";
import { diffRows, type DiffRow } from "./plant";

function Arrow({ dir }: { dir: "up" | "down" | "flat" }) {
  if (dir === "flat")
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <path d="M2 6h8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" style={{ transform: dir === "down" ? "rotate(180deg)" : undefined }}>
      <path d="M6 10V2.5M2.8 5.5 6 2.3l3.2 3.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Row({ row }: { row: DiffRow }) {
  const { before, after } = row;
  if (before == null || after == null) return null;
  const delta = after - before;
  const flat = Math.abs(delta) < (row.pct ? 0.05 : Math.max(0.005, Math.abs(before) * 0.001));
  const better = !flat && Math.sign(delta) === row.good;
  const tone = flat ? "flat" : better ? "better" : "worse";
  const unit = row.unit === "%" ? "%" : ` ${row.unit}`;
  const d = `${delta > 0 ? "+" : "−"}${fmtNum(Math.abs(delta))}${row.pct ? " pt" : unit}`;
  return (
    <li className={`dz-diff-row ${tone}`}>
      <span className="dz-diff-label">{row.label}</span>
      <span className="dz-diff-vals">
        <span className="dz-diff-before">
          {fmtNum(before)}
          {unit}
        </span>
        <span aria-hidden="true">→</span>
        <strong>
          {fmtNum(after)}
          {unit}
        </strong>
      </span>
      <span className="dz-diff-delta">
        <Arrow dir={flat ? "flat" : delta > 0 ? "up" : "down"} />
        {flat ? "same" : d}
        <span className="sr-only">{flat ? "" : better ? ", better" : ", worse"}</span>
      </span>
    </li>
  );
}

export function ParentDiff({ design, threadId }: { design: Design; threadId: string | null }) {
  const wb = useWorkbench();
  const parent = design.parent ? wb.designs.find((d) => d.id === design.parent) : null;
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!parent) return null;
  const mine = design.origin === "user";

  const remove = async () => {
    setBusy(true);
    setError(null);
    const res = await wb.removeDesign(design.id);
    setBusy(false);
    if (!res.ok) {
      setError(res.offline ? "The agent server isn't answering." : res.message);
      return;
    }
    forget(`${threadId}/${design.id}`);
    wb.select(parent.id);
  };

  return (
    <section className="dz-diff ta-rise" aria-label={`${design.code} against ${parent.code}`}>
      <div className="dz-diff-head">
        <span className="dz-diff-title">
          <span className="wb-code small">{design.code}</span>
          <span>
            against <button type="button" className="link-btn" onClick={() => wb.select(parent.id)}>{parent.code} {parent.name}</button>
            {mine ? ", the design you edited" : design.origin === "what_if" ? ", before the what-if" : ""}
          </span>
        </span>
        {mine &&
          (confirm ? (
            <span className="dz-diff-confirm">
              <span>Delete {design.code}?</span>
              <button type="button" className="btn btn-soft ta-btn ta-soft dz-btn-sm dz-danger" onClick={() => void remove()} disabled={busy}>
                {busy && <Spinner size={14} />}
                Delete
              </button>
              <button type="button" className="btn btn-soft ta-btn ta-soft dz-btn-sm" onClick={() => setConfirm(false)} disabled={busy}>
                Keep
              </button>
            </span>
          ) : (
            <button type="button" className="link-btn dz-link-danger" onClick={() => setConfirm(true)}>
              Delete this design
            </button>
          ))}
      </div>
      <ul className="dz-diff-rows">
        {diffRows(parent, design).map((r) => (
          <Row key={r.key} row={r} />
        ))}
      </ul>
      {error && (
        <p role="alert" className="dz-error">
          {error}
        </p>
      )}
    </section>
  );
}
