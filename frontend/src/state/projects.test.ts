import { describe, expect, it } from "vitest";

import type { ProjectInfo } from "../agent/client";
import { ChatStore } from "./store";
import { CHALLENGE, EXAMPLES, examplesFor, initialsOf, toProject } from "./projects";
import { parseNumber } from "../components/ProjectDialogs";

const info = (over: Partial<ProjectInfo> = {}): ProjectInfo => ({
  id: "riccarton-campus-3f9a01",
  name: "Riccarton campus",
  builtin: false,
  created: 1,
  files: ["heat.csv"],
  reservoir: { depth_m: 2000, temperature_c: 72, pressure_bar: 202.1, permeability_md: 200, thickness_m: 100, gradient_c_per_km: 30 },
  heating: { supply_c: 100, return_c: 60 },
  cooling: { supply_c: 20, return_c: 25 },
  totals: { annual_heat_gwh: 111.67, annual_cool_gwh: 0, peak_heat_mw: 30, peak_cool_mw: 0 },
  notes: [],
  weekly_mw: { heat: [1, 2], cool: [0, 0] },
  ...over,
});

describe("projects", () => {
  it("names a project's avatar by its first words", () => {
    expect(initialsOf("Riccarton campus")).toBe("RC");
    expect(initialsOf("delft")).toBe("DE");
    expect(initialsOf("  ")).toBe("P");
  });

  it("keeps the challenge district's look and tints the users' projects by id", () => {
    const challenge = toProject(info({ id: "challenge", name: "Challenge district 2027", builtin: true }));
    expect(challenge).toMatchObject({ id: "challenge", initials: "CD", bg: CHALLENGE.bg, builtin: true });
    const a = toProject(info());
    expect(a).toMatchObject({ initials: "RC", builtin: false, files: ["heat.csv"] });
    expect(toProject(info()).bg).toBe(a.bg);
  });

  it("keeps the real projects built in beside the challenge under their own ids", () => {
    const hal = toProject(info({ id: "hal-leyweg", name: "Haagse Aardwarmte Leyweg", builtin: true }));
    expect(hal).toMatchObject({ id: "hal-leyweg", initials: "HA", builtin: true });
  });

  it("offers a heating design when the project has no cold", () => {
    const heat = toProject(info({ totals: { annual_heat_gwh: 48, annual_cool_gwh: 0, peak_heat_mw: 12.9, peak_cool_mw: 0 } }));
    expect(examplesFor(heat)[0]).toMatchObject({ title: "Design the heating", text: "Design a geothermal heating system for this district." });
  });

  it("starts the depth comparison at the project's reservoir", () => {
    expect(examplesFor(CHALLENGE)).toBe(EXAMPLES);
    const compare = examplesFor(toProject(info())).find((e) => e.title === "Compare depths")!;
    expect(compare.text).toBe("Compare a 2 km doublet with a 3 km doublet for this district.");
    expect(compare.sub).toBe("The 2,000 m aquifer or deeper, hotter wells");
  });

  it("reads numbers as typed: blank is not given, a decimal comma is a point", () => {
    expect(parseNumber("")).toBeUndefined();
    expect(parseNumber(" 87,5 ")).toBe(87.5);
    expect(parseNumber("2500")).toBe(2500);
    expect(parseNumber("hot")).toBeNull();
  });

  it("forgets a removed project's chats and keeps the others", () => {
    const store = new ChatStore(null);
    const meta = (threadId: string) => ({ threadId, title: threadId, createdAt: 1, updatedAt: 1 });
    store.addChat("gone", meta("a"));
    store.addChat("gone", meta("b"));
    store.addChat("challenge", meta("c"));
    store.removeProject("gone");
    const s = store.getSnapshot();
    expect(s.index.gone).toBeUndefined();
    expect(Object.keys(s.chats)).toEqual(["c"]);
    expect(s.index.challenge.map((m) => m.threadId)).toEqual(["c"]);
  });
});
