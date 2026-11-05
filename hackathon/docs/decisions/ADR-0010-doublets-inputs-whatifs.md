# ADR-0010: Doublets that differ, the known aquifer, inputs confirmed, what-ifs on any input

- Status: **accepted** (31 Oct 2026). Amends [ADR-0008](ADR-0008-challenge-engine.md) (the
  search and its depths) and [ADR-0009](ADR-0009-reading-requests.md) (what a design or a
  what-if may change).
- Evidence: the user's review of 31 Oct; the GPU replays in the session scratchpad (`v12.json`);
  `unit_test/dioscuri_plant/test_doublets.py`, `unit_test/gemini_agent/test_parameters.py`,
  `unit_test/gemini_agent/test_confirm.py`; scenarios S40–S50.

## Context

The user's review of 31 Oct found:

- the pick drilled to 3,500 m, into an aquifer the requirements do not describe. Their sentence
  ("for selecting different geothermal well depth, you can use hydrostatic pressure ... and the
  provided gradient") allows other depths, but the only aquifer they give is 100 m thick around
  2,500 m TVD;
- every doublet was a copy of the first: same depth, same share of the brine, one injector, one
  shared surface plant. The user wants doublets that differ in rate and depth, may have their own
  separator, and may have one producer with two injectors;
- "What happens to the design if we lower the heating return temperature to 50 °C?" was answered
  from the documents: only a reservoir-temperature change could be re-run;
- a design ran without the user seeing what had been read from the project's files;
- the search tried about 30 candidates although a year takes 2 ms;
- the GEMINI tab missed the components the user expected, and GEMINI's example ESP (sized for
  about 150 m³/h) gave a negative head at the design's 300 m³/h, so the tab's ESP power (24 kW)
  was meaningless.

## Decision

1. **The known aquifer by default.** A search drills into the aquifer the project describes;
   deeper (assumed) aquifers only when the user asks for depths or picks "Allow wells into an
   assumed deeper aquifer" when nothing else fits. The confirm card says so.
2. **Doublets that differ** (`dioscuri_plant.Doublet`): each doublet has its aquifer, the part
   of it each well is open to (all 100 m, the upper or the lower half: the produced brine has the
   rock's temperature at the middle of the open part; half the open length halves the
   productivity or injectivity), one or two injectors, a flow cap and a treatment train
   (separator and filters; doublets with the same number share one). Each day the fewest doublets
   that carry the brine run, hottest first, in equal shares or base load. The brine meets in one
   heat plant; the 40 K cap holds per doublet, so the exchanger is throttled when brines differ.
3. **Costs follow the build**: wells priced at each well's depth; the treatment train is a sixth
   of ThermoGIS's per-doublet surface cost (our estimate, flagged), shared trains scale with the
   six-tenths rule.
4. **A two-stage search with sizing.** Stage one: every layout the brief allows (doublet count,
   top-up, cooling, both dispatches), each sized up to 30 ways (heat pump 10-100 % of the top-up,
   absorption 20-100 % of the cooling peak), each sizing improved until its caps hold. Stage two:
   variants of the best three (two injectors, a train per doublet, half-open wells), each with a
   reason in numbers against its parent. 34 layouts, 414 sizings, 622 simulated years in 2 s.
5. **Inputs confirmed before the first design** of a chat (and again when the project's data
   change): a card lists what was read (with the file or section), derived, assumed, or asked.
   A button or a typed reply decides; the reasoning model reads a typed reply (run, change,
   other); a change shows the card again with the changed rows marked.
6. **One parameter catalogue** (`gemini_agent.parameters`) for designs and what-ifs: networks,
   reservoir, caps, demand, prices, how doublets are built, unit sizes. The reasoning model maps
   the user's words onto it and quotes them; code keeps a change only when the quote is in the
   message, the value in range and its number in the quote (or worked from it: "10 K lower",
   "20 % more", "double"). A change without an amount ("cheaper gas") is asked, with choices; what
   no parameter covers is said plainly.
7. **A what-if runs twice**: the same plant under the change (the answer to "what happens to the
   design"), and the search again under it (does another design win?), kept as a new attempt.
8. **GEMINI's view is the whole brine loop**, built from the design: per-doublet producers,
   per-train mixer, separator and filter, a header mixer, the exchanger, a splitter to every
   injector, an adder for the separators' gas, the boiler; GEMINI's example ESP scaled to each
   producer's duty (flow scale, stages for the head, power at the challenge's 70 %).
9. **The 4B model answers on the CPU** (the 1.7B reader's answers to source and physics
   questions were wrong too often).

## Consequences

- At the known aquifer the pick is 2D-HP-AB at 62.1 €/MWh of heat and cold (was 1D-BO-EC@3500
  at 49.6 with the assumed 3,500 m aquifer, and 68.8 at 2,500 m with the old, coarser sizing).
- Upper and lower half-open injectors give the same pressures: their difference is gravity
  (cold brine sinks), which needs a reservoir simulation. Said in the search notes and the
  self card; separate trains' value (a spare when one is serviced) is not modelled either.
- One more reasoning-model call per design request and what-if (about 1-3 s on the GPU).
- The eval runner presses "Run" on the inputs card unless a scenario says `confirm: false`.
