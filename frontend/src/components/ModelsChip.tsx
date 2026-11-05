// The app bar's chip while the local models load: "Loading the models · 1 of 2 · 12 s" with a
// pulsing dot, "Models ready" for a moment when they are (then it fades), or a failure with what
// to do ("Ollama is not running · Start it with: ollama serve"). Nothing once they are ready.

import { useEffect, useState } from "react";

import { ModelsWatcher, fetchModels, type ChipView } from "../agent/loading";

export function ModelsChip() {
  const [view, setView] = useState<ChipView | null>(null);
  useEffect(() => {
    const watcher = new ModelsWatcher(fetchModels, setView);
    watcher.start();
    return () => watcher.stop();
  }, []);
  return <ModelsChipView view={view} />;
}

export function ModelsChipView({ view }: { view: ChipView | null }) {
  if (!view) return null;
  const at = view.hint?.indexOf(": ") ?? -1;
  // "Run: ollama pull qwen3.5:9b": the command in the code font (the words are in the tooltip,
  // and the chat's offline card gives the steps), else the hint as it is.
  const hint = view.hint && at > 0 ? { words: "", code: view.hint.slice(at + 2) } : view.hint ? { words: view.hint, code: "" } : null;
  return (
    <span className={`pill pill-line load-chip is-${view.phase}`} role="status" aria-live="polite" title={view.title}>
      {view.phase === "ready" || view.phase === "fading" ? (
        <svg className="load-tick ta-pop" width="14" height="14" viewBox="0 0 20 20" aria-hidden="true">
          <circle cx="10" cy="10" r="10" fill="var(--ok-bg)" />
          <path d="M6 10.4 8.7 13 14 7.2" fill="none" stroke="var(--ok)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <span className="load-dot" aria-hidden="true" />
      )}
      <span className="load-text">{view.text}</span>
      {hint && (
        <span className="load-hint">
          {hint.words}
          {hint.code && <code>{hint.code}</code>}
        </span>
      )}
    </span>
  );
}
