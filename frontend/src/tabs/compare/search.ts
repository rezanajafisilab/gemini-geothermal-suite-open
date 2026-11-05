// The chat's design searches (S1, S2 …), newest first, with when each ran; and whether the
// newest search's gas baseline is priced like the designs now (the Economics tab draws it only
// then). The Compare tab's library (library.ts) lists the searches' candidates themselves.

import type { Attempt, Candidate, Workbench } from "../../workbench";
import { lcoeOf } from "../economics/model";

const close = (a: number | null | undefined, b: number | null | undefined, tol: number) => a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a - b) <= tol;

/**
 * Whether the search's candidates (and its gas baseline) are priced like the designs now. The
 * server prices them once, when the search runs, while every design follows the assumptions as
 * they change. "stale" when the chosen candidate no longer costs what the chosen design costs now,
 * or the baseline's capital is not what the designs are measured against now; "current" when
 * both hold; "unknown" with nothing to compare. A change that only touches units neither the
 * chosen design nor the gas plant has (a heat pump's price, say) can't be seen this way.
 */
export function searchPricing(wb: Pick<Workbench, "designs" | "candidates" | "reference"> | null | undefined): "current" | "stale" | "unknown" {
  const chosen = wb?.candidates?.find((c) => c.role === "chosen");
  const design = chosen && wb?.designs.find((d) => d.code === chosen.code && d.origin === "agent" && !d.reservoir_delta_c);
  // The gas plant's capital now, from what each design costs more than it.
  const gasCapex = (wb?.designs ?? [])
    .map((d) => (d.economics?.versus_reference ? d.economics.capex_meur - d.economics.versus_reference.extra_capex_meur : null))
    .filter((v): v is number => v != null && Number.isFinite(v));
  if (wb?.reference && gasCapex.some((v) => !close(v, wb.reference?.capex_meur, 0.02))) return "stale";
  if (!chosen || !design) return "unknown";
  const same = close(chosen.lcoe, lcoeOf(design), 0.05) && close(chosen.lcoh, design.economics?.lcoh, 0.05) && close(chosen.capex_meur, design.economics?.capex_meur, 0.01);
  return same ? "current" : "stale";
}

/** The gas baseline, when it is priced like the designs (or nothing says it isn't). */
export function currentBaseline(wb: Pick<Workbench, "designs" | "candidates" | "reference"> | null | undefined): Candidate | null {
  return wb?.reference && searchPricing(wb) !== "stale" ? wb.reference : null;
}

// ------------------------------------------------------------------ attempts

/**
 * The chat's design searches, newest first. A server without attempts has only the last search's
 * candidates at the top level: those count as the one attempt, so the tab works the same either way.
 */
export function attemptsOf(wb: Pick<Workbench, "attempts" | "candidates" | "reference"> | null | undefined): Attempt[] {
  if (wb?.attempts?.length) return [...wb.attempts].sort((a, b) => b.n - a.n);
  if (!wb?.candidates?.length) return [];
  const chosen = wb.candidates.find((c) => c.role === "chosen")?.code ?? null;
  return [{ id: "S1", n: 1, at: null, message: "", label: "", objective: "cost", chosen, repriced: true, candidates: wb.candidates, reference: wb.reference ?? null }];
}

export interface TimeOpts {
  /** The user's locale and time zone by default; tests fix them. */
  locale?: string;
  timeZone?: string;
  /** "Now", for telling today from another day. */
  now?: number;
}

/** When an attempt ran, short: "16:40" today, "29 Oct, 16:40" on another day; "" when unknown. */
export function attemptTime(at: number | null | undefined, { locale, timeZone, now = Date.now() }: TimeOpts = {}): string {
  if (at == null || !Number.isFinite(at)) return "";
  const d = new Date(at * 1000);
  const time = d.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit", timeZone });
  const day = (x: Date) => x.toLocaleDateString(locale, { timeZone });
  return day(d) === day(new Date(now)) ? time : `${d.toLocaleDateString(locale, { day: "numeric", month: "short", timeZone })}, ${time}`;
}

/** "Search 2 · 16:40 · lowest CO₂ · 1 doublet · 3,000 m": the switcher's label for an attempt. */
export function attemptLabel(a: Attempt, opts: TimeOpts = {}): string {
  return [`Search ${a.n}`, attemptTime(a.at, opts), a.label].filter(Boolean).join(" · ");
}
