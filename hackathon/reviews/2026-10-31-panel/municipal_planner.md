# Review: municipal energy planner (future client)

Role: I am the city's energy planner, not an engineer. I have to recommend a heating and cooling
solution for a new district to the council. I care about budget, cost per household, the CO2
target and risk. Server http://127.0.0.1:8791. Threads `city-1` (14 turns) and `city-2` (5 turns),
plus the tabs' data (`designs`, `design … economics/checks`, `attempts`, `sensitivity`, one `edit`).
I also checked figures in Python against the plant model (`engine.reference()`, the cost lines).

## 1. Verdict

Underneath, Dioscuri has the numbers a council needs, and they hold together. The heat cost lines
add up exactly to 64.25 €/MWh, and the gas reference reproduces at 92.2 €/MWh of heat. A 10-year
payback is computed for the cheapest design. But the chat would not give me those numbers in
words I could use. In 19 turns it never told me what we pay per year, per home, or how much we
save compared with gas. It told me twice that it needed a gas price that is on its own inputs
card. Once it said the opposite of its own data: "the gas-only cost would be significantly lower
than 64.2 €/MWh". My requests for a council summary, a side-by-side table and "why only 65% CO2"
got a paragraph about wellhead temperatures and ESP pumps, three times out of five. Today I would
trust the tabs, if someone read them to me, but not the chat. I could not take its answers to the
council.

## 2. What works

- **The inputs card is honest.** Every line says where it comes from (read from the files,
  fixed by the requirements, worked out, assumed, asked), with sources. Its "Not modelled" row
  was the most trustworthy moment of the session: it flagged my rule, "cheapest option that still
  cuts CO2 by at least 80%…", as not modelled instead of pretending.
- **The design engine is fast and the numbers are consistent.** It tried 35 layouts and 730
  sizings in seconds. The cost lines sum to the headline cost. The payback, NPV and CO2 split
  (bought gas / gas from the wells / electricity) are all in the data.
- **The 20% growth what-if was the best answer of the session.** It re-ran the year and found
  the coldest-day gap ("On the worst day (28 Jan), the shortfall is **5.95 MW** when demand hits
  **36.00 MW**"), then searched again and found a plant that works.
- **The claim checker removes real nonsense.** Removed examples: "High pressure keeps CO2
  dissolved in the brine, preventing leaks"; an unfounded "not expected to cause earthquakes";
  "Removing the gas boiler adds roughly 10 M€" (it is 16 M€).
- **Language and structure.** The Dutch question got a Dutch answer. The second council summary
  (`city-2`) had the right shape: recommendation, money and CO2, risks, open questions. In the
  code, the Compare tab draws exactly the picture a council wants: cost against CO2 saving, gas
  as the grey baseline, bubble size for investment. The chat never points to it.

## 3. Issues

### H1 (high). It cannot say what we pay or whether it beats gas, and once it said gas was cheaper

- **What I did** (`city-1`, after the first design):
  1. "What does this cost us? I need the investment up front, the cost per year, and what it
     means per home. And is it cheaper than gas, and by how much?"
  2. Then: "…In euros: what does the gas option cost us per year, what does your design cost per
     year, and how much do we save? The district will have about 12,000 homes…"
  3. Then: "Your design gives heat at 64.2 euros per MWh. What would heat cost per MWh if we just
     built gas boilers instead? And how much extra money do we have to put in up front, and
     after how many years do we get it back?"
- **What happened:**
  - "While the exact annual cost depends on your specific gas and electricity prices…"; "To find
    the cost per home, divide the total annual energy bill by the number of households" (it
    never gave the bill); "Is it cheaper than gas? Yes, significantly. The design saves 60.4% on
    CO₂…". It answered a money question with CO2.
  - "If you provide the current gas price per MWh, I can calculate the exact annual saving and
    cost per home immediately." The price, 69.4 €/MWh, is on its own inputs card. Its first
    draft had sums (14.5, 10.8, 3.7, 1,208, 904, 304); the number guard removed them all and left
    the refusal. The suggestion chip still offered "the breakdown of the 10.8 M€ annual cost".
  - "**the gas-only cost would be significantly lower than 64.2 €/MWh**"; "Gas fuel price used:
    8.9 €/MWh"; "The context does not provide a specific capital cost for a gas-only plant to
    calculate an exact payback period."
  - In Dutch: "Dit is goedkoper dan gas…", with no amount, and still no per-home figure.
    Its suggestion then asked "Hoeveel woningen zijn er in de wijk?" although I had said 12,000.
- **Why it matters:**
  - Dioscuri's own gas reference costs 92.2 €/MWh of heat, so gas is 44% *more* expensive than
    64.2, not lower.
  - 8.9 €/MWh is the gas line spread over each MWh of heat, not the gas price.
  - The data has the payback: 38.5 M€ extra investment, 5.39 M€ a year lower running costs,
    10 years, NPV 42.5 M€.
  - If I had repeated the chat, I would have told the council the opposite of the tool's own
    result.
  - Cause in the code: `answer.py` `economics_block()` passes only the design's own cost lines
    and capital. It passes no prices, no gas reference, no yearly total and no `versus_reference`.
    The guard then removes any derived sum, including "÷ 12,000 homes".
- **What to do instead:**
  - Add a "money" block computed in code and give it to every money question: yearly total
    (M€/yr), the gas reference's €/MWh for heat and cold and its yearly cost, extra investment,
    yearly saving, payback, NPV and the prices.
  - When the user gives a number of homes, store it in the brief and compute per-home figures in
    code.
  - Let the claim checker test "cheaper / more expensive than gas" against those numbers.
  - Say plainly that cold costs *more* than with gas (50.1 against 36.2 €/MWh in the cheapest
    design). It never said so.

### H2 (high). My CO2 target is not modelled, and "lowest CO2" ignores cost completely

- **What I did:**
  - "The council wants the cheapest option that still cuts CO2 by at least 80% compared with
    every home having its own gas boiler."
  - In `city-2`: "Climate comes first… the lowest CO2 we can get, within reason."
- **What happened:**
  - It picked the cheapest design, with a 60.4% cut.
  - The claim checker *removed* the one sentence I needed: "While it does not reach 80% savings
    …". What stayed was "The alternative with lower emissions (3D-HP-EC) costs significantly
    more", with no figures.
  - In `attempts`, the best of the 35 cost-sized designs cuts 63%, and even the lowest-CO2
    search in `city-2` tops out at 72%. It never told me that **no design reaches 80%**.
  - In `city-2`, "lowest CO2" chose 3D-HP-EC-2I: 9 wells, 82.7 M€, 72% cut, payback 28 of 30
    years. In the same search:
    - 2D-HP-EC-2I gives 6,949 t a year (24 t more) for 61.7 M€ (21 M€ less);
    - 2D-HP-EC gives 7,129 t (a 70.7% cut) for 50.7 M€ (32 M€ less) and 65.6 €/MWh instead
      of 81.1.
  - Its own fallback text shows the third doublet "runs 4 days" a year.
- **Why it matters:**
  - A council sets a target and then wants the cheapest way to meet it, or to be told it cannot
    be met.
  - "Within reason" means the 50.7 M€ option, not one that spends about 21 M€ to save 24 t a year.
  - Going from the cheapest design to 2D-HP-EC costs about 200 € per extra tonne avoided. Going
    to the chosen lowest-CO2 design costs about 960 €/t; going to the no-gas design, about
    1,970 €/t.
- **What to do instead:**
  - Add a target objective, "cheapest design that cuts CO2 by at least X%", with a code-made
    line "Target met: yes/no (best possible: 63%)" that the checker cannot remove.
  - For "lowest CO2", take the cheapest design within ~2% of the minimum, or show the cost
    against CO2 frontier (cheapest / balanced / greenest).

### H3 (high). Summary, table and "why" questions get the engineering paragraph

- **What I did:**
  - "I don't understand. If there is no gas at all, why do we only save 65% of the CO2? Where
    does the rest come from? And how much more do we have to invest…?"
  - "OK. What do I tell the council? Please give me a one-page summary…"
  - "No, I don't want a new design. Please just write a short summary for the city council, in
    plain language…"
  - "Can you put the options side by side in a simple table for me…"
- **What happened:**
  - Three of these four got the same block: "Wells: 2 doublet(s) in the known aquifer at 2,500
    m, each a producer and an injector open over the whole 100 m of the aquifer; rock temperature
    there 87 °C … brine at the wellhead 86.1 °C (0.9 K lost up the well at full flow …) … the
    well pumps (ESP and injection) draw 4.1 GWh/yr." The trace shows `fallback: true`,
    `understood: ""`.
  - The council request was read as "design again": "I ran this search already … The search is
    deterministic…". It offered "Design again, also trying an assumed deeper aquifer at 3,000
    m".
  - The table never came. A later wording ("Summarise this for the council on one page…")
    worked.
- **Why it matters:** These are a client's most important requests. A paragraph on wellhead
  temperatures is unusable for me, and it looks as if the tool did not listen.
- **What to do instead:**
  - Add a summary or report path filled by code: recommendation; money against gas; CO2 and
    target met; risks; what is not assessed. Let the model only smooth the wording.
  - Make the fallback for a non-design question the one-line result plus the money and CO2
    figures, never `reporter.design_answer` + `design_notes` (`agent.py` `_talk`).
  - Route "what do I tell…", "summary", "table" and "side by side" to an answer, never to a
    repeat search.

### H4 (high). It made an unchecked safety claim and gave no answer on earthquakes

- **What I did:** "Residents will ask me two things at the public meeting: can the drilling cause
  earthquakes, and what happens to our heating if a well fails in the middle of winter?"
- **What happened:**
  - "the design includes a backup boiler and heat pumps that can cover 100% of heating demand
    even if one doublet is offline." No check tests this; the 11 checks have no
    one-doublet-out case.
  - My `edit` of the same plant with one doublet less fails "Heat at 100 °C every day: short by
    up to 1.04 MW".
  - On earthquakes, the only sentence was removed and nothing replaced it, so I got no answer.
  - In the earlier risk answer it gave no range for "how sure". It never mentioned drilling or
    geology risk, a seismic risk assessment and permits, electricity price, the district being
    built in phases, or the gas from the wells being flared.
- **Why it matters:** I would stand in a public meeting and promise "100% even if a well fails".
  The tool's own model says otherwise.
- **What to do instead:**
  - Add a one-doublet-out check (peak day) to the checks.
  - When a question is outside the model, say so: "Dioscuri does not assess induced seismicity;
    a seismic risk assessment is needed for the permit".
  - Keep a fixed "not assessed" list: network cost, seismicity, drilling success, subsidies,
    phasing.
  - Give "how sure" as a range from the sensitivity tool, which takes 0.15 s. For example:
    capital ×0.8 to ×1.4 gives 57 to 71 €/MWh, and electricity at 120 to 260 €/MWh gives 56 to
    68 €/MWh. All of these stay below gas at 82 €/MWh.

### H5 (high). Different designs share one name, and my first recommendation disappeared

- **What I did:** I asked for the no-gas version after the first design.
- **What happened:**
  - The no-gas plant got the same code, **2D-HP-AB**.
  - `designs city-1` now lists only the no-gas plant under that name (78.5 €/MWh). The first
    2D-HP-AB, with the backup boiler (43.2 M€, 61.8 €/MWh), is gone from the list.
  - The Dutch answer then quoted 84.8 €/MWh without saying the design had changed. Earlier it
    had said 64.2.
  - In `city-2`, "2D-HP-AB" is a third plant: 51.4 M€, 7,529 t.
- **Why it matters:** "Compare with your first design" is impossible when the first design is
  overwritten. A councillor who hears 64 and then 85 for "the same" design stops trusting the
  numbers.
- **What to do instead:**
  - Give each design a unique name, e.g. `S1·2D-HP-AB` and `S3·2D-HP-AB (no boiler)`, and keep
    every design.
  - When an answer switches design, say so: "the no-gas version".

### M1 (medium). The inputs card is honest but not written for a client

- **What I saw:**
  - 13 rows of engineering ("TVD", "mD", "Nm³/m³", "J/(kg·K)", "brine cooled by at most 40 K").
    No line says which inputs actually move the answer.
  - It says "Design for: lowest cost … from: **your message**" when I had said nothing about
    cost.
  - In `city-2` it said this when I had asked for "the lowest CO2". The run then used lowest
    CO2, through the `CO2_FIRST` regex in `_design`, so the card misinformed me.
  - My "12,000 homes" appeared nowhere, not even as "Not modelled".
  - When I asked what a doublet is instead of clicking, the card closed silently. My objection
    "I never said lowest cost" was dropped: the brief kept `objective: cost`.
  - Its definitions answer was useful: doublet, TVD, mD. But it read my city CO2 target as CO2
    in the brine, and suggested "Can we adjust the well depth to optimize CO2 capture?"
- **What to do instead:**
  - Quote my own words in the "Your request" row and show the objective that will actually run.
  - Add client rows: homes or connections, CO2 target, budget, lifetime.
  - Mark the 3 inputs the tornado says matter most, and add a hover glossary.
  - Keep the card open after a side question.

### M2 (medium). CO2 is never explained in plain words

- **What I saw:**
  - Of the remaining CO2, 46-55% is "produced gas": methane and CO2 that come up with the hot
    water. It is 4,413 t a year in the cheapest and no-gas designs and 3,841 t in the lowest-CO2
    design.
  - In the no-gas design there is no boiler, so this gas is **flared**. The code burns it in the
    boiler first and flares the rest.
  - The chat's draft blamed grid electricity ("the remaining ~35% … come from grid
    electricity"), which was wrong and was removed. The fallback text followed.
- **Why it matters:**
  - "No gas at all" in practice means flaring the gas the wells bring up. The council must know
    this before it votes.
  - The electricity part shrinks as the grid gets greener. That favours the electric options
    over 30 years, and it was never said.
- **What to do instead:** Add a code-made CO2 line, for example: "gas that comes up with the
  water 4,400 t (flared/burned), electricity 4,100 t (falls as the grid greens), bought gas
  0 t".

### M3 (medium). Wording errors that change the meaning, and leaked internals

- "This option saves **71.6%** more CO₂ than a gas boiler…" means the opposite of 71.6% less.
- "The total annual cost is **90.6 €/MWh**": that is a price per MWh, not a yearly total.
- "The cost drops to **59.7 €/MWh** for both heat and cold":
  - 59.7 is the blend (heat 61.6, cold 49.0);
  - "drops" hides that the total bill rises;
  - the extra 4.0 M€ of investment for the plant that works (47.3 against 43.2 M€, 9-year
    payback) was never mentioned.
- "Yes, the plan still works but … this scenario breaks a key cap" is a yes and a no at once.
- "…ten opzichte van een gascentrale": a gascentrale is a gas power station; gas boilers are
  gasketels.
- The UI's **Understood** line shows the guard's instructions to the model: "I will remove the
  calculated totals and per-home costs that were not in the context."; "…without inventing new
  totals."
- The small reader model marked four of my questions "relevant: false": why only 65%, the Dutch
  question, earthquakes, and the second summary request. After a fallback the suggestions
  became generic ("Design heating and cooling for this district | Compare well depths").

### L1 (low). Jargon left in client answers

- The council summary listed a risk as "Partial pressure of CO₂ in brine must be checked
  against material limits using $p_{CO2} = \frac{C_{aq} + C_g}{K_H(T)}$". It also used "COP
  4.6", "ESP" and "doublet(s)" without explanation.
- The summary also said "long-term sustainability beyond the 330-day cap requires further
  simulation". The 330 days is a yearly operating cap, not a time horizon.

### L2 (low). What "gas" means, and what is left out, is not said

- I asked to compare with "every home having its own gas boiler". The reference is a central
  gas boiler plant with electric chillers. Nothing in the chat says so.
- In the Netherlands new homes have not been connected to gas since 2018. The realistic
  alternative for my district is individual heat pumps or an all-electric district.
- The street network, the home connections (substations) and subsidies (SDE++) are not costed
  or flagged. For a new district the network is usually the largest single cost, so any
  "per home" figure is only the heat source.

## 4. Implement differently or remove

- **Give a client a decision table by default, built by code.** Here is what I needed, computed
  from Dioscuri's own data:

  | Option | Up front | Per year, all in | Per home* | CO2 per year | Cut | Payback |
  |---|---|---|---|---|---|---|
  | Gas boilers + electric chillers | 4.7 M€ | 11.2 M€ | ~930 € | 24,365 t | none | n/a |
  | A: cheapest, 2D-HP-AB with backup boiler | 43.2 M€ | 8.4 M€ | ~700 € | 9,655 t | 60% | 10 yr |
  | B: no gas boiler | 59.2 M€ | 10.6 M€ | ~890 € | 8,506 t | 65% | 22 yr |
  | C: lowest CO2, 3D-HP-EC-2I | 82.7 M€ | 11.0 M€ | ~915 € | 6,925 t | 72% | 28 yr |
  | Not offered: 2D-HP-EC (CO2 sizing) | 50.7 M€ | 8.9 M€ | ~740 € | 7,129 t | 71% | n/a |

  \*All heat and cold costs spread over 12,000 homes, ignoring the offices' share, and excluding
  the street network and connections, which are not modelled.

  With this table I could have written my council memo in ten minutes. The chat gave me none of
  its rows.
- **Remove the engineering paragraph as the fallback** for anything but an engineering question.
  Use a plain fallback (result line plus money and CO2) and a template report for "summary / what
  do I tell / one page".
- **Let code state verdicts.** Yes/no facts come from arithmetic on the data: "Target met: no",
  "Cheaper than gas: yes, by 20 €/MWh", "Works with one well out: no, 1 MW short on the coldest
  day". Code should write these lines, so the claim checker cannot delete them as it did with
  "it does not reach 80%" and "Yes, I can design the district without any gas backup".
- **Store user facts in the brief** (number of homes, CO2 target, budget) so the next turns use
  them instead of asking again.
- **Replace the `CO2_FIRST` regex** with the parameters model, so the card and the run agree.
  This also follows the team's own "no hard-coded phrasings" rule.
- **Point the chat to the Compare tab** whenever the client asks to compare or for a trade-off.
  Its bubble chart already shows cost against CO2 against investment.

## 5. Top 3 priorities before the deadline

1. **Money block and code-made comparisons.**
   - Give the answerer the yearly cost, the gas reference (€/MWh and M€/yr), the extra
     investment, the payback and the prices.
   - Compute per-home figures in code once homes are known.
   - Have the checker block any "cheaper / dearer than gas" sentence that contradicts the
     numbers. Today the chat said gas is cheaper when the tool's own reference says it is 44%
     dearer for heat.
2. **A plain-language summary path and a plain fallback.** "What do I tell the council?", "one
   page", "table" and "why only 65%" must give the decision table and a short memo: target met?,
   money against gas, CO2 split in plain words, risks and what is not assessed. They must never
   give the wells paragraph or a repeat search.
3. **Targets the way a council sets them.**
   - Add "cheapest design meeting X% CO2", with an explicit "target met / best possible" line.
   - Make "lowest CO2" pick within reason, or show cheapest / balanced / greenest.
   - Give designs unique, kept names so "compare with the first design" works.
   - Before a public meeting: a one-doublet-out check, and an honest "not assessed" list
     (seismicity, network cost, drilling risk).
