// Server-sent events from POST /api/run: one `data: <json>` line per AG-UI event, blank line
// between events. The parser is incremental so it works on a streamed body and on a whole file.

import type { AgEvent } from "./types";

export class SseParser {
  private buffer = "";

  /** Feed a chunk of text; returns the events completed by it. */
  push(chunk: string): AgEvent[] {
    this.buffer += chunk.replace(/\r\n?/g, "\n");
    const out: AgEvent[] = [];
    let cut: number;
    while ((cut = this.buffer.indexOf("\n\n")) >= 0) {
      const block = this.buffer.slice(0, cut);
      this.buffer = this.buffer.slice(cut + 2);
      const event = parseBlock(block);
      if (event) out.push(event);
    }
    return out;
  }

  /** Flush whatever is left when the stream ends without a trailing blank line. */
  end(): AgEvent[] {
    const rest = this.buffer;
    this.buffer = "";
    const event = parseBlock(rest);
    return event ? [event] : [];
  }
}

function parseBlock(block: string): AgEvent | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /, ""))
    .join("\n");
  if (!data.trim()) return null;
  try {
    const value = JSON.parse(data);
    return value && typeof value.type === "string" ? (value as AgEvent) : null;
  } catch {
    return null;
  }
}

/** Parse a whole recorded stream (a fixture file). */
export function parseSse(text: string): AgEvent[] {
  const parser = new SseParser();
  return [...parser.push(text), ...parser.end()];
}
