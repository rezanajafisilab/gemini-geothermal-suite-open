# Judge's review: Dioscuri (SPE GeoHackathon 2026, GEMINI agentic design)

Role: hackathon judge (TNO / organiser view). Server 127.0.0.1:8791, threads `judge-1`, `judge-2`,
`judge-3`, 31 Oct 2026. 12 chat turns, 2 GEMINI loop runs, 4 design edits, 12 sensitivity runs,
traces and the Evidence data. Code read: ADR-0008, ADR-0010, `tools/gemini.py`,
`dioscuri_plant/doublet.py`, `search.py` (`improve`), `workbench.py` (sensitivity), `agent.py`
(when claims are checked), `answer.py`, the eval scenarios and runs.

## 1. Verdict

Dioscuri is a serious engineering entry. It reads the organisers' files into a sourced inputs
card, searches every layout the brief allows (35 layouts, 730 sizings, 1,040 simulated years in
about 3 s), checks every hard cap day by day, prices from cited sources, and keeps a reason in
numbers for every losing candidate. Its GEMINI bug hunt (11 patches with a released-against-fixed
table) is a real contribution to GEMINI. But in the brief's sense the "agent" is deterministic
code: the model reads the request and writes the reply, while rules plan, size, repair and rank.
In the design loop GEMINI computes only the doublet pressures (ESP head and injection pressure).
The full GEMINI flowsheet is a view, and nothing checks it when it disagrees with the design.
Live, the weak spot is explanation. Two of my "why / which" questions and my report request got
a canned paragraph, and one answer invented the engineering behind the runner-up.

**Scores**

| Criterion | Score | Why |
|---|---|---|
| Use of GEMINI | 6/10 | GEMINI's well solve with the real brine drives the pump power, and 11 patches have an impact table. But the full GEMINI loop runs only after the design is chosen, and its disagreements are ignored (negative pressure, starved ESP). |
| Agentic workflow | 5/10 | Good: the inputs card, the options card when no design fits, what-ifs that run twice. But planning, repair and ranking are all `decided_by: rules`, and the repair loop grows units blindly (a 63.9 MW heat pump). |
| Engineering correctness | 6/10 | Energy balances close, my hand check of ESP and injection pressure agrees within 0.1 bar, COPs are below Carnot, and the caps are checked per day. Missing: ESP intake pressure, surface pressure losses, an injection pressure limit. The depth sensitivity does nothing. |
| Explanation and transparency | 5/10 | Excellent: the inputs card, the per-loser reasons, the trace with tokens, the Evidence tab. Unreliable in chat: fallbacks to a template, an invented mechanism, true sentences deleted. |
| Robustness | 5/10 | Out-of-range edits are rejected cleanly. But the 800-token cap causes fallbacks, a follow-up overwrote the recommended design, one question was misrouted, two inputs gave HTTP 500, and turns take 15-47 s of compute (up to 100 s queued). |
| Usability | 6/10 | Cards, suggestions and tabs are well designed. But the same canned paragraph keeps coming back, and simple questions re-run the whole search. |
| Innovation | 7/10 | Local open-weight models only, upstreamable GEMINI patches, parameter mapping checked against the user's own quote, a claim checker, doublets that differ (open interval, two injectors, trains). |

Overall about 5.7/10 today. 7.5 or more is within reach with the five changes in section 7.

## 2. What works

- **Inputs card before the first design** (judge-1, 5.8 s). Every row is marked data, fixed,
  derived, assumed or asked, with its file and section. For example: "87 °C = 12 °C + 30 °C/km ×
  2.5 km | from the gradient in ... section 3.1", and "at most 330 days a year per doublet ... read
  as a cap (asked of the organisers)". This is how assumptions should be shown.
- **The search and its record.** `attempts` lists 35 candidates, each with a reason in numbers,
  for example "2D-HP-AB-2I ... +11.0 M€ of capital for the extra injector(s), -1.05 GWh a year of
  pumping ... +3.9 €/MWh". The pick's energy closes:
  - heat: exchanger 57.88 + heat pump 23.24 + boiler 30.54 = 111.66 GWh;
  - heat pump COP 23.24 / 5.04 = 4.61, and the boiler converts 30.54 / 32.15 = 95 %;
  - tower: 32.27 GWh = absorption 4.73 × (1 + 1/0.75) + chillers 19.02 + 2.22.

  By hand I get an ESP head of 32.9 bar and an injection pressure of 22.7 bar at 300 m³/h
  (PI 14.5 m³/h/bar, 4.6 bar friction). The tool reports 32.8 and 22.6.
- **No feasible design is reported honestly.** "The municipality wants zero fossil fuel: ...
  single doublet and no gas boiler at all" got "covers 80.5% of the annual heat demand (21.8 GWh
  short) ... cannot supply the network's required 100 °C on 172 days". An options card followed,
  with prices: allow a boiler (68.3 €/MWh), up to 3 doublets (84.8), lift all limits (64.2), or
  keep the limits. This is exactly the brief's "detect violations".
- **What-ifs run twice.** "Suppose the district renovates and brings its heating return down to
  50 °C" kept the plant and got 60.0 €/MWh, with the CO₂ saving going from 60.4 to 68.8 % and
  reinjection at 45.8 °C, exactly at the 40.0 K cap (checked per day). Searching again picks
  1D-HP-AB at 56.5 €/MWh. Correct and well worded.
- **The GEMINI bug hunt in the Evidence tab.** 11 patches (injector friction sign, a 10 mm default
  roughness, the heat pump root, brine properties, ...) and a released-against-fixed table (ESP
  head at 300 m³/h: 41.7 bar released, 32.8 bar fixed). The two patches I read (02, 03) are real
  fixes. Give them to TNO as issues or a pull request.

## 3. Issues

### 3.1 HIGH: GEMINI's own loop run contradicts the design, and nothing checks it

- **Did:** `panel.py gemini judge-1 "2D-HP-AB"` on the pick. Then the same on
  `2D-HP-AB · reservoir permeability 50 mD`, made by "What happens to this design if the
  permeability turns out to be 50 mD instead of 200 mD, like a P90 case?".
- **Happened, on the pick:**
  - `filter_a` "pressure_out": **-1.62 bar** and `filter_b` "pressure_out": **-2.24 bar**.
    GEMINI's example filter (36 bar per m³/s) drops 6 bar at 600 m³/h, starting from a 5 bar
    wellhead.
  - GEMINI's injection pump draws 295.7 kW per well against 221 kW in the plant model (+34 %).
  - GEMINI's ESP draws 419 kW against 391 kW (+7 %).
  - The brine reaches the exchanger at 84.1 °C against the plant model's 86.1 °C (the separator
    and the filter each lose 1 K), so the exchanger carries 14.03 MW against 14.46 MW.
- **Happened, at 50 mD:**
  - GEMINI's producer gives "flow_rate": **222.06 m³/h** with "esp_intake_pressure": **0.0**:
    the pump at its 650 m setting is starved.
  - The design still runs at up to 300 m³/h with a 94.8 bar ESP head. The reply says it "still
    covers 100%", and all 12 checks pass.
  - By hand: the flowing bottom-hole pressure is 250 - 300/3.63 = 167 bar. Take away the
    187 bar of brine column up to 650 m and the pump intake would be about -20 bar.
- **Why it matters:** the brief asks for engineering checks run with GEMINI. Here GEMINI says
  "negative pressure" and "starved pump" while the agent says "passes all 12 checks". The comment
  in `tools/gemini.py` says the booster pump "is not needed (the producers' 5 bar wellhead
  pressure carries the brine through the plant to the injection pumps)", and GEMINI's own result
  says otherwise. A TNO judge will open the GEMINI tab and see this.
- **Instead:**
  - After ranking, run the pick and the top 3 through GEMINI's flowsheet.
  - Add checks:
    - GEMINI's flow within 2 % of the design flow;
    - no pressure in the surface loop below the brine's vapour or bubble pressure;
    - an ESP intake pressure margin at the setting depth;
    - plant-model pump power within 10 % of GEMINI's.
  - Treat a failed check as a violation for the repair loop to fix: a booster pump, filters sized
    for the flow, the ESP set deeper from the dynamic fluid level, or a second injector.

  Then "checked with GEMINI" is true.

### 3.2 HIGH: explanations fall back to a template or are invented; numbers are checked, mechanisms are not

- **"Why two doublets and not one or three, and why a heat pump plus a boiler rather than only a
  boiler on the produced gas? Point me to the numbers behind each decision."**
  - The claim checker removed 3 of 4 sentences ("most of the reply was unsupported; showed the
    checked template"). The reply became a generic design description that never says why.
  - One removed sentence was true (61.8 against 62.7 €/MWh for one doublet). One was wrong: it
    called 2D-HP-AB-2I "the three-doublet variant", but 2I is two doublets with two injectors
    each. The best three-doublet design is 3D-HP-AB at 69.4 €/MWh.
- **"Forget the zero-fossil idea. What is the runner-up to your best design, and what exactly
  makes it lose?"**
  - The reply: "The runner-up is 2D-HP-EC, which replaces the gas backup boiler with electric
    chillers for heating ... It loses because it cannot meet your zero-fossil cap without a gas
    boiler". Its table says "Heat Source: Brine + Electric Heater" and "CO₂ Savings: Lower
    (relies on grid)".
  - All of it is wrong:
    - EC means electric chillers for cooling instead of the 1 MW absorption chiller;
    - both designs have the same 3.9 MW heat pump and boiler;
    - 2D-HP-EC emits less CO₂ (9,275 t against 9,655 t);
    - I had just dropped the zero-fossil limit.
  - The real reason is in `attempts`: "+0.6 €/MWh of heat and cold (62.4 against 61.8)".
  - No claims step ran. `agent.py _checks_claims` skips the checker when a reply rewords the
    template and reasoning is off. The reader had decided "A value, a greeting or a short reply
    needs no weighing".
- **True sentences are deleted:**
  - "CO₂ saving against gas: Drops to 51.9%" (the card says -52 %);
  - "Added a heat pump sized at 15.6 MW" (the improve step says 1.3 -> 15.6 MW). After that
    deletion the reply ends with "Key changes: - Maintained two doublets at 2,500 m depth."
- **The UI's "Understood" line** after the first design read "You want me to remove the invented
  brine temperature value (86 °C) and stick strictly to the provided context." That is the
  claim checker's re-ask prompt leaking into the field `StepsGroup.tsx` shows.
- **Why it matters:** "explain every major decision" is scored, and judges ask "why?" live.
- **Instead:**
  - Answer "why X not Y" from code. The attempts already hold a reason in numbers for every
    loser. Give the model those strings and a code-built table of how the two designs differ, and
    let it only phrase them.
  - On every model-written reply, template rewordings included, check unit roles (chillers cool;
    boilers and heat pumps heat) and direction words (lower, higher) against the data.
  - Keep a sentence when its numbers match the data.
  - Keep the first "understood".

### 3.3 HIGH: report and GEMINI-provenance requests get the canned paragraph

- **"Write a short design report on 2D-HP-AB for the hackathon judges: the design, how GEMINI
  was used, the checks it passed, the alternatives you rejected and why, and the main assumptions
  and risks."** Same canned paragraph. The trace says answer "ok": False, "the answering model
  gave no usable reply; showed the checked template".
- **"Which numbers in your design come from GEMINI and which from your own models? And what
  would GEMINI as released have given for the wells?"** Canned paragraph again. The trace shows
  exactly 800 output tokens and "ok": False: `answer.py NUM_PREDICT = 800` cuts off the JSON
  reply. In a fresh thread (`judge-3`) the same question was routed to a new design and showed
  the inputs card.
- **The eval does not catch it:** S29 ("give me the full report") passes because it checks only
  `verifier_pass` and `numbers_grounded`, not what the report contains.
- **Instead:**
  - Build the report in code as a Markdown or PDF download:
    - the inputs with their sources;
    - a provenance table (GEMINI: ESP head, injection pressure; Dioscuri: wellhead temperature
      (Ramey), PI, plant, costs);
    - the checks;
    - the candidates and their reasons;
    - the bug impact and the sensitivity;
    - the assumptions and risks.
  - Let the model write only short paragraphs, and claim-check them.
  - Raise the output cap, or let long answers be plain text.
  - Add eval checks on what the answer contains.

### 3.4 MEDIUM: the repair loop grows the wrong unit and never notices that it does not help

- **Did:** the zero-fossil, single-doublet request in `judge-2`.
- **Happened:**
  - The improve step went "heat pump 0.7 -> 22.8 MW", "22.8 -> 36.5", "36.5 -> 50.2",
    "50.2 -> 63.9 MW". After the first step the gap stayed at "worst 13.67 MW on 28 Jan".
  - The failed card shows a **63.9 MW heat pump** on one doublet's brine, which can give at most
    13.7 MW in all (300 m³/h × 40 K). It costs 99.2 M€ of capital and the heat 127.5 €/MWh.
  - `search.py improve` grows the short unit by the worst gap until `MAX_ROUNDS`. It never tests
    whether the gap shrank and never asks why the unit cannot deliver: here the 40 K brine cap,
    not the heat pump's size, is the limit.
- **Why it matters:** "iteratively improve" means diagnosing a violation, and this is blind
  growth. The failed design's price also includes 41 MW of heat pump that does nothing.
- **Instead:**
  - Stop when the gap does not shrink.
  - Name the binding limit: "the brine can give only 40 K: 13.7 MW per doublet".
  - Let the reasoning model choose a fix from a menu (another doublet, a boiler, a lower return,
    a deeper aquifer) and let code check it. This is also where the model could become a real
    agent.

### 3.5 MEDIUM: the model decides little; the "agents" are rule steps

- **Happened:** in the design turn's trace, plan, improve and rank are all
  `"decided_by": "rules"`. The model calls are the reader (1.7B), the parameter mapping (9B) and
  the reply (9B, twice). ADR-0008 says "The steps are the agents", and the agents panel labels
  rule steps as agents.
- **Why it matters:** the brief says "GEMINI is not an end-to-end optimiser: the agent is". An
  exhaustive optimiser behind a chat is defensible for reliability with small local models. But
  judges will ask "what does the LLM decide?", and today the honest answer is: the intent, the
  parameter mapping and the wording.
- **Instead:**
  - Say it plainly in the pitch: "code decides the numbers; the model decides what to try and how
    to explain".
  - Give the model one real decision that code checks: the fix menu in 3.4, which stage-2
    variants to try, or which what-ifs matter given the sensitivity tornado.

### 3.6 MEDIUM: a follow-up overwrote the recommended design

- **Did:** "My edited design U2 has no boiler and fails the heat check. Fix U2 so it meets every
  day without adding a boiler".
- **Happened:**
  - The agent ran a fresh "no boilers" search (S4). Its pick is also called 2D-HP-AB (15.6 MW
    heat pump, no boiler, 78.51 €/MWh).
  - `designs` now lists only that one, as "2D-HP-AB [agent/chosen, attempt S4]". The original
    pick (S1: 61.77 €/MWh, with a boiler) has gone from the list, and
    `design judge-1 "2D-HP-AB"` returns S4's design.
  - U2 itself was not repaired.
- **Instead:** give designs unique IDs (for example S1·2D-HP-AB) and never replace an earlier
  pick. "Fix this design" should start from U2's sizes.

### 3.7 MEDIUM: well-engineering checks a TNO reviewer expects are missing

- No check of the ESP setting depth or its intake pressure (see 3.1).
- No injection pressure limit (fracture gradient). At 50 mD the injection wellhead pressure is
  84.6 bar, about 333 bar at the bottom of the well at 2,500 m (0.133 bar/m), and nothing
  compares it with a limit.
- No surface pressure losses in the plant model, which assumes `RETURN_BAR = 4` bar at the
  injection pump.
- Constant 0.40 mPa·s and 1,030 kg/m³ for reinjected brine at 46-56 °C. Colder brine is more
  viscous, so injectivity is lower.
- The hydraulics use a vertical 2,500 m well, while the costs use the deviated along-hole length
  for 1.5 km spacing.
- **Instead:** add the three checks (intake pressure, injection pressure limit, surface pressure
  drop), and list the rest as assumptions on the inputs card.

### 3.8 LOW: gaps in the sensitivity tool

- "Doublet depth" from 2,000 to 3,000 m gives exactly 61.77 €/MWh at both ends: the doublet
  specs override `alt.depth_m` in `workbench._apply`. That is a flat line in the tornado, on the
  parameter most people try first.
- Reservoir temperature entered as 80-95 returned HTTP 500. It is a change (-10 to +5 K), so the
  input should be checked with a message instead of crashing. Six parameters in one call also
  returned HTTP 500.

### 3.9 LOW: wrong labels, contradictions and speed in answers

- The 50 mD what-if said "Cost of heat: Increases to 75.9 €/MWh (from 61.8 €/MWh)". Those are
  the combined costs of heat and cold; the card says heat 80.05 €/MWh. The same reply says the
  heat shares "remain identical", then that low permeability is "limiting the direct geothermal
  contribution, which forces greater reliance on the electric heat pump and gas boiler".
- Turns took 15-47 s of compute on the A6000, and up to 100 s with queueing. The runner-up
  question re-ran the whole search (35 designs) instead of reading the designs already made.
- The "zero fossil" design still burns the produced gas, in a flare (3,196 t CO₂ a year), and the
  reply did not say so.

## 4. Implement differently or remove

- **Make the GEMINI flowsheet a check, not a view** (3.1). Scale GEMINI's example filters and
  separator to the design flow, or add GEMINI's booster pump, and remove the "booster pump not
  needed" claim.
- **Label where each graph value comes from.** The reservoir, well and treatment nodes are all
  labelled "gemini". But the PI and the reservoir pressure come from `dioscuri_plant.doublet`,
  the wellhead temperature from Ramey, and the reinjection temperature and gas from the plant
  model. Label each value (GEMINI: ESP head, injection pressure; Dioscuri: the rest), or TNO's
  first question will expose it.
- **Replace the claim checker's fallback.** It throws away the model's answer and shows a
  template that does not answer the question; a non-answer is worse than a flagged answer.
  Regenerate from the data, or keep the answer and flag the sentence.
- **Answer questions about existing designs from the designs already made** (runner-up, why);
  do not re-run the search.
- **Update or drop `BENCHMARKS.md` in the Evidence tab.** It dates from 28 Oct, before the
  challenge engine, and sits next to 46/50 from 31 Oct. Its claim-checker result ("0 of 8 true
  claims removed") does not match what I saw: three true sentences removed in four turns.
  Re-run the readers and the claim checker on the current suite.
- **Rename the "agents" panel to "steps"**, unless the steps make decisions.

## 5. Top 3 priorities before the deadline

1. **The GEMINI loop as a check on the pick**, with the fixes for the negative pressure and the
   pump intake (3.1). This is the criterion TNO cares about most, and the contradiction is
   visible in their own tab.
2. **The explanation path** (3.2, 3.3):
   - raise `NUM_PREDICT`;
   - answer "why" and "runner-up" from the attempts' reasons;
   - check mechanisms on template rewordings;
   - keep true sentences.
3. **Unique design IDs and a stall test in `improve`** (3.4, 3.6). Two small code changes that
   remove two embarrassing demo moments.

## 6. What wins and loses points in the final presentation

**Wins:**
- Opening with the inputs card: what was read, from where, what is assumed, and the 330-day
  question put to the organisers.
- The bug-impact table: "GEMINI as released gives a 41.7 bar ESP head; with our 11 patches,
  32.8 bar". Then hand TNO the patches.
- "How I got here": 35 candidates, each loser with its reason in €/MWh. Then the case where no
  design fits, with its priced options card.
- A live what-if that runs twice (the same plant, then a new search), with the 40 K cap holding
  at exactly 40.0 K.
- Open-weight models only, on a local GPU, with tokens and seconds for every step in the trace.

**Losses:**
- A judge asks "why not three doublets?" and gets the canned paragraph, or asks about the
  runner-up and hears "electric chillers for heating".
- A judge opens the GEMINI tab and sees -2.24 bar after the filter, or 222 m³/h from a starved ESP
  on a design that "passes all 12 checks".
- Saying "our agents" when the trace says `decided_by: rules` for every design decision.
- A 63.9 MW heat pump in the repair log.
- The recommended design disappearing from the list after one follow-up.

## 7. The five changes that would raise the score most

1. **GEMINI as the checker** (GEMINI +2, correctness +1). Run the full GEMINI loop on the top
   designs and add four checks: flow agreement, surface pressure, ESP intake, and the injection
   pressure limit. Send failures to the repair loop, and show "GEMINI agrees within x %" on the
   result card.
2. **Explanations from the search record** (explanation +2):
   - answer "why X not Y" from the attempts' reasons and a code-built table of differences;
   - check unit roles and directions on every reply;
   - keep true sentences;
   - fix the "understood" leak.
3. **A real model decision in the loop** (agentic +2). Detect a repair that stalls and name the
   limit. Then the reasoning model chooses the fix from a menu, code checks it, and the chat shows
   the rounds.
4. **A one-click design report** (usability +1, explanation +1). Build a Markdown or PDF report
   in code: the provenance table, checks, candidates, bug impact, sensitivity, assumptions and
   risks.
5. **A robustness pass** (robustness +2):
   - raise the output cap, or let long answers be plain text;
   - unique design IDs;
   - wire depth into the sensitivity, and check ranges with a message;
   - answer from existing designs without a new search;
   - add eval scenarios that check what explanations say (the runner-up's reason must name
     cooling), and re-run all 50 on the final build.
