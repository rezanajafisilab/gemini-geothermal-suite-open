import { useEffect, useState } from "react";

import { fetchMemory, forgetMemory, type MemoryNote } from "../agent/client";
import { MEMORY_EVENT } from "../state/store";
import { Cross } from "./Icons";

/** Where a note was said, as the list shows it: this chat, or another chat of the project. */
export function noteSource(note: Pick<MemoryNote, "thread" | "turn">, current: string | null): string {
  if (current && note.thread === current) return note.turn ? `Said in this chat (turn ${note.turn})` : "Said in this chat";
  return "Said in another chat";
}

/**
 * What the user asked Dioscuri to remember in this project (their name, how to answer): shared by
 * every chat of the project, while each chat keeps its own conversation, designs and inputs. A
 * note can be forgotten here; nothing shows when the server keeps no memory (fixtures, offline).
 */
export function ProjectMemory({ projectId, current }: { projectId: string; current: string | null }) {
  const [notes, setNotes] = useState<MemoryNote[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const ctrl = new AbortController();
    const load = () =>
      fetchMemory(projectId, ctrl.signal)
        .then((n) => (setNotes(n), setError("")))
        .catch(() => setNotes(null));
    load();
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent).detail as { projectId?: string; notes?: MemoryNote[] } | undefined;
      if (detail?.projectId === projectId && Array.isArray(detail.notes)) setNotes(detail.notes);
      else if (!detail?.projectId || detail.projectId === projectId) load();
    };
    window.addEventListener(MEMORY_EVENT, onChange);
    return () => {
      ctrl.abort();
      window.removeEventListener(MEMORY_EVENT, onChange);
    };
  }, [projectId]);

  if (notes === null) return null;
  const forget = (id?: string) =>
    forgetMemory(projectId, id)
      .then((n) => (setNotes(n), setError("")))
      .catch((err: Error) => setError(err.message || "Couldn't forget that."));

  return (
    <section className="side-memory" aria-label="Remembered in this project">
      <div className="sm-head">
        <h2>Remembered</h2>
        {notes.length > 1 && (
          <button type="button" className="link-btn" onClick={() => forget()}>
            Forget all
          </button>
        )}
      </div>
      {notes.length === 0 ? (
        <p className="sm-empty">Nothing yet. Tell Dioscuri, for example "call me Sam" or "keep answers short".</p>
      ) : (
        <ul className="sm-list">
          {notes.map((n) => (
            <li key={n.id} className="sm-note" title={`${noteSource(n, current)}: “${n.said}”`}>
              <span className="sm-text">{n.text}</span>
              <button type="button" className="del ta-soft" aria-label={`Forget "${n.text}"`} title="Forget this" onClick={() => forget(n.id)}>
                <Cross />
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="sm-hint">Every chat in this project shares what is remembered here. Each chat keeps its own conversation, designs and inputs.</p>
      {error && (
        <p className="sm-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
