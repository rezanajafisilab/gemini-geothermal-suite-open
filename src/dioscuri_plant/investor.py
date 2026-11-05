"""The investor's view of a design: heat and cold sold, the SDE++ subsidy, tax and the return.

The plant's cost of heat and of cold (``economics``) is what making the heat costs: capital,
O&M, energy and CO2, with no subsidy, no tax and no sale. That stays the headline, and the
design search ranks on it. This module answers another question: what would a company earn
that builds the plant and runs it for 30 years? It sells the heat and the cold, gets the SDE++
subsidy on its geothermal heat for 15 years, pays corporate tax on its profit and buys the
units that wear out again. Its cash flow after tax gives the investor's NPV, IRR and payback.
Nothing here changes a ranking or a pick.

Kept simple, and said where it is done:

- every year runs like the simulated one (no decline of the wells, no banking of SDE++ hours);
- the SDE++ correction for the gas price is PBL's long-term value, the same every year; its
  CO2 part (ETS2) starts in 2028, the plant's second year (the demand year 2027 is year 1);
- losses are carried forward without the real limit; no EIA (it is not given on parts SDE++
  pays for); what the units bought late are still worth at the end is neither taxed nor
  written off.

Money is in the prices' euros (2025, the cost basis: ``InvestorTerms.price_year``), discounted
at the plant's real rate (``Prices.discount_rate``). The SDE++ and the tax write-offs are fixed
in euros of the day they are paid, so in 2025 euros they shrink with inflation: year 1 is 2027,
two years on from the prices, so its euros of the day are 2025's × 1.02², year t's × 1.02^(t+1)
(the building year 0, 2026: × 1.02). Every default has its source in ``SOURCES``.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from dioscuri_plant.economics import Prices, crf
from dioscuri_plant.types import Economics, Plant, Rules, YearResult

PBL = "PBL, SDE++ 2026 advice (Lensink & Eggink, publication 5698-1, 1 July 2026)"


@dataclass(frozen=True)
class SdeCategory:
    """One SDE++ 2026 category for deep geothermal heat (PBL's advice; the round follows it).

    ``basis_eur_per_kwh`` is the basisbedrag: what a kWh of heat earns with the gas price's
    correction taken off. Subsidy is paid on at most ``full_load_hours`` a year at the
    installation's thermal capacity. Base-load categories (``by_size``) are chosen by that
    capacity: ``min_mw`` up to, not including, ``max_mw``.

    The geothermal-only categories pay for geothermal heat only: the brine's heat, through the
    exchanger and through the heat pump's evaporator, not the heat pump's electricity; their
    installation is the doublets (the brine at the cap flow). The ``with_heat_pump`` categories
    take the heat pump as the installation: its thermal output is the capacity (PBL 2026, p.13
    and pp.137-141), and the subsidised heat is what the geothermal source and heat pump
    deliver, at most that capacity times the full-load hours.
    """

    key: str
    name: str  # the official (Dutch) name
    label: str  # in plain English
    basis_eur_per_kwh: float
    full_load_hours: float
    min_mw: float = 0.0
    max_mw: Optional[float] = None
    ets_eur_per_kwh: float = 0.0  # the CO2-price part of the correction, long term
    ets_from: int = 2026  # the first calendar year with that part
    by_size: bool = False
    source: str = ""
    with_heat_pump: bool = False  # the installation is the heat pump (its thermal output)


# ETS2 (the CO2 price on gas for buildings, from 2028) corrects the base-load categories; the
# others are corrected with ETS1. PBL, Table 4.8 p.53.
ETS2 = dict(ets_eur_per_kwh=0.0114, ets_from=2028)
ETS1 = dict(ets_eur_per_kwh=0.0031, ets_from=2026)
CATEGORIES: Tuple[SdeCategory, ...] = (
    SdeCategory(
        "base_lt12",
        "Diepe geothermie <12 MWth (basislast)",
        "Deep geothermal, base load, under 12 MW",
        0.0799,
        6000,
        0.0,
        12.0,
        by_size=True,
        source=f"{PBL}, Table 11.7a p.136",
        **ETS2,
    ),
    SdeCategory(
        "base_12_20",
        "Diepe geothermie 12-20 MWth (basislast)",
        "Deep geothermal, base load, 12 to 20 MW",
        0.0696,
        6000,
        12.0,
        20.0,
        by_size=True,
        source=f"{PBL}, Table 11.7b p.136",
        **ETS2,
    ),
    SdeCategory(
        "base_ge20",
        "Diepe geothermie ≥20 MWth (basislast)",
        "Deep geothermal, base load, 20 MW or more",
        0.0627,
        6000,
        20.0,
        None,
        by_size=True,
        source=f"{PBL}, Table 11.7c p.136",
        **ETS2,
    ),
    SdeCategory(
        "mid_load",
        "Diepe geothermie (middenlast)",
        "Deep geothermal, mid load (70-75 °C network, no heat pump)",
        0.0997,
        5000,
        source=f"{PBL}, Table 11.9 p.139",
        **ETS1,
    ),
    SdeCategory(
        "peak_lt12",
        "Diepe geothermie <12 MWth (geen basislast)",
        "Deep geothermal, not base load, under 12 MW",
        0.1850,
        3500,
        0.0,
        12.0,
        source=f"{PBL}, Table 11.10a p.140",
        **ETS1,
    ),
    SdeCategory(
        "peak_ge12",
        "Diepe geothermie ≥12 MWth (geen basislast)",
        "Deep geothermal, not base load, 12 MW or more",
        0.1647,
        3500,
        12.0,
        None,
        source=f"{PBL}, Table 11.10b p.140",
        **ETS1,
    ),
    SdeCategory(
        "ht_hp_lt12",
        "Diepe geothermie <12 MWth basislast, HT-net met warmtepomp",
        "Deep geothermal, base load, high-temperature network with heat pump, under 12 MW",
        0.1476,
        6000,
        0.0,
        12.0,
        source=f"{PBL}, Table 11.8a p.138; installation = the heat pump's output, p.13",
        with_heat_pump=True,
        **ETS1,
    ),
    SdeCategory(
        "ht_hp_ge12",
        "Diepe geothermie ≥12 MWth basislast, HT-net met warmtepomp",
        "Deep geothermal, base load, high-temperature network with heat pump, 12 MW or more",
        0.1325,
        6000,
        12.0,
        None,
        source=f"{PBL}, Table 11.8b p.138; installation = the heat pump's output, p.13",
        with_heat_pump=True,
        **ETS1,
    ),
)
BY_KEY: Dict[str, SdeCategory] = {c.key: c for c in CATEGORIES}
MIN_HEAT_PUMP_MW = 0.5  # the 'with heat pump' categories' smallest heat pump (PBL 2026, p.13)


@dataclass(frozen=True)
class InvestorTerms:
    """What the investor's case assumes. Defaults are sourced in ``SOURCES``; all can change.

    A sale price of ``None`` is the gas reference's cost of heat (or of cold): what the buyer
    would pay for its own gas boilers and electric chillers. ``sde_category`` is ``"auto"``
    (the base-load category for the plant's capacity) or a key of ``BY_KEY``.
    ``brine_cooling_k`` of ``None`` takes the design's own brine cooling, at most the cap.
    """

    heat_sale_eur_per_mwh: Optional[float] = None
    cold_sale_eur_per_mwh: Optional[float] = None
    sde_on: bool = True
    sde_category: str = "auto"
    sde_basis_eur_per_kwh: Optional[float] = None  # a lower bid than the category's basisbedrag
    sde_years: int = 15
    ttf_eur_per_kwh: float = 0.0280  # long-term TTF gas price, lower heating value
    correction_share: float = 0.70  # the correction is this share of the TTF price
    correction_floor_eur_per_kwh: float = 0.0131
    brine_cooling_k: Optional[float] = None
    tax_rate: float = 0.258
    tax_rate_low: float = 0.19
    tax_band_meur: float = 0.2  # profit taxed at the low rate each year
    depreciation_years: int = 15
    inflation: float = 0.02
    first_year: int = 2027  # the plant's first year: the demand year
    price_year: int = 2025  # the year of the prices' and costs' euros (``economics.Prices``)


SOURCES: Dict[str, str] = {
    "heat_sale_eur_per_mwh": (
        "The gas reference's cost of heat (gas boilers for the same demand, same prices): "
        "the 'niet meer dan anders' rule of Dutch heat tariffs (ACM, maximum heat tariffs "
        "2026; Warmtewet); ACM's 2026 retail ceiling is 40.97 €/GJ incl. VAT, about "
        "122 €/MWh excl. VAT"
    ),
    "cold_sale_eur_per_mwh": (
        "The gas reference's cost of cold (electric chillers for the same demand, same "
        "prices); ACM sets no variable cold tariff (only a fixed 300.01 €/yr)"
    ),
    "sde_on": "RVO, SDE++ 2026 round (27 Oct-26 Nov 2026, budget 8 bn€); Kamerbrief 13 Feb 2026",
    "sde_category": (
        f"{PBL}, Tables 11.7-11.11 pp.136-141: deep geothermal 1,500-4,000 m (Tekstkader 11.1)"
    ),
    "sde_basis_eur_per_kwh": "RVO, SDE++: an applicant may ask less than the basisbedrag",
    "sde_years": f"{PBL}, p.126: 15 years of subsidy (a doublet lasts 30)",
    "ttf_eur_per_kwh": f"{PBL}, Table 4.7 p.52: long-term TTF (LHV) 0.0280 €/kWh (KEV 2025)",
    "correction_share": f"{PBL}, Table 4.7 p.52: geothermal heat corrected at 70 % of TTF",
    "correction_floor_eur_per_kwh": (
        f"{PBL}, p.20 and Table 4.7: the floor (basisprijs), two thirds of the long-term price"
    ),
    "ets": f"{PBL}, Table 4.8 p.53: ETS2 0.0114 €/kWh from 2028 (base load); ETS1 0.0031",
    "brine_cooling_k": "The design's year (``YearResult.max_brine_cooling_k``), at most the cap",
    "tax_rate": "Belastingdienst, corporate tax (Vpb) 2026: 25.8 % above 200,000 €",
    "tax_rate_low": "Belastingdienst, corporate tax (Vpb) 2026: 19 % up to 200,000 €",
    "tax_band_meur": "Belastingdienst, corporate tax (Vpb) 2026: the first 200,000 € of profit",
    "depreciation_years": f"{PBL}, p.65: fiscal depreciation over 15 years",
    "inflation": f"{PBL}, Table 6.1 p.58: long-term inflation 2.0 %",
    "first_year": "The organisers' demand files (2027)",
    "price_year": "The cost basis: every price and cost in 2025 euros (``economics.Prices``)",
    "discount_rate": f"{PBL}, Table 6.3 p.65: geothermal WACC 5.2 % real after tax",
    "eia": "RVO, Energielijst 2026 p.6: no EIA on parts an SDE++ grant pays for",
}

# What a conversation may change (``PUT /api/assumptions``): label, unit.
OVERRIDES: Dict[str, Tuple[str, str]] = {
    "heat_sale_eur_per_mwh": ("Heat sale price", "€/MWh"),
    "cold_sale_eur_per_mwh": ("Cold sale price", "€/MWh"),
    "sde_category": ("SDE++ category", ""),
    "sde_on": ("SDE++ subsidy", ""),
}


@dataclass
class InvestorCase:
    """A design as an investment: what it sells, the subsidy, tax, cash flow and its return.

    Money is in M€ of the prices' euros (2025, real), a year unless said; ``flows`` has one row
    per year from 0 (building) to ``years``. ``sde`` and ``tax`` say how those were worked out.
    """

    years: int
    discount_rate: float
    inflation: float
    heat_sale_eur_per_mwh: float
    cold_sale_eur_per_mwh: float
    sale_basis: Dict[str, str]  # "heat"/"cold" -> "gas reference" or "yours"
    heat_sold_gwh: float
    cold_sold_gwh: float
    revenue_heat_meur: float
    revenue_cold_meur: float
    opex_meur: float
    capex_meur: float
    reinvest_meur: float  # units bought again in later years, 2025 euros, not discounted
    value_left_meur: float  # what units bought late are still worth at the end
    sde: Dict[str, object]
    tax: Dict[str, object]
    flows: List[Dict[str, float]]
    npv_meur: float
    irr: Optional[float]
    payback_years: Optional[float]  # discounted; None when it never pays back
    without_sde: Dict[str, Optional[float]]
    break_even_basis_eur_per_kwh: Optional[float]
    needs_subsidy: bool
    notes: List[str] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)


# ------------------------------------------------------------------ pieces


def thermal_capacity(
    plant: Plant, rules: Rules, year: Optional[YearResult] = None, brine_cooling_k=None
) -> Tuple[float, float, float]:
    """Return the plant's geothermal thermal capacity, MW, with the cooling and flow it uses.

    The capacity is the brine's heat at every doublet's flow cap, cooled by the design's own
    brine cooling (``year.max_brine_cooling_k``) or ``brine_cooling_k``, never past the cap.

    Parameters
    ----------
    plant : Plant
        The design (its doublets and their flow caps).
    rules : Rules
        The flow and cooling caps and the brine's properties.
    year : YearResult, optional
        The design's year, for its brine cooling.
    brine_cooling_k : float, optional
        A cooling to use in place of the year's.

    Returns
    -------
    tuple of float
        Capacity (MW), brine cooling (K) and flow (m3/h, all doublets).
    """
    if plant.n_doublets == 0:
        return 0.0, 0.0, 0.0
    flow = float(sum(d.cap_m3h(rules) for d in plant.specs()))
    own = brine_cooling_k
    if own is None:
        own = float(getattr(year, "max_brine_cooling_k", 0.0) or 0.0) if year else 0.0
    cooling = min(own, rules.max_brine_cooling_k) if own > 0 else rules.max_brine_cooling_k
    return float(rules.brine_mw_per_k(flow)) * cooling, cooling, flow


def installation_mw(plant: Plant, category: SdeCategory, geothermal_mw: float) -> float:
    """Return the installation's capacity SDE++ counts for a category, MW.

    The heat pump's thermal output for the ``with_heat_pump`` categories (PBL 2026, p.13 and
    pp.137-141); the geothermal capacity (``thermal_capacity``) for the others.
    """
    return float(plant.heat_pump_mw) if category.with_heat_pump else geothermal_mw


def category_for(capacity_mw: float, key: str = "auto") -> SdeCategory:
    """Return the SDE++ category: the one named, or the base-load one for this capacity."""
    if key != "auto":
        if key not in BY_KEY:
            raise ValueError(f"unknown SDE++ category {key!r}")
        return BY_KEY[key]
    for c in CATEGORIES:
        if c.by_size and c.min_mw <= capacity_mw and (c.max_mw is None or capacity_mw < c.max_mw):
            return c
    return CATEGORIES[0]


def fits(category: SdeCategory, capacity_mw: float) -> bool:
    """Return True when the capacity is inside the category's size range."""
    return category.min_mw <= capacity_mw and (
        category.max_mw is None or capacity_mw < category.max_mw
    )


def gas_correction_eur_per_kwh(terms: InvestorTerms = InvestorTerms()) -> float:
    """Return the gas-price part of the correction: a share of the TTF price, at least the floor."""
    return max(terms.correction_share * terms.ttf_eur_per_kwh, terms.correction_floor_eur_per_kwh)


def correction_eur_per_kwh(
    category: SdeCategory, plant_year: int, terms: InvestorTerms = InvestorTerms()
) -> float:
    """Return the correction taken off the basisbedrag in a year of the plant (1, 2 ...).

    The gas part (``gas_correction_eur_per_kwh``) and, from the calendar year its emissions
    trading starts, the CO2 part.
    """
    gas = gas_correction_eur_per_kwh(terms)
    calendar = terms.first_year + plant_year - 1
    return gas + (category.ets_eur_per_kwh if calendar >= category.ets_from else 0.0)


def subsidy_eur_per_kwh(
    category: SdeCategory,
    plant_year: int,
    terms: InvestorTerms = InvestorTerms(),
    basis_eur_per_kwh: Optional[float] = None,
) -> float:
    """Return the SDE++ paid per kWh in a year of the plant: basisbedrag less the correction.

    The basisbedrag is ``basis_eur_per_kwh`` when given, else the terms' bid, else the
    category's.
    """
    basis = basis_eur_per_kwh
    if basis is None:
        basis = terms.sde_basis_eur_per_kwh
    if basis is None:
        basis = category.basis_eur_per_kwh
    return max(basis - correction_eur_per_kwh(category, plant_year, terms), 0.0)


def corporate_tax(profit_meur: float, terms: InvestorTerms = InvestorTerms()) -> float:
    """Return a year's corporate tax on a profit, M€: the low rate on the first band."""
    if profit_meur <= 0:
        return 0.0
    low = min(profit_meur, terms.tax_band_meur)
    return low * terms.tax_rate_low + (profit_meur - low) * terms.tax_rate


def taxes(profits_meur: Sequence[float], terms: InvestorTerms = InvestorTerms()) -> List[float]:
    """Return each year's tax, with every loss carried forward to the next profits (no limit)."""
    out: List[float] = []
    losses = 0.0
    for p in profits_meur:
        if p < 0:
            losses -= p
            out.append(0.0)
            continue
        used = min(losses, p)
        losses -= used
        out.append(corporate_tax(p - used, terms))
    return out


def annuity_factor(rate: float, years: float) -> float:
    """Return what a euro a year for ``years`` years is worth today."""
    if years <= 0:
        return 0.0
    return years if rate == 0 else (1 - (1 + rate) ** -years) / rate


def capital_flows(
    items: Sequence[Dict[str, object]], years: int, rate: float
) -> Tuple[List[float], float, List[Tuple[int, float]]]:
    """Return the capital spent each year (years 0 to ``years``), the value left, the purchases.

    Each capital item (``Economics.capex_items``: ``meur`` and ``life_years``) is bought at
    year 0 and again each time it wears out before the end. What the last one is still worth at
    the end is the rest of its annuity (``economics.crf`` over its life), so the capital's
    present value equals the annuities the plant's cost of heat charges over the same years.

    Returns
    -------
    tuple
        Spend per year (M€, today's), the value left at the end (M€) and (year, M€) per purchase.
    """
    spend = [0.0] * (years + 1)
    buys: List[Tuple[int, float]] = []
    left = 0.0
    for it in items:
        cost = float(it.get("meur", 0.0) or 0.0)
        life = max(int(it.get("life_years") or years), 1)
        if cost <= 0:
            continue
        last = 0
        for k in range(0, years, life):
            spend[k] += cost
            buys.append((k, cost))
            last = k
        rest = last + life - years
        left += cost * crf(rate, life) * annuity_factor(rate, rest)
    return spend, left, buys


def npv(flows: Sequence[float], rate: float) -> float:
    """Return the net present value of yearly flows (year 0 first)."""
    return sum(f / (1 + rate) ** t for t, f in enumerate(flows))


def irr(flows: Sequence[float]) -> Optional[float]:
    """Return the rate at which the flows' NPV is zero, or None when no rate in -90 %..1000 %."""
    lo, hi = -0.9, 10.0
    f_lo, f_hi = npv(flows, lo), npv(flows, hi)
    if f_lo == 0:
        return lo
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(flows, mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


def discounted_payback(flows: Sequence[float], rate: float) -> Optional[float]:
    """Return the years until the discounted flows first add up to zero (to a tenth), or None."""
    total = 0.0
    for t, f in enumerate(flows):
        d = f / (1 + rate) ** t
        if total + d >= 0 and (t == 0 or total < 0):
            return 0.0 if t == 0 else round(t - 1 + (-total) / d, 1)
        total += d
    return None


# ------------------------------------------------------------------ the case


def _sold_gwh(year: YearResult) -> Tuple[float, float]:
    """Return the heat reaching the buildings (after the network's losses) and the cold, GWh."""
    lost = float(((year.network or {}).get("heat_loss_gwh", 0.0)) or 0.0)
    return max(year.heat_delivered_gwh - lost, 0.0), year.cool_delivered_gwh


def _eligible_gwh(year: YearResult, category: Optional[SdeCategory] = None) -> float:
    """Return the heat SDE++ pays for, GWh, before the cap.

    Geothermal-only categories: geothermal heat only, the exchanger's heat and the heat the
    heat pump takes from the brine (its output less its electricity). The ``with_heat_pump``
    categories: what the geothermal source and the heat pump deliver (the heat pump's output
    with its electricity), capped by the heat pump's capacity in ``investor_case``.
    """
    split = year.heat_split_gwh or {}
    geo = float(split.get("geo", 0.0) or 0.0)
    hp = float(split.get("hp", 0.0) or 0.0)
    if category is not None and category.with_heat_pump:
        return geo + hp
    power = getattr(year, "electricity_gwh", None) or {}
    hp_el = float(power.get("hp", 0.0) or 0.0)
    return geo + max(hp - hp_el, 0.0)


def investor_case(
    plant: Plant,
    year: YearResult,
    econ: Economics,
    rules: Rules,
    prices: Prices,
    reference: Economics,
    terms: InvestorTerms = InvestorTerms(),
) -> InvestorCase:
    """Return a design as an investment: sales, SDE++, tax, the cash flow and its return.

    Parameters
    ----------
    plant : Plant
        The design.
    year : YearResult
        Its year (``simulate_year``, or the agent's copy with the same fields).
    econ : Economics
        Its costs (``economics``): the yearly running costs and the capital items.
    rules : Rules
        The flow and cooling caps, for the plant's thermal capacity.
    prices : Prices
        The discount rate (real) and the wells' life (the years of the case).
    reference : Economics
        The gas reference's costs at the same prices: its cost of heat and of cold are the
        default sale prices.
    terms : InvestorTerms
        Sale prices, the SDE++ terms, tax and inflation.

    Returns
    -------
    InvestorCase
        The yearly sales, subsidy, tax and cash flow, and the NPV, IRR and payback after tax.
    """
    n, r, i = int(prices.wells_life_years), prices.discount_rate, terms.inflation
    heat_gwh, cold_gwh = _sold_gwh(year)
    ref_cold = reference.lcoc_eur_per_mwh or 0.0
    heat_price = (
        reference.lcoh_eur_per_mwh
        if terms.heat_sale_eur_per_mwh is None
        else terms.heat_sale_eur_per_mwh
    )
    cold_price = ref_cold if terms.cold_sale_eur_per_mwh is None else terms.cold_sale_eur_per_mwh
    rev_heat = heat_gwh * heat_price / 1000
    rev_cold = cold_gwh * cold_price / 1000
    opex = float(econ.opex_meur_per_year or 0.0)
    spend, left, buys = capital_flows(econ.capex_items or [], n, r)

    # SDE++: the category, the heat it pays for and the cap on it.
    capacity, cooling, flow = thermal_capacity(plant, rules, year, terms.brine_cooling_k)
    cat = category_for(capacity, terms.sde_category)
    size = installation_mw(plant, cat, capacity) if plant.n_doublets else 0.0
    eligible = _eligible_gwh(year, cat) if plant.n_doublets else 0.0
    cap_gwh = size * cat.full_load_hours / 1000
    subsidised = min(eligible, cap_gwh)
    sde_years = min(terms.sde_years, n)

    # Year t is calendar year first_year + t - 1; its euros of the day are the prices' euros
    # (price_year) grown by inflation over the years between: (1 + i) ** (t + shift).
    shift = terms.first_year - 1 - terms.price_year

    def of_the_day(t: int) -> float:
        return (1 + i) ** (t + shift)

    # Write-offs in euros of the day: each purchase over ``depreciation_years`` from the next year.
    write_off = [0.0] * (n + 1)
    for k, cost in buys:
        paid = cost * of_the_day(k)
        for t in range(k + 1, min(k + terms.depreciation_years, n) + 1):
            write_off[t] += paid / terms.depreciation_years

    def run(on: bool, basis: Optional[float] = None):
        """Return the rows (M€ of 2025) and the net flows for SDE++ on or off at a basisbedrag."""
        sde_day = [0.0] * (n + 1)  # euros of the day
        if on:
            for t in range(1, sde_years + 1):
                sde_day[t] = subsidised * subsidy_eur_per_kwh(cat, t, terms, basis)
        profit = [0.0] + [
            (rev_heat + rev_cold - opex) * of_the_day(t) + sde_day[t] - write_off[t]
            for t in range(1, n + 1)
        ]
        tax_day = taxes(profit, terms)
        rows, net, total = [], [], 0.0
        for t in range(n + 1):
            today = 1 / of_the_day(t)  # euros of the day to the prices' (2025) euros
            ops = t > 0
            row = {
                "year": t,
                "revenue_heat": rev_heat if ops else 0.0,
                "revenue_cold": rev_cold if ops else 0.0,
                "sde": sde_day[t] * today,
                "opex": -opex if ops else 0.0,
                "capital": -spend[t],
                "value_left": left if t == n else 0.0,
                "tax": -tax_day[t] * today,
            }
            row["net"] = sum(v for k, v in row.items() if k != "year")
            total += row["net"] / (1 + r) ** t
            row["cumulative"] = total
            rows.append(row)
            net.append(row["net"])
        return rows, net

    rows, net = run(terms.sde_on)
    _, bare = run(False)
    value, value_bare = npv(net, r), npv(bare, r)

    # The basisbedrag at which the investor just breaks even (None: needs none, or no heat).
    break_even = None
    if value_bare < 0 and subsidised > 0:
        lo, hi = 0.0, 2.0
        if npv(run(True, hi)[1], r) >= 0:
            for _ in range(60):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if npv(run(True, mid)[1], r) < 0 else (lo, mid)
            break_even = round(hi, 4)

    sde_today = [row["sde"] for row in rows]
    per_kwh = [subsidy_eur_per_kwh(cat, t, terms) for t in range(1, sde_years + 1)]
    ets_year = max(cat.ets_from - terms.first_year + 1, 1)
    sde = {
        "on": terms.sde_on,
        "category": asdict(cat),
        "chosen_by": "size" if terms.sde_category == "auto" else "you",
        "fits": fits(cat, size) and (not cat.with_heat_pump or size >= MIN_HEAT_PUMP_MW),
        "capacity_mw": round(capacity, 2),
        "installation_mw": round(size, 2),  # what the category counts: the heat pump or brine
        "installation": "heat pump" if cat.with_heat_pump else "geothermal",
        "heat_pump_electricity_gwh": round(
            float((getattr(year, "electricity_gwh", None) or {}).get("hp", 0.0) or 0.0), 3
        ),
        "flow_m3h": round(flow, 1),
        "brine_cooling_k": round(cooling, 2),
        "eligible_gwh": round(eligible, 3),
        "cap_gwh": round(cap_gwh, 3),
        "subsidised_gwh": round(subsidised, 3),
        "capped": eligible > cap_gwh + 1e-9,
        "basis_eur_per_kwh": (
            cat.basis_eur_per_kwh
            if terms.sde_basis_eur_per_kwh is None
            else terms.sde_basis_eur_per_kwh
        ),
        "correction_eur_per_kwh": round(gas_correction_eur_per_kwh(terms), 4),  # gas part
        "floor_eur_per_kwh": terms.correction_floor_eur_per_kwh,
        "ets_eur_per_kwh": cat.ets_eur_per_kwh,
        "ets_from_year": ets_year,
        "per_kwh_first": round(per_kwh[0], 4) if per_kwh else 0.0,
        "per_kwh_later": round(per_kwh[-1], 4) if per_kwh else 0.0,
        "first_year": 1,
        "last_year": sde_years,
        "calendar_years": [terms.first_year, terms.first_year + sde_years - 1],
        "meur_first_year": round(sde_today[1], 3) if n >= 1 else 0.0,
        "meur_average": round(sum(sde_today) / sde_years, 3) if sde_years else 0.0,
        "total_meur": round(sum(sde_today), 3),
    }
    tax_today = [-row["tax"] for row in rows]
    tax = {
        "rate": terms.tax_rate,
        "rate_low": terms.tax_rate_low,
        "band_meur": terms.tax_band_meur,
        "depreciation_years": terms.depreciation_years,
        "total_meur": round(sum(tax_today), 3),
        "first_tax_year": next((t for t, x in enumerate(tax_today) if x > 1e-9), None),
    }
    case = InvestorCase(
        years=n,
        discount_rate=r,
        inflation=i,
        heat_sale_eur_per_mwh=round(heat_price, 2),
        cold_sale_eur_per_mwh=round(cold_price, 2),
        sale_basis={
            "heat": "gas reference" if terms.heat_sale_eur_per_mwh is None else "yours",
            "cold": "gas reference" if terms.cold_sale_eur_per_mwh is None else "yours",
        },
        heat_sold_gwh=round(heat_gwh, 3),
        cold_sold_gwh=round(cold_gwh, 3),
        revenue_heat_meur=round(rev_heat, 3),
        revenue_cold_meur=round(rev_cold, 3),
        opex_meur=round(opex, 3),
        capex_meur=round(spend[0], 3),
        reinvest_meur=round(sum(spend[1:]), 3),
        value_left_meur=round(left, 3),
        sde=sde,
        tax=tax,
        # (+ 0.0 writes a rounded -0.0 as 0.0)
        flows=[
            {k: (v if k == "year" else round(v, 3) + 0.0) for k, v in row.items()} for row in rows
        ],
        npv_meur=round(value, 2),
        irr=irr(net),
        payback_years=discounted_payback(net, r),
        without_sde={
            "npv_meur": round(value_bare, 2),
            "irr": irr(bare),
            "payback_years": discounted_payback(bare, r),
        },
        break_even_basis_eur_per_kwh=break_even,
        needs_subsidy=value_bare < 0,
    )
    case.notes = notes(case, terms)
    case.sources = dict(SOURCES)
    return case


def notes(case: InvestorCase, terms: InvestorTerms = InvestorTerms()) -> List[str]:
    """Return what the case assumes, in plain words, with the numbers it used."""
    s, cat = case.sde, case.sde["category"]
    pct = _pct
    out = [
        "The plant's cost of heat has no subsidy, no tax and no sale. This is a company's view: "
        "it sells the heat and cold, gets SDE++ on its geothermal heat and pays corporate tax.",
        f"Heat is sold at {_num(case.heat_sale_eur_per_mwh)} €/MWh and cold at "
        f"{_num(case.cold_sale_eur_per_mwh)} €/MWh"
        + (
            ": what the buyer's own gas boilers and electric chillers would cost (the 'no more "
            "than otherwise' rule of Dutch heat tariffs)."
            if set(case.sale_basis.values()) == {"gas reference"}
            else " (prices you set; the default is what the gas plant would cost the buyer)."
        ),
        f"SDE++ category '{cat['name']}' ({_num(cat['basis_eur_per_kwh'] * 1000)} €/MWh), "
        + (
            f"chosen by the plant's geothermal capacity: {_num(s['capacity_mw'])} MW "
            f"({_num(s['flow_m3h'], 0)} m³/h of brine cooled {_num(s['brine_cooling_k'])} K)."
            if s["chosen_by"] == "size"
            else (
                f"chosen by you; the installation is the heat pump, {_num(s['installation_mw'])}"
                " MW of heat (PBL counts the heat pump's thermal output)"
                if s["installation"] == "heat pump"
                else f"chosen by you; the plant's geothermal capacity is "
                f"{_num(s['capacity_mw'])} MW"
            )
            + ("." if s["fits"] else ", outside this category's size range.")
        ),
        (
            f"Subsidised: up to {_num(s['eligible_gwh'])} GWh a year of the geothermal source "
            "and heat pump's heat, at most the heat pump's "
            f"{_num(s['installation_mw'])} MW × {_num(cat['full_load_hours'], 0)} h."
            if s["installation"] == "heat pump"
            else f"Only geothermal heat earns SDE++: {_num(s['eligible_gwh'])} GWh a year, the "
            "exchanger's heat and the heat the heat pump takes from the brine; the heat pump's "
            f"electricity ({_num(s['heat_pump_electricity_gwh'])} GWh) and the boilers' heat "
            "earn none."
        ),
        "The 'high-temperature network with heat pump' categories assume the heat pump lifts "
        "all the geothermal heat, and count the heat pump's thermal output as the installation "
        "(at most that × 6,000 h is subsidised); here the heat pump only tops up after a heat "
        "exchanger, so they are not used unless you pick one.",
        f"SDE++ pays the basisbedrag less a gas-price correction ({pct(terms.correction_share)} "
        f"of the TTF gas price, {_num(s['correction_eur_per_kwh'] * 1000)} €/MWh, at least "
        f"{_num(s['floor_eur_per_kwh'] * 1000)} €/MWh), for {s['last_year']} years, on at most "
        f"{_num(cat['full_load_hours'], 0)} full-load hours a year. The CO₂ part of the "
        f"correction ({_num(s['ets_eur_per_kwh'] * 1000)} €/MWh) is added from year "
        f"{s['ets_from_year']}"
        + (" (2028, when ETS2 starts)." if cat["ets_from"] == 2028 else ".")
        + " Cooling earns no SDE++.",
        f"Corporate tax {pct(terms.tax_rate)} ({pct(terms.tax_rate_low)} on the first "
        f"{_num(terms.tax_band_meur)} M€ of profit a year); the plant is written off in equal "
        f"parts over {terms.depreciation_years} years; losses are carried forward without the "
        "real limit. No EIA: it is not given on parts SDE++ pays for.",
        f"All money in {terms.price_year} euros (the prices' year), discounted at "
        f"{pct(case.discount_rate)} real (PBL's geothermal WACC, after tax) over {case.years} "
        "years. SDE++ and the tax write-offs are fixed in euros of the day, so they shrink "
        f"{pct(case.inflation)} a year in {terms.price_year} euros, from {terms.price_year}: "
        f"year 1 is {terms.first_year}.",
        "Units with shorter lives are bought again when they wear out; what they are still "
        "worth at the end counts back (neither taxed nor written off). Every year runs like "
        "the simulated one; the heat network is not in the plant, so not in this case.",
    ]
    if s["capped"]:
        out.append(
            f"SDE++ is capped: {_num(s['eligible_gwh'])} GWh of eligible heat, of which "
            f"{_num(s['subsidised_gwh'])} GWh earns subsidy ({_num(s['installation_mw'])} MW × "
            f"{_num(cat['full_load_hours'], 0)} h)."
        )
    if terms.sde_basis_eur_per_kwh is not None:
        out.append(
            f"The subsidy uses a basisbedrag of {_num(s['basis_eur_per_kwh'] * 1000)} €/MWh in "
            "place of the category's (an application may ask for less)."
        )
    if not s["on"]:
        out.append("SDE++ is switched off: the figures are without any subsidy.")
    return out


def _num(x: float, digits: int = 1) -> str:
    """Return a number with at most ``digits`` decimals and thousands separators."""
    text = f"{float(x):,.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _pct(x: float) -> str:
    """Return a fraction as a percentage: 0.258 -> "25.8 %"."""
    return f"{_num(x * 100)} %"


# ------------------------------------------------------------------ the conversation's choices


def override(key: str, value: object) -> object:
    """Return a user's value for one of ``OVERRIDES``, checked; raise ``ValueError`` if wrong."""
    if key in ("heat_sale_eur_per_mwh", "cold_sale_eur_per_mwh"):
        if isinstance(value, bool):
            raise ValueError(f"{key} is a price in €/MWh")
        try:
            price = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(f"{key} is a price in €/MWh") from None
        if not math.isfinite(price) or not 0 <= price <= 2000:
            raise ValueError(f"{key} must be 0 to 2,000 €/MWh")
        return price
    if key == "sde_category":
        text = str(value)
        if text != "auto" and text not in BY_KEY:
            raise ValueError(f"sde_category is 'auto' or one of {sorted(BY_KEY)}")
        return text
    if key == "sde_on":
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        if str(value).strip().lower() in ("true", "false", "on", "off"):
            return str(value).strip().lower() in ("true", "on")
        raise ValueError("sde_on is true or false")
    raise ValueError(f"unknown investor assumption {key!r}")


def terms_from(assumptions: Optional[dict], base: InvestorTerms = InvestorTerms()) -> InvestorTerms:
    """Return the terms with a conversation's changes (keys of ``OVERRIDES``; others ignored)."""
    changes = {
        k: override(k, v)
        for k, v in (assumptions or {}).items()
        if k in OVERRIDES and v is not None
    }
    return replace(base, **changes)


def view(case: InvestorCase, terms: InvestorTerms, reference: Economics) -> Dict[str, object]:
    """Return the case for the app: its figures, what can be changed and the category choices."""

    def item(key, value, default, kind="number", options=None):
        label, unit = OVERRIDES[key]
        out = {
            "key": key,
            "label": label,
            "unit": unit,
            "value": value,
            "default": default,
            "changed": getattr(terms, key) != getattr(InvestorTerms(), key),
            "kind": kind,
            "source": SOURCES.get(key, ""),
        }
        if options is not None:
            out["options"] = options
        return out

    options = [{"key": "auto", "label": "By the plant's capacity (base load)"}] + [
        {
            "key": c.key,
            "label": c.label,
            "name": c.name,
            "basis_eur_per_kwh": c.basis_eur_per_kwh,
            "full_load_hours": c.full_load_hours,
        }
        for c in CATEGORIES
    ]
    return dict(
        asdict(case),
        inputs=[
            item(
                "heat_sale_eur_per_mwh",
                case.heat_sale_eur_per_mwh,
                round(reference.lcoh_eur_per_mwh, 2),
            ),
            item(
                "cold_sale_eur_per_mwh",
                case.cold_sale_eur_per_mwh,
                round(reference.lcoc_eur_per_mwh or 0.0, 2),
            ),
            item("sde_category", terms.sde_category, "auto", "choice", options),
            item("sde_on", terms.sde_on, True, "switch"),
        ],
    )
