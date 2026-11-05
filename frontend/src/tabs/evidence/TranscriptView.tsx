// One eval case's whole conversation, read-only (the Evidence tab's "Open transcript"): what
// the case checked and how each check came out, then the chat as the user saw it (each message,
// the steps with their tool calls, the cards and the answers to them), rebuilt from the recorded
// events with the chat's own reducer and turn view. Below it, every model call of the case.

import { useMemo } from "react";

import { TurnView } from "../../components/ChatView";
import { FilesContext, type FilesApi } from "../../components/filesContext";
import { Modal } from "../../components/Modal";
import { Spinner } from "../../components/Icons";
import { getTranscript, useResource } from "../../workbench";
import type { Transcript, TruthRow } from "../../workbench";
import { behaviourLabel, scenarioName } from "./model";
import { transcriptChat } from "./transcript";

const NO_FILES: FilesApi = { open: () => undefined, showImage: () => undefined };
const noop = () => undefined;

function Mark({ ok }: { ok: boolean | null }) {
  return <span className={`tx-mark ${ok === null ? "na" : ok ? "ok" : "fail"}`}>{ok === null ? "–" : ok ? "✓" : "✗"}</span>;
}

function TruthList({ title, rows }: { title: string; rows: TruthRow[] }) {
  if (!rows.length) return null;
  return (
    <div className="tx-truth">
      <h4>{title}</h4>
      <ul>
        {rows.map((r) => (
          <li key={r.key}>
            <Mark ok={r.ok} />
            <span>{r.name.replace(/^(cap|known): /, "")}</span>
            <span className="tx-found">{r.found}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TranscriptBody({ t }: { t: Transcript }) {
  const chat = useMemo(() => transcriptChat(t), [t]);
  const { num, name } = scenarioName(t.case);
  const checks = Object.entries(t.checks);
  const calls = t.runs.flatMap((r) => r.calls);
  const tokens = calls.reduce((n, c) => n + (c.prompt_tokens || 0) + (c.output_tokens || 0), 0);
  return (
    <div className="tx">
      <header className="tx-head">
        <span className={`tx-verdict ${t.pass ? "ok" : "fail"}`}>{t.pass ? "Passed" : "Failed"}</span>
        <h2>
          <span className="ev-muted">{num}</span> {name}
        </h2>
        <p className="ev-muted">
          Expected {behaviourLabel(t.expected)}, got {behaviourLabel(t.got ?? "") || "nothing"} · {t.model} on the {t.device === "cpu" ? "CPU" : "GPU"}
          {t.project && t.project.id !== "challenge" ? ` · project ${t.project.name}` : ""} · {calls.length} model calls, {tokens.toLocaleString("en-US")} tokens, {Math.round(t.wall_seconds)} s
        </p>
        {t.after && <p className="ev-muted">Continues the conversation of {scenarioName(t.after).num || t.after} (its transcript has the turns before).</p>}
      </header>

      <section className="tx-checks" aria-label="Checks">
        <ul>
          <li>
            <Mark ok={t.behaviour_ok} /> <span>behaviour: {behaviourLabel(t.expected)}</span>
          </li>
          {checks
            .filter(([k]) => !/^(cap|known): /.test(k))
            .map(([k, v]) => (
              <li key={k}>
                <Mark ok={v} /> <span>{k.replace(/_/g, " ")}</span>
              </li>
            ))}
        </ul>
        {t.truth && (t.truth.caps.length > 0 || t.truth.known.length > 0) && (
          <div className="tx-truths">
            <TruthList title={`Hard caps, read again from ${t.truth.design ?? "the design"}'s year`} rows={t.truth.caps} />
            <TruthList title="The district's known demand" rows={t.truth.known} />
          </div>
        )}
      </section>

      <FilesContext.Provider value={NO_FILES}>
        <div className="tx-chat main" aria-label="The conversation, read-only">
          {chat.turns.map((turn) => (
            <TurnView key={turn.id} turn={turn} isLast={false} now={Date.now()} running={false} onAnswer={noop} onSend={noop} thumb={() => undefined} />
          ))}
        </div>
      </FilesContext.Provider>

      {calls.length > 0 && (
        <details className="tx-calls">
          <summary>Every model call ({calls.length})</summary>
          <table>
            <thead>
              <tr>
                <th>Purpose</th>
                <th>Model</th>
                <th>Prompt tokens</th>
                <th>Output tokens</th>
                <th>Seconds</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((c, i) => (
                <tr key={i}>
                  <td>{c.purpose}</td>
                  <td>
                    <code>{c.model}</code>
                  </td>
                  <td>{c.prompt_tokens}</td>
                  <td>{c.output_tokens}</td>
                  <td>{typeof c.seconds === "number" ? c.seconds.toFixed(1) : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}

/** The transcript of one case of one run, in a dialog. */
export function TranscriptView({ run, caseId, onClose }: { run: string; caseId: string; onClose: () => void }) {
  const res = useResource((signal) => getTranscript(run, caseId, signal), [run, caseId]);
  return (
    <Modal label={`Transcript of ${caseId}`} onClose={onClose} className="modal-transcript">
      {res.status === "loading" && (
        <p className="ev-muted">
          <Spinner /> Reading the transcript…
        </p>
      )}
      {res.status === "error" && <p className="ev-muted">This case's transcript couldn't be read{res.error?.status === 404 ? ": the run kept none" : ""}.</p>}
      {res.data && <TranscriptBody t={res.data} />}
    </Modal>
  );
}
