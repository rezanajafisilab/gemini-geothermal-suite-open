// The N-1 or risk figure (RiskCurve): drawn at its pixel width with named axes and values, a log
// scale of days with a row for none, the target line, and N-1 and the size by risk named (the
// numbers recorded from GET /api/risk?spare=1 on the challenge's recommended design, 4 Nov: with
// a spare ESP on the shelf; as built, with none, the risk size is the N-1 size, 30 MW). The
// tiles beside it price both plans a year.

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { RiskView } from "../../workbench";
import { RiskTiles } from "./OutagesCard";
import { RiskCurve, daysWords, placeName, riskGeometry } from "./RiskCurve";

const view: RiskView = {
  design: "A1 · 1D-HP-EC@3000-N1-FC",
  unit: "boiler_mw",
  unit_words: "gas boiler",
  n1_mw: 30,
  risk_mw: 26.72,
  target_days: 0.1,
  spare_esp: true,
  at_n1: { lole_days: 0, eens_mwh: 0, years_short: 0, base_days: 0 },
  at_risk: { lole_days: 0.093, eens_mwh: 3.557664, years_short: 0.027, base_days: 0 },
  tried: [
    [15, 5.415],
    [22.5, 0.75],
    [26.25, 0.169],
    [26.72, 0.093],
    [27.19, 0.07],
    [28.12, 0.05],
    [30, 0],
  ],
  capex_saved_meur: 0.246,
  n1_plan: { mw: 30, capital_keur: 162.9, om_keur: 125.3, grid_keur: 0, backup_keur: 288.2, design_meur: 7.6722, lost_keur: 0 },
  risk_plan: { mw: 26.72, capital_keur: 145.1, om_keur: 117.4, grid_keur: 0, backup_keur: 262.5, design_meur: 7.6465, lost_keur: 0.43 },
  n1_extra_keur_per_year: 25.7,
  annuity: { discount_rate: 0.052, life_years: 25, crf: 0.07238 },
  spare_keur_per_year: 20,
  not_drawn: [],
  lost_keur_per_year: 0.43,
  lost_eur_per_mwh: 122,
  reliable: true,
  seconds: 2.4,
  source: "LOLE 0.1 day a year",
};

describe("the N-1 or risk figure", () => {
  const g = riskGeometry(view, 600);

  it("has the backup's size on x, in MW, the smallest size tried to N-1 inside the plot", () => {
    expect(g.xTicks).toEqual([16, 18, 20, 22, 24, 26, 28, 30]);
    expect(g.x(15)).toBeGreaterThan(g.left);
    expect(g.x(30)).toBeLessThan(g.right);
    expect(g.x(26.72)).toBeLessThan(g.x(30));
  });

  it("has days short a year on a log scale, decades from 0.01 to 10, and none on a row of its own", () => {
    expect(g.yTicks.map((t) => t.label)).toEqual(["0", "0.01", "0.1", "1", "10"]);
    expect(g.y(0)).toBe(g.zeroY);
    expect(g.y(0.01)).toBe(g.floorY);
    expect(g.zeroY - g.floorY).toBeGreaterThan(10);
    // Each decade the same height; more days higher up.
    expect(g.y(0.1) - g.y(1)).toBeCloseTo(g.y(1) - g.y(10), 6);
    expect(g.y(5.415)).toBeLessThan(g.y(0.093));
  });

  it("is drawn at its pixel width, not stretched, with both axes named and the marks named", () => {
    const html = renderToStaticMarkup(createElement(RiskCurve, { view }));
    expect(html).toMatch(/<svg width="560" height="250" role="img"/);
    expect(html).not.toContain("preserveAspectRatio");
    expect(html).toContain("Days short of heat a year</text>");
    expect(html).toContain("Backup size: the gas boiler, MW</text>");
    expect(html).toContain("One day in ten years (0.1 a year)</text>");
    expect(html).toContain("N-1 · 30 MW</text>");
    expect(html).toContain("By risk · 26.7 MW</text>");
    expect(html.match(/class="risk-dot"/g)).toHaveLength(7);
    // The step into the row of none is dashed (off the log scale).
    expect(html).toContain('class="risk-line is-broken"');
    // Every size tried in a table for screen readers.
    expect(html).toContain("<td>26.72</td><td>0.093</td>");
    expect(html).toContain("<td>30</td><td>none</td>");
  });

  it("prices both plans a year, so what N-1 buys is k€ a year against k€ a year", () => {
    const html = renderToStaticMarkup(createElement(RiskTiles, { view }));
    expect(html).toContain("288 k€ a year (capital 163, O&amp;M 125)");
    expect(html).toContain("263 k€ a year (capital 145, O&amp;M 117)");
    expect(html).toContain("26 <span class=\"u\">k€ a year more</span>");
    expect(html).toContain("0.09 fewer days short a year");
    expect(html).not.toContain("M€ more capital");
  });

  it("says N-1 buys nothing when the risk target needs the N-1 size (as built, no spare ESP)", () => {
    const built: RiskView = {
      ...view,
      spare_esp: false,
      risk_mw: 30,
      at_risk: view.at_n1,
      risk_plan: view.n1_plan,
      n1_extra_keur_per_year: 0,
      tried: [
        [15, 26.661],
        [22.5, 11.463],
        [26.25, 2.438],
        [28.12, 0.61],
        [29.06, 0.304],
        [29.53, 0.304],
        [30, 0],
      ],
    };
    const html = renderToStaticMarkup(createElement(RiskTiles, { view: built }));
    expect(html).toContain("nothing smaller keeps to one day in ten years");
    expect(html).toContain("the risk target needs the N-1 size here");
  });

  it("names a mark where its words keep clear of the line", () => {
    const line: [number, number][] = [
      [0, 0],
      [100, 100],
    ];
    const at = placeName(50, 50, "By risk · 26.7 MW", line, [], [-500, -500, 500, 500]);
    const [x0, y0, x1, y1] = at.box;
    for (let k = 0; k <= 100; k += 3) expect(k >= x0 - 3 && k <= x1 + 3 && k >= y0 - 3 && k <= y1 + 3).toBe(false);
    expect(daysWords(0)).toBe("none");
    expect(daysWords(0.093)).toBe("0.093");
    expect(daysWords(5.415)).toBe("5.4");
  });
});
