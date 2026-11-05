// The result card (CUSTOM `result` + `checks`): the design at a glance. Every number on it comes
// from the card the agent sends; nothing is computed here except shares, bar widths and, on a
// what-if's compact card, the differences against the design it changed. A design's variant
// flags ("2I1", "ST") are chips on its code, explained on hover, and doublets built differently
// get a line each. The links open the design in the tabs by its id ("<code> · <change>" for a
// what-if, so the tabs show the what-if and not the design it changed).

import { useState, type ReactNode } from "react";

import { changeList, doubletLines, flagMeaning, splitCode } from "../agent/numbers";
import type { Check, Firm, Pick, ResultCard as Card } from "../agent/types";
import { previewExport } from "../workbench/exports";
import { checkWords, fmtNum, fmtSigned, statusWords } from "../workbench/format";
import { useWorkbench } from "../workbench";
import { hrefFor } from "../workbench/route";
import { Arrow, DoneIcon, FailIcon, Tick } from "./Icons";
import { MonthlyChart } from "./MonthlyChart";
import { MenuButton, menuProps, type MenuTarget } from "../menu";

/** The card's design as a context menu's target (menu/registry.ts): open, compare, ask, the PDF. */
const cardTarget = (card: Card): MenuTarget => ({ kind: "design", design: { id: designIdOf(card), name: card.uid || card.alternative, sub: card.name } });

export { fmtNum };

const HEAT: Record<string, { label: string; color: string }> = {
  geo: { label: "Geothermal", color: "#C24E1C" },
  hp: { label: "Heat pump", color: "#E3A33B" },
  boiler: { label: "Gas boiler", color: "#7856C4" },
  electric_boiler: { label: "Electric boiler", color: "#C8378A" },
};
const COLD: Record<string, { label: string; color: string }> = {
  free: { label: "Free cooling", color: "#3C9D7A" },
  abs: { label: "Absorption chiller", color: "#2363A6" },
  chill: { label: "Electric chillers", color: "#139FBF" },
};
const SIZES: Record<string, string> = {
  heat_exchanger: "Heat exchanger",
  heat_pump: "Heat pump",
  boiler: "Gas boiler",
  electric_boiler: "Electric boiler",
  absorption: "Absorption chiller",
  chillers: "Chillers",
};

const kpi = (card: Card, id: string) => card.kpis.find((k) => k.id === id);

interface SplitPart {
  key: string;
  label: string;
  color: string;
  gwh: number;
}

function parts(split: Record<string, number> | undefined, names: typeof HEAT): SplitPart[] {
  return Object.entries(split ?? {})
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ key: k, label: names[k]?.label ?? k, color: names[k]?.color ?? "#B3BAB2", gwh: v }));
}

/** A what-if's card is one row against the design it changed; a design run gets the full report. */
export const isCompact = (card: Card): boolean => card.view === "compact";

/** The design's id in the tabs: the card's, else "<code> · <change label>" for a what-if, else the code. */
export function designIdOf(card: Card): string {
  if (card.design_id) return card.design_id;
  const label = card.change_label?.trim();
  return label ? `${card.alternative} · ${label}` : card.alternative;
}

/** A design code as its layout and its variant flags (the card's flags, else the code's). */
export function codeParts(card: Card): { badge: string; flags: string[] } {
  const split = splitCode(card.alternative);
  const flags = Array.isArray(card.flags) && card.flags.length ? card.flags.map(String) : split.flags;
  return { badge: split.flags.length ? split.base : card.alternative, flags };
}

export interface CompactFigure {
  id: "heat_coverage" | "lcoh" | "lcoe" | "co2_saving";
  label: string;
  value: number | null;
  unit: string;
  /** The change against the compared design, in the figure's unit (points for the two shares). */
  delta?: number;
  /** True when the change is an improvement (more heat covered, cheaper heat, more CO₂ saved); unset at zero. */
  better?: boolean;
}

// The reporter sends CO₂ against gas as a signed change (−69 means 69% less); the card shows the saving.
function co2Saving(card: Card): number | null {
  const saving = kpi(card, "co2_saving");
  if (saving) return saving.value;
  const co2 = kpi(card, "co2");
  return co2?.value == null ? null : -co2.value;
}

/** The three figures of a compact card, each with its change against `card.against` when known. */
export function compactFigures(card: Card): CompactFigure[] {
  const base = card.against;
  const figure = (id: CompactFigure["id"], label: string, unit: string, read: (c: Card) => number | null, upIsBetter: boolean): CompactFigure => {
    const value = read(card);
    const against = base ? read(base) : null;
    const f: CompactFigure = { id, label, value, unit };
    if (value != null && against != null) {
      f.delta = Math.round((value - against) * 10) / 10;
      if (f.delta !== 0) f.better = upIsBetter ? f.delta > 0 : f.delta < 0;
    }
    return f;
  };
  // The headline cost is heat and cold together (what the search ranks by); cards recorded
  // before 1 Nov have only the cost of heat.
  const cost = kpi(card, "lcoe")
    ? figure("lcoe", "Cost of heat and cold", "€/MWh", (c) => kpi(c, "lcoe")?.value ?? null, false)
    : figure("lcoh", "Cost of heat", kpi(card, "lcoh")?.unit ?? "€/MWh", (c) => kpi(c, "lcoh")?.value ?? null, false);
  return [figure("heat_coverage", "Heat covered", "%", (c) => kpi(c, "heat_coverage")?.value ?? null, true), cost, figure("co2_saving", "CO₂ saving", "%", co2Saving, true)];
}

export function ResultCard({ card, checks, picked = false }: { card: Card; checks?: Check[]; picked?: boolean }) {
  if (isCompact(card)) return <CompactCard card={card} />;
  return <FullCard card={card} checks={checks} picked={picked} />;
}

/**
 * A what-if in one row: the change, the design it was made on, three figures with their change
 * against that design, and the links to the what-if's tabs. The checks that follow are not shown.
 */
function CompactCard({ card }: { card: Card }) {
  const base = card.against;
  const figures = compactFigures(card);
  const id = designIdOf(card);
  const label = card.change_label?.trim();
  const on = base?.alternative ?? card.alternative;
  // A change to the plant itself (a second injector, a unit's size) makes another code.
  const moved = !!base && base.alternative !== card.alternative;
  const changes = changeList(card.changes);
  return (
    <section
      className="card result compact ta-rise"
      style={{ animationDelay: ".12s" }}
      aria-label={label ? `What-if: ${label}, on ${on}` : `What-if on ${card.alternative}`}
      {...menuProps(cardTarget(card))}
    >
      <div className="compact-head">
        <span className="compact-kicker">What-if</span>
        {label ? (
          <>
            <span className="change-chip" title={changes.length ? `Changed: ${changes.join(", ")}` : undefined}>
              <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M2.5 5h7M12.5 5h1M2.5 11h1M6.5 11h7" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                <circle cx="11" cy="5" r="1.7" fill="none" stroke="currentColor" strokeWidth="1.5" />
                <circle cx="5" cy="11" r="1.7" fill="none" stroke="currentColor" strokeWidth="1.5" />
              </svg>
              {label}
            </span>
            <span className="compact-on">
              on{" "}
              <span className="alt-code" title={base?.name ?? card.name}>
                {on}
              </span>
              {moved && (
                <>
                  {" "}
                  <span aria-label="becomes">→</span>{" "}
                  <span className="alt-code" title={card.name}>
                    {card.alternative}
                  </span>
                </>
              )}
            </span>
          </>
        ) : (
          <strong className="compact-title">
            {card.alternative} {card.name}
          </strong>
        )}
        {!card.verified && (
          <span className="tag tag-red" title={card.failed?.length ? `Fails: ${card.failed.join("; ")}` : undefined}>
            {card.failed?.length ? statusWords(card.failed, false) : "fails checks"}
          </span>
        )}
        {base && <span className="note compact-vs">against {designIdOf(base)} as designed</span>}
      </div>
      <div className="compact-figures">
        {figures.map((f) => (
          <span key={f.id} className="compact-figure">
            <span className="tile-label">{f.label}</span>
            <strong className="compact-value">
              {f.value == null ? "–" : f.unit === "%" ? `${fmtNum(f.value)}%` : <>{fmtNum(f.value)} <span className="tile-unit">{f.unit}</span></>}
            </strong>
            {f.delta != null && (
              <span className={`delta${f.better === undefined ? "" : f.better ? " good" : " bad"}`}>
                {f.delta === 0 ? "no change" : `${fmtSigned(f.delta)}${f.unit === "%" ? " points" : ` ${f.unit}`}`}
              </span>
            )}
          </span>
        ))}
      </div>
      {card.firm && card.firm.short > 0 && card.against?.firm && card.against.firm.short === 0 && (
        <p className="research-line changed">
          <span className="research-kicker">N-1 lost</span>
          Under this change {card.firm.short} of {card.firm.cases.length} one-unit-out cases leave a day short
          {(() => {
            const w = card.firm.cases.filter((c) => c.short).sort((a, b) => b.worst_mw - a.worst_mw)[0];
            return w ? `; worst: ${w.unit}, ${fmtNum(w.worst_mw)} MW ${w.side === "heat" ? "heat" : "cold"} short on ${w.worst_day}` : "";
          })()}
          .
        </p>
      )}
      {card.research && <ResearchLine card={card} />}
      <nav className="card-links" aria-label={`${id} in the tabs`}>
        <a href={hrefFor("design", id)}>
          Open in Design <Arrow size={12} />
        </a>
        <a href={hrefFor("economics", id)}>
          Economics <Arrow size={12} />
        </a>
        <ReportLink id={id} />
        <MenuButton small target={cardTarget(card)} label={`More for ${card.uid || id}: Energy, compare, what-if, link`} />
      </nav>
    </section>
  );
}

/** A what-if's other half: what the search picks under the change, and whether that changes the pick. */
function ResearchLine({ card }: { card: Card }) {
  const r = card.research!;
  return (
    <p className={`research-line${r.changed ? " changed" : ""}`}>
      <span className="research-kicker">{r.changed ? "The pick changes" : "The pick stays"}</span>
      {r.changed ? (
        <>
          Searching again under the change picks <span className="alt-code">{r.id}</span> at <strong>{fmtNum(r.lcoe)} €/MWh</strong> instead of{" "}
          <span className="alt-code">{r.base_id}</span>.
        </>
      ) : (
        <>
          Searching again under the change picks the same layout, <span className="alt-code">{r.id}</span>, at <strong>{fmtNum(r.lcoe)} €/MWh</strong>.
        </>
      )}
    </p>
  );
}

function FullCard({ card, checks, picked }: { card: Card; checks?: Check[]; picked: boolean }) {
  const [showChecks, setShowChecks] = useState(false);
  const heat = parts(card.heat_split_gwh, HEAT);
  const cold = parts(card.cool_split_gwh, COLD);
  const heatDemand = card.demand_gwh?.heat ?? heat.reduce((a, p) => a + p.gwh, 0);
  const coldDemand = card.demand_gwh?.cold ?? cold.reduce((a, p) => a + p.gwh, 0);
  const failed: Check[] = checks?.length ? checks.filter((c) => !c.passed) : (card.failed ?? []).map((name) => ({ name, passed: false, detail: "" }));
  const physicsFailed = failed.some((c) => c.requirement === false);
  const ok = card.verified && !failed.length;
  // What happened, in words (Ali, 3 Nov): the check it misses, or how many.
  const words = failed.length ? statusWords(failed.map((c) => c.name), false) : "";
  const status = ok
    ? { text: `${picked ? "Your pick" : "Recommended"}, ${card.checks.passed} of ${card.checks.total} checks`, color: "#0F7A3D" }
    : physicsFailed
      ? { text: `Fails physics: ${words}, ${card.checks.passed} of ${card.checks.total} checks`, color: "#A12C22" }
      : {
          text: `${picked ? "Your pick, but it" : "It"} ${words || "misses the brief"}, ${card.checks.passed} of ${card.checks.total} checks`,
          color: "#9A3B12",
        };

  const heatCov = kpi(card, "heat_coverage");
  const coolCov = kpi(card, "cool_coverage");
  const lcoe = kpi(card, "lcoe");
  const lcoh = kpi(card, "lcoh");
  const lcoc = kpi(card, "lcoc");
  const co2 = kpi(card, "co2");
  const flh = kpi(card, "flh");
  // A design that delivers no heat has no meaningful cost or CO₂ figure.
  const delivers = (heatCov?.value ?? 1) > 0;
  const id = designIdOf(card);
  const code = codeParts(card);
  const doublets = card.doublets?.length;
  // Doublets built differently: a line each; the flags already say what they share.
  const lines = doubletLines(card.doublets, "differences");

  return (
    <section className="card result ta-rise" style={{ animationDelay: ".12s" }} aria-label={ok ? "Recommended design" : "Closest design"} {...menuProps(cardTarget(card))}>
      <div className="result-head">
        <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          {card.uid && card.uid !== card.alternative && (
            <span className="uid-chip" title="This design's name in the chat and the tabs">
              {card.uid}
            </span>
          )}
          <span className="code-group">
            <span className="alt-badge">{code.badge}</span>
            {code.flags.map((f) => (
              <span key={f} className="design-flag" title={flagMeaning(f, doublets)}>
                <span aria-hidden="true">{f}</span>
                <span className="sr-only">{`-${f}: ${flagMeaning(f, doublets)}`}</span>
              </span>
            ))}
          </span>
          <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.25, minWidth: 0 }}>
            <strong style={{ fontSize: 16, fontWeight: 650 }}>{card.name}</strong>
            <button
              type="button"
              className="checks-btn"
              style={{ color: status.color }}
              aria-expanded={showChecks}
              onClick={() => setShowChecks(!showChecks)}
              disabled={!checks?.length}
            >
              {ok ? <Tick /> : <span aria-hidden="true">!</span>}
              <span>{status.text}</span>
            </button>
          </span>
        </div>
        {card.source?.startsWith("gemini") && (
          <span
            className="tag tag-teal"
            title="GEMINI's well solve (with the team's fixes and the challenge's brine) gives the doublets; Dioscuri's plant model runs every day of 2027, the checks and the sourced costs"
          >
            GEMINI wells · Dioscuri year
          </span>
        )}
      </div>

      {lines.length > 0 && (
        <div className="alts doublet-line" aria-label="How the doublets differ">
          {lines.map((l) => {
            const at = l.indexOf(": ");
            return (
              <span key={l} className="alt">
                <b>{l.slice(0, at)}</b>
                {l.slice(at + 2)}
              </span>
            );
          })}
        </div>
      )}

      {!ok && failed.length > 0 && <WhyItFails failed={failed} />}
      {showChecks && checks && <CheckList checks={checks} />}


      <div className="tiles">
        {lcoe && (
          <Tile label="Cost of heat and cold" value={delivers ? fmtNum(lcoe.value ?? 0) : "–"} unit={lcoe.unit} headline>
            {delivers && (
              <span className="tile-sub">
                heat {fmtNum(lcoh?.value ?? 0)}
                {lcoc?.value != null && coldDemand > 0 && (coolCov?.value ?? 0) > 0 ? ` · cold ${fmtNum(lcoc.value)}` : ""} €/MWh
              </span>
            )}
            {delivers && card.vs_gas_pct?.total != null && <VsGas vs={card.vs_gas_pct} />}
          </Tile>
        )}
        {heatCov && (
          <Tile label="Heat covered" color="#C24E1C" value={fmtNum(heatCov.value ?? 0)} unit="%">
            <Mini parts={heat} total={heatDemand} />
          </Tile>
        )}
        {coolCov && coldDemand > 0 && (
          <Tile label="Cold covered" color="#2363A6" value={fmtNum(coolCov.value ?? 0)} unit="%">
            <Mini parts={cold} total={coldDemand} />
          </Tile>
        )}
        {lcoh && !lcoe && (
          <Tile label="Cost of heat" value={delivers ? fmtNum(lcoh.value ?? 0) : "–"} unit={lcoh.unit}>
            {!delivers ? (
              <span className="tile-sub">no heat delivered</span>
            ) : (
              lcoc?.value != null && coldDemand > 0 && (coolCov?.value ?? 0) > 0 && <span className="tile-sub">cold {fmtNum(lcoc.value)} {lcoc.unit}</span>
            )}
          </Tile>
        )}
        {co2 && co2.value != null && (
          <Tile
            label="CO₂ against gas"
            value={delivers ? `${co2.value < 0 ? "−" : "+"}${fmtNum(Math.abs(co2.value))}` : "–"}
            unit="%"
            valueColor={!delivers ? undefined : co2.value < 0 ? "#0F7A3D" : "#A12C22"}
          >
            <span className="minibar">
              <span className="ta-grow" style={{ width: `${delivers ? Math.min(100, Math.abs(co2.value)) : 0}%`, background: co2.value < 0 ? "#2BA866" : "#B42318" }} />
            </span>
          </Tile>
        )}
      </div>

      {card.picks && card.picks.length > 0 && <PicksRow picks={card.picks} />}
      {card.firm && <FirmStrip firm={card.firm} />}
      {(card.network || (card.service && card.service.length > 0) || card.solar || card.storage) && <Conditions card={card} />}
      {card.gemini_check && card.gemini_check.ok && card.gemini_check.total > 0 && <GeminiCheck check={card.gemini_check} />}
      {card.cooling_check && <CoolingCheck check={card.cooling_check} />}
      {card.operability && card.operability.units.length > 0 && <Operability op={card.operability} />}

      <Split title="Heat" demand={heatDemand} parts={heat} />
      {coldDemand > 0 && <Split title="Cold" demand={coldDemand} parts={cold} />}
      {card.monthly_gwh && <MonthlyChart monthly={card.monthly_gwh} heat={HEAT} cold={COLD} />}

      <div className="sizes" aria-label="Equipment sizes">
        {Object.entries(card.sizes_mw ?? {})
          .filter(([, v]) => v > 0)
          .map(([k, v]) => (
            <span key={k} className="chip">
              {SIZES[k] ?? k} <strong style={{ color: "#11181C", fontWeight: 650 }}>{v.toFixed(1)} MW</strong>
            </span>
          ))}
        {flh?.value != null && flh.value > 0 && (
          <span className="chip">
            Doublet in use <strong style={{ color: "#11181C", fontWeight: 650 }}>{fmtNum(flh.value)} h</strong> a year
          </span>
        )}
      </div>

      <nav className="card-links" aria-label={`${id} in the tabs`}>
        <a href={hrefFor("design", id)}>
          Open in Design <Arrow size={12} />
        </a>
        <a href={hrefFor("economics", id)}>
          Economics <Arrow size={12} />
        </a>
        <ReportLink id={id} />
        <MenuButton small target={cardTarget(card)} label={`More for ${card.uid || id}: Energy, compare, what-if, link`} />
      </nav>
    </section>
  );
}

/** "17 % cheaper than gas", "9 % dearer than gas", "as gas": a signed fraction in words. */
export function pctVsGas(x: number): string {
  const p = Math.round(Math.abs(x) * 100);
  if (p === 0) return "same as gas";
  return `${p} % ${x < 0 ? "cheaper" : "dearer"} than gas`;
}

/** The headline against gas, heat and cold apart (the reference of the same conditions). */
function VsGas({ vs }: { vs: { heat: number | null; cold: number | null; total: number | null } }) {
  const total = vs.total ?? 0;
  const part = (label: string, x: number | null) => (x == null ? "" : `${label} ${x < 0 ? "−" : "+"}${Math.round(Math.abs(x) * 100)} %`);
  const parts = [part("heat", vs.heat), part("cold", vs.cold)].filter(Boolean).join(", ");
  return (
    <span className={`tile-sub vs-gas ${total <= 0 ? "good" : "bad"}`} title="Against gas boilers and electric chillers under the same conditions">
      {pctVsGas(total)}
      {parts ? ` (${parts})` : ""}
    </span>
  );
}

/** GEMINI's own run of the brine loop, figure by figure against the plant model. */
function GeminiCheck({ check }: { check: NonNullable<Card["gemini_check"]> }) {
  const [open, setOpen] = useState(false);
  const all = check.agree === check.total;
  return (
    <div className={`firm gemini-check${all ? " ok" : ""}`}>
      <div className="firm-row">
        <span className="firm-label">GEMINI check</span>
        <span className={`firm-fig ${all ? "good" : ""}`}>
          {check.agree} of {check.total} figures agree with GEMINI's own run (within 5 %, or 1 K)
        </span>
        <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Each figure"}
        </button>
      </div>
      {open && (
        <ul className="firm-cases">
          {check.rows.map((r) => (
            <li key={r.quantity} className={r.agree ? "good" : "bad"} title={r.note || undefined}>
              {r.agree ? <DoneIcon size={14} /> : <FailIcon size={14} />}
              <span>{r.quantity}</span>
              <span className="muted">
                GEMINI {fmtNum(r.gemini, 2)} · plant model {fmtNum(r.plant, 2)} {r.unit} ({fmtSigned(r.diff_pct)} %)
                {r.note ? ` · ${r.note}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Minimum loads and trips: the days a unit runs below its minimum (it cycles), and the ESP trips. */
function Operability({ op }: { op: NonNullable<Card["operability"]> }) {
  const [open, setOpen] = useState(false);
  const cycling = op.units.filter((u) => u.days_below > 30);
  const worst = [...op.units].sort((a, b) => b.days_below - a.days_below)[0];
  return (
    <div className={`firm gemini-check${cycling.length ? "" : " ok"}`}>
      <div className="firm-row">
        <span className="firm-label">Running</span>
        <span className="firm-fig">
          {cycling.length ? (
            <>
              The {worst.name} {worst.name.endsWith("s") ? "cycle" : "cycles"} on <strong>{worst.days_below} days</strong> (below {fmtNum(worst.minimum_mw)} MW a unit)
            </>
          ) : (
            "Every unit runs above its minimum load"
          )}
          {op.trips.boiler_gwh > 0 ? ` · ESP trips move ${fmtNum(op.trips.boiler_gwh, 2)} GWh a year to the boiler` : ""}
        </span>
        <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Each unit"}
        </button>
      </div>
      {open && (
        <ul className="firm-cases">
          {op.units.map((u) => (
            <li key={u.kind} className={u.days_below > 30 ? "bad" : "good"}>
              {u.days_below > 30 ? <FailIcon size={14} /> : <DoneIcon size={14} />}
              <span>{u.name[0].toUpperCase() + u.name.slice(1)}</span>
              <span className="muted">
                on {u.days_on} days, {u.days_below} of them below its minimum ({fmtNum(u.minimum_mw)} MW a unit); about {u.starts} starts a year
              </span>
            </li>
          ))}
          <li>
            <span>Trips</span>
            <span className="muted">
              {fmtNum(op.trips.per_doublet_year)} a doublet a year, {fmtNum(op.trips.hours_each)} h each to restart (assumed)
            </span>
          </li>
          <li>
            <span>Figures</span>
            <span className="muted">{op.source}</span>
          </li>
        </ul>
      )}
    </div>
  );
}

/** The cooling component model on the chillers and towers: its electricity and the towers' water. */
function CoolingCheck({ check }: { check: NonNullable<Card["cooling_check"]> }) {
  const [open, setOpen] = useState(false);
  const o = check.ours;
  const limits = Object.entries(check.limits);
  const fine = check.unmet_gwh <= 0.001 && limits.length === 0;
  return (
    <div className={`firm gemini-check${fine ? " ok" : ""}`}>
      <div className="firm-row">
        <span className="firm-label">Cooling check</span>
        <span className="firm-fig">
          Component model: chillers {fmtNum(check.compressor_gwh, 2)} GWh at COP {fmtNum(check.cop)} (ours {fmtNum(o.chillers_gwh, 2)} GWh at {fmtNum(o.chiller_cop)}), towers use{" "}
          <strong>{Math.round(check.makeup_water_m3).toLocaleString("en-GB")} m³</strong> of water a year
        </span>
        <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Details"}
        </button>
      </div>
      {open && (
        <ul className="firm-cases">
          <li className="good">
            <span>Cold from the chillers</span>
            <span className="muted">
              {fmtNum(check.cold_gwh, 2)} GWh{check.unmet_gwh > 0.001 ? `, ${fmtNum(check.unmet_gwh, 2)} GWh unmet` : ", all met"}
            </span>
          </li>
          {check.absorption && (
            <li className={check.absorption.cold_gwh >= 0.95 * check.absorption.ours_cold_gwh ? "good" : "bad"}>
              <span>Absorption chiller</span>
              <span className="muted">
                {fmtNum(check.absorption.cold_gwh, 2)} GWh of cold from {fmtNum(check.absorption.drive_gwh, 2)} GWh of brine heat at COP {fmtNum(check.absorption.cop, 2)} (ours {fmtNum(check.absorption.ours_cold_gwh, 2)} GWh at{" "}
                {fmtNum(check.absorption.ours_cop, 2)}), hot water {check.absorption.hot_loop_c[0]}/{check.absorption.hot_loop_c[1]} °C
              </span>
            </li>
          )}
          <li className="good">
            <span>Towers&rsquo; fans and pumps</span>
            <span className="muted">
              {fmtNum(check.towers_gwh, 2)} GWh (ours {fmtNum(o.towers_gwh, 2)} GWh)
            </span>
          </li>
          <li className="good">
            <span>Towers&rsquo; water</span>
            <span className="muted">
              {Math.round(check.evaporation_m3).toLocaleString("en-GB")} m³ evaporated, {Math.round(check.blowdown_m3).toLocaleString("en-GB")} m³ blown down
            </span>
          </li>
          {limits.map(([k, n]) => (
            <li key={k} className="bad">
              <span>{k.toLowerCase().replace(/_/g, " ")}</span>
              <span className="muted">on {n} days</span>
            </li>
          ))}
          {check.not_checked.map((t) => (
            <li key={t}>
              <span>Not checked yet</span>
              <span className="muted">{t}</span>
            </li>
          ))}
          <li>
            <span>Weather</span>
            <span className="muted">{check.weather}</span>
          </li>
        </ul>
      )}
    </div>
  );
}

/** What the design was run with beyond the challenge: the network's losses, planned service. */
function Conditions({ card }: { card: Card }) {
  const n = card.network;
  return (
    <div className="conditions">
      {n && (
        <span className="chip" title={`DN${n.heat_dn} trunk; supply ${fmtNum(n.supply_c_peak_day)} °C on the peak day; network pumps ${fmtNum(n.pump_gwh, 2)} GWh a year`}>
          District network {fmtNum(n.length_km)} km: <strong>{fmtNum(n.heat_loss_share * 100)} % of the heat lost</strong>, supply up to {fmtNum(n.supply_c_max)} °C
        </span>
      )}
      {card.service && card.service.length > 0 && (
        <span className="chip" title={card.service.map((s) => `${s.unit} ${s.from}–${s.to}`).join("; ")}>
          Planned service built in: {card.service.length} windows ({card.service[0].unit} {card.service[0].from}–{card.service[0].to}
          {card.service.length > 1 ? ", …" : ""})
        </span>
      )}
      {card.solar && (
        <span className="chip" title={`${fmtNum(card.solar.generated_gwh, 2)} GWh a year; ${fmtNum(card.solar.sold_gwh, 2)} GWh sold; the plant still buys ${fmtNum(card.solar.bought_gwh, 2)} GWh`}>
          Own solar {fmtNum(card.solar.mwp)} MWp: <strong>{fmtNum(card.solar.used_gwh, 2)} GWh used by the plant</strong>
        </span>
      )}
      {card.storage && (
        <span className="chip" title={card.storage.note ? "The boiler's days had no geothermal heat to spare before them" : `Charged ${fmtNum(card.storage.charged_gwh, 2)} GWh, ${fmtNum(card.storage.lost_gwh, 2)} GWh lost; about ${fmtNum(card.storage.full_cycles ?? 0)} full cycles a year`}>
          Heat store {fmtNum(card.storage.capacity_mwh, 0)} MWh:{" "}
          <strong>{card.storage.note ? "nothing to move" : `${fmtNum(card.storage.boiler_saved_gwh, 2)} GWh less from the boiler`}</strong>
        </span>
      )}
    </div>
  );
}

/** Each pick's mark (16 × 16 strokes): what it is chosen for, at a glance. */
export const PICK_ICONS: Record<string, string> = {
  // A star.
  best: "M8 2.2l1.8 3.7 4 .6-2.9 2.8.7 4L8 11.4l-3.6 1.9.7-4L2.2 6.5l4-.6z",
  // A euro sign.
  cost: "M11.6 4.4A4.2 4.2 0 1 0 11.6 11.6M2.8 6.9h6.4M2.8 9.1h6.4",
  // A leaf.
  co2: "M3.2 12.8C3 7 6.6 3.4 12.8 3.2c.2 6.2-3.4 9.8-9.6 9.6zM3.2 12.8 8.6 7.4",
  // A shield.
  reliable: "M8 1.9l5 1.8v3.9c0 3.1-2.1 5.4-5 6.5-2.9-1.1-5-3.4-5-6.5V3.7z",
  // A shield with a leaf in it.
  green_reliable: "M8 1.9l5 1.8v3.9c0 3.1-2.1 5.4-5 6.5-2.9-1.1-5-3.4-5-6.5V3.7zM5.6 10.4c0-2.8 1.6-4.4 4.6-4.6.1 3-1.5 4.6-4.6 4.6zM5.6 10.4l2.4-2.4",
  // A flame, struck through: no gas bought.
  gas_free: "M8 2.2c2 2.7 3.8 4.2 3.8 6.9a3.8 3.8 0 0 1-7.6 0C4.2 6.7 6.2 5.6 8 2.2zM2.6 2.6l10.8 10.8",
};

/**
 * The search's picks (up to six) side by side, three to a row: each one's mark, what it costs
 * (a bar against the dearest pick), what it emits and whether any one unit can be out.
 */
export function PicksRow({ picks }: { picks: Pick[] }) {
  const dearest = Math.max(0, ...picks.map((p) => (Number.isFinite(p.lcoe) ? p.lcoe : 0)));
  return (
    <div className="picks" role="list" aria-label="The search's picks">
      {picks.map((p) => (
        <div key={p.key} role="listitem" className={`pick${p.chosen ? " chosen" : ""}`} title={p.rule} {...menuProps({ kind: "design", design: { id: p.id || p.uid, name: p.uid || p.code, sub: p.code } })}>
          <span className="pick-label">
            {PICK_ICONS[p.key] && (
              <svg className="pick-icon" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                <path d={PICK_ICONS[p.key]} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            {p.label}
            {p.chosen && <span className="pick-mark">recommended</span>}
          </span>
          <span className="pick-name">
            <span className="uid-chip small">{p.uid}</span>
            <span className="alt-code">{p.code}</span>
          </span>
          <strong className="pick-cost">
            {fmtNum(p.lcoe)} <span className="tile-unit">€/MWh</span>
          </strong>
          {dearest > 0 && (
            <span className="pick-bar" aria-hidden="true">
              <i className="ta-grow" style={{ width: `${Math.max(2, Math.min(100, (p.lcoe / dearest) * 100))}%` }} />
            </span>
          )}
          <span className="pick-sub">
            {p.vs_gas_pct?.total != null && <>{pctVsGas(p.vs_gas_pct.total)} · </>}
            {fmtNum(p.co2_t, 0)} t CO₂ · {fmtNum(p.capex_meur)} M€
          </span>
          <span className={`pick-firm${p.reliable ? " ok" : ""}`}>
            {p.reliable ? "any one unit out: met" : p.n1_short ? `one unit out: ${p.n1_short} cases short` : "one unit out: met"}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Firm capacity: the spare on the peak days, and what happens with each unit out all year. */
function FirmStrip({ firm }: { firm: Firm }) {
  const [open, setOpen] = useState(false);
  const short = firm.cases.filter((c) => c.short);
  const worst = short.reduce<typeof short[number] | null>((w, c) => (!w || c.worst_mw > w.worst_mw ? c : w), null);
  const peak = (["heat", "cool"] as const).map((k) => [k, firm.peak[k]] as const).filter(([, v]) => v);
  return (
    <div className={`firm${short.length ? "" : " ok"}`}>
      <div className="firm-row">
        <span className="firm-label">Spare on the peak day</span>
        {peak.map(([k, v]) => (
          <span key={k} className="firm-fig">
            {k === "heat" ? "heat" : "cold"} <strong>{fmtSigned(v!.spare_mw)} MW</strong> <span className="muted">({v!.day})</span>
          </span>
        ))}
      </div>
      <div className="firm-row">
        <span className="firm-label">One unit out</span>
        {short.length ? (
          <span className="firm-fig bad">
            {short.length} of {firm.cases.length} cases leave a day short; worst: {worst!.unit}, <strong>{fmtNum(worst!.worst_mw)} MW</strong> {worst!.side === "heat" ? "heat" : "cold"} short on {worst!.worst_day}
          </span>
        ) : (
          <span className="firm-fig good">
            all {firm.cases.length} cases met every day
            {firm.reliable ? ` (boiler ${firm.boiler_units} units, chillers ${firm.chiller_units} units)` : ""}
          </span>
        )}
        <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Each case"}
        </button>
      </div>
      {open && (
        <ul className="firm-cases">
          {firm.cases.map((c) => (
            <li key={c.unit} className={c.short ? "bad" : "good"}>
              {c.short ? <FailIcon size={14} /> : <DoneIcon size={14} />}
              <span>{c.unit} out</span>
              <span className="muted">
                {c.short ? `${c.side === "heat" ? "heat" : "cold"} short on ${c.days_short} days, worst ${fmtNum(c.worst_mw)} MW on ${c.worst_day}` : "every day met"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Tile({ label, color, value, unit, valueColor, headline, children }: { label: string; color?: string; value: string; unit: string; valueColor?: string; headline?: boolean; children?: ReactNode }) {
  return (
    <div className={`tile${headline ? " headline" : ""}`}>
      <span className="tile-label">
        {color && <span className="sq" style={{ background: color }} />}
        {label}
      </span>
      <strong className="tile-value" style={valueColor ? { color: valueColor } : undefined}>
        {unit === "%" || value === "–" ? (
          value + (value === "–" ? "" : "%")
        ) : (
          <>
            {value} <span className="tile-unit">{unit}</span>
          </>
        )}
      </strong>
      {children}
    </div>
  );
}

function Mini({ parts, total }: { parts: SplitPart[]; total: number }) {
  if (!total) return null;
  return (
    <span className="minibar" aria-hidden="true">
      {parts.map((p) => (
        <span key={p.key} className="ta-grow" style={{ width: `${(p.gwh / total) * 100}%`, background: p.color }} />
      ))}
    </span>
  );
}

function Split({ title, demand, parts }: { title: string; demand: number; parts: SplitPart[] }) {
  if (!demand) return null;
  const supplied = parts.reduce((a, p) => a + p.gwh, 0);
  const unmet = Math.max(0, demand - supplied);
  const pct = (v: number) => `${fmtNum((v / demand) * 100)}%`;
  const aria = `${title}: ${parts.map((p) => `${p.label} ${fmtNum(p.gwh)} GWh`).join(", ")}${unmet > 0.05 ? `, ${fmtNum(unmet)} GWh not covered` : ""}.`;
  return (
    <div className="split">
      <div className="split-head">
        <span>
          {title} over the year, <strong style={{ color: "#11181C", fontWeight: 650 }}>{fmtNum(demand)} GWh</strong>
        </span>
        {unmet > 0.05 && <strong style={{ color: "#A12C22", fontWeight: 650 }}>{fmtNum(unmet)} GWh short</strong>}
      </div>
      <div className="split-bar" role="img" aria-label={aria}>
        {parts.map((p) => (
          <span key={p.key} className="ta-grow" style={{ width: `${(p.gwh / demand) * 100}%`, background: p.color }} />
        ))}
        {unmet > 0.05 && <span className="gap-fill" style={{ flex: "1 1 auto", minWidth: 6 }} />}
      </div>
      <div className="legend-row">
        {parts.map((p) => (
          <span key={p.key}>
            <span className="sq" style={{ background: p.color }} />
            {p.label} {pct(p.gwh)}
          </span>
        ))}
        {unmet > 0.05 && (
          <span>
            <span className="sq gap-fill" style={{ width: 10, height: 10 }} />
            <strong style={{ color: "#A12C22", fontWeight: 650 }}>Not covered {pct(unmet)}</strong>
          </span>
        )}
      </div>
    </div>
  );
}

/** Why a design fails: each failed check, its value against its limit, and the input that would fix it. */
export function WhyItFails({ failed }: { failed: Check[] }) {
  return (
    <section className="why-fails ta-rise" aria-label="Why it fails">
      <h3 className="why-fails-title">
        <FailIcon size={15} />
        Why it fails
      </h3>
      <ul>
        {failed.map((c) => {
          const w = checkWords(c.name);
          return (
            <li key={c.name}>
              <span className="why-fails-what">
                <b>{c.name}</b>
                {c.detail && <span className="why-fails-value">{c.detail}</span>}
              </span>
              {w.fix && (
                <span className="why-fails-fix">
                  <span className="why-fails-fix-label">To fix</span> {w.fix}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function CheckList({ checks }: { checks: Check[] }) {
  return (
    <ul className="check-list ta-rise" aria-label="Verifier checks">
      {checks.map((c) => (
        <li key={c.name} className={`check-item${c.passed ? "" : " fail"}`}>
          {c.passed ? <DoneIcon size={16} /> : <FailIcon size={16} />}
          <span style={{ minWidth: 0 }}>
            <span style={{ fontWeight: 550 }}>
              <span className="sr-only">{c.passed ? "Passed: " : "Failed: "}</span>
              {c.name}
            </span>
            {c.requirement && (
              <span className="tag tag-grey" style={{ marginLeft: 6, fontSize: 11 }}>
                brief
              </span>
            )}
            <span className="check-detail">{c.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The design's operator's report (PDF), made by the server for this chat; none offline. */
function ReportLink({ id }: { id: string }) {
  const wb = useWorkbench();
  if (!wb.threadId || wb.fixture || wb.threadId.startsWith("replay-")) return null;
  const href = `/api/report.pdf?${new URLSearchParams({ threadId: wb.threadId, id })}`;
  return (
    <a
      href={href}
      title={`The operator's report of ${id}: see it, then save it (PDF, A4)`}
      onClick={(e) => {
        // A preview first, then Save (3 Nov).
        e.preventDefault();
        previewExport("report", wb.threadId!, id);
      }}
    >
      Operator report (PDF) <Arrow size={12} />
    </a>
  );
}
