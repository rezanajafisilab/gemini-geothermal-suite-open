// Writes the workbench fixtures (src/fixtures/{workbench,catalogue,gemini-run,sensitivity,trace,evidence}.json):
// FIXTURE DATA for working on the tabs without the Python server. Every number is made up but
// consistent: the A1 plant uses the GEMINI operating point the team quotes (flow 195.5 m³/h,
// wellhead 86 °C, heat exchanger 9.25 MW, heat pump 4.55 MW at COP 4.29 …), the year's daily
// values add up to the months and the months to the year, and the cost lines add up to the
// LCOH and LCOC. Deterministic (seeded); rerun after changing it:
//
//   node scripts/make-workbench-fixtures.mjs
//
// The tabs read these only in fixture mode (see src/workbench/api.ts).

import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "fixtures");
const MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const DAYS = 365;
const HOURS = 8760;

// ------------------------------------------------------------------ helpers
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(20261029);
const gauss = () => {
  const u = Math.max(rand(), 1e-12);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rand());
};
const round = (v, d = 2) => Math.round(v * 10 ** d) / 10 ** d;
const sum = (a) => a.reduce((x, y) => x + y, 0);
const gwh = (mwDaily) => (sum(mwDaily) * 24) / 1000;
const scaleTo = (a, totalGwh) => {
  const k = totalGwh / gwh(a);
  return a.map((v) => v * k);
};
/** Round daily MW to 4 decimals and put the residual on the largest day, so the year is exact. */
function exact(daily, totalGwh) {
  const r = daily.map((v) => round(v, 4));
  if (totalGwh == null) return r;
  const residualMw = ((totalGwh - gwh(r)) * 1000) / 24;
  if (Math.abs(residualMw) > 1e-9 && r.some((v) => v > 0)) {
    const i = r.indexOf(Math.max(...r));
    r[i] = round(r[i] + residualMw, 4);
  }
  return r;
}
function monthly(daily) {
  const out = [];
  let d = 0;
  for (const n of MONTH_DAYS) {
    out.push(round((sum(daily.slice(d, d + n)) * 24) / 1000, 4));
    d += n;
  }
  return out;
}
/** Largest cap with sum(min(d, cap)) = target GWh (bisection). */
function fitCap(demand, target) {
  let lo = 0;
  let hi = Math.max(...demand);
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) / 2;
    if (gwh(demand.map((v) => Math.min(v, mid))) < target) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}
const annuity = (r, n) => r / (1 - (1 + r) ** -n);

// ------------------------------------------------------------------ the example year
// Outdoor temperature with day-to-day weather; heat follows degree days, cold the warm days.
const tout = [];
let e = 0;
for (let d = 0; d < DAYS; d++) {
  e = 0.78 * e + gauss() * 1.25;
  tout.push(10.4 - 7.4 * Math.cos((2 * Math.PI * (d - 19)) / DAYS) + e);
}
const HEAT_GWH = 61.76;
const COLD_GWH = 13.674;
let heatDemand = scaleTo(tout.map((t) => 2.05 + Math.max(0, 16.5 - t)), HEAT_GWH);
let coldDemand = scaleTo(tout.map((t) => 0.34 + 0.36 * Math.max(0, t - 12.5) ** 1.15), COLD_GWH);

// A1: the heat exchanger takes the base, the heat pump the rest (boiler 0 GWh).
const A1_GEO = 52.45;
const A1_HP = 9.31;
const HP_CAP = 4.55;
let geoCap = fitCap(heatDemand, A1_GEO);
// Clip the coldest days so the heat exchanger and heat pump cover every day, then refit.
for (let i = 0; i < 30 && Math.max(...heatDemand) > geoCap + HP_CAP - 0.05; i++) {
  heatDemand = scaleTo(heatDemand.map((v) => Math.min(v, geoCap + HP_CAP - 0.08)), HEAT_GWH);
  geoCap = fitCap(heatDemand, A1_GEO);
}
heatDemand = exact(heatDemand, HEAT_GWH);
const a1Geo = exact(scaleTo(heatDemand.map((v) => Math.min(v, geoCap)), A1_GEO), A1_GEO);
const a1Hp = exact(heatDemand.map((v, i) => Math.max(0, v - a1Geo[i])), A1_HP);
const a1Boiler = heatDemand.map(() => 0);

// Cold: the absorption chiller runs on brine heat the network doesn't need (spring to autumn), at
// most 2 MW; electric chillers take the rest (the winter base and the summer peaks). The doublet
// carries flow × (wellhead − reinjection) of heat; the network takes the heat exchanger's share
// and the heat pump's source heat.
const A1_ABS = 7.3154;
const A1_CHILL = 6.3586;
const ABS_MW = 2.0;
const ABS_COP = 0.7;
const CHILL_CAP = 2.5;
const RHO_C = 4.19; // MJ/(m³·K)
const doubletMw = (flow, wellhead, reinjection) => (flow / 3600) * RHO_C * (wellhead - reinjection);
const absRoom = (geo, hp, carried, cop, hpCop) => geo.map((g, i) => Math.min(ABS_MW, Math.max(0, (carried - g - hp[i] * (1 - 1 / hpCop)) * cop)));
/** The level L (MW) the absorption chiller runs at most, so it gives `target` GWh. */
function fitLevel(demand, room, target) {
  let lo = 0;
  let hi = ABS_MW;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (gwh(demand.map((v, j) => Math.min(v, room[j], mid))) < target) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}
const a1Room = absRoom(a1Geo, a1Hp, doubletMw(195.5, 86, 30), ABS_COP, 4.29);
let absLevel = ABS_MW;
// Clip the hottest days so the absorption chiller and the chillers cover every day, then refit.
for (let i = 0; i < 40; i++) {
  coldDemand = scaleTo(coldDemand.map((v) => Math.min(v, absLevel + CHILL_CAP - 0.08)), COLD_GWH);
  absLevel = fitLevel(coldDemand, a1Room, A1_ABS);
  const chillPeak = Math.max(...coldDemand.map((v, j) => v - Math.min(v, a1Room[j], absLevel)));
  if (chillPeak <= CHILL_CAP - 0.05) break;
}
coldDemand = exact(coldDemand, COLD_GWH);
absLevel = fitLevel(coldDemand, a1Room, A1_ABS);
if (absLevel > ABS_MW - 0.001) throw new Error("the absorption chiller can't give A1_ABS: make the summer cold peakier");
const a1Abs = exact(scaleTo(coldDemand.map((v, i) => Math.min(v, a1Room[i], absLevel)), A1_ABS), A1_ABS);
const a1Chill = exact(coldDemand.map((v, i) => Math.max(0, v - a1Abs[i])), A1_CHILL);
if (Math.max(...a1Chill) > CHILL_CAP) throw new Error("the chillers can't cover A1's cold peaks");

/** Dispatch a heat demand over units in merit order, each limited to its daily MW. */
function dispatch(demand, caps) {
  const rest = [...demand];
  const out = {};
  for (const [key, cap] of caps) {
    out[key] = rest.map((v) => Math.min(v, cap));
    out[key].forEach((v, i) => (rest[i] -= v));
  }
  return { ...Object.fromEntries(Object.entries(out).map(([k, v]) => [k, exact(v)])), unmet: rest };
}

// ------------------------------------------------------------------ assumptions and costs
const DEFAULTS = {
  gas_eur_per_mwh: 38,
  electricity_eur_per_mwh: 90,
  discount_rate: 0.05,
  lifetime_years: 30,
  fixed_opex_share: 0.02,
  gas_t_co2_per_mwh: 0.202,
  grid_t_co2_per_mwh: 0.425,
  carbon_eur_per_t: 80,
  capex_meur: { well_base: 2.0, well_per_km: 3.0, hex: 0.06, heat_pump: 0.5, boiler: 0.12, absorption: 0.4, chiller: 0.25 },
};
const ASSUMPTIONS = {
  ...structuredClone(DEFAULTS),
  defaults: structuredClone(DEFAULTS),
  sources: {
    gas_eur_per_mwh: "Fixture: toy-model default (TTF forward plus network tariff, team estimate)",
    electricity_eur_per_mwh: "Fixture: toy-model default (Dutch business tariff, team estimate)",
    discount_rate: "Fixture: toy-model default, real terms",
    lifetime_years: "Fixture: toy-model default for wells and surface plant",
    fixed_opex_share: "Fixture: share of the capital spent on maintenance each year",
    gas_t_co2_per_mwh: "Fixture: natural gas, combustion only",
    grid_t_co2_per_mwh: "Fixture: Dutch grid average, team estimate",
    carbon_eur_per_t: "Fixture: EU ETS price, team estimate",
    capex_meur: "Fixture: toy-model unit costs per well, per km of well and per MW",
  },
  notes: [
    "Fixture data for the tabs, not a real run.",
    "The toy model's cost lines end with a small calibration line so A1, A2 and A4 match the agent's quoted costs.",
    "Carbon is priced into the gas and electricity lines.",
  ],
};
const A = annuity(DEFAULTS.discount_rate, DEFAULTS.lifetime_years);
const ELEC = DEFAULTS.electricity_eur_per_mwh + DEFAULTS.grid_t_co2_per_mwh * DEFAULTS.carbon_eur_per_t;
const GAS = DEFAULTS.gas_eur_per_mwh + DEFAULTS.gas_t_co2_per_mwh * DEFAULTS.carbon_eur_per_t;
const BOILER_EFF = 0.92;
const CHILLER_COP = 4.5;
const C = DEFAULTS.capex_meur;

/** Cost lines that add up to the target €/MWh (a calibration line takes the remainder). */
function lines(items, deliveredGwh, target) {
  const mwh = deliveredGwh * 1000;
  const out = items
    .filter((x) => x.meur > 0)
    .map((x) => ({ item: x.item, kind: x.kind, meur_per_year: round(x.meur, 4), eur_per_mwh: round((x.meur * 1e6) / mwh, 2) }));
  const rest = round(target - sum(out.map((l) => l.eur_per_mwh)), 2);
  if (Math.abs(rest) > 0.004) out.push({ item: "Calibration (toy model)", kind: "calibration", meur_per_year: round((rest * mwh) / 1e6, 4), eur_per_mwh: rest });
  return out;
}

function capexItems(p) {
  const items = [];
  if (p.depth_m > 0) items.push({ item: `Wells (2 × ${p.depth_m / 1000} km)`, size: 2, unit: "wells", meur_per_unit: C.well_base + (C.well_per_km * p.depth_m) / 1000, meur: 2 * (C.well_base + (C.well_per_km * p.depth_m) / 1000) });
  const per = { heat_exchanger: ["Heat exchanger", C.hex], heat_pump: ["Heat pump", C.heat_pump], boiler: ["Gas boiler", C.boiler], absorption: ["Absorption chiller", C.absorption], chillers: ["Electric chillers", C.chiller] };
  for (const [k, [label, unitCost]] of Object.entries(per)) {
    const mw = p.sizes_mw[k];
    if (mw > 0) items.push({ item: label, size: mw, unit: "MW", meur_per_unit: unitCost, meur: mw * unitCost });
  }
  return items.map((x) => ({ ...x, meur_per_unit: round(x.meur_per_unit, 4), meur: round(x.meur, 4) }));
}

// ------------------------------------------------------------------ checks (the verifier's names)
function checks(d) {
  const { plant: p, year: y } = d;
  const heatSum = sum(Object.values(y.heat_split_gwh));
  const coldSum = sum(Object.values(y.cool_split_gwh));
  const list = [
    ["Heat adds up", Math.abs(heatSum - y.heat_delivered_gwh) <= 0.02, `${heatSum.toFixed(1)} GWh from the sources, ${y.heat_delivered_gwh.toFixed(1)} GWh delivered`],
    ["Cold adds up", Math.abs(coldSum - y.cool_delivered_gwh) <= 0.02, `${coldSum.toFixed(1)} GWh from the sources, ${y.cool_delivered_gwh.toFixed(1)} GWh delivered`],
    ["No more heat than demand", y.heat_delivered_gwh <= y.heat_demand_gwh + 0.02, `${y.heat_delivered_gwh.toFixed(1)} of ${y.heat_demand_gwh.toFixed(1)} GWh`],
    ["No more cold than demand", y.cool_delivered_gwh <= y.cool_demand_gwh + 0.02, `${y.cool_delivered_gwh.toFixed(1)} of ${y.cool_demand_gwh.toFixed(1)} GWh`],
  ];
  if (p.heat_pump) list.push(["Heat pump COP below the Carnot limit", p.cop < p.carnot_cop, `COP ${p.cop.toFixed(1)} < ${p.carnot_cop.toFixed(1)} at ${p.reinjection_c} °C in and 70 °C out`]);
  if (p.wellhead_c > 15) {
    list.push(["Brine cools along its path", p.wellhead_c >= p.hex_outlet_c && p.hex_outlet_c >= p.reinjection_c, `${p.wellhead_c} → ${p.hex_outlet_c} → ${p.reinjection_c} °C`]);
    list.push(["Reinjection at or above 30 °C", p.reinjection_c >= 29.95, `${p.reinjection_c} °C`]);
  }
  if (p.sizes_mw.heat_exchanger > 0) list.push(["No temperature cross in the heat exchanger", p.wellhead_c >= 70 && p.hex_outlet_c >= 40, `brine ${p.wellhead_c} → ${p.hex_outlet_c} °C, network 40 → 70 °C`]);
  const units = [
    ["Heat exchanger", y.heat_split_gwh.geo, p.sizes_mw.heat_exchanger],
    ["Heat pump", y.heat_split_gwh.hp, p.sizes_mw.heat_pump],
    ["Gas boiler", y.heat_split_gwh.boiler, p.sizes_mw.boiler],
    ["Absorption chiller", y.cool_split_gwh.abs, p.sizes_mw.absorption],
    ["Electric chillers", y.cool_split_gwh.chill, p.sizes_mw.chillers],
  ].filter((u) => u[2] > 0);
  const worst = units.reduce((a, b) => (b[1] / b[2] > a[1] / a[2] ? b : a));
  list.push(["No unit gives more than its size allows", units.every((u) => u[1] <= (u[2] * HOURS) / 1000 + 0.02), `${worst[0]}: ${worst[1].toFixed(1)} of ${((worst[2] * HOURS) / 1000).toFixed(1)} GWh possible at ${worst[2]} MW`]);
  if (p.heat_pump && y.heat_split_gwh.hp > 0) {
    const el = y.heat_split_gwh.hp / p.cop;
    list.push(["Heat pump heat = electricity × COP", true, `${y.heat_split_gwh.hp.toFixed(1)} GWh vs ${el.toFixed(1)} GWh × ${p.cop.toFixed(1)}`]);
  }
  list.push(["Heating supply above return", true, "70/40 °C"]);
  list.push(["Cooling return above supply", true, "6/12 °C"]);
  if (p.absorption) list.push(["Absorption chiller driven hot enough", p.wellhead_c >= 80, `${p.wellhead_c} °C ${p.wellhead_c >= 80 ? "≥" : "<"} 80 °C`]);
  list.push(["Cost is finite", d.economics.lcoh < 1000, `${d.economics.lcoh} EUR/MWh`]);
  list.push([`Heat coverage at least 95%`, y.heat_coverage >= 0.95, `${(y.heat_coverage * 100).toFixed(1)}%`, true]);
  list.push([`Cold coverage at least 95%`, y.cool_coverage >= 0.95, `${(y.cool_coverage * 100).toFixed(1)}%`, true]);
  return list.map(([name, passed, detail, requirement]) => ({ name, passed: !!passed, detail, ...(requirement ? { requirement: true } : {}) }));
}

// ------------------------------------------------------------------ one design
function year({ heat, cool }) {
  const heatDelivered = round(gwh(heat.geo) + gwh(heat.hp) + gwh(heat.boiler), 4);
  const coolDelivered = round(gwh(cool.abs) + gwh(cool.chill), 4);
  const split = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, round(gwh(v), 4)]));
  return {
    heat_demand_gwh: HEAT_GWH,
    cool_demand_gwh: COLD_GWH,
    heat_delivered_gwh: heatDelivered,
    cool_delivered_gwh: coolDelivered,
    heat_coverage: round(heatDelivered / HEAT_GWH, 4),
    cool_coverage: round(coolDelivered / COLD_GWH, 4),
    heat_split_gwh: split({ geo: heat.geo, hp: heat.hp, boiler: heat.boiler }),
    cool_split_gwh: split({ abs: cool.abs, chill: cool.chill }),
    peak_heat_mw: round(Math.max(...heatDemand), 2),
    peak_cool_mw: round(Math.max(...coldDemand), 2),
    full_load_hours: 0,
    monthly_gwh: {
      heat: { demand: monthly(heatDemand), geo: monthly(heat.geo), hp: monthly(heat.hp), boiler: monthly(heat.boiler) },
      cool: { demand: monthly(coldDemand), abs: monthly(cool.abs), chill: monthly(cool.chill) },
    },
    daily_mw: {
      heat: { demand: heatDemand, geo: heat.geo, hp: heat.hp, boiler: heat.boiler },
      cool: { demand: coldDemand, abs: cool.abs, chill: cool.chill },
    },
  };
}

function economics(p, y, { lcoh, lcoc, pumpsGwh, absAuxGwh, co2Target }) {
  const items = capexItems(p);
  const capex = round(sum(items.map((x) => x.meur)), 2);
  const heatCapex = items.filter((x) => !/chiller/i.test(x.item));
  const coldCapex = items.filter((x) => /chiller/i.test(x.item));
  const hpElecGwh = p.heat_pump ? y.heat_split_gwh.hp / p.cop : 0;
  const gasGwh = y.heat_split_gwh.boiler / BOILER_EFF;
  const chillElecGwh = y.cool_split_gwh.chill / CHILLER_COP;
  const heatLines = lines(
    [
      ...heatCapex.map((x) => ({ item: x.item.replace(/ \(.*/, ""), kind: "capital", meur: x.meur * A })),
      { item: "Maintenance", kind: "fixed", meur: sum(heatCapex.map((x) => x.meur)) * DEFAULTS.fixed_opex_share },
      { item: "Electricity: well pumps", kind: "electricity", meur: (pumpsGwh * ELEC) / 1000 },
      { item: "Electricity: heat pump", kind: "electricity", meur: (hpElecGwh * ELEC) / 1000 },
      { item: "Gas", kind: "gas", meur: (gasGwh * GAS) / 1000 },
      { item: "Heat network", kind: "network", meur: (y.heat_delivered_gwh * 2.0) / 1000 },
    ],
    y.heat_delivered_gwh,
    lcoh,
  );
  const coldLines = lines(
    [
      ...coldCapex.map((x) => ({ item: x.item, kind: "capital", meur: x.meur * A })),
      { item: "Maintenance", kind: "fixed", meur: sum(coldCapex.map((x) => x.meur)) * DEFAULTS.fixed_opex_share },
      { item: "Electricity: chillers", kind: "electricity", meur: (chillElecGwh * ELEC) / 1000 },
      { item: "Electricity: absorption pumps and cooling tower", kind: "electricity", meur: (absAuxGwh * ELEC) / 1000 },
      { item: "Cooling tower and water", kind: "fixed", meur: p.sizes_mw.absorption * 0.025 },
      { item: "Cold network", kind: "network", meur: (y.cool_delivered_gwh * 26.0) / 1000 },
    ],
    y.cool_delivered_gwh,
    lcoc,
  );
  const elecGwh = pumpsGwh + hpElecGwh + chillElecGwh + absAuxGwh;
  const co2 = co2Target ?? round((elecGwh * DEFAULTS.grid_t_co2_per_mwh + gasGwh * DEFAULTS.gas_t_co2_per_mwh) * 1000, 0);
  const opex = (elecGwh * ELEC + gasGwh * GAS) / 1000 + capex * DEFAULTS.fixed_opex_share;
  return { lcoh, lcoc, capex_meur: capex, co2_t_per_year: co2, opex, heatLines, coldLines, items };
}

// ------------------------------------------------------------------ GEMINI projects
function trajectory(depth) {
  return [
    { MD: 0, TVD: 0, ID: 0.2 },
    { MD: 600, TVD: 600, ID: 0.2 },
    { MD: depth, TVD: depth, ID: 0.16 },
  ];
}
function project(p) {
  if (!(p.depth_m > 0)) return null;
  const components = {
    producer_well: {
      type: "producer_well",
      parameters: { reservoir_pressure_bar: round(p.depth_m * 0.1, 0), productivity_index_m3h_per_bar: p.productivity_index_m3h_per_bar, ambient_temperature_c: 10, trajectory_table: trajectory(p.depth_m), esp_depth_m: 550, esp_freq_hz: 50 },
    },
  };
  const boundary = [
    { component: "producer_well", key: "wellhead_pressure", value: 3.0 },
    { component: "producer_well", key: "wellhead_temperature", value: p.wellhead_c },
  ];
  const connections = [];
  let last = "producer_well";
  let lastPorts = [["flow_rate_m3s", "primary_flow_rate"], ["pressure_out", "pressure_in"], ["temperature_out", "primary_temperature_in"]];
  if (p.sizes_mw.heat_exchanger > 0) {
    components.heat_exchanger = { type: "heat_exchanger", parameters: { flow_resistance: 0, flow_configuration: "counter", heat_transfer_coefficient: p.hex_ua_kw_per_k * 1000 } };
    boundary.push({ component: "heat_exchanger", key: "secondary_temperature_in", value: 40.0 });
    boundary.push({ component: "heat_exchanger", key: "secondary_flow_rate", value: round(p.sizes_mw.heat_exchanger / (4.19 * 30), 4) });
    connections.push({ predecessor: last, successor: "heat_exchanger", ports: lastPorts });
    last = "heat_exchanger";
    lastPorts = [["pressure_out", "source_pressure_in"], ["primary_flow_rate", "source_flow_rate"], ["primary_temperature_out", "source_temperature_in"]];
  } else {
    lastPorts = [["pressure_out", "source_pressure_in"], ["flow_rate_m3s", "source_flow_rate"], ["temperature_out", "source_temperature_in"]];
  }
  if (p.heat_pump) {
    components.heatpump = { type: "heatpump", parameters: { mode: "carnot", eta_carnot: 0.5, rho_s: 1000, rho_h: 1000 } };
    boundary.push({ component: "heatpump", key: "hot_temperature_out", value: 70.0 });
    boundary.push({ component: "heatpump", key: "source_temperature_out", value: p.reinjection_c });
    connections.push({ predecessor: last, successor: "heatpump", ports: lastPorts });
    last = "heatpump";
    lastPorts = [["source_flow_rate_m3h", "flow_rate"], ["source_temperature_out", "wellhead_temperature"], ["source_pressure_out", "pressure_in"]];
  } else {
    lastPorts = [["primary_flow_rate", "flow_rate"], ["primary_temperature_out", "wellhead_temperature"], ["pressure_out", "pressure_in"]];
  }
  if (p.boiler) {
    components.boiler = { type: "boiler", parameters: { caloric_value: 50000000, efficiency_factor: BOILER_EFF, gas_emission_factor: 56.6 } };
    boundary.push({ component: "boiler", key: "temperature_in", value: 68.0 });
  }
  components.injector_well = {
    type: "injector_well",
    parameters: { reservoir_pressure_bar: round(p.depth_m * 0.1 - 10, 0), productivity_index_m3h_per_bar: p.productivity_index_m3h_per_bar, trajectory_table: trajectory(p.depth_m), injector_pump: { efficiency_factor: 0.8, electricity_emission_factor: DEFAULTS.grid_t_co2_per_mwh } },
  };
  connections.push({ predecessor: last, successor: "injector_well", ports: lastPorts });
  return { _description: "Fixture: the plant as GEMINI's solver ran it (made up for the tabs).", components, boundary_inputs: boundary, connections };
}

// ------------------------------------------------------------------ graphs
const n = (id, type, label, solver, values, units) => ({ id, type, label, solver, values, units });
const ed = (id, source, target, kind, mw, temperature_c, label) => ({ id, source, target, kind, mw, temperature_c, label });
const MW = "MW";

function graph(p, y, proj) {
  const nodes = [];
  const edges = [];
  const hpElecMw = p.heat_pump ? round(p.sizes_mw.heat_pump / p.cop, 2) : 0;
  if (p.depth_m > 0) {
    nodes.push(n("producer_well", "producer_well", "Producer well", "gemini", { depth_m: p.depth_m, flow_m3h: p.flow_m3h, temperature_out_c: p.wellhead_c, esp_mw: p.esp_mw }, { depth_m: "m", flow_m3h: "m³/h", temperature_out_c: "°C", esp_mw: MW }));
    nodes.push(n("injector_well", "injector_well", "Injector well", "gemini", { temperature_in_c: p.reinjection_c, pump_mw: p.injector_pump_mw }, { temperature_in_c: "°C", pump_mw: MW }));
    nodes.push(n("grid", "grid", "Electricity grid", "dioscuri", { power_mw: round(p.esp_mw + p.injector_pump_mw + hpElecMw + p.sizes_mw.chillers / CHILLER_COP, 2) }, { power_mw: MW }));
    edges.push(ed("e_grid_esp", "grid", "producer_well", "electricity", p.esp_mw, null, `ESP ${p.esp_mw} MW`));
    edges.push(ed("e_grid_inj", "grid", "injector_well", "electricity", p.injector_pump_mw, null, `Injector pump ${p.injector_pump_mw} MW`));
  }
  let brineFrom = "producer_well";
  let brineT = p.wellhead_c;
  if (p.sizes_mw.heat_exchanger > 0) {
    nodes.push(n("heat_exchanger", "heat_exchanger", "Heat exchanger", "gemini", { power_mw: p.sizes_mw.heat_exchanger, ua_kw_per_k: p.hex_ua_kw_per_k, temperature_in_c: p.wellhead_c, temperature_out_c: p.hex_outlet_c }, { power_mw: MW, ua_kw_per_k: "kW/K", temperature_in_c: "°C", temperature_out_c: "°C" }));
    edges.push(ed("e_prod_hex", brineFrom, "heat_exchanger", "brine", null, brineT, `${p.flow_m3h} m³/h at ${brineT} °C`));
    brineFrom = "heat_exchanger";
    brineT = p.hex_outlet_c;
  }
  if (p.heat_pump) {
    nodes.push(n("heatpump", "heatpump", "Heat pump", "gemini", { power_mw: p.sizes_mw.heat_pump, cop: p.cop, carnot_cop: p.carnot_cop, electricity_mw: hpElecMw, source_out_c: p.reinjection_c }, { power_mw: MW, cop: "", carnot_cop: "", electricity_mw: MW, source_out_c: "°C" }));
    edges.push(ed(`e_${brineFrom}_hp`, brineFrom, "heatpump", "brine", null, brineT, `${p.flow_m3h} m³/h at ${brineT} °C`));
    edges.push(ed("e_grid_hp", "grid", "heatpump", "electricity", hpElecMw, null, `${hpElecMw} MW`));
    brineFrom = "heatpump";
    brineT = p.reinjection_c;
  }
  if (p.depth_m > 0) edges.push(ed(`e_${brineFrom}_inj`, brineFrom, "injector_well", "brine", null, brineT, `${p.flow_m3h} m³/h at ${brineT} °C`));
  nodes.push(n("demand_heat", "demand_heat", "Heat demand", "dioscuri", { annual_gwh: y.heat_demand_gwh, peak_mw: y.peak_heat_mw, supply_c: 70, return_c: 40 }, { annual_gwh: "GWh", peak_mw: MW, supply_c: "°C", return_c: "°C" }));
  if (p.sizes_mw.heat_exchanger > 0) edges.push(ed("e_hex_heat", "heat_exchanger", "demand_heat", "network", p.sizes_mw.heat_exchanger, 70, `${p.sizes_mw.heat_exchanger} MW into the network`));
  if (p.heat_pump) edges.push(ed("e_hp_heat", "heatpump", "demand_heat", "network", p.sizes_mw.heat_pump, 70, `${p.sizes_mw.heat_pump} MW at 70 °C`));
  if (p.boiler) {
    nodes.push(n("gas", "gas", "Gas", "dioscuri", { power_mw: round(p.sizes_mw.boiler / BOILER_EFF, 2) }, { power_mw: MW }));
    nodes.push(n("boiler", "boiler", "Gas boiler", "gemini", { power_mw: p.sizes_mw.boiler, efficiency: BOILER_EFF }, { power_mw: MW, efficiency: "" }));
    edges.push(ed("e_gas_boiler", "gas", "boiler", "gas", round(p.sizes_mw.boiler / BOILER_EFF, 2), null, "Gas"));
    edges.push(ed("e_boiler_heat", "boiler", "demand_heat", "network", p.sizes_mw.boiler, 70, `${p.sizes_mw.boiler} MW peak top-up`));
  }
  nodes.push(n("demand_cold", "demand_cold", "Cold demand", "dioscuri", { annual_gwh: y.cool_demand_gwh, peak_mw: y.peak_cool_mw, supply_c: 6, return_c: 12 }, { annual_gwh: "GWh", peak_mw: MW, supply_c: "°C", return_c: "°C" }));
  if (p.absorption) {
    nodes.push(n("absorption", "absorption", "Absorption chiller", "dioscuri", { power_mw: p.sizes_mw.absorption, cop: 0.7, drive_c: p.wellhead_c }, { power_mw: MW, cop: "", drive_c: "°C" }));
    edges.push(ed("e_hex_abs", "heat_exchanger", "absorption", "network", round(p.sizes_mw.absorption / 0.7, 2), p.wellhead_c - 2, "Summer: hot water drives the absorption chiller"));
    edges.push(ed("e_abs_cold", "absorption", "demand_cold", "cold", p.sizes_mw.absorption, 6, `${p.sizes_mw.absorption} MW at 6 °C`));
  }
  if (p.chillers) {
    nodes.push(n("chillers", "chillers", "Electric chillers", "dioscuri", { power_mw: p.sizes_mw.chillers, cop: CHILLER_COP }, { power_mw: MW, cop: "" }));
    edges.push(ed("e_chill_cold", "chillers", "demand_cold", "cold", p.sizes_mw.chillers, 6, `${p.sizes_mw.chillers} MW at 6 °C`));
    if (p.depth_m > 0) edges.push(ed("e_grid_chill", "grid", "chillers", "electricity", round(p.sizes_mw.chillers / CHILLER_COP, 2), null, `${round(p.sizes_mw.chillers / CHILLER_COP, 2)} MW`));
  }
  return { nodes, edges, gemini_project: proj };
}

// ------------------------------------------------------------------ the four designs
const A1_PLANT = {
  depth_m: 2500,
  heat_pump: true,
  boiler: true,
  absorption: true,
  chillers: true,
  reservoir_c: 87,
  wellhead_c: 86,
  hex_outlet_c: 45.4,
  reinjection_c: 30,
  flow_m3h: 195.5,
  esp_mw: 0.195,
  injector_pump_mw: 0.281,
  hex_ua_kw_per_k: 1013,
  cop: 4.29,
  carnot_cop: 8.58,
  transmissivity_dm: 31.5,
  productivity_index_m3h_per_bar: 22.4,
  sizes_mw: { heat_exchanger: 9.25, heat_pump: 4.55, boiler: 0.5, absorption: 2.0, chillers: 2.5 },
};

function build({ id, code, name, origin, parent, chosen, delta, source, plant, heat, cool, econ, provenance }) {
  const y = year({ heat, cool });
  if (plant.sizes_mw.heat_exchanger > 0) y.full_load_hours = Math.round((y.heat_split_gwh.geo * 1000) / plant.sizes_mw.heat_exchanger);
  else if (plant.sizes_mw.heat_pump > 0) y.full_load_hours = Math.round((y.heat_split_gwh.hp * 1000) / plant.sizes_mw.heat_pump);
  else y.full_load_hours = Math.round((y.heat_split_gwh.boiler * 1000) / plant.sizes_mw.boiler);
  const x = economics(plant, y, econ);
  const proj = project(plant);
  const d = {
    id,
    code,
    name,
    origin,
    parent,
    chosen,
    reservoir_delta_c: delta,
    source,
    verified: false,
    checks: [],
    plant,
    year: y,
    economics: {
      lcoh: x.lcoh,
      lcoc: x.lcoc,
      capex_meur: x.capex_meur,
      co2_t_per_year: x.co2_t_per_year,
      reference_co2_t_per_year: 0,
      co2_saving_pct: 0,
      lines: { heat: x.heatLines, cold: x.coldLines },
      capex_items: x.items,
      versus_reference: null,
    },
    graph: graph(plant, y, proj),
    provenance,
  };
  d._opex = x.opex;
  return d;
}

const pumpsGwh = (p, y) => round(((p.esp_mw + p.injector_pump_mw) * y) / 1000, 4);

const a1 = build({
  id: "A1",
  code: "A1",
  name: "Deep doublet with absorption cascade",
  origin: "agent",
  parent: null,
  chosen: true,
  delta: 0,
  source: "gemini+mock",
  plant: A1_PLANT,
  heat: { geo: a1Geo, hp: a1Hp, boiler: a1Boiler },
  cool: { abs: a1Abs, chill: a1Chill },
  econ: { lcoh: 42.4, lcoc: 58, pumpsGwh: pumpsGwh(A1_PLANT, 5670), absAuxGwh: 0.39 },
  provenance: { plant: "gemini", year: "mock", economics: "mock", cooling: "mock" },
});

// A1 with the reservoir 10 °C colder: same equipment, less heat from the brine, absorption
// driven below 80 °C (the verifier flags it).
const wiPlant = structuredClone(A1_PLANT);
Object.assign(wiPlant, { reservoir_c: 77, wellhead_c: 76, hex_outlet_c: 43.2, carnot_cop: 8.58, cop: 4.29 });
const wiHexMw = round((195.5 / 3600) * 4.19 * (76 - 43.2), 2);
const wiHpMw = round((195.5 / 3600) * 4.19 * (43.2 - 30) * (4.29 / 3.29), 2);
const wiHeat = dispatch(heatDemand, [["geo", geoCap * (wiHexMw / 9.25)], ["hp", wiHpMw], ["boiler", 0.5]]);
// Driven at 76 °C the absorption chiller's COP drops to about 0.6.
const wiRoom = absRoom(wiHeat.geo, wiHeat.hp, doubletMw(195.5, 76, 30), 0.6, 4.29);
const wiAbs = exact(coldDemand.map((v, i) => Math.min(v, wiRoom[i], absLevel)));
const wiCool = { abs: wiAbs, ...dispatch(coldDemand.map((v, i) => v - wiAbs[i]), [["chill", CHILL_CAP]]) };
const whatIf = build({
  id: "A1 −10 °C",
  code: "A1",
  name: "Deep doublet with absorption cascade",
  origin: "what_if",
  parent: "A1",
  chosen: false,
  delta: -10,
  source: "gemini+mock",
  plant: wiPlant,
  heat: wiHeat,
  cool: wiCool,
  econ: { lcoh: 47.9, lcoc: 59.6, pumpsGwh: pumpsGwh(A1_PLANT, 5520), absAuxGwh: 0.33 },
  provenance: { plant: "gemini", year: "mock", economics: "mock", cooling: "mock" },
});

// A2: a shallower doublet whose brine only feeds heat pumps; electric chillers for the cold.
const A2_PLANT = {
  depth_m: 1500,
  heat_pump: true,
  boiler: false,
  absorption: false,
  chillers: true,
  reservoir_c: 57,
  wellhead_c: 55,
  hex_outlet_c: 55,
  reinjection_c: 30,
  flow_m3h: 305.6,
  esp_mw: 0.31,
  injector_pump_mw: 0.22,
  hex_ua_kw_per_k: null,
  cop: 3.86,
  carnot_cop: 8.58,
  transmissivity_dm: 48.0,
  productivity_index_m3h_per_bar: 34.0,
  sizes_mw: { heat_exchanger: 0, heat_pump: 12.0, boiler: 0, absorption: 0, chillers: 4.6 },
};
const a2Heat = dispatch(heatDemand, [["geo", 0], ["hp", 12.0], ["boiler", 0]]);
const a2Cool = dispatch(coldDemand, [["abs", 0], ["chill", 4.6]]);
const a2 = build({
  id: "A2",
  code: "A2",
  name: "Shallow doublet with heat pumps",
  origin: "agent",
  parent: null,
  chosen: false,
  delta: 0,
  source: "gemini+mock",
  plant: A2_PLANT,
  heat: a2Heat,
  cool: a2Cool,
  econ: { lcoh: 65.7, lcoc: 59.0, pumpsGwh: pumpsGwh(A2_PLANT, 5100), absAuxGwh: 0 },
  provenance: { plant: "gemini", year: "mock", economics: "mock", cooling: "mock" },
});

// A4: the reference, gas boilers and electric chillers, no well.
const A4_PLANT = {
  depth_m: 0,
  heat_pump: false,
  boiler: true,
  absorption: false,
  chillers: true,
  reservoir_c: 0,
  wellhead_c: 0,
  hex_outlet_c: 0,
  reinjection_c: 0,
  flow_m3h: null,
  esp_mw: null,
  injector_pump_mw: null,
  hex_ua_kw_per_k: null,
  cop: 0,
  carnot_cop: 0,
  transmissivity_dm: null,
  productivity_index_m3h_per_bar: null,
  sizes_mw: { heat_exchanger: 0, heat_pump: 0, boiler: 16.0, absorption: 0, chillers: 4.6 },
};
const a4Heat = dispatch(heatDemand, [["geo", 0], ["hp", 0], ["boiler", 16.0]]);
const a4 = build({
  id: "A4",
  code: "A4",
  name: "Gas boiler and electric chillers (reference)",
  origin: "agent",
  parent: null,
  chosen: false,
  delta: 0,
  source: "mock",
  plant: A4_PLANT,
  heat: a4Heat,
  cool: a2Cool,
  econ: { lcoh: 63.9, lcoc: 59.0, pumpsGwh: 0, absAuxGwh: 0 },
  provenance: { plant: "rule", year: "mock", economics: "mock", cooling: "mock" },
});
// The reference graph: boiler, chillers and the demands only.
a4.graph = {
  nodes: a4.graph.nodes.filter((x) => ["boiler", "chillers", "demand_heat", "demand_cold"].includes(x.id)).map((x) => ({ ...x, solver: "dioscuri" })),
  edges: a4.graph.edges.filter((x) => ["e_boiler_heat", "e_chill_cold"].includes(x.id)),
  gemini_project: null,
};

// CO₂ against the reference; A1 lands on the 80.9 % the team quotes.
const ref = a4.economics.co2_t_per_year;
a1.economics.co2_t_per_year = Math.round(ref * (1 - 0.809));
for (const d of [a1, whatIf, a2, a4]) {
  d.economics.reference_co2_t_per_year = ref;
  d.economics.co2_saving_pct = round((1 - d.economics.co2_t_per_year / ref) * 100, 1);
}
a1.economics.co2_saving_pct = 80.9;

// Against the gas reference: extra capital, yearly savings, payback, NPV and cumulative cash.
for (const d of [a1, whatIf, a2]) {
  const extra = round(d.economics.capex_meur - a4.economics.capex_meur, 2);
  const save = round(a4._opex - d._opex, 3);
  const cash = [round(-extra, 2)];
  // Discounted, as the server sends it, so the curve ends at the NPV.
  for (let t = 1; t <= DEFAULTS.lifetime_years; t++) cash.push(round(cash[t - 1] + save / (1 + DEFAULTS.discount_rate) ** t, 2));
  const npv = round(-extra + save / A, 2);
  d.economics.versus_reference = { extra_capex_meur: extra, savings_meur_per_year: save, payback_years: save > 0 ? round(extra / save, 1) : null, npv_meur: npv, cash_flow_meur: cash };
}

for (const d of [a1, whatIf, a2, a4]) {
  d.checks = checks(d);
  d.verified = d.checks.every((c) => c.passed);
  delete d._opex;
}

const workbench = {
  _fixture: "Fixture data made by scripts/make-workbench-fixtures.mjs, not a real run.",
  threadId: "fixture",
  physics: "gemini",
  gemini: {
    version: "1.0.3",
    patches: [
      "01_heat_exchanger_signed_duty",
      "02_injection_friction_sign",
      "03_roughness_default_4p5e-5m",
      "04_heatpump_bracketed_root",
      "05_esp_affinity_flow_scaling",
      "06_compressor_k_factor",
      "07_dpdt_two_phase_usg_and_roughness_unit_comment",
      "08_heatpump_electricity_emission",
      "09_register_heatpump",
      "10_heatpump_carnot_source_outlet",
    ],
  },
  assumptions: ASSUMPTIONS,
  designs: [a1, a2, a4, whatIf],
};

// ------------------------------------------------------------------ catalogue
const io = (key, unit, description) => ({ key, unit, description });
const par = (key, unit, def, description) => ({ key, unit, default: def, description });
const catalogue = {
  _fixture: "Fixture: GEMINI's component types as the Design tab lists them (made up from gemini_model).",
  types: [
    {
      type: "producer_well",
      label: "Producer well",
      group: "wells",
      description: "Reservoir, well and ESP, solved for the flow that meets the wellhead pressure.",
      inputs: [io("wellhead_pressure", "bar", "Pressure held at the wellhead"), io("wellhead_temperature", "°C", "Brine temperature at the wellhead")],
      outputs: [io("flow_rate", "m³/h", "Brine flow"), io("flow_rate_m3s", "m³/s", "Brine flow, SI"), io("pressure_out", "bar", "Wellhead pressure"), io("temperature_out", "°C", "Brine temperature"), io("esp_power_el", "W", "ESP electricity"), io("emission", "kg/h", "CO₂ from the ESP's electricity")],
      parameters: [
        par("reservoir_pressure_bar", "bar", 250, "Reservoir pressure"),
        par("productivity_index_m3h_per_bar", "m³/h/bar", 10, "Flow per bar of drawdown"),
        par("ambient_temperature_c", "°C", 20, "Surface temperature"),
        par("trajectory_table", "", [{ MD: 0, TVD: 0, ID: 0.15 }, { MD: 2400, TVD: 2400, ID: 0.15 }], "Survey stations: measured depth, true vertical depth, inner diameter (m)"),
        par("esp_depth_m", "m", 650, "Pump setting depth"),
        par("esp_freq_hz", "Hz", 65, "Pump frequency"),
      ],
    },
    {
      type: "injector_well",
      label: "Injector well",
      group: "wells",
      description: "Well back into the reservoir, with the pump that lifts the return brine to the injection pressure.",
      inputs: [io("flow_rate", "m³/h", "Brine flow to inject"), io("wellhead_temperature", "°C", "Return brine temperature"), io("pressure_in", "Pa", "Pressure arriving at the wellhead")],
      outputs: [io("wellhead_pressure", "bar", "Pressure needed at the wellhead"), io("power_el", "W", "Injector pump electricity"), io("emission", "kg/h", "CO₂ from the pump's electricity")],
      parameters: [
        par("reservoir_pressure_bar", "bar", 240, "Reservoir pressure"),
        par("productivity_index_m3h_per_bar", "m³/h/bar", 10, "Injectivity"),
        par("trajectory_table", "", [{ MD: 0, TVD: 0, ID: 0.15 }, { MD: 3100, TVD: 3100, ID: 0.15 }], "Survey stations"),
        par("injector_pump", "", { efficiency_factor: 0.8, electricity_emission_factor: 0.3 }, "Pump efficiency and the grid's CO₂ factor"),
      ],
    },
    {
      type: "separator",
      label: "Gas separator",
      group: "surface",
      description: "Takes the co-produced gas out of the brine.",
      inputs: [io("flow_rate", "m³/s", "Brine flow"), io("pressure", "bar", "Inlet pressure"), io("temperature", "°C", "Inlet temperature")],
      outputs: [io("flow_rate", "m³/s", "Brine flow out"), io("pressure_out", "bar", "Outlet pressure"), io("temperature_out", "°C", "Outlet temperature"), io("gas_mass_flow_rate", "kg/s", "Separated gas")],
      parameters: [par("flow_resistance", "bar·s²/m⁶", 3.6, "Pressure loss coefficient"), par("temperature_drop", "K", 1, "Heat lost across it"), par("gas_water_ratio", "", 0.5, "Gas per volume of water"), par("gas_density", "kg/m³", 0.7, "Gas density")],
    },
    {
      type: "filter",
      label: "Filter",
      group: "surface",
      description: "Particle filter whose resistance grows with fouling.",
      inputs: [io("flow_rate", "m³/s", "Brine flow"), io("pressure", "bar", "Inlet pressure"), io("temperature", "°C", "Inlet temperature")],
      outputs: [io("flow_rate", "m³/s", "Brine flow out"), io("pressure_out", "bar", "Outlet pressure"), io("temperature_out", "°C", "Outlet temperature")],
      parameters: [par("base_resistance", "bar·s²/m⁶", 36, "Clean resistance"), par("fouling_coeff_a", "", 18, "Fouling growth"), par("fouling_coeff_b", "", 0.036, "Fouling rate"), par("temperature_drop", "K", 1, "Heat lost across it")],
    },
    {
      type: "heat_exchanger",
      label: "Heat exchanger",
      group: "heat",
      description: "Passes heat from the brine to the district network (counter-flow by default).",
      inputs: [io("primary_flow_rate", "m³/s", "Brine flow"), io("primary_temperature_in", "°C", "Brine in"), io("secondary_flow_rate", "m³/s", "Network flow"), io("secondary_temperature_in", "°C", "Network return"), io("pressure_in", "bar", "Brine pressure in")],
      outputs: [io("heat_duty", "W", "Heat passed"), io("primary_temperature_out", "°C", "Brine out"), io("secondary_temperature_out", "°C", "Network supply"), io("pressure_out", "bar", "Brine pressure out"), io("power_th", "W", "Thermal power")],
      parameters: [par("heat_transfer_coefficient", "W/K", 250000, "UA, the conductance of the exchanger"), par("flow_configuration", "", "counter", "counter or parallel"), par("flow_resistance", "bar·s²/m⁶", 0, "Pressure loss coefficient")],
    },
    {
      type: "heatpump",
      label: "Heat pump",
      group: "heat",
      description: "Lifts heat from the brine to the network temperature; COP from a Carnot or Lorenz efficiency.",
      inputs: [io("source_flow_rate", "m³/s", "Brine flow"), io("source_temperature_in", "°C", "Brine in"), io("source_temperature_out", "°C", "Brine out"), io("hot_flow_rate", "m³/s", "Network flow"), io("hot_temperature_out", "°C", "Network supply")],
      outputs: [io("power_th", "W", "Heat delivered"), io("electrical_consumption", "W", "Electricity"), io("cop", "", "Coefficient of performance"), io("source_flow_rate_m3h", "m³/h", "Brine flow")],
      parameters: [par("mode", "", "carnot", "carnot or lorenz"), par("eta_carnot", "", 0.5, "Share of the Carnot COP reached"), par("eta_lorenz", "", 0.6, "Share of the Lorenz COP reached"), par("rho_s", "kg/m³", 1000, "Source fluid density"), par("rho_h", "kg/m³", 1000, "Network water density")],
    },
    {
      type: "boiler",
      label: "Gas boiler",
      group: "heat",
      description: "Burns gas to top up the network temperature.",
      inputs: [io("gas_flow_rate", "kg/s", "Gas burnt"), io("water_flow_rate", "m³/s", "Water through it"), io("temperature_in", "°C", "Water in")],
      outputs: [io("temperature_out", "°C", "Water out"), io("power_th", "W", "Heat delivered"), io("emission", "kg/h", "CO₂ from the gas")],
      parameters: [par("caloric_value", "J/kg", 50000000, "Gas energy content"), par("efficiency_factor", "", 0.8, "Share of the gas energy delivered"), par("gas_emission_factor", "kg/GJ", 56.6, "CO₂ per GJ of gas")],
    },
    {
      type: "chp",
      label: "Combined heat and power",
      group: "heat",
      description: "Burns gas for heat and electricity.",
      inputs: [io("gas_flow_rate", "kg/s", "Gas burnt"), io("water_flow_rate", "m³/s", "Water through it"), io("temperature_in", "°C", "Water in")],
      outputs: [io("temperature_out", "°C", "Water out"), io("power_th", "W", "Heat delivered"), io("power_el", "W", "Electricity made"), io("emission", "kg/h", "CO₂ from the gas")],
      parameters: [par("caloric_value", "J/kg", 50000000, "Gas energy content"), par("efficiency_factor", "", 0.8, "Share of the gas energy delivered"), par("gas_emission_factor", "kg/GJ", 56.6, "CO₂ per GJ of gas")],
    },
    {
      type: "splitter",
      label: "Splitter",
      group: "flow",
      description: "Splits one flow into fixed fractions.",
      inputs: [io("input", "", "The flow to split")],
      outputs: [io("output_0", "", "First branch"), io("output_1", "", "Second branch")],
      parameters: [par("split_fractions", "", [0.8, 0.2], "Fractions, adding up to 1")],
    },
    {
      type: "mixer",
      label: "Mixer",
      group: "flow",
      description: "Joins flows; the temperature is the flow-weighted mean.",
      inputs: [io("input_0_flow", "m³/s", "First flow"), io("input_0_temperature", "°C", "First temperature"), io("input_1_flow", "m³/s", "Second flow"), io("input_1_temperature", "°C", "Second temperature")],
      outputs: [io("flow", "m³/s", "Joined flow"), io("temperature", "°C", "Mixed temperature")],
      parameters: [par("num_inputs", "", 2, "How many flows join")],
    },
    {
      type: "adder",
      label: "Adder",
      group: "flow",
      description: "Adds numbers, e.g. the electricity of several units.",
      inputs: [io("input_0", "", "First value"), io("input_1", "", "Second value")],
      outputs: [io("output", "", "The sum")],
      parameters: [par("num_inputs", "", 2, "How many values")],
    },
  ],
};

// A GEMINI run of A1's project: the fixed solver, and the released one with the bugs.
const geminiRun = {
  _fixture: "Fixture: a GEMINI run of A1's project, fixed and released (made up).",
  ok: true,
  error: null,
  seconds: 0.42,
  outputs: {
    producer_well: { flow_rate: 195.5, temperature_out: 86, pressure_out: 3.0, esp_power_el: 195000 },
    heat_exchanger: { heat_duty: 9250000, primary_temperature_out: 45.4, secondary_temperature_out: 70.0, power_th: 9250000 },
    heatpump: { power_th: 4550000, electrical_consumption: 1060606, cop: 4.29, source_flow_rate_m3h: 195.5 },
    boiler: { power_th: 500000, temperature_out: 70.0, emission: 0 },
    injector_well: { wellhead_pressure: 18.4, power_el: 281000 },
  },
  released: {
    ok: true,
    error: null,
    outputs: {
      producer_well: { flow_rate: 123.7, temperature_out: 86, pressure_out: 3.0, esp_power_el: 156000 },
      heat_exchanger: { heat_duty: -5850000, primary_temperature_out: 45.4, secondary_temperature_out: 70.0, power_th: -5850000 },
      heatpump: { power_th: 4550000, electrical_consumption: 4174312, cop: 1.09, source_flow_rate_m3h: 123.7 },
      boiler: { power_th: 500000, temperature_out: 70.0, emission: 0 },
      injector_well: { wellhead_pressure: 22.6, power_el: 363000 },
    },
  },
  patches: workbench.gemini.patches,
};

// ------------------------------------------------------------------ sensitivity (A1)
const OUTS = [
  { key: "lcoh", label: "Cost of heat", unit: "€/MWh" },
  { key: "lcoc", label: "Cost of cold", unit: "€/MWh" },
  { key: "co2_saving_pct", label: "CO₂ saving", unit: "%" },
  { key: "heat_coverage", label: "Heat covered", unit: "%" },
  { key: "capex_meur", label: "Capital", unit: "M€" },
  { key: "npv_meur", label: "NPV against gas", unit: "M€" },
];
const PARAMS = [
  { key: "reservoir_delta_c", label: "Reservoir temperature", unit: "°C", group: "subsurface", low: -10, high: 5, kind: "delta", description: "Reservoir warmer (+) or colder (−) than expected" },
  { key: "transmissivity_scale", label: "Transmissivity", unit: "×", group: "subsurface", low: 0.5, high: 1.5, kind: "scale", description: "How easily the reservoir gives water, times the expected value" },
  { key: "heat_demand_scale", label: "Heat demand", unit: "×", group: "demand", low: 0.85, high: 1.15, kind: "scale", description: "The district's heat demand, times the profile" },
  { key: "cool_demand_scale", label: "Cold demand", unit: "×", group: "demand", low: 0.8, high: 1.3, kind: "scale", description: "The district's cold demand, times the profile" },
  { key: "gas_eur_per_mwh", label: "Gas price", unit: "€/MWh", group: "prices", low: 25, high: 60, kind: "absolute", description: "Gas price without CO₂" },
  { key: "electricity_eur_per_mwh", label: "Electricity price", unit: "€/MWh", group: "prices", low: 60, high: 160, kind: "absolute", description: "Electricity price without CO₂" },
  { key: "carbon_eur_per_t", label: "CO₂ price", unit: "€/t", group: "prices", low: 40, high: 150, kind: "absolute", description: "Price of a tonne of CO₂" },
  { key: "discount_rate", label: "Discount rate", unit: "%", group: "costs", low: 3, high: 9, kind: "absolute", description: "Real discount rate, in percent" },
  { key: "well_capex_scale", label: "Well cost", unit: "×", group: "costs", low: 0.7, high: 1.5, kind: "scale", description: "Drilling cost, times the expected value" },
  { key: "heat_pump_cop_scale", label: "Heat pump COP", unit: "×", group: "equipment", low: 0.85, high: 1.1, kind: "scale", description: "Heat pump COP, times the computed one" },
  { key: "absorption_cop", label: "Absorption COP", unit: "", group: "equipment", low: 0.6, high: 0.8, kind: "absolute", description: "Cold per unit of driving heat" },
];
const BASE = { lcoh: 42.4, lcoc: 58, co2_saving_pct: 80.9, heat_coverage: 100, capex_meur: a1.economics.capex_meur, npv_meur: a1.economics.versus_reference.npv_meur };
const BASE_X = { reservoir_delta_c: 0, transmissivity_scale: 1, heat_demand_scale: 1, cool_demand_scale: 1, gas_eur_per_mwh: 38, electricity_eur_per_mwh: 90, carbon_eur_per_t: 80, discount_rate: 5, well_capex_scale: 1, heat_pump_cop_scale: 1, absorption_cop: 0.7 };
// Effect of each parameter on each output per unit change (a linear surrogate, made up).
const SLOPE = {
  reservoir_delta_c: { lcoh: -0.55, lcoc: -0.16, co2_saving_pct: 0.95, heat_coverage: 0.42, capex_meur: 0, npv_meur: 0.62 },
  transmissivity_scale: { lcoh: -6.2, lcoc: -1.1, co2_saving_pct: 7.5, heat_coverage: 3.0, capex_meur: 0, npv_meur: 8.4 },
  heat_demand_scale: { lcoh: -9.5, lcoc: 0, co2_saving_pct: -14, heat_coverage: -9, capex_meur: 0, npv_meur: 12.0 },
  cool_demand_scale: { lcoh: 0, lcoc: -11.8, co2_saving_pct: -2.1, heat_coverage: 0, capex_meur: 0, npv_meur: 1.1 },
  gas_eur_per_mwh: { lcoh: 0, lcoc: 0, co2_saving_pct: 0, heat_coverage: 0, capex_meur: 0, npv_meur: 1.05 },
  electricity_eur_per_mwh: { lcoh: 0.078, lcoc: 0.124, co2_saving_pct: 0, heat_coverage: 0, capex_meur: 0, npv_meur: -0.07 },
  carbon_eur_per_t: { lcoh: 0.019, lcoc: 0.026, co2_saving_pct: 0, heat_coverage: 0, capex_meur: 0, npv_meur: 0.15 },
  discount_rate: { lcoh: 2.15, lcoc: 0.18, co2_saving_pct: 0, heat_coverage: 0, capex_meur: 0, npv_meur: -3.1 },
  well_capex_scale: { lcoh: 20.0, lcoc: 0, co2_saving_pct: 0, heat_coverage: 0, capex_meur: 19.0, npv_meur: -19.0 },
  heat_pump_cop_scale: { lcoh: -3.3, lcoc: 0, co2_saving_pct: 2.6, heat_coverage: 0.4, capex_meur: 0, npv_meur: 1.9 },
  absorption_cop: { lcoh: 0, lcoc: -22, co2_saving_pct: 1.2, heat_coverage: 0, capex_meur: 0, npv_meur: 0.8 },
};
const outputAt = (key, x) =>
  Object.fromEntries(
    OUTS.map((o) => {
      let v = BASE[o.key] + SLOPE[key][o.key] * (x - BASE_X[key]);
      if (o.key === "heat_coverage") v = Math.min(100, v);
      return [o.key, round(v, 2)];
    }),
  );
const tornado = PARAMS.map((p) => ({ key: p.key, label: p.label, low: outputAt(p.key, BASE_X[p.key] + (p.kind === "delta" ? p.low : 0) + (p.kind !== "delta" ? p.low - BASE_X[p.key] : 0)), high: outputAt(p.key, p.kind === "delta" ? BASE_X[p.key] + p.high : p.high) }))
  .sort((a, b) => Math.abs(b.high.lcoh - b.low.lcoh) - Math.abs(a.high.lcoh - a.low.lcoh));
const spider = PARAMS.map((p) => ({
  key: p.key,
  points: [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const x = round(p.low + f * (p.high - p.low), 4);
    return { x, values: outputAt(p.key, p.kind === "delta" ? BASE_X[p.key] + x : x) };
  }),
}));
const SAMPLES = 200;
const mc = Object.fromEntries(OUTS.map((o) => [o.key, []]));
for (let s = 0; s < SAMPLES; s++) {
  const v = { ...BASE };
  for (const p of PARAMS) {
    const x = p.low + rand() * (p.high - p.low);
    const at = p.kind === "delta" ? BASE_X[p.key] + x : x;
    for (const o of OUTS) v[o.key] += SLOPE[p.key][o.key] * (at - BASE_X[p.key]);
  }
  v.heat_coverage = Math.min(100, v.heat_coverage);
  for (const o of OUTS) mc[o.key].push(v[o.key]);
}
function stats(values) {
  const s = [...values].sort((a, b) => a - b);
  const q = (f) => s[Math.min(s.length - 1, Math.max(0, Math.round(f * (s.length - 1))))];
  const lo = s[0];
  const hi = s[s.length - 1];
  const bins = 16;
  const width = (hi - lo) / bins || 1;
  const edges = Array.from({ length: bins + 1 }, (_, i) => round(lo + i * width, 3));
  const counts = new Array(bins).fill(0);
  for (const v of s) counts[Math.min(bins - 1, Math.floor((v - lo) / width))]++;
  return { p10: round(q(0.1), 2), p50: round(q(0.5), 2), p90: round(q(0.9), 2), mean: round(sum(s) / s.length, 2), histogram: { edges, counts } };
}
const sensitivity = {
  _fixture: "Fixture: a sensitivity study of A1 on a made-up linear surrogate.",
  parameters: PARAMS,
  outputs: OUTS,
  result: {
    design: "A1",
    seconds: 18.6,
    runs: 2 * PARAMS.length + 5 * PARAMS.length + SAMPLES,
    base: BASE,
    tornado,
    spider,
    monte_carlo: { samples: SAMPLES, outputs: Object.fromEntries(OUTS.map((o) => [o.key, stats(mc[o.key])])) },
  },
};

// ------------------------------------------------------------------ trace
const FULL =
  "Design a geothermal heating and cooling system for this district using the provided heating and cooling demand profiles and reservoir data. Use 70/40 C district heating and 6/12 C district cooling. Minimise levelised cost while meeting at least 95% of both demands.";
const step = (name, label, kind, code, seconds, meta = {}) => ({ name, label, kind, code, seconds, meta });
const t0 = Date.UTC(2026, 9, 29, 9, 12, 4) / 1000;
const trace = {
  _fixture: "Fixture: two runs of one conversation (a design, then a what-if), made up after recorded streams.",
  runs: [
    {
      runId: "fbc5f7c183",
      started: t0,
      message: FULL,
      mode: "fast",
      device: "gpu",
      seconds: 4.12,
      tokens: { prompt: 2380, output: 315 },
      steps: [
        step("intake", "Read the request", "model", null, 0.31, { model: "qwen3:1.7b", device: "gpu", fields: 7 }),
        step("plan", "Plan the study", "plan", "plan(brief, options)", 0.01, { decided_by: "rules", plan: ["A1", "A2", "A4"] }),
        step("doublet", "Solve the doublet", "tool", "solve_doublet(depth_m=2500, 1500)", 0.38, { solver: "gemini", patches: 10 }),
        step("simulate", "Simulate the year", "tool", "simulate_year(A1, A2, A4)", 0.02, { source: "mock" }),
        step("economics", "Cost and CO₂", "tool", "economics(A1, A2, A4)", 0.01, { source: "mock" }),
        step("verify", "Check the physics", "check", "verify_design(A1, A2, A4)", 0.01, { passed: 17, total: 17 }),
        step("answer", "Write the answer", "model", "answer(self, project, A1, A4, A2, draft)", 3.21, { model: "qwen3.5:9b", device: "gpu" }),
        step("claims", "Check each sentence", "model", null, 0.14, { checked: 4, supported: 4, removed: 0 }),
        step("report", "Check the answer's numbers", "report", null, 0.03, { numbers: 6, ungrounded: 0 }),
      ],
      calls: [
        { purpose: "intake", model: "qwen3:1.7b", prompt_tokens: 820, output_tokens: 70, seconds: 0.31, ok: true },
        { purpose: "answer", model: "qwen3.5:9b", prompt_tokens: 1560, output_tokens: 245, seconds: 3.21, ok: true },
      ],
      tools: [
        { name: "solve_doublet", args: { depth_m: 2500 }, result: { flow_m3h: 195.5, wellhead_c: 86, esp_mw: 0.195, injector_pump_mw: 0.281 } },
        { name: "solve_doublet", args: { depth_m: 1500 }, result: { flow_m3h: 305.6, wellhead_c: 55, esp_mw: 0.31, injector_pump_mw: 0.22 } },
        { name: "simulate_year", args: { alternative: "A1" }, result: { heat_delivered_gwh: 61.76, cool_delivered_gwh: 13.67 } },
        { name: "economics", args: { alternative: "A1" }, result: { lcoh: 42.4, lcoc: 58, co2_saving_pct: 80.9 } },
        { name: "verify_design", args: { alternative: "A1" }, result: { passed: 17, total: 17 } },
      ],
      outcome: "design",
    },
    {
      runId: "3c90d1aa07",
      started: t0 + 96,
      message: "What happens to the recommended design if the reservoir is 10 C colder than expected?",
      mode: "fast",
      device: "gpu",
      seconds: 3.48,
      tokens: { prompt: 2210, output: 268 },
      steps: [
        step("intake", "Read the request", "model", null, 0.29, { model: "qwen3:1.7b", device: "gpu", fields: 2 }),
        step("plan", "Plan the study", "plan", "plan(what_if, A1)", 0.01, { decided_by: "rules", plan: ["A1 −10 °C"] }),
        step("doublet", "Solve the doublet", "tool", "solve_doublet(depth_m=2500, reservoir_delta_c=-10)", 0.36, { solver: "gemini", patches: 10 }),
        step("simulate", "Simulate the year", "tool", "simulate_year(A1 −10 °C)", 0.02, { source: "mock" }),
        step("economics", "Cost and CO₂", "tool", "economics(A1 −10 °C)", 0.01, { source: "mock" }),
        step("verify", "Check the physics", "check", "verify_design(A1 −10 °C)", 0.01, { passed: whatIf.checks.filter((c) => c.passed).length, total: whatIf.checks.length }),
        step("answer", "Write the answer", "model", "answer(self, A1, A1 −10 °C)", 2.71, { model: "qwen3.5:9b", device: "gpu" }),
        step("report", "Check the answer's numbers", "report", null, 0.02, { numbers: 5, ungrounded: 0 }),
      ],
      calls: [
        { purpose: "intake", model: "qwen3:1.7b", prompt_tokens: 760, output_tokens: 48, seconds: 0.29, ok: true },
        { purpose: "answer", model: "qwen3.5:9b", prompt_tokens: 1450, output_tokens: 220, seconds: 2.71, ok: true },
      ],
      tools: [
        { name: "solve_doublet", args: { depth_m: 2500, reservoir_delta_c: -10 }, result: { flow_m3h: 195.5, wellhead_c: 76 } },
        { name: "simulate_year", args: { alternative: "A1", reservoir_delta_c: -10 }, result: { heat_delivered_gwh: whatIf.year.heat_delivered_gwh } },
        { name: "economics", args: { alternative: "A1", reservoir_delta_c: -10 }, result: { lcoh: 47.9, co2_saving_pct: whatIf.economics.co2_saving_pct } },
        { name: "verify_design", args: { alternative: "A1 −10 °C" }, result: { passed: whatIf.checks.filter((c) => c.passed).length, total: whatIf.checks.length } },
      ],
      outcome: "design",
    },
  ],
};

// ------------------------------------------------------------------ evidence
const SCEN = [
  ["S01_full_brief", "design"],
  ["S02_missing_network_temps", "clarify"],
  ["S03_missing_reservoir", "clarify"],
  ["S04_irrelevant_weather", "refuse"],
  ["S05_irrelevant_poem", "refuse"],
  ["S06_adversarial_physics", "reject"],
  ["S07_what_if_reservoir", "design"],
  ["S08_compare_depths", "design"],
  ["S09_model_gap_adsorption", "answer"],
  ["S10_dutch_prompt", "clarify_or_design"],
  ["S11_infeasible", "report_infeasible"],
  ["S12_injection_in_docs", "design"],
  ["S13_who_are_you", "about"],
  ["S14_what_can_you_do", "about"],
  ["S15_greeting", "greeting"],
  ["S16_reservoir_question", "answer"],
  ["S17_values_after_design", "answer"],
  ["S18_pick_a_fix", "design"],
  ["S19_plan_without_heat_pumps", "design"],
  ["S20_advantages", "answer_or_about"],
  ["S21_instructions", "answer_or_about_or_clarify"],
  ["S22_what_from_gemini", "answer_or_about"],
  ["S23_general_background", "answer"],
  ["S24_interpret_result", "answer"],
  ["S25_nonsense", "nonsense"],
];
function evalRun(file, device, answerer, when, speed, fail = []) {
  const scenarios = SCEN.map(([id, expected]) => {
    const got = fail.includes(id) ? (expected === "clarify" ? "design" : "answer") : expected.split("_or_")[0];
    const calls = ["S04_irrelevant_weather", "S05_irrelevant_poem", "S15_greeting"].includes(id) ? 1 : 2;
    const tokens = Math.round((calls === 1 ? 420 : 1650) * (0.85 + rand() * 0.3));
    return { id, expected, got, ok: !fail.includes(id), calls, tokens, seconds: round((tokens / 1000) * speed * (0.8 + rand() * 0.4), 2) };
  });
  return { file, device, answerer, when, passed: scenarios.filter((s) => s.ok).length, total: scenarios.length, tokens: sum(scenarios.map((s) => s.tokens)), seconds: round(sum(scenarios.map((s) => s.seconds)), 1), scenarios };
}
const evidence = {
  _fixture: "Fixture: eval runs, benchmarks and GEMINI's bug impact, made up after the team's real runs.",
  evals: [
    evalRun("hackathon/evals/runs/20261029T081500Z_qwen3-1.7b_cpu.jsonl", "cpu", "qwen3.5:4b", "2026-10-29T08:15:00Z", 2.1),
    evalRun("hackathon/evals/runs/20261029T083000Z_qwen3.5-9b_gpu.jsonl", "gpu", "qwen3.5:9b", "2026-10-29T08:30:00Z", 0.9, ["S21_instructions"]),
  ],
  benchmarks: [
    {
      title: "Local models on a judge-like laptop (8 cores, 16 GB, no GPU)",
      columns: ["Model", "Size", "Scenarios passed", "Tokens a turn", "Seconds a turn"],
      rows: [
        ["qwen3:1.7b", "1.4 GB", "25 / 25", 1650, 2.6],
        ["qwen3.5:2b q4_K_M", "1.6 GB", "24 / 25", 1710, 2.9],
        ["qwen2.5:1.5b", "1.0 GB", "23 / 25", 1580, 2.2],
        ["granite4.2:3b", "2.1 GB", "24 / 25", 1690, 3.8],
        ["llama3.2:3b", "2.0 GB", "22 / 25", 1720, 3.6],
        ["qwen3:0.6b", "0.5 GB", "19 / 25", 1600, 1.4],
      ],
      note: "Fixture: made-up numbers in the shape of hackathon/evals/runs.",
    },
    {
      title: "Tokens against a naive agent",
      columns: ["Task", "Dioscuri", "Naive agent", "Saved"],
      rows: [
        ["Full brief to a design", 2695, 11840, "77%"],
        ["What-if on the reservoir", 2478, 9930, "75%"],
        ["Value question", 1210, 6020, "80%"],
      ],
      note: "Fixture: the naive agent sends the whole tool output to the model every turn.",
    },
  ],
  gemini: {
    version: "1.0.3",
    patches: workbench.gemini.patches.map((file) => ({ file: `${file}.diff`, title: file.replace(/^\d+_/, "").replace(/_/g, " ") })),
    bug_impact: [
      {
        design: "A1",
        rows: [
          { quantity: "Brine flow", unit: "m³/h", released: 123.7, fixed: 195.5, bugs: "F10 roughness default 10 mm" },
          { quantity: "Heat exchanger duty", unit: "MW", released: -5.85, fixed: 9.25, bugs: "F1 heat flows cold to hot; F10" },
          { quantity: "Heat pump COP", unit: "", released: 1.09, fixed: 4.29, bugs: "F2 spurious root when source-limited" },
          { quantity: "ESP power", unit: "MW", released: 0.156, fixed: 0.195, bugs: "F5 affinity law misapplied; F10" },
          { quantity: "Injector pump power", unit: "MW", released: 0.363, fixed: 0.281, bugs: "F3 friction sign" },
          { quantity: "Absorption chiller", unit: "MW", released: null, fixed: 2.0, bugs: "not in GEMINI (Dioscuri's model)" },
        ],
      },
    ],
  },
};

// ------------------------------------------------------------------ write and report
const write = (name, data) => writeFileSync(join(OUT, name), JSON.stringify(data) + "\n");
write("workbench.json", workbench);
write("catalogue.json", catalogue);
write("gemini-run.json", geminiRun);
write("sensitivity.json", sensitivity);
write("trace.json", trace);
write("evidence.json", evidence);

for (const d of workbench.designs) {
  const y = d.year;
  const heatLines = sum(d.economics.lines.heat.map((l) => l.eur_per_mwh));
  const coldLines = sum(d.economics.lines.cold.map((l) => l.eur_per_mwh));
  const cal = [...d.economics.lines.heat, ...d.economics.lines.cold].filter((l) => l.kind === "calibration").map((l) => l.eur_per_mwh);
  console.log(
    `${d.id.padEnd(10)} heat ${y.heat_delivered_gwh.toFixed(2)} (${Object.values(y.heat_split_gwh).map((v) => v.toFixed(2)).join("/")}) cov ${y.heat_coverage}`,
    `cold ${y.cool_delivered_gwh.toFixed(2)} (${Object.values(y.cool_split_gwh).map((v) => v.toFixed(2)).join("/")}) cov ${y.cool_coverage}`,
    `lcoh ${heatLines.toFixed(2)} lcoc ${coldLines.toFixed(2)} cal ${cal.join(",")} capex ${d.economics.capex_meur} co2 ${d.economics.co2_saving_pct}% flh ${y.full_load_hours}`,
    `checks ${d.checks.filter((c) => c.passed).length}/${d.checks.length}`,
    d.economics.versus_reference ? `npv ${d.economics.versus_reference.npv_meur} payback ${d.economics.versus_reference.payback_years}` : "",
  );
}
console.log(`geo cap ${geoCap.toFixed(2)} MW, abs level ${absLevel.toFixed(2)} MW, peak heat ${Math.max(...heatDemand).toFixed(2)}, peak cold ${Math.max(...coldDemand).toFixed(2)}`);
