# Reliability: N-1 and the risk-based plan

## What N-1 means here

N-1 means: with any one unit out (a doublet, a treatment train, the heat exchanger, the heat
pump, one boiler or chiller unit, the absorption chiller), every day of the year is still met.
Dioscuri's "reliable plans" are sized that way: the backup grows until each single outage on the
design's own year leaves no day short.

## Is N-1 a standard?

N-1 is a common deterministic criterion, not a Dutch rule for heat. It comes from electricity
grids, where operators must keep supplying after the loss of any one element (the n-1 criterion
in the European grid codes). District heating companies use the same idea for their backup:
peak and backup boilers sized so the design load is met with the largest heat source out. No
Dutch law sets it for a heat network; the Heat Act asks for a reliable supply and leaves the
method to the supplier.

## What the risk-based plan adds

N-1 sizes the backup for the largest unit out on the coldest day, however unlikely that is. The
risk-based plan uses the drawn years of unplanned outages (each unit failing at its rate for its
repair time, 1,000 years): it counts the days short of heat a year (the loss-of-load expectation,
LOLE) and the heat not delivered (EENS), and finds the smallest backup that keeps the days short
to one in ten years (LOLE 0.1 day a year: the "one day in ten years" standard many power
systems plan their reserve to; the Netherlands' standard for electricity is 4 hours a year). The
difference between the two sizes is what N-1 buys: how much it costs a year, for how much less
risk.

On the Sensitivity tab, "Size the backup by risk" works this out for a design. With gas boilers
at about 75 k€/MW, N-1 costs little; with an electric boiler and its grid connection it costs
much more, and the risk-based size matters more.

## What the drawn years assume

- **No spare ESP, unless asked.** No design pays for a spare pump, so the years are drawn as the
  design is built: a failed ESP keeps its doublet out 120 days (about four months for a new
  pump). The switch "Spare ESP on the shelf" draws them with a spare instead (the doublet back
  after 7 days), in both plans, and counts its cost in each. Until 4 Nov the risk size was
  always drawn with a spare: on the recommended design (A1) it gave 26.7 MW instead of the
  30 MW N-1 boiler, but without the spare 26.7 MW leaves heat short 1.2 days a year, twelve
  times the target, and the risk size is the N-1 size.
- **The backup that is sized** is the gas boiler when the plant buys gas, and the electric
  boiler when it does not (its gas boiler burns only the brine's gas and backs nothing up).
- **Both plans are priced a year the same way** as the cost of heat prices them: the backup's
  capital over its life at the discount rate (25 years for a gas boiler, 20 for an electric
  one, at 5.2 %), its O&M and, for an electric boiler, its grid charge. "What N-1 buys" is the
  difference in k€ a year, set beside the heat the smaller backup would not deliver (valued at
  the lost sale) and the days short a year.
- **Not drawn:** a treatment train shared by several doublets has no published failure rate,
  so it never fails in the drawn years; the card says so when a design has one. N-1 does cover
  it (it is one of the cases the reliable plan is sized for).
- **The grid contract counts.** An outage that pushes the electric boiler past 600 hours a year
  at its peak puts the whole year on the standard grid charge; each drawn year counts it, as
  the yearly failure costs do.
