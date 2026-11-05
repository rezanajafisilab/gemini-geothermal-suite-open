"""What GEMINI as released would have given for our designs, next to the fixed GEMINI.

Searches the challenge's designs (``gemini_agent.engine``), then runs the chosen one's doublet
and the best heat-pump design's heat pump on GEMINI as released in ``src/`` and on the copy with
``patches/`` applied, and writes ``BUG_IMPACT.md`` beside this folder. Run from the repository
root:

    PYTHONPATH=src python hackathon/gemini_bughunt/scripts/14_bug_impact_on_designs.py
"""

from pathlib import Path

from gemini_agent import engine, gemini_runtime
from gemini_agent.contract import DesignBrief

OUT = Path(__file__).resolve().parents[1] / "BUG_IMPACT.md"


def fmt(x):
    """Return a cell: '—' for a missing value, otherwise 3 significant digits."""
    if x is None:
        return "—"
    return f"{x:.3g}" if abs(x) < 1000 else f"{x:,.0f}"


def change(released, fixed):
    """Return the released value's error against the fixed one, as a percentage or a word."""
    if released is None or fixed is None:
        return "—"
    if fixed == 0:
        return "same" if released == 0 else "fixed gives 0"
    return f"{(released - fixed) / abs(fixed):+.0%}"


def main():
    """Write the table for the chosen design and the best design with a heat pump."""
    fixed = gemini_runtime.load("fixed")
    outcome = engine.search(DesignBrief())
    shown = [outcome.chosen]
    shown += [e for e in engine.ranked(outcome) if e.alternative.heat_pump and e not in shown][:1]
    lines = [
        "# What GEMINI as released would have given for our designs",
        "",
        f"GEMINI {fixed.version} (`development`, released 29 Oct 2026), as released and with "
        f"our {len(fixed.patches)} patches in `patches/`. The challenge's reservoir and brine "
        "(87 °C at 2,500 m, 1,030 kg/m³, 0.40 mPa·s), doublets at 300 m³/h, network 100/60 °C. "
        "Written by `scripts/14_bug_impact_on_designs.py`.",
        "",
    ]
    for entry in shown:
        alt = entry.alternative
        lines += [
            f"## {alt.code}: {alt.name}",
            "",
            "| Quantity | Released | Fixed | Released is off by | Cause |",
            "|---|---|---|---|---|",
        ]
        for r in engine.bug_impact(entry):
            unit = f" {r['unit']}" if r["unit"] else ""
            lines.append(
                f"| {r['quantity']}{(' (' + r['unit'] + ')') if unit else ''} | "
                f"{fmt(r['released'])} | {fmt(r['fixed'])} | "
                f"{change(r['released'], r['fixed'])} | {r['bugs']} |"
            )
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
