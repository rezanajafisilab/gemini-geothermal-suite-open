"""Each doublet's planned stops: read from a year, said in words, and the user's dates checked.

A doublet runs at most ``operating_days`` days a year (the challenge's 330), so it stops at least
365 - ``operating_days`` days. By default Dioscuri places one block per doublet in the weeks that
need the least brine (``dioscuri_plant.year.stop_ranges``); on the inputs card the user may give
the dates instead (``DesignBrief.doublet_stops``): one block or several ranges per doublet. These
helpers read a year's stops however they were set (``stop_ranges``, or the one block per doublet
of older results, ``stop_days``), say them, and check the user's dates before a run.
"""

from __future__ import annotations

import json
from typing import List, Optional, Sequence, Tuple

DAYS = 365
YEAR = 2027  # the demand files' year: day 0 is 1 Jan 2027
MAX_DOUBLETS = 3
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

Range = Tuple[int, int]


def ranges_of(year) -> List[List[Range]]:
    """Return each doublet's stops as (first, last) days of 2027, 0-based and inclusive.

    Parameters
    ----------
    year : YearResult or YearSummary or None
        A design's year: its ``stop_ranges`` when it has them, else its ``stop_days`` (one block
        per doublet, older results).
    """
    if year is None:
        return []
    ranges = getattr(year, "stop_ranges", None)
    if ranges:
        return [[(int(a), int(b)) for a, b in r] for r in ranges]
    blocks = getattr(year, "stop_days", None) or []
    return [[(int(s[0]), int(s[1]))] if s and len(s) >= 2 else [] for s in blocks]


def stopped(ranges: Sequence[Sequence[Range]], k: int, day: int) -> bool:
    """Return True when doublet ``k`` (0-based) is in a planned stop on ``day`` (0-based)."""
    return k < len(ranges) and any(a <= day <= b for a, b in ranges[k])


def days_off(ranges: Sequence[Range]) -> int:
    """Return how many days one doublet's stops take."""
    return sum(int(b) - int(a) + 1 for a, b in ranges)


def day_name(i: int) -> str:
    """Return a 0-based day of 2027 as "9 Jul"."""
    m = 0
    i = int(i)
    while m < 11 and i >= MONTH_DAYS[m]:
        i -= MONTH_DAYS[m]
        m += 1
    return f"{i + 1} {MONTHS[m]}"


def span_words(ranges: Sequence[Range], to: str = " to ") -> str:
    """Return one doublet's stops in words: "9 Jul to 12 Aug", or several joined by "and"."""
    parts = [f"{day_name(a)}{to}{day_name(b)}" for a, b in ranges]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def users(brief, k: int) -> bool:
    """Return True when doublet ``k`` (0-based) stops on the user's dates (the inputs card)."""
    given = getattr(brief, "doublet_stops", None) or []
    return k < len(given) and bool(given[k])


def why(brief, k: int, operating_days: int) -> str:
    """Return why doublet ``k`` stops when it does: the user's dates, or Dioscuri's placing."""
    if users(brief, k):
        return f"your dates (the {operating_days}-day cap leaves {DAYS - operating_days} days off)"
    cap = f"the {operating_days}-day cap"
    return (
        f"{cap}; placed in the weeks that need the least brine (also the window for yearly "
        "maintenance)"
    )


def summary(year, brief) -> str:
    """Return the doublets' stops in one phrase: how long each is, and who placed them."""
    ranges = ranges_of(year)
    if not ranges:
        return ""
    lengths = {days_off(r) for r in ranges if r}
    long = f"{lengths.pop()} days each" if len(lengths) == 1 else "days off differ by doublet"
    mine = [k for k in range(len(ranges)) if users(brief, k)]
    if not mine:
        return f"{long}, placed by Dioscuri in the weeks that need the least brine"
    if len(mine) == len(ranges):
        return f"{long}, on your dates"
    names = " and ".join(f"doublet {k + 1}" for k in mine)
    return f"{long}; {names} on your dates, the others in the weeks that need the least brine"


def row(brief, operating_days: int) -> Tuple[str, str, str]:
    """Return the inputs card's "Doublet stops" row: its value, its source and its kind."""
    off = max(0, DAYS - int(operating_days))
    given = list(getattr(brief, "doublet_stops", None) or [])
    if not any(given):
        return (
            f"{off} days a year each, in one block in the weeks that need the least brine; "
            "Dioscuri staggers the doublets",
            "Dioscuri's default (choose below)",
            "assumed",
        )
    parts = []
    for k in range(max(len(given), 1)):
        mine = [(int(a), int(b)) for a, b in given[k]] if k < len(given) else []
        parts.append(
            f"doublet {k + 1}: {span_words(mine)} ({days_off(mine)} days)"
            if mine
            else f"doublet {k + 1}: in the quietest weeks"
        )
    rest = "; any other doublet in the quietest weeks" if len(given) < MAX_DOUBLETS else ""
    return "; ".join(parts) + rest, "you", "asked"


def parse(value) -> List[List[List[int]]]:
    """Return the user's stops, ``[[[first, last], ...] per doublet]``, from the card's JSON.

    Raises
    ------
    ValueError
        When the value is not a list of doublets, each a list of [first, last] whole days.
    """
    data = json.loads(value) if isinstance(value, str) else value
    if data in (None, "", []):
        return []
    if not isinstance(data, list) or len(data) > MAX_DOUBLETS:
        raise ValueError(f"give at most {MAX_DOUBLETS} doublets, each a list of date ranges")
    out: List[List[List[int]]] = []
    for doublet in data:
        if doublet in (None, []):
            out.append([])
            continue
        if not isinstance(doublet, list):
            raise ValueError("each doublet's stops are a list of date ranges")
        rows = []
        for r in doublet:
            if not (isinstance(r, (list, tuple)) and len(r) == 2):
                raise ValueError("each range is a first and a last day")
            a, b = (float(x) for x in r)
            if a != int(a) or b != int(b):
                raise ValueError("days are whole days")
            rows.append([int(a), int(b)])
        out.append(sorted(rows))
    while out and not out[-1]:
        out.pop()
    return out


def check(stops: Sequence[Sequence[Sequence[int]]], operating_days: int) -> Optional[str]:
    """Return what is wrong with the user's stops, or None: in 2027, no overlap, enough days.

    Every doublet given dates must stop at least 365 - ``operating_days`` days, so that the cap
    on operating days holds; a doublet without dates is placed by Dioscuri.
    """
    need = DAYS - int(operating_days)
    for k, ranges in enumerate(stops):
        if not ranges:
            continue
        name = f"Doublet {k + 1}"
        for a, b in ranges:
            if not 0 <= a <= b < DAYS:
                return f"{name}: every range must fall in {YEAR}, its first day before its last."
        ordered = sorted((int(a), int(b)) for a, b in ranges)
        for (a1, b1), (a2, b2) in zip(ordered, ordered[1:]):
            if a2 <= b1:
                return f"{name}: {span_words([(a1, b1)])} and {span_words([(a2, b2)])} overlap."
        off = days_off(ordered)
        if off < need:
            return (
                f"{name}: {off} days off, fewer than the {need} the {operating_days}-day cap "
                "needs."
            )
    return None
