# Codex instructions: Dioscuri cooling development

This is the repository entry point for the cooling task. Read [START_HERE.md](START_HERE.md)
first: it is the core team instruction and public-interface contract. This file routes work;
it does not replace START_HERE or higher-priority user instructions. Apply the accepted
31 October review in [REVIEW_AND_CHANGELOG.md](REVIEW_AND_CHANGELOG.md)
and DECISIONS for the specific supersessions listed there. Keep the bundled START_HERE
snapshot unchanged; its older cp, work allocation and operating-day wording are not the
current defaults.

## At the beginning of every run, and after a handoff

1. Read START_HERE.md in full.
2. Read [the cooling index](README.md),
   [PROJECT_STATE](PROJECT_STATE.md) and
   [DECISIONS](DECISIONS.md).
3. Read the scope/requirements and contracts documents in the index. Inspect the actual
   repository, branch, status, applicable nested AGENTS files and existing callers.
4. Use the index's change-routing table to read the relevant model, integration and
   verification sections BEFORE editing code. Links are instructions to read, not proof
   their content has already been loaded.
5. State the current milestone, intended change, preserved interfaces and checks.

## Objective and limits

Build three adjustable options: water-cooled electric compression with optional waterside
free cooling; air-cooled electric compression; and single-effect absorption plus electric
backup. Provide cooling-side energy/material inventories, component costs and emissions
inputs. Reza already has an annual plant model, economics and design search on his branch:
replace its placeholder cooling formulas through agreed hooks, never build another dispatcher.
For the 3–4 November deadline, deliver M0, the necessary M1 foundations, M2, minimum tower
physics/water for M2/M4, M4 and the cooling-cost subset of M6, with hand checks/tests.
Optional free cooling is specified but deferred unless the baseline is complete. Stop before
M5 annual integration; Ali and Reza do that together. M7 supplies parameter/range metadata to
the app's existing Sensitivity tab; do not build a second runner or tab.

Use Python 3.12 for development and preserve the team's Python 3.11 CI compatibility.
Runtime dependencies are standard library, NumPy and SciPy. Keep the agent/UI/well work
with Reza. Keep existing GEMINI fixes in the team's patch layer; do not edit existing model
physics. Use one vectorised numerical cooling path shared with scalar GEMINI wrappers;
benchmark it as specified in 07/08. Runtime functions perform no file/network access and use
no global configuration or commercial-model calls. Codex is a development tool, not a product
dependency. Root AGENTS.md is intended to be committed.

## Before every behaviour change

- Reopen the relevant routed MD sections, current function/call sites and relevant tests.
- Check DECISIONS and SOURCES_AND_ASSUMPTIONS. A screening assumption is not a requirement.
- Preserve START_HERE names, argument compatibility, units and existing result meanings.
  Add fields with safe defaults; do not silently rename/reinterpret fields.
- Keep physical operating constraints fixed in challenge mode. Report shortfalls and
  violations; do not change raw demands or clamp a failed design until it appears feasible.
- Include source, unit, validity range and status for every nontrivial parameter.
- Apply Reza's flow-dependent wellhead temperature on EVERY active doublet/day/trial.
  Read its additional well_loss_k diagnostic; do not subtract it again or use a cached
  300 m3/h temperature for all flows. Reservoir temperature is 12+30*depth_km, not fixed 87 C.
- Active defaults are operating_days=330 as an at-most cap, brine_cp_j_kg_k=3990 in Rules,
  EUR-2025 costs, real discount 0.052, grid CO2 0.20 t/MWh and gas CO2 0.202 t/MWh. See 05/12.
- For weather changes read 10; use the bundled hourly KNMI scenario for calculations and
  daily weather only for screening/checking. For water changes read 11: treated-water
  assumption, cycles, costs and supply limits replace detailed water-chemistry simulation.

## Before ending a meaningful change

Run the relevant verification checks. Update affected specifications and their links when
behaviour changes; log the reason in DECISIONS. Update PROJECT_STATE with actual tests,
remaining limitations and the exact next action. Record failed checks honestly.
Checkpoint before a context handoff; the next run must resume from files, not memory.

Do not mark a full plant valid when heating, source hydraulics, sink conditions or required
maps are unevaluated. A complete cooling screening module may still be delivered with
those integration limits stated. Do not stop independent work solely because a provisional
return temperature, tariff or weather case is awaiting confirmation.

## Code review rules

Flag double-counted heat/electricity/emissions, incorrect Celsius/Kelvin or pressure/flow
conversion, false 100% demand coverage, lost legacy fields, source-temperature reuse across
different flows, absent sink capacity, currency-year mixing and undocumented curve extrapolation.

Keep this router short. The maintained specifications are in hackathon/docs/cooling/.

## Branches and handoff

Use task branches `ali/cooling-<topic>` from current main, push working checkpoints often and
open draft PRs into main. Reza reviews/merges. Read his unmerged branch only to inspect a
contract when needed; do not use rn/* as the task base or copy its annual model into a second
package. If the exact integration branch is unavailable, record the missing ref and proceed
with component tests and explicit boundary inputs. Keep PROJECT_STATE current.
