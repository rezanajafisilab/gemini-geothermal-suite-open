# ADR-0016: Two real projects, plant options, operations and the permit pack

- Status: **accepted** (2 Nov 2026). Amends [ADR-0015](ADR-0015-provenance-sweep-outages.md)
  (the cooling check, the canvas) and finishes most of the plan of 2 Nov's phase D.
- Evidence: `unit_test/dioscuri_plant/test_plant_options.py`; `unit_test/gemini_agent/`
  `test_projects.py`, `test_cooling_check.py`, `test_gemini_export.py`, `test_permit_pack.py`;
  `frontend/src/tabs/energy/operations.test.ts`, `frontend/src/tabs/design/plant.test.ts`.

## Context

- The user asked for Trias Westland and Haagse Aardwarmte Leyweg as projects like the challenge
  district, then: the canvas's crossings, free cooling, absorption chillers in the cooling
  check, the bought gas's upstream CO₂, own solar, and phase D (heat storage, minimum loads and
  trips, a second reservoir, GEMINI export, operations mode, a permit and subsidy pack).
- The challenge's cooling network supplies 20 °C: cold enough outside air can cool it directly.
- The design must work without weather data (2 Nov).
- GEMINI ships no operating data: its database is external.

## Decision

1. **Real projects built in** (`projects.BUILTINS`). Reservoir, brine, permits and well
   spacing from NLOG (PanTerra 2020 for Trias; the ministry's decision V-109 for HAL); demand
   assumed and labelled so on the inputs card, each row with its source. Network returns 5 K
   below the published injection temperatures. The wells are priced at the project's spacing.
2. **One weather year** (`dioscuri_plant.weather`): KNMI De Bilt normals 1991-2020
   (temperature, humidity, global radiation), wet bulb by Stull, day length from the sun.
3. **Free cooling** (`Rules.free_cooling`, a switch): the towers cool the network through a
   plate exchanger when the wet bulb + 6 K is below the return, part of the way otherwise, up
   to the towers' size. Default off; the default design's cold drops from 42 to 23 €/MWh.
4. **Own solar** (`Rules.solar_mwp`): KNMI radiation scaled to PBL's 855 full-load hours;
   used in daylight first, the rest sold at PBL's long-term 71 €/MWh; priced at PBL's base
   amount (88.9 €/MWh, capital in it) rather than an invented capex.
5. **Heat store** (`Rules.storage_mwh`): DEA steel tanks (3.0 M€2015/GWh, 0.2 %/day, 2.9 MW
   per 175 MWh). The year runs twice: the store charges on days the geothermal has room and
   gives back on days it is at its best or stopped. When it saves nothing, the first year
   stands and says so. At DEA's price it does not pay on the challenge: shown, not hidden.
6. **Upstream CO₂ of the gas bought**: 54 kg CO₂-eq/MWh (co2emissiefactoren.nl 2025, an upper
   value), beside the total, as the flare's methane slip is.
7. **Absorption in the cooling check**: the kernel's absorption option, fed the brine our year
   gives it; its limits counted only on the days it was meant to run.
8. **Minimum loads and trips** (`dioscuri_plant.operability`): each unit's days below one
   unit's minimum load (it cycles) and its starts; ESP trips' heat moved to the boiler. All
   figures assumed typical values, said so. A card row and a line in the chat's notes, not
   a warning on every design.
9. **Second aquifer** (`Rules.second_aquifer_*`, `Rules.aquifer_at`): doublets drilled to it
   see its thickness and permeability (hydrostatic pressure, the gradient's temperature); the
   search tries its depth; the inputs card and the notes name it.
10. **GEMINI export** (`gemini_export`, `GET /api/gemini.json`): the design's brine loop as
    a project file GEMINI's own `load_project` reads and runs, with what GEMINI cannot simulate
    and the daily flows in a block it ignores.
11. **Operations** (Energy tab, `operations.ts`): the year as an operator's plan, a week at a
    time (the peak week first), each doublet's flow and temperatures, each unit's output,
    stops and shortfalls; the week or the year as CSV. From the design's own year: GEMINI's
    operating data is not in the repository.
12. **Permit and subsidy pack** (`permit_pack`, `GET /api/permits.pdf`): the production plan's
    figures with SodM's limits, the SDE++ category and subsidy (the investor view), the
    environment figures, and what the applications also need.
13. **Canvas**: electricity is drawn as a tap at each unit (a utility, as on a P&ID), not a
    dotted line across the plant; pipes that still cross hop over the one below with a white
    halo. The motion across the app is BoardUI's blur-in.

## Not done

- HT-ATES (a seasonal store needs a reservoir model of its own), a seasonal grid factor.
- Operations against measured data (GEMINI's database is not available here).
- The store is not sized by the search (the boiler is still sized for the peak).
