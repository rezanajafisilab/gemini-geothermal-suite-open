// Finds the numbers in an answer so the UI can draw them as chips that point at the step that
// produced them (the canvas's "number chips"). Every number in an answer comes from a tool or
// from the user (the reporter proves it), so the unit is enough to find the step.

import type { DoubletBuild } from "./types";

export type Segment = { text: string; num?: false } | { text: string; num: true; unit: string };

// A supply/return pair ("70/40 °C"), or a number with an optional unit. Not part of a word
// ("A1", "D1") and not a list of thousands without a unit ("2,500" stays whole).
// Model tags ("qwen3:1.7b", "qwen3.5:9b") are names, not numbers: nothing glued on with ":" or a letter.
const PATTERN =
  /(?<![\p{L}\p{N}_.,:])(?:-?\d+(?:[.,]\d+)?\/\d+(?:[.,]\d+)?\s?°C|[-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-−]?\d+(?:\.\d+)?)(?:\s?(%|°C|€\/MWh|GWh|MWh|MW|km|bar|K|m)(?![\p{L}]))?(?![\p{L}\p{N}:])/gu;

export function segments(text: string): Segment[] {
  const out: Segment[] = [];
  let at = 0;
  for (const m of text.matchAll(PATTERN)) {
    const start = m.index ?? 0;
    const whole = m[0];
    const pair = whole.includes("/");
    const unit = pair ? "°C" : (m[1] ?? "");
    // A bare integer without a unit is usually a count or a code, and a distance names a well
    // ("the 1 km doublet"); keep those as text.
    if ((!unit && !/[.,]/.test(whole)) || unit === "km" || unit === "m") continue;
    if (start > at) out.push({ text: text.slice(at, start) });
    out.push({ text: whole, num: true, unit });
    at = start + whole.length;
  }
  if (at < text.length) out.push({ text: text.slice(at) });
  return out;
}

/** Step names that can have produced a number with this unit, best first. */
export function sourcesFor(unit: string, after: string): string[] {
  if (unit === "€/MWh") return ["economics", "options"];
  if (unit === "%") return /^\s*(less|more)\s+CO/.test(after) ? ["economics", "options"] : ["simulate", "options"];
  if (unit === "GWh" || unit === "MWh" || unit === "MW") return ["simulate", "options"];
  if (unit === "°C") return ["doublet", "simulate", "verify"];
  if (unit === "km" || unit === "m") return ["plan", "doublet"];
  return ["verify", "report"];
}

export interface OptionLine {
  label: string;
  /** The option's text after the label, e.g. "100% of the heat at 70.8 €/MWh." */
  detail: string;
  coverage?: number;
  cost?: number;
}

/**
 * The reporter ends an infeasible answer with "Options: <label>: <x>% of the heat at <y> €/MWh."
 * per relaxed design. Split them out so the UI can draw them as rows; any other text comes back
 * whole, with no options.
 */
export function splitOptions(text: string): { lead: string; options: OptionLine[] } {
  const at = text.search(/\sOptions:\s/);
  if (at < 0) return { lead: text, options: [] };
  const lead = text.slice(0, at).trim();
  const rest = text.slice(at).replace(/^\s*Options:\s*/, "");
  const parts = rest.split(/(?<=€\/MWh\.)\s+/).map((p) => p.trim()).filter(Boolean);
  const options: OptionLine[] = [];
  for (const part of parts) {
    const m = part.match(/^([^:]+):\s*(.+)$/s);
    if (!m) return { lead: text, options: [] };
    const pct = m[2].match(/(\d+(?:\.\d+)?)%/);
    const eur = m[2].match(/(\d+(?:\.\d+)?)\s?€\/MWh/);
    options.push({
      label: m[1].trim(),
      detail: m[2].trim(),
      coverage: pct ? Number(pct[1]) : undefined,
      cost: eur ? Number(eur[1]) : undefined,
    });
  }
  return { lead, options };
}

/** Split "… Source: the project's subsurface data (subsurface.json)." sentences out of an answer. */
export function splitSources(text: string): { text: string; sources: string[] } {
  const sources: string[] = [];
  const rest = text.replace(/\s*Source: (.+?)\.(?=\s|$)/g, (_, src: string) => {
    if (!sources.includes(src)) sources.push(src);
    return "";
  });
  return { text: rest.trim(), sources };
}

export interface DecisionOption {
  text: string;
  label: string;
  summary: string;
  coverage?: number;
  cost?: number;
}

/** Read a decision option, "<label> (<x>% of the heat at <y> €/MWh)", into its parts. */
export function parseOption(text: string): DecisionOption {
  const m = text.match(/^(.*\S)\s+\(([^()]*)\)$/);
  if (!m) return { text, label: text, summary: "" };
  const pct = m[2].match(/(\d+(?:\.\d+)?)%/);
  const eur = m[2].match(/(\d+(?:\.\d+)?)\s?€\/MWh/);
  return {
    text,
    label: m[1],
    summary: m[2],
    coverage: pct ? Number(pct[1]) : /no heat/.test(m[2]) ? 0 : undefined,
    cost: eur ? Number(eur[1]) : undefined,
  };
}

/** Split the agent's closing "Note: <file> contains text that reads like instructions …" off an answer. */
export function splitInjectionNote(text: string): { text: string; note: string } {
  const m = text.match(/\s*Note: ([^]*?contains text that reads like instructions[^]*)$/);
  return m ? { text: text.slice(0, m.index).trim(), note: m[1].trim() } : { text, note: "" };
}

// A challenge design code or a user design ("U1"); not the older A1-style codes of the toy model.
// A code is the doublets, top-up and cooling ("2D-HP-AB"), the aquifer when it is not the known
// one ("@3000", "@2500+3000": one per doublet) and the variant flags ("-2I1-ST", see flagMeaning).
// The flags repeat greedily and the code must end at a word boundary, so the whole code is
// matched: "2D-HP-AB-2I1-ST" is never cut to "2D-HP-AB". A what-if's design id in the tabs is
// "<code> · <change label>" (the card's design_id); text only ever links the code.
export const DESIGN_CODE = /\b[123]D-(?:HP|BO|DH)-(?:AB|EC|NC)(?:@\d{3,5}(?:\+\d{3,5})*)?(?:-(?:2I\d*|ST\d*|BL|PL\d*|PU\d*|IL\d*|IU\d*|N1|EB|GS|FC|PV\d+(?:\.\d+)?|TS\d+|ATES))*\b|\bU\d+\b/;

/** The first design code an answer names, so a reply with no card can still link to the tabs. */
export function designCodeIn(text: string): string | undefined {
  return text.match(DESIGN_CODE)?.[0];
}

const CODE_PARTS = /^([123]D-(?:HP|BO|DH)-(?:AB|EC|NC)(?:@\d{3,5}(?:\+\d{3,5})*)?)((?:-(?:2I\d*|ST\d*|BL|PL\d*|PU\d*|IL\d*|IU\d*|N1|EB|GS|FC|PV[\d.]+|TS[\d.]+|ATES))*)$/;

/** A code's layout and its variant flags: "2D-HP-AB-2I1-ST" → {base: "2D-HP-AB", flags: ["2I1", "ST"]}. */
export function splitCode(code: string): { base: string; flags: string[] } {
  const m = CODE_PARTS.exec(code);
  if (!m) return { base: code, flags: [] };
  return { base: m[1], flags: m[2] ? m[2].slice(1).split("-") : [] };
}

const andList = (items: string[]) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`);

/**
 * What a variant flag means, as the engine names it (dioscuri_plant.search.flag_words):
 * 2I two injectors per doublet (2I1: on doublet 1 only), ST a treatment train per doublet (ST2:
 * two trains), BL the hottest doublet first, PL/PU producers and IL/IU injectors open over the
 * lower/upper half of the aquifer. An unknown flag comes back as it is.
 */
export function flagMeaning(flag: string, doublets?: number): string {
  const one = /^2I(\d+)$/.exec(flag);
  if (one) {
    const which = one[1].split("");
    return which.length === 1 ? `Two injectors on doublet ${which[0]} only` : `Two injectors on doublets ${andList(which)}`;
  }
  const trains = /^ST(\d+)$/.exec(flag);
  if (trains) return `${trains[1]} treatment trains (separator, filters)${doublets ? ` for the ${doublets} doublets` : ""}`;
  const pv = /^PV([\d.]+)$/.exec(flag);
  if (pv) return `Own solar panels, ${pv[1]} MWp: their power runs the plant first, the rest is sold`;
  const ts = /^TS([\d.]+)$/.exec(flag);
  if (ts) return `A ${Number(ts[1]).toLocaleString("en-US")} MWh hot-water store: quiet days' geothermal heat for the boiler's days`;
  const half = /^([PI])([LU])(\d+)$/.exec(flag);
  if (half) {
    const which = half[3].split("");
    const well = half[1] === "P" ? "producer" : "injector";
    return `The ${well} of doublet${which.length > 1 ? "s" : ""} ${andList(which)} open over the ${half[2] === "L" ? "lower" : "upper"} half`;
  }
  const named: Record<string, string> = {
    "2I": "Two injectors per doublet",
    ST: "A treatment train (separator, filters) per doublet",
    BL: "The hottest doublet first (base load)",
    PL: "Producers open over the lower half of the aquifer",
    PU: "Producers open over the upper half of the aquifer",
    IL: "Injectors open over the lower half of the aquifer",
    IU: "Injectors open over the upper half of the aquifer",
    N1: "Reliable plan: boiler and chillers in equal units, sized so that any one unit can be out (N-1)",
    EB: "Gas-free: no gas bought; an electric boiler for the peaks (the brine's own gas burnt in a small boiler, unless it is sold)",
    GS: "The brine's gas cleaned and sold to the gas grid (nothing burnt on site; the buyer's CO₂ is not counted here)",
    FC: "Free cooling: the towers cool the network directly on cool days, before the chillers",
    ATES: "A seasonal aquifer store (HT-ATES): summer's geothermal heat kept for winter",
  };
  return named[flag] ?? flag;
}

const OPENED: Record<string, string> = { full: "full height", upper: "upper half", lower: "lower half" };
const whole = (v: number) => Math.round(v).toLocaleString("en-US");

/**
 * Each doublet in a few words, "D1: 2 injectors". "differences" (a design card) names only what
 * differs between the doublets, and nothing when they are all built alike, since the flags say
 * what they share; "described" (what a message asked for) names what is not standard on each.
 * Doublets on the same treatment train share it; one alone on its train has its own.
 */
export function doubletLines(doublets: DoubletBuild[] | null | undefined, mode: "differences" | "described" = "differences"): string[] {
  const ds = (Array.isArray(doublets) ? doublets : []).filter((d): d is DoubletBuild => !!d && typeof d === "object");
  if (!ds.length || (mode === "differences" && ds.length < 2)) return [];
  const trains = ds.map((d) => (typeof d.train === "number" ? d.train : 0));
  const oneTrain = new Set(trains).size === 1;
  const pairs = (d: DoubletBuild) => (Number(d.injectors) >= 2 ? 2 : 1);
  const shared = (i: number) => trains.filter((t) => t === trains[i]).length > 1;
  // Each attribute: the value compared between doublets, how it reads, and whether it is standard.
  const attrs: { key: (d: DoubletBuild, i: number) => unknown; show: (d: DoubletBuild, i: number) => string; plain: (d: DoubletBuild, i: number) => boolean }[] = [
    { key: pairs, show: (d) => (pairs(d) === 2 ? "2 injectors" : "1 injector"), plain: (d) => pairs(d) === 1 },
    {
      key: (d) => d.producer_open ?? "full",
      show: (d) => `producer open over the ${OPENED[d.producer_open ?? "full"] ?? d.producer_open}`,
      plain: (d) => (d.producer_open ?? "full") === "full",
    },
    {
      key: (d) => d.injector_open ?? "full",
      show: (d) => `${pairs(d) === 2 ? "injectors" : "injector"} open over the ${OPENED[d.injector_open ?? "full"] ?? d.injector_open}`,
      plain: (d) => (d.injector_open ?? "full") === "full",
    },
    { key: (d) => d.depth_m ?? null, show: (d) => (typeof d.depth_m === "number" ? `${whole(d.depth_m)} m` : "the known aquifer"), plain: (d) => typeof d.depth_m !== "number" },
    {
      key: (d) => d.max_flow_m3h ?? null,
      show: (d) => (typeof d.max_flow_m3h === "number" ? `at most ${whole(d.max_flow_m3h)} m³/h` : "the flow cap"),
      plain: (d) => typeof d.max_flow_m3h !== "number",
    },
    { key: (_, i) => shared(i), show: (_, i) => (shared(i) ? "shared treatment train" : "own treatment train"), plain: () => oneTrain },
  ];
  if (mode === "differences") {
    const differ = attrs.filter((a) => new Set(ds.map((d, i) => a.key(d, i))).size > 1);
    if (!differ.length) return [];
    return ds.map((d, i) => `D${i + 1}: ${differ.map((a) => a.show(d, i)).join(", ")}`);
  }
  return ds.map((d, i) => {
    const parts = attrs.filter((a) => !a.plain(d, i)).map((a) => a.show(d, i));
    return `D${i + 1}: ${parts.length ? parts.join(", ") : "standard"}`;
  });
}

/** A parameter's value as written in a change: 50 → "50", ["boiler"] → "boiler", true → "yes". */
export function shownValue(v: unknown): string {
  if (typeof v === "number") return Number.isFinite(v) ? String(Math.round(v * 1e6) / 1e6) : "–";
  if (typeof v === "string") return v || "–";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (v == null) return "none";
  if (Array.isArray(v)) return v.length ? v.map(shownValue).join(", ") : "none";
  try {
    return JSON.stringify(v);
  } catch {
    return "–";
  }
}

/** Changes as the parameters they set: {heat_return_c: 50} → ["heat_return_c → 50"]. */
export function changeList(changes: Record<string, unknown> | null | undefined): string[] {
  if (!changes || typeof changes !== "object" || Array.isArray(changes)) return [];
  return Object.entries(changes).map(([k, v]) => `${k} → ${shownValue(v)}`);
}
