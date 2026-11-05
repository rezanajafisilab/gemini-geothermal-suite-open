# Operator review: Dioscuri, a year of plant operation

Role: operator of a geothermal district heating plant (daily dispatch, maintenance windows, trips and restarts, minimum flows, boiler backup, the control room). Server http://127.0.0.1:8791. Threads `ops-1` and `ops-2`: 19 chat turns, plus 3 user designs made with `edit`. The daily numbers below come from the chosen design's year series, which I read from the local workbench endpoint because the CLI strips it. I checked them with the model's own formulas: my rebuild of the gas balance matched the model exactly (14.27 GWh bought, 17.88 GWh of produced gas burned).

The design under review is **2D-HP-AB**: 2 doublets at 2,500 m, a 14.46 MW heat exchanger, a 3.9 MW heat pump, an 11.7 MW boiler, a 1 MW absorption chiller and 9 MW of electric chillers. Its costs are 64.25 €/MWh of heat and 50.08 €/MWh of cold, with 43.2 M€ of capital.

## 1. Verdict

As a design study, the plant is sound and well documented. I would still not approve it for operation, and I could not run it from what the chat tells me.

- **No margin and no N-1.** On the coldest day there are 30.06 MW of capacity against 30.00 MW of demand. If one doublet trips, the town is up to 7.2 MW short on any of 70 winter days. The "backup boiler" is really the peak boiler: it runs at 99.5 % on 28 January.
- **The chat cannot see the daily schedule.** Most of the day-level answers I asked for were wrong or missing: November dispatch, 19 July, the stop dates, a shift plan.
- **The trip answer flips.** On the question that matters most, "do we hold supply after a trip?", two wordings got opposite answers, and one of them was confidently false.

The fixes are cheap. A 19 MW boiler gives N-1 on the doublets for +0.52 €/MWh of heat. The daily data already exists in the year model; the chat just cannot reach it.

## 2. What works

- **The year model can be audited.** The daily energy balance is off by 0.0000 % and there are 12 named checks. The daily series (MW per unit; flow, wellhead and reinjection temperature per doublet) makes physical sense. I rebuilt the gas balance from the flows and the boiler output and matched the model to the decimal.
- **The inputs card is clear and honest.** Every assumed value has its source: the 60 °C return, the heat capacity of 3,990 J/(kg·K), the reading of "330 days", the prices. An approval panel needs exactly this.
- **The stop windows are in the right season.** They are placed in the quietest blocks of brine demand and staggered, so the two doublets are never down together.
- **The tools behind the chat work.** "Lead-lag" was mapped to `dispatch: base` and simulated correctly: +0.7 €/MWh and +0.49 GWh a year of pumping. With `edit` I tested N-1 by hand in a minute. The Compare list says why each layout lost, for example "+0.29 M€ for a treatment train per doublet".
- **It can state a limit plainly.** In `ops-1` it said: "The design cannot guarantee 100 °C supply if doublet 1 trips … it does not have extra capacity to replace the lost brine heat." Keep that tone, and make it consistent (issue 2).

## 3. Issues

### Issue 1 (high): no N-1 and no margin; the "backup boiler" is the peak boiler

**What I did.** In `ops-1` I asked two things:
- "28 January is the coldest day, 30 MW. Break it down for the control room: MW from the heat exchanger, heat pump and boiler, the flow on each doublet, and how many MW of spare capacity I have left."
- "I would not sign off a plant that loses supply when one doublet trips in winter. Re-size it so the coldest day is still met at 100 °C with either doublet out (N-1 on the doublets), and tell me what that costs extra per MWh."

**What happened.**
- The peak-day reply gave the exchanger (14.46 MW), the heat pump (3.9 MW) and both doublets at 300 m³/h. It gave no boiler figure and no answer on spare capacity. The data: 14.46 + 3.90 + 11.64 (of 11.70) = 30.00 MW, so **0.06 MW spare**.
- On re-sizing it said: "I cannot re-size the plant to guarantee N-1 reliability on the coldest day because my plant model does not support simulating single-doublet failure scenarios … I would need you to adjust other parameters, such as:". Nothing followed: the claim check had removed all three bullets.

**What I found with `edit`.**
- **U1, the same plant with one doublet:** short of 100 °C on **70 days** (31 in January, 14 in February, 25 in December). The worst day is **28 Jan, 7.17 MW short (24 %)**. Cooling is 1 MW short on 9 summer days.
- **U2, one doublet and a 19 MW boiler:** heat is met on every day.
- **U3, two doublets and a 19 MW boiler:** passes every check. Heat costs **64.77 against 64.25 €/MWh (+0.52)**; capital is **43.78 against 43.23 M€ (+0.55)**.

**Other single points of failure, from the daily data:**
- **Boiler trip on 28 Jan:** 11.6 MW short. On 110 days a year, demand is above what the exchanger and heat pump can give.
- **The one shared treatment train and exchanger out:** the town is short on **182 days**, worst 18.3 MW. The heat pump has no source without the brine.
- **Cooling on 19 Jul:** the chillers run at 9.0 of 9.0 MW and the absorption chiller at 1.0 of 1.0 MW. On all 9 days above 9 MW of cooling, only one doublet runs, so a trip of that doublet leaves cooling 1 MW short.
- **The "backup" label:** the boiler makes 27.4 % of the year's heat, fires on all 365 days and runs at 99.5 % on the peak day.

**Why it matters.** Supply security is the first thing an operator and a heat company sign off. This plant loses 24 % of supply when one ESP trips in January and has no margin for the morning peak, so it would not pass an operations review. Calling the boiler "backup" tells the panel there is redundancy when there is none.

**What to do instead.**
- Add an N-1 rule to the verifier and the improve loop. Take the largest unit out: a doublet together with its produced gas, the largest boiler unit, or the shared treatment train. The peak day must still be met; otherwise the reply must say how much short and on how many days.
- Put "spare MW on the peak day" and "N-1: met / short X MW on Y days" on the result card.
- Call the boiler a peak boiler unless it is sized for N-1.
- Rank separate treatment trains (2D-HP-AB-ST: +0.29 M€, +0.1 €/MWh) for what they buy. The shared train is the one failure that takes out both doublets.

### Issue 2 (high): the trip answer flips with wording, and one version is false

**What I did.**
- In `ops-1`: "Say doublet 1 trips on the ESP at 6 am on 28 January and stays off for three days. I know the model may not do failures, but tell me straight: is the backup boiler big enough to hold 100 °C supply, and if not how many MW short am I and for how many days of the winter would a single trip leave me short?"
- In a new chat, `ops-2`: "Cold snap at the end of January and we lose one production pump. Do we keep the town warm, and if not by how much do we fall short?"

**What happened.**
- **ops-1:** "The design cannot guarantee 100 °C supply if doublet 1 trips". The direction is right, but it gave no MW and no day count. Its guard stripped a number the model had worked out ("removed sentences with numbers no source gives (18.36)"; 18.36 is the exchanger plus the heat pump). The reply ended with an unrelated "The full-load hours of the doublet is 3,007 h a year."
- **ops-2:** "**covers 100% of heating demand even if one production pump is lost.** The backup boiler and the remaining doublet supply enough heat to meet the peak of 30 MW on 2027-01-28." The intake had marked the question `relevant: false`. The claim check removed "Yes, the town remains warm." but kept the two sentences that say the same thing.

**Why it matters.** This is the safety question. The true answer is 7.2 MW short on 28 Jan and short on 70 days. A control room or approver told "covers 100 %" plans no contingency: no extra boiler, no margin in the gas contract, no load-shedding plan.

**What to do instead.**
- Send any question about a trip, failure, outage or lost pump to a fixed "unit out" run: the year re-run with that unit unavailable for the stated window, or for the whole winter. The answer must quote that run's numbers.
- When no run is possible, the only allowed answer is "not modelled", never a coverage claim.
- Add an evaluation scenario with three wordings of the trip question that must all give the same answer.

### Issue 3 (high): the chat cannot see the daily schedule, so day-level answers are made up

The table quotes my messages from `ops-1`; the data column is the design's year series.

| My message | Reply | Data |
|---|---|---|
| "How do I dispatch the two doublets day to day? On a normal November day which doublet runs, at what flow, and do they swap lead so they wear evenly?" | "doublet 1 runs first … while doublet 2 is idle … This ensures even wear without daily swapping." | Both doublets run on all 30 November days, for example 181/181 m³/h on 1 Nov. Doublet 1 runs 330 days and doublet 2 226 days (1.68 against 1.13 million m³ of brine), so wear is not even. |
| "Give me the dates, not day numbers: when does each doublet come off for its 35 days, why those weeks …" | "the exact weeks are not defined in the available data" | The design has them: doublet 1 is off 9 Jul to 12 Aug, doublet 2 26 May to 29 Jun. One turn earlier the agent itself had quoted "days 190–224" and "146–180". |
| "What is running on 19 July, the hottest day? Which doublet, what flow, what does the boiler do, and how close are the chillers to their limit?" | "doublet 1 runs at its cap of 300 m³/h while doublet 2 is idle", plus yearly gas totals and "absorption 19.9 % … electric chillers 80.1 %" | Doublet 1 is in its stop. Doublet 2 runs at 136.4 m³/h and the boiler gives 0.82 MW. The chillers run at 9.0 of 9.0 MW and the absorption chiller at 1.0 of 1.0 MW: a 10/90 split on the day, with no margin. |
| "Make me the shift plan for 25 to 31 January as a table …" | It fell back (`fallback: true`) to "GEMINI_Heating_Demand_Daily_2027.csv has 365 rows …" | The table exists, for example 28 Jan: 30.00 MW = 14.46 + 3.90 + 11.64, both doublets at 300 m³/h. The model's own figures were invented (only 11.64 was right), so the guard was right to block them. |
| "Give the control room an operating envelope for the chosen design …" | "flow range 50–300 m³/h … wellhead 86.1 °C and reinjection at 56 °C." The claim check removed a correct sentence on ESP head (33 bar) and injection pressure (23 bar). | Design: ESP head 32.8 bar and injection 22.6 bar at full flow; wellhead 85.0 to 86.1 °C; reinjection 56.0 to 65.2 °C. No alarm limits were given. |

**Why it matters.** Operators work in days and hours, not in yearly averages. These are the first questions a shift supervisor or an approver asks, and the wrong answers are confident and specific: the wrong doublet, the wrong flow.

**What to do instead.**
- The cause: the answerer's context holds only yearly figures and "each doublet stops 35 days a year, staggered" (`answer.py`). `lookup.py` has about 25 fixed facts, none of them for a date.
- Add a tool for a day or a date range. It should read `year.daily_mw` and each doublet's `flow_m3h`, `on`, `wellhead_c` and `reinjection_c`, give the stop windows as calendar dates, and offer standard rows for the coldest and the hottest day.
- Let the claim check verify day-level numbers against that tool.

### Issue 4 (high): answers invent equipment and unsafe practice

**What I did and what happened.**
- **Minimum flow.** I asked: "Does the running doublet drop to its 50 m3/h minimum then? If the minimum gives more brine than the network takes, where does that heat go?" Reply: "Yes … drops to its 50 m³/h minimum … the excess heat is managed by the plant's thermal storage or rejected via the backup boiler's controls". In fact the design has no storage, and a boiler cannot reject heat. The lowest running flow all year is 136.4 m³/h, because the absorption chiller needs brine too. The extra brine simply goes back into the ground warmer (65.2 °C on 1 June).
- **Produced gas.** I asked: "What happens to the gas that comes up with the brine when the boiler is off for service or trips: do we flare it, or do we have to shut the doublets in?" Reply: "Produced gas is stored in a buffer tank … excess gas would be vented safely per safety protocols". The design has no tank and no flare, and venting a gas that is 80 % methane is not acceptable practice. The same reply said: "The total gas consumed by the boiler is 17.9 GWh/yr, with the remainder produced by the wells". That is wrong: the boiler burns 17.9 GWh of produced gas plus 14.3 GWh of bought gas, 32.2 GWh in all.
- **Service windows.** I asked: "When do I open the exchanger to clean the plates, or service the boiler and the heat pump, and what carries the town while they are out?" Reply: "would typically occur during the staggered 35-day shutdowns of each doublet … During these periods, the backup boiler covers heating needs". But during those windows the other doublet still runs through the one shared exchanger, and the boiler cannot be serviced and carry the load at the same time.
- **Morning peak.** I asked: "How does the plant cover the morning peak with no margin left?" Reply: "by sizing the heat exchanger for 14.46 MW, which exceeds the daily average of 30 MW". 14.46 does not exceed 30.

**Why it matters.** An operator who trusted these answers would plan around equipment that does not exist, or would vent methane. That is worse than "I don't know".

**What to do instead.**
- Check every piece of equipment a reply names against the design's component list (the graph). Remove or flag the rest: storage, buffer tank, flare.
- Give the answerer an explicit list of what is not in the design or not modelled (storage, flare, trips, hourly peaks, start-ups, unit counts), so it says so instead of filling the gap.
- Never let "vent" through for produced gas.

### Issue 5 (medium): the claim check removes correct operating data and keeps wrong claims; padding

- **Removed, though correct:**
  - "At full flow (300 m³/h), the ESP head is **33 bar** and injection pressure is **23 bar**" (the design has 32.8 and 22.6).
  - "The total pump power is **4.6 GWh/yr**, and the cost of heat is **65 €/MWh**" (the lead-lag design has 4.62 GWh and 64.99 €/MWh).
  - "On 28 January, the plant meets the 30 MW demand using the shared heat exchanger, heat pump, and boiler."
- **Kept, though wrong:** the 19 July reply (3 claims checked, 0 removed), the November reply (5 checked, 0 removed) and the ops-2 trip reply.
- **Broken text left behind:** "such as:" followed by an empty list (issue 1).
- **Padding:** "The full-load hours of the doublet is 3,007 h a year." was added to four answers that had nothing to do with it. Capital cost and €/MWh were added to the maintenance and approval answers.
- **Leaks in the "Understood" row**, which the chat shows (`StepsGroup.tsx`). It displayed internal retries: "You want me to correct my previous answer by removing invented numbers …", "You want the JSON response with specific values from the draft.", "I will remove the invented alarm limits …".

**Why it matters.** The control room loses the numbers it needs (the pressures) and keeps the ones that are wrong. The padding buries the answer.

**What to do instead.**
- Check claims against the full design record (doublet summary, daily series), not only against the short context.
- Drop the "added back" step for values the question did not ask for.
- When a list loses all its items, remove the sentence that introduces it.
- Fill "Understood" only from the first intake pass.

### Issue 6 (medium): daily steps hide the morning peak, starts and turndown, and no check covers them

**What I did.**
- In `ops-1`: "Your year is in daily steps. The 30 MW on 28 January is a daily average, so the 7 am peak hour will be well above that. How does the plant cover the morning peak with no margin left? And in April doublet 2 starts and stops several times for one or two days at a time: how many ESP starts a year does your schedule need, and would you really run it that way?"
- In `ops-2`: "Your boiler is one 11.7 MW unit but in summer it only fires about 0.8 MW … Should it be split into smaller units …?"
- Then I sent the agent's own suggestion back: "Run a design with three 4 MW boilers instead of one 11.7 MW unit."

**What happened.**
- **Morning peak.** The reply was the "14.46 MW, which exceeds the daily average of 30 MW" quoted in issue 4. Capacity is 30.06 MW against a daily mean of 30.00 MW. Suppose the peak hour is 1.2 times the daily mean (my assumption; the demand file is daily): the plant is then about 6 MW short at the peak hour on 29 days. At 1.1 times it is 2.9 MW short on 5 days; at 1.3 times, 8.9 MW on 63 days. The search never tries a storage tank.
- **ESP starts.** Reply: "The schedule does not require stopping and starting the ESP multiple times … the doublet operates continuously when needed". The data says doublet 2 starts 7 times a year, including one-day runs on 16 Apr and 1 Oct and a two-day run on 18–19 Apr. In lead-lag mode it also sits at the 50 m³/h minimum on 44 days.
- **Turndown.** The boiler fires every day, because it burns the gas that comes up with the brine. It runs below 10 % of its 11.7 MW on 115 days; the lowest is 0.82 MW, or 7 %. The heat pump drops to 0.51 MW (13 % of 3.9 MW) and is below 25 % on 81 days. A single unit of either cannot run that low.
- **Unit count.** The agent had suggested three 4 MW boilers. When I sent that back, it dropped the change ("boiler_mw=12: its number is not in the quote") and repeated the old design. The model has no unit count.

**Why it matters.**
- ESP starts after short stops are where wells and pumps fail: thermal cycling, scaling, sand.
- A boiler that cannot turn down that far short-cycles or trips on flame failure, and the well gas then has nowhere to go.
- A design sized on daily means with zero margin will be short every cold morning.

**What to do instead.**
- Add a peak-hour factor (or let the user give one), and a small hot-water store as a search option.
- Add a minimum run time and minimum down time for doublets (for example 7 days), and count starts per doublet.
- Give boiler, heat pump and chillers a unit count with minimum loads, for example a small boiler for the summer well gas.
- Add a check for each of these.
- Do not suggest changes the model cannot run.

### Issue 7 (medium): the stop windows are in the right season, but the handover is not workable

**What happened.**
- **The stops:** doublet 1 is off 9 Jul to 12 Aug, doublet 2 26 May to 29 Jun.
- **Doublet 2's stop proves nothing.** It sits entirely inside an 80-day idle spell (20 Apr to 8 Jul), so it costs nothing and tests nothing.
- **No overlap at the handover.** Doublet 2 restarts on 9 Jul, the same day doublet 1 goes down, after 80 days idle. If it fails to restart, there is no geothermal heat for 35 days and the absorption chiller is lost at the cooling peak.
- **No service windows for the rest:** none for the shared exchanger and treatment train, the boiler (fires 365 days) or the heat pump (365 days).
- **Wrong reason given.** Asked for the dates and the reason, the agent said the weeks are "not defined" and that the stagger is "to ensure even wear". The code picks the weeks that need the least brine.

**What to do instead.**
- Start the standby doublet several days before the other one stops, and show the overlap.
- Plan the window for the shared train and exchanger when the boiler and chillers alone can carry the town. Late May works (heat at most 5.1 MW, cooling at most 5.3 MW), and so does September (8.5 MW and 6.1 MW), against an 11.7 MW boiler and 9 MW of chillers. The doublets' own gas stops during that window, so the boiler runs on bought gas.
- List the service windows for the boiler and the heat pump.
- Give dates, not day numbers, everywhere.

### Issue 8 (medium): gas dependence and the gas connection are not explained

**What I did.** "How much gas do I have to buy from the grid in a year, and in the coldest week? …"

**What happened.** The reply gave 14.3 GWh/yr and nothing for the coldest week. From the data:
- **Bought gas:** 12 % of the heat. 71 % of it falls in December to February (10.2 GWh), 1,134 MWh in 25–31 January, with a peak of 8.4 MW on 28 January.
- **Produced gas:** 17.9 GWh/yr, all burned, none flared.
- **Trip case:** if a doublet trips on 28 January and the boiler is sized for N-1, bought gas rises to about 18 MW, because the tripped doublet's own gas (about 1.9 MW) disappears as well.

**Why it matters.** The trip case, not the normal peak, sets the gas grid connection and the contract capacity. The produced gas needs a path for start-ups and boiler outages (a flare); otherwise the doublets must stop whenever the boiler does.

**What to do instead.** Report bought-gas peak MW in normal and N-1 operation and the coldest-week volume, and include a flare for the produced gas.

### Issue 9 (low): smaller faults

- **"Operable" was ignored.** "Lowest cost, but it has to be operable" (`ops-2`) changed nothing: same design, same sizes.
- **The lead-lag reply contradicted its own run.** The what-if ran correctly, but the reply opened with "The current design [2D-HP-AB-BL] uses a 'hottest first' (base) strategy, not the 'lead-lag' configuration you requested", which denies what it had just run. The result card names the design "how doublets share the brine: equal shares, or the hottest first: base", a parameter description pasted in as a name.
- **The approval answer missed the operating gaps.** I asked what the model does not cover. It named reservoir breakthrough, price volatility and maintenance schedules, but none of the gaps above, and padded the answer with "capital cost is 43.2 M€, CO₂ saving is 60.4 % …".

## 4. Implement differently or remove

- **The dispatch rule.** Both modes hard-code "the fewest doublets that carry the brine". So doublet 1 always leads (330 days) and doublet 2 cycles (7 starts). That contradicts the label "equal shares (the least pumping)": pump power rises steeply with flow, so two doublets at half flow pump less than one at full flow.
  - Add a mode in which every available doublet shares the flow. Each still runs at most 330 days, within the cap.
  - From the model's own pump curve I estimate about 0.4 GWh a year less pumping (about 10 %; this extrapolates the curve below 136 m³/h). Doublet 2's starts fall from 7 to about 2, and a running doublet is a warm standby that can take more flow when the other trips.
  - If the fewest-doublets rule stays, rotate the lead doublet.
- **"Backup boiler"** should be "peak boiler", unless it is sized for N-1.
- **Separate treatment trains** should be ranked on what they add to availability, not on cost alone.
- **Remove the padding.** Drop "added back from the checked answer" for values the question did not ask for, and keep internal retry text out of "Understood".
- **Stop windows as dates** (9 Jul to 12 Aug) everywhere, not "days 190–224".
- **Reviewer access to the year.** `panel.py design … year` strips the daily series and the per-doublet flows (it prints `"doublets": [{}, {}]`), so a reviewer has to read the workbench endpoint directly. A `year-day <date>` or `year-csv` command would help reviewers, and would help the team test the day tool.

## 5. Top 3 priorities before the deadline

1. **An N-1 check and a "unit out" what-if.** Take out a doublet with its gas, the biggest boiler unit, or the shared treatment train. Build it into the verifier and the improve loop, and show "spare MW on the peak day" and "N-1 met / short X MW on Y days" on the result card. Route every trip or outage question to it, so the answer cannot flip with wording. The 19 MW boiler test shows the fix costs about +0.5 €/MWh of heat. The team's own spare-equipment note already proposes this check.
2. **A day and date tool for the answerer** over the year series: MW by unit, flow and temperatures per doublet, stop windows as dates, the coldest and hottest day, a week table. Check claims against this tool and against the design's component list. Then the chat stops inventing storage, buffer tanks and venting, and stops deleting correct pressures.
3. **An operations summary for each design:**
   - the dispatch rule in words;
   - stop windows with handover dates, and starts per doublet;
   - boiler and heat pump minimum loads against their turndown;
   - bought-gas peak in normal and N-1 operation, and the margin on the peak day;
   - an explicit "not modelled" list: hourly peaks, trips, start-ups, storage, flare.

   If time allows, add a peak-hour factor or a storage option to the search.

Evidence files (scratchpad):
- `analyse.py` (a scratch script, not kept) (daily dispatch analysis)
- `fetch.py` (a scratch script, not kept) (read-only workbench fetch)
- saved workbench snapshots `wb_ops1*.json` in the same folder.
