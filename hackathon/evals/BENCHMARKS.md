# Model benchmarks and why each role uses its model

All runs are on 28 Oct 2026, on the team machine: an RTX A6000, or 8 CPU threads with the GPU
hidden. Every model is open-weight and served locally by Ollama. Raw runs are in
[`runs/`](runs/), and the decisions are in the ADRs linked below.

## Summary

| Role | GPU | CPU | Why |
|---|---|---|---|
| Reader (every message) | `qwen3:1.7b` | `qwen3:1.7b` | Accurate enough to route, 2.2 s per turn on the CPU, Apache-2.0, handles Dutch. |
| Answerer (every reply) | `qwen3.5:9b` | `qwen3:1.7b` fast, `qwen3.5:4b` reasoning | 9B: 25/25 scenarios at 2–4 s. On a CPU the 9B is too slow; 1.7B passes 23–24/25 at 8–20 s. |
| Planner, reflector (reasoning) | `qwen3.5:9b` | `qwen3.5:4b` | Three capped reasoning steps in the JSON, with native thinking off (thinking never finished). |
| Claim checker | `qwen3.5:9b` | `qwen3.5:4b` (reasoning only) | Caught 8 of 8 false claims; 1.7B removed 2 of 8 true sentences, so it does not check. |
| Model builder | `qwen3.5:4b` | `qwen3.5:4b` | Writes code checked in a sandbox and approved by the user. |
| Image questions | `qwen3.5:9b` | `qwen3.5:4b` | The qwen3.5 models can see images; qwen3 cannot. |
| Document search | `snowflake-arctic-embed:s` | same | 67 MB embedding model, in GEMINI's own embedding family. Keyword search is the fallback. |

## 1. Reader: ten CPU models on the first pipeline ([ADR-0002](../docs/decisions/ADR-0002-llm-runtime-and-framework.md))

The morning runs used the first agent, where code made almost every decision. There were 12
scenarios; the 12th needed attachments, which that agent could not take yet.

| Model | Scenarios passed | Seconds per scenario | Tokens per scenario |
|---|---|---|---|
| `functiongemma:270m` | 11/11 | 0.5 | 601 |
| `qwen3:0.6b` | 10/11 | 1.2 | 571 |
| `qwen2.5:1.5b` (the 2025 winner) | 11/11 | 1.8 | 565 |
| **`qwen3:1.7b`** | 11/11 | 2.2 | 577 |
| `llama3.2:3b` (GEMINI's default) | 11/11 | 3.1 | 565 |
| `qwen3.5:2b` (q4_K_M) | 11/11 | 3.3 | 570 |
| `granite4.2:3b` | 10/11 | 4.1 | 614 |
| `qwen3.5:4b` | 11/11 | 7.5 | 571 |
| `bonsai-2:4b` | 11/11 | 13.6 | 571 |
| `bonsai-2:9b` | 11/11 | 23.6 | 571 |

- Even a 270M model passed, so these scenarios did not test understanding. ADR-0004 drew that
  conclusion, and the model now does more: it decides relevance and intent, and the answerer
  writes every reply.
- `qwen3:1.7b` was kept for four reasons:
  - It is among the fast models.
  - It is reliable with JSON schemas.
  - It is Apache-2.0.
  - It follows Dutch better than the sub-1B models.
- This benchmark predates the 25-scenario suite and the answerer, and has not been re-run on
  them yet.

## 2. Reasoning: native thinking against capped steps ([ADR-0004](../docs/decisions/ADR-0004-model-decides-code-checks.md))

| Way to reason | Device | Time per call | Result |
|---|---|---|---|
| `qwen3.5:9b`, native thinking, 4,096-token budget | GPU | 45 s | no answer: still thinking |
| `qwen3.5:4b`, native thinking, 1,024-token budget | CPU | 73 s | no answer: still thinking |
| `qwen3:1.7b`, native thinking | CPU | 30 s | called the absorption chiller a heat pump |
| **`qwen3.5:9b`, 3 capped steps in the JSON reply** | GPU | 2 s | sound plan |
| **`qwen3.5:4b`, 3 capped steps in the JSON reply** | CPU | 8 s | chose heat pumps the user had ruled out (code removes them) |

Native thinking is off everywhere. The reasoning model writes up to three short steps inside its
JSON reply, and code checks every decision it makes.

## 3. Answerer: the 25 scenarios ([ADR-0005](../docs/decisions/ADR-0005-answerer-and-roles.md), [ADR-0006](../docs/decisions/ADR-0006-files-markdown-citations.md))

| Answerer | Scenarios passed | Seconds per turn |
|---|---|---|
| `qwen3.5:9b`, GPU | 25/25 (24/25 in one run; that miss was later fixed in code) | 2–10 |
| `qwen3:1.7b`, CPU | 23–24/25 before the slips were fixed in code | 2–40 |

- On the CPU, the 1.7B made about one plain-word slip in five replies. Examples:
  - it labelled a greeting "nonsense";
  - it wrote the poem it was asked for;
  - it answered "is this a good design?" without numbers.

  Each slip now has a code rule and a unit test.
- The 9B misquoted 2,500 m as 250 m once; the number check caught it.

## 4. Claim checker ([ADR-0007](../docs/decisions/ADR-0007-claim-checker-and-lean-context.md))

The test has 16 sentences, checked against the self card and a GEMINI passage. Eight are true
(two of them general knowledge) and eight are false:

- features Dioscuri lacks;
- a cooling model GEMINI lacks;
- a commercial API;
- a made-up site;
- validation data that does not exist;
- live weather;
- a wrong database;
- drilling-risk planning.

| Checker | False claims caught | True claims wrongly removed | Time per check |
|---|---|---|---|
| **`qwen3.5:9b`** | 8 of 8 | 0 of 8 | 0.8 s (GPU) |
| **`qwen3.5:4b`** | 8 of 8 | 1 of 8 | 1.2 s (GPU), 11 s (CPU) |
| `qwen3:1.7b` | 7 of 8 | 2 of 8 | 0.2 s (GPU), 4 s (CPU) |

A checker that removes true sentences does harm, so models under 2B do not check.

## Not yet benchmarked

- **Readers on the current suite.** Re-run them on the 25 scenarios now that the answerer
  depends on the reader's labels.
- **The judges' hardware.** Run the CPU suite on Ali's laptop as the stand-in for the judges'
  machine.
- **lfm3.** It needs Ollama's MLX build.
