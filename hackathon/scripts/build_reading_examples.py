"""Build the worked examples of the parameters reading (``gemini_agent.reading_examples``).

From the fine-tuning data (round 2's simulated conversations: ``train.jsonl`` and ``val.jsonl``,
gitignored), every row whose task is ``parameters``: the user's message (the words after the
prompt's last "Message: ") and the reading the row was labelled with (its last assistant
message). Kept only when:

- the reading passes the app's own checks (``parameters.check`` with the row's values now):
  nothing dropped, or only values refused on their merits (out of range, a return across its
  supply), which is the reading the app wants: the value said, and code refusing it. A guess
  for a change without an amount, a number not in the quote, a quote not in the message or an
  unknown key leaves the row out;
- the message is not near-identical to any evaluation prompt (``hackathon/evals/scenarios``:
  the same normalised text, a token overlap of 0.7 or more, or a character similarity of 0.9 or
  more), so no test case leaks into the prompt;
- it is the first of its normalised text.

The readings are written compactly (empty fields left out), the messages embedded with
``snowflake-arctic-embed:s`` through Ollama on the CPU (``num_gpu=0``), and the index saved to
``src/gemini_agent/data/reading_examples.npz`` (int8 embeddings, under 2 MB).

Usage::

    python hackathon/scripts/build_reading_examples.py [--data DIR] [--out FILE] [--max N]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from gemini_agent import parameters, reading_examples  # noqa: E402

DATA = ROOT / "hackathon" / "finetune" / "data" / "v2"  # not in the repository: pass --data
FILES = ("train-sim/train.jsonl", "train-sim/val.jsonl")
MODEL = "snowflake-arctic-embed:s"
LINE = re.compile(r"^(\w+)=(.*?)(?: \[[^\]]*\])?$")


def values_now(content: str) -> dict:
    """Return the values now listed in a short reading prompt (``key=value [unit]`` lines)."""
    now: dict = {}
    block = content.split("Parameters:\n", 1)[-1].split("\n\n", 1)[0]
    for line in block.splitlines():
        m = LINE.match(line.strip())
        if not m or m.group(1) not in parameters.CATALOGUE or m.group(2) == "":
            continue
        key, raw = m.groups()
        if parameters.CATALOGUE[key].kind == "records":
            continue
        if raw.startswith("["):
            items = [x.strip() for x in raw.strip("[]").split(",") if x.strip()]
            try:
                now[key] = [float(x) for x in items]
            except ValueError:
                now[key] = items
            continue
        try:
            now[key] = float(raw)
        except ValueError:
            now[key] = raw
    return now


def refused_on_merit(dropped: str) -> bool:
    """Return True for a drop of a value said but refused (out of range, crossing its pair)."""
    why = dropped.split(": ", 1)[-1]
    return why.startswith("outside") or any(why == c[2] for c in parameters.CROSSED)


def compact(reading: dict) -> str:
    """Return a reading's JSON without its empty fields (shorter in the prompt)."""
    out = {}
    for key, value in reading.items():
        if value in ([], None, ""):
            continue
        if key == "steps":
            value = [
                {k: v for k, v in step.items() if v not in ([], None, "")}
                for step in value
                if isinstance(step, dict)
            ]
        if key == "changes":
            value = [{k: v for k, v in c.items() if k != "step" or v} for c in value]
        out[key] = value
    return json.dumps(out, ensure_ascii=False)


def rows(data: Path):
    """Yield (message, reading, user content) of every parameters row."""
    for name in FILES:
        with open(data / name, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("task") != "parameters":
                    continue
                msgs = row["messages"]
                if msgs[-1]["role"] != "assistant":
                    continue
                user = next(m["content"] for m in reversed(msgs[:-1]) if m["role"] == "user")
                if "Message: " not in user:
                    continue
                yield user.rsplit("Message: ", 1)[1].strip(), msgs[-1]["content"], user


def main() -> None:
    """Build the index."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--out", type=Path, default=reading_examples.INDEX)
    ap.add_argument("--max", type=int, default=3000)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    args = ap.parse_args()

    prompts = reading_examples.eval_prompts(
        sorted((ROOT / "hackathon/evals/scenarios").glob("*.yaml"))
    )
    seen, kept = set(), []
    counts = {"rows": 0, "bad_json": 0, "not_checked": 0, "eval_like": 0, "repeat": 0}
    for message, label, user in rows(args.data):
        counts["rows"] += 1
        try:
            reading = json.loads(label)
        except json.JSONDecodeError:
            counts["bad_json"] += 1
            continue
        norm = reading_examples.normalise(message)
        if not norm or norm in seen:
            counts["repeat"] += 1
            continue
        now = values_now(user)
        checked = parameters.check(
            reading, message, now, designed="Current design:" in user, pairs=True
        )
        if not all(refused_on_merit(d) for d in checked.dropped):
            counts["not_checked"] += 1
            continue
        if reading_examples.leaks(message, prompts):
            counts["eval_like"] += 1
            continue
        seen.add(norm)
        kept.append((message, compact(reading)))
    kept = kept[: args.max]
    print(json.dumps(counts), "kept", len(kept), "eval prompts", len(prompts))

    from ollama import Client

    client = Client(host=args.host, timeout=120)
    vectors = []
    start = time.time()
    for i in range(0, len(kept), 64):
        batch = [m for m, _ in kept[i : i + 64]]
        res = client.embed(model=MODEL, input=batch, options={"num_ctx": 512, "num_gpu": 0})
        vectors += list(res.embeddings)
    print(f"embedded {len(vectors)} in {time.time() - start:.0f} s")
    reading_examples.save(
        args.out,
        [m for m, _ in kept],
        [r for _, r in kept],
        vectors,
        MODEL,
        source="hackathon/finetune/data/v2/train-sim (train + val), parameters rows",
    )
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
