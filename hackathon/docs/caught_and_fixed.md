# Caught and fixed

Failures the team found in GEMINI, in Dioscuri's model and in the agent, and fixed: 87 in all, 66 guarded by a test. Each says what failed, how it was found, the fix and the tests that guard it. The physics bugs in GEMINI keep their codes F1-F10 (`hackathon/gemini_bughunt/README.md`); the agent's failures from the understanding review are U1 ... (that review calls them F1 ...). 3 GEMINI bugs are not patched but kept out of the designs, said so.

Written from `src/gemini_agent/data/caught_and_fixed.json` (the Evidence tab reads the same file) by `python -m gemini_agent.caught`. Updated 2026-11-04.

| Group | Items | Guarded by a test |
|---|---|---|
| GEMINI's physics code | 15 | 12 |
| Dioscuri's plant and subsurface model | 19 | 16 |
| Costs | 11 | 7 |
| The agent: reading, planning, answers | 37 | 29 |
| The app | 5 | 2 |

## GEMINI's physics code

### F1. Heat exchanger moved heat from cold to hot

- **What failed.** GEMINI's HeatExchanger took the absolute temperature difference and applied it with fixed signs, so heat flowed from cold to hot when the secondary inlet was the hotter stream. Primary 20 °C and secondary 60 °C (150/150 m³/h, UA 250 kW/K) came out at −3.05 °C and 83.05 °C.
- **How it was found.** Bug hunt 27 Oct: repro script 01_heat_exchanger.py (`hackathon/gemini_bughunt/README.md#F1`).
- **Fix.** Patch 01 uses the signed temperature difference for the maximum duty (checked: 20 → 43.05 °C and 60 → 36.95 °C). (patch `01_heat_exchanger_signed_duty.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`

### F2. Heat pump solver returned a spurious root

- **What failed.** HeatpumpBasic minimised a sum of residuals with Nelder-Mead, with no bounds and no check of convergence. In a cascade it gave COP 1.09, 311 °C, 24.8 MW of heat and 22.6 MW of power against the correct COP 6.15, 72.2 °C, 2.52 MW and 0.41 MW, and it divided by zero when Ts_in equalled Th_out_target.
- **How it was found.** Bug hunt 27 Oct: repro scripts 02b_heatpump_grid.py and 13_heatpump_cascade.py (`hackathon/gemini_bughunt/README.md#F2`).
- **Fix.** Patch 04 uses the closed form in Carnot mode and a bracketed root (brentq) for the source-limited and Lorenz cases; errors were 1e-13 on the full grid, with no exceptions. (patch `04_heatpump_bracketed_root.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`; `unit_test/gemini_agent/test_gemini_tools.py::TestChallengeDoublet::test_heat_pump_point_respects_carnot`

### F3. Injection well friction had the wrong sign

- **What failed.** The simulator passed the injector's flow as +Q with direction 'down', so tubing friction was added instead of subtracted: bottomhole pressure 267.09 bar against 263.41 bar. On a challenge design the released code gives 0.007 MW of injection pump power against 0.263 MW (together with the roughness default, F10).
- **How it was found.** Bug hunt 27 Oct: repro script 04_wells.py (`hackathon/gemini_bughunt/README.md#F3`).
- **Fix.** Patch 02 passes the injector's flow as −Q to the pressure-drop model. (patch `02_injection_friction_sign.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`; `unit_test/gemini_agent/test_gemini_tools.py::TestBugImpact::test_released_code_misses_the_injector_pump_and_the_heat_pumps_co2`; `unit_test/dioscuri_plant/test_year.py::TestGeminiDoublet::test_gemini_and_hand_physics_agree_within_one_percent`

### F4. Producer flow solve could return a non-physical root

- **What failed.** GEMINI's nodal solve searches 0.01–700 m³/h on an extrapolated ESP curve and clamps the pump intake at 0 bar. In the repro it had roots at 213.6, 376.8 and 598.5 m³/h and returned 598.6 m³/h with an ESP head of 3312 bar and 3230 % efficiency, with no warning.
- **How it was found.** Bug hunt 27 Oct: repro script 11_nodal_multiple_roots.py (`hackathon/gemini_bughunt/README.md#F4`).
- **Fix.** Not patched. Dioscuri calls GEMINI's flow solve with a bracket of 0.6 to 1.4 times the design flow (src/gemini_agent/tools/gemini.py, next to FLOW_BRACKET_M3H), which keeps the physical root. *Avoided, not patched.* (commit `1badcae`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestChallengeDoublet::test_the_project_view_runs_at_the_design_flow`; `unit_test/gemini_agent/test_confirm.py::TestPanelFixes::test_gemini_loop_agrees_with_the_plant_model`

### F5. ESP affinity law applied without scaling the flow

- **What failed.** The ESP model used (f/60)²·H60(Q) and (f/60)³·P60(Q) instead of evaluating the 60 Hz curves at Q·60/f. Efficiency reached 105.8 % at 40 Hz, and ESP power was off by −20 % at 40 Hz, −15 % at 45 Hz and +8 % at 70 Hz.
- **How it was found.** Bug hunt 27 Oct: repro script 06_esp_affinity.py (`hackathon/gemini_bughunt/README.md#F5`).
- **Fix.** Patch 05 evaluates the 60 Hz curves at Q·60/f; efficiency is then 68.2 % at 40, 50, 60 and 70 Hz on affinity-similar points. (patch `05_esp_affinity_flow_scaling.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`

### F6. Recycle loops were not converged

- **What failed.** GEMINI's solver makes one sequential sweep per time step, with no iteration or residual check. A closed secondary loop (exchanger, 15 K consumer, exchanger) gave 3.383 MW after one run against 2.756 MW converged (+23 %), and nothing said so.
- **How it was found.** Bug hunt 27 Oct: repro script 08_solver.py (`hackathon/gemini_bughunt/README.md#F6`).
- **Fix.** Not patched. Dioscuri's GEMINI brine loop gives the heat network's return temperature to the heat exchanger as a boundary input (src/gemini_agent/tools/gemini.py, plant_project), so it has no recycle loop. *Avoided, not patched.* (commit `1badcae`)
- **Guarded by.** no test guards it

### F7. Compressor power was low by a factor k

- **What failed.** The compressor used n·m·R·T1/(k−1)·(…) instead of n·m·k/(k−1)·R·T1·(…). It gave 355.0 kW against 461.4 kW by hand: −23 % at k = 1.3 and −29 % at k = 1.4.
- **How it was found.** Bug hunt 27 Oct: repro script 07_misc_components.py (`hackathon/gemini_bughunt/README.md#F7`).
- **Fix.** Patch 06 adds the missing factor k; the result matches the hand calculation for 1, 2 and 3 stages. (patch `06_compressor_k_factor.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`

### F8. Borehole heat exchanger stepped twice per solver step

- **What failed.** On GEMINI's geoloop branch the BHE's calculate_output also updated its state and re-ran its whole history. Five solver steps made 10 history entries, and 200 hourly steps took 218 s, so a yearly run was infeasible.
- **How it was found.** Bug hunt 27 Oct: repro script 10_geoloop_bhe.py (`hackathon/gemini_bughunt/README.md#F8`).
- **Fix.** Not patched. The BHE model is on GEMINI's geoloop branch, and no Dioscuri design uses a borehole heat exchanger. *Avoided, not patched.* (no reference)
- **Guarded by.** no test guards it

### F9. Two-phase well pressure drop used the wrong gas velocity

- **What failed.** The two-phase path computed the superficial gas velocity from gmf instead of the gas mass flow, with a constant gas density at standard conditions. With GMF = 1e-4 the wellhead pressure jumped from 4.5 to 26 bar.
- **How it was found.** Bug hunt 27 Oct: repro script 07_misc_components.py (last block) (`hackathon/gemini_bughunt/README.md#F9`).
- **Fix.** Patch 07 uses the gas mass flow for the superficial gas velocity; the gas PVT is still constant, and Dioscuri's well configs leave GMF at its default of 0. (patch `07_dpdt_two_phase_usg_and_roughness_unit_comment.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`

### F10. Default well roughness was 10 mm, documented as mm

- **What failed.** The well-flow default roughness was 0.01 m (10 mm), while the code comment and docs say the unit is mm. Friction was 4.3–5.4 times that of steel at 4.5e-5 m, and the example doublet ran at 129 m³/h instead of 203 m³/h.
- **How it was found.** Bug hunt 27 Oct: repro script 04_wells.py (blocks C, D and D2) (`hackathon/gemini_bughunt/README.md#F10`).
- **Fix.** Patch 03 sets the default roughness to 4.5e-5 m (0.045 mm, steel), and patch 07 corrects the unit comment. (patch `03_roughness_default_4p5e-5m.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`; `unit_test/dioscuri_plant/test_year.py::TestGeminiDoublet::test_gemini_and_hand_physics_agree_within_one_percent`

### G08. Heat pump reported no CO2 (patch 08)

- **What failed.** HeatpumpBasic reported zero CO2 because its electricity was not counted. For the challenge design 1D-HP-EC@3000 the released code gives 0 kg/h of heat pump CO2 against 86 kg/h.
- **How it was found.** Running Dioscuri's designs on GEMINI's solver, 29 Oct (`hackathon/gemini_bughunt/BUG_IMPACT.md`).
- **Fix.** Patch 08 counts the CO2 of the heat pump's electricity, with an optional electricity_emission_factor. (patch `08_heatpump_electricity_emission.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`; `unit_test/gemini_agent/test_gemini_tools.py::TestBugImpact::test_released_code_misses_the_injector_pump_and_the_heat_pumps_co2`

### G09. Simulator registry had no heat pump (patch 09)

- **What failed.** GEMINI's component registry had no heat pump, so a simulator project could not use one.
- **How it was found.** Running Dioscuri's designs on GEMINI's solver, 29 Oct (`hackathon/gemini_bughunt/README.md`).
- **Fix.** Patch 09 registers HeatpumpBasic as 'heatpump'. (patch `09_register_heatpump.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`; `unit_test/gemini_agent/test_workbench.py::TestWorkbench::test_gemini_catalogue_and_run`

### G10. Heat pump Carnot COP taken at the source inlet (patch 10)

- **What failed.** The Carnot COP used the source's inlet temperature. With brine cooled from 53 to 30 °C, that gave a COP above the physical Carnot limit.
- **How it was found.** Running Dioscuri's designs on GEMINI's solver, 29 Oct (`hackathon/gemini_bughunt/README.md`).
- **Fix.** Patch 10 (applied after 04) takes the Carnot COP at the source outlet, where the evaporator runs, and both modes solve the source balance. (patch `10_heatpump_carnot_source_outlet.diff`, commit `9d28750`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`; `unit_test/gemini_agent/test_gemini_tools.py::TestChallengeDoublet::test_heat_pump_point_respects_carnot`

### G11. Well model used water, not the brine (patch 11)

- **What failed.** The well model's fluid was water at standard conditions, hard-coded in _build_dpdt, not the challenge brine (1,030 kg/m³, 0.40 mPa·s). With the 10 mm roughness (F10) the released code gives an ESP head of 41.7 bar at 300 m³/h against 31.1 bar (+34 %).
- **How it was found.** Building the challenge doublet on GEMINI's well model, 30 Oct (`hackathon/gemini_bughunt/README.md`).
- **Fix.** Patch 11 lets a well config pass the fluid (RHOL, VISL, CPL), and Dioscuri passes the brine; without it, behaviour is unchanged. (patch `11_well_brine_properties.diff`, commit `1896edd`)
- **Guarded by.** `unit_test/gemini_agent/test_gemini_tools.py::TestRuntime::test_every_patch_applies_and_both_versions_load`; `unit_test/gemini_agent/test_gemini_tools.py::TestChallengeDoublet::test_pumps_rise_with_flow_and_the_well_cools_the_brine_more_at_low_flow`; `unit_test/dioscuri_plant/test_year.py::TestGeminiDoublet::test_gemini_and_hand_physics_agree_within_one_percent`

### A-S1. The GEMINI check compared GEMINI with the wrong plant figures

- **What failed.** The check's plant side ignored the doublet's aquifer, its wells' open parts and the injectors' share of the flow (an injection pump shown 83 % off), and GEMINI's exchanger ran on its default water (duty 5.5 % off on the pick).
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#subsurface-and-wells`).
- **Fix.** Each doublet solved as the year model does; GEMINI's exchanger given the brine's density and heat capacity. (commit `cbbbf79`)
- **Guarded by.** no test guards it


## Dioscuri's plant and subsurface model

### R1-01. A hard cap relaxed by asking still showed as passed

- **What failed.** Asked to run 365 days, the design accepted it, and the 330-day check renamed itself 'At most 365 days per doublet' and passed.
- **How it was found.** Review panel 31 Oct (red team) (`hackathon/reviews/2026-10-31-panel/red_team.md`).
- **Fix.** A relaxed cap is still checked against the challenge's 330 days, and the check and the inputs card say what was asked. (commit `17084bb`)
- **Guarded by.** `unit_test/gemini_agent/test_confirm.py::TestPanelFixes::test_a_relaxed_cap_is_still_checked_against_the_challenge`

### R1-02. Dioscuri's GEMINI brine loop went below vacuum

- **What failed.** The brine loop Dioscuri drew as a GEMINI project went to negative pressure after the filters (−1.62 and −2.24 bar; −5.9 bar at the injection pump suction with a shared train), and the run still reported ok.
- **How it was found.** Review panel 31 Oct (judge, production engineer) (`hackathon/reviews/2026-10-31-panel/production_engineer.md#3.1`).
- **Fix.** The treatment train is sized for a 1 bar drop at its flow and the duty ESP runs at 70 %, so GEMINI's pumps equal the plant model's (0.391 MW ESP, 0.221 MW injection at 300 m³/h); a run warns on any pressure below 1 bar. (commit `17084bb`)
- **Guarded by.** `unit_test/gemini_agent/test_confirm.py::TestPanelFixes::test_gemini_loop_agrees_with_the_plant_model`

### D01. GEMINI's example ESP had negative head at the design flow

- **What failed.** GEMINI's example ESP is sized for about 150 m³/h and gave a negative head at the design's 300 m³/h, so the GEMINI tab's ESP power (24 kW) was meaningless.
- **How it was found.** The user's review of 31 Oct (`hackathon/docs/decisions/ADR-0010-doublets-inputs-whatifs.md#Context`).
- **Fix.** The GEMINI view scales the same pump family to each producer's duty (the design flow at 60 % of run-out, stages for the head needed at 55 Hz). (commit `1badcae`, ADR-0010)
- **Guarded by.** `unit_test/gemini_agent/test_confirm.py::TestPanelFixes::test_gemini_loop_agrees_with_the_plant_model`

### R1-15. One unit out was never checked

- **What failed.** No design was checked with one unit out: with either doublet out the design was 7.17 MW short on 70 days, and the outage answer said the town stays warm.
- **How it was found.** Review panel 31 Oct (operator, geothermal specialist, district energy engineer) (`hackathon/reviews/2026-10-31-panel/build_page.py#FIXED`).
- **Fix.** Every design gets each one-unit-out case and the peak-day spare (dioscuri_plant.firm), and the answer model gets them as conclusions. (commit `97cb3a5`)
- **Guarded by.** `unit_test/dioscuri_plant/test_firm.py::TestFirm::test_each_unit_once`; `unit_test/dioscuri_plant/test_firm.py::TestFirm::test_a_lost_doublet_leaves_winter_short`; `unit_test/dioscuri_plant/test_firm.py::TestFirm::test_peak_spare`

### D02. No design was sized for a lost unit

- **What failed.** No design covered a lost unit: one doublet's ESP out left 7.2 MW short on 28 Jan.
- **How it was found.** Review panel 31 Oct (`hackathon/docs/decisions/ADR-0011-picks-failures-plans.md#Context`).
- **Fix.** Reliable plans (code -N1) grow the boiler and chillers, as three equal units, until every one-unit-out case meets every day; for the pick this adds 2.0 M€ and 1.6 €/MWh. (commit `5190d6a`, ADR-0011)
- **Guarded by.** `unit_test/dioscuri_plant/test_firm.py::TestFailures::test_reliable_plan_holds`

### D03. No subsurface checks

- **What failed.** Designs passed with no check of thermal breakthrough, gas at the ESP or injection pressure.
- **How it was found.** Review panel 31 Oct (`hackathon/docs/decisions/ADR-0011-picks-failures-plans.md#Context`).
- **Fix.** dioscuri_plant.subsurface checks Gringarten-Sauty breakthrough, the ESP setting depth above the bubble point (about 43 bar) and SodM's 0.135 bar/m, and caps a doublet's flow where a limit breaks. (commit `5190d6a`, ADR-0011)
- **Guarded by.** `unit_test/dioscuri_plant/test_firm.py::TestSubsurface::test_challenge_doublet_passes`; `unit_test/dioscuri_plant/test_firm.py::TestSubsurface::test_tight_reservoir_fails_then_search_caps_the_flow`

### R2-09. The repair loop grew a heat pump that could not help

- **What failed.** The repair loop kept growing a unit that did not close the gap: it grew a heat pump from 0.7 to 64 MW.
- **How it was found.** Review panel 1 Nov (judge) (`hackathon/reviews/2026-11-01-panel/build_page.py#FIXED`).
- **Fix.** The loop stops when growing a unit does not close the gap, and says why. (commit `111a320`)
- **Guarded by.** no test guards it

### SC4. Gas-free plans had no treatment train per doublet (E4 in science.md)

- **What failed.** The gas-free stage sized only a shared treatment train, so 'the train out' forced a 30 MW electric boiler (92.7 €/MWh); with the gas boiler ruled out, reliable plans grew the heat pump to 195.6 MW for cases it cannot cover.
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E4`).
- **Fix.** Gas-free plans are also sized with a train per doublet (pick 86.4 €/MWh, electric boiler 16.6 MW), and a reliable plan takes back a growth that does not close its gap. (commit `0939a54`, ADR-0013)
- **Guarded by.** `unit_test/gemini_agent/test_model_review.py::TestGasFreeTrains::test_a_train_each_needs_a_smaller_electric_boiler`; `unit_test/gemini_agent/test_model_review.py::TestGasFreeTrains::test_no_heat_pump_grown_for_nothing`; `unit_test/dioscuri_plant/test_firm.py::TestFailures::test_a_unit_that_cannot_close_the_gap_is_not_grown`

### SC14. Service windows fell inside a doublet's stop (E14 in science.md)

- **What failed.** With yearly service on, the cheapest design's single boiler was serviced from 29 Jul, inside the doublet's stop (9 Jul–12 Aug), leaving 7 days short (2.67 MW).
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E14`).
- **Fix.** The doublets' stops are placed first, and no heating unit is serviced while a doublet stands. (commit `0939a54`, ADR-0013)
- **Guarded by.** `unit_test/dioscuri_plant/test_network_service.py::TestService::test_no_heating_service_while_a_doublet_stands`; `unit_test/dioscuri_plant/test_network_service.py::TestService::test_the_year_places_service_around_the_stops`

### D04. Brine flow was cut by the 40 K cap after planning

- **What failed.** When the network warms by more than the brine may cool (a 50 °C return heated to 100 °C, 40 K cap), the brine flow was planned 'balanced' and then cut by the cap: 6 GWh a year went to the boiler at 3,500 m.
- **How it was found.** Found while building ADR-0015's changes ('a model bug found on the way') (`hackathon/docs/decisions/ADR-0015-provenance-sweep-outages.md`).
- **Fix.** The flow is planned for the cap (dioscuri_plant/year.py). (commit `0ca195a`, ADR-0015)
- **Guarded by.** no test guards it

### A-S3. The wells' productivity index ignored the doublet

- **What failed.** The index used a single well with a 500 m drainage radius (14.5 m3/h/bar); a producer and an injector 1,500 m apart give 2 pi k h / (mu ln(L / r_w)) = 11.7 m3/h/bar, so the pumps' electricity was about 19 % low.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#subsurface-and-wells`).
- **Fix.** The doublet's steady-state formula with the well spacing; the pick's cost of heat and cold rose by 1.5 %. (commit `cbbbf79`)
- **Guarded by.** `unit_test/dioscuri_plant/test_audit_fixes.py::TestDoubletIndex::test_hand_value`

### A-S5. Very tight rock crashed the search

- **What failed.** Below about 0.83 D·m GEMINI's injection solve found no root under 500 bar and the search raised an error.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#subsurface-and-wells`).
- **Fix.** The closed form GEMINI agrees with elsewhere, so the subsurface checks flag the design and cap its flow. (commit `cbbbf79`)
- **Guarded by.** no test guards it

### A-P1. An injector out on some days left brine unused

- **What failed.** Equal shares ranked the doublets by their year's largest cap, so a doublet whose injector was out could be filled last: 1.7 GWh more boiler depending only on which injector failed.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#surface-plant-and-yearly-dispatch`).
- **Fix.** The shares are filled day by day from that day's smallest cap. (commit `cbbbf79`)
- **Guarded by.** `unit_test/dioscuri_plant/test_audit_fixes.py::TestDispatchByDay::test_injector_out_is_symmetric`

### A-P3. The heat pump's COP had no upper bound

- **What failed.** With the source as hot as the supply (the exchanger out, brine straight from the well) the COP was 64 over a year, infinite above 100 °C.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#surface-plant-and-yearly-dispatch`).
- **Fix.** Carnot over at least a 10 K lift (at most 18.7 at 100 °C). (commit `cbbbf79`)
- **Guarded by.** `unit_test/dioscuri_plant/test_audit_fixes.py::TestHeatPumpLift::test_finite_at_no_lift`

### A-C1. Free cooling on a smoothed weather year

- **What failed.** Free cooling used monthly normals spread over the days (wet bulb never above 15.5 °C): 21.0 GWh, where De Bilt's real hours of 2021-2025 give 16.9-17.8 GWh.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#cooling`).
- **Fix.** Each day's free cooling is the clipped share averaged over that calendar day's 120 real hours (KNMI hourly data in the repository); the pick's cost of cold rose from 23.5 to 30.4 €/MWh. (commit `2f29b05`)
- **Guarded by.** `unit_test/dioscuri_plant/test_cooling_water.py::TestFreeShare::test_hand_calculation`; `unit_test/dioscuri_plant/test_cooling_water.py::TestFreeShare::test_challenge_pick`

### A-C5. The absorption chiller ran on any brine

- **What failed.** Absorption cold was credited at COP 0.75 from a 65 °C well, below the 80 °C its hot-water loop needs.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#cooling`).
- **Fix.** Below an 80 °C wellhead it gives no cold, and a warning says why. (commit `2f29b05`)
- **Guarded by.** `unit_test/dioscuri_plant/test_cooling_water.py::TestAbsorptionDrive::test_too_cold_gives_nothing`

### A-R1. The sweep dropped its lowest-CO2 design

- **What failed.** The front's points were picked by index, not position, before cutting to 6: the lowest-CO2 point was never refined, though refined it beats the 'lowest CO2' pick on cost and CO2.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#reliability-n-1-and-the-search`).
- **Fix.** Points chosen by position on the front, both ends kept, up to 10 refined. (commit `912d41e`)
- **Guarded by.** `unit_test/dioscuri_plant/test_sweep.py::TestFront::test_spread_keeps_both_ends`

### A-R2. Risk sizing assumed a spare ESP no design pays for

- **What failed.** The days-short draws took a spare ESP on site (7 days out, not 120), and N-1 was set as one-off M€ against k€ a year: the pick's '0.25 M€ saved' disappears without the spare.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#reliability-n-1-and-the-search`).
- **Fix.** Drawn as built (a spare only when asked); both plans priced a year; units with no failure rate named. (commit `912d41e`)
- **Guarded by.** `unit_test/dioscuri_plant/test_montecarlo.py::TestDraw::test_as_built_no_spare`; `unit_test/gemini_agent/test_views.py::TestViews::test_risk_view_prices_both_plans_a_year`

### A-R4. Failure remedies grew a bank by too little

- **What failed.** With a unit of a 3-unit boiler bank among the failures, '10 MW more boiler' left 3.3 MW short (the bank needs gap x 3/2); a failed single electric boiler was itself grown.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#reliability-n-1-and-the-search`).
- **Fix.** The bank factor u/(u-1); a standby twin for a single electric boiler. (commit `912d41e`)
- **Guarded by.** `unit_test/dioscuri_plant/test_firm.py::TestBankRemedies::test_doublet_and_a_boiler_unit_out`; `unit_test/dioscuri_plant/test_firm.py::TestBankRemedies::test_failed_electric_boiler_gets_a_twin`


## Costs

### D05. Cost basis 20–35 % below PBL

- **What failed.** Geothermal capital and O&M sat 20–35 % below PBL 2026, although the code said they matched PBL.
- **How it was found.** Review panel 31 Oct (economist) (`hackathon/docs/decisions/ADR-0011-picks-failures-plans.md#Context`).
- **Fix.** Costs use the ThermoGIS v3 surface plant (3.5 M€ + 882 €/kW) with the v3 wells and PBL's fixed O&M (121 €/kW/yr); the cheapest design becomes one doublet. (commit `5190d6a`, ADR-0011)
- **Guarded by.** no test guards it

### R1-09. 'Lowest CO2' bought 24 t a year with 21 M€

- **What failed.** The lowest-CO2 pick bought its last 24 t of CO2 a year with 21 M€ of extra wells.
- **How it was found.** Review panel 31 Oct (municipal planner, economist) (`hackathon/reviews/2026-10-31-panel/municipal_planner.md`).
- **Fix.** 'Lowest CO2' takes the cheapest design within 2 % of the lowest CO2. (commit `17084bb`)
- **Guarded by.** no test guards it

### R2-08. Best-overall rule inverted at high carbon prices

- **What failed.** The best-overall pick weighs CO2 at PBL's long-term 137 €/t, so with a user carbon price above 137 €/t it weighed CO2 less than the user's own price.
- **How it was found.** Review panel 1 Nov (economist, judge) (`hackathon/reviews/2026-11-01-panel/build_page.py#FIXED`).
- **Fix.** CO2 never weighs less than the user's own carbon price; reliable plans are built for the best layout of each doublet count. (commit `111a320`)
- **Guarded by.** no test guards it

### SC3. Best overall was not best by its own measure (E3 in science.md)

- **What failed.** The reliable plan was built only on the sizing cheapest at today's carbon price. The pick (2.0 MW heat pump, 14,103 t, 76.37 weighted) lost to the same layout with 3.3 MW (12,967 t, 75.87 weighted) for +0.03 €/MWh.
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E3`).
- **Fix.** Each layout's reliable plan is also built on its sizing cheapest with CO2 at 137 €/t, and picks are kept by design, not by code. (commit `0939a54`, ADR-0013)
- **Guarded by.** `unit_test/gemini_agent/test_model_review.py::TestBestOverallSizing::test_the_best_is_a_bigger_heat_pump`; `unit_test/gemini_agent/test_model_review.py::TestBestOverallSizing::test_best_by_its_own_measure`

### SC5. Failures ignored the 600-hour grid contract (E5 in science.md)

- **What failed.** An ESP outage (5 Jan–4 May) ran the electric boiler 849 h, past the 600-hour contract, but the failure card said 2.05 M€; the grid charge rises from 0.74 to 3.73 M€ and the event costs 5.04 M€.
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E5`).
- **Fix.** Failure cards and yearly failure costs add the change of grid charge when an outage passes 600 hours; the treatment train, with no published failure rate, is said not counted. (commit `0939a54`, ADR-0013)
- **Guarded by.** `unit_test/gemini_agent/test_model_review.py::TestFailureGrid::test_the_event_breaks_the_contract`; `unit_test/gemini_agent/test_model_review.py::TestFailureGrid::test_the_yearly_cost_counts_it`; `unit_test/dioscuri_plant/test_failure_costs.py::TestGridContract::test_counted_in_the_expected_cost`

### SC6. SDE++ paid on the heat pump's electricity (E6 in science.md)

- **What failed.** SDE++ counted the heat pump's whole output, its electricity included (eligible 56.7 against 53.3 GWh of brine heat), and the 'with heat pump' categories used the brine capacity instead of the heat pump's (6.94 M€ in year 1).
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E6`).
- **Fix.** Base-load categories pay only geothermal heat (SDE++ 3.35 → 3.15 M€ in year 1), and in the heat-pump categories the heat pump is the installation (6.94 → 1.47 M€). (commit `0939a54`, ADR-0013)
- **Guarded by.** `unit_test/dioscuri_plant/test_investor.py::TestHeatPumpHeat::test_base_load_pays_the_brine_heat_not_the_heat_pumps_electricity`; `unit_test/dioscuri_plant/test_investor.py::TestHeatPumpHeat::test_with_heat_pump_the_heat_pump_is_the_installation`; `unit_test/gemini_agent/test_model_review.py::TestInvestorHeat::test_the_heat_pumps_electricity_earns_nothing`

### SC13. Monte Carlo was not centred on the case (E13 in science.md)

- **What failed.** The uncertainty draws were uniform over ranges not centred on the case, so the median cost (74.4 €/MWh) sat above the base (69.8 €/MWh).
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E13`).
- **Fix.** Each input is drawn triangular with its mode at the design's own value, and the answer says the base's percentile (median 72.4 €/MWh, base at P33). (commit `0939a54`, ADR-0013)
- **Guarded by.** `unit_test/gemini_agent/test_model_review.py::TestCentredUncertainty::test_draws_centre_on_the_case_and_say_where_it_sits`

### D06. The recommended design flared the brine's gas

- **What failed.** The recommended design flared 4.1 GWh of the brine's gas a year.
- **How it was found.** Plan of 3 Nov (C10) (`hackathon/docs/decisions/ADR-0017-chat-needs-options-risk.md#Context`).
- **Fix.** A plan that flares more than 1 GWh a year gives way, as best overall, to one that flares less within 3 % of its measure. (commit `7c43f07`, ADR-0017)
- **Guarded by.** no test guards it

### A-C2. The cooling towers' water was never costed

- **What failed.** No water price, no water line, and the permit pack printed 4,682 m3 of make-up water where about 36,000 m3 is right (free cooling's heat left out).
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#cooling`).
- **Fix.** Make-up and blow-down from all the heat the towers reject, priced on the cold side (WML 2026 tariff and tap-water tax; blow-down assumed); the check and the permit pack print the same figure. (commit `2f29b05`)
- **Guarded by.** `unit_test/dioscuri_plant/test_cooling_water.py::TestTowers::test_pick_by_hand`; `unit_test/gemini_agent/test_cooling_check.py::TestTowersAndCop::test_free_cooling_in_the_towers`

### A-F1. NPV against gas left out re-buys and the value left

- **What failed.** Units with 20- or 25-year lives were never bought again: the gas-free pick showed 9.32 M€ where 6.60 M€ is right.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#economics-and-finance`).
- **Fix.** Both sides go through the investor model's capital flows (re-buys, value left at year 30). (commit `afb2bdc`)
- **Guarded by.** `unit_test/gemini_agent/test_money_against_gas.py::TestNpvAgainstGas::test_by_hand`

### A-F5. One design, two gas references

- **What failed.** Options' CO2 saving used the plain reference, the money views a reference with the option's free cooling: '60.6 % less' beside tonnes that gave 59.8 %, NPV against gas 15 % apart.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#economics-and-finance`).
- **Fix.** One reference with the plant options taken out, for every comparison. (commit `afb2bdc`)
- **Guarded by.** `unit_test/gemini_agent/test_money_against_gas.py::TestOneGasReference::test_options_meet_the_plain_reference`


## The agent: reading, planning, answers

### R1-03. Money answers were written by the model

- **What failed.** The chat made up the gas reference and once said gas was cheaper than the design.
- **How it was found.** Review panel 31 Oct (economist, municipal planner) (`hackathon/reviews/2026-10-31-panel/build_page.py#MEMBERS`).
- **Fix.** The gas reference, yearly totals, extra capital, payback, NPV, prices and what the costs leave out are computed by code and given to the answer model. (commit `17084bb`)
- **Guarded by.** `unit_test/gemini_agent/test_confirm.py::TestPanelFixes::test_money_facts_for_the_answerer`

### R1-07. Other units and number words were dropped

- **What failed.** Values in other units (ct/kWh, l/s, TWh, °F) and German or Dutch number words were not read, and an out-of-range ask was not said to be refused.
- **How it was found.** Review panel 31 Oct (ML and LLM expert, red team) (`hackathon/reviews/2026-10-31-panel/build_page.py#FIXED`).
- **Fix.** Code converts these units and reads the number words; an ask out of range is said in the reply as 'Not applied'. (commit `17084bb`)
- **Guarded by.** `unit_test/gemini_agent/test_confirm.py::TestPanelFixes::test_units_people_use_are_read`

### R1-08. An injected value in an attachment reached the reply

- **What failed.** A datasheet (rated COP 2.2) carried a hidden instruction to report COP 12. The reply flagged it, yet also said 'you must use a COP of 12'.
- **How it was found.** Review panel 31 Oct (red team) (`hackathon/reviews/2026-10-31-panel/red_team.md`).
- **Fix.** Text in a file addressed to the assistant (hidden comments, 'AI note', 'you must report') is left out before the model reads it. (commit `17084bb`)
- **Guarded by.** `unit_test/gemini_agent/test_agent.py::TestDocuments::test_hidden_instruction_in_an_attachment_is_ignored`

### R1-16. The chat could not see the design's days

- **What failed.** The chat could not see the daily schedule, so a question about 19 July was answered wrong.
- **How it was found.** Review panel 31 Oct (operator) (`hackathon/reviews/2026-10-31-panel/build_page.py#FIXED`).
- **Fix.** The peak days, any day or month named, stops as dates and ESP starts per doublet reach the answers; 19 July is now answered right. (commit `97cb3a5`)
- **Guarded by.** `unit_test/gemini_agent/test_answer.py::TestOperations::test_named_days`; `unit_test/gemini_agent/test_answer.py::TestOperations::test_operations_block`

### R1-18. A sentence about injected brine changed the reservoir

- **What failed.** 'The injected brine is 30-40 K colder' was read as a what-if that made the reservoir 35 K colder.
- **How it was found.** Review panel 31 Oct (reservoir simulation expert) (`hackathon/reviews/2026-10-31-panel/build_page.py#FIXED`).
- **Fix.** Reservoir what-ifs are read only from sentences about the reservoir. (commit `2516a34`)
- **Guarded by.** no test guards it

### R2-01. Dates in other languages and short forms misread

- **What failed.** '19/7' became 28 Jan and 'jan 28th' became 28–31 Jan; 'the coldest week' ran as 1–7 Jan instead of 25–31 Jan.
- **How it was found.** Review panel 1 Nov (judge, district client, operator) (`hackathon/reviews/2026-11-01-panel/judge.md`).
- **Fix.** Dates and durations are read in Dutch, German and French and as 19/7 or 10/01-24/01, and 'the coldest week' takes the worst start (ties go to the most demand). (commit `111a320`)
- **Guarded by.** `unit_test/gemini_agent/test_planner.py::TestPlanReading::test_dates_in_other_languages`; `unit_test/gemini_agent/test_planner.py::TestPlanReading::test_a_duration_in_a_named_month_is_a_window`

### R2-02. Planned maintenance took the worst window

- **What failed.** Planned maintenance was put in the worst window of the year.
- **How it was found.** Review panel 1 Nov (operator) (`hackathon/reviews/2026-11-01-panel/build_page.py#FIXED`).
- **Fix.** Planned work ('take the heat pump out for 10 days') takes the mildest window (1–10 Aug). (commit `111a320`)
- **Guarded by.** `unit_test/gemini_agent/test_planner.py::TestPlanReading::test_planned_maintenance_flag`

### R2-04. Failure replies contradicted their cards

- **What failed.** In 9 of 15 failure replies the model's text contradicted the card that code wrote.
- **How it was found.** Review panel 1 Nov (operator) (`hackathon/reviews/2026-11-01-panel/build_page.py#FIXED`).
- **Fix.** Failure replies are shown as code wrote them; negative running costs say the heat went undelivered. (commit `111a320`)
- **Guarded by.** no test guards it

### R2-05. Words read as the wrong parameter

- **What failed.** 'From 10 to 24 January' became a 10/24 °C cooling network, '20 % more heat demand' lowered the coverage check to 20 %, 'doublet 1' set one doublet and 'COP 12' became a 12 MW heat pump.
- **How it was found.** Review panel 1 Nov (agentic AI expert, district client) (`hackathon/reviews/2026-11-01-panel/build_page.py#FIXED`).
- **Fix.** Code checks these readings: dates are days, a doublet's name is not a count, a COP is not a size, and a described doublet's depth must be in the message. (commit `111a320`)
- **Guarded by.** `unit_test/gemini_agent/test_planner.py::TestPlanReading::test_doublet_name_is_not_a_count`

### U1. A reply said yes when the data said no (F1 in understanding.md)

- **What failed.** Asked whether the cheapest design meets a 50 % CO2 cut, the reply began 'yes' although it cuts 41.2 %; the claim check removed the true sentence 'This falls short of the required 50%'.
- **How it was found.** Understanding challenge 1 Nov, turn 19 (`hackathon/reviews/2026-11-01-challenge/understanding.md#F1`).
- **Fix.** A CO2 floor ('at least 50 % less') runs as a search against the design named and says first whether it meets it (now: 41.2 %, short; the cheapest at 50 % is 2D-HP-AB, 71.4 €/MWh). (commit `f91061f`, ADR-0014)
- **Guarded by.** `unit_test/gemini_agent/test_premises.py::CO2Floor::test_objective_co2_with_a_percentage_becomes_a_floor`; `unit_test/gemini_agent/test_premises.py::CO2Floor::test_lowest_co2_stays_an_objective`

### U2. A reply claimed an action that never ran (F2 in understanding.md)

- **What failed.** After a long brief the reply said 'I have updated the heating network return temperature to 55 °C … I am now sizing a reliable plan', but nothing ran and the return stayed 60 °C.
- **How it was found.** Understanding challenge 1 Nov, turns 45–47 (`hackathon/reviews/2026-11-01-challenge/understanding.md#F2`).
- **Fix.** A check removes actions claimed that never ran, and a long brief is never taken for a file request. (commit `0939a54`, ADR-0014)
- **Guarded by.** no test guards it

### U3. The small reader turned down fair questions (F3 in understanding.md)

- **What failed.** qwen3:1.7b marked 8 on-topic messages unrelated; 'why did you recommend that one and not the one you call best overall?' was declined and replaced by about 600 words on the wells.
- **How it was found.** Understanding challenge 1 Nov, turns 5, 8 and 12 (`hackathon/reviews/2026-11-01-challenge/understanding.md#F3`).
- **Fix.** Fair questions are never declined once a design exists. (commit `0939a54`)
- **Guarded by.** no test guards it

### U4. The model's working was shown as the answer (F4 in understanding.md)

- **What failed.** Two replies were the model's own working ('Wait, let me re-read carefully…'), cut off mid-sentence, and never answered the question.
- **How it was found.** Understanding challenge 1 Nov, turns 13 and 22 (`hackathon/reviews/2026-11-01-challenge/understanding.md#F4`).
- **Fix.** A check removes the model's own working and sentences about 'the text' or 'the context'. (commit `0939a54`, ADR-0014)
- **Guarded by.** no test guards it

### U5. Switches and stop dates could not be set in words (F5 in understanding.md)

- **What failed.** 'Switch on the district network heat losses and a yearly service stop' was refused as 'Not applied', and 'could we move the stop to August?' could not run.
- **How it was found.** Understanding challenge 1 Nov, turns 24 and 39 (`hackathon/reviews/2026-11-01-challenge/understanding.md#F5`).
- **Fix.** Switches are read in words, a missing network length is asked for, and stop dates are a what-if (doublet_stops) whose days code reads from the words. (commit `f91061f`, ADR-0014)
- **Guarded by.** `unit_test/gemini_agent/test_premises.py::StopDates::test_month_keeps_the_stop_length`; `unit_test/gemini_agent/test_premises.py::StopDates::test_one_doublet_on_given_days`; `unit_test/gemini_agent/test_premises.py::StopDates::test_planner_change_is_checked_and_applied`

### GR1. Costs given under the wrong names (H1 in grounding.md)

- **What failed.** A reply called the 30.6 M€ capital the yearly cost (9.45 M€), the cost of heat (75.7) the cost of heat and cold, the cost of cold (42.1) the cost of heat, and invented a budget cap.
- **How it was found.** Grounding audit 1 Nov, turn g1-25 (`hackathon/reviews/2026-11-01-challenge/grounding.md#H1`).
- **Fix.** A final label check shows the code's draft when a cost or reliability claim is still wrong, and the yearly cost by part is a fact the reply can use. (commit `0939a54`, ADR-0014)
- **Guarded by.** `unit_test/gemini_agent/test_answer.py::TestCostLabels::test_heat_plus_cold_is_no_cost`; `unit_test/gemini_agent/test_answer.py::TestCostLabels::test_right_labels_pass`; `unit_test/gemini_agent/test_premises.py::LongFacts::test_cost_split`

### GR2. False premises answered 'Yes, that is correct' (H2 in grounding.md)

- **What failed.** 'The cost of heat is 69.8 €/MWh and the boiler gives about a quarter, correct?' got 'Yes'; the cost of heat is 75.7 €/MWh (69.8 is heat and cold) and the boiler gives 49.2 %.
- **How it was found.** Grounding audit 1 Nov, turn g1-38 (`hackathon/reviews/2026-11-01-challenge/grounding.md#H2`).
- **Fix.** Code checks what the message takes as given and leads with a correction ('Not quite. The cost of heat is 75.7 €/MWh; 69.8 €/MWh is the cost of heat and cold together.'). (commit `f91061f`, ADR-0014)
- **Guarded by.** `unit_test/gemini_agent/test_premises.py::PremiseChecks::test_cost_of_heat_and_cold_given_as_cost_of_heat`; `unit_test/gemini_agent/test_premises.py::PremiseChecks::test_doublet_count_and_co2`; `unit_test/gemini_agent/test_premises.py::PremiseChecks::test_a_right_premise_is_not_corrected`

### GR6. Modelled options said to be not modelled (H6 in grounding.md)

- **What failed.** Asked to switch on network heat losses and yearly service, the reply said losses are not modelled, though both exist behind switches.
- **How it was found.** Grounding audit 1 Nov, turn g1-32 (`hackathon/reviews/2026-11-01-challenge/grounding.md#H6`).
- **Fix.** When a tool ran, a sentence saying it cannot be computed or modelled is removed, and the context lists options switched off apart from what is not modelled. (commit `f91061f`, ADR-0014)
- **Guarded by.** `unit_test/gemini_agent/test_premises.py::Refusals::test_refusal_only_reply_falls_back`

### GR10. A what-if kept its N-1 name after losing N-1 (H10 in grounding.md)

- **What failed.** A what-if with the reservoir 5 K colder kept '(N-1)' in its name and reliable = true, while 1 of its 5 one-unit-out cases was short (1.69 MW on 28 Jan).
- **How it was found.** Grounding audit 1 Nov, turn g1-39 (`hackathon/reviews/2026-11-01-challenge/grounding.md#H10`).
- **Fix.** A what-if keeps N-1 only if its own one-unit-out cases hold. (commit `0939a54`)
- **Guarded by.** no test guards it

### SC1. Gas share stated about 100 times too low (E1 in science.md)

- **What failed.** The reply said the gas boiler gives about 0.5 GWh (3 %) of the heat; it gives 54.99 GWh, 49.2 %.
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E1`).
- **Fix.** The values a question asks for (heat by source in GWh, CO2 by source, gas flows) are looked up by code and given as facts. (commit `0939a54`, ADR-0014)
- **Guarded by.** `unit_test/gemini_agent/test_premises.py::LongFacts::test_heading_and_any_number`; `unit_test/gemini_agent/test_premises.py::LongFacts::test_cost_share_and_heat_and_cold_patterns`

### SC2. N-1 blamed for the gas share (E2 in science.md)

- **What failed.** Why-answers blamed N-1 for the gas share and the heat pump size, but the design without N-1 burns the same 54.99 GWh; the split is set by the exchanger's limit and the heat pump sweep.
- **How it was found.** Science challenge 1 Nov (`hackathon/reviews/2026-11-01-challenge/science.md#E2`).
- **Fix.** A code-written note gives the heat split's reason: the exchanger's limit, the peak, and the heat pump sizes tried with their costs. (commit `0939a54`, ADR-0014)
- **Guarded by.** no test guards it

### D07. A request for the full report was refused

- **What failed.** 'Please do the design work and give me the full report' was refused: the small reader flagged it as skipping the checks, and a word list confirmed it because it says 'report'.
- **How it was found.** The user's conversation of 30 Oct (`hackathon/docs/decisions/ADR-0009-reading-requests.md#Context`).
- **Fix.** The reader's flags are suspicions that a larger model must confirm, and the word list is gone. (commit `8bccc69`, ADR-0009)
- **Guarded by.** `unit_test/gemini_agent/test_understanding.py::TestRefusals::test_a_report_request_flagged_by_the_reader_still_runs`

### D08. A what-if on the heating return was not run

- **What failed.** 'What happens if we lower the heating return to 50 °C?' was answered from the documents; only a reservoir temperature change could be re-run.
- **How it was found.** The user's review of 31 Oct (`hackathon/docs/decisions/ADR-0010-doublets-inputs-whatifs.md#Context`).
- **Fix.** What-ifs run on any input in the parameter catalogue: the same plant under the change, then a new search. (commit `1badcae`, ADR-0010)
- **Guarded by.** `unit_test/gemini_agent/test_confirm.py::TestWhatIf::test_a_lower_heating_return_is_run`

### D09. A calculation in a reply did not add up

- **What failed.** A reply worked out '86.1 °C − 40 K = 52.1 °C'.
- **How it was found.** Chat questions about where numbers come from, 2 Nov (`hackathon/docs/decisions/ADR-0015-provenance-sweep-outages.md#Context`).
- **Fix.** A calculation written in a reply is checked (answer.wrong_sums): if wrong, the model is asked again; if still wrong, the line goes. (commit `0ca195a`, ADR-0015)
- **Guarded by.** `unit_test/gemini_agent/test_provenance.py::TestReplyChecks::test_wrong_sums`

### D10. The reading's JSON was cut short

- **What failed.** Read inside the long parameters reading, three new fields came back wrong for most messages and the JSON was cut short.
- **How it was found.** Work on the 3 Nov plan (A1–A3) (`hackathon/docs/decisions/ADR-0017-chat-needs-options-risk.md#Context`).
- **Fix.** What a reply needs is its own short model call (needs_v1): 14 of 14 test messages read right, 0.2 s each. (commit `4aa7dca`, ADR-0017)
- **Guarded by.** `unit_test/gemini_agent/test_which_design.py::TestReading::test_needs`; `unit_test/gemini_agent/test_which_design.py::TestReading::test_read_needs_from_a_model`

### E1. Design codes read as numbers in outage replies

- **What failed.** Replies about a unit out quoted designs such as 1D-HP-EC@3000-N1-FC; the number check took the 3000 for a figure no source gives and removed the sentence, and a remedy's boiler size was never registered as sourced.
- **How it was found.** The final eval run of 4 Nov on the merged code (cases S51, S52, S59) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** Design codes are skipped by the number check, and the outage text registers every figure it states. (commit `47ddff6`)
- **Guarded by.** `unit_test/gemini_agent/test_model_review.py::TestFailureNumbersSourced::test_cheapest_boiler_out_three_weeks`

### E2. An attached file was said to be missing

- **What failed.** "Summarise the attached datasheet and size an absorption chiller" got "no file was provided": the request went down the not-modelled path, which never searched the attachment.
- **How it was found.** The final eval run of 4 Nov on the merged code (case S12) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** A message about the attached file searches it on that path too; the reply summarises the file and flags the instruction hidden in it. (commit `47ddff6`)
- **Guarded by.** no test guards it

### E3. The chat could no longer add or change an aquifer

- **What failed.** The merge of 4 Nov kept the new reading prompt, written before aquifers could be edited in words, so their instructions were lost.
- **How it was found.** Probing the merged code, 4 Nov (`src/gemini_agent/prompts/parameters_v3.txt`).
- **Fix.** The aquifer instructions are back in the prompt in use, and a test reads that prompt for them. (commit `d27dd63`)
- **Guarded by.** `unit_test/gemini_agent/test_aquifers.py::TestTheChat::test_the_prompt_in_use_says_how`

### E4. "Not quite" for a premise with no figure

- **What failed.** "Why didn't you pick the cheapest?" and "you drilled deeper than the aquifer" were answered "Not quite." with a figure about something else.
- **How it was found.** The final eval run of 4 Nov on the merged code (case T04) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** Code leads with a correction only when the premise states a figure. (commit `6fec710`)
- **Guarded by.** `unit_test/gemini_agent/test_premises.py::PremiseChecks::test_a_premise_without_a_figure_is_not_led`

### E5. The search was invisible to most questions

- **What failed.** "What did the search go through to get here?" got "I have only run one design": the search summary went into the answer only when the question used certain words.
- **How it was found.** The final eval run of 4 Nov on the merged code (case N02) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** Once a search ran, every answer is told how wide it was and its picks, a line each. (commit `a061234`)
- **Guarded by.** `unit_test/gemini_agent/test_thread.py::TestSearchInEveryAnswer::test_question_without_design_words_gets_the_search`

### E6. Another design's figure said of the one asked about

- **What failed.** "What about the cheapest one, how much CO2 does it save?" got 60.6 %, the recommended design's figure; the cheapest saves 64 %.
- **How it was found.** The final eval run of 4 Nov on the merged code (case T02) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** A sentence that gives another design's value without naming that design is sent back once, then removed; a value the claim check removed is added back from the checked draft. (commit `64f6b70`)
- **Guarded by.** `unit_test/gemini_agent/test_answer.py::TestChecks::test_another_designs_figure_is_asked_again_then_dropped`; `unit_test/gemini_agent/test_answer.py::TestChecks::test_add_back_takes_the_drafts_sentence_for_a_lost_value`

### E7. "How does it compare with the most reliable one?" compared nothing

- **What failed.** One design was named and "it" (the current one) implied; the comparison was dropped, and the reply called the cheapest the most reliable.
- **How it was found.** The final eval run of 4 Nov on the merged code (case T03) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** One other existing design and nothing new to run: it is set against the current design. (commit `64f6b70`)
- **Guarded by.** `unit_test/gemini_agent/test_planner.py::TestCompareWithTheCurrent::test_one_other_design_is_compared_with_the_current`

### E8. The pick's choices went missing

- **What failed.** Since plant options came in, the pick is an option of a reliable plan (1D-HP-EC@3000-N1-FC); its layout was looked up by the wrong parent, so "why not two injectors?" and "why not the cheapest?" had no figures to answer from.
- **How it was found.** The final eval run of 4 Nov on the merged code (cases T04, S50) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** A design's parents are followed to its layout; each variant is set against its own layout. (commit `92c4e7d`)
- **Guarded by.** `unit_test/gemini_agent/test_answer.py::TestDecisionsBlock::test_a_reliable_pick_with_a_plant_option_has_its_choices`; `unit_test/gemini_agent/test_answer.py::TestDecisionsBlock::test_the_search_lists_the_variants_of_the_picks_layout`

### E9. True sentences removed as unsupported

- **What failed.** "Run A assumed a 60 °C return" and "the best overall choice is A1 at 56.7 €/MWh" were removed: run A's value was in no source, and a long cited block left the checker no room for the designs.
- **How it was found.** The final eval run of 4 Nov on the merged code (cases M04, T04) (`hackathon/evals/runs/20261104T045511Z_qwen3-1.7b_auto.jsonl`).
- **Fix.** The runs block gives run A's values too; the claim check reads twice the sources in a 16k window. (commit `94bb2fb`)
- **Guarded by.** `unit_test/gemini_agent/test_answer.py::TestRunsBlock::test_run_a_values_are_given_with_the_change`; `unit_test/gemini_agent/test_answer.py::TestClaimsBudget::test_a_16k_window_reads_twice_an_8k_one`

### E10. "Which designs did the search pick?" answered with heat pump sizes

- **What failed.** A long context cut the search summary to its first lines, which held no pick.
- **How it was found.** The final eval run of 4 Nov on the merged code (long conversation C3, turn 1) (`hackathon/evals/runs/conversations_20261104T054811Z_qwen3.5-9b_auto_final.jsonl`).
- **Fix.** The summary opens with a short line per pick, and a cut keeps them all. (commit `b5ba787`)
- **Guarded by.** `unit_test/gemini_agent/test_answer.py::TestDecisionsBlock::test_a_cut_search_block_keeps_every_pick`

### E11. A unit's share of the heat corrected against the plant's coverage

- **What failed.** "You told me the gas boiler covers about 21 % of the heat?" got "Not quite. ... covered is 100 %".
- **How it was found.** The final eval run of 4 Nov on the merged code (long conversation C2, turn 12) (`hackathon/evals/runs/conversations_20261104T054811Z_qwen3.5-9b_auto_final.jsonl`).
- **Fix.** A premise about a unit's share of the heat is paired with the heat split, which the model judges. (commit `b5ba787`)
- **Guarded by.** `unit_test/gemini_agent/test_premises.py::PremiseChecks::test_a_units_share_of_the_heat_is_not_the_coverage`

### A-F2. The best-overall rule in the reply left out the flaring rule

- **What failed.** The lead reply said best overall is the cheapest with CO2 at 137 €/t, while the cheaper A2 was set aside for flaring 4.1 GWh a year, unsaid.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#economics-and-finance`).
- **Fix.** The rule is said as the code applies it, and the reply names the plan set aside and its flaring. (commit `afb2bdc`)
- **Guarded by.** `unit_test/gemini_agent/test_money_against_gas.py::TestOneGasReference::test_reply_states_the_flaring_rule`

### A-R5. 'Most reliable' was the cheapest N-1 plan

- **What failed.** Every N-1 plan ties on every reliability measure the code computes, so the label claimed more than it knew.
- **How it was found.** Calculation audit 4 Nov (five independent reviewers, before fine-tuning) (`hackathon/docs/calculation_audit/README.md#reliability-n-1-and-the-search`).
- **Fix.** Shown as 'cheapest reliable' (a user saying 'most reliable' still finds it). (commit `912d41e`)
- **Guarded by.** `unit_test/gemini_agent/test_views.py::TestViews::test_cheapest_reliable`


## The app

### R1-06. A later search replaced the first pick

- **What failed.** Design ids were not unique across searches, so a follow-up search overwrote the recommended design.
- **How it was found.** Review panel 31 Oct (judge, municipal planner) (`hackathon/reviews/2026-10-31-panel/hackathon_judge.md#3.6`).
- **Fix.** Design ids are unique per search, and what-ifs name the design they were asked about. (commit `17084bb`)
- **Guarded by.** `unit_test/gemini_agent/test_confirm.py::TestPanelFixes::test_a_later_search_keeps_the_first_pick`

### R1-13. Two chats at once mixed their steps

- **What failed.** With two chats running at once, the server mixed their steps and replies.
- **How it was found.** Found while preparing the 31 Oct panel (`hackathon/reviews/2026-10-31-panel/build_page.py#FIXED`).
- **Fix.** The server runs one chat at a time. (commit `ed20963`)
- **Guarded by.** no test guards it

### R2-11. A what-if's gas price leaked into the tabs

- **What failed.** A what-if's gas price (30 €/MWh) leaked into the Economics tab, so every design was compared with that gas plant; the design picker showed no names.
- **How it was found.** Review panel 1 Nov (UI and UX designer) (`hackathon/reviews/2026-11-01-panel/ui_ux.md#3.1`).
- **Fix.** The tabs measure every design against the base case's gas reference; edited designs keep their own name (U1) and lose the N-1 flag; the design picker shows the names. (commit `111a320`)
- **Guarded by.** no test guards it

### D11. The requirements PDF read one word per line

- **What failed.** The requirements PDF was not searchable, and its preview showed one word per line.
- **How it was found.** The user's conversation of 30 Oct (`hackathon/docs/decisions/ADR-0009-reading-requests.md#Context`).
- **Fix.** Word-exported PDFs are read in layout mode, as lines and tables. (commit `8bccc69`, ADR-0009)
- **Guarded by.** `unit_test/gemini_agent/test_understanding.py::TestContext::test_a_word_per_line_pdf_is_read_in_lines`

### D12. A design with no cost broke the design-space map

- **What failed.** The Compare tab's design-space map failed with a server error: a drawn design that delivers no heat has a NaN cost, and JSON has no NaN.
- **How it was found.** A teammate's use of the Compare map, 3 Nov (`src/gemini_agent/server.py`).
- **Fix.** Such a design counts as broken ('no cost per MWh'), its numbers are null, and every server response and stream event sends NaN as null. (commit `b9be350`)
- **Guarded by.** no test guards it
