// A tiny chip that says who produced a number: GEMINI's solver, Dioscuri's plant model, you, or a rule.

import { useRef } from "react";

import type { Design, Provenance, ProvenanceKey } from "../types";
import "./workbench.css";

export const PROVENANCE: Record<Provenance, { label: string; tip: string }> = {
  gemini: { label: "GEMINI", tip: "Computed by GEMINI's solver with the team's fixes" },
  dioscuri: { label: "Dioscuri", tip: "Dioscuri's plant model: the year day by day, cooling and sourced costs" },
  user: { label: "you", tip: "A value you set" },
  rule: { label: "rule", tip: "Set by a rule in the code, not computed" },
};

/** Who produced a design's field group; the design's `source` decides when it doesn't say. */
export function provenanceOf(design: Design, key: ProvenanceKey): Provenance {
  const p = design.provenance?.[key];
  if (p === "gemini" || p === "dioscuri" || p === "user" || p === "rule") return p;
  return key === "plant" && design.source.startsWith("gemini") ? "gemini" : "dioscuri";
}

interface Props {
  source: Provenance;
  /** Added to the tooltip, e.g. "GEMINI 1.0.3 with 10 fixes". */
  detail?: string;
  className?: string;
}

export function ProvenanceChip({ source, detail, className }: Props) {
  const p = PROVENANCE[source] ?? PROVENANCE.dioscuri;
  const tip = detail ? `${p.tip}. ${detail}` : p.tip;
  const tipRef = useRef<HTMLSpanElement>(null);
  // Keep the tip on screen: shift it sideways when the chip sits near an edge (phones).
  const place = () => {
    const el = tipRef.current;
    if (!el) return;
    el.style.setProperty("--tip-shift", "0px");
    const r = el.getBoundingClientRect();
    const room = document.documentElement.clientWidth - 8;
    const shift = r.left < 8 ? 8 - r.left : r.right > room ? room - r.right : 0;
    el.style.setProperty("--tip-shift", `${Math.round(shift)}px`);
  };
  return (
    <span className={`prov prov-${source}${className ? ` ${className}` : ""}`} tabIndex={0} role="note" aria-label={`${p.label}: ${tip}`} onPointerEnter={place} onFocus={place}>
      {p.label}
      <span className="wb-tip" aria-hidden="true" ref={tipRef}>
        {tip}
      </span>
    </span>
  );
}
