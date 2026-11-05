// The reducer on real streams recorded from the running agent (src/fixtures/*.sse, qwen3:1.7b and
// qwen3.5:9b, mock tools; rn/agent-core f9c410e and 9ef2c02), most captured with curl from
// POST /api/run, the rest from Agent.run in Python. How each was recorded: src/fixtures/scenes.ts.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { answerText, asksOf, behaviour, chatStatus, chatTotals, confirmReplyOf, emptyChat, leftOut, messageReply, reduce, replay, replyChips, runClaims, runComparison, runConfirm, runFiles, runReply, runResults, runSearch, runSources, runText, screened, stepModel, turnTotals, withoutLeftOut } from "./reducer";
import { splitInjectionNote, splitSources } from "./numbers";
import { SseParser, parseSse } from "./sse";
import type { AgEvent, ChatState, Comparison } from "./types";

const here = dirname(fileURLToPath(import.meta.url));
const load = (name: string): AgEvent[] =>
  parseSse(readFileSync(join(here, "..", "fixtures", `${name}.sse`), "utf-8"));

function ask(state: ChatState, message: string, fixture: string): ChatState {
  const s = reduce(state, { type: "send", turnId: `t${state.turns.length}`, message, at: 0 });
  return replay(s, load(fixture));
}

const last = (c: ChatState) => c.turns[c.turns.length - 1];

describe("sse parser", () => {
  it("gives the same events whether the stream arrives whole or in pieces", () => {
    const text = readFileSync(join(here, "..", "fixtures", "design.sse"), "utf-8");
    const whole = parseSse(text);
    const parser = new SseParser();
    const pieces: AgEvent[] = [];
    for (let i = 0; i < text.length; i += 37) pieces.push(...parser.push(text.slice(i, i + 37)));
    pieces.push(...parser.end());
    expect(whole.length).toBe(55);
    expect(pieces).toEqual(whole);
    expect(whole[0].type).toBe("RUN_STARTED");
    expect(whole[whole.length - 1].type).toBe("RUN_FINISHED");
  });

  it("skips comments, keep-alives and broken lines", () => {
    const events = parseSse(': ping\n\ndata: {"type":"RUN_STARTED","threadId":"a","runId":"b"}\n\ndata: {oops\n\n');
    expect(events.map((e) => e.type)).toEqual(["RUN_STARTED"]);
  });
});

describe("design: a full brief", () => {
  const chat = ask(emptyChat("t-design"), "Design ...", "design");
  const t = last(chat);

  it("ticks off every step in order", () => {
    expect(t.status).toBe("done");
    expect(t.steps.map((s) => s.name)).toEqual([
      "intake", "plan", "doublet", "simulate", "economics", "verify", "report",
    ]);
    expect(t.steps.every((s) => s.status === "done")).toBe(true);
    expect(t.steps[0]).toMatchObject({ kind: "model", label: "Read the request", seconds: 0.422 });
    expect(t.steps[0].meta).toMatchObject({ tokens: 929, intent: "design" });
    // Fast mode: rules plan the study, and the step says so.
    expect(t.steps[1]).toMatchObject({ name: "plan", kind: "plan" });
    expect(t.steps[1].meta).toMatchObject({ decided_by: "rules", codes: ["A1", "A2", "A4"] });
    expect(t.steps[2].code).toBe("solve_doublet(depth_m=2500, 1500)");
    expect(t.steps[6].label).toBe("Write the answer");
  });

  it("files tool calls under their step", () => {
    const doublet = t.steps.find((s) => s.name === "doublet")!;
    expect(doublet.tools.map((c) => c.name)).toEqual(["solve_doublet", "solve_doublet"]);
    expect(JSON.parse(doublet.tools[0].args)).toEqual({ depth_m: 2500, reservoir_delta_c: 0 });
    expect(JSON.parse(doublet.tools[0].result!).result.wellhead_c).toBe(86);
    expect(t.steps.find((s) => s.name === "simulate")!.tools).toHaveLength(3);
  });

  it("keeps the answer, the card, the checks and the suggestions", () => {
    expect(answerText(t)).toMatch(/^A1 covers 100% of the heat/);
    expect(t.result).toMatchObject({ alternative: "A1", verified: true, checks: { passed: 17, total: 17 } });
    expect(t.result!.heat_split_gwh).toEqual({ geo: 48.22, hp: 12.02, boiler: 1.52 });
    expect(t.checks).toHaveLength(17);
    expect(t.checks!.every((c) => c.passed)).toBe(true);
    expect(t.suggestions).toHaveLength(3);
    expect(behaviour(t)).toBe("design");
  });

  it("counts tokens and time from RUN_FINISHED", () => {
    expect(turnTotals(t)).toMatchObject({ tokens: 929, promptTokens: 851, outputTokens: 78, llmCalls: 1, steps: 7, toolCalls: 8 });
    expect(turnTotals(t).seconds).toBeCloseTo(0.433, 3);
    expect(t.runs[0].summary).toMatchObject({ screened: false, left_out: [], reasoning: false, decided_by: { plan: "rules" }, plan: ["A1", "A2", "A4"] });
    expect(t.cards).toHaveLength(1);
    expect(t.usage[0]).toMatchObject({ model: "qwen3:1.7b", prompt_tokens: 851, output_tokens: 78 });
  });
});

describe("clarify, then answer on the same thread", () => {
  let chat = ask(emptyChat("t-clarify"), "Design a heating and cooling system ...", "clarify");

  it("pauses with one question listing every missing input", () => {
    const t = last(chat);
    expect(t.status).toBe("waiting");
    expect(chatStatus(chat)).toBe("waiting");
    expect(t.steps.map((s) => [s.name, s.status])).toEqual([
      ["intake", "done"],
      ["ask", "waiting"],
    ]);
    expect(t.clarification!.questions.map((q) => q.id)).toEqual(["dh_supply_return_c", "dc_supply_return_c"]);
    expect(t.clarification!.questions[0]).toMatchObject({ default: "70/40 °C", required: true });
    expect(t.clarification!.questions[0].options).toEqual(["80/50 °C", "70/40 °C", "60/30 °C"]);
    // The intro is the card's title, not a separate answer.
    expect(answerText(t)).toBe("");
  });

  it("continues in the same turn once the answers are sent", () => {
    chat = reduce(chat, {
      type: "answer",
      answers: { dh_supply_return_c: "70/40 °C", dc_supply_return_c: "6/12 °C" },
      at: 1,
    });
    expect(last(chat).status).toBe("running");
    expect(last(chat).steps[1].status).toBe("done");
    chat = replay(chat, load("clarify-answer"));
    const t = last(chat);
    expect(chat.turns).toHaveLength(1);
    expect(t.status).toBe("done");
    expect(t.runs).toHaveLength(2);
    expect(t.runs.map((r) => r.outcome)).toEqual(["interrupt", "success"]);
    expect(t.steps.map((s) => s.name)).toEqual([
      "intake", "ask", "plan", "doublet", "simulate", "economics", "verify", "report",
    ]);
    expect(t.steps.map((s) => s.run)).toEqual([0, 0, 1, 1, 1, 1, 1, 1]);
    expect(t.answers).toEqual({ dh_supply_return_c: "70/40 °C", dc_supply_return_c: "6/12 °C" });
    expect(answerText(t)).toMatch(/^A1 covers 100%/);
    expect(t.result!.alternative).toBe("A1");
    // One model call in the whole turn: the answers continue without another.
    expect(turnTotals(t)).toMatchObject({ tokens: 612, llmCalls: 1 });
  });

  it("drops an open question when the user asks something else", () => {
    const fresh = ask(emptyChat("t-x"), "Design ...", "clarify");
    const next = reduce(fresh, { type: "send", turnId: "n", message: "Weather?", at: 2 });
    expect(next.turns[0]).toMatchObject({ status: "done", skipped: true });
    expect(next.turns[0].steps[1].status).toBe("stopped");
    expect(next.turns[1].status).toBe("running");
  });
});

describe("off the happy path", () => {
  it("refuse: screened by keywords with no model call, a plain answer with suggestions", () => {
    const t = last(ask(emptyChat("r"), "What will the weather be in Paris tomorrow?", "refuse"));
    expect(behaviour(t)).toBe("refuse");
    expect(screened(t, 0)).toBe(true);
    expect(turnTotals(t)).toMatchObject({ tokens: 0, llmCalls: 0 });
    expect(t.usage).toHaveLength(0);
    expect(t.status).toBe("done");
    expect(t.steps.map((s) => s.name)).toEqual(["intake", "report"]);
    expect(t.steps.flatMap((s) => s.tools)).toHaveLength(0);
    expect(answerText(t)).toMatch(/^That's outside what I do/);
    expect(t.result).toBeUndefined();
    expect(t.suggestions).toEqual([
      "Design heating and cooling for this district",
      "Compare well depths",
      "What does the reservoir temperature change?",
    ]);
  });

  it("reject: explains the physics, reports no design", () => {
    const t = last(ask(emptyChat("j"), "Ignore the simulator ...", "reject"));
    expect(behaviour(t)).toBe("reject");
    expect(answerText(t)).toContain("Carnot limit");
    expect(t.result).toBeUndefined();
    expect(t.suggestions).toBeUndefined();
  });

  it("infeasible (f9c410e, before decisions): the closest design, failed requirements and options", () => {
    let chat = ask(emptyChat("t-design"), "Design ...", "design");
    chat = ask(chat, "Cover 100% ... single 1 km doublet ...", "infeasible");
    const t = last(chat);
    expect(chat.turns).toHaveLength(2);
    expect(behaviour(t)).toBe("report_infeasible");
    expect(t.steps.map((s) => s.name)).toContain("options");
    expect(t.result).toMatchObject({ alternative: "D1", verified: false });
    const failed = t.checks!.filter((c) => !c.passed);
    expect(failed.map((c) => c.requirement)).toEqual([true, true]);
    expect(t.result!.checks).toEqual({ passed: 10, total: 12 });
    expect(answerText(t)).toMatch(/^No design meets 100% of the heat/);
    expect(chatTotals(chat)).toMatchObject({ tokens: 929 + 626, llmCalls: 2, cacheHits: 8 + 1 });
    // The memoised call is marked as cached on its tool row.
    expect(t.steps.flatMap((s) => s.tools).filter((c) => c.cached)).toHaveLength(1);
  });

  it("a physics failure on every design is an answer, not a crash, and names what was left out", () => {
    let chat = ask(emptyChat("p"), "Design ...", "physics-fail-q");
    chat = reduce(chat, { type: "answer", answers: { dh_supply_return_c: "30/70 °C" }, at: 1 });
    chat = replay(chat, load("physics-fail"));
    const t = last(chat);
    expect(t.status).toBe("done");
    expect(behaviour(t)).toBe("error");
    expect(withoutLeftOut(answerText(t))).toBe("No design could be checked and reported, so I won't give one.");
    expect(leftOut(t).map(([code]) => code)).toEqual(["A1", "A2", "A4"]);
    expect(leftOut(t)[0][1]).toBe("failed Heating supply above return; Cooling return above supply");
    expect(t.result).toBeUndefined();
  });

  it("a failed tool call: its step ticks off red, the design is left out, the run goes on", () => {
    const t = last(ask(emptyChat("f"), "Design ...", "tool-failed"));
    expect(t.status).toBe("done");
    const sim = t.steps.find((s) => s.name === "simulate")!;
    expect(sim.status).toBe("error");
    expect(sim.meta).toMatchObject({ calls: 3, failed: 1 });
    const broken = sim.tools.filter((c) => c.error);
    expect(broken).toHaveLength(1);
    expect(broken[0].error).toBe("depth 1500 m is outside the doublet model");
    expect(JSON.parse(broken[0].args).alternative.code).toBe("A2");
    expect(t.steps.find((s) => s.name === "economics")!.status).toBe("done");
    expect(leftOut(t)).toEqual([["A2", "simulate_year failed: depth 1500 m is outside the doublet model"]]);
    expect(withoutLeftOut(answerText(t))).toMatch(/A4 \(gas reference\) at 63\.9 €\/MWh\.$/);
    expect(t.result!.alternative).toBe("A1");
    expect(turnTotals(t).toolErrors).toBe(1);
  });

  it("RUN_ERROR: an unexpected exception ends the turn in error, RUN_FINISHED keeps it", () => {
    const t = last(ask(emptyChat("e"), "Design ...", "run-error"));
    expect(t.status).toBe("error");
    expect(t.error).toEqual({ message: "KeyError: 'lcoc_eur_per_mwh'", code: "agent_error" });
    expect(t.steps.every((s) => s.status === "done")).toBe(true);
    expect(t.runs[0].summary!.behaviour).toBe("error");
  });

  it("model unavailable: a notice with the command that fixes it, not a crash", () => {
    const down = last(ask(emptyChat("o"), "Design ...", "model-down"));
    expect(down.status).toBe("done");
    expect(behaviour(down)).toBe("model_unavailable");
    expect(down.unavailable).toMatchObject({ model: "qwen3:1.7b", fix: "ollama serve" });
    expect(down.usage[0]).toMatchObject({ ok: false, prompt_tokens: 0 });
    expect(turnTotals(down).tokens).toBe(0);
    const missing = last(ask(emptyChat("m"), "Design ...", "model-missing"));
    expect(missing.unavailable).toMatchObject({ model: "qwen3:8b", fix: "ollama pull qwen3:8b" });
    expect(answerText(missing)).toContain("`ollama pull qwen3:8b`");
  });

  it("stop: the active step stops and late events don't revive the run", () => {
    const events = load("design");
    let chat = reduce(emptyChat("s"), { type: "send", turnId: "a", message: "Design ...", at: 0 });
    chat = replay(chat, events.slice(0, 8));
    expect(last(chat).steps.map((s) => s.status)).toEqual(["done", "done", "active"]);
    chat = reduce(chat, { type: "stopped" });
    expect(last(chat).status).toBe("stopped");
    expect(last(chat).steps[2].status).toBe("stopped");
    chat = replay(chat, events.slice(-1));
    expect(last(chat).status).toBe("stopped");
  });

  it("a network failure becomes an error on the turn", () => {
    let chat = reduce(emptyChat("n"), { type: "send", turnId: "a", message: "Design ...", at: 0 });
    chat = replay(chat, load("design").slice(0, 2));
    chat = reduce(chat, { type: "failed", message: "Failed to fetch", code: "network" });
    expect(last(chat)).toMatchObject({ status: "error", error: { code: "network" } });
    expect(last(chat).steps[0].status).toBe("error");
  });

  it("Dutch: asks in Dutch", () => {
    const t = last(ask(emptyChat("d"), "Ontwerp ...", "dutch"));
    expect(t.clarification!.intro).toMatch(/^Voordat ik ontwerp/);
    expect(t.status).toBe("waiting");
  });
});

describe("decisions, routing and reasoning (9ef2c02)", () => {
  it("decision: the shortfall and its card, then a multiple choice; the pick continues the turn", () => {
    let chat = ask(emptyChat("v-design"), "Design ...", "design");
    chat = ask(chat, "Cover 100% ... single 1 km doublet ...", "decision");
    let t = last(chat);
    expect(t.status).toBe("waiting");
    expect(t.clarification!.kind).toBe("decision");
    expect(t.clarificationRun).toBe(0);
    const q = t.clarification!.questions[0];
    expect(q.id).toBe("decision");
    expect(q.options).toHaveLength(4);
    expect(q.options![3]).toBe("Keep my limits and report the shortfall");
    expect(q.default).toMatch(/^A1, the 2\.5 km cascade/);
    expect(t.runs[0].outcome).toBe("interrupt");
    expect(t.runs[0].summary).toMatchObject({ behaviour: "report_infeasible", decided_by: { plan: "rules", reflect: "rules" } });
    expect(t.steps.find((s) => s.name === "reflect")!.meta).toMatchObject({ decided_by: "rules", try: ["allow", "deeper", "cascade"] });
    expect(t.cards.map((c) => [c.run, c.result.alternative, c.result.verified])).toEqual([[0, "D1", false]]);
    expect(runText(t, 0)).toMatch(/^No design meets 100% of the heat/);

    chat = reduce(chat, { type: "answer", answers: { decision: q.default! }, at: 1 });
    chat = replay(chat, load("decision-answer"));
    t = last(chat);
    expect(t.status).toBe("done");
    expect(t.runs).toHaveLength(2);
    expect(t.steps.slice(-2).map((s) => [s.label, s.run])).toEqual([
      ["Check the option you picked", 1],
      ["Write the answer", 1],
    ]);
    expect(t.cards.map((c) => [c.run, c.result.alternative, c.result.verified])).toEqual([
      [0, "D1", false],
      [1, "A1", true],
    ]);
    expect(runText(t, 1)).toMatch(/^You chose Deep doublet with absorption cascade\./);
    // The pick runs no model.
    expect(t.runs[1].summary!.llm_calls).toBe(0);
  });

  it("about and greeting: routed with no model call and no card", () => {
    const about = last(ask(emptyChat("a"), "Who are you?", "about"));
    expect(behaviour(about)).toBe("about");
    expect(turnTotals(about).llmCalls).toBe(0);
    expect(about.cards).toHaveLength(0);
    expect(answerText(about)).toMatch(/^I'm Dioscuri\./);
    const hello = last(ask(emptyChat("g"), "Hello!", "greeting"));
    expect(behaviour(hello)).toBe("greeting");
  });

  it("question: a lookup step with what it found, and the answer names its source", () => {
    const t = last(ask(emptyChat("q"), "What is the reservoir initial temperature?", "question"));
    expect(behaviour(t)).toBe("answer");
    const lookup = t.steps.find((s) => s.name === "lookup")!;
    expect(lookup).toMatchObject({ kind: "tool", code: "lookup(reservoir_temp)", status: "done" });
    expect(lookup.meta).toMatchObject({ found: ["reservoir_temp"], missing: [] });
    expect(answerText(t)).toContain("Source: the project's subsurface data (subsurface.json).");
    expect(t.cards).toHaveLength(0);
  });

  it("reasoning: the model plans and rewords, code checks the numbers, the template is kept", () => {
    const t = last(ask(emptyChat("r"), "Design ...", "reasoning-design"));
    const plan = t.steps.find((s) => s.name === "plan")!;
    expect(plan.kind).toBe("model");
    expect(plan.meta).toMatchObject({ decided_by: "model" });
    expect(plan.meta.steps as string[]).toHaveLength(3);
    expect(typeof plan.meta.reason).toBe("string");
    expect(stepModel(t, plan)).toBe("qwen3.5:9b");
    const write = t.steps.find((s) => s.name === "write")!;
    expect(write).toMatchObject({ kind: "model", label: "Write the answer" });
    expect(t.steps[t.steps.length - 1].label).toBe("Check the answer's numbers");
    const s = t.runs[0].summary!;
    expect(s).toMatchObject({ reasoning: true, decided_by: { plan: "model", write: "model" }, calls: ["intake: qwen3:1.7b", "plan: qwen3.5:9b", "write: qwen3.5:9b"] });
    expect(s.draft).toMatch(/^A1 covers 100% of the heat/);
    expect(answerText(t)).not.toBe(s.draft);
    expect(turnTotals(t)).toMatchObject({ llmCalls: 3, tokens: 1698 + 432 });
  });

  it("reasoning model missing: an amber fallback notice, rules decide, the run goes on", () => {
    const t = last(ask(emptyChat("m"), "Design ...", "reasoning-missing"));
    expect(t.status).toBe("done");
    expect(t.unavailable).toMatchObject({ model: "qwen3.5:27b", fix: "ollama pull qwen3.5:27b", fallback: "rules", run: 0 });
    const plan = t.steps.find((s) => s.name === "plan")!;
    expect(plan.kind).toBe("model");
    expect(plan.meta).toMatchObject({ decided_by: "rules", note: "the reasoning model isn't available; rules decided" });
    expect(t.cards[0].result.alternative).toBe("A1");
    expect(behaviour(t)).toBe("design");
  });

  it("corrections: code takes out what the brief rules out, and says so", () => {
    const t = last(ask(emptyChat("c"), "Design ... no heat pumps.", "rules-correction"));
    const plan = t.steps.find((s) => s.name === "plan")!;
    expect(plan.meta.corrections).toEqual(["left out A2: it needs heat pumps, which you ruled out"]);
    expect(t.runs[0].summary!.plan).toEqual(["A1", "A4"]);
  });

  it("reasoning decision: the model picks the fixes to try and recommends one", () => {
    let chat = ask(emptyChat("v-rdesign"), "Design ...", "reasoning-design");
    chat = ask(chat, "Cover 100% ...", "reasoning-decision");
    const t = last(chat);
    const reflect = t.steps.find((s) => s.name === "reflect")!;
    expect(reflect.meta).toMatchObject({ decided_by: "model", try: ["deeper", "allow"] });
    expect(t.runs[0].summary!.recommended).toBe("deeper");
    expect(t.clarification!.questions[0].default).toMatch(/^A 2\.2 km doublet/);
    expect(t.status).toBe("waiting");
  });

  it("a send carries the chat's reasoning mode onto the turn", () => {
    const chat = reduce(emptyChat("x"), { type: "send", turnId: "a", message: "hi", at: 0, reasoning: true });
    expect(chat.turns[0].reasoning).toBe(true);
  });
});

describe("model generation, documents and attachments (2246791)", () => {
  const answer = (chat: ChatState, answers: Record<string, string>, fixture: string) =>
    replay(reduce(chat, { type: "answer", answers, at: 1 }), load(fixture));

  it("a missing component model: offer, write and test, approve, then use it", () => {
    let chat = ask(emptyChat("g1"), "Design ...", "design");
    chat = ask(chat, "Could an adsorption chiller ... cover part of the cooling?", "model-offer");
    let t = last(chat);
    expect(t.status).toBe("waiting");
    expect(behaviour(t)).toBe("offer_model");
    expect(asksOf(t).map((a) => a.value.kind)).toEqual(["offer"]);
    const offer = t.clarification!.details as { component: string; inputs: string[]; outputs: string[]; physics: string[] };
    expect(offer.component).toBe("adsorption_chiller");
    expect(offer.inputs).toContain("drive_temp_c [°C]");
    expect(offer.physics.length).toBeGreaterThan(3);
    expect(t.clarification!.questions[0]).toMatchObject({ id: "generate", options: ["Yes, write and test the model", "No, answer without it"] });

    chat = answer(chat, { generate: "Yes, write and test the model" }, "model-attempts");
    t = last(chat);
    expect(t.status).toBe("waiting");
    expect(behaviour(t)).toBe("approve_model");
    const gen = t.steps.find((s) => s.name === "modelgen-1")!;
    expect(gen).toMatchObject({ kind: "model", status: "done", run: 1 });
    expect(gen.meta).toMatchObject({ passed: true, problems: [] });
    expect(t.attempts).toHaveLength(1);
    expect(t.generation).toMatchObject({ component: "adsorption_chiller", model: "qwen3.5:4b", passed: true });
    expect(t.generation!.table).toHaveLength(14);
    expect(t.generation!.code).toContain("def ");
    // Two questions in one turn, each after the run that asked it, each with its own answers.
    const asks = asksOf(t);
    expect(asks.map((a) => [a.value.kind, a.run])).toEqual([["offer", 0], ["approval", 1]]);
    expect(asks[0].answers).toEqual({ generate: "Yes, write and test the model" });
    expect(asks[1].value.questions[0].options).toEqual(["Approve and use it", "Reject it"]);

    chat = answer(chat, { approval: "Approve and use it" }, "model-used");
    t = last(chat);
    expect(t.status).toBe("done");
    // Saving and running the approved model are real steps, each with its tool call.
    const tail = t.steps.slice(-3).map((s) => [s.name, s.label, s.status, s.run, s.tools.map((c) => c.name)]);
    expect(tail).toEqual([
      ["register", "Save the approved model", "done", 2, ["register_model"]],
      ["use_model", "Run the adsorption chiller model at this design's conditions", "done", 2, ["evaluate_adsorption_chiller"]],
      ["report", "Write the answer", "done", 2, []],
    ]);
    expect(t.steps.find((s) => s.name === "register")!.meta).toMatchObject({ saved: true });
    expect(t.steps.find((s) => s.name === "use_model")!.meta).toMatchObject({ passed: true, cases: 2 });
    const result = runResults(t, 2)[0];
    expect(result).toMatchObject({ component: "adsorption_chiller", title: "Adsorption chiller", warnings: [] });
    expect(result.cases).toHaveLength(2);
    expect(result.units).toMatchObject({ drive_temp_c: "°C", cold_mw: "MW", cop: "-" });
    expect(splitSources(runText(t, 2)).sources).toEqual(["the generated model, run in the sandbox (not a GEMINI model)"]);
    expect(asksOf(t)[1].answers).toEqual({ approval: "Approve and use it" });
    // The offer and the approval name the same generation.
    expect(asksOf(t)[0].value.generation_id).toBe(asksOf(t)[1].value.generation_id);
    expect(runText(t, 1)).toMatch(/^I wrote an adsorption chiller model with qwen3\.5:4b in 1 attempt\(s\) \(1,776 tokens\)/);
  });

  it("self-correction: a failed attempt ticks off red with its problems, the next one passes", () => {
    let chat = ask(emptyChat("g4"), "Could aquifer thermal energy storage ...?", "ates-offer");
    chat = answer(chat, { generate: "Yes, write and test the model" }, "ates-attempts");
    const t = last(chat);
    const [a1, a2] = ["modelgen-1", "modelgen-2"].map((n) => t.steps.find((s) => s.name === n)!);
    expect(a1.status).toBe("error");
    expect(a1.meta.passed).toBe(false);
    expect((a1.meta.problems as string[])[0]).toMatch(/NameError: name 'math' is not defined/);
    expect(a2.status).toBe("done");
    expect(t.attempts!.map((a) => a.passed)).toEqual([false, true]);
    expect(t.generation!.attempts).toHaveLength(2);
    expect(t.status).toBe("waiting");
  });

  it("rejecting or declining ends the turn with no model saved", () => {
    let chat = ask(emptyChat("g2"), "Could an adsorption chiller ...?", "model-offer-2");
    chat = answer(chat, { generate: "Yes, write and test the model" }, "model-attempts-2");
    chat = answer(chat, { approval: "Reject it" }, "model-rejected");
    expect(runText(last(chat), 2)).toBe("Rejected: the model was not saved.");
    expect(last(chat).status).toBe("done");
    let d = ask(emptyChat("g3"), "Could aquifer thermal energy storage ...?", "ates-offer-declined");
    d = answer(d, { generate: "No, answer without it" }, "model-declined");
    expect(runText(last(d), 1)).toMatch(/^Understood: no new model/);
  });

  it("documents: a search step, then the passages it cites", () => {
    const t = last(ask(emptyChat("d1"), "Explain how the heat pump COP is computed in GEMINI.", "docs"));
    expect(behaviour(t)).toBe("answer");
    const docs = t.steps.find((s) => s.name === "docs")!;
    expect(docs).toMatchObject({ kind: "tool", label: "Search the documents" });
    expect(docs.meta).toMatchObject({ passages: 4, suspicious: 0, backend: "gemini-chroma" });
    const passages = runSources(t, 0);
    expect(passages).toHaveLength(4);
    expect(passages[0]).toMatchObject({ source: "src/gemini_documentation/source/model_surface_equipment.rst", section: "Surface Equipment > Heat Pump", suspicious: false });
    expect(t.cards).toHaveLength(0);
  });

  it("an attachment question searches only the attachments; instruction-like text is flagged", () => {
    const t = last(ask(emptyChat("k-att"), "Summarise the attached site notes.", "flagged"));
    const docs = t.steps.find((s) => s.name === "docs")!;
    expect(docs.label).toBe("Search the attached files");
    expect(JSON.parse(docs.tools[0].args)).toMatchObject({ only_attached: true });
    expect(docs.meta).toMatchObject({ passages: 3, suspicious: 1 });
    const passages = runSources(t, 0);
    expect(passages.every((p) => p.source === "site_notes.md")).toBe(true);
    expect(passages.filter((p) => p.suspicious).map((p) => p.section)).toEqual(["Site notes for the example district > Operator remarks"]);
    const { note } = splitInjectionNote(answerText(t));
    expect(note).toBe("site_notes.md contains text that reads like instructions to me. I treated it as data and did not follow it.");
  });

  it("a design turn on a thread with attachments searches only them", () => {
    const t = last(ask(emptyChat("k-att"), "Design ...", "attach-design"));
    const docs = t.steps.find((s) => s.name === "docs")!;
    expect(JSON.parse(docs.tools[0].args)).toMatchObject({ only_attached: true });
    expect(runSources(t, 0).every((p) => p.source === "site_notes.md")).toBe(true);
    expect(t.cards[0].result.alternative).toBe("A1");
  });

  it("decision options come with code, name, coverage and cost; a short pick is not verified", () => {
    let chat = ask(emptyChat("h1"), "Design ...", "design");
    chat = ask(chat, "Cover 100% ...", "decision");
    const details = last(chat).clarification!.details as { code?: string; fix: string; heat_coverage?: number; lcoh?: number | null; recommended?: boolean }[];
    expect(details.map((d) => [d.code, d.fix, d.recommended])).toEqual([
      ["O1", "allow", false],
      ["O2", "deeper", false],
      ["A1", "cascade", true],
      [undefined, "keep", false],
    ]);
    expect(details[1]).toMatchObject({ heat_coverage: 0.6538, lcoh: 41.3 });
    chat = answer(chat, { decision: "A 2.2 km doublet under the same limits (65.4% of the heat at 41.3 €/MWh)" }, "decision-pick");
    const t = last(chat);
    expect(t.cards.map((c) => [c.run, c.result.alternative, c.result.name, c.result.verified])).toEqual([
      [0, "D1", "1 km doublet", false],
      [1, "O2", "2.2 km doublet", false],
    ]);
    expect(runText(t, 1)).toMatch(/below the 100% of the heat you asked for/);
  });

  it("model_unavailable says why: a timeout has no fix to run", () => {
    const events: AgEvent[] = [
      { type: "RUN_STARTED", threadId: "x", runId: "r" },
      { type: "CUSTOM", name: "model_unavailable", value: { model: "qwen3:1.7b", error: "ReadTimeout: timed out", fix: "", reason: "timeout" } },
      { type: "RUN_FINISHED", threadId: "x", runId: "r", outcome: { type: "success" }, result: { behaviour: "model_unavailable" } },
    ];
    const t = last(replay(reduce(emptyChat("x"), { type: "send", turnId: "a", message: "hi", at: 0 }), events));
    expect(t.unavailable).toMatchObject({ reason: "timeout", fix: "", run: 0 });
  });
});

// Hand-written streams for the answerer contract (see scenes.ts); re-recorded from the backend later.
describe("the answerer: a model writes every reply, code checks it", () => {
  const answer = (chat: ChatState, answers: Record<string, string>, fixture: string) =>
    replay(reduce(chat, { type: "answer", answers, at: 1 }), load(fixture));

  it("advantages: an answer step with what it understood; the answer event before the text is claimed by it", () => {
    const t = last(ask(emptyChat("w1"), "What does Dioscuri do better than a spreadsheet?", "answer-advantages"));
    expect(t.status).toBe("done");
    expect(behaviour(t)).toBe("answer");
    expect(t.steps.map((s) => [s.name, s.kind, s.label])).toEqual([
      ["intake", "model", "Read the request"],
      ["answer", "model", "Write the answer"],
    ]);
    expect(t.steps[1].meta).toMatchObject({ decided_by: "model", model: "qwen3.5:9b", device: "gpu", kind: "answer", scope: "project" });
    expect(t.steps[1].meta.understood).toBe("You want to know what Dioscuri does better than a spreadsheet.");
    expect(stepModel(t, t.steps[1])).toBe("qwen3.5:9b");
    const reply = runReply(t, 0)!;
    expect(reply).toMatchObject({ kind: "answer", scope: "project", used: ["self"], fallback: false });
    // Sent before its text: the message that follows takes it.
    expect(t.replies).toHaveLength(1);
    expect(t.replies![0].message).toBe(t.messages[0].id);
    expect(messageReply(t, t.messages[0].id)).toBe(reply);
    expect(replyChips(reply)).toEqual([]);
    expect(answerText(t)).toMatch(/^A spreadsheet holds the numbers you type in/);
    expect(t.suggestions).toHaveLength(3);
    expect(turnTotals(t)).toMatchObject({ llmCalls: 2, tokens: 884 + 2354 });
  });

  it("general background: the answer event and the cited sources arrive after the text, on the same run", () => {
    const t = last(ask(emptyChat("w2"), "What is geothermal energy?", "answer-general"));
    const docs = t.steps.find((s) => s.name === "docs")!;
    expect(docs.meta).toMatchObject({ passages: 3, backend: "gemini-chroma" });
    // Only the passage the answer cited, though the search found three.
    const passages = runSources(t, 0);
    expect(passages.map((p) => p.source)).toEqual(["src/gemini_documentation/source/glossary.rst"]);
    expect(t.replies![0].message).toBe(t.messages[0].id);
    expect(runReply(t, 0)).toMatchObject({ scope: "general", used: ["doc1"] });
    expect(replyChips(runReply(t, 0))).toEqual(["general"]);
    expect(t.suggestions).toEqual([
      "How deep would the wells be for this district?",
      "Can geothermal heat also cool buildings?",
      "Design heating and cooling for this district",
    ]);
  });

  it("nonsense and out of scope: model-written replies with their chips", () => {
    const n = last(ask(emptyChat("w3"), "asdkjh qwe zxc", "nonsense"));
    expect(behaviour(n)).toBe("nonsense");
    expect(n.status).toBe("done");
    expect(replyChips(runReply(n, 0))).toEqual(["nonsense"]);
    expect(answerText(n)).toMatch(/^I couldn't read that as a question/);
    const o = last(ask(emptyChat("w4"), "What will the weather be in Paris tomorrow?", "out-of-scope"));
    expect(behaviour(o)).toBe("refuse");
    // The keyword screen read it; the answerer still wrote the reply with a model.
    expect(screened(o, 0)).toBe(true);
    expect(o.steps.find((s) => s.name === "answer")!.meta).toMatchObject({ decided_by: "model", kind: "out_of_scope", scope: "out" });
    expect(turnTotals(o).llmCalls).toBe(1);
    expect(replyChips(runReply(o, 0))).toEqual(["out_of_scope"]);
    expect(o.replies![0].message).toBe(o.messages[0].id);
  });

  it("choice: the model offers readings, a pick resumes the turn with the picked request", () => {
    let chat = ask(emptyChat("w5"), "How do I install it?", "choice");
    let t = last(chat);
    expect(t.status).toBe("waiting");
    expect(t.runs[0].outcome).toBe("interrupt");
    expect(t.runs[0].summary).toMatchObject({ behaviour: "clarify", asked: ["choice"] });
    expect(t.clarification).toMatchObject({ kind: "choice", intro: "Do you mean how to use me, or how to install GEMINI?" });
    const q = t.clarification!.questions[0];
    expect(q).toMatchObject({ id: "choice", default: null, options: ["Show me how to use Dioscuri", "Explain how to install GEMINI"] });
    // The intro is the card's title, not an answer; the reply's meta says it asks back.
    expect(answerText(t)).toBe("");
    expect(runReply(t, 0)).toMatchObject({ kind: "clarify" });
    expect(replyChips(runReply(t, 0))).toEqual([]);
    expect(t.steps.every((s) => s.status === "done")).toBe(true);

    chat = answer(chat, { choice: "Explain how to install GEMINI" }, "choice-answer");
    t = last(chat);
    expect(chat.turns).toHaveLength(1);
    expect(t.status).toBe("done");
    expect(t.runs.map((r) => r.outcome)).toEqual(["interrupt", "success"]);
    expect(asksOf(t)[0].answers).toEqual({ choice: "Explain how to install GEMINI" });
    expect(t.steps.map((s) => [s.name, s.run])).toEqual([
      ["intake", 0],
      ["answer", 0],
      ["docs", 1],
      ["answer", 1],
    ]);
    expect(runText(t, 1)).toMatch(/^GEMINI's quick start needs Docker Desktop/);
    // The sources came after run 1's text and belong to run 1 only.
    expect(runSources(t, 0)).toEqual([]);
    expect(runSources(t, 1)).toHaveLength(2);
    expect(t.replies!.map((r) => [r.run, r.value.kind])).toEqual([
      [0, "clarify"],
      [1, "answer"],
    ]);
    expect(runReply(t, 1)).toMatchObject({ used: ["doc1", "doc2"] });
  });

  it("choice: typing a new message instead starts a new turn and drops the choice", () => {
    const chat = reduce(ask(emptyChat("w6"), "How do I install it?", "choice"), { type: "send", turnId: "n", message: "What can you do?", at: 2 });
    expect(chat.turns[0]).toMatchObject({ status: "done", skipped: true });
    expect(asksOf(chat.turns[0])[0]).toMatchObject({ skipped: true });
    expect(chat.turns[1].status).toBe("running");
  });

  it("reasoning: the answer step's steps and the code's correction", () => {
    let chat = ask(emptyChat("w7"), "Design ...", "design");
    chat = ask(chat, "Why is A1 cheaper than A2?", "reasoning-answer");
    const t = last(chat);
    const step = t.steps.find((s) => s.name === "answer")!;
    expect(step.meta.steps as string[]).toHaveLength(3);
    expect(step.meta.corrections).toEqual(["removed a sentence with an unsourced number (17)"]);
    expect(runReply(t, 0)).toMatchObject({ corrections: ["removed a sentence with an unsourced number (17)"], used: ["A1", "A2", "A4"] });
    expect(t.runs[0].summary).toMatchObject({ reasoning: true, decided_by: { answer: "model" } });
    expect(answerText(t)).toContain("41 €/MWh and A2 at 65.5 €/MWh");
  });

  it("fallback: the checked template, decided by rules, with the reason", () => {
    let chat = ask(emptyChat("w8"), "Design ...", "design");
    chat = ask(chat, "Explain the summer cascade", "answer-fallback");
    const t = last(chat);
    const step = t.steps.find((s) => s.name === "answer")!;
    expect(step.meta).toMatchObject({ decided_by: "rules", note: "the model's text failed the number checks twice" });
    expect(runReply(t, 0)).toMatchObject({ fallback: true });
    expect(replyChips(runReply(t, 0))).toEqual(["fallback"]);
    expect(t.usage.filter((u) => u.purpose === "answer")).toHaveLength(2);
  });

  it("an answer event pairs with the right message: before it, right after it, or with none", () => {
    const meta = (kind: string) => ({ type: "CUSTOM" as const, name: "answer", value: { kind, scope: "project" } });
    const msg = (id: string, text: string): AgEvent[] => [
      { type: "TEXT_MESSAGE_START", messageId: id },
      { type: "TEXT_MESSAGE_CONTENT", messageId: id, delta: text },
      { type: "TEXT_MESSAGE_END", messageId: id },
    ];
    const step = (name: string): AgEvent[] => [
      { type: "STEP_STARTED", stepName: name, metadata: { label: name, kind: "model" } },
      { type: "STEP_FINISHED", stepName: name, metadata: {} },
    ];
    const events: AgEvent[] = [
      { type: "RUN_STARTED", threadId: "x", runId: "r" },
      ...msg("m1", "A template line."),
      ...step("answer"),
      // Before its text: m1 came before the answer step, so it isn't m1's.
      meta("answer"),
      ...msg("m2", "The model's reply."),
      ...msg("m3", "Another reply."),
      // Right after its text.
      meta("nonsense"),
      { type: "RUN_FINISHED", threadId: "x", runId: "r", outcome: { type: "success" } },
    ];
    const t = last(replay(reduce(emptyChat("x"), { type: "send", turnId: "a", message: "hi", at: 0 }), events));
    expect(t.replies!.map((r) => [r.message, r.value.kind])).toEqual([
      ["m2", "answer"],
      ["m3", "nonsense"],
    ]);
    expect(messageReply(t, "m1")).toBeUndefined();
    expect(runReply(t, 0)!.kind).toBe("nonsense");
  });

  it("late sources: each run keeps its own list, and a later list of the same run replaces the earlier one", () => {
    const passage = (source: string) => ({ source, section: "s", text: "t" });
    const src = (...names: string[]): AgEvent => ({ type: "CUSTOM", name: "sources", value: names.map(passage) });
    const run = (id: string, text: string, before: AgEvent[], after: AgEvent[], interrupt = false): AgEvent[] => [
      { type: "RUN_STARTED", threadId: "x", runId: id },
      ...before,
      { type: "TEXT_MESSAGE_START", messageId: `${id}-m` },
      { type: "TEXT_MESSAGE_CONTENT", messageId: `${id}-m`, delta: text },
      { type: "TEXT_MESSAGE_END", messageId: `${id}-m` },
      ...after,
      { type: "RUN_FINISHED", threadId: "x", runId: id, outcome: interrupt ? { type: "interrupt" } : { type: "success" } },
    ];
    let chat = reduce(emptyChat("x"), { type: "send", turnId: "a", message: "hi", at: 0 });
    // Run 0: a search step's list before the text, then the cited one after it.
    chat = replay(chat, run("r0", "Which one?", [src("a.md", "b.md", "c.md")], [src("b.md")], true));
    chat = reduce(chat, { type: "answer", answers: { choice: "x" }, at: 1 });
    // Run 1: only the cited list, after the text and the suggestions.
    chat = replay(chat, run("r1", "Here.", [], [{ type: "CUSTOM", name: "suggestions", value: [] }, src("d.md")]));
    const t = last(chat);
    expect(runSources(t, 0).map((p) => p.source)).toEqual(["b.md"]);
    expect(runSources(t, 1).map((p) => p.source)).toEqual(["d.md"]);
  });
});

describe("files: the agent opens a file (hand-written, the 28 Oct contract)", () => {
  const table = last(ask(emptyChat("f-table"), "Give me the table of heating_profile.csv", "file-table"));

  it("ticks off the read_file step and keeps the file per run", () => {
    expect(table.status).toBe("done");
    expect(table.steps.map((s) => s.name)).toEqual(["intake", "read_file", "answer"]);
    const step = table.steps[1];
    expect(step).toMatchObject({ kind: "tool", status: "done", label: "Open heating_profile.csv" });
    expect(step.tools.map((c) => [c.name, c.done, c.error])).toEqual([["read_file", true, undefined]]);
    const files = runFiles(table, 0);
    expect(files.map((f) => [f.name, f.kind, f.origin, f.show])).toEqual([["heating_profile.csv", "table", "project", "table"]]);
    expect(files[0].table).toMatchObject({ total_rows: 365, truncated: true });
    expect(files[0].table!.rows).toHaveLength(20);
    expect(files[0].table!.columns.map((c) => [c.name, c.type, c.unit])).toEqual([
      ["date", "date", ""],
      ["heat_demand_mw", "number", "MW"],
      ["hot_water_mw", "number", "MW"],
      ["t_outdoor_c", "number", "°C"],
    ]);
    expect(files[0].totals?.[0]).toMatchObject({ column: "heat_demand_mw", value: 61.8, unit: "GWh" });
    expect(files[0].chart?.x_values).toHaveLength(61);
    expect(files[0].chart?.series.every((s) => s.values.length === 61)).toBe(true);
  });

  it("keeps the new source fields: kind and the file to open", () => {
    expect(runSources(table, 0)).toEqual([expect.objectContaining({ kind: "data", file: "heating_profile.csv" })]);
    expect(runText(table, 0)).toMatch(/^Here is \*\*heating_profile\.csv\*\*: .*\[\^1\]/);
  });

  it("replaces a file sent again in the same run, and keeps another run's", () => {
    const view = runFiles(table, 0)[0];
    const again = { type: "event" as const, event: { type: "CUSTOM" as const, name: "file", value: { ...view, show: "chart" } } };
    let chat = reduce(ask(emptyChat("f"), "x", "file-table"), again);
    expect(runFiles(last(chat), 0).map((f) => f.show)).toEqual(["chart"]);
    chat = reduce(chat, { type: "event", event: { type: "RUN_STARTED", threadId: "f", runId: "r2" } });
    chat = reduce(chat, again);
    expect(runFiles(last(chat), 1)).toHaveLength(1);
    expect(last(chat).files).toHaveLength(2);
    // Not a file view: ignored.
    expect(reduce(chat, { type: "event", event: { type: "CUSTOM", name: "file", value: "heating_profile.csv" } })).toBe(chat);
  });

  it("opens a chart on its chart, and an upload as your image", () => {
    const chart = runFiles(last(ask(emptyChat("f-chart"), "Plot it", "file-chart")), 0)[0];
    expect(chart).toMatchObject({ name: "cooling_profile.csv", show: "chart" });
    expect(chart.chart?.series.map((s) => s.unit)).toEqual(["MW", "°C"]);
    const image = last(ask(emptyChat("f-image"), "Show it", "file-image"));
    expect(runFiles(image, 0)[0]).toMatchObject({ kind: "image", origin: "attachment", show: "image", image: { url: "/favicon.svg" } });
    expect(runSources(image, 0)).toEqual([]);
  });

  it("keeps a passage's figures", () => {
    const md = last(ask(emptyChat("w-md"), "Compare", "answer-markdown"));
    const passages = runSources(md, 0);
    expect(passages.map((p) => p.kind)).toEqual(["doc", "note"]);
    expect(passages[0].images).toEqual([{ url: "/favicon.svg", caption: expect.stringContaining("Heat pump") }]);
    expect(passages[1].file).toBe("cooling_design.md");
  });
});

describe("design charts: monthly energy and the designs compared (recorded 28 Oct)", () => {
  const design = ask(emptyChat("c1"), "Design ...", "design-charts");
  const t = last(design);
  const sum = (list: number[]) => list.reduce((a, v) => a + v, 0);

  it("keeps the card's monthly energy, which adds up to the yearly split", () => {
    expect(t.status).toBe("done");
    const card = t.cards[0].result;
    const m = card.monthly_gwh!;
    for (const list of [m.heat.demand, m.heat.geo, m.heat.hp, m.heat.boiler, m.cool.demand, m.cool.abs, m.cool.chill]) expect(list).toHaveLength(12);
    expect(sum(m.heat.geo)).toBeCloseTo(card.heat_split_gwh.geo, 1);
    expect(sum(m.cool.chill)).toBeCloseTo(card.cool_split_gwh.chill, 1);
    expect(m.cool.demand[0]).toBe(0);
  });

  it("keeps the comparison on its run, the chosen design first and the gas reference marked", () => {
    const c = runComparison(t, 0)!;
    expect(c.chosen).toBe("A1");
    expect(c.designs.map((d) => [d.code, d.reference, d.verified])).toEqual([
      ["A1", false, true],
      ["A4", true, true],
      ["A2", false, true],
    ]);
    expect(c.designs[0]).toMatchObject({ lcoh: 41, lcoc: 58, co2_saving_pct: 82.2, capex_meur: 25.1, source: "mock" });
    expect(t.comparisons).toHaveLength(1);
  });

  it("what-if: the colder reservoir's design leads, the design as expected is kept for reference", () => {
    const chat = ask(design, "What happens ...", "whatif-charts");
    const w = last(chat);
    const c = runComparison(w, 0)!;
    expect(c.designs.map((d) => [d.code, d.reservoir_delta_c, d.lcoh])).toEqual([
      ["A1", -10, 47.2],
      ["A4", 0, 63.9],
      ["A2", 0, 65.5],
      ["A1", 0, 41],
    ]);
    expect(w.cards[0].result.cool_split_gwh).toEqual({ abs: 0, chill: 13.67 });
    expect(sum(w.cards[0].result.monthly_gwh!.cool.abs)).toBe(0);
    // Each turn keeps its own.
    expect(runComparison(chat.turns[0], 0)!.designs).toHaveLength(3);
  });

  it("a comparison sent again in a run replaces it; fewer than two designs or a broken value show none", () => {
    const value = runComparison(t, 0)!;
    const send = (chat: ChatState, v: unknown) => reduce(chat, { type: "event", event: { type: "CUSTOM", name: "comparison", value: v } });
    const two: Comparison = { ...value, designs: value.designs.slice(0, 2) };
    let chat = send(design, two);
    expect(last(chat).comparisons).toHaveLength(1);
    expect(runComparison(last(chat), 0)!.designs).toHaveLength(2);
    chat = send(chat, { chosen: "A1", designs: value.designs.slice(0, 1) });
    expect(runComparison(last(chat), 0)).toBeUndefined();
    expect(send(chat, null)).toBe(chat);
    expect(send(chat, { chosen: "A1" })).toBe(chat);
  });

  it("older streams have no monthly energy and no comparison", () => {
    const old = last(ask(emptyChat("d"), "Design ...", "design"));
    expect(old.cards[0].result.monthly_gwh).toBeUndefined();
    expect(runComparison(old, 0)).toBeUndefined();
    expect(old.comparisons).toBeUndefined();
  });
});

describe("the claim checker (hand-written, the 28 Oct contract)", () => {
  const t = last(ask(emptyChat("w-claims"), "What is geothermal energy?", "claims-removed"));

  it("checks the claims after the answer and takes the unsupported one out", () => {
    expect(t.status).toBe("done");
    expect(t.steps.map((s) => s.name)).toEqual(["intake", "docs", "answer", "claims"]);
    expect(t.steps[3]).toMatchObject({ kind: "model", label: "Check the claims", status: "done", seconds: 0.905 });
    expect(stepModel(t, t.steps[3])).toBe("qwen3:1.7b");
    const c = runClaims(t, 0)!;
    expect(c).toMatchObject({ skipped: false, checked: 5, supported: 3, general: 1, removed: 1 });
    expect(c.sentences).toEqual([expect.stringMatching(/^Most doublets in the Netherlands/)]);
    expect(c.step?.key).toBe(t.steps[3].key);
    expect(runText(t, 0)).not.toMatch(/Most doublets/);
  });

  it("the answer event still pairs with its text, and carries the claims too", () => {
    const meta = messageReply(t, t.messages[0].id)!;
    expect(meta.claims).toEqual({ checked: 5, removed: [runClaims(t, 0)!.sentences[0]] });
    expect(replyChips(meta)).toEqual(["general"]);
    expect(turnTotals(t).llmCalls).toBe(3);
  });

  it("skipped says why; the answer event alone still counts; no check, no claims", () => {
    const run = (finished: Record<string, unknown> | null, answer: Record<string, unknown>): AgEvent[] => [
      { type: "RUN_STARTED", threadId: "x", runId: "r" },
      ...(finished
        ? ([
            { type: "STEP_STARTED", stepName: "claims", metadata: { label: "Check the claims", kind: "model" } },
            { type: "STEP_FINISHED", stepName: "claims", metadata: finished },
          ] as AgEvent[])
        : []),
      { type: "TEXT_MESSAGE_START", messageId: "m" },
      { type: "TEXT_MESSAGE_CONTENT", messageId: "m", delta: "Hi." },
      { type: "CUSTOM", name: "answer", value: answer },
      { type: "RUN_FINISHED", threadId: "x", runId: "r" },
    ];
    const play = (events: AgEvent[]) => last(replay(reduce(emptyChat("x"), { type: "send", turnId: "a", message: "hi", at: 0 }), events));
    const skipped = play(run({ seconds: 0, decided_by: "skipped", checked: 0, supported: 0, general: 0, removed: 0, note: "no model for the check" }, { kind: "answer" }));
    expect(runClaims(skipped, 0)).toMatchObject({ skipped: true, removed: 0, note: "no model for the check" });
    const eventOnly = play(run(null, { kind: "answer", claims: { checked: 4, removed: ["A.", "B."] } }));
    expect(runClaims(eventOnly, 0)).toMatchObject({ step: undefined, checked: 4, removed: 2, sentences: ["A.", "B."] });
    expect(runClaims(play(run(null, { kind: "answer" })), 0)).toBeUndefined();
    expect(runClaims(last(ask(emptyChat("g"), "What is geothermal energy?", "answer-general")), 0)).toBeUndefined();
  });
});

describe("attachments go with the message they were sent with", () => {
  const files = [
    { name: "notes.md", kind: "text" as const, chunks: 3 },
    { name: "map.png", kind: "image" as const },
  ];

  it("the send action keeps them on its turn only; later turns don't repeat them", () => {
    let chat = reduce(emptyChat("a"), { type: "send", turnId: "t0", message: "Summarise the notes", at: 0, attachments: files });
    chat = reduce(chat, { type: "send", turnId: "t1", message: "And the costs?", at: 1 });
    expect(chat.turns[0].attachments).toEqual(files);
    // A message without files has no field at all, as in chats saved before this existed.
    expect("attachments" in chat.turns[1]).toBe(false);
    expect("attachments" in reduce(emptyChat("b"), { type: "send", turnId: "t", message: "hi", at: 0, attachments: [] }).turns[0]).toBe(false);
  });

  it("settles a turn's files by turn id once their uploads finish", () => {
    let chat = reduce(emptyChat("a"), { type: "send", turnId: "t0", message: "Read the brief", at: 0, attachments: [{ name: "brief.pdf", kind: "text", uploading: true }] });
    chat = reduce(chat, { type: "attachments", turnId: "t0", attachments: [{ name: "brief.pdf", kind: "text", chunks: 12 }] });
    expect(chat.turns[0].attachments).toEqual([{ name: "brief.pdf", kind: "text", chunks: 12 }]);
    // Every upload failed: the message shows no files (they go back to the composer).
    chat = reduce(chat, { type: "attachments", turnId: "t0", attachments: [] });
    expect("attachments" in chat.turns[0]).toBe(false);
    expect(reduce(chat, { type: "attachments", turnId: "nope", attachments: [] })).toBe(chat);
  });

  it("passes a compact what-if card through with the design it is set against", () => {
    const base = { alternative: "2D-HP-AB@2500", name: "Cascade", verified: true, checks: { passed: 17, total: 17 }, kpis: [{ id: "lcoh", label: "Cost of heat", value: 47.2, unit: "€/MWh" }], heat_split_gwh: {}, cool_split_gwh: {}, sizes_mw: {} };
    const card = { ...base, view: "compact", against: base, kpis: [{ id: "lcoh", label: "Cost of heat", value: 49.1, unit: "€/MWh" }] };
    const chat = replay(reduce(emptyChat("w"), { type: "send", turnId: "t", message: "What if the reservoir is 10 °C colder?", at: 0 }), [
      { type: "RUN_STARTED", threadId: "w", runId: "r" },
      { type: "CUSTOM", name: "result", value: card },
      { type: "CUSTOM", name: "checks", value: [{ name: "coverage", passed: true, detail: "" }] },
      { type: "RUN_FINISHED", threadId: "w", runId: "r" },
    ]);
    expect(last(chat).cards[0].result).toMatchObject({ view: "compact", against: { alternative: "2D-HP-AB@2500" } });
    expect(last(chat).cards[0].checks).toHaveLength(1);
  });
});

describe("the inputs card and the challenge engine's streams (recorded 30-31 Oct, make_ui_fixtures.py)", () => {
  const RUN = "Run the design with these inputs";
  const asked = ask(emptyChat("t-confirm"), "Design a geothermal heating and cooling system for this district.", "confirm");
  const t = last(asked);

  it("reads the message, what it sets, gathers the inputs, and stops on the card", () => {
    expect(t.status).toBe("waiting");
    expect(t.steps.map((s) => [s.name, s.label])).toEqual([
      ["intake", "Read the request"],
      ["think", "Answer without reasoning"],
      ["parameters", "Read what the message asks: changes, failures, designs, steps"],
      ["inputs", "Gather the inputs to confirm"],
    ]);
    expect(t.steps.every((s) => s.status === "done")).toBe(true);
    expect(t.steps[2].meta).toMatchObject({ decided_by: "model", changes: {}, doublets: [], unsupported: [], dropped: [] });
    expect(t.steps[3].meta).toMatchObject({ rows: 18, assumed: 9 });
    expect(t.clarification).toMatchObject({ kind: "confirm", questions: [{ id: "confirm", options: [RUN, "Change an input first"] }] });
  });

  it("keeps the rows on the run and hides the Markdown table the card replaces", () => {
    const c = runConfirm(t, 0)!;
    expect(c.value.rows).toHaveLength(18);
    expect(c.value.rows[0]).toMatchObject({ group: "Demand", label: "Heat", value: "111.67 GWh a year, peak 30 MW on 2027-01-28", source: "GEMINI_Heating_Demand_Daily_2027.csv", kind: "data", changed: false });
    expect([...new Set(c.value.rows.map((r) => r.group))]).toEqual(["Demand", "Reservoir", "Brine and gas", "Caps", "Networks", "Plant options", "Maintenance", "Costs", "Your request"]);
    expect(c.value.kinds).toMatchObject({ assumed: "Dioscuri's assumption", asked: "your request" });
    expect(c.value.options).toEqual([RUN, "Change an input first"]);
    expect(c.message).toBe(t.messages[0].id);
    expect(t.messages[0].text).toMatch(/\| Input \| Value \| From \|/);
    expect(runText(t, 0)).toBe("");
  });

  it("without the card's event the table stays: a server that sends only the text", () => {
    const events = load("confirm").filter((e) => !(e.type === "CUSTOM" && e.name === "confirm_inputs"));
    const bare = last(replay(reduce(emptyChat("b"), { type: "send", turnId: "b", message: "x", at: 0 }), events));
    expect(runConfirm(bare, 0)).toBeUndefined();
    // The text is the clarification's intro, which the card shows as Markdown in its place.
    expect(bare.clarification!.intro).toMatch(/\| Heat \| 111\.67 GWh/);
    // A card's event without its question changes nothing either: the text is the answer.
    const alone = load("confirm").filter((e) => !(e.type === "CUSTOM" && e.name === "clarification"));
    const t2 = last(replay(reduce(emptyChat("c"), { type: "send", turnId: "c", message: "x", at: 0 }), alone));
    expect(runConfirm(t2, 0)).toBeUndefined();
    expect(runText(t2, 0)).toMatch(/^Before I run the design/);
  });

  it("Run continues the same turn: the search, the design and its card", () => {
    const answered = replay(reduce(asked, { type: "answer", answers: { confirm: RUN }, at: 1 }), load("confirm-run"));
    const done = last(answered);
    expect(answered.turns).toHaveLength(1);
    expect(done.status).toBe("done");
    expect(done.runs).toHaveLength(2);
    expect(asksOf(done)[0].answers).toEqual({ confirm: RUN });
    expect(done.steps.filter((s) => s.run === 1).map((s) => s.name)).toEqual(["plan", "doublet", "simulate", "verify", "improve", "rank", "gemini", "cooling", "answer", "claims", "report"]);
    expect(done.cards).toHaveLength(1);
    expect(done.cards[0]).toMatchObject({ run: 1, result: { alternative: "1D-HP-EC-N1-FC", design_id: "A1 · 1D-HP-EC-N1-FC", flags: ["N1", "FC"], dispatch: "equal" } });
    expect(runText(done, 1)).toMatch(/^I recommend \*\*1 doublet at 2,500 m/);
    expect(runText(done, 0)).toBe("");
  });

  it("a typed reply is a new message: the card is skipped and the next turn's confirm step says how it was read", () => {
    let chat = reduce(asked, { type: "send", turnId: "t1", message: "a 50 °C heating return", at: 2 });
    const card = asksOf(chat.turns[0])[0];
    expect(card.skipped).toBe(true);
    expect(chat.turns[0].status).toBe("done");
    expect(confirmReplyOf(chat.turns[1])).toBe("reading");
    const step = (decision?: string): AgEvent[] => [
      { type: "STEP_STARTED", stepName: "confirm", metadata: { label: "Read the reply to the inputs", kind: "model" } },
      ...(decision ? [{ type: "STEP_FINISHED", stepName: "confirm", metadata: { decision, model: "qwen3.5:9b", device: "gpu" } } as AgEvent] : []),
    ];
    chat = replay(chat, [{ type: "RUN_STARTED", threadId: "t-confirm", runId: "r2" }, ...step()]);
    expect(confirmReplyOf(last(chat))).toBe("reading");
    for (const d of ["run", "change", "reset", "other"]) {
      const next = replay(reduce(asked, { type: "send", turnId: "t1", message: "x", at: 2 }), [{ type: "RUN_STARTED", threadId: "t", runId: "r" }, ...step(d)]);
      expect(confirmReplyOf(last(next))).toBe(d);
    }
    // A change the next card refused (5 Nov): its notice says nothing changed.
    const cardWith = (notice: unknown): AgEvent => ({ type: "CUSTOM", name: "confirm_inputs", value: { rows: [], changed: [], options: [], kinds: {}, notice } });
    const refused = replay(reduce(asked, { type: "send", turnId: "t1", message: "x", at: 2 }), [{ type: "RUN_STARTED", threadId: "t", runId: "r" }, ...step("change"), cardWith({ kind: "refused", title: "Nothing changed", lines: [] })]);
    expect(confirmReplyOf(last(refused))).toBe("refused");
    const taken = replay(reduce(asked, { type: "send", turnId: "t1", message: "x", at: 2 }), [{ type: "RUN_STARTED", threadId: "t", runId: "r" }, ...step("change"), cardWith(null)]);
    expect(confirmReplyOf(last(taken))).toBe("change");
    // A next turn the agent didn't read as a reply (no confirm step), or none at all.
    const other = replay(reduce(asked, { type: "send", turnId: "t1", message: "x", at: 2 }), load("refuse"));
    expect(confirmReplyOf(last(other))).toBeUndefined();
    expect(confirmReplyOf(undefined)).toBeUndefined();
  });

  it("what-if: the change it read, the same plant under it, the search again, and a compact card against the design", () => {
    const w = last(ask(emptyChat("w"), "What happens to the design if we lower the heating return temperature to 50 °C?", "whatif-return"));
    expect(w.steps.map((s) => s.name)).toEqual(["intake", "think", "parameters", "needs", "plan", "simulate", "search", "answer", "claims", "report"]);
    expect(w.steps[2].meta.changes).toEqual({ heat_return_c: 50 });
    const search = w.steps.find((s) => s.name === "search")!;
    expect(search.label).toBe("Search the designs again under the change");
    expect(JSON.parse(search.tools[0].result!).result.chosen).toBe("1D-HP-EC-N1-FC-PV1.7");
    const card = w.cards[0].result;
    expect(card).toMatchObject({
      view: "compact",
      alternative: "1D-HP-EC-N1-FC",
      design_id: "W2 · 1D-HP-EC-N1-FC",
      change_label: "heating return temperature 50 °C",
      changes: { heat_return_c: 50 },
      flags: ["N1", "FC"],
      dispatch: "equal",
      against: { alternative: "1D-HP-EC-N1-FC", design_id: "A1 · 1D-HP-EC-N1-FC", change_label: "" },
    });
    expect(card.doublets).toHaveLength(1);
  });

  it("two doublets built differently: the doublets the message describes, the flags on the chosen code", () => {
    const b = last(ask(emptyChat("b"), "Design two doublets: the first with two injectors, the second with its own separator and filters.", "build-doublets"));
    expect(b.status).toBe("done");
    expect(b.steps.find((s) => s.name === "parameters")!.meta.doublets).toEqual([
      { depth_m: null, producer_open: "full", injector_open: "full", injectors: 2, max_flow_m3h: null, min_flow_m3h: null, train: 0 },
      { depth_m: null, producer_open: "full", injector_open: "full", injectors: 1, max_flow_m3h: null, min_flow_m3h: null, train: 1 },
    ]);
    expect(b.cards[0].result).toMatchObject({ alternative: "2D-HP-AB-2I1-ST-N1-FC", design_id: "A1 · 2D-HP-AB-2I1-ST-N1-FC", flags: ["2I1", "ST", "N1", "FC"] });
    expect(b.cards[0].result.doublets!.map((d) => [d.injectors, d.train])).toEqual([
      [2, 0],
      [1, 1],
    ]);
    expect(runSearch(b, 0)?.chosen).toBe("2D-HP-AB-2I1-ST-N1-FC");
  });
});

