"""Claim checker: a second model call checks the reply's words against its sources.

The number check in ``answer.py`` proves every number; this step covers what numbers do not:
a sentence such as "Dioscuri models aquifer storage" or "GEMINI includes a cooling model" has
no number, yet the context says otherwise. The checker sees the reply's sentences and the
blocks the reply relied on (and the project's facts and the conversation so far), and gives
each sentence a verdict. Code then removes the sentences found "unsupported" or
"contradicted". When most of the reply goes, a reply that rewords a checked template (a tool's
result) shows that template; any other keeps what was supported and says what it could not
confirm.

Sentences the code has already checked are not sent: those copied from the draft (the
template the tools filled), table rows (all numbers) and questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import List, Optional, Sequence, Tuple

from gemini_agent.answer import (
    LINE_LEAD,
    TABLE_ROW,
    TABLE_RULE,
    Block,
    _flat,
    load,
    sentences,
    strip_cites,
)
from gemini_agent.intake import numbers_in
from gemini_agent.llm import LLMCall, LLMError, ModelUnavailable

CLAIMS_PROMPT = "claims_v2"  # v2: inferences count as supported; the conversation is a source
# Before a sentence goes, the model must quote the sources that back it, or say none does; code
# checks the quote is really there. A batch of verdicts is coarse: on 30 Oct it removed "87 °C
# is not reported in any of the files" although the facts said just that.
QUOTE_PROMPT = "claims_quote_v1"
# The user asked on 5 Nov that the checker mostly mend the wording rather than delete right
# claims ("I remember your name from our first conversation" went, though T1 gave the name): a
# flagged sentence now gets a quote and, when it is close, a rewrite that says only what the
# quote says; it goes only when neither holds.
FIX_PROMPT = "claims_fix_v1"
# Models too small to judge claims: on 28 Oct qwen3:1.7b removed 2 of 8 true sentences in the
# claim benchmark (qwen3.5:4b removed 1, qwen3.5:9b none), so they do not check.
TOO_SMALL = re.compile(r"[:-](0\.\d+|1(\.\d+)?)b\b", re.I)
VERDICTS = ("supported", "general", "unsupported", "contradicted", "no_claim")
REMOVE = ("unsupported", "contradicted")
MAX_SENTENCES = 12
SOURCE_CHARS = 3600  # the least the checker reads (about 1,100 tokens); more when it fits
MAX_SOURCE_CHARS = 14000  # at most: about 4,400 tokens, within an 8k context


@dataclass
class ClaimCheck:
    """What the checker found and what was removed."""

    checked: List[str] = field(default_factory=list)
    verdicts: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    text: str = ""
    call: Optional[LLMCall] = None
    quote_call: Optional[LLMCall] = None
    kept: List[str] = field(default_factory=list)  # flagged, then backed by a quote
    reworded: List[Tuple[str, str]] = field(default_factory=list)  # (as written, as mended)
    skipped: str = ""
    unavailable: str = ""
    fallback: bool = False

    def meta(self) -> dict:
        """Return what the step row shows."""
        if self.skipped:
            return {"decided_by": "skipped", "checked": 0, "note": self.skipped}
        count = {v: self.verdicts.count(v) for v in VERDICTS}
        out = {
            "decided_by": "model",
            "checked": len(self.checked),
            "supported": count["supported"],
            "general": count["general"],
            "removed": len(self.removed),
        }
        if self.removed:
            out["removed_sentences"] = self.removed
        if self.kept:
            out["kept_with_quote"] = len(self.kept)
        if self.reworded:
            out["reworded"] = len(self.reworded)
            out["reworded_sentences"] = [[a, b] for a, b in self.reworded]
        if self.fallback:
            out["note"] = "most of the reply was unsupported; showed the checked template"
        return out


def candidates(text: str, draft: str = "") -> List[str]:
    """Return the reply's sentences worth checking (not from the draft, no rows, no questions)."""
    plain_draft = _norm(draft)
    out = []
    for line in text.split("\n"):
        if TABLE_ROW.match(line) or TABLE_RULE.match(line) or not line.strip():
            continue
        lead = LINE_LEAD.match(line)
        body = line[len(lead.group(0)) :] if lead else line
        for s in sentences(body):
            plain = _norm(s)
            if len(plain) < 20 or s.rstrip().endswith("?") or (plain and plain in plain_draft):
                continue
            out.append(s)
    return out[:MAX_SENTENCES]


SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")  # "CO₂" in a block, "CO2" in a reply


def _norm(text: str) -> str:
    text = strip_cites(text).replace("**", "").replace("`", "").translate(SUBSCRIPTS)
    return re.sub(r"\s+", " ", text).strip().lower()


def schema(n: int) -> dict:
    """Return the JSON schema: one verdict per sentence, in order."""
    return {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {"type": "string", "enum": list(VERDICTS)},
                "minItems": n,
                "maxItems": n,
            }
        },
        "required": ["verdicts"],
    }


# The conversation as the checker reads it: who said what, and when. What Dioscuri said is
# evidence that it said it, never of a value (the prompt says so too).
SAID = (
    "the conversation so far: who said what and when (Dioscuri's words prove only that it said "
    "them)"
)


def sources(blocks: Sequence[Block], used: Sequence[str], text: str = "") -> List[Block]:
    """Return the blocks the checker reads, most relevant first (the budget cuts the end).

    The draft (a tool's checked result) and opened files come first: they are sources whether
    cited or not. Then the blocks the reply named, then the rest ranked by how many of the
    reply's numbers they hold (1 Nov: the investor's figures were removed as unsupported
    because the economics block had been cut off behind the others), then the project's facts
    and the self note. The values code wrote for the question rank with the rest: the draft
    holds them already, and put first they pushed the project's facts past the budget (5 Nov).
    Then the conversation, the user's words and Dioscuri's: a reply about the chat itself ("your
    first question was ...", "I said 61.6 °C") is checked against it (4 Nov: true recalls were
    removed when only the user's lines were kept). Dioscuri's own earlier words count only as
    what was said, never as a value (a false comparison of 31 Oct backed itself for four
    turns); a reply that relied on the conversation reads it first.
    """
    wanted = set(used)
    # What the user asked to remember (``memory``) is short and is what a reply addressing
    # them rests on: it is read first, with the draft.
    lead = [b for b in blocks if b.kind in ("draft", "data", "notes")]
    tail = [b for b in blocks if b.kind in ("project", "self")]
    rest = [
        b for b in blocks if b.kind not in ("draft", "data", "notes", "project", "self", "history")
    ]
    said = {round(x, 2) for x in numbers_in(text)} if text else set()

    def overlap(b: Block) -> int:
        return len(said & {round(x, 2) for x in numbers_in(b.text)}) if said else 0

    rest.sort(key=lambda b: (b.id not in wanted, -overlap(b)))
    chat = [replace(b, title=SAID) for b in blocks if b.kind == "history"]
    if "history" in wanted:
        return lead + chat + rest + tail
    return lead + rest + tail + chat


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9°€.,/%-]+", _norm(text).replace("**", ""))


def quoted(quote: str, sources: str) -> bool:
    """Return True when a quote is really in the sources (a few words may differ).

    A quote cut with "..." is its parts: each of four words or more must be in the sources
    (5 Nov: "cost of heat 64.7 €/MWh; ... cost of cold 30.4 €/MWh;" was refused whole).
    """
    if not re.search(r"\.\.\.|…", quote):
        return _quoted(quote, sources)
    parts = [p for p in re.split(r"\.\.\.|…", quote) if len(_words(p)) >= 4]
    return bool(parts) and all(_quoted(p, sources) for p in parts)


def _quoted(quote: str, sources: str) -> bool:
    q = _words(quote)
    if len(q) < 4:
        return False
    src = " ".join(_words(sources))
    if " ".join(q) in src:
        return True
    grams = [" ".join(q[i : i + 3]) for i in range(len(q) - 2)]
    return sum(g in src for g in grams) >= 0.85 * len(grams)


STOP = set(
    "the a an of to in on at for and or is are was were be been it its this that these those "
    "with by from as than then so not no any all each every which who what when where how "
    "does do did has have had can could will would may might must shall should into about "
    "above below after before over under up down out off very also only just more most less "
    "our your their his her my we you they he she i me us them there here".split()
)
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
FIGURE = re.compile(r"(?<![A-Za-z\d.,])\d+(?:[.,]\d+)*")  # a number on its own, not in a name


def _content(text: str) -> set:
    return {
        w for w in _words(text) if w not in STOP and (len(w) > 2 or any(c.isdigit() for c in w))
    }


def _numbers(text: str) -> set:
    return {n.replace(",", "") for n in NUMBER.findall(text)}


def backs(sentence: str, quote: str, sources: str = "") -> bool:
    """Return True when a quote is about the sentence, not just somewhere near its topic.

    Every number in the sentence must be in the quote or elsewhere in the sources, and the
    quote must share a third of the sentence's content words. On 30 Oct a quote about the
    wellhead temperature kept a sentence that invented why the brine was hotter than the
    reservoir.
    """
    if not _numbers(sentence) <= _numbers(quote) | _numbers(sources):
        return False
    words = _content(sentence)
    if not words:
        return True
    return len(words & _content(quote)) >= max(1, round(0.34 * len(words)))


# Before a flagged sentence goes, its best evidence from every block the reply was written from:
# the checker's sources are cut at its budget, and a sentence whose evidence fell past the cut
# read as unsupported (5 Nov: "a geothermal gradient of 30 °C/km", "the boiler covers 34.5 % of
# the year's heat" and "we cannot drill five doublets" were removed; the project's facts and the
# end of the design block, which say each, were past the cut).
EVIDENCE_LINES = 4  # the lines that share the most with each flagged sentence
EVIDENCE_CHARS = 2400  # at most, for all the flagged sentences together
EVIDENCE_TITLE = (
    "[evidence] (the context's lines that share the most words and numbers with each "
    "statement, from every block the reply was written from)"
)


def evidence(flagged: Sequence[str], blocks: Sequence[Block]) -> str:
    """Return the lines of all the blocks that share the most with each flagged sentence.

    Every block the reply was written from, whatever the checker's budget left out; not the
    conversation, which shows only what was said (``sources``). A line is a sentence or a
    ";"-separated fact of a block, at most 400 characters; it is scored by the content words
    and the numbers it shares with the sentence (a number counts twice); the best four are kept.
    """
    pieces: List[str] = []
    for b in blocks:
        if b.kind == "history":
            # Never the conversation: a user's wrong premise would back the reply that repeats
            # it. What the user asked to remember (their name) is in the ``notes`` block.
            continue
        for part in re.split(r"(?<=[.;])\s+|\n+", b.text):
            part = " ".join(part.split())
            if len(part) >= 12 and part[:400] not in pieces:
                pieces.append(part[:400])

    def terms(text: str) -> set:
        return {w.strip(".,:;%()") for w in _content(text)} - {""}

    def figures(text: str) -> set:  # not the 2 of CO2
        return _numbers(" ".join(FIGURE.findall(text.translate(SUBSCRIPTS))))

    known = [(terms(p), figures(p)) for p in pieces]
    picked: List[str] = []
    for sentence in flagged:
        words, nums = terms(strip_cites(sentence)), figures(sentence)
        score = [len(words & w) + 2 * len(nums & n) for w, n in known]
        best = sorted(range(len(pieces)), key=lambda k: -score[k])[:EVIDENCE_LINES]
        picked += [pieces[k] for k in best if score[k] >= 1 and pieces[k] not in picked]
    lines, size = [], 0
    for line in picked:
        if size + len(line) > EVIDENCE_CHARS:
            break
        lines.append("- " + line)
        size += len(line) + 3
    return "\n".join(lines)


def backed(
    llm, flagged: Sequence[str], sources: str
) -> Tuple[List[str], Optional[LLMCall], List[Tuple[str, str]]]:
    """Return the flagged sentences a quote backs, the call, and those mended by a rewrite.

    The model gives each flagged sentence a quote and, when it is close but worded wrong, a
    rewrite (``FIX_PROMPT``). A sentence stays when its quote is in the sources (``quoted``) and
    is about it (``backs``); else its rewrite takes its place when the quote backs the rewrite
    and every number of the rewrite is in the sources; else it goes.
    """
    numbered = "\n".join(f"{i + 1}. {_flat(strip_cites(s), 300)}" for i, s in enumerate(flagged))
    n = len(flagged)
    strings = {"type": "array", "items": {"type": "string", "maxLength": 300}}
    schema = {
        "type": "object",
        "properties": {
            "quotes": dict(strings, minItems=n, maxItems=n),
            "fixed": dict(strings, minItems=n, maxItems=n),
        },
        "required": ["quotes", "fixed"],
    }
    msgs = [
        {"role": "system", "content": load(FIX_PROMPT)},
        {"role": "user", "content": f"Sources:\n{sources}\n\nStatements:\n{numbered}"},
    ]
    try:
        raw, call = llm.structured("claims_quote", msgs, schema, 40 + 160 * n)
    except LLMError as err:
        return [], err.call, []
    quotes = [str(q) for q in raw.get("quotes") or []]
    fixes = [str(f) for f in raw.get("fixed") or []]
    quotes += [""] * (n - len(quotes))
    fixes += [""] * (n - len(fixes))
    kept, mended = [], []
    for s, q, f in zip(flagged, quotes, fixes):
        good = bool(q.strip()) and quoted(q, sources)
        if good and backs(s, q, sources):
            kept.append(s)
        elif good and mends(s, f, q, sources):
            mended.append((s, f.strip()))
    return kept, call, mended


def mends(sentence: str, fixed: str, quote: str, sources: str) -> bool:
    """Return True when a rewrite may stand for a flagged sentence (code's checks).

    It must differ from the sentence, be about as long (not a new paragraph), keep to the
    numbers the sources give, and be backed by the quote (``backs``).
    """
    fixed = fixed.strip()
    if not fixed or _norm(fixed) == _norm(sentence) or fixed.endswith("?"):
        return False
    if len(fixed) > 2 * len(sentence) + 80:
        return False
    if not _numbers(fixed) <= _numbers(sources):
        return False
    return backs(fixed, quote, sources)


def budget(llm) -> int:
    """Return the source characters the checker may read for this model's context.

    Twice the cap in a window over 8k (the 9b on the GPU, 16k): a cited search block of 9,000
    characters left no room for the designs, and true sentences were removed (4 Nov). On the
    CPU (8k) the cap stays: a longer prompt costs half a minute there.
    """
    ctx = int(getattr(llm, "options", {}).get("num_ctx", 4096))
    chars = int((ctx - 900) * 3.2)  # the prompt, the reply's sentences and the verdicts
    cap = MAX_SOURCE_CHARS * (2 if ctx > 8192 else 1)
    return max(SOURCE_CHARS, min(cap, chars))


def check(
    llm, text: str, blocks: Sequence[Block], used: Sequence[str], draft: str = ""
) -> ClaimCheck:
    """Check a reply's sentences against its sources and remove the unsupported ones.

    Parameters
    ----------
    llm : OllamaLLM or ScriptedLLM
        The checking model.
    text : str
        The reply, after the number checks.
    blocks : sequence of Block
        The context pack the reply was written from.
    used : sequence of str
        The ids the reply relied on.
    draft : str
        The checked template, when the reply rewords one (its sentences are not sent).

    Returns
    -------
    ClaimCheck
        The verdicts, the removed sentences and the text without them. ``fallback`` says that
        more than half of the checked sentences were removed.
    """
    out = ClaimCheck(text=text)
    out.checked = candidates(text, draft)
    if not out.checked:
        out.skipped = "nothing to check: the reply repeats the checked answer"
        return out
    context, size, limit = [], 0, budget(llm)
    for b in sources(blocks, used, text):
        line = b.render()
        if size + len(line) > limit:
            line = line[: max(0, limit - size)]
        if line:
            context.append(line)
            size += len(line)
    numbered = "\n".join(
        f"{i + 1}. {_flat(strip_cites(s), 300)}" for i, s in enumerate(out.checked)
    )
    msgs = [
        {"role": "system", "content": load(CLAIMS_PROMPT)},
        {"role": "user", "content": "Sources:\n" + "\n".join(context) + "\n\nReply:\n" + numbered},
    ]
    try:
        raw, out.call = llm.structured(
            "claims", msgs, schema(len(out.checked)), 20 + 8 * len(out.checked)
        )
    except LLMError as err:
        out.call = err.call
        out.unavailable = str(err) if isinstance(err, ModelUnavailable) else ""
        out.skipped = "the checking model gave no usable verdicts; the reply is shown as written"
        return out
    verdicts = [str(v) for v in raw.get("verdicts") or []]
    verdicts = (verdicts + ["supported"] * len(out.checked))[: len(out.checked)]
    out.verdicts = [v if v in VERDICTS else "supported" for v in verdicts]
    out.removed = [s for s, v in zip(out.checked, out.verdicts) if v in REMOVE]
    if out.removed:
        # Asked for a quote, the model reads each flagged sentence's best evidence from every
        # block the reply was written from first, then the sources it judged from.
        near = evidence(out.removed, blocks)
        bundle = "\n".join(([EVIDENCE_TITLE + "\n" + near] if near else []) + context)
        out.kept, out.quote_call, out.reworded = backed(llm, out.removed, bundle)
        mended = {a for a, _ in out.reworded}
        out.removed = [s for s in out.removed if s not in out.kept and s not in mended]
    kept = text
    for old, new in out.reworded:
        kept = kept.replace(old, new)
    out.text = kept
    if not out.removed:
        return out
    claims = [v for v in out.verdicts if v != "no_claim"]
    out.fallback = len(out.removed) * 2 > len(claims)  # the caller decides what to show
    for s in out.removed:
        kept = kept.replace(s, "")
    kept = re.sub(r"[ \t]{2,}", " ", kept)
    kept = re.sub(r"^\s*([-*]|\d+[.)])\s*$", "", kept, flags=re.M)  # an emptied list item
    out.text = re.sub(r"\n{3,}", "\n\n", kept).strip()
    return out
