// Hash routes: #chat (default), #design, #energy, #economics, #compare, #sensitivity, #trace,
// #evidence, with an optional design id after a slash (#design/A1, #energy/A1%20%E2%88%9210%20%C2%B0C).
// Hash routes keep the server's single index.html and make back/forward work for free.

import { useSyncExternalStore } from "react";

export const TABS = ["chat", "design", "energy", "economics", "compare", "sensitivity", "trace", "evidence"] as const;
export type TabId = (typeof TABS)[number];

/** What a tab reads: the conversation, one design (the picker's), all designs, or how we know. */
export type TabScope = "talk" | "design" | "designs" | "evidence";

export interface TabMeta {
  id: TabId;
  label: string;
  scope: TabScope;
  /** Shown on hover: what the tab is about. */
  hint: string;
}

export const TAB_META: Record<TabId, TabMeta> = {
  chat: { id: "chat", label: "Chat", scope: "talk", hint: "The conversation" },
  design: { id: "design", label: "Design", scope: "design", hint: "The plant of the design in the picker" },
  energy: { id: "energy", label: "Energy", scope: "design", hint: "Heat and cold over the year, for the design in the picker" },
  economics: { id: "economics", label: "Economics", scope: "design", hint: "Costs, CO₂ and cash flow, for the design in the picker" },
  compare: { id: "compare", label: "Compare", scope: "designs", hint: "All the conversation's designs side by side" },
  sensitivity: { id: "sensitivity", label: "Sensitivity", scope: "designs", hint: "What drives the result, across the designs" },
  trace: { id: "trace", label: "Trace", scope: "evidence", hint: "How each answer was computed: steps, model calls, tools" },
  evidence: { id: "evidence", label: "Evidence", scope: "evidence", hint: "Tests, benchmarks and GEMINI's fixes" },
};

/** The header's groups, in order, with a thin divider between them. */
export const TAB_GROUPS: { caption: string; tabs: TabId[] }[] = [
  { caption: "Talk", tabs: ["chat"] },
  { caption: "One design", tabs: ["design", "energy", "economics"] },
  { caption: "All designs", tabs: ["compare", "sensitivity"] },
  { caption: "How we know", tabs: ["trace", "evidence"] },
];

/** Tabs that read the conversation's designs (the workbench refetches when one opens). */
export const DESIGN_TABS: ReadonlySet<TabId> = new Set(TABS.filter((t) => TAB_META[t].scope === "design" || TAB_META[t].scope === "designs"));

export interface Route {
  tab: TabId;
  /** A design id from the URL (decoded), or null. */
  design: string | null;
}

const isTab = (s: string): s is TabId => (TABS as readonly string[]).includes(s);

/** "#design/A1%20%E2%88%9210%20%C2%B0C" → { tab: "design", design: "A1 −10 °C" }. Unknown → chat. */
export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, "");
  const cut = raw.indexOf("/");
  const head = (cut < 0 ? raw : raw.slice(0, cut)).trim().toLowerCase();
  const rest = cut < 0 ? "" : raw.slice(cut + 1).replace(/\/+$/, "");
  if (!isTab(head)) return { tab: "chat", design: null };
  if (head === "chat" || !rest) return { tab: head, design: null };
  let design = rest;
  try {
    design = decodeURIComponent(rest);
  } catch {
    /* a malformed escape: keep it as written */
  }
  return { tab: head, design: design.trim() || null };
}

/** { tab: "design", design: "A1 −10 °C" } → "#design/A1%20%E2%88%9210%20%C2%B0C". */
export function formatHash(route: { tab: TabId; design?: string | null }): string {
  if (route.tab === "chat" || !route.design) return `#${route.tab}`;
  return `#${route.tab}/${encodeURIComponent(route.design)}`;
}

/** The href of a tab, for links (middle-click and "open in a new tab" work). */
export function hrefFor(tab: TabId, design?: string | null): string {
  return formatHash({ tab, design });
}

// ------------------------------------------------------------------ the live route

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((fn) => fn());
let watching = false;

function subscribe(fn: () => void): () => void {
  if (!watching && typeof window !== "undefined") {
    window.addEventListener("hashchange", emit);
    window.addEventListener("popstate", emit);
    watching = true;
  }
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const currentHash = () => (typeof window === "undefined" ? "" : window.location.hash);

let lastHash: string | null = null;
let lastRoute: Route = { tab: "chat", design: null };
/** The current route (a stable object while the hash doesn't change). */
export function currentRoute(): Route {
  const h = currentHash();
  if (h !== lastHash) {
    lastHash = h;
    lastRoute = parseHash(h);
  }
  return lastRoute;
}

/** The current route; re-renders on every hash change (links, back, forward, go()). */
export function useRoute(): Route {
  return useSyncExternalStore(subscribe, currentRoute, currentRoute);
}

/**
 * Go to a tab (and design). Pushes a history entry, so back returns; `replace` swaps the
 * current entry instead (e.g. correcting a stale design id).
 */
export function go(tab: TabId, design?: string | null, opts: { replace?: boolean } = {}): void {
  if (typeof window === "undefined") return;
  const hash = formatHash({ tab, design });
  if (window.location.hash === hash) return;
  if (opts.replace) {
    const url = `${window.location.pathname}${window.location.search}${hash}`;
    window.history.replaceState(window.history.state, "", url);
    emit();
  } else {
    window.location.hash = hash;
  }
}
