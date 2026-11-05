# Operator review, round 2 (1 Nov): failures, spares and the reliable plan

Role: shift lead of a Dutch geothermal heat plant with backup boilers and chillers. Server http://127.0.0.1:8790. Threads `op-1` (default brief, 1-doublet recommendation) and `op-2` (exactly two doublets, N-1): 23 chat turns and 1 `edit`. I checked the agent's numbers in two ways: against the workbench's daily series, and by re-running `dioscuri_plant.firm` locally with the same plants (scripts `n1*.py` in the scratchpad folder listed at the end).

Designs used:
- **op-1 A1 · 1D-HP-EC-N1**: 1 doublet, exchanger 7.23 MW, heat pump 2.0 MW, boiler 31.2 MW as 3 × 10.4 MW, chillers 15 MW as 3 × 5 MW. 69.8 €/MWh. The boiler makes 49 % of the year's heat.
- **op-2 A1 · 2D-HP-AB-ST-N1**: 2 doublets with a treatment train each, exchanger 14.46 MW, heat pump 2.6 MW, boiler 27.4 MW as 3 units, absorption 1 MW, chillers 13.5 MW as 3 units. 73.3 €/MWh.

## 1. Verdict

The plant side has moved a long way since round 1, and I could now sign off the *design*:
- the recommendation is an N-1 plan by default;
- the result card shows the spare on the peak day (op-2: 14.45 MW heat, 4.5 MW cold) and all seven one-unit-out cases;
- every failure I asked about was actually simulated, on the right dates when it read them, and the FAILURE card is honest about what it ran.

I would still not let the control room use the chat for contingency questions. **In 9 of 15 failure turns the reply contradicted its own card or the physics.** Examples:
- "No, you cannot hold 100 °C" when one boiler unit trips on the reliable plan. My own run of the plant says it holds, with 0.03 MW to spare.
- "the 100 °C … wordt niet gehaald" when the card says heat is met every day.
- "Yes, U1 remains N-1 compliant … However … short 3.4 MW".
- It offered **23 Jan–1 Feb as the "best" maintenance window**. That is the worst window of the year, and the card itself says "the worst 10 days".

The machinery behind the chat is right. The faults are in how a message is read: "one boiler unit" becomes the whole boiler, and "the coldest day", "20/01" or "1. bis 21. Dezember" become "all year". After that, the answer model is free to override the card's verdict. These are hours of work each, and until they are fixed an operator gets a confident wrong answer to the one question that matters most.

**Round-1 issues: status**

| Round-1 issue | Status now |
|---|---|
| 1. No N-1, no margin, "backup" boiler | **Fixed in the design:** reliable plans (3 boiler and chiller units), spare on the peak day and the N-1 cases on the card, separate trains picked for the 2-doublet plan. **Not fixed:** the name still says "backup boiler" for a boiler that makes 49 % of the heat (op-1 A1) and fires all 365 days. |
| 2. The trip answer flips with wording | **Half fixed.** A failure run now exists and the card is from code. The flip has moved to how the unit and the date are read (issues 1–3 below), and the reply can still deny its own card. |
| 3. No day-level data | **Mostly fixed.** "What is running on 19 July" got it right: doublet 1 in its stop "9 Jul – 12 Aug", doublet 2 at 136.4 m³/h, 85.03 / 65.21 °C, heat 2.67 = 1.34 + 0.51 + 0.83 MW, cold 1 + 9 MW. It did not say how close the chillers were to their limit (the claim check removed that sentence). |
| 4. Invented equipment | **Not fixed:** "The district relies on stored heat or lower temperatures"; "Die Bohrung 2 kann weiter produzieren" (its separator is down); suggestions to "add a small buffer tank" or "store cold in tanks". |
| 5. The claim check deletes correct text and keeps wrong text; leaks | **Not fixed.** Correct statements were removed (t05, t16). No claim check ran on 14 of 22 answer turns, including the worst replies. The "Understood" row leaks retries ("You want the response reformatted as JSON …"). Padding remains ("The cost of heat is 76.1 €/MWh."). |
| 6. Starts, turndown, peak hour | **Not fixed, but now honest:** "does not model hourly peaks, start-ups, or ramping". Doublet 2 still makes 6 starts with one-day runs on 16 Apr and 1 Oct. Boiler units run below 25 % of one unit's rating on 168 days. |
| 7. Handover | **Not fixed.** Doublet 2 restarts on 9 Jul, the day doublet 1 stops, after 80 days idle. The operations facts still say "stopped days 190–224". |

## 2. Stress test

| Request | Wordings tried | Right / wrong | What went wrong |
|---|---|---|---|
| **Dated outage: are the dates read?** | "from the 10th to the 24th of Jan"; "1–14 Feb"; "for a fortnight in January"; "on 28 January"; "next winter … out for six weeks"; "3 t/m 9 februari"; "2027-12-01 … 2027-12-21"; "from 15 to 25 July"; "on the coldest day" (×2); "on 20/01 … until 27/01"; "vom 1. bis 21. Dezember" | **8 / 4** | "Coldest day" (twice), dd/mm and German dates were all run as **all year**. One case was "is back the next morning", which became "doublet 2 out all year … 839 k€ more running cost". |
| **Which unit is out?** | "the ESP"; "production pump"; "the heat pump"; "warmtewisselaar"; "ESP on doublet 2"; "heat exchanger plates"; "a pump"; "Doublet 2"; "one boiler unit" (×2 wordings); "one of the three boiler units"; "one chiller unit and the absorption chiller"; "Gasabscheider der Dublette 2" | **8 / 5** | **Every "one unit of a 3-unit bank" was run as the whole bank** (3/3 boiler, 1/1 chiller). "Dublette 2" became "train 1", which is doublet 1's train. |
| **Does the reply agree with the card?** | t03, t04, t05, t06, t07, t08, t09, t11, t12, t13, t14, t18, t19, t21, t22 | **5 agree / 9 contradict / 1 vague** | Details in issues 2–4. |
| **Which design is meant?** | "A1"; "Back to A1"; "On A1"; "A1 again"; "the recommended design"; "Worst case for A1"; "my edited design U1"; "the cheapest one" | **6 / 2** | "Worst case for A1" ran on B1, and the reply said "There is no design named A1". "the cheapest one" started a whole new search and **switched the recommendation** from the N-1 plan to the non-N-1 cheapest one (issue 5). |
| **Spare on the peak day** | "how many MW of spare heat … with everything running" | **1 / 0** | 14.45 MW, right. But in the same reply the sizing case was wrong (issue 6). |
| **Two failures at once** | ESP + boiler unit, 20/01–27/01; chiller unit + absorption, 15–25 July | **0 / 2** | First case: the dates were lost, both units were run out all year, and the reply said "does not simulate simultaneous faults" even though its card had. Second case: "one chiller unit" became all chillers, so the answer was "10 MW short over 11 days" when the truth is **1.0 MW short on 8 days, 0.096 GWh**. |
| **Maintenance window** | "a 10-day maintenance window to … clean the heat exchanger plates. Which 10 days are best?" | **0 / 1** | It gave the worst window as the best (issue 4). |
| **Operator questions** | min load of the boiler units; starts and minimum run time; ESP swap time and ramp-up; which outage sets the boiler size | **1 / 3** | Starts: honest "not modelled" (right), but the count, which is in the data, was not given. Min load: right figure (0.83 MW) but no day count, and it implied a 25–30 % rule is modelled. Swap time: a useless clarifying question after the claim check deleted two correct sentences. Sizing case: wrong. |

## 3. Issues

### Issue 1 (high): "one boiler unit" or "one chiller unit" is run as the whole bank, and the reliable plan is then declared to fail

**Messages (op-1, A1 = 1D-HP-EC-N1 with 3 × 10.4 MW of boiler):**
- t06: "On A1: one boiler unit trips on the coldest day. Do we hold 100 °C?"
- t07: "A1 again: if one of the three boiler units is unavailable on 28 January, can the plant still deliver the full 30 MW? How much spare is left?"

**What happened.**
- Parameters read `"unit": "boiler"`. In t07 the step also listed `unsupported: ["one of the three boiler units unavailable on 28 January"]`, then ran anyway. Card: "the boiler out 28 Jan-28 Jan … 20.77 MW short". Remedies: none (`best=None`).
- t06 reply: "**No, you cannot hold 100 °C.** … if the boiler trips, heat demand is not met for 318 days". The 318 comes from the context of another design, B1 1D-HP-AB. The card says 327 days, so one reply gives two numbers.
- t07 reply: "**This design does not have multiple parallel boiler units; it has one large backup unit.**" Then it suggested "switch to design B8 (1D-HP-AB-N1) which has multiple boiler units".
- op-2 t18, "one chiller unit and the absorption chiller are both out from 15 to 25 July": the card ran "the electric chillers out", meaning all three units. Reply: "shortfall of 10 MW … 2.46 GWh".

**The truth, from `firm.failure` on the same plants:**
- One boiler unit out on 28 Jan: demand 30.0 = exchanger 7.23 + heat pump 2.0 + boiler 20.77 (2 units = 20.8 MW). Met, with 0.03 MW to spare.
- One chiller unit plus the absorption chiller out 15–25 Jul: 8 days short, worst 1.0 MW on 19 Jul, 0.096 GWh.

**Why it matters.** This is the round-1 safety flip, back in a new form. The reliable plan exists to survive exactly this trip. The chat tells the shift lead it does not, and invents a "single unit" design. An approver reading t07 would reject the recommended plant.

**What to do.**
- Resolve the unit against the design. When `boiler_units > 1`, "the boiler", "a boiler", "one boiler (unit)" and "boiler 2" mean `boiler unit`. "All boilers" and "the boiler house" mean the whole bank. Chillers likewise.
- Use the model's own `unsupported` note as a stop: never run a substitute unit silently.
- Give multi-unit failures a remedy row ("a fourth unit of X MW") so the card is not empty.

### Issue 2 (high): the reply overrides the card's verdict

| Turn and message | Card | Reply |
|---|---|---|
| op-2 t11: "Wat gebeurt er als de warmtewisselaar uitvalt van 3 t/m 9 februari? Halen we dan nog 100 graden?" | heat met every day | "**De doeltemperatuur van 100 °C … wordt niet gehaald**" |
| op-2 t21: "Is U1 still N-1 - can it lose any one unit, including the heat exchanger, on the peak day?" | "one unit out: 1 of 7 cases short: the heat exchanger 3.4 MW heat on 28 Jan" | "**Yes, design U1 remains N-1 compliant** … It can lose any one unit, including the heat exchanger … However, losing the heat exchanger does cause a shortfall … 3.4 MW" |
| op-1 t08: ESP out "next winter … six weeks" | "42 days short … 4.88 GWh" | "**The model does not simulate trips or short outages** … Heat is short for **86 days**". These are the all-year numbers. |
| op-1 t09: ESP + boiler unit | both units simulated together | "Our model **does not simulate simultaneous faults**" |
| op-1 t04: "cheapest one, production pump down 1–14 Feb. town still warm?" | 14 days short, worst 6.35 MW; cold met | "**Yes, the town remains warm**" and then "6.4 MW deficit". Also "leaves **100% of the cold demand** unmet", false: there is no cold demand on 1 Feb. A table shows the "Heat Exchanger: Running (7.23 MW)" and the "Heat Pump: Running (2 MW)": with the only doublet out, both are at 0. "relies on stored heat": there is no store. "raising costs to 69.8 €/MWh": that is another design's cost; the card says 0.48 M€ and 50 k€/yr. |

**Why it matters.** The card is right and the words are wrong, so the operator gets two answers and believes the friendlier one. The worst replies (t04, t06, t11, t21) had **no claims step at all**.

**What to do.**
- For a failure step, lead with code's `failure_text` as the answer. The model may add context without numbers or verdicts.
- Reject a reply whose yes/no disagrees with `needed` / `days_short`, or that says "not simulated" when a failure card is attached.
- Always run the claim check on failure replies.

### Issue 3 (high): dates outside a few patterns become "all year"

| Message | Card |
|---|---|
| t06: "on the coldest day" | all year |
| op-2 t22: "Doublet 2 trips on the coldest day of the year and is back the next morning" | "out all year … 21.94 GWh more gas … 839 k€". The spare ESP is then credited with saving 1,809 k€, for a one-day trip. |
| t09: "fails on 20/01 … (until 27/01)" | doublet 1 and the boiler out all year: "365 days short, worst 30 MW, 111.668 GWh". My run of the real case (ESP plus one boiler unit, 20–27 Jan, op-1 A1) gives **8 days short, worst 8.24 MW**. |
| op-2 t12: "vom 1. bis 21. Dezember" | all year |

**Cause.** `parameters._failure` keeps the model's from/to only when they fall in a month the message names, and `named_days` knows "28 January", "Jan 28" and ISO only. So "coldest day", "peak day", dd/mm and German ordinals are dropped. "Back the next morning" (one day) has no duration pattern.

**Why it matters.** "On the coldest day" is *the* operator question. An all-year run answers a different question, with numbers 10–100 times too big.

**What to do.**
- Accept the reasoning model's ISO dates when the quote holds a date-like phrase.
- Map "coldest/peak day", "hottest day" and "peak week" to the demand file's own days (28 Jan, 19 Jul). That is data, not a phrase list: the model can name it as `"peak_heat_day"`.
- Show "all year (one unit out)" in red on the card when the message had a time phrase.

### Issue 4 (high): a planned maintenance window is treated as a failure, so the worst window is offered as the best

**Message (op-2 t14):** "I need a 10-day maintenance window to open and clean the heat exchanger plates. Which 10 days of the year are best, and what carries the town while it is out?"

**What happened.**
- Card: "the heat exchanger out 23 Jan-1 Feb (10 d, **the worst 10 days of the year (from 9 Jul it would be mildest)**)", extra cost 255 k€.
- Reply: "**The best 10-day window is 23 Jan to 1 Feb** … Demand on these days is low compared to the peak in January (30 MW)". The 30 MW peak day, 28 Jan, is inside that window.
- My run of 9–18 Jul: **0 GWh of extra gas**.

**Why it matters.** Planned work goes in the mildest window. Planning it over the peak day takes out the main heat source in the week the boiler bank is already at 2 of 3 units' worth.

**What to do.**
- Add a maintenance step that takes the mildest start. Code already computes it: `worst_start` returns both.
- Report what carries the town, and whether N-1 still holds during the window. With the exchanger out for maintenance, is a boiler-unit trip still covered?
- Offer a yearly maintenance calendar for every unit: exchanger, each train, each boiler unit, heat pump, chillers.

**Related bug (t05).** "heat pump out for a fortnight in January – which two weeks hurt most?" got "the worst 14 days between 1 Jan and 31 Jan (**from 1 Jan it would be mildest**)". The heat pump runs at a flat 2 MW all January, so every start ties. Say "any fortnight in January costs the same".

### Issue 5 (medium): a question changes the recommended plant, and design names collide

- **t04: "cheapest one, production pump down 1–14 Feb".** This started a fresh search (B1–B39) with `objective: cost`. The recommendation became "PICK cheapest (recommended): B1 · 1D-HP-AB": the plant **without** N-1, with 0.03 MW of spare. Two turns later "the recommended design" meant B1, and the reply quoted B1's 86 days short.
- **op-2 `edit` of A1 (boiler 24 MW).** It produced a design listed as **"A1 · U1"** (uid `A1`, code `U1`). Two designs now read "A1". U1 keeps `reliable: true`, flags `['ST','N1']` and the name "sized so that any one unit can be out (N-1)". By the agent's own card it fails the exchanger case by 3.4 MW. Asking about it (t21) ran a what-if **W1 · 2D-HP-AB-ST-N1** and another full search (B1…).

**Why it matters.** The operator must always know which plant is meant. A label "-N1" on a plant that is not N-1 is exactly the "backup boiler" problem from round 1.

**What to do.**
- A question that names a pick ("the cheapest one") refers to the existing pick and must not re-search or re-recommend.
- User designs get their own id (U1), not A1.
- Recompute `reliable` and the flags after an edit, and drop "-N1" when any case is short.

### Issue 6 (medium): wrong sizing case, and no cheaper redundancy than more boiler

**Message (op-2 t17):** "which single outage sets the 27.4 MW boiler size?"

**Reply:** "the failure of **one of the three boiler units**".

**The truth, from local runs of the same plant:**
- One boiler unit out leaves 18.3 + 14.46 + 2.6 = 35.3 MW, 5 MW of margin.
- The **heat-exchanger-out** case alone sets the boiler: 27.4 + 2.6 = 30.0. At a 20.3 MW boiler, every case except the exchanger is met.
- The exchanger case costs **+0.53 M€ of capital and +0.41 €/MWh** (52.87 against 52.33 M€; 73.31 against 72.90 €/MWh).

**Why it matters.** An operator covers a plate exchanger with two plate packs (2 × 60 %) or a spare plate set, not with 7 MW of extra boiler. A 4th boiler unit, which the agent suggests, buys nothing here.

**What to do.**
- Show the binding case on the card: "the boiler is sized by: the heat exchanger out".
- Add exchanger units (2 × 50 / 60 %) as a reliable-plan option, the way the separate trains already are.

### Issue 7 (medium): the spare ESP is under-sold, and its outage times are optimistic

**Under-sold.**
- t03 and t13 cards: the spare "saves 3.35 GWh (282 k€)" and "256 k€" per event, for **12.5 k€ a year**.
- Replies: "Given the short duration, the current plan is robust without immediate hardware changes"; "niet noodzakelijk"; costs "stijgen licht" (rise slightly). 258 k€ in three weeks is not slight.
- The card's green tag "No spare needed" sits next to a note saying the spare pays for itself 20 times over.

**Optimistic outage times.**
- Swap with a spare: 3 days, citing TNO. In my experience the bottleneck is getting a workover rig on site, then pulling and re-running ~670 m of tubing and cleaning up the well. With a spare in stock and no rig on contract, one to two weeks is typical.
- Without a spare: 30 days is the code's assumption. A new ESP has a lead time of months, not weeks.
- The "doublet (its producer or ESP)" outage also assumes the fault is the ESP. A spare ESP does not help with a tubing leak or a scaled well.
- Asked about this (t16), the agent asked me to clarify, after the claim check deleted two correct sentences: "only tracks how many days a unit is out" and "stays down until … repaired".

**What to do.**
- Rename the tag "Supply kept: no spare needed for heat" and state the spare's pay-back in words.
- Make the swap time and the no-spare time user inputs, defaulting to perhaps 10 and 90 days.
- Value the spare on expected failures per year (ESP run life), not on one event.

### Issue 8 (medium): the claim check and leaks (unchanged from round 1)

- **No claims step** on 14 of 22 answer turns (t02, t04, t06, t10, t11, t12, t13, t14, t15, t17, t18, t19, t20, t21), including the four most wrong replies (t04, t06, t11, t21).
- **Removed, though true:** t05 (all three sentences, every number on the card), t16 (the two correct sentences above), t23 (chiller loading).
- **"Understood" leaks:**
  - t12: "The user wants to correct the previous answer by removing invented numbers and sticking strictly to the provided context."
  - t22: "You want the response reformatted as JSON without inventing specific numerical values".
- **Other stray text:**
  - "[2D-HP-AB-ST-N1 operation]" left at the end of the op-2 design reply.
  - "used:" on its own line at the end of t03.
  - t23 shows its reasoning: "but the text says … however, the peak day description … explicitly states …".
  - An English question was answered in Dutch (t13), carried over from a Dutch turn two turns earlier.

### Issue 9 (medium): negative "extra" gas and cost on failure cards

**Cards:**
- Boiler out all year: "extra gas -46.687 GWh, CO2 -9389 t, cost **-3972 k€**".
- Double fault: "cost **-6,472 k€**".
- Chillers out: "-51.7 k€".

**Why.** When the failed unit is the one that burns gas or electricity, the year without it simply buys less, while 54 GWh of heat goes undelivered. On the card a failure then reads as a saving.

**What to do.** Show undelivered heat and cold as the cost (at the heat price or a penalty), and never show a negative "extra cost" for a failure.

### Issue 10 (low): operability gaps still open, stated honestly now

- **Boiler turndown.** The boiler fires on all 365 days (it burns the well gas). Each op-2 unit is 9.13 MW; the summer load is 0.82 MW (9 % of one unit), below 25 % of one unit on 168 days.
- **ESP starts.** Doublet 2 runs 104 days, then 1 day, 2 days, 35 days, 1 day, 18 days, 65 days: 6 starts.
- **Wording.** Asked about turndown, the reply implied "the general 25–30% rule" is applied (it is not), and called the boiler one that "fires only when needed" (it fires daily).
- **Stop windows** in the operations facts are still "stopped days 190–224".
- **"Backup boiler"** is still the name of a boiler that makes 49 % of the heat (op-1 A1).

## 4. What users in my role need most that is missing

| # | Need | Why it matters | Effort |
|---|---|---|---|
| 1 | **Unit and date reading tied to the design and the demand file.** "One boiler unit" means one of N; the "coldest / hottest day" comes from the data; accept the model's ISO dates; handle dd/mm and German/Dutch ordinals; "back next morning" means 1 day; and stop (not substitute) when the model flags `unsupported`. | Without it the reliable plan is reported as failing (issue 1) and day trips become year-long outages (issue 3). This decides whether the failure feature can be trusted at all. | Hours |
| 2 | **Failure replies bound to the card.** Code's `failure_text` leads; the model adds no numbers or verdicts; the claim check always runs; reject "not simulated" when a card exists. | 9 of 15 failure replies contradicted their card. | Hours to a day |
| 3 | **Maintenance planner.** The mildest window per unit (already computed), what carries the load, whether N-1 still holds during the window, and a no-overlap calendar for the exchanger, trains, boiler and chiller units, heat pump and doublets, with a handover overlap for the doublets. | Planned work is most of an operator's year. The current answer would schedule exchanger cleaning over the peak day. | A day |
| 4 | **Binding case and cheaper redundancy.** Show which outage sets each size. Offer 2 × 60 % plate exchangers or a spare plate pack, and a 4th boiler unit, next to "grow the boiler". | The op-2 plan carries 7 MW of boiler (+0.53 M€) only for an exchanger failure that an operator would cover otherwise. | A day |
| 5 | **Realistic ESP outage inputs and spare economics.** Swap time including the rig, no-spare lead time in months, ESP run life to get expected failures a year, and the spare valued per year. | The spare ESP is the cheapest reliability buy there is. The chat currently tells the operator it is not needed. | Hours to a day |
| 6 | **Two units out (N-1 plus maintenance, or a trip during an outage) as a first-class question.** The engine already takes several events; the gaps are reading and wording. | "What if a second unit trips while the exchanger is open?" is the real winter risk. | Hours |
| 7 | **Operability constraints.** Minimum load per boiler, heat pump and chiller unit; minimum run and down time per doublet with a start count; a dispatch mode where both doublets share flow (a warm standby); a small summer boiler or flare for the well gas. | Short-cycling boilers and 1-day ESP runs are where plants trip and wells fail. | Days |
| 8 | **Gas connection under N-1.** Peak bought-gas MW with a doublet out (its own gas disappears too), and a flare path for the produced gas when the boilers are down. | This sets the grid contract and connection, and tells whether the doublets must stop when the boilers do. | Hours |
| 9 | **Questions don't move the recommendation; ids are unique; "-N1" is recomputed after edits.** | The operator must know which plant is "the plant". | Hours |

## 5. What works

- **N-1 by default.** The recommended design is a reliable plan. The card shows the spare on the peak day and all seven one-unit-out cases, and it labels the cheapest plan's gaps ("5 of 6 cases short: doublet 1 9.2 MW heat on 28 Jan …"). Separate treatment trains were picked for the 2-doublet plan, as round 1 asked.
- **Honest failure runs.** Every failure I asked about was simulated, and the card says exactly what was run, including "the worst 42 days of the year (from 9 Jul it would be mildest)". Remedies come with capital and €/MWh: "6.4 MW more boiler (27.2 MW in all): 0.48 M€, 50.1 k€/yr". Where the unit and the date were read right, the numbers matched my local reruns.
- **Dates in many forms.** "from the 10th to the 24th of Jan", "1–14 Feb", "3 t/m 9 februari", "2027-12-01" and "for a fortnight in January" all landed on the right days.
- **The day tool.** The 19 July snapshot was right to the decimal and gave the stop window as dates. This was round-1 issue 3.
- **"Not modelled" said plainly.** Asked about starts and ramping, it said "does not model hourly peaks, start-ups, or ramping" instead of inventing a schedule, as it did in round 1.

Evidence (scratchpad):
- turn transcripts: `scratchpad/panel2/op/t01.txt` to `t23.txt`
- local reruns: `scratchpad/panel2/op/n1.py`, `n1b.py`, `n1c.py`, `n1d.py`
- workbench snapshots: `scratchpad/panel2/op/wb_op1.json`, `wb_op1b.json`, `wb_op2.json`, `wb_op2b.json`
