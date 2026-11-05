// Unplanned outages (2 Nov): the design's units fail at random through 1,000 drawn years, each
// at its sourced rate for its repair time, and every year with failures is run. Four figures
// lead (how often heat runs short, how much in a bad year, what failures cost on average and in
// a bad year); a bar per band of heat short shows the spread; the worst case (a doublet out 35
// days in the coldest weeks) stands apart. A switch compares with and without a spare ESP on
// the shelf (a doublet out 7 days, or about four months waiting for a new pump). It starts off:
// no design pays for a spare, so the years are drawn as the design is built (4 Nov), and the
// N-1-or-risk panel below follows the same switch.

import { useEffect, useState } from "react";

import { getOutages, getRisk, type OutagesView, type RiskView } from "../../workbench";
import { RiskCurve } from "./RiskCurve";

const fmt = (x: number, d = 0) => x.toLocaleString("en-GB", { maximumFractionDigits: d, minimumFractionDigits: 0 });
const pct = (x: number) => `${fmt(x * 100, x < 0.1 && x > 0 ? 1 : 0)}%`;

const UNIT_WORDS: Record<string, string> = {
  "heat exchanger": "Heat exchanger",
  "heat pump": "Heat pump",
  boiler: "Boiler",
  "boiler unit": "Boiler units (all of them)",
  "electric boiler": "Electric boiler",
  "electric boiler unit": "Electric boiler units (all of them)",
  chillers: "Electric chillers",
  "chiller unit": "Chiller units (all of them)",
  absorption: "Absorption chiller",
};
const unitWords = (u: string) => (u.startsWith("doublet ") ? `ESP, ${u}` : (UNIT_WORDS[u] ?? u));

function Bars({ view }: { view: OutagesView }) {
  const { edges_mwh: edges, years } = view.histogram;
  const top = Math.max(1, ...years);
  return (
    <figure className="out-bars" aria-label="Years by heat not delivered">
      <div className="out-bars-plot" role="list">
        {years.map((n, i) => {
          const label = i === 0 ? "None" : `${fmt(edges[i])}–${fmt(edges[i + 1])} MWh`;
          return (
            <div key={i} className={`out-bar${i === 0 ? " is-none" : ""}`} role="listitem" title={`${label}: ${fmt(n)} of ${fmt(view.years)} years`}>
              <span className="out-bar-fill" style={{ height: `${Math.max(n > 0 ? 3 : 0, (n / top) * 100)}%` }} />
              <span className="out-bar-n">{n > 0 ? fmt(n) : ""}</span>
            </div>
          );
        })}
      </div>
      <figcaption>
        Years by heat not delivered: the first bar is the years with none, then bands up to the worst year ({fmt(edges.at(-1) ?? 0)} MWh).
      </figcaption>
    </figure>
  );
}

export function OutagesCard({ threadId, design }: { threadId: string; design: string }) {
  const [spare, setSpare] = useState(false);
  const [view, setView] = useState<OutagesView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    setBusy(true);
    setError(null);
    void getOutages(threadId, design, spare, ctl.signal).then((r) => {
      if (ctl.signal.aborted) return;
      setBusy(false);
      if (r.ok) setView(r.data);
      else setError(r.message);
    });
    return () => ctl.abort();
  }, [threadId, design, spare]);

  return (
    <section className="sen-card out-card ta-rise" aria-labelledby="out-h" aria-busy={busy}>
      <header className="sen-card-head out-head">
        <div>
          <h2 id="out-h">Unplanned outages</h2>
          <span className="sen-card-sub">
            {view ? `${fmt(view.years)} years drawn: each unit fails at random at its rate, for its repair time, and each year is run` : "Drawing 1,000 years…"}
          </span>
        </div>
        <label className="out-switch">
          <input type="checkbox" role="switch" checked={spare} onChange={(e) => setSpare(e.target.checked)} />
          <span className="out-switch-track" aria-hidden="true">
            <span className="out-switch-thumb" />
          </span>
          Spare ESP on the shelf
          <span className="out-switch-hint">{spare ? "an ESP swap takes 7 days" : "as built: a new ESP takes about four months"}</span>
        </label>
      </header>
      {error && <p className="out-error">The outages couldn't be run: {error}</p>}
      {view && (
        <>
          <div className={`out-tiles${busy ? " is-busy" : ""}`}>
            <div className={`out-tile${view.heat_mwh.share_above_zero > 0 ? " is-warn" : " is-ok"}`}>
              <span className="out-tile-cap">Years with heat short</span>
              <strong>{pct(view.heat_mwh.share_above_zero)}</strong>
              <span className="out-tile-sub">{view.heat_mwh.share_above_zero > 0 ? `${fmt(view.heat_mwh.mean)} MWh a year on average` : view.reliable ? "every day met: any one unit can be out" : "every day met in every year drawn"}</span>
            </div>
            <div className="out-tile">
              <span className="out-tile-cap">Heat short, 1 year in 10</span>
              <strong>
                {fmt(view.heat_mwh.p90)}
                <small> MWh</small>
              </strong>
              <span className="out-tile-sub">worst year {fmt(view.heat_mwh.max)} MWh</span>
            </div>
            <div className="out-tile">
              <span className="out-tile-cap">Failures cost, on average</span>
              <strong>
                {fmt(view.total_keur.mean)}
                <small> k€ a year</small>
              </strong>
              <span className="out-tile-sub">
                running {fmt(view.extra_keur.mean)}
                {view.grid_keur && view.grid_keur.mean > 0.5 ? ` (of it the grid contract ${fmt(view.grid_keur.mean)})` : ""}, repairs {fmt(view.repair_keur.mean)}
                {view.lost_keur > 0.5 ? `, heat not sold ${fmt(view.lost_keur)}` : ""}
              </span>
            </div>
            <div className="out-tile">
              <span className="out-tile-cap">Failures cost, 1 year in 10</span>
              <strong>
                {fmt(view.total_keur.p90)}
                <small> k€ or more</small>
              </strong>
              <span className="out-tile-sub">worst year {fmt(view.total_keur.max)} k€</span>
            </div>
          </div>
          <div className="out-grid">
            {view.heat_mwh.share_above_zero > 0 ? (
              <Bars view={view} />
            ) : (
              <div className="out-none">
                <strong>Heat never ran short in the {fmt(view.years)} years drawn.</strong>
                <span>Every failure, alone or at the same time as another, left enough of the plant to meet each day; failures cost money (the boilers burn more gas), not heat.</span>
              </div>
            )}
            <div className="out-side">
              {view.worst && (
                <div className={`out-worst${view.worst.heat_mwh > 0.5 ? " is-warn" : ""}`}>
                  <span className="out-tile-cap">Worst case</span>
                  <p>
                    The doublet out {view.worst.days} days in the coldest weeks ({view.worst.from} to {view.worst.to}):{" "}
                    {view.worst.heat_mwh > 0.5 ? <strong>{fmt(view.worst.heat_mwh)} MWh of heat short</strong> : <strong>every day still met</strong>}, running costs {fmt(view.worst.extra_keur)} k€ more
                    {view.worst.grid_keur && view.worst.grid_keur > 0.5 ? ` (of it ${fmt(view.worst.grid_keur)} k€ for the grid contract, past 600 hours)` : ""}.
                  </p>
                </div>
              )}
              <table className="out-rates">
                <caption>Failures a year in the years drawn</caption>
                <tbody>
                  {Object.entries(view.failures).map(([u, n]) => (
                    <tr key={u}>
                      <th scope="row">{unitWords(u)}</th>
                      <td>{fmt(n, 3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <details className="out-sources">
            <summary>Where the failure rates and repair times come from</summary>
            <ul>
              {Object.entries(view.sources).map(([k, text]) => (
                <li key={k}>{text}</li>
              ))}
            </ul>
          </details>
          <p className="out-foot">
            A failure of a few hours puts its unit out for that whole day with that chance, so the days out are right on average.
            {view.not_drawn && view.not_drawn.length > 0 ? ` Not drawn, with no published failure rate: ${view.not_drawn.join(", ")}.` : ""} Run in {fmt(view.seconds, 2)} s.
          </p>
          <RiskPanel threadId={threadId} design={design} spare={spare} />
        </>
      )}
    </section>
  );
}

/**
 * N-1 or risk (3 Nov): the backup sized for any one unit out on the coldest day (N-1), beside the
 * smallest backup that keeps the days short of heat to one in ten years over the drawn years.
 * Both plans are priced a year the same way (4 Nov: capital annuity, O&M and the grid charge, so
 * "What N-1 buys" sets k€ a year against k€ a year), over years drawn with the card's spare ESP
 * switch.
 */
function RiskPanel({ threadId, design, spare }: { threadId: string; design: string; spare: boolean }) {
  const [view, setView] = useState<RiskView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setView(null);
    setError(null);
  }, [threadId, design, spare]);
  const run = async () => {
    setBusy(true);
    setError(null);
    const r = await getRisk(threadId, design, spare);
    setBusy(false);
    if (r.ok) setView(r.data);
    else setError(r.message);
  };
  return (
    <div className="risk">
      <div className="risk-head">
        <div>
          <h3>N-1, or sized by risk</h3>
          <p>
            N-1 sizes the backup for any one unit out on the coldest day. Sized by risk, it is the smallest backup that keeps the days short of heat to one in ten years over the drawn years
            {spare ? ", with a spare ESP on the shelf in both plans" : ", as built: no spare ESP"}.
          </p>
        </div>
        {!view && (
          <button type="button" className="btn btn-soft ta-btn ta-soft" disabled={busy} onClick={() => void run()}>
            {busy ? "Running the years…" : "Size the backup by risk"}
          </button>
        )}
      </div>
      {error && <p className="out-error">{error}</p>}
      {view && <RiskTiles view={view} />}
      {view && (
        <>
          <RiskCurve view={view} />
          <p className="out-foot">{view.source}. Run in {fmt(view.seconds, 1)} s.</p>
        </>
      )}
    </div>
  );
}

/** The two plans and what N-1 buys, each a year (pure: the tests render it). */
export function RiskTiles({ view }: { view: RiskView }) {
  const same = view.risk_mw >= view.n1_mw - 1e-6;
  const n1 = view.n1_plan;
  const risk = view.risk_plan;
  const fewer = view.at_risk.lole_days - view.at_n1.lole_days;
  const perYear = (plan?: RiskView["n1_plan"]) =>
    plan ? `${fmt(plan.backup_keur)} k€ a year (capital ${fmt(plan.capital_keur)}, O&M ${fmt(plan.om_keur)}${plan.grid_keur > 0.05 ? `, grid ${fmt(plan.grid_keur)}` : ""})` : "";
  return (
    <div className="risk-tiles">
      <div className="risk-tile">
        <span className="k">{view.reliable ? "N-1 (this design)" : "This design"}</span>
        <strong>
          {fmt(view.n1_mw, 1)} <span className="u">MW {view.unit_words}</span>
        </strong>
        <span className="s">
          {fmt(view.at_n1.lole_days, 2)} days short a year{n1 ? ` · ${perYear(n1)}` : ""}
        </span>
      </div>
      <div className="risk-tile is-risk">
        <span className="k">Sized by risk</span>
        <strong>
          {fmt(view.risk_mw, 1)} <span className="u">MW</span>
        </strong>
        <span className="s">
          {same
            ? `nothing smaller keeps to one day in ten years (${fmt(view.at_risk.lole_days, 2)} days short a year)`
            : `${fmt(view.at_risk.lole_days, 2)} days short a year · ${fmt(view.at_risk.eens_mwh, 1)} MWh not delivered${risk ? ` · ${perYear(risk)}` : ""}`}
        </span>
      </div>
      <div className="risk-tile">
        <span className="k">What N-1 buys</span>
        {same ? (
          <>
            <strong>
              0 <span className="u">k€ a year</span>
            </strong>
            <span className="s">the risk target needs the N-1 size here</span>
          </>
        ) : view.n1_extra_keur_per_year !== undefined ? (
          <>
            <strong>
              {fmt(view.n1_extra_keur_per_year)} <span className="u">k€ a year more</span>
            </strong>
            <span className="s">
              for {fmt(fewer, 2)} fewer days short a year (the heat not delivered worth {fmt(view.lost_keur_per_year, 1)} k€ a year at the lost sale)
            </span>
          </>
        ) : (
          <>
            <strong>
              {fmt(view.capex_saved_meur, 2)} <span className="u">M€ more capital</span>
            </strong>
            <span className="s">for {fmt(fewer, 2)} fewer days short a year</span>
          </>
        )}
      </div>
    </div>
  );
}
