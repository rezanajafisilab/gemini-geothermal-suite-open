"""Design search: plant layouts, each sized, checked against the caps, improved, priced, ranked.

A layout (``Topology``) is the number of doublets and how each is built (the aquifer it is
drilled into, the part of it each well is open to, one or two injectors, shared or separate
treatment trains), how the doublets share the brine, how the network is topped up to 100 °C and
how cold is made. The search runs in two stages:

1. every layout the brief allows with the usual wells (open over the whole aquifer, one
   injector, one shared treatment train), each doublet count with both ways of sharing the
   brine;
2. variants of the best three: two injectors per doublet, separate treatment trains, and wells
   open over only half the aquifer (the producer in the lower half, the injector in either).

Each layout is sized several ways (the heat pump's share of the top-up, the absorption
chiller's share of the cooling peak) by rules of thumb; each sizing runs for a year, and while a
hard cap breaks (a day short of heat or cold) the unit that is short grows by the worst gap and
the year runs again. The best valid sizing stands for the layout. Valid layouts are priced and
ranked; every other one keeps the reason it lost, so the agent can say what it tried.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from dioscuri_plant.components import Components, produced_gas
from dioscuri_plant.economics import Prices, economics
from dioscuri_plant.subsurface import max_flow_m3h
from dioscuri_plant.types import (
    Demand,
    Doublet,
    DoubletModel,
    Economics,
    Plant,
    Rules,
    YearResult,
)
from dioscuri_plant.year import gas_flow, simulate_year

TOPUPS = {"heat_pump": "heat pump on the brine", "boiler": "gas boiler"}
COOLINGS = {"absorption": "absorption + electric chillers", "electric": "electric chillers"}
DEPTHS = (2500.0,)
MAX_ROUNDS = 4
ABSORPTION_SHARE = 0.6  # of the cooling peak, the first guess when absorption is chosen
ABSORPTION_SHARES = (0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0)
HEAT_PUMP_SHARES = (0.1, 0.2, 0.3, 0.5, 0.75, 1.0)  # of the top-up at full flow
STAGE_TWO = 3  # layouts whose variants are tried
CO2_BAND = 0.02  # "lowest CO2" takes the cheapest design within 2 % of the lowest CO2
# Variant flags, in the order they appear in a code.
FLAGS = {
    "2I": "two injectors per doublet",
    "ST": "a treatment train (separator, filters) per doublet",
    "BL": "the hottest doublet first (base load)",
    "PL": "producers open over the lower half of the aquifer",
    "IU": "injectors open over the upper half of the aquifer",
    "IL": "injectors open over the lower half of the aquifer",
    "N1": "sized so that any one unit can be out (N-1): boiler and chillers in equal units",
    "EB": "no gas bought: heat pumps and an electric boiler for the peaks (the brine's own gas "
    "burnt in a small boiler unless it is sold)",
    "GS": "the brine's gas cleaned and sold to the gas grid (nothing burnt on site)",
}


def flag_words(flag: str) -> str:
    """Return a variant flag in words, the per-doublet ones too (``2I1``, ``ST2``)."""
    if flag in FLAGS:
        return FLAGS[flag]
    if flag.startswith("2I"):
        which = " and ".join(flag[2:])
        return f"two injectors on doublet{'s' if len(flag) > 3 else ''} {which}"
    if flag.startswith("ST"):
        return f"{flag[2:]} treatment trains"
    if flag == "PU":
        return "producers open over the upper half of the aquifer"
    if len(flag) > 2 and flag[:2] in ("PL", "PU", "IL", "IU"):
        well = "producer" if flag[0] == "P" else "injector"
        half = "lower" if flag[1] == "L" else "upper"
        which = " and ".join(flag[2:])
        return (
            f"the {well} of doublet{'s' if len(flag) > 3 else ''} {which} open over the {half} half"
        )
    return flag


@dataclass(frozen=True)
class Topology:
    """What a candidate is made of, before sizing."""

    n_doublets: int
    topup: str = "heat_pump"  # or "boiler"
    cooling: str = "absorption"  # or "electric"
    depth_m: float = 2500.0  # the aquifer of every doublet, unless ``depths`` says otherwise
    depths: Tuple[float, ...] = ()  # one per doublet when they differ
    injectors: int = 1  # per doublet
    trains: str = "shared"  # or "separate"
    dispatch: str = "equal"  # or "base"
    producer_open: str = "full"
    injector_open: str = "full"
    known_depth_m: float = 2500.0  # the known aquifer's midpoint (codes name other depths)
    specs: Tuple[Doublet, ...] = ()  # each doublet as the user described it (overrides above)
    gas: str = "buy"  # ``Plant.gas``: buy, produced (no gas bought) or sell

    def aquifers(self) -> Tuple[float, ...]:
        """Return each doublet's aquifer depth."""
        if self.specs:
            return tuple(d.depth_m for d in self.specs)
        return self.depths or tuple(self.depth_m for _ in range(self.n_doublets))

    def doublets(self) -> Tuple[Doublet, ...]:
        """Return each doublet's set-up."""
        if self.specs:
            return self.specs
        return tuple(
            Doublet(
                depth_m=d,
                producer_open=self.producer_open,
                injector_open=self.injector_open,
                injectors=self.injectors,
                train=i if self.trains == "separate" else 0,
            )
            for i, d in enumerate(self.aquifers())
        )

    @property
    def flags(self) -> List[str]:
        """Return the variant flags that set this layout apart, such as ``2I`` or ``ST``."""
        if self.n_doublets == 0:
            return []
        return plant_flags(
            Plant(
                self.n_doublets,
                doublet_specs=self.doublets(),
                dispatch=self.dispatch if self.n_doublets > 1 else "equal",
                gas=self.gas,
            )
        )

    @property
    def code(self) -> str:
        """Return a short code, for example ``2D-HP-AB`` or ``2D-BO-EC@3000-2I-BL``."""
        if self.n_doublets == 0:
            return "REF"
        top = "HP" if self.topup == "heat_pump" else "BO"
        cold = "AB" if self.cooling == "absorption" else "EC"
        return f"{self.n_doublets}D-{top}-{cold}" + _suffix(
            self.aquifers(), self.flags, self.known_depth_m
        )

    @property
    def name(self) -> str:
        """Return the candidate in words."""
        if self.n_doublets == 0:
            return "Gas boilers and electric chillers (reference)"
        plural = "s" if self.n_doublets > 1 else ""
        depths = sorted(set(self.aquifers()))
        where = " and ".join(f"{d:,.0f} m" for d in depths)
        wells = f"{self.n_doublets} doublet{plural} at {where}"
        extra = [flag_words(f) for f in self.flags]
        top = TOPUPS[self.topup] if self.gas == "buy" or self.topup != "boiler" else "boiler"
        return ", ".join([wells, f"{top} top-up", COOLINGS[self.cooling], *extra])


def _suffix(aquifers: Sequence[float], flags: Sequence[str], known_m: float = 2500.0) -> str:
    """Return the depth and flag part of a code: ``@3000``, ``@2500+3000``, ``-2I-ST``."""
    depth = ""
    if len(set(aquifers)) > 1:
        depth = "@" + "+".join(f"{d:g}" for d in aquifers)
    elif aquifers and aquifers[0] != known_m:
        depth = f"@{aquifers[0]:g}"
    return depth + "".join(f"-{f}" for f in flags)


def plant_flags(plant: Plant) -> List[str]:
    """Return a plant's variant flags from its doublets (see ``FLAGS``)."""
    specs = plant.specs()
    out = []
    if specs and all(d.injectors == 2 for d in specs):
        out.append("2I")
    elif any(d.injectors == 2 for d in specs):
        out.append("2I" + "".join(str(i + 1) for i, d in enumerate(specs) if d.injectors == 2))
    if plant.n_doublets > 1 and plant.trains == plant.n_doublets:
        out.append("ST")
    elif 1 < plant.trains < plant.n_doublets:
        out.append(f"ST{plant.trains}")
    if plant.dispatch == "base" and plant.n_doublets > 1:
        out.append("BL")
    for attr, letter in (("producer_open", "P"), ("injector_open", "I")):
        for half, mark in (("lower", "L"), ("upper", "U")):
            which = [i + 1 for i, d in enumerate(specs) if getattr(d, attr) == half]
            if specs and len(which) == len(specs):
                out.append(letter + mark)
            elif which:  # some doublets only: "PL2" = doublet 2's producer, lower half
                out.append(letter + mark + "".join(str(i) for i in which))
    if plant.reliable:
        out.append("N1")
    if plant.gas != "buy":
        out.append("EB")
    if plant.gas == "sell":
        out.append("GS")
    return out


def plant_code(plant: Plant, known_depth_m: float = 2500.0) -> str:
    """Return a short code from what a design has: ``2D-HP-EC`` (``@3000``, ``-2I`` ...).

    HP: heat pump top-up, BO: boiler only, DH: no top-up; AB: absorption (with or without
    electric chillers), EC: electric chillers only, NC: no cooling. ``@`` gives the aquifer
    when it is not the known one (``@2500+3000``: one per doublet), and the flags the variants:
    2I two injectors per doublet, ST a treatment train per doublet, BL the hottest doublet
    first, PL/PU producers and IU/IL injectors open over half the aquifer.
    """
    if plant.n_doublets == 0:
        return "REF"
    top = (
        "HP"
        if plant.heat_pump_mw > 0
        else "BO" if plant.boiler_mw > 0 or plant.electric_boiler_mw > 0 else "DH"
    )
    cold = "AB" if plant.absorption_mw > 0 else "EC" if plant.chiller_mw > 0 else "NC"
    aquifers = tuple(d.depth_m for d in plant.specs())
    return f"{plant.n_doublets}D-{top}-{cold}" + _suffix(
        aquifers, plant_flags(plant), known_depth_m
    )


@dataclass
class Round:
    """One run of a candidate: its sizes, the caps it broke and what changed next."""

    plant: Plant
    violations: List[str]
    change: str = ""


@dataclass
class Candidate:
    """A candidate after the search: its rounds, final year, price, and verdict."""

    topology: Topology
    rounds: List[Round]
    year: YearResult
    economics: Optional[Economics]
    status: str = "valid"  # valid, chosen, failed, same, reference
    reason: str = ""
    stage: int = 1  # 2: a variant of one of the best layouts
    parent: str = ""  # the layout a variant was made from
    sizings: List[Dict[str, object]] = field(default_factory=list)  # every sizing tried
    effect: str = ""  # a variant: what it changed against its parent, in numbers

    @property
    def plant(self) -> Plant:
        """Return the final sizes."""
        return self.rounds[-1].plant


@dataclass
class SearchResult:
    """All candidates, the chosen one and the reference they are measured against."""

    candidates: List[Candidate]
    chosen: Optional[Candidate]
    reference: Candidate
    objective: str
    notes: List[str] = field(default_factory=list)
    years: int = 0  # simulated years in all

    @property
    def sizings(self) -> int:
        """Return how many sizings were run in all."""
        return sum(len(c.sizings) for c in self.candidates)


def _up(x: float, step: float = 0.1) -> float:
    return math.ceil(max(x, 0.0) / step - 1e-9) * step


def first_guess(
    top: Topology,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules,
    excluded: Sequence[str] = (),
    heat_pump_share: float = 1.0,
    absorption_share: float = ABSORPTION_SHARE,
) -> Plant:
    """Size a candidate by rules of thumb (the search then corrects it).

    The heat pump covers ``heat_pump_share`` of the top-up of the doublets' full flow; the
    boiler the January peak beyond what the doublets and heat pump give; absorption
    ``absorption_share`` of the cooling peak and the electric chillers the rest.
    """
    heat, cool = demand.arrays()
    peak_heat, peak_cool = float(heat.max()), float(cool.max())
    if top.n_doublets == 0:
        return Plant(0, boiler_mw=_up(peak_heat), chiller_mw=_up(peak_cool), name=top.name)
    specs = top.doublets()
    caps = [d.cap_m3h(rules) for d in specs]
    wellheads = [doublet(cap, d.depth_m)["wellhead_c"] for d, cap in zip(specs, caps)]
    wellhead = sum(w * c for w, c in zip(wellheads, caps)) / sum(caps)
    cb = float(rules.brine_mw_per_k(sum(caps)))
    cw = peak_heat / (rules.heat_supply_c - rules.heat_return_c)
    tx = min(wellhead - 5.0, rules.heat_supply_c)
    flow = min(cb, cw)
    geo = flow * max(tx - rules.heat_return_c, 0.0)
    topup = flow * (rules.heat_supply_c - tx)
    hp = _up(topup * heat_pump_share) if top.topup == "heat_pump" else 0.0
    boiler = _up(peak_heat - geo - hp)
    electric = 0.0
    if top.gas != "buy":  # no gas bought: an electric boiler where the gas boiler would be
        electric, boiler = boiler, 0.0
        if top.gas == "produced":  # a small boiler for the brine's own gas
            # Each doublet's brine at its cap, with its own aquifer's gas.
            flow, ratio = gas_flow([[c] for c in caps], specs, rules)
            ch4_mw = produced_gas(
                float(flow[0]), ratio, rules.gas_ch4_fraction, rules.gas_co2_fraction
            )[0]
            boiler = _up(float(ch4_mw) * Components().boiler_efficiency)
    absorption = _up(absorption_share * peak_cool) if top.cooling == "absorption" else 0.0
    if absorption and "chiller" in excluded:
        absorption = _up(peak_cool)  # no electric chillers to share the peak with
    return Plant(
        top.n_doublets,
        depth_m=top.aquifers()[0],
        heat_pump_mw=hp,
        boiler_mw=boiler,
        electric_boiler_mw=electric,
        absorption_mw=absorption,
        chiller_mw=_up(peak_cool - absorption),
        name=top.name,
        doublet_specs=specs,
        dispatch=top.dispatch if top.n_doublets > 1 else "equal",
        gas=top.gas,
    )


def improve(
    top: Topology,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
    excluded: Sequence[str] = (),
    heat_pump_share: float = 1.0,
    absorption_share: float = ABSORPTION_SHARE,
) -> Tuple[List[Round], YearResult]:
    """Run a candidate; while a day is short of heat or cold, grow the unit that is short.

    Parameters
    ----------
    excluded : sequence of str
        Units that may not be added or grown: ``"boiler"``, ``"heat_pump"``, ``"chiller"``.
    heat_pump_share, absorption_share : float
        The first guess's sizes (see ``first_guess``).

    Returns
    -------
    tuple of (list of Round, YearResult)
        Each round's sizes and broken caps, and the last year.
    """
    plant = first_guess(top, demand, doublet, rules, excluded, heat_pump_share, absorption_share)
    if "boiler" in excluded:  # the gas boiler
        plant = replace(plant, boiler_mw=0.0)
    if "electric_boiler" in excluded:
        plant = replace(plant, electric_boiler_mw=0.0)
    if "chiller" in excluded:
        plant = replace(plant, chiller_mw=0.0)
    rounds: List[Round] = []
    year = simulate_year(plant, demand, doublet, rules, components)
    for _ in range(MAX_ROUNDS):
        rounds.append(Round(plant, list(year.violations)))
        short_heat, short_cool = year.peak_shortfall_mw["heat"], year.peak_shortfall_mw["cool"]
        changes = []
        was = rounds[-1].plant
        capped = subsurface_caps(plant, year, rules)
        if capped is not None:
            plant, said = capped
            changes.append(said)
        if short_heat > 1e-6:
            if "electric_boiler" not in excluded and plant.gas != "buy":
                grown = _up(plant.electric_boiler_mw + short_heat)
                plant = replace(plant, electric_boiler_mw=grown)
                changes.append(f"electric boiler {was.electric_boiler_mw:g} -> {grown:g} MW")
            elif "boiler" not in excluded and plant.gas == "buy":
                plant = replace(plant, boiler_mw=_up(plant.boiler_mw + short_heat))
                changes.append(f"boiler {was.boiler_mw:g} -> {plant.boiler_mw:g} MW")
            elif plant.heat_pump_mw > 0 and "heat_pump" not in excluded:
                plant = replace(plant, heat_pump_mw=_up(plant.heat_pump_mw + short_heat))
                changes.append(f"heat pump {was.heat_pump_mw:g} -> {plant.heat_pump_mw:g} MW")
        if short_cool > 1e-6:
            if "chiller" not in excluded:
                plant = replace(plant, chiller_mw=_up(plant.chiller_mw + short_cool))
                changes.append(f"chillers {was.chiller_mw:g} -> {plant.chiller_mw:g} MW")
            elif plant.absorption_mw > 0:
                plant = replace(plant, absorption_mw=_up(plant.absorption_mw + short_cool))
                changes.append(f"absorption {was.absorption_mw:g} -> {plant.absorption_mw:g} MW")
        if plant == was:
            changes = []  # nothing could grow: the cap stays broken
        if not changes:
            break
        rounds[-1].change = "; ".join(changes)
        before = sum(year.peak_shortfall_mw.values())
        year = simulate_year(plant, demand, doublet, rules, components)
        after = sum(year.peak_shortfall_mw.values())
        if before > 1e-6 and after > before - 0.05 and not capped:
            # Growing it did not close the gap (the heat pump is held by the brine's 40 K cap,
            # or the absorption chiller by the brine flow): stop, with the reason.
            rounds.append(Round(plant, list(year.violations)))
            rounds[-1].change = (
                f"growing it left the gap at {after:.2f} MW: the unit is not what limits the "
                "plant (the brine's flow or its 40 K cap does)"
            )
            break
    else:
        rounds.append(Round(plant, list(year.violations)))
    return rounds, year


def subsurface_caps(plant: Plant, year: YearResult, rules: Rules) -> Optional[Tuple[Plant, str]]:
    """Cap the flow of doublets that break the ESP or injection limits; None when none do.

    The highest flow within both limits (``subsurface.max_flow_m3h``) becomes the doublet's
    cap, so the next year runs it slower and the boiler or heat pump covers the rest.
    """
    rows = {int(r["doublet"]): r for r in year.doublet_summary}
    specs = list(plant.specs())
    said = []
    for i, spec in enumerate(specs):
        row = rows.get(i + 1)
        problems = row.get("subsurface_problems", []) if row else []
        if not any("ESP" in x or "injection" in x for x in problems):
            continue
        q = max_flow_m3h(
            spec,
            rules.aquifer_at(spec.depth_m),  # the aquifer it is drilled into
            float(row["producer_mid_m"]),
            float(row["pi_m3h_per_bar"]),
            float(row["injectivity_m3h_per_bar"]),
            float(row["wellhead_full_c"]),
        )
        q = math.floor(q / 5.0) * 5.0  # a round number below the limit
        if q < rules.flow_min_m3h or q >= spec.cap_m3h(rules) - 1e-6:
            continue
        specs[i] = replace(spec, max_flow_m3h=q)
        said.append(f"doublet {i + 1} capped at {q:g} m3/h (ESP and injection limits)")
    if not said:
        return None
    return replace(plant, doublet_specs=tuple(specs)), "; ".join(said)


def sizings(top: Topology, excluded: Sequence[str] = ()) -> List[Tuple[float, float]]:
    """Return the (heat pump share, absorption share) pairs a layout is sized with."""
    hp = HEAT_PUMP_SHARES if top.topup == "heat_pump" else (1.0,)
    ab = (
        ABSORPTION_SHARES
        if top.cooling == "absorption" and "chiller" not in excluded
        else (ABSORPTION_SHARE,)
    )
    return [(h, a) for h in hp for a in ab]


def topologies(
    excluded: Sequence[str] = (),
    doublets: Iterable[int] = (1, 2, 3),
    depths: Iterable[float] = DEPTHS,
    known_depth_m: float = 2500.0,
    fixed: Optional[Dict[str, object]] = None,
) -> List[Topology]:
    """Return the first stage's layouts, without the excluded units.

    Every doublet count, top-up and cooling choice; each doublet in any of the allowed aquifers
    (the same one or different ones), with the usual wells unless ``fixed`` says otherwise;
    two or more doublets sharing the brine both ways unless ``fixed["dispatch"]`` is set.

    ``fixed`` may hold ``injectors``, ``trains``, ``dispatch``, ``producer_open``,
    ``injector_open`` (the same for every doublet) or ``specs`` (a tuple of ``Doublet``, each
    doublet as described: the doublet count is then theirs).
    """
    fixed = fixed or {}
    tops = []
    depths = tuple(depths)
    specs = tuple(fixed.get("specs") or ())
    counts = [len(specs)] if specs else list(doublets)
    for n in counts:
        if specs:
            combos = [tuple(d.depth_m for d in specs)]
        else:
            combos = list(itertools.combinations_with_replacement(depths, n)) if n else [()]
        for combo in combos:
            same = len(set(combo)) <= 1
            dispatches = (fixed["dispatch"],) if fixed.get("dispatch") else ("equal", "base")
            for dispatch in dispatches if n > 1 else ("equal",):
                for topup in TOPUPS:
                    if topup == "heat_pump" and "heat_pump" in excluded:
                        continue
                    for cooling in COOLINGS:
                        if (
                            cooling == "electric"
                            and "chiller" in excluded
                            and "absorption" not in excluded
                        ):
                            continue
                        tops.append(
                            Topology(
                                n,
                                topup,
                                cooling,
                                combo[0] if combo else depths[0],
                                () if same else tuple(combo),
                                injectors=int(fixed.get("injectors") or 1),
                                trains=str(fixed.get("trains") or "shared"),
                                dispatch=dispatch,
                                producer_open=str(fixed.get("producer_open") or "full"),
                                injector_open=str(fixed.get("injector_open") or "full"),
                                known_depth_m=known_depth_m,
                                specs=specs,
                            )
                        )
    return tops


def variants(top: Topology, fixed: Optional[Dict[str, object]] = None) -> List[Topology]:
    """Return the second stage's variants of a layout: injectors, trains, open intervals.

    Only along what the brief left open (``fixed`` as in ``topologies``); none for doublets
    the user described one by one.
    """
    fixed = fixed or {}
    if top.specs or top.n_doublets == 0:
        return []
    out = []
    if not fixed.get("injectors") and top.injectors == 1:
        out.append(replace(top, injectors=2))
    if not fixed.get("trains") and top.n_doublets > 1 and top.trains == "shared":
        out.append(replace(top, trains="separate"))
    if not fixed.get("producer_open") and top.producer_open == "full":
        out.append(replace(top, producer_open="lower"))
    if not fixed.get("injector_open") and top.injector_open == "full":
        out += [replace(top, injector_open="lower"), replace(top, injector_open="upper")]
    return out


# The plant's own options (``Rules`` fields): what a design adds to its plant, not a premise of
# the place. The gas reference never has them, so every design, with or without options, is
# measured against one and the same gas plant. The last two act on the brine's gas only and
# so cannot change a plant without wells; they are listed so the reference never depends on
# them either.
PLANT_OPTIONS = (
    "free_cooling",
    "solar_mwp",
    "storage_mwh",
    "storage_ates",
    "co2_reinjection",
    "flare_brine_gas",
)


def reference_rules(rules: Rules) -> Rules:
    """Return the rules the gas reference runs under: these, without the plant's options.

    Free cooling, own solar and a heat store are a design's choices (``PLANT_OPTIONS``); the
    network, the returns, the grid's CO2 and the service plan stay, as they hold for any plant.
    """
    return replace(rules, **{k: 0.0 for k in PLANT_OPTIONS})


OBJECTIVES: Dict[str, Tuple[str, Callable[[Candidate], float]]] = {
    "cost": ("lowest cost of heat and cold", lambda c: c.economics.lcoe_eur_per_mwh),
    "co2": ("lowest CO2", lambda c: c.economics.co2_t_per_year),
}


def run_layout(
    top: Topology,
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules,
    components: Components,
    prices: Prices,
    excluded: Sequence[str],
    reference: Tuple[YearResult, Economics],
    objective: str = "cost",
) -> Candidate:
    """Size a layout every way it allows; return the best valid sizing as the candidate.

    Every sizing is kept in ``Candidate.sizings`` (shares, sizes, cost, CO2, valid), so the
    agent can say which sizes it tried.
    """
    _, key = OBJECTIVES[objective]
    best: Optional[Candidate] = None
    tried: List[Dict[str, object]] = []
    for hp_share, ab_share in sizings(top, excluded):
        rounds, year = improve(
            top, demand, doublet, rules, components, excluded, hp_share, ab_share
        )
        econ = economics(rounds[-1].plant, year, prices, reference=reference, rules=rules)
        cand = Candidate(top, rounds, year, econ)
        plant = cand.plant
        tried.append(
            {
                "heat_pump_share": hp_share if top.topup == "heat_pump" else None,
                "absorption_share": ab_share if top.cooling == "absorption" else None,
                "heat_pump_mw": plant.heat_pump_mw,
                "boiler_mw": plant.boiler_mw,
                "electric_boiler_mw": plant.electric_boiler_mw,
                "absorption_mw": plant.absorption_mw,
                "chiller_mw": plant.chiller_mw,
                "lcoe": econ.lcoe_eur_per_mwh,
                "co2_t": econ.co2_t_per_year,
                "valid": not year.violations,
                "years": len(rounds),
            }
        )
        if best is None or _better(cand, best, key):
            best = cand
    assert best is not None
    best.sizings = tried
    if best.year.violations:
        best.status, best.reason = "failed", best.year.violations[0]
    return best


def _layout_with(state: dict, top: Topology) -> Candidate:
    return run_layout(
        top,
        state["demand"],
        state["doublet"],
        state["rules"],
        state["components"],
        state["prices"],
        state["excluded"],
        state["reference"],
        state["objective"],
    )


def run_layouts(tops: Sequence[Topology], state: dict) -> List[Candidate]:
    """Run layouts, in worker processes when there are many (``parallel.pmap``; in order).

    Layouts are independent: a search of 150 ran in 12 s on one core, under 3 s on 8 (2 Nov).
    """
    from dioscuri_plant.parallel import pmap

    return pmap(_layout_with, tops, state)


def _better(a: Candidate, b: Candidate, key) -> bool:
    """Return True when ``a`` beats ``b``: valid before invalid, then by the objective."""
    if bool(a.year.violations) != bool(b.year.violations):
        return not a.year.violations
    if a.year.violations:  # both short: the smaller gap
        return sum(a.year.peak_shortfall_mw.values()) < sum(b.year.peak_shortfall_mw.values())
    return key(a) < key(b) - 1e-9


def search(
    demand: Demand,
    doublet: DoubletModel,
    rules: Rules = Rules(),
    components: Components = Components(),
    prices: Prices = Prices(),
    excluded: Sequence[str] = (),
    doublets: Iterable[int] = (1, 2, 3),
    depths: Iterable[float] = DEPTHS,
    objective: str = "cost",
    layouts: Optional[Sequence[Topology]] = None,
    stage_two: bool = True,
    fixed: Optional[Dict[str, object]] = None,
) -> SearchResult:
    """Run every layout, size and improve each until its caps hold, price them and pick one.

    Parameters
    ----------
    excluded : sequence of str
        Units the user ruled out.
    doublets, depths : iterables
        The numbers of doublets and the aquifer depths to consider.
    objective : {"cost", "co2"}
        What "best" means among the valid candidates.
    layouts : sequence of Topology, optional
        The first stage's layouts, when the caller builds them (instead of ``topologies``).
    stage_two : bool
        Whether to try the variants of the best layouts.
    fixed : dict, optional
        How the doublets are built when the user said so (see ``topologies``).

    Returns
    -------
    SearchResult
        Every candidate with its rounds and verdict, the chosen one and the gas reference.
    """
    ref_top = Topology(0)
    ref_rules = reference_rules(rules)  # one gas plant for every design, options or not
    ref_rounds, ref_year = improve(ref_top, demand, doublet, ref_rules, components)
    ref_econ = economics(ref_rounds[-1].plant, ref_year, prices, rules=ref_rules)
    reference = Candidate(ref_top, ref_rounds, ref_year, ref_econ, status="reference")
    label, key = OBJECTIVES[objective]
    first = (
        list(layouts)
        if layouts is not None
        else topologies(excluded, doublets, depths, rules.reservoir_depth_m, fixed)
    )
    out: List[Candidate] = []
    seen: Dict[tuple, Candidate] = {}
    state = {
        "demand": demand,
        "doublet": doublet,
        "rules": rules,
        "components": components,
        "prices": prices,
        "excluded": tuple(excluded),
        "reference": (ref_year, ref_econ),
        "objective": objective,
    }

    def add(cand: Candidate, stage: int, parent: str = "") -> Candidate:
        cand.stage, cand.parent = stage, parent
        k = _sizes(cand.plant)
        if k in seen and cand.status != "failed":  # e.g. deep wells need no top-up
            cand.status = "same"
            cand.reason = f"the same plant as {seen[k].topology.code}"
        seen.setdefault(k, cand)
        out.append(cand)
        return cand

    for cand in run_layouts(first, state):
        add(cand, 1)
    if stage_two:
        best = sorted((c for c in out if c.status == "valid"), key=key)[:STAGE_TWO]
        done = {c.topology for c in out}
        todo: List[Tuple[Topology, str]] = []
        for parent in best:
            for top in variants(parent.topology, fixed):
                if top not in done:
                    done.add(top)
                    todo.append((top, parent.topology.code))
        for (top, parent_code), cand in zip(todo, run_layouts([t for t, _ in todo], state)):
            add(cand, 2, parent_code)
    valid = sorted((c for c in out if c.status == "valid"), key=key)
    chosen = valid[0] if valid else None
    if chosen is not None and objective == "co2":
        # Lowest CO2 "within reason": the cheapest design within CO2_BAND of the lowest. Without
        # it the search bought the last 24 t a year for 21 M€ of extra wells (31 Oct panel).
        least = chosen.economics.co2_t_per_year
        near = [c for c in valid if c.economics.co2_t_per_year <= least * (1 + CO2_BAND)]
        chosen = min(near, key=lambda c: c.economics.lcoe_eur_per_mwh)
        valid = [chosen] + [c for c in valid if c is not chosen]
    if chosen is not None:
        chosen.status = "chosen"
        for c in valid[1:]:
            c.reason = _lost(c, chosen, objective)
    by_code = {c.topology.code: c for c in out}
    for c in out:
        if c.stage == 2 and c.status in ("valid", "failed") and c.parent in by_code:
            what = variant_effect(c, by_code[c.parent])
            c.effect = what
            c.reason = f"{what}; {c.reason}" if c.reason else what
    years = sum(int(s["years"]) for c in out for s in c.sizings) + len(ref_rounds)
    notes = [f"ranked by {label}"]
    return SearchResult(out, chosen, reference, objective, notes=notes, years=years)


def variant_effect(c: Candidate, parent: Candidate) -> str:
    """Say in numbers what a stage-two variant changed against the layout it came from."""
    a, b = c.economics, parent.economics
    ya, yb = c.year, parent.year
    pumps = ya.electricity_gwh["pumps"] - yb.electricity_gwh["pumps"]
    capex = a.capex_meur - b.capex_meur
    flags = set(c.topology.flags) - set(parent.topology.flags)
    head = f"against {parent.topology.code}: "
    if "2I" in flags:
        return head + (
            f"{capex:+.1f} M€ of capital for the extra injector(s), {abs(pumps):.2f} GWh a year "
            f"{'less' if pumps < 0 else 'more'} pumping (half the brine through each injector, "
            "so a lower injection pressure)"
        )
    if "ST" in flags:
        return head + (
            f"{capex:+.2f} M€ for a treatment train per doublet; the heat is the same (the "
            "trains only degas and filter the brine; a spare train keeps the others running)"
        )
    if flags & {"PL", "IU", "IL"}:
        sa = (ya.doublet_summary or [{}])[0]
        sb = (yb.doublet_summary or [{}])[0]
        well = "producer" if "PL" in flags else "injector"
        if well == "producer":
            detail = (
                f"wellhead {sa.get('wellhead_full_c', 0):.1f} °C against "
                f"{sb.get('wellhead_full_c', 0):.1f} °C, ESP head "
                f"{sa.get('esp_head_full_bar', 0):.0f} bar against "
                f"{sb.get('esp_head_full_bar', 0):.0f} bar at full flow"
            )
        else:
            detail = (
                f"injection pressure {sa.get('injection_full_bar', 0):.0f} bar against "
                f"{sb.get('injection_full_bar', 0):.0f} bar at full flow"
            )
        index = "productivity" if well == "producer" else "injectivity"
        return head + (
            f"the {well} open over half the aquifer has half the {index}: "
            f"{detail}, {abs(pumps):.2f} GWh a year {'less' if pumps < 0 else 'more'} pumping"
        )
    return head + f"{a.lcoe_eur_per_mwh - b.lcoe_eur_per_mwh:+.1f} €/MWh"


def _sizes(plant: Plant) -> tuple:
    return (
        plant.n_doublets,
        plant.specs(),
        plant.dispatch if plant.n_doublets > 1 else "equal",
        round(plant.heat_pump_mw, 1),
        round(plant.boiler_mw, 1),
        round(plant.electric_boiler_mw, 1),
        plant.gas,
        round(plant.absorption_mw, 1),
        round(plant.chiller_mw, 1),
    )


def _lost(c: Candidate, best: Candidate, objective: str) -> str:
    """Say why a valid candidate lost to the chosen one, in numbers."""
    a, b = c.economics, best.economics
    if objective == "co2":
        if a.co2_t_per_year <= b.co2_t_per_year * (1 + CO2_BAND) and a.co2_t_per_year < (
            b.co2_t_per_year
        ):
            return (
                f"{b.co2_t_per_year - a.co2_t_per_year:,.0f} t CO2 a year less, for "
                f"{a.lcoe_eur_per_mwh - b.lcoe_eur_per_mwh:+.1f} €/MWh "
                f"({(a.capex_meur - b.capex_meur):+.1f} M€ of capital): within "
                f"{CO2_BAND:.0%} of the lowest, the cheaper one is picked"
            )
        if abs(a.co2_t_per_year - b.co2_t_per_year) < 0.005 * b.co2_t_per_year:
            return f"as little CO2, but {a.lcoe_eur_per_mwh - b.lcoe_eur_per_mwh:+.1f} €/MWh"
        return f"{a.co2_t_per_year:,.0f} t CO2 a year against {b.co2_t_per_year:,.0f} t"
    gap = a.lcoe_eur_per_mwh - b.lcoe_eur_per_mwh
    if abs(gap) < 0.05:
        extra = a.capex_meur - b.capex_meur
        return f"the same cost per MWh, but {extra:+.1f} M€ of capital"
    return (
        f"{gap:+.1f} €/MWh of heat and cold "
        f"({a.lcoe_eur_per_mwh:.1f} against {b.lcoe_eur_per_mwh:.1f})"
    )
