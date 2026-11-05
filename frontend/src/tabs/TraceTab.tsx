// The Trace tab: how each answer of the conversation was computed. The runs of the chat, newest
// first; for the one picked, its steps on a time scale, its model calls and tokens, and every
// tool call with its arguments and result. Export saves a run (or all of them) as JSON.

import "./TraceTab.css";

import { useMemo, useState } from "react";

import { Download } from "../components/Icons";
import { TabFrame, getTrace, go, resourceStatus, useResource, useWorkbench } from "../workbench";
import { RunDetail } from "./trace/RunDetail";
import { RunList } from "./trace/RunList";
import { downloadJson, exportName, exportPayload, pickRun, sortRuns } from "./trace/model";

export default function TraceTab() {
  const { threadId, runsFinished } = useWorkbench();
  // Refetch when the chat on screen changes and after each of its runs.
  const trace = useResource((signal) => (threadId ? getTrace(threadId, signal) : new Promise<never>(() => {})), [threadId, runsFinished]);
  const runs = useMemo(() => sortRuns(trace.data?.runs ?? []), [trace.data]);
  // Nothing picked by hand: follow the newest run, so a new message takes over the page.
  const [picked, setPicked] = useState<{ thread: string | null; run: string | null }>({ thread: null, run: null });
  const follow = picked.thread !== threadId || !picked.run;
  const run = pickRun(runs, picked.run, follow);
  const [kindPick, setKind] = useState<string | null>(null);
  // A filter the run on screen has no steps of shows them all.
  const kind = kindPick && run?.steps.some((s) => (s.kind || "other") === kindPick) ? kindPick : null;
  // The chat's order: message 1 is the first one sent.
  const number = run ? runs.length - runs.indexOf(run) : 0;

  const select = (runId: string) => {
    // Picking the newest goes back to following new runs.
    setPicked({ thread: threadId, run: runId === runs[0]?.runId ? null : runId });
    setKind(null);
  };

  return (
    <TabFrame
      scope="none"
      className="tab-trace"
      title="How the answers were computed"
      lead="Every message of this chat is a run: its steps, the model calls with their tokens, and the tool calls with their arguments and results."
      status={resourceStatus(trace, runs.length === 0, {
        title: "No runs in this chat yet",
        hint: "Ask something in the chat, then come back: each message shows up here with its steps, model calls and tokens.",
        action: { label: "Go to the chat", onClick: () => go("chat") },
      })}
      actions={
        run && (
          <>
            <button type="button" className="btn btn-soft ta-btn ta-soft tr-export" onClick={() => downloadJson(exportName(threadId, run.runId), exportPayload(threadId, [run]))}>
              <Download />
              Export this run
            </button>
            {runs.length > 1 && (
              <button type="button" className="btn btn-soft ta-btn ta-soft tr-export" onClick={() => downloadJson(exportName(threadId), exportPayload(threadId, [...runs].reverse()))}>
                <Download />
                All {runs.length} runs
              </button>
            )}
          </>
        )
      }
    >
      {run && (
        <div className={`tr-layout${trace.refreshing ? " is-refreshing" : ""}`}>
          <RunList runs={runs} selected={run.runId} onSelect={select} />
          <RunDetail run={run} number={number} kind={kind} onKind={setKind} />
        </div>
      )}
    </TabFrame>
  );
}
