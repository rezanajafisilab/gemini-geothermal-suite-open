# ADR-0017: What a reply needs, options the search tries, and reliability by risk

- Status: **accepted** (3 Nov 2026). Amends [ADR-0016](ADR-0016-real-projects-plant-options-operations.md)
  (the options become the search's own) and [ADR-0011](ADR-0011-picks-failures-plans.md)
  (the best-overall pick). Plan: `hackathon/docs/plans/2026-11-03-plan.md`.
- Evidence: `unit_test/gemini_agent/test_which_design.py`, `test_answer.py` (cards on request),
  `test_model_review.py`; `unit_test/dioscuri_plant/test_plant_options.py` (risk sizing, HT-ATES,
  grid by month); `hackathon/evals/scenarios/chat.yaml` groups options and needs.

## Context

- After a design the chat showed three cards; the user wants the result card alone.
- Questions defaulted to the chosen design ("Questions are about A1"); the user wants to name
  one (@) or be asked.
- "I want to do another design", in other words, got a reply instead of the inputs card.
- Read inside the long parameters reading, three new fields came back wrong for most messages
  and the JSON was cut short.
- The recommended design flared 4.1 GWh of the brine's gas a year.
- The user asked whether N-1 is a standard and whether it could be done better.

## Decision

1. **What a reply needs is its own short call** (`parameters.read_needs`, prompt `needs_v1`):
   one choice of five (a new design run, one existing design, designs side by side, how a
   design was found, none in particular). 14 of 14 test messages, 0.2 s each.
2. **Cards on request**: "How I got here" and "Designs compared" are sent when the message asks
   for them; the search's card is kept with its search to be shown later.
3. **No default design**: a question about one design, with none named and two or more in the
   chat, gets a question back (the picks, Other for a handle or a name).
4. **Another design** opens the inputs card ready to edit (with what the message changes, the
   run).
5. **Options the search tries**: free cooling where there are towers, own solar at once and
   twice the plant's mean load, a 2,000 MWh tank and a 28,000 MWh HT-ATES where the boiler runs,
   the gas sold where it flares; on the 4 cheapest designs and the 4 cheapest reliable plans,
   each a variant with its own brief and code suffix (`-FC`, `-PV1.7`, `-TS2000`, `-ATES`).
6. **The best-overall pick avoids routine flaring**: a plan that flares more than 1 GWh a year
   gives way to one that flares less within 3 % of its measure; the notes say so.
7. **Reliability by risk** beside N-1 (`montecarlo.risk_sizing`): the smallest backup boiler
   that keeps the days short of heat to one in ten years over 1,000 drawn years. N-1 stays the
   reliable plan; the Sensitivity tab shows what it buys. `hackathon/docs/reliability.md` says
   what N-1 is and is not (no Dutch rule for heat).
8. **The grid's CO₂ by month** (a switch): Ember's 2024 monthly shape for the Netherlands on
   the yearly figure.
9. **HT-ATES** as a store kind (Middenmeer pilot's 10 MW, 60 % back; cost estimated from the
   ThermoGIS well cost, labelled so).
10. **A cooling check against a real plant**: Oregon Tech's geothermal absorption chiller
    (541 kW from 38 L/s at 89 °C, 1996): our 15 K generator drop takes a third of the water a
    single-effect machine runs on.
11. **A new model is offered only for what the plant lacks**: the offer waits for the reading;
    a message it maps onto the plant's own parameters (an aquifer store is HT-ATES) runs them.
    **The plant's options are read again on their own** (`parameters.read_options`, prompt
    `options_v1`, 13 keys) when the long reading leaves something: an item filed as not
    modelled, a change dropped, or nothing read from a what-if or a question once a design
    exists. The same code checks apply. 0.3 s on the GPU, about 7 s on the CPU model, 1,200
    prompt tokens. An option asked for that the design already has is said first.
12. **UI**: headers redesigned, exports previewed, the design space interactive with every drawn
    design listed and openable, a command palette, a jump-to-latest button.

## Not done

- Operations on measured data: GEMINI's operating data is not in the repository.
- The store's and solar's sizes are tried at two points each, not optimised.
