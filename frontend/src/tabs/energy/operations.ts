// Operations: the design's year as an operator's plan, day by day: what each doublet pumps and at
// what temperatures, what each unit makes, what the plant buys, and how close each day comes to
// the caps. Nothing is recomputed: every figure is the design's own year (daily_mw, doublets), the
// same numbers the charts draw, set out as setpoints for a week, or the year as a CSV.

import type { Design } from "../../workbench";
import { MONTH_START, MONTHS } from "./model";

export const YEAR = 2027;

export interface PlanDoublet {
  flow: number;
  on: boolean;
  wellhead: number | null;
  reinjection: number | null;
  /** How far the brine is cooled, K (wellhead − reinjection). */
  cooled: number | null;
  /** Cooled to the cap (within 0.5 K): normal at full output, shown in its cell, not as a note. */
  atCap: boolean;
}

export interface PlanDay {
  day: number;
  label: string;
  heat: { demand: number; geo: number; hp: number; boiler: number; electric_boiler: number; short: number };
  cold: { demand: number; free: number; abs: number; chill: number; short: number };
  doublets: PlanDoublet[];
  electricity: number;
  /** What an operator should know that day: a stop, a shortfall, a cap within reach. */
  notes: string[];
}

const at = (xs: number[] | undefined, i: number) => {
  const v = xs?.[i];
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
};

/** "Mon 4 Jan": a day of the design's year (2027) with its weekday. */
export function dayName(day: number): string {
  const d = new Date(Date.UTC(YEAR, 0, 1 + day));
  let m = 11;
  while (m > 0 && MONTH_START[m] > day) m--;
  return `${d.toLocaleDateString("en-GB", { weekday: "short", timeZone: "UTC" })} ${day - MONTH_START[m] + 1} ${MONTHS[m]}`;
}

/** The plan for `days` days from `start` (0-based day of the year), every figure the year's own. */
export function operatingPlan(design: Design, start: number, days = 7): PlanDay[] {
  const y = design.year;
  const h = y.daily_mw?.heat as Record<string, number[]> | undefined;
  const c = y.daily_mw?.cool as Record<string, number[]> | undefined;
  const power = y.daily_mw?.power ?? {};
  const cap = design.plant.max_brine_cooling_k ?? 40;
  const stops = y.stop_ranges ?? (y.stop_days ?? []).map((r) => [r]);
  const out: PlanDay[] = [];
  for (let i = Math.max(0, start); i < Math.min(365, start + days); i++) {
    const doublets = (y.doublets ?? []).map((d) => {
      const flow = Math.max(0, at(d.flow_m3h, i));
      const on = (d.on?.[i] ?? flow > 0) && flow > 0.05;
      const wellhead = on && typeof d.wellhead_c?.[i] === "number" ? (d.wellhead_c[i] as number) : null;
      const reinjection = on && typeof d.reinjection_c?.[i] === "number" ? (d.reinjection_c[i] as number) : null;
      const cooled = wellhead != null && reinjection != null ? wellhead - reinjection : null;
      return { flow, on, wellhead, reinjection, cooled, atCap: cooled != null && cooled >= cap - 0.5 };
    });
    const notes: string[] = [];
    stops.forEach((rows, k) => {
      if ((rows ?? []).some(([a, b]) => i >= a && i <= b)) notes.push(`Doublet ${k + 1} stopped (maintenance)`);
    });
    doublets.forEach((d, k) => {
      if (d.cooled != null && d.cooled > cap + 0.05) notes.push(`Doublet ${k + 1}: brine cooled ${d.cooled.toFixed(1)} K, above the ${cap} K cap`);
    });
    const heatShort = at(h?.short, i);
    const coldShort = at(c?.short, i);
    if (heatShort > 1e-3) notes.push(`${heatShort.toFixed(1)} MW of heat short`);
    if (coldShort > 1e-3) notes.push(`${coldShort.toFixed(1)} MW of cold short`);
    const electricity = Object.values(power).reduce((s, xs) => s + at(xs as number[], i), 0);
    out.push({
      day: i,
      label: dayName(i),
      heat: { demand: at(h?.demand, i), geo: at(h?.geo, i), hp: at(h?.hp, i), boiler: at(h?.boiler, i), electric_boiler: at(h?.electric_boiler, i), short: heatShort },
      cold: { demand: at(c?.demand, i), free: at(c?.free, i), abs: at(c?.abs, i), chill: at(c?.chill, i), short: coldShort },
      doublets,
      electricity,
      notes,
    });
  }
  return out;
}

const n1 = (v: number | null) => (v == null ? "" : v.toFixed(1));

/** The plan as CSV: one row a day, MW and m³/h and °C, the notes last. */
export function planCsv(design: Design, plan: PlanDay[]): string {
  const k = design.year.doublets?.length ?? 0;
  const head = [
    "date",
    "heat_demand_mw",
    "geothermal_mw",
    "heat_pump_mw",
    "gas_boiler_mw",
    "electric_boiler_mw",
    "heat_short_mw",
    "cold_demand_mw",
    "free_cooling_mw",
    "absorption_mw",
    "chillers_mw",
    "cold_short_mw",
    ...Array.from({ length: k }, (_, j) => [`doublet_${j + 1}_flow_m3h`, `doublet_${j + 1}_wellhead_c`, `doublet_${j + 1}_reinjection_c`]).flat(),
    "electricity_mw",
    "notes",
  ];
  const iso = (day: number) => new Date(Date.UTC(YEAR, 0, 1 + day)).toISOString().slice(0, 10);
  const rows = plan.map((p) =>
    [
      iso(p.day),
      ...[p.heat.demand, p.heat.geo, p.heat.hp, p.heat.boiler, p.heat.electric_boiler, p.heat.short, p.cold.demand, p.cold.free, p.cold.abs, p.cold.chill, p.cold.short].map((v) => v.toFixed(2)),
      ...p.doublets.flatMap((d) => [d.flow.toFixed(1), n1(d.wellhead), n1(d.reinjection)]),
      p.electricity.toFixed(2),
      `"${p.notes.join("; ").replace(/"/g, "'")}"`,
    ].join(","),
  );
  return [head.join(","), ...rows].join("\n") + "\n";
}
