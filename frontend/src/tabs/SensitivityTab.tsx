// The Sensitivity tab: what drives the result of one design. You pick the design, the parameters to
// vary (each with its range) and the outputs to measure, both from the server's catalogue (GET
// /api/sensitivity/parameters), and whether to sample them all together (Monte Carlo); a run
// gives a tornado, a spider, a histogram and, with several outputs, a heatmap of which parameter
// moves which output. The first run starts by itself; after a change you press Run (a change
// cancels a run on its way). Each configuration's result is kept for the visit, so going back to
// one shows it at once. The picks are kept per conversation (those the catalogue no longer has are
// dropped). The two setup cards share one height: the right one shows what to measure, a live
// summary of the run the picks make, and Monte Carlo with Run pinned to its bottom.

import "./SensitivityTab.css";

import { useEffect, useMemo, useRef, useState } from "react";

import { Retry, Spinner } from "../components/Icons";
import { useIntent } from "../menu";
import {
  AskButton,
  DesignPicker,
  ErrorState,
  ProvenanceChip,
  Skeleton,
  TabFrame,
  getSensitivityParameters,
  provenanceOf,
  resourceStatus,
  useResource,
  useWorkbench,
  type Design,
  type SensOutput,
  type SensParam,
  type SensitivityParameters,
  type Workbench,
} from "../workbench";
import { Histogram } from "./sensitivity/Histogram";
import { OutagesCard } from "./sensitivity/OutagesCard";
import { ParameterPicker } from "./sensitivity/ParameterPicker";
import { RunSummary } from "./sensitivity/RunSummary";
import {
  DEFAULT_OUTPUTS,
  SAMPLES,
  assignSlots,
  buildRequest,
  configKey,
  defaultSelection,
  fmtOut,
  keepKnown,
  lowerFirst,
  newRow,
  outputName,
  resultOutputs,
  runCount,
  spiderLines,
  tornadoRows,
  trimNum,
  type McSetting,
  type ParamRow,
} from "./sensitivity/params";
import { Spider } from "./sensitivity/Spider";
import { SwingHeatmap } from "./sensitivity/SwingHeatmap";
import { Tornado } from "./sensitivity/Tornado";
import { hasResult, useSensitivityRun } from "./sensitivity/useSensitivityRun";

interface Config {
  rows: ParamRow[];
  outputs: string[];
  mc: McSetting;
  slots: Record<string, number>;
}

const memory = new Map<string, Config>();

function initialConfig(cat: SensitivityParameters): Config {
  const keys = defaultSelection(cat.parameters);
  const rows = keys.map((k) => newRow(cat.parameters.find((p) => p.key === k)!));
  const outputs = DEFAULT_OUTPUTS.filter((o) => cat.outputs.some((x) => x.key === o));
  return { rows, outputs: outputs.length ? outputs : cat.outputs.slice(0, 1).map((o) => o.key), mc: { on: true, samples: SAMPLES.default }, slots: assignSlots({}, keys) };
}

/** What a design's result depends on besides the picks: its numbers and the conversation's assumptions (every one the server lists). */
function designSignature(d: Design, wb: Workbench | null): string {
  const assumptions = (wb?.assumptions?.items ?? []).map((it) => `${it.key}=${it.value}`);
  return JSON.stringify([d.id, d.economics?.lcoh, d.economics?.lcoc, d.economics?.lcoe, d.economics?.capex_meur, d.year?.heat_coverage, ...assumptions]);
}

function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    const t = setInterval(() => setNow(performance.now()), 200);
    return () => clearInterval(t);
  }, []);
  return <>{((now - since) / 1000).toFixed(1)} s</>;
}

export default function SensitivityTab() {
  const wb = useWorkbench();
  const cat = useResource((signal) => getSensitivityParameters(signal), []);
  const threadId = wb.threadId ?? "";
  const design = wb.selected;
  const catalogue = cat.data;

  // The picks, per conversation (adjusted while rendering when the conversation changes).
  const [saved, setSaved] = useState<{ thread: string; cfg: Config | null }>(() => ({ thread: threadId, cfg: memory.get(threadId) ?? null }));
  let stored = saved.cfg;
  if (saved.thread !== threadId) {
    stored = memory.get(threadId) ?? null;
    setSaved({ thread: threadId, cfg: stored });
  }
  const fresh = useMemo(() => (catalogue ? initialConfig(catalogue) : null), [catalogue]);
  // Picks kept from before only count where the catalogue still has them.
  const cfg = stored && catalogue ? keepKnown(stored, catalogue) : (stored ?? fresh);
  // Changes build on the latest picks, so several in one go (fast clicks) all count.
  const update = (change: (c: Config) => Config) =>
    setSaved((s) => {
      const kept = (s.thread === threadId ? s.cfg : memory.get(threadId)) ?? fresh;
      const current = kept && catalogue ? keepKnown(kept, catalogue) : kept;
      if (!current) return s;
      const next = change(current);
      memory.set(threadId, next);
      return { thread: threadId, cfg: next };
    });
  const setRows = (rows: ParamRow[]) => update((c) => ({ ...c, rows, slots: assignSlots(c.slots, rows.map((r) => r.key)) }));
  // "Vary it in Sensitivity" (a number in a reply, a cost line): that parameter joins the picks,
  // with the catalogue's range, once the catalogue is in.
  const [wanted, setWanted] = useState<string | null>(null);
  useIntent("sensitivity", (v) => setWanted(v.param));
  useEffect(() => {
    if (!wanted || !catalogue || !cfg) return;
    setWanted(null);
    const p = catalogue.parameters.find((x) => x.key === wanted);
    if (p && !cfg.rows.some((r) => r.key === p.key)) setRows([...cfg.rows, newRow(p)]);
  }, [wanted, catalogue, cfg]); // eslint-disable-line react-hooks/exhaustive-deps
  const toggleOutput = (key: string) =>
    update((c) => {
      const on = c.outputs.includes(key);
      if (on && c.outputs.length === 1) return c;
      const next = on ? c.outputs.filter((o) => o !== key) : [...c.outputs, key];
      const order: string[] = catalogue?.outputs.map((o) => o.key) ?? [];
      return { ...c, outputs: next.sort((a, b) => order.indexOf(a) - order.indexOf(b)) };
    });

  const sig = design ? designSignature(design, wb.workbench) : "";
  const req = useMemo(
    () => (cfg && design && catalogue ? buildRequest(threadId, design.id, catalogue.parameters, cfg.rows, cfg.outputs, cfg.mc) : null),
    [cfg, design, catalogue, threadId],
  );
  const key = req ? configKey(req, sig) : null;
  const run = useSensitivityRun(threadId, req, key);

  // The first run starts by itself, and again when another design is picked.
  const autoFor = useRef<string | null>(null);
  const runNow = run.run;
  useEffect(() => {
    if (!req || !key || !design || run.pending || hasResult(key)) return;
    const id = `${threadId}|${design.id}`;
    if (autoFor.current === id) return;
    autoFor.current = id;
    runNow();
  }, [req, key, design, threadId, run.pending, runNow]);

  const [outPick, setOutPick] = useState<string | null>(null);
  const result = run.result?.data ?? null;
  const outputs = catalogue?.outputs ?? [];
  const outByKey = new Map(outputs.map((o) => [o.key, o]));
  const paramByKey = useMemo(() => new Map<string, SensParam>((catalogue?.parameters ?? []).map((p) => [p.key, p])), [catalogue]);
  // The outputs the result has, in the catalogue's order (the picks keep that order too).
  const shownOutputs = result ? resultOutputs(result, outputs.map((o) => o.key)) : [];
  const outKey = outPick && shownOutputs.includes(outPick) ? outPick : (shownOutputs[0] ?? null);
  const output: SensOutput | undefined = outKey ? outByKey.get(outKey as SensOutput["key"]) : undefined;
  const tornado = result && outKey ? tornadoRows(result, outKey) : [];
  const ranges = useMemo(() => {
    const r: Record<string, [number, number]> = {};
    for (const s of result?.spider ?? []) if (s.points.length) r[s.key] = [s.points[0].x, s.points[s.points.length - 1].x];
    return r;
  }, [result]);
  const mc = result && outKey ? (result.monte_carlo?.outputs[outKey] ?? null) : null;
  const resultDesign = result ? wb.designs.find((d) => d.id === result.design) : null;

  const top = tornado.find((t) => t.swing > 0);
  // Worded so neither label has to agree with a verb ("capital costs", "caps broken").
  const askQuestion =
    top && output ? `Why does the ${outputName(output)} depend most on the ${lowerFirst(top.label)}?` : "What drives the cost of heat of this design?";
  const askContext =
    result && output && design
      ? `the sensitivity of ${result.design}'s ${lowerFirst(output.label)} on the Sensitivity tab (base ${fmtOut(output, result.base[output.key])}): ${tornado
          .slice(0, 5)
          .map((t) => `${lowerFirst(t.label)} gives ${trimNum(t.low ?? NaN, 1)} to ${trimNum(t.high ?? NaN, 1)}`)
          .join(", ")}`
      : `the Sensitivity tab for ${design?.id ?? "this chat's design"}`;

  const status = wb.workbench ? (wb.designs.length ? resourceStatus(cat) : undefined) : undefined;
  const estimate = cfg ? runCount(cfg.rows.length, cfg.mc.on ? cfg.mc.samples : 0).total : 0;
  const last = run.result?.data;
  const secondsPerRun = last && last.runs > 0 && last.seconds > 0 ? last.seconds / last.runs : null;
  const invalid = cfg && !req && cfg.rows.length > 0;

  return (
    <TabFrame
      scope="designs"
      status={status}
      className="tab-sensitivity"
      title="What drives the result"
      lead="Pick what to vary and what to measure; see which inputs move the result, one at a time and all together."
      actions={<AskButton context={askContext} question={askQuestion} label={top ? askQuestion : "Ask what drives it"} className="sen-ask" />}
      toolbar={
        <div className="sen-toolbar ta-rise" style={{ animationDelay: ".04s" }}>
          <span className="sen-toolbar-cap">Design</span>
          <DesignPicker />
          <span className="sen-toolbar-note">The ranges vary around this design, under this chat's assumptions.</span>
        </div>
      }
    >
      {cfg && catalogue && design && (
        <>
          <div className="sen-setup">
            <section className="sen-card sen-vary ta-rise" style={{ animationDelay: ".06s" }} aria-labelledby="sen-vary-h">
              <header className="sen-card-head">
                <h2 id="sen-vary-h">What to vary</h2>
                <span className="sen-card-sub">
                  {cfg.rows.length} of {catalogue.parameters.length} parameters
                </span>
              </header>
              <ParameterPicker catalogue={catalogue.parameters} rows={cfg.rows} slots={cfg.slots} onRows={setRows} />
            </section>

            <aside className="sen-card sen-side ta-rise" style={{ animationDelay: ".1s" }} aria-label="What to measure and run">
              <div className="sen-side-block" role="group" aria-labelledby="sen-out-h">
                <h2 id="sen-out-h">What to measure</h2>
                <span className="sen-chips">
                  {outputs.map((o) => {
                    const on = cfg.outputs.includes(o.key);
                    return (
                      <button
                        key={o.key}
                        type="button"
                        className={`sen-out ta-btn${on ? " is-on" : ""}`}
                        aria-pressed={on}
                        title={on && cfg.outputs.length === 1 ? "Measure at least one output" : `${o.label}, ${o.unit}`}
                        onClick={() => toggleOutput(o.key)}
                      >
                        {o.label}
                        <span className="sen-out-unit">{o.unit}</span>
                      </button>
                    );
                  })}
                </span>
              </div>

              <RunSummary
                rows={cfg.rows}
                slots={cfg.slots}
                catalogue={paramByKey}
                outputs={cfg.outputs.map((k) => outByKey.get(k as SensOutput["key"])?.label ?? k)}
                mc={cfg.mc}
                secondsPerRun={secondsPerRun}
              />

              <div className="sen-side-foot">
                <div className="sen-side-block">
                  <div className="sen-mc-head">
                    <h2 id="sen-mc-h">All together (Monte Carlo)</h2>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={cfg.mc.on}
                      aria-labelledby="sen-mc-h"
                      className={`sen-switch${cfg.mc.on ? " is-on" : ""}`}
                      onClick={() => update((c) => ({ ...c, mc: { ...c.mc, on: !c.mc.on } }))}
                    >
                      <i />
                    </button>
                  </div>
                  <label className={`sen-samples${cfg.mc.on ? "" : " is-off"}`}>
                    <span>
                      <strong>{cfg.mc.samples}</strong> samples, uniform within each range
                    </span>
                    <input
                      type="range"
                      min={SAMPLES.min}
                      max={SAMPLES.max}
                      step={SAMPLES.step}
                      value={cfg.mc.samples}
                      disabled={!cfg.mc.on}
                      aria-label="Monte Carlo samples"
                      onChange={(e) => {
                        const samples = Number(e.target.value);
                        update((c) => ({ ...c, mc: { ...c.mc, samples } }));
                      }}
                    />
                    <span className="sen-samples-scale" aria-hidden="true">
                      <span>{SAMPLES.min}</span>
                      <span>{SAMPLES.max}</span>
                    </span>
                  </label>
                </div>

                <div className="sen-run">
                  {run.pending ? (
                    <button type="button" className="btn btn-soft ta-btn ta-soft sen-run-btn" onClick={run.cancel}>
                      <Spinner size={16} />
                      Cancel
                    </button>
                  ) : (
                    <button
                      type="button"
                      className={`btn btn-ink ta-btn ta-ink sen-run-btn${run.stale || !run.result ? " is-due" : ""}`}
                      disabled={!req}
                      onClick={run.run}
                    >
                      <Retry size={15} />
                      {run.stale || !run.result ? "Run" : "Run again"}
                    </button>
                  )}
                  <span className="sen-run-note" role="status">
                    {run.pending && run.startedAt != null ? (
                      <>
                        Running about {estimate} model runs… <Elapsed since={run.startedAt} />
                      </>
                    ) : invalid ? (
                      "Fix the ranges marked in red to run."
                    ) : run.stale ? (
                      `Changed since the last run: about ${estimate} model runs.`
                    ) : run.result ? (
                      `Up to date: ${run.result.data.runs} model runs in ${trimNum(run.result.data.seconds, 1)} s.`
                    ) : (
                      `About ${estimate} model runs.`
                    )}
                  </span>
                </div>
              </div>
            </aside>
          </div>

          {run.error && !run.pending ? (
            <ErrorState message={`The sensitivity run failed: ${run.error.message}`} onRetry={run.run} />
          ) : result && output && outKey ? (
            <section
              className={`sen-card sen-results ta-rise${run.pending ? " is-pending" : ""}${run.stale ? " is-stale" : ""}`}
              aria-labelledby="sen-res-h"
              aria-busy={run.pending}
            >
              <header className="sen-card-head sen-res-head">
                <div className="sen-res-title">
                  <h2 id="sen-res-h">
                    {result.design}: {lowerFirst(output.label)}
                  </h2>
                  <span className="sen-card-sub">
                    base {fmtOut(output, result.base[outKey])} · {result.runs} model runs in {trimNum(result.seconds, 1)} s · run {run.result!.n}
                  </span>
                </div>
                {resultDesign && (
                  <span className="sen-prov">
                    <ProvenanceChip source={provenanceOf(resultDesign, "economics")} detail="The runs recompute the year and the economics around this design" />
                  </span>
                )}
              </header>
              {run.stale && (
                <div className="sen-stale" role="status">
                  <span>
                    {result.design !== design.id
                      ? `These results are for ${result.design}, not ${design.id}.`
                      : "These results are for the settings before your changes."}
                  </span>
                  {req && !run.pending && (
                    <button type="button" className="link-btn" onClick={run.run}>
                      Run now
                    </button>
                  )}
                </div>
              )}
              {run.pending && (
                <div className="sen-pending" role="status">
                  <Spinner size={18} />
                  Running…
                </div>
              )}
              {shownOutputs.length > 1 && (
                <div className="sen-outs" role="radiogroup" aria-label="Output shown">
                  {shownOutputs.map((o) => (
                    <button
                      key={o}
                      type="button"
                      role="radio"
                      aria-checked={o === outKey}
                      className={`sen-pill ta-btn${o === outKey ? " is-on" : ""}`}
                      onClick={() => setOutPick(o)}
                    >
                      {outByKey.get(o as SensOutput["key"])?.label ?? o}
                    </button>
                  ))}
                </div>
              )}
              <div className="sen-res-grid">
                <figure className="sen-fig">
                  <figcaption>
                    <h3>One at a time</h3>
                    <span>each parameter to the ends of its range, the rest as designed</span>
                  </figcaption>
                  <Tornado rows={tornado} output={output} base={result.base[outKey] ?? null} ranges={ranges} catalogue={paramByKey} design={resultDesign?.uid || result.design} />
                </figure>
                <figure className="sen-fig">
                  <figcaption>
                    <h3>Across each range</h3>
                    <span>five points from the low end to the high end</span>
                  </figcaption>
                  <Spider lines={spiderLines(result, outKey)} output={output} base={result.base[outKey] ?? null} slots={cfg.slots} catalogue={paramByKey} />
                </figure>
                <figure className={`sen-fig${shownOutputs.length > 1 ? "" : " is-wide"}`}>
                  <figcaption>
                    <h3>All together</h3>
                    <span>{result.monte_carlo ? `${result.monte_carlo.samples} samples, every parameter drawn at once` : "Monte Carlo was off for this run"}</span>
                  </figcaption>
                  {mc && result.monte_carlo ? (
                    <Histogram mc={mc} output={output} base={result.base[outKey] ?? null} samples={result.monte_carlo.samples} wide={shownOutputs.length <= 1} />
                  ) : (
                    <p className="sen-note">
                      {result.monte_carlo ? "No samples for this output." : "Turn on Monte Carlo and run to see the spread with every parameter uncertain at once."}
                    </p>
                  )}
                </figure>
                {shownOutputs.length > 1 && (
                  <figure className="sen-fig">
                    <figcaption>
                      <h3>Who moves what</h3>
                      <span>each parameter's share of each output's swing</span>
                    </figcaption>
                    <SwingHeatmap
                      result={result}
                      outputs={shownOutputs.map((o) => outByKey.get(o as SensOutput["key"])).filter((o): o is SensOutput => !!o)}
                      current={outKey}
                      onPick={setOutPick}
                    />
                  </figure>
                )}
              </div>
            </section>
          ) : (
            <section className="sen-card sen-results" aria-label="Results loading" role="status">
              <div className="sen-res-grid">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="sen-fig">
                    <Skeleton width="40%" height={14} />
                    <Skeleton height={200} radius={14} />
                  </div>
                ))}
              </div>
              <span className="sen-pending-text">{run.pending ? "Running the first sensitivity…" : invalid ? "Fix the ranges to run." : "Press Run to see what drives the result."}</span>
            </section>
          )}
          {threadId && <OutagesCard threadId={threadId} design={design.id} />}
        </>
      )}
    </TabFrame>
  );
}
