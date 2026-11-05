// The inputs card's form and the doublets' stop dates as plain functions, on the rows the server
// sends (confirm-edit.sse, make_ui_fixtures.py): the text of each field, its checks in the form's
// units, what changed and what "Confirm and run" sends; the stop dates in 2027, without overlap,
// long enough for the cap, and the answer.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { emptyChat, reduce, replay, runConfirm } from "../agent/reducer";
import { parseSse } from "../agent/sse";
import type { AgEvent, InputField } from "../agent/types";
import {
  canReset,
  cellProblem,
  changedKeys,
  changesOf,
  checkCard,
  consequences,
  dateOf,
  dayName,
  dayOf,
  defaultDraft,
  defaultWords,
  differsFromDefault,
  doubletProblem,
  draftProblems,
  draftsDiffer,
  fieldProblem,
  fieldText,
  fieldChanged,
  fieldValue,
  fieldWarning,
  fieldsOf,
  impossible,
  recordsChanges,
  recordsWords,
  initialDraft,
  initialStops,
  offDefaultKeys,
  operatingDaysOf,
  stopsAnswer,
  stopsProblems,
  stopsTogether,
  type StopsState,
} from "./inputsForm";

const here = dirname(fileURLToPath(import.meta.url));
const load = (name: string): AgEvent[] => parseSse(readFileSync(join(here, "..", "fixtures", `${name}.sse`), "utf-8"));
const turn = replay(reduce(emptyChat("f"), { type: "send", turnId: "t", message: "Design it", at: 0 }), load("confirm-edit")).turns[0];
const inputs = runConfirm(turn, 0)!.value;
const rows = inputs.rows;
const field = (key: string) => fieldsOf(rows).find((f) => f.key === key)!;
// The Maintenance section carries the doublets' stops (2 Nov; "stops" from older servers).
const stopsToggle = inputs.toggles!.find((t) => t.kind === "maintenance" || t.kind === "stops")!;

describe("the fields", () => {
  it("come from the server's rows: each planner parameter once, the value now as text", () => {
    const keys = fieldsOf(rows).map((f) => f.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys).toEqual(expect.arrayContaining(["heat_return_c", "gradient_c_per_km", "operating_days", "discount_rate", "objective", "n_doublets", "exclude", "aquifers"]));
    // One place per value: the known aquifer's rock is in the Aquifers table, not its own boxes.
    expect(keys).not.toContain("permeability_md");
    expect(rows.find((r) => r.label === "Aquifer")?.locked).toContain("first line is this aquifer");
    // The challenge's supply too (with a warning), and the brine's own properties (4 Nov).
    expect(keys).toEqual(expect.arrayContaining(["heat_supply_c", "brine_cp_j_kg_k", "brine_viscosity_pa_s", "gas_ch4_fraction"]));
    const draft = initialDraft(rows);
    expect(draft.heat_return_c).toBe("60");
    expect(draft.discount_rate).toBe(String(field("discount_rate").value)); // per cent, as shown
    // The aquifers (stream M's records field): the known one and two assumed deeper (2 Nov).
    expect((draft.aquifers as string[][]).map((r) => r[0])).toEqual(["2500", "3000", "3500"]);
    expect(field("aquifers").kinds).toEqual(["known", "assumed", "assumed"]);
    expect(draft.exclude).toEqual([]);
    expect(draft.n_doublets).toBe("");
  });

  it("checks a number in the form's units: its range, whole days, a number at all", () => {
    expect(fieldProblem(field("heat_return_c"), "50")).toBeNull();
    expect(fieldProblem(field("heat_return_c"), "5,5")).toBe("Between 20 and 95 °C.");
    expect(fieldProblem(field("gradient_c_per_km"), "90")).toBe("Between 10 and 80 °C/km.");
    expect(fieldProblem(field("operating_days"), "300.5")).toBe("Give a whole number.");
    expect(fieldProblem(field("operating_days"), "lots")).toBe("Give a number.");
    expect(fieldProblem(field("discount_rate"), "31")).toBe("Between 0 and 30 %.");
    expect(fieldProblem(field("reservoir_change_k"), "−10")).toBeNull(); // a typed minus sign
    const aq = initialDraft(rows).aquifers as string[][];
    expect(fieldProblem(field("aquifers"), aq)).toBeNull();
    expect(fieldProblem(field("aquifers"), [aq[0], ["9000", ...aq[1].slice(1)]])).toBe("Aquifer 2, depth: between 500 and 7000 m.");
    expect(fieldProblem(field("aquifers"), [aq[0], ["", ...aq[1].slice(1)]])).toBe("Aquifer 2, depth: required: give a value.");
    // Any other box may stay empty: the server fills it (the known one's value, the brine column's pressure).
    expect(fieldProblem(field("aquifers"), [aq[0], ["3000", "", "", "", ""]])).toBeNull();
    expect(fieldProblem(field("aquifers"), [])).toBe("Give at least 1 aquifer.");
    // An empty box is red: users forgot numbers and could not find the box (Ali, 3 Nov).
    expect(fieldProblem(field("gradient_c_per_km"), "")).toBe("Required: give a value.");
    expect(fieldProblem(field("gradient_c_per_km"), "  ")).toBe("Required: give a value.");
  });

  it("sends the server's units: a per cent as a fraction, records as numbers by column, choices as they are", () => {
    expect(fieldValue(field("discount_rate"), "6")).toBe(0.06);
    expect(fieldValue(field("heat_return_c"), "50,5")).toBe(50.5);
    expect(fieldValue(field("aquifers"), [["2500", "100", "200", "250", "0.8"], ["3200", "60", "", "", "1,2"]])).toEqual([
      { depth_m: 2500, thickness_m: 100, permeability_md: 200, pressure_bar: 250, gas_liquid_ratio: 0.8 },
      { depth_m: 3200, thickness_m: 60, permeability_md: null, pressure_bar: null, gas_liquid_ratio: 1.2 },
    ]);
    expect(fieldValue(field("objective"), "cost")).toBe("cost");
    expect(fieldValue(field("exclude"), ["heat_pump"])).toEqual(["heat_pump"]);
    expect(fieldValue(field("gradient_c_per_km"), "90")).toBeUndefined();
  });

  it("sends only what changed, and marks it", () => {
    const draft = { ...initialDraft(rows), heat_return_c: "50", gradient_c_per_km: "30.0", discount_rate: "6", exclude: ["heat_pump"] };
    expect(changedKeys(rows, draft).sort()).toEqual(["discount_rate", "exclude", "heat_return_c"]);
    expect(changesOf(rows, draft)).toEqual({ heat_return_c: 50, discount_rate: 0.06, exclude: ["heat_pump"] });
    expect(changesOf(rows, initialDraft(rows))).toEqual({});
  });

  it("refuses values that do not fit together, on both boxes of the pair", () => {
    const draft = { ...initialDraft(rows), flow_min_m3h: "250", flow_max_m3h: "200" };
    expect(draftProblems(rows, draft)).toEqual({
      flow_min_m3h: "The lowest flow can't be above the flow cap (200 m³/h).",
      flow_max_m3h: "The flow cap can't be below the lowest flow (250 m³/h).",
    });
    expect(draftProblems(rows, { ...initialDraft(rows), flow_min_m3h: "300" })).toEqual({}); // one fixed rate
    expect(draftProblems(rows, { ...initialDraft(rows), gradient_c_per_km: "0" })).toEqual({ gradient_c_per_km: "Between 10 and 80 °C/km." });
    expect(draftProblems(rows, initialDraft(rows))).toEqual({}); // the server's values are fine
    expect(draftProblems(rows, { ...initialDraft(rows), heat_return_c: "" })).toEqual({ heat_return_c: "Required: give a value." });
  });

  it("opens with the values the server refused, in the form's units", () => {
    const pct: InputField = { key: "discount_rate", label: "Discount rate", kind: "number", unit: "%", low: 0, high: 30, scale: 100, value: 5 };
    expect(initialDraft([{ group: "g", label: "Prices", value: "", source: "", kind: "assumed", fields: [pct] }], { discount_rate: 0.5 }).discount_rate).toBe("50");
    expect(fieldText(pct, null)).toBe("");
  });
});

describe("three levels of checks", () => {
  const draft = initialDraft(rows);
  const ctx = inputs.context!;

  it("blocks what is physically impossible, as the server does (card_edits.impossible)", () => {
    expect(Object.keys(impossible({ heat_supply_c: 70, heat_return_c: 70 })).sort()).toEqual(["heat_return_c", "heat_supply_c"]);
    expect(impossible({ cool_supply_c: 20, cool_return_c: 18 }).cool_return_c).toBe("The return must be above the supply (20 °C): the water warms up in the buildings.");
    expect(impossible({ pump_efficiency: 1 }).pump_efficiency).toBe("No pump turns all its electricity into lift: give less than 100 %.");
    expect(impossible({ gas_ch4_fraction: 0.9, gas_co2_fraction: 0.2 }).gas_co2_fraction).toBe("Methane and CO₂ make 110 % of the gas: more than all of it.");
    expect(impossible({ reservoir_pressure_bar: 700 }, 2500).reservoir_pressure_bar).toBe("More than the weight of the rock above the aquifer (about 564 bar at 2,500 m): the rock would crack open.");
    expect(impossible({ reservoir_pressure_bar: 250, pump_efficiency: 0.7 }, 2500)).toEqual({});
    // On the card: a pump typed at 100 % blocks the run.
    const issues = checkCard(rows, { ...draft, pump_efficiency: "100" }, ctx);
    expect(issues.pump_efficiency[0]).toEqual({ level: "block", text: "No pump turns all its electricity into lift: give less than 100 %." });
  });

  it("warns outside the challenge's caps (it still runs), else outside typical values", () => {
    expect(fieldWarning(field("flow_max_m3h"), 400)).toBe("The challenge allows at most 300 m³/h per doublet: the design will not meet the challenge.");
    expect(fieldWarning(field("max_brine_cooling_k"), 45)).toBe("The challenge allows the brine to be cooled by at most 40 K: the design will not meet the challenge.");
    expect(fieldWarning(field("operating_days"), 340)).toContain("at most 330 days a year: the design will not meet the challenge");
    expect(fieldWarning(field("operating_days"), 320)).toBeNull(); // fewer days than allowed: within the cap
    expect(fieldWarning(field("heat_supply_c"), 90)).toBe("The challenge requires heat at 100 °C: the design will not meet the challenge.");
    expect(fieldWarning(field("cool_supply_c"), 12)).toBe("The challenge requires cold at 20 °C: the design will not meet the challenge.");
    expect(fieldWarning(field("pump_efficiency"), 75)).toContain("sets the pumps at 70 %");
    expect(fieldWarning(field("gradient_c_per_km"), 45)).toBe("Outside the typical 25 to 40 °C/km: check it is right.");
    expect(fieldWarning(field("gradient_c_per_km"), 30)).toBeNull();
    // On the aquifers' table, as the old Aquifer boxes did (and as the server says it):
    // outside the typical values, and rock too tight to flow (the search fails there).
    const aq = draft.aquifers as string[][];
    const known = (k: string, h: string) => [aq[0][0], h, k, ...aq[0].slice(3)];
    const rare = checkCard(rows, { ...draft, aquifers: [known("3000", "100"), ...aq.slice(1)] }, ctx);
    expect(rare.aquifers[0]).toEqual({ level: "warn", text: "Aquifer 1, permeability: outside the typical 50 to 1,000 mD: check it is right." });
    const tight = checkCard(rows, { ...draft, aquifers: [known("5", "20"), ...aq.slice(1)] }, ctx);
    expect(tight.aquifers[0]).toEqual({ level: "warn", text: expect.stringMatching(/^Aquifer 1: the rock lets very little brine through \(k × h = 0.1 D·m/) });
    // The rock's weight on the known aquifer's line blocks the run.
    expect(draftProblems(rows, { ...draft, aquifers: [[aq[0][0], aq[0][1], aq[0][2], "700", aq[0][4]], ...aq.slice(1)] }).aquifers).toBe("Aquifer 1, pressure: 700 bar at 2,500 m is more than the rock above it weighs (about 575 bar).");
    // Nothing on the challenge's own values; the server says the same (warnings).
    const warned = Object.entries(checkCard(rows, draft, ctx)).filter(([, l]) => l.some((i) => i.level !== "note"));
    expect(warned).toEqual([]);
    expect(inputs.warnings).toEqual({});
  });

  it("notes what follows as the boxes change: the production temperature, the injection floor", () => {
    const v = { gradient_c_per_km: 30, reservoir_change_k: 0, max_brine_cooling_k: 40, flow_max_m3h: 300, brine_density_kg_m3: 1030, brine_cp_j_kg_k: 3990, operating_days: 330, heat_demand_scale: 1.2 };
    const out = consequences(v, ctx);
    expect(out.gradient_c_per_km).toBe("Brine at the producer: 12 + 30 °C/km × 2.5 km = 87 °C.");
    expect(out.max_brine_cooling_k).toBe("Injected at 47 °C or warmer (87 − 40).");
    expect(out.flow_max_m3h).toBe("One doublet at the cap, its brine cooled 40 K: about 13.7 MW of heat.");
    expect(out.operating_days).toBe("Each doublet is off 35 days a year; set when under Maintenance.");
    expect(out.heat_demand_scale).toBe("111.67 GWh × 1.2 = 134 GWh a year, peak 36 MW.");
    expect(consequences({ ...v, gradient_c_per_km: 34, reservoir_change_k: -5 }, ctx).max_brine_cooling_k).toBe("Injected at 52 °C or warmer (92 − 40).");
    // Live on the card: a 35 °C/km gradient moves the floor under "Brine cooled by at most".
    const issues = checkCard(rows, { ...draft, gradient_c_per_km: "35" }, ctx);
    expect(issues.max_brine_cooling_k).toContainEqual({ level: "note", text: "Injected at 60 °C or warmer (100 − 40)." });
    // Without a sum, nothing: what it is linked to is behind "more".
    expect(checkCard(rows, draft, ctx).heat_return_c).toBeUndefined();
  });
});

describe("a records field (the aquifers, stream M's row): a box per value, the same checks", () => {
  const aquifers: InputField = {
    key: "aquifers",
    label: "Aquifers",
    kind: "records",
    columns: [
      { key: "depth_m", label: "Depth", unit: "m", low: 500, high: 7000 },
      { key: "permeability_md", label: "Permeability", unit: "mD", low: 1, high: 10000 },
    ],
    value: [{ depth_m: 2500, permeability_md: 200 }],
    min_items: 1,
    max_items: 3,
  };
  const recRows = [{ group: "Reservoir and wells", label: "Aquifers", value: "", source: "", kind: "data", fields: [aquifers] }];

  it("shows each value as text, says which aquifer and column is wrong", () => {
    expect(fieldText(aquifers, aquifers.value)).toEqual([["2500", "200"]]);
    expect(fieldProblem(aquifers, [["2500", "200"]])).toBeNull();
    expect(fieldProblem(aquifers, [["2500", "200"], ["3200", ""]])).toBe("Aquifer 2, permeability: required: give a value.");
    expect(fieldProblem(aquifers, [["2500", "200"], ["9000", "50"]])).toBe("Aquifer 2, depth: between 500 and 7000 m.");
    expect(fieldProblem(aquifers, [])).toBe("Give at least 1 aquifer.");
    expect(fieldProblem(aquifers, [["1", "1"], ["1", "1"], ["1", "1"], ["1", "1"]])).toBe("At most 3 aquifers.");
    expect(cellProblem(aquifers.columns![0], "x")).toBe("Give a number.");
  });

  it("sends the whole list when it changed, as numbers by column", () => {
    const d = { aquifers: [["2500", "200"], ["3200", "150"]] };
    expect(fieldChanged(aquifers, d.aquifers)).toBe(true);
    expect(fieldChanged(aquifers, [["2500", "200"]])).toBe(false);
    expect(changesOf(recRows, d)).toEqual({ aquifers: [{ depth_m: 2500, permeability_md: 200 }, { depth_m: 3200, permeability_md: 150 }] });
    expect(draftProblems(recRows, { aquifers: [["2500", ""]] })).toEqual({ aquifers: "Aquifer 1, permeability: required: give a value." });
  });
});

describe("the aquifers as the server sends them (aquifers.card_field)", () => {
  const f = field("aquifers");
  const aq = initialDraft(rows).aquifers as string[][];

  it("checks them together as the server does: near the surface, the rock's weight, overlapping", () => {
    expect(fieldProblem(f, [aq[0], ["2560", ...aq[1].slice(1)]])).toBe("Aquifers 1 and 2 overlap (2,500 m and 2,560 m): give them depths further apart, or thinner layers.");
    expect(fieldProblem(f, [aq[0], ["3000", "100", "200", "800", "0.8"]])).toBe("Aquifer 2, pressure: 800 bar at 3,000 m is more than the rock above it weighs (about 690 bar).");
    expect(fieldProblem(f, [["550", "1000", "200", "60", "0.8"]])).toBe("Aquifer 1, thickness: 1000 m around 550 m would reach within 100 m of the surface.");
  });

  it("warns of a pressure far from the brine column's, as typed; the server's warnings otherwise", () => {
    const issues = checkCard(rows, { ...initialDraft(rows), aquifers: [aq[0], ["3000", "100", "200", "400", "0.8"]] }, inputs.context!);
    expect(issues.aquifers[0]).toEqual({ level: "warn", text: "Aquifer 2: 400 bar is 32 % above the brine column's 303 bar at 3,000 m; possible, but rare in Dutch aquifers." });
    expect(checkCard(rows, initialDraft(rows), inputs.context!).aquifers).toBeUndefined();
  });

  it("says the list and what changed in words", () => {
    expect(recordsWords(f, aq)).toBe("3 aquifers: 2,500 m (known), 3,000 m and 3,500 m");
    expect(recordsChanges(f, [aq[0], ["3000", "100", "200", "303.13", "1.2"], aq[2]])).toEqual([{ label: "Aquifer 2 · gas-liquid ratio", was: "0.8 Nm³/m³", now: "1.2 Nm³/m³" }]);
    expect(recordsChanges(f, [aq[0], aq[2]])).toEqual([{ label: "Aquifer 2", was: "3,000 m", now: "removed" }]);
    expect(recordsChanges(f, [aq[0], ["4200", "", "", "", ""]]).map((c) => `${c.label}: ${c.was} → ${c.now}`)).toEqual(["Aquifer 2: none → added at 4,200 m", "Aquifer 2: 3,000 m → removed", "Aquifer 3: 3,500 m → removed"]);
    // A box emptied: the server's fill ("auto").
    expect(recordsChanges(f, [aq[0], ["3000", "", "200", "303.13", "0.8"], aq[2]])).toEqual([{ label: "Aquifer 2 · thickness", was: "100 m", now: "auto" }]);
  });
});

describe("the stop dates", () => {
  it("reads and writes the inputs' dates as days of 2027", () => {
    expect(dateOf(0)).toBe("2027-01-01");
    expect(dateOf(189)).toBe("2027-07-09");
    expect(dayOf("2027-07-09")).toBe(189);
    expect(dayOf("2027-02-30")).toBeNull();
    expect(dayOf("2028-01-01")).toBe(365);
    expect(dayName(364)).toBe("31 Dec");
  });

  it("opens on Dioscuri's weeks, with its suggestion to start from", () => {
    const s = initialStops(stopsToggle);
    expect(s.mode).toBe("quiet");
    expect(s.doublets).toHaveLength(3);
    expect(s.doublets.map((d) => d.kind)).toEqual(["block", "block", "block"]);
    expect(s.doublets[0].start).toBe(dateOf(stopsToggle.suggested![0][0][0]));
    expect(stopsProblems(s, 330)).toEqual([null, null, null]);
    expect(stopsAnswer(s, 330)).toBe("[]");
  });

  it("opens on the user's dates: one block, or several ranges; the refused ones first", () => {
    const s = initialStops({ ...stopsToggle, stops: [[[180, 199], [230, 244]], [[100, 134]]] });
    expect(s.mode).toBe("mine");
    expect(s.doublets[0]).toMatchObject({ kind: "ranges", ranges: [{ from: "2027-06-30", to: "2027-07-19" }, { from: "2027-08-19", to: "2027-09-02" }] });
    expect(s.doublets[1]).toMatchObject({ kind: "block", start: "2027-04-11" });
    expect(initialStops(stopsToggle, [[[10, 29]]]).doublets[0].ranges).toEqual([{ from: "2027-01-11", to: "2027-01-30" }]);
  });

  it("checks each doublet: in 2027, in order, no overlap, at least 365 − operating days", () => {
    const ranges = (pairs: [string, string][]) => ({ kind: "ranges" as const, start: "", ranges: pairs.map(([from, to]) => ({ from, to })) });
    expect(doubletProblem({ kind: "block", start: "2027-07-09", ranges: [] }, 330)).toBeNull();
    expect(doubletProblem({ kind: "block", start: "2027-12-01", ranges: [] }, 330)).toBe("The stop must end by 31 Dec: start by 27 Nov.");
    expect(doubletProblem(ranges([["2027-06-30", "2027-07-19"], ["2027-08-19", "2027-09-02"]]), 330)).toBeNull();
    expect(doubletProblem(ranges([["2027-06-30", "2027-07-19"]]), 330)).toBe("20 of 35 days off: the 330-day cap needs 15 more.");
    expect(doubletProblem(ranges([["2027-06-30", "2027-07-19"], ["2027-07-10", "2027-07-30"]]), 330)).toBe("30 Jun to 19 Jul and 10 Jul to 30 Jul overlap.");
    expect(doubletProblem(ranges([["2027-07-19", "2027-06-30"]]), 330)).toBe("A range ends before it starts.");
    expect(doubletProblem(ranges([["2026-12-20", "2027-01-30"]]), 330)).toBe("Keep every date in 2027.");
    expect(doubletProblem(ranges([["", "2027-01-30"]]), 330)).toBe("Pick a date for every range.");
    // 300 operating days need 65 days off: the 35 of a block are short.
    expect(doubletProblem(ranges([["2027-06-01", "2027-07-05"]]), 300)).toBe("35 of 65 days off: the 300-day cap needs 30 more.");
  });

  it("sends every doublet's ranges in order; notes doublets off together", () => {
    const s: StopsState = {
      mode: "mine",
      doublets: [
        { kind: "ranges", start: "", ranges: [{ from: "2027-08-19", to: "2027-09-02" }, { from: "2027-06-30", to: "2027-07-19" }] },
        { kind: "block", start: "2027-07-10", ranges: [] },
      ],
    };
    expect(JSON.parse(stopsAnswer(s, 330))).toEqual([
      [
        [180, 199],
        [230, 244],
      ],
      [[190, 224]],
    ]);
    expect(stopsTogether(s, 330)).toBe("doublets 1 and 2 are both off on 10 days: the other units cover those days.");
    expect(stopsTogether({ ...s, mode: "quiet" }, 330)).toBeNull();
  });

  it("checks against the operating days the form sets", () => {
    expect(operatingDaysOf(rows, initialDraft(rows), 330)).toBe(330);
    expect(operatingDaysOf(rows, { ...initialDraft(rows), operating_days: "300" }, 330)).toBe(300);
    expect(operatingDaysOf(rows, { ...initialDraft(rows), operating_days: "9" }, 330)).toBe(330); // out of range: the card's
  });
});

// ------------------------------------------------------------------ the project's defaults (5 Nov)
// Each field carries the project's own value (`default`, card_edits.with_fields): a value that is
// not it is marked and can be put back; "Reset to defaults" asks the server for all of them. The
// fixture's card was recorded before defaults, so they are added here as the server sends them.

describe("the project's defaults", () => {
  const known = { depth_m: 2500, thickness_m: 100, permeability_md: 200, pressure_bar: 250, gas_liquid_ratio: 0.8 };
  const deeper = (d: number, p: number) => ({ ...known, depth_m: d, pressure_bar: p });
  const threeAquifers = [known, deeper(3000, 303.13), deeper(3500, 353.65)];
  // The card after "add a doublet at 4,200 m" read as a replacement: the user's 50 °C return,
  // two doublets and one aquifer; the defaults are the project's.
  const withDefaults: InputField[] = fieldsOf(rows).map((f) => ({
    ...f,
    default: f.key === "aquifers" ? threeAquifers : f.key === "n_doublets" ? "" : f.key === "exclude" ? [] : f.value,
  }));
  const at = (key: string) => withDefaults.find((f) => f.key === key)!;
  const shown = [{ ...rows[0], fields: withDefaults }, ...rows.slice(1).map((r) => ({ ...r, fields: [] }))];
  const draft = initialDraft(shown);

  it("compares as values, not as text: 60, 60.0 and 60,0 are the default", () => {
    expect(draftsDiffer(at("heat_return_c"), "60.0", "60")).toBe(false);
    expect(draftsDiffer(at("heat_return_c"), "60,0", "60")).toBe(false);
    expect(draftsDiffer(at("heat_return_c"), "50", "60")).toBe(true);
    expect(draftsDiffer(at("exclude"), ["boiler", "heat_pump"], ["heat_pump", "boiler"])).toBe(false);
    expect(fieldChanged(at("heat_return_c"), "60.0")).toBe(false);
  });

  it("marks a value typed away from its default, and the default puts it back", () => {
    const f = at("heat_return_c");
    expect(differsFromDefault(f, draft.heat_return_c)).toBe(false);
    expect(differsFromDefault(f, "50")).toBe(true);
    expect(defaultDraft(f)).toBe("60");
    expect(defaultWords(f)).toBe("60 °C");
    expect(differsFromDefault(f, defaultDraft(f))).toBe(false);
    // The doublets' "1 to 3" and the aquifers' list in words.
    expect(defaultWords(at("n_doublets"))).toBe("1 to 3 (the search picks)");
    expect(differsFromDefault(at("n_doublets"), "2")).toBe(true);
    expect(defaultWords(at("aquifers"))).toBe("3 aquifers: 2,500 m (known), 3,000 m and 3,500 m");
    const one = [["4200", "100", "200", "424.2", "0.8"]];
    expect(differsFromDefault(at("aquifers"), one)).toBe(true);
    expect(differsFromDefault(at("aquifers"), defaultDraft(at("aquifers")))).toBe(false);
  });

  it("lists the fields that are not at their defaults; none for an older server", () => {
    expect(offDefaultKeys(shown, draft)).toEqual([]);
    const typed = { ...draft, heat_return_c: "50", n_doublets: "2", aquifers: [["4200", "100", "200", "424.2", "0.8"]] };
    expect(offDefaultKeys(shown, typed).sort()).toEqual(["aquifers", "heat_return_c", "n_doublets"]);
    // Without `default` (a server from before 5 Nov) nothing is marked.
    expect(offDefaultKeys(rows, typed)).toEqual([]);
    expect(differsFromDefault(field("heat_return_c"), "50")).toBe(false);
  });

  it("a reset of everything has something to do: a box, a switch, or the server's own inputs", () => {
    expect(canReset(shown, draft, true)).toBe(false);
    expect(canReset(shown, { ...draft, heat_return_c: "50" }, true)).toBe(true);
    expect(canReset(shown, draft, true, true)).toBe(true); // a switch changed on the card
    // The card's values came from the message (the server says they are not the defaults).
    expect(canReset(shown, draft, false)).toBe(true);
  });
});
