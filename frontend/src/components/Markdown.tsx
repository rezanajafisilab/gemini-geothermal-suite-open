// An answer's Markdown (agent/markdown.ts) as React elements: numbers as chips in every run of
// text (table cells and list items too), [^n] as a chip that shows its source card, file names
// as chips that open the file, and LaTeX formulas drawn by KaTeX. React escapes every string;
// the only HTML set is KaTeX's own output for a formula (renderMath: trust off), and a formula
// KaTeX can't read is shown as its source in a code span.

import "katex/dist/katex.min.css";
import { Fragment, type HTMLAttributes, type ReactNode } from "react";

import { mathSource, parseMarkdown, plain, renderMath, type Align, type Block, type Inline, type ListBlock } from "../agent/markdown";
import { segments } from "../agent/numbers";
import { menuProps } from "../menu";
import { useFiles } from "./filesContext";
import { FileGlyph } from "./Icons";

export type SourceFns = { hasSource: (unit: string, after: string) => boolean; onSource: (unit: string, after: string) => void };

interface Props extends SourceFns {
  text: string;
  className?: string;
  /** How many passages the run cited: a marker past them draws nothing. */
  cites: number;
  onCite: (n: number) => void;
  /** More attributes for the text's box (a context menu's handlers). */
  rootProps?: HTMLAttributes<HTMLDivElement>;
}

type Ctx = SourceFns & { cites: number; onCite: (n: number) => void };

export function Markdown({ text, className, rootProps, ...ctx }: Props) {
  const blocks = parseMarkdown(text);
  return (
    <div {...rootProps} className={`md${className ? ` ${className}` : ""}`}>
      {blocks.map((b, i) => renderBlock(b, i, ctx))}
    </div>
  );
}

function renderBlock(b: Block, key: number, ctx: Ctx): ReactNode {
  switch (b.type) {
    case "paragraph":
      return <p key={key}>{inlines(b.children, ctx)}</p>;
    case "heading": {
      const H = (["h3", "h4", "h5"] as const)[b.level - 1];
      return (
        <H key={key} className="md-h">
          {inlines(b.children, ctx)}
        </H>
      );
    }
    case "list":
      return renderList(b, key, ctx);
    case "table":
      return <Table key={key} block={b} ctx={ctx} />;
    case "quote":
      return <blockquote key={key}>{inlines(b.children, ctx)}</blockquote>;
    case "code":
      return (
        <pre key={key} className="md-pre">
          <code>{b.text}</code>
        </pre>
      );
    case "math":
      return <Formula key={key} tex={b.tex} display block />;
    case "rule":
      return <hr key={key} />;
  }
}

/**
 * A LaTeX formula drawn by KaTeX: in the text, displayed in it ($$…$$ mid-paragraph), or as a
 * block of its own. One KaTeX can't read shows as the source it was written in, as code.
 */
export function Formula({ tex, display, block = false }: { tex: string; display: boolean; block?: boolean }) {
  const out = renderMath(tex, display);
  if ("error" in out) {
    const title = `This formula couldn't be drawn (${out.error}); it is shown as written.`;
    return block ? (
      <pre className="md-pre md-math-error" title={title}>
        <code>{mathSource(tex, display)}</code>
      </pre>
    ) : (
      <code className="md-code md-math-error" title={title}>
        {mathSource(tex, display)}
      </code>
    );
  }
  return block ? (
    <div className="md-math md-math-block" dangerouslySetInnerHTML={{ __html: out.html }} />
  ) : (
    <span className={`md-math${display ? " md-math-display" : ""}`} dangerouslySetInnerHTML={{ __html: out.html }} />
  );
}

function renderList(b: ListBlock, key: number, ctx: Ctx): ReactNode {
  const items = b.items.map((it, i) => (
    <li key={i}>
      {inlines(it.children, ctx)}
      {it.sub && renderList(it.sub, -1, ctx)}
    </li>
  ));
  return b.ordered ? (
    <ol key={key} start={b.start !== 1 ? b.start : undefined}>
      {items}
    </ol>
  ) : (
    <ul key={key}>{items}</ul>
  );
}

/** Columns whose cells all start with a number read right-aligned unless the table says otherwise. */
function numericColumns(rows: Inline[][][], width: number): boolean[] {
  return Array.from({ length: width }, (_, c) => {
    const cells = rows.map((r) => plain(r[c] ?? []).trim()).filter(Boolean);
    return cells.length > 0 && cells.every((t) => /^[-−+~≈<>]?\s?\d/.test(t));
  });
}

function Table({ block, ctx }: { block: Extract<Block, { type: "table" }>; ctx: Ctx }) {
  const numeric = numericColumns(block.rows, block.head.length);
  const align = (c: number): Align => block.align[c] ?? (numeric[c] ? "right" : null);
  return (
    <div className="md-table-wrap" role="region" aria-label="Table" tabIndex={0}>
      <table className="md-table">
        <thead>
          <tr>
            {block.head.map((cell, c) => (
              <th key={c} scope="col" style={{ textAlign: align(c) ?? undefined }}>
                {inlines(cell, ctx)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) =>
                c === 0 && !plain(block.head[0]).trim() ? (
                  <th key={c} scope="row">
                    {inlines(cell, ctx)}
                  </th>
                ) : (
                  <td key={c} style={{ textAlign: align(c) ?? undefined }} className={numeric[c] ? "n" : undefined}>
                    {inlines(cell, ctx)}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function inlines(nodes: Inline[], ctx: Ctx): ReactNode {
  return nodes.map((n, i) => <Fragment key={i}>{renderInline(n, ctx)}</Fragment>);
}

function renderInline(n: Inline, ctx: Ctx): ReactNode {
  switch (n.type) {
    case "text":
      return <NumberText text={n.text} hasSource={ctx.hasSource} onSource={ctx.onSource} />;
    case "strong":
      return <strong>{inlines(n.children, ctx)}</strong>;
    case "em":
      return <em>{inlines(n.children, ctx)}</em>;
    case "code":
      return <code className="md-code">{n.text}</code>;
    case "br":
      return <br />;
    case "file":
      return <FileRef name={n.name} />;
    case "math":
      return <Formula tex={n.tex} display={n.display} />;
    case "cite":
      if (n.n < 1 || n.n > ctx.cites) return null;
      return (
        <sup className="cite-ref">
          <button type="button" className="ta-num" aria-label={`Source ${n.n}`} title="Show the source" onClick={() => ctx.onCite(n.n)}>
            {n.n}
          </button>
        </sup>
      );
  }
}

/** A file name in an answer: opens the file's preview. */
export function FileRef({ name }: { name: string }) {
  const files = useFiles();
  return (
    <button type="button" className="file-ref" title={`Open ${name}`} onClick={() => files.open(name)}>
      <FileGlyph name={name} />
      <span>{name}</span>
    </button>
  );
}

/**
 * Text with its numbers drawn as chips; a chip shows the step its number comes from, and its
 * context menu asks where it comes from, copies it with its unit or varies it in Sensitivity.
 */
export function NumberText({ text, hasSource, onSource }: { text: string } & SourceFns) {
  return (
    <>
      {segments(text).map((seg, i, all) => {
        if (!seg.num) return <span key={i}>{seg.text}</span>;
        const after = all[i + 1]?.text ?? "";
        const source = hasSource(seg.unit, after);
        const menu = menuProps(() => ({
          kind: "number",
          text: seg.text,
          unit: seg.unit,
          before: all.slice(Math.max(0, i - 3), i).map((s) => s.text).join(""),
          after,
          showSource: source ? () => onSource(seg.unit, after) : undefined,
        }));
        return source ? (
          <button key={i} type="button" className="num ta-num" title="Show the step this number comes from (right-click for more)" onClick={() => onSource(seg.unit, after)} {...menu}>
            {seg.text}
          </button>
        ) : (
          <span key={i} className="num" style={{ cursor: "default" }} {...menu}>
            {seg.text}
          </span>
        );
      })}
    </>
  );
}
