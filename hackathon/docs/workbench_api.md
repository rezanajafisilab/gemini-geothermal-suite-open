# Workbench API: what the tabs read and do

Version 2, 30 Oct 2026 (the challenge engine, ADR-0008). Version 1 was the toy model's.

The chat and the tabs share one store: the designs of a conversation. The agent's tools and
these endpoints call the same Python functions, so a number on a tab is always the number the
chat would give. JSON everywhere. `threadId` is the chat's thread id; a new chat has no
designs yet.

Tabs and their scope:

| Group | Tabs | Scope |
|---|---|---|
| Talk | Chat | the conversation |
| One design | Design · Energy · Economics | the design in the design picker |
| All designs | Compare · Sensitivity | the conversation's designs |
| How we know | Trace · Evidence | the runs, the tests, the benchmarks |

## Designs

### `GET /api/workbench?threadId=T`

```ts
interface Workbench {
  threadId: string;
  physics: "gemini";                  // GEMINI's well solve (patched) for every doublet
  gemini: { version: string; patches: string[] } | null;
  assumptions: Assumptions;           // the conversation's prices, defaults where not changed
  designs: Design[];                  // [] for a new chat; the chosen one first, then what-ifs and user designs
  candidates: Candidate[];            // the last search: chosen first, then valid by cost, then failed
  reference: Candidate | null;        // gas boilers and electric chillers: the baseline for savings
}

interface Candidate {
  code: string;                       // "2D-BO-EC@3000": doublets, top-up (HP, BO, DH none), cooling (AB, EC), depth
  name: string;
  role: "chosen" | "candidate" | "failed" | "reference";
  reason: string;                     // why it lost (in numbers) or the cap it broke
  n_doublets: number; depth_m: number; topup: string | null; cooling: string | null;
  sizes_mw: Record<string, number>;
  lcoh: number; lcoc: number | null; lcoe: number;   // €/MWh; lcoe = heat and cold together
  co2_t: number; co2_saving_pct: number; capex_meur: number;
  heat_coverage_pct: number; cool_coverage_pct: number;
  rounds: number; changes: string[]; violations: string[]; verified: boolean;
}

interface Design {
  id: string;                         // stable within the conversation: "2D-BO-EC@3000", "2D-BO-EC@3000 −5 °C", "U1" …
  code: string;
  name: string;
  origin: "agent" | "user" | "what_if";
  role: string;                       // chosen, what_if, user …
  rounds: { sizes_mw: Record<string, number>; violations: string[]; change: string }[];
  parent: string | null;              // id it was derived from (user edits, what-ifs)
  chosen: boolean;                    // the chat's current recommendation or pick
  reservoir_delta_c: number;          // what-if shift, °C
  source: "gemini+dioscuri_plant" | "dioscuri_plant";  // wells on GEMINI, the year on the plant model
  verified: boolean;
  checks: { name: string; passed: boolean; detail: string }[];
  plant: Plant;
  year: Year;
  economics: Economics;
  graph: Graph;                       // the plant as the Design tab draws it
  provenance: Record<string, "gemini" | "dioscuri" | "user" | "rule">; // per field group, see below
}

interface Plant {
  depth_m: number;                    // 0 = no well (the gas reference)
  n_doublets: number; topup: string | null; cooling: string | null;
  max_brine_cooling_k: number; flow_mean_m3h: number | null;
  esp_head_bar: number | null; injection_wellhead_bar: number | null;
  stop_days: number[][];              // each doublet's 35-day stop, [first, last] (0-based)
  reservoir: { depth_m; temperature_c; pressure_bar; permeability_md; thickness_m;
               brine_density_kg_m3; brine_viscosity_mpa_s; gas_liquid_ratio };
  heat_pump: boolean; boiler: boolean; absorption: boolean; chillers: boolean;
  reservoir_c: number; wellhead_c: number; hex_outlet_c: number; reinjection_c: number;
  flow_m3h: number | null; esp_mw: number | null; injector_pump_mw: number | null;
  hex_ua_kw_per_k: number | null; cop: number; carnot_cop: number;
  transmissivity_dm: number | null; productivity_index_m3h_per_bar: number | null;
  heating_supply_c: number; heating_return_c: number; cooling_supply_c: number; cooling_return_c: number;
  sizes_mw: { heat_exchanger: number; heat_pump: number; boiler: number; absorption: number; chillers: number };
}

interface Year {
  heat_demand_gwh: number; cool_demand_gwh: number;
  heat_delivered_gwh: number; cool_delivered_gwh: number;
  heat_coverage: number; cool_coverage: number;        // 0..1
  heat_split_gwh: { geo: number; hp: number; boiler: number };
  cool_split_gwh: { abs: number; chill: number };
  peak_heat_mw: number; peak_cool_mw: number; full_load_hours: number;
  monthly_gwh: { heat: Record<"demand" | "geo" | "hp" | "boiler", number[]>; cool: Record<"demand" | "abs" | "chill", number[]> };
  daily_mw: { heat: Record<"demand" | "geo" | "hp" | "boiler" | "short", number[]>; cool: Record<"demand" | "abs" | "chill" | "short", number[]> }; // 365 values, day 1..365
  violations: string[];               // one sentence per broken cap (empty when all hold)
  electricity_gwh: Record<"hp" | "chillers" | "pumps" | "towers" | "recovery_hp", number>;
  purchased_gas_gwh: number; produced_gas_burned_gwh: number; produced_gas_flared_gwh: number;
  co2_t: Record<"purchased_gas" | "produced_gas" | "electricity" | "total", number>;
  stop_days: number[][];
  doublets: { flow_m3h: number[]; on: boolean[]; reinjection_c: (number | null)[] }[];
}

interface Economics {
  lcoh: number; lcoc: number | null; lcoe: number;  // €/MWh; lcoe: heat and cold together
  capex_meur: number;
  co2_t_per_year: number; reference_co2_t_per_year: number; co2_saving_pct: number;
  lines: { heat: CostLine[]; cold: CostLine[] };   // they add up to lcoh and lcoc
  capex_items: { item: string; size: number; unit: string; meur_per_unit: number; meur: number; life_years: number }[];
  versus_reference: {                 // against the gas reference (A4), same assumptions
    extra_capex_meur: number; savings_meur_per_year: number;
    payback_years: number | null; npv_meur: number;
    cash_flow_meur: number[];         // cumulative, year 0 .. lifetime
  } | null;                           // null for the reference itself
}

interface CostLine {
  item: string;                       // "Wells", "Heat exchanger", "Gas", "Electricity: heat pump" …
  kind: "capital" | "fixed" | "variable" | "electricity" | "gas" | "carbon";
  meur_per_year: number; eur_per_mwh: number;
}

interface Graph {
  nodes: GraphNode[]; edges: GraphEdge[];
  gemini_project: object | null;      // the GEMINI project JSON that GEMINI's solver ran
}
interface GraphNode {
  id: string; type: string;           // a catalogue type, or "reservoir", "demand_heat", "demand_cold", "absorption", "chillers", "gas"
  label: string;
  solver: "gemini" | "dioscuri";      // GEMINI's solver, or Dioscuri's plant model
  values: Record<string, number>;     // e.g. { power_mw: 9.25, temperature_out_c: 45.4 }
  units: Record<string, string>;
}
interface GraphEdge {
  id: string; source: string; target: string;
  kind: "brine" | "network" | "cold" | "gas" | "electricity";
  mw: number | null; temperature_c: number | null; label: string;
}
```

`provenance` keys: `plant` (the operating point), `year` (the dispatch), `economics`,
`cooling`. Values say who produced them.

### `PUT /api/assumptions`  `{threadId, assumptions: Record<string, number | null>}` → `Workbench`

Economics is recomputed for every design (the physics does not change). `null` goes back to
the default.

```ts
interface Assumptions {
  items: { key: string; label: string; unit: string; group: "prices" | "capital" | "o&m" | "lifetimes";
           value: number; default: number; source: string }[];   // dioscuri_plant Prices, with sources
  defaults: Record<string, number>;
  sources: Record<string, string>;
  notes: string[];
  [key: string]: unknown;             // the current values by key too
}
```

### `POST /api/designs`  `{threadId, base: string, name?: string, changes: DesignChanges}` → `{design: Design}`

Adds a user design (origin `"user"`, code `U1`, `U2` …) built from `base` with `changes`, runs
it end to end (GEMINI's wells, the year, costs, the caps) and keeps it with the conversation.

```ts
interface DesignChanges {
  n_doublets?: number;                // 1-3
  depth_m?: number;                   // 1,000-4,000
  heat_pump_mw?: number; boiler_mw?: number; absorption_mw?: number; chiller_mw?: number;  // 0: not built
  reservoir_delta_c?: number;
  return_c?: number;                  // heating return (supply fixed at 100 °C)
  cool_return_c?: number;             // cooling return (supply fixed at 20 °C)
}
```

### `DELETE /api/designs?threadId=T&id=U1` → `{ok: true}` (user designs only)

## GEMINI projects (the Design tab's "GEMINI project" view)

### `GET /api/gemini/catalogue` → `{types: CatalogueType[]}`

```ts
interface CatalogueType {
  type: string;                       // GEMINI registry type: producer_well, separator, filter, heat_exchanger, heatpump, boiler, chp, splitter, mixer, adder, injector_well …
  label: string; group: "wells" | "surface" | "heat" | "flow";
  description: string;
  inputs: { key: string; unit: string; description: string }[];
  outputs: { key: string; unit: string; description: string }[];
  parameters: { key: string; unit: string; default: number | string | object | null; description: string }[];
}
```

### `POST /api/gemini/run`  `{project, compare_released?: boolean}` → `GeminiRun`

```ts
interface GeminiRun {
  ok: boolean; error: string | null; seconds: number;
  outputs: Record<string, Record<string, number>>;            // component -> output key -> value
  released: { ok: boolean; error: string | null; outputs: Record<string, Record<string, number>> } | null;
  patches: string[];                  // the fixes the "fixed" run used
}
```

`project` is GEMINI's own JSON: `components`, `boundary_inputs`, `connections` (exactly the
format of `simulator_examples/projects/*.json`).

## Sensitivity

### `GET /api/sensitivity/parameters` → `{parameters: SensParam[], outputs: SensOutput[]}`

```ts
interface SensParam {
  key: string; label: string; unit: string;
  group: "subsurface" | "demand" | "prices" | "costs" | "equipment";
  low: number; high: number;          // default range, as a value or a change (see kind)
  kind: "absolute" | "delta" | "scale"; // value; added (°C); multiplied (1 = as is)
  description: string;
}
interface SensOutput { key: "lcoh" | "lcoc" | "lcoe" | "co2_saving_pct" | "heat_coverage" | "capex_meur" | "npv_meur" | "violations"; label: string; unit: string }
```

### `POST /api/sensitivity`  `{threadId, design: string, parameters: {key, low, high}[], outputs: string[], samples?: number}` → `Sensitivity`

```ts
interface Sensitivity {
  design: string; seconds: number; runs: number;
  base: Record<string, number>;       // output -> value at the base case
  tornado: { key: string; label: string; low: Record<string, number>; high: Record<string, number> }[]; // sorted by swing of the first output
  spider: { key: string; points: { x: number; values: Record<string, number> }[] }[];   // 5 points low..high
  monte_carlo: { samples: number; outputs: Record<string, { p10: number; p50: number; p90: number; mean: number; histogram: { edges: number[]; counts: number[] } }> } | null;
}
```

`samples` 0 or absent: no Monte Carlo; otherwise uniform within each chosen range (at most
500).

## Trace and evidence

### `GET /api/trace?threadId=T` → `{runs: TraceRun[]}`

```ts
interface TraceRun {
  runId: string; started: number; message: string; mode: "fast" | "reasoning"; device: string;
  seconds: number; tokens: { prompt: number; output: number };
  steps: { name: string; label: string; kind: string; code: string | null; seconds: number; meta: Record<string, unknown> }[];
  calls: { purpose: string; model: string; prompt_tokens: number; output_tokens: number; seconds: number; ok: boolean }[];
  tools: { name: string; args: unknown; result: unknown }[];
  outcome: string;                    // behaviour: design, answer, clarify …
}
```

### `GET /api/evidence` → `Evidence`

```ts
interface Evidence {
  evals: { file: string; device: string; answerer: string; when: string; passed: number; total: number; tokens: number; seconds: number;
           scenarios: { id: string; expected: string; got: string; ok: boolean; calls: number; tokens: number; seconds: number;
                        failed: string[]; transcript: boolean }[] }[];
  benchmarks: { title: string; columns: string[]; rows: (string | number)[][]; note: string }[];
  gemini: { version: string; patches: { file: string; title: string }[];
            bug_impact: { design: string; rows: { quantity: string; unit: string; released: number | null; fixed: number | null; bugs: string }[] }[] };
  // Failures found and fixed (src/gemini_agent/caught.py, data/caught_and_fixed.json; the
  // report's hackathon/docs/caught_and_fixed.md is written from the same file).
  caught: { updated: string; total: number; guarded: number; avoided: number;
            groups: { key: string; label: string; total: number; guarded: number }[];
            items: { id: string; group: string; group_label: string; title: string; failed: string; found: string;
                     found_in: string; fix: string; commit: string | null; adr: string | null; patch: string | null;
                     tests: string[]; status: "fixed" | "avoided"; source_label: string | null }[] };
}
```

### `GET /api/transcript?run=R&case=C` → `Transcript`

One eval case, whole (`hackathon/evals/transcripts.py` writes
`hackathon/evals/runs/transcripts/<run>/<case>.json`; `run` is the run's JSONL name without
`.jsonl`). 400 for a name with a path in it, 404 when the run kept none. The Evidence tab opens it
at `#evidence/<run>/<case>`.

```ts
interface Transcript {
  run: string; case: string; after: string | null;   // the case whose conversation it continues
  prompt: string; model: string; device: string; expected: string; got: string | null;
  pass: boolean; behaviour_ok: boolean; checks: Record<string, boolean | null>;
  truth: { design: string | null;                    // hackathon/evals/truth.py
           caps: { key: string; name: string; ok: boolean | null; found: string }[];
           known: { key: string; name: string; ok: boolean | null; found: string }[];
           quotes: { text: string; known: number; ok: boolean }[] } | null;
  exchanges: { user: { message?: string; answers?: Record<string, string>; upload?: { files: string[] } };
               events: AgEvent[] }[];                // what the chat's reducer replays
  runs: TraceRun[];                                  // the events read as GET /api/trace reads them
}
```

## The recommended design and the cost basis (3 Nov)

### `GET /api/lead` → `LeadView`

The app opened on this until 5 Nov; a new chat now starts empty and nothing on screen reads it
(the report's scripts do). The recommended design for the challenge district (`gemini_agent.lead`):
`engine.search` on a new conversation's brief, run once in the background on the first request
(`DIOSCURI_LEAD_AT_START=1` starts it when the server starts) and kept in `hackathon/evals/runs/lead/challenge.json`
(`DIOSCURI_LEAD`) under a fingerprint of the models, the engine and the data. While it runs:
`{state: "computing", since}`; on failure `{state: "error", error}`; then `{state: "ready", found,
design: Design, words, caps: {key, label, passed, detail}[] (the six hard caps, the verifier's own
checks), checks: {passed, total}, basis: CostBasis, search: {layouts, valid, years, picks}, computed_at,
seconds}`.

### `POST /api/lead/open`  `{threadId}` → `{threadId, design}`

Puts that search into an empty conversation (S1, A1 ... as the chat names them; its uploads and
prices stay), so the tabs show the design and the chat can be asked about it. 409 when the
conversation has started, is another project's, or the design is still being computed.

### `GET /api/cost-basis?threadId=T&design=ID` → `CostBasis`

What a design's cost includes (each part in €/MWh of heat and cold, and its share) and leaves out
(and why), the discount rate, the lifetimes of its units, the prices with their sources, how heat
and cold share the costs, and `swings`: the same plant repriced (`engine.reprice`) with one
assumption at a low and a high value (discount rate 3 / 8 %, electricity and gas ±50 %, CO₂ 0 and the
long-term 137 €/t, capital ±30 %, the wells' life 20 / 40 years), widest first.

## Design attempts (the Compare tab)

Every design search of a conversation is kept as an attempt, `S1`, `S2` …, and every candidate
and design carries its `attempt`. `GET /api/workbench` returns them newest first:

```ts
interface Attempt {
  id: string; n: number; at: number | null;   // epoch seconds
  message: string;                             // the request, at most 200 characters
  label: string;                               // "lowest cost · 1–3 doublets · 2,500, 3,000 and 3,500 m"
  objective: "cost" | "co2"; chosen: string | null;
  repriced: boolean;                           // only the newest is priced at the chat's assumptions
  candidates: Candidate[]; reference: Candidate | null;
}
// Workbench.attempts: Attempt[]; Candidate.attempt and Design.attempt: string | null
```

`candidates` and `reference` at the top level stay the newest attempt's. A search asked for again
with the same inputs is not run: the chat says the search is deterministic and offers choices
(the runner-up in full, the other objective, the known aquifer only, a different top-up).

## The plant graph's grid and towers

`Design.graph` has two more node types: `grid` (electricity drawn from the grid: total and per
unit, its CO₂) and `tower` (heat rejected by the chillers and the absorption chiller, the towers'
electricity). Edges of kind `electricity` run from `grid` to `chillers`, `heat_pump`, `producer`
(the well pumps) and `tower`; edges of kind `reject` run from `chillers` and `absorption` to
`tower`. `Design.year.daily_mw` gains `power: {hp, chillers, towers, pumps}` and
`reject: {abs, chillers}` (365 values each) for the per-day view. The reservoir node's `label`
says "Assumed aquifer at 3,000 m" when the wells are deeper than the known aquifer, and its
`values` carry `assumed`, `known_depth_m` and `known_temperature_c`.

## Chat cards

A `result` event may carry `view: "compact"` and `against` (the design it is compared with): a
what-if is shown as one row of deltas, not the full report. Answers about a design that exists
carry no card; the chat links to the tabs instead.

## Projects (the sidebar's switcher and "New project")

A project is one district: a year of daily heat and cold demand, a reservoir and the networks'
supply and return temperatures (`src/gemini_agent/projects.py`). The organisers' district is
built in (`challenge`); users add theirs. Every chat belongs to one project: a run's
`projectId` puts a new conversation in it, and the engine then runs on that project's demand
and reservoir. The challenge's caps hold for every project. User projects are kept under
`DIOSCURI_PROJECTS` (default `hackathon/evals/runs/projects/`, not committed).

### `GET /api/projects` → `{projects: Project[]}`

```ts
interface Project {
  id: string; name: string; builtin: boolean; created: number | null;
  files: string[];                    // the uploads as they came (the challenge: its 3 files)
  reservoir: { depth_m: number; temperature_c: number; pressure_bar: number; permeability_md: number;
               thickness_m: number; gradient_c_per_km: number };   // gradient from a 12 °C surface
  heating: { supply_c: number; return_c: number }; cooling: { supply_c: number; return_c: number };
  totals: { annual_heat_gwh: number; annual_cool_gwh: number; peak_heat_mw: number; peak_cool_mw: number };
  notes: string[];                    // how the files were read ("kW read from the header …")
  weekly_mw: { heat: number[]; cool: number[] };                   // 52 weekly means
}
```

### `POST /api/projects` (form) → 201 `{project: Project}`, or 422 with the reason

Fields: `name`; `heat` (CSV file); `cool` (CSV file, optional: else the heating file's cooling
column if it has one, else no cooling); `depth_m` and `temperature_c` (needed);
`pressure_bar` (default hydrostatic), `permeability_md` (200), `thickness_m` (100),
`heat_supply_c` (100), `heat_return_c` (60), `cool_supply_c` (20), `cool_return_c` (25).
A demand file is 365 daily or 8,760 hourly values (averaged to days), comma- or
semicolon-separated (then with decimal commas), in MW, kW, MWh or kWh as its header says (MW
when it says none). Searches try the reservoir's depth and 500 and 1,000 m deeper.

### `POST /api/projects/profile` (form: `file`, `kind` heat|cool) → `ProfilePreview`

The form's preview: `{name, kind, column, annual_gwh, peak_mw, notes, weekly_mw, cool_column}`,
read exactly as `POST /api/projects` would; 422 with the reason when it can't be.

### `DELETE /api/projects/{id}` → `{ok: true, threads: string[]}`

Removes a user's project and its files (422 for `challenge`, 404 when unknown), and every chat
of it the server knows (in memory or saved), as `DELETE /api/threads/{id}` does; `threads` lists
them. The project's documents leave the document search. The app then forgets the project's
chats in the browser and removes each on the server by its id too (a run stopped before its chat
was saved leaves a trace and no session).

`POST /api/attachments` takes an optional `projectId` too, and `GET /api/files` an optional
`projectId` for a chat that has not started yet.

## Removing a chat (5 Nov)

### `DELETE /api/threads/{threadId}` → `{ok: true, threadId, stopped: number, removed: string[]}`

Removes a conversation with all the server keeps of it. A run of it streaming (or waiting for its
turn) stops at its next event; `stopped` counts them. Then, by the exact thread id (letters,
digits, `-` and `_`, else 400), in the server's own folders: the session `<id>.json` (and an
unfinished `<id>.tmp`) and the uploads folder `<id>/` under `DIOSCURI_SESSIONS`, and the trace
`<id>.jsonl` under `DIOSCURI_TRACES`; `removed` names the ones that were there. From memory: the
session (its designs, searches, what-ifs, cost assumptions, names and stars live in it) and the
uploads' passages in the document search. What a stopped run writes after the removal is removed
when it stops; meanwhile a new run on that id gets 409. An unknown thread answers the same, with
nothing removed.

Left alone, because other chats share them: the project and its files and documents, approved
generated component models (`generated_models/`), the document index of GEMINI's documentation,
and the tool results the agent memoises by their inputs (another chat may ask for the same
design).

## Doublets that differ, wider searches, what-ifs (31 Oct, ADR-0010)

**Codes.** `{n}D-{HP|BO|DH}-{AB|EC|NC}`, then `@3000` (all doublets in an assumed aquifer) or
`@2500+3000` (one per doublet), then flags: `-2I` two injectors per doublet (`-2I1`: on doublet 1
only), `-ST` a treatment train per doublet (`-ST2`: two trains), `-BL` the hottest doublet first
(base load), `-PL`/`-PU` producers and `-IL`/`-IU` injectors open over the lower/upper half of the
aquifer. A what-if's id is `<code> · <change label>` (`2D-HP-AB · heating return temperature 50 °C`).

**`Design`** gains `changes` (`{key: value}`, a what-if's), `change_label`, `flags`, `stage`
(2: a variant of `parent`), `dispatch` (`equal` | `base`), `doublets` (each `{depth_m,
producer_open, injector_open, injectors, max_flow_m3h, train}`), `sizings` (every sizing tried:
`heat_pump_share, absorption_share, heat_pump_mw, boiler_mw, absorption_mw, chiller_mw, lcoe,
co2_t, valid, years`) and `warnings`. `design.plant` gains `doublets` (one row per doublet:
`doublet, depth_m, producer_open, injector_open, producer_mid_m, producer_open_m,
injector_mid_m, injector_open_m, injectors, train, cap_m3h, rock_c, wellhead_full_c,
wellhead_min_c, well_loss_full_k, days_on, flow_mean_m3h, flow_year_mean_m3h, brine_m3,
max_cooling_k, esp_gwh, injection_gwh, esp_head_full_bar, injection_full_bar, pi_m3h_per_bar,
injectivity_m3h_per_bar`), `wells`, `trains`, `dispatch`. `design.year.doublets[i]` gains a daily
`wellhead_c` (null on days off).

**`design.graph`**: `producer_1`..`producer_n` (type `producer_well`), `injector_1` or
`injector_1a`/`injector_1b` (type `injector_well`), `train_1`..`train_k` (type `treatment`:
separator and filters), with edges reservoir → producer → train → exchanger (and absorption, gas)
→ heat pump → injectors → reservoir, and grid → each producer (its pumps). The old `producer` and
`injector` ids are gone. `gemini_project` is the whole brine loop in brine-flow order
(`tools.gemini.plant_project`): `producer_well[_i]`, per train `brine_mixer[_k]`, `separator[_k]`,
`filter_a[_k]`, then `brine_header` (mixer, several trains), `heat_exchanger`, `filter_b`,
`gas_adder` (adder, several separators), `boiler`, `brine_splitter` (several injectors),
`injector_well[_i|_ia|_ib]`; the producers' ESP is GEMINI's example scaled to each duty.

**Economics**: `capex_items` may hold several `Wells` rows (each with a `note`: producers,
injectors, the depth priced) and `Treatment trains` rows (one per train).

**Attempts** gain `layouts`, `sizings`, `years`, `notes`; candidate rows gain `flags`, `stage`,
`parent`, `dispatch`, `doublets`, `wells`, `trains`, `sizings` (a count).

**`POST /api/designs`** `changes` may hold `doublets` (1-3 rows as above; depth 500-7,000 m, cap
50-300 m³/h) and `dispatch`.

**Chat events.** Before the first design of a chat: a text (the inputs as a Markdown table), a
`confirm_inputs` custom event `{rows: [{group, label, value, source, kind, changed}], changed,
options, kinds}` and a `clarification` of kind `confirm` (options "Run the design with these
inputs", "Change an input first"); the run ends with interrupt `confirm`. Answer with
`{"answers": {"confirm": <option>}}` or a message (read by the reasoning model: run, change,
other). The `result` card gains `design_id`, `change_label`, `changes`, `flags`, `doublets`,
`dispatch`. New steps: `parameters` (what the message sets: `changes`, `doublets`, `unsupported`,
`dropped`), `confirm` (`decision`), `inputs` (`rows`, `assumed`) and, in a what-if, `search`.

## Issues on the Design tab (5 Nov)

**`Design`** gains `broken_days` (the day ranges a cap is broken, as the Compare tab's rows had
them: `{first, last, kind, text}`, the year strip's red bands) and `issues`, what goes wrong in the
year part by part, the worst first (`gemini_agent.issues`):

```ts
interface DesignIssue {
  id: string;                      // "heat_short-1"
  kind: "heat_short" | "cool_short" | "failure" | "cap";
  severity: "critical" | "warning"; // critical: demand not met (red); warning (amber)
  units: string[];                 // graph node ids it concerns, the main one first
  limit: string[];                 // node ids flat out on its days (at their limit)
  unit: string; what: string; why: string; when: string;  // in words
  first: number | null; last: number | null; day: number | null;  // 0-based; day: the worst
  days: number; what_if: boolean; worst_mw?: number; asked?: string;
}
```

Days short of heat or cold are grouped by their cause that day: a unit out for its planned
service or a doublet in its planned stop (that unit), else too little capacity (the side's top-up
unit: electric boiler, gas boiler, heat pump or exchanger; chillers or absorption). A failure
what-if asked in the chat on this design (`session.failures`) is its unit (`doublet 1` →
`producer_1`, `injector 1` → `injector_1`, `train 1` → its train, `boiler unit` → `boiler` …),
red when it leaves days short, amber when the rest of the plant covers it. A cap broken without a
shortfall (the brine cooled past the cap, a doublet's days or flow) is amber on the doublet's
injector or producer; one no part owns has `units: []`.
