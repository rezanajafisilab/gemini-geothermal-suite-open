// The claim checker's row: sentences it reworded (5 Nov) as well as those it removed.

import { describe, expect, it } from "vitest";

import { runClaims } from "./reducer";
import type { Turn } from "./types";

const turn = (meta: Record<string, unknown>) => ({ steps: [{ run: 0, name: "claims", meta }], replies: [] }) as unknown as Turn;

describe("claims", () => {
  it("reads the reworded sentences, before and after", () => {
    const c = runClaims(
      turn({ decided_by: "model", checked: 3, supported: 2, removed: 0, reworded: 1, reworded_sentences: [["The peak is 35 MW.", "The peak is 30 MW."]] }),
      0,
    );
    expect(c?.reworded).toEqual([["The peak is 35 MW.", "The peak is 30 MW."]]);
    expect(c?.removed).toBe(0);
  });

  it("has none from an older server", () => {
    const c = runClaims(turn({ decided_by: "model", checked: 2, removed: 1, removed_sentences: ["x"] }), 0);
    expect(c?.reworded).toEqual([]);
    expect(c?.sentences).toEqual(["x"]);
  });
});
