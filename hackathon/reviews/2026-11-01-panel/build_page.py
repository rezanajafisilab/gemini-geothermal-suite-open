# flake8: noqa  (a page generator: the review data are long strings)
"""Build the review panel page: synthesis on top, every member's full report below."""

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE

MEMBERS = [
    ("judge", "Hackathon judge", "6.2 / 10", "Up from 5.7. Every number made by code checks out, dated failures in English are exact, comparisons and multi-step requests work. It loses points on non-English dates, why-questions, a relaxed cap carried into later searches, GEMINI used as a view rather than a check, and picks that depend on the objective."),
    ("operator", "Plant operator", None, "Could now sign off the design (N-1 by default, spare on the peak day, every failure simulated and the card honest), not yet the chat for contingencies: 9 of 15 failure replies contradicted their card; 'one boiler unit' ran as the whole bank; planned maintenance took the worst window."),
    ("reservoir_production", "Reservoir and production engineer", None, "The subsurface physics is sound (breakthrough, bubble point, ESP depth and SodM within 0.5 % of hand values; flow caps land right), but it was invisible: not in the check list, not in the answer's facts, and the spacing did not reach the breakthrough check (all three fixed after the panel)."),
    ("economist", "Energy economist", None, "The cost base is now PBL-consistent (+3-5 %) and every figure rebuilds to the cent; the reliable plan's +1.6 €/MWh is right and cheap. The best-overall rule inverted above 137 €/t (fixed) and is decided by margins of 0.03-0.08 €/MWh; money answers at what-if prices and for non-chosen designs are not computed by code."),
    ("district_client", "District energy engineer for the client", None, "The four picks, one-unit-out cases, costed failure remedies and multi-step requests work; a client cannot use the chat for a council yet: it answered about the wrong plant, deleted a correct council summary, and called a boiler that makes 49 % of the heat a 'backup' (label fixed)."),
    ("agentic_ai", "Agentic AI and LLM evaluation expert", None, "The planner fixes round 1's two-step failure and reads clean wordings in three languages; the code around it was weak: 27 of 62 wordings right. Steps were skipped silently, dates became a cooling network, 'doublet 1' a doublet count, a what-if before the design crashed (all fixed after the panel); two scenarios of one parameter and injected sentences still pass."),
    ("ui_ux", "UI and UX designer", None, "The result card, picks, firm strip, 'the pick changes/stays' line and the canvas re-layout are right; a what-if's gas price leaked into the Economics tab for every design (fixed), names were unique only in the chat (picker fixed), and the new cards shipped without padding (fixed). 12 of 16 wordings handled right; the cards were right more often than the prose."),
]

FIXED = [
    ("Dates and durations in Dutch, German and French, 19/7 and 10/01-24/01; the model's dates kept when the message gives their day numbers; 'the coldest week' takes the worst start (ties go to the most demand)", "Judge, operator, agentic AI"),
    ("Planned maintenance ('take the heat pump out for 10 days') takes the mildest window (1-10 Aug), not the worst", "Operator"),
    ("'One boiler unit' is one of three units, not the whole bank; a failed boiler or chiller set gets a standby twin as its remedy", "Operator"),
    ("Failure replies are shown as code wrote them (the model contradicted its own card 9 times in 15); negative running costs say the heat went undelivered", "Operator, economist, UI"),
    ("'From 10 to 24 January' is no longer a 10/24 °C cooling network; '20 % more heat demand' no longer lowers the coverage check to 20 %; 'doublet 1' is a name, not a count; 'COP 12' is not a 12 MW heat pump; a described doublet's depth must be in the message", "Agentic AI, client"),
    ("Quotes with typos the model fixed, number words (ten, a fifth, verdubbelt), '77 °C instead of 87 °C'", "Agentic AI"),
    ("Plans: a what-if before the design runs after it (it crashed); a step that cannot run is said, never concluded; the plan survives a change on the inputs card; a question about a named design no longer re-runs the search; design steps take only the planner's changes", "Agentic AI, client, operator"),
    ("Best overall: CO2 never weighs less than the user's own carbon price (it inverted above 137 €/t); reliable plans for the best layout of each doublet count", "Economist, judge"),
    ("The repair loop stops when growing a unit does not close the gap, and says why (it grew a heat pump from 0.7 to 64 MW)", "Judge"),
    ("The subsurface checks in the check list (breakthrough, ESP above the bubble point, SodM) and in the answer's facts; the well spacing reaches the breakthrough check; provenance says what GEMINI computes (pressures, pumps) and what Dioscuri does (index, heat loss, checks)", "Reservoir and production, judge"),
    ("The tabs measure every design against the base case's gas reference, not a what-if's; edited designs keep their own name (U1) and lose the N-1 flag; names in the design picker", "UI"),
    ("A what-if card says when N-1 is lost under the change; the failure and compare cards padded; comparisons in words with the table on the card (three tables before)", "UI, agentic AI"),
    ("Money facts reach every answer about a design, in any language (Dutch and German money questions got canned text)", "Economist"),
    ("The design reply gives the heat split (exchanger, heat pump, gas boiler) and the gas bought; the boiler is called a gas boiler, not a backup; the checks line counts the checks passed", "Client, judge, agentic AI"),
    ("Why-answers get each choice of the design against its best alternative in €/MWh and t CO2, computed by code", "Judge, client"),
]

PRIORITIES = [
    ("P1", "Replies bound to the cards", "Code renders the conclusions (the pick changed or not, N-1 kept or lost, which design is cheaper or greener) and the model writes one or two sentences around them; a claim check on every plan reply; no heat/heat-and-cold label swaps; no user-dictated sentences or numbers. Most wrong answers in round 2 were prose contradicting a correct card.", "All seven", "a day"),
    ("P1", "A visible plan and multi-scenario steps", "Show the plan ('1 design · 2 what-if: reservoir -10 K · 3 does the pick change?') with the inputs card; each step with its own changes (two what-ifs of one parameter, failure on two designs, compare designs a step makes); ask when a step has no amount; more than three steps: ask which.", "Agentic AI, judge", "a day"),
    ("P1", "Money for every design and scenario, by code", "NPV, IRR, payback, €/t avoided, € per home, at each scenario's own prices, on the COMPARE, what-if and FAILURE cards and in the answer's facts; a scenario chip on every design and no ranking across scenarios in Compare.", "Economist, client, UI", "a day"),
    ("P1", "GEMINI as a check", "Run GEMINI's loop for the pick and compare it with the plant model on the card (GEMINI sets the ESP at 650 m, 39 bar intake, below the 41.7 bar bubble point; its exchanger gives 7.60 MW against 7.23).", "Judge, reservoir and production", "a day"),
    ("P1", "Why and alternatives", "Answer why-questions from the search record (the decisions facts help: 'why not two injectors' is now right; 'why boilers', 'why one doublet' still weak); the best design for any doublet count on request.", "Judge, client", "a day"),
    ("P1", "A decision table and council memo", "Gas reference, recommended, cheapest, greenest, greenest reliable: capital, yearly cost, € per home, CO2 and its cut, share of heat from gas, N-1, €/t avoided; a plain summary for a council.", "Client, economist", "a day"),
    ("P1", "A timed CPU session", "Judges ran 2025 entries on CPU laptops: time a 20-minute session on the CPU models and run the full eval there.", "Judge", "half a day"),
    ("P2", "Uncertainty in the chat", "The tornado and a P10/P50/P90 Monte Carlo for the pick; a tie band ('a tie within 0.5 €/MWh'), probability of being cheapest.", "Judge, economist", "a day"),
    ("P2", "Constrained objectives and gas-free plans", "Greenest reliable; cheapest with at least X % CO2 cut; an electric boiler so a reliable plan without gas exists; a consistent lowest-CO2 pick (cost-sized 10,045 t against 6,949 t when sized for CO2).", "Client, economist, judge", "days"),
    ("P2", "Subsurface refinements", "A margin on the bubble point, the Poynting correction and a stated salinity basis (42 to 45-54 bar); cold-water viscosity for injectivity (SodM could bind at 50 mD); production temperature falling over 30 years; interference between doublets.", "Reservoir and production", "one to two days"),
    ("P2", "Reliability economics", "Failure rates and expected outage cost; a value on unserved heat; realistic ESP outage (rig mobilisation, lead time without a spare); a split plate exchanger as a cheaper N-1 option; two units out at once.", "Operator, economist", "one to two days"),
    ("P2", "Fewer model calls", "One reader: fold intent, route, screen and the inputs-card decision into the planner's call; the claim check as a continuation of the answer (cached); 3.45 calls a turn to about 2.5.", "Agentic AI", "one to two days"),
    ("P2", "A held-out planner eval", "About 100 messages (10 request types × 10 wordings, three languages, typos, two scenarios, adversarial) with exact labels: steps, changes per step, failure days, designs; end-to-end checks against the ledger.", "Agentic AI", "half a day"),
    ("P2", "The canvas for two and three doublets", "The page view for multi-doublet designs (fits at 0.40 for three); unit counts drawn (3 × 10.4 MW); the day's temperatures on the pipes; 'Gas · Burning' as a number.", "UI", "a day"),
    ("P3", "After the deadline", "An investor case (SDE++, ACM tariff, tax, equity IRR); growth and phasing; network losses; minimum loads and start counts; the gas flash and scaling.", "Economist, client, operator, reservoir", "weeks"),
]

KEEP = [
    "Physics and costs made by code: every reviewer rebuilt their numbers to within 0.5 % (breakthrough, bubble point, ESP depth, SodM, LCOE, NPV, the N-1 premium)",
    "The reliable plan as the default recommendation, with the one-unit-out cases and the spare on the peak day on the card",
    "Failures simulated on dates with remedies run through the same days; planned maintenance in the mildest window",
    "The COMPARE card resolving names, codes and picks in three languages; the what-if card's 'the pick changes / stays'",
    "The planner in the existing reading call: one 2.4k-token call, no parse failures in 102 live turns",
]

REMOVE = [
    "Remaining phrase routers that decide meaning: WHY_START, ABOUT_RESULT, ABOUT_DESIGN, DESIGN_TALK/GEMINI_TALK as context routers, PICK_HINTS",
    "The small reader as a router (its 'other' and false bypass flags cost 9B calls); keep it as a 0.3 s gate",
    "Separate claim and claim-quote calls (one continuation call)",
    "'Most reliable' as a separate pick when it is the same plan family within 0.1 €/MWh as best overall (or rename it 'cheapest reliable plan')",
]

DECISIONS = [
    "Push rn/challenge so Ali can see it (a branch push, not a merge); nothing is pushed yet.",
    "The default recommendation: best overall is a one-doublet reliable plan whose gas boiler makes about half the heat; keep it, or make the default 'cheapest reliable plan with at least X % CO2 cut' or a two-doublet plan.",
    "Failure answers are now shown as code wrote them (accurate, English only); keep that, or let the model word them again once replies are bound to the cards.",
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
<title>Dioscuri review round 2</title>
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
  <h1>Dioscuri review panel, round 2</h1>
  <p class="sub">Round 2 · {n} reviewers, each in a role, stressed the agent through its API with many wordings and read its code · 1 Nov 2026 · build v14 (local commits 5190d6a to cf704b6); fixes after the panel in 111a320 · rn/challenge, not pushed</p>
  <p class="lede">The build they tested added four picks with reliable plans, failures on dates, subsurface checks, a step planner and PBL costs. Every reviewer could rebuild the numbers made by code. What still fails is the edge of the conversation: reading odd wordings, and prose that contradicts a correct card. {nfixed} of their findings were fixed after the panel; the rest are below by priority, with what each role needs most, then every report.</p>
</header>

<section aria-labelledby="h-verdicts">
  <h2 id="h-verdicts">Verdicts</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Member</th><th>Verdict</th><th>Score</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>

<section aria-labelledby="h-fixed">
  <h2 id="h-fixed">Fixed after the panel (commit 111a320)</h2>
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
