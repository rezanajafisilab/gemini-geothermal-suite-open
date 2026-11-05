# Cooling development: reading and change guide

START_HERE.md in this folder is the core instruction. Read this index at every new
run. Apply the dated accepted amendments in DECISIONS and
[REVIEW_AND_CHANGELOG.md](REVIEW_AND_CHANGELOG.md) to START_HERE's older defaults/scope.
Read the initial set once per run, then the relevant sections again before changing
behaviour. Do not load every long reference into every prompt.

## Initial reading order

1. [START_HERE.md](START_HERE.md) in this folder.
2. [PROJECT_STATE.md](PROJECT_STATE.md) and [DECISIONS.md](DECISIONS.md).
3. [01_SCOPE_AND_REQUIREMENTS.md](01_SCOPE_AND_REQUIREMENTS.md).
4. [02_CONTRACTS_AND_CONFIGURATION.md](02_CONTRACTS_AND_CONFIGURATION.md).
5. [SOURCES_AND_ASSUMPTIONS.md](SOURCES_AND_ASSUMPTIONS.md).
6. [REVIEW_AND_CHANGELOG.md](REVIEW_AND_CHANGELOG.md), then the current deadline milestone
   in [07_IMPLEMENTATION_PLAN.md](07_IMPLEMENTATION_PLAN.md).
7. [10_WEATHER_INPUTS.md](10_WEATHER_INPUTS.md), [11_WATER_INPUTS.md](11_WATER_INPUTS.md)
   and [12_COST_DATA_HANDOFF.md](12_COST_DATA_HANDOFF.md) before changing their inputs.

The source PDFs/CSVs are local under ../../data/raw/. See the exact links and hashes in
SOURCES_AND_ASSUMPTIONS. Use source-specific pages when resolving an ambiguity, not an old
chat summary. The report's open wellhead-temperature question is resolved by decision D001.

## Before changing this subject, reread these files

| Change | Required reading in this folder |
| --- | --- |
| Public inputs, dataclasses, output keys, units | 02; DECISIONS; relevant callers; 08 contract checks |
| Cooling/heating demand, weather or aggregation | 01; 02; 10; 08 data/weather checks; M5 ownership |
| Water assumptions, makeup, treatment or supply/disposal limits | 03 tower; 11; 05 costs; 08 water checks |
| Electric chiller, tower, free cooling or heat exchanger | 03 relevant equations; 02 units; 08 physics checks |
| Absorption or geothermal heat allocation | 03 absorption/HX; 04; D001-D004; 08 integration checks |
| Flow, wellhead temperature, reinjection, availability | 04; 01 hard limits; DECISIONS; 08 integration checks |
| Prices, investment, currency, CO2/CO2e | 05; 12; source register; 08 accounting checks |
| Sensitivity parameters or ranking | 06; 05; existing app schema; no new runner |
| Performance, array path or runtime dependency | 02; 07/08 speed gates; accepted review |
| Bug fix, refactor, schema change | 09; affected specification; 08; PROJECT_STATE |
| New idea outside these three options | START_HERE section 8; DECISIONS; separate idea branch/card |

## Complete specification map

- [03_COMPONENT_EQUATIONS.md](03_COMPONENT_EQUATIONS.md): reusable physics and equipment.
- [04_DISPATCH_AND_GEMINI.md](04_DISPATCH_AND_GEMINI.md): joint M5 integration reference;
  source/return boundaries are consumed by components now, annual orchestration is deferred.
- [05_ECONOMICS_AND_EMISSIONS.md](05_ECONOMICS_AND_EMISSIONS.md): inventories and ledgers.
- [06_SENSITIVITY.md](06_SENSITIVITY.md): parameters/ranges for the existing app and fair comparisons.
- [07_IMPLEMENTATION_PLAN.md](07_IMPLEMENTATION_PLAN.md): milestones and completion gates.
- [08_VERIFICATION.md](08_VERIFICATION.md): checks and test commands.
- [09_DEBUGGING_AND_CHANGE_RULES.md](09_DEBUGGING_AND_CHANGE_RULES.md): maintenance workflow.
- [BENCHMARKS.md](BENCHMARKS.md): reproducible report fixture, not a geothermal design.

If sources conflict, use the authority rules in 01 and record the issue. Update the existing
specification rather than creating alternate v2/v3 instructions with unclear precedence.

## Added specifications

- [10_WEATHER_INPUTS.md](10_WEATHER_INPUTS.md): canonical hourly weather, daily screening,
  calendar joins, pure/vectorised evaluation and aggregation without a second dispatcher.
- [11_WATER_INPUTS.md](11_WATER_INPUTS.md): six user inputs, treated-water assumptions,
  water balance and supply/disposal limits without chemistry simulation.
- [12_COST_DATA_HANDOFF.md](12_COST_DATA_HANDOFF.md): required EUR-2025 data, scope flags,
  conversion sources, auxiliaries and optional refrigerant leakage.
- [REVIEW_AND_CHANGELOG.md](REVIEW_AND_CHANGELOG.md): accepted review-to-file traceability,
  precedence and exact scope of this document-only revision.

The historical BENCHMARKS file remains unchanged, including its USD/UK/legacy-cp examples.
It is test evidence only. Current plant defaults and current hand checks are in 05, 08 and
DECISIONS. Do not promote fixture values into Rules or Prices.

## Implemented handoff artifacts

- [CONTRACT_HANDOFF.json](CONTRACT_HANDOFF.json): frozen legacy field inventory and additions.
- [PARAMETER_HANDOFF.json](PARAMETER_HANDOFF.json): actual settings paths and existing-app proposals.
- [COOLING_COST_DATA.json](COOLING_COST_DATA.json): primary originals and explicit missing EUR inputs.
- [M0_EVIDENCE.json](M0_EVIDENCE.json), [VERIFICATION_EVIDENCE.json](VERIFICATION_EVIDENCE.json)
  and [PERFORMANCE_EVIDENCE.json](PERFORMANCE_EVIDENCE.json): actual checks and machine timing.
