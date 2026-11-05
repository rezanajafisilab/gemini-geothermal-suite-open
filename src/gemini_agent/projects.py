"""Projects: the organisers' district and the districts users add, each with its own data.

A project is one district: a year of daily heat and cold demand, a reservoir and the networks'
supply and return temperatures. The organisers' challenge district is built in (id
``challenge``); users add theirs from the app (``POST /api/projects``). Each user project is a
folder under ``DIOSCURI_PROJECTS`` (default ``hackathon/evals/runs/projects``, not committed):

- ``project.json``: the name, the reservoir, the networks, the uploads and the year's totals;
- ``heat_mw.csv`` and ``cool_mw.csv``: the year as the engine reads it, in the organisers'
  format (``date,heating_demand_MWth``, 365 rows);
- ``files/``: the uploads as they came, which the chat can show.

A profile may be daily (365 rows) or hourly (8,760 rows, averaged to days), comma- or
semicolon-separated (decimal commas then allowed), in MW, kW, MWh or kWh (read from the
column's header; MW when it names none, unless the values are far too large for a district in
MW: then the user is asked, ``UnitQuestion``). The challenge's caps (1-3 doublets, 50-300 m3/h,
brine cooled by at most 40 K, 330 days, 70 % pumps) apply to every project.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import secrets
import shutil
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import dioscuri_plant as dp
from dioscuri_plant.types import DAYS
from gemini_agent.contract import NetworkTemps, ProjectData

CHALLENGE = "challenge"
CHALLENGE_DIR = Path(__file__).resolve().parent / "data" / "challenge"
CHALLENGE_FILES = (
    "GEMINI_Heating_Demand_Daily_2027.csv",
    "GEMINI_Cooling_Demand_Daily_2027.csv",
    "GEMINI_Hackathon_Challenge_Requirements.docx.pdf",
)
DATA_DIR = Path(__file__).resolve().parent / "data"
# Two real Dutch doublets set up like the challenge district (2 Nov): their reservoirs, brine and
# permits from the public documents on NLOG, their demand assumed (the briefs say how; see
# ``hackathon/scripts/make_real_projects.py``). Built in, like the challenge.
BUILTINS: Dict[str, dict] = {
    "trias-westland": {
        "name": "Trias Westland",
        "folder": DATA_DIR / "trias_westland",
        "files": (
            "Trias_Westland_Heating_Demand_Daily_2027.csv",
            "Trias_Westland_Cooling_Demand_Daily_2027.csv",
            "Trias_Westland_project_brief.md",
        ),
        "rules": {
            "reservoir_depth_m": 2336.0,
            "reservoir_thickness_m": 59.0,
            "permeability_md": 650.0,
            "well_spacing_m": 1800.0,  # mid-reservoir, the report's p. 40
            "gradient_c_per_km": 33.0,
            "surface_temperature_c": 10.0,
            "reservoir_pressure_bar": round(1.01325 + 1087.0 * 9.81 * 2336.0 / 1e5, 1),
            "brine_density_kg_m3": 1087.0,
            "brine_cp_j_kg_k": 3575.0,
            "flow_max_m3h": 525.0,
            "max_brine_cooling_k": 56.0,
            "heat_supply_c": 75.0,
            # The brine is injected at 31 °C: the network returns 5 K colder (the exchanger).
            "heat_return_c": 26.0,
        },
        "has_cool_profile": False,
        # What the inputs card says each figure comes from, and its kind (see reporter.KINDS).
        "sources": {
            "demand": (
                "assumed (the project brief): 100 ha of greenhouses at 1.0 GJ/m² a year, 40 % "
                "a steady base, 60 % the challenge district's shape; no profile is published",
                "assumed",
            ),
            "reservoir": ("PanTerra, Geological report TW OK II (G1363b, 2020), on NLOG", "data"),
            "brine": (
                "PanTerra (2020): 140,000 ppm; the gas 0.8 Nm³/m³ assumed (as in the challenge)",
                "data",
            ),
            "heat_capacity": ("Sharqawy, Lienhard & Zubair 2010 for 140 g/kg at 60 °C", "derived"),
            "caps": (
                "PanTerra (2020): at most 525 m³/h (the tubing), injection at 31 °C (87 - 31 = "
                "56 K); 1 to 3 doublets as in the challenge",
                "data",
            ),
            "operating_days": ("assumed, as in the challenge", "assumed"),
            "heating": (
                "assumed (the project brief): the return 5 K below the 31 °C injection",
                "assumed",
            ),
        },
        "notes": (
            "Reservoir, brine and caps: PanTerra, Geological report TW OK II (2020), on NLOG",
            "Demand assumed: 100 ha of greenhouses at 1.0 GJ/m2 a year (no published profile)",
            "Network temperatures assumed: 75/26 °C (the return 5 K below the 31 °C injection)",
        ),
    },
    "hal-leyweg": {
        "name": "Haagse Aardwarmte Leyweg",
        "folder": DATA_DIR / "hal_leyweg",
        "files": (
            "HAL_Leyweg_Heating_Demand_Daily_2027.csv",
            "HAL_Leyweg_Cooling_Demand_Daily_2027.csv",
            "HAL_Leyweg_project_brief.md",
        ),
        "rules": {
            "reservoir_depth_m": 2025.0,
            "reservoir_thickness_m": 50.0,
            "permeability_md": 1000.0,
            "gradient_c_per_km": 35.0,
            "surface_temperature_c": 10.0,
            "reservoir_pressure_bar": round(1.01325 + 1070.0 * 9.81 * 2025.0 / 1e5, 1),
            "brine_density_kg_m3": 1070.0,
            "brine_cp_j_kg_k": 3653.0,
            "gas_liquid_ratio": 1.0,
            "flow_max_m3h": 165.0,
            "max_brine_cooling_k": 34.0,
            "heat_supply_c": 70.0,
            # Injected at 45 °C in winter: the network returns 5 K colder (the exchanger).
            "heat_return_c": 40.0,
        },
        "has_cool_profile": False,
        "sources": {
            "demand": (
                "assumed (the project brief): 4,000 homes at 12 MWh a year, the challenge "
                "district's shape; no profile is published",
                "assumed",
            ),
            "reservoir": (
                "Ministry of EZK, decision DGKE-WO / V-109 (2020), on NLOG: about 2 km, 79 °C "
                "produced; thickness 50 m and 1,000 mD assumed",
                "data",
            ),
            "brine": (
                "the decision: about 1 Nm³ of gas per m³; 120,000 ppm and 80 % CH₄ assumed",
                "data",
            ),
            "heat_capacity": ("Sharqawy, Lienhard & Zubair 2010 for 120 g/kg at 60 °C", "derived"),
            "caps": (
                "the decision: at most 165 m³/h, injection at least 45 °C (about 34 K of "
                "cooling); 1 to 3 doublets as in the challenge",
                "data",
            ),
            "operating_days": ("assumed, as in the challenge", "assumed"),
            "heating": (
                "assumed (the project brief): the return 5 K below the 45 °C winter injection",
                "assumed",
            ),
        },
        "notes": (
            "Reservoir and permit: Ministry of EZK, approval of the production plan (2020), "
            "on NLOG",
            "Demand assumed: 4,000 homes at 12 MWh a year (no published profile)",
            "Thickness 50 m and 1,000 mD assumed; network temperatures assumed: 70/40 °C (the "
            "return 5 K below the 45 °C winter injection)",
        ),
    },
}
ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(
    os.environ.get("DIOSCURI_PROJECTS", ROOT / "hackathon" / "evals" / "runs" / "projects")
)
PROJECT_ID = re.compile(r"^[a-z0-9-]{1,48}$")
FILE_NAME = re.compile(r"^[\w.() -]{1,120}$")
MAX_UPLOAD_MB = 5
HOURS = DAYS * 24
SURFACE_C = dp.Rules().surface_temperature_c  # 12 °C: the gradient runs from here
# What a form may give, with its unit, its range and its default (None: required).
LIMITS: Dict[str, Tuple[str, float, float, Optional[float]]] = {
    "depth_m": ("reservoir depth (m)", 500, 6000, None),
    "temperature_c": ("reservoir temperature (°C)", 20, 200, None),
    "pressure_bar": ("reservoir pressure (bar)", 10, 1000, None),  # None: hydrostatic
    "permeability_md": ("permeability (mD)", 1, 10000, 200.0),
    "thickness_m": ("net thickness (m)", 5, 1000, 100.0),
    "heat_supply_c": ("heating supply (°C)", 40, 150, 100.0),
    "heat_return_c": ("heating return (°C)", 15, 120, 60.0),
    "cool_supply_c": ("cooling supply (°C)", 4, 30, 20.0),
    "cool_return_c": ("cooling return (°C)", 6, 40, 25.0),
}


class ProjectError(ValueError):
    """A project the user asked for that can't be made: the message says what to change."""


class UnitQuestion(ProjectError):
    """A demand file whose unit can't be told from it: the question, and the units to pick.

    Parameters
    ----------
    message : str
        The question, with what was found.
    key : str
        ``heat_unit`` or ``cool_unit``: the form field the answer goes back in.
    options : list of str
        The units to choose from, the likelier first.
    """

    def __init__(self, message: str, key: str, options: Sequence[str]):
        """Keep the question's field and options."""
        super().__init__(message)
        self.key = key
        self.options = list(options)


# The highest daily mean a district's demand may have in MW when its file names no unit. The
# largest Dutch heat networks peak near 1,500 MW and the challenge district at 30 MW; values
# above this are far likelier kW (a 30 MW district written in kW peaks at 30,000).
MW_PLAUSIBLE = 2000.0
UNITS = ("mw", "kw", "mwh", "kwh", "gwh")


# ------------------------------------------------------------------ reading a profile


@dataclass
class Profile:
    """One year of daily demand read from an upload, in MW, with what was done to it."""

    mw: List[float]
    dates: List[str]
    column: str
    notes: List[str] = field(default_factory=list)

    @property
    def annual_gwh(self) -> float:
        """Return the year's energy, GWh."""
        return round(sum(self.mw) * 24 / 1000, 2)

    @property
    def peak_mw(self) -> float:
        """Return the highest daily mean, MW."""
        return round(max(self.mw), 2)


KIND_WORDS = {"heat": re.compile(r"heat|warm", re.I), "cool": re.compile(r"cool|cold|koud", re.I)}
KIND_NAMES = {"heat": "heating", "cool": "cooling"}
UNIT = re.compile(r"(?<![a-z])(gwh|mwh|kwh|mw|kw)(?:th|cool|c|e)?(?![a-z])", re.I)
UNIT_NAMES = {"kw": "kW", "kwh": "kWh", "mwh": "MWh", "gwh": "GWh"}


def _number(cell: str, decimal_comma: bool) -> Optional[float]:
    text = cell.strip().replace(" ", "").replace(" ", "")
    if decimal_comma:
        text = text.replace(".", "").replace(",", ".") if "," in text else text
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _rows(text: str) -> Tuple[List[List[str]], bool]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ProjectError("the file is empty")
    first = lines[0]
    delimiter = ";" if first.count(";") > first.count(",") else "\t" if "\t" in first else ","
    rows = [r for r in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter) if r]
    return rows, delimiter != ","


def read_profile(name: str, data: bytes, kind: str, unit: Optional[str] = None) -> Profile:
    """Read one year of heat or cold demand from an uploaded CSV.

    Parameters
    ----------
    name : str
        The upload's file name (for the messages).
    data : bytes
        The file.
    kind : {"heat", "cool"}
        Which demand: picks the column when the header names both.
    unit : {"MW", "kW", "MWh", "kWh", "GWh"}, optional
        The user's answer when the header names no unit (``UnitQuestion``); a unit in the
        header wins.

    Returns
    -------
    Profile
        365 daily means in MW, their dates, the column read and notes on any conversion.

    Raises
    ------
    ProjectError
        When the file is not a year of daily or hourly values: the message says why.
    UnitQuestion
        When the header names no unit and the values are far too large for MW.
    """
    if not name.lower().endswith((".csv", ".txt", ".tsv")):
        raise ProjectError(f"{name}: a CSV file, please (date and value per row)")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    rows, decimal_comma = _rows(text)
    width = max(len(r) for r in rows)
    header = rows[0] if _number(rows[0][-1], decimal_comma) is None else None
    body = rows[1:] if header else rows
    col = width - 1
    if header:
        named = [i for i, h in enumerate(header) if KIND_WORDS[kind].search(h)]
        other = "cool" if kind == "heat" else "heat"
        values = [i for i in range(len(header)) if not KIND_WORDS[other].search(header[i])]
        col = named[-1] if named else (values[-1] if len(values) > 1 else len(header) - 1)
        if not named and KIND_WORDS[other].search(header[col]):
            raise ProjectError(
                f"{name}: its column {header[col].strip()!r} looks like {KIND_NAMES[other]} "
                f"demand, not {KIND_NAMES[kind]}"
            )
    column = header[col].strip() if header and col < len(header) else f"column {col + 1}"
    mw: List[float] = []
    stamps: List[str] = []
    for i, r in enumerate(body, start=2 if header else 1):
        cell = r[col] if col < len(r) else ""
        value = _number(cell, decimal_comma)
        if value is None:
            raise ProjectError(
                f"{name}, row {i}: {cell.strip() or 'an empty cell'} is not a number"
            )
        if value < -1e-9:
            raise ProjectError(f"{name}, row {i}: demand can't be negative ({value:g})")
        mw.append(max(value, 0.0))
        stamps.append(r[0].strip() if len(r) > 1 and col != 0 else "")
    n = len(mw)
    if n not in (DAYS, HOURS):
        leap = " (a leap year: drop 29 February)" if n in (DAYS + 1, HOURS + 24) else ""
        raise ProjectError(
            f"{name}: {n:,} values{leap}; a year of 365 daily or 8,760 hourly values is needed"
        )
    named = UNIT.search(column)
    given = (unit or "").strip().lower() or None
    if given is not None and given not in UNITS:
        raise ProjectError(f"{name}: the unit must be one of MW, kW, MWh, kWh or GWh, not {unit!r}")
    if named is None and given is None:
        _plausible_mw(name, column, mw, kind)
    unit = named.group(1).lower() if named else given or "mw"
    notes = []
    hourly = n == HOURS
    # Hourly energy (kWh in an hour) is the hour's mean power (kW); a day's energy is 24 h of it.
    scale = {
        "mw": 1.0,
        "kw": 1e-3,
        "mwh": 1.0 if hourly else 1 / 24,
        "kwh": 1e-3 if hourly else 1 / 24000,
        "gwh": 1e3 if hourly else 1e3 / 24,
    }[unit]
    if named is None and given is not None:
        notes.append(f"no unit in the header: {UNIT_NAMES.get(unit, 'MW')} as you said")
    elif unit != "mw":
        notes.append(f"{UNIT_NAMES[unit]} read from the header, turned to MW")
    elif named is None:
        notes.append("no unit in the header: read as MW")
    mw = [v * scale for v in mw]
    if hourly:
        mw = [sum(mw[d * 24 : d * 24 + 24]) / 24 for d in range(DAYS)]
        stamps = [s.replace("T", " ").split(" ")[0] for s in stamps[::24]]
        notes.append("8,760 hourly values averaged to 365 days")
    dates = (
        stamps
        if all(stamps) and len(set(stamps)) == DAYS
        else [f"day {d + 1}" for d in range(DAYS)]
    )
    if kind == "heat" and max(mw) <= 0:
        raise ProjectError(f"{name}: the heating demand is zero all year")
    return Profile([round(v, 4) for v in mw], dates, column, notes)


def _plausible_mw(name: str, column: str, values: Sequence[float], kind: str) -> None:
    """Ask for the unit when a file names none and its values are far too large for MW."""
    peak = max(values) if values else 0.0
    if peak <= MW_PLAUSIBLE:
        return
    raise UnitQuestion(
        f"{name}: the column {column!r} names no unit and its values reach {peak:,.0f}. As MW "
        f"that is far more {KIND_NAMES[kind]} than a district needs (the challenge district's "
        f"heat peaks at 30 MW); as kW it is {peak / 1000:,.1f} MW. Which unit is it? Name it in "
        f"the header (for example {kind}ing_demand_kW) or pick it.",
        key=f"{kind}_unit",
        options=["kW", "MW"],
    )


def weekly(values) -> List[float]:
    """Return 52 weekly means of 365 daily values (the app's sparklines)."""
    return [round(sum(values[w * 7 : w * 7 + 7]) / 7, 2) for w in range(DAYS // 7)]


def preview(name: str, data: bytes, kind: str, unit: Optional[str] = None) -> dict:
    """Return what an upload gives before a project is made: totals, weekly means, notes.

    A file whose unit has to be asked (``UnitQuestion``) is shown read in the likelier unit,
    with ``unit_question`` (its text, the form field and the units to pick); the project is
    not made until the user picks one.

    Raises
    ------
    ProjectError
        As ``read_profile`` does.
    """
    if kind not in KIND_WORDS:
        raise ProjectError("kind: heat or cool")
    if len(data) > MAX_UPLOAD_MB * 2**20:
        raise ProjectError(f"{name}: at most {MAX_UPLOAD_MB} MB")
    question = None
    try:
        p = read_profile(_file_name(name), data, kind, unit)
    except UnitQuestion as q:
        question = {"key": q.key, "text": str(q), "options": q.options}
        p = read_profile(_file_name(name), data, kind, q.options[0])
        p.notes[:] = [f"read as {q.options[0]} until you pick the unit"]
    return {
        "unit_question": question,
        "name": _file_name(name),
        "kind": kind,
        "column": p.column,
        "annual_gwh": p.annual_gwh,
        "peak_mw": p.peak_mw,
        "notes": p.notes,
        "weekly_mw": weekly(p.mw),
        # A heating file with a cooling column too: the form need not ask for a second file.
        "cool_column": kind == "heat" and has_column(data, "cool"),
    }


def has_column(data: bytes, kind: str) -> bool:
    """Return True when a CSV's header names a column for this demand (heat or cool)."""
    try:
        rows, _ = _rows(data.decode("utf-8-sig", errors="replace"))
    except ProjectError:
        return False
    return any(KIND_WORDS[kind].search(h) for h in rows[0])


# ------------------------------------------------------------------ the projects


@dataclass(frozen=True)
class Record:
    """One project as stored: what the app lists and what the engine needs."""

    id: str
    name: str
    files: Tuple[str, ...]
    reservoir: Dict[str, float]
    heating: Tuple[float, float]
    cooling: Tuple[float, float]
    totals: Dict[str, float]
    builtin: bool = False
    created: Optional[float] = None
    notes: Tuple[str, ...] = ()
    has_cool_profile: bool = True

    def as_dict(self) -> dict:
        """Return the project as the app reads it (``GET /api/projects``)."""
        return {
            "id": self.id,
            "name": self.name,
            "builtin": self.builtin,
            "created": self.created,
            "files": list(self.files),
            "reservoir": dict(self.reservoir),
            "heating": {"supply_c": self.heating[0], "return_c": self.heating[1]},
            "cooling": {"supply_c": self.cooling[0], "return_c": self.cooling[1]},
            "totals": dict(self.totals),
            "notes": list(self.notes),
        }


def _totals(demand: dp.Demand) -> Dict[str, float]:
    heat, cool = demand.arrays()
    return {
        "annual_heat_gwh": round(float(heat.sum()) * 24 / 1000, 2),
        "annual_cool_gwh": round(float(cool.sum()) * 24 / 1000, 2),
        "peak_heat_mw": round(float(heat.max()), 2),
        "peak_cool_mw": round(float(cool.max()), 2),
    }


def hydrostatic_bar(depth_m: float) -> float:
    """Return the brine column's pressure at a depth, bar (the challenge's brine)."""
    rules = dp.Rules()
    return round(rules.brine_density_kg_m3 * 9.81 * depth_m / 1e5, 1)


def _checked(values: Dict[str, Optional[float]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, (label, lo, hi, default) in LIMITS.items():
        raw = values.get(key)
        if raw is None or raw == "":
            if default is None and key != "pressure_bar":
                raise ProjectError(f"the {label} is needed")
            if default is not None:
                out[key] = default
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ProjectError(f"the {label} must be a number, not {raw!r}")
        if not lo <= value <= hi:
            raise ProjectError(f"the {label} must be between {lo:g} and {hi:g}, not {value:g}")
        out[key] = value
    if out["temperature_c"] <= SURFACE_C + 5:
        raise ProjectError(f"the reservoir must be warmer than {SURFACE_C + 5:g} °C")
    if out["heat_return_c"] >= out["heat_supply_c"] - 5:
        raise ProjectError("the heating return must be at least 5 °C below its supply")
    if out["cool_return_c"] <= out["cool_supply_c"]:
        raise ProjectError("the cooling return must be warmer than its supply")
    out.setdefault("pressure_bar", hydrostatic_bar(out["depth_m"]))
    return out


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32].strip("-") or "project"


def _file_name(name: str) -> str:
    base = Path(name or "profile.csv").name
    return base if FILE_NAME.match(base) else re.sub(r"[^\w.() -]", "_", base)[:120]


class Projects:
    """The projects on this server: the challenge district and the ones users added.

    Parameters
    ----------
    folder : str or Path
        Where user projects are kept (one folder each).
    """

    def __init__(self, folder):
        """Use this folder for user projects (made when the first project is)."""
        self.folder = Path(folder)
        self._demand: Dict[str, dp.Demand] = {}
        self._records: Dict[str, Record] = {}

    # The challenge district: the organisers' files and the requirements' reservoir.
    def _challenge(self) -> Record:
        if CHALLENGE not in self._records:
            rules = dp.Rules()
            self._records[CHALLENGE] = Record(
                id=CHALLENGE,
                name="Challenge district 2027",
                files=CHALLENGE_FILES,
                reservoir={
                    "depth_m": rules.reservoir_depth_m,
                    "temperature_c": rules.reservoir_temperature_c(),
                    "pressure_bar": rules.reservoir_pressure_bar,
                    "permeability_md": rules.permeability_md,
                    "thickness_m": rules.reservoir_thickness_m,
                    "gradient_c_per_km": rules.gradient_c_per_km,
                },
                heating=(rules.heat_supply_c, rules.heat_return_c),
                cooling=(rules.cool_supply_c, rules.cool_return_c),
                totals=_totals(self.demand(CHALLENGE)),
                builtin=True,
            )
        return self._records[CHALLENGE]

    def _builtin(self, project_id: str) -> Record:
        """Return a built-in real project (``BUILTINS``) as a record."""
        if project_id not in self._records:
            spec = BUILTINS[project_id]
            rules = self.rules(project_id)
            self._records[project_id] = Record(
                id=project_id,
                name=spec["name"],
                files=tuple(spec["files"]),
                reservoir={
                    "depth_m": rules.reservoir_depth_m,
                    "temperature_c": rules.reservoir_temperature_c(),
                    "pressure_bar": rules.reservoir_pressure_bar,
                    "permeability_md": rules.permeability_md,
                    "thickness_m": rules.reservoir_thickness_m,
                    "gradient_c_per_km": rules.gradient_c_per_km,
                },
                heating=(rules.heat_supply_c, rules.heat_return_c),
                cooling=(rules.cool_supply_c, rules.cool_return_c),
                totals=_totals(self.demand(project_id)),
                builtin=True,
                notes=tuple(spec.get("notes", ())),
                has_cool_profile=bool(spec.get("has_cool_profile", True)),
            )
        return self._records[project_id]

    def _dir(self, project_id: str) -> Path:
        if not PROJECT_ID.match(project_id or "") or project_id == CHALLENGE:
            raise KeyError(project_id)
        if project_id in BUILTINS:
            raise KeyError(project_id)
        return self.folder / project_id

    def get(self, project_id: str) -> Record:
        """Return a project; KeyError when there is none with this id."""
        if project_id == CHALLENGE:
            return self._challenge()
        if project_id in BUILTINS:
            return self._builtin(project_id)
        if project_id in self._records:
            return self._records[project_id]
        path = self._dir(project_id) / "project.json"
        if not path.is_file():
            raise KeyError(project_id)
        raw = json.loads(path.read_text("utf-8"))
        record = Record(
            id=raw["id"],
            name=raw["name"],
            files=tuple(raw["files"]),
            reservoir=raw["reservoir"],
            heating=tuple(raw["heating"]),
            cooling=tuple(raw["cooling"]),
            totals=raw["totals"],
            created=raw.get("created"),
            notes=tuple(raw.get("notes", ())),
            has_cool_profile=raw.get("has_cool_profile", True),
        )
        self._records[project_id] = record
        return record

    def list(self) -> List[Record]:
        """Return the challenge district first, then the users' projects, oldest first."""
        found = []
        if self.folder.is_dir():
            for path in self.folder.glob("*/project.json"):
                try:
                    found.append(self.get(path.parent.name))
                except (KeyError, ValueError, json.JSONDecodeError):
                    continue  # a half-written or foreign folder is not a project
        builtin = [self._builtin(k) for k in BUILTINS]
        return [self._challenge()] + builtin + sorted(found, key=lambda r: r.created or 0.0)

    def create(
        self,
        name: str,
        heat: Tuple[str, bytes],
        cool: Optional[Tuple[str, bytes]] = None,
        values: Optional[Dict[str, Optional[float]]] = None,
        units: Optional[Dict[str, Optional[str]]] = None,
    ) -> Record:
        """Make a project from its demand files and its reservoir.

        Parameters
        ----------
        name : str
            What the project is called (1-80 characters).
        heat : tuple of (str, bytes)
            The heating profile's file name and content.
        cool : tuple of (str, bytes), optional
            The cooling profile; when left out, the heating file's cooling column if it has one,
            else no cooling.
        values : dict, optional
            The reservoir and the networks (keys of ``LIMITS``); depth and temperature needed.
        units : dict, optional
            ``{"heat": "kW", "cool": "MW"}``: the user's answer for a file whose header names
            no unit (``UnitQuestion``).

        Returns
        -------
        Record
            The new project.

        Raises
        ------
        ProjectError
            When a value or a file can't be used: the message says which and why.
        """
        name = " ".join((name or "").split())
        if not 1 <= len(name) <= 80:
            raise ProjectError("the project needs a name (at most 80 characters)")
        for upload in (heat, cool):
            if upload and len(upload[1]) > MAX_UPLOAD_MB * 2**20:
                raise ProjectError(f"{upload[0]}: at most {MAX_UPLOAD_MB} MB")
        v = _checked(values or {})
        units = units or {}
        heat_name = _file_name(heat[0])
        heat_profile = read_profile(heat_name, heat[1], "heat", units.get("heat"))
        notes = [f"{heat_name}: {n}" for n in heat_profile.notes]
        files = [heat_name]
        if cool is not None:
            cool_name = _file_name(cool[0])
            if cool_name == heat_name:
                cool_name = "cooling_" + cool_name
            cool_profile = read_profile(cool_name, cool[1], "cool", units.get("cool"))
            notes += [f"{cool_name}: {n}" for n in cool_profile.notes]
            files.append(cool_name)
        elif has_column(heat[1], "cool"):
            cool_profile = read_profile(heat_name, heat[1], "cool", units.get("cool"))
            notes.append(f"cooling read from {heat_name} ({cool_profile.column})")
        else:
            cool_profile = Profile([0.0] * DAYS, heat_profile.dates, "none")
            notes.append("no cooling profile: no cooling demand")
        depth, temp = v["depth_m"], v["temperature_c"]
        gradient = round((temp - SURFACE_C) / depth * 1000, 2)
        project_id = f"{_slug(name)}-{secrets.token_hex(3)}"
        tmp = self.folder / f".{project_id}.tmp"
        (tmp / "files").mkdir(parents=True)
        try:
            (tmp / "files" / heat_name).write_bytes(heat[1])
            if cool is not None:
                (tmp / "files" / files[1]).write_bytes(cool[1])
            for fname, profile, header in (
                ("heat_mw.csv", heat_profile, "heating_demand_MWth"),
                ("cool_mw.csv", cool_profile, "cooling_demand_MWcool"),
            ):
                lines = [f"date,{header}"] + [
                    f"{d},{x:.4f}" for d, x in zip(heat_profile.dates, profile.mw)
                ]
                (tmp / fname).write_text("\n".join(lines) + "\n", "utf-8")
            demand = dp.Demand.from_csv(tmp / "heat_mw.csv", tmp / "cool_mw.csv")
            raw = {
                "version": 1,
                "id": project_id,
                "name": name,
                "created": time.time(),
                "files": files,
                "reservoir": {
                    "depth_m": depth,
                    "temperature_c": temp,
                    "pressure_bar": v["pressure_bar"],
                    "permeability_md": v["permeability_md"],
                    "thickness_m": v["thickness_m"],
                    "gradient_c_per_km": gradient,
                },
                "heating": [v["heat_supply_c"], v["heat_return_c"]],
                "cooling": [v["cool_supply_c"], v["cool_return_c"]],
                "totals": _totals(demand),
                "notes": notes,
                "has_cool_profile": cool_profile.column != "none",
            }
            (tmp / "project.json").write_text(
                json.dumps(raw, indent=2, ensure_ascii=False), "utf-8"
            )
            tmp.replace(self.folder / project_id)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return self.get(project_id)

    def delete(self, project_id: str) -> None:
        """Remove a user's project and its files (the challenge district stays)."""
        if project_id == CHALLENGE or project_id in BUILTINS:
            raise ProjectError("a built-in project can't be removed")
        folder = self._dir(project_id)
        if not (folder / "project.json").is_file():
            raise KeyError(project_id)
        shutil.rmtree(folder)
        self._records.pop(project_id, None)
        self._demand.pop(project_id, None)

    def demand(self, project_id: str = CHALLENGE) -> dp.Demand:
        """Return a project's daily demand for the year (MW)."""
        if project_id not in self._demand:
            if project_id == CHALLENGE:
                folder, heat, cool = CHALLENGE_DIR, CHALLENGE_FILES[0], CHALLENGE_FILES[1]
            elif project_id in BUILTINS:
                spec = BUILTINS[project_id]
                folder, heat, cool = spec["folder"], spec["files"][0], spec["files"][1]
            else:
                self.get(project_id)  # KeyError when unknown
                folder, heat, cool = self._dir(project_id), "heat_mw.csv", "cool_mw.csv"
            self._demand[project_id] = dp.Demand.from_csv(folder / heat, folder / cool)
        return self._demand[project_id]

    def rules(self, project_id: str = CHALLENGE) -> dp.Rules:
        """Return the plant model's rules for a project: its reservoir and networks."""
        base = dp.Rules()
        if project_id == CHALLENGE:
            return base
        if project_id in BUILTINS:
            return replace(base, **BUILTINS[project_id]["rules"])
        r = self.get(project_id)
        res = r.reservoir
        return replace(
            base,
            reservoir_depth_m=res["depth_m"],
            gradient_c_per_km=res["gradient_c_per_km"],
            surface_temperature_c=SURFACE_C,
            reservoir_pressure_bar=res["pressure_bar"],
            permeability_md=res["permeability_md"],
            reservoir_thickness_m=res["thickness_m"],
            heat_supply_c=r.heating[0],
            heat_return_c=r.heating[1],
            cool_supply_c=r.cooling[0],
            cool_return_c=r.cooling[1],
        )

    def data(self, project_id: str = CHALLENGE) -> ProjectData:
        """Return what a conversation in this project starts knowing."""
        r = self.get(project_id)
        return ProjectData(
            id=r.id,
            name=r.name,
            files=list(r.files),
            has_heat_profile=True,
            has_cool_profile=r.has_cool_profile,
            has_reservoir=True,
            annual_heat_gwh=r.totals["annual_heat_gwh"],
            annual_cool_gwh=r.totals["annual_cool_gwh"],
            reservoir_depth_m=r.reservoir["depth_m"],
            reservoir_temp_c=round(r.reservoir["temperature_c"], 2),
            heating=NetworkTemps(supply_c=r.heating[0], return_c=r.heating[1]),
            cooling=NetworkTemps(supply_c=r.cooling[0], return_c=r.cooling[1]),
        )

    def view(self, project_id: str) -> dict:
        """Return a project as the app shows it, with its weekly demand for the sparklines."""
        d = self.demand(project_id)
        return {
            **self.get(project_id).as_dict(),
            "weekly_mw": {"heat": weekly(d.heat_mw), "cool": weekly(d.cool_mw)},
        }

    def file_path(self, project_id: str, name: str) -> Optional[Path]:
        """Return a project file's path (the uploads as they came), None when it has none."""
        try:
            record = self.get(project_id)
        except KeyError:
            return None
        match = next((f for f in record.files if f.lower() == Path(name).name.lower()), None)
        if match is None:
            return None
        if project_id in BUILTINS:
            path = BUILTINS[project_id]["folder"] / match
        else:
            path = (
                CHALLENGE_DIR / match if record.builtin else self._dir(project_id) / "files" / match
            )
        return path if path.is_file() else None


def depths(rules: dp.Rules, project_id: str = CHALLENGE) -> Sequence[float]:
    """Return the aquifer depths a search tries unless asked.

    The challenge: the known aquifer and 500 and 1,000 m deeper (2,500 to 3,500 m). The
    requirements describe one aquifer, at its midpoint; the organisers said on 2 Nov that a
    depth change is acceptable, so deeper wells are tried with the same aquifer properties
    assumed there (hydrostatic pressure, the gradient), and labelled as assumed. Other projects
    describe their own reservoir: the known one only, unless the user asks for other depths.
    """
    described = tuple(a.depth_m for a in rules.aquifers())
    if len(described) > 1:
        # Aquifers described beside the known one (``Rules.other_aquifers``, the older second
        # aquifer): those, and no assumed ones.
        return tuple(dict.fromkeys(described))
    if project_id == CHALLENGE:
        return tuple(assumed_depths(rules))
    return (rules.reservoir_depth_m,)


def assumed_depths(rules: dp.Rules) -> Sequence[float]:
    """Return the depths tried when the user asks for deeper wells: 500 and 1,000 m deeper."""
    d = rules.reservoir_depth_m
    return (d, d + 500.0, d + 1000.0)


_REGISTRY = Projects(FOLDER)


def registry() -> Projects:
    """Return the server's projects."""
    return _REGISTRY


def use(folder) -> Projects:
    """Keep user projects in another folder (tests, a second server); return the registry."""
    global _REGISTRY
    _REGISTRY = Projects(folder)
    return _REGISTRY
