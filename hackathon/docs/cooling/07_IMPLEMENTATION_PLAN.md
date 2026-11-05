# 07. Milestones and completion gates

Use ali/cooling-<topic> task branches from current main. Push working checkpoints often
and open draft PRs into main; Reza reviews/merges. Do not build tasks on an unmerged idea or
rn/* branch. Root AGENTS.md is fine to commit. Each milestone must leave runnable,
reviewable work; maintain PROJECT_STATE at milestone/change boundaries.

The 3–4 November deadline scope is M0, necessary M1 foundations, M2, minimum tower/water
accounting supporting M2/M4, M4, and cooling costs from M6, with hand checks/tests. M3 free
cooling/maps are optional after the baseline. Stop before M5; annual integration is joint
work with Reza. M7 is a parameter/range handoff to the existing app, not a new runner.

## M0. Inspect and freeze the working contract

Read initial documents, inspect active AGENTS and actual branch/callers. Verify source hashes
and the demand/hourly/daily weather CSVs. Find current Plant/Rules/Prices/YearResult
definitions and placeholder chiller/absorption formulas. Reza confirms that simulate_year,
economics and design search already exist on his branch, even if not yet on main. Locate
that ref and hackathon/docs/challenge/cost_sources.md; inspect them read-only for interfaces
when available. Never create a replacement annual package because main lacks the branch's
code. Do not use rn/* as a task base. If the exact branch/file is unavailable, record this
fact and continue component/evaluator work with explicit test boundaries.
Specify/test additive cooling settings, return-check hook and heating-provider seam; record
their exact names in 02 and DECISIONS. Confirm cp=3990 in Rules, at-most-330 semantics,
well_loss_k, chill/free meanings, chillers/towers/pumps inventory ownership and EUR-2025
conventions. Do not rename existing public fields. Reuse actual provider interfaces when
present; when absent, document the proposed seam and use explicit test providers. Additive routine choices
do not need a permission round trip. Missing final providers do not block the components.
Gate: inventory/contract plan and truthful PROJECT_STATE, no renamed legacy fields.

## M1. Common types, data and physics

Implement only the foundations needed by M2/M4/M6: small contracts/settings, strict
input-layer CSV ingestion, conversions, required pump/HX helpers and diagnostics. Load
weather outside numerical evaluation; pass arrays rather than reopening files in a run.
Reusable physics must not import the challenge plant. Add independent hand checks, input validation, off/limited cases and demand totals. Gate: data/physics checks.

## M2. Water and air electric models

Implement a shared electric calculation with separate condenser configurations. Include
capacity limits, actual outlet temperature and explicit COP boundary. Constant-COP fixtures
first, with explicitly declared temperature/load envelopes and auxiliaries. Include the
minimum tower rejection, capacity/temperature and simple water model from 11 for the wet
option. Supplier maps are deferred unless already available and needed. Gate: component/API
and energy/shortfall tests, no hidden fan/pump double counting, shared scalar/vector kernel.

## M3. Optional free cooling and tower refinement

Minimum tower duty/temperature/water/power belongs to the deadline M2/M4 dependencies.
Detailed tower refinement and free-HX/trim control are optional after that baseline. Keep
free_cooling_enabled=False until full/partial/unavailable mode tests pass. When implemented,
use hourly KNMI wet bulb, finite exchanger/tower/flow capacity, water limits and full-backup
sizing. Gate: water conservation, cold-service sum and diagnostics independent of GEMINI.
Do not promise free-cooling savings when this optional feature is not implemented.

## M4. Absorption and backup

Implement separate hot/chilled/rejection circuits, thermal COP/capacity limits, HX grade,
external pumps and electric fallback. Use constant COP/capacity inside a stated envelope
for the deadline. Consume allocated hot-side boundaries rather than implementing heating
or well schedules. Gate: source/sink/return constraints, three-circuit energy balances and
scalar/batch parity; zero source heat uses backup or explicitly reports unmet cooling.

## M5. Joint annual integration — deferred

Ali and Reza replace the placeholder formulas inside Reza's existing simulate_year,
economics and design-search path. No second dispatcher is created. Handoff the pure scalar
and vector cooling functions, inventory ownership, cost records and tests first; this task
stops before changing annual integration. During the joint stage, consume the current
per-flow/depth Ramey adapter and return validator, preserve heating allocations and test
365 demand days with at most 330 active days per well. Integrate the towers/free additions
and central cost allocation once. Gate: coupled-stub then actual-adapter checks, with
missing heating/return/map evidence retained visibly. Do not fabricate full-system results.

## M6. Costs and emissions

Deliver the cooling subset now: installed-capex data/functions, fixed/variable O&M,
lifetimes, water/service costs, auxiliary inventories and optional refrigerant data in
EUR-2025, with sources/price years and r=0.052. Follow 12. Apply plant factors once centrally;
provide shared-cost allocation inputs without a full-plant heat price. Do not rewrite the
annual Economics function before joint M5. Keep the old USD ledger as a regression test
only. Gate: sourced-vs-assumed/missing status, cost-item reconciliation, scope/tower flags
and no double counts. Direct-only cooling cost is labelled partial until M5 allocation.

## M7. Existing-app parameter handoff and final review

Send Reza the parameter names, actual Rules/Prices or proposed additive binding paths,
units, defaults, ranges and restrictions in 06. His Sensitivity tab already executes the
runs; do not build another runner/tab/optimizer. USD sweeps remain fixture tests only.
Final deadline gates are the applicable component/cost/data tests in 08 and current
PROJECT_STATE. Joint M5 and optional M3/map work remain explicitly deferred.

## Performance and runtime dependency gate

Reza evaluates about 30 candidates across several rounds and 500-sample sensitivities;
his NumPy annual plant is about 10 ms. Supply a vectorised cooling path over 365 days,
including (365,24) hourly weather where used. If a scalar per-day path is used instead,
its cooling evaluation must stay below 20 microseconds per day on the recorded reference
machine. Prefer vectorisation over relying on this scalar limit.

Profile representative wet/air/absorption cases, record environment, batch size and median
timing, and compare scalar/batch inventories. Exclude file loading, plotting, diagnostics
string formatting and GEMINI well solves from the cooling-kernel measurement; also report
end-to-end timing separately when joint M5 is available. No module-level mutable state,
global runtime settings or implicit cross-candidate caches. No cooling/runtime calls to
commercial AI services: Codex is for development. Reza's existing local agent is outside
this coding scope and must not be redesigned as part of the cooling task.

## Proposed layout (adapt to existing code, do not duplicate it)

```text
src/gemini_model/cooling_common/{physics,units}.py
src/gemini_model/electric_chiller/electric_chiller.py
src/gemini_model/cooling_tower/cooling_tower.py
src/gemini_model/free_cooling/free_cooling.py   # optional M3 after the baseline
src/gemini_model/absorption_chiller/absorption_chiller.py
src/dioscuri_plant/cooling/{contracts,config,evaluate,batch}.py
src/dioscuri_plant/cooling_costs.py
# Existing annual dispatch/economics/search/sensitivity code stays with its current owner.
# Use existing paths/hooks where present; this layout is not a second plant package.
unit_test/gemini_model/<new_component>/
unit_test/dioscuri_plant/
```

Prefer focused functions with equations/units in numpydoc docstrings over a giant simulator
class. Keep orchestration separate from equipment physics. Add .rst pages if offering
components upstream. Add the plant test path to .github/workflows/team-ci.yaml as required.
Do not claim a JSON registry integration until registered components and connections are
tested; direct Python calls are sufficient for initial agent integration.
