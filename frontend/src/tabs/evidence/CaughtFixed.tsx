// Caught and fixed (src/gemini_agent/caught.py, data/caught_and_fixed.json): the failures the team
// found in GEMINI's physics, in Dioscuri's model and costs, in the agent and in the app, and
// fixed. Tiles count them by group with how many a test guards; a row per failure opens to what
// failed, how it was found, the fix (patch, commit, ADR) and the tests that guard it. The same
// list is the report's hackathon/docs/caught_and_fixed.md.

import { useMemo, useState } from "react";

import type { Caught, CaughtItem } from "../../workbench/basis";

const GROUP_COLOR: Record<string, string> = {
  gemini: "#C24E1C",
  model: "#0A6F7C",
  costs: "#8A5A00",
  agent: "#5B3FA6",
  app: "#2363A6",
};
const SHORT: Record<string, string> = { gemini: "GEMINI", model: "Model", costs: "Costs", agent: "Agent", app: "App" };
const TILE: Record<string, string> = { gemini: "GEMINI's physics", model: "Our plant model", costs: "Costs", agent: "The agent", app: "The app" };

/** "unit_test/gemini_agent/test_x.py::TestY::test_z" → "test_x.py · test_z". */
function testName(t: string): { file: string; name: string } {
  const [path, ...rest] = t.split("::");
  return { file: path.split("/").pop() ?? path, name: rest[rest.length - 1] ?? "" };
}

export function CaughtFixed({ caught }: { caught: Caught }) {
  const [group, setGroup] = useState<string | null>(null);
  const [guardedOnly, setGuardedOnly] = useState(false);
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const items = useMemo(() => caught.items.filter((it) => (!group || it.group === group) && (!guardedOnly || it.tests.length > 0)), [caught, group, guardedOnly]);
  const toggle = (id: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const allOpen = items.length > 0 && items.every((it) => open.has(it.id));
  return (
    <section id="ev-caught" className="ev-card ev-caught" aria-labelledby="ev-caught-h">
      <header className="ev-card-head">
        <h2 id="ev-caught-h">Caught and fixed</h2>
        <p className="ev-sub">
          {caught.total} failures we found and fixed: in GEMINI&rsquo;s physics code, in our own model and costs, in the agent and in the app. {caught.guarded} are guarded by a test that fails if they come back.
          {caught.avoided ? ` ${caught.avoided} GEMINI bugs are not patched but kept out of every design, and say how.` : ""} The GEMINI bugs keep their codes F1–F10; the agent&rsquo;s failures are U1 and on.
        </p>
      </header>

      <div className="ev-cf-tiles" role="list" aria-label="By where the failure was">
        {caught.groups.map((g) => (
          <button
            key={g.key}
            type="button"
            role="listitem"
            className={`ev-cf-tile ta-btn${group === g.key ? " on" : ""}`}
            aria-pressed={group === g.key}
            onClick={() => setGroup((v) => (v === g.key ? null : g.key))}
          >
            <span className="ev-cf-tile-top" title={g.label}>
              <i style={{ background: GROUP_COLOR[g.key] ?? "#8A959E" }} aria-hidden="true" />
              {TILE[g.key] ?? g.label}
            </span>
            <span className="ev-cf-tile-num">{g.total}</span>
            <span className="ev-cf-meter" aria-hidden="true">
              <span className="ta-grow" style={{ width: `${(g.guarded / Math.max(1, g.total)) * 100}%`, background: GROUP_COLOR[g.key] ?? "#8A959E" }} />
            </span>
            <span className="ev-cf-tile-sub">
              {g.guarded} of {g.total} guarded by a test
            </span>
          </button>
        ))}
      </div>

      <div className="ev-cf-bar">
        <span className="ev-muted">
          {items.length} shown{group ? ` · ${SHORT[group] ?? group}` : ""}
        </span>
        <label className="ev-cf-check">
          <input type="checkbox" checked={guardedOnly} onChange={(e) => setGuardedOnly(e.target.checked)} /> Only those a test guards
        </label>
        {group && (
          <button type="button" className="link-btn" onClick={() => setGroup(null)}>
            Show every group
          </button>
        )}
        <button type="button" className="link-btn ev-cf-all" onClick={() => setOpen(allOpen ? new Set() : new Set(items.map((it) => it.id)))}>
          {allOpen ? "Close all" : "Open all"}
        </button>
      </div>

      <ol className="ev-cf-list">
        {items.map((it) => (
          <CaughtRow key={it.id} item={it} open={open.has(it.id)} onToggle={() => toggle(it.id)} />
        ))}
      </ol>
      <p className="ev-muted ev-cf-foot">
        The same list, for the report: <span className="ev-model">hackathon/docs/caught_and_fixed.md</span> (updated {caught.updated}).
      </p>
    </section>
  );
}

function CaughtRow({ item, open, onToggle }: { item: CaughtItem; open: boolean; onToggle: () => void }) {
  const color = GROUP_COLOR[item.group] ?? "#8A959E";
  const n = item.tests.length;
  const panel = `ev-cf-${item.id}`;
  return (
    <li className={`ev-cf-row${open ? " open" : ""}`}>
      <button type="button" className="ev-cf-head" aria-expanded={open} aria-controls={panel} onClick={onToggle}>
        <span className="ev-cf-id" style={{ color, borderColor: `${color}55`, background: `${color}12` }}>
          {item.id}
        </span>
        <span className="ev-cf-title">
          {item.title}
          {item.status === "avoided" && <span className="ev-cf-avoided">avoided, not patched</span>}
        </span>
        <span className={`ev-cf-guard${n ? " ok" : ""}`} title={n ? item.tests.join("\n") : "No test guards it"}>
          {n ? (
            <>
              <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {n} test{n > 1 ? "s" : ""}
            </>
          ) : (
            "no test"
          )}
        </span>
        <svg className="ev-cf-chev" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div id={panel} className="ev-cf-body">
          <dl>
            <dt>What failed</dt>
            <dd>{item.failed}</dd>
            <dt>How we found it</dt>
            <dd>
              {item.found}
              {item.source_label ? ` (there: ${item.source_label.replace(/ in .*$/, "")})` : ""} <span className="ev-model">{item.found_in}</span>
            </dd>
            <dt>The fix</dt>
            <dd>
              {item.fix}
              <span className="ev-cf-refs">
                {item.patch && <span className="ev-cf-ref">patch {item.patch.replace(/\.diff$/, "")}</span>}
                {item.commit && <span className="ev-cf-ref mono">commit {item.commit}</span>}
                {item.adr && <span className="ev-cf-ref">{item.adr}</span>}
              </span>
            </dd>
            <dt>Guarded by</dt>
            <dd>
              {n ? (
                <ul className="ev-cf-tests">
                  {item.tests.map((t) => {
                    const { file, name } = testName(t);
                    return (
                      <li key={t} title={t}>
                        <span className="ev-cf-test">{name.replace(/^test_/, "").replace(/_/g, " ")}</span> <span className="ev-muted">{file}</span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <span className="ev-muted">No test guards it yet.</span>
              )}
            </dd>
          </dl>
        </div>
      )}
    </li>
  );
}
