"""Minimum loads and trips: what the daily dispatch hides about running the plant.

A unit cannot run below its minimum load: on a day its mean output is above zero but below one
unit's minimum, it runs at its minimum part of the day and stops (it cycles), which wears it
and, for a boiler, costs efficiency. The year model's dispatch is daily and does not see this,
so it is counted here, unit by unit, without changing the year: the days below the minimum and
the starts (each day it runs after a day it did not, and each cycling day).

Trips: a doublet's ESP stops now and then without warning (a grid dip, a gas lock, a sensor),
and is restarted after some hours; the boiler (and the heat pump, if it has room) carries the
heat meanwhile. The expected heat moved to the boiler is the trips a year times the hours to
restart times the doublet's mean heat on its running days.

All the figures are assumed typical values (no Dutch statistic was found for trips): minimum
loads from the turndown of each kind of unit, four trips a doublet a year, eight hours each.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

# One unit's minimum load as a share of its size (typical turndown; assumed).
MIN_LOAD = {
    "boiler": 0.20,  # modulating burner, turndown 5:1
    "heat_pump": 0.30,  # large screw or turbo compressors, about 3:1
    "electric_boiler": 0.05,  # electrode boilers modulate almost to zero
    "chillers": 0.15,  # variable-speed centrifugal chillers
    "absorption": 0.25,  # single-effect LiBr
}
NAMES = {
    "boiler": "gas boiler",
    "heat_pump": "heat pump",
    "electric_boiler": "electric boiler",
    "chillers": "electric chillers",
    "absorption": "absorption chiller",
}
TRIPS_PER_DOUBLET_YEAR = 4.0
TRIP_HOURS = 8.0
SOURCE = (
    "assumed typical values: minimum loads from each unit's turndown (boiler 20 %, heat pump "
    "30 %, electric boiler 5 %, chillers 15 %, absorption 25 % of one unit); ESP trips 4 a "
    "doublet a year, 8 hours each to restart"
)


def check(
    output_mw: Dict[str, np.ndarray],
    unit_mw: Dict[str, float],
    geo_mw: np.ndarray,
    doublets: int,
) -> Dict[str, object]:
    """Return each unit's days below its minimum load and starts, and the trips' heat.

    Parameters
    ----------
    output_mw : dict of array
        Each unit kind's daily mean output (365 values, MW).
    unit_mw : dict of float
        One unit's size per kind (MW; 0 when the design has none).
    geo_mw : array
        The doublets' daily heat (MW, all of them).
    doublets : int
        How many doublets.

    Returns
    -------
    dict
        ``units`` (kind, name, minimum MW, days below it, starts), ``trips`` (a year, hours each,
        GWh moved to the boiler) and ``source``.
    """
    units: List[Dict[str, object]] = []
    for kind, out in output_mw.items():
        size = float(unit_mw.get(kind, 0.0) or 0.0)
        if size <= 0:
            continue
        out = np.asarray(out, dtype=float)
        floor = MIN_LOAD[kind] * size
        on = out > 1e-6
        below = on & (out < floor)
        starts = int(np.sum(on[1:] & ~on[:-1])) + int(on[0]) + int(np.sum(below))
        units.append(
            {
                "kind": kind,
                "name": NAMES[kind],
                "minimum_mw": round(floor, 2),
                "days_below": int(np.sum(below)),
                "days_on": int(np.sum(on)),
                "starts": starts,
            }
        )
    geo = np.asarray(geo_mw, dtype=float)
    running = geo > 1e-6
    mean_mw = float(geo[running].mean()) if running.any() else 0.0
    moved = TRIPS_PER_DOUBLET_YEAR * TRIP_HOURS * mean_mw / max(doublets, 1) * doublets / 1000
    return {
        "units": units,
        "trips": {
            "per_doublet_year": TRIPS_PER_DOUBLET_YEAR,
            "hours_each": TRIP_HOURS,
            "boiler_gwh": round(moved, 3) if doublets else 0.0,
        },
        "source": SOURCE,
    }


def warnings(result: Dict[str, object]) -> List[str]:
    """Return a sentence for each unit that cycles on more than a month of days."""
    out = []
    for u in result.get("units", []):
        if u["days_below"] > 30:
            many = u["name"].endswith("s")
            out.append(
                f"The {u['name']} {'run' if many else 'runs'} below {'their' if many else 'its'} "
                f"minimum load ({u['minimum_mw']:g} MW a unit) on {u['days_below']} days, so "
                f"{'they cycle' if many else 'it cycles'} on and off those days: smaller units, "
                "or one more, would run steadier."
            )
    return out
