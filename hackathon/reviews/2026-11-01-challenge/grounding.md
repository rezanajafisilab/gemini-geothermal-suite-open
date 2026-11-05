# Grounding audit: does Dioscuri make things up? (1 Nov 2026)

Challenger: grounding. Server http://127.0.0.1:8822 (qwen3:1.7b reader, qwen3.5:9b answerer, GPU).
Threads: `aud-g1` (best-overall design, 40 turns) and `aud-g2` (gas-free design, 9 turns). I checked every
number and factual claim in each reply against `panel.py design … all`, `designs`, `attempts`, `gemini`, the
full workbench JSON (`/api/workbench`), the operator PDF (`/api/report.pdf`), the demand CSVs, and hand
calculations in Python (heat = flow × 1,030 kg/m³ × 3,990 J/kg·K × ΔT).

Note on IDs: in `aud-g1` the chosen design was **A1 · 1D-HP-EC-N1** until turn 33. From turn 34 on the
system calls the same design **G1 · 1D-HP-EC-N1** (A17 became G17, A49 became G49 and so on). To reproduce,
use `panel.py design aud-g1 "G1 · 1D-HP-EC-N1" all`.

## 1. Verdict

**Fail, not yet hallucination-free.** Every number the *code* writes is right: the design reply, the
failure what-if with its costs and the spare-ESP case, the compare and what-if cards, the operator PDF
(about 40 values checked) and the GEMINI run. I could reproduce all of them by hand. The problem is the
answerer's free text in follow-up questions. Of about 190 claims checked, **35 were wrong**: values under
the wrong name, false premises accepted, a rival design's figure given to the chosen one, a formula that does
not compute, and false statements about what Dioscuri can do. **14 more replies said a value was missing
when the design holds it.** The worst cases came from plain questions: "the total yearly cost is 30.6 M€"
(that is the capital), the cost of heat and the cost of cold swapped, and "Yes, that is correct" to "the cost
of heat is 69.8 €/MWh and the boiler gives about a quarter of the heat" (the true values are 75.7 €/MWh and
49.2 %).

The number check works: it removed 8 invented numbers from first drafts, so roughly one draft in five
contained a made-up number. But it cannot see three things:
- what a number is called (its label);
- figures written as words ("a quarter");
- whether a stated calculation holds.

The claim checker is skipped whenever a code draft exists, which covers most value questions. When it does
run, it removed true sentences 5 times and let a false one through once.

## 2. Every claim checked

Verdicts:
- **PASS**: the claim matches the data.
- **FAIL**: a hallucination, a wrong label, a wrong unit, arithmetic that does not hold, or a false premise accepted.
- **MISS**: the reply says the data lacks a value that the design holds.
- **CAUGHT**: the first draft invented a number and the number check removed it.
- **OVER**: the claim checker removed a true sentence.
- **WEAK**: the reply makes no false claim but does not answer the question.
- **LOW**: a minor wording problem.

The exact messages sent are in the appendix (turn IDs `g1-nn` and `g2-nn`).

| # | Turn | Claim in the reply | Data's value (where) | Verdict |
|---|---|---|---|---|
| 1 | g1-01 | Heat 111.67 GWh, peak 30 MW on 2027-01-28; cold 23.74 GWh, peak 10 MW on 2027-07-19 | CSV: 4,652.82 MW·d × 24 = 111.67 GWh, max 30.0 on 01-28; 989.27 × 24 = 23.74 GWh, max 10.0 on 07-19 | PASS |
| 2 | g1-01 | 87 °C = 12 + 30 °C/km × 2.5 km | 87.0 | PASS |
| 3 | g1-02 | 1 doublet at 2,500 m, heat pump top-up, gas boiler (3 units), electric chillers, N-1 | plant: 1 doublet, HP 2.0 MW, boiler 31.2 MW (3 units), chillers 15 MW (3 units) | PASS |
| 4 | g1-02 | 69.8 €/MWh for heat and cold together | economics.lcoe 69.8 | PASS |
| 5 | g1-02 | 42.1 % CO₂ saving against gas | co2_saving_pct 42.1 (1 − 14,103.2/24,364.9) | PASS |
| 6 | g1-02 | Heat 37.4 % doublet, 13.4 % heat pump, 49.2 % boiler | 41.75 / 14.929 / 54.988 of 111.668 GWh = 37.39 / 13.37 / 49.24 % | PASS |
| 7 | g1-02 | Cold 100 % electric chillers | cool_split chill 23.743, abs 0 | PASS |
| 8 | g1-02 | Heat 75.7 €/MWh, cold 42.1 €/MWh | lcoh 75.69, lcoc 42.11 | PASS |
| 9 | g1-02 | Passes all 14 checks; meets every day | 14/14; coverage 1.0 | PASS |
| 10 | g1-02 | Returns 60/25 °C assumed; 330 days | inputs card | PASS |
| 11 | g1-03 | Capital 30.6 M€ | capex_meur 30.638 | PASS |
| 12 | g1-03 | Wells 11 M€ | 10.959 | PASS |
| 13 | g1-03 | The three biggest items: wells, "Surface plant 2.9 M€", electric chillers 3.7 M€ | capex_items: wells 10.96, surface plant (per MW) **7.76**, chillers 3.68, surface plant 2.90 (4th) | FAIL |
| 14 | g1-04 | 14,103 t CO₂ a year | 14,103.2 | PASS |
| 15 | g1-04 | Gas reference 24,365 t; 42.1 % less | 24,364.9; 42.1 | PASS |
| 16 | g1-04 | "two main sources": gas combustion, produced gas | co2_t: bought gas 9,430.8, produced gas 2,763.1, **electricity 1,909.3** (13.5 %) | FAIL |
| 17 | g1-04 | "gas produced from the brine is cleaned and sold to the grid; if not sold, burnt in a small on-site boiler" | A1: gas "buy"; produced_gas_sold 0; 11.195 GWh burnt in the main boiler; no GS flag | FAIL |
| 18 | g1-04 | produced gas "that might be flared" | produced_gas_flared 0; design notes: no flare | FAIL |
| 19 | g1-05 | Not 4 doublets but 1 | n_doublets 1 | PASS |
| 20 | g1-05 | "does not specify the exact volumetric flow rate" | cap 300 m³/h; mean when running 222.1; year mean 200.8 | MISS |
| 21 | g1-05 | Heat exchanger 7.23 MW | sizes_mw.heat_exchanger 7.23 | PASS |
| 22 | g1-06 | Heat pump 2 MW, COP 4.5, Carnot 7.8 | 2.0; 4.467; 7.797 | PASS |
| 23 | g1-06 | Treats the user's "COP 9" as a new case ("its original COP was 4.5") | COP 4.467 | FAIL (premise not rejected) |
| 24 | g1-06 | "the boiler out leaves heat 20.8 MW short", said of A1 | A1: 0 of 5 one-unit-out cases short; 20.8 MW is 1D-HP-EC / 1D-HP-AB (attempts) | FAIL |
| 25 | g1-06 | "without explicit total annual heat demand … we cannot calculate" | 111.67 GWh; heat-pump heat 14.929 GWh; its electricity 3.342 GWh | MISS |
| 26 | g1-06 | Reasoning shown to the user, cut off at "let's assume" | – | FAIL (format) |
| 27 | g1-07 | "does not state the specific skin factor" | design well notes: "skin 0 … assumed" (answer.py design notes; PDF p.6) | MISS |
| 28 | g1-07 | Productivity index "not available" | 14.51 m³/h/bar | MISS |
| 29 | g1-07 | Wellhead 86.1 °C, flow 300 m³/h, 87 °C | 86.1; 300; 87 | PASS |
| 30 | g1-08 | No ESP make or model is specified | GEMINI project: "GEMINI's example ESP scaled to 300 m³/h, 17 stages" | PASS |
| 31 | g1-08 | ESP draws 0.39 MW | esp_mw 0.391; GEMINI 390,994 W | PASS |
| 32 | g1-08 | ESP at 732 m or deeper, at most 1,000 m | check | PASS |
| 33 | g1-08 | Wellhead 86.1 °C, reinjection 52.1 °C | 86.1; 52.14 | PASS |
| 34 | g1-09 | No household price; plant cost 75.7; networks, taxes and tariff not in it | money lines | PASS |
| 35 | g1-10 | No 2040 projection; 75.7 €/MWh, 14,103 t; prices 69.4 / 185.7 / 73.9 | data | PASS |
| 36 | g1-11 | Draft: "1.08" $/€, "81.76" $/MWh | no exchange rate in data | CAUGHT |
| 37 | g1-11 | Final: only 75.7 €/MWh; €/GJ (75.69/3.6 = 21.0) silently dropped | – | PASS (unhelpful) |
| 38 | g1-11 | Follow-up "cost of heat for design 1D-HP-EC-N2?" | no such design | FAIL |
| 39 | g1-12 | "does not state the total volume of natural gas purchased or burned" | bought 46.687 GWh; produced gas burnt 11.195 GWh | MISS |
| 40 | g1-12 | "29 €/MWh for purchased gas" | line "Gas" 29.02 €/MWh *of heat*; the gas price is 69.4 €/MWh | LOW (ambiguous) |
| 41 | g1-12 | 6.2 €/MWh CO₂ for that gas | "CO2: gas" 6.24 | PASS |
| 42 | g1-12 | "1.8 €/MWh for produced gas" | the line is "CO2: produced gas" 1.83, a carbon cost | FAIL (label) |
| 43 | g1-13 | Drafts: "39", "9,104" | not in data | CAUGHT |
| 44 | g1-13 | One doublet against two: "from 69.8 €/MWh to 87.6 €/MWh" | 87.55 is 2D-HP-AB-EB-GS (electric boiler, gas sold, not N-1); cheapest 2-doublet 2D-HP-AB 71.39; reliable 2D-HP-AB-N1 73.32 (78.3 vs 76.4 with CO₂ at 137 €/t) | FAIL |
| 45 | g1-14 | 69.8 vs 68.1 €/MWh, +1.7 | 69.8, 68.13 | PASS |
| 46 | g1-14 | 30.6 vs 29.5 M€, +1.1 | 30.638, 29.523 | PASS |
| 47 | g1-14 | 14,103 vs 14,334 t, −231 | 14,103.2, 14,333.9 | PASS |
| 48 | g1-14 | A17: boiler out, heat 20.8 MW short; A1 N-1 | attempts; firm 0 of 5 | PASS |
| 49 | g1-14 | Claim check removed the same true figures from the prose, leaving "However, it achieves this…" | – | OVER |
| 50 | g1-15 | SDE++ question refused as "outside what I do" | investor.sde: category, 3.351 M€ in year 1, 15 years, 56.68 GWh | FAIL (wrong refusal) |
| 51 | g1-16 | NPV 34.8 M€, IRR 16.1 %, payback 7 years (with SDE++) | 34.8; 0.1606; 7.0 | PASS |
| 52 | g1-16 | Without SDE++: 16 M€, 9.7 %, 13 years | 15.98; 0.097; 13.0 | PASS |
| 53 | g1-16 | Category "Diepe geothermie <12 MWth (basislast)", 79.9 €/MWh, 56.7 GWh | same | PASS |
| 54 | g1-16 | 3.4 M€ in year 1 | meur_first_year 3.351 | PASS |
| 55 | g1-16 | "calculated as 79.9 €/MWh × 56.7 GWh" | 79.9 × 56.7 = **4.53** M€; true: (79.9 − 19.6) × 56.68 = 3.42 M€, 3.35 M€ in today's euros | FAIL (arithmetic) |
| 56 | g1-17 | Failure costs and spare ESP "not possible to determine" | dioscuri_plant.failure_costs computes them (see g1-18) | MISS |
| 57 | g1-17 | Geothermal O&M 9.5 €/MWh; ESP head 54 vs 33 bar, 1.26 GWh/yr (PL variant) | 9.54; attempts reason | PASS |
| 58 | g1-18 | ESP out 13 Jan–2 Feb (21 days), demand still met | failure card: 0 days short | PASS |
| 59 | g1-18 | 5.86 GWh more gas | by hand: (3.642 + 1.008 GWh)/0.95 + 0.962 GWh of produced gas lost = 5.857 | PASS |
| 60 | g1-18 | 841 t more CO₂; 381 k€ | by hand ≈ 839 t; ≈ 370 k€ before variable O&M (within 3 %) | PASS |
| 61 | g1-18 | Spare saves 3.91 GWh, 254 k€, for 20 k€ a year (0.3 M€) | 5.857 × 14/21 = 3.905; 380.6 × 2/3 = 253.7; annuity 5.2 %, 30 years = 19.7 k€ | PASS |
| 62 | g1-18 | Failures 928 k€ a year; ESP fails every 2 years, out 120 days | RATES esp 0.5/yr, 120 days (sources in failure_costs.SOURCES) | PASS |
| 63 | g1-18 | 709 saved, 689 net, 219 with spare; pays if failures more often than every 71 years | 928 − 709 = 219; 709 − 20 = 689; 709 × 2/20 = 70.9 | PASS |
| 64 | g1-19 | "no specific data … for the peak day of 28 January" | 30.0 = HX 7.23 + HP 2.0 + boiler 20.77 MW; spare 10.43 MW | MISS |
| 65 | g1-20 | Draft: "24.3" MW on 28 Jan | 24.313 is 1 Jan; 28 Jan is 30.0 | CAUGHT |
| 66 | g1-20 | "I would need the specific demand value for that date … If you can provide the exact demand" | 30 MW on 28 Jan (inputs card) | MISS |
| 67 | g1-21 | Draft: largest brine cooling "34" K (86.1 − 52.1) | max_brine_cooling_k 30.98 | CAUGHT |
| 68 | g1-21 | 86.1 °C, 52.1 °C | data | PASS |
| 69 | g1-21 | Largest cooling and mean flow "not listed" | 30.98 K (check "at most 31.0 K"); 200.8 m³/h | MISS |
| 70 | g1-22 | 330 days on; stopped 35 days, 9 Jul–12 Aug; least-brine weeks, not for wear | stop_days [189, 223]; stops.py wording | PASS |
| 71 | g1-22 | Does not name the 330-day cap as the reason | stops.why: "the 330-day cap" | LOW |
| 72 | g1-23 | Asked for injection pressure; reply gives "the brine temperature at the wellhead is 86.1 °C" | injection wellhead 22.6 bar; top of reservoir 265.6 bar vs 330.8 bar (65.2 bar = 946 psi) | FAIL (wrong quantity) |
| 73 | g1-24 | Cold 42.1 vs 36.2 €/MWh (dearer); heat 75.7 vs 92.2 (cheaper) | lcoc 42.11 vs 36.17; lcoh 75.69 vs 92.24 | PASS |
| 74 | g1-25 | "the total yearly cost is **30.6 M€**" | that is capital; yearly cost 75.69 × 111.668 + 42.11 × 23.743 = **9.45 M€** | FAIL (label) |
| 75 | g1-25 | "a cost of heat and cold of **75.7 €/MWh**" | heat and cold 69.8; 75.7 is heat | FAIL (label) |
| 76 | g1-25 | "The specific cost of heat alone is **42.1 €/MWh**" | 42.1 is cold; heat 75.7 | FAIL (label) |
| 77 | g1-25 | "within the project's budgetary caps" | no budget cap anywhere | FAIL |
| 78 | g1-26 | Premise "A1 uses absorption chillers" not corrected; follow-up repeats it | absorption 0 MW; cold 100 % electric | FAIL (premise) |
| 79 | g1-27 | Drafts: "1,050" kg/m³, "3,900" J/kg·K | 1,030; 3,990 | CAUGHT |
| 80 | g1-27 | Flow and ΔT "not listed"; "any calculation would be an invention" | 300 m³/h, 30.98 K → 300/3600 × 1030 × 3990 × 30.98 = 10.61 MW (= SDE++ capacity) | MISS |
| 81 | g1-28 | Drafts: "2023", "2024"; "total project budget of 11 M€" | not in data; 11 M€ is the wells | CAUGHT |
| 82 | g1-28 | Final: cannot confirm the price and well-cost sources | inputs card: Eurostat 2025 NL; PDF: nrg_pc_203 band I4 | MISS |
| 83 | g1-29 | No IEA figure given; A1 69.8 €/MWh | – | PASS |
| 84 | g1-29 | Claim check removed true "75.7 vs 92.2 €/MWh" | – | OVER |
| 85 | g1-30 | Return 45 °C: 64.6 €/MWh, CO₂ −58 %, doublet 56.4 %, boiler 33.8 % | W1 64.55; 58.0; 56.37; 33.77 | PASS |
| 86 | g1-30 | "the heat pump contribution **remains** at 9.9 %" | W1 9.86 %, A1 13.37 %: it fell | FAIL |
| 87 | g1-30 | New search picks 1D-HP-AB-N1 at 63.2 | B1 63.2 | PASS |
| 88 | g1-31 | Network loss "not stated" | inputs card: off (delivered at the plant's gate) | WEAK |
| 89 | g1-31 | "330 days of operation (planned service)"; "planned stoppage of 35 days" | planned service is OFF; the 35 days are the 330-day-cap stop | FAIL (label) |
| 90 | g1-32 | Network losses "not modelled … which Dioscuri does not currently run" | inputs card offers the switch; answer.network_notes models a trunk (it needs a length) | FAIL |
| 91 | g1-32 | Service "already accounted for in the … figures already presented (69.8 €/MWh)" | A1 had no service; with service W2: 69.84, CO₂ −41.9 % | FAIL |
| 92 | g1-32 | "heat pump from 15 Jul to 28 Jul" | service windows not exposed in workbench or trace | UNVERIFIED |
| 93 | g1-32 | Service: 100 % covered; new search 2D-HP-AB-ST-N1 at 73.4 | W2 coverage 1.0; C1 73.4 | PASS |
| 94 | g1-33 | Drafts: "68", "14,000", "16,000"; "gas-free pick … selling produced gas" | not in data; the gas-free pick 2D-HP-AB-N1-EB has no GS | CAUGHT |
| 95 | g1-33 | Final: "refer to the design search results in the project documentation" | gas-free pick 92.7 €/MWh, 7,527 t, 76.3 M€ (g1-02 card) | MISS |
| 96 | g1-34 | G1: 69.8 vs gas reference 82.4 €/MWh, 30.6 M€, N-1 | (92.24 × 111.668 + 36.17 × 23.743)/135.411 = 82.41; 0 of 5 short | PASS |
| 97 | g1-34 | Draft: "200 €" saving | not in data | CAUGHT |
| 98 | g1-35 PDF | Capital table and total 30.64 M€ | sum of capex_items 30.638 | PASS |
| 99 | g1-35 PDF | Peak day 30 = 7.23 + 2 + 20.77 MW; spare 10.4 of 40.4 MW; cold 10 of 15 | daily_mw; firm | PASS |
| 100 | g1-35 PDF | Month table; days on Jul 8, Aug 19 | monthly_gwh; stop 9 Jul–12 Aug | PASS |
| 101 | g1-35 PDF | Limits: ESP room 268 m; injection 266 of 331 bar; breakthrough 85 years; flow 58.5–300 | checks; plant.doublets | PASS |
| 102 | g1-35 PDF | Electricity 3.34 / 2.77 / 0.33 / 3.1 GWh; gas 46.7 bought, 11.2 burnt, 0 flared | year | PASS |
| 103 | g1-35 PDF | −17.9 % / +16.4 % / −15.3 % against gas; payback 10 years, NPV 26 M€; prices and sources | vs_gas_pct; versus_reference | PASS |
| 104 | g1-35 PDF | "No failure what-if has been run on this design yet … (1 what-if(s) were run on other designs.)" | g1-18 ran an ESP failure on this design (then named "A1 · 1D-HP-EC-N1") | FAIL |
| 105 | g1-36 | Asks the user to supply porosity and spacing | design notes: Gringarten-Sauty, 1.5 km, porosity 0.20; 85 years | MISS |
| 106 | g1-37 | Draft: home of 12 MWh pays 908 € vs 1,107 € with gas (removed by claim check) | 12 × 75.69 = 908; 12 × 92.24 = 1,107 (HOME_MWH 12) | OVER |
| 107 | g1-38 | "**Yes, that is correct**" to "cost of heat is 69.8 €/MWh" | cost of heat 75.69; 69.8 is heat and cold | FAIL (premise) |
| 108 | g1-38 | "does not give an exact percentage breakdown of heat output by source" | 37.4 / 13.4 / 49.2 % | FAIL |
| 109 | g1-38 | The boiler giving "about a quarter" "aligns with the typical role" | boiler 49.2 % | FAIL (premise) |
| 110 | g1-38 | "to meet the 69.8 €/MWh target" | a result, not a target | FAIL (label) |
| 111 | g1-38 | G17: boiler out, 20.8 MW short | G17 = 1D-HP-AB | PASS |
| 112 | g1-39 | Reservoir −5 K: 74.1 €/MWh, −33.7 % CO₂, reinjection 48.8 °C, boiler 57.7 % | W3 74.05; 33.7; 48.82; 57.69 | PASS |
| 113 | g1-39 | New search 1D-HP-AB-N1 at 73.9 | D1 73.89 | PASS |
| 114 | g1-39 | "the chosen design (1D-HP-EC-N1) still covers 100 %", no word on reliability; W3 still named "(N-1)", reliable = true | W3 firm: 1 of 5 cases short (one boiler unit out leaves 1.69 MW short on 28 Jan) | FAIL |
| 115 | g1-40 | Heat sold at 92.2, cold at 36.2: what the buyer's own gas boilers and chillers would cost | investor 92.24, 36.17, basis "gas reference" | PASS |
| 116 | g1-40 | "does not mention the ACM's maximum heat tariff" | investor.sources holds it (40.97 €/GJ incl. VAT ≈ 122 €/MWh excl.); not in the answerer's context | PASS (honest) |
| 117 | g2-02 | 2D-HP-AB-N1-EB-GS: 101.7 (heat 111.1, cold 57.6) €/MWh, −79.5 %, 81.8 M€, N-1, gas sold | 101.68 / 111.06 / 57.56; 79.5; 81.839; 0 of 8; sold 17.882 GWh | PASS |
| 118 | g2-02 | "a heat pump for most heating" | HP 48.0 %, exchanger **51.8 %**, electric boiler 0.15 % | FAIL (minor) |
| 119 | g2-03 | Fallback: "CO₂ saving 79.5 %" for "zero CO₂, right?"; premise not rejected in words | 4,998.5 t | WEAK |
| 120 | g2-04 | Same fallback for "tonnes by source" | electricity 4,115.8 t, produced gas 882.7 t; sold gas burnt by buyers 3,612.1 t | WEAK |
| 121 | g2-05 | "Design 2D-HP-AB-N1-EB-GS has no peak boiler size" | **electric boiler 30 MW** (3 units), 0.172 GWh a year, 1.97 M€ a year | FAIL |
| 122 | g2-06 | Removed: NPV −13.4 / −40.3 M€, IRR 3.3 % / 0.1 %, no payback | −13.41; −40.28; 0.0327; 0.0012; None | OVER |
| 123 | g2-06 | Needs a subsidy | needs_subsidy true (break-even basisbedrag 80.8 vs 62.7 €/MWh) | PASS |
| 124 | g2-06 | 13.8 vs 11.2 M€ a year; capital 81.8 vs 4.7 M€; 4,999 vs 24,365 t, 79.5 % | 111.06 × 111.668 + 57.56 × 23.743 = 13.77; 11.16; 81.839 − 77.14 = 4.70 | PASS |
| 125 | g2-06 | "this environmental benefit is not currently monetized in the financial model" | CO₂ at 73.9 €/t is in both the plant's and the reference's costs; the SDE++ correction includes ETS2 | FAIL |
| 126 | g2-06 | Follow-up "revenue from selling produced gas that was not included in this model?" | "Gas sold" line −5.87 / −1.78 €/MWh = 0.70 M€ a year | FAIL |
| 127 | g2-07 | "does not contain the specific annual volume of brine gas sold" | produced_gas_sold 17.882 GWh | MISS |
| 128 | g2-07 | Gas sold −5.9 €/MWh (heat), −1.8 (cold) | −5.87, −1.78 | PASS |
| 129 | g2-07 | "annual heat and cold production figures (which are given as 111.1 €/MWh and 57.6 €/MWh…)" | those are costs; production is 111.67 / 23.74 GWh | FAIL (label) |
| 130 | g2-08 | 101.7 / 87.5 €/MWh, 4,998 t each, 81.8 / 69.6 M€, 0 / 8 cases short | 101.68 / 87.55 / 4,998.5 / 81.839 / 69.584 | PASS (87.55 is 87.5 here, 87.6 in g1-13) |
| 131 | g2-08 | Compare card "Boiler (MW): [0.0, 0.0]", no electric-boiler row | electric boiler 30 vs 2.6 MW: the difference that makes A1 N-1 | FAIL (card) |
| 132 | g2-09 | Electricity 120 €/MWh: 91.7 €/MWh (from 101.7), 100 % covered | W1 91.7 | PASS |
| 133 | g2-09 | "finds 2D-HP-EC-N1-EB-GS **cheaper** at 92 €/MWh" | 92.0 > 91.7 (A1 at the same price) | FAIL |
| 134 | g2-09 | Both save 79.5 %; electric chillers instead of absorption | B1 79.5, W1 79.5; code EC | PASS |
| 135 | gemini | Wellhead 86.1 °C, ESP 0.391 MW, head 32.8 bar, injection wellhead 22.6 bar, injection pump 0.221 MW | GEMINI run: 86.104; 390,994 W; 82.14 − 49.33 = 32.8; 22.60; 221,439 W | PASS |

Counted claim by claim (some rows hold several), the tally is about 190 claims:

| Verdict | Count |
|---|---|
| PASS | about 120 |
| FAIL | 35 |
| MISS | 14 |
| CAUGHT | 8 drafts |
| OVER | 5 |
| WEAK | 3 |
| LOW | 3 |
| UNVERIFIED | 1 |

## 3. Hallucinations and mislabels, most serious first

### H1. A cost-of-heat question gives three wrong labels and an invented budget cap (g1-25)

**Message:** "What share of A1's yearly cost is gas, and what share is capital? And how much electricity does
the plant use in a year, split by what uses it?"

**Reply:** "the total yearly cost is **30.6 M€**, which translates to a cost of heat and cold of **75.7
€/MWh**. The specific cost of heat alone is **42.1 €/MWh**. … staying within the project's budgetary caps."

**True values:**
- 30.6 M€ is the capital (`economics.capex_meur` 30.638). The yearly cost is 9.45 M€.
- 75.7 €/MWh is the cost of heat (`lcoh`). Heat and cold together cost 69.8 €/MWh (`lcoe`).
- 42.1 €/MWh is the cost of cold (`lcoc`).
- No budget cap exists.
- What was asked was never given: gas 34.3 % and capital 22.1 % of the cost (`breakdown_pct`); electricity
  9.55 GWh (heat pump 3.34, pumps 3.10, chillers 2.77, towers 0.33).

**Cause:**
- The first attempt failed the `must` check. The retry in `answer.py answer()` said "Keep these values from
  the draft: 30.6 M€, 75.7 €/MWh, 42.1 €/MWh", which gives the values without their names, so the model
  forced them in under the wrong names.
- The number check (`unsourced`) only asks whether a number exists somewhere.
- `_swaps` runs inside the two-attempt loop, but its finding on the last attempt is never enforced:
  `_finish` re-checks numbers only.
- `_swaps` only covers heat ↔ heat-and-cold. It does not cover heat ↔ cold, and nothing checks M€ labels
  (capital against yearly cost).
- The claim checker was skipped. `agent._checks_claims` returns False whenever a draft exists, and this was
  the lookup path.

### H2. False premises answered "Yes, that is correct" (g1-38)

**Message:** "So the cost of heat of the chosen design is 69.8 €/MWh and the boiler gives about a quarter of
the heat, correct?"

**Reply:** "Yes, that is correct based on the provided text. … While the text does not give an exact
percentage breakdown of heat output by source … The statement that the boiler gives 'about a quarter' aligns
with the typical role of such backup/top-up boilers … to meet the 69.8 €/MWh target. The cost of heat is 75.7
€/MWh."

**True values:** cost of heat 75.69 €/MWh (69.8 is heat and cold); boiler 49.24 % of the heat
(`year.heat_split_gwh`). The split was in the first design reply.

**Cause:**
- Lookup path with a draft, so no claim check (`_checks_claims`).
- "A quarter" is a word, so the number check cannot see it.
- The "added back from the checked answer" step appended 75.7 €/MWh without fixing the "Yes" it
  contradicts.
- `prompts/answer_v6.txt` has a premise rule only for "why this and not that" questions.

### H3. Produced gas said to be "sold to the grid" or "flared" in a design that burns it; electricity left out (g1-04)

**Message:** "How many tonnes of CO2 does the chosen design emit per year, where do they come from, and how
many tonnes is that less than the gas reference?"

**Reply:** "These emissions come from two main sources: Gas combustion … Produced gas processing: A small
amount of gas produced from the geothermal brine is cleaned and sold to the grid; however, if not sold, it is
burnt in a small on-site boiler … any produced gas that might be flared".

**True values:** A1 buys gas (`plant.gas` "buy"). Produced gas: 0 sold, 11.195 GWh burnt in the main boiler,
0 flared. CO₂: bought gas 9,430.8 t, produced gas 2,763.1 t, **electricity 1,909.3 t**. Difference from the
reference: 10,262 t, not given.

**Cause:**
- The "small boiler / sold to the gas grid" wording comes from the EB/GS candidates' names in the
  search/decisions blocks (`answer.search_block`, `decisions_block`). The model gave it to the chosen design.
- No claim check on this path (as in H1).
- `economics_block` gives CO₂ only as a total; it does not split it by source.

### H4. A formula that does not compute (g1-16)

**Message:** "For an investor building A1: what are the NPV, IRR and payback with SDE++ and without it, and
how much SDE++ does it receive in the first year?"

**Reply:** "Total SDE++ received in Year 1: 3.4 M€ (calculated as 79.9 €/MWh * 56.7 GWh, rounded to match the
text's figure)."

**True values:** 79.9 × 56.7 = 4.53 M€. The data (`investor.sde`) pays the basisbedrag less the correction:
(79.9 − 19.6) = 60.3 €/MWh × 56.68 GWh = 3.42 M€, which is 3.35 M€ in today's euros (`meur_first_year`
3.351). All the other investor numbers in this reply are right.

**Cause:**
- Each operand and the result exist in the facts, so `unsourced` passes. `_chained`/`_derived` accept
  numbers that can be derived, but do not check the operation the sentence states.
- The claim checker ran and removed nothing.

### H5. The claim checker kept a false claim and removed five true ones (g2-06)

**Message:** "Would an investor build this gas-free plant? Give the NPV and IRR with and without SDE++, and
say whether it needs a subsidy."

**Kept:** "this environmental benefit is not currently monetized in the financial model to offset the high
costs."

**Removed (all true):** NPV −13.4 M€ with SDE++ and −40.3 M€ without; IRR 3.3 % and 0.1 %; no payback.

**What is left:** empty headings, a cut-off "* **Rel**", and a text that implies SDE++ alone makes it viable.
In truth NPV is −13.41 M€ even with SDE++, and break-even needs a basisbedrag of 80.8 €/MWh against the
category's 62.7.

**True value:** CO₂ is priced at 73.9 €/t in both the plant's and the reference's cost lines, and the SDE++
correction includes ETS2 from 2028.

**Cause:**
- `claims.check` → `sources()` fits blocks into `budget()`: (num_ctx − 900) × 3.2 characters, about 10 k
  characters at 4096. The long economics/investor lines are likely cut. Numeric sentences lose their
  evidence; a vague sentence gets a "general" verdict and stays.
- The same pattern appeared in g1-13, g1-14, g1-29 and g1-37 (true sentences removed). In g1-37 the removed
  draft was right: 12 MWh × 75.69 = 908 € against 1,107 €.

### H6. False statements about what Dioscuri models (g1-32)

**Message:** "Switch on the district network heat losses and the yearly planned service for A1. How do the
cost and CO2 change, and how much heat is lost in the network?"

**Reply:** "we cannot calculate the cost or CO₂ change because network heat losses are not modelled … we
would need a model that simulates district pumping and insulation, which Dioscuri does not currently run. …
This downtime is accounted for in the sizing and cost figures already presented (69.8 €/MWh)".

**True values:**
- The inputs card offers "Network heat losses: off … (switch below)". `answer.network_notes` reports a
  trunk's losses and pump energy when the network is on.
- A1 had no planned service. With service on, W2 costs 69.84 €/MWh and saves 41.9 % CO₂.

**Cause:**
- `answer.NOT_IN_DESIGN` (answer.py ≈ line 1203) always says "network losses and pumping" are not modelled,
  even though the model exists behind a switch.
- The parameters step dropped `network_length_km` ("its number is not in the quote") instead of asking for
  a length.

### H7. A rival's cost given as the price of "a second doublet" (g1-13)

**Message:** "Why did you choose one doublet rather than two or three? Give the numbers that decided it."

**Reply (after the claim check):** "This jump raises the levelized cost of heat and cold from **69.8 €/MWh**
to **87.6 €/MWh**."

**True values:** 87.55 €/MWh is 2D-HP-AB-EB-GS: electric boiler, gas sold, not N-1, the lowest-CO₂ pick. The
fair comparisons are:
- 2D-HP-AB at 71.39 €/MWh, 50.4 M€;
- the reliable 2D-HP-AB-N1 at 73.32 €/MWh, 52.8 M€ (78.3 against 76.4 €/MWh with CO₂ at 137 €/t);
- 3D-HP-AB-N1 at 81.68 €/MWh.

The draft first invented "39" and "9,104" (caught).

**Cause:**
- The picks list puts the lowest-CO₂ 2-doublet design forward, and the model took it as "two doublets".
- The claim checker removed the sentence that set the comparison up, leaving "This jump" with nothing
  before it.

### H8. A rival's outage given to A1; the COP premise not rejected; reasoning shown to the user (g1-06)

**Message:** "Since the COP of the heat pump is 9, how much electricity does the heat pump use in a year, and
how big is it?"

**Reply:** "its original COP was 4.5 … The text states that when the boiler is out, the system is short by
20.8 MW of heat … without explicit total annual heat demand … we cannot calculate … let's assume".

**True values:**
- A1 is N-1: 0 of 5 cases short. 20.8 MW is the shortfall of 1D-HP-EC and 1D-HP-AB (attempts).
- COP 4.467. Heat-pump heat 14.929 GWh; electricity 3.342 GWh (14.929/3.342 = 4.47).

**Cause:**
- The search block's reasons ("not sized for one unit out: the boiler out leaves heat 20.8 MW short") stand
  next to the chosen design without naming the rival inside the sentence.
- The reasoning text leaked, and the reply was cut at the length limit (NUM_PREDICT).

### H9. The operator PDF says no failure what-if was run on the design (g1-35)

**Reply (PDF section 4):** "No failure what-if has been run on this design yet. … (1 what-if(s) were run on
other designs.)"

**True value:** the ESP failure in g1-18 ran on this very design, then named "A1 · 1D-HP-EC-N1". The system
renamed it G1 later.

**Cause:** `report_pdf.py:1834` matches `f.get("design") == did` on the display id, and the ledger re-letters
designs mid-conversation (A1 became G1).

### H10. A what-if keeps the "(N-1)" name after losing N-1 (g1-39)

W3 (reservoir 5 K colder) is named "… sized so that any one unit can be out (N-1)" and has `reliable` = true.
Its own firm data says "one unit out: 1 of 5 cases short: one of the 3 boiler units 1.69 MW heat on 28 Jan".

The reply says only "still covers 100 % of heat and cold demands".

**Cause:** the what-if path copies the base design's flags and name and does not recompute `reliable` from
the new firm result.

### H11. Code says the gas-free design has no peak boiler (g2-05)

**Message:** "How big is the electric boiler in A1, how much heat does it give in the year, and why was it made
that big?"

**Reply (rules fallback):** "The share of the heat demand covered is 100%. … Design 2D-HP-AB-N1-EB-GS has no
peak boiler size."

**True values:** electric boiler 30 MW in 3 units. It gives 0.172 GWh a year (0.15 % of the heat) and costs
1.97 M€ a year (capital 1.00, O&M 0.23, grid capacity 0.74). It went from 2.6 to 30 MW for N-1.

**Cause:**
- `lookup.design_facts` (lookup.py 241–283) has no electric-boiler fact; `reporter.py:1049` writes "has no
  peak boiler size".
- The design's own change log says "reliable plan: boiler 0 -> 0 MW as 1 units". It also leaves out the
  electric boiler's change from 2.6 to 30 MW.

### H12. A pressure question answered with a temperature (g1-23)

**Message:** "What injection pressure does A1 need at the wellhead and at the top of the reservoir, and how
close is that to the regulator's limit? Express the margin in psi too."

**Reply (rules):** "The brine temperature at the wellhead is 86.1 °C … The initial reservoir temperature is 87
°C".

**True values:** injection wellhead 22.6 bar; top of the reservoir 265.6 bar against SodM's 330.8 bar; margin
65.2 bar = 946 psi.

**Cause:** `lookup.wanted` matches "wellhead" to `wellhead_temp`, and `design_facts` has no injection
pressure.

### H13. Other wrong labels

- **g1-31**, "330 days of operation (planned service)". Planned service was off; the 35 days off are the
  330-day-cap stop (`stops.why`).
- **g1-12**, "1.8 €/MWh for produced gas". The line is "CO2: produced gas", a carbon cost.
- **g2-07**, "annual heat and cold production figures (which are given as 111.1 €/MWh and 57.6 €/MWh)". Those
  are costs; production is 111.67 and 23.74 GWh.
- **g2-02**, "a heat pump for most heating". The heat exchanger gives 51.8 %, the heat pump 48.0 %.

### H14. Wrong comparisons

- **g2-09**, "finds 2D-HP-EC-N1-EB-GS cheaper at 92 €/MWh". The what-if of A1 at the same price costs
  91.7 €/MWh. The re-search itself picks a dearer design than the current one under the change.
- **g1-30**, the heat pump "remains at 9.9 %". It fell from 13.4 %.
- **g1-03**, the "three biggest items" left out the 7.76 M€ surface-plant (per MW) item and put 2.9 M€ second.

### H15. Suggestions that invent designs or carry false premises

- g1-11 suggests "the cost of heat for design 1D-HP-EC-N2" (no such design).
- g1-26 suggests "How does the capacity of the absorption chiller compare to the electric chiller in design
  A1?" (A1 has none).
- g2-06 suggests gas-sale revenue is "not included in this model" (it is, 0.70 M€ a year).

**Cause:** `follow_ups` are not number- or claim-checked.

### H16. A compare card hides the electric boiler (g2-08)

The "Boiler (MW)" row shows [0.0, 0.0] for both designs, and there is no electric-boiler row. Yet 30 against
2.6 MW is what makes A1 N-1. Also, "Against gas (%)" has no sign and does not say whether it means cost or
CO₂ (+23 % here means dearer).

### Saying the data lacks a value it holds (14 turns; no number invented, but untrue)

| Turn | Asked for | The reply said | The data holds |
|---|---|---|---|
| g1-05 | flow | not specified | 300 m³/h |
| g1-07 | skin factor, productivity index | not available | skin 0 (assumed), 14.51 m³/h/bar |
| g1-12 | gas volumes | not stated | 46.7 GWh bought, 11.2 GWh produced gas burnt |
| g1-17 | failure costs | not possible | computed by failure_costs.py (see g1-18) |
| g1-19, g1-20 | 28 January | no data; asked the user for the demand | 30 MW split by unit |
| g1-21 | largest brine cooling, mean flow | not listed | 31 K, 200.8 m³/h |
| g1-27 | flow and ΔT | not listed | 300 m³/h, 31 K |
| g1-28 | price sources | could not confirm | Eurostat 2025 NL |
| g1-33 | gas-free pick values | see the documentation | 92.7 €/MWh, 7,527 t |
| g1-36 | porosity, spacing | asked the user | 0.20, 1.5 km |
| g2-04 | CO₂ by source | not answered | 4,115.8 t electricity, 882.7 t produced gas |
| g2-07 | gas sold | not given | 17.9 GWh |

**Cause:**
- `agent._write` adds full design blocks only when DESIGN_TALK / COST_TALK / GEMINI_TALK match. Otherwise
  the pack is a one-line `designs_line` plus economics.
- The "explain", "about" and "docs" routes bring documents instead.
- `lookup.design_facts` is a short list with no flow, brine cooling, injection pressure, productivity index
  or skin, gas volumes, CO₂ split, electric boiler, sold gas, porosity or spacing.
- The intake model (qwen3:1.7b) marked SDE++, investor and board questions "relevant: false" four times, and
  once refused outright (g1-15).

## 4. What is solid

- **Replies written by code are right.** All of the following matched the data and my hand checks:
  - the design reply's numbers (g1-02, g2-02);
  - the failure what-if (g1-18): 21 days, 5.86 GWh, 841 t, 381 k€, the spare ESP's 254 k€ for 20 k€ a year,
    928/709/219 k€ a year, 71 years. Rates and repair times are sourced in `failure_costs.SOURCES`;
  - the compare tables (g1-14, g2-08), the what-if result cards (W1, W2, W3) and the decision summary
    (g1-34).
- **The operator PDF:** about 40 values checked (capital table, peak-day stack, month table, limits, checks,
  prices with Eurostat/PBL/EU ETS sources). All were right except the failure-section line (H9).
- **GEMINI agrees with the design:** wellhead 86.104 °C, ESP 391 kW and 32.8 bar, injection 22.6 bar and
  221 kW. The demand totals and peaks match the CSVs exactly.
- **Honest "I don't have that"** for values that are not in the data: the ESP make (g1-08), the household
  price (g1-09), 2040 (g1-10), an IEA figure (g1-29), the ACM tariff (g1-40). The "4 doublets" premise was
  rejected (g1-05).
- **The number check works for numbers.** It removed 8 invented values before the user saw them: 1.08 $/€,
  39, 9,104, 24.3 MW, 34 K, 1,050 kg/m³ and 3,900 J/kg·K, 2023/2024, 68 / 14,000 / 16,000, and 200 €.

### Fixes, in order of value

1. **A last code gate on labels before a reply goes out.** Extend `_swaps` to cover:
   - heat ↔ cold;
   - capital (M€) ↔ yearly cost;
   - shares (a fraction of the heat named for the wrong unit).

   Make it final: show the draft if the second attempt still fails. Give `must` values with their labels
   ("capital 30.6 M€; cost of heat 75.7 €/MWh; cost of cold 42.1 €/MWh").
2. **Check the premise in code.** When the message states a value or fact about the design ("COP is 9", "4
   doublets", "a quarter", "uses absorption"), compare it with the design's facts and lead with the
   correction.
3. **Claim-check the sentences the model adds to a draft** (`claims.candidates` already strips copied ones).
   Feed the checker the economics/investor block first, so true money sentences are not removed.
4. **Widen `lookup.design_facts`:** flow, brine cooling, injection pressure, productivity index and skin, gas
   bought/burnt/sold, CO₂ by source, electric boiler, porosity and spacing. Make `NOT_IN_DESIGN` depend on
   what is switched on.
5. **Keep design IDs stable,** or key failures by code and changes. Recompute `reliable` and the "(N-1)" name
   after a what-if. Name the rival inside each search-block reason.

## Appendix: messages sent

**aud-g1**

- **g1-01:** "Design a geothermal heating and cooling system for the district in the challenge files."
- **g1-02:** click 1 (run with these inputs).
- **g1-03:** "What is the total capital cost of the chosen design, and what are its three biggest items?"
- **g1-04:** "How many tonnes of CO2 does the chosen design emit per year, where do they come from, and how many
  tonnes is that less than the gas reference?"
- **g1-05:** "Your design uses 4 doublets, right? How much flow does each of them produce?"
- **g1-06:** "Since the COP of the heat pump is 9, how much electricity does the heat pump use in a year, and how
  big is it?"
- **g1-07:** "What skin factor did you assume for the production well, and what is its productivity index?"
- **g1-08:** "Which exact ESP model (manufacturer and model number) does the design use, how much power does it draw
  and at what depth is it set?"
- **g1-09:** "What heat price will the households in the district pay per MWh, including VAT and the network?"
- **g1-10:** "What will the cost of heat and the CO2 emissions of this design be in 2040?"
- **g1-11:** "Give me the cost of heat in euros per GJ and in US dollars per MWh."
- **g1-12:** "How much natural gas does the plant buy in a year, and how much of the gas that comes up with the brine
  does it burn?"
- **g1-13:** "Why did you choose one doublet rather than two or three? Give the numbers that decided it."
- **g1-14:** "Compare the best overall pick with the cheapest pick: cost per MWh, capital, CO2 and what happens when
  one unit is out."
- **g1-15:** "How much SDE++ subsidy does the chosen design get, in which category, for how many years, and on how
  much heat?"
- **g1-16:** "For an investor building A1: what are the NPV, IRR and payback with SDE++ and without it, and how much
  SDE++ does it receive in the first year?"
- **g1-17:** "What do equipment failures cost this design a year, and would a spare ESP pay for itself?"
- **g1-18:** "What if the ESP of doublet 1 fails for three weeks in winter? How much heat is lost, what does it
  cost, and would a spare ESP pay?"
- **g1-19:** "On the peak day, 28 January, how much heat does each unit deliver, and how much spare capacity is
  left?"
- **g1-20:** "Show the operation of A1 on 28 January: heat demand, what the doublet, the heat pump and the boiler
  give, and the brine flow."
- **g1-21:** "For A1, what are the wellhead temperature, the reinjection temperature, the largest brine cooling,
  and the mean brine flow over the year?"
- **g1-22:** "How many days a year does the A1 doublet run, when is it stopped, and why then?"
- **g1-23:** "What injection pressure does A1 need at the wellhead and at the top of the reservoir, and how close
  is that to the regulator's limit? Express the margin in psi too."
- **g1-24:** "Is A1's cold cheaper than the gas reference's cold? And its heat? Give both pairs of numbers."
- **g1-25:** "What share of A1's yearly cost is gas, and what share is capital? And how much electricity does the
  plant use in a year, split by what uses it?"
- **g1-26:** "Since A1 uses absorption chillers, how much of the doublet's heat goes to them in summer?"
- **g1-27:** "How much geothermal heat in MW does the A1 doublet give at full flow, counting the heat exchanger and
  the heat pump's source? Show the calculation with flow, density, heat capacity and temperature drop."
- **g1-28:** "What is the source of the well cost you used, about 5.5 M€ per well at 2,500 m? And where does the
  gas price of 69.4 €/MWh come from?"
- **g1-29:** "According to the IEA's Geothermal Outlook 2025, what is the typical levelised cost of geothermal heat
  in the Netherlands, and how does A1 compare with it?"
- **g1-30:** "What if the heating network return were 45 °C instead of 60 °C? What happens to A1's cost and CO2?"
- **g1-31:** "How much heat does A1 lose in the district network each year, and how many days of planned service
  does it take?"
- **g1-32:** "Switch on the district network heat losses and the yearly planned service for A1. How do the cost and
  CO2 change, and how much heat is lost in the network?"
- **g1-33:** "Explain the gas-free pick from the first search: what heats the district instead of gas, what happens
  to the gas that comes up with the brine, what it costs per MWh, and its CO2 a year."
- **g1-34:** "Summarise the decision on A1 for the municipality's board in five bullet points with the key
  numbers."
- **g1-35:** "Make the operator's PDF report for the chosen design." (The PDF was then downloaded from
  /api/report.pdf.)
- **g1-36:** "What porosity and well spacing did you assume for the cold-front estimate, and when does cold water
  reach the producer?"
- **g1-37:** "What would a typical home's heat cost per year at the plant's cost of heat, compared with gas
  boilers?"
- **g1-38:** "So the cost of heat of the chosen design is 69.8 €/MWh and the boiler gives about a quarter of the
  heat, correct?"
- **g1-39:** "First run the chosen design with the reservoir 5 °C colder, then compare that result with the chosen
  design."
- **g1-40:** "At what price does the investor's case sell the heat and the cold, and what is that price based on?
  Is it above or below the ACM's maximum heat tariff?"
- **gemini:** `panel.py gemini aud-g1 "G1 · 1D-HP-EC-N1"`.

**aud-g2**

- **g2-01:** "Design a heating and cooling system for the challenge district that buys no natural gas at all."
- **g2-02:** click 1 (run with these inputs).
- **g2-03:** "Since this design buys no gas, its CO2 emissions are zero, right? Where would any CO2 come from?"
- **g2-04:** "How many tonnes of CO2 a year does the gas-free design emit, split by source, and what about the gas
  it sells?"
- **g2-05:** "How big is the electric boiler in A1, how much heat does it give in the year, and why was it made that
  big?"
- **g2-06:** "Would an investor build this gas-free plant? Give the NPV and IRR with and without SDE++, and say
  whether it needs a subsidy."
- **g2-07:** "How much of the brine's gas does the A1 plant sell in a year, what does the sale earn, and what does
  cleaning and injecting it cost?"
- **g2-08:** "Compare A1 with A2: cost of heat and cold, capital, CO2, and what one unit out does to each."
- **g2-09:** "What if electricity cost 120 €/MWh instead of 185.7? What happens to A1's cost of heat and cold?"

Raw transcripts, the workbench JSON and the PDF text are in the challenger's scratchpad. They are not part of
the repository.
