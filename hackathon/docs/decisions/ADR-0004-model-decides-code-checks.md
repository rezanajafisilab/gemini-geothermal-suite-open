# ADR-0004: The model decides, code checks; a reasoning toggle

- Status: **accepted** (28 Oct 2026). Amends ADR-0002's "one call, then code" for reasoning mode.
- Evidence: eval runs in [`hackathon/evals/runs/`](../../evals/runs/) of 28 Oct, the timings
  below, and `src/gemini_agent/router.py`.

## Context

- Version 1 used the model for one thing: reading the message into a form. Code rules made
  every decision. It passed the 11 scenarios, but even a 270M model scored 11/11, so the model
  hardly mattered. Anything the rules did not foresee fell through: "who are you" was refused,
  and "what is the reservoir initial temperature?" got a design questionnaire.
- The organiser said on 28 Oct that the judges will have a GPU with at least 16 GB. Speed and
  the number of prompts still count, and a CPU-only machine must still work.
- Measured on 28 Oct (RTX A6000; 8 CPU threads):

  | Way to reason | Device | Time per call | Result |
  |---|---|---|---|
  | Qwen3.5-9B, native thinking, 4,096 token budget | GPU | 45 s | no answer: still thinking |
  | Qwen3.5-4B, native thinking, 1,024 token budget | CPU | 73 s | no answer: still thinking |
  | Qwen3-1.7B, native thinking | CPU | 30 s | answered; called the absorption chiller a heat pump |
  | Qwen3.5-9B, 3 capped steps in the JSON reply | GPU | 2 s | sound plan |
  | Qwen3.5-4B, 3 capped steps in the JSON reply | CPU | 8 s | chose heat pumps the user had ruled out |

## Decision

1. **Route every message.** The intake call also classifies questions about values, "who are
   you" and greetings. Greetings and "who are you" are matched by pattern and need no model
   call. Value questions are answered from the project data and the latest design, with the
   source of each number. General "how does ... work" questions are answered from GEMINI's
   documentation (its own RAG pipeline, with keyword search as a fallback).
2. **Three decision points** (`policies.py`): which designs to study (plan), which fixes to try
   when no design meets the brief (reflect), and how to word the answer (write).
   - **Fast mode** (default): code rules decide. One model call per turn.
   - **Reasoning mode** (the toggle): the reasoning model decides. It writes up to three short
     reasoning steps before each choice, and the UI shows them.
   - **Both modes**: the same code checks run after every decision. The plan may hold only
     modelled options that respect the user's exclusions, and it always includes the gas
     reference. A fix must be one that code built. An answer may contain only numbers that a
     tool, a cited document or the user produced; otherwise the template answer is kept. Each
     correction is shown, e.g. "left out A2: it needs heat pumps, which you ruled out".
3. **Router** (`router.py`). The fast model is `qwen3:1.7b` on whatever device Ollama picks.
   The reasoning model is `qwen3.5:9b` when a GPU with at least 9 GB free is found, and
   `qwen3.5:4b` on the CPU otherwise. Native thinking stays off. If the reasoning model is
   missing, the rules decide and the run says which command fixes it.
4. **The user decides at a shortfall.** When no design meets the brief, the run stops with one
   multiple-choice question: the fixes that were simulated, or "keep my limits". The pick
   continues the run without a model call, and the picked design is checked again.

## Consequences

- Fast mode on CPU: 18 of 18 runnable scenarios pass, at 2–3 s a turn and about 900 tokens a
  call (the prompt grew from about 600 tokens with the new intents).
- Reasoning mode on GPU: 18 of 18, with 1–3 calls and 2–5 s a turn once the model is loaded.
- The grounding check matches numbers, not their meaning: a reworded answer could swap two
  real values. The checks reduce this risk but don't remove it; the template text is kept in
  the trace (`draft`).
- Numbers quoted from documents count as sourced. Passages with instruction-like text are
  never quoted or passed to the model, so an injected claim cannot become a "sourced" number.
