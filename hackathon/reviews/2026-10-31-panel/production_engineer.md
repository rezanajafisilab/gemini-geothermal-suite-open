# Production engineer review: Dioscuri (server 8790, threads prod-1, prod-2)

## 1. Verdict

The well numbers in the plant model are sound and easy to check by hand. At 300 m³/h the ESP head is 32.8 bar and the ESP draws 0.391 MW; the injection wellhead pressure is 22.6 bar and the injection pump draws 0.221 MW. Each matches flow × head / 0.70 to the kW. The edits a production engineer wants (two injectors, a train per doublet, flow caps, half-open wells) work.

Everything below the wellhead flange is weak:
- **The surface loop drawn as GEMINI's project is not physical.** With a shared train the pressure goes negative (as low as -5.9 bar at the injection-pump suction), and the run still reports `ok: true`.
- **The gas has no physics at all.** The bubble point is about 45 bar(a), not below 5 bar. The ESP at 650 m sits at or below it at full flow, and the gas comes out of solution in the top ~380 m of the producer.
- **GEMINI's ESP and the plant model's ESP disagree by 7-10 %** for the same head.
- **The agent cannot answer a basic hydraulics question.** It gives cost numbers back, and once it invented a "bubble point check" that does not exist.

I would not put the GEMINI view or the gas handling in front of judges until the three priorities at the end are fixed.

## 2. What works

- **The plant model's doublet physics are right and traceable.** I checked them by hand:
  - PI from k·h is 14.51 m³/h/bar.
  - Drawdown is 20.7 bar at 300 m³/h.
  - Friction is 4.5 bar over 2,500 m of 8.5 in (Colebrook f = 0.0146).
  - ESP head = 5 + 252.6 + 4.6 − 229.3 = 32.8 bar; 300/3600 × 32.82e5 / 0.7 = 391 kW.
  - Injection pump: (22.6 − 4) bar × 300/3600 / 0.7 = 221 kW.
  - GEMINI's ESP intake (39.0 bar) and discharge (71.9 bar) agree with the same column.
- **The `edit` path works and the request parser understood production language.** "two doublets, each with one producer and two injectors, a separate treatment train per doublet, and the flow capped at 200 m3/h" became `{"n_doublets": 2, "injectors": 2, "trains": "separate", "flow_max_m3h": 200}`.
- **The search's variant explanations read like an engineer wrote them.** Examples: "the producer open over half the aquifer has half the productivity: ... ESP head 54 bar against 33 bar"; "+11.0 M€ of capital for the extra injector(s), -1.05 GWh a year of pumping". Not choosing a second injector on energy grounds is correct.
- **The GEMINI project mirrors a P&ID** (producers → mixer → separator/filter per train → header → exchanger → filter → splitter → injectors, gas → adder → boiler) and runs in 3 ms. Separate trains and two injectors give plausible numbers: 1.7 bar after filter_a, 8.9 bar per injector at 150 m³/h.
- **It is honest about scope** when asked directly: "The design does not currently model chemical treatment for scaling below the ESP"; "the plant model has no input for specific component failures". The planned 35-day stops are staggered into early and late summer (days 145-179 and 189-223), which is sensible.

## 3. Issues (most important first)

### 3.1 HIGH: the GEMINI surface loop goes to negative pressure, and the agent says it does not
- **What I did:**
  - `panel.py gemini prod-1 "2D-HP-AB"` (the recommended design: 2 doublets × 300 m³/h, one shared train).
  - An edit with 3 doublets on one train (U2).
  - An edit with a train per doublet and 2 injectors (U1).
- **What happened (2D-HP-AB, 600 m³/h through one train):**
  - separator `pressure_out` 4.40 bar
  - `filter_a` `pressure_out` **-1.62** bar
  - `heat_exchanger` `pressure_in` -1.62 bar
  - `filter_b` `pressure_out` **-2.24** bar
  - `"ok": true, "error": null`
- **U2 (900 m³/h through one train):** filter_a -4.94 bar, filter_b **-5.88** bar.
- **Injection pumps:** GEMINI's draw 295.7 kW each (U2: 339.1 kW) against the plant model's 221 kW, i.e. +34 % and +53 %. GEMINI boosts from the negative suction; the plant model assumes 4 bar.
- **Even one doublet at 300 m³/h** loses 3.6 bar in GEMINI's train (separator 0.3, filter_a 3.0, filter_b 0.3) and reaches the injection pumps at 1.4 bar.
- **The code has three different suction assumptions:**
  - `tools/gemini.py` `RETURN_BAR = 4.0`;
  - `dioscuri_plant/doublet.py` `stub_doublet` uses `WELLHEAD_BAR` (5 bar, i.e. no surface losses);
  - GEMINI's own loop gives 1.4 bar.
- **I asked:** "Why is there no booster pump in the GEMINI loop of 2D-HP-AB between the separator and the injection pumps?"
- **The reply:** "the model assumes that the pressure generated at the wellhead (approximately 5 bar) by the producers is sufficient to push the brine through the treatment train (separator, filters, heat exchanger) to reach the injection pumps. Therefore, an additional booster pump component is not modeled or needed". It is quoting `answer.gemini_block` and the `plant_project` docstring, and its own run of that design says otherwise.
- **Why it matters:**
  - Pressure below vacuum is impossible. Brine at 84 °C would flash, and the 12 % of the CH4 and 66 % of the CO2 still dissolved after the separator (see 3.2) would come out in the filter, exchanger and pump suction. That means gas locking and cavitation at the injection pump.
  - A judge who clicks "Run on GEMINI" sees the negative numbers.
  - The cause is that `plant_project` copies GEMINI's example separator and filter resistances (3.6 and 36 bar per m³/s, sized for one ~140 m³/h doublet) without scaling them to each train's flow.
- **What to do instead:**
  - Scale each separator/filter resistance to its train's design flow, so a clean filter drops about 0.3-0.5 bar and a fouled one about 1 bar.
  - Take the injection-pump suction from the same train in both models (one constant, one source).
  - Add GEMINI's `booster_pump` after the separator, or raise the separator pressure, when the loop would fall below the separator pressure minus a margin.
  - Make the GEMINI run fail (not `ok: true`) when any pressure is below the separator pressure or the brine's vapour pressure.
  - Delete the "5 bar carries the brine" sentence from `gemini_block` and the docstring.

### 3.2 HIGH: the produced gas has no physics, the 5 bar comment is wrong, and the ESP sits at the bubble point
- **The code says:** `doublet.py`: `WELLHEAD_BAR = 5.0  # kept above the produced gas's bubble point at the surface separator`.
- **My check:** Henry's law with IAPWS constants (Fernández-Prini et al. 2003), salting-out for about 0.73 mol/kg NaCl, a Poynting term and water vapour. For 0.8 Nm³/m³ of gas (80 % CH4, 20 % CO2), i.e. 35.7 mol/m³:
  - bubble point **about 45 bar(a)** at 86 °C, 36 bar(a) without salting-out;
  - at the 5 bar(g) separator, 88 % of the CH4 and 34 % of the CO2 come out (GVF about 14 %).
  - So the plant runs far below the bubble point, which is the reason it needs a separator at all.
- **Where the gas comes out:**
  - In the producer above the ESP, first gas appears about **380 m** below the wellhead (5 bar + 0.103 bar/m). The top 380 m of tubing are two-phase, with CO2 leaving solution, which is where calcite scale and CO2 corrosion start.
  - **ESP intake:**

    | Case | GEMINI ESP intake | Against the bubble point |
    |---|---|---|
    | Full completion, 300 m³/h | 39.0 bar(g) | About 5 bar below; about 9 % of the gas free |
    | Half-open producer (U3, "PL" variants) | 18.4 bar(g) | About half the gas free at the pump (GVF about 3 %) |
    | Full completion, 200 m³/h | 47.8 bar(g) | About 3 bar above |

  - The required setting depth for intake ≥ Pb + 5 bar is about 750 m (full completion, 300 m³/h) and about 950 m (half-open). The GEMINI view fixes 650 m from GEMINI's example for every design.
- **I asked (prod-1):** "what is the bubble point pressure of the produced brine ... Is the ESP intake at 650 m above it at 300 m3/h, and does gas come out of solution in the producer above the pump or only in the separator at 5 bar?"
  - **Reply:** "the current context does not provide the specific fluid properties (80% CH₄, 20% CO₂) or the exact depth of the ESP intake". Both are in its own inputs card and GEMINI project. It also said: "gas is removed before reaching downstream equipment like the heat exchanger".
- **In prod-2,** after a design capped at 200 m³/h "so the ESP intake stays above the gas bubble point", the reply said: "The design passes all 12 checks, **including the ESP intake pressure requirement relative to the gas bubble point**." There is no such check; the 12 are energy balance, Carnot, temperature cross and the challenge caps. The claim checker let it through.
- **Why it matters:**
  - Gas at the intake, scale where the gas leaves, and residual gas in the surface loop are the main production risks of this brine. The agent can neither compute them nor admit it consistently.
  - The impact on the numbers is small: the plant model burns 100 % of the CH4 (about 12 % too much, roughly 2 GWh/yr of gas) and counts all the gas's CO2 as emitted (about 580 t/yr too much, conservative). The credibility impact is large.
- **What to do instead:**
  - Add a 20-line Henry's-law bubble-point and flash function (CH4 and CO2, salting-out) as a tool.
  - Add a check: ESP intake ≥ Pb + margin, or GVF at the intake < 10 %.
  - Set the ESP depth per design from it.
  - Report the depth of first gas and the gas actually freed at the separator.
  - Use the flash split for the gas burned and the CO2 vented.
  - State scale-inhibitor injection below the ESP (capillary line) as a design item.
  - Make the claim checker reject named checks that are not in the check list.

### 3.3 HIGH: production questions get cost lists instead of answers
- **Basic hydraulics.** I asked (prod-1): "What ESP head and ESP power does each producer of 2D-HP-AB need at 300 m3/h, and what is the injection wellhead pressure?"
  - **Reply:** "includes a heat exchanger of **14.46 MW**, a capital cost of **43.2 M€**, a heat cost of **64.2 €/MWh** ... The brine temperature at the wellhead is **86.1 °C**."
  - The answer it should have given (32.8 bar, 0.391 MW, 22.6 bar) is in the Plant view. The "understood" field read: "You want me to restate the specific project values from the draft block in JSON format."
- **Fallback answers.** The negative-pressure question (3.1) and the ESP-mismatch question (3.4) both ended in `"fallback": true`. The reply was five or six cost figures, each followed by the same sentence: "Source: 2D-HP-AB, 2 doublets at 2,500 m, heat pump top-up with a backup boiler, absorption and electric chillers (simulate_year and economics, gemini+dioscuri_plant tools)".
- **The grounding check removed the plant's own number:** "These numbers are not in the context: 391, 8.33 ... removed sentences with numbers no source gives (391)".
- **Off-topic restatement.** The scaling question also opened with "68.2 €/MWh ... 54.6 M€ ... 56% ... 9.43 MW".
- **The first design reply** said "To see the exact ESP and pressure curves, please request a detailed hydraulic simulation report" when I had asked for the operating point.
- **Causes:**
  - `lookup.ALIASES` has no production facts (no ESP head or power, ESP intake, injection pressure, injection pump, wellhead pressure, gas rate or PI). Its `wellhead` pattern maps to `wellhead_temp`, so "injection wellhead pressure" returns 86.1 °C.
  - The design block in `answer.py` gives injection pressure but no ESP figures.
  - The "Keep these values from the draft" retry pushes costs into every answer and overwrites the "understood" field.
- **What to do instead:**
  - Add design facts per doublet: ESP head, power and intake pressure; injection wellhead pressure and pump power; separator pressure; gas Nm³/h; PI and injectivity.
  - Split the `wellhead` pattern by temperature vs pressure.
  - Only force draft values that the question asks about.
  - Never return a fallback that answers a different question; say "I don't have that" instead.

### 3.4 MEDIUM: GEMINI's ESP draws 7-10 % more than the plant model for the same head
- **Numbers:**

  | Case | GEMINI ESP | Plant model ESP | Difference |
  |---|---|---|---|
  | 2D-HP-AB, 300 m³/h, 32.82 bar | 419.1 kW | 391 kW | +7.2 % |
  | 200 m³/h, 23.45 bar | 204.4 kW | 186 kW | +9.9 % |
  | Half-open producer, 53.44 bar | 685.3 kW | 636 kW | +7.7 % |

  GEMINI's figure corresponds to 273.5 kW hydraulic / 419.1 kW = **65.2 %**, not the challenge's 70 %.
- **I asked:** "each producer's ESP draws 419 kW ... but the Plant view says 0.391 MW. Which is right ... The challenge says pumps are 70% efficient." The answer fell back to a cost list (3.3).
- **Cause:** `duty_esp` fits the power curve as `h(q)·q·c/η × (60/hz)`. That factor is right for GEMINI as released, where flow is not scaled with frequency, but patch 05 (affinity on flow) is applied in the "fixed" GEMINI that runs. The efficiency then comes out as η × hz/60 = 0.7 × 55.97/60 = 0.653. I evaluated the same coefficients both ways: 70.0 % on the released ESP model, 65.2 % on the patched one.
- **Why it matters:** the GEMINI view breaks the challenge's 70 % rule, and the two views of one design disagree.
- **What to do:** drop the `(60/hz)` factor for the fixed variant, so power is fitted on the 60-Hz-equivalent flow. Then GEMINI reads 391 kW. Add a test that GEMINI's ESP efficiency at the duty point is 0.70 ± 0.005.

### 3.5 MEDIUM: no availability. One ESP workover in winter breaks the peak
- **I asked (prod-2):** "If doublet 1's ESP fails on 28 January, can 2D-HP-AB-2I-ST still deliver the 30 MW peak?"
  - **Reply:** "Likely fails to meet 30 MW". This is a guess. The parameters step marked the failure as "unsupported", although `Plant.stop_start_day` already does it.
- **My check (plant model, doublet 1's 35-day stop forced over 28 Jan):**
  - 2D-HP-AB (recommended) is **7.17 MW short on 28 Jan, short on 25 days**.
  - 2D-HP-AB-2I-ST is 4.68 MW short on 13 days.
- **Why it matters:**
  - ESP run lives in Dutch geothermal are about 2-3 years, and a workover takes 2-4 weeks plus rig availability. The 35 days of planned summer stops do not cover forced outages.
  - The boilers are sized only for the gap with all doublets running.
  - The search's argument for separate trains ("a spare train keeps the others running") is an availability argument the model never credits.
- **What to do:**
  - Add an N-1 check: the peak is met with the largest doublet out.
  - Offer it as a what-if, since `stop_start_day` exists.
  - The cheap fix is about 7.2 MW more boiler (×0.075 M€/MW = 0.54 M€). Present it next to the spare-ESP option from Ali's note.

### 3.6 MEDIUM: flat 70 % at every flow, and the ESP's operating window is not checked
- **Flows in the designs:** the 300 m³/h designs run 136-300 m³/h; the 200 m³/h design runs 107-200 m³/h. Even one doublet bottoms at 136 m³/h, set by summer heat plus the absorption chiller's drive.
- **On GEMINI's own example pump shape** (BEP at 0.64 of run-out, 72 %), the 300 m³/h duty pump behaves as follows:

  | Flow | Frequency | Share of run-out | Efficiency | Note |
  |---|---|---|---|---|
  | 300 m³/h | 56 Hz | 0.64 | 72 % | At its best-efficiency point |
  | 136 m³/h | 40 Hz | 0.41 | about 59 % | Edge of the downthrust range |
  | 50 m³/h (challenge minimum) | 32 Hz | 0.19 | about 38 % | Outside any ESP's window |

  At 32 Hz the low flow past the motor also limits motor cooling.
- **Why it matters:** the plant model understates ESP energy by about 16 % on low-flow days (about 6 % over the year, small in euros). A design that runs a 300 m³/h pump at 50 m³/h would pass every check.
- **What to do:**
  - Keep 70 % for compliance with the rules.
  - Add a check that each doublet's daily flows stay within about 70-120 % of BEP flow at the running speed.
  - Report the real part-load efficiency as a sensitivity.

### 3.7 MEDIUM/LOW: the Plant view headline hydraulics belong to a different doublet
- `workbench` fills `esp_mw`, `esp_head_bar`, `injection_wellhead_bar` and `productivity_index_m3h_per_bar` from `engine.doublet_summary(depth, rules)`: a full-open, one-injector doublet at the cap.
- **Examples:**
  - For 2D-HP-AB-2I-ST the headline says 13.2 bar and 0.073 MW; its injectors run at 4.83 bar.
  - For U3 (upper-half producers) it says 32.8 bar head and PI 14.51; the doublets need 53.4 bar at PI 7.26.
  - For U1 it says 22.6 bar; the design's injectors run at 8.9 bar.
- **Fix:** show the design's own worst doublet, or remove the headline (the per-doublet rows are right).

### 3.8 LOW: no injection pressure limit, and the injectivity what-if is not computed
- **I asked:** "What maximum injection pressure does the design allow? ... how far is the injector's bottomhole pressure from the fracture pressure at 2,500 m, and what happens if the injectivity halves?"
  - **Reply:** "the fracture pressure ... is not provided ... we cannot calculate the exact distance". It did not compute the trivial case.
  - The claim checker removed "maximum injection pressure of 4.8 bar". That is the design's per-injector wellhead pressure, wrongly called a maximum.
- **The numbers it could have given:** with injectivity halved, one injector at 300 m³/h has a build-up of 41 bar, about 43 bar at the wellhead and about 291 bar bottomhole. Against an assumed Shmin of about 0.155 bar/m × 2,500 m ≈ 390 bar, that is not binding, but it should be a check with a stated gradient.
- **Also:** the cooler injection column (56 °C vs 86 °C, about 1.7 % denser) is ignored. That makes injection pressure about 4 bar conservative, which is fine but worth saying.

### 3.9 LOW: production assumptions are not on the inputs card
- **Missing from the card:**
  - wellhead/separator pressure 5 bar;
  - injection-pump suction 4 bar;
  - ESP depth 650 m;
  - 8.5 in bore to TD;
  - PI from k·h with skin −0.75 and a 500 m drainage radius;
  - roughness 0.045 mm.
- **Wrong source:** in prod-2 the user's 200 m³/h cap appears as "50 to 200 m³/h ... from: GEMINI_Hackathon_Challenge_Requirements.docx.pdf" (the PDF says 300).

### 3.10 LOW: well and train details
- **Pump chamber:** a 300 m³/h, 33-bar ESP is a roughly 10 in OD pump. It needs a 13⅜ in pump chamber to about 750-950 m (see 3.2), not 8.5 in from surface to 2,500 m.
- **Half-open wells:** the PI simply halves, with no partial-penetration skin (Brons-Marting gives about 9 m³/h/bar at kv = kh, about 6.7 at kv/kh = 0.1). Halving is a fair middle value; say so.
- **GEMINI temperature drops:** the separator and both filters keep GEMINI's example 1 K drops, so the exchanger sees 84.1 °C in GEMINI against 86.1 °C in the plant model. Set them to about 0.

## 4. Implement differently or remove

- **ESP depth:** compute the setting depth per design from the bubble point and the drawdown, instead of GEMINI's fixed 650 m. Put the pump chamber depth and size into the well description and the cost.
- **Treatment train:**
  - Size the separator and filters to each train's flow.
  - Have one suction-pressure source shared by the plant model and the GEMINI loop.
  - Add a booster pump or a higher separator pressure when needed, so the residual gas stays in solution to the injection pump.
  - Then credit separate trains for what they really do: hydraulics, and availability when one is fouled or in maintenance. Otherwise drop the "spare train keeps the others running" sentence.
- **Remove false text:**
  - the "5 bar wellhead pressure carries the brine through the plant" sentence (`gemini_block`, `plant_project` docstring);
  - the "kept above the produced gas's bubble point" comment;
  - the "(the example suits about 150 m3/h ...)" aside, once the duty pump is fixed.
- **Gas accounting:** replace the 100 %-separated assumption with a flash at the separator pressure (88 % of the CH4, 34 % of the CO2 at 5 bar(g)). Report the residual gas that goes to the injector.
- **Answer pipeline:** remove the "keep these values from the draft" correction for questions that are not about those values. Remove fallbacks that answer a different question.
- **Keep the second-injector variant.** It is correctly rejected on cost (+11 M€ to save 1.05 GWh/yr). It is still worth offering as injectivity-risk insurance if 3.8's check is added.

## 5. Top 3 priorities before the deadline

1. **Make the GEMINI loop physical.**
   - Scale the train resistances to flow, add a booster where needed, and fail the run on any pressure below the separator pressure.
   - Fix `duty_esp`'s `(60/hz)` factor so GEMINI's ESP is 70 % and agrees with the plant model.
   - Today a judge who clicks "Run on GEMINI" on the recommended design sees -2.2 bar and 419 vs 391 kW.
2. **Add the gas physics and the two missing checks.**
   - A Henry's-law bubble point and flash; ESP intake ≥ Pb + margin; ESP depth set from it.
   - An N-1 peak check with the largest doublet out (boiler +7 MW).
   - Teach the claim checker to reject checks that do not exist.
3. **Let the agent answer production questions.**
   - Add ESP, injection, wellhead-pressure and gas facts to the lookup and the design block.
   - Fix the `wellhead` → temperature mapping.
   - Stop the draft-value retry and the cost-list fallback from replacing the answer.

*Evidence: threads prod-1 (2D-HP-AB, edits U1-U4) and prod-2 (2D-HP-AB-2I-ST) on http://127.0.0.1:8790. My check scripts are in the scratchpad: prod_check1.py, prod_esp.py, prod_gas.py, prod_gas2.py, prod_depth.py, prod_year.py, prod_n1.py. The plant-model reruns reproduce the server's pumps figure (4.135 GWh) exactly.*
