"""Verifier: the physics and requirement checks every reported design must pass.

Plain code, no model. A failed physics check means a tool is wrong, so the design is not
reported. A failed requirement check (coverage below what was asked) means the design is
feasible physics but does not meet the brief, which the reporter turns into an honest
"no design meets this" answer. The Carnot limit is recomputed here from the temperatures
rather than trusted from the tool. Each component is checked too: no temperature cross in the
heat exchanger, no unit giving more energy than its size allows over a year, heat pump heat
equal to electricity times COP, and the brine giving no more heat than it carries (which
bounds the absorption chiller's drive). The last two run only when the tool reports the
optional fields they need.
"""

from __future__ import annotations

from typing import List, Optional

from gemini_agent.contract import Check, DesignBrief, Economics, Verification, YearResult

REINJECT_MIN_C = 30.0
ABS_MIN_DRIVE_C = 80.0
DEFAULT_SUPPLY_C = 70.0
HOURS = 8760
# Split keys the tools report, with the unit's name and its size field in ``YearResult``.
UNITS = {
    "geo": ("heat exchanger", "hex_mw"),
    "hp": ("heat pump", "heat_pump_mw"),
    "boiler": ("boiler", "boiler_mw"),
    "abs": ("absorption chiller", "absorption_mw"),
    "chill": ("chillers", "chiller_mw"),
}


def carnot_cop(supply_c: float, source_c: float) -> float:
    """Return the Carnot COP of a heat pump.

    Parameters
    ----------
    supply_c : float
        Delivery temperature, °C.
    source_c : float
        Source temperature, °C.

    Returns
    -------
    float
        ``T_hot / (T_hot - T_cold)`` in kelvin.
    """
    return (supply_c + 273.15) / max(supply_c - source_c, 1e-6)


def verify(year: YearResult, econ: Economics, brief: DesignBrief) -> Verification:
    """Run every check on one simulated design.

    Parameters
    ----------
    year : YearResult
        The simulated year.
    econ : Economics
        Its costs.
    brief : DesignBrief
        What was asked (network temperatures, minimum coverage).

    Returns
    -------
    Verification
        One ``Check`` per rule.
    """
    checks: List[Check] = []

    def add(name: str, passed: bool, detail: str, requirement: bool = False) -> None:
        checks.append(Check(name=name, passed=bool(passed), detail=detail, requirement=requirement))

    heat_sum = sum(year.heat_split_gwh.values())
    cold_sum = sum(year.cool_split_gwh.values())
    add(
        "Heat adds up",
        abs(heat_sum - year.heat_delivered_gwh) <= 0.02,
        f"{heat_sum:.1f} GWh from the sources, {year.heat_delivered_gwh:.1f} GWh delivered",
    )
    add(
        "Cold adds up",
        abs(cold_sum - year.cool_delivered_gwh) <= 0.02,
        f"{cold_sum:.1f} GWh from the sources, {year.cool_delivered_gwh:.1f} GWh delivered",
    )
    add(
        "No more heat than demand",
        year.heat_delivered_gwh <= year.heat_demand_gwh + 0.02,
        f"{year.heat_delivered_gwh:.1f} of {year.heat_demand_gwh:.1f} GWh",
    )
    add(
        "No more cold than demand",
        year.cool_delivered_gwh <= year.cool_demand_gwh + 0.02,
        f"{year.cool_delivered_gwh:.1f} of {year.cool_demand_gwh:.1f} GWh",
    )
    supply = brief.heating.supply_c if brief.heating else DEFAULT_SUPPLY_C
    if year.heat_pump_mw > 0:
        limit = carnot_cop(supply, year.reinjection_c)
        add(
            "Heat pump COP below the Carnot limit",
            year.heat_pump_cop < limit,
            f"COP {year.heat_pump_cop:.1f} < {limit:.1f} at {year.reinjection_c:g} °C in and "
            f"{supply:g} °C out",
        )
    if year.wellhead_c > 15:
        add(
            "Brine cools along its path",
            year.wellhead_c >= year.hex_outlet_c - 0.05 >= year.reinjection_c - 0.1,
            f"{year.wellhead_c:g} → {year.hex_outlet_c:g} → {year.reinjection_c:g} °C",
        )
        add(
            "Reinjection at or above 30 °C",
            year.reinjection_c >= REINJECT_MIN_C - 0.05,
            f"{year.reinjection_c:g} °C",
        )
    heating = brief.heating
    if year.hex_mw > 0 and heating:
        add(
            "No temperature cross in the heat exchanger",
            year.wellhead_c >= heating.supply_c and year.hex_outlet_c >= heating.return_c,
            f"brine {year.wellhead_c:g} → {year.hex_outlet_c:g} °C, network "
            f"{heating.return_c:g} → {heating.supply_c:g} °C",
        )
    loads = [
        (UNITS[key][0], gwh, getattr(year, UNITS[key][1]))
        for split in (year.heat_split_gwh, year.cool_split_gwh)
        for key, gwh in split.items()
        if key in UNITS
    ]
    if loads:
        over = [x for x in loads if x[1] > x[2] * HOURS / 1000 + 0.02]
        label, gwh, size = max(over or loads, key=lambda x: x[1] / max(x[2], 1e-9))
        add(
            "No unit gives more than its size allows",
            not over,
            f"{label}: {gwh:.1f} of {size * HOURS / 1000:.1f} GWh possible at {size:g} MW",
        )
    hp_heat = year.heat_split_gwh.get("hp", 0.0)
    if year.heat_pump_electricity_gwh and hp_heat > 0:
        expected = year.heat_pump_electricity_gwh * year.heat_pump_cop
        add(
            "Heat pump heat = electricity × COP",
            abs(hp_heat - expected) <= 0.02 + 0.01 * hp_heat,
            f"{hp_heat:.1f} GWh vs {year.heat_pump_electricity_gwh:.1f} GWh × "
            f"{year.heat_pump_cop:.1f}",
        )
    if year.brine_heat_gwh is not None and year.brine_capacity_mw:
        possible = year.brine_capacity_mw * HOURS / 1000
        add(
            "Brine gives no more heat than it carries",
            year.brine_heat_gwh <= possible + 0.02,
            f"{year.brine_heat_gwh:.1f} of {possible:.1f} GWh a year",
        )
    if brief.heating:
        add(
            "Heating supply above return",
            brief.heating.supply_c > brief.heating.return_c,
            brief.heating.label(),
        )
    if brief.cooling:
        add(
            "Cooling return above supply",
            brief.cooling.return_c > brief.cooling.supply_c,
            brief.cooling.label(),
        )
    if year.absorption_mw > 0:
        add(
            "Absorption chiller driven hot enough",
            year.wellhead_c >= ABS_MIN_DRIVE_C,
            f"{year.wellhead_c:g} °C ≥ {ABS_MIN_DRIVE_C:g} °C",
        )
    if year.heat_delivered_gwh > 0:
        add("Cost is finite", econ.lcoh_eur_per_mwh < 1000, f"{econ.lcoh_eur_per_mwh:g} EUR/MWh")
    add(
        f"Heat coverage at least {brief.min_heat_coverage:.0%}",
        year.heat_coverage >= brief.min_heat_coverage - 1e-6,
        f"{year.heat_coverage:.1%}",
        requirement=True,
    )
    if brief.wants_cooling and year.cool_demand_gwh > 0:
        add(
            f"Cold coverage at least {brief.min_cool_coverage:.0%}",
            year.cool_coverage >= brief.min_cool_coverage - 1e-6,
            f"{year.cool_coverage:.1%}",
            requirement=True,
        )
    return Verification(alternative=year.alternative, checks=checks)


def physics_ok(v: Verification) -> bool:
    """Return True when every physics check passed (requirement checks aside)."""
    return all(c.passed for c in v.checks if not c.requirement)


def meets_brief(v: Verification) -> bool:
    """Return True when every requirement check passed."""
    return all(c.passed for c in v.checks if c.requirement)


def verify_plant(year, rules, alternative: str, caps=None) -> Verification:
    """Run the challenge's checks on a year of ``dioscuri_plant`` (the engine's designs).

    Physics checks (a failure means a model is wrong, so the design is not reported): the
    daily energy balance, each machine below its Carnot limit, the absorption chiller below
    one, the exchanger without a temperature cross. Requirement checks are the challenge's
    hard caps: heat at the supply temperature and cold at its supply every day, 50-300 m3/h
    per running doublet, the brine cooled by at most 40 K, the operating days, 1-3 doublets.

    Parameters
    ----------
    year : dioscuri_plant.YearResult
        The design's year.
    rules : dioscuri_plant.Rules
        The challenge's inputs and caps.
    alternative : str
        The design's code.
    caps : dioscuri_plant.Rules, optional
        The project's own caps (the challenge's). A request may relax a cap for a what-if
        ("run 365 days"); the requirement checks still hold the design to these, and say what
        was asked. Defaults to ``rules``.

    Returns
    -------
    Verification
        Every check with a one-line detail.
    """
    p = year.plant
    caps = caps or rules

    def asked(key: str, unit: str) -> str:
        """Say when the run used another value than the project's cap."""
        mine, theirs = getattr(rules, key), getattr(caps, key)
        if mine == theirs:
            return ""
        return f"; this run used {mine:g}{unit} as you asked, the cap is {theirs:g}{unit}"

    checks: List[Check] = []

    def add(name: str, passed: bool, detail: str, requirement: bool = False):
        checks.append(Check(name=name, passed=bool(passed), detail=detail, requirement=requirement))

    add(
        "Daily energy balance",
        year.balance_error <= 1e-3,
        f"worst day off by {year.balance_error:.4%} (0.1 % allowed)",
    )
    if year.heat_pump_cop > 0:
        carnot = carnot_cop(rules.heat_supply_c, year.min_reinjection_c)
        add(
            "Heat pump below Carnot",
            year.heat_pump_cop <= carnot,
            f"COP {year.heat_pump_cop:.2f}; Carnot {carnot:.2f} at its coldest source",
        )
    if p.chiller_mw > 0:
        t_evap = rules.cool_supply_c - 2.0 + 273.15
        carnot_ch = t_evap / max(35.0 + 273.15 - t_evap, 1e-6)
        add(
            "Chillers below Carnot",
            year.chiller_cop <= carnot_ch,
            f"COP {year.chiller_cop:.2f}; Carnot {carnot_ch:.2f}",
        )
    if p.absorption_mw > 0:
        add(
            "Absorption COP below one",
            0 < year.absorption_cop < 1,
            f"COP {year.absorption_cop:.2f} (single effect)",
        )
    if p.n_doublets > 0:
        hot_end = year.wellhead_c - p.hex_approach_k
        add(
            "No temperature cross in the exchanger",
            hot_end > rules.heat_return_c,
            f"network heated to {min(hot_end, rules.heat_supply_c):.1f} °C by brine at "
            f"{year.wellhead_c:.1f} °C",
        )
    short_heat, short_cool = year.peak_shortfall_mw["heat"], year.peak_shortfall_mw["cool"]
    add(
        f"Heat at {caps.heat_supply_c:g} °C every day",
        short_heat <= 1e-6 and rules.heat_supply_c >= caps.heat_supply_c,
        ("met every day" if short_heat <= 1e-6 else f"short by up to {short_heat:.2f} MW")
        + asked("heat_supply_c", " °C"),
        requirement=True,
    )
    if year.cool_demand_gwh > 0:
        add(
            f"Cold at {caps.cool_supply_c:g} °C every day",
            short_cool <= 1e-6 and rules.cool_supply_c <= caps.cool_supply_c,
            ("met every day" if short_cool <= 1e-6 else f"short by up to {short_cool:.2f} MW")
            + asked("cool_supply_c", " °C"),
            requirement=True,
        )
    if p.n_doublets > 0:
        flows = [f for d in year.doublets for f, on in zip(d["flow_m3h"], d["on"]) if on] or [0.0]
        add(
            f"Flow {caps.flow_min_m3h:g}-{caps.flow_max_m3h:g} m3/h per doublet",
            caps.flow_min_m3h - 1e-6 <= min(flows) and max(flows) <= caps.flow_max_m3h + 1e-6,
            f"{min(flows):.0f}-{max(flows):.0f} m3/h while running"
            + asked("flow_min_m3h", " m3/h")
            + asked("flow_max_m3h", " m3/h"),
            requirement=True,
        )
        add(
            f"Brine cooled by at most {caps.max_brine_cooling_k:g} K",
            year.max_brine_cooling_k <= caps.max_brine_cooling_k + 1e-6,
            f"at most {year.max_brine_cooling_k:.1f} K (reinjection from "
            f"{year.min_reinjection_c:.1f} °C)" + asked("max_brine_cooling_k", " K"),
            requirement=True,
        )
        days = max(sum(d["on"]) for d in year.doublets)
        # The user's stop dates (one block or several a doublet): the days off each one had.
        off = [sum(b - a + 1 for a, b in r) for r in (getattr(year, "stop_ranges", None) or [])]
        yours = getattr(rules, "doublet_stops", ()) and off
        add(
            f"At most {caps.operating_days} days per doublet",
            days <= caps.operating_days,
            f"{days} days at most"
            + asked("operating_days", " days")
            + (f"; stopped {', '.join(map(str, off))} days, on your dates" if yours else ""),
            requirement=True,
        )
        add(
            "Production equals injection",
            True,
            f"{year.brine_m3:,.0f} m3 produced and injected",
            requirement=True,
        )
    add(
        "One to three doublets",
        1 <= p.n_doublets <= 3 or p.n_doublets == 0,
        "reference without doublets" if p.n_doublets == 0 else f"{p.n_doublets}",
        requirement=True,
    )
    gas = _gas_by_aquifer(year, rules)
    if gas is not None:
        # Each doublet's brine brings its own aquifer's gas: what the year burnt, flared and
        # sold is the sum of the doublets' (a model error otherwise, not a cap).
        add("Produced gas from each doublet's aquifer", *gas)
    rows = [r for r in (year.doublet_summary or []) if r.get("breakthrough_years") is not None]
    if rows:
        # The subsurface checks (dioscuri_plant.subsurface): not the challenge's caps, but a
        # design that breaks one cannot be built as it is.
        worst = min(rows, key=lambda r: r["breakthrough_years"])
        add(
            "Cold water reaches the producer after the 30-year life",
            all(r["breakthrough_years"] >= 30 for r in rows),
            f"after {worst['breakthrough_years']:.0f} years at the earliest (doublet "
            f"{worst['doublet']}{_in_aquifer(worst, rows)}; Gringarten-Sauty)",
            requirement=True,
        )
        deep = max(rows, key=lambda r: r["esp_setting_m"])
        add(
            "ESP intake above the gas bubble point",
            all(r["esp_setting_m"] <= 1000 for r in rows),
            f"ESP at {deep['esp_setting_m']:,.0f} m or deeper (bubble point "
            f"{deep['bubble_point_bar']:.1f} bar; at most 1,000 m)"
            + (
                f"; doublet {deep['doublet']}{_in_aquifer(deep, rows)}"
                if _in_aquifer(deep, rows)
                else ""
            ),
            requirement=True,
        )
        tight = max(rows, key=lambda r: r["injection_top_bar"] - r["injection_limit_bar"])
        add(
            "Injection pressure under SodM's limit",
            all(r["injection_top_bar"] <= r["injection_limit_bar"] for r in rows),
            f"{tight['injection_top_bar']:.0f} bar at the top of the reservoir against "
            f"{tight['injection_limit_bar']:.0f} bar (0.135 bar/m)"
            + (
                f"; doublet {tight['doublet']}{_in_aquifer(tight, rows)}"
                if _in_aquifer(tight, rows)
                else ""
            ),
            requirement=True,
        )
    return Verification(alternative=alternative, checks=checks)


def _in_aquifer(row: dict, rows: List[dict]) -> str:
    """Return ", aquifer 2 at 3,100 m" for a doublet's row when the doublets' aquifers differ."""
    depths = {r.get("aquifer_depth_m") for r in rows}
    if len(depths) < 2 or row.get("aquifer_depth_m") is None:
        return ""
    n = row.get("aquifer")
    where = f"aquifer {n}" if n else "an assumed aquifer"
    return f", {where} at {float(row['aquifer_depth_m']):,.0f} m"


def _gas_by_aquifer(year, rules) -> Optional[tuple]:
    """Return (passed, detail) for the produced gas against each doublet's aquifer's, or None.

    The methane of each doublet's brine (its flow times its aquifer's gas-liquid ratio and
    the gas's methane share) summed, against what the year burnt, flared and sold. None for a
    year without the doublets' gas (the reference, an older result).
    """
    from dioscuri_plant.components import LHV_CH4_MJ_PER_NM3

    rows = [r for r in (year.doublet_summary or []) if r.get("gas_nm3") is not None]
    if not rows:
        return None
    ch4 = float(getattr(rules, "gas_ch4_fraction", 0.8))
    mine = sum(float(r["gas_nm3"]) for r in rows) * ch4 * LHV_CH4_MJ_PER_NM3 / 3.6e6
    year_gwh = (
        float(year.produced_gas_burned_gwh or 0.0)
        + float(year.produced_gas_flared_gwh or 0.0)
        + float(getattr(year, "produced_gas_sold_gwh", 0.0) or 0.0)
    )
    passed = abs(mine - year_gwh) <= 0.005 * max(year_gwh, mine) + 0.01
    parts = [
        f"doublet {r['doublet']} {float(r['gas_liquid_ratio']):g} Nm3/m3"
        + (f" (aquifer {r['aquifer']})" if r.get("aquifer") else "")
        for r in rows
    ]
    return (
        passed,
        f"{year_gwh:.2f} GWh of methane a year; the doublets' brine at their aquifers' "
        f"gas-liquid ratios gives {mine:.2f} GWh ({', '.join(parts)})",
    )
