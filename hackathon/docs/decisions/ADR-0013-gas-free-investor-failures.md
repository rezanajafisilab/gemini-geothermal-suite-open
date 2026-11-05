# ADR-0013: Gas-free designs, an investor's view, and what failures cost a year

- Status: **accepted** (1 Nov 2026). Amends [ADR-0011](ADR-0011-picks-failures-plans.md) (picks)
  and [ADR-0012](ADR-0012-library-network-service.md).
- Evidence: the user's choices of 31 Oct (gas-free design, investor case, failure economics;
  produced gas both burnt and sold; a separate investor view); sourced numbers in
  `hackathon/research/numbers_2026-10-31.md`; `unit_test/dioscuri_plant/test_gas_free.py`.

## Context

Every design bought gas: the boiler covered the peaks and, in the reliable plans, the backup. A
council asking for a fossil-free plant had no answer, and the cost of going without gas was
unknown. The plant's cost per MWh (what society pays) also says nothing about what an investor
earns with SDE++, the heat tariff and tax; and a failure answer said what one outage does, not
what failures cost over a year or whether a spare ESP pays.

## Decision

1. **Gas modes** (`Plant.gas`): `buy` (as before), `produced` (no gas bought; a small boiler
   burns only the brine's own gas, sized for it) and `sell` (the brine's gas is cleaned and sold
   to the gas grid; nothing is burnt on site). Venting and flaring are banned except when
   unavoidable (Mijnbouwbesluit art. 38), so the gas is either burnt or sold. Flags `EB` (no gas
   bought) and `GS` (sold): `2D-HP-AB-N1-EB`, `2D-HP-AB-EB-GS`.
2. **Electric boiler** after the gas boiler in the daily dispatch, 99 % efficient; 407 €/kW
   with its grid connection upgrade (PBL SDE++ 2026, Table 13.4), 7.8 €/kW/yr maintenance and
   0.84 €/MWh. Its grid capacity charge depends on how it runs: up to 600 hours a year at its
   peak it takes Liander's 600-hour contract (23.94 €/kW/yr and 2.16 €/kW of each week's peak),
   otherwise the standard 123 €/kW/yr (Liander 2026, TS/MS). A backup electric boiler is cheap
   to connect; one that heats every day is not.
3. **Gas sold** at the wholesale price (TTF 39 €/MWh, PBL Table 4.5) less 0.25 €/Nm³ of raw gas
   to clean, compress and inject it (small biogas upgrading, 0.20–0.30 €/Nm³). Its CO2 is
   then let out and counted; the methane's CO2 when the buyer burns it is shown apart
   (`co2_t.sold_gas_elsewhere`), not in the plant's total.
4. **Gas-free search stage** (`engine._gas_free`, stage 4): for each doublet count, the
   cheapest heat-pump layout is sized again in both modes over every heat-pump share (a
   gas-free plant leans on the heat pump, which gives about three times the heat per MWh of
   electricity), and gets a reliable plan in which the electric boiler, as three equal units,
   is what grows. A sixth pick, **gas-free**: the cheapest such reliable plan.
5. "No boilers" means no gas boiler; the electric boiler can be ruled out on its own
   (`electric_boiler`). With the gas boiler ruled out only the `sell` mode is tried.

6. **What failures cost a year** (`dioscuri_plant.failure_costs`). Each unit has a failure rate,
   a repair time with and without a spare and a repair cost, with sources: an ESP fails 0.5 times
   a year (range 0.2–1.0; Dutch ESPs run 1–2 years, GeoExpro 2026), is back after 7 days with a
   spare and after 120 without (a replacement's lead time), and a swap costs 0.35 M€; the other
   units from DEA 2026 and US Army TM 5-698-5. The expected cost a year is the rate times the
   repair days' share of the unit's all-year outage (the same as averaging over every start day,
   since days do not interact in the model): more gas, power and CO2, heat and cold not
   delivered at 122 €/MWh (the lost sale, a floor; 10,000 €/MWh as a stress line) and repairs.
   It is said apart, not added to the cost of heat (PBL's O&M already provides for the ESP).
   A spare ESP's worth is the expected cost without it minus with it, against its price over
   30 years at the discount rate.

7. **An investor's view** (`dioscuri_plant.investor`, the Economics tab and money answers), apart
   from the plant's cost, which still ranks the designs. Heat and cold are sold at the gas
   reference's own cost of heat and of cold ("niet meer dan anders"; the user can set the
   prices). SDE++ 2026 (PBL advice): the deep-geothermal base-load category by the plant's
   capacity (the brine at its cap flow and the design's own cooling), 6,000 full-load hours, 15
   years, the basisbedrag less 0.70 × TTF (long-term 19.6 €/MWh, floor 13.1) and, from 2028, the
   ETS2 correction (11.4 €/MWh); cooling earns none. Corporate tax 19 % / 25.8 %, 15 years'
   straight-line write-off, losses carried forward; 2 % inflation shrinks the subsidy and the
   write-offs, fixed in euros of their day. NPV, IRR and discounted payback after tax, with and
   without SDE++, and the basisbedrag needed to break even. The investor's choices never
   reprice the designs.

## Consequences

- On the challenge: the best overall (1D-HP-EC-N1) costs 69.8 €/MWh and emits 14,103 t CO2 a
  year; the gas-free pick (2D-HP-AB-N1-EB) 92.7 €/MWh and 7,527 t; selling the brine's gas
  (2D-HP-AB-N1-EB-GS) 101.7 €/MWh and 4,999 t at the plant. Going gas-free costs about
  23 €/MWh more and halves the CO2, about 470 €/t avoided at today's grid (0.20 t/MWh).
- Failures: the recommended design costs about 928 k€ a year on average without a spare ESP
  and 219 k€ with one; the spare (20 k€ a year) pays at any failure rate above once in 71 years.
  It delivers every MWh (N-1); the cheapest design leaves 1,286 MWh a year undelivered, 13.7 M€
  a year at the stress value.
- Investor, recommended design: sales 11.2 M€ a year at the gas reference's prices, SDE++
  3.35 M€ in year 1 ("diepe geothermie <12 MWth", 79.9 €/MWh); NPV after tax +34.8 M€ with
  SDE++ and +16.0 M€ without, IRR 16.1 % and 9.7 %, payback 7 and 13 years. It needs no subsidy
  at these sale prices; at 75 €/MWh for heat it needs a basisbedrag of 44.4 €/MWh.
- A second failure during a repair is not excluded: the no-spare ESP cost is about 16 % high.
- One-doublet gas-free designs cost 107+ €/MWh: their electric boiler runs too many hours
  for the 600-hour contract.
- Daily peaks understate a week's real peak a little, so the 600-hour charge is a little low.
- Not modelled: grid congestion (a 20–30 MW connection may not be available in time), heat
  storage, and an electric boiler's flexible running on cheap hours (PBL's SDE++ e-boiler case).

## Addendum (1 Nov 2026): fixes from the science review

The review (`hackathon/reviews/2026-11-01-challenge/science.md`, E3–E6, E13, E14) found six
model errors. What changed, with the challenge's numbers before → after:

- **Best overall weighs every layout's best sizing (E3).** A layout's reliable plan is also
  built on its sizing that is cheapest with CO2 at 137 €/t, when that is not the cheapest
  today (`engine.shadow_sizings`). Picks are now kept by design, not by code (two plans can
  share a code). Best overall: 1D-HP-EC-N1 with a 2.0 MW heat pump, 69.80 €/MWh, 14,103 t,
  76.37 weighted → the same layout with 3.3 MW, 69.83 €/MWh, 12,967 t, 75.87 weighted.
- **Gas-free with a treatment train per doublet (E4).** Stage 4 also sizes two and three
  doublets with a train each (`engine.gas_free_layouts`): a shared train out no longer forces
  a 30 MW electric boiler. Gas-free pick 2D-HP-AB-N1-EB 92.7 → 2D-HP-AB-ST-N1-EB 86.4 €/MWh
  (electric boiler 30 → 16.6 MW); selling the gas 101.7 → 95.6 €/MWh. Going gas-free now costs
  about 16.6 €/MWh more than the best overall, about 410 €/t avoided (was 23 €/MWh, 470 €/t).
  `firm.reliable` takes back a growth that does not close its gap (a heat pump with no brine)
  and says the case is not covered: no more 195.6 MW heat pumps when the gas boiler is ruled
  out.
- **The 600-hour grid contract in failures (E5).** An outage that pushes the electric boiler
  past 600 hours a year at its peak puts the whole year on the standard tariff. Failure cards
  add that change of the grid charge; the yearly failure costs work it out per start day
  (`failure_costs.grid_change_meur`). The rule is per connection: **the backup electric boiler
  is assumed to have its own grid connection** (the heat pump, pumps and chillers run about
  8,000 hours a year). The shared-train gas-free plan with doublet 1's ESP out 5 Jan–4 May:
  849 h, grid charge 0.74 → 3.73 M€, the event costs 5.04 M€ (card said 2.05). Its failures cost
  3.50 M€ a year without a spare ESP (was 1.65); the spare is worth 3.04 M€ a year (was 1.21).
  No failure rate is published for a treatment train: not counted, and said so.
- **SDE++ on geothermal heat only (E6).** Base-load categories pay for the exchanger's heat and
  the heat the heat pump takes from the brine, not its electricity. In the "with heat pump"
  categories the installation is the heat pump: at most its MW × 6,000 h. The 2.0 MW design:
  eligible 56.7 → 53.3 GWh, SDE++ 3.35 → 3.15 M€ in year 1, NPV 34.8 → 33.7 M€; the heat-pump
  category 6.94 → 1.47 M€ in year 1.
- **Monte Carlo centred on the case (E13).** Each input is drawn triangular, most likely at the
  design's own value; the answer says the case's percentile. Best overall: base 69.8, median
  74.4 → 72.4 €/MWh, the base at P33 (the ranges reach further on the dear side).
- **Service windows around the doublets' stops (E14).** The stops are placed first; no heating
  unit is serviced while a doublet stands.
