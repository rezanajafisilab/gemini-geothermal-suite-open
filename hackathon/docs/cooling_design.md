# Cooling models and tool layer: design notes

These notes come from our first GEMINI review (27 Oct 2026). They are **our design**, not GEMINI
features. Technology numbers are indicative literature ranges: fit them to datasheets before use.
The alternatives A1–A4 are the first design alternatives we compared.

## 1. Why cooling fits a geothermal doublet

District cooling typically runs at 5–7 °C supply and 12–16 °C return. Its demand peaks in summer,
when heating demand is low apart from domestic hot water. A doublet runs best at a steady base load.
Using summer geothermal heat to drive **thermally driven chillers** therefore raises the doublet's
full-load hours and improves its economics. This seasonal match is our strongest design story. The
counter-arguments are the low COP of sorption chillers and the large amount of heat they reject.

## 2. Technology options

| Technology | Driven by | Cooling COP | Fit with geothermal |
|---|---|---|---|
| Absorption, single-effect H₂O–LiBr | hot water 70–120 °C (nominal 80–95 °C) | 0.6–0.75 | Good if the producer gives ≳ 80 °C. Capacity drops steeply below about 75 °C. Rejects about 2.4 × the cooling duty. |
| Absorption, double-effect | 140–180 °C | 1.1–1.4 | Not feasible for typical Dutch reservoirs. |
| Adsorption (silica gel or zeolite–water) | 55–90 °C | 0.45–0.65 | Uses lower temperatures, such as the heat-exchanger outlet in a cascade. Bulky and expensive per kW. |
| Electric vapour compression | electricity | 4–7 (EER) | Baseline and back-up. Grid CO₂ and peak electricity. |
| Free cooling: ATES, surface water, BTES | pumps only | 20–50 (electric) | Very common in NL (more than 2,500 ATES systems). Needs a seasonal energy balance. |
| Heat-recovery heat pump | electricity | 6–9 combined | Cools and heats at once; condenser heat goes to the DH return or to ATES. |

## 3. Integration patterns

- **Series cascade (used by A1).** Brine flows producer → absorption-chiller generator (the hot
  slice, in summer) → district-heating heat exchanger → heat-pump evaporator (the cold slice) →
  injector. This maximises the temperature drop across the doublet, and so the heat per unit of
  pumping.
- **Seasonal switching.** In winter all geothermal heat goes to district heating. In summer it
  drives absorption chillers, with electric chillers for the peak.
- **ATES coupling (A3).** Deep geothermal covers the heating base load. A shallow ATES cold well
  gives free cooling. Summer condenser and absorber heat charges the warm well (or a
  high-temperature ATES) for winter heat-pump use. This is the most "Dutch" solution.
- **All-electric (A4 reference).** Doublet plus heat pump for heat, electric chillers for cold.

The agent decides which blocks exist and how large they are, and verifies every hourly operating
point (section 6).

## 4. Proposed models (GEMINI-compatible)

Each model is a `StaticModel` or `DynamicModel` with `parameters`, `calculate_output(u, x)` and
GEMINI's common outputs `power_el` [W], `power_th` [W] and `emission` [kg CO₂/s], so plant totals
can be summed generically. Cooling models add `power_cool` [W]. Each gets an `.rst` page and
`unittest` tests. All solve in closed form, without `minimize`, for robustness and speed (see bug F2
in the overview for what an unchecked search does).

### Absorption chiller: characteristic-equation model

After Hellmann, Schweigler and Ziegler (1999), adapted by Kühn and Ziegler (2005). Three water
circuits pass through the machine: the generator (G, driven by hot brine), the absorber plus
condenser cooling water (AC) and the evaporator (E, the chilled water). With `t̄_X` the mean of a
circuit's inlet and outlet temperature:

```text
ΔΔt      = t̄_G − a·t̄_AC + e·t̄_E
Q_E      = s_E · max(0, ΔΔt − ΔΔt_min,E)        cooling delivered
Q_G      = s_G · max(0, ΔΔt − ΔΔt_min,G)        driving heat taken from the brine
Q_AC     = Q_E + Q_G                             heat rejected
t_G,out  = t_G,in  − Q_G  / (ṁ·cp)_G
t_E,out  = t_E,in  − Q_E  / (ṁ·cp)_E
t_AC,out = t_AC,in + Q_AC / (ṁ·cp)_AC
COP      = Q_E / Q_G
```

The mean temperatures are linear in the heat flows, so the system solves exactly. Fit `s_E`,
`s_G`, `a`, `e` and the thresholds by least squares to a manufacturer's performance table; the
agent can do this itself as the "automatic model generation" demo. Typical single-effect values
are a ≈ 2–3 and e ≈ 1–2; treat them only as plausibility bounds. Limit capacity with
`Q_E ≤ Q_E,nom` and part-load control. Checks: `COP < COP_rev = (1 − T_A/T_G) · T_E / (T_A − T_E)`
in kelvin, and `Q_AC = Q_E + Q_G` (± pump work).

### Adsorption chiller

Bilinear interpolation of datasheet maps `Q_E(t_G,in, t_AC,in, t_E,out)` and `COP(…)`, with a
hard lower limit on the driving temperature. Simple, transparent and honest
about where the data comes from.

### Electric chiller

Mirrors GEMINI's `HeatpumpBasic`: `COP = η_II · T_E / (T_C − T_E)` with
`T_E = t_chw,out − Δt_e` and `T_C = t_cw,out + Δt_c` (kelvin), and η_II ≈ 0.45–0.6. Optional
part-load curve `COP(PLR) = COP_nom · f(PLR)`. Outputs `P_el = Q_E / COP` and
`Q_rej = Q_E + P_el`.

### Heat rejection

Wet tower: `t_cw,out = t_wet-bulb + approach` (3–5 K). Dry cooler:
`t_out = t_dry-bulb + approach` (5–10 K). Fan power `P_fan = σ · Q_rej` with σ ≈ 0.01–0.03. Hourly weather (dry bulb, humidity) comes from KNMI or Open-Meteo,
which the agent can fetch (an "external data" bonus).

### Thermal storage tank (dynamic)

`E[k+1] = E[k] + Δt · (Q_charge − Q_discharge − UA · (T̄[k] − T_amb))` with
`T̄ = T_ref + E / (ρ·cp·V)`. Fully mixed or two-zone (stratified), with state-of-charge
bounds.

### ATES and free cooling (dynamic, simplified)

Track stored volumes and temperatures of the warm and cold wells. The extraction temperature relaxes
toward the ambient aquifer temperature with a thermal recovery efficiency η_rec ≈ 0.6–0.8. Constraints: well flow limit, injection temperature limits and an
annual energy balance (a Dutch permit condition). Free cooling:
`Q = ρ·cp·Q_ates · (t_DC,return − t_cold,extracted − Δt_HEX)`.

### Supporting components

- **ProfileSource** uses the simulator's `set_time` hook to output hourly heat and cold demand,
  supply and return temperatures, and weather. GEMINI's demand side is hydraulic (flow,
  temperatures, pressure), so a kW profile needs the network's supply and return temperatures.
- **GeothermalGradient**: `T_res(z) = T_s + G·z` (NL: T_s ≈ 10 °C, G ≈ 31 K/km), plus the
  wellhead temperature after wellbore loss (Ramey).
- **Dispatcher**: a merit order such as geothermal → heat pump → storage → boiler for heat, and
  free cooling → absorption → electric for cold. An LP/MILP option handles sizing.
- **Economics**: CAPEX/OPEX library, LCOH and LCOC, NPV, CO₂. GEMINI already uses 56.6 kg/GJ for
  gas and 0.3 kg/kWh for grid electricity.
- **Lifetime**: analytical thermal breakthrough time
  `t_b ≈ (π/3) · ((ρc)_aquifer / (ρc)_water) · H·L² / Q` (H: aquifer thickness, L: well spacing).
- **Fluid properties**: a temperature-dependent water or brine correlation, or IAPWS via
  `CoolProp` or `iapws`.

## 5. Wiring into the simulator

Registering a model is one import and one dictionary entry in `registry.py`:

```python
from gemini_model.absorption_chiller.absorption_chiller import AbsorptionChiller
from gemini_model.heatpump.heatpump_basic import HeatpumpBasic

COMPONENT_REGISTRY.update({
    "absorption_chiller": AbsorptionChiller,
    "heat_pump": HeatpumpBasic,
    "profile_source": ProfileSource,
})
```

A project-JSON fragment with an absorption chiller in the brine cascade (placeholder parameter
values, not fitted):

```json
"absorption": {"type": "absorption_chiller",
  "parameters": {"s_E": 9.5e3, "a": 2.5, "e": 1.5, "ddt_min_E": 15.0, "Q_E_nom": 3.0e6}},
{"predecessor": "filter_a", "successor": "absorption",
 "ports": [["temperature_out", "generator_temperature_in"], ["flow_rate", "generator_flow_rate"]]},
{"predecessor": "absorption", "successor": "heat_exchanger",
 "ports": [["generator_temperature_out", "primary_temperature_in"],
           ["generator_flow_rate", "primary_flow_rate"]]}
```

For annual runs, call `Solver.run(time_vector=range(8760))` with a ProfileSource. The doublet's
operating point changes only when flow or temperatures change, so memoise the nodal solves. One
steady solve takes about 2 ms and an hourly year about 10 s.

## 6. Verification hooks (shared by the tests and the agent's verifier)

- **Energy balance** per component and per plant, every hour:
  `ΣQ_in + ΣP_el = ΣQ_out + losses`, within a tolerance.
- **Second law**: no heat from cold to hot without work (catches F1); COP ≤ the Carnot or
  reversible limit (catches F2); heat-exchanger outlet temperatures do not cross.
- **Operating envelopes**: absorption `t_G,in ≥ t_min`; injection temperature ≥ its minimum
  (scaling); ESP intake pressure above vapour pressure; flow inside the pump curve and
  pump efficiency below 100 % (F4, F5); no silent clamping.
- **Loops**: the loop residual is below tolerance after iterating (F6).
- **Demand coverage**: unmet heat and cold [MWh/yr] and peak shortfall [MW], reported explicitly.

## 7. Agent tool surface (names indicative)

The LLM never touches raw GEMINI signatures or 8760-element arrays. It gets compact summaries and
handles, and nothing reaches the answer without passing the verifier. In 2025 the judges ran every
submission on Windows laptops (8 cores, 16 GB RAM, no GPU), so the tools and the default model must
be CPU-friendly.

| Tool | Wraps / returns |
|---|---|
| `inspect_demand` | Profile statistics: peaks, annual energy, load-duration curve, overlap of heat and cold. Returns a handle, not raw arrays. |
| `reservoir_temperature` | T(z) from the gradient or provided data; wellhead temperature after loss. |
| `solve_doublet` | `ProducerWell`/`InjectorWell` with the corrected friction sign and roughness: flow, ESP and injection-pump power, pressures. |
| `simulate_plant` | `build_project` + `Solver.run` on a project JSON (steady state). |
| `rate_component` | Heat exchanger, heat pump, absorption, adsorption or electric chiller, heat rejection, at one operating point. |
| `annual_simulation` | Hourly dispatch over 8760 h. KPIs: coverage, energy mix, COP statistics, full-load hours. |
| `economics` | CAPEX/OPEX, LCOH and LCOC, NPV, CO₂ against a gas or all-electric baseline. |
| `uncertainty` | Monte Carlo on kH, gradient, surface temperature and demand scaling: P10/P50/P90. |
| `optimise_design` | Sizing search: LP/MILP, Bayesian optimisation or a Pareto front (LCOH vs CO₂ vs unmet demand). |
| `verify_design` | Runs every check in section 6 and returns a structured report. |
| `search_docs` | RAG over GEMINI's `.rst` docs, model docstrings and datasheets, reusing GEMINI's Chroma/Ollama pipeline. |
| `propose_model` | Generates a new `gemini_model` class plus tests in a sandbox, and registers it only if its tests and the verifier pass (with human approval). |

## 8. Related open tools, and GEMINI's own assistant

- **TNO and other open tools the agent could call:** `geoloop` (borehole heat exchangers; GEMINI's
  `geoloop` branch), `mesido` (MILP design and operation of district heating, LGPL-3.0), `pyesdl`
  (ESDL energy-system descriptions), `pandapipes` (network hydraulics) and `pygfunction`. Each must
  be pip-installable on Windows and justify its install weight.
- **GEMINI's `chatpopup` assistant** already does RAG: ChromaDB, Ollama embeddings
  (`snowflake-arctic-embed`), MMR re-ranking, Dutch→English translation with a Gemma-3 translator,
  citations and a strict "answer only from context" prompt. It has no tool calling, so a tool-using
  engineering agent is a natural, mergeable extension of it.

## Appendix: GEMINI model reference

Condensed from the first review, for whoever writes the wrappers. Bug IDs refer to
[gemini_bughunt/](../gemini_bughunt/README.md).

| Model (registry key) | Physics | Caveats for heating and cooling design |
|---|---|---|
| IPR (`reservoir_ipr`) | Linear inflow: `p_bh = p_res ∓ Q/PI` | Production and injection share one PI in the simulator wrapper. No skin or transient terms. |
| `bottomhole_skin_dp` | Radial Darcy Δp + skin + hydrostatic | The hydrostatic term is computed but left out of `reservoir_dp`. Unused by the examples. |
| DPDT (`well`) | Segment march: Darcy–Weisbach with Swamee–Jain friction (single phase), Beggs–Brill (two phase), heat loss with U = 10 W/m²K | Constant water properties (ρ = 1000, μ = 1 mPa·s). Friction sign (F3), roughness default (F10). One ambient temperature, no gradient. |
| ESP (`esp`) | 6th-order head and power polynomials (bbl/d, ft), affinity laws | Needs vendor curve coefficients; the example has 10 stages at 65 Hz. F4, F5. |
| `ProducerWell` | IPR + DPDT (+ ESP) nodal solve by `brentq` | Wellhead temperature is a boundary input, passed straight through. |
| `InjectorWell` | IPR + DPDT; solves the required wellhead pressure; pump `P = Q·Δp/η` | Returns the 0.001 bar floor when gravity suffices, which reports zero pump power. |
| Separator | Δp = RQ, fixed ΔT, gas split by gas–water ratio | Co-produced gas feeds the boiler and CHP in the example. |
| Filter | `R(Q) = a·(1 − exp(−b·Q)) + R0` (fouling) | Also outputs `pressure_out_pa` and `flow_rate_m3h` for unit bridging. |
| `HeatExchanger` | Plate heat exchanger, ε-NTU (counter or parallel flow), Δp = RQ | Assumes the primary is the hot side (F1). Same ρ and cp on both sides. `heat_transfer_coefficient` is UA [W/K]. |
| `BoosterPump` | `p_out = p_in − R·Q`, fixed ΔT | Adds no head; `power_el` = 0. |
| `InjectorPump` | `P_el = Q · max(0, Δp) / η` | Flow in m³/s and Δp in Pa, while its neighbours emit bar. |
| Boiler | `P_th = η · LHV · ṁ_gas`; outlet T from the energy balance | Fuel-driven: to follow a load, invert `ṁ_gas = Q / (η · LHV)`. No outlet-temperature limit. |
| CHP | As the boiler, with a fixed electrical share (1/3 of η·fuel) | Same fuel-driven caveat. |
| Compressor | Multi-stage, intercooled ideal gas | F7. Not registered. |
| Mixer, Splitter, Adder | Mass-weighted mixing, fixed split fractions, sums | No valve or controller logic. |
| `HeatpumpBasic` | `COP = η · T_h / (T_h − T_s)` (Carnot or Lorenz), closed by `COP = Q_h / (Q_h − Q_s)` | F2. Not in the simulator registry. Uses ρ = 1000, cp = 4181. |
| `CO2Corrosion`, `Erosion` | de Waard–Lotz, NORSOK M-506; API RP 14E, DNV, Oka | Not needed for the design objective. |
| `BHEGeoloop` (`geoloop` branch) | Wrapper of the external `geoloop` 1.1.0 U-tube borehole model | F8. Needs Python 3.12. |

**Units the code actually uses.** Producer and injector wells: bar, °C and m³/h at the wellhead
(also m³/s outputs). DPDT, IPR and ESP: Pa, K and m³/s. Heat exchanger, boiler, CHP and the KPI
helpers: °C, m³/s and W, with ρ = 1050 and cp = 4200 hard-coded in the KPIs. Heat pump: °C in
and out, m³/s, W. The `.rst` docs sometimes say Pa or K where the examples use bar or °C.

**Calibration data.** `dataset/geothermal_example_dataset.csv`: 17,280 rows at 15 minutes
(7 Jun to 3 Dec 2024) with 32 plant tags. Production at 80 °C and re-injection at about 24 °C;
primary flow about 145 m³/h and secondary about 162 m³/h, heated from 24 to 74 °C; about 9.9 MW
thermal; ESP about 126 kW and injection pump about 196 kW. It looks generated by the legacy model,
so use it as a sanity target, not as measurements.
