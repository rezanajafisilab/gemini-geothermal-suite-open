// The quick-ask box: a question about what was right-clicked, typed where the menu was. Enter (or
// Send) switches to the chat and sends it; Shift+Enter is a new line; Escape or a click outside
// closes it. "Edit in chat" puts the question in the chat's composer instead, unsent. From full
// screen the Design tab leaves full screen first, so the chat is there to see. "@" picks designs
// as in the composer (4 Nov: "@A1" typed here went as plain text): the conversation's designs,
// filtered as you type; a pick is a chip and goes with the question, as the composer's do.

import { useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { MentionList, PickedChips, mentionAt, mentionOrder, withoutMention } from "../components/Mentions";
import { askInChat, sendInChat } from "../workbench/ask";
import { designItems, type DesignItem } from "../workbench/designList";
import { useWorkbench } from "../workbench/store";
import { MenuIcon } from "./icons";
import { placeMenu } from "./keys";
import { closeQuickAsk, quickAskStore, type QuickAsk } from "./quickask";
import { showToast } from "./store";

const LINES_MAX = 6;

async function leaveFullScreen(): Promise<void> {
  if (typeof document !== "undefined" && document.fullscreenElement) await document.exitFullscreen().catch(() => undefined);
}

function Box({ ask }: { ask: QuickAsk }) {
  const [text, setText] = useState(ask.text);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  // "About A1: " is a question still to be finished.
  const empty = !text.trim() || text.trim().endsWith(":");
  // "@" at the caret: the conversation's designs to pick from (as in the composer).
  const wb = useWorkbench();
  const designs = useMemo(() => designItems(wb.workbench), [wb.workbench]);
  const [picked, setPicked] = useState<DesignItem[]>([]);
  const [caret, setCaret] = useState(ask.text.length);
  const [active, setActive] = useState(0);
  const [closedAt, setClosedAt] = useState<number | null>(null);
  const at = designs.length ? mentionAt(text, caret) : null;
  const mention = at && at.start !== closedAt ? at : null;
  const free = designs.filter((d) => !picked.some((p) => p.id === d.id));
  const order = mention ? mentionOrder(free, mention.query) : [];
  // The list opens above the box's input in the lower half of the screen, else below it.
  const up = !!area.current && area.current.getBoundingClientRect().top > window.innerHeight / 2;
  const pick = (d: DesignItem) => {
    if (!mention) return;
    setPicked((p) => [...p.filter((x) => x.id !== d.id), d]);
    const next = withoutMention(text, mention);
    setText(next);
    setActive(0);
    requestAnimationFrame(() => {
      const el = area.current;
      if (!el) return;
      const at = Math.min(mention.start, next.length);
      el.focus();
      el.setSelectionRange(at, at);
      setCaret(at);
    });
  };

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const view = { w: window.innerWidth, h: window.innerHeight };
    const size = { w: el.offsetWidth, h: el.offsetHeight };
    // Where the menu was; with no place, low in the middle of the screen, above the fold.
    setPos(ask.at ? placeMenu(ask.at, size, view, 12) : { left: Math.max(12, (view.w - size.w) / 2), top: Math.max(12, view.h - size.h - 96) });
  }, [ask]);

  useEffect(() => {
    const el = area.current;
    if (!el || !pos) return;
    el.focus({ preventScroll: true });
    el.setSelectionRange(el.value.length, el.value.length);
  }, [pos]);

  // The box grows with the question, up to six lines.
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    const line = parseFloat(getComputedStyle(el).lineHeight) || 20;
    el.style.height = `${Math.min(el.scrollHeight, line * LINES_MAX + 16)}px`;
  }, [text]);

  useEffect(() => {
    const away = (e: Event) => {
      if (!root.current?.contains(e.target as Node)) closeQuickAsk();
    };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, []);

  const send = async () => {
    const t = text.trim();
    if (empty) return;
    closeQuickAsk();
    await leaveFullScreen();
    if (!sendInChat(t, picked)) showToast("A reply is still being written: your question is in the chat box, ready to send");
  };

  const toChat = async () => {
    closeQuickAsk();
    await leaveFullScreen();
    askInChat(text, picked);
  };

  return (
    <div
      ref={root}
      className="qa"
      role="dialog"
      aria-modal="false"
      aria-label={ask.about ? `Ask about ${ask.about}` : "Ask Dioscuri"}
      style={pos ? { left: pos.left, top: pos.top } : { left: 0, top: 0, visibility: "hidden" }}
      onContextMenu={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          closeQuickAsk();
        }
      }}
    >
      <div className="qa-head">
        <span className="qa-icon" aria-hidden="true">
          <MenuIcon name="ask" />
        </span>
        <span className="qa-title">Ask Dioscuri</span>
        {ask.about && (
          <span className="qa-about" title={ask.about}>
            {ask.about}
          </span>
        )}
        <button type="button" className="qa-close" aria-label="Close" onClick={() => closeQuickAsk()}>
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      {picked.length > 0 && <PickedChips picked={picked} about={null} onRemove={(id) => setPicked((p) => p.filter((x) => x.id !== id))} onCompare={() => undefined} />}
      <div className={`qa-field${up ? " up" : ""}`}>
        {mention && <MentionList items={free} query={mention.query} active={Math.min(active, Math.max(0, order.length - 1))} onActive={setActive} onPick={pick} id={`qa-${ask.id}`} />}
        <textarea
          ref={area}
          className="qa-input"
          rows={2}
          value={text}
          placeholder={designs.length ? "Type your question; @ picks a design" : "Type your question…"}
          aria-label="Your question"
          role={mention ? "combobox" : undefined}
          aria-expanded={mention ? true : undefined}
          aria-controls={mention ? `qa-${ask.id}-mentions` : undefined}
          aria-activedescendant={mention && order.length ? `qa-${ask.id}-m-${Math.min(active, order.length - 1)}` : undefined}
          onChange={(e) => {
            setText(e.target.value);
            setCaret(e.target.selectionStart ?? e.target.value.length);
            setActive(0);
          }}
          onSelect={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart ?? 0)}
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
                pick(order[i]);
                return;
              }
            }
            if (mention && e.key === "Escape") {
              // Closes the list, not the box.
              e.preventDefault();
              e.stopPropagation();
              setClosedAt(mention.start);
              return;
            }
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void send();
            }
          }}
        />
      </div>
      <div className="qa-foot">
        <span className="qa-keys" aria-hidden="true">
          <kbd>↵</kbd> send <kbd>⇧</kbd>
          <kbd>↵</kbd> new line
          {designs.length > 0 && (
            <>
              {" "}
              <kbd>@</kbd> design
            </>
          )}
        </span>
        <button type="button" className="qa-btn ghost" onClick={() => void toChat()}>
          Edit in chat
        </button>
        <button type="button" className="qa-btn primary" disabled={empty} onClick={() => void send()}>
          Send
          <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M8 13V3M3.8 7.2 8 3l4.2 4.2" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

/** Drawn by the menu host, so it shows in full screen too. */
export function QuickAskHost() {
  const ask = useSyncExternalStore(quickAskStore.subscribe, quickAskStore.getSnapshot, quickAskStore.getSnapshot);
  return ask ? <Box key={ask.id} ask={ask} /> : null;
}
