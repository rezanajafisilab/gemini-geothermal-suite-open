// Removing a chat removes all of it: the server is asked first (DELETE /api/threads/{id}: its
// run, session, uploads and trace), then this browser's copy, its files and its saved copy go.
// When the server can't be reached nothing is removed. A project's removal does the same for
// each of its chats.

import { afterEach, describe, expect, it, vi } from "vitest";

import type { Transport } from "../agent/client";
import { emptyChat } from "../agent/reducer";
import type { AgEvent } from "../agent/types";
import { WorkbenchStore } from "../workbench/store";
import { ChatStore } from "./store";

const KEY = "dioscuri.v2";
const meta = (id: string, extra: object = {}) => ({ threadId: id, title: `Chat ${id}`, createdAt: 1, updatedAt: 1, ...extra });

/** localStorage as a map, with a chat saved in it per id (index, chat and files). */
function storage(chats: Record<string, string[]>): Storage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  const index = Object.fromEntries(Object.entries(chats).map(([pid, ids]) => [pid, ids.map((id) => meta(id))]));
  data.set(`${KEY}.index`, JSON.stringify(index));
  data.set(`${KEY}.files`, JSON.stringify(Object.fromEntries(Object.values(chats).flat().map((id) => [id, [{ name: "notes.md", status: "ready" }]]))));
  for (const id of Object.values(chats).flat()) data.set(`${KEY}.chat.${id}`, JSON.stringify(emptyChat(id)));
  return {
    data,
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    key: (i: number) => [...data.keys()][i] ?? null,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

/** A server that records each request and answers DELETE /api/threads/{id} (or can't be reached). */
function server(opts: { down?: boolean } = {}) {
  const calls: { method: string; url: string }[] = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    calls.push({ method: init?.method ?? "GET", url });
    if (opts.down) throw new TypeError("Failed to fetch");
    const threadId = decodeURIComponent(url.split("/").pop() ?? "");
    return { ok: true, status: 200, statusText: "OK", json: async () => ({ ok: true, threadId, stopped: 0, removed: [`${threadId}.json`] }) } as unknown as Response;
  });
  return calls;
}

const saved = () => new Promise((r) => setTimeout(r, 350)); // the store saves 300 ms after a change

afterEach(() => vi.unstubAllGlobals());

describe("removing a chat", () => {
  it("asks the server to remove it, then drops the chat, its files and its saved copy here", async () => {
    const calls = server();
    const s = storage({ challenge: ["a", "b"] });
    const store = new ChatStore(s);
    await store.removeChat("challenge", "a");
    expect(calls).toEqual([{ method: "DELETE", url: "/api/threads/a" }]);
    const state = store.getSnapshot();
    expect(state.index.challenge.map((m) => m.threadId)).toEqual(["b"]);
    expect(state.chats.a).toBeUndefined();
    expect(state.files.a).toBeUndefined();
    expect(s.data.has(`${KEY}.chat.a`)).toBe(false);
    await saved();
    expect(JSON.parse(s.data.get(`${KEY}.index`)!).challenge.map((m: { threadId: string }) => m.threadId)).toEqual(["b"]);
    expect(Object.keys(JSON.parse(s.data.get(`${KEY}.files`)!))).toEqual(["b"]);
    // The other chat is untouched.
    expect(state.chats.b).toBeDefined();
    expect(s.data.has(`${KEY}.chat.b`)).toBe(true);
  });

  it("keeps everything when the server can't be reached, and says why", async () => {
    server({ down: true });
    const s = storage({ challenge: ["a"] });
    const store = new ChatStore(s);
    await expect(store.removeChat("challenge", "a")).rejects.toThrow("Couldn't reach the agent server.");
    expect(store.getSnapshot().index.challenge.map((m) => m.threadId)).toEqual(["a"]);
    expect(store.getSnapshot().chats.a).toBeDefined();
    expect(store.getSnapshot().files.a).toHaveLength(1);
    expect(s.data.has(`${KEY}.chat.a`)).toBe(true);
  });

  it("does not ask the server about a replayed scene, which never reached it", async () => {
    const calls = server();
    const store = new ChatStore(null);
    store.addChat("challenge", meta("replay-design-x", { replay: true }));
    await store.removeChat("challenge", "replay-design-x");
    expect(calls).toEqual([]);
    expect(store.getSnapshot().index.challenge).toEqual([]);
  });

  it("waits for an upload on its way, so no file lands on the server after the removal", async () => {
    const calls: string[] = [];
    let finish: () => void = () => {};
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/attachments") {
        await new Promise<void>((resolve) => (finish = resolve));
        calls.push("upload done");
        return { ok: true, status: 200, json: async () => ({ threadId: "a", name: "notes.md", chunks: 1 }) } as unknown as Response;
      }
      return { ok: true, status: 200, json: async () => ({ ok: true, threadId: "a", stopped: 0, removed: [] }) } as unknown as Response;
    });
    const store = new ChatStore(null);
    store.addChat("challenge", meta("a"));
    const upload = store.attach("a", [new File(["# notes"], "notes.md")]);
    await new Promise((r) => setTimeout(r, 0));
    const removal = store.removeChat("challenge", "a");
    await new Promise((r) => setTimeout(r, 0));
    expect(calls).toEqual(["POST /api/attachments"]);
    finish();
    await removal;
    await upload;
    expect(calls).toEqual(["POST /api/attachments", "upload done", "DELETE /api/threads/a"]);
    expect(store.getSnapshot().files.a).toBeUndefined();
  });

  it("stops a run going on, and its last events don't bring the chat back", async () => {
    server();
    const store = new ChatStore(null);
    store.pace = false;
    let release: () => void = () => {};
    const transport: Transport = async function* (_body, signal) {
      yield { type: "RUN_STARTED", threadId: "a", runId: "r1" } as AgEvent;
      await new Promise<void>((resolve) => {
        release = resolve;
        signal.addEventListener("abort", () => resolve());
      });
      yield { type: "RUN_FINISHED", threadId: "a", runId: "r1", outcome: { type: "success" } } as AgEvent;
    };
    store.setTransport("a", transport);
    const sent = store.send("challenge", "a", "Design heating and cooling for the district");
    await new Promise((r) => setTimeout(r, 0));
    expect(store.isRunning("a")).toBe(true);
    await store.removeChat("challenge", "a");
    release();
    await sent;
    expect(store.isRunning("a")).toBe(false);
    expect(store.getSnapshot().chats.a).toBeUndefined();
    expect(store.getSnapshot().index.challenge).toEqual([]);
  });
});

describe("removing a project", () => {
  it("drops its chats here and asks the server to remove each; other projects' chats stay", async () => {
    const calls = server();
    const s = storage({ campus: ["c1", "c2"], challenge: ["a"] });
    const store = new ChatStore(s);
    await store.removeProject("campus");
    expect(calls.map((c) => `${c.method} ${c.url}`).sort()).toEqual(["DELETE /api/threads/c1", "DELETE /api/threads/c2"]);
    const state = store.getSnapshot();
    expect(state.index.campus).toBeUndefined();
    expect(Object.keys(state.chats)).toEqual(["a"]);
    expect(Object.keys(state.files)).toEqual(["a"]);
    expect([...s.data.keys()].filter((k) => k.startsWith(`${KEY}.chat.`))).toEqual([`${KEY}.chat.a`]);
  });

  it("goes here even when the server can't be reached (the project itself was removed there)", async () => {
    server({ down: true });
    const store = new ChatStore(storage({ campus: ["c1"] }));
    await store.removeProject("campus");
    expect(store.getSnapshot().index.campus).toBeUndefined();
    expect(store.getSnapshot().chats.c1).toBeUndefined();
  });
});

describe("the tabs forget a removed chat", () => {
  it("drops its designs, its pick and its runs; other chats keep theirs", async () => {
    const wb = { designs: [{ id: "A1", code: "1D", chosen: true }], latest: null };
    const api = { getWorkbench: async () => ({ ok: true, data: wb, fixture: false }) } as unknown as ConstructorParameters<typeof WorkbenchStore>[0];
    const tabs = new WorkbenchStore(api);
    await tabs.load("a");
    await tabs.load("b");
    tabs.select("A1", "a");
    tabs.runFinished("a");
    tabs.forgetThread("a");
    const state = tabs.getSnapshot();
    expect(Object.keys(state.entries)).toEqual(["b"]);
    expect(state.picked.a).toBeUndefined();
    expect(state.runs.a).toBeUndefined();
    expect(tabs.entry("a").workbench).toBeNull();
  });
});
