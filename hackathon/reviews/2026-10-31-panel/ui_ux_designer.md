# Review panel: UI and UX designer (engineering and data tools)

What I reviewed: the 11 panel screenshots, plus 20 more I took from the fixture build (`panel/shots/ux_*.png`; crops in `panel/ux/`). I read the components in `frontend/src`. I ran one live thread on :8792 (`ux-1`), sending these three messages:
1. "Design a geothermal heating and cooling system for the challenge district, lowest cost."
2. A click on 1 to run with the inputs as shown.
3. "and if the heating network came back at 50 degrees instead?"

Viewport: 1440 px wide, at 1x scale.

## 1. Verdict

The pieces are good. The inputs card, the steps rows, the inspector, Economics and Sensitivity are well-built, modern data UI. The problem is that the screens don't agree with each other, and this breaks the team's own rule that what you see must be what is really happening.

In one chat, a judge sees all of the following:
- **One design, three costs.** The same design is shown at 61.8, 64.2 and 64.3 €/MWh.
- **Three designs, one code.** Three different designs are all called `2D-HP-AB`.
- **Two "chosen" tags on one page.** Compare marks two different designs as "chosen".
- **A what-if that contradicts itself.** Its reply says "2D-HP-AB remains optimal" and then "searching again picks 1D-HP-AB".
- **A plant diagram that can't be read.** It draws its labels 5–9 px high at normal zoom, and full screen doesn't make it bigger.

None of these are physics problems. They are naming, formatting and layout decisions, and each one makes a judge doubt numbers that are actually right. Fix identity, the headline metric and rounding first. Then make the canvas readable.

## 2. What works (keep it)

- **Inputs card** (`ux_confirm_top.png`, `01_inputs_card.png`):
  - The bar shows 2 read / 3 fixed / 1 derived / 6 assumed / 1 asked.
  - Each row carries a provenance badge, and file chips cite the section they came from.
  - A big "Run the design with these inputs" button sits next to an inline "type what to change" field.
  - This is the best screen in the app. It shows what was read and what was assumed at a glance.
- **Steps as tick-off rows** (`ux_confirmrun_top.png`):
  - Each row has a label, a tool-call chip (`search_designs(20 combinations, objective=cost)`), a "rules decided" or "model decided" tag and a time.
  - The last row, "Check the answer's numbers · every number traced", is a strong trust signal.
  - Collapsed to "Worked for 2.2 s · 8 steps · 3 model calls", it is a good default.
- **Design-tab inspector** (`ux_U2_producer2.png`):
  - Text is large and readable, with a ring gauge and a sparkline of the year.
  - It lists checks per part and has an "Ask about this" link.
  - The diff strip on user designs is clear and honest: "U2 against 2D-HP-AB … Cost of heat 64.3 → 69.3 €/MWh ↑ +5 €/MWh".
- **Economics and Sensitivity** (`08_economics.png`, `ux_econ_full.png`, `ux_tab_sensitivity.png`):
  - Economics: KPI tiles against gas, a line-by-line cost waterfall that ties to a stacked total, and a cash-flow chart with "Pays back in year 10". Clear for a non-economist.
  - Sensitivity: parameter chips are coloured like their chart lines, and the run-count estimate is accurate (226 = 1 + 10 + 15 + 200).
- **Decision card for an infeasible brief** (`panel/ux/inf_1.png`):
  - Each option has a coverage bar, the recommended one is highlighted, and there is a single Continue button.
  - The canvas also has good accessibility: nodes have aria labels, Enter inspects a node, and the tablist supports arrow keys.

## 3. Issues (most important first, ranked by the damage done in a judge's first five minutes)

### 3.1 HIGH: one design, three "costs" and two roundings; the headline metric is not the one that picked the design

**What I saw:**
- **The pick is made on heat and cold together.** The inputs card's "Design for" row says "lowest cost of heat and cold". The rank step says "2D-HP-AB has the lowest cost of heat and cold of the 35 designs".
- **The candidate list in "How I got here" uses that metric:** `2D-HP-AB … 61.8 €/MWh` (`02_design_reply.png`).
- **The result card's headline tile uses a different one:** "Cost of heat 64.3 €/MWh" (`ux_confirmrun_result.png`).
- **The chat's "Designs compared" card defaults to "Cost of heat" and shows 64.3.** It has no heat-and-cold tab at all: the only metrics in `ComparisonCard.tsx` are lcoh, co2, lcoc and capex. Its bars are not sorted either: 64.3, 67.9, 65, 77.1, 92.2.
- **The prose says 64.2.** In live `ux-1` the result card value is 64.25. Python's round-half-even writes "64.2" in the prose, and JS `toFixed` shows "64.3" on the card. I verified both in this environment.
- **The what-if turn mixes the two metrics.**
  - Prose: "Heat and cold cost 60 €/MWh (was 61.8)".
  - Card: "Cost of heat 62.3 €/MWh −1.9 €/MWh" (`03_whatif_card.png`).
  - Live reply: "lowers the cost of heat to **60 €/MWh**". But 60.02 is the heat-and-cold figure; the card's cost of heat is 62.32.

**Why it matters:** a judge sees 61.8, 64.2, 64.3 and 60 for "the cost" within 30 seconds and concludes the numbers are unreliable, even though every one of them is correct for its own definition.

**Do instead:**
- Make the objective the headline everywhere: "Cost of heat and cold 61.8 €/MWh", with heat 64.3 and cold 50.1 as smaller lines underneath. This applies to the result card, the what-if card, the design picker and the Compare default (Compare already defaults to `lcoe`).
- Add "Heat and cold" as the first tab of the chat's comparison card and sort its bars by the selected metric.
- Use one number formatter. Either the backend sends pre-formatted strings, or it rounds half-up with `Decimal` to match JS.
- Use a fixed number of decimals per metric:
  - "65.0", not "65", in `02`;
  - "64.0", not "64", in `04`;
  - "60.0%", not "60%", in the U2 diff.

### 3.2 HIGH: design identity is ambiguous; the code names a layout, not a design

**What I saw:**
- **The design picker lists five designs under two codes.**
  - `2D-HP-AB` three times: the agent's pick, the what-if "reservoir −5 K" and the what-if "heating return 50 °C".
  - `1D-HP-AB` twice (`ux_picker.png`).
  - The dark code badge, which is the strongest visual element, is identical across them. Only an 11 px teal subtitle tells them apart.
- **The Compare bubble chart labels two bubbles "2D-HP-AB (what-if)" and two "1D-HP-AB (what-if)"** (`panel/ux/cmp_2.png`).
- **The Design tab diff for a what-if reads "2D-HP-AB against 2D-HP-AB … before the what-if"** (`ux_design_whatif.png`).
- **Codes grow long and use I-versus-1 glyphs:** `2D-HP-AB-2I1-ST-BL`.
- **In the candidate list, descriptions are cut off exactly where the designs differ.** Four rows read "2 doublets at 2,500 m, heat pump top-up with a backup boiler, absorp…" (`02`), and the ST and BL suffixes are lost.

**Why it matters:** "never ambiguous" fails at the level of names. A judge cannot tell which 2D-HP-AB they are looking at on Economics or Energy.

**Do instead:**
- Give every design a unique short id, as already done for U1 and U2.
  - For example, A1 for the agent's pick, W1/W2 for what-ifs and U1/U2 for user designs. The old fixtures used A1/D1/O1, so the pattern exists.
- Show the layout code as a secondary monospace chip, and the change as a chip next to it: "W2 · 1D-HP-AB · return 50 °C".
- Do this in the closed picker, the bubble labels and the diff strip too.
- In list rows, lead with what differs ("+ a treatment train per doublet", "hottest first") instead of the shared prefix.
- Put a one-line legend for the code letters in a popover: D = doublets, HP/BO = top-up, AB/EC = cooling, ST, BL, 2I, PL, IU, IL.

### 3.3 HIGH: the plant canvas is unreadable at normal zoom, and full screen doesn't help

**What I saw:**
- **At 1440 px the React Flow viewport fits at `scale(0.4765)`.** Node fonts are 10–20 px in CSS, so they render at 4.8–9.5 px. I measured this in the page.
- **Only the big numbers (300, 14.5) are legible.** "2,500 m · fully open · mean 212 m³/h · 330 days" and every edge label (56 °C, 86.1 °C, 14.5 MW) are 4–5 px (`panel/ux/crop05a.png`, `crop05b.png`).
- **The diagram uses about 330 px of a roughly 1,000 px tall canvas.** The other two-thirds are empty (`05`, `06`).
- **Full screen fits at `scale(0.479)`, the same size** (`ux_plant_fullscreen.png`), and the floating inspector covers the right edge.
- **The wells' open parts are hard to see.** They sit in a 30 px reservoir band. Full, upper-half and lower-half openings differ by about 10 px, and their labels ("P2 lower half open 2,500–2,550 m") are about 5 px.
- **Line crossings:**
  - The grey return header drops to Injector 2 across the orange supply header, and nothing marks that it is not a junction.
  - Dashed "Electricity" lines run along the bottom just above the reservoir band, under all four well risers.
- **Two line types share one style.** The legend draws "Electricity" and "Heat to the towers" as near-identical grey dashes.
- **Brine colour collides with the cooling network.** In the 50 °C what-if (`ux_design_whatif.png`) the 45.8 °C return brine turns blue, the same blue as "Cooling network".
- **A word sits in the number slot.** The gas node shows the word "Burning" where every other node shows a number.

**Why it matters:**
- This is the hero visual of the Design tab, and it is the first thing a judge clicks after the chat.
- Doublets, treatment trains and open parts are your differentiators, and none of them can be read without zooming in and panning.

**Do instead:**
- **Reflow the layout to fit the canvas's aspect.** Put the surface plant on top (treatment → exchanger → heat pump → demand), cooling on the right, and the doublets and reservoir below at full width. Fit should then reach a scale of 0.85 or more at 1440 × 900.
- **Use semantic zoom.** Below about 0.7, show only each node's name and one value at 14 px or more; reveal the detail rows when zoomed in.
- **Make full screen hide the year player and dock the inspector,** then fit again to the larger area.
- **Draw a small to-scale well section per doublet** in the inspector or a strip under the canvas: aquifer top and bottom, with the screened interval per well.
- **Mark crossings with line hops** (P&ID style).
- **Give the line types distinct styles:** electricity as dotted amber, "heat to towers" as dashed cyan.
- **Use one neutral brine hue** (for example brown-grey) with temperature labels, so the brine never turns network blue or orange.

### 3.4 HIGH: the what-if card hides the turn's most important outcome, and the reply contradicts itself

**What I saw:**
- **The answer that matters is only in the prose.** The what-if card (`03`) shows heat covered, cost of heat and CO₂ for 2D-HP-AB under the change. The headline result, "Searching again under the change picks 1D-HP-AB at 56.5 €/MWh instead of 2D-HP-AB", appears only in the last sentence.
- **The live reply contradicts itself.** It opens "the **2D-HP-AB** design … remains optimal" and ends "Searching again under the change picks 1D-HP-AB".
- **The card disagrees with the Design tab on CO₂.**
  - The card shows "CO₂ saving 69% +9 points".
  - The Design tab shows "68.8% +8.4 pt" for the same change, and the prose says 68.8% (was 60.4%).
  - So the card rounds each value first and then subtracts.

**Why it matters:** iterative improvement is the scored behaviour. The UI should make "the change flips the pick" impossible to miss, not bury it.

**Do instead:**
- Give the what-if card a second row: "Searching again under this change → 1D-HP-AB 56.5 €/MWh (3.5 below 2D-HP-AB at 60.0) · Open in Compare".
- Compute deltas from unrounded values.
- Have the claim checker flag "remains optimal" when `search_again.code != base.code`.

### 3.5 HIGH: the result card's temperature strip shows something the plant doesn't do

**What I saw:**
- **The strip under the result card's title reads "86.1 °C wellhead · 81.1 °C to the heat pump · 56 °C rejection"** (`ux_confirmrun_result.png`). It gives the heat exchanger a 17% sliver, labelled "Heat exchanger …" because the label is cut off, and the heat pump 83%.
- **81.1 °C is not a brine temperature.** In `engine.py`, `hex_outlet = min(wellhead − approach, heat_supply)` is the network-side outlet. The Design inspector correctly labels it "Network out 81.1 °C".
- **The strip contradicts the bar right below it.** The share-of-heat bar says the exchanger gives 51.8% of the heat and the heat pump 20.8%.

**Why it matters:** it is a visual that is literally wrong, placed at the very top of the first result.

**Do instead:** remove the strip. The heat-split bar already tells the story. If you keep it, draw the brine path with real brine temperatures: wellhead → after the exchanger → after the heat-pump evaporator → reinjection.

### 3.6 MEDIUM: Compare opens on the wrong search, shows two "chosen" tags, and its head-to-head mixes assumptions

**What I saw** (`07_compare.png`, `panel/ux/cmp_1..3.png`):
- **Opening on the wrong search.** "Open in Compare" always lands on the newest search. After one what-if, the first reply's link opens "What search 3 tried", where 1D-HP-AB is marked "chosen".
- **Two "chosen" tags on one page.** The same page lists 2D-HP-AB as "agent · chosen" under "This chat's designs".
- **The designs a judge cares about are buried.** "This chat's designs" and Head to head start about 2,900 px down, below 32 candidate rows.
- **Rank numbers jump.** They read 1, 2, 5, 8, 15, 18… in Layouts, then 3, 6, 7, 4, 9, 11… in Variants.
- **Filter chips use undefined abbreviations.** "HP BO AB EC" is explained only in tooltips, and nothing shows that "no chips selected" means all designs are shown.
- **The suggested question at the top is broken English:** "Why are 1D-HP-AB · heating return temperature 50 °C, searched again's heat and cold together cheaper than 2D-HP-AB · heating return temperature 50 °C's?"
- **Head to head:**
  - The long design name overprints the "Difference" column header.
  - The winner chips repeat that long name six times and run outside the card's right edge.
  - Signs read A − B: the better side gets "+5 years" for payback and "+5.3 €/MWh" for cost.
  - It compares 2D-HP-AB at 60 °C return with 1D-HP-AB at 50 °C return and gives no warning that the assumptions differ.
- **Bubble legends don't match the data.** "area is capital: 5 and 20 M€", while the bubbles range from 25 to 49 M€.

**Do instead:**
- Deep-link "Open in Compare" to the search the reply came from (`#compare?search=S1`).
- Use "best in this search" on the search panel and keep "chosen" for the agent's current pick.
- Put "This chat's designs" and Head to head first. Collapse the search table to its top 5, with a funnel line ("20 layouts → 280 sizings → 35 met every cap → 1 picked").
- Spell out the filter chips ("Heat pump", "Gas boiler", "Absorption", "Electric chillers").
- Write differences in words ("5.3 €/MWh cheaper", "pays back 5 years sooner"). Use short ids in chips and headers.
- Add an amber banner in Head to head: "Different assumptions: heating return 60 °C vs 50 °C".

### 3.7 MEDIUM: the chat reply is long and compares the same designs three times

**What I saw:**
- **The first design reply runs about 3.5 screens:**
  - prose;
  - the result card with KPI tiles, two split bars, a monthly chart and size chips;
  - the "How I got here" scatter plus a candidate list;
  - "Designs compared" with 4 metric tabs.
- **These are three views of the same ranking, and they disagree on the number** (61.8 against 64.3, see 3.1).
- **The scatter hides its own subject.** The chosen point is an orange ring under a cluster of teal dots. The y range is 57–86 to include the gas reference, so the cluster is squashed. The y-axis label is cut off: "€/MWh, heat ar…" (`04`).
- **The live reply repeats itself.** In `ux-1` it states the result twice, almost word for word: "It meets all daily heating and cooling demands for 64.2 €/MWh…" and, at the end, "It meets heat at 100 °C and cold at 20 °C every day of 2027 for 64.2 €/MWh…".
- **Emphasis is diluted.** Every number in the prose gets a teal pill; the what-if paragraph has 20 of them (`03`).
- **Small text error.** A full stop is missing in the baseline note: "so it cannot rank them A treatment train" (`02`).

**Do instead:**
- Merge the three views into one "Why this design" block: a sorted bar list by the objective (top 5 plus the gas reference), with a "scatter" toggle that zooms to the cluster and draws the chosen point on top with a label.
- Move the monthly chart out of the chat; it already lives in Energy. Keep the KPI tiles and the two split bars.
- Highlight only the 2–3 numbers the decision rests on.
- De-duplicate the reply's last paragraph when the model's text already states the result.

### 3.8 MEDIUM: the steps rows are almost right

**What I saw** (`ux_confirmrun_top.png`):
- **Many rows read "0.00 s".** Nine of 12 rows show it.
- **Python leaks into the UI.** The answer step shows `answer(self, project, 2D-HP-AB, history, draft)`; this is emitted live too.
- **A sentence is cut mid-word:** "UNDERSTOOD The user asked: Design a geothermal heating and cooling system for this dist".
- **The counts never add up into one story.**
  - In the steps: 20 combinations → 280 sizings → `verify_design(35 candidates)` → `improve(10 candidates)` → `rank(35 designs)`.
  - In Compare: "32 layouts · 500 sizings · 960 simulated years".
- **"7 agents took part" overclaims.** It shows letter avatars R L P E V E W, with two "E"s. Planner, Verifier and Economist are rules or code (`AgentsPanel.tsx`), not models.
- **Fixture-only tag text:** the replay shows "scripted decided".

**Why it matters:** "7 agents" plus avatars reads as 7 LLM agents, which breaks the "what you see is what happens" rule, and judges for an agentic track will check exactly this.

**Do instead:**
- Show "<10 ms" or no time at all.
- Drop `self`.
- Truncate on word boundaries.
- Add a funnel chip row at the top of the steps.
- Label the roles honestly: "7 roles · 3 on models (Reader, Writer, Fact-checker), 4 rules/code", with a model or code glyph on each avatar.

### 3.9 MEDIUM: the GEMINI project canvas is an expert node editor that a non-GEMINI user cannot read

**What I saw** (`10_gemini_U2.png`, `11_gemini_pick.png`, `ux_gemini_run.png`):
- **Code names and unreadable ports.** Components are snake_case (`producer_well_1`, `filter_a_1`, `brine_splitter`). Port tables render at about 4 px.
- **Before running there is nothing to read.** The canvas has no values until "Run with GEMINI".
- **Editor controls take the stage.** "Every port", "Paste JSON", Import and Export sit in the main toolbar. The palette offers "Combined heat and power", Adder and Mixer, which are irrelevant to the judge's question.
- **The team's best GEMINI evidence is written in code.** After a run it reads: "injector_well_1.power_el 0.221 MW fixed against 26.4 kW released (+738%)".
- **One word, two machines.**
  - In the GEMINI view, `boiler` is "Gas boiler · burns the separated gas".
  - In the Plant view, "Boiler 11.6 MW" is the network's backup gas boiler, and the produced-gas burner is a node called "Gas · Burning".
- **Two kinds of names for the same parts.** The Plant view says "Injector 1A" and "Treatment train 1"; the GEMINI view says `injector_well_1a` and `separator_1` + `filter_a_1`.

**Do instead:**
- Default this sub-tab to a plain "GEMINI check" summary. Per well: wellhead temperature, pump power and injection pressure, "with our 11 fixes" against "GEMINI as released", as paired bars with plain names. Lead with "Injection pump power, doublet 1: 221 kW with fixes vs 26 kW as released (8.4×)".
- Put the node editor behind "Open the GEMINI editor (for GEMINI users)".
- Rename the GEMINI `boiler` to "produced-gas burner" everywhere.

### 3.10 MEDIUM: names and units drift between chat and tabs

Each item below is small, but together they read as carelessness:

| What drifts | Where |
|---|---|
| CO₂ is shown as "−60%", "60.4% less", "CO₂ saving 60.4%" and "69%" | result card, chat prose, Compare, what-if card |
| "Doublet in use 3,007 h a year" in chat; "Doublet full-load hours 3,007 h" in Energy | same number, two labels. The doublets actually run 330 and 226 days, so "in use" is wrong |
| Raw variable name `treatment_scale_exponent 0.6` | Economics assumption chips (`08`) |
| "Surface plant (per MW)" and "Surface plant" as two separate lines; "2 producer(s), 2 injector(s)" | Economics capital list |
| "Chillers 9.0 MW" vs "Electric chillers"; "BO" vs "Boiler" vs "Gas boiler" | chat vs tabs |
| "5.2 %" vs "5.2%" | Economics vs inputs card |
| "Open part" used as the label of two different tiles | Producer 2 inspector |
| Header "720 tokens · 5.2 s" | not scoped: is it this turn or this chat? |

### 3.11 LOW–MEDIUM: one colour means different things on different tabs

**What I saw:**
- **Orange** is geothermal or the heating network (Energy, Plant), "what-if" (Compare), and the reservoir-temperature line (Sensitivity).
- **Purple** is boiler (Energy), gas (Economics), "your design" (Compare), and "low end of range" (Sensitivity tornado).
- **Blue** is the cooling network, and also cold brine on the canvas.

**Do instead:**
- Reserve the energy palette for energy flows.
- In Compare, mark provenance with shape or outline (ring = agent, dashed = what-if, square = yours).
- Draw the tornado's low and high ends in two greys.

### 3.12 LOW: accessibility

**What I saw:**
- **Muted text fails WCAG AA (4.5:1) for small text:**
  - `--ink-4` #8A959E is 3.06:1 on white and 2.79:1 on the ground colour #F3F5F5. It is used in 30 rules: Compare table units, the "UNDERSTOOD" label, Sensitivity scale captions, Economics help text.
  - #9DB4B6 is 2.18:1, used in 13 rules.
- **Faded nodes are worse.** On the canvas, the "off" nodes (the cooling side on 28 Jan) are faded below even that.
- **The scatter marks "chosen" by colour alone**, and the point is hidden under others.

**Do instead:** darken `--ink-4` to about #6F7A83, which is at least 4.5:1. Keep the canvas aria labels and tablist keys; they are good.

### 3.13 LOW: replay hygiene (it matters if a demo video is recorded from fixtures)

**What I saw:**
- **Replay is signalled four ways.** The header's red "Server offline", the amber "agent server isn't answering" banner over the composer, "Fixture data" and "Replay" all appear together.
- **Stale fixtures.** The `infeasible` scene still uses old codes (A1, D1, O1) and "17 of 17 checks".
- **Sensitivity results don't match the controls.** In fixture mode the controls say electricity 80–220 and 200 samples, the results show 120–220 and 60 samples, and the status reads "Up to date: 86 model runs".
- **Evidence hides a gap.** It shows "GPU 46 of 50" next to "CPU 32 of 34" and doesn't say that 16 scenarios were not run on CPU.

**Do instead:**
- In replay mode, show one "Replay" chip and hide the offline banner.
- Re-record the fixtures.
- Draw scenarios that were not run as grey squares in the Evidence strip.

## 4. Implement differently or remove

- **Remove** the result card's temperature strip (3.5) and the monthly chart in the chat result card. Energy owns that chart.
- **Merge** "How I got here" (scatter + list) and "Designs compared" into one "Why this design" block, sorted by the objective.
- **Collapse** the Economics "Cost of heat" list from 18 lines to its 6 groups (Capital, Fixed O&M, Variable O&M, Electricity, Gas, CO₂), with the line-by-line list on expand. The stacked total bar already shows these groups.
- **Move** the GEMINI node editor behind an "advanced" disclosure, and put Paste JSON, Import and Export into an overflow menu. Make the default a readable "GEMINI with fixes vs as released" summary.
- **Reorder Compare:** this chat's designs and Head to head first, then the search, with a funnel line. Number the rows in the order they are shown.
- **Rename** "7 agents" to "7 roles (3 on models)". Rename the GEMINI `boiler` to "produced-gas burner". Replace the repeated layout codes with unique design ids, keeping the code as a secondary chip.
- **Header:** show one connection state instead of four signals. Label the token and time pill's scope ("this chat").

## 5. Top 3 priorities before the deadline

1. **One name, one metric, one rounding across chat and tabs.**
   - Give each design a unique id (A1, W1, W2, U1…) with its layout code and change as chips.
   - Make "cost of heat and cold" the headline everywhere, since it is what the agent optimises.
   - Use one half-up formatter with fixed decimals per metric.
   - This removes most of the "which number is true?" moments: 61.8, 64.2, 64.3, "+9" against "+8.4", and three designs called 2D-HP-AB.
2. **Make the plant canvas readable at 1440 × 900 without zooming.**
   - Reflow the layout to the canvas's aspect so it fits at a scale of 0.85 or more.
   - Use semantic zoom, and make full screen actually enlarge the drawing.
   - Add a small well-section view for open intervals.
   - Use line hops at crossings, distinct electricity and tower lines, and a brine colour that never matches the cooling network.
3. **Make iteration visible and honest.**
   - The what-if card states the re-search outcome ("the pick changes to 1D-HP-AB, 56.5 €/MWh").
   - "Open in Compare" opens the search it came from.
   - Head to head warns when assumptions differ, and its header and chip overflow is fixed.
   - Remove the mislabelled temperature strip.
