// Talking to the Python server (src/gemini_agent/server.py): the run stream, health and threads.

import { SseParser } from "./sse";
import type { AgEvent, FileView } from "./types";

/** Where the models run: "auto" uses the GPU when there is one, "cpu" never does. */
export type Device = "auto" | "cpu";

/** Which model: "auto" takes the first that fits (9B GPU, 4B GPU, 9B CPU, 4B CPU). */
export type Size = "auto" | "9b" | "4b";

export interface RunBody {
  threadId: string;
  message?: string;
  answers?: Record<string, string>;
  /** Force reasoning on or off; left out, the agent decides per message. */
  reasoning?: boolean;
  /** The device the user picked in the header; sent with every run. */
  device?: Device;
  /** The model the user picked in the header; sent with every run. */
  size?: Size;
  /** The chat's project (the server puts a new conversation in it). */
  projectId?: string;
  /** The designs the user picked with @ for this message: the question is about them. */
  designs?: string[];
}

/** Where a run's events come from: the live server, or a recorded stream in fixture mode. */
export type Transport = (body: RunBody, signal: AbortSignal) => AsyncIterable<AgEvent>;

export class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export const liveTransport: Transport = async function* (body, signal) {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail ?? data);
    } catch {
      /* not JSON */
    }
    throw new HttpError(res.status, `The server answered ${res.status}: ${detail}`);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SseParser();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const event of parser.push(value)) yield event;
    }
    for (const event of parser.end()) yield event;
  } finally {
    reader.releaseLock();
  }
};

export type HealthState = "checking" | "ok" | "model-offline" | "server-offline";

export interface ModelHealth {
  model?: string;
  device?: "gpu" | "cpu";
  ready?: boolean;
  /** The command that makes the model ready ("ollama serve" or "ollama pull <model>"). */
  fix?: string;
}

/** One role's model and where it runs. */
export interface RoleModel {
  model: string;
  device: "gpu" | "cpu";
}

/** The models of every role on one device choice (GET /api/health `profiles`). */
export interface Profile {
  /** Reads messages. */
  fast?: RoleModel;
  /** Writes the replies. */
  answer?: RoleModel;
  /** Writes the replies in reasoning mode. */
  answer_reasoning?: RoleModel;
  /** Plans the study and picks fixes in reasoning mode. */
  reasoning?: RoleModel;
  /** Writes missing component models. */
  generator?: RoleModel;
  /** Why the reasoning model runs where it does (GPU memory), in a sentence. */
  why?: string;
}

export interface Health extends ModelHealth {
  state: HealthState;
  reasoning?: ModelHealth;
  /** The GPU's name, empty without one (then the GPU choice is off). */
  gpu?: string;
  /** The device the server uses when a run doesn't say. */
  default_device?: Device;
  /** The model size the server uses when a run doesn't say. */
  default_size?: Size;
  /** The model that writes replies on the server's default device. */
  answer?: RoleModel;
  /** Every role's model per choice ("auto", "cpu", "auto:9b", "cpu:4b" ...); older servers send the devices only. */
  profiles?: Partial<Record<string, Profile>>;
  /** What uploads may be: file types and size. */
  attachments?: { types: string[]; max_mb: number };
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  try {
    const res = await fetch("/api/health", { signal, cache: "no-store" });
    if (!res.ok) return { state: "server-offline" };
    const data = (await res.json()) as Omit<Health, "state"> & { ollama?: boolean };
    const ready = data.ready ?? data.ollama;
    return {
      state: ready ? "ok" : "model-offline",
      model: data.model,
      device: data.device,
      ready,
      fix: data.fix || (ready ? undefined : "ollama serve"),
      reasoning: data.reasoning,
      gpu: data.gpu,
      default_device: data.default_device === "cpu" || data.default_device === "auto" ? data.default_device : undefined,
      default_size: data.default_size === "9b" || data.default_size === "4b" || data.default_size === "auto" ? data.default_size : undefined,
      answer: data.answer,
      profiles: data.profiles && typeof data.profiles === "object" ? data.profiles : undefined,
      attachments: data.attachments,
    };
  } catch {
    return { state: "server-offline" };
  }
}

export interface ThreadInfo {
  threadId: string;
  pending: unknown;
  attachments?: string[];
}

export interface Uploaded {
  threadId: string;
  name: string;
  chunks: number;
}

/** Attach a file to a conversation (POST /api/attachments); the thread is created if new. */
export async function uploadAttachment(threadId: string, file: File, signal?: AbortSignal, projectId?: string): Promise<Uploaded> {
  const form = new FormData();
  form.append("threadId", threadId);
  form.append("file", file, file.name);
  if (projectId) form.append("projectId", projectId);
  let res: Response;
  try {
    res = await fetch("/api/attachments", { method: "POST", body: form, signal });
  } catch {
    throw new HttpError(0, "Couldn't reach the agent server.");
  }
  if (!res.ok) {
    let detail = res.statusText || "upload failed";
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* not JSON */
    }
    throw new HttpError(res.status, detail);
  }
  return (await res.json()) as Uploaded;
}

/** A project file or an upload of a thread, raw (downloads, images) or as a preview (`view`). */
export function fileUrl(threadId: string, name: string, view = false, projectId?: string): string {
  const q = new URLSearchParams({ threadId, name });
  if (view) q.set("view", "1");
  if (projectId) q.set("projectId", projectId);
  return `/api/files?${q}`;
}

export type FileLookup = { ok: true; view: FileView } | { ok: false; status: number; detail: string };

/**
 * The preview of a file (GET /api/files?view=1): the same FileView a run's "file" event carries.
 * Never throws: a missing file (404), an unreachable server or an answer that isn't a preview
 * (fixture mode with no server) come back as { ok: false } with a sentence to show.
 */
export async function fetchFileView(threadId: string, name: string, signal?: AbortSignal, projectId?: string): Promise<FileLookup> {
  let res: Response;
  try {
    res = await fetch(fileUrl(threadId, name, true, projectId), { signal, cache: "no-store" });
  } catch {
    return { ok: false, status: 0, detail: "The agent server isn't answering." };
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* not JSON: an older server, or a dev server with no API behind it */
  }
  const body = data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  if (!res.ok) {
    if (typeof body?.detail === "string") return { ok: false, status: res.status, detail: body.detail };
    // A dev proxy with no server behind it answers 502-504.
    if (res.status >= 502 && res.status <= 504) return { ok: false, status: 0, detail: "The agent server isn't answering." };
    return { ok: false, status: res.status, detail: res.status === 404 ? "The file isn't on the server." : `The server answered ${res.status}.` };
  }
  if (!body || typeof body.name !== "string" || typeof body.kind !== "string") {
    return { ok: false, status: 0, detail: "The server didn't send a preview of this file." };
  }
  return { ok: true, view: body as unknown as FileView };
}

// ------------------------------------------------------------------ projects

/** One district on the server (GET /api/projects): the organisers' one first, then the users'. */
export interface ProjectInfo {
  id: string;
  name: string;
  builtin: boolean;
  created: number | null;
  files: string[];
  reservoir: { depth_m: number; temperature_c: number; pressure_bar: number; permeability_md: number; thickness_m: number; gradient_c_per_km: number };
  heating: { supply_c: number; return_c: number };
  cooling: { supply_c: number; return_c: number };
  totals: { annual_heat_gwh: number; annual_cool_gwh: number; peak_heat_mw: number; peak_cool_mw: number };
  notes: string[];
  /** 52 weekly means, MW (the sparklines). */
  weekly_mw: { heat: number[]; cool: number[] };
}

/** What a demand file gives (POST /api/projects/profile), read as a new project would read it. */
export interface ProfilePreview {
  name: string;
  kind: "heat" | "cool";
  column: string;
  annual_gwh: number;
  peak_mw: number;
  notes: string[];
  weekly_mw: number[];
  /** A heating file that has a cooling column too. */
  cool_column: boolean;
  /**
   * The header names no unit and the values are far too large for MW: the user picks the unit
   * (sent back as `unit`, and as `heat_unit` or `cool_unit` with the project). Read in the
   * first option meanwhile.
   */
  unit_question?: { key: string; text: string; options: string[] } | null;
}

async function detail(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    /* not JSON */
  }
  return res.statusText || fallback;
}

async function call(url: string, init: RequestInit, fallback: string): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new HttpError(0, "Couldn't reach the agent server.");
  }
  if (!res.ok) throw new HttpError(res.status, await detail(res, fallback));
  return res;
}

export async function fetchProjects(signal?: AbortSignal): Promise<ProjectInfo[]> {
  const res = await call("/api/projects", { signal, cache: "no-store" }, "couldn't list the projects");
  const data = await res.json();
  if (!Array.isArray(data?.projects)) throw new HttpError(0, "The server didn't send a list of projects.");
  return data.projects as ProjectInfo[];
}

/** Add a project (POST /api/projects); a refusal (422) carries the reason to show. */
export async function createProject(form: FormData): Promise<ProjectInfo> {
  const res = await call("/api/projects", { method: "POST", body: form }, "the project couldn't be made");
  return (await res.json()).project as ProjectInfo;
}

export async function previewProfile(file: File, kind: "heat" | "cool", signal?: AbortSignal, unit?: string): Promise<ProfilePreview> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("kind", kind);
  if (unit) form.append("unit", unit);
  const res = await call("/api/projects/profile", { method: "POST", body: form, signal }, "the file couldn't be read");
  return (await res.json()) as ProfilePreview;
}

export async function deleteProject(id: string): Promise<void> {
  await call(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" }, "the project couldn't be removed");
}

/** What DELETE /api/threads/{id} removed: the runs it stopped and the files that went. */
export interface ThreadRemoved {
  threadId: string;
  stopped: number;
  removed: string[];
}

/**
 * Remove a chat on the server: its run stops, and its session, uploads and trace go. A thread
 * the server never knew has nothing to remove (still ok); a refusal or no server throws.
 */
export async function deleteThread(threadId: string): Promise<ThreadRemoved> {
  const res = await call(`/api/threads/${encodeURIComponent(threadId)}`, { method: "DELETE" }, "the chat couldn't be removed");
  return (await res.json()) as ThreadRemoved;
}

/** What the server knows of a thread; null when it doesn't know it (it restarted). */
/** One thing the user asked Dioscuri to remember, shared by every chat of its project. */
export interface MemoryNote {
  id: string;
  text: string;
  said: string;
  thread: string;
  turn: number;
  at: number;
}

/** What a project remembers (GET /api/projects/{id}/memory); [] from a server without memory. */
export async function fetchMemory(projectId: string, signal?: AbortSignal): Promise<MemoryNote[]> {
  try {
    const res = await call(`/api/projects/${encodeURIComponent(projectId)}/memory`, { signal, cache: "no-store" }, "couldn't read the project's memory");
    const data = await res.json();
    return Array.isArray(data?.notes) ? (data.notes as MemoryNote[]) : [];
  } catch (err) {
    if (err instanceof HttpError && err.status === 404) return [];
    throw err;
  }
}

/** Forget one note, or all of a project's (DELETE /api/projects/{id}/memory[?id=]); returns what is left. */
export async function forgetMemory(projectId: string, noteId?: string): Promise<MemoryNote[]> {
  const q = noteId ? `?id=${encodeURIComponent(noteId)}` : "";
  const res = await call(`/api/projects/${encodeURIComponent(projectId)}/memory${q}`, { method: "DELETE" }, "couldn't forget that");
  const data = await res.json();
  return Array.isArray(data?.notes) ? (data.notes as MemoryNote[]) : [];
}

export async function fetchThread(threadId: string): Promise<ThreadInfo | null> {
  const res = await fetch(`/api/threads/${encodeURIComponent(threadId)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new HttpError(res.status, res.statusText);
  return (await res.json()) as ThreadInfo;
}

export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const id = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(id);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * Presentation pacing. Tool steps finish in milliseconds, so without it a run's
 * rows would all tick at once. Each step stays visibly active for at least `minActive` ms and the
 * next one starts `gap` ms later. The durations shown are always the agent's own.
 */
export function paced(source: AsyncIterable<AgEvent>, signal: AbortSignal, minActive = 240, gap = 40): AsyncIterable<AgEvent> {
  return {
    async *[Symbol.asyncIterator]() {
      let startedAt = 0;
      let finishedAt = 0;
      for await (const event of source) {
        if (minActive > 0 && event.type === "STEP_STARTED") {
          const wait = finishedAt + gap - performance.now();
          if (wait > 0) await sleep(wait, signal);
          startedAt = performance.now();
        } else if (minActive > 0 && event.type === "STEP_FINISHED") {
          const wait = startedAt + minActive - performance.now();
          if (wait > 0) await sleep(wait, signal);
          finishedAt = performance.now();
        }
        yield event;
      }
    },
  };
}
