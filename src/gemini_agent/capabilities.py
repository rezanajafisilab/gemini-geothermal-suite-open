"""What the plant model can do: a short card generated from the code's own catalogues.

On 4 Nov the chat said of options the model has that it had none: "Add a heat store" got "I
cannot add a heat store ... no inputs for it", "Can we put PV on it?" got "cannot add PV", and
"cooling with outside air in winter, before the chillers" got "not currently modelled", though
free cooling is a switch of the plant. The answerer saw no list of what the plant can do, and
the reply for a request "not modelled" listed by hand what can be varied (without the store,
the solar panels or free cooling, which came later).

The card is generated, never written by hand: the plant's options are the options reading's
keys (``parameters.OPTION_KEYS``) and the stops, the units the search may use are the
catalogue's (``parameters.UNITS``), the economics are the catalogue's prices. A parameter added
to the catalogue is on the card with its own label, unit and typical values.

- ``card()``: the card for the answerer (a context block), about 900 characters;
- ``names()``: the options in a few words each, for a reading's prompt (one line);
- ``covers()``: before Dioscuri says it cannot do something, a short reading asks the model
  whether one of the card's options is meant (the model reads the meaning; code keeps the card).

``DIOSCURI_CAPABILITY_CARD=0`` turns it off: the prompts and replies are as before.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Sequence, Tuple

from gemini_agent import parameters
from gemini_agent.llm import LLMCall, LLMError

# The plant's options and settable inputs, in the card's order: the options reading's keys
# first (what a plant can add or switch), then the stops and maintenance.
STOPS = ("doublet_stops", "operating_days")
# A plant option's second key is said with the first (the second aquifer's rock with its depth).
WITH = {
    "storage_ates": "storage_mwh",
    "second_aquifer_thickness_m": "second_aquifer_depth_m",
    "second_aquifer_permeability_md": "second_aquifer_depth_m",
}
SAID_WHAT = ("free_cooling",)  # options the answerer's card explains (``answer_card``)
UNIT_NAMES = {  # the search's units (``parameters.UNITS``) as the card names them
    "heat_pump": "heat pump",
    "boiler": "gas boiler",
    "chiller": "electric chillers",
    "electric_boiler": "electric boiler",
}
# What a label says for code, not for a reader ("1 on, 0 off", "(0: none)", "set with ...").
CODE_NOTES = re.compile(
    r";?\s*\b1 on, 0 (off|a tank)\b|\s*\(0: [^)]*\)|;\s*0: none|;\s*set with its size in \w+|"
    r"\s*\(value: [^)]*\)|\bwith storage_ates on\b",
    re.I,
)


def on() -> bool:
    """Return True unless ``DIOSCURI_CAPABILITY_CARD`` turns the card off."""
    return os.environ.get("DIOSCURI_CAPABILITY_CARD", "1").strip().lower() not in (
        "0",
        "false",
        "off",
        "no",
    )


def _label(key: str) -> str:
    """Return a parameter's label without the notes meant for code."""
    text = CODE_NOTES.sub("", parameters.CATALOGUE[key].label)
    text = re.sub(r"\(\s*[;,]?\s*", "(", text)
    text = re.sub(r"\s*[;,]\s*\)", ")", text)
    return re.sub(r"\s*\(\s*\)", "", re.sub(r"\s+", " ", text)).strip(" ;,")


def name(key: str) -> str:
    """Return an option's short name: its label's head (with a short aside such as "(PV)").

    A long head ("Depth of the middle of a second aquifer the wells could be drilled to") gives
    way to the key's words ("second aquifer depth").
    """
    label = _label(key)
    head = re.split(r"\s*[(;:]", label, maxsplit=1)[0].strip()
    aside = re.match(r"^[^(]*\(([^()]{1,12})\)", label)
    if aside and len(aside.group(1).split()) <= 2:
        head += f" ({aside.group(1)})"
    if len(head.split()) > 6:
        words = [w for w in key.split("_") if w not in ("m", "km", "md", "mwh", "mwp", "c")]
        head = " ".join(words)
    return head[0].lower() + head[1:] if head[:2] != head[:2].upper() else head


def _about(key: str) -> str:
    """Return what an option is, in its label's own aside, when it says more than its name."""
    m = re.search(r"\(([^()]{13,})\)", _label(key))
    return m.group(1).split(";")[0].strip() if m else ""


def option_keys() -> List[str]:
    """Return the plant's options and settable inputs (catalogue keys), in the card's order."""
    keys = [k for k in parameters.OPTION_KEYS if k in parameters.CATALOGUE]
    return keys + [k for k in STOPS if k in parameters.CATALOGUE and k not in keys]


def _line(key: str, about: bool = True) -> str:
    """Return one option: its name, key, unit, typical range and, if asked, what it is."""
    p = parameters.CATALOGUE[key]
    bits = [key]
    if p.unit not in ("", "x", "fraction"):
        bits.append(p.unit)
    if p.typical:
        bits.append(f"typically {p.typical[0]:,g} to {p.typical[1]:,g}")
    said = _about(key) if about else ""
    return f"{name(key)} ({', '.join(bits)}{': ' + said if said else ''})"


def units() -> List[str]:
    """Return the units a design search may use or rule out, by name."""
    return [UNIT_NAMES.get(u, u.replace("_", " ")) for u in parameters.UNITS]


def economics() -> List[str]:
    """Return the economics inputs (the catalogue's prices, the grid's CO2), by name."""
    keys = [k for k, p in parameters.CATALOGUE.items() if p.target == "prices"]
    keys += [k for k in ("grid_t_co2_per_mwh",) if k in parameters.CATALOGUE]
    return [name(k) for k in keys]


def card() -> str:
    """Return what the plant model can do, generated from the catalogues (for the answerer)."""
    parts = []
    for key in option_keys():
        if key in WITH or key in ("grid_t_co2_per_mwh",):
            continue
        line = _line(key, about=key in ("free_cooling", "storage_mwh", "co2_reinjection"))
        joined = [k for k, to in WITH.items() if to == key]
        if joined:
            line += " with " + ", ".join(joined)
        parts.append(line)
    return (
        "What the plant model can do (each is simulated over the year: run it, or ask its "
        "size; never call it not modelled). Options: "
        + "; ".join(parts)
        + ". Units the search may use or rule out: "
        + ", ".join(units())
        + ". Economics: "
        + ", ".join(economics())
        + ". Doublets: 1 to 3, depths and aquifers, injectors, treatment trains, open parts, "
        "base-load dispatch; a unit out (a failure) on given days."
    )


def names() -> str:
    """Return the plant's options in a few words each with their keys, for a reading (one line)."""
    parts = [f"{name(k)} ({k})" for k in option_keys() if k not in WITH]
    return "; ".join(parts) + "; an electric boiler (allow, exclude)"


def answer_card() -> str:
    """Return the card for the answerer: the options by name, the units, the economics."""
    skip = {k for k in WITH if k != "storage_ates"} | {"grid_t_co2_per_mwh"}
    # An option whose name is read another way says what it is (5 Nov: "free cooling" was
    # taken for groundwater, and cooling with outside air called not modelled).
    options = [
        name(k) + (f" ({_about(k)})" if k in SAID_WHAT and _about(k) else "")
        for k in option_keys()
        if k not in skip
    ]
    return (
        "Plant options Dioscuri simulates over the year (run them, or ask their size; never "
        "call them not modelled): "
        + "; ".join(options)
        + ". Units a design may use or rule out: "
        + ", ".join(units())
        + ". Economics inputs: "
        + ", ".join(economics())
        + "."
    )


def block():
    """Return the card as a context block for the answerer, or None when it is off."""
    if not on():
        return None
    from gemini_agent import answer as answering

    return answering.Block("capabilities", "self", answer_card(), "what the plant model can do")


COVERS_PROMPT = (
    "Dioscuri's plant model has the options listed. A message asked for something Dioscuri "
    "first read as not in the model. Say which option it is, by its key, if any: read the "
    "meaning, in any words or language (a tank, a buffer or a thermal battery is a heat "
    "store; panels or a PV field is own solar; cooling with outside air or the towers before "
    "the chillers is free cooling). none when no option is that thing (a wind turbine, a "
    "biomass boiler, another site). Reply with JSON only."
)


def covers(
    asks: Sequence[str], message: str, llm, thread: str = ""
) -> Tuple[Optional[str], Optional[LLMCall]]:
    """Return the option key a request filed as not modelled is, or None; and the call.

    Asked once before a reply says the model cannot do something (``asks``: what the reading
    filed as unsupported). The key must be one of the card's options.
    """
    keys = option_keys()
    schema = {
        "type": "object",
        "properties": {"key": {"type": "string", "enum": keys + ["none"]}},
        "required": ["key"],
    }
    listed = "\n".join(_line(k) for k in keys)
    context = f"Conversation so far:\n{thread}\n\n" if thread else ""
    msgs = [
        {"role": "system", "content": COVERS_PROMPT},
        {
            "role": "user",
            "content": f"Options:\n{listed}\n\n{context}Message: {message}\n"
            f"Read as not in the model: {'; '.join(asks)}",
        },
    ]
    try:
        raw, call = llm.structured("covers", msgs, schema, 30)
    except LLMError as err:
        return None, err.call
    key = str(raw.get("key") or "") if isinstance(raw, dict) else ""
    return (key if key in keys else None), call


def unsupported_text(asks: Sequence[str], chosen=None) -> str:
    """Return the reply for a request the model cannot vary, with the card's list of what it can.

    The list is generated (``card``); the hand-written one in ``reporter.unsupported_text``
    left out the store, the solar panels and free cooling.
    """
    from gemini_agent import reporter

    what = reporter.unsupported_note(asks) or "that"
    options = [name(k) for k in option_keys() if k not in WITH]
    text = (
        f"I can't vary {what}: my plant model has no input for it, so any number I gave would "
        "be a guess. What I can run: the networks' temperatures, the reservoir and the "
        "aquifers, the challenge's caps, the demand, the doublets and how each is built, the "
        "units the search may use ("
        + ", ".join(units())
        + "), the plant's options ("
        + ", ".join(options)
        + ") and the economics ("
        + ", ".join(economics())
        + "). Ask for any of these and I'll run it."
    )
    if chosen is not None and chosen.year.electricity_gwh:
        # For scale, what the design draws from the grid (as ``reporter.unsupported_text``).
        y = chosen.year
        total = sum(v for v in y.electricity_gwh.values() if v)
        co2 = y.co2_t or {}
        text += (
            f" For scale: {chosen.alternative.code} draws {reporter.num(total)} GWh of "
            f"electricity a year, which gives {reporter.num(co2.get('electricity', 0.0), 0)} t "
            f"of its {reporter.num(co2.get('total', 0.0), 0)} t of CO2 a year."
        )
    return text
