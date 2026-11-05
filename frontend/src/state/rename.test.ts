// Renaming a chat: the sidebar's name changes, an empty or unchanged name leaves it as it was.

import { describe, expect, it } from "vitest";

import { ChatStore } from "./store";

const meta = (id: string, title = "Design heating and cooling for the district") => ({ threadId: id, title, createdAt: 1, updatedAt: 1 });

describe("renaming a chat", () => {
  it("takes the new name, trimmed and on one line", () => {
    const store = new ChatStore(null);
    store.addChat("challenge", meta("a"));
    store.renameChat("challenge", "a", "  Gas-free\n options  ");
    expect(store.meta("a")?.title).toBe("Gas-free options");
  });

  it("keeps the old name when the new one is empty, and leaves other chats alone", () => {
    const store = new ChatStore(null);
    store.addChat("challenge", meta("a", "First"));
    store.addChat("challenge", meta("b", "Second"));
    store.renameChat("challenge", "a", "   ");
    store.renameChat("challenge", "b", "Renamed");
    expect(store.meta("a")?.title).toBe("First");
    expect(store.meta("b")?.title).toBe("Renamed");
  });
});
