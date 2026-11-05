# ADR-0014: Checking what the user takes as given, stop dates from chat, and replies that stay with the data

- Status: **accepted** (1 Nov 2026). Amends [ADR-0007](ADR-0007-claim-checker-and-lean-context.md)
  (claim check) and [ADR-0012](ADR-0012-library-network-service.md) (service, network).
- Evidence: the challenge round of 1 Nov (`hackathon/reviews/2026-11-01-challenge/`); the
  regression questions re-run on the GPU models after each fix;
  `unit_test/gemini_agent/test_premises.py`.

## Context

The challengers' questions showed answers that read well but were not true to the data:

- "The cost of heat is 69.8 and the boiler gives about a quarter, correct?" was agreed with.
  69.8 €/MWh is heat and cold together (heat alone is 75.7); the boiler gives 42.9 %.
- "Why does the design take half its heat from gas?" was blamed on the N-1 sizing. The split
  is set by what the brine can give and by the heat pump size the search found cheapest.
- "What share of the yearly cost is gas?" had no fact to answer from, and the reply rambled
  ("The text states …", "Let's break down …").
- "Could we move the stop to August?" could not be run from chat.
- A what-if with the yearly service ran, and the reply said the service "is not modelled".
- "Add a 5 MW solar PV park" read as a 5 MW heat pump plus "lowest CO2", and ran a new search.
- "At least 50 % less CO2: could they live with the cheapest?" ran on the recommended design.
- Long facts (all well checks, all CO2 sources) were pasted under every short answer.

## Decision

1. **Premises.** The planner lists the message's own words that state something as given
   (`premises`; code keeps only words the message has). Code pairs each with the facts it is
   about and corrects a number that a fact contradicts, first: "**Not quite.** The cost of
   heat is 75.7 €/MWh; 69.8 €/MWh is the cost of heat and cold together."
   (`lookup.premise_checks`; the user's number is matched to a fact with the same unit). What
   code cannot judge ("about a quarter") goes to the answering model paired with its fact,
   and reasoning is switched on for that message.
2. **Stop dates from chat.** A new change, `doublet_stops`: the planner gives the words, code
   reads the days (`parameters.stop_dates`). "In August" starts the stop on 1 August and keeps
   its length (35 days for 330 operating days); "doublet 2 off 1 to 21 July" sets that doublet
   alone. It runs as a what-if, and the result says both the design's own dates and the
   what-if's.
3. **New facts.** The yearly cost by part (capital, gas, electricity, O&M, CO2, with shares;
   gas sold as a credit), the cost of heat and cold together, and the number of doublets. Long
   facts open with a heading ("Heat over the year by source: …") and count as kept when the
   reply gives any one of their numbers, so they are no longer pasted under short answers.
4. **Why-questions.** The heat split's reason comes from the design: the exchanger's limit,
   the peak, the heat pump sizes the search tried and what each cost. A why-question looks up
   the heat split and its reason. "Why that one and not the cheapest?" sets the two side by
   side (cost, CO2, capital, one unit out).
5. **What-ifs stay what-ifs.** A what-if's design and operation blocks say they are a
   what-if, and the design's own operation goes in beside them. A what-if keeps its cost of
   heat and cold in the reply.
6. **Refusals of a result that exists.** When a tool ran, a sentence saying it cannot be
   computed, switched on or modelled is removed; a reply that is only that shows the checked
   result. The context lists options that are modelled but switched off (network losses,
   yearly service) apart from what is not modelled at all.
7. **Unsupported requests.** When nothing the model has would change ("a solar PV park"), the
   reply says so and gives the design's electricity use and its CO2 for scale, whatever steps
   the planner listed. A change read from the unsupported item's own words is dropped.
8. **Questions about a named design.** A lookup about "the cheapest" uses that design's facts.
   A CO2 floor runs as a search against the design named and says first whether it meets the
   floor.
9. **Run claims and repeat runs.** "I have run a new search" is removed when no tool ran; a
   design request that changes nothing (no question mark, the same inputs as the last search)
   gets the same-search reply even when the router reads it as a question.
10. **No guessed amounts.** A network length the words do not give is asked for, and the reply
   says it was not applied.
11. **Reply hygiene.** Sentences about "the text", "the provided data" or "the context", the
    model's working ("Let's break down …", "Actually, …") and the user in the third person are
    removed.

## Results (regression questions, GPU models)

| Question | Before | After |
|---|---|---|
| Cost 69.8 and a quarter from the boiler, correct? | agreed | corrected (75.7 heat; 42.9 %) |
| Why half the heat from gas? | blamed N-1 | exchanger limit, peak, heat pump sweep |
| Share of the cost that is gas and capital | rambling, no figure | gas 28.8 %, capital 23.8 % |
| When does cold water reach the producer? | "not modelled" | 85.4 years (Gringarten-Sauty) |
| Move the stop to August | not possible | what-if: 69.9 vs 69.8 €/MWh, both dates said (when the planner reads the change; else the reply points to the inputs card) |
| Switch on network losses and service | refused | service result; network length asked |
| 5 MW solar PV park | new search | not modelled; electricity CO2 for scale |
| Why A1 and not the cheapest? | denied a recommendation | side by side: cost, CO2, one unit out |
| 50 % CO2 floor, "the cheapest" | ran on A1 | A29 cuts 41.2 %, short; the cheapest at 50 % is 2D-HP-AB, 71.4 €/MWh |

GPU eval (60 scenarios, qwen3:1.7b reader, qwen3.5:9b reasoning and answers): 54/60 after the
first fixes, 59/60 at the end. The open one, S35 ("do another design attempt"), passes when run
straight after S01 (it says the same inputs give the same designs) but not in the full run,
where an earlier scenario changes what it starts from; not found yet.

## Not done

- The grid's CO2 factor (0.20 t/MWh) is fixed in the plant model: own solar power can only be
  approximated by a lower electricity price, not by cleaner power.
- The answering model (qwen3.5:9b) still words some replies loosely; the checks remove what
  is wrong, so some replies come out short.
