"""Talk to a running Dioscuri server from the command line, as the app's panel does.

For reviewers (people or agents) who want to use the agent without a browser. Every command
prints plain text: what the agent did (its steps), what it said, the cards it showed, and the
tabs' data. Start a server first, for example::

    DIOSCURI_PORT=8790 PYTHONPATH=src python -m gemini_agent.server

Commands (``--url`` defaults to ``$DIOSCURI_URL`` or http://127.0.0.1:8790)::

    python hackathon/scripts/panel.py say   <thread> "message"     # one chat turn
    python hackathon/scripts/panel.py click <thread> <n | "option text">  # answer the open card
    python hackathon/scripts/panel.py state <thread>               # the brief, designs, open card
    python hackathon/scripts/panel.py designs <thread>             # every design, one line each
    python hackathon/scripts/panel.py design <thread> <design id> [part]
        part: plant, graph, economics, year, checks, gemini or all (default)
    python hackathon/scripts/panel.py attempts <thread>            # the design searches (Compare)
    python hackathon/scripts/panel.py gemini <thread> <design id>  # run its loop on GEMINI
    python hackathon/scripts/panel.py edit <thread> <design id> '<json changes>'  # a user design
    python hackathon/scripts/panel.py prices <thread> '<json>'     # change cost assumptions
    python hackathon/scripts/panel.py sensitivity <thread> <design id> '<json parameters>'
    python hackathon/scripts/panel.py trace <thread>               # every run's steps and calls
    python hackathon/scripts/panel.py attach <thread> <file>       # attach a file to the chat
    python hackathon/scripts/panel.py projects                     # the projects
    python hackathon/scripts/panel.py health                       # models and devices

A thread id is any name of letters, digits, - and _ (a new name starts a new chat).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request

URL = os.environ.get("DIOSCURI_URL", "http://127.0.0.1:8790")
TIMEOUT = 900


def call(method: str, path: str, body=None, stream: bool = False):
    """Send one request; return the parsed JSON (or the raw response for a stream)."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        URL + path, data=data, method=method, headers={"content-type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as err:
        sys.exit(f"HTTP {err.code}: {err.read().decode(errors='replace')[:500]}")
    except urllib.error.URLError as err:
        sys.exit(f"cannot reach {URL}: {err.reason} (is the server running?)")
    if stream:
        return resp
    return json.loads(resp.read().decode())


def wrap(text: str, indent: str = "  ") -> str:
    """Wrap long lines for the terminal, keeping tables and bullets as they are."""
    out = []
    for line in (text or "").splitlines():
        if line.startswith("|") or len(line) <= 100:
            out.append(indent + line)
        else:
            out += textwrap.wrap(line, 100, initial_indent=indent, subsequent_indent=indent)
    return "\n".join(out)


def run(thread: str, message=None, answers=None) -> None:
    """Run one turn and print what happened."""
    start = time.time()
    body = {"threadId": thread}
    if message is not None:
        body["message"] = message
    if answers is not None:
        body["answers"] = answers
    resp = call("POST", "/api/run", body, stream=True)
    text, steps, cards, finished = [], [], [], None
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line.startswith("data: "):
            continue
        e = json.loads(line[6:])
        kind = e.get("type")
        if kind == "TEXT_MESSAGE_CONTENT":
            text.append(e.get("delta", ""))
        elif kind == "STEP_FINISHED":
            m = e.get("metadata") or {}
            keep = {
                k: m[k]
                for k in (
                    "intent",
                    "relevant",
                    "decided_by",
                    "changes",
                    "unsupported",
                    "dropped",
                    "decision",
                    "run_design",
                    "removed",
                    "removed_sentences",
                    "reason",
                    "chosen",
                    "candidates",
                    "model",
                    "device",
                    "corrections",
                    "ungrounded",
                    "steps",
                    "failures",
                    "designs",
                )
                if k in m and m[k] not in (None, [], {}, "")
            }
            steps.append(f"{e.get('stepName')} {json.dumps(keep, ensure_ascii=False)[:600]}")
        elif kind == "CUSTOM":
            name, value = e.get("name"), e.get("value")
            if name == "confirm_inputs":
                rows = value.get("rows", [])
                cards.append(
                    "INPUTS CARD:\n"
                    + "\n".join(
                        f"    [{r['kind']}{', CHANGED' if r.get('changed') else ''}] "
                        f"{r['group']} / {r['label']}: {r['value']}  (from: {r['source']})"
                        for r in rows
                    )
                )
            elif name == "clarification":
                q = (value.get("questions") or [{}])[0]
                opts = q.get("options") or []
                cards.append(
                    f"QUESTION ({value.get('kind')}): {q.get('label', '')}\n"
                    + "\n".join(f"    {i + 1}. {o}" for i, o in enumerate(opts))
                    + ("\n    (answer with: click <thread> <n>)" if opts else "")
                )
            elif name == "result":
                k = {x["id"]: x.get("value") for x in value.get("kpis", [])}
                cards.append(
                    f"RESULT CARD ({value.get('view', 'full')}): {value.get('design_id')} "
                    f"{value.get('name')}; heat {k.get('heat_coverage')} %, cold "
                    f"{k.get('cool_coverage')} %, {k.get('lcoe')} €/MWh heat and cold "
                    f"({k.get('lcoh')} heat, {k.get('lcoc')} cold), CO2 vs gas {k.get('co2')} %; "
                    f"checks {value.get('checks')}; flags {value.get('flags')}"
                    + (
                        f"; against {value['against'].get('design_id')}"
                        if value.get("against")
                        else ""
                    )
                )
                for pk in value.get("picks") or []:
                    cards.append(
                        f"    PICK {pk['label']}{' (recommended)' if pk['chosen'] else ''}: "
                        f"{pk['id']}, {pk['lcoe']} €/MWh, {pk['co2_t']} t CO2, "
                        f"{pk['capex_meur']} M€, reliable={pk['reliable']}, "
                        f"one-unit-out cases short={pk.get('n1_short')}"
                    )
                firm = value.get("firm") or {}
                if firm:
                    cards.append(
                        f"    FIRM: peak spare {json.dumps(firm.get('peak'))}; one unit out: "
                        f"{firm.get('short')} of {len(firm.get('cases') or [])} cases short: "
                        + "; ".join(
                            f"{c['unit']} {c['worst_mw']} MW {c['side']} on {c['worst_day']}"
                            for c in firm.get("cases") or []
                            if c.get("short")
                        )
                    )
                if value.get("research"):
                    r = value["research"]
                    cards.append(
                        f"    NEW SEARCH UNDER THE CHANGE: picks {r['id']} at {r['lcoe']} €/MWh "
                        f"({'CHANGED from ' + r['base_id'] if r['changed'] else 'pick stays'})"
                    )
            elif name == "failure":
                f = value.get("failed") or {}
                cards.append(
                    "FAILURE CARD on "
                    + str(value.get("design"))
                    + ": "
                    + "; ".join(
                        f"{e['words']} out {e['from']}-{e['to']} ({e['days']} d, {e['how']})"
                        for e in value.get("events") or []
                    )
                    + f"\n    heat {json.dumps(f.get('heat'))}"
                    + f"\n    cold {json.dumps(f.get('cool'))}"
                    + f"\n    extra gas {f.get('extra_gas_gwh')} GWh, CO2 {f.get('extra_co2_t')} t,"
                    f" "
                    f"cost {f.get('extra_cost_keur')} k€; needed={value.get('needed')}, "
                    f"best={value.get('best')}"
                    + "".join(
                        f"\n    REMEDY {r['name']}: covers={r['covers']}, still short "
                        f"{max(r['heat_short_mw'], r['cool_short_mw'])} MW, "
                        f"{r['capex_meur']} M€, {r['yearly_keur']} k€/yr"
                        for r in value.get("remedies") or []
                    )
                    + (
                        f"\n    SPARE ESP (not needed): {json.dumps(value['spare_esp'])}"
                        if value.get("spare_esp")
                        else ""
                    )
                )
            elif name == "compare":
                names = [d["id"] for d in value.get("designs") or []]
                cards.append(
                    "COMPARE CARD: "
                    + " vs ".join(names)
                    + "".join(
                        f"\n    {r['label']} ({r['unit']}): {r['values']}"
                        + (f" best={names[r['best']]}" if r.get("best") is not None else "")
                        for r in value.get("rows") or []
                    )
                )
            elif name == "candidates":
                cands = value.get("candidates") or value.get("rows") or []
                cards.append(f"CANDIDATES: {len(cands)} listed")
            elif name == "suggestions":
                cards.append("SUGGESTIONS: " + " | ".join(value if isinstance(value, list) else []))
            elif name == "sources":
                cards.append(
                    "SOURCES: " + "; ".join(str(c.get("source")) for c in value or [])[:400]
                )
            elif name in ("model_unavailable", "answer"):
                cards.append(f"{name.upper()}: {json.dumps(value, ensure_ascii=False)[:300]}")
        elif kind == "RUN_FINISHED":
            finished = e
        elif kind == "RUN_ERROR":
            cards.append(f"RUN ERROR: {e.get('message')}")
    seconds = time.time() - start
    result = (finished or {}).get("result") or {}
    interrupt = ((finished or {}).get("outcome") or {}).get("interrupts") or []
    print(
        f"[{seconds:.1f} s, behaviour={result.get('behaviour')}, model calls="
        f"{result.get('llm_calls')}, tokens={result.get('prompt_tokens')}+"
        f"{result.get('output_tokens')}"
        + (f", waiting for: {interrupt[0].get('reason')}" if interrupt else "")
        + "]"
    )
    print("STEPS:")
    for s in steps:
        print("  - " + s)
    print("REPLY:")
    print(wrap("".join(text)))
    for c in cards:
        print(c)


def click(thread: str, choice: str) -> None:
    """Answer the open card: by its number or its text."""
    state = call("GET", f"/api/threads/{thread}")
    pending = state.get("pending") or {}
    kind = pending.get("kind")
    options = pending.get("options") or []
    if kind == "decision":
        options = [c[0] for c in pending.get("choices", [])] + ["Keep my limits"]
    if kind == "confirm":
        options = ["Run the design with these inputs", "Change an input first"]
    if choice.isdigit() and options:
        choice = options[int(choice) - 1]
    key = {"choice": "choice", "decision": "decision", "confirm": "confirm"}.get(kind)
    if key is None:
        sys.exit(f"no card to click (open: {kind}); use say <thread> <message>")
    run(thread, answers={key: choice})


def attach(thread: str, path: str) -> None:
    """Upload a file to a conversation (the chat's paperclip)."""
    boundary = "----panel" + str(int(time.time() * 1000))
    with open(path, "rb") as fh:
        content = fh.read()
    name = os.path.basename(path)
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="threadId"\r\n\r\n{thread}\r\n',
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n",
    ]
    body = parts[0].encode() + parts[1].encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        URL + "/api/attachments",
        data=body,
        method="POST",
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as err:
        sys.exit(f"HTTP {err.code}: {err.read().decode(errors='replace')[:500]}")
    print(resp.read().decode()[:2000])


def short(d: dict) -> str:
    """Return one design as a line."""
    e, y = d.get("economics") or {}, d.get("year") or {}
    return (
        f"{d['id']} [{d.get('origin')}/{d.get('role')}, attempt {d.get('attempt')}] "
        f"{d.get('name')} | LCOE {e.get('lcoe') or e.get('lcoe_eur_per_mwh')} €/MWh, heat "
        f"{round((y.get('heat_coverage') or 0) * 100, 1)} %, caps broken "
        f"{len(y.get('violations') or [])}, verified {d.get('verified')}"
    )


def main() -> None:
    """Parse the command and run it."""
    global URL
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--url", default=URL)
    p.add_argument("command")
    p.add_argument("args", nargs="*")
    a = p.parse_args()
    URL = a.url.rstrip("/")
    cmd, args = a.command, a.args
    if cmd == "say":
        run(args[0], message=" ".join(args[1:]))
    elif cmd == "click":
        click(args[0], " ".join(args[1:]))
    elif cmd == "state":
        print(
            json.dumps(call("GET", f"/api/threads/{args[0]}"), ensure_ascii=False, indent=1)[:6000]
        )
    elif cmd in ("designs", "design", "attempts"):
        wb = call("GET", "/api/workbench?" + urllib.parse.urlencode({"threadId": args[0]}))
        if cmd == "designs":
            for d in wb.get("designs", []):
                print(short(d))
        elif cmd == "attempts":
            for at in wb.get("attempts", []):
                print(
                    f"{at['id']}: {at.get('label')} | layouts {at.get('layouts')}, sizings "
                    f"{at.get('sizings')}, years {at.get('years')} | chosen {at.get('chosen')}"
                )
                for c in at.get("candidates", [])[:60]:
                    print(
                        f"   {c['code']:28s} {c['role']:9s} stage {c.get('stage')} LCOE "
                        f"{c.get('lcoe')} CO2 {c.get('co2_t')} t capex {c.get('capex_meur')} | "
                        f"{(c.get('reason') or '')[:150]}"
                    )
        else:
            want, part = args[1], (args[2] if len(args) > 2 else "all")
            d = next((x for x in wb.get("designs", []) if x["id"] == want), None)
            if d is None:
                sys.exit("no such design; ids: " + ", ".join(x["id"] for x in wb["designs"]))
            if part == "graph":
                g = d["graph"]
                out = {"nodes": g["nodes"], "edges": g["edges"]}
            elif part == "gemini":
                out = d["graph"].get("gemini_project")
            elif part == "year":
                y = dict(d["year"])
                y.pop("daily_mw", None)
                rows = []
                for i, dd in enumerate(y.get("doublets") or []):
                    flows = [f for f, on in zip(dd.get("flow_m3h", []), dd.get("on", [])) if on]
                    rows.append(
                        {
                            "doublet": i + 1,
                            "days_on": len(flows),
                            "flow_mean_m3h": round(sum(flows) / len(flows), 1) if flows else 0,
                            "flow_min_m3h": min(flows) if flows else 0,
                            "flow_max_m3h": max(flows) if flows else 0,
                        }
                    )
                y["doublets"] = rows  # daily series: see design <id> plant, or the workbench
                out = y
            elif part == "all":
                out = {k: v for k, v in d.items() if k not in ("graph", "year")}
            else:
                out = d.get(part)
            print(json.dumps(out, ensure_ascii=False, indent=1)[:12000])
    elif cmd == "gemini":
        wb = call("GET", "/api/workbench?" + urllib.parse.urlencode({"threadId": args[0]}))
        d = next((x for x in wb.get("designs", []) if x["id"] == args[1]), None)
        if d is None or not d["graph"].get("gemini_project"):
            sys.exit("no GEMINI project for that design")
        out = call("POST", "/api/gemini/run", {"project": d["graph"]["gemini_project"]})
        print(json.dumps(out, ensure_ascii=False, indent=1)[:8000])
    elif cmd == "edit":
        out = call(
            "POST",
            "/api/designs",
            {"threadId": args[0], "base": args[1], "changes": json.loads(args[2])},
        )
        print(short(out["design"]))
    elif cmd == "prices":
        out = call(
            "PUT", "/api/assumptions", {"threadId": args[0], "assumptions": json.loads(args[1])}
        )
        for d in out.get("designs", []):
            print(short(d))
    elif cmd == "sensitivity":
        params = json.loads(args[2])
        out = call(
            "POST",
            "/api/sensitivity",
            {
                "threadId": args[0],
                "design": args[1],
                "parameters": params,
                "outputs": ["lcoe", "co2_saving_pct", "violations"],
            },
        )
        print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
    elif cmd == "trace":
        out = call("GET", "/api/trace?" + urllib.parse.urlencode({"threadId": args[0]}))
        print(json.dumps(out, ensure_ascii=False, indent=1)[:12000])
    elif cmd == "attach":
        attach(args[0], args[1])
    elif cmd == "projects":
        print(json.dumps(call("GET", "/api/projects"), ensure_ascii=False, indent=1)[:4000])
    elif cmd == "health":
        print(json.dumps(call("GET", "/api/health"), ensure_ascii=False, indent=1))
    else:
        sys.exit(f"unknown command {cmd}; see --help")


if __name__ == "__main__":
    main()
