"""GEMINI-backed tools: the challenge's doublet from GEMINI's own well solve, with the team's fixes.

- ``doublet_point`` / ``doublet_model``: at a set brine flow, GEMINI's well-segment model
  (with the challenge's brine, patch 11) and reservoir inflow give the ESP head, and its
  injector solve the injection pressure; both pumps at the challenge's 70 %.
- ``challenge_project``: one doublet as a GEMINI project (the Design tab's "GEMINI project"
  view), which ``run`` puts through GEMINI's solver.
- ``heat_pump_point``: GEMINI's ``HeatpumpBasic`` at a design's operating point.

The ``"fixed"`` GEMINI (``gemini_runtime``) runs every design; ``"asis"`` is GEMINI as
released, for the report's "what the released code would have given" (``engine.bug_impact``).
"""

from __future__ import annotations

import copy
import json
import math
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from gemini_agent import gemini_runtime

BASE_PROJECT = gemini_runtime.ROOT / "simulator_examples" / "projects" / "doublet_plant.json"
RHO, CP = 1000.0, 4181.0  # GEMINI's water (PVTConstantSTP, HeatpumpBasic defaults)
ESP_DEPTH_M = 650.0  # GEMINI's doublet example
ESP_HZ = 65.0  # GEMINI's doublet example
GRID_KG_PER_KWH = 0.3  # GEMINI's example projects
SURFACE = ("producer_well", "separator", "filter_a", "heat_exchanger", "filter_b")


def run(proj: dict, variant: str = "fixed") -> Dict[str, float]:
    """Run a project on GEMINI's solver and return the plant's outputs.

    Returns
    -------
    dict
        ``flow_m3h``, ``esp_mw``, ``injector_pump_mw``, ``injector_wellhead_bar``,
        ``hex_in_c``, ``hex_out_c``, ``network_out_c``, ``hex_duty_mw`` and ``co2_kg_h``.
    """
    solver = gemini_runtime.load(variant).build_project(proj)
    solver.run()

    def out(component: str, key: str) -> float:
        return float(solver.get_output(component, key))

    def of_type(type_: str):
        return [k for k, c in proj["components"].items() if c.get("type") == type_]

    producers, injectors = of_type("producer_well"), of_type("injector_well")
    esp_w = sum(out(c, "esp_power_el") for c in producers)
    inj_w = sum(out(c, "power_el") for c in injectors)
    feed = next(
        (
            c["predecessor"]
            for c in proj["connections"]
            if c["successor"] == "heat_exchanger"
            and any(port[1] == "primary_temperature_in" for port in c["ports"])
        ),
        "filter_a",
    )
    feed_key = (
        "temperature" if proj["components"][feed].get("type") == "mixer" else ("temperature_out")
    )
    return {
        "flow_m3h": sum(out(c, "flow_rate") for c in producers),
        "esp_mw": esp_w / 1e6,
        "injector_pump_mw": inj_w / 1e6,
        "injector_wellhead_bar": out(injectors[0], "wellhead_pressure"),
        "hex_in_c": out(feed, feed_key),
        "hex_out_c": out("heat_exchanger", "primary_temperature_out"),
        "network_out_c": out("heat_exchanger", "secondary_temperature_out"),
        "hex_duty_mw": out("heat_exchanger", "heat_duty") / 1e6,
        "co2_kg_h": (esp_w + inj_w) / 1e3 * GRID_KG_PER_KWH,
    }


# --------------------------------------------------------------------- the challenge's doublet
#
# The challenge fixes the brine (1,030 kg/m3, 0.40 mPa·s), the pumps (70 % hydraulic) and the
# flow window (50-300 m3/h per doublet). GEMINI's ProducerWell solves the flow an ESP curve
# gives; here the flow is the design's choice, so GEMINI's own pieces answer the question the
# other way round: its well-segment model (DPDT, with the brine through patch 11) walks the
# producer from the wellhead to the bottom at that flow, its reservoir inflow (IPR) says what
# the reservoir supplies there, and the ESP makes up the difference. The injector side is
# GEMINI's injector solve as it stands (patch 02 fixes its friction sign).

# Rules fields a well's solve does not read, kept out of its cache's key.
SOLVE_IGNORES = ("doublet_stops", "other_aquifers")
WELL_BORE_M = 0.2159  # 8.5 in: our well design for 300 m3/h (GEMINI's example has 0.15 m)
PRODUCER_WELLHEAD_BAR = 5.0  # surface separator pressure
RETURN_BAR = 4.0  # brine at the injection pump's inlet, after the surface plant
INJECTION_C = 50.0  # about the reinjection temperature (constant-property brine)


def well_config(depth_m: float, rules=None, open_m: Optional[float] = None) -> dict:
    """Return the well configuration GEMINI's well solve reads, for the challenge's reservoir.

    Parameters
    ----------
    depth_m : float
        Depth of the middle of the well's open part (vertical well), m.
    rules : dioscuri_plant.Rules, optional
        The challenge's inputs; the defaults when omitted.
    open_m : float, optional
        Length of the well open to the aquifer; its whole thickness when omitted.

    Returns
    -------
    dict
        ``reservoir_pressure_bar``, ``productivity_index_m3h_per_bar``, ``trajectory_table``
        and the brine's properties as ``fluid`` (patch 11).
    """
    from dioscuri_plant import Rules
    from dioscuri_plant.doublet import productivity_index_m3h_per_bar, reservoir_pressure_bar

    rules = rules or Rules()
    return {
        "reservoir_pressure_bar": reservoir_pressure_bar(depth_m, rules),
        "productivity_index_m3h_per_bar": productivity_index_m3h_per_bar(rules, open_m),
        "trajectory_table": [
            {"MD": 0.0, "TVD": 0.0, "ID": WELL_BORE_M},
            {"MD": float(depth_m), "TVD": float(depth_m), "ID": WELL_BORE_M},
        ],
        "fluid": {
            "RHOL": rules.brine_density_kg_m3,
            "VISL": rules.brine_viscosity_pa_s,
            "CPL": rules.brine_cp_j_kg_k,
        },
    }


@lru_cache(maxsize=8192)
def _doublet_point(
    flow_m3h: float, depth_m: float, rules_key: tuple, variant: str, open_m: Optional[float] = None
) -> str:
    from dioscuri_plant import Rules
    from dioscuri_plant.doublet import well_loss_k

    rules = Rules(**dict(rules_key))
    wf = gemini_runtime.load(variant).well_flow
    cfg = well_config(depth_m, rules, open_m)
    # GEMINI takes the wellhead temperature as an input (ProducerWell passes it through):
    # the rock's temperature at depth less the heat lost up the well at this flow (Ramey).
    loss_k = well_loss_k(flow_m3h, depth_m, rules)
    wellhead_c = rules.reservoir_temperature_c(depth_m) - loss_k
    segments = wf._resolve_trajectory_segments(cfg)
    try:
        dpdt = wf._build_dpdt(segments, fluid=cfg["fluid"])
    except TypeError:  # GEMINI as released has no brine (patch 11): water at STP
        dpdt = wf._build_dpdt(segments)
    q = flow_m3h / 3600.0
    dpdt.calculate_output(
        {
            "pressure": PRODUCER_WELLHEAD_BAR * 1e5,
            "temperature": wellhead_c + 273.15,
            "temperature_ambient": wellhead_c + 273.15,
            "flowrate": q,
            "direction": "down",
        },
        None,
    )
    needed_bar = dpdt.get_output()["pressure_output"] / 1e5  # at the bottom, to lift the flow
    supplied_bar = cfg["reservoir_pressure_bar"] - flow_m3h / cfg["productivity_index_m3h_per_bar"]
    esp_head = max(0.0, needed_bar - supplied_bar)
    try:
        injection_bar = wf.solve_injector_wellhead_pressure_bar(cfg, flow_m3h, INJECTION_C)
        injection_solve = "gemini"
    except ValueError:
        # GEMINI's root finder searches 0.001-500 bar at the wellhead; tight rock needs more (at
        # 8 mD the challenge's aquifer would need about 600 bar). The closed form it agrees with
        # to 0.5 % elsewhere: reservoir pressure + build-up + friction - the brine column. The
        # subsurface checks then flag the pressure and cap the flow (``subsurface_caps``).
        from dioscuri_plant.doublet import G, friction_bar

        column = rules.brine_density_kg_m3 * G * depth_m / 1e5
        injection_bar = (
            cfg["reservoir_pressure_bar"]
            + flow_m3h / cfg["productivity_index_m3h_per_bar"]
            + friction_bar(flow_m3h, depth_m, rules)
            - column
        )
        injection_solve = "closed form (beyond GEMINI's 500 bar search)"
    boost = max(0.0, injection_bar - RETURN_BAR)
    to_mw = q * 1e5 / rules.pump_efficiency / 1e6  # bar of head at this flow -> MW
    return json.dumps(
        {
            "wellhead_c": wellhead_c,
            "well_loss_k": loss_k,
            "esp_mw": esp_head * to_mw,
            "injector_pump_mw": boost * to_mw,
            "esp_head_bar": esp_head,
            "bottomhole_bar": supplied_bar,
            "injection_wellhead_bar": injection_bar,
            "gas_nm3h": flow_m3h * rules.gas_liquid_ratio,
            "pi_m3h_per_bar": cfg["productivity_index_m3h_per_bar"],
            "source": "gemini",
            "injection_solve": injection_solve,
        }
    )


def doublet_point(
    flow_m3h: float,
    depth_m: float,
    rules=None,
    variant: str = "fixed",
    open_m: Optional[float] = None,
) -> dict:
    """Return the challenge doublet's operating point at a brine flow, from GEMINI's well solve.

    Parameters
    ----------
    flow_m3h : float
        Brine flow, m3/h (production = injection).
    depth_m : float
        Depth of the middle of the wells' open part, m.
    rules : dioscuri_plant.Rules, optional
        The challenge's inputs.
    variant : {"fixed", "asis"}
        GEMINI with the team's patches, or as released.
    open_m : float, optional
        Length of the wells open to the aquifer; its whole thickness when omitted.

    Returns
    -------
    dict
        ``wellhead_c``, ``esp_mw``, ``injector_pump_mw``, ``esp_head_bar``, ``bottomhole_bar``,
        ``injection_wellhead_bar``, ``gas_nm3h``, ``pi_m3h_per_bar``.
    """
    from dataclasses import asdict

    from dioscuri_plant import Rules

    rules = rules or Rules()
    # The doublets' stop dates do not change a well's solve, nor the aquifers it is not in (the
    # rules are already its own aquifer's, ``Rules.aquifer_at``): kept out of the cache's key.
    key = tuple(sorted((k, v) for k, v in asdict(rules).items() if k not in SOLVE_IGNORES))
    open_key = None if open_m is None else round(float(open_m), 3)
    return json.loads(
        _doublet_point(round(float(flow_m3h), 3), float(depth_m), key, variant, open_key)
    )


def doublet_model(rules=None, variant: str = "fixed"):
    """Return ``doublet(flow_m3h, depth_m, open_m=None)`` backed by GEMINI, for the plant model."""

    def doublet(flow_m3h: float, depth_m: float, open_m: Optional[float] = None) -> dict:
        # The rock of the aquifer each doublet is drilled into (``Rules.aquifer_at``).
        here = rules.aquifer_at(depth_m) if rules is not None else rules
        return doublet_point(flow_m3h, depth_m, here, variant, open_m)

    return doublet


def heat_pump_point(
    source_in_c: float,
    source_flow_m3h: float,
    sink_in_c: float,
    sink_out_c: float,
    heat_mw: float,
    variant: str = "fixed",
    eta: float = 0.5,
    floor_c: float = 46.0,
) -> Dict[str, float]:
    """Return GEMINI's ``HeatpumpBasic`` (Carnot mode) at a top-up operating point.

    The network enters at ``sink_in_c`` and leaves at ``sink_out_c`` carrying ``heat_mw``; the
    brine enters the evaporator at ``source_in_c``. Used to set the released model against the
    fixed one on a design's own numbers.

    Returns
    -------
    dict
        ``cop``, ``heat_mw``, ``electricity_mw``, ``sink_out_c``, ``source_out_c``,
        ``co2_kg_h``; or ``error`` when GEMINI's model raises.
    """
    hp = gemini_runtime.load(variant).HeatpumpBasic()
    hp.update_parameters(
        {
            "mode": "carnot",
            "eta_carnot": eta,
            "Th_out_target": sink_out_c,
            "Ts_in_minimum": floor_c,
            "electricity_emission_factor": GRID_KG_PER_KWH,
        }
    )
    sink_m3s = heat_mw * 1e6 / (RHO * CP * max(sink_out_c - sink_in_c, 1e-6))
    try:
        hp.calculate_output(
            {
                "Th_in": sink_in_c,
                "Ts_in": source_in_c,
                "hot_flow_rate": sink_m3s,
                "source_flow_rate": source_flow_m3h / 3600,
            }
        )
    except Exception as err:  # noqa: BLE001 - the released model can fail outright
        return {"error": f"{type(err).__name__}: {err}"}
    o = hp.output
    return {
        "cop": round(float(o["COP"]), 3),
        "heat_mw": round(float(o["Thermal_production"]) / 1e6, 3),
        "electricity_mw": round(float(o["electrical_consumption"]) / 1e6, 3),
        "sink_out_c": round(float(o["Th_out"]), 2),
        "source_out_c": round(float(o["Ts_out"]), 2),
        "co2_kg_h": round(float(o.get("emission", 0.0)) * 3600, 1),
    }


# GEMINI's nodal solve has more than one root for this well with its example ESP (bug F4): a
# wide bracket finds a non-physical 675 m3/h. A bracket around the design flow keeps the
# physical root, and the ESP's frequency is bisected on it.
FLOW_BRACKET_M3H = (200.0, 400.0)
# GEMINI's example ESP (10 stages) suits about 100-170 m3/h: at 300 m3/h its head curve is
# negative, so GEMINI would report a power that is not this design's. The GEMINI view uses the
# same pump family scaled to each producer's duty: flow scaled so the design flow sits at 60 %
# of the scaled pump's run-out, stages for the head the well needs at 55 Hz, and a power curve
# at the challenge's 70 % hydraulic efficiency at the frequency it runs at.
ESP_RUNOUT_SHARE = 0.6
ESP_PLAN_HZ = 55.0
BBLD_PER_M3H = 24 / 0.158987294928  # barrels a day per m3/h


def _poly(coeffs, x: float) -> float:
    return sum(c * x**k for k, c in enumerate(coeffs))


def duty_esp(flow_m3h: float, head_bar: float, efficiency: float, hz: float = 60.0) -> dict:
    """Return GEMINI's example ESP scaled to a duty (flow, head) at a set efficiency.

    The head curve per stage, ``h(q)`` (ft at 60 Hz, q in bbl/d), becomes ``h(q / s)``: the
    same pump shape for ``s`` times the flow. The power curve is head x flow / ``efficiency`` on
    the 60 Hz curve: the patched GEMINI (patch 05) scales flow with f, head with f² and power
    with f³, so the pump keeps that efficiency at every frequency (``hz`` is not used: kept for
    callers).
    """
    base = json.loads(BASE_PROJECT.read_text(encoding="utf-8"))
    esp = dict(base["components"]["producer_well"]["parameters"]["esp"])
    head = list(esp["head_coeff"])
    q_design = flow_m3h * BBLD_PER_M3H
    # The base curve's run-out: the first flow where its head per stage falls to zero.
    lo = 100.0
    while lo < 2.0e5 and _poly(head, lo + 100.0) > 0:
        lo += 100.0
    s = q_design / (ESP_RUNOUT_SHARE * lo)
    scaled = [c / s**k for k, c in enumerate(head)]
    per_stage_ft = _poly(scaled, q_design) * (ESP_PLAN_HZ / 60.0) ** 2
    head_ft = max(head_bar, 1.0) * 1e5 / 2988.30167
    stages = max(1, int(math.ceil(head_ft / max(per_stage_ft, 1e-6))))
    # Electrical power (bhp) = head (ft) x flow (bbl/d) x c / efficiency, at the run frequency;
    # GEMINI's model takes six coefficients, so the product is fitted over the working range.
    import numpy as np

    c = 2988.30167 / 543439.650564 / 745.7
    q = np.linspace(0.3, 1.0, 40) * lo * s
    target = np.array([_poly(scaled, x) * x for x in q]) * c / efficiency
    power = [float(v) for v in np.polynomial.polynomial.polyfit(q, target, 5)]
    esp.update(no_stages=stages, head_coeff=scaled, power_coeff=power)
    esp["_description"] = (
        f"GEMINI's example ESP scaled to {flow_m3h:g} m3/h (flow x{s:.2f}), {stages} stages for "
        f"{head_bar:.0f} bar, power at {efficiency:.0%} hydraulic efficiency"
    )
    return esp


def esp_depth(depth_m: float, flow_m3h: float, rules, open_m: Optional[float] = None) -> float:
    """Return where GEMINI's ESP is set: deep enough that its intake stays above the bubble point.

    The subsurface check's setting depth (``dioscuri_plant.subsurface``) rounded up to 10 m plus
    10 m of margin, and never shallower than GEMINI's example (650 m).
    """
    from dioscuri_plant.doublet import well_loss_k
    from dioscuri_plant.subsurface import bubble_point_bar, esp_setting_m

    pi = well_config(depth_m, rules, open_m)["productivity_index_m3h_per_bar"]
    wellhead_c = rules.reservoir_temperature_c(depth_m) - well_loss_k(flow_m3h, depth_m, rules)
    need = esp_setting_m(flow_m3h, depth_m, pi, bubble_point_bar(wellhead_c, rules), rules)
    return max(ESP_DEPTH_M, math.ceil(need / 10.0) * 10.0 + 10.0)


@lru_cache(maxsize=64)
def _duty_pump(
    depth_m: float, flow_m3h: float, rules_key: tuple, open_m: Optional[float] = None
) -> str:
    """Return the producer's ESP for its duty and the frequency that gives the flow (JSON)."""
    from dioscuri_plant import Rules
    from dioscuri_plant.doublet import well_loss_k

    rules = Rules(**dict(rules_key))
    need = doublet_point(flow_m3h, depth_m, rules, "fixed", open_m)["esp_head_bar"]
    wf = gemini_runtime.load("fixed").well_flow
    wellhead_c = rules.reservoir_temperature_c(depth_m) - well_loss_k(flow_m3h, depth_m, rules)
    esp = duty_esp(flow_m3h, need, rules.pump_efficiency)
    cfg = dict(
        well_config(depth_m, rules, open_m),
        esp=esp,
        esp_depth_m=esp_depth(depth_m, flow_m3h, rules, open_m),
    )
    bracket = (0.6 * flow_m3h, 1.4 * flow_m3h)

    def flow(hz: float) -> Optional[float]:
        try:
            return wf.solve_primary_flow_m3h(
                dict(cfg, esp_freq_hz=hz),
                PRODUCER_WELLHEAD_BAR,
                wellhead_c,
                flow_bracket_m3h=bracket,
            )
        except ValueError:
            return None

    lo, hi = 30.0, 70.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        q = flow(mid)
        if q is not None and q < flow_m3h:
            lo = mid
        else:
            hi = mid
    hz = round(lo, 3)
    esp = duty_esp(flow_m3h, need, rules.pump_efficiency, hz)
    return json.dumps({"esp": esp, "hz": hz, "head_bar": need})


def _esp_frequency(
    depth_m: float, flow_m3h: float, rules_key: tuple, open_m: Optional[float] = None
) -> float:
    """Return the frequency (Hz) at which the duty ESP gives this flow in GEMINI's solve."""
    return json.loads(_duty_pump(depth_m, flow_m3h, rules_key, open_m))["hz"]


def challenge_project(
    depth_m: float, n_doublets: int = 1, rules=None, boiler_mw: float = 0.0
) -> dict:
    """Return ``n`` identical doublets' brine loop as a GEMINI project (see ``plant_project``)."""
    n = max(1, int(n_doublets))
    return plant_project([{"depth_m": depth_m} for _ in range(n)], rules, boiler_mw)


# The treatment train is sized for its own flow: GEMINI's example separator and filters suit
# one doublet of about 140 m3/h and drop 3.6 bar at 300 m3/h (7 bar at 600, a negative
# pressure after the filters). Sized here so the whole loop drops 1 bar at its design flow
# (in the example's proportions), the 1 bar the plant model's pumps assume: the producers
# deliver 5 bar at the wellhead and the injection pumps take the brine at 4 bar.
TRAIN_DROP_BAR = {"separator": 0.08, "filter_a": 0.84, "filter_b": 0.08}


def _size_unit(params: dict, flow_m3h: float, drop_bar: float) -> None:
    """Set a separator's or filter's resistance so it drops ``drop_bar`` at its design flow.

    GEMINI's pressure drop is flow (m3/s) x resistance (bar s/m3); a filter's resistance also has
    a fouling term, scaled alike. Temperature drops are set to 0, as in the plant model.
    """
    q = max(flow_m3h, 1.0) / 3600.0
    if "flow_resistance" in params:
        params["flow_resistance"] = round(drop_bar / q, 4)
    if "base_resistance" in params:
        old = params["base_resistance"] + params.get("fouling_coeff_a", 0.0) * (
            1 - math.exp(-params.get("fouling_coeff_b", 0.0) * q)
        )
        factor = drop_bar / q / max(old, 1e-9)
        params["base_resistance"] = round(params["base_resistance"] * factor, 4)
        params["fouling_coeff_a"] = round(params.get("fouling_coeff_a", 0.0) * factor, 4)
    params["temperature_drop"] = 0.0


def plant_project(doublets: List[dict], rules=None, boiler_mw: float = 0.0) -> dict:
    """Return a design's brine loop as a GEMINI project (the Design tab's GEMINI view).

    Everything GEMINI can simulate is in it, one component per piece of equipment:

    - one ``producer_well`` per doublet (GEMINI's nodal solve: reservoir inflow, the well's
      tubing segments and the ESP, its frequency set so the well gives the doublet's flow cap),
      at the depth and with the open part of the aquifer of that doublet;
    - one treatment train per group of doublets that share one: a ``mixer`` joining the group's
      producers (when there are several), the ``separator`` (the produced gas) and a ``filter``;
    - a ``mixer`` (the brine header) when there are several trains, the ``heat_exchanger``
      (sized for the balanced duty of all the brine, 5 K at both ends), a second ``filter``;
    - a ``splitter`` sharing the brine among all injectors (each doublet's share, split equally
      between its injectors), and one ``injector_well`` per injector (its pump at 70 %);
    - with ``boiler_mw``, GEMINI's ``boiler`` burning the separated gas (an ``adder`` sums the
      separators' gas when there are several) and heating the network after the exchanger.

    GEMINI has no heat pump, chillers or absorption chiller, so those are only in the Plant
    view (the plant model). The treatment train is sized for a 1 bar drop at its design flow
    (``TRAIN_DROP_BAR``), so the producers' 5 bar wellhead pressure reaches the injection pumps
    at 4 bar, as the plant model assumes; GEMINI's ``booster_pump`` is therefore not placed. Its
    ``chp`` is not in these designs (the gas goes to the boiler).

    Parameters
    ----------
    doublets : list of dict
        Each doublet: ``depth_m`` (aquifer midpoint), ``producer_open``/``injector_open``
        (full, upper, lower), ``injectors`` (1 or 2), ``max_flow_m3h``, ``train``.
    rules : dioscuri_plant.Rules, optional
        The challenge's inputs.
    boiler_mw : float
        The design's boiler (0: none).
    """
    from dataclasses import asdict

    from dioscuri_plant import Rules
    from dioscuri_plant.doublet import well_loss_k
    from dioscuri_plant.types import open_interval

    rules = rules or Rules()
    base = json.loads(BASE_PROJECT.read_text(encoding="utf-8"))
    specs = []
    for d in doublets or [{}]:
        depth = float(d.get("depth_m") or rules.reservoir_depth_m)
        h = rules.aquifer_at(depth).reservoir_thickness_m  # its own aquifer's thickness
        cap = min(float(d.get("max_flow_m3h") or rules.flow_max_m3h), rules.flow_max_m3h)
        p_mid, p_len = open_interval(depth, d.get("producer_open") or "full", h)
        i_mid, i_len = open_interval(depth, d.get("injector_open") or "full", h)
        specs.append(
            {
                "depth": depth,
                "cap": cap,
                "p_mid": p_mid,
                "p_len": None if p_len == h else p_len,
                "i_mid": i_mid,
                "i_len": None if i_len == h else i_len,
                "rules": rules.aquifer_at(depth),
                "injectors": 2 if int(d.get("injectors") or 1) >= 2 else 1,
                "train": int(d.get("train") or 0),
            }
        )
    n = len(specs)
    trains = sorted({sp["train"] for sp in specs})
    multi_train = len(trains) > 1

    components: Dict[str, dict] = {}
    connections: List[dict] = []
    boundary: List[dict] = []

    def name(stem: str, i: int, many: bool) -> str:
        return f"{stem}_{i + 1}" if many else stem

    # Producers, each with its own depth, open part and ESP frequency.
    producers = []
    for i, sp in enumerate(specs):
        cfg = well_config(sp["p_mid"], sp["rules"], sp["p_len"])
        here = tuple(
            sorted((k, v) for k, v in asdict(sp["rules"]).items() if k not in SOLVE_IGNORES)
        )
        pump = json.loads(_duty_pump(float(sp["p_mid"]), sp["cap"], here, sp["p_len"]))
        prod = copy.deepcopy(base["components"]["producer_well"])
        prod["parameters"].update(
            cfg,
            esp=pump["esp"],
            esp_depth_m=esp_depth(float(sp["p_mid"]), sp["cap"], sp["rules"], sp["p_len"]),
            esp_freq_hz=pump["hz"],
            flow_bracket_m3h=[round(0.6 * sp["cap"], 1), round(1.4 * sp["cap"], 1)],
        )
        prod["parameters"].pop("_trajectory_table_description", None)
        prod["parameters"]["esp"]["electricity_emission_factor"] = GRID_KG_PER_KWH
        prod["_description"] = (
            f"Doublet {i + 1}'s producer: open over {sp['p_len'] or h:g} m of the aquifer around "
            f"{sp['p_mid']:,.0f} m TVD, {sp['cap']:g} m3/h"
        )
        pname = name("producer_well", i, n > 1)
        components[pname] = prod
        wellhead_c = rules.reservoir_temperature_c(sp["p_mid"]) - well_loss_k(
            sp["cap"], sp["p_mid"], rules
        )
        boundary += [
            {"component": pname, "key": "wellhead_pressure", "value": PRODUCER_WELLHEAD_BAR},
            {"component": pname, "key": "wellhead_temperature", "value": round(wellhead_c, 3)},
        ]
        producers.append(pname)

    # Treatment trains: the group's mixer, the separator and the first filter.
    gas_density = round(rules.gas_ch4_fraction * 0.717 + rules.gas_co2_fraction * 1.977, 3)
    train_out: List[str] = []
    separators: List[str] = []
    for t_i, t in enumerate(trains):
        members = [i for i, sp in enumerate(specs) if sp["train"] == t]
        sep_name = name("separator", t_i, multi_train)
        filt_name = name("filter_a", t_i, multi_train)
        if len(members) > 1:
            mix = name("brine_mixer", t_i, multi_train)
            components[mix] = {
                "type": "mixer",
                "_description": "The producers' brine joins before the treatment train",
                "parameters": {"num_inputs": len(members)},
            }
            for k, i in enumerate(members):
                connections.append(
                    {
                        "predecessor": producers[i],
                        "successor": mix,
                        "ports": [
                            ["flow_rate_m3s", f"input_{k}_flow"],
                            ["temperature_out", f"input_{k}_temperature"],
                        ],
                    }
                )
            # The mixer carries flow and temperature; the wellhead pressure is the same at
            # every producer (a boundary input), so the first one's goes on.
            connections += [
                {
                    "predecessor": mix,
                    "successor": sep_name,
                    "ports": [["flow", "flow_rate"], ["temperature", "temperature"]],
                },
                {
                    "predecessor": producers[members[0]],
                    "successor": sep_name,
                    "ports": [["pressure_out", "pressure"]],
                },
            ]
        else:
            connections.append(
                {
                    "predecessor": producers[members[0]],
                    "successor": sep_name,
                    "ports": [
                        ["flow_rate_m3s", "flow_rate"],
                        ["pressure_out", "pressure"],
                        ["temperature_out", "temperature"],
                    ],
                }
            )
        sep = copy.deepcopy(base["components"]["separator"])
        flow = sum(specs[i]["cap"] for i in members)
        # The train's brine mixes the gas of its doublets' aquifers, by their flows.
        ratio = sum(specs[i]["cap"] * specs[i]["rules"].gas_liquid_ratio for i in members) / max(
            flow, 1e-9
        )
        sep["parameters"].update(gas_water_ratio=round(ratio, 6), gas_density=gas_density)
        _size_unit(sep["parameters"], flow, TRAIN_DROP_BAR["separator"])
        if multi_train:
            sep["_description"] = f"Treatment train {t_i + 1}: separates the produced gas"
        components[sep_name] = sep
        filt = copy.deepcopy(base["components"]["filter_a"])
        _size_unit(filt["parameters"], flow, TRAIN_DROP_BAR["filter_a"])
        components[filt_name] = filt
        connections.append(
            {
                "predecessor": sep_name,
                "successor": filt_name,
                "ports": [
                    ["pressure_out", "pressure"],
                    ["temperature_out", "temperature"],
                    ["flow_rate", "flow_rate"],
                ],
            }
        )
        train_out.append(filt_name)
        separators.append(sep_name)

    # The exchanger on all the brine (through a header when there are several trains).
    cb = sum(sp["cap"] for sp in specs) / 3600 * rules.brine_density_kg_m3 * rules.brine_cp_j_kg_k
    approach = 5.0
    hot = sum(
        sp["cap"]
        * (rules.reservoir_temperature_c(sp["p_mid"]) - well_loss_k(sp["cap"], sp["p_mid"], rules))
        for sp in specs
    ) / sum(sp["cap"] for sp in specs)
    hot_out = min(hot - approach, rules.heat_supply_c)
    duty = cb * (hot_out - rules.heat_return_c)
    # GEMINI's exchanger takes one density and heat capacity for both sides; the brine's, with
    # the network's flow set to the same capacity rate (a balanced exchanger, as the plant
    # model's), so its effectiveness gives the plant model's duty exactly. Its defaults (1,050
    # kg/m3, 4,200 J/kg/K) would add 7 % to the brine's capacity rate.
    rho_cp = rules.brine_density_kg_m3 * rules.brine_cp_j_kg_k
    network_m3s = duty / (rho_cp * (hot_out - rules.heat_return_c))
    components["heat_exchanger"] = {
        "type": "heat_exchanger",
        "parameters": {
            "flow_resistance": 0,
            "flow_configuration": "counter",
            "heat_transfer_coefficient": round(duty / approach, 1),
            "fluid_density": rules.brine_density_kg_m3,
            "specific_heat": rules.brine_cp_j_kg_k,
        },
    }
    if multi_train:
        components["brine_header"] = {
            "type": "mixer",
            "_description": "The treatment trains' brine joins before the heat exchanger",
            "parameters": {"num_inputs": len(train_out)},
        }
        for k, f in enumerate(train_out):
            connections.append(
                {
                    "predecessor": f,
                    "successor": "brine_header",
                    "ports": [
                        ["flow_rate", f"input_{k}_flow"],
                        ["temperature_out", f"input_{k}_temperature"],
                    ],
                }
            )
        connections += [
            {
                "predecessor": "brine_header",
                "successor": "heat_exchanger",
                "ports": [["flow", "primary_flow_rate"], ["temperature", "primary_temperature_in"]],
            },
            {
                "predecessor": train_out[0],
                "successor": "heat_exchanger",
                "ports": [["pressure_out", "pressure_in"]],
            },
        ]
    else:
        connections.append(
            {
                "predecessor": train_out[0],
                "successor": "heat_exchanger",
                "ports": [
                    ["pressure_out", "pressure_in"],
                    ["temperature_out", "primary_temperature_in"],
                    ["flow_rate", "primary_flow_rate"],
                ],
            }
        )
    filt_b = copy.deepcopy(base["components"]["filter_b"])
    _size_unit(filt_b["parameters"], sum(sp["cap"] for sp in specs), TRAIN_DROP_BAR["filter_b"])
    components["filter_b"] = filt_b
    connections.append(
        {
            "predecessor": "heat_exchanger",
            "successor": "filter_b",
            "ports": [
                ["pressure_out", "pressure"],
                ["primary_temperature_out", "temperature"],
                ["primary_flow_rate", "flow_rate"],
            ],
        }
    )
    boundary += [
        {
            "component": "heat_exchanger",
            "key": "secondary_temperature_in",
            "value": rules.heat_return_c,
        },
        {"component": "heat_exchanger", "key": "secondary_flow_rate", "value": network_m3s},
    ]

    if boiler_mw > 0:
        # GEMINI's boiler on the separated gas: the gas is 80 % CH4 and 20 % CO2 by mole, so a
        # kilogram holds 0.593 kg of CH4 (LHV 50 MJ/kg): 29.7 MJ/kg. Its CO2 per GJ: the CH4's
        # 55 kg plus the 13.7 kg already in the gas. The gas the plant buys on top is the plant
        # model's (GEMINI's boiler burns one gas stream).
        ch4_mass = rules.gas_ch4_fraction * 16.04
        mix_mass = ch4_mass + rules.gas_co2_fraction * 44.01
        lhv_j_kg = ch4_mass / mix_mass * 50.0e6
        co2_kg_per_gj = (ch4_mass / mix_mass * 2.75 + (1 - ch4_mass / mix_mass)) / lhv_j_kg * 1e9
        components["boiler"] = {
            "type": "boiler",
            "_description": (
                f"GEMINI's boiler burning the separated gas; the design's boiler is {boiler_mw:g} "
                "MW and buys gas when the produced gas is short (the plant model)"
            ),
            "parameters": {
                "caloric_value": round(lhv_j_kg),
                "efficiency_factor": 0.95,
                "gas_emission_factor": round(co2_kg_per_gj, 1),
            },
        }
        if len(separators) > 1:
            components["gas_adder"] = {
                "type": "adder",
                "_description": "Sums the separated gas of every treatment train for the boiler",
                "parameters": {"num_inputs": len(separators)},
            }
            for k, sep_name in enumerate(separators):
                connections.append(
                    {
                        "predecessor": sep_name,
                        "successor": "gas_adder",
                        "ports": [["gas_mass_flow_rate", f"input_{k}"]],
                    }
                )
            connections.append(
                {
                    "predecessor": "gas_adder",
                    "successor": "boiler",
                    "ports": [["output", "gas_flow_rate"]],
                }
            )
        else:
            connections.append(
                {
                    "predecessor": separators[0],
                    "successor": "boiler",
                    "ports": [["gas_mass_flow_rate", "gas_flow_rate"]],
                }
            )
        connections.append(
            {
                "predecessor": "heat_exchanger",
                "successor": "boiler",
                "ports": [
                    ["secondary_temperature_out", "temperature_in"],
                    ["secondary_flow_rate", "water_flow_rate"],
                ],
            }
        )

    # Injectors: each doublet's share of the brine, split equally between its injectors.
    total = sum(sp["cap"] for sp in specs)
    injectors: List[Tuple[str, dict, float]] = []
    many_inj = sum(sp["injectors"] for sp in specs) > 1
    for i, sp in enumerate(specs):
        for j in range(sp["injectors"]):
            suffix = "" if sp["injectors"] == 1 else "ab"[j]
            iname = f"injector_well_{i + 1}{suffix}" if many_inj else "injector_well"
            inj = copy.deepcopy(base["components"]["injector_well"])
            inj["parameters"].update(well_config(sp["i_mid"], sp["rules"], sp["i_len"]))
            inj["parameters"]["injector_pump"] = {
                "efficiency_factor": rules.pump_efficiency,
                "electricity_emission_factor": GRID_KG_PER_KWH,
            }
            inj["_description"] = (
                f"Doublet {i + 1}'s injector{' ' + suffix.upper() if suffix else ''}: open over "
                f"{sp['i_len'] or h:g} m around {sp['i_mid']:,.0f} m TVD"
            )
            injectors.append((iname, inj, sp["cap"] / sp["injectors"] / total))
    if len(injectors) > 1:
        fractions = [round(f, 6) for _, _, f in injectors]
        fractions[-1] = round(1.0 - sum(fractions[:-1]), 6)  # exactly 1 (GEMINI checks)
        components["brine_splitter"] = {
            "type": "splitter",
            "_description": "The brine shared among the injectors (each doublet's share)",
            "parameters": {"split_fractions": fractions},
        }
        connections.append(
            {
                "predecessor": "filter_b",
                "successor": "brine_splitter",
                "ports": [["flow_rate_m3h", "input"]],
            }
        )
        for iname, inj, _ in injectors:  # after the splitter, in the order the brine flows
            components[iname] = inj
        for k, (iname, _, _) in enumerate(injectors):
            connections += [
                {
                    "predecessor": "brine_splitter",
                    "successor": iname,
                    "ports": [[f"output_{k}", "flow_rate"]],
                },
                {
                    "predecessor": "filter_b",
                    "successor": iname,
                    "ports": [
                        ["temperature_out", "wellhead_temperature"],
                        ["pressure_out_pa", "pressure_in"],
                    ],
                },
            ]
    else:
        components[injectors[0][0]] = injectors[0][1]
        connections.append(
            {
                "predecessor": "filter_b",
                "successor": injectors[0][0],
                "ports": [
                    ["flow_rate_m3h", "flow_rate"],
                    ["temperature_out", "wellhead_temperature"],
                    ["pressure_out_pa", "pressure_in"],
                ],
            }
        )

    # Listed in the order the brine flows (the canvas lays them out so); a train's mixer,
    # separator and filter stay together, train by train.
    order = (
        "producer_well",
        "brine_mixer",
        "separator",
        "filter_a",
        "brine_header",
        "heat_exchanger",
        "filter_b",
        "gas_adder",
        "boiler",
        "brine_splitter",
        "injector_well",
    )

    def rank(item) -> tuple:
        name = item[0]
        stem = next((o for o in order if name.startswith(o)), "")
        index = order.index(stem) if stem else len(order)
        if stem in ("brine_mixer", "separator", "filter_a"):
            tail = name.rsplit("_", 1)[-1]
            train = int(tail) if tail.isdigit() else 0
            return (1, train, index)
        return (index, 0, 0)

    components = dict(sorted(components.items(), key=rank))
    depths = sorted({sp["depth"] for sp in specs})
    where = " and ".join(f"{d:,.0f} m" for d in depths)
    return {
        "_description": (
            f"The brine loop of a design with {n} doublet{'s' if n > 1 else ''} at {where} "
            f"({len(trains)} treatment train{'s' if len(trains) > 1 else ''}, {len(injectors)} "
            f"injector{'s' if len(injectors) > 1 else ''}) as GEMINI simulates it (with the "
            "team's patches). GEMINI has no heat pump, chillers or absorption chiller: see the "
            "Plant view for the whole plant."
        ),
        "components": components,
        "boundary_inputs": boundary,
        "connections": connections,
    }
