# 11. Simple tower-water model and user inputs

This file owns the water assumptions, fields and missing-value meanings. Use it with 03
for physical inventories, 05/12 for costs and 08 for checks. It applies to wet towers in
water-cooled compression, absorption/backup and optional wet-tower free cooling. The
air-cooled configuration has no evaporative tower-water demand.

## Simplification and boundary

Assume treatment, monitoring and maintenance keep circulating water within equipment-supplier
requirements. Do not require hardness, conductivity, alkalinity, pH, ion composition or
chemical-dose time series in the cooling solver. The supplier/user represents the outcome
through achievable concentration cycles and treatment/service costs. Record this as an
assumption until supported; treatment cost alone is not proof of maintained performance.

Cycles N describe the concentration of dissolved material relative to makeup water. They
determine blowdown even when treatment is effective. Treatment does not make water supply,
heat rejection or permissible discharge unlimited. Preserve these physical limits and the
main chiller/tower temperature/energy calculations. This is an annual energy/economic model,
not a design of treatment equipment or a prediction of water chemistry.

## Six user inputs

These are proposed additive binding names. Reuse an existing equivalent and record the
mapping during M0; do not rename a public field or keep two conflicting defaults.

| Input/binding | Unit | Base/missing policy |
| --- | --- | --- |
| Prices.water_supply_eur_per_m3 | EUR-2025/m3 delivered makeup | User/source value; None means cost missing, not free water |
| Prices.water_treatment_eur_per_m3 | EUR-2025/m3 delivered makeup | Variable treatment service; None missing, explicit 0 allowed |
| Prices.blowdown_disposal_eur_per_m3 | EUR-2025/m3 discharged | User/source value and disposal-cost basis |
| Prices.water_fixed_eur_per_year | EUR-2025/year | Fixed supply, monitoring and treatment-maintenance charges |
| CoolingSettings.water.cycles | Dimensionless, >1 | 5 provisional; sensitivity 3/5/6; supplier confirmation pending |
| CoolingSettings.water.max_makeup_water_m3h | m3/h delivered to tower | None means availability unchecked; 0 means no makeup supply |

All rates need currency/price year, source/status and scope. Normalise other price years
through 12. Water supply and treatment may be one quoted service; store its scope and apply
it once. An explicit combined rate must not also be charged as separate supply/treatment.
Fixed or variable tower O&M may already include treatment/monitoring: remove the overlap
from one ledger, not add both. Fixed charges generally remain for installed equipment even
when temporarily off; document the actual contract basis. For an option without a wet tower,
these tower-water items are not applicable and do not require artificial zero-price inputs.

The flow limit is water available after treatment at the tower. Raw-water withdrawal and
pretreatment reject are outside this simple boundary. If a proposed treatment process has
material losses/energy/capital, obtain a delivered-water service cost/limit or add its
explicit aggregate inputs; do not claim a cost-only proxy captures those physical effects.
An owned treatment plant needs sourced capital as well as O&M; a genuine outsourced service
can instead be represented by its quoted service charges.

## Water inventory

The simple baseline uses water density 1000 kg/m3, h_fg=2.45e6 J/kg, latent fraction 0.8,
and negligible drift/leaks. These are explicit screening parameters, not Netherlands water
measurements or automatically calibrated by the weather file. Keep them adjustable in one
component-parameter definition, with N sourced from the single setting above.

```text
V_evap_m3 = latent_fraction * Q_tower_W * dt_seconds / (rho_water * h_fg)
V_blowdown_m3 = V_evap_m3/(N-1) - V_drift_m3
V_makeup_m3 = V_evap_m3 + V_blowdown_m3 + V_drift_m3
makeup_rate_m3h = V_makeup_m3 / interval_hours
```

N must exceed 1. Use an explicit off branch when there is no tower duty/flow. With drift=0,
makeup is evaporation times N/(N-1). At N=3/5/6, those factors are 1.50/1.25/1.20. Thus the
same evaporation needs 20% more makeup at N=3 than N=5. Negative calculated blowdown means
inconsistent inputs; do not silently clip it. Add drift only with a declared rate/basis.

Use actual tower heat rejection, not cold duty: compression rejects cold plus compressor
heat, absorption rejects cold plus generator heat/internal power, and free mode still
rejects its transferred heat and assigned auxiliary heat. Use the heat-routing rules in 03.
At the baseline parameters and N=5, 1 MWh rejected needs about 1.4694 m3 makeup. A cold-output
water intensity must use each option's actual rejection/cold ratio, not this value directly.

## Costs, electricity and emissions

```text
C_water_EUR_year = annual_makeup_m3*(supply_EUR_m3+treatment_EUR_m3)
                   + annual_blowdown_m3*disposal_EUR_m3 + fixed_EUR_year
```

Apply this once in central economics. Keep fixed/variable treatment, tower electricity,
general O&M and disposal scopes separate. If any required cost is missing, return the
physical inventory and the known cost subtotal with a missing-cost status; do not publish
a complete-cost LCOC or silently replace missing prices by zero.

Optional aggregate treatment electricity can be supplied as treatment_kwh_per_m3 and
multiplied by makeup volume. Keep it in exactly one central electricity bucket; if the
treatment tariff already includes its electricity, reconcile financial ownership before
adding a second grid charge. An optional supplier kgCO2e/m3 factor needs a documented
boundary so its electricity is not also counted again in that same emissions total.
Only on-site treatment electricity belongs in plant grid imports. Off-site supplier
emissions are reported with their separate service boundary, not relabelled as plant grid
consumption. An unavailable treatment footprint is a stated exclusion, not measured zero.

## Supply and discharge limits

Check aggregate cooling-tower makeup per hourly interval, including shared hybrid towers
and free mode. A common supply allocation cannot be given in full to each parallel component.
With a finite supply cap and
no storage, reduce the feasible tower/chiller operating point consistently and re-evaluate
its heat/electricity/water balance, or report water-limited operation and unmet cooling.
Use an existing alternative only if installed and available. Do not clip water use while
leaving the same cooling output, assume a storage basin or buy an unmodelled air backup.

None means the limit was not checked. It may be used for screening, with a visible
WATER_SUPPLY_NOT_CHECKED status, but not a verified site-feasibility claim. Zero is a real
zero supply; wet operation needing makeup cannot pass without an explicit stored-water
model, which is outside this deadline scope. Water-supply and operating-day caps are
different constraints.

Discharge price does not establish acceptance of blowdown. Record discharge conditions as
assumed or verified metadata; if a user supplies a maximum blowdown rate or no-discharge
condition, enforce it without a chemistry solver. Unknown conditions remain unchecked.

## Accuracy and sensitivity

The baseline assumes maintained performance under effective treatment. Real scaling/fouling
can change heat transfer and energy use; model one optional aggregate degradation scenario
only if useful, with its basis stated. Do not apply both a supplier fouling allowance and
the same extra penalty. Detailed degradation/chemistry is not a deadline requirement.

Send N=3/5/6, independent user cost ranges, makeup caps and optional performance allowance
to Reza's existing Sensitivity tab. Respect known relationships between treatment service,
achievable N and performance; an unsupported high-N/zero-cost combination is an analyst
scenario. Report cooling, electricity, water, cost and status together. Accurate comparisons
remain conditional on these assumptions and equipment/weather validity, not on a promise
of unchanged accuracy after removing all water-quality effects.

Reference: DOE/FEMP [Cooling Tower Management](https://www.energy.gov/cmei/femp/best-management-practice-10-cooling-tower-management)
for water balance, chemistry-dependent concentration cycles and treatment cost scope.

## Implemented supply/discharge treatment

WaterSettings owns cycles and optional max_makeup_water_m3h/max_blowdown_m3h. One
tower_budget function applies these to aggregate rejection before absorption/backup duties
are calculated; delivered cooling, power, rejection and water are recomputed together.
None limits emit WATER_SUPPLY_NOT_CHECKED/DISCHARGE_NOT_CHECKED during wet operation.
No-discharge and zero makeup are genuine constraints; air backup operates only if installed.
CoolingWaterPrices mirrors the four proposed Prices field names for handoff. Composite
supply/treatment has one rate and treatment=None; overlapping O&M scopes need reconciliation.
The physical kernel never prices water. Effective treatment remains explicitly assumed.
