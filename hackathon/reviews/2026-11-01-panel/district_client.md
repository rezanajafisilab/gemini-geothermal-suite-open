# Review round 2: district energy engineer advising the municipality (the client)

Server http://127.0.0.1:8791. Threads `client-1` (11 turns) and `client-2` (11 turns), plus `designs`, `design … plant/economics/year/checks`, `attempts`, `trace` and one `sensitivity` run on A1. I wrote in plain, loose client language and checked the numbers in Python against the design data. Transcripts: `scratchpad/panel2/client/t1.txt` … `t22.txt`.

## 1. Verdict

The engine now gives me what I asked for in round 1. Every search shows four picks, the one-unit-out cases are listed with MW and dates, a failure on a named design gives the shortfall and a costed remedy, and "design it, then +30 %, compare" works in one turn. I could not take the chat to a council yet, for three reasons:
- **It loses track of which plant we are talking about.** "For A1" ran on C1 twice, "the cheapest one" ran on A1, and "the one you recommended first" was compared against B41.
- **It still cannot write the council summary or the money-per-home answer.** It failed 0 of 3 council wordings and got 1 of 2 money wordings right. The claim checker deleted a correct draft ("9.5 M€ a year against 11.2 M€ for gas; 14,103 t; 42 %") and the agent fell back to the paragraph on wells.
- **The recommended plant is half a gas plant, and the label hides it.** In A1 the "backup boiler" gives 49 % of the heat and burns 46.7 GWh a year of bought gas.

For a Dutch municipality, where new districts have been built without gas since 2018, that last point is the first thing a councillor will find. The agent should say it plainly and offer the gas-free and green-and-reliable alternatives at a price, not bury it.

## 2. Stress test

| Request | Wordings tried (quoted, shortened) | Right / wrong | What went wrong |
|---|---|---|---|
| Best design | t1 "What's the best design you can give us?"; t12 "design the plant for us, then …" | **2 / 2** | Both gave A1 · 1D-HP-EC-N1, 69.8 €/MWh, N-1. |
| Greenest | t4 "Show me the greenest option then. What does it cost us extra compared to your recommendation?" | **½** | Greenest found (B1 · 2D-HP-EC-2I, 6,949 t). "Extra compared to your recommendation" was never answered. A new search ran and the other picks moved (issue H4). |
| Green **and** safe | t7 "the green one but also safe if something breaks during a cold week in january? I need both" | **0 / 1** | It set objective = reliable, dropped "green", and returned C1 · 1D-HP-AB-N1 with a 41.2 % cut. That is greener than nothing but less green than A1 (42.1 %). It still answered "Yes … already meets your requirement". |
| Cheapest (Dutch) | t15 "wat is de goedkoopste optie, en is die ook leveringszeker …?" | **0 / 1** | "1D-HP-EC-N1 is de goedkoopste en meest betrouwbare optie". The same reply ends "picks 1D-HP-AB at 68.1 €/MWh". It labelled 69.8 as "kosten voor warmte", but heat alone costs 75.7. It never said whether the cheapest plan survives a breakdown (it does not: 5 cases short). The reply switches to English at the end. |
| Most reliable / why not A2 | t22 "your card calls A2 the 'most reliable' but you recommend A1. is A1 less safe?" | **½** | "A1 is not less safe" is right. But it said "lower cost of heat (75.7 €/MWh vs 73 €/MWh)", which has the order backwards, and then "the marginal reliability difference", which does not exist. The question also started a full new search (F1 … F42). |
| Compare with an earlier design | t5 "how much more does the green one cost than the one you recommended first? side by side"; t6 "no, I mean A1 vs B1" | **1 / 2** | t5 compared B1 with B41 (the cheapest of the second search), not with A1, and said B1 "uses fewer wells" (6 against 2). t6, with names, was right. |
| Breakdown on a named design | t8 "For A1: … the geothermal well itself breaks down for a week right in the coldest week"; t16 "and the cheapest one: if the heat pump breaks down for two weeks in a cold spell"; t17 "same question but for A9 (the cheapest)" | **1 / 3** | t8 ran on C1 and took 1–7 Jan as "the worst 7 days". The coldest week is 25–31 Jan (mean 28.3 MW against 25.1 MW). The reply was cut off mid-sentence. t16 ran on A1 and answered with the chillers ("No one goes cold … the chillers cover the demand"). t17 was right (issue M1). |
| "Something breaks in a cold week" | t7 (same message as above) | **0 / 1** | Read as "the heat pump out 1 Jan–31 Jan (31 d)". "Something" became the heat pump, and a week became a month. The reply never mentioned the FAILURE card. |
| Demand growth | t11 "district might grow by 20% more homes in 10 years. does A1 still cope?"; t12 "+30 % more heat demand and compare" | **1 / 2** | t11 ran on C1, not A1. It said "backup boiler and chillers will likely be insufficient to meet peak loads", which is false (spare 4.4 MW on 28 Jan), and left "you would need to add capacity to the backup units:" with nothing after the colon. t12 gave a correct table but called the +30 % plant "reliable" when 4 of 5 one-unit-out cases are short. |
| Colder network | t14 "run the heat network colder, like 70 degrees out and 40 back? is that cheaper and greener?" | **½** | The direction was right (55.5 % cut). It compared the heat cost (65.9) with the combined baseline (69.8). It never said that 70 °C breaks the brief's 100 °C, although the check failed (10 of 11). |
| What to tell the council | t9 "What do I tell the council on Thursday? … which option, what it costs the city, the co2, and the risks"; t10 "one-page council memo for A1 …"; t20 "5 short bullet points about A1 … I can read out to the council" | **0 / 3** | t9 gave two sentences with no numbers, about C1, not A1. t10 and t20 gave the wells paragraph (`fallback: true`). In t20 the claim checker removed 4 correct bullets. |
| Money, per home | t18 "what does it cost per year in total, and per household if we have 10,000 homes? … compared with just gas boilers"; t19 "Is A1 cheaper than gas boilers? by how many euros a year, and what's the payback" | **1 / 2** | t18 gave the wells paragraph: "9,500,000, 950 … not in the context" were removed, and 950 €/home is correct (9.45 M€ / 10,000). t19 was right: 9.5 against 11.2 M€, payback in year 10. |
| Gas share | t3 "how much of the heat actually comes from the geothermal well and how much from burning gas?" | **½** | It gave "37.4 %" for the geothermal heat only. 62.6 (the rest) was removed. It never stated the boiler's 49.2 %. |
| Gas-free and reliable | t21 "Can you make a reliable design without any gas boiler, e.g. an electric boiler as backup?" | **0 / 1** | The reply contradicts itself ("No design meets every cap … covers 100% of the heat, 0 GWh a year short"). The two options are identical ("Allow a boiler: … 73 €/MWh. Lift all these limits: … 73 €/MWh"). It never said that it has no electric boiler. |

Names and costs between reply and cards:
- The same plant gets a new name in each search. In `client-2`, A1 = W3 = F1. In `client-1`, A1 = C2 and A2 = C1.
- The headline mixes heat-only and heat-plus-cold costs in 3 replies (t14, t15, t21).
- In the app the picks row shows A1 and A2 both at "69.8" (69.80 and 69.77). The one not recommended is labelled "most reliable".

## 3. Issues (most important first)

### H1 (high). Council and money answers are still deleted or replaced by the wells paragraph

- **Messages:** t9, t10, t18, t20 (above).
- **What happened:**
  - t20: the draft was exactly right. "**What we build:** … one deep doublet well (2,500 m), a heat pump for top-up heating, a backup gas boiler, and three electric chillers"; "**Cost vs Gas:** The total annual cost is 9.5 M€, which is 1.7 M€ cheaper than a pure gas-based reference system"; "**CO2 Reduction:** The plant emits 14,103 tonnes … a 42% reduction".
  - The claim checker removed all 4 bullets. The reply became "1D-HP-EC-N1 covers 100% … Wells: 1 doublet(s) in the known aquifer … productivity index 14.5 m3/h/bar … Ramey (1962) …".
  - One turn earlier (t19) the same 9.5 / 11.2 M€ figures were kept, because that context had the money block. The council turns went through the `docs` route with `used: []`.
  - t9 kept only: "The recommended design is the Reliable Hybrid Plant (1D-HP-AB-N1). It combines our geothermal well, a heat pump, a backup gas boiler, and electric chillers." The removed sentence was "The total annual cost is 9.4 million euros, which is lower than the gas-only alternative of 11.2 million euros". It was correct for C1 (73.01 × 111.668 + 54.55 × 23.743 = 9.45 M€).
  - t18: "950" €/home was removed as "no source gives". Per-home figures are still never computed in code.
- **Why it matters:** The council summary and the cost per household are the two outputs a client exists for. This was round 1's H1 and H3, and the code fix (`answer.money_lines`) exists. But the context is still chosen by regexes (`COST_TALK`, `DESIGN_TALK` in `agent.py` around line 2880), and the docs route skips them. The checker then deletes whatever it cannot find, even figures the agent printed one turn earlier.
- **What to do:**
  - Build the council memo and the decision table in code from the ledger: recommendation, M€ up front, M€/yr all-in against gas, € per home once homes are known, CO2 t and %, share of heat from gas, reliable yes/no, not assessed. The model only smooths the words.
  - Always put `money_lines` and the picks into the context when a design exists.
  - Never let a turn with any design in scope fall back to `design_notes`.

### H2 (high). Names in the message are lost for failures and what-ifs, so answers are about a different plant

- **Messages and results:**

  | Message | Ran on |
  |---|---|
  | t8 "For A1: suppose the geothermal well itself breaks down …" | C1 · 1D-HP-AB-N1. The reply says "for C1 (the chosen reliable plan)". |
  | t11 "does A1 still cope …" | C1 (W1 "against C1"). Trace: `"dropped": ["designs: not a parameter"]`. |
  | t16 "and the cheapest one: …" | A1, not A9 / 1D-HP-AB. |
  | t5 "than the one you recommended first" | Compared B1 with B41. |
  | t9 / t10 council memo "for A1" | Described C1. |

- **Why it matters:** The client never sees the switch, because the reply names the code in passing. In t16 the difference is the whole answer: A1 is N-1 and the cheapest plant is not. Run on the right design (t17, A9), the heat pump outage leaves 4 days short, 1.97 MW on 28 Jan, and needs +2 MW of boiler.
- **What to do:**
  - When the reader returns a name, a pick or a code, bind the step to it in code, and refuse to fall back silently to `session.chosen`.
  - Resolve "the cheapest / greenest / recommended / first one" against the picks of the search the user saw.
  - Put "Ran on: A1 · 1D-HP-EC-N1" at the top of every FAILURE and what-if card, and in the first line of the reply.

### H3 (high). The recommendation is half gas, and "backup boiler" hides it

- **Data for A1 · 1D-HP-EC-N1:**
  - Plant: heat exchanger 7.23 MW, heat pump 2.0 MW, boiler 31.2 MW (3 × 10.4).
  - Heat split: geothermal 41.75 GWh (37.4 %), heat pump 14.93 GWh (13.4 %), **boiler 54.99 GWh (49.2 %)**.
  - Bought gas: 46.7 GWh a year, 9,431 t of the 14,103 t of CO2. The cut against gas is 42.1 %.
- **Labels:** The card reads "heat pump top-up with a backup boiler" (`engine.py` line 1193 says "backup" whenever `boiler_mw > 0`). In t15 the Dutch reply calls the same unit "Peak boiler: 49,2 %" and then "aangevuld door een backup boiler".
- **t3** asked "how much … from burning gas?" and got only "37.4 %" from the geothermal heat. 62.6 was removed.
- **Why it matters:**
  - Here N-1 is met by a gas plant big enough for the whole peak (40.4 MW available against a 30 MW peak).
  - That is a legitimate engineering answer at 69.4 €/MWh gas, but it is the decision the council has to make. Saying "backup" for a unit that makes half the heat would get the advisor in trouble.
  - The real trade-off is not shown. The greenest plant (B1, 71.5 % cut) costs 11.10 M€/yr against 9.45 M€/yr for A1. That is +1.65 M€/yr for 7,155 t/yr less, **≈ 231 € per tonne avoided**, against PBL's 137 €/t. It is still no dearer than gas boilers (11.2 M€/yr). The agent never said either figure.
- **What to do:**
  - Add a code tile with the share of heat from geothermal, heat pump and gas (bought and produced).
  - Call the boiler a "peak boiler" when it gives more than about 10 % of the heat.
  - Add a code line "Going to <greenest>: +x M€/yr, −y t/yr, z €/t avoided" to every pick card.

### H4 (high). Picks change between searches and the same plant gets new names

- **Picks move between searches:**
  - Asking for the greenest (t4) ran a new CO2-sized search (S2). The card then showed "best overall: B26 · 1D-HP-EC-N1, 71.91 €/MWh, 11,002 t" and "cheapest: B41 · 1D-BO-AB, 69.66".
  - The first search (S1) had "best overall: A1 · 1D-HP-EC-N1, 69.8 €/MWh, 14,103 t" and "cheapest: A9 · 1D-HP-AB, 68.13".
  - So the same code moved by 2.1 €/MWh with no change of inputs, and "cheapest" got dearer.
  - Under the stated rule (CO2 at 137 €/t), A1 scores 76.4 and B26 scores 77.0. The S2 card therefore recommends a "best overall" that loses to a design already in the thread.
- **Names multiply:**
  - "Back to normal temperatures" (t15) and a question about labels (t22) each started a full search. In `client-2`, A1, W3 and F1 are the same plant. In `client-1`, A1 = C2 and A2 = C1. In t7 the "recommended" pick became C1, which is A2 under another name.
  - "Most reliable" (A2, 69.77) appears beside the recommended A1 (69.80). In the app both read "69.8". A1 is equally reliable, cheaper to build (30.6 against 31.5 M€) and emits 231 t less.
- **Why it matters:** A councillor who hears "best overall 69.8" in one meeting and "best overall 71.9" in the next, for the same code, will stop trusting every figure. The label "most reliable" invites "why not the safest one?"
- **What to do:**
  - Compute the picks over every design evaluated in the conversation, or make every search include the cost-sized variants.
  - Give a plant spec one name for life (hash the plant; reuse A1 when a later search finds it again).
  - Rename "most reliable" to "cheapest reliable plan", or drop it when the best-overall pick is itself reliable.
  - Do not re-search for questions about labels or picks.

### H5 (high). "Green and reliable" and "gas-free and reliable" cannot be asked for

- **t7:** No objective means "lowest CO2 among reliable plans". It answered with the cheapest N-1 plan (41.2 % cut) and "Yes".
- **t4:** The greenest pick B1 has 0.05 MW of spare heat and 0 MW of spare cold on the peak days, and fails all 7 one-unit-out cases. For example, losing the shared treatment train leaves 24.2 MW of heat short on 28 Jan. The reply said "passes all 11 checks" with no warning.
- **t21, gas-free:**
  - The N-1 sizing (`firm.reliable`) can only grow boiler and chiller units, so no reliable plan without a boiler can exist.
  - The agent has no electric boiler. It did not say so.
  - It showed a contradictory infeasibility text and two identical options at "73 €/MWh", a heat-only cost from another design. The card's E1 costs 92.94 €/MWh for heat and cold.
- **Why it matters:** "Green, reliable and no gas" is the brief a Dutch municipality gives. The tool's answer space has no point for it. An electric boiler (cheap per MW, grid-flexible) or a second heat pump unit is the standard way to get N-1 without gas.
- **What to do:**
  - Add the constrained picks "greenest reliable" and "cheapest with at least X % cut".
  - Add an electric boiler component.
  - Let the N-1 sizing split the heat pump into units, or add a doublet, when the boiler is excluded.
  - When nothing fits, say which limit binds: "my reliable sizing only adds boiler units".

### M1 (medium). Failure answers: wrong week, wrong unit, cut-off text, remedies not quoted

- **t8:** "a week right in the coldest week" was run as 1–7 Jan, labelled "the worst 7 days of the year".
  - With N-1 nothing is short, so `worst_start` ranks by bought gas, every winter week ties, and `argmax` takes the first one.
  - The coldest week is 25–31 Jan.
  - The reply ended "If a spare ESP or wellhead equipment were kept" (cut off) and said "based on the draft's calculation".
- **t7:** "something breaks during a cold week" became "the heat pump out 1 Jan–31 Jan (31 d)".
- **t16:** A heat pump failure "in a cold spell" got an answer about chillers: "No one 'goes cold' in terms of losing the ability to cool".
- **t17:** The right answer, but the remedy's cost (0.15 M€, 14.9 k€/yr) is on the card and not in the reply.
- **What to do:**
  - When ties occur, break them by demand, or ask "the coldest week, 25–31 Jan?".
  - For "something", run the largest unit or all units and report the worst.
  - Always quote the remedy line from the card.

### M2 (medium). What-if replies misstate reliability and physics

- **t11 (+20 %):** "will likely be insufficient to meet peak loads". The plant meets every day, with a peak of 36 MW against 40.4 MW of capacity. What is actually lost is N-1 (3 of 6 cases short: doublet out 4.8 MW, one boiler unit out 5.97 MW) and CO2 (42 → 36 %). The reply did not mention either.
- **t13 (+30 %):** "This reliable plan ensures any single unit can be out" while 4 of 5 cases are short. "the boiler (running on produced gas) contributes a larger share": the extra heat is from bought gas, because produced gas is fixed by the flow.
- **Growth scope not stated:** "20 % more homes" scaled only the heat. The cold stayed at 10 MW, and the agent did not say so.
- **What to do:** Have code write a "still N-1? yes / no (n cases short)" line and a "CO2 cut x → y %" line on every what-if card and in the reply.

### M3 (medium). The colder-network what-if hides that it breaks the brief, and mixes metrics

- **t14:**
  - "Cost of heat: 65.9 €/MWh (down from the baseline 69.8)". 65.9 is heat only and 69.8 is heat and cold. The like-for-like figures are 75.7 → 65.9 for heat, or 69.8 → 61.7 combined.
  - The card fails "Heat at 100 °C every day" (10 of 11 checks; `verified False`), yet the designs list shows "caps broken 0". The reply said "while maintaining N-1 reliability" and nothing about the 100 °C requirement.
  - "Searching again picks 2D-BO-EC-N1 at 61.8 €/MWh instead of" W2 at 61.7 reads as a dearer pick, with no reason given (lower CO2 at 137 €/t).
- **Why it matters:** For a new, well-insulated district, a colder network is the client's strongest lever. The sensitivity run on A1 gives a 50 °C return → 65.5 €/MWh and a 54.6 % cut; 70 °C → 76.0 and 27 %. The reply should present it as "outside the brief, but worth this much".

### M4 (medium). Questions start searches; the reader marks client questions irrelevant

- Searches started by questions: t15 started search D; t22 started search F (39 designs, 40–90 s). "forget the gas-free one for now … is A1 less safe than A2?" is not a design request.
- The reader marked `relevant: false` on t5, t9, t10, t11 and t22. Four of these are council or comparison questions.

### L1 (low). Leaks and stale text

- **Leaked instructions:** The Understood lines show the guard's instructions, for example "I will remove the invented CO2 numbers and rely only on the context data" (t9) and "I will recalculate using only the numbers explicitly found in the provided text" (t18). This was round 1's M3. Replies also say "Based on the provided text", "The text states" and "described in the draft".
- **Stale text:** The wells paragraph (`answer.py` line 839) still says "Not modelled: the reservoir's cooling over the years (thermal breakthrough)". The new Gringarten-Sauty check gives 85.4 years for A1.
- **Small errors:**
  - t6: a "However, …" sentence is left without the sentence it answered.
  - t5: B1 "uses fewer wells" (6 against 2).
  - t2: "heat 75.7, cold 42.1, with 42.1 % less CO₂" (a coincidence, but it reads like a copy error).

## 4. What a client and a district energy engineer need most that is missing

1. **A code-built decision table and council memo (about a day).** The rows are: gas reference, recommended, cheapest, greenest, greenest reliable. The columns are:
   - M€ up front and M€/yr all-in;
   - € per home (once the number of homes is in the brief);
   - CO2 in t and as a % cut;
   - % of heat from gas;
   - N-1 yes/no;
   - € per tonne avoided against the recommendation.

   All of these are in the ledger already (`money_lines`, picks, `firm`). This one page is what the client takes to the council. Without it every other feature stays in the engineer's tab.
2. **Stable picks and one name per plant across the conversation (a day).** Without it, "A1" cannot be relied on, and neither can "best overall" (H2, H4).
3. **The objectives a council actually sets (a few days).**
   - "Greenest that is still reliable" and "cheapest with at least X % CO2 cut" as picks: hours.
   - An electric boiler: hours.
   - N-1 with the boiler excluded, by heat pump units or a second doublet: a day or two.
4. **Growth and phasing (days).**
   - The best plan across demand scenarios (0 / +20 / +30 %).
   - "Start with A1, drill doublet 2 when demand passes x", with the NPV of waiting.
   - A1 meets +30 % every day, but loses N-1 and drops to a 35 % cut. At +30 % the search prefers a 2-doublet reliable plan at 69.9 €/MWh. A municipality planning a district that is built in stages needs exactly this answer.
5. **Security of supply in client terms (a day).**
   - Per design, one sentence: "if the well, the heat pump or one boiler fails on the coldest day, everyone stays warm / x MW short".
   - The coldest week by default, and an hourly peak factor (still sized on the daily mean: 40.4 MW for a 30 MW daily peak).
   - The spare-parts policy (the spare ESP line is good: 0.24 M€, back after 3 days).
   - A "gas supply cut" case when the backup is gas.
6. **The network and the tariff (days).**
   - Network losses and distribution pumping (missing since round 1).
   - The street network and house connections (the largest cost for a new district).
   - The heat tariff against the ACM maximum price, and SDE++.
   - Residents see the tariff, not the €/MWh at the plant. The money lines already say the network is not included; give a per-home range with it.
7. **A fixed "not assessed" list for public meetings (hours).** Drilling success (a P90 flow), induced seismicity and the SodM permit, flaring the produced gas when there is no boiler, and the 330-day reading still waiting for the organisers' answer.

## 5. What works

- **Steps of several parts:** "design the plant for us, then show me what happens with 30 % more heat demand and compare the two" gave the design, the what-if and a baseline / +30 % table in one turn. The card adds the one-unit-out list (4 of 5 short) and the re-search pick (2D-HP-AB-ST-N1 at 69.9).
- **Failures on a named design:** A9's heat pump out for 14 days was placed on 16–29 Jan, the right window. It found "4 days short, 1.97 MW on 28 Jan, 0.117 GWh" and costed the remedy at "+2 MW boiler, 0.15 M€, 14.9 k€/yr". That is what a utility engineer wants, and it matches the data.
- **The COMPARE card by name:** A1 against B1 marks the best of each row, and every figure matches the designs' runs.
- **The four picks and the firm-capacity block on the result card:** spare MW on the peak day and each unit-out case with MW and date. This is a large step from round 1, where the "backup" boiler covered nothing. The checks also flag a run outside the brief honestly ("this run used 70 °C as you asked, the cap is 100 °C").
- **The money lines, when they reach the model, are correct:** t19 gave "9.5 M€ … gas reference costs 11.2 M€ … discounted payback occurs in year 10 … capital cost is 30.6 M€".
