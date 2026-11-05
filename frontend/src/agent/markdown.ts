// The answer's Markdown subset, parsed into blocks and inlines that React draws (Markdown.tsx):
// paragraphs, headings, one level of nested lists, GFM pipe tables, quotes, fenced code, bold,
// italic, code, citation markers [^n], file names and LaTeX formulas. Every node is plain text
// that React escapes, except a formula: KaTeX draws it (renderMath, with KaTeX's trust off, so
// a reply cannot inject markup through it), and one KaTeX can't read shows as its source in a
// code span. A template with no Markdown in it is one paragraph, as before.

import katex from "katex";

export type Inline =
  | { type: "text"; text: string }
  | { type: "strong"; children: Inline[] }
  | { type: "em"; children: Inline[] }
  | { type: "code"; text: string }
  /** A citation marker [^n]: n is the 1-based place in the run's sources. */
  | { type: "cite"; n: number }
  /** A file name the user can open, e.g. heating_profile.csv. */
  | { type: "file"; name: string }
  /** A LaTeX formula: $…$ or \(…\) in the text, $$…$$ or \[…\] displayed on its own line. */
  | { type: "math"; tex: string; display: boolean }
  | { type: "br" };

export interface ListItem {
  children: Inline[];
  /** Indented items under this one (one level). */
  sub?: ListBlock;
}

export interface ListBlock {
  type: "list";
  ordered: boolean;
  start: number;
  items: ListItem[];
}

export type Align = "left" | "center" | "right" | null;

export type Block =
  | { type: "paragraph"; children: Inline[] }
  | { type: "heading"; level: 1 | 2 | 3; children: Inline[] }
  | ListBlock
  | { type: "table"; align: Align[]; head: Inline[][]; rows: Inline[][][] }
  | { type: "quote"; children: Inline[] }
  | { type: "code"; text: string }
  /** A displayed formula: $$…$$ (or \[…\]) on lines of its own. */
  | { type: "math"; tex: string }
  | { type: "rule" };

const EXT = "csv|json|xlsx|xls|pdf|md|txt|tex|rst|png|jpe?g|webp|gif";
/** A file name on its own, not part of a path or a longer word. */
export const FILE_NAME = new RegExp(`(?<![\\w/.-])[\\w.-]+\\.(?:${EXT})\\b`, "gi");
const WHOLE_FILE = new RegExp(`^[\\w.-]+\\.(?:${EXT})$`, "i");
const IMAGE = /\.(png|jpe?g|webp|gif)$/i;

export const isImageName = (name: string) => IMAGE.test(name);

const HEADING = /^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/;
const ITEM = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/;
const RULE = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/;
const FENCE = /^ {0,3}(```|~~~)/;
const QUOTE = /^ {0,3}>\s?(.*)$/;
const SEPARATOR = /^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$/;

/** Parse an answer into blocks. */
export function parseMarkdown(text: string): Block[] {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ type: "paragraph", children: parseInline(para.join("\n")) });
    para = [];
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      flush();
      i++;
      continue;
    }

    const fence = FENCE.exec(line);
    if (fence) {
      flush();
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith(fence[1])) body.push(lines[i++]);
      i++;
      blocks.push({ type: "code", text: body.join("\n") });
      continue;
    }

    const math = displayMath(lines, i);
    if (math) {
      flush();
      blocks.push({ type: "math", tex: math[0] });
      i = math[1];
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      blocks.push({ type: "heading", level: Math.min(3, heading[1].length) as 1 | 2 | 3, children: parseInline(heading[2]) });
      i++;
      continue;
    }

    if (isTableStart(lines, i)) {
      flush();
      const head = cells(line);
      const align = cells(lines[i + 1]).map(alignOf);
      const rows: Inline[][][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) {
        const row = cells(lines[i]);
        // Rows have the header's width: cut extra cells, pad missing ones.
        rows.push(head.map((_, c) => parseInline(row[c] ?? "")));
        i++;
      }
      blocks.push({ type: "table", align: head.map((_, c) => align[c] ?? null), head: head.map((h) => parseInline(h)), rows });
      continue;
    }

    if (RULE.test(line)) {
      flush();
      blocks.push({ type: "rule" });
      i++;
      continue;
    }

    if (ITEM.test(line)) {
      flush();
      const [list, next] = parseList(lines, i);
      blocks.push(list);
      i = next;
      continue;
    }

    const quote = QUOTE.exec(line);
    if (quote) {
      flush();
      const body: string[] = [];
      while (i < lines.length && QUOTE.test(lines[i])) body.push(QUOTE.exec(lines[i])![1]), i++;
      blocks.push({ type: "quote", children: parseInline(body.join("\n")) });
      continue;
    }

    para.push(line.trim());
    i++;
  }
  flush();
  return blocks;
}

/**
 * A displayed formula from line i on: $$…$$ (or \[…\]) alone on its line, or opened on line i
 * and closed at the end of a later line, with no blank line between. Returns its TeX and the
 * next line; null when line i doesn't start one (a closing in mid-line is text with inline math).
 */
function displayMath(lines: string[], i: number): [string, number] | null {
  const first = lines[i].trim();
  const open = first.startsWith("$$") ? "$$" : first.startsWith("\\[") ? "\\[" : "";
  if (!open || lines[i].length - lines[i].trimStart().length > 3) return null;
  const close = open === "$$" ? "$$" : "\\]";
  const body: string[] = [];
  let rest = first.slice(2);
  for (let j = i; j < lines.length && j < i + 60; j++) {
    if (j > i) {
      rest = lines[j];
      if (!rest.trim()) return null;
    }
    const at = rest.indexOf(close);
    if (at < 0) {
      body.push(rest);
      continue;
    }
    if (rest.slice(at + close.length).trim()) return null;
    body.push(rest.slice(0, at));
    const tex = body.join("\n").trim();
    return tex ? [tex, j + 1] : null;
  }
  return null;
}

/** A list from line i on, with its indented items nested one level; returns the next line. */
function parseList(lines: string[], i: number): [ListBlock, number] {
  const first = ITEM.exec(lines[i])!;
  const ordered = /\d/.test(first[2]);
  const indent = first[1].length;
  const list: ListBlock = { type: "list", ordered, start: ordered ? parseInt(first[2], 10) : 1, items: [] };
  let item: { text: string[]; sub: string[] } | null = null;
  const items: { text: string[]; sub: string[] }[] = [];

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      // A blank line ends the list unless the next line carries on with an item.
      const next = lines[i + 1];
      if (next !== undefined && ITEM.test(next) && /\d/.test(ITEM.exec(next)![2]) === ordered) {
        i++;
        continue;
      }
      break;
    }
    const m = ITEM.exec(line);
    if (m && m[1].length <= indent + 1) {
      // Same level: a new item, unless the marker changes kind (a new list).
      if (/\d/.test(m[2]) !== ordered) break;
      item = { text: [m[3]], sub: [] };
      items.push(item);
    } else if (m && item) {
      item.sub.push(line);
    } else if (item && !HEADING.test(line) && !QUOTE.test(line) && !isTableStart(lines, i)) {
      // A continuation line of the item (or of its last sub-item).
      if (item.sub.length) item.sub[item.sub.length - 1] += "\n" + line.trim();
      else item.text.push(line.trim());
    } else break;
    i++;
  }

  for (const it of items) {
    const out: ListItem = { children: parseInline(it.text.join("\n")) };
    if (it.sub.length) {
      // Deeper levels are drawn one level down, flat.
      const flat = it.sub.flatMap((l) => l.split("\n")).map((l, k) => (k === 0 || ITEM.test(l) ? l.replace(/^\s+/, "  ") : l));
      const [sub] = parseList(flat, 0);
      out.sub = sub;
    }
    list.items.push(out);
  }
  return [list, i];
}

function isTableStart(lines: string[], i: number): boolean {
  const head = lines[i];
  const sep = lines[i + 1];
  if (!head?.includes("|") || sep === undefined || !SEPARATOR.test(sep) || !sep.includes("-")) return false;
  // A separator with no pipe is a rule or a heading underline unless the header has one cell.
  if (!sep.includes("|") && cells(head).length > 1) return false;
  return cells(head).length === cells(sep).length;
}

/** The cells of a table row; leading and trailing pipes are optional, "\|" is a literal pipe. */
function cells(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
  const out: string[] = [];
  let cur = "";
  for (let k = 0; k < s.length; k++) {
    if (s[k] === "\\" && s[k + 1] === "|") {
      cur += "|";
      k++;
    } else if (s[k] === "|") {
      out.push(cur.trim());
      cur = "";
    } else cur += s[k];
  }
  out.push(cur.trim());
  return out;
}

function alignOf(cell: string): Align {
  const l = cell.startsWith(":");
  const r = cell.endsWith(":");
  return l && r ? "center" : r ? "right" : l ? "left" : null;
}

const WORD = /[\p{L}\p{N}]/u;
const SPACE = /\s/;

/** Parse one run of text into inlines: code, citations, bold, italic, file names and line breaks. */
export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  let buf = "";
  const flush = () => {
    if (buf) out.push(...textWithFiles(buf));
    buf = "";
  };
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === "$" || (c === "\\" && (src[i + 1] === "(" || src[i + 1] === "["))) {
      const math = mathAt(src, i);
      if (math) {
        flush();
        out.push(math.node);
        i = math.end;
        continue;
      }
    }
    if (c === "\\" && i + 1 < src.length && "\\`*_[]#|-.!>$".includes(src[i + 1])) {
      buf += src[i + 1];
      i += 2;
      continue;
    }
    if (c === "\n") {
      flush();
      out.push({ type: "br" });
      i++;
      continue;
    }
    if (c === "`") {
      const end = src.indexOf("`", i + 1);
      if (end > i + 1) {
        flush();
        const code = src.slice(i + 1, end);
        // A file name in backticks is still a file the user can open.
        out.push(WHOLE_FILE.test(code.trim()) ? { type: "file", name: code.trim() } : { type: "code", text: code });
        i = end + 1;
        continue;
      }
    }
    if (c === "[" && src[i + 1] === "^") {
      const m = /^\[\^(\d{1,3})\]/.exec(src.slice(i));
      if (m) {
        flush();
        out.push({ type: "cite", n: Number(m[1]) });
        i += m[0].length;
        continue;
      }
    }
    if (c === "*" && src[i + 1] === "*") {
      const end = closing(src, i + 2, "**");
      if (end > 0) {
        flush();
        out.push({ type: "strong", children: parseInline(src.slice(i + 2, end)) });
        i = end + 2;
        continue;
      }
    }
    if ((c === "*" || c === "_") && opens(src, i, c)) {
      const end = closing(src, i + 1, c);
      if (end > 0) {
        flush();
        out.push({ type: "em", children: parseInline(src.slice(i + 1, end)) });
        i = end + 1;
        continue;
      }
    }
    buf += c;
    i++;
  }
  flush();
  return out;
}

const DIGIT = /\d/;
const ALNUM = /[\p{L}\p{N}]/u;

/**
 * The formula that starts at src[i], if one does. $$…$$ and \[…\] are displayed, $…$ and \(…\)
 * sit in the text. A single $ is money unless it reads as math: the opening $ is not glued to a
 * word ("US$5") and has no space after it, the closing $ is the next unescaped $ on the same
 * line, with no space before it and no digit after it. So "costs $5 and $10" stays text.
 */
function mathAt(src: string, i: number): { node: Inline; end: number } | null {
  const pair = src.startsWith("$$", i) ? ["$$", "$$"] : src.startsWith("\\[", i) ? ["\\[", "\\]"] : src.startsWith("\\(", i) ? ["\\(", "\\)"] : null;
  if (pair) {
    const end = src.indexOf(pair[1], i + 2);
    if (end < 0) return null;
    const tex = src.slice(i + 2, end).trim();
    // \(…\) stays on its line; a displayed formula may span the paragraph's lines.
    if (!tex || (pair[0] === "\\(" && tex.includes("\n"))) return null;
    return { node: { type: "math", tex, display: pair[0] !== "\\(" }, end: end + 2 };
  }
  if (i > 0 && ALNUM.test(src[i - 1])) return null;
  const next = src[i + 1];
  if (next === undefined || SPACE.test(next)) return null;
  for (let j = i + 1; j < src.length; j++) {
    const ch = src[j];
    if (ch === "\n") return null;
    if (ch === "\\") {
      j++; // an escaped character, \$ included, never closes
      continue;
    }
    if (ch !== "$") continue;
    if (SPACE.test(src[j - 1]) || DIGIT.test(src[j + 1] ?? "")) return null;
    return { node: { type: "math", tex: src.slice(i + 1, j), display: false }, end: j + 1 };
  }
  return null;
}

export type MathOut = { html: string } | { error: string };

const MATH_CACHE = new Map<string, MathOut>();

/**
 * A formula drawn by KaTeX, as HTML (cached: a streaming reply is parsed on every delta), or why
 * KaTeX couldn't read it; never throws. Trust is off, so \href, \url, \includegraphics and the
 * \html* commands draw as red text, and KaTeX escapes every character of the source it shows.
 */
export function renderMath(tex: string, display: boolean): MathOut {
  const key = `${display ? "D" : "I"}${tex}`;
  const hit = MATH_CACHE.get(key);
  if (hit) return hit;
  let out: MathOut;
  try {
    out = {
      html: katex.renderToString(tex, {
        displayMode: display,
        throwOnError: true,
        trust: false,
        strict: "ignore",
        output: "htmlAndMathml",
        maxSize: 20,
        maxExpand: 500,
      }),
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    out = { error: message.replace(/^KaTeX parse error: /, "").replace(/ at position \d+:[\s\S]*$/, "") || "unreadable formula" };
  }
  if (MATH_CACHE.size >= 400) MATH_CACHE.delete(MATH_CACHE.keys().next().value as string);
  MATH_CACHE.set(key, out);
  return out;
}

/** A formula as it was written, with its delimiters (a formula KaTeX can't read is shown so). */
export function mathSource(tex: string, display: boolean): string {
  return display ? `$$${tex}$$` : `$${tex}$`;
}

/** "*" or "_" opens emphasis before a non-space; "_" only at the start of a word (not snake_case). */
function opens(src: string, i: number, c: string): boolean {
  const next = src[i + 1];
  if (next === undefined || SPACE.test(next) || next === c) return false;
  return c === "*" || i === 0 || !WORD.test(src[i - 1]);
}

/** Where the emphasis that starts at `from` closes, on the same line; -1 when it doesn't. */
function closing(src: string, from: number, mark: string): number {
  if (from >= src.length || SPACE.test(src[from])) return -1;
  for (let j = from + 1; j <= src.length - mark.length; j++) {
    if (src[j] === "\n") return -1;
    if (src.startsWith(mark, j) && !SPACE.test(src[j - 1])) {
      if (mark === "_" && j + 1 < src.length && WORD.test(src[j + 1])) continue;
      if (mark === "*" && src[j + 1] === "*") {
        j++;
        continue;
      }
      return j;
    }
  }
  return -1;
}

/** Plain text with its file names as file nodes. */
export function textWithFiles(text: string): Inline[] {
  const out: Inline[] = [];
  let at = 0;
  for (const m of text.matchAll(FILE_NAME)) {
    const start = m.index ?? 0;
    if (start > at) out.push({ type: "text", text: text.slice(at, start) });
    out.push({ type: "file", name: m[0] });
    at = start + m[0].length;
  }
  if (at < text.length) out.push({ type: "text", text: text.slice(at) });
  return out;
}

/** The text of inlines without their markup (for titles and tests). */
export function plain(nodes: Inline[]): string {
  return nodes
    .map((n) =>
      n.type === "text" || n.type === "code"
        ? n.text
        : n.type === "file"
          ? n.name
          : n.type === "cite"
            ? `[${n.n}]`
            : n.type === "br"
              ? "\n"
              : n.type === "math"
                ? mathSource(n.tex, n.display)
                : plain(n.children),
    )
    .join("");
}
