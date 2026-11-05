# ADR-0009: The reader suspects, a larger model decides; context over routing rules

- Status: **accepted** (30 Oct 2026). Amends [ADR-0004](ADR-0004-model-decides-code-checks.md)
  (who may refuse), [ADR-0005](ADR-0005-answerer-and-roles.md) (the answerer may run the design)
  and [ADR-0007](ADR-0007-claim-checker-and-lean-context.md) (the claim check).
- Evidence: the user's conversation of 30 Oct (trace `34b3af21ac93`), the replays of it and of
  19 reworded requests on the GPU and the CPU, `unit_test/gemini_agent/test_understanding.py`,
  scenarios S29–S34.

## Context

In one conversation on 30 Oct the agent:

- refused "please do the design work and give me the full report": the small reader
  (qwen3:1.7b) flagged it as a request to skip the checks, and a word list confirmed the flag
  because the message contains "report";
- answered "what breaks physics?" with an invented conflict, since its context did not say
  why it had refused;
- could not say where the 87 °C comes from. The requirements PDF gives a 2,500 m depth, a
  30 °C/km gradient and a 12 °C surface temperature, but never 87 °C. The fact was labelled
  "from the requirements", the PDF was not searchable, and the preview showed one word per line;
- offered "A1 (2.5 km) or A2 (1.5 km)" designs from a self card still written for the toy model;
- showed "That's outside what I do" after its claim check removed most of an in-scope answer.

The user asked for fixes that don't hard-code phrasings: people ask for the same thing in many
ways.

## Decision

1. **The reader's flags are suspicions.** A request to skip the checks is refused only when the
   reasoning model confirms it with one focused question (`intake.confirm_bypass`,
   `prompts/screen_v1.txt`). The refusal says what was understood ("You asked me to report a
   95% CO2 saving"). With no model to confirm, only a message that says "ignore/skip the
   simulator" in plain words is refused. The "report/tell/say" word list is gone.
2. **A larger model may run the design the reader missed.**
   - On the GPU the answerer (qwen3.5:9b) returns `run: "design"` when the message asks for a
     design, a study or a report of one (`answer_v6`). The agent then runs the design instead of
     showing that reply.
   - On the CPU the answerer is the reader's own model, so the reasoning model (qwen3.5:4b)
     answers one focused question instead (`intake.wants_design`, `route_v1`). Offered the run
     itself, the 1.7b ran designs for questions about sources.
3. **Context over rules.** The answerer always gets the following, so it can answer phrasings no
   rule anticipated:
   - the project's facts, each with where it comes from and how; for example, 87 °C is "worked
     out by Dioscuri from section 3.1, which gives no temperature itself", and the returns are
     "Dioscuri's assumption";
   - what the demand files hold (totals, peaks and their days);
   - each design's check results;
   - the last search: the pick, its rivals and why each lost;
   - the kind of each earlier reply (for example "declined: …");
   - a self card for the challenge engine (`self_v2`).
4. **Documents are read and searched.** A page that comes out one word per line (a Word export)
   is read again in pypdf's layout mode. Each project's documents are indexed under the project
   and searched with every query, kept apart from the user's uploads. The reader's "unrelated"
   no longer skips the search. The preview shows the PDF itself, with the text the agent reads
   as a second tab.
5. **The claim check removes less, and never refuses.**
   - It reads the conversation and a source budget sized to its model's context (not a fixed
     3,600 characters).
   - It counts direct inferences as supported (`claims_v2`).
   - Before a sentence goes, the model must quote words from the sources that back it, and code
     checks that the quote is really there (`claims_quote_v1`).
   - When most of a reply goes, a reply backed by a tool result shows that result. Any other
     reply keeps what was supported and says what it could not confirm; it never falls back to
     the out-of-scope template.
   - A small answer model's reply is checked by the reasoning model instead of not at all.
   - A reply that describes an opened document is checked: it is the model's reading. The
     answerer reads up to 5,000 characters of such a document, plus the passages that best
     match the question.
   - A reply that dropped a key value is no longer sent back for a retry when code can add
     the draft's sentence back.

## Amendment of 30 Oct (evening): once a design exists

The user's second conversation showed the next layer of mistakes, all after the first design:

- "why does the design show 102 °C when the reservoir is 87 °C?" became a what-if with a 0 °C
  change and an invented explanation (the design's context never said its wells were at
  3,000 m, where the rock is 102 °C);
- "do another design attempt" re-ran the same search and gave the same design;
- a question from the Evidence tab, read as "compare", re-ran the search before answering;
- every follow-up answer repeated the design's summary sentence and a "feasibility" note;
- "why is the chiller disconnected?" was answered without knowing what the canvas shows.

Decisions:

7. **A design's context states its physics and its connections** (`answer.design_notes`): the
   aquifer the wells are in (known at 2,500 m, or assumed deeper), the rock temperature there
   and how it is derived, the wellhead loss, the reinjection temperature, and what each unit is
   connected to (grid, gas, cooling towers). The plant canvas shows the same: a grid node, the
   cooling towers, and the reservoir band says when the aquifer is assumed.
8. **Once a design exists, a design-shaped message is confirmed before a new run.** A what-if
   that changes nothing is a question. A reader intent of design or compare with no new input
   (depths, doublets, exclusions, temperatures, objective) goes to the reasoning model's
   one question (`route_v1`); "no" answers from the design's context.
9. **The same search is not run twice.** A brief equal to the last search's (`engine.same_search`)
   gets a reply that says the search is deterministic and offers choices: the runner-up in
   full, the other objective, the known aquifer only, a design without the top-up it used.
   "Show the runner-up, X, in full" adds that candidate to the chat's designs with its card.
10. **The design summary is context, not a draft, for questions about it.** Its key values are
    no longer forced into every answer; the answer prompt no longer asks for a feasibility note.
11. **Quotes must be about the sentence** (`claims.backs`): every number of the sentence in the
    quote or the sources, and a third of its content words in the quote.
12. **Every search is an attempt** (`S1`, `S2` …) kept with the conversation; the Compare tab
    shows them apart, and each candidate and design carries its attempt.
13. **The wellhead temperature depends on the flow** (Ramey 1962, rock warmed for a year:
    about 0.9 K lost at 300 m³/h and 5 K at 50 m³/h at 2,500 m), in the GEMINI adapter and the
    plain-physics doublet, and in the year model each day uses the temperature at that day's
    flow per doublet (the flow is planned with the full-flow value). This moved the pick: one
    doublet at 3,500 m (always at full flow) is now 0.1 €/MWh ahead of two at 3,000 m, which
    share a lower flow for most of the year.

## Consequences

- One more model call when the reader suspects a refusal (about 0.5 s on the GPU), and one more
  when the answerer asks for a design run (the run then costs what a design costs).
- On the GPU all 19 reworded requests reach the right path:
  - all 6 design requests run the design (3 of them recovered by the answerer);
  - all 3 real requests to skip the checks are refused, each saying what was asked;
  - the 4 questions about the 87 °C explain it from section 3.1.
- Scenarios S29–S34 cover these. On the GPU all 34 pass (S34 after the retry change; three
  repeat runs).
- On the CPU the 6 design requests and the 3 refusals behave as on the GPU. The answers to
  source questions are limited by the 1.7b answerer. The 4b check removes its wrong statements
  ("Yes, 87 °C is in the PDF"), and the reply then says it could not confirm. Using the 4b as
  the CPU's answerer would fix this at about twice the answer time.
- On the CPU a message the reader calls unrelated is answered first, and the reasoning model is
  asked about a design run only when the answerer treats it as about the project. This keeps
  the weather and the poem at two model calls. The full CPU run passed 32/34 before this
  change; the affected scenarios then passed 7/7.
- A request the reader routes to a design that is really a question about the current design
  ("is anything physically impossible in this design?") re-runs the search before answering.
