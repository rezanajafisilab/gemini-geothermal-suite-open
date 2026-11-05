"""Write the UI's offline fixtures (frontend/src/fixtures/*.json) from the real backend.

A scripted conversation (no model needed) confirms the inputs, designs the challenge plant,
asks two what-ifs (a colder reservoir with a smaller boiler, which breaks a cap, and a 50 °C
heating return) and makes two designs on the tabs (U1: two doublets on one treatment train, equal
shares; U2: two doublets built differently, base-load dispatch); the workbench, a sensitivity
run, two GEMINI project runs, the trace and the evidence are then saved as the tabs' fixtures,
and four chat streams (``confirm``, ``confirm-run``, ``whatif-return``, ``build-doublets``) as
SSE. Every number is the engine's. The inputs card's form has three streams of its own
(``edit_fixtures``: the card, a change refused, the changes and stop dates run).

    PYTHONPATH=src python hackathon/scripts/make_ui_fixtures.py
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from gemini_agent import Agent, Session, engine, parameters, workbench  # noqa: E402
from gemini_agent.llm import ScriptedLLM  # noqa: E402
from gemini_agent.reporter import RUN_OPTION  # noqa: E402
from gemini_agent.tools import gemini  # noqa: E402
from unit_test.gemini_agent.test_agent import fake_intake  # noqa: E402

OUT = ROOT / "frontend" / "src" / "fixtures"
NOTE = "Made by hackathon/scripts/make_ui_fixtures.py from the real backend (scripted model)."


def scripted(purpose, messages):
    """Answer as ``fake_intake`` does, and read a boiler's size too ("the boiler is 20 MW")."""
    out = fake_intake(purpose, messages)
    if purpose == "parameters":
        said = messages[-1]["content"].split("Message: ", 1)[-1]
        m = re.search(r"boiler (?:is |at |of )?(\d+) MW", said, re.I)
        if m:
            out["changes"].append(
                {"key": "boiler_mw", "value": float(m.group(1)), "quote": m.group(0)}
            )
    return out


def save(name: str, data: dict) -> None:
    """Write one fixture with its provenance note first."""
    path = OUT / name
    path.write_text(json.dumps({"_fixture": NOTE, **data}, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} kB)")


def save_sse(name: str, events) -> None:
    """Write one chat stream as server-sent events, as the server sends them."""
    path = OUT / f"{name}.sse"
    path.write_text("".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events))
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} kB)")


def main() -> None:
    """Run the conversation and save every fixture."""
    with tempfile.TemporaryDirectory() as traces:
        agent = Agent(ScriptedLLM(scripted), trace_dir=traces)
        s = Session(thread_id="fixture")
        # At the known aquifer, as recorded since 30 Oct: the tabs' tests are about layouts and
        # cards (a heat pump, its sizes), not the depth (the edit fixtures keep the default).
        s.brief = s.brief.model_copy(update={"doublet_depths_m": [2500.0]})
        save_sse(
            "confirm",
            list(agent.run(s, "Design a geothermal heating and cooling system for this district.")),
        )
        save_sse("confirm-run", list(agent.run(s, answers={"confirm": RUN_OPTION})))
        # A what-if that breaks a cap, so the fixtures show a failing design too. The pick is a
        # reliable plan (its boiler alone covers the peak), so a colder reservoir alone never
        # does: 10 K colder with the largest boiler that then falls short.
        colder = 10
        rules = engine.rules_for(s.chosen.brief)
        under = parameters.apply(s.chosen.brief, {"reservoir_change_k": -colder})
        boiler = next(
            (
                mw
                for mw in (25, 20, 15, 10, 5)
                if engine.evaluate(
                    parameters.change_design(
                        s.chosen.alternative, {"boiler_mw": mw}, rules.reservoir_depth_m
                    ),
                    under,
                    s.assumptions,
                    role="what_if",
                ).year.violations
            ),
            5,
        )
        list(
            agent.run(
                s,
                f"What happens to the recommended design if the reservoir is {colder} C colder "
                f"and the boiler is {boiler} MW?",
            )
        )
        save_sse(
            "whatif-return",
            list(
                agent.run(
                    s,
                    "What happens to the design if we lower the heating return temperature to "
                    "50 °C?",
                )
            ),
        )
        chosen = workbench.design_id(s.chosen)
        # The pick has one doublet: U1 has two, identical, on one treatment train in equal shares
        # (the Plant view's shared lane and brine mixer), U2 two built differently.
        workbench.create_design(s, chosen, {"n_doublets": 2}, "Two doublets")
        built = workbench.create_design(
            s,
            chosen,
            {
                "doublets": [
                    {"depth_m": 2500, "injectors": 2, "train": 0},
                    {"depth_m": 2500, "producer_open": "lower", "train": 1},
                ],
                "dispatch": "base",
            },
            "Two doublets built differently",
        )
        wb = workbench.workbench(s)
        save("workbench.json", wb)
        params = workbench.sensitivity_parameters()
        picked = [
            {"key": k, "low": lo, "high": hi}
            for k, lo, hi in (
                ("heat_return", 45, 70),
                ("reservoir_temp", -10, 5),
                ("electricity_price", 120, 220),
                ("gas_price", 25, 70),
                ("capex", 0.8, 1.3),
            )
        ]
        result = workbench.sensitivity(
            s, chosen, picked, ["lcoh", "co2_saving_pct", "npv_meur"], samples=60
        )
        save("sensitivity.json", {**params, "result": result})
        alt = s.chosen.alternative
        project = gemini.plant_project(
            alt.doublets, engine.rules_for(s.chosen.brief), alt.sizes_mw.get("boiler", 0.0)
        )
        save("gemini-run.json", workbench.run_gemini(project, compare_released=True))
        save(
            "gemini-run-trains.json",
            workbench.run_gemini(built["graph"]["gemini_project"], compare_released=False),
        )
        save("trace.json", {"runs": workbench.trace(Path(traces), "fixture")})
        b = Session(thread_id="fixture-build")
        # How doublets are built, at the known aquifer (since 2 Nov the default also tries
        # 3,000 and 3,500 m; the canvas tests are about injectors and trains, not depth).
        b.brief = b.brief.model_copy(update={"doublet_depths_m": [2500.0]})
        from gemini_agent.agent import project_fingerprint

        b.confirmed[b.project.id] = project_fingerprint(b.project)
        save_sse(
            "build-doublets",
            list(
                agent.run(
                    b,
                    "Design two doublets: the first with two injectors, the second with its own "
                    "separator and filters.",
                )
            ),
        )
    save("evidence.json", workbench.evidence())
    edit_fixtures()


def edit_fixtures() -> None:
    """Save the inputs card's form: the card, a change out of range refused, changes run."""
    s = Session(thread_id="fixture-edit")
    agent = Agent(ScriptedLLM(scripted))
    save_sse(
        "confirm-edit",
        list(agent.run(s, "Design a geothermal heating and cooling system for this district.")),
    )
    refused = {
        "confirm": RUN_OPTION,
        "changes": json.dumps({"heat_return_c": 50, "gradient_c_per_km": 90}),
        # 20 days: short of the 35 the cap leaves, so the cap is relaxed to 345 (2 Nov); the
        # gradient out of range is what is refused.
        "doublet_stops": json.dumps([[[180, 199]]]),
    }
    save_sse("confirm-refused", list(agent.run(s, answers=refused)))
    applied = {
        "confirm": RUN_OPTION,
        "changes": json.dumps({"heat_return_c": 50}),
        "doublet_stops": json.dumps([[[180, 199], [230, 244]]]),  # 20 + 15 days, doublet 1
    }
    save_sse("confirm-applied", list(agent.run(s, answers=applied)))


if __name__ == "__main__":
    main()
