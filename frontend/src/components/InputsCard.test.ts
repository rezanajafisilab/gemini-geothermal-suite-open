// The inputs card on the recorded stream (confirm.sse, make_ui_fixtures.py): the rows by group
// with their kind, the two answers it sends, the box that sends a message instead, the table
// fallback without the card's event, and the line it folds to once answered.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { asksOf, emptyChat, reduce, replay, runConfirm } from "../agent/reducer";
import { parseSse } from "../agent/sse";
import type { AgEvent, Ask } from "../agent/types";
import { CHANGE_OPTION, InputsCard, RESET_OPTION, REVEAL_TOP, RUN_OPTION, afterInputs, confirmOptions, confirmSummary, groupRows, kindCounts, revealTop, splitIntro } from "./InputsCard";

const here = dirname(fileURLToPath(import.meta.url));
const load = (name: string): AgEvent[] => parseSse(readFileSync(join(here, "..", "fixtures", `${name}.sse`), "utf-8"));
const turnOf = (events: AgEvent[]) => replay(reduce(emptyChat("i"), { type: "send", turnId: "t", message: "Design it", at: 0 }), events).turns[0];

const turn = turnOf(load("confirm"));
const ask = asksOf(turn)[0];
const inputs = runConfirm(turn, 0)!.value;
const noop = () => {};
const draw = (props: Partial<Parameters<typeof InputsCard>[0]> = {}) =>
  renderToStaticMarkup(createElement(InputsCard, { ask, inputs, id: "c", active: true, running: false, onAnswer: noop, onSend: noop, ...props }));

describe("the rows", () => {
  it("groups the rows in the order the agent sends them", () => {
    const groups = groupRows(inputs.rows);
    expect(groups.map((g) => [g.name, g.rows.length])).toEqual([
      ["Demand", 2],
      ["Reservoir", 3],
      ["Brine and gas", 3],
      ["Caps", 2],
      ["Networks", 3],
      ["Plant options", 1],
      ["Maintenance", 2],
      ["Costs", 1],
      ["Your request", 1],
    ]);
  });

  it("counts the kinds, in the agent's words", () => {
    expect(kindCounts(inputs.rows, inputs.kinds)).toEqual([
      { id: "data", words: "read from the files", n: 2 },
      { id: "fixed", words: "fixed by the requirements", n: 4 },
      { id: "derived", words: "worked out by Dioscuri", n: 1 },
      { id: "assumed", words: "Dioscuri's assumption", n: 9 },
      { id: "asked", words: "your request", n: 2 },
    ]);
    // A kind the card doesn't know yet is still counted, after the known ones.
    expect(kindCounts([{ group: "X", label: "a", value: "1", source: "", kind: "guessed" }], {})).toEqual([{ id: "guessed", words: "guessed", n: 1 }]);
  });

  it("takes its title from the intro's first sentence, the rest is the table", () => {
    const [title, rest] = splitIntro(ask.value.intro);
    expect(title).toBe("Before I run the design, please check what I read and what I assume.");
    expect(rest).toMatch(/^Run it as it is, or tell me what to change\.\n\n\| Input \| Value \| From \|/);
    expect(splitIntro("Check these")).toEqual(["Check these", ""]);
  });
});

describe("Next brings the card's top into view", () => {
  const fake = (handled: boolean) => {
    const calls: string[] = [];
    const el = { dispatchEvent: (e: Event) => (calls.push(e.type), !handled), scrollIntoView: () => calls.push("own scroll") } as unknown as HTMLElement;
    return { el, calls };
  };
  it("asks the chat's scroller first (it cancels the event)", () => {
    const { el, calls } = fake(true);
    revealTop(el);
    expect(calls).toEqual([REVEAL_TOP]);
  });
  it("scrolls the card itself when nothing handles the event", () => {
    const { el, calls } = fake(false);
    revealTop(el);
    expect(calls).toEqual([REVEAL_TOP, "own scroll"]);
    expect(() => revealTop(null)).not.toThrow();
  });
});

describe("the open card: pages", () => {
  const html = draw();

  it("has a step bar of seven pages and the review, the first page open", () => {
    const tabs = [...html.matchAll(/<button type="button" role="tab"[^>]*aria-selected="(true|false)"[^>]*>.*?<span class="ic-step-name">([^<]+)<\/span>/g)].map((m) => [m[2], m[1]]);
    expect(tabs).toEqual([
      ["Demand", "true"],
      ["Reservoir", "false"],
      ["Brine", "false"],
      ["Networks", "false"],
      ["Prices", "false"],
      ["Request", "false"],
      ["Limits", "false"],
      ["Review", "false"],
    ]);
    expect(html).toContain('<div class="ic-page-head"><h3>Demand</h3>');
    expect(html).not.toContain('class="ic-dot'); // nothing to fix, nothing to warn about
  });

  it("shows each row with where it comes from in words, not a badge, and its value as read", () => {
    expect(html.match(/class="ic-row[ "]/g)).toHaveLength(2);
    expect(html).toContain("111.67 GWh a year, peak 30 MW on 2027-01-28");
    expect(html).toContain('<span class="ic-src src-data"><b><i aria-hidden="true"></i>Read from the files</b>');
    expect(html).toContain('<span class="ic-asread">as read</span>111.67 GWh a year');
    expect(html).toContain('<span class="ic-ico t-heat">'); // the Heat row's icon
    expect(html).toContain('<button type="button" class="file-ref" title="Open GEMINI_Heating_Demand_Daily_2027.csv">');
    expect(html).not.toContain("inputs-kind");
    // The card replaces the table: no Markdown table in it.
    expect(html).not.toContain("md-table");
    expect(html).not.toContain("| Input |");
  });

  it("makes every parameter a box with its explanation, range bar and what follows", () => {
    expect(html).toMatch(/<label class="ic-field-name" id="[^"]+-name" for="([^"]+-heat_demand_scale)">Scale the demand<\/label>/);
    expect(html).toContain("Multiplies the district&#x27;s daily heat demand from the file");
    expect(html).toMatch(/<input id="[^"]+-heat_demand_scale" type="text" inputMode="decimal"[^>]*placeholder="required"[^>]*value="1"\/><span class="unit">times<\/span>/);
    expect(html).toContain('class="ic-bar-typical"');
    expect(html).toContain("111.67 GWh × 1 = 111.67 GWh a year, peak 30 MW.");
    expect(html).toContain('class="ic-more-btn" aria-expanded="false"');
    // One short line visible: the rest behind "more".
    expect(html).not.toContain("More demand needs more doublets");
  });

  it("has Next on every page and Run only on the review; no Change button; a box that sends a message", () => {
    expect(html).not.toContain("ic-run");
    expect(html).not.toContain(CHANGE_OPTION);
    expect(html).toMatch(/class="btn btn-ink ta-btn ta-ink ic-next">Next: Reservoir/);
    expect(html).not.toContain("ic-back"); // the first page
    // Limits after the request (4 Nov): the request's Next goes to Limits, Limits' to the review.
    expect(draw({ page: "request" })).toMatch(/class="btn btn-ink ta-btn ta-ink ic-next">Next: Limits/);
    expect(draw({ page: "limits" })).toMatch(/class="btn btn-ink ta-btn ta-ink ic-next">Review and run/);
    expect(draw({ page: "review" })).toMatch(/<button type="button" class="btn btn-ink ta-btn ta-ink ic-run"><svg[^>]*>.*?<\/svg>Run the design with these inputs<\/button>/);
    expect(html).toContain('placeholder="Or type what to change, e.g. a 50 °C heating return"');
    expect(html).toContain('<form class="inputs-say">');
    expect(html).toContain("Your go-ahead");
  });

  it("says the challenge's caps on the Limits page, and Ali's cooling constraint", () => {
    const out = draw({ page: "limits" });
    expect(out).toContain("Brine cooled by at most");
    expect(out).toContain("How much the brine may be cooled from the producer to the injector (ΔT).");
    // Ali's constraint, in the field's words behind "more", and its cap.
    const cooling = inputs.rows.flatMap((r) => r.fields ?? []).find((f) => f.key === "max_brine_cooling_k")!;
    expect(cooling.help).toContain("can't be more than this below the production temperature");
    expect(cooling.cap?.words).toBe("The challenge allows the brine to be cooled by at most 40 K");
    expect(out).toContain("Injected at 47 °C or warmer (87 − 40).");
    expect(out).toContain('class="ic-bar-cap"');
    expect(out).toContain('<span class="sr-only" id="c-maint">Maintenance</span>'); // the stops and the units' service, in one section
    expect(out.match(/<h4 id="[^"]+">Units&#x27; yearly service<\/h4>/g)).toBeNull(); // shown by Maintenance
  });

  it("explains the networks and their accepted range; the supplies can change, with the challenge's value", () => {
    const out = draw({ page: "networks" });
    expect(out).toContain("The pipes that carry hot water from the plant to the buildings (the supply) and back (the return).");
    const heating = inputs.rows.find((r) => r.label === "Heating network")!;
    expect(heating.help).toContain("Accepted: supply 50 to 130 °C, return 20 to 95 °C and below the supply."); // behind "more"
    expect(out).toContain("130 °C</span>"); // the range bar's end
    expect(out).toMatch(/-heat_supply_c"[^>]*value="100"/);
    expect(heating.fields?.find((f) => f.key === "heat_supply_c")?.cap?.words).toBe("The challenge requires heat at 100 °C"); // behind "more"
    expect(draw({ inputs: { ...inputs, asked: { heat_supply_c: 90 } }, page: "networks" })).toContain("The challenge requires heat at 100 °C: the design will not meet the challenge.");
    expect(out).toContain("Include the district network&#x27;s heat losses"); // its switch, in its row
  });

  it("puts the switches in their rows: the brine's gas on its page, the plant options on the request's", () => {
    const brine = draw({ page: "brine" });
    expect(brine).toContain("Flare all the brine&#x27;s gas instead of burning it in the boiler");
    expect(brine).toContain("Dissolve the brine&#x27;s own CO₂ back into the injected brine");
    expect(brine).toMatch(/-brine_cp_j_kg_k"[^>]*value="3990"/); // the heat capacity, editable
    const request = draw({ page: "request" });
    expect(request.indexOf("Design for")).toBeLessThan(request.indexOf("Free cooling, solar, heat store"));
    expect(request).toContain("Put solar panels at the plant");
    expect(request).toContain('<span class="ic-chips neg" role="group"');
  });

  it("reviews: nothing changed, nothing to fix, what follows", () => {
    const out = draw({ page: "review" });
    expect(out).toContain("Nothing: the design runs on the inputs as read.");
    expect(out).toContain('<div class="ic-tile ok"><b>0</b><span>to fix</span></div>');
    expect(out).toContain("<b>87 °C</b><small>brine at the producer</small>");
    expect(out).toContain("<b>≥ 47 °C</b><small>injected back</small>");
    // Each tile: the icon in its own centred box, the words in their own column beside it (4 Nov:
    // the words' column style took the icon's box too, and its glyph sat at the top).
    expect(out).toMatch(/<div class="ic-follow"><span class="ic-ico t-heat"><svg[^>]*>.*?<\/svg><\/span><span class="ic-follow-text"><b>87 °C<\/b>/);
    expect(out).not.toContain("Next:");
  });

  it("marks a row the last message changed", () => {
    const changed = { ...inputs, changed: ["heat_return_c"], rows: inputs.rows.map((r) => (r.label === "Heating network" ? { ...r, value: "supply 100 °C, return 50 °C", kind: "asked", source: "you", changed: true } : r)) };
    const out = draw({ inputs: changed, page: "networks" });
    expect(out).toContain('<section class="ic-row changed"');
    expect(out).toContain('<span class="ic-src src-asked"><b><i aria-hidden="true"></i>Your request</b></span>');
  });

  it("without the card's event, the agent's own table is the body", () => {
    const out = draw({ inputs: undefined });
    expect(out).toContain("md-table");
    expect(out).toContain("GEMINI_Heating_Demand_Daily_2027.csv");
    expect(out).not.toContain("ic-row");
    expect(out).toContain(RUN_OPTION);
  });
});

describe("the boxes as typed: red blocks the run, amber warns", () => {
  // A card whose draft starts from values the server refused (asked): the same path as typing.
  const typed = (asked: Record<string, unknown>, page: string) => draw({ inputs: { ...inputs, asked }, page });

  it("turns an empty box red, with a dot on its page and the run held back", () => {
    const out = typed({ gradient_c_per_km: "" }, "reservoir");
    expect(out).toMatch(/<div class="ic-field lvl-block" data-key="gradient_c_per_km">/);
    expect(out).toContain('role="alert"><span class="ic-msg-icon"');
    expect(out).toContain("Required: give a value.");
    expect(out).toMatch(/Reservoir<\/span><span class="ic-dot block" aria-hidden="true">/);
    expect(out).toMatch(/<span class="ic-status bad" role="status"><span class="ic-dot-inline block" aria-hidden="true"><\/span>1 input to fix<\/span>/);
    const review = typed({ gradient_c_per_km: "" }, "review");
    expect(review).toContain('class="btn btn-ink ta-btn ta-ink ic-run is-blocked"');
    expect(review).toContain("Show what to fix");
  });

  it("warns outside the challenge's cap, says what follows, and still runs", () => {
    const out = typed({ flow_max_m3h: 400 }, "limits");
    expect(out).toMatch(/<div class="ic-field lvl-warn" data-key="flow_max_m3h">/);
    expect(out).toContain("The challenge allows at most 300 m³/h per doublet: the design will not meet the challenge.");
    expect(out).toContain("about 18.3 MW of heat");
    expect(out).toMatch(/Limits<\/span><span class="ic-dot warn"/);
    expect(out).toContain('<span class="ic-was">was 300 m³/h</span>');
    expect(typed({ flow_max_m3h: 400 }, "review")).toContain("Run with your changes");
  });

  it("refuses a heating return at the supply, on both boxes", () => {
    const out = typed({ heat_supply_c: 90, heat_return_c: 95 }, "networks");
    expect(out).toContain("The return must be below the supply (90 °C): the water comes back cooler than it left.");
    expect(out).toContain("The supply must be above the return (95 °C).");
  });

  it("lists the change, the problem and the warning on the review, each with a way back", () => {
    const out = typed({ flow_max_m3h: 400, pump_efficiency: 1 }, "review");
    expect(out).toContain("<b>Doublets and flow · Flow cap</b> <span class=\"ic-was-now\">300 m³/h</span>");
    expect(out).toContain("<b>Doublets and flow · Pump efficiency</b> No pump turns all its electricity into lift: give less than 100 %.");
    expect(out).toContain("Warnings (it still runs)");
    expect(out).toContain('class="link-btn ic-goto">Limits');
  });
});

describe("answered: one line that says what happened", () => {
  const options = confirmOptions(ask, inputs);
  const answered = (v: string): Ask => ({ ...ask, answers: { confirm: v } });

  it("Run and Change, as the buttons send them", () => {
    expect(options).toEqual([RUN_OPTION, CHANGE_OPTION]);
    expect(confirmSummary(answered(RUN_OPTION), options)).toEqual({ tone: "ok", title: "Inputs confirmed" });
    expect(confirmSummary(answered(CHANGE_OPTION), options)).toEqual({ tone: "amber", title: "Changing an input" });
    // The agent reads any answer that starts with "run" as the go-ahead.
    expect(confirmSummary(answered("run it"), options).title).toBe("Inputs confirmed");
    // "Reset to defaults": nothing ran, the card shows again (5 Nov).
    expect(confirmSummary(answered(RESET_OPTION), options)).toEqual({ tone: "grey", title: "Inputs reset", note: "back to the project's defaults" });
  });

  it("a message instead: how the next turn read it", () => {
    expect(confirmSummary(ask, options, "run")).toEqual({ tone: "ok", title: "Inputs confirmed", note: "by your message" });
    expect(confirmSummary(ask, options, "change")).toEqual({ tone: "amber", title: "Changing an input", note: "as your message asks" });
    expect(confirmSummary(ask, options, "reading")).toEqual({ tone: "busy", title: "Reading your reply" });
    expect(confirmSummary(ask, options, "reset")).toEqual({ tone: "grey", title: "Inputs reset", note: "back to the project's defaults, as your message asks" });
    expect(confirmSummary(ask, options, "refused")).toEqual({ tone: "amber", title: "Nothing changed", note: "your change could not be taken: see the card below" });
    expect(confirmSummary(ask, options, "other")).toEqual({ tone: "grey", title: "Inputs not confirmed", note: "your message asked something else" });
    expect(confirmSummary(ask, options, undefined)).toEqual({ tone: "grey", title: "Inputs not confirmed", note: "you sent a new message" });
    // Nothing skipped it: the agent no longer has the question.
    expect(confirmSummary(ask, options, undefined, false)).toEqual({ tone: "grey", title: "Inputs not confirmed", note: "the question is no longer open" });
  });

  it("folds to the line with the counts, and the inputs open again on request", () => {
    const out = draw({ ask: answered(RUN_OPTION), active: false });
    expect(out).toContain("<strong>Inputs confirmed</strong>");
    expect(out).toContain('<span class="chip">18 inputs · 9 assumed</span>');
    expect(out).toContain('aria-expanded="false"');
    expect(out).toContain("Show the inputs");
    expect(out).not.toContain("inputs-row");
    expect(out).not.toContain(CHANGE_OPTION);
    const skipped = draw({ ask: { ...ask, skipped: true }, active: false, skipped: true, reply: "change" });
    expect(skipped).toContain("<strong>Changing an input</strong>");
    expect(skipped).toContain("as your message asks");
  });
});

// The form on today's streams (confirm-edit, confirm-refused, confirm-applied: make_ui_fixtures.py
// edit_fixtures): the card, then a gradient of 90 °C/km refused (20 days off taken, the cap
// relaxed to 345), then a 50 °C return and doublet 1's two ranges run (the cap back to 330).
const editStream = replay(reduce(emptyChat("e"), { type: "send", turnId: "t", message: "Design it", at: 0 }), load("confirm-edit"));
const edited = editStream.turns[0];
const editAsk = asksOf(edited)[0];
const editInputs = runConfirm(edited, 0)!.value;
const drawEdit = (props: Partial<Parameters<typeof InputsCard>[0]> = {}) =>
  renderToStaticMarkup(createElement(InputsCard, { ask: editAsk, inputs: editInputs, id: "e", active: true, running: false, onAnswer: noop, onSend: noop, ...props }));

describe("the Maintenance section on the Limits page", () => {
  const html = drawEdit({ page: "limits" });

  it("the doublets first (35 days off each, Dioscuri's weeks chosen); no other unit stops until added", () => {
    expect(html).toContain('<div class="mt" role="group"');
    expect(html).toMatch(/<h4 id="[^"]+">Maintenance<\/h4>/); // the stops row, called Maintenance
    expect(html).not.toMatch(/<h4 id="[^"]+">Doublet stops<\/h4>/);
    expect(html).toContain("The challenge runs each doublet at most <b>330 days a year</b>, so each is off <b>35 days</b>");
    expect(html).toContain('<label class="on"><input type="radio" name="e-stops-mode" checked="" value="quiet"/>Quietest weeks (Dioscuri chooses)</label>');
    expect(html.match(/class="mt-day"/g)).toHaveLength(3);
    expect(html.match(/<li class="mt-card[ "]/g)).toHaveLength(1); // the doublets only
    expect(html.match(/class="mt-add-tile"/g)).toHaveLength(6); // every other unit, to add
    expect(html).toContain("<b>Heat pump</b><small>Lifts the brine&#x27;s leftover heat to the network&#x27;s temperature.</small>");
  });

  it("shows each doublet's dates once the user's are chosen: a block, or ranges with their days", () => {
    const toggles = editInputs.toggles!.map((t) => (t.kind === "maintenance" ? { ...t, stops: [[[180, 199], [230, 244]], [[100, 134]]], doublets: 2, days_off: [35, 35] } : t));
    const out = drawEdit({ inputs: { ...editInputs, toggles }, page: "limits" });
    expect(out.match(/class="inputs-stop"/g)).toHaveLength(2);
    expect(out).toContain('value="2027-06-30"');
    expect(out).toContain('<span class="inputs-stop-days">15 days</span>');
  });
});
const refusedAnswer = { confirm: RUN_OPTION, changes: JSON.stringify({ heat_return_c: 50, gradient_c_per_km: 90 }), doublet_stops: "[[[180,199]]]" };
const refusedStream = replay(reduce(editStream, { type: "answer", answers: refusedAnswer, at: 1 }), load("confirm-refused"));
const appliedAnswer = { confirm: RUN_OPTION, changes: JSON.stringify({ heat_return_c: 50 }), doublet_stops: "[[[180,199],[230,244]]]" };
const appliedStream = replay(reduce(refusedStream, { type: "answer", answers: appliedAnswer, at: 2 }), load("confirm-applied"));

describe("what the server refused, and what ran", () => {
  const t = refusedStream.turns[0];
  const asks = asksOf(t);

  it("opens the new card as a form, the refused value and the reason on its field", () => {
    const ask = asks[1];
    const inputs = runConfirm(t, ask.run)!.value;
    // 20 days off is taken (the cap relaxed to 345, said in Caps); only the permeability is refused.
    expect(inputs.errors).toEqual({ gradient_c_per_km: "Between 10 and 80 °C/km." });
    expect(inputs.rows.find((r) => r.label === "Relaxed by you")?.value).toContain("operating days 345 (cap 330)");
    const html = renderToStaticMarkup(createElement(InputsCard, { ask, inputs, id: "r", active: true, running: false, onAnswer: noop, onSend: noop }));
    // It opens on the refused box's page, the value given and the reason on the box.
    expect(html).toMatch(/aria-selected="true"[^>]*>.*?<span class="ic-step-name">Reservoir<\/span>/);
    expect(html).toMatch(/<div class="ic-field lvl-block" data-key="gradient_c_per_km">.*?<input[^>]*aria-invalid="true"[^>]*value="90"\/><span class="unit">°C\/km<\/span>/);
    expect(html).toContain('role="alert"><span class="ic-msg-icon" aria-hidden="true">');
    expect(html).toContain("Between 10 and 80 °C/km.");
    expect(html).toContain("1 input to fix");
    const limits = renderToStaticMarkup(createElement(InputsCard, { ask, inputs, id: "r", active: true, running: false, onAnswer: noop, onSend: noop, page: "limits" }));
    expect(limits).toContain('value="2027-06-30"'); // the 20 days taken, shown as the user's dates
    expect(limits).toContain("may run 345 days, more than the 330-day cap");
    // What passed is applied and marked: the 50 °C return.
    expect(inputs.rows.find((r) => r.label === "Heating network")).toMatchObject({ changed: true, value: "supply 100 °C, return 50 °C" });
    // The first card folds to say that nothing ran yet.
    expect(afterInputs(t, asks[0].run)).toBe(inputs);
    expect(confirmSummary(asks[0], confirmOptions(asks[0], inputs), undefined, true, inputs)).toEqual({ tone: "amber", title: "Not run yet", note: "a change was refused: see the card below" });
    const folded = renderToStaticMarkup(createElement(InputsCard, { ask: asks[0], inputs: runConfirm(t, 0)!.value, after: inputs, id: "f", active: false, running: false, onAnswer: noop, onSend: noop }));
    expect(folded).toContain("<strong>Not run yet</strong>");
  });

  it("folds the last card to the rows that ran, changes marked", () => {
    const done = appliedStream.turns[0];
    const ask = asksOf(done)[1];
    const applied = afterInputs(done, ask.run)!;
    expect(applied.applied).toBe(true);
    // The cap goes back to 330 (35 days off again), so its row is marked too.
    expect(applied.rows.filter((r) => r.changed).map((r) => r.label)).toEqual(["Operating days", "Heating network", "Doublet stops"]);
    const html = renderToStaticMarkup(createElement(InputsCard, { ask, inputs: runConfirm(done, ask.run)!.value, after: applied, id: "a", active: false, running: false, onAnswer: noop, onSend: noop }));
    expect(html).toContain("<strong>Inputs confirmed</strong>");
    expect(html).toContain('<span class="note">with your changes</span>');
    expect(html).toMatch(/<span class="chip">18 inputs · \d+ assumed · 3 changed<\/span>/);
    expect(afterInputs(done, 0)?.applied).toBeUndefined(); // the first answer was refused: nothing ran
  });
});

// Stream M's row (the plan's contract), as the server sends it: the aquifers on the Reservoir page.
describe("a records field: the aquifers' table", () => {
  // confirm-edit: the challenge's default, the known aquifer and two assumed deeper.
  const aq = editInputs.rows.flatMap((r) => r.fields ?? []).find((f) => f.key === "aquifers")!;
  const rows = aq.value as Record<string, number | null>[];
  const asText = (r: Record<string, number | null>) => (aq.columns ?? []).map((c) => (r[c.key] == null ? "" : String(r[c.key])));
  const withDraft = (d: string[][], page = "reservoir") => drawEdit({ inputs: { ...editInputs, asked: { aquifers: d.map((r) => Object.fromEntries((aq.columns ?? []).map((c, j) => [c.key, r[j] === "" ? null : Number(r[j])]))) } }, page });
  const out = drawEdit({ page: "reservoir" });

  it("renders the server's columns, a row per aquifer with what it is and its note", () => {
    expect(out).toContain('<div class="ic-records"><table>');
    expect(out).toContain("Gas-liquid ratio<small>Nm³/m³</small>");
    expect(out).toContain('<th scope="row">1<small class="ic-rec-kind k-known">known</small></th>');
    expect(out).toContain('<small class="ic-rec-kind k-assumed">assumed</small>');
    expect(out).toContain("the project&#x27;s aquifer; 87 °C from the gradient");
    expect(out).toContain('aria-label="aquifer 2, Depth (m)"');
    expect(out).toContain('aria-label="Remove aquifer 2"');
    expect(out).not.toContain('aria-label="Remove aquifer 1"'); // the known one stays
    expect(out).not.toContain("+ Add an aquifer"); // three already, the most
    expect(withDraft(rows.slice(0, 2).map(asText))).toContain("+ Add an aquifer");
  });

  it("turns an empty depth red and says which aquifer and column; other boxes may stay empty (auto)", () => {
    const empty = withDraft([asText(rows[0]), ["", ...asText(rows[1]).slice(1)], asText(rows[2])]);
    expect(empty).toMatch(/<input id="[^"]+-aquifers-1-depth_m" class="bad"[^>]*aria-invalid="true"/);
    expect(empty).toContain("Aquifer 2, depth: required: give a value.");
    expect(empty).toContain("1 input to fix");
    const auto = withDraft([asText(rows[0]), ["3000", "100", "200", "303.13", ""], asText(rows[2])]);
    expect(auto).toMatch(/<input id="[^"]+-aquifers-1-gas_liquid_ratio" class="auto"[^>]*placeholder="auto"/);
    expect(auto).not.toContain("to fix");
  });

  it("lists each aquifer's change on the review", () => {
    const review = withDraft([asText(rows[0]), ["3000", "100", "200", "303.13", "1.2"], asText(rows[2])], "review");
    expect(review).toContain("<b>Aquifer 2 · gas-liquid ratio</b> <span class=\"ic-was-now\">0.8 Nm³/m³</span>");
    expect(review).toContain('<span class="ic-now">1.2 Nm³/m³</span>');
  });

  it("a records field without new_item (any other) needs every box", () => {
    const layers = { ...aq, key: "layers", label: "Layers", new_item: undefined, kinds: undefined, notes: undefined, value: rows.slice(0, 1) };
    const row = { group: "Reservoir", label: "Layers", value: "", source: "", kind: "data", page: "reservoir", fields: [layers] };
    const html = drawEdit({ inputs: { ...editInputs, rows: [...editInputs.rows, row], asked: { layers: [{ ...rows[0], gas_liquid_ratio: null }] } }, page: "reservoir" });
    expect(html).toContain("Layer 1, gas-liquid ratio: required: give a value.");
  });
});

// The user's feedback, 4 Nov: what the message set is marked, and what it affects is said when the card opens.
describe("what you set, and what it affects", () => {
  const mine = { ...inputs, yours: ["heat_return_c"], asked: { heat_return_c: 50 } };

  it("lists each value you set with the boxes linked to it and what it changes in the design", () => {
    const out = draw({ inputs: mine });
    expect(out).toContain('<section class="ic-yours" aria-label="What you set and what it affects">');
    expect(out).toContain("You set 1 input");
    expect(out).toMatch(/class="ic-chip mine strong" title="From your message">Heating network · Return <b>50 °C<\/b>/);
    expect(out).toContain("Doublets and flow · Brine cooled by at most");
    expect(out).toContain('<span class="ic-chip out">the heat pump&#x27;s size and efficiency</span>');
    expect(draw({ inputs: { ...inputs, yours: [] } })).not.toContain("ic-yours"); // nothing set: no banner
    // The fixture's own brief drills only the known aquifer: said in words (it was "Aquifers , "),
    // with what the aquifers are linked to.
    const own = draw();
    expect(own).toContain("Aquifers <b>1 aquifer: 2,500 m (known)</b>");
    expect(own).toMatch(/Aquifers <b>1 aquifer: 2,500 m \(known\)<\/b><\/button><span class="ic-yours-arrow" aria-hidden="true">→<\/span><span class="ic-chip-list"><button type="button" class="ic-chip link">.*?Temperature · Gradient/);
  });

  it("marks the boxes linked to it, on their own pages", () => {
    const limits = draw({ inputs: mine, page: "limits" });
    expect(limits).toMatch(/data-key="max_brine_cooling_k">.*?<button type="button" class="ic-chip linked" title="Linked to Heating network · Return, which you set">/);
    const nets = draw({ inputs: { ...inputs, yours: ["heat_return_c"] }, page: "networks" });
    expect(nets).toMatch(/data-key="heat_return_c">.*?<span class="ic-chip mine">.*?from your message<\/span>/);
  });
});

describe("Reset to defaults and the card's notes (5 Nov)", () => {
  const withDefaults = (atDefaults: boolean) => ({
    ...editInputs,
    at_defaults: atDefaults,
    rows: editInputs.rows.map((r) => ({ ...r, fields: r.fields?.map((f) => ({ ...f, default: f.key === "heat_return_c" ? 60 : f.value })) })),
  });

  it("an older server's card has no reset button", () => {
    expect(drawEdit()).not.toContain("ic-reset-all");
  });

  it("at the defaults the button says so and is off; otherwise it resets", () => {
    expect(drawEdit({ inputs: withDefaults(true) })).toMatch(/<button type="button" class="ic-reset-all" disabled=""[^>]*>.*At the defaults<\/button>/);
    const html = drawEdit({ inputs: withDefaults(false) });
    expect(html).toMatch(/<button type="button" class="ic-reset-all"(?! disabled)[^>]*>.*Reset to defaults<\/button>/);
  });

  it("a value that is not the default has a dot and its own default button", () => {
    const changed = withDefaults(false);
    changed.rows = changed.rows.map((r) => ({ ...r, fields: r.fields?.map((f) => (f.key === "heat_return_c" ? { ...f, value: 50 } : f)) }));
    const html = drawEdit({ inputs: changed, page: "networks" });
    expect(html).toContain('class="ic-default-dot"');
    expect(html).toContain('aria-label="Reset Return to the default, 60 °C"');
    expect(html).toContain("default 60 °C");
    expect(drawEdit({ inputs: withDefaults(false), page: "networks" })).not.toContain("ic-default-dot");
  });

  it("a refused reply is said at the top: nothing changed, why, and what still stands", () => {
    const notice = { kind: "refused", title: "Nothing changed", lines: ["Doublets 4: outside 1 to 3.", "Well depth 100 m: outside 500 to 7,000 m."], offer: "The card still has 3 aquifers at 2,500, 3,000 and 3,500 m." };
    const html = drawEdit({ inputs: { ...editInputs, notice } });
    expect(html).toContain('class="ic-notice refused" role="alert"');
    expect(html).toContain("<li>Doublets 4: outside 1 to 3.</li>");
    expect(html).toContain("<p>The card still has 3 aquifers at 2,500, 3,000 and 3,500 m.</p>");
    const reset = drawEdit({ inputs: { ...editInputs, notice: { kind: "reset", title: "Back to the project's defaults", lines: ["Put back: aquifers."] } } });
    expect(reset).toContain('class="ic-notice reset" role="status"');
  });
});
