# ADR-0015: Where numbers come from, a stricter chat eval, deeper wells, the design-space sweep and unplanned outages

- Status: **accepted** (2 Nov 2026). Amends [ADR-0014](ADR-0014-premises-stops-grounding.md)
  (answers), [ADR-0011](ADR-0011-picks-failures-plans.md) (the search) and the failure costs of
  [ADR-0013](ADR-0013-gas-free-investor-failures.md).
- Evidence: `hackathon/evals/scenarios/chat.yaml` and its runs; `unit_test/gemini_agent/`
  `test_provenance.py`, `test_suggest.py`; `unit_test/dioscuri_plant/` `test_sweep.py`,
  `test_co2_reinjection.py`.

## Context

- "Where does the 30 MW come from?" got "I couldn't confirm an answer" or the circular
  "three 10 MW units"; once the reply worked out "86.1 °C − 40 K = 52.1 °C".
- The chat was tested on about 60 questions, one wording each. The first run of the new suite
  (156 cases) passed 77 %: a film was recommended, "the capital of Peru" got the reservoir's
  temperature, "4,5 ct/kWh" was read as 54 €/MWh, "the first design" was looked up on the
  current one, "two doublets" was accepted for a one-doublet design.
- Suggested follow-ups were the model's own and sometimes led to refusals.
- The organisers confirmed (2 Nov) that a depth change is acceptable and that 330 days is the
  geothermal source's availability (the system runs all year).
- The search tried 60–100 layouts, none failed; the user asked for a much wider, sampled
  search with failures kept.
- Failures were costed on average only; the spread over years and a cold-week worst case were
  missing.
- The user asked whether the brine's CO₂ could be dissolved back into the injected brine.

## Decision

1. **Where a number comes from** (`provenance.py`). The reasoning model marks the numbers whose
   origin a message asks for (`origin_of`, any wording or language; a phrase pattern is only a
   backstop). Code finds which figure each is and writes its working: the boilers by the N-1
   case that sets them, a cost by its parts, the exchanger by its busiest day, the reinjection
   by its coldest day and what limited it. The reply must keep a value of the working, not only
   the figure.
2. **Replies that add up.** A calculation written in a reply is checked (`answer.wrong_sums`):
   wrong, the model is asked again; still wrong, the line goes. LaTeX in the model's JSON is
   kept whole (`llm.latex_escapes`). Cost parts are merged ("Surface plant" once).
3. **Stricter chat eval** (`--suite chat`): 51 scenarios × 3 wordings in 10 groups, values
   filled from the design itself, designs picked as with @, and automatic fails on every case:
   a run claimed that did not happen, a calculation that does not add up, a refusal when the
   design has the answer, a cost called by another's name, a design named that was not asked
   about. Fixes from its first run: an `on_topic` reading by the reasoning model (off-topic
   messages declined even with a design in the chat); prices with energy units converted by
   code; runs named by what they changed and given to both models ("run A", "the first
   design"); counts in words in premises; "runs all year" checked against the operating days;
   the wells' depth as a value; a stop window that is already where it is is no change; spans
   over two months read as one range; the prompt's list of values regenerated (lcoe and
   doublets were missing) and pinned by a test.
4. **Tested suggestions** (`suggest.py`): follow-ups are eval wordings, picked by the reply's
   topic and filled with the design's numbers; `test_suggest` fails if one is not in the evals.
5. **Evidence** (`evidence.py`): the GPU's energy is measured during each turn (nvidia-smi,
   the whole GPU, an upper bound) and shown beside tokens and time; CPU energy is not claimed.
   The eval records it and the models' GPU memory, and says whether they fit a 16 GB GPU.
6. **Deeper wells by default** for the challenge: 2,500, 3,000 and 3,500 m, the deeper aquifers
   with the known one's properties, labelled as assumed, citing the organisers.
7. **The design-space sweep** (`dioscuri_plant/explore.py`): 5,000 designs drawn by Latin
   hypercube (doublets, depth, flow cap, every unit's size, the gas mode), each run for a year
   as drawn, all kept with the cap they break; the best feasible ones are refined (each unit
   shrunk while every cap holds) and join the candidates (and get reliable plans). The Compare
   tab maps them (cost against CO₂, failures as rings, the front, the search's designs on top).
8. **Speed.** Doublet curves are cached; layouts, the sweep and the one-unit-out checks run in
   worker processes (`parallel.pmap`, fork, with a timeout and a serial fallback): the search
   with the sweep takes about 6 s on 8 cores (25 s on one).
9. **Unplanned outages** (`dioscuri_plant/montecarlo.py`): 1,000 drawn years, each unit failing
   at its sourced rate for its repair time, every failure year run; the worst case is the
   doublet out 35 days in the coldest weeks. With and without a spare ESP, on the Sensitivity
   tab.
10. **CO₂ reinjection** (a switch, off by default): the brine's own CO₂ (20 % of its gas, about
    550 t a year for the chosen design, 6 % of its CO₂) is dissolved back into the injected
    brine at 25 €/t (CarbFix2, Gunnarsson et al. 2018); the methane's CO₂ is let out either way.
    About 0.007 mol/kg needs well under 1 bar of CO₂ to stay dissolved, far below injection
    pressures. Not modelled: corrosion and scaling of the wells, and the permit (CO₂ storage
    under the Mining Act).

11. **Each doublet's flow** (C4): a doublet has its own cap and now its own minimum
    (`Doublet.min_flow_m3h`; equal to the cap, one fixed rate). The daily dispatch honours each
    doublet's floor; the Design tab's editor sets both ("Runs at least", with the rate in words);
    the reading takes "at least 150 m3/h" and "fixed at 200 m3/h".
12. **Flaring** (C5): a switch flares all the brine's gas (the boiler then buys all its gas);
    the search never picks it. Every design that flares any gas, the default ones included
    (they flare the summer's surplus), carries a note: routine flaring needs consent under the
    Mijnbouwbesluit (art. 38 and 84, per SodM's 2026 review) and the EU Methane Regulation
    2024/1787 allows it only in the situations it lists.
13. **Ali's cooling model connected** (C6, `cooling_check.py`): his kernel runs day by day on the
    pick's electric chillers and towers and is set beside ours on the card, as a tool step and
    in the design's notes: compressor and tower electricity, and the towers' make-up water (new:
    about 41,000 m³ a year for the default design). Without weather files it uses a typical
    De Bilt year (KNMI 1991-2020 normals, wet bulb by Stull 2011). Chilled-water pumps are the
    network's (ratio 0). Absorption and free cooling are not checked yet.
14. **CO₂ inputs** (C7): the grid's CO₂ factor is an input (default CBS 2024, 0.20 t/MWh); the
    flare's unburnt methane is counted as CO₂-equivalent apart from the total (98 % destruction,
    US EPA default; GWP100 29.8, IPCC AR6). Upstream emissions of bought gas are not counted.
15. **Spare units on the canvas** (C8): a bank of equal units shows one block per unit, filled
    for those the day (or the year's busiest day) needs, outlined for those standing by.

## A model bug found on the way

With a network that warms by more than the brine may cool (a 50 °C return heated to 100 °C,
40 K cap), the brine flow was planned "balanced" and then cut by the cap: 6 GWh a year went to
the boiler at 3,500 m. The flow is now planned for the cap (`year.py`).

## Consequences

- The default design changes: one doublet at 3,500 m with a backup boiler and electric
  chillers, N-1 (59.1 €/MWh of heat and cold, 62 % less CO₂ than gas, against 69.8 €/MWh and
  46.8 % at 2,500 m). Tests of the 31 Oct review designs are pinned to 2,500 m.
- A design reply waits about 6 s more on 8 cores for the search; the sweep can be turned off
  (`DIOSCURI_SWEEP=0`) and the workers set (`DIOSCURI_WORKERS`).
- Forking a multi-threaded server can, rarely, hang a worker; the pool then gives up and the
  work runs in the server process.
