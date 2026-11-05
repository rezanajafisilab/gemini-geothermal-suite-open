"""Component specs for model generation: interface, physics, reference cases and checks.

Each ``ComponentSpec`` describes a component Dioscuri has no model for: what it does, its
inputs and outputs with units, the physics relations a generated model must implement (cited
per spec), reference operating points and the physics checks its outputs must pass. The
checks are plain code over a batch of cases, ``test(cases, outputs) -> (passed, detail)``,
and their details name the case and the numbers, because they are sent back to the model
when it gets something wrong.

The numbers in ``physics`` are the spec the model implements. The checks test physics
(energy balance, the Carnot limit, bounds, trends, literature ranges), plus the few spec
values a user is told about (the adsorption chiller's minimum drive temperature, the ATES
thermal radius).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from gemini_agent.contract import Check

TOLERANCE = 0.01  # 1 % on energy balances and ratios

Rule = Callable[[List[dict], List[dict]], Tuple[bool, str]]


@dataclass
class Quantity:
    """One input or output of a component, with its unit and typical range.

    Attributes
    ----------
    name : str
        Argument or output key; the unit is in the name (``_c``, ``_mw``, ``_mwh``, ``_m``).
    unit : str
        Unit as written in the report.
    description : str
        What it means, in a few words.
    low, high : float, optional
        Typical range (inputs); the reference cases cover it.
    default : float, optional
        Value assumed when the user does not give one (inputs).
    """

    name: str
    unit: str
    description: str
    low: Optional[float] = None
    high: Optional[float] = None
    default: Optional[float] = None


@dataclass
class PhysicsCheck:
    """A test the generated outputs must pass.

    Attributes
    ----------
    name : str
        Short name shown in the test table.
    rule : str
        The rule in words; the model sees it in the prompt.
    test : callable
        ``test(cases, outputs) -> (passed, detail)`` over the whole batch.
    sweep : bool
        True when the test needs a sweep of cases (for example "rises with drive
        temperature"); such tests are skipped when a registered model is evaluated at a few
        operating points.
    """

    name: str
    rule: str
    test: Rule
    sweep: bool = False


@dataclass
class ReferenceCase:
    """One operating point the code is run at, with optional expected ranges.

    Attributes
    ----------
    inputs : dict
        Keyword arguments for the function.
    expect : dict
        ``{output: (low, high)}`` ranges from the literature (datasheet-style anchors).
    """

    inputs: Dict[str, float]
    expect: Dict[str, Tuple[float, float]] = field(default_factory=dict)


@dataclass
class ComponentSpec:
    """Everything the model needs to write a component model, and everything to test it.

    Attributes
    ----------
    name : str
        Registry key, for example ``adsorption_chiller``.
    title : str
        Plain name, for example ``Adsorption chiller``.
    description : str
        What the component does and where it sits in the plant.
    func_name : str
        Name of the function to write.
    inputs, outputs : list of Quantity
        Arguments and returned keys, with units.
    physics : list of str
        The relations to implement, in order.
    checks : list of PhysicsCheck
        Tests specific to this component (the generic ones are added by ``all_checks``).
    cases : list of ReferenceCase
        Operating points to run.
    sources : list of str
        Where the relations come from.
    keywords : list of str
        Words that name the component in a request (regular expressions).
    """

    name: str
    title: str
    description: str
    func_name: str
    inputs: List[Quantity]
    outputs: List[Quantity]
    physics: List[str]
    checks: List[PhysicsCheck]
    cases: List[ReferenceCase]
    sources: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    @property
    def arguments(self) -> List[str]:
        """Return the input names, which are the function's arguments."""
        return [q.name for q in self.inputs]

    def defaults(self) -> Dict[str, float]:
        """Return the default value of every input that has one."""
        return {q.name: q.default for q in self.inputs if q.default is not None}

    def offer(self) -> str:
        """Return the sentence the agent uses to offer generating this model.

        Returns
        -------
        str
            One question; generation and running the code need the user's yes.
        """
        summary = self.description.split(".")[0]
        summary = summary[:1].lower() + summary[1:]
        return (
            f"Dioscuri has no {self.title.lower()} model yet. I can ask the local model to "
            f"write one from a spec ({summary}), run it in a "
            f"sandbox on {len(self.cases)} reference cases and {len(all_checks(self))} physics "
            "checks, and show you the code and the results before anything is used. "
            "Generate it?"
        )


# ---------------------------------------------------------------------------------------------
# Check helpers


def fmt(x: float) -> str:
    """Return a number with four significant digits for messages."""
    return f"{x:.4g}"


def case_label(case: dict) -> str:
    """Return a case as ``name=value`` pairs for messages."""
    return ", ".join(f"{k}={fmt(v)}" for k, v in case.items())


def per_case(rule: Callable[[dict, dict], Optional[str]]) -> Rule:
    """Turn a rule on one case into a test over the batch.

    Parameters
    ----------
    rule : callable
        ``rule(inputs, outputs)`` returns the problem as a sentence, or ``None``.

    Returns
    -------
    callable
        ``test(cases, outputs) -> (passed, detail)``; the detail names the first failing case.
    """

    def test(cases: List[dict], outputs: List[dict]) -> Tuple[bool, str]:
        problems = []
        for inp, out in zip(cases, outputs):
            problem = rule(inp, out)
            if problem:
                problems.append(f"at {case_label(inp)}: {problem}")
        if problems:
            more = f" ({len(problems) - 1} more cases fail too)" if len(problems) > 1 else ""
            return False, problems[0] + more
        return True, f"holds in all {len(cases)} cases"

    return test


def rises_with(var: str, output: str, min_points: int = 3) -> Rule:
    """Return a test that ``output`` never falls, and does rise, as ``var`` increases.

    Cases that differ only in ``var`` form a sweep; at least one sweep of ``min_points`` or
    more must exist (it is part of the spec's reference cases).

    Parameters
    ----------
    var : str
        The input that is swept.
    output : str
        The output that must not fall.
    min_points : int
        Smallest sweep that counts.

    Returns
    -------
    callable
        ``test(cases, outputs) -> (passed, detail)``.
    """

    def test(cases: List[dict], outputs: List[dict]) -> Tuple[bool, str]:
        groups: Dict[tuple, list] = {}
        for inp, out in zip(cases, outputs):
            key = tuple(sorted((k, v) for k, v in inp.items() if k != var))
            groups.setdefault(key, []).append((inp[var], out[output]))
        sweeps = [sorted(g) for g in groups.values() if len(g) >= min_points]
        if not sweeps:
            return False, f"the cases hold no sweep of {var} with {min_points} or more points"
        for points in sweeps:
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                if y1 < y0 - 1e-9 * max(1.0, abs(y0)):
                    return False, (
                        f"{output} falls from {fmt(y0)} to {fmt(y1)} when {var} rises from "
                        f"{fmt(x0)} to {fmt(x1)}"
                    )
        longest = max(sweeps, key=len)
        if longest[-1][1] <= longest[0][1] + 1e-9:
            return False, (
                f"{output} stays at {fmt(longest[0][1])} from {var}={fmt(longest[0][0])} to "
                f"{fmt(longest[-1][0])}; it should rise"
            )
        return True, (
            f"{output} rises from {fmt(longest[0][1])} to {fmt(longest[-1][1])} as {var} goes "
            f"from {fmt(longest[0][0])} to {fmt(longest[-1][0])}"
        )

    return test


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE * max(abs(a), abs(b)) + 1e-6


# ---------------------------------------------------------------------------------------------
# Adsorption chiller

ADS_CW_WEIGHT = 2.0  # characteristic-equation weight of the cooling water, a
ADS_RATED_DDT_K = 20.0  # characteristic temperature difference at full load
ADS_CARNOT_SHARE = 0.4  # second-law efficiency of a silica gel-water chiller
ADS_COP_MAX = 0.65  # best COP of single-stage silica gel-water chillers
COP_CEILING = 0.7  # what the check allows for any single-stage sorption chiller


def chiller_carnot_cop(drive_c: float, cooling_c: float, chilled_c: float) -> float:
    """Return the reversible COP of a heat-driven chiller working between three temperatures.

    A Carnot engine between the drive and the heat-rejection temperature drives a Carnot
    refrigerator between the chilled water and the heat rejection (Herold, Radermacher and
    Klein, *Absorption Chillers and Heat Pumps*, 2nd ed., 2016, ch. 2).

    Parameters
    ----------
    drive_c, cooling_c, chilled_c : float
        Drive, heat-rejection and chilled-water temperatures, °C.

    Returns
    -------
    float
        ``(1 - T_c / T_g) * T_e / (T_c - T_e)`` in kelvin; 0 when no cooling is possible.
    """
    tg, tc, te = drive_c + 273.15, cooling_c + 273.15, chilled_c + 273.15
    if tg <= tc or tc <= te:
        return 0.0
    return (1.0 - tc / tg) * te / (tc - te)


def ads_min_drive_c(cooling_c: float, chilled_c: float) -> float:
    """Return the drive temperature below which the adsorption chiller gives no cold, °C.

    From the characteristic equation ``ΔΔt = t_G - a·t_AC + e·t_E`` (Hellmann, Schweigler and
    Ziegler 1999; Kühn and Ziegler 2005) with ``a = 2``, ``e = 1`` and ``ΔΔt_min = 0``.

    Parameters
    ----------
    cooling_c, chilled_c : float
        Heat-rejection and chilled-water temperatures, °C.

    Returns
    -------
    float
        ``2 · t_cooling - t_chilled``.
    """
    return ADS_CW_WEIGHT * cooling_c - chilled_c


def _ads_balance(inp: dict, out: dict) -> Optional[str]:
    d, c, r = out["drive_heat_mw"], out["cold_mw"], out["rejected_heat_mw"]
    if not _close(d + c, r):
        return (
            f"drive heat {fmt(d)} + cold {fmt(c)} = {fmt(d + c)} MW, but rejected_heat_mw is "
            f"{fmt(r)} MW"
        )
    return None


def _ads_available(inp: dict, out: dict) -> Optional[str]:
    d, avail = out["drive_heat_mw"], inp["heat_available_mw"]
    if d > avail * (1 + 1e-6) + 1e-9:
        return f"drive_heat_mw is {fmt(d)} MW but only {fmt(avail)} MW is available"
    return None


def _ads_cop_ratio(inp: dict, out: dict) -> Optional[str]:
    d, c, cop = out["drive_heat_mw"], out["cold_mw"], out["cop"]
    if d <= 1e-9:
        if c > 1e-9:
            return f"cold_mw is {fmt(c)} MW with no drive heat"
        if abs(cop) > 1e-6:
            return f"cop is {fmt(cop)} with no drive heat; it should be 0"
        return None
    if not _close(cop, c / d):
        return f"cop is {fmt(cop)} but cold_mw / drive_heat_mw is {fmt(c / d)}"
    return None


def _ads_cop_limit(inp: dict, out: dict) -> Optional[str]:
    d, c = out["drive_heat_mw"], out["cold_mw"]
    if d <= 1e-9:
        return None
    limit = chiller_carnot_cop(
        inp["drive_temp_c"], inp["cooling_water_temp_c"], inp["chilled_water_temp_c"]
    )
    ceiling = min(COP_CEILING, limit)
    cop = c / d
    if cop < -1e-9 or cop > ceiling + 1e-6:
        return (
            f"the COP (cold / drive heat) is {fmt(cop)}; it must lie between 0 and "
            f"{fmt(ceiling)} (Carnot limit {fmt(limit)}, single-stage ceiling {COP_CEILING:g})"
        )
    return None


def _ads_threshold(inp: dict, out: dict) -> Optional[str]:
    t_min = ads_min_drive_c(inp["cooling_water_temp_c"], inp["chilled_water_temp_c"])
    if abs(out["min_drive_temp_c"] - t_min) > 0.5:
        return (
            f"min_drive_temp_c is {fmt(out['min_drive_temp_c'])} °C; it should be "
            f"2 × cooling water - chilled water = {fmt(t_min)} °C"
        )
    if inp["drive_temp_c"] <= t_min and (out["cold_mw"] > 1e-9 or out["drive_heat_mw"] > 1e-9):
        return (
            f"the drive water ({fmt(inp['drive_temp_c'])} °C) is not above the minimum "
            f"{fmt(t_min)} °C, so cold_mw and drive_heat_mw must be 0 (they are "
            f"{fmt(out['cold_mw'])} and {fmt(out['drive_heat_mw'])})"
        )
    return None


def _ads_case(drive: float, avail: float = 3.0, cooling: float = 27.0, chilled: float = 6.0):
    return {
        "drive_temp_c": drive,
        "heat_available_mw": avail,
        "cooling_water_temp_c": cooling,
        "chilled_water_temp_c": chilled,
    }


ADSORPTION_CHILLER = ComponentSpec(
    name="adsorption_chiller",
    title="Adsorption chiller",
    description=(
        "A silica gel-water adsorption chiller driven by low-temperature hot water, such as the "
        "brine leaving the district-heating heat exchanger (45 to 65 °C), which makes chilled "
        "water for the cooling network (6/12 °C) and rejects its heat to cooling-tower water "
        "(25 to 30 °C). Below a minimum drive temperature it gives no cold; above it the "
        "cold output rises with the drive temperature."
    ),
    func_name="adsorption_chiller",
    inputs=[
        Quantity("drive_temp_c", "°C", "hot water temperature driving the chiller", 40, 90, 60),
        Quantity("heat_available_mw", "MW", "hot water heat the chiller may use", 0, 10, 3),
        Quantity("cooling_water_temp_c", "°C", "cooling-tower water temperature", 20, 35, 27),
        Quantity("chilled_water_temp_c", "°C", "chilled water supply temperature", 5, 12, 6),
    ],
    outputs=[
        Quantity("cold_mw", "MW", "cooling delivered"),
        Quantity("drive_heat_mw", "MW", "hot water heat used"),
        Quantity("rejected_heat_mw", "MW", "heat rejected to the cooling water"),
        Quantity("cop", "-", "thermal COP, cold_mw / drive_heat_mw (0 when off)"),
        Quantity("min_drive_temp_c", "°C", "lowest drive temperature that gives cold"),
    ],
    physics=[
        "Kelvin temperatures: tg = drive_temp_c + 273.15, tc = cooling_water_temp_c + 273.15, "
        "te = chilled_water_temp_c + 273.15.",
        "Minimum drive temperature (characteristic equation, Kuehn and Ziegler 2005): "
        f"min_drive_temp_c = {ADS_CW_WEIGHT:g} * cooling_water_temp_c - chilled_water_temp_c.",
        f"Load fraction: load = (drive_temp_c - min_drive_temp_c) / {ADS_RATED_DDT_K:g}, limited "
        "to 0 ... 1.",
        "drive_heat_mw = load * heat_available_mw.",
        "Carnot limit of a heat-driven chiller: cop_carnot = (1 - tc / tg) * te / (tc - te).",
        f"cop = min({ADS_COP_MAX:g}, {ADS_CARNOT_SHARE:g} * cop_carnot) when drive_heat_mw > 0, "
        "otherwise cop = 0.",
        "cold_mw = cop * drive_heat_mw.",
        "rejected_heat_mw = drive_heat_mw + cold_mw (energy balance).",
    ],
    checks=[
        PhysicsCheck(
            "Energy balance",
            "drive_heat_mw + cold_mw = rejected_heat_mw within 1 %",
            per_case(_ads_balance),
        ),
        PhysicsCheck(
            "Uses no more heat than is available",
            "drive_heat_mw <= heat_available_mw",
            per_case(_ads_available),
        ),
        PhysicsCheck(
            "COP = cold / drive heat",
            "cop = cold_mw / drive_heat_mw, and 0 with no cold when drive_heat_mw is 0",
            per_case(_ads_cop_ratio),
        ),
        PhysicsCheck(
            "COP within the Carnot limit",
            "0 <= cold_mw / drive_heat_mw <= the three-temperature Carnot COP, and <= 0.7",
            per_case(_ads_cop_limit),
        ),
        PhysicsCheck(
            "No cold below the minimum drive temperature",
            "min_drive_temp_c = 2 * cooling_water_temp_c - chilled_water_temp_c, and cold_mw "
            "= drive_heat_mw = 0 when drive_temp_c <= min_drive_temp_c",
            per_case(_ads_threshold),
        ),
        PhysicsCheck(
            "Cold rises with drive temperature",
            "with the other inputs fixed, cold_mw never falls as drive_temp_c rises",
            rises_with("drive_temp_c", "cold_mw"),
            sweep=True,
        ),
    ],
    cases=[ReferenceCase(_ads_case(t)) for t in (40, 45, 48, 50, 55, 60)]
    + [
        ReferenceCase(_ads_case(65), {"cop": (0.45, 0.65), "cold_mw": (1.0, 2.0)}),
        ReferenceCase(_ads_case(70)),
        ReferenceCase(_ads_case(80), {"cop": (0.5, 0.65)}),
        ReferenceCase(_ads_case(90)),
        ReferenceCase(_ads_case(55, 1.0, 25.0, 9.0), {"cop": (0.45, 0.65)}),
        ReferenceCase(_ads_case(55, 1.0, 30.0, 6.0)),
        ReferenceCase(_ads_case(45, 5.0, 27.0, 12.0)),
        ReferenceCase(_ads_case(70, 0.0)),
    ],
    sources=[
        "Herold, Radermacher and Klein (2016), Absorption Chillers and Heat Pumps, ch. 2: "
        "three-temperature Carnot COP.",
        "Hellmann, Schweigler and Ziegler (1999); Kuehn and Ziegler (2005): characteristic "
        "equation ΔΔt = t_G - a·t_AC + e·t_E; a = 2, e = 1 and 20 K at full load are "
        "plausible single-stage values, not fitted to a datasheet.",
        "cooling_design.md, section 2: silica gel-water chillers run on 55-90 °C water with "
        "COP 0.45-0.65.",
    ],
    keywords=[r"adsorption", r"adsorptie"],
)

# ---------------------------------------------------------------------------------------------
# Aquifer thermal energy storage (seasonal)

WATER_J_PER_M3K = 4.18e6  # volumetric heat capacity of water
AQUIFER_J_PER_M3K = 2.8e6  # volumetric heat capacity of a saturated sand aquifer
SEASON_CONDUCTION_M = 3.8  # sqrt(alpha * t), alpha = 9e-7 m2/s over half a year
ATES_MAX_RECOVERY = 0.9
J_PER_MWH = 3.6e9


def ates_radius_m(energy_mwh: float, delta_k: float, thickness_m: float) -> float:
    """Return the thermal radius of one ATES well's stored volume.

    ``R_th = sqrt(c_w V / (c_aq π L))`` with ``V`` the stored water volume (Doughty et al.
    1982; Bloemendal and Hartog 2018).

    Parameters
    ----------
    energy_mwh : float
        Energy stored, MWh, relative to the aquifer temperature.
    delta_k : float
        Injection temperature minus aquifer temperature (warm well) or the reverse (cold
        well), K.
    thickness_m : float
        Aquifer (screen) thickness, m.

    Returns
    -------
    float
        Thermal radius, m; 0 when nothing can be stored.
    """
    if energy_mwh <= 0 or delta_k <= 0 or thickness_m <= 0:
        return 0.0
    volume = energy_mwh * J_PER_MWH / (WATER_J_PER_M3K * delta_k)
    return math.sqrt(WATER_J_PER_M3K * volume / (AQUIFER_J_PER_M3K * math.pi * thickness_m))


def _ates_parts(inp: dict) -> List[Tuple[str, float, float]]:
    """Return (prefix, stored MWh, thermal radius) for the warm and the cold well."""
    warm = inp["warm_temp_c"] - inp["aquifer_temp_c"]
    cold = inp["aquifer_temp_c"] - inp["cold_temp_c"]
    return [
        (
            "heat",
            inp["heat_stored_mwh"],
            ates_radius_m(inp["heat_stored_mwh"], warm, inp["thickness_m"]),
        ),
        (
            "cold",
            inp["cold_stored_mwh"],
            ates_radius_m(inp["cold_stored_mwh"], cold, inp["thickness_m"]),
        ),
    ]


def _ates_not_more(inp: dict, out: dict) -> Optional[str]:
    for part, stored, _ in _ates_parts(inp):
        got = out[f"{part}_recovered_mwh"]
        if got > stored * (1 + 1e-6) + 1e-6:
            return f"{part}_recovered_mwh is {fmt(got)} MWh but only {fmt(stored)} MWh was stored"
    return None


def _ates_efficiency(inp: dict, out: dict) -> Optional[str]:
    for part, _, _ in _ates_parts(inp):
        eff = out[f"{part}_recovery"]
        if not -1e-9 <= eff <= ATES_MAX_RECOVERY + 1e-6:
            return f"{part}_recovery is {fmt(eff)}; it must lie between 0 and 0.9"
    return None


def _ates_losses(inp: dict, out: dict) -> Optional[str]:
    for part, _, _ in _ates_parts(inp):
        if out[f"{part}_loss_mwh"] < -1e-6:
            return (
                f"{part}_loss_mwh is {fmt(out[f'{part}_loss_mwh'])} MWh; losses cannot be negative"
            )
    return None


def _ates_balance(inp: dict, out: dict) -> Optional[str]:
    for part, stored, _ in _ates_parts(inp):
        got, lost = out[f"{part}_recovered_mwh"], out[f"{part}_loss_mwh"]
        if not _close(got + lost, stored):
            return (
                f"{part}: recovered {fmt(got)} + lost {fmt(lost)} = {fmt(got + lost)} MWh, but "
                f"{fmt(stored)} MWh was stored"
            )
        eff = out[f"{part}_recovery"]
        expected = got / stored if stored > 0 else 0.0
        if abs(eff - expected) > TOLERANCE * max(eff, expected) + 1e-6:
            return f"{part}_recovery is {fmt(eff)} but recovered / stored is {fmt(expected)}"
    return None


def _ates_radius(inp: dict, out: dict) -> Optional[str]:
    for (part, _, radius), well in zip(_ates_parts(inp), ("warm", "cold")):
        got = out[f"{well}_radius_m"]
        if abs(got - radius) > 0.02 * radius + 0.5:
            return f"{well}_radius_m is {fmt(got)} m; the stored volume gives {fmt(radius)} m"
    return None


def _ates_case(heat: float = 5000.0, cold: float = 4000.0, warm: float = 18.0, **kw) -> dict:
    case = {
        "heat_stored_mwh": heat,
        "cold_stored_mwh": cold,
        "warm_temp_c": warm,
        "cold_temp_c": 7.0,
        "aquifer_temp_c": 12.0,
        "thickness_m": 40.0,
    }
    case.update(kw)
    return case


ATES = ComponentSpec(
    name="ates",
    title="Aquifer thermal energy storage",
    description=(
        "Seasonal aquifer thermal energy storage (ATES) with a warm and a cold well. Summer "
        "heat is stored in the warm well and winter cold in the cold well; the next season "
        "recovers a share of each. The share falls as the stored cylinder of water gets "
        "smaller or the aquifer thinner, because more of it loses heat by conduction to the "
        "surrounding ground. The two wells are independent: an empty warm well leaves the "
        "cold well's results unchanged, and the reverse. Buoyancy (important above about "
        "30 °C) is ignored."
    ),
    func_name="ates",
    inputs=[
        Quantity("heat_stored_mwh", "MWh", "summer heat put in the warm well", 0, 20000, 5000),
        Quantity("cold_stored_mwh", "MWh", "winter cold put in the cold well", 0, 20000, 4000),
        Quantity("warm_temp_c", "°C", "warm well injection temperature", 10, 90, 18),
        Quantity("cold_temp_c", "°C", "cold well injection temperature", 4, 10, 7),
        Quantity("aquifer_temp_c", "°C", "undisturbed aquifer temperature", 10, 14, 12),
        Quantity("thickness_m", "m", "aquifer (well screen) thickness", 10, 100, 40),
    ],
    outputs=[
        Quantity("heat_recovered_mwh", "MWh", "heat recovered from the warm well"),
        Quantity("heat_loss_mwh", "MWh", "heat lost to the ground"),
        Quantity("heat_recovery", "-", "heat_recovered_mwh / heat_stored_mwh"),
        Quantity("cold_recovered_mwh", "MWh", "cold recovered from the cold well"),
        Quantity("cold_loss_mwh", "MWh", "cold lost to the ground"),
        Quantity("cold_recovery", "-", "cold_recovered_mwh / cold_stored_mwh"),
        Quantity("warm_radius_m", "m", "thermal radius of the warm store"),
        Quantity("cold_radius_m", "m", "thermal radius of the cold store"),
    ],
    physics=[
        f"Stored water volume, m3: v_warm = heat_stored_mwh * {J_PER_MWH:g} / ({WATER_J_PER_M3K:g} "
        f"* (warm_temp_c - aquifer_temp_c)) and v_cold = cold_stored_mwh * {J_PER_MWH:g} / "
        f"({WATER_J_PER_M3K:g} * (aquifer_temp_c - cold_temp_c)); a volume is 0 when its energy "
        "or its temperature difference is not positive. Such a well stores nothing: its radius, "
        "recovery and recovered energy are 0 and its loss is all the energy put in.",
        f"Thermal radius, m (Doughty et al. 1982): r = sqrt({WATER_J_PER_M3K:g} * v / "
        f"({AQUIFER_J_PER_M3K:g} * pi * thickness_m)); this gives warm_radius_m and "
        "cold_radius_m.",
        "Recovery of each well (conduction through the cylinder's surface, Bloemendal and "
        f"Hartog 2018): recovery = 1 - {SEASON_CONDUCTION_M:g} * (2 / thickness_m + 2 / r), "
        f"limited to 0 ... {ATES_MAX_RECOVERY:g}; recovery = 0 when r = 0.",
        "heat_recovered_mwh = heat_recovery * heat_stored_mwh and heat_loss_mwh = "
        "heat_stored_mwh - heat_recovered_mwh; the same for cold.",
    ],
    checks=[
        PhysicsCheck(
            "Recovers no more than was stored",
            "heat_recovered_mwh <= heat_stored_mwh and cold_recovered_mwh <= cold_stored_mwh",
            per_case(_ates_not_more),
        ),
        PhysicsCheck(
            "Recovery between 0 and 0.9",
            "0 <= heat_recovery <= 0.9 and 0 <= cold_recovery <= 0.9",
            per_case(_ates_efficiency),
        ),
        PhysicsCheck(
            "Losses not negative",
            "heat_loss_mwh >= 0 and cold_loss_mwh >= 0",
            per_case(_ates_losses),
        ),
        PhysicsCheck(
            "Stored = recovered + lost",
            "recovered + loss = stored within 1 %, and recovery = recovered / stored (0 when "
            "nothing is stored)",
            per_case(_ates_balance),
        ),
        PhysicsCheck(
            "Thermal radius from the stored volume",
            "warm_radius_m and cold_radius_m follow r = sqrt(4.18e6 * v / (2.8e6 * pi * "
            "thickness_m)) within 2 %",
            per_case(_ates_radius),
        ),
        PhysicsCheck(
            "Recovery rises with the stored energy",
            "with the other inputs fixed, heat_recovery never falls as heat_stored_mwh rises",
            rises_with("heat_stored_mwh", "heat_recovery"),
            sweep=True,
        ),
    ],
    cases=[ReferenceCase(_ates_case(h)) for h in (0, 500, 2000)]
    + [
        ReferenceCase(
            _ates_case(5000), {"heat_recovery": (0.6, 0.85), "cold_recovery": (0.6, 0.85)}
        ),
        ReferenceCase(_ates_case(10000)),
        ReferenceCase(_ates_case(20000)),
        ReferenceCase(_ates_case(5000, thickness_m=15.0)),
        ReferenceCase(_ates_case(20000, 20000, thickness_m=100.0)),
        ReferenceCase(_ates_case(10000, 0, 70.0, thickness_m=60.0)),
        ReferenceCase(_ates_case(3000, 3000, 10.0)),
    ],
    sources=[
        "Doughty, Hellström, Tsang and Claesson (1982), Water Resources Research 18(3): "
        "thermal radius and its role in recovery.",
        "Bloemendal and Hartog (2018), Geothermics 71: recovery falls with the surface-to-"
        "volume ratio of the store; LT-ATES in the Netherlands recovers about 0.6-0.9. The "
        "3.8 m conduction length is a half-year estimate, not their fitted correlation.",
    ],
    keywords=[r"\bates\b", r"aquifer (thermal|storage)", r"seasonal storage", r"\bwko\b"],
)

SPECS: Dict[str, ComponentSpec] = {s.name: s for s in (ADSORPTION_CHILLER, ATES)}


def find_spec(text: str) -> Optional[ComponentSpec]:
    """Return the spec of a component named in a request, if any.

    Parameters
    ----------
    text : str
        The user's message, or a component name.

    Returns
    -------
    ComponentSpec or None
        The first spec whose name or keywords appear in the text.
    """
    low = text.lower()
    for spec in SPECS.values():
        names = [rf"\b{spec.name}\b"] + spec.keywords
        if any(re.search(k, low) for k in names):
            return spec
    return None


# ---------------------------------------------------------------------------------------------
# Running the checks


def _outputs_complete(spec: ComponentSpec) -> PhysicsCheck:
    names = [q.name for q in spec.outputs]

    def rule(inp: dict, out: dict) -> Optional[str]:
        missing = [n for n in names if n not in out]
        extra = [k for k in out if k not in names]
        if missing or extra:
            parts = [f"missing {', '.join(missing)}"] if missing else []
            parts += [f"unexpected {', '.join(extra)}"] if extra else []
            return "the dict has " + " and ".join(parts)
        bad = [n for n in names if not math.isfinite(out[n])]
        if bad:
            return f"{', '.join(bad)} is not a finite number"
        return None

    return PhysicsCheck(
        "Returns every output as a finite number",
        f"the dict has exactly the keys {', '.join(names)}, all finite",
        per_case(rule),
    )


def _no_negative(spec: ComponentSpec) -> PhysicsCheck:
    names = [q.name for q in spec.outputs]

    def rule(inp: dict, out: dict) -> Optional[str]:
        negative = [n for n in names if out[n] < -1e-9]
        if negative:
            return f"{', '.join(negative)} is negative ({fmt(out[negative[0]])})"
        return None

    return PhysicsCheck("No negative outputs", "every output is >= 0", per_case(rule))


def _reference_ranges(spec: ComponentSpec) -> Optional[PhysicsCheck]:
    anchored = [c for c in spec.cases if c.expect]
    if not anchored:
        return None

    def test(cases: List[dict], outputs: List[dict]) -> Tuple[bool, str]:
        shown = []
        for inp, out in zip(cases, outputs):
            ref = next((c for c in anchored if c.inputs == inp), None)
            for key, (lo, hi) in (ref.expect if ref else {}).items():
                if not lo - 1e-9 <= out[key] <= hi + 1e-9:
                    return False, (
                        f"at {case_label(inp)}: {key} is {fmt(out[key])}, the literature gives "
                        f"{fmt(lo)} to {fmt(hi)}"
                    )
                shown.append(f"{key} {fmt(out[key])} in {fmt(lo)}-{fmt(hi)}")
        return True, "; ".join(shown) if shown else "no reference case was run"

    return PhysicsCheck(
        "Within the literature ranges",
        "at the reference points the outputs fall in the published ranges",
        test,
        sweep=True,
    )


def all_checks(spec: ComponentSpec, sweeps: bool = True) -> List[PhysicsCheck]:
    """Return the generic checks followed by the spec's own.

    Parameters
    ----------
    spec : ComponentSpec
        The component.
    sweeps : bool
        Include the checks that need the full reference set (sweeps and literature ranges).

    Returns
    -------
    list of PhysicsCheck
        The checks in the order they are reported.
    """
    checks = [_outputs_complete(spec), _no_negative(spec)] + list(spec.checks)
    ranges = _reference_ranges(spec)
    if ranges:
        checks.append(ranges)
    return [c for c in checks if sweeps or not c.sweep]


def run_checks(
    spec: ComponentSpec, cases: List[dict], outputs: List[dict], sweeps: bool = True
) -> List[Check]:
    """Run the physics checks on outputs the sandbox returned.

    A check that cannot run (an output is missing) fails with that reason; when the outputs
    are incomplete only the completeness check is reported, so the model fixes that first.

    Parameters
    ----------
    spec : ComponentSpec
        The component.
    cases : list of dict
        The inputs of each case.
    outputs : list of dict
        The outputs of each case.
    sweeps : bool
        Include sweep and literature-range checks.

    Returns
    -------
    list of Check
        One check per rule, in order.
    """
    out: List[Check] = []
    for check in all_checks(spec, sweeps):
        try:
            passed, detail = check.test(cases, outputs)
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as err:
            passed, detail = False, f"could not run: {type(err).__name__} {err}"
        out.append(Check(name=check.name, passed=bool(passed), detail=detail))
        if not out[0].passed:
            break
    return out
