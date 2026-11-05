# 12. Cooling cost data and handoff to Reza

This is the M6 data/function deliverable, not an instruction to rebuild annual economics.
Read 05 for the ledger/allocation equations and 11 for user water inputs. Production data
use EUR-2025; every value retains a source and source price year. The unchanged report's
USD/UK examples belong only to regression tests. This revision specifies the required data;
it does not pretend that new installed EUR quotations have already been collected.

## Required technology records

Collect comparable installed scopes for water-cooled compression including its tower,
air-cooled compression, single-effect absorption including its tower, and a tower-alone
record. Also retain bare-component records when needed to cost shared-tower hybrid designs.

| Required field | Canonical handoff unit | Notes |
| --- | --- | --- |
| Installed capex | M EUR-2025 per MW cold | State capacity domain, installation scope, modular scaling and tower inclusion |
| Fixed O&M | EUR-2025 per MW cold per year | Retain original basis; convert fractions once if necessary |
| Variable O&M | EUR-2025 per MWh cold | Exclude electricity/water already priced separately, or mark their inclusion |
| Economic lifetime | years | Source per technology; do not use the report's 25/20 years as universal defaults |
| Water consumption | m3 per MWh heat rejected | Derived from the 11 parameters or sourced tower data, with basis retained |
| Makeup/treatment/disposal | EUR-2025/m3, plus fixed EUR/year | User values/supplier data with service scope |
| Auxiliary electricity | kWh per MWh cold | Fans, condenser/chilled-water pumps and solution/internal pumps, with boundary |
| Optional refrigerant charge | kg per MW installed cold | Identify refrigerant, charge source and capacity basis |
| Optional refrigerant leakage/GWP | fraction/year and kgCO2e/kg | State annual/end-of-life scope and GWP assessment/time horizon |

Use the actual installed capacity, not the capacity dispatched on one day. A value in EUR/kW
equals the same numeric value in thousands of EUR/MW; divide EUR/MW by 1e6 for M EUR/MW.
For linear specific cost c, investment EUR = c_MEUR_per_MW * installed_MW * 1e6. Preserve a
source's intercept/scale dependence or module limits instead of forcing it into a misleading
single per-MW number. Fixed O&M scales installed capacity; variable O&M scales delivered
cold from that item. Include a known subtotal/status when some costs are missing.

## Tower basis and avoiding duplicate investment

Tower source data often use MW rejected, which differs from MW cold. Retain the native
MW-rejection cost basis. To present an equivalent per-MW-cold value, multiply by the design
rejection/cold ratio and record that ratio and operating conditions. Tower-only fixed O&M
needs the same explicit basis conversion. For variable tower O&M originally per MWh rejected,
use actual rejected energy and retain that basis; an equivalent per-MWh-cold value depends
on the operating rejection/cold ratio. Do not divide by an unrelated absorption capacity.

If a chiller package includes its tower, do not add the same tower again. For absorption
with water-cooled backup sharing one tower, cost bare units plus one tower sized for the
largest feasible simultaneous rejection duty, or use a sourced package and a documented
incremental tower upgrade. Do not add two complete bundled towers to a one-tower design or
subtract an unknown tower price from a bundled quote. Dedicated towers are allowed only
when that is the actual selected topology. Retain the full installed electric backup when
its reliability policy requires it, even if its annual use is low or free cooling is enabled.

Check whether the quoted installed scope includes equipment, pumps, heat exchangers,
controls, water treatment, electrical works, piping, commissioning, civil work, contingency
and taxes. Keep scope flags for included/excluded/unpriced items. A bare equipment price
plus an analyst installation multiplier remains an estimate, not a supplier installed quote.

## Source/conversion procedure

First locate Reza's actual `hackathon/docs/challenge/cost_sources.md` on the integration
branch or merged main and record its ref/commit. It was not available at that path on the
main/rn/challenge refs inspected during this document revision; do not invent its contents.
The factors below are accepted from Reza's supplied review and must be reconciled with
that file when available. Component coding does not wait for a missing economics source.

1. Start with [DEA Technology Data](https://ens.dk/en/analyses-and-statistics/technology-data-industrial-process-heat),
   [EIA equipment cost/efficiency data](https://www.eia.gov/analysis/studies/buildings/equipcosts/)
   and DOE chiller/absorption sources. Confirm which technology and scope each table actually
   covers; a catalogue publication year is not necessarily its monetary price year.
2. Use manufacturers' documented performance at 20 C chilled-water supply, with hot/sink
   temperatures and flow rates. A 7/12 C rating alone does not validate a 20 C point. If
   no applicable data exist, retain the stated-envelope constant-COP model as screening.
3. DEA monetary data explicitly in 2020 EUR use the agreed x1.168 uplift to 2025. Do not
   apply it to values already in 2025 EUR or to every unrelated source currency/year.
4. Convert USD using the Eurostat annual-average exchange-rate convention specified by the
   source file. Record the dataset, year and direction: USD-per-EUR means EUR=USD/rate;
   EUR-per-USD means EUR=USD*rate. Never assume parity or use an unexplained spot rate.
5. For Towler & Sinnott, retain the source cost year and use the documented CEPCI index
   ratio to the chosen 2025 basis, then the agreed currency conversion. Do not stack DEA
   inflation and CEPCI for the same escalation. If a licensed index value is unavailable,
   mark it missing rather than invent it.
6. Record original value/unit/currency/year, each factor/ratio and final EUR-2025 value.
   The cost conversion chain must be reproducible, with no annual re-escalation inside
   a constant-real-price model.

Use 5.2% real annuity discount as the accepted team convention attributed to
[PBL SDE++ 2026](https://www.pbl.nl/publicaties/advies-basisbedragen-sde-2026). Keep the actual
page/table/context from cost_sources when inspected; do not present the review's attribution
as a newly verified universal financing rate for every chiller project.

## Data record and uncertainty

Each record needs technology/item/source_id, original value/unit/currency/price_year,
final_EUR_2025_value, conversion chain, capacity basis/domain, equipment/reference
temperatures, source page/table/URL or quote ID/date, lifetime, included-scope flags and
status (`sourced`, `user_input`, `analyst_scenario`, `missing`). Retain low/base/high values
only when supported or explicitly exploratory. Zero is allowed only as an explicit value,
not a substitute for an absent variable O&M, installation cost or leakage estimate.

Prepare records and a concise source/assumption list for Reza's Prices/economics adapter.
Use existing field names; document proposed additive names/units for gaps. A missing EUR
input does not justify a production USD ledger, an arbitrary currency conversion, a false
complete LCOC or a new cost survey presented as done. Keep historical fixture tests separate.

## Auxiliary electricity and emissions handoff

Report auxiliaries as physical energy items, with reference conditions and which items
are included in COP/package power. Convert a power ratio into kWh/MWh cold using actual
operating ratios; tower auxiliaries originally per MWh rejected are not automatically
per MWh cold. Include standby only if modelled/sourced. The canonical bucket mapping is
in 02: chillers for compressors/air fans/internal and dedicated chilled/hot-loop auxiliaries;
towers for wet fans/condenser and tower-loop pumps; shared source/well pumps remain pumps.
Each item has one owner and is priced/emitted once by the central plant.

Consume the plant's grid factor 0.20 tCO2/MWh (CBS attribution) and gas factor 0.202 tCO2/MWh
(IPCC attribution). Retain actual factor year and LHV/HHV/scope when inspecting the source;
EUR-2025 does not imply that every emissions factor is from 2025. Native produced-gas CO2
and boiler-first/remaining-flare routing remain the existing plant's responsibility in 05.
Optional refrigerant leakage is separate CO2e: charge_per_MW * installed_MW * annual_fraction
* GWP / 1000 gives tCO2e/year. Do not overwrite direct CO2 with CO2e.

The full plant assigns shared geothermal costs to heat/cold by brine heat used and adds
no heat price to absorption. Hand off generator heat, brine-side allocation/loss basis and
dedicated auxiliary inventories; do not reconstruct whole-plant allocation in each component.

## Collected evidence and remaining gaps, 31 October

[COOLING_COST_DATA.json](COOLING_COST_DATA.json) retains source-native EIA/Guidehouse
Appendix A printed pages 125-126/129-130 installed-cost and maintenance points, plus DOE
single-stage absorption Table 3 System 2. These are primary-source reference records, not
installed EUR-2025 package quotations. EIA technical life is not silently declared economic
life. Source cost year is explicit for EIA and unknown for the DOE factsheet. No USD-2022
number is passed as an EUR-2025 value; FX/escalation and unresolved tower/BOP scope remain
missing. Water/absorption bundled packages and tower-alone installed records are missing.
Do not rank complete economics from this partial source collection. Runtime costing accepts
normalised sourced/user/analyst records, checks scopes and retains missing subtotals.

The reviewed EIA air-chiller efficiency includes condenser energy; it cannot be used as a
compressor-only COP with a second fan charge. DOE O&M includes water-quality monitoring;
reconcile that against treatment charges. DEA industrial-heat catalogue is a starting point,
not evidence that a comparable installed cooling/tower quote has been found. The actual
team cost_sources.md and final EUR-normalisation chain remain required from Reza/suppliers.

### D022 update: supplied local conversion source

A local untracked cost_sources.md snapshot became available during final verification;
the SHA/ref status is recorded in PROJECT_STATE and COOLING_COST_DATA. The prior missing
conversion-source limitation is superseded for EIA/DOE reference normalization. Run
`PYTHONPATH=src python hackathon/scripts/normalise_cooling_cost_handoff.py` against that
preserved snapshot to reproduce nested derived_eur2025 records. Each point retains its
native module size, source values and conversion factors; no market quote or economic life
is inferred. The file's tower correlation conversion stops at EUR-2024, so final tower
EUR-2025 capital/O&M/life remains missing. Reconciliation notes flag mixed EIA columns,
unclear tower investment inclusion and DOE publication-year monetary assumption.
