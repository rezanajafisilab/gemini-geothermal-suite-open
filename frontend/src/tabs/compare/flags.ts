// A candidate's code in parts, and its variant flags in words (dioscuri_plant/search.py FLAGS and
// flag_words): "2D-HP-AB@2500+3000-2I1-ST" is 2 doublets, a heat pump top-up, absorption cooling,
// doublets at 2,500 and 3,000 m, two injectors on doublet 1, a treatment train per doublet.

export interface CodeParts {
  doublets: number | null;
  /** HP heat pump, BO boiler only, DH no top-up. */
  topup: string | null;
  /** AB absorption, EC electric chillers, NC no cooling. */
  cooling: string | null;
  /** The aquifers named after "@" (empty: the known one). */
  depths: number[];
  flags: string[];
}

/** Reads a code: "2D-HP-AB@3000-2I-BL" → 2, HP, AB, [3000], [2I, BL]. Unknown parts are left out. */
export function codeParts(code: string): CodeParts {
  const m = /^(\d+)D-(HP|BO|DH)-(AB|EC|NC)(?:@([\d+.]+))?((?:-[A-Z0-9.]+)*)$/.exec(code.trim());
  if (!m) return { doublets: null, topup: null, cooling: null, depths: [], flags: [] };
  return {
    doublets: Number(m[1]),
    topup: m[2],
    cooling: m[3],
    depths: m[4] ? m[4].split("+").map(Number).filter(Number.isFinite) : [],
    flags: m[5] ? m[5].split("-").filter(Boolean) : [],
  };
}

const FLAG_WORDS: Record<string, string> = {
  "2I": "two injectors per doublet",
  ST: "a treatment train (separator, filters) per doublet",
  BL: "the hottest doublet first (base load)",
  PL: "producers open over the lower half of the aquifer",
  PU: "producers open over the upper half of the aquifer",
  IU: "injectors open over the upper half of the aquifer",
  IL: "injectors open over the lower half of the aquifer",
  N1: "sized so that any one unit can be out (reliable plan)",
  EB: "no gas bought: an electric boiler for the peaks (the brine's own gas burnt in a small boiler, unless it is sold)",
  GS: "the brine's gas cleaned and sold to the gas grid (nothing burnt on site)",
  FC: "free cooling on the towers before the chillers",
  ATES: "a seasonal aquifer store (HT-ATES)",
};

/** A flag in words, the per-doublet ones too: "2I1" two injectors on doublet 1, "ST2" 2 treatment trains. */
export function flagWords(flag: string): string {
  if (FLAG_WORDS[flag]) return FLAG_WORDS[flag];
  const two = /^2I(\d+)$/.exec(flag);
  if (two) {
    const ds = two[1].split("");
    return `two injectors on doublet${ds.length > 1 ? "s" : ""} ${ds.length > 1 ? `${ds.slice(0, -1).join(", ")} and ${ds[ds.length - 1]}` : ds[0]}`;
  }
  const st = /^ST(\d+)$/.exec(flag);
  if (st) return `${st[1]} treatment trains`;
  const pv = /^PV([\d.]+)$/.exec(flag);
  if (pv) return `${pv[1]} MWp of own solar`;
  const ts = /^TS([\d.]+)$/.exec(flag);
  if (ts) return `a ${Number(ts[1]).toLocaleString("en-US")} MWh hot-water store`;
  const half = /^([PI])([LU])(\d+)$/.exec(flag);
  if (half) {
    const ds = half[3].split("");
    const which = ds.length > 1 ? `${ds.slice(0, -1).join(", ")} and ${ds[ds.length - 1]}` : ds[0];
    return `the ${half[1] === "P" ? "producer" : "injector"} of doublet${ds.length > 1 ? "s" : ""} ${which} open over the ${half[2] === "L" ? "lower" : "upper"} half`;
  }
  return flag;
}

/** The family a flag filters under: 2I1 and 2I12 are "2I", ST2 is "ST". */
export const flagFamily = (flag: string) =>
  /^2I\d*$/.test(flag) ? "2I" : /^ST\d*$/.test(flag) ? "ST" : /^[PI][LU]\d+$/.test(flag) ? flag.slice(0, 2) : /^PV[\d.]+$/.test(flag) ? "PV" : /^TS[\d.]+$/.test(flag) ? "TS" : flag;

/** Short names for the filter chips. */
export const FAMILY_NAMES: Record<string, string> = {
  "2I": "2 injectors",
  ST: "own trains",
  BL: "hottest first",
  PL: "producer lower ½",
  PU: "producer upper ½",
  IU: "injector upper ½",
  IL: "injector lower ½",
  N1: "reliable plan",
  EB: "gas-free",
  GS: "gas sold",
  FC: "free cooling",
  PV: "own solar",
  TS: "hot-water store",
  ATES: "seasonal store",
};

/** "aquifer at 3,000 m", "aquifers at 2,500 and 3,000 m": the "@" part in words. */
export function depthWords(depths: number[]): string {
  if (!depths.length) return "the known aquifer";
  const d = depths.map((x) => `${x.toLocaleString("en-US")} m`);
  return depths.length === 1 ? `aquifer at ${d[0]}` : `doublets at ${d.slice(0, -1).join(", ")} and ${d[d.length - 1]}`;
}

export const TOPUP_WORDS: Record<string, string> = { HP: "heat pump top-up", BO: "boiler top-up", DH: "no top-up" };
export const COOLING_WORDS: Record<string, string> = { AB: "absorption chiller", EC: "electric chillers", NC: "no cooling" };
