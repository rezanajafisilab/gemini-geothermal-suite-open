// Every chat of every project, and the runs that feed them. A run keeps streaming into its own
// chat while you look at another one, so the sidebar's status is always live.
// Chats are kept in localStorage per project; the server keeps each chat's session, uploads and
// trace, and removing a chat removes them there too (DELETE /api/threads/{id}).

import { useSyncExternalStore } from "react";

import { HttpError, deleteThread, fetchThread, liveTransport, paced, uploadAttachment, type Device, type Size, type RunBody, type Transport } from "../agent/client";
import { emptyChat, reduce } from "../agent/reducer";
import type { Action, ChatState } from "../agent/types";
import { isImage, pendingFiles, toTurnAttachment, type Attachment } from "./attachments";

/** Sent on `window` when a run says what the project remembers changed (CUSTOM "memory"). */
export const MEMORY_EVENT = "dioscuri:memory";

export type { Attachment } from "./attachments";

export interface ChatMeta {
  threadId: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  /** A fixture replay: shown, never saved. */
  replay?: boolean;
  /** A replayed scene's recorded mode; live runs let the agent decide per message. */
  reasoning?: boolean;
}

function thumbnail(file: File): string | undefined {
  if (!isImage(file.name) || typeof URL === "undefined" || !URL.createObjectURL) return undefined;
  try {
    return URL.createObjectURL(file);
  } catch {
    return undefined;
  }
}

export interface StoreState {
  index: Record<string, ChatMeta[]>;
  chats: Record<string, ChatState>;
  /** Attachments per thread (a new chat's thread has them before its first message). */
  files: Record<string, Attachment[]>;
}

// v2 (30 Oct 2026): the challenge engine. Chats saved by v1 ran on the toy model and are no
// longer shown (their keys stay in the browser, untouched).
const KEY = "dioscuri.v2";

export function newThreadId(): string {
  const raw =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().replace(/-/g, "")
      : Math.random().toString(16).slice(2) + Date.now().toString(16);
  return raw.slice(0, 12);
}

function safeStorage(): Storage | null {
  try {
    const s = window.localStorage;
    s.getItem(KEY);
    return s;
  } catch {
    return null;
  }
}

function load(storage: Storage | null): StoreState {
  const state: StoreState = { index: {}, chats: {}, files: {} };
  if (!storage) return state;
  try {
    state.index = JSON.parse(storage.getItem(`${KEY}.index`) || "{}");
    state.files = JSON.parse(storage.getItem(`${KEY}.files`) || "{}");
    for (const metas of Object.values(state.index)) {
      for (const m of metas) {
        const raw = storage.getItem(`${KEY}.chat.${m.threadId}`);
        if (!raw) continue;
        const chat = JSON.parse(raw) as ChatState;
        // A run cut short by a reload can't resume: its stream is gone.
        chat.turns = chat.turns.map((t) =>
          t.status === "running"
            ? { ...t, status: "stopped", steps: t.steps.map((s) => (s.status === "active" ? { ...s, status: "stopped" } : s)) }
            : t,
        );
        state.chats[m.threadId] = chat;
      }
    }
  } catch {
    return { index: {}, chats: {}, files: {} };
  }
  return state;
}

export class ChatStore {
  private state: StoreState;
  private listeners = new Set<() => void>();
  private runListeners = new Set<(threadId: string) => void>();
  private controllers = new Map<string, AbortController>();
  /** Uploads still in flight, per thread: a message sent meanwhile waits for them. */
  private uploads = new Map<string, Set<Promise<void>>>();
  private transports = new Map<string, Transport>();
  private dirty = new Set<string>();
  /** Chats removed this visit: a run still winding down writes nothing back into them. */
  private removed = new Set<string>();
  private saveTimer: ReturnType<typeof setTimeout> | null = null;
  private storage: Storage | null;
  pace = true;
  /** The device picked in the header, sent with every run (messages and answers). */
  device: Device = "auto";
  /** The model picked in the header (auto: the first that fits), sent with every run. */
  size: Size = "auto";

  constructor(storage: Storage | null = safeStorage()) {
    this.storage = storage;
    this.state = load(storage);
  }

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = () => this.state;

  /** Called with the thread id each time a run on it finishes (RUN_FINISHED): the tabs refetch. */
  onRunFinished(fn: (threadId: string) => void): () => void {
    this.runListeners.add(fn);
    return () => this.runListeners.delete(fn);
  }

  chat(threadId: string): ChatState {
    return this.state.chats[threadId] ?? emptyChat(threadId);
  }

  isRunning(threadId: string): boolean {
    return this.controllers.has(threadId);
  }

  /** Use a different event source for one chat (fixture replay). */
  setTransport(threadId: string, transport: Transport) {
    this.transports.set(threadId, transport);
  }

  addChat(projectId: string, meta: ChatMeta) {
    const list = this.state.index[projectId] ?? [];
    if (list.some((m) => m.threadId === meta.threadId)) return;
    this.state = {
      ...this.state,
      index: { ...this.state.index, [projectId]: [meta, ...list] },
      chats: { ...this.state.chats, [meta.threadId]: emptyChat(meta.threadId) },
    };
    this.dirty.add("index");
    this.emit();
  }

  meta(threadId: string): ChatMeta | undefined {
    for (const metas of Object.values(this.state.index)) {
      const m = metas.find((x) => x.threadId === threadId);
      if (m) return m;
    }
    return undefined;
  }

  /** Give a chat another name (empty keeps the old one). */
  renameChat(projectId: string, threadId: string, title: string) {
    const t = title.replace(/\s+/g, " ").trim().slice(0, 90);
    const list = this.state.index[projectId] ?? [];
    if (!t || !list.some((m) => m.threadId === threadId && m.title !== t)) return;
    this.state = { ...this.state, index: { ...this.state.index, [projectId]: list.map((m) => (m.threadId === threadId ? { ...m, title: t } : m)) } };
    this.dirty.add("index");
    this.emit();
  }

  /** A replayed scene: it never reached the server, so only its copy here goes. */
  private isReplay(threadId: string): boolean {
    return threadId.startsWith("replay-") || !!this.meta(threadId)?.replay;
  }

  /**
   * Remove a chat with all of it: the server stops its run and removes its session, uploads and
   * trace (its designs and runs), then this browser's copy goes. Uploads on their way finish
   * first, so none lands after the removal. When the server can't be reached or refuses, this
   * throws and the chat stays as it was, so nothing is left behind there.
   */
  async removeChat(projectId: string, threadId: string): Promise<void> {
    await Promise.allSettled([...(this.uploads.get(threadId) ?? [])]);
    if (!this.isReplay(threadId)) await deleteThread(threadId);
    this.forget([threadId]);
    this.state = {
      ...this.state,
      index: { ...this.state.index, [projectId]: (this.state.index[projectId] ?? []).filter((m) => m.threadId !== threadId) },
    };
    this.emit();
  }

  /**
   * Forget a removed project's chats: their runs stop and their copies here go. The server has
   * removed the ones it knows with the project; each is removed there by its id too, for a run
   * cut short before its chat was saved. Resolves when the server has answered for each.
   */
  async removeProject(projectId: string): Promise<void> {
    const ids = (this.state.index[projectId] ?? []).map((m) => m.threadId);
    const online = ids.filter((id) => !this.isReplay(id));
    this.forget(ids);
    const { [projectId]: _index, ...index } = this.state.index;
    this.state = { ...this.state, index };
    this.emit();
    await Promise.allSettled(online.map((id) => deleteThread(id)));
  }

  /** Drop chats from this browser: their runs stop, their copies, files and previews go. */
  private forget(ids: string[]) {
    const gone = new Set(ids);
    for (const id of gone) {
      this.removed.add(id);
      this.stop(id);
      for (const f of this.state.files[id] ?? []) if (f.preview) URL.revokeObjectURL(f.preview);
      this.storage?.removeItem(`${KEY}.chat.${id}`);
      this.dirty.delete(id);
    }
    const chats = Object.fromEntries(Object.entries(this.state.chats).filter(([id]) => !gone.has(id)));
    const files = Object.fromEntries(Object.entries(this.state.files).filter(([id]) => !gone.has(id)));
    this.state = { ...this.state, chats, files };
    this.dirty.add("index");
    this.dirty.add("files");
  }

  dispatch(threadId: string, action: Action) {
    if (this.removed.has(threadId)) return; // a removed chat's run winding down
    const before = this.chat(threadId);
    const after = reduce(before, action);
    if (after === before) return;
    const index = Object.fromEntries(
      Object.entries(this.state.index).map(([pid, metas]) => [
        pid,
        metas.map((m) => (m.threadId === threadId ? { ...m, updatedAt: Date.now() } : m)),
      ]),
    );
    this.state = { ...this.state, index, chats: { ...this.state.chats, [threadId]: after } };
    this.dirty.add(threadId);
    this.dirty.add("index");
    this.emit();
  }

  /** Send a message on a chat, creating the chat in the project if it is new. */
  async send(projectId: string, threadId: string, message: string, opts: { replay?: boolean; reasoning?: boolean; designs?: { id: string; text: string }[] } = {}): Promise<void> {
    const text = message.trim();
    if (!text || this.isRunning(threadId)) return;
    const known = (this.state.index[projectId] ?? []).some((m) => m.threadId === threadId);
    if (!known) {
      const now = Date.now();
      this.addChat(projectId, {
        threadId,
        title: text.replace(/\s+/g, " ").slice(0, 90),
        createdAt: now,
        updatedAt: now,
        replay: opts.replay,
        reasoning: opts.reasoning,
      });
    }
    // The agent decides whether to reason; only a replayed scene sends its recorded mode.
    const reasoning = opts.reasoning;
    const turnId = newThreadId();
    // The files attached since the last message go with this one. The server searches them for
    // the rest of the chat; the chat shows them under this message only.
    const pending = pendingFiles(this.state.files[threadId] ?? []).filter((f) => f.status !== "failed");
    if (pending.length) this.markSent(threadId, new Set(pending.map((f) => f.name)), turnId);
    this.dispatch(threadId, { type: "send", turnId, message: text, at: Date.now(), reasoning, attachments: pending.map(toTurnAttachment), designs: opts.designs });
    // The run is marked as started at once (no second send meanwhile; Stop works), but it only
    // goes to the server once every file it carries is there: the agent reads them in this run.
    const ctrl = new AbortController();
    this.controllers.set(threadId, ctrl);
    this.emit();
    if (pending.some((f) => f.status === "uploading")) {
      await Promise.allSettled([...(this.uploads.get(threadId) ?? [])]);
      const sent = (this.state.files[threadId] ?? []).filter((f) => f.sentIn === turnId && f.status === "ready");
      this.dispatch(threadId, { type: "attachments", turnId, attachments: sent.map(toTurnAttachment) });
    }
    const designs = opts.designs?.map((d) => d.id);
    await this.run(threadId, { threadId, message: text, reasoning, device: this.device, size: this.size, projectId, ...(designs?.length ? { designs } : {}) }, ctrl);
  }

  private markSent(threadId: string, names: Set<string>, turnId: string | undefined) {
    const list = (this.state.files[threadId] ?? []).map((f) => (names.has(f.name) ? { ...f, sentIn: turnId } : f));
    this.state = { ...this.state, files: { ...this.state.files, [threadId]: list } };
    this.dirty.add("files");
    this.emit();
  }

  /** Answer the open clarification; the run continues on the same thread. */
  async answer(threadId: string, answers: Record<string, string>): Promise<void> {
    if (this.isRunning(threadId)) return;
    if (!this.transports.has(threadId)) {
      // The server keeps sessions in memory: after a restart it no longer knows the question.
      try {
        const info = await fetchThread(threadId);
        if (!info || !info.pending) {
          this.dispatch(threadId, {
            type: "failed",
            message: "The agent restarted and no longer has this question. Send the request again.",
            code: "expired",
          });
          return;
        }
      } catch {
        /* the run below reports a network failure */
      }
    }
    this.dispatch(threadId, { type: "answer", answers, at: Date.now() });
    await this.run(threadId, { threadId, answers, device: this.device, size: this.size });
  }

  /**
   * Upload files to a thread; each gets a chip that shows uploading, ready or failed. A file
   * waits in the composer (no `sentIn`) until the next message takes it.
   */
  async attach(threadId: string, files: File[], limits?: { types: string[]; max_mb: number }, projectId?: string): Promise<void> {
    await Promise.all(
      files.map(async (file) => {
        // Check what the server would refuse (415, 413) before sending it.
        const ext = file.name.includes(".") ? "." + file.name.split(".").pop()!.toLowerCase() : "";
        if (limits?.types?.length && !limits.types.includes(ext)) {
          this.setFile(threadId, { name: file.name, status: "failed", error: `file type: only ${limits.types.join(", ")} can be read` });
          return;
        }
        if (limits?.max_mb && file.size > limits.max_mb * 1024 * 1024) {
          this.setFile(threadId, { name: file.name, status: "failed", error: `file too large: at most ${limits.max_mb} MB` });
          return;
        }
        const preview = thumbnail(file);
        this.setFile(threadId, { name: file.name, status: "uploading", preview, sentIn: undefined });
        const upload = (async () => {
          try {
            const up = await uploadAttachment(threadId, file, undefined, projectId);
            // A message sent meanwhile took the file: it stays with that message.
            this.setFile(threadId, { name: up.name, status: "ready", chunks: up.chunks, preview }, file.name);
          } catch (err) {
            const message = err instanceof HttpError ? (err.status === 415 ? `can't read it: ${err.message}` : err.message) : "upload failed";
            if (preview) URL.revokeObjectURL(preview);
            // Failed after a message took it: back to the composer, where it can be dismissed.
            this.setFile(threadId, { name: file.name, status: "failed", error: message, sentIn: undefined });
          }
        })();
        const inflight = this.uploads.get(threadId) ?? new Set();
        inflight.add(upload);
        this.uploads.set(threadId, inflight);
        await upload;
        inflight.delete(upload);
      }),
    );
  }

  dismissFile(threadId: string, name: string) {
    const gone = (this.state.files[threadId] ?? []).find((f) => f.name === name);
    if (gone?.preview) URL.revokeObjectURL(gone.preview);
    const list = (this.state.files[threadId] ?? []).filter((f) => f.name !== name);
    this.state = { ...this.state, files: { ...this.state.files, [threadId]: list } };
    this.dirty.add("files");
    this.emit();
  }

  /** Take the server's list of a thread's attachments (it keeps them with the session). */
  async syncFiles(threadId: string): Promise<void> {
    try {
      const info = await fetchThread(threadId);
      if (!info?.attachments) return;
      const known = new Map((this.state.files[threadId] ?? []).map((f) => [f.name, f]));
      for (const name of info.attachments) if (!known.has(name)) known.set(name, { name, status: "ready" });
      this.state = { ...this.state, files: { ...this.state.files, [threadId]: [...known.values()] } };
      this.dirty.add("files");
      this.emit();
    } catch {
      /* offline: keep what we have */
    }
  }

  /** Add or replace a file's entry. It keeps the message it was sent with unless told otherwise. */
  private setFile(threadId: string, file: Attachment, replacing?: string) {
    if (this.removed.has(threadId)) return;
    const all = this.state.files[threadId] ?? [];
    const before = all.find((f) => f.name === replacing) ?? all.find((f) => f.name === file.name);
    const entry = "sentIn" in file ? file : { ...file, ...(before?.sentIn ? { sentIn: before.sentIn } : {}) };
    const list = all.filter((f) => f.name !== file.name && f.name !== replacing);
    this.state = { ...this.state, files: { ...this.state.files, [threadId]: [...list, entry] } };
    this.dirty.add("files");
    this.emit();
  }

  stop(threadId: string) {
    this.controllers.get(threadId)?.abort();
  }

  /** Stream a run; `ctrl` is the controller `send` registered while it waited for uploads. */
  private async run(threadId: string, body: RunBody, ctrl = new AbortController()) {
    this.controllers.set(threadId, ctrl);
    this.emit();
    const transport = this.transports.get(threadId) ?? liveTransport;
    let finished = false;
    try {
      // Stopped while its files were still uploading: nothing goes to the server.
      if (!ctrl.signal.aborted) {
        const source = transport(body, ctrl.signal);
        for await (const event of this.pace ? paced(source, ctrl.signal) : source) {
          if (ctrl.signal.aborted) break;
          this.dispatch(threadId, { type: "event", event });
          // What the user asked to remember changed: the sidebar's "Remembered" list reloads.
          if (event.type === "CUSTOM" && event.name === "memory" && typeof window !== "undefined")
            window.dispatchEvent(new CustomEvent(MEMORY_EVENT, { detail: event.value }));
          if (event.type === "RUN_FINISHED" || event.type === "RUN_ERROR") finished = true;
          if (event.type === "RUN_FINISHED") for (const fn of this.runListeners) fn(threadId);
        }
      }
      if (ctrl.signal.aborted) this.dispatch(threadId, { type: "stopped" });
      else if (!finished)
        this.dispatch(threadId, { type: "failed", message: "The stream ended before the run finished.", code: "stream" });
    } catch (err) {
      if (ctrl.signal.aborted) this.dispatch(threadId, { type: "stopped" });
      else if (err instanceof HttpError) this.dispatch(threadId, { type: "failed", message: err.message, code: "http" });
      else this.dispatch(threadId, { type: "failed", message: "Couldn't reach the agent server.", code: "network" });
    } finally {
      if (this.controllers.get(threadId) === ctrl) this.controllers.delete(threadId);
      this.emit();
    }
  }

  private emit() {
    // A new top-level object tells React that something changed (running flags included).
    this.state = { ...this.state };
    for (const fn of this.listeners) fn();
    this.saveSoon();
  }

  private saveSoon() {
    if (!this.storage || this.saveTimer) return;
    this.saveTimer = setTimeout(() => {
      this.saveTimer = null;
      this.save();
    }, 300);
  }

  private save() {
    const storage = this.storage;
    if (!storage) return;
    const replay = new Set(
      Object.values(this.state.index)
        .flat()
        .filter((m) => m.replay)
        .map((m) => m.threadId),
    );
    try {
      if (this.dirty.has("index")) {
        const index = Object.fromEntries(
          Object.entries(this.state.index).map(([pid, metas]) => [pid, metas.filter((m) => !m.replay)]),
        );
        storage.setItem(`${KEY}.index`, JSON.stringify(index));
      }
      if (this.dirty.has("files")) {
        const files = Object.fromEntries(
          Object.entries(this.state.files).map(([id, list]) => [id, list.filter((f) => f.status === "ready").map(({ preview: _, ...f }) => f)]),
        );
        storage.setItem(`${KEY}.files`, JSON.stringify(files));
      }
      for (const id of this.dirty) {
        if (id === "index" || id === "files" || replay.has(id)) continue;
        const chat = this.state.chats[id];
        if (chat) storage.setItem(`${KEY}.chat.${id}`, JSON.stringify(chat));
      }
      this.dirty.clear();
    } catch {
      /* storage full or blocked: the chats still work for this session */
    }
  }
}

export const store = new ChatStore();

export function useStore(): StoreState {
  return useSyncExternalStore(store.subscribe, store.getSnapshot);
}
