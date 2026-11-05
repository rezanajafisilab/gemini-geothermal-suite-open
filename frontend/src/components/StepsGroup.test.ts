// The steps as tick-off rows on the recorded streams: what the new steps of the challenge engine
// show (parameters, confirm, inputs, the what-if's search), the title while the inputs card
// waits, and no row of any recorded stream showing "undefined", "NaN" or "[object Object]".

import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { emptyChat, reduce, replay } from "../agent/reducer";
import { parseSse } from "../agent/sse";
import type { AgEvent, Step, Turn } from "../agent/types";
import { StepsGroup, details, usedLabel } from "./StepsGroup";

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = join(here, "..", "fixtures");
const load = (name: string): AgEvent[] => parseSse(readFileSync(join(fixtures, `${name}.sse`), "utf-8"));
const turnOf = (events: AgEvent[]): Turn => replay(reduce(emptyChat("s"), { type: "send", turnId: "t", message: "x", at: 0 }), events).turns[0];
const stepOf = (t: Turn, name: string): Step => t.steps.find((s) => s.name === name)!;
const draw = (turn: Turn) => renderToStaticMarkup(createElement(StepsGroup, { turn, open: true, onToggle: () => {}, focusKey: null, now: 0 }));

describe("the challenge engine's new steps", () => {
  it("parameters: each change it read as the key and its value", () => {
    const w = turnOf(load("whatif-return"));
    const d = details(stepOf(w, "parameters"), w);
    expect(d.chips).toEqual([{ code: "heat_return_c", name: "→ 50", mono: true }]);
    expect(d.tags).toEqual([]);
    expect(draw(w)).toContain('<span class="alt alt-mono"><b>heat_return_c</b>→ 50</span>');
  });

  it("parameters: nothing to change, or the doublets as the message describes them", () => {
    const c = turnOf(load("confirm"));
    expect(details(stepOf(c, "parameters"), c).tags).toEqual([{ text: "nothing to change", tone: "grey" }]);
    const b = turnOf(load("build-doublets"));
    expect(details(stepOf(b, "parameters"), b).chips).toEqual([
      { code: "D1", name: "2 injectors, own treatment train", title: "A doublet as the message describes it" },
      { code: "D2", name: "own treatment train", title: "A doublet as the message describes it" },
    ]);
  });

  it("parameters: what the model can't vary, and what the checks set aside", () => {
    const c = turnOf(load("confirm"));
    const step = { ...stepOf(c, "parameters"), meta: { decided_by: "model", changes: { gas_eur_per_mwh: 45 }, doublets: [], unsupported: ["a heat storage tank"], dropped: ["heat_return_c=50: the quote is not in the message"] } };
    const d = details(step, c);
    expect(d.chips).toEqual([{ code: "gas_eur_per_mwh", name: "→ 45", mono: true }]);
    expect(d.subs.map((s) => s.text)).toEqual([
      "Not in the model, so not changed: a heat storage tank",
      "Set aside by the checks: heat_return_c=50: the quote is not in the message",
    ]);
  });

  it("inputs: how many, and how many assumed", () => {
    const c = turnOf(load("confirm"));
    expect(details(stepOf(c, "inputs"), c).tags).toEqual([
      { text: "18 inputs", tone: "grey" },
      { text: "9 assumed", tone: "amber" },
    ]);
  });

  it("confirm: how the reply to the inputs was read", () => {
    const c = turnOf(load("confirm"));
    const confirm = (decision: string): Step => ({ key: "0:confirm:9", name: "confirm", label: "Read the reply to the inputs", kind: "model", status: "done", run: 0, meta: { decision, model: "qwen3.5:9b", device: "gpu" }, tools: [] });
    expect(details(confirm("run"), c).tags).toEqual([{ text: "run the design", tone: "ok" }]);
    expect(details(confirm("change"), c).tags).toEqual([{ text: "change an input", tone: "amber" }]);
    expect(details(confirm("other"), c).subs[0].text).toBe("Read as a new message: the inputs card is set aside.");
    expect(details({ ...confirm("run"), status: "active" }, c).tags).toEqual([]);
  });

  it("the what-if's search: how many designs and which it picks", () => {
    const w = turnOf(load("whatif-return"));
    const d = details(stepOf(w, "search"), w);
    expect(d.tags).toEqual([{ text: "112 designs", tone: "grey" }]);
    expect(d.chips).toEqual([{ code: "1D-HP-EC-N1-FC-PV1.7", name: "the best under the change" }]);
  });

  it("names what an answer drew on: blocks, designs, cost lines and passages", () => {
    expect(usedLabel("draft")).toEqual({ name: "the checked draft" });
    expect(usedLabel("2D-HP-AB-2I1-ST")).toEqual({ code: "2D-HP-AB-2I1-ST", name: "design" });
    expect(usedLabel("A1")).toEqual({ code: "A1", name: "design" });
    expect(usedLabel("2D-HP-AB costs")).toEqual({ code: "2D-HP-AB", name: "cost lines" });
    expect(usedLabel("doc2")).toEqual({ code: "doc 2", name: "passage" });
    expect(usedLabel("data1")).toEqual({ code: "data 1", name: "data file" });
    expect(usedLabel("something")).toEqual({ name: "something" });
  });
});

describe("the group's title", () => {
  it("waits for the go-ahead on the inputs, then for the change after Change an input first", () => {
    const c = turnOf(load("confirm"));
    expect(draw(c)).toContain("Waiting for your go-ahead on the inputs");
    const change = replay(reduce({ threadId: "s", turns: [c] }, { type: "answer", answers: { confirm: "Change an input first" }, at: 1 }), [
      { type: "RUN_STARTED", threadId: "s", runId: "r2" },
      { type: "TEXT_MESSAGE_CONTENT", messageId: "m2", delta: "What should I change?" },
      { type: "RUN_FINISHED", threadId: "s", runId: "r2", outcome: { type: "interrupt", interrupts: [{ id: "r2-ask", reason: "confirm" }] } },
    ]);
    expect(change.turns[0].status).toBe("waiting");
    expect(draw(change.turns[0])).toContain("Waiting for what to change");
  });
});

describe("every recorded stream", () => {
  const names = readdirSync(fixtures)
    .filter((f) => f.endsWith(".sse"))
    .map((f) => f.slice(0, -4));

  it("draws every step with no undefined, NaN or [object Object]", () => {
    expect(names.length).toBeGreaterThan(50);
    for (const name of names) {
      const html = draw(turnOf(load(name)));
      expect(html, name).not.toMatch(/undefined|NaN|\[object Object\]/);
    }
  });
});
