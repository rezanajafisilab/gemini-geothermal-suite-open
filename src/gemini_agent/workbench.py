"""Workbench: what the tabs read and do (``hackathon/docs/workbench_api.md``).

The chat and the tabs share one store, a conversation's design ledger. Every function here
calls the same tools as the agent, so a number on a tab is the number the chat would give.
The tabs add three things the chat does not do:

- user designs (``create_design``): a design edited on the Design tab, run end to end;
- cost assumptions per conversation (``put_assumptions``), used by every economics view;
- sensitivity runs (``sensitivity``) over the parameters the user picks.
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import dioscuri_plant as dp
from dioscuri_plant.economics import SOURCES as PRICE_SOURCES
from dioscuri_plant.types import GAS_MODES
from gemini_agent import aquifers, engine, gemini_runtime, issues, reporter
from gemini_agent.contract import DesignBrief, LedgerEntry, NetworkTemps

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "hackathon" / "evals" / "runs"
BENCHMARKS = ROOT / "hackathon" / "evals" / "BENCHMARKS.md"
MINUS = "−"
OUTPUTS = {
    "lcoh": ("Cost of heat", "€/MWh"),
    "lcoc": ("Cost of cold", "€/MWh"),
    "lcoe": ("Cost of heat and cold", "€/MWh"),
    "co2_saving_pct": ("CO₂ saving against gas", "%"),
    "heat_coverage": ("Heat covered", "%"),
    "capex_meur": ("Capital", "M€"),
    "npv_meur": ("NPV against gas", "M€"),
    "violations": ("Caps broken", ""),
}
# key: (label, unit, group, low, high, kind, description)
PARAMETERS = {
    "heat_return": (
        "Heating return temperature",
        "°C",
        "demand",
        45.0,
        70.0,
        "absolute",
        "Not given by the organisers (we assume 60 °C); sets how much heat the brine gives",
    ),
    "cool_return": (
        "Cooling return temperature",
        "°C",
        "demand",
        22.0,
        30.0,
        "absolute",
        "Not given by the organisers (we assume 25 °C)",
    ),
    "reservoir_temp": (
        "Reservoir temperature",
        "°C",
        "subsurface",
        -10.0,
        5.0,
        "delta",
        "Change to the reservoir temperature (the gradient's uncertainty)",
    ),
    "permeability": (
        "Permeability",
        "mD",
        "subsurface",
        100.0,
        300.0,
        "absolute",
        "Sets the wells' productivity index, so the pumps' power (GEMINI's inflow)",
    ),
    "depth": (
        "Doublet depth",
        "m",
        "subsurface",
        2000.0,
        3500.0,
        "absolute",
        "Depth of the wells (hotter brine deeper, dearer wells)",
    ),
    "operating_days": (
        "Operating days per doublet",
        "days",
        "subsurface",
        300.0,
        365.0,
        "absolute",
        "The requirements' 330 daily steps (meaning asked of the organisers)",
    ),
    "heat_demand": (
        "Heat demand",
        "×",
        "demand",
        0.8,
        1.2,
        "scale",
        "The daily heat demand, scaled",
    ),
    "cool_demand": (
        "Cooling demand",
        "×",
        "demand",
        0.8,
        1.2,
        "scale",
        "The daily cooling demand, scaled",
    ),
    "gas_price": (
        "Gas price",
        "€/MWh",
        "prices",
        40.0,
        100.0,
        "absolute",
        "Gas bought for the boiler (2025 NL: 69.4)",
    ),
    "electricity_price": (
        "Electricity price",
        "€/MWh",
        "prices",
        120.0,
        250.0,
        "absolute",
        "Electricity for the heat pump, pumps and chillers (2025 NL: 185.7)",
    ),
    "carbon_price": (
        "CO₂ price",
        "€/t",
        "prices",
        40.0,
        200.0,
        "absolute",
        "Price on the CO₂ the plant emits (2025: 73.9; PBL's long-term 137)",
    ),
    "capex": (
        "Capital costs",
        "×",
        "costs",
        0.8,
        1.3,
        "scale",
        "All equipment and well costs, scaled",
    ),
    "discount_rate": (
        "Discount rate",
        "",
        "costs",
        0.03,
        0.08,
        "absolute",
        "Sets the annuities and the NPV",
    ),
}
# What a sensitivity range may span (a value outside is refused with a reason, not a crash).
LIMITS = {
    "heat_return": (20.0, 95.0),
    "cool_return": (6.0, 35.0),
    "reservoir_temp": (-30.0, 30.0),
    "permeability": (5.0, 5000.0),
    "depth": (500.0, 7000.0),
    "operating_days": (100.0, 365.0),
    "heat_demand": (0.1, 5.0),
    "cool_demand": (0.0, 5.0),
    "gas_price": (0.0, 1000.0),
    "electricity_price": (0.0, 2000.0),
    "carbon_price": (0.0, 1000.0),
    "capex": (0.2, 5.0),
    "discount_rate": (0.0, 0.3),
}
PRICE_LABELS = {
    "discount_rate": ("Discount rate (real)", ""),
    "electricity_eur_per_mwh": ("Electricity", "€/MWh"),
    "gas_eur_per_mwh": ("Gas", "€/MWh"),
    "carbon_eur_per_t": ("CO₂ price", "€/t"),
    "well_scale": ("Well cost scale", "×"),
    "well_base_eur": ("Well, fixed part", "€"),
    "well_per_m_eur": ("Well, per metre", "€/m"),
    "well_per_m2_eur": ("Well, per metre²", "€/m²"),
    "well_spacing_m": ("Well spacing", "m"),
    "well_curvature": ("Well curvature factor", "×"),
    "surface_per_doublet_meur": ("Surface plant, per doublet", "M€"),
    "surface_meur_per_mw": ("Surface plant, per MW", "M€/MW"),
    "heat_pump_meur_per_mw": ("Heat pump", "M€/MW"),
    "boiler_meur_per_mw": ("Boiler", "M€/MW"),
    "absorption_meur_per_mw": ("Absorption chiller", "M€/MW"),
    "chiller_meur_per_mw": ("Electric chillers", "M€/MW"),
    "geothermal_fixed_eur_per_kw": ("Geothermal O&M, fixed", "€/kW/yr"),
    "geothermal_variable_eur_per_mwh": ("Geothermal O&M, variable", "€/MWh"),
    "heat_pump_fixed_eur_per_mw": ("Heat pump O&M, fixed", "€/MW/yr"),
    "heat_pump_variable_eur_per_mwh": ("Heat pump O&M, variable", "€/MWh"),
    "boiler_fixed_eur_per_mw": ("Boiler O&M, fixed", "€/MW/yr"),
    "boiler_variable_eur_per_mwh": ("Boiler O&M, variable", "€/MWh"),
    "absorption_variable_eur_per_mwh": ("Absorption O&M", "€/MWh"),
    "chiller_fixed_eur_per_mw": ("Chiller O&M", "€/MW/yr"),
    "water_supply_eur_per_m3": ("Cooling towers' make-up water", "€/m³"),
    "blowdown_disposal_eur_per_m3": ("Cooling towers' blow-down discharge", "€/m³"),
    "wells_life_years": ("Wells and surface plant life", "years"),
    "heat_pump_life_years": ("Heat pump life", "years"),
    "boiler_life_years": ("Boiler life", "years"),
    "absorption_life_years": ("Absorption chiller life", "years"),
    "chiller_life_years": ("Chiller life", "years"),
    "carbon_long_term_eur_per_t": ("CO₂ price, long-term (best overall pick)", "€/t"),
    "treatment_scale_exponent": ("Treatment train scale exponent", ""),
    "electric_boiler_meur_per_mw": ("Electric boiler, with grid upgrade", "M€/MW"),
    "electric_boiler_fixed_eur_per_kw": ("Electric boiler O&M", "€/kW/yr"),
    "electric_boiler_grid_eur_per_kw": ("Electric boiler grid charge", "€/kW/yr"),
    "electric_boiler_grid_600h_eur_per_kw": ("Grid charge, 600-hour contract", "€/kW/yr"),
    "electric_boiler_grid_600h_week_eur_per_kw": ("Grid charge, a week's peak", "€/kW"),
    "electric_boiler_variable_eur_per_mwh": ("Electric boiler O&M, variable", "€/MWh"),
    "electric_boiler_life_years": ("Electric boiler life", "years"),
    "gas_sale_eur_per_mwh": ("Brine gas sold at", "€/MWh"),
    "gas_cleaning_eur_per_nm3": ("Cleaning and injecting it", "€/Nm³"),
}
# What the "capex" parameter scales: every capital cost, the same list as ``capex_scale``.
CAPEX_KEYS = list(engine.CAPEX_KEYS)
PATCH_TITLES = {
    "01": "Heat exchanger: signed duty (heat can flow cold to hot) — F1",
    "02": "Injector well: friction sign — F3",
    "03": "Well pipe roughness default 10 mm → 0.045 mm — F10",
    "04": "Heat pump: bracketed physical root — F2",
    "05": "ESP: affinity-law flow scaling — F5",
    "06": "Compressor: missing k factor — F7",
    "07": "Well pressure drop: two-phase superficial velocity, roughness units — F9",
    "08": "Heat pump: CO₂ of its electricity",
    "09": "Simulator: heat pump in the registry",
    "10": "Heat pump: Carnot COP at the source outlet",
    "11": "Well model: the brine's own properties (density, viscosity, heat capacity)",
}


# ------------------------------------------------------------------ designs


def design_id(entry: LedgerEntry) -> str:
    """Return a design's id (``reporter.design_id``: the code and what sets it apart)."""
    return reporter.design_id(entry)


def entries(session) -> List[LedgerEntry]:
    """Return the conversation's designs, the latest per id, the chosen one first."""
    latest: Dict[str, LedgerEntry] = {}
    for e in session.ledger:
        latest.pop(design_id(e), None)
        latest[design_id(e)] = e
    out = list(latest.values())
    if session.chosen is not None and design_id(session.chosen) in latest:
        chosen = latest[design_id(session.chosen)]
        out.remove(chosen)
        out.insert(0, chosen)
    return out


def find(session, design: str) -> LedgerEntry:
    """Return the design with this id, or raise ``KeyError``."""
    for e in entries(session):
        if design_id(e) == design:
            return e
    raise KeyError(design)


def assumptions_view(session) -> dict:
    """Return the conversation's prices and costs, the defaults, their units and sources."""
    defaults = asdict(dp.Prices())
    changed = {k: v for k, v in (session.assumptions or {}).items() if k in defaults}
    items = [
        {
            "key": k,
            "label": PRICE_LABELS.get(k, (k, ""))[0],
            "unit": PRICE_LABELS.get(k, (k, ""))[1],
            "group": _price_group(k),
            "value": changed.get(k, v),
            "default": v,
            "source": PRICE_SOURCES.get(k, ""),
        }
        for k, v in defaults.items()
    ]
    return dict(
        dict(defaults, **changed),
        items=items,
        defaults=defaults,
        sources={k: PRICE_SOURCES.get(k, "") for k in defaults},
        notes=[
            "Costs from dioscuri_plant (sourced per line). Shared costs (wells, pumps, produced "
            "gas) are split between heat and cold by the brine heat each side uses.",
        ],
    )


def _price_group(key: str) -> str:
    if key.endswith("_life_years"):
        return "lifetimes"
    if "_fixed_" in key or "_variable_" in key:
        return "o&m"
    if key.startswith("well_") or "_meur" in key:
        return "capital"
    return "prices"


def price_changes(assumptions: Optional[dict]) -> dict:
    """Return the changed prices and costs alone, without the investor's sale prices and SDE++.

    Only these change a design's figures; the investor's choices change only the investor's
    view, so they never mark a search as repriced or run the designs again.
    """
    return {k: v for k, v in (assumptions or {}).items() if k not in dp.investor.OVERRIDES}


def put_assumptions(session, changes: dict) -> dict:
    """Store the changed prices and costs (``None`` resets one) and return the view."""
    known = asdict(dp.Prices())
    current = dict(session.assumptions or {})
    for key, value in changes.items():
        if key in dp.investor.OVERRIDES:  # the investor's sale prices and SDE++ (checked there)
            current.pop(key, None)
            if value is not None:
                current[key] = dp.investor.override(key, value)
            continue
        if key not in known:
            raise ValueError(f"unknown assumption {key!r}")
        if value is None:
            current.pop(key, None)
        else:
            current[key] = type(known[key])(value)
    session.assumptions = current
    return assumptions_view(session)


def economics_view(entry: LedgerEntry, assumptions: dict) -> dict:
    """Return the techno-economic view of one design: lines, capital, CO₂, against gas.

    ``investor`` adds a company's view: sales, SDE++ and corporate tax (``dioscuri_plant.
    investor``, with the conversation's sale prices and SDE++ choices); the rest has neither.
    """
    entry = engine.reprice(entry, assumptions) if price_changes(assumptions) else entry
    e, y = entry.economics, entry.year
    prices = engine.prices_for(assumptions, entry.brief)
    ref = engine.reference(entry.brief, assumptions)

    def lines(raw, mwh):
        return [
            {
                "item": item,
                "kind": kind,
                "meur_per_year": round(float(m), 4),
                "eur_per_mwh": round(float(m) * 1e6 / mwh, 2) if mwh else 0.0,
            }
            for item, kind, m in (raw or [])
        ]

    versus = None
    if entry.alternative.depth_m:
        versus = engine.versus_reference(entry, ref, prices)
    # The investor's view (sales, SDE++, tax; ``dioscuri_plant.investor``): not for the gas plant,
    # whose costs set the sale prices.
    investor = None
    if entry.alternative.depth_m:
        terms = dp.investor.terms_from(assumptions)
        case = dp.investor.investor_case(
            engine.plant_of(entry.alternative),
            y,
            e,
            engine.rules_for(entry.brief),
            prices,
            ref.economics,
            terms,
        )
        investor = dp.investor.view(case, terms, ref.economics)
    # Each kind's share of the year's cost of heat and cold (capital, O&M, energy, CO2).
    kinds: Dict[str, float] = {}
    for _item, kind, m in list(e.lines_heat or []) + list(e.lines_cold or []):
        kinds[kind] = kinds.get(kind, 0.0) + float(m)
    # A revenue (the brine's gas sold) is no share of the cost: its credit is said apart.
    credit = -sum(v for v in kinds.values() if v < 0)
    kinds = {k: v for k, v in kinds.items() if v > 0}
    total = sum(kinds.values()) or 1.0
    return {
        "vs_gas_pct": engine.against_gas(entry, ref),
        "breakdown_pct": {k: round(v / total, 4) for k, v in kinds.items()},
        "credit_pct": round(credit / total, 4) if credit else None,
        "lcoh": e.lcoh_eur_per_mwh,
        "lcoc": e.lcoc_eur_per_mwh,
        "lcoe": e.lcoe_eur_per_mwh,
        "capex_meur": e.capex_meur,
        "co2_t_per_year": round(e.co2_t_per_year or 0.0, 1),
        "reference_co2_t_per_year": round(ref.economics.co2_t_per_year or 0.0, 1),
        "co2_saving_pct": round(e.co2_saving_vs_gas * 100, 1),
        "co2_t": y.co2_t,
        "lines": {
            "heat": lines(e.lines_heat, y.heat_delivered_gwh * 1000),
            "cold": lines(e.lines_cold, y.cool_delivered_gwh * 1000),
        },
        "capex_items": [
            {
                "item": it["item"],
                "size": it["size"],
                "unit": it["unit"],
                "meur_per_unit": it["meur_per_unit"],
                "meur": it["meur"],
                "life_years": it.get("life_years"),
                "note": it.get("note", ""),
            }
            for it in (e.capex_items or [])
        ],
        "versus_reference": versus,
        "investor": investor,
    }


def plant_view(entry: LedgerEntry) -> dict:
    """Return the plant's configuration and operating point."""
    y, alt, b = entry.year, entry.alternative, entry.brief
    rules = engine.rules_for(b)
    here = rules.aquifer_at(alt.depth_m) if alt.depth_m else rules  # the first doublet's aquifer
    depths = [float(x.get("depth_m") or alt.depth_m) for x in alt.doublets or []]
    p = y.plant or {}
    d = engine.doublet_summary(alt.depth_m, rules) if alt.depth_m else {}
    heating = b.heating or engine.DEFAULT_HEATING
    cooling = b.cooling or engine.DEFAULT_COOLING
    return {
        "depth_m": alt.depth_m,
        "n_doublets": alt.n_doublets if alt.depth_m else 0,
        "topup": alt.topup,
        "cooling": alt.cooling,
        "heat_pump": alt.heat_pump,
        "boiler": alt.boiler,
        "absorption": alt.absorption,
        "chillers": alt.chillers,
        "reservoir_c": y.reservoir_c,
        "wellhead_c": y.wellhead_c,
        "hex_outlet_c": y.hex_outlet_c,
        "reinjection_c": y.reinjection_c,
        "max_brine_cooling_k": y.max_brine_cooling_k,
        "flow_m3h": rules.flow_max_m3h if alt.depth_m else None,
        "flow_mean_m3h": p.get("flow_mean_m3h"),
        "esp_mw": d.get("esp_mw"),
        "esp_head_bar": d.get("esp_head_bar"),
        "injector_pump_mw": d.get("injector_pump_mw"),
        "injection_wellhead_bar": d.get("injection_wellhead_bar"),
        "hex_ua_kw_per_k": None,
        "cop": y.heat_pump_cop,
        "carnot_cop": y.heat_pump_carnot_cop,
        "transmissivity_dm": rules.permeability_md * rules.reservoir_thickness_m / 1000,
        "heating_supply_c": heating.supply_c,
        "heating_return_c": heating.return_c,
        "cooling_supply_c": cooling.supply_c,
        "cooling_return_c": cooling.return_c,
        "productivity_index_m3h_per_bar": d.get("pi_m3h_per_bar"),
        "stop_days": y.stop_days or [],
        "stop_ranges": y.stop_ranges or [[list(s)] for s in (y.stop_days or [])],
        "doublets": p.get("doublets") or [],
        "wells": p.get("wells"),
        "trains": p.get("trains"),
        "dispatch": p.get("dispatch", "equal"),
        "sizes_mw": {
            "heat_exchanger": y.hex_mw,
            "heat_pump": y.heat_pump_mw,
            "boiler": y.boiler_mw,
            "absorption": y.absorption_mw,
            "chillers": y.chiller_mw,
            **(
                {"electric_boiler": alt.sizes_mw["electric_boiler"]}
                if alt.sizes_mw.get("electric_boiler")
                else {}
            ),
        },
        "gas": alt.gas,  # buy, produced (none bought) or sell (to the grid)
        "electric_boiler_units": alt.electric_boiler_units,
        "reservoir": {
            "depth_m": alt.depth_m or rules.reservoir_depth_m,
            "temperature_c": round(rules.reservoir_temperature_c(alt.depth_m or None), 1),
            "pressure_bar": round(engine.reservoir_pressure(alt.depth_m, here), 1),
            "permeability_md": here.permeability_md,
            "thickness_m": here.reservoir_thickness_m,
            "brine_density_kg_m3": rules.brine_density_kg_m3,
            "brine_viscosity_mpa_s": rules.brine_viscosity_pa_s * 1000,
            "gas_liquid_ratio": here.gas_liquid_ratio,
        },
        # Each doublet's aquifer (its own rock and gas), when they are not all in one.
        "aquifers": (
            [
                {
                    "doublet": k,
                    "label": aquifers.label(depth, b, rules),
                    **{
                        key: float(getattr(rules.aquifer_at(depth), field))
                        for key, field in (
                            ("depth_m", "reservoir_depth_m"),
                            ("thickness_m", "reservoir_thickness_m"),
                            ("permeability_md", "permeability_md"),
                            ("gas_liquid_ratio", "gas_liquid_ratio"),
                        )
                    },
                    "depth_m": depth,
                    "pressure_bar": round(
                        engine.reservoir_pressure(depth, rules.aquifer_at(depth)), 1
                    ),
                }
                for k, depth in enumerate(depths, start=1)
            ]
            if len(set(depths)) > 1
            else []
        ),
    }


def _bank(alt, unit: str, year=None) -> dict:
    """Return how a unit is built: its equal units, each one's size, whether one can be out.

    ``n1`` is the design's own one-unit-out result (a reliable plan that still holds), not the
    unit count: a what-if with a smaller boiler keeps three units but may no longer hold.
    """
    units = int(getattr(alt, f"{unit}_units", 1) or 1)
    if units <= 1:
        return {}
    size = (alt.sizes_mw or {}).get("boiler" if unit == "boiler" else "chillers", 0.0)
    out = {
        "units": float(units),
        "unit_mw": round(size / units, 2) if size else None,
        "n1": 1.0 if alt.reliable else 0.0,
    }
    if year is not None:  # the most it gives in a day: how many units that needs (the canvas)
        side, key = ("heat", "boiler") if unit == "boiler" else ("cool", "chill")
        daily = (((year.daily_mw or {}).get(side) or {}).get(key)) or []
        if daily:
            out["most_mw"] = round(float(max(daily)), 2)
    return out


def _ranges(days: List[int]) -> List[List[int]]:
    """Return sorted days as [first, last] runs."""
    out: List[List[int]] = []
    for d in sorted(days):
        if out and d == out[-1][1] + 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    return out


def broken_days(entry: LedgerEntry) -> List[dict]:
    """Return when a design breaks a cap: heat or cold short, the brine cooled past the cap.

    Each range: ``first``, ``last`` (0-based days of 2027), ``kind`` and ``text`` ("Heat short
    by up to 4.2 MW, 9 to 21 Jan"). A cap broken over the whole year (a doublet's operating
    days) has no days and is left to the violations' list.
    """
    from gemini_agent import stops

    y = entry.year
    daily = y.daily_mw or {}
    out: List[dict] = []
    for side, word in (("heat", "Heat"), ("cool", "Cold")):
        short = list((daily.get(side) or {}).get("short") or [])
        days = [i for i, v in enumerate(short) if v > 0.01]
        for a, b in _ranges(days):
            worst = max(short[a : b + 1])
            out.append(
                {
                    "first": a,
                    "last": b,
                    "kind": f"{side}_short",
                    "text": f"{word} short by up to {reporter.num(worst, 2)} MW, "
                    f"{stops.span_words([[a, b]])}",
                }
            )
    limit = engine.rules_for(entry.brief).max_brine_cooling_k
    for k, d in enumerate(y.doublets or []):
        wh, rj = d.get("wellhead_c") or [], d.get("reinjection_c") or []
        days = [
            i
            for i, (a, b) in enumerate(zip(wh, rj))
            if a is not None and b is not None and a - b > limit + 0.05
        ]
        for a, b in _ranges(days):
            out.append(
                {
                    "first": a,
                    "last": b,
                    "kind": "brine",
                    "text": f"Doublet {k + 1}'s brine cooled by more than "
                    f"{reporter.num(limit, 0)} K, {stops.span_words([[a, b]])}",
                }
            )
    return sorted(out, key=lambda r: r["first"])


def graph_view(entry: LedgerEntry) -> dict:
    """Return the plant as the Design tab draws it: reservoir, doublets, surface plant, demand."""
    y, alt = entry.year, entry.alternative
    rules = engine.rules_for(entry.brief)
    n = alt.n_doublets if alt.depth_m else 0
    nodes, edges = [], []

    def node(id_, type_, label, slv, values, units):
        nodes.append(
            {
                "id": id_,
                "type": type_,
                "label": label,
                "solver": slv,
                "values": {k: round(v, 3) for k, v in values.items() if v is not None},
                "units": units,
            }
        )

    def edge(src, dst, kind, mw=None, temp=None, label=""):
        edges.append(
            {
                "id": f"{src}-{dst}",
                "source": src,
                "target": dst,
                "kind": kind,
                "mw": None if mw is None else round(mw, 2),
                "temperature_c": None if temp is None else round(temp, 1),
                "label": label,
            }
        )

    split = y.heat_split_gwh
    hours = 8760 / 1000
    rows = (y.plant or {}).get("doublets") or []
    specs = alt.doublets or [
        {
            "depth_m": alt.depth_m,
            "producer_open": "full",
            "injector_open": "full",
            "injectors": 1,
            "train": 0,
        }
        for _ in range(n)
    ]
    trains = sorted({int(d.get("train") or 0) for d in specs}) if n else []
    injector_ids: List[str] = []
    train_ids = [f"train_{k + 1}" for k in range(len(trains))]
    if n:
        depths = sorted({float(d.get("depth_m") or alt.depth_m) for d in specs})
        known = all(abs(d - rules.reservoir_depth_m) < 1e-6 for d in depths)
        main = depths[0] if known else max(depths)
        d0 = engine.doublet_summary(main, rules)
        node(
            "reservoir",
            "reservoir",
            (
                "Reservoir"
                if known
                else "Assumed aquifer at " + " and ".join(f"{d:,.0f} m" for d in depths)
            ),
            "gemini",
            {
                "depth_m": main,
                "temperature_c": rules.reservoir_temperature_c(main),
                "pressure_bar": engine.reservoir_pressure(main, rules),
                "permeability_md": rules.permeability_md,
                "thickness_m": rules.reservoir_thickness_m,
                "pi_m3h_per_bar": d0["pi_m3h_per_bar"],
                # The aquifer the requirements describe; a deeper design assumes the same rock
                # there, with hydrostatic pressure and the gradient's temperature.
                "known_depth_m": rules.reservoir_depth_m,
                "known_temperature_c": rules.reservoir_temperature_c(),
                "assumed": 0.0 if known else 1.0,
                "doublets": n,
            },
            {
                "depth_m": "m",
                "temperature_c": "°C",
                "pressure_bar": "bar",
                "permeability_md": "mD",
                "thickness_m": "m",
                "pi_m3h_per_bar": "m³/h/bar",
                "known_depth_m": "m",
                "known_temperature_c": "°C",
                "assumed": "",
                "doublets": "",
            },
        )
        for i, d in enumerate(specs):
            row = rows[i] if i < len(rows) else {}
            pid = f"producer_{i + 1}"
            p_open = str(d.get("producer_open") or "full")
            node(
                pid,
                "producer_well",
                f"Producer {i + 1}" + ("" if p_open == "full" else f", {p_open} half open"),
                "gemini",
                {
                    "doublet": i + 1,
                    "depth_m": row.get("producer_mid_m", d.get("depth_m")),
                    "open_m": row.get("producer_open_m"),
                    "rock_c": row.get("rock_c"),
                    "wellhead_c": row.get("wellhead_full_c", y.wellhead_c),
                    "wellhead_min_c": row.get("wellhead_min_c"),
                    "flow_m3h": row.get("cap_m3h", rules.flow_max_m3h),
                    "flow_mean_m3h": row.get("flow_mean_m3h"),
                    "days_on": row.get("days_on"),
                    "esp_head_bar": row.get("esp_head_full_bar", d0["esp_head_bar"]),
                    "esp_gwh": row.get("esp_gwh"),
                    "pi_m3h_per_bar": row.get("pi_m3h_per_bar"),
                },
                {
                    "doublet": "",
                    "depth_m": "m TVD",
                    "open_m": "m open",
                    "rock_c": "°C",
                    "wellhead_c": "°C at full flow",
                    "wellhead_min_c": "°C at its lowest flow",
                    "flow_m3h": "m³/h max",
                    "flow_mean_m3h": "m³/h mean",
                    "days_on": "days",
                    "esp_head_bar": "bar",
                    "esp_gwh": "GWh/yr",
                    "pi_m3h_per_bar": "m³/h/bar",
                },
            )
            edge("reservoir", pid, "brine", temp=row.get("rock_c"))
            k = trains.index(int(d.get("train") or 0))
            edge(pid, train_ids[k], "brine", temp=row.get("wellhead_full_c", y.wellhead_c))
            count = int(d.get("injectors") or 1)
            i_open = str(d.get("injector_open") or "full")
            for j in range(count):
                letter = "" if count == 1 else "ab"[j]
                iid = f"injector_{i + 1}{letter}"
                node(
                    iid,
                    "injector_well",
                    f"Injector {i + 1}{letter.upper()}"
                    + ("" if i_open == "full" else f", {i_open} half open"),
                    "gemini",
                    {
                        "doublet": i + 1,
                        "depth_m": row.get("injector_mid_m", d.get("depth_m")),
                        "open_m": row.get("injector_open_m"),
                        "reinjection_c": y.reinjection_c,
                        "wellhead_bar": row.get("injection_full_bar"),
                        "pump_gwh": (row.get("injection_gwh") or 0.0) / count,
                        "flow_mean_m3h": (row.get("flow_mean_m3h") or 0.0) / count,
                    },
                    {
                        "doublet": "",
                        "depth_m": "m TVD",
                        "open_m": "m open",
                        "reinjection_c": "°C",
                        "wellhead_bar": "bar at full flow",
                        "pump_gwh": "GWh/yr",
                        "flow_mean_m3h": "m³/h mean",
                    },
                )
                edge(iid, "reservoir", "brine", temp=y.reinjection_c)
                injector_ids.append(iid)
        gas_total = (y.produced_gas_burned_gwh or 0.0) + (y.produced_gas_flared_gwh or 0.0)
        brine_total = sum(float(r.get("brine_m3") or 0.0) for r in rows) or 1.0
        for k, t in enumerate(trains):
            members = [i + 1 for i, d in enumerate(specs) if int(d.get("train") or 0) == t]
            share = (
                sum(float(rows[i - 1].get("brine_m3") or 0.0) for i in members if i - 1 < len(rows))
                / brine_total
                if rows
                else 1.0 / len(trains)
            )
            node(
                train_ids[k],
                "treatment",
                "Treatment train" + (f" {k + 1}" if len(trains) > 1 else ""),
                "gemini",
                {"doublets": len(members), "gas_gwh": gas_total * share},
                {"doublets": "", "gas_gwh": "GWh/yr of gas separated"},
            )
        if y.absorption_mw:
            node(
                "absorption",
                "absorption",
                "Absorption chiller",
                "dioscuri",
                {"power_mw": y.absorption_mw, "cold_gwh": y.cool_split_gwh["abs"]},
                {"power_mw": "MW", "cold_gwh": "GWh/yr"},
            )
            for t_id in train_ids:
                edge(t_id, "absorption", "brine", temp=y.wellhead_c, label="drive")
        node(
            "hex",
            "heat_exchanger",
            "Heat exchanger",
            "dioscuri",
            {"power_mw": y.hex_mw, "network_out_c": y.hex_outlet_c, "heat_gwh": split["geo"]},
            {"power_mw": "MW", "network_out_c": "°C", "heat_gwh": "GWh/yr"},
        )
        for t_id in train_ids:
            edge(t_id, "hex", "brine", temp=y.wellhead_c)
        last = "hex"
        if y.heat_pump_mw:
            node(
                "heat_pump",
                "heatpump",
                "Heat pump",
                "dioscuri",
                {"power_mw": y.heat_pump_mw, "cop": y.heat_pump_cop, "heat_gwh": split["hp"]},
                {"power_mw": "MW", "cop": "", "heat_gwh": "GWh/yr"},
            )
            edge(last, "heat_pump", "brine", label="source")
            last = "heat_pump"
        for iid in injector_ids:
            edge(last, iid, "brine", temp=y.reinjection_c)
    # What the plant does with gas: buys it for the boiler, burns only the brine's own (no gas
    # bought), or cleans the brine's gas and sells it to the gas grid (nothing burnt on site).
    gas_mode = getattr(alt, "gas", "buy") or "buy"
    selling = gas_mode == "sell" and bool(train_ids)
    co2 = y.co2_t or {}
    if y.boiler_mw or selling:
        if selling:
            # The buyer burns the methane: its CO2 is the buyer's, not in this plant's total;
            # the CO2 separated from the gas is let out here and is in it.
            label = "Gas sold to the grid"
            gas_values = {
                "sold_gwh": y.produced_gas_sold_gwh or 0.0,
                "buyer_co2_t": co2.get("sold_gas_elsewhere", 0.0),
                "vented_co2_t": co2.get("produced_gas", 0.0),
                "bought_gwh": y.purchased_gas_gwh or 0.0,
            }
        else:
            flare_all = bool(engine.rules_for(entry.brief).flare_brine_gas)
            label = (
                "Gas bought (the brine's flared)"
                if flare_all
                else "Gas from the brine" if gas_mode == "produced" else "Gas"
            )
            gas_values = {
                "produced_gwh": y.produced_gas_burned_gwh,
                "bought_gwh": y.purchased_gas_gwh,
                "flared_gwh": y.produced_gas_flared_gwh,
            }
            if flare_all:  # the switch: all the brine's gas flared, the boiler's all bought
                gas_values["flare_all"] = 1.0
        node(
            "gas",
            "gas",
            label,
            "dioscuri",
            gas_values,
            {
                "produced_gwh": "GWh/yr",
                "bought_gwh": "GWh/yr",
                "flared_gwh": "GWh/yr",
                "sold_gwh": "GWh/yr of methane",
                "buyer_co2_t": "t CO₂/yr, not counted",
                "vented_co2_t": "t CO₂/yr, counted",
            },
        )
        nodes[-1]["gas"] = gas_mode
        for t_id in train_ids:
            edge(t_id, "gas", "gas", label="separated gas")
    if y.boiler_mw:
        node(
            "boiler",
            "boiler",
            "Gas boiler",
            "dioscuri",
            {"power_mw": y.boiler_mw, "heat_gwh": split["boiler"], **_bank(alt, "boiler", y)},
            {"power_mw": "MW", "heat_gwh": "GWh/yr", "units": "equal units", "unit_mw": "MW"},
        )
        if not selling:
            edge("gas", "boiler", "gas")
    el = y.electricity_gwh or {}
    eboiler_mw = (alt.sizes_mw or {}).get("electric_boiler", 0.0)
    if eboiler_mw:
        units = getattr(alt, "electric_boiler_units", 1) or 1
        node(
            "electric_boiler",
            "electric_boiler",
            "Electric boiler",
            "dioscuri",
            {
                "power_mw": eboiler_mw,
                "units": float(units) if units > 1 else None,
                "heat_gwh": split.get("electric_boiler", 0.0),
                "electricity_gwh": el.get("electric_boiler", 0.0),
            },
            {
                "power_mw": "MW",
                "units": "equal units",
                "heat_gwh": "GWh/yr",
                "electricity_gwh": "GWh/yr from the grid",
            },
        )
    if y.chiller_mw:
        node(
            "chillers",
            "chillers",
            "Electric chillers",
            "dioscuri",
            {
                "power_mw": y.chiller_mw,
                "cold_gwh": y.cool_split_gwh["chill"],
                "cop": y.chiller_cop,
                **_bank(alt, "chiller", y),
            },
            {"power_mw": "MW", "cold_gwh": "GWh/yr", "cop": "", "units": "equal units"},
        )
    el_total = sum(v for v in el.values() if v)
    if el_total > 0 or eboiler_mw:
        # Every electric unit draws from the grid: shown, so no unit looks unconnected.
        node(
            "grid",
            "grid",
            "Grid electricity",
            "dioscuri",
            {
                "electricity_gwh": el_total,
                "chillers_gwh": el.get("chillers", 0.0),
                "pumps_gwh": el.get("pumps", 0.0),
                "heat_pump_gwh": el.get("hp", 0.0),
                "towers_gwh": el.get("towers", 0.0),
                "electric_boiler_gwh": el.get("electric_boiler") or None,
                "co2_t": (y.co2_t or {}).get("electricity", 0.0),
            },
            {
                "electricity_gwh": "GWh/yr",
                "chillers_gwh": "GWh/yr",
                "pumps_gwh": "GWh/yr",
                "heat_pump_gwh": "GWh/yr",
                "towers_gwh": "GWh/yr",
                "electric_boiler_gwh": "GWh/yr",
                "co2_t": "t CO₂/yr",
            },
        )
    rejected = (y.cool_split_gwh.get("chill", 0.0) + el.get("chillers", 0.0)) + (
        y.cool_split_gwh.get("abs", 0.0) * (1 + 1 / y.absorption_cop) if y.absorption_cop else 0.0
    )
    free = y.cool_split_gwh.get("free", 0.0)
    if rejected > 0 or free > 0:
        values = {"rejected_gwh": rejected, "electricity_gwh": el.get("towers", 0.0)}
        units = {"rejected_gwh": "GWh/yr", "electricity_gwh": "GWh/yr"}
        if free > 0:  # free cooling: the towers cool the network directly on cool days
            values["free_cooling_gwh"] = free
            units["free_cooling_gwh"] = "GWh/yr"
        node("tower", "tower", "Cooling towers", "dioscuri", values, units)
        if y.chiller_mw:
            edge(
                "chillers",
                "tower",
                "reject",
                mw=(y.cool_split_gwh["chill"] + el.get("chillers", 0.0)) / hours,
                label="heat out",
            )
        if y.absorption_mw and y.absorption_cop:
            edge(
                "absorption",
                "tower",
                "reject",
                mw=y.cool_split_gwh["abs"] * (1 + 1 / y.absorption_cop) / hours,
                label="heat out",
            )
    if el_total > 0:
        for target, key in (
            ("chillers", "chillers"),
            ("heat_pump", "hp"),
            ("tower", "towers"),
        ):
            if el.get(key) and any(nd["id"] == target for nd in nodes):
                edge(
                    "grid", target, "electricity", mw=el[key] / hours, label=f"{el[key]:.1f} GWh/yr"
                )
    if eboiler_mw:
        # Drawn even in a year it never runs: it is wired to the grid all the same.
        gwh = el.get("electric_boiler", 0.0) or 0.0
        edge("grid", "electric_boiler", "electricity", mw=gwh / hours, label=f"{gwh:.1f} GWh/yr")
    if el_total > 0:
        # The ESP and the injection pumps of each doublet.
        for i in range(n):
            row = rows[i] if i < len(rows) else {}
            gwh = (row.get("esp_gwh") or 0.0) + (row.get("injection_gwh") or 0.0)
            if not rows and el.get("pumps"):
                gwh = el["pumps"] / max(n, 1)
            if gwh > 0:
                edge(
                    "grid",
                    f"producer_{i + 1}",
                    "electricity",
                    mw=gwh / hours,
                    label=f"{gwh:.1f} GWh/yr, pumps",
                )
    node(
        "demand_heat",
        "demand_heat",
        "Heat demand",
        "dioscuri",
        {
            "peak_mw": y.peak_heat_mw,
            "heat_gwh": y.heat_demand_gwh,
            "covered_pct": y.heat_coverage * 100,
        },
        {"peak_mw": "MW", "heat_gwh": "GWh/yr", "covered_pct": "%"},
    )
    heating = entry.brief.heating or engine.DEFAULT_HEATING
    for src, gwh in (
        ("hex", split["geo"]),
        ("heat_pump", split["hp"]),
        ("boiler", split["boiler"]),
        ("electric_boiler", split.get("electric_boiler", 0.0)),
    ):
        if any(nd["id"] == src for nd in nodes):
            edge(
                src,
                "demand_heat",
                "network",
                mw=gwh / hours,
                temp=heating.supply_c,
                label=f"{gwh:.1f} GWh/yr",
            )
    if y.cool_demand_gwh:
        node(
            "demand_cold",
            "demand_cold",
            "Cooling demand",
            "dioscuri",
            {
                "peak_mw": y.peak_cool_mw,
                "cold_gwh": y.cool_demand_gwh,
                "covered_pct": y.cool_coverage * 100,
            },
            {"peak_mw": "MW", "cold_gwh": "GWh/yr", "covered_pct": "%"},
        )
        cooling = entry.brief.cooling or engine.DEFAULT_COOLING
        for src, gwh in (
            ("tower", y.cool_split_gwh.get("free", 0.0)),
            ("absorption", y.cool_split_gwh["abs"]),
            ("chillers", y.cool_split_gwh["chill"]),
        ):
            if src == "tower" and gwh <= 0:
                continue
            if any(nd["id"] == src for nd in nodes):
                edge(
                    src,
                    "demand_cold",
                    "cold",
                    mw=gwh / hours,
                    temp=cooling.supply_c,
                    label=f"{gwh:.1f} GWh/yr",
                )
    project = None
    if n:
        from gemini_agent.tools import gemini as gem_tools

        project = gem_tools.plant_project(specs, rules, boiler_mw=alt.sizes_mw.get("boiler", 0.0))
    return {"nodes": nodes, "edges": edges, "gemini_project": project}


ORIGINS = {"chosen": "agent", "candidate": "agent", "what_if": "what_if", "user": "user"}


def design_view(session, entry: LedgerEntry, daily: bool = True) -> dict:
    """Return one design as the tabs show it (contract ``Design``)."""
    y = entry.year
    if daily and y.daily_mw is None:
        entry = engine.reprice(entry, session.assumptions or {})
        y = entry.year
    meta = (session.user_designs or {}).get(entry.alternative.code, {})
    origin = "user" if meta else ORIGINS.get(entry.alternative.role, "agent")
    if (entry.brief.reservoir_delta_c or entry.changes) and origin == "agent":
        origin = "what_if"
    parent = meta.get("parent")
    if origin == "what_if" and parent is None:
        parent = entry.alternative.parent or entry.alternative.code.split(" ")[0]
    if origin == "agent" and entry.alternative.parent:
        parent = entry.alternative.parent  # a second-stage variant of the search
    year = {
        k: getattr(y, k)
        for k in (
            "heat_demand_gwh",
            "cool_demand_gwh",
            "heat_delivered_gwh",
            "cool_delivered_gwh",
            "heat_coverage",
            "cool_coverage",
            "heat_split_gwh",
            "cool_split_gwh",
            "peak_heat_mw",
            "peak_cool_mw",
            "full_load_hours",
            "monthly_gwh",
            "daily_mw",
            "violations",
            "electricity_gwh",
            "purchased_gas_gwh",
            "produced_gas_burned_gwh",
            "produced_gas_flared_gwh",
            "produced_gas_sold_gwh",
            "co2_t",
            "co2_by_unit_t",
            "stop_days",
            "stop_ranges",
            "doublets",
        )
    }
    graph = graph_view(entry)
    return {
        "id": design_id(entry),
        "uid": entry.alternative.uid,
        "picks": list(entry.alternative.picks),
        "reliable": entry.alternative.reliable,
        "code": entry.alternative.code,
        "name": meta.get("name") or entry.alternative.name,
        "origin": origin,
        "role": entry.alternative.role,
        "parent": parent,
        "attempt": entry.alternative.attempt,
        "chosen": session.chosen is not None and design_id(session.chosen) == design_id(entry),
        "reservoir_delta_c": entry.brief.reservoir_delta_c or 0.0,
        "changes": entry.changes,
        "change_label": entry.change_label,
        "flags": entry.alternative.flags,
        "stage": entry.alternative.stage,
        "dispatch": entry.alternative.dispatch,
        "doublets": entry.alternative.doublets,
        "sizings": entry.alternative.sizings,
        "warnings": list(y.warnings or []),
        "source": y.source,
        "verified": entry.verification.passed,
        "checks": [
            {"name": c.name, "passed": c.passed, "detail": c.detail, "requirement": c.requirement}
            for c in entry.verification.checks
        ],
        "rounds": entry.alternative.rounds,
        "plant": plant_view(entry),
        "year": year,
        "economics": economics_view(entry, session.assumptions or {}),
        "graph": graph,
        # When a cap is broken, as day ranges (the year strip's red bands; 5 Nov: the Design
        # tab read them, but only the Compare tab's rows had them).
        "broken_days": broken_days(entry),
        # What goes wrong in the year, part by part (the canvas's alerts and its issues list).
        "issues": issues.design_issues(entry, graph, getattr(session, "failures", None)),
        "provenance": {
            "plant": "gemini" if entry.alternative.depth_m else "dioscuri",
            "year": "dioscuri",
            "economics": "dioscuri",
            "cooling": "dioscuri",
        },
    }


def candidate_row(entry: LedgerEntry) -> dict:
    """Return a candidate of the last search as the Compare tab lists it."""
    a, e, y = entry.alternative, entry.economics, entry.year
    return {
        "code": a.code,
        "uid": a.uid,
        "id": design_id(entry),
        "picks": list(a.picks),
        "reliable": a.reliable,
        "name": a.name,
        "role": a.role,
        "reason": a.reason,
        "n_doublets": a.n_doublets if a.depth_m else 0,
        "depth_m": a.depth_m,
        "topup": a.topup,
        "cooling": a.cooling,
        "sizes_mw": a.sizes_mw,
        "lcoh": e.lcoh_eur_per_mwh,
        "lcoc": e.lcoc_eur_per_mwh,
        "lcoe": e.lcoe_eur_per_mwh,
        "co2_t": e.co2_t_per_year,
        "co2_saving_pct": round(e.co2_saving_vs_gas * 100, 1),
        "capex_meur": e.capex_meur,
        "heat_coverage_pct": round(y.heat_coverage * 100, 1),
        "cool_coverage_pct": round(y.cool_coverage * 100, 1),
        "rounds": len(a.rounds),
        "changes": [r["change"] for r in a.rounds if r.get("change")],
        "violations": list(y.violations),
        # The days a cap is broken, as ranges, for the Design tab's red bands (2 Nov).
        "broken_days": broken_days(entry),
        "verified": entry.verification.passed,
        "failed": [c.name for c in entry.verification.checks if not c.passed],
        "attempt": a.attempt,
        "flags": a.flags,
        "stage": a.stage,
        "parent": a.parent,
        "dispatch": a.dispatch,
        "doublets": a.doublets,
        "wells": (y.plant or {}).get("wells"),
        "trains": (y.plant or {}).get("trains"),
        "sizings": len(a.sizings),
    }


def scenario_of(srch: dict, n: int, first: Optional[dict] = None) -> dict:
    """Return a search's scenario: the base case, a what-if (its change) or another search.

    Its run's letter (the designs' handles start with it, A1) and name come with it.
    """
    from gemini_agent import naming

    label = srch.get("label", "")
    run = {"letter": naming.letter(n), "name": naming.run_name(srch, n, first)}
    if label.startswith("what-if: "):
        what = label[len("what-if: ") :].split(" · ")[0]
        return {"id": srch["id"], "n": n, "kind": "what_if", "label": f"What-if: {what}", **run}
    return {
        "id": srch["id"],
        "n": n,
        "kind": "base" if n == 1 else "search",
        "label": "Base case" if n == 1 else f"Search {n}: {label}",
        **run,
    }


def with_names(session, rows: List[dict]) -> List[dict]:
    """Add to each design what it is in words (or the user's name for it) and its star."""
    from gemini_agent import naming

    names = dict(session.design_names or {})
    labels: Dict[str, str] = {}
    for srch in session.searches or []:
        for e in srch.get("candidates") or []:
            labels.setdefault(design_id(e), naming.design_label(e, names))
    for e in session.ledger:
        labels[design_id(e)] = naming.design_label(e, names)
    starred = set(session.starred or [])
    return [
        dict(
            r,
            label=labels.get(r["id"], r.get("name", "")),
            user_name=names.get(r["id"]),
            starred=r["id"] in starred,
        )
        for r in rows
    ]


def library_row(entry: LedgerEntry, scenario: dict, ref: Optional[LedgerEntry], session) -> dict:
    """Return one design as the Compare tab's library lists it (contract ``LibraryRow``)."""
    from gemini_agent import reporter

    row = candidate_row(entry)
    prices = engine.prices_for(session.assumptions or None, entry.brief)
    firm = reporter.firm_view(entry) if entry.alternative.n_doublets else None
    worst = None
    if firm:
        short = [c for c in firm["cases"] if c["short"]]
        if short:
            w = max(short, key=lambda c: c["worst_mw"])
            worst = {
                "unit": w["unit"],
                "side": w["side"],
                "mw": w["worst_mw"],
                "day": w["worst_day"],
            }
    ids = {design_id(e) for e in session.ledger}
    row.update(
        {
            "id": design_id(entry),
            "scenario": scenario,
            # The design it came from: a what-if's base, your design's original, a variant's.
            "parent": entry.alternative.parent or None,
            "origin": (
                "user"
                if entry.alternative.role == "user"
                else "what_if" if entry.alternative.role == "what_if" else "agent"
            ),
            "recommended": session.chosen is not None
            and design_id(session.chosen) == design_id(entry),
            "in_tabs": design_id(entry) in ids,
            "vs_gas_pct": engine.against_gas(entry, ref) if ref is not None else None,
            "money": (
                {
                    k: v
                    for k, v in engine.versus_reference(entry, ref, prices).items()
                    if k != "cash_flow_meur"
                }
                if ref is not None and entry.alternative.depth_m
                else None
            ),
            "firm": (
                {
                    "cases": len(firm["cases"]),
                    "short": firm["short"],
                    "worst": worst,
                    "spare_heat_mw": ((firm.get("peak") or {}).get("heat") or {}).get("spare_mw"),
                    "spare_cool_mw": ((firm.get("peak") or {}).get("cool") or {}).get("spare_mw"),
                }
                if firm
                else None
            ),
        }
    )
    return row


def library_view(session) -> List[dict]:
    """Return every design of the conversation, each with its scenario, money and reliability.

    Each search's candidates and every what-if and user design, with the cost against gas. After
    the Economics tab changes a price, every design is run again under the new prices (about
    3 ms each, without the one-unit-out years, which prices do not change), so a row's figures
    and its money are at one set of prices; the picks stay those the search made.

    The Compare tab filters, sorts, selects and compares them; designs not yet in the tabs open
    with ``open_design``.
    """
    a = price_changes(session.assumptions)
    keys = [design_id(e) for s in session.searches or [] for e in s.get("candidates") or []]
    keys += [design_id(e) for e in session.ledger]
    chosen = design_id(session.chosen) if session.chosen is not None else ""
    key = json.dumps(a, sort_keys=True) + chosen + "|".join(keys)
    cached = getattr(session, "_library", None)
    if cached and cached[0] == key:
        return cached[1]
    refs: dict = {}

    def priced(e: LedgerEntry) -> LedgerEntry:
        if not a:
            return e
        new = engine.reprice(e, a, with_firm=False)
        return new.model_copy(
            update={
                "alternative": e.alternative,
                "firm": e.firm,
                "gemini": e.gemini,
                "changes": e.changes,
                "change_label": e.change_label,
            }
        )

    def reference(e: LedgerEntry, ref: Optional[LedgerEntry]) -> Optional[LedgerEntry]:
        if not a and ref is not None:
            return ref
        k = e.brief.model_dump_json()
        if k not in refs:
            refs[k] = engine.reference(e.brief, a or None)
        return refs[k]

    rows: List[dict] = []
    seen = set()
    for i, srch in enumerate(session.searches or []):
        scenario = dict(scenario_of(srch, i + 1, session.searches[0]), repriced=bool(a))
        for e in srch.get("candidates") or []:
            if e.alternative.role == "same":
                continue
            k = design_id(e)
            if k in seen:
                continue
            seen.add(k)
            rows.append(
                library_row(priced(e), scenario, reference(e, srch.get("reference")), session)
            )
    first = (session.searches or [None])[0]
    by_id = {s["id"]: (s, i + 1, first) for i, s in enumerate(session.searches or [])}
    briefs = {
        design_id(e): e.brief for s in session.searches or [] for e in s.get("candidates") or []
    }
    by_design = {r["id"]: r["scenario"] for r in rows}
    for e in session.ledger:
        k = design_id(e)
        briefs.setdefault(k, e.brief)
        if k in seen:
            continue
        seen.add(k)
        scenario = dict(_ledger_scenario(e, by_id, by_design, briefs), repriced=bool(a))
        by_design[k] = scenario
        rows.append(library_row(priced(e), scenario, reference(e, None), session))
    session._library = (key, rows)
    return rows


def _ledger_scenario(e: LedgerEntry, by_id: dict, by_design: dict, briefs: dict) -> dict:
    """Return the scenario a what-if or a user design belongs to.

    A what-if belongs to the search run under the same change (``attempt``); your design to its
    parent's scenario when it ran under the same conditions (only its plant was edited), so it
    is ranked with the designs it came from.
    """
    a = e.alternative
    if a.attempt in by_id and a.role == "what_if":
        return scenario_of(*by_id[a.attempt])
    if a.role == "user":
        parent, brief = by_design.get(a.parent), briefs.get(a.parent)
        if parent and brief is not None and brief.model_dump() == e.brief.model_dump():
            return parent
        return {"id": "user", "n": 0, "kind": "user", "label": "Your designs"}
    what = e.change_label or "what-if"
    return {"id": f"w:{what}", "n": 0, "kind": "what_if", "label": f"What-if: {what}"}


def set_meta(session, design: str, name: Optional[str], starred: Optional[bool]) -> None:
    """Set a design's own name ("" takes it away) and its star.

    Raises
    ------
    KeyError
        When the conversation has no such design.
    ValueError
        When the name is too long.
    """
    known = {design_id(e) for e in session.ledger} | {
        design_id(e) for s in session.searches or [] for e in s.get("candidates") or []
    }
    if design not in known:
        raise KeyError(design)
    if name is not None:
        clean = " ".join(str(name).split())
        if len(clean) > 60:
            raise ValueError("a name of at most 60 characters")
        if clean:
            session.design_names[design] = clean
        else:
            session.design_names.pop(design, None)
    if starred is not None:
        stars = [x for x in session.starred if x != design]
        session.starred = stars + [design] if starred else stars


SWEEP_ID = re.compile(r"^(S\d+)·sweep·(\d+)$")


def sweep_entry(session, design: str) -> LedgerEntry:
    """Return a design drawn in a search's design-space sweep as a ledger entry (``S1·sweep·12``).

    The sweep keeps each drawn design as one row (its doublets, depth, flow cap, unit sizes and
    gas): it is built again as drawn, run for its year and priced like any design; its handle
    is ``X`` and its row (``X13``).
    """
    from dioscuri_plant import explore
    from dioscuri_plant.search import Candidate, Round

    m = SWEEP_ID.match(design or "")
    srch = next((s for s in session.searches or [] if m and s["id"] == m.group(1)), None)
    if srch is None or not srch.get("sweep"):
        raise KeyError(design)
    sweep = srch["sweep"]
    k = int(m.group(2))
    if not 0 <= k < len(sweep["rows"]):
        raise KeyError(design)
    r = dict(zip(sweep["columns"], sweep["rows"][k]))
    n = int(r["doublets"])
    plant = dp.Plant(
        n,
        depth_m=float(r["depth_m"]),
        doublet_specs=tuple(
            dp.Doublet(depth_m=float(r["depth_m"]), max_flow_m3h=float(r["flow_cap_m3h"]))
            for _ in range(n)
        ),
        gas=str(r["gas"]),
        heat_pump_mw=float(r["heat_pump_mw"]),
        boiler_mw=float(r["boiler_mw"]),
        electric_boiler_mw=float(r["electric_boiler_mw"]),
        absorption_mw=float(r["absorption_mw"]),
        chiller_mw=float(r["chiller_mw"]),
    )
    brief = DesignBrief(**srch["brief"])
    rules = engine.rules_for(brief)
    prices = engine.prices_for(session.assumptions, brief)
    year = dp.simulate_year(plant, engine.demand_of(brief), engine.doublet_model(rules), rules)
    econ = dp.economics(plant, year, prices, rules=rules)
    cand = Candidate(
        explore.topology_of(plant, rules.reservoir_depth_m),
        [Round(plant, [], f"drawn in the design-space sweep of {srch['id']} (row {k + 1})")],
        year,
        econ,
        stage=3,
        effect="drawn in the design-space sweep, as drawn",
    )
    entry = engine.to_entry(cand, brief, rules, None)
    full = engine.reprice(entry, session.assumptions or {})
    full.alternative.attempt = srch["id"]
    full.alternative.uid = f"X{k + 1}"
    full.alternative.name = f"drawn design {k + 1} of the sweep: {full.alternative.name}"
    return full


def open_design(session, design: str) -> dict:
    """Bring a design of any search into the tabs (it runs again with its daily series)."""
    for e in session.ledger:
        if design_id(e) == design or (
            SWEEP_ID.match(design or "") and e.alternative.sweep_id == design
        ):
            return design_view(session, e)
    if SWEEP_ID.match(design or ""):
        full = sweep_entry(session, design)
        full.alternative.sweep_id = design
        session.ledger.append(full)
        return design_view(session, full)
    for srch in reversed(session.searches or []):
        for e in srch.get("candidates") or []:
            if design_id(e) == design and e.alternative.role != "same":
                full = engine.reprice(e, session.assumptions or {})
                full.alternative.attempt = e.alternative.attempt
                full.alternative.uid = e.alternative.uid
                full.alternative.picks = list(e.alternative.picks)
                session.ledger.append(full)
                return design_view(session, full)
    raise KeyError(design)


def attempts_view(session) -> List[dict]:
    """Return every design search of the conversation, newest first, each with its candidates.

    The latest search is priced at the conversation's prices (``repriced_search``); the earlier
    ones keep the prices of their day, and say so (``repriced``).
    """
    from gemini_agent import naming

    latest, latest_ref = repriced_search(session)
    out = []
    for i, srch in enumerate(session.searches or []):
        last = i == len(session.searches) - 1
        cands = latest if last else [e for e in srch["candidates"] if e.alternative.role != "same"]
        ref = latest_ref if last else srch.get("reference")
        cands = sorted(
            cands,
            key=lambda e: (
                e.alternative.role != "chosen",
                e.alternative.role == "failed",
                e.economics.lcoe_eur_per_mwh or 0.0,
            ),
        )
        out.append(
            {
                "id": srch["id"],
                "n": i + 1,
                "letter": naming.letter(i + 1),
                "name": naming.run_name(srch, i + 1, session.searches[0]),
                "at": srch.get("at"),
                "message": srch.get("message", ""),
                "label": srch.get("label", ""),
                "objective": srch.get("objective", "cost"),
                "chosen": srch.get("chosen"),
                "repriced": bool(last and price_changes(session.assumptions)),
                "layouts": srch.get("layouts", len(srch.get("candidates") or [])),
                "sizings": srch.get("sizings", 0),
                "years": srch.get("years", 0),
                "candidates": [candidate_row(e) for e in cands],
                "reference": candidate_row(ref) if ref is not None else None,
                # The sweep's size only; its designs come from ``/api/sweep`` (the map).
                "swept": (
                    {
                        "designs": len(srch["sweep"]["rows"]),
                        "feasible": srch["sweep"].get("feasible", 0),
                    }
                    if (srch.get("sweep") or {}).get("rows")
                    else None
                ),
            }
        )
    return list(reversed(out))


def sweep_view(session, search_id: Optional[str] = None) -> Optional[dict]:
    """Return a search's design-space sweep for the map, with the search's own designs on it.

    ``marks``: each candidate the search kept (its handle, code, cost, CO2 saving, role and
    picks), so the map shows where the picks sit among the thousands drawn.
    """
    from gemini_agent import naming

    found = [
        (i, s)
        for i, s in enumerate(session.searches or [])
        if s.get("sweep") and (search_id is None or s["id"] == search_id)
    ]
    if not found:
        return None
    i, srch = found[-1]
    marks = []
    for e in srch.get("candidates") or []:
        a, econ = e.alternative, e.economics
        if a.role in ("same", "failed") or econ is None:
            continue
        marks.append(
            {
                "id": design_id(e),
                "uid": a.uid or a.code,
                "code": a.code,
                "lcoe": econ.lcoe_eur_per_mwh,
                "co2_t": round(econ.co2_t_per_year, 0),
                "co2_saving_pct": round((econ.co2_saving_vs_gas or 0.0) * 100, 1),
                "role": a.role,
                "picks": list(a.picks or []),
                "reliable": bool(a.reliable),
                "swept": a.stage == 3 and "sweep" in (a.effect or "") + (a.reason or ""),
            }
        )
    return dict(
        srch["sweep"],
        search={"id": srch["id"], "name": naming.run_name(srch, i + 1, session.searches[0])},
        marks=marks,
    )


def repriced_search(session) -> tuple:
    """Return the last search's candidates and the gas reference under the conversation's prices.

    The search priced them with the prices of its day; after the Economics tab changes one, each
    is run again under the new prices (about 10 ms each), and each loser's reason is said again
    against the chosen one. Kept on the session until the prices change again.
    """
    last = (session.searches or [None])[-1]
    pool = last["candidates"] if last else (session.candidates or [])
    tried = [e for e in pool if e.alternative.role != "same"]
    reference = (last.get("reference") if last else None) or session.reference
    a = price_changes(session.assumptions)
    if not (a and tried):
        return tried, reference
    key = json.dumps(a, sort_keys=True) + (last["id"] if last else "")
    cached = getattr(session, "_repriced", None)
    if cached and cached[0] == key:
        return cached[1], cached[2]
    tried = [engine.reprice(e, a) for e in tried]
    reference = engine.reference(session.brief, a)
    chosen = next((e for e in tried if e.alternative.role == "chosen"), None)
    for e in tried:
        if chosen is not None and e.alternative.role == "candidate":
            gap = e.economics.lcoe_eur_per_mwh - chosen.economics.lcoe_eur_per_mwh
            e.alternative.reason = (
                f"{gap:+.1f} €/MWh of heat and cold ({e.economics.lcoe_eur_per_mwh:.1f} "
                f"against {chosen.economics.lcoe_eur_per_mwh:.1f}), at your prices"
            )
    session._repriced = (key, tried, reference)
    return tried, reference


def workbench(session) -> dict:
    """Return everything the tabs show for a conversation (contract ``Workbench``)."""
    rt = gemini_runtime.load("fixed")
    tried, reference = repriced_search(session)
    candidates = sorted(
        tried,
        key=lambda e: (
            e.alternative.role != "chosen",
            e.alternative.role == "failed",
            e.economics.lcoe_eur_per_mwh or 0.0,
        ),
    )
    if reference is None and candidates:
        reference = engine.reference(session.brief, session.assumptions)
    # The tabs measure every design against gas at the base case's prices: the chosen design's
    # own search, never a what-if's (gas at 30 €/MWh made the pick look 45 % dearer than gas).
    chosen = session.chosen
    base = next(
        (x for x in session.searches or [] if chosen and x["id"] == chosen.alternative.attempt),
        None,
    )
    if (
        base is not None
        and base.get("reference") is not None
        and not price_changes(session.assumptions)
    ):
        reference = base["reference"]
    return {
        "threadId": session.thread_id,
        "physics": "gemini",
        "gemini": {"version": rt.version, "patches": rt.patches},
        "assumptions": assumptions_view(session),
        "designs": with_names(session, [design_view(session, e) for e in entries(session)]),
        # The design the chat ran last (a what-if, your design, or the pick): the tabs open on
        # it when no design is asked for (2 Nov: after a what-if the Design tab showed the pick).
        "latest": design_id(session.ledger[-1]) if session.ledger else None,
        "candidates": [candidate_row(e) for e in candidates],
        "reference": candidate_row(reference) if reference is not None else None,
        "attempts": attempts_view(session),
        "library": with_names(session, library_view(session)),
    }


def _doublets(value) -> List[dict]:
    """Check the doublets a user design sets one by one (1 to 3, each a known set-up)."""
    out = []
    for d in list(value or [])[:3]:
        opening = {"full", "upper", "lower"}
        spec = {
            "depth_m": float(d.get("depth_m") or 2500.0),
            "producer_open": str(d.get("producer_open") or "full"),
            "injector_open": str(d.get("injector_open") or "full"),
            "injectors": 2 if int(d.get("injectors") or 1) >= 2 else 1,
            "max_flow_m3h": float(d["max_flow_m3h"]) if d.get("max_flow_m3h") else None,
            "min_flow_m3h": float(d["min_flow_m3h"]) if d.get("min_flow_m3h") else None,
            "train": int(d.get("train") or 0),
        }
        if spec["producer_open"] not in opening or spec["injector_open"] not in opening:
            raise ValueError("open parts are full, upper or lower")
        if not 500 <= spec["depth_m"] <= 7000:
            raise ValueError("depth_m must be between 500 and 7,000 m")
        if spec["max_flow_m3h"] is not None and not 50 <= spec["max_flow_m3h"] <= 300:
            raise ValueError("max_flow_m3h must be 50 to 300 m3/h")
        low = spec["min_flow_m3h"]
        if low is not None and not 50 <= low <= (spec["max_flow_m3h"] or 300):
            raise ValueError("min_flow_m3h must be 50 m3/h up to the doublet's cap")
        out.append(spec)
    if not out:
        raise ValueError("doublets needs 1 to 3 doublets")
    return out


def _dispatch(value) -> str:
    if value not in ("equal", "base"):
        raise ValueError("dispatch is equal or base")
    return str(value)


def _gas(value) -> str:
    """Return a gas mode (``dioscuri_plant.types.GAS_MODES``) or refuse it."""
    if value not in GAS_MODES:
        raise ValueError(f"gas is one of {', '.join(GAS_MODES)}")
    return str(value)


EDITABLE = {
    "n_doublets": int,
    "depth_m": float,
    "heat_pump_mw": float,
    "boiler_mw": float,
    "electric_boiler_mw": float,
    "gas": _gas,
    "absorption_mw": float,
    "chiller_mw": float,
    "reservoir_delta_c": float,
    "return_c": float,
    "cool_return_c": float,
    "doublets": _doublets,
    "dispatch": _dispatch,
}


def create_design(session, base: str, changes: dict, name: Optional[str] = None) -> dict:
    """Run a design edited on the tabs end to end and keep it with the conversation."""
    entry = find(session, base)
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise ValueError("unknown change: " + ", ".join(sorted(unknown)))
    c = {k: EDITABLE[k](v) for k, v in changes.items()}
    if not 1 <= c.get("n_doublets", entry.alternative.n_doublets or 1) <= 3:
        raise ValueError("n_doublets must be 1 to 3")
    # The engine's reach: a project's reservoir (500-6,000 m) and 1,000 m below it.
    if not 500 <= c.get("depth_m", entry.alternative.depth_m or 2500) <= 7000:
        raise ValueError("depth_m must be between 500 and 7,000 m")
    n = 1 + sum(1 for code in (session.user_designs or {}) if code.startswith("U"))
    code = f"U{n}"
    sizes = dict(entry.alternative.sizes_mw)
    for key, size in (
        ("heat_pump_mw", "heat_pump"),
        ("boiler_mw", "boiler"),
        ("electric_boiler_mw", "electric_boiler"),
        ("absorption_mw", "absorption"),
        ("chiller_mw", "chillers"),
    ):
        if key in c:
            sizes[size] = max(0.0, c[key])
    if not sizes.get("electric_boiler"):
        sizes.pop("electric_boiler", None)
    doublets = c.get("doublets")
    n_new = len(doublets) if doublets else c.get("n_doublets", entry.alternative.n_doublets)
    if doublets is None:
        base_rows = [dict(d) for d in entry.alternative.doublets] or [
            {"depth_m": entry.alternative.depth_m, "injectors": 1, "train": 0}
        ]
        doublets = [dict(base_rows[min(i, len(base_rows) - 1)]) for i in range(n_new)]
        if "depth_m" in c:
            for d in doublets:
                d["depth_m"] = c["depth_m"]
    alt = entry.alternative.model_copy(
        update={
            "code": code,
            "name": name or f"{design_id(entry)}, edited",
            "n_doublets": n_new,
            "depth_m": float(doublets[0].get("depth_m") or entry.alternative.depth_m),
            "doublets": doublets,
            "dispatch": c.get("dispatch", entry.alternative.dispatch) if n_new > 1 else "equal",
            "sizes_mw": sizes,
            "role": "user",
            "sizings": [],
            "stage": 1,
            "parent": base,
            "uid": code,  # "U1": its own name, not its parent's
            "picks": [],
            "reliable": False,
            "gas": c.get("gas", entry.alternative.gas),
        }
    )
    brief = entry.brief.model_copy(deep=True)
    if "reservoir_delta_c" in c:
        brief.reservoir_delta_c = c["reservoir_delta_c"]
    if "return_c" in c:
        heating = brief.heating or engine.DEFAULT_HEATING
        brief.heating = NetworkTemps(supply_c=heating.supply_c, return_c=c["return_c"])
    if "cool_return_c" in c:
        cooling = brief.cooling or engine.DEFAULT_COOLING
        brief.cooling = NetworkTemps(supply_c=cooling.supply_c, return_c=c["cool_return_c"])
    new = engine.evaluate(alt, brief, session.assumptions or {}, role="user")
    session.ledger.append(new)
    session.user_designs = dict(session.user_designs or {})
    session.user_designs[code] = {"parent": base, "name": alt.name}
    return design_view(session, new)


def delete_design(session, design: str) -> None:
    """Remove a user design (agent designs stay: the chat refers to them)."""
    entry = find(session, design)
    code = entry.alternative.code
    if code not in (session.user_designs or {}):
        raise ValueError("only designs made on the tabs can be deleted")
    session.ledger = [e for e in session.ledger if e.alternative.code != code]
    if session.chosen is not None and session.chosen.alternative.code == code:
        session.chosen = None
    session.user_designs.pop(code, None)


# ------------------------------------------------------------------ GEMINI projects

GROUPS = {
    "producer_well": (
        "Producer well",
        "wells",
        "Reservoir inflow, well pressure drop and the ESP; nodal-solved flow",
    ),
    "injector_well": (
        "Injector well",
        "wells",
        "Injection back into the reservoir, with the injector pump",
    ),
    "reservoir_ipr": (
        "Reservoir inflow",
        "wells",
        "Bottomhole pressure from flow and productivity",
    ),
    "well": ("Well tubing", "wells", "Pressure drop along a well"),
    "esp": ("ESP", "wells", "Electric submersible pump"),
    "separator": ("Separator", "surface", "Separates co-produced gas from the brine"),
    "filter": ("Filter", "surface", "Pressure drop and fouling"),
    "heat_exchanger": ("Heat exchanger", "heat", "Effectiveness-NTU, counter or parallel flow"),
    "heatpump": (
        "Heat pump",
        "heat",
        "Carnot or Lorenz COP, energy balance (with the team's fixes)",
    ),
    "boiler": ("Boiler", "heat", "Gas-fired; heat and CO₂"),
    "chp": ("CHP", "heat", "Gas-fired combined heat and power"),
    "booster_pump": ("Booster pump", "surface", "Raises pressure in the surface network"),
    "injector_pump": (
        "Injector pump",
        "surface",
        "Raises the return water to the injection pressure",
    ),
    "splitter": ("Splitter", "flow", "Splits one flow into fractions"),
    "mixer": ("Mixer", "flow", "Mixes flows, flow-weighted temperature"),
    "adder": ("Adder", "flow", "Adds flows"),
    "reservoir_bottomhole_skin": ("Skin pressure drop", "wells", "Near-well skin"),
}


def _unit(key: str) -> str:
    k = key.lower()
    if "temperature" in k or k in ("th_in", "ts_in", "th_out", "ts_out") or k.endswith("_c"):
        return "°C"
    if k.endswith("_pa"):
        return "Pa"
    if "pressure" in k:
        return "bar"
    if k.endswith("m3h") or k.endswith("_m3h"):
        return "m³/h"
    if "flow" in k:
        return "m³/s"
    if k.startswith(("power", "heat_duty", "thermal", "electrical")) or k.endswith("_power_el"):
        return "W"
    if "emission" in k:
        return "kg/s"
    return ""


def catalogue() -> List[dict]:
    """Return the GEMINI component types a project can use, with their ports and parameters.

    Inputs and outputs are read from each model's code (``u["key"]`` and
    ``self.output["key"]``); parameters are its defaults, and for the types GEMINI's doublet
    example uses, the example's values.
    """
    import inspect

    rt = gemini_runtime.load("fixed")
    registry = __import__(
        rt.build_project.__module__.replace("project_loader", "registry"),
        fromlist=["COMPONENT_REGISTRY"],
    )
    example = json.loads((ROOT / "simulator_examples/projects/doublet_plant.json").read_text())
    by_type = {}
    for comp in example["components"].values():
        by_type.setdefault(comp["type"], comp.get("parameters", {}))
    out = []
    for type_, cls in registry.COMPONENT_REGISTRY.items():
        try:
            src = inspect.getsource(cls)
        except (OSError, TypeError):
            src = ""
        inputs = sorted(set(re.findall(r'\bu\[\s*"(\w+)"\s*\]', src)))
        outputs = sorted(set(re.findall(r'self\.output\[\s*"(\w+)"\s*\]', src)))
        try:
            defaults = dict(getattr(cls(), "parameters", {}) or {})
        except Exception:  # noqa: BLE001 - some need arguments
            defaults = {}
        defaults.update(by_type.get(type_, {}))
        label, group, desc = GROUPS.get(type_, (type_.replace("_", " ").title(), "surface", ""))
        out.append(
            {
                "type": type_,
                "label": label,
                "group": group,
                "description": desc,
                "inputs": [{"key": k, "unit": _unit(k), "description": ""} for k in inputs],
                "outputs": [{"key": k, "unit": _unit(k), "description": ""} for k in outputs],
                "parameters": [
                    {"key": k, "unit": _unit(k), "default": v, "description": ""}
                    for k, v in defaults.items()
                    if not k.startswith("_")
                ],
            }
        )
    return out


def _outputs(solver) -> Dict[str, Dict[str, float]]:
    out = {}
    for name in solver.components:
        try:
            snapshot = solver.get_output(name)
        except (IndexError, KeyError):
            continue
        out[name] = {
            k: float(v)
            for k, v in snapshot.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        }
    return out


def _pressure_warnings(outputs: Dict[str, Dict[str, float]]) -> List[str]:
    """Return a line for each pressure below 1 bar(g): the loop cannot run like that."""
    out = []
    for comp, values in outputs.items():
        for key, value in values.items():
            if "pressure" in key and isinstance(value, (int, float)) and "pa" not in key:
                if value < 1.0:
                    out.append(f"{comp}: {key} {value:.2f} bar, below 1 bar")
    return out


def run_gemini(project: dict, compare_released: bool = False) -> dict:
    """Run a GEMINI project on the fixed GEMINI (and the release, when asked)."""
    start = time.perf_counter()

    def one(variant):
        try:
            solver = gemini_runtime.load(variant).build_project(json.loads(json.dumps(project)))
            solver.run()
            return {"ok": True, "error": None, "outputs": _outputs(solver)}
        except Exception as err:  # noqa: BLE001 - the user's project may not solve
            return {"ok": False, "error": f"{type(err).__name__}: {err}", "outputs": {}}

    fixed = one("fixed")
    released = one("asis") if compare_released else None
    return dict(
        fixed,
        warnings=_pressure_warnings(fixed.get("outputs") or {}),
        seconds=round(time.perf_counter() - start, 3),
        released=released,
        patches=gemini_runtime.load("fixed").patches,
    )


# ------------------------------------------------------------------ sensitivity


def sensitivity_parameters() -> dict:
    """Return the parameters a sensitivity run can vary and the outputs it reports."""
    return {
        "parameters": [
            {
                "key": k,
                "label": lab,
                "unit": unit,
                "group": group,
                "low": lo,
                "high": hi,
                "kind": kind,
                "description": desc,
            }
            for k, (lab, unit, group, lo, hi, kind, desc) in PARAMETERS.items()
        ],
        "outputs": [{"key": k, "label": lab, "unit": unit} for k, (lab, unit) in OUTPUTS.items()],
    }


def _apply(entry: LedgerEntry, assumptions: dict, values: Dict[str, float]):
    """Return the design's alternative, brief, prices, demand scale and rule changes."""
    alt = entry.alternative.model_copy()
    brief = entry.brief.model_copy(deep=True)
    a = dict(assumptions or {})
    # Unscaled: a conversation's ``capex_scale`` still applies on top when the design is run.
    prices = asdict(engine.prices_for({k: v for k, v in a.items() if k != "capex_scale"}))
    scale = [1.0, 1.0]
    overrides: Dict[str, float] = {}
    for key, x in values.items():
        if key == "reservoir_temp":
            brief.reservoir_delta_c = (entry.brief.reservoir_delta_c or 0.0) + x
        elif key == "heat_return":
            heating = brief.heating or engine.DEFAULT_HEATING
            brief.heating = NetworkTemps(supply_c=heating.supply_c, return_c=x)
        elif key == "cool_return":
            cooling = brief.cooling or engine.DEFAULT_COOLING
            brief.cooling = NetworkTemps(supply_c=cooling.supply_c, return_c=x)
        elif key == "permeability":
            overrides["permeability_md"] = x
        elif key == "operating_days":
            overrides["operating_days"] = int(round(x))
        elif key == "depth" and alt.depth_m:
            # Every doublet moves to that aquifer depth (an assumed aquifer off the known one).
            rows = [dict(d, depth_m=x) for d in alt.doublets]
            alt = alt.model_copy(update={"depth_m": x, "doublets": rows})
        elif key == "heat_demand":
            scale[0] = x
        elif key == "cool_demand":
            scale[1] = x
        elif key == "gas_price":
            a["gas_eur_per_mwh"] = x
        elif key == "electricity_price":
            a["electricity_eur_per_mwh"] = x
        elif key == "carbon_price":
            a["carbon_eur_per_t"] = x
        elif key == "discount_rate":
            a["discount_rate"] = x
        elif key == "capex":
            for k in CAPEX_KEYS:
                a[k] = prices[k] * x
    return alt, brief, a, tuple(scale), overrides


def _evaluate(entry, assumptions, values, outputs) -> Dict[str, float]:
    alt, brief, a, scale, overrides = _apply(entry, assumptions, values)
    new = engine.evaluate(alt, brief, a, scale=scale, overrides=overrides or None, with_firm=False)
    e, y = new.economics, new.year
    versus = None
    if "npv_meur" in outputs and alt.depth_m:
        # The gas plant for the same demand: a heat or cold demand swing scales it too.
        demand = [s * d for s, d in zip(scale, brief.demand_scale or [1.0, 1.0])]
        ref = engine.reference(brief.model_copy(update={"demand_scale": demand}), a)
        versus = engine.versus_reference(new, ref, engine.prices_for(a, brief))
    metrics = {
        "lcoh": e.lcoh_eur_per_mwh,
        "lcoc": e.lcoc_eur_per_mwh,
        "lcoe": e.lcoe_eur_per_mwh,
        "co2_saving_pct": round(e.co2_saving_vs_gas * 100, 2),
        "heat_coverage": round(y.heat_coverage * 100, 2),
        "capex_meur": e.capex_meur,
        "npv_meur": versus["npv_meur"] if versus else None,
        "violations": len(y.violations),
    }
    return {k: metrics[k] for k in outputs if metrics.get(k) is not None}


def _backup_year(plant, attr: str, size: float, demand, model, rules, prices) -> dict:
    """Return what a plan with its backup at ``size`` MW costs a year, k€, by line.

    The design run and priced as ``economics`` prices it (capital at the same discount rate
    and life): the backup's capital annuity, its O&M (fixed and variable), the electric
    boiler's grid charge, and the whole design's yearly cost (M€) for the difference.
    """
    from dataclasses import replace as _replace

    p = _replace(plant, **{attr: size})
    year = dp.simulate_year(p, demand, model, rules)
    e = dp.economics(p, year, prices, rules=rules)
    name = "Boiler" if attr == "boiler_mw" else "Electric boiler"
    mine = [(i, k, m) for i, k, m in e.lines if i == name or i.startswith(name + " ")]
    capital = sum(m for _, k, m in mine if k == "capital")
    grid = sum(m for i, _, m in mine if i.endswith("grid capacity"))
    om = sum(m for i, k, m in mine if k != "capital" and not i.endswith("grid capacity"))
    return {
        "mw": round(size, 2),
        "capital_keur": round(capital * 1000, 1),
        "om_keur": round(om * 1000, 1),
        "grid_keur": round(grid * 1000, 1),
        "backup_keur": round((capital + om + grid) * 1000, 1),
        "design_meur": sum(m for _, _, m in e.lines),
    }


def risk_view(session, design: str, spare_esp: bool = False) -> dict:
    """Return a design's backup sized by risk beside its own (N-1) size (``montecarlo``).

    The smallest backup boiler that keeps the days short of heat to one in ten years over the
    drawn years of unplanned outages. The years are drawn as the design is built: no spare ESP
    (a failed ESP keeps its doublet out 120 days) unless ``spare_esp`` asks for one in both
    plans. Both plans are priced a year the same way (``_backup_year``: capital annuity, O&M,
    the electric boiler's grid charge), beside the heat the smaller backup would not deliver.
    Until 4 Nov the one-off capital saved was set against k€ a year, without the grid charge,
    over years drawn with a spare ESP that no design pays for.
    """
    from dioscuri_plant import montecarlo
    from dioscuri_plant.economics import crf
    from dioscuri_plant.failure_costs import LOST_EUR_PER_MWH, spare_yearly_keur
    from dioscuri_plant.firm import NO_SPARE_ESP_DAYS, SPARE_ESP_SWAP_DAYS

    entry = find(session, design)
    if entry.alternative.n_doublets == 0:
        raise ValueError("the gas reference has no doublet to fail")
    brief = entry.brief
    rules = engine.rules_for(brief)
    prices = engine.prices_for(session.assumptions or None, brief)
    plant = engine.plant_of(entry.alternative)
    demand, model = engine.demand_of(brief), engine.doublet_model(rules)
    start = time.perf_counter()
    out = montecarlo.risk_sizing(plant, demand, model, rules, spare_esp=spare_esp)
    if out is None:
        raise ValueError("this design has no backup boiler to size")
    gas = out["unit"] == "boiler_mw"
    per_mw = prices.boiler_meur_per_mw if gas else prices.electric_boiler_meur_per_mw
    life = prices.boiler_life_years if gas else prices.electric_boiler_life_years
    saved = (out["n1_mw"] - out["risk_mw"]) * per_mw
    n1 = _backup_year(plant, out["unit"], out["n1_mw"], demand, model, rules, prices)
    risk = _backup_year(plant, out["unit"], out["risk_mw"], demand, model, rules, prices)
    for plan, at in ((n1, out["at_n1"]), (risk, out["at_risk"])):
        plan["lost_keur"] = round(at["eens_mwh"] * LOST_EUR_PER_MWH / 1000, 2)
    spare = round(spare_yearly_keur(prices), 1) if spare_esp else 0.0
    not_drawn = montecarlo.not_drawn(plant)
    out.update(
        design=design_id(entry),
        unit_words="gas boiler" if gas else "electric boiler",
        capex_saved_meur=round(saved, 3),
        n1_plan=n1,
        risk_plan=risk,
        # What N-1 costs a year more than the plan sized by risk (the whole design priced).
        n1_extra_keur_per_year=round((n1["design_meur"] - risk["design_meur"]) * 1000, 1),
        annuity={
            "discount_rate": prices.discount_rate,
            "life_years": life,
            "crf": round(crf(prices.discount_rate, life), 5),
        },
        lost_keur_per_year=risk["lost_keur"],
        lost_eur_per_mwh=LOST_EUR_PER_MWH,
        spare_keur_per_year=spare,
        not_drawn=not_drawn,
        reliable=bool(entry.alternative.reliable),
        seconds=round(time.perf_counter() - start, 1),
        source=(
            "LOLE 0.1 day a year (one day in ten years, a common reserve standard for power "
            "systems; the Dutch one for electricity is 4 hours a year); "
            "unplanned outages drawn at each unit's rate over 1,000 years "
            + (
                f"with a spare ESP on the shelf in both plans (a doublet out "
                f"{SPARE_ESP_SWAP_DAYS} days; {spare:,.0f} k€ a year each, so not in the "
                "difference)"
                if spare_esp
                else "as the design is built, with no spare ESP (a doublet out "
                f"{NO_SPARE_ESP_DAYS} days when its ESP fails)"
            )
            + "; "
            + (
                f"not drawn (no published failure rate): {', '.join(not_drawn)}; "
                if not_drawn
                else ""
            )
            + "each plan priced a year as the cost of heat prices it (capital over "
            f"{life} years at {prices.discount_rate:.1%}, O&M"
            + ("" if gas else ", the grid charge")
            + ") (dioscuri_plant.montecarlo); see hackathon/docs/reliability.md"
        ),
    )
    for plan in (n1, risk):
        plan["design_meur"] = round(plan["design_meur"], 4)
    return out


def outages(session, design: str, spare_esp: bool = False, years: int = 1000) -> dict:
    """Return a design's unplanned outages over drawn years (``dioscuri_plant.montecarlo``).

    Each unit fails at its sourced rate on random days for its repair time; every year with
    failures is run; the worst case is a doublet out 35 days in the coldest weeks. Under this
    chat's prices. ``spare_esp``: a spare ESP on the shelf (a doublet out 7 days when its ESP
    fails) or not, as the design is built (120 days, about four months).
    """
    from dioscuri_plant import montecarlo

    entry = find(session, design)
    if entry.alternative.n_doublets == 0:
        raise ValueError("the gas reference has no doublet to fail")
    brief = entry.brief
    rules = engine.rules_for(brief)
    prices = engine.prices_for(session.assumptions or None, brief)
    start = time.perf_counter()
    out = montecarlo.unplanned(
        engine.plant_of(entry.alternative),
        engine.demand_of(brief),
        engine.doublet_model(rules),
        rules,
        prices,
        years=max(100, min(int(years), 5000)),
        spare_esp=spare_esp,
    )
    from dioscuri_plant.failure_costs import SOURCES, kind

    kinds = {kind(u) for u in out.get("failures") or {}} | {"esp"}
    keys = [k for k in ("esp", "esp_swap_days", "esp_no_spare_days", "esp_repair_meur") if k]
    keys += sorted(k for k in kinds if k and k != "esp")
    out["sources"] = {k: SOURCES[k] for k in keys if k in SOURCES}
    if out.get("not_drawn"):
        out["sources"]["treatment train"] = SOURCES["treatment train"]
    out["design"] = design
    out["reliable"] = bool(entry.alternative.reliable)
    out["seconds"] = round(time.perf_counter() - start, 2)
    if out.get("worst"):
        from gemini_agent import stops

        w = out["worst"]
        w["from"], w["to"] = stops.day_name(w["first_day"]), stops.day_name(
            min(w["first_day"] + w["days"] - 1, 364)
        )
    return out


def sensitivity(
    session,
    design: str,
    parameters: Sequence[dict],
    outputs: Sequence[str],
    samples: int = 0,
    seed: int = 7,
) -> dict:
    """Vary the chosen parameters around a design: tornado, spider and Monte Carlo.

    Parameters
    ----------
    session : Session
        The conversation (its designs and cost assumptions).
    design : str
        The design's id.
    parameters : sequence of dict
        ``key``, ``low``, ``high`` (keys from ``PARAMETERS``).
    outputs : sequence of str
        Keys from ``OUTPUTS``.
    samples : int
        Monte Carlo samples (0: none; at most 500). Each input is drawn from a triangular
        distribution over its range whose most likely value is the design's own (``mode``
        when a parameter gives it, else ``base_value``), so the runs centre on the case; an
        input whose case lies outside its range is drawn uniformly. The inputs are drawn
        independently of each other: no correlation (gas and electricity prices, or the
        capital costs, do not move together), so the ranges may be narrower than when they
        do.
    seed : int
        Seed of the samples, so a run can be repeated.

    Returns
    -------
    dict
        Contract ``Sensitivity``; each Monte Carlo output also has ``base_percentile`` (the
        share of runs below the design's own value), and ``monte_carlo["modes"]`` the most
        likely value each input was drawn around (None: uniform).
    """
    start = time.perf_counter()
    entry = find(session, design)
    outputs = [o for o in outputs if o in OUTPUTS] or ["lcoh"]
    params = []
    for p in parameters:
        if p["key"] not in PARAMETERS:
            raise ValueError(f"unknown parameter {p['key']!r}")
        lo, hi = float(p["low"]), float(p["high"])
        allowed = LIMITS.get(p["key"])
        if allowed and not (allowed[0] <= min(lo, hi) and max(lo, hi) <= allowed[1]):
            kind = PARAMETERS[p["key"]][5]
            raise ValueError(
                f"{p['key']}: {lo:g} to {hi:g} is outside {allowed[0]:g} to {allowed[1]:g}"
                + (" (a change, not an absolute value)" if kind == "delta" else "")
            )
        params.append((p["key"], min(lo, hi), max(lo, hi)))
    assumptions = session.assumptions or {}
    modes: Dict[str, Optional[float]] = {}
    for p, (key, lo, hi) in zip(parameters, params):
        mode = p.get("mode")
        mode = base_value(entry, assumptions, key) if mode is None else float(mode)
        modes[key] = mode if mode is not None and lo <= mode <= hi else None
    runs = 0

    def ev(values):
        nonlocal runs
        runs += 1
        return _evaluate(entry, assumptions, values, outputs)

    base = ev({})
    tornado, spider = [], []
    for key, lo, hi in params:
        low, high = ev({key: lo}), ev({key: hi})
        tornado.append({"key": key, "label": PARAMETERS[key][0], "low": low, "high": high})
        points = []
        for i in range(5):
            x = lo + (hi - lo) * i / 4
            values = low if i == 0 else high if i == 4 else ev({key: x})
            points.append({"x": round(x, 4), "values": values})
        spider.append({"key": key, "points": points})
    first = outputs[0]
    tornado.sort(key=lambda t: -abs((t["high"].get(first) or 0) - (t["low"].get(first) or 0)))
    mc = None
    samples = max(0, min(int(samples or 0), 500))
    if samples and params:
        rng = random.Random(seed)
        results: Dict[str, List[float]] = {o: [] for o in outputs}

        def draw(key, lo, hi):
            mode = modes.get(key)
            if mode is None or hi <= lo:
                return rng.uniform(lo, hi)
            return rng.triangular(lo, hi, mode)

        for _ in range(samples):
            r = ev({key: draw(key, lo, hi) for key, lo, hi in params})
            for o in outputs:
                if o in r:
                    results[o].append(r[o])
        mc = {
            "samples": samples,
            "draw": (
                "triangular, most likely at the design's own value; each input drawn "
                "independently of the others (no correlation)"
            ),
            "modes": dict(modes),
            "outputs": {o: _summary(v, base.get(o)) for o, v in results.items() if v},
        }
    return {
        "design": design,
        "seconds": round(time.perf_counter() - start, 2),
        "runs": runs,
        "base": base,
        "tornado": tornado,
        "spider": spider,
        "monte_carlo": mc,
    }


def base_value(entry: LedgerEntry, assumptions: Optional[dict], key: str) -> Optional[float]:
    """Return a sensitivity input's value in the design's own case (None when unknown).

    A change (``kind`` "delta") is 0 and a factor ("scale") 1; prices are the conversation's
    (the defaults unless set in Economics); temperatures, permeability, depth and operating
    days are the design's brief and rules.
    """
    if key not in PARAMETERS:
        return None
    kind = PARAMETERS[key][5]
    if kind == "delta":
        return 0.0
    if kind == "scale":
        return 1.0
    prices = engine.prices_for(assumptions or None, entry.brief)
    rules = engine.rules_for(entry.brief)
    heating = entry.brief.heating or engine.DEFAULT_HEATING
    cooling = entry.brief.cooling or engine.DEFAULT_COOLING
    values = {
        "gas_price": prices.gas_eur_per_mwh,
        "electricity_price": prices.electricity_eur_per_mwh,
        "carbon_price": prices.carbon_eur_per_t,
        "discount_rate": prices.discount_rate,
        "heat_return": heating.return_c,
        "cool_return": cooling.return_c,
        "permeability": rules.permeability_md,
        "operating_days": float(rules.operating_days),
        "depth": entry.alternative.depth_m or None,
    }
    value = values.get(key)
    return None if value is None else float(value)


def _summary(values: List[float], base: Optional[float] = None) -> dict:
    v = sorted(values)

    def pct(q):
        k = (len(v) - 1) * q
        f = math.floor(k)
        return v[f] + (v[min(f + 1, len(v) - 1)] - v[f]) * (k - f)

    lo, hi = v[0], v[-1]
    bins = 12
    width = (hi - lo) / bins or 1.0
    edges = [lo + width * i for i in range(bins + 1)]
    counts = [0] * bins
    for x in v:
        counts[min(int((x - lo) / width), bins - 1)] += 1
    return {
        "above_zero": round(sum(x > 0 for x in v) / len(v), 3),
        "p10": round(pct(0.1), 3),
        "p50": round(pct(0.5), 3),
        "p90": round(pct(0.9), 3),
        "mean": round(statistics.fmean(v), 3),
        "histogram": {"edges": [round(e, 3) for e in edges], "counts": counts},
        # Where the design's own case sits among the runs (ties count half): 0.5 is the median.
        "base": None if base is None else round(float(base), 3),
        "base_percentile": (
            None
            if base is None
            else round((sum(x < base for x in v) + 0.5 * sum(x == base for x in v)) / len(v), 3)
        ),
    }


# ------------------------------------------------------------------ trace and evidence


def trace(trace_dir: Path, thread_id: str) -> List[dict]:
    """Return a conversation's runs from its trace file (contract ``TraceRun``)."""
    path = Path(trace_dir) / f"{thread_id}.jsonl"
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return trace_events(events)


def trace_events(events) -> List[dict]:
    """Return the runs of a list of AG-UI events (a trace file's, an eval transcript's)."""
    runs: Dict[str, dict] = {}
    order: List[str] = []
    current: Optional[dict] = None
    open_steps: Dict[str, dict] = {}
    tools_open: Dict[str, dict] = {}
    for e in events:
        if not isinstance(e, dict):
            continue
        t = e.get("type")
        if t == "RUN_STARTED":
            current = {
                "runId": e.get("runId"),
                "started": e.get("timestamp"),
                "message": "",
                "answer": "",
                "answer_model": "",
                "mode": "fast",
                "device": "",
                "seconds": 0.0,
                "tokens": {"prompt": 0, "output": 0},
                "steps": [],
                "calls": [],
                "tools": [],
                "outcome": "",
            }
            runs[current["runId"]] = current
            order.append(current["runId"])
            open_steps, tools_open = {}, {}
        elif current is None:
            continue
        elif t == "STEP_STARTED":
            md = e.get("metadata") or {}
            open_steps[e["stepName"]] = {
                "name": e["stepName"],
                "label": md.get("label", ""),
                "kind": md.get("kind", ""),
                "code": md.get("code"),
                "seconds": 0.0,
                "meta": {},
            }
        elif t == "STEP_FINISHED":
            md = dict(e.get("metadata") or {})
            step = open_steps.pop(
                e["stepName"], {"name": e["stepName"], "label": "", "kind": "", "code": None}
            )
            step["seconds"] = md.pop("seconds", 0.0)
            step["meta"] = md
            current["steps"].append(step)
        elif t == "CUSTOM" and e.get("name") == "usage":
            u = e.get("value") or {}
            current["calls"].append(
                {
                    k: u.get(k)
                    for k in ("purpose", "model", "prompt_tokens", "output_tokens", "seconds", "ok")
                }
            )
        elif t == "TOOL_CALL_START":
            tools_open[e["toolCallId"]] = {
                "name": e.get("toolCallName"),
                "args": None,
                "result": None,
            }
        elif t == "TOOL_CALL_ARGS" and e.get("toolCallId") in tools_open:
            tools_open[e["toolCallId"]]["args"] = _json(e.get("delta"))
        elif t == "TOOL_CALL_RESULT" and e.get("toolCallId") in tools_open:
            call = tools_open.pop(e["toolCallId"])
            call["result"] = _json(e.get("content"))
            current["tools"].append(call)
        elif t in ("RUN_FINISHED", "RUN_ERROR"):
            r = e.get("result") or {}
            current["message"] = r.get("message", "")
            current["answer"] = r.get("answer", "")
            current["answer_model"] = r.get("answer_model", "")
            current["mode"] = "reasoning" if r.get("reasoning") else "fast"
            current["device"] = r.get("device") or ""
            current["seconds"] = r.get("seconds", 0.0)
            current["tokens"] = {
                "prompt": r.get("prompt_tokens", 0),
                "output": r.get("output_tokens", 0),
            }
            current["outcome"] = r.get("behaviour") or ("error" if t == "RUN_ERROR" else "")
    return [runs[i] for i in order]


# A run's file stem or a case id: no path separators, no leading dot.
TRANSCRIPT_NAME = re.compile(r"^[A-Za-z0-9_][\w.@-]{0,119}$")


def transcript_path(runs_dir: Path, run: str, case: str) -> Path:
    """Return where an eval case's transcript is kept (``runs/transcripts/<run>/<case>.json``).

    Raises
    ------
    ValueError
        When the run or the case is not a plain name.
    """
    for name in (run, case):
        if not TRANSCRIPT_NAME.match(name or "") or ".." in name:
            raise ValueError(f"{name!r}: letters, digits, _ . @ - only")
    return Path(runs_dir) / "transcripts" / run / f"{case}.json"


def transcript(runs_dir: Path, run: str, case: str) -> Optional[dict]:
    """Return one eval case's transcript, with each exchange's runs read as the Trace tab does.

    The file (written by ``hackathon/evals/run_evals.py``) has the case's record (prompt,
    expected and got, every check) and its ``exchanges``: what the user sent (a message, the
    answers to a card, an upload) and the AG-UI events the agent sent back. ``runs`` adds the
    steps, tool calls and model calls of each run, as ``trace`` gives them.

    Returns
    -------
    dict or None
        The transcript, or None when that case of that run has none.
    """
    path = transcript_path(runs_dir, run, case)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["runs"] = trace_events(
        e for x in data.get("exchanges") or [] for e in x.get("events") or []
    )
    return data


def _json(text):
    try:
        return json.loads(text) if isinstance(text, str) else text
    except json.JSONDecodeError:
        return text


def _tables(markdown: str) -> List[dict]:
    """Return the Markdown tables with their section titles.

    ``emphasis`` lists the rows that were set in bold (the model each role uses).
    """
    out, title, rows, bold = [], "", [], []
    for line in markdown.splitlines() + [""]:
        if line.startswith("## "):
            title = line[3:].strip()
        if line.startswith("|"):
            raw = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in raw):
                continue
            if rows and any(c.startswith("**") for c in raw):
                bold.append(len(rows) - 1)
            rows.append([c.replace("**", "").replace("`", "") for c in raw])
            continue
        if rows:
            out.append(
                {
                    "title": title,
                    "columns": rows[0],
                    "rows": rows[1:],
                    "note": "",
                    "emphasis": bold,
                }
            )
            rows, bold = [], []
    return out


def evidence(runs_dir: Path = RUNS) -> dict:
    """Return the evidence the judges look for: test runs, benchmarks, GEMINI's bug impact.

    ``caught`` is the list of failures found and fixed (``caught``), each with its guard.
    """
    evals = []
    files = sorted(Path(runs_dir).glob("2026*_*.jsonl"))
    # The newest run of each suite on each device: the main scenarios, and the chat suite
    # (its cases carry a group) apart, so one never hides the other.
    latest: Dict[tuple, Path] = {}
    for f in files:
        recs = _read_jsonl(f)
        if len(recs) >= 20:
            suite = "chat" if any(r.get("group") for r in recs) else "main"
            latest[(recs[0].get("device", "?"), suite)] = f
    for (device, suite), f in sorted(latest.items()):
        recs = _read_jsonl(f)
        ok = sum(bool(r.get("pass")) for r in recs)
        answerer = next(
            (
                str(r["result"].get("answer_model"))
                for r in recs
                if r.get("result", {}).get("answer_model")
            ),
            "",
        )
        label = "GPU" if device == "auto" and "9b" in answerer else device.upper()
        groups: Dict[str, List[int]] = {}
        for r in recs:
            if r.get("group"):
                g = groups.setdefault(r["group"], [0, 0])
                g[0] += bool(r.get("pass"))
                g[1] += 1
        evals.append(
            {
                "suite": suite,
                "groups": {k: {"passed": v[0], "total": v[1]} for k, v in groups.items()},
                "file": f.name,
                "device": device,
                "label": label,
                "answerer": answerer,
                "when": f.name[:16],
                "passed": ok,
                "total": len(recs),
                "tokens": sum(
                    r["result"].get("prompt_tokens", 0) + r["result"].get("output_tokens", 0)
                    for r in recs
                ),
                "seconds": round(sum(r.get("wall_seconds", 0) for r in recs), 1),
                "scenarios": [
                    {
                        "id": r["id"],
                        "expected": r.get("expected"),
                        "got": r["result"].get("behaviour"),
                        "ok": bool(r.get("pass")),
                        "calls": len(r["result"].get("calls", [])),
                        "tokens": r["result"].get("prompt_tokens", 0)
                        + r["result"].get("output_tokens", 0),
                        "seconds": r.get("wall_seconds", 0),
                        # The checks that failed, by name, and whether its transcript was kept.
                        "failed": [k for k, v in (r.get("checks") or {}).items() if v is False],
                        "group": r.get("group"),
                        "transcript": _has_transcript(runs_dir, f.stem, r["id"]),
                    }
                    for r in recs
                ],
            }
        )
    benchmarks = _tables(BENCHMARKS.read_text(encoding="utf-8")) if BENCHMARKS.is_file() else []
    rt = gemini_runtime.load("fixed")
    outcome = engine.search(DesignBrief())
    shown = [outcome.chosen] if outcome.chosen is not None else []
    shown += [e for e in engine.ranked(outcome) if e.alternative.heat_pump and e not in shown][:1]
    gem = {
        "version": rt.version,
        "patches": [{"file": p, "title": PATCH_TITLES.get(p[:2], p)} for p in rt.patches],
        "bug_impact": [{"design": e.alternative.code, "rows": engine.bug_impact(e)} for e in shown],
    }
    from gemini_agent import validation

    try:
        checks = validation.all_projects()
    except Exception:  # noqa: BLE001 - the evidence stands without it
        checks = []
    from gemini_agent import caught

    return {
        "evals": evals,
        "benchmarks": benchmarks,
        "gemini": gem,
        "validation": checks,
        "caught": caught.view(),
    }


def _has_transcript(runs_dir: Path, run: str, case: str) -> bool:
    try:
        return transcript_path(runs_dir, run, case).is_file()
    except ValueError:
        return False


def _read_jsonl(path: Path) -> List[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
