// The GPU | CPU switch: which device runs use, which model the header names, the health answer
// it reads (GET /api/health with `profiles`), and the device every run request carries.

import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatStore } from "../state/store";
import { fetchHealth, type Health, type RunBody, type Transport } from "./client";
import { answerRole, hasGpu, pickDevice, pickSize, profileKey, roleRows, roleText } from "./models";
import type { AgEvent } from "./types";

const PROFILES = {
  auto: {
    fast: { model: "qwen3:1.7b", device: "gpu" },
    answer: { model: "qwen3.5:9b", device: "gpu" },
    answer_reasoning: { model: "qwen3.5:9b", device: "gpu" },
    reasoning: { model: "qwen3.5:9b", device: "gpu" },
    generator: { model: "qwen3.5:4b", device: "gpu" },
  },
  cpu: {
    fast: { model: "qwen3:1.7b", device: "cpu" },
    answer: { model: "qwen3:1.7b", device: "cpu" },
    answer_reasoning: { model: "qwen3.5:4b", device: "cpu" },
    reasoning: { model: "qwen3.5:4b", device: "cpu" },
    generator: { model: "qwen3.5:4b", device: "cpu" },
  },
} as const;

const HEALTH = {
  model: "qwen3:1.7b",
  device: "gpu",
  ready: true,
  reasoning: { model: "qwen3.5:9b", device: "gpu", ready: true },
  gpu: "NVIDIA RTX A6000",
  default_device: "auto",
  answer: { model: "qwen3.5:9b", device: "gpu" },
  profiles: PROFILES,
  attachments: { types: [".pdf", ".md"], max_mb: 20 },
};

afterEach(() => vi.unstubAllGlobals());

describe("device and models", () => {
  const health: Health = { state: "ok", ...(HEALTH as Omit<Health, "state">) };

  it("uses the pick, else the server's default; the CPU when there is no GPU", () => {
    expect(pickDevice(null, health)).toBe("auto");
    expect(pickDevice("cpu", health)).toBe("cpu");
    expect(pickDevice(null, { ...health, default_device: "cpu" })).toBe("cpu");
    const noGpu: Health = { ...health, gpu: "" };
    expect(hasGpu(noGpu)).toBe(false);
    expect(pickDevice("auto", noGpu)).toBe("cpu");
    // Unknown (server offline, older server): the pick stands.
    expect(pickDevice("auto", { state: "server-offline" })).toBe("auto");
  });

  it("names the model that answers in this mode on this device", () => {
    expect(roleText(answerRole(health, "auto", false))).toBe("qwen3.5:9b · GPU");
    expect(roleText(answerRole(health, "cpu", false))).toBe("qwen3:1.7b · CPU");
    expect(roleText(answerRole(health, "cpu", true))).toBe("qwen3.5:4b · CPU");
  });

  it("falls back to today's label without profiles", () => {
    const old: Health = { state: "ok", model: "qwen3:1.7b", device: "gpu", reasoning: { model: "qwen3.5:9b", device: "gpu" } };
    expect(roleText(answerRole(old, "cpu", false))).toBe("qwen3:1.7b · GPU");
    expect(roleText(answerRole(old, "auto", true))).toBe("qwen3.5:9b · GPU");
    expect(roleRows(old, "auto", false).map((r) => [r.label, r.role.model, r.active])).toEqual([
      ["Reads messages and answers", "qwen3:1.7b", true],
      ["Plans and explains when it reasons", "qwen3.5:9b", false],
    ]);
  });

  it("lists every role with its model and device, marking the one that answers now", () => {
    const rows = roleRows(health, "cpu", true);
    expect(rows.map((r) => [r.label, roleText(r.role), r.active])).toEqual([
      ["Reads messages", "qwen3:1.7b · CPU", false],
      ["Answers", "qwen3:1.7b · CPU", false],
      ["Answers when it reasons", "qwen3.5:4b · CPU", true],
      ["Plans when it reasons", "qwen3.5:4b · CPU", false],
      ["Writes models", "qwen3.5:4b · CPU", false],
    ]);
  });

  it("reads the new health fields and keeps the old ones", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(HEALTH), { status: 200 })));
    const h = await fetchHealth();
    expect(h).toMatchObject({ state: "ok", model: "qwen3:1.7b", device: "gpu", gpu: "NVIDIA RTX A6000", default_device: "auto" });
    expect(h.answer).toEqual({ model: "qwen3.5:9b", device: "gpu" });
    expect(h.profiles?.cpu?.answer_reasoning).toEqual({ model: "qwen3.5:4b", device: "cpu" });
    const { profiles: _p, default_device: _d, answer: _a, ...older } = HEALTH;
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(older), { status: 200 })));
    const o = await fetchHealth();
    expect(o.profiles).toBeUndefined();
    expect(o.default_device).toBeUndefined();
    expect(o.model).toBe("qwen3:1.7b");
  });
});

describe("every run carries the device and the model size", () => {
  it("sends it with a message and with the answer to a clarification, and leaves reasoning to the agent", async () => {
    const bodies: RunBody[] = [];
    const stream: AgEvent[][] = [
      [
        { type: "RUN_STARTED", threadId: "t", runId: "r0" },
        { type: "CUSTOM", name: "clarification", value: { kind: "choice", intro: "Which?", questions: [{ id: "choice", label: "Which?", options: ["A", "B"], default: null }] } },
        { type: "RUN_FINISHED", threadId: "t", runId: "r0", outcome: { type: "interrupt", interrupts: [{ id: "r0-ask", reason: "choice" }] } },
      ],
      [
        { type: "RUN_STARTED", threadId: "t", runId: "r1" },
        { type: "RUN_FINISHED", threadId: "t", runId: "r1", outcome: { type: "success" } },
      ],
    ];
    const transport: Transport = async function* (body) {
      bodies.push(body);
      yield* stream[bodies.length - 1];
    };
    const store = new ChatStore(null);
    store.pace = false;
    store.setTransport("t", transport);
    store.device = "cpu";
    await store.send("p", "t", "How do I install it?");
    expect(store.chat("t").turns[0].status).toBe("waiting");
    store.device = "auto";
    store.size = "4b";
    await store.answer("t", { choice: "B" });
    expect(bodies.map((b) => "reasoning" in b && b.reasoning !== undefined)).toEqual([false, false]);
    // A message names the chat's project (the server puts a new conversation in it).
    expect(bodies).toEqual([
      { threadId: "t", message: "How do I install it?", device: "cpu", size: "auto", projectId: "p" },
      { threadId: "t", answers: { choice: "B" }, device: "auto", size: "4b" },
    ]);
    expect(store.chat("t").turns[0].status).toBe("done");
  });
});

describe("the model switch (5 Nov)", () => {
  it("keys a profile by device, and by device and size when a size is picked", () => {
    expect(profileKey("auto")).toBe("auto");
    expect(profileKey("cpu", "auto")).toBe("cpu");
    expect(profileKey("auto", "4b")).toBe("auto:4b");
    expect(profileKey("cpu", "9b")).toBe("cpu:9b");
  });
  it("names the picked model in the chip", () => {
    const health = {
      state: "ok",
      gpu: "A6000",
      profiles: {
        auto: { answer: { model: "qwen3.5:9b", device: "gpu" } },
        "auto:4b": { answer: { model: "qwen3.5:4b", device: "gpu" } },
        "cpu:9b": { answer: { model: "qwen3.5:9b", device: "cpu" } },
      },
    } as Health;
    expect(answerRole(health, "auto", false, "auto").model).toBe("qwen3.5:9b");
    expect(answerRole(health, "auto", false, "4b").model).toBe("qwen3.5:4b");
    expect(answerRole(health, "cpu", false, "9b")).toEqual({ model: "qwen3.5:9b", device: "cpu" });
  });
  it("takes the user's size, else the server's, else auto", () => {
    expect(pickSize(null, { state: "ok" } as Health)).toBe("auto");
    expect(pickSize(null, { state: "ok", default_size: "4b" } as Health)).toBe("4b");
    expect(pickSize("9b", { state: "ok", default_size: "4b" } as Health)).toBe("9b");
  });
});
