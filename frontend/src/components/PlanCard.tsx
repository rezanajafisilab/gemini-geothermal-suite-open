// A request's steps as the agent planned and ran them (CUSTOM `plan`): what it understood, in
// order, each ticked when done or marked when it could not run, so a reworded request that was
// read differently is visible before the answer.

import type { PlanView } from "../agent/types";
import { DoneIcon } from "./Icons";

export function PlanCard({ value }: { value: PlanView }) {
  if (value.steps.length < 2 && value.steps.every((s) => s.do === "answer")) return null;
  return (
    <section className="plan-card ta-rise" aria-label="The steps I took">
      <span className="plan-kicker">The steps I took</span>
      <ol>
        {value.steps.map((s) => (
          <li key={s.n} className={`plan-step ${s.status}`}>
            <span className="plan-mark" aria-hidden="true">
              {s.status === "done" ? <DoneIcon size={14} /> : s.status === "skipped" ? "–" : s.n}
            </span>
            <span>{s.label}</span>
            {s.status === "skipped" && <span className="tag tag-amber">not run</span>}
          </li>
        ))}
      </ol>
    </section>
  );
}
