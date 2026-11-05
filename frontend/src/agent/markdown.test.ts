// The answer's Markdown subset: blocks, inlines, citations, file names, and number chips inside
// table cells and list items (Markdown.tsx runs segments() on every text node).

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { parseInline, parseMarkdown, plain, type Block, type Inline } from "./markdown";
import { segments } from "./numbers";
import { emptyChat, reduce, replay, runSources, runText } from "./reducer";
import { parseSse } from "./sse";

const kinds = (blocks: Block[]) => blocks.map((b) => b.type);
const texts = (nodes: Inline[]) => nodes.filter((n) => n.type === "text").map((n) => (n as { text: string }).text);
/** The numbers a run of inlines shows as chips. */
const chips = (nodes: Inline[]) => texts(nodes).flatMap((t) => segments(t).filter((s) => s.num).map((s) => s.text));

describe("blocks", () => {
  it("keeps a template with no Markdown as one paragraph of plain text", () => {
    const text =
      "A1 covers 100% of the heat and 100% of the cold at 41 €/MWh for heat, with 82.2% less CO₂ than gas. The reservoir is 87 °C at 2,500 m; the network runs at 70/40 °C.";
    const blocks = parseMarkdown(text);
    expect(kinds(blocks)).toEqual(["paragraph"]);
    const p = blocks[0] as Extract<Block, { type: "paragraph" }>;
    expect(p.children.every((n) => n.type === "text")).toBe(true);
    expect(plain(p.children)).toBe(text);
  });

  it("splits paragraphs on blank lines and keeps single newlines as line breaks", () => {
    const blocks = parseMarkdown("First line\nsecond line\n\nNext paragraph.");
    expect(kinds(blocks)).toEqual(["paragraph", "paragraph"]);
    const first = (blocks[0] as Extract<Block, { type: "paragraph" }>).children;
    expect(first.map((n) => n.type)).toEqual(["text", "br", "text"]);
  });

  it("reads bullets, numbered lists and indented sub-bullets", () => {
    const blocks = parseMarkdown("Here is what matters:\n- heat 61.8 GWh\n* cold\n  - in summer\n  - from May\n\n3. third\n4. fourth");
    expect(kinds(blocks)).toEqual(["paragraph", "list", "list"]);
    const bullets = blocks[1] as Extract<Block, { type: "list" }>;
    expect(bullets.ordered).toBe(false);
    expect(bullets.items.map((i) => plain(i.children))).toEqual(["heat 61.8 GWh", "cold"]);
    expect(bullets.items[1].sub?.items.map((i) => plain(i.children))).toEqual(["in summer", "from May"]);
    expect(chips(bullets.items[0].children)).toEqual(["61.8 GWh"]);
    const numbered = blocks[2] as Extract<Block, { type: "list" }>;
    expect(numbered).toMatchObject({ ordered: true, start: 3 });
    expect(numbered.items).toHaveLength(2);
  });

  it("draws deeper levels one level down, flat", () => {
    const list = parseMarkdown("- a\n  - b\n    - c\n- d")[0] as Extract<Block, { type: "list" }>;
    expect(list.items.map((i) => plain(i.children))).toEqual(["a", "d"]);
    expect(list.items[0].sub?.items.map((i) => plain(i.children))).toEqual(["b", "c"]);
  });

  it("caps headings at level 3 and never takes #tags for headings", () => {
    const blocks = parseMarkdown("# Big\n#### Small\n#notaheading");
    expect(blocks.slice(0, 2)).toMatchObject([
      { type: "heading", level: 1 },
      { type: "heading", level: 3 },
    ]);
    expect(blocks[2].type).toBe("paragraph");
  });

  it("reads quotes, fenced code and rules", () => {
    expect(kinds(parseMarkdown("> quoted\n\n```\nx = 1\n```\n\n---\nafter"))).toEqual(["quote", "code", "rule", "paragraph"]);
  });
});

describe("tables", () => {
  it("reads a GFM pipe table with alignment, padding short rows and cutting long ones", () => {
    const blocks = parseMarkdown("| Design | Heat | Cost |\n|:---|---:|:-:|\n| A1 | 100% | 41 €/MWh |\n| A2 | 65.4% |\n| A4 | 100% | 63.9 €/MWh | extra |");
    expect(kinds(blocks)).toEqual(["table"]);
    const t = blocks[0] as Extract<Block, { type: "table" }>;
    expect(t.align).toEqual(["left", "right", "center"]);
    expect(t.head.map(plain)).toEqual(["Design", "Heat", "Cost"]);
    expect(t.rows.map((r) => r.map(plain))).toEqual([
      ["A1", "100%", "41 €/MWh"],
      ["A2", "65.4%", ""],
      ["A4", "100%", "63.9 €/MWh"],
    ]);
  });

  it("takes rows without leading and trailing pipes, and \\| as a pipe in a cell", () => {
    const t = parseMarkdown("a | b\n--- | ---\nx \\| y | 2")[0] as Extract<Block, { type: "table" }>;
    expect(t.type).toBe("table");
    expect(t.rows[0].map(plain)).toEqual(["x | y", "2"]);
  });

  it("keeps number chips in cells as in a paragraph: 70/40 °C is a chip, 2,500 m names a well", () => {
    const t = parseMarkdown("| | Network | Well |\n|---|---|---|\n| A1 | 70/40 °C | 2,500 m |\n| Cost | 41 €/MWh | 6/12 °C |")[0] as Extract<Block, { type: "table" }>;
    expect(chips(t.rows[0][1])).toEqual(["70/40 °C"]);
    // segments() keeps distances as text everywhere ("the 1 km doublet, 2,500 m deep").
    expect(chips(t.rows[0][2])).toEqual([]);
    expect(chips(t.rows[0][2])).toEqual(segments("2,500 m").filter((s) => s.num).map((s) => s.text));
    expect(chips(t.rows[1][1])).toEqual(["41 €/MWh"]);
    expect(chips(t.rows[1][2])).toEqual(["6/12 °C"]);
  });

  it("leaves a line with a pipe but no separator as text", () => {
    expect(kinds(parseMarkdown("GPU | CPU switch\nis at the top"))).toEqual(["paragraph"]);
    expect(kinds(parseMarkdown("GPU | CPU\n---"))).toEqual(["paragraph", "rule"]);
  });
});

describe("inlines", () => {
  it("reads bold, italic and code", () => {
    expect(parseInline("a **bold** and *it* and _it_ and `code`")).toEqual([
      { type: "text", text: "a " },
      { type: "strong", children: [{ type: "text", text: "bold" }] },
      { type: "text", text: " and " },
      { type: "em", children: [{ type: "text", text: "it" }] },
      { type: "text", text: " and " },
      { type: "em", children: [{ type: "text", text: "it" }] },
      { type: "text", text: " and " },
      { type: "code", text: "code" },
    ]);
  });

  it("leaves snake_case, formulas and lone stars alone", () => {
    for (const text of ["heat_demand_mw and t_outdoor_c", "COP = η_II · T_E / (T_C − T_E)", "2 * 3 * 4", "a ** b"]) {
      expect(parseInline(text).every((n) => n.type === "text")).toBe(true);
      expect(plain(parseInline(text))).toBe(text);
    }
  });

  it("reads citation markers", () => {
    expect(parseInline("61.8 GWh a year.[^1][^12]")).toEqual([
      { type: "text", text: "61.8 GWh a year." },
      { type: "cite", n: 1 },
      { type: "cite", n: 12 },
    ]);
    expect(parseInline("[^x] and [1]").every((n) => n.type === "text")).toBe(true);
  });

  it("finds file names, but not paths, longer extensions or version numbers", () => {
    const files = (text: string) => parseInline(text).filter((n) => n.type === "file").map((n) => (n as { name: string }).name);
    expect(files("See heating_profile.csv and subsurface.json.")).toEqual(["heating_profile.csv", "subsurface.json"]);
    expect(files("Open `cooling_design.md`, site-photo.JPG or plot.jpeg")).toEqual(["cooling_design.md", "site-photo.JPG", "plot.jpeg"]);
    expect(files("in src/gemini_documentation/source/model_surface_equipment.rst")).toEqual([]);
    expect(files("notes.mdx, qwen3.5:9b and version 1.2.3")).toEqual([]);
    expect(files("**heating_profile.csv**")).toEqual([]);
    expect(parseInline("**heating_profile.csv**")).toEqual([{ type: "strong", children: [{ type: "file", name: "heating_profile.csv" }] }]);
  });

  it("drops escapes' backslashes", () => {
    expect(plain(parseInline("not \\*italic\\* and 1\\. item"))).toBe("not *italic* and 1. item");
  });
});

describe("a recorded-shape answer (answer-markdown.sse)", () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const events = parseSse(readFileSync(join(here, "..", "fixtures", "answer-markdown.sse"), "utf-8"));
  const turn = replay(reduce(emptyChat("m"), { type: "send", turnId: "a", message: "x", at: 0 }), events).turns[0];
  const blocks = parseMarkdown(runText(turn, 0));

  it("parses into a lead, bullets, a table, a heading and a closing paragraph", () => {
    expect(kinds(blocks)).toEqual(["paragraph", "list", "table", "heading", "paragraph"]);
    const table = blocks[2] as Extract<Block, { type: "table" }>;
    expect(table.head.map(plain)).toEqual(["", "Heat pump", "Absorption chiller"]);
    expect(table.rows).toHaveLength(4);
    expect(chips(table.rows[2][1])).toEqual(["70/40 °C"]);
    expect(table.rows[3][1]).toEqual([{ type: "code", text: "HeatpumpBasic" }]);
  });

  it("cites only passages the run sent, and names a file the user can open", () => {
    const cites: number[] = [];
    const files: string[] = [];
    const walk = (nodes: Inline[]) =>
      nodes.forEach((n) => {
        if (n.type === "cite") cites.push(n.n);
        if (n.type === "file") files.push(n.name);
        if (n.type === "strong" || n.type === "em") walk(n.children);
      });
    for (const b of blocks) {
      if (b.type === "paragraph" || b.type === "heading") walk(b.children);
      if (b.type === "list") b.items.forEach((i) => walk(i.children));
    }
    expect(cites).toEqual([1, 2, 2]);
    expect(Math.max(...cites)).toBeLessThanOrEqual(runSources(turn, 0).length);
    expect(files).toEqual(["cooling_design.md"]);
  });
});

describe("math: LaTeX in replies, drawn by KaTeX", () => {
  const maths = (nodes: Inline[]): { tex: string; display: boolean }[] =>
    nodes.flatMap((n) =>
      n.type === "math" ? [{ tex: n.tex, display: n.display }] : n.type === "strong" || n.type === "em" ? maths(n.children) : [],
    );

  it("reads an inline formula between single dollars, as the answerer is told to write it", () => {
    const nodes = parseInline("The heat is $Q = \\dot{m}\\,c_p\\,\\Delta T$, with $c_p$ in J/(kg·K).");
    expect(maths(nodes)).toEqual([
      { tex: "Q = \\dot{m}\\,c_p\\,\\Delta T", display: false },
      { tex: "c_p", display: false },
    ]);
    expect(texts(nodes)).toEqual(["The heat is ", ", with ", " in J/(kg·K)."]);
    // The source keeps its delimiters wherever the text is needed whole.
    expect(plain(nodes)).toBe("The heat is $Q = \\dot{m}\\,c_p\\,\\Delta T$, with $c_p$ in J/(kg·K).");
  });

  it("reads a displayed formula on its own line, on one line or over several", () => {
    const one = parseMarkdown("The flow sets the heat:\n$$Q = \\dot{m}\\,c_p\\,\\Delta T$$\nso more flow, more heat.");
    expect(kinds(one)).toEqual(["paragraph", "math", "paragraph"]);
    expect(one[1]).toEqual({ type: "math", tex: "Q = \\dot{m}\\,c_p\\,\\Delta T" });
    const several = parseMarkdown("$$\n\\dot{m} = \\rho\\,\\dot{V}\n  = 1030 \\times \\frac{300}{3600}\n$$");
    expect(several).toEqual([{ type: "math", tex: "\\dot{m} = \\rho\\,\\dot{V}\n  = 1030 \\times \\frac{300}{3600}" }]);
    // \[ … \] on its own line is the same, and $$ … $$ in the middle of a sentence stays in it.
    expect(parseMarkdown("\\[ P = \\frac{Q}{COP} \\]")).toEqual([{ type: "math", tex: "P = \\frac{Q}{COP}" }]);
    const mid = parseMarkdown("So $$x^2$$ and $$y^2$$ both.");
    expect(kinds(mid)).toEqual(["paragraph"]);
    expect(maths((mid[0] as Extract<Block, { type: "paragraph" }>).children)).toEqual([
      { tex: "x^2", display: true },
      { tex: "y^2", display: true },
    ]);
  });

  it("leaves money alone: a lone $, or one with a space or a digit at the wrong side", () => {
    for (const text of [
      "It costs $5 and $10 a month.",
      "between $20,000 and $30,000",
      "from $5-$10, or $5/$10",
      "US$5 and US$ 10",
      "a $ 5 note and 5 $",
      "only $5",
      "$$ alone",
    ]) {
      const nodes = parseInline(text);
      expect(nodes.every((n) => n.type === "text"), text).toBe(true);
      expect(plain(nodes)).toBe(text);
    }
    expect(kinds(parseMarkdown("It costs $5 and $10.\n\n$$ not closed"))).toEqual(["paragraph", "paragraph"]);
  });

  it("an escaped dollar is a dollar; code keeps its dollars; \\( \\) is inline math", () => {
    expect(plain(parseInline("costs \\$5 and \\$10"))).toBe("costs $5 and $10");
    expect(parseInline("costs \\$5 and \\$10").every((n) => n.type === "text")).toBe(true);
    expect(parseInline("run `echo $HOME$` now")).toEqual([
      { type: "text", text: "run " },
      { type: "code", text: "echo $HOME$" },
      { type: "text", text: " now" },
    ]);
    expect(maths(parseInline("so \\(T_E < T_C\\) holds"))).toEqual([{ tex: "T_E < T_C", display: false }]);
    // An escaped dollar inside a formula doesn't close it.
    expect(maths(parseInline("price $p = \\$5$ each"))).toEqual([{ tex: "p = \\$5", display: false }]);
  });

  it("keeps every other feature around formulas: bold, citations, file names, tables, bullets", () => {
    const nodes = parseInline("**$\\Delta T = 40$ K** from heating_profile.csv.[^1] See [doc1].");
    expect(nodes[0]).toEqual({ type: "strong", children: [{ type: "math", tex: "\\Delta T = 40", display: false }, { type: "text", text: " K" }] });
    expect(nodes.some((n) => n.type === "file" && n.name === "heating_profile.csv")).toBe(true);
    expect(nodes.some((n) => n.type === "cite" && n.n === 1)).toBe(true);
    expect(plain(nodes)).toContain("See [doc1].");
    const blocks = parseMarkdown("| Unit | Rule |\n|---|---|\n| Heat pump | $COP < T_C/(T_C - T_E)$ |\n\n- flow $\\dot{V}$ in m³/h\n- 70/40 °C");
    expect(kinds(blocks)).toEqual(["table", "list"]);
    const table = blocks[0] as Extract<Block, { type: "table" }>;
    expect(maths(table.rows[0][1])).toEqual([{ tex: "COP < T_C/(T_C - T_E)", display: false }]);
    const list = blocks[1] as Extract<Block, { type: "list" }>;
    expect(maths(list.items[0].children)).toEqual([{ tex: "\\dot{V}", display: false }]);
    expect(chips(list.items[1].children)).toEqual(["70/40 °C"]);
  });

  it("numbers inside a formula are not number chips", () => {
    expect(chips(parseInline("$\\Delta T = 40$ K and 13.7 MW"))).toEqual(["13.7 MW"]);
  });

  it("renders with KaTeX, escapes what it shows, and never throws on a broken formula", async () => {
    const { renderMath } = await import("./markdown");
    const ok = renderMath("Q = \\dot{m}\\,c_p\\,\\Delta T", false);
    expect("html" in ok && ok.html.startsWith('<span class="katex">')).toBe(true);
    const shown = renderMath("x^2", true);
    expect("html" in shown && shown.html.includes("katex-display")).toBe(true);
    const bad = renderMath("\\frac{1}{", false);
    expect(bad).toEqual({ error: expect.stringMatching(/^Unexpected end of input/) });
    expect(renderMath("\\unknownmacro x", false)).toEqual({ error: "Undefined control sequence: \\unknownmacro" });
    const text = renderMath("\\text{<script>alert(1)</script>}", false);
    expect("html" in text && !text.html.includes("<script>") && text.html.includes("&lt;script&gt;")).toBe(true);
    // Trust is off: a link or an image is drawn as red text, never as a link or an image (the
    // source stays as text in MathML's annotation, for screen readers and copying).
    const link = renderMath("\\href{javascript:alert(1)}{x}", false);
    expect("html" in link && !/<a[\s>]|href=|<img/.test(link.html) && link.html.includes('mathcolor="#cc0000"')).toBe(true);
  });

  it("the Markdown component draws formulas, shows a broken one as its source, and keeps money as text", async () => {
    const { createElement } = await import("react");
    const { renderToStaticMarkup } = await import("react-dom/server");
    const { Markdown } = await import("../components/Markdown");
    const draw = (text: string) =>
      renderToStaticMarkup(createElement(Markdown, { text, cites: 1, onCite: () => {}, hasSource: () => false, onSource: () => {} }));
    const html = draw("The heat is $Q = \\dot{m}\\,c_p\\,\\Delta T$.\n\n$$\\frac{a}{b}$$\n\nIt costs $5 and $10.[^1]");
    expect(html).toContain('<span class="md-math"><span class="katex">');
    expect(html).toContain('<div class="md-math md-math-block"><span class="katex-display">');
    expect(html).toContain("It costs $5 and $10.");
    expect(html).toContain('aria-label="Source 1"');
    // The source is kept only in MathML's annotation (read aloud, copied), never shown raw.
    expect(html.replace(/<annotation[^>]*>[\s\S]*?<\/annotation>/g, "")).not.toContain("\\dot{m}");
    const broken = draw("Broken: $\\frac{1}{$ here");
    expect(broken).toContain('<code class="md-code md-math-error"');
    expect(broken).toContain("$\\frac{1}{$</code>");
  });
});
