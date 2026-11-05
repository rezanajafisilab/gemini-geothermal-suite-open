// A design's cost basis (GET /api/cost-basis) and the caught-and-fixed list the Evidence tab
// shows. The server computes both (src/gemini_agent/cost_basis.py, caught.py); nothing here is
// recomputed. Fixture mode has no cost basis: the call answers "not here" and the tab skips it.

import { request, usesFixtures, type ApiResult } from "./api";

/** One part of a cost, summed over heat and cold, per MWh of both. */
export interface BasisPart {
  item: string;
  kind: "capital" | "o&m" | "electricity" | "gas" | "carbon" | "credit" | string;
  eur_per_mwh: number;
  /** Of the year's costs (a credit is negative). */
  share: number;
  note?: string;
}

export interface BasisCase {
  value: string;
  lcoe: number | null;
  lcoh: number | null;
  lcoc: number | null;
}

/** The same plant repriced with one assumption at its low and its high value. */
export interface BasisSwing {
  key: string;
  label: string;
  /** The assumption's value in the case, in words. */
  base: string;
  low: BasisCase;
  high: BasisCase;
}

export interface CostBasis {
  design: string;
  headline: { lcoe: number | null; lcoh: number; lcoc: number | null; capex_meur: number };
  method: string;
  includes: BasisPart[];
  excludes: { item: string; why: string }[];
  rate: { value: number; label: string; source: string };
  lifetimes: { label: string; years: number }[];
  prices: { label: string; value: string; source: string }[];
  split: { heat_share: number | null; text: string; headline: string };
  swings: BasisSwing[];
  note: string;
}

export interface CaughtItem {
  id: string;
  group: "gemini" | "model" | "costs" | "agent" | "app" | string;
  group_label: string;
  title: string;
  failed: string;
  found: string;
  found_in: string;
  fix: string;
  commit: string | null;
  adr: string | null;
  patch: string | null;
  tests: string[];
  status: "fixed" | "avoided";
  source_label: string | null;
}

export interface Caught {
  updated: string;
  items: CaughtItem[];
  groups: { key: string; label: string; total: number; guarded: number }[];
  total: number;
  guarded: number;
  avoided: number;
}

const NONE: ApiResult<never> = { ok: false, status: 404, message: "Not in fixture mode.", offline: false };

/** GET /api/cost-basis: what a design's cost includes and leaves out, and how far it moves. */
export function getCostBasis(threadId: string, design: string, signal?: AbortSignal): Promise<ApiResult<CostBasis>> {
  if (usesFixtures()) return Promise.resolve(NONE);
  return request("GET", `/api/cost-basis?${new URLSearchParams({ threadId, design })}`, undefined, signal);
}
