// The design's issues on the canvas: a compact panel that lists what goes wrong in the year (the
// part, what happens, when), the worst first. A row picks its part, centres the drawing on it and
// goes to its worst day; its header folds the list to a chip. The panel sits in a band of the
// canvas the fit keeps clear (PlantView reserves its measured size in the fit's padding), or
// under the drawing on a narrow canvas, so it never covers a part or a pipe at the fit.

import type { CSSProperties, Ref } from "react";

import type { Design } from "../../workbench";
import type { DesignIssue, IssueSeverity } from "./issues";
import { alertsByNode, issueCounts, issuesOf } from "./issues";

/** Where the panel sits: a side of the canvas it keeps clear, or under the drawing. */
export type IssuesPlacement = "right" | "left" | "top" | "below";

/** An issue's mark, never colour alone: a round "!" (demand not met), a triangle "!" (a warning),
 * an arrow to a bar (a part at its limit). */
export function SeverityIcon({ severity, limit = false, size = 16 }: { severity: IssueSeverity; limit?: boolean; size?: number }) {
  if (severity === "critical")
    return (
      <svg className="dz-sev is-critical" width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="7.2" fill="currentColor" />
        <path d="M8 4.1v4.8" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" />
        <circle cx="8" cy="11.6" r="1.1" fill="#fff" />
      </svg>
    );
  if (limit)
    return (
      <svg className="dz-sev is-warning" width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="7.2" fill="currentColor" />
        <path d="M4.6 4.4h6.8M8 12V6.6M5.6 9 8 6.6 10.4 9" fill="none" stroke="#3d2800" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  return (
    <svg className="dz-sev is-warning" width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 1.4c.5 0 .9.3 1.2.8l6 10.6c.5.9-.1 2-1.2 2H2c-1.1 0-1.7-1.1-1.2-2l6-10.6c.3-.5.7-.8 1.2-.8z" fill="currentColor" />
      <path d="M8 5.6v3.9" stroke="#3d2800" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="8" cy="11.9" r="1.05" fill="#3d2800" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="2" y="3.2" width="12" height="11" rx="2.2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2 6.8h12M5.4 1.8v2.6M10.6 1.8v2.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg className={`dz-issues-chev${open ? " open" : ""}`} width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface Props {
  issues: DesignIssue[];
  open: boolean;
  onToggle: () => void;
  /** The issue last picked (its row is pressed, and says why). */
  active: string | null;
  onPick: (issue: DesignIssue) => void;
  placement: IssuesPlacement;
  style?: CSSProperties;
  panelRef?: Ref<HTMLElement>;
}

export function IssuesPanel({ issues, open, onToggle, active, onPick, placement, style, panelRef }: Props) {
  const counts = issueCounts(issues);
  const worst: IssueSeverity = counts.critical ? "critical" : "warning";
  const summary = [
    counts.critical ? `${counts.critical} with demand not met` : "",
    counts.warning ? `${counts.warning} ${counts.warning === 1 ? "warning" : "warnings"}` : "",
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <section ref={panelRef} className={`dz-issues at-${placement} is-${worst}${open ? "" : " folded"}`} style={style} aria-label={`Issues in the year: ${summary}`}>
      <button type="button" className="dz-issues-head" aria-expanded={open} aria-controls="dz-issues-list" onClick={onToggle} title={open ? "Fold the issues" : "Show the issues"}>
        <SeverityIcon severity={worst} size={17} />
        <span className="dz-issues-title">{issues.length === 1 ? "1 issue" : `${issues.length} issues`}</span>
        <span className="dz-issues-counts" aria-hidden="true">
          {counts.critical > 0 && (
            <span className="dz-count is-critical" title="Demand not met">
              <SeverityIcon severity="critical" size={11} />
              {counts.critical}
            </span>
          )}
          {counts.warning > 0 && (
            <span className="dz-count is-warning" title="Warnings">
              <SeverityIcon severity="warning" size={11} />
              {counts.warning}
            </span>
          )}
        </span>
        <Chevron open={open} />
      </button>
      {open && (
        <ol id="dz-issues-list" className="dz-issues-list">
          {issues.map((i) => {
            const on = active === i.id;
            return (
              <li key={i.id}>
                <button type="button" className={`dz-issue is-${i.severity}${on ? " active" : ""}`} aria-pressed={on} onClick={() => onPick(i)} title={i.why || undefined}>
                  <SeverityIcon severity={i.severity} />
                  <span className="dz-issue-body">
                    <span className="dz-issue-top">
                      <strong>{i.unit}</strong>
                      {i.what_if && <span className="dz-issue-tag">what-if</span>}
                    </span>
                    <span className="dz-issue-what">{i.what}</span>
                    {i.when && (
                      <span className="dz-issue-when">
                        <CalendarIcon />
                        {i.when}
                      </span>
                    )}
                    {on && i.why && <span className="dz-issue-why">{i.why}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

/** A part's issues at the top of the inspector: what goes wrong on it, and when. */
export function NodeIssues({ design, nodeId }: { design: Design; nodeId: string }) {
  const alert = alertsByNode(issuesOf(design)).get(nodeId);
  if (!alert) return null;
  return (
    <ul className="dz-insp-issues" aria-label="Issues on it">
      {alert.issues.map((i) => {
        const own = i.units.includes(nodeId);
        const severity: IssueSeverity = own ? i.severity : "warning";
        return (
          <li key={i.id} className={`is-${severity}`}>
            <SeverityIcon severity={severity} limit={!own} size={15} />
            <span className="dz-issue-body">
              <span className="dz-issue-what">{own ? i.what : `At its limit while ${i.what.charAt(0).toLowerCase()}${i.what.slice(1)}`}</span>
              {(i.when || i.what_if) && (
                <span className="dz-issue-when">
                  <CalendarIcon />
                  {[i.when, i.what_if ? "a what-if" : ""].filter(Boolean).join(" · ")}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
