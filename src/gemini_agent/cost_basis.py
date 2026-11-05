"""What a design's cost per MWh includes and leaves out, and how far it moves.

Judges compare teams' €/MWh, which only means something with its basis: what is in it, at which
discount rate and lifetimes, at which prices, and how heat and cold share the costs. ``basis``
says all of that for one design, and reprices the same plant (``engine.reprice``, about 20 ms
each) with one assumption changed at a time, so each swing is the real economics, not a guess.
The plant stays as designed: a search at other prices might pick another design.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from dioscuri_plant.economics import SOURCES, Prices
from gemini_agent import engine
from gemini_agent.contract import LedgerEntry

# What every design's cost leaves out, and why (the sources say so; see each line).
EXCLUDES = [
    {
        "item": "The district network",
        "why": "Pipes to the buildings and their substations are not priced: the cost is at the "
        "plant's gate. A network length on the inputs card adds its heat loss and pumping, not "
        "its pipes.",
    },
    {
        "item": "Exploration and project preparation",
        "why": "Left out by PBL's SDE++ costs, to which ThermoGIS v3's well and plant costs are "
        "calibrated (PBL 2026, Table 11.2).",
    },
    {
        "item": "Abandoning the wells",
        "why": "PBL assumes the abandonment cost and the residual value cancel; neither is "
        "counted.",
    },
    {
        "item": "SDE++, sales and corporate tax",
        "why": "This is what the heat and cold cost to make. The investor's view, with subsidy, "
        "sales and tax, is apart (below on the Economics tab).",
    },
    {
        "item": "What failures cost a year",
        "why": "Said apart (Sensitivity tab); PBL's fixed O&M already provides for ESP "
        "replacements.",
    },
    {
        "item": "VAT, and the CO₂ of the electricity",
        "why": "Prices are without VAT (the electricity price keeps its energy tax and network "
        "charges); power stations pay for their CO₂ under the EU ETS, inside the electricity "
        "price.",
    },
]

# Capital items as the basis names them, in this order.
CAPITAL_WORDS = {
    "Wells": "Wells: drilling, casing and the ESP",
    "Surface plant": "Surface plant: exchangers, pumps, civil works, grid connection",
    "Treatment trains": "Treatment train: gas separator and filters",
    "Heat pump": "Heat pump",
    "Boiler": "Gas boiler",
    "Electric boiler": "Electric boiler, with its grid connection",
    "Absorption chiller": "Absorption chiller, with its cooling tower",
    "Electric chillers": "Electric chillers, with their cooling towers",
    "Free-cooling exchanger": "Free-cooling exchanger",
    "Heat store": "Hot-water store",
}

LIFE_KEYS = (
    ("Wells and surface plant", "wells_life_years"),
    ("Heat pump", "heat_pump_life_years"),
    ("Gas boiler", "boiler_life_years"),
    ("Electric boiler", "electric_boiler_life_years"),
    ("Absorption chiller", "absorption_life_years"),
    ("Electric chillers", "chiller_life_years"),
)
LIFE_ITEMS = {
    "wells_life_years": ("Wells", "Surface plant", "Treatment trains"),
    "heat_pump_life_years": ("Heat pump",),
    "boiler_life_years": ("Boiler",),
    "electric_boiler_life_years": ("Electric boiler",),
    "absorption_life_years": ("Absorption chiller",),
    "chiller_life_years": ("Electric chillers",),
}


def _is_pbl(rate: float) -> bool:
    return abs(rate - Prices().discount_rate) < 1e-9


def rate_words(rate: float, investor: bool = True) -> str:
    """Say the discount rate and its basis: PBL's after-tax WACC, with no tax in the cost.

    ``investor`` adds that the investor's case adds the tax (not for the gas plant, which has
    no such case).
    """
    basis = (
        "PBL's after-tax WACC"
        if _is_pbl(rate)
        else f"set in this chat (PBL's after-tax WACC is {_pct(Prices().discount_rate)})"
    )
    return f"{_pct(rate)} real, {basis}; corporate tax is not in the cost of heat" + (
        "; the investor case adds it" if investor else ""
    )


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".rstrip("0").rstrip(".") + " %"


def _num(x: float) -> str:
    return f"{x:,.1f}".rstrip("0").rstrip(".") if x != int(x) else f"{int(x):,}"


def heat_share(entry: LedgerEntry) -> float:
    """Return the heat's share of the brine heat, which splits the shared costs (``economics``)."""
    y = entry.year
    hp_source = y.heat_split_gwh.get("hp", 0.0) - y.electricity_gwh.get("hp", 0.0)
    heat = y.heat_split_gwh.get("geo", 0.0) + max(hp_source, 0.0)
    cold = y.cool_split_gwh.get("abs", 0.0) / y.absorption_cop if y.absorption_cop else 0.0
    return heat / (heat + cold) if heat + cold > 0 else 1.0


def swings(entry: LedgerEntry, assumptions: Optional[dict] = None) -> List[dict]:
    """Return how far the cost of heat and cold moves with each assumption, low and high.

    Each case reprices the same plant with one assumption changed from the conversation's own
    (``engine.reprice``). Sorted by how far it moves, the widest first.
    """
    base_a = dict(assumptions or {})
    prices = engine.prices_for(base_a, entry.brief)
    e = entry.economics
    cases = [
        (
            "discount_rate",
            "Discount rate (real)",
            (0.03, 0.08),
            lambda v: _pct(v),
            f"{_pct(prices.discount_rate)} (PBL)",
        ),
        (
            "electricity_eur_per_mwh",
            "Electricity price",
            (prices.electricity_eur_per_mwh * 0.5, prices.electricity_eur_per_mwh * 1.5),
            lambda v: f"{v:,.0f} €/MWh",
            f"{prices.electricity_eur_per_mwh:,.1f} €/MWh",
        ),
        (
            "gas_eur_per_mwh",
            "Gas price",
            (prices.gas_eur_per_mwh * 0.5, prices.gas_eur_per_mwh * 1.5),
            lambda v: f"{v:,.0f} €/MWh",
            f"{prices.gas_eur_per_mwh:,.1f} €/MWh",
        ),
        (
            "carbon_eur_per_t",
            "CO₂ price",
            (0.0, prices.carbon_long_term_eur_per_t),
            lambda v: f"{v:,.0f} €/t",
            f"{prices.carbon_eur_per_t:,.1f} €/t",
        ),
        (
            "capex_scale",
            "Capital costs",
            (0.7, 1.3),
            lambda v: f"{(v - 1) * 100:+.0f} %".replace("-", "−"),
            "as sourced",
        ),
        (
            "wells_life_years",
            "Life of the wells and surface plant",
            (20, 40),
            lambda v: f"{v:.0f} years",
            f"{prices.wells_life_years} years",
        ),
    ]
    out = []
    for key, label, (lo, hi), words, base_words in cases:
        moved = []
        for v in (lo, hi):
            a = dict(base_a, **{key: v})
            if key == "capex_scale" and base_a.get("capex_scale"):
                a[key] = float(base_a["capex_scale"]) * v
            r = engine.reprice(entry, a).economics
            moved.append(r)
        if not (e.lcoe_eur_per_mwh or 0) and not any(m.lcoe_eur_per_mwh for m in moved):
            continue
        out.append(
            {
                "key": key,
                "label": label,
                "base": base_words,
                "low": {
                    "value": words(lo),
                    "lcoe": moved[0].lcoe_eur_per_mwh,
                    "lcoh": moved[0].lcoh_eur_per_mwh,
                    "lcoc": moved[0].lcoc_eur_per_mwh,
                },
                "high": {
                    "value": words(hi),
                    "lcoe": moved[1].lcoe_eur_per_mwh,
                    "lcoh": moved[1].lcoh_eur_per_mwh,
                    "lcoc": moved[1].lcoc_eur_per_mwh,
                },
            }
        )
    out.sort(key=lambda s: -abs((s["high"]["lcoe"] or 0) - (s["low"]["lcoe"] or 0)))
    return out


def basis(entry: LedgerEntry, assumptions: Optional[dict] = None, moves: bool = True) -> dict:
    """Return a design's cost basis: what is in, what is out, rate, lives, prices, split, swings.

    Parameters
    ----------
    entry : LedgerEntry
        The design, priced at the conversation's prices (``engine.reprice`` when they changed).
    assumptions : dict, optional
        The conversation's changed prices (``Prices`` keys), the base of the swings.
    moves : bool
        Also reprice it with each assumption changed (``swings``).

    Returns
    -------
    dict
        ``headline`` (€/MWh of heat and cold, heat, cold), ``includes`` (each part with its
        €/MWh), ``excludes``, ``rate``, ``lifetimes``, ``prices``, ``split`` and ``swings``.
    """
    a = dict(assumptions or {})
    prices = engine.prices_for(a, entry.brief)
    e, y = entry.economics, entry.year
    lost = (y.network or {}).get("heat_loss_gwh", 0.0) or 0.0
    heat_mwh = max(y.heat_delivered_gwh - lost, 0.0) * 1000
    cold_mwh = y.cool_delivered_gwh * 1000
    mwh = heat_mwh + cold_mwh

    # Each part of the cost, summed over heat and cold, per MWh of both (the headline's terms):
    # the capital items first, then the running costs.
    parts: Dict[str, float] = {}
    kinds: Dict[str, str] = {}
    rank: Dict[str, int] = {}
    words = list(CAPITAL_WORDS)

    def put(name: str, kind: str, at: int, meur: float) -> None:
        parts[name] = parts.get(name, 0.0) + meur
        kinds.setdefault(name, kind)
        rank.setdefault(name, at)

    capital = {it["item"] for it in (e.capex_items or [])}
    for item, kind, meur in list(e.lines_heat or []) + list(e.lines_cold or []):
        meur = float(meur)
        if kind == "capital":
            at = words.index(item) if item in words else len(words)
            put(CAPITAL_WORDS.get(item, item), "capital", at, meur)
        elif kind in ("fixed", "variable"):
            put("Operation and maintenance", "o&m", 100, meur)
        elif kind == "electricity":
            put(f"Electricity at {prices.electricity_eur_per_mwh:,.1f} €/MWh", kind, 101, meur)
        elif kind == "gas" and meur >= 0:
            put(f"Gas bought at {prices.gas_eur_per_mwh:,.1f} €/MWh", kind, 102, meur)
        elif kind == "gas":
            put("The brine's gas sold (a credit)", "credit", 104, meur)
        elif kind == "carbon":
            put(f"CO₂ of the gas burnt at {prices.carbon_eur_per_t:,.1f} €/t", kind, 103, meur)
        else:
            put(item, kind, 105, meur)
    total = sum(v for v in parts.values() if v > 0) or 1.0
    includes = [
        {
            "item": name,
            "kind": kinds[name],
            "eur_per_mwh": round(parts[name] * 1e6 / mwh, 2) if mwh else 0.0,
            "share": round(parts[name] / total, 4),
        }
        for name in sorted(parts, key=lambda n: rank[n])
        if abs(parts[name]) > 1e-9
    ]
    om_note = (
        "PBL's fixed O&M for the geothermal part ("
        f"{prices.geothermal_fixed_eur_per_kw:g} €/kW a year: insurance, staff and the ESP "
        "replacements), each unit's own maintenance"
    )
    for row in includes:
        if row["item"] == "Operation and maintenance":
            row["note"] = om_note if entry.alternative.depth_m else "each unit's own maintenance"

    lives = []
    for label, key in LIFE_KEYS:
        if any(i in capital for i in LIFE_ITEMS[key]):
            lives.append({"label": label, "years": int(getattr(prices, key))})
    share = heat_share(entry)
    shared = entry.alternative.depth_m > 0
    split = {
        "heat_share": round(share, 4) if shared else None,
        "text": (
            "Costs that serve both, the wells, the surface plant, the pumps and the brine's gas, "
            "are shared by the brine heat each side uses: "
            + (
                f"heating takes {share * 100:.0f} %, cooling {100 - share * 100:.0f} % (the "
                "absorption chiller's driving heat). "
                if share < 0.9995
                else "here heating takes all of it, since no cold is made from the brine. "
            )
            + "A unit that serves one side is that side's alone."
            if shared
            else "No wells: each unit is its own side's."
        ),
        "headline": (
            "The headline is heat and cold together: every cost of the year over every MWh "
            "delivered"
            + (
                f" ({heat_mwh / 1000:,.1f} GWh of heat and {cold_mwh / 1000:,.1f} GWh of cold)."
                if cold_mwh
                else f" ({heat_mwh / 1000:,.1f} GWh of heat)."
            )
        ),
    }
    return {
        "design": entry.alternative.code,
        "headline": {
            "lcoe": e.lcoe_eur_per_mwh,
            "lcoh": e.lcoh_eur_per_mwh,
            "lcoc": e.lcoc_eur_per_mwh,
            "capex_meur": e.capex_meur,
        },
        "method": (
            "Levelised cost: each unit's capital paid off over its own life at one real discount "
            f"rate ({rate_words(prices.discount_rate)}), plus a year's running costs, over the "
            "MWh delivered. Prices in 2025 euros."
        ),
        "includes": includes,
        "excludes": EXCLUDES,
        "rate": {
            "value": prices.discount_rate,
            "label": f"{_pct(prices.discount_rate)} real"
            + (", after tax" if _is_pbl(prices.discount_rate) else ""),
            "source": SOURCES["discount_rate"],
            "note": rate_words(prices.discount_rate),
        },
        "lifetimes": lives,
        "prices": [
            {
                "label": "Electricity",
                "value": f"{prices.electricity_eur_per_mwh:,.1f} €/MWh",
                "source": SOURCES["electricity_eur_per_mwh"],
            },
            {
                "label": "Gas",
                "value": f"{prices.gas_eur_per_mwh:,.1f} €/MWh",
                "source": SOURCES["gas_eur_per_mwh"],
            },
            {
                "label": "CO₂",
                "value": f"{prices.carbon_eur_per_t:,.1f} €/t",
                "source": SOURCES["carbon_eur_per_t"],
            },
        ],
        "split": split,
        "swings": swings(entry, a) if moves else [],
        "note": (
            "Each swing reprices this same plant with one assumption changed; a search at those "
            "prices might pick another design."
        ),
    }
