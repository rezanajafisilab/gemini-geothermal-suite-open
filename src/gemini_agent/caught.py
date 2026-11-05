"""Caught and fixed: the failures the team found and fixed, with how each was found and guarded.

The list is one file, ``data/caught_and_fixed.json``: the Evidence tab reads it through
``workbench.evidence`` and ``markdown`` writes it for the report
(``hackathon/docs/caught_and_fixed.md``; ``python -m gemini_agent.caught`` writes it again).
Each item says what failed, how it was found (the source document), the fix (commit, ADR or
GEMINI patch) and the tests that guard it. The physics bugs in GEMINI keep their codes F1-F10;
the agent's failures from the understanding review have their own (U1 ...), so the two never
clash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parent / "data" / "caught_and_fixed.json"
ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "hackathon" / "docs" / "caught_and_fixed.md"

GROUPS = {
    "gemini": "GEMINI's physics code",
    "model": "Dioscuri's plant and subsurface model",
    "costs": "Costs",
    "agent": "The agent: reading, planning, answers",
    "app": "The app",
}


def load() -> dict:
    """Return the list as stored: ``{"updated", "items"}``."""
    return json.loads(DATA.read_text("utf-8"))


def items() -> List[Dict]:
    """Return the items, each with its group's name."""
    return [dict(it, group_label=GROUPS.get(it["group"], it["group"])) for it in load()["items"]]


def view() -> dict:
    """Return what the Evidence tab shows: the items and counts by group, fixed and guarded."""
    rows = items()
    groups = []
    for key, label in GROUPS.items():
        mine = [r for r in rows if r["group"] == key]
        if mine:
            groups.append(
                {
                    "key": key,
                    "label": label,
                    "total": len(mine),
                    "guarded": sum(bool(r["tests"]) for r in mine),
                }
            )
    return {
        "updated": load()["updated"],
        "items": rows,
        "groups": groups,
        "total": len(rows),
        "guarded": sum(bool(r["tests"]) for r in rows),
        "avoided": sum(r["status"] == "avoided" for r in rows),
    }


def _fix_refs(it: Dict) -> str:
    refs = []
    if it.get("patch"):
        refs.append(f"patch `{it['patch']}`")
    if it.get("commit"):
        refs.append(f"commit `{it['commit']}`")
    if it.get("adr"):
        refs.append(it["adr"])
    return ", ".join(refs) or "no reference"


def markdown() -> str:
    """Return the list as Markdown for the report, grouped, one entry per failure."""
    v = view()
    out = [
        "# Caught and fixed",
        "",
        f"Failures the team found in GEMINI, in Dioscuri's model and in the agent, and fixed: "
        f"{v['total']} in all, {v['guarded']} guarded by a test. Each says what failed, how it "
        "was found, the fix and the tests that guard it. The physics bugs in GEMINI keep their "
        "codes F1-F10 (`hackathon/gemini_bughunt/README.md`); the agent's failures from the "
        "understanding review are U1 ... (that review calls them F1 ...). "
        f"{v['avoided']} GEMINI bugs are not patched but kept out of the designs, said so.",
        "",
        "Written from `src/gemini_agent/data/caught_and_fixed.json` (the Evidence tab reads the "
        f"same file) by `python -m gemini_agent.caught`. Updated {v['updated']}.",
        "",
        "| Group | Items | Guarded by a test |",
        "|---|---|---|",
    ]
    out += [f"| {g['label']} | {g['total']} | {g['guarded']} |" for g in v["groups"]]
    for g in v["groups"]:
        out += ["", f"## {g['label']}", ""]
        for it in (r for r in v["items"] if r["group"] == g["key"]):
            label = f" ({it['source_label']})" if it.get("source_label") else ""
            avoided = " *Avoided, not patched.*" if it["status"] == "avoided" else ""
            tests = "; ".join(f"`{t}`" for t in it["tests"]) if it["tests"] else "no test guards it"
            out += [
                f"### {it['id']}. {it['title']}{label}",
                "",
                f"- **What failed.** {it['failed']}",
                f"- **How it was found.** {it['found']} (`{it['found_in']}`).",
                f"- **Fix.** {it['fix']}{avoided} ({_fix_refs(it)})",
                f"- **Guarded by.** {tests}",
                "",
            ]
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    """Write the Markdown for the report."""
    REPORT.write_text(markdown(), "utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)} ({view()['total']} items)")


if __name__ == "__main__":
    main()
