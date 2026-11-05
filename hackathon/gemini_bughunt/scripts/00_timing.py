"""Timing of a single steady-state solve for both simulator examples, plus how
many times each component's calculate_output is executed per solve.

Run (from the exported development tree):
  PYTHONPATH=<tree>/src python 00_timing.py <tree>
"""

import collections
import json
import statistics
import sys
import time
from pathlib import Path

TREE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
sys.path.insert(0, str(TREE / "src"))

from gemini_simulator.project_loader import build_project  # noqa: E402


def count_calls(solver):
    counts = collections.Counter()
    for name, comp in solver.components.items():
        orig = comp.calculate_output

        def wrapped(u, x=None, _orig=orig, _name=name):
            counts[_name] += 1
            return _orig(u, x)

        comp.calculate_output = wrapped
    return counts


for proj in ("doublet_plant.json", "parallel_hex_plant.json"):
    path = TREE / "simulator_examples" / "projects" / proj
    project = json.loads(path.read_text())

    # build+run timing
    times_build, times_run = [], []
    for _ in range(20):
        t0 = time.perf_counter()
        solver = build_project(project)
        t1 = time.perf_counter()
        solver.run()
        t2 = time.perf_counter()
        times_build.append(t1 - t0)
        times_run.append(t2 - t1)

    solver = build_project(project)
    counts = count_calls(solver)
    solver.run()
    print(f"== {proj}")
    print(
        f"  build_project: median {statistics.median(times_build)*1e3:.2f} ms;"
        f" solver.run() (1 steady-state step): median {statistics.median(times_run)*1e3:.1f} ms,"
        f" min {min(times_run)*1e3:.1f} ms, max {max(times_run)*1e3:.1f} ms"
    )
    print("  calculate_output calls per run():", dict(counts))

    # Multi-step run with a time vector (boundary inputs constant -- no driver)
    solver = build_project(project)
    t0 = time.perf_counter()
    solver.run(time_vector=list(range(100)))
    dt = time.perf_counter() - t0
    print(f"  run(time_vector=range(100)): {dt:.2f} s total, {dt/100*1e3:.1f} ms/step;"
          f" history length={len(solver.history['producer_well']['output'])}")
