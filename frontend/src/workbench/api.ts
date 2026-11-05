// The workbench API (hackathon/docs/workbench_api.md): one function per endpoint. None of them
// throws: a failure comes back as { ok: false, status, message, offline } with a sentence to show
// (offline: the server isn't answering), like agent/client.ts does for file previews.
//
// FIXTURES. In fixture mode the functions never call the server: they answer from the FIXTURE
// files in src/fixtures/ (workbench.json, catalogue.json, gemini-run.json and gemini-run-trains.json,
// sensitivity.json, trace.json, evidence.json), written from the real backend by
// hackathon/scripts/make_ui_fixtures.py. The
// mode comes from the URL:
//   ?fixture=<scene>     the chat's replay mode (no server): the workbench uses the fixtures too
//   ?workbench=fixture   fixtures with a live chat (work on the tabs before the backend has them)
//   ?workbench=empty     fixtures with no designs (the tabs' empty states)
//   ?workbench=live      the server even in a chat replay
// In fixture mode the edits (assumptions, new and deleted designs) are kept in memory for the
// visit and nothing is recomputed: a user design copies its base's numbers. Results carry
// fixture: true so the tabs can say so.

import type {
  AssumptionsPatch,
  Catalogue,
  Design,
  DesignChanges,
  Evidence,
  GeminiProject,
  GeminiRun,
  OutagesView,
  RiskView,
  Sensitivity,
  SensitivityParameters,
  SensitivityRequest,
  SweepView,
  Trace,
  Transcript,
  Workbench,
} from "./types";

export interface ApiError {
  ok: false;
  /** The HTTP status; 0 when the server couldn't be reached. */
  status: number;
  /** A sentence to show. */
  message: string;
  /** The server isn't answering (network error, or a dev proxy with nothing behind it). */
  offline: boolean;
}

export type ApiResult<T> = { ok: true; data: T; fixture: boolean } | ApiError;

// ------------------------------------------------------------------ mode

export type WorkbenchMode = "live" | "fixture" | "empty";

function modeFromUrl(): WorkbenchMode {
  if (typeof window === "undefined") return "live";
  const q = new URLSearchParams(window.location.search);
  const w = q.get("workbench");
  if (w === "fixture" || w === "empty" || w === "live") return w;
  return q.has("fixture") ? "fixture" : "live";
}

let mode: WorkbenchMode = modeFromUrl();

/** Where the workbench comes from: the server, or the fixture files. */
export function workbenchMode(): WorkbenchMode {
  return mode;
}

/** Switch the mode (tests); forgets the fixture edits. */
export function setWorkbenchMode(m: WorkbenchMode): void {
  mode = m;
  fixtureThreads.clear();
}

export const usesFixtures = () => mode !== "live";

// ------------------------------------------------------------------ live requests

const OFFLINE: ApiError = { ok: false, status: 0, message: "The agent server isn't answering.", offline: true };

function detailOf(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const d = (data as Record<string, unknown>).detail ?? (data as Record<string, unknown>).message;
  if (typeof d === "string") return d;
  // FastAPI's validation errors: [{loc, msg, type}, …]
  if (Array.isArray(d) && d.length && typeof d[0]?.msg === "string") return `The server couldn't read the request: ${d[0].msg}.`;
  return null;
}

export async function request<T>(method: "GET" | "PUT" | "POST" | "DELETE", url: string, body?: unknown, signal?: AbortSignal): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: body === undefined ? { accept: "application/json" } : { accept: "application/json", "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch {
    if (signal?.aborted) return { ok: false, status: 0, message: "Cancelled.", offline: false };
    return OFFLINE;
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* not JSON: an older server, or a dev proxy with no API behind it */
  }
  if (!res.ok) {
    const detail = detailOf(data);
    // A dev proxy with no server behind it answers 502-504.
    if (!detail && res.status >= 502 && res.status <= 504) return OFFLINE;
    if (res.status === 404 && (!detail || detail === "Not Found"))
      return { ok: false, status: 404, message: "The server doesn't have this yet (404): it may be older than the workbench API.", offline: false };
    return { ok: false, status: res.status, message: detail ?? `The server answered ${res.status}.`, offline: false };
  }
  if (data === null) return { ok: false, status: res.status, message: "The server's answer wasn't JSON.", offline: false };
  return { ok: true, data: data as T, fixture: false };
}

const q = (params: Record<string, string>) => new URLSearchParams(params).toString();

// ------------------------------------------------------------------ endpoints

/** GET /api/workbench?threadId=T: the conversation's designs and assumptions. */
export function getWorkbench(threadId: string, signal?: AbortSignal): Promise<ApiResult<Workbench>> {
  if (usesFixtures()) return fixture(() => fixtureWorkbench(threadId));
  return request("GET", `/api/workbench?${q({ threadId })}`, undefined, signal);
}

/** GET /api/outages: a design's unplanned outages over 1,000 drawn years, and the worst case. */
export function getOutages(threadId: string, design: string, spare: boolean, signal?: AbortSignal): Promise<ApiResult<OutagesView>> {
  return request("GET", `/api/outages?${q({ threadId, design, spare: spare ? "1" : "0" })}`, undefined, signal);
}

/** GET /api/risk: a design's backup sized by risk (one day short in ten years) beside N-1;
 * ``spare``: the years drawn with a spare ESP on the shelf (false: as built, none). */
export function getRisk(threadId: string, design: string, spare = false, signal?: AbortSignal): Promise<ApiResult<RiskView>> {
  return request("GET", `/api/risk?${q({ threadId, design, spare: spare ? "1" : "0" })}`, undefined, signal);
}

/** GET /api/sweep?threadId=T&search=S1: a search's design-space sweep, for the Compare map. */
export function getSweep(threadId: string, search: string, signal?: AbortSignal): Promise<ApiResult<SweepView>> {
  return request("GET", `/api/sweep?${q({ threadId, search })}`, undefined, signal);
}

/** PUT /api/assumptions: change assumptions (null = back to the default); economics is recomputed. */
export function putAssumptions(body: { threadId: string; assumptions: AssumptionsPatch }, signal?: AbortSignal): Promise<ApiResult<Workbench>> {
  if (usesFixtures()) return fixture(() => fixturePutAssumptions(body.threadId, body.assumptions));
  return request("PUT", "/api/assumptions", body, signal);
}

/** POST /api/designs: add a user design (U1, U2 …) built from `base` with `changes`, run end to end. */
export function createDesign(
  body: { threadId: string; base: string; name?: string; changes: DesignChanges },
  signal?: AbortSignal,
): Promise<ApiResult<{ design: Design }>> {
  if (usesFixtures()) return fixture(() => fixtureCreateDesign(body));
  return request("POST", "/api/designs", body, signal);
}

/**
 * POST /api/designs/open: bring a design of any search (a candidate not yet in the tabs) into the
 * Design and Economics tabs; it runs again with its daily series. Answers the full design.
 */
export function openDesign(body: { threadId: string; id: string }, signal?: AbortSignal): Promise<ApiResult<{ design: Design }>> {
  if (usesFixtures())
    return fixture(async () => {
      const d = (await threadState(body.threadId)).designs.find((x) => x.id === body.id);
      if (!d) throw new FixtureError(404, `Fixture mode can only open the designs already in the tabs, not ${body.id}.`);
      return { design: clone(d) };
    });
  return request("POST", "/api/designs/open", body, signal);
}

/** POST /api/designs/meta: a design's own name ("" takes it away) and its star; the workbench back. */
export function setDesignMeta(body: { threadId: string; id: string; name?: string; starred?: boolean }, signal?: AbortSignal): Promise<ApiResult<Workbench>> {
  if (usesFixtures())
    return fixture(async () => {
      const wb = await threadState(body.threadId);
      const apply = <T extends { id: string; user_name?: string | null; label?: string; starred?: boolean }>(d: T): T =>
        d.id !== body.id ? d : { ...d, ...(body.name !== undefined ? { user_name: body.name || null, label: body.name || d.label } : {}), ...(body.starred !== undefined ? { starred: body.starred } : {}) };
      wb.designs = wb.designs.map(apply);
      if (wb.library) wb.library = wb.library.map(apply);
      return clone(wb);
    });
  return request("POST", "/api/designs/meta", body, signal);
}

/** DELETE /api/designs?threadId=T&id=U1 (user designs only). */
export function deleteDesign(threadId: string, id: string, signal?: AbortSignal): Promise<ApiResult<{ ok: true }>> {
  if (usesFixtures()) return fixture(() => fixtureDeleteDesign(threadId, id));
  return request("DELETE", `/api/designs?${q({ threadId, id })}`, undefined, signal);
}

/** GET /api/gemini/catalogue: GEMINI's component types. */
export function getCatalogue(signal?: AbortSignal): Promise<ApiResult<Catalogue>> {
  if (usesFixtures()) return fixture(async () => ({ types: (await loadFixtures()).catalogue.types }));
  return request("GET", "/api/gemini/catalogue", undefined, signal);
}

/** POST /api/gemini/run: run a GEMINI project with the team's fixes (and the released GEMINI too). */
export function runGemini(body: { project: GeminiProject; compare_released?: boolean }, signal?: AbortSignal): Promise<ApiResult<GeminiRun>> {
  if (usesFixtures()) return fixture(() => fixtureRunGemini(body));
  return request("POST", "/api/gemini/run", body, signal);
}

/** GET /api/sensitivity/parameters: what can vary, and what can be measured. */
export function getSensitivityParameters(signal?: AbortSignal): Promise<ApiResult<SensitivityParameters>> {
  if (usesFixtures())
    return fixture(async () => {
      const s = (await loadFixtures()).sensitivity;
      return { parameters: s.parameters, outputs: s.outputs };
    });
  return request("GET", "/api/sensitivity/parameters", undefined, signal);
}

/** POST /api/sensitivity: tornado, spider and (samples > 0) Monte Carlo for one design. */
export function runSensitivity(body: SensitivityRequest, signal?: AbortSignal): Promise<ApiResult<Sensitivity>> {
  if (usesFixtures()) return fixture(() => fixtureSensitivity(body));
  return request("POST", "/api/sensitivity", body, signal);
}

/** GET /api/trace?threadId=T: every run of the conversation. */
export function getTrace(threadId: string, signal?: AbortSignal): Promise<ApiResult<Trace>> {
  if (usesFixtures()) return fixture(async () => (mode === "empty" ? { runs: [] } : clone((await loadFixtures()).trace)));
  return request("GET", `/api/trace?${q({ threadId })}`, undefined, signal);
}

/** GET /api/transcript?run=R&case=C: one eval case's full transcript, to show read-only. */
export function getTranscript(run: string, caseId: string, signal?: AbortSignal): Promise<ApiResult<Transcript>> {
  return request("GET", `/api/transcript?${q({ run, case: caseId })}`, undefined, signal);
}

/** GET /api/evidence: the eval runs, the benchmarks and GEMINI's bug impact. */
export function getEvidence(signal?: AbortSignal): Promise<ApiResult<Evidence>> {
  if (usesFixtures()) return fixture(async () => clone((await loadFixtures()).evidence));
  return request("GET", "/api/evidence", undefined, signal);
}

// ------------------------------------------------------------------ fixtures

interface Fixtures {
  workbench: Workbench;
  catalogue: Catalogue;
  geminiRun: GeminiRun;
  /** The run of a loop with two treatment trains (U2's): separators, a brine header, an adder, three injectors. */
  geminiRunTrains: GeminiRun;
  sensitivity: SensitivityParameters & { result: Sensitivity };
  trace: Trace;
  evidence: Evidence;
}

let fixtures: Promise<Fixtures> | null = null;

/** The fixture files, loaded once on first use (a separate chunk: live mode never loads them). */
export function loadFixtures(): Promise<Fixtures> {
  fixtures ??= Promise.all([
    import("../fixtures/workbench.json"),
    import("../fixtures/catalogue.json"),
    import("../fixtures/gemini-run.json"),
    import("../fixtures/sensitivity.json"),
    import("../fixtures/trace.json"),
    import("../fixtures/evidence.json"),
    import("../fixtures/gemini-run-trains.json"),
  ]).then(([w, c, g, s, t, e, gt]) => {
    const strip = <T>(m: { default: unknown }): T => {
      const { _fixture: _, ...rest } = m.default as Record<string, unknown>;
      return rest as T;
    };
    return {
      workbench: strip<Workbench>(w),
      catalogue: strip<Catalogue>(c),
      geminiRun: strip<GeminiRun>(g),
      geminiRunTrains: strip<GeminiRun>(gt),
      sensitivity: strip<Fixtures["sensitivity"]>(s),
      trace: strip<Trace>(t),
      evidence: strip<Evidence>(e),
    };
  });
  return fixtures;
}

class FixtureError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const clone = <T>(v: T): T => structuredClone(v);
// A short wait in the browser, so loading states show as they would with a server.
const FIXTURE_DELAY_MS = typeof window === "undefined" ? 0 : 160;

async function fixture<T>(make: () => Promise<T>): Promise<ApiResult<T>> {
  try {
    const data = await make();
    if (FIXTURE_DELAY_MS) await new Promise((r) => setTimeout(r, FIXTURE_DELAY_MS));
    return { ok: true, data, fixture: true };
  } catch (err) {
    if (err instanceof FixtureError) return { ok: false, status: err.status, message: err.message, offline: false };
    return { ok: false, status: 0, message: `The fixtures couldn't be read: ${String(err)}`, offline: false };
  }
}

/** Each thread's workbench in fixture mode, with its edits (this visit only). */
const fixtureThreads = new Map<string, Workbench>();

async function threadState(threadId: string): Promise<Workbench> {
  let wb = fixtureThreads.get(threadId);
  if (!wb) {
    wb = { ...clone((await loadFixtures()).workbench), threadId };
    if (mode === "empty") wb.designs = [];
    fixtureThreads.set(threadId, wb);
  }
  return wb;
}

async function fixtureWorkbench(threadId: string): Promise<Workbench> {
  return clone(await threadState(threadId));
}

async function fixturePutAssumptions(threadId: string, patch: AssumptionsPatch): Promise<Workbench> {
  const wb = await threadState(threadId);
  const a = wb.assumptions as unknown as Record<string, unknown>;
  const defaults = wb.assumptions.defaults as unknown as Record<string, unknown>;
  for (const [key, value] of Object.entries(patch)) {
    if (!(key in defaults)) throw new FixtureError(422, `The server couldn't read the request: unknown assumption ${key}.`);
    a[key] = value === null ? clone(defaults[key]) : value;
    const item = wb.assumptions.items?.find((i) => i.key === key);
    if (item) item.value = (value === null ? defaults[key] : value) as number;
  }
  return clone(wb);
}

async function fixtureCreateDesign(body: { threadId: string; base: string; name?: string; changes: DesignChanges }): Promise<{ design: Design }> {
  const wb = await threadState(body.threadId);
  const base = wb.designs.find((d) => d.id === body.base);
  if (!base) throw new FixtureError(404, `There's no design ${body.base} in this conversation.`);
  const used = wb.designs.map((d) => /^U(\d+)$/.exec(d.code)?.[1]).filter(Boolean).map(Number);
  const code = `U${Math.max(0, ...used) + 1}`;
  const d = clone(base);
  const c = body.changes;
  Object.assign(d, { id: code, code, name: body.name?.trim() || `${base.name}, your version`, origin: "user", parent: base.id, chosen: false });
  if (c.depth_m != null) d.plant.depth_m = c.depth_m;
  if (c.n_doublets != null) d.plant.n_doublets = c.n_doublets;
  if (c.reservoir_delta_c != null) {
    const shift = c.reservoir_delta_c - base.reservoir_delta_c;
    d.reservoir_delta_c = c.reservoir_delta_c;
    d.plant.reservoir_c += shift;
    d.plant.wellhead_c += shift;
  }
  if (c.doublets?.length) {
    // Nothing is recomputed in fixture mode: the set-up is kept so the edit form and the tabs show it.
    d.doublets = clone(c.doublets);
    d.plant.n_doublets = c.doublets.length;
    d.plant.depth_m = c.doublets[0].depth_m;
  }
  if (c.dispatch) {
    d.dispatch = c.dispatch;
    d.plant.dispatch = c.dispatch;
  }
  if (c.return_c != null) d.plant.heating_return_c = c.return_c;
  if (c.cool_return_c != null) d.plant.cooling_return_c = c.cool_return_c;
  const sizes = { heat_pump_mw: "heat_pump", boiler_mw: "boiler", absorption_mw: "absorption", chiller_mw: "chillers" } as const;
  const flags = { heat_pump_mw: "heat_pump", boiler_mw: "boiler", absorption_mw: "absorption", chiller_mw: "chillers" } as const;
  for (const key of Object.keys(sizes) as (keyof typeof sizes)[]) {
    const mw = c[key];
    if (mw == null) continue;
    d.plant.sizes_mw[sizes[key]] = mw;
    d.plant[flags[key]] = mw > 0;
  }
  d.provenance = { ...d.provenance, plant: "user" };
  wb.designs.push(d);
  return { design: clone(d) };
}

async function fixtureDeleteDesign(threadId: string, id: string): Promise<{ ok: true }> {
  const wb = await threadState(threadId);
  const d = wb.designs.find((x) => x.id === id);
  if (!d) throw new FixtureError(404, `There's no design ${id} in this conversation.`);
  if (d.origin !== "user") throw new FixtureError(400, "Only your own designs can be deleted.");
  wb.designs = wb.designs.filter((x) => x.id !== id);
  return { ok: true };
}

/** The fixture run that covers most of a project's components (one train, or two). */
export function bestRun(runs: GeminiRun[], names: string[]): GeminiRun {
  const covered = (r: GeminiRun) => names.filter((n) => n in r.outputs).length;
  return runs.reduce((best, r) => (covered(r) > covered(best) ? r : best), runs[0]);
}

async function fixtureRunGemini(body: { project: GeminiProject; compare_released?: boolean }): Promise<GeminiRun> {
  const f = await loadFixtures();
  const names = Object.keys(body.project?.components ?? {});
  const run = clone(bestRun([f.geminiRun, f.geminiRunTrains], names));
  if (!names.length) return { ...run, ok: false, error: "The project has no components.", outputs: {}, released: null };
  const only = (o: GeminiRun["outputs"]) => Object.fromEntries(Object.entries(o).filter(([k]) => names.includes(k)));
  return {
    ...run,
    outputs: only(run.outputs),
    released: body.compare_released && run.released ? { ...run.released, outputs: only(run.released.outputs) } : null,
  };
}

async function fixtureSensitivity(body: SensitivityRequest): Promise<Sensitivity> {
  const wb = await threadState(body.threadId);
  if (!wb.designs.some((d) => d.id === body.design)) throw new FixtureError(404, `There's no design ${body.design} in this conversation.`);
  const s = clone((await loadFixtures()).sensitivity.result);
  const keys = new Set(body.parameters.map((p) => p.key));
  const outs = new Set(body.outputs);
  const pick = (r: Record<string, number>) => (outs.size ? Object.fromEntries(Object.entries(r).filter(([k]) => outs.has(k))) : r);
  const tornado = s.tornado.filter((t) => !keys.size || keys.has(t.key));
  return {
    ...s,
    design: body.design,
    base: pick(s.base),
    tornado: tornado.map((t) => ({ ...t, low: pick(t.low), high: pick(t.high) })),
    spider: s.spider.filter((p) => !keys.size || keys.has(p.key)).map((p) => ({ ...p, points: p.points.map((pt) => ({ ...pt, values: pick(pt.values) })) })),
    monte_carlo:
      body.samples && s.monte_carlo
        ? { ...s.monte_carlo, outputs: Object.fromEntries(Object.entries(s.monte_carlo.outputs).filter(([k]) => !outs.size || outs.has(k))) }
        : null,
  };
}
