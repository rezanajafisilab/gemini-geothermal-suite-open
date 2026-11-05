# Trias Westland, second doublet: project brief

A real Dutch geothermal project, set up in Dioscuri like the challenge district so its design
can be compared with what was built. Figures from public documents are marked with their
source; the rest are assumptions, marked as such.

## The heat network

- Greenhouse growers in the Westland (Zuid-Holland), connected to Trias Westland's heat
  network. The second doublet's expansion connects about 100 ha of greenhouses held by 30
  growers; the network as a whole was to heat about 275 ha (ThinkGeoEnergy, 2020 and 2021).
- Daily heat demand: not published. Assumed: 1.0 GJ per m2 of greenhouse a year, about
  278 GWh for 100 ha; 40 % of each day's heat a constant base (greenhouses also need heat at
  night and to dehumidify in summer), 60 % following the shape of the challenge district's 2027
  heat profile. No cooling.
- Network temperatures: not published. Assumed: supply 75 °C, return 26 °C (the brine is
  injected at 31 °C, and leaves the heat exchanger 5 K warmer than the network's return).

## The reservoir (PanTerra Geoconsultants, Geological report TW OK II, G1363b, 2020, on NLOG)

- Delft Sandstone (Lower Cretaceous). At the planned producer NLW-GT-03: top 2,306 m and base
  2,366 m TVDss, midpoint about 2,336 m.
- Gross thickness 58 to 66 m, net-to-gross 0.87 to 0.96: about 59 m net.
- Permeability 450 / 650 / 1,000 mD (P90 / P50 / P10); 650 mD used.
- Temperature: T = 10 + 0.033 × depth (°C, m); the first doublet's well NLW-GT-01 produced
  87 °C from about 2,350 m.
- Salinity about 140,000 ppm NaCl: brine about 1,087 kg/m3 and 3,575 J/(kg K) at 60 °C
  (Sharqawy, Lienhard & Zubair 2010).
- The wells about 1,800 m apart at mid-reservoir (p. 40), laid parallel to the main faults.
- Injection at 31 °C; at most 525 m3/h (the tubing); pumps set to 110 bar in DoubletCalc.
- DoubletCalc 1.4.3 (the report): 25 / 32 / 41 MW (P90 / P50 / P10), COP 13 / 14 / 15.

## Caps used in Dioscuri

- 1 to 3 doublets; 50 to 525 m3/h per doublet; the brine cooled from about 87 °C to 31 °C, so
  by at most 56 K; at most 330 days a year per doublet (assumed, as in the challenge).
- Gas in the brine: not published for this well; the challenge's 0.8 Nm3/m3 (80 % CH4) is
  assumed.
