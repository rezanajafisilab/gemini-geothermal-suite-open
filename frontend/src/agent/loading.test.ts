// Loading the models: what the app bar's chip says (loading, ready then fading, failed), how
// often it asks the server, that it stops when they are ready, and the working view's row.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ModelsChipView } from "../components/ModelsChip";
import { StepsGroup, details } from "../components/StepsGroup";
import { FADE_MS, FAILED_POLL_MS, ModelsWatcher, POLL_MS, READY_SHOW_MS, chipView, fetchModels, type ChipView, type ModelsStatus } from "./loading";
import { emptyChat, reduce, replay } from "./reducer";
import type { AgEvent, Turn } from "./types";

const reader = { model: "qwen3:1.7b", roles: ["reader"], device: "gpu" as const, size_gb: 1.36 };
const deep = { model: "qwen3.5:9b", roles: ["answerer", "reasoning"], device: "gpu" as const, size_gb: 6.55 };

function status(state: ModelsStatus["state"], loaded: number, seconds: number, extra: Partial<ModelsStatus> = {}): ModelsStatus {
  return {
    ready: state === "ready",
    state,
    loaded,
    total: 2,
    seconds,
    models: [
      { ...reader, state: loaded >= 1 ? "ready" : state === "loading" ? "loading" : "waiting", seconds: 2.1 },
      { ...deep, state: loaded >= 2 ? "ready" : loaded === 1 && state === "loading" ? "loading" : "waiting", seconds: loaded >= 1 ? seconds - 2.1 : null },
    ],
    ...extra,
  };
}

const DOWN = status("failed", 0, 0.1, { message: "Ollama is not running", hint: "Start it with: ollama serve" });

/** A watcher on a list of answers (the last repeats), recording each view it shows. */
function watch(answers: (ModelsStatus | "unsupported" | null)[]) {
  const views: (ChipView | null)[] = [];
  let calls = 0;
  const fetcher = vi.fn(async () => answers[Math.min(calls++, answers.length - 1)]);
  const w = new ModelsWatcher(fetcher, (v) => views.push(v));
  return { w, views, fetcher, last: () => views[views.length - 1] };
}

describe("the models chip", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("says how many are loaded and for how long, with every model in the tooltip", () => {
    const v = chipView(status("loading", 1, 12.4))!;
    expect(v.phase).toBe("loading");
    expect(v.text).toBe("Loading the models · 1 of 2 · 12 s");
    expect(v.title.split("\n").slice(0, 2)).toEqual(["qwen3:1.7b (reads) · GPU · ready, 2 s", "qwen3.5:9b (answers, reasons) · GPU · loading, 10 s"]);
    expect(chipView(status("idle", 0, 0))).toBeNull();
  });

  it("polls once a second while loading, then shows Models ready, fades and stops", async () => {
    const { w, views, fetcher, last } = watch([status("loading", 0, 0.4), status("loading", 1, 3), status("ready", 2, 9)]);
    w.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(last()?.text).toBe("Loading the models · 0 of 2 · 0 s");
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(last()?.text).toBe("Loading the models · 1 of 2 · 3 s");
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(last()).toMatchObject({ phase: "ready", text: "Models ready" });
    await vi.advanceTimersByTimeAsync(READY_SHOW_MS);
    expect(last()?.phase).toBe("fading");
    await vi.advanceTimersByTimeAsync(FADE_MS);
    expect(last()).toBeNull();
    const asked = fetcher.mock.calls.length;
    await vi.advanceTimersByTimeAsync(30_000);
    expect(fetcher.mock.calls.length).toBe(asked); // stopped: no polling once ready
    expect(views.map((v) => v?.phase ?? null)).toEqual(["loading", "loading", "ready", "fading", null]);
  });

  it("shows nothing when the models were ready at the first look", async () => {
    const { w, views, fetcher } = watch([status("ready", 2, 5)]);
    w.start();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(views).toEqual([null]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("says what failed and what to do, and recovers when Ollama starts", async () => {
    const { w, fetcher, last } = watch([DOWN, status("loading", 0, 1), status("ready", 2, 8)]);
    w.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(last()).toMatchObject({ phase: "failed", text: "Ollama is not running", hint: "Start it with: ollama serve" });
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(fetcher).toHaveBeenCalledTimes(1); // a failure is looked at less often
    await vi.advanceTimersByTimeAsync(FAILED_POLL_MS - POLL_MS);
    expect(last()?.phase).toBe("loading");
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(last()?.text).toBe("Models ready");
  });

  it("stays out of the way of an older server and a server that doesn't answer", async () => {
    const old = watch(["unsupported"]);
    old.w.start();
    await vi.advanceTimersByTimeAsync(20_000);
    expect(old.views).toEqual([null]);
    expect(old.fetcher).toHaveBeenCalledTimes(1);
    const off = watch([null, status("loading", 0, 1)]);
    off.w.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(off.last()).toBeNull();
    await vi.advanceTimersByTimeAsync(5000);
    expect(off.last()?.phase).toBe("loading");
    off.w.stop();
  });

  it("reads the endpoint, and a 404 as an older server", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(status("loading", 1, 4)), { status: 200 })));
    expect(await fetchModels()).toMatchObject({ state: "loading", loaded: 1, total: 2 });
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
    expect(await fetchModels()).toBe("unsupported");
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    expect(await fetchModels()).toBeNull();
  });

  it("draws a pulsing dot while loading, a tick when ready, the hint's command in code", () => {
    const loading = renderToStaticMarkup(createElement(ModelsChipView, { view: chipView(status("loading", 1, 12)) }));
    expect(loading).toContain('class="pill pill-line load-chip is-loading"');
    expect(loading).toContain('role="status"');
    expect(loading).toContain('<span class="load-dot"');
    expect(loading).toContain("Loading the models · 1 of 2 · 12 s");
    const ready = renderToStaticMarkup(createElement(ModelsChipView, { view: chipView(status("ready", 2, 9)) }));
    expect(ready).toContain("load-tick");
    expect(ready).toContain("Models ready");
    const failed = renderToStaticMarkup(createElement(ModelsChipView, { view: chipView(DOWN) }));
    expect(failed).toContain("is-failed");
    expect(failed).toContain('<span class="load-hint"><code>ollama serve</code></span>');
    expect(chipView(DOWN)!.title.split("\n")[0]).toBe("Start it with: ollama serve");
    const other = renderToStaticMarkup(createElement(ModelsChipView, { view: { phase: "failed", text: "qwen3.5:9b took too long to load", hint: "Send a message to try again", title: "" } }));
    expect(other).toContain('<span class="load-hint">Send a message to try again</span>');
    expect(renderToStaticMarkup(createElement(ModelsChipView, { view: null }))).toBe("");
  });
});

describe("the working view's load row", () => {
  const LABEL = "Load qwen3.5:9b into GPU memory (6.6 GB, first time only)";
  const started: AgEvent = { type: "STEP_STARTED", stepName: "load_model", metadata: { label: LABEL, kind: "tool", code: null }, timestamp: 1 } as AgEvent;
  const finished = (meta: Record<string, unknown>): AgEvent => ({ type: "STEP_FINISHED", stepName: "load_model", metadata: { seconds: 14.2, model: "qwen3.5:9b", device: "gpu", ...meta }, timestamp: 2 }) as AgEvent;
  const turnOf = (events: AgEvent[]): Turn =>
    replay(reduce(emptyChat("s"), { type: "send", turnId: "t", message: "x", at: 0 }), [{ type: "RUN_STARTED", threadId: "s", runId: "r", timestamp: 0 } as AgEvent, ...events]).turns[0];
  const draw = (turn: Turn) => renderToStaticMarkup(createElement(StepsGroup, { turn, open: true, onToggle: () => {}, focusKey: null, now: 0 }));

  it("is the first row while the model loads, and the group's title", () => {
    const t = turnOf([started]);
    expect(t.steps.map((s) => [s.name, s.status])).toEqual([["load_model", "active"]]);
    const html = draw(t);
    expect(html).toContain(LABEL);
    expect(html).toContain("Only the first message waits for this");
    expect(html).not.toContain("model call");
  });

  it("ticks off when loaded, with its time", () => {
    const t = turnOf([started, finished({})]);
    expect(t.steps[0].status).toBe("done");
    expect(details(t.steps[0], t).tags).toEqual([{ text: "in memory", tone: "ok" }]);
    expect(draw(t)).toContain("14.2 s");
  });

  it("ends red with what to do when the model can't load", () => {
    const t = turnOf([started, finished({ failed: 1, error: "qwen3.5:9b is not downloaded", hint: "Run: ollama pull qwen3.5:9b" })]);
    expect(t.steps[0].status).toBe("error");
    expect(details(t.steps[0], t).subs.map((s) => s.text)).toEqual(["qwen3.5:9b is not downloaded. Run: ollama pull qwen3.5:9b"]);
  });
});
