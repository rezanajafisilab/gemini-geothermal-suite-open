// Every design of the conversation as one list, for the design picker, the chat's designs strip
// and the composer's @ list: each with its handle (A1), what it is in words (or the user's name),
// its star, its run, and whether the tabs have it already. Grouped for people: the shortlist (the
// stars), the latest run's picks, what-ifs, the user's designs; a search finds any design of any
// run, grouped by run.

import type { Design, LibraryRow, Workbench } from "./types";

export interface DesignItem {
  id: string;
  /** "A1", "W1", "U1" (older designs: their code). */
  uid: string;
  code: string;
  /** What it is in words ("Best overall", "A1 + 50 °C heating return"), or the user's name. */
  label: string;
  /** The longer description ("1 doublet at 2,500 m, heat pump top-up …"). */
  name: string;
  userName: string | null;
  starred: boolean;
  origin: "agent" | "what_if" | "user" | string;
  picks: string[];
  recommended: boolean;
  inTabs: boolean;
  verified: boolean;
  /** The names of the checks it fails (the verifier's), for its status in words. */
  failed: string[];
  /** Cost of heat and cold together, €/MWh, and the CO₂ saving against gas, %. */
  lcoe: number | null;
  co2SavingPct: number | null;
  /** The search it came from: "S2", its letter and name ("Run B · What-if: …"), and its number. */
  run: { id: string; letter: string; name: string; n: number } | null;
}

export interface DesignSection {
  key: string;
  title: string;
  items: DesignItem[];
}

const fromRow = (r: LibraryRow): DesignItem => ({
  id: r.id,
  uid: r.uid || r.code,
  code: r.code,
  label: r.label || r.name,
  name: r.name,
  userName: r.user_name ?? null,
  starred: !!r.starred,
  origin: r.origin,
  picks: r.picks ?? [],
  recommended: r.recommended,
  inTabs: r.in_tabs,
  verified: r.verified,
  failed: r.failed ?? [],
  lcoe: r.lcoe,
  co2SavingPct: r.co2_saving_pct,
  run: r.scenario && r.scenario.n > 0 ? { id: r.scenario.id, letter: r.scenario.letter ?? "", name: r.scenario.name ?? r.scenario.label, n: r.scenario.n } : null,
});

const fromDesign = (d: Design): DesignItem => ({
  id: d.id,
  uid: d.uid || d.code,
  code: d.code,
  label: d.label || d.name,
  name: d.name,
  userName: d.user_name ?? null,
  starred: !!d.starred,
  origin: d.origin,
  picks: d.picks ?? [],
  recommended: !!d.chosen,
  inTabs: true,
  verified: d.verified,
  failed: d.checks.filter((c) => !c.passed).map((c) => c.name),
  lcoe: d.economics?.lcoe ?? null,
  co2SavingPct: d.economics?.co2_saving_pct ?? null,
  run: null,
});

/** Every design: the library's rows (all runs), with the tabs' own designs it lacks. */
export function designItems(wb: Pick<Workbench, "designs" | "library"> | null | undefined): DesignItem[] {
  if (!wb) return [];
  const rows = (wb.library ?? []).filter((r) => !/^REF\b/.test(r.uid ?? "") && r.role !== "failed").map(fromRow);
  const known = new Set(rows.map((r) => r.id));
  return [...rows, ...wb.designs.filter((d) => !known.has(d.id)).map(fromDesign)];
}

/** The handle and the words: "A1 · Best overall". */
export const itemText = (i: Pick<DesignItem, "uid" | "label">) => (i.label && i.label !== i.uid ? `${i.uid} · ${i.label}` : i.uid);

/** Whether an item matches what was typed: every word in its handle, words, code or description. */
export function matches(i: DesignItem, query: string): boolean {
  const hay = `${i.uid} ${i.label} ${i.userName ?? ""} ${i.code} ${i.name} ${i.run?.name ?? ""}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => hay.includes(w.replace(/^@/, "")));
}

/**
 * The list in sections. Without a query: the shortlist, the latest run's picks (and the current
 * design), what-ifs, the user's designs, the others already in the tabs. With one: every match,
 * grouped by run, then what-ifs and the user's designs. A design shows once, in its first section.
 */
export function designSections(items: DesignItem[], query = "", limit = 40): DesignSection[] {
  const q = query.trim();
  const seen = new Set<string>();
  const take = (key: string, title: string, list: DesignItem[]): DesignSection | null => {
    const fresh = list.filter((i) => !seen.has(i.id));
    fresh.forEach((i) => seen.add(i.id));
    return fresh.length ? { key, title, items: fresh } : null;
  };
  if (q) {
    // The cheapest first (cost of heat and cold); designs without a figure last.
    const hits = items
      .filter((i) => matches(i, q))
      .sort((a, b) => (a.lcoe ?? Infinity) - (b.lcoe ?? Infinity))
      .slice(0, limit);
    const runs = [...new Map(hits.filter((i) => i.run).map((i) => [i.run!.id, i.run!])).values()].sort((a, b) => b.n - a.n);
    return [
      ...runs.map((r) => take(`run-${r.id}`, r.name, hits.filter((i) => i.run?.id === r.id && i.origin === "agent"))),
      take("what-ifs", "What-ifs", hits.filter((i) => i.origin === "what_if")),
      take("yours", "Your designs", hits.filter((i) => i.origin === "user")),
      take("other", "Other designs", hits),
    ].filter((s): s is DesignSection => !!s);
  }
  const latest = items.reduce<DesignItem["run"]>((best, i) => (i.run && (!best || i.run.n > best.n) ? i.run : best), null);
  return [
    take("starred", "Shortlist", items.filter((i) => i.starred)),
    take(
      "latest",
      latest ? `${latest.name}: its picks` : "The picks",
      items.filter((i) => i.recommended || (i.origin === "agent" && i.picks.length > 0 && (!latest || i.run?.id === latest.id))),
    ),
    take("what-ifs", "What-ifs", items.filter((i) => i.origin === "what_if")),
    take("yours", "Your designs", items.filter((i) => i.origin === "user")),
    take("tabs", "Also in the tabs", items.filter((i) => i.inTabs)),
  ].filter((s): s is DesignSection => !!s);
}
