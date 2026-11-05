# Calculation audit, 4 Nov 2026

Before fine-tuning a model on the app's outputs, five independent reviewers checked the deterministic calculations:
- subsurface and wells;
- the surface plant and the yearly dispatch;
- cooling;
- economics and finance;
- reliability, N-1 sizing and the design search.

Each reviewer worked out the right equations from first principles, ran our code on concrete inputs, compared the two and listed what they found correct. Their scratch scripts are kept in `scripts/`; they import the code as it was before the fixes (commit 79e2bf5), from a path on the team machine.

**The core of the model checked out.**
- The plant reviewer rebuilt the recommended design (1D-HP-EC@3000-N1-FC) day by day and matched the app within 0.1 %: heat from the exchanger, the heat pump and the boiler, electricity, gas bought and CO₂.
- The other reviewers reproduced the rest independently:
  - the brine heat;
  - the gas from the brine and its CO₂;
  - the 40 K, flow, 330-day and balance caps;
  - the cost of heat line by line;
  - the subsidy (SDE++), tax and investor case.

**What changed for the recommended design.**

| | Before | After |
|---|---|---|
| Design | 1D-HP-EC@3000-N1-FC | the same |
| Cost of heat and cold | 56.66 €/MWh | 58.70 €/MWh |
| Cost of heat | 63.72 €/MWh | 64.72 €/MWh |
| Cost of cold | 23.46 €/MWh | 30.39 €/MWh |
| CO₂ | 9,594 t a year | 9,828 t a year |
| Free cooling | 21.0 GWh | 17.3 GWh |

The rise comes from three fixes:
- the doublet's productivity index (more pump electricity);
- free cooling on real weather hours;
- the cooling towers' pumps and water.

## Findings and what was done

Severity follows the reviewers' scale:
- **high:** a headline number off by more than 2 %, or a hard rule broken;
- **medium:** a real defect with a smaller effect, or one that shows in what-if answers;
- **low:** an edge case, or a statement missing.

### Subsurface and wells

| Id | Severity | Finding | Done | Commit |
|---|---|---|---|---|
| S1 | medium | The GEMINI check compared GEMINI against plant figures that ignored the doublet's aquifer, its wells' open parts and the injectors' share of the flow (an injection pump shown 83 % off). | Each doublet is solved as the year model does. | cbbbf79 |
| S2 | medium | GEMINI's exchanger used its default water (1,050 kg/m³ × 4,200 J/kg/K), so its duty disagreed by 5.5 % on the recommended design. | The brine's density and heat capacity are passed to it. | cbbbf79 |
| S3 | medium | The productivity index used a single well with a 500 m drainage radius (14.5 m³/h/bar). A doublet at steady state gives 2πkh/(μ ln(L/r_w)) = 11.7 m³/h/bar at 1,500 m spacing. | Doublet formula. Pumps use about 19 % more electricity. | cbbbf79 |
| S4 | assumption | All the brine's CO₂ is taken as released at the separator. A flash at 6 bar(a) would free about a third of it, about 365 t a year less. | Kept: it is conservative, and the challenge defines the gas-liquid ratio as gas "potentially liberated". Stated here. | – |
| S5 | low | Very tight rock (below about 0.83 D·m) crashed the search: GEMINI's injection solve finds no root below 500 bar. | It falls back to the closed form, so the subsurface checks flag the design and cap its flow. | cbbbf79 |
| S6 | low | A second aquifer's pressure (and the validation projects') was in bar(a); every other path uses bar(g). | bar(g) throughout. | cbbbf79 |
| S7 | low | The test stub's injection pump started from 5 bar, GEMINI's path from 4 bar. | 4 bar. | cbbbf79 |
| S8 | low | The pressure jumps by 2.6 bar at the edge of the known aquifer: the challenge's 250 bar is below the brine column. | Kept: the challenge gives 250 bar there and hydrostatic elsewhere. | – |

### Surface plant and yearly dispatch

| Id | Severity | Finding | Done | Commit |
|---|---|---|---|---|
| P1 | medium | Equal-share dispatch ranked doublets by their highest cap of the year. During a dated injector outage, brine went unused: 1.7 GWh more boiler, depending only on which injector failed. | Ranked by each day's cap. | cbbbf79 |
| P2 | low | The CO₂ saving and the gas reference shown beside it came from two different references: 60.6 % shown, 59.8 % from the tonnes shown. | One reference with the plant options taken out; see F5. | afb2bdc |
| P3 | low | The heat pump COP had no upper bound as the lift went to zero: 64 in the exchanger-out case, infinite above 100 °C. | Carnot over at least a 10 K lift, so at most 18.7. | cbbbf79 |
| P4 | low | Two outages of the same bank on the same day counted as one unit out. | Not changed: it only matters when a whole-year outage meets a dated one on the same bank. | – |
| P5 | low | Stops could shift to the wrong doublet when one doublet had no days off. | Placed doublet by doublet. | cbbbf79 |
| P6 | medium | Free cooling was optimistic (smoothed weather). | See C1. | 2f29b05 |
| P7 | low | Own solar's self-use is counted on daily energy, ignoring the midday peak: 6–8 % high. | Not changed: affects option variants only. | – |
| P8 | low | The HT-ATES returns its heat at 100 °C with no pumping, and has no O&M. | Not changed: no variant with it is picked; stated here. | – |

### Cooling

| Id | Severity | Finding | Done | Commit |
|---|---|---|---|---|
| C1 | high | Free cooling used a smoothed typical year (monthly normals), whose wet bulb never passes 15.5 °C. Real KNMI De Bilt hours for 2021–2025 give 16.9–17.8 GWh, not 21.0. | Each day's free cooling is now the clipped share averaged over that calendar day's 120 real hours. The data file is `src/dioscuri_plant/data/wet_bulb_de_bilt_2021_2025.csv`, built by `hackathon/scripts/build_wet_bulb.py`. | 2f29b05 |
| C2 | high (cold) | The cooling towers' water was never costed. | Make-up and blow-down are computed from all the heat sent to the towers. A "Water: cooling towers" line is on the cold side, at 1.64 €/m³ (WML 2026 plus the tap-water tax) and 0.40 €/m³ for blow-down (assumed, 0.1–1.0). | 2f29b05 |
| C3 | high (shown) | The cooling check left free cooling out of the towers' load, and the permit pack printed 4,682 m³ of make-up water where about 36,000 m³ is right. | Free cooling's heat is in the check. The permit pack prints the year's figure. | 2f29b05 |
| C4 | medium | Tower electricity had no condenser-water pumps. | 0.5 % of the heat rejected, the cooling model's own figure. | 2f29b05 |
| C5 | medium | The absorption chiller ran at any driving temperature: full cold from a 65 °C well. | Below an 80 °C wellhead it gives no cold, with a warning. | 2f29b05 |
| C6 | low | The cooling check always used a chiller COP of 6, not ours, so the comparison read as a model disagreement. | It runs at our COP. | 2f29b05 |
| C7 | low | The towers take the chillers' 25-year life (ASHRAE's median is about 20), and have no O&M of their own. | Not changed; stated here. | – |

### Economics and finance

| Id | Severity | Finding | Done | Commit |
|---|---|---|---|---|
| F1 | high | "NPV against gas" left out units bought again and the value left at year 30. The gas-free pick showed 9.32 M€ where 6.60 M€ is right. | Both sides go through the investor model's capital flows. | afb2bdc |
| F2 | high | The lead reply's "best overall" rule did not mention the flaring rule that decided the pick. | The rule is stated as the code applies it, and the reply names the plan it set aside. | afb2bdc |
| F3 | medium | The "known aquifer" comparison checked only the first doublet's depth, and named a design with a well at 3,500 m. | Every doublet must be at the known depth, and like is compared with like. | afb2bdc |
| F4 | medium | The Monte Carlo of outages left out the grid contract's 600-hour jump. | Counted for each drawn year. | 912d41e |
| F5 | medium | One design was compared with two different gas references. NPV against gas differed by 15 % depending on the path. | One reference, with the plant options taken out. | afb2bdc |
| F6 | medium | The sensitivity's capital-cost scaling missed the electric boiler, the treatment train, free cooling and storage. | One shared list, checked by a test. | afb2bdc |
| F7 | low | The discount rate's basis was not stated. | "5.2 % real, PBL's after-tax WACC; corporate tax is not in the cost of heat; the investor case adds it." | afb2bdc |
| F8 | low | The investor turned 2025 € into money of the day one or two years late. | Indexed from the 2025 price year. | afb2bdc |
| F9 | low | One electricity price band is used for every design. 8 of 204 designs would fall in a cheaper band. | Not changed: no pick changes. | – |
| F10 | low | The cost-uncertainty draws are independent, and nothing said so. | Said in the output's text. | afb2bdc |
| F11 | suspected | The grid tariff may bill each month's own peak, not the year's. | Not changed: needs Liander's tariff sheet to confirm. | – |

### Reliability, N-1 and the search

| Id | Severity | Finding | Done | Commit |
|---|---|---|---|---|
| R1 | high | The sweep refined the front's points by index, not by position, and dropped the lowest-CO₂ point. Refined, that point beats the old lowest-CO₂ pick on both counts. | Points are chosen by position on the front, and up to 10 are refined (the whole front, for the challenge). | 912d41e, 02ada33 |
| R2 | high | Risk-based sizing drew failures as if a spare ESP were on site, which no design pays for. N-1 was then set as one-off M€ against k€ a year. The recommended design's claimed 0.25 M€ saving disappears without the spare. | Failures are drawn without a spare unless asked. Both plans are priced per year. Units with no failure rate are named. | 912d41e |
| R3 | medium | Risk sizing shrank the small produced-gas boiler, not the electric backup, in designs that buy no gas. | The electric boiler is sized. | 912d41e |
| R4 | medium | Failure what-if remedies grew a bank by the gap, not gap × u/(u−1), and grew a failed single electric boiler. | The bank factor is used, and a standby twin is offered. | 912d41e |
| R5 | medium | "Most reliable" was the cheapest N-1 plan: every N-1 plan ties on every reliability measure. | Shown as "cheapest reliable" (the key is unchanged; a user typing "most reliable" still finds it). | 912d41e |
| R6 | low | The sweep drew each grid's end values half as often as the others. | Whole bins. | 912d41e |
| R7 | low | The Pareto front kept a dominated point on exact cost ties. | Sorted by cost, then CO₂. | 912d41e |
| R8 | suspected | The count of days short (LOLE) undercounts failures shorter than a day. | Not changed: no effect at the shipped sizes. | – |

## Effect on the fine-tuned model

The model learns to read requests into actions and to write replies from the numbers the code gives it. It never computes a number.
- **Corrected numbers:** these fixes change numbers, not the interface, so the training examples stay valid. Each reply was written from the numbers in its own context.
- **The one rename:** "most reliable" became "cheapest reliable". It appears in one training reply. The reading prompts, which list "most reliable" as something a user may type, are unchanged.
