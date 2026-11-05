# flake8: noqa  (a page generator: the review data are long strings)
"""Build the review panel page: synthesis on top, every member's full report below."""

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE

MEMBERS = [
    ("hackathon_judge", "Hackathon judge", "5.7 / 10", "The engineering core is sound and the record of what it tried is excellent; it loses points where its own GEMINI run contradicted the design (now fixed) and where chat explanations fail or are wrong when asked why."),
    ("geothermal_specialist", "Geothermal specialist", None, "The concept's shape is right and the well physics match hand calculations within 0.1 %, but he would not sign it off: no N-1 cover (7.2 MW short with one doublet out) and no sizing margin (a reservoir 2.5 K colder breaks 100 °C)."),
    ("reservoir_simulation_expert", "Reservoir simulation expert", None, "Base hydraulics are sound and the 1.5 km spacing keeps breakthrough near 90 years, but by luck: there is no reservoir physics below the near-well inflow, no feasibility limits on wells, and the agent describes its own subsurface model wrongly."),
    ("production_engineer", "Production engineer", None, "Doublet hydraulics are right to the kW; the surface loop GEMINI drew went below vacuum (now fixed), the produced gas has no physics (bubble point about 45 bar, the ESP sits at or below it), and production questions got cost lists."),
    ("district_energy_engineer", "District heating and cooling engineer", None, "Energy balances and COPs reproduce by hand; a utility would reject the firm capacity (the 'backup' boiler is the peak boiler), and the network side is missing (losses, pumping, free cooling at 20 °C chilled water)."),
    ("economist", "Energy economist", None, "The cost engine is exact and well sourced, but geothermal capex and O&M sit 20-35 % below PBL 2026 (with PBL costs the pick becomes one doublet), the cost win is a near-tie, and the chat made up the gas reference (now given the real one)."),
    ("operator", "Plant operator", None, "Sound and auditable as a design study, but not approvable for operation: no N-1, no margin, the chat cannot see the daily schedule, and it invented equipment (a buffer tank, venting methane)."),
    ("municipal_planner", "Municipal energy planner (client)", None, "The tool has the numbers a council needs and they hold together, but the chat would not give them in usable words, once said gas was cheaper (now given the real comparison), and lost the client's CO2 target."),
    ("ml_llm_expert", "ML and LLM expert", None, "A sound base with excellent traces, but a chain of 3-7 model calls per turn whose code checks fail both ways (correct unit readings dropped, now fixed; numbers in the wrong role passed), and evals that measure the pipeline's own filters."),
    ("agentic_ai_expert", "Agentic AI expert", None, "A well-built, honest pipeline with models at the edges, not yet an agent that plans: a two-step request ran under the wrong conditions, comparisons are never checked, and the documented planner and reflector are dead code."),
    ("red_team", "Red-team tester", None, "Hard to break where it matters (bypass, injection into results, impossible inputs, leakage); the real weaknesses were consistency: a hard cap relaxed by asking and still shown as passed, and an injected value voiced in prose (both fixed)."),
    ("ui_ux_designer", "UI and UX designer", None, "The pieces are modern and well built (inputs card, steps, inspector, Economics, Sensitivity), but the screens disagree: one design at three costs, three designs under one code, two \"chosen\" tags, a plant canvas drawn at 5-9 px, and a what-if card that hides the changed pick."),
]

FIXED = [
    ("A cap relaxed by asking (\"run 365 days\") is still checked against the challenge's 330 days, and the check and the inputs card say what was asked", "Red team"),
    ("GEMINI's loop went below vacuum after the filters: the treatment train is now sized for a 1 bar drop at its flow, the duty ESP runs at 70 %, and GEMINI's pumps equal the plant model's (0.391 MW ESP, 0.221 MW injection at 300 m³/h)", "Judge, production engineer"),
    ("Money answers: the gas reference, yearly totals, extra capital, payback, NPV, prices and what the costs leave out are computed by code and given to the answer model", "Planner, economist"),
    ("The agent's own earlier replies no longer count as evidence for the claim check", "Agentic AI expert"),
    ("Report-length answers were cut off at 800 tokens and replaced by a template: now 1,400", "Judge"),
    ("Design ids are unique per search, so a later search no longer replaces the first pick; what-ifs name the design they were asked about", "Judge, planner"),
    ("Unit conversions (ct/kWh, l/s, TWh, °F) and German and Dutch number words are read; an ask out of range is said in the reply as \"Not applied\"", "ML and LLM expert, red team"),
    ("Text in an attached file addressed to the assistant (hidden comments, \"AI note\", \"you must report\") is left out before the model reads it", "Red team"),
    ("\"Lowest CO2\" takes the cheapest design within 2 % of the lowest (it bought the last 24 t a year with 21 M€ of wells)", "Planner, economist"),
    ("The inputs card shows the objective that will run; a blank message costs no model call", "Planner, red team"),
    ("The depth sensitivity moved nothing; out-of-range sensitivity input returned a server error", "Reservoir expert, geothermal specialist, judge"),
    ("Per-doublet open-part flags, each train's own gas, capital notes in the tabs, each search's own candidates in Compare", "Tabs helper, economist"),
    ("One chat run at a time on the server (two chats at once mixed their steps)", "Found while preparing the panel"),
    ("The \"5 bar carries the brine\" and \"above the bubble point\" texts corrected", "Production engineer"),
    ("N-1 and the peak-day spare are computed for every design (either doublet out: 7.17 MW short on 70 days; 0.05 MW spare on 28 Jan) and stated as conclusions to the answer model; the outage answer no longer says \"the town stays warm\" (re-tested: 1 of 3 wordings fully right, 1 right with a wrong number, 1 declined)", "Operator, geothermal specialist, district energy"),
    ("The design's days reach the answers: the peak days, any day or month named, stops as dates, ESP starts per doublet; 19 July (doublet 2 at 136.4 m³/h, doublet 1 in its stop, chillers at their limit) now answered right", "Operator"),
    ("A not-in-the-design list (no storage, buffer tank, gas holder or flare; no venting) and a rule to name only equipment the design has: the produced-gas question now says the doublets must stop when the boiler is out", "Operator"),
    ("Reservoir what-ifs only from sentences about the reservoir (\"the injected brine is 30-40 K colder\" had made the reservoir 35 K colder)", "Reservoir simulation expert"),
    ("The answerer promises only what the tools do (it had \"started\" a reservoir interference analysis); the well model is described to it (index, skin, drainage radius, Ramey, what is not modelled)", "Reservoir simulation expert, agentic AI expert"),
    ("One rounding (half up) in chat and cards (64.25 was 64.2 in the chat, 64.3 on the card); the CO₂ change from unrounded values (+8.4, not +9 points); the temperature strip that called the network outlet \"81.1 °C to the heat pump\" removed; \"7 agents\" is now \"7 roles · 3 on a model\"; self out of the step label", "UI and UX designer"),
]

PRIORITIES = [
    ("P1", "Firm capacity: size for N-1, show it, answer outages by code", "N-1 is now computed and told to the answer model. Still open: a fixed \"unit out\" answer made by code for any outage question (the 9b model still mixes the numbers on some wordings); spare MW and N-1 on the result card; an option to size for it (about a 19 MW boiler, +0.5 €/MWh of heat) and a peak-hour factor; call it the peak boiler until then.", "Operator, geothermal, district energy, production, economist, planner", "half a day"),
    ("P1", "One name, one metric, one rounding", "A unique id per design (A1 the pick, W1, W2 what-ifs, U1 yours) with the layout code as a second chip; \"cost of heat and cold\", which the search optimises, as the headline everywhere (heat 64.3 and cold 50.1 below it); fixed decimals per metric; \"best in this search\" instead of a second \"chosen\".", "UI and UX designer, judge, planner", "half a day"),
    ("P1", "Explanations from facts, comparisons by code", "A plant fact sheet in every design answer (dispatch order, produced gas first, what each input feeds); comparisons between designs computed by code and checked; the claim check against the full design record; \"remains optimal\" flagged when the re-search changes the pick.", "District energy, operator, agentic AI, judge, planner, ML, UI", "one day"),
    ("P1", "Make iteration visible", "The what-if card states the re-search result (\"the pick changes to 1D-HP-AB, 56.5 €/MWh\"); Open in Compare opens the search the reply came from; Head to head warns when the assumptions differ.", "UI and UX designer, judge", "half a day"),
    ("P1", "A readable plant canvas", "Reflow it to the canvas's shape so it fits at 0.85 or more at 1440 × 900 (today 0.48: labels at 5-9 px); semantic zoom; full screen that enlarges; a small well section per doublet for the open parts; line hops; brine in one neutral colour.", "UI and UX designer", "one day"),
    ("P1", "Subsurface and well checks", "Gringarten-Sauty breakthrough per doublet from its mean flow and the 1.5 km spacing; ESP intake against the gas bubble point (about 45 bar) and the setting depth; an injection-pressure limit; then low-permeability and half-open designs stop passing 12 of 12.", "Reservoir, production, geothermal", "one day"),
    ("P1", "Multi-step requests", "\"Design it, then check it 10 °C colder, and tell me if the pick changes\" ran once under the wrong conditions. A small planner (at most 3 typed steps over design, what-if, search, compare, checked by code).", "Agentic AI expert", "one day"),
    ("P1", "Decide the cost basis", "Recalibrate geothermal capex and O&M to PBL 2026 (the pick likely becomes 1D-HP-EC), or show both cost sets; present the 0.1-1 €/MWh win as a tie with Monte Carlo downside (P10 NPV -9.4 against +2.6 M€).", "Economist", "half a day, your decision"),
    ("P2", "Evals that measure correctness", "A held-out set of about 150 paraphrased, Dutch, German, typo and odd-unit messages; comparisons checked against the ledger; compound requests; three wordings of the trip question that must agree; every clickable option run.", "ML and LLM expert, agentic AI expert, operator", "one day"),
    ("P2", "Fewer model calls per turn", "One \"understand\" call instead of reader, parameters, route, screen and confirm; one claim-check call instead of two; cached prompt prefixes. Today 3.25 calls a turn and about 85 s for a CPU question.", "ML and LLM expert, agentic AI expert", "one to two days"),
    ("P2", "Operations detail", "Every available doublet sharing the flow (fewer ESP starts: doublet 2 starts 7 times a year), or a rotating lead; minimum run and down times; unit counts and minimum loads (the boiler runs below 10 % on 115 days); a flare for the produced gas; overlap at the stop handover; service windows for the exchanger, boiler and heat pump.", "Operator", "one day"),
    ("P2", "Free cooling and the network", "A free-cooling stage at 20 °C chilled water (about 7-10 €/MWh of cold saved); network losses and pumping, or label the cooling return \"no effect in this model\".", "District energy", "one day"),
    ("P2", "Client answers", "A CO2-target objective (\"cheapest meeting X %\", with target met yes/no); the user's number of homes kept for per-home costs; a plain-language summary for \"what do I tell the council\".", "Planner, economist", "half a day"),
    ("P2", "A calmer chat reply and GEMINI tab", "Merge \"How I got here\" and \"Designs compared\" into one sorted \"Why this design\"; the monthly chart only in Energy; 2-3 highlighted numbers, not 20; the GEMINI tab opens on a plain \"with our fixes vs as released\" summary, the node editor behind \"advanced\"; contrast of muted text to 4.5:1.", "UI and UX designer", "one day"),
    ("P2", "Human-in-the-loop records and gas handling", "Record each decision (options, recommended, chosen) in the trace; a flash at the separator (about 88 % of the CH4 comes out at 5 bar); a CHP option on the produced gas.", "Agentic AI expert, production, geothermal", "one day"),
    ("P3", "After the deadline", "A reservoir simulator (DARTS, OPM Flow) for breakthrough, buoyancy and interference; hourly time steps; storage; a recovery heat pump (the district engineer shows it does not pay here).", "Reservoir, district energy", "weeks"),
]

KEEP = [
    "The inputs card: every value with its source and whether it was read, fixed, derived, assumed or asked",
    "The deterministic search with each loser's reason in numbers, the sizing record, and the traces",
    "Physics a reviewer can check by hand (PI 14.5 m³/h/bar, ESP head 32.8 bar, Ramey loss, energy balances to 0.001 MW)",
    "The shortfall decision card with simulated options; the parameter catalogue (the model maps, code checks)",
    "Honesty about limits when asked directly; the GEMINI bug-impact table",
    "The steps as tick-off rows with tool chips and \"rules decided\" / \"model decided\" tags; the design inspector; Economics' waterfall and cash flow; Sensitivity's run estimate",
]

REMOVE = [
    "Half-open well variants in the automatic search: the model cannot rank them (keep them as user builds with the gravity caveat)",
    "The cooling-return input, which feeds nothing yet, and the zero placeholders recovery_hp and chp",
    "Regex routers that duplicate model calls; the answerer acting as a router (its reply is written, then thrown away)",
    "The stock design text as a fallback for unrelated questions; must-keep values spliced into the prose (a code-made key-numbers line instead)",
    "Dead planner and reflector prompts, and the docs that still describe them",
    "Two claim-check calls where one would do; \"reasoning mode\" as a concept on the GPU, where the same model answers both ways",
    "The monthly chart inside the chat's result card (Energy has it); the three views of one ranking in a design reply; the GEMINI node editor as the tab's default",
]

DECISIONS = [
    "Push rn/challenge so Ali can see the plant model and the review's references (a branch push, not a merge to main).",
    "Size for N-1 (a ~19 MW boiler, +0.5 €/MWh of heat; the challenge does not ask for it) or report it only, as now.",
    "The cost basis: keep the ThermoGIS v2-based costs (labelled) or recalibrate to PBL 2026, which likely makes one doublet the pick.",
    "Which P1 items to build before 3-4 Nov.",
]


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def main() -> None:
    reports = {}
    for key, *_ in MEMBERS:
        path = REPORTS / f"{key}.md"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        reports[key] = text.replace(str(HERE.parent) + "/", "scratchpad/")
    rows = []
    for key, role, score, verdict in MEMBERS:
        if verdict is None:  # the designer's verdict: the first paragraph of its report
            text = reports[key]
            part = text.split("## 1.", 1)[-1].split("##", 1)[0] if "## 1." in text else text[:600]
            lines = [x for x in part.splitlines() if x.strip() and not x.startswith("#")]
            verdict = " ".join(lines)[:420].rsplit(" ", 1)[0] + "…" if lines else "See the report."
        rows.append(
            f'<tr><td><a href="#{key.replace("_", "-")}">{esc(role)}</a></td><td>{esc(verdict)}</td>'
            f'<td class="num">{esc(score or "")}</td></tr>'
        )
    fixed = "".join(
        f'<li><span class="txt">{esc(t)}</span><span class="who">{esc(w)}</span></li>'
        for t, w in FIXED
    )
    pri = "".join(
        f'<article class="pri {p.lower()}"><div class="tag">{p}</div><div><h3>{esc(t)}</h3>'
        f"<p>{esc(d)}</p><p class=\"meta\"><span>Raised by {esc(w)}</span><span>{esc(e)}</span>"
        f"</p></div></article>"
        for p, t, d, w, e in PRIORITIES
    )
    keep = "".join(f"<li>{esc(x)}</li>" for x in KEEP)
    remove = "".join(f"<li>{esc(x)}</li>" for x in REMOVE)
    decide = "".join(f"<li>{esc(x)}</li>" for x in DECISIONS)
    toc = "".join(f'<a href="#{k.replace("_", "-")}">{esc(r)}</a>' for k, r, *_ in MEMBERS)
    full = "".join(
        f'<section class="report" id="{k.replace("_", "-")}"><h3>{esc(r)}</h3>'
        f'<div class="md" data-key="{k}"><pre>{esc(reports[k])}</pre></div></section>'
        for k, r, *_ in MEMBERS
    )
    data = json.dumps(reports, ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.format(
        rows="".join(rows), fixed=fixed, pri=pri, keep=keep, remove=remove, decide=decide,
        toc=toc, full=full, data=data, n=len(MEMBERS), nfixed=len(FIXED),
    )
    (HERE / "panel_page.html").write_text(page, encoding="utf-8")
    print("wrote", HERE / "panel_page.html", len(page) // 1024, "kB")


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dioscuri review panel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
  /* A review dossier: a summary to act on first, the members' own words after. */
  --ink: #17232b;
  --muted: #5d6b73;
  --paper: #f6f7f5;
  --card: #ffffff;
  --line: #dde3e1;
  --accent: #0f6e78;   /* brine teal, as in the app */
  --ember: #c4572b;    /* the gradient's hot end */
  --good: #2f7d4f;
  --warn: #a76a00;
  --font-body: "Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ink: #e4ecee; --muted: #9db0b6; --paper: #10181c; --card: #172227; --line: #2a3a40;
    --accent: #4fb3bd; --ember: #e68a5e; --good: #6cc08d; --warn: #e0b04a; color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --ink: #e4ecee; --muted: #9db0b6; --paper: #10181c; --card: #172227; --line: #2a3a40;
  --accent: #4fb3bd; --ember: #e68a5e; --good: #6cc08d; --warn: #e0b04a; color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.55 var(--font-body); }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 64px; display: grid; gap: 36px; }}
header h1 {{ font-size: 34px; line-height: 1.15; margin: 0 0 6px; letter-spacing: -0.01em; text-wrap: balance; }}
header .sub {{ color: var(--muted); margin: 0 0 14px; }}
header .lede {{ max-width: 68ch; margin: 0; }}
.strip {{ height: 6px; border-radius: 3px; background: linear-gradient(90deg, var(--accent), var(--ember)); margin-bottom: 18px; width: 120px; }}
h2 {{ font-size: 21px; margin: 0 0 12px; }}
h3 {{ font-size: 16.5px; margin: 0 0 4px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
th, td {{ text-align: left; vertical-align: top; padding: 10px 12px; border-bottom: 1px solid var(--line); font-size: 14.5px; }}
th {{ font-size: 12.5px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); font-weight: 600; }}
td:first-child {{ white-space: nowrap; font-weight: 600; }}
td.num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
tr:last-child td {{ border-bottom: 0; }}
a {{ color: var(--accent); }}
a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 3px; }}
.table-wrap {{ overflow-x: auto; }}
ul.fixed {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }}
ul.fixed li {{ background: var(--card); border: 1px solid var(--line); border-left: 4px solid var(--good); border-radius: 8px; padding: 9px 12px; display: grid; gap: 2px; }}
ul.fixed .who {{ color: var(--muted); font-size: 13px; }}
.pris {{ display: grid; gap: 10px; }}
.pri {{ display: grid; grid-template-columns: 44px 1fr; gap: 12px; background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }}
.pri .tag {{ font: 600 13px var(--font-mono); border-radius: 6px; height: 26px; display: grid; place-items: center; color: #fff; background: var(--ember); }}
.pri.p2 .tag {{ background: var(--warn); }}
.pri.p3 .tag {{ background: var(--muted); }}
.pri p {{ margin: 4px 0 0; max-width: 78ch; }}
.pri .meta {{ display: flex; flex-wrap: wrap; gap: 6px 16px; color: var(--muted); font-size: 13px; }}
.cols {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }}
.box {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }}
.box ul, .box ol {{ margin: 0; padding-left: 20px; display: grid; gap: 6px; }}
.toc {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.toc a {{ font-size: 13.5px; text-decoration: none; border: 1px solid var(--line); background: var(--card); border-radius: 999px; padding: 4px 10px; }}
.report {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; }}
.report h3 {{ font-size: 19px; margin-bottom: 8px; color: var(--accent); }}
.md {{ max-width: 80ch; overflow-wrap: anywhere; }}
.md pre {{ white-space: pre-wrap; font: 13px/1.5 var(--font-mono); }}
.md h1 {{ font-size: 19px; }} .md h2 {{ font-size: 17px; margin-top: 18px; }} .md h3 {{ font-size: 15.5px; color: var(--ink); margin-top: 14px; }}
.md table {{ font-size: 13px; display: block; overflow-x: auto; }}
.md code {{ font: 12.5px var(--font-mono); background: color-mix(in srgb, var(--line) 55%, transparent); padding: 1px 4px; border-radius: 4px; }}
.md pre code {{ background: none; padding: 0; }}
.md blockquote {{ border-left: 3px solid var(--line); margin: 8px 0; padding-left: 12px; color: var(--muted); }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; }} }}
@media (max-width: 520px) {{ header h1 {{ font-size: 27px; }} td:first-child {{ white-space: normal; }} }}
</style>
</head>
<body>
<main class="wrap">
<header>
  <div class="strip" aria-hidden="true"></div>
  <h1>Dioscuri review panel</h1>
  <p class="sub">{n} reviewers, each in a role, used the running agent through its API and read its code · 31 Oct 2026 · fixes in local commits ed20963 to 3d195b9 on rn/challenge (not pushed)</p>
  <p class="lede">The panel agrees the engineering core is honest: the search, the year model and the costs add up and can be checked by hand. What they push on is firm capacity (no N-1 cover, no margin), the chat's explanations and comparisons, the subsurface and gas checks, and how many model calls a turn needs. {nfixed} of their findings were fixed during the review; the rest are below by priority, then each member's full report.</p>
</header>

<section aria-labelledby="h-verdicts">
  <h2 id="h-verdicts">Verdicts</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Member</th><th>Verdict</th><th>Score</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>

<section aria-labelledby="h-fixed">
  <h2 id="h-fixed">Fixed during the review</h2>
  <ul class="fixed">{fixed}</ul>
</section>

<section aria-labelledby="h-open">
  <h2 id="h-open">Open, by priority</h2>
  <div class="pris">{pri}</div>
</section>

<section class="cols" aria-label="Keep, remove, decide">
  <div class="box"><h2>Keep</h2><ul>{keep}</ul></div>
  <div class="box"><h2>Remove or merge</h2><ul>{remove}</ul></div>
  <div class="box"><h2>Decisions for you</h2><ol>{decide}</ol></div>
</section>

<section aria-labelledby="h-full">
  <h2 id="h-full">The full reports</h2>
  <nav class="toc" aria-label="Reports">{toc}</nav>
</section>
{full}
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script id="reports" type="application/json">{data}</script>
<script>
(function () {{
  try {{
    if (!window.marked) return;
    // The reports are Markdown from the reviewers: any raw HTML in them is shown as text.
    var escape = function (h) {{
      var t = typeof h === "string" ? h : (h && (h.text || h.raw)) || "";
      return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }};
    window.marked.use({{ renderer: {{ html: escape }} }});
    var reports = JSON.parse(document.getElementById("reports").textContent);
    document.querySelectorAll(".md").forEach(function (el) {{
      var text = reports[el.dataset.key] || "";
      // Drop the report's own first heading: the section already names the member.
      text = text.replace(/^#\\s.*\\n+/, "");
      el.innerHTML = window.marked.parse(text, {{ mangle: false, headerIds: false }});
    }});
  }} catch (e) {{ /* the plain text stays */ }}
}})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
