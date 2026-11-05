// Lines to idle units are still: a stopped doublet's brine and an idle unit's electricity carry
// nothing that day, so they get no moving dots (the canvas draws them faded).

import { describe, expect, it } from "vitest";

import fixture from "../../fixtures/workbench.json";
import type { Design, GraphNode } from "../../workbench";
import { edgeIdle, nodeIdle, stoppedOn } from "./plant";

const design = (fixture as unknown as { designs: Design[] }).designs[0];
const nodes = new Map<string, GraphNode>(design.graph.nodes.map((n) => [n.id, n]));
const brine = design.graph.edges.filter((e) => e.kind === "brine");
const stopDay = (design.year.stop_ranges?.[0]?.[0]?.[0] ?? 189) + 1 + 5; // 1-based, inside the stop
const runDay = 20; // a January day: the doublet runs

describe("idle lines on the design canvas", () => {
  it("the fixture's doublet is stopped on the stop day and running in January", () => {
    expect(stoppedOn(design, 1, stopDay)).toBe(true);
    expect(stoppedOn(design, 1, runDay)).toBe(false);
  });

  it("every brine line of a stopped doublet is idle; in January they carry brine", () => {
    expect(brine.length).toBeGreaterThan(0);
    expect(brine.every((e) => edgeIdle(design, e, nodes, stopDay))).toBe(true);
    const producer = design.graph.nodes.find((n) => n.type === "producer_well")!;
    expect(nodeIdle(design, producer, runDay)).toBe(false);
    expect(brine.some((e) => !edgeIdle(design, e, nodes, runDay))).toBe(true);
  });

  it("a demand is never idle", () => {
    const demand = design.graph.nodes.find((n) => n.type === "demand_heat")!;
    expect(nodeIdle(design, demand, stopDay)).toBe(false);
  });
});

describe("a bank of equal units (2 Nov)", () => {
  it("fills the units a day needs and outlines the rest", async () => {
    const { bankOf } = await import("./PlantCanvas");
    const node = { id: "boiler", type: "boiler", label: "Gas boiler", values: { units: 3, unit_mw: 10, n1: 1, most_mw: 19.5 }, units: {} } as never;
    expect(bankOf(node)).toMatchObject({ units: 3, running: 2 });
    expect(bankOf(node, 4)).toMatchObject({ running: 1 });
    expect(bankOf(node, 0)).toMatchObject({ running: 0 });
    expect(bankOf(node)!.title).toContain("1 stands by");
    expect(bankOf({ ...(node as object), values: { units: 1, unit_mw: 30 } } as never)).toBeNull();
  });
});
