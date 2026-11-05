// The action registry: what each kind of right-clicked thing offers. One function per kind turns a
// MenuTarget into the menu's sections, using the app's own actions (MenuOps: open a tab, the
// Compare tray, copy, the PDF report, a question in the composer). An item is only listed when it
// can work end to end here: no PDF without a server, no "compare with the recommended" on the
// recommended design, no price to change on a line that uses none. What-ifs, failures and "why"
// are questions put in the composer for the user to send; nothing is computed here.

import { sensParamOfNumber } from "./domain";
import type { DesignRef, MenuItem, MenuModel, MenuOps, MenuSection, MenuTarget } from "./types";

/** The tag on items that put a question in the chat's composer (the user sends it). */
export const CHAT_HINT = "chat";

const nameOf = (d: DesignRef) => d.name?.trim() || d.id;
const lowerFirst = (s: string) => (/^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s);
const clip = (s: string, n: number) => {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n - 1).trimEnd()}…` : t;
};
/** "1.5 × 4.2 MW" in one decimal at most: 6.3. */
const mw = (v: number) => (Math.round(v * 10) / 10).toLocaleString("en-US");

/** "the heat pump", but "Producer 1" (a well's own name). */
export function unitWords(label: string): string {
  const l = label.split(",")[0].trim();
  return /\d/.test(l) ? l : `the ${lowerFirst(l)}`;
}

/** An item, or a falsy value where it doesn't apply. */
type Maybe = MenuItem | null | undefined | false | "" | 0;

function sections(...lists: Maybe[][]): MenuSection[] {
  return lists.map((l) => ({ items: l.filter((x): x is MenuItem => !!x) })).filter((s) => s.items.length > 0);
}

// ------------------------------------------------------------------ designs

/** "Open in Design / Energy / Economics", the Compare tray, "why", a what-if, a failure, the PDF and the link. */
export function designMenu(t: Extract<MenuTarget, { kind: "design" }>, ops: MenuOps): MenuModel {
  const d = t.design;
  const name = nameOf(d);
  const rec = ops.recommended();
  const isRec = !!rec && ops.same(rec, d.id);
  const meta = ops.meta(d.id);
  return {
    title: name,
    sub: d.sub && d.sub !== name ? d.sub : d.id !== name ? d.id : undefined,
    sections: sections(
      [
        { id: "open-design", label: "Open in Design", icon: "design", run: () => ops.openDesign(d.id, "design") },
        { id: "open-energy", label: "Open in Energy", icon: "energy", run: () => ops.openDesign(d.id, "energy") },
        { id: "open-economics", label: "Open in Economics", icon: "economics", run: () => ops.openDesign(d.id, "economics") },
      ],
      [
        t.tray
          ? {
              id: "tray",
              label: t.tray.ticked ? "Take out of the Compare tray" : "Add to the Compare tray",
              icon: t.tray.ticked ? "untray" : "tray",
              run: t.tray.toggle,
              disabled: !t.tray.ticked && !!t.tray.full,
              why: !t.tray.ticked && t.tray.full ? "four are ticked" : undefined,
            }
          : { id: "tray", label: "Add to the Compare tray", icon: "tray", run: () => ops.addToTray(d.id) },
        rec && !isRec && { id: "compare-rec", label: "Compare with the recommended", icon: "compare", run: () => ops.compare([d.id, rec]) },
        t.onlyScenario && { id: "only-scenario", label: "Show only its scenario", icon: "scenario", run: t.onlyScenario },
      ],
      [
        {
          id: "why",
          label: "Ask “why this design?”",
          icon: "ask",
          hint: CHAT_HINT,
          run: () => ops.ask(`Why ${name}? What makes it a good choice here, and what does it give up?`),
        },
        { id: "what-if", label: "Run a what-if on it", icon: "whatif", hint: CHAT_HINT, run: () => ops.ask(`What if ${name} `) },
        {
          id: "failure",
          label: "Simulate a unit failing",
          icon: "failure",
          hint: CHAT_HINT,
          run: () => ops.ask(`What if ${name}'s largest heat unit fails for 14 days in January?`),
        },
      ],
      [
        meta && {
          id: "star",
          label: meta.starred ? "Take it off the shortlist" : "Star it: add to the shortlist",
          icon: "star",
          run: () => ops.star(d.id, !meta.starred),
        },
        meta && { id: "rename", label: meta.name ? "Rename it" : "Give it a name", icon: "edit", run: () => ops.rename(d.id, meta.name) },
      ],
      [
        ops.canReport() && { id: "pdf", label: "Operator's report (PDF)…", icon: "pdf", run: () => ops.downloadReport(d.id) },
        ops.canReport() && { id: "permits", label: "Permit and subsidy pack (PDF)…", icon: "pdf", run: () => ops.downloadPermits(d.id) },
        ops.canReport() && { id: "gemini", label: "GEMINI project (JSON)…", icon: "pdf", run: () => ops.downloadGemini(d.id) },
        // "@A1" to paste into a message: the chat reads the handle as the design asked about.
        { id: "copy-at", label: `Copy @${handleOf(d.id)}`, icon: "copy", run: () => ops.copy(`@${handleOf(d.id)}`, `@${handleOf(d.id)}`) },
        { id: "link", label: "Copy its link", icon: "link", run: () => ops.copy(ops.linkFor("design", d.id), "Link") },
      ],
    ),
  };
}

/** A design's handle from its id: "A1 · 1D-BO-EC@3500-N1" → "A1". */
const handleOf = (id: string) => id.split(" · ")[0].trim();

// ------------------------------------------------------------------ the chat

/** A few words either side of a number, to say which one a question means. */
export function numberSnippet(text: string, before: string, after: string): string {
  // The sentence the number is in: up to seven words before it, three after.
  const b0 = before.replace(/\s+/g, " ");
  const b1 = b0.slice(b0.lastIndexOf(". ") + 1);
  const b = b1.trim() ? `${b1.trim().split(" ").slice(-7).join(" ")}${/\s$/.test(b1) ? " " : ""}` : "";
  const a0 = after.replace(/\s+/g, " ").split(/(?<=[.!?])\s/)[0];
  const a = a0.trim() ? `${/^\s/.test(a0) ? " " : ""}${a0.trim().split(" ").slice(0, 3).join(" ")}` : "";
  return clip(`${b}${text}${a}`.replace(/^[,;:.)\s]+|[,;:.(\s]+$/g, ""), 120);
}

export function numberMenu(t: Extract<MenuTarget, { kind: "number" }>, ops: MenuOps): MenuModel {
  const param = sensParamOfNumber(t.text, t.unit, t.before, t.after);
  const snippet = numberSnippet(t.text, t.before, t.after);
  return {
    title: t.text,
    sub: "A number in the answer",
    sections: sections(
      [
        t.showSource && { id: "source", label: "Show the step it came from", icon: "step", run: t.showSource },
        {
          id: "where",
          label: "Where does this come from?",
          icon: "ask",
          hint: CHAT_HINT,
          run: () => ops.ask(snippet && snippet !== t.text ? `Where does the ${t.text} in “${snippet}” come from?` : `Where does the ${t.text} in your answer come from?`),
        },
      ],
      [
        { id: "copy", label: "Copy with its unit", icon: "copy", run: () => ops.copy(t.text, t.text) },
        param && { id: "vary", label: "Vary it in Sensitivity", icon: "sensitivity", run: () => ops.vary(param) },
      ],
    ),
  };
}

export function messageMenu(t: Extract<MenuTarget, { kind: "message" }>, ops: MenuOps): MenuModel {
  const dev = ops.device();
  const busy = dev.busy ? "when the reply has finished" : undefined;
  const on = (d: "auto" | "cpu") => () => {
    if (dev.device !== d) ops.setDevice(d);
    t.resend();
  };
  return {
    title: "Your message",
    sub: clip(t.text, 60),
    sections: sections(
      [
        { id: "edit", label: "Edit and resend", icon: "edit", hint: CHAT_HINT, run: () => ops.ask(t.text) },
        { id: "resend", label: `Resend on the ${dev.device === "cpu" ? "CPU" : "GPU"}`, icon: "resend", run: on(dev.device), disabled: dev.busy, why: busy },
        dev.device === "cpu"
          ? dev.gpu && { id: "resend-gpu", label: "Resend on the GPU", icon: "gpu", run: on("auto"), disabled: dev.busy, why: busy }
          : { id: "resend-cpu", label: "Resend on the CPU", icon: "cpu", run: on("cpu"), disabled: dev.busy, why: busy },
      ],
      [{ id: "copy", label: "Copy the message", icon: "copy", run: () => ops.copy(t.text, "Message") }],
    ),
  };
}

export function answerMenu(t: Extract<MenuTarget, { kind: "answer" }>, ops: MenuOps): MenuModel {
  const sel = t.selection?.replace(/\s+/g, " ").trim();
  return {
    title: "Answer",
    sub: clip(t.markdown.replace(/[#*_`>|[\]^]/g, ""), 60),
    sections: sections(
      [
        sel && { id: "copy-sel", label: "Copy the selection", icon: "copy", run: () => ops.copy(sel, "Selection") },
        { id: "copy-md", label: "Copy as Markdown", icon: "markdown", run: () => ops.copy(t.markdown, "Answer") },
      ],
      [
        {
          id: "flag",
          label: sel ? "Flag the selection as wrong" : "Flag a wrong statement",
          icon: "flag",
          hint: CHAT_HINT,
          run: () => ops.ask(sel ? `This statement looks wrong: “${clip(sel, 400)}”. ` : "This statement looks wrong: "),
        },
      ],
    ),
  };
}

// ------------------------------------------------------------------ the Design tab

export function unitMenu(t: Extract<MenuTarget, { kind: "unit" }>, ops: MenuOps): MenuModel {
  const name = nameOf(t.design);
  const words = unitWords(t.node.label);
  const size = t.sizeMw && t.sizeMw > 0 ? t.sizeMw : null;
  const bigger = size ? Math.max(size + 0.5, size * 1.5) : null;
  const energy = t.energy;
  // The demand and the reservoir are not units that can fail.
  const canFail = !/^demand_|^reservoir$/.test(t.node.type);
  return {
    title: t.node.label,
    sub: `on ${name}`,
    sections: sections(
      [t.inspect && { id: "inspect", label: "Inspect", icon: "inspect", run: t.inspect }, t.edit && { id: "edit", label: t.edit.label, icon: "size", run: t.edit.run }],
      [
        canFail && { id: "out", label: "Take it out for 14 days", icon: "out", hint: CHAT_HINT, run: () => ops.ask(`What if ${words} of ${name} is out for 14 days?`) },
        size &&
          bigger && {
            id: "bigger",
            label: `What if it were ${mw(bigger)} MW`,
            icon: "whatif",
            hint: CHAT_HINT,
            run: () => ops.ask(`What if ${words} of ${name} were ${mw(bigger)} MW instead of ${mw(size)} MW?`),
          },
      ],
      [
        energy && { id: "energy", label: "Show its year in Energy", icon: "energy", run: () => ops.showEnergy(t.design.id, energy.side, energy.series) },
        t.costs && t.costs.length > 0 && { id: "costs", label: t.costs.length > 1 ? "Show its cost lines in Economics" : "Show its cost line in Economics", icon: "economics", run: () => ops.showCosts(t.design.id, t.costs!) },
      ],
    ),
  };
}

export function canvasMenu(t: Extract<MenuTarget, { kind: "canvas" }>): MenuModel {
  return {
    title: "The plant drawing",
    sections: sections([
      t.fit && { id: "fit", label: "Fit the view", icon: "fit", run: t.fit },
      t.fullScreen && { id: "full", label: t.fullScreen.on ? "Leave full screen" : "Full screen", icon: "full", hint: "F", run: t.fullScreen.toggle },
    ]),
  };
}

// ------------------------------------------------------------------ Energy and Economics

export function dayMenu(t: Extract<MenuTarget, { kind: "day" }>, ops: MenuOps): MenuModel {
  const name = nameOf(t.design);
  return {
    title: t.label,
    sub: `${name}, day ${t.day + 1} of the year`,
    sections: sections(
      [{ id: "jump", label: "Jump to that day in the Design player", icon: "day", run: () => ops.jumpToDay(t.design.id, t.day + 1) }],
      [{ id: "failure", label: "Start a failure on that day", icon: "failure", hint: CHAT_HINT, run: () => ops.ask(`What if ${name}'s largest heat unit fails on ${t.label} for 14 days?`) }],
      [{ id: "copy", label: "Copy the day's values", icon: "copy", run: () => ops.copy(t.values, "Values") }],
    ),
  };
}

export function seriesMenu(t: Extract<MenuTarget, { kind: "series" }>): MenuModel {
  return {
    title: t.label,
    sub: "On the chart",
    sections: sections([
      t.only ? { id: "all", label: "Show all series", icon: "series", run: t.showAll } : { id: "only", label: "Show only this series", icon: "filter", run: t.showOnly },
    ]),
  };
}

export function costMenu(t: Extract<MenuTarget, { kind: "cost" }>, ops: MenuOps): MenuModel {
  const name = nameOf(t.design);
  const what = t.side === "heat" ? "heat" : "cold";
  const param = t.sensParam;
  return {
    title: t.item,
    sub: `${t.eur} €/MWh of ${name}'s cost of ${what}`,
    sections: sections(
      [
        {
          id: "why",
          label: "Why so much?",
          icon: "ask",
          hint: CHAT_HINT,
          run: () => ops.ask(`Why is “${t.item}” ${t.eur} €/MWh of ${name}'s cost of ${what} (${t.total} €/MWh in all)? What drives it?`),
        },
      ],
      [
        t.price && { id: "price", label: "Change this price", icon: "price", hint: t.price.label, run: t.price.open },
        param && { id: "vary", label: "Vary it in Sensitivity", icon: "sensitivity", run: () => ops.vary(param, t.design.id) },
      ],
      [{ id: "copy", label: "Copy the line", icon: "copy", run: () => ops.copy(`${t.item}: ${t.eur} €/MWh (${name}, cost of ${what} ${t.total} €/MWh)`, "Line") }],
    ),
  };
}

// ------------------------------------------------------------------ Compare, Sensitivity, Trace, sources

export function columnMenu(t: Extract<MenuTarget, { kind: "column" }>): MenuModel {
  const s = t.sort;
  const f = t.filter;
  return {
    title: t.label,
    sub: "Column",
    sections: sections(
      s
        ? [
            { id: "asc", label: s.dir === "asc" ? "Sorted ascending" : "Sort ascending", icon: "sortAsc", run: () => s.set("asc"), disabled: s.dir === "asc" },
            { id: "desc", label: s.dir === "desc" ? "Sorted descending" : "Sort descending", icon: "sortDesc", run: () => s.set("desc"), disabled: s.dir === "desc" },
          ]
        : [],
      [f && { id: "filter", label: f.on ? "Show every design again" : f.label, icon: "filter", run: f.toggle }],
    ),
  };
}

export function barMenu(t: Extract<MenuTarget, { kind: "bar" }>, ops: MenuOps): MenuModel {
  const words = lowerFirst(t.label);
  const q = (v: string) => `What if the ${words} were ${v} for ${t.design}?`;
  return {
    title: t.label,
    sub: `${t.low} to ${t.high}, on ${t.design}`,
    sections: sections([
      { id: "low", label: `What-if at the low end, ${t.low}`, icon: "low", hint: CHAT_HINT, run: () => ops.ask(q(t.low)) },
      { id: "high", label: `What-if at the high end, ${t.high}`, icon: "high", hint: CHAT_HINT, run: () => ops.ask(q(t.high)) },
    ]),
  };
}

export function stepMenu(t: Extract<MenuTarget, { kind: "step" }>, ops: MenuOps): MenuModel {
  const code = t.code?.trim();
  return {
    title: t.label,
    sub: "A step of the run",
    sections: sections(
      [
        code && { id: "copy-call", label: "Copy its tool call", icon: "copy", run: () => ops.copy(code, "Tool call") },
        { id: "copy-json", label: "Copy what it reported", icon: "copy", run: () => ops.copy(t.json, "Step") },
      ],
      [t.details && { id: "details", label: t.details.open ? "Hide its details" : "Show its details", icon: "step", run: t.details.toggle }],
    ),
  };
}

export function sourceMenu(t: Extract<MenuTarget, { kind: "source" }>, ops: MenuOps): MenuModel {
  return {
    title: t.title,
    sub: t.citation !== t.title ? clip(t.citation, 70) : undefined,
    sections: sections(
      [t.open && { id: "open", label: t.open.label, icon: "open", run: t.open.run }],
      [
        { id: "copy-cite", label: "Copy the citation", icon: "source", run: () => ops.copy(t.citation, "Citation") },
        t.text && { id: "copy-text", label: "Copy the passage", icon: "copy", run: () => ops.copy(`${t.text}\n— ${t.citation}`, "Passage") },
      ],
      [{ id: "ask", label: "Ask about this source", icon: "ask", hint: CHAT_HINT, run: () => ops.ask(`About ${t.citation}: `) }],
    ),
  };
}

// ------------------------------------------------------------------ text, selections, links

/** "⌘C" on a Mac, "Ctrl+C" elsewhere: the key the item stands for. */
function keyHint(k: string): string {
  const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
  return mac ? `⌘${k}` : `Ctrl+${k}`;
}

/** A text box's own menu: the browser's is never shown. */
export function textMenu(t: Extract<MenuTarget, { kind: "text" }>, ops: MenuOps): MenuModel {
  const sel = t.selection;
  const empty = !t.field.value;
  return {
    title: t.editable ? "Text" : "Text (read only)",
    sub: sel ? `“${clip(sel, 40)}”` : undefined,
    sections: sections(
      [
        t.editable && { id: "cut", label: "Cut", icon: "cut", hint: keyHint("X"), run: () => ops.editText(t, "cut"), disabled: !sel, why: sel ? undefined : "nothing selected" },
        { id: "copy", label: "Copy", icon: "copy", hint: keyHint("C"), run: () => ops.editText(t, "copy"), disabled: !sel, why: sel ? undefined : "nothing selected" },
        t.editable && { id: "paste", label: "Paste", icon: "paste", hint: keyHint("V"), run: () => ops.editText(t, "paste") },
      ],
      [{ id: "select-all", label: "Select all", icon: "selectAll", hint: keyHint("A"), run: () => ops.editText(t, "selectAll"), disabled: empty }],
    ),
  };
}

/** Text selected on the page, outside a reply (a reply's own menu covers that). */
export function selectionMenu(t: Extract<MenuTarget, { kind: "selection" }>, ops: MenuOps): MenuModel {
  return {
    title: "Selected text",
    sub: `“${clip(t.text, 40)}”`,
    sections: sections(
      [{ id: "copy", label: "Copy", icon: "copy", hint: keyHint("C"), run: () => ops.copy(t.text, "Text") }],
      [{ id: "ask", label: "Ask about this", icon: "ask", hint: CHAT_HINT, run: () => ops.ask(`About “${clip(t.text, 300)}”: `) }],
    ),
  };
}

/** A chat in the sidebar: rename it, or remove it (after a yes: its designs and runs go too). */
export function chatMenu(t: Extract<MenuTarget, { kind: "chat" }>): MenuModel {
  return {
    title: clip(t.title, 40),
    sub: "Chat",
    sections: sections(
      [{ id: "rename", label: "Rename", icon: "edit", hint: "F2", run: t.rename }],
      [{ id: "remove", label: "Remove chat…", icon: "remove", run: t.remove }],
    ),
  };
}

export function linkMenu(t: Extract<MenuTarget, { kind: "link" }>, ops: MenuOps): MenuModel {
  return {
    title: clip(t.text || t.href, 40),
    sub: t.text && t.text !== t.href ? clip(t.href, 60) : undefined,
    sections: sections(
      [
        { id: "open", label: "Open", icon: "open", run: () => ops.openLink(t.href, false) },
        { id: "open-new", label: "Open in a new tab", icon: "link", run: () => ops.openLink(t.href, true) },
      ],
      [{ id: "copy-link", label: "Copy the link", icon: "copy", run: () => ops.copy(t.href, "Link") }],
    ),
  };
}

// ------------------------------------------------------------------ the registry

type Builders = { [K in MenuTarget["kind"]]: (t: Extract<MenuTarget, { kind: K }>, ops: MenuOps) => MenuModel };

export const REGISTRY: Builders = {
  design: designMenu,
  number: numberMenu,
  message: messageMenu,
  answer: answerMenu,
  unit: unitMenu,
  canvas: canvasMenu,
  day: dayMenu,
  series: seriesMenu,
  cost: costMenu,
  column: columnMenu,
  bar: barMenu,
  step: stepMenu,
  source: sourceMenu,
  text: textMenu,
  selection: selectionMenu,
  link: linkMenu,
  chat: chatMenu,
};

/** The menu for what was right-clicked (no sections: nothing to offer, the browser's own menu stays). */
export function menuFor(target: MenuTarget, ops: MenuOps): MenuModel {
  const build = REGISTRY[target.kind] as (t: MenuTarget, ops: MenuOps) => MenuModel;
  return build(target, ops);
}

/** Every item of a menu, in order. */
export const itemsOf = (m: MenuModel): MenuItem[] => m.sections.flatMap((s) => s.items);
