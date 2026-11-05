// An empty state: an icon, a one-line title, a one-line hint and an optional action.

import type { ReactNode } from "react";

import { DESIGN_REQUEST, askInChat } from "../ask";
import "./workbench.css";

export interface EmptyAction {
  label: string;
  onClick: () => void;
}

interface Props {
  title: string;
  hint?: ReactNode;
  icon?: ReactNode;
  action?: EmptyAction;
}

/** The action of a conversation with no designs: the chat, with a design request ready to send. */
export const ASK_FOR_DESIGN: EmptyAction = { label: "Ask for a design in the chat", onClick: () => askInChat(DESIGN_REQUEST) };

/** Two wells joined underground: the doublet. */
export function DoubletIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3.5v10a5 5 0 0 0 10 0v-10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M4.5 3.5h5M14.5 3.5h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function EmptyState({ title, hint, icon, action }: Props) {
  return (
    <section className="wb-empty ta-rise" aria-label={title}>
      <span className="wb-empty-icon">{icon ?? <DoubletIcon />}</span>
      <h2 className="wb-empty-title">{title}</h2>
      {hint && <p className="wb-empty-hint">{hint}</p>}
      {action && (
        <button type="button" className="btn btn-ink ta-btn ta-ink" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </section>
  );
}
