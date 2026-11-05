# Panel report: energy economist

Server http://127.0.0.1:8791. Threads `econ-1` (cost design, what-ifs, Economics tab) and `econ-2` (lowest-CO2 design). 13 chat turns, plus `design … economics`, `prices`, `sensitivity` (tornado, spider, Monte Carlo) and one user design (`U1`). I checked every number below in Python. My scripts are in `/tmp/claude-1978995908/-home-rn2038-Projects-GEOHACKATHON/b6915066-9ab1-4789-b907-6d653b215277/scratchpad/econ/`.

## 1. Verdict

The cost engine is honest and exact. Every €/MWh rebuilds from its lines, the CO2 accounting includes the produced gas, and the sources are better than most consultancy work. The numbers an investor would act on are another matter: they are too optimistic and too fragile. The geothermal capex and fixed O&M sit 20-35 % below PBL's SDE++ 2026 figures, although the code and ADR-0008 say they match PBL. With PBL-consistent costs the pick changes from two doublets to one. Even at the team's own costs, the "cheapest" design wins by 0.1-1 €/MWh, while the inputs move the cost by 5-13 €/MWh. The chat is the weakest part. It made up the gas reference cost ("roughly 150–200 €/MWh"; the real figure is 82-92). It said a design was "still the cheapest at your prices" when four designs were 4 €/MWh cheaper. It refused to give the NPV and payback that its own Economics tab shows. A jury that asks about money in chat will catch it out.

## 2. What works

- **The arithmetic is exact and traceable.** I rebuilt 2D-HP-AB from its capex items, annuity factors (CRF), O&M, energy and CO2 lines: LCOH 64.25, LCOC 50.08, LCOE 61.77 €/MWh, matching to the cent. The NPV against gas also matches: −38.53 + 5.39 × 15.028 = 42.47 M€ (tool 42.48). The gas reference rebuilds too: opex 10.82 M€/yr, LCOH 92.2 €/MWh.
- **The sources are excellent.** `cost_sources.md` cites page and table, converts price years (DEA 2020→2025, CEPCI, FX) and states its caveats (C1-C13). Every `Prices` field has a `SOURCES` entry. The inputs card shows the prices and their sources before the run. The one home-made number, the treatment train, is flagged, and it matters little: ±100 % moves LCOE by about ±0.4 €/MWh.
- **The CO2 accounting is honest.** The produced gas is charged in full (4,413 t/yr, 46 % of the design's CO2). Electricity CO2 is counted at 0.20 t/MWh (CBS 2024) but not priced a second time, which is right because ETS costs are already in the power price. The reference is like for like: boilers plus electric chillers at the same prices.
- **The tools are fast and well built.** A 36-run tornado takes 0.22 s, a 300-sample Monte Carlo takes seconds, and repricing is instant. A price what-if in chat really re-runs the search, and it found the new pick both times (gas/electricity, and an 8 % discount rate).
- **Splitting shared costs by the brine heat each side uses** is defensible and documented. The Economics tab tile ("NPV against gas … pays back in year 10") is the right thing to show.

## 3. Issues (most important first)

### H1 (high): the chat states made-up or stale money facts that decide the investment case
- **Made-up gas reference.** I said (econ-1, after changing prices in the Economics tab to gas 40 and electricity 130): *"I changed the prices in the Economics tab. At my prices, is 2D-HP-AB still the cheapest design, and what does it cost against the gas reference?"* It replied: *"Yes, **2D-HP-AB** remains the cheapest design at your new prices. Its cost of heat and cold together is **61.8 €/MWh**, which is lower than the gas reference (which would be roughly 150–200 €/MWh …)"*. All three parts are wrong:
  - at those prices 2D-HP-AB costs 53.82, not 61.8;
  - four one-doublet designs are 4.0-4.3 €/MWh cheaper (1D-HP-EC 49.49);
  - the gas reference is 55.6 €/MWh LCOE (61.3 for heat), or 82.4 (92.2) at the default prices.

  The claim check passed it (`checked 4, removed []`). The made-up figure came back in a later turn: *"still lower than the gas reference (roughly 150–200 €/MWh)"* (8 % discount-rate what-if).
- **What-if misreported.** I asked: *"What if gas costs 40 EUR/MWh and electricity 130 EUR/MWh … tell me whether the pick changes and whether geothermal still beats gas."* It replied: *"the optimal pick changes to **1D-HP-EC**. The heat cost drops to **49.1 €/MWh**, while CO₂ savings remain at **60.4%**"*, with a table of 49.1 against 64.2.
  - 49.1 is the LCOE; the heat cost is 53.45.
  - The new pick saves 42.1 % CO2, not 60.4 % (that figure belongs to the old design).
  - The table sets the new design at the new prices against the old design at the old prices. At the new prices 2D-HP-AB costs 56.08 €/MWh heat (53.82 LCOE).
  - The real trade-off was hidden: cheap gas buys a design with 46 % more CO2.
- **It contradicts itself.** Discount-rate what-if: *"Yes, **2D-HP-AB** stays the pick"*, and in the same reply: *"Searching again under the change picks 1D-HP-EC at 66.8 €/MWh instead of 2D-HP-AB"*.
- **False claim in the first answer.** It said *"beats the runner-up (2D-HP-EC) by saving costs while maintaining superior CO₂ performance"*. The runner-up emits less: 9,276 t against 9,655 t.
- **Why it matters.** The gas reference and "is it still the cheapest" are the two numbers a jury or investor remembers. Overstating gas by 2-3× makes geothermal look far better than it is.
- **Causes I found:**
  - `answer.economics_block` sends the cost lines and capex only: no gas-reference cost, no `versus_reference`, no current prices, no user overrides.
  - `reporter.Facts.ungrounded` matches bare numbers regardless of unit, so "200" passes because "200 mD" is in the context.
  - The conversation history carries unchecked numbers into later turns.
- **Do instead:**
  - Put the reference's LCOH/LCOC/LCOE, `versus_reference` (extra capex, savings, NPV, payback) and the prices in force (marked "your price" or "default, source") into the cost block.
  - Make the number check match number plus unit.
  - When the user's prices reorder the candidates, have the chat say so ("at your prices 1D-HP-EC is 4.3 €/MWh cheaper; run the search again?").

### H2 (high): geothermal capex and fixed O&M are 20-35 % below PBL 2026, but the code says they "match PBL"
- **The claim.** `SOURCES["surface_per_doublet_meur"]` says "matches PBL's total capex", and ADR-0008 says "ThermoGIS v2 surface plant (matching PBL's total)".
- **What the code actually prices.** It combines ThermoGIS **v3** wells (5.48 M€ per well at 2,500 m, per-well reading) with the **v2** surface plant (3.45 M€ + 345 €/kW). `cost_sources.md` row 1.4 recommends the v3 surface cost (3.5 M€ + 882 €/kW), and only that combination reproduces PBL.
- **One doublet, priced three ways:**

| Doublet size | Code | ThermoGIS v3 | PBL 2026 (Tables 11.7a–c) | Code vs PBL |
|---|---|---|---|---|
| 27.4 MW | 23.9 M€ (871 €/kW) | 38.6 M€ (1,410 €/kW) | 36.7 M€ (1,340 €/kW) | −35 % |
| 8.7 MW | 17.4 M€ | 22.1 M€ | 21.4 M€ | −19 % |

- **Fixed O&M** uses ThermoGIS's 81 €/kW/yr, while PBL uses 121 (with insurance, staff and ESP provisions). It is charged on peak brine heat, not on installed doublets, so lightly used doublets look cheap to run. The 9-well design pays 0.64 M€/yr per doublet; PBL implies 1.0-1.9 M€/yr per doublet. ESPs in Dutch wells run 1-2 years on average (cost_sources C5).
- **Test.** I set `prices` to `{"surface_per_doublet_meur": 3.5, "surface_meur_per_mw": 0.882, "geothermal_fixed_eur_per_kw": 121}`. Result:
  - 2D-HP-AB: LCOH 64.25 → **75.29 €/MWh**, capex 43.2 → 52.7 M€, NPV against gas 42.5 → 22.4 M€, payback 10 → 16 years;
  - **the cost pick becomes 1D-HP-EC** (LCOE 68.18 against 71.62), and the four cheapest designs all have one doublet;
  - the Compare tab still says "chosen 2D-HP-AB".
- **Why it matters.** The headline LCOH, the number of wells (4 against 2, about 17.6 M€ of capital at risk) and the NPV all rest on a calibration claim that is not true.
- **Do instead.**
  - Use the v3 surface formula with the v3 wells, or calibrate to PBL by category.
  - Charge fixed O&M per installed doublet or well (an ESP provision per ESP, e.g. 63.5-95 k€/yr, S6) plus a per-kW part.
  - Correct the SOURCES text and ADR-0008, then re-run the evals. If the team keeps the cheaper set, say "ThermoGIS v2-based, about 20-35 % below PBL 2026" next to every LCOH.

### H3 (high): the cost pick sits on a knife edge but is presented as a clear win
- **What I did.** I ran a sensitivity on 2D-HP-AB and on the runner-up layout recreated as `U1` (1 doublet, HP 3.3 MW, boiler 19.5 MW, chillers 10 MW; LCOE 62.69 = the 1D-HP-EC candidate). I compared the spider curves point by point.
- **The margin.** The pick beats five rivals by 0.1-1.0 €/MWh. The tornado on 2D-HP-AB moves LCOH by 59.7-75.7 (capex ×0.8-1.5), 59.1-77.4 (discount rate 3-10 %) and 57.9-77.7 (reservoir −10/+5 K). The NPV against gas ranges from **−3.2 M€ (gas 40 €/MWh)** to +90 M€ (gas 100).
- **The pick changes to 1D-HP-EC** when any one of these moves:
  - gas below about 65 €/MWh (the 2026-S1 band-I4 price is 73.8 LHV; PBL's long-term TTF of 28 implies roughly 58 retail);
  - carbon price below about 60 €/t;
  - capex +10-15 %;
  - real discount rate above about 6.3 %;
  - reservoir 3-6 K colder;
  - heating return below about 60 °C (the assumed value sits exactly at the crossover).
- **Monte Carlo** (300 samples, uniform over gas 40-100, electricity 131-220, carbon 0-137, capex ×0.8-1.5, discount rate 3-10 %):

| | 2D-HP-AB | 1D-HP-EC (U1) |
|---|---|---|
| LCOE P10 / P50 / P90 (€/MWh) | 55.9 / 66.3 / 80.1 | 54.4 / 64.9 / 75.9 |
| NPV against gas, P10 / mean (M€) | **−9.4** / 29.4 | **+2.6** / 31.9 |

  Under uncertainty the one-doublet design is cheaper on average and safer on the downside. The two-doublet design buys 3,312 t/yr more CO2 saving.
- **Why it matters.** A jury will ask "how sure are you?". The honest answer is "it's a tie on cost, and the choice is about carbon and capital at risk". At PBL-consistent costs the second doublet abates CO2 at about 141 €/t (3.44 €/MWh × 135.4 GWh ÷ 3,312 t), close to PBL's long-term ETS price of 137 €/t. That is a strong, honest story, and the agent doesn't tell it.
- **Do instead.**
  - Treat candidates within about 2 €/MWh as tied.
  - Break ties by P10 NPV or P90 LCOE (the Monte Carlo already exists), capital at risk and CO2.
  - Report "probability of being cheapest" and the €/t of each step up in CO2 saving.

### H4 (high): finance questions get refusals, canned text or false promises
- **NPV and payback.** I asked: *"What is the payback time and the NPV of 2D-HP-AB against the gas reference? …"*.
  - The model wrote *"I cannot compute the payback time or NPV … the context does not include the gas reference costs, discount rates …"*.
  - The claim check then removed 6 sentences, and the user received an unrelated canned description of the wells.
  - Payback (10 years, discounted) and NPV (42.48 M€) are in `versus_reference`, but not in the answer context.
- **SDE++.** I asked: *"Does your 64.2 EUR/MWh include the SDE++ subsidy? … is 64.2 what the customer pays?"*.
  - The checker removed the correct sentences ("64.2 … without any subsidy applied", "the cost before SDE++").
  - What remained was: *"Once provided, I can re-run the economics with that subsidy included and tell you the new customer price."* That is a fragment and a false capability: no SDE++ input exists in `Prices`, `prices` or `sensitivity`.
  - The removed text was also wrong on economics: SDE++ pays the producer the gap between the base amount and the correction amount (15 years); it does not cut the customer's price by the subsidy.
  - The customer question went unanswered. LCOH is the cost at the plant gate, without the network, losses, retail margin, VAT or the ACM price cap.
- **Uncertainty.** I asked: *"How sure are you of the 64 EUR/MWh …? Give me a range and the three inputs that move it most."* It replied: *"I am not sure of a precise range because the context does not list input uncertainties"*. It then listed the biggest **cost lines** as the inputs that "move it most", which confuses cost size with sensitivity. It also offered a confidence interval "if you provide standard deviations", which chat cannot do. The Sensitivity tab with Monte Carlo exists.
- **CO2 accounting, carbon price, discount rate, lifetimes.** Two "explain" questions returned the canned design text (`fallback: true`, "the answering model gave no usable reply"). A simpler rewording got *"The provided context does not list the specific grid CO₂ factor or the carbon price"*, although both were on its own inputs card. It also missed the heat side's produced-gas CO2 line (2.7 €/MWh).
- **Do instead.**
  - Add to the cost block: the prices, CO2 factors, carbon price, discount rate, lifetimes and `versus_reference`, plus a fixed line "not modelled: SDE++, taxes, network and retail, heat tariff".
  - Let chat call `sensitivity` for "how sure" questions.
  - Replace the canned fallback with "I could not answer this; the numbers are in the Economics tab (…)" and a retry.
  - Stop the claim check from deleting true "not included" statements: it should check against a not-modelled list as well as the data.

### H5 (medium-high): "lowest CO2" picks a design at 3,600-10,000 €/t, and the reply hides it
- **What I did.** econ-2: *"Design the challenge district for the lowest CO2, but tell me what each tonne of CO2 avoided costs …"*.
  - First, the card said "Design for: lowest cost" and I had to correct it.
  - The pick was 3D-HP-EC-2I: 9 wells, capex 82.7 M€, LCOH 90.6 €/MWh, 71.6 % saving, NPV against gas 3.7 M€, payback 28 years.
  - The reply gave no €/t. Asked again, it computed the tonnes (*"7,129 - 6,925 = 204 t"*) but no €/t. The checker removed its only conclusion (*"At a carbon price of 74 EUR/t, the savings … do not offset its higher … cost"*), which was correct.
- **The real figures.** Against 2D-HP-EC in the same search, the pick avoids 204 t/yr for 2.10 M€/yr more: **about 10,250 €/t**. Against 2D-HP-AB it is 3,600 €/t, and against 1D-HP-EC 589 €/t. That is 8-140 times the carbon price.
- **Do instead.** Make "lowest CO2" mean either the lowest cost at a stated shadow carbon price (e.g. PBL's 137 €/t), or the lowest CO2 within +x €/MWh of the cost pick. Show a marginal abatement cost curve (MACC) across the candidates. The data is already in `attempts`.

### M1 (medium): the Compare tab shows the wrong search and a stale "chosen"
- **Wrong search.** After the price what-if, attempt S2 ("chosen 1D-HP-EC") lists **S1's candidates at the old prices**, with "2D-HP-AB chosen, LCOE 61.77" and S1's reference (92.24). Cause: `workbench.attempts_view` uses `session.candidates` for the latest search.
- **Stale "chosen".** After `prices`, the label stays on 2D-HP-AB while four rivals show "−4.3 €/MWh … at your prices", and after the PBL test it ranks 5th.
- **Do instead.** Store and show each search's own candidates. When repricing reorders them, mark "cheapest at your prices: X" next to the original "chosen".

### M2 (medium): the NPV, payback and price paths need labels and two fixes
- **Payback** "in year 10" is a *discounted* payback; the simple payback is 7.1 years. Label it.
- **Replacements.** `versus_reference` adds no replacements (heat pump, boiler and chillers at 25 years, absorption at 20). That is inconsistent with the LCOH, which annualises each unit over its own life. The present-value gap is about 1.2 M€, small but easy to fix.
- **What the NPV is.** It is a cost-saving NPV against gas: no revenue, tax or subsidy. Say so on the tile.
- **Flat prices for 30 years.** The 2025 ETS price (73.9 €/t) and 2025 retail gas are held constant. Carbon alone moves the NPV from 24 M€ (0 €/t) to 58 M€ (137 €/t), and gas moves it from −3 to +90 M€.
- **Do instead.** Offer a "PBL long-term" price set (ETS 137 €/t, TTF 28 €/MWh LHV plus today's taxes and network charges) next to "2025 spot". Make the default sensitivity range for gas two-sided: it is now 25-70 around a 69.4 base, so it has no upside case.

### M3 (medium): the produced gas is a big, under-explained driver
- **Its value.** Burning the produced gas (17.9 GWh/yr) is worth 1.24 M€/yr, or **11.1 €/MWh of heat**. Its CO2 is 46 % of the design's emissions.
- **The agent got it wrong.** I asked how much it saves; the reply was *"saves **8.9 €/MWh** compared to buying grid electricity"*. That is the wrong number (8.9 is the cost of the gas still bought) and the wrong comparison (the produced gas replaces bought gas, not electricity).
- **What isn't costed.** The 80/20 CH4/CO2 gas has a Wobbe index of about 37 MJ/Nm³, far below G-gas, so the boiler needs a low-calorific burner and gas conditioning. Using the gas may also need a Mining Act licence (PBL p.127 flags it as a regulatory issue). Neither is in the costs.
- **The grid factor** moves the CO2 saving between 50 % (0.45, fossil-marginal) and 63 % (0.13, PBL marginal), and there is no sensitivity key for it.
- **Do instead.** Show "produced gas: 11 €/MWh saved, 46 % of CO2". Add a key for the fate of the produced gas (burn, flare, re-inject) and one for the grid factor.

### M4 (medium): costs an investor or lender would ask for are missing, and some are cheap to add
- **No N-1 backup.** No such check exists anywhere in `dioscuri_plant`, the verifier or the engine. 3D-HP-EC-2I has a 3.8 MW boiler for a 30 MW peak, so one ESP failure in January leaves customers cold. Backup boilers cost 0.075 M€/MW, so N-1 cover costs about 1 €/MWh and buys a lot of credibility.
- **Other omissions:** ESP replacement and workover per well; exploration and dry-hole risk (the RNES guarantee scheme); interest during construction; grid connection (and congestion risk) for MW-scale heat pumps; abandonment; and the heat network and retail costs, so LCOH is not the customer price.
- **Do instead.** Add N-1 as a check and a cost line. List the rest in a visible "not included" box on the Economics tab, which the chat should also see.

### L1 (low): price bands and line names
- **Gas band.** The design buys 14.3 GWh of gas, which is band I3 (about 84.6 €/MWh LHV), not I4 (69.4): +1.9 €/MWh LCOH. Electricity band ID is right for this design (11.8 GWh), but the band is fixed for all designs; heat-pump-heavy designs above 20 GWh belong in band IE at 130.7 €/MWh. Pick the band from each design's own volumes.
- **Line names.** Two lines are both called "Surface plant" (3.14 and 3.33 €/MWh), because economics.py strips "(per MW)". This garbled the agent's top-5 ranking: it listed 11.7 above 12.1 and 8.4 above 8.9, and missed pump electricity at 6.35. Name them "Surface plant (per doublet)" and "(per MW)".
- **Heat pump COP.** The year's COP is 4.6 (23.24/5.04 GWh), against PBL's SPF of 2.9 for 90-120 °C networks; at 2.9, LCOH rises about 5 €/MWh. The engineer on the panel should check this.

## 4. Implement differently or remove

- **Ranking:** replace "lowest point LCOE wins" with a near-tie band plus robustness (P10 NPV, P90 LCOE, probability of being cheapest from the existing Monte Carlo) and capital at risk.
- **CO2 objective:** replace the pure "lowest CO2" ranking with "cost at a shadow carbon price" or "CO2 within a cost cap", and show the €/t of each step (MACC).
- **Remove** the "matching PBL's total" statements (SOURCES, ADR-0008) unless the costs are recalibrated.
- **Remove** offers the tool cannot keep ("I can re-run with that subsidy", "a confidence interval if you provide standard deviations").
- **Chat cost block:** add the gas reference, `versus_reference`, live prices (with user overrides), CO2 factors, carbon price, discount rate, lifetimes and a not-modelled list.
- **Checks:** make the number check unit-aware, and stop unchecked numbers from earlier turns carrying forward.
- **Fallback:** an honest "couldn't answer" instead of the canned design summary (3 of my 13 turns got it).
- **Compare tab:** fix `attempts_view` (each search's own candidates); flag "cheapest at your prices" after repricing.
- **NPV:** include replacements, label "discounted payback", and state "cost-saving NPV, no revenue, tax or subsidy" on the tile.

## 5. Top 3 priorities before the deadline

1. **Ground the chat's money answers.** Feed the answerer the gas reference, NPV and payback, the prices in force and the CO2 factors; make the number check unit-aware; list what is not modelled (SDE++, taxes, network, tariff); replace the canned fallback. Then re-ask the exact messages quoted in H1 and H4. Today the chat can make up the competitor's cost and contradict the tabs.
2. **Recalibrate geothermal capex and O&M to PBL 2026, or show both cases, and correct the "matches PBL" claims.** Expect the cost pick to become 1D-HP-EC (LCOE about 68, against 71.6 for 2D-HP-AB) and say so plainly. If you keep the cheaper cost set, label every LCOH with it.
3. **Present the decision as a robust trade-off, not a 0.9 €/MWh win.** Report the near-tie, the Monte Carlo downside (P10 NPV −9.4 against +2.6 M€) and the abatement cost of the second doublet (about 141 €/t at PBL-consistent costs, against PBL's 137 €/t long-term ETS price), plus a long-term carbon and gas price case. Add N-1 backup cover. If time allows, add SDE++ as an optional revenue line: base amount (PBL Table 11.13 category) minus a gas-linked correction amount, for 15 years.
