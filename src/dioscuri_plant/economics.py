"""Costs of a design: capital, running costs, the levelised cost of heat and of cold, CO2.

Every price and cost is a field of ``Prices`` with its source in ``SOURCES`` (full references in
``hackathon/docs/challenge/cost_sources.md``). Capital is annualised with each unit's own
lifetime at one real discount rate (PBL's for geothermal). Costs shared by heat and cold (the
wells, the surface plant, the pumps, the produced gas) are split by the brine heat each side
uses: heating takes the exchanger's and the heat pump's source heat, cooling the absorption
chiller's driving heat. The electricity's CO2 is not priced again: generators pay it under the
EU ETS, inside the electricity price.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from dioscuri_plant.components import LHV_CH4_MJ_PER_NM3, Components
from dioscuri_plant.types import Economics, Plant, Rules, YearResult

SOURCE = "dioscuri_plant 0.1"


@dataclass(frozen=True)
class Prices:
    """Prices, unit costs and financial conventions (2025 euros; sources in ``SOURCES``)."""

    # Real; PBL's after-tax WACC for geothermal. Corporate tax is not in the cost of heat (the
    # investor's case, ``investor``, adds it).
    discount_rate: float = 0.052
    electricity_eur_per_mwh: float = 185.7
    gas_eur_per_mwh: float = 69.4  # net calorific value
    carbon_eur_per_t: float = 73.9
    # CO2 at the long-term price, for the "best overall" pick (not in the cost of heat).
    carbon_long_term_eur_per_t: float = 137.0
    # Wells: ThermoGIS v3, per well, along-hole length L = curvature x sqrt(TVD^2 + (spacing/2)^2).
    well_scale: float = 1.96
    well_base_eur: float = 790_000.0
    well_per_m_eur: float = 555.0
    well_per_m2_eur: float = 0.05
    well_spacing_m: float = 1500.0
    well_curvature: float = 1.1
    # Surface plant per doublet (separator, filters, exchangers, pumps, civils, connection).
    surface_per_doublet_meur: float = 3.5
    # Of which the treatment train (degassing separator and filters), for one doublet's brine;
    # doublets that share a train pay one larger train (six-tenths rule) instead of one each.
    treatment_train_meur: float = 0.6
    treatment_scale_exponent: float = 0.6
    surface_meur_per_mw: float = 0.882
    heat_pump_meur_per_mw: float = 1.2
    boiler_meur_per_mw: float = 0.075
    # Electric boiler with its grid connection upgrade (PBL: 259 + 55 + 92 €/kW).
    electric_boiler_meur_per_mw: float = 0.407
    absorption_meur_per_mw: float = 0.89  # with its cooling tower
    chiller_meur_per_mw: float = 0.245  # with its cooling tower
    # Running costs.
    geothermal_fixed_eur_per_kw: float = 121.0  # per kW of brine heat, per year
    geothermal_variable_eur_per_mwh: float = 0.62  # per MWh of brine heat
    heat_pump_fixed_eur_per_mw: float = 3200.0
    heat_pump_variable_eur_per_mwh: float = 2.5
    boiler_fixed_eur_per_mw: float = 2420.0
    boiler_variable_eur_per_mwh: float = 1.37
    electric_boiler_fixed_eur_per_kw: float = 7.8  # maintenance, per kW a year
    # The grid's capacity charge for its connection, per kW a year: an electric boiler large
    # enough to carry the peak pays for that connection all year, run or not.
    electric_boiler_grid_eur_per_kw: float = 123.0
    # A unit that runs at most 600 hours a year at its peak (a backup, a peak unit) may take
    # the grid's 600-hour contract instead: less per kW contracted, plus each week's peak.
    electric_boiler_grid_600h_eur_per_kw: float = 23.94
    electric_boiler_grid_600h_week_eur_per_kw: float = 2.16
    electric_boiler_variable_eur_per_mwh: float = 0.84
    # The brine's gas sold (``Plant.gas == "sell"``): its methane at the wholesale price, less
    # cleaning it to grid quality, compressing and injecting it (per Nm3 of raw gas, all in).
    gas_sale_eur_per_mwh: float = 39.0
    gas_cleaning_eur_per_nm3: float = 0.25
    # The brine's own CO2 scrubbed from the separated gas, dissolved at pressure and injected
    # with the brine (``Rules.co2_reinjection``), per tonne, all in.
    co2_reinjection_eur_per_t: float = 25.0
    absorption_variable_eur_per_mwh: float = 0.6
    # The hot-water store (``Rules.storage_mwh``): DEA's steel tanks, 3.0 M€2015 per GWh, in
    # 2025 euros (x1.05 to 2020, then the +16.8 % used for DEA's 2020 figures); its upkeep.
    storage_meur_per_mwh: float = 0.00368
    storage_fixed_eur_per_mwh: float = 10.5  # per MWh of capacity, a year
    storage_life_years: int = 40
    # HT-ATES: no published cost found; estimated as a shallow doublet (two wells at 500 m TVD,
    # the ThermoGIS well cost) and its surface plant per MW of charging (the geothermal one).
    ates_well_tvd_m: float = 500.0
    ates_life_years: int = 30
    # Own solar (``Rules.solar_mwp``): its full cost per MWh it makes, capital included (PBL's
    # base amount), and what the electricity the plant does not use sells for.
    solar_eur_per_mwh: float = 88.9
    solar_sale_eur_per_mwh: float = 71.0
    # Free cooling's plate exchanger, with its valves and piping, per MW of cold (assumed).
    free_cooling_meur_per_mw: float = 0.03
    free_cooling_life_years: int = 25
    chiller_fixed_eur_per_mw: float = 10_500.0
    # The cooling towers' water (``YearResult.tower_water_m3``): drinking water for the make-up,
    # with the tap-water tax (excl. VAT), and the blow-down's discharge to the sewer.
    water_supply_eur_per_m3: float = 1.64
    blowdown_disposal_eur_per_m3: float = 0.40
    # Lifetimes, years.
    wells_life_years: int = 30
    heat_pump_life_years: int = 25
    boiler_life_years: int = 25
    electric_boiler_life_years: int = 20
    absorption_life_years: int = 20
    chiller_life_years: int = 25


SOURCES: Dict[str, str] = {
    "discount_rate": (
        "PBL, SDE++ 2026 advice, Table 6.3: geothermal WACC 5.2 % real, after tax; corporate "
        "tax is not in the cost of heat; the investor case adds it"
    ),
    "electricity_eur_per_mwh": (
        "Eurostat nrg_pc_205, Netherlands, band ID (2-20 GWh/yr), 2025, excl. VAT"
    ),
    "gas_eur_per_mwh": (
        "Eurostat nrg_pc_203, Netherlands, band I4, 2025, excl. VAT, on net calorific value"
    ),
    "carbon_eur_per_t": "EU ETS average price 2025 (EEA ETC CM 2025/06; UBA 01/2026)",
    "storage_meur_per_mwh": (
        "Danish Energy Agency, Technology Data - Energy storage, 141 Large-scale hot water "
        "tanks (steel): 3.0 M€2015/GWh, x1.05 (euro-area HICP 2015-2020) x1.168 (2020-2025)"
    ),
    "storage_fixed_eur_per_mwh": "Danish Energy Agency, the same sheet: 8.6 €2015/MWh a year",
    "storage_life_years": "Danish Energy Agency, the same sheet: 40 years",
    "ates_well_tvd_m": (
        "HT-ATES estimated, no published cost found: two wells at this depth (ThermoGIS well "
        "cost) and the surface plant per MW of charging; the Middenmeer pilot (IF Technology "
        "for ECW) charges at 10 MW"
    ),
    "solar_eur_per_mwh": (
        "PBL, SDE++ 2026 advice, table 3.3: base amount for ground-mounted solar PV of 1-20 MWp, "
        "0.0889 €/kWh at 855 full-load hours (its whole cost, capital included)"
    ),
    "solar_sale_eur_per_mwh": (
        "PBL, SDE++ 2026 advice, table 3.4: long-term product price of solar PV, 0.0710 €/kWh"
    ),
    "free_cooling_meur_per_mw": "Assumed: a plate exchanger with valves and piping, 30 €/kW",
    "free_cooling_life_years": "Assumed, as the chillers' towers",
    "carbon_long_term_eur_per_t": (
        "PBL, SDE++ 2026 advice, §4.10: long-term ETS price 2026-2040 (KEV 2025); used only to "
        "weigh CO2 in the best-overall pick"
    ),
    "well_scale": "ThermoGIS v3 economic model (well cost formula, calibrated to PBL SDE++)",
    "well_base_eur": "ThermoGIS v3 economic model",
    "well_per_m_eur": "ThermoGIS v3 economic model",
    "well_per_m2_eur": "ThermoGIS v3 economic model",
    "well_spacing_m": "Our choice (typical Dutch doublet); sets the along-hole length",
    "well_curvature": "ThermoGIS technical model: curvature factor 1.0-1.13",
    "surface_per_doublet_meur": (
        "ThermoGIS v3 economic model (2026): other capex 3.5 M€ + 882 €/kW, calibrated by TNO "
        "to PBL's SDE++ costs; with the v3 wells, 1,410 €/kW for PBL's 27.4 MW reference "
        "(PBL 2026: 1,340 €/kW)"
    ),
    "surface_meur_per_mw": "ThermoGIS v3 economic model (2026): 882 €/kW",
    "treatment_train_meur": (
        "Dioscuri's estimate: the separator and filters' share (about a sixth) of the "
        "per-doublet surface cost; no published split"
    ),
    "treatment_scale_exponent": "Six-tenths rule for process plant (Towler & Sinnott 2013, 7.3)",
    "heat_pump_meur_per_mw": (
        "Danish Energy Agency, technology data, large heat pumps (sheet 40), 2025 €"
    ),
    "boiler_meur_per_mw": "Danish Energy Agency, gas boilers (sheet 44), 2020 € +16.8 %",
    "absorption_meur_per_mw": (
        "US DOE (2017) installed absorption chiller ~730 €/kW + cooling tower (Towler & Sinnott)"
    ),
    "chiller_meur_per_mw": "US EIA (2023) water-cooled chiller ~170 €/kW + cooling tower ~75 €/kW",
    "geothermal_fixed_eur_per_kw": (
        "PBL, SDE++ 2026 advice, Tables 11.7a-c: 117-121 €/kW/yr with insurance, staff and the "
        "ESP provisions (ThermoGIS v3 81, DEA 55-60)"
    ),
    "geothermal_variable_eur_per_mwh": "ThermoGIS v3 OPEX (0.062 €ct/kWh)",
    "heat_pump_fixed_eur_per_mw": "Danish Energy Agency, sheet 40 (2,100-4,300 €/MW/yr)",
    "heat_pump_variable_eur_per_mwh": "Danish Energy Agency, sheet 40 (1.3-3.6 €/MWh)",
    "boiler_fixed_eur_per_mw": "Danish Energy Agency, sheet 44 (2,074 €/MW/yr in 2020 €)",
    "boiler_variable_eur_per_mwh": "Danish Energy Agency, sheet 44 (1.17 €/MWh in 2020 €)",
    "electric_boiler_meur_per_mw": (
        "PBL, SDE++ 2026 advice, Table 13.4: 407 €/kW for a 20 MW electric boiler (boiler 259, "
        "electrical and civil 55, grid connection upgrade 92); DEA 2026 sheet 41: 70-155 €/kW"
    ),
    "electric_boiler_fixed_eur_per_kw": "PBL, SDE++ 2026 advice, Table 13.6: 7.8 €/kW/yr",
    "electric_boiler_grid_eur_per_kw": (
        "Liander 2026 transport tariff, TS/MS >2,000 kW: 3.99 €/kW/month contracted + 6.24 "
        "€/kW/month peak = 123 €/kW/yr (PBL's 2028-2042 firm value: 183; non-firm: 91)"
    ),
    "electric_boiler_variable_eur_per_mwh": "Danish Energy Agency 2026, sheet 41 (large): 0.84",
    "electric_boiler_grid_600h_eur_per_kw": (
        "Liander 2026, 600-hour contract (TS/MS, HS/MS, TS; at most 600 hours a year at the "
        "peak): 1.995 €/kW/month contracted = 23.94 €/kW/yr. The hours are the connection's "
        "(its kWh / its peak kW), so the backup electric boiler is assumed to have its own "
        "connection: the heat pump, pumps and chillers run about 8,000 hours a year"
    ),
    "electric_boiler_grid_600h_week_eur_per_kw": (
        "Liander 2026, 600-hour contract: 2.16 €/kW of each week's peak"
    ),
    "gas_sale_eur_per_mwh": (
        "PBL, SDE++ 2026 advice, Table 4.5: TTF 0.0390 €/kWh (LHV), Sep 2024-Aug 2025"
    ),
    "co2_reinjection_eur_per_t": (
        "CarbFix2 at Hellisheidi: capture, dissolution in water and injection about 25 USD/t "
        "(Gunnarsson et al. 2018, Int. J. Greenh. Gas Control 79, 117-126), taken as 25 EUR/t; "
        "a scale far larger than one doublet's, so a low estimate"
    ),
    "gas_cleaning_eur_per_nm3": (
        "Small biogas upgrading with grid injection: 0.20-0.30 €/Nm3 of raw gas all in, not "
        "economic below about 150 Nm3/h (Jyväskylä University thesis, 2013, techno-economic "
        "comparison of biogas upgrading in Europe); no geothermal figure published"
    ),
    "absorption_variable_eur_per_mwh": "US DOE (2017) absorption chillers",
    "chiller_fixed_eur_per_mw": "US EIA (2023) chiller maintenance 9-12 €/kW/yr",
    "water_supply_eur_per_m3": (
        "WML Tarievenregeling 2026: drinking water 1.1749 €/m3 + provincial tax 0.0270, plus the "
        "belasting op leidingwater 0.4373 €/m3 (on the first 50,000 m3 a connection in 2026, on "
        "all of it from 2027), excl. VAT: 1.64 €/m3. Range 1.2-1.8 (other companies' tariffs; "
        "surface or process water for industry is cheaper)"
    ),
    "blowdown_disposal_eur_per_m3": (
        "Assumed (no tariff for cooling-tower blow-down published): a municipal sewer charge for "
        "a large discharger and the water board's treatment levy on lightly polluted water, "
        "0.40 €/m3; range 0.1-1.0, 0 when a permit lets it go to surface water"
    ),
    "wells_life_years": "PBL SDE++ 2026: technical lifetime of a doublet 30 years",
    "heat_pump_life_years": "Danish Energy Agency, sheet 40",
    "boiler_life_years": "Danish Energy Agency, sheet 44",
    "electric_boiler_life_years": "Danish Energy Agency 2026, sheet 41: 20 years (25 from 2030)",
    "absorption_life_years": "US DOE (2017): 20-25 years",
    "chiller_life_years": "US EIA (2023)",
}


def crf(rate: float, years: int) -> float:
    """Return the capital recovery factor: the yearly payment per euro of capital."""
    if rate == 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def along_hole_m(depth_m: float, prices: Prices = Prices()) -> float:
    """Return a well's along-hole length to a vertical depth (ThermoGIS's technical model)."""
    return prices.well_curvature * math.hypot(depth_m, prices.well_spacing_m / 2)


def priced_tvd_m(depth_m: float, opening: str, thickness_m: float) -> float:
    """Return the vertical depth a well is priced at, from the part of the aquifer it opens.

    ThermoGIS prices a well at the aquifer's midpoint, though a well open over the whole aquifer
    reaches its base. The same offset applies to half-open wells: one open over the lower half
    also reaches the base (priced at the midpoint), one open over the upper half stops at the
    midpoint (priced half a thickness shallower).
    """
    return depth_m - (thickness_m / 2.0 if opening == "upper" else 0.0)


def well_meur(depth_m: float, prices: Prices = Prices()) -> float:
    """Return the cost of one well to a vertical depth, M€ (ThermoGIS v3 formula)."""
    length = along_hole_m(depth_m, prices)
    p = prices
    return (
        p.well_scale
        * (p.well_base_eur + p.well_per_m_eur * length + p.well_per_m2_eur * length**2)
        / 1e6
    )


def capex_items(
    plant: Plant,
    prices: Prices = Prices(),
    brine_mw: float = 0.0,
    rules: Optional[Rules] = None,
) -> List[Dict[str, object]]:
    """Return the capital items of a design: item, size, unit, M€ per unit, M€, lifetime.

    ``brine_mw`` is the largest daily brine heat of the year: the surface plant's size.
    ``rules`` gives the aquifer's thickness and the flow cap (the challenge's by default).
    """
    p, n = prices, plant.n_doublets
    rules = rules or Rules()
    items: List[Dict[str, object]] = []

    def add(item, size, unit, per, life, side):
        if size > 0:
            items.append(
                {
                    "item": item,
                    "size": round(size, 3),
                    "unit": unit,
                    "meur_per_unit": round(per, 4),
                    "meur": round(size * per, 3),
                    "life_years": life,
                    "side": side,
                }
            )

    if n > 0:
        # Wells: each producer and injector at the depth of the part of the aquifer it opens.
        wells: Dict[float, List[str]] = {}
        for d in plant.specs():
            h = rules.aquifer_at(d.depth_m).reservoir_thickness_m  # its own aquifer's
            wells.setdefault(priced_tvd_m(d.depth_m, d.producer_open, h), []).append("producer")
            wells.setdefault(priced_tvd_m(d.depth_m, d.injector_open, h), []).extend(
                ["injector"] * d.injectors
            )
        for tvd, kinds in sorted(wells.items()):
            add("Wells", len(kinds), "wells", well_meur(tvd, p), p.wells_life_years, "shared")
            items[-1]["note"] = (
                f"{kinds.count('producer')} producer(s), {kinds.count('injector')} injector(s), "
                f"priced at {tvd:,.0f} m TVD"
            )
        add(
            "Surface plant",
            n,
            "doublets",
            p.surface_per_doublet_meur - p.treatment_train_meur,
            p.wells_life_years,
            "shared",
        )
        # Treatment trains: one per group of doublets that share one, sized for their brine.
        groups: Dict[int, float] = {}
        for d in plant.specs():
            groups[d.train] = groups.get(d.train, 0.0) + d.cap_m3h(rules) / rules.flow_max_m3h
        for share in groups.values():
            add(
                "Treatment trains",
                1,
                "trains",
                p.treatment_train_meur * share**p.treatment_scale_exponent,
                p.wells_life_years,
                "shared",
            )
        add(
            "Surface plant (per MW)",
            brine_mw,
            "MW",
            p.surface_meur_per_mw,
            p.wells_life_years,
            "shared",
        )
    add(
        "Heat pump",
        plant.heat_pump_mw,
        "MW",
        p.heat_pump_meur_per_mw,
        p.heat_pump_life_years,
        "heat",
    )
    add("Boiler", plant.boiler_mw, "MW", p.boiler_meur_per_mw, p.boiler_life_years, "heat")
    add(
        "Electric boiler",
        plant.electric_boiler_mw,
        "MW",
        p.electric_boiler_meur_per_mw,
        p.electric_boiler_life_years,
        "heat",
    )
    add(
        "Absorption chiller",
        plant.absorption_mw,
        "MW",
        p.absorption_meur_per_mw,
        p.absorption_life_years,
        "cold",
    )
    add(
        "Electric chillers",
        plant.chiller_mw,
        "MW",
        p.chiller_meur_per_mw,
        p.chiller_life_years,
        "cold",
    )
    return items


GRID_600H = 600.0  # hours a year at the peak: up to this, the 600-hour contract applies


def grid_capacity_meur(plant: Plant, year: YearResult, prices: Prices = Prices()) -> float:
    """Return the electric boiler's grid capacity charge a year, M€.

    The connection is contracted for the boiler's full electric load. A boiler that runs at
    most ``GRID_600H`` hours a year at its peak (energy / peak) takes the 600-hour contract:
    a lower charge per kW contracted plus each week's peak; otherwise the standard charge, for
    the whole year. Peaks are daily averages here (the model is daily), so a week's peak is a
    little low. The rule is per connection: the electric boiler is assumed to have its own,
    apart from the units that run all year (heat pump, pumps, chillers). An outage that makes
    it run more can break the 600 hours (``failure_costs.grid_change_meur``).
    """
    if plant.electric_boiler_mw <= 0:
        return 0.0
    contracted_kw = plant.electric_boiler_mw / Components().electric_boiler_efficiency * 1000
    daily = np.asarray(year.daily_mw.get("power", {}).get("electric_boiler") or [0.0])
    peak_kw = float(daily.max(initial=0.0)) * 1000
    hours = year.electricity_gwh.get("electric_boiler", 0.0) * 1e6 / peak_kw if peak_kw else 0.0
    if hours > GRID_600H:
        return prices.electric_boiler_grid_eur_per_kw * contracted_kw / 1e6
    weeks = [float(daily[i : i + 7].max(initial=0.0)) * 1000 for i in range(0, len(daily), 7)]
    weekly = prices.electric_boiler_grid_600h_week_eur_per_kw * sum(weeks)
    return float(prices.electric_boiler_grid_600h_eur_per_kw * contracted_kw + weekly) / 1e6


def economics(
    plant: Plant,
    year: YearResult,
    prices: Prices = Prices(),
    reference: Optional[Tuple[YearResult, Economics]] = None,
    rules: Optional[Rules] = None,
) -> Economics:
    """Price a design's year: levelised cost of heat and of cold, capital and CO2.

    Parameters
    ----------
    plant : Plant
        The design.
    year : YearResult
        Its year from ``simulate_year``.
    prices : Prices
        Prices, unit costs and financial conventions.
    reference : tuple of (YearResult, Economics), optional
        The gas reference, for the CO2 saving.
    rules : Rules, optional
        The aquifer's thickness and the flow cap, for the wells and treatment trains.

    Returns
    -------
    Economics
        Costs by line (heat and cold), the levelised costs, capital items and CO2.
    """
    p = prices
    items = capex_items(plant, p, year.peak_brine_heat_mw, rules)
    store = float((year.storage or {}).get("capacity_mwh") or 0.0)
    ates = (year.storage or {}).get("kind") == "HT-ATES"
    if store > 0 and ates and (year.storage or {}).get("given_gwh"):
        power = float(year.storage.get("power_mw") or 0.0)
        wells = 2 * well_meur(p.ates_well_tvd_m, p)
        items.append(
            {
                "item": "HT-ATES store (estimated)",
                "size": round(power, 1),
                "unit": "MW",
                "meur_per_unit": round((wells + power * p.surface_meur_per_mw) / power, 4),
                "meur": round(wells + power * p.surface_meur_per_mw, 3),
                "life_years": p.ates_life_years,
                "side": "heat",
                "note": "no published HT-ATES cost: two wells at 500 m (ThermoGIS) and a surface "
                "plant per MW",
            }
        )
    elif store > 0 and (year.storage or {}).get("given_gwh"):
        items.append(
            {
                "item": "Heat store",
                "size": round(store, 1),
                "unit": "MWh",
                "meur_per_unit": p.storage_meur_per_mwh,
                "meur": round(store * p.storage_meur_per_mwh, 3),
                "life_years": p.storage_life_years,
                "side": "heat",
            }
        )
    if year.free_cooling_mw > 0:
        items.append(
            {
                "item": "Free-cooling exchanger",
                "size": round(year.free_cooling_mw, 3),
                "unit": "MW",
                "meur_per_unit": p.free_cooling_meur_per_mw,
                "meur": round(year.free_cooling_mw * p.free_cooling_meur_per_mw, 3),
                "life_years": p.free_cooling_life_years,
                "side": "cold",
            }
        )
    lost = (year.network or {}).get("heat_loss_gwh", 0.0) or 0.0
    # Per MWh reaching the buildings: the network's losses are a cost of the heat, not a sale.
    heat_mwh = max(year.heat_delivered_gwh - lost, 0.0) * 1000
    cold_mwh = year.cool_delivered_gwh * 1000
    # Brine heat each side uses, to split the shared costs.
    hp_source = year.heat_split_gwh["hp"] - year.electricity_gwh["hp"]
    heat_brine = year.heat_split_gwh["geo"] + max(hp_source, 0.0)
    cold_brine = year.cool_split_gwh["abs"] / year.absorption_cop if year.absorption_cop else 0.0
    total_brine = heat_brine + cold_brine
    heat_share = heat_brine / total_brine if total_brine > 0 else 1.0

    heat_lines: List[Tuple[str, str, float]] = []
    cold_lines: List[Tuple[str, str, float]] = []

    def put(item: str, kind: str, meur: float, side: str):
        if abs(meur) < 1e-9:
            return
        if side == "heat":
            heat_lines.append((item, kind, meur))
        elif side == "cold":
            cold_lines.append((item, kind, meur))
        else:
            heat_lines.append((item, kind, meur * heat_share))
            if heat_share < 1:
                cold_lines.append((item, kind, meur * (1 - heat_share)))

    for it in items:
        annuity = float(it["meur"]) * crf(p.discount_rate, int(it["life_years"]))
        put(str(it["item"]).replace(" (per MW)", ""), "capital", annuity, str(it["side"]))
    if plant.n_doublets > 0:
        put(
            "Geothermal O&M",
            "fixed",
            p.geothermal_fixed_eur_per_kw * year.peak_brine_heat_mw / 1e3,
            "shared",
        )
        put(
            "Geothermal O&M",
            "variable",
            p.geothermal_variable_eur_per_mwh * total_brine / 1e3,
            "shared",
        )
    put("Heat pump O&M", "fixed", p.heat_pump_fixed_eur_per_mw * plant.heat_pump_mw / 1e6, "heat")
    put(
        "Heat pump O&M",
        "variable",
        p.heat_pump_variable_eur_per_mwh * year.heat_split_gwh["hp"] / 1e3,
        "heat",
    )
    put("Boiler O&M", "fixed", p.boiler_fixed_eur_per_mw * plant.boiler_mw / 1e6, "heat")
    put(
        "Boiler O&M",
        "variable",
        p.boiler_variable_eur_per_mwh * year.heat_split_gwh["boiler"] / 1e3,
        "heat",
    )
    eb_mw = plant.electric_boiler_mw
    put("Electric boiler O&M", "fixed", p.electric_boiler_fixed_eur_per_kw * eb_mw / 1e3, "heat")
    put("Electric boiler grid capacity", "fixed", grid_capacity_meur(plant, year, p), "heat")
    put(
        "Electric boiler O&M",
        "variable",
        p.electric_boiler_variable_eur_per_mwh
        * year.heat_split_gwh.get("electric_boiler", 0.0)
        / 1e3,
        "heat",
    )
    put(
        "Absorption O&M",
        "variable",
        p.absorption_variable_eur_per_mwh * year.cool_split_gwh["abs"] / 1e3,
        "cold",
    )
    put("Chiller O&M", "fixed", p.chiller_fixed_eur_per_mw * plant.chiller_mw / 1e6, "cold")
    water = getattr(year, "tower_water_m3", None) or {}
    put(
        "Water: cooling towers",
        "variable",
        (
            float(water.get("makeup", 0.0)) * p.water_supply_eur_per_m3
            + float(water.get("blowdown", 0.0)) * p.blowdown_disposal_eur_per_m3
        )
        / 1e6,
        "cold",
    )
    el = year.electricity_gwh
    put(
        "Electricity: heat pump", "electricity", el["hp"] * p.electricity_eur_per_mwh / 1000, "heat"
    )
    put(
        "Electricity: pumps",
        "electricity",
        el["pumps"] * p.electricity_eur_per_mwh / 1000,
        "shared",
    )
    put(
        "Electricity: chillers",
        "electricity",
        el["chillers"] * p.electricity_eur_per_mwh / 1000,
        "cold",
    )
    put(
        "Electricity: electric boiler",
        "electricity",
        el.get("electric_boiler", 0.0) * p.electricity_eur_per_mwh / 1000,
        "heat",
    )
    put(
        "Electricity: network pumps",
        "electricity",
        el.get("network", 0.0) * p.electricity_eur_per_mwh / 1000,
        "heat",
    )
    put(
        "Electricity: cooling towers",
        "electricity",
        el["towers"] * p.electricity_eur_per_mwh / 1000,
        "cold",
    )
    put("Gas", "gas", year.purchased_gas_gwh * p.gas_eur_per_mwh / 1000, "heat")
    sold = year.produced_gas_sold_gwh
    if sold > 0:  # the brine's gas sold: a revenue, less cleaning it per Nm3 of raw gas
        ch4 = (rules or Rules()).gas_ch4_fraction or 1.0
        raw_nm3 = sold * 1e6 / (LHV_CH4_MJ_PER_NM3 / 3.6) / ch4
        put("Gas sold", "gas", -sold * p.gas_sale_eur_per_mwh / 1000, "shared")
        put(
            "Gas cleaning and injection",
            "variable",
            raw_nm3 * p.gas_cleaning_eur_per_nm3 / 1e6,
            "shared",
        )
    if store > 0 and (year.storage or {}).get("given_gwh") and not ates:
        put("Heat store O&M", "fixed", p.storage_fixed_eur_per_mwh * store / 1e6, "heat")
    sun = year.solar or {}
    if sun.get("generated_gwh"):
        # Own solar: its whole cost per MWh it makes (capital in it); the plant buys less, and
        # what it does not use is sold.
        put("Own solar", "fixed", sun["generated_gwh"] * p.solar_eur_per_mwh / 1000, "shared")
        put(
            "Electricity: own solar used",
            "electricity",
            -sun["used_gwh"] * p.electricity_eur_per_mwh / 1000,
            "shared",
        )
        put(
            "Electricity: own solar sold",
            "electricity",
            -sun["sold_gwh"] * p.solar_sale_eur_per_mwh / 1000,
            "shared",
        )
    co2 = year.co2_t
    put("CO2: gas", "carbon", co2["purchased_gas"] * p.carbon_eur_per_t / 1e6, "heat")
    put("CO2: produced gas", "carbon", co2["produced_gas"] * p.carbon_eur_per_t / 1e6, "shared")
    if co2.get("reinjected"):
        put(
            "CO2 reinjection",
            "variable",
            co2["reinjected"] * p.co2_reinjection_eur_per_t / 1e6,
            "shared",
        )

    heat_cost = sum(m for _, _, m in heat_lines)
    cold_cost = sum(m for _, _, m in cold_lines)
    lcoh = heat_cost * 1e6 / heat_mwh if heat_mwh > 0 else 0.0  # no heat: nothing to level
    lcoc = cold_cost * 1e6 / cold_mwh if cold_mwh > 0 else None
    total_mwh = heat_mwh + cold_mwh
    capex = sum(float(it["meur"]) for it in items)
    opex = sum(m for _, kind, m in heat_lines + cold_lines if kind != "capital")
    saving = None
    if reference is not None and reference[0].co2_t["total"] > 0:
        saving = 1 - year.co2_t["total"] / reference[0].co2_t["total"]
    merged: Dict[Tuple[str, str], float] = {}
    for item, kind, m in heat_lines + cold_lines:
        merged[(item, kind)] = merged.get((item, kind), 0.0) + m
    return Economics(
        plant=plant,
        source=SOURCE,
        lcoh_eur_per_mwh=round(lcoh, 2),
        lcoc_eur_per_mwh=round(lcoc, 2) if lcoc is not None else None,
        lcoe_eur_per_mwh=round((heat_cost + cold_cost) * 1e6 / total_mwh, 2) if total_mwh else 0.0,
        capex_meur=round(capex, 3),
        lines=[(i, k, round(m, 4)) for (i, k), m in merged.items()],
        lines_heat=[(i, k, round(m, 4)) for i, k, m in heat_lines],
        lines_cold=[(i, k, round(m, 4)) for i, k, m in cold_lines],
        capex_items=items,
        co2_t_per_year=year.co2_t["total"],
        co2_saving_vs_gas=round(saving, 4) if saving is not None else None,
        opex_meur_per_year=round(opex, 4),
        assumptions={k: {"value": v, "source": SOURCES.get(k, "")} for k, v in asdict(p).items()},
    )
