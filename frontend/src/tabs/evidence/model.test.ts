// The Evidence tab's arithmetic: the scenario matrix, the benchmark cleanup and GEMINI's
// relative errors, on numbers from the server's real /api/evidence (29 Oct 2026).

import { describe, expect, it } from "vitest";

import type { Benchmark, EvalRun, EvalScenario } from "../../workbench";
import {
  behaviourLabel,
  bugRefs,
  buildMatrix,
  cleanCell,
  cleanTitle,
  divergingBar,
  fmtError,
  fmtUnit,
  fmtValue,
  isNumeric,
  median,
  numericColumns,
  parseWhen,
  patchTitle,
  relativeError,
  scenarioName,
  splitModels,
} from "./model";

const sc = (id: string, ok = true, expected = "design", got = expected): EvalScenario => ({ id, expected, got, ok, calls: 2, tokens: 1500, seconds: 3 });

function evalRun(device: string, when: string, scenarios: EvalScenario[], answerer = "qwen3.5:9b"): EvalRun {
  return {
    file: `${when}_${device}.jsonl`,
    device,
    answerer,
    when,
    passed: scenarios.filter((s) => s.ok).length,
    total: scenarios.length,
    tokens: scenarios.reduce((a, s) => a + s.tokens, 0),
    seconds: scenarios.reduce((a, s) => a + s.seconds, 0),
    scenarios,
  };
}

describe("the evals matrix", () => {
  const cpu = evalRun("cpu", "20261029T180525Z", [sc("S02_missing_network_temps", true, "clarify"), sc("S10_dutch_prompt", true, "clarify_or_design", "clarify"), sc("S01_full_brief")], "qwen3:1.7b");
  const auto = evalRun("auto", "20261029T174554Z", [sc("S01_full_brief"), sc("S17_values_after_design", false, "answer"), sc("S02_missing_network_temps", true, "clarify")]);
  const gpu = evalRun("gpu", "2026-10-29T08:30:00Z", [sc("S01_full_brief")]);

  it("orders the runs GPU, auto, CPU and the scenarios by number", () => {
    const m = buildMatrix([cpu, auto, gpu]);
    expect(m.runs.map((r) => r.label)).toEqual(["GPU", "Auto", "CPU"]);
    expect(m.rows.map((r) => r.id)).toEqual(["S01_full_brief", "S02_missing_network_temps", "S10_dutch_prompt", "S17_values_after_design"]);
  });

  it("puts each run's result in its column, and null where a run lacks the scenario", () => {
    const m = buildMatrix([cpu, auto]);
    const row = (id: string) => m.rows.find((r) => r.id === id)!;
    expect(row("S10_dutch_prompt").cells.map((c) => c?.got ?? null)).toEqual([null, "clarify"]);
    expect(row("S17_values_after_design").cells.map((c) => c?.ok ?? null)).toEqual([false, null]);
    expect(row("S17_values_after_design").failures).toBe(1);
    expect(row("S01_full_brief").failures).toBe(0);
    expect(row("S10_dutch_prompt")).toMatchObject({ num: "S10", name: "Dutch prompt", expected: "clarify_or_design" });
    expect(m.runs[0].failed).toEqual(["S17_values_after_design"]);
    expect(m.runs[0].when?.toISOString()).toBe("2026-10-29T17:45:54.000Z");
  });

  it("numbers two runs of one device and keeps the newest first", () => {
    const older = evalRun("cpu", "20261028T090000Z", [sc("S01_full_brief")]);
    const m = buildMatrix([older, cpu]);
    expect(m.runs.map((r) => [r.label, r.run.when])).toEqual([
      ["CPU", "20261029T180525Z"],
      ["CPU 2", "20261028T090000Z"],
    ]);
  });

  it("is empty with no runs", () => {
    expect(buildMatrix([])).toEqual({ runs: [], rows: [] });
  });

  it("names scenarios and behaviours in words", () => {
    expect(scenarioName("S07_what_if_reservoir")).toEqual({ num: "S07", name: "What-if reservoir" });
    expect(scenarioName("S22_what_from_gemini")).toEqual({ num: "S22", name: "What from GEMINI" });
    expect(scenarioName("odd")).toEqual({ num: "", name: "Odd" });
    expect(behaviourLabel("report_infeasible")).toBe("report infeasible");
    expect(behaviourLabel("answer_or_about_or_clarify")).toBe("answer, about or clarify");
    expect(behaviourLabel("clarify_or_design")).toBe("clarify or design");
  });

  it("reads both time stamps and takes medians", () => {
    expect(parseWhen("20261029T081500Z")?.toISOString()).toBe("2026-10-29T08:15:00.000Z");
    expect(parseWhen("2026-10-29T08:15:00Z")?.toISOString()).toBe("2026-10-29T08:15:00.000Z");
    expect(parseWhen("not a date")).toBeNull();
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 2, 3])).toBe(2.5);
    expect(median([])).toBeNaN();
  });
});

describe("benchmarks", () => {
  const reader: Benchmark = {
    title: "1. Reader: ten CPU models on the first pipeline ([ADR-0002](../docs/decisions/ADR-0002-llm-runtime-and-framework.md))",
    columns: ["Model", "Scenarios passed", "Seconds per scenario", "Tokens per scenario"],
    rows: [
      ["functiongemma:270m", "11/11", "0.5", "601"],
      ["qwen2.5:1.5b (the 2025 winner)", "11/11", "1.8", "565"],
    ],
    note: "",
  };
  const checker: Benchmark = {
    title: "4. Claim checker ([ADR-0007](x.md))",
    columns: ["Checker", "False claims caught", "True claims wrongly removed", "Time per check"],
    rows: [
      ["qwen3.5:9b", "8 of 8", "0 of 8", "0.8 s (GPU)"],
      ["qwen3:1.7b", "7 of 8", "2 of 8", "0.2 s (GPU), 4 s (CPU)"],
    ],
    note: "",
  };

  it("cleans titles of their numbers and links, keeping the records they cite", () => {
    expect(cleanTitle(reader.title)).toEqual({ text: "Reader: ten CPU models on the first pipeline", refs: ["ADR-0002"] });
    expect(cleanTitle("3. Answerer ([ADR-0005](a.md), [ADR-0006](b.md))")).toEqual({ text: "Answerer", refs: ["ADR-0005", "ADR-0006"] });
    expect(cleanTitle("Summary")).toEqual({ text: "Summary", refs: [] });
  });

  it("right-aligns the columns that hold numbers only", () => {
    expect(numericColumns(reader)).toEqual([false, true, true, true]);
    expect(numericColumns(checker)).toEqual([false, true, true, false]);
    expect(isNumeric(1650)).toBe(true);
    expect(isNumeric("45 s")).toBe(true);
    expect(isNumeric("2–10")).toBe(true);
    expect(isNumeric("25 / 25")).toBe(true);
    expect(isNumeric("no answer: still thinking")).toBe(false);
    expect(isNumeric("")).toBe(false);
  });

  it("cleans cells and finds model ids for the mono font", () => {
    expect(cleanCell("**`qwen3:1.7b`**")).toBe("qwen3:1.7b");
    expect(cleanCell(11840)).toBe("11,840");
    expect(splitModels("qwen3:1.7b fast, qwen3.5:4b reasoning")).toEqual([
      { text: "qwen3:1.7b", model: true },
      { text: " fast, ", model: false },
      { text: "qwen3.5:4b", model: true },
      { text: " reasoning", model: false },
    ]);
    expect(splitModels("Reader: every message")).toEqual([{ text: "Reader: every message", model: false }]);
  });
});

describe("GEMINI's bug impact", () => {
  it("measures the released value against the fixed one", () => {
    // A1's heat pump supply temperature: 314.69 °C released, 70 °C fixed.
    expect(relativeError(314.69, 70)).toBeCloseTo(3.4956, 4);
    // Brine flow: 116.775 against 195.471 m³/h.
    expect(relativeError(116.775, 195.471)).toBeCloseTo(-0.4026, 4);
    // Injector pump electricity: 0 against 0.281 MW.
    expect(relativeError(0, 0.281)).toBe(-1);
    // A2's heat exchanger duty: 0 and 0.
    expect(relativeError(0, 0)).toBe(0);
    expect(relativeError(5, 0)).toBe(Infinity);
    expect(relativeError(-5, 0)).toBe(-Infinity);
    // Negative fixed values keep the sign of the difference.
    expect(relativeError(-5.85, 9.25)).toBeCloseTo(-1.6324, 4);
    expect(relativeError(-2, -4)).toBe(0.5);
    // The absorption chiller: not in the released GEMINI.
    expect(relativeError(null, 2)).toBeNull();
    expect(relativeError(1, null)).toBeNull();
  });

  it("draws it on a diverging bar clipped at ±100%", () => {
    expect(divergingBar(-0.4026)).toEqual({ side: "neg", width: expect.closeTo(40.26, 2), clipped: false });
    expect(divergingBar(3.4956)).toEqual({ side: "pos", width: 100, clipped: true });
    expect(divergingBar(-1)).toEqual({ side: "neg", width: 100, clipped: false });
    expect(divergingBar(Infinity)).toEqual({ side: "pos", width: 100, clipped: true });
    expect(divergingBar(0)).toEqual({ side: "none", width: 0, clipped: false });
    expect(divergingBar(null)).toEqual({ side: "none", width: 0, clipped: false });
    expect(divergingBar(0.5, 2)).toEqual({ side: "pos", width: 25, clipped: false });
  });

  it("labels errors and values", () => {
    expect(fmtError(3.4956)).toBe("+350%");
    expect(fmtError(-0.4026)).toBe("−40%");
    expect(fmtError(0.0412)).toBe("+4.1%");
    expect(fmtError(0)).toBe("0%");
    expect(fmtError(Infinity)).toBe("from 0");
    expect(fmtError(null)).toBe("–");
    expect(fmtValue(314.69)).toBe("314.7");
    expect(fmtValue(0.166)).toBe("0.166");
    expect(fmtValue(70.0)).toBe("70");
    expect(fmtValue(4.289)).toBe("4.29");
    expect(fmtValue(-5.85)).toBe("−5.85");
    expect(fmtValue(0)).toBe("0");
    expect(fmtValue(null)).toBe("–");
    expect(fmtUnit("m3/h")).toBe("m³/h");
  });

  const patches = [
    { file: "02_injection_friction_sign.diff", title: "Injector well: friction sign — F3" },
    { file: "05_esp_affinity_flow_scaling.diff", title: "ESP: affinity-law flow scaling — F5" },
    { file: "03_roughness_default_4p5e-5m.diff", title: "Well pipe roughness default 10 mm → 0.045 mm — F10" },
    { file: "08_heatpump_electricity_emission.diff", title: "Heat pump: CO₂ of its electricity" },
    { file: "10_heatpump_carnot_source_outlet.diff", title: "Heat pump: Carnot COP at the source outlet" },
  ];

  it("splits the bug causes into chips tied to their patches", () => {
    const refs = bugRefs("F10 pipe roughness, F5 ESP speed scaling", patches);
    expect(refs.map((r) => [r.text, r.code, r.patch?.file])).toEqual([
      ["F10 pipe roughness", "F10", "03_roughness_default_4p5e-5m.diff"],
      ["F5 ESP speed scaling", "F5", "05_esp_affinity_flow_scaling.diff"],
    ]);
    // Commas inside brackets don't split; "(08)" is the patch's number.
    expect(bugRefs("flow (F10, F5)", patches).map((r) => r.text)).toEqual(["flow (F10, F5)"]);
    expect(bugRefs("electricity not counted (08)", patches)[0].patch?.file).toBe("08_heatpump_electricity_emission.diff");
    expect(bugRefs("F2 spurious root; Carnot at the source outlet (10)", patches).map((r) => [r.code, r.patch?.file ?? null])).toEqual([
      ["F2", null],
      [null, "10_heatpump_carnot_source_outlet.diff"],
    ]);
  });

  it("takes the bug code off a patch's title", () => {
    expect(patchTitle("Injector well: friction sign — F3")).toEqual({ text: "Injector well: friction sign", code: "F3" });
    expect(patchTitle("Simulator: heat pump in the registry")).toEqual({ text: "Simulator: heat pump in the registry", code: null });
  });
});
