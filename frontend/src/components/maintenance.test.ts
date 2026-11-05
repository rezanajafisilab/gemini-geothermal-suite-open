// The inputs card's Maintenance section: each doublet's days off, each unit's service, and what the
// card sends back (nothing when nothing changed).

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { InputToggle } from "../agent/types";
import { daysOffProblem, initialMaintenance, initialStops, maintenanceAnswers, relaxedNote, serviceProblem, stopsProblems, type MaintenanceState } from "./inputsForm";
import { MaintenanceEditor, UNIT_INFO, YearStrip, splitUnits } from "./Maintenance";

const toggle: InputToggle = {
  id: "maintenance",
  kind: "maintenance",
  label: "Maintenance",
  value: 0,
  doublets: 2,
  operating_days: 330,
  days_off: [35, 35],
  default_days_off: 35,
  cap_operating_days: 330,
  units: [
    { unit: "heat pump", label: "Heat pump", days: 14, bank: false, mode: "off", ranges: [] },
    { unit: "boiler", label: "Gas boiler", days: 7, bank: true, mode: "off", ranges: [] },
  ],
};

describe("the Maintenance section", () => {
  it("opens with 35 days off a doublet and every service off; sends nothing unchanged", () => {
    const m = initialMaintenance(toggle);
    expect(m.daysOff).toEqual(["35", "35"]);
    expect(m.units.map((u) => u.mode)).toEqual(["off", "off"]);
    expect(maintenanceAnswers(m, m, 35, true)).toEqual({});
  });

  it("sends each doublet's days off when changed, and the plan of the units not off", () => {
    const was = initialMaintenance(toggle);
    const now: MaintenanceState = {
      daysOff: ["50", "35"],
      units: [
        { ...was.units[0], mode: "dates", ranges: [{ from: "2027-05-01", to: "2027-05-14" }] },
        { ...was.units[1], mode: "auto" },
      ],
    };
    const a = maintenanceAnswers(now, was, 35, true);
    expect(JSON.parse(a.doublet_days_off)).toEqual([50, 35]);
    expect(JSON.parse(a.service_plan)).toEqual([
      { unit: "heat pump", mode: "dates", ranges: [[120, 133]] },
      { unit: "boiler", mode: "auto", ranges: [] },
    ]);
  });

  it("with the user's dates the ranges say the days off: no lengths are sent", () => {
    const was = initialMaintenance(toggle);
    expect(maintenanceAnswers({ ...was, daysOff: ["50", "35"] }, was, 35, false)).toEqual({});
  });

  it("fewer days off than the cap leaves is a note, not a problem", () => {
    expect(daysOffProblem("20")).toBeNull();
    expect(relaxedNote(20, 35, 330)).toContain("may run 345 days");
    expect(relaxedNote(40, 35, 330)).toBeNull();
    expect(daysOffProblem("0")).toContain("1 to 265");
    expect(daysOffProblem("ten")).toContain("whole number");
    const short = { mode: "mine" as const, doublets: [{ kind: "ranges" as const, start: "2027-07-01", ranges: [{ from: "2027-07-01", to: "2027-07-20" }] }] };
    expect(stopsProblems(short, 330, undefined, true)).toEqual([null]);
    expect(stopsProblems(short, 330)[0]).toContain("needs 15 more");
  });

  it("a unit's dates: every range in the year and none overlapping", () => {
    const u = { unit: "boiler", label: "Gas boiler", days: 7, bank: true, mode: "dates" as const, ranges: [] as { from: string; to: string }[] };
    expect(serviceProblem(u)).toContain("Add a range");
    expect(serviceProblem({ ...u, ranges: [{ from: "2027-05-01", to: "2027-05-07" }, { from: "2027-05-05", to: "2027-05-10" }] })).toContain("overlap");
    expect(serviceProblem({ ...u, ranges: [{ from: "2027-05-01", to: "2027-05-07" }] })).toBeNull();
    expect(serviceProblem({ ...u, mode: "auto" })).toBeNull();
  });

  it("taking out a unit that opened with a stop says so (off); one that opened with none is left out", () => {
    const was: MaintenanceState = { ...initialMaintenance(toggle), units: initialMaintenance(toggle).units.map((u, k) => (k === 0 ? { ...u, mode: "auto" } : u)) };
    const now: MaintenanceState = { ...was, units: was.units.map((u) => ({ ...u, mode: "off" })) };
    expect(JSON.parse(maintenanceAnswers(now, was, 35, true).service_plan)).toEqual([{ unit: "heat pump", mode: "off", ranges: [] }]);
    const added: MaintenanceState = { ...was, units: was.units.map((u) => ({ ...u, mode: "auto" })) };
    const back = maintenanceAnswers(initialMaintenance(toggle), added, 35, true);
    expect(JSON.parse(back.service_plan)).toEqual([
      { unit: "heat pump", mode: "off", ranges: [] },
      { unit: "boiler", mode: "off", ranges: [] },
    ]);
  });
});

// The section as drawn (4 Nov): one list of units, the doublets always, the others once added.
const SERVER_UNITS = ["heat exchanger", "heat pump", "boiler", "electric boiler", "chillers", "absorption"]; // card_edits.SERVICE_UNITS

describe("the Maintenance list", () => {
  const draw = (m: MaintenanceState) =>
    renderToStaticMarkup(
      createElement(MaintenanceEditor, { toggle, stops: initialStops(toggle), maint: m, operatingDays: 330, problems: [null, null], serverError: null, onStops: () => {}, onMaint: () => {}, id: "m" }),
    );

  it("explains every unit the server plans, in one line", () => {
    for (const u of [...SERVER_UNITS, "doublet"]) expect(UNIT_INFO[u]?.what, u).toMatch(/^[A-Z].{10,70}\.$/);
  });

  it("opens with the doublets (required, 35 days off each) and every other unit as a tile to add", () => {
    const m = initialMaintenance(toggle);
    expect(splitUnits(m)).toEqual({ listed: [], free: [0, 1] });
    const html = draw(m);
    expect(html.match(/<li class="mt-card/g)).toHaveLength(1);
    expect(html).toContain("Doublets (2)");
    expect(html).toContain('<span class="mt-req">Required</span>');
    expect(html).toContain("each is off <b>35 days</b>");
    expect(html.match(/class="mt-add-tile"/g)).toHaveLength(2);
    expect(html).toContain('aria-label="Add a stop for the heat pump: Lifts the brine&#x27;s leftover heat to the network&#x27;s temperature."');
  });

  it("lists a unit once added, with what it is, when it stops, and a button to take it out", () => {
    const m = initialMaintenance(toggle);
    const html = draw({ ...m, units: m.units.map((u, k) => (k === 1 ? { ...u, mode: "dates", ranges: [{ from: "2027-05-01", to: "2027-05-07" }] } : u)) });
    expect(splitUnits({ ...m, units: m.units.map((u, k) => (k === 1 ? { ...u, mode: "auto" } : u)) })).toEqual({ listed: [1], free: [0] });
    expect(html.match(/<li class="mt-card/g)).toHaveLength(2);
    expect(html).toContain("Gas boiler<span class=\"mt-unit-each\"> · each unit</span>");
    expect(html).toContain('aria-label="No stop for the gas boiler"');
    expect(html).toContain('value="2027-05-01"');
    expect(html).toContain('role="img" aria-label="Gas boiler off: 1 May to 7 May"'); // the year strip
    expect(html.match(/class="mt-add-tile"/g)).toHaveLength(1); // only the heat pump left to add
  });

  it("draws the days off on a strip of the year, in proportion", () => {
    const html = renderToStaticMarkup(createElement(YearStrip, { ranges: [[0, 36], null, [200, 199]], label: "Doublet 1" }));
    expect(html).toContain('aria-label="Doublet 1 off: 1 Jan to 6 Feb"');
    expect(html.match(/class="mt-year-bar"/g)).toHaveLength(1);
    expect(html).toContain('style="left:0%;width:10.136986301369863%"');
  });
});
