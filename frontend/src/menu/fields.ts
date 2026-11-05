// What a text box's own menu does (the browser's is never shown): cut, copy, paste and select
// all, on the selection the box had when the menu opened. Text goes in through the browser's
// insertText command where it works, so React's onChange and the undo stack both see it; else
// through setRangeText and an input event.

import { copyText } from "./ops";
import { showToast } from "./store";
import type { MenuTarget } from "./types";

type TextTarget = Extract<MenuTarget, { kind: "text" }>;

function put(field: HTMLInputElement | HTMLTextAreaElement, text: string, start: number, end: number): void {
  field.focus({ preventScroll: true });
  try {
    field.setSelectionRange(start, end);
  } catch {
    /* a field type with no selection (number): the caret stays where it is */
  }
  let done = false;
  try {
    done = document.execCommand("insertText", false, text);
  } catch {
    done = false;
  }
  if (!done) {
    field.setRangeText(text, start, end, "end");
    field.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

export async function editText(t: TextTarget, action: "cut" | "copy" | "paste" | "selectAll"): Promise<void> {
  const { field, start, end, selection } = t;
  if (!field.isConnected) return;
  if (action === "selectAll") {
    field.focus({ preventScroll: true });
    field.select();
    return;
  }
  if (action === "copy" || action === "cut") {
    if (!selection) return;
    const ok = await copyText(selection);
    if (!ok) return showToast("Couldn't copy: the browser blocked the clipboard", "bad");
    if (action === "cut" && t.editable) put(field, "", start, end);
    return;
  }
  // Paste: the browser may ask once whether this page may read the clipboard.
  let text: string | null = null;
  try {
    text = navigator.clipboard?.readText ? await navigator.clipboard.readText() : null;
  } catch {
    text = null;
  }
  if (text == null) {
    field.focus({ preventScroll: true });
    return showToast("The browser didn't allow reading the clipboard: paste with Ctrl+V", "bad");
  }
  put(field, text, start, end);
}
