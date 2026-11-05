"""Score the planner's reading of held-out messages against exact labels (cases.yaml).

Run: PYTHONPATH=src python hackathon/evals/planner/run_planner_eval.py [--device auto|cpu]
The reasoning model reads each message with the catalogue and the designs so far, as the agent
does; code checks the reading (``parameters.check``); this compares the result with the labels:
the steps (a trailing "answer" ignored), the changes (and per step), the failures' units and
days, the designs named, and that adversarial messages change nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from gemini_agent import engine, parameters  # noqa: E402
from gemini_agent.answer import load  # noqa: E402
from gemini_agent.contract import DesignBrief  # noqa: E402
from gemini_agent.llm import OllamaLLM  # noqa: E402
from gemini_agent.router import Router  # noqa: E402

DESIGNS = (
    "A1 1D-HP-EC-N1: best overall (the current design)\n"
    "A11 1D-HP-AB: cheapest\nA35 3D-HP-EC: lowest CO2\nA2 1D-HP-AB-N1: most reliable"
)


def read(deep, msg: str, designed: bool):
    b = DesignBrief()
    rules, prices = engine.rules_for(b), engine.prices_for(None, b)
    now = parameters.values_now(b, None, rules, prices)
    if designed:
        context = f"Current design: 1D-HP-EC-N1, 1 doublet\nDesigns so far:\n{DESIGNS}"
    else:
        context = "No design yet."
    msgs = [
        {"role": "system", "content": load(parameters.PROMPT)},
        {
            "role": "user",
            "content": f"Parameters:\n{parameters.catalogue_text(now)}\n\n{context}\n\n"
            f"Message: {msg}",
        },
    ]
    from gemini_agent.llm import LLMError

    try:
        raw, call = deep.structured("parameters", msgs, parameters.SCHEMA, 900)
    except LLMError as err:  # counted as a reading of nothing, as the agent treats it
        return parameters.Reading(ok=False), err.call
    return parameters.check(raw, msg, now, designed=designed), call


def close(a, b) -> bool:
    if isinstance(b, (int, float)) and isinstance(a, (int, float)):
        return abs(float(a) - float(b)) <= 0.01 * max(1.0, abs(float(b)))
    return str(a) == str(b)


def score(case: dict, r) -> list:
    """Return the labels the reading missed (empty: right)."""
    miss = []
    steps = [s.do for s in r.steps]
    while steps and steps[-1] == "answer":
        steps.pop()
    if "steps" in case and steps != case["steps"]:
        miss.append(f"steps {steps} != {case['steps']}")
    if "steps_any" in case and steps not in [[x for x in s if x != "answer"] for s in case["steps_any"]]:
        miss.append(f"steps {steps} not in {case['steps_any']}")
    for k, v in (case.get("changes") or {}).items():
        if k not in r.changes or not close(r.changes[k], v):
            miss.append(f"{k}={r.changes.get(k)} != {v}")
    if case.get("changes") == {} and r.changes:
        miss.append(f"changes read: {r.changes}")
    for k in case.get("changes_none") or []:
        if k in r.changes:
            miss.append(f"{k} read: {r.changes[k]}")
    for i, want in enumerate(case.get("step_changes") or []):
        got = r.changes_for(i) if len(r.steps) > 1 else r.changes
        for k, v in want.items():
            if k not in got or not close(got[k], v):
                miss.append(f"step {i}: {k}={got.get(k)} != {v}")
    for i, want in enumerate(case.get("failures") or []):
        if i >= len(r.failures):
            miss.append(f"failure {i} missing ({want['unit']})")
            continue
        f = r.failures[i]
        for k in ("unit", "first", "last", "days", "planned"):
            if k in want and getattr(f, k) != want[k]:
                miss.append(f"failure {i} {k} {getattr(f, k)!r} != {want[k]!r}")
    names = [d.lower() for d in r.designs]
    if case.get("designs_all") and not all(d.lower() in " ".join(names) for d in case["designs_all"]):
        miss.append(f"designs {r.designs} lack {case['designs_all']}")
    if case.get("designs_any") and not any(
        d.lower() in " ".join(names) for d in case["designs_any"]
    ):
        miss.append(f"designs {r.designs} have none of {case['designs_any']}")
    return miss


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--device", default="auto", choices=["auto", "cpu"])
    p.add_argument("--only", default=None)
    args = p.parse_args()
    cases = yaml.safe_load((Path(__file__).parent / "cases.yaml").read_text(encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    deep = Router(OllamaLLM(model="qwen3:1.7b", device=args.device), device=args.device).reasoning()
    right, rows = 0, []
    for c in cases:
        t = time.time()
        r, call = read(deep, c["msg"], c.get("ctx") == "designed")
        miss = score(c, r)
        right += not miss
        rows.append({"id": c["id"], "ok": not miss, "miss": miss, "s": round(time.time() - t, 2)})
        print(f"{c['id']:5} {'ok ' if not miss else 'NO '} {time.time() - t:5.1f}s  {'; '.join(miss)[:200]}")
    print(f"\n{right}/{len(cases)} right on {deep.model} ({args.device})")
    out = ROOT / "hackathon/evals/runs" / f"planner_{time.strftime('%Y%m%dT%H%M%S')}.json"
    out.write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
