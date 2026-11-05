// GEMINI as released against GEMINI with the team's fixes: per design, each quantity's released
// and fixed value with the released one's relative error on a diverging bar (left: released too
// low, right: too high, clipped at ±100% with a break mark), the bugs behind it as chips, and the
// list of patches.

import { useState } from "react";

import { menuProps } from "../../menu";
import { AskButton, type Evidence } from "../../workbench";
import { bugRefs, divergingBar, fmtError, fmtUnit, fmtValue, patchTitle, relativeError } from "./model";

type Gemini = Evidence["gemini"];

/** The diverging pair: released lower (cool blue) and released higher (warm), grey midpoint. */
const LOW = "#3F7FE0";
const HIGH = "#C24E1C";

export function GeminiImpact({ gemini }: { gemini: Gemini }) {
  const designs = gemini.bug_impact;
  const [pick, setPick] = useState(0);
  const impact = designs[Math.min(pick, designs.length - 1)];
  return (
    <section id="ev-gemini" className="ev-card" aria-labelledby="ev-gm-h">
      <div className="ev-card-head">
        <h2 id="ev-gm-h">GEMINI, as released and with our fixes</h2>
        <span className="tag tag-teal">GEMINI {gemini.version}</span>
        <span className="tag tag-grey">
          {gemini.patches.length} patch{gemini.patches.length === 1 ? "" : "es"}
        </span>
      </div>

      {impact ? (
        <div className="ev-gm">
          <div className="ev-gm-bar">
            <p className="ev-gm-lead">What GEMINI as released would have given for this design, next to GEMINI with the team's fixes.</p>
            {designs.length > 1 && (
              <div className="ev-seg" role="group" aria-label="Design">
                {designs.map((d, i) => (
                  <button key={d.design} type="button" aria-pressed={i === pick} onClick={() => setPick(i)}>
                    {d.design}
                  </button>
                ))}
              </div>
            )}
          </div>
          <ImpactChart impact={impact} patches={gemini.patches} />
        </div>
      ) : (
        <p className="ev-none">No design to compare yet.</p>
      )}

      {gemini.patches.length > 0 && (
        <div className="ev-patches">
          <h3>The patches</h3>
          <ol className="ev-patch-list">
            {gemini.patches.map((p, i) => {
              const t = patchTitle(p.title);
              const n = p.file.match(/^(\d+)_/)?.[1] ?? String(i + 1).padStart(2, "0");
              return (
                <li key={p.file} className="ev-patch" {...menuProps({ kind: "source", title: t.text, citation: `GEMINI patch ${p.file}: ${p.title}` })}>
                  <span className="ev-patch-n" aria-hidden="true">
                    {n}
                  </span>
                  <span className="ev-patch-main">
                    <span className="ev-patch-title">
                      {t.text}
                      {t.code && <span className="ev-bug-code">{t.code}</span>}
                    </span>
                    <code className="ev-patch-file">{p.file}</code>
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}

function ImpactChart({ impact, patches }: { impact: Gemini["bug_impact"][number]; patches: Gemini["patches"] }) {
  const rows = impact.rows.map((r) => ({ ...r, err: relativeError(r.released, r.fixed) }));
  const compared = rows.filter((r) => r.err !== null);
  const off = compared.filter((r) => Math.abs(r.err!) > 0.1).length;
  const hot = rows.find((r) => /supply temperature/i.test(r.quantity) && r.released !== null && r.fixed !== null);
  const worst = [...compared].sort((a, b) => Math.abs(b.err!) - Math.abs(a.err!))[0];
  return (
    <>
      <div className="ev-gm-sum">
        <span className="ev-gm-big">
          <strong>{off}</strong> of {compared.length} quantities off by more than 10% in GEMINI as released
        </span>
        {hot ? (
          <AskButton
            context={`${impact.design}'s heat pump in GEMINI as released: supply temperature ${fmtValue(hot.released)} ${fmtUnit(hot.unit)}, against ${fmtValue(hot.fixed)} ${fmtUnit(hot.unit)} with the team's fixes (Evidence tab)`}
            question={`why does the released heat pump give ${Math.round(hot.released!)} ${fmtUnit(hot.unit)}?`}
            label={`Why does the released heat pump give ${Math.round(hot.released!)} ${fmtUnit(hot.unit)}?`}
          />
        ) : (
          worst && (
            <AskButton
              context={`${impact.design}'s ${worst.quantity.toLowerCase()} in GEMINI as released, ${fmtValue(worst.released)} against ${fmtValue(worst.fixed)} ${fmtUnit(worst.unit)} with the team's fixes (Evidence tab)`}
              question="which bug causes this, and how does the fix change it?"
            />
          )
        )}
      </div>
      <div className="ev-impact" role="table" aria-label={`GEMINI as released against fixed, ${impact.design}`}>
        <div className="ev-ir ev-ir-head" role="row">
          <span role="columnheader">Quantity</span>
          <span role="columnheader" className="is-num">
            Released
          </span>
          <span role="columnheader" className="is-num">
            Fixed
          </span>
          <span role="columnheader" className="ev-ir-axis">
            <span className="ev-axis-cap">
              <span>
                <i style={{ background: LOW }} />
                released too low
              </span>
              <span>
                released too high
                <i style={{ background: HIGH }} />
              </span>
            </span>
            <span className="ev-axis-ticks" aria-hidden="true">
              <span style={{ left: "0%" }}>−100%</span>
              <span style={{ left: "50%" }}>0</span>
              <span style={{ left: "100%" }}>+100%</span>
            </span>
          </span>
          <span role="columnheader">Bugs behind it</span>
        </div>
        {rows.map((r) => {
          const bar = divergingBar(r.err);
          const unit = fmtUnit(r.unit);
          const label = fmtError(r.err);
          return (
            <div key={r.quantity} className="ev-ir" role="row">
              <span role="rowheader" className="ev-ir-q">
                {r.quantity}
                {unit && <span className="ev-unit">{unit}</span>}
              </span>
              <span role="cell" className="is-num ev-ir-rel">
                <span className="ev-ir-tag">released</span>
                {r.released === null ? <span className="ev-muted">not in GEMINI</span> : fmtValue(r.released)}
              </span>
              <span role="cell" className="is-num ev-ir-fix">
                <span className="ev-ir-tag">fixed</span>
                <strong>{fmtValue(r.fixed)}</strong>
              </span>
              <span role="cell" className="ev-ir-bar" aria-label={r.err === null ? "no comparison" : `released ${label} against fixed`}>
                <span className="ev-track">
                  <span className="ev-mid" />
                  {bar.side !== "none" && (
                    <span
                      className={`ev-div ${bar.side}${bar.clipped ? " clipped" : ""}`}
                      style={{ width: `${bar.width / 2}%`, background: bar.side === "neg" ? LOW : HIGH }}
                    />
                  )}
                  <span
                    className={`ev-div-label ${bar.side}`}
                    style={bar.side === "neg" ? { right: `calc(${50 + bar.width / 2}% + 6px)` } : bar.side === "pos" ? { left: `calc(${50 + bar.width / 2}% + 6px)` } : { left: "calc(50% + 8px)" }}
                  >
                    {r.err === null ? (r.released === null ? "Dioscuri's own model" : "–") : r.err === 0 ? "same" : label}
                  </span>
                </span>
              </span>
              <span role="cell" className="ev-ir-bugs">
                {bugRefs(r.bugs, patches).map((b) => (
                  <span key={b.text} className="ev-bug" title={b.patch ? `Fixed by ${b.patch.file}: ${b.patch.title}` : undefined}>
                    {b.code ? (
                      <>
                        <b>{b.code}</b>
                        {b.text.slice(b.code.length)}
                      </>
                    ) : (
                      b.text
                    )}
                  </span>
                ))}
              </span>
            </div>
          );
        })}
      </div>
    </>
  );
}
