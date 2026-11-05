// The workbench of the conversation on screen: its designs and assumptions, which design the
// one-design tabs show, and the loading state. One store for every tab, the same pattern as
// state/store.ts (a class with subscribe/getSnapshot, read through useSyncExternalStore).
//
// It loads when a tab that reads designs opens (and again each time one opens, keeping what it
// has on screen meanwhile) and when a chat run on the thread finishes (RUN_FINISHED).

import { useEffect, useMemo, useSyncExternalStore } from "react";

import { store as chatStore } from "../state/store";
import * as apiModule from "./api";
import type { ApiError, ApiResult } from "./api";
import { DESIGN_TABS, TAB_META, currentRoute, go, type Route } from "./route";
import type { AssumptionsPatch, Design, DesignChanges, Workbench } from "./types";

export type WorkbenchStatus = "idle" | "loading" | "ready" | "error";

export interface WorkbenchEntry {
  /** "loading" only until the first answer; a refetch keeps "ready" and sets `refreshing`. */
  status: WorkbenchStatus;
  workbench: Workbench | null;
  /** The last request's failure (kept beside an older workbench when a refetch failed). */
  error: ApiError | null;
  refreshing: boolean;
  /** The data came from the fixture files (src/workbench/api.ts). */
  fixture: boolean;
  loadedAt: number;
}

export interface WorkbenchState {
  /** The thread on screen (the chat's thread id). */
  threadId: string | null;
  entries: Record<string, WorkbenchEntry>;
  /** The design picked per thread (from the route or the picker). */
  picked: Record<string, string>;
  /** Chat runs finished per thread this visit (a dependency for tabs that show runs). */
  runs: Record<string, number>;
}

const IDLE: WorkbenchEntry = { status: "idle", workbench: null, error: null, refreshing: false, fixture: false, loadedAt: 0 };

/**
 * Which design the one-design tabs show: the one asked for (by id, else by code, preferring
 * the design itself over its what-ifs), else the chosen one, else the first; null with none.
 */
export function pickDesign(designs: Design[], wanted?: string | null, latest?: string | null): Design | null {
  if (!designs.length) return null;
  // No design asked for: the one the chat ran last (a what-if just run), else the pick.
  if (!wanted && latest) {
    const last = designs.find((d) => d.id === latest);
    if (last) return last;
  }
  if (wanted) {
    const byId = designs.find((d) => d.id === wanted);
    if (byId) return byId;
    const byCode = designs.filter((d) => d.code === wanted);
    if (byCode.length) return byCode.find((d) => d.origin !== "what_if") ?? byCode[0];
  }
  return designs.find((d) => d.chosen) ?? designs[0];
}

type Api = Pick<typeof apiModule, "getWorkbench" | "putAssumptions" | "createDesign" | "deleteDesign" | "openDesign" | "setDesignMeta">;

export class WorkbenchStore {
  private state: WorkbenchState = { threadId: null, entries: {}, picked: {}, runs: {} };
  private listeners = new Set<() => void>();
  private inflight = new Map<string, Promise<void>>();

  constructor(private api: Api = apiModule) {}

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };

  getSnapshot = () => this.state;

  entry(threadId: string | null = this.state.threadId): WorkbenchEntry {
    return (threadId && this.state.entries[threadId]) || IDLE;
  }

  /** The thread on screen changed (App calls this). */
  setThread(threadId: string) {
    if (this.state.threadId === threadId) return;
    this.state = { ...this.state, threadId };
    this.emit();
  }

  /**
   * Fetch a thread's workbench. Without `force` a loaded one is kept; a request already on its
   * way is shared, so many callers cost one request.
   */
  load(threadId: string | null = this.state.threadId, opts: { force?: boolean } = {}): Promise<void> {
    if (!threadId) return Promise.resolve();
    const running = this.inflight.get(threadId);
    if (running) return running;
    const before = this.entry(threadId);
    if (!opts.force && before.status === "ready") return Promise.resolve();
    this.setEntry(threadId, before.workbench ? { ...before, refreshing: true } : { ...before, status: "loading", refreshing: false });
    const p = this.api
      .getWorkbench(threadId)
      .then((res) => {
        const prev = this.entry(threadId);
        if (res.ok) this.setEntry(threadId, { status: "ready", workbench: res.data, error: null, refreshing: false, fixture: res.fixture, loadedAt: Date.now() });
        else this.setEntry(threadId, { ...prev, status: prev.workbench ? "ready" : "error", error: res, refreshing: false });
      })
      .finally(() => this.inflight.delete(threadId));
    this.inflight.set(threadId, p);
    return p;
  }

  /** Refetch the thread on screen. */
  refresh(): Promise<void> {
    return this.load(this.state.threadId, { force: true });
  }

  /** A chat run finished: count it, and refetch that thread if a tab has read it. */
  runFinished(threadId: string) {
    this.state = { ...this.state, runs: { ...this.state.runs, [threadId]: (this.state.runs[threadId] ?? 0) + 1 } };
    this.emit();
    if (this.state.entries[threadId]) void this.load(threadId, { force: true });
  }

  /**
   * Pick the design the one-design tabs show, or null for the default (the chosen one). Store
   * only; `select` on the hook goes through the route.
   */
  select(id: string | null, threadId: string | null = this.state.threadId) {
    if (!threadId || (this.state.picked[threadId] ?? null) === id) return;
    const { [threadId]: _old, ...rest } = this.state.picked;
    this.state = { ...this.state, picked: id === null ? rest : { ...rest, [threadId]: id } };
    this.emit();
  }

  /** The design shown on the one-design tabs (see pickDesign). */
  selected(threadId: string | null = this.state.threadId): Design | null {
    const wb = this.entry(threadId).workbench;
    return pickDesign(wb?.designs ?? [], threadId ? this.state.picked[threadId] : null, wb?.latest);
  }

  /** Change assumptions (null = back to the default); every design's economics is recomputed. */
  async setAssumptions(assumptions: AssumptionsPatch, threadId: string | null = this.state.threadId): Promise<ApiResult<Workbench>> {
    if (!threadId) return noThread();
    const res = await this.api.putAssumptions({ threadId, assumptions });
    if (res.ok) this.setEntry(threadId, { ...this.entry(threadId), status: "ready", workbench: res.data, error: null, fixture: res.fixture, loadedAt: Date.now() });
    return res;
  }

  /** Add a user design built from `base` with `changes`; it joins the conversation's designs. */
  async addDesign(base: string, changes: DesignChanges, name?: string, threadId: string | null = this.state.threadId): Promise<ApiResult<{ design: Design }>> {
    if (!threadId) return noThread();
    const res = await this.api.createDesign({ threadId, base, name, changes });
    const wb = this.entry(threadId).workbench;
    if (res.ok && wb) {
      const designs = [...wb.designs.filter((d) => d.id !== res.data.design.id), res.data.design];
      this.setEntry(threadId, { ...this.entry(threadId), workbench: { ...wb, designs } });
    }
    return res;
  }

  /**
   * Bring a design of any search into the tabs (a candidate from the Compare tab's library): it
   * joins the conversation's designs, so the picker lists it and Design/Economics can show it. A
   * design already there answers at once, without a request.
   */
  async openDesign(id: string, threadId: string | null = this.state.threadId): Promise<ApiResult<{ design: Design }>> {
    if (!threadId) return noThread();
    const have = this.entry(threadId).workbench?.designs.find((d) => d.id === id);
    if (have) return { ok: true, data: { design: have }, fixture: this.entry(threadId).fixture };
    const res = await this.api.openDesign({ threadId, id });
    const wb = this.entry(threadId).workbench;
    if (res.ok && wb) {
      const opened = res.data.design;
      const designs = [...wb.designs.filter((d) => d.id !== opened.id), opened];
      const library = wb.library?.map((r) => (r.id === opened.id ? { ...r, in_tabs: true } : r));
      this.setEntry(threadId, { ...this.entry(threadId), workbench: { ...wb, designs, ...(library ? { library } : {}) } });
    }
    return res;
  }

  /**
   * Give a design the user's own name ("" takes it away) or star it (the shortlist). The tabs
   * show it at once; the server's workbench then replaces the guess.
   */
  async setMeta(id: string, meta: { name?: string; starred?: boolean }, threadId: string | null = this.state.threadId): Promise<ApiResult<Workbench>> {
    if (!threadId) return noThread();
    const wb = this.entry(threadId).workbench;
    if (wb) {
      const apply = <T extends { id: string; user_name?: string | null; label?: string; starred?: boolean }>(d: T): T =>
        d.id !== id ? d : { ...d, ...(meta.name !== undefined ? { user_name: meta.name || null, label: meta.name || d.label } : {}), ...(meta.starred !== undefined ? { starred: meta.starred } : {}) };
      this.setEntry(threadId, { ...this.entry(threadId), workbench: { ...wb, designs: wb.designs.map(apply), ...(wb.library ? { library: wb.library.map(apply) } : {}) } });
    }
    const res = await this.api.setDesignMeta({ threadId, id, ...meta });
    if (res.ok) this.setEntry(threadId, { ...this.entry(threadId), status: "ready", workbench: res.data, error: null, fixture: res.fixture, loadedAt: Date.now() });
    else this.load(threadId);
    return res;
  }

  /** Delete a user design. */
  async removeDesign(id: string, threadId: string | null = this.state.threadId): Promise<ApiResult<{ ok: true }>> {
    if (!threadId) return noThread();
    const res = await this.api.deleteDesign(threadId, id);
    const wb = this.entry(threadId).workbench;
    if (res.ok && wb) {
      this.setEntry(threadId, { ...this.entry(threadId), workbench: { ...wb, designs: wb.designs.filter((d) => d.id !== id) } });
      if (this.state.picked[threadId] === id) this.select(null, threadId);
    }
    return res;
  }

  /** A chat was removed: forget its designs, its pick and its runs (a load on its way included). */
  forgetThread(threadId: string) {
    const drop = <T,>(rec: Record<string, T>) => Object.fromEntries(Object.entries(rec).filter(([id]) => id !== threadId));
    this.inflight.delete(threadId);
    this.state = { ...this.state, entries: drop(this.state.entries), picked: drop(this.state.picked), runs: drop(this.state.runs) };
    this.emit();
  }

  private setEntry(threadId: string, entry: WorkbenchEntry) {
    this.state = { ...this.state, entries: { ...this.state.entries, [threadId]: entry } };
    this.emit();
  }

  private emit() {
    for (const fn of this.listeners) fn();
  }
}

const noThread = (): ApiError => ({ ok: false, status: 0, message: "No conversation is open.", offline: false });

export const workbench = new WorkbenchStore();
chatStore.onRunFinished((threadId) => workbench.runFinished(threadId));

// ------------------------------------------------------------------ hooks

export interface WorkbenchView {
  threadId: string | null;
  status: WorkbenchStatus;
  workbench: Workbench | null;
  /** The conversation's designs ([] while loading or for a new chat). */
  designs: Design[];
  /** The design the one-design tabs show. */
  selected: Design | null;
  selectedId: string | null;
  error: ApiError | null;
  /** A refetch is on its way (the data on screen stays meanwhile). */
  refreshing: boolean;
  /** The data came from the fixture files. */
  fixture: boolean;
  /** Chat runs finished on this thread this visit: use it as a dependency to refetch per run. */
  runsFinished: number;
  refresh: () => Promise<void>;
  /** Show another design: on a one-design tab this changes the route (#energy/A2), so back works. */
  select: (id: string) => void;
  setAssumptions: (assumptions: AssumptionsPatch) => Promise<ApiResult<Workbench>>;
  addDesign: (base: string, changes: DesignChanges, name?: string) => Promise<ApiResult<{ design: Design }>>;
  removeDesign: (id: string) => Promise<ApiResult<{ ok: true }>>;
  /** Bring a design of any search into the tabs (see WorkbenchStore.openDesign). */
  openDesign: (id: string) => Promise<ApiResult<{ design: Design }>>;
  /** The user's own name for a design ("" takes it away), or its star (see WorkbenchStore.setMeta). */
  setMeta: (id: string, meta: { name?: string; starred?: boolean }) => Promise<ApiResult<Workbench>>;
}

/** Show another design; on a one-design tab via the route, else in the store. */
export function selectDesign(id: string) {
  const route = currentRoute();
  if (TAB_META[route.tab].scope === "design") go(route.tab, id);
  else workbench.select(id);
}

const actions = {
  refresh: () => workbench.refresh(),
  select: selectDesign,
  setAssumptions: (a: AssumptionsPatch) => workbench.setAssumptions(a),
  addDesign: (base: string, changes: DesignChanges, name?: string) => workbench.addDesign(base, changes, name),
  removeDesign: (id: string) => workbench.removeDesign(id),
  openDesign: (id: string) => workbench.openDesign(id),
  setMeta: (id: string, meta: { name?: string; starred?: boolean }) => workbench.setMeta(id, meta),
};

/** The workbench of the conversation on screen, with its state and actions. */
export function useWorkbench(): WorkbenchView {
  const s = useSyncExternalStore(workbench.subscribe, workbench.getSnapshot, workbench.getSnapshot);
  return useMemo(() => {
    const threadId = s.threadId;
    const e = (threadId && s.entries[threadId]) || IDLE;
    const designs = e.workbench?.designs ?? [];
    const selected = pickDesign(designs, threadId ? s.picked[threadId] : null, e.workbench?.latest);
    return {
      threadId,
      status: e.status,
      workbench: e.workbench,
      designs,
      selected,
      selectedId: selected?.id ?? null,
      error: e.error,
      refreshing: e.refreshing,
      fixture: e.fixture,
      runsFinished: (threadId && s.runs[threadId]) || 0,
      ...actions,
    };
  }, [s]);
}

/** The design the one-design tabs show (null while loading or with no designs). */
export function useSelectedDesign(): Design | null {
  return useWorkbench().selected;
}

/**
 * Keeps the store in step with the app (App.tsx calls it once): the thread on screen, the
 * design in the route (on a one-design tab, no id means the default, so back from #energy/A2 to
 * #energy shows the chosen design again), and a refetch each time a tab that reads designs opens.
 */
export function useWorkbenchSync(threadId: string, route: Route) {
  const reads = DESIGN_TABS.has(route.tab);
  const oneDesign = TAB_META[route.tab].scope === "design";
  useEffect(() => {
    workbench.setThread(threadId);
  }, [threadId]);
  useEffect(() => {
    // #compare/<ids>: the ticked designs, not one design to select (the Compare tab reads them).
    if (route.design && reads && route.tab !== "compare") workbench.select(route.design, threadId);
    else if (oneDesign) workbench.select(null, threadId);
  }, [reads, oneDesign, route.design, threadId]);
  useEffect(() => {
    if (reads) void workbench.load(threadId, { force: true });
  }, [reads, route.tab, threadId]);
}
