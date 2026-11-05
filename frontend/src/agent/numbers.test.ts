import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { segments, sourcesFor, splitOptions } from "./numbers";
import { answerText, emptyChat, reduce, replay } from "./reducer";
import { parseSse } from "./sse";

const nums = (text: string) => segments(text).filter((s) => s.num).map((s) => s.text);

describe("number chips", () => {
  it("finds the numbers of a design answer, with their units", () => {
    const text =
      "A1 covers 100% of the heat and 100% of the cold at 41 €/MWh for heat and 58 €/MWh for cold, with 82.2% less CO₂ than gas. For comparison: A4 (gas reference) at 63.9 €/MWh, A2 at 65.5 €/MWh.";
    expect(nums(text)).toEqual(["100%", "100%", "41 €/MWh", "58 €/MWh", "82.2%", "63.9 €/MWh", "65.5 €/MWh"]);
    expect(segments(text).map((s) => s.text).join("")).toBe(text);
  });

  it("keeps codes, counts, model tags and CO₂ as text", () => {
    expect(nums("A1, D1 and O2 in 3 steps; CO₂ saving")).toEqual([]);
    expect(nums("I run locally: qwen3:1.7b reads your messages, and qwen3.5:9b plans")).toEqual([]);
    expect(nums("a 4.1 MW heat pump with a COP of 3.6, costs 25.1 M€")).toEqual(["4.1 MW", "3.6", "25.1"]);
  });

  it("reads temperatures, pairs, energy and decimals", () => {
    expect(nums("Its brine reaches only 39.8 °C, below the 70 °C the network needs; 61.8 GWh a year short.")).toEqual([
      "39.8 °C",
      "70 °C",
      "61.8 GWh",
    ]);
    expect(nums("Use 70/40 °C and 6/12 °C.")).toEqual(["70/40 °C", "6/12 °C"]);
    expect(nums("cannot beat a COP of 8.6 (the Carnot limit); real machines reach about 3.6")).toEqual(["8.6", "3.6"]);
    expect(nums("The same 1 km doublet, 2,500 m deep")).toEqual([]);
  });

  it("points each unit at the step that computes it", () => {
    expect(sourcesFor("€/MWh", "")[0]).toBe("economics");
    expect(sourcesFor("%", " less CO₂ than gas")[0]).toBe("economics");
    expect(sourcesFor("%", " of the heat")[0]).toBe("simulate");
    expect(sourcesFor("°C", "")[0]).toBe("doublet");
  });
});

describe("infeasible options", () => {
  it("splits the recorded infeasible answer into the lead and one row per option", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const events = parseSse(readFileSync(join(here, "..", "fixtures", "infeasible.sse"), "utf-8"));
    const chat = replay(reduce(emptyChat("i"), { type: "send", turnId: "a", message: "x", at: 0 }), events);
    const { lead, options } = splitOptions(answerText(chat.turns[0]));
    expect(lead).toMatch(/^No design meets 100% of the heat.*below the 70 °C the network needs\.$/);
    expect(options.map((o) => o.label)).toEqual([
      "The same 1 km doublet with heat pumps and a peak boiler",
      "A 2.2 km doublet under the same limits",
      "A1, the 2.5 km cascade with heat pump, boiler and absorption chiller",
    ]);
    expect(options.map((o) => [o.coverage, o.cost])).toEqual([
      [100, 70.8],
      [65.4, 41.3],
      [100, 41],
    ]);
  });

  it("leaves any other answer whole", () => {
    expect(splitOptions("A1 covers 100% of the heat.")).toEqual({ lead: "A1 covers 100% of the heat.", options: [] });
  });
});

describe("sources and decision options", () => {
  it("splits sources out of a lookup answer, keeping dots inside file names", async () => {
    const { splitSources } = await import("./numbers");
    const text =
      "The initial reservoir temperature is 87 °C (undisturbed, before production cools it, at 2,500 m). Source: the project's subsurface data (subsurface.json).";
    expect(splitSources(text)).toEqual({
      text: "The initial reservoir temperature is 87 °C (undisturbed, before production cools it, at 2,500 m).",
      sources: ["the project's subsurface data (subsurface.json)"],
    });
    expect(splitSources("A1 covers 100% of the heat.").sources).toEqual([]);
  });

  it("reads a decision option's label, coverage and cost", async () => {
    const { parseOption } = await import("./numbers");
    expect(parseOption("A1, the 2.5 km cascade with heat pump, boiler and absorption chiller (100% of the heat at 41 €/MWh)")).toMatchObject({
      label: "A1, the 2.5 km cascade with heat pump, boiler and absorption chiller",
      coverage: 100,
      cost: 41,
    });
    expect(parseOption("A 2.2 km doublet under the same limits (65.4% of the heat at 41.3 €/MWh)")).toMatchObject({ coverage: 65.4, cost: 41.3 });
    expect(parseOption("A 1 km doublet (no heat at all)")).toMatchObject({ coverage: 0, cost: undefined });
    expect(parseOption("Keep my limits and report the shortfall")).toEqual({
      text: "Keep my limits and report the shortfall",
      label: "Keep my limits and report the shortfall",
      summary: "",
    });
  });
});

describe("design codes in a reply", () => {
  it("finds the first challenge or user design code, so a card-less reply can link to its tabs", async () => {
    const { designCodeIn } = await import("./numbers");
    expect(designCodeIn("2D-HP-AB@2500 covers 100% of the heat at 47.2 €/MWh.")).toBe("2D-HP-AB@2500");
    expect(designCodeIn("Against 1D-BO-EC@3000, 2D-HP-AB@2500 is cheaper.")).toBe("1D-BO-EC@3000");
    expect(designCodeIn("Your design U1 needs a 4 MW boiler; 3D-DH-NC would not.")).toBe("U1");
    expect(designCodeIn("1D-BO-EC has no depth yet")).toBe("1D-BO-EC");
  });

  it("ignores the toy model's A-codes, plain numbers and look-alikes", async () => {
    const { designCodeIn } = await import("./numbers");
    expect(designCodeIn("A1 covers 100% of the heat; A2 is 2500 m deep.")).toBeUndefined();
    expect(designCodeIn("4D-HP-AB@2500 and 2D-XX-AB are not codes, nor is SU1 or U1x.")).toBeUndefined();
    expect(designCodeIn("")).toBeUndefined();
  });
});

describe("design codes: the grammar with aquifers and variant flags (30 Oct)", () => {
  it("matches the whole code: flags are never cut off, aquifers may be one per doublet", async () => {
    const { DESIGN_CODE, designCodeIn } = await import("./numbers");
    expect(designCodeIn("I recommend 2D-HP-AB-2I1-ST. It meets heat at 100 °C.")).toBe("2D-HP-AB-2I1-ST");
    expect(designCodeIn("(2D-HP-AB-2I1-ST)")).toBe("2D-HP-AB-2I1-ST");
    expect(designCodeIn("Try 1D-BO-EC@3000+3500-2I-BL-PL, then")).toBe("1D-BO-EC@3000+3500-2I-BL-PL");
    expect(designCodeIn("3D-HP-AB-ST2-IU and 3D-HP-AB-IL")).toBe("3D-HP-AB-ST2-IU");
    expect(designCodeIn("2D-HP-AB-2I12-PU.")).toBe("2D-HP-AB-2I12-PU");
    // A what-if's design id is the code and its change: text links the code.
    expect(designCodeIn("2D-HP-AB · heating return temperature 50 °C")).toBe("2D-HP-AB");
    // A suffix that is not a flag is not part of the code.
    expect(designCodeIn("2D-HP-AB-based plants")).toBe("2D-HP-AB");
    expect(designCodeIn("2D-HP-ABC or 2D-HP-AB-STX")).toBe("2D-HP-AB");
    const all = "2D-HP-AB-2I1-ST beats 1D-HP-EC and U2".match(new RegExp(DESIGN_CODE.source, "g"));
    expect(all).toEqual(["2D-HP-AB-2I1-ST", "1D-HP-EC", "U2"]);
  });

  it("splits a code into its layout and its flags", async () => {
    const { splitCode } = await import("./numbers");
    expect(splitCode("2D-HP-AB-2I1-ST")).toEqual({ base: "2D-HP-AB", flags: ["2I1", "ST"] });
    expect(splitCode("1D-BO-EC@3000+3500-2I-BL")).toEqual({ base: "1D-BO-EC@3000+3500", flags: ["2I", "BL"] });
    expect(splitCode("2D-HP-AB")).toEqual({ base: "2D-HP-AB", flags: [] });
    expect(splitCode("A1")).toEqual({ base: "A1", flags: [] });
    expect(splitCode("U3")).toEqual({ base: "U3", flags: [] });
  });

  it("says what each flag means, the per-doublet ones too", async () => {
    const { flagMeaning } = await import("./numbers");
    expect(flagMeaning("2I")).toBe("Two injectors per doublet");
    expect(flagMeaning("2I1")).toBe("Two injectors on doublet 1 only");
    expect(flagMeaning("2I13")).toBe("Two injectors on doublets 1 and 3");
    expect(flagMeaning("ST")).toBe("A treatment train (separator, filters) per doublet");
    expect(flagMeaning("ST2", 3)).toBe("2 treatment trains (separator, filters) for the 3 doublets");
    expect(flagMeaning("BL")).toBe("The hottest doublet first (base load)");
    expect(flagMeaning("PL")).toMatch(/^Producers open over the lower half/);
    expect(flagMeaning("PU")).toMatch(/^Producers open over the upper half/);
    expect(flagMeaning("IL")).toMatch(/^Injectors open over the lower half/);
    expect(flagMeaning("IU")).toMatch(/^Injectors open over the upper half/);
    expect(flagMeaning("XY")).toBe("XY");
  });

  it("names how doublets differ, or nothing when they are built alike", async () => {
    const { doubletLines } = await import("./numbers");
    const plain = { depth_m: 2500, producer_open: "full", injector_open: "full", injectors: 1, max_flow_m3h: 300, train: 0 };
    // build-doublets.sse: two injectors on doublet 1, a train each (the ST flag says so).
    const built = [
      { ...plain, injectors: 2, train: 0 },
      { ...plain, train: 1 },
    ];
    expect(doubletLines(built)).toEqual(["D1: 2 injectors", "D2: 1 injector"]);
    expect(doubletLines([plain, plain])).toEqual([]);
    expect(doubletLines([plain])).toEqual([]);
    expect(doubletLines(undefined)).toEqual([]);
    // Three doublets on two trains: who shares one, who has its own.
    expect(doubletLines([plain, plain, { ...plain, train: 1, producer_open: "lower" }])).toEqual([
      "D1: producer open over the full height, shared treatment train",
      "D2: producer open over the full height, shared treatment train",
      "D3: producer open over the lower half, own treatment train",
    ]);
    // As a message describes them (the parameters step): what is not standard on each.
    const asked = [
      { depth_m: null, producer_open: "full", injector_open: "full", injectors: 2, max_flow_m3h: null, train: 0 },
      { depth_m: null, producer_open: "full", injector_open: "full", injectors: 1, max_flow_m3h: null, train: 1 },
    ];
    expect(doubletLines(asked, "described")).toEqual(["D1: 2 injectors, own treatment train", "D2: own treatment train"]);
    expect(doubletLines([{ injectors: 1 }], "described")).toEqual(["D1: standard"]);
  });

  it("writes a change as the parameter it sets", async () => {
    const { changeList, shownValue } = await import("./numbers");
    expect(changeList({ heat_return_c: 50.0, exclude: ["heat_pump", "boiler"], trains: "separate" })).toEqual([
      "heat_return_c → 50",
      "exclude → heat_pump, boiler",
      "trains → separate",
    ]);
    expect(changeList(undefined)).toEqual([]);
    expect([shownValue(0.052), shownValue(true), shownValue(null), shownValue([]), shownValue({ a: 1 })]).toEqual(["0.052", "yes", "none", "none", '{"a":1}']);
  });
});
