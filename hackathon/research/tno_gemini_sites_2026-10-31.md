# Which doublets does TNO run GEMINI on, and can Dioscuri use their data?

Research note for Dioscuri (SPE GeoHackathon 2026), 31 Oct 2026.

How to read this note:
- Numbers come from the source cited next to them.
- **derived** means I calculated it from public data; the method is given next to it.
- **estimate** or **assumption** means it is not in any source.
- "Not found" means I searched and found nothing.
- I called the public APIs (NLOG, ThermoGIS) myself on 31 Oct 2026, so the request formats below are tested.

---

## Short answer

1. **GEMINI sites.** The repo names no plant. Public project documents name two operational GEMINI installations, both installed in Q1 2025:
   - **Haagse Aardwarmte Leyweg (HAL)** in The Hague (operator Gaia/Aardyn);
   - **Trias Westland** in Naaldwijk (operator HVC).

   The Nieuwe Warmte Nu (NWN) project page also lists two demonstration sites: **Geothermie Delft** (Aardyn) and the **Jan Brouwer test well in Rijswijk**. I found no proof that GEMINI is running at either. The TNO papers that use field data never name the well.
2. **Can we get their data?** Partly.
   - **Public:**
     - monthly water, gas and injection volumes per well from 2013 (NLOG API, open for reuse with attribution);
     - well depths (NLOG);
     - production plans, geology reports and test reports, with permeability, thickness, temperature, salinity, design flow and injection temperature (NLOG and RVO documents);
     - regional reservoir maps (ThermoGIS, CC BY 4.0).
   - **Not public:**
     - the 15-minute or hourly plant data (SCADA) that GEMINI runs on;
     - heat output per plant (only national totals are published);
     - the monthly temperatures and pressures that operators send to NLOG. GEMINI's own NLOG report fills these fields, but NLOG publishes only the volumes.
3. **Demand.** No site publishes its own hourly demand. Usable public stand-ins:
   - **When2Heat** for the Netherlands (hourly heat demand, CC BY 4.0);
   - the official **gas consumption profiles** (hourly fractions, by temperature);
   - **KNMI** hourly weather (CC0);
   - an open greenhouse model (**GreenLight**) for greenhouse load;
   - the **challenge's own daily demand file**, scaled to the site.
4. **Recommended example projects**, ranked by how complete the data is:
   1. **Trias Westland** (two doublets, greenhouses, GEMINI site);
   2. **HAL / Den Haag Geothermie** (one doublet, district heating, GEMINI site);
   3. **Middenmeer** (ECW, Rotliegend sandstone, greenhouses; not a GEMINI site, but a useful contrast case);
   4. **Geothermie Delft** (campus and homes; GEMINI demo site, but its well data stays confidential until 2028).

---

## 1. Where GEMINI is used

### 1a. What the repo says (checked first)

Files read: `src/gemini_documentation/source/*.rst`, the root `README.md`, `gemini-project/geothermal_example/`, `dataset/` and `src/gemini_application/reportgenerator/`. The model, simulator and interface packages have no README files; the only README is `src/gemini_agent/README.md`.

| Finding | Where |
|---|---|
| Developed by TNO, Well Engineering Partners (WEP) and Helin. Main partners: TNO, WEP, Helin, Aardyn and HVC. Sponsored by Nieuwe Warmte Nu, theme "Datagedreven optimalisatie aardwarmtesystemen". The README lists "TNO, Gaia Energy, HVC, WEP, Helin". | `src/gemini_documentation/source/index.rst`; `README.md` (Acknowledgments) |
| Contacts: Ryvo Octaviano (TNO, platform), Jonah Poort (TNO, manual); emails are in `index.rst`. | `index.rst` |
| ESP model reference: "TNO 2022 R11363, *Model-based monitoring of geothermal assets, case study: electrical submersible pumps*". It names no site, and I could not find the report online. | `model_well_esp.rst` |
| GEMINI builds the monthly **NLOG report** that operators must submit (Excel with an XML export; month plus licence holder). Fields per producer: `prod_vol_water`, `prod_gas_vol`, `prod_oil_vol`, `prod_condens_vol`, `prod_inhibit_vol`, `prod_temp_avg_weighted`, `prod_pres_avg`, `prod_pres_min`, `prod_wh_pres`. Per injector: `inj_vol_water`, `inj_temp_avg_weighted`, `inj_pres_avg`, `inj_pres_max`, `inj_inhibit_vol`. Plus `tot_oper_hours`. | `application_report_generator.rst`; `reportgenerator.py` (`calculate_nlog_1A/1B/2`) |
| The example project is generic: reservoir 80 °C, 45 m, 10,000 mD, top 1,800 m; trajectory to 2,800 m MD / 2,300 m TVD. The dataset (15 min, 7 Jun–3 Dec 2024) holds an almost constant 160 m³/h, 80 °C and 10.9 MW. It names no real site. | `gemini-project/geothermal_example/*.param`; `dataset/geothermal_example_dataset.csv` |
| The team's own note (27 Oct) already lists the NWN pilot sites: Trias Westland, Geothermie Delft and the Jan Brouwer well. | `hackathon/docs/research/hackathon_intel_2026-10-27.md` §6 |

**Not in the repo:** any named plant, field case, well name, or real operator dataset.

### 1b. Evidence from the web

| Site (NLOG installation, wells) | Operator | What the evidence says | Source | Confidence |
|---|---|---|---|---|
| **Haagse Aardwarmte Leyweg, "HAL"** (NLOG: *Den Haag Geothermie*, wells DEN HAAG-GT-01/-02 = HAG-GT-01/02) | Aardyn B.V., part of Gaia Energy | "In Q1 of 2025 the first version of the GEMINI digital twin … have been installed for the HAL and Trias Westland sites of GAIA and HVC respectively." Next version (ESP monitoring, WIMS, reports) due Q3 2025. | NWN, *Update GEMINI Q2 2025* (2025) | High: a project document says it is installed |
| **Trias Westland** (NLOG: *Naaldwijk Geothermie* 1 and 2, wells NAALDWIJK-GT-01…04 = NLW-GT-01…04) | Trias Westland B.V., initiated by HVC, Capturam and Royal FloraHolland | The same sentence as above. The Stanford 2026 GEMINI paper thanks "Sander Maat from HVC for providing the data used in this study" (ESP failure prediction on "a specific geothermal well in the Netherlands", 3 failures). | NWN Q2 2025; Shoeibi Omrani et al., SGW 2026 | High for the installation. Which HVC well the paper used is not stated (HVC also runs Maasdijk and Monster) |
| **Geothermie Delft** (wells DELFT-GT-01, DELFT-GT-02-S2) | Geothermie Delft B.V.; partners TU Delft, EBN and Gaia/Aardyn | Listed as a demo site: "Geothermie Delft (Aardyn)". First production in NLOG: Feb 2026. | NWN project page | Medium: listed as planned, not confirmed as installed. TU Delft runs its *own* digital twin there (Voskov et al. 2024), which is not GEMINI |
| **Jan Brouwer thermal-storage test well, Rijswijk** | Rijswijk Centre for Sustainable Geo-energy (the NWN page words it slightly differently) | Listed as a demo site. A documentation host `gemini-rijswijk.westeurope.cloudapp.azure.com` is indexed. | NWN project page; web index | Medium. It is a storage test well, not a heat doublet |
| Hosted instances | – | Indexed documentation hosts `gemini-hvc…`, `gemini-tno…` and `gemini-rijswijk….westeurope.cloudapp.azure.com`. Their pages are generic and name no plant. | Web index | Hostnames only (inference: one instance per partner) |
| WIMS screenshot | – | WEP slides (WarmingUP GOO, 12 Jun 2025) show a well-barrier sheet for **VDB-GT-05, Bleiswijk**, dated 16-4-2025. The same slides say "Release to Gaia/HVC in steps for testing". | Degener (WEP), 2025 | Low: a screenshot could be an example. The DGK 2025 paper anonymises the same sheet as "XXX-GT-01" |
| Unnamed sites in papers | – | GRC 2022: "a low-enthalpy doublet … representative for production from sedimentary reservoirs". Geoenergy Sci. Eng. 2025: 2 years of hourly ESP data from "a low-enthalpy hydrothermal geothermal well". DGK 2025: "a geothermal plant in the Netherlands for direct-use heating". | See sources | Sites not named |

Also searched, with no link to GEMINI found:
- the Kennisagenda Aardwarmte reports;
- EBN reports;
- the SCAN seismic programme (EBN/TNO, 2019–2022; its data is on NLOG);
- EAGE/EGC/WGC papers;
- operators' news for Californië, Honselersdijk, Vierpolders, Middenmeer and Pijnacker.

**Not found:**
- a public list of GEMINI deployments;
- the TNO 2022 R11363 ESP report;
- any public GEMINI time series from a real plant;
- confirmation that the challenge's reservoir or demand is based on a real site. The challenge reservoir (87 °C at 2,500 m, gas–liquid ratio 0.8) looks like a West Netherlands Basin doublet: Naaldwijk produces 87 °C from about 2,350 m with about 0.9–1.0 Nm³ gas per m³ water. That is an observation, not evidence.

---

## 2. Public data that can define a Dutch doublet in Dioscuri

### 2.1 NLOG monthly production per well (tested; the best time series)

- **Fields** (one row per well per month, JSON):
  - `facilityName`, `wellName`, `operatorName`, `startDate` (month);
  - `h2oProd` (m³), `h2oInj` (m³), `gasProd` (Nm³), `oilProd` (Sm³), `conProd` (Sm³), `inhibProd` (L), `inhibInj` (L).
- **No** temperatures, pressures, operating hours or energy, although operators report those through the same NLOG form (see 1a).
- **Coverage:** Jan 2013 to Aug 2026; 6,643 rows; 39 installations, Heerlen mine water included.
- **Access:** POST to a JSON API used by the NLOG data centre (no key needed). There is also an Excel export.
  ```bash
  # all geothermal wells, 2023–2025, JSON
  curl -X POST -H "Content-Type: application/json" \
       -d '{"yearStart":2023,"yearEnd":2025}' \
       https://www.nlog.nl/nlog-mapviewer-api/rest/prodfigures/geothermal
  # filter by name (matches facility/well, e.g. "Naaldwijk"); Excel export
  curl -X POST -H "Content-Type: application/json" \
       -d '{"name":"Naaldwijk","yearStart":2025,"yearEnd":2025}' \
       "https://www.nlog.nl/nlog-mapviewer-api/rest/prodfigures/geothermal-export?lang=en" -o naaldwijk_2025.xlsx
  ```
  The API is undocumented: I found the endpoints in the data centre's own JavaScript. NLOG could change it. Front end: https://www.nlog.nl/datacenter/?lang=en (production figures, then geothermal).
- **Licence:** NLOG "does not claim any rights". Users may "copy, download and disclose in any way" and edit, "provided NLOG.NL is quoted as the source" (https://www.nlog.nl/en/disclaimer).
- **What it gives Dioscuri:**
  - real monthly flow (volume ÷ hours in the month);
  - the gas–liquid ratio (`gasProd/h2oProd`);
  - seasonal shape;
  - outage months. Examples: Naaldwijk I, Sep 2025, 40 m³/h; Den Haag, Jun–Jul 2025, about 0; Poeldijk, Oct 2025, 52 m³/h. The cause is unknown (maintenance, low demand or failure).

  This is real evidence for availability and for the "330 days" assumption.

### 2.2 NLOG well data

- **Borehole list API** (tested): `POST https://www.nlog.nl/nlog-mapviewer-api/rest/brh/boreholes` with an empty body. It returns all 6,738 NL boreholes with:
  - `boreholeName`, `shortName`, `endAhDepthInMeters`, `tvdInMeters` (and NAP versions);
  - `startDate`, `endDate`, `statusDescription`, `purposeCd`, `legalOwnerName`, `confidentialityDate`, `boreholeDbk`.
  - No coordinates.
- **Per-well page:** `https://www.nlog.nl/nlog-mapviewer/brh/<boreholeDbk>`, for example https://www.nlog.nl/nlog-mapviewer/brh/2512296585 (NLW-GT-01). Per NLOG it holds documents (reports, composite logs as TIF/PDF), LAS/LIS log curves, deviation data, core data and stratigraphy.
- **Bulk thematic data:** https://www.nlog.nl/sites/default/files/2026-09/thematische_data_boringen.zip (one sheet per data type: deviation surveys, gas composition, porosity/permeability, stratigraphy, …).
- **Confidentiality:** logs and reports are public **5 years** after drilling (NLOG boreholes page). Example: the Delft wells show `confidentialityDate` 2028-09/12 and no depths yet.

### 2.3 NLOG documents (the richest source per site)

Production plans (*winningsplannen*), TNO-AGE advice letters, SDE+ geology reports and well-test analyses, published as redacted PDFs on NLOG.

Typical contents:
- reservoir, depth, thickness, net-to-gross, permeability from tests;
- temperature, salinity, gas–liquid ratio;
- design and maximum flow, injection temperature;
- maximum wellhead pressure versus flow (the SodM protocol);
- DoubletCalc inputs;
- yearly production forecast (m³, GJ, Nm³ gas, full-load hours);
- customers.

The yearly national report *Delfstoffen en aardwarmte in Nederland* lists every installation and its wells. It gives heat output only as a national total: 7.491 PJ in 2024.

### 2.4 ThermoGIS v3.1 (TNO-GDN): reservoir properties at any location (tested)

- **Layers per aquifer:** depth, thickness P10/50/90, permeability P10/50/90, porosity, transmissivity, net-to-gross, temperature, flow rate P10/50/90 (also stimulated), power P10/50/90 (also with heat pump), heat in place, economic potential. Example service: `…/thermogis_gdn/SLDN_STACKED_v1/MapServer`.
- **Access:**
  - grids in NetCDF (RD New, EPSG:28992): https://www.thermogis.nl/sites/default/files/2026-10/for_external_use_0.zip
  - property table: https://www.thermogis.nl/sites/default/files/2026-10/ThermoGIS_V3.1_public_reservoir_properties_V1.xlsx
  - ArcGIS REST: https://gis.gdngeoservices.nl/standalone/rest/services/thermogis_gdn/ (point query works with WGS84 input)
  - temperature model: by email request only.
  ```bash
  curl "https://gis.gdngeoservices.nl/standalone/rest/services/thermogis_gdn/SLDN_STACKED_v1/MapServer/identify?geometry=4.205,51.995&geometryType=esriGeometryPoint&sr=4326&layers=all:2,4,7,11,14,17,25&tolerance=1&mapExtent=3,51,5,53&imageDisplay=600,600,96&returnGeometry=false&f=pjson"
  ```
- **Licence:** the download page says CC BY 4.0, cited as "TNO – GDN (2025) ThermoGIS v3.1". The general website disclaimer is stricter (personal, non-commercial use). Use the data under CC BY with the citation, and do not copy website text.
- **Caution:** ThermoGIS values are regional and per stacked formation, so they differ from well data. Point queries for the Nieuwerkerk Formation stack (SLDN_STACKED) at my approximate site coordinates:

| Approx. point (lat, lon) | Depth [m] | Thickness P50 [m] | Perm P50 [mD] | kH P50 [D·m] | N/G | T [°C] | Flow P50 [m³/h] | Power P50 [MW] |
|---|---|---|---|---|---|---|---|---|
| Naaldwijk (51.995, 4.205) | 2,050 | 362 | 279 | 44.6 | 0.44 | 92.8 | 367 | 24.5 |
| Den Haag Leyweg (52.046, 4.257) | 1,916 | 456 | 678 | 143 | 0.47 | 91.7 | 460 | 30.4 |
| TU Delft (51.995, 4.375) | 1,581 | 412 | 514 | 90.7 | 0.43 | 78.4 | 426 | 22.4 |

Well data at Naaldwijk, for comparison:
- Delft Sandstone about 55–83 m thick, N/G about 90 %;
- permeability from the well test about 700 mD;
- produced water 87 °C (PanTerra 2018).

So the formation stack is not the producing interval. Use ThermoGIS only where no well data exist.

### 2.5 Other public sources

| Source | What is in it | Format and access | Terms |
|---|---|---|---|
| RVO subsidy final reports (e.g. RNES) | Project history, test results, capacity, customers | PDF, rvo.nl | Public document; no licence stated |
| SodM (regulator) | **Injection-pressure protocol:** "usable for temperature differences between producer and injector of at most 40 °C", with extra justification needed above that. Also a pressure conversion tool and the 2025 supervision framework. No time series. | PDF/web, sodm.nl | Public |
| Operators' and trade news (ThinkGeoEnergy, HortiDaily, TU Delft Delta) | Capacity (MWth), customers, opening dates | Web | Copyrighted news; cite, don't copy |
| WUR Energiemonitor glastuinbouw 2024 | Greenhouse sector used 7.1 PJ of geothermal heat in 2024 (provisional) | PDF | CC BY-NC 4.0 |

**Not found:**
- heat output (GJ) per installation by name;
- public temperatures or pressures per installation;
- supply and return temperatures of the Westland, The Hague or Delft networks;
- a document API for NLOG files (they are downloaded per well page).

---

## 3. Demand data when the site's own is not public

| Dataset | What it is | Resolution | Access | Licence | Fit for Dioscuri |
|---|---|---|---|---|---|
| **When2Heat** (Ruhnau, Hirth & Praktiknjo 2019; OPSD version 2023-07-27) | Simulated heat demand for 28 countries **including NL**: space heat and hot water for single-family homes, apartments and commercial buildings (MW and normalised MW/TWh), plus heat-pump COPs | Hourly (15-min variants), 2008–2022 | CSV/XLSX/SQLite, https://data.open-power-system-data.org/when2heat/ | CC BY 4.0 | Good district-heating shape (HAL, Delft). Scale to the site's annual GJ |
| **Gas consumption profiles** ("NEDU" profiles, now published by MFFBAS on Energiedatawijzer) | Hourly allocation fractions for small gas users: G1A (households and similar), G2A (small business), G2C. Columns `_TST`, `_RER`, `_TOP` (TST looks like a temperature; RER and TOP look like the temperature-dependent and fixed parts; check the readme in the zip). Plus a standard profile temperature (SPT) file and a GXX profile. Built from 2021–23 allocation data in 112 grid areas. | Hourly, one file per year (2015–2027) | ZIP of CSVs, e.g. https://energiedatawijzer.nl/app/uploads/Documenten/Profielen/Profielen/Profielen-aardgas-2025-v1.00.zip | No licence stated (flag) | A Dutch-official shape for residential heat demand that responds to temperature |
| **KNMI hourly weather** | Temperature, sun, cloud, wind, pressure, rain; about 60 stations, some from 1951 (e.g. 344 Rotterdam, 260 De Bilt) | Hourly | ZIP/ASCII, https://www.knmi.nl/nederland-nu/klimatologie/uurgegevens (e.g. `uurgeg_344_2021-2030.zip`) | CC0 (credit "bron: KNMI") | Drives a degree-hour or greenhouse model for the site's own weather |
| **GreenLight** (Katzin et al. 2020, *Biosystems Engineering* 194:61–81) | Open greenhouse climate and energy model (Venlo, tomato) | Any step | MATLAB, https://github.com/davkat1/GreenLight (third-party Python port: `GreenLightPlus` on PyPI) | Open source (check the repo licence) | Builds an hourly greenhouse heat demand for Westland or Middenmeer from KNMI weather. Heating error reported as 1–12 % |
| **NLOG monthly volumes** (section 2.1) | What the doublet actually delivered (volume × an assumed ΔT) | Monthly | API above | Reuse with attribution | Lower bound and shape of the *geothermal share* of demand, not total demand (gas boilers and CHP cover the peaks) |
| **Challenge demand files** | `GEMINI_Heating_Demand_Daily_2027.csv` and `GEMINI_Cooling_Demand_Daily_2027.csv` | Daily | Already in the repo (untracked) | Hackathon terms | Scale to a site's peak or annual demand, keeping the shape |
| CBS StatLine | Annual district-heating and housing statistics; CBS says actual heat use per home on district heating "is not available" | Annual | opendata.cbs.nl | CC BY 4.0 (CBS standard; table IDs not checked) | Annual scaling only |
| Hotmaps load profiles (Zenodo 4687256) | Generic hourly residential and commercial profiles | Hourly | Zenodo/GitLab | Not verified | Second choice; a forum post warns they reflect heat-pump tank charging |

**Not found:**
- a public **hourly greenhouse-cluster demand** for any Dutch geothermal site;
- public hourly demand for the **Den Haag Zuidwest** or **Delft** heat networks;
- a Kas als Energiebron hourly demand dataset. WUR reports give crop profiles only as figures, e.g. de Zwart 2007 for a cucumber case.

---

## 4. Proposed real-world example projects (ranked by data completeness)

Common assumption for the **estimate** columns: brine volumetric heat capacity of about 4.0 MJ/(m³·K). In the formulas, P is heat output (MW), Q is flow (m³/h) and ΔT is the temperature drop between producer and injector (K); the 4.0 is the assumed heat capacity in MJ/(m³·K):

- P [MW] ≈ Q [m³/h] × ΔT [K] × 4.0 / 3600.

Salinity of 120–160 g/L (Naaldwijk) changes this by a few per cent.

### Rank 1: Trias Westland, Naaldwijk I + II (greenhouses; GEMINI site)

| Item | Value | Source |
|---|---|---|
| Operator | Trias Westland B.V.; initiators HVC, Capturam, Royal FloraHolland | RVO 2019; ThinkGeoEnergy 2021 |
| Doublets and wells | TWL-01: NLW-GT-01 (4,447 m AH / 4,021 m TVD; drilled to the Triassic, which turned out too tight, and produced from the Lower Cretaceous through perforations at about 2.3 km) + NLW-GT-02-S1 (2,680 AH / 2,526 TVD). TWL-02: NLW-GT-03-S1 (2,600 / 2,494) + NLW-GT-04 (3,015 / 2,401) | NLOG boreholes API; RVO 2019 |
| Reservoir | Delft Sandstone Member (Schieland Group). Top about 2,300–2,400 m; gross 55–75 m (about 83 m at NLW-GT-01 in the test); N/G about 90 % | PanTerra 2018 |
| Permeability | Well test NLW-GT-01 about 700 mD. Design range for TWL-02: 450 / 650 / 1,000 mD | PanTerra 2018 |
| Temperature and salinity | Produced water 87 °C at about 2,350 m mid-reservoir (gradient 3.3 °C/100 m). RVO report: "87,5 graden". Salinity about 140,000 ppm NaCl equivalent (range 120–160 k) | PanTerra 2018; RVO 2019 |
| Gas | "circa 1 kuub per kuub" (about 1 m³ gas per m³ water). Burnt in a boiler; CHP planned later. NLOG gas–liquid ratio 2023–2025: 0.92–0.96 (I) and 0.83–0.96 (II) (derived) | RVO 2019; NLOG API |
| Injection temperature | About 86 °C produced, injected at about 35 °C, so ΔT about 51 K. That is **above** the challenge's 40 K cap and the SodM protocol range | Pre-drill production plan Naaldwijk II, 2020 |
| Design flow and limits | TWL-01 modelled at 430 m³/h, "the maximum the system can handle". Dynamic model: TWL1 350 m³/h, TWL2 260 m³/h average. Maximum wellhead pressure table, e.g. 80.6 bar at 400 m³/h including friction. TWL-02 tubing limit 525 m³/h | Production plan TWL-01, 2020; PanTerra 2018 |
| Observed flow | 2024: I = 2.961 Mm³ (338 m³/h average), II = 2.106 Mm³ (240 m³/h). 2025: I = 2.553 Mm³ (291 m³/h), II = 2.355 Mm³ (269 m³/h). Peak months about 680 m³/h combined (Dec 2024, Jan 2025) (derived) | NLOG API |
| Capacity | Doublet 1: 17–21 MWth (test 2018); doublet 2: P50 32 MW (P90 25, P10 41); system "more than 40 MWth". Two doublets "potentially about 1.0 PJ/yr" | RVO 2019; PanTerra 2018; ThinkGeoEnergy 2021 |
| Heat **estimate** | 2025: 4.908 Mm³ × 51 K × 4.0 MJ/(m³·K) ≈ 1.0 PJ, i.e. about 32 MW average (estimate; ΔT assumed constant) | derived |
| Demand side | Greenhouse growers: 67 signed letters of intent for over 55 MWth; 26–32 growers on doublet 1; each connection is twice the contracted capacity. No demand time series is public | RVO 2019 |

**What we would have to assume:**
- the hourly or daily greenhouse demand. Options: GreenLight with the nearest KNMI station (e.g. 344 Rotterdam); or the challenge heat file scaled to a 55 MW peak; or NLOG monthly volumes × ΔT as the geothermal share;
- network supply and return temperatures (only "injected at about 35 °C" is known);
- gas composition (it exists as a table in project documents, but I did not extract it);
- ESP setting depth and curve;
- well spacing (on the maps, not extracted).

**Why first:** two doublets, as in the challenge's 1–3 doublet range. Reservoir temperature (87 °C) and gas–liquid ratio (about 0.9) are close to the challenge's. It is a confirmed GEMINI site, and the geology, test data, plans and monthly volumes are all public.

### Rank 2: Haagse Aardwarmte Leyweg (HAL), Den Haag (district heating; GEMINI site)

| Item | Value | Source |
|---|---|---|
| Operator | 2020 plan: Haagse Aardwarmte Leyweg B.V., operator Hydreco Geomec. Now Aardyn B.V. (NLOG), part of Gaia Energy | HAL production plan, 2020; NLOG; ThinkGeoEnergy 2023 |
| Wells | HAG-GT-01 producer (2,702 m AH / 2,306 m TVD) and HAG-GT-02 injector (2,330 AH / 1,892 TVD), drilled 2010. The plan gives producing depth "about 2,192 m" and injecting depth "about 1,776 m". Spacing about 2,050 m at top reservoir | NLOG API; HAL plan 2020 |
| Reservoir | Delft Sandstone, about 70 m thick. Tests (Q1 2018): HAG-GT-01 2,330 mD over 62.5 m net; HAG-GT-02 1,400 mD over 96 m net. The interference test gave an *effective* 280 mD between the wells | HAL plan 2020 |
| Temperature | About 79 °C (77 °C in the forecast table) | HAL plan 2020 |
| Flow | 70–165 m³/h; 165 m³/h limited by heat demand and well diameter. Observed: 2025 = 0.821 Mm³ (94 m³/h average); monthly averages up to about 133 m³/h (Jan 2026) (derived) | HAL plan 2020; NLOG API |
| Gas | "circa 1 m³ aardgas per m³ water" (about 1 m³ per m³), degassed, used to heat the high-temperature network, flare as backup. NLOG gas–liquid ratio 0.87–0.95 (derived) | HAL plan 2020; NLOG |
| Injection | Winter design case: injection at 45 °C, 165 m³/h (ΔT about 32–34 K, inside the 40 K cap) | HAL plan 2020 |
| Forecast | 2025–2035: 1,059,414 m³/yr, 71,195 GJ/yr, 6,421 full-load hours. **Derived:** 67 MJ per m³, i.e. ΔT about 17 K at 4.0 MJ/(m³·K). That is well below the design case, so the network return is probably warm (not stated) | HAL plan 2020 |
| Demand side | Eneco's low-temperature city heating in Den Haag Zuidwest: 700 homes first, 600 more from 2020, room for at least 2,000 more. A 25 MWth gas auxiliary boiler on site | HAL plan 2020 |

**What we would have to assume:**
- the hourly demand: When2Heat NL apartment profile or gas profile G1A, scaled to 71,195 GJ/yr (geothermal share) or to the homes count × an assumed GJ per home;
- the network temperatures;
- the ESP data.

### Rank 3: Middenmeer I (ECW, Agriport, Noord-Holland; greenhouses; not a GEMINI site)

| Item | Value | Source |
|---|---|---|
| Operator | ECW Geowarmte I in 2019; now Ennatuurlijk Aardwarmte Middenmeer B.V. (NLOG) | TNO-AGE advice 2019; NLOG |
| Wells | Doublet 2 = MDM-GT-02-S2 (2,589 AH / 2,457 TVD) + MDM-GT-05 (2,385 / 2,384). Middenmeer has four installations in total | NLOG API; TNO-AGE 2019 |
| Reservoir | Slochteren Formation (Rotliegend), about 2,200 m | TNO-AGE 2019 |
| Temperatures | Produced at 91 °C, injected at 30 °C (ΔT about 60 K) | TNO-AGE 2019 |
| Flow | Maximum about 230 and 260 m³/h (doublets 1 and 2). Plan: 700 m³/h total ±20 %. TNO found 350 m³/h feasible in doublet 1 within the 73 bar injection limit (the requested 420 m³/h maximum was not). For doublet 2, 350 m³/h would need about 78 bar against a 70 bar limit. Observed (installation "Middenmeer Geothermie 3", MDM-GT-02/05): 2025 = 2.046 Mm³ (234 m³/h average) (derived) | TNO-AGE 2019; NLOG |
| Gas | 0.34 Nm³/m³ (also 0.34 in NLOG 2023–2025) | TNO-AGE 2019; NLOG |
| Energy | 0.038 and 0.044 PJ per month (doublets 1 and 2, start-up to early 2019) | TNO-AGE 2019 |
| Demand side | "glastuinbouwbedrijven" (greenhouse companies) | TNO-AGE 2019 |

**Why include it:** a contrasting case with a different reservoir, low gas and a high ΔT. It tests the agent's 40 K cap logic (a real site cools by about 60 K) and gas handling. Its data are thinner: no geology report was read for it.

### Rank 4: Geothermie Delft (TU Delft campus; GEMINI demo site)

| Item | Value | Source |
|---|---|---|
| Owner and partners | Geothermie Delft B.V.; TU Delft, EBN, Gaia/Aardyn; €50 M financing (Rabobank, NWB Bank) | ThinkGeoEnergy, 2 Mar 2026 |
| Wells | DELFT-GT-01 and DELFT-GT-02-S2 (drilled 2023). Depths are not public: confidential until Sep–Dec 2028 | NLOG API |
| Reservoir and temperature | Delft Sandstone, producer section "approximately 2300m depth" (EGU 2024). Water 78 °C from "around 2 kilometres" (Delta 2026) | EGU24-20414; TU Delft Delta 2026 |
| Capacity | "targeted to supply around 25 MW of thermal energy at peak conditions" | EGU24-20414 |
| Observed flow | Feb–Aug 2026 = 1.076 Mm³; monthly averages 163–328 m³/h after start-up (Jul 2026 the highest). Gas–liquid ratio 0.90 (derived; start-up period) | NLOG API |
| Demand side | Part of the campus plus three DUWO student blocks now; 6,000 more rental homes (Buitenhof) planned, 15,000 in total; linked to high-temperature storage | Delta 2026; EGU 2024 |

**What we would have to assume:**
- the reservoir thickness and permeability (ThermoGIS, or papers in Voskov et al. 2024 / DSUEL);
- the well paths;
- the whole demand profile (When2Heat or gas profile, scaled to a 25 MW peak).

It is good for a "new urban project" story. It is weakest on data until 2028 or until TU Delft publishes more.

### How these compare with the challenge spec

| | Challenge | Trias Westland | HAL | Middenmeer (doublet 2) | Delft |
|---|---|---|---|---|---|
| Reservoir | 100 m, 200 mD, mid 2,500 m | 55–83 m, 650–700 mD, about 2,350 m | about 70 m, 1,400–2,330 mD (280 mD effective), about 1,800–2,200 m | Rotliegend, about 2,200–2,450 m TVD | Delft Sandstone, about 2–2.3 km |
| T production | 87 °C | 87 °C | 77–79 °C | 91 °C | 78 °C |
| Gas–liquid ratio | 0.8 Nm³/m³ | about 0.9–1.0 | about 0.9–1.0 | 0.34 | about 0.9 |
| ΔT | ≤ 40 K | about 51 K | about 32–34 K (design) | about 60 K | not public |
| Flow per doublet | 50–300 m³/h | 240–340 m³/h average (2024–25) | 70–165 m³/h | about 234 m³/h average | up to about 330 m³/h monthly |
| Demand | 111.67 GWh heat, 30 MW peak; plus cooling | over 55 MWth contracted; greenhouses | 1,300+ homes; 71,195 GJ/yr from geothermal | greenhouses | 25 MW peak target |

Using them in Dioscuri:
- **"Challenge demand on a real subsurface":** keep the challenge's daily heat and cooling files and swap in the real site's reservoir and wells.
- **"Site's own demand":** use When2Heat or the gas profiles (district heating), or GreenLight (greenhouses), with KNMI weather, scaled to the documented contracted MW or forecast GJ. Validate against NLOG monthly volumes.

---

## 5. Getting the non-public data

- **TNO, the GEMINI team:**
  - Ryvo Octaviano and Jonah Poort (emails in `src/gemini_documentation/source/index.rst`);
  - Pejman Shoeibi Omrani (corresponding author of the papers);
  - the NWN contact is Laura Precupanu.

  Ask whether an anonymised GEMINI dataset from HAL or Trias Westland can be shared, and whether the challenge data is based on a real site. Ask through the organisers; it is unlikely before the 3–4 Nov deadline.
- **Operators:** HVC for Trias Westland (Sander Maat is acknowledged as the data provider in SGW 2026) and Gaia/Aardyn for HAL and Delft. Expect a confidentiality agreement.
- **NLOG/TNO:** the monthly temperatures and pressures reported under the Mining Act are not on the public API. I found no statement on whether they can be requested.

---

## 6. Points that matter for the agent

- **The 40 K cap has a regulatory root.** SodM's injection-pressure protocol is written for producer–injector temperature differences of at most 40 °C; above that the operator must justify the seal integrity. Real Dutch greenhouse doublets run at about 51 K (Naaldwijk) and about 60 K (Middenmeer). Dioscuri can cite this when it explains the cap.
- **Gas–liquid ratio from NLOG** is a free, real check on the gas assumption: about 0.9–1.0 in the West Netherlands Basin, about 0.34 at Middenmeer and about 0.41 at Andijk.
- **Monthly NLOG volumes** give real availability and seasonality (summer dips, outage months). That is better evidence for "330 days" than a guess.
- **ThermoGIS stack values are not well values** (section 2.4). Prefer documented well tests and label ThermoGIS values as regional.

---

## Sources

Repo (read 31 Oct 2026):
- `src/gemini_documentation/source/index.rst`, `index_about_gemini.rst`, `about_gemini_overview.rst`, `model_well_esp.rst`, `application_report_generator.rst`
- `src/gemini_application/reportgenerator/reportgenerator.py`
- `README.md`
- `gemini-project/geothermal_example/`
- `dataset/geothermal_example_dataset.csv`
- `hackathon/docs/research/hackathon_intel_2026-10-27.md`

GEMINI deployments and papers:
1. Nieuwe Warmte Nu!, *Datagedreven optimalisatie aardwarmtesystemen* (project page), accessed 2026. https://nwn.nu/projecten/innovaties/datagedreven-optimalisatie-aardwarmte-systemen/
2. Nieuwe Warmte Nu!, *Update GEMINI Q2 2025*, 2025. https://nwn.nu/media/update-innovatieproject-April-May-2025-1.pdf
3. TNO, *GEMINI: intelligent decision support system for geothermal assets*, 30 Nov 2023. https://www.tno.nl/en/newsroom/insights/2023/11/intelligent-support-system-geothermal/
4. TNO, GEMINI webinar event page, 2025. https://www.tno.nl/en/newsroom/events/2025/gemini-digital-twin-geothermal-plants/
5. Degener, F. (WEP), *Gemini Digital Twin Development – Corrosion Prognosis*, WarmingUP GOO session, Geothermie Nederland, 12 Jun 2025. https://geothermie.nl/wp-content/uploads/2025/06/Sessie-4-Floris-Degener-WEP-Corrosion-prognosis.pdf
6. Shoeibi Omrani, P.S., Egberts, P.J.P., Octaviano, R., *Real-time Monitoring and Optimization of Geothermal Plants*, GRC Transactions 46, 2022. https://repository.tno.nl/SingleDoc?find=UID%204ae3182c-40e7-47aa-90df-8a156bafffae
7. Shoeibi Omrani, P., Yang, Y., Rijnaarts, H.H.M., Shariat Torbaghan, S., *Real-time model-based condition monitoring of geothermal systems under uncertainties – Case study on electrical submersible pumps*, Geoenergy Science and Engineering 249, 213775, Elsevier, 2025. https://publications.tno.nl/publication/34643980/sICmE1jF/omrani-2025-real.pdf
8. Degener, F., van Og, G., Blinovs, A., Octaviano, R., Palochis, D., Hashemi, L., Shoeibi Omrani, P., *Geothermal Digital Twins*, DGK 2025; Zenodo, 5 Feb 2026, CC BY 4.0. https://zenodo.org/records/18302404
9. Shoeibi Omrani, P., Hashemi, L., Poort, J., Schouten, A., Egberts, P.J.P., Octaviano, R., Palochis, D., *An Open Digital Twin Platform for Co-Simulation and Optimization of Geothermal Plant Operations*, 51st Stanford Geothermal Workshop, SGP-TR-230, Feb 2026. https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Shoeibi.pdf
10. Hashemi, L., Palochis, D., Poort, J., Octaviano, R., Shoeibi Omrani, P., *Advancing Geothermal Operations with Digital Twin Technology*, SPE-225592-MS, SPE Europe, Jun 2025. Abstract via search only; the page returned 403. https://onepetro.org/SPEEURO/proceedings/25EURO/25EURO/692684
11. Indexed GEMINI documentation hosts (generic content): https://gemini-hvc.westeurope.cloudapp.azure.com/documentation/sphinx/index_about_gemini.html (also `gemini-tno…` and `gemini-rijswijk…`)

Sites:

12. Cariaga, C., *Towards 500 MW of geothermal in the Netherlands – Gaia Energy acquires Aardyn*, ThinkGeoEnergy, 4 Oct 2023. https://www.thinkgeoenergy.com/towards-500-mw-of-geothermal-in-the-netherlands-gaia-energy-acquires-aardyn/
13. Hydreco Geomec / Haagse Aardwarmte Leyweg, *Winningsplan Haagse Aardwarmte Leyweg* (request for consent), NLOG, 2020 (file dated 29 Jan 2020). https://www.nlog.nl/sites/default/files/2020-10/200129_verzoek_tot_instemming_wp_haagse_aardwarmte_leyweg_publiek_gelakt.pdf
14. Trias Westland B.V. (Bogers, J.), *Eindrapportage RNES Onder-Krijt Trias Westland*, AARD05002, RVO, 9 Sep 2019. https://rvo.nl/sites/default/files/2022/01/Bijlage%20A%20Eindrapportage%20Trias%20Westland%20AARD05002_0.pdf
15. PanTerra Geoconsultants, *Geological report TW OK II* (G1363b), Mar 2018, with Trias Westland cover note of 29 Mar 2021, NLOG. https://www.nlog.nl/sites/default/files/2021-03/200213_appendix_1_-_geologisch_rapport_gelakt.pdf
16. Trias Westland, *Winningsplan TWL-01 NLW-GT-01/02*, v2.0, 31 Mar 2020, NLOG. https://www.nlog.nl/sites/default/files/2021-11/200331_verzoek_tot_instemming_wp_naaldwijk_i_publiek_gelakt.pdf
17. Trias Westland, *Pre-drill winningsplan Naaldwijk II*, 13 Feb 2020, NLOG. https://www.nlog.nl/sites/default/files/2021-08/200213_verzoek_tot_instemming_pre-drill_wp_naaldwijk_ii_publiek_gelakt.pdf
18. Cariaga, C., *Successful rollout of Westland geothermal heat system, Netherlands*, ThinkGeoEnergy, 14 Oct 2021. https://www.thinkgeoenergy.com/successful-rollout-of-westland-geothermal-heat-system-netherlands/
19. TNO-AGE, *Advies instemming winningsplan geothermie Middenmeer I*, AGE 19-10.072, 13 Dec 2019, NLOG. https://www.nlog.nl/sites/default/files/2021-01/191213_advies_tno_wp_middenmeer_i_gelakt.pdf
20. Heinsman, E., *TU Delft officially taps into geothermal energy*, Delta (TU Delft), 26 Feb 2026. https://delta.tudelft.nl/?p=181821
21. Cariaga, C., *Geothermal heat supply starts at Geothermie Delft project in the Netherlands*, ThinkGeoEnergy, 2 Mar 2026. https://www.thinkgeoenergy.com/?p=68320
22. Abels, H. et al., *A newly installed research infrastructure for geothermal energy … the TU Delft campus geothermal project*, EGU24-20414, 2024. https://meetingorganizer.copernicus.org/EGU24/EGU24-20414.html
23. Voskov, D. et al., *A research and production geothermal project on the TU Delft campus: initial modeling and establishment of a digital twin*, 49th Stanford Geothermal Workshop, 2024. https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2024/Voskov.pdf

Public data portals:

24. NLOG (TNO for the Ministry of Economic Affairs), production and injection data, 2026; API endpoints tested 31 Oct 2026. https://www.nlog.nl/en/production-and-injection-data and https://www.nlog.nl/datacenter/?lang=en
25. NLOG, boreholes; mapviewer; thematic dataset, 2026. https://www.nlog.nl/en/boreholes, https://www.nlog.nl/nlog-mapviewer/, https://www.nlog.nl/sites/default/files/2026-09/thematische_data_boringen.zip
26. NLOG, disclaimer (reuse terms). https://www.nlog.nl/en/disclaimer
27. Ministerie van Economische Zaken / TNO, *Delfstoffen en aardwarmte in Nederland – Jaarverslag 2024* (update 1.1), 14 Jul 2025. https://www.nlog.nl/sites/default/files/2025-09/Jaarverslag%20Delfstoffen%20Aardwarmte_2024_NL_update_1_1.pdf
28. van der Molen, J., Tolsma, S., *Aardwarmte in Nederland – 2023: een recordjaar, maar toch teleurstellend*, TNO 2024 R12084. https://www.nlog.nl/sites/default/files/2025-01/TNO-2024-R12084.pdf
29. TNO – GDN, *ThermoGIS v3.1*: download page, ArcGIS REST services, disclaimer, Oct 2026. https://www.thermogis.nl/en/download-data, https://gis.gdngeoservices.nl/standalone/rest/services/thermogis_gdn/, https://www.thermogis.nl/en/disclaimer
30. SodM, *Protocol bepaling maximale injectiedrukken bij aardwarmtewinning* (2021 version; page dated 14 Mar 2024). https://www.sodm.nl/documenten/publicaties/2013/11/23/protocol-bepaling-maximale-injectiedrukken-bij-aardwarmtewinning ; conversion tool: https://www.sodm.nl/documenten/richtlijnen/2023/05/17/conversietool-voor-injectiedruk-in-geothermieputten

Demand data:

31. Ruhnau, O., Hirth, L., Praktiknjo, A., *Time series of heat demand and heat pump efficiency for energy system modeling*, Scientific Data 6, 189, 2019; When2Heat dataset (OPSD, 2023-07-27), CC BY 4.0. https://data.open-power-system-data.org/when2heat/
32. MFFBAS / Energiedatawijzer (prepared by De Energiemanager), *Profielen aardgas 2025*, v1.00, 5 Jun 2024. https://energiedatawijzer.nl/documenten/profielen-aardgas-2025/ (overview: https://energiedatawijzer.nl/onderwerpen/profielen/standaardprofielen/)
33. KNMI, *Uurgegevens van het weer in Nederland*; copyright CC0. https://www.knmi.nl/nederland-nu/klimatologie/uurgegevens, https://www.knmi.nl/copyright
34. Smit, P., *Energiemonitor van de Nederlandse glastuinbouw 2024*, Wageningen Social & Economic Research, Rapport 2025-150, Oct 2025, CC BY-NC 4.0. https://doi.org/10.18174/702373
35. Katzin, D. et al., *GreenLight – An open source model for greenhouses with supplemental lighting*, Biosystems Engineering 194, 61–81, 2020; code: https://github.com/davkat1/GreenLight
36. CBS, *Verbeterd zicht op warmtenetten*, 2025. https://www.cbs.nl/nl-nl/longread/rapportages/2025/verbeterd-zicht-op-warmtenetten/4-conclusies
37. Hotmaps project (Fraunhofer ISI), residential load profile, Zenodo record 4687256 (licence not verified). https://zenodo.org/record/4687256
