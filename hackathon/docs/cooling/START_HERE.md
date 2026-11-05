# Dioscuri: start here (Ali)

Welcome to the team repo. This file gets you from nothing to a working setup, and covers four
things: the challenge, your part of the work, how your code plugs into the agent, and a few
choices we should agree on together. Section 8 covers trying your own ideas on separate
branches.

## 1. Get the repo

The repo is private on GitHub: `rezanajafisilab/dioscuri`. It is a mirror of TNO's GEMINI
(`development` branch, version 1.0.3, released 29 Oct) plus our team folder `hackathon/`.

1. Accept the GitHub invite (you get it by email, or at github.com/rezanajafisilab/dioscuri).
2. Clone the repo and add GEMINI as a second remote:

   ```bash
   git clone https://github.com/rezanajafisilab/dioscuri.git
   cd dioscuri
   git remote add upstream https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open.git
   ```

3. Work from `main`. The `rn/*` branches are Reza's agent and UI work in progress. You don't need
   them; your code talks to the agent only through the interface in section 5.

## 2. Install

You need Git, Python 3.12 (GEMINI needs < 3.13), and about 10 minutes. The models and the simulator
need only numpy and scipy.

**Linux or macOS**

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r hackathon/requirements-dev.txt
pre-commit install
export PYTHONPATH=src
pytest -q unit_test/gemini_model unit_test/gemini_simulator     # 91 passed
python simulator_examples/run_doublet_plant_example.py          # GEMINI's doublet plant
```

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r hackathon\requirements-dev.txt
pre-commit install
$env:PYTHONPATH = "src"
pytest -q unit_test\gemini_model unit_test\gemini_simulator
python simulator_examples\run_doublet_plant_example.py
```

Conda works too: `conda create -y -n dioscuri python=3.12`, then the same `pip` line.

`pre-commit` runs black, isort and flake8 (with numpydoc docstrings), the same rules as GEMINI's CI.
Our CI runs them, plus the tests, on every pull request into `main`.

Later, your laptop doubles as the judges' machine (CPU only). For that test we will also install
Ollama and the local models. That isn't needed for your models now.

## 3. The challenge in one page

The organisers' files are `GEMINI_Hackathon_Challenge_Requirements.docx.pdf`,
`GEMINI_Heating_Demand_Daily_2027.csv` and `GEMINI_Cooling_Demand_Daily_2027.csv`. Put them in
`hackathon/data/raw/challenge/`; that folder is git-ignored, so they are not committed.

| | Value |
|---|---|
| Heat demand | daily 2027, 111.67 GWh/yr, peak 30.0 MW on 28 Jan, minimum 2.7 MW, about 3.4 MW in summer |
| Cooling demand | daily 2027, 23.74 GWh/yr, peak 10.0 MW on 19 Jul, 219 days with cooling (all of them also need heat) |
| Reservoir | midpoint 2,500 m TVD, 100 m thick, 30 °C/km from 12 °C (so 87 °C), 250 bar(g), 200 mD (k·h = 20 D·m) |
| Brine | 1,030 kg/m³, 0.40 mPa·s (constants); gas–liquid ratio 0.8 Nm³/m³, gas 80 % CH₄ / 20 % CO₂ |
| Doublets | 1 to 3 (a design variable), same reservoir, equal production and injection volumes |
| Flow per doublet | 50 to 300 m³/h while running (hard caps) |
| Brine cooling | at most 40 °C from producer to injector (hard cap) |
| Pumps | 70 % hydraulic efficiency |
| Operation | 330 daily steps a year, with a daily power and energy balance |
| Supply temperatures | heating 100 °C, cooling 20 °C (fixed) |

What it means for the design:

- **100 °C supply.** 87 °C brine can only preheat the network (to about 80 °C), so every design
  needs a top-up to 100 °C: a high-temperature heat pump, a boiler or a CHP.
- **Peak.** One doublet at 300 m³/h and 40 K gives about 13.7 MW (with cp ≈ 4.0 kJ/kg·K), so the
  30 MW peak needs 2 to 3 doublets or a large top-up.
- **Produced gas.** At 300 m³/h the wells also produce about 240 Nm³/h of gas, roughly 1.9 MW of
  methane fuel, which can feed the boiler or a CHP. Its CO₂ counts, including the 20 % that is
  already CO₂.
- **20 °C cooling.** This is easy for absorption chillers and very efficient for electric chillers.
  It also makes a heat pump that takes heat from the cooling network and delivers it at 100 °C
  attractive.

The task wording: "build an agentic AI orchestration workflow that uses GEMINI for applicable
subsurface/well-engineering evaluations and complementary component models for heating and
cooling … generate system configurations, run engineering checks, detect violations, and iteratively
improve a proposed design", and "explain every major engineering decision".

## 4. Your part

**Split.** Reza builds the agent, the user interface, the GEMINI well and doublet solve (with our
fixes for the GEMINI bugs), the checks and the evaluation. You build the energy system around the
wells:

1. **The plant over the year** (daily, 365 steps). Given a design, the demand and a doublet model, it
   decides each day what runs. It covers:
   - doublets on and off, at 50 to 300 m³/h;
   - 330 operating days;
   - brine cooled by at most 40 K;
   - heating preheated by the brine, then topped up to 100 °C;
   - cooling at 20 °C.

   It returns each day's power by source, electricity and gas use, CO₂, and every broken hard cap.
2. **Component models**, in GEMINI's style: an absorption chiller at 20 °C supply, an electric
   chiller, a high-temperature heat pump (top-up to 100 °C, and the mode that takes heat from the
   cooling network), and the produced gas with its CO₂. GEMINI's own boiler and CHP models can burn
   the gas.
3. **Economics with sourced numbers.** This means capital, running costs, the cost of heat and of
   cold, the comparison with a gas boiler and electric chillers, and CO₂. Every price and cost needs
   a source (for example the Danish Energy Agency technology catalogue for heat pumps, boilers and
   geothermal plants).
4. **Checks against hand calculations** for each model and for one full year. These are evidence for
   the report.
5. **Later:**
   - interference between doublets in the same reservoir, and well spacing;
   - your spare-equipment idea (`hackathon/docs/spare_equipment.md` on Reza's design branch; he can
     send it);
   - the Windows CPU install test;
   - the system sections of the report.

## 5. How your code plugs into the agent

The agent calls your code as ordinary Python functions. It changes nothing when your version
replaces the stand-in it uses today.

### Where the code goes

| Code | Path | Tests |
|---|---|---|
| Component models (upstreamable to GEMINI) | `src/gemini_model/<name>/`, as GEMINI's models | `unit_test/gemini_model/<name>/` |
| The plant over the year and economics (ours, challenge-specific) | `src/dioscuri_plant/` (new package) | `unit_test/dioscuri_plant/` |

Component models follow GEMINI's `StaticModel` pattern, the same shape as `src/gemini_model/boiler/`:
- a `parameters` dict;
- `calculate_output(u, x)`;
- outputs including `power_th`, `power_el` and `emission`;
- numpydoc docstrings;
- an `.rst` page in `src/gemini_documentation/source/` if we want to offer it upstream.

Please don't edit GEMINI's existing models. We keep fixes for its bugs as patches in
`hackathon/gemini_bughunt/patches/`.

The team CI tests only the GEMINI folders today. Add `unit_test/dioscuri_plant` to the test paths in
`.github/workflows/team-ci.yaml` in your first pull request.

### The interface (the names matter; add fields freely, never rename)

Use plain dataclasses, so nothing beyond numpy and scipy is needed. Put the units in the names
(`_c`, `_k`, `_mw`, `_gwh`, `_m3h`, `_bar`, `_meur`, `_eur_per_mwh`).

```python
# src/dioscuri_plant/__init__.py
def simulate_year(plant: Plant, demand: Demand, doublet: DoubletModel, rules: Rules = Rules()) -> YearResult: ...
def economics(plant: Plant, year: YearResult, prices: Prices = Prices()) -> Economics: ...
def stub_doublet(flow_m3h: float, depth_m: float) -> dict: ...   # simple physics for your tests
```

```python
@dataclass
class Rules:            # the challenge's fixed inputs and hard caps (defaults = the PDF)
    heat_supply_c: float = 100.0
    heat_return_c: float = 60.0          # not given: our assumption, see section 6
    cool_supply_c: float = 20.0
    cool_return_c: float = 25.0          # not given: our assumption, see section 6
    flow_min_m3h: float = 50.0
    flow_max_m3h: float = 300.0
    max_brine_cooling_k: float = 40.0
    operating_days: int = 330
    pump_efficiency: float = 0.70
    brine_density_kg_m3: float = 1030.0
    brine_viscosity_pa_s: float = 0.40e-3
    brine_cp_j_kg_k: float = 3950.0      # not given: our choice, cite a source
    gas_liquid_ratio: float = 0.8        # Nm³ gas per m³ liquid
    gas_ch4_fraction: float = 0.80
    gas_co2_fraction: float = 0.20

@dataclass
class Plant:            # one design: what the agent varies
    n_doublets: int                      # 0 (gas reference) to 3
    depth_m: float = 2500.0
    hex_approach_k: float = 5.0
    heat_pump_mw: float = 0.0            # top-up heat pump, heat output
    recovery_heat_pump_mw: float = 0.0   # takes heat from the cooling network
    absorption_mw: float = 0.0           # cold output, driven by brine
    chiller_mw: float = 0.0              # electric chillers, cold output
    boiler_mw: float = 0.0               # heat output
    chp_mw_el: float = 0.0               # electrical output
    burn_produced_gas: bool = True
    stop_start_day: list[int] | None = None   # per doublet; None lets the model choose

@dataclass
class Demand:
    heat_mw: list[float]                 # 365 daily means
    cool_mw: list[float]
    # Demand.from_csv(heat_csv, cool_csv) reads the organisers' files

DoubletModel = Callable[[float, float], dict]
# doublet(flow_m3h, depth_m) -> {"wellhead_c", "esp_mw", "injector_pump_mw", "gas_nm3h"}
# Reza provides the GEMINI-backed one; use stub_doublet until then.
```

`YearResult` and `Economics` keep the names the agent and the user interface already read. Here
`geo` is the heat from the brine, `hp` the top-up heat pump, `recovery_hp` the recovery heat pump,
`abs` absorption and `chill` the electric chillers.

| `YearResult` field | Meaning |
|---|---|
| `heat_demand_gwh`, `cool_demand_gwh`, `heat_delivered_gwh`, `cool_delivered_gwh` | yearly totals |
| `heat_coverage`, `cool_coverage` | 0 to 1 |
| `heat_split_gwh` | `{"geo", "hp", "recovery_hp", "boiler", "chp"}` |
| `cool_split_gwh` | `{"abs", "chill", "recovery_hp"}` |
| `peak_heat_mw`, `peak_cool_mw` | |
| `daily_mw` | `{"heat": {"demand", "geo", …}, "cool": {"demand", "abs", …}}`, 365 values each |
| `monthly_gwh` | the same keys, 12 values |
| `doublets` | per doublet: `{"flow_m3h": [365], "on": [365], "reinjection_c": [365]}` |
| `electricity_gwh` | `{"hp", "recovery_hp", "chillers", "pumps"}` |
| `purchased_gas_gwh`, `produced_gas_burned_gwh`, `produced_gas_flared_gwh` | |
| `co2_t` | `{"purchased_gas", "produced_gas", "electricity", "total"}` |
| `violations` | one plain sentence per broken hard cap, with the day and the value |
| `source` | for example `"dioscuri_plant 0.1"`, shown next to every number in the app |

`Economics` has:
- `lcoh_eur_per_mwh` and `lcoc_eur_per_mwh`;
- `capex_meur`;
- `lines`: a list of `(item, kind, meur_per_year)` that adds up to the costs;
- `capex_items`;
- `co2_saving_vs_gas`;
- `assumptions`: each value with its source.

### What makes it work well with the agent

- **Pure functions.** No file or network access, no global state, the same output for the same
  input.
- **Report, don't raise.**
  - Put broken hard caps in `violations`. The agent reads them, explains them, and tries the next
    design.
  - Raise `ValueError` only for inputs that make no sense, such as `n_doublets=5`.
- **Fast.** A year should take well under 50 ms. The agent runs hundreds of them for comparisons,
  sensitivity and its own design search.
- **No hidden numbers.** Every constant sits in `Rules`, `Prices` or a model's `parameters`, with
  its source in a comment.
- **A balance every day.** Heat and cold delivered equal what the sources give, within 0.1 %, and the
  tests check it.

## 6. Choices to agree on together

The organisers didn't give these, so we decide, write down why, and let the Sensitivity tab show
how much each matters.

- **Heating return temperature.** `60 °C` is a typical return for a 100 °C network. It sets how
  much heat the brine can give before the top-up. Should we test 50–70 °C?
- **Cooling return temperature.** `25 °C`? Which value best fits 20 °C high-temperature cooling?
- **Brine heat capacity.** About 3.9–4.0 kJ/kg·K for a brine of 1,030 kg/m³. Which source should we
  cite?
- **Top-up to 100 °C.** Heat pump, boiler on the produced gas, CHP, or a mix? This is likely the
  design's main decision.
- **The 35 days off.** Do the doublets stop at the same time or one after another, and in which
  weeks?
- **Produced gas.** Burn it on site and count its CO₂, or flare it? Burning it is our current view.
- **Interference.** Model it now, or check spacing first and model it if there is time?

Reza will ask the organisers about the return temperatures and the exact meaning of "330 daily
steps". We decide everything else ourselves and state it in the report.

## 7. Working together

- **Branches.** Use branches like `ali/plant-dispatch` or `ali/model-absorption-chiller` for the
  tasks in section 4, and open a pull request into `main` when a piece works. Reza reviews and
  merges. Your own ideas go on `ali/idea-…` branches instead (section 8).
- **Interface changes.** Ask before renaming anything in the interface above. Adding a field is
  always fine.
- **Older documents.** `hackathon/TEAM_WORKFLOW.md` has more detail on pull requests, and
  `hackathon/docs/cooling_design.md` has earlier notes on the cooling models. Both predate the
  challenge files, so this page wins where they differ.

## 8. Your own ideas

Ideas beyond section 4 are welcome: the spare-equipment analysis, a different plant layout, a
better dispatch rule, a new chart for the report. Keep each idea on its own branch, separate from
the task branches, so a task merge never waits on an experiment, and write down what each one is.
That way Reza can see at any time what exists and what is ready to merge.

**1. One branch per idea, always from `main`.**

```bash
git switch main && git pull
git switch -c ali/idea-spares          # ali/idea-<short-name>
```

Don't build an idea on top of a task branch, or a task on top of an idea. If an idea needs a task
that hasn't been merged yet, write that under "Needs" on its card (below).

**2. Put a card in the branch: `hackathon/ideas/<short-name>.md`.** One file per idea, so idea
branches never conflict with each other. Copy this and fill it in:

```markdown
# Idea: <one line>

- **Status:** exploring | works | dropped
- **Merge?** not yet | ready | needs a decision from Reza | no
- **Branch:** ali/idea-<short-name>
- **Needs:** nothing | <other branch or task that must merge first>
- **Touches:** new files only | changes existing files (list them) | changes the interface in section 5

## Why
What it would change: LCOH, CO2, cooling coverage, risk, the score, the report. One paragraph.

## What it does
A few lines on the method, with sources for any numbers taken from outside the challenge files.

## How to try it
The one command that shows it working, and what you should see.

## Results so far
Numbers, a table or a chart. Note what is still a guess.

## Open questions
What you'd like Reza or the organisers to decide.
```

**3. Open a draft pull request early**, as soon as the branch has its card, even before the idea
works. Give it the title `Idea: <one line>` and the label `idea`, and link the card in the
description:

```bash
git add hackathon/ideas/spares.md && git commit -m "Idea: N+1 spare equipment, card"
git push -u origin ali/idea-spares
gh pr create --repo rezanajafisilab/dioscuri --draft --base main --label idea \
  --title "Idea: N+1 spare equipment" --body "Card: hackathon/ideas/spares.md"
```

Always pass `--repo rezanajafisilab/dioscuri` to `gh`. Your clone also has the GEMINI
`upstream` remote, and `gh` may otherwise open the pull request there.

On the website, choose "Create draft pull request" and add the `idea` label on the right.

**4. Keep the card current.** Update Status, Merge? and Results whenever you push. When the idea is
ready, set `Merge?: ready` and click "Ready for review" on the pull request. If you drop it, set
`Status: dropped` with one sentence on why, close the pull request, and keep the branch. A dead end
is still worth a line in the report.

**5. A few rules.**
- Don't rename or remove anything in the interface in section 5 on an idea branch. If an idea
  needs an interface change, say so under "Touches" and we'll agree on it first.
- Keep idea code in new files where you can (for example `src/dioscuri_plant/spares.py`), so it can
  merge without touching your task code.
- Tests for an idea go in `unit_test/dioscuri_plant/` like the rest, and should pass before you
  set `Merge?: ready`.

To see every idea and its state, list the pull requests with the `idea` label:
<https://github.com/rezanajafisilab/dioscuri/pulls?q=label%3Aidea>, or run
`gh pr list --repo rezanajafisilab/dioscuri --label idea --state all`.
