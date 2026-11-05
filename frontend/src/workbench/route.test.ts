import { describe, expect, it } from "vitest";

import { DESIGN_TABS, TABS, TAB_GROUPS, formatHash, hrefFor, parseHash } from "./route";

describe("parseHash", () => {
  it("defaults to the chat", () => {
    expect(parseHash("")).toEqual({ tab: "chat", design: null });
    expect(parseHash("#")).toEqual({ tab: "chat", design: null });
    expect(parseHash("#chat")).toEqual({ tab: "chat", design: null });
  });

  it("reads every tab", () => {
    for (const tab of TABS) expect(parseHash(`#${tab}`)).toEqual({ tab, design: null });
  });

  it("reads a design id after a slash, decoded", () => {
    expect(parseHash("#design/A1")).toEqual({ tab: "design", design: "A1" });
    expect(parseHash("#energy/A1%20%E2%88%9210%20%C2%B0C")).toEqual({ tab: "energy", design: "A1 −10 °C" });
    expect(parseHash("#economics/U2")).toEqual({ tab: "economics", design: "U2" });
  });

  it("takes ids with a slash in them whole", () => {
    expect(parseHash("#design/A%2FB")).toEqual({ tab: "design", design: "A/B" });
  });

  it("is lenient: case, a leading slash, a trailing slash", () => {
    expect(parseHash("#Design/A1")).toEqual({ tab: "design", design: "A1" });
    expect(parseHash("#/compare")).toEqual({ tab: "compare", design: null });
    expect(parseHash("#design/A1/")).toEqual({ tab: "design", design: "A1" });
    expect(parseHash("#design/")).toEqual({ tab: "design", design: null });
  });

  it("sends unknown routes to the chat and ignores an id on the chat", () => {
    expect(parseHash("#nowhere")).toEqual({ tab: "chat", design: null });
    expect(parseHash("#nowhere/A1")).toEqual({ tab: "chat", design: null });
    expect(parseHash("#chat/A1")).toEqual({ tab: "chat", design: null });
  });

  it("keeps a malformed escape as written", () => {
    expect(parseHash("#design/A1%E2")).toEqual({ tab: "design", design: "A1%E2" });
  });
});

describe("formatHash", () => {
  it("writes routes, encoding the id", () => {
    expect(formatHash({ tab: "chat" })).toBe("#chat");
    expect(formatHash({ tab: "design", design: "A1" })).toBe("#design/A1");
    expect(formatHash({ tab: "energy", design: "A1 −10 °C" })).toBe("#energy/A1%20%E2%88%9210%20%C2%B0C");
    expect(formatHash({ tab: "compare", design: null })).toBe("#compare");
    expect(formatHash({ tab: "chat", design: "A1" })).toBe("#chat");
    expect(hrefFor("economics", "A1")).toBe("#economics/A1");
  });

  it("round-trips ids with spaces, minus signs and degrees", () => {
    for (const design of ["A1", "A1 −10 °C", "U1", "D1 +5 °C", "A/B #2"]) {
      expect(parseHash(formatHash({ tab: "design", design }))).toEqual({ tab: "design", design });
    }
  });
});

describe("tab groups", () => {
  it("list every tab once, in the header's order", () => {
    expect(TAB_GROUPS.flatMap((g) => g.tabs)).toEqual([...TABS]);
  });

  it("refetch designs for the one-design and all-design tabs only", () => {
    expect([...DESIGN_TABS].sort()).toEqual(["compare", "design", "economics", "energy", "sensitivity"]);
  });
});
