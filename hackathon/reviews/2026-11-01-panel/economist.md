# Panel report, round 2: energy economist

Server: http://127.0.0.1:8791. Threads: `econ-r2a` (objective read as lowest cost: A1 = 1D-HP-AB, A9 = 1D-HP-EC-N1) and `econ-r2b` (default best overall: A1 = 1D-HP-EC-N1, plus W1/B1 at gas 45 and C1 at CO2 150 €/t). 18 chat turns, plus `design … economics`, `attempts`, `sensitivity` and three read-only Python checks against the repository code. Scripts and turn logs are in `scratchpad/econ2/`.

## 1. Verdict

The cost base is now right. ThermoGIS v3 wells plus the v3 surface plant come out 3-5 % above PBL's SDE++ 2026 totals in all three size classes, the fixed O&M is PBL's 121 €/kW/yr, and every figure I rebuilt (wells, annuities, O&M, NPV, the +1.64 €/MWh for the reliable plan) matches to the cent. Requiring the plan to survive any one unit out is a sound gate, and it is cheap at about 226 k€ a year. The "best overall" rule is not yet something I would take to an investment committee, for three reasons. It inverts when the user's carbon price is above 137 €/t: at 250 €/t it recommends the highest-CO2 reliable plan while the other three picks are all two-doublet designs. It picks from a pool that the plain cost ranking has already filtered. It is decided by margins of 0.03-0.08 €/MWh. The chat is still where the money case breaks. At gas 45 €/MWh it said "geothermal still beats gas" and gave NPV 26 M€ with payback in year 10. The true figures are NPV 0.0 M€, payback in year 30, and gas 0.16 €/MWh cheaper. It gave two designs "the same NPV" when their NPVs differ by 3.2 M€. It told an investment committee that the best overall is chosen for its CO2 saving, which is worth one-seventh of what the reliability costs.

## 2. Stress test

| Request | Wordings tried | Right / wrong | What went wrong |
|---|---|---|---|
| Design with an investment framing | "Design the heating and cooling system … I care about the investment case." | 0.5 / 1 | It set the objective to "lowest cost" (not the default best overall), so it recommended a plan with 0 MW spare and 5 of 6 one-unit-out cases short. The reply says only "not sized for a full boiler outage". |
| Compare picks by code | "compare the cheapest with the best overall"; "which is cheapest over 30 years, A1, A9 or 2D-HP-AB? total cost of ownership please"; "cheapst vs most relaible - wich one has the better npv against gas?"; "W1 vs A1" | right designs 3 / 4; figures right 1 / 4 | The code tables are right. The prose around them is not claim-checked (`_checks_claims` skips replies built on a draft): "A21 offers more reliability" (A21 has 8 cases short, A9 has 0); "the **same** NPV against gas: **29.4 M€**" for A1 and A8 (A8 is about 26.2). There is no TCO and no NPV for non-chosen designs ("-" in its own table). "W1 vs A1": "I cannot find any designs … named 'W1' or 'A1'", although both are in `designs`. |
| NPV / payback against gas | "how long before A1 pays for itself compared with just using gas boilers, and what's it worth in today's money?"; Dutch "Wat is de terugverdientijd … netto contante waarde?"; German "Lohnt sich A1 wirtschaftlich … Kapitalwert und Amortisationszeit"; "and at that gas price, what are the NPV and payback …?"; "What IRR does A1 give … SDE++ 2026 base amount" | 1 / 5 | English was right (year 10, 26 M€). Dutch: the claim check removed both correct sentences. German: canned well text (fallback). "At that gas price": default-price figures given as the answer. IRR/SDE++: canned text about the wrong design (C1, not A1). |
| Price what-ifs | "what if gas drops to 45 €/MWh? does the pick change, and does geothermal still beat gas?"; "Forget the gas change. Suppose the carbon price is 150 €/t … which design is best overall then, and what's the NPV against gas?" | picks 2 / 2; money 0 / 2 | Gas 45: "The cost of heat drops to 61.4 €/MWh". That is heat and cold together (heat is 65.5). "Geothermal still beats gas" is false: 61.39 against 61.23. CO2 150: the NPV was asked for and not given (the tab has 41.2 M€), and the figures are labelled "Key values from the baseline design". |
| Failure + spare ESP | "what if the ESP of doublet 1 fails from 10 to 24 January? what does it cost us and is a spare ESP worth buying?"; "for A1: the ESP packs up for a fortnight in the worst part of winter. what does that cost, and does keeping a spare pump pay off?" | parsed 1 / 2; reply right 0 / 2 | First: "adding capacity there does not help", while the card's best remedy is 6.1 MW more boiler (covers every day, 47.4 k€/yr). Second: it ran C1, not A1, out all year (not the worst 14 days), twice. The reply says "the plant cannot meet demand" (card: 0 days short) and "I cannot calculate the exact cost saving". |
| Explain the best-overall rule | "Explain to my investment committee why the best overall pick is A9 and not A1 … How exactly is best overall decided, and what does the extra reliability cost per year?" | 0 / 1 | It gives the wrong reason ("this carbon saving often justifies the higher upfront cost"). It states neither the rule (N-1 gate, CO2 at 137 €/t) nor the yearly cost. One sentence is broken ("According to, A1 costs …"). |
| € per tonne of CO2 avoided | "If we went for the lowest-CO2 pick instead of the cheapest, what would each extra tonne of CO2 avoided cost us in euros per tonne?" | 0 / 1 | The model computed it. The number check removed every derived figure (even 4,289 = 14,334 − 10,045), leaving a bare two-row table. |

## 3. Issues

### Round-1 issues: status

| Round 1 | Status now |
|---|---|
| H2 capex/O&M 20-35 % below PBL | **Fixed.** Code against PBL Tables 11.7a-c: 8.7 MW 2,544 against 2,463 €/kW (+3.3 %); 15.9 MW 1,791 against 1,719 (+4.2 %); 27.4 MW 1,410 against 1,340 (+5.2 %). Fixed O&M 121 against 117-121. `SOURCES` text is correct. |
| M4 no N-1 | **Fixed.** Reliable plans, the one-unit-out cases, a FAILURE card. |
| M1 Compare tab showed the wrong search | **Fixed.** S2 (gas 45) lists its own candidates at 58-60 €/MWh. |
| H1 made-up gas reference | **Partly fixed.** The chosen design at default prices is now grounded ("year 10, 26 M€", correct). What-if prices and non-chosen designs are not (see H1 below). |
| H4 refusals / canned text | **Partly fixed.** English yes, and the "Not in these costs: … SDE++ … tariff" line is good. Dutch, German, IRR and SDE++ questions still get deletions or canned text (H5). |
| H3 knife-edge pick, H5 lowest-CO2 at absurd €/t | **Not fixed** (M1 below). |
| M2 NPV labels / replacements | Labels fixed in the money lines. Replacements and flat prices remain (L1). |
| L1 duplicate "Surface plant" lines | **Not fixed.** `economics.py` still strips "(per MW)", so the cost lines show two "Surface plant" rows. |

### H1 (high): money answers at the wrong prices or for the wrong design, stated as fact
- **Gas 45, turn 1.** "what if gas drops to 45 €/MWh? … does geothermal still beat gas?" got: *"The cost of heat drops to **61.4 €/MWh** … Geothermal still beats gas, saving **42.1%** CO₂."*
  - 61.39 is heat and cold together; heat is 65.49.
  - At 45 €/MWh the gas reference costs 61.23 €/MWh, so gas is cheaper on the headline cost (heat alone: 65.49 against 66.56).
  - The re-searched pick B1 shrinks the heat pump and emits 15,656 t (35.7 % saving), not 42.1 %.
- **Gas 45, turn 2.** Follow-up: "and at that gas price, what are the NPV and payback against the gas reference?" Reply: *"The NPV against the gas reference is 26 M€ over 30 years … The discounted payback occurs in year 10."* These are the default-price figures. I recomputed with the repository's own `engine.reference` and `versus_reference`: savings 1.726 M€/yr, **NPV 0.0 M€, payback year 30**, real IRR 5.2 % (against 13.0 % at 69.4 €/MWh).
- **NPV copied to another design.** "cheapst vs most relaible - wich one has the better npv against gas?" got: *"have the **same** NPV against gas: **29.4 M€** … it saves on CO₂ penalties or other factors that balance the equation"*. CO2 is identical (14,334 t both). A8 has 2.0 M€ more capital and 78 k€/yr more O&M, so its NPV is about 26.2 M€. No claim check ran on this turn.
- **NPV asked, not given.** "Suppose the carbon price is 150 €/t … what's the NPV against gas?" The reply gives none; the Economics tab has 41.2 M€, payback year 9.
- **Why it matters.** NPV against gas and "does it still beat gas at cheap gas" are the investor's first two questions. At 45 €/MWh the whole case is break-even, and the agent says the opposite with numbers.
- **Cause.**
  - `answer.money_lines` is built only for the conversation's chosen design at the base prices. What-if designs (W/B) and the compared designs get no money facts.
  - The COMPARE card has no money rows.
  - Prose that wraps a code table is not claim-checked (`agent._checks_claims` returns False for draft-based replies in auto mode).
- **Do instead.**
  - Compute `versus_reference` (NPV, discounted and simple payback, IRR, total yearly cost, €/t against gas) in code for every design at the prices it was run at.
  - Add these as rows to the COMPARE and what-if cards.
  - Have the what-if card state "against gas at 45 €/MWh: 61.4 against 61.2 €/MWh, NPV 0.0 M€".
  - Claim-check the free prose around code tables.

### H2 (high): "best overall" inverts when the carbon price is above 137 €/t
- **The bug.** `engine.shadow_cost` adds `(carbon_long_term − carbon_eur_per_t) × CO2/MWh`. With the user's carbon at 150 €/t the extra term is negative, so CO2 is valued at 137, below the user's own price.
- **Test.** I ran `engine.search` with `{"carbon_eur_per_t": 250}` (script `carbon_pick.py`):
  - picks: `cost: 2D-HP-EC`, `co2: 2D-HP-EC-2I`, `reliable: 2D-HP-EC-ST-N1`, **`best: 1D-HP-EC-N1`**;
  - the recommendation has the most CO2 of the reliable plans (11,002 t against 7,768 t for 2D-HP-EC-ST-N1, which is also 0.35 €/MWh cheaper at 250 €/t);
  - at 400 €/t the best overall is 2D-HP-AB-ST-N1, again not the cheapest at the user's price.
- **Two smaller problems with the rule.**
  - **Filtered pool.** Reliable plans are made only for the 6 cheapest layouts at *today's* carbon price plus the greenest (`_reliable_plans`, `RELIABLE_TOP`). At default prices no two-doublet reliable plan exists, so the CO2-weighted pick can never choose one.
  - **Mixed price years.** It mixes a 2026-2040 carbon price with 2025 retail gas and power. PBL's same long-term set (KEV 2025) has TTF 28 €/MWh LHV and wholesale power 74.3 €/MWh. Power is not raised when carbon is, which biases the pick towards electric units.
- **Do instead.**
  - Use `extra = max(0, LT − p)`, or price CO2 at `max(p, LT)`.
  - Make reliable plans of the cheapest layouts by shadow cost as well.
  - Offer one consistent "PBL long-term" price set rather than a carbon-only overlay.

### H3 (high): the rule is not explained, and the chat gives the wrong reason
- **Explanation deleted.** In "compare the cheapest with the best overall" the claim check deleted the only correct explanation: *"A9 is chosen as best overall because it offers superior reliability and lower emissions for a minimal cost increase"*. It also deleted *"spare capacity of 10.4 MW … meet demand even if any single unit fails"*, which are the card's own figures.
- **Wrong reason given.** Asked for an investment committee, it said: *"Over the project life, this carbon saving often justifies the higher upfront cost"*.
  - The saving is 231 t × 137 €/t = **31.6 k€/yr**, against an N-1 premium of 1.67 €/MWh × 135.4 GWh = **226 k€/yr**.
  - A9 wins because A1 fails the N-1 gate (5 of 6 cases short).
  - Among the reliable plans, A9 beats A8 by 0.08 €/MWh of shadow cost (LCOE 69.80 against 69.77).
- **Inputs card.** It says "cheapest with CO2 at the long-term price" without the 137 €/t or its source.
- **Why it matters.** An investor accepts "N-1 is a hard requirement; it costs 2.4 % of the cost of heat (+2.0 M€); among N-1 plans we pick the cheapest with CO2 at 137 €/t". An investor does not accept "carbon justifies it", because that is false by a factor of seven.
- **Do instead.** Generate a fixed, code-written "why this pick" sentence:
  - the gate;
  - the premium in M€ and €/MWh;
  - the shadow-cost margin to the runner-up;
  - "a tie" when the margin is under about 0.5 €/MWh.

### H4 (high): failure answers contradict their card, and the spare-ESP benefit is mis-valued
- **Reply against its own card.** "what if the ESP of doublet 1 fails from 10 to 24 January?" (A1 = 1D-HP-AB):
  - the card says the best remedy is `6.1 MW more boiler (26.9 MW in all): covers=True, 0.458 M€, 47.4 k€/yr`;
  - the reply says *"Since the boiler is already at full output during this period, adding capacity there does not help."* It never names the recommended remedy;
  - it also leaves out the 119.7 k€ the outage costs ("what does it cost us" was asked).
- **Wrong design, duration and verdict.** "for A1: the ESP packs up for a fortnight in the worst part of winter":
  - it ran **C1** for **all year**, twice ("keeping a spare pump" was read as a second failure);
  - the reply says the plant *"cannot meet demand"* (card: 0 days short) and *"I cannot calculate the exact cost saving"*.
- **The spare-ESP economics.**
  - **Cost side: sound.** 0.24 M€ × 5.2 % = 12.5 k€/yr of capital tied up. This is consistent, because PBL's 121 €/kW/yr already holds the ESP replacement provision, so the pump itself is not charged twice.
  - **Benefit side: overstated.** `money_saved_keur = gas saved × (gas price + CO2 price × 0.2023)` is *gross*. It ignores the electricity the doublet and heat pump use when they run again. All-year case: "saves" 8,424 k€ while the failure's whole extra running cost is 4,884 k€. Dated case: 2.41 GWh × 84.4 = 203 k€ gross against 119.7 k€ net (+70 %).
  - **Units don't match.** It compares a per-event saving with a per-year cost. It needs a failure rate: NL ESP run life is 1-2 years (cost_sources 1.11), so about 0.5-1 failure per ESP per year. With that, the spare clearly pays (about 50-100 k€/yr expected against 12.5 k€/yr). The agent never says so.
  - **No price on unserved heat.** The 1.69 GWh not delivered has no value attached (Warmtewet outage compensation, mobile boiler hire). So a spare that cuts the shortfall but does not cover every day can never win, and spare + smaller boiler is not tried.
  - **Unrealistic counterfactual.** `firm.NO_SPARE_ESP_DAYS = 30` is defined but never used. A no-date failure is valued as 365 days without a pump.
- **Do instead.**
  - Value the spare by the net running-cost difference.
  - Add a failure rate to get an expected annual value.
  - Price unserved heat (a parameter, e.g. 100-300 €/MWh or compensation per connection).
  - Use 30 days as the no-spare case.
  - Let the code write the verdict ("pays: 12.5 k€/yr against about 60 k€/yr expected").

### H5 (high): finance questions outside an English keyword list fail
- **The cause.** `answer.COST_TALK` is a regex. "terugverdientijd", "netto contante waarde", "Kapitalwert", "Amortisationszeit" and "IRR" are not in it, so the cost block is not sent.
- **What happened.**
  - **Dutch:** the model answered correctly from history, then the checker removed both sentences ("Design A1 … pays for itself in year 10"; "net present value of 26 M€"). What was left: *"This assumes the plant delivers heat at 75.7 €/MWh …"*.
  - **German:** canned well description (`fallback: true`).
  - **"IRR … SDE++ 2026 base amount":** canned text for **C1** (83 €/MWh), although the user said "A1 at the default prices". That canned text also says *"Not modelled: the reservoir's cooling over the years (thermal breakthrough)"*, which contradicts ADR-0011's Gringarten-Sauty check.
- **This breaks the team's rule.** "No phrase lists deciding what a message means" is the team's own rule, and this list decides whether money facts are available.
- **Do instead.**
  - Send the money lines whenever a design is in scope (they are short), or let the intake model flag "money".
  - Answer IRR from code (13.0 % real at default prices).
  - Say plainly "SDE++ is not modelled; PBL's base amount for < 12 MW deep geothermal is 79.9 €/MWh".

### M1 (medium): picks decided by noise; lowest CO2 at 385-3,900 €/t, still unexplained
- **Cheapest.** 1D-HP-AB (68.13) beats 1D-HP-EC (68.16) by **0.03 €/MWh**, yet costs 0.9 M€ more capital and emits 231 t more. The `lost_reason` even says "the same cost per MWh, but -0.9 M€ of capital", and the pick stays. Any investor takes 1D-HP-EC.
- **Best overall against most reliable:** decided by 0.08 €/MWh of shadow cost.
- **Lowest CO2.** The pick is 3D-HP-EC (80.31 €/MWh, 65.3 M€):
  - **385 €/t** against the cheapest;
  - **3,936 €/t** against 2D-HP-EC, which it beats by 284 t/yr for +8.26 €/MWh and +15.6 M€ of capital;
  - 2D-HP-EC misses the 2 % band by 84 t.
- **No €/t anywhere.** No card or tab shows €/t, and the chat cannot compute it (derived numbers are stripped).
- **Do instead.**
  - A tie band (about 0.5 €/MWh, or within the Monte Carlo spread), broken by capital, then CO2.
  - "Lowest CO2" as the cheapest design whose step-up costs no more than X €/t (e.g. 137-200), or show the marginal abatement cost (MACC) of the candidates.
  - Let the number check accept sums and differences of context numbers.

### M2 (medium): the LCOH is a societal figure, not an investor's price, and it isn't labelled as one
- **The issue.** The code annualises at PBL's **after-tax** real WACC (5.2 %) over 30 years, with no tax lines. With PBL's own inputs that method gives 53.1 / 44.0 / 40.8 €/MWh for the three size classes, against PBL base amounts of **79.9 / 69.6 / 62.7**. A PBL-like cash flow (15 years, 7.3 % nominal after tax, 25.8 % tax, 15-year depreciation, O&M +2 %/yr) reproduces 82.0 / 65.2 / 58.3 (`pbl_check.py`).
- **What it means for the investor.** Required heat prices are about 35-50 % above the LCOH shown. A pre-tax real WACC of about 7.7 % moves the best-overall design from 69.8 to 74.2 €/MWh and its NPV against gas from 26.0 to 14.1 M€.
- **Do instead.** Label LCOH and NPV "real, societal (no tax, no subsidy)". Add an investor view (see section 4, item 3).

### M3 (medium): the reliable plan's premium is right, but the comparison base and the pool are not
- **Verified.** 1D-HP-AB-N1 adds boiler 20.8 → 31.2 MW (3 × 10.4) and chillers 10 → 15 MW (3 × 5): +2.005 M€. That is 0.145 M€/yr annuity plus 0.078 M€/yr fixed O&M = **1.645 €/MWh**, exactly the "+1.64 €/MWh" shown. Sound and cheap insurance.
- **Missing 1: the gas reference has no N-1.** It is one 30 MW boiler and 10 MW of chillers. A real gas alternative for district heating would also have N-1: +15 MW boiler, +5 MW chillers, about 2.35 M€ plus 89 k€/yr. So the NPV of the reliable plans against gas is understated by about 3.7 M€. That is conservative, but not like for like.
- **Missing 2: capacity-based charges.** Gas and electricity connection and capacity charges scale with contracted capacity. Eurostat's €/MWh averages them by volume, so standby capacity looks free.
- **Missing 3: the pool.** No two-doublet reliable plan is evaluated (see H2).

### L1 (low): presentation
- **No replacements in the NPV.** Heat pump, boiler and chillers at year 25 (and the reference's units): −0.88 M€ on A1's NPV. Prices are flat for 30 years.
- **"Discounted" dropped.** The reply says "pays for itself in year 10" without "discounted". The money lines have it; simple payback is 7.5 years.
- **Names depend on the objective.** "A1" is 1D-HP-AB in one thread and 1D-HP-EC-N1 in the other, and "A9" is the reverse. Two reports about the same district will confuse a reader.
- **What-if cost against the pick's cost.** The gas-45 reply compares "61.4 (from a previous baseline of 69.8)": W1's headline cost against A1's, under different prices, without saying so.

## 4. What users in my role need most that is missing

1. **Money rows for every design and scenario, computed by code** (NPV against gas, IRR, simple and discounted payback, total yearly cost, 30-year PV of costs, €/t against gas and against the cheapest), shown in the COMPARE, what-if and FAILURE cards and sent to the answerer. Today only the chosen design at base prices has them, and the model fills the gaps. *Why:* it fixes H1, most of H5 and the €/t question at once. *Effort:* half a day to a day.
2. **Correct and consistent carbon pricing in "best overall":** `max(p, 137)`, reliable plans for the cheapest layouts by shadow cost, and a selectable "PBL long-term" price set (TTF 28 + taxes and network charges, power 74.3 + the same, ETS 137) next to "2025 spot". *Why:* the default recommendation must not invert under a user's carbon price, and it must rest on one price scenario. *Effort:* a few hours (fix), a day (price set).
3. **An investor case:**
   - SDE++ revenue for 15 years: category deep geothermal < 12 MW, base amount 79.9 €/MWh, minus the gas-linked correction amount, on eligible geothermal heat. Rough order: 2-3 M€/yr, PV about 20-30 M€, which is as large as the whole NPV against gas.
   - The heat tariff (ACM cap under the Warmtewet) instead of "cost against gas".
   - Tax and depreciation, equity IRR, and a debt-service cover check.

   *Why:* a lender or the SDE++ application looks at these, not at a societal LCOH. *Effort:* 2-3 days.
4. **Robust ranking:**
   - a tie band;
   - P(cheapest), P10 NPV and P90 LCOE from the Monte Carlo that already exists, shown next to the picks;
   - a MACC across the candidates.

   *Why:* every pick today is decided by 0.03-0.08 €/MWh. *Effort:* about a day.
5. **Reliability economics:**
   - failure rates per unit (ESP 0.5-1 per year);
   - expected yearly outage cost;
   - a price on unserved heat;
   - the spare ESP valued net and per year;
   - remedies combined (spare + smaller boiler);
   - an N-1 gas reference.

   *Why:* it turns the FAILURE card into a decision ("buy the spare: about 60 k€/yr expected saving for 12.5 k€/yr"). *Effort:* 1-2 days.
6. **Remove the `COST_TALK` regex** (money facts whenever a design is in scope), and answer IRR/SDE++ honestly instead of with the canned text. *Why:* Dutch and German investors and judges get nothing today. *Effort:* hours.

## 5. What works

- **The cost basis is now PBL-consistent and well sourced.** Totals are within +3-5 % of PBL Tables 11.7a-c in all three size classes, the fixed O&M is 121 €/kW/yr, and the `SOURCES` text and ADR-0011 say exactly what was done.
- **The arithmetic is exact.** Well 5.479 M€ (L = 2,871 m), CRF 0.06654, fixed O&M 1.065 M€/yr, NPV 25.99 = −25.94 + 3.455 × 15.028, discounted payback in year 10, N-1 premium 1.645 €/MWh: all match my hand checks.
- **The reliable plans are a real step up.** The N-1 gate is costed (+2.0 M€, +1.6 €/MWh), the card lists the one-unit-out cases, and each FAILURE remedy is run through the same days. Charging the spare ESP only for its capital tied up is consistent with the ESP provision in PBL's fixed O&M.
- **English money questions are grounded now.** "how long before A1 pays for itself … today's money" gave the right year and NPV. The "Not in these costs: networks, SDE++, taxes, tariff" line is exactly the caveat I asked for.
- **Comparisons and re-searches work in code.** The COMPARE card resolves "cheapest", "best overall", "most reliable" and codes, even with typos. Each search keeps its own candidates (round-1 M1 fixed). A price what-if re-runs the search and says "pick stays".
