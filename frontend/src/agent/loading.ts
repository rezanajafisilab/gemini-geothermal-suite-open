// Loading the local models (GET /api/models). The first message on a laptop can wait 10-60 s for
// its model to load; the server loads them at start, and the app bar says how far it has got:
// "Loading the models · 1 of 2 · 12 s" while they load, "Models ready" for a moment when they
// are, and what to do when they can't load ("Ollama is not running"). The poller asks about once
// a second while they load and stops when they are ready.

export type LoadState = "waiting" | "loading" | "ready" | "failed";

/** One model the server loads: what it does, where, how big, and how far it got. */
export interface ModelLoadInfo {
  model: string;
  roles: string[];
  device: "gpu" | "cpu";
  num_ctx?: number;
  state: LoadState;
  size_gb?: number | null;
  memory_gb?: number | null;
  seconds?: number | null;
  message?: string;
  hint?: string;
  label?: string;
}

export interface ModelsStatus {
  ready: boolean;
  /** idle: the server was not asked to load them (they load with the first message). */
  state: "idle" | "loading" | "ready" | "failed";
  loaded: number;
  total: number;
  seconds?: number | null;
  message?: string;
  hint?: string;
  device?: string;
  models: ModelLoadInfo[];
}

/** The status, "unsupported" for a server without the endpoint, or null when it doesn't answer. */
export async function fetchModels(signal?: AbortSignal): Promise<ModelsStatus | "unsupported" | null> {
  try {
    const res = await fetch("/api/models", { signal, cache: "no-store" });
    if (res.status === 404) return "unsupported";
    if (!res.ok) return null;
    const data = (await res.json()) as Partial<ModelsStatus>;
    if (!data || typeof data.state !== "string") return "unsupported";
    return { ready: !!data.ready, state: data.state, loaded: data.loaded ?? 0, total: data.total ?? 0, seconds: data.seconds, message: data.message, hint: data.hint, device: data.device, models: Array.isArray(data.models) ? data.models : [] };
  } catch {
    return null;
  }
}

export type ChipPhase = "loading" | "ready" | "fading" | "failed";

export interface ChipView {
  phase: ChipPhase;
  text: string;
  /** What to do about a failure, set in the code font. */
  hint?: string;
  /** Each model on its own line, for the tooltip. */
  title: string;
}

const ROLE_WORDS: Record<string, string> = { reader: "reads", answerer: "answers", reasoning: "reasons" };
const DEVICE: Record<string, string> = { gpu: "GPU", cpu: "CPU" };

/** One line per model for the tooltip: "qwen3.5:9b (answers, reasons) · GPU · loading, 12 s". */
export function modelLines(s: ModelsStatus): string {
  return s.models
    .map((m) => {
      const roles = m.roles.map((r) => ROLE_WORDS[r] ?? r).join(", ");
      const secs = m.seconds != null ? `, ${Math.round(m.seconds)} s` : "";
      const state = m.state === "failed" ? m.message || "failed" : m.state === "ready" ? `ready${secs}` : m.state === "loading" ? `loading${secs}` : "waiting";
      return `${m.model}${roles ? ` (${roles})` : ""} · ${DEVICE[m.device] ?? m.device} · ${state}`;
    })
    .join("\n");
}

/** What the chip says for a status; null when there is nothing to say (idle). */
export function chipView(s: ModelsStatus): ChipView | null {
  const title = modelLines(s);
  switch (s.state) {
    case "loading": {
      // The model being loaded counts as not yet loaded: "0 of 2" until the first is in memory.
      const secs = Math.max(0, Math.round(s.seconds ?? 0));
      return { phase: "loading", text: `Loading the models · ${s.loaded} of ${s.total} · ${secs} s`, title: `${title}\nThe first message waits for them once; they then stay in memory.` };
    }
    case "failed":
      return { phase: "failed", text: s.message || "The models could not be loaded", hint: s.hint || undefined, title: s.hint ? `${s.hint}\n${title}` : title };
    case "ready":
      return { phase: "ready", text: "Models ready", title };
    default:
      return null;
  }
}

export const POLL_MS = 1000;
/** After a failure the server tries again by itself (Ollama started later): look less often. */
export const FAILED_POLL_MS = 5000;
/** A server that doesn't answer (restarting): look again, with the chip hidden. */
export const OFFLINE_POLL_MS = 5000;
export const READY_SHOW_MS = 2500;
export const FADE_MS = 600;

type Fetcher = () => Promise<ModelsStatus | "unsupported" | null>;

/**
 * Polls the status while the models load, and says what the chip shows (null: no chip). It stops
 * when they are ready: "Models ready" then fades, unless they were ready at the first look (no
 * chip at all). A server without the endpoint stops it at once.
 */
export class ModelsWatcher {
  private timer: ReturnType<typeof setTimeout> | undefined;
  private stopped = false;
  private sawWork = false;

  constructor(
    private readonly fetcher: Fetcher,
    private readonly onView: (v: ChipView | null) => void,
  ) {}

  start(): void {
    this.stopped = false;
    void this.poll();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== undefined) clearTimeout(this.timer);
    this.timer = undefined;
  }

  private later(ms: number, fn: () => void): void {
    if (this.stopped) return;
    this.timer = setTimeout(fn, ms);
  }

  private async poll(): Promise<void> {
    if (this.stopped) return;
    const s = await this.fetcher();
    if (this.stopped) return;
    if (s === "unsupported") {
      this.onView(null);
      return;
    }
    if (s === null) {
      this.onView(null);
      this.later(OFFLINE_POLL_MS, () => void this.poll());
      return;
    }
    const view = chipView(s);
    if (s.state === "loading" || s.state === "failed") {
      this.sawWork = true;
      this.onView(view);
      this.later(s.state === "failed" ? FAILED_POLL_MS : POLL_MS, () => void this.poll());
      return;
    }
    if (s.state === "ready" && this.sawWork && view) {
      this.onView(view);
      this.later(READY_SHOW_MS, () => {
        this.onView({ ...view, phase: "fading" });
        this.later(FADE_MS, () => this.onView(null));
      });
      return;
    }
    this.onView(null); // ready at the first look, or idle: nothing to say
  }
}
