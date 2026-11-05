"""The plant model's inputs and outputs: plain dataclasses with the unit in every name.

``Rules`` holds the challenge's fixed inputs and hard caps (the organisers' requirements of
28 Oct 2026), ``Plant`` one design (what the agent varies), ``Demand`` the daily profiles.
``YearResult`` and ``Economics`` are what ``simulate_year`` and ``economics`` return; the agent
and the app read these names, so fields may be added but never renamed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

DAYS = 365


@dataclass(frozen=True)
class Aquifer:
    """An aquifer the wells can be drilled into, with its own rock, pressure and gas.

    ``depth_m`` is its midpoint (TVD); ``pressure_bar`` the pressure there, bar(g) like the
    requirements' 250 bar; ``gas_liquid_ratio`` the gas its brine brings up, Nm3 per m3. Its
    temperature follows the gradient at its depth; the brine's other properties (density,
    viscosity, heat capacity, the gas's make-up) are the project's.
    """

    depth_m: float
    thickness_m: float
    permeability_md: float
    pressure_bar: float
    gas_liquid_ratio: float


@dataclass(frozen=True)
class Rules:
    """The challenge's fixed inputs and hard caps; defaults are the requirements document.

    Values the document does not give are marked; each is a sensitivity parameter.
    """

    heat_supply_c: float = 100.0  # fixed
    heat_return_c: float = 60.0  # not given: our assumption (sensitivity 45-70 °C)
    cool_supply_c: float = 20.0  # fixed (read as chilled-water supply; asked)
    cool_return_c: float = 25.0  # not given: our assumption (sensitivity 23-30 °C)
    flow_min_m3h: float = 50.0  # per doublet while running
    flow_max_m3h: float = 300.0  # per doublet
    max_brine_cooling_k: float = 40.0  # producer to injector
    operating_days: int = 330  # per doublet; read as "at most 330 days a year" (asked)
    pump_efficiency: float = 0.70  # hydraulic, all pumps
    brine_density_kg_m3: float = 1030.0
    brine_viscosity_pa_s: float = 0.40e-3
    # Not given. Seawater-like brine of 1,030 kg/m3 (salinity about 41 g/kg) at 60-87 °C:
    # 3.98-4.00 kJ/(kg K) (Sharqawy, Lienhard & Zubair 2010, eq. 9).
    brine_cp_j_kg_k: float = 3990.0
    gas_liquid_ratio: float = 0.8  # Nm3 gas per m3 produced liquid
    gas_ch4_fraction: float = 0.80  # mol
    gas_co2_fraction: float = 0.20  # mol
    # The reservoir (for the doublet model and the record).
    reservoir_depth_m: float = 2500.0
    reservoir_thickness_m: float = 100.0
    gradient_c_per_km: float = 30.0
    surface_temperature_c: float = 12.0
    reservoir_pressure_bar: float = 250.0
    permeability_md: float = 200.0
    # Not given: for the subsurface checks (``subsurface.py``). The spacing is the cost model's.
    porosity: float = 0.20  # Dutch geothermal sandstones 0.15-0.25
    well_spacing_m: float = 1500.0  # producer to injector at the aquifer
    # The district network (``network.py``): 0 km = delivered at the plant's gate (the default).
    network_length_km: float = 0.0
    ground_temperature_c: float = 10.0  # at the pipes' depth, Dutch yearly mean (assumed)
    # Each surface unit's yearly service in its quietest weeks (``service.py``); off by default.
    planned_service: float = 0.0
    # The brine's own CO2 (not the CO2 of burning its methane) dissolved back into the injected
    # brine instead of let out (1 on, 0 off): water-scrubbed from the separated gas at pressure
    # (CO2 dissolves some 25 times more than methane), as at Hellisheidi (CarbFix2).
    co2_reinjection: float = 0.0
    # All the brine's gas flared, none burnt in the boiler (1 on, 0 off): the boiler then buys
    # all its gas. Never chosen by the search; routine flaring needs consent (``year.py``).
    flare_brine_gas: float = 0.0
    # Grid electricity's CO2, t/MWh; None: the components' (CBS 2024 average, 0.20).
    grid_t_co2_per_mwh: Optional[float] = None
    # The grid's CO2 month by month (1 on, 0 off): the year's figure above shaped by Ember's
    # monthly intensity (``Components.grid_month_shape``).
    grid_by_month: float = 0.0
    # Free cooling (1 on, 0 off): on days the outside air's wet bulb is low enough, the cooling
    # towers cool the network's return through a plate exchanger before the chillers do
    # (``year.free_cooling``). Needs towers: a design with chillers or an absorption chiller.
    free_cooling: float = 0.0
    # Own solar panels, MWp (0: none): their electricity first runs the plant, the rest is sold.
    solar_mwp: float = 0.0
    # A hot-water store at the plant, MWh (0: none): it takes the geothermal heat the quiet days
    # leave and gives it back on the days the boiler would run (``year.with_storage``).
    storage_mwh: float = 0.0
    # The store's kind: 0 a steel hot-water tank (DEA), 1 a high-temperature aquifer store
    # (HT-ATES: seasonal, charged at up to ``Components.ates_mw``, recovering a share).
    storage_ates: float = 0.0
    # A second aquifer (0: none): its midpoint, thickness and permeability. Doublets drilled to
    # it (``aquifer_at``) see its rock; its temperature follows the gradient, its pressure is
    # hydrostatic. The search tries it beside the known aquifer.
    second_aquifer_depth_m: float = 0.0
    second_aquifer_thickness_m: float = 0.0
    second_aquifer_permeability_md: float = 0.0
    # The aquifers besides the known one (the reservoir fields above), each with its own rock,
    # pressure and gas-liquid ratio (``Aquifer``): a doublet drilled to one sees it
    # (``aquifer_at``). Depths in none of them are assumed aquifers with the known one's rock.
    other_aquifers: Tuple[Aquifer, ...] = ()
    # Each doublet's planned stops on the user's dates: per doublet, (first, last) days (0-based,
    # inclusive), one block or several. () or a doublet without ranges: in the quietest weeks.
    doublet_stops: Tuple[Tuple[Tuple[int, int], ...], ...] = ()
    # Each doublet's days off a year when Dioscuri places its stop (per doublet; () or 0: the
    # 365 - ``operating_days`` the cap leaves). Fewer than that relaxes the cap (the card does).
    stop_days_off: Tuple[int, ...] = ()
    # The user's yearly service, per unit type: (unit, mode, ranges). Mode "auto" (quietest
    # weeks, ``service.DAYS_OUT`` long), "dates" (each range takes one unit out, a bank's units
    # in turn; units left without dates go in the quietest weeks) or "off". A unit type not
    # listed follows ``planned_service``. Applies only to the units a design has.
    service_plan: Tuple[Tuple[str, str, Tuple[Tuple[int, int], ...]], ...] = ()

    def known_aquifer(self) -> Aquifer:
        """Return the known aquifer (the reservoir fields) as an ``Aquifer``."""
        return Aquifer(
            float(self.reservoir_depth_m),
            float(self.reservoir_thickness_m),
            float(self.permeability_md),
            float(self.reservoir_pressure_bar),
            float(self.gas_liquid_ratio),
        )

    def aquifers(self) -> Tuple[Aquifer, ...]:
        """Return every aquifer described: the known one first, then the others.

        The older ``second_aquifer_*`` fields count as one more (hydrostatic pressure, the
        known aquifer's gas) unless an aquifer is already described at its depth.
        """
        out = [self.known_aquifer(), *self.other_aquifers]
        d = float(self.second_aquifer_depth_m or 0.0)
        if d > 0 and all(abs(a.depth_m - d) > 1.0 for a in out):
            out.append(
                Aquifer(
                    d,
                    float(self.second_aquifer_thickness_m or 0.0) or self.reservoir_thickness_m,
                    float(self.second_aquifer_permeability_md or 0.0) or self.permeability_md,
                    round(self.brine_density_kg_m3 * 9.81 * d / 1e5, 2),
                    float(self.gas_liquid_ratio),
                )
            )
        return tuple(out)

    def aquifer_index(self, depth_m: float) -> Optional[int]:
        """Return which of ``aquifers()`` a well at this depth is in (0: the known one).

        The nearest whose midpoint is within half its thickness (1 m at least); None for a
        depth in none of them (an assumed aquifer, with the known one's rock).
        """
        best: Optional[Tuple[int, float]] = None
        for i, a in enumerate(self.aquifers()):
            gap = abs(float(depth_m) - a.depth_m)
            if gap <= max(a.thickness_m / 2, 1.0) and (best is None or gap < best[1]):
                best = (i, gap)
        return None if best is None else best[0]

    def aquifer_at(self, depth_m: float) -> "Rules":
        """Return the rules a doublet at this depth sees: the aquifer's it is drilled into.

        The known aquifer (and an assumed one, at a depth no aquifer is described at): these
        rules. Another aquifer: its depth, thickness, permeability, pressure and gas-liquid
        ratio in the reservoir fields, and no other aquifer (the doublet sees only its own).
        """
        from dataclasses import replace

        i = (
            self.aquifer_index(depth_m)
            if (self.other_aquifers or self.second_aquifer_depth_m)
            else 0
        )
        if not i:
            return self
        a = self.aquifers()[i]
        return replace(
            self,
            reservoir_depth_m=a.depth_m,
            reservoir_thickness_m=a.thickness_m,
            permeability_md=a.permeability_md,
            reservoir_pressure_bar=a.pressure_bar,
            gas_liquid_ratio=a.gas_liquid_ratio,
            other_aquifers=(),
            second_aquifer_depth_m=0.0,
            second_aquifer_thickness_m=0.0,
            second_aquifer_permeability_md=0.0,
        )

    def hydrostatic_bar(self, depth_m: float) -> float:
        """Return the brine column's pressure at a depth, bar(g): an assumed aquifer's."""
        return self.brine_density_kg_m3 * 9.81 * float(depth_m) / 1e5

    def reservoir_temperature_c(self, depth_m: Optional[float] = None) -> float:
        """Return the reservoir temperature at a depth from the gradient (87 °C at 2,500 m)."""
        depth = self.reservoir_depth_m if depth_m is None else depth_m
        return self.surface_temperature_c + self.gradient_c_per_km * depth / 1000.0

    def brine_mw_per_k(self, flow_m3h):
        """Return the brine's heat-capacity rate (MW/K) at a flow (m3/h); arrays welcome."""
        return (
            np.asarray(flow_m3h, dtype=float)
            / 3600.0
            * (self.brine_density_kg_m3 * self.brine_cp_j_kg_k / 1e6)
        )


OPENINGS = ("full", "upper", "lower")
DISPATCHES = ("equal", "base")
# Units that can be out on given days (``Plant.outages``). "doublet 2" is its producer or ESP;
# "injector 2" one of doublet 2's two injectors (halves its flow; with one injector the doublet
# stops); "train 1" a treatment train (its doublets stop); "boiler unit" and "chiller unit" one
# of ``boiler_units`` / ``chiller_units`` equal units.
OUTAGE_UNITS = (
    "heat exchanger",
    "heat pump",
    "boiler",
    "boiler unit",
    "electric boiler",
    "electric boiler unit",
    "chillers",
    "chiller unit",
    "absorption",
)
# What the plant does with gas: ``buy`` (the boiler burns the brine's gas, then buys gas),
# ``produced`` (the boiler burns only the brine's gas; none is bought), ``sell`` (the brine's
# gas is cleaned and sold to the gas grid; nothing is burnt on site).
GAS_MODES = ("buy", "produced", "sell")
OUTAGE_NUMBERED = ("doublet", "injector", "train")


@dataclass(frozen=True)
class Doublet:
    """One doublet: a producer, one or two injectors, its flow cap and its treatment train.

    ``depth_m`` is the midpoint (TVD) of the aquifer the wells are drilled into: the known
    reservoir, or an assumed one deeper. Each well is open over the whole aquifer (``full``,
    the usual completion) or over its ``upper`` or ``lower`` half: the produced brine has the
    rock's temperature at the middle of the producer's open part, and a half-open well has half
    the productivity (or injectivity). Two injectors share the doublet's brine equally. Doublets
    with the same ``train`` share one treatment train (separator and filters) at the surface.
    """

    depth_m: float = 2500.0
    producer_open: str = "full"
    injector_open: str = "full"
    injectors: int = 1
    max_flow_m3h: Optional[float] = None  # None: the rules' cap (300 m3/h)
    # The least it runs at when it runs (None: the rules' minimum, 50 m3/h); equal to the cap,
    # the doublet runs at that one rate (2 Nov: "at least 150 m3/h", "fixed at 200 m3/h").
    min_flow_m3h: Optional[float] = None
    train: int = 0

    def __post_init__(self):
        """Refuse what makes no sense."""
        if self.producer_open not in OPENINGS or self.injector_open not in OPENINGS:
            raise ValueError(f"open intervals are one of {OPENINGS}")
        if self.injectors not in (1, 2):
            raise ValueError("a doublet has one or two injectors")
        if self.max_flow_m3h is not None and self.max_flow_m3h <= 0:
            raise ValueError("max_flow_m3h must be positive")
        if self.min_flow_m3h is not None and self.min_flow_m3h <= 0:
            raise ValueError("min_flow_m3h must be positive")
        if (
            self.min_flow_m3h is not None
            and self.max_flow_m3h is not None
            and self.min_flow_m3h > self.max_flow_m3h
        ):
            raise ValueError("min_flow_m3h must not exceed max_flow_m3h")

    def cap_m3h(self, rules: "Rules") -> float:
        """Return the doublet's flow cap: its own, never above the rules' cap."""
        cap = rules.flow_max_m3h if self.max_flow_m3h is None else self.max_flow_m3h
        return min(cap, rules.flow_max_m3h)

    def floor_m3h(self, rules: "Rules") -> float:
        """Return the least flow it runs at: its own, at least the minimum, at most the cap."""
        floor = max(rules.flow_min_m3h, self.min_flow_m3h or 0.0)
        return min(floor, self.cap_m3h(rules))


def open_interval(depth_m: float, opening: str, thickness_m: float) -> Tuple[float, float]:
    """Return the middle (TVD, m) and the length (m) of a well's open part of the aquifer."""
    if opening == "full":
        return depth_m, thickness_m
    half = thickness_m / 2.0
    return (depth_m - half / 2.0 if opening == "upper" else depth_m + half / 2.0), half


@dataclass(frozen=True)
class Plant:
    """One design: the doublets and the size of each surface unit (0 = not installed).

    ``n_doublets`` identical doublets at ``depth_m`` unless ``doublet_specs`` sets each one.
    ``dispatch`` says how the doublets share the brine each day: ``equal`` shares, or ``base``,
    the hottest doublet first up to its cap (then the next).
    """

    n_doublets: int  # 0 (the gas reference) to 3
    depth_m: float = 2500.0
    hex_approach_k: float = 5.0
    heat_pump_mw: float = 0.0  # top-up heat pump on the brine, heat output
    recovery_heat_pump_mw: float = 0.0  # takes heat from the cooling network (not modelled yet)
    absorption_mw: float = 0.0  # cold output, driven by the brine
    chiller_mw: float = 0.0  # electric chillers, cold output
    boiler_mw: float = 0.0  # heat output
    electric_boiler_mw: float = 0.0  # heat output, after the gas boiler
    chp_mw_el: float = 0.0  # electrical output (not modelled yet)
    burn_produced_gas: bool = True  # in the boiler; the rest is flared
    stop_start_day: Optional[Tuple[int, ...]] = None  # per doublet, 0-based; None: chosen
    name: str = ""
    doublet_specs: Tuple[Doublet, ...] = ()
    dispatch: str = "equal"
    # (unit, first day, last day), 0-based and inclusive: a unit out on those days (a failure,
    # a what-if). Units are ``OUTAGE_UNITS`` or "doublet 1", "injector 1", "train 1".
    outages: Tuple[Tuple[str, int, int], ...] = ()
    boiler_units: int = 1  # equal units the boiler capacity is built as
    chiller_units: int = 1
    electric_boiler_units: int = 1
    gas: str = "buy"  # one of ``GAS_MODES``
    reliable: bool = False  # sized so that any one unit can be out (``firm.reliable``)

    def __post_init__(self):
        """Refuse what makes no sense (the hard caps are checked, not refused)."""
        if not 0 <= self.n_doublets <= 3:
            raise ValueError(f"n_doublets must be 0 to 3, not {self.n_doublets}")
        for key in (
            "heat_pump_mw",
            "absorption_mw",
            "chiller_mw",
            "boiler_mw",
            "electric_boiler_mw",
            "chp_mw_el",
        ):
            if getattr(self, key) < 0:
                raise ValueError(f"{key} cannot be negative")
        if self.stop_start_day is not None and len(self.stop_start_day) != self.n_doublets:
            raise ValueError("stop_start_day needs one day per doublet")
        if self.doublet_specs and len(self.doublet_specs) != self.n_doublets:
            raise ValueError("doublet_specs needs one Doublet per doublet")
        if self.dispatch not in DISPATCHES:
            raise ValueError(f"dispatch is one of {DISPATCHES}")
        if self.boiler_units < 1 or self.chiller_units < 1 or self.electric_boiler_units < 1:
            raise ValueError("a plant has at least one unit of each")
        if self.gas not in GAS_MODES:
            raise ValueError(f"gas is one of {GAS_MODES}")
        for unit, first, last in self.outages:
            if not 0 <= first <= last < DAYS:
                raise ValueError(f"outage days run 0-{DAYS - 1}, first before last")
            kind, _, number = unit.rpartition(" ")
            if unit in OUTAGE_UNITS:
                continue
            if kind not in OUTAGE_NUMBERED or not number.isdigit() or int(number) < 1:
                raise ValueError(f"unknown unit {unit!r}")
            if kind in ("doublet", "injector") and int(number) > self.n_doublets:
                raise ValueError(f"{unit} is not in a plant of {self.n_doublets} doublet(s)")

    def specs(self) -> Tuple[Doublet, ...]:
        """Return each doublet's set-up (identical ones at ``depth_m`` when not given)."""
        if self.doublet_specs:
            return self.doublet_specs
        return tuple(Doublet(depth_m=self.depth_m) for _ in range(self.n_doublets))

    @property
    def wells(self) -> int:
        """Return the number of wells: a producer and its injectors per doublet."""
        return sum(1 + d.injectors for d in self.specs())

    @property
    def trains(self) -> int:
        """Return how many treatment trains the surface plant has: separators and filters."""
        return len({d.train for d in self.specs()})

    def out(self, unit: str) -> np.ndarray:
        """Return 365 booleans, True on the days ``outages`` lists for this unit."""
        days = np.zeros(DAYS, dtype=bool)
        for name, first, last in self.outages:
            if name == unit:
                days[first : last + 1] = True
        return days

    def train_numbers(self) -> Tuple[int, ...]:
        """Return each doublet's treatment train as 1, 2 ... in order of first use."""
        seen: Dict[int, int] = {}
        return tuple(seen.setdefault(d.train, len(seen) + 1) for d in self.specs())


@dataclass(frozen=True)
class Demand:
    """Daily mean demand (MW) for each of the 365 days of 2027."""

    heat_mw: Tuple[float, ...]
    cool_mw: Tuple[float, ...]
    dates: Tuple[str, ...] = ()

    def __post_init__(self):
        """Check that both profiles cover the year."""
        if len(self.heat_mw) != DAYS or len(self.cool_mw) != DAYS:
            raise ValueError("demand needs 365 daily values for heat and for cold")

    @classmethod
    def from_csv(cls, heat_csv, cool_csv) -> "Demand":
        """Read the organisers' files (``date,heating_demand_MWth`` and ``date,cooling_...``)."""
        heat, dates = _column(heat_csv)
        cool, _ = _column(cool_csv)
        return cls(tuple(heat), tuple(cool), tuple(dates))

    def arrays(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return heat and cold demand, MW, as numpy vectors."""
        return np.asarray(self.heat_mw, dtype=float), np.asarray(self.cool_mw, dtype=float)


def _column(path) -> Tuple[List[float], List[str]]:
    with open(Path(path), newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    body = [r for r in rows[1:] if len(r) >= 2 and r[0].strip()]
    return [float(r[1]) for r in body], [r[0].strip() for r in body]


# doublet(flow_m3h, depth_m, open_m=None) -> {"wellhead_c", "esp_mw", "injector_pump_mw", ...}
# depth_m: the middle of the well's open part; open_m: its length (None: the aquifer's thickness).
DoubletModel = Callable[..., dict]


@dataclass
class YearResult:
    """One year at daily resolution; every value carries its unit in its name."""

    plant: Plant
    source: str
    heat_demand_gwh: float
    cool_demand_gwh: float
    heat_delivered_gwh: float
    cool_delivered_gwh: float
    heat_coverage: float
    cool_coverage: float
    heat_split_gwh: Dict[str, float]  # geo, hp, recovery_hp, boiler, electric_boiler, chp
    cool_split_gwh: Dict[str, float]  # abs, chill, recovery_hp
    peak_heat_mw: float
    peak_cool_mw: float
    daily_mw: Dict[str, Dict[str, List[float]]]
    monthly_gwh: Dict[str, Dict[str, List[float]]]
    doublets: List[Dict[str, list]]  # per doublet: flow_m3h, on, reinjection_c (365 each)
    electricity_gwh: Dict[str, float]  # hp, chillers, pumps, towers, electric_boiler, network
    purchased_gas_gwh: float
    produced_gas_burned_gwh: float
    produced_gas_flared_gwh: float
    co2_t: Dict[str, float]  # purchased_gas, produced_gas, electricity, total
    violations: List[str]
    # Detail the agent and the app use (added fields).
    wellhead_c: float = 0.0
    wellhead_min_c: float = 0.0  # at the lowest flow of the year (the brine cools more when slow)
    reservoir_c: float = 0.0
    max_brine_cooling_k: float = 0.0
    min_reinjection_c: float = 0.0
    heat_pump_cop: float = 0.0  # heat-weighted over the year
    chiller_cop: float = 0.0
    absorption_cop: float = 0.0
    full_load_hours: float = 0.0  # geothermal heat / installed geothermal capacity
    brine_m3: float = 0.0  # produced (= injected) over the year
    peak_shortfall_mw: Dict[str, float] = field(default_factory=dict)
    peak_brine_heat_mw: float = 0.0  # largest daily heat taken from the brine (sizes the plant)
    stop_days: List[Tuple[int, int]] = field(default_factory=list)  # (first, last) per doublet
    # Every stop of each doublet, (first, last) ranges; ``stop_days`` keeps each one's first.
    stop_ranges: List[List[Tuple[int, int]]] = field(default_factory=list)
    balance_error: float = 0.0  # worst daily |delivered - sources| / demand
    # Per doublet: depth, open parts, injectors, train, flows, temperatures, pumps' energy.
    doublet_summary: List[Dict[str, object]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)  # not caps: worth saying
    network: Optional[Dict[str, object]] = None  # the district network's losses (``network.py``)
    service: List[Tuple[str, int, int]] = field(default_factory=list)  # planned service windows
    # The brine's gas cleaned and sold to the grid (``Plant.gas == "sell"``), its methane.
    produced_gas_sold_gwh: float = 0.0
    # Free cooling's largest day, MW of cold (sizes its plate exchanger); 0 without it.
    free_cooling_mw: float = 0.0
    # The cooling towers' water over the year, m3: evaporation, blow-down and make-up (the two
    # together), from all the heat they reject (``components.tower_water_m3``).
    tower_water_m3: Optional[Dict[str, float]] = None
    # Own solar: generated, used by the plant, sold (GWh a year); None without panels.
    solar: Optional[Dict[str, float]] = None
    # The hot-water store: charged, given back, lost (GWh), the gas boiler's heat it saved.
    storage: Optional[Dict[str, object]] = None
    # Minimum loads and trips (``operability``): each unit's days below its minimum and starts.
    operability: Optional[Dict[str, object]] = None
    # ``co2_t["total"]`` by the unit that lets it out, t a year, in a fixed order: boiler,
    # electric_boiler, hp, pumps (the wells'), flare, brine_co2 (the brine's own CO2 at the
    # separator), chillers, towers, network. The electricity users carry the grid's CO2 on what
    # they draw. Every key is there (0 when none); the parts add up to the total to the tenth.
    co2_by_unit_t: Dict[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True when no hard cap is broken."""
        return not self.violations


@dataclass
class Economics:
    """Costs of one design over its life: levelised cost of heat and cold, capital, CO2."""

    plant: Plant
    source: str
    lcoh_eur_per_mwh: float
    lcoc_eur_per_mwh: Optional[float]
    lcoe_eur_per_mwh: float  # heat and cold together, per MWh delivered
    capex_meur: float
    lines: List[Tuple[str, str, float]]  # (item, kind, meur_per_year), heat and cold together
    lines_heat: List[Tuple[str, str, float]]
    lines_cold: List[Tuple[str, str, float]]
    capex_items: List[Dict[str, object]]
    co2_t_per_year: float
    co2_saving_vs_gas: Optional[float]  # 0..1 against the reference; None for the reference
    opex_meur_per_year: float
    assumptions: Dict[str, Dict[str, object]]  # key -> {"value", "unit", "source"}


def daily_sum(values: Sequence[float]) -> float:
    """Return the energy (GWh) of a series of daily mean powers (MW)."""
    return float(np.sum(values)) * 24.0 / 1000.0
