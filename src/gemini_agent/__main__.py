"""Ask the agent from a terminal.

Examples
--------
``python -m gemini_agent "Design heating and cooling for this district."``
``python -m gemini_agent --device cpu --defaults "Design heating and cooling."``
``python -m gemini_agent --reasoning "Compare a 3 km and a 1.5 km doublet."``
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable, List, Optional

from gemini_agent import Agent, Session
from gemini_agent.contract import DesignBrief
from gemini_agent.docs import DocIndex
from gemini_agent.intake import missing_inputs
from gemini_agent.llm import DEFAULT_MODEL, OllamaLLM
from gemini_agent.modelgen import Registry
from gemini_agent.router import Router


def _show(events: Iterable[dict], raw: bool) -> None:
    steps = {}
    for e in events:
        if raw:
            print(json.dumps(e, ensure_ascii=False))
            continue
        kind = e["type"]
        if kind == "STEP_STARTED":
            steps[e["stepName"]] = e["metadata"]
        elif kind == "STEP_FINISHED":
            meta = steps.get(e["stepName"], {})
            tag = " [model call]" if meta.get("kind") == "model" else ""
            code = f"  {meta['code']}" if meta.get("code") else ""
            print(
                f"  ✓ {meta.get('label', e['stepName'])}{tag}{code}  "
                f"{e['metadata']['seconds']:.2f} s"
            )
            done = e["metadata"]
            if done.get("decided_by"):
                print(f"      {done['decided_by']}: {done.get('reason', '')}")
                for line in done.get("steps", []) + done.get("corrections", []):
                    print(f"        · {line}")
                if done.get("note"):
                    print(f"        ! {done['note']}")
        elif kind == "TEXT_MESSAGE_CONTENT":
            print("\n" + e["delta"])
        elif kind == "CUSTOM" and e["name"] == "clarification":
            for q in e["value"]["questions"]:
                default = f" (default: {q['default']})" if q.get("default") else ""
                print(f"  ? {q['label']}{default}")
                for option in q.get("options", []) if e["value"].get("kind") == "decision" else []:
                    print(f"      - {option}")
        elif kind == "CUSTOM" and e["name"] == "result":
            kpis = ", ".join(
                f"{k['label']} {k['value']} {k['unit']}"
                for k in e["value"]["kpis"]
                if k["value"] is not None
            )
            print(f"  [{e['value']['alternative']}] {kpis}")
        elif kind == "RUN_FINISHED":
            r = e.get("result") or {}
            print(
                f"\n  {r.get('behaviour')} · {r.get('llm_calls')} model call(s) · "
                f"{(r.get('prompt_tokens') or 0) + (r.get('output_tokens') or 0)} tokens · "
                f"{r.get('seconds', 0):.1f} s"
            )
        elif kind == "RUN_ERROR":
            print(f"  error: {e['message']}")


def main(argv: Optional[List[str]] = None) -> int:
    """Run one question (and its clarification, with ``--defaults``) and print the result.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; ``sys.argv`` when omitted.

    Returns
    -------
    int
        Exit code.
    """
    p = argparse.ArgumentParser(prog="python -m gemini_agent", description=__doc__.split("\n")[0])
    p.add_argument("message", help="the question for the agent")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model tag")
    p.add_argument(
        "--device",
        choices=["auto", "cpu"],
        default="auto",
        help="cpu keeps the model off the GPU, like the judges' laptops",
    )
    p.add_argument(
        "--defaults",
        action="store_true",
        help="accept every proposed default, option or approval (the CLI's yes to everything)",
    )
    p.add_argument("--json", action="store_true", help="print the raw AG-UI events")
    p.add_argument("--trace", default=None, help="folder for the JSONL trace")
    p.add_argument("--attach", action="append", default=[], help="attach a file (repeatable)")
    p.add_argument(
        "--reasoning",
        action="store_const",
        const=True,
        default=None,
        help="always reason: the larger model plans and explains (by default the agent decides)",
    )
    p.add_argument(
        "--no-reasoning",
        dest="reasoning",
        action="store_const",
        const=False,
        help="never reason (by default the agent decides per message)",
    )
    args = p.parse_args(argv)
    router = Router(OllamaLLM(model=args.model, device=args.device), device=args.device)
    docs = DocIndex(device=args.device, background=False)
    agent = Agent(router.fast, trace_dir=args.trace, docs=docs, registry=Registry(), router=router)
    if args.reasoning:
        info = router.info()["reasoning"]
        print(f"  reasoning mode: {info['model']} on the {info['device']}")
    session = Session()
    for path in args.attach:
        print(f"  attached {path}: {agent.attach(session, path)} chunk(s)")
    _show(agent.run(session, args.message, reasoning=args.reasoning), args.json)
    while session.pending and args.defaults:
        kind = session.pending.get("kind")
        if kind == "decision":
            answers = {"decision": session.pending["choices"][0][0]}
            print("\n  (picking the first option)")
        elif kind in ("generate", "approval"):
            answers = {kind: session.pending["options"][0]}
            print(f"\n  (answering {session.pending['options'][0]!r})")
        else:
            brief = DesignBrief(**session.pending["brief"])
            answers = {q.id: q.default or "" for q in missing_inputs(brief, session.project)}
            print("\n  (accepting the proposed defaults)")
        _show(agent.run(session, answers=answers, reasoning=args.reasoning), args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
