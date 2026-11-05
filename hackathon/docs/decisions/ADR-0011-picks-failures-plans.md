# ADR-0011: Four picks with a reliable plan, failures by code, steps read by the model, PBL costs

- Status: **accepted** (1 Nov 2026). Amends [ADR-0008](ADR-0008-challenge-engine.md) (the costs,
  what "best" means) and [ADR-0010](ADR-0010-doublets-inputs-whatifs.md) (what-ifs).
- Evidence: the review panel of 31 Oct (`hackathon/reviews/2026-10-31-panel/`); the user's
  review of 1 Nov; `unit_test/dioscuri_plant/test_firm.py`; scenarios S51–S60.

## Context

The panel found: no cover for a lost unit (one doublet's ESP out left 7.2 MW short on 28 Jan); a
cost basis 20–35 % below PBL although the code said it matched PBL; outage and comparison answers
written by the model with mixed-up numbers; what-if cards that hid whether the pick changed;
no subsurface checks (breakthrough, gas at the ESP, injection pressure); one design name for
many designs; and no way to ask for several steps at once. The user asked for designs that are
best on reliability, on cost and on emissions, with one recommended as best overall; for
failures on given dates with what a spare would change; and for the model, not phrase lists,
to work out what is asked.

## Decision

1. **Costs.** ThermoGIS v3 surface plant (3.5 M€ + 882 €/kW, which TNO calibrates to PBL)
   with the v3 wells, and PBL's fixed O&M (121 €/kW/yr, with insurance, staff and the ESP
   provisions). The cheapest design becomes one doublet (1D-HP-AB, 68.1 €/MWh); the best
   two-doublet design (2D-HP-AB) costs 71.4 €/MWh.
2. **Reliable plans** (`dioscuri_plant.firm.reliable`). The six cheapest layouts and the
   lowest-CO2 one get a second sizing: the boiler and the electric chillers as three equal
   units, grown until each one-unit-out case (each doublet, a shared treatment train, the heat
   exchanger, the heat pump, a boiler unit, a chiller unit, the absorption chiller) leaves every
   day met. Code `-N1`. For the pick (1D-HP-EC-N1: boiler 3 × 10.4 MW, chillers 3 × 5 MW) it
   adds 2.0 M€ and 1.6 €/MWh.
3. **Four picks** (`engine.pick`): cheapest; lowest CO2 (the cheapest within 2 % of the least);
   most reliable (the cheapest reliable plan); best overall (the reliable plan that is cheapest
   with CO2 at PBL's long-term 137 €/t). Best overall is the default objective and the
   recommendation; the user can ask for any other. The card shows all four.
4. **Failures on dates** (`Plant.outages`, `firm.failure`, `firm.remedies`,
   `gemini_agent.reliability`). Any unit can be out on given days; a duration without dates
   takes the worst start of the year; no dates means all year. The answer gives what is not
   delivered, the extra gas and CO2, and each remedy run through the same days: more boiler or
   chillers, a standby twin when the boiler or chillers themselves fail, a spare ESP (back after
   3 days; TNO at the EBN workshop, Dec 2025). Numbers come from these runs; the model words them.
5. **Subsurface checks** (`dioscuri_plant.subsurface`): Gringarten-Sauty breakthrough against the
   30-year life; the ESP's setting depth for its intake to stay above the bubble point (IAPWS
   G7-04 Henry constants, salted out at 0.85 mol/kg: about 43 bar), with 5 bar of margin, at most 1,000 m; SodM's 0.135 bar/m at the
   top of the reservoir. A doublet that breaks the ESP or injection limit is capped at the
   highest flow within both, and the search grows the top-up instead.
6. **Steps read by the model.** The reasoning model's one reading per message
   (`parameters_v2`) now also returns the failures with their dates, the designs named (by
   name, code or pick) and up to three steps (design, what-if, failure, compare, answer). Code
   checks the plan (quotes in the message, dates in a month the message names, a what-if or
   failure needs a design) and runs it; one reply covers all steps. No extra model call.
7. **Comparisons by code** (`reliability.compare`): every figure from the ledger, the best of
   each row marked; a comparison reply may name only the compared designs, else the code's
   table is shown.
8. **One name per design**: A1, A2 … (a search, ranked), B1 … (the next), W1 … (what-ifs),
   U1 … (the user's), the code beside it. **One headline cost**: heat and cold together, what
   the search ranks by. **One rounding**: half up, thousands as whole numbers, in Python and
   in the app.

## Consequences

- A failure of the recommended design is covered by design; the cheapest design shows the gap
  and what closing it costs. The challenge does not ask for N-1; it is offered and labelled.
- The reliable plan's boiler is sized for the full peak when a shared treatment train is a
  single point of failure; separate trains are not yet weighed against that.
- The breakthrough estimate ignores neighbouring doublets; the ESP limit of 1,000 m and the
  porosity of 0.20 are assumptions, both in `Rules`/`subsurface.py`.
