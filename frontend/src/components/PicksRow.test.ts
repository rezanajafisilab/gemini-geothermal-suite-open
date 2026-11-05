// The chat card's picks row with the six picks of a search: each one's mark, label, cost bar
// and figures, three to a row.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { Pick } from "../agent/types";
import { PICK_ICONS, PicksRow } from "./ResultCard";

const pick = (key: string, label: string, code: string, lcoe: number, extra: Partial<Pick> = {}): Pick => ({
  key,
  label,
  uid: `A${code.length}`,
  code,
  id: code,
  chosen: false,
  lcoe,
  lcoh: lcoe,
  lcoc: null,
  co2_t: 5000,
  co2_saving_pct: 70,
  capex_meur: 60,
  reliable: false,
  rule: `the rule of ${key}`,
  ...extra,
});

// engine.search(DesignBrief()), 31 Oct.
const SIX = [
  pick("best", "best overall", "1D-HP-EC-N1", 77.4, { chosen: true, reliable: true }),
  pick("cost", "cheapest", "1D-HP-AB", 68.1, { n1_short: 5 }),
  pick("co2", "lowest CO2", "2D-HP-AB-EB-GS", 87.55),
  pick("reliable", "cheapest reliable", "1D-HP-AB-N1", 69.8, { reliable: true }),
  pick("green_reliable", "greenest reliable", "2D-HP-AB-N1-EB-GS", 101.68, { reliable: true }),
  pick("gas_free", "gas-free", "2D-HP-AB-N1-EB", 92.7, { reliable: true }),
];

describe("the picks row", () => {
  const html = renderToStaticMarkup(createElement(PicksRow, { picks: SIX }));

  it("draws all six, each with its own mark", () => {
    expect(html.match(/role="listitem"/g)).toHaveLength(6);
    expect(html.match(/class="pick-icon"/g)).toHaveLength(6);
    expect(new Set(SIX.map((p) => PICK_ICONS[p.key])).size).toBe(6);
    expect(html).toContain("gas-free");
    expect(html).toContain("greenest reliable");
    expect(html).toContain("2D-HP-AB-N1-EB");
  });

  it("gives each a cost bar against the dearest pick", () => {
    const widths = [...html.matchAll(/class="ta-grow" style="width:([\d.]+)%"/g)].map((m) => Number(m[1]));
    expect(widths).toHaveLength(6);
    expect(Math.max(...widths)).toBe(100);
    expect(widths[1]).toBeCloseTo((68.1 / 101.68) * 100, 3);
  });

  it("marks the recommended one and says whether any one unit can be out", () => {
    expect(html.match(/pick-mark/g)).toHaveLength(1);
    expect(html).toContain("one unit out: 5 cases short");
    expect(html.match(/any one unit out: met/g)).toHaveLength(4);
  });
});
