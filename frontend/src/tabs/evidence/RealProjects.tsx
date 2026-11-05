// Real projects (2 Nov): two Dutch doublets' published inputs run through our doublet model and
// set against their published figures, each row with whether it is a check at all.

import type { RealCheck } from "../../workbench";

const fmt = (x: number | null, d = 1) => (x == null ? "–" : x.toLocaleString("en-GB", { maximumFractionDigits: d }));

export function RealProjects({ checks }: { checks: RealCheck[] }) {
  return (
    <section id="ev-real" className="ev-card ev-real" aria-labelledby="ev-real-h">
      <header className="ev-card-head">
        <h2 id="ev-real-h">Real projects</h2>
        <p className="ev-sub">Published inputs of two Dutch doublets (NLOG) run through Dioscuri&rsquo;s doublet model, and a geothermal absorption chiller (Oregon Tech) against our cooling model, each set against its published figures.</p>
      </header>
      {checks.map((c) => (
        <div key={`${c.key}-${c.case}`} className="ev-real-project">
          <h3>
            {c.name}
            {c.case && c.key === "trias_westland" ? <span className="ev-real-case"> · {c.case}</span> : null}
          </h3>
          <p className="ev-real-src">{c.source}</p>
          <table className="ev-real-table">
            <thead>
              <tr>
                <th scope="col">Figure</th>
                <th scope="col">Ours</th>
                <th scope="col">Published</th>
                <th scope="col">Check</th>
              </tr>
            </thead>
            <tbody>
              {c.rows.map((r) => (
                <tr key={r.quantity}>
                  <th scope="row">{r.quantity}</th>
                  <td>
                    {fmt(r.ours)} {r.unit}
                  </td>
                  <td>{r.theirs == null ? "not given" : `${fmt(r.theirs)} ${r.unit}`}</td>
                  <td className={r.agree === true ? "ok" : r.agree === false ? "bad" : "muted"}>
                    {r.agree === true ? `agrees (${r.diff_pct! > 0 ? "+" : ""}${fmt(r.diff_pct)} %)` : r.agree === false ? `differs (${fmt(r.diff_pct)} %)` : r.note || "not judged"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {c.assumed && <p className="ev-real-note">Assumed where the documents are silent: {c.assumed}.</p>}
        </div>
      ))}
    </section>
  );
}
