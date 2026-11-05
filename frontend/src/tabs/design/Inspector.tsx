// The Plant view's inspector: the part picked on the canvas, on the chosen day (load ring, MW),
// over the year (a sparkline you can click), its values, its share of the year, the verifier's
// checks about it, who computed it, and a question for the chat.

import { Cross, Tick } from "../../components/Icons";
import { AskButton, ProvenanceChip, type Design, type GraphNode } from "../../workbench";
import { NodeIssues } from "./IssuesPanel";
import { LoadRing, partToday } from "./PlantCanvas";
import { YearStrip } from "./YearStrip";
import {
  dateLabel,
  doubletOf,
  doubletRow,
  doubletsText,
  fmtValue,
  fmtWithUnit,
  gasModeOf,
  iconOf,
  injectorsOf,
  isFlagValue,
  isWell,
  meanOf,
  metaOf,
  nodeProvenance,
  onDay as valueOn,
  openingWords,
  partNote,
  relatedChecks,
  seriesWords,
  shortLabel,
  trainMembers,
  trainYear,
  valueLabel,
  wellDay,
  wellOpening,
  wellYear,
  yearShare,
} from "./plant";

interface Props {
  design: Design;
  node: GraphNode;
  day: number;
  onDay: (day: number) => void;
  geminiDetail?: string;
}

/** "A1 heat pump (4.55 MW, COP 4.29)": what the chat is asked about. */
export function askContext(design: Design, node: GraphNode): string {
  const facts = Object.entries(node.values)
    .filter(([k]) => !isFlagValue(k))
    .slice(0, 3)
    .map(([k, v]) => (k === "cop" ? `COP ${fmtValue(v)}` : fmtWithUnit(v, node.units[k])));
  return `${design.code} ${shortLabel(node.label).toLowerCase()}${facts.length ? ` (${facts.join(", ")})` : ""}`;
}

/** A well or a treatment train over the year: the brine through it, m³/h, day by day. */
function BrineYear({ design, node, day, onDay: pick }: Props) {
  const meta = metaOf(node.type);
  const well = isWell(node.type) ? wellYear(design, node) : null;
  const train = node.type === "treatment" ? trainYear(design, node.id) : null;
  const flow = well?.flow ?? train?.flow;
  const cap = well?.cap ?? train?.cap ?? 0;
  if (!flow) return null;
  const today = valueOn(flow, day);
  const w = well ? wellDay(design, node, day) : null;
  const producer = node.type === "producer_well";
  const what = producer ? "brine produced" : node.type === "injector_well" ? "brine injected" : "brine treated";
  const temps = well ? well.temperature : [];
  const tToday = w?.temperature ?? null;
  const tMean = meanOf(temps);
  return (
    <>
      <div className="dz-insp-today">
        <LoadRing value={cap > 0 ? today / cap : 0} size={64} stroke={7} color={meta.color} label={`${Math.round(cap > 0 ? (today / cap) * 100 : 0)}% of its ${fmtValue(cap)} m³/h on ${dateLabel(day)}`} />
        <div className="dz-insp-num">
          <span>
            <strong>{fmtValue(today)}</strong> m³/h
          </span>
          <span>
            {what} on {dateLabel(day)}
            {tToday != null ? `, at ${fmtValue(tToday)} °C` : ""}
          </span>
        </div>
      </div>
      <div className="dz-insp-year">
        <span className="dz-insp-cap">Over the year, m³/h{well && tMean != null ? ` · ${producer ? "wellhead" : "reinjection"} ${fmtValue(tMean)} °C on average when on` : ""}</span>
        <YearStrip
          series={[{ label: shortLabel(node.label), values: flow, color: meta.color }]}
          day={day}
          onDay={pick}
          height={52}
          label={`${shortLabel(node.label)} over the year, daily m³/h; most ${fmtValue(Math.max(...flow))} m³/h against a cap of ${fmtValue(cap)}`}
        />
        <div className="dz-insp-axis" aria-hidden="true">
          <span>Jan</span>
          <span>Jul</span>
          <span>Dec</span>
        </div>
      </div>
    </>
  );
}

/** The few facts that place a well (its doublet, depth, open part) or a train (its doublets). */
function placeFacts(design: Design, node: GraphNode): [string, string][] {
  if (isWell(node.type)) {
    const d = doubletOf(node);
    const row = doubletRow(design, d);
    const open = wellOpening(node, row, design.plant.reservoir?.thickness_m ?? 100);
    const out: [string, string][] = [
      ["Doublet", `${d}${row ? `, aquifer at ${fmtValue(row.depth_m)} m` : ""}`],
      ["Open part", `${openingWords(open)}${Number.isFinite(node.values.depth_m) ? `, middle at ${fmtValue(node.values.depth_m)} m` : ""}`],
    ];
    if (node.type === "injector_well" && injectorsOf(design, d) > 1) out.push(["Share", `half of doublet ${d}'s brine`]);
    return out;
  }
  if (node.type === "treatment") return [["Takes the brine of", doubletsText(trainMembers(design.graph, node.id))]];
  return [];
}

/**
 * The CO₂ of sold gas, kept apart: this plant's year (its total) beside what the buyer emits
 * burning the methane it bought, hatched and outside the plant's total.
 */
export function SoldCo2({ design, node }: { design: Design; node: GraphNode }) {
  const plant = design.year.co2_t?.total ?? design.economics.co2_t_per_year;
  const buyer = node.values.buyer_co2_t ?? 0;
  const max = Math.max(plant, buyer) || 1;
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  return (
    <div className="dz-co2" role="img" aria-label={`CO₂ a year: this plant ${fmtValue(plant)} t; the buyer of the gas, burning it, ${fmtValue(buyer)} t, not in this plant's total`}>
      <span className="dz-insp-cap">CO₂ a year</span>
      <div className="dz-co2-row">
        <span className="dz-co2-name">This plant</span>
        <span className="dz-co2-bar">
          <i style={{ width: pct(plant) }} />
        </span>
        <span className="dz-co2-fig">{fmtValue(plant)} t</span>
      </div>
      <div className="dz-co2-row is-out">
        <span className="dz-co2-name">Buyer burns the gas</span>
        <span className="dz-co2-bar">
          <i style={{ width: pct(buyer) }} />
        </span>
        <span className="dz-co2-fig">{fmtValue(buyer)} t</span>
      </div>
      <span className="dz-co2-foot">The buyer's CO₂ is not counted in this plant's.</span>
    </div>
  );
}

export function Inspector({ design, node, day, onDay, geminiDetail }: Props) {
  const brine = isWell(node.type) || node.type === "treatment";
  if (brine) return <BrineInspector design={design} node={node} day={day} onDay={onDay} geminiDetail={geminiDetail} />;
  const meta = metaOf(node.type);
  const today = partToday(design, node, day);
  const share = yearShare(design, node.type);
  const checks = relatedChecks(node.type, design.checks);
  const prov = nodeProvenance(design, node);
  const gas = node.type === "gas" ? gasModeOf(node) : null;
  const note = partNote(design, node);
  const status = gas === "sell"
    ? "Cleaned and sold to the gas grid, all year"
    : today
    ? today.series.follows
      ? today.off
        ? "Idle on this day"
        : gas === "produced"
          ? "Burning the brine's gas on this day"
          : "Burning gas on this day"
      : today.off
        ? "Off on this day"
        : `At ${Math.round(today.load * 100)}% of its ${node.type.startsWith("demand") || node.type === "grid" || node.type === "tower" ? "peak" : "size"} on ${dateLabel(day)}`
    : node.type === "producer_well" || node.type === "injector_well"
      ? "Runs all year at the design flow"
      : "Fixed through the year";
  const sized = today && !today.series.follows && today.series.capacity > 0 && !node.type.startsWith("demand") && today.series.kind !== "power" && today.series.kind !== "reject";
  const hours = sized ? today.series.values.reduce((a, b) => a + b, 0) * 24 / today.series.capacity : null;
  const values = Object.entries(node.values).filter(([k]) => !isFlagValue(k));

  return (
    <div className="dz-insp" aria-live="polite">
      <div className="dz-insp-head">
        <span className="dz-insp-icon" style={{ background: meta.tint }} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 16 16">
            <path d={iconOf(node)} fill="none" stroke={meta.color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <div className="dz-insp-title">
          <h2>{node.label}</h2>
          <span className={today?.off ? "is-off" : ""}>{status}</span>
        </div>
        <ProvenanceChip source={prov} detail={prov === "gemini" ? geminiDetail : undefined} />
      </div>

      <NodeIssues design={design} nodeId={node.id} />

      {today && !today.series.follows && (
        <div className="dz-insp-today">
          <LoadRing value={today.load} size={64} stroke={7} color={meta.color} label={`${Math.round(today.load * 100)}% load on ${dateLabel(day)}`} />
          <div className="dz-insp-num">
            <span>
              <strong>{fmtValue(today.mw)}</strong> MW
            </span>
            <span>
              {seriesWords(today.series.kind, node.type.startsWith("demand"))} on {dateLabel(day)}
            </span>
          </div>
        </div>
      )}

      {today && (
        <div className="dz-insp-year">
          <span className="dz-insp-cap">Over the year{today.series.follows ? " (the gas boiler's heat)" : ""}</span>
          <YearStrip
            series={[{ label: node.label, values: today.series.values, color: meta.color }]}
            day={day}
            onDay={onDay}
            height={52}
            label={`${node.label} over the year, daily MW; peak ${fmtValue(Math.max(...today.series.values))} MW`}
          />
          <div className="dz-insp-axis" aria-hidden="true">
            <span>Jan</span>
            <span>Jul</span>
            <span>Dec</span>
          </div>
        </div>
      )}

      {note && <p className="dz-insp-note">{note}</p>}
      {gas === "sell" && <SoldCo2 design={design} node={node} />}

      {(values.length > 0 || share || hours != null) && (
        <dl className="dz-facts">
          {share && (
            <div>
              <dt>{share.of === "covered" ? "Covered" : "Share of the year"}</dt>
              <dd>
                {fmtValue(share.share * 100)}% {share.of === "covered" ? "" : share.of}
              </dd>
            </div>
          )}
          {hours != null && (
            <div>
              <dt>Full-load hours</dt>
              <dd>{Math.round(hours).toLocaleString("en-US")} h</dd>
            </div>
          )}
          {values.map(([k, v]) => (
            <div key={k}>
              <dt>{valueLabel(k)}</dt>
              <dd>{k === "cop" || k === "carnot_cop" ? fmtValue(v) : fmtWithUnit(v, node.units[k])}</dd>
            </div>
          ))}
        </dl>
      )}

      {checks.length > 0 && (
        <div className="dz-insp-checks">
          <span className="dz-insp-cap">
            Checks on it · {checks.filter((c) => c.passed).length} of {checks.length} pass
          </span>
          <ul>
            {checks.map((c) => (
              <li key={c.name} className={c.passed ? "pass" : "fail"}>
                <span className="dz-check-icon" aria-hidden="true">
                  {c.passed ? <Tick size={11} /> : <Cross size={9} />}
                </span>
                <span>
                  <span className="sr-only">{c.passed ? "Passes: " : "Fails: "}</span>
                  {c.name}
                  {!c.passed && c.detail && <span className="dz-check-detail">{c.detail}</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <AskButton context={askContext(design, node)} />
    </div>
  );
}

/** A well or a treatment train: the brine through it on the day and over the year, where it is, its values. */
function BrineInspector({ design, node, day, onDay, geminiDetail }: Props) {
  const meta = metaOf(node.type);
  const prov = nodeProvenance(design, node);
  const checks = relatedChecks(node.type, design.checks);
  const w = isWell(node.type) ? wellDay(design, node, day) : null;
  const train = node.type === "treatment" ? trainYear(design, node.id) : null;
  const status = w
    ? w.on
      ? `At ${Math.round(w.load * 100)}% of its ${fmtValue(w.cap)} m³/h on ${dateLabel(day)}`
      : w.stopped
        ? `Stopped on ${dateLabel(day)}: its doublet's planned stop`
        : `Off on ${dateLabel(day)}`
    : train
      ? `${fmtValue(valueOn(train.flow, day))} of ${fmtValue(train.cap)} m³/h on ${dateLabel(day)}`
      : "Separates the gas and filters the brine";
  const values = Object.entries(node.values).filter(([k]) => !isFlagValue(k) && k !== "doublet" && k !== "doublets");
  return (
    <div className="dz-insp" aria-live="polite">
      <div className="dz-insp-head">
        <span className="dz-insp-icon" style={{ background: meta.tint }} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 16 16">
            <path d={iconOf(node)} fill="none" stroke={meta.color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <div className="dz-insp-title">
          <h2>{shortLabel(node.label)}</h2>
          <span className={w && !w.on ? "is-off" : ""}>{status}</span>
        </div>
        <ProvenanceChip source={prov} detail={prov === "gemini" ? geminiDetail : undefined} />
      </div>

      <NodeIssues design={design} nodeId={node.id} />

      <BrineYear design={design} node={node} day={day} onDay={onDay} />

      <dl className="dz-facts">
        {placeFacts(design, node).map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
        {values.map(([k, v]) => (
          <div key={k}>
            <dt>{valueLabel(k)}</dt>
            <dd>{fmtWithUnit(v, node.units[k])}</dd>
          </div>
        ))}
      </dl>

      {checks.length > 0 && (
        <div className="dz-insp-checks">
          <span className="dz-insp-cap">
            Checks on it · {checks.filter((c) => c.passed).length} of {checks.length} pass
          </span>
          <ul>
            {checks.map((c) => (
              <li key={c.name} className={c.passed ? "pass" : "fail"}>
                <span className="dz-check-icon" aria-hidden="true">
                  {c.passed ? <Tick size={11} /> : <Cross size={9} />}
                </span>
                <span>
                  <span className="sr-only">{c.passed ? "Passes: " : "Fails: "}</span>
                  {c.name}
                  {!c.passed && c.detail && <span className="dz-check-detail">{c.detail}</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <AskButton context={askContext(design, node)} />
    </div>
  );
}
