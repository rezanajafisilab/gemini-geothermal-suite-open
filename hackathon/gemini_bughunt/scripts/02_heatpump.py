"""HeatpumpBasic physics checks against a closed-form / bracketed reference that
solves the SAME equations the model claims to solve (eta-Carnot or eta-Lorenz COP
+ energy balance Qh = Qs + W), but picks the physical root.

Checks per operating point:
  * energy balance Q_cond = Q_evap + W with the reported outlet temperatures
  * reported Th_out within [Th_in, Th_out_target] and Ts_out within [Ts_min, Ts_in]
  * COP <= reversible (entropy-balance / Lorenz) COP for the reported streams
  * deviation of COP / heat / electricity vs. the reference solution

  PYTHONPATH=<tree>/src python 02_heatpump.py
"""

import itertools
import math
import warnings

import numpy as np
from scipy.optimize import brentq

from gemini_model.heatpump.heatpump_basic import HeatpumpBasic

warnings.filterwarnings("ignore")
CP, RHO = 4181.0, 1000.0
K = 273.15


def lmean(a, b):
    return a if abs(a - b) < 1e-9 else (a - b) / math.log(a / b)


def reference(mode, eta, th_t, th_in, ts_in, mh, ms, ts_min):
    """Physical solution of the model's own equations (temps in K)."""
    if mode == "carnot":
        cop = eta * th_t / (th_t - ts_in)
        qh = CP * mh * (th_t - th_in)
        qs = qh * (1 - 1 / cop)
        ts_out = ts_in - qs / (CP * ms)
        if ts_out >= ts_min:
            return cop, th_t, ts_out, qh, qh / cop
        # source-limited: Ts_out = Ts_min, find Th_out in (Th_in, Th_t]
        qs = CP * ms * (ts_in - ts_min)

        def f(th):
            c = eta * th / (th - ts_in)
            return CP * mh * (th - th_in) * (1 - 1 / c) - qs

        th = brentq(f, max(th_in, ts_in) + 1e-6, th_t)
        c = eta * th / (th - ts_in)
        q = CP * mh * (th - th_in)
        return c, th, ts_min, q, q / c
    else:  # lorenz
        qh = CP * mh * (th_t - th_in)
        thm = lmean(th_in, th_t)

        def g(ts_out):
            tsm = lmean(ts_in, ts_out)
            c = eta * thm / (thm - tsm)
            return CP * ms * (ts_in - ts_out) - qh * (1 - 1 / c)

        lo = ts_min
        if g(lo) <= 0:  # source-limited: Ts_out = Ts_min, solve Th_out
            qs = CP * ms * (ts_in - ts_min)
            tsm = lmean(ts_in, ts_min)

            def f(th):
                c = eta * lmean(th_in, th) / (lmean(th_in, th) - tsm)
                return CP * mh * (th - th_in) * (1 - 1 / c) - qs

            th = brentq(f, th_in + 1e-6, th_t)
            c = eta * lmean(th_in, th) / (lmean(th_in, th) - tsm)
            q = CP * mh * (th - th_in)
            return c, th, ts_min, q, q / c
        ts_out = brentq(g, lo, ts_in - 1e-9)
        c = eta * thm / (thm - lmean(ts_in, ts_out))
        return c, th_t, ts_out, qh, qh / c


def model(mode, eta, th_t_c, th_in_c, ts_in_c, qh_m3h, qs_m3h, ts_min_c):
    hp = HeatpumpBasic()
    hp.update_parameters({"mode": mode, "Th_out_target": th_t_c, "Ts_in_minimum": ts_min_c,
                          "eta_carnot": eta, "eta_lorenz": eta})
    hp.calculate_output({"Th_in": th_in_c, "Ts_in": ts_in_c, "hot_flow_rate": qh_m3h / 3600,
                         "source_flow_rate": qs_m3h / 3600})
    return hp.get_output()


rows = []
for mode, (th_in, th_t), ts_in, (qh, qs) in itertools.product(
    ("carnot", "lorenz"),
    ((40.0, 70.0), (50.0, 80.0), (30.0, 45.0), (55.0, 90.0)),
    (12.0, 15.0, 20.0, 30.0, 40.0),          # source (e.g. geothermal return / aquifer / BHE)
    ((100.0, 100.0), (100.0, 300.0), (50.0, 200.0), (150.0, 60.0)),
):
    eta, ts_min = 0.5, 10.0
    mh, ms = qh / 3600 * RHO, qs / 3600 * RHO
    try:
        ref = reference(mode, eta, th_t + K, th_in + K, ts_in + K, mh, ms, ts_min + K)
    except Exception as e:  # noqa
        ref = None
    try:
        y = model(mode, eta, th_t, th_in, ts_in, qh, qs, ts_min)
    except Exception as e:  # noqa
        rows.append((mode, th_in, th_t, ts_in, qh, qs, "EXC " + repr(e)))
        continue
    q_cond = CP * mh * (y["Th_out"] - th_in)
    q_evap = CP * ms * (ts_in - y["Ts_out"])
    bal = (q_cond - q_evap - y["power_el"]) / max(abs(q_cond), 1)
    th_ok = th_in - 1e-3 <= y["Th_out"] <= th_t + 1e-3
    ts_ok = ts_min - 1e-3 <= y["Ts_out"] <= ts_in + 1e-3
    cop_rev = None
    if y["Th_out"] > th_in and y["Ts_out"] < ts_in:
        thm, tsm = lmean(th_in + K, y["Th_out"] + K), lmean(ts_in + K, y["Ts_out"] + K)
        cop_rev = thm / (thm - tsm) if thm > tsm else math.inf
    dW = (y["power_el"] - ref[4]) / ref[4] if ref else float("nan")
    dQ = (y["power_th"] - ref[3]) / ref[3] if ref else float("nan")
    rows.append((mode, th_in, th_t, ts_in, qh, qs, y["COP"], ref[0] if ref else float("nan"),
                 y["Th_out"], ref[1] - K if ref else float("nan"), y["Ts_out"],
                 y["power_th"] / 1e6, y["power_el"] / 1e6, bal, th_ok and ts_ok,
                 cop_rev, dQ, dW))

print("columns: mode Th_in Th_target Ts_in Qh Qs | COP_model COP_ref | Th_out_model Th_out_ref |"
      " Ts_out_model | Q_MW W_MW | balance_err | temps_in_range | COP_rev | dQ_rel dW_rel")
nbad = 0
for r in rows:
    if isinstance(r[6], str):
        nbad += 1
        print("FAIL", r)
        continue
    bad = (abs(r[13]) > 0.01) or (not r[14]) or (abs(r[16]) > 0.10) or (abs(r[17]) > 0.10)
    nbad += bad
    tag = "BAD " if bad else "ok  "
    print(tag + " ".join(
        f"{v:.3g}" if isinstance(v, float) else str(v) for v in r))
print(f"\n{len(rows)} cases, {nbad} flagged (balance err >1%, temps out of range, or >10% off reference)")
