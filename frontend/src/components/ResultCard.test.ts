// The result card's one decision made in code: a what-if's compact row against the design it
// changed, and the three figures it shows with their differences.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { parseSse } from "../agent/sse";
import type { ResultCard as Card } from "../agent/types";
import { ResultCard, codeParts, compactFigures, designIdOf, isCompact } from "./ResultCard";

const card = (kpis: Record<string, number | null>, extra: Partial<Card> = {}): Card => ({
  alternative: "2D-HP-AB@2500",
  name: "Deep doublet with absorption cascade",
  verified: true,
  checks: { passed: 17, total: 17 },
  kpis: Object.entries(kpis).map(([id, value]) => ({ id, label: id, value, unit: id === "lcoh" ? "€/MWh" : "%" })),
  heat_split_gwh: {},
  cool_split_gwh: {},
  sizes_mw: {},
  ...extra,
});

describe("compact what-if cards", () => {
  const base = card({ heat_coverage: 100, lcoh: 47.2, co2: -69 });
  const colder = card({ heat_coverage: 97.4, lcoh: 49.1, co2: -66 }, { view: "compact", against: base });

  it("only a card the agent marks compact is drawn as one row", () => {
    expect(isCompact(colder)).toBe(true);
    expect(isCompact(base)).toBe(false);
    expect(isCompact(card({}, { view: "full" }))).toBe(false);
  });

  it("shows heat covered, cost of heat and the CO₂ saving, each against the compared design", () => {
    expect(compactFigures(colder)).toEqual([
      { id: "heat_coverage", label: "Heat covered", value: 97.4, unit: "%", delta: -2.6, better: false },
      { id: "lcoh", label: "Cost of heat", value: 49.1, unit: "€/MWh", delta: 1.9, better: false },
      { id: "co2_saving", label: "CO₂ saving", value: 66, unit: "%", delta: -3, better: false },
    ]);
    const warmer = card({ heat_coverage: 100, lcoh: 45.0, co2: -72 }, { view: "compact", against: base });
    expect(compactFigures(warmer).map((f) => [f.delta, f.better])).toEqual([
      [0, undefined],
      [-2.2, true],
      [3, true],
    ]);
  });

  it("without a design to compare with, or a value, there is no difference", () => {
    const alone = card({ heat_coverage: 97.4, lcoh: 49.1, co2: -66 }, { view: "compact" });
    expect(compactFigures(alone).every((f) => f.delta === undefined && f.better === undefined)).toBe(true);
    const noCo2 = card({ heat_coverage: 97.4, lcoh: 49.1 }, { view: "compact", against: base });
    expect(compactFigures(noCo2)[2]).toEqual({ id: "co2_saving", label: "CO₂ saving", value: null, unit: "%" });
    // A reporter that sends the saving itself is read as is.
    expect(compactFigures(card({ co2_saving: 66 }, { view: "compact" }))[2].value).toBe(66);
  });
});

const here = dirname(fileURLToPath(import.meta.url));
/** The result card a recorded stream sent (make_ui_fixtures.py, 30-31 Oct). */
const recorded = (name: string): Card => {
  const events = parseSse(readFileSync(join(here, "..", "fixtures", `${name}.sse`), "utf-8"));
  const e = events.find((x) => x.type === "CUSTOM" && x.name === "result");
  return (e as { value: Card }).value;
};
const draw = (card: Card) => renderToStaticMarkup(createElement(ResultCard, { card }));

describe("design ids, codes and flags", () => {
  it("links a what-if by its id, so the tabs open the what-if and not the design it changed", () => {
    const whatIf = recorded("whatif-return");
    expect(designIdOf(whatIf)).toBe("W2 · 1D-HP-EC-N1-FC");
    expect(designIdOf(whatIf.against!)).toBe("A1 · 1D-HP-EC-N1-FC");
    // Older cards have no design_id: the code, with the change label when there is one.
    expect(designIdOf(card({}))).toBe("2D-HP-AB@2500");
    expect(designIdOf(card({}, { change_label: "gas price 45 EUR/MWh" }))).toBe("2D-HP-AB@2500 · gas price 45 EUR/MWh");
  });

  it("splits the code into its layout and its flags, the card's flags first", () => {
    expect(codeParts(recorded("build-doublets"))).toEqual({ badge: "2D-HP-AB", flags: ["2I1", "ST", "N1", "FC"] });
    expect(codeParts(card({}, { alternative: "1D-BO-EC-2I-BL" }))).toEqual({ badge: "1D-BO-EC", flags: ["2I", "BL"] });
    expect(codeParts(recorded("confirm-run"))).toEqual({ badge: "1D-HP-EC", flags: ["N1", "FC"] });
  });

  it("a full card: the flags as chips with what they mean, a line per doublet when they differ", () => {
    const html = draw(recorded("build-doublets"));
    expect(html).toContain('<span class="alt-badge">2D-HP-AB</span>');
    expect(html).toContain('<span class="design-flag" title="Two injectors on doublet 1 only"><span aria-hidden="true">2I1</span>');
    expect(html).toContain('<span class="design-flag" title="A treatment train (separator, filters) per doublet">');
    expect(html).toContain('<span class="design-flag" title="Reliable plan: boiler and chillers in equal units, sized so that any one unit can be out (N-1)">');
    expect(html).toContain('aria-label="How the doublets differ"><span class="alt"><b>D1</b>2 injectors</span><span class="alt"><b>D2</b>1 injector</span></div>');
    expect(html).toContain('href="#design/A1%20%C2%B7%202D-HP-AB-2I1-ST-N1-FC"');
    // Doublets built alike: no line.
    expect(draw(recorded("confirm-run"))).not.toContain("How the doublets differ");
  });

  it("a what-if's compact card: the change as a chip, the design it was made on, the deltas, its own tabs", () => {
    const html = draw(recorded("whatif-return"));
    expect(html).toMatch(/<span class="change-chip" title="Changed: heat_return_c → 50"><svg[^]*?<\/svg>heating return temperature 50 °C<\/span>/);
    expect(html).toContain('on <span class="alt-code" title="1 doublet at 2,500 m, heat pump top-up and a gas boiler (3 units), electric chillers, sized so that any one unit can be out (N-1): boiler and chillers in equal units">1D-HP-EC-N1-FC</span>');
    expect(html).toContain("against A1 · 1D-HP-EC-N1-FC as designed");
    expect(html).toContain('<span class="delta good">−3.8 €/MWh</span>');
    expect(html).toContain('<span class="delta good">+10.9 points</span>');
    expect(html).toContain('href="#design/W2%20%C2%B7%201D-HP-EC-N1-FC"');
    expect(html).toContain('href="#economics/W2%20%C2%B7%201D-HP-EC-N1-FC"');
    // A change to the plant itself makes another code: from one to the other.
    const moved = draw({ ...recorded("whatif-return"), alternative: "1D-HP-EC-2I-N1", change_label: "injectors per doublet 2", design_id: "W3 · 1D-HP-EC-2I-N1" });
    expect(moved).toMatch(/1D-HP-EC-N1-FC<\/span> <span aria-label="becomes">→<\/span> <span class="alt-code"[^>]*>1D-HP-EC-2I-N1<\/span>/);
  });
});


// Ali, 3 Nov: "not verified" said nothing. A design that fails says what, by how much, and what fixes it.
describe("a design that fails says what happened", () => {
  it("names the check in words, or how many", async () => {
    const { statusWords, checkWords } = await import("../workbench/format");
    expect(statusWords(["Brine cooled by at most 40 K"], false)).toBe("misses the 40 K cap");
    expect(statusWords(["Flow 50-300 m3/h per doublet"], false)).toBe("breaks the 50–300 m³/h flow cap");
    expect(statusWords(["At most 330 days per doublet", "Heat at 100 °C every day"], false)).toBe("fails 2 checks");
    expect(statusWords(["Daily energy balance"], false)).toBe("does not balance");
    expect(statusWords([], true)).toBe("verified");
    expect(checkWords("Brine cooled by at most 40 K").fix).toContain("“Brine cooled by at most” at 40 K (inputs card, Limits)");
    expect(checkWords("Something new").short).toBe("fails “Something new”");
  });

  it("shows a Why it fails panel: each failed check, its value against its limit, the fix", () => {
    const checks = [
      { name: "Daily energy balance", passed: true, detail: "worst day off by 0.0000%", requirement: false },
      { name: "Flow 50-300 m3/h per doublet", passed: false, detail: "50-400 m3/h while running; this run used 400 m3/h as you asked, the cap is 300", requirement: true },
    ];
    const failing = card({ lcoe: 50, heat_coverage: 100 }, { verified: false, checks: { passed: 1, total: 2 }, failed: ["Flow 50-300 m3/h per doublet"] });
    const html = renderToStaticMarkup(createElement(ResultCard, { card: failing, checks }));
    expect(html).toContain("It breaks the 50–300 m³/h flow cap, 1 of 2 checks");
    expect(html).toContain('<section class="why-fails ta-rise" aria-label="Why it fails">');
    expect(html).toContain("<b>Flow 50-300 m3/h per doublet</b>");
    expect(html).toContain("this run used 400 m3/h as you asked, the cap is 300");
    expect(html).toContain("Keep the flow cap at 300 m³/h or less");
    expect(html).not.toContain("<b>Daily energy balance</b>");
    const compact = renderToStaticMarkup(createElement(ResultCard, { card: { ...failing, view: "compact", against: card({}) } }));
    expect(compact).toContain(">breaks the 50–300 m³/h flow cap</span>");
    expect(compact).not.toContain("fails checks");
  });
});
