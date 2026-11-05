# 06. Sensitivity without changing the question

Use the app's existing Sensitivity tab and runner, which already vary Rules/Prices. Do not
implement a second runner, optimizer, tab or USD scenario engine for the deadline. Deliver
parameter names, binding paths, units, base values, ranges, source status and constraints
to Reza. Confirm actual field names during M0 rather than silently renaming them. The
existing runner builds fresh configurations without modifying raw data/shared Rules. Save
scenario ID, option, settings/hash, model/source versions, parameter changes, validation
level, violations, coverage, costs, emissions, electricity, source heat, water and peak flows.

## Sequence

This is the existing app's eventual comparison sequence. The current task supplies bindings,
ranges and unit/parameter checks; it does not require deferred joint-M5 sweeps to be complete.

1. Reproduce the named report fixture for all three options.
2. One-at-a-time low/base/high tests, keeping other inputs fixed.
3. Paired combined scenarios: every alternative gets the same demand, weather, grid factors,
   tariffs and common assumptions; technology-specific maps remain physically consistent.
4. Sizing/dispatch sweeps with source/sink feasibility checks. Keep backup reliability policy
   identical when comparing equipment sizes.
5. Optional Latin hypercube/Monte Carlo only after bounds/distributions and correlations are
   documented. Use NumPy/SciPy with a recorded seed. These are scenario distributions unless
   evidence supports probabilistic interpretations.

## Initial exploratory ranges

| Parameter | Values | Qualification |
| --- | --- | --- |
| Cooling return C | 23,25,28 | Supply 20 unchanged |
| Heating return C | 50,60,70 | Requires heating coupling/provider |
| Brine cp J/kg/K | 3,990 fixed baseline | Single Rules value/source; not a default sweep |
| Water / air compressor COP | 4-8 / 3-6 | Constant-COP scenarios inside a stated envelope; maps only when sourced |
| Thermal COP | 0.55,0.70,0.75 | Check driving/sink envelope |
| Absorption capacity MW | 0,2,4,6 | 4 is not assumed optimal; reject infeasible sizes |
| Heat-exchanger approach K | 3,5,8 | Recalculate hot grade, UA and flows |
| Electricity EUR-2025/MWh | 0.5/1/2 x sourced or user base | Missing base is not zero; no full-plant heat-price sweep |
| Capital multiplier / real discount | 0.7,1,1.3 / 0.03,0.052,0.08 | EUR-2025, same installed scope; baseline r=5.2% |
| Water supply/treatment/disposal EUR-2025/m3 | 0.5/1/2 x each user base | Separate bases; honour any bundled scope |
| Concentration cycles | 3,5,6 | 5 provisional; effective treatment does not verify feasibility |
| Maximum makeup m3/h | None; 0; 0.5/1/1.5 x base peak need | None unchecked; zero is a real no-supply case |
| Tower approach / free-HX approach K | 2,3,5 / 1,2,3 | Screening settings, finite capacity still required |
| Grid CO2 t/MWh | 0.10,0.20,0.40 | Base 0.20 from plant; do not relabel as lifecycle CO2e |
| Weather input / mode | De Bilt 2025 hourly; daily_screening; other verified cases | Daily mode is a fidelity check, not a second weather year |
| Source thermal history | Year-warmed / supported startup cases | Adapter controlled, D001 |
| Downtime | Staggered/common and seasonal alternatives | Keep 365 loads and actual operating-day counts |
| Free cooling | Off; hourly weather-driven when M3 is implemented/tested | Hypothetical share cases remain historical fixture tests only |

Do not vary hard challenge caps inside a purported compliant baseline. An out-of-challenge
stress case needs an explicit label and is not a candidate winner. Do not independently
sample dry bulb, wet bulb and incompatible humidity, or COP and capacity independent of
the weather driving their maps. Do not alter the resolved source method back to flat 1 K.

## Ranking and plots

Filter by required service and validation level before ranking. Do not reward cheap unmet
demand. Report LCOC, plant CO2 and water separately; report CO2e with its available factor
coverage, never by relabelling CO2-only factors. An explicit user-selected objective or
documented carbon price can create a combined score; arbitrary weights cannot.
The existing app/report layer can provide OAT, two-parameter break-even and cost/emissions
Pareto plots, labelled CO2 or CO2e as appropriate, after the needed integration. Do not implement a second
plotting/sensitivity product as a deadline dependency. Ranking frequency in assumed samples
is scenario frequency, not a real-world probability of winning. Retain failed scenarios as diagnostics rather than discarding them.

The existing app/CLI owns scenario execution, exports and plots. Optional report plotting
stays outside the NumPy/SciPy numerical core. Retain the unchanged USD/UK report sweeps as
regression tests only, not user-facing production scenarios.

Deliver one parameter-handoff record per adjustable input: parameter_id, actual binding
path, component/option applicability, unit, base or missing status, low/high or categories,
source/price year, hard vs exploratory bound, coupled-input restrictions and affected outputs.
For new CoolingSettings fields, provide an additive binding proposal for Reza's Rules/Prices
tab adapter; do not create a parallel sensitivity configuration. A 500-sample run must use
the existing runner and shared vectorised cooling kernel. Its probabilistic interpretation
requires justified distributions/correlations; scenario ranges alone are not probabilities.

## Actual app-schema inspection and delivered metadata

Read-only rn/challenge@4c77016f1dd584a1ba01ac9d24b75247c7890a7a inspection of
frontend/src/tabs/sensitivity/params.ts and frontend/src/workbench/types.ts confirms
SensParam uses key,label,unit,group,low,high,kind,description. PARAMETER_HANDOFF.json includes
51 records with actual additive settings paths, units, domains/defaults and source status,
plus proposed numeric catalogue rows in that shape. Categories and missing-price bases stay
metadata; current UI numeric ranges must have low<high. Server mapping of new keys is Reza's
joint-M5 work. Existing runtime Rules/Prices bindings are not independently verified because
the annual package ref remains unavailable. No frontend, runner, sampler or optimiser changed.
