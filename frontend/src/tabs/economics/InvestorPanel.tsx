// The investor's view on the Economics tab: what a company that builds and runs the plant would
// earn. It sells the heat and cold, gets SDE++ on its geothermal heat for 15 years and pays
// corporate tax; the plant's cost above has none of these, and the rankings use the plant's cost.
//
// A section of its own below the plant's cost: KPI tiles (NPV, IRR and payback after tax, SDE++
// a year, whether it needs SDE++), the cash flow by year as stacked columns (money in above the
// line, money out below, the net after tax as a line, the subsidy years shaded), the SDE++
// category with its basisbedrag and source, and the sale prices and SDE++ choices, which one PUT
// /api/assumptions changes. Every figure is the server's (economics.investor); this file only
// formats and draws. Tested in InvestorPanel.test.ts.

import "./investor.css";
import "../../workbench/components/workbench.css";

import { useId, useState, type KeyboardEvent, type PointerEvent } from "react";

import { Spinner } from "../../components/Icons";
import { niceTicks, useWidth } from "../../components/LineChart";
import {
  AskButton,
  ProvenanceChip,
  type ApiResult,
  type AssumptionsPatch,
  type Design,
  type Investor,
  type InvestorFlow,
  type InvestorInput,
  type Provenance,
  type Workbench,
} from "../../workbench";
import { Meter, Panel, SplitBar, Switch, TableToggle, Tile } from "../energy/parts";
import { parseField, same, type FieldDef } from "./assumptions";
import { eur, signed } from "./format";

type Apply = (patch: AssumptionsPatch) => Promise<ApiResult<Workbench>>;

type FlowKey = "revenue_heat" | "revenue_cold" | "sde" | "value_left" | "opex" | "tax" | "capital";

const CAPITAL = "#00879C";
const NET = "#11181C";
const SDE = "#199E70";

/**
 * The cash-flow chart's series, in stacking order: money in from the line up, money out from the
 * line down (each value goes to the side of its sign). Heat and cold take the app's heat and cold
 * hues, capital the Capital card's teal. Validated as a set with the dataviz palette script
 * (adjacent pairs pass CVD and normal vision on white; running costs' amber and SDE++'s aqua are
 * under 3:1, so the legend, the tooltip and the table carry every value too).
 */
export const FLOW_SERIES: { key: FlowKey; label: string; color: string }[] = [
  { key: "revenue_heat", label: "Heat sold", color: "#C24E1C" },
  { key: "revenue_cold", label: "Cold sold", color: "#2363A6" },
  { key: "sde", label: "SDE++", color: SDE },
  { key: "value_left", label: "Value left at the end", color: CAPITAL },
  { key: "opex", label: "Running costs", color: "#E3A33B" },
  { key: "tax", label: "Corporate tax", color: "#6250D6" },
  { key: "capital", label: "Units bought again", color: CAPITAL },
];

/** One coloured piece of a year's column: a series between two values (M€). */
export interface Segment {
  key: FlowKey;
  color: string;
  from: number;
  to: number;
}

/** A year's column: each non-zero series stacked away from zero on the side of its sign. */
export function stackYear(flow: InvestorFlow): Segment[] {
  let up = 0;
  let down = 0;
  const out: Segment[] = [];
  for (const s of FLOW_SERIES) {
    const v = flow[s.key];
    if (!Number.isFinite(v) || Math.abs(v) < 5e-4) continue;
    if (v > 0) {
      out.push({ key: s.key, color: s.color, from: up, to: up + v });
      up += v;
    } else {
      out.push({ key: s.key, color: s.color, from: down, to: down + v });
      down += v;
    }
  }
  return out;
}

/** A fraction as a percentage: 0.1606 → "16.1 %". */
export const pctText = (f: number | null | undefined, digits = 1) => (f != null && Number.isFinite(f) ? `${eur(f * 100, digits)} %` : "none");

/** Years with a tenth: 7.05 → "7.1 years"; null → "not within 30 years". */
export const yearsText = (y: number | null | undefined, horizon: number) => (y != null && Number.isFinite(y) ? `${eur(y)} years` : `not within ${horizon} years`);

/** €/kWh as €/MWh: 0.0799 → "79.9". */
const perMwh = (eurPerKwh: number) => eur(eurPerKwh * 1000);

interface Props {
  design: Design;
  prov: Provenance;
  setAssumptions: Apply;
  delay?: number;
}

/** The investor's section: nothing from a server that doesn't send it, a note for the gas plant. */
export function InvestorSection({ design, prov, setAssumptions, delay = 0.16 }: Props) {
  const id = useId();
  const inv = design.economics.investor;
  if (inv === undefined) return null;
  return (
    <section className="inv-section" aria-labelledby={`${id}-h`}>
      <header className="inv-head ta-rise" style={{ animationDelay: `${delay}s` }}>
        <div className="inv-head-titles">
          <span className="inv-eyebrow">Separate from the plant's cost</span>
          <h2 id={`${id}-h`}>Investor's view (with subsidy and tax)</h2>
          <p>
            What a company that builds and runs {design.code} would earn: it sells the heat and cold, gets SDE++ on its geothermal heat and pays corporate
            tax. The plant's cost above has none of these, and the design rankings use the plant's cost.
          </p>
        </div>
        {inv && (
          <AskButton
            context={`the investor's view of ${design.code} (NPV after tax ${signed(inv.npv_meur)} M€, SDE++ ${inv.sde.on ? "on" : "off"})`}
            question={`What would an investor earn on ${design.code}, with SDE++ and tax?`}
          />
        )}
      </header>
      {inv ? (
        <InvestorBody design={design} inv={inv} prov={prov} setAssumptions={setAssumptions} delay={delay} />
      ) : (
        <p className="ec-ref-note inv-gas ta-rise">
          <strong>{design.code} is the gas plant.</strong> Its cost of heat ({eur(design.economics.lcoh)} €/MWh)
          {design.economics.lcoc != null ? ` and of cold (${eur(design.economics.lcoc)} €/MWh)` : ""} is what the geothermal designs sell at by default: what
          the buyer would pay for its own gas boilers and electric chillers.
        </p>
      )}
    </section>
  );
}

function InvestorBody({ design, inv, prov, setAssumptions, delay }: { design: Design; inv: Investor; prov: Provenance; setAssumptions: Apply; delay: number }) {
  const [busy, setBusy] = useState(false);
  return (
    <div className={`inv-body${busy ? " pending" : ""}`} aria-busy={busy}>
      <InvestorTiles inv={inv} />
      <FlowPanel design={design} inv={inv} prov={prov} delay={delay + 0.02} />
      <div className="ec-pair">
        <SdePanel inv={inv} prov={prov} delay={delay + 0.04} />
        <ChoicesPanel inv={inv} setAssumptions={setAssumptions} onBusy={setBusy} delay={delay + 0.06} />
      </div>
      <details className="inv-notes ta-rise" style={{ animationDelay: `${delay + 0.08}s` }}>
        <summary>How the investor's figures are worked out</summary>
        <ul>
          {inv.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

// ------------------------------------------------------------------ tiles

export function InvestorTiles({ inv }: { inv: Investor }) {
  const rate = inv.discount_rate;
  const off = !inv.sde.on;
  const w = inv.without_sde;
  const s = inv.sde;
  const be = inv.break_even_basis_eur_per_kwh;
  return (
    <div className="ee-tiles ec-tiles inv-tiles ta-rise">
      <Tile
        label="NPV after tax"
        value={signed(inv.npv_meur)}
        valueTone={inv.npv_meur >= 0 ? "good" : "bad"}
        unit="M€"
        sub={`over ${inv.years} years at ${pctText(rate)} real; ${off ? "no SDE++" : `without SDE++ ${signed(w.npv_meur)} M€`}`}
      />
      <Tile
        label="IRR after tax"
        value={inv.irr != null ? eur(inv.irr * 100) : "none"}
        valueTone={inv.irr == null ? "muted" : undefined}
        unit={inv.irr != null ? "% real" : undefined}
        note={`cost of capital ${pctText(rate)}`}
        noteTone={inv.irr != null && inv.irr >= rate ? "good" : "bad"}
        sub={off ? "no SDE++" : `without SDE++ ${pctText(w.irr)}`}
      />
      <Tile
        label="Payback"
        value={inv.payback_years != null ? eur(inv.payback_years) : "none"}
        valueTone={inv.payback_years == null ? "muted" : undefined}
        unit={inv.payback_years != null ? "years" : undefined}
        sub={inv.payback_years == null ? `not within ${inv.years} years` : off ? "discounted, after tax" : `discounted; without SDE++ ${yearsText(w.payback_years, inv.years)}`}
      />
      <Tile
        label="SDE++ in year 1"
        swatch={SDE}
        value={off ? "off" : eur(s.meur_first_year, 2)}
        valueTone={off ? "muted" : undefined}
        unit={off ? undefined : "M€"}
        sub={
          off
            ? "switched off below"
            : `years ${s.first_year}–${s.last_year} (${s.calendar_years[0]}–${s.calendar_years[1]}); ${eur(s.meur_average, 2)} M€ a year on average in 2025 euros`
        }
      />
      <Tile
        label="Needs SDE++?"
        value={inv.needs_subsidy ? "Yes" : "No"}
        valueTone={inv.needs_subsidy ? "bad" : "good"}
        sub={
          inv.needs_subsidy
            ? be != null
              ? `breaks even at a basisbedrag of ${perMwh(be)} €/MWh (category: ${perMwh(s.basis_eur_per_kwh)})`
              : "no SDE++ makes it break even"
            : "breaks even without it, after tax"
        }
      />
    </div>
  );
}

// ------------------------------------------------------------------ cash flow by year

const HEIGHT = 250;
const TOP = 30;
const BOTTOM = 26;
const RIGHT = 12;

function FlowPanel({ design, inv, prov, delay }: { design: Design; inv: Investor; prov: Provenance; delay: number }) {
  const [table, setTable] = useState(false);
  const build = inv.flows[0];
  return (
    <Panel
      title="Cash flow by year, after tax"
      sub={`Money in above the line, money out below, in M€ of 2025. Year 0 is building: ${signed(build?.net ?? 0)} M€ (not drawn, in the table).`}
      delay={delay}
      aside={
        <>
          <ProvenanceChip source={prov} detail="Sales, SDE++ and tax from dioscuri_plant.investor, on the design's year and costs" />
          <TableToggle on={table} onChange={setTable} />
          <AskButton compact label="Ask about this chart" context={`${design.code}'s cash flow by year for an investor, on the Economics tab`} question={`Why does ${design.code}'s cash flow change over the years?`} />
        </>
      }
    >
      <div className="ee-legend">
        {FLOW_SERIES.filter((s) => s.key !== "value_left" && s.key !== "capital").map((s) => (
          <span key={s.key} className="ee-key">
            <span className="ee-swatch" style={{ background: s.color }} aria-hidden="true" />
            {s.label}
          </span>
        ))}
        <span className="ee-key">
          <span className="ee-swatch" style={{ background: CAPITAL }} aria-hidden="true" />
          Units bought again, value left at the end
        </span>
        <span className="ee-key">
          <svg width="16" height="8" viewBox="0 0 16 8" aria-hidden="true">
            <path d="M1 4h14" stroke={NET} strokeWidth="2" strokeLinecap="round" />
          </svg>
          Net after tax
        </span>
      </div>
      {table ? <FlowTable inv={inv} /> : <FlowChart inv={inv} code={design.code} />}
    </Panel>
  );
}

/** A column piece with its far end rounded (4px) and its near end square. */
function piece(x: number, w: number, yNear: number, yFar: number): string {
  const up = yFar < yNear;
  const h = Math.abs(yFar - yNear);
  const r = Math.min(4, w / 2, h);
  if (up)
    return `M${x} ${yNear}V${yFar + r}Q${x} ${yFar} ${x + r} ${yFar}H${x + w - r}Q${x + w} ${yFar} ${x + w} ${yFar + r}V${yNear}Z`;
  return `M${x} ${yNear}V${yFar - r}Q${x} ${yFar} ${x + r} ${yFar}H${x + w - r}Q${x + w} ${yFar} ${x + w} ${yFar - r}V${yNear}Z`;
}

function FlowChart({ inv, code }: { inv: Investor; code: string }) {
  const [wrap, width] = useWidth(720);
  const [hover, setHover] = useState<number | null>(null);
  const years = inv.flows.filter((f) => f.year >= 1);
  const n = years.length;
  if (!n) return <p className="ee-foot">No years to draw.</p>;
  const stacks = years.map(stackYear);
  const hi = Math.max(0, ...stacks.flat().map((s) => Math.max(s.from, s.to)), ...years.map((f) => f.net));
  const lo = Math.min(0, ...stacks.flat().map((s) => Math.min(s.from, s.to)), ...years.map((f) => f.net));
  const yt = niceTicks(lo, hi, 5);
  const ymin = Math.min(yt[0], lo);
  const ymax = Math.max(yt[yt.length - 1], hi);
  const labels = yt.map((t) => eur(t, 0));
  const left = Math.max(30, Math.max(...labels.map((l) => l.length)) * 6.6 + 12);
  const pw = Math.max(10, width - left - RIGHT);
  const ph = HEIGHT - TOP - BOTTOM;
  const band = pw / n;
  const bw = Math.max(3, Math.min(24, band - 4));
  const cx = (i: number) => left + band * (i + 0.5);
  const y = (v: number) => TOP + ((ymax - v) / (ymax - ymin || 1)) * ph;
  const zero = y(0);
  const s = inv.sde;
  const subsidy = s.on && s.meur_first_year > 0;
  const firstSde = years.findIndex((f) => f.year === s.first_year);
  const lastSde = years.findIndex((f) => f.year === s.last_year);
  const net = years.map((f, i) => `${i ? "L" : "M"}${cx(i).toFixed(1)} ${y(f.net).toFixed(1)}`).join("");
  const step = n <= 12 ? 1 : 5;
  const ticks = years.map((f, i) => ({ year: f.year, i })).filter((t) => t.year === 1 || t.year % step === 0);

  const pick = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.floor((e.clientX - box.left - left) / band);
    setHover(Math.max(0, Math.min(n - 1, i)));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const d = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
    if (d) setHover((h) => Math.max(0, Math.min(n - 1, (h ?? (d > 0 ? -1 : n)) + d)));
    else if (e.key === "Home") setHover(0);
    else if (e.key === "End") setHover(n - 1);
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };
  const hf = hover != null ? years[hover] : null;
  const hx = hover != null ? cx(hover) : 0;
  const summary =
    `${code}'s cash flow for an investor, years 1 to ${years[n - 1].year}, in M€ of 2025: ${signed(years[0].net)} net in year 1, ` +
    `${signed(years[n - 1].net)} in year ${years[n - 1].year}` +
    (subsidy ? `; SDE++ in years ${s.first_year} to ${s.last_year}` : "; no SDE++") +
    `. NPV after tax ${signed(inv.npv_meur)} M€. Arrow keys read one year at a time.`;

  return (
    <div ref={wrap}>
      <div className="ee-plot" tabIndex={0} role="group" aria-label={summary} onKeyDown={onKey} onBlur={() => setHover(null)}>
        <svg width={width} height={HEIGHT} aria-hidden="true" onPointerMove={pick} onPointerDown={pick} onPointerLeave={() => setHover(null)}>
          {subsidy && firstSde >= 0 && lastSde >= firstSde && (
            <g>
              <rect x={left + band * firstSde} y={TOP - 6} width={band * (lastSde - firstSde + 1)} height={ph + 6} fill={SDE} fillOpacity={0.07} rx={6} />
              <text x={left + band * firstSde + 6} y={TOP - 12} className="lc-label">
                SDE++ years {s.first_year}–{s.last_year} ({s.calendar_years[0]}–{s.calendar_years[1]})
              </text>
            </g>
          )}
          {yt.map((t, k) => (
            <g key={t}>
              <line x1={left} x2={left + pw} y1={y(t)} y2={y(t)} className="lc-grid" />
              <text x={left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="lc-tick">
                {labels[k]}
              </text>
            </g>
          ))}
          {stacks.map((segs, i) => {
            const x = cx(i) - bw / 2;
            // The outermost piece on each side gets the rounded end; pieces touch with a 2px gap.
            const lastUp = segs.filter((g) => g.to > g.from).at(-1);
            const lastDown = segs.filter((g) => g.to < g.from).at(-1);
            return (
              <g key={years[i].year} opacity={hover == null || hover === i ? 1 : 0.55}>
                {segs.map((g) => {
                  const up = g.to > g.from;
                  const near = y(g.from) + (g.from === 0 ? 0 : up ? -1 : 1);
                  const far = y(g.to) + (g === (up ? lastUp : lastDown) ? 0 : up ? 1 : -1);
                  if (up ? near - far < 0.5 : far - near < 0.5) return null;
                  const outer = g === (up ? lastUp : lastDown);
                  return outer ? (
                    <path key={g.key} d={piece(x, bw, near, far)} fill={g.color} />
                  ) : (
                    <rect key={g.key} x={x} y={Math.min(near, far)} width={bw} height={Math.abs(far - near)} fill={g.color} />
                  );
                })}
              </g>
            );
          })}
          <line x1={left} x2={left + pw} y1={zero} y2={zero} className="lc-axis" />
          <path d={net} fill="none" stroke="#fff" strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" />
          <path d={net} fill="none" stroke={NET} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {ticks.map((t) => (
            <text key={t.year} x={cx(t.i)} y={HEIGHT - 8} textAnchor="middle" className={`lc-tick${hover === t.i ? " on" : ""}`}>
              {t.year}
            </text>
          ))}
          {hf && (
            <g>
              <line x1={hx} x2={hx} y1={TOP - 4} y2={TOP + ph} className="lc-cross" />
              <circle cx={hx} cy={y(hf.net)} r={4.5} fill={NET} stroke="#fff" strokeWidth={2} />
            </g>
          )}
        </svg>
        {hf && <FlowTip f={hf} x={hx} flip={hx > left + pw * 0.6} />}
        <span className="ee-sr" aria-live="polite">
          {hf ? `Year ${hf.year}: ${FLOW_SERIES.filter((x) => Math.abs(hf[x.key]) >= 5e-4).map((x) => `${x.label} ${signed(hf[x.key], 2)}`).join(", ")}; net ${signed(hf.net, 2)} M€.` : ""}
        </span>
      </div>
      <p className="ee-xcap">Years after building</p>
    </div>
  );
}

function FlowTip({ f, x, flip }: { f: InvestorFlow; x: number; flip: boolean }) {
  return (
    <div className={`ee-tip${flip ? " flip" : ""}`} style={{ left: x }} aria-hidden="true">
      <span className="ee-tip-title">Year {f.year}</span>
      <span className="ee-tip-sub">M€ of 2025</span>
      {FLOW_SERIES.filter((s) => Math.abs(f[s.key]) >= 5e-4).map((s) => (
        <span key={s.key} className="ee-tip-row">
          <span className="ee-swatch" style={{ background: s.color }} />
          <strong>{signed(f[s.key], 2)}</strong>
          <span className="n">{s.label}</span>
        </span>
      ))}
      <span className="ee-tip-row total">
        <strong>{signed(f.net, 2)}</strong>
        <span className="n">net after tax</span>
      </span>
      <span className="ee-tip-row">
        <strong>{signed(f.cumulative, 2)}</strong>
        <span className="n">so far, discounted</span>
      </span>
    </div>
  );
}

function FlowTable({ inv }: { inv: Investor }) {
  const cols = FLOW_SERIES;
  return (
    <div className="ftable-wrap" role="region" aria-label="The investor's cash flow by year, M€ of 2025" tabIndex={0}>
      <table className="ftable inv-table">
        <thead>
          <tr>
            <th scope="col">Year</th>
            {cols.map((c) => (
              <th key={c.key} scope="col" className="n">
                {c.label}
              </th>
            ))}
            <th scope="col" className="n">
              Net after tax
            </th>
            <th scope="col" className="n">
              So far, discounted
            </th>
          </tr>
        </thead>
        <tbody>
          {inv.flows.map((f) => (
            <tr key={f.year}>
              <td>{f.year}</td>
              {cols.map((c) => (
                <td key={c.key} className="n">
                  {Math.abs(f[c.key]) >= 5e-4 ? signed(f[c.key], 2) : "–"}
                </td>
              ))}
              <td className="n">
                <strong>{signed(f.net, 2)}</strong>
              </td>
              <td className="n">{signed(f.cumulative, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------ SDE++

/** A small chip that names a source and shows it in full on hover or focus. */
export function SourceChip({ label, source }: { label: string; source: string }) {
  return (
    <span className="prov prov-rule inv-source" tabIndex={0} role="note" aria-label={`Source: ${source}`}>
      {label}
      <span className="wb-tip" aria-hidden="true">
        {source}
      </span>
    </span>
  );
}

const GAS_PART = "#9AA5AB";
const CO2_PART = "#C9D1D4";

export function SdePanel({ inv, prov, delay }: { inv: Investor; prov: Provenance; delay?: number }) {
  const s = inv.sde;
  const c = s.category;
  const basis = s.basis_eur_per_kwh;
  const later = s.per_kwh_later;
  const parts = [
    { key: "paid", value: later, color: SDE },
    { key: "co2", value: s.ets_from_year <= s.last_year ? s.ets_eur_per_kwh : 0, color: CO2_PART },
    { key: "gas", value: s.correction_eur_per_kwh, color: GAS_PART },
  ];
  const co2From = s.ets_from_year <= 1 ? "every year" : `from year ${s.ets_from_year} (${c.ets_from})`;
  return (
    <Panel
      title="SDE++ subsidy"
      sub={s.on ? `${eur(s.meur_first_year, 2)} M€ in year 1, for ${s.last_year} years; cooling earns none` : "Switched off: the figures above are without any subsidy"}
      delay={delay}
      className="ec-fill"
      aside={
        <>
          <SourceChip label="PBL 2026" source={c.source} />
          <ProvenanceChip source={prov} detail="The category from the plant's geothermal capacity; SDE++ on the exchanger's and heat pump's heat" />
        </>
      }
    >
      <div className="inv-cat">
        <div className="inv-cat-name">
          <strong>{c.label}</strong>
          <span className="inv-cat-official">{c.name}</span>
        </div>
        <div className="inv-cat-chips">
          <span className="inv-chip">{s.chosen_by === "size" ? "chosen by capacity" : "picked by you"}</span>
          {!s.fits && <span className="inv-chip warn">outside its size range</span>}
        </div>
      </div>

      <dl className="inv-figs">
        <div>
          <dt>Basisbedrag</dt>
          <dd>
            <strong>{perMwh(basis)}</strong> <span className="ec-unit">€/MWh</span>
          </dd>
        </div>
        <div>
          <dt>Full-load hours</dt>
          <dd>
            <strong>{eur(c.full_load_hours, 0)}</strong> <span className="ec-unit">h a year</span>
          </dd>
        </div>
        <div>
          <dt>Geothermal capacity</dt>
          <dd>
            <strong>{eur(s.capacity_mw)}</strong> <span className="ec-unit">MW</span>
          </dd>
        </div>
      </dl>

      <div className="inv-block">
        <span className="inv-block-label">
          What SDE++ pays on a MWh of geothermal heat{s.ets_from_year > 1 ? ` from ${c.ets_from}` : ""}: the basisbedrag less the corrections
        </span>
        <SplitBar
          parts={parts}
          total={basis}
          label={`Of ${perMwh(basis)} €/MWh: ${perMwh(later)} paid, ${perMwh(parts[1].value)} CO₂ correction, ${perMwh(s.correction_eur_per_kwh)} gas-price correction`}
        />
        <div className="ee-legend inv-legend">
          <span className="ee-key">
            <span className="ee-swatch" style={{ background: SDE }} aria-hidden="true" />
            Paid {perMwh(later)} €/MWh{s.per_kwh_first !== later ? ` (${perMwh(s.per_kwh_first)} in year 1)` : ""}
          </span>
          {parts[1].value > 0 && (
            <span className="ee-key">
              <span className="ee-swatch" style={{ background: CO2_PART }} aria-hidden="true" />
              CO₂ correction {perMwh(s.ets_eur_per_kwh)}, {co2From}
            </span>
          )}
          <span className="ee-key">
            <span className="ee-swatch" style={{ background: GAS_PART }} aria-hidden="true" />
            Gas-price correction {perMwh(s.correction_eur_per_kwh)} (floor {perMwh(s.floor_eur_per_kwh)})
          </span>
        </div>
      </div>

      <div className="inv-block ec-panel-end">
        <span className="inv-block-label">
          Heat that earns SDE++: <strong>{eur(s.subsidised_gwh)}</strong> of {eur(s.cap_gwh)} GWh a year
          {s.capped ? ` (capped: ${eur(s.eligible_gwh)} GWh of geothermal heat)` : ""}
        </span>
        <Meter value={s.subsidised_gwh} max={Math.max(s.cap_gwh, s.eligible_gwh)} color={SDE} label={`${eur(s.subsidised_gwh)} of ${eur(s.cap_gwh)} GWh a year earns SDE++`} />
        <span className="ee-foot">
          Capacity {eur(s.capacity_mw)} MW: {eur(s.flow_m3h, 0)} m³/h of brine cooled {eur(s.brine_cooling_k)} K; the cap is capacity × {eur(c.full_load_hours, 0)} h.
        </span>
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------------ sale prices and choices

const fieldOf = (it: InvestorInput): FieldDef => ({ id: it.key, label: it.label, unit: it.unit, group: "investor", source: it.source, min: 0, max: 2000 });

/** The PUT /api/assumptions patch for typed sale prices: a new value, or null when back at the default. */
export function salePatch(edits: Record<string, string>, inputs: InvestorInput[]): { patch: AssumptionsPatch; errors: Record<string, string> } {
  const patch: AssumptionsPatch = {};
  const errors: Record<string, string> = {};
  for (const it of inputs) {
    const text = edits[it.key];
    if (it.kind !== "number" || text == null) continue;
    const p = parseField(text, fieldOf(it));
    if (!p.ok) {
      errors[it.key] = p.error;
      continue;
    }
    if (typeof it.value === "number" && same(p.value, it.value)) continue;
    patch[it.key] = typeof it.default === "number" && same(p.value, it.default) ? null : p.value;
  }
  return { patch, errors };
}

export function ChoicesPanel({ inv, setAssumptions, onBusy, delay }: { inv: Investor; setAssumptions: Apply; onBusy?: (b: boolean) => void; delay?: number }) {
  const uid = useId();
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prices = inv.inputs.filter((it) => it.kind === "number");
  const category = inv.inputs.find((it) => it.key === "sde_category");
  const sdeOn = inv.inputs.find((it) => it.key === "sde_on");
  const { patch, errors } = salePatch(edits, inv.inputs);
  const nPatch = Object.keys(patch).length;
  const nErrors = Object.keys(errors).length;

  const send = async (p: AssumptionsPatch) => {
    setPending(true);
    onBusy?.(true);
    setError(null);
    const res = await setAssumptions(p);
    setPending(false);
    onBusy?.(false);
    if (res.ok) setEdits({});
    else setError(res.offline ? "The agent server isn't answering; nothing changed." : res.message);
  };
  const apply = () => {
    if (nPatch && !nErrors && !pending) void send(patch);
  };
  const revenue: Record<string, { meur: number; gwh: number }> = {
    heat_sale_eur_per_mwh: { meur: inv.revenue_heat_meur, gwh: inv.heat_sold_gwh },
    cold_sale_eur_per_mwh: { meur: inv.revenue_cold_meur, gwh: inv.cold_sold_gwh },
  };

  return (
    <Panel title="Sale prices and subsidy" sub="What the investor sells at and what it gets; Apply recomputes this section for every design" delay={delay} className="ec-fill inv-choices">
      <form
        className="inv-form"
        onSubmit={(e) => {
          e.preventDefault();
          apply();
        }}
      >
        {prices.map((it) => {
          const id = `${uid}-${it.key}`;
          const text = edits[it.key];
          const shown = text ?? String(it.value);
          const err = errors[it.key];
          const edited = text != null && it.key in patch;
          const r = revenue[it.key];
          return (
            <div key={it.key} className={`ec-field${it.changed ? " changed" : ""}${edited ? " edited" : ""}${err ? " invalid" : ""}`}>
              <div className="ec-field-row">
                <label htmlFor={id} className="ec-field-label">
                  {it.label}
                  {it.changed && !edited && (
                    <span className="ec-changed">
                      <span className="ec-dot" aria-hidden="true" />
                      yours
                    </span>
                  )}
                  {edited && <span className="ec-edited">not applied</span>}
                </label>
                <span className="ec-input">
                  <input
                    id={id}
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    spellCheck={false}
                    value={shown}
                    disabled={pending}
                    aria-invalid={!!err}
                    aria-describedby={`${id}-help`}
                    onChange={(e) => setEdits((x) => ({ ...x, [it.key]: e.target.value }))}
                  />
                  <span className="ec-input-unit">{it.unit}</span>
                </span>
              </div>
              <div className="ec-field-foot">
                <span id={`${id}-help`} className="ec-help">
                  {r && (
                    <>
                      <strong className="inv-rev">{eur(r.meur, 2)} M€ a year</strong> for {eur(r.gwh)} GWh ·{" "}
                    </>
                  )}
                  Default {typeof it.default === "number" ? eur(it.default) : String(it.default)} {it.unit}, the gas plant's cost{" "}
                  {it.source && <SourceChip label="source" source={it.source} />}
                </span>
                {it.changed && (
                  <button type="button" className="link-btn ec-reset" disabled={pending} onClick={() => void send({ [it.key]: null })}>
                    Reset
                  </button>
                )}
              </div>
              {err && (
                <p className="ec-field-error" role="alert">
                  {err}
                </p>
              )}
            </div>
          );
        })}
        {(nPatch > 0 || nErrors > 0) && (
          <div className="inv-apply">
            <button type="submit" className="btn btn-ink ta-btn ta-ink" disabled={!nPatch || nErrors > 0 || pending}>
              {pending ? <Spinner size={14} light /> : null}
              {pending ? "Applying" : "Apply"}
            </button>
            <button type="button" className="btn btn-soft ta-btn ta-soft" disabled={pending} onClick={() => setEdits({})}>
              Discard
            </button>
          </div>
        )}
      </form>

      {sdeOn && (
        <div className="inv-row">
          <span className="ec-field-label">SDE++</span>
          <Switch
            label="SDE++ subsidy"
            options={[
              { id: "on", label: "With" },
              { id: "off", label: "Without" },
            ]}
            value={sdeOn.value === false ? "off" : "on"}
            onChange={(v) => {
              if (!pending && (v === "on") !== (sdeOn.value !== false)) void send({ sde_on: v === "on" ? null : false });
            }}
          />
        </div>
      )}
      {category && (
        <div className="inv-row inv-row-col">
          <label htmlFor={`${uid}-cat`} className="ec-field-label">
            SDE++ category
            {category.changed && (
              <span className="ec-changed">
                <span className="ec-dot" aria-hidden="true" />
                yours
              </span>
            )}
          </label>
          <select
            id={`${uid}-cat`}
            className="inv-select"
            value={String(category.value)}
            disabled={pending}
            onChange={(e) => void send({ sde_category: e.target.value === "auto" ? null : e.target.value })}
          >
            {(category.options ?? []).map((o) => (
              <option key={o.key} value={o.key}>
                {o.basis_eur_per_kwh != null ? `${o.label} · ${perMwh(o.basis_eur_per_kwh)} €/MWh, ${eur(o.full_load_hours ?? 0, 0)} h` : o.label}
              </option>
            ))}
          </select>
          <span className="ec-help">
            By capacity picks the base-load category for the plant's size. The "with heat pump" categories assume the heat pump lifts all the geothermal heat;
            here it only tops up after the exchanger.
          </span>
        </div>
      )}
      <span className="ec-status inv-status" role="status" aria-live="polite">
        {error ? (
          <span className="ec-error">{error}</span>
        ) : pending ? (
          <span className="ec-pending">
            <Spinner size={14} /> Recomputing…
          </span>
        ) : nErrors ? (
          `Fix ${nErrors} value${nErrors === 1 ? "" : "s"} first`
        ) : (
          ""
        )}
      </span>
    </Panel>
  );
}
