"""The design space swept: thousands of designs drawn by Latin hypercube, failures kept.

The layout search (``search``) sizes each layout until its caps hold: some 60 to 100 designs,
none failed, all near the cheapest sizing of their layout. This draws designs across the whole
space at once (2 Nov): the number of doublets, their depth and flow cap, every unit's size and
what the plant does with gas. Each is run for a year with its sizes as drawn and priced, and
every one is kept: the ones that meet every cap, and the ones that do not with the cap they
break first. The map shows where the feasible designs lie, what they cost and emit, and where
the space ends. The best feasible ones are then refined, each unit shrunk while every cap still
holds, and join the search's candidates.

Latin hypercube: each dimension is cut into ``n`` equal strata and each stratum is drawn once,
so 5,000 designs cover every dimension's range evenly (McKay, Beckman & Conover 1979). Depths
are drawn in 100 m steps and flow caps in 10 m3/h steps, so the doublet model's solutions are
shared between designs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from dioscuri_plant.components import Components
from dioscuri_plant.economics import Economics, Prices, economics
from dioscuri_plant.search import Candidate, Round, Topology
from dioscuri_plant.types import GAS_MODES, Demand, Doublet, DoubletModel, Plant, Rules, YearResult
from dioscuri_plant.year import simulate_year

# What a design that fails breaks first, in the order the year's checks report them.
BROKEN = (
    ("heat", "Heat short"),
    ("cold", "Cooling short"),
    ("days", "runs "),
    ("flow", " flow "),
    ("brine", "cooled by"),
    ("wells", "Doublet "),
)
BROKEN_WORDS = {
    "heat": "heat short on some days",
    "cold": "cold short on some days",
    "days": "a doublet runs more days than allowed",
    "flow": "a doublet's flow outside its range",
    "brine": "the brine cooled by more than the cap",
    "wells": "a well check (injection pressure, ESP depth, cold front)",
    "cost": "no cost per MWh (it delivers no heat or cold)",
    "other": "another cap",
}
UNITS = ("heat_pump_mw", "boiler_mw", "electric_boiler_mw", "absorption_mw", "chiller_mw")
# A drawn size below this share of its range is "not installed".
NONE_BELOW = 0.08
DEFAULT_N = int(os.environ.get("DIOSCURI_SWEEP", "5000"))


@dataclass
class Point:
    """One drawn design and its year: sizes, cost, CO2 and the cap it breaks ("" if none)."""

    n_doublets: int
    depth_m: float
    flow_cap_m3h: float
    heat_pump_mw: float
    boiler_mw: float
    electric_boiler_mw: float
    absorption_mw: float
    chiller_mw: float
    gas: str
    lcoe: float
    lcoh: float
    co2_t: float
    co2_saving: float
    capex_meur: float
    broken: str = ""  # a ``BROKEN`` key, or "" when every cap holds

    @property
    def ok(self) -> bool:
        """Return True when the design meets every cap."""
        return not self.broken

    def row(self) -> list:
        """Return the point's values in the order of ``Exploration.COLUMNS``.

        A cost or saving that is not a number (a drawn design that delivers no heat divides by
        zero; such a point is broken, "cost") is None: NaN is not JSON, and on 3 Nov it made the
        Compare map's request fail with a server error.
        """
        return [
            self.n_doublets,
            self.depth_m,
            self.flow_cap_m3h,
            round(self.heat_pump_mw, 2),
            round(self.boiler_mw, 2),
            round(self.electric_boiler_mw, 2),
            round(self.absorption_mw, 2),
            round(self.chiller_mw, 2),
            self.gas,
            _finite(self.lcoe, 2),
            _finite(self.lcoh, 2),
            _finite(self.co2_t, 0),
            _finite(self.co2_saving * 100, 1),
            _finite(self.capex_meur, 2),
            self.broken,
        ]


def _finite(x: float, digits: int) -> Optional[float]:
    """Return ``x`` rounded, or None when it is not a finite number."""
    return round(float(x), digits) if np.isfinite(x) else None


@dataclass
class Exploration:
    """The sweep: every drawn design, the feasible ones' front and the refined designs."""

    COLUMNS = (
        "doublets",
        "depth_m",
        "flow_cap_m3h",
        "heat_pump_mw",
        "boiler_mw",
        "electric_boiler_mw",
        "absorption_mw",
        "chiller_mw",
        "gas",
        "lcoe",
        "lcoh",
        "co2_t",
        "co2_saving_pct",
        "capex_meur",
        "broken",
    )
    points: List[Point]
    front: List[int]  # indices of the feasible designs no other beats on both cost and CO2
    refined: List[Candidate] = field(default_factory=list)
    seconds: float = 0.0
    ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    @property
    def feasible(self) -> int:
        """Return how many drawn designs meet every cap."""
        return sum(p.ok for p in self.points)

    def failures(self) -> Dict[str, int]:
        """Return how many designs break each cap first."""
        out: Dict[str, int] = {}
        for p in self.points:
            if p.broken:
                out[p.broken] = out.get(p.broken, 0) + 1
        return out

    def as_dict(self) -> dict:
        """Return the sweep for the map: columns, rows, the front, ranges and counts."""
        return {
            "columns": list(self.COLUMNS),
            "rows": [p.row() for p in self.points],
            "front": self.front,
            "ranges": {k: list(v) for k, v in self.ranges.items()},
            "feasible": self.feasible,
            "failures": self.failures(),
            "broken_words": BROKEN_WORDS,
            "seconds": round(self.seconds, 1),
        }


def latin_hypercube(n: int, d: int, rng: np.random.Generator) -> np.ndarray:
    """Return ``n`` points in the unit cube, one in each of ``n`` strata of every dimension."""
    u = (rng.random((n, d)) + np.arange(n)[:, None]) / n
    for j in range(d):
        u[:, j] = u[rng.permutation(n), j]
    return u


def on_grid(x: float, lo: float, hi: float, step: float) -> float:
    """Return the value of the grid ``step`` apart in ``[lo, hi]`` that a unit draw ``x`` falls in.

    The range is cut into one equal bin per grid value, so every value (the two ends too) is
    drawn as often as the others. Rounding ``lo + x (hi - lo)`` to the nearest step instead gave
    each end half a bin: half as many designs at the shallowest and deepest wells and at the
    lowest and highest flow caps (4 Nov). A range narrower than a step gives ``lo``.
    """
    first = float(np.ceil(lo / step - 1e-9) * step)
    last = float(np.floor(hi / step + 1e-9) * step)
    if last < first:
        return float(lo)
    k = int(round((last - first) / step))
    return float(min(first + np.floor(x * (k + 1)) * step, last))


def broken_of(violations: Sequence[str]) -> str:
    """Return the first cap a year breaks, as a ``BROKEN`` key ("" when none)."""
    for v in violations:
        for key, word in BROKEN:
            if word in v:
                return key
        return "other"
    return ""


def draw(
    n: int,
    demand: Demand,
    rules: Rules,
    excluded: Sequence[str] = (),
    doublets: Sequence[int] = (1, 2, 3),
    depths: Tuple[float, float] = (2500.0, 2500.0),
    seed: int = 7,
    levels: Sequence[float] = (),
) -> Tuple[List[Plant], Dict[str, Tuple[float, float]]]:
    """Return ``n`` plants drawn across the design space, and each dimension's range.

    ``excluded`` units (``heat_pump``, ``boiler``, ``electric_boiler``, ``absorption``,
    ``chiller``) are never installed. ``levels``: the only depths there are (the aquifers
    described); a drawn depth goes to the nearest of them. Without them any depth in the range
    is drawn (an assumed aquifer, to the nearest 100 m).
    """
    rng = np.random.default_rng(seed)
    peak_heat = float(np.max(demand.heat_mw))
    peak_cool = float(np.max(demand.cool_mw))
    ranges = {
        "depth_m": (float(min(depths)), float(max(depths))),
        "flow_cap_m3h": (max(rules.flow_min_m3h + 50.0, 100.0), rules.flow_max_m3h),
        "heat_pump_mw": (0.0, 0.5 * peak_heat),
        "boiler_mw": (0.0, 1.2 * peak_heat),
        "electric_boiler_mw": (0.0, 1.2 * peak_heat),
        "absorption_mw": (0.0, 1.2 * peak_cool),
        "chiller_mw": (0.0, 1.5 * peak_cool),
    }
    unit_of = {
        "heat_pump_mw": "heat_pump",
        "boiler_mw": "boiler",
        "electric_boiler_mw": "electric_boiler",
        "absorption_mw": "absorption",
        "chiller_mw": "chiller",
    }
    u = latin_hypercube(n, 4 + len(UNITS), rng)
    counts = sorted(set(int(x) for x in doublets)) or [1]
    aquifers = sorted(set(float(d) for d in levels))
    plants = []
    for row in u:
        k = counts[min(int(row[0] * len(counts)), len(counts) - 1)]
        depth = on_grid(row[1], *ranges["depth_m"], 100.0)
        if aquifers:  # each aquifer described drawn as often as the others
            depth = aquifers[min(int(row[1] * len(aquifers)), len(aquifers) - 1)]
        flow = on_grid(row[2], *ranges["flow_cap_m3h"], 10.0)
        gas = GAS_MODES[min(int(row[3] * len(GAS_MODES)), len(GAS_MODES) - 1)]
        sizes = {}
        for j, key in enumerate(UNITS):
            lo, hi = ranges[key]
            x = row[4 + j]
            on = x >= NONE_BELOW and unit_of[key] not in excluded
            size = lo + (x - NONE_BELOW) / (1 - NONE_BELOW) * (hi - lo)
            sizes[key] = round(float(size), 1) if on else 0.0
        specs = tuple(Doublet(depth_m=depth, max_flow_m3h=flow) for _ in range(k))
        plants.append(Plant(k, depth_m=depth, doublet_specs=specs, gas=gas, **sizes))
    return plants, ranges


# The state each worker process runs with (set once, before the plants are shared out).
_STATE: dict = {}


def _init(state: dict) -> None:
    _STATE.clear()
    _STATE.update(state)


def _run_one(plant: Plant) -> Tuple[Point, Optional[Tuple[YearResult, Economics]]]:
    s = _STATE
    try:
        year = simulate_year(plant, s["demand"], s["doublet"], s["rules"], s["components"])
        econ = economics(plant, year, s["prices"], reference=s["reference"], rules=s["rules"])
    except (ValueError, ZeroDivisionError, FloatingPointError):
        return _failed(plant, "other"), None
    broken = broken_of(year.violations)
    costs = (
        econ.lcoe_eur_per_mwh,
        econ.lcoh_eur_per_mwh,
        econ.co2_t_per_year,
        econ.co2_saving_vs_gas,
        econ.capex_meur,
    )
    if not broken and not all(x is None or np.isfinite(x) for x in costs):
        broken = "cost"  # no cost per MWh: it delivers no heat or cold (NaN, 3 Nov)
    point = Point(
        plant.n_doublets,
        plant.depth_m,
        plant.doublet_specs[0].max_flow_m3h or s["rules"].flow_max_m3h,
        plant.heat_pump_mw,
        plant.boiler_mw,
        plant.electric_boiler_mw,
        plant.absorption_mw,
        plant.chiller_mw,
        plant.gas,
        float(econ.lcoe_eur_per_mwh or 0.0),
        float(econ.lcoh_eur_per_mwh or 0.0),
        float(econ.co2_t_per_year),
        float(econ.co2_saving_vs_gas or 0.0),
        float(econ.capex_meur),
        broken,
    )
    return point, (year, econ)


def _run_with(state: dict, plant: Plant) -> Point:
    if _STATE.get("demand") is not state.get("demand"):  # a worker's first design
        _init(state)
    return _run_one(plant)[0]


def _failed(plant: Plant, broken: str) -> Point:
    return Point(
        plant.n_doublets,
        plant.depth_m,
        plant.doublet_specs[0].max_flow_m3h or 0.0 if plant.doublet_specs else 0.0,
        plant.heat_pump_mw,
        plant.boiler_mw,
        plant.electric_boiler_mw,
        plant.absorption_mw,
        plant.chiller_mw,
        plant.gas,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        broken,
    )


def front_of(points: Sequence[Point]) -> List[int]:
    """Return the feasible points no other feasible point beats on both cost and CO2.

    Cheapest first. Points of the same cost are taken by CO2, so of two at exactly one cost the
    one with more CO2 (dominated by the other) is not kept.
    """
    ok = sorted(
        (i for i, p in enumerate(points) if p.ok), key=lambda i: (points[i].lcoe, points[i].co2_t)
    )
    out, least = [], float("inf")
    for i in ok:
        if points[i].co2_t < least - 1e-9:
            out.append(i)
            least = points[i].co2_t
    return out


def _plant_of(p: Point) -> Plant:
    specs = tuple(
        Doublet(depth_m=p.depth_m, max_flow_m3h=p.flow_cap_m3h) for _ in range(p.n_doublets)
    )
    return Plant(
        p.n_doublets,
        depth_m=p.depth_m,
        doublet_specs=specs,
        gas=p.gas,
        heat_pump_mw=p.heat_pump_mw,
        boiler_mw=p.boiler_mw,
        electric_boiler_mw=p.electric_boiler_mw,
        absorption_mw=p.absorption_mw,
        chiller_mw=p.chiller_mw,
    )


def refine(point: Point, steps: Sequence[float] = (0.5, 0.25, 0.1)) -> Tuple[Plant, int]:
    """Shrink each unit of a feasible design while every cap holds and the cost falls.

    Returns the refined plant and how many years were run. Runs in the calling process with
    the state ``_init`` set.
    """
    plant = _plant_of(point)
    best_point, _ = _run_one(plant)
    years = 1
    for step in steps:
        improved = True
        while improved:
            improved = False
            for key in UNITS:
                size = getattr(plant, key)
                if size <= 0:
                    continue
                smaller = round(size * (1 - step), 2)
                trial = replace(plant, **{key: smaller if smaller >= 0.2 else 0.0})
                got, _ = _run_one(trial)
                years += 1
                if got.ok and got.lcoe < best_point.lcoe - 1e-6:
                    plant, best_point, improved = trial, got, True
    return plant, years


def spread(front: Sequence[int], k: int) -> List[int]:
    """Return ``k`` points of the front to refine: its cheapest, its lowest-CO2 and evenly between.

    Chosen by position along the front (cheapest first), not by the points' numbers: on 4 Nov
    the picks were sorted by number before the cut, and the lowest-CO2 point of a front of 7 was
    dropped. The whole front when it has ``k`` points or fewer.
    """
    front = list(front)
    if k <= 0 or not front:
        return []
    if len(front) <= k:
        return front
    if k == 1:
        return front[:1]
    at = sorted({int(round(j * (len(front) - 1) / (k - 1))) for j in range(k)})
    return [front[j] for j in at]


def topology_of(plant: Plant, known_depth_m: float) -> Topology:
    """Return the layout a drawn plant has (for its code and name)."""
    return Topology(
        plant.n_doublets,
        topup="heat_pump" if plant.heat_pump_mw > 0 else "boiler",
        cooling="absorption" if plant.absorption_mw > 0 else "electric",
        depth_m=plant.depth_m,
        known_depth_m=known_depth_m,
        specs=plant.doublet_specs,
        gas=plant.gas,
    )


def explore(
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules,
    components: Components,
    prices: Prices,
    reference: Tuple[YearResult, Economics],
    excluded: Sequence[str] = (),
    doublets: Sequence[int] = (1, 2, 3),
    depths: Tuple[float, float] = (2500.0, 2500.0),
    n: int = DEFAULT_N,
    refine_top: int = 10,  # the whole front as a rule (7 points for the challenge; 0.2 s each)
    seed: int = 7,
    workers: Optional[int] = None,
    levels: Sequence[float] = (),
) -> Exploration:
    """Draw ``n`` designs, run and price each, keep them all, refine the best feasible ones.

    Parameters
    ----------
    reference : tuple of (YearResult, Economics)
        The gas reference, for each design's CO2 saving.
    depths : (low, high)
        The depth range to draw from (one value: every design at that depth).
    workers : int, optional
        Processes to run the designs in; by default up to 8, one per CPU (1 runs them here).

    Returns
    -------
    Exploration
        Every design, the cost-CO2 front of the feasible ones and the refined designs (stage
        3 candidates of the search).
    """
    import time

    start = time.perf_counter()
    plants, ranges = draw(n, demand, rules, excluded, doublets, depths, seed, levels)
    state = {
        "demand": demand,
        "doublet": doublet,
        "rules": rules,
        "components": components,
        "prices": prices,
        "reference": reference,
    }
    _init(state)
    from dioscuri_plant.parallel import pmap

    if workers == 1:
        points = [_run_one(p)[0] for p in plants]
    else:
        points = pmap(_run_with, plants, state, min_items=400)
    front = front_of(points)
    refined: List[Candidate] = []
    for i in spread(front, refine_top):
        plant, years = refine(points[i])
        point, run = _run_one(plant)
        if run is None or not point.ok:
            continue
        year, econ = run
        top = topology_of(plant, rules.reservoir_depth_m)
        cand = Candidate(
            top,
            [
                Round(
                    plant,
                    [],
                    f"drawn in the design-space sweep, then each unit shrunk ({years} years)",
                )
            ],
            year,
            econ,
            stage=3,
            effect="from the design-space sweep",
        )
        cand.sizings = [{"years": years}]
        refined.append(cand)
    return Exploration(points, front, refined, seconds=time.perf_counter() - start, ranges=ranges)
