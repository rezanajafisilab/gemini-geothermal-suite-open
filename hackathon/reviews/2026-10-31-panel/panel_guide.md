# Review panel guide: challenge the Dioscuri agent

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
the cost of a treatment train.

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
  search.py, economics.py, doublet.py, components.py); GEMINI itself: `src/gemini_model/`,
  `src/gemini_simulator/`;
- decisions: `hackathon/docs/decisions/ADR-0001` to `ADR-0010`; the tabs' contract:
  `hackathon/docs/workbench_api.md`; GEMINI's bugs: `hackathon/docs/gemini_overview/`;
- the evaluation scenarios: `hackathon/evals/scenarios/scenarios.yaml`;
- the app's front end: `frontend/src/` (React; chat in components/, tabs in tabs/).

You may run Python (`$PY`) to check numbers (for example heat = flow × density × cp × ΔT).

## Rules

- Do not change any file in the repository, do not commit, do not push, do not start or stop
  servers, do not install anything, never use sudo. Write only your report file.
- Never send anything to an external service; work only with the local server and files.
- Be concrete: quote the exact message you sent and the part of the reply or data that is
  wrong, and say why in your field's terms, with numbers where you can.
- Say what works well too, briefly: the team needs to know what to keep.
- Spend your effort where your role knows best; 10-20 turns is plenty. Stop when you have
  enough evidence.

## Report

Write your report (Markdown) to the file named in your task and also return it as your final
answer, in this form:

1. **Verdict** (3-5 sentences, in your role's voice).
2. **What works** (up to 5 bullets).
3. **Issues** (each: severity high / medium / low; what you did, with the message; what
   happened, quoted; why it matters; what to do instead). Most important first.
4. **Implement differently or remove** (design changes, redundancy, things that should go).
5. **Top 3 priorities before the deadline.**
