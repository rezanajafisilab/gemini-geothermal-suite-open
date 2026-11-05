# ML and LLM expert review of Dioscuri (models, prompts, checks, evals)

Reviewer: ML/LLM panel member. Server 8792, threads `ml-1`, `ml-de`, `ml-typo`, `ml-typo2`,
`ml-long`, `ml-p1`..`ml-p4`, `ml-cpu` (about 20 turns, one of them on the CPU). I also ran
offline probes of the check functions on the live `ml-1` session (read only), and pulled
statistics from every trace on the three panel servers: 194 turns from about 10 reviewers.
Timings on the GPU were inflated by other panel members sharing Ollama, so for latency I rely
on token counts, on Ollama's own prompt and output durations, and on the eval runs.

## 1. Verdict

The base is sound: the simulator computes the numbers, the model reads and writes, code checks
the result, and the traces are the best I have seen in a hackathon build. But the model layer
has grown into a chain of 3–7 calls (mean 3.25 per turn, 42 % of turns need 4 or more). Each
call has a code check bolted on, and those checks fail in both directions:

- They throw away correct readings by the model: unit conversions and German number words.
  In one case this made the agent present an unchanged result as the scenario the user asked
  for.
- They let through the errors the models actually make. Every wrong number I saw in a reply
  was a real number from the context, used in the wrong role. The number check is blind to that
  by design.

The 1.7B reader misrouted roughly 8 of my 17 messages, and its guesses are then enforced as hard
constraints on the 9B's answer. The evals cannot see any of this. They use one wording per
behaviour, tuned on the team's own conversation, and their most used check (`numbers_grounded`,
failed 1 of 335) re-runs the agent's own filter, so it always passes. On the CPU, a simple
source question took 121 s; I estimate about 50 s without load and contention, and 85–125 s for
claim-checked turns, and that is on the team's workstation, not a judge's laptop.

## 2. What works (keep it)

- **Grammar-constrained JSON everywhere, with temperature 0 and thinking off.** No call failed
  to parse in 194 turns, and capping the reasoning at 3 steps instead of native thinking was the
  right decision (ADR-0004 table).
- **The inputs card before the first design.** It is the best hallucination control in the
  system: it showed me every silent drop below (two doublets lost, wrong objective, "no boilers").
  Keep it, and make it show what was dropped.
- **Refusing to invent missing metrics.** NPV/IRR/payback (`ml-1`) and the cost before any design
  exists (`ml-typo2`) were declined honestly. The claim checker caught real errors: "the context
  does not provide a discount rate" (it does: 5.2 %), "saves 11.0 M€" (a number taken from the
  two-injector variant), "it produces less heat and cold overall", "a single doublet cannot cover
  all demand".
- **The 9B handles Dutch and German well.** It read "50 graden" and "55 °C Rücklauf" correctly
  and answered in the user's language.
- **Traces and usage records.** Every call has its tokens, load, prompt and output time. All the
  statistics in this report came from them.

## 3. Issues (most important first)

### 3.1 HIGH: correct model readings are silently thrown away, and the unchanged result is presented as the one asked for

**What I did, and what happened:**

- `ml-1`, after a design: "What if electricity cost 12 ct/kWh instead?"
  - The 9B read `electricity_eur_per_mwh=120`, which is correct. The parameters step dropped it:
    `"electricity_eur_per_mwh=120: its number is not in the quote"`.
  - The answerer then offered a clarification whose second option said "higher electricity
    prices". 120 €/MWh is lower than the current 185.7 €/MWh.
  - I clicked "Run a new design ... with electricity at 12 ct/kWh". The value was dropped again,
    the route call said run, and search S3 ran with the old prices.
  - The reply asked "Could you clarify ... Please confirm so I can proceed with the simulation",
    and code then appended the draft sentence "...for 64.2 €/MWh of heat and 50.1 €/MWh of cold".
    That is the 185.7 €/MWh result, shown under a 12 ct/kWh request.
- `ml-de`: "...mit genau zwei Dubletten und ohne Wärmepumpen" was dropped as `"n_doublets=2: its
  number is not in the quote"`. I asked again ("wirklich nur zwei Dubletten") and it was dropped
  again. The card still says "1 to 3 doublets".
- **Offline probe of `parameters.check`.** I fed it correct model readings for 12 ct/kWh, 122 °F,
  83 l/s, "zwei Dubletten", "doppelt so teuer", "um die Hälfte", 4.5 ct/kWh and 0.13 TWh. All
  were dropped (the only case kept was a Dutch one that matched the current value). The cause:
  `WORDS` holds English and Dutch number words only, `_backed` knows only ×1, ×1000 and /100, and
  products are not accepted.
- **Across the panel's traces:** 11 drops for "not in the quote".
  - About 7 were correct readings: ct/kWh twice, "zwei" twice, `140/85 F` → 60/30 °C twice, and
    "three 4 MW boilers" → 12 MW.
  - 3 were real catches: "two instead" read as 3, "no gas at all" read as gas price 0, and one
    reading made from a question.
  - So roughly 70 % of the drops were wrong.
- **Typo request** (`ml-typo`): "...3 dublets, no gas boilr pls". The reader said intent `other`,
  and the answerer recovered the run through `run: "design"`. But that path never calls
  `parameters.read`, so the three doublets were lost.

**Why it matters:** this is the worst kind of hallucination. It is not invented text: it is a
correct-looking result for a different question, and both the number check and the claim check
pass it.

**What to do instead:**

1. Let the model return what it read (`value_as_written`, `unit_as_written`) and let code convert
   with a unit table per catalogue unit: ct/kWh, €/kWh, °F, K/°C, l/s, m³/s, kW, TWh, km, ft, psi.
2. Add number words for German and French ("zwei", "drei", "doppelt", "Hälfte", "deux"...).
   Accept products of numbers in the quote, and 0 for "no/without" on size keys.
3. When a reading still fails, ask, don't drop: "Did you mean 120 €/MWh (12 ct/kWh)?" as a
   one-click card. The vague-amount card already does this.
4. Run `parameters.read` on the recovered-design path too.
5. Never append "added back" draft sentences when the reading of the request failed.

### 3.2 HIGH: the number check accepts numbers used in the wrong role

**Wrong numbers that reached the user in my session.** Each passed the number check, and none
was sent to (or removed by) the claim checker:

| Where | Reply | Truth |
|---|---|---|
| Design report | "2 doublets (330 days/year each)"; table "Doublets \| 2 wells @ 2,500 m" | doublet 2 runs 226 days; 4 wells |
| "Is this a good design?" | "It also saves **9,655 t CO₂** per year." | 9,655 t is its emissions; the saving is 24,365 − 9,655 = 14,710 t (60.4 %) |
| Same reply, table | "\| 1D-HP-AB \| 62.8 \| 12,967 \|" | 12,967 t belongs to 1D-HP-EC; 1D-HP-AB emits 13,270 t |
| "make it cheaper" | "The next best layout ... is 1D-HP-AB ... 62.8 €/MWh" | it ranks 8th; next are 2D-HP-AB-ST 61.91 and 2D-HP-EC 62.36 |
| Days/wells question | "the doublets operate for a total of 3,007 h a year" | 3,007 h is full-load hours |

**Offline probe on the live context** (7 blocks, 15,990 characters, 183 distinct sourced numbers):

- 7 of my 8 wrong test statements pass `unsourced()`, including "COP is 3.6" (3.6 is a
  "constant"), "the boiler is 10 MW" (10 is a constant) and "each doublet runs 330 days".
- A random wrong value followed by "MW" passes alone for 41 of the integers 1–200 and for 140
  of the one-decimal values 0.1–99.9. In a sentence that also states three other numbers, 58 of
  200 integers pass through the derived-number rule (±0.5 tolerance).
- `CONSTANTS` = {10, 24, 60, 100, 1000, 3.6, ...} pass in any role, so "covers 100 %" can never
  be caught.
- Table rows are never sent to the claim checker (`claims.candidates` skips them, "the number
  check covers them"), yet tables are exactly where rows get mixed up.

**Why it matters:** the check catches invented numbers (it removed or retried in 28 of 889
eval turns: 63.4, 0.25 ...). But the error these models actually make is a real number used in
the wrong role, and for that the check does nothing.

**What to do instead:**

1. Key the facts by entity and quantity: (design code or project, quantity, unit). A number in a
   sentence or table row that names a design code must belong to that design or to the project.
2. Allow constants only inside a worked formula (the sentence has an arithmetic sign).
3. Render comparison tables and per-doublet facts from data in code, and let the model write
   only the prose around them. ADR-0002 originally planned placeholders for exactly this.

Expected gain: of the 5 wrong numbers in the table above, the entity and quantity key would
flag the 330 days (each doublet's run days stored with its doublet) and the 12,967 t row (a
design row may only use that design's numbers). Code-rendered tables and per-doublet facts would
remove the "2 wells" and "next best" errors at the source. The 9,655 t and 3,007 h role swaps
also need the quantity label to be checked (emissions against saving, full-load hours against
operating hours).

### 3.3 HIGH: too many model calls; the CPU experience is minutes per turn

**Panel-wide traces (194 turns):**

- Calls per turn: 1 call 15 turns, 2 calls 62, 3 calls 36, 4 calls 39, 5 calls 27, 6 calls 12,
  7 calls 3. The mean is 3.25. ADR-0002 promised 1–2, and judging counts prompts.
- **`parameters` (9B):** 127 calls, median 1,609 prompt tokens, median 23 output tokens. 82 of
  them (65 %) returned nothing to change.
- **`claims_quote`:** ran in 54 of 75 claim-checked turns, and rescued 16 sentences in total
  (0.3 per call).
- **`screen`:** 10 calls, 8 of them false alarms from the 1.7B's bypass flag ("why not two
  injectors per doublet?" triggered it in the eval too).
- **Answer retries:** 34 of 149 turns with an answer call.

**Prompt cache.** Calls processed at more than 20k tokens/s on the A6000 must have reused a
cached prompt prefix:

| Call | Cache hits |
|---|---|
| intake (qwen3:1.7b) | 154/174 (static prefix) |
| parameters (qwen3.5:9b) | 0/130 |
| claims | 0/79 |
| claims_quote | 0/58 |
| answer | 32/195 (the retries, which extend the previous prompt exactly) |

So every qwen3.5 call pays for its whole prompt. One model slot is shared by interleaved
prompts, and qwen3.5 may only reuse an exact continuation of the previous prompt; this needs a
quick test.

**Measured CPU turn** (`ml-cpu`, "Where does the 87 °C come from, and is it in the PDF?"):

- 121 s wall in total.
- Intake: 27.9 s, of which 22.1 s was loading the 1.7B.
- Answer (qwen3.5:4b): prompt 2,173 tokens in 14.2 s (153 tok/s), output 286 tokens in 22.4 s
  (12.8 tok/s), and about 44 s waiting behind other servers' requests.
- Claims: 1,562 tokens, 12.5 s.

**Older CPU runs.** The CPU eval of 30 Oct took 96–124 s for claim-checked turns (S38, S39,
S24), and that was before the 4B wrote every CPU reply and before the parameters call existed.
The current CPU pipeline has never been run on the full suite.

**Estimate without contention, on this workstation:**

| Turn | Time |
|---|---|
| Design request, up to the card | about 13 s |
| Design reply | about 40 s |
| Question with claims and quote | about 85 s |
| A retry | +40 s more |

A judge's 8-core laptop will be slower still.

**What to do instead:** see section 4.

### 3.4 HIGH: routing fails on paraphrases and languages; the regex layer is English and Dutch only

I sent the same intent, a lowest-CO₂ design, in four wordings. Only 1 of 4 was right:

- **p1** "I care most about emissions. What is the greenest system you could build here?"
  - The reader said `about`, and `run` is disabled for `about` (agent.py line 1292).
  - The 9B replied "I will now run the design search with: Electric chillers ... Heat pump ...
    (no gas boiler). I will present the winner and its variants in the next step." Nothing ran.
  - The claim checker counts promises as `no_claim`.
- **p2** "Optimise the district plant for carbon rather than for cost." Correct: objective
  `co2`.
- **p3** "Minimiere bitte die CO2-Emissionen bei der Auslegung für dieses Quartier."
  - The reader said `relevant: false`. The reply came in English and planned "maximizing on-site
    CHP generation" (CHP is not in the model, as the self card says) on a "daily heat demand of
    111.7 GWh" (that figure is annual).
  - The claim check left the CHP sentence in.
- **p4** "Ontwerp het systeem met zo weinig mogelijk CO2-uitstoot." The card showed "lowest cost
  of heat and cold": the objective was lost silently.

**Other reader misses:**

- NPV question: `relevant: false`, intent `compare`.
- "Is this a good design?": intent `design`.
- "Warum hat das Design zwei Dubletten...": intent `what_if`.
- The long message: intent `compare`.

The bigger models and the regexes recovered several of these, but each recovery costs a route,
screen or parameters call.

**Long message** (303 words, `ml-long`):

- The `FOSSIL_FREE` regex set "no boilers", but the message explicitly accepts that "the gas that
  comes up with the brine is burned on site".
- The one-sentence question about subsidies was filed under "Not modelled" and never answered.

**The cause:** intent is decided by about 25 English and Dutch regexes on top of the 1.7B
(`WHY_START`, `CHANGE_CUE`, `CO2_FIRST`, `BEST_DESIGN`, `ABOUT_RESULT`, `NEGATION`, `DOUBLETS`,
`DUTCH_WORDS`, `RELATIVE`, ...), with no German. This is the "hard-coded phrasings" the team
said it wanted to avoid. Eval S26 passes only because its wording matches `BEST_DESIGN` and
`CO2_FIRST`.

**What to do instead:**

1. Have one structured "understand" call on the reasoning model return intent, `run_design`,
   `skip_checks`, the confirm decision, the changes and the language (see section 4).
2. Turn the regexes into validators, not overrides.
3. Always let the answerer run a design (`run`), including for `about`.
4. Strip or act on "I will run ..." promises in code, and count promises about Dioscuri's
   actions as claims.

### 3.5 MEDIUM: the reader's guesses become hard "must keep" constraints on the 9B

- **"When does thermal breakthrough happen at the producers, and what COP does the heat pump
  reach in January?"**
  - The 1.7B's `asks_for` added `reservoir_depth`, so "2,500 m" became a value the answer must
    keep.
  - The 9B's answer left it out and was replaced by the template: "The heat pump COP is 4.6 ...
    The reservoir depth is 2,500 m". The January part and thermal breakthrough (not modelled)
    went unanswered.
- **"How many days a year does each doublet run, and how many wells are drilled in total?"**
  - The must-keep retry produced "the doublets operate for a total of 3,007 h a year" (wrong
    meaning) and dropped the well count.
  - The `understood` row then read "You want the JSON response with specific draft values
    retained.". The retry leak noted in the code comment of 30 Oct still happens.
- **Fix:** use must-keep values only for the design report (coverage and cost of heat). For
  look-ups, pass the values as context, not as constraints. If something must be restored,
  retry with a plain instruction rather than appending English template sentences.

### 3.6 MEDIUM: the claim checker is costly and one-sided

- **Panel traces:** 452 sentences checked, 124 flagged (27 %), 108 removed, and 47 of 75 checked
  turns lost at least one sentence.
- **It removed good content:**
  - Eval S24 failed because the removed sentences carried the €/MWh. Its answer no longer says
    whether the design is good.
  - In my "is this a good design" turn it removed the true 61.8 vs 62.8 €/MWh comparison
    sentence (which also contained a wrong capex).
- **It kept false content:** "saves 9,655 t CO₂" stayed in that same turn.
- **The design is one-sided:** "supported" verdicts are never verified, table rows and
  promises are never checked, and the second look (`claims_quote`) exists only to un-remove.
- **The benchmark behind the choice is too small** (ADR-0007): 16 synthetic sentences. 8 of 8
  correct has a 95 % lower bound near 63 %.
- **What to do instead:**
  1. Use one call that writes evidence first: for each sentence, `{quote, verdict}`.
  2. Have code verify the quote for every factual sentence that is kept, not only the removed
     ones.
  3. Send it as a continuation of the answer's own messages, so the context is already cached.
  4. Check table rows with the entity-keyed facts of 3.2.
  5. Label about 100 real sentences from the traces (about 2 hours of work) to measure the
     precision and recall of removals for the 9B and the 4B.

### 3.7 MEDIUM: multilingual output is patched with English, and numbers are not locale-aware

- The Dutch what-if reply ended with the code-appended English "With heating return temperature
  50 °C, 2D-HP-AB with its present sizes covers 100% ...".
- The inputs card and other templates are English for German and Dutch users. `language_of`
  detects only Dutch and English.
- `numbers_in("9.655 t")` returns 9.655 and `numbers_in("1.200 Wohnungen")` returns 1.2. So
  correctly written German thousands would be removed as unsourced.
- In the other direction, the German reply wrote "9,655 t/a", which a German reader reads as
  9.655, and the check accepts it as 9,655.
- **Fix:** make `numbers_in` aware of the reply's language; take the language from the model's
  structured output; translate the dozen templates or let the answerer rewrite them; never
  append template sentences to a reply in another language.

### 3.8 LOW: output-handling bugs

- **LaTeX corrupted on the CPU.** The 4B writes `\text` and `\times` with single backslashes
  inside JSON, so they arrive as TAB + "ext" and TAB + "imes" (`ml-cpu`):
  `$T = T_{surf} + ⇥ext{gradient} ⇥imes ⇥ext{depth}$`. `\frac`, `\beta`, `\rho`, `\nu` and
  `\theta` break the same way. The 9B escaped correctly in the evals. S48 only checks for a
  "$". **Fix:** after parsing, map `\t \b \f \r \n` back to backslash sequences inside `$...$`.
- **Raw citations in the chat.** `CITE_ID` needs ids that start with a letter, so `[2D-HP-AB]`
  and `[2D-HP-AB what-if]` appear as they are (seen twice live, reproduced offline).
- **Follow-up suggestions are not checked:**
  - "What would happen if electricity prices rose to 15 ct/kWh?": the current price is
    18.57 ct/kWh, and clicking it triggers issue 3.1.
  - "What discount rate should we use?": 5.2 % is given.
  - "Doublets | 2 wells".

### 3.9 HIGH for the deadline: the evals measure the pipeline's own filters, not correctness

- **`numbers_grounded`:** evaluated 335 times, failed once, because the agent strips ungrounded
  sentences before the check runs. `verifier_pass` (122/0) tests deterministic code.
- **One prompt per behaviour,** drawn from the team's own conversations and patched until it
  passes. There are no paraphrases, no German, and no typos. `answer_language` is in the YAML,
  but `judge()` ignores it.
- **`llm_calls` counts only the last run** of multi-run scenarios (the confirm turn is missing).
- **One sample per scenario, with no confidence intervals.** 46/50 against 48/50 is noise.
- **The CPU suite is stale.** Its last full run was on 30 Oct 15:50, on the old pipeline.
- **What to add:**
  1. A held-out routing and slot set of about 150 messages: 15 intents × 6–10 wordings in
     English, Dutch and German, with typos, long, indirect, odd-unit and false-premise variants.
     Run only intake and parameters against labelled intent and changes; it takes minutes on the
     GPU. Never tune the prompts on it.
  2. A fact-correctness check: extract (design, quantity, value) triples from every reply and
     compare them with the ledger.
  3. CPU latency gates (p50/p90 per turn type) on the judge-proxy laptop.

## 4. Implement differently or remove

| Change | Expected gain |
|---|---|
| Replace intake (1.7B) + parameters + route + screen + confirm with **one "understand" call** on the reasoning model. Schema: relevant, intent, `run_design`, `skip_checks`, confirm decision (when a card is open), changes with value and unit as written, doublets, unsupported, asks_for, language. Static instructions and catalogue first, message last. Keep the 1.7B, if at all, only as a cheap gate for greetings and off-topic messages. | −1 to −2 calls on design, what-if and card turns; better reading (the 1.7B missed about 8 of 17 of my messages); fewer regex patches. |
| **Merge claims + claims_quote** into one evidence-first call, sent as a continuation of the answer's messages. | −1 call in 72 % of checked turns; about 2,200 fewer prompt tokens (about 11–16 s on the CPU), and the claims prompt itself mostly cached (about 13 s on the CPU). Kept sentences become verifiable too. |
| **Skip parameters** when no change cue is present (65 % return nothing), or fold it into "understand". | About 10 s on the CPU per such turn. |
| **Call screen only** when the bypass words match. The model flag was wrong 8 times out of 10. | −1 call on those turns. |
| **On the CPU**, drop `understood` and `follow_ups` (and `steps`) from the answer schema; use code suggestions. | About 100–150 of the median 326 output tokens, so 7–10 s per answer at 13 tok/s. |
| **Design reports on the CPU:** show the checked template with a 1–2 sentence model lead instead of a full rewrite. | About 25 s per design turn. |
| **Fixed answer system prompt** (not filtered by tags), with blocks in a stable order, so prefixes repeat across turns. Benchmark whether qwen3.5 can reuse a partial prefix. If not, compare `qwen3:4b-instruct-2507` (standard attention, cache works as for the reader) as the CPU reasoning model, and try `OLLAMA_NUM_PARALLEL=2–3` so call types keep their own cache. | Prompt time on cached turns falls by 50–80 %. |
| **Remove must-keep values for look-ups**, and remove "added back" English appends. | Ends the template take-overs and distorted answers of 3.5 and 3.7. |
| **Stop regexes overriding the model** (`FOSSIL_FREE` exclusion, `CO2_FIRST`, `BEST_DESIGN`, intent rewrites); keep them only as validators that trigger a confirmation. | Behaviour stops depending on wording; fits the team's "no hard-coded phrasings" rule. |
| **Render comparison tables and per-doublet facts in code**; the model writes only the prose. | Removes row mix-ups (3.2). |

Taken together, I estimate a CPU question turn falls from about 85 s to about 40 s, and the GPU
average from 3.25 to about 2 calls per turn.

## 5. Top 3 priorities before the deadline

1. **Stop silent wrong-scenario answers (3.1, 3.5).**
   - Unit- and number-word-aware backing; a confirm card instead of a drop; parameters on the
     recovered-design path; no appended draft sentences when the request was not applied.
   - Small code changes, and they remove the worst failure mode I found (the 12 ct/kWh result
     shown with the 185.7 €/MWh numbers).
2. **Cut the call chain (3.3).**
   - Merge claims + quote as a continuation of the answer, skip empty parameters reads, call
     screen only on bypass words, and trim the CPU answer schema.
   - Then run the full suite on the CPU on Ali's laptop and report p50/p90 per turn type.
   - Target: at most 2.5 calls per turn and under 45 s for a CPU question.
3. **Measure what matters (3.2, 3.4, 3.9).**
   - An entity-keyed number check plus code-rendered tables.
   - A held-out set of about 150 paraphrased, Dutch, German, typo and odd-unit messages for
     intake and parameters.
   - A fact-correctness check against the ledger.
   - Report pass rates with intervals. Until then, 46/50 says little about how the held-out
     queries the judges use will go.
