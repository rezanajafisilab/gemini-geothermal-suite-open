<p align="center">
  <img src="hackathon/brand/png/dioscuri-logo@4x.png" alt="Dioscuri" width="340">
</p>

# Dioscuri: geothermal heating and cooling, designed in a chat

Team Dioscuri's entry to the **SPE Europe Energy GeoHackathon 2026**, built on TNO's open-source
[GEMINI](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open) geothermal digital
twin.

**Team:** Reza Najafi Silab and Abdolali (Ali) Mosallanezhad, Heriot-Watt University.

> **Report, video and transcripts.** Our report, the 5-minute video and the chat transcripts of
> our evaluations have already been sent to the organisers via Discord. They are not part of
> this repository.

Dioscuri designs a geothermal plant that heats **and cools** an urban district. You ask in plain
words. It shows every input it will use, with its source, and asks when something is missing or
unclear. Then it simulates thousands of candidate plants over a whole year, day by day, checks the
physics and the challenge's limits, and recommends a design with its energy, costs, CO₂ and
risks. Code computes every number; a local language model reads your request and explains the
results. Everything runs on your own computer with open-weight models (Ollama): no cloud service
and no API key.

## What Dioscuri adds to GEMINI

| Part | What it does | Where |
|---|---|---|
| **The agent** | Reads each message with a local model and asks, with choices, when a request is missing a value or unclear. Code then plans the work, runs the design search and checks every number in the reply against its source before you see it. It keeps track of the conversation, remembers what you ask it to (your name, how to answer), and counts the tokens and time of every model call. | `src/gemini_agent/` |
| **A whole-plant model** | GEMINI's wells and reservoir for every design, plus what GEMINI does not model: heat pumps, gas and electric boilers, chillers, free cooling, heat and cold stores, solar panels, the district network's heat losses, CO₂ dissolved back into the injected brine, more than one aquifer, a year of operation day by day, outages, N-1 and Monte Carlo risk, and the costs (capital, running, cash flow against gas, the investor's view with subsidy and tax). | `src/dioscuri_plant/` |
| **The design search** | Thousands of designs under the challenge's hard limits (1 to 3 doublets, 50 to 300 m³/h, ΔT up to 40 K, 330 days of operation). It picks the best design for each goal: cheapest, greenest, gas-free and most reliable. | `src/dioscuri_plant/search.py`, `src/gemini_agent/engine.py` |
| **GEMINI fixes** | 10 issues found in GEMINI's models (F1 to F10), each with a reproduction script and a patch. Dioscuri applies the patches to a copy of GEMINI's models when it runs, so GEMINI's own files are unchanged. | `hackathon/gemini_bughunt/` |
| **The app** | A chat with tabs for **Design** (the plant drawn, with a year played day by day), **Energy**, **Economics**, **Compare**, **Sensitivity**, **Trace** (every step, model call and token count) and **Evidence** (tests, model benchmarks, GEMINI fixes, real-project checks). Exports: the operator's report (PDF), a permit and subsidy pack (PDF), and the design as a GEMINI project file (JSON). | `frontend/` |
| **Real projects** | Two real Dutch doublets are built in besides the challenge district: Trias Westland and Haagse Aardwarmte Leyweg. Dioscuri's heat for Trias Westland is within 1.6 % of the published pre-drill forecast. | `src/gemini_agent/data/` |
| **Evidence** | Evaluation suites with recorded runs, a calculation audit, model benchmarks and the design decisions. | `hackathon/evals/`, `hackathon/docs/` |

**Measured on this release** (qwen3.5:9b on a GPU): 185 of 185 chat cases, 59 of 61 unclear or
incomplete requests, and 71 of 76 turns in multi-turn conversations. 1,081 Python tests and 682
interface tests pass. The report and its transcripts come from the test run of the morning of 5 Nov
(184 of 185, 51 of 52 and 64 of 65). This release then added project memory, CO₂ by unit, the inputs
reset and design alerts, with new test cases for them; on the earlier cases it scores 185 of 185,
50 of 52 and 62 of 65.

## What you need

- Windows 10/11, macOS or Linux, with 16 GB of RAM and about 10 GB free for the models.
- **Ollama**, which runs the models locally. One command installs it (step 1 below).
- An internet connection for the install. Python is not needed: the installer brings its own.
- A GPU is optional. Dioscuri takes the first of these that fits:
  1. qwen3.5:9b on an NVIDIA GPU with about 7 GB free (10 to 30 s a question);
  2. qwen3.5:4b on a GPU with 4.5 GB free;
  3. without a usable GPU, qwen3.5:9b on the CPU when about 8 GB of memory is free;
  4. otherwise qwen3.5:4b on the CPU (about 2 minutes for a design and 2 to 4 for a question).

  The two switches in the header pick the device (GPU | CPU) and the model (Auto | 9B | 4B), and
  the header shows which model runs where, and why.

## Install (once, 10 to 20 minutes, mostly downloading the models)

**Get Dioscuri** in one of two ways:

- **The release zip (easiest):** download `dioscuri-<date>-<commit>.zip` from this repository's
  [Releases](https://github.com/rezanajafisilab/gemini-geothermal-suite-open/releases) page and unzip it (Windows: right-click the file, **Extract All**,
  then **Extract**). You get a `dioscuri` folder.
- **With git:**

  ```sh
  git clone -b dioscuri https://github.com/rezanajafisilab/gemini-geothermal-suite-open.git dioscuri
  ```

  The interface is prebuilt in `frontend/dist`, so Node.js is not needed.

**Windows**

1. Install **Ollama**: open **PowerShell** (Start menu, type `PowerShell`, press Enter), paste
   this line and press Enter:

   ```powershell
   irm https://ollama.com/install.ps1 | iex
   ```

   Ollama then runs in the background (a llama icon near the clock). Already have Ollama? Skip
   this step.
2. Open the `dioscuri` folder and **double-click `install.bat`**. A window shows each step. If
   Windows warns about the file, choose **More info**, then **Run anyway**. At the end the window
   says **Done** (or what to fix); press any key to close it.

**macOS or Linux**

1. Install **Ollama**: open a terminal, paste this line and press Enter (it may ask for your
   password):

   ```sh
   curl -fsSL https://ollama.com/install.sh | sh
   ```

   Already have Ollama? Skip this step.
2. Open a terminal in the `dioscuri` folder and run `./install.sh`.

If the Ollama command does not work, its installer is also at
[ollama.com/download](https://ollama.com/download).

Everything goes into the `dioscuri` folder: [uv](https://docs.astral.sh/uv/) and its own Python
3.12 in `.tools`, and the packages of `requirements-dioscuri.txt` in `.venv`. A Python already on
the computer is neither used nor changed. Ollama downloads both models, qwen3.5:9b and
qwen3.5:4b.

## Start

- **Windows:** double-click `start.bat`.
- **macOS or Linux:** run `./start.sh` in a terminal in the folder.

A window opens and Dioscuri opens in your browser. Keep that window open while you use Dioscuri;
close it (or press Ctrl+C in it) to stop. If the browser does not open, copy the address the
window shows, for example `http://127.0.0.1:8000`, into the browser.

If port 8000 is taken, Dioscuri uses the next free one (8001, 8002, ...) and the window says
which. To choose the port yourself, set `DIOSCURI_PORT` first, for example
`DIOSCURI_PORT=8765 ./start.sh` (Windows: `set DIOSCURI_PORT=8765` in a command window, then
`start.bat`).

## Uninstall

1. Close Dioscuri first: its browser tabs, and the window that `start.bat` or `./start.sh` opened.
   Ollama can stay open: it is needed to remove the models.
2. Double-click `uninstall.bat` (Windows) or run `./uninstall.sh`. It removes `.venv` and `.tools`
   and asks before removing the models from Ollama.
3. Delete the `dioscuri` folder.

## A first design (2 minutes)

1. Dioscuri opens on an empty chat in the challenge district. The design tabs fill once the chat
   has run a design.
2. Click **Design heating and cooling** and send it, or type "Design heating and cooling for the
   district". Dioscuri shows the inputs it will use, page by page: the organisers' demand files,
   the reservoir and its aquifers, the brine and its gas, the networks, the prices and the
   limits. Each value has its source, its range and what it depends on, and the values Dioscuri
   had to assume are marked. Options the brief leaves out, such as free cooling, solar panels
   and heat stores, can be switched on here. Change any value, then press **Run** on the review
   page.
3. The steps tick off while it searches. The answer leads with one recommended design, and the
   tabs at the top show it in full.
4. Ask anything: "what does heat cost?", "what if the doublet stops from 10 to 24 January?",
   "add 5 MWp of solar", "compare the cheapest with the most reliable", "there is also a
   sandstone at 3.4 km with more gas: design with both". Type **@** to name a design, or
   right-click any result to ask about it, change it or compare it.
5. **Export** (top right of a design tab): the operator's report, the permit and subsidy pack,
   and the GEMINI project file. Each opens as a preview first.

Three projects are built in: the challenge district, Trias Westland and Haagse Aardwarmte
Leyweg. **Ctrl+K** finds any screen, design or action.

**What Dioscuri remembers.** Each chat keeps its own conversation, designs and confirmed inputs.
Each project keeps what you ask Dioscuri to remember ("call me Sam", "keep answers short"); the
sidebar lists it under **Remembered**, where you can forget one note or all of them. Removing a
chat removes its conversation, designs, runs and uploaded files.

## If something goes wrong

- **"Ollama is not installed"**: run the one-line install of step 1, then the installer again.
- **"Ollama is not running"**: start the Ollama app (Windows, macOS) or run `ollama serve`.
- **A model is missing**: `ollama pull qwen3.5:9b` and `ollama pull qwen3.5:4b`.
- **The page does not open**: copy the address the start window shows into the browser.
- **The install stops**: it says why; run it again after fixing that (it starts over safely).
- **Slow answers**: without a GPU each answer takes minutes. Pick 4B in the header's model switch
  for faster answers on the CPU.
- Optional, better document search: `.venv/bin/python -m pip install -r requirements-search.txt`
  (Windows: `.venv\Scripts\python -m pip ...`) and `ollama pull snowflake-arctic-embed:s`.
  Without these the search is by keywords.

## For developers

```sh
# Python 3.12 with requirements-dioscuri.txt and hackathon/requirements-dev.txt installed
PYTHONPATH=src:. python -m pytest unit_test          # all Python tests
PYTHONPATH=src:. python -m gemini_agent.server       # the app, at http://127.0.0.1:8000

cd frontend && npm ci                                 # Node.js 22 or newer
npm test                                              # interface tests
npm run dev                                           # live-reloading interface
npm run build                                         # rebuilds frontend/dist
```

The evaluations run against a local Ollama, for example
`python hackathon/evals/run_evals.py --scenarios hackathon/evals/scenarios/chat.yaml --mode auto --device auto`.
`hackathon/scripts/make_release.py` builds the release zip from the committed tree.

## What is where

| Path | What |
|---|---|
| `src/gemini_agent/` | The agent: reading the message, asking, planning, the design engine, answers and their checks, memory, the server |
| `src/dioscuri_plant/` | The plant model: wells, heat exchanger, heat pump, boilers, chillers, free cooling, stores, solar, networks, a year day by day, costs, outages and risk |
| `frontend/` | The interface (React and TypeScript); `frontend/dist` is prebuilt |
| `unit_test/gemini_agent/`, `unit_test/dioscuri_plant/` | Tests of the agent and the plant model |
| `hackathon/gemini_bughunt/` | The 10 GEMINI issues: write-up, reproductions, outputs and patches |
| `hackathon/evals/` | Evaluation scenarios (chat, unclear requests, conversations) with their recorded runs, tokens and times |
| `hackathon/docs/` | Design decisions (`decisions/ADR-*.md`), the calculation audit, the cooling and reliability notes, cost sources |
| `hackathon/research/` | Sourced numbers for the plant model and notes on real Dutch doublets |
| `hackathon/brand/` | The Dioscuri logo |
| `install.*`, `start.*`, `uninstall.*` | The install, start and uninstall scripts |
| everything else | TNO's GEMINI, as released on its `development` branch; see [README_GEMINI.md](README_GEMINI.md) |

## Contributing back to GEMINI

Apart from this README (GEMINI's own is [README_GEMINI.md](README_GEMINI.md)), a few
`.gitignore` lines and the line endings of two CI scripts, GEMINI's files are unchanged. The
fixes we found are in `hackathon/gemini_bughunt/patches/`, one patch per issue against GEMINI's
`development` branch (`patch -p1 --binary`), each explained in
[hackathon/gemini_bughunt/README.md](hackathon/gemini_bughunt/README.md), so each can be applied
and reviewed on its own. `hackathon/gemini_bughunt/BUG_IMPACT.md` shows what each issue changes
in our designs.

## Licence and acknowledgements

Apache License 2.0, as GEMINI. Dioscuri builds on GEMINI by TNO and its partners (see
[README_GEMINI.md](README_GEMINI.md)). We thank SPE Europe and the GEMINI team for the challenge.
