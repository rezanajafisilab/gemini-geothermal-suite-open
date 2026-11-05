"""Component models of the surface plant, vectorised over days.

Each model is a few lines of physics with its parameters named and sourced, so a hand
calculation can check it. GEMINI has the heat pump (``HeatpumpBasic``, Carnot mode); the
formula here is the same one, with our patch 10 (the evaporator runs at the source's outlet).
GEMINI has no chillers; those are ours.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gemini_model.cooling_common.config import AbsorptionSettings, TowerSettings, WaterSettings

K = 273.15

# Methane's lower heating value per normal cubic metre (0 °C, 1.01325 bar): 35.8 MJ/Nm3
# (ISO 6976:2016, net calorific value of methane).
LHV_CH4_MJ_PER_NM3 = 35.8
# CO2 per normal cubic metre of CO2, or of CH4 burnt (one mole each): 44.01 g / 22.414 L.
CO2_KG_PER_NM3 = 44.01 / 22.414
CH4_KG_PER_NM3 = 16.04 / 22.414
# Methane let out unburnt: a flare destroys 98 % of it (US EPA's default destruction efficiency,
# GHG Reporting Program subpart W); fossil methane warms 29.8 times as much as CO2 over 100 years
# (IPCC AR6 WG1, table 7.15). Counted apart from the CO2, as CO2-equivalent (2 Nov).
FLARE_DESTRUCTION = 0.98
CH4_GWP100 = 29.8
# The cooling component model's settings (``gemini_model.cooling_common.config``), reused so the
# year model and the cooling check share their towers' water and pumps and the absorption
# chiller's limit: the generator's clean hot-water loop is supplied at 75 °C through an
# exchanger with a 5 K approach, so the brine must reach it at 80 °C at least.
_ABS, _TOWER, _WATER = AbsorptionSettings(), TowerSettings(), WaterSettings()
ABSORPTION_MIN_DRIVE_C = _ABS.hot_supply_c + _ABS.hx_approach_k


@dataclass(frozen=True)
class Components:
    """Performance parameters of the surface units (the sources are in ``ASSUMPTIONS``)."""

    heat_pump_eta: float = 0.50  # GEMINI HeatpumpBasic default; DEA second-law 0.48-0.50
    heat_pump_min_source_c: float = 10.0  # evaporator limit, on top of the 40 K brine cap
    absorption_cop: float = 0.75  # single-effect LiBr, 15-18 °C chilled water (IEA SHC Task 48)
    absorption_brine_drop_k: float = 15.0  # brine through the generator (about 86 -> 71 °C)
    chiller_eta: float = 0.50  # COP 8.6 at 20 °C; derived 9.5-10.5 (EIA, Thu et al. 2017)
    chiller_condensing_c: float = 35.0  # water-cooled: cooling water at about 30 °C + 5 K
    chiller_evap_approach_k: float = 2.0
    # Below this wellhead temperature the absorption chiller gives no cold (its hot-water loop).
    absorption_min_drive_c: float = ABSORPTION_MIN_DRIVE_C
    # Cooling-tower fans per MW rejected: 1.25 % (ASHRAE 90.1's minimum for open towers with
    # axial fans, 40.2 gpm/hp at 35/29.4/23.9 °C: 59 kW rejected per 0.75 kW of fan).
    tower_mw_el_per_mw: float = 0.0125
    # Condenser-water pumps per MW rejected: 0.5 % (the cooling component model's
    # ``TowerSettings.pump_ratio``); their heat goes into the towers' water.
    tower_pump_mw_el_per_mw: float = _TOWER.pump_ratio
    # The towers' water (the cooling component model's ``WaterSettings``, no drift): 80 % of the
    # heat rejected leaves as evaporation at 2.45 MJ/kg; the blow-down keeps the dissolved salts
    # at 5 cycles of concentration (blow-down = evaporation / (cycles - 1)).
    tower_latent_fraction: float = _WATER.latent_fraction
    tower_latent_heat_mj_per_kg: float = _WATER.latent_heat_j_kg / 1e6
    tower_cycles: float = _WATER.cycles
    # Gas boiler, LHV; condensing needs a colder return than 60 °C (DEA sheet 44: 92-95 %).
    boiler_efficiency: float = 0.95
    # Electric boiler (electrode or resistance): DEA 2026 sheet 41 and PBL SDE++ 2026 §13.2.6.
    electric_boiler_efficiency: float = 0.99
    # Natural gas: 56,100 kg CO2/TJ (IPCC 2006 Guidelines, vol. 2, table 2.2) = 0.202 t/MWh.
    gas_t_co2_per_mwh: float = 0.202
    # Grid electricity, Netherlands 2024, average of all production (CBS, Dec 2025).
    grid_t_co2_per_mwh: float = 0.20
    # The grid's CO2 by month, relative to its year (``Rules.grid_by_month``): Ember's monthly
    # electricity data, Netherlands 2024, emissions intensity of generation (gCO2e/kWh) over the
    # year's generation-weighted mean; the year's level stays the one above. Winter's grid is
    # dirtier (more gas, less sun): a heat pump's winter electricity weighs more.
    grid_month_shape: tuple = (
        1.146,
        1.029,
        1.021,
        0.754,
        0.86,
        0.744,
        0.749,
        0.849,
        0.924,
        1.192,
        1.389,
        1.209,
    )
    # The supply chain of the gas bought (extraction, LNG, transport), CO2-equivalent: 0.015 kg
    # per MJ of fossil methane (co2emissiefactoren.nl 2025, CNG; its compression included, so
    # an upper value) = 0.054 t/MWh. A life-cycle figure, kept out of the plant's CO2 total.
    gas_upstream_t_co2e_per_mwh: float = 0.054
    # Free cooling: the towers' water leaves 4 K above the wet bulb and the plate exchanger
    # takes 2 K more (assumed: towers are usually selected for 3-6 K, plate exchangers 1-2 K).
    free_cooling_approach_k: float = 6.0
    # Own solar: 855 full-load hours a year (PBL, SDE++ 2026 advice, table 3.3: ground-mounted
    # 1-20 MWp), spread over the year as the KNMI radiation at De Bilt (``weather``).
    solar_full_load_hours: float = 855.0
    # The hot-water store (Danish Energy Agency, Technology Data - Energy storage, 141 Large-
    # scale hot water tanks, steel): 0.2 % of its heat lost a day; 2.9 MW in and out per 175 MWh.
    storage_loss_per_day: float = 0.002
    storage_mw_per_mwh: float = 2.9 / 175.0
    # A high-temperature aquifer store (HT-ATES), as the Middenmeer pilot (IF Technology for ECW,
    # GEOTHERMICA HEATSTORE: charged at 10 MW, recovered at 2-8 MW, about 28,000 MWh a year); 60 %
    # of the heat put in comes back (53-71 % for HT-ATES with more than 35 K, EGU 2019-4341).
    ates_mw: float = 10.0
    ates_recovery: float = 0.60


# A compressor needs some pressure ratio: the Carnot COP is taken over at least this lift, so the
# COP stays finite (at most 0.5 x 373 K / 10 K = 18.7 for the challenge's 100 °C) when the source
# is nearly as hot as the supply, as when the heat exchanger is out and the heat pump takes the
# brine straight from the well (4 Nov audit: a year COP of 64 there, infinite above 100 °C).
MIN_LIFT_K = 10.0


def heat_pump_cop(sink_out_c, source_out_c, eta: float = 0.5):
    """Return the COP of a heat pump (GEMINI ``HeatpumpBasic``, Carnot mode, patch 10).

    COP = eta * T_sink_out / max(T_sink_out - T_source_out, MIN_LIFT_K), temperatures in
    kelvin: the Carnot COP over at least a 10 K lift.

    Parameters
    ----------
    sink_out_c : float or array
        Supply temperature the heat pump delivers, °C.
    source_out_c : float or array
        Temperature the source leaves at, °C.
    eta : float
        Fraction of the Carnot COP reached.

    Returns
    -------
    float or array
        COP (heat out / electricity in).
    """
    lift = np.asarray(sink_out_c, dtype=float) - np.asarray(source_out_c, dtype=float)
    return eta * (np.asarray(sink_out_c, dtype=float) + K) / np.maximum(lift, MIN_LIFT_K)


def heat_pump_on_source(heat_mw, source_in_c, source_mw_per_k, sink_out_c, floor_c, eta):
    """Solve a heat pump on a stream for each day: how far it cools the source, and its COP.

    The heat pump delivers ``heat_mw`` (or less, when the source cannot give enough before
    reaching ``floor_c``); its evaporator takes heat_mw * (1 - 1/COP) from the source, whose
    outlet temperature sets the COP. Bisection on the outlet temperature, vectorised.

    Parameters
    ----------
    heat_mw : array
        Heat wanted from the heat pump each day, MW.
    source_in_c : array
        Source temperature at the evaporator inlet, °C.
    source_mw_per_k : array
        Source heat-capacity rate, MW/K.
    sink_out_c : float
        Supply temperature, °C.
    floor_c : array or float
        Lowest outlet temperature of the source (the brine cap and the evaporator limit).
    eta : float
        Carnot efficiency.

    Returns
    -------
    tuple of arrays
        (heat delivered MW, source outlet °C, COP, electricity MW)
    """
    heat = np.asarray(heat_mw, dtype=float)
    t_in = np.asarray(source_in_c, dtype=float)
    cb = np.asarray(source_mw_per_k, dtype=float)
    floor = np.minimum(np.broadcast_to(np.asarray(floor_c, dtype=float), t_in.shape), t_in)
    # Most the source can give before reaching its floor.
    cop_floor = heat_pump_cop(sink_out_c, floor, eta)
    max_heat = np.where(
        cop_floor > 1, cb * (t_in - floor) * cop_floor / np.maximum(cop_floor - 1, 1e-9), 0.0
    )
    heat = np.clip(heat, 0.0, max_heat)
    lo, hi = floor.copy(), t_in.copy()
    for _ in range(40):  # 40 halvings: far below 0.001 K
        mid = 0.5 * (lo + hi)
        cop = heat_pump_cop(sink_out_c, mid, eta)
        taken = cb * (t_in - mid)
        needed = heat * (1 - 1 / np.maximum(cop, 1.0 + 1e-9))
        too_cold = taken > needed  # the source would be cooled more than the heat needs
        lo = np.where(too_cold, mid, lo)
        hi = np.where(too_cold, hi, mid)
    t_out = np.where(heat > 0, 0.5 * (lo + hi), t_in)
    cop = np.where(heat > 0, heat_pump_cop(sink_out_c, t_out, eta), 0.0)
    electricity = np.where(heat > 0, heat / np.maximum(cop, 1e-9), 0.0)
    return heat, t_out, cop, electricity


def chiller_cop(supply_c: float, condensing_c: float, eta: float, approach_k: float) -> float:
    """Return an electric chiller's COP (cold out / electricity in) from its Carnot limit.

    COP = eta * T_evap / (T_cond - T_evap), with the evaporator ``approach_k`` below the
    chilled-water supply.
    """
    t_evap = supply_c - approach_k + K
    t_cond = condensing_c + K
    return eta * t_evap / max(t_cond - t_evap, 1e-9)


def produced_gas(flow_m3h, gas_liquid_ratio: float, ch4_fraction: float, co2_fraction: float):
    """Return the produced gas of a brine flow: CH4 energy (MW) and Nm3/h of CH4 and CO2.

    Parameters
    ----------
    flow_m3h : array
        Brine flow, m3/h.
    gas_liquid_ratio, ch4_fraction, co2_fraction : float
        Gas per m3 of liquid (Nm3/m3) and its molar make-up.

    Returns
    -------
    tuple of arrays
        (CH4 energy MW (LHV), CH4 Nm3/h, CO2 Nm3/h)
    """
    gas = np.asarray(flow_m3h, dtype=float) * gas_liquid_ratio
    ch4, co2 = gas * ch4_fraction, gas * co2_fraction
    return ch4 * LHV_CH4_MJ_PER_NM3 / 3600.0, ch4, co2


def tower_water_m3(rejected_mw, comp: Components) -> tuple:
    """Return the towers' evaporation, blow-down and make-up water a day, m3, per MW rejected.

    Evaporation = heat x latent fraction / latent heat (1,000 kg/m3); blow-down = evaporation /
    (cycles - 1); make-up = both. 1 MWh rejected evaporates 3,600 x 0.8 / 2,450 = 1.18 m3.
    """
    heat_mj = np.asarray(rejected_mw, dtype=float) * 3600.0 * 24.0  # MJ a day
    evaporation = heat_mj * comp.tower_latent_fraction / comp.tower_latent_heat_mj_per_kg / 1000
    blowdown = evaporation / (comp.tower_cycles - 1.0)
    return evaporation, blowdown, evaporation + blowdown
