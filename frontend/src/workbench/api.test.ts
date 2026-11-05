import { afterEach, describe, expect, it, vi } from "vitest";

import { createDesign, deleteDesign, getCatalogue, getEvidence, getTrace, getWorkbench, putAssumptions, runGemini, runSensitivity, setWorkbenchMode } from "./api";
import type { Design, Workbench } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
  setWorkbenchMode("live");
});

const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
const gwh = (dailyMw: number[]) => (sum(dailyMw) * 24) / 1000;

async function fixtureWorkbench(threadId = "t1"): Promise<Workbench> {
  setWorkbenchMode("fixture");
  const res = await getWorkbench(threadId);
  if (!res.ok) throw new Error(res.message);
  expect(res.fixture).toBe(true);
  return res.data;
}

describe("fixture mode", () => {
  it("answers from the fixtures without calling the server", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const wb = await fixtureWorkbench("abc");
    expect(fetch).not.toHaveBeenCalled();
    expect(wb.threadId).toBe("abc");
    // The fixture of 31 Oct: the pick, four what-ifs (two re-searched), two designs of the user's.
    expect(wb.designs.map((d) => d.origin)).toEqual(["agent", "what_if", "what_if", "what_if", "what_if", "user", "user"]);
    expect(wb.designs.filter((d) => d.chosen)).toHaveLength(1);
    expect(wb.designs[0].chosen).toBe(true);
    expect(wb.candidates!.length).toBeGreaterThan(20);
    expect(wb.reference!.code).toBe("REF");
    expect("_fixture" in wb).toBe(false);
    for (const call of [getCatalogue(), getEvidence(), getTrace("abc")]) expect((await call).ok).toBe(true);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("has no designs in the empty mode", async () => {
    setWorkbenchMode("empty");
    const res = await getWorkbench("t1");
    expect(res.ok && res.data.designs).toEqual([]);
    const trace = await getTrace("t1");
    expect(trace.ok && trace.data.runs).toEqual([]);
  });

  it("keeps user designs and assumptions per thread for the visit", async () => {
    const wb = await fixtureWorkbench("t1");
    const base = wb.designs[0];
    const made = await createDesign({ threadId: "t1", base: base.id, name: "Without the heat pump", changes: { heat_pump_mw: 0, reservoir_delta_c: -5 } });
    expect(made.ok).toBe(true);
    if (!made.ok) return;
    const u = made.data.design;
    // The fixture already holds two user designs (U1, U2), so this one is U3.
    expect(u).toMatchObject({ id: "U3", code: "U3", origin: "user", parent: base.id, chosen: false, name: "Without the heat pump", reservoir_delta_c: -5 });
    expect(u.plant.heat_pump).toBe(false);
    expect(u.plant.sizes_mw.heat_pump).toBe(0);
    expect(u.plant.reservoir_c).toBeCloseTo(base.plant.reservoir_c - 5, 6);
    expect(u.provenance.plant).toBe("user");
    const again = await getWorkbench("t1");
    expect(again.ok && again.data.designs.map((d) => d.id)).toContain("U3");
    const other = await getWorkbench("t2");
    expect(other.ok && other.data.designs.map((d) => d.id)).not.toContain("U3");

    expect((await deleteDesign("t1", base.id)).ok).toBe(false);
    expect((await deleteDesign("t1", "U3")).ok).toBe(true);

    const changed = await putAssumptions({ threadId: "t1", assumptions: { gas_eur_per_mwh: 50, discount_rate: null } });
    expect(changed.ok && changed.data.assumptions.gas_eur_per_mwh).toBe(50);
    expect(changed.ok && changed.data.assumptions.discount_rate).toBe(changed.ok && changed.data.assumptions.defaults.discount_rate);
    expect(changed.ok && changed.data.assumptions.items.find((i) => i.key === "gas_eur_per_mwh")?.value).toBe(50);
  });

  it("answers GEMINI runs and sensitivity for the project and design asked", async () => {
    const wb = await fixtureWorkbench("t1");
    const project = wb.designs[0].graph.gemini_project!;
    const run = await runGemini({ project, compare_released: true });
    expect(run.ok && Object.keys(run.data.outputs).sort()).toEqual(Object.keys(project.components).sort());
    expect(run.ok && run.data.released).toBeTruthy();
    const design = wb.designs[0].id;
    const sens = await runSensitivity({ threadId: "t1", design, parameters: [{ key: "reservoir_temp", low: -10, high: 5 }], outputs: ["lcoh"], samples: 0 });
    expect(sens.ok && sens.data.tornado.map((t) => t.key)).toEqual(["reservoir_temp"]);
    expect(sens.ok && Object.keys(sens.data.base)).toEqual(["lcoh"]);
    expect(sens.ok && sens.data.monte_carlo).toBeNull();
    expect((await runSensitivity({ threadId: "t1", design: "Z9", parameters: [], outputs: [] })).ok).toBe(false);
  });
});

describe("fixture mode with doublets", () => {
  it("answers a multi-train project with the multi-train run", async () => {
    const wb = await fixtureWorkbench("t1");
    const u2 = wb.designs.find((d) => d.id === "U2")!.graph.gemini_project!;
    const run = await runGemini({ project: u2 });
    expect(run.ok && Object.keys(run.data.outputs).sort()).toEqual(Object.keys(u2.components).sort());
    expect(run.ok && run.data.outputs.brine_splitter.output_2).toBeCloseTo(300, 0);
    const pick = wb.designs[0].graph.gemini_project!;
    const one = await runGemini({ project: pick });
    expect(one.ok && Object.keys(one.data.outputs).sort()).toEqual(Object.keys(pick.components).sort());
  });

  it("keeps the doublets and the dispatch of a user design made in fixture mode", async () => {
    const wb = await fixtureWorkbench("t3");
    const doublets = [
      { depth_m: 2500, producer_open: "lower" as const, injector_open: "full" as const, injectors: 2 as const, max_flow_m3h: null, train: 0 },
      { depth_m: 3000, producer_open: "full" as const, injector_open: "upper" as const, injectors: 1 as const, max_flow_m3h: 200, train: 1 },
    ];
    const made = await createDesign({ threadId: "t3", base: wb.designs[0].id, changes: { doublets, dispatch: "base" } });
    expect(made.ok && made.data.design.doublets).toEqual(doublets);
    expect(made.ok && made.data.design.plant).toMatchObject({ n_doublets: 2, dispatch: "base" });
  });
});

describe("the fixture data", () => {
  it("has the chosen design on GEMINI's wells, with the reservoir under them", async () => {
    const chosen = (await fixtureWorkbench()).designs[0];
    expect(chosen.verified).toBe(true);
    expect(chosen.source).toBe("gemini+dioscuri_plant");
    expect(chosen.provenance.plant).toBe("gemini");
    expect(chosen.plant.n_doublets).toBeGreaterThanOrEqual(1);
    expect(chosen.plant.flow_m3h).toBe(300);
    // The brine loses heat up the well (Ramey): about 1-2 K at full flow, more when slow.
    const loss = chosen.plant.reservoir!.temperature_c - chosen.plant.wellhead_c;
    expect(loss).toBeGreaterThan(0.5);
    expect(loss).toBeLessThan(3);
    expect(chosen.graph.nodes[0].type).toBe("reservoir");
    expect(chosen.year.violations).toEqual([]);
    expect(chosen.checks.every((c) => c.passed)).toBe(true);
  });

  it("adds up: days to months to the year, cost lines to LCOH and LCOC", async () => {
    const designs: Design[] = (await fixtureWorkbench()).designs;
    for (const d of designs) {
      const y = d.year;
      for (const side of ["heat", "cool"] as const) {
        for (const [key, daily] of Object.entries(y.daily_mw[side])) {
          const months = (y.monthly_gwh[side] as Record<string, number[]>)[key];
          expect(daily).toHaveLength(365);
          expect(months).toHaveLength(12);
          expect(sum(months)).toBeCloseTo(gwh(daily), 1);
        }
      }
      for (const [k, v] of Object.entries(y.heat_split_gwh)) expect(gwh(y.daily_mw.heat[k as "geo"])).toBeCloseTo(v, 1);
      for (const [k, v] of Object.entries(y.cool_split_gwh)) expect(gwh(y.daily_mw.cool[k as "abs"])).toBeCloseTo(v, 1);
      expect(sum(Object.values(y.heat_split_gwh))).toBeCloseTo(y.heat_delivered_gwh, 2);
      expect(sum(Object.values(y.cool_split_gwh))).toBeCloseTo(y.cool_delivered_gwh, 2);
      expect(gwh(y.daily_mw.heat.demand)).toBeCloseTo(y.heat_demand_gwh, 1);
      expect(sum(d.economics.lines.heat.map((l) => l.eur_per_mwh))).toBeCloseTo(d.economics.lcoh, 0);
      expect(sum(d.economics.lines.cold.map((l) => l.eur_per_mwh))).toBeCloseTo(d.economics.lcoc ?? 0, 0);
      for (const e of d.graph.edges) {
        expect(d.graph.nodes.some((n) => n.id === e.source)).toBe(true);
        expect(d.graph.nodes.some((n) => n.id === e.target)).toBe(true);
      }
    }
  });

  it("has a what-if that breaks a cap and a gas reference that costs more", async () => {
    const wb = await fixtureWorkbench();
    // The what-ifs carry their name and code in their id ("W1 · 1D-HP-EC-N1") and their change in
    // change_label; the one on the pick itself (colder, with a smaller boiler) breaks a cap.
    const whatIf = wb.designs.find((d) => d.origin === "what_if" && !d.verified)!;
    expect(whatIf.id).toBe(`${whatIf.uid} · ${whatIf.code}`);
    expect(whatIf.uid).toMatch(/^W\d+$/);
    expect(whatIf.change_label).toMatch(/^reservoir -\d+ K/);
    expect(whatIf.parent).toBe(wb.designs[0].id);
    expect(whatIf.reservoir_delta_c).toBeLessThan(0);
    expect(whatIf.verified).toBe(false);
    expect(whatIf.year.violations!.length).toBeGreaterThan(0);
    const ref = wb.reference!;
    expect(ref.depth_m).toBe(0);
    expect(ref.lcoh).toBeGreaterThan(wb.designs[0].economics.lcoh);
    expect(wb.candidates![0].role).toBe("chosen");
    expect(wb.candidates!.slice(1).every((c) => c.reason)).toBe(true);
  });
});

describe("live mode", () => {
  it("calls the endpoint and passes the answer through", async () => {
    const body = { threadId: "t1", physics: "gemini", gemini: null, assumptions: {}, designs: [] };
    const fetch = vi.fn(async () => new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    const res = await getWorkbench("t 1");
    expect(res).toEqual({ ok: true, data: body, fixture: false });
    expect(fetch).toHaveBeenCalledWith("/api/workbench?threadId=t+1", expect.objectContaining({ method: "GET" }));
    await deleteDesign("t1", "U1");
    expect(fetch).toHaveBeenLastCalledWith("/api/designs?threadId=t1&id=U1", expect.objectContaining({ method: "DELETE" }));
  });

  it("says the server is offline when it can't be reached or a dev proxy has nothing behind it", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    expect(await getWorkbench("t1")).toEqual({ ok: false, status: 0, message: "The agent server isn't answering.", offline: true });
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 502 })));
    expect(await getEvidence()).toMatchObject({ ok: false, offline: true });
  });

  it("shows the server's own message, and explains a missing endpoint", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Only user designs can be deleted." }), { status: 400 })));
    expect(await deleteDesign("t1", "A1")).toEqual({ ok: false, status: 400, message: "Only user designs can be deleted.", offline: false });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 })));
    const missing = await getCatalogue();
    expect(missing).toMatchObject({ ok: false, status: 404, offline: false });
    expect(!missing.ok && missing.message).toMatch(/doesn't have this yet/);
  });
});
