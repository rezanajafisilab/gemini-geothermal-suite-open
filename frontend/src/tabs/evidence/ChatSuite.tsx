// The chat suite (2 Nov): 51 questions about a design, each in three wordings, in ten groups,
// each case also failed automatically on a false run claim, wrong arithmetic, a refusal when
// the design has the answer, a cost under another's name or a design nobody asked about.
// One bar per group: the share of cases that passed.

import type { EvalRun } from "../../workbench";
import { openTranscript } from "./EvalMatrix";

const WORDS: Record<string, string> = {
  provenance: "Where a number comes from",
  premises: "Wrong premises corrected",
  quoted: "Quoting the reply",
  references: "“That one”, the picks",
  runs: "Several runs, @ picks",
  units: "Units (ct/kWh, °C, %)",
  languages: "Dutch and German",
  out_of_scope: "Off-topic declined",
  values: "Values the design has",
  labels: "Each cost by its name",
};

export function ChatSuite({ runs }: { runs: EvalRun[] }) {
  const run = runs[runs.length - 1];
  const groups = Object.entries(run.groups ?? {});
  return (
    <section id="ev-chat" className="ev-card ev-chat" aria-labelledby="ev-chat-h">
      <header className="ev-card-head">
        <h2 id="ev-chat-h">Chat suite</h2>
        <p className="ev-sub">
          {run.passed} of {run.total} cases passed ({Math.round((run.passed / Math.max(1, run.total)) * 100)}%) on the {run.label ?? run.device} with {run.answerer}, {run.when.slice(0, 8)}: 51 questions about a design, three wordings each, with automatic fails on every case.
        </p>
      </header>
      <ul className="ev-groups">
        {groups.map(([k, g]) => {
          const share = g.passed / Math.max(1, g.total);
          // Each case of the group, failures first, with its transcript when the run kept one.
          const cases = run.scenarios.filter((c) => c.group === k).sort((a, b) => Number(a.ok) - Number(b.ok));
          return (
            <li key={k} className="ev-group-item">
              <details>
                <summary className="ev-group">
                  <span className="ev-group-name">{WORDS[k] ?? k}</span>
                  <span className="ev-group-bar" aria-hidden="true">
                    <span style={{ width: `${share * 100}%` }} className={share >= 0.95 ? "ok" : share >= 0.8 ? "mid" : "low"} />
                  </span>
                  <span className="ev-group-n">
                    {g.passed}/{g.total}
                  </span>
                </summary>
                {cases.length > 0 && (
                  <ul className="ev-group-cases">
                    {cases.map((c) => (
                      <li key={c.id} className={c.ok ? "ok" : "fail"}>
                        <span>{c.ok ? "passed" : "failed"}</span>
                        <code>{c.id}</code>
                        {!c.ok && !!c.failed?.length && <span className="ev-muted">{c.failed.join("; ")}</span>}
                        {c.transcript && (
                          <button type="button" className="link-btn ev-link" onClick={() => openTranscript(run.file, c.id)}>
                            Open transcript
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </details>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
