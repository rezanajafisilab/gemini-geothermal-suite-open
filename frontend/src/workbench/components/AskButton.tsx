// "Ask about this": opens the chat with a question about what you're looking at in the composer
// (not sent) and focuses it.

import { aboutPrompt, askInChat } from "../ask";
import "./workbench.css";

interface Props {
  /** What this is about, with its numbers, e.g. "A1's cost of heat, 42.4 €/MWh on the Economics tab". */
  context: string;
  /** The question; without one the composer ends after "About <context>: " for you to finish. */
  question?: string;
  /** The button's text (default "Ask about this"). */
  label?: string;
  /** Icon only (the label becomes its accessible name). */
  compact?: boolean;
  className?: string;
}

export function AskButton({ context, question, label = "Ask about this", compact = false, className }: Props) {
  return (
    <button
      type="button"
      className={`wb-ask ta-btn ta-chip${compact ? " compact" : ""}${className ? ` ${className}` : ""}`}
      aria-label={compact ? `${label}: ${context}` : undefined}
      title={`Ask the agent about ${context}`}
      onClick={() => askInChat(aboutPrompt(context, question))}
    >
      <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M2.5 3.5h11v7.2H7.6L4.6 13.2v-2.5H2.5z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
      {!compact && label}
    </button>
  );
}
