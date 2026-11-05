// Off-the-happy-path cards from the States board: model offline, run error, state tags.

import { useState } from "react";

import type { Health } from "../agent/client";
import type { ReplyChip } from "../agent/reducer";
import type { Turn, Unavailable } from "../agent/types";
import { Copy, Plug, Retry, Spinner, Tick } from "./Icons";

export function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="cmd">
      <code>{command}</code>
      <button
        type="button"
        className="icon-btn ta-btn ta-soft"
        aria-label={`Copy: ${command}`}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(command);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          } catch {
            /* clipboard blocked: the command is selectable */
          }
        }}
      >
        {copied ? <Tick size={15} color="#0F7A3D" /> : <Copy />}
      </button>
    </div>
  );
}

export function OfflineBanner({ health, checking, onRetry }: { health: Health; checking: boolean; onRetry: () => void }) {
  const model = health.model ?? "qwen3:1.7b";
  const server = health.state === "server-offline";
  const pull = health.fix?.startsWith("ollama pull");
  const steps = server
    ? [{ label: "Start it from the repo root", cmd: "PYTHONPATH=src python -m gemini_agent.server" }]
    : pull
      ? [{ label: "Get the model once", cmd: health.fix! }]
      : [
          { label: "Start Ollama", cmd: "ollama serve" },
          { label: "Get the model once if you haven't, about 1.4 GB", cmd: `ollama pull ${model}` },
        ];
  return (
    <section role="status" aria-label={server ? "Agent server not available" : "Local model not available"} className="banner ta-rise">
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <span className="icon-box" style={{ background: "#FBEACB" }}>
          <Plug color="#8A5A00" />
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
          <h3>{server ? "The agent server isn't answering" : pull ? `${model} isn't pulled yet` : `${model} isn't reachable`}</h3>
          <p>
            {server
              ? "The page can't reach the Python server, so nothing can run."
              : pull
                ? "Ollama runs, but the model isn't on this machine yet."
                : "Ollama didn't answer, so the agent can't read requests yet."}
          </p>
        </div>
      </div>
      <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        {steps.map((s, i) => (
          <li key={s.cmd} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <span className="numbered">{i + 1}</span>
            <div style={{ flex: "1 1 auto", minWidth: 0, display: "flex", flexDirection: "column", gap: 5 }}>
              <span style={{ fontSize: 13, color: "#45515B" }}>{s.label}</span>
              <CopyCommand command={s.cmd} />
            </div>
          </li>
        ))}
      </ol>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <button type="button" className="btn btn-ink ta-btn ta-ink" style={{ fontSize: 14, padding: "8px 14px 8px 12px" }} onClick={onRetry} disabled={checking}>
          {checking ? <Spinner size={15} light /> : <Retry />}
          {checking ? "Checking" : "Try again"}
        </button>
      </div>
    </section>
  );
}

/** The offline notice in a compact form, above the composer of a chat that has turns. */
export function OfflineStrip({ health, checking, onRetry }: { health: Health; checking: boolean; onRetry: () => void }) {
  const server = health.state === "server-offline";
  const cmd = server ? "PYTHONPATH=src python -m gemini_agent.server" : (health.fix ?? "ollama serve");
  return (
    <div className="strip" role="status">
      <span className="icon-box" style={{ background: "#FBEACB", width: 26, height: 26, borderRadius: 8 }}>
        <Plug size={14} color="#8A5A00" />
      </span>
      <span className="strip-text">
        <strong>{server ? "The agent server isn't answering." : `${health.model ?? "The model"} isn't available.`}</strong>{" "}
        {server ? "Start it:" : "Run this, then ask again:"}
      </span>
      <span className="strip-cmd">
        <CopyCommand command={cmd} />
      </span>
      <button type="button" className="btn btn-soft ta-btn ta-soft" style={{ fontSize: 13.5, padding: "6px 10px" }} onClick={onRetry} disabled={checking}>
        {checking ? <Spinner size={14} /> : <Retry size={14} />}
        Retry
      </button>
    </div>
  );
}

/** CUSTOM `model_unavailable`: the run couldn't read the request; name the fix, don't crash. */
export function UnavailableCard({ value, onRetry, canRetry }: { value: Unavailable; onRetry: () => void; canRetry: boolean }) {
  const pull = value.reason ? value.reason === "not_pulled" : value.fix.startsWith("ollama pull");
  // A timeout means Ollama is up but busy: there's nothing to install, just ask again.
  const slow = value.reason ? value.reason === "timeout" : /time(d)? ?out/i.test(value.error);
  if (slow)
    return (
      <section role="status" aria-label="The model didn't answer in time" className="banner ta-rise">
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <span className="icon-box" style={{ background: "#FBEACB" }}>
            <Plug color="#8A5A00" />
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
            <h3>{value.model} didn't answer in time</h3>
            <p>Ollama is running but busy, perhaps with another job. Ask again in a moment.</p>
          </div>
        </div>
        <details className="tech">
          <summary>What Ollama said</summary>
          <code>{value.error}</code>
        </details>
        {canRetry && (
          <div>
            <button type="button" className="btn btn-ink ta-btn ta-ink" style={{ fontSize: 14, padding: "8px 14px 8px 12px" }} onClick={onRetry}>
              <Retry />
              Ask again
            </button>
          </div>
        )}
      </section>
    );
  return (
    <section role="status" aria-label="Local model not available" className="banner ta-rise">
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <span className="icon-box" style={{ background: "#FBEACB" }}>
          <Plug color="#8A5A00" />
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
          <h3>{pull ? `${value.model} isn't pulled yet` : `${value.model} isn't reachable`}</h3>
          <p>{pull ? "Get it once, then ask again." : "Start Ollama, then ask again."}</p>
        </div>
      </div>
      {value.fix && <CopyCommand command={value.fix} />}
      <details className="tech">
        <summary>What Ollama said</summary>
        <code>{value.error}</code>
      </details>
      {canRetry && (
        <div>
          <button type="button" className="btn btn-ink ta-btn ta-ink" style={{ fontSize: 14, padding: "8px 14px 8px 12px" }} onClick={onRetry}>
            <Retry />
            Ask again
          </button>
        </div>
      )}
    </section>
  );
}

/** The reasoning model was missing mid-run: rules decided instead, and the run went on. */
export function FallbackNotice({ value }: { value: Unavailable }) {
  const slow = value.reason === "timeout";
  return (
    <div className="strip ta-rise" role="status" style={{ background: "#FFF8EB" }}>
      <span className="icon-box" style={{ background: "#FBEACB", width: 26, height: 26, borderRadius: 8 }}>
        <Plug size={14} color="#8A5A00" />
      </span>
      <span className="strip-text">
        <strong>
          {value.model} {slow ? "didn't answer in time" : "isn't available"},
        </strong>{" "}
        so rules made the decisions in this answer.{value.fix ? " To use it:" : " Ask again in a moment for the model's view."}
      </span>
      {value.fix && (
        <span className="strip-cmd">
          <CopyCommand command={value.fix} />
        </span>
      )}
    </div>
  );
}

/** Designs the answer leaves out (a tool failed or a physics check failed), one row each. */
export function LeftOutCard({ items }: { items: [string, string][] }) {
  return (
    <section className="card leftout ta-rise" aria-label="Designs left out">
      <span className="options-title">Left out of this answer</span>
      {items.map(([code, why]) => (
        <div key={code + why} className="leftout-row">
          {code ? <span className="alt-badge leftout-code">{code}</span> : <span />}
          <span>{why}</span>
        </div>
      ))}
    </section>
  );
}

const ERROR_TITLES: Record<string, string> = {
  expired: "This question expired",
  network: "The agent server didn't answer",
  http: "The server refused the request",
  stream: "The stream broke off",
};

export function ErrorCard({ turn, onRetry, canRetry }: { turn: Turn; onRetry: () => void; canRetry: boolean }) {
  const err = turn.error!;
  return (
    <section className="card error-card ta-rise" role="alert" aria-label="Run error">
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="icon-box" style={{ background: "#FCE9E7", color: "#A12C22" }}>
          <Retry />
        </span>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 650 }}>{ERROR_TITLES[err.code ?? ""] ?? "The run stopped on an error"}</h3>
      </div>
      <p className="error-msg">{err.message}</p>
      {canRetry && (
        <div>
          <button type="button" className="btn btn-ink ta-btn ta-ink" style={{ fontSize: 14 }} onClick={onRetry}>
            <Retry />
            {err.code === "expired" ? "Send the request again" : "Try again"}
          </button>
        </div>
      )}
    </section>
  );
}

const TAGS: Record<string, { text: string; bg: string; ink: string; icon: string }> = {
  refuse: {
    text: "Off-topic",
    bg: "#EEF2F2",
    ink: "#45515B",
    icon: "M8 1.8v12.4M8 3.6h4.2l1.6 1.6-1.6 1.6H8M8 8.4H3.8L2.2 10l1.6 1.6H8",
  },
  reject: { text: "Breaks physics", bg: "#FCE9E7", ink: "#A12C22", icon: "M2.4 12.2a5.6 5.6 0 1 1 11.2 0M8 12.2l3-3.9" },
  report_infeasible: {
    text: "Infeasible",
    bg: "#FCEDE6",
    ink: "#9A3B12",
    icon: "M13.6 8A5.6 5.6 0 1 1 8 2.4M8 2.4V8h5.6",
  },
  offer_model: { text: "No model yet", bg: "#E2F3F5", ink: "#0A6F7C", icon: "M8 1.8 13.4 4.9v6.2L8 14.2 2.6 11.1V4.9zM2.6 4.9 8 8l5.4-3.1M8 8v6.2" },
  approve_model: { text: "Model written and tested", bg: "#E3F5EA", ink: "#0F7A3D", icon: "M8 1.8 13.4 4.9v6.2L8 14.2 2.6 11.1V4.9zM2.6 4.9 8 8l5.4-3.1M8 8v6.2" },
  answer_docs: { text: "From the documents", bg: "#EEF2F2", ink: "#45515B", icon: "M2.5 3.2c2-.8 3.8-.6 5.5.6 1.7-1.2 3.5-1.4 5.5-.6v9.4c-2-.8-3.8-.6-5.5.6-1.7-1.2-3.5-1.4-5.5-.6zM8 3.8v9.4" },
  answer_model: { text: "From the generated model", bg: "#E3F5EA", ink: "#0F7A3D", icon: "M8 1.8 13.4 4.9v6.2L8 14.2 2.6 11.1V4.9zM2.6 4.9 8 8l5.4-3.1M8 8v6.2" },
  answer: { text: "From the project data", bg: "#E2F3F5", ink: "#0A6F7C", icon: "M4 1.8h5l3 3V14H4z M9 1.8V5h3M6 8.5h4M6 11h4" },
  error: { text: "No design to report", bg: "#FCE9E7", ink: "#A12C22", icon: "M2.4 12.2a5.6 5.6 0 1 1 11.2 0M8 12.2l3-3.9" },
};

export function StateTag({ behaviour }: { behaviour?: string }) {
  const tag = behaviour ? TAGS[behaviour] : undefined;
  if (!tag) return null;
  return (
    <p className="state-tag ta-rise" style={{ background: tag.bg, color: tag.ink }}>
      <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
        <path d={tag.icon} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {tag.text}
    </p>
  );
}

const REPLY_CHIPS = {
  general: {
    text: "General background",
    title: "Background knowledge, not drawn from this project's data",
    icon: "M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2zM2 8h12M8 2c1.7 1.6 2.5 3.6 2.5 6S9.7 12.4 8 14C6.3 12.4 5.5 10.4 5.5 8S6.3 3.6 8 2z",
  },
  out_of_scope: {
    text: "Outside my scope",
    title: "Not about designing geothermal heating and cooling, so not answered",
    icon: "M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2zM3.8 3.8l8.4 8.4",
  },
  nonsense: {
    text: "Not a question",
    title: "The message didn't read as a question or a request",
    icon: "M2.5 9.5c1.2-2.2 2.4-2.2 3.6 0s2.4 2.2 3.6 0 2.4-2.2 3.8 0",
  },
  fallback: {
    text: "Checked template",
    title: "The model was unavailable or failed the checks twice, so this is the checked template text",
    icon: "M8 1.6 13.4 3.6v4.2c0 3.2-2.3 5.6-5.4 6.6-3.1-1-5.4-3.4-5.4-6.6V3.6zM5.6 8.1 7.3 9.8l3.2-3.4",
  },
} as const;


const REMOVED_ICON = "M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2zM5.2 8h5.6";

/**
 * Small, quiet chips under a reply: what kind of answer this is when it isn't a project answer,
 * and how many sentences the claim checker took out (a button that opens its step).
 */
export function ReplyChips({ chips, removed = 0, onRemoved }: { chips: ReplyChip[]; removed?: number; onRemoved?: () => void }) {
  const removedText = `${removed} ${removed === 1 ? "claim" : "claims"} removed`;
  const removedIcon = (
    <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
      <path d={REMOVED_ICON} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  return (
    <div className="reply-meta ta-rise" aria-label="About this answer">
      {chips.map((c) => {
        const chip = REPLY_CHIPS[c];
        return (
          <span key={c} className={`meta-chip meta-${c}`} title={chip.title}>
            <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
              <path d={chip.icon} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {chip.text}
          </span>
        );
      })}
      {removed > 0 &&
        (onRemoved ? (
          <button type="button" className="meta-chip meta-removed ta-btn ta-chip" title="Not supported by the sources, so taken out of the reply. Show which" onClick={onRemoved}>
            {removedIcon}
            {removedText}
          </button>
        ) : (
          <span className="meta-chip meta-removed" title="Not supported by the sources, so taken out of the reply">
            {removedIcon}
            {removedText}
          </span>
        ))}
    </div>
  );
}
