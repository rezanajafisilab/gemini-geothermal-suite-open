// The Evidence tab, the judges' page (global, not per conversation): the eval runs as headline
// tiles and a scenario matrix, the failures caught and fixed, the model benchmarks, and what the
// team's fixes change in GEMINI.

import "./EvidenceTab.css";

import { useMemo, useState } from "react";

import { TabFrame, getEvidence, go, resourceStatus, useResource, useRoute } from "../workbench";
import { Benchmarks } from "./evidence/Benchmarks";
import { EvalMatrix, EvalTiles } from "./evidence/EvalMatrix";
import { CaughtFixed } from "./evidence/CaughtFixed";
import { ChatSuite } from "./evidence/ChatSuite";
import { GeminiImpact } from "./evidence/GeminiImpact";
import { RealProjects } from "./evidence/RealProjects";
import { buildMatrix } from "./evidence/model";
import { TranscriptView } from "./evidence/TranscriptView";

const SECTIONS = [
  { id: "ev-scenarios", label: "Test scenarios" },
  { id: "ev-caught", label: "Caught and fixed" },
  { id: "ev-chat", label: "Chat suite" },
  { id: "ev-real", label: "Real projects" },
  { id: "ev-benchmarks", label: "Benchmarks" },
  { id: "ev-gemini", label: "GEMINI's fixes" },
];

const jump = (id: string) => {
  const el = document.getElementById(id);
  if (!el) return;
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
};

export default function EvidenceTab() {
  const evidence = useResource((signal) => getEvidence(signal), []);
  const e = evidence.data;
  // "#evidence/<run>/<case>": that eval case's transcript, over the page.
  const route = useRoute();
  const cut = route.design?.lastIndexOf("/") ?? -1;
  const transcript = route.design && cut > 0 ? { run: route.design.slice(0, cut), id: route.design.slice(cut + 1) } : null;
  // The matrix shows the main scenarios; the chat suite (three wordings of 51) has its own card.
  const matrix = useMemo(() => buildMatrix((e?.evals ?? []).filter((r) => (r.suite ?? "main") === "main")), [e]);
  const chat = (e?.evals ?? []).filter((r) => r.suite === "chat");
  // The first failure, if any, is open below the matrix to begin with.
  const firstFail = useMemo(() => {
    for (const row of matrix.rows) {
      const col = row.cells.findIndex((c) => c && !c.ok);
      if (col >= 0) return { rowId: row.id, col };
    }
    return null;
  }, [matrix]);
  const [picked, setPicked] = useState<{ rowId: string; col: number } | null | undefined>(undefined);
  const selected = picked === undefined ? firstFail : picked;

  const hasGemini = !!e && (e.gemini.patches.length > 0 || e.gemini.bug_impact.length > 0);
  const sections = SECTIONS.filter((s) =>
    s.id === "ev-scenarios" ? matrix.rows.length > 0 : s.id === "ev-caught" ? !!e?.caught?.items.length : s.id === "ev-gemini" ? hasGemini : s.id === "ev-chat" ? chat.length > 0 : s.id === "ev-real" ? !!e?.validation?.length : true,
  );

  return (
    <TabFrame
      scope="none"
      className="tab-evidence"
      title="Evidence"
      lead="How we know the agent works: the test scenarios on each device, the failures we caught and fixed, the benchmarks behind the choice of local models, and what the team's fixes change in GEMINI."
      status={resourceStatus(evidence, !!e && !e.evals.length && !e.benchmarks.length && !hasGemini, {
        title: "No evidence yet",
        hint: "Run the evals (hackathon/evals/run_evals.py) to fill this page.",
        action: null,
      })}
      toolbar={
        sections.length > 1 && (
          <nav className="ev-jump" aria-label="Sections">
            {sections.map((s) => (
              <button key={s.id} type="button" className="ev-jump-btn ta-btn" onClick={() => jump(s.id)}>
                {s.label}
              </button>
            ))}
          </nav>
        )
      }
    >
      {e && (
        <>
          {matrix.runs.length > 0 && (
            <EvalTiles
              matrix={matrix}
              onShow={(rowId, col) => {
                setPicked({ rowId, col });
                jump("ev-scenarios");
              }}
            />
          )}
          {matrix.rows.length > 0 && <EvalMatrix matrix={matrix} selected={selected} onSelect={setPicked} />}
          {!!e.caught?.items.length && <CaughtFixed caught={e.caught} />}
          {chat.length > 0 && <ChatSuite runs={chat} />}
          {!!e.validation?.length && <RealProjects checks={e.validation} />}
          <Benchmarks benchmarks={e.benchmarks} />
          {hasGemini && <GeminiImpact gemini={e.gemini} />}
        </>
      )}
      {transcript && <TranscriptView run={transcript.run} caseId={transcript.id} onClose={() => go("evidence", null, { replace: true })} />}
    </TabFrame>
  );
}
