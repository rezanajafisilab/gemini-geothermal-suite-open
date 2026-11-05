// Attachments in the store: a file waits in the composer until a message takes it, the message
// keeps it (and the server's passage count), a message sent mid-upload waits for the upload, a
// failed upload goes back to the composer, and all of it survives a reload.

import { afterEach, describe, expect, it, vi } from "vitest";

import type { RunBody, Transport } from "../agent/client";
import type { AgEvent } from "../agent/types";
import { pendingFiles } from "./attachments";
import { ChatStore } from "./store";

const LIMITS = { types: [".md", ".pdf", ".png"], max_mb: 10 };

/** A server whose uploads answer when the test says so (or at once, by default). */
function fakeServer(chunks: Record<string, number> = {}) {
  const waiting = new Map<string, { resolve: (r: Response) => void }>();
  const answer = (body: unknown, ok = true, status = 200): Response =>
    ({ ok, status, statusText: ok ? "OK" : "error", json: async () => body }) as unknown as Response;
  const hold = new Set<string>();
  vi.stubGlobal("fetch", async (_url: string, init?: RequestInit) => {
    const form = init?.body as FormData;
    const file = form.get("file") as File;
    const threadId = String(form.get("threadId"));
    const reply = answer({ threadId, name: file.name, chunks: chunks[file.name] ?? 1 });
    if (!hold.has(file.name)) return reply;
    return new Promise<Response>((resolve) => waiting.set(file.name, { resolve }));
  });
  return {
    hold: (name: string) => hold.add(name),
    finish: (name: string) => waiting.get(name)!.resolve(answer({ threadId: "t", name, chunks: chunks[name] ?? 1 })),
    fail: (name: string) => waiting.get(name)!.resolve(answer({ detail: "can't read this PDF" }, false, 415)),
  };
}

function storeWith(bodies: RunBody[]): ChatStore {
  const transport: Transport = async function* (body) {
    bodies.push(body);
    const events: AgEvent[] = [
      { type: "RUN_STARTED", threadId: "t", runId: `r${bodies.length}` },
      { type: "RUN_FINISHED", threadId: "t", runId: `r${bodies.length}`, outcome: { type: "success" } },
    ];
    yield* events;
  };
  const store = new ChatStore(null);
  store.pace = false;
  store.setTransport("t", transport);
  return store;
}

const tick = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => vi.unstubAllGlobals());

describe("files go with the next message", () => {
  it("the composer holds them until a message takes them; the message keeps name, kind and passages", async () => {
    fakeServer({ "notes.md": 3, "map.png": 0 });
    const bodies: RunBody[] = [];
    const store = storeWith(bodies);
    await store.attach("t", [new File(["# notes"], "notes.md"), new File(["png"], "map.png")], LIMITS, "p");
    expect(pendingFiles(store.getSnapshot().files.t).map((f) => f.name).sort()).toEqual(["map.png", "notes.md"]);

    await store.send("p", "t", "Summarise the notes");
    const [first] = store.chat("t").turns;
    expect(first.attachments).toEqual([
      { name: "notes.md", kind: "text", chunks: 3 },
      { name: "map.png", kind: "image" },
    ]);
    // The chips are gone from the composer; the files stay on the thread, marked with their message.
    expect(pendingFiles(store.getSnapshot().files.t)).toEqual([]);
    expect(store.getSnapshot().files.t.map((f) => f.sentIn)).toEqual([first.id, first.id]);

    await store.send("p", "t", "And the costs?");
    expect("attachments" in store.chat("t").turns[1]).toBe(false);
    expect(bodies).toHaveLength(2);
  });

  it("a file still uploading goes with the message, and the run waits for it", async () => {
    const server = fakeServer({ "brief.pdf": 12 });
    server.hold("brief.pdf");
    const bodies: RunBody[] = [];
    const store = storeWith(bodies);
    const upload = store.attach("t", [new File(["pdf"], "brief.pdf")], LIMITS, "p");
    const sending = store.send("p", "t", "Read the brief");
    await tick();
    // Sent at once, shown as uploading; no second message can slip in; nothing sent to the agent yet.
    const turn = store.chat("t").turns[0];
    expect(turn.attachments).toEqual([{ name: "brief.pdf", kind: "text", uploading: true }]);
    expect(turn.status).toBe("running");
    expect(store.isRunning("t")).toBe(true);
    expect(bodies).toHaveLength(0);
    expect(pendingFiles(store.getSnapshot().files.t)).toEqual([]);

    server.finish("brief.pdf");
    await upload;
    await sending;
    expect(store.chat("t").turns[0].attachments).toEqual([{ name: "brief.pdf", kind: "text", chunks: 12 }]);
    expect(store.getSnapshot().files.t[0]).toMatchObject({ status: "ready", chunks: 12, sentIn: turn.id });
    expect(bodies).toHaveLength(1);
    expect(store.chat("t").turns[0].status).toBe("done");
  });

  it("an upload that fails after the message went goes back to the composer; the message shows no file", async () => {
    const server = fakeServer();
    server.hold("scan.pdf");
    const bodies: RunBody[] = [];
    const store = storeWith(bodies);
    const upload = store.attach("t", [new File(["pdf"], "scan.pdf")], LIMITS, "p");
    const sending = store.send("p", "t", "What does the scan say?");
    await tick();
    server.fail("scan.pdf");
    await upload;
    await sending;
    expect("attachments" in store.chat("t").turns[0]).toBe(false);
    expect(pendingFiles(store.getSnapshot().files.t)).toEqual([{ name: "scan.pdf", status: "failed", error: "can't read it: can't read this PDF" }]);
    // The message itself still went.
    expect(bodies).toHaveLength(1);
  });

  it("stopping while the file uploads sends nothing", async () => {
    const server = fakeServer();
    server.hold("brief.pdf");
    const bodies: RunBody[] = [];
    const store = storeWith(bodies);
    const upload = store.attach("t", [new File(["pdf"], "brief.pdf")], LIMITS, "p");
    const sending = store.send("p", "t", "Read the brief");
    await tick();
    store.stop("t");
    server.finish("brief.pdf");
    await upload;
    await sending;
    expect(bodies).toHaveLength(0);
    expect(store.chat("t").turns[0].status).toBe("stopped");
    expect(store.isRunning("t")).toBe(false);
  });

  it("a failed file is never sent, and keeps its dismiss button in the composer", async () => {
    fakeServer();
    const bodies: RunBody[] = [];
    const store = storeWith(bodies);
    await store.attach("t", [new File(["x"], "huge.exe")], LIMITS, "p");
    await store.send("p", "t", "Hello");
    expect("attachments" in store.chat("t").turns[0]).toBe(false);
    expect(pendingFiles(store.getSnapshot().files.t).map((f) => f.status)).toEqual(["failed"]);
    store.dismissFile("t", "huge.exe");
    expect(store.getSnapshot().files.t).toEqual([]);
  });

  it("which message a file went with survives a reload", async () => {
    fakeServer({ "notes.md": 3 });
    const saved = new Map<string, string>();
    const storage = {
      getItem: (k: string) => saved.get(k) ?? null,
      setItem: (k: string, v: string) => void saved.set(k, v),
      removeItem: (k: string) => void saved.delete(k),
    } as unknown as Storage;
    const bodies: RunBody[] = [];
    const store = new ChatStore(storage);
    store.pace = false;
    store.setTransport("t", async function* (body) {
      bodies.push(body);
      yield { type: "RUN_STARTED", threadId: "t", runId: "r" } as AgEvent;
      yield { type: "RUN_FINISHED", threadId: "t", runId: "r", outcome: { type: "success" } } as AgEvent;
    });
    await store.attach("t", [new File(["# notes"], "notes.md")], LIMITS, "p");
    await store.send("p", "t", "Summarise the notes");
    await new Promise((r) => setTimeout(r, 350));

    const again = new ChatStore(storage);
    const turn = again.chat("t").turns[0];
    expect(turn.attachments).toEqual([{ name: "notes.md", kind: "text", chunks: 3 }]);
    expect(again.getSnapshot().files.t).toEqual([{ name: "notes.md", status: "ready", chunks: 3, sentIn: turn.id }]);
    expect(pendingFiles(again.getSnapshot().files.t)).toEqual([]);
  });
});
