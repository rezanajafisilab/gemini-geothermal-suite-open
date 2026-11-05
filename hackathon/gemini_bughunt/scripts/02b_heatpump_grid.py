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



# Coordinator grid: Th_in 30-60 C, Th_out_target 60-90 C, Ts_in 15-60 C, flows 0.005-0.1 m3/s
import collections
stats = collections.defaultdict(list)
nonphys = collections.Counter()
exc = collections.Counter()
ncase = collections.Counter()
examples = {}
for mode in ("carnot", "lorenz"):
    for th_in in (30.0, 40.0, 50.0, 60.0):
        for th_t in (60.0, 70.0, 80.0, 90.0):
            if th_t <= th_in:
                continue
            for ts_in in (15.0, 25.0, 35.0, 45.0, 55.0, 60.0):
                for qh in (0.005, 0.02, 0.05, 0.1):
                    for qs in (0.005, 0.02, 0.05, 0.1):
                        ncase[mode] += 1
                        mh, ms = qh * RHO, qs * RHO
                        try:
                            ref = reference(mode, 0.5, th_t + K, th_in + K, ts_in + K, mh, ms, 10.0 + K)
                        except Exception:
                            ref = None
                        try:
                            y = model(mode, 0.5, th_t, th_in, ts_in, qh * 3600, qs * 3600, 10.0)
                        except Exception as e:
                            exc[(mode, type(e).__name__)] += 1
                            continue
                        q_cond = CP * mh * (y["Th_out"] - th_in)
                        q_evap = CP * ms * (ts_in - y["Ts_out"])
                        bal = abs(q_cond - q_evap - y["power_el"]) / max(abs(q_cond), 1)
                        thK, tsK = y["Th_out"] + K, y["Ts_out"] + K
                        carnot = thK / (thK - tsK) if thK > tsK else float("inf")
                        flags = []
                        if y["COP"] <= 0: flags.append("COP<=0")
                        if y["COP"] > carnot: flags.append("COP>Carnot(Th_out,Ts_out)")
                        if y["Th_out"] > th_in and y["Ts_out"] < ts_in:
                            thm_, tsm_ = lmean(th_in + K, thK), lmean(ts_in + K, tsK)
                            if thm_ > tsm_ and y["COP"] > thm_ / (thm_ - tsm_):
                                flags.append("COP>reversible(log-mean) bound")
                        if bal > 0.01: flags.append("balance>1%")
                        if y["Ts_out"] < 10.0 - 1e-3: flags.append("Ts_out<Ts_min")
                        if y["Th_out"] > th_t + 1e-3: flags.append("Th_out>target")
                        for f in flags:
                            nonphys[(mode, f)] += 1
                        if ref is not None:
                            limited = ref[2] - K <= 10.0 + 1e-6
                            key = (mode, "source-limited" if limited else "unconstrained")
                            ncase[key] += 1
                            for nm, a, b in (("COP", y["COP"], ref[0]), ("Q", y["power_th"], ref[3]), ("W", y["power_el"], ref[4])):
                                stats[key + (nm,)].append(abs(a - b) / abs(b))
                            if flags and key not in examples:
                                examples[key] = (th_in, th_t, ts_in, qh, qs, y["COP"], ref[0], y["Th_out"], ref[1] - K, y["power_th"]/1e6, ref[3]/1e6, y["power_el"]/1e6, ref[4]/1e6)
print("cases:", dict(ncase))
print("exceptions:", dict(exc))
print("non-physical flags:", dict(nonphys))
for k, v in sorted(stats.items()):
    import numpy as _np
    v = _np.array(v)
    print(f"{k}: n={len(v)} max_rel_err={v.max():.3g} median={_np.median(v):.3g} frac>10%={(v>0.1).mean():.2f}")
print("example per regime (Th_in, Th_t, Ts_in, qh, qs, COP_model, COP_ref, Th_out_model, Th_out_ref, Q_model MW, Q_ref MW, W_model MW, W_ref MW):")
for k, v in examples.items():
    print(" ", k, tuple(round(x, 3) for x in v))
