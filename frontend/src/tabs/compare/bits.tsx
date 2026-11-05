// Small pieces the library's table, side by side and tray share: the design's name, its
// scenario chip, its pick tags, its one-unit-out badge, "vs gas", and the links into the
// one-design tabs (a design not yet in them is opened first).

import { hrefFor } from "../../workbench/route";
import type { LibraryRow } from "../../workbench";
import { KIND_WORD, PICK_LABEL, PICK_RULE, fmtVsGas, finite, isValid, picksOf, reliabilityText, scenarioShort, worstText } from "./library";

export const KIND_CLASS: Record<string, string> = { base: "is-base", what_if: "is-whatif", search: "is-search", user: "is-user", all: "is-all" };

/** "A1 · 1D-HP-EC-N1": the name first, then the code (just the code when there is no name). */
export function designLabel(r: Pick<LibraryRow, "uid" | "code" | "id">): string {
  return r.uid ? `${r.uid} · ${r.code}` : r.id;
}

export function DesignName({ r, small = true }: { r: LibraryRow; small?: boolean }) {
  return (
    <span className="lib-design">
      {r.uid && <span className={`uid-chip${small ? " small" : ""}`}>{r.uid}</span>}
      <span className="lib-code">{r.code}</span>
    </span>
  );
}

/** The scenario a design's figures come from, coloured by kind. */
export function ScenarioChip({ r }: { r: LibraryRow }) {
  const kind = r.scenario.kind;
  const text = scenarioShort(r.scenario);
  return (
    <span className={`lib-scn-chip ${KIND_CLASS[kind] ?? ""}`} title={`Scenario: ${text}`}>
      <span className="lib-scn-chip-kind">{KIND_WORD[kind] ?? kind}</span>
      {kind !== "base" && kind !== "user" && <span className="lib-scn-chip-text">{text}</span>}
    </span>
  );
}

/** The search's picks this design is, each with its rule on hover; scoped by the scenario chip beside it. */
export function PickTags({ r }: { r: LibraryRow }) {
  const picks = picksOf(r);
  if (!picks.length) return null;
  return (
    <span className="lib-picks">
      {picks.map((p) => (
        <span key={p} className={`lib-pick is-${p}`} title={`${PICK_LABEL[p]} of its search: ${PICK_RULE[p]}`}>
          {PICK_LABEL[p]}
        </span>
      ))}
    </span>
  );
}

/** "N-1 ✓" in green, "5 of 6 short" in amber; the worst case on hover. */
export function ReliabilityBadge({ r }: { r: LibraryRow }) {
  const f = r.firm;
  if (!f || !f.cases) return <span className="lib-muted">–</span>;
  const worst = worstText(f);
  if (f.short === 0)
    return (
      <span className="lib-n1 is-met" title={`Any one unit can be out and every day is still met (${f.cases} cases)`}>
        N-1 <span aria-hidden="true">✓</span>
        <span className="sr-only">met</span>
      </span>
    );
  return (
    <span className="lib-n1 is-short" title={`${reliabilityText(f)}${worst ? `; worst: ${worst}` : ""}`}>
      {f.short} of {f.cases} short
    </span>
  );
}

/** "−17.3% vs gas", green when cheaper. */
export function VsGas({ frac }: { frac: number | null | undefined }) {
  if (!finite(frac)) return null;
  // Coloured as shown: "0.0%" is neither.
  const shown = Math.round(frac * 1000);
  return <small className={`lib-vs${shown < 0 ? " is-good" : shown > 0 ? " is-bad" : ""}`}>{fmtVsGas(frac)} vs gas</small>;
}

export function FailTag({ r }: { r: LibraryRow }) {
  if (isValid(r)) return null;
  return (
    <span className="tag tag-red lib-fail" title={r.violations?.join("; ") || r.reason || "It broke a cap of the challenge"}>
      broke a cap
    </span>
  );
}

export type OpenTab = "design" | "economics";

/** "Open in Design · Economics": links when the design is in the tabs, else buttons that open it first. */
export function OpenLinks({ r, onOpen, opening, compact = false }: { r: LibraryRow; onOpen: (r: LibraryRow, tab: OpenTab) => void; opening: string | null; compact?: boolean }) {
  const busy = opening === r.id;
  const label = (tab: OpenTab) => (compact ? (tab === "design" ? "Design" : "Economics") : tab === "design" ? "Open in Design" : "Open in Economics");
  const aria = (tab: OpenTab) => `Open ${designLabel(r)} in ${tab === "design" ? "Design" : "Economics"}`;
  if (r.in_tabs)
    return (
      <span className="lib-open">
        {(["design", "economics"] as const).map((tab) => (
          <a key={tab} className="lib-open-link" href={hrefFor(tab, r.id)} aria-label={aria(tab)}>
            {label(tab)}
          </a>
        ))}
      </span>
    );
  return (
    <span className="lib-open">
      {(["design", "economics"] as const).map((tab) => (
        <button key={tab} type="button" className="lib-open-link" disabled={busy} aria-label={aria(tab)} title="Adds this design to the tabs (it runs again with its daily series)" onClick={() => onOpen(r, tab)}>
          {busy ? "Opening…" : label(tab)}
        </button>
      ))}
    </span>
  );
}
