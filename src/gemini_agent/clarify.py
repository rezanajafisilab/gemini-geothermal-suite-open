"""Clarifying with concrete choices: one short question, two or three options to act on at once.

On 4 Nov a request that left out what it needed ran on a guess: "Run it again with 2." ran with
2 doublets, "Use the setting we talked about." (none was) ran the recommended design, and the
small model ran "And if gas gets more expensive?" with no amount (and a misread flaring switch).
A missing amount asked "By how much?" with three steps from the value now, which for an option
the design does not have yet ("add a heat store": 0 MWh now) offered sizes no one would build.

The decision stays in the model's reading (``parameters`` reads ``unclear``: the words whose
referent the message and the conversation leave open, and what they most likely mean, with a
rule and examples on both sides, act and ask). Code then:

- checks that a run has every amount it needs: a change asked without one (``Reading.vague``)
  is asked about before anything runs, the other changes of the message kept for the run after;
- builds the options from the catalogue and the design: typical sizes from the catalogue's
  range for an option being added (a store, solar panels, a network), steps from the value now
  for a change (a price, a temperature), whole steps for a count (doublets), the likely
  referents for a bare number ("2 doublets, or a 2 MW heat pump?"), the settings run earlier for
  "the setting we talked about" (else options the design does not have yet);
- keeps the offered choices with the question (``session.pending``: each option and the full
  request it runs), so the next message ("the first", "5,000", "doublets") is read against them.

``DIOSCURI_CLARIFY_CHOICES=0`` turns it off: the reading has no ``unclear`` field, a vague
change runs the rest as before, and "By how much?" offers the old steps.
"""

from __future__ import annotations

import math
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

from gemini_agent import parameters

# The parameters reading's field: the words whose referent is open, and what they may mean.
FIELD = {
    "type": "array",
    "maxItems": 1,
    "items": {
        "type": "object",
        "properties": {
            "quote": {"type": "string"},
            "could_be": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        },
        "required": ["quote", "could_be"],
    },
}
# The rule, after the parameters prompt (full and short forms); examples on both sides.
RULE = (
    "open: [] unless the message asks to run something but leaves open what a number or "
    "setting is for and the conversation does not say: then [{quote, could_be: up to three "
    'keys it may mean, [] if none fits}] and no change from those words. Ask: "run it again '
    'with 2" (["n_doublets", "heat_pump_mw"]); "use the setting we talked about" when none '
    'was ([]). Act: "with 2 doublets", "a store of 5,000 MWh", "return temperature 50 C", '
    '"heated 50, cooled 10" (code checks values). A change without its amount ("add a store", '
    '"gas gets dearer") is a change (a size 0), not open: Dioscuri asks how much.'
)
SHORT_RULE = (
    "open: the words of a number or setting whose referent neither the message nor the "
    'conversation gives ("run it again with 2"), with could_be: up to three keys; else [].'
)


def on() -> bool:
    """Return True unless ``DIOSCURI_CLARIFY_CHOICES`` turns clarifying with choices off."""
    return os.environ.get("DIOSCURI_CLARIFY_CHOICES", "1").strip().lower() not in (
        "0",
        "false",
        "off",
        "no",
    )


def schema(base: dict) -> dict:
    """Return the parameters reading's schema, with ``open`` when the flag is on."""
    if not on():
        return base
    out = dict(base, properties=dict(base["properties"], open=FIELD))
    out["required"] = list(base["required"]) + ["open"]
    return out


def rule(short: bool = False) -> str:
    """Return the rule to add after the parameters prompt ("" when off)."""
    if not on():
        return ""
    return "\n\n" + (SHORT_RULE if short else RULE)


def read_unclear(raw: dict, message: str, reading) -> Optional[dict]:
    """Return the reading's checked ``open`` item, and drop the changes read from its words.

    The quote must be the message's own; ``could_be`` keeps catalogue keys only. A change whose
    quote is inside the unclear words (or holds them) is the guess the item says is open: it
    goes, so nothing runs on it.
    """
    if not on():
        return None
    items = raw.get("open") if isinstance(raw, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None
    quote = " ".join(str(items[0].get("quote") or "").split())
    text = parameters._norm(message)
    if not quote or parameters._norm(quote) not in text:
        return None
    keys = [
        str(k)
        for k in items[0].get("could_be") or []
        if str(k) in parameters.CATALOGUE and not parameters.CATALOGUE[str(k)].card_only
    ][:3]
    q = parameters._norm(quote)
    taken = [
        key
        for key, said in reading.quotes.items()
        if parameters._norm(said) and (parameters._norm(said) in q or q in parameters._norm(said))
    ]
    if len(keys) == 1 and keys[0] in taken:
        return None  # the words name what they set ("with 2 doublets"): nothing is open
    # Only a request that would run something can leave a referent open (the rule says so; on
    # 4 Nov the 9B also filled the field for questions and premises: "Well depth?", "the CO2
    # saving is 80 %, isn't it?" were asked "which setting?"). A message that says what it
    # changes besides the open words, or whose open words are a change it read ("cool with
    # outside air"), has nothing open either.
    if not any(s.do in ("design", "what_if") for s in reading.steps):
        if not ([k for k in reading.changes if k not in taken] or reading.doublets):
            reading.open_unrun = {"quote": quote, "could_be": keys}
        return None
    if [k for k in reading.changes if k not in taken] or reading.doublets or reading.failures:
        return None
    if not keys and taken:
        return None
    for key in taken:
        reading.changes.pop(key, None)
        reading.items = [x for x in reading.items if x[0] != key]
        reading.dropped.append(f"{key}: read from “{quote}”, which the reading left open")
    if not (reading.changes or reading.doublets or reading.failures):
        reading.steps = [s for s in reading.steps if s.do not in ("design", "what_if")]
    return {"quote": quote, "could_be": keys}


# Words that name nothing (and the small numbers, which are the amount itself).
NAMES_NOTHING = set(
    "the and for with its has are was how many each lets from into that this than then when "
    "what which but not all any one two three four five six none".split()
)


def _stems(text: str) -> set:
    """Return the words of three letters or more, cut to their first four letters."""
    words = [w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if re.search("[a-z]", w)]
    return {w[:4] for w in words if w not in NAMES_NOTHING}


def names_key(message: str, key: str) -> bool:
    """Return True when the message says what a number sets: a word of the key's name or unit.

    The name is the catalogue's label, the first sentence of its help and the key's own words
    ("number of doublets", "a producer and an injector well each", "n_doublets"), compared by
    their first four letters; an amount with a unit of the key's dimension names it too.
    """
    from gemini_agent import quantities

    p = parameters.CATALOGUE[key]
    dim = quantities.KEY_UNITS.get(p.unit, ("", 1.0))[0]
    if dim and any(q.clear and q.dimension == dim for q in quantities.extract(message)):
        return True
    first = re.split(r"(?<=[.;])\s", p.help or "", maxsplit=1)[0]
    words = _stems(p.label) | _stems(first) | _stems(key.replace("_", " "))
    return bool(words & _stems(message))


def bare_numbers(reading, message: str, earlier: Sequence[str] = ()) -> Optional[dict]:
    """Return an ``open`` item for a change read from a bare number, and drop that change.

    "Run it again with 2", "hmm 70" (5 Nov): the reader set doublets or a store from a number
    the words give nothing for. A number is bare when the message gives it no unit and no word
    of the setting's name; a setting the conversation's last what-if changed (``earlier``) is
    the referent ("and with 45?" after a gas price). Code checks only that the words name the
    setting; what a named number means stays the model's reading.
    """
    from gemini_agent import quantities

    if not on() or reading.open_ref or reading.doublets or reading.failures:
        return None
    amounts = quantities.extract(message)
    if not amounts or any(q.clear for q in amounts):
        return None
    numeric = [
        k
        for k, v in reading.changes.items()
        if isinstance(v, (int, float))
        and not isinstance(v, bool)
        and k in parameters.CATALOGUE
        and parameters.CATALOGUE[k].kind == "number"
        and k not in parameters.SWITCHES
    ]
    if not numeric or len(numeric) != len(reading.changes):
        return None
    if any(names_key(message, k) or k in earlier for k in numeric):
        return None
    for key in numeric:
        reading.changes.pop(key, None)
        reading.items = [x for x in reading.items if x[0] != key]
        reading.dropped.append(f"{key}: read from a bare number, which names no setting")
    reading.steps = [s for s in reading.steps if s.do not in ("design", "what_if")]
    x = amounts[0].value
    return {"quote": f"{x:g}", "could_be": _likely(x, numeric[:1])}


def _likely(x: float, could: Sequence[str] = ()) -> List[str]:
    """Return up to two settings a bare number may set.

    Those given first, then the doublets or the options whose typical range holds it.
    """
    from gemini_agent import capabilities

    out = list(could)
    for key in ["n_doublets"] + capabilities.option_keys():
        p = parameters.CATALOGUE.get(key)
        if p is None or key in out or key in parameters.SWITCHES or p.kind != "number":
            continue
        span = p.typical
        if span and span[0] <= x <= span[1] and len(out) < 2:
            out.append(key)
    return out


def names_nothing(message: str) -> bool:
    """Return True when a message's words name nothing: numbers, signs and sounds only.

    "3?", "42", "hmm 70": no word of three letters or more with a vowel, besides the small
    words that name nothing. Structure, not phrasing: any word that could name a setting, a
    design or a question ("doublets", "cost", "again") makes the message say something.
    """
    words = re.findall(r"[^\W\d_]+", (message or "").lower())
    return not any(
        len(w) >= 3 and re.search(r"[aeiouyà-ÿ]", w) and w not in NAMES_NOTHING for w in words
    )


def bare_message(message: str, earlier: Sequence[str] = ()) -> Optional[dict]:
    """Return an ``open`` item for a message that is a bare number, whatever it was read as.

    "3?" after a design (5 Nov): the reader took it for a question and the answerer guessed
    "a design with three doublets". A message whose words name nothing gives a number nothing
    to set: its likely referents are asked, with choices. A number with a unit says what it is
    ("2 GWh"); one in the range of a setting the chat's latest what-if changed is that setting
    ("and 45?" after a gas price), left to the reading. ``could_be`` holds the settings whose
    typical range holds the number: none ("42") is a message that cannot be read; one ("uh 15")
    is left to the reading, which reads it as unclear or as that setting.
    """
    from gemini_agent import quantities

    if not on() or not names_nothing(message):
        return None
    amounts = quantities.extract(message)
    if not amounts or any(q.clear for q in amounts):
        return None
    x = amounts[0].value
    for key in earlier:
        p = parameters.CATALOGUE.get(key)
        if p is not None and p.kind == "number" and p.low is not None and p.high is not None:
            if p.low <= x <= p.high:
                return None
    return {"quote": f"{x:g}", "could_be": _likely(x)}


def _nice(x: float) -> float:
    """Return ``x`` rounded to one significant figure (two below 10: 2.5, 6)."""
    if x <= 0:
        return 0.0
    power = 10 ** math.floor(math.log10(x))
    return round(x / power) * power if x >= 10 else round(x * 2) / 2


def choices(key: str, guess: float, now: float, quote: str = "") -> List[float]:
    """Return two or three amounts to offer for a change asked without one.

    An option the design does not have yet (0 now: a store, solar panels, a network): sizes
    across the catalogue's typical range. A count (doublets): the whole numbers the words point
    to. Anything else: ``parameters.amount_options`` (steps from the value now).
    """
    p = parameters.CATALOGUE[key]
    if not now and p.typical and p.typical[0] > 0:
        low, high = p.typical
        ratio = high / low
        out = [_nice(low * ratio ** (1 / 3)), _nice(low * ratio ** (2 / 3)), float(high)]
        return [v for i, v in enumerate(out) if v and v not in out[:i]]
    whole = p.unit == "" and p.kind == "number" and p.low is not None and p.high is not None
    if whole and float(p.low).is_integer() and float(p.high).is_integer() and p.high - p.low <= 10:
        down = bool(quote and parameters.DOWN.search(quote)) or (guess < now and not quote)
        span = (
            range(int(now) - 1, int(p.low) - 1, -1)
            if down
            else range(int(now) + 1, int(p.high) + 1)
        )
        return [float(v) for v in span][:3]
    return parameters.amount_options(key, guess, now, quote)


def _name(key: str) -> str:
    """Return a parameter's name for a question ("heat store at the plant")."""
    label = parameters.CATALOGUE[key].label
    label = re.sub(r"\s*\(.*\)$", "", label[0].lower() + label[1:])
    return label


def _shown(key: str, value: float) -> str:
    """Return a value with its unit ("1,000 MWh", "x1.2", "2")."""
    p = parameters.CATALOGUE[key]
    if p.unit == "x":
        return f"×{value:g}"
    unit = "" if p.unit in ("", "fraction") else f" {p.unit}"
    return f"{value:,g}{unit}"


def amount_question(
    key: str, guess: float, now: float, quote: str, kind: str, message: str, others: bool
) -> Tuple[str, List[str], Dict[str, str]]:
    """Return the question for a change asked without an amount, its options and their runs.

    ``others``: the message asks for other changes too; each option's run is then the message
    with the amount added, so they run together.
    """
    p = parameters.CATALOGUE[key]
    name = _name(key)
    options, requests = [], {}
    for v in choices(key, guess, now, quote):
        shown = _shown(key, v)
        option = (
            f"What if the {name} were {shown}?"
            if kind == "what_if"
            else f"Design with the {name} at {shown}"
        )
        options.append(option)
        requests[option] = f"{message.strip()} ({name}: {shown})" if others else option
    if not now and p.typical:
        typical = f" Typical: {p.typical_words}." if p.typical_words else ""
        text = f"What size for the {name}?{typical} Pick one, or type the size you have in mind."
    else:
        text = (
            f"By how much? The {name} is {_shown(key, now)} now. Pick one, or type the value "
            "you have in mind."
        )
    return text, options, requests


def referent_question(
    item: dict, message: str, now: Dict[str, object], earlier: Sequence[Tuple[str, object]]
) -> Tuple[str, List[str], Dict[str, str]]:
    """Return the question for words whose referent is open, its options and their runs.

    A number ("run it again with 2"): what it may be for, each a key of ``could_be`` whose
    range holds it. No number ("the setting we talked about"): the settings run earlier
    (``earlier``: key and value of the chat's what-ifs), else options the design lacks.
    """
    from gemini_agent.intake import numbers_in

    numbers = numbers_in(item["quote"])
    options, requests = [], {}
    if numbers:
        x = numbers[0]
        for key in item["could_be"]:
            p = parameters.CATALOGUE[key]
            if p.kind != "number" or not (p.low <= x <= p.high):
                continue
            option = f"{_name(key)[0].upper()}{_name(key)[1:]}: {_shown(key, x)}"
            options.append(option)
            requests[option] = f"{message.strip()} ({_name(key)}: {_shown(key, x)})"
        if options:
            listed = " or ".join(o.split(": ")[0].lower() for o in options)
            text = f"What should be {x:g}: the {listed}? Pick one, or say what you meant."
            return text, options, requests
    for key, value in earlier:
        if key not in parameters.CATALOGUE or len(options) >= 3:
            continue
        shown = _shown(key, float(value)) if isinstance(value, (int, float)) else str(value)
        option = f"What if the {_name(key)} were {shown}?"
        if option not in options:
            options.append(option)
            requests[option] = option
    if options:
        text = "Which setting do you mean? These are the ones we tried in this chat."
        return text, options, requests
    from gemini_agent import capabilities

    for key in capabilities.option_keys():
        p = parameters.CATALOGUE[key]
        if len(options) >= 3 or key in capabilities.WITH or now.get(key):
            continue
        if key in parameters.SWITCHES:
            option = f"What if the design had {capabilities.name(key)}?"
        elif p.typical:
            size = _nice((p.typical[0] * p.typical[1]) ** 0.5)
            option = f"What if the design had a {_name(key)} of {_shown(key, size)}?"
        else:
            continue
        options.append(option)
        requests[option] = option
    text = (
        "I can't find a setting we talked about in this chat. Which do you mean? Pick one, or "
        "tell me the setting and its value."
    )
    return text, options, requests


def objective_is_a_question(reading) -> bool:
    """Return True when a reading's only change is what "best" means but the reply needs none.

    "Back to the original design, its CO2 saving?" was read as a new search for the lowest CO2
    (4 Nov): the planner gave a design step with the objective, while the needs reading said the
    reply is about a design that exists. A new search needs the needs reading to say so. A
    what-if step alike: "heat under 70 euros a MWh?" (5 Nov) ran a search for the lowest cost
    and quoted another design's cost.
    """
    if not on():
        return False
    kinds = {s.do for s in reading.steps}
    return bool(
        set(reading.changes) == {"objective"}
        and not (reading.doublets or reading.failures or reading.vague)
        and kinds & {"design", "what_if"}
        and reading.new_design is False
        and reading.about_design is True
    )
