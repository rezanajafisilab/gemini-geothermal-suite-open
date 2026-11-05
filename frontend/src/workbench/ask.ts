// "Ask about this": from any tab, open the chat with a question about what you were looking at
// in the composer (prefilled, not sent) and focus it. App.tsx listens with onAsk().

import { itemText, type DesignItem } from "./designList";
import { go } from "./route";

/** The request the empty states offer when a conversation has no designs yet. */
export const DESIGN_REQUEST = "Design heating and cooling for the district with 70/40 °C heating and 6/12 °C cooling.";

type Listener = (text: string) => void;
const listeners = new Set<Listener>();

/** App.tsx: put `text` in the composer and focus it. */
export function onAsk(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** The designs a message is about, as the chat sends them (the composer's @ picks). */
export interface SentDesign {
  id: string;
  text: string;
}
export const sentDesigns = (picked: DesignItem[]): SentDesign[] | undefined => (picked.length ? picked.map((d) => ({ id: d.id, text: itemText(d) })) : undefined);

type PickListener = (picked: DesignItem[]) => void;
const pickers = new Set<PickListener>();

/** ChatView: take the designs picked elsewhere (the quick-ask box's @) as the composer's chips. */
export function onAskPicks(fn: PickListener): () => void {
  pickers.add(fn);
  return () => {
    pickers.delete(fn);
  };
}

/** Switch to the chat with `text` in the composer, ready to edit and send (and its @ picks as chips). */
export function askInChat(text: string, picked: DesignItem[] = []): void {
  go("chat");
  for (const fn of listeners) fn(text);
  if (picked.length) for (const fn of pickers) fn(picked);
}

/**
 * The composer text for "Ask about this": "About <context>: <question>". Without a question the
 * text ends after the colon, for the reader to finish.
 * aboutPrompt("A1's cost of heat, 42.4 €/MWh", "why is it lower than A2's?")
 *   → "About A1's cost of heat, 42.4 €/MWh: why is it lower than A2's?"
 */
export function aboutPrompt(context: string, question?: string): string {
  const c = context.trim().replace(/[.:]+$/, "");
  const q = question?.trim();
  return q ? `About ${c}: ${q}` : `About ${c}: `;
}

type SendListener = (text: string, designs?: SentDesign[]) => boolean;
const senders = new Set<SendListener>();

/** App.tsx: send `text` as the user's message; false when a reply is still being written. */
export function onSendAsk(fn: SendListener): () => void {
  senders.add(fn);
  return () => {
    senders.delete(fn);
  };
}

/**
 * The quick-ask box's Send: switch to the chat and send `text` there, with the designs picked
 * with @ (sent as the composer sends its picks). When a reply is still being written the text
 * waits in the composer instead (false), the picks as its chips, for the user to send.
 */
export function sendInChat(text: string, picked: DesignItem[] = []): boolean {
  go("chat");
  let sent = false;
  const designs = sentDesigns(picked);
  for (const fn of senders) sent = fn(text, designs) || sent;
  if (!sent) {
    for (const fn of listeners) fn(text);
    if (picked.length) for (const fn of pickers) fn(picked);
  }
  return sent;
}
