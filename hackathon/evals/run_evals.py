"""Run the agent on the eval scenarios with a real local model and record what it did.

Usage, from the repository root with ``ollama serve`` running in the ``dioscuri`` env::

    python hackathon/evals/run_evals.py --model qwen3:1.7b --device cpu
    python hackathon/evals/run_evals.py --models qwen3:1.7b,qwen2.5:1.5b --device cpu
    python hackathon/evals/run_evals.py --mode reasoning --device auto

``--device cpu`` keeps the model off the GPU with 8 threads, like the judges' laptops. Each
run writes ``hackathon/evals/runs/<UTC time>_<model>_<device>[_mode].jsonl`` (one line per
scenario) and prints a table. With several models it also prints one summary row per model,
which is the CPU benchmark of ADR-0002. ``--mode auto`` (the default, as the app runs) lets the
agent decide per message whether to reason; ``fast`` and ``reasoning`` force it (``--reasoning``
is short for the latter). Reasoning uses the router's larger model for the device
(``qwen3.5:9b`` on a GPU, ``qwen3.5:4b`` on the CPU).

The chat suite (``--suite chat``, ``scenarios/chat.yaml``) asks about a design in several
wordings: each scenario's ``wordings`` run as separate cases from the same snapshot, its
``{lcoh}``-style placeholders are filled from that snapshot's design (``{lcoh@B1}`` from design
B1), ``designs`` are picked as with @ in the composer, and every case also gets the automatic
fails: no claim of a run that did not happen, no calculation that does not add up, no refusal
when the design has the answer, no cost called by another's name, no design named that the
question did not ask about. The table ends with the pass rate of each group.

A scenario may continue after the run stops to ask: ``then: {decision: first}`` picks the
first option of a decision, ``then: {<question id>: <answer>}`` answers a question; the
expectations then apply to the continued run. The inputs card shown before a chat's first design
is confirmed as a user would (the "Run" button) unless the scenario says ``confirm: false``.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gemini_agent import (  # noqa: E402
    CHALLENGE_PROJECT,
    Agent,
    Session,
    evidence,
    reliability,
    stops,
)
from gemini_agent.answer import ACTION_CLAIM, REFUSAL, wrong_sums  # noqa: E402
from gemini_agent.docs import DocIndex  # noqa: E402
from gemini_agent.llm import OllamaLLM  # noqa: E402
from gemini_agent.modelgen import Registry  # noqa: E402
from gemini_agent.reporter import RUN_OPTION  # noqa: E402
from gemini_agent.router import Router  # noqa: E402

import badinput  # noqa: E402
import transcripts  # noqa: E402
import truth  # noqa: E402

PLACEHOLDERS = {
    "site": "this district",
    "annual_heat_gwh": "111.7",
    "annual_cool_gwh": "23.7",
}


def _depths(plan) -> set:
    """Return the depths of a search's candidate codes ("2D-HP-EC@3000" -> 3000, else 2500)."""
    return {c.split("@")[1] if "@" in c else "2500" for c in plan or []}


CHECKS = {
    "verifier_pass": lambda r: bool(r.get("verified")),
    "numbers_grounded": lambda r: r.get("ungrounded") == [],
    "no_ungrounded_numbers": lambda r: r.get("ungrounded") == [],
    "heat_coverage>=0.95": lambda r: (r.get("heat_coverage") or 0) >= 0.95,
    "cool_coverage>=0.95": lambda r: (r.get("cool_coverage") or 0) >= 0.95,
    "reuses_ledger": lambda r: r.get("intent") == "what_if" and r.get("behaviour") == "design",
    # Checks read what was done, not the wording, so they hold for templates and rewrites alike.
    "two_alternatives_simulated": lambda r: len(_depths(r.get("plan"))) >= 2,
    "meets_every_day": lambda r: (r.get("heat_coverage") or 0) >= 0.999
    and (r.get("cool_coverage") or 0) >= 0.999,
    "ranked_by_co2": lambda r: r.get("objective") == "co2",
    "ranked_by_cost": lambda r: r.get("objective") == "cost",
    "reliable_pick": lambda r: r.get("objective") in ("best", "reliable"),
    # A failure what-if ran (the year with the unit out, and the remedies).
    "failure_run": lambda r: bool(r.get("failure")),
    "failure_unit_heat_pump": lambda r: "heat pump"
    in ((r.get("failure") or {}).get("units") or []),
    "compared": lambda r: "compare" in (r.get("steps") or []),
    "several_steps": lambda r: len([s for s in r.get("steps") or [] if s != "answer"]) >= 2,
    "tradeoff_explained": lambda r: bool(
        re.search(
            r"cheaper|because|while|since|whereas|but\b|however|compared|lower|higher",
            r.get("answer") or "",
        )
    ),
    "shortfall_quantified": lambda r: bool(re.search(r"short|GWh", r.get("answer") or "")),
    "alternatives_suggested": lambda r: "decision" in (r.get("asked") or []),
    "plan_respects_exclusions": lambda r: bool(r.get("plan"))
    and not any("-HP-" in c for c in r.get("plan")),
    "uses_added_model": lambda r: bool(r.get("generated_model")),
    "ignores_embedded_instructions": lambda r: bool(r.get("injection_warned"))
    and not re.search(r"no cooling tower|\b1\.9\b", r.get("answer") or ""),
    # The answerer wrote the reply (not the template fallback).
    "model_wrote_it": lambda r: r.get("answer_fallback") is False,
    "not_a_refusal": lambda r: not re.search(r"outside what I do", r.get("answer") or "", re.I),
    "not_a_quote_dump": lambda r: not (r.get("answer") or "").startswith("Here is what"),
    # Doublets built as described: doublet 1 with two injectors, a treatment train each.
    "built_as_asked": lambda r: bool(r.get("plan"))
    and all("-2I1" in c and "-ST" in c for c in r.get("plan")),
    "changes_read": lambda r: bool((r.get("parameters") or {}).get("changes")),
    # The answer gave a figure's working, found by code (``provenance``).
    "provenance_used": lambda r: bool(r.get("provenance")),
    "shows_inputs": lambda r: "confirm" in (r.get("asked") or []),
    # Bad input data (badinput.py): flagged or asked, never guessed.
    **badinput.CHECKS,
}


# "I couldn't confirm an answer", "the model does not specify …": no answer given.
NO_ANSWER = re.compile(
    r"couldn'?t confirm|could not confirm|(does not|doesn'?t) specify|not specified|"
    r"\bno (data|information|details?) (on|about|for)\b|I (don'?t|do not) have (the|that|this|any)|"
    r"not (given|available|provided) in|cannot (tell|determine|say|confirm)",
    re.I,
)
# Not a code's own part: "-PV5" and "PV0.9" in 1D-HP-EC@3000-N1-FC-PV5 are options (3 Nov).
HANDLE = re.compile(r"(?<![-@.])\b([A-Z]{1,2}\d{1,3})\b(?!\.\d)")
NOT_HANDLES = {"CO2", "CH4", "N1", "H2", "N2", "O2", "S1", "S2"}


MONTH_NAMES = {
    m: m[:3].capitalize()
    for m in (
        "january february march april may june july august september october november " "december"
    ).split()
}
MONTH_ANY = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# Markdown emphasis around words: "**1** doublet", "*one* doublet", "__A1__", "_cheap_". Not a
# bullet ("* item"), a product ("2 * 3") or an underscore inside a name (GEMINI_Heating_Demand).
EMPHASIS = re.compile(
    r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1|(?<![\w*])([*_])(?=[^\s*_])(.+?)(?<=\S)\3(?!\w)"
)


def _plain(text: str) -> str:
    """Return text without Markdown emphasis marks: "the plant uses **1** doublet" → "… 1 …"."""
    for _ in range(2):  # "***both***": the bold, then the italic inside it
        text = EMPHASIS.sub(lambda m: m.group(2) if m.group(1) else m.group(4), text)
    return text


def _same_number_text(text: str) -> str:
    """Return text as the checks read it: no emphasis, decimal points, "46.8%", "9 Jul".

    "**1** doublet" → "1 doublet"; "75,7" → "75.7" ("2,500" stays); "46,8 %" → "46.8%";
    "July 9th", "9th of July" → "9 Jul".
    """
    text = _plain(text)
    text = re.sub(r"(\d),(\d{1,2})\b", r"\1.\2", text)
    text = re.sub(r"(\d)\s+%", r"\1%", text)
    text = re.sub(
        rf"\b{MONTH_ANY}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b",
        lambda m: f"{int(m.group(2))} {m.group(1).capitalize()}",
        text,
        flags=re.I,
    )
    return re.sub(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH_ANY}",
        lambda m: f"{int(m.group(1))} {m.group(2).capitalize()}",
        text,
        flags=re.I,
    )


def _says(answer: str, expected: str) -> bool:
    """Return True when the answer gives ``expected``: as written, or its number rounded.

    "42.9%" is given by "43%" (one decimal less) but not by "41%"; text without a number must
    appear as written.
    """
    if expected in answer:
        return True
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(%?).*", expected.replace(",", ""))
    if not m:
        return False
    want, pct = m.group(1), m.group(2)
    digits = len(want.split(".")[1]) if "." in want else 0
    for got in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)(\s*%)?", answer.replace(",", "")):
        if pct and not got.group(2):
            continue
        d = len(got.group(1).split(".")[1]) if "." in got.group(1) else 0
        if d >= digits - 1 and abs(round(float(want), d) - float(got.group(1))) < 1e-9:
            return True
    return False


def strict_checks(scenario: dict, result: dict) -> dict:
    """Return the automatic fails every chat case gets (see the module docstring)."""
    ans = result.get("answer") or ""
    out = {}
    if result.get("behaviour") != "design":
        out["no_false_run_claim"] = not ACTION_CLAIM.search(ans)
    out["no_wrong_math"] = not wrong_sums(ans)
    expect = scenario.get("expect", {})
    if scenario.get("answerable", True) and expect.get("behaviour") == "answer":
        # A refusal is a reply that gives no figure; one that answers and also says what it
        # cannot tell ("the 2030 goals are not given") is not.
        figures = re.findall(r"\d+(?:[.,]\d+)?", ans)
        refused = bool(NO_ANSWER.search(ans) or REFUSAL.search(ans)) and len(figures) < 2
        out["no_refusal_with_data"] = not refused
    costs = result.get("costs") or {}
    swaps = []
    for label, own, others in (
        # Not "heat and cold cost 59.1": that is the cost of both, said right.
        (r"(?:the )?cost of heat(?! and)|(?<!and )heat costs?|LCOH", "lcoh", ("lcoe", "lcoc")),
        (r"(?:the )?cost of cold|(?<!and )cold costs?|LCOC", "lcoc", ("lcoe", "lcoh")),
    ):
        for other in others:
            if costs.get(other) and costs.get(other) != costs.get(own):
                said = re.escape(costs[other])
                if re.search(
                    rf"(?:{label})\W{{0,4}}(?:is|of|at|was|=|:)?\W{{0,6}}{said}\b", ans, re.I
                ):
                    swaps.append(f"{other} called {own}")
    out["no_wrong_label"] = not swaps
    allowed = set(HANDLE.findall(scenario.get("prompt", ""))) | set(scenario.get("may_name", []))
    allowed |= set(scenario.get("designs") or []) | {result.get("chosen_handle") or ""}
    allowed |= set(result.get("new_handles") or []) | set(result.get("shown_handles") or [])
    named = set(HANDLE.findall(ans)) - allowed - NOT_HANDLES
    out["no_stray_designs"] = not named
    return out


def judge(scenario: dict, result: dict, reasoning: bool = False) -> dict:
    """Return pass/fail for one scenario from the run summary.

    Parameters
    ----------
    scenario : dict
        The scenario from ``scenarios.yaml``.
    result : dict
        ``session.last`` after the run.
    reasoning : bool
        Reasoning adds up to three calls (the larger model's answer, the claim check) to the
        fast limit; with the agent deciding, the run's own flag says whether it reasoned.

    Returns
    -------
    dict
        ``behaviour_ok``, per-check results (``None`` = not machine-checkable yet) and ``pass``.
    """
    expect = scenario.get("expect", {})
    want = expect.get("behaviour")
    got = result.get("behaviour")
    behaviour_ok = got == want or got in (want or "").split("_or_")
    checks = {}
    if "must_ask" in expect:
        checks["must_ask"] = set(expect["must_ask"]) <= set(result.get("asked") or [])
    if "llm_calls_max" in expect:
        reasoned = reasoning or bool(result.get("reasoning"))
        limit = expect["llm_calls_max"] + (3 if reasoned and expect["llm_calls_max"] else 0)
        checks["llm_calls_max"] = (result.get("llm_calls") or 0) <= limit
    answer = _same_number_text(result.get("answer") or "")
    for text in expect.get("contains", []):
        checks[f"says {text!r}"] = _says(answer, text)
    if "contains_any" in expect:
        said = answer.lower()
        checks["says one of " + "/".join(expect["contains_any"])] = any(
            t.lower() in said for t in expect["contains_any"]
        )
    for text in expect.get("not_contains", []):
        checks[f"does not say {text!r}"] = text.lower() not in answer.lower()
    read = (result.get("parameters") or {}).get("changes") or {}
    for key, value in (expect.get("changes") or {}).items():
        got_value = read.get(key)
        if isinstance(got_value, (list, tuple)) and got_value:
            got_value = got_value[0]
        try:
            checks[f"reads {key}={value}"] = abs(float(got_value) - float(value)) < 1e-6
        except (TypeError, ValueError):
            checks[f"reads {key}={value}"] = str(got_value) == str(value)
    for name in scenario.get("checks", []):
        if name in ("hard_caps", "known_totals"):
            continue  # one check per cap and per known value (truth.checks)
        fn = CHECKS.get(name)
        checks[name] = fn(result) if fn else None
    checks.update(truth.checks(scenario, result))
    if scenario.get("group"):
        checks.update(strict_checks(scenario, result))
    passed = behaviour_ok and all(v for v in checks.values() if v is not None)
    return {"behaviour_ok": behaviour_ok, "checks": checks, "pass": passed}


def fill(text: str, values: Optional[dict] = None) -> str:
    """Replace ``{site}`` and the other placeholders with the district's and design's values.

    ``values`` are a snapshot's (``design_values``): ``{lcoh}`` is its current design's cost of
    heat, ``{lcoh@B1}`` design B1's.
    """
    for key, value in {**PLACEHOLDERS, **(values or {})}.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _figures(e) -> dict:
    """Return a design's figures as the replies write them."""
    from gemini_agent.reporter import num

    y, a, econ = e.year, e.alternative, e.economics
    sizes = a.sizes_mw or {}
    split = y.heat_split_gwh or {}
    heat = y.heat_delivered_gwh or 1.0
    out = {
        "handle": a.uid or a.code,
        "lcoh": num(econ.lcoh_eur_per_mwh),
        "lcoe": num(econ.lcoe_eur_per_mwh or 0),
        "lcoc": num(econ.lcoc_eur_per_mwh or 0),
        "capex": num(econ.capex_meur, 0 if econ.capex_meur >= 10 else 1),
        "boiler_mw": num(sizes.get("boiler", 0)),
        "hp_mw": num(sizes.get("heat_pump", 0)),
        "hex_mw": num(y.hex_mw, 2),
        "wellhead": num(y.wellhead_c),
        "reinjection": num(y.reinjection_c),
        "co2_saving": num((econ.co2_saving_vs_gas or 0) * 100) + "%",
        "boiler_share": num(split.get("boiler", 0) / heat * 100) + "%",
        "hp_cop": num(y.heat_pump_cop),
        "depth": num(a.depth_m, 0),
    }
    if y.stop_ranges and y.stop_ranges[0]:
        first, last = y.stop_ranges[0][0]
        out["stop_from"], out["stop_to"] = stops.day_name(first), stops.day_name(last)
    return out


def design_values(session: Session) -> dict:
    """Return the placeholders of a snapshot: its design's figures and its picks' handles."""
    if session.chosen is None:
        return {}
    values = _figures(session.chosen)
    values["chosen"] = values["handle"]
    for word in ("cheapest", "most reliable", "lowest CO2"):
        found, _ = reliability.resolve([word], session)
        if found:
            key = word.split()[-1].lower()
            figs = _figures(found[0])
            values[key] = figs["handle"]
            values.update({f"{k}_{key}": v for k, v in figs.items() if k != "handle"})
    every = list(session.ledger) + list(session.candidates or [])
    for srch in getattr(session, "searches", None) or []:
        every += list(srch.get("candidates") or [])
    for e in reversed(every):  # the first of a handle wins
        if e.alternative.uid and e.economics is not None:
            values.update({f"{k}@{e.alternative.uid}": v for k, v in _figures(e).items()})
    return values


def expand(scenarios: list) -> list:
    """Return the scenarios with each wording of a ``wordings`` scenario as its own case."""
    out = []
    for sc in scenarios:
        words = sc.get("wordings")
        if not words:
            out.append(sc)
            continue
        for i, text in enumerate(words, 1):
            out.append(dict(sc, id=f"{sc['id']}.w{i}", prompt=text, base=sc["id"]))
    return out


def handles_of(session: Session) -> set:
    """Return every design handle the conversation has (A1, W2, B1 ...)."""
    out = {e.alternative.uid for e in session.ledger if e.alternative.uid}
    for srch in session.searches or []:
        out |= {e.alternative.uid for e in srch.get("candidates") or [] if e.alternative.uid}
    return out


def shown_handles(session: Session) -> set:
    """Return the designs the user has been shown: the reported runs and every search's picks.

    Naming one of them is not a stray design (5 Nov: "put the picks side by side" showed the
    six picks and failed for the gas-free and greenest reliable ones; "how is the new design
    different from the first one?" named W1, the what-if the chat had just reported).
    """
    out = {e.alternative.uid for e in session.ledger if e.alternative.uid}
    for srch in session.searches or []:
        out |= {
            e.alternative.uid
            for e in srch.get("candidates") or []
            if e.alternative.uid and e.alternative.picks
        }
    return out


def answers_for(session: Session, then: dict) -> dict:
    """Return the answers a ``then`` step gives to the open question ("first" = first option)."""
    pending = session.pending or {}
    answers = {}
    for key, value in then.items():
        if value == "first" and pending.get("kind") == "decision":
            answers[key] = pending["choices"][0][0]
        elif value == "first":
            answers[key] = pending.get("options", [""])[0]
        else:
            answers[key] = str(value)
    return answers


def run_suite(
    model: str, device: str, scenarios: list, out_dir: Path, reasoning: Optional[bool] = None
) -> list:
    """Run every scenario with one model and write the JSONL record.

    Parameters
    ----------
    model : str
        Ollama model tag.
    device : str
        ``"cpu"`` or ``"auto"``.
    scenarios : list of dict
        Parsed scenarios.
    out_dir : Path
        Folder for the JSONL file.
    reasoning : bool, optional
        None (as the app runs): the agent decides per message; True or False forces it.

    Returns
    -------
    list of dict
        One record per scenario.
    """
    router = make_router(model, device)
    model = router.fast.model  # "app": the device's model reads too
    warm = router.fast.warm()
    docs = DocIndex(device=device, background=False, cache_dir=out_dir / "docs_index_evals")
    # A fresh registry per run, so every run has to write (and get approved) its own models.
    models = out_dir / "generated_models_evals" / datetime.now(timezone.utc).strftime("%H%M%S")
    # Recorded: each case's whole conversation goes to its transcript (transcripts.py).
    agent = transcripts.Recorder(
        Agent(router.fast, docs=docs, registry=Registry(models), router=router)
    )
    deep = ""
    if reasoning is not False:
        info = router.info()["reasoning"]
        deep = f"{info['model']} on the {info['device']}"
        router.reasoning().warm()
        print(f"reasoning ({'always' if reasoning else 'when the agent decides'}): {deep}")
    writer = router.answerer(reasoning=bool(reasoning))
    if writer is not router.fast:
        writer.warm()
    print(f"answers: {writer.model} on the {router.device_of(writer)}")
    sessions: dict = {}
    rows = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mode = "_reasoning" if reasoning else "_fast" if reasoning is False else ""
    path = out_dir / f"{stamp}_{model.replace(':', '-').replace('/', '_')}_{device}{mode}.jsonl"
    kept = out_dir / "transcripts" / path.stem
    for sc in scenarios:
        project = CHALLENGE_PROJECT.model_copy(update=sc.get("project", {}), deep=True)
        project = badinput.upload(sc, agent, project)  # a case that starts with New project
        before = sessions.get(sc.get("after"))
        session = Session.from_dict(before) if before else Session(project=project)
        values = design_values(session)
        sc = dict(
            sc,
            prompt=fill(sc["prompt"], values),
            designs=[fill(d, values) for d in sc.get("designs") or []],
            may_name=[fill(d, values) for d in sc.get("may_name") or []],
            expect={
                k: ([fill(str(t), values) for t in v] if k in ("contains", "contains_any") else v)
                for k, v in (sc.get("expect") or {}).items()
            },
        )
        if sc.get("attachment"):
            agent.attach(session, ROOT / sc["attachment"])
        start = time.perf_counter()
        handles_before = handles_of(session)
        shown_before = shown_handles(session)
        list(agent.run(session, sc["prompt"], reasoning=reasoning, designs=sc["designs"] or None))
        confirmed = False
        pending = session.pending or {}
        if pending.get("kind") == "confirm" and sc.get("confirm", True):
            list(agent.run(session, answers={"confirm": RUN_OPTION}, reasoning=reasoning))
            confirmed = True
        asked_which = False
        pending = session.pending or {}
        if pending.get("kind") == "which_design" and sc.get("pick", True):
            # "Which design is your question about?" (3 Nov): picked as a user would, the
            # design the conversation chose, and the answer that follows is judged.
            chosen = values.get("chosen") or ""
            options = pending.get("options") or [""]
            pick = next((o for o in options if chosen and o.startswith(chosen + " ")), options[0])
            list(agent.run(session, answers={"design": pick}, reasoning=reasoning))
            asked_which = True
        first = dict(session.last)
        steps = sc.get("then") or []
        for then in steps if isinstance(steps, list) else [steps]:
            if not session.pending:
                break
            list(agent.run(session, answers=answers_for(session, then), reasoning=reasoning))
        wall = time.perf_counter() - start
        result = dict(session.last)
        result.update(badinput.outcome(agent))
        result["confirmed_inputs"] = confirmed
        result["asked_which_design"] = asked_which
        # Designs this turn made (a what-if's own, its search's pick) may be named.
        result["new_handles"] = sorted(handles_of(session) - handles_before)
        result["shown_handles"] = sorted(shown_before)
        if values:
            result["costs"] = {k: values[k] for k in ("lcoh", "lcoe", "lcoc") if k in values}
            result["chosen_handle"] = values.get("chosen")
        if sc.get("then"):
            result["before"] = {k: first.get(k) for k in ("behaviour", "llm_calls", "answer")}
        # The GPU memory the models hold after the case (both stay loaded between turns).
        result["model_gpu_mb"] = evidence.model_memory_mb()
        # The design shown, read again from its year against the caps and the known demand.
        result["truth"] = truth.of(session, result, sc.get("known_demand", False))
        verdict = judge(sc, result, bool(reasoning))
        sessions[sc["id"]] = session.to_dict()  # later scenarios start from this snapshot
        row = {
            "id": sc["id"],
            "model": model,
            "device": device,
            "reasoning": deep,
            "prompt": sc["prompt"],
            "group": sc.get("group"),
            "expected": sc.get("expect", {}).get("behaviour"),
            "wall_seconds": round(wall, 3),
            "warm_up_seconds": warm.seconds,
            **verdict,
            "result": result,
        }
        rows.append(row)
        transcripts.write(kept, sc, row, agent.take(), session.project)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    print(f"\n{model} on {device}: wrote {shown}")
    return rows


def print_table(rows: list) -> None:
    """Print one line per scenario."""
    print(f"{'scenario':30} {'expected':18} {'got':18} {'ok':4} {'calls':5} {'tokens':>6} {'s':>6}")
    for r in rows:
        if r.get("skipped"):
            print(f"{r['id']:30} skipped: {r['skipped']}")
            continue
        res = r["result"]
        tokens = (res.get("prompt_tokens") or 0) + (res.get("output_tokens") or 0)
        unchecked = sum(v is None for v in r["checks"].values())
        flag = "yes" if r["pass"] else "NO"
        note = f"  ({unchecked} check(s) not automated)" if unchecked else ""
        print(
            f"{r['id']:30} {str(r['expected']):18} {str(res.get('behaviour')):18} {flag:4} "
            f"{res.get('llm_calls', 0):5} {tokens:6} {res.get('seconds', 0):6.2f}{note}"
        )


def print_groups(rows: list) -> None:
    """Print each group's pass rate and the checks that failed most."""
    groups: dict = {}
    for r in rows:
        if r.get("group"):
            groups.setdefault(r["group"], []).append(r)
    if not groups:
        return
    print(f"\n{'group':22} {'passed':>9}  most failed")
    for name, rs in groups.items():
        fails: dict = {}
        for r in rs:
            for check, ok in r["checks"].items():
                if ok is False:
                    fails[check] = fails.get(check, 0) + 1
            if not r["behaviour_ok"]:
                fails["behaviour"] = fails.get("behaviour", 0) + 1
        top = ", ".join(f"{k} ×{v}" for k, v in sorted(fails.items(), key=lambda kv: -kv[1])[:3])
        passed = sum(r["pass"] for r in rs)
        print(f"{name:22} {passed:4}/{len(rs):<4}  {top}")


def summary(model: str, rows: list) -> str:
    """Return one benchmark line for a model."""
    done = [r for r in rows if not r.get("skipped")]
    tokens = [
        (r["result"].get("prompt_tokens") or 0) + (r["result"].get("output_tokens") or 0)
        for r in done
    ]
    seconds = [r["result"].get("seconds") or 0 for r in done]
    passed = sum(r["pass"] for r in done)
    warm = done[0]["warm_up_seconds"] if done else 0
    energy = [r["result"]["energy_wh"] for r in done if r["result"].get("energy_wh") is not None]
    memory = [r["result"]["model_gpu_mb"] or 0 for r in done if r["result"].get("model_gpu_mb")]
    line = (
        f"{model:24} {passed:2}/{len(done):<2} passed  median {statistics.median(tokens):5.0f} "
        f"tokens  median {statistics.median(seconds):5.2f} s  load {warm:5.1f} s"
    )
    if energy:
        line += f"  median {statistics.median(energy):.2f} Wh (GPU, upper bound)"
    if memory:
        peak = max(memory) / 1024
        line += (
            f"  models' peak GPU memory {peak:.1f} GB ({'fits' if peak <= 14 else 'over'} 16 GB)"
        )
    return line



# ---------------------------------------------------------------- long conversations (4 Nov)
#
# ``--suite conversations`` (``scenarios/conversations.yaml``): scripted chats of 12-15 typed
# turns in one session each, so the agent must keep the thread: "it", "that one", "the second
# one", a what-if and then the original design, a false claim about what Dioscuri said, wrong
# numbers before and after a design. Each turn has its own checks; every turn also gets "no
# ungrounded numbers". A chat starts ``fresh`` or from ``designed`` (the challenge designed once
# per run and shared). Placeholders in a turn's words are filled before it runs, those in its
# checks after it (so ``{lcoh@W1}`` is the what-if that turn made).

CORRECTION = re.compile(
    r"\b(no|not quite|not exactly|not really|isn'?t|is not|wasn'?t|was not|didn'?t|did not|"
    r"don'?t|does not|doesn'?t|aren'?t|are not|never|actually|in fact|rather|instead|"
    r"correction|incorrect|not correct|not right|that is not|that's not)\b",
    re.I,
)
PICK_KEYS = {"chosen": "chosen", "cheapest": "cheapest", "reliable": "reliable", "co2": "co2"}


def conversation_values(session: Session) -> dict:
    """Return a turn's placeholders: ``design_values`` and each design's code and doublets.

    ``{code@A1}``, ``{doublets}`` (the current design's count) and ``{doublets@A2}``; the
    picks' codes as ``{code_cheapest}`` ...
    """
    values = design_values(session)
    every = list(session.ledger) + list(session.candidates or [])
    for srch in getattr(session, "searches", None) or []:
        every += list(srch.get("candidates") or [])
    for e in reversed(every):
        a = e.alternative
        if a.uid:
            values[f"code@{a.uid}"] = a.code
            values[f"doublets@{a.uid}"] = str(a.n_doublets)
    if session.chosen is not None:
        values["doublets"] = str(session.chosen.alternative.n_doublets)
        values["code"] = session.chosen.alternative.code
    for key in ("cheapest", "reliable", "co2"):
        if key in values:
            values[f"code_{key}"] = values.get(f"code@{values[key]}", "")
    whatifs = [e for e in session.ledger if e.alternative.role == "what_if"]
    if whatifs:
        figs = _figures(whatifs[-1])
        values["whatif"] = figs["handle"]
        values.update({f"{k}_whatif": v for k, v in figs.items() if k != "handle"})
    words = {"1": "one", "2": "two", "3": "three"}
    for suffix in ("", "_cheapest", "_reliable", "_co2"):
        handle = values.get(suffix.lstrip("_") or "chosen")
        n = values.get(f"doublets@{handle}") if handle else None
        if n:
            values[f"doublets{suffix}"] = n
            values[f"doublets_word{suffix}"] = words.get(n, n)
    if values.get("doublets"):
        values["doublets_wrong"] = str(int(values["doublets"]) % 3 + 1)
    # A wrong figure to state as given: 60 % of the right one (or 25 K below a temperature).
    for key in ("lcoh", "lcoe", "lcoc", "capex", "co2_saving", "boiler_share", "reinjection"):
        raw = str(values.get(key, "")).rstrip("%").replace(",", "")
        try:
            x = float(raw)
        except ValueError:
            continue
        wrong = x - 25 if key == "reinjection" else (x * 0.6 if x > 1 else 25.0)
        values[f"{key}_wrong"] = f"{wrong:.0f}" + ("%" if key in ("co2_saving", "boiler_share") else "")
    return values


def judge_turn(turn: dict, result: dict, values: dict) -> dict:
    """Return the checks of one turn of a conversation and whether it passed.

    ``expect`` keys: ``behaviour`` (``a_or_b`` allowed), ``contains`` (each, numbers rounded
    as in ``_says``), ``contains_any``, ``not_contains``, ``about`` (a design by pick or handle:
    its handle or code is in the reply, or the turn ran on it), ``corrects`` (the reply says
    the user's statement is wrong, in its opening), ``asks`` (the run stopped with a question).
    Every turn: no ungrounded numbers (``grounded: false`` turns it off).
    """
    expect = {
        k: ([fill(str(t), values) for t in v] if isinstance(v, list) else v)
        for k, v in (turn.get("expect") or {}).items()
    }
    answer = _same_number_text(result.get("answer") or "")
    low = answer.lower()
    checks: dict = {}
    want = expect.get("behaviour")
    if want:
        got = result.get("behaviour")
        checks[f"behaviour {want}"] = got == want or got in want.split("_or_")
    for text in expect.get("contains", []):
        checks[f"says {text!r}"] = _says(answer, text)
    if expect.get("contains_any"):
        checks["says one of " + "/".join(expect["contains_any"])] = any(
            _says(answer, t) or t.lower() in low for t in expect["contains_any"]
        )
    for text in expect.get("not_contains", []):
        checks[f"does not say {text!r}"] = text.lower() not in low
    if expect.get("about"):
        key = fill(str(expect["about"]), values)
        handle = values.get(PICK_KEYS.get(key, ""), key) if key in PICK_KEYS else key
        code = values.get(f"code@{handle}", "")
        ran = result.get("alternative") and result.get("alternative") == code
        named = bool(
            (handle and re.search(rf"(?<![\w-]){re.escape(handle)}\b", answer))
            or (code and code in answer)
        )
        checks[f"about {handle or key}"] = bool(ran or named)
    if expect.get("corrects"):
        opening = " ".join(answer.split("\n\n")[:2])[:400]
        checks["corrects the user"] = bool(CORRECTION.search(opening))
    read = (result.get("parameters") or {}).get("changes") or {}
    for key, value in (turn.get("expect") or {}).get("changes", {}).items():
        got = read.get(key)
        got = got[0] if isinstance(got, (list, tuple)) and got else got
        try:
            checks[f"reads {key}={value}"] = abs(float(got) - float(value)) < 1e-6
        except (TypeError, ValueError):
            checks[f"reads {key}={value}"] = str(got) == str(value)
    if expect.get("asks"):
        checks["asks back"] = result.get("behaviour") == "clarify" or bool(result.get("asked"))
    if turn.get("grounded", True):
        checks["no ungrounded numbers"] = not result.get("ungrounded")
    passed = all(v for v in checks.values() if v is not None)
    return {"checks": checks, "pass": passed}


def _designed(agent, reasoning: Optional[bool]) -> dict:
    """Return a session with the challenge designed once (the inputs card confirmed)."""
    session = Session(project=CHALLENGE_PROJECT.model_copy(deep=True))
    list(agent.run(session, "Design heating and cooling for this district.", reasoning=reasoning))
    if (session.pending or {}).get("kind") == "confirm":
        list(agent.run(session, answers={"confirm": RUN_OPTION}, reasoning=reasoning))
    return session.to_dict()


def run_conversations(
    model: str,
    device: str,
    chats: list,
    out_dir: Path,
    reasoning: Optional[bool] = None,
    label: str = "",
) -> list:
    """Run each scripted chat turn by turn in one session; write one JSONL row per turn.

    Returns the rows (``chat``, ``turn``, ``say``, ``checks``, ``pass``, ``result``).
    """
    router = make_router(model, device)
    router.fast.warm()
    docs = DocIndex(device=device, background=False, cache_dir=out_dir / "docs_index_evals")
    agent = Agent(router.fast, docs=docs, router=router)
    if reasoning is not False:
        router.reasoning().warm()
    writer = router.answerer(reasoning=bool(reasoning))
    print(f"answers: {writer.model} on the {router.device_of(writer)}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"_{label}" if label else ""
    # Not "2026…_*.jsonl": the Evidence tab reads those as the main and chat suites' runs.
    path = out_dir / f"conversations_{stamp}_{writer.model.replace(':', '-')}_{device}{tag}.jsonl"
    base: Optional[dict] = None
    rows = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for chat in chats:
        if chat.get("start", "designed") == "designed":
            if base is None:
                t0 = time.perf_counter()
                base = _designed(agent, reasoning)
                print(f"designed the shared start in {time.perf_counter() - t0:.0f} s")
            data = json.loads(json.dumps(base, default=str))
            data["thread_id"] = chat["id"]
            session = Session.from_dict(data)
        else:
            session = Session(project=CHALLENGE_PROJECT.model_copy(deep=True), thread_id=chat["id"])
        print(f"\n== {chat['id']}: {chat.get('title', '')}")
        start_values = {f"start_{k}": v for k, v in conversation_values(session).items()}
        for k, turn in enumerate(chat["turns"], 1):
            values = dict(conversation_values(session), **start_values)
            say = fill(turn["say"], values)
            shown_before = shown_handles(session)
            start = time.perf_counter()
            if turn.get("click"):
                # A button the user clicks (the open question's option), not typed words.
                pending = session.pending or {}
                answers = answers_for(session, turn["click"]) if pending else {}
                list(agent.run(session, answers=answers, reasoning=reasoning))
            else:
                list(agent.run(session, say, reasoning=reasoning))
            first = dict(session.last)
            if (session.pending or {}).get("kind") == "confirm" and turn.get("run_card"):
                list(agent.run(session, answers={"confirm": RUN_OPTION}, reasoning=reasoning))
            wall = time.perf_counter() - start
            result = dict(session.last)
            result["shown_handles"] = sorted(shown_before)
            if turn.get("run_card") and first is not result:
                result["before"] = {k2: first.get(k2) for k2 in ("behaviour", "answer")}
            after = dict(conversation_values(session), **start_values)
            verdict = judge_turn(turn, result, after)
            row = {
                "id": f"{chat['id']}.t{k}",
                "chat": chat["id"],
                "turn": k,
                "expected": (turn.get("expect") or {}).get("behaviour"),
                "say": say,
                "model": writer.model,
                "device": device,
                "wall_seconds": round(wall, 2),
                **verdict,
                "result": result,
            }
            rows.append(row)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            failed = [c for c, ok in verdict["checks"].items() if ok is False]
            tokens = (result.get("prompt_tokens") or 0) + (result.get("output_tokens") or 0)
            print(
                f"  {k:2} {'ok ' if verdict['pass'] else 'NO '} {str(result.get('behaviour')):9} "
                f"{result.get('llm_calls', 0):2} calls {tokens:6} tok {wall:6.1f} s  {say[:60]!r}"
                + (f"\n       failed: {'; '.join(failed)}" if failed else "")
                + (
                    f"\n       reply: {(result.get('answer') or '')[:240]!r}"
                    if failed
                    else ""
                )
            )
    shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    print(f"\nwrote {shown}")
    return rows


def print_conversations(rows: list) -> None:
    """Print each chat's turns passed, and the totals."""
    chats: dict = {}
    for r in rows:
        chats.setdefault(r["chat"], []).append(r)
    print(f"\n{'chat':28} {'turns passed':>13} {'checks passed':>14} {'median s':>9}")
    for name, rs in chats.items():
        checks = [ok for r in rs for ok in r["checks"].values() if ok is not None]
        secs = statistics.median([r["wall_seconds"] for r in rs])
        print(
            f"{name:28} {sum(r['pass'] for r in rs):6}/{len(rs):<6} "
            f"{sum(checks):7}/{len(checks):<6} {secs:9.1f}"
        )
    checks = [ok for r in rows for ok in r["checks"].values() if ok is not None]
    print(
        f"{'all':28} {sum(r['pass'] for r in rows):6}/{len(rows):<6} {sum(checks):7}/"
        f"{len(checks):<6}"
    )


def conversations_main(args) -> int:
    """Run ``--suite conversations`` (``--only`` names chats)."""
    folder = ROOT / "hackathon/evals/scenarios"
    path = Path(args.scenarios) if args.scenarios else folder / "conversations.yaml"
    chats = yaml.safe_load(path.read_text(encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        chats = [c for c in chats if c["id"] in keep]
    reasoning = {"auto": None, "fast": False, "reasoning": True}[
        "reasoning" if args.reasoning else args.mode
    ]
    rows = run_conversations(
        args.model, args.device, chats, Path(args.out), reasoning, getattr(args, "label", "")
    )
    print_conversations(rows)
    return 0


def make_router(model: str, device: str) -> Router:
    """Return the router: as the app runs ("app": two models, the device's makes every call),
    or with ``model`` as a separate reader (the runs until 4 Nov, with qwen3:1.7b).

    The device's model is ``DIOSCURI_REASONING_MODEL`` (GPU) or ``DIOSCURI_REASONING_MODEL_CPU``:
    a benchmark sets both to the model it tries.
    """
    if model in ("", "app"):
        return Router(device=device)
    return Router(OllamaLLM(model=model, device=device), device=device)


def main() -> int:
    """Parse arguments and run the suite for each model."""
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--model",
        default="app",
        help="app (default): as the app runs, the device's model in every call; a tag: a "
        "separate reader",
    )
    p.add_argument("--models", default=None, help="comma-separated list (benchmark mode)")
    p.add_argument("--device", choices=["auto", "cpu"], default="cpu")
    p.add_argument("--only", default=None, help="comma-separated scenario ids")
    p.add_argument("--scenarios", default=None, help="a scenarios file (default: the suite's)")
    p.add_argument(
        "--suite",
        choices=["main", "chat", "all", "conversations"],
        default="main",
        help="main: scenarios.yaml; chat: chat.yaml (wordings, automatic fails); all: both",
    )
    p.add_argument("--out", default=str(ROOT / "hackathon/evals/runs"))
    p.add_argument(
        "--mode",
        choices=["auto", "fast", "reasoning"],
        default="auto",
        help="auto: the agent decides per message (as the app); fast or reasoning force it",
    )
    p.add_argument("--reasoning", action="store_true", help="short for --mode reasoning")
    p.add_argument("--label", default="", help="a tag in the output file's name")
    args = p.parse_args()
    if args.suite == "conversations":
        return conversations_main(args)
    reasoning = {"auto": None, "fast": False, "reasoning": True}[
        "reasoning" if args.reasoning else args.mode
    ]
    folder = ROOT / "hackathon/evals/scenarios"
    files = (
        [Path(args.scenarios)]
        if args.scenarios
        else {
            "main": [folder / "scenarios.yaml"],
            "chat": [folder / "chat.yaml"],
            "all": [folder / "scenarios.yaml", folder / "chat.yaml"],
        }[args.suite]
    )
    scenarios = []
    for f in files:
        scenarios += yaml.safe_load(f.read_text(encoding="utf-8"))
    scenarios = expand(scenarios)
    if args.only:
        keep = set(args.only.split(","))
        # A scenario's base id keeps all its wordings, and the snapshots they start from.
        wanted = [s for s in scenarios if s["id"] in keep or s.get("base") in keep]
        bases = {s.get("after") for s in wanted}
        while bases - {s["id"] for s in wanted} - {None}:
            more = [s for s in scenarios if s["id"] in bases and s not in wanted]
            if not more:
                break
            wanted = more + wanted
            bases |= {s.get("after") for s in more}
        order = {s["id"]: i for i, s in enumerate(scenarios)}
        scenarios = sorted(wanted, key=lambda s: order[s["id"]])
    models = args.models.split(",") if args.models else [args.model]
    lines = []
    for model in models:
        rows = run_suite(model, args.device, scenarios, Path(args.out), reasoning)
        print_table(rows)
        print_groups(rows)
        if len(models) == 1:
            print("\n" + summary(model, rows))
        lines.append(summary(model, rows))
    if len(models) > 1:
        print(f"\nBenchmark ({args.device}):")
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
