# Judge's review, round 2 (1 Nov): Dioscuri

Role: hackathon judge (TNO view; 50 % agentic workflow, 50 % energy-system design, plus bonus
items). Server 127.0.0.1:8792, threads `judge-r2a`, `judge-r2b`, `judge-r2c`. 22 chat turns,
1 GEMINI loop run, 1 sensitivity run with 6 parameters, `designs`, `attempts`, `design … all`,
`trace`. I checked the numbers by hand against the demand CSV and the design data. Code read:
ADR-0011, `engine.pick`, `parameters._failure`, `answer.named_days`, `subsurface.py`,
`tools/gemini.plant_project`, `doublet.py`, scenarios S51–S60.

## 1. Verdict

The engine underneath has grown up since round 1. There are four picks with priced reliable
plans. Failures can now be put on dates, and the remedies are run through the same days. The
comparison table is built by code. Requests of several steps work. Subsurface checks now cap the
flow. The sensitivity tool now works. Every number I checked against the data was right. But in
a 20-minute judge session the chat layer still loses the points it should win. The "why" and
"what are the alternatives" questions still get non-answers or false ones. The GEMINI provenance
answer is still wrong. Dates and durations outside plain English are silently turned into "all
year": TNO's judges are Dutch, and "van 3 tot 17 maart" gave a wrong answer. A cap-breaking flow
I asked for (400 m³/h) was applied and then carried silently into the next two searches. On
design, the recommended plant gets 49 % of its heat from a full-size gas boiler. It wins over an
untried two-doublet reliable plan by 0.02 €/MWh, and the agent never says so.

**Score: 6.2 / 10** (round 1: 5.7). It would be 7.5+ with the first five items in section 4.

| Part | Item | Score | Why |
|---|---|---|---|
| Agentic (50 %) | Interpret the demand and inputs | 8 | The inputs card is still the best thing in the demo; multi-step requests are read in one call |
| | Generate configurations | 7 | 39–42 designs, 500 sizings, 905 years in 8–45 s; but picks depend on the objective (3.5) |
| | Engineering checks, detect violations | 6 | 11 caps per day plus new subsurface checks. But the GEMINI loop is still not a check, replies contradict the checks, and a broken cap is inherited silently |
| | Iterative improvement | 4 | Same blind growth as round 1 (heat pump 0.7 → 63.9 MW, gap unchanged); plan, improve and rank are still `decided_by: rules` |
| | Explain every decision | 4 | Failure and compare replies are good. "Why", "the two-doublet option", provenance and uncertainty were all wrong |
| | Robustness (wording, language, refs) | 4.5 | 6 of 19 requests right, 5 partly right, 8 wrong (table below) |
| | **Agentic subtotal** | **5.5** | |
| Design (50 %) | Energy and mass balances | 8.5 | Every hand check closed (section 5) |
| | Design quality and insight | 5.5 | Half the heat from gas; N-1 bought with a 31.2 MW gas boiler; the near-tie with two doublets is hidden; depth is a lever the brief invites but the default search ignores |
| | Subsurface realism | 6.5 | Breakthrough, bubble point and SodM limit are in. The ESP is set with zero margin, and GEMINI's own ESP sits above that depth |
| | Techno-economics | 7.5 | ThermoGIS/PBL basis, line items, NPV and payback, all reconciled |
| | Reliability | 7.5 | N-1 plans, priced remedies, a spare ESP back after 3 days |
| | **Design subtotal** | **6.6** | |
| Bonus | Uncertainty | partial | A good tornado in the tab (0.65 s), but none in chat and no P10/P90 |
| | Techno-economics | yes | |
| | Auto model generation | not tested | |
| | Autonomous verification | partial | The claim checker removes true sentences and misses false mechanisms |
| | Multi-agent | weak | The "agents" are rule steps |
| | Token minimisation | moderate | 7–19 k prompt tokens and 3–6 calls a turn; questions re-run the whole search |
| | Open-weight local models | strong | Only Ollama qwen3 models, with tokens and seconds in the trace |
| | **Bonus** | **+0.15** | (5.5 + 6.6) / 2 + 0.15 ≈ 6.2 |

## 2. Stress test

| Request | Wordings tried | Right / wrong | What went wrong |
|---|---|---|---|
| Incomplete design request | "Design the geothermal heating and cooling system for the challenge district." | right | Inputs card in 2.4 s, then A1 · 1D-HP-EC-N1 in 8.5 s |
| Design, then what-if, then "does the pick change?" | "Design the lowest-CO2 system, then rerun it assuming the permeability is only 50 mD (a P90 case), and tell me whether the pick changes." | partly right | The steps were right and the pick changed to 3D-HP-EC-2I. But the reply says "both designs meet all challenge caps and physics checks", while W1 has "caps broken 2" (the ESP must sit at 1,270 m > 1,000 m on both doublets) |
| Why one doublet / why half from gas | "Why only one doublet and not two or three? And why is half the heat still coming from a gas boiler? Point me to the numbers behind each decision." | wrong | 3 sentences removed (one of them true: "A33 … much more expensive"). What is left only lists heat shares and never says why |
| Alternatives | "What is the best two-doublet option you found, and exactly what makes it lose against A1?" | wrong | The model said "There is no two-doublet option in this design search". 2D-HP-AB (71.39 €/MWh) is in `attempts` with its reason. Then the fallback template described A1 |
| Compare by reference | "compare the recommended one against the cheapest and the greenest" | right | A1, A9 and A33 resolved; the code table is correct. Minor: "Wells" is bolded for A1 only, though A9 also has 2 |
| Failure, dated, long English, other design | "Suppose the ESP in the producer dies on 10 January and the workover rig only gets it running again on the 24th. What does that do to the cheapest design A9, and what would fix it?" | right (one slip) | Card exact: 15 days, 6.02 MW on 22 Jan, 1.687 GWh (my hand check: 1.687). The reply calls the 6.1 MW boiler remedy "the reliable plan A2", which has 31.2 MW |
| Failure, duration, German | "Was passiert mit dem empfohlenen Entwurf, wenn die Wärmepumpe zwei Wochen ausfällt?" | wrong | `dropped: "failure heat pump: 14 days not in the message"`, so the run was "1 Jan-31 Dec (365 d, all year)" and 15.7 GWh of extra gas. The reply was left with a dangling "übernehmen andere Komponenten die Last:" followed by nothing |
| Same in English | "what happens to A1 if the heat pump is down for two weeks?" | right | Worst 14 days, 0.708 GWh of gas, 114 t, 32 k€ |
| Failure, dated, Dutch | "Wat gebeurt er met A9 als de ESP van 3 tot 17 maart uitvalt?" | wrong | The dates were dropped, so the run was all year (86 days short). The Dutch text says "tekort van ongeveer 20,8 MW … 15 dagen". The truth: March demand peaks at 19.66 MW, below A9's 20.8 MW boiler, so nothing is short |
| Two failures, typos, 19/7 date, a reference | "back to the first recomended design A1: wat if one boilr unit trips on jan 28th and the chiller is also down on 19/7?" | wrong | Re-ran the whole search (68 s, renamed F1). "One boiler unit" became the whole boiler (20.8 MW short on an N-1 plant). "jan 28th" became 28–31 Jan. "19/7" became **28 Jan** |
| Ambiguous failure | "ok and what if it breaks?" | partly right | Silently assumed "boiler", with no assumption shown. Ran on D1 (the 400 m³/h design). Extra cost shown as "-2691.7 k€" with no remedy |
| Colder reservoir, casual | "the gradient might be wrong. if the aquifer is 10 degrees colder than you assumed, does the recommendation change?" | right (omission) | 78.4 €/MWh, pick stays. Not said: the same plant is no longer N-1 ("one of the 3 boiler units 3.4 MW heat on 28 Jan"). A true sentence was removed ("running the boiler more often") |
| Out-of-cap request | "Make it four doublets running at 400 m3/h each so we never need the boiler." | partly right | 4 doublets refused. 400 m³/h applied; the card says 10/11 checks but the reply ends with "passes all 11 checks". The intent (no boiler) was not addressed |
| Depth as a design variable | "…Let the depth be free between 2,000 and 3,500 m within the 300 m3/h cap and find the best depth." | wrong | Only the two ends were searched. **400 m³/h inherited despite "within the 300 m3/h cap"** (E1 fails the flow check). It compared 58.7 (heat and cold) with "86.1 €/MWh" (the -10 K what-if's heat cost). W2 is called "@2000" but described as "at 2,500 m" |
| Off-topic | "Who won the football match between Ajax and Feyenoord last weekend?" | right | Polite refusal |
| Report for judges | "Write a short design report on A1 for the hackathon judges: …" | partly right | Now a real report, not the canned paragraph. But it re-ran the search, titled A1 "C1", said "GEMINI's well solve modelled doublet productivity and reinjection temperatures", and said "thermal breakthrough [is] not modelled" (it is, since ADR-0011). No claims step ran |
| Provenance | "Be precise: which numbers of A1 come from GEMINI itself and which from your own models? And did GEMINI's full loop agree with your plant model?" | wrong (honest on the second half) | It credited GEMINI with the PI, the wellhead and the reinjection temperatures; these come from `dioscuri_plant` (radial inflow, Ramey, the plant model). It said honestly that agreement is not checked |
| Uncertainty | "How certain is the cost of A1? Give me a P10-P50-P90 range and say which uncertainty drives it most." | wrong | No range, and it did not offer the tornado that exists. It called A1 "the -10 K reservoir variant" and gave capex 27.6, 29.8 and 33.9 M€; A1's is 30.638 M€ |
| Zero fossil, terse with typos | "zero fosil fuel pls - one doublet only, no gas boilr" | partly right | Understood, with a good options card. But the repair log still grows the heat pump to 63.9 MW, and the reason given is wrong ("because the brine at the wellhead is only 86.1 °C"); the binding limit is the 40 K brine cap (300 m³/h × 40 K = 13.7 MW) |

Tally: 6 right (2 with a slip or omission), 5 partly right, 8 wrong, out of 19 requests.
Every English request with explicit dates, codes or references worked; almost everything else
broke somewhere.

## 3. Issues

### 3.1 HIGH: failures in Dutch, German or numeric dates silently become "all year"

- **Did:** "Wat gebeurt er met A9 als de ESP van 3 tot 17 maart uitvalt?" and "…wenn die
  Wärmepumpe zwei Wochen ausfällt?" and "…the chiller is also down on 19/7".
- **Happened:**
  - The reasoning model read the dates correctly. Code then threw them away:
    `"failure doublet 1: 15 days not in the message"` and
    `"failure heat pump: 14 days not in the message"`.
  - The cards ran "1 Jan-31 Dec (365 d, all year (one unit out))".
  - The Dutch reply invented "een tekort van ongeveer 20,8 MW" for 15 days. Under it, the code
    line says "out all year … NOT met on 86 days … 9.2 MW short".
  - Correct answer: from 3 to 17 March demand is 17.2–19.7 MW and A9's boiler is 20.8 MW, so
    nothing is short.
  - "19/7" was run as 28 Jan.
- **Why:**
  - `parameters._failure` checks the model's days against `answer.named_days` and `DURATION`.
    These are English regexes: month prefixes `jan…dec` (so "maart", "mei", "okt", "März",
    "Dezember" fail); range words `to|until|till|through` (so "tot" and "bis" fail); number words
    `one…twelve` (so "zwei", "twee" fail); no d/m dates.
  - So the team's own rule ("no phrase lists decide what a message means") is broken in the
    checking layer.
  - S58 passes because it says "februari" (prefix "feb") and checks only the unit, not the days.
- **Why it matters:** TNO judges will type Dutch. A failure answer that is silently wrong in
  both its dates and its shortfall is worse than no answer.
- **Instead:**
  - Trust the model's `from`/`to` when its quote is in the message, and check that the days are
    plausible (in range, from ≤ to).
  - Never fall back to "all year" without saying so. Ask: "Which days? I read none."
  - At least add NL/DE month names, "tot/bis", "weken/Wochen/dagen/Tage" and d/m dates.
  - Add eval checks on the days run, not only on the unit.
  - Hours.

### 3.2 HIGH: "why" and "what are the alternatives" still fail; the search record is not used

- "Why only one doublet …?": the claim checker removed 3 of 4 sentences, one of them true. The
  reply never says why.
- "What is the best two-doublet option …?": "There is no two-doublet option in this design
  search". The checker removed that, and the template described A1 instead.
- `attempts` has the answer in numbers: "2D-HP-AB … +1.6 €/MWh of heat and cold (71.4 against
  69.8)", and "not sized for one unit out: the shared treatment train out leaves heat 17.0 MW
  short".
- This is round-1 issue 3.2, unchanged. The answerer's context does not include the losers'
  reasons.
- **Instead:**
  - For any "why / alternative / runner-up / two doublets / three" question, put the ranked
    `lost_reason` strings and a code-built table of differences in the context. Let the model only
    phrase them.
  - Answer from the ledger without a new search.
  - A day.

### 3.3 HIGH: a hard-cap breach is applied, labelled as passing, and inherited

- **Did:** "Make it four doublets running at 400 m3/h each…"
- **Happened:**
  - `changes: {"flow_max_m3h": 400.0}` was applied (only n_doublets=4 was dropped).
  - D1 became "agent/chosen" with `verified False` and the check "this run used 400 m3/h as you
    asked, the cap is 300 m3/h". That part is fine.
  - But the reply's code-made last line says "passes all 11 checks" (the card says 10 of 11), and
    the rank step says "of the 39 designs that meet every cap".
  - The next turn, "within the 300 m3/h cap … find the best depth", ran on top of D1. **E1
    (58.74 €/MWh, "best depth 3,500 m") and W2 both run at 400 m³/h** and fail the flow check.
  - The reply: "passing all physics checks".
  - "what if it breaks?" also ran on D1.
- **Why it matters:** the brief scores "detect violations". Here a recommended 3,500 m design
  owes part of its 11 €/MWh advantage to an illegal flow, and the chat says it passes.
- **Instead:**
  - A run that breaks a hard cap is an experiment: never "chosen", never the parent of later
    what-ifs, and it says so in the first sentence.
  - The appended summary must use the real check count.
  - Hours.

### 3.4 HIGH: GEMINI is still a view, not a check (round-1 #1)

- **Fixed:** the filter pressures (4.08 and 4.00 bar, no longer negative).
- **Still true on A1's GEMINI run:**
  - `esp_intake_pressure` is **39.04 bar**, against the subsurface check's bubble point of
    **41.7 bar** with the ESP required at **667 m**. GEMINI's loop uses `ESP_DEPTH_M = 650`, so in
    GEMINI's own model the pump draws free gas.
  - The setting depth itself has zero margin (`esp_setting_m` solves intake = bubble point).
  - GEMINI's exchanger: **7.60 MW** (brine 86.1 → 65.4 °C, about 4,280 J/kg·K implied). The
    plant model: **7.23 MW** at 3,990 J/kg·K.
  - GEMINI's network leaves the loop at **86.1 °C**, not 100 °C (no heat pump; the boiler burns
    only the produced gas).
- Nothing compares any of this. The agent itself says "I cannot confirm that GEMINI's full loop
  agrees with my plant model".
- **Instead:**
  - Set GEMINI's ESP at the subsurface setting depth plus a margin (5–10 bar).
  - Run the loop on the pick and the top 3, and show "GEMINI agrees within x %" on the card for
    the HX duty, ESP and injection power, and ESP intake against the bubble point.
  - Send a disagreement to the repair loop.
  - A day.

### 3.5 MEDIUM-HIGH (design score): the picks depend on the objective, and the best overall is an unexamined near-tie

- Default run:
  - "lowest CO2" = 3D-HP-EC, 10,045 t at 80.31 €/MWh;
  - "cheapest" = 1D-HP-AB, 68.13.
- Objective "co2" run, same inputs:
  - lowest CO2 = 2D-HP-EC-2I, **6,949 t** at 82.0;
  - "cheapest" = 1D-BO-AB, **69.66**;
  - "best overall" = 1D-HP-EC-N1 at **71.91 €/MWh, 38.8 M€**, against 69.8 and 30.6 M€ in the
    default run.
- Same code, two designs. `engine.pick` picks among entries that each carry one sizing, chosen
  for the current objective. So the card's "lowest CO2 10,045 t" is not the lowest the agent can
  find.
- With CO₂ at 137 €/t:
  - A1 costs **76.37** and the non-reliable 2D-HP-AB **76.35** €/MWh. Two doublets cut
    **3,451 t/yr** for +1.6 €/MWh, which is 62 €/t on top of ETS.
  - 2D-HP-AB loses only because no N-1 plan was made for any two-doublet layout: only the six
    cheapest layouts get one, and all six are single doublets.
  - With two doublets the natural N-1 is the other doublet plus separate trains, which ADR-0011
    lists as "not yet weighed".
- The A1 plant takes 54.99 of 111.67 GWh (49 %) from the boiler, and its N-1 comes from a 31.2 MW
  gas boiler that covers the whole 30 MW peak. A design judge will call it "a gas plant with a
  geothermal fuel saver" unless the trade-off is shown.
- **Instead:**
  - Keep every sizing in the ledger and pick each objective over all of them.
  - Make N-1 plans for the best two- and three-doublet layouts, with a train per doublet.
  - Put the geothermal share on the result card.
  - Say near-ties out loud.
  - Half a day to a day.

### 3.6 MEDIUM: provenance and the report contain false statements a TNO judge will catch

- The report and the provenance answer both credit GEMINI's well solve with the productivity,
  the injectivity and the wellhead and reinjection temperatures.
- The code: the PI comes from `dioscuri_plant.doublet.productivity_index_m3h_per_bar`, the
  wellhead from Ramey (`well_loss_k`), the reinjection from the year model. GEMINI gives the ESP
  head and the injection pressure.
- Neither turn ran a claims step.
- The report and the fallback template still say "thermal breakthrough … not modelled" and
  "the 1.5 km well spacing enters only the well cost". Both are stale since ADR-0011 (85.4 years
  is on the plant).
- **Instead:** a fixed provenance table built by code, in the report and in the context.
  Hours.

### 3.7 MEDIUM: the repair loop is unchanged (round-1 #3)

- "zero fosil fuel pls - one doublet only, no gas boilr": heat pump 0.7 → 22.8 → 36.5 → 50.2 →
  63.9 MW, worst gap still 13.67 MW.
- The reply blames "the brine at the wellhead is only 86.1 °C". The real limit is the 40 K brine
  cap: 342.5 kW/K × 40 K = 13.7 MW, plus the heat pump's electricity = 16.33 MW.
- **Instead:**
  - Stop when the gap does not shrink and name the binding cap.
  - Let the reasoning model choose a fix from a menu that code checks. That is also the one real
    model decision the "agentic" score needs.
  - Half a day.

### 3.8 MEDIUM: wrong references and units in failure turns

- "one boilr unit trips" ran as the whole boiler, so an N-1 plant "fails" with 20.8 MW short.
  `failure_unit` needs the word "unit" in the model's unit string.
- "if it breaks" silently assumed the boiler.
- For whole-unit failures the cards show negative extra cost ("cost -2691.7 k€", "-149.9 k€")
  and `best=None`. That reads as a saving, and no standby twin is offered, although ADR-0011
  says it should be.
- In the A9 ESP reply, the 6.1 MW remedy was called "the reliable plan A2".
- "How certain is the cost of A1?" became "A1 (the -10 K reservoir variant)", with D1's capex
  appended.
- "back to … A1" re-ran the whole search and renamed it F1.

### 3.9 LOW: the claim checker still damages good replies

- True sentences removed: "running the boiler more often" (-10 K), the "A33 … much more
  expensive" line, and in German "Die Kessel liefern den fehlenden Wärmebeitrag" and the demand
  "weiterhin vollständig gedeckt". Both German ones were true per the card.
- The removals left a heading with an empty list.
- Meanwhile false mechanisms passed: "two would exceed the 330-day operating cap per well" in the
  very first design reply.

### 3.10 LOW: speed and the CPU laptop

- Turns took 2.4–72.9 s on an A6000 (median about 36 s), with 7–19 k prompt tokens and 3–6
  model calls.
- Judges ran 2025 entries on CPU laptops, where the answerer becomes qwen3.5:4b. There is no
  measurement of this pipeline on a CPU (BENCHMARKS.md dates from 28 Oct).
- A question that re-runs the full search (the report, "back to A1") costs 60–70 s even on the
  GPU.

## 4. What judges would expect that is still missing (ranked by points it would win before 3–4 Nov)

1. **Explanations from the search record** (3.2, 3.6): "why", the alternatives, the runner-up
   and provenance, answered from `lost_reason`, a difference table and a fixed provenance table,
   without a new search. Explanation is scored, and it is what judges ask live. About +0.6.
   1 day.
2. **Language-independent dates, durations and units** (3.1, 3.8): trust the model's dates when
   its quote matches; ask instead of falling back to all year; "one boiler unit" means a unit.
   Dutch-speaking judges hit this in their first failure question. About +0.4. Hours.
3. **Hard caps never inherited or mislabelled** (3.3): cap-breaking runs are experiments, and
   the code-made summary uses the real check count. About +0.3. Hours.
4. **GEMINI as a check** (3.4): ESP at the setting depth plus a margin; agreement figures on the
   card; disagreement goes to the repair loop. The criterion TNO cares about most is still open
   from round 1. About +0.5. 1 day.
5. **True picks and the two-doublet reliable plan** (3.5): every objective picked over all
   sizings; N-1 plans for the best 2D/3D layouts with separate trains; the geothermal share and
   near-ties on the card. This decides whether the design half reads as "geothermal" at all.
   About +0.4. Half a day to 1 day.
6. **Uncertainty in chat** (bonus): route "how certain / P10-P90" to the tornado that exists,
   plus a small Monte Carlo (permeability, temperature, gas price, capex), giving P10/P50/P90
   LCOE and the probability that the pick changes. About +0.3. 1 day.
7. **A repair loop with a diagnosis and one real model decision** (3.7). About +0.3. Half a day.
8. **A one-click design report** (Markdown or PDF, built by code: inputs, provenance, checks,
   candidates with reasons, bug impact, sensitivity, risks). A judge takes it home. About +0.2.
   Half a day.
9. **A measured 20-minute CPU session** (3.10): turn times on qwen3.5:4b without the GPU, prompts
   trimmed, no re-search for questions. This protects against the judges' laptop test. Half a
   day.
10. **Stale text and labels**: "breakthrough not modelled"; W2 "@2000" described "at 2,500 m";
    "(one unit out)" on whole-unit failures; negative "extra cost"; a report on A1 titled C1;
    `design <thread> A1` not accepting the short ID. Hours.

## 5. What works

- **The numbers are right where code makes them.** On A1:
  - the heat split 41.75 + 14.93 + 54.99 = 111.67 GWh;
  - fixed O&M 121 €/kW × 8.803 MW = 1.065 M€;
  - purchased gas 3.2401 M€ / 69.4 = 46.69 GWh → 9,431 t;
  - produced gas 1.759 Mm³ × 0.8 → 2,763 t;
  - pumps 2.044 + 1.056 = 3.10 GWh;
  - CO₂ saving 1 − 14,103/24,365 = 42.1 %;
  - LCOE (75.69 × 111.67 + 42.11 × 23.74)/135.41 = 69.80;
  - breakthrough 85.4 years (85.7 by hand).
- **Failure on dates in English** (A9's ESP from 10 to 24 Jan): 15 days, 6.02 MW on 22 Jan,
  1.687 GWh, all exact against the CSV. The 6.1 MW boiler remedy (26.9 MW in all) just covers the outage's 26.82 MW
  peak; the spare ESP is shown as not enough (4.21 MW still short).
- **The COMPARE card by reference**: "the recommended one against the cheapest and the
  greenest" resolved to A1/A9/A33 with a correct, code-built table.
- **Requests of several steps and what-ifs that run twice**: design, then 50 mD, then "does
  the pick change", in one turn; "pick stays" / "CHANGED" on the card; the -10 K what-if (78.38)
  matches the sensitivity tool's -10 K point exactly.
- **The inputs card, the options card and the fixed sensitivity tool**: sourced inputs; priced
  options when no design fits; depth now moves LCOE (81.3 → 60.7 €/MWh over 2,000–3,000 m), six
  parameters in 0.65 s, -10/+5 K accepted, and the 50 mD point flagged with a violation.
