// The Energy tab: heat and cold over the year for the design in the picker. KPI tiles, then a
// Heat | Cold switch over three charts: the year day by day (stacked by source, the demand as a
// line, any shortfall hatched), the load-duration curve and the months; then the year's CO₂ by
// unit, the doublets and the operating plan. The numbers are the design's Year (workbench API);
// nothing is recomputed here except shares and sorting.

import "./EnergyTab.css";

import { useMemo, useState } from "react";

import { useIntent } from "../menu";
import { AskButton, ProvenanceChip, TabFrame, designTitle, fmtNum, hrefFor, provenanceOf, useSelectedDesign, type Design } from "../workbench";
import { SIDE_KEYS, SOURCE_META, heatInstalled as installedHeat, powerParts, sideRows, type Side } from "./energy/model";
import { Co2Panel } from "./energy/Co2Panel";
import { DoubletsPanel } from "./energy/DoubletsPanel";
import { OperationsPanel } from "./energy/OperationsPanel";
import { DurationPanel, MonthPanel, YearPanel } from "./energy/Panels";
import { Meter, Panel, SplitBar, Switch, Tile } from "./energy/parts";

export default function EnergyTab() {
  const design = useSelectedDesign();
  // Kept across designs: picking another design keeps the side on screen.
  const [side, setSide] = useState<Side>("heat");
  // The one series the stacks show (a legend entry's menu), or all of them.
  const [only, setOnly] = useState<string | null>(null);
  // "Show its year in Energy" on a unit of the Design tab: its side, and its series alone.
  useIntent("energy", (v) => {
    setSide(v.side);
    setOnly(v.series);
  });
  return (
    <TabFrame
      scope="design"
      className="tab-energy"
      title="Energy over the year"
      lead="Heat and cold supplied against demand, day by day and month by month."
      actions={design && <AskButton context={`the energy over the year of ${designTitle(design)}`} />}
    >
      {design && <EnergyBody design={design} picked={side} setSide={setSide} only={only} onOnly={setOnly} />}
    </TabFrame>
  );
}

function EnergyBody({ design, picked, setSide, only, onOnly }: { design: Design; picked: Side; setSide: (s: Side) => void; only: string | null; onOnly: (k: string | null) => void }) {
  const y = design.year;
  const hasCold = y.cool_demand_gwh > 0;
  const side: Side = picked === "cool" && !hasCold ? "heat" : picked;
  const rows = useMemo(() => sideRows(y, side), [y, side]);
  const yearProv = provenanceOf(design, "year");
  const plantProv = provenanceOf(design, "plant");

  return (
    <>
      <Kpis design={design} />

      <div className="en-bar ta-rise" style={{ animationDelay: ".04s" }}>
        <Switch
          label="Show heat or cold"
          value={side}
          onChange={setSide}
          options={hasCold ? [{ id: "heat", label: "Heat" }, { id: "cool", label: "Cold" }] : [{ id: "heat", label: "Heat" }]}
        />
        <p className="en-prov">
          <span>
            Plant <ProvenanceChip source={plantProv} detail={plantProv === "gemini" ? "The operating point: flow, temperatures, sizes" : undefined} />
          </span>
          <span>
            Year's dispatch <ProvenanceChip source={yearProv} detail="Which source runs each day, from a typical weather year" />
          </span>
        </p>
      </div>

      {rows.length ? (
        <>
          <YearPanel design={design} side={side} rows={rows} prov={yearProv} only={only} onOnly={onOnly} />
          <div className="en-pair">
            <DurationPanel design={design} side={side} rows={rows} prov={yearProv} only={only} onOnly={onOnly} />
            {y.monthly_gwh && <MonthPanel design={design} side={side} prov={yearProv} />}
          </div>
        </>
      ) : (
        <Panel title="No daily data">
          <p className="ee-foot">This design has no day-by-day {side === "heat" ? "heat" : "cold"} dispatch to draw.</p>
        </Panel>
      )}

      <Co2Panel design={design} prov={yearProv} />
      {(y.doublets?.length ?? 0) > 0 && <DoubletsPanel design={design} prov={yearProv} />}
      {rows.length > 0 && <OperationsPanel design={design} prov={yearProv} />}

      <p className="en-note ta-rise" style={{ animationDelay: ".18s" }}>
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="8" cy="8" r="6.4" fill="none" stroke="currentColor" strokeWidth="1.4" />
          <path d="M8 7.2v4M8 4.7v.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <span>
          This is one base-case year. The P10, P50 and P90 bands of coverage, cost and CO₂ come from the Monte Carlo on the{" "}
          <a href={hrefFor("sensitivity")}>Sensitivity tab</a>.
        </span>
      </p>
    </>
  );
}

const pct = (v: number) => fmtNum(Math.max(0, Math.min(1, v)) * 100);

function Kpis({ design }: { design: Design }) {
  const y = design.year;
  const p = design.plant;
  const s = p.sizes_mw;
  const heatInstalled = installedHeat(design);
  const coldInstalled = (p.absorption ? s.absorption || 0 : 0) + (p.chillers ? s.chillers || 0 : 0);
  const heatShort = Math.max(0, y.heat_demand_gwh - y.heat_delivered_gwh);
  const coolShort = Math.max(0, y.cool_demand_gwh - y.cool_delivered_gwh);
  const hasCold = y.cool_demand_gwh > 0;
  const doublet = p.depth_m > 0;
  const split = (side: Side) => {
    const values = side === "heat" ? y.heat_split_gwh : y.cool_split_gwh;
    return SIDE_KEYS[side].map((k) => ({ key: k, value: (values as Record<string, number>)[k] ?? 0, color: SOURCE_META[k].color }));
  };
  const splitText = (side: Side) =>
    split(side)
      .filter((x) => x.value > 0)
      .map((x) => `${SOURCE_META[x.key].label} ${fmtNum(x.value)} GWh`)
      .join(", ");
  const full = (cov: number) => cov >= 0.9995;
  return (
    <div className="ee-tiles ta-rise">
      <Tile
        label="Heat covered"
        swatch={SOURCE_META.geo.color}
        note={full(y.heat_coverage) ? "all of it" : `${fmtNum(heatShort)} GWh short`}
        noteTone={full(y.heat_coverage) ? "muted" : "bad"}
        value={pct(y.heat_coverage)}
        unit="%"
        valueTone={full(y.heat_coverage) ? undefined : "bad"}
        sub={`${fmtNum(y.heat_delivered_gwh)} of ${fmtNum(y.heat_demand_gwh)} GWh a year`}
      >
        <SplitBar parts={split("heat")} total={y.heat_demand_gwh} short={heatShort} label={`Heat by source: ${splitText("heat")}`} />
      </Tile>
      <PeakTile label="Peak heat" peak={y.peak_heat_mw} installed={heatInstalled} />
      {hasCold ? (
        <>
          <Tile
            label="Cold covered"
            swatch={SOURCE_META.abs.color}
            note={full(y.cool_coverage) ? "all of it" : `${fmtNum(coolShort)} GWh short`}
            noteTone={full(y.cool_coverage) ? "muted" : "bad"}
            value={pct(y.cool_coverage)}
            unit="%"
            valueTone={full(y.cool_coverage) ? undefined : "bad"}
            sub={`${fmtNum(y.cool_delivered_gwh)} of ${fmtNum(y.cool_demand_gwh)} GWh a year`}
          >
            <SplitBar parts={split("cool")} total={y.cool_demand_gwh} short={coolShort} label={`Cold by source: ${splitText("cool")}`} />
          </Tile>
          <PeakTile label="Peak cold" peak={y.peak_cool_mw} installed={coldInstalled} />
        </>
      ) : (
        <Tile label="Cold" value="none" valueTone="muted" sub="no cooling demand in this brief" />
      )}
      {doublet ? (
        <Tile
          label="Doublet full-load hours"
          value={fmtNum(y.full_load_hours, 0)}
          unit="h"
          sub={`at full flow ${fmtNum((y.full_load_hours / 8760) * 100, 0)}% of the year's 8,760 h`}
        >
          <Meter value={y.full_load_hours} max={8760} color={SOURCE_META.geo.color} label={`${fmtNum(y.full_load_hours, 0)} of 8,760 hours`} />
        </Tile>
      ) : (
        <Tile label="Doublet full-load hours" value="no doublet" valueTone="muted" sub={design.economics.versus_reference ? "this design has no wells" : "the gas reference has no wells"} />
      )}
      <PowerTile design={design} />
    </div>
  );
}

/** The grid electricity of the year: its total, and a bar of who draws it (the electric boiler among them). */
function PowerTile({ design }: { design: Design }) {
  const parts = powerParts(design.year);
  const total = parts.reduce((a, x) => a + x.gwh, 0);
  if (!(total > 0)) return null;
  const words = parts.map((x) => `${x.label} ${fmtNum(x.gwh)} GWh`).join(", ");
  return (
    <Tile label="Grid electricity" value={fmtNum(total)} unit="GWh a year">
      <SplitBar parts={parts.map((x) => ({ key: x.key, value: x.gwh, color: x.color }))} total={total} label={`Grid electricity by user: ${words}`} />
      <span className="en-users" aria-hidden="true">
        {parts.map((x) => (
          <span key={x.key} className="en-user" title={`${x.label}: ${fmtNum(x.gwh)} GWh a year`}>
            <i style={{ background: x.color }} />
            {x.label} {fmtNum(x.gwh)}
          </span>
        ))}
      </span>
    </Tile>
  );
}

/** The peak demand against the capacity installed for it: grey up to the peak, hatched past it. */
function PeakTile({ label, peak, installed }: { label: string; peak: number; installed: number }) {
  const short = installed > 0 && installed < peak * 0.995;
  return (
    <Tile
      label={label}
      note={installed > 0 ? `${fmtNum(installed)} MW installed` : "nothing installed"}
      noteTone={short || !(installed > 0) ? "bad" : undefined}
      value={fmtNum(peak)}
      unit="MW"
      sub={short ? `${fmtNum(peak - installed)} MW more than installed` : installed > 0 ? `${fmtNum(installed - peak)} MW of headroom at the peak` : "the highest demand of the year"}
    >
      <SplitBar
        parts={[{ key: "peak", value: short ? installed : peak, color: "#8A959E" }]}
        total={short ? peak : Math.max(installed, peak)}
        short={short ? peak - installed : 0}
        label={`Peak ${fmtNum(peak)} MW against ${fmtNum(installed)} MW installed`}
      />
    </Tile>
  );
}
