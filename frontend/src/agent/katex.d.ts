// KaTeX 0.16.11 ships no type declarations (they live in @types/katex): the part of its API the
// chat uses (agent/markdown.ts: renderMath), as the library documents it.

declare module "katex" {
  export interface KatexOptions {
    displayMode?: boolean;
    output?: "html" | "mathml" | "htmlAndMathml";
    throwOnError?: boolean;
    errorColor?: string;
    /** Off by default: \href, \url, \includegraphics and \html* draw as red text instead. */
    trust?: boolean;
    strict?: boolean | "ignore" | "warn" | "error";
    /** The largest size \rule, \kern and the like may take, in em. */
    maxSize?: number;
    /** How many macro expansions one formula may make. */
    maxExpand?: number;
    macros?: Record<string, string>;
  }

  export class ParseError extends Error {
    position?: number;
    rawMessage?: string;
  }

  export function renderToString(tex: string, options?: KatexOptions): string;

  const katex: {
    version: string;
    renderToString: typeof renderToString;
    ParseError: typeof ParseError;
  };
  export default katex;
}
