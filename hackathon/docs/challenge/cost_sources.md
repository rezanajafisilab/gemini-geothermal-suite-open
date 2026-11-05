# Sourced techno-economic parameters: geothermal district heating and cooling (NL / north-west Europe)

Compiled 30 Oct 2026 for the Dioscuri design tool (SPE GeoHackathon 2026); the defaults in `src/dioscuri_plant/economics.py` (`Prices`, `SOURCES`) come from this table. Every number below was read from the cited document (PDF or Excel downloaded and checked, or the official API queried). Numbers marked **derived** are my arithmetic on sourced inputs; the method is given. Short cites [S#] point to section (b).

Currency and price-year conventions used for conversions (only where needed):
- DEA 2020 EUR to 2025 EUR: x1.168, the DEA's own factor (DEA tech brief June 2026, footnote 1). The euro-area HICP factor would be x1.225 (Eurostat prc_hicp_aind: 105.06 to 128.75).
- USD to EUR: Eurostat ert_bil_eur_a annual averages (2017: 1.1297; 2022: 1.0530; 2024: 1.0824 USD/EUR), then euro-area HICP to 2025 (2017 to 2025: x1.265; 2022 to 2025: x1.102).
- Towler & Sinnott (US Gulf Coast, 2010 basis): CEPCI 2010 = 550.8 to 2024 = 800.0 (x1.452, Univ. of Manchester CEPCI table as bundled in OpenPyTEA), then 2024 USD to EUR at 1.0824.
- 1 refrigeration ton = 3.517 kW. Gas GCV to NCV: x1.11 (ratio of PBL's TTF prices in HHV and LHV, 0.0390/0.0351, [S3] Table 4.5).

---

## (a) Summary table

### 1. Geothermal wells and surface plant

| # | Parameter | Value (suggested default) | Unit | Plausible range | Source |
|---|---|---|---|---|---|
| 1.1 | Well cost vs depth, ThermoGIS v3.x (current, calibrated to PBL SDE++) | Well CAPEX = 1.96 x (790,000 + 555·L + 0.05·L²), with L = along-hole depth (m) = 1.1·√(TVD² + (spacing/2)²) | EUR | see 1.2 | [S4] Economic model page; Technical model page (L definition) |
| 1.2 | Drilling + completion cost for one well at 2,500 m TVD (L ≈ 2,750–2,870 m) | **≈ 5.0** | M EUR per well | 2.7–5.9 (10–11 M EUR per doublet is the central value) | **derived** from [S4] and [S5]: v3 formula 5.3–5.5 if the 1.96 factor is per well (2.7 if it covers both wells, see caveat C1); ThermoGIS v2 config 250,000 + 700·L + 0.2·L², x1.3 per well → 4.8–5.1; older ThermoGIS template 375,000 + 1,050·L + 0.3·L² → 5.5–5.9 |
| 1.3 | Same, per metre | ≈ 1,900 | EUR/m along-hole, per well | 1,700–2,050 | **derived** from 1.2 |
| 1.4 | Other (non-well) capex: surface plant, HX, pumps, degassing, civils, connections | 3.5 M EUR + 882 EUR/kW_th | EUR | v2 config: 3.0 M EUR + 300 EUR/kW + 15 % contingency | [S4] Economic model page and parameter table; [S5] TG basecase table |
| 1.5 | Total installed capex, deep geothermal baseload NL (incl. wells, ESP, gas/oil separation, HX, civils, insurance, interest during construction) | **1,340** (≥ 20 MW_th, ref. 27.4 MW) | EUR/kW_th | 1,340 (≥ 20 MW) / 1,719 (12–20 MW) / 2,463 (< 12 MW) | [S3] Tables 11.7a–c, p.136 |
| 1.6 | Same, geothermal plus heat pump for a 90–120 °C network (≥ 12 MW_th) | 2,587 | EUR/kW_th | 2,587–3,045 | [S3] Tables 11.8a–b, p.138 |
| 1.7 | Cross-check, Denmark: geothermal DH plant incl. heat pump, 2,000 m, 80/40 °C (2025 EUR) | 1.9 (21 MW plant) / 1.75 (62 MW, 3+3 wells) | M EUR/MW_th | 1.5–2.1 | [S1] data sheets 45.1.b and 45.3 |
| 1.8 | Learning with number of wells | −15 % capex each time the number of wells doubles | – | – | [S1] ch.45 p.232 |
| 1.9 | ESP purchase and installation (250–500 kW_e units) | 180–300 (2016 prices) | k EUR per ESP | – | [S6] §9, Table 5, p.22 |
| 1.10 | ESP O&M including replacement provision | 63.5–95 (assumes a 4-year pump life) | k EUR/yr per ESP | – | [S6] Table 6, p.22 |
| 1.11 | ESP life: design target vs NL experience | target 4–5 yr; NL average run time 1–2 yr | yr | 9 days to > 5 yr | [S6] pp.16, 24; [S7]; DEA assumes replacement about every 5 yr ([S1] 45.1.b note E) |
| 1.12 | ESP pump efficiency and setting depth (ThermoGIS) | 60 % at 300 m | – | 35–55 % observed in NL | [S4] parameter table; [S6] §9 |
| 1.13 | Injection pump capex | **not found as a separate number**; PBL lists ESP and injection pump inside total capex | – | – | [S3] Tables 11.1 and 11.2 |
| 1.14 | Fixed O&M, geothermal (NL) | **121** (≥ 20 MW_th) | EUR/kW_th/yr | 117–121 baseload; ThermoGIS 81 + 0.62 EUR/MWh; DEA 55,000–60,000 EUR/MW/yr | [S3] Tables 11.7a–c; [S4]; [S1] 45.1.b/45.3 |
| 1.15 | Variable O&M, geothermal (NL, mostly ESP electricity) | 5.8 | EUR/MWh_th | 5.3–6.3 | [S3] Tables 11.7a–c |
| 1.16 | Pump electricity, geothermal loop | 2–10 % of extracted heat | – | PBL system SPF 19.9–22.8 (about 4.4–5.0 % of heat) | [S1] ch.45 p.229; [S3] Tables 11.7a–c |
| 1.17 | Doublet lifetime | 30 | yr | DEA 25 (25–30) | [S3] p.126; [S4]; [S1] 45.1.b |
| 1.18 | Abandonment (ABEX) | ≈ 7.5 % of investment (DEA); PBL assumes residual value and abandonment cancel | – | – | [S1] ch.45 p.239; [S3] Table 11.2 p.129 |

### 2. Large / high-temperature heat pump (~100 °C supply)

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 2.1 | Capex, district-heating heat pump (2025 EUR, incl. building and integration) | **1.2** | M EUR/MW_th | 0.95–1.5: 0.95 (10 MW waste heat, 70/35 °C), 1.19 (20 MW seawater, 80/40 °C; stand-alone plants near the upper bound); +5 % for 40–80 °C DH; HTHP ≤ 125 °C 0.9–1.5 (row 2.2) | [S1] data sheets 40 (waste heat 10 MW, seawater 20 MW), notes O; [S2] 2.a |
| 2.2 | Capex, industrial HTHP up to 125 °C (2025 EUR, 2 MW unit) | 1.2 | M EUR/MW_th | 0.9–1.5; +0.15 M EUR/MW for lift > 75 K | [S2] sheet 2.a |
| 2.3 | Capex, NL industrial closed heat pump (1.4 MW, 25→70 °C) | 1,476 (826 equipment + 649 other) | EUR/kW_th | – | [S3] §13.5.3 p.174, Table 13.12 p.176 |
| 2.4 | Capex, HTHP equipment only (34 technologies) | – | EUR/kW_th | 200–1,500 | [S8] Table 2-3 p.65 |
| 2.5 | Fixed O&M | 2,100–4,300 | EUR/MW_th/yr | PBL: 4 % of equipment capex per year (33 EUR/kW/yr) | [S1] sheets 40; [S2] 2.a (2,494); [S3] §13.5.4 |
| 2.6 | Variable O&M (excl. electricity) | 1.3–3.6 | EUR/MWh_th | – | [S1] sheets 40; [S2] 2.a |
| 2.7 | Technical lifetime | 25 (DH) / 20 (HTHP) | yr | 15–40; Annex 58 average 23.3 yr for > 5 MW | [S1]; [S2]; [S8] p.64 |
| 2.8 | Second-law (Lorenz) efficiency, real COP / ideal COP | **0.48–0.50** (DEA, market standard 2025) | – | 0.40–0.60 typical (DEA); 0.11–0.69 (Annex 58 dataset); ThermoGIS 0.60 (0.50–0.70) | [S1] ch.40 p.199–200, Table 1; [S8] Fig. 2-36 p.64; [S4] Heat pumps page |
| 2.9 | COP for a 65 K lift (≤ 125 °C HTHP) | 2.75 | – | 2.25–4.0; 4.45 at 40 K; 2.4 at 80 K | [S2] 2.a |
| 2.10 | COP for 45 °C source → 100 °C | 3.1–3.4 (Carnot with η 0.45–0.50, no glide); 4.6–4.9 (Lorenz, sink 60→100 °C, source 50/45→40 °C, η 0.48) | – | 2.8–4.9 | **derived** with the [S1] Eq. 1–3 method |
| 2.11 | NL reference SPF, heat pump boosting geothermal to a 90–120 °C network | 2.9 (system SPF incl. geothermal 3.5) | – | – | [S3] Tables 11.8a–b p.138 (Carnot method, p.128) |

### 3. Natural-gas boiler (district heating)

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 3.1 | Capex (2–3 MW reference) | 0.064 (2020 EUR) ≈ **0.075** (2025 EUR) | M EUR/MW_th | 0.043–0.27 (2020 EUR, 0.5–10 MW) | [S1] sheet 44; 2025 EUR derived |
| 3.2 | Capex, industrial hot-water boiler (2025 EUR) | ≈ 0.063 (0.09 for a steam boiler, −30 % for hot water; +10 % with flue-gas condenser) | M EUR/MW_th | – | [S2] 6.1 |
| 3.3 | Fixed O&M | 2,074 (2020 EUR) ≈ 2,400 (2025 EUR) | EUR/MW/yr | 1,063–2,658 (2020 EUR) | [S1] 44 |
| 3.4 | Variable O&M | 1.17 (2020 EUR) | EUR/MWh_th | 0.64–2.23 | [S1] 44 |
| 3.5 | Efficiency (LHV) | 103 % annual / 105 % nameplate with condensing economiser; 92–95 % without | – | 93–105 % | [S1] 44 notes B; [S2] 6.1 (94 % + 6 points with condenser) |
| 3.6 | Lifetime | 25 | yr | ≥ 25 | [S1] 44 |

### 4. Gas-engine CHP (1–10 MW_e)

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 4.1 | Capex | 1.01 (2020 EUR) ≈ **1.18** (2025 EUR) | M EUR/MW_e | 0.96–1.17 (2020 EUR) | [S1] sheet 06 |
| 4.2 | Electrical efficiency (LHV) | 47 % nameplate / 45 % annual average | – | 38–48 % | [S1] 06; ch.06 p.57 "45–48 %" |
| 4.3 | Thermal efficiency | ≈ 49–50 % (derived: η_el / Cb, Cb = 0.95 at 50/100 °C); total 96–98 % with condensing cooler | – | – | [S1] 06; ch.06 p.57 |
| 4.4 | Fixed O&M | 10,370 (2020 EUR) | EUR/MW_e/yr | 7,444–21,270 | [S1] 06 |
| 4.5 | Variable O&M | 5.74 (2020 EUR) | EUR/MWh_e | 4.25–12.76 | [S1] 06 (at 4,000 h/yr) |
| 4.6 | Lifetime | 25 | yr | – | [S1] 06 |
| 4.7 | Methane slip | 315 | g CH4/GJ fuel | 300–400 | [S1] 06 |

### 5. Absorption chiller (single-effect LiBr, hot-water driven)

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 5.1 | Installed capex, about 1.5 MW (440 RT) | $2,300/RT (2017) ≈ **730** (2025 EUR) | EUR/kW_cold | 570 (1,320 RT, steam) – 1,900 (50 RT); equipment only ≈ 300 | [S9] Table 3 p.4; EUR derived |
| 5.2 | TNO modelling assumption (geothermal-driven chiller, incl. HX) | 0.5 M EUR + 1,100 EUR/kW; OPEX 50 EUR/kW/yr + 10 k EUR/yr | – | – | [S5] chiller page (cites DOE 2017) |
| 5.3 | COP at standard conditions (12.2/6.7 °C chilled, 88→83 °C hot water) | **0.70** | – | 0.70–0.79 | [S9] Table 2 p.3; [S10] spec table (35 kW cold / 50.2 kW heat) |
| 5.4 | COP at high chilled-water temperature | 0.75 (EAW SE30, chilled 17/11 °C, hot 90/80, cooling 30/35) | – | 0.71–0.75 (15–18 °C chilled); NH3/H2O at 18/15 °C with 75/68 °C drive: 0.72 | [S11] table, PDF p.4 |
| 5.5 | Driving temperature | 88 °C nominal inlet; **75–95 °C** allowed | °C | 70 °C min (TNO); 93–116 °C (200–240 °F) per DOE for single stage | [S10]; [S5]; [S9] Table 1 |
| 5.6 | O&M | 0.2 ¢/RT·h ≈ 0.6 EUR/MWh_cold | – | 0.1–0.6 ¢/RT·h | [S9] Table 3 |
| 5.7 | Heat rejection | (1 + 1/COP) x cooling ≈ 2.4 x cooling (larger cooling tower than an electric chiller) | – | – | [S9] p.2 (qualitative); factor derived |

### 6. Electric water-cooled chiller and cooling tower

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 6.1 | Capex, centrifugal chiller 400–600 RT, **excluding cooling tower** | $540–590/RT (2022) ≈ **160–176** (2025 EUR) | EUR/kW_cold | high efficiency: $740–760/RT ≈ 226 | [S12] App. A p.125; EUR derived |
| 6.2 | COP full load at AHRI (6.7 °C leaving chilled water, 29.4 °C entering condenser water) | 6.8 typical (6.3 = ASHRAE 90.1 minimum) | – | 6.3–7.8; IPLV 11.3 | [S12] p.125 |
| 6.3 | COP gain with chilled-water temperature | +3.5 % per K; +37–40 % at 17 °C vs AHRI | – | 1–3.5 %/K in other studies | [S13] abstract |
| 6.4 | COP at 20 °C supply / 25 °C return | **≈ 9.5–10.5** (chiller only) | – | 8.6–12 | **derived**: [S12] COP x [S13] gain, 3 K extrapolated past the measured range |
| 6.5 | Cooling tower + condenser pumps capex | 170,000 + 1,500·Q^0.9 USD (2010, Q in L/s, 100–10,000 L/s) ≈ **75 EUR/kW_cold** for 10 MW | EUR/kW_cold | – | [S15]; EUR derived |
| 6.6 | Cooling tower fan electricity | 1.25 % of the heat rejected ≈ 1.4 % of cooling load ≈ 10–14 % of chiller electricity (at the ASHRAE 90.1 minimum of 40.2 gpm/hp, 5.6 K range) | – | – | [S14]; derived |
| 6.8 | Condenser-water pump electricity (added 4 Nov; the fan figure above has no pumps) | 0.5 % of the heat rejected, its heat into the towers' water | – | – | the cooling component model's `TowerSettings.pump_ratio` (Dioscuri's screening value, not a published figure) |
| 6.7 | Lifetime / maintenance | 25 yr / $30–40 per RT·yr ≈ 9–12 EUR/kW/yr | – | – | [S12] p.125 |

### 7. Energy and carbon prices (Netherlands)

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 7.1 | Electricity, non-household, band ID (2–20 GWh/yr), excl. VAT and recoverable taxes, 2025 mean (S1, S2) | **185.7** | EUR/MWh | 2024: 195.8; 2026-S1: 182.4; excl. all taxes 146.8 | [S16] |
| 7.2 | Same, band IE (20–70 GWh/yr) | **130.7** | EUR/MWh | 2024: 143.9; 2026-S1: 139.1; excl. all taxes 117.5 | [S16] |
| 7.3 | EU-27 comparison, bands ID / IE, 2025 | 161.8 / 136.2 | EUR/MWh | – | [S16] |
| 7.4 | Natural gas, non-household, band I3 (10,000–100,000 GJ), excl. VAT, 2025 mean | **76.2 per MWh GCV** (≈ 84.6 per MWh LHV) | EUR/MWh | 2024: 68.3; 2026-S1: 83.9 (GCV) | [S17]; LHV derived |
| 7.5 | Same, band I4 (100,000–1,000,000 GJ) | **62.5 per MWh GCV** (≈ 69.4 per MWh LHV) | EUR/MWh | 2024: 57.8; 2026-S1: 66.5; excl. all taxes 39.0 | [S17] |
| 7.6 | NL wholesale reference values (PBL): EPEX average Sep 2024–Aug 2025; long-term 2026–2040 (KEV 2025) | 90.6; 74.3 | EUR/MWh_e | – | [S3] Table 4.2 p.46 |
| 7.7 | TTF gas (PBL): Sep 2024–Aug 2025; long-term | 39.0; 28.0 | EUR/MWh LHV | HHV: 35.1; 25.2 | [S3] Table 4.5 p.48 |
| 7.8 | EU ETS (EUA) annual average | **2024: 64.8; 2025: 73.9** (auctions) | EUR/t CO2 | Sep 2024–Aug 2025: 69.1; PBL long-term (2026–2040): 137.0 | [S18] PDF p.9; [S19]; [S3] §4.10 p.50 |

### 8. CO2 emission factors

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 8.1 | Natural gas, IPCC default (energy industries, NCV basis) | 56,100 (= 0.2020 t/MWh_LHV) | kg CO2/TJ | 54,300–58,300; CH4 1, N2O 0.1 kg/TJ | [S20] Table 2.2 p.2.16 |
| 8.2 | Natural gas, NL national value (RVO list 2025, used by PBL) | **56.2** (= 0.2023 t/MWh_LHV) | kg CO2/GJ | – | [S3] §5.1.1 p.56 |
| 8.3 | Heat from a gas boiler (PBL, 90 % efficient) | 0.225 | t CO2/MWh_th | 0.213 at 95 % (derived) | [S3] §5.1.1 p.56 |
| 8.4 | NL grid electricity, average of all production (CBS integral method) | **0.20 (2024)** | t CO2/MWh_e | 2023: 0.22; 2022: 0.27 | [S21] Table 1 |
| 8.5 | NL grid, fossil reference park (marginal-type) | 0.45 (2024) | t CO2/MWh_e | 2023: 0.47 | [S21] Table 2 |
| 8.6 | NL forward-looking marginal factor (PBL SDE++, average of 2037 hours) | 0.13 | t CO2/MWh_e | – | [S3] §5.1.2 p.56 |
| 8.7 | EU-27 grid average | 0.224 (2023, CO2 only, IEA data) | t CO2/MWh_e | about 0.20 for 2024 (derived: EEA reports 2024 was 11 % below 2023) | [S22]; [S23] |

### 9. Financial conventions and benchmark cost of geothermal heat (NL)

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 9.1 | WACC, geothermal (after tax) | **7.3 % nominal / 5.2 % real** | – | heat pumps and e-boilers: 6.0 / 3.9 % | [S3] Table 6.3 p.66 |
| 9.2 | Underlying assumptions | debt 70 % at 5.75 %; equity 30 % at 14.5 %; corporate tax 25.8 %; inflation 2.0 % | – | – | [S3] Tables 6.1–6.2 p.58, 61; §6.5 p.64 |
| 9.3 | Economic lifetime / subsidy period / tax depreciation | 30 / 15 / 15 | yr | heat pumps: 12 / 12 / 12 | [S3] §6.6 p.65; p.126 |
| 9.4 | ThermoGIS financial settings | 80 % debt at 5 %; 14.5 % return on equity; 1.5 % inflation; 25 % tax; 30 yr life; 6,000 full-load hours; 15-yr payback | – | – | [S4] parameter table and Economic model page |
| 9.5 | PBL base amount, deep geothermal baseload (6,000 h), ≥ 20 MW_th (benchmark cost of heat) | **62.7** | EUR/MWh_th | 69.6 (12–20 MW); 79.9 (< 12 MW) | [S3] Table 11.13 p.143 |
| 9.6 | Same, other NL categories | mid-load (5,000 h): 99.7; non-baseload (3,500 h): 164.7–185.0; 90–120 °C network with heat pump: 132.5–147.6 (baseload), 207.5 (non-baseload) | EUR/MWh_th | – | [S3] Table 11.13 p.143 |
| 9.7 | DEA cost-of-heat convention | 3.5 % interest rate | – | – | [S1] tech brief footnote 1 |

### 10. Brine heat capacity

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 10.1 | Correlation (Jamieson et al. 1969, recommended by Sharqawy et al.) | c_p = A + B·T + C·T² + D·T³, with T in K and S in g/kg; A = 5.328 − 9.76e-2·S + 4.04e-4·S²; B = −6.913e-3 + 7.351e-4·S − 3.15e-6·S²; C = 9.6e-6 − 1.927e-6·S + 8.23e-9·S²; D = 2.5e-9 + 1.666e-9·S − 7.125e-12·S² | kJ/(kg·K) | valid 273–453 K, 0–180 g/kg, ±0.28 % | [S24] Table 3, Eq. (9), p.360 |
| 10.2 | Salinity that gives 1,030 kg/m³ (Sharqawy Eq. 8, 0.1 MPa) | ≈ 40–42 g/kg if the density is at 15–20 °C | g/kg | ≈ 70 g/kg if 1,030 is the in-situ density at 87 °C and 250 bar | **derived** from [S24] Eq. (8), p.357 |
| 10.3 | c_p of the brine at 60–87 °C | **3.99** (S ≈ 41 g/kg) | kJ/(kg·K) | 3.86–4.01 (S 70–40 g/kg); 60 °C: 3.984, 75 °C: 3.992, 87 °C: 4.000 at S = 41.6 g/kg | **derived** from [S24] Eq. (9) |
| 10.4 | Volumetric heat capacity ρ·c_p at 75 °C | ≈ 4.01 | MJ/(m³·K) | – | **derived** |

### 11. Plate heat exchanger (brine/water)

| # | Parameter | Value | Unit | Range | Source |
|---|---|---|---|---|---|
| 11.1 | Purchased cost correlation, plate & frame, 304 stainless steel | C = 1,600 + 210·A^0.95 USD (US Gulf Coast 2010; A = 1–500 m²) | USD | – | [S15] |
| 11.2 | Same, escalated | 210–245 | EUR/m² (2024) | for 500–100 m² units | **derived** (CEPCI, FX) |
| 11.3 | Per unit of UA | ≈ 40–70 | EUR per kW/K (purchased) | if U = 3,000–5,000 W/m²K (U is my assumption, not sourced) | **derived** |
| 11.4 | Example: 30 MW brine HX at an LMTD of 5 K | ≈ 10 | EUR/kW_th (purchased, 3 x 500 m²) | – | **derived**; titanium or super-duplex plates for brine will cost more (no sourced factor) |

### 12. Cooling-tower water (added 4 Nov)

The towers evaporate water with the heat they reject (free cooling's, the chillers' cold and electricity, the absorption chiller's cold and driving heat): 80 % of the heat as latent heat at 2.45 MJ/kg, so 1.18 m³ per MWh rejected; the blow-down keeps 5 cycles of concentration (a quarter of the evaporation more). These are the cooling component model's `WaterSettings`. On the challenge pick with free cooling, about 36,000 m³ of make-up water a year.

| # | Parameter | Value (suggested default) | Unit | Plausible range | Source |
|---|---|---|---|---|---|
| 12.1 | Drinking water, business and household tariff, WML (Limburg) 2026 | 1.1749 + provincial tax 0.0270 = 1.2019 (excl. VAT) | EUR/m³ | other companies 2026: Vitens 1.23 (consumer, 1.34 incl. VAT); Vitens business 2024: 0.95 | [S26] p.5; [S27] |
| 12.2 | Tap-water tax (belasting op leidingwater), 2026 | 0.4373 (excl. VAT), on the first 50,000 m³ a connection; from 2027 on all of it (proposed 0.55) | EUR/m³ | – | [S26] p.5; [S28] |
| 12.3 | **Make-up water, all in** (`Prices.water_supply_eur_per_m3`) | **1.64** (12.1 + 12.2) | EUR/m³ | 1.2–1.8; surface or industrial process water is cheaper (not sourced) | **derived** from [S26] |
| 12.4 | **Blow-down discharge** (`Prices.blowdown_disposal_eur_per_m3`) | **0.40, assumed** | EUR/m³ | 0.1–1.0; 0 when a permit lets it go to surface water | **assumption**: a municipal sewer charge for a large discharger plus the water board's treatment levy on lightly polluted water; no tariff for cooling-tower blow-down was found |

---

## (b) References: full citations and where each number appears

**[S1] Danish Energy Agency and Energinet. *Technology Data for Generation of Electricity and District Heating*.** Catalogue PDF updated August 2026 (280 pp.); data sheet workbook version 0019 updated August 2026; "Technology Brief: Update of large heat pumps, geothermal, el and gas boilers" (June 2026). Landing page: https://ens.dk/en/analyses-and-statistics/technology-data-generation-electricity-and-district-heating. PDF: https://ens.dk/media/8614/download. Excel: https://ens.dk/media/8615/download. Brief: https://ens.dk/media/8616/download.
- Price base (Intro sheet): sheets 40x, 41x, 45x and 47x are in 2025 EUR; all other sheets, including 06 and 44, are in 2020 EUR. Brief footnote 1: interest rate 3.5 %, inflation 2020→2025 = 16.8 %.
- Sheet "45.1.b Geothermal DH, 2000m": 21 MW_h; total efficiency 4 (3.5–4.5); investment 1.9 M EUR/MW (2030 range 1.7–2.1); variable O&M 3.07 EUR/MWh; fixed O&M 60,000 EUR/MW/yr (50,000–65,000); lifetime 25; 1 production + 1 injection well; geothermal 65/10 °C. Note E: "Replacement of submersible pump(s), approx. once every five years". Note C: excludes project development, seismic and geological model.
- Sheet "45.3 Geothermal DH, lar scale": 62 MW; 1.75 M EUR/MW (1.5–1.95); fixed O&M 55,000 EUR/MW/yr; 3+3 wells.
- Catalogue ch.45: pump electricity "normally 2-10 % of the heat extracted" (p.229); −15 % capex per doubling of wells (p.232); 2 injection wells per producer and brine cooling limited to 35 K (pp.235–236); ABEX ≈ 7.5 % of investment (p.239).
- Ch.40 heat pumps: Lorenz COP method (Eq. 1–3) and "Lorenz efficiency, is typically around 40-60%" (p.199); Table 1, market-standard Lorenz efficiencies 43–50 % in 2025 (p.200). Sheets "40 Comp. hp, waste heat 10 MW" (0.95 M EUR/MW, of which heat pump 0.36, building 0.12, other 0.47; fixed O&M 2,127 EUR/MW/yr; variable O&M 3.07 EUR/MWh; lifetime 25; note O: +5 % at 40–80 °C DH) and "40 Comp. hp, seawater 20 MW" (1.19 M EUR/MW; COP 3.0 nameplate at 80/40 °C; fixed O&M 4,253 EUR/MW/yr; variable O&M 1.265 EUR/MWh).
- Sheet "44 Natural Gas DH Only" (2020 EUR column): 0.0638 M EUR/MW (0.0425–0.266); fixed O&M 2,074 EUR/MW/yr; variable O&M 1.17 EUR/MWh; efficiency 1.03 annual / 1.05 nameplate; note B: with condensing economiser, "without economizer ... up to some 92-95 %, LHV"; note J: averages are for 2–3 MW boilers; lifetime 25.
- Sheet "06 Gas engines, natural gas" (2020 EUR): 1.01 M EUR/MW_e (0.957–1.17); electrical efficiency 0.47 nameplate / 0.45 annual; Cb (50 °C/100 °C) 0.95; fixed O&M 10,370 EUR/MW_e/yr; variable O&M 5.742 EUR/MWh_e (at 4,000 h); CH4 315 g/GJ; lifetime 25. Catalogue ch.06 p.57: electrical efficiency 45–48 %, total 96–98 % with a condensing cooler.

**[S2] Danish Energy Agency. *Technology Data for Industrial Process Heat*, data sheet (updated 5 Jan 2026; "All cost data is in 2025€").** https://ens.dk/media/7758/download (page: https://ens.dk/en/analyses-and-statistics/technology-data-industrial-process-heat).
- Sheet "2.a High temp. hp Up to 125C": 1.2 M EUR/MW (0.9–1.5); unit 2 MW (0.3–25); COP 2.75 at 65 K lift (2.25–4.0), 4.45 at 40 K, 2.4 at 80 K, 2.05 at 100 K; fixed O&M 2,494 EUR/MW/yr; variable O&M 3.6 EUR/MWh; lifetime 20 (15–30); +0.15 M EUR/MW for lift above 75 K.
- Sheet "6.1 Boiler, gas and oil": 0.09 M EUR/MW (5 MW steam boiler with economiser); hot-water boiler −30 % capex and +1 point efficiency; flue-gas condenser +10 % capex and +6 points; efficiency 94 %; fixed O&M 2,000 EUR/MW/yr; variable O&M 1.23 EUR/MWh; lifetime 25.

**[S3] Lensink, S. and E. Eggink (eds.) (2026). *Advies basisbedragen SDE++ 2026*. PBL Netherlands Environmental Assessment Agency with TNO and DNV, publication 5698-1, version 1 July 2026 (359 pp.).** https://www.pbl.nl/downloads/pbl-2026-eindadvies-sde-plus-plus-2026-5698-1pdf (page: https://www.pbl.nl/publicaties/advies-basisbedragen-sde-2026).
- p.126: subsidy period 15 yr, technical lifetime of a doublet 30 yr. p.127 Table 11.1: ESP and injection pump in every category. p.128: heat-pump SPF set by the Carnot method. p.129 Table 11.2: capex includes drilling (with double casing), ESP, gas/oil separation, surface HX, civils, insurance, interest during construction and a 3-year inflation correction; excludes the distribution network, backup boilers, preparation and exploration.
- p.133: deep category covers 1,500–4,000 m. p.136 Tables 11.7a–c (baseload, 6,000 h), 2026 advice: < 12 MW: 8.7 MW, 2,463 EUR/kW, 117 EUR/kW/yr, variable O&M 0.0063 EUR/kWh, base amount 0.0799 EUR/kWh; 12–20 MW: 15.9 MW, 1,719, 118, 0.0053, 0.0696; ≥ 20 MW: 27.4 MW, 1,340, 121, 0.0058, system SPF 19.9, electricity 8,269 MWh/yr, 0.0627.
- p.138 Tables 11.8a–b (90–120 °C network with heat pump; geothermal source 11.2 MW plus a heat pump of 18.5 MW_th output): 3,045 / 2,587 EUR/kW; 179 / 167 EUR/kW/yr; heat-pump SPF 2.9; system SPF 3.5; base amount 0.1476 / 0.1325 EUR/kWh.
- p.139 Table 11.9 (mid-load) base amount 0.0997; p.140 Tables 11.10a–b (non-baseload) 0.1850 / 0.1647; p.141 Table 11.11: 0.2075; p.143 Table 11.13 summary of all base amounts.
- p.46 Tables 4.1–4.2 (energy tax; EPEX 0.0906 and long-term 0.0743 EUR/kWh); p.48 Table 4.5 (TTF HHV 0.0351 / LHV 0.0390; long-term 0.0252 / 0.0280 EUR/kWh); p.50 §4.10 (EUA average 1 Sep 2024–31 Aug 2025 = 69.148 EUR/t; long-term ETS1 137.0265 EUR/t).
- p.56 §5.1.1–5.1.2: natural gas 56.2 kg CO2/GJ (RVO 2025 list), 0.225 kg/kWh heat at 90 % efficiency; electricity 0.13 kg/kWh (marginal, 2037, KEV 2025).
- p.58 Table 6.1; p.61 Table 6.2; p.64 §6.5 (inflation 2.0 %); p.65 §6.6 (geothermal economic lifetime 30 yr, depreciation 15 yr); p.66 Table 6.3 (WACC: geothermal 7.3 % nominal / 5.2 % real).
- p.174 §13.5.3 and p.176 Table 13.12: industrial heat pump 1,400 kW_th, COP 3.5, 1,476 EUR/kW_th, maintenance 33 EUR/kW_th/yr (4 % of equipment).

**[S4] TNO, Geological Survey of the Netherlands. ThermoGIS website (current versions v3.0, July 2026, and v3.1, October 2026), accessed 30 Oct 2026.**
- "Economic model": https://www.thermogis.nl/en/economic-model (Dutch: https://www.thermogis.nl/economisch-model). Well CAPEX = 1.96 x (790,000 + 555 x depth + 0.05 x depth²) EUR; other capex 3.5 M EUR + 882 EUR/kW; OPEX 81 EUR/kW/yr + 0.062 EUR ct/kWh; ESP electricity 0.23 EUR/kWh; costs "calibrated to the costs published by PBL for the SDE++"; 15-year payback; uses the SDE++ 2026 baseload base amounts.
- "Doublet and economic parameters": https://www.thermogis.nl/en/doublet-and-economic-parameters. Economic lifetime 30 yr; 6,000 h; contingency 0 %; tax 25 %; interest 5 %; inflation 1.5 %; return on equity 14.5 %; debt 80 %; pump efficiency 60 %; ESP depth 300 m; curvature factor 1.1; 8.5" casing; DH return temperature 30 °C.
- "Technical model": https://www.thermogis.nl/en/technical-model. Along-hole length = curvature factor x √(TVD² + (½ x well distance)²); factor 1.0–1.13 in practice; salinity = 70,000/1,500 x depth (ppm).
- "Heat pumps": https://www.thermogis.nl/en/heat-pumps (Carnot COP times system efficiency: 0.63 in the symbol list, "60 %" in the footnote; typical 50–70 %; 3 K heat-exchanger losses; 70/30 °C network). "Alternative scenarios": https://www.thermogis.nl/en/alternative-scenarios (heat pump 200 EUR/kW_th capex, 10 EUR/kW/yr OPEX; stimulation +0.5 M EUR).

**[S5] TNO. pythermogis documentation and source repository (accessed 30 Oct 2026).**
- Cost model: https://pythermogis-15909e.ci.tno.nl/theory/economicmodel/cost_model/. "CAPEX_wells = 2·wscale·(wc0 + wc1·scurve·z_top + wc2·(scurve·z_top)²)"; scurve·z_top is the along-hole depth.
- ThermoGIS NL properties (v2.x scenarios): https://pythermogis-15909e.ci.tno.nl/theory/utcprops/utc_props_TG/. wc0 0.25 (M EUR), wc1 700 EUR/m, wc2 0.2 EUR/m², wcscale 1.3, CAPEXbase 3.0 M EUR, CAPEXother,var 300 EUR/kW, contingency 15 %, OPEXpower 100 EUR/kW, OPEXheat,var 0.19 EUR ct/kWh, heat pump 200 EUR/kW and 10 EUR/kW/yr.
- Template scenario `tests/resources/test_input/scenarios/thermogistemplate.xml` in https://ci.tno.nl/gitlab/ags_public/pythermogis: well cost base 0.375 M EUR, 1,050 EUR/m along hole, 0.3 EUR/m², scaling 1.0.
- Chiller (Geothermal Atlas for Africa scenario): https://pythermogis-15909e.ci.tno.nl/theory/energyconversion/chiller/. Minimum production temperature 70 °C; return 60 °C; CAPEX 0.5 M EUR + 1,100 EUR/kW (incl. HX); OPEX 10 k EUR + 50 EUR/kW/yr; cites DOE (2017).

**[S6] van 't Spijker, H. and P. Ungemach (2016). *Definition of Electrosubmersible pump (ESP) design and selection workflow*. Kennisagenda Aardwarmte 2015/2016, 29 June 2016.** https://geothermie.nl/images/Onderzoeken-en-rapporten/01_07_16_Definitie_ESP/20031_Definition_of_ESP_design-_final_version_20160919-public.pdf. §9 Economics, pp.22–23: Table 5 ESP CAPEX 180–300 k EUR (250–500 kW_e; pump, seals, motor, cable, control, shipment, field service, RIH crew); Table 6 OPEX 63.5–95 k EUR/yr "assuming a four year life"; NL costs similar to the Paris Basin (p.23); ESP efficiency 55 % overall, some 35 %; 4–5 yr life objective (p.16) and "five year ESP life" (p.24). Companion slides (15 Nov 2016, https://geothermie.nl/images/Onderzoeken-en-rapporten/01_07_16_Definitie_ESP/Geofluid-presentation_ESP_15Nov2016.pdf), slide 10: 4–5 yr life objective; NL flows 100–300 m³/h at 80–100 °C.

**[S7] Kombrink, H. (14 Apr 2026). "When the reliability of your project depends on a single tool at hundreds of meters depth". GEO ExPro.** https://geoexpro.com/when-the-reliability-of-your-project-depends-on-a-single-tool-at-hundreds-of-meters-depth/. Quote: "The ESPs that are running in geothermal wells in the Netherlands have an average run time between one and two years."

**[S8] IEA HPT Annex 58 (2023). *High-Temperature Heat Pumps: Task 1 – Technologies*. Report no. HPT-AN58-2, August 2023 (Operating Agent B. Zühlsdorf, DTI).** https://heatpumpingtechnologies.org/content/uploads/sites/70/2023/09/annex-58-task-1-technologies-task-report.pdf. p.61: equipment cost 200–1,200 EUR/kW excluding installation and integration. p.64: Lorenz efficiency 11–69 % (Fig. 2-36); average expected lifetime 14.5 yr (< 0.5 MW), 19.0 yr (0.5–5 MW), 23.3 yr (> 5 MW). p.65 Table 2-3: 200–1,500 EUR/kW; 0.03–70 MW; 100–280 °C. p.72 footnote: a second-law efficiency of 0.46 used for steam generation.

**[S9] U.S. DOE (May 2017). *Combined Heat and Power Technology Fact Sheet Series: Absorption Chillers for CHP Systems*. DOE/EE-1608.** https://www.energy.gov/sites/prod/files/2017/06/f35/CHP-Absorption%20Chiller-compliant.pdf. Table 1 (p.1): single stage driven by 200–240 °F hot water. Table 2 (p.3): single-stage COP 0.70 (50 RT, hot water 190→181 °F), 0.74 (440 RT, 208→190 °F), 0.79 (1,320 RT, steam); chilled water 54→44 °F. Table 3 (p.4): installed cost 6,000 / 2,300 / 1,800 $/RT (equipment 2,010 / 930 / 820); O&M 0.6 / 0.2 / 0.1 ¢/RT·h.

**[S10] Yazaki. *WFC-SC 10, 20 & 30, Sezione 1: Specifiche tecniche*, ver. 03.04 (Italian distributor copy).** https://personales.upv.es/vsoto/index_archivos/FTP/SOLAR/WFCYAZAKI.pdf. §1.3 table (p.3): 35/70/105 kW cold; chilled water 12.5→7 °C; cooling water 31→35 °C; hot water 88→83 °C, range "Min. 75 – Max 95" °C; heat input 50.2/100.4/150.6 kW (COP ≈ 0.70).

**[S11] Helm, M. (24 Mar 2015). "Pump efficiency and adaptability". IEA SHC Task 48, 8th experts meeting (slides).** https://task48.iea-shc.org/Data/Sites/6/documents/events/meeting-08/2015_03_24_helm_a4-pump-efficiency-and-adaptability.pdf. Thermally driven chiller table (PDF p.4): EAW Wegracal SE30, 30 kW, COP 0.75, hot 90/80, reject 30/35, chilled 17/11 °C; SE80/SE50, COP 0.75, hot 86/71, chilled 15/9; Pink PC19 (NH3/H2O), COP 0.72, hot 75/68, chilled 18/15; Yazaki WFC-SC 0.69–0.70 at 12.5/7.

**[S12] U.S. EIA (March 2023). *Updated Buildings Sector Appliance and Equipment Costs and Efficiencies*, Appendix A (Guidehouse/Leidos). Costs in 2022 USD.** https://www.eia.gov/analysis/studies/buildings/equipcosts/pdf/appendix-a.pdf. "Commercial Centrifugal Chillers (Water-Cooled)", p.125 (PDF p.126): 2022 typical full-load COP 6.8, high 7.8, ASHRAE 90.1-2019 6.3; IPLV COP 11.3; installed 540–590 $/RT (typical), 740–760 (high); life 25 yr; maintenance 30–40 $/RT/yr. p.126: ratings exclude cooling-tower energy.

**[S13] Thu, K., Saththasivam, J., Saha, B.B., Chua, K.J., Srinivasa Murthy, S., Ng, K.C. (2017). "Experimental investigation of a mechanical vapour compression chiller at elevated chilled water temperatures". *Applied Thermal Engineering* 123: 226–233.** https://doi.org/10.1016/j.applthermaleng.2017.05.091. Abstract: COP +≈3.5 % per K of chilled water (7–17 °C tested, coolant 28–32 °C); at 17 °C, COP +37–40 % vs AHRI.

**[S14] ASHRAE Standard 90.1, minimum efficiency of axial-fan open-circuit cooling towers: ≥ 40.2 gpm/hp at 95/85/75 °F (CTI ATC-105).** Read from a secondary source: Baltimore Aircoil Company technical resource "Codes and standards" (2015), https://baltimoreaircoil.com/es/download_api_endpoint/1187/j22_tr_codesstandards_20150914.pdf. The standard itself was not consulted.

**[S15] Towler, G. and R. Sinnott, *Chemical Engineering Design* (cost correlations on a US Gulf Coast, 2010 basis; Ch. 7, Table 7.2 in the 3rd ed., 2022, doi:10.1016/B978-0-12-821179-3.00007-8).** Coefficients read from the OpenPyTEA data file that transcribes this table: https://raw.githubusercontent.com/pbtamarona/OpenPyTEA/main/src/openpytea/data/cost_correlations.csv. Row `plate_frame_hx_towler_2010`: a 1,600, b 210, n 0.95, A 1–500 m², 304 SS, purchased cost. Row `cooling_tower_n_pumps_towler_2010`: a 170,000, b 1,500, n 0.9, flow 100–10,000 L/s, field assembly. CEPCI 2010 = 550.8 and 2024 = 800.0 from the same repository's `cepci_values.csv` (Univ. of Manchester table). Not checked against the printed book.

**[S16] Eurostat, nrg_pc_205 "Electricity prices for non-household consumers – bi-annual data" (updated 19 Oct 2026).** https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_205/default/table; API used: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_pc_205?geo=NL&geo=EU27_2020&currency=EUR&unit=KWH`. NL X_VAT (EUR/kWh): band ID (MWH2000-19999) 2024-S1 0.1956, 2024-S2 0.1961, 2025-S1 0.1889, 2025-S2 0.1824, 2026-S1 0.1824; band IE (MWH20000-69999) 0.1538, 0.1341, 0.1432, 0.1182, 0.1391. X_TAX 2025: ID 0.1497/0.1438; IE 0.1201/0.1150. EU-27 X_VAT 2025: ID 0.1640/0.1596; IE 0.1381/0.1342.

**[S17] Eurostat, nrg_pc_203 "Gas prices for non-household consumers – bi-annual data" (updated 19 Oct 2026), unit KWH (GCV).** https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_203/default/table. NL X_VAT (EUR/kWh GCV): I3 (GJ10000-99999) 2024-S1 0.0744, 2024-S2 0.0623, 2025-S1 0.0849, 2025-S2 0.0675, 2026-S1 0.0839; I4 (GJ100000-999999) 0.0612, 0.0544, 0.0680, 0.0569, 0.0665. X_TAX 2025: I3 0.0450/0.0386; I4 0.0419/0.0361. EU-27 X_VAT 2025: I3 0.0660/0.0605; I4 0.0545/0.0483.

**[S18] Nissen, C., Cludius, J., Gores, S., Skribbe, R., Wissner, N. (Öko-Institut) (Dec 2025). *Trends and projections in the EU-ETS in 2025*. ETC CM Report 2025/06, European Topic Centre on Climate change mitigation / EEA.** https://www.eionet.europa.eu/etcs/etc-cm/products/etc-cm-report-2025-06/@@download/file/ETS-Report_2025_final.pdf. PDF p.9: average EUA price 2023 EUR 83.60/t, 2024 EUR 64.76/t; PDF p.17 table (−23 %); summary PDF p.5 (EUR 64.8/t).

**[S19] Umweltbundesamt / DEHSt, press release No. 01/2026 (7 Jan 2026), "Emissionshandel: 21 Milliarden Euro fließen in den Klima- und Transformationsfonds".** https://www.umweltbundesamt.de/presse/pressemitteilungen/emissionshandel-21-milliarden-euro-fliessen-in-den. Quote: "Dieser lag 2025 mit rund 74 (73,86) Euro oberhalb des Vorjahreswertes (2024: 65 Euro)" (average EUA auction price).

**[S20] IPCC (2006). *2006 IPCC Guidelines for National Greenhouse Gas Inventories*, Vol. 2 Energy, Ch. 2 Stationary Combustion.** https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_2_Ch2_Stationary_Combustion.pdf. Table 2.2, p.2.16: natural gas CO2 56,100 kg/TJ (lower 54,300, upper 58,300), CH4 1, N2O 0.1 kg/TJ, net calorific basis.

**[S21] CBS Statistics Netherlands (5 Dec 2025). "Energie- en emissiefactoren elektriciteit, update 2024".** https://www.cbs.nl/nl-nl/achtergrond/2025/49/energie-en-emissiefactoren-elektriciteit-update-2024. Excel: https://www.cbs.nl/-/media/_excel/2025/49/energie--en-emissiefactoren-elektriciteit---2024.xlsx. Tabel 1 (integral method, total production) CO2 factor "Totaal": 0.27 (2022), 0.22 (2023), 0.20 (2024) kg/kWh; gas-fired 0.37 (2024). Tabel 2 (reference-park method): 0.52, 0.47, 0.45 kg/kWh.

**[S22] SDES, French Ministry of Ecological Transition (2025). *Key figures on climate – France, Europe and worldwide, 2025 edition*, "9. Sector focus: electricity".** https://www.statistiques.developpement-durable.gouv.fr/edition-numerique/chiffres-cles-du-climat/en/9-sector-focus--electricity-. EU: "224 g CO2/kWh in 2023", source "SDES, d'après AIE, 2025".

**[S23] EEA, indicator ENER038 "Greenhouse gas emission intensity of electricity generation in Europe" (published 10 Jul 2026).** https://www.eea.europa.eu/en/analysis/indicators/greenhouse-gas-emission-intensity-of-1. Text: 2024 intensity 11 % below 2023 and 63 % below 1990. Absolute values sit only in the interactive chart, which I could not retrieve (HTTP 401).

**[S24] Sharqawy, M.H., Lienhard V, J.H., Zubair, S.M. (2010). "Thermophysical properties of seawater: a review of existing correlations and data". *Desalination and Water Treatment* 16: 354–380. doi:10.5004/dwt.2010.1079.** Author copy: https://web.mit.edu/lienhard/www/Thermophysical_properties_of_seawater-DWT-16-354-2010.pdf. Table 3, Eq. (9), p.360 (c_p from Jamieson et al. 1969; recommended; ±0.28 %). Table 2, Eq. (8), p.357 (density at 0.1 MPa, S in kg/kg, 0–180 °C, 0–0.16 kg/kg, ±0.1 %): a1–a5 = 9.999e2, 2.034e-2, −6.162e-3, 2.261e-5, −4.657e-8; b1–b5 = 8.020e2, −2.001, 1.677e-2, −3.060e-5, −1.613e-5. Eq. (3), p.355: S_R = 1.00472·S_P.

**[S25] Eurostat prc_hicp_aind (HICP annual averages, 2015 = 100; EA 2017 101.78, 2020 105.06, 2022 116.82, 2025 128.75; NL 2025 135.86) and ert_bil_eur_a (USD per EUR: 2017 1.1297, 2022 1.0530, 2024 1.0824, 2025 1.1300).** Used only for the conversions stated at the top.

**[S26] WML. *Tarievenregeling WML 2026*, Maastricht, 1 January 2026.** https://www.wml.nl/cms/assets/IManager/MediaLink/1/397/2604/0. p.5 "Kosten watergebruik per m³": tariff WML 1.1749 €/m³, taxes 0.0270, total 1.2019 €/m³ excl. VAT (1.3101 incl. 9 % VAT); "Belasting op Leidingwater (BoL)": 0.4373 €/m³ excl. VAT; the ceiling rises from 300 m³ to 50,000 m³ on 1 January 2026 and disappears in 2027. Read 4 Nov 2026.

**[S27] Vitens. *Tarieven 2026 Consument* (drinking water 1.34 €/m³ incl. 9 % VAT) and *Tarieven 2024 Zakelijk* (0.95 €/m³ excl. VAT).** https://www.vitens.nl/-/media/Project/Vitens/VitensNl/Tarieven/Documenten-tarieven-2026/050004-31_Vitens-Tarieven-2026-Consument.pdf; https://www.vitens.nl/-/media/Project/Vitens/VitensNl/Tarieven/Documenten-tarieven-2024/050005-33-Vitens-Tarieven-2024-Zakelijk-DEF.pdf. Read from a search summary on 4 Nov 2026, not downloaded; used only for the range.

**[S28] Ondernemersplein (KVK and the Dutch government), "Belasting op leidingwater omhoog".** https://ondernemersplein.overheid.nl/wetswijzigingen/belasting-op-leidingwater-omhoog/. The ceiling for large users disappears in 2027; then 0.55 €/m³ (a proposal, not yet passed). Read 4 Nov 2026.

Worked numbers (from `scripts/calcs.py` in this research folder):
- Wells at 2,500 m TVD and 1,500 m spacing: L = 2,871 m; v3 bracket 2.796 M EUR, so 5.48 M EUR (x1.96) or 10.96 M EUR (x2x1.96). With L = 2,750 m (vertical): 5.28 / 10.56 M EUR. v2: 4.79–5.08 M EUR per well. Template: 5.53–5.86 M EUR per well.
- ThermoGIS v3 total for 27.4 MW (PBL ≥ 20 MW reference): 1,210 EUR/kW (doublet reading) or 1,410 EUR/kW (per-well reading), against PBL's 1,340 EUR/kW.
- Brine c_p, S = 41.6 g/kg (1,030 kg/m³ at 20 °C): 3.984 (60 °C), 3.992 (75 °C), 4.000 (87 °C) kJ/kgK. Pure water at 25 °C gives 4.1865, a sanity check against 4.18.

---

## (c) Confidence and caveats

- **C1, well-cost formula ambiguity (medium confidence).** ThermoGIS v3 prints "1.96 x (790,000 + 555 x depth + 0.05 x depth²)" without saying whether the result is per well or for both wells. The pythermogis cost model writes the doublet cost as 2·wscale·(…), so 1.96 may mean 2 x 0.98, which gives 2.7 M EUR per well at 2,500 m. The older ThermoGIS configurations give 4.8–5.9 M EUR per well. I recommend about 5 M EUR per well (10–11 M EUR per doublet). ThermoGIS is calibrated to PBL's total capex, so the split between wells and surface is soft but the total is not: use about 1,340–1,720 EUR/kW_th as the total for 15–30 MW systems.
- **C2, price years differ.** DEA geothermal, heat-pump and boiler-update sheets are in 2025 EUR, while DEA gas boiler and gas engine sheets are in 2020 EUR. PBL capex is escalated to the expected investment decision (it includes a 3-year inflation correction). The ESP figures are 2016 prices and are not escalated. DOE and EIA costs are US prices converted to EUR.
- **C3, Danish vs Dutch geothermal.** The DEA plant (65 °C reservoir, electric heat pump, 80/40 °C network) is not our design (87 °C, 100/60 °C). PBL categories are the NL benchmark: their baseload cases (reference is greenhouses) assume 6,000 full-load hours and "middentemperatuur" delivery without a heat pump; the mid-load case states a network of about 70–75 °C ([S3] Table 11.1 p.127; §11.8 p.139). Our network runs at 100 °C, so PBL's "90–120 °C network with heat pump" category (2,587 EUR/kW, SPF 2.9) may be the closer analogue if a heat pump is needed.
- **C4, fixed O&M differs about 2x across sources.** PBL 121 EUR/kW/yr (about 9 % of capex per year; includes insurance, staff, grid standing charges and ESP provisions) vs ThermoGIS 81 vs DEA 55–60. The DEA tech brief notes its own fixed O&M rose 2–3x in the 2026 update.
- **C5, ESP life.** The 4–5 year design life (2016) and the 1–2 year average run time observed in the NL fleet (2026 trade article) differ a lot. The ESP provision is a sensitivity parameter. I found no separate injection-pump cost.
- **C6, heat-pump COP at 45→100 °C is model-derived.** The DEA and Annex 58 Lorenz efficiencies are sourced; the COPs in row 2.10 are my application of them. A Lorenz calculation (sink glide 60→100 °C) gives about 4.6–4.9, while a single-temperature Carnot calculation gives about 3.1–3.4. PBL's sourced SPF of 2.9 for a 90–120 °C network is a conservative NL anchor. ThermoGIS's 200 EUR/kW heat-pump capex looks like equipment only and is far below DEA and PBL (0.95–1.5 M EUR/MW installed).
- **C7, boiler efficiency at a 60 °C return.** The 103–105 % (LHV) DEA values need condensing. With a 60 °C return, condensing is marginal, so about 94–96 % LHV is more realistic. I did not find a source that quantifies the exact return-temperature dependence.
- **C8, absorption chiller at 20/25 °C.** No source gives COP at exactly 20 °C supply. The closest data are 15–18 °C chilled water (COP 0.71–0.75, [S11], manufacturer nominal data in a conference slide). Capex is US-based (DOE 2017), converted to EUR. I found no EU or Danish catalogue for district-cooling chillers; DEA's absorption heat-pump sheets were removed in 2026.
- **C9, electric chiller COP at 20 °C is extrapolated** 3 K past the measured range of Thu et al. (7–17 °C), and it excludes tower fans and pumps. The capex excludes the cooling tower (EIA says so explicitly). The tower cost comes from a 2010 process-plant correlation; the fan-power estimate uses the ASHRAE 90.1 minimum, read from a vendor summary rather than the standard.
- **C10, brine c_p.** The correlation is for seawater-composition brine. NL formation brines are NaCl–CaCl2 dominated; the error at about 40 g/kg is probably small, but this is not verified. The density basis for "1,030 kg/m³" matters: at 15–20 °C it implies S ≈ 41 g/kg and c_p ≈ 3.99; as an in-situ density (87 °C, 250 bar, about 1.1 % compression assumed) it implies S ≈ 70 g/kg and c_p ≈ 3.86 kJ/kgK.
- **C11, grid emission factors depend on method.** Use CBS 0.20 t/MWh (2024 average) for attributional accounting, about 0.45 for fossil-marginal, and PBL's 0.13 for forward-looking SDE++-style accounting. The EU-27 0.224 t/MWh is CO2 only (2023, IEA data via SDES). My about-0.20 figure for 2024 is derived from EEA's −11 % statement.
- **C12, Eurostat bands.** "Excluding VAT and other recoverable taxes" (X_VAT) still includes NL energy tax and network charges. Band ID vs IE changes the price by about 55 EUR/MWh; pick by expected annual consumption (ESP plus heat pump). Gas prices are per kWh GCV; multiply by about 1.11 for LHV. NL band IE and gas I3/I4 move a lot between half-years (e.g. IE 2025-S2 118 vs 2026-S1 139 EUR/MWh).
- **C13, emissions not covered by the factors above.** Produced gas at 0.8 Nm³/m³ (80 % CH4, 20 % CO2) adds about 0.32 kg CO2 per m³ of brine if the CO2 is vented, plus about 1.27 kg if the methane is burned (derived with 1.977 kg/Nm³ CO2); PBL p.127 notes this by-catch gas is a regulatory issue. Gas engines also emit methane (315 g CH4/GJ fuel, [S1] sheet 06), which adds roughly 15 % CO2e on top of combustion CO2 with a GWP of about 28–30 (GWP is my assumption).
- **Not found or not used:** EBN well-cost datasets; a separate injection-pump cost; an EU or NL district-cooling plant cost catalogue; an absorption-chiller COP measured at exactly 20/25 °C; an independently published NL geothermal LCOH range other than PBL's base amounts (which are cost prices at PBL's WACC with a 15-yr subsidy and 30-yr life). The Arpagaus et al. (2018) COP–lift correlation could not be checked (full text blocked), so it is not used.
