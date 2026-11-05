// The cost of heat (or cold) as a waterfall: one row per cost line, its bar starting where the
// one before ends, its €/MWh at the right; the last row is the total, split by kind (capital,
// fixed and variable O&M, electricity, gas, the CO₂ price). The rounded labels add up to the
// LCOH/LCOC shown (model.costSteps). Beside the other side's card the rows spread to the card's
// height, so both totals and keys sit level at the bottom.

import { useEffect, useRef } from "react";

import { menuProps, priceKeyOf, sensParamOfCost, type MenuTarget } from "../../menu";
import { AskButton, ProvenanceChip, type AssumptionItem, type CostLine, type Design, type Provenance } from "../../workbench";
import { Key, Panel } from "../energy/parts";
import { costSteps, kindMeta, kindTotals, largestLine, type CostStep } from "./model";
import { eur, meur } from "./format";

interface Props {
  design: Design;
  side: "heat" | "cold";
  lines: CostLine[];
  total: number | null;
  prov: Provenance;
  /** Why there's nothing to show (no cold, no heat delivered). */
  none?: string | null;
  delay?: number;
  /** The conversation's prices, for "Change this price" on a line's menu. */
  prices?: AssumptionItem[];
  /** Open the assumptions on one price. */
  onPrice?: (key: string) => void;
  /** Lines to pick out (a unit's "Show its cost lines in Economics"), and when asked. */
  highlight?: { items: string[]; at: number } | null;
}

const NAME = { heat: "Cost of heat", cold: "Cost of cold" };

/** What the chip says about these costs (dioscuri_plant.economics). */
const PROV_DETAIL = {
  heat: "Sourced prices and unit costs (see Assumptions), capital paid off over each unit's life; the wells, pumps and brine gas shared with the cold by the brine heat each uses",
  cold: "Sourced prices and unit costs (see Assumptions), capital paid off over each unit's life; the wells, pumps and brine gas shared with the heat by the brine heat each uses",
};

export function CostPanel({ design, side, lines, total, prov, none, delay, prices, onPrice, highlight }: Props) {
  const w = none ? null : costSteps(lines, total);
  // A line's menu: why so much, change its price, vary it in Sensitivity, copy it.
  const lineMenu = (s: CostStep): MenuTarget => {
    const key = prices && onPrice ? priceKeyOf(s, prices.map((p) => p.key)) : null;
    const price = key ? prices?.find((p) => p.key === key) : undefined;
    return {
      kind: "cost",
      design: { id: design.id, name: design.uid || design.code, sub: design.code },
      side,
      item: s.item,
      eur: s.label === 0 ? eur(s.raw, 2) : eur(s.label),
      total: eur(w?.total ?? 0),
      price: key && price && onPrice ? { label: price.label || key, open: () => onPrice(key) } : undefined,
      sensParam: sensParamOfCost(s) ?? undefined,
    };
  };
  const top = w ? largestLine(w.steps) : null;
  const ask = (
    <AskButton
      compact
      label="Ask about this chart"
      context={`${design.code}'s ${NAME[side].toLowerCase()}${w ? `, ${eur(w.total)} €/MWh,` : ""} on the Economics tab`}
      question={top ? `Why is "${top.item}" the largest part of the ${NAME[side].toLowerCase()}?` : undefined}
    />
  );
  return (
    <Panel
      title={NAME[side]}
      sub={w ? `What makes up the ${eur(w.total)} €/MWh, line by line: €/MWh and the share of it` : undefined}
      delay={delay}
      className="ec-cost ec-fill"
      aside={
        <>
          <ProvenanceChip source={prov} detail={PROV_DETAIL[side]} />
          {ask}
        </>
      }
    >
      {!w || !w.steps.length ? (
        <p className="ee-foot ec-none">{none ?? "No cost lines for this design."}</p>
      ) : (
        <Waterfall steps={w.steps} total={w.total} domain={w.domain} label={NAME[side]} lineMenu={lineMenu} highlight={highlight} />
      )}
    </Panel>
  );
}

function Waterfall({
  steps,
  total,
  domain,
  label,
  lineMenu,
  highlight,
}: {
  steps: CostStep[];
  total: number;
  domain: [number, number];
  label: string;
  lineMenu?: (s: CostStep) => MenuTarget;
  highlight?: { items: string[]; at: number } | null;
}) {
  const box = useRef<HTMLOListElement>(null);
  // The design's names ("Boiler O&M", "CO2: gas") as the waterfall shows them ("Boiler O&M, fixed", "CO₂: gas").
  const fold = (x: string) => x.toLowerCase().replace(/₂/g, "2").trim();
  const wanted = (highlight?.items ?? []).map(fold);
  const isLit = (item: string) => wanted.some((w) => fold(item) === w || fold(item).startsWith(`${w},`));
  // Picked out from another tab: bring the first of them into view.
  useEffect(() => {
    if (!highlight) return;
    box.current?.querySelector(".ec-wf-row.is-hl")?.scrollIntoView({ block: "center", behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [highlight?.at]); // eslint-disable-line react-hooks/exhaustive-deps
  const [lo, hi] = domain;
  const span = hi - lo || 1;
  const pos = (v: number) => ((v - lo) / span) * 100;
  const kinds = kindTotals(steps);
  const summary = `${label}, ${eur(total)} €/MWh: ${steps.map((s) => `${s.item} ${eur(s.label)} (${shareText(s.raw, total)})`).join(", ")}.`;
  let cum = 0;
  return (
    <div className="ec-wf-wrap">
      <ol ref={box} className="ec-wf" aria-label={summary}>
        {steps.map((s) => {
          const a = pos(Math.min(s.start, s.end));
          const b = pos(Math.max(s.start, s.end));
          const meta = kindMeta(s.kind);
          return (
            <li
              key={`${s.kind}-${s.item}`}
              className={`ec-wf-row${isLit(s.item) ? " is-hl" : ""}`}
              title={`${meta.label}: ${eur(s.raw, 2)} €/MWh, ${shareText(s.raw, total)} of the ${label.toLowerCase()}${Number.isFinite(s.meurPerYear) ? `, ${meur(s.meurPerYear)} M€ a year` : ""}`}
              {...(lineMenu ? menuProps(() => lineMenu(s)) : {})}
            >
              <span className="ec-wf-label">
                <span className="ee-swatch" style={{ background: meta.color }} aria-hidden="true" />
                <span className="ec-wf-item">{s.item}</span>
              </span>
              <span className="ec-wf-track" aria-hidden="true">
                <span className="ec-wf-bar ta-grow" style={{ left: `${a}%`, width: `max(2px, ${b - a}%)`, background: meta.color }} />
              </span>
              <span className="ec-wf-value">
                {s.label === 0 ? (s.raw < 0 ? "> −0.1" : "< 0.1") : eur(s.label)} <span className="ec-wf-share">({shareText(s.raw, total)})</span>
              </span>
            </li>
          );
        })}
        <li className="ec-wf-row total">
          <span className="ec-wf-label">
            <span className="ec-wf-item">{label}</span>
          </span>
          <span className="ec-wf-track" aria-hidden="true">
            {/* Costs stacked first; a revenue (the brine's gas sold) steps back from their end, hatched. */}
            {[...kinds.filter((k) => k.value >= 0), ...kinds.filter((k) => k.value < 0)].map((k) => {
              const start = cum;
              cum += k.value;
              const a = pos(Math.min(start, cum));
              const b = pos(Math.max(start, cum));
              const color = kindMeta(k.kind).color;
              const credit = k.value < 0;
              return (
                <span
                  key={k.kind}
                  className={`ec-wf-bar ta-grow${credit ? " ec-wf-credit" : ""}`}
                  style={{
                    left: `${a}%`,
                    width: `max(2px, calc(${b - a}% - 2px))`,
                    background: credit ? `repeating-linear-gradient(135deg, ${color} 0 3px, transparent 3px 6px)` : color,
                  }}
                />
              );
            })}
          </span>
          <span className="ec-wf-value">
            <strong>{eur(total)}</strong> <span className="ec-unit">€/MWh</span>
          </span>
        </li>
      </ol>
      <div className="ee-legend">
        {kinds.map((k) => (
          <Key key={k.kind} color={kindMeta(k.kind).color}>
            {kindMeta(k.kind).label} <span className="ee-fig">{eur(k.value)}</span>
            {k.value < 0 ? " (a sale, taken off)" : ""}
          </Key>
        ))}
      </div>
    </div>
  );
}

/** A line's share of the side's cost: "17 %", "<1 %", a credit "−3 %". */
export function shareText(raw: number, total: number): string {
  if (!Number.isFinite(raw) || !(total > 0)) return "–";
  const f = raw / total;
  if (f > 0 && f < 0.005) return "<1 %";
  if (f < 0 && f > -0.005) return "<1 %";
  const p = Math.round(Math.abs(f) * 100);
  return `${f < 0 ? "−" : ""}${p} %`;
}
