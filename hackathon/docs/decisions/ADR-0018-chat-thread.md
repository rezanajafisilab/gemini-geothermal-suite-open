# ADR-0018: The chat's thread, kept by code; prompts guarded against the window

- Status: **accepted** (4 Nov 2026). Amends [ADR-0005](ADR-0005-answerer-and-roles.md) (the
  answerer's last exchanges), [ADR-0007](ADR-0007-claim-checker-and-lean-context.md) (the
  history kept two exchanges), [ADR-0014](ADR-0014-premises-stops-grounding.md) (premises) and
  [ADR-0017](ADR-0017-chat-needs-options-risk.md) (no default design). Plan:
  `hackathon/docs/plans/2026-11-04-plan.md`, stream B.
- Evidence: `src/gemini_agent/thread.py`, `unit_test/gemini_agent/test_thread.py`, the long
  conversation eval `hackathon/evals/scenarios/conversations.yaml` (runs
  `hackathon/evals/runs/conversations_*`).

## Context

- A teammate's long test showed the chat losing the thread. Only the answerer saw earlier
  turns: two exchanges, the message cut to 160 characters and the reply to 240, and dropped
  first when the prompt was full. The readings that decide what a message asks (the reader,
  the planner, the options and needs calls, the route and the inputs card's reply) saw none.
- "What does heat cost in the design you recommended?", "And with 45 °C?", "the second one",
  "back to the original design" could not be read. A question about "it" got "which design?"
  each time; "and in the original design, without the cheaper gas?" ran a new design search.
- A typed reply to a question Dioscuri asked ("the cheapest one" after "which design?")
  dropped the question and was read as a new message.
- Wrong statements were checked only by the planner, which reads no message before a design
  and no "why" question; "earlier you told me the reinjection is 37 °C" was read as a message
  about Dioscuri and answered without saying it was wrong.
- Answer prompts reached 8,042 tokens in an 8,192-token window with 1,400 to write. Design
  blocks (8-9k characters each) were never trimmed, and number-heavy text runs at 2.8-3.1
  characters a token, not the 3.2 the budget assumed. A 55,000-character prompt came back as
  4,098 prompt tokens: Ollama had cut its start, the rules with it, without a word.

## Decision

1. **The thread, kept by code** (`thread.py`, saved with the session; no model call). After
   each turn: one line (what was asked, what was done: the what-if run, the search's pick, the
   design an answer was about; the reply's opening with its numbers), forty kept; the design
   under discussion; the last list shown (the designs a reply named, in its order, the
   search's picks, or a question's options); the question left open; what the user stated as
   given and whether it was corrected. A prompt shows the turn count, the chat's first two
   turns, the last twelve as lines and the last exchanges, every turn numbered (T1, T2 ...),
   and names the turns it leaves out: a turn not shown is said to be unknown, never guessed
   (the model had answered "what did I ask first?" with the earliest turn it could see).
2. **Every reading gets it**, before "Message:", sized to the call: the reader, the options,
   needs, route, confirm and open-question calls about 1,000 characters (the last two
   exchanges, the focus, the list); the planner about 2,400 (eight earlier lines, three
   exchanges); the answerer about 5,200 (twelve lines, three exchanges with 600 characters of
   each reply). Without history the messages are exactly as before: the fine-tuned models'
   short form is unchanged. The planner's prompt (`parameters_v3`) says what the thread is
   for: a design the message points to ("it", "the design you recommended", "the second one"),
   a short follow-up's parameter ("and with 45 °C?"); changes, premises and numbers still come
   from the message, which code checks as before.
3. **No default design, but the conversation names one** (amends ADR-0017): before asking
   "which design?", a short call (`parameters.design_meant`, prompt `which_v1`, about 850
   tokens, 0.3 s on the GPU) gives the model the chat's designs (what-ifs included, the one
   under discussion marked) and the thread; it answers with a design's name, not a number,
   so "the second one" means the chat's list. A message that names none, a what-if
   included, is about the design under discussion; "that one" after a reply that picks a
   design is that design; "several" (which designs so far, a summary) asks nothing; the user
   is asked when the message points away ("the other one") or nothing is under discussion.
4. **A typed reply to an open question** (`parameters.answers_question`, prompt `open_v1`):
   the model says whether it answers the question and which option or words; code maps that
   onto what the buttons send. The inputs card stays open over a side question.
5. **Wrong statements**: before a design, a question with figures is read by the planner for
   what it states and answered, not run as a design; its figures are checked against the
   project's own facts (demand, reservoir), paired by their words or, when only one fact has
   that unit, by the unit ("3,500 m and 120 °C" against the reservoir's 2,500 m and 87 °C).
   What the message says Dioscuri said ("you told me the boiler covers 13 %") and figures of
   the project's given data said differently in a question are premises; a value of the
   user's own networks or district ("our cooling network returns at 15 °C") sets the
   parameter. Once a design exists, a message whose reading changes nothing and whose reply
   needs one existing design is answered, whatever the small reader made of it ("it has 2
   doublets, hasn't it?" ran a 2-doublet search). When no planner read the message (a why, a
   message about Dioscuri), or its reading has nothing to run, the answerer's own verdict on
   the premises counts and leads ("Not quite. ..."); not with a change to run (1 Nov: "could
   we move the stop to August?"). The answer prompt (`answer_v7`) says to check "you said
   ..." against the history; the claim checker takes the user's lines of the thread as
   evidence, never Dioscuri's own earlier replies.
   The history's user lines are not sources for the reply's numbers.
6. **A guard on every call** (`llm.py`): the prompt is estimated (a token per digit and per
   non-ASCII character, 3.6 characters a token for the rest: 0-15 % above Ollama's counts on
   qwen3.5:9b) and a prompt that does not fit the window with its answer is not sent
   (`ContextOverflow`). The answerer budgets in tokens (at most 7,600 in all) and gives up
   context in order: passages after the first two, the other designs (cut, then dropped), the
   search and runs, the history (cut to its latest part, never dropped), the choices, the cost
   and operation lines; the self card, project, draft, files and the current design stay. Each
   call's estimate and window are in the trace (`call_tokens`).
7. **The reasoning model's window on the GPU is 16,384** (`DIOSCURI_REASONING_CTX`; the CPU 4B
   keeps 8,192): Qwen3.5-9B caches keys and values in 8 of its 32 layers, 32 KiB a token, so
   the larger window costs 0.25 GB. It is room against a short estimate, not a larger prompt.

## Consequences

- **Long-conversation eval** (`conversations.yaml`: 5 chats, 65 typed turns, 210 checks;
  qwen3:1.7b reader, qwen3.5:9b on the GPU in an 8,192 window, so the shared models were not
  reloaded during the runs):

  | Chat | Before (turns, checks) | After (turns, checks) |
  |---|---|---|
  | C1 pronouns, a what-if, the original, a false "you said" | 2/13, 23/42 | 12/13, 41/42 |
  | C2 wrong facts before a design, typed "go ahead", "and with 45 °C?" | 4/13, 24/44 | 10/13, 41/44 |
  | C3 the picks as a list, "the second one", "that one" | 5/12, 24/41 | 8/12, 36/41 |
  | C4 questions answered by typing, a store what-if, off-topic and back | 5/12, 23/38 | 7/12, 32/38 |
  | C5 fifteen turns, documents, Dutch, two what-ifs | 1/15, 20/45 | 14/15, 44/45 |
  | All | 17/65, 114/210 | 51/65, 194/210 (last code: 50/65, 192/210) |

  Before, 41 of the 65 turns ended in "which design?"; after, 4. No turn had an ungrounded
  number in either run. Runs: `hackathon/evals/runs/conversations_*`.
- **The chat suite** (single questions after one design, 185 cases) checks for regressions:
  180/185 before; 166/185 with the first version of the thread (the search's picks listed as
  the last list pulled answers to other designs, the answerer's own premise verdict led plain
  questions with "Not quite", "about" messages lost the planner); 174/185 after those fixes,
  172/185 on the branch's last run. That run was taken from the code just before the
  which-design check was committed (another design than the one discussed needs the message
  or the last reply to point to it), so "the CO2 saving is 80 %, isn't it?" (three wordings)
  still got the lowest-CO2 pick's 88.6 % there. After the merge into rn/challenge (4 Nov) all
  three wordings answer with the design's 60.6 %, and the final GPU run gives 176/185 (premises
  14/15).
- **Wrong statements** corrected first in the final run: "you said heat costs 38 €/MWh",
  "the capital is about 20 M€?", "earlier you told me the reinjection was 37 °C", "the
  district needs 200 GWh, right?", "the aquifer sits at 3,500 m and 120 °C" (by code: "Not
  quite. The reservoir depth is 2,500 m. The initial reservoir temperature is 87 °C."), "up to
  five doublets", "it has 2 doublets, hasn't it?".
- **Merge note (4 Nov)**: `parameters_v3` was copied from `parameters_v2` before the
  several-aquifers stream added its aquifer edits to v2; the merge kept both files, so the
  chat lost those edits until they were copied into v3 (d27dd63; a test now checks the prompt
  in use).
- **The guard**: its estimate is within 0.89-1.04 of Ollama's counts (above it for the long
  calls); in the final run no call was refused and the longest prompt was 6,701 tokens, inside
  the 8,192 window with its answer.
- **Cost**: the thread is about 220 tokens in the short calls, 350 in the planner's and 400
  in the answerer's (850 at most), against about 140 for the old history; the which-design
  call adds about 850 tokens and 0.3 s when it runs. An answered turn's median went from
  18,400 to 22,100 prompt tokens, and its prompt reading from 3.0 to 4.4 s on a GPU shared
  with two other eval runs. On the CPU each thread is about half.
- **The fine-tuned reader**: dioscuri-castor reads 78/82 of the held-out messages, as on
  3 Nov (the short form is unchanged without history).
- **Left**: the claim checker still removes some true sentences in long contexts (C1 turn 6,
  C4 turn 10 lost their figure); "what did I ask first?" was answered with a later turn twice
  in the final run (since then the first two turns are kept in every cut, a premise is
  corrected only when this message states it, and a reply from the history alone is not sent
  to the claim checker: re-run on C2 and C4, both recall turns answer right); a what-if's figures
  are sometimes given for "the design itself"; the planner misreads some messages the thread
  cannot fix ("is that one fine if a unit fails?" claimed fine for a design that is not N-1;
  "30 % dearer electricity" asked "by how much?"). The CPU path (4B readings with the
  thread) had a two-turn smoke test only. The 16,384 window was not loaded during these runs
  (the GPU was shared); its cost is computed from the model's layers.
