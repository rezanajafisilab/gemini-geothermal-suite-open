# 05. Economics, CO2 and CO2e

Read the physical inventory and boundary before adding costs. Models return energy/material
quantities; the existing plant's central functions apply prices/factors once. M6 now delivers
cooling cost functions/data and emissions inputs only; the full Economics bridge is joint M5.
Use 12 for the required source/price-year records and installed-scope checks. Full-system
comparisons must serve the same heat and cold. A cooling-only cost allocation is not a full plant LCOH/LCOC result.

## Costs and price basis

```text
CRF(r,n) = r/[1-(1+r)**(-n)]        # r=0 -> 1/n
C_capital_annual = sum(I_j*CRF(r,n_j))
C_fixed_OM = sum(capacity_cold_MW_j*fixed_OM_EUR_per_MW_year_j)
C_variable_OM = sum(delivered_cold_MWh_j*variable_OM_EUR_per_MWh_cold_j)
C_water = V_makeup*(price_supply+price_treatment)
          + V_blowdown*price_disposal + fixed_water_service_EUR_per_year
C_cooling_direct = C_capital_annual+C_fixed_OM+C_variable_OM
                   + sum(E_cooling_electric_MWh_d*price_e_d) + C_water
C_cold_allocated = C_cooling_direct + cold_share_of_shared_brine_costs
LCOC = C_cold_allocated / E_cooling_delivered_MWh
```

For no cooling delivered return None/not_applicable, not zero or Infinity. Retain coverage
beside LCOC. If a finite project horizon is assessed, include replacement investment and
salvage in discounted cashflows; discount cooling in the denominator on the same horizon.
Do not apply both an annual capital charge and the original investment in one cashflow sum.
Keep real prices/real discount or nominal prices/nominal discount consistent.

Production costs use constant EUR-2025 and r=0.052 real, following Reza's PBL SDE++ 2026
convention. Lifetimes and fixed/variable O&M must be sourced separately for each technology.
Convert a source maintenance fraction into EUR/MW/year if needed; never apply both forms
to the same cost. Missing prices remain missing or explicitly labelled analyst scenarios.

Use the factors/conventions in the actual repository's hackathon/docs/challenge/cost_sources.md.
The accepted review specifies DEA 2020-to-2025 x1.168, Eurostat annual-average USD/EUR
conversion and CEPCI for Towler & Sinnott. Read the actual file/ref before claiming its
contents were checked. Preserve the original source value, source currency/year, each
conversion factor and final EUR-2025 value; see 12. Do not build a runtime USD ledger.

The constant USD-2015 report examples below and in BENCHMARKS remain regression tests
only, including their old 5% discount and UK grid factors. Never populate production EUR
fields with those numbers or silently convert a fixture until its expected results change.

Historical fixture only: CEA component proxies, P in W. These are not production defaults:

| Item | Investment, USD-2015 | Life / annual fixed maintenance |
| --- | --- | --- |
| CH1 water-cooled electric | 1,568,000+0.3049*P | 25 years / 5% |
| ACH1 single-effect absorption | 0.4395*P per eligible module | 25 / 5% |
| CT1 tower | 1,457.3+0.0161*P_reject_design | 20 / 10% |

CH1's cited capacity domain is 1.05-70 MW; ACH1's selected single-effect row is limited to
1.176 MW per module. Sum per-unit costs for actual modules, including any intercepts.
Cost the installed design, not each day's running capacity. Outages/free cooling do not
remove purchased backup/tower equipment. Other source domains must be checked at ingestion.

Air cooling needs its own quote/curve. The 3/5/7 million USD investments in BENCHMARKS are
analyst budgets, not market bounds. Include scope flags for installation, electrical works,
piping, controls, civil work, contingency, well/network costs and taxes. No unpriced item
silently becomes 'included'. The benchmark is a partial cost, not an installed 2027 quote.

## Source heat: choose a nonduplicating ledger

In the full plant absorption pays no separate heat price. Reza's accepted allocation splits
shared geothermal costs between heat and cold by brine heat used, at one consistent source
boundary. Generator heat taken from the brine is assigned to cold; direct geothermal heat
and heat-pump source extraction assigned to heating are assigned to heat. Include any
assigned branch losses once, and do not use boosted useful heating as if it were brine heat.

```text
f_cold = E_brine_for_cold / (E_brine_for_cold + E_brine_for_heat)
C_cold = C_cooling_direct + f_cold*C_shared_geothermal
C_heat = C_heating_direct + (1-f_cold)*C_shared_geothermal
```

Use annual energy sums for an annual share, not an unweighted mean of daily fractions.
The shared-cost pool must be explicit: source capital, shared O&M and source electricity
cannot also be charged directly to cooling. Dedicated cooling auxiliaries stay direct.
Heating top-up/fuel effects are calculated by the existing plant; do not replace them with
an extra heat bill. If no brine heat is used, keep any installed shared costs visible and
flag the allocation as undefined until the plant's fallback policy assigns them.

Without joint M5 source allocations, report cooling-direct cost with its partial scope,
not a completed whole-plant LCOC. Heat-price/opportunity-price experiments are confined to
the unchanged historical fixture; they are not the current plant ledger.

Net grid imports/exports after CHP belong to the plant's balance and tariff policy. Do not
subtract CHP generation independently in each cooling component. Keep purchases, exports
and component consumption separate. co2_saving_vs_gas requires a complete reference with
gas heating AND electric cooling, not a gas boiler credited with supplying cold.

## Emissions

```text
M_grid_CO2_t = sum(E_import_MWh*factor_grid_CO2_t_per_MWh)
M_grid_CO2e_t = sum(E_import_MWh*factor_grid_CO2e_t_per_MWh)
M_fuel_CO2_t = E_fuel * matching_fuel_factor
M_refrigerant_CO2e_t = charge_kg*annual_leak_fraction*GWP100/1000
intensity_kgCO2e_per_MWh_cold = 1000*M_CO2e_t/E_cooling_MWh
```

Separate CO2 from CO2e. Use the plant's accepted central defaults: grid CO2=0.20 t/MWh
(team attribution: CBS) and purchased-gas CO2=0.202 t/MWh (team attribution: IPCC). Preserve
their actual source year and energy basis from the plant/cost-source file when inspected;
do not invent a year or add a second cooling copy. The gas factor does not account for
native produced-gas CO2. Benchmark UK factors 0.12943 CO2 and 0.13096 CO2e t/MWh are
historical fixture data only. A CO2-only grid factor is not automatically a full lifecycle
CO2e factor. Keep geography, year, upstream/grid-loss scope and GWP assessment. Do not
count Scope 3 losses twice if already in a supplied factor. Physical emissions are not financially discounted.

Electrical chiller component `emission` is direct CO2 only (zero for these machines); compute
purchased-grid emissions centrally. Disable legacy component grid factors or reconcile
their contribution explicitly so the same kWh is not counted again.

A full-plant inventory uses actual grid/fuel/produced-gas flows once; do not add a second
allocated-heat emissions bill. Any allocation to cold is a reporting split of that same
inventory, not an additional physical release. Optional water-treatment electricity or a
supplier water-service emissions factor follows the nonduplicating boundary in 11.

## Produced gas: preserve the challenge baseline

The existing plant owns gas dispatch. Per Reza's review, burn available produced gas in the
boiler first, up to its usable demand/capacity, then flare the remainder. Count both methane
oxidation CO2 and the native 20% CO2 release once, including the flare path. Keep boiler/CHP
fields for compatibility, but do not invent a new produced-gas-to-CHP/export strategy in the
cooling task. Retain explicit liberation/capture/oxidation assumptions from the plant.

```text
V_gas_Nm3 = V_brine_m3 * 0.8 * fraction_liberated
m_CO2_kg = V_gas_Nm3*(44.01/22.414) *
           [0.20*f_native_CO2_released + 0.80*f_CH4_oxidised_to_air]
m_CH4_air_kg = V_gas_Nm3*(16.04/22.414)*0.80*f_CH4_to_air
M_gas_CO2e_t = m_CO2_kg/1000 + m_CH4_air_kg*GWP_CH4/1000
```

The molar-volume approximation uses normal gas conditions in the challenge. If the adapter
already returns a standard gas flow, do not multiply that gas flow by GLR again. Derive
potential gas from produced liquid or use a documented adapter field, with one inventory
owner. Gas liberation,
venting, burning/flaring efficiency, reinjection, capture and export must have explicit
fractions and mass conservation. Do not assume potential gas is all released or all benign.
Do not reduce GLR to zero as a workaround. Native CO2 is a mass release, not methane fuel
energy. If boiler/CHP already calculates methane-combustion CO2, the gas inventory must not
add that combustion CO2 again. Reconcile both plus native CO2 once at plant level.

Report excluded refrigerant, upstream and construction emissions as exclusions. Zero
assumed leakage is not a complete lifecycle assessment. Keep costs and physical emissions
as separate ledgers; an expensive heat source is not automatically a high-emission source.

## Implemented cooling-direct handoff (D019)

`dioscuri_plant.cooling_costs` supplies CoolingCostRecord, InstalledCoolingItem,
CoolingWaterPrices (a view of the six-input handoff, not a replacement Prices), annuity,
explicit conversion-chain helper and cooling_direct_cost. Inputs retain native cold or
rejection capacity/energy bases and per-module intercepts. Duplicate shared-tower purchases
and overlapping package electricity/water O&M are rejected. Missing scope/year/price/life
is retained with a known subtotal; no direct intensity is returned when required costs are
missing or no cold is delivered. Even complete direct costing excludes shared geothermal
allocation and is labelled partial. No source heat price, plant ledger or annual economics
function is introduced. Optional refrigerant leakage returns separate CO2e only.
