import { describe, expect, it } from "vitest";

import { newTurn } from "../agent/reducer";
import type { Step, Turn } from "../agent/types";
import { agentsOf } from "./AgentsPanel";

const step = (name: string, status: Step["status"] = "done", meta: Record<string, unknown> = {}, seconds = 0.5): Step => ({
  key: `${name}-0`,
  name,
  label: name,
  kind: "tool",
  status,
  run: 0,
  seconds,
  meta,
  tools: [],
});

function turnWith(steps: Step[], usage: Turn["usage"] = []): Turn {
  return { ...newTurn("t", "Design the plant", 0), steps, usage };
}

describe("agentsOf", () => {
  it("names each agent once, in the order it first acted, with its model or code", () => {
    const t = turnWith(
      [step("intake"), step("think", "done", { decided_by: "model", model: "qwen3:1.7b" }), step("plan", "done", { decided_by: "rules" }), step("doublet"), step("simulate"), step("verify"), step("improve"), step("rank"), step("answer")],
      [
        { purpose: "intake", model: "qwen3:1.7b", ok: true } as Turn["usage"][number],
        { purpose: "answer", model: "qwen3.5:9b", ok: true } as Turn["usage"][number],
      ],
    );
    const rows = agentsOf(t);
    expect(rows.map((r) => r.role.id)).toEqual(["reader", "planner", "engineer", "verifier", "economist", "writer"]);
    expect(rows.find((r) => r.role.id === "reader")!.who).toBe("qwen3:1.7b");
    expect(rows.find((r) => r.role.id === "planner")!.who).toBe("rules");
    expect(rows.find((r) => r.role.id === "engineer")!.who).toBe("GEMINI + plant model");
    expect(rows.find((r) => r.role.id === "writer")!.who).toBe("qwen3.5:9b");
    expect(rows.find((r) => r.role.id === "engineer")!.steps.map((s) => s.name)).toEqual(["doublet", "simulate"]);
  });

  it("marks the agent at work and the one waiting for the user", () => {
    const rows = agentsOf(turnWith([step("intake"), step("simulate", "active"), step("ask", "waiting")]));
    expect(rows.find((r) => r.role.id === "engineer")!.status).toBe("active");
    expect(rows.find((r) => r.role.id === "planner")!.status).toBe("waiting");
    expect(rows.find((r) => r.role.id === "reader")!.status).toBe("done");
  });
});
