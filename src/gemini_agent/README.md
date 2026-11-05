# gemini_agent: the Dioscuri agent

Turns a question about a district's geothermal heating and cooling into a verified design, and
answers questions about it. A code orchestrator runs role-specific local models, typed tools and
code checks (ADR-0004, ADR-0005): a small model reads every message, a larger one writes every
reply from what the agent knows, and in reasoning mode it also plans the study and picks fixes.
Typed tools compute every number, a verifier checks the physics, and no number reaches the user
unless a tool, a cited document or the user produced it. No commercial LLM API is used; the
models run in Ollama on the same machine.

## Run it

Start the model server once per session: `conda activate dioscuri && ollama serve`.

| What | Command (from the repo root) |
|---|---|
| Ask one question | `PYTHONPATH=src python -m gemini_agent "Design heating and cooling, 70/40 C and 6/12 C."` |
| ...as a laptop without a GPU would | add `--device cpu`; `--defaults` accepts proposed defaults |
| ...in reasoning mode | add `--reasoning` |
| ...with a file | add `--attach path/to/datasheet.pdf` |
| The app | `PYTHONPATH=src python -m gemini_agent.server`, then http://127.0.0.1:8000 |
| Eval scenarios | `python hackathon/evals/run_evals.py --model qwen3:1.7b --device cpu` (add `--reasoning`) |
| CPU model benchmark | `python hackathon/evals/run_evals.py --models qwen3:1.7b,qwen2.5:1.5b --device cpu` |
| Unit tests (no Ollama needed) | `pytest -q unit_test/gemini_agent` |

Models to pull: `qwen3:1.7b` (reader), `qwen3.5:9b` (answers and reasoning on a GPU),
`qwen3.5:4b` (reasoning on the CPU, and writing component models), `snowflake-arctic-embed:s`
(document search).

| Role (`router.py`) | GPU (header switch on GPU) | CPU |
|---|---|---|
| Reader: every message | `qwen3:1.7b` | `qwen3:1.7b` |
| Answerer: every reply | `qwen3.5:9b`, both modes (2–4 s) | `qwen3:1.7b`; `qwen3.5:4b` in reasoning mode |
| Planner and reflector (reasoning mode) | `qwen3.5:9b` | `qwen3.5:4b` |
| Model builder | `qwen3.5:4b` | `qwen3.5:4b` |

The 9B model is used on a GPU with at least 9 GB free. Each run may ask for `"device": "cpu"`;
the app's header switch does that.

## How a turn works

1. **Read** (`intake.py`). Greetings and "who are you" skip this call. Everything else gets
   one JSON-schema call to the reader (prompt `prompts/intake_v2`): relevance, intent, the
   values a question asks for, a bypass flag and any numbers. Code keeps only what the user
   actually wrote, in the role they wrote it: network temperatures by pattern, numbers only
   with their unit next to the right words, exclusions from negations. Only a request for a
   design (a design verb or domain words) starts the design path; everything else is
   answered. If Ollama is down or the model isn't pulled, the answer names the command that
   fixes it.
2. **Gather.** A message that names a file ("the table of heating_profile.csv", "plot the
   cooling profile", "what is in this picture?") opens it (`files.py`, tool `read_file`): the
   chat gets the file as a table with its statistics, a chart, a text preview or the image,
   and the answerer gets a summary (columns, ranges, energy over the file). The model never
   retypes rows; a table in its reply that copies the file's columns is removed. Questions
   about an image go to a model that can see it (`qwen3.5`). A value question runs a lookup
   over the project data and the latest design, each value with its source (`lookup.py`);
   other questions search GEMINI's documentation, the team's notes and the attached files
   (`docs.py`).
3. **Ask once.** A design request with missing inputs ends with **one** question listing each
   input with a proposed default (an AG-UI interrupt). The answers continue the run.
4. **Decide, engineer, verify** (`policies.py`, `tools/`, `verifier.py`):
   - **plan**: which designs to simulate. Rules in fast mode; the reasoning model in
     reasoning mode, writing up to three short reasoning steps. Code then drops options that
     need excluded equipment or aren't modelled and adds the gas reference, and says so;
   - typed tools simulate each design (`solve_doublet`, `simulate_year`, `economics`, all
     memoised). A tool that raises leaves out only the design that needed it;
   - the verifier checks every design: energy balance, the Carnot limit (recomputed here),
     the brine temperature path, reinjection, coverage, and each component (no temperature
     cross in the heat exchanger, no unit beyond its size, heat pump heat = electricity × COP,
     brine heat within what it carries). A design that fails is left out with the reason;
   - **reflect**: when no design meets the brief, fixes are chosen (rules or the reasoning
     model), simulated, and offered as a multiple-choice decision, "keep my limits"
     included. The pick continues the run and is checked again.
5. **Answer** (`answer.py`). The answerer writes the reply from a context pack: the self card
   (`prompts/self_v2.md`: who Dioscuri is, what it uses from GEMINI, strengths, limits, how to
   use it), the project, the simulated designs (values, where the heat comes from, checks),
   the last three exchanges, the passages found and, after a tool run, the checked template
   answer (`reporter.py`) as a draft it must keep. It says what it understood and what kind
   of reply it is: an answer, a multiple-choice question when the message can mean different
   things, "not a proper question" for letter mash, or "outside what I do". It may use
   Markdown (bullets, a small table, bold) and ends a sentence with the id of the block it
   relies on (`[doc1]`); code turns those into `[^1]`, the number of the source card. In
   reasoning mode it writes up to three short reasoning steps first.
6. **Check** (code). Every number must come from the context or the user, or be a difference
   or ratio of two numbers the reply states; citations must name blocks that exist; the
   draft's key values must stay. A reply that fails gets one retry naming the problem, then
   sentences (or table rows) with an unsourced number are dropped; with too little left, or
   with no model,
   the template is shown. Passages that read like instructions are never shown to a model,
   and the reply warns about them once per file. The **claim checker** (`claims.py`) then
   reads the sentences of a reply written freely (from documents or the self card, and every
   reply in reasoning mode) against the blocks it relied on, and removes what they do not
   support (ADR-0007). Before a flagged sentence goes, the model is asked to quote what backs
   it, reading first the sentence's nearest lines from every block the reply was written from
   (`claims.evidence`), since its own sources are cut at a budget (5 Nov: "a gradient of
   30 °C/km" and "the boiler covers 34.5 %" were removed when the facts saying so were past
   the cut); a quote cut with "..." counts when each part is in the sources, and "CO₂" reads
   as "CO2". A premise of the message shown false is corrected in the same turn: a reply that
   gives the correction and then asks something is an answer, not a clarifying question, and
   a reply that opens with "No" on a premise, its verdict sound (the user's words and figures,
   the right values from a source and in the reply), keeps that opening from the claim
   checker as it keeps code's correction. A number the guard asks about that rounds a context
   value ("63 %" for 63.1 %) is named with that value in the retry.

`Agent.run(session, message, reasoning=False, device=None)` yields AG-UI events (`events.py`):

- steps with label, code and seconds; decision steps (`plan`, `reflect`, `answer`) also carry
  `decided_by`, `steps` and `corrections` (the answer step adds `understood`, `kind`,
  `scope`, `model` and `device`);
- tool calls (a failed one's result is `{"cached": false, "error": "..."}`);
- model-call usage;
- the answer;
- `CUSTOM` events: `answer` (`understood`, `kind`, `scope`, `used`, `model`, `device`,
  `fallback`, `corrections`), `clarification` (`kind` "inputs", "decision", "choice", "offer"
  or "approval"), `result` (the card), `checks`, `suggestions` (the model's follow-ups),
  `sources` (the passages and files the answer cited, numbered as its `[^n]` markers, with
  `kind`, any `file` to open and the `images` of a documentation section, plus flagged
  ones), `file` (a file's view: `table`, `stats`, `totals`, `chart`, `text` or `image`, and
  the `show` the user asked for) and `model_unavailable` (`{model, error, fix}`, plus
  `fallback: "rules"` or `"template"`).

`RUN_FINISHED.result` is the run summary: behaviour, who decided each step, every model call,
tokens and seconds per phase, tool calls, cache hits, tool errors, designs left out, sources,
what the answerer understood, user turns, models and prompt versions. The server streams the
events as server-sent events, takes uploads at `POST /api/attachments` (documents, CSV,
JSON, Excel and images), serves files at `GET /api/files?threadId=&name=` (`&view=1` for the
chat's view) and documentation figures at `GET /api/doc-image?path=`, and saves each
conversation (with its files and last exchanges) under `hackathon/evals/runs/sessions/` after
every turn, so a restart continues it. Models: `DIOSCURI_MODEL` (or GEMINI's
`LLM_MODEL_VERSION`), `DIOSCURI_REASONING_MODEL`, `DIOSCURI_REASONING_MODEL_CPU`,
`DIOSCURI_MODELGEN_MODEL`; `DIOSCURI_DEVICE=cpu` makes the CPU the default and
`DIOSCURI_GPU=0` hides the GPU from the router.

The parameters reading (`parameters.read`) has two helpers. A reading in doubt (a value refused
or dropped while the message gives an amount of its unit, a value none of the message's amounts
gives, or nothing read from a message with an amount) is read once more with the amounts
`quantities.py` found (numbers and units only; the model decides what each is for), and kept
only if code accepts it; the run summary's `parameters.second_look` says why and which reading
was kept (`DIOSCURI_SECOND_LOOK=0` turns it off). `DIOSCURI_EXAMPLES=1` (off by default) adds
the three nearest worked readings of `data/reading_examples.npz` to the prompt
(`reading_examples.py`; built by `hackathon/scripts/build_reading_examples.py`, with no
message near an evaluation prompt), embedded by Ollama's `snowflake-arctic-embed:s`; without it,
no examples. `DIOSCURI_SHORT_PROMPTS=1` (or `0`) forces the fine-tuned models' short prompts
(or the full ones) for every model.

Three helpers keep track of the conversation and ask back with choices (4 Nov); each has a flag,
on by default, that turns it off:

- **The chat's state** (`chat_state.py`, `DIOSCURI_CHAT_STATE=0`). After every turn code notes,
  with no model call, the designs in the order they came up (id, code, pick or "what-if of A1",
  turn), the user's questions, the decisions (recommended, inputs confirmed, what-ifs run), the
  open question and the last figures a reply gave of a design (only its ledger values). The
  answerer gets it as a `state` block (designs with their figures); the parameters and needs
  readings get it, shorter, when the message names no design; the which-design reading
  (`prompts/which_v2`) gets each option marked "2nd in the last list shown", "the original
  design", the turn it came up and its figures, so "the second one", "the first one's", "the
  cheaper of the two" and "back to the original design" resolve. Older questions are cut short,
  then folded into one line that names the turns it covers; nothing is dropped without saying.
- **The capability card** (`capabilities.py`, `DIOSCURI_CAPABILITY_CARD=0`): what the plant
  model can do, generated from `parameters.OPTION_KEYS`, the stops, `parameters.UNITS` and the
  catalogue's prices. The answerer gets it with every reply; before Dioscuri says it cannot do
  something, a short `covers` reading asks the model, with the card, whether an option is meant
  (a switch then runs, a size is asked for); the "not modelled" reply lists the card's options.
- **Clarifying with choices** (`clarify.py`, `DIOSCURI_CLARIFY_CHOICES=0`). The parameters
  reading has an `open` field (beside the planner's yes/no `unclear`, a message with nothing readable): words whose referent neither the message nor the chat gives
  ("run it again with 2", "the setting we talked about"), with the keys they may mean. Code
  then asks one short question with two or three options it can run at once: the referents
  ("Number of doublets: 2", "Heat pump size: 2 MW"), the settings tried earlier or options the
  design lacks; for a change without an amount (`Reading.vague`), typical sizes from the
  catalogue for an option being added, whole numbers for a count, steps from the value now
  otherwise. Nothing runs on a guess. Each option's full request (the message with the
  amount) is kept in `session.pending["requests"]`, so a click or a typed "the first", "5,000"
  or "doublets" runs it. A design step for "best" alone while the needs reading says the reply
  is about a design that exists is answered, not run.

Three tools on the answer path (4 Nov) follow published agent practice: code keeps the facts,
an evaluator reads the output, and reasoning is spent only where it helps. Each has a flag;
`1` or `0` forces it, unset takes the default, and since 5 Nov all three are off by default.
Measured on 5 Nov on the merged code (memory layer, claim-check evidence, corrections first):
with value answers and the reply check on, 181/185, 47/52 and 61/65; with all three off, 181,
48 and 61 at 3 % less time. The tools no longer won anything the other fixes had not, and once
the "In short" line named the wrong design ("that one" after a list gave A48, not A139).

- **Value answers written by code** (`lookup.value_lines`, `DIOSCURI_CODE_FACTS`, off unless set to `1`). When the
  reading asks for values the design under discussion has (`asks_for` keys that `design_facts`
  or `money_facts` give: costs of heat, of cold, of both, CO2, capital, sizes, depth, COP, the
  investor's NPV, IRR and payback ...), code writes them first as "In short" lines, the design
  named: "- Cost of heat (A1 · 1D-HP-EC@3000-N1-FC): **64.7 €/MWh**". The answerer gets the same
  lines as a `values` block and explains them; a rule tells it never to give another number,
  another design's value or another quantity for one. The claim checker skips sentences that
  repeat the lines and reads the block among its other sources (the draft, read first, holds
  the same values). The block and its rule get room of their own on top of the context
  (`answer.own_room`): counted in every answer's budget, the rule cut 260-450 tokens of context
  from turns without values too (5 Nov). Nothing is written that was not asked, nor for a
  message that states values of its own (its premises are checked first, and the key read for
  it is a guess: "the boilers cover 25 %?" got "heat demand covered: 100 %"); a question no key
  fits is answered as before, and when the checked template stands in for the reply (which
  states the values itself) the lines are left out. The run summary's `code_facts` names the
  design and the keys.
- **The reply check** (`reply_check.py`, prompt `reply_check_v1`, `DIOSCURI_REPLY_CHECK`, off
  unless set to `1`). After a reply to a question is written and claim-checked
  (not a run report, a clarifying question or a refusal), one short call asks whether its first
  sentence answers what was asked and whether it speaks of everything the message names ("5
  MWp of solar"). Code keeps only listed items that are in the user's words and whose figures
  the reply does not already give. On a fail the answerer rewrites the reply once, told why
  (`answer.answer(revise=...)`: the same prompt, then its reply and the reason), and the rewrite
  gets every code check and the claim checker. When the rewrite is worse (it fell back to the
  template, is empty or no answer, or lost a number the first reply gave) the first reply
  stays. The run summary's `reply_check` has the verdict, the rewrite kept or discarded and
  why, and the calls, tokens and seconds it cost.
- **Thinking on hard turns** (`answer.think_first`, `DIOSCURI_THINK`, off unless set to `1`,
  never on the CPU; off since 5 Nov: over the three suites it won 4 cases and lost 7, asking
  "which 2030 targets?" or "which is the most reliable?" where the context answered, at 4-16 s
  a hard turn). When the turn reasons (`policies.wants_reasoning`), the answer's prompt first goes
  to a call of its own with Ollama's `think=True` and no format, cut at `THINK_TOKENS` (1,024,
  `DIOSCURI_THINK_TOKENS`); the answer call then reads that thinking as notes and writes the
  JSON as on any turn. One call with both a format and thinking does not work with
  qwen3.5:9b: on 4 Nov it thought through all 3,448 tokens of a trade-off question and wrote no
  JSON (70 s). Measured on 4 Nov on 11434 (qwen3.5:9b, 16k window, while both GPUs also ran
  evaluations: about 49 tokens a second) for three trade-off questions: the thinking call took 20.8-21.7 s (1,024 tokens,
  always cut), the answer after it 10.5-13.2 s (prompt 6,200-6,300 tokens, its start cached,
  454-596 tokens written), against 15.1-18.0 s for the answer without thinking (630-879
  tokens, one of which wrote its working into the reply). All three gave valid JSON. The
  thinking never reaches the reply; the call record keeps its start and end
  (`LLMCall.thinking`), and the run summary's `thinking` its tokens and seconds. The readers,
  the claim checker and the reply check never think.

## For the physics side (Ali)

`contract.py` is the v0 tool contract: every field carries its unit in its name. The tools in
`tools/toy.py` are **mocks on the team's toy model**. They reproduce the canvas numbers for A1:
61.8 GWh of heat, 13.7 GWh of cold, 6,080 full-load hours, 41 and 58 €/MWh. The example
project's files in `data/example_district/` (daily heat and cold demand for 2025, the
reservoir) are written from the same toy model and are **synthetic**; replace them with the
organisers' data. Replace them one
at a time with GEMINI-backed functions of the same name and types, and the agent needs no
change. A3 (aquifer storage) is reported as not modelled until its model exists.

## Known limits (28 Oct)

- **Tools:** all mocks; the organiser data is not in yet. Real tools should also fill the
  optional `heat_pump_electricity_gwh`, `brine_heat_gwh` and `brine_capacity_mw` fields so
  that the component checks run.
- **Grounding** matches numbers, not their meaning: an answer could swap two real values, or
  use a number that appears somewhere in the context in the wrong role. The template answer is
  kept in the trace (`draft`) when it was replaced.
- **Words are checked by a model, not proven.** The claim checker (ADR-0007) removes
  sentences its sources do not support. On 28 Oct it caught 8 of 8 false claims with
  `qwen3.5:9b` and with `qwen3.5:4b`. `qwen3:1.7b` removed 2 of 8 true sentences, so it does
  not check: on a CPU in fast mode, words stay unchecked unless Reasoning is on.
- **Tokens:** a turn costs the reader (about 870 tokens, skipped for greetings and file
  requests) and the answerer (900–1,600 with the lean context of ADR-0007). A free answer
  checked for claims adds about 1,150. On the CPU an answer from the 1.7B model takes 8–20 s.
- **Leaking examples:** small models copy values from the prompt's worked examples. The
  context checks drop them, and each run lists what was dropped (`dropped`).
- **lfm3:** needs Ollama's MLX build, so it isn't benchmarked yet.

## Documents

`docs.py` gives the agent document search as a tool. A passage explains a model, a method or a
datasheet value; the numbers of a design still come only from tools.

```python
from gemini_agent.docs import DocIndex
index = DocIndex()                                    # reads nothing yet
hits = index.search("how is the heat pump COP computed", k=4)
index.add_text(thread_id, "spec.pdf", text)           # this conversation only
hits = index.search("rated cooling capacity", k=4, thread_id=thread_id)
index.info()                                          # backend, model, chunks, timings, sources
```

- **What it reads** (`CORPUS`): GEMINI's `.rst` docs, the docstrings of `gemini_model` and
  `gemini_simulator` (read with `ast`, nothing imported), `hackathon/docs/cooling_design.md`,
  `hackathon/docs/reliability.md` and everything in
  `hackathon/data/` (PDF pages, `.md`, `.txt`, `.rst`, the header of each `.csv`). Not our
  agent code or research notes. Today that is 99 files, 779 chunks of about 100 words.
- **Two backends, one interface:**
  - `gemini-chroma`: GEMINI's ChatPopup retrieval (Ollama embeddings, a local Chroma
    collection, MMR re-ranking) without its translation and answer steps.
  - `bm25`: plain Python over the same chunks, with no dependencies. It answers while the
    vectors are being built, and whenever chromadb, the embedding model or Ollama is
    missing. `info()["fallback_reason"]` says why; Ollama is tried again after a minute.
- **Embedding model:** `snowflake-arctic-embed:s` (67 MB, GEMINI's own embedding family), or
  `$EMBED_MODEL_VERSION`. On 8 CPU threads, over 25 test questions:

  | Model | Size | Build (779 chunks) | Query | Right document in top 4 |
  |---|---|---|---|---|
  | BM25 | – | 0.15 s | 0.5 ms | 19/25 |
  | all-minilm | 45 MB | 10 s | 8 ms | 21/25 |
  | **snowflake-arctic-embed:s** | 67 MB | 15 s | 14 ms | 20/25 |
  | nomic-embed-text | 274 MB | 52 s | 22 ms | 22/25 |
  | embeddinggemma | 621 MB | 51 s | 22 ms | 21/25 |

  `qwen3-embedding:0.6b` was slower (95 s) and worse (10 of the first 14).
  Of the three Dutch questions, BM25 finds none and each embedding model two.
- **Cost:** nothing at import or construction. The first search builds the keyword index
  (0.15 s) and starts embedding in a background thread (17 s on a cold cache, 1.3 s to reopen
  a warm one); searches switch to the vectors when they are ready. Warm queries take 19 ms
  (Chroma) or 0.5 ms (BM25). `DocIndex(background=False)` or `refresh(wait=True)` waits for
  the vectors, which tests and evals want.
- **Rebuild:** chunks and vectors are cached in `hackathon/evals/runs/docs_index/` (git-ignored,
  about 5 MB). A search re-checks file signatures at most every 5 s and reads and embeds only
  files that changed, so dropping organiser files into `hackathon/data/` is enough. To rebuild
  everything, delete the folder.
- **Attachments** stay in memory, per conversation, and never go into the shared collection.
  `drop_thread` forgets them; after a restart they must be added again.
- **Documents are data.** A passage with instruction-like text ("ignore previous
  instructions", "you are now", "system prompt", "respond with") has `suspicious=True`; the
  agent warns and never follows it.
- **Install:** the pins in `hackathon/requirements-dev.txt` (`chromadb`, `langid`,
  `langchain-community`, `pypdf`, and `influxdb-client`, which ChatPopup's base class imports),
  then `ollama pull snowflake-arctic-embed:s`.

## Generated models

When a design needs a component Dioscuri has no model for, a local model can write one.
Generation and running the code each need the user's yes; nothing is registered without it.

- **Specs** (`component_specs.py`): `SPECS` holds `adsorption_chiller` (silica gel–water,
  driven by 40–90 °C water such as the heat-exchanger outlet) and `ates` (seasonal aquifer
  storage). Each gives inputs and outputs with units, the physics relations with their
  sources, reference cases and the physics checks.
- **Generate** (`modelgen.py`): `generate(SPECS[name], llm)` makes one JSON-schema call
  (`prompts/modelgen_v1.txt`, reply `{"reason", "code"}`) and tests the code. Every broken
  rule, error (with its line) and failed check goes back to the model, up to three attempts.
  `iter_generate` yields each attempt as it is tested, for the UI's tick-off rows.
- **Sandbox** (`sandbox.py`): a syntax-tree allow-list first (only `math` and `numpy`; no
  files, network, `eval`/`exec`/`open`/`getattr`, underscore names, classes or `global`).
  Then one child process runs every case (`python -I`, JSON in and out, reduced builtins).
  On Linux and macOS it also limits CPU time and memory and blocks new files and processes.
  On Windows only the timeout applies.
- **Register** (`Registry`): `save(result, approved_by="user")` writes `<name>.py` with a
  header (spec, model, date, test table) and a `.json` sidecar to
  `hackathon/evals/runs/generated_models/` (git-ignored; `DIOSCURI_MODELS` moves it).
  `evaluate(name, cases)` runs it in the sandbox; `evaluate_checked` also fills defaults,
  re-runs the per-case checks and flags inputs outside the tested range. Code edited after
  approval is refused.

Live check on 28 Oct: thinking off, temperature 0, up to three attempts. The adsorption
chiller lists its physics step by step; ATES is harder (two wells, a helper function and edge
cases). "ATES over 3 wordings" counts passes over three versions of the ATES wording.

| Model | Adsorption chiller | ATES | ATES over 3 wordings |
|---|---|---|---|
| qwen3:1.7b, CPU | pass, 1 attempt, 17 s | fail, 146 s | 0/3 |
| qwen3.5:4b, GPU / CPU | pass, 1 attempt, 5 s / 1 attempt, 41 s | pass, 2 attempts, 11 s / 1 attempt, 58 s | 3/3 / 2/2 |
| qwen3.5:9b, GPU | pass, 2 attempts, 9 s | fail, 29 s | 2/3 |
| qwen2.5:7b, GPU | pass, 2 attempts, 5 s | fail, 21 s | 0/3 |
| qwen2.5:14b, GPU | pass, 1 attempt, 7 s | pass, 1 attempt, 11 s | 2/3 |

With thinking on, ATES failed on qwen3:1.7b, qwen3.5:4b and qwen3.5:9b. The 4b model spent its
whole 7,000-token budget thinking and never wrote the JSON. The self-correction loop fixed
syntax errors, missing imports and edge cases. Tests:
`pytest -q unit_test/gemini_agent/test_sandbox.py` (no Ollama needed).
