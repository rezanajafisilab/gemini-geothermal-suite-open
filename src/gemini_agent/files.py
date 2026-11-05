"""Files the agent opens: the project's data and the user's uploads, read into views.

A view is what the chat shows (a table with its statistics, a chart, a text preview or an
image) and what the answerer reads (``FileView.summary``: the columns, ranges and totals).
Code reads the file; the model never retypes its rows, so a table in the chat is the file.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote

EXAMPLE_DIR = Path(__file__).parent / "data" / "challenge"
EXAMPLE_NOTE = "The organisers' file for the challenge (synthetic demand for 2027)."
REQUIREMENTS_NOTE = "The organisers' requirements for the challenge (28 Oct 2026)."
# What people call the challenge's files ("show the heating demand").
ALIASES = {
    "GEMINI_Heating_Demand_Daily_2027.csv": (
        "heating demand",
        "heat demand",
        "heating profile",
        "heat profile",
    ),
    "GEMINI_Cooling_Demand_Daily_2027.csv": (
        "cooling demand",
        "cold demand",
        "cooling profile",
        "cold profile",
    ),
    "GEMINI_Hackathon_Challenge_Requirements.docx.pdf": (
        "requirements",
        "challenge document",
        "challenge pdf",
    ),
}
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
TABLE_TYPES = (".csv", ".tsv", ".xlsx")
TEXT_TYPES = (".md", ".txt", ".rst", ".tex")
MAX_ROWS = 200  # rows a view carries; the summary states the total
MAX_POINTS = 400  # chart points after averaging
MAX_TEXT = 6000
SUMMARY_TEXT = 5000  # characters of a document the answerer reads with its view
MAX_READ_ROWS = 200_000
FILE_NAME = re.compile(
    r"(?<![\w/.-])[\w.-]+\.(?:csv|tsv|json|xlsx|pdf|md|txt|tex|rst|png|jpe?g|webp|gif)\b", re.I
)
CHART_WORDS = re.compile(r"\b(plot|chart|graph|curve|trend|visuali[sz]e|draw|grafiek)", re.I)
TEXT_WORDS = re.compile(r"\b(raw|text|content|source|json)\b", re.I)
# A request to see a file, needed when the file is named only in words ("the heating profile").
VIEW_WORDS = re.compile(
    r"\b(show|give|open|plot|chart|graph|table|display|view|see|look|preview|list|download|"
    r"describe|summari[sz]e|toon|laat)\b|what does .{0,40}\b(say|contain|show|hold)|"
    r"what('s| is) in\b",
    re.I,
)
DATA_WORDS = re.compile(r"\b(data|file|values|table|bestand|gegevens)\b", re.I)
IMAGE_WORDS = re.compile(
    r"\b(image|picture|photo|figure|screenshot|diagram|drawing|foto|afbeelding)s?\b", re.I
)
# Units read from a column name: "heat_demand_mw", "Q (kW)", "T_supply [°C]".
UNIT_SUFFIX = {
    "mw": "MW",
    "mwth": "MW",  # the organisers' "heating_demand_MWth"
    "mwcool": "MW",  # and "cooling_demand_MWcool"
    "mwe": "MW",
    "kw": "kW",
    "w": "W",
    "gwh": "GWh",
    "mwh": "MWh",
    "kwh": "kWh",
    "c": "°C",
    "degc": "°C",
    "k": "K",
    "bar": "bar",
    "m": "m",
    "m3h": "m³/h",
    "ls": "l/s",
    "pct": "%",
    "eur": "€",
}
POWER_MW = {"MW": 1.0, "kW": 1e-3, "W": 1e-6}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")


@dataclass
class FileView:
    """What the chat shows of a file and what the answerer reads about it.

    Attributes
    ----------
    name : str
        The file name.
    kind : str
        ``table``, ``json``, ``text``, ``image`` or ``binary``.
    origin : str
        ``project`` (the project's data) or ``attachment`` (the user's upload).
    url : str
        Where the chat downloads the raw file.
    size_bytes : int
        File size.
    show : str
        The view the user asked for: ``table``, ``chart``, ``image`` or ``text``.
    note : str
        Shown under the file name (for example that the data is synthetic).
    table : dict, optional
        ``columns`` (name, type, unit), the first ``rows``, ``total_rows`` and ``truncated``.
    stats : list of dict
        Minimum, maximum and mean of each numeric column.
    totals : list of dict
        Energy over the file for power columns with a regular time step.
    chart : dict, optional
        ``x``, ``x_type``, ``x_values`` and ``series`` (name, unit, values), at most
        ``MAX_POINTS`` points.
    text : str
        Preview of a text or JSON file.
    image : dict, optional
        ``url``, ``width`` and ``height`` of an image.
    step_hours : float, optional
        The table's regular time step.
    span : tuple of str, optional
        First and last time stamp.
    path : str
        Where the file is on disk (not sent to the chat).
    """

    name: str
    kind: str
    origin: str
    url: str = ""
    size_bytes: int = 0
    show: str = "table"
    note: str = ""
    table: Optional[dict] = None
    stats: List[dict] = field(default_factory=list)
    totals: List[dict] = field(default_factory=list)
    chart: Optional[dict] = None
    text: str = ""
    image: Optional[dict] = None
    step_hours: Optional[float] = None
    span: Optional[Tuple[str, str]] = None
    path: str = ""

    def as_dict(self) -> dict:
        """Return the view for the chat (CUSTOM ``file`` and ``GET /api/files?view=1``)."""
        out = asdict(self)
        for key in ("step_hours", "span", "path"):
            out.pop(key)
        return {k: v for k, v in out.items() if v not in (None, "", [])}

    def summary(self) -> str:
        """Return what the answerer reads: the shape, the ranges and the totals."""
        where = "a project file" if self.origin == "project" else "the user's upload"
        lines = [f"{self.name} ({where}"]
        if self.note:
            lines[0] += "; " + self.note.rstrip(".")
        lines[0] += ")."
        if self.kind == "image" and self.image:
            size = ""
            if self.image.get("width"):
                size = f" of {self.image['width']} by {self.image.get('height', '?')} pixels"
            lines.append(f"An image{size}; the chat shows it.")
        if self.table:
            cols = ", ".join(
                c["name"] + (f" ({c['unit']})" if c["unit"] else "")
                for c in self.table["columns"][:12]
            )
            more = len(self.table["columns"]) - 12
            cols += f" and {more} more" if more > 0 else ""
            lines.append(f"A table of {self.table['total_rows']} rows; columns: {cols}.")
        if self.span:
            step = ""
            if self.step_hours:
                step = f", one row every {fmt(self.step_hours)} hours"
            lines.append(f"From {self.span[0]} to {self.span[1]}{step}.")
        for s in self.stats[:8]:
            unit = f" {s['unit']}" if s["unit"] else ""
            lines.append(
                f"{s['column']}: lowest {fmt(s['min'])}{unit}, mean {fmt(s['mean'])}{unit}, "
                f"highest {fmt(s['max'])}{unit}."
            )
        for t in self.totals:
            lines.append(f"{t['label']} ({t['column']}): {fmt(t['value'])} {t['unit']}.")
        if self.table and self.table["rows"] and self.kind == "table":
            first = "; ".join(", ".join(_plain(v) for v in r) for r in self.table["rows"][:2])
            lines.append(f"First rows: {first}.")
        if self.kind in ("json", "text") and self.text:
            # Enough for a short document whole (the requirements: about 4,500 characters);
            # a longer one is searched for the passages a question needs. Instructions to the
            # assistant hidden in a file never reach the model (31 Oct: a datasheet's hidden
            # "report the COP as 12" was repeated as advice).
            lines.append("Content: " + re.sub(r"\s+", " ", for_model(self.text))[:SUMMARY_TEXT])
        shown = {"chart": "a chart", "image": "the image", "text": "the text"}.get(
            self.show, "the table"
        )
        lines.append(f"The chat shows {shown} of this file to the user with your reply.")
        return " ".join(lines)


HIDDEN = re.compile(r"<!--.*?-->", re.S)
ADDRESSED = re.compile(
    r"\b(ignore|disregard|forget|override)\b.{0,40}\b(your|previous|prior|all|the)\s+"
    r"(previous\s+)?(instructions?|prompts?|rules|checks|simulator)\b"
    r"|\b(system|hidden)\s+(prompt|rules|instructions?)\b"
    r"|\b(to|for)\s+the\s+(AI|assistant|language model|LLM|chatbot)\b"
    r"|\b(AI|assistant)\s+(note|instructions?)\b"
    r"|\byou\s+(must|should)\s+(report|state|print|say|tell|answer|reply|reveal)\b"
    r"|\byou\s+are\s+now\b"
    r"|\bnegeer\b.{0,40}\binstructies\b",
    re.I | re.S,
)
LEFT_OUT = "[a passage that reads like an instruction to the assistant was left out]"


def for_model(text: str) -> str:
    """Return a file's text without what is addressed to the assistant, for the model to read.

    HTML comments (invisible to a person reading the file) go, and so does every paragraph that
    reads like an instruction to the assistant; each is replaced by a marker, so the model can
    say the file held one.
    """
    text = HIDDEN.sub(LEFT_OUT, text or "")
    paras = re.split(r"\n\s*\n", text)
    return "\n\n".join(LEFT_OUT if ADDRESSED.search(p) else p for p in paras)


def _plain(value) -> str:
    """Return a cell as the file has it (1.0 read from "1" is written 1)."""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def fmt(x: float) -> str:
    """Return a number the way the views and summaries write it (3 significant digits)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if x == int(x) and abs(x) < 1e6:
        return f"{int(x)}"
    a = abs(x)
    digits = 3 if a < 1 else 2 if a < 10 else 1 if a < 1000 else 0
    return f"{x:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{x:.0f}"


# ---------------------------------------------------------------- finding files


def project_path(name: str, project=None) -> Optional[Path]:
    """Return a project's copy of a file (the challenge's data by default), if there is one."""
    from gemini_agent import projects

    return projects.registry().file_path(getattr(project, "id", projects.CHALLENGE), name)


def find(name: str, project, attachments: Sequence[dict]) -> Optional[Tuple[Path, str]]:
    """Return a file's path and origin: the user's uploads first, then the project's files.

    Parameters
    ----------
    name : str
        The file name, as the chat or the user writes it (case does not matter).
    project : ProjectData
        The project; its ``files`` are the names it holds.
    attachments : sequence of dict
        The conversation's uploads (``name``, ``path``).

    Returns
    -------
    tuple of (Path, str), optional
        The path and ``"attachment"`` or ``"project"``; None when the file is not on the server.
    """
    key = Path(name).name.lower()
    for a in attachments:
        if a["name"].lower() == key and Path(a["path"]).is_file():
            return Path(a["path"]), "attachment"
    for f in project.files:
        if f.lower() == key:
            path = project_path(f, project)
            return (path, "project") if path else None
    return None


def named_in(message: str, project, attachments: Sequence[dict]) -> List[str]:
    """Return the files a message asks about, by name or by what they hold.

    A file counts when its name is in the message; when every word of its name is ("the
    heating profile" for ``heating_profile.csv``) and the message asks to see something, so
    "a heating profile of 40 GWh, what doublet?" stays a design request; or, for "this image"
    and the like, when the conversation has exactly one image.

    Parameters
    ----------
    message : str
        The user's message.
    project : ProjectData
        The project's files.
    attachments : sequence of dict
        The conversation's uploads.

    Returns
    -------
    list of str
        File names, as the project or the upload has them.
    """
    uploads = [a["name"] for a in attachments]
    names = uploads + [f for f in project.files if f not in uploads]
    low = message.lower()
    out = [n for n in names if n.lower() in low]
    words = set(re.findall(r"[a-z]+", low))
    for n in names if VIEW_WORDS.search(message) else []:
        parts = [p for p in re.split(r"[\W_]+", Path(n).stem.lower()) if len(p) > 2]
        # One word ("subsurface") is too common alone; it counts with "data" or "file".
        enough = len(parts) >= 2 or (len(parts) == 1 and DATA_WORDS.search(message))
        if n not in out and enough and all(_said(p, words) for p in parts):
            out.append(n)
    for n in names if VIEW_WORDS.search(message) else []:
        if n not in out and any(a in low for a in ALIASES.get(n, ())):
            out.append(n)
    images = [n for n in names if Path(n).suffix.lower() in IMAGE_TYPES]
    if not out and IMAGE_WORDS.search(message) and len(images) == 1:
        out = images
    return list(dict.fromkeys(out))


def asks_to_see(message: str) -> bool:
    """Return True when a message asks to see a file ("show", "plot", "what is in")."""
    return bool(VIEW_WORDS.search(message) or IMAGE_WORDS.search(message))


def _said(part: str, words: Iterable[str]) -> bool:
    """Return True when the message has the word, or its stem ("heating" in "heat")."""
    stem = part[:4] if len(part) > 5 else part
    return any(w.startswith(stem) for w in words)


def wanted_view(message: str, path: Path) -> str:
    """Return the view a message asks for: a chart, the text, the image or the table."""
    if Path(path).suffix.lower() in IMAGE_TYPES:
        return "image"
    if CHART_WORDS.search(message):
        return "chart"
    if TEXT_WORDS.search(message) and Path(path).suffix.lower() == ".json":
        return "text"
    return "table"


def url_for(thread_id: str, name: str) -> str:
    """Return the chat's link to the raw file."""
    return f"/api/files?threadId={quote(thread_id)}&name={quote(name)}"


def media_type(path: Path) -> str:
    """Return the media type the server sends a file with."""
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_TYPES:
        return IMAGE_TYPES[suffix]
    return {
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix, "text/plain; charset=utf-8")


# ---------------------------------------------------------------- reading


def read(path: Path, name: str, origin: str, url: str = "", show: str = "table") -> FileView:
    """Read a file into a view.

    Parameters
    ----------
    path : Path
        The file.
    name : str
        Its name in the chat.
    origin : {"project", "attachment"}
        Where it comes from.
    url : str
        The chat's link to the raw file.
    show : str
        The view the user asked for.

    Returns
    -------
    FileView
        Tables get columns, the first rows, statistics, totals and a chart; JSON gets a table
        of its values and the text; images their size.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    view = FileView(name=name, kind="binary", origin=origin, url=url, path=str(path))
    view.size_bytes = path.stat().st_size
    if origin == "project" and path.parent == EXAMPLE_DIR:
        view.note = REQUIREMENTS_NOTE if suffix == ".pdf" else EXAMPLE_NOTE
    if suffix in IMAGE_TYPES:
        view.kind, view.show = "image", "image"
        view.image = {"url": url, **_image_size(path)}
        return view
    if suffix in (".csv", ".tsv"):
        header, rows = _read_csv(path)
        _tabulate(view, header, rows)
    elif suffix == ".xlsx":
        header, rows = _read_xlsx(path)
        _tabulate(view, header, rows)
    elif suffix == ".json":
        data = json.loads(path.read_text("utf-8", errors="replace"))
        view.kind = "json"
        view.text = json.dumps(data, indent=2, ensure_ascii=False)[:MAX_TEXT]
        header, rows = _json_rows(data)
        if header:
            _tabulate(view, header, rows, chart=isinstance(data, list))
            view.kind = "json"
    elif suffix in TEXT_TYPES:
        view.kind = "text"
        view.text = path.read_text("utf-8", errors="replace")[:MAX_TEXT]
    elif suffix == ".pdf":
        from gemini_agent.docs import _pdf_pages

        try:
            pages = _pdf_pages(path)
        except ImportError:
            pages = []
        if pages:
            view.kind = "text"
            view.text = "\n\n".join(t for _, t in pages)[:MAX_TEXT]
    if show == "chart" and not view.chart:
        show = "table"
    if show == "table" and not view.table:
        show = "text" if view.text else "table"
    view.show = show
    return view


def _image_size(path: Path) -> dict:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return {"width": im.width, "height": im.height}
    except Exception:  # noqa: BLE001 - the size is a nicety
        return {}


def _read_csv(path: Path) -> Tuple[List[str], List[List[str]]]:
    text = path.read_text("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for i, row in enumerate(reader):
        if i > MAX_READ_ROWS:
            break
        if any(c.strip() for c in row):
            rows.append([c.strip() for c in row])
    if not rows:
        return [], []
    comma_decimal = delimiter != "," and any(
        re.fullmatch(r"-?\d+,\d+", c) for r in rows[1:50] for c in r
    )
    if comma_decimal:
        rows = [rows[0]] + [[re.sub(r"^(-?\d+),(\d+)$", r"\1.\2", c) for c in r] for r in rows[1:]]
    return rows[0], rows[1:]


def _read_xlsx(path: Path) -> Tuple[List[str], List[list]]:
    from openpyxl import load_workbook

    book = load_workbook(path, read_only=True, data_only=True)
    sheet = book.worksheets[0]
    rows = []
    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i > MAX_READ_ROWS:
            break
        cells = [_cell(v) for v in row]
        if any(str(c).strip() for c in cells):
            rows.append(cells)
    book.close()
    if not rows:
        return [], []
    head = next((i for i, r in enumerate(rows) if sum(bool(str(c).strip()) for c in r) >= 2), 0)
    header = [str(c) or f"column {j + 1}" for j, c in enumerate(rows[head])]
    return header, rows[head + 1 :]


def _cell(value):
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return "" if value is None else value


def _json_rows(data) -> Tuple[List[str], List[list]]:
    """Return a table for JSON: records as rows, or a nested object as key and value."""
    if isinstance(data, list) and data and all(isinstance(r, dict) for r in data[:50]):
        header = list(dict.fromkeys(k for r in data[:50] for k in r))
        return header, [[r.get(k, "") for k in header] for r in data[:MAX_READ_ROWS]]
    if isinstance(data, dict):
        flat = list(_flatten(data))
        if flat:
            return ["key", "value"], [[k, v] for k, v in flat]
    return [], []


def _flatten(data, prefix: str = "") -> Iterable[Tuple[str, object]]:
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            yield from _flatten(v, key)
        elif isinstance(v, list):
            yield key, json.dumps(v, ensure_ascii=False)[:200]
        else:
            yield key, v


def unit_of(column: str) -> str:
    """Return the unit a column name states (``heat_demand_mw`` -> MW), or ''."""
    m = re.search(r"[\[(]\s*([^\])]+?)\s*[\])]\s*$", column)
    if m:
        return m.group(1)
    tail = re.split(r"[_\s.]+", column.strip().lower())[-1]
    if tail != column.strip().lower() or column.endswith(("_c", "_k")):
        return UNIT_SUFFIX.get(tail, "")
    return ""


def _number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    try:
        x = float(str(value).replace("−", "-"))
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _tabulate(view: FileView, header: List[str], rows: List[list], chart: bool = True) -> None:
    """Fill a view's table, statistics, totals and chart from a header and rows."""
    view.kind = "table"
    width = max([len(header)] + [len(r) for r in rows[:50]])
    header = list(header) + [f"column {j + 1}" for j in range(len(header), width)]
    rows = [list(r) + [""] * (width - len(r)) for r in rows]
    columns = []
    for j, name in enumerate(header):
        cells = [r[j] for r in rows if str(r[j]).strip() != ""]
        nums = [_number(c) for c in cells]
        if cells and sum(n is not None for n in nums) >= 0.9 * len(cells):
            kind = "number"
        elif cells and all(DATE.match(str(c)) for c in cells[:50]):
            kind = "date"
        else:
            kind = "text"
        columns.append({"name": str(name), "type": kind, "unit": unit_of(str(name))})
    shown = []
    for r in rows[:MAX_ROWS]:
        shown.append(
            [
                _number(v) if c["type"] == "number" and _number(v) is not None else v
                for v, c in zip(r, columns)
            ]
        )
    view.table = {
        "columns": columns,
        "rows": shown,
        "total_rows": len(rows),
        "truncated": len(rows) > MAX_ROWS,
    }
    values = {
        j: [_number(r[j]) for r in rows] for j, c in enumerate(columns) if c["type"] == "number"
    }
    index = {j for j, v in values.items() if _is_index(v)}
    for j, v in values.items():
        clean = [x for x in v if x is not None]
        if j in index or not clean:
            continue
        view.stats.append(
            {
                "column": columns[j]["name"],
                "unit": columns[j]["unit"],
                "min": float(min(clean)),
                "max": float(max(clean)),
                "mean": float(statistics.fmean(clean)),
            }
        )
    x_col = next((j for j, c in enumerate(columns) if c["type"] == "date"), None)
    view.step_hours = _step_hours(rows, columns, x_col, index)
    if x_col is not None and rows:
        view.span = (str(rows[0][x_col]), str(rows[-1][x_col]))
    if view.step_hours:
        for j, v in values.items():
            per_mw = POWER_MW.get(columns[j]["unit"])
            if per_mw is None or j in index:
                continue
            mwh = sum(x for x in v if x is not None) * per_mw * view.step_hours
            value, unit = (mwh / 1000, "GWh") if mwh >= 1000 else (mwh, "MWh")
            view.totals.append(
                {
                    "column": columns[j]["name"],
                    "label": "Energy over the file",
                    "value": float(f"{value:.3g}"),
                    "unit": unit,
                }
            )
    series = [j for j in values if j not in index and any(x is not None for x in values[j])]
    if chart and series and len(rows) > 2:
        if x_col is None and index:
            x_col = min(index)
        x_type = "index" if x_col is None else columns[x_col]["type"]
        xs = list(range(1, len(rows) + 1)) if x_col is None else [r[x_col] for r in rows]
        if x_type == "number":
            xs = [_number(x) for x in xs]
        size = max(1, math.ceil(len(rows) / MAX_POINTS))
        view.chart = {
            "x": "row" if x_col is None else columns[x_col]["name"],
            "x_type": x_type,
            "x_values": xs[::size],
            "series": [
                {
                    "name": columns[j]["name"],
                    "unit": columns[j]["unit"],
                    "values": _bucket_means(values[j], size),
                }
                for j in series[:6]
            ],
        }


def _is_index(values: Sequence[Optional[float]]) -> bool:
    """Return True for a counter column (1, 2, 3 ...): a row number, not a measurement."""
    v = [x for x in values[:500] if x is not None]
    if len(v) < 3 or any(x != int(x) for x in v):
        return False
    steps = {b - a for a, b in zip(v, v[1:])}
    return steps == {1.0}


def _step_hours(rows, columns, x_col, index) -> Optional[float]:
    """Return the regular time step in hours, from time stamps or an hour or day counter."""
    if x_col is not None:
        stamps = []
        for r in rows[:200]:
            try:
                stamps.append(datetime.fromisoformat(str(r[x_col])))
            except ValueError:
                return None
        steps = {(b - a).total_seconds() / 3600 for a, b in zip(stamps, stamps[1:])}
        if len(steps) != 1:
            return None
        step = steps.pop()
        return step if step > 0 else None
    for j in index:
        name = columns[j]["name"].lower()
        if re.search(r"\bhour|_h$|^h$", name):
            return 1.0
        if re.search(r"\bday", name):
            return 24.0
    return None


def _bucket_means(values: Sequence[Optional[float]], size: int) -> List[Optional[float]]:
    out = []
    for i in range(0, len(values), size):
        chunk = [x for x in values[i : i + size] if x is not None]
        out.append(round(statistics.fmean(chunk), 4) if chunk else None)
    return out


# ---------------------------------------------------------------- images in documents


IMAGE_DIRECTIVE = re.compile(r"^\s*\.\.\s+(?:image|figure)::\s*(\S+)", re.I)
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)")
DOC_IMAGE_ROOTS = ("src/gemini_documentation/", "hackathon/docs/")


def section_images(root: Path, source: str, section: str, limit: int = 3) -> List[dict]:
    """Return the figures in one section of a documentation file, for its source card.

    Parameters
    ----------
    root : Path
        The repository root.
    source : str
        The passage's file, relative to ``root`` (``.rst`` or ``.md``).
    section : str
        The passage's heading path (``"Parent > Heading"``, as the search writes it).
    limit : int
        At most this many figures.

    Returns
    -------
    list of dict
        ``url`` (``/api/doc-image?path=...``) and ``caption``; only images that exist under
        the documentation folders.
    """
    rel = source.replace("\\", "/")
    path = root / rel
    if not rel.startswith(DOC_IMAGE_ROOTS) or path.suffix.lower() not in (".rst", ".md"):
        return []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    target = section.split(" > ")[-1].strip().lower() if section else ""
    current, found = "", []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        heading = _heading(line, nxt, path.suffix.lower())
        if heading is not None:
            current = heading.lower()
            continue
        if target and current != target:
            continue
        m = IMAGE_DIRECTIVE.match(line)
        if m:
            caption = _rst_caption(lines, i)
            found.append((m.group(1), caption))
        for alt, link in MD_IMAGE.findall(line):
            found.append((link, alt))
    out = []
    for link, caption in found:
        image = (path.parent / link).resolve()
        try:
            image_rel = image.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if image.suffix.lower() not in IMAGE_TYPES or not image_rel.startswith(DOC_IMAGE_ROOTS):
            continue
        if image.is_file():
            out.append(
                {
                    "url": f"/api/doc-image?path={quote(image_rel)}",
                    "caption": caption or image.stem.replace("_", " "),
                }
            )
        if len(out) >= limit:
            break
    return out


def _heading(line: str, nxt: str, suffix: str) -> Optional[str]:
    from gemini_agent.docs import MD_HEADING, RST_RULE

    if suffix == ".md":
        m = MD_HEADING.match(line)
        return m.group(2).strip() if m else None
    if line.strip() and not line.startswith(" ") and RST_RULE.match(nxt):
        return re.sub(r"[*`]", "", line.strip())
    return None


def _rst_caption(lines: Sequence[str], at: int) -> str:
    """Return an image's ``:alt:`` text, or a figure's caption (its indented paragraph)."""
    for line in lines[at + 1 : at + 8]:
        m = re.match(r"^\s+:alt:\s*(.+)$", line)
        if m:
            return m.group(1).strip()
        if line.strip() and not line.strip().startswith(":") and line.startswith(" "):
            return line.strip()
        if line.strip() and not line.startswith(" "):
            break
    return ""


def doc_image_path(root: Path, rel: str) -> Optional[Path]:
    """Return a documentation image's path when ``rel`` names one inside the docs folders."""
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel.startswith(DOC_IMAGE_ROOTS):
        return None
    path = (root / rel).resolve()
    try:
        inside = path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    if not inside.startswith(DOC_IMAGE_ROOTS):
        return None
    if path.suffix.lower() not in IMAGE_TYPES or not path.is_file():
        return None
    return path
