# Review: district heating and cooling engineer

Server: http://127.0.0.1:8790. Threads: `dhc-1` (design, what-ifs, edits U1-U6) and `dhc-2` (questions). 19 chat turns, 4 sensitivity runs, 6 edits. I checked the numbers with Python against `src/dioscuri_plant/` and the workbench JSON. My scripts are in `scratchpad/dhc/`.

## 1. Verdict

The plant model is honest arithmetic. Daily heat and cold balances close. The brine heat counted at the wells matches the heat used in the plant. The heat pump, chiller and absorption COPs follow the formulas in `components.py`, and I could reproduce them by hand.

What a district energy utility would reject is the firm capacity:
- The "backup" boiler is not a backup. The plant fails the N-1 test (lose any one major unit) and sits exactly on the daily-mean peak, with no margin for the hourly peak, a warmer return or demand growth. Each of these costs less than 1 €/MWh to fix.

The network side is missing:
- No network heat losses and no distribution pumping.
- No free cooling at a 20 °C chilled-water supply. That is the first thing a district cooling engineer would build.
- The 25 °C cooling-return assumption has no effect on any output.

The agent's explanations in my field are often wrong or deleted. It misstated how its own boiler is dispatched and what the cooling return does. The claim checker passed those errors and deleted correct answers instead.

## 2. What works

- **Energy balances are clean.** Chosen design 2D-HP-AB: worst daily heat error 0.001 MW, cold 0.000 MW.
  - Brine heat counted at the wells (flow × ρ·cp × (wellhead − reinjection)) is 82.390 GWh. Heat used in the plant (exchanger 57.884 + heat-pump source 18.204 + absorption drive 6.303) is also 82.390 GWh. Worst day differs by 0.006 MW.
  - Produced gas checks out: 2,809,613 m³ × 0.8 × 0.8 × 35.8 MJ/Nm³ = 17.88 GWh, as reported. The boiler's fuel and heat give 0.95.
- **COPs reproduce by hand.**
  - Heat pump on 28 Jan: brine leaves the exchanger at 65.0 °C, the evaporator takes it to 60.5 °C, giving COP 4.72 (model 4.73). Annual COP 4.61, daily range 4.24-5.37.
  - Chillers: 0.5 × 291.15 / (35 − 18) = 8.56.
  - Absorption: 2.33 MW rejected per MW of cold, which feeds the cooling-tower electricity.
- **The plant topology is sound for a 100 °C network fed by 86 °C brine:**
  - balanced counterflow exchanger;
  - heat pump on the exchanger outlet;
  - 40 K cap per doublet;
  - absorption on brine that bypasses the exchanger;
  - produced gas burnt first. That is correct economics: the gas must be burnt or flared anyway.
- **Return-temperature what-ifs work in chat.**
  - Message: "What happens to 2D-HP-AB if the heating return comes back at 68 °C … and the cooling return at 28 °C?"
  - Reply: "fails on **39 days**, with the worst shortfall being **5.42 MW** on 28 January". It then re-sized the plant (heat pump 6.5 MW, boiler 14.6 MW, 65.6 €/MWh).
  - The Design tab edit is fast and good for N-1 tests.
- **Assumptions are visible, and the agent admits its limits.** The inputs card shows the 60/25 °C returns as assumed, and the agent said plainly that it sized for daily means. Keep both.

## 3. Issues (most important first)

### 3.1 HIGH: the "backup boiler" is not a backup; the plant has no firm capacity (N-1)

**What I did.** I asked: "You call the 11.7 MW boiler in 2D-HP-AB a backup. If one doublet's ESP fails on 28 January, or the heat pump trips, can the plant still supply 30 MW at 100 °C? What would N-1 security of supply cost?"

**What happened.**
- The agent replied: "No, I cannot calculate the N-1 security of supply cost … My plant model does not have inputs to simulate these specific component failures." It still said it "relies on a backup boiler (11.7 MW) and two doublets to meet the 30 MW peak". A unit you rely on for the peak cannot also be the backup.
- Reworded in the tool's terms ("keep … the heat pump, boiler and chillers exactly as they are but with only one doublet"), it found "short by **7.17 MW**". It then said: "To cover this peak with a single doublet, the backup boiler must be sized at **11.7 MW**. This matches the current design's boiler capacity."
- That is wrong: 11.7 MW is what leaves the 7.17 MW gap. About 18.9 MW is needed. The claim checker removed nothing.

**My edits (Design tab):**

| Edit | Heat short | Worst day | LCOH €/MWh |
|---|---|---|---|
| Base, boiler 11.7 MW | none | none | 64.25 |
| One doublet lost (U1) | 70 days | 7.17 MW, 28 Jan | 64.96 |
| Heat pump lost (U2) | 39 days | 3.85 MW | 67.20 |
| Boiler 19 MW (U3) | none | none | **64.77** |
| Boiler 19 MW, one doublet lost (U4) | none | none | 66.34 |
| Boiler 19 MW, no heat pump (U5) | none | none | 67.87 |

U4 is short only on the cold side: on its stop days the single doublet cannot drive the absorption chiller.

**Why it matters.** N-1 on the heat peak is the first question a heat utility or lender asks. ESP failures are the most common doublet outage. Full N-1 cover costs **+0.52 €/MWh of heat** (+0.55 M€ capex), so leaving it out saves nothing and fails the review. The cooling side has the same gap: 9 MW chillers + 1 MW absorption = exactly the 10 MW peak, with no spare unit. An N+1 chiller (13 MW) costs +4.76 €/MWh of cold (U6).

**Fix.**
- Add an N-1 check to `verify`: rerun the peak day with each unit out (largest doublet, heat pump, largest boiler or chiller) and report the unserved MW.
- Size the boiler so the peak is met with the largest heat unit out.
- Stop calling an undersized boiler a "backup"; call it "peak boiler" until it passes N-1.

### 3.2 HIGH: sized to the daily-mean peak, with no margin

**What I did.**
- Message: "The 30 MW heat peak and the 10 MW cold peak are daily means … Is 2D-HP-AB sized for the hourly peak, and if not, how much extra boiler, chiller or storage would you add?"
- Sensitivity runs on heat return and heat demand.

**What happened.**
- The reply was honest ("sized for the **daily mean** peaks"). But the claim checker removed the remedies ("A larger boiler and chillers…", "Thermal storage tanks charged during off-peak hours."). What was left reads "To cover hourly spikes above these means, you would need:" followed by nothing. The table then said "Larger (unknown)".
- The turn also re-ran the whole search (35 layouts, 280 sizings) for a question that needed none (80 s).
- Sensitivity on the design: heat demand ×1.1 gives 1 violation; heat return 63.75 °C gives 1 violation (the 70 °C case falls to 46 % CO₂ saving).
- So **+10 % demand or a return 4 K warmer breaks the design**. Return-temperature creep is the most common fault in a real network.

**Why it matters.**
- Typical design-day ratios of hourly peak to daily mean are about 1.1-1.3 for heat and 1.3-1.6 for commercial cooling. The organisers also say the profiles "include … short demand excursions".
- The brief asks for a daily balance, so daily resolution is acceptable. Capacity equal to the daily-mean peak is not.
- The demand file is smooth (the 30 MW day sits in a cold spell, only 152 MWh above the 99th percentile), so the daily data cannot show the margin needed.

**Fix.**
- Add a peak factor (an assumption with a sensitivity range) applied to firm capacity: boiler and chillers.
- Optionally add a diurnal storage tank. Note that at ΔT 5 K a chilled-water store holds only about 5.8 kWh/m³.
- A 19 MW boiler covers N-1 and a 1.2× hourly heat peak together: 14.46 + 3.9 + 19 = 37.4 MW, more than 36 MW.

### 3.3 HIGH: explanations of the plant's own physics are wrong, and the claim checker keeps the errors while deleting correct text

Five examples:

**a) Summer boiler.**
- Message: "In 2D-HP-AB the boiler runs on all 365 days, about 0.7 GWh a month even in June to August … Why is the boiler on in summer instead of the heat pump, and what share of the heat could the geothermal exchanger ever give with a 100 °C supply?"
- The reply went to the `file` step: "GEMINI_Heating_Demand_Daily_2027.csv has 365 rows … (fallback: true)". It did not answer.
- Reworded ("Why does the gas boiler … keep firing through the summer months?"), it invented reasons: "provides backup heating … on very cold days that might occur late in the season", "the system prioritizes cooling". All 8 claims passed.
- The real rule (`year.py`): the produced methane is burnt in the boiler first, ahead of the heat pump. The agent's own template states it: "the boiler burns the produced gas first (17.9 GWh/yr)".

**b) Cooling return.**
- Message: "What exactly does [the 25 °C cooling return] change in 2D-HP-AB's results?"
- Reply: "used … as the sink temperature for the chillers … directly sets the heat rejection point"; "A lower return temperature (easier heat rejection) improves the COP"; "Pumping: The impact is negligible; pumps move fluid, not heat"; "gas usage for absorption chillers"; "If the return were higher (e.g., 30 °C), the COP would drop".
- Every statement is wrong:
  - the chilled-water return is on the evaporator side, not the rejection side;
  - the absorption chiller burns no gas;
  - in district cooling the return mainly sets network flow and pumping;
  - the model never reads `cool_return_c`, and the sensitivity run shows LCOE 61.77 at both 23 and 30 °C.
- 9 claims checked, 0 removed.

**c) Geothermal share.**
- Message: "Only about 52 % of the heat … comes straight from the geothermal exchanger. What limits that share?"
- The draft blamed "the daily heating demand peak (30 MW) combined with the reservoir's cooling cap". The checker deleted it and fell back to a stock design description that does not answer.
- Correct answer: the exchanger can only lift the network from 60 to 81.1 °C, so (86.1 − 5 − 60)/(100 − 60) = **52.75 %**. A third doublet does not raise it. A colder return does: 45 °C gives 66 %.

**d) Free cooling and condensing.**
- Reply: "the condensing temperature is determined by these network conditions [20/25 °C] plus the cooling tower approach".
- The code fixes condensing at 35 °C (`chiller_condensing_c`). The 20/25 °C water is on the evaporator side.

**e) Heat pump technology.**
- The checker removed both sentences that answered "is 100 °C realistic / which refrigerant / does 1.2 M€/MW cover it". Three sentences were left.
- The removed text was itself partly wrong: CO₂ heat pumps suit cold returns, not 60 °C.

**Why it matters.** The challenge asks the agent to "explain every major engineering decision". Here the plant-side explanations are the weakest part, and the claim checker gets it backwards: it lets fluent nonsense through and deletes correct qualitative engineering.

**Fix.**
- Put a short, fixed "plant rules" fact sheet in the answer context, generated from `year.py`: dispatch order, produced gas first, the exchanger-share formula, which inputs feed which units, and that `cool_return` currently feeds nothing.
- Make the claim checker test statements about model behaviour against that sheet, not only numbers.
- Never replace a direct answer with the stock design template.

### 3.4 MEDIUM-HIGH: network losses and distribution pumping are missing; the demand boundary is invented

**What I did.** Message: "Is the 111.67 GWh heat demand measured at the customers' substations or at the plant? … The cooling network at a 5 K difference moves about 1,700 m3/h at the 10 MW peak."

**What happened.**
- Reply: "measured at the customers' substations, as per the challenge's input files". The requirements PDF does not say where demand is metered; I read its full text.
- By that answer, the plant is undersized, because no losses are added.
- It then "corrected" me: "not 1,700 m³/h … approximately **4,000 m³/h**". The correct figure is 10 MW / (4.18 kJ/kg·K × 5 K) = **1,720 m³/h**.
- The formula came out garbled ("rac{P}{ho c_p imes ext{diff}}"): the `\f`, `\r` and `\t` in the LaTeX were read as escape characters.
- No claims step ran on this turn.

**Why it matters.**
- Losses of 10-15 % (about 1.5 MW, nearly constant) would make the plant fall short. Heat demand ×1.1 already breaks it.
- In summer, losses are a large share of a 3.5 MW load.
- Cooling-network pumping at ΔT 5 K is about 0.3 MW at peak, roughly 15-20 % of the chiller electricity. That pumping is the only thing the cooling-return assumption would drive.

**Fix.**
- State the boundary as an assumption: "demand at the plant fence, losses included". Add a loss-factor sensitivity.
- Add network pumping for both networks: flow from ΔT, a head assumption, the cube law.
- Until then, take `cool_return` out of the inputs card and the sensitivity menu, or label it "no effect in this model".

### 3.5 MEDIUM: no free cooling at a 20 °C chilled-water supply; chillers at a fixed 35 °C condensing all year

**What happened.** Reply: "No, the 2D-HP-AB design does not use free cooling." The chiller COP is 8.56 on every one of its 175 days.

**Why it matters.**
- With 20/25 °C water, a plate exchanger on the towers that already exist gives full free cooling when the wet-bulb is below about 13-14 °C, and partial pre-cooling of the 25 °C return up to about 19 °C wet-bulb.
- My estimate, from De Bilt monthly normals and not modelled: free cooling covers about 40-60 % of the 23.7 GWh of cold, almost all of the March-May and September-November cold.
- That saves about 0.9-1.3 GWh of chiller electricity a year, roughly 0.2 M€/yr or 7-10 €/MWh of cold (LCOC is 50 €/MWh), for a plate exchanger costing well under 1 M€.
- It also changes the case for the absorption chiller: free cooling takes its spring and autumn hours.

**Fix.** Add a free-cooling stage before the chillers, driven by a monthly or daily wet-bulb table, plus a condensing temperature that follows the wet-bulb. Free cooling cuts energy, not peak capacity.

### 3.6 MEDIUM: LCOE rewards designs that fail to deliver

**What happened.**
- U1 (one doublet lost, 3.85 GWh of heat unserved) shows LCOE **61.31** against 61.77 for the compliant base.
- In the tornado, heat demand ×1.2 shows LCOE **59.71** with 1 violation, cheaper than the base.
- The agent repeated "combined cost of heat and cold of **61.3 €/MWh**" for the failing single-doublet design, with no warning.

**Why it matters.** A reader comparing LCOEs will prefer a design that leaves customers cold.

**Fix.** Charge unserved heat or cold at a penalty price, or blank out (or strongly flag) the LCOE of any design with violations, in the tornado, the Compare tab and the chat.

### 3.7 MEDIUM: heat recovery from the cooling network: right not to build it, but the agent cannot say why

**What I did.** Message: "On 219 days … 2D-HP-AB throws about 32 GWh of condenser and absorber heat into cooling towers while burning gas … Should we add a heat-recovery heat pump … What COP would it have compared with the brine heat pump?"

**What happened.**
- The claim checker removed 5 sentences, including the correct answer: "No, adding a heat-recovery heat pump is not recommended for this design."
- The reply fell back (fallback: true) to the stock recommendation text, after a full 1,040-year search (106 s). The COP question was never answered.
- Side effect: intake stored "32 GWh" as the brief's `annual_cool_gwh = 32.0`. It is the rejected heat, not the cooling demand. Results are not affected, because demand is scaled by `demand_scale`, but the brief is now wrong.

**My calculation, with the model's own formulas:**
- A recovery heat pump at sink 100 °C and source outlet 20 °C has COP 0.5 × 373.15/80 = **2.33**, or 2.82 counting the chiller and tower work it saves. The brine heat pump runs at **4.61**.
- Running cost: recovery heat pump 65.8 €/MWh, purchased-gas boiler 88.8 €/MWh, brine heat pump 40.3 €/MWh.
- On the 219 cooling days the boiler mostly burns produced gas that is free and must be burnt anyway. Purchased-gas boiler heat on those days is only 0.90 GWh, and a recovery heat pump could displace about **0.30 GWh/yr**, saving about **7 k€/yr** against an 87 k€/yr annuity per MW.
- The brine is not scarce in summer: 27.4 MW is available against 3.4 MW of demand.

**Fix.** Do not build `recovery_heat_pump_mw` before the deadline. Give the agent this reasoning: the 100 °C supply forces an 80 K lift, the brine is the better source, and the summer top-up is produced gas.

### 3.8 MEDIUM: thermal storage: the generator path does not work from the client, and its spec is the wrong store for this question

**What happened.**
- First message: "Would thermal storage help 2D-HP-AB: a hot-water tank for the daily peaks, or a seasonal store such as high-temperature ATES …?" It offered to "write [an ATES model] … run it in a sandbox".
- `panel.py click` cannot answer this card type ("no card to click (open: generate)").
- Typing the option text ("Yes, write and test the model") was classed as `relevant: false`, and the offer was lost.
- A reworded question gave no card at all, only a text offer.
- Answered with the `generate` key, the generator took 318 s and failed: "qwen3.5:4b didn't answer in time".
- The spec in `component_specs.py` describes a low-temperature ATES (default 18 °C warm / 7 °C cold) that "ignores buoyancy (important above about 30 °C)". It is a standalone calculator, not part of the daily plant model.

**Why it matters.**
- For an 80 °C seasonal store, buoyancy drives recovery, so this spec would overstate it.
- Even a perfect store at brine temperature cannot replace the gas, which is burnt for the 81→100 °C top-up. Only a heat pump can lift stored heat to 100 °C.
- So storage is not the lever for gas here. A day tank against the hourly peak (issue 3.2) is the relevant store.

**Fix.**
- Make the client and the chat accept the generate card.
- Have the agent say why a brine-temperature store cannot cut top-up gas at a 100 °C supply.
- Leave seasonal storage out of scope before the deadline.

### 3.9 LOW: component parameters

- **Cooling towers.** `tower_mw_el_per_mw = 0.0125` is commented as "fans and pumps", but the ASHRAE 90.1 basis (about 40 gpm/hp) covers fans only. Condenser-water pumps add about 1.5 % of rejected heat, and the absorption chiller needs about 2.5× the condenser flow. Tower electricity (0.403 GWh) is understated by about 2×. That is about 0.1 M€/yr, but it hits the absorption case hardest.
- **Heat pump.** A 100 °C sink is at the edge of large commercial units: R1234ze(Z) or R1233zd(E), butane, or steam compression. Ammonia tops out at about 90-95 °C, and CO₂ is poor with a 60 °C return. DEA sheet 40 (1.2 M€/MW) is for lower outlet temperatures. A 20-40 % premium for a high-temperature unit would add about 1 €/MWh of heat. Say so in the assumptions.
- **Boiler.** 95 % LHV at a 60 °C return is optimistic for a non-condensing boiler (about 92-93 %). In summer it runs at about 0.8 MW on an 11.7 MW unit (7 % load), below the turndown of one unit. Split it into units, for example one small unit for the produced gas.
- **Brine in the units.** The absorption generator and the heat pump evaporator take the gassy, saline brine directly, with no intermediate loop or approach. The main exchanger has a 5 K approach; these units have none. In practice there is an intermediate loop costing about 3-5 K.
- **CHP.** A CHP on the produced gas (17.9 GWh of methane a year; electricity at 185.7 €/MWh) is a natural option. `chp_mw_el` is only a placeholder.

### 3.10 LOW: wasted turns

Explanation questions (hourly peak, heat recovery, free cooling in a new thread) start the full design search: 35 layouts, 730 sizings, 1,040 years, 80-106 s each. In the free-cooling case, a new thread first demands the inputs card before answering a factual question.

## 4. Implement differently or remove

- **Remove or label `cool_return`.** Take it off the inputs card and the sensitivity menu, or label it "no effect yet", until network pumping or storage uses it. It currently invites false explanations (issue 3.3b).
- **Remove the zero placeholders.** Drop `recovery_hp: 0.0` and `chp: 0.0` from the outputs and the chat until those units exist. Replace them with the one-paragraph reasoning for leaving recovery out.
- **Rename the boiler.** Call it "peak boiler" until it passes N-1, then "peak and backup boiler". Size it on firm capacity (largest unit out, hourly peak factor), not on the daily-mean shortfall.
- **Treat failing designs differently.** Report unserved energy and violations next to the LCOE, and never rank or quote a failing design's LCOE as cheaper.
- **Answer explanation questions from a plant fact sheet,** not from a re-run of the search. Let the claim checker check statements about model behaviour against that sheet, and stop it deleting answers wholesale (issues 3.2, 3.3, 3.7).
- **Keep the solver as it is.** It is good.

## 5. Top 3 priorities before the deadline

1. **Firm capacity check.** In `verify`, add an N-1 test on the peak day (largest doublet, heat pump, largest boiler or chiller) and a peak-factor margin. Size the boiler to pass both: about 19 MW, +0.5 €/MWh of heat. Report unserved MW and MWh, and flag or penalise the LCOE of failing designs.
2. **Ground the plant explanations.** Give the answer model a plant-rules sheet generated from `year.py`:
   - dispatch order;
   - produced gas first;
   - the exchanger share (twh − 5 − tr)/(100 − tr);
   - fixed 35 °C condensing;
   - what each assumption feeds.

   Make the claim checker test statements about model behaviour, not only numbers, and stop it deleting the direct answer or substituting the stock template. Also fix the LaTeX escaping in replies.
3. **Network boundary and cooling realism.**
   - State "demand at the plant fence, losses included" as an assumption with a loss-factor sensitivity.
   - Add network pumping, so the cooling return means something, or remove that assumption.
   - Add a free-cooling stage driven by a monthly wet-bulb table. It is cheap and standard at 20 °C, and is likely the largest cut available in the cost of cold (about 7-10 €/MWh by my estimate).
