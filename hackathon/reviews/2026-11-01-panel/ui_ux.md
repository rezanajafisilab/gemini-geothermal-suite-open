# Review panel round 2 (1 Nov): UI and UX designer (data-heavy engineering tools)

**Method.** I drove the built app on :8790 in my own headless Chrome at 1440×900. The browser chat was `ux-b1`, seeded so it follows the panel's naming. In it I ran 7 turns:
- design;
- what-if: reservoir −10 K;
- ESP failure 10–24 Jan;
- compare A1/A9/A33;
- what-if: gas at 30 €/MWh;
- boiler failure on A9;
- one user edit (3 doublets, through `panel.py edit`).

I ran 12 more turns on the command line (`ux-c1`) to test different wordings. I measured the canvas's scale and the rendered font sizes in the page, and read the components.

Screenshots are in `scratchpad/panel2/ux/shots/`. The command-line transcripts are in `scratchpad/panel2/ux/stress/`.

## 1. Verdict

Round 2 fixed the most visible things:
- The result card leads with the cost of heat and cold.
- It shows the four picks, the spare on the peak day and the one-unit-out strip.
- The what-if card states "THE PICK CHANGES / STAYS".
- The plant canvas is readable on the page and fits at 0.867 in full screen.
- One-decimal rounding now agrees between Python and the browser.

But "what you see is what really happened" now breaks in a new and worse place: **assumptions leak between scenarios**.
- After a single what-if ("gas at 30 €/MWh"), the Economics tab says the recommended design costs **"+21.6 vs gas"**. That compares it with a gas plant priced at 30 €/MWh, and the same row reads "NPV against gas +26.0 M€".
- Compare ranks a gas-at-30 what-if first and tags it "best overall · most reliable".

Names are unique only inside the chat cards:
- The Design picker lists four designs with the identical chip `1D-HP-EC-N1`.
- An edited design gets the name **A1** a second time.

The "Most reliable" label is ambiguous enough that the model invented a false reason for it.

Fix the scenario leak and identity first. Most of the rest is presentation.

## 2. Stress test

| Request | Wordings tried (exact) | Right / wrong | What went wrong |
|---|---|---|---|
| Compare designs by name or role (COMPARE card) | "Compare A1 with A9 and A33 side by side." · "compare the cheapest one with the recommended one" · "vergelijk A1 en A9 even naast elkaar" · "A1 vs A33 pls" | **4/4** right designs, right figures | Every reply prints the same table 2–3 times: the model's Markdown table, then the template's table, then the card. The Dutch reply gets the English template table appended. "co₂:" is lower-case. The Dutch table bolds both 69.8 and 68.1. |
| Why a pick has its label | "Why is A2 listed as most reliable when A1 also survives any one unit out?" | **0/1** | The reply is invented: "A1 … does not explicitly guarantee N-1 for every possible component failure" and "A2 costs **+2.00 M€** more capital than A1". In fact both are reliable plans, A2 is +0.9 M€ (31.5 against 30.6), and A2 is 0.03 €/MWh *cheaper* (69.77 against 69.80). The label caused the misunderstanding (issue 3.4). |
| Failure on dates | "What happens if the ESP of doublet 1 fails from 10 to 24 January?" · "For A9, what if its boiler is out from 20 to 31 January?" · "the heat pump breaks down for two weeks" · "if we lose a pump, what then?" · "wat als de warmtepomp in februari twee weken uitvalt?" · "ESP failure 10/01-24/01 on doublet 1, impact?" | **4/6** | Two wordings ran the wrong window (see below). The "two weeks" reply is garbled after the claim check: "demand 30 MW).", "supply.", "[1D-HP-EC-N1 operation]". |
| What-if, and does the pick change | "what if the reservoir is 10 °C colder than we think — does the pick change?" · "and if gas were only 30 €/MWh, would you still pick A1?" · "what if electricity costs 50% more - would A1 still be the pick?" (278.55 €/MWh, correct) · "Wenn der Gaspreis nur 30 €/MWh wäre, bleibt die Empfehlung gleich?" · "check it with the reservoir 10 °C colder, then tell me if the pick changes and by how much" | **4/5** replies; **5/5** cards | Several replies contradict or mislabel their cards (see below). |
| Same names across chat, Design and Compare | the 6 designs in `ux-b1` | Consistent in the chat cards; inconsistent in the tabs | The Design picker shows no names. The edited design is "A1 · U1". Compare's search table numbers rows differently from the chat's names (issue 3.3). |

**Failure wordings that went wrong:**
- "wat als de warmtepomp in februari twee weken uitvalt?" (two weeks in February) ran all year: "the heat pump out 1 Jan–31 Dec".
- "ESP failure 10/01-24/01" also ran all year. Its prose then says "a spare ESP … would save about **5,905 k€** for a 3-day repair window".

**What-if replies that contradict or mislabel their cards:**
- **German gas question:** the reply says "Ja, die Empfehlung … bleibt gleich … 1D-BO-EC-N1 ist … teurer". The card below says THE PICK CHANGES to C1 at **53.4** (cheaper than 56.2).
- **Reservoir question:** the reply opens "Yes, the pick remains". It calls 78.4 "the cost of heat", but that is heat and cold; heat alone is 86.1.
- **Reservoir −10 K:** under the change, A1 loses N-1 ("1 of 5 cases short"). The reply still says "passes all checks" (issue 3.5).

**Total: 12 of 16 wordings handled right (75%).** The cards were right more often than the prose.

## 3. Issues (most important first)

### 3.1 HIGH: a what-if's assumptions leak into Economics for every design

**Message:** "and if gas were only 30 €/MWh, would you still pick A1?", then open Economics for A1.

**What happened** (`shots/19_econ.png`): A1 is priced at today's gas price of 69.4 €/MWh, but every comparison on the page is against a gas plant priced at 30 €/MWh.
- "Cost of heat 75.7 €/MWh **+24.9 vs gas** · gas plant 50.8 €/MWh"
- "Heat + cold 69.8 **+21.6 vs gas** · gas plant 48.2 €/MWh"
- On the same row: "NPV against gas **+26.0 M€** · pays back in year 10"

The cause: `/api/workbench` sends `reference` from the *last* search, S3 (lcoh 50.77, lcoe 48.21, priced at gas 30). `currentBaseline()` then uses it for every design. S1's reference is 92.24 / 82.41. The chat's candidates card still says "Baseline … 92.2 €/MWh for heat".

**Why it matters:** One what-if turns the recommended design from "18% cheaper than gas" into "45% dearer than gas" on the page judges open to check the economics. The red tile also contradicts the green NPV next to it.

**Do instead:**
- Price each design against the reference of its own search and its own assumptions.
- Show the scenario on the page ("prices as in S1: gas 69.4 €/MWh").
- Never mix scenarios in one subtraction.

### 3.2 HIGH: Compare ranks and tags designs across scenarios, and says it doesn't

**What happened** (`shots/20_compare_chat.png`, `20b_compare_chat.png`): "This chat's designs" is subtitled "at the chat's current assumptions", but the rows mix scenarios.
- **Row 1** is "C1 · 1D-BO-EC-N1 53.4" (gas at 30), tagged "best overall · most reliable".
- **Row 3** is "A1 … 69.8 · recommended".
- **B1** (reservoir −10 K) is also tagged "best overall · most reliable".
- **The edited design** is tagged "best overall"; it inherited A1's picks.
- **Head to head** opens on A1 against C1: "A1 is better on 4 of 10 figures". The NPVs are computed against different gas plants, and nothing warns that the assumptions differ.
- **The Search 2 banner** says "you have changed them since", but I changed nothing; it was a what-if search.

**Do instead:**
- Group or filter this chat's designs by scenario (Base · reservoir −10 K · gas 30 €/MWh), with a scenario chip on every tile and bubble.
- Only rank within one scenario.
- Scope the pick tags ("best overall in search 3, gas 30 €/MWh").
- Put an amber banner in Head to head when the two sides' assumptions differ.
- Reword the stale-search banner to "This search ran a what-if (gas 30 €/MWh); the base case uses 69.4".

### 3.3 HIGH: names are unique in the chat cards, but not in the tabs

**What happened:**
- **The Design picker** (`shots/07_picker.png`) shows only `d.code`. After six turns it lists A1, B1, W1 and W2, all as the identical chip `1D-HP-EC-N1` with the same long name. Only small tags differ ("agent · chosen", "what-if: reservoir -10 K, searched again" …). `DesignPicker.tsx` never renders `uid`.
- **An edited design gets the parent's name.** `create_design` copies the parent (`model_copy`), keeping `uid` "A1" and setting `code` to "U1". The edit therefore becomes **"A1 · U1"**, named "A1 · 1D-HP-EC-N1, edited". In Compare it shows an "A1" chip and the "best overall" tag. There are now two A1s.
- **Compare's search table numbers rows by rank, not by name.**
  - Row "**2** 1D-HP-AB" is the chat's **A9** (cheapest).
  - Row "**9** 1D-HP-AB-N1" is the chat's **A2** (most reliable).
  - A judge who looks for "A9" finds the wrong design.
- **The what-if card never names its own design.** W1 and W2 never appear on their cards. The card says "on 1D-HP-EC-N1 … against A1 · 1D-HP-EC-N1", and only the link goes to W1.
- **Compare's chip row and bubble labels drop the names**, e.g. "1D-HP-EC-N1 (what-if)" three times.
- **Reply links point to codes:** `#design/1D-HP-EC-N1` fits no design id and silently opens the chosen design.
- **The picks A2, A9 and A33 cannot be opened.** They are not in the picker, and the pick tiles are not clickable.

**Do instead:**
- Make the name primary everywhere: picker, Compare chips, bubbles, head-to-head selectors, the what-if card head ("W1 · reservoir −10 K"), prose and links.
- Give user designs "U1 · <layout code>".
- Number the Compare table with the A-names.
- Make each pick tile open its design, and add it to the picker on demand.

### 3.4 HIGH: "Most reliable" is the wrong label, and rounding hides the difference

**What happened** (`shots/02_chat_500.png`): the picks read "Best overall A1 … **69.8** €/MWh · 14,103 t · 30.6 M€ · any one unit out: met" and "Most reliable A2 … **69.8** €/MWh · 14,334 t · 31.5 M€ · any one unit out: met".
- The two are equally reliable, and A2 looks worse on every visible figure.
- The rule ("cheapest such plan") is only in a hover title.
- The ranking rule that makes the cheapest design **A9** and the lowest-CO₂ one **A33** is invisible.
- "How I got here" says "ranked by cost", but the ranking is reliable plans first, then cost with CO₂ at 137 €/t.
- The model's invented answer (section 2) is the predictable result.

**Do instead:**
- Rename the pick to "Cheapest reliable plan".
- Hide it, or mark it "same as best overall at today's CO₂ price", when it is the same layout family within 0.1 €/MWh.
- Add the deciding row to the tile: "with CO₂ at 137 €/t: 76.4 against 76.5".
- Put the rule under the label, not in a tooltip.
- Make the "How I got here" chip read "reliable plans first, then cost with CO₂ at 137 €/t".

### 3.5 HIGH: a what-if can quietly break N-1, and the UI still says the plant is reliable

**Message:** "check it with the reservoir 10 °C colder, then tell me if the pick changes and by how much"

**What happened:**
- **The data shows the loss.** W3's firm data says "one unit out: **1 of 5 cases short**: one of the 3 boiler units, 3.4 MW heat on 28 Jan".
- **The prose denies it:** "it still covers 100% of both demands and **passes all checks**".
- **The card doesn't show it.** The compact what-if card never renders `firm`; `FirmStrip` is only on the full card.
- **The design still claims it.** It keeps the "N1" chip and the name "sized so that any one unit can be out (N-1)" in the picker and in Compare.
- **The status line leaves it out.** "11 of 11 checks" does not include N-1.

**Why it matters:** reliability is now the headline differentiator, and the UI asserts it in exactly the case where it is false.

**Do instead:**
- Add a fourth figure to the compact card: "One unit out: met → **1 case short** (boiler unit, 3.4 MW on 28 Jan)".
- Turn the N1 chip amber ("N-1 lost under this change").
- Count N-1 in the status line ("11 of 11 checks · N-1 not met").

### 3.6 HIGH: the FAILURE card's money doesn't add up, and its verdict contradicts its own note

**What happened** (`shots/10b_failure_card.png`, `21b_fail_A9_card.png`, `stress/07.txt`):
- **A1, ESP out 10–24 Jan.** The tag says "**No spare needed**". The card shows "Extra gas 4.18 GWh · 601 t CO₂ · **272 k€**", then "a spare ESP … saves 3.35 GWh of gas (**282 k€** with its CO₂) for about 13 k€ a year". Saving 80% of the gas is shown as worth more than the whole outage. The cause: `extra_cost_keur` is the net change in running cost, while `money_saved_keur` is gross gas plus CO₂.
- **All-year case.** The extra cost is 3,517 k€ while the spare "saves" 5,905 k€.
- **A9, boiler out 20–31 Jan.** The card shows "Extra gas **-4.99** GWh · **-1,009 t CO₂ · -428 k€**". The outage reads as a saving, because 5.27 GWh of heat not delivered has no value.
- **Contradictory verdict.** "No spare needed" sits above a note showing that a spare earns about 20 times its yearly cost.

**Do instead:**
- Use one basis for both figures.
- When heat is not delivered, label the figure "Gas not burned (heat not delivered) 4.99 GWh", grey and not signed, and put a value on the unserved heat.
- Replace the tag with "Every day met · a spare ESP still pays: 282 k€ saved for 13 k€/yr".
- Use real minus signs.

### 3.7 MEDIUM: the new cards ship without their own styles

**What happened:**
- **No padding.** `.failure-card` and `.compare-card` have no CSS. Their computed padding is `0px`, against `14px 18px 16px` on the what-if card. The "FAILURE" kicker, the remedies table, the compare table and the footnotes touch the card edge (`shots/13_compare_card.png`, `21b_fail_A9_card.png`).
- **The day bars don't match their axis.** The failure bars are a fixed 10 px wide, but the axis runs the full width. 12 bars fill the first ~140 px of a ~760 px axis, with "31 Jan" at the far right. The bars have no y scale and no values.
- **Ties are marked on one side only.** On the COMPARE card, "Wells 2 | 2 | 6" bolds only A1.
- **The deciding row is missing.** The card has no row for cost with CO₂ at 137 €/t, so the "best overall" column has no bold cost cell and the card can't show why A1 wins.

**Do instead:** give these cards the padding of the result cards. Make the day bars flex to the axis, or label each bar. Mark ties on both sides. Add the deciding row.

### 3.8 MEDIUM: the prose repeats or contradicts its cards

**What happened:**
- **Three tables per comparison.** Every COMPARE reply prints the model's table, then the template's table with every label in bold, then the card. "(bold in the table)" no longer identifies anything.
- **Mislabels and contradictions:**
  - "the cost of heat rises to 78.4 €/MWh (from 69.8)" (that is heat and cold).
  - "Yes, the pick remains".
  - The German "bleibt gleich" sits above an English template sentence saying the opposite.
- **The template attaches the new pick's description to the old code:** "picks 1D-BO-EC-N1 at 53.4 €/MWh instead of 1D-HP-EC-N1: 1 doublet at 2,500 m, **gas boiler top-up** …".
- **Leftovers and leaked tags:** "demand 30 MW).", "supply.", "Die Energiequellen verteilen sich wie folgt:" followed by nothing, "[1D-HP-EC-N1 operation]", "[1D-HP-EC-N1 what-if]".
- **Codes instead of names.** The prose says "1D-HP-EC-N1" where the cards say A1, W1 or C1.
- **A unit dropped.** The failure prose says "13 k€ in capital"; the card says "13 k€ **a year**".
- **An unclear source chip.** "General background" appears under replies made of tool numbers, without saying which sentence it covers.

**Do instead:**
- When a card is shown, limit the prose to a one-to-two-sentence verdict that leads with the name ("No: C1 · 1D-BO-EC-N1 becomes the pick, 3.0 €/MWh below W2").
- Have the claim checker reject heat against heat-and-cold label swaps, and any "remains" or "bleibt" when `research.changed` is true.
- Strip the source tags.
- Drop the English template when replying in another language.
- Underline the sentences "General background" refers to.

### 3.9 MEDIUM: the chat's search cards still use the old metric and order

**What happened** (`shots/02_chat_1650.png`, `02_chat_2300.png`, `03_scatter.png`):
- **"Designs compared"** still opens on "Cost of heat" and has no heat-and-cold tab. Its bars are unsorted (75.7, 72.3, **75**, 89.7, 92.2), its labels are codes only, and the "89.7" label overprints the dashed gas line.
- **The scatter** hides the chosen point: it is drawn 14th of 52, and 7 dots sit on top of it.
- **The baseline line** says "92.2 €/MWh **for heat**", while the scatter puts gas at about 82 (heat and cold).
- **The list** says "−42% CO₂" where the tile says "−42.1%".
- **The notes** are joined without a full stop: "…leaves every day met Injectors open…".

**Do instead:** use heat and cold as the default tab, sort by the chosen tab, draw the chosen point last with its name, and show the baseline in the headline metric.

### 3.10 MEDIUM: the plant canvas reads well for one doublet; three doublets and N-1 still don't work

**Measured** (font sizes as rendered):

| View | Scale | Text sizes |
|---|---|---|
| A1, page | 0.563 | names 12.5 px, values 16 px, edge labels 11.5 px |
| A1, full screen | 0.867 | details 10–10.5 px, edge labels 9.5 px, provenance badges 8.5 px |
| 3-doublet edit, page | **0.401** | edge labels 9 px, "Doublet n" 9 px; the drawing uses 497 of 1,060 px width |
| 3-doublet edit, full screen | 0.727 | well intervals **7.5 px**, well details 8–8.5 px, edge labels 8 px |

Two-doublet and three-doublet designs are the ones where the canvas matters most.

**Temperatures don't change with the day** (`shots/18_A1_full_summer.png`):
- On 19 Jul the doublet is "stopped, 0 m³/h", but the brine pipes are still drawn at full weight and labelled "86.1 °C / 52.1 °C".
- On 28 Jan the injector card says 60.4 °C (that day's reinjection) while its pipe says 52.1 °C (the design value).
- So one stream carries two temperatures, and neither says which.

**N-1 is not drawn:**
- The Boiler node and inspector say "Size 31.2 MW", not "3 × 10.4 MW".
- The chillers say "15 MW", not "3 × 5 MW".
- The property that makes A1 the recommendation can't be seen in the Design tab.

**Smaller problems:**
- "Gas · **Burning**" is still a word in the number slot.
- Detail rows are cut off ("Produced gas first, then bo…").
- The canvas formats to 3 significant figures ("7.23 MW", "1.04"), while the chat writes "7.2 MW" and the size chips "2.0 MW" against "2" in Compare.

**Do instead:**
- Lay the page view out in the canvas's wide shape, or fit by width with the doublets in a row.
- Fade the brine edges, and show the day's temperature or none, on days off.
- Draw unit counts ("3 × 10.4 MW") with one ring per unit.
- Use one formatter.

### 3.11 LOW: one rounding: one decimal is fixed, two decimals and the edges are not

**Fixed:** 0 mismatches between the Python `num()` and the browser's `fmtNum()` in 3,599 half-way values at one decimal.

**Still open:**
- **Two decimals** (FAILURE card: GWh, M€, "+1.20 €/MWh") differ in the last digit for 41 of 3,624 half-way values. For example, 2.175 shows as "2.17" on the card and "2.18" in the prose. Trailing zeros differ too ("44.10" against "44.1").
- **Whole numbers lose the decimal:** "75", "72 M€", "+5 MW" beside "+10.4".
- **Differences don't match the numbers shown:**
  - The U1 diff shows "75.7 → 94.5 · +18.9".
  - Capital shows "30.6 → 72 M€ · +41.3".
  - Head to head shows "30.6 against 29.8 → +0.9 M€".
- **Hyphens and real minus signs are mixed:** "-4.99 GWh", "reservoir -10 K", "-1.7 €/MWh" against "−17 points".

### 3.12 LOW: carried over from round 1

- "Doublet in use 3,894 h a year". These are full-load hours; the doublet runs 330 days.
- The step counts still don't reconcile: "280 sizings" against "500 sizings", and "20 combinations" against "39 layouts". Many steps still show "0.00 s".
- Raw variable names in the Economics chips: `carbon_long_term_eur_per_t 137`, `treatment_scale_exponent 0.6`.
- The bubble legend "area is capital: 2.5 and 10 M€" sits beside bubbles of 27–31 M€.
- The Head to head header still overprints: "B1·1D-HP-EC-N1ifference".
- Abbreviated filter chips: "HP BO AB EC".
- "Best Overall / Most Reliable / Lowest CO2" are in title case and use "CO2", while the COMPARE card writes "lowest CO₂".
- The edited design's diff strip uses "Cost of heat" instead of the headline cost.

## 4. What users in my role need most that is missing

1. **Scenarios as a first-class object.**
   - **What:** a scenario chip (Base · reservoir −10 K · gas 30 €/MWh) on every design, tile, bubble and figure. Never subtract or rank across scenarios without a banner. Add a "compare under the same assumptions" toggle.
   - **Why:** what-ifs are the scored iteration, and today each one corrupts the Economics and Compare tabs (3.1, 3.2).
   - **Effort:** about a day (server: a reference per search and a scenario label; UI: chip, grouping, banner).
2. **One identity per design, everywhere.**
   - **What:** the name first in the picker, Compare, bubbles, head to head, prose and links. Fix the edited design's name. Number the Compare table with the A-names. Make the pick tiles open their designs (A2, A9, A33 into the picker).
   - **Why:** "never ambiguous" fails at the first click into a tab (3.3).
   - **Effort:** half a day.
3. **A decision board for the four picks.**
   - **What:** one compact table of the picks. Show each pick's rule in words, the deciding figure (cost with CO₂ at 137 €/t), CO₂, capital and the one-unit-out result, with "why A1 and not A2 or A9" in one line.
   - **Why:** judges ask "why this one"; today the answer is spread over hover titles and invented prose (3.4).
   - **Effort:** half a day to a day.
4. **A reliability view.**
   - **What:** a unit-by-case matrix (5 cases, met or short, worst day and MW), units drawn on the canvas ("3 × 10.4 MW"), and an N-1 figure on every what-if card.
   - **Why:** N-1 is the new differentiator, and it is invisible in Design and silently lost in what-ifs (3.5, 3.10).
   - **Effort:** about a day.
5. **A failure timeline.**
   - **What:** the year strip with the outage window shaded, the shortfall and what covered it (the boiler's load rising), and each remedy on the same axis. Use one money basis and value the heat not delivered.
   - **Why:** the current card can't be read as a story, and its money contradicts its verdict (3.6, 3.7).
   - **Effort:** about a day.
6. **Prose discipline when a card is shown.**
   - **What:** a one-to-two-sentence verdict, no duplicate tables, one language, no leaked tags, claim checks on labels and on pick changes.
   - **Why:** most wrong answers in the stress test were prose that contradicted a correct card (section 2).
   - **Effort:** hours to a day.
7. **The canvas for 2–3 doublets.**
   - **What:** a page layout in the canvas's shape, and text of 11 px or more in full screen for well intervals and edge labels.
   - **Why:** multi-doublet designs are where wells, trains and open intervals carry the argument.
   - **Effort:** about a day.

## 5. What works

- **The result card's new structure.** It leads with "Cost of heat and cold 69.8 €/MWh · heat 75.7 · cold 42.1". The four picks sit side by side, and the green strip reads "Spare on the peak day heat +10.4 MW (28 Jan) · One unit out: all 5 cases met (boiler 3 units, chillers 3 units)" with "Each case" to expand it. It is clear, scannable and honest for the base design.
- **The what-if card's search-again line.** "THE PICK CHANGES · Searching again under the change picks C1 · 1D-BO-EC-N1 at 53.4 €/MWh instead of A1 · 1D-HP-EC-N1" is the iteration story judges want. The cards were right in 5 of 5 what-ifs, including the relative "+50% electricity" (278.55 €/MWh).
- **The canvas re-layout.** The page view is legible for one doublet (12.5–16 px), and full screen fits at 0.867. Line styles are distinct (amber dotted electricity, cyan dashed towers), the brine is a neutral brown-grey, and the reservoir band shows each well's open interval with depths.
- **The COMPARE card.** It understood names and roles in 4 of 4 wordings, including "the cheapest one" and Dutch. Its column headers carry name · code plus the pick tags. "Every figure is from the designs' own runs" is the right promise.
- **Honest process signals.** "7 roles took part · 2 on a model, 5 rules or code". The "model unavailable" and "Checked template" tags show when the reasoning model dropped out. One-decimal rounding now agrees between the server and the browser.
