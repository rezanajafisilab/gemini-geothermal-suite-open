"""What a message asks to set or change, read by a model and checked by code.

One catalogue (``CATALOGUE``) lists every parameter a design or a what-if can set: the
networks' temperatures, the reservoir, the challenge's caps, the demand, the prices, how the
doublets are built and the units' sizes. The reasoning model maps the user's words onto it
(``read``); every change must quote the message, stay in its range and, for numbers, show its
number in the quote, so a model cannot invent a change. ``apply`` then turns the changes into a
brief (the conditions and the search's options) and, for a what-if, the design's own changes.
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

from gemini_agent import quantities, reading_examples
from gemini_agent.contract import Alternative, DesignBrief, DoubletSpec, NetworkTemps
from gemini_agent.llm import LLMCall, LLMError

# v2: failures, the designs named, the steps of a request; v3: the chat's thread (4 Nov).
PROMPT = "parameters_v3"
OPENINGS = ["full", "upper", "lower"]
UNITS = ["heat_pump", "boiler", "chiller", "electric_boiler"]  # boiler: the gas boiler


@dataclass(frozen=True)
class Parameter:
    """One parameter: what it is, its unit, its range or options, and where it goes."""

    label: str
    unit: str = ""
    low: Optional[float] = None
    high: Optional[float] = None
    options: Tuple[str, ...] = ()
    kind: str = "number"  # number, choice, list
    target: str = "rules"  # network, brief, rules, scale, prices, search, size
    field: str = ""  # the field it sets (Rules, Prices, DesignBrief ...), the key when empty
    relative: bool = False  # a change to add (reservoir temperature)
    # In plain words, for the inputs card and the chat (``EXPLAINED``): what it is and what it
    # changes in the design; its typical values (in the catalogue's unit) and where they come
    # from; what it depends on, or what depends on it.
    help: str = ""
    typical: Optional[Tuple[float, float]] = None
    typical_words: str = ""
    depends: str = ""
    # The other parameters it is linked to (catalogue keys; the card reads the links both ways)
    # and what it changes in the design, in a few words each (``LINKS``).
    linked: Tuple[str, ...] = ()
    affects: Tuple[str, ...] = ()
    # Only the inputs card sets it (a fact of the challenge's brine): not in the reading's prompt.
    card_only: bool = False


CATALOGUE: Dict[str, Parameter] = {
    # The networks.
    "heat_supply_c": Parameter("Heating supply temperature", "°C", 50, 130, target="network"),
    "heat_return_c": Parameter("Heating return temperature", "°C", 20, 95, target="network"),
    "cool_supply_c": Parameter("Cooling supply temperature", "°C", 2, 25, target="network"),
    "cool_return_c": Parameter("Cooling return temperature", "°C", 6, 35, target="network"),
    # The reservoir and the brine.
    "reservoir_change_k": Parameter(
        "Reservoir temperature change (warmer +, colder -)",
        "K",
        -30,
        30,
        target="brief",
        field="reservoir_delta_c",
        relative=True,
    ),
    "gradient_c_per_km": Parameter("Geothermal gradient", "°C/km", 10, 80),
    "permeability_md": Parameter("Reservoir permeability", "mD", 5, 5000),
    "reservoir_thickness_m": Parameter("Aquifer thickness", "m", 5, 1000),
    "reservoir_pressure_bar": Parameter("Reservoir pressure", "bar", 20, 800),
    "gas_liquid_ratio": Parameter(
        "Gas-liquid ratio of the known aquifer's brine (another aquifer's: aquifers)",
        "Nm3/m3",
        0,
        10,
    ),
    # The challenge's caps.
    "operating_days": Parameter("Days a year each doublet may run", "days", 100, 365),
    "flow_max_m3h": Parameter("Flow cap per doublet", "m3/h", 50, 1000),
    "flow_min_m3h": Parameter("Minimum flow of a running doublet", "m3/h", 0, 300),
    "max_brine_cooling_k": Parameter("Most the brine may be cooled", "K", 5, 90),
    "network_length_km": Parameter(
        "Length of the district network's trunk from the plant to the buildings (0: no losses)",
        "km",
        0,
        50,
    ),
    "planned_service": Parameter(
        "Planned yearly service of each unit in its quietest weeks (1 on, 0 off)", "", 0, 1
    ),
    "grid_t_co2_per_mwh": Parameter(
        "Grid electricity's CO2 (CBS 2024 average 0.20; lower for a cleaner future grid)",
        "t/MWh",
        0,
        1,
    ),
    "flare_brine_gas": Parameter(
        "Flaring (all the brine's gas flared, none burnt in the boiler; 1 on, 0 off)", "", 0, 1
    ),
    "storage_ates": Parameter(
        "Heat store in an aquifer, HT-ATES (summer heat kept in the ground for winter; set "
        "with its size in storage_mwh; 1 on, 0 a tank)",
        "",
        0,
        1,
    ),
    "grid_by_month": Parameter(
        "Grid CO2 month by month (instead of one yearly figure: winter electricity dirtier, "
        "summer cleaner; 1 on, 0 off)",
        "",
        0,
        1,
    ),
    "free_cooling": Parameter(
        "Free cooling (the cooling towers cool the network directly, before the chillers, on "
        "days the outside air is cold enough; 1 on, 0 off)",
        "",
        0,
        1,
    ),
    "solar_mwp": Parameter("Own solar panels (PV) at the plant (0: none)", "MWp", 0, 200),
    "storage_mwh": Parameter(
        "Heat store at the plant (a hot-water tank or buffer, or a seasonal aquifer store with "
        "storage_ates on; 0: none)",
        "MWh",
        0,
        50000,
    ),
    "second_aquifer_depth_m": Parameter(
        "Depth of the middle of a second aquifer the wells could be drilled to (0: none)",
        "m",
        0,
        6000,
    ),
    "second_aquifer_thickness_m": Parameter("Thickness of the second aquifer", "m", 5, 500),
    "second_aquifer_permeability_md": Parameter(
        "Permeability of the second aquifer", "mD", 1, 10000
    ),
    "co2_reinjection": Parameter(
        "CO2 reinjection (the brine's own CO2 dissolved back into the injected brine instead "
        "of let out; 1 on, 0 off)",
        "",
        0,
        1,
    ),
    # The user's dates for the doublets' yearly stop (their maintenance window); code reads
    # the dates from the quote ("move the stop to August", "doublet 2 off 1 to 21 July").
    "doublet_stops": Parameter(
        "Dates of the doublets' yearly stop, their maintenance window (value: the dates in "
        "words, as the message gives them)",
        kind="dates",
        target="stops",
    ),
    "pump_efficiency": Parameter("Pump efficiency", "fraction", 0.2, 1.0),
    # The demand.
    "heat_demand_scale": Parameter("Heat demand multiplier", "x", 0.1, 5, target="scale"),
    "homes": Parameter(
        "Homes the district serves (for costs per home)", "", 10, 1000000, target="brief"
    ),
    "min_co2_saving": Parameter(
        "Smallest CO2 cut against gas a design must reach (0.5: half)",
        "fraction",
        0,
        1,
        target="brief",
    ),
    "cool_demand_scale": Parameter("Cooling demand multiplier", "x", 0.0, 5, target="scale"),
    # Prices and costs.
    "electricity_eur_per_mwh": Parameter("Electricity price", "EUR/MWh", 0, 2000, target="prices"),
    "gas_eur_per_mwh": Parameter("Gas price", "EUR/MWh", 0, 1000, target="prices"),
    "carbon_eur_per_t": Parameter("CO2 price", "EUR/t", 0, 1000, target="prices"),
    "discount_rate": Parameter("Discount rate (real)", "fraction", 0, 0.3, target="prices"),
    "well_spacing_m": Parameter("Well spacing at the aquifer", "m", 300, 5000, target="prices"),
    "capex_scale": Parameter("All capital costs multiplier", "x", 0.2, 5, target="prices"),
    # How the plant is built and chosen (the search's options; a what-if's design changes).
    "n_doublets": Parameter("Number of doublets", "", 1, 3, target="search"),
    "aquifer_depths_m": Parameter(
        "Aquifer depths to try (other than the known one are assumed aquifers)",
        "m",
        500,
        7000,
        kind="list",
        target="search",
        field="doublet_depths_m",
    ),
    # Every aquifer the wells may be drilled into, each with its own depth, rock, pressure and
    # gas (``gemini_agent.aquifers``): added, changed, dropped or kept alone.
    "aquifers": Parameter(
        "The aquifers the wells can be drilled into, each with its own depth, thickness, "
        "permeability, pressure and gas-liquid ratio (the known one first; an aquifer you add "
        "replaces the assumed ones)",
        kind="records",
        target="aquifers",
    ),
    "injectors": Parameter("Injectors per doublet", "", 1, 2, target="search"),
    "trains": Parameter(
        "Treatment trains (separator, filters)",
        options=("shared", "separate"),
        kind="choice",
        target="search",
    ),
    "dispatch": Parameter(
        "How doublets share the brine: equal shares, or the hottest first (base load)",
        options=("equal", "base"),
        kind="choice",
        target="search",
    ),
    "producer_open": Parameter(
        "Part of the aquifer producers are open to",
        options=tuple(OPENINGS),
        kind="choice",
        target="search",
    ),
    "injector_open": Parameter(
        "Part of the aquifer injectors are open to",
        options=tuple(OPENINGS),
        kind="choice",
        target="search",
    ),
    "exclude": Parameter(
        "Units ruled out",
        options=tuple(UNITS),
        kind="list",
        target="search",
        field="excluded",
    ),
    "allow": Parameter("Units allowed again", options=tuple(UNITS), kind="list", target="search"),
    "objective": Parameter(
        "What best means: best (a reliable plan, cheapest with CO2 at the long-term price), "
        "cost (the cheapest), co2 (the lowest CO2), reliable (any one unit can be out), "
        "green_reliable (the lowest CO2 of the reliable plans), gas_free (no gas bought: heat "
        "pumps and an electric boiler)",
        options=("best", "cost", "co2", "reliable", "green_reliable", "gas_free"),
        kind="choice",
        target="search",
    ),
    # Unit sizes of the current design (what-ifs).
    "heat_pump_mw": Parameter("Heat pump size", "MW", 0, 100, target="size"),
    "boiler_mw": Parameter("Boiler size", "MW", 0, 100, target="size"),
    "absorption_mw": Parameter("Absorption chiller size", "MW", 0, 100, target="size"),
    "chiller_mw": Parameter("Electric chillers size", "MW", 0, 100, target="size"),
}
# The brine's properties the requirements give (and the heat capacity they don't): the inputs
# card can change them; the reading's prompt does not list them (``card_only``).
CATALOGUE.update(
    {
        "brine_density_kg_m3": Parameter("Brine density", "kg/m3", 980, 1300, card_only=True),
        "brine_viscosity_pa_s": Parameter("Brine viscosity", "Pa s", 0.0001, 0.003, card_only=True),
        "brine_cp_j_kg_k": Parameter("Brine heat capacity", "J/(kg K)", 3000, 4300, card_only=True),
        "gas_ch4_fraction": Parameter("Methane share of the gas", "fraction", 0, 1, card_only=True),
        "gas_co2_fraction": Parameter("CO2 share of the gas", "fraction", 0, 1, card_only=True),
    }
)

# Each parameter in plain words (the inputs card shows them; the chat may quote them): what it
# is and what it changes in the design (``help``), its typical values in the catalogue's unit
# (``typical``: outside them the card warns) and their source, and what it depends on.
EXPLAINED: Dict[str, Dict[str, object]] = {
    "heat_demand_scale": dict(
        help="Multiplies the district's daily heat demand from the file (1 is the file as "
        "given). More demand needs more doublets, a bigger heat pump or more boiler.",
        typical=(0.8, 1.5),
        typical_words="0.8 to 1.5: a district that shrinks or grows by half; 1 for the challenge",
        depends="The heat demand file; every unit is sized for the scaled peak",
    ),
    "cool_demand_scale": dict(
        help="Multiplies the district's daily cooling demand from the file (1 as given, 0 no "
        "cooling). More cooling needs bigger chillers and cooling towers.",
        typical=(0.0, 1.5),
        typical_words="0 (no cooling) to 1.5; 1 for the challenge",
        depends="The cooling demand file",
    ),
    "reservoir_thickness_m": dict(
        help="How thick the water-bearing sandstone is. A thicker layer lets a well produce "
        "more brine for the same pump pressure.",
        typical=(20.0, 300.0),
        typical_words="20 to 300 m for Dutch geothermal sandstones (Rotliegend, Delft); "
        "100 m in the challenge",
        depends="With the permeability it sets the transmissivity (k × h), which sets how much "
        "a doublet can pump",
    ),
    "permeability_md": dict(
        help="How easily brine flows through the rock, in millidarcy. Low permeability means "
        "less flow per well or more pump power for the same flow.",
        typical=(50.0, 1000.0),
        typical_words="50 to 1,000 mD for Dutch geothermal sandstones (ThermoGIS); 200 mD in the "
        "challenge",
        depends="With the thickness it sets the transmissivity (k × h); with the viscosity, the "
        "pressure each m³/h costs",
    ),
    "reservoir_pressure_bar": dict(
        help="The brine's pressure in the aquifer. It sets how high the brine rises in the "
        "well, and so how much the pump in the well (ESP) must lift.",
        typical=(150.0, 400.0),
        typical_words="close to hydrostatic, about 0.1 bar per metre of depth (about 253 bar at "
        "2,500 m); 250 bar in the challenge",
        depends="The aquifer's depth: far below hydrostatic is unusual, above the rock's weight "
        "(about 0.23 bar per metre) impossible",
    ),
    "gradient_c_per_km": dict(
        help="How fast the rock warms with depth. With the surface temperature and the "
        "aquifer's depth it sets the brine's temperature at the producer.",
        typical=(25.0, 40.0),
        typical_words="25 to 40 °C/km in the Netherlands (about 31 on average); 30 in the "
        "challenge",
        depends="The production temperature: surface + gradient × depth (12 + 30 × 2.5 = 87 °C)",
    ),
    "reservoir_change_k": dict(
        help="Moves the reservoir temperature up (+) or down (−) from what the gradient gives, "
        "to test an aquifer warmer or colder than expected.",
        typical=(-10.0, 10.0),
        typical_words="±10 K covers the usual uncertainty of a temperature log; 0 in the "
        "challenge",
        depends="Adds to the production temperature; colder brine gives less heat per m³",
    ),
    "aquifer_depths_m": dict(
        help="The depths (midpoints) the search may drill doublets to. Deeper is hotter but "
        "dearer to drill; depths other than the known aquifer's are assumed aquifers.",
        typical=(1500.0, 4000.0),
        typical_words="1.5 to 4 km for Dutch geothermal doublets; the known aquifer at 2,500 m",
        depends="Each depth's temperature follows the gradient; its rock is the known " "aquifer's",
    ),
    "gas_liquid_ratio": dict(
        help="Gas that comes out of the brine at the separator, in normal m³ per m³ of brine. "
        "Its methane can fire the boiler; its CO₂ is an emission unless put back.",
        typical=(0.0, 2.0),
        typical_words="0.1 to 1.5 Nm³/m³ in Dutch geothermal wells; 0.8 in the challenge",
        depends="With the flow and the gas's methane share it sets the free fuel for the boiler",
    ),
    "brine_density_kg_m3": dict(
        help="Mass of a cubic metre of brine; salty water is heavier than fresh (1,000). It "
        "sets the heat each m³ carries and the weight of the column the pump lifts.",
        typical=(1000.0, 1200.0),
        typical_words="1,000 to 1,200 kg/m³ for formation brines; 1,030 in the challenge",
        depends="Heat per doublet: flow × density × heat capacity × cooling",
    ),
    "brine_viscosity_pa_s": dict(
        help="How thick the brine is. A more viscous brine flows less easily through the rock "
        "and the pipes, so the pumps need more power for the same flow.",
        typical=(0.0002, 0.001),
        typical_words="0.2 to 1 mPa·s for warm brines (60 to 100 °C); 0.40 in the challenge",
        depends="With the permeability it sets the pressure each m³/h costs",
    ),
    "brine_cp_j_kg_k": dict(
        help="Heat a kilogram of brine gives up per degree it is cooled. Saltier brine holds "
        "a little less heat than fresh water (4,186).",
        typical=(3700.0, 4100.0),
        typical_words="3,700 to 4,100 J/(kg·K); about 3,990 for brine of 1,030 kg/m³ "
        "(Sharqawy, Lienhard & Zubair 2010). The challenge does not give it",
        depends="Heat per doublet: flow × density × heat capacity × cooling",
    ),
    "gas_ch4_fraction": dict(
        help="Share of methane in the separated gas. The methane fires the boiler, so less "
        "gas is bought.",
        typical=(0.5, 0.95),
        typical_words="50 to 95 %; 80 % in the challenge",
        depends="Methane and CO₂ together can't be more than 100 % (the rest is nitrogen and "
        "other gases)",
    ),
    "gas_co2_fraction": dict(
        help="Share of CO₂ in the separated gas. It is let out at the separator, and counted in "
        "the design's CO₂, unless it is dissolved back into the injected brine.",
        typical=(0.02, 0.5),
        typical_words="2 to 50 %; 20 % in the challenge",
        depends="Methane and CO₂ together can't be more than 100 %",
    ),
    "flow_max_m3h": dict(
        help="The most brine one doublet may pump. More flow gives more heat but needs more "
        "pump power and pushes harder on the rock.",
        typical=(100.0, 400.0),
        typical_words="100 to 400 m³/h for Dutch doublets; the challenge's cap is 300",
        depends="Heat of one doublet: flow × density × heat capacity × cooling (300 m³/h cooled "
        "40 K is about 13.7 MW)",
    ),
    "flow_min_m3h": dict(
        help="The least a running doublet pumps; below it the doublet stops instead. Well "
        "pumps (ESPs) need a steady minimum flow to stay cool and stable.",
        typical=(30.0, 100.0),
        typical_words="30 to 100 m³/h; the challenge's minimum is 50",
        depends="Must not be above the flow cap",
    ),
    "max_brine_cooling_k": dict(
        help="How much the brine may be cooled from the producer to the injector (ΔT). The "
        "injected brine can't be more than this below the production temperature.",
        typical=(20.0, 50.0),
        typical_words="20 to 50 K; the challenge's cap is 40 K",
        depends="Injection no colder than the production temperature minus this (87 − 40 = "
        "47 °C)",
    ),
    "pump_efficiency": dict(
        help="Share of the pumps' electricity that becomes lift; the rest is lost as heat. A "
        "lower efficiency means more electricity for the same flow.",
        typical=(0.5, 0.8),
        typical_words="50 to 80 % for well pumps (ESPs) and injection pumps; the challenge "
        "sets 70 %",
        depends="Every pump: the producers' ESPs, the injection pumps and the networks' pumps",
    ),
    "operating_days": dict(
        help="Days a year each doublet may run; the rest are its maintenance, when the other "
        "units cover the heat.",
        typical=(300.0, 350.0),
        typical_words="300 to 350 days; the challenge allows at most 330 (35 days off)",
        depends="Each doublet's days off: 365 − this. Its stop dates are set under Maintenance",
    ),
    "heat_supply_c": dict(
        help="Temperature of the hot water the plant sends to the buildings. A hotter supply "
        "needs more lift from the heat pump or boiler when the brine is cooler.",
        typical=(60.0, 110.0),
        typical_words="60 to 110 °C for district heating; the challenge requires 100 °C",
        depends="Must be above the return",
    ),
    "heat_return_c": dict(
        help="Temperature the water comes back from the buildings at. A colder return lets "
        "the brine give more heat and makes the heat pump more efficient.",
        typical=(35.0, 70.0),
        typical_words="35 to 70 °C; the challenge does not give it, Dioscuri assumes 60",
        depends="Must be below the supply; the supply − return sets the network's flow",
    ),
    "cool_supply_c": dict(
        help="Temperature of the chilled water sent to the buildings. A colder supply makes "
        "the chillers work harder.",
        typical=(6.0, 20.0),
        typical_words="6 to 20 °C; the challenge requires 20 °C",
        depends="Must be below the return",
    ),
    "cool_return_c": dict(
        help="Temperature the chilled water comes back at, after taking heat out of the "
        "buildings. A wider gap to the supply moves more cold per m³.",
        typical=(12.0, 30.0),
        typical_words="12 to 30 °C; the challenge does not give it, Dioscuri assumes 25",
        depends="Must be above the supply",
    ),
    "network_length_km": dict(
        help="Length of the main pipe from the plant to the buildings. With a length the "
        "pipes are sized for the peak and lose heat to the ground; 0 delivers at the plant.",
        typical=(1.0, 10.0),
        typical_words="1 to 10 km for a district",
        depends="The plant then supplies a little hotter so the buildings get the supply",
    ),
    "electricity_eur_per_mwh": dict(
        help="What the plant pays for electricity (heat pump, well pumps, chillers). Dearer "
        "power favours direct geothermal heat and boilers over heat pumps.",
        typical=(60.0, 250.0),
        typical_words="60 to 250 €/MWh; Eurostat 2025 for Dutch non-household users",
    ),
    "gas_eur_per_mwh": dict(
        help="What the plant pays for natural gas for the boiler. Dearer gas favours "
        "geothermal heat and heat pumps.",
        typical=(20.0, 80.0),
        typical_words="20 to 80 €/MWh; Eurostat 2025 for Dutch non-household users",
    ),
    "carbon_eur_per_t": dict(
        help="Price of each tonne of CO₂ emitted (EU ETS). It makes gas and grid electricity "
        "dearer when designs are compared.",
        typical=(50.0, 200.0),
        typical_words="50 to 200 €/t; EU ETS 2025 about 70 €/t",
    ),
    "discount_rate": dict(
        help="The real interest rate that spreads the investment over the years. A higher rate "
        "makes costly wells weigh more against fuel bills.",
        typical=(0.02, 0.1),
        typical_words="2 to 10 %; PBL SDE++ 2026 uses about 4 %",
    ),
    "grid_by_month": dict(
        help="Counts the grid electricity's CO₂ month by month: winter power is dirtier, so a "
        "heat pump's winter use weighs more.",
    ),
    "objective": dict(
        help="What “best” means when the search picks a design: the lowest cost, the lowest "
        "CO₂, a reliable plan (any one unit can fail and the heat still comes), or gas-free.",
    ),
    "n_doublets": dict(
        help="How many doublets (a producer and an injector well each) the plant has; “1 to "
        "3” lets the search pick.",
        typical=(1.0, 3.0),
        typical_words="1 to 3 in the challenge",
    ),
    "exclude": dict(
        help="Units the design may not use, for example no gas boilers for a plant without " "gas.",
    ),
    "free_cooling": dict(
        help="On cool days the cooling towers chill the network directly through a plate "
        "exchanger, before the chillers, which saves their electricity.",
        depends="Needs cooling towers: a design with chillers or an absorption chiller",
    ),
    "solar_mwp": dict(
        help="Solar panels at the plant; their power runs the plant first and the rest is " "sold.",
        typical=(0.5, 20.0),
        typical_words="0.5 to 20 MWp (about 1 hectare per MWp)",
    ),
    "storage_mwh": dict(
        help="A hot-water store at the plant: it keeps the geothermal heat of quiet days for "
        "the days the boiler would run.",
        typical=(50.0, 5000.0),
        typical_words="50 to 5,000 MWh for a tank; 10,000 MWh and more for a seasonal store",
    ),
    "storage_ates": dict(
        help="Makes the store seasonal: summer heat kept in a shallow aquifer (HT-ATES) for "
        "winter; about 60 % of it comes back.",
        depends="Needs a store size",
    ),
    "co2_reinjection": dict(
        help="Dissolves the brine's own CO₂ back into the injected brine, so it stays "
        "underground instead of being let out (about 25 €/t).",
    ),
    "flare_brine_gas": dict(
        help="Burns all the brine's gas in a flare instead of the boiler; the boiler then buys "
        "all its gas. Routine flaring needs consent.",
    ),
    "planned_service": dict(
        help="Gives each unit a yearly service in its quietest weeks; the other units cover "
        "those days.",
    ),
    "grid_t_co2_per_mwh": dict(
        help="CO₂ per MWh of grid electricity. A cleaner grid makes heat pumps and chillers "
        "greener.",
        typical=(0.05, 0.4),
        typical_words="0.05 to 0.4 t/MWh; CBS 2024 average 0.20 for the Netherlands",
    ),
    "well_spacing_m": dict(
        help="Distance between the producer and the injector at the aquifer. Wider spacing "
        "delays the cold injected brine reaching the producer but needs longer wells.",
        typical=(1000.0, 2000.0),
        typical_words="1,000 to 2,000 m for Dutch doublets",
    ),
    "capex_scale": dict(
        help="Multiplies every capital cost, to test dearer or cheaper equipment and wells.",
        typical=(0.7, 1.5),
        typical_words="0.7 to 1.5 (±30 to 50 % is a usual cost uncertainty)",
    ),
    "homes": dict(help="Homes the district serves, for the costs per home."),
    "doublet_stops": dict(
        help="The dates each doublet stops for its yearly maintenance; the other units cover "
        "the heat on those days.",
        depends="The operating days: each doublet is off 365 − them",
    ),
    "injectors": dict(
        help="Injection wells per doublet. Two injectors share the brine, so each takes half "
        "the flow at a lower pressure, at the cost of a third well.",
    ),
    "trains": dict(
        help="Whether the doublets share one surface treatment train (gas separator and "
        "filters) or each has its own; separate trains cost more but one can stop alone.",
    ),
    "dispatch": dict(
        help="How the doublets share the brine: in equal shares, or the hottest first at full "
        "flow (base load) and the others after it.",
    ),
    "producer_open": dict(
        help="Which part of the aquifer the producer is open to: all of it, or its upper or "
        "lower half (half the productivity; the lower half is a little hotter).",
    ),
    "injector_open": dict(
        help="Which part of the aquifer the injector is open to: all of it, or its upper or "
        "lower half (half the injectivity).",
    ),
    "second_aquifer_depth_m": dict(
        help="The midpoint of a second aquifer the wells could be drilled to (0: none); its "
        "temperature follows the gradient and its pressure is hydrostatic.",
    ),
    "heat_pump_mw": dict(help="The heat pump's heating power in the current design."),
    "boiler_mw": dict(help="The gas boiler's heating power in the current design."),
    "absorption_mw": dict(help="The absorption chiller's cooling power in the current design."),
    "chiller_mw": dict(help="The electric chillers' cooling power in the current design."),
    "min_co2_saving": dict(
        help="The smallest CO₂ cut against an all-gas plant a design must reach (0.5: half)."
    ),
}
CATALOGUE.update({k: replace(CATALOGUE[k], **v) for k, v in EXPLAINED.items() if k in CATALOGUE})

# What each parameter is linked to (other parameters: the card shows the links both ways) and
# what it changes in the design. When a message sets a value, the inputs card says what it
# affects before the run.
BRINE_HEAT = "the heat per doublet"
PUMPS = "the pumps' power"
LIFT = "how much the heat pump or boiler must lift"
LINKS: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "heat_demand_scale": ((), ("every unit's size", "how many doublets", "the cost")),
    "cool_demand_scale": ((), ("the chillers' size", "the cooling towers", "the cost of cold")),
    "reservoir_thickness_m": (
        ("permeability_md", "flow_max_m3h"),
        ("how much a doublet can pump", PUMPS),
    ),
    "permeability_md": (
        ("reservoir_thickness_m", "flow_max_m3h", "brine_viscosity_pa_s"),
        ("how much a doublet can pump", PUMPS),
    ),
    "reservoir_pressure_bar": (
        ("gas_liquid_ratio",),
        ("how deep the well pump (ESP) hangs", PUMPS),
    ),
    "gradient_c_per_km": (
        ("reservoir_change_k", "max_brine_cooling_k", "heat_supply_c", "aquifer_depths_m"),
        ("the brine's temperature", "the injection temperature floor", LIFT),
    ),
    "reservoir_change_k": (
        ("gradient_c_per_km", "max_brine_cooling_k", "heat_supply_c"),
        ("the brine's temperature", "the injection temperature floor", LIFT),
    ),
    "aquifer_depths_m": (
        ("gradient_c_per_km",),
        ("the brine's temperature", "the cost of drilling"),
    ),
    "aquifers": (
        ("gradient_c_per_km", "reservoir_change_k", "permeability_md", "reservoir_thickness_m"),
        ("the brine's temperature", "the cost of drilling", PUMPS, "the free fuel for the boiler"),
    ),
    "gas_liquid_ratio": (
        ("gas_ch4_fraction", "gas_co2_fraction", "reservoir_pressure_bar"),
        ("the free fuel for the boiler", "the CO₂ let out", "how deep the ESP hangs"),
    ),
    "gas_ch4_fraction": (
        ("gas_co2_fraction", "gas_liquid_ratio"),
        ("the free fuel for the boiler",),
    ),
    "gas_co2_fraction": (("gas_ch4_fraction", "gas_liquid_ratio"), ("the CO₂ let out",)),
    "brine_density_kg_m3": (("brine_cp_j_kg_k", "flow_max_m3h"), (BRINE_HEAT, PUMPS)),
    "brine_viscosity_pa_s": (("permeability_md",), (PUMPS,)),
    "brine_cp_j_kg_k": (
        ("brine_density_kg_m3", "flow_max_m3h", "max_brine_cooling_k"),
        (BRINE_HEAT,),
    ),
    "flow_max_m3h": (
        ("flow_min_m3h", "max_brine_cooling_k", "brine_cp_j_kg_k", "n_doublets"),
        (BRINE_HEAT, "how many doublets are needed", PUMPS),
    ),
    "flow_min_m3h": (("flow_max_m3h",), ("the days the doublets stop in summer",)),
    "max_brine_cooling_k": (
        ("heat_return_c", "gradient_c_per_km", "flow_max_m3h"),
        ("the injection temperature floor", BRINE_HEAT, "how much the heat pump does"),
    ),
    "pump_efficiency": ((), ("the pumps' electricity", "the cost")),
    "operating_days": ((), ("each doublet's days off", "the backup the boiler gives")),
    "heat_supply_c": (
        ("heat_return_c", "gradient_c_per_km"),
        (LIFT, "the share of direct geothermal heat"),
    ),
    "heat_return_c": (
        ("heat_supply_c", "max_brine_cooling_k"),
        (
            "how far the brine is cooled",
            "the heat pump's size and efficiency",
            "the network's flow",
        ),
    ),
    "cool_supply_c": (("cool_return_c",), ("the chillers' efficiency", "the free-cooling days")),
    "cool_return_c": (("cool_supply_c",), ("the network's flow", "the free-cooling days")),
    "electricity_eur_per_mwh": ((), ("heat pump or boiler", "the cost")),
    "gas_eur_per_mwh": ((), ("heat pump or boiler", "the cost")),
    "carbon_eur_per_t": ((), ("the cost of gas and grid power",)),
    "discount_rate": ((), ("how much the investment weighs in the cost",)),
    "n_doublets": (("flow_max_m3h",), ("the heat from the ground", "the cost of drilling")),
    "objective": ((), ("which design is picked",)),
    "exclude": ((), ("which units the plant may have",)),
}
CATALOGUE.update(
    {k: replace(CATALOGUE[k], linked=a, affects=b) for k, (a, b) in LINKS.items() if k in CATALOGUE}
)


def linked_both_ways(key: str) -> List[str]:
    """Return the parameters linked to one: those it names and those that name it."""
    out = list(CATALOGUE[key].linked)
    out += [k for k, p in CATALOGUE.items() if key in p.linked and k not in out and k != key]
    return out


def explain(key: str) -> str:
    """Return a parameter in plain words: what it is, its typical values, what it depends on."""
    p = CATALOGUE[key]
    parts = [p.help or p.label]
    if p.typical_words:
        parts.append(f"Typical: {p.typical_words}.")
    if p.depends:
        parts.append(f"Linked to: {p.depends}.")
    return " ".join(parts)


SIZE_KEYS = {"heat_pump_mw": "heat_pump", "boiler_mw": "boiler", "absorption_mw": "absorption"}
SIZE_KEYS["chiller_mw"] = "chillers"
# The steps a request can ask for, in order (at most ``MAX_STEPS``): a new design search, the
# current design under a change, units failing, designs set side by side, an answer.
STEP_KINDS = (
    "design",
    "what_if",
    "failure",
    "compare",
    "summary",
    "uncertainty",
    "report",
    "answer",
)
MAX_STEPS = 4


def _fact_keys() -> List[str]:
    """Return the values a question can ask for by name (``lookup.FACT_KEYS``)."""
    from gemini_agent import lookup

    return list(lookup.FACT_KEYS)


# What a reply needs (``read_needs``: its own short call; inside the long reading the model
# cut its JSON short and picked the third option for most messages, 3 Nov).
NEEDS = [
    "new_design_run",
    "about_one_existing_design",
    "designs_side_by_side",
    "how_the_design_was_found",
    "no_particular_design",
]
SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {},
                    "quote": {"type": "string"},
                },
                "required": ["key", "value", "quote"],
            },
        },
        "doublets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "depth_m": {"type": ["number", "null"]},
                    "injectors": {"type": "integer"},
                    "producer_open": {"type": "string", "enum": OPENINGS},
                    "injector_open": {"type": "string", "enum": OPENINGS},
                    "max_flow_m3h": {"type": ["number", "null"]},
                    "min_flow_m3h": {"type": ["number", "null"]},
                    "train": {"type": ["integer", "null"]},
                },
                "required": ["injectors"],
            },
        },
        "unsupported": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"what": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["what", "quote"],
            },
        },
        "failures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit": {"type": "string"},
                    "doublet": {"type": ["integer", "null"]},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "days": {"type": ["integer", "null"]},
                    "planned": {"type": "boolean"},
                    "quote": {"type": "string"},
                    "step": {"type": "integer"},
                },
                # Every field, so the dates and days land here and nowhere else.
                "required": ["unit", "doublet", "from", "to", "days", "planned", "quote", "step"],
            },
        },
        "designs": {"type": "array", "items": {"type": "string"}},
        # The values a question asks for by name (``lookup.FACT_KEYS``), code looks them up.
        "asks_for": {"type": "array", "items": {"type": "string", "enum": _fact_keys()}},
        # What the message states as given about the project or design ("since you used 3
        # doublets"): the answer checks each first.
        "premises": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        # The numbers whose origin the message asks for ("where does the 30 MW come from?"):
        # code finds which figure each is and how it was worked out (``provenance``).
        "origin_of": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        # Whether the message is about this project, energy or Dioscuri at all (2 Nov: "what's
        # the capital of Peru?" got the reservoir's temperature, a film was recommended).
        "on_topic": {"type": "boolean"},
        # No request, question or statement can be read from the message, even with the chat
        # (cut off, garbled, a bare number): nothing from it is applied, the user is asked.
        "unclear": {"type": "boolean"},
        # What the design should be best at, or null (``CATALOGUE["objective"]`` options).
        "objective": {
            "type": ["string", "null"],
            "enum": ["best", "cost", "co2", "reliable", "green_reliable", "gas_free", None],
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "do": {"type": "string", "enum": list(STEP_KINDS)},
                    "quote": {"type": "string"},
                    # The step's own changes (the same items as the top-level list).
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {},
                                "quote": {"type": "string"},
                            },
                            "required": ["key", "value", "quote"],
                        },
                    },
                },
                "required": ["do", "quote", "changes"],
            },
        },
    },
    "required": [
        "changes",
        "doublets",
        "unsupported",
        "failures",
        "designs",
        "asks_for",
        "premises",
        "origin_of",
        "on_topic",
        "unclear",
        "objective",
        "steps",
    ],
}
SCHEMA["properties"]["changes"]["items"]["properties"]["step"] = {"type": "integer"}


@dataclass
class Failure:
    """A unit out, as a message asks: on given days, for a number of days, or all year."""

    unit: str  # a plant outage unit: "doublet 1", "injector 2", "heat pump", "boiler" ...
    first: Optional[int] = None  # 0-based day of 2027; None: no dates said
    last: Optional[int] = None
    days: Optional[int] = None  # a duration without dates ("for two weeks")
    quote: str = ""
    step: int = 0
    assumed: str = ""  # what code chose that the message did not say ("doublet 1")
    planned: bool = False  # maintenance the user plans: the mildest days, not the worst

    @property
    def dated(self) -> bool:
        """Return True when the message gives the days."""
        return self.first is not None and self.last is not None


@dataclass
class Step:
    """One step of a request (``STEP_KINDS``)."""

    do: str
    quote: str = ""


@dataclass
class Reading:
    """What a message sets or changes, checked against the message and the catalogue."""

    changes: Dict[str, object] = field(default_factory=dict)
    doublets: List[DoubletSpec] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    dropped: List[str] = field(default_factory=list)
    # Changes the message asks for without saying how much ("a lower return"): key -> the
    # model's guess, which is never used as it is (the user is asked).
    vague: Dict[str, Tuple[float, str]] = field(default_factory=dict)
    # What the message asked that could not be used (its words, why): said in the reply, so a
    # result is never shown as if the change had been made.
    unread: List[Tuple[str, str]] = field(default_factory=list)
    # Changes refused because they cross their pair (a return across its supply): asked about.
    crossed: List[str] = field(default_factory=list)
    call: Optional[LLMCall] = None
    ok: bool = True
    failures: List[Failure] = field(default_factory=list)
    designs: List[str] = field(default_factory=list)  # names of designs to compare or show
    asks_for: List[str] = field(default_factory=list)  # values asked by name (lookup keys)
    premises: List[str] = field(default_factory=list)  # the message's words stated as given
    origin_of: List[float] = field(default_factory=list)  # numbers asked "where from?"
    on_topic: Optional[bool] = None  # about the project, energy or Dioscuri (None: not read)
    unclear: bool = False  # nothing in the message can be read as a request (``check``)
    show: List[str] = field(default_factory=list)  # cards asked for: "search", "comparison"
    about_design: Optional[bool] = None  # answering needs one particular design of the chat
    new_design: Optional[bool] = None  # asks for another or a new design run
    corrections: List[str] = field(default_factory=list)  # what code put right in the reading
    already: List[str] = field(default_factory=list)  # options asked for that are already so
    steps: List[Step] = field(default_factory=list)
    step_of: Dict[str, int] = field(default_factory=dict)  # change key -> its step
    # Every change with its step, in order: two what-ifs of one parameter keep both values.
    items: List[Tuple[str, object, int]] = field(default_factory=list)
    asked_steps: int = 0  # how many steps the message asked for (more than MAX_STEPS: said)
    quotes: Dict[str, str] = field(default_factory=dict)  # each kept change's quoted words
    # The second look (``second_look``): why the first reading was in doubt, the message's
    # amounts, which reading was kept; and the calls made after the first (``call``).
    second_look: Optional[dict] = None
    extra_calls: List[LLMCall] = field(default_factory=list)
    examples: int = 0  # worked examples in the prompt (``reading_examples``)
    # Words whose referent the message and the chat leave open ("run it again with 2"), with
    # the keys they may mean: asked about with choices (``clarify``, DIOSCURI_CLARIFY_CHOICES).
    # Words whose number or setting has no referent ("run it again with 2"), with what they
    # could be (``clarify``); ``unclear`` above is a message with no readable request at all.
    open_ref: Optional[dict] = None
    # The same item when the reading has no run step (a question, or a request that names no
    # change): kept for a run another route asks for (``agent._routed_design``), never acted on.
    open_unrun: Optional[dict] = None

    @property
    def empty(self) -> bool:
        """Return True when the message sets nothing (and asks for nothing unsupported)."""
        return (
            not self.changes
            and not self.doublets
            and not self.unsupported
            and not self.failures
            and len(self.designs) < 2
        )

    def changes_for(self, step: int) -> Dict[str, object]:
        """Return the changes of one step (all of them when the request has one step)."""
        if len(self.steps) <= 1:
            return dict(self.changes)
        if self.items:
            return {k: v for k, v, st in self.items if st == step}
        return {k: v for k, v in self.changes.items() if self.step_of.get(k, 0) == step}


def catalogue_text(now: Dict[str, object], keys: Optional[Sequence[str]] = None) -> str:
    """Return the catalogue as the prompt lists it, with each parameter's value now."""
    lines = []
    for key, p in CATALOGUE.items():
        if p.card_only or (keys is not None and key not in keys):
            continue
        if p.kind == "number":
            allowed = f"{p.low:g} to {p.high:g}"
        elif p.kind == "dates":
            allowed = "dates in words"
        elif p.kind == "records":
            from gemini_agent import aquifers

            allowed = aquifers.EDIT_WORDS
            value = now.get(key)
            shown = f"; now {aquifers.now_text(value)}" if value else ""
            lines.append(f"{key}: {p.label}; {allowed}{shown}")
            continue
        else:
            allowed = ", ".join(p.options) if p.options else f"{p.low:g} to {p.high:g}"
            if p.kind == "list":
                allowed = f"a list of: {allowed}" if p.options else f"a list, each {allowed}"
        value = now.get(key)
        shown = "" if value is None else f"; now {_shown(value)}"
        unit = f" [{p.unit}]" if p.unit else ""
        lines.append(f"{key}: {p.label}{unit}; {allowed}{shown}")
    return "\n".join(lines)


def _shown(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_shown(v) for v in value) + "]"
    return str(value)


# Dioscuri's own fine-tuned models (dioscuri-castor on the CPU, dioscuri-pollux on a GPU) have
# learnt the readings, so they get short instructions and the parameters as key=value (about
# 90 % fewer prompt tokens for the largest call). An experiment: the app ships the base models.
SHORT_PROMPT = "parameters_short_v1"
NEEDS_SHORT_PROMPT = "needs_short_v1"
# The models trained on the short prompts (rounds 1 and 2). A later one (dioscuri-pollux:r3) is
# trained on the app's full prompts, so any other dioscuri-* name reads with those.
# ``DIOSCURI_SHORT_PROMPTS=1`` (or 0) forces the short (or the full) prompts for every model.
SHORT_MODELS = frozenset(
    {
        "dioscuri-castor:latest",
        "dioscuri-pollux:latest",
        "dioscuri-castor:r2",
        "dioscuri-pollux:r2",
    }
)


def short_for(llm) -> bool:
    """Return True for the models trained on the short prompts, which read with them."""
    forced = os.environ.get("DIOSCURI_SHORT_PROMPTS", "").strip().lower()
    if forced in ("1", "true", "yes", "on", "short"):
        return True
    if forced in ("0", "false", "no", "off", "full"):
        return False
    name = str(getattr(llm, "model", "")).strip().lower()
    if name and ":" not in name:
        name += ":latest"  # Ollama's name for an untagged model
    return name in SHORT_MODELS


def catalogue_short(now: Dict[str, object]) -> str:
    """Return the parameters as ``key=value [unit]``, one a line (for the fine-tuned models)."""
    lines = []
    for key, p in CATALOGUE.items():
        if p.card_only:
            continue
        value = now.get(key)
        shown = "" if value is None else _shown(value)
        if p.kind == "records":
            from gemini_agent import aquifers

            shown = aquifers.now_text(value or [])
        unit = f" [{p.unit}]" if p.unit else ""
        lines.append(f"{key}={shown}{unit}")
    return "\n".join(lines)


def thread_block(thread: str) -> str:
    """Return the chat's thread as the readings show it before "Message:" ("" without one)."""
    return f"Conversation so far:\n{thread}\n\n" if thread else ""


def reading_messages(
    message: str,
    now: Dict[str, object],
    design: str = "",
    designs: str = "",
    short=False,
    thread: str = "",
    examples: Sequence[Tuple[str, str]] = (),
    notes: str = "",
) -> List[dict]:
    """Return the chat messages of the parameters reading (``short``: the fine-tuned form).

    ``thread``: the chat's thread (``thread.py``), a block before the message; without one the
    messages are exactly as before (the fine-tuned models learnt that form). ``examples``:
    worked readings of other messages (``reading_examples``, with ``DIOSCURI_EXAMPLES=1``);
    ``notes``: a second look's doubts and the message's amounts (``second_look``). Both go after
    the catalogue, so the prompt's long start stays the same from call to call.
    """
    from gemini_agent.answer import load
    from gemini_agent.reading_examples import block

    context = f"Current design: {design}" if design else "No design yet."
    if designs:
        context += f"\nDesigns so far:\n{designs}"
    from gemini_agent import clarify

    listed = catalogue_short(now) if short else catalogue_text(now)
    return [
        {
            "role": "system",
            "content": load(SHORT_PROMPT if short else PROMPT) + clarify.rule(short),
        },
        {
            "role": "user",
            "content": f"Parameters:\n{listed}\n\n{context}\n\n{block(examples)}"
            f"{thread_block(thread)}{notes}Message: {message}",
        },
    ]


def reading_schema() -> dict:
    """Return the reading's schema (with ``unclear`` when ``clarify`` is on)."""
    from gemini_agent import clarify

    return clarify.schema(SCHEMA)


def read(
    message: str,
    llm,
    now: Dict[str, object],
    design: str = "",
    designs: str = "",
    thread: str = "",
) -> Reading:
    """Ask the model what the message sets or changes; keep only what the message backs.

    Parameters
    ----------
    message : str
        The user's message.
    llm : OllamaLLM or ScriptedLLM
        The model that reads it (the reasoning model).
    now : dict
        Each parameter's value now (the current design's, or the project's).
    design : str
        The current design in a few words ("" when there is none).
    designs : str
        The conversation's designs and picks, one per line ("A1 1D-HP-EC-N1, best overall").
    thread : str
        The chat's thread: what "it", "the second one" or "and with 45 °C?" refers to. Code
        still keeps only changes the message's own words back.

    Returns
    -------
    Reading
        The checked changes, described doublets, failures, the designs named, the steps and
        unsupported asks, and what was dropped.
    """
    short = short_for(llm)
    examples = reading_examples.for_reading(
        message, lambda ex: reading_messages(message, now, design, designs, short, thread, ex), llm
    )
    msgs = reading_messages(message, now, design, designs, short, thread, examples)
    try:
        raw, call = llm.structured("parameters", msgs, reading_schema(), READING_TOKENS)
    except LLMError as err:
        return Reading(call=err.call, ok=False)
    out = check(raw, message, now, designed=bool(design), pairs=True)
    out.call = call
    out.examples = len(examples)
    if not second_look_on():
        return out

    def again(notes: str) -> Tuple[dict, LLMCall]:
        msgs = reading_messages(message, now, design, designs, short, thread, examples, notes)
        return llm.structured(SECOND_LOOK, msgs, reading_schema(), READING_TOKENS)

    return second_look(out, message, now, again, designed=bool(design))


# ------------------------------------------------------------------ the second look

# A reading in doubt is read once more, with the message's amounts beside it (4 Nov: a fine-tuned
# model read "Return temperature 50 C" as the supply and refused it, "a fifth more heat demand"
# as x1.5 and dropped it, and nothing at all from "En met gas op 4,5 ct/kWh?"). Code finds the
# amounts and the doubts; the model reads again, and decides what each amount is for. At most
# one more call a turn, and only in doubt; ``DIOSCURI_SECOND_LOOK=0`` turns it off.
SECOND_LOOK = "parameters_again"
READING_TOKENS = 900
# Drops that are code's own rulings on what the words are, not a value misread: not read again.
RULED = ("names a doublet", "is an efficiency", "which is not modelled", "already on those days")


class Doubt(NamedTuple):
    """Why a reading may have misread an amount: its key ("" for the whole reading), in words.

    ``kind``: "vague" (no amount read), "outside" (out of range), "crossed" (across its pair),
    "dropped" (another refusal), "unit" (an amount of another unit), "value" (another number),
    "nothing" (no change read).
    """

    key: str
    why: str
    kind: str


def second_look_on() -> bool:
    """Return True unless ``DIOSCURI_SECOND_LOOK`` turns the second look off."""
    return os.environ.get("DIOSCURI_SECOND_LOOK", "1").strip().lower() not in ("0", "false", "off")


def _accounted(q: "quantities.Quantity", reading: Reading) -> bool:
    """Return True when the reading uses an amount otherwise (a number asked "where from?")."""
    said = " ".join(reading.premises).lower()
    if q.text.lower() in said:
        return True
    return any(any(abs(n - x) < 1e-9 for n in q.numbers()) for x in reading.origin_of)


def doubts(
    reading: Reading,
    message: str,
    now: Optional[Dict[str, object]] = None,
    amounts: Optional[Sequence["quantities.Quantity"]] = None,
) -> List[Doubt]:
    """Return why a checked reading may have misread the message's amounts.

    Code only compares units and numbers: a value asked for without an amount while the message
    gives one of the key's unit; a value refused (out of range, its number not in the quote,
    the quote not in the message, or across its pair when the message gave only one of the
    two) while the message has an amount of the key's unit; a kept value whose quote gives an
    amount of another unit, or of the unit but another number; and no change at all while the
    message gives a usable amount. Two values of a pair that the message gives across each
    other ("cooling 18/12") are the user's own: asked about, not read again.

    Parameters
    ----------
    reading : Reading
        The checked reading (``check``).
    message : str
        The user's message.
    now : dict, optional
        Each parameter's value now ("10 K lower" is worked out from it).
    amounts : list of Quantity, optional
        The message's usable amounts (``quantities.candidates``), when already found.

    Returns
    -------
    list of Doubt
        Each doubt's key, words and kind.
    """
    now = now or {}
    amounts = list(quantities.candidates(message, now) if amounts is None else amounts)
    amounts = [q for q in amounts if not _accounted(q, reading)]
    both = {k for pair in CROSSED for k in pair[:2] if set(pair[:2]) <= set(reading.crossed)}
    out: List[Doubt] = []
    for key, (guess, quote) in reading.vague.items():
        fit = [q for q in amounts if quantities.compatible(q, key)]
        if fit:
            said = ", ".join(f"“{q.text}”" for q in fit)
            out.append(
                Doubt(key, f"{key}={guess:g} was dropped as {VAGUE}, but it has {said}", "vague")
            )
    for item in reading.dropped:
        m = re.match(r"^(\w+)=(.+?): (.+)$", str(item))
        if m is None or m.group(1) not in CATALOGUE or m.group(1) in both:
            continue
        key, value, why = m.groups()
        if why == VAGUE or any(r in why for r in RULED) or not quantities.key_dimension(key):
            continue
        if any(quantities.compatible(q, key) for q in amounts):
            kind = "crossed" if key in reading.crossed else "dropped"
            kind = "outside" if why.startswith("outside") else kind
            out.append(Doubt(key, f"{key}={value} was not taken: {why}", kind))
    for key, value in reading.changes.items():
        if not quantities.key_dimension(key):
            continue
        values = value if isinstance(value, list) else [value]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            continue
        said = [q for q in quantities.extract(reading.quotes.get(key, "")) if q.clear]
        if not said:
            continue  # a bare number ("set the cap to 250"): nothing to compare
        fit = [q for q in said if quantities.compatible(q, key)]
        p = CATALOGUE[key]
        shown = f"{key}={_shown(value)}"
        if not fit:
            what = f"“{said[0].text}” is {quantities.shown(said[0])}"
            out.append(Doubt(key, f"{shown}, but {what}, not a value in {p.unit}", "unit"))
            continue
        given = quantities.supported(reading.quotes[key], key, now.get(key), fit)
        if given and not all(quantities.matches(v, given, key) for v in values):
            gives = " or ".join(f"{x:g}" for x in given[:4])
            out.append(
                Doubt(key, f"{shown}, but its quote's amounts give {gives} {p.unit}", "value")
            )
    busy = reading.changes or reading.doublets or reading.failures or reading.crossed
    if reading.ok and reading.on_topic is not False and not busy and not out and amounts:
        out.append(Doubt("", "no change was read, but the message gives an amount", "nothing"))
    return out


def notes_block(amounts: Sequence["quantities.Quantity"], why: Sequence[Doubt]) -> str:
    """Return a second look's block: the first reading's doubts and the message's amounts."""
    lines = ["A second look. The first reading of this message was in doubt:"]
    lines += [f"- {d.why}" for d in why]
    if amounts:
        lines.append(
            "Amounts in the message, as written and in the parameters' units (code read the "
            "numbers and units only; which parameter each is for, if any, is yours to read):"
        )
        lines += [f"- “{q.text}”: {quantities.shown(q)}" for q in amounts]
    lines.append(
        "Read the message again and give the whole reading. Set only what the message asks; "
        "an amount can also be a question's or a premise's, not a change. If the first "
        "reading was what the message says, give it again: a value code cannot use is asked "
        "about, never run."
    )
    return "\n".join(lines) + "\n\n"


def _better(first: Reading, again: Reading, why, left) -> bool:
    """Return True when the second reading is to be kept: valid, fewer doubts, nothing lost.

    Nothing lost: every change the first kept and did not doubt is kept with the same value,
    and no failure or described doublet goes. A value refused as out of range is kept only
    corrected on its own key.
    """
    if not again.ok or len(left) >= len(why):
        return False
    doubted = {d.key for d in why}
    if any(d.kind == "outside" and d.key not in again.changes for d in why):
        # A value out of its range is refused for the key its words name; another key that
        # happens to take the number is not a correction (a 105 °C return is not a supply).
        return False
    for key, value in first.changes.items():
        if key not in doubted and not _same(again.changes.get(key), value):
            return False
    if len(again.failures) < len(first.failures) or len(again.doublets) < len(first.doublets):
        return False
    return bool(again.changes or again.doublets or again.failures or not first.changes)


def second_look(
    first: Reading,
    message: str,
    now: Optional[Dict[str, object]],
    again: Callable[[str], Tuple[dict, LLMCall]],
    designed: bool = False,
) -> Reading:
    """Read a doubtful reading once more with the message's amounts; keep it if code accepts it.

    Parameters
    ----------
    first : Reading
        The checked first reading.
    message : str
        The user's message.
    now : dict
        Each parameter's value now.
    again : callable
        ``again(notes) -> (raw, call)``: the reading's call with the notes before the message.
    designed : bool
        A design exists (a change is then a what-if).

    Returns
    -------
    Reading
        The second reading when it is valid, has fewer doubts and loses nothing the first had
        right; else the first. Either way ``second_look`` records why, the amounts and which
        was kept, and ``extra_calls`` the second call.
    """
    now = now or {}
    amounts = quantities.candidates(message, now)
    why = doubts(first, message, now, amounts)
    if not why:
        return first
    record = {
        "why": [d.why for d in why],
        "amounts": [q.as_dict() for q in amounts],
        "first": {"changes": dict(first.changes), "dropped": list(first.dropped)},
    }
    try:
        raw, call = again(notes_block(amounts, why))
    except LLMError as err:
        record.update(kept="first", error=str(err))
        first.second_look = record
        if err.call is not None:
            first.extra_calls.append(err.call)
        return first
    second = check(raw, message, now, designed=designed, pairs=True)
    left = doubts(second, message, now, amounts)
    keep = _better(first, second, why, left)
    record.update(
        kept="second" if keep else "first",
        second={"changes": dict(second.changes), "dropped": list(second.dropped)},
        doubts_after=[d.why for d in left],
    )
    if not keep:
        first.second_look = record
        first.extra_calls.append(call)
        return first
    second.call, second.examples = first.call, first.examples
    second.extra_calls = list(first.extra_calls) + [call]
    second.second_look = record
    second.corrections = list(first.corrections) + ["read again with the message's amounts"]
    return second


def check(
    raw: dict,
    message: str,
    now: Optional[Dict[str, object]] = None,
    designed: bool = False,
    pairs: bool = False,
) -> Reading:
    """Keep the model's changes the message backs: known key, in range, quoted, its number.

    Parameters
    ----------
    raw : dict
        The model's JSON (``changes``, ``doublets``, ``unsupported``).
    message : str
        The user's message.
    now : dict, optional
        Each parameter's value now (a change to the same value is not a change).
    pairs : bool, optional
        Refuse a change that crosses its pair (``CROSSED``: a return across its supply). The
        chat's readings do; the inputs card checks one value at a time and its pairs together
        (``card_edits``), so it does not.

    Returns
    -------
    Reading
        What passed, and one line per dropped item.
    """
    now = now or {}
    out = Reading()
    text = _norm(message)
    raw = _gather(raw)
    quotes: Dict[str, str] = {}  # each change's words, for a cross-check's "not applied"
    raw["changes"] = _one_list(raw.get("changes") or [], text)
    now_rules = now.get("_rules")  # the rules the aquifers now are worked out with
    if now_rules is None:
        from dioscuri_plant import Rules

        now_rules = Rules()
    for item in raw.get("changes") or []:
        if not isinstance(item, dict):
            continue
        key, value, quote = str(item.get("key", "")), item.get("value"), str(item.get("quote", ""))
        p = CATALOGUE.get(key)
        if p is None:
            # A key one or two letters off is the model's slip ("second_aquiper_permeability_md",
            # 3 Nov), not another parameter.
            near = difflib.get_close_matches(key, list(CATALOGUE), n=1, cutoff=0.92)
            if near:
                out.corrections.append(f"{key}: read as {near[0]}")
                key, p = near[0], CATALOGUE[near[0]]
        if p is None and key in STEP_KINDS:
            continue  # a step written as a change ("design"): the steps say it, nothing unread
        if p is None:
            out.dropped.append(f"{key}: not a parameter")
            continue
        if not quote.strip() or not _quoted(quote, text):
            out.dropped.append(f"{key}={value}: the quote is not in the message")
            continue
        if p.kind == "records":
            from gemini_agent import aquifers

            records, why = aquifers.from_reading(value, message, now.get(key) or [], now_rules)
            if records is None:
                out.dropped.append(f"{key}: {why}")
                out.unread.append((quote.strip(), why))
                continue
            if aquifers.same(records, now.get(key) or []):
                continue  # the aquifers there are
            out.changes[key] = records
            out.step_of[key] = _step(item.get("step"))
            out.items.append((key, records, out.step_of[key]))
            continue
        if p.kind == "dates":
            stops, why = stop_dates(quote, message, now)
            if not stops:
                out.dropped.append(f"{key}={value}: {why}")
                out.unread.append((quote.strip(), why))
                continue
            current = now.get("stop_ranges")
            if current and [list(map(list, d)) for d in stops] == [
                [list(r) for r in d] for d in current[: len(stops)]
            ]:
                # The stop where it already is (2 Nov: "“stopping 9 Jul to 12 Aug”, why then?"
                # quoted the reply and ran a what-if that changed nothing).
                out.dropped.append(f"{key}: the stop is already on those days")
                continue
            out.changes[key] = stops
            out.step_of[key] = _step(item.get("step"))
            out.items.append((key, stops, out.step_of[key]))
            continue
        priced = per_mwh(quote) if p.unit == "EUR/MWh" else None
        if priced is not None and p.low <= priced <= p.high:
            # A price in its own unit ("4,5 ct/kWh", "€0.04 per kWh") is converted by code:
            # the model gave 54 and 160 for those on 2 Nov.
            if not isinstance(value, (int, float)) or abs(float(value) - priced) > 1e-6:
                out.corrections.append(f"{key}: read “{quote.strip()}” as {priced:g} €/MWh")
            value = priced
        good, why = _valid(p, value, quote, now.get(key))
        if key in SWITCHES and str(value) in ("0", "1", "0.0", "1.0", "True", "False"):
            # A switch is said in words ("with a yearly service stop for each unit"), never as
            # the number 1 (1 Nov: "switch on … a yearly service stop" was dropped).
            good, why, value = True, "", float(str(value) in ("1", "1.0", "True"))
        elif key in NEEDS_AMOUNT and isinstance(value, (int, float)):
            # "Switch on the network losses": how long is it? A length the words do not give
            # (0, or the model's 50 km on 1 Nov) is asked for, never run.
            if not _backed([float(value)], quote):
                good, why = False, VAGUE
        if not good:
            out.dropped.append(f"{key}={value}: {why}")
            guess = value if isinstance(value, (int, float)) else now.get(key)
            if why == VAGUE and isinstance(guess, (int, float)):
                out.vague[key] = (float(guess), quote)
            elif why.startswith("outside"):
                out.unread.append((quote.strip(), f"{p.label.lower()} {why}"))
            elif why.startswith("its number") and isinstance(value, (int, float)):
                # Said, never silently dropped: the reading's number does not follow from the words.
                out.unread.append(
                    (quote.strip(), f"I read {p.label.lower()} {value:g} but cannot match it to it")
                )
            continue
        value = _clean(p, value)
        if key in SIZE_KEYS and re.search(r"\bCOP\b|\bEER\b|efficien", quote, re.I):
            out.dropped.append(f"{key}={value}: '{quote}' is an efficiency, not a size")
            out.unsupported.append("a fixed heat pump or chiller COP")
            continue
        if key == "n_doublets" and re.search(r"\b(doublet|dublette|put)\s*\d\b", quote, re.I):
            out.dropped.append(f"{key}={value}: '{quote}' names a doublet, it is not a count")
            continue
        if key in now and _same(now[key], value):
            if key in ALREADY_KEYS and value and key not in out.already:
                out.already.append(key)  # "would free cooling help?" when the design has it
            continue  # asks for what is already so
        out.changes[key] = value
        out.step_of[key] = _step(item.get("step"))
        out.items.append((key, value, out.step_of[key]))
        quotes[key] = quote.strip()
    if pairs:
        _crossed(out, now, quotes)
    out.quotes = {k: q for k, q in quotes.items() if k in out.changes}
    for d in raw.get("doublets") or []:
        if not isinstance(d, dict):
            continue
        depth = _depth(d.get("depth_m"))
        if depth is not None and not _backed([depth], message):
            out.dropped.append(f"doublet at {depth:g} m: the depth is not in the message")
            depth = None
        try:
            spec = DoubletSpec(
                depth_m=depth,
                producer_open=d.get("producer_open") or "full",
                injector_open=d.get("injector_open") or "full",
                injectors=2 if int(d.get("injectors") or 1) >= 2 else 1,
                max_flow_m3h=_flow(d.get("max_flow_m3h"), message),
                min_flow_m3h=_flow(d.get("min_flow_m3h"), message),
                train=d.get("train"),
            )
        except (ValueError, TypeError) as err:
            out.dropped.append(f"doublet {d}: {err}")
            continue
        out.doublets.append(spec)
    if len(out.doublets) > 3 or (out.doublets and not _describes_doublets(message)):
        out.dropped.append("doublets: the message does not describe doublets one by one")
        out.doublets = []
    if out.doublets and all(_plain(d) for d in out.doublets):
        out.changes.setdefault("n_doublets", len(out.doublets))
        out.doublets = []  # nothing set apart: a doublet count
    covered = bool(out.doublets or out.changes)
    for item in raw.get("unsupported") or []:
        if not (isinstance(item, dict) and item.get("what")):
            continue
        what, quote = str(item["what"]).strip(), str(item.get("quote", ""))
        if _norm(quote) not in text:
            continue
        if covered and BUILD_WORDS.search(what):
            # "its own separator", "a single producer": the doublets or the changes cover it.
            out.dropped.append(f"unsupported '{what}': covered by the doublets or the changes")
            continue
        if MODELLED.search(what) and not FOREIGN.search(what):
            # "size an absorption chiller": a unit the model sizes is not unsupported (1 Nov: it
            # was answered "I cannot size an absorption chiller").
            out.dropped.append(f"unsupported '{what}': a unit the model has")
            continue
        out.unsupported.append(what)
        # A change quoted from the unsupported thing's own words is a misreading of it ("add a
        # 5 MW solar PV park to run the heat pump" read as a 5 MW heat pump, 1 Nov).
        words = [w for w in re.findall(r"[a-zà-ÿ]{4,}", _norm(what))]
        if words:
            for key, value, k in list(out.items):
                q = _norm(
                    next(
                        (
                            str(c.get("quote", ""))
                            for c in raw.get("changes") or []
                            if isinstance(c, dict) and c.get("key") == key
                        ),
                        "",
                    )
                )
                if q and all(w in q for w in words):
                    out.changes.pop(key, None)
                    out.items.remove((key, value, k))
                    out.dropped.append(f"{key}={value}: read from '{what}', which is not modelled")
    for item in raw.get("failures") or []:
        failure = _failure(item, message, out)
        if failure is not None:
            out.failures.append(failure)
    # Names the message uses, or ids of the designs listed to the model ("A9" for "the
    # cheapest"); the agent resolves them against the conversation, and drops what is not there.
    out.designs = [str(d).strip() for d in raw.get("designs") or [] if str(d).strip()][:4]
    keys = set(_fact_keys())
    out.asks_for = [str(k) for k in raw.get("asks_for") or [] if str(k) in keys]
    if len(out.asks_for) > 3:
        # A long list is the model listing what exists, not what was asked: keep the values
        # the message itself names (S28 got eight keys for "which return did you assume?").
        from gemini_agent import lookup

        out.asks_for = [k for k in out.asks_for if lookup.ALIASES[k].search(message)]
    out.asks_for = out.asks_for[:6]
    # Only words the message has: a premise the model made up is not checked.
    said = _norm(message)
    for quote in raw.get("premises") or []:
        words = re.findall(r"[a-zà-ÿ0-9]{3,}", _norm(str(quote)))
        if words and sum(w in said for w in words) >= 0.8 * len(words):
            out.premises.append(str(quote).strip()[:160])
    out.premises = out.premises[:3]
    # Only numbers the message has: the model's own figures are not asked about.
    from gemini_agent.intake import numbers_in

    given = numbers_in(message)
    for item in raw.get("origin_of") or []:
        # "N-1" names the reliability rule, not a number to explain.
        for x in numbers_in(re.sub(r"\bN-1\b", "", str(item), flags=re.I)):
            if any(abs(x - g) < 1e-9 for g in given) and x not in out.origin_of:
                out.origin_of.append(x)
    out.origin_of = out.origin_of[:3]
    if isinstance(raw.get("on_topic"), bool):
        out.on_topic = raw["on_topic"]
    needs = raw.get("needs")
    if needs in NEEDS:  # set by ``read_needs`` (its own call), merged in by the agent
        set_needs(out, needs)
    for item in raw.get("steps") or []:
        if isinstance(item, dict) and item.get("do") in STEP_KINDS:
            out.steps.append(Step(str(item["do"]), str(item.get("quote") or "")))
    # What the design should be best at: its own field, always given (null when not said). As
    # an optional change it was skipped: "the cheapest plant you can find" ran as best overall.
    goal = raw.get("objective")
    floor = CO2_FLOOR.search(message)
    if goal == "co2" and floor and "min_co2_saving" not in out.changes:
        # "At least 50 % less CO2 than gas" is a floor, not "the lowest CO2" (1 Nov: read as
        # the greenest design, which then cost 87.6 €/MWh). The number is the message's own.
        pct = float(floor.group(1).replace(",", "."))
        if 0 < pct < 100:
            goal = None
            out.changes["min_co2_saving"] = pct / 100
            out.step_of["min_co2_saving"] = 0
            out.items.append(("min_co2_saving", pct / 100, 0))
    searches = [k for k, s in enumerate(out.steps) if s.do in ("design", "what_if")]
    if goal in CATALOGUE["objective"].options and "objective" not in out.changes:
        if not designed or searches:
            k = searches[0] if searches else 0
            out.changes["objective"] = goal
            out.step_of["objective"] = k
            out.items.append(("objective", goal, k))
    if not out.steps and (out.changes or out.doublets):
        # Changes and no step: a what-if of the design there is, else a design with them.
        out.steps.append(Step("what_if" if designed else "design"))
    out.steps = _fit_steps(out, designed)
    if raw.get("unclear") is True:
        _set_unclear(out)
    else:
        from gemini_agent import clarify

        out.open_ref = clarify.read_unclear(raw, message, out)
    return out


def _set_unclear(out: "Reading") -> None:
    """Empty a reading the model found unreadable: nothing from that message is applied.

    "hmm 70" after a design ran a what-if with a 70 MWh store on 4 Nov: a number with no words
    for what it sets is no change. What was read goes to ``dropped``, so the trace shows it.
    """
    out.unclear = True
    gone = [f"{k}={v}" for k, v in out.changes.items()] + [f"{k} (no amount)" for k in out.vague]
    gone += [f"unsupported '{u}'" for u in out.unsupported]
    gone += [f"failure of the {f.unit}" for f in out.failures]
    gone += [f"{len(out.doublets)} doublet(s) described"] if out.doublets else []
    out.dropped += [f"{g}: the message has no readable request" for g in gone]
    out.changes, out.doublets, out.failures, out.vague, out.unsupported = {}, [], [], {}, []
    out.items, out.step_of, out.quotes, out.unread, out.crossed = [], {}, {}, [], []
    out.steps, out.premises, out.origin_of, out.designs, out.asks_for = [], [], [], [], []
    out.already = []


# Values that must stay on one side of another: (lower, higher, why when crossed). A cooling
# network takes heat from the buildings, so its water comes back warmer than it went out; a
# heating network's comes back colder. On 3 Nov "what if the cooling return is 16 °C?" ran a
# year with the return below the 20 °C supply and reported its cost as if it could be built.
CROSSED = (
    ("cool_supply_c", "cool_return_c", "the cooling return must be warmer than its supply"),
    ("heat_return_c", "heat_supply_c", "the heating return must be colder than its supply"),
    ("flow_min_m3h", "flow_max_m3h", "the lowest flow must stay below the flow cap"),
)


def _crossed(out: "Reading", now: Dict[str, object], quotes: Dict[str, str]) -> None:
    """Drop a change that puts a value on the wrong side of its pair, and say why.

    The pair's other value is the message's own change, else the value now. The change is
    not run (``unread``: the reply says it was not applied, and why), so no result is shown
    for a network that cannot exist.
    """
    for low, high, why in CROSSED:
        if low not in out.changes and high not in out.changes:
            continue
        a, b = out.changes.get(low, now.get(low)), out.changes.get(high, now.get(high))
        try:
            crossed = float(a) >= float(b)
        except (TypeError, ValueError):
            continue
        if not crossed:
            continue
        for key in (k for k in (low, high) if k in out.changes):
            other = high if key == low else low
            value = out.changes.pop(key)
            out.step_of.pop(key, None)
            out.items = [i for i in out.items if i[0] != key]
            p, q = CATALOGUE[key], CATALOGUE[other]
            there = b if key == low else a
            out.dropped.append(f"{key}={value}: {why}")
            out.crossed.append(key)
            out.unread.append(
                (
                    quotes.get(key) or f"{p.label.lower()} {value:g} {p.unit}",
                    f"{why} ({q.label.lower()} {float(there):g} {q.unit}); which value did "
                    "you mean?",
                )
            )


def _quoted(quote: str, text: str) -> bool:
    """Return True when the quote is in the (normalised) message, allowing a few typos fixed.

    The model may quote "temperature" for the user's "temprature": a stretch of the message
    nine-tenths alike counts (difflib), never a quote of other words.
    """
    q = _norm(quote)
    if not q:
        return False
    if q in text:
        return True
    n = len(q)
    for size in (n - 2, n - 1, n, n + 1, n + 2):
        if size < 6:
            continue
        for start in range(0, max(1, len(text) - size + 1)):
            if difflib.SequenceMatcher(None, q, text[start : start + size]).ratio() >= 0.9:
                return True
    return False


def _gather(raw: dict) -> dict:
    """Return the reading with each step's own changes and stray failures where code reads them.

    The model often puts a step's values under the step (``steps[i].changes``) and a failure's
    dates under a ``failures`` item of ``changes``: both are moved to the lists ``check`` reads,
    each change marked with its step.
    """
    raw = dict(raw)
    changes = [c for c in raw.get("changes") or [] if isinstance(c, dict)]
    failures = [f for f in raw.get("failures") or [] if isinstance(f, dict)]
    stray = []
    for c in list(changes):
        if c.get("key") == "failures" and isinstance(c.get("value"), list):
            stray += [f for f in c["value"] if isinstance(f, dict)]
            changes.remove(c)
    for f in stray:  # the richer item wins: it carries the dates or the days
        same = next((g for g in failures if str(g.get("unit")) == str(f.get("unit"))), None)
        if same is None:
            failures.append(f)
        else:
            for k in ("from", "to", "days", "doublet", "planned"):
                if not same.get(k) and f.get(k):
                    same[k] = f[k]
    seen = {(str(c.get("key")), str(c.get("value"))) for c in changes}
    for i, st in enumerate(raw.get("steps") or []):
        if not isinstance(st, dict):
            continue
        for c in st.get("changes") or []:
            if not isinstance(c, dict):
                continue
            key = (str(c.get("key")), str(c.get("value")))
            if key in seen:
                for d in changes:  # the step says which step it belongs to
                    if (str(d.get("key")), str(d.get("value"))) == key:
                        d.setdefault("step", i)
                continue
            seen.add(key)
            changes.append(dict(c, step=i))
    raw["changes"], raw["failures"] = changes, failures
    return raw


def _one_list(changes: List[dict], text: str) -> List[dict]:
    """Return the changes with a records parameter's items of one step joined into one list.

    The edits of the aquifers are one list, but the model may write them as several items of
    the same key (an aquifer added in one, the assumed ones dropped in the next): read apart,
    each was applied to the list as it is now and the request split into one design each.
    """
    out: List[dict] = []
    joined: Dict[Tuple[str, int], dict] = {}
    for c in changes:
        key = str(c.get("key", ""))
        p = CATALOGUE.get(key)
        if p is None or p.kind != "records":
            out.append(c)
            continue
        value = c.get("value")
        edits = [e for e in (value if isinstance(value, list) else [value]) if e is not None]
        at = (key, _step(c.get("step")))
        if at not in joined:
            joined[at] = dict(c, value=list(edits))
            out.append(joined[at])
            continue
        item = joined[at]
        item["value"] = item["value"] + edits
        if not _quoted(str(item.get("quote", "")), text) and _quoted(str(c.get("quote", "")), text):
            item["quote"] = c.get("quote")
    return out


def _step(value) -> int:
    try:
        return max(0, min(int(value), MAX_STEPS - 1))
    except (TypeError, ValueError):
        return 0


def _drop_steps(out: "Reading", drop: List[int]) -> None:
    """Remove steps by position, renumbering the changes' and failures' steps after them."""
    keep = [i for i in range(len(out.steps)) if i not in drop]
    new = {old: k for k, old in enumerate(keep)}
    out.steps = [out.steps[i] for i in keep]
    out.items = [(k, v, new.get(s, max(0, s - sum(d < s for d in drop)))) for k, v, s in out.items]
    out.step_of = {
        k: new.get(s, max(0, s - sum(d < s for d in drop))) for k, s in out.step_of.items()
    }
    for f in out.failures:
        f.step = new.get(f.step, max(0, f.step - sum(d < f.step for d in drop)))


def _fit_steps(out: "Reading", designed: bool = False) -> List[Step]:
    """Return the request's steps, at most ``MAX_STEPS``, consistent with what was read.

    A failure read without a failure step gets one; designs to compare without a compare step
    get one; the model's order is kept, repeats of the same kind next to each other merged.
    """
    # Two what-ifs of one parameter in one step ("50 °C, and what if it were 45 °C?"): two steps.
    by_step: Dict[int, List[Tuple[str, object, int]]] = {}
    for key, value, st in out.items:
        by_step.setdefault(st, []).append((key, value, st))
    for st, group in sorted(by_step.items()):
        keys = [k for k, _, _ in group]
        if len(keys) != len(set(keys)) and 0 <= st < len(out.steps):
            seen: Dict[str, int] = {}
            extra = 0
            for i, (key, value, _) in enumerate(group):
                seen[key] = seen.get(key, 0) + 1
                if seen[key] > 1:
                    extra = max(extra, seen[key] - 1)
            for _ in range(extra):
                out.steps.insert(st + 1, Step(out.steps[st].do, out.steps[st].quote))
            count: Dict[str, int] = {}
            renumbered = []
            for key, value, s in out.items:
                if s == st:
                    count[key] = count.get(key, 0) + 1
                    renumbered.append((key, value, st + count[key] - 1))
                elif s > st:
                    renumbered.append((key, value, s + extra))
                else:
                    renumbered.append((key, value, s))
            out.items = renumbered
            break
    # A what-if step with no change, next to a failure: the model's echo of the failure.
    if any(s.do == "failure" for s in out.steps) or out.failures:
        empty = [
            i
            for i, s in enumerate(out.steps)
            if s.do == "what_if" and not any(st == i for _, _, st in out.items)
        ]
        if empty:
            _drop_steps(out, empty)
    # With a design there, a "design" step that only changes conditions is a what-if of it (the
    # what-if also searches again, so nothing is lost).
    if designed and [s.do for s in out.steps] == ["design"] and out.items:
        if all(CATALOGUE[k].target not in ("search",) for k, _, _ in out.items):
            out.steps = [Step("what_if", out.steps[0].quote)]
    out.asked_steps = len(out.steps)
    steps: List[Step] = list(out.steps)  # same kinds next to each other stay apart: two scenarios
    if out.failures and "failure" not in {s.do for s in steps}:
        steps.append(Step("failure"))
    kinds = {s.do for s in steps}
    if not kinds & {"compare", "failure"}:
        out.designs = []  # designs to compare or to fail (the model also lists the one in hand)
    if "failure" not in {s.do for s in steps}:
        out.failures = []  # failures only with a failure step
    steps = steps[:MAX_STEPS]
    kinds = [s.do for s in steps]
    if "design" in kinds and "what_if" in kinds:
        # "Design it, then check it 10 °C colder": a what-if step with none of the changes gets
        # the conditions (the design step keeps the search's options: doublets, objective ...).
        d, w = kinds.index("design"), kinds.index("what_if")
        if d < w and w not in out.step_of.values():
            for key in out.changes:
                if CATALOGUE[key].target != "search":
                    out.step_of[key] = w
            out.items = [
                (k, v, w if CATALOGUE[k].target != "search" and s == d else s)
                for k, v, s in out.items
            ]
    return steps


# A duration in English, Dutch or German: "for two weeks", "drie dagen", "zwei Wochen".
DURATION = re.compile(
    r"\b(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|een|twee|drie|vier|"
    r"vijf|zes|zeven|acht|negen|tien|ein|eine|einen|zwei|drei|f[üu]nf|sechs|sieben|neun|zehn)"
    r"\s*(days?|weeks?|months?|fortnight|dag|dagen|weken|week|maand|maanden|tage?n?|wochen?|"
    r"monate?n?)\b",
    re.I,
)
COUNTS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "een": 1, "twee": 2, "drie": 3, "vier": 4,
    "vijf": 5, "zes": 6, "zeven": 7, "acht": 8, "negen": 9, "tien": 10, "ein": 1, "eine": 1,
    "einen": 1, "zwei": 2, "drei": 3, "fünf": 5, "funf": 5, "sechs": 6, "sieben": 7, "neun": 9,
    "zehn": 10,
}  # fmt: skip
UNIT_DAYS = {"d": 1, "t": 1, "w": 7, "m": 30, "f": 14}  # day/dag/Tag, week/Woche, month, fortnight


def failure_unit(word: str, doublet: Optional[int], n_doublets: int = 3) -> Tuple[str, str]:
    """Return the plant outage unit a failure names, and what was assumed ("" when nothing).

    "the ESP", "a production pump", "the producer of doublet 2", "a well" are the doublet (its
    producer); "an injector" one injector; "the separator", "the filters" its treatment train;
    the heat exchanger, the heat pump, the boiler, the chillers, the absorption chiller.
    """
    w = re.sub(r"[_-]+", " ", word.lower())
    k = doublet if isinstance(doublet, int) and doublet >= 1 else None
    digits = re.findall(r"\d", w)
    if k is None and digits:
        k = int(digits[0])
    assumed = ""
    if any(x in w for x in ("injector", "injection")):
        kind = "injector"
    elif any(x in w for x in ("train", "separator", "filter", "degass", "treatment")):
        kind = "train"
    elif "exchanger" in w or re.search(r"\bhex\b", w):
        return "heat exchanger", ""
    elif "heat pump" in w or "heatpump" in w or "warmtepomp" in w:
        return "heat pump", ""
    elif "boiler" in w or "ketel" in w:
        return ("boiler unit" if "unit" in w else "boiler"), ""
    elif "absorption" in w:
        return "absorption", ""
    elif "chiller" in w or "koelmachine" in w:
        return ("chiller unit" if "unit" in w else "chillers"), ""
    elif any(x in w for x in ("esp", "pump", "producer", "production", "doublet", "well", "put")):
        kind = "doublet"
    else:
        return "", ""
    if k is None:
        k = 1
        if n_doublets > 1:
            assumed = f"{kind} 1 (the message does not say which)"
    return f"{kind} {k}", assumed


def _failure(item: object, message: str, out: "Reading") -> Optional[Failure]:
    """Check one failure the model read: its quote, its unit, its days from the quote."""
    from gemini_agent.answer import named_days

    if not isinstance(item, dict):
        return None
    quote = str(item.get("quote") or "")
    pieces = [x for x in re.split(r"\.\.\.|…", quote) if x.strip()]  # "the boiler ... trips"
    if not pieces or any(_norm(x) not in _norm(message) for x in pieces):
        out.dropped.append(f"failure {item.get('unit')}: the quote is not in the message")
        return None
    quote = " … ".join(x.strip() for x in pieces)
    doublet = item.get("doublet")
    said = re.search(r"\b(?:doublet|producer|injector|train|esp)\s*(\d)\b", quote, re.I)
    if not isinstance(doublet, int) and said:
        doublet = int(said.group(1))  # "the ESP of doublet 1": the number is in the quote
    word = str(item.get("unit") or "")
    if re.search(r"\b(one|a single|1|een|eine?)\b[^.]*\bunits?\b", quote, re.I):
        word += " unit"  # "one boiler unit": a unit of a plant built as several
    unit, assumed = failure_unit(word, doublet)
    if not unit:
        out.unsupported.append(f"{item.get('unit')} failing")
        return None
    days, months = named_days(quote, limit=366)
    if not days and not months:  # the dates may sit elsewhere in the message
        days, months = named_days(message, limit=366)
    first = last = None
    said = _model_days(item.get("from"), item.get("to"))
    named_months = set(months) | {_month_of(d) for d in days}
    backed = said and {_day_of_month(said[0]), _day_of_month(said[1])} <= set(_numbers(message))
    span = (said[1] - said[0] + 1) if said else 0
    asked = _duration(quote) or _duration(message)
    # A length the message gives, laid by the model on days the message does not name: the
    # length counts, the days are code's ("three weeks in January"; never "the first week").
    guessed = bool(said and not backed and not days and months and asked and span == asked)
    if guessed:
        # "Three weeks in January": the model's own pick of days in a named month; code takes
        # the worst (or mildest, planned) start in that month instead.
        said = None
        item = dict(item, days=item.get("days") or span)
    if said and ({_month_of(said[0]), _month_of(said[1])} <= named_months or backed):
        # "the first week of February": the model's days in a month the message names; or its
        # dates whose day numbers the message gives (a month in a language not parsed here).
        first, last = said
    elif days:
        first, last = min(days), max(days)
    elif months:
        first = sum(MONTH_DAYS[: min(months)])
        last = sum(MONTH_DAYS[: max(months) + 1]) - 1
    length = _duration(quote) or _duration(message)
    if first is not None and len(days) == 1 and not months and length:
        last = min(first + length - 1, 364)  # "from 10 January for two weeks"
    duration = None if first is not None else length
    if first is None and duration is None and isinstance(item.get("days"), int):
        if 1 <= item["days"] <= 31:  # "the coldest week": the worst days are found and said
            duration = int(item["days"])
    if first is not None and months and not days and length and length < last - first + 1:
        duration = length  # "for three weeks in January": the worst start within the month
    if first is None and isinstance(item.get("days"), int) and duration is None:
        out.dropped.append(f"failure {unit}: {item['days']} days is not a duration it can use")
    return Failure(
        unit,
        first,
        last,
        duration,
        quote.strip(),
        _step(item.get("step")),
        assumed,
        bool(item.get("planned")),
    )


MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)  # 2027


def _day_of_month(day: int) -> float:
    m = _month_of(day)
    return float(day - sum(MONTH_DAYS[:m]) + 1)


def _month_of(day: int) -> int:
    total = 0
    for m, n in enumerate(MONTH_DAYS):
        total += n
        if day < total:
            return m
    return 11


def _model_days(a: object, b: object) -> Optional[Tuple[int, int]]:
    """Return the model's "MM-DD" (or "2027-MM-DD") dates as 0-based days, or None."""
    out = []
    for x in (a, b):
        m = re.search(r"(?:2027-)?(\d{1,2})-(\d{1,2})", str(x or ""))
        if not m:
            return None
        month, day = int(m.group(1)) - 1, int(m.group(2))
        if not (0 <= month < 12 and 1 <= day <= MONTH_DAYS[month]):
            return None
        out.append(sum(MONTH_DAYS[:month]) + day - 1)
    return (min(out), max(out))


def _duration(text: str) -> Optional[int]:
    """Return a duration in days from "for two weeks", "10 days", "a month", or None."""
    m = DURATION.search(text)
    if not m:
        return None
    n = m.group(1).lower()
    count = int(n) if n.isdigit() else COUNTS.get(n, 1)
    unit = m.group(2).lower()
    return count * (14 if unit.startswith("fortnight") else UNIT_DAYS[unit[0]])


# Units and parts the plant model has, and things it has not: an "unsupported" item naming
# only the first is a request the model can run.
MODELLED = re.compile(
    r"\b(absorption|chillers?|heat pumps?|boilers?|doublets?|heat exchangers?|esp|injectors?|"
    r"producers?|separators?|treatment trains?|cooling towers?|wells?)\b",
    re.I,
)
FOREIGN = re.compile(
    r"solar|\bpv\b|photovolt|wind|batter|storage|\bates\b|hydrogen|\bchp\b|cogenerat|"
    r"biomass|turbine|tank|buffer|lake|river|\bsea\b|waste heat|data cent|series|cascade of|"
    r"\bcop\b|\beer\b|efficien",
    re.I,
)
BUILD_WORDS = re.compile(
    r"\b(separator|separators|filter|filters|train|trains|injector|injectors|producer|"
    r"producers|doublet|doublets|well|wells|open|half|depth|flow|boiler|heat pump|chiller)",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").lower()).strip(" .,;:!?\"'")


NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "single": 1,
    "double": 2,
    "doubles": 2,
    "doubled": 2,
    "doubling": 2,
    "twice": 2,
    "half": 0.5,
    "halve": 0.5,
    "halves": 0.5,
    "halved": 0.5,
    "triple": 3,
    "triples": 3,
    "tripled": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "fifteen": 15,
    "twenty": 20,
    "fifth": 0.2,
    "quarter": 0.25,
    "third": 1 / 3,
    "tien": 10,
    "vijf": 5,
    "zehn": 10,
    "fünf": 5,
    "verdubbelt": 2,
    "verdubbeld": 2,
    "verdubbelen": 2,
    "verdoppelt": 2,
    "verdoppeln": 2,
    "een": 1,
    "één": 1,
    "twee": 2,
    "drie": 3,
    "eins": 1,
    "zwei": 2,
    "drei": 3,
    "dubbel": 2,
    "helft": 0.5,
    "eins": 1,
    "eine": 1,
    "zwei": 2,
    "drei": 3,
    "doppelt": 2,
    "hälfte": 0.5,
    "halb": 0.5,
}


def _numbers(quote: str) -> List[float]:
    found = [float(m.group(0).replace(",", ".")) for m in NUMBER.finditer(quote)]
    found += [v for w, v in WORDS.items() if re.search(rf"\b{w}\b", quote, re.I)]
    return found


VAGUE = "the message gives no amount"


def _flow(value, message: str) -> Optional[float]:
    """Return a doublet's flow the message gives (m3/h, 50 to 300), else None."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if 50 <= x <= 300 and _backed([x], message) else None


def per_mwh(quote: str) -> Optional[float]:
    """Return the price a quote gives in €/MWh ("4,5 ct/kWh" is 45), or None.

    The units are read by ``quantities`` (cents or euros per kWh, MWh or GJ; "1.500" and
    "4,5" as written).
    """
    for q in quantities.extract(quote):
        if q.dimension == "energy_price":
            return round(q.base()[0], 6)
    return None


def _valid(p: Parameter, value: object, quote: str, now: object = None) -> Tuple[bool, str]:
    """Return whether a value fits a parameter and its quote, and why not.

    A number must be in the quote (or km/%-converted), or follow from a number in the quote
    and the value now ("10 K lower", "20 % more", "double"); a relative wording without an
    amount ("a lower return") is vague, never a number to use.
    """
    if p.kind == "choice":
        return (str(value) in p.options, f"not one of {', '.join(p.options)}")
    if p.kind == "list":
        values = value if isinstance(value, list) else [value]
        if p.options:
            bad = [v for v in values if str(v) not in p.options]
            return (not bad, f"not among {', '.join(p.options)}")
        try:
            nums = [float(v) for v in values]
        except (TypeError, ValueError):
            return False, "not numbers"
        if not all(p.low <= v <= p.high for v in nums):
            return False, f"outside {p.low:g}-{p.high:g}"
        return (_backed(nums, quote), "its numbers are not in the quote")
    try:
        x = float(value)
    except (TypeError, ValueError):
        # "what if gas got cheaper?": the reader named the input and gave no number (S44, 31
        # Oct); that is an ask without an amount, not a reading to drop.
        if p.kind == "number" and value is None and _relative(quote):
            return False, VAGUE
        return False, "not a number"
    if not p.low <= x <= p.high:
        return False, f"outside {p.low:g}-{p.high:g} {p.unit}"
    if p.target in ("search",) and p.kind == "number":
        if _backed([x], quote):
            return True, ""
        # "Use more doublets": a count asked for without one is asked for (4 Nov: read as 2
        # and dropped, then the last search's card opened as if nothing had been asked).
        return False, VAGUE if _relative(quote) else "its number is not in the quote"
    if _backed([x], quote):
        return True, ""
    if isinstance(now, (int, float)) and _derived(x, float(now), quote):
        return True, ""
    if _relative(quote):
        return False, VAGUE
    return False, "its number is not in the quote"


def _vague_counts() -> bool:
    """Return True when a count asked without one ("more doublets") is asked about."""
    from gemini_agent import clarify

    return clarify.on()


def _derived(x: float, now: float, quote: str) -> bool:
    """Return True when ``x`` follows from the value now and a number of the quote.

    Also the difference of two numbers of the quote ("77 °C instead of 87 °C" is -10).
    """
    nums = _numbers(quote)
    for a in nums:
        for b in nums:
            if a != b and abs(x - (a - b)) <= 1e-6 * max(1.0, abs(x)):
                return True
    for n in nums:
        for y in (
            now + n,
            now - n,
            now * n,
            now / n if n else None,
            now * (1 + n / 100),
            now * (1 - n / 100),
        ):
            if y is not None and abs(x - y) <= 1e-6 * max(1.0, abs(x)) + 1e-9:
                return True
    return False


RELATIVE = re.compile(
    r"\b(doubles?|doubled|twice|half|halve[sd]?|triples?|tripled|more|less|higher|lower|colder|"
    r"warmer|hotter|cooler|"
    r"cheaper|dearer|pricier|bigger|smaller|larger|longer|shorter|deeper|shallower|"
    r"increase|decrease|raise|reduce|drop|cut|up|down|extra|plus|minus|percent|per cent|"
    r"goedkoper|duurder|meer|minder|hoger|lager)\b|%",
    re.I,
)


def _relative(quote: str) -> bool:
    """Return True when the quote words a relative change ("10 K lower", "double")."""
    return bool(RELATIVE.search(quote))


# Unit conversions a reading may have made: km -> m and TWh -> GWh (x1000), % -> fraction
# (/100), ct/kWh -> EUR/MWh (x10), l/s -> m3/h (x3.6), and the reverse of each.
FACTORS = (1.0, 1000.0, 0.001, 0.01, 10.0, 0.1, 3.6, 1 / 3.6)


def _backed(values: Sequence[float], quote: str) -> bool:
    """Return True when every value is a number of the quote, as written or unit-converted.

    Conversions: ``FACTORS``, and °F to °C. A sign may differ ("10 K colder" is -10).
    """
    nums = _numbers(quote)
    fahrenheit = bool(re.search(r"°\s*F\b|\bfahrenheit\b", quote, re.I))
    for v in values:
        ok = False
        for n in nums:
            candidates = [n * f for f in FACTORS]
            if fahrenheit:
                candidates.append((n - 32) * 5 / 9)
            if any(
                abs(v - c) <= 1e-6 * max(1.0, abs(c))
                or abs(abs(v) - abs(c)) <= 1e-6 * max(1.0, abs(c))
                for c in candidates
            ):
                ok = True
                break
            if fahrenheit and abs(v - round((n - 32) * 5 / 9, 1)) <= 0.051:
                ok = True
                break
        if not ok:
            return False
    return True


def _clean(p: Parameter, value: object) -> object:
    if p.kind == "choice":
        return str(value)
    if p.kind == "list":
        values = value if isinstance(value, list) else [value]
        return [str(v) for v in values] if p.options else [float(v) for v in values]
    x = float(value)
    return int(round(x)) if p.target == "search" or p.unit == "days" else x


def _same(a: object, b: object) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def _depth(value) -> Optional[float]:
    if value in (None, "", 0):
        return None
    x = float(value)
    return x if 500 <= x <= 7000 else None


def _plain(d: DoubletSpec) -> bool:
    return (
        d.depth_m is None
        and d.injectors == 1
        and d.producer_open == "full"
        and d.injector_open == "full"
        and d.max_flow_m3h is None
        and d.train is None
    )


DOUBLET_WORDS = re.compile(
    r"\b(doublet|triplet|well|wells|injector|injectors|producer|separator|train|doublets|put|bron)",
    re.I,
)


def _describes_doublets(message: str) -> bool:
    return bool(DOUBLET_WORDS.search(message))


# ------------------------------------------------------------------ the values now


def values_now(brief: DesignBrief, alt: Optional[Alternative], rules, prices) -> Dict[str, object]:
    """Return each parameter's value now: the design's, else the brief's and the project's."""
    heating = brief.heating
    cooling = brief.cooling
    now: Dict[str, object] = {
        "heat_supply_c": heating.supply_c if heating else rules.heat_supply_c,
        "heat_return_c": heating.return_c if heating else rules.heat_return_c,
        "cool_supply_c": cooling.supply_c if cooling else rules.cool_supply_c,
        "cool_return_c": cooling.return_c if cooling else rules.cool_return_c,
        "reservoir_change_k": brief.reservoir_delta_c or 0.0,
        "objective": brief.objective,
        "heat_demand_scale": brief.demand_scale[0],
        "cool_demand_scale": brief.demand_scale[1],
        "capex_scale": 1.0,
    }
    for key in (
        "gradient_c_per_km",
        "permeability_md",
        "reservoir_thickness_m",
        "reservoir_pressure_bar",
        "gas_liquid_ratio",
        "operating_days",
        "flow_max_m3h",
        "flow_min_m3h",
        "max_brine_cooling_k",
        "pump_efficiency",
    ):
        now[key] = getattr(rules, key)
    from dioscuri_plant.components import Components

    grid = getattr(rules, "grid_t_co2_per_mwh", None)
    now["grid_t_co2_per_mwh"] = Components().grid_t_co2_per_mwh if grid is None else grid
    for key in (
        "flare_brine_gas",
        "co2_reinjection",
        "free_cooling",
        "grid_by_month",
        "solar_mwp",
        "storage_mwh",
        "storage_ates",
        "second_aquifer_depth_m",
        "second_aquifer_thickness_m",
        "second_aquifer_permeability_md",
    ):
        now[key] = float(getattr(rules, key, 0.0) or 0.0)
    for key in (
        "electricity_eur_per_mwh",
        "gas_eur_per_mwh",
        "carbon_eur_per_t",
        "discount_rate",
        "well_spacing_m",
    ):
        now[key] = getattr(prices, key)
    # The aquifers there are (each with what it is: known, given, assumed), and the rules they
    # are worked out with (``aquifers.from_reading``).
    from gemini_agent import aquifers

    now["aquifers"] = aquifers.resolved(brief, rules)
    now["_rules"] = rules
    given = next((a for a in now["aquifers"] if a["kind"] == "given"), None)
    if given is not None:  # the older second aquifer's keys: the first one described
        now["second_aquifer_depth_m"] = given["depth_m"]
        now["second_aquifer_thickness_m"] = given["thickness_m"]
        now["second_aquifer_permeability_md"] = given["permeability_md"]
    if alt is not None and alt.n_doublets:
        now["n_doublets"] = alt.n_doublets
        specs = alt.doublets or [{}]
        now["aquifer_depths_m"] = sorted({float(d.get("depth_m") or alt.depth_m) for d in specs})
        now["injectors"] = max(int(d.get("injectors") or 1) for d in specs)
        trains = {d.get("train", 0) for d in specs}
        now["trains"] = "separate" if len(trains) > 1 else "shared"
        now["dispatch"] = alt.dispatch
        now["producer_open"] = str(specs[0].get("producer_open") or "full")
        now["injector_open"] = str(specs[0].get("injector_open") or "full")
        for key, size in SIZE_KEYS.items():
            now[key] = float(alt.sizes_mw.get(size, 0.0))
    now["exclude"] = list(brief.excluded)
    return now


# ------------------------------------------------------------------ applying the changes


def apply(brief: DesignBrief, changes: Dict[str, object], doublets: Sequence[DoubletSpec] = ()):
    """Return the brief with the changes: conditions, prices and the search's options.

    Unit sizes are not the brief's (see ``change_design``).
    """
    update: Dict[str, object] = {}
    rules = dict(brief.rules)
    prices = dict(brief.prices)
    scale = list(brief.demand_scale)
    heating = brief.heating
    cooling = brief.cooling
    second = {k: v for k, v in changes.items() if k.startswith("second_aquifer_")}
    if "aquifers" in changes:
        # The list holds every aquifer: an older second-aquifer key read beside it (the
        # options call's) is the same aquifer said twice, never one more.
        changes = {k: v for k, v in changes.items() if k not in second}
        second = {}
    for key, value in changes.items():
        p = CATALOGUE[key]
        if key in second:
            continue  # onto the aquifers list, below
        if p.target == "aquifers":
            from gemini_agent import aquifers

            found = aquifers.put(brief.model_copy(update={"rules": rules}), value)
            rules = dict(found.pop("rules"))
            update.update(found)
            continue
        if p.target == "network":
            if key.startswith("heat"):
                base = heating or NetworkTemps(supply_c=100.0, return_c=60.0)
                heating = NetworkTemps(
                    supply_c=float(value) if key == "heat_supply_c" else base.supply_c,
                    return_c=float(value) if key == "heat_return_c" else base.return_c,
                )
            else:
                base = cooling or NetworkTemps(supply_c=20.0, return_c=25.0)
                cooling = NetworkTemps(
                    supply_c=float(value) if key == "cool_supply_c" else base.supply_c,
                    return_c=float(value) if key == "cool_return_c" else base.return_c,
                )
        elif p.target == "brief":
            update[p.field or key] = float(value)
        elif p.target == "rules":
            rules[p.field or key] = value
        elif p.target == "scale":
            scale[0 if key.startswith("heat") else 1] = float(value)
        elif p.target == "prices":
            prices[p.field or key] = float(value)
            if key == "well_spacing_m":  # the breakthrough check reads it from the rules
                rules["well_spacing_m"] = float(value)
        elif p.target == "stops":
            update["doublet_stops"] = [[list(r) for r in d] for d in value]
        elif p.target == "search":
            if key == "exclude":
                update["excluded"] = sorted(set(brief.excluded) | set(value))
            elif key == "allow":
                update["excluded"] = [x for x in brief.excluded if x not in set(value)]
            elif key == "aquifer_depths_m":
                update["doublet_depths_m"] = [float(v) for v in value]
            else:
                update[p.field or key] = value
    if second:
        # The older second-aquifer keys (the fine-tuned readers still give them): the first
        # aquifer described, added or changed in the list.
        from gemini_agent import aquifers

        records = aquifers.second_edits(second, brief)
        if records is None:
            rules.update(second)
        else:
            found = aquifers.put(brief.model_copy(update={"rules": rules}), records)
            rules = dict(found.pop("rules"))
            update.update(found)
    if heating is not None:
        update["heating"] = heating
    if cooling is not None:
        update["cooling"] = cooling
    update["rules"] = rules
    update["prices"] = prices
    update["demand_scale"] = scale
    if doublets:
        update["doublets"] = list(doublets)
        update["n_doublets"] = len(doublets)
    return brief.model_copy(update=update)


def change_design(alt: Alternative, changes: Dict[str, object], rules_depth: float) -> Alternative:
    """Return a design with a what-if's changes to the plant itself: sizes and how it is built.

    The search's options (``injectors``, ``trains``, ``dispatch``, the open parts, the
    doublets' count and aquifers) change the design's doublets; sizes change its units.
    """
    sizes = dict(alt.sizes_mw)
    for key, size in SIZE_KEYS.items():
        if key in changes:
            sizes[size] = float(changes[key])
    doublets = [dict(d) for d in alt.doublets] or [
        {"depth_m": alt.depth_m or rules_depth, "injectors": 1, "train": 0}
        for _ in range(alt.n_doublets)
    ]
    n = int(changes.get("n_doublets") or len(doublets))
    while len(doublets) < n:
        doublets.append(dict(doublets[-1], train=doublets[-1].get("train", 0)))
    doublets = doublets[:n]
    for d_i, d in enumerate(doublets):
        if "injectors" in changes:
            d["injectors"] = int(changes["injectors"])
        if "producer_open" in changes:
            d["producer_open"] = changes["producer_open"]
        if "injector_open" in changes:
            d["injector_open"] = changes["injector_open"]
        if "trains" in changes:
            d["train"] = d_i if changes["trains"] == "separate" else 0
        if "aquifer_depths_m" in changes and changes["aquifer_depths_m"]:
            depths = list(changes["aquifer_depths_m"])
            d["depth_m"] = float(depths[min(d_i, len(depths) - 1)])
    dispatch = str(changes.get("dispatch") or alt.dispatch)
    return alt.model_copy(
        update={
            "sizes_mw": sizes,
            "doublets": doublets,
            "n_doublets": n,
            "depth_m": float(doublets[0].get("depth_m") or alt.depth_m) if doublets else 0.0,
            "dispatch": dispatch if n > 1 else "equal",
            "heat_pump": sizes.get("heat_pump", 0.0) > 0,
            "boiler": sizes.get("boiler", 0.0) > 0,
            "absorption": sizes.get("absorption", 0.0) > 0,
            "chillers": sizes.get("chillers", 0.0) > 0,
        }
    )


DESIGN_KEYS = {
    "n_doublets",
    "aquifer_depths_m",
    "injectors",
    "trains",
    "dispatch",
    "producer_open",
    "injector_open",
    *SIZE_KEYS,
}
SEARCH_ONLY = {"exclude", "allow", "objective"}
# On/off settings said in words, and settings that need an amount when switched on.
# A floor on the CO2 cut in the message's words: "at least 50 % less CO2", "a 60% CO2 cut".
CO2_FLOOR = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*%\s*(?:less|lower|fewer|cut|reduction|saving|down)?\s*"
    r"(?:of |in )?(?:co2|co₂|carbon|emissions?)",
    re.I,
)
SWITCHES = {
    "planned_service",
    "co2_reinjection",
    "flare_brine_gas",
    "free_cooling",
    "grid_by_month",
    "storage_ates",
}
NEEDS_AMOUNT = {"network_length_km", "solar_mwp", "storage_mwh"}
# What best means, in the few words of a what-if's name.
OBJECTIVE_SHORT = {
    "best": "best overall",
    "cost": "lowest cost",
    "co2": "lowest CO₂",
    "reliable": "cheapest reliable",
    "green_reliable": "greenest reliable",
    "gas_free": "gas-free",
}


def stop_dates(
    quote: str, message: str, now: Dict[str, object]
) -> Tuple[List[List[List[int]]], str]:
    """Return the doublets' stops a message asks for, ``[[[first, last], ...] per doublet]``.

    The days are read from the words by code, never taken from the model: "in August" starts
    the stop on 1 August and keeps its length (the days the cap leaves, 35 for 330 operating
    days); "1 to 21 July" is those days; "from 10 July for three weeks" is 21 days. "doublet 2"
    sets that doublet alone; else every doublet gets the dates. Returns no stops and why when
    the words give no date.
    """
    from gemini_agent.answer import named_days

    days, months = named_days(quote, limit=366)
    if not days and not months:
        days, months = named_days(message, limit=366)
    length = _duration(quote) or _duration(message)
    cap = int(float(now.get("operating_days") or 330))
    length = length or max(1, 365 - cap)
    if len(days) >= 2:
        ranges, start = [], days[0]
        for a, b in zip(days, days[1:] + [None]):
            if b is None or b != a + 1:
                ranges.append([start, a])
                start = b
    elif days:
        ranges = [[days[0], min(days[0] + length - 1, 364)]]
    elif months:
        first = sum(MONTH_DAYS[: months[0]])
        ranges = [[first, min(first + length - 1, 364)]]
    else:
        return [], "no dates for the stop; say when, for example 'in August' or '1 to 21 July'"
    if sum(b - a + 1 for a, b in ranges) > 365 - 100:
        return [], "the stop is longer than the year allows"
    which = re.search(r"\b(?:doublet|dublette)\s*(\d)\b", quote, re.I)
    n = int(now.get("n_doublets") or 1)
    if which and 1 <= int(which.group(1)) <= 3:
        k = int(which.group(1))
        return [[] for _ in range(k - 1)] + [ranges], ""
    return [ranges for _ in range(max(1, n))], ""


def stops_label(stops: Sequence[Sequence[Sequence[int]]]) -> str:
    """Return the doublets' stops in words ("the doublets stopped 1 Aug to 4 Sep")."""
    from gemini_agent.answer import _date

    parts = []
    for k, ranges in enumerate(stops):
        if ranges:
            when = " and ".join(f"{_date(int(a))} to {_date(int(b))}" for a, b in ranges)
            parts.append((k, when))
    if len({w for _, w in parts}) == 1 and len(parts) == len(stops) and len(parts) > 1:
        return f"the doublets stopped {parts[0][1]}"
    if len(parts) == 1 and len(stops) == 1:
        return f"the doublet stopped {parts[0][1]}"
    return "; ".join(f"doublet {k + 1} stopped {w}" for k, w in parts)


def label(changes: Dict[str, object]) -> str:
    """Return the changes in a few words, for a what-if's name ("heating return 50 °C")."""
    parts = []
    # A store with HT-ATES on is the aquifer store, said once with its size (5 Nov: "HT-ATES
    # switched on, heat store at the plant 28000 MWh" read as two stores, and the reply's "a
    # heat store in an aquifer of 28,000 MWh" was removed as unsupported).
    ates = bool(changes.get("storage_ates")) and bool(changes.get("storage_mwh"))
    for key, value in changes.items():
        p = CATALOGUE[key]
        name = p.label[0].lower() + p.label[1:]
        name = re.sub(r"\s*\(.*\)$", "", name)
        if ates and key == "storage_ates":
            continue
        if ates and key == "storage_mwh":
            parts.append(f"a heat store in an aquifer (HT-ATES) of {float(value):,g} MWh")
            continue
        if key == "objective":
            short = OBJECTIVE_SHORT.get(str(value), str(value))
            # Beside other changes, said as what the search looks for ("With the yearly service
            # switched on, lowest cost, ..." read as a figure on 1 Nov).
            parts.append(f"(searching for the {short})" if len(changes) > 1 else short)
        elif key == "doublet_stops":
            parts.append(stops_label(value))
        elif key == "aquifers":
            from gemini_agent import aquifers

            parts.append(aquifers.words(value))
        elif key == "min_co2_saving":
            parts.append(f"a CO2 cut of at least {float(value) * 100:g}% against gas")
        elif key in SWITCHES:
            # "planned yearly service ... 1" read as a number on 1 Nov
            parts.append(f"{name} {'switched on' if float(value) else 'switched off'}")
        elif key == "network_length_km" and not float(value):
            parts.append("no district network")
        elif key == "solar_mwp" and not float(value):
            parts.append("no own solar")
        elif key == "storage_mwh" and not float(value):
            parts.append("no heat store")
        elif key == "n_doublets":
            n = int(float(value))
            parts.append(f"{n} doublet{'s' if n != 1 else ''}")
        elif key == "reservoir_change_k":
            parts.append(f"reservoir {float(value):+g} K")
        elif p.kind == "number":
            unit = "" if p.unit in ("", "x", "fraction") else f" {p.unit}"
            shown = f"×{float(value):g}" if p.unit == "x" else _shown(value)
            parts.append(f"{name} {shown}{unit}")
        else:
            parts.append(f"{name}: {_shown(value)}")
    return ", ".join(parts).replace(", (searching", " (searching")


# v2 (5 Nov): "reset", a reply that asks to go back to the project's defaults; v1 read "get back
# to default values" as a change with nothing in it, and the card's unconfirmed values ran.
CONFIRM_PROMPT = "confirm_v2"
CONFIRM_DECISIONS = ("run", "change", "reset", "other")
CONFIRM_SCHEMA = {
    "type": "object",
    "properties": {"decision": {"type": "string", "enum": list(CONFIRM_DECISIONS)}},
    "required": ["decision"],
}


def confirm_decision(message: str, llm, thread: str = "") -> Tuple[str, Optional[LLMCall]]:
    """Return what a typed reply to the inputs card means: run, change, reset or other.

    Parameters
    ----------
    message : str
        The user's reply.
    llm : OllamaLLM or ScriptedLLM
        The model that judges (the reasoning model).
    thread : str
        The chat's thread, short.

    Returns
    -------
    tuple of (str, LLMCall or None)
        The decision (``other`` when no model answers) and the call.
    """
    from gemini_agent.answer import load

    msgs = [
        {"role": "system", "content": load(CONFIRM_PROMPT)},
        {"role": "user", "content": f"{thread_block(thread)}Reply: {message}"},
    ]
    try:
        raw, call = llm.structured("confirm", msgs, CONFIRM_SCHEMA, 20)
    except LLMError as err:
        return "other", err.call
    decision = str(raw.get("decision") or "other")
    return (decision if decision in CONFIRM_DECISIONS else "other"), call


# Why the reading's own slips are not taken (a number the words do not give, a value that is no
# number, an aquifer edit with nothing in it): not the user's request refused on its merits.
MISREAD = (
    "is not in the message",
    "not in the quote",
    "cannot match it",
    "is not a number",
    "no aquifer change read",
)


def misread(why: str) -> bool:
    """Return True when a value was not taken for the reading's own slip, not on its merits."""
    return any(w in str(why) for w in MISREAD)


# ------------------------------------------------------------------ a list added to

# A reading whose aquifers (or depths to try) both lose some of those there and name new ones
# is either an add ("put one more well pair in at 4,200 m") or a replacement ("drill to 4 km
# instead"). The model says which (``list_op``); code then keeps every aquifer there for an add
# and refuses one past the limit (``as_added``). 5 Nov: "add a 4th doublet at 100 m" left one
# aquifer at 100 m on the inputs card, and "one more well pair at 4,200 m" left only 4,200 m.
LIST_PROMPT = "list_v1"
LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": ["add", "replace", "remove", "change", "unclear"]}
    },
    "required": ["op"],
}
LIST_KEYS = ("aquifers", "aquifer_depths_m")


def list_op(message: str, listed: str, llm, thread: str = "") -> Tuple[str, Optional[LLMCall]]:
    """Return what a message does to the aquifers listed: add, replace, remove, change, unclear.

    Parameters
    ----------
    message : str
        The user's message.
    listed : str
        The aquifers there are, as the planner lists them (``aquifers.now_text``).
    llm : OllamaLLM or ScriptedLLM
        The model that judges (the reasoning model).
    thread : str
        The chat's thread, short.

    Returns
    -------
    tuple of (str, LLMCall or None)
        The operation (``unclear`` when no model answers) and the call.
    """
    from gemini_agent.answer import load

    msgs = [
        {"role": "system", "content": load(LIST_PROMPT)},
        {
            "role": "user",
            "content": f"{thread_block(thread)}Listed now: {listed}\n\nMessage: {message}",
        },
    ]
    try:
        raw, call = llm.structured("list_op", msgs, LIST_SCHEMA, 20)
    except LLMError as err:
        return "unclear", err.call
    op = str(raw.get("op") or "unclear") if isinstance(raw, dict) else "unclear"
    return (op if op in LIST_SCHEMA["properties"]["op"]["enum"] else "unclear"), call


def _depths_of(value: object) -> List[float]:
    out = []
    for v in value if isinstance(value, list) else [value]:
        try:
            out.append(float(v["depth_m"] if isinstance(v, dict) else v))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def list_drops_and_adds(reading: "Reading", now: Dict[str, object]) -> Optional[str]:
    """Return the key of a list change that drops aquifers there and names new ones, or None.

    Only then is "add or replace?" open: a list that keeps every aquifer and adds is an add,
    one that names only aquifers there is a choice among them.
    """
    from gemini_agent import aquifers

    before = _depths_of(now.get("aquifers") or [])
    for key in LIST_KEYS:
        if key not in reading.changes:
            continue
        after = _depths_of(reading.changes[key])
        near = lambda d, ds: any(abs(d - x) < aquifers.SAME_DEPTH_M for x in ds)  # noqa: E731
        new = [d for d in after if not near(d, before)]
        gone = [d for d in before if not near(d, after)]
        if new and gone:
            return key
    return None


def as_added(reading: "Reading", now: Dict[str, object], key: str, message: str) -> None:
    """Make a list change an add: every aquifer there stays and the new ones join it.

    More than ``aquifers.MAX`` in all is refused: the change is dropped, and why is said with
    what can be done (``dropped`` as a refusal of ``key``, so the inputs card says it).
    """
    from gemini_agent import aquifers

    rows = [dict(r) for r in now.get("aquifers") or []]
    before = _depths_of(rows)
    value = reading.changes[key]
    near = lambda d: any(abs(d - x) < aquifers.SAME_DEPTH_M for x in before)  # noqa: E731
    if key == "aquifers":
        new = [dict(r) for r in value if not near(float(r["depth_m"]))]
        combined = [{k: float(r[k]) for k in aquifers.KEYS} for r in rows] + new
    else:
        new = [float(d) for d in value if not near(float(d))]
        combined = before + new
    if len(combined) <= aquifers.MAX:
        reading.changes[key] = combined
        reading.items = [(k, combined if k == key else v, s) for k, v, s in reading.items]
        return
    shown = ", ".join(f"{d:,.0f}" for d in before)
    added = " and ".join(f"{d:,.0f} m" for d in _depths_of(new))
    why = (
        f"there are {len(before)} aquifers already ({shown} m) and a design can use at most "
        f"{aquifers.MAX}: say which one {added} should replace, or change one's depth"
    )
    reading.changes.pop(key, None)
    reading.step_of.pop(key, None)
    reading.items = [i for i in reading.items if i[0] != key]
    reading.quotes.pop(key, None)
    listed = [round(d, 1) for d in _depths_of(new)]
    reading.dropped.append(f"{key}={listed}: {why}")


OPEN_PROMPT = "open_v1"
OPEN_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {"type": "boolean"},
        "option": {"type": "integer"},
        "value": {"type": "string"},
    },
    "required": ["answers", "option", "value"],
}


def answers_question(
    message: str, question: str, options: Sequence[str], llm, thread: str = ""
) -> Tuple[Optional[Tuple[int, str]], Optional[LLMCall]]:
    """Return whether a typed reply answers the question Dioscuri left open, and how.

    "the cheapest one" after "Which design is your question about?", "2 GWh" after "By how
    much?", "yes" after "Write an adsorption chiller model?": the model decides (4 Nov: a typed
    reply dropped the question and was read as a new message, without what it answered).

    Parameters
    ----------
    message : str
        The user's typed reply.
    question : str
        The question as Dioscuri asked it.
    options : sequence of str
        The options it offered (may be empty).
    llm : OllamaLLM or ScriptedLLM
        The model that judges (the reasoning model).
    thread : str
        The chat's thread, short.

    Returns
    -------
    tuple of ((int, str) or None, LLMCall or None)
        ``(option, value)`` when the reply answers it (``option`` 1-based, 0 for none; ``value``
        the reply's own words), else None; and the call.
    """
    from gemini_agent.answer import load

    listed = "\n".join(f"{i}. {o}" for i, o in enumerate(options, 1)) or "(none: a free answer)"
    msgs = [
        {"role": "system", "content": load(OPEN_PROMPT)},
        {
            "role": "user",
            "content": f"{thread_block(thread)}Question: {question}\nOptions:\n{listed}\n\n"
            f"Reply: {message}",
        },
    ]
    try:
        raw, call = llm.structured("open_question", msgs, OPEN_SCHEMA, 60)
    except LLMError as err:
        return None, err.call
    if not isinstance(raw, dict) or raw.get("answers") is not True:
        return None, call
    try:
        option = int(raw.get("option") or 0)
    except (TypeError, ValueError):
        option = 0
    option = option if 1 <= option <= len(options) else 0
    value = " ".join(str(raw.get("value") or "").split())[:200]
    if not option and not value:
        return None, call
    return (option, value), call


WHICH_PROMPT = "which_v1"
# v2: the options marked from the chat's state (``chat_state.annotate``): their place in the last
# list shown, the original design of a what-if, their figures (DIOSCURI_CHAT_STATE, 4 Nov).
WHICH_STATE_PROMPT = "which_v2"


def design_meant(
    message: str, options: Sequence[str], llm, thread: str = ""
) -> Tuple[int, Optional[LLMCall]]:
    """Return which of the chat's designs a message is about (1-based), 0 when unclear.

    -1 when the message is about several designs or none ("which designs have we looked at?").
    Asked before Dioscuri asks the user "which design?" (ADR-0017): "how much capital does it
    need?" right after a reply about A1 is about A1, from the conversation (4 Nov: every such
    question was asked back). The model answers with a design's name, not a number: "the
    second one" means the conversation's list, not this one. 0 when the model cannot say;
    then the user is asked.

    ``options``: "A1 · best overall (1D-HP-EC-N1)", the name before the " · ".
    """
    from gemini_agent.answer import load

    names = [o.split(" · ", 1)[0].strip() for o in options]
    schema = {
        "type": "object",
        "properties": {"design": {"type": "string", "enum": names + ["unclear", "several"]}},
        "required": ["design"],
    }
    from gemini_agent import chat_state

    listed = "\n".join(f"- {o}" for o in options)
    msgs = [
        {
            "role": "system",
            "content": load(WHICH_STATE_PROMPT if chat_state.on() else WHICH_PROMPT),
        },
        {
            "role": "user",
            "content": f"Designs:\n{listed}\n\n{thread_block(thread)}Message: {message}",
        },
    ]
    try:
        raw, call = llm.structured("which_design", msgs, schema, 20)
    except LLMError as err:
        return 0, err.call
    said = str(raw.get("design") or "") if isinstance(raw, dict) else ""
    if said == "several":
        return -1, call
    return (names.index(said) + 1 if said in names else 0), call


DOWN = re.compile(
    r"\b(lower|less|cheaper|colder|cooler|smaller|shorter|shallower|reduce|decrease|drop|cut|"
    r"down|minus|fewer|goedkoper|lager|minder|kouder)\b",
    re.I,
)


def amount_options(key: str, guess: float, now: float, quote: str = "") -> List[float]:
    """Return three amounts to offer for a change asked without one ("cheaper gas").

    The direction is the words' ("cheaper", "lower" go down), else the model's guess; the
    steps are 5 K for temperatures, else 15 % of the value now.
    """
    p = CATALOGUE[key]
    if quote and DOWN.search(quote):
        sign = -1.0
    elif quote and RELATIVE.search(quote):
        sign = 1.0
    else:
        sign = -1.0 if guess < now else 1.0
    count = not p.unit and p.low is not None and p.high is not None
    count = count and float(p.low).is_integer() and float(p.high).is_integer()
    if p.unit in ("°C", "K") or (count and p.high - p.low <= 10):
        step = 5.0 if p.unit else 1.0  # a count (doublets, injectors) goes one at a time
    elif abs(now) > 1e-9:
        step = abs(now) * 0.15
    else:
        step = (p.high - p.low) / 10
    out = []
    for f in (1.0, 2.0, 3.0):
        v = min(max(now + sign * f * step, p.low), p.high)
        v = round(v, 0 if step >= 2 else 2)
        if v not in out and abs(v - now) > 1e-9:
            out.append(v)
    return out


NEEDS_PROMPT = "needs_v1"
NEEDS_SCHEMA = {
    "type": "object",
    "properties": {"needs": {"type": "string", "enum": NEEDS}},
    "required": ["needs"],
}


# The plant's options, read again on their own when the long reading leaves something unread
# (3 Nov): "a 2 GWh buffer tank" was filed as not modelled and "winter electricity dirtier than
# summer's" as a what-if with nothing to change. A short call that sees only these does better.
OPTION_KEYS = (
    "free_cooling",
    "solar_mwp",
    "storage_mwh",
    "storage_ates",
    "grid_by_month",
    "grid_t_co2_per_mwh",
    "second_aquifer_depth_m",
    "second_aquifer_thickness_m",
    "second_aquifer_permeability_md",
    "network_length_km",
    "planned_service",
    "flare_brine_gas",
    "co2_reinjection",
)
# Options a design has or has not ("would free cooling help?" when it has it): said as already
# there. Not the grid's figure or the second aquifer's rock, which every design has a value of.
ALREADY_KEYS = (
    "free_cooling",
    "solar_mwp",
    "storage_mwh",
    "storage_ates",
    "grid_by_month",
    "planned_service",
    "flare_brine_gas",
    "co2_reinjection",
)
OPTIONS_PROMPT = "options_v1"
OPTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": list(OPTION_KEYS)},
                    "value": {"type": "number"},
                    "quote": {"type": "string"},
                },
                "required": ["key", "value", "quote"],
            },
        }
    },
    "required": ["changes"],
}


def wants_options(reading: "Reading", asks_change: bool = False) -> bool:
    """Return whether the long reading left something the options call may read.

    Something filed as not modelled, a change dropped, or a what-if with nothing to change;
    or nothing read at all from a message the small reader took for a change (``asks_change``:
    "count the grid's CO2 month by month" read as nothing with the chat's designs listed).
    """
    if not reading.ok or reading.unclear:
        return False
    idle = not (
        reading.changes or reading.doublets or reading.failures or reading.vague or reading.already
    )
    what_if = any(s.do == "what_if" for s in reading.steps)
    return bool(reading.unsupported or reading.dropped or (idle and (what_if or asks_change)))


def read_options(
    message: str, llm, now: Dict[str, object], thread: str = ""
) -> Tuple["Reading", object]:
    """Ask the model which of the plant's options (``OPTION_KEYS``) the message sets.

    Returns the checked reading (the same checks as ``read``) and the call. ``thread``: the
    chat's thread, short (what "that" or "the same" refers to).
    """
    from gemini_agent.answer import load

    msgs = [
        {"role": "system", "content": load(OPTIONS_PROMPT)},
        {
            "role": "user",
            "content": f"Options:\n{catalogue_text(now, OPTION_KEYS)}\n\n"
            f"{thread_block(thread)}Message: {message}",
        },
    ]
    try:
        raw, call = llm.structured("options", msgs, OPTIONS_SCHEMA, 300)
    except LLMError as err:
        return Reading(ok=False), err.call
    items = [
        c
        for c in (raw.get("changes") if isinstance(raw, dict) else None) or []
        if isinstance(c, dict) and c.get("key") in OPTION_KEYS
    ]
    return check({"changes": items}, message, now, pairs=True), call


def merge_options(reading: "Reading", extra: "Reading") -> List[str]:
    """Add the options call's changes to the reading; return the keys added.

    What the long reading filed as not modelled goes when an option now covers it, and a
    what-if step gets the changes (they are its change).
    """
    # A second aquifer read again beside the aquifers list is the list's (``apply``).
    listed = "aquifers" in reading.changes
    added = [
        k
        for k in extra.changes
        if k not in reading.changes and not (listed and k.startswith("second_aquifer_"))
    ]
    vague = [k for k in extra.vague if k not in reading.changes and k not in reading.vague]
    reading.already += [k for k in extra.already if k not in reading.already]
    if not added and not vague:
        return []
    step = next((i for i, s in enumerate(reading.steps) if s.do in ("what_if", "design")), 0)
    for key in added:
        reading.changes[key] = extra.changes[key]
        reading.step_of[key] = step
        reading.items.append((key, extra.changes[key], step))
    for key in vague:
        reading.vague[key] = extra.vague[key]
    reading.unsupported = []  # what was not modelled is an option after all
    reading.dropped += [f"{k}: read again as a plant option" for k in added + vague]
    if not any(s.do in ("what_if", "design") for s in reading.steps) and reading.steps:
        reading.steps.insert(0, Step("what_if", ""))
        for key in reading.step_of:
            reading.step_of[key] = 0
        reading.items = [(k, v, 0) for k, v, _ in reading.items]
    return added + vague


def set_needs(reading: "Reading", needs: str) -> None:
    """Set the reading's new_design, about_design and show from what the reply needs."""
    reading.new_design = needs == "new_design_run"
    reading.about_design = needs == "about_one_existing_design"
    reading.show = {
        "designs_side_by_side": ["comparison"],
        "how_the_design_was_found": ["search"],
    }.get(needs, [])


def read_needs(
    message: str, llm, designs: str = "", thread: str = ""
) -> Tuple[Optional[str], object]:
    """Ask the model what the reply needs (``NEEDS``); (None, call) when it cannot say.

    ``thread``: the chat's thread, short, before the message (nothing changes without one).
    """
    from gemini_agent.answer import load

    msgs = [
        {"role": "system", "content": load(NEEDS_SHORT_PROMPT if short_for(llm) else NEEDS_PROMPT)},
        {
            "role": "user",
            "content": (f"Designs made so far:\n{designs}\n\n" if designs else "")
            + thread_block(thread)
            + f"Message: {message}",
        },
    ]
    try:
        raw, call = llm.structured("needs", msgs, NEEDS_SCHEMA, 40)
    except LLMError as err:
        return None, err.call
    needs = raw.get("needs") if isinstance(raw, dict) else None
    return (needs if needs in NEEDS else None), call
