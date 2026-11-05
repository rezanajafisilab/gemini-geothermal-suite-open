import { describe, expect, it, vi } from "vitest";

import type { ApiResult } from "./api";
import { WorkbenchStore, pickDesign } from "./store";
import type { Design, Workbench } from "./types";

const design = (id: string, extra: Partial<Design> = {}): Design =>
  ({ id, code: id.split(" ")[0], name: id, origin: "agent", parent: null, chosen: false, reservoir_delta_c: 0, checks: [], verified: true, ...extra }) as Design;

const wb = (designs: Design[], threadId = "t1"): Workbench => ({ threadId, physics: "gemini", gemini: null, assumptions: {} as Workbench["assumptions"], designs });

describe("pickDesign", () => {
  const a1 = design("A1", { chosen: true });
  const a2 = design("A2");
  const a4 = design("A4");
  const whatIf = design("A1 −10 °C", { code: "A1", origin: "what_if", parent: "A1", reservoir_delta_c: -10 });

  it("is null with no designs", () => {
    expect(pickDesign([], "A1")).toBeNull();
    expect(pickDesign([])).toBeNull();
  });

  it("takes the design asked for by id", () => {
    expect(pickDesign([a2, a1, a4, whatIf], "A4")).toBe(a4);
    expect(pickDesign([a2, a1, a4, whatIf], "A1 −10 °C")).toBe(whatIf);
  });

  it("falls back to the code, preferring the design over its what-if", () => {
    const u = design("U1 (edit)", { code: "U1", origin: "user" });
    expect(pickDesign([whatIf, a1, u], "U1")).toBe(u);
    expect(pickDesign([whatIf, a1], "A1")).toBe(a1);
    expect(pickDesign([whatIf], "A1")).toBe(whatIf);
  });

  it("otherwise shows the chosen design, else the first", () => {
    expect(pickDesign([a2, a1, a4])).toBe(a1);
    expect(pickDesign([a2, a1, a4], "Z9")).toBe(a1);
    expect(pickDesign([a2, a4])).toBe(a2);
  });
});

function fakeApi(answers: ApiResult<Workbench>[]) {
  const getWorkbench = vi.fn(async (threadId: string) => {
    const next = answers.shift() ?? { ok: true as const, data: wb([], threadId), fixture: false };
    return next;
  });
  return {
    getWorkbench,
    putAssumptions: vi.fn(),
    createDesign: vi.fn(async (body: { base: string }) => ({ ok: true as const, data: { design: design("U1", { origin: "user", parent: body.base }) }, fixture: false })),
    deleteDesign: vi.fn(async () => ({ ok: true as const, data: { ok: true as const }, fixture: false })),
  };
}

describe("WorkbenchStore", () => {
  it("loads once, shares a request on its way, and selects the chosen design", async () => {
    const api = fakeApi([{ ok: true, data: wb([design("A2"), design("A1", { chosen: true })]), fixture: true }]);
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    expect(s.entry().status).toBe("idle");
    const p1 = s.load();
    const p2 = s.load("t1", { force: true });
    expect(s.entry().status).toBe("loading");
    await Promise.all([p1, p2]);
    expect(api.getWorkbench).toHaveBeenCalledTimes(1);
    expect(s.entry().status).toBe("ready");
    expect(s.entry().fixture).toBe(true);
    expect(s.selected()?.id).toBe("A1");
    await s.load();
    expect(api.getWorkbench).toHaveBeenCalledTimes(1);
  });

  it("keeps the picked design per thread and falls back when it goes", async () => {
    const api = fakeApi([{ ok: true, data: wb([design("A1", { chosen: true }), design("A2"), design("U1", { origin: "user" })]), fixture: false }]);
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    await s.load();
    s.select("U1");
    expect(s.selected()?.id).toBe("U1");
    expect(s.selected("t2")).toBeNull();
    await s.removeDesign("U1");
    expect(api.deleteDesign).toHaveBeenCalledWith("t1", "U1");
    expect(s.selected()?.id).toBe("A1");
  });

  it("refetches with the old data on screen, and keeps it when the refetch fails", async () => {
    const api = fakeApi([
      { ok: true, data: wb([design("A1", { chosen: true })]), fixture: false },
      { ok: false, status: 0, message: "The agent server isn't answering.", offline: true },
    ]);
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    await s.load();
    const p = s.refresh();
    expect(s.entry().refreshing).toBe(true);
    expect(s.entry().workbench?.designs).toHaveLength(1);
    await p;
    expect(s.entry().status).toBe("ready");
    expect(s.entry().error?.offline).toBe(true);
    expect(s.entry().workbench?.designs).toHaveLength(1);
  });

  it("is in error when the first load fails", async () => {
    const api = fakeApi([{ ok: false, status: 500, message: "boom", offline: false }]);
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    await s.load();
    expect(s.entry().status).toBe("error");
    expect(s.entry().error?.message).toBe("boom");
    expect(s.selected()).toBeNull();
  });

  it("refetches a loaded thread when a chat run on it finishes", async () => {
    const api = fakeApi([
      { ok: true, data: wb([]), fixture: false },
      { ok: true, data: wb([design("A1", { chosen: true })]), fixture: false },
    ]);
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    s.runFinished("t9"); // never loaded: only counted
    expect(api.getWorkbench).not.toHaveBeenCalled();
    expect(s.getSnapshot().runs.t9).toBe(1);
    await s.load();
    s.runFinished("t1");
    await vi.waitFor(() => expect(s.entry().workbench?.designs).toHaveLength(1));
    expect(api.getWorkbench).toHaveBeenCalledTimes(2);
    expect(s.selected()?.id).toBe("A1");
  });

  it("adds a user design to the thread's designs", async () => {
    const api = fakeApi([{ ok: true, data: wb([design("A1", { chosen: true })]), fixture: false }]);
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    await s.load();
    const res = await s.addDesign("A1", { heat_pump_mw: 0 }, "No heat pump");
    expect(res.ok).toBe(true);
    expect(api.createDesign).toHaveBeenCalledWith({ threadId: "t1", base: "A1", name: "No heat pump", changes: { heat_pump_mw: 0 } });
    expect(s.entry().workbench?.designs.map((d) => d.id)).toEqual(["A1", "U1"]);
  });
});

describe("WorkbenchStore.select", () => {
  it("clears the pick with null, back to the chosen design", async () => {
    const api = fakeApi([{ ok: true, data: wb([design("A1", { chosen: true }), design("A2")]), fixture: false }]);
    const s = new WorkbenchStore(api as never);
    s.setThread("t1");
    await s.load();
    s.select("A2");
    expect(s.selected()?.id).toBe("A2");
    s.select(null);
    expect(s.selected()?.id).toBe("A1");
    expect(s.getSnapshot().picked).toEqual({});
  });
});

describe("what-if labels", () => {
  it("says what a what-if changed, from its label, else its id, else the reservoir shift", async () => {
    const { changeText, idParts, originLabel, designTitle } = await import("./format");
    const w = design("2D-HP-AB · heating return temperature 50 °C", { code: "2D-HP-AB", origin: "what_if", change_label: "heating return temperature 50 °C", name: "2 doublets" });
    expect(changeText(w)).toBe("heating return temperature 50 °C");
    expect(originLabel(w)).toBe("what-if: heating return temperature 50 °C");
    expect(idParts(w)).toEqual({ code: "2D-HP-AB", what: "heating return temperature 50 °C" });
    expect(designTitle(w)).toBe("2D-HP-AB 2 doublets (what-if: heating return temperature 50 °C)");
    expect(changeText(design("1D-HP-EC · reservoir -5 K, searched again", { code: "1D-HP-EC", origin: "what_if" }))).toBe("reservoir -5 K, searched again");
    expect(originLabel(design("A1 −10 °C", { code: "A1", origin: "what_if", reservoir_delta_c: -10 }))).toBe("what-if: reservoir −10 °C");
    expect(idParts(design("U2", { origin: "user" }))).toEqual({ code: "U2", what: "" });
    // A design picked by its id with a label comes back as itself.
    const plain = design("2D-HP-AB", { chosen: true });
    expect(pickDesign([plain, w], w.id)).toBe(w);
    expect(pickDesign([w, plain], "2D-HP-AB")).toBe(plain);
  });
});

