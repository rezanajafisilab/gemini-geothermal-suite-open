// Links into the Compare tab with designs ticked: #compare/<ids joined by "|">, read back by parseHash.

import { describe, expect, it } from "vitest";

import { parseHash } from "../../workbench/route";
import { compareHref, compareIds } from "./link";

describe("compareHref", () => {
  it("joins the ids with | and encodes them as one route part", () => {
    expect(compareHref(["A1 · 1D-HP-EC-N1", "A11 · 1D-HP-AB"])).toBe("#compare/A1%20%C2%B7%201D-HP-EC-N1%7CA11%20%C2%B7%201D-HP-AB");
    expect(compareHref(["A1"])).toBe("#compare/A1");
  });

  it("is the plain tab with no ids, and drops blanks and repeats", () => {
    expect(compareHref([])).toBe("#compare");
    expect(compareHref(["  ", ""])).toBe("#compare");
    expect(compareHref([" A1 ", "A1", "B1"])).toBe("#compare/A1%7CB1");
  });

  it("comes back as the same ids through the route", () => {
    const ids = ["A1 · 1D-HP-EC-N1", "W2 · 1D-HP-EC-N1", "U1", "B1 · 2D-BO-AB@2500+3000-2I1"];
    const route = parseHash(compareHref(ids));
    expect(route.tab).toBe("compare");
    expect(compareIds(route.design)).toEqual(ids);
  });
});

describe("compareIds", () => {
  it("splits a route's design part, trimmed, without repeats", () => {
    expect(compareIds("A1|A11")).toEqual(["A1", "A11"]);
    expect(compareIds(" A1 | | A1|B2 ")).toEqual(["A1", "B2"]);
    expect(compareIds(null)).toEqual([]);
    expect(compareIds("")).toEqual([]);
  });

  it("reads a link the chat wrote by hand (unencoded ·)", () => {
    expect(compareIds(parseHash("#compare/A1 · 1D-HP-EC-N1|A9 · 1D-HP-AB").design)).toEqual(["A1 · 1D-HP-EC-N1", "A9 · 1D-HP-AB"]);
  });
});
