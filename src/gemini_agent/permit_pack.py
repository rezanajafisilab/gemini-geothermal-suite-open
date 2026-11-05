"""The permit and subsidy pack of a design: the figures the applications ask for, in one PDF.

Not the applications themselves: the figures from the design that a production plan under the
Mining Act (Mijnbouwwet), the SDE++ round and the environment permits ask for, each with where
it comes from, and a list of what the design cannot give (studies a permit needs that are not a
model's). Four parts:

1. Mining permit: per doublet the depth, flows, injection temperature and the brine's cooling,
   the injection pressure at the top of the reservoir against SodM's limit (0.135 bar a metre),
   the ESP's setting against the gas bubble point, the years until cold water reaches the
   producer, and the produced gas and where it goes (flaring needs consent).
2. SDE++ (the 2026 round, PBL's advice): the category for the plant's capacity, its base amount
   and full-load hours, the heat that qualifies, and the subsidy a year and over 15 years
   (``dioscuri_plant.investor``, the Economics tab's investor view).
3. Environment and grid: the CO2 a year and the cut against gas, the cooling towers' water
   (the cooling check), the grid electricity.
4. Not in this pack: what the applications also need.

Uses the operator's report's page layout (``report_pdf``).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional

import matplotlib

from dioscuri_plant.subsurface import ESP_MAX_SETTING_M, SODM_BAR_PER_M
from gemini_agent import reporter, workbench
from gemini_agent.contract import LedgerEntry
from gemini_agent.report_pdf import LEFT, RC, TEAL, WIDTH, _Doc, _with_days, fit, num, target

NOT_IN_PACK = [
    "A seismic risk assessment (SodM's protocol for geothermal) and the monitoring plan it sets",
    "The geological report behind the reservoir figures, with its P90 / P50 / P10 cases",
    "Well design and integrity (casing, cement, corrosion and scaling programme)",
    "The environment permit for the plant site (omgevingsvergunning): noise, safety, spatial fit",
    "The water permits for the cooling towers' intake and discharge, when the plant has towers",
    "The SDE++ feasibility study, the heat customers' agreements and the financing",
]


def filename(entry: LedgerEntry) -> str:
    """Return the pack's file name, ``dioscuri-1D-HP-EC-N1-permits.pdf``."""
    code = re.sub(r"[^A-Za-z0-9_.-]+", "-", entry.alternative.code).strip("-.") or "design"
    return f"dioscuri-{code}-permits.pdf"


def _mining(doc: _Doc, entry: LedgerEntry) -> None:
    y, alt = entry.year, entry.alternative
    doc.section_head(
        1,
        "Mining permit: the production plan's figures",
        "Per doublet, what the production plan (winningsplan) under the Mining Act states, from "
        "the design's year and its subsurface checks. Each limit with its margin.",
    )
    rows_d = (y.plant or {}).get("doublets") or []
    if not alt.n_doublets or not rows_d:
        doc.para("This design has no doublet: no mining permit is needed.")
        return
    for k, r in enumerate(rows_d):
        tag = f"Doublet {r.get('doublet', k + 1)}"
        flows = [f for f in ((y.doublets or [{}])[k].get("flow_m3h") or []) if f]
        top = r.get("injection_top_bar")
        limit = r.get("injection_limit_bar")
        rows: List[List[str]] = [
            [
                "Aquifer and wells",
                f"midpoint {num(r.get('depth_m'), 0)} m TVD; producer open "
                f"{num(r.get('producer_open_m'), 0)} m, {r.get('injectors', 1)} injector(s)",
            ],
            [
                "Flow",
                f"cap {num(r.get('cap_m3h'), 0)} m³/h; highest day "
                f"{num(max(flows) if flows else 0, 0)} m³/h; "
                f"{num((r.get('brine_m3') or 0) / 1e6, 2)} million m³ a year",
            ],
            [
                "Brine cooled",
                f"at most {num(r.get('max_cooling_k'))} K; coldest reinjection "
                f"{num(y.reinjection_c)} °C",
            ],
        ]
        if top is not None and limit is not None:
            rows.append(
                [
                    "Injection pressure, top of reservoir",
                    f"{num(top)} bar against SodM's {num(limit)} bar ({SODM_BAR_PER_M:g} bar/m): "
                    f"{num(limit - top)} bar to spare",
                ]
            )
        if r.get("esp_setting_m") is not None:
            rows.append(
                [
                    "ESP setting",
                    f"{num(r['esp_setting_m'], 0)} m or deeper (gas bubble point "
                    f"{num(r.get('bubble_point_bar'))} bar); at most "
                    f"{num(ESP_MAX_SETTING_M, 0)} m",
                ]
            )
        if r.get("breakthrough_years") is not None:
            rows.append(
                [
                    "Cold water reaches the producer",
                    f"after about {num(r['breakthrough_years'], 0)} years (Gringarten & Sauty)",
                ]
            )
        doc.heading(tag, table=True)
        doc.table([("Figure", 2.2, "left"), ("Value", 4.9, "left")], rows)
    burned, flared = y.produced_gas_burned_gwh or 0.0, y.produced_gas_flared_gwh or 0.0
    sold = getattr(y, "produced_gas_sold_gwh", 0.0) or 0.0
    words = (
        f"The brine's gas: {num(burned)} GWh a year burnt in the boiler, {num(sold)} GWh sold, "
        f"{num(flared)} GWh flared."
    )
    if flared > 0.05:
        words += (
            " Routine flaring needs consent under the Mijnbouwbesluit (art. 38 and 84), and the "
            "EU Methane Regulation 2024/1787 allows it only in the situations it lists."
        )
    doc.para(words)


def _sde(doc: _Doc, econ: dict) -> None:
    inv = econ.get("investor") or {}
    sde = inv.get("sde") or {}
    cat = sde.get("category") or {}
    doc.section_head(
        2,
        "SDE++: the subsidy for the geothermal heat",
        "The category for the plant's capacity in the 2026 round, as PBL advised it, and the "
        "subsidy the design's year would earn (the Economics tab's investor view).",
        need=2.6,
    )
    if not cat:
        doc.para("This design has no geothermal heat: no SDE++ category applies.")
        return
    rows = [
        ["Category", f"{cat.get('name')} ({cat.get('label')})"],
        [
            "Base amount",
            f"{num((cat.get('basis_eur_per_kwh') or 0) * 1000, 1)} €/MWh, at most "
            f"{num(cat.get('full_load_hours'), 0)} full-load hours a year",
        ],
        [
            "Capacity applied for",
            f"{num(sde.get('installation_mw'))} MW ({sde.get('installation')}; the brine at "
            f"{num(sde.get('flow_m3h'), 0)} m³/h cooled {num(sde.get('brine_cooling_k'))} K)",
        ],
        [
            "Heat that qualifies",
            f"{num(sde.get('subsidised_gwh'))} GWh a year (of {num(sde.get('cap_gwh'))} GWh "
            "the hours allow)",
        ],
        [
            "Subsidy",
            f"{num((sde.get('per_kwh_first') or 0) * 1000, 1)} €/MWh the first year (the base "
            f"amount less PBL's gas correction of "
            f"{num((sde.get('correction_eur_per_kwh') or 0) * 1000, 1)} €/MWh): "
            f"{num(sde.get('meur_first_year'), 2)} M€, then about "
            f"{num(sde.get('meur_average'), 2)} M€ a year; "
            f"{num(sde.get('total_meur'), 1)} M€ over years {sde.get('first_year')} to "
            f"{sde.get('last_year')}",
        ],
    ]
    doc.table([("Item", 2.2, "left"), ("Value", 4.9, "left")], rows)
    doc.para(f"Source: {cat.get('source', 'PBL, SDE++ 2026 advice')}.", 8.5)
    if inv.get("needs_subsidy"):
        doc.para(
            "Without SDE++ the design does not pay back for an investor (the Economics tab's "
            "investor view): the application matters.",
            9,
            TEAL,
            bold=True,
        )


def _environment(doc: _Doc, entry: LedgerEntry) -> None:
    from gemini_agent import cooling_check

    y = entry.year
    e = entry.economics
    co2 = y.co2_t or {}
    doc.section_head(
        3,
        "Environment and grid",
        "The figures an environment permit and the grid operator ask for.",
        need=2.4,
    )
    items = [
        f"CO2: {num(co2.get('total'), 0)} t a year ({num((e.co2_saving_vs_gas or 0) * 100, 0)} % "
        "less than gas boilers and electric chillers); the gas bought adds about "
        f"{num(co2.get('upstream_gas_co2e', 0), 0)} t CO2-equivalent before it reaches the "
        "plant (not in the total)."
    ]
    el = y.electricity_gwh or {}
    items.append(f"Grid electricity: {num(sum(el.values()), 1)} GWh a year.")
    # The towers' water from the year (all the heat they reject, free cooling's too); a design
    # from before 4 Nov has none, and the cooling check (which now counts the same) stands in.
    water = getattr(y, "tower_water_m3", None) or {}
    if not water.get("makeup"):
        try:
            cc = cooling_check.check(entry)
        except Exception:  # noqa: BLE001 - the pack stands without it
            cc = None
        if cc:
            water = {
                "makeup": cc["makeup_water_m3"],
                "evaporation": cc["evaporation_m3"],
                "blowdown": cc["blowdown_m3"],
            }
    if water.get("makeup"):
        items.append(
            f"Cooling towers: {num(water['makeup'], 0)} m³ of make-up water a year "
            f"({num(water['evaporation'], 0)} m³ evaporated, {num(water['blowdown'], 0)} m³ "
            "blown down), for the water permits; all the heat the towers reject, free "
            "cooling's included."
        )
    doc.bullets(items)


def build(session, design_id: Optional[str] = None, today: Optional[date] = None) -> bytes:
    """Return the permit and subsidy pack of a design (the chosen one by default) as a PDF."""
    found = target(session, design_id)
    entry = _with_days(found, session)
    today = today or date.today()
    did = reporter.design_id(found)
    econ = workbench.economics_view(entry, session.assumptions or {})
    with matplotlib.rc_context(RC):
        doc = _Doc(did, f"Permit and subsidy pack of {today.day} {today:%B %Y}")
        doc.kind = "Permit and subsidy pack"
        doc.new_page("Permit and subsidy pack")
        size, lines = fit(f"Permit and subsidy pack: {did}", WIDTH, 18, 12, bold=True, lines=2)
        for line in lines:
            doc.put(LEFT, doc.y, line, size, TEAL, bold=True)
            doc.y += size * 1.25 / 72
        doc.y += 0.11
        doc.para(
            "The figures from this design that the mining permit's production plan, the SDE++ "
            "application and the environment permits ask for, each with its source. The "
            "applications also need studies a design model cannot give: they are listed at the "
            "end.",
            9.5,
        )
        _mining(doc, entry)
        _sde(doc, econ)
        _environment(doc, entry)
        doc.section_head(4, "Not in this pack", "What the applications also need.", need=2.0)
        doc.bullets(NOT_IN_PACK)
        return doc.finish(
            {
                "Title": f"Permit and subsidy pack: {did}",
                "Author": "Dioscuri",
                "Creator": "Dioscuri agent (matplotlib)",
                "CreationDate": datetime(today.year, today.month, today.day),
            }
        )
