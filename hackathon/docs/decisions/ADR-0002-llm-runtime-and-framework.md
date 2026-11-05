# ADR-0002: CPU-first LLM runtime, a plain state machine, and GPU "deep mode"

- Status: **accepted** (27 Oct 2026, provisional: revisit after the 28 Oct bootcamp)
- Evidence: [research/llm_agent_stack_2026-10-27.md](../research/llm_agent_stack_2026-10-27.md),
  [research/hackathon_intel_2026-10-27.md](../research/hackathon_intel_2026-10-27.md)

## Context

- **Judges run the code** on CPU-only Windows laptops (8 cores, 16 GB) and score accuracy on
  held-out queries, speed and the number of prompts. The 2025 winner used Qwen2.5-1.5B via
  Ollama.
- **Small models handle single-shot structured calls but not multi-turn tool calling.** On BFCL v4
  multi-turn, Qwen3-1.7B scores 11% and Qwen3-0.6B 3.6%.
- **CPU prompt processing is the bottleneck.** About 4k uncached prompt tokens cost an estimated
  30–80 s on that laptop class.

## Decision

0. **No commercial LLM APIs** (team decision, 27 Oct). Only open-weight models run locally: in
   the agent, the evaluations, and any teacher, judge or fine-tuning step. The teammate runs
   the CPU shortlist on the laptop, which doubles as a check that the judges can install and
   run it. Coding assistants the team uses are not part of the submission.
1. **Judged path: one or two LLM calls per query.**
   - **Call 1** is a grammar-constrained Ollama `format` JSON schema returning
     `{is_relevant, intent, workflow, params, missing[]}`.
   - When something is missing, a clarifying question is rendered from a template, with no
     LLM call.
   - Physics, optimisation and verification run in Python.
   - **Call 2** (optional) is an explanation of at most 150 tokens, with numbers filled from the
     design ledger through placeholders.
2. **Pick the default model by measurement** on the teammate's laptop (the judge proxy). Use the
   same eval scenarios and log tokens and time. Shortlist:
   - `qwen3:1.7b`
   - `qwen3.5:2b-q4_K_M`
   - `qwen2.5:1.5b` (2025 winner, baseline)
   - `qwen3:0.6b`
   - `granite4.2:3b`
   - `functiongemma:270m`
   - plus `llama3.2:3b` (GEMINI's current default)

   All are Apache-2.0 except FunctionGemma (Gemma terms) and Llama (community licence).
   Excluded for non-OSI licences: xLAM, Hammer, Arch.
3. **Ollama settings, fixed for every call:**
   - `num_ctx 4096`, `num_thread 8`, `temperature 0`, `seed 42`, `think false`,
     `keep_alive -1`, `num_predict ≤ 256`.
   - Changing `num_ctx`, `num_thread` or `num_batch` reloads the model, so never vary them.
   - Pre-load and warm the byte-identical static prefix at startup. Keep the uncached part of
     each prompt to about 800 tokens or less.
   - Ship a Modelfile (`ollama create geo-agent`) so the settings hold through the
     OpenAI-compatible API too.
   - Log `prompt_eval_count`, `eval_count` and the durations.
4. **Framework.** A plain Python state machine on the `ollama` client (GEMINI already pins
   `ollama==0.5.4`, which supports `format`, `tools` and `think`), with Pydantic validation.
   There are no automatic retry loops, because every retry is an extra prompt. Deep mode uses
   the `openai` client against vLLM. LangGraph stays optional: 1.0.1 resolves against GEMINI's
   pins, if checkpoints or HITL are ever needed.
5. **UI streaming.** Our loop emits AG-UI events directly (the `ag-ui-protocol` encoder), so we
   don't need `ag-ui-langgraph` (see ADR-0003).
6. **Deep mode (GPU, development only; never on the judged path).**
   - vLLM 0.32 serving `Qwen/Qwen3.8-27B-FP8` (about 31 GB) on **one** A6000. TP=1 avoids the
     tensor-parallel drift issue (#40725). The GPUs are NVLinked, but one card is enough.
   - Fallback: `Qwen3.6-35B-A3B-FP8`.
   - Used for open-ended planning, automatic model generation (its output becomes committed
     Python plus tests) and as a teacher for distillation.
7. **Optional LoRA distillation (D3–D4)**, only if held-out accuracy falls short:
   - Data: teacher-generated tool calls, kept only if they execute correctly against GEMINI.
   - Training: an Unsloth bf16 LoRA on `qwen3:1.7b` or `qwen3.5:2b` (about 5 GB VRAM).
   - Export: merge, convert to GGUF `q4_k_m`, wrap in an Ollama Modelfile. LoRA adapters are
     deprecated in Ollama, so merging is required.
   - Distribution: host the GGUF on the HF Hub and test `ollama pull hf.co/...`.
8. **MCP server** (spec 2026-07-28; Python SDK 2.x or FastMCP 4) exposing GEMINI tools, for
   development, reuse and upstream. Keep it **out of the timed path**: in-process calls are faster.

## Rejected

- **LiteLLM:** its PyPI package was compromised twice in 2026.
- **RouteLLM:** stale since 2024.
- **Guard models on the CPU path:** RAM and latency for little risk.
- **Langfuse on the judge path:** 6 containers, ≥16 GiB recommended. Dev only, if at all.
- **Semantic answer cache:** held-out queries don't repeat, and it is unsafe for numbers.

## About "JEV" (Reza's question)

- **What it is.** "Jev" is **TypeSafe AI's closed "System One" decision model**: typed
  choice, score and yes/no answers with calibrated probabilities. Its own docs say "Jev is not a
  calculator". It is not Meta's JEPA.
- **Open alternatives.** Cloudflare Clef, vLLM Semantic Router `d3`, Together `tev1`, Amazon
  strands-decider. They are served through `/v1/systemone` in recent Ollama and vLLM.
- **Where they fit.** Single-pass System-1 checks: is the request relevant, which workflow, what
  is missing. That is exactly what Call 1 already does inside one structured call.
- **Our use.** Benchmark `tev1:0.8b` or `d3:2b` as the router **only** if Call 1 underperforms. A
  second resident model costs RAM on a 16 GB laptop.
- **Design decisions** come from simulators plus optimisation: Optuna, BoTorch/Ax, pymoo for
  Pareto fronts and SALib for sensitivity. Meta's JEPA world models (video and robotics
  planning) are not usable here within a week.

## Consequences

- **Upgrade Ollama** on both team machines. 0.13.0 is installed here; the caching and options
  behaviour above was checked in the 0.40.x source.
- The judges' README pins the Ollama model tag and the `ollama create geo-agent` step.
- Disk: about 31–38 GB per deep-mode checkpoint. The GPU box has about 249 GB free.
