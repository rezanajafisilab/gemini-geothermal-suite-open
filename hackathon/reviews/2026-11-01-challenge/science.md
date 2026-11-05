# Science and economics challenge: Dioscuri (1 Nov 2026)

Reviewer role: senior geothermal engineer and energy economist. Server `http://127.0.0.1:8822`, threads
`sci-1` (20 turns) and `sci-2` (11 turns), plus the tab data (`/api/workbench`), one user edit (U1), the
operator PDF (`/api/report.pdf`), the Monte Carlo API, and local runs of `dioscuri_plant` with GEMINI's
doublet model. My scripts are in the session scratchpad. I changed no repository file.

## 1. Verdict

The plant model is better than the agent that talks about it. Hand checks reproduce the energy balance,
the CO2 split, the well hydraulics, the bubble point, the ESP depth, the breakthrough time, the well and
reference costs, the failure costs and the network loss, often to the last digit. The chat is a
different matter. On the questions an expert or a council adviser asks first, it states wrong numbers,
gives wrong reasons or denies features that exist. It said the recommended design takes about 0.5 GWh
(3 %) of its heat from gas; the true figure is 55 GWh (49 %). It blamed N-1 for the gas share. Three
times it said it cannot compute SDE++, NPV, IRR, failure costs or service windows, although the tabs
show all of them.

Four results are wrong or biased in the model itself:
- **The best-overall pick is not the best by its own measure.** A larger heat pump cuts CO2 by 8 % for
  about 0.03 €/MWh more.
- **The gas-free premium is about 6 €/MWh too high.** The search never tries a treatment train per
  doublet for the gas-free plans.
- **The 600-hour grid contract can break without the model seeing it.** An outage, or a return
  temperature 10 K off the assumption, pushes the electric boiler past 600 hours and the yearly grid
  charge up by 3.0 M€. Failure costs, failure cards and the uncertainty explanation leave this out.
- **SDE++ is paid on the heat pump's electricity**, and the "with heat pump" categories, which the user
  can pick, use the wrong capacity.

Fix the chat's access to the facts and these four items, and the science will hold up to a jury.

## 2. Checks

| Thread / turn | Question | Agent's figure or claim | My check | Verdict |
|---|---|---|---|---|
| sci-1 t1–2 | Recommended design, alternatives, economics | A1 1D-HP-EC-N1: 69.8 €/MWh, 14,103 t, 30.6 M€, 42.1 % less CO2 than gas | Ledger reproduced locally (69.80; 14,103.2 t). CO2 = 46.69 GWh gas × 0.202 = 9,431 t + produced gas 1.759 Mm³ × 0.8 Nm³/m³ × 1.9635 kg/Nm³ = 2,763 t + 9.55 GWh × 0.20 = 1,909 t. 1 − 14,103/24,365 = 42.1 % | Correct |
| sci-1 t3 | Yearly heat balance by source | A sentence fragment, no numbers | Data: exchanger 41.75 + heat pump 14.93 + boiler 54.99 = 111.67 GWh | No answer |
| sci-1 t4 | "How much of the recommended design's heat comes from the gas boiler?" | "approximately **0.5 GWh** … about **3%**" | 54.99 GWh = 49.2 %. The PDF of the similar sci-2 design says "boiler gives 50.2 % (57.6 GWh)" | **Wrong, by 110× in GWh** |
| sci-1 t5 | Why half the heat from gas, and why one doublet beats two | "a direct consequence of … Reliability (N-1 capability)" | The non-N-1 twin 1D-HP-EC has the same boiler energy (54.99 GWh) and the same CO2 (14,103.2 t). N-1 adds only standby MW | **Wrong mechanism** |
| Edit U1 | A1 with a 3.3 MW heat pump and 3 × 10 MW boiler | – | 69.83 €/MWh, 12,967 t, N-1 holds (5 of 5 cases met). Weighted with CO2 at 137 €/t: 75.87 against A1's 76.37 | **Pick is not optimal** |
| sci-1 t6 | Why 31 K and not 40 K; is the cap a SodM rule? | "not a SodM rule" (right); COP falls because ΔT "to the ambient air (or ground source)" shrinks; "807 sizings"; "87 °C − 31 K ≈ 56 °C" | COP = 0.5·T_sink/(T_sink − T_src,out): colder brine means a bigger lift to 100 °C. The plan says 280 (500) sizings. Coldest reinjection is 52.1 °C, from 83.1 °C at the wellhead that day. The 31 K follows from the 2 MW heat pump | Partly wrong |
| sci-1 t7 | Bubble point 43.4 bar, ESP at 732 m | "fluid properties … not provided"; mixes in the half-open (PL) variant | Reproduced. CH4 42.1 + CO2 0.72 + water 0.60 = 43.4 bar(a). Intake at 732 m: 250 − 300/14.51 − 0.101 × 1,768 − 3.3 = 47.4 bar(g) = 43.4 + 5 bar margin. GEMINI: 49.3 bar(g) at 750 m | Data right, no answer |
| sci-1 t8 | Breakthrough 85 years: formula and inputs | "I couldn't confirm an answer" | Gringarten–Sauty t = π/3·(ρc)aq·H·L²/((ρc)w·Q): φ 0.20, L 1,500 m, H 100 m, Q 200.8 m³/h gives 85.4 yr | Data right, no answer |
| sci-1 t9 | Why the boiler is 3 × 10.4 MW | Boiler-unit-out case; "two boilers plus the 2 MW heat pump … cover the full peak" | Right case, incomplete balance: 20.8 + 2.0 + **7.23 (exchanger)** = 30.03 MW ≥ 30. Doublet out: 31.2 ≥ 30 | Right case, balance incomplete |
| sci-1 t10 | Cost of a fossil-free plant against A1, and why | B1 2D-HP-AB-N1-EB-GS 101.7 €/MWh; "79.5 % less CO₂"; the comparison sentence was removed | 101.68 checks. No reason is given for the extra cost. With a treatment train per doublet: 95.56 €/MWh | Incomplete; over-priced |
| sci-1 t11 | CO2 of the sold methane | Excluded (right); tonnage "not given"; plant "roughly 100 MWth" | `co2_t.sold_gas_elsewhere` = 3,612.1 t is in the data. Counted in: 8,611 t, 64.7 % less than gas, not 79.5 %. The peak is 30 MW | Partly wrong |
| sci-1 t12–13 | SDE++ category, amount, NPV, IRR of A1 | "My plant model has no input for these financial variables" / "outside what I do" | Investor tab: <12 MWth (79.9 €/MWh), 3.35 M€ in year 1, NPV 34.8 / 16.0 M€, IRR 16.1 / 9.7 % (real) | **Feature denied** |
| sci-1 t14 | Investor view of B1 | ≥20 MWth 62.7 €/MWh, 24 MW, 111.5 GWh, NPV −13.4 M€, IRR 3.3 % | Matches the tab, but 111.5 GWh includes 13.65 GWh of heat-pump electricity | Consistent; eligibility wrong |
| sci-1 t15–16 | Failure costs and a spare ESP | (refused for A1) B1: 1,653 k€ without a spare, 427 k€ with one; spare 20 k€/yr; pays above one failure in 123 yr | Reproduced exactly (1,652.8 / 426.6 / 0.0081/yr). Leaves out the 600-hour cliff and the shared train | Consistent, understated |
| sci-1 t17 | Uncertainty of the cost | B1: P10–P90 95.4–150.3, median 121.6; drivers: reservoir, discount rate, electricity | Reproduced. The base (101.7) sits near P25. With ranges centred on the base: P50 108.2. Heat return ±10 K gives 129–130 €/MWh through the 600-hour cliff, which is not mentioned | Misleading |
| sci-1 t18 | B1, ESP out 5 Jan–4 May: hours of the electric boiler, 600-hour contract | "still meets heat … No spare is needed"; card cost 2,050 k€; question not answered | Electric boiler runs 849 h, over 600, so the grid charge goes from 0.736 to 3.727 M€. The event costs 4.85 M€ | **Wrong (58 % low)** |
| sci-1 t19 | Is 0.20 t/MWh an average or a marginal factor? | The correct "average" sentence was removed; "79.5 % … regardless of the specific grid mix" | At a gas-fired marginal 0.37 t/MWh the plant-scope saving is about 66 % | Wrong |
| sci-1 t20 | A treatment train per doublet for B1 | Answer cut off mid-word | Local: electric boiler 30 → 17 MW, 101.68 → 95.56 €/MWh, capex −5.0 M€ | No answer |
| sci-2 t1–3 | Design with a 5 km network and service windows | First card ignored both. After a correction: network on, service still off. Result 73.07 €/MWh, losses 2.94 GWh | Loss reproduced: DN350, U 0.48 W/m/K, 5 km × (90 + 50) K = 336 kW = 2.94 GWh (2.6 %) | Correct (service not applied) |
| sci-2 t4 | How the loss was computed, and why it is below the 10–25 % of real networks | "does not explain how this number was derived" | Trunk only, one pipe pair; distribution and service pipes not modelled. That is the gap to 10–25 % (TNO 2020) | No answer |
| sci-2 t5 | Investor view | Only "IRR 15.6 % real / 9.7 %" left, plus "assumes … no other subsidies (like SDE++), and excludes taxes" | All 10 removed sentences match the tab (96.6 / 36.4 €/MWh, <12 MWth, 54.5 GWh, 3.2 M€, NPV 34.7 / 16.6, payback 7.3 / 12.9 yr). The kept note is false | **Claim checker error** |
| sci-2 t6 | What breakdowns cost; is a spare ESP worth it? | "The text does not provide a specific monetary value" | `failure_costs` exists (sci-1 t16 shows it) | No answer |
| sci-2 t7 | Gas share and what limits the geothermal share | "not stated"; the boiler is a "top-up … rather than the primary heat source"; limits: aquifer, injection pressure, breakthrough | PDF: boiler 50.2 %, exchanger 37.5 %. Injection has 65 bar of room, breakthrough is at 74 yr. The real limits: 300 m³/h cap, 81 °C exchanger outlet, heat-pump size | **Wrong** |
| sci-2 t8 | Why not SDE++ "met warmtepomp"; is the heat pump's electricity subsidised? | "subsidy rules that exclude heat pump electricity from the subsidised thermal amount"; "base-load capacity of 2 MW" | Code: eligible 57.03 GWh = exchanger 42.99 + heat-pump output 14.05 (incl. 3.02 GWh electricity). SDE capacity is 9.08 MW | **Wrong; contradicts the tab** |
| sci-2 t9 | Why only a 2 MW heat pump | "The N-1 Reliability Constraint (The Primary Driver)" | N-1 never resizes the heat pump. The size comes from the sizing sweep at today's prices (2.0 MW 68.16 vs 3.3 MW 68.18 €/MWh) | **Wrong mechanism** |
| sci-2 t10 | Is 96.6 €/MWh a realistic producer price; NPV at 40 €/MWh? | "The plant model has no input for heat selling price" | `investor.OVERRIDES` has it. Local run, A1 at 40 €/MWh: NPV −36.7 M€ with SDE++ | **Feature denied** |
| sci-2 t11 | Yearly service windows | "no input for varying yearly planned service" | `service.py` exists. Local: A1 still meets every day; the cheapest design is short 7 days | **Feature denied** |
| PDF sci-2 | Operator's report | Boiler 50.2 % (57.6 GWh); limits table; checks | Right figures, but "Not modelled: … network losses and pumping" while network losses are on | Inconsistent |

## 3. Errors, most serious first

### E1. Gas share stated about 100× too low; the claim checker lets it through (high)
- **Message** (sci-1 t4): "How much of the recommended design's heat comes from the gas boiler over the
  year, in GWh and percent?"
- **Reply**: "the gas boiler contributes approximately **0.5 GWh** of heat, which represents about
  **3%** of the total annual heat production." The report step lists `ungrounded: []`.
- sci-2 t7 repeated the claim in words: the boiler is "a **top-up** source … rather than being the
  primary heat source."
- **Correct**: `heat_split_gwh` = exchanger 41.75, heat pump 14.93, **boiler 54.99 GWh = 49.2 %** of
  111.67 GWh. For the sci-2 design the PDF itself says "The boiler gives 50.2 % of the year's heat (57.6
  GWh)". The boiler is the largest single source.
- **Code**:
  - The design block puts the split in only as percentages (`answer.py` ~l.718–727).
  - The `lookup` step fetched only `heat_coverage`, and the model answered from the costs block.
  - The number grounding accepts any number that appears anywhere in the context ("3 units", 0.5
    failures a year).
- **Fix**:
  - Add `boiler_gwh`, `boiler_share` and the full split in GWh to `lookup.design_facts`.
  - Ground numbers by unit and subject: a GWh claim about the boiler must match the boiler's GWh
    within 2 %.
  - Answer "how much heat from X" with code-written text.

### E2. Wrong reasons for the gas share and the heat-pump size: N-1 blamed (high)
- **Messages**: sci-1 t5 ("Why does the recommended design take about half its heat from the gas
  boiler …?") and sci-2 t9 ("why is the heat pump only 2 MW …?").
- **Replies**: "a direct consequence of its primary design goal: **Reliability (N-1 capability)**",
  and "The N-1 Reliability Constraint (The Primary Driver)".
- **Correct**:
  - N-1 only grows standby capacity. `1D-HP-EC` (not N-1) and `1D-HP-EC-N1` have the same boiler
    energy (54.99 GWh) and the same CO2 (14,103.2 t). The reliable plan adds 10.4 MW of boiler and
    2.0 M€.
  - The gas share follows from three physical facts and one price choice:
    1. One doublet carries at most 300 m³/h = 0.3425 MW/K, so the exchanger gives ≤ 7.23 MW against a
       30 MW peak.
    2. The exchanger can lift the 60 °C return only to 81 °C (86.1 − 5 K approach), which is 52.5 % of
       each MWh.
    3. The 81→100 °C top-up (47.5 %) and all flow beyond the brine's rate go to the heat pump or the
       boiler.
    4. The heat pump is sized by the sweep at today's prices (E3).
  - A second doublet adds only 15.7 GWh of exchanger heat (42.19 → 57.88; at most 0.525 × 111.67 =
    58.6 GWh). It costs +1.45 M€/yr of capital and +0.93 M€/yr of fixed O&M and saves about 2.1 M€/yr
    of gas and CO2, hence 71.4 against 68.1 €/MWh.
- **Fix**: give the answerer a code-written "why this gas share" fact: the exchanger's ceiling, the
  top-up share, the heat-pump source limit and the 2D comparison.

### E3. The "best overall" pick is not the best by its own objective (high)
- **Evidence**: the sizing table of A1's layout (tab `sizings`):

  | Heat pump share | Heat pump MW | €/MWh | t CO2 |
  |---|---|---|---|
  | 0.3 (chosen) | 2.0 | 68.16 | 14,103 |
  | 0.5 | 3.3 | 68.18 | 12,967 |

- With CO2 at 137 €/t (the pick's own weighting: lcoe + t × (137 − 73.9)/MWh) the 3.3 MW sizing scores
  74.22 against 74.73. My edit U1 (heat pump 3.3 MW, boiler 3 × 10 MW) is N-1 (5 cases, 0 short): 69.83
  €/MWh, 12,967 t, weighted **75.87 against A1's 76.37**. That is −1,136 t CO2 a year (−8 %) for
  +0.03 €/MWh (about 4 k€ a year).
- **Code**: the sweep keeps the cheapest sizing at today's carbon price. `firm.reliable` is built on
  that sizing, and the 137 €/t weighting applies only in `engine.pick` across layouts.
- **Fix**: rank sizings within each layout by the pick's objective, or build reliable plans for the top
  two or three sizings.

### E4. Gas-free premium overstated by about 6 €/MWh: no separate treatment trains in the gas-free stage (high)
- **Evidence**: for B1 and A10 the N-1 sizing is set by "the shared treatment train out", which forces a
  30 MW electric boiler (12.2 M€ plus 0.73 M€/yr of grid charge). Local `firm.reliable` runs with one
  train per doublet (+0.29 M€):

  | Design | Electric boiler (MW) | €/MWh | Capex (M€) |
  |---|---|---|---|
  | A10 gas-free, shared train | 30.0 | 92.70 | 76.34 |
  | A10 gas-free, train per doublet | 16.6 | 86.39 | 71.18 |
  | B1, shared train | 30.0 | 101.68 | 81.84 |
  | B1, train per doublet | 17.0 | 95.56 | 76.84 |

  CO2 is unchanged in both cases.
- ADR-0013 says "Going gas-free costs about 23 €/MWh more … about 470 €/t avoided". With separate
  trains it is about **16.6 €/MWh and about 342 €/t** (2.25 M€ / 6,576 t).
- **Code**:
  - `engine._gas_free` (stage 4) re-sizes only "the cheapest heat-pump layout", with a shared train.
    The `-ST` variants exist only at stage 2 and never get the electric-boiler N-1 plan. ADR-0011
    notes this gap.
  - With the gas boiler ruled out, `firm.reliable` grows the heat pump to 195.6 MW (B40/B41, 213
    €/MWh, 290 M€) for cases a heat pump cannot cover (doublet or train out: no brine). These
    nonsense rows sit in the Compare library.
- **Fix**:
  - Run stage 4 on the `-ST` variants for two or more doublets.
  - In `reliable`, stop growing a unit when the gap does not shrink (the `improve` step already
    detects this).

### E5. The 600-hour grid contract is not checked in failures, what-ifs or uncertainty (high)
- **Message** (sci-1 t18): "If the ESP of doublet 1 fails from 5 January to 4 May (no spare), how many
  hours does the electric boiler run, does it lose the 600-hour contract …?"
- **Reply**: "still meets heat and cold every day … No spare is needed". The card shows "cost 2050.0
  k€". The question about hours and the contract is not answered.
- **Correct**: local run of that event on B1: the electric boiler takes 11.72 GWh of electricity at a
  13.8 MW peak, **849 h > 600**. `grid_capacity_meur` rises from 0.736 to 3.727 M€, so the event costs
  **4.85 M€**, not 2.05.
  - Over start days: 57 % of the 120-day ESP outages break the contract, +1.56 M€ per failure on
    average.
  - B1 has 2 doublets × 0.5 failures a year, so its expected failure cost is about 3.2 M€ a year, not
    1.65. The spare ESP is worth about 2.8 M€ a year, not 1.2.
  - The same cliff drives the uncertainty. With the return at 50 or 70 °C instead of 60, the electric
    boiler runs 2,626 h or 874 h and B1 costs 129.6 or 129.2 €/MWh instead of 101.7.
  - The agent's driver list (t17) never names it.
- **Code**: `failure_costs.RUNNING_KINDS` (l.47) leaves out "fixed" lines, which include the grid
  charge. The failure card uses the same running-cost difference. The treatment train has no failure
  rate (`kind()` returns None, "skipped"), although it is the case that sizes the gas-free plans.
- Unstated assumption: the contract's operating time is per connection. The plant's heat pump, ESPs and
  chillers run about 8,000 h a year, so the backup boiler needs its own connection to qualify.
- **Fix**:
  - Include the grid-charge difference in `outage_runs`, failure cards and remedies.
  - Show "hours left under 600" as a limit to watch.
  - Give the train a failure rate or say it is not counted.
  - State the separate-connection assumption, or price the standard tariff and non-firm ATR (PBL 91
    €/kW/yr) as options.

### E6. SDE++ paid on the heat pump's electricity; wrong capacity for the "met warmtepomp" categories (medium)
- **Code**: `investor._eligible_gwh` = `geo + hp` (the heat pump's full output, electricity included).
  For a base-load category, PBL's reference has no heat pump, and only geothermal heat counts.
- **Effect**:
  - A1: eligible 56.68 GWh against 53.34 GWh of brine heat. Year-1 SDE++ 3.351 against 3.153 M€; NPV
    34.80 against 33.69 M€.
  - B1: 111.5 GWh (99.8 % of all heat) includes 13.65 GWh of electricity, about 0.59 M€ too much in
    year 1.
- **Inconsistent with itself**:
  - The code's own note rejects the heat-pump categories because the heat pump "only tops up", yet it
    counts the heat pump's whole output.
  - The chat (sci-2 t8) said the opposite of the code: "standard subsidy rules that exclude heat pump
    electricity from the subsidised thermal amount".
- **"With heat pump" categories**: the user can pick them in Economics. PBL (2026, p.13, pp.137–141)
  sets the installation size to the heat pump's thermal output. The code uses the brine capacity (10.61
  MW), so for A1 the subsidised heat is 56.7 GWh instead of at most 2 MW × 6,000 h = 12 GWh. Result: 6.94
  M€ in year 1 and NPV 62.9 M€, both far too high.
- **Fix**: eligible = `geo + hp − electricity.hp` for base-load categories; capacity = `heat_pump_mw`
  for the heat-pump categories.

### E7. Investor heat price: all heat sold at the gas reference's full cost (medium)
- **Evidence**:
  - Every MWh is sold at 92.24 €/MWh (96.62 with the network), on top of SDE++. That includes the 49 %
    made by the gas boiler.
  - SDE++ prices heat at 0.70 × TTF: 19.6 €/MWh long term, 27.3 €/MWh provisional 2026 (PBL Table 4.7).
    ACM's "niet meer dan anders" is a retail ceiling for small consumers, distribution included (ACM
    2026), not a price at the plant gate.
  - Local run, A1 at 40 €/MWh: **NPV −36.7 M€ with SDE++** (IRR negative), against +34.8 M€. The case
    rests on this one input.
  - "It needs no subsidy" (ADR-0013) is true only at the avoided-cost ceiling.
- The chat denied the feature (sci-2 t10): "The plant model has no input for heat selling price … any
  number provided would be a guess". `investor.OVERRIDES` has `heat_sale_eur_per_mwh`.
- **Fix**:
  - Default to a gate price (TTF-linked), or show both cases side by side.
  - Route sale-price what-ifs to `investor_case`.
  - Value lost heat (122 €/MWh in `failure_costs`) at the same sale price for consistency.

### E8. The chat denies features that exist (medium; it undermines every economics answer)
- sci-1 t12: "My plant model has no input for these financial variables".
- sci-1 t13 and t15: "That's outside what I do".
- sci-2 t6: "The provided text does not list a specific line item for 'breakdown costs'".
- sci-2 t10: no heat-price input.
- sci-2 t11: "no input for varying yearly planned service".
- The `parameters` step marks these "unsupported", and intake marks two of them "relevant: false".
  The tabs show the investor case, failure costs and service windows (ADR-0012/0013). The same
  questions worked only when the current design was named, or when the phrasing matched (sci-1 t14,
  t16).
- **Fix**: add investor, failure-economics and service steps to the planner's step kinds with
  held-out phrasings; never answer "no input" for a module the session has.

### E9. The claim checker deletes correct economics and keeps wrong text (medium)
- sci-2 t5 removed 10 sentences, every one equal to the tab (sale prices 96.6 / 36.4 €/MWh, category
  <12 MWth, 54.5 GWh subsidised, 3.2 M€ in year 1, NPV 34.7 / 16.6 M€, payback 7.3 / 12.9 yr). It kept
  "assumes … no other subsidies (like SDE++), and excludes taxes", which is false.
- sci-1 t1 removed two true statements:
  - "The cheapest option … fails if the boiler is out": 20.8 MW short.
  - "The lowest CO₂ option uses two doublets but costs significantly more": 87.6 against 69.8 €/MWh.
- sci-1 t19 removed the correct "0.20 t/MWh is an average emission factor".
- **Fix**: give the checker the investor, failure and firm facts; correct a number before deleting a
  sentence; never keep a sentence that negates a computed result.

### E10. CO2 of the sold gas: the tonnage is withheld and the 79.5 % is not qualified (medium)
- **Replies**:
  - sci-1 t10: B1 "burns no fossil gas … 79.5% less CO₂".
  - sci-1 t11: "The provided text does not give a specific annual tonnage for the *sold* gas". It also
    calls the 4,999 t "electricity generation for pumps and chillers" and gives the plant "roughly 100
    MWth".
- **Correct**:
  - `co2_t.sold_gas_elsewhere` = **3,612.1 t** (17.88 GWh × 0.202). Counted in: 8,610.6 t, **64.7 %**
    less than gas (24,365 t).
  - The 4,998.5 t includes 882.7 t of reservoir CO2 vented when the gas is cleaned. The peak is 30 MW.
  - Factor mismatch: the plant burns the same methane at the stoichiometric 0.1975 t/MWh (3,531 t),
    but the buyer is charged 0.202 t/MWh (3,612 t), 2.3 % apart.
  - Selling is defensible on a displacement view: the methane replaces fossil gas the buyer would burn
    anyway. Against A10 the plant-scope difference (−2,529 t) matches the system difference (about
    −2,531 t). The agent must say this rather than leave the tonnage out.
  - Methane slip from upgrading (0.5–2 %) is not counted.
- **Fix**: put the buyer's tonnage and the plant-scope label in every CO2 claim of a GS design; use one
  CH4 factor.

### E11. The agent cannot explain its own subsurface and network checks (medium)
- **Replies**: breakthrough (sci-1 t8) "I couldn't confirm"; bubble point and ESP depth (t7) "reservoir
  fluid properties … are not provided"; network loss (sci-2 t4) "does not explain how this number was
  derived".
- **Correct**, all reproduced; the inputs are in `subsurface.py` and `network.py`:
  - **Breakthrough**: Gringarten–Sauty, φ 0.20, L 1.5 km, H 100 m, Q 200.8 m³/h, (ρc)aq 2.62 MJ/m³K
    gives 85.4 yr.
  - **Bubble point**: IAPWS G7-04 Henry constants at 86.1 °C, salted out at 0.85 mol/kg NaCl, give
    43.4 bar(a). Methane sets it (42.1 bar).
  - **ESP depth**: the intake stays above bubble + 5 bar at 732 m. The GEMINI intake is 49.3 bar(g) at
    750 m.
  - **Network**: DN350 with U = 0.20 + 0.0008 × 350 = 0.48 W/m/K over 5 km gives 336 kW = 2.94 GWh.
    It is a trunk only; distribution and service pipes, which make most of the 10–25 % in real Dutch
    networks (TNO 2020, Table 3), are not modelled.
- **Fix**: add the check inputs and the network summary (DN, U, temperatures, "trunk only") to the
  design block.

### E12. The 40 K-cap answer has wrong physics and made-up numbers (medium)
- **Message** (sci-1 t6): "In A1 the brine is cooled by at most 31 K, while the cap is 40 K. Why not use
  the full 40 K …?"
- **Reply**: COP falls because "the temperature difference ($\Delta T$) between the brine and the ambient
  air (or ground source) decreases"; "tested 807 sizings"; "87 °C − 31 K ≈ 56 °C"; the cap is "derived
  from … section 3.1" and prevents "thermal shock or fracturing".
- **Correct**:
  - The heat pump's sink is the 100 °C network: colder brine at the evaporator outlet means a larger
    lift and a lower COP (0.5 × 373 K / lift).
  - The search ran 280 sizings (500 counting the gas-free stage); the reply's 807 appears nowhere.
  - Coldest reinjection is 52.1 °C, from 83.1 °C at the wellhead that day.
  - The caps are in "Design and operating constraints", and the requirements give no reason for the
    cap.
  - The 31 K results from the 2 MW heat pump (E3).

### E13. Monte Carlo ranges are not centred on the case, so the median sits above the base (medium)
- **Evidence**: `agent._uncertainty` draws uniformly from these ranges:

  | Input | Range | Base |
  |---|---|---|
  | CO2 price | 40–200 €/t (middle 120) | 73.9 €/t |
  | Reservoir temperature | −10 to +5 K | 0 |
  | Capex | ×0.8–1.3 | ×1.0 |
  | Discount rate | 3–8 % | 5.2 % |
  | Heat return | 45–70 °C | 60 °C |

- Results:
  - A1: base 69.8, P50 74.4.
  - B1: base 101.7, P50 121.6 (the agent's "95.4 to 150.3").
  - B1 with ranges centred on the base: P50 108.2, P10–P90 91.2–136.5. The rest of the shift is the
    600-hour cliff (E5).
- **Fix**:
  - Centre the ranges on the case (or draw triangular with mode = base).
  - State the base's percentile.
  - Name the cliff when it drives the spread.

### E14. Service windows ignore the doublets' planned stops (low)
- **Local run**, `planned_service` on: the cheapest 1D-HP-AB's single boiler goes into service from 29
  Jul, inside the doublet's stop (9 Jul–12 Aug), which leaves 7 days short (2.67 MW). Both are placed
  in the "quietest weeks", so they collide by construction. A1 (3 boiler units) is unaffected.
- **Code**: `service.windows` does not count a doublet stop as a heating unit out.
- **Fix**: add the doublet stops to `taken` for the heating side.
- The inputs card also ignored "include the yearly service windows" twice (sci-2 t1–2).

### E15. Inconsistencies between the PDF, the tabs and the chat (low)
- The PDF (sci-2) lists "Not modelled: … network losses and pumping" but its own year includes 2.94 GWh
  of loss and 1.19 GWh of network pumping.
- "Heat covered … 114.6 of 114.6 GWh/yr" calls the plant's load (demand + losses) "demand"; the
  buildings' demand is 111.67 GWh.
- The cover shows payback 10 yr / NPV 27.2 M€ (against gas, society) while the investor view says 7.3
  yr / 34.7 M€, with no note on which is which.
- After the second search in sci-1, design A1 was renamed G1 in the tabs while the chat kept saying A1.
  The sensitivity API then rejected "A1" (ADR-0011 promises one name per design).

### E16. Smaller points (low)
- **N-1 called a requirement**: the chat said "N-1 reliability requirement" (sci-1 t9); the challenge
  does not ask for it (ADR-0011).
- **Grid factor**: 0.20 t/MWh is an average.
  - For an electric boiler that runs in winter peaks and failure events, a gas-fired marginal factor
    (about 0.35–0.45) is the relevant one. "79.5 % … regardless of the specific grid mix" (sci-1 t19)
    is false: at 0.37 the plant-scope saving is about 66 %.
  - I could not verify the CBS value offline. Other public series put the Netherlands above 0.2 for
    2023–24; please re-check.
- **"Heat pump below Carnot" check**: it cannot fail (COP = 0.5 × Carnot by construction), and it sets
  the year's COP against Carnot at the coldest source.
- **Cooling-network gain**: the free cooling uses ground at 10 °C all year (0.44 GWh). At pipe depth in
  July the ground is about 15–18 °C.
- **GEMINI exchanger**: GEMINI's duty (7.595 MW) does not match its own temperatures (85.8 kg/s × 3,990
  × 20.67 K = 7.08 MW). Its exchanger uses other fluid properties (ρc ≈ 4.41 MJ/m³K), and the check
  differs from the plant model by 5.1 %.
- **Two capacities**: the SDE++ capacity is cap flow × the year's largest cooling (10.61 MW for A1),
  while the surface plant is priced on the peak brine heat (8.80 MW).
- **Value of lost heat**: 122 €/MWh (ACM retail ceiling) in failures, against 92.24 €/MWh as the
  investor's sale price.

## 4. What is sound

- **Energy and CO2 balances close.** Heat 41.75 + 14.93 + 54.99 = 111.67 GWh. Brine side: 53.34 GWh of
  brine heat from 1.759 Mm³ is a mean cooling of 26.6 K. Chiller COP 8.56 and tower power 0.0125 ×
  rejected heat check out. The CO2 split reproduces by hand.
- **Well physics checks out.**
  - Productivity index 14.51 m³/h/bar from radial inflow (200 mD × 100 m, 0.4 mPa·s).
  - ESP head 32.8 bar: 5 + 252.6 + 4.6 − 229.3. Power 0.391 MW = 0.0833 × 32.8e5 / 0.7.
  - Injection 22.6 bar; SodM limit 0.135 × 2,450 = 330.8 bar against 266 bar.
  - GEMINI agrees on intake, head and injection pressure.
  - Bubble point (43.4 bar), ESP depth (732 m) and Gringarten–Sauty (85.4 yr) reproduce exactly.
- **Costs are traceable and close to PBL.**
  - ThermoGIS wells: 5.479 M€ each.
  - Geothermal part about 2,530 €/kW against PBL's 2,463 €/kW for <12 MWth.
  - Gas reference 92.24 / 36.17 €/MWh.
  - Electric boiler 407 €/kW; Liander 123 and 23.94 €/kW/yr.
  - Sold gas: 0.697 M€ revenue against 0.562 M€ of cleaning, at about 257 Nm³/h (above the 150 Nm³/h
    economic floor).
  - `numbers_2026-10-31.md` is an unusually well-sourced basis.
- **Failure economics reproduce.**
  - A1: 928 / 219 k€; spare break-even at one failure in 71 yr.
  - Cheapest design: 1,286 MWh not delivered; 13.7 M€ a year at the stress value.
  - B1: 1,653 / 427 k€.
  - Method: rate × repair share of the all-year outage, stated first-order.
- **The N-1 logic is right.** Boiler-unit-out sets 3 × 10.4 MW (20.8 + 7.23 + 2.0 = 30.03 MW), and a
  doublet out is covered (31.2 ≥ 30 MW).
- **Sensitivity slopes match the ledger.** Gas 0.345 €/MWh per €/MWh (= 46.69 / 135.41 GWh); CO2 0.090
  t/MWh.
- **Some economics answers in the chat matched the tab when they did get through.** B1's investor view
  (NPV −13.4 M€, IRR 3.3 %, ≥20 MWth at 62.7 €/MWh) and failure costs; IRRs labelled "real".
