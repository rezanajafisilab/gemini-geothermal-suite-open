# 03. Component equations and operating boundaries

Internal units: W, kg/s, m3/s, Pa, J/kg/K and seconds. Temperatures are C except absolute K
in thermodynamic bounds. Q_c is positive heat removed. Check input validity before division.
Every limited duty must yield an unmet-duty/status record; do not just overwrite the request.

## Common water, pump and heat-exchanger physics

```text
Q_c = mdot_chw * cp_chw * (T_return - T_supply)
mdot_required = Q_request / [cp_chw * (T_return - T_target)]
T_supply_actual = T_return - Q_delivered/(mdot_chw*cp_chw)
P_pump = Vdot * dp / eta_total
dp = K_flow * Vdot**2                   # optional fitted hydraulic law
E_day_MWh = P_day_MW * 24
```

Require a positive return-to-target difference for a positive cooling request. At zero flow,
deliver zero transfer; do not report the target as achieved. A calculated required flow is
not a guarantee that a real pump can deliver it. K_flow has Pa/(m3/s)^2 units. Secondary-loop
flow is independent of the challenge's per-doublet cap. Use the specified 0.70 for challenge
well pumping; secondary total efficiency is a separate sourced/assumed setting.

For a counterflow exchanger with separately specified fluid properties:

```text
C_h = mdot_h*cp_h; C_c = mdot_c*cp_c
Cmin = min(C_h,C_c); Cr = Cmin/max(C_h,C_c); NTU = UA/Cmin
epsilon = [1-exp(-NTU*(1-Cr))]/[1-Cr*exp(-NTU*(1-Cr))]
epsilon(Cr=1) = NTU/(1+NTU)
Q = epsilon*Cmin*(Th_in-Tc_in)
Th_out = Th_in-Q/C_h; Tc_out = Tc_in+Q/C_c
Th_in-Tc_out >= approach; Th_out-Tc_in >= approach
```

UA is W/K. Identify the genuinely hot stream first and map ports back correctly; energy
balance alone does not catch a wrong heat-flow direction. Handle zero flow, UA=0 and Cr
near 1 with stable branches. If a controlled duty is requested, cap at feasible UA and both
terminal approaches. A generator-duty heat exchanger never receives an automatic 40 K budget.

## Electric compressor: both condenser types

```text
Q_mech = min(Q_remaining, Q_available,
             mdot_chw*cp_chw*max(0,T_return-T_target))
Q_unmet = Q_remaining-Q_mech
P_comp = Q_mech/COP_e
Q_cond_core = Q_mech+P_comp
```

The last equation assumes hermetic compressor input reaches the condenser; make any other
heat split explicit. Zero demand has a separate off/standby path. Do not double-count a
fan/pump already inside a package COP. Record `cop_boundary` as compressor-only or package.

The deadline model is screening constant COP with a stated applicability envelope,
configurable capacity and explicit auxiliaries. It must reject/flag unsupported operating
points rather than silently extrapolate. BENCHMARKS defaults apply only to that named fixture.

Temperature/part-load maps are an optional later model level, fitted to one machine with
reference conditions. Do not build or invent maps for the deadline. The following equations
remain a reference for that later extension. Both model levels must be labelled in results.

An EIR-family implementation can use:

```text
F(Ts,Tk) = a+b*Ts+c*Ts**2+d*Tk+e*Tk**2+f*Ts*Tk
Q_available = Q_rated*F_capacity(Ts,Tk)
r = Q_mech/Q_available
r_on = max(r,r_min); u = min(1,r/r_min)  # 0<r_min<=1; explicit off branch
F_PLR(r_on) = a0+a1*r_on+a2*r_on**2
P_comp = Q_available/COP_ref * F_EIR(Ts,Tk)*F_PLR(r_on)*u
```

For water cooling Tk is the entering/leaving condenser-water temperature used in the data;
for air cooling it is usually entering outdoor dry bulb. Do not mix curve definitions.
F_PLR=r gives constant-COP unloading. This simplified cycling treatment excludes startup
and false-loading penalties; add only with documented data. Reject negative factors and
out-of-domain points as model limits. Q_available=0 must not cause a divide-by-zero.

Fit full-load capacity/Q_rated and power*COP_ref/Q_available first, then part-load power.
Use NumPy least squares, normalize at reference, and hold out temperature/load points for
validation. Supplier capacity and electricity maps must describe the same unit and conditions.

Optional screening bound:

```text
COP_Carnot = T_evap_K/(T_cond_K-T_evap_K)
COP_e = eta_II*COP_Carnot
```

Use refrigerant-side temperatures with stated evaporator/condenser approaches, positive lift
and 0<eta_II<1. Do not force an infinite COP at low lift; switch to a valid free-cooling mode
or report the compressor outside its envelope. The bound is not a calibrated machine map.

## Water-cooled compression and cooling tower

```text
T_cw_out = T_cw_in + Q_cond_core/(mdot_cw*cp_cw)
T_cw_in_estimate = T_wetbulb + approach_tower
P_water = P_comp + P_tower_fan + P_cw_pump + P_chw_pump + P_free_loop
```

The wet-bulb expression is a first estimate, not proof of available tower duty. Check tower
capacity and circulation flow; use a bounded iteration if chiller and tower temperatures
depend on each other. Add a fan law, such as P=P_design*(speed/speed_design)^3, only with a
declared control/flow relationship; do not replace a manufacturer's fan/control map blindly.

Minimum tower heat-rejection, fan/pump and water accounting is required for M2/M4 even
when optional M3 free cooling is deferred. Hourly wet bulb comes from 10. Detailed water
chemistry is excluded; use the effective-treatment assumption and user settings in 11.

Water inventory for a time interval:

```text
V_evap = latent_fraction*Q_tower*dt/(rho_water*h_fg)
V_blowdown = V_evap/(cycles-1) - V_drift
V_makeup = V_evap+V_blowdown+V_drift
```

Require cycles>1, latent_fraction between 0 and 1, and non-negative consistent losses.
Negative blowdown indicates inconsistent inputs; do not silently clip it. If drift=0,
makeup=evap*cycles/(cycles-1). The benchmark uses h_fg=2.45e6 J/kg, latent fraction 0.8,
five cycles, no drift/leaks. Treatment and disposal are separate ledger items unless a
labelled composite water charge includes them. The current user-input contract and
supply-limit check are in 11; the constant latent fraction remains an explicit screening
approximation even when hourly weather is available.

## Waterside free cooling: an optional mode of option 1

Use an isolation exchanger between the cold sink/tower water and the clean chilled loop.

```text
Q_free_available = epsilon*Cmin*max(0,T_return-T_sink_in)
Q_free = min(Q_request,Q_free_available,Q_free_rated)
Q_mech_request = Q_request-Q_free
```

Then check actual exchanger outlet temperatures, both approaches and flows. Full free cooling
requires enough duty AND a sufficiently cold sink. A necessary simplified temperature test is
T_wetbulb+approach_tower+approach_HX <= T_supply_target. A warmer sink can still precool the
return if the exchanger permits it. Model series precooling followed by mechanical trim, or
document a parallel arrangement with explicit branch flows and mixing. Do not cool the same
load twice. Include free-mode fans, pumps and tower water. Hot geothermal brine is not a cold
sink. Retain full mechanical and tower design capacity for unavailable free cooling.

Free mode is optional M3 work, disabled by default for the deadline delivery until its
capacity, temperature, water and auxiliary tests pass. A valid aligned hourly weather/sink
scenario is required when enabled. The bundled KNMI scenario in 10 supplies such an input
scenario, not proof of the actual site or future weather. Do not automatically enable free
cooling merely because CSVs exist. A percentage energy-share case stays a regression or
hypothetical sensitivity calculation, never a weather-predicted result.

## Air-cooled compression

```text
Tk = T_outdoor_drybulb                       # when that is the fitted curve input
P_air_fan = fan_ratio*Q_cond_core             # screening proxy only
P_air = P_comp+P_air_fan+P_chw_pump
```

No evaporative tower makeup is assigned to this configuration. A sealed circuit may still
need filling/leak makeup. For the deadline use constant performance inside a stated
ambient/chilled-water envelope. If a sourced derating map is later available, evaluate
capacity and electricity at the same ambient point.
The benchmark COP 4 excludes fans; an actual package COP may include them. Multiple modules
require per-module sizing/staging/costs; 10 MW nominal is not a guarantee at hot conditions.

## Single-effect absorption and electric backup

Three distinct circuits: clean generator hot water, chilled water and absorber/condenser
cooling water. A separating geothermal heat exchanger supplies the hot loop.

```text
Q_abs = min(Q_request,Q_abs_available,COP_th*Q_heat_allocated,Q_abs_flow_limit)
Q_gen = Q_abs/COP_th
P_abs_internal = internal_ratio*Q_abs
Q_abs_reject = Q_abs+Q_gen+P_abs_internal
T_hot_out = T_hot_in-Q_gen/(mdot_hot*cp_hot)
T_cw_out = T_cw_in+Q_abs_reject/(mdot_cw*cp_cw)
Q_backup_request = Q_request-Q_abs
```

Derive Q_abs_flow_limit from all relevant circuit flow/temperature limits. Check hot-loop
return, generator temperature, sink capacity and both separating-HX approaches. Do not use
the generator inlet temperature alone to declare feasibility. For the deadline, use bounded
constant thermal COP/capacity with an explicit hot/sink/chilled-water/flow envelope and
source allocation. A constant 0.7 is a screening choice, not validated at 20 C supply or at
the actual wellhead/HX temperature. The cited CEA reference is at 90/38/7 C. Supplier maps
are a later extension; interpolate only inside their documented domain when available.

The backup is the same electric component as options 1/2. In the comparison fixture it has
10 MW capacity despite a 4 MW absorber. Complete outage backup is a design setting; it does
not imply N+1 or hourly peak compliance. Keep absorber electricity plus all backup and
external hot/chilled/condenser pumps and heat rejection in the inventory.

Plausibility bound using representative absolute internal temperatures:

```text
COP_th_reversible = [TE/(TA-TE)]*[1-TA/TG], with TG>TA>TE
```

This is a reversible bound, not a way to obtain a supplier rating. Do not silently clamp a
bad empirical prediction to this bound and call it validated.

## Auxiliary heat routing and closure

Every pump/fan power has one electricity owner and an explicit heat destination/fraction.
Pump heat entering the chilled circuit increases the plant cooling duty; power entering the
hot/condenser circuit changes its duty. Fan heat usually reaches ambient. Account for heat
to ambient separately if it does not enter the water loop. Iterate these effects if needed.
The report fixture deliberately omits external auxiliary heat feedback and must retain that
label; full-physics mode must close the complete boundary to the required tolerance.

## Scalar and vectorised implementation

Use the same equations in a pure NumPy numerical kernel for scalar and batch calls. GEMINI
StaticModel wrappers adapt scalar units and replace self.output snapshots; they do not
implement a separate set of physics or carry thermal age between calls. The batch accepts
365-day or (365,24) arrays as agreed in 02/10. Do not loop through thousands of model objects,
open files, call wells or format strings for every successful hour in the numerical core.
Mask invalid/limited points explicitly and preserve useful diagnostics. Benchmark as in 08.
Keep brine cp sourced from Rules=3990; secondary water properties remain separate settings.

## Implemented constant-COP closure (D018)

The shared kernel uses net delivered service q and factor f=1+r_chw*h_chw. Evaporator
duty is f*q, rated evaporator capacity limits f*q, and compressor input is f*q/COP.
Absorption generator input is f*q_abs/COP_th; internal power is r_internal*f*q_abs.
CW-pump power is r_cw*core_rejection. Actual tower duty includes h_cw*CW-pump power;
tower fan is r_fan*actual_tower_duty. Heat fractions default to 1 for chilled/CW pumps.
The dedicated hot-loop pump and fans reject heat to ambient in this explicit screening
installation assumption. Unrouted pump fractions also go to ambient. The full returned
boundary closes q_service+Q_generator+P_all=Q_tower+Q_air+P_aux_to_ambient.
This is algebraic for the linear proxies; no iterative thermal state is introduced.
The report fixture sets external pump heat feedback to zero expressly and is separate.

Generator HX has fixed controlled clean hot_supply_c and actual hot-loop heat capacity Ch.
With G=epsilon*Cmin, clean HX inlet is hot_supply-Qgen/Ch. Its finite-UA duty bound is
Qgen <= G*(wellhead-hot_supply)/(1-G/Ch); at G=Ch the allocated heat cap remains the bound.
Also enforce both HX pinches, actual brine-return floor, clean hot-return floor and explicit
heat allocation. No new 40 K budget is granted. Tests cover zero/very-large UA and near Cr=1.

Wet absorption and backup share one tower capacity/flow/makeup/disposal budget. Tower
circulation and maximum return temperature cap heat rejection in addition to nameplate.
Absorption-first is a declared screening policy; it does not optimise whole-plant service
or economics under a tight shared sink. Such cases report unmet cold truthfully; Reza may
select a different allocation at joint M5. Constant approaches and envelope limits remain
analyst assumptions, not manufacturer maps. No free-cooling savings are predicted.

The pure-water wet-tower baseline has no freeze/bypass control. At an estimated tower inlet
at or below 0 C, wet rejection is unavailable and SINK_FREEZE_RISK is reported (D021).
No weather value or sink temperature is repaired to conceal that unsupported point.
