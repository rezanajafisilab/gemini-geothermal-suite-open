// The quick-ask box's question goes to the chat with the designs picked in it with @, as the
// composer sends its own picks (4 Nov: they went as plain text, and the server never saw them).

import { describe, expect, it } from "vitest";

import { askInChat, onAsk, onAskPicks, onSendAsk, sendInChat, sentDesigns } from "./ask";
import type { DesignItem } from "./designList";

const item = (uid: string, label: string): DesignItem => ({
  id: `${uid} · 1D-HP`,
  uid,
  code: "1D-HP",
  label,
  name: label,
  userName: null,
  starred: false,
  origin: "agent",
  picks: [],
  recommended: false,
  inTabs: true,
  verified: true,
  failed: [],
  lcoe: 41.2,
  co2SavingPct: 60,
  run: null,
});
const a1 = item("A1", "Best overall");
const w1 = item("W1", "A1 + 50 °C heating return");

describe("the quick-ask box's @ picks", () => {
  it("are sent with the question, as the composer sends its picks", () => {
    const got: unknown[] = [];
    const off = onSendAsk((text, designs) => (got.push([text, designs]), true));
    expect(sendInChat("Why is it cheaper?", [a1, w1])).toBe(true);
    off();
    expect(got).toEqual([
      [
        "Why is it cheaper?",
        [
          { id: "A1 · 1D-HP", text: sentDesigns([a1])![0].text },
          { id: "W1 · 1D-HP", text: sentDesigns([w1])![0].text },
        ],
      ],
    ]);
    expect(sentDesigns([a1])![0].text).toContain("A1");
    expect(sentDesigns([])).toBeUndefined();
  });

  it("go no further than the question when there are none", () => {
    const got: unknown[] = [];
    const off = onSendAsk((text, designs) => (got.push([text, designs]), true));
    sendInChat("What is a doublet?");
    off();
    expect(got).toEqual([["What is a doublet?", undefined]]);
  });

  it("wait in the composer as its chips when a reply is still being written", () => {
    const texts: string[] = [];
    const picks: DesignItem[][] = [];
    const offs = [onSendAsk(() => false), onAsk((t) => texts.push(t)), onAskPicks((p) => picks.push(p))];
    expect(sendInChat("Compare them", [a1, w1])).toBe(false);
    offs.forEach((off) => off());
    expect(texts).toEqual(["Compare them"]);
    expect(picks).toEqual([[a1, w1]]);
  });

  it("go to the composer with Edit in chat", () => {
    const picks: DesignItem[][] = [];
    const off = onAskPicks((p) => picks.push(p));
    askInChat("About A1: ", [a1]);
    askInChat("About A1: ");
    off();
    expect(picks).toEqual([[a1]]);
  });
});
