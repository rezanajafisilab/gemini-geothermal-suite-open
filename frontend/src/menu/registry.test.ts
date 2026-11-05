// The action registry: what each kind of right-clicked thing lists, what is left out where it
// can't work, and that an item calls the app's own action with the right design, tab or text.

import { describe, expect, it } from "vitest";

import { CHAT_HINT, REGISTRY, itemsOf, menuFor, numberSnippet, unitWords } from "./registry";
import type { MenuModel, MenuOps, MenuTarget } from "./types";

const REC = "A1 · 1D-HP-EC-N1";

function fakeOps(over: Partial<MenuOps> = {}) {
  const calls: unknown[][] = [];
  const rec =
    (name: string) =>
    (...args: unknown[]) => {
      calls.push([name, ...args]);
    };
  const ops: MenuOps = {
    ask: rec("ask"),
    openDesign: rec("openDesign"),
    compare: rec("compare"),
    addToTray: rec("addToTray"),
    recommended: () => REC,
    same: (a, b) => a === b || (a === "A1" && b === REC) || (a === REC && b === "A1"),
    canReport: () => true,
    downloadReport: rec("downloadReport"),
    downloadGemini: rec("downloadGemini"),
    downloadPermits: rec("downloadPermits"),
    linkFor: (tab, ref) => `http://app/#${tab}/${encodeURIComponent(ref ?? "")}`,
    copy: rec("copy"),
    jumpToDay: rec("jumpToDay"),
    showEnergy: rec("showEnergy"),
    showCosts: rec("showCosts"),
    vary: rec("vary"),
    device: () => ({ device: "auto", gpu: true, busy: false }),
    setDevice: rec("setDevice"),
    editText: rec("editText"),
    openLink: rec("openLink"),
    meta: () => null,
    star: rec("star"),
    rename: rec("rename"),
    ...over,
  };
  return { ops, calls };
}

const ids = (m: MenuModel) => itemsOf(m).map((i) => i.id);
const item = (m: MenuModel, id: string) => {
  const it = itemsOf(m).find((i) => i.id === id);
  if (!it) throw new Error(`no item ${id} in ${ids(m).join(", ")}`);
  return it;
};

const design = (over: Partial<Extract<MenuTarget, { kind: "design" }>> = {}): MenuTarget => ({ kind: "design", design: { id: "A2 · 1D-HP-AB", name: "A2", sub: "1D-HP-AB" }, ...over });

describe("a design's menu", () => {
  it("opens it in the three one-design tabs, compares it, asks about it, reports it and copies its link", () => {
    const { ops, calls } = fakeOps();
    const m = menuFor(design(), ops);
    expect(m.title).toBe("A2");
    expect(ids(m)).toEqual(["open-design", "open-energy", "open-economics", "tray", "compare-rec", "why", "what-if", "failure", "pdf", "permits", "gemini", "copy-at", "link"]);
    void item(m, "open-energy").run();
    void item(m, "compare-rec").run();
    void item(m, "tray").run();
    void item(m, "what-if").run();
    void item(m, "pdf").run();
    void item(m, "link").run();
    expect(calls).toEqual([
      ["openDesign", "A2 · 1D-HP-AB", "energy"],
      ["compare", ["A2 · 1D-HP-AB", REC]],
      ["addToTray", "A2 · 1D-HP-AB"],
      ["ask", "What if A2 "],
      ["downloadReport", "A2 · 1D-HP-AB"],
      ["copy", "http://app/#design/A2%20%C2%B7%201D-HP-AB", "Link"],
    ]);
  });

  it("puts its questions in the composer (tagged chat), never sends or computes them", () => {
    const { ops, calls } = fakeOps();
    const m = menuFor(design(), ops);
    for (const id of ["why", "what-if", "failure"]) expect(item(m, id).hint).toBe(CHAT_HINT);
    void item(m, "why").run();
    void item(m, "failure").run();
    expect(calls.map((c) => c[0])).toEqual(["ask", "ask"]);
    expect(String(calls[0][1])).toMatch(/^Why A2\?/);
    expect(String(calls[1][1])).toMatch(/A2's largest heat unit fails for 14 days/);
  });

  it("doesn't offer to compare the recommended design with itself, nor a report without a server", () => {
    const { ops } = fakeOps({ canReport: () => false });
    const m = menuFor({ kind: "design", design: { id: "A1" } }, ops);
    expect(ids(m)).not.toContain("compare-rec");
    expect(ids(m)).not.toContain("pdf");
  });

  it("without a recommended design (no workbench yet) leaves the comparison out", () => {
    const { ops } = fakeOps({ recommended: () => null });
    expect(ids(menuFor(design(), ops))).not.toContain("compare-rec");
  });

  it("on the Compare tab ticks in place, refuses a fifth, and can show only its scenario", () => {
    const { ops, calls } = fakeOps();
    let toggled = 0;
    let only = 0;
    const ticked = menuFor(design({ tray: { ticked: true, toggle: () => toggled++ }, onlyScenario: () => only++ }), ops);
    expect(item(ticked, "tray").label).toBe("Take out of the Compare tray");
    void item(ticked, "tray").run();
    void item(ticked, "only-scenario").run();
    expect([toggled, only, calls.length]).toEqual([1, 1, 0]);
    const full = menuFor(design({ tray: { ticked: false, toggle: () => toggled++, full: true } }), ops);
    expect(item(full, "tray").disabled).toBe(true);
    expect(item(full, "tray").why).toBe("four are ticked");
  });
});

describe("the chat's menus", () => {
  it("a number: where it comes from (with the words around it), copy with its unit, the step it came from", () => {
    const { ops, calls } = fakeOps();
    let shown = 0;
    const m = menuFor({ kind: "number", text: "42.4 €/MWh", unit: "€/MWh", before: "The cost of heat and cold is ", after: ", 17% cheaper than gas.", showSource: () => shown++ }, ops);
    expect(ids(m)).toEqual(["source", "where", "copy"]);
    void item(m, "source").run();
    void item(m, "where").run();
    void item(m, "copy").run();
    expect(shown).toBe(1);
    expect(calls[0]).toEqual(["ask", "Where does the 42.4 €/MWh in “The cost of heat and cold is 42.4 €/MWh, 17% cheaper” come from?"]);
    expect(calls[1]).toEqual(["copy", "42.4 €/MWh", "42.4 €/MWh"]);
  });

  it("a number that is a parameter can be varied in Sensitivity; a result can't", () => {
    const { ops, calls } = fakeOps();
    const gas = menuFor({ kind: "number", text: "30 €/MWh", unit: "€/MWh", before: "What if gas cost ", after: "?" }, ops);
    void item(gas, "vary").run();
    expect(calls).toEqual([["vary", "gas_price"]]);
    const cost = menuFor({ kind: "number", text: "42.4 €/MWh", unit: "€/MWh", before: "The cost of heat is ", after: "." }, ops);
    expect(ids(cost)).not.toContain("vary");
  });

  it("your message: edit and resend in the composer, resend here or on the other device", () => {
    let sent = 0;
    const { ops, calls } = fakeOps();
    const m = menuFor({ kind: "message", text: "Design it", resend: () => sent++ }, ops);
    expect(ids(m)).toEqual(["edit", "resend", "resend-cpu", "copy"]);
    expect(item(m, "resend").label).toBe("Resend on the GPU");
    void item(m, "edit").run();
    void item(m, "resend-cpu").run();
    void item(m, "resend").run();
    expect(calls).toEqual([["ask", "Design it"], ["setDevice", "cpu"]]);
    expect(sent).toBe(2);
  });

  it("your message on the CPU offers the GPU only when there is one, and waits for a reply being written", () => {
    const noGpu = fakeOps({ device: () => ({ device: "cpu", gpu: false, busy: false }) });
    expect(ids(menuFor({ kind: "message", text: "x", resend: () => {} }, noGpu.ops))).toEqual(["edit", "resend", "copy"]);
    const busy = fakeOps({ device: () => ({ device: "cpu", gpu: true, busy: true }) });
    const m = menuFor({ kind: "message", text: "x", resend: () => {} }, busy.ops);
    expect(item(m, "resend-gpu").disabled).toBe(true);
    expect(item(m, "resend").disabled).toBe(true);
    expect(item(m, "edit").disabled).toBeFalsy();
  });

  it("an answer: copy as Markdown, flag a statement (the selection when there is one)", () => {
    const { ops, calls } = fakeOps();
    const plain = menuFor({ kind: "answer", markdown: "**A1** costs 42 €/MWh." }, ops);
    expect(ids(plain)).toEqual(["copy-md", "flag"]);
    void item(plain, "flag").run();
    const sel = menuFor({ kind: "answer", markdown: "x", selection: "  the boiler is 20 MW " }, ops);
    expect(ids(sel)).toEqual(["copy-sel", "copy-md", "flag"]);
    void item(sel, "flag").run();
    expect(calls).toEqual([
      ["ask", "This statement looks wrong: "],
      ["ask", "This statement looks wrong: “the boiler is 20 MW”. "],
    ]);
  });
});

describe("the tabs' menus", () => {
  const unit: MenuTarget = {
    kind: "unit",
    design: { id: REC, name: "A1" },
    node: { id: "heat_pump", type: "heatpump", label: "Heat pump" },
    sizeMw: 4.2,
    inspect: () => {},
    edit: { label: "Change its size", run: () => {} },
    energy: { side: "heat", series: "hp" },
    costs: ["Heat pump", "Electricity: heat pump"],
  };

  it("a unit of the plant: inspect, change, out for 14 days, a bigger size, its year, its cost lines", () => {
    const { ops, calls } = fakeOps();
    const m = menuFor(unit, ops);
    expect(ids(m)).toEqual(["inspect", "edit", "out", "bigger", "energy", "costs"]);
    expect(item(m, "bigger").label).toBe("What if it were 6.3 MW");
    for (const id of ["out", "bigger", "energy", "costs"]) void item(m, id).run();
    expect(calls).toEqual([
      ["ask", "What if the heat pump of A1 is out for 14 days?"],
      ["ask", "What if the heat pump of A1 were 6.3 MW instead of 4.2 MW?"],
      ["showEnergy", REC, "heat", "hp"],
      ["showCosts", REC, ["Heat pump", "Electricity: heat pump"]],
    ]);
  });

  it("a well keeps its own name; a unit with no size, year or costs lists only what works", () => {
    const { ops, calls } = fakeOps();
    const m = menuFor({ kind: "unit", design: { id: "A1" }, node: { id: "producer_1", type: "producer_well", label: "Producer 1, lower half open" } }, ops);
    expect(ids(m)).toEqual(["out"]);
    void item(m, "out").run();
    expect(calls).toEqual([["ask", "What if Producer 1 of A1 is out for 14 days?"]]);
    expect(unitWords("Gas boiler")).toBe("the gas boiler");
    const demand = menuFor({ kind: "unit", design: { id: "A1" }, node: { id: "demand_heat", type: "demand_heat", label: "Heat demand" }, energy: { side: "heat", series: null } }, ops);
    expect(ids(demand)).toEqual(["energy"]);
  });

  it("the canvas: fit the view and full screen", () => {
    const m = menuFor({ kind: "canvas", fit: () => {}, fullScreen: { on: false, toggle: () => {} } }, fakeOps().ops);
    expect(ids(m)).toEqual(["fit", "full"]);
    expect(item(m, "full").hint).toBe("F");
  });

  it("a day of a chart: the Design player on that day (1-based), a failure from it, its values", () => {
    const { ops, calls } = fakeOps();
    const m = menuFor({ kind: "day", design: { id: REC, name: "A1" }, day: 11, label: "12 January", values: "12 January: Geothermal 10 MW" }, ops);
    for (const id of ["jump", "failure", "copy"]) void item(m, id).run();
    expect(calls).toEqual([
      ["jumpToDay", REC, 12],
      ["ask", "What if A1's largest heat unit fails on 12 January for 14 days?"],
      ["copy", "12 January: Geothermal 10 MW", "Values"],
    ]);
  });

  it("a legend entry: show only its series, then all again", () => {
    const seen: string[] = [];
    const t = (only: boolean): MenuTarget => ({ kind: "series", label: "Heat pump", only, showOnly: () => seen.push("only"), showAll: () => seen.push("all") });
    void item(menuFor(t(false), fakeOps().ops), "only").run();
    void item(menuFor(t(true), fakeOps().ops), "all").run();
    expect(seen).toEqual(["only", "all"]);
  });

  it("a cost line: why so much, its price when it has one, Sensitivity when a parameter varies it", () => {
    const { ops, calls } = fakeOps();
    let opened = 0;
    const m = menuFor({ kind: "cost", design: { id: REC, name: "A1" }, side: "heat", item: "Gas", eur: "12.5", total: "41.3", price: { label: "Gas", open: () => opened++ }, sensParam: "gas_price" }, ops);
    expect(ids(m)).toEqual(["why", "price", "vary", "copy"]);
    for (const id of ["why", "price", "vary"]) void item(m, id).run();
    expect(opened).toBe(1);
    expect(calls).toEqual([
      ["ask", "Why is “Gas” 12.5 €/MWh of A1's cost of heat (41.3 €/MWh in all)? What drives it?"],
      ["vary", "gas_price", REC],
    ]);
    const bare = menuFor({ kind: "cost", design: { id: "A1" }, side: "cold", item: "Chiller O&M", eur: "1.2", total: "30" }, ops);
    expect(ids(bare)).toEqual(["why", "copy"]);
  });

  it("a column: sort either way (the current way greyed), its filter where the toolbar has one", () => {
    const set: string[] = [];
    const m = menuFor({ kind: "column", label: "CO₂", sort: { dir: "asc", set: (d) => set.push(d) }, filter: { label: "Show only designs with N-1 met", on: true, toggle: () => set.push("filter") } }, fakeOps().ops);
    expect(item(m, "asc").disabled).toBe(true);
    expect(item(m, "filter").label).toBe("Show every design again");
    void item(m, "desc").run();
    void item(m, "filter").run();
    expect(set).toEqual(["desc", "filter"]);
    expect(itemsOf(menuFor({ kind: "column", label: "Scenario" }, fakeOps().ops))).toEqual([]);
  });

  it("a tornado bar: a what-if at either end of its range, for the design the runs vary", () => {
    const { ops, calls } = fakeOps();
    const m = menuFor({ kind: "bar", design: "A1", param: "gas_price", label: "Gas price", low: "20 €/MWh", high: "60 €/MWh" }, ops);
    void item(m, "low").run();
    void item(m, "high").run();
    expect(calls).toEqual([
      ["ask", "What if the gas price were 20 €/MWh for A1?"],
      ["ask", "What if the gas price were 60 €/MWh for A1?"],
    ]);
  });

  it("a step of a run: its tool call only when it made one; a source: open it when it can be", () => {
    const { ops } = fakeOps();
    expect(ids(menuFor({ kind: "step", label: "Plan", json: "{}" }, ops))).toEqual(["copy-json"]);
    expect(ids(menuFor({ kind: "step", label: "Inputs", code: "inputs(project, brief)", json: "{}", details: { open: false, toggle: () => {} } }, ops))).toEqual(["copy-call", "copy-json", "details"]);
    expect(ids(menuFor({ kind: "source", title: "a.md", citation: "docs/a.md, Wells" }, ops))).toEqual(["copy-cite", "ask"]);
    expect(ids(menuFor({ kind: "source", title: "a.csv", citation: "a.csv", text: "t", open: { label: "Open a.csv", run: () => {} } }, ops))).toEqual(["open", "copy-cite", "copy-text", "ask"]);
  });

  it("has a builder for every kind, and each menu has a title", () => {
    expect(Object.keys(REGISTRY).sort()).toEqual(["answer", "bar", "canvas", "chat", "column", "cost", "day", "design", "link", "message", "number", "selection", "series", "source", "step", "text", "unit"]);
    expect(menuFor(design(), fakeOps().ops).title).toBeTruthy();
  });

  it("quotes a few words either side of a number", () => {
    expect(numberSnippet("70/40 °C", "Design heating and cooling for the district with ", " heating and 6/12 °C cooling.")).toBe("heating and cooling for the district with 70/40 °C heating and 6/12");
    expect(numberSnippet("41 €/MWh", "Gas alone. A1 costs ", ". It is cheaper.")).toBe("A1 costs 41 €/MWh");
  });
});

describe("text boxes, links and selected text (the browser's menu never shows)", () => {
  const field = (value: string, readOnly = false) => ({ value, readOnly }) as unknown as HTMLInputElement;

  it("a text box with a selection cuts, copies, pastes and selects all", () => {
    const { ops, calls } = fakeOps();
    const t: MenuTarget = { kind: "text", field: field("hello world"), selection: "world", start: 6, end: 11, editable: true };
    const m = menuFor(t, ops);
    expect(ids(m)).toEqual(["cut", "copy", "paste", "select-all"]);
    itemsOf(m).find((i) => i.id === "cut")!.run();
    expect(calls).toEqual([["editText", t, "cut"]]);
  });

  it("without a selection, cut and copy say why they are off; a read-only box has no cut or paste", () => {
    const { ops } = fakeOps();
    const none = menuFor({ kind: "text", field: field("x"), selection: "", start: 0, end: 0, editable: true }, ops);
    expect(itemsOf(none).find((i) => i.id === "copy")).toMatchObject({ disabled: true, why: "nothing selected" });
    const ro = menuFor({ kind: "text", field: field("x", true), selection: "x", start: 0, end: 1, editable: false }, ops);
    expect(ids(ro)).toEqual(["copy", "select-all"]);
  });

  it("selected text copies or starts a question; a link opens, opens in a new tab or copies", () => {
    const { ops, calls } = fakeOps();
    const sel = menuFor({ kind: "selection", text: "the boiler gives 42.9 %" }, ops);
    expect(ids(sel)).toEqual(["copy", "ask"]);
    itemsOf(sel)[1].run();
    expect(calls.at(-1)).toEqual(["ask", "About “the boiler gives 42.9 %”: "]);
    const link = menuFor({ kind: "link", href: "https://example.org/x", text: "a source" }, ops);
    expect(ids(link)).toEqual(["open", "open-new", "copy-link"]);
    itemsOf(link)[1].run();
    expect(calls.at(-1)).toEqual(["openLink", "https://example.org/x", true]);
  });
});

