// A design's issues on its drawing (5 Nov): which parts glow, how badly, and where a click goes.

import { describe, expect, it } from "vitest";

import type { DesignIssue } from "../../workbench";
import { alertWords, alertsByNode, issueCounts, issueDay, issueTargets, issueUnit, issuesOf } from "./issues";

/** An issue as gemini_agent.issues sends it. */
const issue = (over: Partial<DesignIssue>): DesignIssue => ({
  id: "x-1",
  kind: "heat_short",
  severity: "critical",
  units: [],
  limit: [],
  unit: "Gas boiler",
  what: "Heat short on 4 days in January, up to 2.3 MW",
  why: "",
  when: "26–29 Jan",
  first: 25,
  last: 28,
  day: 27,
  days: 4,
  what_if: false,
  ...over,
});

// A small boiler (heat short in late January, the exchanger and the heat pump flat out), the ESP
// of doublet 1 failing in January (a what-if), and the brine cooled past the cap in February.
const short = issue({ id: "heat_short-1", units: ["boiler", "demand_heat"], limit: ["hex", "heat_pump", "producer_1"] });
const esp = issue({
  id: "failure-2",
  kind: "failure",
  units: ["producer_1", "demand_heat"],
  unit: "Producer 1",
  what: "Doublet 1 (its producer or ESP) out: heat short on 15 days, up to 11.8 MW",
  when: "10–24 Jan",
  first: 9,
  last: 23,
  day: 20,
  days: 15,
  what_if: true,
});
const brine = issue({ id: "cap-3", kind: "cap", severity: "warning", units: ["injector_1"], unit: "Injector 1", what: "Brine of doublet 1 cooled by up to 45 K on 5 days in February", when: "10–14 Feb", first: 40, last: 44, day: 42, days: 5 });
const drawn = ["reservoir", "producer_1", "injector_1", "train_1", "hex", "heat_pump", "gas", "boiler", "demand_heat"];

describe("a design's issues", () => {
  it("come the worst first: demand not met, then what-ifs, then warnings; none from an older server", () => {
    expect(issuesOf({ issues: [brine, esp, short] }).map((i) => i.id)).toEqual(["heat_short-1", "failure-2", "cap-3"]);
    expect(issuesOf({})).toEqual([]);
    expect(issuesOf({ issues: [null as never, { id: "bad" } as never, brine] }).map((i) => i.id)).toEqual(["cap-3"]);
  });

  it("are counted by severity", () => {
    expect(issueCounts([short, esp, brine])).toEqual({ critical: 2, warning: 1 });
    expect(issueCounts([])).toEqual({ critical: 0, warning: 0 });
  });
});

describe("the parts that glow", () => {
  const alerts = alertsByNode([short, esp, brine], drawn);

  it("a part an issue names takes its severity; the demand short is red", () => {
    expect(alerts.get("boiler")).toMatchObject({ severity: "critical", limitOnly: false });
    expect(alerts.get("demand_heat")?.severity).toBe("critical");
    expect(alerts.get("demand_heat")?.issues.map((i) => i.id)).toEqual(["heat_short-1", "failure-2"]);
    expect(alerts.get("injector_1")).toMatchObject({ severity: "warning", limitOnly: false });
  });

  it("a part only at its limit is amber; named by another issue it takes that one's severity", () => {
    expect(alerts.get("hex")).toMatchObject({ severity: "warning", limitOnly: true });
    expect(alerts.get("heat_pump")).toMatchObject({ severity: "warning", limitOnly: true });
    // Producer 1 is flat out on the short days and the unit of the ESP what-if: red, not "at its limit".
    expect(alerts.get("producer_1")).toMatchObject({ severity: "critical", limitOnly: false });
    expect(alerts.get("producer_1")?.issues.map((i) => i.id)).toEqual(["heat_short-1", "failure-2"]);
  });

  it("the worst wins, whatever the order", () => {
    const amber = issue({ id: "w", severity: "warning", units: ["boiler"] });
    expect(alertsByNode([amber, short]).get("boiler")?.severity).toBe("critical");
    expect(alertsByNode([short, amber]).get("boiler")?.severity).toBe("critical");
  });

  it("parts not on the drawing are left out, and parts with no issue have no alert", () => {
    const gone = issue({ units: ["chillers", "demand_cold"], limit: ["absorption"] });
    expect(alertsByNode([gone], drawn).size).toBe(0);
    expect(alertsByNode([gone]).size).toBe(3); // without the drawing, every id
    expect(alerts.has("reservoir")).toBe(false);
    expect(alerts.has("gas")).toBe(false);
  });

  it("say what is wrong in words, never colour alone", () => {
    expect(alertWords(alerts.get("boiler")!, "boiler")).toBe("Demand not met: Heat short on 4 days in January, up to 2.3 MW (26–29 Jan)");
    expect(alertWords(alerts.get("hex")!, "hex")).toBe("At its limit while heat short on 4 days in January, up to 2.3 MW (26–29 Jan)");
    expect(alertWords(alerts.get("producer_1")!, "producer_1")).toBe(
      "Demand not met: at its limit while heat short on 4 days in January, up to 2.3 MW (26–29 Jan); Doublet 1 (its producer or ESP) out: heat short on 15 days, up to 11.8 MW (10–24 Jan), a what-if",
    );
    expect(alertWords(alerts.get("injector_1")!, "injector_1")).toMatch(/^Warning: Brine of doublet 1/);
  });
});

describe("a click on an issue", () => {
  it("picks its first drawn unit and centres on its parts", () => {
    expect(issueUnit(short, drawn)).toBe("boiler");
    expect(issueTargets(short, drawn)).toEqual(["boiler", "demand_heat", "hex", "heat_pump", "producer_1"]);
    const offDrawing = issue({ units: ["chillers", "boiler"] });
    expect(issueUnit(offDrawing, drawn)).toBe("boiler");
    expect(issueUnit(issue({ units: [] }), drawn)).toBeNull();
    expect(issueTargets(issue({ units: ["boiler"], limit: ["boiler", "hex"] }))).toEqual(["boiler", "hex"]);
  });

  it("goes to the worst day (1-based); not for a what-if or a cap over the year", () => {
    expect(issueDay(short)).toBe(28);
    expect(issueDay(esp)).toBeNull();
    expect(issueDay(issue({ day: null, first: 9 }))).toBe(10);
    expect(issueDay(issue({ day: null, first: null, last: null }))).toBeNull();
    expect(issueDay(issue({ day: 364 }))).toBe(365);
    expect(issueDay(issue({ day: 400 }))).toBe(365);
  });
});
