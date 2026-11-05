// The Economics tab: costs, capital, CO₂ and cash flow for the design in the picker, from
// Dioscuri's plant model and its sourced prices. Headline tiles (the cost of heat, of cold and of
// both together, capital, CO₂, NPV against gas); a toolbar with the Assumptions button (it opens
// the assumptions as a slide-over drawer) and the prices the costs use; then, full width, the cost
// of heat and of cold side by side as waterfalls of their cost lines, the discounted cash flow
// against the gas plant with its payback and NPV, and the capital by item beside CO₂ by source.
// Cards side by side share one height. Every number is the design's Economics (workbench API);
// Apply in the drawer has the server recompute them for every design. Below the plant's cost, a
// separate section: the investor's view with sales, SDE++ and corporate tax (InvestorPanel).

import "./EconomicsTab.css";

import { useCallback, useRef, useState } from "react";

import { useIntent } from "../menu";
import { AskButton, TabFrame, designTitle, provenanceOf, useWorkbench, type Candidate, type Design, type Workbench } from "../workbench";
import { currentBaseline } from "./compare/search";
import { ApplyBar, AssumptionsBar, AssumptionsDrawer, useAssumptionsForm } from "./economics/AssumptionsPanel";
import { BasisPanel } from "./economics/BasisPanel";
import { assumptionValue } from "./economics/assumptions";
import { CapitalPanel } from "./economics/CapitalPanel";
import { CashFlowPanel } from "./economics/CashFlowPanel";
import { Co2Panel } from "./economics/Co2Panel";
import { CostPanel } from "./economics/CostPanel";
import { eur, signed, tonnes } from "./economics/format";
import { InvestorSection } from "./economics/InvestorPanel";
import { GAS_PLANT, horizonOf, lcoeOf, paybackText } from "./economics/model";
import { Meter, Tile } from "./energy/parts";

export default function EconomicsTab() {
  const wb = useWorkbench();
  const design = wb.selected;
  return (
    <TabFrame
      scope="design"
      className="tab-economics"
      title="Economics"
      lead="What the heat and cold cost, what it takes to build, and how it pays back against gas."
      actions={design && <AskButton context={`the economics of ${designTitle(design)}`} />}
    >
      {design && wb.workbench && <EconomicsBody design={design} workbench={wb.workbench} threadId={wb.threadId} setAssumptions={wb.setAssumptions} />}
    </TabFrame>
  );
}

function EconomicsBody({
  design,
  workbench,
  threadId,
  setAssumptions,
}: {
  design: Design;
  workbench: Workbench;
  threadId: string | null;
  setAssumptions: ReturnType<typeof useWorkbench>["setAssumptions"];
}) {
  const a = workbench.assumptions ?? null;
  const form = useAssumptionsForm(a, setAssumptions);
  // The drawer: closed, or open (at a field when a key price was clicked).
  const [drawer, setDrawer] = useState<{ field: string | null } | null>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const closeDrawer = useCallback(() => setDrawer(null), []);
  // A unit's "Show its cost lines in Economics" (the Design tab): those lines picked out.
  const [highlight, setHighlight] = useState<{ items: string[]; at: number } | null>(null);
  useIntent("economics", (v) => setHighlight({ items: v.highlight, at: Date.now() }));
  const onPrice = useCallback((key: string) => setDrawer({ field: key }), []);
  const pending = form.pending != null;
  // The search priced its gas baseline once; after a change of prices it no longer compares.
  const baseline = currentBaseline(workbench);
  const prov = provenanceOf(design, "economics");
  const rate = assumptionValue(a, "discount_rate");
  const y = design.year;
  const e = design.economics;
  const gaps = [
    y.heat_demand_gwh > 0 && y.heat_coverage < 0.995 ? `${pct(y.heat_coverage)} of the heat` : null,
    y.cool_demand_gwh > 0 && y.cool_coverage < 0.995 ? `${pct(y.cool_coverage)} of the cold` : null,
  ].filter(Boolean);
  const short = gaps.length ? `only ${gaps.join(" and ")}` : null;
  const noHeat = !(y.heat_delivered_gwh > 0) ? "This design delivers no heat, so it has no cost of heat." : null;
  const noCold = !(y.cool_demand_gwh > 0) ? "No cooling demand in this brief." : e.lcoc == null || !(y.cool_delivered_gwh > 0) ? "This design supplies no cold." : null;

  return (
    <>
      <Kpis design={design} baseline={baseline} />
      {e.breakdown_pct && <Breakdown shares={e.breakdown_pct} credit={e.credit_pct ?? null} />}

      {short && (
        <p className="ec-short ta-rise" role="note">
          <strong>
            {design.code} covers {short}.
          </strong>{" "}
          Its costs and CO₂ count only what it delivers, so they flatter it against designs that meet the whole demand.
        </p>
      )}

      {a && <AssumptionsBar a={a} form={form} open={drawer != null} onOpen={(field) => setDrawer({ field: field ?? null })} buttonRef={opener} />}

      <div className={`ec-main${pending ? " pending" : ""}`} aria-busy={pending}>
        <div className="ec-pair">
          <CostPanel design={design} side="heat" lines={e.lines?.heat ?? []} total={e.lcoh} prov={prov} none={noHeat} delay={0.06} prices={a?.items} onPrice={a ? onPrice : undefined} highlight={highlight} />
          <CostPanel design={design} side="cold" lines={e.lines?.cold ?? []} total={e.lcoc} prov={prov} none={noCold} delay={0.08} prices={a?.items} onPrice={a ? onPrice : undefined} highlight={highlight} />
        </div>
        {!isGasPlant(design) && <BasisPanel design={design} threadId={threadId} prov={prov} delay={0.09} />}
        <CashFlowPanel design={design} prov={prov} rate={rate} reference={GAS_PLANT} delay={0.1} />
        <div className="ec-pair">
          <CapitalPanel design={design} prov={prov} reference={GAS_PLANT} delay={0.12} />
          <Co2Panel design={design} prov={prov} carbonPrice={assumptionValue(a, "carbon_eur_per_t")} delay={0.14} />
        </div>
        <InvestorSection design={design} prov={prov} setAssumptions={setAssumptions} />
      </div>

      {a && !drawer && <ApplyBar form={form} onReview={() => setDrawer({ field: null })} />}
      {a && drawer && <AssumptionsDrawer a={a} form={form} code={design.code} focusField={drawer.field} onClose={closeDrawer} returnTo={opener} />}
    </>
  );
}

const pct = (f: number) => `${eur(Math.max(0, f) * 100).replace(/\.0$/, "")}%`;

/** The gas reference has no wells, no basis of its own to explain (the other designs are set against it). */
const isGasPlant = (d: Design) => d.economics.versus_reference == null;

function Kpis({ design, baseline }: { design: Design; baseline: Candidate | null }) {
  const e = design.economics;
  const y = design.year;
  const v = e.versus_reference;
  const isRef = v == null;
  const r = !isRef ? baseline : null;
  const heat = y.heat_delivered_gwh > 0;
  const cold = e.lcoc != null && y.cool_delivered_gwh > 0;
  const lcoe = lcoeOf(design);
  // Against the gas plant of this design's own conditions (the server's fractions); the shared
  // baseline only for designs from older servers.
  const own = e.vs_gas_pct;
  const gasOf = (ours: number, frac: number | null | undefined, fallback: number | null | undefined) =>
    frac != null && Number.isFinite(frac) && 1 + frac !== 0 ? ours / (1 + frac) : fallback;
  const vs = (ours: number, theirs: number | null | undefined) => {
    if (theirs == null || !Number.isFinite(theirs)) return {};
    const d = ours - theirs;
    if (Math.abs(d) < 0.05) return { note: "same as gas", noteTone: "muted" as const };
    const p = Math.round((Math.abs(d) / theirs) * 100);
    return { note: `${p} % ${d < 0 ? "cheaper" : "dearer"} than gas (${signed(d)})`, noteTone: d < 0 ? ("good" as const) : ("bad" as const) };
  };
  const gasHeat = gasOf(e.lcoh, own?.heat, r?.lcoh);
  const gasCold = e.lcoc != null ? gasOf(e.lcoc, own?.cold, r?.lcoc) : null;
  const years = horizonOf(v);
  const biggest = (e.capex_items ?? []).reduce<{ item: string; meur: number } | null>((b, it) => (!b || it.meur > b.meur ? it : b), null);
  const sub = (gas: number | null | undefined, plain: string) => (gas != null && Number.isFinite(gas) ? `gas plant ${eur(gas)} €/MWh` : isRef ? "this is the gas plant" : plain);
  return (
    <div className="ee-tiles ec-tiles ta-rise">
      <Tile
        label="Cost of heat"
        value={heat ? eur(e.lcoh) : "none"}
        valueTone={heat ? undefined : "muted"}
        unit={heat ? "€/MWh" : undefined}
        {...(heat && !isRef ? vs(e.lcoh, gasHeat) : {})}
        sub={!heat ? "no heat delivered" : sub(isRef ? null : gasHeat, "levelised over each unit's life")}
      />
      <Tile
        label="Cost of cold"
        value={cold ? eur(e.lcoc as number) : "none"}
        valueTone={cold ? undefined : "muted"}
        unit={cold ? "€/MWh" : undefined}
        {...(cold && !isRef ? vs(e.lcoc as number, gasCold) : {})}
        sub={!cold ? "no cold supplied" : sub(isRef ? null : gasCold, "levelised over each unit's life")}
      />
      <Tile
        label="Heat + cold"
        value={lcoe != null ? eur(lcoe) : "none"}
        valueTone={lcoe != null ? undefined : "muted"}
        unit={lcoe != null ? "€/MWh" : undefined}
        {...(lcoe != null && !isRef ? vs(lcoe, gasOf(lcoe, own?.total, r?.lcoe)) : {})}
        sub={lcoe == null ? "nothing delivered" : sub(isRef ? null : gasOf(lcoe, own?.total, r?.lcoe), "both together, levelised")}
      />
      <Tile
        label="Capital"
        value={eur(e.capex_meur)}
        unit="M€"
        note={v ? `${signed(v.extra_capex_meur)} vs gas` : undefined}
        noteTone="muted"
        sub={biggest ? `${biggest.item} ${eur(biggest.meur)} M€ of it` : undefined}
      />
      <Tile
        label="CO₂"
        value={tonnes(e.co2_t_per_year)}
        unit="t a year"
        note={isRef ? undefined : `${e.co2_saving_pct >= 0 ? "−" : "+"}${eur(Math.abs(e.co2_saving_pct))}% vs gas`}
        noteTone={e.co2_saving_pct >= 0 ? "good" : "bad"}
        sub={isRef ? "this is the gas plant" : `gas plant ${tonnes(e.reference_co2_t_per_year)} t`}
      >
        {!isRef && <Meter value={e.co2_t_per_year} max={Math.max(e.reference_co2_t_per_year, e.co2_t_per_year)} color={e.co2_saving_pct >= 0 ? "#2BA866" : "#B42318"} label={`${tonnes(e.co2_t_per_year)} of the gas plant's ${tonnes(e.reference_co2_t_per_year)} t`} />}
      </Tile>
      {isRef ? (
        <Tile label="NPV against gas" value="this is the gas plant" valueTone="muted" sub="the other designs are measured against it" />
      ) : (
        <Tile
          label="NPV against gas"
          value={signed(v.npv_meur)}
          valueTone={v.npv_meur >= 0 ? "good" : "bad"}
          unit="M€"
          sub={v.payback_years != null ? `pays back ${paybackText(v.payback_years)}` : `no payback${years != null ? ` in ${years} years` : ""}`}
        />
      )}
    </div>
  );
}

const KIND_NAMES: Record<string, { label: string; color: string }> = {
  capital: { label: "Capital", color: "#0a6f7c" },
  fixed: { label: "Fixed O&M", color: "#5aa6ae" },
  variable: { label: "Variable O&M", color: "#9fd0d4" },
  electricity: { label: "Electricity", color: "#e3a33b" },
  gas: { label: "Gas", color: "#7856c4" },
  carbon: { label: "CO₂", color: "#8a959e" },
};

/** Where the year's cost of heat and cold goes, in shares (Ali's "costs in percentage"). */
function Breakdown({ shares, credit }: { shares: Record<string, number>; credit: number | null }) {
  const parts = Object.entries(shares)
    .filter(([, v]) => v > 0.0005)
    .sort((a, b) => b[1] - a[1]);
  if (!parts.length) return null;
  const pctOf = (v: number) => `${Math.round(v * 100)} %`;
  return (
    <section className="card ec-breakdown ta-rise" aria-label="Where the cost goes">
      <h3>Where the cost of heat and cold goes</h3>
      <div className="split-bar" role="img" aria-label={parts.map(([k, v]) => `${KIND_NAMES[k]?.label ?? k} ${pctOf(v)}`).join(", ")}>
        {parts.map(([k, v]) => (
          <span key={k} className="ta-grow" style={{ width: `${v * 100}%`, background: KIND_NAMES[k]?.color ?? "#B3BAB2" }} />
        ))}
      </div>
      <div className="legend-row">
        {parts.map(([k, v]) => (
          <span key={k}>
            <span className="sq" style={{ background: KIND_NAMES[k]?.color ?? "#B3BAB2" }} />
            {KIND_NAMES[k]?.label ?? k} {pctOf(v)}
          </span>
        ))}
      </div>
      {credit ? <p className="note">The brine&apos;s gas sold to the grid earns back {pctOf(credit)} of these costs.</p> : null}
    </section>
  );
}
