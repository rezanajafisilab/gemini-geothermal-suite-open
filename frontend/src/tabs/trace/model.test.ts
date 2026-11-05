// The Trace tab's arithmetic: run order, the step timeline on one scale, totals, step facts,
// tool grouping and the export file, on runs shaped like the server's (src/gemini_agent/workbench.py).

import { describe, expect, it } from "vitest";

import type { TraceRun, TraceStep } from "../../workbench";
import {
  argSummary,
  codeFunction,
  deviceLabel,
  exportName,
  exportPayload,
  kindCounts,
  outcomeLabel,
  outcomeTone,
  pickRun,
  resultFlags,
  runTotals,
  sortRuns,
  startedMs,
  stepFacts,
  tickStep,
  timeline,
  toolGroups,
} from "./model";

const step = (name: string, kind: string, seconds: number, meta: Record<string, unknown> = {}, code: string | null = null): TraceStep => ({
  name,
  label: name,
  kind,
  code,
  seconds,
  meta,
});

function run(runId: string, started: number, extra: Partial<TraceRun> = {}): TraceRun {
  return {
    runId,
    started,
    message: `message ${runId}`,
    mode: "fast",
    device: "auto",
    seconds: 3.503,
    tokens: { prompt: 2114, output: 349 },
    steps: [],
    calls: [],
    tools: [],
    outcome: "design",
    ...extra,
  };
}

// The real run of "Design a geothermal heating and cooling system…" (29 Oct 2026, GPU).
const DESIGN_STEPS = [
  step("intake", "model", 0.257, { tokens: 890, model: "qwen3:1.7b", device: "gpu", intent: "design", screened: false }),
  step("plan", "plan", 0, { decided_by: "rules" }, "plan(brief, options)"),
  step("doublet", "tool", 0.01, { calls: 2, failed: 0 }, "solve_doublet(depth_m=2500, 1500)"),
  step("simulate", "tool", 0.021, { calls: 3, failed: 0 }, "simulate_year(A1, A2, A4)"),
  step("economics", "tool", 0.003, { calls: 3, failed: 0 }, "economics(A1, A2, A4)"),
  step("verify", "check", 0, { passed: 3, total: 3 }, "verify_design(A1, A2, A4)"),
  step("answer", "model", 3.195, { decided_by: "model", model: "qwen3.5:9b", device: "gpu" }, "answer(self, project, A1, A4, A2, draft)"),
  step("report", "report", 0, { ungrounded: [] }),
];

describe("runs", () => {
  it("reads the start in ms, or in seconds from older traces and the fixtures", () => {
    expect(startedMs(1793299082544)).toBe(1793299082544);
    expect(startedMs(1793265124)).toBe(1793265124000);
    expect(startedMs(0)).toBe(0);
  });

  it("sorts newest first, mixing ms and seconds, and keeps the server's order on a tie", () => {
    const runs = [run("a", 1793265124), run("b", 1793299082544), run("c", 1793299086056), run("d", 1793299086056)];
    expect(sortRuns(runs).map((r) => r.runId)).toEqual(["d", "c", "b", "a"]);
    // The input is left as it was.
    expect(runs.map((r) => r.runId)).toEqual(["a", "b", "c", "d"]);
  });

  it("follows the newest run unless one was picked by hand, and falls back when it is gone", () => {
    const sorted = sortRuns([run("a", 1), run("b", 2), run("c", 3)]);
    expect(pickRun(sorted, null, true)?.runId).toBe("c");
    expect(pickRun(sorted, "a", false)?.runId).toBe("a");
    expect(pickRun(sorted, "a", true)?.runId).toBe("c");
    expect(pickRun(sorted, "gone", false)?.runId).toBe("c");
    expect(pickRun([], "a", false)).toBeNull();
  });

  it("names the device, from the steps when the run says auto", () => {
    expect(deviceLabel(run("a", 1, { device: "gpu" }))).toBe("GPU");
    expect(deviceLabel(run("a", 1, { device: "auto", steps: DESIGN_STEPS }))).toBe("GPU (auto)");
    expect(deviceLabel(run("a", 1, { device: "auto" }))).toBe("auto");
  });

  it("gives outcomes a tone and a label", () => {
    expect(outcomeTone("design")).toBe("teal");
    expect(outcomeTone("clarify")).toBe("amber");
    expect(outcomeTone("refuse")).toBe("red");
    expect(outcomeTone("report_infeasible")).toBe("red");
    expect(outcomeTone("answer")).toBe("grey");
    expect(outcomeLabel("report_infeasible")).toBe("report infeasible");
    expect(outcomeLabel("")).toBe("unfinished");
  });
});

describe("the step timeline", () => {
  it("puts the steps one after another on the run's time scale", () => {
    const tl = timeline(DESIGN_STEPS, 3.503);
    expect(tl.total).toBe(3.503);
    expect(tl.rows.map((r) => r.start)).toEqual([0, 0.257, 0.257, 0.267, 0.288, 0.291, 0.291, 3.486].map((v) => expect.closeTo(v, 9)));
    const answer = tl.rows[6];
    expect(answer.left).toBeCloseTo((0.291 / 3.503) * 100, 9);
    expect(answer.width).toBeCloseTo((3.195 / 3.503) * 100, 9);
    // Bars never run past the end of the scale.
    for (const r of tl.rows) expect(r.left + r.width).toBeLessThanOrEqual(100 + 1e-9);
    expect(tl.rows.reduce((a, r) => a + r.width, 0)).toBeLessThanOrEqual(100);
  });

  it("stretches the scale to the steps' sum when the run's own time is shorter", () => {
    const tl = timeline([step("a", "model", 2), step("b", "tool", 3)], 4);
    expect(tl.total).toBe(5);
    expect(tl.rows[1].left).toBe(40);
    expect(tl.rows[1].width).toBe(60);
  });

  it("puts round ticks from 0 to the end", () => {
    const tl = timeline(DESIGN_STEPS, 3.503);
    expect(tl.ticks.map((t) => t.label)).toEqual(["0", "1 s", "2 s", "3 s"]);
    expect(tl.ticks[3].left).toBeCloseTo((3 / 3.503) * 100, 9);
    expect(tickStep(0.4)).toBe(0.1);
    expect(tickStep(54)).toBe(15);
    expect(timeline([step("a", "tool", 0.25)], 0.25).ticks.map((t) => t.label)).toEqual(["0", "0.05 s", "0.10 s", "0.15 s", "0.20 s", "0.25 s"]);
  });

  it("copes with no time at all", () => {
    const tl = timeline([step("a", "plan", 0)], 0);
    expect(tl.total).toBe(0);
    expect(tl.rows[0]).toMatchObject({ left: 0, width: 0 });
    expect(tl.ticks).toEqual([]);
  });

  it("counts the kinds in legend order, unknown kinds last", () => {
    const counts = kindCounts([...DESIGN_STEPS, step("x", "mystery", 0)]);
    expect(counts.map((c) => [c.info.key, c.count])).toEqual([
      ["model", 2],
      ["tool", 3],
      ["plan", 1],
      ["check", 1],
      ["report", 1],
      ["mystery", 1],
    ]);
  });
});

describe("what a step reports", () => {
  it("turns metadata into short facts", () => {
    const text = (s: TraceStep) => stepFacts(s).map((f) => `${f.tone}:${f.text}`);
    expect(text(DESIGN_STEPS[0])).toEqual(["grey:890 tokens", "grey:intent: design"]);
    expect(text(DESIGN_STEPS[5])).toEqual(["ok:3 of 3 pass"]);
    expect(text(DESIGN_STEPS[7])).toEqual(["ok:every number traced"]);
    expect(text(step("claims", "model", 0.9, { decided_by: "model", checked: 3, supported: 1, general: 2, removed: 1 }))).toEqual([
      "teal:model decided",
      "grey:3 claims checked",
      "red:1 removed",
    ]);
    expect(text(step("answer", "model", 1, { corrections: ["a", "b"], ungrounded: ["42.4"] }))).toEqual(["amber:2 corrections", "red:1 number not traced"]);
    expect(text(step("doublet", "tool", 1, { calls: 2, failed: 1 }))).toEqual(["grey:2 calls", "red:1 failed"]);
  });
});

describe("tool calls", () => {
  const tools: TraceRun["tools"] = [
    { name: "solve_doublet", args: { depth_m: 2500, reservoir_delta_c: 0 }, result: { cached: false, result: { source: "gemini", flow_m3h: 195.5 } } },
    { name: "solve_doublet", args: { depth_m: 1500, reservoir_delta_c: 0 }, result: { cached: true, result: { source: "gemini" } } },
    { name: "simulate_year", args: { alternative: { code: "A1", name: "Deep doublet" }, brief: {} }, result: { cached: false, result: { source: "gemini+mock" } } },
    { name: "search_docs", args: { query: "what is geothermal energy?", only_attached: false }, result: { passages: [] } },
  ];

  it("finds the function a step calls", () => {
    expect(codeFunction("solve_doublet(depth_m=2500, 1500)")).toBe("solve_doublet");
    expect(codeFunction("plan(brief, options)")).toBe("plan");
    expect(codeFunction(null)).toBeNull();
    expect(codeFunction("no call here")).toBeNull();
  });

  it("sums up arguments in a line", () => {
    expect(argSummary(tools[0].args)).toBe("depth_m=2500, reservoir_delta_c=0");
    expect(argSummary(tools[2].args)).toBe("alternative=A1");
    expect(argSummary(tools[3].args)).toBe('query="what is geothermal energy?", only_attached=false');
    expect(argSummary(null)).toBe("");
  });

  it("flags results from the cache and who computed them", () => {
    expect(resultFlags(tools[0].result).map((f) => f.text)).toEqual(["GEMINI"]);
    expect(resultFlags(tools[1].result).map((f) => f.text)).toEqual(["from cache", "GEMINI"]);
    expect(resultFlags({ error: "boom" }).map((f) => f.text)).toEqual(["error"]);
    expect(resultFlags("text")).toEqual([]);
  });

  it("groups the calls under the step that made them, the rest last", () => {
    const groups = toolGroups(run("a", 1, { steps: DESIGN_STEPS, tools }));
    expect(groups.map((g) => [g.title, g.calls.map((c) => c.index)])).toEqual([
      ["doublet", [0, 1]],
      ["simulate", [2]],
      ["Other tool calls", [3]],
    ]);
  });
});

describe("totals and export", () => {
  it("adds up the calls, and tokens per purpose", () => {
    const t = runTotals(
      run("a", 1, {
        calls: [
          { purpose: "intake", model: "qwen3:1.7b", prompt_tokens: 796, output_tokens: 70, seconds: 0.271, ok: true },
          { purpose: "answer", model: "qwen3.5:9b", prompt_tokens: 1492, output_tokens: 149, seconds: 2.346, ok: true },
          { purpose: "claims", model: "qwen3.5:9b", prompt_tokens: 1123, output_tokens: 30, seconds: 0.885, ok: false },
        ],
        seconds: 3.565,
      }),
    );
    expect(t).toMatchObject({ calls: 3, failedCalls: 1, prompt: 3411, output: 249, tokens: 3660, models: ["qwen3:1.7b", "qwen3.5:9b"] });
    expect(t.modelSeconds).toBeCloseTo(3.502, 9);
    expect(t.byPurpose.map((p) => [p.purpose, p.total])).toEqual([
      ["intake", 866],
      ["answer", 1641],
      ["claims", 1153],
    ]);
  });

  it("falls back to the run's own token count when it has no calls", () => {
    expect(runTotals(run("a", 1)).tokens).toBe(2463);
  });

  it("writes the export as the server sent the runs, with a safe file name", () => {
    const r = run("fd84647c07", 1793299082544);
    const p = exportPayload("t1", [r], new Date("2026-10-29T18:00:00Z"));
    expect(p).toEqual({ kind: "dioscuri-trace", threadId: "t1", exported: "2026-10-29T18:00:00.000Z", runs: [r] });
    expect(exportName("t1", "fd84647c07")).toBe("dioscuri-trace-t1-fd84647c07.json");
    expect(exportName("a b/c")).toBe("dioscuri-trace-a_b_c.json");
    expect(exportName(null)).toBe("dioscuri-trace-chat.json");
  });
});
