"""The amounts a message gives: numbers with their units, converted to the catalogue's units.

Code reads number formats and units here: decimal commas ("4,5"), thousands separators
("1.500", "1,500"), small numbers in words (English and Dutch), fractions and multipliers ("a
fifth more" is x1.2, "20 procent minder" x0.8, "twice", "half"), and units (ct/kWh, EUR/MWh,
EUR/GJ, °C, °F, K, m3/h, l/s, kW, MWp, GWh, km ...). It never decides which parameter an amount
is for: that is the model's reading (``parameters.read``). An amount only says which values the
message supports for a key's unit (``supported``), so a reading can be checked against them and,
when in doubt, read again with them (``parameters.second_look``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_I = re.IGNORECASE

# The catalogue's units (``parameters.CATALOGUE``): their dimension and one unit in the
# dimension's base unit (°C, K, m, m3/h, MW, MWh, EUR/MWh ...).
KEY_UNITS: Dict[str, Tuple[str, float]] = {
    "°C": ("temperature", 1.0),
    "K": ("temperature_change", 1.0),
    "°C/km": ("gradient", 1.0),
    "mD": ("permeability", 1.0),
    "m": ("length", 1.0),
    "km": ("length", 1000.0),
    "bar": ("pressure", 1.0),
    "Nm3/m3": ("gas_ratio", 1.0),
    "days": ("days", 1.0),
    "m3/h": ("flow", 1.0),
    "t/MWh": ("emission", 1.0),
    "MW": ("power", 1.0),
    "MWp": ("power", 1.0),
    "MWh": ("energy", 1.0),
    "fraction": ("fraction", 1.0),
    "x": ("factor", 1.0),
    "EUR/MWh": ("energy_price", 1.0),
    "EUR/t": ("co2_price", 1.0),
}
# How each dimension is shown in a second look (the catalogue's units of it).
SHOWN_IN: Dict[str, Tuple[str, ...]] = {
    "temperature": ("°C",),
    "gradient": ("°C/km",),
    "permeability": ("mD",),
    "length": ("m", "km"),
    "pressure": ("bar",),
    "gas_ratio": ("Nm3/m3",),
    "days": ("days",),
    "flow": ("m3/h",),
    "emission": ("t/MWh",),
    "power": ("MW",),
    "energy": ("MWh",),
    "energy_price": ("EUR/MWh",),
    "co2_price": ("EUR/t",),
}

_PER = r"\s*(?:/|per|a|an|pro|the)\s*"
_EURO = r"(?:€|eur(?:os?)?\b|euro?s?\b)"
_CENT = r"(?:ct|cents?|eurocents?)\b"
_END = r"(?![a-zA-Z0-9³²€])"
# Units written after a number, tried in order (longer and costlier first): the regex, the unit
# as shown, its dimension and one of it in the dimension's base unit. Temperatures are worked
# out on their own (``_temperature``): a level in °F is not a change in °F.
UNIT_TABLE: Tuple[Tuple[str, str, str, float], ...] = (
    # Prices of energy, to EUR/MWh; of CO2, to EUR/t.
    (rf"{_CENT}{_PER}kwh\b", "ct/kWh", "energy_price", 10.0),
    (rf"{_CENT}{_PER}mwh\b", "ct/MWh", "energy_price", 0.01),
    (rf"{_CENT}{_PER}gj\b", "ct/GJ", "energy_price", 0.036),
    (rf"{_EURO}?{_PER}kwh\b", "EUR/kWh", "energy_price", 1000.0),
    (rf"{_EURO}?{_PER}mwh\b", "EUR/MWh", "energy_price", 1.0),
    (rf"{_EURO}?{_PER}gj\b", "EUR/GJ", "energy_price", 3.6),
    (rf"{_EURO}?{_PER}(?:t|tons?|tonnes?)\b(?:\s*(?:co2|co₂))?", "EUR/t", "co2_price", 1.0),
    # CO2 per unit of electricity, to t/MWh.
    (r"t(?:\s*co2|\s*co₂)?\s*(?:/|per)\s*mwh\b", "t/MWh", "emission", 1.0),
    (r"kg(?:\s*co2|\s*co₂)?\s*(?:/|per)\s*mwh\b", "kg/MWh", "emission", 0.001),
    (r"g(?:\s*co2|\s*co₂)?\s*(?:/|per)\s*kwh\b", "g/kWh", "emission", 0.001),
    (r"kg(?:\s*co2|\s*co₂)?\s*(?:/|per)\s*kwh\b", "kg/kWh", "emission", 1.0),
    # Gradients, to °C/km.
    (r"(?:°\s*c|k|degrees?|graden)\s*(?:/|per)\s*km\b", "°C/km", "gradient", 1.0),
    (r"(?:°\s*c|k|degrees?|graden)\s*(?:/|per)\s*100\s*m\b", "°C/100 m", "gradient", 10.0),
    # Flows, to m3/h.
    (r"(?:m³|m3)\s*/\s*(?:h|hr|hour|u|uur)\b", "m3/h", "flow", 1.0),
    (
        r"(?:m³|m3|cubic met(?:re|er)s?|kuub)\s+(?:per|an|a|in an?)\s+(?:hour|uur)\b",
        "m3/h",
        "flow",
        1.0,
    ),
    (r"(?:m³|m3)\s*/\s*(?:s|sec)\b", "m3/s", "flow", 3600.0),
    (r"(?:m³|m3|cubic met(?:re|er)s?)\s+(?:per|a)\s+second\b", "m3/s", "flow", 3600.0),
    (r"(?:m³|m3)\s*/\s*(?:d|day|dag)\b", "m3/day", "flow", 1 / 24),
    (r"l\s*/\s*s\b|lps\b", "l/s", "flow", 3.6),
    (r"(?:lit(?:re|er)s?|l)\s+(?:per|a|in een)\s+sec(?:ond|onde)?\b", "l/s", "flow", 3.6),
    (r"l\s*/\s*min\b", "l/min", "flow", 0.06),
    # Energy a year ("111 GWh/yr": a demand, no parameter of the catalogue), then energy, to
    # MWh (before power: "MWh" starts with "MW").
    (
        r"[tgmk]wh\s*(?:/|per|a|an|each|every)\s*(?:yr|year|jaar|annum|y)\b",
        "MWh/yr",
        "annual_energy",
        1.0,
    ),
    (r"twh\b", "TWh", "energy", 1e6),
    (r"gwh\b", "GWh", "energy", 1000.0),
    (r"mwh\b", "MWh", "energy", 1.0),
    (r"kwh\b", "kWh", "energy", 0.001),
    (r"(?:gigawatt[- ]hours?)\b", "GWh", "energy", 1000.0),
    (r"(?:megawatt[- ]hours?)\b", "MWh", "energy", 1.0),
    # Power, to MW (peak power of solar panels too).
    (r"gw(?:p|th|t|e)?\b", "GW", "power", 1000.0),
    (r"mw(?:p|th|t|e)?\b", "MW", "power", 1.0),
    (r"kw(?:p|th|t|e)?\b", "kW", "power", 0.001),
    (r"gigawatts?\b", "GW", "power", 1000.0),
    (r"megawatts?\b", "MW", "power", 1.0),
    (r"kilowatts?\b", "kW", "power", 0.001),
    # The aquifer's gas, its rock, its pressure.
    (r"n(?:m³|m3)\s*/\s*(?:m³|m3)\b", "Nm3/m3", "gas_ratio", 1.0),
    (r"md\b|millidarcys?\b", "mD", "permeability", 1.0),
    (r"darcys?\b", "D", "permeability", 1000.0),
    (r"bar[ag]?\b", "bar", "pressure", 1.0),
    (r"mpa\b", "MPa", "pressure", 10.0),
    (r"kpa\b", "kPa", "pressure", 0.01),
    (r"psi\b", "psi", "pressure", 0.0689476),
    # Lengths, to m.
    (r"km\b|kilomet(?:re|er)s?\b", "km", "length", 1000.0),
    (rf"m{_END}|met(?:re|er)s?\b|meter\b", "m", "length", 1.0),
    # Days a year.
    (r"days?\b|dagen\b|dag\b|d(?![a-zA-Z0-9])", "days", "days", 1.0),
    (r"weeks?\b|weken\b", "weeks", "days", 7.0),
    # Shares and multipliers.
    (r"%|percent\b|per\s?cent\b|procent\b|prozent\b|pct\b", "%", "percent", 1.0),
    (r"x(?![a-zA-Z0-9])|×|times\b|keer\b|maal\b", "x", "factor", 1.0),
)
UNITS = [(re.compile(rx, _I), unit, dim, f) for rx, unit, dim, f in UNIT_TABLE]
# Temperatures: a level (°C) or, said as a change or for a key in K, a difference (K).
CELSIUS = re.compile(
    r"(?:°|º)\s*c\b|℃|degrees?(?:\s*(?:c\b|celsius\b))?|celsius\b|graden(?:\s*celsius)?\b|"
    r"grad\b|"
    r"c(?![a-zA-Z0-9])",
    _I,
)
FAHRENHEIT = re.compile(r"(?:°|º)\s*[fF]\b|[fF]ahrenheit\b|F(?![a-zA-Z0-9])")
KELVIN = re.compile(r"K(?![a-zA-Z0-9/])|kelvin\b")

# Numbers in words: small ones, English and Dutch ("een" is the article; "één" is one).
NUMBER_WORDS: Dict[str, float] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "nul": 0,
    "één": 1,
    "twee": 2,
    "drie": 3,
    "vier": 4,
    "vijf": 5,
    "zes": 6,
    "zeven": 7,
    "acht": 8,
    "negen": 9,
    "tien": 10,
    "elf": 11,
    "twaalf": 12,
    "dertien": 13,
    "veertien": 14,
    "vijftien": 15,
    "zestien": 16,
    "zeventien": 17,
    "achttien": 18,
    "negentien": 19,
    "twintig": 20,
    "dertig": 30,
    "veertig": 40,
    "vijftig": 50,
    "zestig": 60,
    "zeventig": 70,
    "tachtig": 80,
    "negentig": 90,
    "honderd": 100,
}
_UNITS_EN = "one|two|three|four|five|six|seven|eight|nine"
_TENS_EN = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
_UNITS_NL = "een|één|twee|drie|vier|vijf|zes|zeven|acht|negen"
_TENS_NL = "twintig|dertig|veertig|vijftig|zestig|zeventig|tachtig|negentig"
NUMBER_WORD = re.compile(
    rf"\b(?:(?P<tens_en>{_TENS_EN})[- ](?P<unit_en>{_UNITS_EN})|"
    rf"(?P<unit_nl>{_UNITS_NL})[eë]n(?P<tens_nl>{_TENS_NL})|"
    rf"(?P<word>{'|'.join(sorted((w for w in NUMBER_WORDS), key=len, reverse=True))}))\b",
    _I,
)
# Fractions in words: "a fifth", "een kwart", "two thirds".
FRACTIONS: Dict[str, float] = {
    "half": 0.5,
    "third": 1 / 3,
    "thirds": 1 / 3,
    "quarter": 0.25,
    "quarters": 0.25,
    "fifth": 0.2,
    "fifths": 0.2,
    "sixth": 1 / 6,
    "tenth": 0.1,
    "tenths": 0.1,
    "helft": 0.5,
    "derde": 1 / 3,
    "kwart": 0.25,
    "vijfde": 0.2,
    "zesde": 1 / 6,
    "tiende": 0.1,
}
# Words that make an amount a change up or down ("20 % more", "10 K lower", "een vijfde meer").
UP = (
    r"more|higher|warmer|hotter|up|extra|larger|bigger|longer|deeper|dearer|pricier|"
    r"meer|hoger|groter|langer|dieper|duurder|erbij|mehr|höher"
)
DOWN = (
    r"less|lower|colder|cooler|down|smaller|shorter|shallower|cheaper|fewer|"
    r"minder|lager|kouder|koeler|kleiner|korter|ondieper|goedkoper|eraf|weniger|niedriger"
)
# After the amount also a Dutch verb: "de prijs met 20 % verhogen".
AFTER_UP = re.compile(rf"\s*(?:{UP}|verhog\w*|verhoog\w*|vergro\w*|stijg\w*|toenem\w*)\b", _I)
AFTER_DOWN = re.compile(
    rf"\s*(?:{DOWN}|verlag\w*|verlaag\w*|verminder\w*|verklein\w*|dal\w*|zak\w*)\b", _I
)
# "increase it by 20 %", "verlaag de prijs met 20 %": the verb before an amount after "by".
BY = re.compile(r"(?:\bby|\bmet|\bum)\s*$", _I)
VERB_UP = re.compile(
    r"\b(increas|rais|grow|add|boost|verhoog|vergrot|erhöh|up\b)\w*(?:\W+\w+){0,4}?\W*$", _I
)
VERB_DOWN = re.compile(
    r"\b(decreas|reduc|lower|cut|drop|lessen|shrink|verlaag|verminder|verklein|senk)\w*"
    r"(?:\W+\w+){0,4}?\W*$",
    _I,
)
# Multipliers in words: "double", "twice", "half", "triple", "verdubbelen", "de helft".
MULTIPLIERS: Tuple[Tuple[str, float], ...] = (
    (r"\b(?:double[sd]?|doubling|twice|verdubbel\w*|dubbel\w*|verdoppel\w*|doppelt)\b", 2.0),
    (r"\b(?:triple[sd]?|tripling|thrice|verdrievoudig\w*)\b", 3.0),
    (r"\b(?:halve[sd]?|halving|halveren|gehalveerd|halbier\w*)\b", 0.5),
    (r"\bhalf\s+(?:as\s+much|as\s+high|of\s+(?:it|that|what)|the|de|het)\b", 0.5),
    (r"\b(?:de\s+)?helft\b", 0.5),
    (r"\banderhalf\s+(?:keer|maal)\b", 1.5),
    (r"\bone and a half times\b", 1.5),
)
MULTIPLIER_RES = [(re.compile(rx, _I), f) for rx, f in MULTIPLIERS]
FRACTION_RE = re.compile(
    rf"\b(?:(?P<count>a|an|one|een|één|two|three|twee|drie)\s+)?"
    rf"(?P<frac>{'|'.join(sorted(FRACTIONS, key=len, reverse=True))})\b"
    rf"(?:\s+(?:of\s+(?:it|that)\s+)?(?P<dir>(?:{UP}|{DOWN}))\b)?",
    _I,
)
COUNT_WORDS = {"a": 1, "an": 1, "one": 1, "een": 1, "één": 1, "two": 2, "twee": 2}
COUNT_WORDS.update({"three": 3, "drie": 3})
# A number: digits with separators ("1.500,5", "2,500", "4,5"), a sign kept only in front.
DIGITS = re.compile(r"(?<![\w.,])[-−]?\d+(?:[.,]\d+)*")
# Words of a decimal-comma language (Dutch, German): "1,500" is then 1.5, "1.500" 1500.
DECIMAL_COMMA_WORDS = re.compile(
    r"\b(het|een|en|met|op|van|voor|naar|bij|wat|als|zijn|graag|hoeveel|warmte|koude|"
    r"prijs|und|mit|für|ist|der|das|bitte)\b",
    _I,
)


@dataclass(frozen=True)
class Quantity:
    """One amount of a message: the number as written, its unit and where it is.

    ``value`` is the number read ("4,5" is 4.5, "a fifth more" 1.2 with unit "x"); ``alt`` the
    other reading of an ambiguous separator ("1,500": 1500, else 1.5). ``change`` is "" for a
    level ("50 °C"), "+" or "-" for a change up or down ("10 K lower"), "?" for a change whose
    way the words leave to the reader ("by 20 %"), "x" for a multiplier ("twice", "a fifth
    more").
    """

    value: float
    unit: str
    dimension: str
    start: int
    end: int
    text: str
    factor: float = 1.0  # one ``unit`` in the dimension's base unit
    change: str = ""
    alt: Optional[float] = None

    @property
    def clear(self) -> bool:
        """Return True for an amount with a unit or a multiplier (not a bare count)."""
        return bool(self.dimension)

    @property
    def span(self) -> Tuple[int, int]:
        """Return where the amount is in the message (start, end)."""
        return self.start, self.end

    def numbers(self) -> List[float]:
        """Return the number as read, then its other reading if the separator was ambiguous."""
        return [self.value] + ([self.alt] if self.alt is not None else [])

    def base(self) -> List[float]:
        """Return the amount in its dimension's base unit (°C for a temperature level)."""
        if self.dimension == "temperature":
            out = [_level_c(self.unit, n) for n in self.numbers()]
            return [x for x in out if x is not None]
        return [n * self.factor for n in self.numbers()]

    def difference(self) -> List[float]:
        """Return a temperature amount as a difference in K ("9 °F" is 5 K)."""
        k = 5 / 9 if self.unit == "°F" else 1.0
        return [n * k for n in self.numbers()]

    def as_dict(self) -> dict:
        """Return the amount for traces and the second look's record."""
        out = {"text": self.text, "value": self.value, "unit": self.unit, "span": list(self.span)}
        if self.alt is not None:
            out["or"] = self.alt
        if self.change:
            out["change"] = self.change
        out["means"] = shown(self)
        return out


def _level_c(unit: str, n: float) -> Optional[float]:
    if unit == "°F":
        return (n - 32) * 5 / 9
    if unit == "K":
        return n - 273.15 if n >= 200 else None  # an absolute kelvin, not a difference
    return n


def _decimal_comma(message: str) -> bool:
    """Return True when the message writes numbers the Dutch way (a comma before decimals)."""
    for token in re.findall(r"\d+(?:[.,]\d+)+", message):
        if re.fullmatch(r"\d+,\d{1,2}", token) or re.fullmatch(r"\d+,\d{4,}", token):
            return True  # "4,5", "0,05": a decimal comma, unambiguous
        if re.fullmatch(r"\d{1,3}(?:\.\d{3}){2,}(?:,\d+)?|\d{1,3}(?:\.\d{3})+,\d+", token):
            return True  # "1.500.000", "1.500,5"
        if re.fullmatch(
            r"\d+\.\d{1,2}|\d{1,3}(?:,\d{3}){2,}(?:\.\d+)?|\d{1,3}(?:,\d{3})+\.\d+", token
        ):
            return False  # "4.5", "1,500,000", "1,500.5": the English way
    return len(DECIMAL_COMMA_WORDS.findall(message)) >= 2


def read_number(token: str, decimal_comma: bool = False) -> Tuple[Optional[float], Optional[float]]:
    """Return a written number and, when its separator is ambiguous, its other reading.

    Parameters
    ----------
    token : str
        Digits with separators: "4,5", "1.500", "1,500", "2,500,000", "1.500,5".
    decimal_comma : bool
        The message writes decimals after a comma (Dutch): "1,500" is then read 1.5 first.

    Returns
    -------
    tuple of (float or None, float or None)
        The number (None when the token is not one, a date "1.2.3"), and the other reading of a
        single separator before three digits ("1,500": 1500 or 1.5), else None.
    """
    t = token.replace("−", "-")
    sign = -1.0 if t.startswith("-") else 1.0
    t = t.lstrip("-")
    if "," in t and "." in t:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        thou = "." if dec == "," else ","
        head, _, tail = t.rpartition(dec)
        if thou not in head or not all(len(g) == 3 for g in head.split(thou)[1:]):
            return None, None
        return sign * float(head.replace(thou, "") + "." + tail), None
    sep = "," if "," in t else "." if "." in t else ""
    if not sep:
        return sign * float(t), None
    parts = t.split(sep)
    if len(parts) > 2:
        if all(len(g) == 3 for g in parts[1:]) and len(parts[0]) <= 3:
            return sign * float("".join(parts)), None
        return None, None
    head, tail = parts
    decimal = sign * float(head + "." + tail)
    if len(tail) != 3 or head == "0" or len(head) > 3:
        return decimal, None
    thousands = sign * float(head + tail)
    comma_decimal = sep == ","
    if decimal_comma == comma_decimal:  # "1,500" in Dutch, "1.500" in English: a decimal
        return decimal, thousands
    return thousands, decimal


def _unit_after(message: str, end: int) -> Optional[Tuple[str, str, float, int]]:
    """Return the unit written right after a number: (unit, dimension, factor, its end)."""
    rest = message[end:]
    gap = len(rest) - len(rest.lstrip("  "))
    rest = rest[gap:]
    for rx, unit, dim, f in UNITS:
        m = rx.match(rest)
        if m and m.group(0):
            return unit, dim, f, end + gap + m.end()
    for rx, unit in ((FAHRENHEIT, "°F"), (KELVIN, "K"), (CELSIUS, "°C")):
        m = rx.match(rest)
        if m and m.group(0):
            return unit, "temperature", 1.0, end + gap + m.end()
    return None


def _currency_before(message: str, start: int) -> bool:
    return bool(re.search(r"(?:€|\beur(?:os?)?)\s*$", message[:start], _I))


def _direction(message: str, start: int, end: int) -> str:
    """Return "+" or "-" when words beside an amount make it a change, "?" for "by N", else ""."""
    after = message[end:]
    if AFTER_UP.match(after):
        return "+"
    if AFTER_DOWN.match(after):
        return "-"
    before = message[:start]
    by = BY.search(before)
    if by:
        head = before[: by.start()]
        if VERB_DOWN.search(head):
            return "-"
        if VERB_UP.search(head):
            return "+"
        if by.group(0).strip().lower() in ("by", "um"):
            return "?"  # "change it by 20 %": which way is the reader's
    m = re.search(rf"\b({UP}|{DOWN})\s+$", before, _I)
    if m:  # "up 20 %", "down 5 K", "extra 10 MW": the word right before the number
        return "+" if re.fullmatch(UP, m.group(1), _I) else "-"
    return ""


def _numbers_with_spans(
    message: str, decimal_comma: bool
) -> List[Tuple[int, int, float, Optional[float]]]:
    found = []
    for m in DIGITS.finditer(message):
        value, alt = read_number(m.group(0), decimal_comma)
        if value is None:
            continue
        found.append((m.start(), m.end(), value, alt))
    for m in NUMBER_WORD.finditer(message):
        if m.group("word"):
            word = m.group("word").lower()
            if word not in NUMBER_WORDS:
                continue
            value = float(NUMBER_WORDS[word])
        elif m.group("tens_en"):
            value = (
                NUMBER_WORDS[m.group("tens_en").lower()] + NUMBER_WORDS[m.group("unit_en").lower()]
            )
        else:
            unit = m.group("unit_nl").lower()
            value = NUMBER_WORDS[m.group("tens_nl").lower()] + (
                1 if unit == "een" else NUMBER_WORDS[unit]
            )
        found.append((m.start(), m.end(), float(value), None))
    return sorted(found)


def extract(message: str) -> List[Quantity]:
    """Return the amounts a message gives, in order, each with its unit and span.

    Parameters
    ----------
    message : str
        The user's message.

    Returns
    -------
    list of Quantity
        Numbers with their units ("4,5 ct/kWh", "80 l/s", "five degrees"), multipliers ("a
        fifth more", "20 procent minder", "twice") and bare numbers (a count: ``clear`` False).
        Which parameter each is for is not said: the model reads that.
    """
    text = message or ""
    decimal_comma = _decimal_comma(text)
    out: List[Quantity] = []
    taken: List[Tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e in taken)

    def add(q: Quantity) -> None:
        out.append(q)
        taken.append(q.span)

    # Fractions with a way ("a fifth more", "een kwart minder") and multipliers in words.
    for m in FRACTION_RE.finditer(text):
        count = COUNT_WORDS.get((m.group("count") or "").lower(), 1)
        frac = FRACTIONS[m.group("frac").lower()]
        if m.group("frac").lower() in ("half", "helft") and not m.group("dir"):
            continue  # "half" alone: a multiplier below
        if not m.group("count") and not m.group("dir"):
            continue  # "the third doublet": an ordinal, not an amount
        share = count * frac
        if m.group("dir"):
            up = bool(re.fullmatch(UP, m.group("dir"), _I))
            value = 1 + share if up else 1 - share
            change = "x"
        else:
            value, change = share, "x"
        add(Quantity(round(value, 6), "x", "factor", m.start(), m.end(), m.group(0), change=change))
    for rx, f in MULTIPLIER_RES:
        for m in rx.finditer(text):
            if free(m.start(), m.end()):
                add(Quantity(f, "x", "factor", m.start(), m.end(), m.group(0), change="x"))
    for start, end, value, alt in _numbers_with_spans(text, decimal_comma):
        if not free(start, end):
            continue
        unit = _unit_after(text, end)
        before = re.search(r"(?:×|\bx)\s*$", text[:start], _I)
        if unit is None and before:  # "×1.5"
            add(
                Quantity(
                    value,
                    "x",
                    "factor",
                    before.start(),
                    end,
                    text[before.start() : end],
                    change="x",
                )
            )
            continue
        if unit is None:
            add(Quantity(value, "", "", start, end, text[start:end], alt=alt))
            continue
        name, dim, f, stop = unit
        lead = start
        if _currency_before(text, start) and dim == "energy_price":
            lead = re.search(r"(?:€|\beur(?:os?)?)\s*$", text[:start], _I).start()
        change = _direction(text, lead, stop)
        if dim == "factor":
            change = "x"
        q = Quantity(value, name, dim, lead, stop, text[lead:stop], f, change, alt)
        add(_preferred(q))
    out.sort(key=lambda q: q.start)
    # "70/40 °C", "2 to 3 km", "6-12 graden": the first number has the second's unit.
    for i, q in enumerate(out[:-1]):
        nxt = out[i + 1]
        between = text[q.end : nxt.start]
        if (
            not q.clear
            and nxt.clear
            and nxt.dimension not in ("factor", "percent")
            and re.fullmatch(r"\s*(?:/|-|–|to|tot|and|en|or|of)\s*", between, _I)
        ):
            out[i] = _preferred(
                Quantity(
                    q.value, nxt.unit, nxt.dimension, q.start, q.end, q.text, nxt.factor, alt=q.alt
                )
            )
        elif (
            not q.clear
            and nxt.dimension == "percent"
            and re.fullmatch(r"\s*(?:-|–|to|tot)\s*", between)
        ):
            out[i] = Quantity(q.value, "%", "percent", q.start, q.end, q.text, change=nxt.change)
    return out


def _keys_of(dimension: str) -> List[str]:
    """Return the catalogue keys whose unit is of a dimension."""
    from gemini_agent.parameters import CATALOGUE

    return [
        k
        for k, p in CATALOGUE.items()
        if p.kind in ("number", "list")
        and not p.card_only
        and KEY_UNITS.get(p.unit, ("",))[0] == dimension
    ]


def _preferred(q: Quantity) -> Quantity:
    """Return the amount with its separator read the way that fits a parameter's range.

    "1.500 m" in an English message is 1.5 m first; no depth or length is 1.5 m, 1500 m is.
    """
    if q.alt is None or q.dimension in ("", "percent", "factor"):
        return q
    from gemini_agent.parameters import CATALOGUE

    def fits(n: float) -> bool:
        x = Quantity(n, q.unit, q.dimension, q.start, q.end, q.text, q.factor, q.change).base()
        for key in _keys_of(q.dimension):
            p = CATALOGUE[key]
            kf = KEY_UNITS[p.unit][1]
            if x and p.low is not None and p.low <= x[0] / kf <= p.high:
                return True
        return False

    if not fits(q.value) and fits(q.alt):
        return Quantity(
            q.alt, q.unit, q.dimension, q.start, q.end, q.text, q.factor, q.change, q.value
        )
    return q


def _close(a: float, b: float, dimension: str = "") -> bool:
    tol = max(1e-6, 0.005 * abs(b))
    if dimension in ("temperature", "temperature_change"):
        tol = max(tol, 0.051)
    return abs(a - b) <= tol


def key_dimension(key: str) -> str:
    """Return the dimension of a catalogue key's unit ("" for a count, a switch or a choice)."""
    from gemini_agent.parameters import CATALOGUE

    p = CATALOGUE.get(key)
    if p is None or p.kind not in ("number", "list"):
        return ""
    return KEY_UNITS.get(p.unit, ("",))[0]


def compatible(q: Quantity, key: str) -> bool:
    """Return True when an amount can be a value of a key: its unit is of the key's dimension.

    A share or a multiplier said as a change ("20 % more", "twice") fits any number; a level
    share ("5 %") fits a fraction or a multiplier.
    """
    dim = key_dimension(key)
    if not dim or not q.clear:
        return False
    if q.dimension == "percent":
        return bool(q.change) or dim in ("fraction", "factor")
    if q.dimension == "factor":
        return True
    if q.dimension == "temperature":
        return dim in ("temperature", "temperature_change")
    return q.dimension == dim


def canonical(q: Quantity, key: str, now: object = None) -> List[float]:
    """Return the values an amount supports for a key, in the key's unit.

    Parameters
    ----------
    q : Quantity
        The amount.
    key : str
        A catalogue key (``parameters.CATALOGUE``).
    now : float, optional
        The key's value now: a change ("10 K lower", "20 % more") is worked out from it.

    Returns
    -------
    list of float
        The values, the reading as written first; empty when the units do not fit.
    """
    from gemini_agent.parameters import CATALOGUE

    if not compatible(q, key):
        return []
    p = CATALOGUE[key]
    dim, kf = KEY_UNITS[p.unit]
    base = float(now) if isinstance(now, (int, float)) and not isinstance(now, bool) else None
    out: List[float] = []
    # The way of a change: up, down, or either when the words leave it open (or for a level,
    # which a reader may take as a change from the value now).
    signs = {"+": (1,), "-": (-1,)}.get(q.change, (1, -1))
    if q.dimension == "percent":
        for n in q.numbers():
            share = n / 100
            if not q.change:
                out.append(share)
                continue
            for s in signs:
                if dim == "factor":
                    out.append(1 + s * share)
                if dim == "fraction":
                    out.append(share)
                if base is not None:
                    out.append(base * (1 + s * share))
                    if dim == "fraction":
                        out.append(base + s * share)  # percentage points
    elif q.dimension == "factor":
        for n in q.numbers():
            if dim in ("factor", "fraction"):
                out.append(n)
            if base is not None:
                out.append(base * n)
    elif dim == "temperature_change":
        for d in q.difference():
            out += [s * d for s in signs]
    elif dim == "temperature":
        out += q.base()  # the level as written (a reader may take a change's number so)
        if base is not None:
            for d in q.difference():
                out += [base + s * d for s in signs]
    else:
        for x in q.base():
            v = x / kf
            out.append(v)
            if p.relative:
                out += [s * v for s in signs]
            if base is not None and q.change:
                out += [base + s * v for s in signs]
    seen: List[float] = []
    for v in out:
        if not any(_close(v, x) for x in seen):
            seen.append(round(v, 9))
    return seen


def supported(
    message: str, key: str, now: object = None, quantities: Optional[Sequence[Quantity]] = None
) -> List[float]:
    """Return every value the message's amounts support for a key, in the key's unit.

    Also the difference of two temperatures for a key in K ("80 °C instead of 87 °C" is -7).
    """
    qs = list(quantities) if quantities is not None else extract(message)
    out: List[float] = []
    for q in qs:
        out += canonical(q, key, now)
    if key_dimension(key) == "temperature_change":
        temps = [q for q in qs if q.dimension == "temperature" and not q.change]
        for a in temps:
            for b in temps:
                if a is not b:
                    out += [x - y for x in a.base() for y in b.base()]
    seen: List[float] = []
    for v in out:
        if not any(_close(v, x) for x in seen):
            seen.append(v)
    return seen


def matches(value: object, candidates: Iterable[float], key: str = "") -> bool:
    """Return True when a reading's value is one of the candidates (rounding allowed)."""
    try:
        x = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    dim = key_dimension(key) if key else ""
    return any(_close(x, c, dim) for c in candidates)


def in_range(q: Quantity, now: Dict[str, object] = None) -> bool:
    """Return True when an amount gives a value inside some key's range (a usable amount)."""
    from gemini_agent.parameters import CATALOGUE

    now = now or {}
    for key, p in CATALOGUE.items():
        if p.card_only or p.low is None or not compatible(q, key):
            continue
        if any(p.low <= v <= p.high for v in canonical(q, key, now.get(key))):
            return True
    return False


def _g(x: float) -> str:
    return f"{x:.4g}" if abs(x) < 1e5 else f"{x:.0f}"


def shown(q: Quantity) -> str:
    """Return what an amount means in the catalogue's units ("45 EUR/MWh", "x1.2", "288 m3/h")."""
    if q.dimension == "factor":
        return f"x{_g(q.value)}"
    if q.dimension == "percent":
        way = {"+": " more", "-": " less", "?": " (a change)"}.get(q.change, "")
        if q.change in ("+", "-"):
            s = 1 if q.change == "+" else -1
            return f"{_g(q.value)} %{way} (x{_g(1 + s * q.value / 100)})"
        return f"{_g(q.value)} % ({_g(q.value / 100)} as a fraction){way}"
    if not q.dimension:
        return _g(q.value)
    if q.dimension == "temperature":
        levels = q.base()
        if q.change or not levels:  # a change, or a difference in K ("cooled by 35 K")
            way = {"+": " up", "-": " down"}.get(q.change, "")
            return " or ".join(f"{_g(d)} K{way}" for d in q.difference())
        return " or ".join(f"{_g(x)} °C" for x in levels)
    parts = []
    for x in q.base():
        for unit in SHOWN_IN.get(q.dimension, ()):
            parts.append(f"{_g(x / KEY_UNITS[unit][1])} {unit}")
    way = {"+": " (up)", "-": " (down)", "?": " (a change)"}.get(q.change, "")
    return " or ".join(parts) + way


def candidates(message: str, now: Dict[str, object] = None) -> List[Quantity]:
    """Return the message's amounts a reading could use: with a unit, a share or a multiplier."""
    return [q for q in extract(message) if q.clear and in_range(q, now)]
