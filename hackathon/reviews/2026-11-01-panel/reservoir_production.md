# Review round 2: reservoir and production engineer (doublets, ESPs, injection, SodM)

Server http://127.0.0.1:8790. Threads: `res-a` (19 turns: base design A1, ten what-ifs, the explanation questions, sensitivity, GEMINI run), `res-b` (8 turns: 100 mD with upper-half producers, ESP failure on dates, explanation questions) and `res-c` (2 turns: a tight, thin sand). I re-derived every subsurface number independently in Python, using IF97 saturation pressure, Batzle-Wang brine density and a numerical triplet streamline integral. The scripts are in the scratchpad: `panel2/res/hand.py`, `code_check.py` and `show.py`.

## 1. Verdict

The new subsurface physics is sound, and the search now handles a broken limit the way an engineer would.
- Gringarten-Sauty, the Henry's-law bubble point with salting-out, the ESP setting depth and the SodM check all reproduce my hand values to within 0.5 %.
- The flow cap lands on the right number in every case I tried: 200, 155, 100, 205, 240, 215 and 80 m³/h.

The problem is everything around the physics.
- **The checks are invisible.** They are not in the check list, so a design that breaks the ESP or SodM limit still shows "11/11 checks". The model is even told it "passed all physics and cap checks".
- **The answerer is never given the results.** Its context still says breakthrough and the gas flash are "not modelled". So it got **0 of 9** explanation questions right, and twice it invented a reason for a cap.
- **Spacing still does not reach the breakthrough check.** The spacing what-if is the very case the check was built for: 600 m still gives 85 years, when it should give 14.

A SodM reviewer reading the chat would conclude the tool has no subsurface checks. Before the deadline, fix the visibility and the spacing wiring (a few hours); the physics can stay.

## 2. Stress test

| Request | Wordings tried | Right / wrong | What went wrong |
|---|---|---|---|
| Will the ESP gas-lock (bubble point, ESP depth)? | 3: *"Will the ESP gas lock?"*; *"For A1, does free gas come out of solution at the ESP intake? What bubble point did you compute and at what depth must the pump be set?"*; *"how deep does the pump go in A1 and is the intake above the bubble point"* | 0 / 3 | (1) Intake marked it `relevant: false`; the reply was "I couldn't confirm an answer". (2) "No, free gas does not come out … no bubble point was computed, and no specific depth for pump setting", plus irrelevant "The cost of heat is 75.7 €/MWh. The heat exchanger size is 7.23 MW". (3) "the ESPs reach a depth corresponding to the well's midpoint at 2,500 m". The data hold 41.7 bar and 667 m (A1), and 1,000 m (res-b A1). |
| When does the cold front reach the producer? | 3: *"When does the cold front reach the producer?"*; *"What thermal breakthrough time do you estimate for the doublet of A1 (Gringarten-Sauty), and with what well spacing, porosity and flow?"*; *"How many years until thermal breakthrough at the producer of doublet 1?"* | 0 / 3 | (1) "The question is not properly phrased … The model does not simulate … thermal breakthrough". (2) A fallback listing four unrelated facts (exchanger 7.23 MW, wellhead 86.1 °C …). (3) "not modelled … I cannot give a number of years". The data hold 85.4 yr (A1) and 122.5 yr (res-b). |
| Are we within the injection pressure limit? | 3: *"Are we within the injection pressure limit?"*; *"Check A1 against SodM: what is the injector pressure at the top of the reservoir at full flow and how does it compare with the 0.135 bar/m guideline?"*; *"Is the injection pressure OK against the SodM limit?"* | 0 / 3 | (1) "The current design does not report an injection pressure value or a check against an injection pressure limit … Please provide the pressure limit", then "The capital cost is 30.6 M€". (2) Parameters read `designs: ["A1", "SodM"]`; the reply asked "Could you clarify what 'SodM' stands for and provide the reservoir pressure". (3) "~250 bar at the bottomhole … If you provide the specific SodM limit". The data hold 265.6 vs 330.8 bar (A1) and 273.2 vs 330.8 bar (res-b). |
| Low permeability (search with flow cap) | 3: *"What if the reservoir permeability is only 50 mD?"*; Dutch *"Wat als de permeabiliteit maar 20 mD is? Blijft het ontwerp haalbaar?"*; typo design *"desing the plant asuming a tighter sand, permeabilty 40 md and only 50m thick"* | Code 3/3, reply 0/3 | Caps were right every time (200, 85 and 80 m³/h). Replies: (1) W1 "passes all physics and cap checks", although W1 breaks the ESP limit at 1,270 m. (2) "Ja, het ontwerp blijft haalbaar … voldoet … nog steeds aan alle eisen", although W6 breaks ESP (2,470 m) and SodM (555 > 466 bar). (3) "I cannot run this specific design yet because the context does not contain the results", followed by the code's line saying it ran. |
| Thin aquifer | 2: *"Suppose the sand is only 30 m net instead of 100 m …"*; *"What if the aquifer thickness is 30 m?"* | 1 / 2 | (1) Marked "unsupported": "My plant model has no input for reservoir thickness". (2) It flagged breakthrough at 26 yr correctly. It missed the second violation (ESP at 1,136 m), wrote "cost of heat drops to 77.8 €/MWh (from 69.8)" (that is heat and cold, and it rose), and credited the fix to "a treatment train per doublet to ensure longevity". |
| Half-open producers, 100 mD | 1 design + *"Why are the doublets of A1 limited to 205 m3/h instead of 300?"* | Code 1/1, explanation 0/1 | It capped at 205 m³/h (ESP at 1,000 m), as it should. The explanation was invented: "limited to 205 m³/h … to satisfy the N-1 reliability requirement". |
| Gas-liquid ratio | 3: German *"Und wenn das Gas-Flüssigkeits-Verhältnis doppelt so hoch wäre?"*; *"What if the gas-liquid ratio is 1.6 Nm3/m3 instead of 0.8?"*; *"glr 2.5 nm3/m3 - what happens?"* | 1.5 / 3 | (1) `relevant: false`: "I can only vary network temperatures, reservoir temperature/permeability/pressure". (2) Right: ESP at 1,066 m flagged, and the re-search capped at 215 m³/h. (3) The violation was reported, but all 20 candidates of the re-search failed, and the reply never says that no design works. |
| Well spacing 600 m | 1: *"What if the producer and injector of A1 are only 600 m apart at reservoir level?"* | 0 / 1 | Breakthrough stays at 85.4 yr; it should be 13.7 yr, a failure. "passes all physics and cap checks"; the cost falls to 69.6. |
| Deeper aquifer | 1: *"Try also an assumed aquifer at 3,500 m TVD, same sand, and tell me whether the subsurface limits … are still met there."* | 0 / 1 | The data are right (ESP 662 m, SodM 369 vs 466 bar). The reply: "The injector operates at a wellhead of 27 bar, which is below the bubble point (approx. 40-45 bar) to keep gas in solution", and "thermal breakthrough … not modelled". |
| ESP failure on dates | 1: *"The ESP in doublet 1 of A1 fails on 10 Jan and the workover rig only gets it back on 24 Jan …"* | Partly | The card is right: 10-24 Jan, 15 days, nothing short, +2.24 GWh of gas. The reply table puts "CO₂ … -151" (the card says 230.5 t) and "Cost … -13" (the card says 151.2 k€ saved). The spare-ESP remedy assumes a 3-day swap, although the user said the rig is the bottleneck. |
| Injectivity halves | 1 | Honest but unhelpful | "outside what Dioscuri can answer", although the code computes it in one line (still 29 bar below SodM; cap about 310 m³/h). |

**Totals:** explanations of the new checks 0/9; what-if replies that state the subsurface outcome correctly 2.5/8; search caps 7/7 correct.

## 3. Issues (most important first)

### H1. The answerer is never given the subsurface results, and its context says they do not exist (high)
- **What happened:** the nine explanation questions above. The well block in `answer.py` (about lines 819-841) gives the PI, the ESP head and the injection wellhead pressure. It then says: *"Wellhead 5 bar at the separator (the gas comes out of solution below about 40-45 bar …; that flash is not modelled). Not modelled: the reservoir's cooling over the years (thermal breakthrough) … the 1.5 km well spacing enters only the well cost."* None of the per-doublet results `breakthrough_years`, `bubble_point_bar`, `esp_setting_m`, `injection_top_bar` or `injection_limit_bar` reach the answer context, `lookup` or the front end (no file in `frontend/src` reads them).
- **Why it matters:**
  - These are the first three questions a subsurface reviewer or SodM inspector asks. The tool computes all three correctly, then denies having them.
  - The "draft value" add-backs keep appending cost figures to pressure questions ("The capital cost is 30.6 M€"). That is round-1 issue 3.3, not fixed.
- **What to do:**
  - Add one sentence per doublet: "breakthrough after X yr (Gringarten-Sauty, L 1.5 km, φ 0.20, H …, mean Q …); bubble point Y bar(a) at T °C; ESP set at ≥ Z m (limit 1,000 m); injector at the top of the reservoir P bar against SodM's 0.135 bar/m × top = L bar; flow capped at Q by the {ESP | injection} limit".
  - Delete the stale "not modelled" sentence.
  - Map "bubble point / gas lock / ESP depth / breakthrough / cold front / SodM / injection limit / fracture" to these facts in `lookup`.
  - Effort: about 2-3 hours.

### H2. Subsurface violations never reach the check list, the cards or the model (high)
- **What happened:**
  - `verifier.verify_plant` has no subsurface check, so designs that break a limit show `checks 11/11` (or 10/10). Examples:
    - W1, 50 mD: ESP at 1,270 m;
    - W2, 30 m: breakthrough at 26 yr and ESP at 1,136 m;
    - W3/W4, GLR 1.6/2.5: ESP at 1,066 and 1,516 m;
    - W6, 20 mD at 3,500 m: ESP at 2,470 m and injection 555 > 466 bar.
  - `answer.designs_line` then tells the model "passed all 11 physics and cap checks", and the model repeats it: W1 "passes all physics and cap checks"; W6 "voldoet aan alle eisen".
- **Why it matters:** the card says the opposite of the data. A judge who opens W6 sees a design that would fracture the seal and gas-lock the pump, marked fully compliant.
- **What to do:**
  - Add three requirement checks per design, built from the doublet rows: "Cold front after the 30-year life", "ESP intake above the bubble point with the pump above 1,000 m", "Injection below SodM 0.135 bar/m at the top of the reservoir".
  - Have `designs_line` use `year.violations` as well.
  - Show the subsurface rows on the Design tab.
  - Effort: about 1-2 hours.

### H3. The spacing what-if still does not reach the breakthrough check (round-1 H1 not fixed) (high)
- **What happened:** *"What if the producer and injector of A1 are only 600 m apart …"* produced W5/E1 with `breakthrough_years 85.4`, the same as at 1.5 km.
  - By Gringarten-Sauty: 85.4 × (600/1,500)² = **13.7 yr**.
  - The reply says "passes all physics and cap checks" and the cost falls from 69.8 to 69.6 €/MWh.
  - Cause: `parameters.CATALOGUE["well_spacing_m"]` has `target="prices"`, so the value goes only to `Prices.well_spacing_m` (well length). `engine.rules_for` reads only `brief.rules`, so `Rules.well_spacing_m` stays at 1,500 m.
- **Why it matters:** this is exactly the wrong-sign case round 1 reported: closer wells look cheaper and safe. The new check exists but is not wired to the input that matters most.
- **What to do:**
  - Write `well_spacing_m` to both `prices` and `rules`.
  - Add porosity and spacing as sensitivity keys.
  - Add the eval "600 m spacing must fail breakthrough".
  - Effort: about 30 minutes.

### H4. Invented explanations for caps and checks pass the claim checker (high)
- **What happened:**
  - *"Why are the doublets of A1 limited to 205 m3/h instead of 300?"* got: "to satisfy the N-1 reliability requirement … By sizing them to 205 m³/h each, the remaining doublet can carry the full load". That is physically meaningless. The cap is the ESP setting-depth limit: Pb 41.6 bar(a), pump at 1,000 m, PI 3.63 m³/h/bar.
  - 3,500 m: "wellhead of 27 bar, which is below the bubble point … to keep gas in solution". That is backwards: below the bubble point is where gas comes out, and the injection wellhead has nothing to do with it.
  - The claim checker removed nothing in either case.
- **Why it matters:** both were stated with confidence, and an expert would stop trusting every other answer.
- **What to do:**
  - Give the binding limit as a fact (H1).
  - Have the claim checker test pass/fail and cause statements ("meets all", "haalbaar", "limited to … to satisfy …") against `violations` and the cap's reason, not only numbers.
  - The cap string `"(ESP and injection limits)"` should name the limit that actually binds:
    - IU at 50 mD is injection-bound (155.7 m³/h);
    - PL at 50 mD and every full-open case are ESP-bound.

### H5. A search that finds no feasible design is not reported (high/medium)
- **What happened:** *"glr 2.5 nm3/m3 - what happens?"*: `search_designs` returned `valid: 0, failed: 20`, every one with "the ESP must sit at 1,516 m". No attempt was stored and the reply says nothing about it. It reports only that W4 got cheaper ("Heat cost drops to 59.7 €/MWh", which is in fact heat and cold).
  - At GLR 2.5, Pb = 129 bar(a). Even at zero flow the pump would have to sit at about 1,290 m, so no flow cap can help, and `subsurface_caps` skips it (`q < flow_min`).
- **Why it matters:** "no doublet can be produced with these assumptions" is the most important answer a feasibility tool can give.
- **What to do:**
  - When `chosen is None`, say so with the reason and the shallowest possible setting depth.
  - List the real options: a deeper pump chamber (cost it), a gas-handling ESP or downhole gas separator (GVF 20-40 %), or a higher separator pressure. A higher separator pressure only reduces surface flash; it does not change the downhole Pb.

### M6. The bubble point is computed on the optimistic side, with no margin (medium)
- **My check:** the code gives 41.7 bar(a) at 86.1 °C; mine is 41.8, so the method is right. Three things push it up:
  - **Salinity.** `SALINITY_MOL_KG = 0.70` (41 g/kg, a seawater figure). By Batzle-Wang, 1,030 kg/m³ means 46-48 g/kg (0.83-0.86 mol/kg) at 15-20 °C, and 73 g/kg (1.35 mol/kg) at 87 °C and 250 bar. The challenge does not say at what conditions the 1,030 is quoted.
  - **Poynting and fugacity.** These are omitted (V∞ ≈ 37 cm³/mol, φ_CH4 ≈ 0.97 at 40 bar), which adds about 8-9 % to the partial pressures.
  - **Margin.** The intake is set exactly at Pb. Practice is Pb + 5-10 bar, or a GVF limit.
- **Effect:**

  | Basis | Pb, bar(a) | ESP depth at 300 m³/h | Cap at 50 mD |
  |---|---|---|---|
  | Code (0.70 mol/kg, ideal) | 41.7 | 667 m | 200 m³/h |
  | 0.85 mol/kg + Poynting/φ | 47.1 | 720 m | |
  | 1.35 mol/kg + Poynting/φ + 5 bar margin | 54 + 5 | 835 m | about 137 m³/h |

  The cap, which drives which design is picked at low k·h, can move by about 30 %.
- **Also:** the setting depth is not costed. A pump chamber at 990 m costs the same as one at 670 m.
- **What to do:**
  - Add a margin parameter (default 5 bar).
  - Add the Poynting/φ factor (3 lines).
  - State the salinity basis on the inputs card and add a "salinity" or "Pb" sensitivity.
  - Price the extra pump-chamber casing.
  - Effort: about half a day.

### M7. Injectivity and the SodM check use the warm-brine viscosity (medium)
- **The problem:** the injector sees 52-56 °C brine, about 0.60-0.65 mPa·s, against the given 0.40 mPa·s at 87 °C (water ratio μ(52 °C)/μ(87 °C) ≈ 1.6). After a few years the cooled zone extends hundreds of metres, so the build-up is about 1.5× the code's.
- **Effect:** W1 (50 mD) sat 3 bar under the limit (327.6/330.8 bar). With cold viscosity (build-up 82.6 bar × 1.5-1.6) it is about 40-45 bar over. At 50 mD the injection cap drops to about 195 m³/h, so SodM, not the ESP, becomes the binding limit.
- **What to do:**
  - Use μ(T_reinjection) in the injectivity, a Ramey-type thermal skin, or simply a stated factor.
  - Also add an injectivity multiplier (skin) as a what-if: "the injector loses half its injectivity" was refused as out of scope (res-b), although it is one line of code.

### M8. GEMINI still sets the ESP at 650 m, so the recommended design runs with free gas at the intake (medium)
- **What happened:** `gemini res-a "A1 · 1D-HP-EC-N1"` gives `esp_intake_pressure` 39.04 bar(g). The bubble point is 41.7 bar(a), i.e. 40.7 bar(g), and the subsurface check says the pump must sit at ≥ 667 m (`tools/gemini.py` `ESP_DEPTH_M = 650.0`).
- **What to do:** pass `esp_setting_m` (with the M6 margin) as `esp_depth_m` per design. Effort: about 1 hour.

### M9. Variant and cap explanations compare unequal flows without saying so (medium)
- **What happened:** at 50 mD, `1D-HP-EC-PL` reads "wellhead 85.0 °C against 85.7 °C, ESP head 63 bar against 65 bar at full flow". The PL doublet is capped at 100 m³/h and its parent at 200. The text implies that a half-open producer lowers the ESP head and the temperature; both effects come from halving the flow.
- **What to do:** say "capped at 100 m³/h by the ESP depth limit (against 200)" and compare at equal flow.

### M10. Headline hydraulics still belong to another doublet (round-1 production 3.7 not fixed) (medium)
- **Examples:**
  - res-c A1: the headline shows `esp_head_bar 218.9`, `injection_wellhead_bar 208.6`; the design's doublet, capped at 80 m³/h, needs 63.1 and 52.9 bar.
  - C1: 81.0 against 65.7 bar.
  - G1: 218.1 against 64.1 bar.
  - res-b A1: PI 7.26 in the headline, against 3.63 for its upper-half producers.
- **Why it matters:** with capping, this headline is now wrong in every capped design.
- **What to do:** show the worst doublet's own row, or drop the headline.

### M11. The inputs card hides the subsurface assumptions and mislabels user changes (round 1, not fixed) (medium)
- **Missing from the card:**
  - porosity 0.20, ρc of the rock 2.25 MJ/m³K, spacing 1.5 km;
  - a 30-year life at constant temperature;
  - the ESP limit of 1,000 m;
  - SodM 0.135 bar/m;
  - salinity 0.70 mol/kg;
  - skin 0, re 500 m, half-open = half PI;
  - separator at 5 bar.
- **Mislabelled:** in res-b the user's 100 mD shows as "[fixed] … 100 mD … from GEMINI_Hackathon_Challenge_Requirements.docx.pdf, section 3.1". The PDF says 200 mD.

### M12. The model rejects valid parameters depending on the wording (medium)
- *"only 30 m net"* got "no input for reservoir thickness". `reservoir_thickness_m` is in the catalogue, and *"aquifer thickness is 30 m"* works.
- German *"doppelt so hoch"* (GLR) got `relevant: false` and "no input for the gas–liquid ratio".
- "SodM" was read as a design name.
- *"Try also an assumed aquifer at 3,500 m"* dropped the depth list ("its numbers are not in the quote", because of "3,500" against 3500 and 2500). The plan then searched only at 3,500 m, and the next what-if (20 mD) was applied to that assumed-aquifer design (round-1 M9 again).

### L13. Breakthrough with two injectors is overstated (low)
- `breakthrough_years` uses Q/2 per injector, which doubles t_b.
- With the producer drawing Q from both sides (a line triplet), my streamline integral gives ×1.50, not ×2 (85.8 against 114.4 yr at 300 m³/h).
- Also, it uses the gross 100 m with no net-to-gross. The docstring's "on the early side" is true only for conduction; layering and high-k streaks bring breakthrough earlier, and gravity under-ride does too.

### L14. The spare-ESP remedy (low; operations)
- **The 3-day swap.** `SPARE_ESP_SWAP_DAYS = 3` assumes a workover rig on standby. The user said the rig is the bottleneck, so a shelf spare does not shorten that outage. In NL, rig mobilisation is 1-4 weeks; the spare saves the ESP's manufacturing lead time (months), not the rig days.
- **Inconsistent money.** "Money saved" (151.2 k€) counts only gas plus CO₂, while the outage's "extra cost" (136.6 k€) is the full opex change. So the remedy saves more than the outage costs.

### L15. Half-open variants unchanged (round-1 M6/M7) (low)
- PL is still rewarded for +0.7 K, with no caveat about gravity under-ride.
- Half-open wells still get half the PI, with no partial-penetration skin and skin 0.
- The variants never mention their deeper ESP: PL at 200 mD needs 868 m against 667 m.

## 4. What users in my role need most that is missing

1. **Make the checks visible and explainable** (H1, H2, M10). The checks belong in the check list, in each design's card and in the answer facts, with the binding limit named. Without this the new physics earns nothing in front of judges. *Effort: half a day.*
2. **Wire spacing, porosity and margins into the checks** (H3, M6, M7). Spacing should reach `Rules`. Add a bubble-point margin with Poynting/φ, a stated salinity basis, and cold-injectate viscosity in the injectivity. Add sensitivity keys: spacing, porosity, skin, GLR, salinity. *Effort: half a day.*
3. **A production temperature that falls over 30 years**, not pass/fail at first arrival.
   - Gringarten-Sauty's T(t) after breakthrough, or Lauwerier with heat from the cap and base rock (which matters for thin sands), feeding the year at years 1/15/30 and the annuity.
   - A plume-radius and interference check for 2-3 doublets in one lease: a stated inter-doublet distance, the cooled radius √(V·(ρc)w/(π·H·(ρc)a)) after 30 years, and pressure superposition.

   *Effort: 1-2 days.*
4. **Ranges on k·h, skin and net-to-gross instead of single values.** ThermoGIS-style P90/P50/P10 flow and cost of heat, and the flow cap as a range (137-204 m³/h at 50 mD, depending on Pb basis and margin). A deep-geothermal investment decision is made on P90. *Effort: about 1 day, using the existing functions.*
5. **ESP engineering output.**
   - From the ESP setting depth (with margin): pump chamber casing depth and its cost, and ESP size.
   - The best-efficiency-point window (70-120 %) on the year's flows, and part-load efficiency.
   - Run life (2-3 yr in NL), turned into expected outage days a year in the economics.
   - Gas-handling options when the limit binds.

   *Effort: 1-2 days.*
6. **Gas and scaling.**
   - The flash at the 5 bar separator: about 88 % of the CH4 and 34 % of the CO2 come out.
   - The depth of first gas in the producer: about 400-450 m.
   - The calcite and CO₂-corrosion zone, and where the inhibitor is injected.
   - The residual gas sent to the injector, and the gas actually burned.

   *Effort: about 1 day.*
7. **A SodM checklist in the report:** the maximum injection pressure statement (with the thermal term), seismic risk screening (distance to faults: data needed), well integrity, and a monitoring plan (PT gauge at the ESP intake, a tracer test to calibrate breakthrough). *Effort: hours (text).*

## 5. What works

- **The formulas and numbers are right.** Each pair below is code, then my value:
  - **Breakthrough:** 85.4 against 85.5 yr; at H = 30 m, 25.6 yr.
  - **Bubble point:** 41.7 against 41.8 bar(a).
  - **ESP setting:** 667 against 668 m; at 50 mD, 1,270 against 1,271 m.
  - **SodM:** 0.135 × 2,450 = 330.75 bar against 244.95 + Q/II.
  - **Assumed aquifers:** 465.8 against 369.3 bar at 3,500 m.
  - **Constants:** the IAPWS G7-04 constants and the Antoine coefficients are the published ones.
- **The flow cap works the way an engineer would size it.** It finds the highest flow within both limits by bisection, rounds down to 5 m³/h, lets the boiler or heat pump take the rest, and reconsiders the doublet count. Examples:
  - one doublet at 50 mD is capped at 200 m³/h, and the pick moves to two doublets;
  - the IU injector is correctly injection-bound at 155 m³/h;
  - at 30 m, two doublets at 240 m³/h push breakthrough to 33.7 yr.
- **Plain-English thickness and GLR what-ifs report the violation** with the right number: "cold water reaches the producer after 26 years"; "the ESP must sit at 1,066 m".
- **Round-1 production bugs are fixed:** GEMINI's ESP now draws 391 kW (70 %), the surface loop stays at 4-5 bar, and the depth sensitivity responds (60.5-81.3 €/MWh).
- **The failure card reads dates correctly** (10-24 Jan, 15 days), says nothing is short, and prices the extra gas.

### Round-1 status (my field)

| Round-1 issue | Status |
|---|---|
| Res H1: breakthrough check | The check exists and is correct; the spacing what-if still bypasses it. |
| Res H4 / Prod 3.2: ESP and injection limits | In the plant and search; invisible in checks, cards and answers. |
| Prod 3.1: negative loop pressures | Fixed. |
| Prod 3.4: GEMINI ESP efficiency | Fixed. |
| Prod 3.5 / Geo H2: N-1 | Fixed. |
| Res M8: depth sensitivity | Fixed. |
| Res M5 / Prod 3.3: the agent knows its well model | Partly: PI and Ramey are in the context; subsurface results are not; cost add-backs remain. |
| Res M6 / M7: half-open variants, inflow formula | Not fixed. |
| Prod 3.7: headline hydraulics | Not fixed; worse now that designs are capped. |
| Prod 3.9: assumptions on the inputs card | Not fixed. |
| Res M9: questions move the reference to an assumed aquifer | Still happens. |
| Res L11: fallback lists unrelated facts | Still happens. |
