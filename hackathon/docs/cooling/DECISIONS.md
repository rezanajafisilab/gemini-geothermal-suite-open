# Cooling decisions and clarifications

Keep stable IDs. 'Accepted' here means part of this requested implementation specification,
not organiser approval or proof of a physical model. Add amendments with source/rationale;
do not erase superseded decisions without a trace.

| ID | State | Decision and source |
| --- | --- | --- |
| D001 | Resolved; updated 31 Oct review | Adapter now returns per-flow/depth wellhead_c and diagnostic well_loss_k for year-warmed Ramey loss. Use temperature once, never subtract the loss again. Add the 100 m3/h reference and depth-dependent loss; actual docstring governs test doubles. See 04. |
| D002 | Amended deadline scope | Three cooling configurations, pure evaluator and cooling costs. M0/necessary M1/M2/minimum tower/M4/M6 subset now; M5 is joint with Reza and deferred. Optional M3 free cooling/maps later; M7 hands parameters to the existing app. START_HERE remains core with this dated amendment. |
| D003 | Provisional boundary | 20 C means supplied cooling water, return 25 C; heating return 60 C. Adjustable team assumptions, not organiser definitions. |
| D004 | Amended, accepted team clarification 31 Oct | At most 330 actual active days per doublet, configurable mode default at_most; retain all 365 demand days. No unnecessary operation to reach a target. Supersedes the former exact-330 default. See 04. |
| D005 | Contract refinement | Keep chill as mechanical electric cooling; add free explicitly and adapt legacy presentation if needed. This avoids silently changing START_HERE semantics. Refines the report's optional aggregation suggestion. Additive fields are allowed; verify caller/UI sums. |
| D006 | Accepted accounting; current conventions in D015 | Physical inventories first, prices/factors once centrally; CO2 separate from CO2e. Production uses EUR-2025; USD/UK figures remain historical regression fixtures only. |
| D007 | Accepted validation policy | Report fixture, stub coupling and actual GEMINI coupling are separate evidence levels. Missing heating/return checks/maps never become full validation by default. |
| D008 | Accepted source ownership | Reza's adapter supplies wellhead temperature and hydraulics; component models consume hot/sink boundaries. Return-validator protocol remains to be inspected/finalised additively. |
| D009 | Amended thermal input 31 Oct | Single Rules.brine_cp_j_kg_k=3990 J/kg/K, team-selected constant attributed to Sharqawy, Lienhard & Zubair (2010). Replaces 3950 in active defaults. HX approach 5 K and auxiliary proxies remain provisional; legacy report fixtures are unchanged. |
| D010 | Accepted instruction workflow | Root AGENTS routes startup; explicit reread-before-change, state and decision records maintain continuity. MD is not an automatic file watcher. |

## Accepted additions, 31 October 2026

| ID | State | Decision and source |
| --- | --- | --- |
| D011 | Accepted ownership clarification | Reza's annual simulate_year/economics/design search already exist on his branch. Replace cooling placeholders through agreed hooks at joint M5; do not create another dispatcher/search. Actual branch/ref must be recorded in M0. |
| D012 | Accepted speed/runtime requirement | Shared vectorised 365-day/hourly numerical path, or scalar cooling day under 20 microseconds on the recorded machine. Pure functions, no runtime file/network/global configuration or commercial-model calls. Codex is development-only. |
| D013 | Accepted weather scenario | Use unchanged hourly De Bilt 2025 weather mapped onto 2027 for calculations; daily summary for screening/checking. Calendar compatibility is not actual 2027 weather or proof of exact demand-weather correlation. See 10. |
| D014 | Accepted simplification | Effective treatment assumed; omit detailed water chemistry. Use six user inputs, cycles, water balance and supply/discharge limits. Unknown limits/prices are not unlimited/zero. See 11. |
| D015 | Accepted economic convention | EUR-2025; 5.2% real discount; central plant grid CO2 0.20 t/MWh (CBS), gas 0.202 (IPCC). DEA 2020→2025 x1.168, Eurostat FX, CEPCI for Towler & Sinnott per actual cost_sources.md when available. See 05/12. |
| D016 | Accepted plant accounting convention | No full-plant absorption heat price. Split shared geothermal costs by brine heat used; produced gas burns in boiler first, remainder flared, native 20% CO2 counted once. Existing plant owns dispatch/ledgers. |
| D017 | Accepted workflow | ali/cooling-<topic> branches from main, frequent pushes, draft PRs into main, Reza reviews/merges. AGENTS.md may be committed. Keep PROJECT_STATE current; do not base work on rn/*. |

## Superseded values retained only for traceability

The original D004 exact-330 interpretation and D009 cp=3950 assumption are replaced above.
The bundled START_HERE/report and BENCHMARKS remain unchanged source snapshots, so those
older values still appear there. They do not override the accepted review. Do not reopen
the resolved wellhead-temperature source, 330-cap meaning or chosen cp as missing definitions.

## Open items (do not reopen D001/D004/D009)

- Return temperatures and physical cooling boundary; whether geothermal-driven cold is required.
- Maintenance calendar and required downtime service coverage within the accepted 330 cap.
- Actual site and replacement weather scenarios; user water costs/limits; installed capacities
  and applicable supplier ratings. The bundled hourly scenario is already available.
- Exact integration branch/ref, current placeholder hooks, return validator and existing app bindings.
- Actual cost_sources.md version and sourced installed EUR-2025 data/lifetimes/O&M; factor
  source years/bases. Finance rate, base factors and boiler-first/flare policy are already accepted.

Continue independent implementation with labelled settings/test providers. Record which
open items limit final certification or economic ranking.

## Entry template for future changes

ID / date / state / source or authority / old behaviour / chosen behaviour / reason /
affected files and public fields / validation required / evidence actually completed.

## Implementation decisions, 31 October 2026

- **D018 / implemented screening seam.** Actual main at 5294e159 inspected; no annual
  package/cost-source file found on the five recorded refs. Added a namespace cooling
  subpackage and shared SI kernel/StaticModel wrappers, not annual APIs. Explicit allocated
  branch/source/return/flow and finite-UA/tower/water boundaries; Rules cp supplied by caller.
  Linear auxiliary heat feedback closes algebraically; hot-pump/fan heat goes to ambient.
  Constant envelopes and absorption-first are analyst policies, not manufacturer calibration.
  No global config, well calls or runtime I/O. Tests include report fixture, full balances,
  source failures, scalar/vector parity and the high-UA limit. See 02/03 and evidence files.
- **D019 / cooling-direct cost subset.** EUR-2025 records/functions retain native capacity
  bases and missing values; known subtotal is not full-plant LCOC. Installed tower groups,
  combined water service and package O&M cannot be charged twice. Primary EIA/DOE originals
  retained in COOLING_COST_DATA; comparable normalised EUR packages/tower quotes remain
  missing. No invented FX, economic life or source heat bill. Tests cover annuity, scopes,
  zero delivery and missing prices. Joint plant allocation/factors remain with Reza.
- **D020 / handoff evidence.** Read actual existing SensParam schema on rn/challenge and
  exported parameter catalogue proposals/legacy field inventory without app changes. Raw
  organiser files stay ignored/unchanged; synthetic complete calendars make CI independent
  of that pack. Python 3.11/3.12 and timing are recorded separately. Joint M5/free cooling/maps
  remain deferred; do not call screening component checks full-plant validation.

- **D021 / conservative wet-sink phase boundary.** Final review found that a generic
  electric sink envelope also allowed a subzero wet-bulb-plus-approach estimate. The
  pure-water tower baseline has no freeze protection/bypass controller, so that estimate
  now gives zero feasible wet rejection and SINK_FREEZE_RISK, with backup/unmet cold.
  Weather is preserved; no temperature is clamped to fabricate operation. A regression
  checks zero wet service/water at this unsupported point. This is a baseline phase/control
  limitation, not a new weather forecast or a calibrated minimum-temperature control map.

- **D022 / local cost source now available.** During final checks an untracked local
  cost_sources.md snapshot appeared; SHA-256 is in PROJECT_STATE/COOLING_COST_DATA. This
  supersedes the current missing-FX-source limitation, not the earlier read-only branch
  observations. Source-linked EUR-2025 EIA capital/maintenance and DOE reference data are
  exported with full conversion factors. DOE's 2017 monetary basis is the team's assumption.
  Keep primary EIA 560/590 typical points; flag the summary's 540 lower endpoint. Source
  tower conversion ends in EUR-2024; do not relabel it as EUR-2025. Preserve unknown tower
  investment scopes/economic lives/O&M and no 20 C performance extrapolation. Original
  local source remains unchanged/untracked; normalization is input preparation only.
