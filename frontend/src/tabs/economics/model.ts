// The Economics tab's data: a design's Economics (workbench API) turned into what the charts
// draw. Pure functions, tested in model.test.ts.
//
//   costSteps      the cost lines as a waterfall whose rounded labels add up to the LCOH/LCOC
//   kindTotals     the same lines summed by kind (capital, fixed O&M, electricity …)
//   lcoeOf         the cost of heat and cold together: the server's, else worked out
//   capexRows      the capital items, largest first, with "size × unit cost" text and their life
//   cashFlow       the discounted cumulative cash flow against gas, its payback and its range
//   co2Split       the CO₂ a year by source: gas bought, gas from the brine, each use of grid power

import type { CapexItem, CostLine, Design, VersusReference } from "../../workbench";

/** The gas plant every saving is measured against (the search's baseline), as the tabs name it. */
export const GAS_PLANT = "gas boilers and electric chillers";

/**
 * Colours and names of the cost kinds, in the order the waterfalls stack them. Capital and fixed
 * O&M are two steps of teal and variable O&M a brown; electricity takes the heat pump's amber and
 * gas the boiler's violet, so the Energy and Economics tabs read as one; the CO₂ price is red.
 * Validated in this order with the dataviz palette script (adjacent pairs, also with a kind
 * missing; all pass on white; amber and the light teal are under 3:1, so every value is also a
 * visible label). Network costs are a neutral grey.
 */
export const KIND_META: Record<string, { label: string; color: string }> = {
  capital: { label: "Capital", color: "#00879C" },
  fixed: { label: "Fixed O&M", color: "#4DBDCF" },
  variable: { label: "Variable O&M", color: "#B5651D" },
  electricity: { label: "Electricity", color: "#E3A33B" },
  gas: { label: "Gas", color: "#7856C4" },
  carbon: { label: "CO₂ price", color: "#D94A5A" },
  network: { label: "Network", color: "#9AA5AB" },
};
const KIND_ORDER = Object.keys(KIND_META);
const OTHER = { label: "Other", color: "#B3BAB2" };

export const kindMeta = (kind: string) => KIND_META[kind] ?? OTHER;

/** The server writes CO2 and arrows in plain ASCII: "CO2: gas" → "CO₂: gas", "4 -> 6.9 MW" → "4 → 6.9 MW". */
export const prettyText = (s: string) => s.replace(/\bCO2\b/g, "CO₂").replace(/\s*->\s*/g, " → ");

export interface CostStep {
  /** As shown: "Wells", "Geothermal O&M, fixed", "CO₂: gas" … */
  item: string;
  kind: string;
  /** €/MWh as sent. */
  raw: number;
  /** €/MWh rounded so the labels add up to the total's label. */
  label: number;
  /** The waterfall: where the bar starts and ends (€/MWh, raw values). */
  start: number;
  end: number;
  meurPerYear: number;
}

export interface CostWaterfall {
  steps: CostStep[];
  /** The cost the steps add up to (the LCOH or LCOC, or the lines' sum without one). */
  total: number;
  /** The lines' own sum. */
  sum: number;
  /** The x range to draw, always including 0 and the total. */
  domain: [number, number];
}

/**
 * Round `values` to `digits` decimals so they add up to `total` rounded the same way (the largest
 * remainder method), when they nearly do; otherwise round each on its own.
 */
export function roundToTotal(values: number[], total: number, digits = 1): number[] {
  const f = 10 ** digits;
  const target = Math.round(total * f);
  const scaled = values.map((v) => v * f);
  const floors = scaled.map((v) => Math.floor(v + 1e-9));
  let diff = target - floors.reduce((a, b) => a + b, 0);
  if (Math.abs(diff) > values.length) return values.map((v) => Math.round(v * f) / f);
  const order = scaled.map((v, i) => ({ i, rem: v - floors[i] }));
  const out = floors.slice();
  if (diff > 0) {
    order.sort((a, b) => b.rem - a.rem || a.i - b.i);
    for (let j = 0; diff > 0; j = (j + 1) % order.length, diff--) out[order[j].i] += 1;
  } else if (diff < 0) {
    order.sort((a, b) => a.rem - b.rem || a.i - b.i);
    for (let j = 0; diff < 0; j = (j + 1) % order.length, diff++) out[order[j].i] -= 1;
  }
  return out.map((v) => v / f);
}

/** "fixed", "variable": how an item with lines of two kinds tells them apart. */
const kindWord = (kind: string) => (kind === "carbon" ? "CO₂" : (KIND_META[kind]?.label.replace(/ O&M$/, "") ?? kind).toLowerCase());

/**
 * The cost lines as a waterfall, grouped by kind (capital first; the server's order within a
 * kind). Lines of the same item and kind are one row (the server sends the surface plant per
 * doublet and per MW); an item with rows of two kinds says which is which ("Geothermal O&M,
 * fixed"). Rows under half a cent are left out. When the lines don't add up to `total` within
 * 0.1 €/MWh, a "Not itemised" step makes up the difference.
 */
export function costSteps(lines: CostLine[], total: number | null | undefined, digits = 1): CostWaterfall {
  const merged: { item: string; kind: string; raw: number; meur: number; i: number }[] = [];
  lines.forEach((l, i) => {
    if (!Number.isFinite(l.eur_per_mwh)) return;
    const m = merged.find((x) => x.item === l.item && x.kind === l.kind);
    if (m) {
      m.raw += l.eur_per_mwh;
      m.meur += l.meur_per_year;
    } else merged.push({ item: l.item, kind: l.kind, raw: l.eur_per_mwh, meur: l.meur_per_year, i });
  });
  const kept = merged.filter((m) => Math.abs(m.raw) >= 0.005).sort((a, b) => rank(a.kind) - rank(b.kind) || a.i - b.i);
  const kinds = new Map<string, Set<string>>();
  for (const m of kept) kinds.set(m.item, (kinds.get(m.item) ?? new Set<string>()).add(m.kind));
  const sum = kept.reduce((a, m) => a + m.raw, 0);
  const goal = total != null && Number.isFinite(total) ? total : sum;
  const tol = 0.1 + 1e-9;
  const rows = kept.map((m) => ({
    item: prettyText((kinds.get(m.item)?.size ?? 0) > 1 ? `${m.item}, ${kindWord(m.kind)}` : m.item),
    kind: m.kind,
    raw: m.raw,
    meur: m.meur,
  }));
  if (Math.abs(goal - sum) > tol) rows.push({ item: "Not itemised", kind: "other", raw: goal - sum, meur: Number.NaN });
  const labels = roundToTotal(
    rows.map((r) => r.raw),
    goal,
    digits,
  );
  let cum = 0;
  let lo = 0;
  let hi = Math.max(0, goal);
  const steps = rows.map((r, i) => {
    const start = cum;
    cum += r.raw;
    lo = Math.min(lo, cum);
    hi = Math.max(hi, cum);
    return { item: r.item, kind: r.kind, raw: r.raw, label: labels[i], start, end: cum, meurPerYear: r.meur };
  });
  return { steps, total: goal, sum, domain: [lo, hi] };
}

function rank(kind: string): number {
  const i = KIND_ORDER.indexOf(kind);
  return i < 0 ? KIND_ORDER.length : i;
}

/** The steps summed by kind, in kind order, using the rounded labels (so they add up too). */
export function kindTotals(steps: CostStep[]): { kind: string; value: number }[] {
  const out: { kind: string; value: number }[] = [];
  for (const s of steps) {
    const last = out.find((o) => o.kind === s.kind);
    if (last) last.value = Math.round((last.value + s.label) * 1000) / 1000;
    else out.push({ kind: s.kind, value: s.label });
  }
  return out;
}

/** The kind of the largest cost line, its item and €/MWh, for a question worth asking. */
export function largestLine(steps: CostStep[]): CostStep | null {
  return steps.reduce<CostStep | null>((b, s) => (!b || s.raw > b.raw ? s : b), null);
}

/**
 * The cost of heat and cold together, €/MWh: the server's, else the costs of heat and of cold
 * weighted by what each delivers. null when neither can be had.
 */
export function lcoeOf(d: Pick<Design, "economics" | "year">): number | null {
  const e = d.economics;
  if (typeof e?.lcoe === "number" && Number.isFinite(e.lcoe)) return e.lcoe;
  const heat = Math.max(0, d.year?.heat_delivered_gwh ?? 0);
  const cold = Math.max(0, d.year?.cool_delivered_gwh ?? 0);
  const parts: [number | null | undefined, number][] = [
    [e?.lcoh, heat],
    [e?.lcoc, cold],
  ];
  if (parts.some(([cost, gwh]) => gwh > 0 && !(typeof cost === "number" && Number.isFinite(cost)))) return null;
  const total = heat + cold;
  return total > 0 ? parts.reduce((s, [cost, gwh]) => s + (gwh > 0 ? (cost as number) * gwh : 0), 0) / total : null;
}

export interface CapexRow {
  /** Unique among the rows (an item can come several times: wells at two depths, one row per train). */
  key: string;
  item: string;
  /** The server's note on the row ("1 producer(s), 2 injector(s), priced at 2,500 m TVD"), else "1 of 2" when the item repeats. */
  note: string | null;
  meur: number;
  /** "4 wells × 6.383 M€ per well", "24.66 MW × 0.345 M€/MW". */
  detail: string;
  /** Its life, years (the annuity's): null when the server doesn't say. */
  life: number | null;
  share: number;
}

const trim = (v: number, digits: number) => String(Number(v.toFixed(digits)));

/** The server's units are plural ("wells", "doublets"): one of them, for "per well" and "1 doublet". */
const SINGULAR: Record<string, string> = { wells: "well", doublets: "doublet", units: "unit", trains: "train" };

/** The capital items, largest first, with their size × unit cost, life and share of the total. */
export function capexRows(items: CapexItem[]): CapexRow[] {
  const total = items.reduce((a, it) => a + Math.max(0, it.meur), 0);
  const kept = items.filter((it) => Number.isFinite(it.meur));
  const count = new Map<string, number>();
  for (const it of kept) count.set(it.item, (count.get(it.item) ?? 0) + 1);
  const seen = new Map<string, number>();
  return kept
    .map((it, i) => {
      const one = SINGULAR[it.unit] ?? it.unit;
      const per = it.unit === "MW" ? " M€/MW" : ` M€ per ${one}`;
      const k = (seen.get(it.item) ?? 0) + 1;
      seen.set(it.item, k);
      const many = (count.get(it.item) ?? 1) > 1;
      const note = it.note?.trim() ? prettyText(it.note.trim()) : many ? `${k} of ${count.get(it.item)}` : null;
      return {
        key: `${i}:${it.item}`,
        item: it.item,
        note,
        meur: it.meur,
        detail: `${trim(it.size, 2)} ${it.size === 1 ? one : it.unit} × ${trim(it.meur_per_unit, 3)}${per}`,
        life: typeof it.life_years === "number" && it.life_years > 0 ? it.life_years : null,
        share: total > 0 ? Math.max(0, it.meur) / total : 0,
      };
    })
    .sort((a, b) => b.meur - a.meur);
}

export interface CashFlow {
  /** Cumulative discounted M€ against gas, year 0 .. lifetime. */
  points: { year: number; value: number; delta: number }[];
  /** The first year the cumulative is at or above 0 (the server's when it sends one); null: never. */
  payback: number | null;
  /** The year the line crosses 0, interpolated; null: it never does. */
  crossing: number | null;
  npv: number;
  min: number;
  max: number;
}

/** The first index at or above zero, after a start below it; 0 when it starts at or above. */
export function firstNonNegative(flow: number[]): number | null {
  const i = flow.findIndex((v) => v >= 0);
  return i < 0 ? null : i;
}

/** The cumulative value at year `t` (fractional years interpolate); null outside the years. */
export function valueAt(points: { year: number; value: number }[], t: number): number | null {
  if (!points.length || !Number.isFinite(t) || t < 0 || t > points.length - 1) return null;
  const i = Math.floor(t);
  if (i === t || i + 1 >= points.length) return points[i].value;
  return points[i].value + (points[i + 1].value - points[i].value) * (t - i);
}

/** "in year 10", "after 7.7 years": how the payback reads (the server may send a fraction). */
export function paybackText(years: number): string {
  if (Number.isInteger(years)) return `in year ${years}`;
  const r = Math.round(years * 10) / 10;
  return `after ${r} year${r === 1 ? "" : "s"}`;
}

/** The cash flow against the gas reference, ready to draw. */
export function cashFlow(v: VersusReference): CashFlow {
  const flow = (v.cash_flow_meur ?? []).filter((x) => Number.isFinite(x));
  const points = flow.map((value, year) => ({ year, value, delta: year === 0 ? value : value - flow[year - 1] }));
  let crossing: number | null = null;
  for (let t = 1; t < flow.length; t++) {
    const a = flow[t - 1];
    const b = flow[t];
    if (a < 0 && b >= 0) {
      crossing = t - 1 + -a / (b - a);
      break;
    }
  }
  if (crossing == null && flow.length && flow[0] >= 0) crossing = 0;
  const payback = v.payback_years ?? (crossing == null ? null : firstNonNegative(flow));
  return {
    points,
    payback,
    crossing,
    npv: flow.length ? flow[flow.length - 1] : v.npv_meur,
    min: Math.min(0, ...flow),
    max: Math.max(0, ...flow),
  };
}

/** The years the cash flow runs over (the server's horizon), or null without one. */
export function horizonOf(v: VersusReference | null | undefined): number | null {
  const n = v?.cash_flow_meur?.length ?? 0;
  return n > 1 ? n - 1 : null;
}

/** Where a design's CO₂ comes from. */
export interface Co2Source {
  key: string;
  /** "Gas bought for the boiler", "Gas from the brine", "Well pumps" … */
  item: string;
  /** Gas bought, the gas that comes up with the brine (burnt or flared), or grid electricity. */
  fuel: "gas" | "brine" | "grid";
  t: number;
  color: string;
}

export interface Co2Split {
  /** In a fixed order (gas first, then each use of grid power), so neighbours keep their colours. */
  sources: Co2Source[];
  /** From gas, bought and from the brine. */
  gas: number;
  grid: number;
  total: number;
}

/**
 * The sources' colours: gas the boiler's violet (the brine's own gas a lighter violet), each use of
 * grid power its part's colour on the Energy tab. Validated in this order with the dataviz palette
 * script (adjacent pairs, also with sources missing; the light violet and the amber are under 3:1,
 * so each source is also a labelled row).
 */
const GAS_SOURCES: { key: string; item: string; fuel: "gas" | "brine"; color: string }[] = [
  { key: "purchased_gas", item: "Gas bought for the boiler", fuel: "gas", color: "#7856C4" },
  { key: "produced_gas", item: "Gas from the brine", fuel: "brine", color: "#A58BE0" },
];
const POWER_USES: { keys: string[]; item: string; color: string }[] = [
  { keys: ["pumps"], item: "Well pumps", color: "#C24E1C" },
  { keys: ["hp", "recovery_hp"], item: "Heat pump", color: "#E3A33B" },
  { keys: ["chillers"], item: "Electric chillers", color: "#139FBF" },
  { keys: ["towers"], item: "Cooling towers", color: "#2363A6" },
];

const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);

/**
 * The CO₂ a year by source, from the year's own breakdown (co2_t: purchased_gas, produced_gas,
 * electricity). The grid's share is split by each use's electricity, which is exact: every MWh
 * from the grid carries the same factor. null when the server sends no breakdown.
 */
export function co2Split(d: Pick<Design, "year" | "economics">): Co2Split | null {
  const co2 = d.year?.co2_t ?? (d.economics as { co2_t?: Record<string, number> } | undefined)?.co2_t;
  if (!co2) return null;
  const sources: Co2Source[] = [];
  for (const g of GAS_SOURCES) {
    const t = num(co2[g.key]);
    if (t > 0) sources.push({ ...g, t });
  }
  const grid = num(co2.electricity);
  if (grid > 0) {
    const el = d.year?.electricity_gwh ?? {};
    const all = Object.values(el).reduce((s, v) => s + num(v), 0);
    if (all > 0) {
      let named = 0;
      for (const u of POWER_USES) {
        const gwh = u.keys.reduce((s, k) => s + num(el[k]), 0);
        named += gwh;
        if (gwh > 0) sources.push({ key: u.keys[0], item: u.item, fuel: "grid", t: (grid * gwh) / all, color: u.color });
      }
      if (all - named > 1e-9) sources.push({ key: "other", item: "Other electricity", fuel: "grid", t: (grid * (all - named)) / all, color: "#9AA5AB" });
    } else {
      sources.push({ key: "electricity", item: "Grid electricity", fuel: "grid", t: grid, color: "#C24E1C" });
    }
  }
  const total = sources.reduce((s, x) => s + x.t, 0);
  if (!(total > 0)) return null;
  return { sources, gas: total - grid, grid, total };
}
