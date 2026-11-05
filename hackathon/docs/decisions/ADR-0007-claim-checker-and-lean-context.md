# ADR-0007: A claim checker for words, a leaner context, charts for design results

- Status: **accepted** (28 Oct 2026). Builds on [ADR-0005](ADR-0005-answerer-and-roles.md)
  and [ADR-0006](ADR-0006-files-markdown-citations.md).
- Evidence: the claim benchmark and token probe of 28 Oct below; `src/gemini_agent/claims.py`,
  `prompts/claims_v1.txt`, `prompts/answer_v4.txt`.

## Context

- The number check proves every number, but not the words. The small answerer could still
  say "Dioscuri models aquifer storage" or "GEMINI includes a cooling model" (ADR-0005, known
  limits).
- A turn cost two model calls and 1,900–3,800 tokens. The full self card (about 800 tokens)
  and all simulated designs (about 450) went to the answerer on every turn, including "what
  will the weather be?". Speed and the number of prompts count in judging.
- A design reply had no charts: only yearly splits and the result card of the chosen design.

## Decision

1. **Claim checker** (`claims.py`, step "Check the claims").
   - A second call gets the reply's sentences and the blocks the reply relied on, and gives
     each sentence one verdict: supported, general knowledge, unsupported, contradicted, or
     no claim.
   - Code removes the unsupported and contradicted sentences. When more than half the claims
     go, the checked template is shown instead.
   - Not sent to the checker: sentences copied from the checked template, table rows (the
     number check covers them) and questions.
   - When it runs (`check_claims`, default "auto"):
     - it checks replies written freely from documents or the self card;
     - it checks every reply in reasoning mode;
     - it skips replies that reword the checked template, describe an opened file, or greet.
   - The checker is the answering model, so no second model is loaded. A model under 2B does
     not judge: in the benchmark below, `qwen3:1.7b` removed 2 of 8 true sentences. So on a
     CPU in fast mode the step says it is skipped and why, and reasoning mode (`qwen3.5:4b`)
     checks.
2. **A leaner context** (`answer_v4`, the pack).
   - The whole self card goes only with messages about Dioscuri; others get one line.
   - Designs go in full only when the message is about designs; otherwise one line each.
   - A value question's project block holds only the values asked for.
   - The history keeps two exchanges, not three.
   - A prompt rule is sent only when the blocks it is about are present: the draft rule with a
     draft, the file rule with a file.
   - A message that plainly asks to see a file skips the reader.
   - A greeting matched by pattern gets the self card only (from ADR-0006).
3. **Charts for design results.**
   - `simulate_year` also returns the energy per month by source (`monthly_gwh`). The result
     card draws it as stacked monthly columns against demand.
   - A new event, `comparison`, puts the designs side by side (cost of heat and cold, CO₂
     saving, coverage, capital) for a comparison chart.
4. **The self card states what GEMINI lacks.** GEMINI has no cooling model; Dioscuri's cooling
   models are its own. The checker can only call a claim contradicted if a source says so.

## Consequences

- **Claim benchmark.** 16 sentences against the self card and a GEMINI passage: 8 true (two of
  them general knowledge) and 8 false (features Dioscuri lacks, a made-up site, a wrong
  database). Groups of four, as in a reply:

  | Checker | False claims caught | True claims removed | Time per check (GPU) |
  |---|---|---|---|
  | `qwen3.5:9b` | 8 of 8 | 0 of 8 | 0.8 s |
  | `qwen3.5:4b` | 8 of 8 | 1 of 8 | 1.2 s (11 s on the CPU) |
  | `qwen3:1.7b` | 7 of 8 | 2 of 8 | 0.2 s (4 s on the CPU) |

  Before the self card named GEMINI's missing cooling model and the prompt defined "general"
  more sharply, the 9B caught 7 of 8 and the 1.7B 5 of 8.
- **Token probe.** The same seven turns on the GPU (a design, a value question, a documents
  question, "what are your advantages", a file, the weather and "is this a good design?"):
  23,219 tokens before, 15,380 after (−34%), not counting the checker.
  - The file request fell 61%, with no reader call.
  - The weather question fell 45%.
  - The value question fell 39%.
  - The documents question fell 35%.
  - A checked turn adds about 1,150 tokens and 0.8 s on the GPU.
- **Eval runs, 25 scenarios.**
  - **GPU, with the checker:** 24 of 25. The miss was S13 ("Who are you?"): its limit of one
    call predates the check of its claims about itself. The limit is now 2, and the re-run
    passes. The suite used 67,934 tokens against 73,037 before (−7%), including five checker
    calls; without them it would be about −16%.
  - **CPU** (1.7B, which does not check): 25 of 25. It used 59,635 tokens against 69,594
    (−14%), and 399 s against 510 s (−22%).
- The reader's prompt (about 800 tokens) is unchanged: it is already lean, and trimming its
  examples would cost the 1.7B model accuracy.
