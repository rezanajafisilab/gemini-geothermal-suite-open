"""GEMINI's models and simulator, as TNO released them and with the team's fixes.

Two versions run side by side in one process:

- ``"asis"``: the packages in ``src/`` exactly as released (upstream ``development``);
- ``"fixed"``: a copy of ``gemini_model`` and ``gemini_simulator`` with the patch files in
  ``hackathon/gemini_bughunt/patches`` applied, imported as ``gemini_model_fixed`` and
  ``gemini_simulator_fixed``.

GEMINI's own files are never edited. The fixed copy is built on first use in a cache folder
named after a hash of the GEMINI sources and the patches, so a new GEMINI release or a new
patch rebuilds it. The code that runs is exactly the patches the team sends upstream, so
"what the released code would have done" is one call away (``load("asis")``).
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PATCH_DIR = ROOT / "hackathon" / "gemini_bughunt" / "patches"
CACHE = Path(
    os.environ.get(
        "DIOSCURI_GEMINI_CACHE", ROOT / "hackathon" / "evals" / "runs" / "tmp" / "gemini"
    )
)
PACKAGES = ("gemini_model", "gemini_simulator")
SUFFIX = "_fixed"


class PatchError(RuntimeError):
    """A patch does not apply to this GEMINI release."""


@dataclass
class Gemini:
    """One version of GEMINI: the modules the tools call.

    Attributes
    ----------
    variant : str
        ``"asis"`` or ``"fixed"``.
    build_project : callable
        ``project_loader.build_project``: a project dict to a Solver.
    kpi : module
        ``gemini_simulator.kpi``.
    HeatpumpBasic, Boiler : type
        Model classes used outside a project graph.
    patches : list of str
        The patch files applied (empty for ``"asis"``).
    version : str
        GEMINI's version from ``pyproject.toml``.
    """

    variant: str
    build_project: object
    kpi: ModuleType
    HeatpumpBasic: type
    Boiler: type
    patches: List[str]
    version: str
    well_flow: ModuleType = None  # the nodal well solve and its well-segment builder


_LOADED: Dict[str, Gemini] = {}


def patches() -> List[Path]:
    """Return the patch files, in the order they are applied."""
    return sorted(PATCH_DIR.glob("*.diff"))


def version() -> str:
    """Return GEMINI's version as ``pyproject.toml`` states it."""
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    return m.group(1) if m else "unknown"


def _fingerprint() -> str:
    h = hashlib.sha256()
    for pkg in PACKAGES:
        for path in sorted((SRC / pkg).rglob("*.py")):
            h.update(str(path.relative_to(SRC)).encode())
            h.update(path.read_bytes())
    for path in patches():
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:12]


def apply_patch(text: str, root: Path) -> List[str]:
    """Apply a unified diff to the files under ``root``; return the paths it changed.

    A small, strict applier: every context and removed line must match exactly (line
    endings included), so a patch that no longer fits a new GEMINI release fails loudly
    instead of applying somewhere else. A hunk may move by up to 50 lines.

    Raises
    ------
    PatchError
        When a file is missing or a hunk does not match.
    """
    changed = []
    for block in re.split(r"(?m)^--- a/", text)[1:]:
        lines = block.split("\n")
        path = lines[0].strip()
        if not lines[1].startswith("+++ "):
            raise PatchError(f"{path}: no '+++' line")
        target = root / path
        if not target.is_file():
            raise PatchError(f"{path}: not found")
        content = target.read_bytes().decode("utf-8").splitlines(keepends=True)
        offset = 0
        i = 2
        while i < len(lines):
            head = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", lines[i])
            if not head:
                i += 1
                continue
            start = int(head.group(1)) - 1
            old, new = [], []
            i += 1
            while i < len(lines) and not lines[i].startswith("@@"):
                line = lines[i]
                if line.startswith("\\"):  # "\ No newline at end of file"
                    for side in (old, new):
                        if side and side[-1].endswith("\n"):
                            side[-1] = side[-1][:-1]
                elif line[:1] in (" ", "-", "+"):
                    body = line[1:] + "\n"
                    if line[0] in (" ", "-"):
                        old.append(body)
                    if line[0] in (" ", "+"):
                        new.append(body)
                i += 1
            at = _find(content, old, start + offset)
            if at is None:
                raise PatchError(f"{path}: a hunk near line {start + 1} does not match")
            content[at : at + len(old)] = new
            offset += len(new) - len(old)
        target.write_bytes("".join(content).encode("utf-8"))
        changed.append(path)
    return changed


def _find(content: List[str], old: List[str], near: int) -> Optional[int]:
    for delta in range(0, 51):
        for at in {near - delta, near + delta}:
            if 0 <= at <= len(content) - len(old) and content[at : at + len(old)] == old:
                return at
    return None


def build_fixed(cache: Path = CACHE) -> Path:
    """Build (once) the patched copy of GEMINI and return the folder that holds it.

    Parameters
    ----------
    cache : Path
        Where the copies live, one folder per fingerprint of the sources and patches.

    Returns
    -------
    Path
        A folder with ``gemini_model_fixed`` and ``gemini_simulator_fixed``.
    """
    target = cache / _fingerprint()
    if (target / ".complete").is_file():
        return target
    tmp = target.with_name(target.name + ".building")
    shutil.rmtree(tmp, ignore_errors=True)
    for pkg in PACKAGES:
        shutil.copytree(SRC / pkg, tmp / "src" / pkg, ignore=shutil.ignore_patterns("__pycache__"))
    applied = []
    for patch in patches():
        apply_patch(patch.read_bytes().decode("utf-8"), tmp)
        applied.append(patch.name)
    names = re.compile(r"\b(" + "|".join(PACKAGES) + r")\b")
    for pkg in PACKAGES:
        for path in (tmp / "src" / pkg).rglob("*.py"):
            raw = path.read_bytes().decode("utf-8")
            path.write_bytes(names.sub(lambda m: m.group(1) + SUFFIX, raw).encode("utf-8"))
        (tmp / "src" / pkg).rename(tmp / (pkg + SUFFIX))
    shutil.rmtree(tmp / "src")
    (tmp / ".complete").write_text("\n".join(applied) + "\n", encoding="utf-8")
    shutil.rmtree(target, ignore_errors=True)
    tmp.rename(target)
    return target


def load(variant: str = "fixed") -> Gemini:
    """Return GEMINI's modules as released (``"asis"``) or with the team's fixes.

    Parameters
    ----------
    variant : {"fixed", "asis"}
        Which version.

    Returns
    -------
    Gemini
        The project loader, the KPI module and the model classes the tools use.
    """
    if variant in _LOADED:
        return _LOADED[variant]
    if variant == "asis":
        if str(SRC) not in sys.path:
            sys.path.append(str(SRC))
        suffix, applied = "", []
    elif variant == "fixed":
        folder = build_fixed()
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
        suffix = SUFFIX
        applied = (folder / ".complete").read_text(encoding="utf-8").split()
    else:
        raise ValueError(f"variant must be 'asis' or 'fixed', not {variant!r}")

    def mod(name: str) -> ModuleType:
        pkg, _, rest = name.partition(".")
        return importlib.import_module(pkg + suffix + "." + rest)

    gemini = Gemini(
        variant=variant,
        build_project=mod("gemini_simulator.project_loader").build_project,
        kpi=mod("gemini_simulator.kpi"),
        HeatpumpBasic=mod("gemini_model.heatpump.heatpump_basic").HeatpumpBasic,
        Boiler=mod("gemini_model.boiler.boiler").Boiler,
        patches=applied,
        version=version(),
        well_flow=mod("gemini_simulator.well_flow"),
    )
    _LOADED[variant] = gemini
    return gemini
