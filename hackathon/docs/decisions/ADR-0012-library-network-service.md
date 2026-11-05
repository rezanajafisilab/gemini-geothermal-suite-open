# ADR-0012: A design library to compare in, network losses, yearly service, GEMINI as a check

- Status: **accepted** (31 Oct 2026). Amends [ADR-0011](ADR-0011-picks-failures-plans.md)
  (picks, steps, comparisons).
- Evidence: the second review round of 31 Oct (`hackathon/reviews/2026-10-31-panel/`); the
  user's and Ali's review of 31 Oct; `unit_test/dioscuri_plant/test_network_service.py`,
  `unit_test/gemini_agent/test_planner.py`, `test_workbench.py`, `test_report_pdf.py`;
  `hackathon/evals/planner/` (42 held-out requests).

## Context

Only the recommended design could be seen in the tabs: the other designs a search ranked, and
the what-ifs, had no economics a user could open. The Compare tab showed one chart (cost against
CO2) and one row per search, which does not scale to a hundred searches. Ali asked for every
design to be filterable and comparable, for costs as percentages against gas, for planned
maintenance as well as failures, for the losses of the pipes to the district, and for a report
an operator can print. The panel asked for replies tied to the cards, a visible plan for
several steps, money for every design by code, GEMINI used as a check and a short decision
summary.

## Decision

1. **Design library** (`workbench.library_view`, the Compare tab). Every design of the
   conversation is one row: each search's candidates, every what-if and every user design, with
   its scenario, cost against gas in percent, money (NPV, payback, IRR) and its one-unit-out
   cases. The tab filters (scenario, picks, doublets, N-1 met, met every cap, text), sorts every
   column, pages 25 rows, and compares up to four side by side. A row's scenario is the search
   it came from; a what-if re-run belongs to the search run under the same change; a user design
   belongs to its parent's scenario when it ran under the same conditions. Designs of different
   scenarios are shown together only with a warning and are never ranked against each other.
2. **One set of prices.** After a price change in Economics every row is run again under the
   new prices (about 3 ms a design, without the one-unit-out years, which prices do not change)
   and says so; the picks stay the ones the search made.
3. **Links into Compare.** `#compare/<ids joined by "|">` ticks those designs and opens them side
   by side; the chat's comparison cards link there.
4. **Chart with reliability.** Cost against CO2 for one scenario; bubble area is capital; a
   solid fill means every one-unit-out case is met, a ring means some are short (thicker with
   more); a dashed red edge means a broken cap; a dashed line marks the gas plant's cost.
5. **District network** (`dioscuri_plant.network`, off by default, one distance on the inputs
   card). A pair of series-2 pre-insulated pipes sized for the peak at 2 m/s; heat loss
   U = 0.20 + 0.0008·DN W/m/K to ground at 10 °C; pumping at 100 Pa/m. The plant makes the loss
   on top of the demand and supplies hotter so the buildings still get 100 °C (5 km: 2.6 % lost,
   up to 102.9 °C in summer, cost of heat and cold +3.4 €/MWh). Costs are per MWh delivered.
6. **Yearly service** (`dioscuri_plant.service`, off by default, a switch on the inputs card).
   Each unit is out once a year in its quietest weeks: heat pump 14 days, a boiler or chiller unit
   7 days each, the heat exchanger 3 days, the absorption chiller 7 days; heating units in summer,
   cooling units in winter, never two heating units at once. The year runs with them out, so a
   design that cannot cover its own service shows it as unmet days.
7. **GEMINI as a check** (`engine.gemini_check`). The picked design's brine loop is run on GEMINI
   at full flow and set against the plant model (injection pressure, ESP intake against the
   bubble point, wellhead temperature, pump powers, exchanger duty, brine out); agreement within
   5 % or 1 K is shown on the card.
8. **Plan, steps and summary.** The planner's reading may hold up to four steps, now also
   `summary` (a decision table: cost per home, against gas, CO2, gas share, N-1) and
   `uncertainty`. The plan is shown as a card that ticks off each step; each step's card comes
   with a code-written verdict ("In short") above the model's words.
9. **Operator's report** (`report_pdf.py`, `GET /api/report.pdf`): a design as an A4 PDF with
   the year, month by month, firm capacity, failures and the yearly service, the limits to
   watch and the assumptions.

## Consequences

- A user can open any design the agent ranked, not only the recommendation; nothing is ranked
  across scenarios.
- The network model is one distance and one pipe pair: no branches, no heat-loss measurements.
  Its numbers are rules of thumb and are labelled as such.
- The service lengths are assumptions (manufacturers' typical yearly service), in `service.py`.
- The UI fixtures (`make_ui_fixtures.py`) still come from the older engine; the frontend tests
  are pinned to them and need updating when they are made again.
- Planner reading: 39 of 42 held-out requests read right on qwen3.5:9b; the misses are two
  what-ifs asked "separately", a design followed by a what-if read as one design, and "the
  coldest day" read as a week.
