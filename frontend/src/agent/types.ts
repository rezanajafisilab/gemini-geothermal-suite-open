// AG-UI events as the Dioscuri agent emits them (src/gemini_agent/events.py), plus the state
// the chat screen draws from them. Only the fields the UI reads are typed; the rest pass through.

export type StepKind = "model" | "tool" | "check" | "ask" | "plan" | "report";

export interface Question {
  id: string;
  label: string;
  hint?: string;
  options?: string[];
  default?: string | null;
  required?: boolean;
}

/** One option of a mid-run decision, as the agent describes it (clarification.details). */
export interface DecisionDetail {
  option: string;
  fix: string;
  code?: string;
  name?: string;
  /** Fraction of the heat demand covered, 0..1 (heat_coverage_pct is the same in percent). */
  heat_coverage?: number;
  heat_coverage_pct?: number;
  lcoh?: number | null;
  recommended?: boolean;
}

/** The spec of a component model the agent offers to write (clarification kind "offer"). */
export interface OfferDetail {
  component: string;
  title: string;
  inputs: string[];
  outputs: string[];
  physics: string[];
  sources: string[];
}

export interface Clarification {
  /**
   * "inputs": missing inputs before a design; "decision": pick how to go on mid-run;
   * "offer": write a missing component model?; "approval": use the generated model?;
   * "choice": the model didn't understand and offers readings, each a complete request;
   * "confirm": before the first design, run it with the inputs shown (CUSTOM "confirm_inputs")?
   */
  kind?: "inputs" | "decision" | "offer" | "approval" | "choice" | "confirm";
  intro: string;
  questions: Question[];
  details?: DecisionDetail[] | OfferDetail;
  /** Ties an offer to the approval of the same generated model. */
  generation_id?: string;
}

/** Where an input of the inputs card comes from (CUSTOM "confirm_inputs"). */
export type InputKind = "data" | "fixed" | "derived" | "assumed" | "asked";

/** One input the design will use: what it is, its value, where it comes from. */
export interface InputRow {
  /** "Demand", "Reservoir", "Brine and gas", "Caps", "Networks", "Costs", "Your request". */
  group: string;
  label: string;
  value: string;
  source: string;
  kind: InputKind | string;
  /** The user's last message changed it. */
  changed?: boolean;
  /** The planner parameters the row holds: the card's form edits these (card_edits.py). */
  fields?: InputField[];
  /** The switches the row holds (InputToggle ids), e.g. ["flare_brine_gas", "co2_reinjection"]. */
  toggles?: string[];
  /** Why a row with neither fields nor switches has nothing to change; shown on the card. */
  locked?: string;
  /** The card's page it goes on ("demand", "reservoir", ...); by its group when missing. */
  page?: string;
  /** What the row is, in a sentence the card shows under its name. */
  help?: string;
}

/** One column of a `records` field: a box per record, checked against its range. */
export interface RecordColumn {
  key: string;
  label: string;
  unit?: string;
  low?: number;
  high?: number;
  help?: string;
  /** Its usual values: outside them the card warns (as the old Aquifer boxes did). */
  typical?: [number, number];
  typical_words?: string;
}

/** One parameter of a row, as the card's form edits it (parameters.CATALOGUE). */
export interface InputField {
  /** The catalogue key the answer sends, e.g. "heat_return_c". */
  key: string;
  label: string;
  /** "number"; "choice"; "list": numbers, or several of `options`. */
  kind: "number" | "choice" | "list" | string;
  /** The catalogue's description. */
  hint?: string;
  unit?: string;
  /** The range, in the form's units (value × scale). */
  low?: number;
  high?: number;
  /** The form shows the value × scale (100: a fraction in per cent); the answer sends the value. */
  scale?: number;
  /** Whole numbers only (days, doublets). */
  whole?: boolean;
  options?: string[];
  words?: Record<string, string>;
  /** The value now, in the form's units; a `records` field: one object per record. */
  value: number | string | null | (number | string)[] | Record<string, number | null>[];
  /** The project's own value (every input at its default), in the same form: the card marks a
   * value that differs and can put it back (5 Nov). Missing from older servers. */
  default?: number | string | null | (number | string)[] | Record<string, number | null>[];
  /** What it is and what it changes in the design, in plain words (parameters.EXPLAINED). */
  help?: string;
  /** Its usual values (form units): outside them the card warns, and says them in words. */
  typical?: [number, number];
  typical_words?: string;
  /** What it is linked to: what it depends on, or what follows from it. */
  depends?: string;
  /** The parameters linked to it, both ways (keys), and what it changes in the design. */
  linked?: string[];
  affects?: string[];
  /** The challenge's limit (form units): outside it the design does not meet the challenge. */
  cap?: { low?: number; high?: number; words?: string };
  /** An empty box blocks the run. */
  required?: boolean;
  /** kind "records": the columns, and how many records (e.g. aquifers) the list may hold. */
  columns?: RecordColumn[];
  min_items?: number;
  max_items?: number;
  /** kind "records": what each record is ("known", "assumed", "given") and a note on it. */
  kinds?: string[];
  notes?: string[];
  /** kind "records": the server's warnings on the records as they are now. */
  warnings?: string[];
  /** kind "records": a new record's start; a box left empty is filled by the server. */
  new_item?: Record<string, number | null>;
}

/** The numbers the card works out consequences from as the user types (card_edits.context). */
export interface CardContext {
  surface_c?: number;
  depth_m?: number;
  heat_gwh?: number;
  heat_peak_mw?: number;
  cool_gwh?: number;
  cool_peak_mw?: number;
  rock_bar_per_m?: number;
}

/**
 * The inputs card (CUSTOM "confirm_inputs"): before the first design the agent shows what it
 * read and what it assumes, then asks (clarification kind "confirm") to run with them.
 */
export interface ConfirmInputs {
  rows: InputRow[];
  /** The parameter keys the last message changed, e.g. ["heat_return_c"]. */
  changed: string[];
  /** [run, change]: "Run the design with these inputs", "Change an input first". */
  options: string[];
  /** Each kind in words, e.g. {assumed: "Dioscuri's assumption"}. */
  kinds: Record<string, string>;
  /** Switches the card offers before the run: network heat losses (km), planned service, stops. */
  toggles?: InputToggle[];
  /** The card's own changes code refused, by key ("doublet_stops" for the dates): why. */
  errors?: Record<string, string>;
  /** The refused values as the answer sent them, shown again on their fields. */
  asked?: Record<string, unknown>;
  /** Sent after Run with changes: the rows as they ran (no question follows). */
  applied?: boolean;
  /** "Another design" with nothing changed: the search these inputs already ran (the card opens to edit). */
  again?: { search: string; label: string } | null;
  /** The card's pages in order (the review page is the card's own). */
  pages?: { id: string; title: string }[];
  /** Warnings for the values now, by key (outside the challenge's caps or typical values). */
  warnings?: Record<string, string>;
  context?: CardContext;
  /** The parameters the user set (their value is not the project's own): marked, with what they affect. */
  yours?: string[];
  /** What a typed reply did, said at the card's top: a change refused (nothing changed), or the
   * inputs put back to the project's defaults (5 Nov). */
  notice?: CardNotice | null;
  /** True when every input is the project's own: nothing for "Reset to defaults" to do. */
  at_defaults?: boolean;
}

/** The inputs card's note on what a typed reply did. */
export interface CardNotice {
  /** "refused": nothing (or not all) of the reply was taken; "reset": back to the defaults. */
  kind: "refused" | "reset" | string;
  title: string;
  lines: string[];
  /** What can be done next, in a sentence. */
  offer?: string;
}

/** A switch on the inputs card; its value goes back with the Run answer under its id. */
export interface InputToggle {
  id: string;
  label: string;
  /** "km": a switch with a length; "amount": a switch with a size in `unit` (solar MWp, a store's
   * MWh); "switch": on or off; "stops": the doublets' stop dates. */
  kind: "km" | "amount" | "switch" | "stops" | string;
  value: number;
  hint?: string;
  /** kind "amount": its unit, range, step and an example for the empty box. */
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  example?: string;
  /** kind "stops": the user's dates now, per doublet [first, last] days of the year (0-based). */
  stops?: number[][][];
  /** kind "stops": a start for "My dates", one block per doublet in the quietest heat weeks. */
  suggested?: number[][][];
  /** kind "stops": how many doublets to give dates for. */
  doublets?: number;
  /** kind "stops": the days each doublet may run (365 − this = its days off). */
  operating_days?: number;
  year?: number;
  /** kind "maintenance": each doublet's days off (its own, else the cap's 35). */
  days_off?: number[];
  default_days_off?: number;
  /** kind "maintenance": the challenge's cap on operating days (330). */
  cap_operating_days?: number;
  /** kind "maintenance": every unit type's yearly service (off, Dioscuri's weeks, or dates). */
  units?: { unit: string; label: string; days: number; bank: boolean; mode: "off" | "auto" | "dates" | string; ranges: number[][] }[];
  /** The card's page and the row it sits in; its plain words (as InputField's). */
  page?: string;
  row?: string;
  help?: string;
  typical_words?: string;
  depends?: string;
}

/** A generated model run at the design's conditions (CUSTOM "model_result"). */
export interface ModelResult {
  component: string;
  title: string;
  cases: Record<string, number | string | null>[];
  outputs: Record<string, number | string | null>[];
  assumed: string[][];
  units: Record<string, string>;
  checks: Check[];
  warnings: string[];
}

/** A clarification in its turn: the run that asked it and the answers sent to it. */
export interface Ask {
  run: number;
  value: Clarification;
  answers?: Record<string, string>;
  skipped?: boolean;
}

/**
 * How the answerer read and wrote one reply (CUSTOM "answer"): a local model writes every chat
 * reply from a context pack, and code checks its numbers and citations.
 */
export interface AnswerMeta {
  /** The model's one-line reading of the message. */
  understood?: string;
  kind?: "answer" | "clarify" | "nonsense" | "out_of_scope";
  /** "project": drawn from this project's data; "general": background knowledge; "out": neither. */
  scope?: "project" | "general" | "out";
  /** Context items the reply drew on: "self", design codes ("A1"), passages ("doc1"). */
  used?: string[];
  model?: string;
  device?: "gpu" | "cpu";
  /** The model was unavailable or failed the checks twice: the checked template was shown. */
  fallback?: boolean;
  /** What code changed in the model's text, e.g. "removed a sentence with an unsourced number (17)". */
  corrections?: string[];
  /** The claim checker's verdict: sentences it checked, and those it took out of the reply. */
  claims?: { checked: number; removed: string[] };
}

/**
 * STEP_FINISHED metadata of the claim checker ("claims", after "answer"): a model reads each
 * sentence of the reply against its sources; unsupported ones are taken out before it is sent.
 */
export interface ClaimsMeta {
  decided_by?: "model" | "skipped";
  /** Sentences sent to the checker. */
  checked?: number;
  supported?: number;
  /** General background, kept without a source. */
  general?: number;
  removed?: number;
  removed_sentences?: string[];
  /** Sentences mended rather than removed: [as written, as it now reads] (5 Nov). */
  reworded?: number;
  reworded_sentences?: [string, string][];
  model?: string;
  device?: string;
  note?: string;
}

/** An answerer reply in its turn: the run it came in and, when known, its text message. */
export interface Reply {
  run: number;
  message?: string;
  value: AnswerMeta;
}

/** A passage the agent cited (CUSTOM "sources"). Answers cite it as [^n], n its 1-based place. */
export interface Passage {
  source: string;
  section: string;
  text: string;
  score?: number;
  /** Instruction-like text: shown as flagged data, never followed. */
  suspicious?: boolean;
  /** GEMINI docs, a team note, an upload or a project data file. */
  kind?: "doc" | "note" | "file" | "data";
  /** A file the user can open (GET /api/files?view=1). */
  file?: string;
  /** Figures in that docs section, e.g. "/api/doc-image?path=src/gemini_documentation/source/images/x.png". */
  images?: { url: string; caption: string }[];
}

export interface FileColumn {
  name: string;
  type: "number" | "date" | "text";
  unit: string;
}

/**
 * A file the agent opened in a run (CUSTOM "file"), and what GET /api/files?view=1 returns: its
 * first rows, column stats, totals, a downsampled chart and a text or image preview.
 */
export interface FileView {
  name: string;
  kind: "table" | "json" | "text" | "image" | "binary";
  origin: "project" | "attachment";
  /** The raw file, e.g. "/api/files?threadId=abc&name=heating_profile.csv". */
  url: string;
  size_bytes: number;
  /** The view the user asked for: the card opens on it. */
  show: "table" | "chart" | "image" | "text";
  /** e.g. "The organisers' file for the challenge (synthetic demand for 2027)." */
  note?: string;
  table?: {
    columns: FileColumn[];
    /** The first rows only (at most 200). */
    rows: (string | number | null)[][];
    total_rows: number;
    truncated: boolean;
  };
  stats?: { column: string; unit: string; min: number; max: number; mean: number }[];
  /** e.g. {column: "heat_demand_mw", label: "Energy over the file", value: 61.8, unit: "GWh"}. */
  totals?: { column: string; label: string; value: number; unit: string }[];
  chart?: {
    x: string;
    x_type: "date" | "number" | "index";
    /** At most 400 points, already downsampled. */
    x_values: (string | number)[];
    series: { name: string; unit: string; values: (number | null)[] }[];
  };
  /** kind json or text: a pretty preview (at most 6000 characters). */
  text?: string;
  image?: { url: string; width?: number; height?: number };
}

/** One attempt of the model generator (CUSTOM "modelgen_attempt"). */
export interface GenAttempt {
  number: number;
  reason: string;
  code: string;
  violations: string[];
  error: string;
  case_errors: string[];
  checks: Check[];
  outputs?: Record<string, number>[] | null;
  sandbox_seconds?: number;
  passed: boolean;
}

/** The generated model awaiting approval (CUSTOM "model_approval"). */
export interface Generation {
  component: string;
  model: string;
  prompt_version?: string;
  passed: boolean;
  code: string;
  checks: Check[];
  table: Record<string, number | string | null>[];
  attempts: GenAttempt[];
  tokens: { prompt?: number; output?: number } | number;
  seconds: number;
}

export interface Kpi {
  id: string;
  label: string;
  value: number | null;
  unit: string;
}

/** Energy per month, Jan..Dec, in GWh: the demand and what each source supplied. */
export interface MonthlyGwh {
  /** `electric_boiler`: a gas-free design's electric boiler, when the card sends it. */
  heat: { demand: number[]; geo: number[]; hp: number[]; boiler: number[]; electric_boiler?: number[] };
  cool: { demand: number[]; abs: number[]; chill: number[] };
}

/** How one doublet is built (a result card's `doublets`, a parameters step's `doublets`). */
export interface DoubletBuild {
  /** null: the known aquifer (as the user described it, before the plan fills it in). */
  depth_m?: number | null;
  /** The part of the aquifer the producer / injectors are open to. */
  producer_open?: "full" | "upper" | "lower" | string;
  injector_open?: "full" | "upper" | "lower" | string;
  injectors?: number;
  max_flow_m3h?: number | null;
  /** The treatment train (separator, filters) it feeds, from 0; doublets with the same one share it. */
  train?: number | null;
}

/** One of a search's six picks (best overall, cheapest, lowest CO₂, cheapest reliable, greenest reliable, gas-free), for the card. */
export interface Pick {
  key: "best" | "cost" | "co2" | "reliable" | "green_reliable" | "gas_free" | string;
  label: string;
  /** The design's name in the chat ("A1") and its code. */
  uid: string;
  code: string;
  id: string;
  chosen: boolean;
  lcoe: number;
  lcoh: number;
  lcoc: number | null;
  co2_t: number;
  co2_saving_pct: number;
  capex_meur: number;
  /** Sized so that any one unit can be out (the reliable plan). */
  reliable: boolean;
  /** One-unit-out cases that leave a day short. */
  n1_short?: number | null;
  /** How this pick is chosen, in words. */
  rule: string;
  vs_gas_pct?: { heat: number | null; cold: number | null; total: number | null } | null;
}

/** One unit out all year (N-1), as the card lists it. */
export interface OutageCase {
  unit: string;
  short: boolean;
  side: "heat" | "cool";
  worst_mw: number;
  worst_day: string | null;
  days_short: number;
  short_gwh: number;
}

/** A design's firm capacity: the spare on its peak days and each one-unit-out case. */
export interface Firm {
  peak: Partial<Record<"heat" | "cool", { day: string; demand_mw: number; capacity_mw: number; spare_mw: number }>>;
  cases: OutageCase[];
  /** How many cases leave a day short. */
  short: number;
  reliable: boolean;
  boiler_units: number;
  chiller_units: number;
}

/** What a what-if's new search picked, against the design it changed. */
export interface Research {
  code: string;
  uid: string;
  id: string;
  lcoe: number;
  base_code: string;
  base_id: string;
  changed: boolean;
  objective: string;
}

export interface ResultCard {
  alternative: string;
  /** The design's name in the chat: A1, A2 … (a search, ranked), W1 … (what-ifs), U1 … (yours). */
  uid?: string;
  name: string;
  source?: string;
  verified: boolean;
  checks: { passed: number; total: number };
  /** The names of the checks it fails (the verifier's), for its status in words. */
  failed?: string[];
  kpis: Kpi[];
  heat_split_gwh: Record<string, number>;
  cool_split_gwh: Record<string, number>;
  sizes_mw: Record<string, number>;
  temperatures_c?: Record<string, number>;
  demand_gwh?: { heat?: number; cold?: number };
  /** Missing in streams recorded before 28 Oct: the card then has no monthly chart. */
  monthly_gwh?: MonthlyGwh | null;
  /** "compact": a what-if, drawn as one row against the design it changed; the default is the full report. */
  view?: "full" | "compact";
  /** The design a compact card is compared with (the chat's chosen one). */
  against?: ResultCard;
  /** The design's id in the tabs: the code, or "<code> · <change label>" for a what-if. */
  design_id?: string;
  /** A what-if's change in words ("heating return temperature 50 °C"); "" for a design. */
  change_label?: string;
  /** A what-if's changes, parameter key to value ({heat_return_c: 50}). */
  changes?: Record<string, unknown>;
  /** The variant flags in the code, e.g. ["2I1", "ST"] (numbers.ts: flagMeaning). */
  flags?: string[];
  doublets?: DoubletBuild[];
  /** How two or more doublets share the brine: equal shares, or the hottest first. */
  dispatch?: "equal" | "base" | string;
  /** The search's four picks (on a design run's card). */
  picks?: Pick[];
  /** The picks this design is. */
  my_picks?: string[];
  reliable?: boolean;
  firm?: Firm | null;
  /** A what-if: what the search under the change picks. */
  research?: Research | null;
  /** Costs against the gas reference of the same conditions, signed fractions (−0.17: 17 % cheaper). */
  vs_gas_pct?: { heat: number | null; cold: number | null; total: number | null } | null;
  /** The district network's losses, when the inputs card switched them on. */
  network?: { length_km: number; heat_dn: number; heat_loss_gwh: number; heat_loss_share: number; supply_c_max: number; supply_c_peak_day: number; pump_gwh: number; cool_free_gwh: number } | null;
  /** Planned service windows, when switched on. */
  service?: { unit: string; from: string; to: string }[];
  /** Own solar panels (inputs card): what they make, what the plant uses and sells, GWh a year. */
  solar?: { mwp: number; generated_gwh: number; used_gwh: number; sold_gwh: number; bought_gwh: number } | null;
  /** Minimum loads and trips: each unit's days below its minimum load and its starts; ESP trips' heat. */
  operability?: {
    units: { kind: string; name: string; minimum_mw: number; days_below: number; days_on: number; starts: number }[];
    trips: { per_doublet_year: number; hours_each: number; boiler_gwh: number };
    source: string;
  } | null;
  /** The hot-water store (inputs card): GWh charged, given back and lost; the boiler's heat it saved. */
  storage?: { capacity_mwh: number; charged_gwh: number; given_gwh: number; lost_gwh: number; boiler_saved_gwh: number; full_cycles?: number; power_mw?: number; note?: string } | null;
  /** GEMINI's own run of the brine loop against the plant model. */
  gemini_check?: {
    ok: boolean;
    error?: string | null;
    agree: number;
    total: number;
    rows: { quantity: string; unit: string; gemini: number; plant: number; diff_pct: number; agree: boolean; note: string }[];
  } | null;
  /** The cooling component model run on the chillers and towers, against ours (``cooling_check``). */
  cooling_check?: {
    model: string;
    weather: string;
    cop: number;
    cold_gwh: number;
    unmet_gwh: number;
    compressor_gwh: number;
    towers_gwh: number;
    electricity_gwh: number;
    makeup_water_m3: number;
    evaporation_m3: number;
    blowdown_m3: number;
    ours: { cold_gwh: number; chillers_gwh: number; towers_gwh: number; chiller_cop: number };
    /** The absorption chiller run on the brine our model gives it (its share from the heat side). */
    absorption?: { cold_gwh: number; drive_gwh: number; cop: number; ours_cold_gwh: number; ours_drive_gwh: number; ours_cop: number; hot_loop_c: number[] } | null;
    limits: Record<string, number>;
    not_checked: string[];
  } | null;
}

/** A failure what-if (CUSTOM "failure"): units out on given days, what it does, what would help. */
export interface FailureView {
  design: string;
  code: string;
  events: { unit: string; words: string; first: number; last: number; from: string; to: string; days: number; how: string; assumed: string }[];
  failed: {
    heat: { days_short: number; worst_mw: number; worst_day: string | null; short_gwh: number };
    cool: { days_short: number; worst_mw: number; worst_day: string | null; short_gwh: number };
    days: { day: string; heat_demand_mw: number; heat_short_mw: number; boiler_mw: number; cool_short_mw: number }[];
    boiler_full: boolean;
    extra_gas_gwh: number;
    extra_co2_t: number;
    extra_cost_keur: number;
  };
  needed: boolean;
  remedies: { key: string; name: string; heat_short_mw: number; cool_short_mw: number; short_gwh: number; covers: boolean; capex_meur: number; yearly_keur: number; lcoe_delta?: number }[];
  best: string | null;
  spare_esp?: { name: string; gas_saved_gwh: number; co2_saved_t: number; money_saved_keur: number; yearly_keur: number; capex_meur: number } | null;
  reliable_plan?: string | null;
  /** Failures over a year on average (``reliability.yearly_view``): cost per unit, a spare ESP. */
  yearly?: FailureYear | null;
}

/** What failures cost a design a year on average (expected over every start day). */
export interface FailureYear {
  /** Without a spare ESP (as designed), k€ a year; ``range_keur`` over the failure rates' ranges. */
  total_keur: number;
  range_keur: [number, number];
  lost_mwh: number;
  lost_heat_mwh: number;
  lost_cold_mwh: number;
  /** What a MWh not delivered is valued at (the lost sale), and the stress value and cost. */
  lost_eur_per_mwh: number;
  stress_keur: number;
  stress_eur_per_mwh: number;
  with_spare_keur: number;
  with_spare_mwh: number;
  /** Largest first; total = running (gas, power, CO2) + not delivered + repairs. */
  units: {
    unit: string;
    label: string;
    words: string;
    failures_per_year: number;
    repair_days: number;
    out_days: number;
    running_keur: number;
    /** The electric boiler's grid charge when an outage pushes it past 600 hours (0 otherwise). */
    grid_keur?: number;
    lost_mwh: number;
    lost_keur: number;
    repair_keur: number;
    total_keur: number;
  }[];
  spare_esp: {
    per_year: number;
    swap_days: number;
    no_spare_days: number;
    price_meur: number;
    life_years: number;
    yearly_keur: number;
    saving_keur: number;
    saving_mwh: number;
    net_keur: number;
    worth: boolean;
    break_even_per_year: number | null;
    stress_net_keur: number;
    range: { low: { per_year: number; net_keur: number }; high: { per_year: number; net_keur: number } };
    /** The failure rate and the break-even rate in words: "once every 2 years". */
    every: string;
    break_even_every: string | null;
  } | null;
  skipped: string[];
  notes: string[];
}

/** How sure a design's result is (CUSTOM "uncertainty"): Monte Carlo ranges and the tornado. */
export interface UncertaintyView {
  design: string;
  base: { lcoe?: number; npv_meur?: number; co2_saving_pct?: number };
  lcoe?: { p10: number; p50: number; p90: number; above_zero: number } | null;
  npv?: { p10: number; p50: number; p90: number; above_zero: number } | null;
  samples?: number;
  tornado: { key: string; label: string; unit: string; from: number; to: number; lcoe_low: number; lcoe_high: number }[];
}

/** A request's steps as planned and run (CUSTOM "plan"): the plan card. */
export interface PlanView {
  steps: { n: number; do: string; label: string; status: "todo" | "done" | "skipped" | string }[];
}

/** The options for a decision (CUSTOM "decision"): gas, the recommended design and the picks. */
/** An operator's report (PDF) the agent made for a design: the card downloads it. */
export interface ReportView {
  id: string;
  code: string;
  name: string;
  /** GET /api/report.pdf?threadId=…&id=… (the server builds it again for the download). */
  url: string;
  file: string;
  pages: number;
  kb: number;
  sections: string[];
}

export interface DecisionView {
  rows: {
    label: string;
    id: string;
    capex_meur: number;
    lcoe: number;
    vs_gas: number | null;
    yearly_meur: number;
    per_home_eur: number;
    co2_t: number;
    co2_cut: number | null;
    gas_share: number;
    n1: number | null;
    eur_per_t: number | null;
    reliable: boolean;
  }[];
  home_words: string;
  homes: number | null;
}

/** Designs side by side (CUSTOM "compare"): one row per figure, the best of each marked. */
export interface CompareView {
  /** True when the designs come from different conditions: money rows are not ranked. */
  mixed?: boolean;
  designs: { id: string; code: string; name: string; picks: string[]; reliable: boolean; scenario?: string }[];
  rows: { key: string; label: string; unit: string; digits: number; values: (number | null)[]; best: number | null }[];
}

/** One design in the comparison (CUSTOM "comparison"). Costs in €/MWh, capital in M€. */
export interface ComparedDesign {
  code: string;
  name: string;
  verified: boolean;
  /** The names of the checks it fails. */
  failed?: string[];
  lcoh: number;
  lcoc: number | null;
  co2_saving_pct: number;
  heat_coverage_pct: number;
  cool_coverage_pct: number;
  capex_meur: number;
  /** A what-if run: the reservoir this much warmer (+) or colder (−) than expected. */
  reservoir_delta_c: number;
  /** The gas boiler and electric chillers reference. */
  reference: boolean;
  source: string;
}

/** One candidate of the agent's design search (CUSTOM "candidates"). */
export interface SearchCandidate {
  code: string;
  name: string;
  /** chosen, candidate (valid but lost), failed (broke a cap), reference. */
  role: string;
  /** Why it lost, in numbers, or the cap it broke. */
  reason: string;
  n_doublets: number;
  depth_m: number;
  topup: string | null;
  cooling: string | null;
  sizes_mw: Record<string, number>;
  lcoh: number;
  lcoc: number | null;
  /** Heat and cold together, €/MWh. */
  lcoe: number;
  co2_t: number;
  co2_saving_pct: number;
  capex_meur: number;
  /** Runs of the improvement loop. */
  rounds: number;
  changes: string[];
  violations: string[];
  checks: { passed: number; total: number };
}

/** The search behind a design (CUSTOM "candidates"): what the agent tried, and why it picked one. */
export interface Search {
  objective: "cost" | "co2" | string;
  chosen: string | null;
  reference: SearchCandidate;
  /** The chosen one first, then the valid ones by the objective, then the failed ones. */
  candidates: SearchCandidate[];
  summary: { candidates: number; valid: number; failed: number; improved: number; rounds: number; depths: number[]; objective: string };
  notes: string[];
  /** Drawn as a card in the chat only when the message asked how the design was found (3 Nov). */
  show?: boolean;
}

/** Sent after the result card when a run reports a design and two or more designs exist. */
export interface Comparison {
  /** The design the run reports, listed first. */
  chosen: string | null;
  designs: ComparedDesign[];
}

export interface Check {
  name: string;
  passed: boolean;
  detail: string;
  requirement?: boolean;
}

export interface UsageCall {
  purpose: string;
  model: string;
  prompt_tokens: number;
  output_tokens: number;
  seconds: number;
  load_seconds?: number;
  prompt_seconds?: number;
  output_seconds?: number;
  ok: boolean;
  error?: string;
}

/** RUN_FINISHED.result: the run summary the agent also writes to its trace. */
export interface RunSummary {
  behaviour?: string | null;
  asked?: string[];
  answer?: string;
  ungrounded?: number[];
  dropped?: string[];
  verified?: boolean | null;
  intent?: string;
  language?: string;
  seconds?: number;
  llm_calls?: number;
  prompt_tokens?: number;
  output_tokens?: number;
  model?: string;
  error?: string;
  tool_calls?: number;
  cache_hits?: number;
  tool_errors?: number;
  /** Designs left out of the answer and why, e.g. "A2: simulate_year failed: ...". */
  left_out?: string[];
  user_turns?: number;
  /** An off-topic message refused by the keyword screen, with no model call. */
  screened?: boolean;
  prompt_version?: string;
  load_seconds?: number;
  prompt_seconds?: number;
  output_seconds?: number;
  /** Reasoning mode was on for this run. */
  reasoning?: boolean;
  /** The GPU's energy while the run ran (Wh, nvidia-smi; the whole GPU, an upper bound). */
  energy_wh?: number;
  energy_source?: string;
  /** Who took each decision step: {plan: "model" | "rules", ...}. */
  decided_by?: Record<string, "model" | "rules">;
  /** Model calls, e.g. ["intake: qwen3:1.7b", "plan: qwen3.5:9b"]. */
  calls?: string[];
  plan?: string[] | null;
  recommended?: string | null;
  /** The template answer, when the reasoning model reworded it. */
  draft?: string;
}

/** CUSTOM `model_unavailable`: the model can't answer; `fix` is the command that fixes it. */
export interface Unavailable {
  model: string;
  error: string;
  fix: string;
  /** "rules": the reasoning model is missing, rules decided and the run went on. */
  fallback?: string;
  /** Why: "not_pulled", "timeout" or "not_running". */
  reason?: "not_pulled" | "timeout" | "not_running" | string;
  /** The run it arrived in (set by the reducer). */
  run?: number;
}

/** A result card and its checks, as one run sent them. */
export interface CardOut {
  run: number;
  result: ResultCard;
  checks?: Check[];
}

interface Base {
  timestamp?: number;
}

export type AgEvent =
  | (Base & { type: "RUN_STARTED"; threadId: string; runId: string })
  | (Base & {
      type: "RUN_FINISHED";
      threadId: string;
      runId: string;
      outcome?: { type: "success" | "interrupt"; interrupts?: { id: string; reason: string }[] };
      usage?: { model: string; inputTokens: number; outputTokens: number; totalTokens: number }[];
      result?: RunSummary;
    })
  | (Base & { type: "RUN_ERROR"; message: string; code?: string })
  | (Base & {
      type: "STEP_STARTED";
      stepName: string;
      metadata?: { label?: string; kind?: StepKind; code?: string | null };
    })
  | (Base & { type: "STEP_FINISHED"; stepName: string; metadata?: Record<string, unknown> })
  | (Base & { type: "TOOL_CALL_START"; toolCallId: string; toolCallName: string })
  | (Base & { type: "TOOL_CALL_ARGS"; toolCallId: string; delta: string })
  | (Base & { type: "TOOL_CALL_END"; toolCallId: string })
  | (Base & { type: "TOOL_CALL_RESULT"; toolCallId: string; content: string })
  | (Base & { type: "TEXT_MESSAGE_START"; messageId: string; role?: string })
  | (Base & { type: "TEXT_MESSAGE_CONTENT"; messageId: string; delta: string })
  | (Base & { type: "TEXT_MESSAGE_END"; messageId: string })
  | (Base & { type: "CUSTOM"; name: string; value: unknown });

export type StepStatus = "active" | "done" | "waiting" | "stopped" | "error";

export interface ToolCall {
  id: string;
  name: string;
  args: string;
  result?: string;
  /** The tool raised: TOOL_CALL_RESULT content was {"cached": false, "error": "..."}. */
  error?: string;
  cached?: boolean;
  done: boolean;
}

export interface Step {
  /** Unique within the turn: stepName plus the run it belongs to. */
  key: string;
  name: string;
  label: string;
  kind: StepKind;
  code?: string | null;
  status: StepStatus;
  run: number;
  startedAt?: number;
  seconds?: number;
  meta: Record<string, unknown>;
  tools: ToolCall[];
}

export interface Message {
  id: string;
  run: number;
  text: string;
  /** How many steps the turn had when the message started (pairs it with its "answer" event). */
  steps?: number;
}

export interface RunRecord {
  runId: string;
  startedAt?: number;
  outcome?: "success" | "interrupt";
  summary?: RunSummary;
  tokens: number;
}

export type TurnStatus = "running" | "waiting" | "done" | "error" | "stopped";

/** A file sent with a message: shown under that message only (the agent searches it for the rest of the chat). */
export interface TurnAttachment {
  name: string;
  kind: "image" | "text";
  /** Passages indexed, for text; unknown while it uploads. */
  chunks?: number;
  /** Still uploading when the message was sent: the run waits for it. */
  uploading?: boolean;
}

export interface Turn {
  id: string;
  message: string;
  /** The files attached since the previous message, sent with this one. */
  attachments?: TurnAttachment[];
  /** The designs picked with @ for this message: [id, "A1 · Best overall"]. */
  designs?: { id: string; text: string }[];
  createdAt: number;
  /** Client time of the last send or answer, for the live elapsed-time chip. */
  activeSince: number;
  /** Sent in reasoning mode. */
  reasoning?: boolean;
  status: TurnStatus;
  runs: RunRecord[];
  steps: Step[];
  messages: Message[];
  usage: UsageCall[];
  clarification?: Clarification;
  /** The run the clarification arrived in: its outputs come before the card. */
  clarificationRun?: number;
  /** Every clarification of the turn in order (an offer, then an approval, ...). */
  asks?: Ask[];
  /** Cited passages, per run. */
  sources?: { run: number; passages: Passage[] }[];
  /** Files the agent opened, per run (CUSTOM "file"). */
  files?: { run: number; file: FileView }[];
  /** How the answerer read and wrote each reply (CUSTOM "answer"), per run. */
  replies?: Reply[];
  /** Model generation: its attempts as they arrive, then the result to approve. */
  attempts?: GenAttempt[];
  generation?: Generation;
  /** Generated models' results, per run. */
  results?: { run: number; value: ModelResult }[];
  /** Every result card of the turn (a decision turn has one before and one after). */
  cards: CardOut[];
  /** The designs compared (CUSTOM "comparison"), one per run. */
  comparisons?: { run: number; value: Comparison }[];
  /** Failure what-ifs (CUSTOM "failure") and designs side by side (CUSTOM "compare"), by run. */
  failures?: { run: number; value: FailureView }[];
  compares?: { run: number; value: CompareView }[];
  /** The plan card (one per run, the latest status) and decision tables, by run. */
  plans?: { run: number; value: PlanView }[];
  decisions?: { run: number; value: DecisionView }[];
  uncertainties?: { run: number; value: UncertaintyView }[];
  /** Operator's reports made in the chat (CUSTOM "report"), by run. */
  reports?: { run: number; value: ReportView }[];
  /** The design search behind a run (CUSTOM "candidates"), one per run. */
  searches?: { run: number; value: Search }[];
  /**
   * The inputs to confirm (CUSTOM "confirm_inputs"), one per run, with the text message it
   * replaces (the same inputs as a Markdown table, kept for a client without the card).
   */
  confirms?: { run: number; value: ConfirmInputs; message?: string }[];
  /** The answers sent to the clarification, by question id. */
  answers?: Record<string, string>;
  result?: ResultCard;
  checks?: Check[];
  suggestions?: string[];
  error?: { message: string; code?: string };
  unavailable?: Unavailable;
  /** The user sent a new message instead of answering the clarification. */
  skipped?: boolean;
}

export interface ChatState {
  threadId: string;
  turns: Turn[];
}

export type Action =
  | { type: "send"; turnId: string; message: string; at: number; reasoning?: boolean; attachments?: TurnAttachment[]; designs?: { id: string; text: string }[] }
  /** The sent files once their uploads settle: final passage counts, failed ones left out. */
  | { type: "attachments"; turnId: string; attachments: TurnAttachment[] }
  | { type: "answer"; answers: Record<string, string>; at: number }
  | { type: "event"; event: AgEvent }
  | { type: "stopped" }
  | { type: "failed"; message: string; code?: string };
