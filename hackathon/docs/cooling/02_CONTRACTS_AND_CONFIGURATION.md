# 02. Public contracts and adjustable configuration

Read START_HERE section 5 before editing any public type or caller. Inspect actual current
code and Reza's integration branch: the annual plant/economics/search already exist according
to his accepted review. Proposed cooling additions must fit that implementation. A missing
package on main is not permission to create a competing annual model.

## Preserve the existing public surface

Keep these names and existing positional arguments:

```python
simulate_year(plant: Plant, demand: Demand, doublet: DoubletModel,
              rules: Rules = Rules()) -> YearResult
economics(plant: Plant, year: YearResult, prices: Prices = Prices()) -> Economics
stub_doublet(flow_m3h: float, depth_m: float) -> dict
DoubletModel = Callable[[float, float], dict]
```

Required doublet keys remain `wellhead_c`, `esp_mw`, `injector_pump_mw`, `gas_nm3h`.
Call for each active doublet at its own proposed flow/depth. Optional additional keys can
report actual flow, feasibility, pressures, violations and provenance. Reza's current adapter
also returns well_loss_k, a diagnostic already included in wellhead_c; never subtract it again.
Keep older four-key callers compatible, but test the new diagnostic when the current adapter
is used. Four numeric keys alone
do not establish that every pump/pressure constraint has been checked. Record whether
gas_nm3h is potential standard gas or actually separated gas; inspect existing semantics.
Undocumented gas basis remains a data-quality issue, not an assumption of atmospheric release.

Keep all Rules, Plant, Demand, YearResult and Economics fields listed in START_HERE.
Copy their exact field inventory into contract tests. Never turn USD into an EUR-named field,
CO2e into CO2, MW into energy, or cold output into useful heating.

## Additive cooling layer

Use small plain dataclasses, enums/Literal types and ordinary functions. Suggested additions:

- `CoolingSettings`: option, electric condenser type, free-mode enable, model level, equipment
  parameters, source/heat-rejection modes, solver tolerances and provenance IDs.
- `CoolingDayRequest`: date, requested cold MW, supply target, return C, optional loop flow.
- `CoolingBoundary`: hot-loop inlet/flow/allocated heat and return limit; sink inlet/flow or
  weather; availability; known hydraulic constraints; provenance and validation level.
- `CoolingDayResult`: cooling delivered/unmet, driver heat, powers by item, sink duties,
  water, circuit outlets/flows/dp, operating mode and diagnostics.
- `CoolingBatchResult`: array-valued cooling inventories plus masks/diagnostics and provenance;
  an existing equivalent may be reused instead of introducing a competing type.
- `CoolingContext`: explicitly passed boundary/heating/return-check providers and versions.

Provide a pure `evaluate_cooling_day(request, settings, boundary)` and a vectorised batch
equivalent, provisionally `evaluate_cooling_batch(requests, settings, boundaries, weather)`.
Reuse existing hooks/types where available and freeze the exact additive interface in M0.
These functions evaluate requested cooling against supplied boundaries; they do not choose
well on/off schedules, search whole-plant designs or replace simulate_year/economics.

The batch path accepts already-loaded NumPy arrays, including 365 daily values and optional
weather shaped (365,24). Daily source boundaries may be broadcast only under the explicit
fixed-daily-boundary assumption in 10. Both scalar and array wrappers must share one numerical
core and produce equivalent physical inventories. Keep validation/diagnostic formatting
outside the tight numeric loop. No files, network, runtime global configuration or hidden
cross-candidate cache; caller-owned immutable inputs may be reused.

The full YearResult bridge is joint M5 work inside the existing plant and is deferred in
this task. Prepare typed inputs/outputs, handoff examples and tests now; do not construct
fake heating totals or an independent simulate_cooling_year dispatcher. Extend Plant only
additively when required by the agreed hook, keeping design configuration separate from
weather/operating data.

## Component API and dependency direction

Reusable components subclass GEMINI StaticModel: `parameters`, `update_parameters`,
`calculate_output(u, x=None)`, `self.output`, `get_output()`. A call replaces the complete
output snapshot; it must not leave stale values from a previous active/off operating point.
`calculate_output` must not advance hidden state. Do not rely on a returned dict if a caller
uses GEMINI's output accessor.

Keep reusable physics and components in `src/gemini_model/`, annual dispatch and economics
in `src/dioscuri_plant/`. gemini_model must never import the challenge-specific plant package.
Use a small new cooling_common module for genuinely shared physics. Do not modify an
existing GEMINI exchanger to fix its direction; use a new checked component or team patch.

| Component key | Meaning / internal unit |
| --- | --- |
| power_cool / power_cool_unmet | Positive removed heat / shortfall, W |
| power_el | Equipment electricity within its stated boundary, W |
| power_drive | Positive absorption-generator heat input, W |
| power_reject | Heat sent to sink, W; not useful heat by default |
| power_th | Useful heating delivered; zero for these cooling-only components |
| emission | Direct CO2 rate, kg/s; grid emissions owned centrally |
| *_temperature_c, *_flow_m3s, *_pressure_drop_pa | Named circuit values with explicit units |
| status, violations, diagnostics | Machine status, plain sentences, structured detail |

Plant-level fields use `_mw`, `_m3h`, `_gwh`, `_bar`/`_pa`. Convert at one adapter boundary.
Do not infer ambiguous legacy units from suffix-free names; inspect the source and examples.
Never emit NaN/Infinity. Actual outlet C may be None if no flow makes it undefined; retain
the target separately and report off/limited status. Serialize None intentionally.

## Preserve annual meanings

- `heat_split_gwh`: existing geo/hp/recovery_hp/boiler/chp remain useful heat delivered.
  Generator heat and HP source heat are not additional useful heating.
- `cool_split_gwh`: keep abs/chill/recovery_hp meanings. Add `free` as an explicit additive
  category and test that all delivered-cold categories sum to cool_delivered_gwh.
  Add `cool_details_gwh` if needed. Do not silently call free cooling compressor cooling.
- If an old UI hardcodes three categories, add a presentation compatibility adapter and
  a truthful 'compression + free cooling' label, or coordinate its additive update with Reza.
  Canonical engineering records must still separate the two modes. See D005.
- Apply Reza's cooling electricity buckets additively. `chillers` owns compressors,
  air-condenser fans, absorber/solution internal power and dedicated chilled-water pumps;
  dedicated clean generator-loop pumps also belong here unless the existing plant already
  owns them as shared source equipment. `towers` owns wet-tower fans, condenser-water pumps
  and dedicated tower/free-HX circulation. `pumps` retains well ESP/injection and shared
  source pumps. Map every physical item to exactly one bucket after inspecting current
  callers; never add cooling auxiliaries to both chillers/towers and pumps. If a package
  COP includes an item, expose its ownership without charging it twice. Add the towers key
  with zero for non-tower cases and update aggregate sums additively at joint M5.
  hp/recovery_hp retain their meanings. The existing plant is the sole annual ledger owner.
- Add `co2e_t`, `validation_level`, `source_ids`, dated diagnostics, unmet cooling and water
  summaries. Keep `co2_t` as CO2. `co2_saving_vs_gas` needs the full reference plant.
- `source` identifies model version, not an invented validation stamp.

## Configuration and failure rules

All nontrivial inputs live in Rules, Prices or component/settings parameters with units,
status, source, price year if relevant, validity bounds and sensitivity range. Use
default_factory for mutable members and never mutate incoming defaults or dataclasses.
Use one default definition per parameter; avoid hidden literals in dispatch/economics.

Invalid configuration/data (negative capacity, nonsensical temperatures, unsupported doublet
count, corrupt CSV) raises ValueError. Physical shortfall, bad operating point, missing final
hydraulic validation or solver nonconvergence produces an explicit status/violation, preserving
diagnostic inputs. Missing final validation is not proof of physical failure or success.
Use mixed absolute/relative tolerances; distinguish harmless roundoff from a repaired violation.

## Active defaults and input ownership after the review

- Rules is the single owner of brine_cp_j_kg_k=3990 J/kg/K. Components receive that value
  through their explicit boundary/parameters, not a second independent brine-cp default.
- Rules.operating_days=330 is an at-most active-day cap. Keep an explicit mode, default
  `at_most`; an exact-target experiment must be selected and labelled, never the baseline.
- Prices/cost data use EUR-2025 and 0.052 real discount. Grid and gas factors come from the
  plant's central configuration, with accepted team defaults in 05. Do not create cooling
  copies that drift from the plant. The USD/UK report fixture is isolated test data only.
- Weather arrays are loaded/validated by an input layer, not by numerical evaluators. Use
  the exact CSV fields in 10; supplied daily demand remains authoritative over copied
  demand columns in the weather files.
- Water settings/prices and missing-value meanings are canonical in 11. Chemistry input
  arrays are not required. Costs are applied centrally once, never by a StaticModel.
- Each result records hourly vs daily-screening mode, effective-treatment assumption,
  source IDs and unchecked physical limits. A lower-detail mode is never labelled as
  calibrated hourly performance solely because hourly weather was supplied.

Contract tests preserve START_HERE field names, argument compatibility and meanings.
Assert the amended defaults from DECISIONS, rather than copying obsolete values from the
unchanged START_HERE sample (in particular cp=3950). Add the towers electricity key and
well_loss_k diagnostic compatibly; do not remove recovery_hp or existing legacy keys.

## Implemented additive seam, 31 October (D018)

The actual functions are in `dioscuri_plant.cooling.evaluate`, re-exported by
`dioscuri_plant.cooling`. `CoolingDayRequest` accepts date, requested_cold_mw, supply_c,
return_c and optional chilled_flow_m3h (computed sizing flow is marked unchecked).
`CoolingBoundary` supplies dry_bulb_c, wet_bulb_c, optional CoolingSource and availability.
`CoolingSource` requires wellhead_c, brine_flow_m3h, brine_density_kg_m3,
brine_cp_j_kg_k from Rules, brine_return_min_c, allocated_heat_mw, hot_flow_m3h;
well_loss_k is diagnostic only. Use an allocated branch, not duplicated complete well flow.
No default brine cp, reconstructed well loss or annual Rules/Plant/Prices class is added.

CoolingSettings and nested ElectricSettings/AbsorptionSettings/TowerSettings/WaterSettings
live in `gemini_model.cooling_common.config`; components never import dioscuri_plant.
CoolingBatchResult.values uses cool_mw/cool_unmet_mw, abs_mw/chill_mw/free_mw/recovery_hp_mw,
drive_mw, el_mw/chillers_mw/towers_mw and item powers, rejection, water rates and circuit C.
Undefined batch outlets use *_outlet_defined masks; scalar outlets become None (JSON safe).
Batch masks remain hourly; format_cooling_violations adds dated/hour-ending text on demand.
CoolingDayResult contains date, values, diagnostics, violations, source_ids and model level.
All outputs remain screening_uncoupled, including when load is fully covered.

CoolingWeather holds loaded arrays, mode, source_id and fixed_daily_boundary. Daily arrays
are expanded to (days,24) only with the explicit fixed_daily_boundary flag. aggregate_hourly
returns daily energy/mean/peak/water and any-hour masks, with no well scheduling or ledgers.
The existing annual functions and types are not present on the inspected refs and are not
reimplemented here; CONTRACT_HANDOFF.json freezes their exact source field inventory.

ReturnCheckRequest/ReturnCheckResult and CoolingContext are the proposed optional joint-M5
provider seam. Components never invoke heating_provider or return_validator. The plant must
apply the per-active-flow adapter and final shared 40 K/hydraulic/330-cap checks at joint M5;
none of these is claimed verified by component-only results.

Minimal scalar example (explicit screening equipment; no coupled plant claim):

```python
from dioscuri_plant.cooling import (
    CoolingSettings, CoolingBoundary, CoolingDayRequest, evaluate_cooling_day,
)
from gemini_model.cooling_common.config import ElectricSettings, TowerSettings

settings = CoolingSettings(
    electric=ElectricSettings(capacity_w=12e6, cop=6),
    tower=TowerSettings(capacity_w=20e6, circulation_m3s=1.0),
)
result = evaluate_cooling_day(
    CoolingDayRequest("2027-07-19", requested_cold_mw=10),
    settings, CoolingBoundary(dry_bulb_c=25, wet_bulb_c=20),
)
# result.values["cool_mw"], ["cool_unmet_mw"], ["el_mw"], ["makeup_m3h"]
# Missing supply/discharge/hydraulic/map evidence remains in result.diagnostics.
```

For normal prepared-weather calculations, load_demand_csvs and load_weather_csvs run once
in the input layer, pass a CoolingDayRequest with the loaded dates/cool_mw array and
WeatherInputs.hourly to evaluate_cooling_batch, then use aggregate_hourly. This evaluates
supplied boundaries only; source schedules/heating balances are not inferred.
