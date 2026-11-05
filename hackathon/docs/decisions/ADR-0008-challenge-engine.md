# ADR-0008: The challenge engine: GEMINI's wells, Dioscuri's plant model, one design per request

- Status: **accepted** (30 Oct 2026). Replaces the toy model of
  [ADR-0002](ADR-0002-llm-runtime-and-framework.md) and the A1–A4 plan of
  [ADR-0004](ADR-0004-model-decides-code-checks.md); the answerer, the checks and the claim
  checker of [ADR-0005](ADR-0005-answerer-and-roles.md) to
  [ADR-0007](ADR-0007-claim-checker-and-lean-context.md) stay.
- Evidence: `src/dioscuri_plant/` (the plant model), `src/gemini_agent/engine.py`,
  `src/gemini_agent/tools/gemini.py` (the doublet), patch 11, the eval runs of 30 Oct
  (`hackathon/evals/runs/20261030T124511Z_qwen3-1.7b_auto.jsonl`, 28/28 on the GPU), and
  [`cost_sources.md`](../challenge/cost_sources.md).

## Context

- The organisers' requirements (28 Oct) fix the problem: daily heat and cold demand for 2027
  (111.7 and 23.7 GWh; peaks 30 and 10 MW), one reservoir (2,500 m, 87 °C, 250 bar,
  200 mD × 100 m), the brine (1,030 kg/m³, 0.40 mPa·s, 0.8 Nm³ of gas per m³, 80 % CH₄), and
  hard caps: 1–3 doublets, 50–300 m³/h each while running, brine cooled by at most 40 K,
  330 operating days, 70 % pumps, heating supplied at 100 °C and cooling at 20 °C.
- The agent's numbers came from a toy model calibrated to a demo district. The user decided on
  30 Oct: no more fallbacks to mock or toy numbers; first real versions of the dispatch, the
  chillers and the costs now (Ali's modules replace them as they land); and one design per
  request with what the agent tried, the gas-only plant as a baseline rather than a design.
- The organisers want an agent that generates configurations, runs checks, detects violations
  and iteratively improves, and explains every major decision.

## Decision

1. **The doublet comes from GEMINI.** At a design's brine flow, GEMINI's well-segment model
   (DPDT, with the challenge's brine through the new patch 11) walks the producer from the
   wellhead down, GEMINI's reservoir inflow (IPR) says what the reservoir supplies, and the ESP
   makes up the difference; GEMINI's injector solve gives the injection pressure. Both pumps at
   the challenge's 70 %. This agrees with a hand calculation within 0.3 % (unit test). GEMINI
   as released gives a 27 % higher ESP head and almost no injection pump at 300 m³/h (water,
   10 mm roughness, the friction-sign bug): the bug-impact rows of the Evidence tab.
2. **The plant over the year is `dioscuri_plant`** (pure numpy, about 10 ms a year), on the
   interface in Ali's guide (`Rules`, `Plant`, `Demand`, `simulate_year`, `economics`). Each
   day: the brine preheats the network in a balanced counterflow exchanger (5 K approach);
   the produced gas is burnt in the boiler first (it would be flared otherwise); a heat pump
   on the brine (GEMINI's Carnot formula with patch 10, η 0.5) tops up to 100 °C within the
   40 K cap; the boiler covers the rest. Cooling: absorption on brine, then electric chillers.
   Each doublet stops for 35 days, staggered, in the weeks that need least brine. Every broken
   cap is a sentence with its day and size; every day's energy balance is checked.
3. **Costs from sources** (`Prices`, `SOURCES`): ThermoGIS v3 well cost and surface
   plant (3.5 M€ + 882 €/kW, which TNO calibrates to PBL; until 1 Nov the v2 surface plant,
   20-35 % below PBL, see ADR-0011), PBL's fixed O&M (121 €/kW/yr), PBL SDE++ 2026 (5.2 % real, 30 years), DEA heat pumps and
   boilers, US DOE/EIA chillers, Eurostat 2025 NL electricity and gas, EU ETS 2025, CBS grid
   CO₂, IPCC gas CO₂. Shared costs are split between heat and cold by the brine heat each uses.
4. **One design per request, with what was tried** (`dioscuri_plant.search`, `engine`). The
   search sizes each candidate by rules of thumb (depth 2,500/3,000/3,500 m × 1–3 doublets ×
   heat-pump or boiler top-up × absorption or electric cooling, about 30 distinct plants),
   runs the year, and while a day is short of heat or cold grows the unit that was short and
   runs again ("fix what broke"). Valid designs are priced and ranked by the cost of heat and
   cold together (or by CO₂ when asked); every loser keeps the reason in numbers. The reply
   names the pick, the runner-up, the lowest-CO₂ option and the assumptions; a `candidates`
   event carries the whole search (the chat's "How I got here" card, the Compare tab).
5. **The steps are the agents.** Plan the candidates (rules), solve the doublets on GEMINI,
   size and run the candidates, check the caps, fix what broke, price and pick, write the
   reply, check its claims. The chat shows them as an agents panel in the steps box.
6. **Assumptions are said, not hidden.** The network returns (60 °C, 25 °C) are not given:
   the reply says so and the Sensitivity tab varies them (the largest effect on the cost of
   heat). Depths other than 2,500 m assume the same aquifer, as the requirements allow. The
   330 days are read as "each doublet runs at most 330 days" (asked of the organisers).

## Consequences

- The toy model, its demo district and the A1–A4 plan and fix code are gone; tests and evals
  were rewritten for the challenge (265 Python tests; 28/28 scenarios on the GPU).
- With the sourced prices the search first picked two doublets at 3,000 m with the boiler on the
  produced gas: about 52 €/MWh of heat against 92 for gas boilers, and 79 % less CO₂. With the
  flow-dependent wellhead temperature of ADR-0009 (the brine loses more heat up the well when
  slow, so doublets that share a low flow deliver a little less) one doublet at 3,500 m is
  0.1 €/MWh of heat and cold ahead of them (52.4 €/MWh of heat, 62 % less CO₂); both assume
  the aquifer continues below the known 2,500 m, and the reply says so. PBL's benchmark for
  deep geothermal heat is 62.7 €/MWh. Electric chillers win over absorption at
  20 °C chilled water (COP about 8.6).
- Not modelled yet: a heat pump between the cooling and heating networks, a CHP on the
  produced gas, interference between doublets, weather-dependent chiller performance (the
  location is asked of the organisers). These are Ali's next modules or later work.
