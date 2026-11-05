// The assumptions drawer's fields and the PUT /api/assumptions patch built from them. The server
// lists every price, unit cost and lifetime as an item (key, label, unit, group, value, default,
// source), so the fields follow that list: a key the server adds shows up without a change here.
// A rate the server keeps as a fraction (the discount rate, 0.052, no unit) is shown and typed in
// percent; lifetimes are whole years; numbers from 1,000 up carry thousands separators. A value
// back at its default is sent as null, so the server forgets it. Tested in assumptions.test.ts.

import type { AssumptionItem, Assumptions, AssumptionsPatch } from "../../workbench";

export interface FieldDef {
  /** The assumption's key (a field of dioscuri_plant's Prices). */
  id: string;
  label: string;
  /** As shown beside the input: "%" for a rate kept as a fraction. */
  unit: string;
  group: string;
  /** Where the default comes from. */
  source: string;
  /** Shown as percent, sent as a fraction. */
  percent?: boolean;
  integer?: boolean;
  /** In shown units (percent for a percent field). */
  min: number;
  max: number;
}

/** The server's groups in the order the drawer lists them; any other group follows, by its name. */
export const GROUPS: { id: string; label: string }[] = [
  { id: "prices", label: "Prices" },
  { id: "capital", label: "Capital costs" },
  { id: "o&m", label: "O&M" },
  { id: "lifetimes", label: "Lifetimes" },
];

/** A rate the server keeps as a fraction: no unit, "rate" in its key or label, at most 1. */
function isFractionRate(it: AssumptionItem): boolean {
  return !it.unit && /rate/i.test(`${it.key} ${it.label}`) && Math.abs(it.default) <= 1;
}

/** The drawer's field for one of the server's items. */
export function fieldOf(it: AssumptionItem): FieldDef {
  const percent = isFractionRate(it);
  const integer = /_years$/.test(it.key) || it.unit === "years";
  return {
    id: it.key,
    label: it.label || it.key,
    unit: percent ? "%" : it.unit,
    group: it.group,
    source: it.source ?? "",
    percent,
    integer,
    // A lifetime of 0 years has no annuity; a rate past 50% is a typo.
    min: integer ? 1 : 0,
    max: percent ? 50 : integer ? 100 : Number.POSITIVE_INFINITY,
  };
}

/** The fields for these assumptions, in the server's order. */
export function fieldsFor(a: Pick<Assumptions, "items">): FieldDef[] {
  return (a.items ?? []).map(fieldOf);
}

/** The fields by group: the known groups first, in their order, then any other by its name. */
export function groupsFor(fields: FieldDef[]): { id: string; label: string; fields: FieldDef[] }[] {
  const ids = [...GROUPS.map((g) => g.id), ...fields.map((f) => f.group).filter((g) => !GROUPS.some((k) => k.id === g))];
  return [...new Set(ids)]
    .map((id) => ({
      id,
      label: GROUPS.find((g) => g.id === id)?.label ?? id.charAt(0).toUpperCase() + id.slice(1),
      fields: fields.filter((f) => f.group === id),
    }))
    .filter((g) => g.fields.length > 0);
}

const finite = (v: unknown): number | undefined => (typeof v === "number" && Number.isFinite(v) ? v : undefined);

const itemOf = (a: Pick<Assumptions, "items">, f: FieldDef) => a.items?.find((it) => it.key === f.id);

/** A field's applied value in API units (a fraction for percent fields). */
export function valueOf(a: Assumptions, f: FieldDef): number | undefined {
  return finite(itemOf(a, f)?.value) ?? finite(a[f.id]);
}

/** A field's default in API units. */
export function defaultOf(a: Assumptions, f: FieldDef): number | undefined {
  return finite(itemOf(a, f)?.default) ?? finite(a.defaults?.[f.id]);
}

/** Equal within floating-point noise. */
export const same = (x: number, y: number) => Math.abs(x - y) <= 1e-9 * Math.max(1, Math.abs(x), Math.abs(y));

/** A value as the input shows it: percent for percent fields, no float noise (0.052 → "5.2"), 790000 → "790,000". */
export function toDisplay(v: number | undefined, f: FieldDef): string {
  if (v == null || !Number.isFinite(v)) return "";
  const shown = Number((f.percent ? v * 100 : v).toPrecision(10));
  return Math.abs(shown) >= 1000 ? shown.toLocaleString("en-US", { maximumFractionDigits: 10 }) : String(shown);
}

export type Parsed = { ok: true; value: number } | { ok: false; error: string };

/**
 * What was typed, back in API units, or why it can't be used. Commas that group thousands
 * ("790,000") are dropped; any other comma is a decimal comma ("3,5" is 3.5).
 */
export function parseField(text: string, f: FieldDef): Parsed {
  let t = text.trim().replace(/\s/g, "").replace(/[−–]/g, "-").replace(/%$/, "");
  t = /^[+-]?[1-9]\d{0,2}(,\d{3})+(\.\d+)?$/.test(t) ? t.replace(/,/g, "") : t.replace(",", ".");
  if (!t) return { ok: false, error: "Enter a number" };
  if (!/^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(t)) return { ok: false, error: "Not a number" };
  const shown = Number(t);
  if (!Number.isFinite(shown)) return { ok: false, error: "Not a number" };
  if (f.integer && !Number.isInteger(shown)) return { ok: false, error: "A whole number of years" };
  if (shown < f.min) return { ok: false, error: `At least ${f.min}${f.percent ? " %" : ""}` };
  if (shown > f.max) return { ok: false, error: `At most ${f.max}${f.percent ? " %" : ""}` };
  return { ok: true, value: f.percent ? Number((shown / 100).toPrecision(12)) : shown };
}

/** The applied value differs from the default. */
export function isChanged(a: Assumptions, f: FieldDef): boolean {
  const v = valueOf(a, f);
  const d = defaultOf(a, f);
  return v != null && d != null && !same(v, d);
}

export interface Draft {
  patch: AssumptionsPatch;
  /** Field id → why its text can't be used. */
  errors: Record<string, string>;
  /** Fields whose value would change. */
  changes: string[];
}

/**
 * The patch the edits make: each edited field whose value differs from the applied one, as the
 * new value, or null when it is back at the default.
 */
export function buildPatch(edits: Record<string, string>, a: Assumptions): Draft {
  const patch: AssumptionsPatch = {};
  const errors: Record<string, string> = {};
  const changes: string[] = [];
  for (const f of fieldsFor(a)) {
    const text = edits[f.id];
    if (text == null) continue;
    const p = parseField(text, f);
    if (!p.ok) {
      errors[f.id] = p.error;
      continue;
    }
    const current = valueOf(a, f);
    if (current != null && same(p.value, current)) continue;
    const def = defaultOf(a, f);
    changes.push(f.id);
    patch[f.id] = def != null && same(p.value, def) ? null : p.value;
  }
  return { patch, errors, changes };
}

/** "Reset all": null for every assumption that differs from its default ({} when none does). */
export function resetAllPatch(a: Assumptions): AssumptionsPatch {
  const patch: AssumptionsPatch = {};
  for (const f of fieldsFor(a)) if (isChanged(a, f)) patch[f.id] = null;
  return patch;
}

/** How many assumptions differ from their defaults. */
export function changedCount(a: Assumptions): number {
  return fieldsFor(a).filter((f) => isChanged(a, f)).length;
}

/** An assumption's applied value by key (the carbon price, say), when the server lists it. */
export function assumptionValue(a: Assumptions | null | undefined, key: string): number | null {
  if (!a) return null;
  return finite(a.items?.find((it) => it.key === key)?.value) ?? finite(a[key]) ?? null;
}
