"""Eval cases with bad input data: the app or the agent must flag it or ask, never guess.

A case with ``upload`` starts as a user would with their own district: it makes a project from
demand files and values through ``projects.Projects.create``, the code behind the New project
dialog (``POST /api/projects``). What the app answered is the case's first exchange:

- the project is made: the chat then runs the case's prompt in it;
- the app asks (``projects.UnitQuestion``, a file with no unit and values too large for MW):
  the case's ``upload.answers`` (``{heat_unit: kW}``) answer it and the project is made, or,
  without an answer, the case ends there, asked;
- the app refuses (``projects.ProjectError``, a 364-day year, a cooling return colder than its
  supply): the case ends there, ``behaviour: upload_rejected``.

Usage in a scenario::

    upload:
      name: Short year
      heat: hackathon/evals/scenarios/fixtures/heating_364_days.csv
      cool: src/gemini_agent/data/challenge/GEMINI_Cooling_Demand_Daily_2027.csv
      values: {depth_m: 2500, temperature_c: 87}
      answers: {heat_unit: kW}
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from gemini_agent import projects
from transcripts import app_reply

ROOT = Path(__file__).resolve().parents[2]
VALUES = {"depth_m": 2500, "temperature_c": 87}  # the challenge's reservoir
_FOLDER: dict = {}


def _registry() -> projects.Projects:
    """Return the eval's own projects folder (made once a run, never the app's)."""
    if "reg" not in _FOLDER:
        _FOLDER["reg"] = projects.use(tempfile.mkdtemp(prefix="dioscuri-eval-projects-"))
    return _FOLDER["reg"]


def _said(spec: dict, units: dict) -> str:
    files = [Path(spec[k]).name for k in ("heat", "cool") if spec.get(k)]
    values = ", ".join(f"{k} {v}" for k, v in (spec.get("values") or {}).items())
    text = f"New project “{spec.get('name', 'Eval district')}” from {' and '.join(files)}"
    text += f" ({values})" if values else ""
    if units:
        text = " ".join(f"The {k}ing file is in {u}." for k, u in units.items())
    return text


def upload(scenario: dict, agent, project):
    """Make the case's project as the New project dialog would; return the project to use.

    The app's answers are kept as the case's first exchanges (``agent.add``). When no
    project is made, the agent is told to skip the chat (``agent.skip``), and ``outcome``
    gives the case's result.

    Parameters
    ----------
    scenario : dict
        The case; without ``upload`` nothing is done.
    agent : transcripts.Recorder
        The recording agent.
    project : ProjectData
        The project the case would use otherwise.

    Returns
    -------
    ProjectData
        The project made, or ``project`` when the case has no upload or none was made.
    """
    agent.upload, agent.skip = None, False
    spec = scenario.get("upload")
    if not spec:
        return project
    reg = _registry()
    read = {k: (ROOT / spec[k]).read_bytes() for k in ("heat", "cool") if spec.get(k)}
    heat = (Path(spec["heat"]).name, read["heat"])
    cool = (Path(spec["cool"]).name, read["cool"]) if "cool" in read else None
    values = {**VALUES, **(spec.get("values") or {})}
    info: dict = {"asked": [], "rejected": False, "reply": "", "made": None, "notes": []}
    units: dict = {}
    for _ in range(3):
        said = _said(dict(spec, values=values), units)
        user = {"message": said, "upload": {"files": [heat[0]] + ([cool[0]] if cool else [])}}
        try:
            record = reg.create(spec.get("name", "Eval district"), heat, cool, values, units)
        except projects.UnitQuestion as q:
            info["asked"].append(q.key)
            info["reply"] = f"{q} ({' or '.join(q.options)})"
            agent.add(user, app_reply(info["reply"], outcome="clarify"))
            answer = (spec.get("answers") or {}).get(q.key)
            if answer is None:
                break
            units[q.key.split("_")[0]] = answer
            continue
        except projects.ProjectError as err:
            info["rejected"] = True
            info["reply"] = f"The project was not made: {err}"
            agent.add(user, app_reply(info["reply"], outcome="upload_rejected"))
            break
        t = record.totals
        info["made"] = record.id
        info["notes"] = list(record.notes)
        info["totals"] = dict(t)
        info["reply"] = (
            f"Project made: {t['annual_heat_gwh']:g} GWh of heat a year (peak "
            f"{t['peak_heat_mw']:g} MW) and {t['annual_cool_gwh']:g} GWh of cold."
            + (f" Notes: {'; '.join(record.notes)}." if record.notes else "")
        )
        agent.add(user, app_reply(info["reply"], outcome="upload_made"))
        agent.upload = info
        return reg.data(record.id)
    agent.upload, agent.skip = info, True
    return project


def outcome(agent) -> dict:
    """Return what an upload adds to the case's result (its ``behaviour`` when no chat ran)."""
    info = getattr(agent, "upload", None)
    if not info:
        return {}
    out = {"upload": info}
    if info["made"] is None:
        out.update(
            behaviour="upload_rejected" if info["rejected"] else "clarify",
            answer=info["reply"],
            asked=list(info["asked"]),
        )
    return out


BREAKS = re.compile(
    r"\b(break|breaks|broke|exceed|exceeds|above|over|beyond|more than|fails?|violat\w*|"
    r"outside)\b",
    re.I,
)
CAP_300 = re.compile(r"\b300\s*(m³/h|m3/h|m\^3/h|cubic)", re.I)


def _flow_cap_said(result: dict) -> bool:
    """Return True when the reply names the 300 m³/h cap, and says it broke when it did.

    A design whose doublets stay within 300 m³/h must not be said to run at 400.
    """
    caps = (result.get("truth") or {}).get("caps") or []
    flow = next((c for c in caps if c["key"] == "flow"), None)
    answer = result.get("answer") or ""
    named = bool(CAP_300.search(answer))
    if flow is not None and flow["ok"] is False:
        return named and bool(BREAKS.search(answer))
    return named


def _no_return_below_supply(result: dict) -> bool:
    """No run used a cooling return at or below its supply (20 °C)."""
    changes = (result.get("parameters") or {}).get("changes") or {}
    ret = changes.get("cool_return_c")
    supply = changes.get("cool_supply_c", 20.0)
    try:
        return ret is None or float(ret) > float(supply)
    except (TypeError, ValueError):
        return True


CHECKS = {
    "upload_rejected": lambda r: bool((r.get("upload") or {}).get("rejected")),
    "upload_asks_unit": lambda r: any(
        k.endswith("_unit") for k in (r.get("upload") or {}).get("asked") or []
    ),
    "upload_made": lambda r: bool((r.get("upload") or {}).get("made")),
    "flow_cap_said": _flow_cap_said,
    "no_return_below_supply": _no_return_below_supply,
}
