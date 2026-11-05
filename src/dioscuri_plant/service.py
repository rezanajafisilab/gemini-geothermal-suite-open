"""Planned service of the surface units: each one out for a few days a year, in its quietest weeks.

Off by default (``Rules.planned_service``). When on, every unit the plant has is taken out once
a year for ``DAYS_OUT`` days: the heating units (heat pump, boiler, heat exchanger) in the weeks
of least heat demand, the cooling units (chillers, absorption chiller) in the weeks of least cold
demand, one after the other so no two are out together. The doublets need nothing more: each
already stops 35 days a year (the 330 operating days), and those stops count as taken on the
heating side, so no heating unit is serviced while a doublet stands (both would otherwise go to
the same quiet summer weeks, and the plant would lose two units at once). A boiler or chiller
bank built as several units is serviced one unit at a time. The lengths are typical annual
service windows (assumed): heat pump two weeks (compressor overhaul), boiler and chillers one
week, exchanger three days (plate cleaning), absorption chiller one week.
"""

from __future__ import annotations

from typing import List, Mapping, Optional, Sequence, Tuple

import numpy as np

DAYS_OUT = {
    "heat pump": 14,
    "boiler": 7,
    "heat exchanger": 3,
    "chillers": 7,
    "absorption": 7,
    "electric boiler": 2,  # DEA 2026 sheet 41: planned outage 0.2 weeks a year
}
HEATING = ("heat pump", "boiler", "electric boiler", "heat exchanger")
COOLING = ("chillers", "absorption")


def _quietest(load: np.ndarray, days: int, taken: List[Tuple[int, int]]) -> int:
    """Return the first day of the quietest ``days`` in a row that overlaps nothing taken."""
    sums = np.convolve(load, np.ones(days), mode="valid")
    for start in np.argsort(sums, kind="stable"):
        end = int(start) + days - 1
        if all(end < a or start > b for a, b in taken):
            return int(start)
    return 0


def windows(
    heat: Sequence[float],
    cool: Sequence[float],
    boiler_units: int = 1,
    chiller_units: int = 1,
    electric_boiler_units: int = 0,
    stops: Sequence[Tuple[int, int]] = (),
    plan: Optional[Mapping[str, Tuple[str, Sequence[Tuple[int, int]]]]] = None,
    auto: bool = True,
    has: Optional[Mapping[str, bool]] = None,
) -> Tuple[Tuple[str, int, int], ...]:
    """Return every unit's service window as ``Plant.outages`` entries: (unit, first, last).

    ``boiler_units``, ``chiller_units``, ``electric_boiler_units``: 0 when the plant has none.
    ``stops``: the doublets' planned stops (first, last day), taken on the heating side: a heating
    unit's service never falls inside one. ``plan``: the user's choice per unit type, (mode,
    ranges): "off", "auto" (the quietest weeks) or "dates" (each range takes one unit out, a
    bank's units in turn; units without a range go in the quietest weeks). A type not in
    ``plan`` is serviced when ``auto`` (``Rules.planned_service``). ``has``: whether the plant
    has the single units (heat pump, heat exchanger, absorption chiller); a unit it lacks gets
    no window, whatever the plan says.
    """
    heat = np.asarray(heat, dtype=float)
    cool = np.asarray(cool, dtype=float)
    plan = dict(plan or {})
    has = dict(has or {})
    banks = {
        "boiler": (boiler_units, "boiler unit"),
        "chillers": (chiller_units, "chiller unit"),
        "electric boiler": (electric_boiler_units, "electric boiler unit"),
    }
    out: List[Tuple[str, int, int]] = []
    for side, load in ((HEATING, heat), (COOLING, cool)):
        taken: List[Tuple[int, int]] = (
            [(int(a), int(b)) for a, b in stops] if side is HEATING else []
        )
        # The user's dates first, so the quietest weeks Dioscuri picks keep clear of them.
        order = sorted(side, key=lambda u: plan.get(u, ("", ()))[0] != "dates")
        for unit in order:
            mode, ranges = plan.get(unit, ("auto" if auto else "off", ()))
            if mode == "off":
                continue
            units, one = banks.get(unit, (1 if has.get(unit, True) else 0, unit))
            if units < 1:
                continue
            count, name = (units, one) if units > 1 else (1, unit)
            given = [(int(a), int(b)) for a, b in ranges] if mode == "dates" else []
            for k in range(count):
                if k < len(given):
                    start, end = given[k]
                else:
                    days = DAYS_OUT[unit]
                    start = _quietest(load, days, taken)
                    end = start + days - 1
                taken.append((start, end))
                out.append((name, start, end))
            # More dates than units: each further range takes a unit out again, in turn.
            for a, b in given[count:]:
                taken.append((a, b))
                out.append((name, a, b))
    return tuple(out)
