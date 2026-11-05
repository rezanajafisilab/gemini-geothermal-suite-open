// The app's own actions behind the menus' items (MenuOps): routes and links (workbench/route.ts,
// tabs/compare/link.ts), "Ask about this" (workbench/ask.ts), the workbench store's openDesign
// for a design not yet in the tabs, the PDF report the Design tab downloads, the Compare tray.
// A design is named however the place knows it ("A1", its code, its tabs' id); find() turns that
// into the tabs' id with the conversation's designs and its library.

import { store as chatStore } from "../state/store";
import { ID_SEPARATOR } from "../tabs/compare/link";
import { trayIds } from "../tabs/compare/tray";
import { remember } from "../tabs/design/remember";
import { usesFixtures } from "../workbench/api";
import { askInChat } from "../workbench/ask";
import { previewExport } from "../workbench/exports";
import { currentRoute, go, hrefFor, type TabId } from "../workbench/route";
import { workbench } from "../workbench/store";
import { deviceState, requestDevice } from "./device";
import { editText } from "./fields";
import { setIntent } from "./intent";
import { openNameBox } from "./namebox";
import { lastMenuRun, openQuickAsk } from "./quickask";
import { showToast } from "./store";
import type { MenuOps } from "./types";

const norm = (s: string | null | undefined) => (s ?? "").replace(/−/g, "-").replace(/\s+/g, " ").trim().toLowerCase();

/** A design by any name: its tabs' id, and whether it is in the tabs yet (else open it first). */
export function find(ref: string): { id: string; inTabs: boolean } | null {
  const wb = workbench.entry().workbench;
  if (!wb) return null;
  const n = norm(ref);
  const d =
    wb.designs.find((x) => norm(x.id) === n) ??
    wb.designs.find((x) => norm(x.uid) === n) ??
    wb.designs.filter((x) => norm(x.code) === n).sort((a, b) => Number(b.chosen) - Number(a.chosen) || Number(a.origin === "what_if") - Number(b.origin === "what_if"))[0];
  if (d) return { id: d.id, inTabs: true };
  const lib = wb.library ?? [];
  const r =
    lib.find((x) => norm(x.id) === n) ??
    lib.find((x) => norm(x.uid) === n) ??
    lib.filter((x) => norm(x.code) === n).sort((a, b) => Number(b.recommended) - Number(a.recommended) || Number(b.in_tabs) - Number(a.in_tabs))[0];
  return r ? { id: r.id, inTabs: r.in_tabs } : null;
}

/** The tabs' id of a design, opened into the tabs first when it isn't there (null: it couldn't be). */
async function ready(ref: string): Promise<string | null> {
  await workbench.load();
  const hit = find(ref);
  if (!hit) return ref;
  if (hit.inTabs) return hit.id;
  showToast(`Opening ${ref}…`);
  const res = await workbench.openDesign(hit.id);
  if (res.ok) return res.data.design.id;
  showToast(`Couldn't open ${ref}: ${res.message}`, "bad");
  return null;
}

const threadId = () => workbench.getSnapshot().threadId;

/** Copy text: the async clipboard, else a hidden textarea (an http page on another host). */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* blocked: try the old way */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch {
    return false;
  }
}

export const appOps: MenuOps = {
  // On the chat the question goes into the composer; on a tab, into the quick-ask box there.
  ask: (text) => {
    if (currentRoute().tab === "chat") return askInChat(text);
    const run = lastMenuRun();
    openQuickAsk(text, run.about, run.at);
  },
  openDesign: async (ref, tab) => {
    const id = await ready(ref);
    if (id) go(tab, id);
  },
  compare: (refs) => go("compare", refs.join(ID_SEPARATOR)),
  addToTray: (ref) => {
    const id = find(ref)?.id ?? ref;
    const ticked = trayIds(threadId());
    if (ticked.some((x) => norm(x) === norm(id))) {
      showToast(`${ref} is in the Compare tray already`);
      return go("compare", ticked.join(ID_SEPARATOR));
    }
    if (ticked.length >= 4) {
      showToast("Four designs are ticked: untick one first", "bad");
      return go("compare", ticked.join(ID_SEPARATOR));
    }
    go("compare", [...ticked, id].join(ID_SEPARATOR));
    showToast(`${ref} added to the Compare tray`);
  },
  recommended: () => {
    const wb = workbench.entry().workbench;
    if (!wb) return null;
    return wb.designs.find((d) => d.chosen)?.id ?? wb.library?.find((r) => r.recommended)?.id ?? null;
  },
  same: (a, b) => {
    if (norm(a) === norm(b)) return true;
    const x = find(a)?.id;
    return !!x && x === find(b)?.id;
  },
  canReport: () => {
    const t = threadId();
    return !usesFixtures() && !!t && !t.startsWith("replay-");
  },
  downloadReport: async (ref) => {
    const t = threadId();
    const id = await ready(ref);
    if (t && id) previewExport("report", t, id);
  },
  downloadPermits: async (ref) => {
    const t = threadId();
    const id = await ready(ref);
    if (t && id) previewExport("permits", t, id);
  },
  downloadGemini: async (ref) => {
    const t = threadId();
    const id = await ready(ref);
    if (t && id) previewExport("gemini", t, id);
  },
  linkFor: (tab: TabId, ref) => {
    const id = ref ? (find(ref)?.id ?? ref) : null;
    return `${window.location.origin}${window.location.pathname}${window.location.search}${hrefFor(tab, id)}`;
  },
  copy: async (text, what) => {
    const ok = await copyText(text);
    showToast(ok ? `${what} copied` : "Couldn't copy: the browser blocked the clipboard", ok ? "ok" : "bad");
  },
  jumpToDay: async (ref, day) => {
    const id = await ready(ref);
    if (!id) return;
    const scope = `${threadId()}/${id}`;
    remember(scope, "day", Math.max(1, Math.min(365, Math.round(day))));
    remember("*", "view", "plant");
    go("design", id);
  },
  showEnergy: async (ref, side, series) => {
    const id = await ready(ref);
    if (!id) return;
    setIntent("energy", { side, series });
    go("energy", id);
  },
  showCosts: async (ref, items) => {
    const id = await ready(ref);
    if (!id) return;
    setIntent("economics", { highlight: items });
    go("economics", id);
  },
  vary: async (param, ref) => {
    const id = ref ? await ready(ref) : null;
    setIntent("sensitivity", { param });
    go("sensitivity");
    if (id) workbench.select(id);
  },
  device: () => deviceState(),
  setDevice: (d) => {
    requestDevice(d);
    // The next send reads the store's device before the header's switch re-renders.
    chatStore.device = d;
  },
  meta: (ref) => {
    const wb = workbench.entry().workbench;
    if (!wb) return null;
    const id = find(ref)?.id ?? ref;
    const d = wb.designs.find((x) => x.id === id) ?? wb.library?.find((x) => x.id === id);
    return d ? { starred: !!d.starred, name: d.user_name ?? null } : null;
  },
  star: async (ref, on) => {
    const id = find(ref)?.id ?? ref;
    const res = await workbench.setMeta(id, { starred: on });
    showToast(res.ok ? (on ? `${ref.split(" · ")[0]} is on your shortlist` : `${ref.split(" · ")[0]} is off your shortlist`) : `Couldn't change it: ${res.message}`, res.ok ? "ok" : "bad");
  },
  rename: (ref, current) => openNameBox(find(ref)?.id ?? ref, current, lastMenuRun().at),
  editText: (t, action) => editText(t, action),
  openLink: (href, newTab) => {
    if (newTab) window.open(href, "_blank", "noopener");
    else window.location.assign(href);
  },
};
