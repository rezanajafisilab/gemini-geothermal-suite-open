// Dialogs over the chat: a file's preview (from a file chip or a source's Open button) and an
// image full size. Esc or a click outside closes the top one; Tab stays inside it; focus goes
// back where it was.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { fetchFileView, type FileLookup } from "../agent/client";
import type { FileView } from "../agent/types";
import { FileCard } from "./FileCard";
import { Cross, FileGlyph, Spinner } from "./Icons";

const stack: object[] = [];

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(
    root.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input, select, textarea'),
  ).filter((el) => el.offsetParent !== null || el === document.activeElement);
}

export function Modal({ label, onClose, children, className }: { label: string; onClose: () => void; children: ReactNode; className?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const token = {};
    stack.push(token);
    const before = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    box.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== token || !box.current) return;
      if (e.key === "Escape") {
        e.preventDefault();
        close.current();
      } else if (e.key === "Tab") {
        const items = focusables(box.current);
        if (!items.length) return e.preventDefault();
        const first = items[0];
        const last = items[items.length - 1];
        const inside = box.current.contains(document.activeElement);
        if (e.shiftKey && (document.activeElement === first || !inside)) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && (document.activeElement === last || !inside)) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      stack.splice(stack.indexOf(token), 1);
      before?.focus();
    };
  }, []);

  return createPortal(
    <div
      className="modal-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close.current();
      }}
    >
      <div ref={box} className={`modal ta-rise${className ? ` ${className}` : ""}`} role="dialog" aria-modal="true" aria-label={label}>
        <button type="button" className="modal-x ta-btn ta-soft" aria-label="Close" title="Close (Esc)" data-autofocus onClick={() => close.current()}>
          <Cross size={11} />
        </button>
        {children}
      </div>
    </div>,
    document.body,
  );
}

/**
 * A file's preview by name. A file a run already opened is shown from its "file" event; any other
 * is asked of the server, and a file it doesn't have (or no server, in fixture mode) says so.
 */
export function FilePreview({ name, threadId, projectId, known, onClose }: { name: string; threadId?: string; projectId?: string; known?: FileView; onClose: () => void }) {
  const [found, setFound] = useState<FileLookup | null>(null);
  useEffect(() => {
    if (known) return;
    if (!threadId) {
      setFound({ ok: false, status: 0, detail: "This chat has no thread on the server yet." });
      return;
    }
    const ctrl = new AbortController();
    setFound(null);
    void fetchFileView(threadId, name, ctrl.signal, projectId).then((r) => {
      if (!ctrl.signal.aborted) setFound(r);
    });
    return () => ctrl.abort();
  }, [name, threadId, projectId, known]);

  const state: FileLookup | null = known ? { ok: true, view: known } : found;
  return (
    <Modal label={`File ${name}`} onClose={onClose} className="modal-file">
      {state?.ok ? (
        <FileCard file={state.view} inModal />
      ) : (
        <div className="fpreview-state" role="status">
          <span className="icon-box" style={{ background: state ? "#FCE9E7" : "#EEF2F2", color: state ? "#A12C22" : "#45515B" }}>
            {state ? <FileGlyph name={name} size={16} /> : <Spinner size={16} />}
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
            <strong className="fpreview-name">{name}</strong>
            {!state ? (
              <span className="note">Opening the file…</span>
            ) : (
              <>
                <span className="note">
                  {state.status === 404 ? "This file isn't on the server, so it can't be opened here." : "This file can't be opened right now."} {state.detail}
                </span>
                <span className="note" style={{ fontSize: 12.5 }}>
                  {state.status === 404
                    ? "Project files and the files you attach to this chat can be opened; documentation is quoted in the sources."
                    : "Check that the agent server is running, then try again."}
                </span>
              </>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

export function ImageModal({ url, caption, onClose }: { url: string; caption?: string; onClose: () => void }) {
  const [broken, setBroken] = useState(false);
  return (
    <Modal label={caption ? `Image: ${caption}` : "Image"} onClose={onClose} className="modal-image">
      <figure className="lightbox">
        {broken ? <p className="fempty">The image couldn't be loaded.</p> : <img src={url} alt={caption ?? ""} onError={() => setBroken(true)} />}
        {caption && <figcaption>{caption}</figcaption>}
      </figure>
    </Modal>
  );
}
