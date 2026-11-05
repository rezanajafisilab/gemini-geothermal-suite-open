"""Two real Dutch doublets, run through our doublet model and set against their published figures.

The challenge district has no measurements to check against. These projects do, in public
documents on NLOG (the Dutch oil and gas portal):

- **Trias Westland, second doublet** (NLW-GT-03/04, Westland greenhouses): PanTerra
  Geoconsultants, "Geological report TW OK II" (G1363b, 2020), the basis of its SDE+ grant.
  Delft Sandstone (Lower Cretaceous), top 2,306 m and base 2,366 m TVDss at NLW-GT-03, 58-66 m
  gross at a net-to-gross of 0.87-0.96; permeability 450 / 650 / 1,000 mD (P90 / P50 / P10);
  140,000 ppm NaCl; T = 10 + 0.033 × depth (87 °C produced at NLW-GT-01, mid-reservoir about
  2,350 m); injection at 31 °C; at most 525 m3/h (the tubing). DoubletCalc 1.4.3 gives
  25 / 32 / 41 MW and a COP of 13 / 14 / 15 with the pumps set to 110 bar.
- **Haagse Aardwarmte Leyweg** (HAG-GT-01/02, The Hague's district heating): the ministry's
  approval of the production plan (DGKE-WO / V-109, 2 December 2020). Delft Sandstone at about
  2 km; about 79 °C produced; injected at 45 °C in winter (57 °C spring and autumn, 63 °C in
  summer), at most 34 K cooler; at most 165 m3/h; about 6 bar of injection pressure at
  reservoir depth for 165 m3/h; about 1 Nm3 of gas per m3 of water.

What is checked: the wellhead temperature our well model gives (its gradient and the heat lost
up the well), and the heat at the published flow and injection temperature, with the brine's
heat capacity and density for its salinity (Sharqawy, Lienhard & Zubair 2010). The pumps are
compared where the document gives them; DoubletCalc's COP comes from a pump pressure set at
110 bar, not from the flow's need, so it is shown beside ours, not as a pass or fail.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional


def brine_cp(salinity_g_kg: float, t_c: float) -> float:
    """Return seawater-type brine's heat capacity, J/(kg K) (Sharqawy et al. 2010, eq. 9)."""
    s, t = salinity_g_kg, t_c + 273.15
    a = 5.328 - 9.76e-2 * s + 4.04e-4 * s**2
    b = -6.913e-3 + 7.351e-4 * s - 3.15e-6 * s**2
    c = 9.6e-6 - 1.927e-6 * s + 8.23e-9 * s**2
    d = 2.5e-9 + 1.666e-9 * s - 7.125e-12 * s**2
    return 1000.0 * (a + b * t + c * t**2 + d * t**3)


def brine_density(salinity_g_kg: float, t_c: float) -> float:
    """Return seawater-type brine's density, kg/m3 (Sharqawy et al. 2010, eq. 8)."""
    s, t = salinity_g_kg / 1000.0, t_c
    rho_w = 9.999e2 + 2.034e-2 * t - 6.162e-3 * t**2 + 2.261e-5 * t**3 - 4.657e-8 * t**4
    return rho_w + s * (
        8.020e2 - 2.001 * t + 1.677e-2 * t**2 - 3.060e-5 * t**3 - 1.613e-5 * s * t**2
    )


PROJECTS: Dict[str, dict] = {
    "trias_westland": {
        "name": "Trias Westland, second doublet (NLW-GT-03/04)",
        "source": (
            "PanTerra Geoconsultants, Geological report TW OK II (G1363b), 2020, on NLOG "
            "(nlog.nl, 200213_appendix_1_-_geologisch_rapport_gelakt.pdf)"
        ),
        "top_m": 2305.9,
        "base_m": 2366.3,
        "net_m": 64.0 * 0.92,
        "permeability_md": {"P90": 450.0, "P50": 650.0, "P10": 1000.0},
        "salinity_g_kg": 140.0,
        "surface_c": 10.0,
        "gradient_c_per_km": 33.0,
        "flow_m3h": 525.0,
        "injection_c": 31.0,
        "reported": {
            "produced_c": 87.0,
            "power_mw": {"P90": 25.0, "P50": 32.0, "P10": 41.0},
            "cop": {"P90": 13.0, "P50": 14.0, "P10": 15.0},
            "note": "DoubletCalc 1.4.3, pumps at 110 bar",
        },
    },
    "hal_leyweg": {
        "name": "Haagse Aardwarmte Leyweg (HAG-GT-01/02)",
        "source": (
            "Ministry of EZK, instemmingsbesluit winningsplan Haagse Aardwarmte Leyweg "
            "(DGKE-WO / V-109), 2 December 2020, on NLOG"
        ),
        "top_m": 2000.0,
        "base_m": 2050.0,
        "net_m": 50.0,
        "permeability_md": {"P50": 1000.0},
        "salinity_g_kg": 120.0,
        "surface_c": 10.0,
        # 79 °C produced from about 2 km: the gradient that gives it with our well loss.
        "gradient_c_per_km": 35.0,
        "flow_m3h": 165.0,
        "injection_c": 45.0,
        "reported": {
            "produced_c": 79.0,
            "max_cooling_k": 34.0,
            "injection_bar": 6.0,
            "note": "the decision gives no thermal power; its flow and cooling imply one",
        },
        "assumed": (
            'thickness 50 m and 1,000 mD ("the permeability of the Delft Sandstone is high"); '
            "120 g/kg salinity (as at nearby Delft doublets); the gradient set so the reservoir "
            "is about 80 °C at 2 km"
        ),
        # Set to match, so not a check.
        "calibrated": ["produced_c"],
    },
}


def run(key: str, case: str = "P50") -> dict:
    """Return our doublet model's figures for a project against its published ones."""
    from dioscuri_plant import Rules
    from gemini_agent.tools.gemini import doublet_point

    p = PROJECTS[key]
    mid = (p["top_m"] + p["base_m"]) / 2.0
    perm = p["permeability_md"].get(case) or next(iter(p["permeability_md"].values()))
    t_mean = (p["surface_c"] + p["gradient_c_per_km"] * mid / 1000.0 + p["injection_c"]) / 2.0
    rho = brine_density(p["salinity_g_kg"], t_mean)
    cp = brine_cp(p["salinity_g_kg"], t_mean)
    rules = replace(
        Rules(),
        reservoir_depth_m=mid,
        reservoir_thickness_m=p["net_m"],
        permeability_md=perm,
        gradient_c_per_km=p["gradient_c_per_km"],
        surface_temperature_c=p["surface_c"],
        flow_max_m3h=max(300.0, p["flow_m3h"]),
        reservoir_pressure_bar=rho * 9.81 * mid / 1e5,
        brine_density_kg_m3=rho,
        brine_cp_j_kg_k=cp,
    )
    pt = doublet_point(p["flow_m3h"], mid, rules)
    wellhead = float(pt["wellhead_c"])
    power = p["flow_m3h"] / 3600.0 * rho * cp * (wellhead - p["injection_c"]) / 1e6
    pumps = float(pt.get("esp_mw", 0.0)) + float(pt.get("injector_pump_mw", 0.0))
    rep = p["reported"]
    calibrated = set(p.get("calibrated") or [])
    rows: List[dict] = [
        _row(
            "Brine at the wellhead",
            "°C",
            wellhead,
            rep.get("produced_c"),
            tol_abs=None if "produced_c" in calibrated else 2.0,
        )
    ]
    if "produced_c" in calibrated:
        rows[0]["note"] = "the gradient was set to give this: not a check"
    if "power_mw" in rep:
        rows.append(_row("Heat at the published flow", "MW", power, rep["power_mw"].get(case), 0.1))
    else:
        implied = (
            p["flow_m3h"] / 3600.0 * rho * cp * rep["max_cooling_k"] / 1e6
            if rep.get("max_cooling_k")
            else None
        )
        heat = _row("Heat at the published flow", "MW", power, implied)
        heat["note"] = "the decision gives no power: theirs is its flow over its 34 K, not a check"
        rows.append(heat)
    rows.append(_row("Pumps (ESP and injection)", "MW", pumps, None))
    if "cop" in rep:
        cop = _row("COP (heat / pumps)", "", power / pumps if pumps else 0.0, rep["cop"].get(case))
        cop["note"] = "theirs with the pumps set to 110 bar, ours with what the flow needs"
        rows.append(cop)
    if rep.get("injection_bar") is not None:
        # The overpressure at reservoir depth that pushes the flow into the rock: the flow over
        # the well's index (the decision's "injectiedruk op reservoirdiepte", about 6 bar).
        pi = float(pt.get("pi_m3h_per_bar") or 0.0)
        over = _row(
            "Overpressure to inject the flow, at reservoir depth",
            "bar",
            p["flow_m3h"] / pi if pi else 0.0,
            rep["injection_bar"],
        )
        over["note"] = "with the assumed rock (" + p.get("assumed", "").split(";")[0] + ")"
        rows.append(over)
    return {
        "key": key,
        "name": p["name"],
        "source": p["source"],
        "case": case,
        "assumed": p.get("assumed", ""),
        "note": rep.get("note", ""),
        "inputs": {
            "mid_depth_m": round(mid, 0),
            "net_m": round(p["net_m"], 1),
            "permeability_md": perm,
            "flow_m3h": p["flow_m3h"],
            "injection_c": p["injection_c"],
            "brine_density_kg_m3": round(rho, 0),
            "brine_cp_j_kg_k": round(cp, 0),
        },
        "rows": rows,
    }


def _row(
    what: str, unit: str, ours: float, theirs: Optional[float], tol: float = 0.0, tol_abs=None
) -> dict:
    """Return one comparison; ``agree`` when within the tolerance (None: not judged)."""
    agree = None
    if theirs is not None and tol_abs is not None:
        agree = abs(ours - theirs) <= tol_abs
    elif theirs is not None and tol:
        agree = abs(ours - theirs) <= tol * abs(theirs)
    return {
        "note": "",
        "quantity": what,
        "unit": unit,
        "ours": round(ours, 2),
        "theirs": None if theirs is None else round(theirs, 2),
        "diff_pct": None if not theirs else round((ours - theirs) / theirs * 100, 1),
        "agree": agree,
    }


# A cooling check (3 Nov): no Dutch deep-geothermal project supplies cold with published
# figures; the best documented geothermal absorption chiller is Oregon Tech's campus in Klamath
# Falls (P. J. Lienau, "OIT geothermal system improvements", Geo-Heat Center Quarterly Bulletin
# 17(3), August 1996): 541 kW (154 tons) of cooling from 38 L/s (600 gpm) of 89 °C geothermal
# water. Its return temperature and COP are not given, so this checks the brine our absorption
# chiller takes, not its output.
OIT = {
    "name": "Oregon Tech campus, geothermal absorption chiller (Klamath Falls, OR)",
    "source": (
        "P. J. Lienau, OIT geothermal system improvements, Geo-Heat Center Quarterly Bulletin "
        "17(3), August 1996 (OSTI 508612): 541 kW of cooling from 38 L/s of 89 °C water"
    ),
    "cold_kw": 541.0,
    "flow_l_s": 38.0,
    "supply_c": 89.0,
}


def cooling_check() -> dict:
    """Return Oregon Tech's absorption chiller set against our absorption model's brine."""
    from dioscuri_plant import Components

    comp = Components()
    p = OIT
    heat_kw = p["cold_kw"] / comp.absorption_cop
    cp = 4.19  # kJ/(kg K), fresh geothermal water at about 85 °C
    ours_flow = heat_kw / (cp * comp.absorption_brine_drop_k)  # L/s at our drop
    their_drop = heat_kw / (cp * p["flow_l_s"])  # K at their flow, if the COP were ours
    rows = [
        _row("Heat the generator takes for 541 kW of cold", "kW", heat_kw, None),
        _row("Water through the generator", "L/s", ours_flow, p["flow_l_s"]),
        _row("Water cooled in the generator", "K", comp.absorption_brine_drop_k, their_drop),
    ]
    rows[0]["note"] = f"at our COP of {comp.absorption_cop:g} (theirs not given)"
    rows[1]["note"] = "ours at the 15 K drop the plant model assumes; theirs the design flow"
    rows[2]["note"] = (
        "theirs worked out from their flow at our COP: single-effect machines run on a few "
        "kelvin, so our 15 K takes a third of the water (a larger generator, or units in series)"
    )
    return {
        "key": "oit_absorption",
        "name": p["name"],
        "source": p["source"],
        "case": "",
        "assumed": "",
        "note": "the bulletin gives no return temperature or COP: not a check of the cold made",
        "inputs": {"cold_kw": p["cold_kw"], "flow_l_s": p["flow_l_s"], "supply_c": p["supply_c"]},
        "rows": rows,
    }


def all_projects() -> List[dict]:
    """Return every project's check.

    Trias Westland at its P50 only: DoubletCalc's P90 and P10 change the flow (its pumps are
    set to 110 bar, so a tighter rock gives less brine), while this check holds the published
    525 m3/h, so only the P50 (the flow at the tubing's limit) compares like for like.
    """
    return [run("trias_westland", "P50"), run("hal_leyweg"), cooling_check()]
