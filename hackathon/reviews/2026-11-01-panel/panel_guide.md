# Review panel guide (round 2, 1 Nov): stress the Dioscuri agent and say what is missing

You are one member of a review panel. Each member has a role. Use the running agent as a real
user in your role would, push it where your expertise says it is weak, and report what you find.

## What Dioscuri is

Dioscuri is an agentic AI built by team Dioscuri for the SPE GeoHackathon 2026 ("GEMINI agentic
geothermal design hackathon", deadline 3-4 Nov 2026). It designs a deep-geothermal heating and
cooling system for a district, using TNO's GEMINI digital twin (an open-source Python geothermal
simulator) for the wells and its own plant model for the year. It runs only on local open-weight
models (Ollama: qwen3:1.7b reads each message, qwen3.5:9b on the GPU / qwen3.5:4b on the CPU
reasons and writes replies). No commercial model APIs: that is a hard rule of the team.

The organisers' challenge (their requirements PDF, 28 Oct 2026):
- daily heat demand for 2027: 111.67 GWh, peak 30 MW (28 Jan); daily cooling demand 23.74 GWh,
  peak 10 MW (19 Jul); supply temperatures fixed: heating 100 °C, cooling 20 °C;
- one reservoir: midpoint 2,500 m TVD, 100 m gross thickness, 30 °C/km from 12 °C (so 87 °C),
  250 bar(g), 200 mD; "for selecting different geothermal well depth, you can use hydrostatic
  pressure for reservoir pressure and estimate reservoir temperature based on the gradient";
- brine 1,030 kg/m³, 0.40 mPa·s; gas-liquid ratio 0.8 Nm³/m³, gas 80 % CH4 / 20 % CO2;
- hard caps: 1-3 doublets; 50-300 m³/h per doublet while running; brine cooled by at most
  40 °C producer to injector; pumps 70 % efficient; production = injection volume; "annual
  operation 330 daily steps" (read as at most 330 days a year per doublet; asked of the
  organisers, no answer yet); daily power and energy balance;
- the agent must interpret the demand, generate configurations, run engineering checks, detect
  violations, iteratively improve a design and explain every major decision. GEMINI is not an
  end-to-end optimiser: the agent is.

Not given (Dioscuri assumes and says so): network return temperatures (60 °C heating, 25 °C
cooling), brine heat capacity (3,990 J/kg·K), prices (Eurostat 2025 NL), well spacing (1.5 km),
porosity (0.20), the cost of a treatment train.

## What changed since the 31 Oct panel (round 1)

Round 1's twelve reports are in `hackathon/reviews/2026-10-31-panel/` (read the one for your
role, and the README's priorities). Since then:

- **Costs** recalibrated: ThermoGIS v3 surface plant (3.5 M€ + 882 €/kW) and PBL SDE++ 2026
  fixed O&M (121 €/kW/yr). The cheapest design is now one doublet.
- **Four picks** per search: cheapest (lowest cost of heat and cold), lowest CO2 (cheapest within
  2 % of the least), most reliable (cheapest *reliable plan*), and **best overall** (the reliable
  plan that is cheapest with CO2 at PBL's long-term 137 €/t) — the default recommendation. A
  *reliable plan* (code suffix `-N1`) has the boiler and electric chillers as 3 equal units, grown
  until any one unit out (a doublet/ESP, a shared treatment train, the heat exchanger, the heat
  pump, a boiler or chiller unit, the absorption chiller) leaves every day met.
- **Failures** on dates: "what if the ESP of doublet 1 fails from 10 to 24 January?", "the heat
  pump breaks down for two weeks" (the worst start in the year is found), "if we lose a pump"
  (all year). The answer gives what is not delivered and runs each remedy through the same days
  (more boiler or chillers, a standby twin, a spare ESP back after 3 days) with its cost. A
  FAILURE card shows it.
- **Comparisons by code** (COMPARE card): every figure from the designs' runs, best of each row
  marked. **Requests of several steps** ("design it, then check it 10 °C colder, and tell me if
  the pick changes"): the reasoning model reads up to 3 steps in the same call that reads the
  changes; code checks and runs them.
- **Subsurface checks** per doublet: Gringarten-Sauty thermal breakthrough vs the 30-year life;
  ESP setting depth to keep the intake above the gas bubble point (~42 bar, IAPWS Henry
  constants with salting out), at most 1,000 m; SodM's 0.135 bar/m injection limit at the top of
  the reservoir. A doublet breaking the ESP or injection limit gets its flow capped.
- **Names**: designs are A1, A2 … (first search, ranked), B1 … (next search), W1 … (what-ifs),
  U1 … (yours), the code beside. **Headline cost** = heat and cold together. One rounding.
- The result card shows the four picks, the spare on the peak day and the one-unit-out cases;
  a what-if card says whether the pick changes.
- Decision record: `hackathon/docs/decisions/ADR-0011-picks-failures-plans.md`.

## How to use it

A server is running for you (the address is in your task). Use the command-line client; every
command prints plain text:

```
cd <the repository>
export DIOSCURI_URL=<your server address>
PY=~/anaconda3/envs/dioscuri/bin/python
$PY hackathon/scripts/panel.py say   <thread> "your message"     # one chat turn
$PY hackathon/scripts/panel.py click <thread> 1                  # answer the open card (option 1, 2 ...)
$PY hackathon/scripts/panel.py state <thread>                    # what the conversation knows
$PY hackathon/scripts/panel.py designs <thread>                  # every design so far
$PY hackathon/scripts/panel.py design <thread> "<design id>" plant|graph|economics|year|checks|gemini|all
$PY hackathon/scripts/panel.py attempts <thread>                 # every design search with its candidates
$PY hackathon/scripts/panel.py gemini <thread> "<design id>"     # run the design's brine loop on GEMINI
$PY hackathon/scripts/panel.py edit <thread> "<design id>" '{"boiler_mw": 10}'   # a user design (Design tab)
$PY hackathon/scripts/panel.py prices <thread> '{"gas_eur_per_mwh": 45}'        # Economics tab assumptions
$PY hackathon/scripts/panel.py sensitivity <thread> "<design id>" '[{"key": "heat_return", "low": 45, "high": 70}]'
$PY hackathon/scripts/panel.py trace <thread>                    # each run's steps, model calls, tokens
$PY hackathon/scripts/panel.py health                            # which models run where
```

- Use thread names that start with your role, e.g. `econ-1`, `econ-2`. A new name is a new chat.
- The first design request of a chat shows an inputs card (what was read from the files, what
  is assumed). Click 1 to run, or say what to change.
- A turn takes 2-60 s; the server runs one chat turn at a time, so a turn may wait for other
  panel members. Give each command up to 10 minutes (Bash `timeout` 600000 ms) and do not run
  the same thread twice at once.
- `edit` keys: n_doublets, depth_m, heat_pump_mw, boiler_mw, absorption_mw, chiller_mw,
  reservoir_delta_c, return_c, cool_return_c, doublets (list of {depth_m, producer_open
  full|upper|lower, injector_open, injectors 1|2, max_flow_m3h, train}), dispatch (equal|base).
- `sensitivity` keys: heat_return, cool_return, reservoir_temp, permeability, depth,
  operating_days, heat_demand, cool_demand, gas_price, electricity_price, carbon_price, capex,
  discount_rate.

Code and documents you may read (read only):
- the agent: `src/gemini_agent/` (agent.py orchestration, engine.py, parameters.py, answer.py,
  reporter.py, claims.py, intake.py, prompts/); the plant model: `src/dioscuri_plant/` (year.py,
  search.py, economics.py, doublet.py, components.py, firm.py, subsurface.py); failures and
  comparisons: `src/gemini_agent/reliability.py`; GEMINI itself: `src/gemini_model/`,
  `src/gemini_simulator/`;
- decisions: `hackathon/docs/decisions/ADR-0001` to `ADR-0011`; the tabs' contract:
  `hackathon/docs/workbench_api.md`; GEMINI's bugs: `hackathon/docs/gemini_overview/`;
- the evaluation scenarios: `hackathon/evals/scenarios/scenarios.yaml`;
- the app's front end: `frontend/src/` (React; chat in components/, tabs in tabs/).

You may run Python (`$PY`) to check numbers (for example heat = flow × density × cp × ΔT).

## Rules

- Do not change any file in the repository, do not commit, do not push, do not start or stop
  servers, do not install anything, never use sudo. Write only your report file.
- Never send anything to an external service; work only with the local server and files.
- Be concrete: quote the exact message you sent and the part of the reply or card that is wrong,
  and say why in your field's terms, with numbers where you can.

## Your two tasks

**A. Stress the model's understanding.** The team's rule is that models understand requests
and code does the numbers: there must be no phrase lists deciding what a message means. Word
the same request several ways (plain, expert jargon, terse, long, with typos, Dutch or German,
relative amounts, dates in different formats, several steps at once, references like "the
cheapest one" or "A2"), and check that the agent does the right thing every time and that every
number it says matches its cards and data. Count how many wordings of each request it gets right.
Check also that what the user sees (cards, labels, names) is what really happened and is not
ambiguous.

**B. Say what is missing.** As an expert in your role who would use or judge this workflow: what
would you expect from it that it does not do yet? What do users in your role need most that is
lacking? Rank it, say why it matters, and roughly how hard it is (hours, a day, days, weeks).

Spend your effort where your role knows best; 15-25 turns is plenty.

## Report

Write your report (Markdown) to the file named in your task and also return it as your final
answer, in this form:

1. **Verdict** (3-5 sentences, in your role's voice).
2. **Stress test** (a table: request, wordings tried, right / wrong, what went wrong).
3. **Issues** (each: severity high / medium / low; message; what happened, quoted; why it
   matters; what to do instead). Most important first.
4. **What users in my role need most that is missing** (ranked, each with why and effort).
5. **What works** (up to 5 bullets).
