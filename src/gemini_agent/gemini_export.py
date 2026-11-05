"""A design's brine loop as a GEMINI project file, for GEMINI's own loader.

GEMINI's simulator reads a plant as JSON: its components (type and parameters), its boundary
inputs and its connections in order (``gemini_simulator.project_loader.load_project``). The
Design tab's GEMINI view already builds that project for each design
(``tools.gemini.plant_project``: producers, treatment trains, the heat exchanger, the injectors,
the boiler on the separated gas). The export writes it as a file GEMINI loads as it is, with a
``dioscuri`` block it ignores: where the design came from, what GEMINI cannot simulate (the heat
pump, the chillers, the absorption chiller, storage and solar stay in our plant model) and the
design's daily flows, so the year can be replayed on GEMINI's solver step by step.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from gemini_agent.contract import LedgerEntry

NOT_IN_GEMINI = {
    "heat_pump": "heat pump",
    "chillers": "electric chillers",
    "absorption": "absorption chiller",
    "electric_boiler": "electric boiler",
}


def project(entry: LedgerEntry) -> Optional[dict]:
    """Return the design's GEMINI project with the ``dioscuri`` block, or None (no doublet)."""
    from gemini_agent import engine, workbench

    proj = workbench.graph_view(entry).get("gemini_project")
    if not proj:
        return None
    y, a = entry.year, entry.alternative
    rules = engine.rules_for(entry.brief)
    outside = [w for k, w in NOT_IN_GEMINI.items() if (a.sizes_mw or {}).get(k)]
    if getattr(y, "storage", None) and (y.storage or {}).get("given_gwh"):
        outside.append("hot-water store")
    if getattr(y, "solar", None):
        outside.append("solar panels")
    if (y.cool_split_gwh or {}).get("free"):
        outside.append("free cooling")
    flows = [
        {"doublet": i + 1, "flow_m3h": list(d.get("flow_m3h") or [])}
        for i, d in enumerate(y.doublets or [])
    ]
    return {
        **proj,
        "dioscuri": {
            "design": a.code,
            "exported": date.today().isoformat(),
            "project": entry.brief.project_id,
            "load_with": "gemini_simulator.project_loader.load_project(path)",
            "flows_at": "each producer's flow cap; the year's daily flows are below",
            "not_in_gemini": outside,
            "reservoir": {
                "depth_m": rules.reservoir_depth_m,
                "temperature_c": round(rules.reservoir_temperature_c(), 2),
                "permeability_md": rules.permeability_md,
                "thickness_m": rules.reservoir_thickness_m,
            },
            "daily_flows": flows,
        },
    }


def filename(entry: LedgerEntry) -> str:
    """Return the file's name, ``dioscuri-1D-HP-EC-N1.gemini.json``."""
    code = re.sub(r"[^A-Za-z0-9_.-]+", "-", entry.alternative.code).strip("-.") or "design"
    return f"dioscuri-{code}.gemini.json"
