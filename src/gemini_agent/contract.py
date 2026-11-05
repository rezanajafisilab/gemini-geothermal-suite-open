"""Typed contract between the agent and its tools (v0 proposal, to agree with Ali on D1).

Every number carries its unit in its field name (``_c``, ``_m``, ``_mw``, ``_gwh``,
``_eur_per_mwh``), so neither side has to guess what a value means. The tool side owns the
physics; the agent only fills the inputs and reads the outputs.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Intent = Literal["design", "compare", "what_if", "explain", "other"]
Behaviour = Literal["design", "clarify", "refuse", "reject", "report_infeasible"]
# "boiler": the gas boiler; "electric_boiler": the electric one (gas-free designs).
Equipment = Literal["heat_pump", "boiler", "chiller", "electric_boiler"]


class NetworkTemps(BaseModel):
    """Supply and return temperature of a district network."""

    supply_c: float
    return_c: float

    def label(self) -> str:
        """Return the pair the way engineers write it, for example ``70/40 °C``."""
        return f"{self.supply_c:g}/{self.return_c:g} °C"


class ProjectData(BaseModel):
    """What the project already holds, so the agent does not ask for it again."""

    id: str = "challenge"  # the organisers' district; user projects: ``gemini_agent.projects``
    name: str = "Example district"
    files: List[str] = Field(default_factory=list)
    has_heat_profile: bool = False
    has_cool_profile: bool = False
    has_reservoir: bool = False
    annual_heat_gwh: Optional[float] = None
    annual_cool_gwh: Optional[float] = None
    reservoir_depth_m: Optional[float] = None
    reservoir_temp_c: Optional[float] = None
    # The networks' supply and return; None: the challenge's (100/60 °C and 20/25 °C).
    heating: Optional[NetworkTemps] = None
    cooling: Optional[NetworkTemps] = None


Opening = Literal["full", "upper", "lower"]


class DoubletSpec(BaseModel):
    """One doublet as the user describes it; unset fields are the usual ones."""

    depth_m: Optional[float] = None  # the aquifer's midpoint; None: the known reservoir
    producer_open: Opening = "full"
    injector_open: Opening = "full"
    injectors: int = 1  # 2: a triplet (one producer, two injectors)
    max_flow_m3h: Optional[float] = None
    # The least it runs at (the cap too: one fixed rate); None: the challenge's 50 m3/h.
    min_flow_m3h: Optional[float] = None
    train: Optional[int] = None  # equal numbers share a treatment train; None: shared


class AquiferSpec(BaseModel):
    """One aquifer the wells can be drilled into, as the user (or the inputs card) gives it.

    The midpoint (TVD), thickness, permeability, pressure at the midpoint (bar(g)) and the gas
    its brine brings up. A value left out is the known aquifer's (the pressure: the brine
    column's at its depth). The temperature follows the gradient at its depth.
    """

    depth_m: float
    thickness_m: Optional[float] = None
    permeability_md: Optional[float] = None
    pressure_bar: Optional[float] = None
    gas_liquid_ratio: Optional[float] = None


class DesignBrief(BaseModel):
    """Everything the agent knows about the requested design, merged across turns."""

    site: Optional[str] = None
    heating: Optional[NetworkTemps] = None
    cooling: Optional[NetworkTemps] = None
    annual_heat_gwh: Optional[float] = None
    annual_cool_gwh: Optional[float] = None
    reservoir_depth_m: Optional[float] = None
    reservoir_temp_c: Optional[float] = None
    transmissivity_dm: Optional[float] = None
    min_heat_coverage: float = 0.95
    min_cool_coverage: float = 0.95
    excluded: List[Equipment] = Field(default_factory=list)
    doublet_depths_m: List[float] = Field(default_factory=list)
    # The aquifers the doublets may be drilled into, one to three, each with its own rock and
    # gas (``gemini_agent.aquifers``); the known one first when kept. Empty: the project's (its
    # aquifer, and for the challenge the same rock assumed deeper).
    aquifers: List[AquiferSpec] = Field(default_factory=list)
    reservoir_delta_c: float = 0.0
    wants_cooling: bool = True
    # The challenge: how many doublets the user asked for (None: the search picks 1-3), and
    # what "best" means among the designs that meet every cap.
    n_doublets: Optional[int] = None
    # best: reliable (any one unit out) and cheapest with CO2 at the long-term price; cost: the
    # lowest cost of heat and cold; co2: the least CO2 (cheapest within 2 %); reliable: the
    # cheapest of the reliable plans.
    objective: Literal["best", "cost", "co2", "reliable", "green_reliable", "gas_free"] = "best"
    # At least this CO2 cut against gas (0.5: half), for every pick; None: no floor.
    min_co2_saving: Optional[float] = None
    # How the doublets are built, when the user says so (None: the search tries the options).
    injectors: Optional[int] = None  # per doublet: 1, or 2 (one producer, two injectors)
    trains: Optional[Literal["shared", "separate"]] = None  # treatment (separator, filters)
    dispatch: Optional[Literal["equal", "base"]] = None  # equal shares, or hottest first
    producer_open: Optional[Opening] = None
    injector_open: Optional[Opening] = None
    doublets: List[DoubletSpec] = Field(default_factory=list)  # each doublet, when described
    # Changes to the project's rules (``dioscuri_plant.Rules`` fields), prices (``Prices``
    # fields, or ``capex_scale``) and demand (heat, cold multipliers): a what-if, or the user's.
    rules: Dict[str, float] = Field(default_factory=dict)
    prices: Dict[str, float] = Field(default_factory=dict)
    demand_scale: List[float] = Field(default_factory=lambda: [1.0, 1.0])
    # The project whose demand and reservoir the engine runs on (``gemini_agent.projects``).
    project_id: str = "challenge"
    # Homes the district serves, for costs per home (None: home-equivalents of 12 MWh a year).
    homes: Optional[int] = None
    # When each doublet stops, on the user's dates (the inputs card): per doublet, [first, last]
    # days of 2027 (0-based, inclusive), one block or several. Empty (or a doublet without
    # ranges): Dioscuri places its stop in the quietest weeks.
    doublet_stops: List[List[List[int]]] = Field(default_factory=list)


class Alternative(BaseModel):
    """One plant configuration the engineer simulates."""

    code: str
    name: str
    # The design search this came from (``S1``, ``S2`` ...): a chat may run several.
    attempt: Optional[str] = None
    # A design drawn in a search's design-space sweep and opened in the tabs (``S1·sweep·12``).
    sweep_id: Optional[str] = None
    depth_m: float
    heat_pump: bool = True
    boiler: bool = True
    absorption: bool = True
    chillers: bool = True
    # The challenge's designs (``engine``): doublets, the top-up and cooling choices, each
    # unit's size (MW), where the design stands in the search and why, and its rounds.
    n_doublets: int = 1
    topup: Optional[str] = None
    cooling: Optional[str] = None
    sizes_mw: Dict[str, float] = Field(default_factory=dict)
    role: str = "design"  # chosen, candidate, failed, same, reference, user, what_if
    reason: str = ""
    rounds: List[Dict[str, object]] = Field(default_factory=list)
    # Each doublet's set-up (aquifer depth, open parts, injectors, flow cap, treatment train),
    # how they share the brine, the variant flags in the code, the search stage it came from
    # (2: a variant of ``parent``) and every sizing the search tried for this layout.
    doublets: List[Dict[str, object]] = Field(default_factory=list)
    dispatch: str = "equal"
    flags: List[str] = Field(default_factory=list)
    stage: int = 1
    parent: str = ""
    sizings: List[Dict[str, object]] = Field(default_factory=list)
    # The name the chat and the tabs use, unique in a conversation: A1, A2 ... (the first
    # search, ranked), B1 ... (the next), W1 ... (what-ifs), F1 ... (failures), U1 ... (yours).
    uid: str = ""
    # The picks this design is (``engine.PICKS``): best, cost, co2, reliable.
    picks: List[str] = Field(default_factory=list)
    # The reliable plan: the boiler and chillers as equal units (1: one machine each).
    boiler_units: int = 1
    chiller_units: int = 1
    electric_boiler_units: int = 1
    # What the plant does with gas (``dioscuri_plant.types.GAS_MODES``): buy, produced, sell.
    gas: str = "buy"
    reliable: bool = False
    effect: str = ""  # a variant: what it changed against its parent


class YearResult(BaseModel):
    """Output of ``simulate_year``: one quasi-steady year, daily resolution."""

    alternative: str
    source: str = "mock"
    reservoir_c: float
    wellhead_c: float
    hex_outlet_c: float
    reinjection_c: float
    heat_demand_gwh: float
    cool_demand_gwh: float
    heat_delivered_gwh: float
    cool_delivered_gwh: float
    heat_coverage: float
    cool_coverage: float
    heat_split_gwh: Dict[str, float]
    cool_split_gwh: Dict[str, float]
    peak_heat_mw: float
    peak_cool_mw: float
    hex_mw: float
    heat_pump_mw: float
    boiler_mw: float
    absorption_mw: float
    chiller_mw: float
    heat_pump_cop: float
    heat_pump_carnot_cop: float
    # The chillers' and the absorption chiller's COP over the year (0 when not installed).
    chiller_cop: float = 0.0
    absorption_cop: float = 0.0
    full_load_hours: float
    cooling_gain: float
    # Optional: when a tool reports them, the verifier also checks each component's balance.
    heat_pump_electricity_gwh: Optional[float] = None
    brine_heat_gwh: Optional[float] = None  # heat taken from the brine: HEX, evaporator, drive
    brine_capacity_mw: Optional[float] = None  # brine flow x (wellhead - reinjection limit)
    # Optional: energy per month (GWh), ``{"heat": {"demand", "geo", "hp", "boiler"},
    # "cool": {"demand", "abs", "chill"}}``, twelve values each; the chat draws it.
    monthly_gwh: Optional[Dict[str, Dict[str, List[float]]]] = None
    # Optional: the plant's operating point when a simulator computed it (brine flow m3/h,
    # ESP and injector pump MW, and for GEMINI its version, variant and patches).
    plant: Optional[Dict[str, object]] = None
    # Optional: each day's mean power by source (MW, 365 values), only when asked for.
    daily_mw: Optional[Dict[str, Dict[str, List[float]]]] = None
    # Optional, from the challenge's plant model: each doublet's days, the broken caps, the
    # energy bought and burnt, CO2 by origin, and the stops.
    n_doublets: Optional[int] = None
    doublets: Optional[List[Dict[str, list]]] = None
    violations: List[str] = Field(default_factory=list)
    electricity_gwh: Optional[Dict[str, float]] = None
    purchased_gas_gwh: Optional[float] = None
    produced_gas_burned_gwh: Optional[float] = None
    produced_gas_flared_gwh: Optional[float] = None
    produced_gas_sold_gwh: Optional[float] = None
    co2_t: Optional[Dict[str, float]] = None
    # The same CO2 by the unit that lets it out (``dioscuri_plant.YearResult.co2_by_unit_t``):
    # boiler, electric_boiler, hp, pumps, flare, brine_co2, chillers, towers, network; the parts
    # add up to ``co2_t["total"]``. None for designs saved before it existed.
    co2_by_unit_t: Optional[Dict[str, float]] = None
    stop_days: Optional[List[List[int]]] = None
    # Every stop of each doublet, [first, last] ranges (several when the user gave the dates).
    stop_ranges: Optional[List[List[List[int]]]] = None
    max_brine_cooling_k: Optional[float] = None
    balance_error: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)  # worth saying, not broken caps
    # The district network's losses and pumping (``dioscuri_plant.network``), when modelled.
    network: Optional[Dict[str, object]] = None
    # Planned service windows of the surface units: [unit, first day, last day] (0-based).
    service: List[List[object]] = Field(default_factory=list)
    # Free cooling's largest day (MW of cold); own solar (GWh: generated, used, sold, bought);
    # the hot-water store (capacity, charged, given back, lost, the boiler's heat it saved).
    free_cooling_mw: float = 0.0
    solar: Optional[Dict[str, float]] = None
    storage: Optional[Dict[str, object]] = None
    # The cooling towers' water a year, m3: evaporation, blow-down and make-up (all they reject).
    tower_water_m3: Optional[Dict[str, float]] = None
    # Minimum loads and trips: each unit's days below its minimum load, its starts, the trips.
    operability: Optional[Dict[str, object]] = None


class Economics(BaseModel):
    """Output of ``economics``: levelised costs and CO2 against the gas reference."""

    alternative: str
    source: str = "mock"
    lcoh_eur_per_mwh: float
    lcoc_eur_per_mwh: Optional[float]
    capex_meur: float
    co2_saving_vs_gas: float
    # Optional, from the challenge's cost model: heat and cold together, the lines each side
    # pays (item, kind, M€/yr), the capital items, CO2 and the assumptions with sources.
    lcoe_eur_per_mwh: Optional[float] = None
    lines_heat: Optional[List[List[object]]] = None
    lines_cold: Optional[List[List[object]]] = None
    capex_items: Optional[List[Dict[str, object]]] = None
    co2_t_per_year: Optional[float] = None
    opex_meur_per_year: Optional[float] = None


class Check(BaseModel):
    """One verifier check; ``requirement`` marks checks of what was asked, not of physics."""

    name: str
    passed: bool
    detail: str
    requirement: bool = False


class Verification(BaseModel):
    """All verifier checks for one design."""

    alternative: str
    checks: List[Check]

    @property
    def passed(self) -> bool:
        """Return True when every check passed."""
        return all(c.passed for c in self.checks)


class LedgerEntry(BaseModel):
    """One evaluated design, kept across turns for what-if questions and comparisons."""

    alternative: Alternative
    brief: DesignBrief
    year: YearResult
    economics: Economics
    verification: Verification
    # A what-if: what changed against the design it was run on (key -> value), in words too.
    changes: Dict[str, object] = Field(default_factory=dict)
    change_label: str = ""
    # Firm capacity (``dioscuri_plant.firm``): the year with each unit out in turn, and what
    # the plant can give on its peak heat and cold days. Not a hard cap: said, not enforced.
    firm: Optional[Dict[str, object]] = None
    # GEMINI's own run of the brine loop set against the plant model (``engine.gemini_check``).
    gemini: Optional[Dict[str, object]] = None


class Question(BaseModel):
    """One item of the consolidated clarifying question."""

    id: str
    label: str
    hint: str = ""
    options: List[str] = Field(default_factory=list)
    default: Optional[str] = None
    required: bool = True
