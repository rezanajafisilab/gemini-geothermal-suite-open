// The conversation's designs as one list (picker, designs strip, @ list): sections and search.

import { describe, expect, it } from "vitest";

import { mentionAt, withoutMention } from "../components/Mentions";
import { designSections, itemText, matches, type DesignItem } from "./designList";

const item = (over: Partial<DesignItem>): DesignItem => ({
  id: "A9 · 1D-HP-AB",
  uid: "A9",
  code: "1D-HP-AB",
  label: "Rank 9 in run A",
  name: "1 doublet at 2,500 m",
  userName: null,
  starred: false,
  origin: "agent",
  picks: [],
  recommended: false,
  inTabs: false,
  verified: true,
  failed: [],
  lcoe: 70.1,
  co2SavingPct: 40,
  run: { id: "S1", letter: "A", name: "Run A · Base case", n: 1 },
  ...over,
});

const items = [
  item({ id: "A1 · 1D-HP-EC-N1", uid: "A1", code: "1D-HP-EC-N1", label: "Best overall", picks: ["best"], recommended: true, inTabs: true }),
  item({ id: "A29 · 1D-HP-AB", uid: "A29", label: "Cheapest", picks: ["cost"] }),
  item({ id: "A9 · 1D-HP-AB", uid: "A9", starred: true, label: "Our backup" }),
  item({ id: "B1 · 2D-HP-AB", uid: "B1", code: "2D-HP-AB", label: "Best overall", picks: ["best"], run: { id: "S2", letter: "B", name: "Run B · What-if: 50 °C heating return", n: 2 } }),
  item({ id: "W1 · 1D-HP-EC-N1", uid: "W1", origin: "what_if", label: "A1 + doublet stopped 1 Aug to 4 Sep", run: null, inTabs: true }),
];

describe("the design list", () => {
  it("shows the shortlist, the latest run's picks (and the chosen design), then what-ifs", () => {
    const s = designSections(items);
    expect(s.map((x) => [x.title, x.items.map((i) => i.uid)])).toEqual([
      ["Shortlist", ["A9"]],
      ["Run B · What-if: 50 °C heating return: its picks", ["A1", "B1"]],
      ["What-ifs", ["W1"]],
    ]);
  });

  it("finds any design by its handle, words, code or run, grouped by run", () => {
    const s = designSections(items, "cheap");
    expect(s.map((x) => [x.title, x.items.map((i) => i.uid)])).toEqual([["Run A · Base case", ["A29"]]]);
    expect(designSections(items, "@b1")[0].items[0].uid).toBe("B1");
    expect(matches(items[4], "aug stopped")).toBe(true);
    expect(designSections(items, "nothing like it")).toEqual([]);
  });

  it("names a design by its handle and words", () => {
    expect(itemText(items[0])).toBe("A1 · Best overall");
  });
});

describe("@ in the composer", () => {
  it("reads the word being typed after an @ at the caret", () => {
    expect(mentionAt("why is @che", 11)).toEqual({ start: 7, query: "che" });
    expect(mentionAt("@", 1)).toEqual({ start: 0, query: "" });
    expect(mentionAt("mail me@x", 9)).toBeNull(); // an @ inside a word is no mention
    expect(mentionAt("why is @A1 cheaper", 18)).toBeNull(); // the caret is past it
  });

  it("takes the @word out once picked (the chip shows it)", () => {
    expect(withoutMention("why is @che so cheap?", { start: 7, query: "che" })).toBe("why is so cheap?");
  });
});
