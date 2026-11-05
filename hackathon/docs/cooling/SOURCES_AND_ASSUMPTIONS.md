# Sources, review record and assumptions

Original five-source review: 30 October 2026. Instruction/weather/review revision:
31 October 2026. This register separates authoritative challenge inputs, accepted
team clarifications and provisional modelling choices. Do not treat every number in the
report as a final requirement.

## Source review, in the requested order

1. **START_HERE.md**: read all eight sections; core team/API/workflow instruction.
2. **Three_Cooling_Options_Model_Design_Report.pdf**: all 28 pages read; equations, examples,
   integration and sensitivity reference. Its later uploaded (1) copy was also read in full
   and has the same 7,620 extracted words. Byte differences between exports do not imply a
   text change. The bundled original's hash below identifies the canonical local copy.
3. **Challenge PDF**: both pages read; hard baseline values and daily-balance requirements.
4. **Heating CSV**: all 365 rows parsed, date/value checks and monthly/year totals recomputed.
5. **Cooling CSV**: all 365 rows parsed; same checks plus heating/cooling overlap confirmed.

## Local source paths and SHA-256

Paths below are relative to repository root. Links are relative to this document.

- [START_HERE.md](START_HERE.md)
  - Path: `hackathon/docs/cooling/START_HERE.md` (moved from the repository root on 2 Nov)
  - SHA-256: `6188cb393d713f3e0dec3471cdc47c3a349f658f88bd58f7b2af192fed262921`
- [Three_Cooling_Options_Model_Design_Report.pdf](../../data/raw/reference/Three_Cooling_Options_Model_Design_Report.pdf)
  - Root path: `hackathon/data/raw/reference/Three_Cooling_Options_Model_Design_Report.pdf`
  - SHA-256: `4ff72d0459d407b54a1f0d0a55f26c6ba6188ff35efc3d8668f5a371c7bd820a`
- [GEMINI_Hackathon_Challenge_Requirements.docx.pdf](../../data/raw/challenge/GEMINI_Hackathon_Challenge_Requirements.docx.pdf)
  - Root path: `hackathon/data/raw/challenge/GEMINI_Hackathon_Challenge_Requirements.docx.pdf`
  - SHA-256: `925144aa7e30a9affb7f78497a23390b1db10543ddbb90d31cfaa3287238cdff`
- [GEMINI_Heating_Demand_Daily_2027.csv](../../data/raw/challenge/GEMINI_Heating_Demand_Daily_2027.csv)
  - Root path: `hackathon/data/raw/challenge/GEMINI_Heating_Demand_Daily_2027.csv`
  - SHA-256: `f5ab8feeb33721bbe6e0e5a4f84c4076de30c7c58b71987838b800761c913efb`
- [GEMINI_Cooling_Demand_Daily_2027.csv](../../data/raw/challenge/GEMINI_Cooling_Demand_Daily_2027.csv)
  - Root path: `hackathon/data/raw/challenge/GEMINI_Cooling_Demand_Daily_2027.csv`
  - SHA-256: `e0ceec2332cd708ca1f97dd3cf6141521058e83e05406b628a758ad15bc3d47a`

## Monthly checks, MWh

| Month | Heating | Cooling |
| --- | ---: | ---: |
| 01 | 19381.392 | 0.000 |
| 02 | 15215.208 | 0.000 |
| 03 | 12774.168 | 30.744 |
| 04 | 8404.800 | 556.584 |
| 05 | 4118.400 | 2636.400 |
| 06 | 2760.984 | 4778.352 |
| 07 | 2578.392 | 6270.960 |
| 08 | 2227.320 | 5199.552 |
| 09 | 4343.112 | 3293.088 |
| 10 | 8909.568 | 900.288 |
| 11 | 13072.512 | 76.560 |
| 12 | 17881.824 | 0.000 |

## Parameter provenance records

Store parameter path, value/unit, status (challenge/team assumption/sourced rating/fitted
map/scenario), source ID, reference conditions, validity range, price currency/year and
whether a missing input limits final validation. Link diagnostics/results to these records.

| ID | Value / purpose | Status and treatment |
| --- | --- | --- |
| A001 | Brine cp 3,990 J/kg/K | Accepted single Rules value, Reza review; Sharqawy et al. (2010), DOI 10.5004/dwt.2010.1079. Representative constant, not a new composition-specific measurement |
| A002 | Cooling 20/25 C, heating return 60 C | Supply fixed; water interpretation and returns provisional |
| A003 | HX approach 5 K | Team assumption; test 3/5/8 and finite UA |
| A004 | At most 330 actual on-days per doublet | Accepted Reza clarification D004; configurable mode defaults at_most |
| A005 | Ramey year-warmed flow-dependent source | Accepted Reza clarification D001; owner supplies implementation |
| A006 | Water COP 6, air COP 4, absorption 0.7 | Screening assumptions/reference; not applicable machine maps |
| A007 | Fan/pump ratios and tower-water inputs | Report fixture proxies; replace with hydraulic/control data |
| A008 | USD-2015 costs, electricity 150, heat 5, water 1.5 | Historical fixture only; no production USD ledger or absorption heat price |
| A009 | UK grid CO2 0.12943, CO2e 0.13096 t/MWh | Historical UK fixture only; not active plant factors |
| A010 | No external auxiliary-heat feedback in fixture | Reproduction simplification; full-physics mode must route it |
| A011 | Optional free mode off until implemented/tested | Aligned hourly KNMI input now available; hypothetical shares remain fixture-only |
| A012 | De Bilt station 260, 2025 weather mapped to 2027 | Replaceable user-approved Netherlands scenario; hourly calculations/daily screening, see 10 |
| A013 | Effective water treatment; N=5, latent fraction 0.8 | Explicit screening assumptions; user costs/limits and N=3/5/6 sensitivity, no chemistry solver, see 11 |
| A014 | EUR-2025, DEA 2020 uplift x1.168, Eurostat FX/CEPCI conventions | Accepted team convention; actual cost_sources.md ref and new cost records still to inspect/collect, see 12 |
| A015 | Real annuity discount 5.2% | Accepted team convention attributed to PBL SDE++ 2026; retain actual page/context on handoff |
| A016 | Plant grid CO2 0.20 and gas CO2 0.202 t/MWh | Team-provided CBS/IPCC attribution; actual source year/scope/energy basis retained from plant, not guessed |
| A017 | Existing annual plant/economics/design search and Sensitivity tab | Reza review is the source; current integration branch/ref not independently inspected here |

## Reference locations for equations/data

- GEMINI pinned report reference: commit d86e8bbcd128f1217eefa19d34c6b117039df74d,
  model_abstract.py, well_components.py, registry.py. Current team-main interface/CI were
  additionally checked at 5294e1590831474f2ce3352b95fb77d575055915. Inspect the actual checkout.
- [CEA electric data](https://github.com/architecture-building-systems/CityEnergyAnalyst/blob/96fc2f2bffb7f94a511a4480a31b73b496ad75ff/cea/databases/CH/COMPONENTS/CONVERSION/VAPOR_COMPRESSION_CHILLERS.csv).
- [CEA absorption data](https://github.com/architecture-building-systems/CityEnergyAnalyst/blob/96fc2f2bffb7f94a511a4480a31b73b496ad75ff/cea/databases/CH/COMPONENTS/CONVERSION/ABSORPTION_CHILLERS.csv).
- [CEA tower data](https://github.com/architecture-building-systems/CityEnergyAnalyst/blob/96fc2f2bffb7f94a511a4480a31b73b496ad75ff/cea/databases/CH/COMPONENTS/CONVERSION/COOLING_TOWERS.csv).
- [EnergyPlus chiller model reference](https://energyplus.readthedocs.io/en/v26.2.0/guides/engineering-reference/14.3-chillers.html).
- [DOE tower water guidance](https://www.energy.gov/cmei/femp/best-management-practice-10-cooling-tower-management).
- [DOE absorption factsheet](https://www.energy.gov/sites/default/files/2017/06/f35/CHP-Absorption%20Chiller-compliant.pdf).
- [Yazaki temperature/capacity information](https://www.yazaki-group.com/en/solar/device/aroace_ex_hw/index.html).
- [DESNZ 2026 factors](https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026).
- [Official Codex AGENTS guidance](https://developers.openai.com/codex/guides/agents-md),
  retrieved during preparation: startup discovery, override/size limits and fresh-run behaviour.

Use the report's source pages 27-28 for additional scope/vintage notes. Runtime simulation
must not fetch URLs; ingestion/calibration is separate. The source-temperature clarification
is a team-provided engineering statement, not an independently reproduced Ramey calculation.

## Added source records, 31 October

- Reza's review supplied by Ali in this request: accepted amendments D001/D002/D004/D009
  and D011-D017. It is the authority for the updated team defaults/scope/workflow; it is
  not a substitute for an actual supplier rating, installed quote or code inspection.
- [Hourly weather](../../data/raw/weather/knmi_debilt_2025/GEMINI_Weather_Hourly_2027_KNMI_DeBilt_2025.csv)
  - SHA-256: `d0a357572ffab16dbfeab8eb33e4e66794402e79bdb2f55246f21e360f778c1f`.
- [Daily weather](../../data/raw/weather/knmi_debilt_2025/GEMINI_Weather_Daily_2027_KNMI_DeBilt_2025.csv)
  - SHA-256: `2b51c2d848db73bf3d79c57b1cee6a7cb2852f8844966178062d64465943113b`.
- [Weather metadata](../../data/raw/weather/knmi_debilt_2025/metadata.json) and
  [validation](../../data/raw/weather/knmi_debilt_2025/validation.json): original archive
  snapshot, PsychroLib method, reporting-time conventions and source hashes, retained unchanged.
- [KNMI hourly archive](https://www.knmi.nl/nederland-nu/klimatologie/uurgegevens): De Bilt
  observations; not a 2027 forecast or a trend-analysis dataset.
- Sharqawy, M.H., Lienhard V, J.H. and Zubair, S.M. (2010), *Thermophysical properties of
  seawater: A review of existing correlations and data*, Desalination and Water Treatment
  16, 354-380, [DOI](https://doi.org/10.5004/dwt.2010.1079).
  Reza selects 3990 as the single representative brine cp. The paper's correlations depend
  on temperature/salinity; this pack does not infer salinity from density or add a second
  dynamic cp model. [MIT record](https://dspace.mit.edu/entities/publication/0c55d19d-eb62-4e5f-8a12-a71c2b53f36a).
- [PBL SDE++ 2026](https://www.pbl.nl/publicaties/advies-basisbedragen-sde-2026),
  [DEA catalogue](https://ens.dk/en/analyses-and-statistics/technology-data-industrial-process-heat)
  and [EIA equipment dataset](https://www.eia.gov/analysis/studies/buildings/equipcosts/):
  primary starting points for the M6 source collection, not newly populated EUR cost tables.

The cost-source file was not available at the stated path on the inspected main/rn/challenge
refs during this revision. Do not claim its conversion factors, CBS/IPCC source years or
Reza's unprovided integration ref were independently read. M0 must locate that current
source. Use the accepted review's explicit constants meanwhile, with their team attribution.
No production code, full-year plant solve, timing benchmark or new EUR quotation survey
was performed by this instruction-pack revision.

## Implementation additions (D018-D020)

- D018 is the source/status for provisional temperature envelopes, zero uninstalled capacity,
  finite user UA/flows and linear heat routing; metadata in PARAMETER_HANDOFF covers each
  settings field. A006/A007 remain screening COP/auxiliary ratios, not vendor maps.
- [EIA/Guidehouse Appendix A](https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/appendix-a.pdf),
  printed pages 125-126 and 129-130: source-native 2022 USD costs, technical lives and scope
  notes retained in COOLING_COST_DATA.json. EUR normalisation/site-installed scope unresolved.
- [DOE CHP absorption factsheet](https://www.energy.gov/sites/default/files/2017/06/f35/CHP-Absorption%20Chiller-compliant.pdf),
  pages 3-4 Tables 2/3: representative single-stage hot-water reference, not a 20 C supplier
  rating; source monetary year not supplied, and water-quality O&M scope retained.
- The initial source review above belongs to preparation of the instruction pack. This
  implementation verifies original hashes/calendars and follows the canonical equations;
  it does not claim a new independently solved Ramey history or a completed EUR cost survey.

- D022: local `hackathon/docs/challenge/cost_sources.md`, compiled 30 October, was read when
  it appeared during final checks. SHA-256 and local/untracked status are recorded in
  PROJECT_STATE. Its S25 FX/HICP factors now normalize the EIA/DOE reference points, with
  assumptions/scopes retained. S3 supplies PBL Table 6.3 p66; S20/S21 give IPCC NCV and CBS
  2024 integral-production CO2 metadata. This is a supplied source record, not a claim that
  every linked API/source was independently requeried. No source or performance default changed.
