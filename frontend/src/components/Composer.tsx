// The composer: Enter sends, Shift+Enter is a new line, Stop aborts a streaming run.
// Attachments go to the thread (POST /api/attachments) from the paperclip or a paste; the picker
// takes the types the server lists in /api/health, images included, and an image's chip shows a
// thumbnail. The chips are the files attached since the last message: the next message takes them.

import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type ClipboardEvent, type FormEvent, type ReactNode } from "react";

import type { Device, Health } from "../agent/client";
import { DEVICE_NAMES, profileOf } from "../agent/models";
import { attachmentLabel, kindOf, pastedFiles, type Attachment } from "../state/attachments";
import type { DesignItem } from "../workbench/designList";
import { Cross, FileIcon, Spinner } from "./Icons";
import { MentionList, PickedChips, mentionAt, mentionOrder, withoutMention } from "./Mentions";
import { CopyCommand } from "./StatusCards";

interface Props {
  draft: string;
  onDraft: (v: string) => void;
  running: boolean;
  waiting: boolean;
  /** What the input asks for, when the conversation waits for something in particular. */
  placeholder?: string;
  onSend: (text: string) => void;
  onStop: () => void;
  /** A notice shown above the input, e.g. the model-offline strip. */
  notice?: ReactNode;
  /** Under the input: the chat's designs (its list opens above the composer). */
  footer?: ReactNode;
  /** Shown above the composer when the reader is well above the latest content (assistant-ui). */
  onJump?: (() => void) | null;
  health: Health;
  /** The device picked in the header: the note names that profile's reasoning model. */
  device: Device;
  attachments: Attachment[];
  onAttach: (files: File[]) => void;
  onDismiss: (name: string) => void;
  /** The conversation's designs (@ picks from them), the picked ones, and the one questions go to. */
  designs?: DesignItem[];
  picked?: DesignItem[];
  onPicked?: (picked: DesignItem[]) => void;
  onCompare?: (ids: string[]) => void;
}

export interface ComposerHandle {
  focus: () => void;
}

export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { draft, onDraft, running, waiting, placeholder, onSend, onStop, notice, footer, onJump, health, device, attachments, onAttach, onDismiss, designs = [], picked = [], onPicked, onCompare },
  ref,
) {
  const area = useRef<HTMLTextAreaElement>(null);
  // "@" at the caret: the designs to pick from, filtered by what follows it.
  const [caret, setCaret] = useState(0);
  const [active, setActive] = useState(0);
  const [closedAt, setClosedAt] = useState<number | null>(null);
  const at = onPicked && designs.length ? mentionAt(draft, caret) : null;
  const mention = at && at.start !== closedAt ? at : null;
  const order = mention ? mentionOrder(designs.filter((d) => !picked.some((p) => p.id === d.id)), mention.query) : [];
  const pickMention = (d: DesignItem) => {
    if (!mention || !onPicked) return;
    onPicked([...picked.filter((p) => p.id !== d.id), d]);
    const next = withoutMention(draft, mention);
    onDraft(next);
    setActive(0);
    requestAnimationFrame(() => {
      const el = area.current;
      if (!el) return;
      const pos = Math.min(mention.start, next.length);
      el.focus();
      el.setSelectionRange(pos, pos);
      setCaret(pos);
    });
  };
  const about = designs.find((d) => d.recommended) ?? null;
  const picker = useRef<HTMLInputElement>(null);
  // Focus with the caret at the end, so a prefilled question ("Ask about this") can be finished.
  useImperativeHandle(
    ref,
    () => ({
      focus: () => {
        const el = area.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(el.value.length, el.value.length);
      },
    }),
    [],
  );

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(200, el.scrollHeight)}px`;
  }, [draft]);

  const canSend = !running && draft.trim().length > 0;
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (canSend) onSend(draft);
  };
  // A pasted screenshot or file attaches like the paperclip; text pastes as usual.
  const paste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = pastedFiles(e.clipboardData);
    if (!files.length) return;
    e.preventDefault();
    onAttach(files);
  };

  return (
    <form className="composer" aria-label="Ask the agent" onSubmit={submit}>
      {onJump && (
        <button type="button" className="jump-latest" onClick={onJump} aria-label="Jump to the latest">
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M8 3v9M4 8.5 8 12.5l4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Latest
        </button>
      )}
      {notice}
      {attachments.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }} aria-label="Files for your next message">
            {attachments.map((f) => (
              <span key={f.name} className={`file-chip ta-pop ${f.status}`} title={f.error ?? chipTitle(f)}>
                {f.status === "uploading" ? <Spinner size={13} /> : f.preview ? <img className="file-thumb" src={f.preview} alt="" /> : <FileIcon />}
                <span>{f.name}</span>
                {f.status === "uploading" && <em>uploading</em>}
                {f.status === "ready" && <em>{attachmentLabel(kindOf(f.name), f.chunks)}</em>}
                {f.status === "failed" && <em>{f.error ?? "failed"}</em>}
                {f.status === "failed" && (
                  <button type="button" className="file-x ta-btn ta-soft" aria-label={`Dismiss ${f.name}`} onClick={() => onDismiss(f.name)}>
                    <Cross />
                  </button>
                )}
              </span>
            ))}
          </div>
          <span className="note" style={{ fontSize: 12.5, paddingLeft: 2 }}>
            Sent with your next message; the agent searches it for the rest of this chat and cites it.
          </span>
        </div>
      )}
      {onPicked && (designs.length > 1 || picked.length > 0) && (
        <PickedChips
          picked={picked}
          about={about}
          onRemove={(id) => onPicked(picked.filter((p) => p.id !== id))}
          onCompare={() => onCompare?.(picked.map((p) => p.id))}
        />
      )}
      {mention && (
        <MentionList
          items={designs.filter((d) => !picked.some((p) => p.id === d.id))}
          query={mention.query}
          active={Math.min(active, Math.max(0, order.length - 1))}
          onActive={setActive}
          onPick={pickMention}
          id="composer"
        />
      )}
      <div className="composer-row">
        <button
          type="button"
          className="sq-btn attach ta-btn ta-soft"
          aria-label="Attach files"
          title={`Attach a brief, a datasheet or notes (${(health.attachments?.types ?? [".pdf", ".md", ".txt", ".csv"]).join(" ")}${health.attachments?.max_mb ? `, up to ${health.attachments.max_mb} MB` : ""}): the agent searches and cites them`}
          onClick={() => picker.current?.click()}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path d="M14.6 8.4 9.1 13.9a3.6 3.6 0 0 1-5.1-5.1l6-6a2.4 2.4 0 0 1 3.4 3.4l-6 6a1.2 1.2 0 0 1-1.7-1.7l5.4-5.4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <input
          ref={picker}
          type="file"
          multiple
          hidden
          accept={(health.attachments?.types ?? [".pdf", ".md", ".txt", ".rst", ".csv", ".tex", ".json"]).join(",")}
          onChange={(e) => {
            const picked = Array.from(e.target.files ?? []);
            if (picked.length) onAttach(picked);
            e.target.value = "";
          }}
        />
        <label htmlFor="composer-q" className="sr-only">
          Message the agent
        </label>
        <textarea
          id="composer-q"
          ref={area}
          rows={1}
          value={draft}
          placeholder={running ? "Working… stop it any time" : placeholder ?? (waiting ? "Or ask something else" : "Ask, or describe a district")}
          role={mention ? "combobox" : undefined}
          aria-expanded={mention ? true : undefined}
          aria-controls={mention ? "composer-mentions" : undefined}
          aria-activedescendant={mention && order.length ? `composer-m-${Math.min(active, order.length - 1)}` : undefined}
          onChange={(e) => {
            onDraft(e.target.value);
            setCaret(e.target.selectionStart ?? e.target.value.length);
            setActive(0);
          }}
          onSelect={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart ?? 0)}
          onPaste={paste}
          onKeyDown={(e) => {
            if (mention && order.length) {
              const i = Math.min(active, order.length - 1);
              if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                setActive(e.key === "ArrowDown" ? Math.min(order.length - 1, i + 1) : Math.max(0, i - 1));
                return;
              }
              if ((e.key === "Enter" || e.key === "Tab") && !e.nativeEvent.isComposing) {
                e.preventDefault();
                pickMention(order[i]);
                return;
              }
            }
            if (mention && e.key === "Escape") {
              e.preventDefault();
              setClosedAt(mention.start);
              return;
            }
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {running ? (
          <button type="button" className="sq-btn send ta-btn ta-ink" aria-label="Stop the agent" title="Stop the agent" onClick={onStop}>
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <rect x="5" y="5" width="8" height="8" rx="1.6" fill="currentColor" />
            </svg>
          </button>
        ) : (
          <button type="submit" className="sq-btn send ta-btn ta-ink" aria-label="Send" disabled={!canSend}>
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <path d="M9 14V4M4.5 8.5 9 4l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
      <ThinkNote health={health} device={device} />
      {footer}
    </form>
  );
});

/** The chip's hover text: what the server made of the file. */
function chipTitle(f: Attachment): string {
  if (kindOf(f.name) === "image") return `${f.name}: an image the agent can look at`;
  return f.chunks != null ? `${f.name}: ${attachmentLabel("text", f.chunks)} indexed` : f.name;
}

/**
 * The agent decides per message whether to reason: the reader judges it, code keeps it off for
 * values and greetings and turns it on when no design fits. The note names the model that
 * reasons on the device picked at the top, and gives the fix when that model isn't pulled (rules
 * then decide, so a run still works).
 */
function ThinkNote({ health, device }: { health: Health; device: Device }) {
  const p = profileOf(health, device);
  const plan = p?.reasoning ?? (health.reasoning?.model ? { model: health.reasoning.model, device: health.reasoning.device } : undefined);
  // Readiness is known for the server's own reasoning model only.
  const r = health.reasoning && (!plan || plan.model === health.reasoning.model) ? health.reasoning : undefined;
  const where = plan?.device ? DEVICE_NAMES[plan.device] : undefined;
  return (
    <div className="composer-foot">
      {r && r.ready === false && r.fix ? (
        <span className="mode-note warn">
          <span>
            <strong>{r.model}</strong> isn't ready, so rules decide when a question needs reasoning, until you run
          </span>
          <CopyCommand command={r.fix} />
        </span>
      ) : (
        <span className="mode-note hide-narrow" title="The reader judges each message; code keeps reasoning off for values and greetings, and on when no design fits">
          Reasons when a question needs it
          {plan?.model && (
            <>
              {" "}
              · <strong>{plan.model}</strong>
              {where ? ` on the ${where}` : ""}
            </>
          )}
        </span>
      )}
    </div>
  );
}
