# 10. Weather inputs and hourly cooling evaluation

This file owns the model's weather-use contract. Read it before changing weather, calendar
joins, free-cooling eligibility or cooling aggregation. The supplied CSVs and their original
guide/metadata are preserved under `hackathon/data/raw/weather/knmi_debilt_2025/`.

## Baseline files and meaning

- [Hourly CSV](../../data/raw/weather/knmi_debilt_2025/GEMINI_Weather_Hourly_2027_KNMI_DeBilt_2025.csv):
  8,760 model intervals. Use this for cooling calculations.
- [Daily CSV](../../data/raw/weather/knmi_debilt_2025/GEMINI_Weather_Daily_2027_KNMI_DeBilt_2025.csv):
  365 summaries. Use this for daily screening and checking, not hourly free-cooling claims.
- [Original data dictionary](../../data/raw/weather/knmi_debilt_2025/DATA_DICTIONARY.md),
  [guide](../../data/raw/weather/knmi_debilt_2025/README_WEATHER.md) and
  [metadata](../../data/raw/weather/knmi_debilt_2025/metadata.json) define every field/source.

The source is KNMI De Bilt station 260 in 2025, mapped by month/day and hour onto 2027.
This is a replaceable Netherlands scenario, not observed/forecast 2027 weather, a confirmed
project site or a typical/design weather year. Do not shift hot spells to match peak demand.
The original challenge demand files remain authoritative. Copied demand columns in the
weather CSVs must match them; a later demand change requires rejoining, not summing versions.

| Numerical input | Hourly column | Daily-screening column | Unit/use |
| --- | --- | --- | --- |
| Outdoor dry bulb | dry_bulb_c | dry_bulb_mean_c | C; air chiller envelope/maps |
| Outdoor wet bulb | wet_bulb_c | wet_bulb_mean_c | C; tower/free-cooling boundary |
| Relative humidity | relative_humidity_pct | relative_humidity_mean_pct | Percent, not fraction |
| Reported dew point | dew_point_c | dew_point_mean_c | C; provenance/checking |
| Sea-level pressure | pressure_msl_pa | pressure_msl_mean_pa | Pa; provenance, not measured surface pressure |
| Model date | date | date | 2027 daily join key |
| Source date/year | source_date/source_weather_year | Same | Retain 2025 provenance |

Wet bulb is already calculated using PsychroLib 2.5.0 from T, U and KNMI MSL pressure as a
near-sea-level proxy. It is not a directly observed KNMI variable. No PsychroLib dependency
or weather download is needed in runtime. Do not recalculate wet bulb from daily means.
The recorded sensitivity to 100 Pa lower pressure is below 0.006 K for this snapshot; this
does not justify using MSL pressure without correction at an elevated future site. Reported
dew point and humidity are independent rounded observations; use one consistent humidity
basis if later preparing a replacement dataset, rather than forcing them to match by edits.

## Time and demand alignment

Use fixed 24-hour UTC model days. The challenge demand timezone was not supplied; this
is an explicit modelling convention. Do not apply local daylight saving and create 23/25
hour days. `hour_ending_utc` runs 1–24: hour 1 is 00:00–01:00, hour 24 is 23:00–00:00 next
day. Group by date and hour_ending_utc, or interval start, not the end timestamp's date.
The final model interval ends at 2028-01-01T00:00:00Z; that is not an extra demand day.
Retain source_observation_time_utc independently, including its next-year midnight endpoint.

KNMI T/U/TD/P are reporting-time observations used as representative interval conditions.
Daily means/extrema are summaries of these 24 samples, not independent daily observations.
There are no missing required values or interpolation in the bundled scenario.

Repeat each original daily mean heating/cooling MW for its 24 hours as the baseline load
profile. This preserves daily energy exactly and annual heating/cooling of 111,667.680 /
23,742.528 MWh. It does not reveal true hourly peaks or establish the exact physical
relationship between historical weather and the supplied future demand. A later hourly
profile must preserve each day's energy unless the user explicitly replaces the demand.

## Input loading and the fast numerical path

Load/validate CSVs once in an explicit input/app/CLI layer. Pass numeric arrays and source
metadata to the pure cooling evaluator. Do not open files, fetch APIs or recreate 8,760
component objects inside every candidate calculation. Use arrays shaped (365,24), with
NumPy broadcasting for the daily requests and fixed daily boundaries. The scalar GEMINI
wrapper uses the same numerical core. Existing plant orchestration remains the sole owner
of well schedules and source allocation; this is not a new annual dispatcher.

```text
cold_request_mw[d,h] = original_cold_daily_mw[d]
source_limit_mw[d,h] = supplied_source_limit_daily_mw[d]  # explicit daily-constant case
hourly = shared_cooling_kernel(requests, weather, supplied_boundaries, settings)
daily_energy_MWh[d] = sum_h(hourly.power_MW[d,h] * 1 hour)
daily_average_MW[d] = daily_energy_MWh[d] / 24 hours
annual_energy_GWh = sum_d(daily_energy_MWh[d]) / 1000
```

A daily source limit is an instantaneous MW cap for every hour, not an energy bank. Check
hot-loop temperatures, allocated heat, sink/flow/water limits and unmet load at each hour.
Do not borrow heat or cooling from another hour without an actual storage model. Return
daily energies/mean powers plus maximum source/rejection/electrical duties, shortfall masks
and dated/hourly violations. Joint M5 must reconcile those peaks with the daily well/heat
boundary; average generator heat alone is insufficient. Keep heating at 100 C and the
shared 40 K source budget with the existing plant owner.

For the deadline, constant COP stays constant inside its stated envelope. Supplying hourly
weather does not turn it into a temperature-calibrated COP model. Weather checks operating
conditions and tower boundaries; optional M3 uses it for full/partial/off free-cooling
control. Free mode remains disabled until implemented/tested, and consumes fans/pumps/water.

## Daily screening mode

Label results `weather_mode=daily_screening` when using the daily file. Use the provided
means for screening conditions and sampled extrema to expose possible envelope exceedance.
Do not certify hourly capacity, free hours or water peaks from the means. Keep this mode
distinct from `hourly` in saved assumptions/results and compare it only as a fidelity check.
Monthly weather is for context/reporting; it is not an operating-control input.

## Validation and replacement

Validate all rows: exact 2027 calendar, 365 daily dates, 24 distinct hours/date, 8,760
continuous intervals, consistent source month/day/year/station, finite required values,
humidity in 0–100 and positive pressure. Wet bulb must not exceed dry bulb beyond rounding.
Reject duplicate/missing keys; never replace missing weather by zero or silently interpolate.
Check daily means against hourly values with an absolute rounding tolerance of 0.000501 in
the stored units, and compare every copied demand value and each daily energy to its source.

Allow a user-provided station/year dataset using the same schema and a new source ID.
Document leap-day, timezone, gaps and pressure treatment when preparing it. Keep dry bulb,
humidity and wet bulb from a consistent weather state; do not sample them independently.
Other years in the retained KNMI archive are available as raw material, not already prepared
or validated scenarios. Keep weather preparation outside runtime and preserve original files.

## Implemented loader and aggregation

`dioscuri_plant.cooling.inputs.load_demand_csvs` joins authoritative demand by date;
load_weather_csvs validates hourly and daily schemas, UTC endpoints/source year/station,
finite/ranged values, all copied demand and every daily statistic within 0.000501.
Inputs remain outside evaluation; no weather files are reopened per candidate. Original
source rows and daily extrema are retained in WeatherInputs for screening review. The
daily mode cannot certify hourly extrema; hourly calculation is the default prepared input.
Complete synthetic-calendar tests run without raw files; local original-data tests also
verify the four unchanged CSV SHA-256 values. See M0_EVIDENCE and VERIFICATION_EVIDENCE.
