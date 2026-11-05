// The agents of a turn: who took part, which model (or code) each is, what each did, and which is
// working now. The orchestrator is code; each agent is a role filled by a local model or by tools,
// and the step rows below say the same in more detail. Folded to a row of faces by default.

import { useState } from "react";

import { stepModel } from "../agent/reducer";
import type { Step, Turn } from "../agent/types";
import { fmtSeconds } from "./Header";
import { Chevron } from "./Icons";

interface Role {
  id: string;
  name: string;
  does: string;
  /** Who fills the role when no model is named on its steps. */
  by: string;
  color: string;
  match: (s: Step) => boolean;
}

export const ROLES: Role[] = [
  { id: "reader", name: "Reader", does: "Reads the message and what it sets or changes, judges whether it needs reasoning, and has a larger model confirm before refusing anything", by: "model", color: "#0a6f7c", match: (s) => ["intake", "think", "screen", "route", "parameters", "confirm"].includes(s.name) },
  { id: "librarian", name: "Librarian", does: "Finds values, files and documents, and gathers the inputs to confirm", by: "tools", color: "#2363a6", match: (s) => ["lookup", "file", "docs", "inputs"].includes(s.name) },
  { id: "planner", name: "Planner", does: "Plans the candidates, and the fixes when none fits", by: "rules", color: "#7856c4", match: (s) => ["plan", "options", "decide", "ask"].includes(s.name) },
  { id: "engineer", name: "Engineer", does: "Solves the wells on GEMINI and runs every day of the year", by: "GEMINI + plant model", color: "#c24e1c", match: (s) => ["doublet", "simulate", "search", "use_model", "register"].includes(s.name) },
  { id: "verifier", name: "Verifier", does: "Checks the challenge's caps and grows what broke", by: "code", color: "#0f7a3d", match: (s) => s.name === "verify" || s.name === "improve" || s.name === "edits" },
  { id: "economist", name: "Economist", does: "Prices the designs and picks one", by: "code", color: "#8a5a00", match: (s) => s.name === "rank" },
  { id: "builder", name: "Model builder", does: "Writes and tests code for a missing component", by: "model", color: "#5b3fa6", match: (s) => s.name.startsWith("modelgen") },
  { id: "writer", name: "Writer", does: "Writes the reply from the checked draft", by: "template", color: "#45515b", match: (s) => s.name === "answer" || s.name === "report" },
  { id: "checker", name: "Fact-checker", does: "Checks each claim of the reply against its sources", by: "model", color: "#a12c22", match: (s) => s.name === "claims" },
];

type Status = "active" | "waiting" | "error" | "done";

export interface AgentRow {
  role: Role;
  steps: Step[];
  status: Status;
  who: string;
  seconds: number;
}

/** The agents that took part in a turn, in the order they first acted. */
export function agentsOf(turn: Turn): AgentRow[] {
  const rows: AgentRow[] = [];
  // Each model a role used, in order: the reader reads the message with the fast model and what
  // it sets or changes with the reasoning model.
  const models = new Map<string, string[]>();
  for (const s of turn.steps) {
    const role = ROLES.find((r) => r.match(s));
    if (!role) continue;
    let row = rows.find((r) => r.role.id === role.id);
    if (!row) {
      row = { role, steps: [], status: "done", who: role.by, seconds: 0 };
      rows.push(row);
      models.set(role.id, []);
    }
    row.steps.push(s);
    row.seconds += s.seconds ?? 0;
    const model = stepModel(turn, s);
    const used = models.get(role.id)!;
    if (model && s.meta.decided_by !== "rules" && !used.includes(model)) used.push(model);
    if (used.length) row.who = used.join(" + ");
  }
  for (const row of rows) {
    const st = row.steps.map((s) => s.status);
    row.status = st.includes("active") ? "active" : st.includes("error") ? "error" : st.includes("waiting") ? "waiting" : "done";
  }
  return rows;
}

const initials = (name: string) =>
  name
    .split(/[\s-]+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

export function AgentsPanel({ turn }: { turn: Turn }) {
  const [open, setOpen] = useState(false);
  const rows = agentsOf(turn);
  if (!rows.length) return null;
  const busy = rows.find((r) => r.status === "active");
  // A role counts as a model only when a model decided one of its steps (the rest is code).
  const onModels = rows.filter((r) => r.who !== r.role.by).length;
  return (
    <div className={`agents${open ? " open" : ""}`}>
      <button type="button" className="agents-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="agents-faces" aria-hidden="true">
          {rows.map((r) => (
            <span key={r.role.id} className={`agent-face ${r.status}`} style={{ ["--agent" as string]: r.role.color }} title={r.role.name}>
              {initials(r.role.name)}
            </span>
          ))}
        </span>
        <span className="agents-title">
          {busy ? (
            <>
              <b>{busy.role.name}</b> is working · {rows.length} roles
            </>
          ) : (
            <>
              {rows.length} roles took part · {onModels} on a model, {rows.length - onModels} rules or code
            </>
          )}
        </span>
        <Chevron open={open} />
      </button>
      {open && (
        <ul className="agents-list">
          {rows.map((r) => (
            <li key={r.role.id} className={`agent-row ${r.status}`}>
              <span className={`agent-face ${r.status}`} style={{ ["--agent" as string]: r.role.color }} aria-hidden="true">
                {initials(r.role.name)}
              </span>
              <span className="agent-main">
                <span className="agent-line">
                  <b>{r.role.name}</b>
                  <span className="agent-who">{r.who}</span>
                  <span className="agent-state">{r.status === "active" ? "working" : r.status === "waiting" ? "waiting for you" : r.status === "error" ? "failed" : fmtSeconds(r.seconds)}</span>
                </span>
                <span className="agent-does">{r.role.does}</span>
                <span className="agent-did">{[...new Set(r.steps.map((s) => s.label))].join(" · ")}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
