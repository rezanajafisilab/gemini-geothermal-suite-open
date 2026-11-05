// The chat's design searches (S1, S2 …): their order and labels, and whether the newest search's
// gas baseline is priced like the designs now.

import { describe, expect, it } from "vitest";

import type { Attempt, Candidate, Design, Workbench } from "../../workbench";
import { attemptLabel, attemptTime, attemptsOf, currentBaseline, searchPricing } from "./search";

function cand(code: string, role: Candidate["role"], lcoe: number, extra: Partial<Candidate> = {}): Candidate {
  return {
    code,
    name: `Plant ${code}`,
    role,
    reason: "",
    n_doublets: 2,
    depth_m: 3000,
    topup: "boiler",
    cooling: "electric",
    sizes_mw: {},
    lcoh: lcoe + 2,
    lcoc: 36.17,
    lcoe,
    co2_t: 5000,
    co2_saving_pct: 78,
    capex_meur: 40,
    heat_coverage_pct: 100,
    cool_coverage_pct: 100,
    rounds: 1,
    changes: [],
    violations: [],
    verified: true,
    ...extra,
  };
}

// As the server sends them (src/gemini_agent/workbench.py, candidate_row): not in order.
const CANDIDATES = [
  cand("1D-HP-AB", "candidate", 70.05, { reason: "+20.7 €/MWh of heat and cold (70.0 against 49.3)", rounds: 2, changes: ["chillers 4 -> 6.9 MW"] }),
  cand("3D-DH-EC@2000", "failed", 45, { reason: "Heat short of 100 °C supply on 52 day(s).", violations: ["Heat short of 100 °C supply on 52 day(s)."], co2_t: 3000 }),
  cand("1D-BO-EC@3500", "candidate", 49.56, { reason: "+0.2 €/MWh of heat and cold (49.6 against 49.3)" }),
  cand("2D-BO-EC@3000", "chosen", 49.31, { co2_t: 5213.2 }),
  cand("1D-HP-EC@3000", "candidate", 50.68, { reason: "+1.4 €/MWh of heat and cold (50.7 against 49.3)" }),
  cand("2D-BO-AB@2000", "failed", 60, { reason: "", violations: ["Brine cooled by 43 K, above the 40 K cap."] }),
];

const REFERENCE = cand("REF", "reference", 82.41, { name: "Gas boilers and electric chillers (reference)", lcoh: 92.24, co2_saving_pct: 0, capex_meur: 4.7, co2_t: 24364.9 });

describe("priced like the designs", () => {
  // Measured against a gas plant of 4.7 M€: 40 M€ is 35.3 M€ more.
  const design = (code: string, lcoe: number, extra: Partial<Design> = {}, gasCapex = 4.7) =>
    ({
      id: code,
      code,
      origin: "agent",
      reservoir_delta_c: 0,
      economics: { lcoe, lcoh: lcoe + 2, capex_meur: 40, versus_reference: { extra_capex_meur: Math.round((40 - gasCapex) * 100) / 100 } },
      year: {},
      ...extra,
    }) as unknown as Design;
  const wb = (designs: Design[]): Pick<Workbench, "designs" | "candidates" | "reference"> => ({ designs, candidates: CANDIDATES, reference: REFERENCE });

  it("is current while the chosen design costs what its candidate did", () => {
    expect(searchPricing(wb([design("2D-BO-EC@3000", 49.31)]))).toBe("current");
    expect(currentBaseline(wb([design("2D-BO-EC@3000", 49.31)]))).toBe(REFERENCE);
  });

  it("is stale once the assumptions changed the design's cost, and the baseline no longer compares", () => {
    expect(searchPricing(wb([design("2D-BO-EC@3000", 55.2)]))).toBe("stale");
    expect(currentBaseline(wb([design("2D-BO-EC@3000", 55.2)]))).toBeNull();
  });

  it("is stale when the gas plant's capital changed, whatever the chosen design costs", () => {
    expect(searchPricing(wb([design("2D-BO-EC@3000", 49.31), design("U1", 50, { origin: "user" }, 5.9)]))).toBe("stale");
  });

  it("can't tell without the chosen design (a what-if or your own don't count)", () => {
    expect(searchPricing(wb([design("2D-BO-EC@3000", 55.2, { reservoir_delta_c: -5 }), design("U1", 50, { origin: "user" })]))).toBe("unknown");
    expect(currentBaseline(wb([]))).toBe(REFERENCE);
    expect(searchPricing(null)).toBe("unknown");
  });
});

// ------------------------------------------------------------------ attempts

// 30 Oct 2026, 16:12 and 16:40 UTC.
const T1 = Date.UTC(2026, 9, 30, 16, 12) / 1000;
const T2 = Date.UTC(2026, 9, 30, 16, 40) / 1000;
const NOON = Date.UTC(2026, 9, 30, 12, 0);
const UTC = { locale: "en-GB", timeZone: "UTC", now: NOON };

function attempt(n: number, extra: Partial<Attempt> = {}): Attempt {
  return {
    id: `S${n}`,
    n,
    at: n === 1 ? T1 : T2,
    message: n === 1 ? "Design a geothermal heating and cooling system for this district." : "Now the lowest CO₂ with one doublet.",
    label: n === 1 ? "lowest cost · 1–3 doublets · 2,500, 3,000 and 3,500 m" : "lowest CO₂ · 1 doublet · 3,000 m",
    objective: n === 1 ? "cost" : "co2",
    chosen: n === 1 ? "2D-BO-EC@3000" : "1D-HP-EC@3000",
    repriced: n === 2,
    candidates: CANDIDATES.map((c) => ({ ...c, attempt: `S${n}` })),
    reference: { ...REFERENCE, attempt: `S${n}` },
    ...extra,
  };
}

describe("attempts", () => {
  it("lists them newest first, whatever order the server sent", () => {
    expect(attemptsOf({ attempts: [attempt(1), attempt(2)] }).map((a) => a.id)).toEqual(["S2", "S1"]);
    expect(attemptsOf({ attempts: [attempt(2), attempt(1)] }).map((a) => a.id)).toEqual(["S2", "S1"]);
  });

  it("counts the top-level candidates of an older server as the one attempt, priced like the designs", () => {
    const [only, ...rest] = attemptsOf({ candidates: CANDIDATES, reference: REFERENCE });
    expect(rest).toEqual([]);
    expect(only).toMatchObject({ id: "S1", n: 1, at: null, chosen: "2D-BO-EC@3000", repriced: true, reference: REFERENCE });
    expect(only.candidates).toBe(CANDIDATES);
    expect(attemptsOf({ candidates: [] })).toEqual([]);
    expect(attemptsOf(null)).toEqual([]);
  });

  it("labels an attempt with its number, its time and what it looked for", () => {
    expect(attemptLabel(attempt(2), UTC)).toBe("Search 2 · 16:40 · lowest CO₂ · 1 doublet · 3,000 m");
    expect(attemptLabel(attempt(1), UTC)).toBe("Search 1 · 16:12 · lowest cost · 1–3 doublets · 2,500, 3,000 and 3,500 m");
    expect(attemptLabel(attempt(1, { at: null, label: "" }), UTC)).toBe("Search 1");
  });

  it("writes the time short, with the day when it was not today", () => {
    expect(attemptTime(T2, UTC)).toBe("16:40");
    expect(attemptTime(T2, { ...UTC, now: Date.UTC(2026, 9, 31, 9, 0) })).toBe("30 Oct, 16:40");
    expect(attemptTime(null, UTC)).toBe("");
    expect(attemptTime(Number.NaN, UTC)).toBe("");
  });
});
