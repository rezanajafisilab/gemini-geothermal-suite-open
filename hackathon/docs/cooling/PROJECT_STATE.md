# Current cooling project state

Last revised: 31 October 2026. Branch: `ali/cooling-components`; draft PR:
https://github.com/rezanajafisilab/dioscuri/pull/1 . Based on verified current main
`5294e1590831474f2ce3352b95fb77d575055915`; M0 checkpoint `119d87d` and implementation checkpoint
`bf753c96f956319a4bb1117cc4badab667b91e41` pushed.

## Current milestone

M0, necessary M1, M2/minimum tower-water and M4 are implemented and tested as screening
components. M6 cooling-direct cost functions/records are delivered; collection of comparable
installed EUR-2025 package/tower prices is **partial**, with missing values preserved. M7
metadata handoff is delivered for the existing Sensitivity tab. Joint M5 annual integration,
optional M3 free cooling and supplier performance maps remain deferred.

## Implemented paths and frozen seam

- `src/gemini_model/cooling_common/`: one pure vector SI kernel, settings and pump/HX/water/tower
  helpers. New electric_chiller, absorption_chiller and cooling_tower StaticModel wrappers.
- `src/dioscuri_plant/cooling/`: typed MW-boundary day/batch evaluation, strict explicit CSV
  loaders, hourly aggregation and failure text. No root annual API/dispatcher/search exists.
- `src/dioscuri_plant/cooling_costs.py`: partial direct EUR-2025 cost inventories with annuity,
  installed/native-basis scope checks, missing-cost status and optional separate leakage CO2e.
- CONTRACT_HANDOFF / PARAMETER_HANDOFF / COOLING_COST_DATA JSON files freeze legacy names,
  actual additive settings paths, existing-app catalogue proposals and source/missing records.
- CI adds plant tests while preserving existing model/simulator/agent discovery.

Use evaluate_cooling_day(request, settings, boundary) / evaluate_cooling_batch(requests,
settings, boundaries, weather). Explicit daily-to-hourly boundary broadcasting is required.
Settings capacities/flows/UA default to zero (uninstalled). Constant COP/envelopes/auxiliary
ratios are declared screening assumptions. Sink/flow/source/return/water/discharge shortfalls
change actual duties and remain diagnosed; unknown water limits stay unchecked.

Rules remains the single brine-cp owner (3990); caller passes it explicitly. Per-flow
wellhead_c is consumed once and well_loss_k retained. Final 330 at-most active days, source
allocation, heating, shared 40 K return/hydraulics and gas/grid ledgers remain Reza's plant
responsibility at joint M5. Cooling factors/prices are not counted again by components.

## Repository evidence and integration limits

Workspace initially contained the instruction/data pack only. An exact shallow main commit/tree
was restored through connected GitHub access with a sparse local models/simulator/test checkout;
unrelated tracked content is retained in the base tree. No nested AGENTS on inspected main.
Main has no annual package/cooling callers/Rules/Prices or cost_sources.md. Read-only inspected
refs: rn/challenge@4c77016, rn/gemini-tools@4891b44, rn/agent-core@d9fc38a,
rn/agent-sandbox@053c774, rn/ui-chat@daa59a6. None exposes the reported annual package/cost path;
this does not establish that Reza's unprovided work is absent. His SensParam types and
params.ts were read on rn/challenge and metadata matches that schema without app changes.

## Actual verification

- Existing baseline: 91 tests passed. Current full local model/simulator/cooling suite:
  **154 passed on Python 3.12.16 and 154 passed on Python 3.11.14** (pinned team dependencies).
- Strict original demand/hourly/daily weather validation and source SHA-256 preservation pass.
  Demands retain 111667.680 / 23742.528 MWh and all 365 days/8760 hourly intervals. Every daily
  statistic/copy/UTC endpoint is checked. Complete synthetic calendar tests also run without raw files.
- Three report_screen_v1 energy/water regressions pass with fixture pump-heat simplification
  explicit. Current 3990-cp and water/annuity/HX/pump hand checks are separate.
- flake8 (jobs=1 on this Windows host), black and isort pass on materialised source/tests.
  Clean raw-free copied checkout: 150 passed, 4 skipped (only original-data/report fixtures).
  Corrected failures are recorded in
  VERIFICATION_EVIDENCE.json; Hosted CI run 41251968252 failed before tests on unchanged main UI
  `src/gemini_interface/blueprint/routes.py:32` D202; 3.12 job cancelled. Main source was
  rechecked read-only; preserve unrelated UI code/lint rules. Reza owns that UI fix.
- Numerical 365-point and (365,24) timing is recorded in PERFORMANCE_EVIDENCE.json, including
  pure adapter timing. No whole-plant/GEMINI timing or coupled validation is claimed.

## Sources, limitations and exact next action

D018-D022 document implemented choices. A006/A007/A013 and declared D018 envelopes remain
screening assumptions. Primary EIA/DOE source-native cost/life/scope records are retained,
but comparable installed EUR-2025 packages/tower cost, economic lives, final tower-2025 escalation/site scope, user
water tariffs/limits and final supplier ratings remain missing. Known cost subtotal is not
full-plant LCOC. No source data, START_HERE, BENCHMARKS or existing GEMINI physics was edited.

Reza reviews the draft component/cost handoff. Next obtain his exact annual integration ref
and installed EUR-2025 quote/normalisation inputs; then Ali and Reza jointly replace cooling
placeholders at M5, preserving all legacy fields and checking per-active-flow wellhead/returns,
heating, 330-cap and central accounting. Do not independently start that integration.


Late source arrival (D022): a local untracked `hackathon/docs/challenge/cost_sources.md`
snapshot became available during final verification. Read fully and preserved unchanged;
SHA-256 `599a1a880149e5fa279074082b81a294fd65c2a6ec42d09a4850a8900031c128`.
The source supplies Eurostat FX/HICP conventions: EIA reference capital/maintenance is now
normalised to EUR-2025; DOE references use the team's assumed 2017 price basis explicitly.
CBS grid year/scope and PBL discount-page metadata are now recorded. EIA column/scope and
Towler-2024-vs-2025 caveats remain in COOLING_COST_DATA. This local file does not locate
Reza's integration branch and was not added to the PR. No runtime defaults were changed.
