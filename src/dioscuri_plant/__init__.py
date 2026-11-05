"""Dioscuri's plant model: the energy system around the wells, over a year, and its costs.

``simulate_year(plant, demand, doublet, rules)`` runs a design day by day and reports every
broken hard cap; ``economics(plant, year, prices)`` prices it. Pure functions of plain
dataclasses (numpy only), so the agent can run hundreds of designs in a second.
"""

from dioscuri_plant.components import Components
from dioscuri_plant.doublet import stub_doublet
from dioscuri_plant.economics import Prices, economics
from dioscuri_plant.investor import InvestorCase, InvestorTerms, investor_case
from dioscuri_plant.search import Candidate, SearchResult, Topology, search
from dioscuri_plant.types import (
    Aquifer,
    Demand,
    Doublet,
    DoubletModel,
    Economics,
    Plant,
    Rules,
    YearResult,
)
from dioscuri_plant.year import SOURCE, simulate_year

__all__ = [
    "Aquifer",
    "Candidate",
    "Components",
    "Demand",
    "Doublet",
    "DoubletModel",
    "Economics",
    "InvestorCase",
    "InvestorTerms",
    "investor_case",
    "Plant",
    "Prices",
    "Rules",
    "SOURCE",
    "SearchResult",
    "Topology",
    "YearResult",
    "economics",
    "search",
    "simulate_year",
    "stub_doublet",
]
