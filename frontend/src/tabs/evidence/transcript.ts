// An eval case's transcript as a chat: each exchange is a message sent (or the answers to the
// card the agent showed) and the events that came back, played through the chat's own reducer.

import { emptyChat, reduce } from "../../agent/reducer";
import type { ChatState } from "../../agent/types";
import type { Transcript } from "../../workbench/types";

/** The case's chat, rebuilt from its exchanges (hackathon/evals/transcripts.py). */
export function transcriptChat(t: Pick<Transcript, "case" | "exchanges">): ChatState {
  let state = emptyChat(`replay-transcript-${t.case}`);
  t.exchanges.forEach((x, i) => {
    const at = Number(x.events[0]?.timestamp) || i;
    if (x.user.answers && state.turns.length) {
      state = reduce(state, { type: "answer", answers: x.user.answers, at });
    } else {
      state = reduce(state, {
        type: "send",
        turnId: `${t.case}-${i}`,
        message: x.user.message ?? Object.values(x.user.answers ?? {}).join("; "),
        at,
        designs: x.user.designs?.map((d) => ({ id: d, text: d })),
      });
    }
    for (const event of x.events) state = reduce(state, { type: "event", event });
  });
  return state;
}
