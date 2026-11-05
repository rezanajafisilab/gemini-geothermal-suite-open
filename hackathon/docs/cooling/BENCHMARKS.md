# Report regression fixture: report_screen_v1

This deliberately uncoupled constant-performance fixture checks arithmetic/accounting.
It is NOT the production default, a Ramey validation, a real weather/free-hours prediction
or a compliant complete geothermal plant. Do not force a coupled model to match it.

## Fixture definition

Use original cooling CSV, every daily mean for 24 h, 10 MW electric capacity in every option.
For the hybrid, Qa=min(cooling,4 MW) on every cooling day and Qe=cooling-Qa; assume sufficient
valid driving heat for this test only. Generator duty G=Qa/0.7; absorber internal power
Pa=0.01*Qa. Electric compressor COP is 6 water / 4 air, excluding external fans/pumps.

For water/hybrid: Qr=Qe+Qe/6+Qa+G+Pa. Tower fan=0.0126*Qr; condenser pump=0.005*Qr;
hot pump=0.005*G; chilled pump=0.01*cooling. For air: Qr=cooling+cooling/4;
fan=0.02*Qr and chilled pump=0.01*cooling. Sum all listed electricity terms.
No extra well power, standby, external-pump heat feedback, thermal losses or refrigerant leak.

Water makeup per day: 0.8*Qr_MW*24*3600/2.45/1000 *5/4 m3. No drift/leaks.
Capex: CH1 at 10 MW, ACH1 as four 1 MW modules if hybrid, CT1 at design rejection.
No tower for air. Air capex=5 million USD-2015 budget. Backup/tower investment is retained
through outages and free-mode cases. All chillers 25 years/5% maintenance; towers 20/10%.
Real discount 5%, electricity 150 USD/MWh, source heat 5 USD/MWh, effective water/treatment
1.5 USD/m3, all constant 2015 USD. No additional unpriced balance-of-plant investment.
Grid CO2 factor=0.12943; CO2e=0.13096 t/MWh. Source-heat/gas emissions excluded here.

## Expected annual results

| Measure | Water | Air | Absorption + water backup |
| --- | ---: | ---: | ---: |
| Cooling MWh | 23742.528000000 | 23742.528000000 | 23742.528000000 |
| Electricity MWh | 4682.026521600 | 6766.620480000 | 2711.255954743 |
| Generator heat MWh | 0.000000000 | 0.000000000 | 22144.285714286 |
| Peak core rejection MW | 11.666666667 | 12.500000000 | 16.754285714 |
| Makeup m3 | 40701.476571429 | 0.000000000 | 69671.625376093 |
| Capex USD-2015 | 4806290.633333333 | 5000000.000000000 | 6646201.300000000 |
| Annual fixed USD-2015/year | 592555.728833508 | 604762.286496148 | 819953.939244068 |
| Annual cost USD-2015/year | 1355911.921930650 | 1619755.358496148 | 1441871.199091065 |
| Partial LCOC USD-2015/MWh | 57.108995383 | 68.221688882 | 60.729472409 |
| Grid CO2 t/year | 605.994692691 | 875.803688726 | 350.917858222 |
| Grid CO2e t/year | 613.158193269 | 886.156618061 | 355.066079833 |

Use floating tolerances (e.g. relative 1e-9/absolute 1e-6 for these independent fixture sums),
not exact binary equality. Check actual unrounded numbers before formatted display.

## Hand-calculation checks

| Case | Expected result |
| --- | --- |
| 10 MW water cooling, 25->20 C; rho=1,000, cp=4,180 | 1,722.488038278 m3/h |
| 1 MW electric cooling, compressor COP 5 | P=0.200 MW; core rejection=1.200 MW |
| 1 MW absorption, COP_th=0.7, internal=0.01 MW | Generator=1.428571429 MW; rejection=2.438571429 MW |
| Pump 100 m3/h, 1 bar, eta=0.70 | 3.968253968 kW |
| Brine 300 m3/h, rho=1,030, cp=3,950, 40 K | 13.561666667 MW |
| 4 MW absorption, COP=0.7, brine usable drop=10 K | 505.626854404 m3/h total before hydraulic checks |
| 3 doublets at 300 each, same 10 K and COP | 7.119875 MW cooling, before temperature/map limits |
| 100,000 m3 brine, full potential gas liberation and complete atmospheric oxidation/release | 157.08 t direct CO2 (rounded) |

Additional check: a counterflow HX with water rho=1,000/cp=4,180, both flows 0.01 m3/s,
UA=20,000 W/K and inlets 16/6 C must cool the hot side and warm the cold side. Swap port
ordering and require the same physical transfer mapped back correctly. Both energy balance
AND heat-flow direction must pass.

## Scenario regressions

- Zero absorber capacity returns the water-cooled result with the same design/inventory.
- Zero free share returns mechanical mode. Zero generator allocation triggers electric
  backup; no nominal absorber duty survives a closed source valve.
- The hypothetical 20% free-energy share fixture adds a dedicated pump at 0.02*Qfree,
  includes its heat in Qr, retains full mechanical/tower capex and excludes extra HX capex.
  Electricity=3,973.321557811 MWh; savings budget=107,840.771684728 USD/year before extra
  free-mode capital/maintenance. This is not a weather model.
- Hybrid LCOC at heat prices 0/5/10/20 is approximately
  56.066050360 / 60.729472409 / 65.392894458 / 74.719738555.
- Grid-plus-heat CO2e with added heat factors 0/10/20 kg/MWh heat is approximately
  355.066079833 / 576.508936976 / 797.951794119 t/year. No explicit source emissions added.
- Report break-even heat cost approximately 1.118218566 USD/MWh; heat-emissions burden
  approximately 11.655020928 kgCO2e/MWh. These thresholds inherit every fixture assumption.

Do not tune equipment curves, thermal losses or well flows to reproduce these policy and
arithmetic assumptions. Production validation uses independent physical operating points.
