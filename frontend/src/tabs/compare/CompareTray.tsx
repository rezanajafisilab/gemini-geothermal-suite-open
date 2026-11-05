// The tray: sticks to the bottom of the page while designs are ticked. Four slots with the
// ticked names (each can be unticked), a note when they come from different scenarios, and
// "Compare side by side" (two or more).

import { Cross } from "../../components/Icons";
import type { LibraryRow } from "../../workbench";
import { designLabel } from "./bits";
import { MAX_SELECTED } from "./library";

interface Props {
  rows: LibraryRow[];
  /** The ticked designs come from different scenarios. */
  mixed: boolean;
  /** A short message (a fifth design refused). */
  notice: string | null;
  open: boolean;
  onRemove: (id: string) => void;
  onClear: () => void;
  onCompare: () => void;
}

export function CompareTray({ rows, mixed, notice, open, onRemove, onClear, onCompare }: Props) {
  if (!rows.length) return null;
  const empty = Math.max(0, MAX_SELECTED - rows.length);
  return (
    <div className="lib-tray" role="region" aria-label="Designs ticked to compare">
      <span className="lib-tray-cap">
        <strong>{rows.length}</strong> of {MAX_SELECTED} ticked
      </span>
      <ul className="lib-tray-list">
        {rows.map((r) => (
          <li key={r.id} className={`lib-tray-item${r.recommended ? " is-rec" : ""}`}>
            {r.uid && <span className="uid-chip small">{r.uid}</span>}
            <span className="lib-code">{r.code}</span>
            <button type="button" className="lib-icon-btn small" onClick={() => onRemove(r.id)} aria-label={`Untick ${designLabel(r)}`}>
              <Cross size={8} />
            </button>
          </li>
        ))}
        {Array.from({ length: empty }, (_, i) => (
          <li key={`empty${i}`} className="lib-tray-slot" aria-hidden="true" />
        ))}
      </ul>
      <span className="lib-tray-note" role="status">
        {notice ?? (mixed ? "Different scenarios: not ranked" : rows.length < 2 ? "Tick one more to compare" : "")}
      </span>
      <button type="button" className="link-btn lib-tray-clear" onClick={onClear}>
        Clear
      </button>
      <button type="button" className="btn btn-ink ta-btn ta-ink lib-tray-go" disabled={rows.length < 2} onClick={onCompare}>
        {open ? "Show side by side" : "Compare side by side"}
      </button>
    </div>
  );
}
