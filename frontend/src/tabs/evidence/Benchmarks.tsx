// The benchmark tables of hackathon/evals/BENCHMARKS.md, as the server parsed them: each with
// its section title (and the decision records it cites), numbers right-aligned in tabular
// figures, model ids in mono.

import type { Benchmark } from "../../workbench";
import { cleanCell, cleanTitle, numericColumns, splitModels } from "./model";

function Cell({ value }: { value: string | number }) {
  const text = cleanCell(value);
  const parts = splitModels(text);
  if (parts.length === 1 && !parts[0].model) return <>{text}</>;
  return (
    <>
      {parts.map((p, i) =>
        p.model ? (
          <code key={i} className="ev-model">
            {p.text}
          </code>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </>
  );
}

function Table({ b, index }: { b: Benchmark; index: number }) {
  const { text, refs } = cleanTitle(b.title);
  const numeric = numericColumns(b);
  const id = `ev-bm-${index}`;
  const wide = b.columns.length >= 4 || b.rows.some((r) => r.some((c) => String(c).length > 48));
  return (
    <article className={`ev-bm${wide ? " is-wide" : ""}`} aria-labelledby={id}>
      <div className="ev-bm-head">
        <h3 id={id}>{text}</h3>
        {refs.map((r) => (
          <span key={r} className="tag tag-grey" title={`The decision record ${r} in hackathon/docs/decisions`}>
            {r}
          </span>
        ))}
      </div>
      <div className="ev-scroll">
        <table className="ev-table">
          <thead>
            <tr>
              {b.columns.map((c, i) => (
                <th key={i} scope="col" className={numeric[i] ? "is-num" : undefined}>
                  {cleanCell(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {b.rows.map((row, r) => (
              <tr key={r} className={b.emphasis?.includes(r) ? "is-chosen" : undefined}>
                {b.columns.map((_, c) => {
                  const v = row[c] ?? "";
                  return c === 0 ? (
                    <th key={c} scope="row">
                      <Cell value={v} />
                    </th>
                  ) : (
                    <td key={c} className={numeric[c] ? "is-num" : String(v).length > 40 ? "long" : undefined}>
                      <Cell value={v} />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {b.note && <p className="ev-note">{cleanCell(b.note)}</p>}
    </article>
  );
}

export function Benchmarks({ benchmarks }: { benchmarks: Benchmark[] }) {
  return (
    <section id="ev-benchmarks" className="ev-card" aria-labelledby="ev-bm-h">
      <div className="ev-card-head">
        <h2 id="ev-bm-h">Model benchmarks</h2>
        <span className="ev-muted">Which local model does each job, and the measurements behind the choice (hackathon/evals/BENCHMARKS.md)</span>
      </div>
      {benchmarks.length === 0 ? (
        <p className="ev-none">No benchmark tables yet.</p>
      ) : (
        <div className="ev-bms">
          {benchmarks.map((b, i) => (
            <Table key={`${i}-${b.title}`} b={b} index={i} />
          ))}
        </div>
      )}
    </section>
  );
}
