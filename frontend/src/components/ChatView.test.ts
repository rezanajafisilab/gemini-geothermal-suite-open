// The chat on the recorded inputs-card streams (confirm.sse, confirm-run.sse, make_ui_fixtures.py):
// the card in place of the agent's Markdown table, the table kept when the card's event is
// missing, the card folded to one line once answered, the composer after "Change an input first",
// and a new chat's empty start.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement, createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { emptyChat, reduce, replay } from "../agent/reducer";
import { parseSse } from "../agent/sse";
import type { AgEvent, ChatState } from "../agent/types";
import { CHALLENGE } from "../state/projects";
import { ChatView } from "./ChatView";
import type { ComposerHandle } from "./Composer";

const here = dirname(fileURLToPath(import.meta.url));
const load = (name: string): AgEvent[] => parseSse(readFileSync(join(here, "..", "fixtures", `${name}.sse`), "utf-8"));
const send = (chat: ChatState, message: string, events: AgEvent[]) =>
  replay(reduce(chat, { type: "send", turnId: `t${chat.turns.length}`, message, at: 0 }), events);
const noop = () => {};
const draw = (chat: ChatState) =>
  renderToStaticMarkup(
    createElement(ChatView, {
      chat,
      project: CHALLENGE,
      running: false,
      health: { state: "ok" },
      checking: false,
      draft: "",
      onDraft: noop,
      onRecheck: noop,
      onSend: noop,
      onAnswer: noop,
      onStop: noop,
      composerRef: createRef<ComposerHandle>(),
      device: "auto",
      attachments: [],
      onAttach: noop,
      onDismiss: noop,
    }),
  );

const MESSAGE = "Design a geothermal heating and cooling system for this district.";
const asked = send(emptyChat("v"), MESSAGE, load("confirm"));

describe("the inputs card in the chat", () => {
  it("shows the card and not the agent's Markdown table", () => {
    const html = draw(asked);
    expect(html).toContain('class="ask inputs-card ic ta-rise"');
    // In pages: the step bar (seven pages and the review), the first page's rows.
    expect(html.match(/class="ic-step[ "]/g)).toHaveLength(8);
    expect(html.match(/class="ic-row[ "]/g)).toHaveLength(2);
    expect(html).not.toContain("md-table");
    expect(html).not.toContain("| Input | Value | From |");
    expect(html).toContain("Waiting for your go-ahead on the inputs");
  });

  it("keeps the table, inside the card, when the server sent no card event", () => {
    const html = draw(send(emptyChat("v"), MESSAGE, load("confirm").filter((e) => !(e.type === "CUSTOM" && e.name === "confirm_inputs"))));
    expect(html).toContain('class="ask inputs-card ic ta-rise"');
    expect(html.match(/class="md-table"/g)).toHaveLength(1);
    expect(html).not.toContain('class="ic-row');
  });

  it("folds to one line once Run is pressed; the design follows in the same turn", () => {
    const html = draw(replay(reduce(asked, { type: "answer", answers: { confirm: "Run the design with these inputs" }, at: 1 }), load("confirm-run")));
    expect(html).toContain("<strong>Inputs confirmed</strong>");
    expect(html).not.toContain('class="ask inputs-card');
    expect(html).not.toContain("md-table");
    expect(html).toContain("I recommend </span><strong>");
    expect(html).toContain('<span class="alt-badge">1D-HP-EC</span>');
  });

  it("after Change an input first, the composer asks for the change", () => {
    const changing = replay(reduce(asked, { type: "answer", answers: { confirm: "Change an input first" }, at: 1 }), [
      { type: "RUN_STARTED", threadId: "v", runId: "r2" },
      { type: "TEXT_MESSAGE_CONTENT", messageId: "m2", delta: 'What should I change? For example "a 50 °C heating return".' },
      { type: "RUN_FINISHED", threadId: "v", runId: "r2", outcome: { type: "interrupt", interrupts: [{ id: "r2-ask", reason: "confirm" }] } },
    ]);
    const html = draw(changing);
    expect(html).toContain("<strong>Changing an input</strong>");
    expect(html).toContain("What should I change?");
    expect(html).toContain('placeholder="Type what to change, e.g. a 50 °C heating return"');
    expect(html).toContain("Waiting for what to change");
  });

  it("a typed change is a new message: the old card says how the agent read it", () => {
    const next = send(asked, "a 50 °C heating return", [
      { type: "RUN_STARTED", threadId: "v", runId: "r3" },
      { type: "STEP_STARTED", stepName: "confirm", metadata: { label: "Read the reply to the inputs", kind: "model" } },
      { type: "STEP_FINISHED", stepName: "confirm", metadata: { decision: "change", model: "qwen3.5:9b", device: "gpu" } },
    ]);
    const html = draw(next);
    expect(html).toContain("<strong>Changing an input</strong>");
    expect(html).toContain("as your message asks");
    expect(html).toContain("Read the reply to the inputs");
    expect(html).toContain('<span class="tag tag-amber">change an input</span>');
  });
});

describe("a new chat", () => {
  it("starts empty: the examples to start from, and no design until the user runs one (5 Nov)", () => {
    const html = draw(emptyChat("new"));
    expect(html).toContain("What should we design today?");
    expect(html).toContain("Design heating and cooling");
    expect(html).toContain("Lowest CO₂");
    expect(html).toContain("Compare depths");
    // The challenge's recommended design is no longer put in front of it.
    expect(html).not.toContain("recommended design");
    expect(html).not.toContain('class="lead');
    expect(html).not.toContain("€/MWh");
    expect(html).not.toContain("user-row");
  });
});
