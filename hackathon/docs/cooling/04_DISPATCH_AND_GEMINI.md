# 04. Daily dispatch and GEMINI integration

This is the joint M5 integration reference. Reza's annual plant already exists; it owns
well schedules, heating dispatch, the annual balance and source allocation. M5 is deferred
from the current deadline task. Components/evaluators consume explicit source boundaries
and return inventories now; do not create another annual dispatcher from this sequence.
Read 10 for the hourly cooling calculation inside the eventual daily plant interface.

## Resolved wellhead temperature: consume D001

Reza's explanation supplied on 30 October, updated by his 31 October review, is the
accepted source for this boundary. ProducerWell passes through its input temperature. Reza computes reservoir
temperature outside GEMINI using 12+30*depth_km, then supplies a well-loss correction.
His hydraulics run DPDT isothermal at wellhead_c; its default 20 C ambient is not an
additional brine-cooling calculation in this adapter.

The adapter now returns flow-dependent Ramey wellhead temperature for rock warmed for a
year, plus well_loss_k. At every active per-doublet/day/trial flow, consume its wellhead_c;
well_loss_k is already subtracted and is diagnostic only. Do not subtract another 1 K,
another Ramey loss or the DPDT default thermal loss. At depth d metres, reservoir temperature
is 12+30*d/1000; 87 C applies only at 2,500 m.

Inspect the actual adapter and its docstring constants in M0/joint M5. A test double may
mirror that documented formula; do not fit a new 'Ramey model' from the reference points.
If the adapter source is unavailable, use explicitly labelled fixed boundary test cases
at the supplied flow/temperature points. The cooling numerical core itself never calls
wells; the existing plant supplies those boundaries.

Reported reference estimates at 2,500 m (team-provided, not independently verified here):

| Per-doublet flow m3/h | Loss after a year K | Wellhead C | Maximum clean hot supply with 5 K approach C |
| --- | --- | --- | --- |
| 300 | 0.9 | 86.1 | 81.1 |
| 150 | 1.8 | 85.2 | 80.2 |
| 100 | 2.7 | 84.3 | 79.3 |
| 50 | 5.2 | 81.8 | 76.8 |

Reza also reported first-week losses 1.5 K at 300 and 8.6 K at 50 m3/h, for 2,500 m,
8.5-inch casing, rock conductivity 2.5 W/m/K and the given gradient. Geometry, insulation,
fluid cp and production-age definitions belong in adapter provenance. The quoted diameter
is a team input, not a specified challenge well design. Use different-depth results from
the adapter, not the 2,500 m loss table reused at all depths. Reza reports about 40% larger
losses at 3,000 m; this rounded comparison is a plausibility check, not a replacement
depth-scaling formula or a strict regression target. The reservoir temperature there is 102 C.

One-year warm rock is a base assumption, not an observed startup history. Add cold-start/
thermal-age sensitivity through explicit adapter settings when supported. Do not change
production age during inner convergence iterations, or reset it to zero at each day without
an actual thermal-history model. A test interpolation is a test double, never 'Ramey'.

## Sequence and limits

1. Read the day's heat/cold, weather, return temperatures and equipment/well availability.
2. The plant proposes active doublets and their individual flows. Off means zero flow;
   while on, use 50-300 m3/h at the daily operating point.
3. Call the adapter at each flow. Evaluate source temperature/pressure/pumping and the
   heating allocation. Follow the chosen series/parallel topology and exchanger pinches.
4. Dispatch eligible free cooling, absorption and electric trim under the selected objective.
   Merit order is configurable: absorption-first is a fixture, not always the cheapest rule.
5. Calculate outlet streams, pressure losses and final mixed brine return. Check the shared
   40 K drop and equal injection volume, then evaluate the injection-pump boundary.
6. Update flows, sink temperatures and dispatch until converged, then commit one daily result.
   Do not sum trial powers or repeatedly advance component state inside the iteration.

```text
Q_source_total = sum_i rho_i*Vdot_i*cp_i*(Tprod_i-Tinj_i)
Q_geo_to_heating + Q_generator + other_source_uses + losses <= Q_source_total
0 <= Tprod_i-Tinj_i <= 40 K                  # validate every return path
T_mix = sum(mdot_i*cp_i*Ti)/sum(mdot_i*cp_i)  # constant-cp approximation
```

For parallel branches allocate actual flows. Do not send the complete well flow down each
branch. Return temperature after the whole plant is different from generator hot-water return.
Heating must still reach 100 C through its provider/booster, even when absorption takes the
highest-temperature slice. Do not credit low-temperature condenser heat as 100 C heating.

## Convergence and diagnostics

Configurable starting tolerances: max temperature change 0.05 K, max relative flow change
0.001, daily energy residual <=0.001 with a small absolute tolerance. Check all, including
constraint validity, not just temperature. Set max_iterations=20 initially. One/two iterations
may suffice in Reza's cases, but is not a universal stopping rule. Under-relaxation (initial
alpha 0.5) or a bounded scalar solve may help. Record tolerances, iterations and residuals.
Keep equipment availability/staging decisions consistent within an inner solve; detect
cycling between modes. Failure returns nonconverged status and a dated violation.

## Return-boundary hook remains an integration requirement

The existing two-argument callback is unchanged. Add an optional, explicitly passed return
validator via CoolingContext rather than renaming the callback or using globals. Proposed
inputs: doublet ID, date, liquid flow_m3h, final reinjection_c and pressure at the injection
pump inlet in Pa, plus adapter/context version. Outputs: required injection pressure, pump
MW, hydraulic violations and validation status. Define the exact protocol with the adapter
owner during M0/M5. If absent, cooling screening continues, but hydraulics_validated=False.
Do not use reservoir pressure as pump dp or count an already returned injection-pump MW twice.

## 330 operating days and maintenance

D004 is amended by Reza's 31 October review: 330 is a cap, not a target. Default to at most
330 actual active days per installed doublet, with an explicit configurable mode. Count on
flags, not merely available dates. Do not run an unnecessary summer well to reach 330 days;
off days may exceed 35. Any explicitly requested exact-target experiment is labelled and
is not the challenge baseline. Preserve operating_days as the existing field name.

Prefer an explicit 365-value per-doublet calendar. Preserve stop_start_day; if converting it
to a maintenance outage, document 1-based day-of-year indexing, duration and wrap policy.
An available day is not an instruction to operate, and a 35-day maintenance calendar does
not require operation on every other day. Do not
silently choose a calendar by lowest heating alone: summer cooling also needs the source.
When the calendar is automatic, evaluate combined loads/costs and backup coverage. Document
the selected heuristic. Keep all 365 load records. Electric backup must operate during
geothermal downtime. The year-warmed thermal model does not independently simulate restarts.

## Completion levels

`screening_uncoupled`: known assumptions/stub boundaries, no full-plant claim.
`coupled_stub`: complete coupling/dispatch tests using explicit test providers.
`coupled_gemini`: actual adapter/return checks, with equipment-map and weather quality stated.
These are evidence labels, not certificates. Missing heating or sink/map validation must
remain visible even when a GEMINI hydraulic call succeeds.
