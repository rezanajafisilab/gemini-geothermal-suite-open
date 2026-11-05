// The Energy tab's chart cards: the year day by day, the load-duration curve and the months. Each
// reads one side (heat or cold) of the design in the picker.

import { useMemo, useState } from "react";

import type { MonthlyGwh } from "../../agent/types";
import { MonthlyChart } from "../../components/MonthlyChart";
import { menuProps, type MenuTarget } from "../../menu";
import { AskButton, ProvenanceChip, fmtNum, type Design, type Provenance } from "../../workbench";
import {
  MONTH_NAMES,
  MONTH_START,
  MONTHS,
  SIDE_KEYS,
  SOURCE_META,
  INK,
  activeIndices,
  dayLabel,
  durationRows,
  peakIndex,
  shortRuns,
  sideShares,
  yearQuestion,
  type DayRow,
  type Side,
} from "./model";
import { Key, Panel, TableToggle } from "./parts";
import { StackChart, type XTick } from "./StackChart";

const SIDE_NAME: Record<Side, string> = { heat: "Heat", cool: "Cold" };

/** Month labels centred in each month, with a grid line at each month's start. */
export function monthTicks(pw: number, n: number): XTick[] {
  if (n < 300) return [];
  const band = pw / 12;
  const every = band >= 16 ? 1 : 3;
  const out: XTick[] = [];
  for (let m = 0; m < 12; m++) {
    const next = m < 11 ? MONTH_START[m + 1] : 365;
    if (m > 0) out.push({ at: MONTH_START[m], label: "", grid: true });
    if (m % every === 0) out.push({ at: (MONTH_START[m] + next - 1) / 2, label: band >= 34 ? MONTHS[m] : MONTHS[m][0] });
  }
  return out;
}

/** Day counts along the duration curve: 1, 50, 100 … 365 (fewer when narrow). */
function rankTicks(pw: number, n: number): XTick[] {
  const step = pw >= 520 ? 50 : 100;
  const out: XTick[] = [{ at: 0, label: "1" }];
  for (let d = step; d < n - step * 0.4; d += step) out.push({ at: d - 1, label: String(d), grid: true });
  out.push({ at: n - 1, label: String(n) });
  return out;
}

const dateTitle = (r: DayRow) => dayLabel(r.day);
const rankSub = (_r: DayRow, i: number) => `demand at or above this on ${i + 1} day${i ? "s" : ""} a year`;

/** Which series the stack draws: all that supply anything, or only the one picked (when it supplies). */
export function shownSeries(active: number[], keys: string[], only: string | null | undefined): number[] {
  const one = only ? active.filter((k) => keys[k] === only) : [];
  return one.length ? one : active;
}

/** A legend entry's menu: show only its series, or all of them again. */
function seriesKey(label: string, key: string, only: string | null | undefined, onOnly?: (k: string | null) => void) {
  if (!onOnly) return undefined;
  const target: MenuTarget = { kind: "series", label, only: only === key, showOnly: () => onOnly(key), showAll: () => onOnly(null) };
  return { tabIndex: 0, title: only === key ? `Only ${label} is shown (right-click to show all)` : `Right-click to show only ${label}`, className: only && only !== key ? "is-off" : undefined, ...menuProps(target) };
}

/** "Only Geothermal · Show all": the filter on screen, said and undone in one place. */
function OnlyNote({ only, onOnly }: { only: string | null | undefined; onOnly?: (k: string | null) => void }) {
  if (!only || !onOnly || !SOURCE_META[only]) return null;
  return (
    <span className="ee-only">
      Showing only {SOURCE_META[only].label}
      <button type="button" className="link-btn" onClick={() => onOnly(null)}>
        Show all
      </button>
    </span>
  );
}

/** The legend of a side's stack: each source's share of the supply, the demand, any shortfall. */
export function StackLegend({ rows, side, active, only, onOnly }: { rows: DayRow[]; side: Side; active: number[]; only?: string | null; onOnly?: (k: string | null) => void }) {
  const keys = SIDE_KEYS[side];
  const shares = sideShares(rows, keys.length);
  const short = shortRuns(rows).reduce((a, [s, e]) => a + e - s + 1, 0);
  return (
    <div className="ee-legend">
      {active.map((k) => (
        <Key key={keys[k]} color={SOURCE_META[keys[k]].color} attrs={seriesKey(SOURCE_META[keys[k]].label, keys[k], only, onOnly)}>
          {SOURCE_META[keys[k]].label} <span className="ee-fig">{shareText(shares.parts[k])}</span>
        </Key>
      ))}
      <OnlyNote only={active.some((k) => keys[k] === only) ? only : null} onOnly={onOnly} />
      <Key color={INK} line>
        Demand
      </Key>
      {short > 0 && (
        <Key hatch>
          <span className="ee-short">
            Not covered on {short} day{short === 1 ? "" : "s"}, {fmtNum(shares.unmet * 100)}% of the demand
          </span>
        </Key>
      )}
    </div>
  );
}

/** 0.85 → "85%", a sliver → "<1%". */
function shareText(f: number): string {
  return f > 0 && f < 0.005 ? "<1%" : `${fmtNum(f * 100, 0)}%`;
}

export function yearSummary(rows: DayRow[], side: Side, active: number[]): string {
  const keys = SIDE_KEYS[side];
  const p = peakIndex(rows);
  const runs = shortRuns(rows);
  return (
    `${SIDE_NAME[side]} supply against demand, day by day over the year, in MW: ${active.map((k) => SOURCE_META[keys[k]].label).join(", ")} stacked, the demand as a line. ` +
    (p >= 0 ? `The demand peaks on ${dayLabel(rows[p].day)} at ${fmtNum(rows[p].demand)} MW. ` : "") +
    (runs.length ? `The supply falls short on ${runs.reduce((a, [s, e]) => a + e - s + 1, 0)} days.` : "The supply meets the demand every day.")
  );
}

interface PanelProps {
  design: Design;
  side: Side;
  rows: DayRow[];
  prov: Provenance;
  /** The one series shown (a legend entry's menu, or another tab's "Show its year in Energy"). */
  only?: string | null;
  onOnly?: (key: string | null) => void;
}

/** A day's menu on the charts: jump the Design player to it, a failure from it, copy its values. */
const dayMenuOf =
  (design: Design) =>
  (row: DayRow, _i: number, values: string): MenuTarget => ({ kind: "day", design: { id: design.id, name: design.uid || design.code, sub: design.code }, day: row.day, label: dayLabel(row.day), values });

export function YearPanel({ design, side, rows, prov, only, onOnly }: PanelProps) {
  const [table, setTable] = useState(false);
  const keys = SIDE_KEYS[side];
  const all = useMemo(() => activeIndices(rows, keys.length), [rows, keys.length]);
  const active = shownSeries(all, keys, only);
  const question = yearQuestion(rows, keys, side);
  return (
    <Panel
      title={`${SIDE_NAME[side]}: supply against demand, day by day`}
      sub="Daily mean MW over the year, by source; hover or use the arrow keys to read a day."
      delay={0.06}
      aside={
        <>
          <ProvenanceChip source={prov} detail="The year's dispatch, day by day" />
          <TableToggle on={table} onChange={setTable} />
          <AskButton compact label="Ask about this chart" context={`${design.code}'s ${SIDE_NAME[side].toLowerCase()} supply over the year on the Energy tab`} question={question} />
        </>
      }
    >
      <StackLegend rows={rows} side={side} active={all} only={only} onOnly={onOnly} />
      {table ? (
        <DayTable rows={rows} side={side} active={active} />
      ) : (
        <StackChart rows={rows} keys={keys} active={active} height={side === "heat" ? 260 : 220} ticks={monthTicks} title={dateTitle} summary={yearSummary(rows, side, active)} markPeak dayMenu={dayMenuOf(design)} />
      )}
    </Panel>
  );
}

export function DurationPanel({ design, side, rows, prov, only, onOnly }: PanelProps) {
  const keys = SIDE_KEYS[side];
  const sorted = useMemo(() => durationRows(rows), [rows]);
  const all = useMemo(() => activeIndices(rows, keys.length), [rows, keys.length]);
  const active = shownSeries(all, keys, only);
  const base = active[0];
  const baseDays = base == null ? 0 : sorted.filter((r) => (r.parts[base] ?? 0) > 0).length;
  const summary =
    `Load-duration curve of the ${SIDE_NAME[side].toLowerCase()}: the days of the year sorted from the highest demand to the lowest, in MW, with what supplied each day stacked. ` +
    (sorted.length ? `The highest day needs ${fmtNum(sorted[0].demand)} MW, the lowest ${fmtNum(sorted[sorted.length - 1].demand)} MW.` : "");
  return (
    <Panel
      title="Load-duration curve"
      sub={
        base != null
          ? `The days sorted by demand, highest first. ${SOURCE_META[keys[base]].label} runs on ${baseDays} of ${sorted.length} days.`
          : "The days sorted by demand, highest first."
      }
      delay={0.1}
      aside={
        <>
          <ProvenanceChip source={prov} detail="The year's dispatch, day by day" />
          <AskButton compact label="Ask about this chart" context={`the ${SIDE_NAME[side].toLowerCase()} load-duration curve of ${design.code} on the Energy tab`} question="What does the load-duration curve say about how the plant is sized?" />
        </>
      }
    >
      <div className="ee-legend">
        {all.map((k) => (
          <Key key={keys[k]} color={SOURCE_META[keys[k]].color} attrs={seriesKey(SOURCE_META[keys[k]].label, keys[k], only, onOnly)}>
            {SOURCE_META[keys[k]].label}
          </Key>
        ))}
        <Key color={INK} line>
          Demand
        </Key>
        <OnlyNote only={all.some((k) => keys[k] === only) ? only : null} onOnly={onOnly} />
      </div>
      <StackChart
        dayMenu={dayMenuOf(design)}
        rows={sorted}
        keys={keys}
        active={active}
        height={220}
        ticks={rankTicks}
        title={dateTitle}
        sub={rankSub}
        summary={summary}
        xCaption="Days of the year, highest demand first"
      />
    </Panel>
  );
}

const EMPTY12 = new Array<number>(12).fill(0);

export function MonthPanel({ design, side, prov }: { design: Design; side: Side; prov: Provenance }) {
  const m = design.year.monthly_gwh;
  // MonthlyChart shows one side when the other has no demand; keyed by side, it opens on it.
  const monthly: MonthlyGwh =
    side === "heat"
      ? { heat: m.heat, cool: { demand: EMPTY12, abs: EMPTY12, chill: EMPTY12 } }
      : { heat: { demand: [], geo: [], hp: [], boiler: [] }, cool: m.cool };
  const peak = (() => {
    const d = side === "heat" ? m.heat.demand : m.cool.demand;
    return d.indexOf(Math.max(...d));
  })();
  return (
    <Panel
      title="Month by month"
      sub="GWh a month by source, the demand as a tick; months the supply falls short are hatched."
      delay={0.14}
      aside={
        <>
          <ProvenanceChip source={prov} detail="The year's dispatch, summed by month" />
          <AskButton
            compact
            label="Ask about this chart"
            context={`${design.code}'s ${SIDE_NAME[side].toLowerCase()} by month on the Energy tab`}
            question={peak >= 0 ? `What supplies the ${SIDE_NAME[side].toLowerCase()} in ${MONTH_NAMES[peak]}, the busiest month?` : undefined}
          />
        </>
      }
    >
      <MonthlyChart key={side} monthly={monthly} heat={SOURCE_META} cold={SOURCE_META} />
    </Panel>
  );
}

/** The year chart's table view: every day's sources, demand and shortfall. */
function DayTable({ rows, side, active }: { rows: DayRow[]; side: Side; active: number[] }) {
  const keys = SIDE_KEYS[side];
  const anyShort = rows.some((r) => r.unmet > 0);
  const cell = (v: number) => (v === 0 ? "0" : v < 0.005 ? "<0.01" : v.toFixed(2));
  return (
    <div className="ftable-wrap" role="region" aria-label={`${SIDE_NAME[side]} by day, MW`} tabIndex={0}>
      <table className="ftable">
        <thead>
          <tr>
            <th scope="col">Day</th>
            {active.map((k) => (
              <th key={k} scope="col" className="n">
                {SOURCE_META[keys[k]].label}
              </th>
            ))}
            <th scope="col" className="n">
              Demand
            </th>
            {anyShort && (
              <th scope="col" className="n">
                Not covered
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.day}>
              <td>{dayLabel(r.day)}</td>
              {active.map((k) => (
                <td key={k} className="n">
                  {cell(r.parts[k] ?? 0)}
                </td>
              ))}
              <td className="n">{cell(r.demand)}</td>
              {anyShort && <td className="n">{r.unmet > 0 ? cell(r.unmet) : "–"}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
