> **How the patches are used now (29 Oct 2026).** GEMINI's files in `src/` stay exactly as released (`development`, 1.0.3). `src/gemini_agent/gemini_runtime.py` copies `gemini_model` and `gemini_simulator`, applies every file in `patches/` in order, and imports the copy as `gemini_model_fixed` / `gemini_simulator_fixed`. The agent's designs run on that copy, and the copy is checked file by file against `git apply` of the same patches. `scripts/14_bug_impact_on_designs.py` runs each design on both versions and writes [`BUG_IMPACT.md`](BUG_IMPACT.md), the "what the released code would have given" table. Patches 08–10 were added on 29 Oct:
>
> - `08_heatpump_electricity_emission.diff`: `HeatpumpBasic` reported zero CO₂; it now counts its electricity (optional `electricity_emission_factor`).
> - `09_register_heatpump.diff`: the simulator's registry had no heat pump, so a project could not use one.
> - `10_heatpump_carnot_source_outlet.diff` (after 04): the Carnot COP used the source's *inlet* temperature. With a brine cooled from 53 to 30 °C, that gave a COP above the physical Carnot limit. The evaporator has to run below the source's outlet, so the COP is now taken there, and both modes solve the source balance.
>
> - `11_well_brine_properties.diff` (30 Oct): the well model's fluid was water at standard conditions, hard-coded in `_build_dpdt`. A well config may now pass `fluid` (`RHOL`, `VISL`, `CPL`) so the well carries the brine it really produces (the challenge's 1,030 kg/m³, 0.40 mPa·s). Without it, behaviour is unchanged.
>
> The same files are the upstream PR.

> Copied from the 2026-10-27 bug-hunt session. `$SCR` paths refer to a temporary scratch folder; the scripts, outputs and patches are copied next to this file (`scripts/`, `outputs/`, `patches/`). Patches apply to upstream `development` with `patch -p1 --binary` (CRLF sources). Do not apply them to our main tree without a decision (2025 rule: do not alter provided models; wrap instead).

# GEMINI (gemini-geothermal-suite-open): runtime evidence and fatal-bug hunt

Date: 2026-10-27. Code under test: `development` @ `0cd5add` ("simulator is implemented (#43)"), plus
`origin/geoloop` @ `1ec683c` for the borehole heat exchanger (BHE) model. Scope: `src/gemini_model`,
`src/gemini_simulator`, `unit_test/`, `simulator_examples/`. The Flask app, Docker stack and databases
were out of scope (Docker is not usable on this machine).

Paths used in these notes (`$SCR` = a temporary working folder):

* `$SCR/upstream/gemini`: the shared clone. I did not modify it. I exported trees with `git archive`.
* `$SCR/work/gemini-dev`: export of `development` (all runs below unless stated otherwise).
* `$SCR/work/gemini-geoloop`: export of `origin/geoloop`.
* `$SCR/work/gemini-fixed`: `development` with my candidate fixes applied (see section 7).
* `$SCR/bughunt/*.py`: reproduction scripts. `$SCR/bughunt/outputs/*.out` holds their captured output.
  `$SCR/bughunt/patches/*.diff` holds one suggested fix per issue.
* `$SCR/envs/gemini311` (main) and `$SCR/envs/gemini312` (geoloop): the two conda environments.

---------------------------------------------------------------------------------------------------

## 0. TL;DR

* **Setup.** Only `numpy`, `scipy` and `pytest` are needed for the models and the simulator. The full
  `pyproject.toml` (Flask, Celery, chromadb, langchain and so on) is not needed. Setup takes about 2 minutes.
  geoloop needs a second env on Python 3.12.
* **Tests.** `pytest unit_test` gives **92 passed, 0 failed** in 0.65 s. 91 of these are in gemini_model and
  gemini_simulator. The one gemini_framework test (AVEVA) passes without doing anything, because it has no
  credentials. No test needs a running service.
* **Examples.** Both examples run (about 0.4 s wall each, including imports). One `solver.run()` takes
  **1.4–1.9 ms**. Energy and mass balances of the doublet example close to 1e-16.
* **Time series.** The simulator is **steady-state algebraic**. `Solver.run(time_vector)` exists, but
  boundary inputs are constant and no shipped component varies with time. An 8760-hour profile can be
  driven in **about 10 s** (custom `set_time` profile component, or a Python loop). Demand-following with
  root-finding per hour takes **about 1.4 min per year**.
* **Fatal bugs confirmed by execution.**
  1. Heat exchanger heat flows cold to hot.
  2. Heat pump returns a spurious root, with heat and electricity 10–1000x wrong.
  3. Injection-well friction sign is wrong.
  4. Nodal solve can silently return non-physical ESP roots.
  5. ESP affinity law is misapplied.
  6. Recycle loops are not converged.
  7. Compressor power is low by a factor k.
  8. geoloop BHE double-steps inside the Solver and costs O(N²) per year.
  9. The two-phase path is unusable.
  10. The default roughness (10 mm, docs say "mm") changes flow by +58%.

  Details are in section 6.

---------------------------------------------------------------------------------------------------

## 1. Setup recipe (tested)

```bash
SCR=<scratch dir>; G=<clone of gemini-geothermal-suite-open>
# 0) use an exported tree (the shared clone must stay untouched; also avoids __pycache__ in it)
mkdir -p $SCR/work/gemini-dev && git -C $G archive development | tar -x -C $SCR/work/gemini-dev

# 1) isolated env (conda base only on this box; no poetry/uv; ~1-2 min)
conda create -y -p $SCR/envs/gemini311 python=3.11
PY=$SCR/envs/gemini311/bin/python
$PY -m pip install "numpy==2.2.6" "scipy==1.13.1" "pandas==2.3.3" "pytest==8.4.2" "pytest-cov==5.0.0"   # 14 s
# optional: only for unit_test/gemini_framework (AVEVA driver import)
$PY -m pip install "adh-sample-library-preview==0.10.19rc0"
# optional: CI lint tools
$PY -m pip install "flake8==7.3.0" "flake8-docstrings==1.7.0" "black==25.11.0" "Flake8-pyproject==1.2.3"

# 2) run
cd $SCR/work/gemini-dev
$PY -m pytest -p no:cacheprovider -q unit_test               # pyproject sets pythonpath=src for pytest
PYTHONPATH=src $PY simulator_examples/run_doublet_plant_example.py
PYTHONPATH=src $PY simulator_examples/run_parallel_hex_plant_example.py

# 3) geoloop branch (needs Python >=3.12,<3.14)
mkdir -p $SCR/work/gemini-geoloop && git -C $G archive origin/geoloop | tar -x -C $SCR/work/gemini-geoloop
conda create -y -p $SCR/envs/gemini312 python=3.12
P312=$SCR/envs/gemini312/bin/python
$P312 -m pip install "geoloop==1.1.0" "pytest==8.4.2"
$P312 -m pip install "numpy==2.2.6" "scipy==1.13.1" "pandas==2.3.3"   # re-pin; geoloop pulled numpy 2.5.4 / scipy 1.18.1
mkdir -p $SCR/work/geoloop_run && cd $SCR/work/geoloop_run       # config has base_dir="output" (relative)
PYTHONPATH=$SCR/work/gemini-geoloop/src $P312 -c "from gemini_model.bhe_geoloop.bhe_geoloop import BHEGeoloop"
```

Pip freezes of both envs are in `$SCR/notes/requirements-gemini311.freeze.txt` and
`$SCR/notes/requirements-gemini312-geoloop.freeze.txt`.

Pitfalls:

* Every dependency installed. Nothing failed. `adh-sample-library-preview==0.10.19rc0` installs fine from
  PyPI.
* `pyproject.toml` has `package-mode = false`, so nothing gets installed as a package. Scripts need
  `PYTHONPATH=src`. pytest gets it from `[tool.pytest.ini_options] pythonpath = "src"`. The example
  docstrings show PowerShell syntax (`$env:PYTHONPATH="src"`).
* The full `poetry install` would pull the whole web, AI and DB stack. It is not needed for
  models/simulator.
* geoloop 1.1.0 requires Python >= 3.12, but the main project declares `^3.11`. The geoloop branch adds
  `geoloop = {version="1.1.0", python=">=3.12,<3.13"}`. On 3.11,
  `import gemini_model.bhe_geoloop.bhe_geoloop` raises `ModuleNotFoundError: geoloop`. The rest of the
  repo works on 3.12: 91/91 model and simulator tests pass with numpy 2.2.6 and scipy 1.13.1. A single
  **Python 3.12** env therefore serves both. geoloop also pulls the obsolete PyPI `pathlib` backport. It
  is harmless, because the stdlib shadows it.
* Many source files use **CRLF** line endings. Apply patches with `patch -p1 --binary`.
* `BHEGeoloop` writes or reads relative to CWD (`base_dir: "output"`). Run it from an empty directory.

---------------------------------------------------------------------------------------------------

## 2. Test results

| Suite | Result | Notes |
|---|---|---|
| `unit_test/gemini_model` + `unit_test/gemini_simulator` | **91 passed**, 0 failed (0.5 s) | same on Python 3.12 |
| `unit_test/gemini_framework` (AVEVA driver) | 1 passed (vacuous) | prints "No credentials file. Did not test the connection". It looks for `unit_test/database/credentials/avevadb.json`, but the template lives in `unit_test/gemini_framework/database/credentials/`. Needs network credentials, not local services. |
| total `pytest unit_test` | **92 passed** in 0.65 s | CI command `pytest -v --cov -p no:faulthandler` also green |

Coverage of `gemini_model` and `gemini_simulator` is 73% overall. Some modules are barely tested:
`well/correlation/beggsbrill.py` at 3%, `erosion/*` at 0%, `reservoir/injectivity_index.py` and
`reservoir_pressure_estimation.py` at 0%, `reservoir_pressuredrop.py` at 32%, and `heatpump_basic.py` at
72%.

**Caveat about what passing means.** Most simulator tests are *regression tests against a "reference
doublet-A run"* of the legacy GEMINI model, not independent physics checks. Examples:
`test_well_flow` expects 135.93 m3/h at 69 Hz, and `test_injector_well` expects ESP power 174,444.7 W.
They encode the same roughness (0.01 m) and the same ESP frequency scaling as the code.
`test_solve_injection_flow_rate_balances_pressures` recomputes the well with the same (+Q) sign as the
solver. So it cannot catch the injection-sign error.

With my candidate fixes applied (`$SCR/work/gemini-fixed`), **84 tests pass and 7 fail**. All 7 failures
assert the old numbers:

* compressor: 1 test
* heat pump: 2 tests, off by 0.2 W in 131 kW. Their tolerance tests Nelder-Mead noise.
* `test_injector_well`: 2 tests, ESP and roughness
* injection balance: 1 test, the sign
* `test_well_flow`: 1 test, roughness and ESP

---------------------------------------------------------------------------------------------------

## 3. Simulator examples: outputs and timing

### 3.1 `run_doublet_plant_example.py` (development tree)

```
Solved primary flow rate (well nodal balance): 129.02 m3/h
Separator out:   P=2.8710 bar, T=79.00 C
Heat exch. out:  T_primary=44.11 C, T_secondary=59.04 C
Boiler:          T_out=61.97 C, power_th=0.401 MW
CHP:             T_out=21.95 C, power_el=0.033 MW, power_th=0.067 MW
ESP (producer):  power_el=0.1744 MW
Injector well:   P_wellhead=0.0010 bar (surface P=1.4500 bar)     <- bracket floor ("no pump needed")
Injector pump:   power_el=0.0000 MW
T_s_out:         53.97 C
power_plant:     5.825 MW  (secondary-network thermal power)
power_doublet:   5.357 MW  (primary-side thermal power extracted)
power_total:     5.684 MW
electricity_surplus: -0.1410 MW
emission_total:  4082.05 kg CO2/day
ESP_in 45.67 bar, ESP_out 74.10 bar (ESP at 650 m MD); Pres_P 250 bar, Pres_I 240 bar
```

Balance checks (executed):

* power_plant = HEX duty 5.3570 + boiler 0.4014 + CHP_th 0.0669 = **5.8253 MW** (closure 4e-16).
* The primary-side heat equals the HEX duty.
* Mixer flow equals 140 m3/h.
* Injector flow equals producer flow (129.024 m3/h).
* Boiler and CHP efficiencies are exactly as parameterized (0.8).
* The injector reservoir (240 bar at 3100 m) is far below the ~304 bar hydrostatic column. That is why the
  injector wellhead pressure sits at the 1e-3 bar bracket floor.

### 3.2 `run_parallel_hex_plant_example.py`

```
Primary flow rate (well nodal balance): 125.10 m3/h ; ESP power_el 0.2431 MW
Degasser out P=9.8749 bar T=76.00 C ; Filter_1 out P=8.6232 bar T=75.00 C
hex_1/2/3: Q_primary 62.55/37.53/25.02 m3/h, T_primary_out 71.00 C, T_secondary_out 24.00 C
HEX mixer out Q=125.10 m3/h T=71.00 C ; Filter_2 out P=8.4973 bar T=70.00 C
Injector well P_wellhead=44.4702 bar ; Injector pump power_el=0.1563 MW, 1125 kg CO2/day
```

The `_assumptions` block says the injector injectivity (2.3 m3/h/bar) was *calibrated* to the measured
44 bar using the code as-is. Bug F3 below shifts that calibration.

### 3.3 Timing (`$SCR/bughunt/00_timing.py`)

| | build_project | one steady-state `solver.run()` | `run(range(100))` |
|---|---|---|---|
| doublet_plant.json | 0.04 ms | median **1.9 ms** | 1.5 ms/step |
| parallel_hex_plant.json | 0.02 ms | median **1.4 ms** | 1.5 ms/step |

The Solver re-evaluates a predecessor once per connection that it feeds. Per `run()`, the
`ProducerWell` nodal root-find runs 3x and `heat_exchanger` runs 6x. This only costs time.

### 3.4 Steady state versus time series (`$SCR/bughunt/09_timeseries_driver.py`)

* All registered components are `StaticModel` (algebraic). `Solver.run(time_vector)` loops over time
  points and calls `component.set_time(t)` on any component that defines it. No shipped component does.
  It also advances `DynamicModel` states (none is registered). Boundary inputs are constant. There is no
  profile or time-series driver, and no `dt` is passed to components. The physics is quasi-steady: no
  reservoir depletion, no thermal breakthrough, no wellbore thermal transient.
* Ways to drive an 8760-hour profile. The test uses a synthetic Dutch-like heat demand with a 7.8 MW
  peak and 28.8 GWh/yr, mapped onto the secondary flow of `doublet_plant.json`:

| Method | Wall time for 8760 h |
|---|---|
| A. Custom `ProfileSource(StaticModel)` with `set_time(t)`, registered with `COMPONENT_REGISTRY["profile_source"]=...` and wired as a predecessor. Then one `solver.run(time_vector=range(8760))`. | **10.7 s** (1.2 ms/h) |
| B. Python loop of `set_boundary_input(...)` plus `run([t])`. Only valid for static models, because `run()` re-initializes dynamic states on every call. | **10.3 s** |
| C. Demand-following: per hour, `brentq` on the secondary flow so that delivered heat equals demand. About 8.2 solves per hour. | 500 sampled hours in 4.8 s, so **about 1.4 min per 8760 h** |

* Memory: `run()` keeps every component's input and output dict for every step. The whole script peaked
  at about 200 MB RSS, which is fine for 8760 steps.
* Non-physical output passes silently. At low secondary flow, the boiler (fired by co-produced gas,
  independent of demand) heats the water to 102.8 °C. Nothing limits it.

---------------------------------------------------------------------------------------------------

## 4. Physics sanity checks (executed)

### 4.1 Heat exchanger (`$SCR/bughunt/01_heat_exchanger.py`)

| Check | Result |
|---|---|
| 600-case sweep with primary hotter (counter and parallel; UA 1e3–1e8 W/K; flows 1–300 m3/h) | 0 violations: ε ≤ 1, energy balance exact, no temperature cross |
| Continuity at Cr → 1 | smooth (ε 0.576396 → 0.576369 → 0.576380) |
| **Secondary inlet hotter than primary inlet** | **2nd-law violation.** Primary 20 → **−3.05 °C**, secondary 60 → **83.05 °C**, duty "4.24 MW" (counter). Cooling case: chilled primary 6 → **−0.71 °C**, building return 16 → **22.71 °C**. |

### 4.2 Heat pump `HeatpumpBasic` (`$SCR/bughunt/02_heatpump.py`, `$SCR/bughunt/02b_heatpump_grid.py`)

**Method.** I solved the *same* equations the model claims to solve: COP = η·Th/(Th−Ts) (Carnot form:
Th=Th_out, Ts=Ts_in; Lorenz form: log-mean temperatures), together with Qh = Qs + W. The reference uses a
closed form or a bracketed root (the physical branch). I compared it with the model over 1440 grid points
per mode: Th_in 30–60 °C, Th_target 60–90 °C, Ts_in 15–60 °C, flows 0.005–0.1 m3/s, η = 0.5,
Ts_min = 10 °C.

| Regime | n | max / median relative error of Q_cond | Fraction of points > 10 % wrong | Other |
|---|---|---|---|---|
| carnot, unconstrained (Ts_out ≥ Ts_min) | 705 | 0 / 0 | 0 % | OK (matches closed form to 1e-6) |
| **carnot, source-limited** | 557 | **980x / 33x** | **82 %** | Th_out ≈ 280–330 °C, COP ≈ 1.0 (spurious root of the fallback solve) |
| **lorenz, source-limited** | 695 | 2330x / 78x | 87 % | Th_out ≈ 630–710 °C |
| **lorenz, unconstrained** | 745 | 68x | 54 % (on W) | 153 points with COP ≤ 0; 434 points with energy balance > 1 % |
| carnot, Ts_in == Th_out_target | 48 | – | – | **ZeroDivisionError** |

A realistic cascade wired through the Solver (`$SCR/bughunt/13_heatpump_cascade.py`): the HEX primary
outlet (44.1 °C, 129 m3/h) is the heat pump source, the injection limit is Ts_min = 30 °C, and the sink is
45 → 75 °C at 80 m3/h. Shipped code: **COP 1.09, Th_out 311.4 °C, Q 24.8 MW, W 22.6 MW**. Correct
solution of the same equations: **COP 6.15, Th_out 72.2 °C, Q 2.52 MW, W 0.41 MW**.

The model is also missing from `COMPONENT_REGISTRY`. It must be registered at runtime to use it in JSON.

Modelling caveat: carnot mode uses Ts_in (the source *inlet*) in the COP formula. With a large source
glide this can exceed the reversible (log-mean) COP bound. That happened at 6 of 1440 grid points as
shipped, and at 246 once the root bug is fixed (all source-limited).

### 4.3 Boiler and CHP (`$SCR/bughunt/07_misc_components.py`)

| Check | Result |
|---|---|
| Boiler, 1 kg/s gas at 50 MJ/kg, η = 0.9 | power_th 45.000 MW; water-side heat 45.000 MW; CO2 10,188 kg/h (= 56.6 kg/GJ × 180 GJ/h) ✓ |
| Boiler at low water flow | No limits. T_out = 427 °C at 100 m3/h and 3734 °C at 10 m3/h. |
| CHP, η = 0.8 | Fixed electrical share of 1/3 of η·fuel: el 26.7 %, th 53.3 %, total 80 %. Plausible but hard-coded. |

### 4.4 Wells and reservoir (`$SCR/bughunt/04_wells.py`, `05_nodal_robustness.py`, `11_nodal_multiple_roots.py`, `12_brine_density.py`)

* DPDT single phase matches a hand calculation exactly. The case is 2500 m vertical, ID 0.2 m, k = 4.5e-5 m,
  water at 1000 kg/m3 and 1 mPa·s.
  * Friction: 0.86, 1.84 and 3.17 bar at 100, 150 and 200 m3/h.
  * Gravity: 245.25 bar.
  * Signs are correct for **production** (flow upward).
* **Injection.** Wellhead 20 bar, 150 m3/h. The correct bottomhole pressure is 263.41 bar. DPDT with
  `direction="down"`:
  * gives 263.41 bar with −Q (the convention used by gemini_framework, `calculate_bottomhole_pressure.py:61`);
  * gives **267.09 bar with +Q**, which is what `gemini_simulator.nodal_solver` passes. Friction is added
    instead of subtracted.
* Effect on the example projects (wellhead pressure and injector pump power; producer flow unchanged):

| Project | as-is | injection sign fixed |
|---|---|---|
| doublet_plant.json | 0.001 bar / 0 kW | 0.001 bar / 0 kW (gravity floor masks it) |
| parallel_hex_plant.json | 44.47 bar / 156.3 kW | **54.86 bar / 201.4 kW** (+23 % / +29 %) |
| derived 2500 m hydrostatic doublet (default roughness) | 1.52 bar / 4.5 kW | **24.75 bar / 151.3 kW** |

* Roughness. The default is **0.01 m (10 mm)** in metres in `well_flow.py`. DPDT comments and docs say
  "mm". Typical new steel is 4.5e-5 m. Friction over the example wells is **4.3–5.4x** higher than with
  4.5e-5 m (doublet producer 27.1 vs 5.6 bar; injector 35.0 vs 7.2 bar).
  * doublet_plant.json producer flow: **129.0 → 203.3 m3/h (+58 %)** with 4.5e-5 m.
  * ESP power: 174 → 194 kW.
  * The repo's legacy reference tests are matched *with* 0.01 m. So it may be an intentional calibration,
    but it is undocumented and physically implausible.
* **Non-physical nodal roots.** The default flow bracket is 0.01–700 m3/h. That is far past the ESP
  polynomial's valid range: for the doublet ESP, head turns negative near 290 m3/h and is 5704 bar at
  700 m3/h.
  * Case: 2500 m hydrostatic doublet, ID 0.2 m, PI 15, k = 4.5e-5. The residual has roots at **213.6,
    376.8 and 598.5 m3/h**. brentq returns **598.6 m3/h**, where the ESP head is 3312 bar, the efficiency
    is 3230 %, and the intake pressure is clamped to 0 bar (`nodal_solver.py:67`). No warning is given.
  * A 90-case sweep (freq 40–70 Hz, Pwh 3–20 bar, PI 5–30, two roughness values) on the shipped doublet
    gave no exceptions. Three cases had ESP efficiency above 100 % at 40 Hz (see 4.5).
* Wellbore temperature. The model uses explicit Euler per cell, U = 10 W/m²K is hard-coded, and ambient
  temperature is constant (no geothermal gradient). For a 2500 m producer at 50–200 m3/h:
  * 1 cell is within 2.3 K of the exact exponential solution; 25 cells within 0.1 K.
  * At 5 m3/h with 1 cell, it gives **−97.7 °C**.
  * The simulator's `ProducerWell` does not use the DPDT temperature: wellhead temperature is a boundary
    input. So this only matters for standalone DPDT use.
* PVT. The simulator's well path always uses `PVTConstantSTP()`: ρ = 1000 kg/m3, μ = 1e-3 Pa·s
  (`well_flow.py:120`). This cannot be set from JSON. Test case: a reservoir hydrostatic for 1080 kg/m3
  brine at 2500 m (p_res = 265.9 bar). The model then predicts **211 m3/h of natural (artesian) flow**
  at 3 bar wellhead pressure (true: 0). Injector Pwh at 150 m3/h is 28.8 bar versus 9.0 bar with a
  consistent density.
* IPR unit conversion is correct: (m3/h)/bar → (m3/s)/Pa divides by 3.6e8. `bottomhole_skin_dp` and
  `reservoir_pressure` regression are consistent by inspection (not in the simulator path).

### 4.5 Pumps (`$SCR/bughunt/06_esp_affinity.py`, `07_misc_components.py`)

* `InjectorPump`: 150 m3/h, 2 → 52 bar, η = 0.8 gives **260.4 kW**, equal to Q·ΔP/η ✓. It expects **Pa**,
  while separator, filter and booster emit **bar**. The doublet JSON correctly uses `pressure_out_pa`.
  Wiring bar into it gives watts instead of kilowatts.
* ESP: head in Pa, power in W, efficiency in % ✓. However, the **affinity law is misapplied**: the 60 Hz
  polynomial is evaluated at the actual Q instead of at Q·60/f.
  * At fixed Q, efficiency scales as 60/f. At 200 m3/h it is 105.8 % at 40 Hz, 84.6 % at 50 Hz, 70.5 %
    at 60 Hz and 60.5 % at 70 Hz.
  * At affinity-similar points the efficiency should be constant. The code gives 82.6 % at 40 Hz and
    61.6 % at 70 Hz. The fixed code gives 68.2 % at every frequency.
  * Producer nodal solve, code versus affinity-correct: flow differs by < 1 %, because this head curve is
    flat. **ESP power** differs by −19.9 % at 40 Hz, −14.8 % at 45 Hz, −9.7 % at 50 Hz, +4.3 % at 65 Hz
    and +8.2 % at 70 Hz.
* `BoosterPump`: P_out = P_in − Q·R with power 0. It is a passive resistance. The docs describe it the
  same way, but it never boosts and never consumes power, so it is a trap for network pumping energy.
* `Compressor` (not in the registry): 1 kg/s, R = 518, k = 1.3, 1 → 10 bar, one stage. The model gives
  **355.0 kW** against an isentropic hand calculation of 461.4 kW, a ratio of exactly 1/k. With 2 and 3
  stages it is also low by 1/k.

### 4.6 Unit conventions observed

| Component | Pressure | Temperature | Flow | Power / other |
|---|---|---|---|---|
| ProducerWell / InjectorWell (simulator) | bar (wellhead); `pressure_in` Pa | °C | m3/h (`flow_rate`), m3/s (`flow_rate_m3s`) | W, kg/s CO2 |
| DPDT / IPR / ESP | Pa | K | m3/s | ESP: Pa head, W, % |
| Separator / Filter / BoosterPump / HEX ΔP | any unit consistent with R (examples use bar with R in bar/(m3/s)); docs say Pa | °C or K (differences only) | m3/s | – |
| HEX / Boiler / CHP / KPI | – | °C | m3/s water, kg/s gas | W; ρ = 1050, cp = 4200 (consistent with each other) |
| HeatpumpBasic | bar (pass-through only) | °C in and out | m3/s | W; ρ = 1000, cp = 4181 |
| Well path PVT | – | – | – | ρ = 1000, μ = 1e-3 (fixed) |

### 4.7 Two-phase well path (only when PVT GMF > 0; default is 0)

`us_g = gmf/rho_g/A` (`pressure_drop.py:105`) uses the mass *fraction*. us_g therefore does not depend on
flow: 0.0016 m/s at every Q, against 0.02–0.13 m/s if computed from mg. Gas density is also the constant
STP value (1.976 kg/m3) at every pressure.

Results are erratic: at 50 m3/h, p_wh is 4.5 bar with GMF = 0 and 26.2 bar with GMF = 1e-4. At 150 m3/h
with GMF = 1e-3 it is 40.0 bar. With us_g fixed it is still erratic (78.1 bar), because of the constant gas
density. Do not use GMF > 0.

---------------------------------------------------------------------------------------------------

## 5. geoloop branch: borehole heat exchanger model (`src/gemini_model/bhe_geoloop/bhe_geoloop.py`)

* **What it is.** A `DynamicModel` wrapper around TNO's `geoloop` package (1.1.0; uses pygfunction 2.3.1,
  pydantic, xarray, netCDF4 and others). It simulates a deep or shallow vertical BHE: U-tube or coaxial,
  `model_type` ANALYTICAL by default. Parameters come from `input_files/bhe_config.json`:
  * geometry: H = 100 m, r_b, pipe positions and radii, SDR
  * thermal conductivities: k_p, k_g, k_s
  * ground: Tg = 10 °C, Tgrad, alfa
  * fluid: water
  * discretisation: nsegments, nled, nyear
  * optional optimisation of m_flow
* **Inputs.**
  * `mass_flow_rate` (kg/s) is always required.
  * TIN mode needs `inlet_temperature` (°C).
  * POWER mode needs `heat_load` or `heat_demand` (W).
* **Outputs.** `outlet_temperature`, `heat_extracted` (W), `pump_power` (W), `inlet_temperature`,
  `mass_flow_rate`, `mean_borehole_wall_temperature`, and fluid and wall temperature depth profiles.
* **Does it run?** Yes, on Python 3.12 only. Import takes 2.9 s.
  * Default TIN case (100 m, Tin 5 °C, 0.45 kg/s), step 1: T_out = 5.979 °C, Q_b = 1848 W, against
    m·cp·ΔT = 1842 W (0.3 % agreement). Pump power is 18 W.
  * After 40 steps: T_out 5.727 °C, Q_b 1372 W. The ground draws down plausibly.
  * POWER mode works: 3000 W load gives T_in 0.16 °C and T_out 1.75 °C.
* **Default time step.** The geoloop step is 360,000 s = **100 h** (`nled`: 100). Set `nled: 1` for hourly
  steps.
* **Problems (executed).**
  1. **History is double-stepped inside `gemini_simulator.Solver`.** `calculate_output()` calls
     `update_state()` (`bhe_geoloop.py:180`), which appends to the history. The Solver then calls
     `update_state()` again at the end of every step (`solver.py:148`). Result: 5 solver steps produce 10
     history entries, so the BHE "time" runs at least 2x faster than the solver clock (one extra step per
     connection that reads it).
  2. **O(N²) cost.** The full history is re-simulated on every step. Per-step time grows 43 → 615 ms over
     40 steps. With hourly steps, 200 steps took **218 s**. A full 8760-hour year extrapolates to roughly
     4–5 days, which is infeasible.
  3. Not registered in `COMPONENT_REGISTRY`. The JSON config path is hard-coded (a TODO in the code).
     `Solver.run()` re-initialises dynamic states on every call, so a Python loop of `run([t])` calls
     would wipe its memory. Use one `run(time_vector)` with a profile source instead.

---------------------------------------------------------------------------------------------------

## 6. FATAL bug list

Classes: (a) crash, (b) physics/unit/sign error > ~10 %, (c) silent non-converged/garbage result,
(d) balance not closing. **C = confirmed by execution**; S = suspected from reading only. All items below
are C.

### F1. HeatExchanger moves heat from cold to hot when the secondary inlet is the hotter stream. (b, d) **C**
* **Where.** `src/gemini_model/heat_exchanger/heat_exchanger.py:107`
  (`heat_duty_max = capacity_min * abs(T_s_in - T_p_in)`), applied with fixed signs at lines 125–126.
* **Repro.** `PYTHONPATH=src python $SCR/bughunt/01_heat_exchanger.py`. Primary 20 °C and secondary 60 °C
  (150/150 m3/h, UA 250 kW/K) give primary → −3.05 °C and secondary → 83.05 °C. Chilled water 6 °C against
  a 16 °C return gives −0.71 °C and 22.71 °C.
* **Impact.** Any district *cooling* loop, heat rejection, or a case where the return is hotter than a
  cooled geothermal primary. Duty has the wrong sign and outlet temperatures are off by tens of K.
* **Fix.** Use the signed ΔT: `heat_duty_max = C_min*(T_p_in - T_s_in)`
  (`$SCR/bughunt/patches/01_heat_exchanger_signed_duty.diff`). Verified: 20 → 43.05 °C and 60 → 36.95 °C.

### F2. HeatpumpBasic returns a spurious root or garbage, and crashes at Ts_in == Th_out_target. (a, c, d) **C**
* **Where.** `src/gemini_model/heatpump/heatpump_basic.py:273–305`. Nelder-Mead on a sum of |residuals|,
  with no bounds and no check of convergence or residual. The fallback starts from
  `x0=[COP_0, Th_out]` (line 287) and lands on the high-temperature root. Lines 242 and 266 divide by
  zero.
* **Repro.** Run `$SCR/bughunt/02b_heatpump_grid.py` (grid statistics in section 4.2) and
  `$SCR/bughunt/13_heatpump_cascade.py`. In the cascade: COP 1.09, Th_out 311 °C, Q 24.8 MW, W 22.6 MW.
  The correct values are COP 6.15, Th_out 72.2 °C, Q 2.52 MW, W 0.41 MW.
* **Impact.** Any heat-pump-assisted design. A source-limited heat pump (the usual case when the
  re-injection temperature is constrained) gives heat 10–1000x too high and electricity 100–10,000x too
  high. Lorenz mode is wrong in about half of normal cases.
* **Fix.** Closed form for Carnot, plus brentq bracketed on (Th_in, Th_target] for the source-limited case
  and on (Ts_min, Ts_in) for Lorenz (`$SCR/bughunt/patches/04_heatpump_bracketed_root.diff`). Verified on
  the full grid: errors 1e-13, no exceptions. Also register it (`COMPONENT_REGISTRY["heatpump"]`).

### F3. Injection-well friction has the wrong sign in the simulator. (b) **C**
* **Where.** `src/gemini_simulator/nodal_solver.py:150` passes `+flow_rate` with `direction="down"`.
  DPDT (`pressure_drop.py:153`) adds `dp_fric`, because its convention is +Q = upward flow. The framework
  passes −Q.
* **Repro.** `python $SCR/bughunt/04_wells.py $SCR/work/gemini-dev`. Bottomhole pressure is 267.09 bar
  against the correct 263.41 bar. The injector wellhead pressure and injector pump power change as listed
  in section 4.4 (parallel-HEX example and derived hydrostatic doublet).
* **Impact.** Injector pump pressure is under-predicted by 2x the tubing friction. That is +23 % to 33x
  on pump pressure and power, depending on the case. It is masked when gravity alone over-delivers, as in
  doublet_plant.json. The parallel-HEX example's calibrated injectivity index (2.3) is biased by it.
* **Fix.** Pass `"flowrate": -flow_rate` (`$SCR/bughunt/patches/02_injection_friction_sign.diff`).
  Better: make the DPDT direction semantics explicit.

### F4. The producer nodal solve can silently return a non-physical root. (c) **C**
* **Where.** Default flow bracket `(0.01, 700)` m3/h at `well_flow.py:129` and `well_components.py:92`,
  far beyond ESP-curve validity. 6th-order polynomial extrapolation in `esp.py`. The ESP intake pressure
  is clamped to 0 at `nodal_solver.py:67`. Plain `brentq` at `nodal_solver.py:137`.
* **Repro.** `python $SCR/bughunt/11_nodal_multiple_roots.py $SCR/work/gemini-dev`. Roots at 213.6, 376.8
  and 598.5 m3/h. The solver returns 598.6 m3/h with ESP head 3312 bar, efficiency 3230 %, and the intake
  clamped.
* **Impact.** Flow is 2.8x too high, and ESP power is about 1.7 MW instead of about 0.2 MW, with no
  warning. The trigger is any low-friction or high-PI well, which is what an optimizer will look for.
* **Fix.**
  * Bracket the flow to where the ESP head is > 0, or to `[min_flow, max_flow]·f/60`.
  * Raise or flag when the intake would go below about 1 bar instead of clamping.
  * Scan for the smallest sign change.

### F5. ESP affinity law misapplied. (b) **C**
* **Where.** `src/gemini_model/pump/esp.py:73` and `:83`. The code uses (f/60)²·H60(Q) and
  (f/60)³·P60(Q). The correct forms are (f/60)²·H60(Q·60/f) and (f/60)³·P60(Q·60/f). The docs show the
  same wrong formula.
* **Repro.** `python $SCR/bughunt/06_esp_affinity.py $SCR/work/gemini-dev`. Efficiency is 105.8 % at
  40 Hz. ESP power from the nodal solve is −20 % at 40 Hz, −15 % at 45 Hz and +8 % at 70 Hz.
* **Impact.** ESP electricity and efficiency, and therefore the plant's net power and emissions, under
  VFD frequency control (what an agent would tune). Flow was < 1 % off for this pump, but it would be
  larger for steep head curves.
* **Fix.** `$SCR/bughunt/patches/05_esp_affinity_flow_scaling.diff`. Verified: efficiency is 68.2 % at
  40, 50, 60 and 70 Hz on affinity-similar points. The legacy-reference tests will need new values.

### F6. Recycle loops are not converged, and nothing says so. (c) **C**
* **Where.** `src/gemini_simulator/solver.py:118–152`: one sequential sweep per time step, with no
  iteration or residual check.
* **Repro.** `python $SCR/bughunt/08_solver.py $SCR/work/gemini-dev`. A closed secondary loop (HEX → 15 K
  consumer → HEX) gives a duty of 3.383 MW after one `run()`, against 2.756 MW converged (+23 %). It takes
  about 20 sweeps to converge.
* **Impact.** Any district heating or cooling network modelled with return-temperature feedback. The
  shipped examples avoid loops by fixing the return temperature as a boundary input.
* **Fix.** Wrap `run()` in a fixed-point loop with a tolerance on the inputs of torn connections, or
  document "no loops" and raise on cycles.

### F7. Compressor power is low by a factor k. (b) **C**, off the DH critical path
* **Where.** `src/gemini_model/compressor/compressor.py:83` uses `n*m*R*T1/(k-1)*(...)`. It should be
  `n*m*k/(k-1)*R*T1*(...)`.
* **Repro.** `PYTHONPATH=src python $SCR/bughunt/07_misc_components.py`. The model gives 355.0 kW against
  461.4 kW by hand: −23 % at k = 1.3, −29 % at k = 1.4.
* **Fix.** `$SCR/bughunt/patches/06_compressor_k_factor.diff`. Verified to match the hand calculation for
  1, 2 and 3 stages.

### F8. geoloop BHE is double-stepped in the Solver and costs O(N²). (c, plus infeasible run time) **C**
* **Where.** `bhe_geoloop.py:180` (`calculate_output` → `update_state`) together with `solver.py:148`.
  `update_state` re-runs `SingleRun` over the whole history on every call.
* **Repro.** `PYTHONPATH=$SCR/work/gemini-geoloop/src $P312 $SCR/bughunt/10_geoloop_bhe.py`, run from an
  empty directory. 5 solver steps produce 10 history entries. 200 hourly steps take 218 s.
* **Impact.** BHE temperatures are reported at the wrong time (2x fast). An annual hourly simulation is
  infeasible (days).
* **Fix.**
  * Make `calculate_output` side-effect-free: compute from history plus the current input without
    appending, and only append in `update_state`.
  * Use geoloop's load-history superposition incrementally, or a coarser `nled`.
  * Register the component.

### F9. Two-phase well path is unusable. (b, c) **C**, only if GMF > 0
* **Where.** `src/gemini_model/well/pressure_drop.py:105` (`us_g = gmf/...` should be `mg/...`), together
  with constant STP gas density in `PVTConstantSTP`.
* **Repro.** `07_misc_components.py`, last block. p_wh jumps 4.5 → 26 bar with GMF = 1e-4.
* **Fix.** `$SCR/bughunt/patches/07_dpdt_two_phase_usg_and_roughness_unit_comment.diff` fixes us_g only.
  The gas PVT is still needed. Until then, keep GMF = 0.

### F10. Roughness: default and units. (b) **C** for the sensitivity; S for whether it is a "bug"
* **Where.** The default `0.01` m (10 mm) is at `src/gemini_simulator/well_flow.py:101, 197, 274, 362`.
  `pressure_drop.py:55` and `model_well_hydraulics.rst` say the unit is "mm".
* **Repro.** `04_wells.py`, blocks C/D and D2.
  * Friction is 4.3–5.4x higher than for steel at 4.5e-5 m.
  * doublet_plant.json flow is 129 → 203 m3/h (+58 %) and ESP power 174 → 194 kW when the realistic value
    is set.
  * A user who follows the docs and enters 0.045 (meaning mm) gets 45 mm.
* **Status.** The repo's legacy reference tests are reproduced *with* 0.01. So this looks like an
  undocumented calibration.
* **Fix or advice.** Always set `roughness_m` explicitly in metres, and fix the "(mm)" comment and docs.
  The optional default change is in `$SCR/bughunt/patches/03_roughness_default_4p5e-5m.diff`.

### Coordinator's suspect list (each run)

| # | Suspect | Verdict |
|---|---|---|
| 1 | Injector friction sign | **CONFIRMED** = F3. doublet_plant.json unchanged (0.001 bar, 0 kW) because the injector is in the gravity-floor regime. parallel_hex: +23 % wellhead pressure, +29 % pump power. |
| 2 | Roughness default | **CONFIRMED** large sensitivity = F10. 4.3–5.4x friction; +58 % flow; ESP +11 %. |
| 3 | HeatExchanger direction | **CONFIRMED** = F1. |
| 4 | HeatpumpBasic | **CONFIRMED** = F2. Matches the closed form when unconstrained. Not in the registry (confirmed). |
| 5 | Compressor | **CONFIRMED** = F7 (factor exactly 1/k). |
| 6 | Two-phase us_g | **CONFIRMED** = F9. It changes results (40 → 78 bar at GMF = 1e-3 and 150 m3/h), but the path is non-physical either way. |

---------------------------------------------------------------------------------------------------

## 7. Material limitations and traps (not counted as code bugs)

* **L1. Well-path fluid is fresh water at 20 °C** (ρ = 1000, μ = 1e-3) and cannot be configured from JSON
  (`well_flow.py:120`). Saline-aquifer cases need the reservoir pressure specified relative to a
  1000 kg/m3 column. Otherwise you get fictitious artesian flow (section 4.4: 211 m3/h). There is no
  hot/cold column density (thermosiphon) effect.
* **L2. No reservoir or wellbore thermal model in the simulator path.** Producer wellhead temperature is a
  fixed input. There is no breakthrough, depletion or transient.
* **L3. `BoosterPump` never boosts and uses 0 W.** Boiler and CHP have no outlet-temperature limits. The
  CHP electrical share is fixed at 1/3.
* **L4. Registry gaps.** There is no heat pump, compressor, BHE, demand or consumer, or cooling component.
  The registry is a plain dict, so runtime registration works (`$SCR/bughunt/13_heatpump_cascade.py`).
* **L5. Unhelpful crash when no root exists.** For example, producer Pwh 60 bar raises
  `ValueError: f(a) and f(b) must have different signs`. A randomly shuffled connection order raises
  `KeyError` (it is not silent). The solver needs topologically ordered connections.
* **L6. Mixed units.** bar and Pa share one chain, as do m3/h and m3/s. The KPI module reads hard-coded
  component names (`water_mixer`, `filter_a`, and so on).
* **L7. `example_dataset.csv`.** 17,280 rows at 15-minute steps, 2024-06-07 to 2024-12-03, 32 columns of
  doublet operating data: Pwh about 10 bar, Qp 143–149 m3/h, T_p_in 80 °C, ESP 55–60 Hz, injector pump
  45–52 bar, thermal 8.7–10.9 MW. It is consistent with ρ·cp = 1050·4200 to 1e-5 and all statuses are
  "Normal". It looks synthetic, generated by the legacy model. It is useful for calibration and
  validation, but it is not the doublet_plant.json parameter set.

---------------------------------------------------------------------------------------------------

## 8. Files

* Scripts: `$SCR/bughunt/00_timing.py` … `13_heatpump_cascade.py`. Most take the tree path as argument or
  use `PYTHONPATH=<tree>/src`.
* Captured outputs: `$SCR/bughunt/outputs/*.out`. These include `fixed_tree_checks.out` and
  `fixed_tree_examples.out`, from the patched tree (doublet: 210.7 m3/h, 6.670 MW; parallel-HEX injector:
  54.86 bar, 201 kW).
* Patches, which apply cleanly to `development` with `patch -p1 --binary`:
  `$SCR/bughunt/patches/01…07_*.diff`.
* Environments: `$SCR/envs/gemini311` (models, simulator and tests) and `$SCR/envs/gemini312` (geoloop).
