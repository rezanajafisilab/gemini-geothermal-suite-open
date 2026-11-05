# 01. Objective, authority and supplied demand

## Objective and ownership

Build three reusable cooling configurations with one consistent calculation boundary:
1. Water-cooled electric compression, optionally using a waterside free-cooling bypass.
2. Air-cooled electric compression without an evaporative tower.
3. Single-effect water/LiBr absorption with water- or air-cooled electric backup.

Provide transparent cooling energy, source heat, heat rejection, auxiliary power, water,
economics, CO2/CO2e inputs and sensitivity parameter metadata. Reza reports that an annual
plant, economics and design search already exist on his branch with placeholder cooling
formulas. Ali builds the cooling components/evaluator and cooling costs; Ali and Reza carry
out annual integration together at M5. Reza retains the agent/UI/well adapter. Preserve
heating interfaces and account for competition for brine heat through supplied boundaries.
The deadline scope and deferred features are defined in 07; no second dispatcher/search/tab.

Do not add storage, heat-recovery equipment, ORC, ATES or new well physics to this scope.
Keep existing heat_pump/recovery_heat_pump/boiler/CHP fields intact. Reuse existing heating
work or an explicit heating-boundary provider; do not pretend it has been evaluated when absent.

## Authority within the project

Current explicit user instructions apply first. START_HERE controls team workflow, ownership,
public names and code layout. Ali's supplied Reza review dated 31 October is an accepted
team amendment for the specific scope/default/workflow changes in REVIEW_AND_CHANGELOG.
It supersedes older pack wording on those points without editing the START_HERE snapshot.
The challenge PDF supplies fixed challenge values and hard constraints. The resolved temperature explanation is an accepted clarification (D001), not
an unanswered question. These cooling specifications translate the report into implementation
requirements. The report is a technical reference and screening example; older team notes
are secondary. A genuine contradiction must be recorded and reconciled, not silently edited
out of START_HERE or the raw sources. Higher-priority runtime instructions still apply.

## Fixed challenge baseline

| Item | Value |
| --- | --- |
| Reservoir midpoint / gross thickness / permeability | 2,500 m TVD / 100 m / 200 mD |
| Reference pressure | 250 bar(g), not a pump differential |
| Gradient / reference surface temperature | 30 C/km / 12 C |
| Brine density / viscosity | 1,030 kg/m3 / 0.00040 Pa s |
| Potential standard gas/liquid ratio | 0.8 Nm3 per m3 produced liquid |
| Gas CH4 / CO2 fractions | 0.80 / 0.20 mol fraction |
| Normal gas conditions | 0 C, 1.01325 bar(a) |
| Doublets for geothermal candidates | 1-3; zero only for an explicitly labelled reference |
| Flow while each doublet is active | 50-300 m3/h; zero when off |
| Total producer-to-injector cooling | At most 40 K across the entire surface plant |
| Production/injection liquid volumes | Equal, same reservoir |
| Simplified well pump efficiency | 0.70 |
| Supply to heating / cooling demand | 100 C / 20 C |
| Annual doublet operation | At most 330 actual active days per doublet; accepted team clarification D004 |

Alternative depth uses the given temperature gradient and hydrostatic pressure convention
through the well adapter: reservoir_temperature_c = 12 + 30*depth_m/1000. Thus 87 C is
the 2,500 m reference, not a constant for all depths. Keep pressure scaling in the adapter;
250 bar(g) is the reference at 2,500 m, not a universal pump differential. Rules has the
single brine_cp_j_kg_k value 3990, attributed by the team to Sharqawy et al. (2010).
Do not invent depth bounds, productivity or an injection-temperature floor. Missing bounds can be explicit study assumptions, never unnamed challenge requirements.

## Load the actual files by date

Paths are ../../data/raw/challenge/GEMINI_Heating_Demand_Daily_2027.csv and
../../data/raw/challenge/GEMINI_Cooling_Demand_Daily_2027.csv relative to this document.
Columns are exactly `date,heating_demand_MWth` and `date,cooling_demand_MWcool`.
Read every row. Join by date, not by row number. Reject duplicates, missing dates, nonfinite
or negative powers and mismatched calendars. Keep raw files unchanged. Use ordinary Python
csv/datetime plus NumPy; pandas is not required at runtime.

| Check | Expected value |
| --- | --- |
| Dates in each file | 2027-01-01 through 2027-12-31, 365 consecutive days |
| Heating energy | 111,667.680 MWh = 111.667680 GWh |
| Heating peak | 30 MW on 2027-01-28 |
| Minimum heating / days with heat | 2.673 MW / 365 |
| Cooling energy | 23,742.528 MWh = 23.742528 GWh |
| Cooling peak | 10 MW on 2027-07-19 |
| Positive / zero cooling days | 219 / 146 |
| Heating present on cooling days | Yes, every one |

Power values are daily means. Energy is MW*24 hours; monthly GWh is the sum over actual
calendar dates divided by 1,000. Never discard the other 35 demand days or multiply demand
by 330/365. These profiles do not establish hourly peaks, start/stop losses or tariff demand
charges. If hourly shapes are later assumed, preserve each original daily energy and label them.

## Provisional boundary, not an organiser definition

Treat cooling demand as heat removed from water supplied at 20 C and returned at 25 C.
Heating return is 60 C. Keep both return temperatures configurable. If 20 C means room/air
temperature instead, preserve the equipment model and add the appropriate demand-side adapter.
Whether cooling itself must be geothermal-driven is not established by these documents.

## Weather and simplified water inputs

The bundled KNMI hourly scenario is the default weather input for cooling calculations;
daily weather is a screening/checking alternative. It uses 2025 De Bilt observations mapped
onto 2027 dates, with original source timestamps retained. See 10 for exact fields, joins,
time assumptions and limitations. Do not change demand to match the weather.

Detailed hardness/conductivity/alkalinity/chemical-dose models are out of scope. Assume
effective treatment within supplier requirements; keep achievable concentration cycles,
water/service prices and maximum makeup-water flow as user inputs. Preserve water balances
and physical supply limits as specified in 11. A treatment fee alone does not establish
water availability, thermal performance or permissible discharge.
