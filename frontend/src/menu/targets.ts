// Targets that read the page when a menu opens (the text selected in an answer).

import type { MenuTarget } from "./types";

/** The text selected inside an answer's text, or "" (a selection elsewhere doesn't count). */
export function answerSelection(): string {
  if (typeof window === "undefined") return "";
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed) return "";
  const node = sel.anchorNode;
  const el = node instanceof Element ? node : node?.parentElement;
  return el?.closest(".answer-text") ? sel.toString().trim() : "";
}

/** An answer's menu: copy it as Markdown, flag a statement (the selection, when there is one). */
export function answerTarget(markdown: string): MenuTarget | null {
  if (!markdown.trim()) return null;
  return { kind: "answer", markdown, selection: answerSelection() || undefined };
}
