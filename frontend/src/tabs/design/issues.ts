// A design's issues on its drawing: which parts glow, how badly, and why (gemini_agent.issues
// gives each issue the Graph node ids it concerns). A part named by an issue takes the issue's
// severity (red: demand not met; amber: a warning); a part that only ran flat out on its days (at
// its limit) is amber. A part named by several takes the worst. Parts not on the drawing are left
// out (the issue is still listed).

import type { Design, DesignIssue, IssueSeverity } from "../../workbench";

export type { DesignIssue, IssueSeverity };

/** One part's alert: the worst severity, and every issue that names it. */
export interface NodeAlert {
  severity: IssueSeverity;
  issues: DesignIssue[];
  /** Named only as at its limit (no issue falls on it as such). */
  limitOnly: boolean;
}

const RANK: Record<IssueSeverity, number> = { critical: 0, warning: 1 };

/** The design's issues, the worst first (none from an older server). */
export function issuesOf(design: Pick<Design, "issues">): DesignIssue[] {
  const list = Array.isArray(design.issues) ? design.issues.filter((i) => i && Array.isArray(i.units)) : [];
  return [...list].sort((a, b) => RANK[a.severity] - RANK[b.severity] || Number(a.what_if) - Number(b.what_if) || (a.first ?? 999) - (b.first ?? 999));
}

/**
 * Each drawn part's alert: the worst severity of the issues that name it (`units`), amber for a
 * part only at its limit (`limit`). `drawn` is the drawing's node ids: ids not on it are skipped.
 */
export function alertsByNode(issues: DesignIssue[], drawn?: Iterable<string>): Map<string, NodeAlert> {
  const on = drawn ? new Set(drawn) : null;
  const out = new Map<string, NodeAlert>();
  const put = (id: string, issue: DesignIssue, severity: IssueSeverity, limit: boolean) => {
    if (on && !on.has(id)) return;
    const was = out.get(id);
    if (!was) {
      out.set(id, { severity, issues: [issue], limitOnly: limit });
      return;
    }
    if (!was.issues.includes(issue)) was.issues.push(issue);
    if (RANK[severity] < RANK[was.severity]) was.severity = severity;
    was.limitOnly = was.limitOnly && limit;
  };
  for (const issue of issues) {
    for (const id of issue.units) put(id, issue, issue.severity, false);
    for (const id of issue.limit ?? []) if (!issue.units.includes(id)) put(id, issue, "warning", true);
  }
  return out;
}

/** The drawn parts an issue concerns (its units, then those at their limit): what a click centres on. */
export function issueTargets(issue: DesignIssue, drawn?: Iterable<string>): string[] {
  const on = drawn ? new Set(drawn) : null;
  const ids = [...issue.units, ...(issue.limit ?? [])].filter((id, k, all) => all.indexOf(id) === k);
  return on ? ids.filter((id) => on.has(id)) : ids;
}

/** The part a click picks: the issue's first drawn unit (null when none is drawn). */
export function issueUnit(issue: DesignIssue, drawn?: Iterable<string>): string | null {
  const on = drawn ? new Set(drawn) : null;
  return issue.units.find((id) => !on || on.has(id)) ?? null;
}

/** The day (1-based, as the year player counts) a click goes to; null when the drawing would not
 * show it (a what-if, or a cap broken over the whole year). */
export function issueDay(issue: DesignIssue): number | null {
  if (issue.what_if) return null;
  const d = issue.day ?? issue.first;
  return d == null || !Number.isFinite(d) ? null : Math.min(365, Math.max(1, Math.round(d) + 1));
}

/** How many issues of each severity. */
export function issueCounts(issues: DesignIssue[]): Record<IssueSeverity, number> {
  return {
    critical: issues.filter((i) => i.severity === "critical").length,
    warning: issues.filter((i) => i.severity === "warning").length,
  };
}

/** A part's alert in words (its badge's label and tooltip). */
export function alertWords(alert: NodeAlert, id?: string): string {
  const lines = alert.issues.map((i) => {
    const own = id == null || i.units.includes(id);
    const what = own ? i.what : `at its limit while ${i.what.charAt(0).toLowerCase()}${i.what.slice(1)}`;
    return `${what}${i.when ? ` (${i.when})` : ""}${i.what_if ? ", a what-if" : ""}`;
  });
  const text = lines.join("; ");
  if (alert.limitOnly) return text.charAt(0).toUpperCase() + text.slice(1);
  return `${alert.severity === "critical" ? "Demand not met" : "Warning"}: ${text}`;
}
