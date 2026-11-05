// What to vary: the server's catalogue as chips grouped by subsurface, demand, prices and costs
// (and any group the server adds, by its name; click to add or remove), then one row per picked
// parameter with its range typed in its own unit (a change, a scale or a value), the catalogue's
// range one click away, and a short description. A picked chip wears its spider colour, so the
// picker and the chart read together.

import { useId } from "react";

import { Cross, Plus, Tick } from "../../components/Icons";
import type { SensParam } from "../../workbench";
import { slotColor } from "./colors";
import { displayUnit, fmtParam, isDefaultRange, kindTag, kindText, newRow, paramGroups, rowError, toggleRow, type ParamRow } from "./params";

interface Props {
  catalogue: SensParam[];
  rows: ParamRow[];
  slots: Record<string, number>;
  onRows: (rows: ParamRow[]) => void;
}

function RangeRow({ p, row, color, onChange, onRemove }: { p: SensParam; row: ParamRow; color: string; onChange: (r: ParamRow) => void; onRemove: () => void }) {
  const id = useId();
  const err = rowError(row);
  const unit = displayUnit(p);
  const changed = !isDefaultRange(p, row);
  return (
    <li className={`sen-row${err ? " is-invalid" : ""}`}>
      <span className="sen-row-head">
        <i className="sen-row-dot" style={{ background: color }} aria-hidden="true" />
        <span className="sen-row-name" id={`${id}-name`}>
          {p.label}
        </span>
        <span className="sen-kind" title={kindText(p)}>
          {kindTag(p)}
        </span>
      </span>
      <span className="sen-row-range" role="group" aria-labelledby={`${id}-name`}>
        <label className="sen-num">
          <span className="sen-num-cap">low</span>
          <input
            type="text"
            inputMode="decimal"
            value={row.low}
            aria-label={`${p.label}, low end${unit ? ` in ${unit}` : ""}`}
            aria-invalid={!!err}
            aria-describedby={err ? `${id}-err` : `${id}-desc`}
            onChange={(e) => onChange({ ...row, low: e.target.value })}
          />
        </label>
        <span className="sen-to" aria-hidden="true">
          to
        </span>
        <label className="sen-num">
          <span className="sen-num-cap">high</span>
          <input
            type="text"
            inputMode="decimal"
            value={row.high}
            aria-label={`${p.label}, high end${unit ? ` in ${unit}` : ""}`}
            aria-invalid={!!err}
            aria-describedby={err ? `${id}-err` : `${id}-desc`}
            onChange={(e) => onChange({ ...row, high: e.target.value })}
          />
        </label>
        <span className="sen-unit">{unit}</span>
      </span>
      <span className="sen-row-actions">
        {changed && (
          <button type="button" className="link-btn" onClick={() => onChange(newRow(p))} title={`Back to ${fmtParam(p, p.low)} to ${fmtParam(p, p.high)}`}>
            Reset
          </button>
        )}
        <button type="button" className="sen-remove ta-btn" aria-label={`Remove ${p.label}`} title="Remove" onClick={onRemove}>
          <Cross size={10} />
        </button>
      </span>
      {err ? (
        <span className="sen-row-err" id={`${id}-err`} role="alert">
          {err}
        </span>
      ) : (
        <span className="sen-row-desc" id={`${id}-desc`}>
          {p.description}
          {p.description ? "; " : ""}
          {kindText(p)}.
        </span>
      )}
    </li>
  );
}

export function ParameterPicker({ catalogue, rows, slots, onRows }: Props) {
  const picked = new Set(rows.map((r) => r.key));
  // Groups the client doesn't know yet still show, under their own name.
  const groups = paramGroups(catalogue);
  const byKey = new Map(catalogue.map((p) => [p.key, p]));

  return (
    <div className="sen-picker">
      <div className="sen-groups">
        {groups.map((g) => (
          <div key={g.label} className="sen-group" role="group" aria-label={g.label}>
            <span className="sen-group-cap">{g.label}</span>
            <span className="sen-chips">
              {g.params.map((p) => {
                const on = picked.has(p.key);
                return (
                  <button
                    key={p.key}
                    type="button"
                    className={`sen-chip ta-btn${on ? " is-on" : ""}`}
                    aria-pressed={on}
                    title={`${p.description}. Default range ${fmtParam(p, p.low)} to ${fmtParam(p, p.high)}`}
                    onClick={() => onRows(toggleRow(rows, p))}
                  >
                    {on ? (
                      <span className="sen-chip-mark" style={{ background: slotColor(slots[p.key]) }} aria-hidden="true">
                        <Tick size={10} color="#fff" />
                      </span>
                    ) : (
                      <span className="sen-chip-mark is-add" aria-hidden="true">
                        <Plus size={11} />
                      </span>
                    )}
                    {p.label}
                  </button>
                );
              })}
            </span>
          </div>
        ))}
      </div>
      {rows.length ? (
        <ul className="sen-rows" aria-label="Parameters to vary">
          {rows.map((row) => {
            const p = byKey.get(row.key);
            if (!p) return null;
            return (
              <RangeRow
                key={row.key}
                p={p}
                row={row}
                color={slotColor(slots[row.key])}
                onChange={(r) => onRows(rows.map((x) => (x.key === r.key ? r : x)))}
                onRemove={() => onRows(rows.filter((x) => x.key !== row.key))}
              />
            );
          })}
        </ul>
      ) : (
        <p className="sen-note">Pick at least one parameter above to vary.</p>
      )}
    </div>
  );
}
