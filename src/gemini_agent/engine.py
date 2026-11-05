"""The challenge engine: GEMINI's doublet and Dioscuri's plant model behind the agent.

Every design the agent reports comes from here:

- the doublet (flow, pumps, wellhead) from GEMINI's well solve with the team's patches and the
  challenge's brine (``tools.gemini.doublet_model``);
- the year, day by day, and its costs from ``dioscuri_plant`` (the energy system around the
  wells, the challenge's caps, sourced prices);
- the search over depth, doublets, top-up and cooling, each candidate improved until its caps
  hold (``dioscuri_plant.search``).

The results come back as the agent's ledger entries (``contract``), so the chat, the checks
and the tabs read them as before. Nothing here is a stand-in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, replace
from functools import lru_cache
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import dioscuri_plant as dp
from dioscuri_plant import explore
from dioscuri_plant.firm import outages, peak_margin
from dioscuri_plant.firm import reliable as reliable_plan
from dioscuri_plant.investor import capital_flows
from dioscuri_plant.parallel import pmap
from dioscuri_plant.search import (
    ABSORPTION_SHARE,
    CO2_BAND,
    HEAT_PUMP_SHARES,
    Candidate,
    Round,
    Topology,
    flag_words,
    improve,
)
from dioscuri_plant.search import plant_code as _plant_code
from dioscuri_plant.search import (
    plant_flags,
    reference_rules,
)
from gemini_agent import aquifers, gemini_runtime, projects, verifier
from gemini_agent.contract import (
    Alternative,
    DesignBrief,
    Economics,
    LedgerEntry,
    NetworkTemps,
    YearResult,
)
from gemini_agent.tools.gemini import doublet_model

DATA = projects.CHALLENGE_DIR
HEAT_CSV = DATA / "GEMINI_Heating_Demand_Daily_2027.csv"
COOL_CSV = DATA / "GEMINI_Cooling_Demand_Daily_2027.csv"
REQUIREMENTS_PDF = DATA / "GEMINI_Hackathon_Challenge_Requirements.docx.pdf"
DEFAULT_HEATING = NetworkTemps(supply_c=100.0, return_c=60.0)
DEFAULT_COOLING = NetworkTemps(supply_c=20.0, return_c=25.0)
SOURCE_GEMINI = "gemini+dioscuri_plant"
SOURCE_PLANT = "dioscuri_plant"
# The picks of a search, by objective: best overall, cheapest, least CO2, the cheapest reliable
# plan, the greenest reliable plan and the cheapest gas-free one. Every reliable (N-1) plan is
# as reliable as the others on every measure the code has, so the "reliable" pick is the
# cheapest of them and is named so (4 Nov: it was "most reliable").
PICKS = ("best", "cost", "co2", "reliable", "green_reliable", "gas_free")
PICK_NAMES = {
    "best": "best overall",
    "cost": "cheapest",
    "co2": "lowest CO2",
    "reliable": "cheapest reliable",
    "green_reliable": "greenest reliable",
    "gas_free": "gas-free",
}
RELIABLE_TOP = 6  # the cheapest layouts (and the lowest-CO2 one) that get a reliable plan


def demand(project_id: str = projects.CHALLENGE) -> dp.Demand:
    """Return a project's daily demand for the year (heat and cold, MW): the organisers' 2027."""
    return projects.registry().demand(project_id)


def rules_for(brief: Optional[DesignBrief] = None) -> dp.Rules:
    """Return the project's rules (its reservoir, the challenge's caps) with the brief's changes.

    The brief may set other network temperatures, a warmer or colder reservoir, and any of
    the rules' fields (``brief.rules``: a what-if, or the user's).
    """
    brief = brief or DesignBrief()
    heating = brief.heating or DEFAULT_HEATING
    cooling = brief.cooling or DEFAULT_COOLING
    base = projects.registry().rules(brief.project_id)
    known = {f.name for f in fields(dp.Rules)}
    extra = {k: v for k, v in (brief.rules or {}).items() if k in known}
    if "operating_days" in extra:
        extra["operating_days"] = int(round(extra["operating_days"]))
    extra.pop("doublet_stops", None)
    if brief.doublet_stops:  # the user's dates for the doublets' stops (the inputs card)
        extra["doublet_stops"] = tuple(
            tuple((int(a), int(b)) for a, b in d) for d in brief.doublet_stops
        )
    # The aquifers the user described: the known one's values, then the brief's own changes
    # (a what-if) on top; the list replaces the older second aquifer.
    found = aquifers.rules_update(brief, base)
    if found:
        extra = {k: v for k, v in extra.items() if k not in aquifers.SECOND_RULES}
        extra = {**found, **extra}
    return replace(
        base,
        heat_supply_c=heating.supply_c,
        heat_return_c=heating.return_c,
        cool_supply_c=cooling.supply_c,
        cool_return_c=cooling.return_c,
        surface_temperature_c=base.surface_temperature_c + (brief.reservoir_delta_c or 0.0),
        **extra,
    )


# Every capital cost among ``dioscuri_plant.Prices`` (each unit's M€ per MW, MWh or doublet, and
# the wells' scale, which also prices an HT-ATES store's wells): what "capital costs ×1.3" scales,
# here (``capex_scale``) and on the Sensitivity tab (``workbench``). Own solar is not here: its
# price is PBL's whole cost per MWh, a running cost.
CAPEX_KEYS = (
    "well_scale",
    "surface_per_doublet_meur",
    "treatment_train_meur",
    "surface_meur_per_mw",
    "heat_pump_meur_per_mw",
    "boiler_meur_per_mw",
    "electric_boiler_meur_per_mw",
    "absorption_meur_per_mw",
    "chiller_meur_per_mw",
    "free_cooling_meur_per_mw",
    "storage_meur_per_mwh",
)


def project_caps(brief: Optional[DesignBrief] = None) -> dp.Rules:
    """Return the project's own caps and supply temperatures, whatever the brief relaxed."""
    brief = brief or DesignBrief()
    try:
        base = projects.registry().rules(brief.project_id)
    except KeyError:
        base = dp.Rules()
    heating = brief.heating or DEFAULT_HEATING
    cooling = brief.cooling or DEFAULT_COOLING
    # The supplies are fixed for the challenge; a user project's are its own networks'.
    if brief.project_id != projects.CHALLENGE:
        base = replace(base, heat_supply_c=heating.supply_c, cool_supply_c=cooling.supply_c)
    return base


def prices_for(
    assumptions: Optional[dict] = None, brief: Optional[DesignBrief] = None
) -> dp.Prices:
    """Return the prices with the conversation's changes and the brief's (keys of ``Prices``).

    ``capex_scale`` multiplies every capital cost.
    """
    known = {f.name for f in fields(dp.Prices)}
    merged = dict(assumptions or {})
    merged.update((brief.prices if brief is not None else None) or {})
    changes = {k: v for k, v in merged.items() if k in known and v is not None}
    if "well_spacing_m" not in changes and brief is not None:
        # A project's own spacing (Trias Westland's 1,800 m) sets the wells' along-hole length.
        try:
            spacing = projects.registry().rules(brief.project_id).well_spacing_m
        except KeyError:
            spacing = None
        if spacing and spacing != dp.Rules().well_spacing_m:
            changes["well_spacing_m"] = spacing
    prices = replace(dp.Prices(), **changes)
    scale = merged.get("capex_scale")
    if scale:
        prices = replace(prices, **{k: getattr(prices, k) * float(scale) for k in CAPEX_KEYS})
    return prices


def demand_of(brief: DesignBrief) -> dp.Demand:
    """Return the brief's demand: the project's, scaled when the brief says so."""
    scale = tuple(float(x) for x in (brief.demand_scale or [1.0, 1.0]))
    return scaled_demand(scale, brief.project_id)


@dataclass
class Outcome:
    """A search, as ledger entries: the chosen design, every candidate and the reference."""

    chosen: Optional[LedgerEntry]
    candidates: List[LedgerEntry]
    reference: LedgerEntry
    objective: str
    rules: dp.Rules
    notes: List[str] = field(default_factory=list)
    years: int = 0  # simulated years in all
    sizings: int = 0  # sizings run in all
    picks: Dict[str, str] = field(default_factory=dict)  # objective -> code (``PICKS``)
    # The design-space sweep for the map (``dioscuri_plant.explore.Exploration.as_dict``).
    sweep: Optional[dict] = None
    # The prices the search ran under (the conversation's), for ``ranked``; None: the defaults.
    prices: Optional[dp.Prices] = None

    @property
    def tried(self) -> List[LedgerEntry]:
        """Return the distinct candidates (identical plants listed once)."""
        return [e for e in self.candidates if e.alternative.role != "same"]

    def as_dict(self) -> Dict[str, object]:
        """Return the search in brief, for the trace: counts, the pick and each candidate."""
        return {
            "summary": summary(self),
            "chosen": self.chosen.alternative.code if self.chosen else None,
            "picks": dict(self.picks),
            "reference": {
                "lcoh": self.reference.economics.lcoh_eur_per_mwh,
                "co2_t": self.reference.economics.co2_t_per_year,
            },
            "candidates": [
                {
                    "code": e.alternative.code,
                    "role": e.alternative.role,
                    "lcoe": e.economics.lcoe_eur_per_mwh,
                    "co2_t": e.economics.co2_t_per_year,
                    "rounds": len(e.alternative.rounds),
                    "reason": e.alternative.reason,
                }
                for e in ranked(self)
            ],
            "notes": self.notes,
        }


def search(brief: DesignBrief, assumptions: Optional[dict] = None) -> Outcome:
    """Search the designs for a brief and return them as ledger entries, with the picks.

    Every layout is sized, run and priced (``dioscuri_plant.search``, ranked by cost, or by CO2
    when that is the objective); the cheapest layouts and the lowest-CO2 one then get a reliable
    plan as well (``dioscuri_plant.firm.reliable``: any one unit can be out). The picks:

    - ``cost``: the lowest cost of heat and cold;
    - ``co2``: the least CO2 (the cheapest within 2 % of the lowest);
    - ``reliable``: the cheapest reliable plan;
    - ``best``: the reliable plan that is cheapest with CO2 at the long-term price
      (``Prices.carbon_long_term_eur_per_t``).

    The brief's objective says which is chosen.

    Parameters
    ----------
    brief : DesignBrief
        What was asked: network temperatures, exclusions, the number of doublets, depths, and
        what "best" means.
    assumptions : dict, optional
        The conversation's prices and costs (``dioscuri_plant.Prices`` keys).

    Returns
    -------
    Outcome
        The chosen design (None when no candidate meets every cap), all candidates, the picks
        and the gas reference.
    """
    rules, prices = rules_for(brief), prices_for(assumptions, brief)
    excluded = [e for e in brief.excluded]
    fixed = fixed_options(brief, rules)
    doublets = (brief.n_doublets,) if brief.n_doublets else (1, 2, 3)
    depths = aquifers.search_depths(brief, rules)
    demand = demand_of(brief)
    model = doublet_model(rules)
    result = dp.search(
        demand,
        model,
        rules,
        dp.Components(),
        prices,
        excluded=excluded,
        doublets=doublets,
        depths=depths,
        objective="co2" if brief.objective == "co2" else "cost",
        fixed=fixed,
    )
    cands = list(result.candidates)
    plans = _reliable_plans(cands, demand, model, rules, prices, excluded, result.reference)
    free = _gas_free(cands, demand, model, rules, prices, excluded, result.reference, fixed)
    free += _reliable_plans(
        cands, demand, model, rules, prices, excluded, result.reference, only=free
    )
    sweep = None
    n_sweep = int(os.environ.get("DIOSCURI_SWEEP", str(explore.DEFAULT_N)))
    if n_sweep > 0 and not fixed:
        # Thousands of designs drawn across the space (failures kept, for the map); the best
        # feasible ones, refined, join the candidates (and get reliable plans too).
        sweep = explore.explore(
            demand,
            model,
            rules,
            dp.Components(),
            prices,
            (result.reference.year, result.reference.economics),
            excluded=excluded,
            doublets=doublets,
            depths=(min(depths), max(depths)),
            n=n_sweep,
            # Only the aquifers described, when every depth is one (else any depth between).
            levels=(
                depths
                if len(depths) > 1 and all(rules.aquifer_index(d) is not None for d in depths)
                else ()
            ),
        )
        fresh = [c for c in sweep.refined if c.status == "valid"]
        cands += fresh + _reliable_plans(
            cands + fresh, demand, model, rules, prices, excluded, result.reference, only=fresh
        )
    cands += plans + free
    reference = to_entry(result.reference, brief, rules, None)
    entries = [to_entry(c, brief, rules, result.reference) for c in cands]
    # The options the search tries itself (3 Nov): free cooling where there are towers, own
    # solar sized to the plant's load, the brine's gas sold instead of flared. Each a variant of
    # the best designs and reliable plans, with its own brief so it runs again the same way.
    optional = _options(cands, demand, model, rules, prices, result.reference)
    for c, extra in optional:
        o_brief = brief.model_copy(update={"rules": {**(brief.rules or {}), **extra}})
        entries.append(to_entry(c, o_brief, replace(rules, **extra), result.reference))
    cands = cands + [c for c, _ in optional]
    # Each candidate's year with each unit out, in worker processes (``parallel.pmap``).
    firms = pmap(_firm_with, [c.plant for c in cands], {"demand": demand, "rules": rules})
    for e, f in zip(entries, firms):
        e.firm = f
    # Picks by entry, not by code: two sizings of one layout share a code (a reliable plan of
    # the cheapest sizing and of the one best with CO2 at the long-term price).
    picked_of = pick_entries(entries, prices, brief.min_co2_saving)
    picks = {k: e.alternative.code for k, e in picked_of.items()}
    chosen = None
    want = picked_of.get(brief.objective)
    for e in entries:
        if e.alternative.role == "chosen":
            e.alternative.role = "candidate"
        e.alternative.picks = [k for k in PICKS if picked_of.get(k) is e]
        if e is want and e.alternative.role == "candidate" and chosen is None:
            chosen = e
    if chosen is not None:
        chosen.alternative.role = "chosen"
        for e in entries:
            if e is not chosen and e.alternative.role == "candidate":
                lost = lost_reason(e, chosen, brief.objective, prices)
                eff = e.alternative.effect
                e.alternative.reason = f"{eff}; {lost}" if eff else lost
    notes = [f"ranked by {OBJECTIVE_WORDS[brief.objective]}"]
    best = picked_of.get("best")
    if best is not None and best.alternative.reliable:
        prices_now = prices
        rel = [
            e
            for e in entries
            if e.alternative.reliable and e.alternative.role in ("chosen", "candidate")
        ]
        top = min(rel, key=lambda e: shadow_cost(e, prices_now), default=None)
        if (
            top is not None
            and top is not best
            and top.year.produced_gas_flared_gwh > FLARE_ROUTINE_GWH
        ):
            notes.append(
                f"best overall avoids routine flaring: {top.alternative.code} flares "
                f"{top.year.produced_gas_flared_gwh:.1f} GWh of the brine's gas a year (consent "
                f"under the Mijnbouwbesluit, art. 38), so {best.alternative.code}, which flares "
                f"{best.year.produced_gas_flared_gwh:.1f} GWh and is within "
                f"{FLARE_MARGIN:.0%} of it with CO2 at the long-term price, is recommended"
            )
    if optional:
        notes.append(
            f"{len(optional)} option variants of the best designs tried by the search: free "
            "cooling on the towers, own solar sized to the plant's load, the brine's gas sold "
            "instead of flared"
        )
    if brief.min_co2_saving:
        meets = [
            e
            for e in entries
            if e.alternative.role in ("chosen", "candidate")
            and (e.economics.co2_saving_vs_gas or 0.0) >= brief.min_co2_saving
        ]
        notes.append(
            f"only designs that cut CO2 against gas by at least {brief.min_co2_saving:.0%}"
            if meets
            else f"no design cuts CO2 by {brief.min_co2_saving:.0%}: the floor was dropped"
        )
    if plans:
        notes.append(
            f"{len(plans)} layouts (the {RELIABLE_TOP} cheapest, the cheapest of each doublet "
            "count and the lowest-CO2 one) also as reliable plans: "
            "the boiler and the electric chillers as equal units, grown until any one unit out "
            "(a doublet, a treatment train, the heat exchanger, the heat pump, a boiler or "
            "chiller unit, the absorption chiller) leaves every day met"
        )
        shadow = [c for c in plans + free if c.effect.startswith(SHADOW_SIZING)]
        if shadow:
            notes.append(
                f"{len(shadow)} more reliable plans from a layout's sizing that is cheapest with "
                f"CO2 at the long-term {prices.carbon_long_term_eur_per_t:g} €/t (the "
                "best-overall measure), where that is not its cheapest sizing at today's price"
            )
    drilled = {d for c in result.candidates for d in c.topology.aquifers()}
    for d in sorted(drilled):
        i = rules.aquifer_index(d)
        if i:  # an aquifer the user described: its own rock, pressure and gas
            a = rules.aquifers()[i]
            notes.append(
                f"The aquifer at {a.depth_m:,.0f} m (as given): {a.thickness_m:g} m thick, "
                f"{a.permeability_md:g} mD, {a.pressure_bar:.0f} bar, gas-liquid ratio "
                f"{a.gas_liquid_ratio:g} Nm3/m3, {rules.reservoir_temperature_c(a.depth_m):.0f} "
                "°C from the gradient; the doublets drilled into it see these"
            )
    drilled = {d for d in drilled if rules.aquifer_index(d) is None or d == rules.reservoir_depth_m}
    if any(d != rules.reservoir_depth_m for d in drilled):
        notes.append(
            f"Depths other than {rules.reservoir_depth_m:,.0f} m assume the same aquifer "
            f"({rules.permeability_md:g} mD, {rules.reservoir_thickness_m:g} m) there, with "
            f"hydrostatic pressure and the {rules.gradient_c_per_km:g} °C/km gradient"
            + (
                ": the requirements allow other depths but describe no aquifer there"
                if brief.project_id == projects.CHALLENGE
                else ""
            )
        )
    tried = {f for c in result.candidates for f in c.topology.flags}
    if tried & {"IU", "IL"}:
        notes.append(
            "Injectors open over the upper or lower half of the aquifer differ only by gravity "
            "(the cold brine sinks), which needs a reservoir simulation; this model gives them "
            "the same pressures, so it cannot rank them"
        )
    if "ST" in tried:
        notes.append(
            "A treatment train per doublet costs more for the same heat; its value shows when one "
            "is out: see the reliable plans and the one-unit-out cases"
        )
    if sweep is not None:
        notes.append(
            f"{len(sweep.points):,} more designs drawn across the space by Latin hypercube "
            f"(doublets, depth, flow cap, every unit's size, the gas mode), each run for a year "
            f"as drawn: {sweep.feasible:,} meet every cap, the rest break one (kept, on the "
            f"Compare tab's map); the {len(sweep.refined)} best feasible ones, each unit shrunk "
            "while every cap held, joined the candidates"
        )
    return Outcome(
        chosen,
        entries,
        reference,
        brief.objective,
        rules,
        notes,
        years=result.years
        + sum(len(c.rounds) for c in plans)
        + (
            len(sweep.points) + sum(int(c.sizings[0]["years"]) for c in sweep.refined)
            if sweep
            else 0
        ),
        sizings=result.sizings,
        picks=picks,
        sweep=sweep.as_dict() if sweep is not None else None,
        prices=prices,
    )


def _reliable_plans(
    cands: List[Candidate],
    demand: dp.Demand,
    model,
    rules: dp.Rules,
    prices: dp.Prices,
    excluded: Sequence[str],
    reference: Candidate,
    only: Optional[List[Candidate]] = None,
) -> List[Candidate]:
    """Return the reliable plans of the cheapest layouts and the lowest-CO2 one (stage 3).

    Each layout's plan is built on its cheapest sizing at today's prices and, when another
    sizing is cheaper with CO2 at the long-term price (``shadow_cost``, the best-overall pick's
    measure), on that one as well (``shadow_sizings``), so the best-overall pick weighs it.

    ``only``: these candidates' reliable plans instead (the gas-free ones).
    """
    valid = [c for c in cands if c.status in ("valid", "chosen")]
    base = sorted(valid, key=lambda c: c.economics.lcoe_eur_per_mwh)[:RELIABLE_TOP]
    greenest = min(valid, key=lambda c: c.economics.co2_t_per_year, default=None)
    extra = [greenest] if greenest is not None else []
    for n in (1, 2, 3):  # the cheapest of each doublet count, so "best overall" weighs them all
        same = [c for c in valid if c.plant.n_doublets == n]
        if same:
            extra.append(min(same, key=lambda c: c.economics.lcoe_eur_per_mwh))
    for c in extra:
        if c not in base:
            base.append(c)
    if only is not None:
        base = [c for c in only if c.status in ("valid", "chosen")]
    out = []
    ref = (reference.year, reference.economics)
    for c, note in shadow_sizings(base, demand, model, rules, prices, excluded, ref):
        plant, rounds, last = reliable_plan(c.plant, demand, model, rules, excluded=excluded)
        year = dp.simulate_year(plant, demand, model, rules)
        econ = dp.economics(plant, year, prices, reference=ref, rules=rules)
        held = all(o["heat"]["days_short"] == 0 and o["cool"]["days_short"] == 0 for o in last)
        was = c.plant
        change = (
            f"reliable plan: boiler {was.boiler_mw:g} -> {plant.boiler_mw:g} MW as "
            f"{plant.boiler_units} units, chillers {was.chiller_mw:g} -> {plant.chiller_mw:g} MW "
            f"as {plant.chiller_units} units"
        )
        if plant.heat_pump_mw != was.heat_pump_mw:
            change += f", heat pump {was.heat_pump_mw:g} -> {plant.heat_pump_mw:g} MW"
        if plant.absorption_mw != was.absorption_mw:
            change += f", absorption {was.absorption_mw:g} -> {plant.absorption_mw:g} MW"
        cand = Candidate(
            c.topology,
            list(c.rounds) + [Round(plant, list(year.violations), change)],
            year,
            econ,
            status="valid" if held and not year.violations else "failed",
            stage=3,
            parent=c.topology.code if not c.plant.reliable else "",
        )
        cand.parent = _plant_code(c.plant, rules.reservoir_depth_m)
        cand.sizings = list(c.sizings)  # the layout's sizings, before the backup was added
        extra = econ.capex_meur - c.economics.capex_meur
        cand.effect = note + (
            f"against {cand.parent}: {extra:+.2f} M€ of capital, "
            f"{econ.lcoe_eur_per_mwh - c.economics.lcoe_eur_per_mwh:+.2f} €/MWh, so that any one "
            "unit can be out"
        )
        if cand.status == "failed":
            short = [o["unit"] for o in last if o["heat"]["days_short"] or o["cool"]["days_short"]]
            cand.reason = (
                "no unit the brief allows covers "
                + ", ".join(short[:3])
                + " out (a boiler or chillers would)"
            )
        out.append(cand)
    return out


SHADOW_SIZING = "the sizing cheapest with CO2 at"  # how such a plan's ``effect`` begins


def shadow_sizings(
    base: Sequence[Candidate],
    demand: dp.Demand,
    model,
    rules: dp.Rules,
    prices: dp.Prices,
    excluded: Sequence[str],
    ref: Tuple[dp.YearResult, dp.Economics],
) -> Iterator[Tuple[Candidate, str]]:
    """Yield each layout to plan for, then its sizing best by the best-overall measure.

    Each candidate stands for its layout's cheapest valid sizing at today's prices. With CO2
    at the long-term price (``shadow_cost``) another of its sizings (``Candidate.sizings``,
    often a bigger heat pump) may cost less: that sizing is run again (``improve`` with its
    shares) and yielded after it, with a note for its plan's ``effect``.

    Yields
    ------
    tuple of (Candidate, str)
        The candidate to build a reliable plan on, and "" or the note saying which sizing it is.
    """
    extra = max(0.0, prices.carbon_long_term_eur_per_t - prices.carbon_eur_per_t)
    for c in base:
        yield c, ""
        mwh = (c.year.heat_delivered_gwh + c.year.cool_delivered_gwh) * 1000
        valid = [s for s in c.sizings if s.get("valid")]
        if extra <= 0 or not mwh or not valid:
            continue
        best = min(valid, key=lambda s: _shadow(s["lcoe"], s["co2_t"], mwh, extra))
        mine = c.plant
        keys = ("heat_pump_mw", "boiler_mw", "electric_boiler_mw", "absorption_mw", "chiller_mw")
        if all(abs(float(best.get(k) or 0.0) - getattr(mine, k)) < 1e-6 for k in keys):
            continue  # the cheapest sizing is also the best with CO2 at the long-term price
        if _shadow(best["lcoe"], best["co2_t"], mwh, extra) >= _shadow(
            c.economics.lcoe_eur_per_mwh, c.economics.co2_t_per_year, mwh, extra
        ):
            continue
        hp = best.get("heat_pump_share")
        ab = best.get("absorption_share")
        rounds, year = improve(
            c.topology,
            demand,
            model,
            rules,
            dp.Components(),
            excluded,
            1.0 if hp is None else float(hp),
            ABSORPTION_SHARE if ab is None else float(ab),
        )
        if year.violations:
            continue
        econ = dp.economics(rounds[-1].plant, year, prices, reference=ref, rules=rules)
        alt = Candidate(c.topology, rounds, year, econ, stage=c.stage, parent=c.parent)
        alt.sizings = list(c.sizings)
        p = alt.plant
        size = (
            f"{p.heat_pump_mw:g} MW heat pump against {mine.heat_pump_mw:g}"
            if p.heat_pump_mw != mine.heat_pump_mw
            else f"{p.absorption_mw:g} MW absorption against {mine.absorption_mw:g}"
        )
        note = (
            f"{SHADOW_SIZING} {prices.carbon_long_term_eur_per_t:g} €/t ({size}; "
            f"{econ.lcoe_eur_per_mwh - c.economics.lcoe_eur_per_mwh:+.2f} €/MWh, "
            f"{econ.co2_t_per_year - c.economics.co2_t_per_year:+,.0f} t CO2 a year before "
            "the backup); "
        )
        yield alt, note


def _shadow(lcoe: float, co2_t: float, mwh: float, extra_eur_per_t: float) -> float:
    """Return a cost per MWh with ``extra_eur_per_t`` more on each tonne of CO2."""
    return lcoe + (extra_eur_per_t * co2_t / mwh if mwh else 0.0)


GAS_FREE = ("produced", "sell")  # ``Plant.gas`` modes with no gas bought


OPTION_TOP = 4  # the cheapest designs and the cheapest reliable plans whose options are tried
# Flaring more than this a year is routine (it needs consent); the best-overall pick prefers a
# plan that flares less when one is within this share of its cost with CO2 at the long-term price.
FLARE_ROUTINE_GWH = 1.0
FLARE_MARGIN = 0.03


def _options(
    cands: List[Candidate],
    demand: dp.Demand,
    model,
    rules: dp.Rules,
    prices: dp.Prices,
    reference: Candidate,
) -> List[Tuple[Candidate, dict]]:
    """Return the option variants of the best designs: (candidate, its ``Rules`` changes).

    Free cooling where the design has towers and the district has cold; own solar at once and
    twice the plant's mean electric load (its electricity first runs the plant); the brine's gas
    sold instead of burnt and flared, where the design flares. Options the brief already set are
    not tried again. Only the ones that meet every cap are kept.
    """
    valid = [c for c in cands if c.status in ("valid", "chosen") and c.plant.n_doublets > 0]
    plain = sorted(
        (c for c in valid if not c.plant.reliable), key=lambda c: c.economics.lcoe_eur_per_mwh
    )
    plans = sorted(
        (c for c in valid if c.plant.reliable), key=lambda c: c.economics.lcoe_eur_per_mwh
    )
    ref = (reference.year, reference.economics)
    cold = any(x > 0 for x in demand.cool_mw)
    out: List[Tuple[Candidate, dict]] = []
    for c in plain[:OPTION_TOP] + plans[:OPTION_TOP]:
        tries: List[Tuple[dict, Optional[dp.Plant], str]] = []
        towers = c.plant.chiller_mw > 0 or c.plant.absorption_mw > 0
        if cold and towers and not rules.free_cooling:
            tries.append(({"free_cooling": 1.0}, None, "with free cooling on the towers"))
        load = sum(c.year.electricity_gwh.values()) * 1000 / 8760  # MW, the year's mean
        if load > 0.05 and not rules.solar_mwp:
            for f in (1.0, 2.0):
                mwp = round(load * f, 1)
                tries.append(({"solar_mwp": mwp}, None, f"with {mwp:g} MWp of own solar"))
        if not rules.storage_mwh and c.year.heat_split_gwh.get("boiler", 0.0) > 1.0:
            # A store where the boiler runs: a day-to-day tank, and a seasonal aquifer store.
            tries.append(({"storage_mwh": 2000.0}, None, "with a 2,000 MWh hot-water tank"))
            tries.append(
                (
                    {"storage_mwh": 28000.0, "storage_ates": 1.0},
                    None,
                    "with a seasonal aquifer store (HT-ATES, 28,000 MWh)",
                )
            )
        if c.plant.gas == "buy" and c.year.produced_gas_flared_gwh > 0.05:
            sold = replace(c.plant, gas="sell")
            tries.append(({}, sold, "with the brine's gas sold instead of flared"))
        for extra, plant, words in tries:
            plant = plant or c.plant
            r = replace(rules, **extra)
            year = dp.simulate_year(plant, demand, model, r)
            if year.violations:
                continue
            econ = dp.economics(plant, year, prices, reference=ref, rules=r)
            rounds = (
                list(c.rounds) if plant is c.plant else list(c.rounds) + [Round(plant, [], words)]
            )
            v = Candidate(c.topology, rounds, year, econ, status="valid", stage=c.stage)
            v.parent = _plant_code(c.plant, rules.reservoir_depth_m)
            v.sizings = list(c.sizings)
            d_cost = econ.lcoe_eur_per_mwh - c.economics.lcoe_eur_per_mwh
            d_co2 = econ.co2_t_per_year - c.economics.co2_t_per_year
            own = f"{words}, against {v.parent}: {d_cost:+.2f} €/MWh, {d_co2:+,.0f} t CO2 a year"
            # The parent's own story first (a reliable plan, the sizing best with CO2 ...).
            v.effect = f"{c.effect}; {own}" if c.effect else own
            out.append((v, extra))
    return out


def option_suffix(plant: dp.Plant, rules: dp.Rules) -> str:
    """Return the code's options: ``-FC`` free cooling, ``-PV5`` own solar (MWp), a store."""
    out = ""
    if getattr(rules, "free_cooling", 0) and (plant.chiller_mw > 0 or plant.absorption_mw > 0):
        out += "-FC"
    if getattr(rules, "solar_mwp", 0):
        out += f"-PV{rules.solar_mwp:g}"
    if getattr(rules, "storage_mwh", 0):
        out += "-ATES" if getattr(rules, "storage_ates", 0) else f"-TS{rules.storage_mwh:g}"
    return out


def _gas_free(
    cands: List[Candidate],
    demand: dp.Demand,
    model,
    rules: dp.Rules,
    prices: dp.Prices,
    excluded: Sequence[str],
    reference: Candidate,
    fixed: Optional[Dict[str, object]] = None,
) -> List[Candidate]:
    """Return gas-free designs (stage 4): no gas bought, an electric boiler for the peaks.

    For each doublet count, the cheapest heat-pump layout of the search is sized again with
    the brine's gas burnt in a small boiler (``EB``) and sold to the grid (``EB-GS``), over
    every heat pump share (the cooling as that layout had it): electricity costs more than gas,
    so a gas-free plant leans on the heat pump, not on the electric boiler. Two or three
    doublets are also sized with a treatment train each (``ST``, unless the brief fixed the
    trains): a shared train out stops every doublet, so its reliable plan must carry the whole
    peak on the electric boiler; with a train each, one out stops one doublet.
    """
    if "electric_boiler" in excluded:
        return []
    # With the gas boiler ruled out the brine's gas cannot be burnt (and may not be flared):
    # it is sold.
    modes = ("sell",) if "boiler" in excluded else GAS_FREE
    valid = [c for c in cands if c.status in ("valid", "chosen") and c.plant.gas == "buy"]
    pool = [c for c in cands if c.status != "same" and c.plant.gas == "buy"]
    heat, cool = demand.arrays()
    peak_cool = float(cool.max()) or 1.0
    out: List[Candidate] = []
    ref = (reference.year, reference.economics)
    for n in (1, 2, 3):
        same = [c for c in valid if c.plant.n_doublets == n and c.topology.topup == "heat_pump"]
        if not same:
            # None met every cap (the gas boiler ruled out leaves the peak to the heat pump):
            # the closest layout is sized again with an electric boiler, which may close it.
            same = [c for c in pool if c.plant.n_doublets == n and c.topology.topup == "heat_pump"]
            if not same:
                continue
            parent = min(same, key=lambda c: sum(c.year.peak_shortfall_mw.values()))
        else:
            parent = min(same, key=lambda c: c.economics.lcoe_eur_per_mwh)
        ab_share = parent.plant.absorption_mw / peak_cool
        for mode, trains in gas_free_layouts(parent.topology, modes, fixed):
            top = replace(parent.topology, gas=mode, trains=trains)
            best: Optional[Candidate] = None
            tried = []
            for share in HEAT_PUMP_SHARES:
                rounds, year = improve(
                    top, demand, model, rules, dp.Components(), excluded, share, ab_share
                )
                econ = dp.economics(rounds[-1].plant, year, prices, reference=ref, rules=rules)
                cand = Candidate(top, rounds, year, econ)
                tried.append(
                    {
                        "heat_pump_share": share,
                        "absorption_share": ab_share if top.cooling == "absorption" else None,
                        "heat_pump_mw": cand.plant.heat_pump_mw,
                        "boiler_mw": cand.plant.boiler_mw,
                        "electric_boiler_mw": cand.plant.electric_boiler_mw,
                        "absorption_mw": cand.plant.absorption_mw,
                        "chiller_mw": cand.plant.chiller_mw,
                        "lcoe": econ.lcoe_eur_per_mwh,
                        "co2_t": econ.co2_t_per_year,
                        "valid": not year.violations,
                        "years": len(rounds),
                    }
                )
                if best is None or (
                    (not year.violations, -econ.lcoe_eur_per_mwh)
                    > (not best.year.violations, -best.economics.lcoe_eur_per_mwh)
                ):
                    best = cand
            assert best is not None
            best.sizings, best.stage = tried, 4
            best.parent = parent.topology.code
            best.status = "failed" if best.year.violations else "valid"
            if best.year.violations:
                best.reason = best.year.violations[0]
            extra = best.economics.lcoe_eur_per_mwh - parent.economics.lcoe_eur_per_mwh
            best.effect = (
                f"against {parent.topology.code}: {extra:+.2f} €/MWh, "
                f"{best.economics.co2_t_per_year - parent.economics.co2_t_per_year:+,.0f} t CO2 "
                "a year, with no gas bought"
                + (
                    " and a treatment train per doublet"
                    if top.trains != parent.topology.trains
                    else ""
                )
            )
            out.append(best)
    return out


def gas_free_layouts(
    top: Topology, modes: Sequence[str], fixed: Optional[Dict[str, object]] = None
) -> List[Tuple[str, str]]:
    """Return the (gas mode, trains) pairs the gas-free stage sizes a layout with.

    Each mode with the layout's own trains; with two or more doublets sharing one train, each
    mode again with a train per doublet, unless the brief fixed the trains or described the
    doublets one by one.
    """
    out = [(m, top.trains) for m in modes]
    if (
        top.n_doublets > 1
        and top.trains == "shared"
        and not top.specs
        and not (fixed or {}).get("trains")
    ):
        out += [(m, "separate") for m in modes]
    return out


def shadow_cost(e: LedgerEntry, prices: dp.Prices) -> float:
    """Return the cost of heat and cold with CO2 at the long-term price, €/MWh."""
    mwh = (e.year.heat_delivered_gwh + e.year.cool_delivered_gwh) * 1000
    # CO2 at the long-term price, or at the user's own when that is higher (never less weight).
    extra = max(0.0, prices.carbon_long_term_eur_per_t - prices.carbon_eur_per_t)
    return _shadow(e.economics.lcoe_eur_per_mwh, e.economics.co2_t_per_year, mwh, extra)


def pick(
    entries: Sequence[LedgerEntry], prices: dp.Prices, min_co2_saving: Optional[float] = None
) -> Dict[str, str]:
    """Return the picks among the valid designs: objective -> code (``PICKS``).

    With ``min_co2_saving`` only designs that cut CO2 against gas at least that much count
    (when none do, the floor is dropped and the reply says so: ``Outcome.notes``).
    """
    return {k: e.alternative.code for k, e in pick_entries(entries, prices, min_co2_saving).items()}


def pick_entries(
    entries: Sequence[LedgerEntry], prices: dp.Prices, min_co2_saving: Optional[float] = None
) -> Dict[str, LedgerEntry]:
    """Return the picks among the valid designs: objective -> the design (see ``pick``)."""
    valid = [e for e in entries if e.alternative.role in ("chosen", "candidate")]
    if min_co2_saving:
        floor = [e for e in valid if (e.economics.co2_saving_vs_gas or 0.0) >= min_co2_saving]
        valid = floor or valid
    plain = [e for e in valid if not e.alternative.reliable]
    plans = [e for e in valid if e.alternative.reliable]
    out: Dict[str, LedgerEntry] = {}
    if plain:
        out["cost"] = min(plain, key=lambda e: e.economics.lcoe_eur_per_mwh)
        least = min(e.economics.co2_t_per_year for e in plain)
        near = [e for e in plain if e.economics.co2_t_per_year <= least * (1 + CO2_BAND)]
        out["co2"] = min(near, key=lambda e: e.economics.lcoe_eur_per_mwh)
    if plans:
        out["reliable"] = min(plans, key=lambda e: e.economics.lcoe_eur_per_mwh)
        out["best"] = min(plans, key=lambda e: shadow_cost(e, prices))
        if out["best"].year.produced_gas_flared_gwh > FLARE_ROUTINE_GWH:
            # Routine flaring needs consent (Mijnbouwbesluit art. 38): a plan that flares less,
            # within FLARE_MARGIN on the same measure, is the better recommendation (3 Nov).
            top = shadow_cost(out["best"], prices)
            calm = [
                e
                for e in plans
                if e.year.produced_gas_flared_gwh <= FLARE_ROUTINE_GWH
                and shadow_cost(e, prices) <= top * (1 + FLARE_MARGIN)
            ]
            if calm:
                out["best"] = min(calm, key=lambda e: shadow_cost(e, prices))
        least = min(e.economics.co2_t_per_year for e in plans)
        near = [e for e in plans if e.economics.co2_t_per_year <= least * (1 + CO2_BAND)]
        out["green_reliable"] = min(near, key=lambda e: e.economics.lcoe_eur_per_mwh)
    elif "cost" in out:  # no reliable plan holds: the best is the cheapest
        out["best"] = out["cost"]
    # Gas-free: the cheapest design that buys no gas, a reliable plan when one holds.
    free = [e for e in valid if e.alternative.gas != "buy"]
    if free:
        held = [e for e in free if e.alternative.reliable] or free
        out["gas_free"] = min(held, key=lambda e: e.economics.lcoe_eur_per_mwh)
    return out


def flaring_passed_over(
    entries: Sequence[LedgerEntry],
    best: Optional[LedgerEntry],
    prices: dp.Prices,
    min_co2_saving: Optional[float] = None,
) -> Optional[LedgerEntry]:
    """Return the reliable plan the flaring rule passed over for best overall, or None.

    ``pick_entries`` takes the reliable plan cheapest with CO2 at the long-term price, unless it
    flares more than ``FLARE_ROUTINE_GWH`` of the brine's gas a year and a plan that flares
    less is within ``FLARE_MARGIN`` of it on that measure: then that one. This returns the
    plan set aside when that happened (``best`` is the pick made).
    """
    if best is None or not best.alternative.reliable:
        return None
    valid = [e for e in entries if e.alternative.role in ("chosen", "candidate")]
    if min_co2_saving:
        floor = [e for e in valid if (e.economics.co2_saving_vs_gas or 0.0) >= min_co2_saving]
        valid = floor or valid
    plans = [e for e in valid if e.alternative.reliable]
    if not plans:
        return None
    top = min(plans, key=lambda e: shadow_cost(e, prices))
    if top is best or top.year.produced_gas_flared_gwh <= FLARE_ROUTINE_GWH:
        return None
    return top


def lost_reason(e: LedgerEntry, chosen: LedgerEntry, objective: str, prices: dp.Prices) -> str:
    """Say in numbers why a valid design is not the one chosen, under the objective."""
    a, b = e.economics, chosen.economics
    gap = a.lcoe_eur_per_mwh - b.lcoe_eur_per_mwh
    cost = f"{gap:+.1f} €/MWh of heat and cold ({a.lcoe_eur_per_mwh:.1f} against " + (
        f"{b.lcoe_eur_per_mwh:.1f})"
    )
    if objective == "co2":
        if a.co2_t_per_year < b.co2_t_per_year:
            return (
                f"{b.co2_t_per_year - a.co2_t_per_year:,.0f} t CO2 a year less, for "
                f"{gap:+.1f} €/MWh: within {CO2_BAND:.0%} of the lowest, the cheaper one is picked"
            )
        return f"{a.co2_t_per_year:,.0f} t CO2 a year against {b.co2_t_per_year:,.0f} t"
    if (
        objective in ("best", "reliable", "green_reliable")
        and not e.alternative.reliable
        and chosen.alternative.reliable
    ):
        worst = worst_outage(e)
        return f"not sized for one unit out{worst}; {cost}"
    if objective == "best":
        sa, sb = shadow_cost(e, prices), shadow_cost(chosen, prices)
        return (
            f"{sa - sb:+.1f} €/MWh with CO2 at {prices.carbon_long_term_eur_per_t:g} €/t "
            f"({sa:.1f} against {sb:.1f}); at today's {prices.carbon_eur_per_t:g} €/t {gap:+.1f}"
        )
    if abs(gap) < 0.05:
        return f"the same cost per MWh, but {a.capex_meur - b.capex_meur:+.1f} M€ of capital"
    return cost


def worst_outage(e: LedgerEntry) -> str:
    """Return ": doublet 1 out leaves heat 7.2 MW short" for the worst one-unit-out case."""
    cases = (e.firm or {}).get("outages") or []
    worst = max(cases, key=lambda o: o["heat"]["worst_mw"] + o["cool"]["worst_mw"], default=None)
    if not worst or worst["heat"]["worst_mw"] + worst["cool"]["worst_mw"] <= 0:
        return ""
    side = "heat" if worst["heat"]["worst_mw"] >= worst["cool"]["worst_mw"] else "cool"
    words = "heat" if side == "heat" else "cold"
    return f": {worst['unit']} out leaves {words} {worst[side]['worst_mw']:.1f} MW short"


def fixed_options(brief: DesignBrief, rules: dp.Rules) -> Dict[str, object]:
    """Return how the doublets are built where the brief says so (for ``dioscuri_plant.search``)."""
    fixed: Dict[str, object] = {}
    for key in ("injectors", "trains", "dispatch", "producer_open", "injector_open"):
        value = getattr(brief, key, None)
        if value:
            fixed[key] = value
    if brief.doublets:
        fixed["specs"] = tuple(
            dp.Doublet(
                depth_m=d.depth_m or rules.reservoir_depth_m,
                producer_open=d.producer_open,
                injector_open=d.injector_open,
                injectors=d.injectors,
                max_flow_m3h=d.max_flow_m3h,
                min_flow_m3h=d.min_flow_m3h,
                train=d.train if d.train is not None else 0,
            )
            for d in brief.doublets
        )
    return fixed


def doublet_rows(plant: dp.Plant, rules: dp.Rules) -> List[Dict[str, object]]:
    """Return each doublet's set-up as a ledger alternative keeps it."""
    return [
        {
            "depth_m": d.depth_m,
            "producer_open": d.producer_open,
            "injector_open": d.injector_open,
            "injectors": d.injectors,
            "max_flow_m3h": d.cap_m3h(rules),
            "min_flow_m3h": d.min_flow_m3h,
            "train": d.train,
        }
        for d in plant.specs()
    ]


def plant_of(alt: Alternative) -> dp.Plant:
    """Return the plant model's design for a ledger alternative."""
    s = alt.sizes_mw
    n = alt.n_doublets if alt.depth_m > 0 else 0
    specs = tuple(
        dp.Doublet(
            depth_m=float(d.get("depth_m") or alt.depth_m or 2500.0),
            producer_open=str(d.get("producer_open") or "full"),
            injector_open=str(d.get("injector_open") or "full"),
            injectors=int(d.get("injectors") or 1),
            max_flow_m3h=d.get("max_flow_m3h"),
            min_flow_m3h=d.get("min_flow_m3h"),
            train=int(d.get("train") or 0),
        )
        for d in alt.doublets
    )
    return dp.Plant(
        n,
        depth_m=alt.depth_m or 2500.0,
        heat_pump_mw=s.get("heat_pump", 0.0),
        boiler_mw=s.get("boiler", 0.0),
        absorption_mw=s.get("absorption", 0.0),
        chiller_mw=s.get("chillers", 0.0),
        name=alt.name,
        doublet_specs=specs if n and len(specs) == n else (),
        dispatch=alt.dispatch if n > 1 else "equal",
        boiler_units=alt.boiler_units,
        chiller_units=alt.chiller_units,
        reliable=alt.reliable,
        electric_boiler_mw=s.get("electric_boiler", 0.0),
        electric_boiler_units=alt.electric_boiler_units,
        gas=alt.gas,
    )


def evaluate(
    alt: Alternative,
    brief: DesignBrief,
    assumptions: Optional[dict] = None,
    role: Optional[str] = None,
    scale: tuple = (1.0, 1.0),
    overrides: Optional[dict] = None,
    with_firm: bool = True,
) -> LedgerEntry:
    """Run one design (fixed sizes) for a brief: what-ifs, user designs, sensitivity.

    Parameters
    ----------
    alt : Alternative
        The design, with its sizes.
    brief : DesignBrief
        The conditions (a colder reservoir, other network temperatures ...).
    assumptions : dict, optional
        Prices and costs.
    role : str, optional
        The entry's role (``what_if``, ``user`` ...); the design's own by default.
    scale : tuple of float
        Heat and cold demand multipliers (sensitivity).
    overrides : dict, optional
        ``dioscuri_plant.Rules`` fields to change (permeability, operating days ...).

    Returns
    -------
    LedgerEntry
        The design's year, costs and checks under these conditions.
    """
    rules, prices = rules_for(brief), prices_for(assumptions, brief)
    if overrides:
        rules = replace(rules, **overrides)
    scale = tuple(a * b for a, b in zip(scale, brief.demand_scale or [1.0, 1.0]))
    plant = plant_of(alt)
    doublet = doublet_model(rules)
    year = dp.simulate_year(plant, scaled_demand(tuple(scale), brief.project_id), doublet, rules)
    # The gas reference without the plant's options (free cooling, own solar, a store): the
    # same gas plant the search measured the design against (``reference_rules``).
    ref_rounds, ref_year, ref_econ = _reference_cached(
        reference_rules(rules), prices, tuple(scale), brief.project_id
    )
    econ = dp.economics(plant, year, prices, reference=(ref_year, ref_econ), rules=rules)
    top = Topology(
        plant.n_doublets,
        alt.topup or "heat_pump",
        alt.cooling or "electric",
        plant.depth_m,
        specs=plant.specs(),
        dispatch=plant.dispatch,
        known_depth_m=rules.reservoir_depth_m,
        gas=plant.gas,
    )
    cand = Candidate(top, [Round(plant, list(year.violations))], year, econ)
    cand.status = role or alt.role
    reference = Candidate(Topology(0), ref_rounds, ref_year, ref_econ, status="reference")
    entry = to_entry(cand, brief, rules, reference)
    entry.alternative = entry.alternative.model_copy(
        update={
            "code": alt.code,
            "name": alt.name,
            "role": role or alt.role,
            "sizings": alt.sizings,
            "stage": alt.stage,
            "parent": alt.parent,
            "uid": alt.uid,
            "picks": list(alt.picks) if role is None or role == alt.role else [],
            "reason": alt.reason if role is None or role == alt.role else entry.alternative.reason,
        }
    )
    if "heat_exchanger" in alt.sizes_mw:  # the design's exchanger, not this year's peak duty
        entry.alternative.sizes_mw["heat_exchanger"] = alt.sizes_mw["heat_exchanger"]
    if with_firm:  # sensitivity runs hundreds of years: firm capacity only where it is shown
        entry.firm = firm_of(plant, scaled_demand(tuple(scale), brief.project_id), rules)
    entry.year.alternative = alt.code
    entry.economics.alternative = alt.code
    entry.verification.alternative = alt.code
    return entry


def firm_of(plant: dp.Plant, demand: dp.Demand, rules: dp.Rules) -> Optional[dict]:
    """Return a design's firm capacity: the year with each unit out, the peak days' spare."""
    if plant.n_doublets == 0:
        return None
    doublet = doublet_model(rules)
    return {
        "outages": outages(plant, demand, doublet, rules),
        "peak": peak_margin(plant, demand, doublet, rules),
    }


def _firm_with(state: dict, plant: dp.Plant) -> Optional[dict]:
    return firm_of(plant, state["demand"], state["rules"])


def firm(entry: LedgerEntry) -> Optional[dict]:
    """Return an entry's firm capacity, computed once (entries saved before it have none)."""
    if entry.firm is None and entry.alternative.n_doublets:
        rules = rules_for(entry.brief)
        entry.firm = firm_of(plant_of(entry.alternative), demand_of(entry.brief), rules)
    return entry.firm


def reference(
    brief: Optional[DesignBrief] = None, assumptions: Optional[dict] = None
) -> LedgerEntry:
    """Return the gas reference, boilers and electric chillers, for these conditions.

    The brief's plant options (free cooling, own solar, a heat store: ``reference_rules``) are a
    design's, not the gas plant's: the reference leaves them out, so a design with options and
    its plain parent are measured against the same gas plant, for the CO2 saving, the money
    against gas and the investor's sale prices alike.
    """
    brief = brief or DesignBrief()
    rules, prices = reference_rules(rules_for(brief)), prices_for(assumptions, brief)
    scale = tuple(float(x) for x in (brief.demand_scale or [1.0, 1.0]))
    rounds, year, econ = _reference_cached(rules, prices, scale, brief.project_id)
    return to_entry(
        Candidate(Topology(0), rounds, year, econ, status="reference"),
        brief,
        rules,
        None,
    )


def to_entry(
    cand: Candidate, brief: DesignBrief, rules: dp.Rules, ref: Optional[Candidate]
) -> LedgerEntry:
    """Turn a candidate of the search into the agent's ledger entry."""
    top, y, e, plant = cand.topology, cand.year, cand.economics, cand.plant
    n = plant.n_doublets
    sizes = {
        "heat_exchanger": round(max(y.daily_mw["heat"]["geo"], default=0.0), 2),
        "heat_pump": plant.heat_pump_mw,
        "boiler": plant.boiler_mw,
        "absorption": plant.absorption_mw,
        "chillers": plant.chiller_mw,
    }
    if plant.electric_boiler_mw > 0:
        sizes["electric_boiler"] = plant.electric_boiler_mw
    role = cand.status if cand.status != "valid" else "candidate"
    code = plant_code(plant, rules) + option_suffix(plant, rules)
    alt = Alternative(
        code=code,
        name=plant_name(plant, rules),
        doublets=doublet_rows(plant, rules),
        dispatch=plant.dispatch if n > 1 else "equal",
        flags=(
            (plant_flags(plant) + [x for x in option_suffix(plant, rules).split("-") if x])
            if n
            else []
        ),
        stage=cand.stage,
        parent=cand.parent,
        boiler_units=plant.boiler_units,
        chiller_units=plant.chiller_units,
        electric_boiler_units=plant.electric_boiler_units,
        gas=plant.gas,
        reliable=plant.reliable,
        effect=cand.effect,
        sizings=list(cand.sizings),
        depth_m=plant.depth_m if n > 0 else 0.0,
        heat_pump=plant.heat_pump_mw > 0,
        boiler=plant.boiler_mw > 0,
        absorption=plant.absorption_mw > 0,
        chillers=plant.chiller_mw > 0,
        n_doublets=n,
        topup=top.topup if n > 0 else None,
        cooling=top.cooling,
        sizes_mw=sizes,
        role=role,
        reason=cand.reason,
        rounds=[
            {
                "sizes_mw": {
                    "heat_pump": r.plant.heat_pump_mw,
                    "boiler": r.plant.boiler_mw,
                    "electric_boiler": r.plant.electric_boiler_mw,
                    "absorption": r.plant.absorption_mw,
                    "chillers": r.plant.chiller_mw,
                },
                "violations": r.violations,
                "change": r.change,
            }
            for r in cand.rounds
        ],
    )
    hex_outlet = min(y.wellhead_c - plant.hex_approach_k, rules.heat_supply_c) if n > 0 else 0.0
    runtime = gemini_runtime.load("fixed")
    caps = sum(d.cap_m3h(rules) for d in plant.specs())
    brine_capacity = float(rules.brine_mw_per_k(caps)) * rules.max_brine_cooling_k
    year = YearResult(
        alternative=code,
        source=SOURCE_GEMINI if n > 0 else SOURCE_PLANT,
        reservoir_c=y.reservoir_c,
        wellhead_c=y.wellhead_c,
        hex_outlet_c=round(hex_outlet, 2),
        reinjection_c=y.min_reinjection_c,
        heat_demand_gwh=y.heat_demand_gwh,
        cool_demand_gwh=y.cool_demand_gwh,
        heat_delivered_gwh=y.heat_delivered_gwh,
        cool_delivered_gwh=y.cool_delivered_gwh,
        heat_coverage=y.heat_coverage,
        cool_coverage=y.cool_coverage,
        heat_split_gwh={
            k: y.heat_split_gwh.get(k, 0.0)
            for k in ("geo", "hp", "boiler", "electric_boiler")
            if k != "electric_boiler" or y.heat_split_gwh.get(k)
        },
        cool_split_gwh={
            k: y.cool_split_gwh.get(k, 0.0)
            for k in ("free", "abs", "chill")
            if k != "free" or y.cool_split_gwh.get(k)
        },
        peak_heat_mw=y.peak_heat_mw,
        peak_cool_mw=y.peak_cool_mw,
        hex_mw=sizes["heat_exchanger"],
        heat_pump_mw=plant.heat_pump_mw,
        boiler_mw=plant.boiler_mw,
        absorption_mw=plant.absorption_mw,
        chiller_mw=plant.chiller_mw,
        heat_pump_cop=y.heat_pump_cop,
        heat_pump_carnot_cop=(
            round(verifier.carnot_cop(rules.heat_supply_c, y.min_reinjection_c), 3)
            if y.heat_pump_cop
            else 0.0
        ),
        full_load_hours=y.full_load_hours,
        chiller_cop=y.chiller_cop,
        absorption_cop=y.absorption_cop,
        cooling_gain=0.0,
        heat_pump_electricity_gwh=y.electricity_gwh["hp"],
        brine_heat_gwh=round(
            y.heat_split_gwh["geo"]
            + y.heat_split_gwh["hp"]
            - y.electricity_gwh["hp"]
            + (y.cool_split_gwh["abs"] / y.absorption_cop if y.absorption_cop else 0.0),
            3,
        ),
        brine_capacity_mw=round(brine_capacity, 2),
        monthly_gwh=y.monthly_gwh,  # with "short": what was not met, month by month
        plant={
            "n_doublets": n,
            "depth_m": plant.depth_m if n > 0 else 0.0,
            "flow_max_m3h": rules.flow_max_m3h,
            "flow_mean_m3h": round(y.brine_m3 / 8760 / max(n, 1), 1) if n else 0.0,
            "stop_days": [list(s) for s in y.stop_days],
            "stop_ranges": [[list(r) for r in rows] for rows in y.stop_ranges],
            "wells": plant.wells if n else 0,
            "trains": plant.trains if n else 0,
            "dispatch": plant.dispatch if n > 1 else "equal",
            "doublets": y.doublet_summary,
            "gemini": (
                {
                    "version": runtime.version,
                    "variant": "fixed",
                    "patches": len(runtime.patches),
                }
                if n > 0
                else None
            ),
        },
        daily_mw=y.daily_mw,
        n_doublets=n,
        doublets=y.doublets,
        violations=y.violations,
        electricity_gwh=y.electricity_gwh,
        purchased_gas_gwh=y.purchased_gas_gwh,
        produced_gas_burned_gwh=y.produced_gas_burned_gwh,
        produced_gas_flared_gwh=y.produced_gas_flared_gwh,
        produced_gas_sold_gwh=y.produced_gas_sold_gwh,
        co2_t=y.co2_t,
        co2_by_unit_t=y.co2_by_unit_t or None,
        stop_days=[list(s) for s in y.stop_days],
        stop_ranges=[[list(r) for r in rows] for rows in y.stop_ranges],
        max_brine_cooling_k=y.max_brine_cooling_k,
        balance_error=y.balance_error,
        warnings=list(y.warnings),
        network=y.network,
        service=[list(w) for w in y.service],
        free_cooling_mw=y.free_cooling_mw,
        solar=y.solar,
        storage=y.storage,
        operability=y.operability,
        tower_water_m3=y.tower_water_m3,
    )
    econ = Economics(
        alternative=code,
        source=SOURCE_PLANT,
        lcoh_eur_per_mwh=e.lcoh_eur_per_mwh,
        lcoc_eur_per_mwh=e.lcoc_eur_per_mwh,
        capex_meur=e.capex_meur,
        co2_saving_vs_gas=e.co2_saving_vs_gas if e.co2_saving_vs_gas is not None else 0.0,
        lcoe_eur_per_mwh=e.lcoe_eur_per_mwh,
        lines_heat=[list(x) for x in e.lines_heat],
        lines_cold=[list(x) for x in e.lines_cold],
        capex_items=e.capex_items,
        co2_t_per_year=e.co2_t_per_year,
        opex_meur_per_year=e.opex_meur_per_year,
    )
    check = verifier.verify_plant(y, rules, code, caps=project_caps(brief))
    return LedgerEntry(alternative=alt, brief=brief, year=year, economics=econ, verification=check)


def ranked(outcome: Outcome) -> List[LedgerEntry]:
    """Return the distinct candidates, the chosen one first, then by the objective.

    Under ``best`` and ``reliable`` the reliable plans come first (by their cost, with CO2 at
    the long-term price for ``best``), then the others. Under the prices the search ran with
    (the conversation's; until 4 Nov always the defaults).
    """
    prices = outcome.prices or prices_for(None, outcome.chosen.brief if outcome.chosen else None)
    if outcome.objective == "co2":

        def key(e):
            return (e.economics.co2_t_per_year, e.alternative.reliable)

    elif outcome.objective == "best":

        def key(e):
            return (not e.alternative.reliable, shadow_cost(e, prices))

    elif outcome.objective == "reliable":

        def key(e):
            return (not e.alternative.reliable, e.economics.lcoe_eur_per_mwh)

    elif outcome.objective == "green_reliable":

        def key(e):
            return (not e.alternative.reliable, e.economics.co2_t_per_year)

    else:

        def key(e):
            return (e.economics.lcoe_eur_per_mwh, e.alternative.reliable)

    valid = [e for e in outcome.tried if e.alternative.role in ("chosen", "candidate")]
    failed = [e for e in outcome.tried if e.alternative.role == "failed"]
    return sorted(valid, key=lambda e: (e.alternative.role != "chosen", key(e))) + failed


def summary(outcome: Outcome) -> Dict[str, object]:
    """Return the numbers the reply and the trace use: how many tried, fixed, failed."""
    tried = outcome.tried
    return {
        "candidates": len(tried),
        "valid": sum(e.alternative.role in ("chosen", "candidate") for e in tried),
        "failed": sum(e.alternative.role == "failed" for e in tried),
        "improved": sum(len(e.alternative.rounds) > 1 for e in tried),
        "rounds": sum(len(e.alternative.rounds) for e in tried),
        "depths": sorted({e.alternative.depth_m for e in tried}),
        "objective": outcome.objective,
        "layouts": len(outcome.candidates),
        "variants": sum(e.alternative.stage == 2 for e in outcome.candidates),
        "sizings": outcome.sizings,
        "years": outcome.years,
    }


def lowest_co2(outcome: Outcome) -> Optional[LedgerEntry]:
    """Return the valid candidate with the least CO2 (to set against the cheapest)."""
    valid = [e for e in outcome.tried if e.alternative.role in ("chosen", "candidate")]
    key = lambda e: (e.economics.co2_t_per_year, e.alternative.reliable)  # noqa: E731
    return min(valid, key=key) if valid else None


def picked(outcome: Outcome, objective: str) -> Optional[LedgerEntry]:
    """Return the design a pick names (``PICKS``), or None.

    The design tagged with the pick (``Alternative.picks``) first: two sizings of one layout
    share a code.
    """
    tagged = next((e for e in outcome.tried if objective in e.alternative.picks), None)
    if tagged is not None:
        return tagged
    code = outcome.picks.get(objective)
    return next((e for e in outcome.tried if e.alternative.code == code), None)


def excluded_names(brief: DesignBrief) -> Sequence[str]:
    """Return the user's exclusions in words."""
    return [
        {
            "heat_pump": "heat pumps",
            "boiler": "gas boilers",
            "chiller": "chillers",
            "electric_boiler": "electric boilers",
        }[x]
        for x in brief.excluded
    ]


OBJECTIVE_WORDS = {
    "best": "best overall (a reliable plan, cheapest with CO2 at the long-term price of 137 €/t, "
    "PBL)",
    "cost": "lowest cost of heat and cold",
    "co2": "lowest CO2 (the cheapest within 2 % of the lowest)",
    "reliable": "cheapest reliable (the cheapest plan in which any one unit can be out)",
    "green_reliable": "greenest reliable (any one unit can be out; the least CO2 of those, the "
    "cheapest within 2 %)",
    "gas_free": "gas-free (no gas bought: heat pumps and an electric boiler; the cheapest such "
    "reliable plan)",
}


def space(brief: DesignBrief) -> Dict[str, object]:
    """Return the layouts a brief allows: doublets, depths, how they are built, top-ups, cooling."""
    from dioscuri_plant.search import STAGE_TWO, sizings, topologies

    rules = rules_for(brief)
    excluded = list(brief.excluded)
    doublets = (
        (len(brief.doublets),)
        if brief.doublets
        else ((brief.n_doublets,) if brief.n_doublets else (1, 2, 3))
    )
    depths = aquifers.search_depths(brief, rules)
    fixed = fixed_options(brief, rules)
    tops = topologies(excluded, doublets, depths, rules.reservoir_depth_m, fixed)
    count = len(tops)
    n_sizings = sum(len(sizings(t, excluded)) for t in tops)
    where = aquifers.where_words(brief, rules)
    parts = [
        f"{'/'.join(str(n) for n in doublets)} doublet(s) {where}",
        "heat pump or boiler top-up" if "heat_pump" not in excluded else "boiler top-up",
        "absorption or electric cooling",
    ]
    if any(n > 1 for n in doublets) and not fixed.get("dispatch"):
        parts.append("two or more doublets sharing the brine equally or hottest first")
    built = built_words(brief)
    if built:
        parts.append(built)
    reason = (
        "Every layout the brief allows: "
        + ", ".join(parts)
        + f"; each sized several ways ({n_sizings} sizings in all)"
    )
    if not brief.doublets:
        reason += (
            f", then variants of the best {STAGE_TWO}: two injectors per doublet, a treatment "
            "train per doublet, wells open over half the aquifer"
        )
    reason += "."
    if excluded:
        reason += " Ruled out by you: " + ", ".join(excluded_names(brief)) + "."
    return {
        "doublets": list(doublets),
        "depths": list(depths),
        "excluded": excluded,
        "count": count,
        "sizings": n_sizings,
        "stage_two": STAGE_TWO if not brief.doublets else 0,
        "reason": reason,
    }


def built_words(brief: DesignBrief) -> str:
    """Return how the brief fixes the doublets' build, in words ("" when it does not)."""
    parts = []
    if brief.doublets:
        for i, d in enumerate(brief.doublets, 1):
            bits = [f"doublet {i}"]
            if d.depth_m:
                bits.append(f"at {d.depth_m:,.0f} m")
            if d.injectors == 2:
                bits.append("two injectors")
            if d.producer_open != "full":
                bits.append(f"producer open over the {d.producer_open} half")
            if d.injector_open != "full":
                bits.append(f"injector open over the {d.injector_open} half")
            if d.min_flow_m3h and d.max_flow_m3h and d.min_flow_m3h >= d.max_flow_m3h:
                bits.append(f"fixed at {d.max_flow_m3h:g} m3/h")
            else:
                if d.min_flow_m3h:
                    bits.append(f"at least {d.min_flow_m3h:g} m3/h")
                if d.max_flow_m3h:
                    bits.append(f"at most {d.max_flow_m3h:g} m3/h")
            if d.train is not None:
                bits.append(f"treatment train {d.train + 1}")
            parts.append(" ".join(bits))
    if brief.injectors == 2:
        parts.append("two injectors per doublet")
    if brief.trains == "separate":
        parts.append("a treatment train per doublet")
    elif brief.trains == "shared":
        parts.append("one shared treatment train")
    if brief.dispatch == "base":
        parts.append("the hottest doublet first")
    elif brief.dispatch == "equal":
        parts.append("equal shares of brine")
    if brief.producer_open and brief.producer_open != "full":
        parts.append(f"producers open over the {brief.producer_open} half")
    if brief.injector_open and brief.injector_open != "full":
        parts.append(f"injectors open over the {brief.injector_open} half")
    return ", ".join(parts)


SEARCH_KEYS = (
    "project_id",
    "n_doublets",
    "doublet_depths_m",
    "excluded",
    "objective",
    "heating",
    "cooling",
    "reservoir_delta_c",
    "reservoir_temp_c",
    "annual_heat_gwh",
    "annual_cool_gwh",
    "rules",
    "prices",
    "demand_scale",
    "injectors",
    "trains",
    "dispatch",
    "producer_open",
    "injector_open",
    "doublets",
)


def same_search(last_brief: dict, brief: DesignBrief) -> bool:
    """Return True when a brief asks for the search that was run last (same inputs)."""
    now = brief.model_dump()
    for key in SEARCH_KEYS + ("aquifers",):
        a, b = last_brief.get(key), now.get(key)
        if key == "aquifers":  # records, in their order
            if list(a or []) != list(b or []):
                return False
        elif isinstance(a, list) or isinstance(b, list):
            if sorted(a or []) != sorted(b or []):
                return False
        elif a != b:
            return False
    return True


def brief_label(brief: DesignBrief) -> str:
    """Return a brief in a few words, for the Compare tab's list of attempts.

    For example ``"lowest cost · 1–3 doublets · 2,500, 3,000 and 3,500 m"`` or
    ``"lowest CO2 · 1 doublet · no boilers"``.
    """
    parts = [OBJECTIVE_WORDS.get(brief.objective, brief.objective).replace(" of heat and cold", "")]
    parts.append(
        f"{brief.n_doublets} doublet{'s' if brief.n_doublets != 1 else ''}"
        if brief.n_doublets
        else "1–3 doublets"
    )
    depths = list(aquifers.search_depths(brief))
    shown = [f"{d:,.0f}" for d in depths]
    parts.append(
        (", ".join(shown[:-1]) + " and " + shown[-1] if len(shown) > 1 else shown[0]) + " m"
    )
    built = built_words(brief)
    if built:
        parts.append(built)
    if brief.excluded:
        parts.append("no " + ", ".join(excluded_names(brief)))
    if brief.reservoir_delta_c:
        parts.append(f"reservoir {brief.reservoir_delta_c:+g} °C")
    return " · ".join(parts)


def doublet_summary(depth_m: float, rules: dp.Rules) -> Dict[str, float]:
    """Return the doublet at full flow from GEMINI's well solve, for the trace."""
    d = doublet_model(rules)(rules.flow_max_m3h, depth_m)
    return {
        "depth_m": depth_m,
        "flow_m3h": rules.flow_max_m3h,
        "wellhead_c": round(d["wellhead_c"], 1),
        "esp_head_bar": round(d["esp_head_bar"], 1),
        "esp_mw": round(d["esp_mw"], 3),
        "injection_wellhead_bar": round(d["injection_wellhead_bar"], 1),
        "injector_pump_mw": round(d["injector_pump_mw"], 3),
        "pi_m3h_per_bar": round(d["pi_m3h_per_bar"], 2),
        "source": "gemini",
    }


def relaxations(brief: DesignBrief) -> List[tuple]:
    """Return the briefs that lift one of the user's limits, each with a label."""
    out = []
    names = {
        "heat_pump": "Allow heat pumps",
        "boiler": "Allow a boiler",
        "chiller": "Allow electric chillers",
    }
    for unit in brief.excluded:
        relaxed = brief.model_copy(update={"excluded": [x for x in brief.excluded if x != unit]})
        out.append((names[unit], relaxed))
    if brief.n_doublets and brief.n_doublets < 3:
        out.append(("Allow up to 3 doublets", brief.model_copy(update={"n_doublets": None})))
    rules = rules_for(brief)
    if (
        not brief.doublet_depths_m
        and not brief.aquifers
        and max(projects.depths(rules, brief.project_id)) <= rules.reservoir_depth_m
    ):
        deeper = list(projects.assumed_depths(rules))
        shown = " or ".join(f"{d:,.0f} m" for d in deeper[1:])
        out.append(
            (
                f"Allow wells into an assumed deeper aquifer ({shown})",
                brief.model_copy(update={"doublet_depths_m": deeper}),
            )
        )
    if len(out) > 1:
        out.append(
            ("Lift all these limits", brief.model_copy(update={"excluded": [], "n_doublets": None}))
        )
    return out


def reprice(entry: LedgerEntry, assumptions: Optional[dict] = None, **kw) -> LedgerEntry:
    """Return the entry run again under these prices (and any ``evaluate`` options)."""
    return evaluate(entry.alternative, entry.brief, assumptions, role=entry.alternative.role, **kw)


@lru_cache(maxsize=64)
def _reference_cached(rules: dp.Rules, prices: dp.Prices, scale: tuple, project_id: str):
    d = scaled_demand(scale, project_id)
    rounds, year = improve(Topology(0), d, doublet_model(rules), rules)
    return rounds, year, dp.economics(rounds[-1].plant, year, prices, rules=rules)


@lru_cache(maxsize=16)
def scaled_demand(scale: tuple = (1.0, 1.0), project_id: str = projects.CHALLENGE) -> dp.Demand:
    """Return a project's demand with heat and cold scaled (sensitivity)."""
    base = demand(project_id)
    if scale == (1.0, 1.0):
        return base
    h, c = scale
    return dp.Demand(
        tuple(x * h for x in base.heat_mw), tuple(x * c for x in base.cool_mw), base.dates
    )


def versus_reference(
    entry: LedgerEntry, ref: LedgerEntry, prices: dp.Prices, years: int = 30
) -> dict:
    """Return the design against the gas reference: extra capital, yearly saving, NPV, payback.

    Both plants' capital as a cash flow (``investor.capital_flows``, as the investor's case
    does): each unit bought at year 0 and again each time it wears out within ``years``, and
    what the last ones are still worth at the end counted back. With the running costs a year
    saved, that gives the NPV, the discounted payback and the IRR against gas. Units of 20 or
    25 years are bought twice on either side; buying a dear electric boiler again in year 20
    can take nearly a third off a gas-free design's NPV.

    Returns
    -------
    dict
        ``extra_capex_meur`` (at year 0), ``savings_meur_per_year``, ``reinvest_meur`` (the
        design's re-buys less the reference's, 2025 euros, not discounted),
        ``value_left_meur`` (the same for what is left at the end), ``payback_years``
        (discounted, the first year the cumulative flow reaches zero), ``simple_payback_years``
        (extra capital over the saving), ``npv_meur``, ``irr`` (real), ``cash_flow_meur``
        (cumulative, discounted, years 0 to ``years``) and ``years``.
    """
    e, r = entry.economics, ref.economics
    rate = prices.discount_rate
    spend, left, _ = capital_flows(e.capex_items or [], years, rate)
    ref_spend, ref_left, _ = capital_flows(r.capex_items or [], years, rate)
    savings = (r.opex_meur_per_year or 0.0) - (e.opex_meur_per_year or 0.0)
    flows = [
        ref_spend[t]
        - spend[t]
        + (savings if t > 0 else 0.0)
        + (left - ref_left if t == years else 0.0)
        for t in range(years + 1)
    ]
    extra = spend[0] - ref_spend[0]
    total, cumulative, payback = 0.0, [], None
    for t, f in enumerate(flows):
        total += f / (1 + rate) ** t
        cumulative.append(round(total, 3))
        if payback is None and t > 0 and total >= 0:
            payback = t
    simple = extra / savings if savings > 0 else None
    return {
        "extra_capex_meur": round(extra, 2),
        "savings_meur_per_year": round(savings, 3),
        "reinvest_meur": round(sum(spend[1:]) - sum(ref_spend[1:]), 2),
        "value_left_meur": round(left - ref_left, 2),
        "payback_years": payback,  # discounted
        "simple_payback_years": round(simple, 1) if simple is not None else None,
        "npv_meur": round(total, 2),
        "irr": irr(flows),
        "cash_flow_meur": cumulative,
        "years": years,
    }


def irr(flows: Sequence[float]) -> Optional[float]:
    """Return the real internal rate of return of a cash flow against gas (year 0 first, M€).

    None when it costs nothing extra up front (``flows[0] >= 0``) or never pays back (no
    positive rate makes the NPV zero).
    """
    if not flows or flows[0] >= 0:
        return None

    def npv(rate: float) -> float:
        return sum(f / (1 + rate) ** t for t, f in enumerate(flows))

    if npv(0.0) <= 0:
        return None
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if npv(mid) > 0 else (lo, mid)
    return round(lo, 4)


def against_gas(entry: LedgerEntry, ref: LedgerEntry) -> Dict[str, Optional[float]]:
    """Return a design's costs against the gas reference's, as fractions (-0.18: 18 % cheaper)."""
    e, r = entry.economics, ref.economics

    def rel(a, b):
        return round(a / b - 1, 4) if a is not None and b else None

    return {
        "heat": rel(e.lcoh_eur_per_mwh, r.lcoh_eur_per_mwh),
        "cold": rel(e.lcoc_eur_per_mwh, r.lcoc_eur_per_mwh),
        "total": rel(e.lcoe_eur_per_mwh, r.lcoe_eur_per_mwh),
    }


def bug_impact(entry: LedgerEntry) -> List[dict]:
    """Return what GEMINI as released gives for this design's doublet, next to the fixed one.

    Rows: ESP head and power, injection pressure and pump at full flow (300 m3/h), and the
    heat pump's COP at the design's own operating point.
    """
    from gemini_agent.tools.gemini import doublet_point, heat_pump_point

    rows: List[dict] = []
    alt = entry.alternative
    if alt.depth_m <= 0:
        return rows
    rules = rules_for(entry.brief)
    fixed = doublet_point(rules.flow_max_m3h, alt.depth_m, rules, "fixed")
    released = doublet_point(rules.flow_max_m3h, alt.depth_m, rules, "asis")
    for key, label, unit, bugs in (
        (
            "esp_head_bar",
            "ESP head at 300 m3/h",
            "bar",
            "water instead of brine (11), 10 mm roughness (F10)",
        ),
        ("esp_mw", "ESP electricity", "MW", "the same"),
        (
            "injection_wellhead_bar",
            "Injection pressure",
            "bar",
            "friction sign (F3), roughness (F10)",
        ),
        ("injector_pump_mw", "Injection pump electricity", "MW", "the same"),
    ):
        rows.append(
            {
                "quantity": label,
                "unit": unit,
                "released": round(released[key], 3),
                "fixed": round(fixed[key], 3),
                "bugs": bugs,
            }
        )
    if alt.sizes_mw.get("heat_pump"):
        y = entry.year
        args = dict(
            source_in_c=rules.heat_return_c + dp.Plant(1).hex_approach_k,  # brine after the HEX
            source_flow_m3h=rules.flow_max_m3h * alt.n_doublets,
            sink_in_c=y.hex_outlet_c,
            sink_out_c=rules.heat_supply_c,
            heat_mw=alt.sizes_mw["heat_pump"],
        )
        hp_fixed = heat_pump_point(**args, variant="fixed")
        hp_released = heat_pump_point(**args, variant="asis")
        for key, label, unit, bugs in (
            ("cop", "Heat pump COP", "", "spurious root (F2); Carnot at the source outlet (10)"),
            ("source_out_c", "Brine after the heat pump", "°C", "spurious root (F2)"),
            ("co2_kg_h", "Heat pump CO₂", "kg/h", "electricity not counted (08)"),
        ):
            rows.append(
                {
                    "quantity": label,
                    "unit": unit,
                    "released": hp_released.get(key),
                    "fixed": hp_fixed.get(key),
                    "bugs": bugs,
                }
            )
    return rows


def reservoir_pressure(depth_m: float, rules: dp.Rules) -> float:
    """Return the reservoir pressure (bar): the requirements' value at 2,500 m, else hydrostatic."""
    from dioscuri_plant.doublet import reservoir_pressure_bar

    return reservoir_pressure_bar(depth_m or rules.reservoir_depth_m, rules)


def demand_summary(project_id: str = projects.CHALLENGE) -> Dict[str, object]:
    """Return the year's demand and its peaks from a project's files (the organisers')."""
    d = demand(project_id)
    heat, cool = d.arrays()
    files = [f for f in projects.registry().get(project_id).files if f.lower().endswith(".csv")]
    return {
        "source": ", ".join(files),
        "annual_heat_gwh": round(float(heat.sum()) * 24 / 1000, 2),
        "annual_cool_gwh": round(float(cool.sum()) * 24 / 1000, 2),
        "peak_heat_mw": round(float(heat.max()), 2),
        "peak_cool_mw": round(float(cool.max()), 2),
        "peak_heat_day": d.dates[int(heat.argmax())],
        "peak_cool_day": d.dates[int(cool.argmax())],
    }


def plant_name(plant: dp.Plant, rules: Optional[dp.Rules] = None) -> str:
    """Return a design in words from what it has (not from what its candidate aimed at)."""
    if plant.n_doublets == 0:
        return "Gas boilers and electric chillers (reference)"
    rules = rules or dp.Rules()
    n = plant.n_doublets
    depths = sorted({d.depth_m for d in plant.specs()})
    parts = [f"{n} doublet{'s' if n > 1 else ''} at " + " and ".join(f"{d:,.0f} m" for d in depths)]
    # Deep enough, the exchanger alone reaches the supply: a boiler is then only a backup.
    hot = rules.reservoir_temperature_c(max(depths)) - 1 - plant.hex_approach_k
    direct = hot >= rules.heat_supply_c
    if plant.heat_pump_mw > 0:
        # The boiler takes the peaks and the days the doublets stop: a gas boiler, not a backup
        # (on the challenge it makes about half the heat); a reliable plan's comes as units.
        boiler = (
            f" and a gas boiler ({plant.boiler_units} units)"
            if plant.boiler_units > 1
            else " and a gas boiler"
        )
        parts.append("heat pump top-up" + (boiler if plant.boiler_mw > 0 else ""))
    elif plant.boiler_mw > 0:
        parts.append(
            f"backup boiler (the brine reaches {rules.heat_supply_c:g} °C)"
            if direct
            else "gas boiler top-up"
        )
    else:
        parts.append("no top-up (the brine is hot enough)")
    if plant.absorption_mw > 0 and plant.chiller_mw > 0:
        parts.append("absorption and electric chillers")
    elif plant.absorption_mw > 0:
        parts.append("absorption chillers")
    elif plant.chiller_mw > 0:
        parts.append("electric chillers")
    for flag in plant_flags(plant):
        parts.append(flag_words(flag))
    return ", ".join(parts)


def plant_code(plant: dp.Plant, rules: Optional[dp.Rules] = None) -> str:
    """Return a short code from what a design has: ``2D-HP-EC``, ``1D-BO-EC@3000-2I`` ...

    HP: heat pump top-up, BO: boiler only, DH: no top-up; AB: absorption (with or without
    electric chillers), EC: electric chillers only, NC: no cooling (a district without any).
    ``@`` names the aquifer when it is not the known one; the flags are the variants
    (``dioscuri_plant.search.FLAGS``, ``flag_words``).
    """
    known = (rules or projects.registry().rules(projects.CHALLENGE)).reservoir_depth_m
    return _plant_code(plant, known)


AGREE_PCT = 5.0  # GEMINI and the plant model agree within 5 % (1 K for temperatures)


def gemini_check(entry: LedgerEntry) -> Optional[dict]:
    """Run the design's brine loop on GEMINI and set its figures against the plant model's.

    At each doublet's full flow: the ESP's and the injection pumps' power, the injection
    pressure, the wellhead and reinjection temperatures, the exchanger's duty, and the ESP's
    intake against the gas bubble point (GEMINI's ESP is set where the subsurface check says).
    Computed once per design (``entry.gemini``).
    """
    if entry.gemini is not None:
        return entry.gemini
    alt = entry.alternative
    if not alt.n_doublets:
        return None
    from dioscuri_plant.subsurface import bubble_point_bar
    from dioscuri_plant.types import open_interval
    from gemini_agent import workbench
    from gemini_agent.tools.gemini import doublet_point

    rules = rules_for(entry.brief)
    project = workbench.graph_view(entry).get("gemini_project")
    if not project:
        return None
    run = workbench.run_gemini(project)
    if not run.get("ok"):
        entry.gemini = {"ok": False, "error": run.get("error"), "rows": [], "agree": 0, "total": 0}
        return entry.gemini
    out = run["outputs"]
    rows: List[dict] = []

    def add(quantity, unit, gem, plant, note="", temp=False):
        if gem is None or plant is None:
            return
        diff = gem - plant
        pct_ = 100 * diff / plant if plant else 0.0
        agree = abs(diff) <= 1.0 if temp else abs(pct_) <= AGREE_PCT
        rows.append(
            {
                "quantity": quantity,
                "unit": unit,
                "gemini": round(gem, 3),
                "plant": round(plant, 3),
                "diff_pct": round(pct_, 1),
                "agree": bool(agree),
                "note": note,
            }
        )

    plant = plant_of(alt)
    specs = plant.specs()
    many = len(specs) > 1
    esp_total = inj_total = 0.0
    gem_esp = gem_inj = 0.0
    for i, d in enumerate(specs):
        sfx = f"_{i + 1}" if many else ""
        cap = d.cap_m3h(rules)
        # As the year model solves it (``year.doublet_curves``): the rock of the aquifer the
        # doublet is drilled into, the wells' open parts, the flow shared by its injectors.
        here = rules.aquifer_at(d.depth_m)
        p_mid, p_len = open_interval(d.depth_m, d.producer_open, here.reservoir_thickness_m)
        i_mid, i_len = open_interval(d.depth_m, d.injector_open, here.reservoir_thickness_m)
        point = doublet_point(cap, p_mid, here, "fixed", p_len)
        injection = doublet_point(cap / max(d.injectors, 1), i_mid, here, "fixed", i_len)
        prod = out.get(f"producer_well{sfx}") or {}
        inj = out.get(f"injector_well{sfx}") or out.get(f"injector_well{sfx}_a") or {}
        esp_total += point["esp_mw"]
        inj_total += injection["injector_pump_mw"] * d.injectors
        gem_esp += float(prod.get("esp_power_el") or 0.0) / 1e6
        gem_inj += sum(
            float(v.get("power_el") or 0.0) / 1e6
            for k, v in out.items()
            if k.startswith(f"injector_well{sfx}")
        )
        tag = f" (doublet {i + 1})" if many else ""
        if inj:
            add(
                f"Injection wellhead pressure{tag}",
                "bar",
                inj.get("wellhead_pressure"),
                injection["injection_wellhead_bar"],
            )
        intake = prod.get("esp_intake_pressure")
        if intake is not None:
            bubble = bubble_point_bar(float(prod.get("temperature_out") or 86.0), rules) - 1.0
            rows.append(
                {
                    "quantity": f"ESP intake above the gas bubble point{tag}",
                    "unit": "bar",
                    "gemini": round(float(intake), 2),
                    "plant": round(bubble, 2),
                    "diff_pct": round(100 * (float(intake) - bubble) / bubble, 1),
                    "agree": float(intake) >= bubble,
                    "note": f"GEMINI's intake against the bubble point {bubble:.1f} bar(g); its "
                    f"ESP is set at {_esp_depth(project, sfx):,.0f} m",
                }
            )
        add(
            f"Wellhead temperature{tag}",
            "°C",
            prod.get("temperature_out"),
            point["wellhead_c"],
            note="GEMINI takes it as an input (Ramey's loss up the well)",
            temp=True,
        )
    add("ESP power, all doublets", "MW", gem_esp, esp_total)
    add("Injection pump power, all doublets", "MW", gem_inj, inj_total)
    hx = out.get("heat_exchanger") or {}
    if hx:
        caps = sum(d.cap_m3h(rules) for d in specs)
        brine = float(rules.brine_mw_per_k(caps))
        twh = entry.year.wellhead_c
        out_c = min(rules.heat_return_c + plant.hex_approach_k, twh)
        add(
            "Exchanger duty at full flow",
            "MW",
            float(hx.get("heat_duty") or 0.0) / 1e6,
            brine * (twh - out_c),
            note="GEMINI's exchanger with the brine's density and heat capacity on both sides",
        )
        add(
            "Brine after the exchanger",
            "°C",
            hx.get("primary_temperature_out"),
            out_c,
            temp=True,
        )
    agree = sum(r["agree"] for r in rows)
    entry.gemini = {
        "ok": True,
        "error": None,
        "rows": rows,
        "agree": agree,
        "total": len(rows),
        "seconds": run.get("seconds"),
        "warnings": run.get("warnings") or [],
    }
    return entry.gemini


def _esp_depth(project: dict, sfx: str) -> float:
    """Return where a GEMINI project sets a producer's ESP, m."""
    comp = project.get("components", {}).get(f"producer_well{sfx}", {})
    return float(comp.get("parameters", {}).get("esp_depth_m", 0.0))
