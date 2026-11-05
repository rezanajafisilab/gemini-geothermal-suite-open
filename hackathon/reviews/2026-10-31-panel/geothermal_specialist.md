# Review: geothermal specialist (deep doublets for district heating, NL and DE)

Server http://127.0.0.1:8790, threads `geo-1` (13 turns: base design, what-ifs, follow-ups) and `geo-2` (4 turns: 3,200 m wells). I also used `edit`, `sensitivity` and `gemini`, read `src/dioscuri_plant/*` and `tools/gemini.py`, and checked the numbers in `scratchpad/geo/check.py`.

## 1. Verdict

As a concept, the recommended 2D-HP-AB is broadly the right shape: two doublets in the known 2,500 m aquifer, 86.1 °C at the wellhead, a balanced exchanger to 81 °C, a heat-pump and boiler top-up to 100 °C, and reinjection at 56 °C. The well and brine numbers behind it are correct within the model. I would still **not sign it off**, for three reasons:
- It has no N-1 cover. With one doublet out, the plant is 7.2 MW short on 28 January.
- It is sized with zero margin: 14.46 + 3.9 + 11.7 MW = 30.06 MW against a 30.0 MW peak. A reservoir only 2.5 K colder than assumed already breaks the 100 °C supply.
- When pushed past its numbers, the agent does not hold up. It recommends a 3,200 m single doublet without saying it assumed the same 200 mD × 100 m sandstone there. It does not know its own well spacing or absorption COP. It denies flaring gas that its own year shows being flared. Asked about risks, it deleted its own (correct) risk list.

A technical reviewer would trust the tables and not the explanations.

## 2. What works

- **The inputs card is good practice.** Every input is tagged data, fixed, derived, assumed or asked, with its source. The 60 °C return, the brine cp of 3,990 and the reading of the 330 days are visibly flagged as assumptions.
- **The core physics matches my hand calculations within 0.1 %:**
  - PI 14.51 m³/h/bar from kh = 20 D·m;
  - ESP head 32.8 bar and 0.39 MW at 300 m³/h;
  - Ramey loss 0.9 K at 300 m³/h and 5.2 K at 50 m³/h;
  - 87 °C from the gradient, and 108 °C and 323.3 bar (hydrostatic) at 3,200 m;
  - produced gas 2.25 M Nm³/yr, i.e. 17.88 GWh of CH₄ and 4,413 t CO₂ (both the CH₄ burnt and the native 20 % CO₂ are counted).
  The 40 K cap, the 50–300 m³/h window and the daily energy balance are checked per doublet per day.
- **The search argues with numbers, and mostly the right ones:**
  - two injectors: "+11.0 M€ of capital for the extra injector(s), −1.05 GWh a year of pumping … +3.9 €/MWh";
  - half-open producer: "wellhead 86.8 °C against 86.1 °C, ESP head 54 bar against 33 bar".
  - Under a 50 mD what-if, the re-search picks a producer with two injectors (`1D-BO-EC@3200-2I`), which is what practice does when injectivity is the limit.
- **What-ifs report failures honestly.**
  - 70 °C return: "covers only 97.1% … worst-case shortfall of 6.79 MW on 28 January".
  - Reservoir 5 K colder: "cannot meet the 100 °C supply temperature on 20 days … 3.37 MW".
- **Sensible defaults.** It uses the known aquifer unless asked otherwise (ADR-0010). The two doublets' 35-day stops are staggered in late May to mid-August, when one doublet carries the load.

## 3. Issues (most important first)

### H1. The deeper-well pick rests on an aquifer the agent never states, and its reply misstates the brief (high)

**What I did.** In `geo-2`: *"Design … with wells drilled to 3,200 m instead of the 2,500 m aquifer. Tell me what reservoir temperature, pressure, permeability and thickness you assume at 3,200 m, and on what basis."*

**What happened.**
- The reply: *"The context does not specify permeability or thickness values for this specific depth; it only notes that the requirements … describe no aquifer at 2,500 m."* (It means 3,200 m.)
- It then recommends `1D-BO-EC@3200`: *"3,200 m wins: 12.9 €/MWh cheaper."*
- The design record shows what it actually used: `{"depth_m": 3200, "temperature_c": 108.0, "pressure_bar": 323.3, "permeability_md": 200.0, "thickness_m": 100.0}`.
- I asked again. The reply: *"the context does not specify the permeability or thickness; these were inputs to the simulation."*
- The inputs card contradicts itself. It lists "Wells drilled into: the known aquifer only; also assumed aquifers at 3,200 m" and also "Not modelled: wells drilled to 3,200 m".

**Why it matters.** The recommendation flips from 2 doublets (61.8 €/MWh) to 1 doublet (48.9 €/MWh) on a sandstone that nobody has described. Its permeability is copied from 700 m shallower, although compaction and cementation usually reduce permeability with depth.
- At 50 mD the design rises to 59.2 €/MWh (heat and cold).
- The pumps at 300 m³/h then need 93.5 bar of ESP head and 88.5 bar at the injection wellhead (406 bar at the sandface).
- The agent shows these without a word of warning.

No subsurface reviewer accepts an undescribed reservoir as the base case.

**What to do instead.**
- State the assumed aquifer in the card and in the reply: T, P, k, h, and "no data".
- Label the pick as speculative.
- Show the break-even permeability, or a k-at-depth sensitivity, in the same answer.
- Fix the "no aquifer at 2,500 m" wording.

### H2. No N-1 cover and zero-margin sizing (high)

**What I did.**
- `edit` 2D-HP-AB with `n_doublets: 1` (same HP and boiler): *"Heat short of 100 °C supply on 70 day(s): worst 7.17 MW on 28 Jan."*
- Sensitivity on reservoir temperature: −2.5 K already gives 1 violation, and −10 K gives LCOE 73.3 with 1 violation.
- Then I asked: *"If one of the two doublets of 2D-HP-AB trips on the peak day, 28 January, can the plant still supply 30 MW … how big must the boiler be for N-1 cover, and what does that cost?"*

**What happened.** The reply says *"it would be a substantial upgrade from the current 43.2 M€ total capital cost"*, with no number. The model's own boiler price gives 7.17 MW × 0.075 M€/MW = **0.54 M€, or 1.2 % of capex**. The parameter step marked the analysis as "unsupported".

**Why it matters.** ESP failure is the most common outage on Dutch doublets: runs of 2–3 years, then weeks for a workover. District heating operators size peak and backup boilers so they can carry the peak with the largest source out, precisely because boilers are cheap. "Fix what broke" grows units only to the deterministic year, so any error in temperature, return or demand turns into unserved heat.

**What to do instead.**
- Add a requirement-level check: the largest doublet out on the peak day.
- Always size the boiler for that case.
- Report a robustness band: −5 K reservoir and +10 K return.

### H3. The claim checker removes correct engineering content but lets false statements through (high)

**(a) The risk answer was deleted.** Message: *"which subsurface and operational risks of this doublet design does your model not capture, and how big could each one be?"*
- `claims` removed 11 sentences, including: *"heterogeneity (fractures, permeable layers) causes thermal breakthrough to be uneven"* and *"The model assumes constant injectivity…"*.
- What was shown instead is a generic design summary that does not answer the question.

**(b) A false statement on flaring passed.** Message: *"In 1D-BO-EC@3200, how much produced gas do you flare each year …"*
- Reply: *"the produced gas is not flared; it is burned in the backup boiler"*.
- The year shows `produced_gas_flared_gwh: 3.622`. Removed: 0.
- The requested CO₂ figure (2,763 t/yr) is missing.

**(c) A false statement on the variants passed.** In the variants answer, the checker removed the separator bullet's header and left *"It was not selected as a standalone variant in the final cost sweep"*. In fact 2D-HP-AB-ST was the runner-up, at 61.91 against 61.77.

**(d) A wrong label passed.** In the 70 °C what-if: *"Exchanger outlet (brine at wellhead): 86.1 °C"*. The exchanger outlet is 81.1 °C on the network side and about 75 °C on the brine side.

**What to do instead.**
- Check numbers and yes/no facts against the design data: flared GWh, which variants were run.
- Do not delete qualitative engineering statements.
- If more than half the answer is removed, regenerate instead of falling back to a summary.

### H4. The agent does not know its own assumptions (high)

- **Spacing and breakthrough.** Asked about spacing and the cold front: *"The context does not specify the exact distance … Without these distances, we cannot calculate when the cold front reaches the producer."*
  - The economics uses `well_spacing_m = 1500`.
  - With 1.5 km spacing, 100 m thickness and ρc 2.6 MJ/m³K, a Gringarten-type estimate gives about 57 years at a continuous 300 m³/h and about 80 years at the 212 m³/h mean. That is no issue for 30 years, but the agent should say so.
- **The absorption cascade.**
  - *"The heat exchanger cools the brine to 56 °C … before it reaches the absorption generator."* In the code, the generator takes brine that bypasses the exchanger, at wellhead temperature, dropping 86 → 71 °C.
  - *"The context does not specify an exact COP"*, while the checks tab shows "COP 0.75 (single effect)".
  - *"Absorption units typically reject roughly 3–4 times their cooling load"*. The model, and physics, give 1 + 1/0.75 = 2.33.
  - *"kept absorption at 1 MW because it relies on … scarce thermal energy"*. In July the brine is idle. The real reason, from ADR-0008, is that electric chillers at 20 °C reach COP 8.6.

**What to do instead.** Put the assumption table into the answerer's context: spacing, well ID, skin, ESP depth, COPs, approach temperatures and the generator's ΔT. Add a one-line breakthrough estimate.

### M1. Produced gas: routine flaring is the default sink, and there is no CHP (medium)

- `1D-BO-EC@3200` flares 3.6 GWh/yr while buying 25.9 GWh/yr of gas.
- A Dutch mining permit (SodM) will not accept routine flaring.
- The 80/20 CH₄/CO₂ gas (LHV about 28.6 MJ/Nm³) normally goes to a gas engine or a dedicated burner.
- In 2D-HP-AB, a 40 %-efficient engine on the 17.9 GWh of gas would make about 7.2 GWh of electricity. That is about 78 % of the heat pump plus pumps (9.2 GWh), worth about 1.3 M€/yr at 185.7 €/MWh.

**What to do instead.** Make flaring a warning (or a violation) and add a CHP option.

### M2. Explanations give numbers without the physics, and mislabel the costs (medium)

- **The exchanger limit.** I asked *"what is the largest share of each MWh the geothermal exchanger can deliver … however many doublets … show the arithmetic."*
  - The reply: *"51.8% … The model calculates that the doublets directly supply heat equivalent to roughly half … the boiler tops up during peak demand."*
  - The answer is (86.1 − 5 − 60)/(100 − 60) = **52.5 % on every day**, whatever the number of doublets, because the supply is 13 K above the reservoir.
  - The boiler runs in every month (0.6–6.4 GWh/month), not only at peaks.
- **The 70 °C return.** The answer never says why it hurts:
  - the exchanger lift falls from 21 K to 11 K;
  - the balanced-exchanger brine flow at peak rises from 657 to 876 m³/h, more than the 600 m³/h cap.
- **"Backup boiler".** The boiler supplies 27 % of annual heat (30.5 GWh): 17 GWh from produced gas plus 14.3 GWh of bought fuel.
- **Cost labels, three times.** In three what-ifs, LCOE is called "cost of heat":
  - "Heat cost rises to 67.6 €/MWh (from 61.8)": the card says 71.08 heat, and 61.8 is heat and cold together;
  - "67.3", where the card says 70.48;
  - "48.9 to 59.2", where the card says 64.13.

### M3. Design changes asked in chat are dropped (medium)

- *"Try a 12 MW heat pump."* The parameters step extracted `heat_pump_mw: 12.0`, but the plan said "same brief: same result" and replayed S1.
- The question before it (the boiler's share, and the 40 K not used) became a choice card with 4.49/5.07/5.66 MW options.
- With `edit`, the 12 MW heat pump shows exactly the trade-off a reviewer wants in chat:
  - bought gas 14.3 → 0 GWh;
  - CO₂ saving 60 % → 69 %;
  - LCOH 64.25 → 71.69 €/MWh;
  - reinjection 56 → 52 °C.

### M4. Well and plant hydraulics are optimistic, and practice limits are missing (medium)

- **Productivity.** PI comes from radial inflow with r_e 500 m and zero skin: 14.5 m³/h/bar. Doublet theory with L = 1.5 km gives 11.7. A skin of +3 gives 10.4, and drawdown at 300 m³/h goes from 21 to 29 bar.
- **Injectivity.** It uses 0.40 mPa·s, but brine injected at 56 °C is about 0.55 mPa·s. Build-up rises from 21 to 28 bar.
- **There are no limits at all:**
  - no maximum injection pressure (fracture gradient, and thermal stress from a 40 K colder brine);
  - no ESP head or setting-depth limit;
  - the 93.5 bar and 88.5 bar case passes silently.
- **Bubble point.** `WELLHEAD_BAR = 5 # kept above the produced gas's bubble point` is wrong.
  - 0.64 Nm³/m³ CH₄ at 86 °C in 41 g/kg brine has a bubble point near 47 bar.
  - GEMINI's ESP intake at 650 m sees 39 bar.
  - So gas, and CO₂, come out in the top roughly 700 m of tubing. That is the carbonate-scaling zone.
- **GEMINI loop pressures.** The GEMINI loop shows −1.6 bar at the exchanger inlet and −2.2 bar after filter_b. A sub-atmospheric brine loop pulls in O₂ and degasses, and nobody flags it.
- **Inconsistent well length.** The wells are vertical (2,500 m) in the hydraulics but priced as deviated (2,871 m along hole).
- **Heat pump COP.** The COP of 4.6 uses stream temperatures with no approach, and the evaporator sits directly on brine. With a titanium intermediate loop, a realistic figure for 100 °C delivery is about 3.9–4.0.

### M5. No knowledge of scaling, corrosion, gas handling, seismicity or permits; the fallback is irrelevant (medium)

- *"…cool the brine from 86 °C to 56 °C … What does that do to carbonate and lead scaling and to CO₂ corrosion…?"*
- The reply (`fallback: true`) quotes *"general-purpose search and never checks the answer. When the source cannot supply enough heat…"* from the GEMINI-bug document.
- These topics are central to any Dutch doublet review:
  - calcite scaling on CO₂ flashing;
  - Pb and barite scaling at 50–60 °C reinjection;
  - CO₂ corrosion of carbon-steel tubing;
  - inhibitors and O₂ exclusion;
  - SodM seismic risk assessment, well integrity, and the Mining Act permit.
- The self card itself lists only "no thermal breakthrough, interference … drilling risk, permits".

### L1. Workbench bugs (low)

- **Doublet depth sensitivity does nothing.** The Sensitivity "Doublet depth" gives 61.77 €/MWh flat from 2,000 to 3,500 m. `plant_of` takes each doublet's own `depth_m` over `alt.depth_m`.
- **`reservoir_temp` crashes on absolute values.** It is a delta (−10..+5); absolute values (77–92) return HTTP 500 instead of a message.
- **Two-injector summary.** For a 2I design, the top-level plant summary shows the single-injector values (88.5 bar) while the doublet row shows 42.9 bar.

### L2. Pure explanation questions re-run the whole search (low)

"Explain the cascade" took 93 s and ran 35 designs. The variants question took 146 s.

### L3. The choice between one and two doublets is a coin toss (low)

- 2D-HP-AB costs 61.8 €/MWh and 1D-HP-EC costs 62.7 €/MWh.
- At −5 K, the re-search switches to one doublet.
- The reply should say the cost optimum is flat and decide on N-1, CO₂ (9.7 against 13.0 kt/yr) and subsurface risk.

## 4. Implement differently or remove

- **Half-open wells as search variants (PL/IU/IL): remove them from the automatic search.**
  - Nobody completes half the aquifer for +0.75 K.
  - PL (producer in the lower half) is the wrong way round once the cold brine slumps.
  - The real reasons for partial completion (tight intervals, gravity segregation, "inject low, produce high") need the reservoir model the team does not have.
  - Keep them only as user-specified builds, with that caveat.
- **"Backup boiler": rename it "peak/N-1 boiler"** and size it for N-1 outside the search. Let the search size only the heat pump and the absorption chiller.
- **Model an intermediate loop** between brine and the heat-pump evaporator and the absorption generator (about 3 K approach), or say plainly that it is left out.
- **Produced gas:** add CHP as a top-up option, or at least warn whenever gas is flared.
- **Explanations:** generate a short physics sentence from the data for each design, e.g. "exchanger limited to 52.5 % because supply exceeds the brine temperature" and "brine flow capped at 600 m³/h". Let the model quote it, instead of improvising.
- **Keep** the two-injector variant, the separate-train variant and base-load dispatch. They are real options, with honest numbers.

## 5. Top 3 priorities before the deadline

1. **N-1 and robustness.** Add a check for the largest doublet out on the peak day, size the boiler for it (about +0.5 M€), and show the −5 K and +10 K-return cases in every design reply. This is the first question any district-heating or geothermal reviewer asks.
2. **State the subsurface assumptions.** At 3,200 m (or any assumed depth), put T, P, k, h and "no data" in the card and the reply, and mark such picks as speculative. Give the answerer the full assumption table: spacing 1.5 km, skin 0, r_e 500 m, ESP depth, COPs, the generator ΔT, plus a breakthrough estimate. Add an injection-pressure and ESP-head warning.
3. **Make the claim checker symmetric.** Verify facts against the data (flared gas, which variants ran, which temperature is which) and stop deleting qualitative risk content. Add a short, cited "not modelled: size and what practice does" card (scaling, corrosion, gas handling, seismicity, well integrity, permits), so risk questions get a real answer instead of a fallback.
