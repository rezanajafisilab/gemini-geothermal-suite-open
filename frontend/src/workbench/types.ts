// The workbench API's shapes (hackathon/docs/workbench_api.md, version 2, 30 Oct 2026). The chat
// and the tabs share one store: the designs of a conversation. Keep this file in step with the
// contract; the tabs import their types from here only.

// ------------------------------------------------------------------ designs

/** Who produced a group of numbers: GEMINI's solver, Dioscuri's plant model, the user, or a rule. */
export type Provenance = "gemini" | "dioscuri" | "user" | "rule";

/** The field groups `Design.provenance` describes. */
export type ProvenanceKey = "plant" | "year" | "economics" | "cooling";

export interface Workbench {
  threadId: string;
  /** What computes the wells: GEMINI's solver (with the team's patches). */
  physics: "gemini";
  gemini: { version: string; patches: string[] } | null;
  /** The conversation's prices and costs, defaults where not changed. */
  assumptions: Assumptions;
  /** [] for a new chat; the chosen one has chosen: true. Then what-ifs and user designs. */
  designs: Design[];
  /** The design the chat ran last (a what-if, the user's, or the pick): the tabs' default. */
  latest?: string | null;
  /** The last search's candidates (the chosen one first), each with why it lost. */
  candidates?: Candidate[];
  /** Gas boilers and electric chillers: the baseline every saving is measured against. */
  reference?: Candidate | null;
  /** Every design search of the chat, newest first; `candidates` and `reference` above are the newest's. */
  attempts?: Attempt[];
  /** Every design of the chat (each search's candidates, every what-if and user design), for the Compare tab. */
  library?: LibraryRow[];
}

// ------------------------------------------------------------------ the design library (Compare)

/** The assumptions a library row was computed under: the base case, a what-if, another search, or yours. */
export interface LibraryScenario {
  /** "S1" (a search), "w:<change>" (a what-if on a design), "user". */
  id: string;
  /** A search's run: its letter (the designs' handles start with it, A1) and its name ("Run A · Base case"). */
  letter?: string;
  name?: string;
  /** The search's number (1, 2 …); 0 when it is not a search. */
  n: number;
  kind: "base" | "what_if" | "search" | "user" | string;
  /** "Base case", "What-if: gas price 30 EUR/MWh", "Search 3: …", "Your designs". */
  label: string;
  /** The figures were run again at the conversation's current prices (the picks stay the search's). */
  repriced?: boolean;
}

/** A design against gas boilers and electric chillers of the same scenario. */
export interface LibraryMoney {
  extra_capex_meur: number;
  savings_meur_per_year: number;
  /** Discounted; null when it never pays back. */
  payback_years: number | null;
  simple_payback_years: number | null;
  npv_meur: number;
  /** A fraction (0.14 = 14%); null when there is none. */
  irr: number | null;
  years: number;
}

/** One-unit-out (N-1) results: how many cases leave a day short, and the worst. */
export interface LibraryFirm {
  cases: number;
  /** Cases that leave a day short; 0: N-1 met. */
  short: number;
  worst: { unit: string; side: "heat" | "cool" | string; mw: number; day: string | null } | null;
  /** Spare on the peak day, MW. */
  spare_heat_mw: number | null;
  spare_cool_mw: number | null;
}

/** One design of the conversation as the Compare tab's library lists it (GET /api/workbench, `library`). */
export interface LibraryRow {
  /** "A1 · 1D-HP-EC-N1": the id the tabs and routes use. */
  id: string;
  /** What it is in words, or the user's name for it (see Design.label). */
  label?: string;
  user_name?: string | null;
  starred?: boolean;
  /** "A1". */
  uid: string;
  code: string;
  name: string;
  scenario: LibraryScenario;
  origin: "agent" | "what_if" | "user" | string;
  role: "chosen" | "candidate" | "failed" | "what_if" | "user" | string;
  /** The search's picks it is: best, cost, co2, reliable. */
  picks: string[];
  /** The chat's current design. */
  recommended: boolean;
  /** Already openable in Design and Economics (else POST /api/designs/open first). */
  in_tabs: boolean;
  /** Sized so that any one unit can be out (an N-1 plan). */
  reliable: boolean;
  n_doublets: number;
  depth_m: number;
  flags?: string[];
  topup: string | null;
  cooling: string | null;
  sizes_mw: Record<string, number>;
  /** Cost of heat and cold together, €/MWh: the headline. */
  lcoe: number | null;
  lcoh: number | null;
  lcoc: number | null;
  co2_t: number | null;
  co2_saving_pct: number | null;
  capex_meur: number | null;
  wells?: number | null;
  trains?: number | null;
  verified: boolean;
  /** The names of the checks it fails (the verifier's). */
  failed?: string[];
  violations: string[];
  /** Why it lost to the chosen one, or the cap it broke. */
  reason?: string;
  /** The design it came from: a what-if's base ("A1 · …"), your design's original, a variant's layout. */
  parent?: string | null;
  /** Signed fractions against the gas plant of the same scenario: −0.17 is 17% cheaper. */
  vs_gas_pct: { heat: number | null; cold: number | null; total: number | null } | null;
  money: LibraryMoney | null;
  firm: LibraryFirm | null;
  heat_coverage_pct?: number;
  cool_coverage_pct?: number;
  attempt?: string | null;
}

/** One design search of the chat (contract ``Attempt``): S1, S2 … */
export interface Attempt {
  id: string;
  /** 1, 2 … in the order asked. */
  n: number;
  /** The run's letter (its designs' handles start with it) and its name ("Run B · What-if: …"). */
  letter?: string;
  name?: string;
  /** Epoch seconds; null when the server didn't record it. */
  at: number | null;
  /** The user's request, at most 200 characters. */
  message: string;
  /** "lowest cost · 1–3 doublets · 2,500, 3,000 and 3,500 m" */
  label: string;
  objective: "cost" | "co2";
  /** The code of the design it chose, or null when no plant met every cap. */
  chosen: string | null;
  /** Only the newest attempt is priced at the chat's current assumptions; older ones keep their day's prices. */
  repriced: boolean;
  /** How wide the search went: layouts tried, sizings of them, years simulated (older servers leave them out). */
  layouts?: number;
  sizings?: number;
  years?: number;
  candidates: Candidate[];
  reference: Candidate | null;
  /** The design-space sweep's size (its designs: ``getSweep``); null or absent when none ran. */
  swept?: { designs: number; feasible: number } | null;
}

/** A spread over the drawn years: mean, P50, P90, P99, worst, and the share of years above 0. */
export interface YearSpread {
  mean: number;
  p50: number;
  p90: number;
  p99: number;
  max: number;
  share_above_zero: number;
}

/** One plan of the risk view priced a year (k€): the backup's capital annuity, O&M, grid charge. */
export interface BackupYear {
  mw: number;
  capital_keur: number;
  om_keur: number;
  grid_keur: number;
  backup_keur: number;
  /** The heat it would not deliver over the drawn years, at the lost sale, k€ a year. */
  lost_keur: number;
  /** The whole design's yearly cost, M€. */
  design_meur: number;
}

/** A design's backup sized by risk beside its own N-1 size (GET /api/risk). */
export interface RiskView {
  design: string;
  unit: string;
  unit_words: string;
  n1_mw: number;
  risk_mw: number;
  target_days: number;
  /** The years drawn with a spare ESP on the shelf (in both plans); false: as built, none. */
  spare_esp?: boolean;
  at_n1: { lole_days: number; eens_mwh: number; years_short: number; base_days: number };
  at_risk: { lole_days: number; eens_mwh: number; years_short: number; base_days: number };
  tried: [number, number][];
  capex_saved_meur: number;
  /** Both plans priced a year, and what N-1 costs a year more (older servers leave them out). */
  n1_plan?: BackupYear;
  risk_plan?: BackupYear;
  n1_extra_keur_per_year?: number;
  annuity?: { discount_rate: number; life_years: number; crf: number };
  spare_keur_per_year?: number;
  /** Units never drawn, in words (no published failure rate: a shared treatment train). */
  not_drawn?: string[];
  lost_keur_per_year: number;
  lost_eur_per_mwh: number;
  reliable: boolean;
  seconds: number;
  source: string;
}

/** Unplanned outages of a design over drawn years (GET /api/outages). */
export interface OutagesView {
  design: string;
  years: number;
  spare_esp: boolean;
  reliable: boolean;
  /** Heat and cold not delivered, MWh a year. */
  heat_mwh: YearSpread;
  cold_mwh: YearSpread;
  /** Extra running cost (with the grid charge), repairs, and all of it with the lost sale, k€ a year. */
  extra_keur: YearSpread;
  /** The electric boiler's grid charge alone (past the 600-hour contract), k€ a year. */
  grid_keur?: YearSpread;
  repair_keur: YearSpread;
  total_keur: YearSpread;
  lost_keur: number;
  histogram: { edges_mwh: number[]; years: number[] };
  /** Failures a year by unit ("doublet 1", "boiler unit" …). */
  failures: Record<string, number>;
  /** Units never drawn, in words (no published failure rate: a shared treatment train). */
  not_drawn?: string[];
  /** A doublet out 35 days in the coldest weeks. */
  worst: { unit: string; days: number; first_day: number; from: string; to: string; heat_mwh: number; cold_mwh: number; extra_keur: number; grid_keur?: number } | null;
  /** Each failure rate's and repair time's source, by key. */
  sources: Record<string, string>;
  seconds: number;
}

/** A search's design-space sweep (GET /api/sweep): every design drawn, as compact rows. */
export interface SweepView {
  /** Row fields: doublets, depth_m, flow_cap_m3h, heat_pump_mw, boiler_mw, electric_boiler_mw,
   * absorption_mw, chiller_mw, gas, lcoe, lcoh, co2_t, co2_saving_pct, capex_meur, broken. */
  columns: string[];
  rows: (number | string)[][];
  /** Rows no other feasible design beats on both cost and CO₂, cheapest first. */
  front: number[];
  ranges: Record<string, [number, number]>;
  feasible: number;
  /** How many designs break each cap first ("heat", "cold" …). */
  failures: Record<string, number>;
  broken_words: Record<string, string>;
  seconds: number;
  search: { id: string; name: string };
  /** The search's own designs, to place on the map. */
  marks: { id: string; uid: string; code: string; lcoe: number; co2_t: number; co2_saving_pct: number; role: string; picks: string[]; reliable: boolean; swept: boolean }[];
}

/** One candidate of the agent's design search (contract ``Candidate``). */
export interface Candidate {
  /** "2D-HP-EC@3000": doublets, top-up (HP heat pump, BO boiler, DH none), cooling (AB, EC), depth. */
  code: string;
  name: string;
  role: "chosen" | "candidate" | "failed" | "reference" | string;
  /** Why it lost to the chosen one, or the cap it broke. */
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
  heat_coverage_pct: number;
  cool_coverage_pct: number;
  /** Runs of the improvement loop (1: it met every cap at once). */
  rounds: number;
  /** "boiler 16.4 -> 16.5 MW" … */
  changes: string[];
  violations: string[];
  verified: boolean;
  /** The search it belongs to (S1, S2 …). */
  attempt?: string | null;
  /** Variant flags in its code: "2I", "2I1", "ST", "ST2", "BL", "PL", "PU", "IU", "IL" (see compare/flags.ts). */
  flags?: string[];
  /** 1: a layout of the search; 2: a variant of one of the best three layouts (its `parent`). */
  stage?: number;
  /** The layout a stage-2 variant was made from (its code); "" or null for a layout. */
  parent?: string | null;
  /** How the doublets share the brine: equal shares, or the hottest first ("base"). */
  dispatch?: Dispatch | string;
  /** Each doublet's set-up. */
  doublets?: DoubletSpec[];
  /** Wells and treatment trains it has. */
  wells?: number | null;
  trains?: number | null;
  /** How many sizings of this layout the search tried. */
  sizings?: number;
}

/** How the doublets share the brine each day: equal shares, or the hottest doublet first up to its cap. */
export type Dispatch = "equal" | "base";

/** Which part of the 100 m aquifer a well is open over. */
export type Opening = "full" | "upper" | "lower";

/** One doublet's set-up (Design.doublets, Candidate.doublets; what create_design takes). */
export interface DoubletSpec {
  /** The aquifer's middle, m TVD. */
  depth_m: number;
  producer_open: Opening | string;
  injector_open: Opening | string;
  /** 1 or 2. */
  injectors: number;
  /** Its own flow cap, m³/h (50-300); null: the challenge's 300. */
  max_flow_m3h?: number | null;
  /** The least it runs at, m³/h (50 to its cap; the cap too: one fixed rate); null: 50. */
  min_flow_m3h?: number | null;
  /** The treatment train it shares (doublets with the same number share one). */
  train: number;
}

/** One sizing the search tried for a layout (Design.sizings). */
export interface Sizing {
  heat_pump_share: number;
  absorption_share: number;
  heat_pump_mw?: number;
  boiler_mw?: number;
  absorption_mw?: number;
  chiller_mw?: number;
  lcoe: number;
  co2_t: number;
  valid: boolean;
  years: number;
  [key: string]: unknown;
}

export interface DesignCheck {
  name: string;
  passed: boolean;
  detail: string;
  /** Not in the contract: the verifier marks the brief's own targets (coverage) this way. */
  requirement?: boolean;
}

export interface Design {
  /** Stable within the conversation: "A1 · 1D-HP-EC-N1", "W1 · 1D-HP-EC-N1", "U1" … (older: the code). */
  id: string;
  /** What it is in words ("Best overall", "A1 + 50 °C heating return", "Rank 7 in run A"), or the user's name. */
  label?: string;
  /** The user's own name for it, when they gave one. */
  user_name?: string | null;
  /** On the user's shortlist. */
  starred?: boolean;
  /** The design's name in the chat: A1, A2 … (a search, ranked), W1 … (what-ifs), U1 … (yours). */
  uid?: string;
  /** The search's picks this design is: best, cost, co2, reliable. */
  picks?: string[];
  /** Sized so that any one unit can be out (a reliable plan). */
  reliable?: boolean;
  /** The design's code, or "U1", "U2" … for user designs. */
  code: string;
  name: string;
  origin: "agent" | "user" | "what_if";
  /** Where it stands: chosen, what_if, user … */
  role?: string;
  /** The improvement loop's runs: sizes, broken caps, what changed. */
  rounds?: { sizes_mw: Record<string, number>; violations: string[]; change: string }[];
  /** The id it was derived from (user edits, what-ifs). */
  parent: string | null;
  /** The search that produced it (S1, S2 …); a what-if or user design may have null: show its parent's. */
  attempt?: string | null;
  /** The chat's current recommendation or pick. */
  chosen: boolean;
  /** What-if shift, °C. */
  reservoir_delta_c: number;
  /** What a what-if changed ({heat_return_c: 50}, {reservoir_change_k: -5}); {} otherwise. */
  changes?: Record<string, unknown>;
  /** The what-if in words ("heating return temperature 50 °C"); its id is "<code> · <change_label>". */
  change_label?: string;
  /** Variant flags in its code (see Candidate.flags). */
  flags?: string[];
  /** 1: a layout; 2: a variant of one of the best three. */
  stage?: number;
  /** How the doublets share the brine. */
  dispatch?: Dispatch | string;
  /** Each doublet's set-up. */
  doublets?: DoubletSpec[];
  /** Every sizing tried for this layout. */
  sizings?: Sizing[];
  /** Things to know that are not broken caps. */
  warnings?: string[];
  /** Who computed it: the wells on GEMINI and the year on Dioscuri's plant model, or the plant
   * model alone (the gas reference). */
  source: "gemini+dioscuri_plant" | "dioscuri_plant" | string;
  /** When a cap is broken, as day ranges (0-based, 2027): heat or cold short, brine cooled too far. */
  broken_days?: { first: number; last: number; kind: string; text: string }[];
  /** What goes wrong in the year, part by part, the worst first (older servers leave it out). */
  issues?: DesignIssue[];
  verified: boolean;
  checks: DesignCheck[];
  plant: Plant;
  year: Year;
  economics: Economics;
  /** The plant as the Design tab draws it. */
  graph: Graph;
  /** Per field group (ProvenanceKey): plant (the operating point), year (the dispatch), economics, cooling. */
  provenance: Record<string, Provenance>;
}

/** How bad an issue is: demand not met (red on the canvas), or worth a look (amber). */
export type IssueSeverity = "critical" | "warning";

/**
 * One thing that goes wrong in a design's year (gemini_agent.issues): demand not met on some
 * days, a failure asked about in the chat (a what-if on this design), or a broken cap.
 */
export interface DesignIssue {
  /** Unique in the design: "heat_short-1". */
  id: string;
  kind: "heat_short" | "cool_short" | "failure" | "cap" | string;
  severity: IssueSeverity;
  /** The parts it concerns, as Graph node ids: the main one first. */
  units: string[];
  /** Parts that ran flat out on its days (at their limit): amber. */
  limit: string[];
  /** The main part in words ("Gas boiler", "Producer 1"). */
  unit: string;
  /** What happens: "Heat short on 6 days in January, up to 1.2 MW". */
  what: string;
  /** Why, when known: "Not enough capacity: …", "Doublet 1 is in its planned stop". */
  why: string;
  /** When, in words: "26–29 Jan", "over the year". */
  when: string;
  /** 0-based days of 2027; null for the whole year. `day` is the worst one. */
  first: number | null;
  last: number | null;
  day: number | null;
  /** How many days. */
  days: number;
  /** A failure asked about in the chat: the drawing shows the design without it. */
  what_if: boolean;
  worst_mw?: number;
  /** The chat message that asked (a what-if). */
  asked?: string;
}

export interface Plant {
  /** 0 = no well (the gas reference). */
  depth_m: number;
  /** 1 to 3 (0: the reference). */
  n_doublets?: number;
  /** "heat_pump" or "boiler" (what the candidate tops up with); null for the reference. */
  topup?: string | null;
  cooling?: string | null;
  max_brine_cooling_k?: number;
  flow_mean_m3h?: number | null;
  esp_head_bar?: number | null;
  injection_wellhead_bar?: number | null;
  /** Each doublet's stop, [first, last] day (0-based); the first of its stops when it has several. */
  stop_days?: number[][];
  /** Every stop of each doublet, [first, last] ranges (several when the user gave the dates). */
  stop_ranges?: number[][][];
  /** The challenge's reservoir at the design's depth. */
  reservoir?: {
    depth_m: number;
    temperature_c: number;
    pressure_bar: number;
    permeability_md: number;
    thickness_m: number;
    brine_density_kg_m3: number;
    brine_viscosity_mpa_s: number;
    gas_liquid_ratio: number;
  };
  heat_pump: boolean;
  boiler: boolean;
  absorption: boolean;
  chillers: boolean;
  reservoir_c: number;
  wellhead_c: number;
  hex_outlet_c: number;
  reinjection_c: number;
  flow_m3h: number | null;
  esp_mw: number | null;
  injector_pump_mw: number | null;
  hex_ua_kw_per_k: number | null;
  cop: number;
  carnot_cop: number;
  transmissivity_dm: number | null;
  productivity_index_m3h_per_bar: number | null;
  /** Network temperatures, °C (older servers leave them out). */
  heating_supply_c?: number;
  heating_return_c?: number;
  cooling_supply_c?: number;
  cooling_return_c?: number;
  sizes_mw: { heat_exchanger: number; heat_pump: number; boiler: number; absorption: number; chillers: number; electric_boiler?: number };
  /** One row per doublet: its wells, flow and pumping (older servers leave it out). */
  doublets?: PlantDoublet[];
  /** Wells and treatment trains built. */
  wells?: number | null;
  trains?: number | null;
  dispatch?: Dispatch | string;
}

/** One doublet of a design as it ran (Plant.doublets). Depths are m TVD; the open parts are of the 100 m aquifer. */
export interface PlantDoublet {
  doublet: number;
  /** The aquifer's middle. */
  depth_m: number;
  producer_open: Opening | string;
  injector_open: Opening | string;
  /** The middle and the length of the producer's open part. */
  producer_mid_m: number;
  producer_open_m: number;
  injector_mid_m: number;
  injector_open_m: number;
  injectors: number;
  train: number;
  /** Its flow cap, m³/h. */
  cap_m3h: number;
  /** The rock at the producer's open part, °C. */
  rock_c: number;
  /** At the wellhead at full flow, and at its lowest flow of the year, °C. */
  wellhead_full_c: number;
  wellhead_min_c: number;
  well_loss_full_k: number;
  days_on: number;
  /** Mean flow over the days it runs, and over the whole year, m³/h. */
  flow_mean_m3h: number;
  flow_year_mean_m3h: number;
  brine_m3: number;
  max_cooling_k: number;
  esp_gwh: number;
  injection_gwh: number;
  esp_head_full_bar: number;
  injection_full_bar: number;
  pi_m3h_per_bar: number;
  injectivity_m3h_per_bar: number;
  [key: string]: unknown;
}

export type HeatSource = "geo" | "hp" | "boiler";
/** A heat source only some designs have (the gas-free ones): sent only when it gives heat. */
export type ExtraHeatSource = "electric_boiler";
/** The heat sources of a year: the three every design has, and the electric boiler when it runs. */
export type HeatSplit<T> = Record<HeatSource, T> & Partial<Record<ExtraHeatSource, T>>;
export type ColdSource = "abs" | "chill";
/** What draws electricity: the heat pump, the chillers, the cooling towers, the wells' pumps, the electric boiler. */
export type PowerUser = "hp" | "chillers" | "towers" | "pumps" | "electric_boiler";
/** What sends heat to the cooling towers: the absorption chiller, the electric chillers. */
export type RejectSource = "abs" | "chillers";

export interface Year {
  heat_demand_gwh: number;
  cool_demand_gwh: number;
  heat_delivered_gwh: number;
  cool_delivered_gwh: number;
  /** 0..1 */
  heat_coverage: number;
  /** 0..1 */
  cool_coverage: number;
  heat_split_gwh: HeatSplit<number>;
  cool_split_gwh: Record<ColdSource, number>;
  peak_heat_mw: number;
  peak_cool_mw: number;
  full_load_hours: number;
  /** Jan..Dec. */
  monthly_gwh: { heat: HeatSplit<number[]> & { demand: number[] }; cool: Record<"demand" | ColdSource, number[]> };
  /** 365 values, day 1..365 (daily mean MW); "short" is what was not met. `power` is the electricity
   * each unit draws (hp: heat pump, pumps: the wells' pumps) and `reject` the heat the towers take
   * from each chiller (older servers leave them out). */
  daily_mw: {
    heat: HeatSplit<number[]> & { demand: number[] };
    cool: Record<"demand" | ColdSource, number[]>;
    power?: Partial<Record<PowerUser, number[]>>;
    reject?: Partial<Record<RejectSource, number[]>>;
  };
  /** One sentence per broken cap (empty when every cap holds). */
  violations?: string[];
  electricity_gwh?: Record<string, number>;
  purchased_gas_gwh?: number;
  produced_gas_burned_gwh?: number;
  produced_gas_flared_gwh?: number;
  /** The brine's gas cleaned and sold to the gas grid, its methane (a design that sells it). */
  produced_gas_sold_gwh?: number;
  /** By origin; `total` is the plant's. `sold_gas_elsewhere` is the buyer's, burning the gas sold: not in the total. */
  co2_t?: Record<string, number>;
  /** The same total by the unit that lets it out, t a year (boiler, electric_boiler, hp, pumps, flare, brine_co2, chillers, towers,
   * network); the parts add up to `co2_t.total`. Older servers and designs leave it out. */
  co2_by_unit_t?: Record<string, number>;
  stop_days?: number[][];
  /** Every stop of each doublet, [first, last] ranges; older designs have only stop_days. */
  stop_ranges?: number[][][];
  /** Per doublet: flow_m3h, on, reinjection_c and wellhead_c (365 each; the temperatures null when off). */
  doublets?: YearDoublet[];
}

/** One doublet over the year, day by day (365 values each). */
export interface YearDoublet {
  flow_m3h: number[];
  on: boolean[];
  reinjection_c: (number | null)[];
  /** The producer's wellhead temperature (older servers leave it out). */
  wellhead_c?: (number | null)[];
}

export interface Economics {
  /** €/MWh */
  lcoh: number;
  /** €/MWh */
  lcoc: number | null;
  /** Heat and cold together, €/MWh. */
  lcoe?: number;
  capex_meur: number;
  co2_t_per_year: number;
  reference_co2_t_per_year: number;
  co2_saving_pct: number;
  /** They add up to lcoh and lcoc. */
  lines: { heat: CostLine[]; cold: CostLine[] };
  capex_items: CapexItem[];
  /** Against the gas reference (A4), same assumptions; null for the reference itself. */
  versus_reference: VersusReference | null;
  /** Costs against the gas reference of the same conditions, signed fractions (−0.17: 17 % cheaper). */
  vs_gas_pct?: { heat: number | null; cold: number | null; total: number | null };
  /** Each kind's share of the year's cost of heat and cold (capital, fixed, variable, electricity, gas, carbon). */
  breakdown_pct?: Record<string, number>;
  /** A revenue (the brine's gas sold) as a share of the costs above; null when there is none. */
  credit_pct?: number | null;
  /** The investor's view (sales, SDE++, corporate tax; dioscuri_plant.investor); null for the gas plant, absent from older servers. */
  investor?: Investor | null;
}

export interface CapexItem {
  item: string;
  size: number;
  unit: string;
  meur_per_unit: number;
  meur: number;
  life_years?: number;
  /** What the row is when an item has several ("1 producer(s), 2 injector(s), priced at 2,500 m TVD"). */
  note?: string;
}

export interface VersusReference {
  extra_capex_meur: number;
  savings_meur_per_year: number;
  payback_years: number | null;
  npv_meur: number;
  /** Cumulative, year 0 .. lifetime. */
  cash_flow_meur: number[];
}

export type CostKind = "capital" | "fixed" | "variable" | "electricity" | "gas" | "network" | "carbon" | "calibration";

export interface CostLine {
  /** "Wells", "Heat exchanger", "Gas", "Electricity: heat pump" … */
  item: string;
  kind: CostKind;
  meur_per_year: number;
  eur_per_mwh: number;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** The GEMINI project JSON that GEMINI's solver ran. */
  gemini_project: GeminiProject | null;
}

export interface GraphNode {
  id: string;
  /** A catalogue type, or "demand_heat", "demand_cold", "absorption", "chillers", "grid", "gas", "tower", "reservoir". */
  type: string;
  label: string;
  /** GEMINI's solver, or Dioscuri's plant model. */
  solver: "gemini" | "dioscuri";
  /** e.g. { power_mw: 9.25, temperature_out_c: 45.4 } */
  values: Record<string, number>;
  units: Record<string, string>;
  /** The gas node: what the plant does with gas (GasMode). */
  gas?: GasMode | string;
}

/** Gas: bought for the boiler (after the brine's own), only the brine's own burnt (none bought), or the brine's sold to the gas grid. */
export type GasMode = "buy" | "produced" | "sell";

/** What a pipe carries: brine, network heat, network cold, gas, electricity, or the heat the towers reject. */
export type EdgeKind = "brine" | "network" | "cold" | "gas" | "electricity" | "reject";

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
  mw: number | null;
  temperature_c: number | null;
  label: string;
}

// ------------------------------------------------------------------ assumptions and edits

/** One price, cost or convention (dioscuri_plant ``Prices``), with its source. */
export interface AssumptionItem {
  key: string;
  label: string;
  unit: string;
  group: "prices" | "capital" | "o&m" | "lifetimes" | string;
  value: number;
  default: number;
  source: string;
}

export interface Assumptions {
  /** Every value, in the order the backend lists them. */
  items: AssumptionItem[];
  defaults: Record<string, number>;
  /** Where each default comes from. */
  sources: Record<string, string>;
  notes: string[];
  /** The current values by key, too. */
  [key: string]: unknown;
}

/** PUT /api/assumptions: a value, or null to go back to the default (the investor's SDE++ category is a string, its switch a boolean). */
export type AssumptionsPatch = Record<string, number | string | boolean | null>;

export interface DesignChanges {
  n_doublets?: number;
  depth_m?: number;
  heat_pump_mw?: number;
  boiler_mw?: number;
  absorption_mw?: number;
  chiller_mw?: number;
  reservoir_delta_c?: number;
  /** Heating network return, °C (the supply is fixed at 100 °C). */
  return_c?: number;
  /** Cooling network return, °C. */
  cool_return_c?: number;
  /** Each doublet set one by one (1 to 3); replaces n_doublets and depth_m. */
  doublets?: DoubletChange[];
  /** How the doublets share the brine (2 or more doublets). */
  dispatch?: Dispatch;
}

/** One doublet as create_design takes it. */
export interface DoubletChange {
  depth_m: number;
  producer_open: Opening;
  injector_open: Opening;
  injectors: 1 | 2;
  /** null: the challenge's 300 m³/h. */
  max_flow_m3h: number | null;
  /** null or absent: the challenge's 50 m³/h. */
  min_flow_m3h?: number | null;
  train: number;
}

// ------------------------------------------------------------------ GEMINI projects

/** GEMINI's own project JSON (the format of simulator_examples/projects/*.json). */
export interface GeminiProject {
  /** What the project is, in words (the backend's; GEMINI ignores keys starting with _). */
  _description?: string;
  /** Components in the order the brine flows (the backend lists them so). */
  components: Record<string, { type: string; parameters?: Record<string, unknown>; _description?: string; [key: string]: unknown }>;
  boundary_inputs: { component: string; key: string; value: number; [key: string]: unknown }[];
  connections: {
    predecessor: string;
    successor: string;
    ports?: [string, string][];
    predecessor_output?: string;
    successor_input?: string;
    [key: string]: unknown;
  }[];
  [key: string]: unknown;
}

export interface CatalogueType {
  /** GEMINI registry type: producer_well, separator, filter, heat_exchanger, heatpump, boiler, chp, splitter, mixer, adder, injector_well … */
  type: string;
  label: string;
  group: "wells" | "surface" | "heat" | "flow";
  description: string;
  inputs: { key: string; unit: string; description: string }[];
  outputs: { key: string; unit: string; description: string }[];
  parameters: { key: string; unit: string; default: number | string | object | null; description: string }[];
}

export interface Catalogue {
  types: CatalogueType[];
}

/** Component -> output key -> value. */
export type GeminiOutputs = Record<string, Record<string, number>>;

export interface GeminiRun {
  ok: boolean;
  error: string | null;
  seconds: number;
  outputs: GeminiOutputs;
  released: { ok: boolean; error: string | null; outputs: GeminiOutputs } | null;
  /** The fixes the "fixed" run used. */
  patches: string[];
}

// ------------------------------------------------------------------ sensitivity

export interface SensParam {
  key: string;
  label: string;
  unit: string;
  group: "subsurface" | "demand" | "prices" | "costs" | "equipment" | string;
  /** Default range, as a value or a change (see kind). */
  low: number;
  high: number;
  /** "absolute": a value; "delta": added (°C); "scale": multiplied (1 = as is). */
  kind: "absolute" | "delta" | "scale";
  description: string;
}

export type SensOutputKey = "lcoh" | "lcoc" | "lcoe" | "co2_saving_pct" | "heat_coverage" | "capex_meur" | "npv_meur" | "violations";

export interface SensOutput {
  key: SensOutputKey;
  label: string;
  unit: string;
}

export interface SensitivityParameters {
  parameters: SensParam[];
  outputs: SensOutput[];
}

export interface SensitivityRequest {
  threadId: string;
  /** A design id. */
  design: string;
  parameters: { key: string; low: number; high: number }[];
  outputs: string[];
  /** 0 or absent: no Monte Carlo; otherwise at most 500. */
  samples?: number;
}

export interface MonteCarloOutput {
  p10: number;
  p50: number;
  p90: number;
  mean: number;
  histogram: { edges: number[]; counts: number[] };
}

export interface Sensitivity {
  design: string;
  seconds: number;
  runs: number;
  /** Output -> value at the base case. */
  base: Record<string, number>;
  /** Sorted by the swing of the first output. */
  tornado: { key: string; label: string; low: Record<string, number>; high: Record<string, number> }[];
  /** 5 points, low..high. */
  spider: { key: string; points: { x: number; values: Record<string, number> }[] }[];
  monte_carlo: { samples: number; outputs: Record<string, MonteCarloOutput> } | null;
}

// ------------------------------------------------------------------ trace and evidence

export interface TraceStep {
  name: string;
  label: string;
  kind: string;
  code: string | null;
  seconds: number;
  meta: Record<string, unknown>;
}

export interface TraceRun {
  runId: string;
  /** Unix milliseconds (the server's event timestamp). */
  started: number;
  message: string;
  /** The reply the user saw, and the model that wrote it (empty when a template answered). */
  answer?: string;
  answer_model?: string;
  mode: "fast" | "reasoning";
  device: string;
  seconds: number;
  tokens: { prompt: number; output: number };
  steps: TraceStep[];
  calls: { purpose: string; model: string; prompt_tokens: number; output_tokens: number; seconds: number; ok: boolean }[];
  tools: { name: string; args: unknown; result: unknown }[];
  /** The behaviour: design, answer, clarify … */
  outcome: string;
}

export interface Trace {
  runs: TraceRun[];
}

export interface EvalScenario {
  id: string;
  expected: string;
  got: string;
  ok: boolean;
  calls: number;
  tokens: number;
  seconds: number;
  /** The checks that failed, by name ("cap: 50 to 300 m³/h a doublet"). */
  failed?: string[];
  /** The case's full transcript was kept (GET /api/transcript). */
  transcript?: boolean;
  /** The chat suite's group ("provenance", "out_of_scope" …). */
  group?: string | null;
}

/** One finding of the eval's own check of a design (hackathon/evals/truth.py). */
export interface TruthRow {
  key: string;
  name: string;
  ok: boolean | null;
  found: string;
}

/** One exchange of an eval case: what the user sent, and every event that came back. */
export interface TranscriptExchange {
  user: { message?: string | null; answers?: Record<string, string>; designs?: string[]; upload?: { files: string[] } };
  events: import("../agent/types").AgEvent[];
}

/** GET /api/transcript?run=&case=: one eval case, whole (hackathon/evals/transcripts.py). */
export interface Transcript {
  version: number;
  run: string;
  case: string;
  /** The conversation this case continues (another case's snapshot). */
  after?: string | null;
  group?: string | null;
  prompt: string;
  attachment?: string | null;
  model: string;
  device: string;
  reasoning: string;
  expected: string;
  got: string | null;
  pass: boolean;
  behaviour_ok: boolean;
  checks: Record<string, boolean | null>;
  truth?: { design: string | null; caps: TruthRow[]; known: TruthRow[]; quotes: { text: string; known: number; ok: boolean }[] } | null;
  verified?: boolean | null;
  wall_seconds: number;
  project?: { id: string; name: string } | null;
  exchanges: TranscriptExchange[];
  /** Each run's steps, tool calls and model calls, as the Trace tab reads them. */
  runs: TraceRun[];
}

export interface EvalRun {
  /** "main": scenarios.yaml; "chat": the chat suite (each case in a group, three wordings). */
  suite?: "main" | "chat" | string;
  /** The chat suite's pass count per group. */
  groups?: Record<string, { passed: number; total: number }>;
  file: string;
  device: string;
  /** "GPU" or "CPU": where the answerer ran (an "auto" run on a GPU machine says GPU). */
  label?: string;
  answerer: string;
  when: string;
  passed: number;
  total: number;
  tokens: number;
  seconds: number;
  scenarios: EvalScenario[];
}

export interface Benchmark {
  title: string;
  columns: string[];
  rows: (string | number)[][];
  note: string;
  /** Rows set in bold in BENCHMARKS.md: the model each role uses. */
  emphasis?: number[];
}

export interface BugImpact {
  design: string;
  rows: { quantity: string; unit: string; released: number | null; fixed: number | null; bugs: string }[];
}

export interface Evidence {
  evals: EvalRun[];
  benchmarks: Benchmark[];
  gemini: { version: string; patches: { file: string; title: string }[]; bug_impact: BugImpact[] };
  /** Real doublets run through our doublet model against their published figures. */
  validation?: RealCheck[];
  /** Failures found and fixed, each with its guard (src/gemini_agent/caught.py). */
  caught?: import("./basis").Caught;
}

export interface RealCheck {
  key: string;
  name: string;
  source: string;
  case: string;
  assumed: string;
  note: string;
  inputs: Record<string, number>;
  rows: { quantity: string; unit: string; ours: number; theirs: number | null; diff_pct: number | null; agree: boolean | null; note: string }[];
}

// ------------------------------------------------------------------ the investor's view

/** One SDE++ 2026 geothermal category (PBL's advice). */
export interface SdeCategory {
  key: string;
  /** The official (Dutch) name: "Diepe geothermie <12 MWth (basislast)". */
  name: string;
  /** In plain English. */
  label: string;
  /** The basisbedrag, €/kWh. */
  basis_eur_per_kwh: number;
  /** The most hours a year that earn subsidy, at the plant's capacity. */
  full_load_hours: number;
  min_mw: number;
  max_mw: number | null;
  /** The CO₂-price part of the correction, €/kWh, from the calendar year `ets_from`. */
  ets_eur_per_kwh: number;
  ets_from: number;
  by_size: boolean;
  source: string;
}

/** The SDE++ a design gets: its category, the heat it pays on and the money a year. */
export interface InvestorSde {
  on: boolean;
  category: SdeCategory;
  /** "size": by the plant's geothermal capacity; "you": picked in this chat. */
  chosen_by: "size" | "you";
  /** The capacity is inside the category's size range. */
  fits: boolean;
  capacity_mw: number;
  flow_m3h: number;
  brine_cooling_k: number;
  /** Geothermal heat a year (exchanger + heat pump), GWh. */
  eligible_gwh: number;
  /** Capacity × full-load hours, GWh. */
  cap_gwh: number;
  subsidised_gwh: number;
  capped: boolean;
  /** The basisbedrag used, €/kWh. */
  basis_eur_per_kwh: number;
  /** The gas-price part of the correction, €/kWh. */
  correction_eur_per_kwh: number;
  floor_eur_per_kwh: number;
  ets_eur_per_kwh: number;
  /** The plant's first year with the CO₂ part (1 = 2027). */
  ets_from_year: number;
  /** Paid per kWh in year 1 and in the last subsidy year, €/kWh (euros of the day). */
  per_kwh_first: number;
  per_kwh_later: number;
  first_year: number;
  last_year: number;
  calendar_years: [number, number];
  /** M€ in 2025 euros (the cost basis's price year). */
  meur_first_year: number;
  meur_average: number;
  total_meur: number;
}

/** One year of the investor's cash flow, M€ of today; outflows negative. */
export interface InvestorFlow {
  year: number;
  revenue_heat: number;
  revenue_cold: number;
  sde: number;
  opex: number;
  capital: number;
  value_left: number;
  tax: number;
  net: number;
  /** Discounted, years 0 to this one. */
  cumulative: number;
}

/** What the user can change in the investor's view (PUT /api/assumptions keys). */
export interface InvestorInput {
  key: "heat_sale_eur_per_mwh" | "cold_sale_eur_per_mwh" | "sde_category" | "sde_on" | string;
  label: string;
  unit: string;
  value: number | string | boolean;
  default: number | string | boolean;
  changed: boolean;
  kind: "number" | "choice" | "switch";
  source: string;
  /** For the category: "auto" and every category. */
  options?: { key: string; label: string; name?: string; basis_eur_per_kwh?: number; full_load_hours?: number }[];
}

/** A design as an investment: sales, SDE++, corporate tax, the cash flow after tax and its return. */
export interface Investor {
  years: number;
  /** Real, after tax (fraction). */
  discount_rate: number;
  inflation: number;
  heat_sale_eur_per_mwh: number;
  cold_sale_eur_per_mwh: number;
  sale_basis: { heat: string; cold: string };
  heat_sold_gwh: number;
  cold_sold_gwh: number;
  /** A year, M€ of today. */
  revenue_heat_meur: number;
  revenue_cold_meur: number;
  opex_meur: number;
  capex_meur: number;
  reinvest_meur: number;
  value_left_meur: number;
  sde: InvestorSde;
  tax: { rate: number; rate_low: number; band_meur: number; depreciation_years: number; total_meur: number; first_tax_year: number | null };
  flows: InvestorFlow[];
  npv_meur: number;
  /** Real, fraction; null when no rate makes the NPV zero. */
  irr: number | null;
  /** Discounted, years; null when it never pays back. */
  payback_years: number | null;
  without_sde: { npv_meur: number; irr: number | null; payback_years: number | null };
  /** The basisbedrag (€/kWh) at which the NPV is zero; null when it needs none (or no SDE++ can help). */
  break_even_basis_eur_per_kwh: number | null;
  needs_subsidy: boolean;
  notes: string[];
  sources: Record<string, string>;
  inputs: InvestorInput[];
}
