# Agentic AI expert: review of Dioscuri

Role: agent architectures (tool use, planning and reflection, human-in-the-loop, memory, guardrails, traces).
Server http://127.0.0.1:8792 on the GPU (qwen3:1.7b reads each message; qwen3.5:9b does everything else).
Threads `agentic-1` to `agentic-5`: 23 runs on 31 Oct 2026.
Code read: agent.py, policies.py, intake.py, parameters.py, answer.py, claims.py, engine.py, router.py, ADR-0002/0004/0005/0008/0009/0010 and agentic_components.md.

Totals: 71 model calls (3.1 a turn) and 140k prompt tokens (6.1k a turn). Server time was 449 s, or 19.5 s a turn on average; that may include waiting for the shared GPU.

## 1. Verdict

Dioscuri is a well-built pipeline that keeps its numbers honest, with models attached at the edges. It is not yet an agent that plans. In my 23 runs, code made every engineering decision: which plants to try, how to repair them, which one wins and which fixes to offer at a shortfall. The models read the message and write the reply. Reading takes up to five separate classifier calls and is steered by about 60 regexes. Keeping the optimiser in code is the right call for small local models. The deterministic core, the inputs card, the shortfall decision and the traces are better than most agents I review.

The conversation layer is the weak part:
- **No planner.** A two-step request ran under the wrong conditions. The agent then invented the conclusion: "The best pick does not change". It does change.
- **Unchecked comparisons.** The model writes comparisons between designs and nothing checks them. A false CO₂ claim lasted four turns, partly because the claim checker counts the agent's own earlier replies as evidence.

The fix is not more agents. It is one planner call that outputs a short, typed plan over the tools you already have, with code checking the plan. Add comparisons computed by code, and interrupts that remember what the human decided.

## 2. What works

- **Deterministic core.** The search covers 35 layouts, 730 sizings and 1,040 simulated years in about 3 s. Every losing design keeps its reason in numbers ("+0.6 €/MWh of heat and cold (62.4 against 61.8)"). The optimiser lives in code, not in a 9B model, and the verifier is the only source of design numbers. Keep both.
- **Inputs card before the first design.** Each value is marked read, derived, assumed or asked, with the file and section. A typed change shows the card again with the changed rows marked. It caught the model's own over-reading: it showed "no boilers, chillers, heat pumps" when I never ruled out chillers.
- **Shortfall decision.** "No design meets every cap ... worst 14.42 MW on 28 Jan" came with four simulated fixes, each with its coverage and cost, plus "Keep my limits". The picked design is checked again. This is the right place for a human decision.
- **Parameter catalogue.** The model maps words to parameters and code checks the quote, the range and the number. A change without an amount is asked back as a choice. This is a good "model maps, code checks" pattern.
- **Traces and the model builder.** Each run records who decided each step, tool arguments and results, tokens and timing per call, corrections, removed sentences, and the answerer's "understood" line. The model builder flow is a real loop: offer, write (self-correcting, in a sandbox, 14 cases, 9 checks), then human approval.

## 3. Issues (most important first)

### H1 (high): no planner; a compound request runs under the wrong conditions, then gets an invented answer

**What I did** (`agentic-2`): "Design the heating and cooling plant for the district, then check it against a 10 °C colder reservoir and tell me if the pick changes."

**What happened:**
- The reader's `CHANGE` regex turned "10 °C colder" into `reservoir_delta_c = -10` and forced the intent to `what_if`. The 9B parameters reader found no change; the regex won.
- With no design yet, `_continue` passed the colder brief straight to `_design`.
- No inputs card appeared, because the card only shows for the intents `design` and `compare`.
- The one design made was `1D-HP-EC −10 °C`.
- The model's text was removed, including the correct sentence "Therefore, a colder reservoir likely changes the pick." The fallback template reads like a normal design ("I recommend 1 doublet at 2,500 m ... 80.5 €/MWh of heat"). It never mentions the colder reservoir and never answers "does the pick change".

**Second attempt:** "That is not what I asked. Step 1: design for the reservoir as given (87 °C). Step 2: run that design with the reservoir 10 °C colder. Step 3: tell me whether the best pick changes."
- No tool ran. The parameters reader saw −10 as the current value, and ADR-0009 #8 sends a what-if that changes nothing to the answerer.
- The reply: "The best pick **does not change**. The design **1D-HP-EC** ... remains the optimal choice even when the reservoir is 10 °C colder ... The design search confirms that this layout is robust against the temperature drop."
- The claim checker removed none of the 7 sentences.
- The answerer's own reasoning steps show it understood the plan but had no way to act: "The user wants a specific sequence: design at 87°C, then re-run at 77°C, then compare. The context already contains the result of this exact comparison in block [1D-HP-EC what-if]."

**The truth:** the same search picks 2D-HP-AB at 87 °C (`agentic-1`, S1, 61.8 €/MWh) and 1D-HP-EC at 77 °C. The pick changes.

**Why it matters:** "iteratively improve a design ... explain every major decision" is the challenge, and a judge will try exactly this kind of request. A silent change of conditions plus a confident false conclusion is the worst failure an engineering agent can have.

**Do instead:** a turn planner (see H6) that outputs up to four typed steps, for example `design(base) → what_if($1, reservoir_change_k=-10) → search(under $2's conditions) → compare(pick of $1, pick of $3)`. Code checks and runs the plan, the reply is written from the step results, and the comparison is computed by code.

### H2 (high): comparisons are free prose and never checked; the agent's earlier replies count as evidence

**The false claim:** right after the first design (`agentic-1`), the reply said: "This layout balances costs and emissions better than alternatives like adding a third doublet or using only electric chillers." The search it had just run says otherwise. 2D-HP-EC emits 9,275.5 t CO₂ a year and 3D-HP-EC 8,978.5 t, against 9,654.9 t for the pick. The pick was ranked on cost only.

**How it persisted:**
- I asked: "You said it balances cost and emissions better than using only electric chillers. Is that true? Which of the two emits less CO2?" The reply: "Yes, the **2D-HP-AB** design emits less CO₂ than a system relying solely on electric chillers ... the search results do not provide a specific "electric-only" baseline". The context's search block did list "2D-HP-EC ... 9,276 t CO2 a year".
- Two turns later, "can you make it better" got "The lowest CO₂ option is also 2D-HP-AB", and the claim checker kept it.
- I clicked the agent's own suggested option, "Which design gives the lowest CO2?". The same false sentence was removed, and the reply fell back to an unrelated description of 2D-HP-AB. Its source was `src/gemini_model/corrosion/correlation/co2_partial_pressure_model.py`. That took 6 calls, 17,790 prompt tokens and 45 s.
- Only when I named the design did it say "2D-HP-EC is the lower-emission option". The checker then removed the true sentence "Therefore, **2D-HP-EC** actually emits *less* CO₂ than 2D-HP-AB." The reply now opens with "Wait, re-evaluating the numbers:", and the tonnes I asked for never came.

**Mechanisms (all in code):**
- The number check tests numbers, not the relations between them; ADR-0004 says so.
- In fast mode the claim check skips any reply written over a draft (a checked template answer). Whether a turn is fast or reasoning is decided by the 1.7B reader's `think` flag.
- `claims_v2` says "The sources are the blocks below, including what was said earlier in the conversation". So one false reply becomes support for the next.
- A 9B checker shares the 9B writer's blind spots.

**Why it matters:** the "why" sentences are the decision explanations the brief asks for, and they are exactly the ones nobody verifies. Memory turns one slip into a lasting belief.

**Do instead:**
1. Add a `compare(designs, metric)` tool, and a code check on any sentence that says "lower / higher / less / more / cheaper / greener than" and names two designs. Check it against the ledger.
2. Count only tool outputs, documents and user turns as sources, never the agent's own replies.
3. Claim-check every model-written sentence not copied from the draft, whatever the mode.

### H3 (high, cheap to fix): the "planner and reflector" exist in the docs, not in the code

**Code rules make every engineering decision.** In all 23 runs, every `plan`, `improve` and `rank` step says `decided_by: rules`. `engine.search` calls `dioscuri_plant.search`, which builds the layouts, sizes them, runs the repair loop and ranks them in one call. The trace rows "verify", "improve" and "rank" just display that result again (0.0 s each).

**The planner prompts are dead code, but the docs still describe them:**
- `prompts/plan_v1.txt` and `prompts/reflect_v1.txt` are loaded nowhere.
- `Agent._model_decides()` is never called.
- ADR-0008 says the plan code is gone.
- Yet `router.py` still says "Planner and reflector (reasoning mode only): the same larger model chooses the designs to study and the fixes to try". `agent.py`'s docstring says the same.
- `agentic_components.md` lists "Decision points | Plan and reflect (fixes at a shortfall): rules in fast mode, the model in reasoning mode".

**At the shortfall nothing reasons.** For "Design a fossil-free plant for the district, and no heat pumps either.", the trace shows "think: Reason it through" (decided by rules: "No design met every cap, so the choice of fix matters"). Then `engine.relaxations` builds the fixes and code marks the cheapest as recommended:
- The cheapest fix was the assumed deeper aquifer, which ADR-0010 keeps as a last resort because the requirements describe no such aquifer.
- The first option offered to a user who asked for fossil-free was "Allow a boiler".

In practice, "reasoning mode" only adds three writing steps and turns the claim checker on.

**Why it matters:** judges will compare your docs with your traces. Claimed planning that never runs costs more credibility than an honest "code optimises; models read and explain".

**Do instead:** fix the three docs today, and remove or rewire the dead prompts. If there is time, add a bounded reflector at the shortfall:
- The model ranks the code-built, already simulated fixes against the user's own words ("fossil-free") and says why.
- Code checks that it picked one of them.
- The user still decides.

### H4 (high): the human's decision is lost; it is neither in the answerer's context nor in the trace

**What I did** (`agentic-3`): I picked "Allow heat pumps (100% of the heat at 103.8 €/MWh)".

**What happened:**
- The answerer's "understood" line: "You want a fossil-free plant without heat pumps."
- The reply restated the shortfall ("removing both boilers and heat pumps leaves no configuration ...").
- It suggested a fix the model does not have: "Reintroduce a fossil-free top-up like electric boilers".
- Only its last line named the design I had chosen (3D-HP-EC-2I).
- The trace for that run has an empty message, the steps answer, claims and report, and `answered: ["decision"]`. The option I chose appears in no event of that run; I searched the JSONL.

**Cause:** `_resume` sets `self._message = pending["message"]`, which is the original request, and stores only the answer keys.

**Why it matters:** a decision or approval that leaves no record breaks the audit trail you rightly advertise, and the reply contradicts the user's own choice.

**Do instead:**
- Emit a `decision` step with the question, the options, the recommended one, the chosen one and who chose. Do this for the confirm, decision, choice, generate and approval cards.
- Pass "The user picked: …" to the answerer as the message.

### H5 (medium-high): interrupts are fragile

- **A side question drops the open inputs card** (`agentic-5`). "Why do you assume a 60 °C heating return?" was answered well, but afterwards `pending` was null. Then "ok, run it" was:
  - read as intent `explain`;
  - screened by the 9B as a possible request to skip the checks;
  - searched in the documents and answered, with that answer thrown away;
  - and only then followed by the card again.

  That was 3 calls and 18 s to get back to where I was.
- **A clicked option is a plain string.** Clicking re-sends it as a new message through the whole chain of reader, regexes and route model. The agent's own option "Which design gives the lowest CO2?" was routed to "no design" (see H2).
- **The inputs card is skipped** when the first request looks like a what-if (H1).

**Do instead:**
- Give each option a typed action, for example `{"action": "search", "objective": "co2"}`, and run it directly.
- Keep open cards on a small stack and show the card again after answering a side question.
- Show the inputs card whenever the turn will run the chat's first search.

### H6 (medium): five classifiers and about 60 routing regexes decide the route, and they disagree

**The routing load:**
- A turn can call the reader (1.7B), then the screen, parameters, confirm and route models (9B). The answerer can also route on its own (`run: "design"`).
- In 15 of my 23 runs, two or three model calls classified the same message:
  - reader and parameters 11 times;
  - confirm with parameters or the reader 3 times;
  - reader and screen once;
  - the route model came on top twice.
- `_turn` has 21 exits and 9 direct regex tests. The package compiles 114 regexes, and by my count about 60 of them steer routing or what goes into the context.

**The outputs are merged, so errors add up:**
- **Regex beat the model.** The `CHANGE` regex overruled the 9B (H1).
- **Any digit costs a 9B call.** `CHANGE_CUE` matches any digit, so "CO2" triggers a parameters call (2.8 s, 1,605 tokens, no change found).
- **Keys nobody asked for.** `lookup.wanted` adds regex keys to the reader's keys. A `capex` key nobody asked for made the must-keep rule add "The capital cost is 43.2 M€." to a CO₂ answer.
- **Nobody asked "two what?".** For "ok try it with two instead":
  - the parameters model guessed `n_doublets=3`, and code dropped it;
  - the answerer asked for a design run, so its reply was thrown away;
  - the same-search card followed.
- **Negation read backwards.** "Electric chillers are fine, I only meant no gas boilers and no heat pumps." became `{"exclude": ["boiler"], "allow": ["heat_pump", "chiller"]}`, the opposite for heat pumps. My first message had chillers excluded although I never mentioned them. The quote check cannot catch this, because for list parameters `_valid` only checks the option names. The intake `NEGATION` regex would have got it right, but the card-change path does not use it.

**Do instead:** the same fix as H1. Use one planner call with the parameter catalogue in its schema. Keep the regexes only as checks: the quote is in the message, the number is in the quote, and exclusions are cross-checked with `NEGATION`.

### H7 (medium): memory; the duplicate guard looks back only one search, and limits and conditions get lost

**What I did** (`agentic-1`): "Add a seasonal heat storage tank so the summer brine heat can be used in winter, and redo the design."

**What happened:**
- It re-ran S1's brief as S3, with an identical result (6 calls, 33 s). `same_search` only compares with the latest search, which was S2, the what-if.
- The parameters reader had flagged "seasonal heat storage tank" as unsupported. In the design path that note only goes to the inputs card, which was already confirmed, so it was lost.
- The reply promised the impossible: "If you have specific storage parameters (cost per m³, round-trip efficiency), please provide them so I can re-run the simulation".
- The claim checker removed the honest sentence: "I cannot invent values for a seasonal storage tank, as no cost, size, or efficiency data exists in our project files."
- The model builder does have a seasonal-storage spec, but its keyword `seasonal storage` does not match "seasonal heat storage tank".
- In `agentic-2`, the context labelled the colder design "what-if" although it was the only design (H1).

**Do instead:**
- Compare with every earlier search, not only the last.
- Give each ledger entry its conditions (base, or the what-if change) and show them in the context.
- Always state unsupported asks in the reply, or offer the model builder, matched by the planner rather than a keyword.

### H8 (medium): the claim checker removes truths and keeps errors; added must-keep sentences break replies

**Removed, though true or honest:**
- a correct physics sentence on the 50 °C return ("the lower return temperature allows the heat exchanger to extract more thermal energy from the geothermal brine");
- the honest storage limitation (H7);
- "Therefore, a colder reservoir likely changes the pick." (H1);
- "2D-HP-EC actually emits less CO₂" (H2).

**Kept, though false:**
- "The lowest CO₂ option is also 2D-HP-AB";
- "Reintroduce a fossil-free top-up like electric boilers";
- "The best pick does not change".

**Labels are not checked.** The what-if reply says "60 €/MWh for heat (down from 61.8 €/MWh)", but the result card shows 62.32 €/MWh for heat; 61.8 is the cost of heat and cold together.

**Added must-keep sentences break the prose.** The must-keep rule adds back key values the model dropped. The first design reply contains a stray "[2D-HP-AB]" and ends by repeating its own summary paragraph.

**Cost:** two 9B calls (claims and claims_quote), 6–14 s a turn.

**Do instead:**
- Use one call that returns a verdict and a quote per sentence.
- Never use agent replies as sources.
- Check in code the relations between numbers, and what each number is (heat, or heat and cold together).
- Show must-keep values in a fixed key-numbers line written by code, not spliced into the prose.

### H9 (medium): traces show what ran, not why this route

**Gaps:**
- The routing choice is not a step: which of `_turn`'s 21 exits was taken, and which regex or classifier decided it. For H1's second message, the trace shows intake `what_if`, parameters `{}`, then docs and answer. Nothing says "what-if with no change, treated as a question (ADR-0009 #8)", which is the one fact needed to debug it.
- "think: Reason it through" appears where nothing reasons (H3).
- Steps replayed after the fact look like separate actions.
- Decisions are missing (H4).

**Do instead:**
- Add a `route` step to every turn: the branch taken, each classifier's output and the rule that fired.
- Show one honest `search` step with its sub-results.
- Add the decision steps from H4.

### H10 (low-medium): an approved generated model stops at a point check

**What happened** (`agentic-4`, no design in that thread): after approval, the adsorption chiller ran at its spec defaults.
- The reply: "Yes, the adsorption chiller can cover a significant portion of the cooling load ... 0.95 MW". The cooling peak is 10 MW.
- It also said "the system can operate for up to 330 days", which was never simulated.
- It used "chilled water temp 6 °C", while the challenge network supplies 20 °C.
- With a design, `model_conditions` gives one or two operating points; the search never uses an approved component.

**Do instead:** say "a point check, not part of the design" in the reply. Later, register approved components as options in the search.

## 4. Implement differently or remove

### More agentic, still reliable

**1. A turn planner: one 9B JSON call per turn.**
- **What it replaces:** the reader, parameters, route, screen and confirm calls, and the answerer's `run` flag.
- **What it outputs:** up to 4 typed steps from a fixed tool list (design, what_if, search, compare, sensitivity, answer, clarify), parameter changes with quotes, and clarify options with typed actions.
- **What code checks:** allowed tools and order, the inputs card before the first search, quotes, ranges and the polarity of exclusions. If the plan fails these checks, today's rules take over.
- **Gains:**
  - compound requests work (H1);
  - one reading of the message instead of up to five (H6);
  - the plan itself explains the route in the trace (H9);
  - on the CPU it also saves time, since today the 4B already runs parameters, route, confirm and screen.
- **Risks and mitigations:**
  - *A 9B call where the 1.7B was enough.* Keep today's pattern-matched fast path for greetings and "who are you".
  - *A wrong plan.* Code checks, a plan row in the trace, and a confirm card for plans of more than two steps or plans that change conditions.

**2. Observe, then maybe act, after a search.**
- Code computes observations, for example: the top 3 are within 1 €/MWh; the pick is not the lowest-CO₂ design; which assumption the cost is most sensitive to.
- The 9B may pick one follow-up tool (search by CO₂, a sensitivity run on the heating return) or none.
- **Gains:** this is a real act-observe-improve loop, and the model still never writes a number.
- **Risk:** 2–3 s more per turn. Allow at most one extra tool call per turn, and reuse the tool cache.

**3. A reflector at the shortfall.**
- The model ranks the fixes code has already built and simulated against the user's own words, and says why.
- Code checks that it picked one of them; the user decides.
- **Gains:** the recommendation follows the user's goal (fossil-free, or no assumed aquifer), not just cost.
- **Risk:** it may recommend a fix that is not the cheapest. Show both: "cheapest" (code) and "recommended because …" (model).

**4. Comparisons computed by code.**
- A compare tool, plus the code check on sentences that compare two designs.
- **Gains:** H2 cannot recur.
- **Risk:** none to reliability.

### Remove or merge

- **The 1.7B reader on the GPU path:** merge it into the planner. Keep it for the CPU fast path.
- **Regexes used as routers:** `WHAT_IF_WORDS`, `COMPARE_WORDS` (which contains "against"), `BEST_DESIGN`, `EXPLAIN_START`, `CHANGE` as an intent setter, `CHANGE_CUE`, `WHY_START`, `ABOUT_RESULT`, `ABOUT_DESIGN`, `SHOW_WORDS`/`RUNNER_UP`, and the context selectors `DESIGN_TALK`/`COST_TALK`/`GEMINI_TALK`. Keep the regexes that check rather than route: number extraction, `NEGATION`, `PAIR`.
- **`lookup.wanted`'s merge** of model keys and regex keys: let the planner choose the keys and let code check them.
- **The separate confirm call:** fold run / change / other into the planner's output.
- **claims plus claims_quote:** make them one call.
- **The answerer as router (`run: "design"`):** its reply is written and thrown away; I saw this twice.
- **The document search on every talk turn:** let the planner decide. It brought a corrosion-model file as the source for a CO₂ question, and four passages for the "Step 1/2/3" message.
- **"Reasoning mode" as a concept:** on the GPU the same 9B answers in both modes. The mode only switches the claim check on or off, and the 1.7B decides it. Let the reply's content decide what gets checked, not the mode.
- **Dead code and stale docs:**
  - `plan_v1`/`reflect_v1` (rewire or delete) and `_model_decides`;
  - the planner/reflector text in router.py, agent.py and agentic_components.md;
  - ADR-0008's "the steps are the agents": they are steps of one pipeline.
- **Must-keep sentences added into the prose:** replace them with a key-numbers line.
- **The replayed verify / improve / rank rows:** show one search step with sub-results.

### Keep

- **No free-text hand-offs between roles** (ADR-0005). This is right for small models.
- **The hand-built state machine.** Do not migrate to LangGraph before the deadline. LangGraph's interrupt()/resume and checkpointer would give you typed resume values and persistent interrupts for free. Copy those semantics now (H4, H5) and consider migrating after.

### Evals to add

Your current checks (behaviour label, numbers grounded, contains) would pass most of the failures above. Add:
- a compound request (design, then what-if, then "does the pick change");
- "which design emits less CO₂?", checked against the ledger;
- a decision follow-up whose reply names the chosen option;
- a side question asked while the inputs card is open; the card must stay;
- every code-made option clicked; each must run its action;
- an unsupported ask that must be stated in the reply.

## 5. Top 3 priorities before the deadline

1. **A planner for multi-step turns, and comparisons computed by code (H1, H2, H6).** A minimal version is enough:
   - the 9B writes a JSON plan of at most 3 steps over design / what_if / search / compare / answer;
   - code checks it, with today's routing as the fallback.

   Add the compare tool and the code check on comparing sentences the same day.
2. **Truth guards (H2, H8).**
   - Remove agent replies from the claim sources.
   - Check every model-written sentence not copied from the draft, whatever the mode.
   - Replace the added must-keep sentences with a key-numbers line.
   - Add the evals above so these fixes stay fixed.
3. **Human-in-the-loop and trace integrity (H3, H4, H5, H9).**
   - Record every decision and the route taken as trace steps.
   - Pass the user's choice to the answerer.
   - Make options typed actions.
   - Keep the card open across side questions, and show the inputs card before any first search.
   - Make the docs say what the code does: remove or rewire the planner/reflector claims.
