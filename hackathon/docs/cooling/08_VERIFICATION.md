# 08. Verification and acceptance evidence

Write tests that can catch incorrect physics/accounting, not copies of the implementation.
Use hand calculations and independent scalar/year sums. A named screening fixture does not
prove a real geothermal design. Record which gates are run, failed, skipped or unavailable.

## Required checks

| Area | Meaningful checks |
| --- | --- |
| Data | Exact demand/weather columns/calendars; 365 daily/8760 hourly rows; no duplicate/missing/nonfinite inputs; join by date; original daily/annual energy preserved; UTC HH=24 rolls end time forward correctly |
| Weather | Derived wet bulb retained; RH 0–100; pressure MSL provenance; daily means match hourly within rounding; no daily-mean free-cooling certification; no demand change to match weather |
| Water | N>1; evaporation/blowdown/makeup balance; N=3/5/6 hand checks; supply checked per interval; None unchecked vs zero unavailable; treatment/service/disposal costs once; no chemistry solver |
| Units | MW/W, hours/seconds, GWh/MWh, m3/h/m3/s, bar/Pa, gauge/absolute and C/K boundaries |
| Components | Off/zero flow; actual outlet with shortfall; hot/cold reversal; UA=0/Cr=1; source/sink capacity and temperature limits |
| Electric | Rating/cycling/PLR domain, positive power, no infinite COP, package vs separate fans |
| Absorption | Generator COP balance; hot return/pinches; internal power; thermal-map domain; absent heat => backup/shortfall |
| Free cooling | Correct full/partial/off transitions; no double cooling; pumps/water counted; full backup retained |
| Annual coupling, joint M5 | 365 demand days, at most 330 actual active days per well, no forced summer running, per-well bounds, equal volumes, one 40 K budget and source heat not counted twice |
| Ramey boundary | Wellhead at each actual flow/depth; well_loss_k diagnostic not subtracted twice; 100 m3/h point included; T_res follows gradient; actual calls verified at joint M5 |
| Solver | Residual/tolerance termination, bounded iteration, nonconvergence status, no trial-power accumulation or state advancement |
| Contracts | Legacy names/args/keys and meanings, additive fields/defaults, JSON-safe outputs and UI compatibility path |
| Accounts | EUR-2025/5.2% real; scope/tower flags; fixed/variable O&M bases; auxiliaries in chillers/towers once; plant factors 0.20/0.202; no full-plant heat price; shared brine-heat allocation reconciles; zero denominator handled |
| Sensitivity handoff | Existing-app binding names/units/ranges; fresh paired configs; no second runner; no USD production ledger |
| Performance | Shared scalar/vector core parity across off/limited/backup states; 365-day/hourly batches; vector path or scalar <20 microseconds/day on recorded machine; no files/global settings/commercial-model calls |

For balances use abs(error) <= abs_tol + 0.001*scale. Define units of abs_tol and scale;
e.g. 1 W absolute at component level, 1e-6 MW at plant level. Near-zero denominators need
an absolute criterion. Demand = delivered + unmet is a service balance; delivered alone
equals demand only for a covered case. Validate heat, cold, electricity and mass separately.

BENCHMARKS defines numerical expected values for the deliberately simplified report fixture.
Keep those regression tests separate from current-default physics and temperature/hydraulic
integration tests. Its cp=3950 hand examples, USD/UK factors and 5% discount are historical
fixture inputs only. A real Ramey-coupled run need not reproduce an infinite-heat fixture.

Current-default independent hand checks (Rules cp=3990, rho_brine=1030):

| Case | Expected result |
| --- | --- |
| One doublet, 300 m3/h, 40 K total brine drop | 13.699 MW |
| Same flow, 10 K available to generator | 3.424750 MW generator heat |
| 4 MW absorption, COP_th=0.7, 10 K usable brine drop | 500.557913508 m3/h total, before grade/flow/map checks |
| Three 300 m3/h doublets, same 10 K and COP_th=0.7 | 7.191975 MW cold, before temperature/map limits |
| 1 MWh rejected, latent fraction 0.8, h_fg=2.45 MJ/kg, rho=1000, N=5, no drift | 1.175510204 m3 evaporation; 0.293877551 m3 blowdown; 1.469387755 m3 makeup |
| 1 MWh grid import at plant factor 0.20 t/MWh | 0.20 t CO2, counted centrally once |
| 1 MWh purchased gas at plant factor 0.202 t/MWh | 0.202 t CO2; native produced-gas CO2 remains separate |

Check cost scaling independently: 1 M EUR-2025 with a 25-year assumed test life at 5.2% real
has CRF=0.072381365451 and annual capital charge 72,381.365451 EUR/year. The 25 years here
is a test input, not the lifetime of every technology. Verify auxiliary and cost buckets
sum exactly once, including the added towers key. Test bundled-tower and standalone-tower
cost paths so an included tower cannot be purchased twice.

## Commands after the test directories exist

From repository root with PYTHONPATH=src, as in START_HERE:

```bash
pytest -q unit_test/gemini_model/electric_chiller unit_test/gemini_model/cooling_tower unit_test/gemini_model/free_cooling unit_test/gemini_model/absorption_chiller unit_test/dioscuri_plant
pytest -q unit_test/gemini_model unit_test/gemini_simulator unit_test/dioscuri_plant
black --check src unit_test
isort --check-only src unit_test
flake8 src unit_test --max-line-length=100
```

Use targeted existing directories while building; do not report nonexistent test paths as
passed. Include the cooling_common test path if created. On Windows use START_HERE's
PowerShell PYTHONPATH/venv setup. Preserve the existing CI commands and agent-test discovery
while adding the plant tests. Run Python 3.12 and preserve the team's 3.11 CI parity.

## Evidence levels and final completion

Store test command, date, environment/commit, result and meaningful limitation in PROJECT_STATE
or a linked generated evidence file. Do not paste large logs into the state file. Deadline
completion means the scoped M0/M1/M2/minimum tower/M4/M6 deliverables and handoff checks pass.
Do not require deferred M5 or a supplier-map model to call those scoped components complete.
Full-plant results still require joint integration, source/return checks, declared validity
envelopes, weather/price assumptions and all challenge constraints. Do not claim calibrated
performance without calibration. Report unavailable evidence rather than inventing it.
Time numerical cooling, annual dispatch and actual GEMINI work separately. A document-pack
check is not a production-code test, timing benchmark or completed EUR cost-data survey.

## Executed component gates (31 October 2026)

See [VERIFICATION_EVIDENCE.json](VERIFICATION_EVIDENCE.json),
[PERFORMANCE_EVIDENCE.json](PERFORMANCE_EVIDENCE.json) and PROJECT_STATE for actual commands,
versions, counts, corrected failed checks and limits. Local full suites pass on Python
3.11/3.12; raw-free checks skip only original-source/report fixtures. Shared scalar/vector,
three-circuit/HX/auxiliary/water/annuity/missing-cost/metadata checks run without M5.
Main's existing model physics is unchanged. Optional free cooling, supplier calibration,
normalised installed-EUR price completion and joint plant validation are not claimed.

Hosted CI run [41251968252](https://github.com/rezanajafisilab/dioscuri/actions/runs/41251968252)
failed before tests on D202 in unchanged main UI routes.py:32; the 3.12 matrix job was
cancelled. Read-only main inspection confirms the pre-existing blank line. This task
preserves that unrelated UI file and does not weaken lint. Local component/baseline
checks above are passing evidence; they are not a claim of green full-repository CI.
