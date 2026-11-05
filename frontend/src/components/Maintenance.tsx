// The inputs card's Maintenance section (2 Nov; one list of units, 4 Nov). Each unit that stops
// is a card: what it is in one line, when it stops (Dioscuri's quietest weeks, or the user's
// dates) and, for dates, a strip of the year. The doublets come first and always: the challenge
// runs each at most 330 days a year, so each is off 35 days, in its quietest weeks unless the
// user gives dates or another number of days. Every other unit has no stop until the user adds
// one from the tiles under the list (each says what the unit does); a unit added can be taken
// out again. A unit a design does not have is left out. Fewer days off than the cap leaves is
// allowed: the card says the cap is relaxed, and every design is still checked against it.

import type { ReactNode } from "react";

import type { InputToggle } from "../agent/types";
import { Ico } from "./InputsIcons";
import {
  DAYS,
  YEAR,
  dateOf,
  dayName,
  dayOf,
  daysOf,
  daysOffOf,
  daysOffProblem,
  rangesOf,
  relaxedNote,
  serviceProblem,
  stopsTogether,
  type MaintenanceState,
  type ServiceMode,
  type ServiceUnit,
  type StopRange,
  type StopsState,
} from "./inputsForm";

interface Props {
  toggle: InputToggle;
  stops: StopsState;
  maint: MaintenanceState;
  operatingDays: number;
  /** Each doublet's problem with its dates (null when fine). */
  problems: (string | null)[];
  serverError: string | null;
  onStops: (s: StopsState) => void;
  onMaint: (m: MaintenanceState) => void;
  id: string;
}

/** What each unit is, in one plain line, with its icon and tint (the server's unit ids). */
export const UNIT_INFO: Record<string, { icon: string; tint: string; what: string }> = {
  doublet: { icon: "well", tint: "earth", what: "A producer and an injector well: the geothermal source." },
  "heat exchanger": { icon: "exchange", tint: "heat", what: "Passes the brine's heat to the heating network." },
  "heat pump": { icon: "cycle", tint: "amber", what: "Lifts the brine's leftover heat to the network's temperature." },
  boiler: { icon: "flame", tint: "red", what: "Burns gas on the coldest days and while others are off." },
  "electric boiler": { icon: "bolt", tint: "violet", what: "Heats water with electricity; burns no gas." },
  chillers: { icon: "snow", tint: "cold", what: "Make the cooling network's cold water with electricity." },
  absorption: { icon: "snow", tint: "teal", what: "Makes cold water from the brine's heat." },
};
const infoOf = (unit: string) => UNIT_INFO[unit] ?? { icon: "wrench", tint: "ink", what: "" };

const MIN = dateOf(0);
const MAX = dateOf(DAYS - 1);
const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const MONTH_START = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

/** A segmented choice: the options as buttons in one rounded strip, one picked. */
function Segments<T extends string>({ value, options, onChange, label, name }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string; name: string }) {
  return (
    <span className="mt-seg" role="radiogroup" aria-label={label}>
      {options.map(([v, words]) => (
        <label key={v} className={value === v ? "on" : ""}>
          <input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange(v)} />
          {words}
        </label>
      ))}
    </span>
  );
}

/** The year as a strip of months with the unit's days off on it (the dates given, in order). */
export function YearStrip({ ranges, label }: { ranges: ([number, number] | null)[]; label: string }) {
  const shown = ranges.filter((r): r is [number, number] => !!r && r[1] >= r[0]).map(([a, b]) => [Math.max(0, a), Math.min(DAYS - 1, b)] as const);
  const words = shown.length ? shown.map(([a, b]) => (a === b ? dayName(a) : `${dayName(a)} to ${dayName(b)}`)).join(", ") : "no dates yet";
  return (
    <div className="mt-year" role="img" aria-label={`${label} off: ${words}`}>
      <div className="mt-year-track">
        {MONTH_START.slice(1).map((d) => (
          <i key={d} className="mt-year-tick" style={{ left: `${(d / DAYS) * 100}%` }} />
        ))}
        {shown.map(([a, b], i) => (
          <b key={i} className="mt-year-bar" style={{ left: `${(a / DAYS) * 100}%`, width: `${((b - a + 1) / DAYS) * 100}%` }} />
        ))}
      </div>
      <div className="mt-year-months" aria-hidden="true">
        {MONTHS.map((m, i) => (
          <span key={i} style={{ left: `${((MONTH_START[i] + (i < 11 ? MONTH_START[i + 1] : DAYS)) / 2 / DAYS) * 100}%` }}>
            {m}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Ranges of dates, each with its days, removable, and one more to add. */
function RangeList({ ranges, onChange, idPrefix, what, bad }: { ranges: StopRange[]; onChange: (r: StopRange[]) => void; idPrefix: string; what: string; bad: boolean }) {
  const add = () => {
    const last = Math.max(...ranges.map((r) => dayOf(r.to) ?? 0), 120);
    const a = Math.min(DAYS - 1, last + 8);
    onChange([...ranges, { from: dateOf(a), to: dateOf(Math.min(DAYS - 1, a + 6)) }]);
  };
  return (
    <>
      {ranges.map((r, j) => {
        const a = dayOf(r.from);
        const b = dayOf(r.to);
        const days = a != null && b != null && b >= a ? b - a + 1 : null;
        return (
          <div key={j} className="inputs-stop-range">
            <label htmlFor={`${idPrefix}-${j}-from`}>From</label>
            <input id={`${idPrefix}-${j}-from`} type="date" min={MIN} max={MAX} value={r.from} aria-invalid={bad} onChange={(e) => onChange(ranges.map((x, i) => (i === j ? { ...x, from: e.target.value } : x)))} />
            <label htmlFor={`${idPrefix}-${j}-to`}>to</label>
            <input id={`${idPrefix}-${j}-to`} type="date" min={MIN} max={MAX} value={r.to} aria-invalid={bad} onChange={(e) => onChange(ranges.map((x, i) => (i === j ? { ...x, to: e.target.value } : x)))} />
            <span className="inputs-stop-days">{days == null ? "" : days === 1 ? "1 day" : `${days} days`}</span>
            {ranges.length > 1 && (
              <button type="button" className="inputs-stop-remove" aria-label={`Remove range ${j + 1} of ${what}`} onClick={() => onChange(ranges.filter((_, i) => i !== j))}>
                ×
              </button>
            )}
          </div>
        );
      })}
      <button type="button" className="link-btn inputs-stop-add" onClick={add}>
        + Add a range
      </button>
    </>
  );
}

/** A unit's card head: its icon, its name, what it is, and what sits at the right. */
function UnitHead({ unit, name, each, aside, id }: { unit: string; name: string; each?: boolean; aside?: ReactNode; id: string }) {
  const info = infoOf(unit);
  return (
    <div className="mt-card-head">
      <Ico name={info.icon} tint={info.tint} size={15} />
      <span className="mt-card-titles">
        <b id={id}>
          {name}
          {each && <span className="mt-unit-each"> · each unit</span>}
        </b>
        {info.what && <span className="mt-what">{info.what}</span>}
      </span>
      {aside}
    </div>
  );
}

/** The units listed (doublets, then those with a stop) and those that could be added. */
export function splitUnits(m: MaintenanceState): { listed: number[]; free: number[] } {
  const listed: number[] = [];
  const free: number[] = [];
  m.units.forEach((u, k) => (u.mode === "off" ? free : listed).push(k));
  return { listed, free };
}

export function MaintenanceEditor({ toggle, stops, maint, operatingDays, problems, serverError, onStops, onMaint, id }: Props) {
  const def = Math.max(0, DAYS - operatingDays);
  const cap = toggle.cap_operating_days ?? 330;
  const offOf = (k: number) => daysOffOf(maint.daysOff[k] ?? "") ?? def;
  const together = stopsTogether(stops, operatingDays);
  const put = (k: number, next: Partial<StopsState["doublets"][number]>) => onStops({ ...stops, doublets: stops.doublets.map((d, i) => (i === k ? { ...d, ...next } : d)) });
  const putDays = (k: number, text: string) => onMaint({ ...maint, daysOff: maint.daysOff.map((d, i) => (i === k ? text : d)) });
  const putUnit = (k: number, next: Partial<ServiceUnit>) => onMaint({ ...maint, units: maint.units.map((u, i) => (i === k ? { ...u, ...next } : u)) });
  const { listed, free } = splitUnits(maint);
  const n = stops.doublets.length;

  return (
    <div className="mt" role="group" aria-labelledby={`${id}-maint`}>
      <span className="sr-only" id={`${id}-maint`}>
        Maintenance
      </span>
      <p className="mt-lead">
        Each unit listed here is off on its days; the other units cover them. The challenge runs each doublet at most <b>{cap} days a year</b>
        {def ? (
          <>
            , so each is off <b>{def} days</b>
          </>
        ) : null}
        . Other units have no stop unless you add one.
      </p>

      <ul className="mt-list">
        <li className={`mt-card doublets${problems.some(Boolean) ? " bad" : ""}`}>
          <UnitHead unit="doublet" name={n === 1 ? "Doublet" : `Doublets (${n})`} id={`${id}-mt-doublets`} aside={<span className="mt-req">Required</span>} />
          <Segments
            value={stops.mode}
            name={`${id}-stops-mode`}
            label="When the doublets stop"
            options={[
              ["quiet", "Quietest weeks (Dioscuri chooses)"],
              ["mine", "My dates"],
            ]}
            onChange={(mode) => onStops({ ...stops, mode })}
          />
          {stops.mode === "quiet" ? (
            <div className="mt-days">
              {maint.daysOff.map((text, k) => {
                const days = daysOffOf(text);
                const bad = daysOffProblem(text);
                const note = days != null ? relaxedNote(days, def, cap) : null;
                return (
                  <div key={k} className={`mt-day${bad ? " bad" : ""}`}>
                    <label htmlFor={`${id}-off-${k}`}>Doublet {k + 1}</label>
                    <input id={`${id}-off-${k}`} type="number" inputMode="numeric" min={1} max={DAYS - 100} step={1} value={text} aria-invalid={!!bad} aria-describedby={bad || note ? `${id}-off-${k}-note` : undefined} onChange={(e) => putDays(k, e.target.value)} />
                    <span className="mt-unit">days off a year</span>
                    {(bad || note) && (
                      <span id={`${id}-off-${k}-note`} className={bad ? "inputs-field-error" : "mt-relaxed"} role={bad ? "alert" : undefined}>
                        {bad ?? note}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="inputs-stops-list">
              {stops.doublets.map((d, k) => {
                const off = offOf(k);
                const ranges = rangesOf(d, off);
                const total = daysOf(ranges);
                const bad = problems[k];
                const note = !bad && total ? relaxedNote(total, def, cap) : null;
                const errId = `${id}-stop-${k}-err`;
                return (
                  <div key={k} className={`inputs-stop${bad ? " bad" : ""}`}>
                    <div className="inputs-stop-head">
                      <strong>Doublet {k + 1}</strong>
                      <Segments
                        value={d.kind}
                        name={`${id}-stop-${k}-kind`}
                        label={`Doublet ${k + 1}: one block or several ranges`}
                        options={[
                          ["block", "One block"],
                          ["ranges", "Several ranges"],
                        ]}
                        onChange={(kind) =>
                          put(k, kind === "ranges" && d.kind === "block" ? { kind, ranges: [{ from: d.start, to: dateOf(Math.min(DAYS - 1, (dayOf(d.start) ?? 180) + off - 1)) }] } : kind === "block" && d.ranges[0] ? { kind, start: d.ranges[0].from } : { kind })
                        }
                      />
                      <span className="inputs-stop-total">{total} days off</span>
                    </div>
                    {d.kind === "block" ? (
                      <div className="inputs-stop-range">
                        <input id={`${id}-stop-${k}-days`} className="mt-block-days" type="number" min={1} max={DAYS - 100} value={maint.daysOff[k] ?? String(def)} aria-label={`Doublet ${k + 1}: days in its block`} onChange={(e) => putDays(k, e.target.value)} />
                        <label htmlFor={`${id}-stop-${k}-start`}>days from</label>
                        <input id={`${id}-stop-${k}-start`} type="date" min={MIN} max={MAX} value={d.start} aria-invalid={!!bad} aria-describedby={bad ? errId : undefined} onChange={(e) => put(k, { start: e.target.value })} />
                        <span className="inputs-stop-to">{ranges[0] ? `to ${dayName(ranges[0][1])}${ranges[0][1] > DAYS - 1 ? ` ${YEAR + 1}` : ""}` : ""}</span>
                      </div>
                    ) : (
                      <RangeList ranges={d.ranges} onChange={(r) => put(k, { ranges: r })} idPrefix={`${id}-stop-${k}`} what={`doublet ${k + 1}`} bad={!!bad} />
                    )}
                    <YearStrip ranges={ranges} label={`Doublet ${k + 1}`} />
                    {bad && (
                      <span id={errId} className="inputs-field-error" role="alert">
                        {bad}
                      </span>
                    )}
                    {note && <span className="mt-relaxed">{note}</span>}
                  </div>
                );
              })}
              {together && <span className="inputs-opt-hint">{together[0].toUpperCase() + together.slice(1)}</span>}
              <span className="inputs-opt-hint">Doublets the design does not build are left out.</span>
            </div>
          )}
        </li>

        {listed.map((k) => {
          const u = maint.units[k];
          const bad = serviceProblem(u);
          const head = `${id}-svc-${k}-name`;
          return (
            <li key={u.unit} className={`mt-card${bad ? " bad" : ""}`} aria-labelledby={head}>
              <UnitHead
                unit={u.unit}
                name={u.label}
                each={u.bank}
                id={head}
                aside={
                  <button type="button" className="mt-remove" aria-label={`No stop for the ${u.label.toLowerCase()}`} title="No stop for this unit" onClick={() => putUnit(k, { mode: "off" })}>
                    <Ico name="close" size={13} boxed={false} />
                  </button>
                }
              />
              <Segments<ServiceMode>
                value={u.mode}
                name={`${id}-svc-${k}`}
                label={`When the ${u.label.toLowerCase()} stops`}
                options={[
                  ["auto", `Quietest weeks (${u.days} ${u.days === 1 ? "day" : "days"}, Dioscuri chooses)`],
                  ["dates", "My dates"],
                ]}
                onChange={(mode) => putUnit(k, mode === "dates" && !u.ranges.length ? { mode, ranges: [{ from: dateOf(120), to: dateOf(120 + u.days - 1) }] } : { mode })}
              />
              {u.mode === "dates" && (
                <div className="mt-unit-dates">
                  <RangeList ranges={u.ranges} onChange={(r) => putUnit(k, { ranges: r })} idPrefix={`${id}-svc-${k}`} what={u.label} bad={!!bad} />
                  <YearStrip ranges={u.ranges.map((r) => [dayOf(r.from) ?? -1, dayOf(r.to) ?? -2] as [number, number])} label={u.label} />
                  {u.bank && <span className="inputs-opt-hint">Each range takes one unit out, the units in turn; units without a range go in their quietest weeks.</span>}
                </div>
              )}
              {bad && (
                <span className="inputs-field-error" role="alert">
                  {bad}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {free.length > 0 && (
        <div className="mt-add" role="group" aria-labelledby={`${id}-mt-add`}>
          <span className="mt-add-head" id={`${id}-mt-add`}>
            Add a stop for
          </span>
          <div className="mt-add-tiles">
            {free.map((k) => {
              const u = maint.units[k];
              const info = infoOf(u.unit);
              return (
                <button key={u.unit} type="button" className="mt-add-tile" aria-label={`Add a stop for the ${u.label.toLowerCase()}: ${info.what}`} onClick={() => putUnit(k, { mode: "auto" })}>
                  <Ico name={info.icon} tint={info.tint} size={14} />
                  <span className="mt-add-text">
                    <b>{u.label}</b>
                    {info.what && <small>{info.what}</small>}
                  </span>
                  <span className="mt-add-plus" aria-hidden="true">
                    <Ico name="plus" size={13} boxed={false} />
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
      <span className="inputs-opt-hint">A unit the design does not have is left out. No heating unit is serviced while a doublet stands.</span>
      {serverError && (
        <span className="inputs-field-error" role="alert">
          {serverError}
        </span>
      )}
    </div>
  );
}
