// The sidebar's "Remembered" list: where each note was said, and the API it reads.

import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchMemory, forgetMemory } from "../agent/client";
import { noteSource } from "./ProjectMemory";

afterEach(() => vi.unstubAllGlobals());

const NOTE = { id: "a1", text: "call the user Sam", said: "I'm Sam, call me Sam", thread: "t1", turn: 2, at: 0 };

describe("project memory", () => {
  it("says which chat a note came from", () => {
    expect(noteSource(NOTE, "t1")).toBe("Said in this chat (turn 2)");
    expect(noteSource({ ...NOTE, turn: 0 }, "t1")).toBe("Said in this chat");
    expect(noteSource(NOTE, "t2")).toBe("Said in another chat");
    expect(noteSource(NOTE, null)).toBe("Said in another chat");
  });

  it("reads a project's notes, and none from a server without memory", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ notes: [NOTE] }), { status: 200 })));
    expect(await fetchMemory("challenge")).toEqual([NOTE]);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "no" }), { status: 404 })));
    expect(await fetchMemory("challenge")).toEqual([]);
  });

  it("forgets one note by id, or all", async () => {
    const seen: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        seen.push(`${init.method} ${url}`);
        return new Response(JSON.stringify({ notes: [] }), { status: 200 });
      }),
    );
    expect(await forgetMemory("challenge", "a1")).toEqual([]);
    await forgetMemory("my project");
    expect(seen).toEqual(["DELETE /api/projects/challenge/memory?id=a1", "DELETE /api/projects/my%20project/memory"]);
  });
});
