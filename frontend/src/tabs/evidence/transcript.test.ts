// An eval transcript rebuilt as a chat: a message, the inputs card, the "Run" answer and the
// design, from streams recorded from the agent (src/fixtures/confirm*.sse).

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { asksOf, behaviour } from "../../agent/reducer";
import { parseSse } from "../../agent/sse";
import type { AgEvent } from "../../agent/types";
import { transcriptChat } from "./transcript";

const here = dirname(fileURLToPath(import.meta.url));
const load = (name: string): AgEvent[] => parseSse(readFileSync(join(here, "..", "..", "fixtures", `${name}.sse`), "utf-8"));

describe("transcriptChat", () => {
  it("puts a card's answer in the same turn as the message that asked", () => {
    const chat = transcriptChat({
      case: "S01",
      exchanges: [
        { user: { message: "Design it" }, events: load("confirm") },
        { user: { answers: { confirm: "Run the design with these inputs" } }, events: load("confirm-run") },
      ],
    });
    expect(chat.turns).toHaveLength(1);
    const turn = chat.turns[0];
    expect(turn.message).toBe("Design it");
    expect(asksOf(turn)[0].answers).toEqual({ confirm: "Run the design with these inputs" });
    expect(turn.status).toBe("done");
    expect(behaviour(turn)).toBe("design");
  });

  it("shows an upload the app refused as a turn with the app's reply", () => {
    const reply = "The project was not made: 364 values";
    const chat = transcriptChat({
      case: "S63",
      exchanges: [
        {
          user: { message: "New project from heating_364_days.csv", upload: { files: ["heating_364_days.csv"] } },
          events: [
            { type: "RUN_STARTED", threadId: "eval", runId: "app", timestamp: 1 },
            { type: "TEXT_MESSAGE_START", messageId: "m", role: "assistant", timestamp: 1 },
            { type: "TEXT_MESSAGE_CONTENT", messageId: "m", delta: reply, timestamp: 1 },
            { type: "TEXT_MESSAGE_END", messageId: "m", timestamp: 1 },
            { type: "RUN_FINISHED", threadId: "eval", runId: "app", result: { behaviour: "upload_rejected", answer: reply }, timestamp: 1 },
          ] as AgEvent[],
        },
      ],
    });
    expect(chat.turns).toHaveLength(1);
    expect(chat.turns[0].messages.map((m) => m.text).join("")).toContain("364 values");
    expect(chat.turns[0].status).toBe("done");
  });
});
