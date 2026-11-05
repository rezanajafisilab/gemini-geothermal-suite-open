"""The operator's report: one design of a conversation on paper, for a plant's shift lead.

``build(session, design_id)`` returns an A4 PDF (portrait, about six pages) of one design:

1. what it is, what the search picked it for, its headline figures, its units and sizes and
   the challenge's caps;
2. how it runs over the year: heat and cold by source day by day, month by month, each
   doublet's days on, flow, starts and planned stop, and the year's CO2 by unit;
3. its firm capacity: the spare on the peak days and every one-unit-out case (N-1 or not);
4. the failure what-ifs the chat ran on it, the planned service windows and stops;
5. the limits to watch (flow, brine cooling, operating days, the ESP setting, the injection
   pressure, the cold front) and every verifier check;
6. the assumptions and sources.

Every number is read from the design's ledger entry and the views the tabs use
(``workbench.economics_view``, ``workbench.plant_view``, ``reporter.firm_view``,
``session.failures``); nothing is recomputed here. Only matplotlib draws it: ``Figure`` objects
saved with ``PdfPages``, never pyplot, so no GUI backend is touched (safe in the server's
threads) and the judges' pip install needs nothing more.
"""

from __future__ import annotations

import io
import math
import re
from datetime import date, datetime
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple, Union

import matplotlib
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.textpath import TextToPath

from dioscuri_plant import components as dp_components
from dioscuri_plant.subsurface import ESP_MAX_SETTING_M, SODM_BAR_PER_M
from gemini_agent import answer, engine, reliability, reporter, workbench
from gemini_agent.contract import LedgerEntry

# ------------------------------------------------------------------ page and colours

PAGE_W, PAGE_H = 8.27, 11.69  # A4 portrait, inches
LEFT = RIGHT = 0.62
TOP = 0.8  # the first line, under the page band
BOTTOM = 0.8  # the last line, above the footer
WIDTH = PAGE_W - LEFT - RIGHT
LEADING = 1.36  # line height over font size
FONT = "DejaVu Sans"  # shipped with matplotlib: the same on every laptop
RC = {"pdf.fonttype": 42, "font.family": FONT, "hatch.linewidth": 0.6, "axes.unicode_minus": True}

# The app's colours (frontend/src/tabs/energy/model.ts): every chart reads as the tabs do.
TEAL = "#0a6f7c"
HEAT = "#c24e1c"
HP = "#e3a33b"
BOILER = "#7856c4"
COLD = "#2363a6"
CHILL = "#139fbf"
INK = "#11181c"
MUTED = "#55626b"
LINE = "#d3dcdc"
SHADE = "#f1f5f5"
SHORT = "#b42318"
STOP = "#e4eaea"
TINT = {TEAL: "#e6f1f2", SHORT: "#fbeceb"}
SOURCES = {
    "geo": ("Heat exchanger (geothermal)", HEAT),
    "hp": ("Heat pump", HP),
    "boiler": ("Boiler", BOILER),
    "abs": ("Absorption chiller", COLD),
    "chill": ("Electric chillers", CHILL),
}
# The year's CO2 by the unit that lets it out (``YearResult.co2_by_unit_t``), in its order: the
# Energy tab's names and colours (frontend/src/tabs/energy/model.ts, CO2_META).
CO2_UNITS = (
    ("boiler", "Gas boiler", BOILER, "burns the bought gas and the brine's methane"),
    ("electric_boiler", "Electric boiler", "#c8378a", "grid electricity"),
    ("hp", "Heat pump", HP, "grid electricity"),
    ("pumps", "Well pumps", "#8b7967", "grid electricity: the ESPs and injection pumps"),
    ("flare", "Flare", "#9c4a1e", "burns the brine's methane the boiler does not take"),
    ("brine_co2", "Brine's own CO₂", "#5e9c3a", "the brine's CO₂, let out at the gas separator"),
    ("chillers", "Electric chillers", CHILL, "grid electricity"),
    ("towers", "Cooling towers", "#5b7f94", "grid electricity: fans and pumps"),
    ("network", "Network pumps", "#a3adb5", "grid electricity"),
)
MONTHS = reliability.MONTHS
MONTH_DAYS = reliability.MONTH_DAYS
MONTH_START = tuple(sum(MONTH_DAYS[:m]) for m in range(12))
LIFE_YEARS = 30  # the life the verifier's cold-front check holds the wells to
MINUS = "−"
# The prices the report lists (``workbench.assumptions_view``), with labels for those it has none.
PRICE_KEYS = (
    "discount_rate",
    "electricity_eur_per_mwh",
    "gas_eur_per_mwh",
    "carbon_eur_per_t",
    "carbon_long_term_eur_per_t",
)
PRICE_ROWS = {"carbon_long_term_eur_per_t": {"label": "CO₂ price, long term", "unit": "€/t"}}
DISPATCH = {
    "equal": "running doublets share the brine equally",
    "base": "the hottest doublet runs first, up to its cap (base load)",
}
BEST = {True: " (the cheapest that covers every day)", False: " (helps most)"}
AMBER = "#b54708"  # "at the limit": a status, always with its words
MW_ON = 1e-3  # a unit runs on a day when it gives more than this (MW)

Cell = Union[str, Tuple[str, str], Tuple[str, str, bool]]

# ------------------------------------------------------------------ text

_PATHS = TextToPath()


def _esc(text: object) -> str:
    """Return text that matplotlib draws as written (a ``$`` would start mathtext)."""
    return str(text).replace("$", r"\$")


@lru_cache(maxsize=8192)
def _width_in(text: str, size: float, bold: bool = False) -> float:
    """Return the width of a text in inches at a font size (DejaVu Sans)."""
    prop = FontProperties(family=FONT, size=size, weight="bold" if bold else "normal")
    return _PATHS.get_text_width_height_descent(text, prop, ismath=False)[0] / 72.0


def wrap(text: str, width_in: float, size: float = 9.0, bold: bool = False) -> List[str]:
    """Break a text into lines that fit a width.

    Parameters
    ----------
    text : str
        The text; a newline starts a new line.
    width_in : float
        The width, inches.
    size : float
        Font size, points.
    bold : bool
        Bold type (wider).

    Returns
    -------
    list of str
        The lines (a word longer than the width is cut over lines of its own, after a hyphen
        where it can).
    """
    space = _width_in("a b", size, bold) - _width_in("ab", size, bold)
    out: List[str] = []
    for para in str(text).split("\n"):
        line, used = "", 0.0
        for word in para.split():
            w = _width_in(word, size, bold)
            if w > width_in:  # a word wider than the line: cut it, never let it run past
                if line:
                    out.append(line)
                *whole, word = _cut(word, width_in, size, bold)
                out.extend(whole)
                line, used = word, _width_in(word, size, bold)
            elif line and used + space + w > width_in:
                out.append(line)
                line, used = word, w
            else:
                line, used = (f"{line} {word}", used + space + w) if line else (word, w)
        out.append(line)
    return out


def _cut(word: str, width_in: float, size: float, bold: bool) -> List[str]:
    """Return a word too wide for a line in pieces that fit, cut after a hyphen where it can."""
    pieces, piece = [], ""
    for ch in word:
        if piece and _width_in(piece + ch, size, bold) > width_in:
            at = max(piece.rfind(c) for c in "-/·_,")
            rest = piece[at + 1 :] + ch
            if 0 < at < len(piece) - 1 and _width_in(rest, size, bold) <= width_in:
                # after the last hyphen (or slash, dot) in the piece
                pieces.append(piece[: at + 1])
                piece = piece[at + 1 :]
            else:
                pieces.append(piece)
                piece = ""
        piece += ch
    return pieces + [piece]


def fit(
    text: str,
    width_in: float,
    size: float,
    min_size: float,
    bold: bool = False,
    lines: int = 1,
) -> Tuple[float, List[str]]:
    """Return the largest font size at which a text fits a width in a few lines, and the lines.

    One line first, down to 80 % of the size; then two lines (if allowed) from the full size
    down, and so on; at ``min_size`` the text takes as many lines as it needs (never wider).

    Parameters
    ----------
    text : str
        The text.
    width_in : float
        The width, inches.
    size, min_size : float
        The font size wanted and the smallest one, points.
    bold : bool
        Bold type.
    lines : int
        The most lines before the smallest size.

    Returns
    -------
    tuple of (float, list of str)
        The size and the lines.
    """
    sizes = [size - 0.5 * i for i in range(int((size - min_size) / 0.5) + 1)]
    for n in range(1, lines + 1):
        for s in sizes:
            if n < lines and s < 0.8 * size:
                break
            out = wrap(text, width_in, s, bold)
            if len(out) <= n:
                return s, out
    return min_size, wrap(text, width_in, min_size, bold)


def clip(text: str, width_in: float, size: float, bold: bool = False) -> str:
    """Return a one-line text cut to a width with an ellipsis (unchanged when it fits)."""
    if _width_in(text, size, bold) <= width_in:
        return text
    words = text.split()
    while len(words) > 1 and _width_in(" ".join(words) + "…", size, bold) > width_in:
        words.pop()
    out = " ".join(words)
    while out and _width_in(out + "…", size, bold) > width_in:
        out = out[:-1]
    return out.rstrip(" ,;·(") + "…"


def one_line(
    text: str, width_in: float, size: float, min_size: float, bold: bool = False
) -> Tuple[float, str]:
    """Return the size and the text of a one-line slot: shrunk to fit, then cut with an ellipsis."""
    s, lines = fit(text, width_in, size, min_size, bold, lines=1)
    return s, lines[0] if len(lines) == 1 else clip(text, width_in, s, bold)


def num(x: Optional[float], digits: int = 1) -> str:
    """Return a number as the app writes it (``reporter.num``); a dash when there is none."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return reporter.num(x, digits).replace("-", MINUS)


def signed(x: Optional[float], digits: int = 1, unit: str = "") -> str:
    """Return a change with its sign: ``+16.4%``, ``−17.9%``."""
    if x is None:
        return "–"
    sign = "+" if x > 0 else MINUS if x < 0 else ""
    return f"{sign}{reporter.num(abs(x), digits)}{unit}"


def gwh(x: float) -> str:
    """Return energy in GWh: two decimals below 10, one above."""
    return num(x, 2 if abs(x) < 10 else 1)


def units_text(total_mw: float, n: int) -> str:
    """Return a unit's size, as built: ``3 × 10.4 MW (31.2 MW)`` or ``2 MW``."""
    if n and n > 1:
        return f"{n} × {num(total_mw / n)} MW ({num(total_mw)} MW)"
    return f"{num(total_mw)} MW"


def day_span(first: int, last: int) -> str:
    """Return days of 2027 as ``9 Jul – 12 Aug``."""
    return f"{reliability.day_name(int(first))} – {reliability.day_name(int(last))}"


def _count(n: int, noun: str) -> str:
    """Return ``1 treatment train``, ``2 treatment trains``."""
    return f"{n} {noun}{'' if n == 1 else 's'}"


def starts(on: Sequence[object]) -> int:
    """Return how often a unit starts in the year (an off day followed by an on day)."""
    flags = [bool(o) for o in on]
    return sum(1 for i, o in enumerate(flags) if o and (i == 0 or not flags[i - 1]))


# ------------------------------------------------------------------ layout


class _Doc:
    """A flowing A4 layout: blocks go down the page; a full page starts the next one.

    Positions are inches from the page's top-left corner.
    """

    def __init__(self, title: str, stamp: str):
        """Start an empty document; ``title`` and ``stamp`` go on every footer."""
        self.title = title
        self.stamp = stamp
        self.figs: List[Figure] = []
        self.fig: Optional[Figure] = None
        self.y = TOP
        self.section = ""
        self.pending = ""  # a heading the next table draws
        self.kind = "Plant operator's report"  # what the page band calls the document
        self.metadata: Dict[str, object] = {}  # the PDF's (``layout``)

    @staticmethod
    def fx(x: float) -> float:
        """Return a page position (inches from the left) as a figure fraction."""
        return x / PAGE_W

    @staticmethod
    def fy(y: float) -> float:
        """Return a page position (inches from the top) as a figure fraction."""
        return 1.0 - y / PAGE_H

    @property
    def room(self) -> float:
        """Return the height left on the page, inches."""
        return PAGE_H - BOTTOM - self.y

    # -- primitives

    def put(
        self,
        x: float,
        y: float,
        text: str,
        size: float = 9.0,
        color: str = INK,
        bold: bool = False,
        ha: str = "left",
        va: str = "top",
        italic: bool = False,
    ) -> None:
        """Write one line of text."""
        self.fig.text(
            self.fx(x),
            self.fy(y),
            _esc(text),
            fontsize=size,
            color=color,
            fontweight="bold" if bold else "normal",
            fontstyle="italic" if italic else "normal",
            ha=ha,
            va=va,
        )

    def rect(self, x: float, y: float, w: float, h: float, color: str) -> None:
        """Fill a rectangle (top-left corner at ``x``, ``y``)."""
        self.fig.add_artist(
            Rectangle(
                (self.fx(x), self.fy(y + h)),
                w / PAGE_W,
                h / PAGE_H,
                transform=self.fig.transFigure,
                facecolor=color,
                edgecolor="none",
                zorder=0,
            )
        )

    def rule(self, y: float, color: str = LINE, lw: float = 0.6, x0: float = LEFT) -> None:
        """Draw a horizontal rule across the text width."""
        self.fig.add_artist(
            Line2D(
                [self.fx(x0), self.fx(PAGE_W - RIGHT)],
                [self.fy(y), self.fy(y)],
                transform=self.fig.transFigure,
                color=color,
                linewidth=lw,
            )
        )

    # -- pages

    def new_page(self, section: Optional[str] = None, band: bool = True) -> None:
        """Start a page; its band names the section (``continued`` on a follow-on page)."""
        follow = section is None
        self.section = section or self.section
        self.fig = Figure(figsize=(PAGE_W, PAGE_H))
        self.figs.append(self.fig)
        self.y = TOP
        if band:
            self.put(LEFT, 0.42, "dioscuri", 10, TEAL, bold=True, va="baseline")
            at = LEFT + _width_in("dioscuri", 10, True) + 0.1
            self.put(at, 0.42, self.kind, 8.5, MUTED, va="baseline")
            label = self.section + (" (continued)" if follow else "")
            room = PAGE_W - RIGHT - (at + _width_in(self.kind, 8.5) + 0.3)
            size, label = one_line(label, room, 8.5, 7)
            self.put(PAGE_W - RIGHT, 0.42, label, size, MUTED, ha="right", va="baseline")
            self.rule(0.52, TEAL, 1.0)

    def ensure(self, h: float) -> bool:
        """Start a new page unless ``h`` inches are left; return True when one was started."""
        if self.fig is None or self.room < h:
            self.new_page()
            return True
        return False

    def footers(self) -> None:
        """Put the footers on: the design at the left, the date in the middle, page n of N.

        A design's name too long for the left third (a what-if's, a long pick's) moves the date
        to the right beside the page number and takes the rest of the line, shrunk to 6.5 pt
        and over two lines at most; it never runs into the date.
        """
        n = len(self.figs)
        base = PAGE_H - 0.42
        mid = _width_in(self.stamp, 8) / 2
        fits = LEFT + _width_in(self.title, 8, True) + 0.2 <= PAGE_W / 2 - mid
        right = f"Page {n} of {n}" if fits else f"{self.stamp}   ·   Page {n} of {n}"
        room = WIDTH - _width_in(right, 8) - 0.3
        size, lines = (8.0, [self.title]) if fits else fit(self.title, room, 8, 6.5, True, 2)
        if len(lines) > 2:
            lines = [lines[0], clip(" ".join(lines[1:]), room, size, True)]
        lh = size * 1.2 / 72
        for i, fig in enumerate(self.figs, 1):
            self.fig = fig
            self.rule(PAGE_H - 0.6, LINE, 0.6)
            top = base - (len(lines) - 1) * lh / 2
            for j, line in enumerate(lines):
                self.put(LEFT, top + j * lh, line, size, INK, bold=True, va="baseline")
            page = f"Page {i} of {n}"
            if fits:
                self.put(PAGE_W / 2, base, self.stamp, 8, MUTED, ha="center", va="baseline")
            else:
                page = f"{self.stamp}   ·   {page}"
            self.put(PAGE_W - RIGHT, base, page, 8, MUTED, ha="right", va="baseline")

    def save(self, metadata: Dict[str, object]) -> bytes:
        """Return the PDF's bytes (the footers already on)."""
        buf = io.BytesIO()
        with PdfPages(buf, metadata=metadata) as pdf:
            for fig in self.figs:
                pdf.savefig(fig)
        return buf.getvalue()

    def finish(self, metadata: Dict[str, object]) -> bytes:
        """Put the footers on and return the PDF's bytes."""
        self.footers()
        return self.save(metadata)

    # -- blocks

    def section_head(self, number: int, title: str, lead: str = "", need: float = 3.2) -> None:
        """Start a section: on a new page unless ``need`` inches are left on this one."""
        if self.fig is None or self.room < need:
            self.new_page(title)
        else:
            self.y += 0.22
            self.rule(self.y, TEAL, 1.0)
            self.y += 0.14
            self.section = title
        size, lines = fit(f"{number}   {title}", WIDTH, 15, 11, bold=True, lines=2)
        for j, line in enumerate(lines):
            self.put(LEFT, self.y + j * size * 1.25 / 72, line, size, TEAL, bold=True)
        self.y += 0.36 + (len(lines) - 1) * size * 1.25 / 72
        if lead:
            self.para(lead, 9, MUTED)
        self.y += 0.04

    def heading(self, text: str, need: float = 0.9, table: bool = False) -> None:
        """Write a block's heading, kept with ``need`` inches of what follows.

        ``table``: the heading of the next table, drawn by it (kept with it on one page).
        """
        if table:
            self.pending = text
            return
        self.ensure(need)
        self.y += 0.08
        for j, line in enumerate(wrap(text, WIDTH, 10.5, bold=True)):
            self.y += 10.5 * LEADING / 72 if j else 0.0
            self.put(LEFT, self.y, line, 10.5, INK, bold=True)
        self.y += 0.25

    def para(
        self,
        text: str,
        size: float = 9.0,
        color: str = INK,
        bold: bool = False,
        indent: float = 0.0,
        after: float = 0.07,
        italic: bool = False,
    ) -> None:
        """Write a paragraph, wrapped to the text width."""
        lh = size * LEADING / 72
        for line in wrap(text, WIDTH - indent, size, bold):
            self.ensure(lh)
            self.put(LEFT + indent, self.y, line, size, color, bold, italic=italic)
            self.y += lh
        self.y += after

    def bullets(self, items: Sequence[str], size: float = 9.0, color: str = INK) -> None:
        """Write a list, each item with a bullet and a hanging indent."""
        lh = size * LEADING / 72
        for item in items:
            lines = wrap(item, WIDTH - 0.2, size)
            self.ensure(lh * min(2, len(lines)))
            self.put(LEFT + 0.04, self.y, "•", size, TEAL, bold=True)
            for line in lines:
                self.ensure(lh)
                self.put(LEFT + 0.2, self.y, line, size, color)
                self.y += lh
            self.y += 0.03
        self.y += 0.05

    def table(
        self,
        cols: Sequence[Tuple[str, float, str]],
        rows: Sequence[Sequence[Cell]],
        size: float = 8.0,
        bold_last: bool = False,
        title: str = "",
        keep: Optional[bool] = None,
    ) -> None:
        """Draw a table that may run onto the next page (its header repeated there).

        Parameters
        ----------
        cols : sequence of (str, float, str)
            Each column's header, its relative width and its alignment (left, right, center).
        rows : sequence of sequence of Cell
            The cells: a text, or ``(text, colour)`` or ``(text, colour, bold)``.
        size : float
            Font size, points (at least 8).
        bold_last : bool
            The last row is a total (bold, over a rule).
        title : str
            A heading kept with the table.
        keep : bool, optional
            Keep the table on one page when it fits on one; by default when it has at most 16
            rows.
        """
        total = sum(c[1] for c in cols)
        widths = [c[1] / total * WIDTH for c in cols]
        pad_x, pad_y = 0.05, 0.035
        # Each column at least as wide as its longest word (header or cell): the others give.
        need = []
        for k, (head, _, _) in enumerate(cols):
            words = head.split() + [
                w
                for row in rows
                for w in str(row[k][0] if isinstance(row[k], tuple) else row[k]).split()
            ]
            longest = max((_width_in(w, size, True) for w in words), default=0.0)
            need.append(min(longest + 2 * pad_x + 0.02, 0.45 * WIDTH))
        for _ in range(4):
            low = [k for k, w in enumerate(widths) if w < need[k] - 1e-9]
            if not low:
                break
            for k in low:
                widths[k] = need[k]
            spare = {k: widths[k] - need[k] for k in range(len(widths)) if widths[k] > need[k]}
            excess, room = sum(widths) - WIDTH, sum(spare.values())
            if room <= 0:
                break
            for k, extra in spare.items():
                widths[k] -= excess * extra / room
        lh = size * LEADING / 72

        def cells(row, bold):
            out = []
            for cell, w in zip(row, widths):
                if isinstance(cell, tuple):
                    text, color = cell[0], cell[1]
                    strong = bold or (len(cell) > 2 and bool(cell[2]))
                else:
                    text, color, strong = cell, INK, bold
                out.append((wrap(str(text), w - 2 * pad_x, size, strong), color, strong))
            return out

        def height(laid):
            return max(len(c[0]) for c in laid) * lh + 2 * pad_y

        head = cells([c[0] for c in cols], True)
        body = [cells(row, bold_last and i == len(rows) - 1) for i, row in enumerate(rows)]

        def draw(laid, header=False, shade=False, bold=False):
            h = height(laid)
            if not header and self.ensure(h):
                draw(head, header=True)
            if shade:
                self.rect(LEFT, self.y, WIDTH, h, SHADE)
            if bold:
                self.rule(self.y, MUTED, 0.6)
            x = LEFT
            for (lines, color, strong), w, (_, _, align) in zip(laid, widths, cols):
                tx = {"left": x + pad_x, "right": x + w - pad_x}.get(align, x + w / 2)
                for j, line in enumerate(lines):
                    color = MUTED if header else color
                    self.put(tx, self.y + pad_y + j * lh, line, size, color, strong, ha=align)
                x += w
            self.y += h
            if header:
                self.rule(self.y, TEAL, 0.8)

        title, self.pending = title or self.pending, ""
        title_h = 0.33 if title else 0.0
        first = height(head) + (height(body[0]) if body else 0.0) + title_h
        whole = height(head) + sum(height(b) for b in body) + title_h + 0.12
        keep = len(rows) <= 16 if keep is None else keep
        if keep and whole <= PAGE_H - TOP - BOTTOM:
            self.ensure(whole)
        else:
            self.ensure(first + lh)
        if title:
            self.heading(title, need=0.0)
        draw(head, header=True)
        for i, laid in enumerate(body):
            last = bold_last and i == len(rows) - 1
            draw(laid, shade=i % 2 == 1 and not last, bold=last)
        self.rule(self.y, LINE, 0.6)
        self.y += 0.12

    def tiles(
        self, items: Sequence[Tuple[str, str, str, str, str]], cols: int = 4, h: float = 1.0
    ) -> None:
        """Draw headline figures: ``(label, value, unit, note, colour)`` in a grid."""
        gap = 0.12
        w = (WIDTH - gap * (cols - 1)) / cols
        for start in range(0, len(items), cols):
            self.ensure(h)
            for k, (label, value, unit, note, color) in enumerate(items[start : start + cols]):
                x = LEFT + k * (w + gap)
                self.rect(x, self.y, w, h, SHADE)
                self.rect(x, self.y, 0.05, h, color)
                self.put(x + 0.15, self.y + 0.1, label, 8, MUTED, bold=True)
                self.put(x + 0.15, self.y + 0.52, value, 17, INK, bold=True, va="baseline")
                vw = _width_in(value, 17, True)
                self.put(x + 0.2 + vw, self.y + 0.52, unit, 8.5, MUTED, va="baseline")
                for j, line in enumerate(wrap(note, w - 0.22, 8)[:3]):
                    self.put(x + 0.15, self.y + 0.6 + j * 0.135, line, 8, MUTED)
            self.y += h + gap

    def callout(self, title: str, text: str, color: str) -> None:
        """Draw a statement in a tinted box: the title says it in words, not in colour alone."""
        lh = 9.5 * LEADING / 72
        lines = wrap(text, WIDTH - 0.4, 9.5)
        h = 0.16 + 0.3 + len(lines) * lh + 0.1
        self.ensure(h)
        self.rect(LEFT, self.y, WIDTH, h, TINT.get(color, SHADE))
        self.rect(LEFT, self.y, 0.07, h, color)
        self.put(LEFT + 0.22, self.y + 0.14, title, 12.5, color, bold=True)
        for j, line in enumerate(lines):
            self.put(LEFT + 0.22, self.y + 0.46 + j * lh, line, 9.5, INK)
        self.y += h + 0.14

    def axes(self, h: float, top: float = 0.34, bottom: float = 0.3, left: float = 0.6):
        """Return chart axes ``h`` inches tall at the cursor (room for a legend and labels)."""
        self.ensure(h)
        ax = self.fig.add_axes(
            (
                self.fx(LEFT + left),
                self.fy(self.y + h - bottom),
                (WIDTH - left - 0.05) / PAGE_W,
                (h - top - bottom) / PAGE_H,
            )
        )
        self.y += h
        return ax


# ------------------------------------------------------------------ which design


def target(session, design_id: Optional[str] = None) -> LedgerEntry:
    """Return the design to report on: the one with this id, or the conversation's chosen one.

    Raises
    ------
    KeyError
        No design with this id, or no design chosen yet.
    """
    if design_id:
        return workbench.find(session, design_id)
    if session.chosen is None:
        raise KeyError("no design yet")
    return session.chosen


def filename(entry: LedgerEntry) -> str:
    """Return the report's file name, ``dioscuri-1D-HP-EC-N1.pdf``."""
    code = re.sub(r"[^A-Za-z0-9_.-]+", "-", entry.alternative.code).strip("-.") or "design"
    return f"dioscuri-{code}.pdf"


def _with_days(entry: LedgerEntry, session) -> LedgerEntry:
    """Return the entry with its daily series (a saved candidate keeps only its year's sums).

    A design saved before its year had the CO2 by unit is run again for it too.
    """
    y = entry.year
    if y.daily_mw is None or (entry.alternative.n_doublets and not y.doublets):
        return engine.reprice(entry, session.assumptions or {})
    if y.co2_t and y.co2_by_unit_t is None:
        return engine.reprice(entry, session.assumptions or {})
    return entry


def co2_parts(y) -> List[Tuple[str, str, str, str, float]]:
    """Return the units that let out CO2, in ``CO2_UNITS`` order: key, name, colour, how, t a year.

    Units of a design saved before the split, or that let out none, are left out.
    """
    split = y.co2_by_unit_t or {}
    return [(k, name, color, how, split[k]) for k, name, color, how in CO2_UNITS if split.get(k)]


def share_text(f: float) -> str:
    """Return a share as the report writes it: ``61.3%``, ``<0.1%`` for a sliver, ``0%``."""
    return "<0.1%" if 0 < f < 0.0005 else reporter.pct(f)


def _ink_on(color: str) -> str:
    """Return white or the ink, whichever reads better on a fill (WCAG contrast)."""

    def lum(c: str) -> float:
        rgb = [int(c.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    fill = lum(color)
    return "white" if 1.05 / (fill + 0.05) >= (fill + 0.05) / (lum(INK) + 0.05) else INK


def _series(part: dict, key: str, n: int) -> np.ndarray:
    values = part.get(key)
    if values is None:
        return np.zeros(n)
    return np.asarray(values, dtype=float)[:n]


def _origin_words(session, entry: LedgerEntry) -> str:
    """Say what the search picked a design for, or where it comes from."""
    alt = entry.alternative
    picks = [p for p in alt.picks if p in engine.OBJECTIVE_WORDS]
    if picks:
        return "Picked by the search as " + "; and as ".join(
            engine.OBJECTIVE_WORDS[p] for p in picks
        )
    meta = (session.user_designs or {}).get(alt.code)
    if meta:
        return f"Your design, made on the Design tab from {meta.get('parent') or 'a design'}"
    if entry.change_label or entry.brief.reservoir_delta_c:
        change = entry.change_label or f"reservoir {signed(entry.brief.reservoir_delta_c)} °C"
        return f"A what-if of {alt.parent or alt.code.split(' ')[0]}: {change}"
    if alt.role == "chosen":
        return "The design this conversation is about"
    return "A candidate of the search, not one of its picks"


# ------------------------------------------------------------------ the sections


def _cover(doc: _Doc, session, entry: LedgerEntry, ctx: dict) -> None:
    """Page 1: the design, its picks, headline figures, units and sizes, the caps."""
    y, alt, econ = entry.year, entry.alternative, ctx["econ"]
    doc.new_page("Summary", band=False)
    doc.rect(0, 0, PAGE_W, 1.45, TEAL)
    doc.put(LEFT, 0.42, "dioscuri", 24, "white", bold=True)
    doc.put(LEFT, 0.95, "Plant operator's report", 12, "#d6ecee")
    # The right column: what the left one leaves, a long project name shrunk, then cut.
    room = WIDTH - max(_width_in("dioscuri", 24, True), _width_in("Plant operator's report", 12))
    room -= 0.4
    size, name = one_line(session.project.name, room, 10.5, 8, bold=True)
    doc.put(PAGE_W - RIGHT, 0.5, name, size, "white", bold=True, ha="right")
    doc.put(PAGE_W - RIGHT, 0.8, ctx["long_date"], 10, "#d6ecee", ha="right")
    size, said = one_line(f"Conversation {session.thread_id}", room, 8.5, 7)
    doc.put(PAGE_W - RIGHT, 1.06, said, size, "#d6ecee", ha="right")
    doc.y = 1.75
    # The design's id: one line down to 19 pt, else two lines, else smaller (a what-if's or a
    # long pick's name ran past the page at 24 pt, 5 Nov).
    size, lines = fit(ctx["id"], WIDTH, 24, 14, bold=True, lines=2)
    for line in lines:
        doc.put(LEFT, doc.y, line, size, INK, bold=True)
        doc.y += size * 1.25 / 72
    doc.y += 0.08
    doc.para(ctx["name"][0].upper() + ctx["name"][1:] + ".", 11, INK, after=0.08)
    doc.para(_origin_words(session, entry) + ".", 9.5, TEAL, bold=True, after=0.06)
    checks = entry.verification.checks
    passed = sum(c.passed for c in checks)
    status = [f"Checks: {passed} of {len(checks)} passed"]
    if ctx["firm"] is not None:
        status.append("N-1: yes" if not ctx["firm"]["short"] else "N-1: no")
    status.append(
        "Results from GEMINI's well solve and Dioscuri's plant model"
        if alt.n_doublets
        else "Results from Dioscuri's plant model"
    )
    doc.para("   ·   ".join(status), 9, MUTED, after=0.18)

    vs = econ.get("vs_gas_pct") or {}
    versus = econ.get("versus_reference") or {}
    rate = engine.prices_for(session.assumptions, entry.brief).discount_rate
    payback = versus.get("payback_years")
    tiles = [
        (
            "Cost of heat",
            num(econ["lcoh"]),
            "€/MWh",
            f"{signed((vs.get('heat') or 0) * 100)}% against the gas reference",
            HEAT,
        ),
        (
            "Cost of cold",
            num(econ["lcoc"]),
            "€/MWh",
            f"{signed((vs.get('cold') or 0) * 100)}% against the gas reference",
            COLD,
        ),
        (
            "Heat covered",
            reporter.pct(y.heat_coverage),
            "of demand",
            f"{gwh(y.heat_delivered_gwh)} of {gwh(y.heat_demand_gwh)} GWh/yr",
            HEAT,
        ),
        (
            "Cold covered",
            reporter.pct(y.cool_coverage) if y.cool_demand_gwh else "–",
            "of demand",
            f"{gwh(y.cool_delivered_gwh)} of {gwh(y.cool_demand_gwh)} GWh/yr",
            COLD,
        ),
        (
            "CO₂ against gas",
            signed(-econ["co2_saving_pct"]),
            "%",
            f"{num(econ['co2_t_per_year'], 0)} t/yr; the gas reference "
            f"{num(econ['reference_co2_t_per_year'], 0)} t/yr",
            TEAL,
        ),
        (
            "Capital",
            num(econ["capex_meur"]),
            "M€",
            (
                f"{signed(versus.get('extra_capex_meur'))} M€ against the gas reference"
                if versus
                else "the gas reference itself"
            ),
            TEAL,
        ),
        (
            "Cost of heat and cold",
            num(econ["lcoe"]),
            "€/MWh",
            f"{signed((vs.get('total') or 0) * 100)}% against the gas reference",
            TEAL,
        ),
        (
            "Payback",
            num(payback, 0) if payback is not None else "–",
            "years" if payback is not None else "",
            (
                f"discounted at {num(rate * 100)}% real; NPV {num(versus.get('npv_meur'))} M€ "
                f"over {versus.get('years', 30)} years"
                if payback is not None
                else "does not pay back within the life"
            ),
            TEAL,
        ),
    ]
    doc.tiles(tiles, cols=4, h=1.02)

    doc.heading("The plant: units and sizes", table=True)
    pv = ctx["plant"]
    rows: List[List[Cell]] = []
    if alt.n_doublets:
        rows_d = (y.plant or {}).get("doublets") or []
        depths = sorted({float(r.get("depth_m") or alt.depth_m) for r in rows_d} or {alt.depth_m})
        caps_m3h = sorted({float(r.get("cap_m3h") or pv["flow_m3h"]) for r in rows_d})
        cap_text = " / ".join(num(c, 0) for c in caps_m3h) or num(pv["flow_m3h"], 0)
        trains = _count(pv.get("trains") or 1, "treatment train")
        rows.append(
            [
                "Doublets",
                f"{alt.n_doublets} × doublet",
                f"aquifer at {' and '.join(num(d, 0) for d in depths)} m; producer with ESP and "
                f"injector; flow cap {cap_text} m³/h each; {trains}"
                + (
                    f"; {DISPATCH.get(pv['dispatch'], pv['dispatch'])}"
                    if alt.n_doublets > 1
                    else ""
                ),
            ]
        )
        rows.append(
            [
                "Heat exchanger",
                f"{num(alt.sizes_mw.get('heat_exchanger') or y.hex_mw)} MW",
                f"brine in at {num(y.wellhead_c)} °C; heats the network return to "
                f"{num(y.hex_outlet_c)} °C",
            ]
        )
    if y.heat_pump_mw:
        rows.append(
            [
                "Heat pump",
                f"{num(y.heat_pump_mw)} MW",
                f"COP {num(y.heat_pump_cop, 2)} (Carnot {num(y.heat_pump_carnot_cop, 2)}); its "
                "source is the brine after the exchanger",
            ]
        )
    if y.boiler_mw:
        rows.append(
            [
                "Gas boiler",
                units_text(y.boiler_mw, alt.boiler_units),
                "burns the produced gas first, then bought gas; tops up to the supply temperature",
            ]
        )
    if y.absorption_mw:
        rows.append(
            [
                "Absorption chiller",
                f"{num(y.absorption_mw)} MW",
                f"COP {num(y.absorption_cop, 2)}; driven by the brine; rejects to cooling towers",
            ]
        )
    if y.chiller_mw:
        rows.append(
            [
                "Electric chillers",
                units_text(y.chiller_mw, alt.chiller_units),
                f"COP {num(y.chiller_cop, 2)}; reject their heat to cooling towers",
            ]
        )
    rows.append(
        [
            "Heating network",
            f"{num(pv['heating_supply_c'], 0)}/{num(pv['heating_return_c'], 0)} °C",
            "supply and return",
        ]
    )
    rows.append(
        [
            "Cooling network",
            f"{num(pv['cooling_supply_c'], 0)}/{num(pv['cooling_return_c'], 0)} °C",
            "supply and return",
        ]
    )
    doc.table(
        [("Unit", 1.3, "left"), ("Size", 1.85, "left"), ("How it is built and runs", 4.3, "left")],
        rows,
        size=8.5,
    )

    caps, rules = ctx["caps"], ctx["rules"]
    doc.heading("The challenge's caps", need=1.4)
    doc.bullets(
        [
            "One to three doublets; production equals injection (all brine goes back).",
            f"Flow {num(caps.flow_min_m3h, 0)}–{num(caps.flow_max_m3h, 0)} m³/h per doublet "
            "while it runs.",
            f"Brine cooled by at most {num(caps.max_brine_cooling_k, 0)} K from producer to "
            "injector.",
            f"At most {caps.operating_days} operating days per doublet per year.",
            f"Heat delivered at {num(caps.heat_supply_c, 0)} °C and cold at "
            f"{num(caps.cool_supply_c, 0)} °C, every day of the year.",
        ],
        size=9,
    )
    relaxed = [
        f"{label} {num(getattr(rules, key), 0)}{unit}"
        for key, label, unit in (
            ("flow_min_m3h", "minimum flow", " m³/h"),
            ("flow_max_m3h", "flow cap", " m³/h"),
            ("max_brine_cooling_k", "brine cooling", " K"),
            ("operating_days", "operating days", ""),
        )
        if abs(float(getattr(rules, key)) - float(getattr(caps, key))) > 1e-9
    ]
    if relaxed:
        doc.para(
            "This design was run with " + ", ".join(relaxed) + " as asked; the checks on page "
            "5 still hold it to the challenge's caps.",
            9,
            SHORT,
            bold=True,
        )
    connections = next((n for n in ctx["notes"] if n.startswith("Connections:")), "")
    if connections:
        doc.heading("How the units connect", need=0.8)
        said = connections.split(":", 1)[1].strip()
        doc.para(said[:1].upper() + said[1:], 9)


def _day_chart(doc: _Doc, entry: LedgerEntry, side: str, h: float) -> None:
    """Draw one side's daily supply by source, stacked, against the day's demand."""
    y = entry.year
    part = (y.daily_mw or {}).get(side) or {}
    demand = np.asarray(part.get("demand") or [], dtype=float)
    n = demand.size
    keys = [k for k in (("geo", "hp", "boiler") if side == "heat" else ("abs", "chill"))]
    keys = [k for k in keys if np.any(_series(part, k, n) > MW_ON)]
    x = np.arange(n)
    ax = doc.axes(h)
    stack = [_series(part, k, n) for k in keys]
    if stack:
        ax.stackplot(
            x,
            *stack,
            colors=[SOURCES[k][1] for k in keys],
            labels=[SOURCES[k][0] for k in keys],
            linewidth=0.3,
            edgecolor="white",
        )
    ax.plot(x, demand, color=INK, linewidth=0.9, label="Demand")
    short = _series(part, "short", n)
    if np.any(short > MW_ON):
        ax.fill_between(
            x,
            demand - short,
            demand,
            where=short > MW_ON,
            facecolor="none",
            edgecolor=SHORT,
            hatch="////",
            linewidth=0,
            label="Not met",
        )
    from gemini_agent import stops as stop_dates

    for k, ranges in enumerate(stop_dates.ranges_of(y)):  # one band per stop, several a doublet
        for j, (a, b) in enumerate(ranges):
            ax.axvspan(a - 0.5, b + 0.5, color=STOP, zorder=0, linewidth=0)
            if j and b - a < 13:
                continue  # a short extra range: the band says it
            ax.text(
                (a + b) / 2,
                0.97 - 0.09 * k,
                f"doublet {k + 1} stop",
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=8,
                color=MUTED,
            )
    ax.set_xlim(-0.5, n - 0.5)
    top = max(float(demand.max(initial=0.0)), float(sum(stack).max(initial=0.0)) if stack else 0.0)
    ax.set_ylim(0, top * 1.12 or 1.0)
    if n == 365:
        ax.set_xticks(MONTH_START)
        ax.set_xticklabels([])
        ax.set_xticks([s + d / 2 for s, d in zip(MONTH_START, MONTH_DAYS)], minor=True)
        ax.set_xticklabels(MONTHS, minor=True)
        ax.tick_params(axis="x", which="minor", length=0)
    else:
        ax.set_xlabel("day of the year", fontsize=8, color=MUTED)
    ax.set_ylabel("MW (daily mean)", fontsize=8, color=MUTED)
    ax.tick_params(which="both", labelsize=8, colors=MUTED)
    ax.grid(axis="y", color=LINE, linewidth=0.5)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(LINE)
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncol=5,
        frameon=False,
        fontsize=8,
        handlelength=1.4,
        borderaxespad=0.15,
        columnspacing=1.2,
    )


def _year(doc: _Doc, session, entry: LedgerEntry, ctx: dict) -> None:
    """Section 2: the year day by day and month by month; each doublet's days."""
    from gemini_agent import stops as stop_dates

    y, alt = entry.year, entry.alternative
    ranges = stop_dates.ranges_of(y)
    said = stop_dates.summary(y, entry.brief)
    doc.section_head(
        2,
        "How it runs over the year",
        "Daily means from the plant model. Heat is stacked in the order the plant uses its "
        "sources: the heat exchanger first, then the heat pump, then the boiler"
        + (f". Grey bands: the doublets' planned stops ({said})." if said else "."),
    )
    doc.heading("Heat by source against demand, every day (MW)", need=3.3)
    _day_chart(doc, entry, "heat", 2.95)
    if y.cool_demand_gwh:
        doc.heading("Cold by source against demand, every day (MW)", need=2.7)
        _day_chart(doc, entry, "cool", 2.35)

    rows_d = (y.plant or {}).get("doublets") or []
    if alt.n_doublets:
        doc.heading("The doublets over the year", table=True)
        rows = []
        for k, r in enumerate(rows_d):
            flows = np.asarray((y.doublets or [{}])[k].get("flow_m3h") or [], dtype=float)
            running = flows[flows > 0]
            on = (y.doublets or [{}])[k].get("on") or []
            stop = ranges[k] if k < len(ranges) else []
            rows.append(
                [
                    f"Doublet {r.get('doublet', k + 1)}",
                    num(r.get("depth_m"), 0),
                    str(r.get("days_on", int(sum(bool(o) for o in on)))),
                    num(r.get("flow_mean_m3h")),
                    f"{num(running.min())}–{num(running.max())}" if running.size else "–",
                    num(r.get("cap_m3h"), 0),
                    str(starts(on)),
                    (
                        ", ".join(day_span(a, b) for a, b in stop)
                        + f" ({stop_dates.days_off(stop)} days)"
                        if stop
                        else "none"
                    ),
                    num((r.get("esp_gwh") or 0) + (r.get("injection_gwh") or 0), 2),
                ]
            )
        doc.table(
            [
                ("Doublet", 0.9, "left"),
                ("Aquifer depth (m)", 0.85, "right"),
                ("Days on", 0.6, "right"),
                ("Mean flow when on (m³/h)", 1.0, "right"),
                ("Flow range (m³/h)", 0.95, "right"),
                ("Cap (m³/h)", 0.6, "right"),
                ("Starts", 0.55, "right"),
                ("Planned stop", 1.55, "left"),
                ("Pumps (GWh/yr)", 0.75, "right"),
            ],
            rows,
        )

    daily = y.daily_mw or {}
    heat, cool = daily.get("heat") or {}, daily.get("cool") or {}
    n = len(heat.get("demand") or [])
    facts = []
    total_h = y.heat_delivered_gwh or 1.0
    for key, label, size in (
        ("geo", "The heat exchanger", alt.sizes_mw.get("heat_exchanger") or y.hex_mw),
        ("hp", "The heat pump", y.heat_pump_mw),
        ("boiler", "The boiler", y.boiler_mw),
    ):
        s = _series(heat, key, n)
        if not size or not s.size:
            continue
        i = int(np.argmax(s))
        facts.append(
            f"{label} gives {reporter.pct(y.heat_split_gwh.get(key, 0) / total_h)} of the year's "
            f"heat ({gwh(y.heat_split_gwh.get(key, 0))} GWh), runs on {int(np.sum(s > MW_ON))} "
            f"days, at most {num(s[i])} MW on {reliability.day_name(i)} (size {num(size)} MW)."
        )
    total_c = y.cool_delivered_gwh or 1.0
    for key, label, size in (
        ("abs", "The absorption chiller", y.absorption_mw),
        ("chill", "The electric chillers", y.chiller_mw),
    ):
        s = _series(cool, key, n)
        if not size or not s.size:
            continue
        i = int(np.argmax(s))
        facts.append(
            f"{label} give{'s' if key == 'abs' else ''} "
            f"{reporter.pct(y.cool_split_gwh.get(key, 0) / total_c)} of the year's cold "
            f"({gwh(y.cool_split_gwh.get(key, 0))} GWh), run{'s' if key == 'abs' else ''} on "
            f"{int(np.sum(s > MW_ON))} days, at most {num(s[i])} MW on "
            f"{reliability.day_name(i)} (size {num(size)} MW)."
        )
    el = y.electricity_gwh or {}
    facts.append(
        "Electricity bought: "
        + ", ".join(
            f"{label} {gwh(el.get(k, 0))} GWh"
            for k, label in (
                ("hp", "heat pump"),
                ("chillers", "chillers"),
                ("towers", "cooling towers"),
                ("pumps", "well pumps"),
            )
            if el.get(k)
        )
        + f". Gas: {gwh(y.purchased_gas_gwh)} GWh bought, {gwh(y.produced_gas_burned_gwh)} GWh "
        f"of the produced gas burned, {gwh(y.produced_gas_flared_gwh)} GWh flared."
    )
    for side, word in ((heat, "Heat"), (cool, "Cold")):
        s = _series(side, "short", n)
        if np.any(s > MW_ON):
            facts.append(
                f"{word} NOT met on {int(np.sum(s > MW_ON))} days, at most {num(s.max())} MW short."
            )
    doc.heading("What each unit does over the year", need=1.0)
    doc.bullets(facts, size=8.5)

    _co2(doc, entry, ctx)
    _months(doc, entry)


def _co2(doc: _Doc, entry: LedgerEntry, ctx: dict) -> None:
    """Draw the year's CO2 by unit: a bar of the shares, its key, a table of tonnes and shares."""
    y = entry.year
    parts = co2_parts(y)
    total = sum(p[4] for p in parts)
    if not parts or total <= 0:
        return
    rules = ctx["rules"]
    grid = rules.grid_t_co2_per_mwh
    if grid is None:
        grid = dp_components.Components().grid_t_co2_per_mwh
    gas = dp_components.Components().gas_t_co2_per_mwh
    doc.heading("CO₂ by unit over the year", need=2.6)
    doc.para(
        f"{num(total, 0)} t of CO₂ a year, by the unit that lets it out. Gas burnt counts "
        f"{num(gas * 1000, 0)} kg per MWh; grid electricity {num(grid * 1000, 0)} kg per MWh"
        + (" (by month)" if getattr(rules, "grid_by_month", 0.0) else "")
        + " on what each unit draws"
        + (" after the plant's own solar" if (y.solar or {}).get("used_gwh") else "")
        + "; the brine's own CO₂ as it leaves the gas separator.",
        8.5,
        MUTED,
    )
    # The bar: each unit's share of the total, 2 pt gaps between the parts, the share written in
    # each part wide enough for it. A sliver is drawn 3 pt wide (as on the Energy tab), the
    # others share the rest.
    h, gap, least = 0.3, 2 / 72, 3 / 72
    doc.ensure(h + 0.8)
    x = LEFT
    room = WIDTH - gap * (len(parts) - 1)
    thin = [p[4] / total * room < least for p in parts]
    rest = sum(p[4] for p, small in zip(parts, thin) if not small) or total
    wide = room - least * sum(thin)
    for (_, _, color, _, t), small in zip(parts, thin):
        w = least if small else wide * t / rest
        doc.rect(x, doc.y, w, h, color)
        label = f"{num(t / total * 100, 0)}%"
        if _width_in(label, 8, True) + 0.1 <= w:
            doc.put(x + 0.05, doc.y + h / 2, label, 8, _ink_on(color), bold=True, va="center")
        x += w + gap
    doc.y += h + 0.1
    # Its key: a swatch and the name of each part, in the bar's order, over as many lines as needed.
    x, size = LEFT, 8.5
    for _, name, color, _, _ in parts:
        w = 0.14 + _width_in(name, size) + 0.22
        if x + w - 0.22 > PAGE_W - RIGHT:
            x, doc.y = LEFT, doc.y + 0.2
        doc.rect(x, doc.y + 0.02, 0.1, 0.1, color)
        doc.put(x + 0.14, doc.y, name, size, INK)
        x += w
    doc.y += 0.28
    rows: List[List[Cell]] = [
        [name, how, num(t, 0), share_text(t / total)] for _, name, _, how, t in parts
    ]
    rows.append(["All units", "", num(total, 0), "100%"])
    doc.table(
        [
            ("Unit", 1.5, "left"),
            ("Where its CO₂ comes from", 3.6, "left"),
            ("CO₂ (t/yr)", 1.0, "right"),
            ("Share", 0.8, "right"),
        ],
        rows,
        size=8,
        bold_last=True,
    )
    none = [name for k, name, _, _ in CO2_UNITS if not (y.co2_by_unit_t or {}).get(k)]
    if none:
        said = ", ".join(n[0].lower() + n[1:] if n[1:2].islower() else n for n in none)
        doc.para(f"No CO₂ from: {said}.", 8, MUTED)


def _months(doc: _Doc, entry: LedgerEntry) -> None:
    """Month by month: energy by source (GWh) and each doublet's days on."""
    y = entry.year
    m = y.monthly_gwh or {}
    heat, cool = m.get("heat") or {}, m.get("cool") or {}
    if not heat.get("demand"):
        return
    has_abs = bool(y.absorption_mw)
    has_cool = bool(y.cool_demand_gwh)
    doublets = y.doublets or []
    cols = [("Month", 0.55, "left"), ("Heat demand (GWh)", 0.8, "right")]
    cols += [
        ("Exchanger (GWh)", 0.8, "right"),
        ("Heat pump (GWh)", 0.8, "right"),
        ("Boiler (GWh)", 0.75, "right"),
        ("Heat not met (GWh)", 0.75, "right"),
    ]
    if has_cool:
        cols.append(("Cold demand (GWh)", 0.8, "right"))
        if has_abs:
            cols.append(("Absorption (GWh)", 0.8, "right"))
        cols += [("Chillers (GWh)", 0.75, "right"), ("Cold not met (GWh)", 0.75, "right")]
    if doublets:
        label = "Days on" + (
            f" (doublet {' / '.join(str(k + 1) for k in range(len(doublets)))})"
            if len(doublets) > 1
            else ""
        )
        cols.append((label, 0.85, "right"))

    def at(part, key, i):
        values = part.get(key) or [0.0] * 12
        return float(values[i]) if i < len(values) else 0.0

    def row_of(values_h, values_c, days, bold=False):
        short_h = values_h[4]
        row: List[Cell] = [gwh(v) for v in values_h[:4]]
        row.append((gwh(short_h), SHORT, True) if short_h > 1e-3 else "0")
        if has_cool:
            row.append(gwh(values_c[0]))
            if has_abs:
                row.append(gwh(values_c[1]))
            row.append(gwh(values_c[2]))
            row.append((gwh(values_c[3]), SHORT, True) if values_c[3] > 1e-3 else "0")
        if doublets:
            row.append(" / ".join(str(d) for d in days))
        return row

    rows = []
    sums_h, sums_c, sums_d = np.zeros(5), np.zeros(4), np.zeros(len(doublets), dtype=int)
    for i in range(12):
        vh = [at(heat, k, i) for k in ("demand", "geo", "hp", "boiler", "short")]
        vc = [at(cool, k, i) for k in ("demand", "abs", "chill", "short")]
        days = [
            int(
                sum(
                    bool(o)
                    for o in (d.get("on") or [])[MONTH_START[i] : MONTH_START[i] + MONTH_DAYS[i]]
                )
            )
            for d in doublets
        ]
        sums_h += vh
        sums_c += vc
        sums_d += np.asarray(days, dtype=int) if doublets else 0
        rows.append([MONTHS[i]] + row_of(vh, vc, days))
    rows.append(["Year"] + row_of(list(sums_h), list(sums_c), [int(d) for d in sums_d]))
    doc.heading("Month by month", table=True)
    doc.table(cols, rows, size=8, bold_last=True)


def _boiler_words(entry: LedgerEntry) -> str:
    """Say what share of the heat the boiler gives, on how many days, and what it is for."""
    y, alt = entry.year, entry.alternative
    if not y.boiler_mw:
        return ""
    heat = (y.daily_mw or {}).get("heat") or {}
    fired = _series(heat, "boiler", len(heat.get("demand") or []))
    share = reporter.pct(y.heat_split_gwh.get("boiler", 0) / (y.heat_delivered_gwh or 1))
    role = (
        "it is the peak boiler and the cover for a lost unit at once."
        if alt.reliable
        else "it is the peak boiler, sized for the peak day with the doublets running, not a "
        "standby."
    )
    return (
        f" The boiler gives {share} of the year's heat and fires on "
        f"{int(np.sum(fired > MW_ON))} days: {role}"
    )


def _doublet_on(y, k: int, i: int) -> str:
    """Say what doublet ``k`` does on day ``i``: its flow, its planned stop, or idle."""
    flows = (y.doublets or [])[k].get("flow_m3h") or []
    flow = float(flows[i]) if i < len(flows) else 0.0
    if flow > 0:
        return f"doublet {k + 1} {num(flow, 0)} m³/h"
    from gemini_agent import stops as stop_dates

    if stop_dates.stopped(stop_dates.ranges_of(y), k, i):
        return f"doublet {k + 1} in its planned stop"
    return f"doublet {k + 1} idle (not needed)"


def _firm(doc: _Doc, entry: LedgerEntry, ctx: dict) -> None:
    """Section 3: the spare on the peak days and every one-unit-out case; N-1 or not."""
    y, alt = entry.year, entry.alternative
    fv = ctx["firm"]
    doc.section_head(
        3,
        "Firm capacity",
        "What the plant can still give when a unit is lost. Each case runs the whole year with "
        "that one unit out; trips, start-ups and hourly peaks are not modelled (daily means), so "
        "a trip of a few days is short only on the days it overlaps the days listed.",
        need=4.0,
    )
    if fv is None:
        doc.para(
            "This design has no doublets (the gas reference): firm capacity is not assessed.", 9.5
        )
        return
    cases = fv["cases"]
    short = [c for c in cases if c["short"]]
    built = []
    if alt.reliable:
        if y.boiler_mw:
            built.append(f"the boiler as {units_text(y.boiler_mw, alt.boiler_units)}")
        if y.chiller_mw:
            built.append(f"the electric chillers as {units_text(y.chiller_mw, alt.chiller_units)}")
    if not short:
        text = (
            f"With any one of its {len(cases)} units out, all year, every day's heat and cold is "
            "still met."
        )
        if built:
            text += " It was sized for this: " + " and ".join(built) + "."
        doc.callout("This plan is N-1", text + _boiler_words(entry), TEAL)
    else:
        worst = max(short, key=lambda c: c["worst_mw"])
        side = "heat" if worst["side"] == "heat" else "cold"
        text = (
            f"{len(short)} of the {len(cases)} one-unit-out cases leave demand unmet. The worst: "
            f"{worst['unit']} out leaves {side} {num(worst['worst_mw'])} MW short on "
            f"{worst['worst_day']} ({worst['days_short']} days short, "
            f"{gwh(worst['short_gwh'])} GWh not delivered). A spare or backup is needed to keep "
            "everyone supplied when that unit is lost."
        )
        doc.callout("This plan is NOT N-1", text + _boiler_words(entry), SHORT)

    peak = fv.get("peak") or {}
    tiles = []
    for side, word, color in (("heat", "heat", HEAT), ("cool", "cold", COLD)):
        p = peak.get(side)
        if not p:
            continue
        tiles.append(
            (
                f"Spare on the peak {word} day, {p['day']}",
                num(p["spare_mw"]),
                "MW",
                f"demand {num(p['demand_mw'])} MW; the plant can give {num(p['capacity_mw'])} MW",
                color,
            )
        )
    if tiles:
        doc.tiles(tiles, cols=2, h=0.92)
    daily = y.daily_mw or {}
    lines = []
    for side, word, keys in (
        ("heat", "heat", ("geo", "hp", "boiler")),
        ("cool", "cold", ("abs", "chill")),
    ):
        part = daily.get(side) or {}
        demand = np.asarray(part.get("demand") or [], dtype=float)
        if not demand.size or not demand.any():
            continue
        i = int(np.argmax(demand))
        given = [
            f"{SOURCES[k][0].split(' (')[0].lower()} {num(_series(part, k, demand.size)[i], 2)}"
            for k in keys
            if np.any(_series(part, k, demand.size) > MW_ON)
        ]
        flows = [_doublet_on(y, k, i) for k in range(len(y.doublets or []))]
        lines.append(
            f"Peak {word} day, {reliability.day_name(i)}: demand {num(demand[i], 2)} MW = "
            + " + ".join(given)
            + " MW"
            + ("; " + ", ".join(flows) if flows else "")
            + "."
        )
    doc.bullets(lines, size=8.5)

    doc.heading("One unit out (N-1), all year", table=True)
    rows = []
    for c in cases:
        unit = c["unit"][0].upper() + c["unit"][1:]
        if c["unit"].startswith("doublet"):
            unit += " (producer, ESP or injector)"
        side = "heat" if c["side"] == "heat" else "cold"
        rows.append(
            [
                unit,
                ("SHORT", SHORT, True) if c["short"] else ("met every day", TEAL),
                side if c["short"] else "–",
                c["worst_day"] or "–",
                num(c["worst_mw"]) if c["short"] else "0",
                str(c["days_short"]),
                gwh(c["short_gwh"]) if c["short"] else "0",
            ]
        )
    doc.table(
        [
            ("Unit out", 2.3, "left"),
            ("Result", 1.0, "left"),
            ("Side", 0.5, "left"),
            ("Worst day", 0.75, "left"),
            ("Short on the worst day (MW)", 1.0, "right"),
            ("Days short", 0.7, "right"),
            ("Not delivered (GWh)", 0.9, "right"),
        ],
        rows,
    )


def _failure_outcome(f: dict) -> str:
    """Say in words what a failure what-if did not deliver, and what it cost."""
    failed = f.get("failed") or {}
    said = []
    for side, word in (("heat", "Heat"), ("cool", "Cold")):
        x = failed.get(side) or {}
        if x.get("days_short"):
            said.append(
                f"{word} NOT met on {x['days_short']} days: worst {x['worst_day']}, "
                f"{num(x['worst_mw'])} MW short; {gwh(x['short_gwh'])} GWh not delivered."
            )
    if not said:
        said.append("Heat and cold are still met every day: the other units cover it.")
    if failed.get("boiler_full"):
        said.append("The boiler is already at full output on those days.")
    if (failed.get("extra_gas_gwh") or 0) > 0.001:
        said.append(
            f"It burns {gwh(failed['extra_gas_gwh'])} GWh more gas, "
            f"{num(failed.get('extra_co2_t'), 0)} t more CO₂; running costs "
            f"{signed(failed.get('extra_cost_keur'), 0)} k€ for the year."
        )
    elif (failed.get("extra_cost_keur") or 0) < 0:
        said.append(
            f"Running costs fall by {num(-failed['extra_cost_keur'], 0)} k€ only because that "
            "heat or cold is not delivered (energy not delivered is not priced)."
        )
    if f.get("needed") and not f.get("remedies"):
        said.append(
            "None of the remedies the model tries applies here (a standby twin of a single boiler "
            "or chiller set, more boiler or chillers, a spare ESP)."
        )
    esp = f.get("spare_esp")
    if esp and esp.get("gas_saved_gwh", 0) > 0.001:
        said.append(
            f"{esp['name'][0].upper()}{esp['name'][1:]} would save {gwh(esp['gas_saved_gwh'])} GWh "
            f"of that gas ({num(esp['money_saved_keur'], 0)} k€ of running costs) for about "
            f"{num(esp['yearly_keur'], 0)} k€ a year of capital tied up "
            f"({num(esp['capex_meur'], 2)} M€)."
        )
    return " ".join(said)


def _short_cell(mw: float) -> Cell:
    """Return MW not delivered as a cell: red and bold when there is any."""
    return (num(mw, 2), SHORT, True) if mw > MW_ON else num(mw, 2)


def _planned(event: dict) -> bool:
    """Return True for a planned service window (the mildest days were taken for it)."""
    return str(event.get("how", "")).startswith("the mildest")


def _failures(doc: _Doc, session, entry: LedgerEntry, ctx: dict) -> None:
    """Section 4: every failure what-if the chat ran on this design; service windows; stops."""
    y = entry.year
    mine = ctx["failures"]
    others = len(session.failures or []) - len(mine)
    doc.section_head(
        4,
        "Failures and maintenance",
        "The failure what-ifs asked in the chat about this design, each run day by day with the "
        "unit out, and with each remedy that could help; then the planned service windows and "
        "the doublets' planned stops.",
    )
    if not mine:
        doc.para(
            "No failure what-if has been run on this design yet. Ask the chat, for example "
            "“What if the ESP of doublet 1 fails from 10 to 24 January?” or “When is the best "
            "time for two weeks of heat pump maintenance?”, and the answer appears here."
            + (f" ({others} what-if(s) were run on other designs.)" if others > 0 else ""),
            9,
        )
    for i, f in enumerate(mine, 1):
        events = f.get("events") or []
        kind = "Planned work" if events and all(_planned(e) for e in events) else "Failure"
        doc.heading(f"{kind} what-if {i}", need=1.8)
        if f.get("message"):
            doc.para(f"Asked: “{f['message']}”", 8.5, MUTED, italic=True)
        doc.table(
            [
                ("Unit out", 1.9, "left"),
                ("From", 0.6, "left"),
                ("To", 0.6, "left"),
                ("Days", 0.45, "right"),
                ("How the days were set", 3.0, "left"),
            ],
            [
                [
                    e["words"][0].upper() + e["words"][1:],
                    e["from"],
                    e["to"],
                    str(e["days"]),
                    e["how"] + (f"; {e['assumed']}" if e.get("assumed") else ""),
                ]
                for e in events
            ],
        )
        doc.para(_failure_outcome(f), 9)
        days = (f.get("failed") or {}).get("days") or []
        if days:
            doc.heading(f"{kind} what-if {i}: the days not met in full", table=True)
            doc.table(
                [
                    ("Day", 0.8, "left"),
                    ("Heat demand (MW)", 1.0, "right"),
                    ("Heat short (MW)", 1.0, "right"),
                    ("Boiler (MW)", 1.0, "right"),
                    ("Cold short (MW)", 1.0, "right"),
                ],
                [
                    [
                        d["day"],
                        num(d["heat_demand_mw"], 2),
                        _short_cell(d["heat_short_mw"]),
                        num(d["boiler_mw"], 2),
                        _short_cell(d["cool_short_mw"]),
                    ]
                    for d in days[:10]
                ],
            )
            if len(days) > 10:
                more = len(days) - 10
                doc.para(f"… and {more} more day{'s' if more > 1 else ''} short.", 8.5, MUTED)
        remedies = f.get("remedies") or []
        if remedies:
            rows = []
            for r in remedies:
                best = r.get("key") == f.get("best")
                rows.append(
                    [
                        (
                            r["name"][0].upper()
                            + r["name"][1:]
                            + (BEST[bool(r.get("covers"))] if best else ""),
                            INK,
                            best,
                        ),
                        ("yes", TEAL, True) if r.get("covers") else ("no", SHORT, True),
                        num(max(r.get("heat_short_mw", 0), r.get("cool_short_mw", 0))),
                        gwh(r.get("short_gwh", 0)),
                        num(r.get("capex_meur"), 2),
                        num(r.get("yearly_keur"), 0),
                        signed(r["lcoe_delta"], 2) if r.get("lcoe_delta") is not None else "–",
                    ]
                )
            doc.heading("Remedies, each run through the same days", table=True)
            doc.table(
                [
                    ("Remedy", 2.6, "left"),
                    ("Every day met", 0.65, "left"),
                    ("Still short (MW)", 0.7, "right"),
                    ("Not delivered (GWh)", 0.8, "right"),
                    ("Capital (M€)", 0.7, "right"),
                    ("Extra cost (k€/yr)", 0.7, "right"),
                    ("Extra cost of heat and cold (€/MWh)", 0.95, "right"),
                ],
                rows,
            )
        if f.get("reliable_plan"):
            doc.para(
                f"The reliable plan of this layout, {f['reliable_plan']}, is sized so that any "
                "one unit can be out.",
                9,
            )

    windows = [(e, f) for f in mine for e in f.get("events") or [] if _planned(e)]
    if windows:
        doc.heading("Planned service windows", table=True)
        rows = []
        for e, f in windows:
            failed = f.get("failed") or {}
            short = [
                f"{word} {failed[side]['days_short']} days short "
                f"(worst {num(failed[side]['worst_mw'])} MW)"
                for side, word in (("heat", "heat"), ("cool", "cold"))
                if (failed.get(side) or {}).get("days_short")
            ]
            rows.append(
                [
                    e["words"][0].upper() + e["words"][1:],
                    e["from"],
                    e["to"],
                    str(e["days"]),
                    ("; ".join(short), SHORT, True) if short else ("met every day", TEAL),
                ]
            )
        doc.table(
            [
                ("Unit", 2.0, "left"),
                ("From", 0.7, "left"),
                ("To", 0.7, "left"),
                ("Days", 0.5, "right"),
                ("Heat and cold", 2.6, "left"),
            ],
            rows,
        )

    if y.service:
        doc.heading("Yearly service built into the year", table=True)
        doc.para(
            "Each unit is taken out once a year in its quietest weeks (heating units in summer, "
            "cooling units in winter, a bank one machine at a time); the year above already runs "
            "without it on these days"
            + (", and still meets every day." if not y.violations else "."),
            9,
        )
        doc.table(
            [
                ("Unit", 2.0, "left"),
                ("From", 0.8, "left"),
                ("To", 0.8, "left"),
                ("Days", 0.5, "right"),
            ],
            [
                [
                    str(unit)[0].upper() + str(unit)[1:],
                    reliability.day_name(int(a)),
                    reliability.day_name(int(b)),
                    str(int(b) - int(a) + 1),
                ]
                for unit, a, b in y.service
            ],
        )

    from gemini_agent import stops as stop_dates

    ranges = stop_dates.ranges_of(y)  # a row per stop: one block a doublet, or the user's ranges
    if any(ranges):
        doc.heading("Planned stops of the doublets", table=True)
        doc.table(
            [
                ("Doublet", 1.0, "left"),
                ("From", 0.8, "left"),
                ("To", 0.8, "left"),
                ("Days", 0.5, "right"),
                ("Why there", 3.6, "left"),
            ],
            [
                [
                    f"Doublet {k + 1}",
                    reliability.day_name(a),
                    reliability.day_name(b),
                    str(b - a + 1),
                    stop_dates.why(entry.brief, k, ctx["caps"].operating_days),
                ]
                for k, rows in enumerate(ranges)
                for a, b in rows
            ],
        )


def _status(room: float, at_limit: bool = True) -> Cell:
    """Return a limit's status in words: within, at the limit (no room left) or OVER."""
    if room < -1e-6:
        return ("OVER", SHORT, True)
    if at_limit and room <= 1e-6:
        return ("at the limit", AMBER, True)
    return ("within", TEAL)


def _limits(doc: _Doc, entry: LedgerEntry, ctx: dict) -> None:
    """Section 5: the limits to watch, each with its margin, and every verifier check."""
    y, alt, caps = entry.year, entry.alternative, ctx["caps"]
    doc.section_head(
        5,
        "Limits to watch",
        "The challenge's caps and the subsurface limits, with this design's value and the room "
        "left. A limit that is close is the one to watch on shift.",
    )
    rows: List[List[Cell]] = []
    rows_d = (y.plant or {}).get("doublets") or []
    if alt.n_doublets:
        rows.append(
            [
                "Number of doublets",
                "1 to 3",
                str(alt.n_doublets),
                f"{3 - alt.n_doublets} more allowed",
                _status(min(alt.n_doublets - 1, 3 - alt.n_doublets), at_limit=False),
            ]
        )
    for k, r in enumerate(rows_d):
        tag = f"doublet {r.get('doublet', k + 1)}"
        flows = np.asarray((y.doublets or [{}])[k].get("flow_m3h") or [], dtype=float)
        run = flows[flows > 0]
        if run.size:
            lo, hi = float(run.min()), float(run.max())
            rows.append(
                [
                    f"Flow while running, {tag}",
                    f"{num(caps.flow_min_m3h, 0)}–{num(caps.flow_max_m3h, 0)} m³/h",
                    f"{num(lo)}–{num(hi)} m³/h (mean {num(r.get('flow_mean_m3h'))})",
                    f"{num(lo - caps.flow_min_m3h)} m³/h above the minimum; "
                    f"{num(caps.flow_max_m3h - hi)} m³/h under the cap",
                    _status(min(lo - caps.flow_min_m3h, caps.flow_max_m3h - hi)),
                ]
            )
        days = int(r.get("days_on") or 0)
        rows.append(
            [
                f"Operating days, {tag}",
                f"at most {caps.operating_days} days a year",
                f"{days} days",
                f"{caps.operating_days - days} days",
                _status(caps.operating_days - days),
            ]
        )
    if alt.n_doublets:
        cooled = y.max_brine_cooling_k or 0.0
        rows.append(
            [
                "Brine cooled, producer to injector",
                f"at most {num(caps.max_brine_cooling_k, 0)} K",
                f"{num(cooled)} K (coldest reinjection {num(y.reinjection_c)} °C)",
                f"{num(caps.max_brine_cooling_k - cooled)} K",
                _status(caps.max_brine_cooling_k - cooled),
            ]
        )
    for k, r in enumerate(rows_d):
        tag = f"doublet {r.get('doublet', k + 1)}"
        if r.get("esp_setting_m") is not None:
            rows.append(
                [
                    f"ESP setting depth, {tag}",
                    f"at most {num(ESP_MAX_SETTING_M, 0)} m (the pump chamber)",
                    f"{num(r['esp_setting_m'], 0)} m or deeper, to stay above the gas bubble "
                    f"point of {num(r.get('bubble_point_bar'))} bar",
                    f"{num(ESP_MAX_SETTING_M - r['esp_setting_m'], 0)} m",
                    _status(ESP_MAX_SETTING_M - r["esp_setting_m"]),
                ]
            )
        if r.get("injection_top_bar") is not None:
            rows.append(
                [
                    f"Injection pressure at the top of the reservoir, {tag}",
                    f"at most {num(r['injection_limit_bar'], 0)} bar (SodM, "
                    f"{num(SODM_BAR_PER_M, 3)} bar/m)",
                    f"{num(r['injection_top_bar'], 0)} bar at full flow "
                    f"(wellhead {num(r.get('injection_full_bar'))} bar)",
                    f"{num(r['injection_limit_bar'] - r['injection_top_bar'], 0)} bar",
                    _status(r["injection_limit_bar"] - r["injection_top_bar"]),
                ]
            )
        if r.get("breakthrough_years") is not None:
            rows.append(
                [
                    f"Cold front reaches the producer, {tag}",
                    f"after the {LIFE_YEARS}-year life",
                    f"after {num(r['breakthrough_years'], 0)} years (Gringarten-Sauty)",
                    f"{num(r['breakthrough_years'] - LIFE_YEARS, 0)} years",
                    _status(r["breakthrough_years"] - LIFE_YEARS),
                ]
            )
    if rows:
        doc.table(
            [
                ("Limit", 2.0, "left"),
                ("Cap", 1.5, "left"),
                ("This design", 2.05, "left"),
                ("Room left", 1.35, "left"),
                ("Status", 0.75, "left"),
            ],
            rows,
        )
        doc.para(
            "Status: within (room left), at the limit (none left: do not push further), OVER "
            "(the design breaks it).",
            8,
            MUTED,
        )
    else:
        doc.para("This design has no doublets: none of the well limits apply.", 9)

    checks = entry.verification.checks
    doc.heading(
        f"Every check of the design: {sum(c.passed for c in checks)} of {len(checks)} passed",
        table=True,
    )
    doc.table(
        [
            ("Check", 2.4, "left"),
            ("Result", 0.6, "left"),
            ("Kind", 1.05, "left"),
            ("Detail", 3.5, "left"),
        ],
        [
            [
                c.name,
                ("✓ pass", TEAL, True) if c.passed else ("✗ FAIL", SHORT, True),
                "challenge cap" if c.requirement else "physics",
                c.detail,
            ]
            for c in checks
        ],
    )
    if y.warnings:
        doc.heading("Warnings from the model", need=0.8)
        doc.bullets(list(y.warnings), size=8.5)


def _assumptions(doc: _Doc, session, entry: LedgerEntry, ctx: dict) -> None:
    """Section 6: networks, prices, capital, reservoir, how the wells are modelled, not modelled."""
    y, alt, pv, econ = entry.year, entry.alternative, ctx["plant"], ctx["econ"]
    doc.section_head(6, "Assumptions and sources", need=3.0)
    caps = ctx["caps"]
    doc.bullets(
        [
            f"Heating network: supply {num(pv['heating_supply_c'], 0)} °C (fixed by the challenge: "
            f"{num(caps.heat_supply_c, 0)} °C), return {num(pv['heating_return_c'], 0)} °C (not "
            "given: our assumption).",
            f"Cooling network: supply {num(pv['cooling_supply_c'], 0)} °C (fixed by the challenge: "
            f"{num(caps.cool_supply_c, 0)} °C), return {num(pv['cooling_return_c'], 0)} °C (not "
            "given: our assumption).",
            (
                "Demand: the organisers' daily heat and cold demand for 2027 ("
                + ", ".join(f for f in (session.project.files or []) if f.lower().endswith(".csv"))
                + ")."
                if any(f.lower().endswith(".csv") for f in (session.project.files or []))
                else "Demand: the project's daily heat and cold demand."
            ),
        ]
        + (
            [
                "Reservoir: "
                + ", ".join(
                    (
                        f"{num(pv['reservoir']['depth_m'], 0)} m",
                        f"{num(pv['reservoir']['temperature_c'])} °C",
                        f"{num(pv['reservoir']['pressure_bar'])} bar",
                        f"{num(pv['reservoir']['permeability_md'], 0)} mD",
                        f"{num(pv['reservoir']['thickness_m'], 0)} m thick",
                    )
                )
                + f"; brine {num(pv['reservoir']['brine_density_kg_m3'], 0)} kg/m³, "
                f"{num(pv['reservoir']['brine_viscosity_mpa_s'], 2)} mPa·s, gas "
                f"{num(pv['reservoir']['gas_liquid_ratio'])} Nm³ per m³ of brine."
                + "".join(
                    f" Doublet {a['doublet']}: {a['label']}." for a in pv.get("aquifers") or []
                )
            ]
            if alt.n_doublets
            else []
        ),
        size=8.5,
    )
    view = workbench.assumptions_view(session)
    known = {it["key"]: it for it in view["items"]}
    prices = [dict(known[k], **PRICE_ROWS.get(k, {})) for k in PRICE_KEYS if k in known]
    if prices:
        doc.heading("Prices (2025 euros)", table=True)
        rows = []
        for it in prices:
            value = it["value"]
            shown = (
                f"{num(value * 100)}%"
                if it["key"] == "discount_rate"
                else f"{num(value)} {it['unit']}"
            )
            if value != it["default"]:
                default = (
                    f"{num(it['default'] * 100)}%"
                    if it["key"] == "discount_rate"
                    else num(it["default"])
                )
                shown = (shown + f" (changed; default {default})", SHORT, True)
            rows.append([it["label"], shown, it["source"]])
        doc.table([("Price", 1.4, "left"), ("Value", 1.4, "left"), ("Source", 4.6, "left")], rows)
    items = econ.get("capex_items") or []
    if items:
        doc.heading("Capital", table=True)
        rows = [
            [
                it["item"],
                f"{num(it['size'], 2)} {it['unit']}",
                f"{num(it['meur_per_unit'], 3)} M€",
                num(it["meur"], 2),
                num(it.get("life_years"), 0),
            ]
            for it in items
        ]
        rows.append(["Total", "", "", num(econ["capex_meur"], 2), ""])
        doc.table(
            [
                ("Item", 2.2, "left"),
                ("Size", 1.3, "right"),
                ("Per unit", 1.2, "right"),
                ("Cost (M€)", 1.0, "right"),
                ("Life (years)", 0.9, "right"),
            ],
            rows,
            bold_last=True,
        )
    model = next((n for n in ctx["notes"] if n.startswith("Wells (pressures")), "")
    if model:
        doc.heading("How the wells are modelled", need=1.0)
        doc.para(model, 8, MUTED)
    gemini = (y.plant or {}).get("gemini") or {}
    sources = []
    if gemini:
        sources.append(
            f"Wells: GEMINI {gemini.get('version', '')} ({gemini.get('variant', 'fixed')}, "
            f"{gemini.get('patches', 0)} of the team's fixes): flow, pumps and wellhead."
        )
    sources += [
        "The year, day by day, and the costs: Dioscuri's plant model (dioscuri_plant); prices and "
        "unit costs sourced per line (above and in the app's Economics tab).",
        "The checks: the agent's verifier, against the challenge's caps.",
    ]
    doc.heading("Where the numbers come from", need=0.9)
    doc.bullets(sources, size=8.5)
    words = answer.not_modelled(entry).replace(" (say so; never describe them as there)", "")
    doc.heading("Not modelled", need=0.8)
    doc.para(words, 8.5, INK)


# ------------------------------------------------------------------ the report


# What the report holds, in its order (the chat's download card lists them).
SECTIONS = (
    "The design at a glance",
    "How it runs over the year",
    "CO₂ by unit",
    "Month by month",
    "Firm capacity",
    "Failures and maintenance",
    "Limits to watch",
    "Assumptions and sources",
)


def build(session, design_id: Optional[str] = None, today: Optional[date] = None) -> bytes:
    """Return the operator's report of one design of a conversation, as a PDF.

    Parameters
    ----------
    session : Session
        The conversation (its ledger, cost assumptions and failure what-ifs).
    design_id : str, optional
        The design's id (``A1 · 1D-HP-EC-N1``); the conversation's chosen design by default.
    today : date, optional
        The date on the pages; today by default.

    Returns
    -------
    bytes
        An A4 portrait PDF, about six pages.

    Raises
    ------
    KeyError
        No design with this id in the conversation, or none chosen yet.
    """
    doc = layout(session, design_id, today)
    with matplotlib.rc_context(RC):
        return doc.save(doc.metadata)


def layout(session, design_id: Optional[str] = None, today: Optional[date] = None) -> _Doc:
    """Return the report laid out, footers on, not yet saved (``build`` saves it).

    Its pages are ``doc.figs``, matplotlib figures whose texts the tests can measure; the PDF's
    metadata is ``doc.metadata``. The arguments and errors are ``build``'s.
    """
    found = target(session, design_id)
    entry = _with_days(found, session)
    today = today or date.today()
    did = reporter.design_id(found)
    meta = (session.user_designs or {}).get(found.alternative.code, {})
    ctx = {
        "id": did,
        "name": meta.get("name") or found.alternative.name or found.alternative.code,
        "long_date": f"{today.day} {today:%B %Y}",
        "econ": workbench.economics_view(entry, session.assumptions or {}),
        "plant": workbench.plant_view(entry),
        "firm": reporter.firm_view(entry) if entry.alternative.n_doublets else None,
        "caps": engine.project_caps(entry.brief),
        "rules": engine.rules_for(entry.brief),
        "notes": answer.design_notes(entry),
        # By id, or by the plant's code: a later search renames the same design (A1 then G1),
        # and its failures were left out as "none run yet" (1 Nov).
        "failures": [
            f
            for f in (session.failures or [])
            if f.get("design") == did or f.get("code") == entry.alternative.code
        ],
    }
    with matplotlib.rc_context(RC):
        doc = _Doc(did, f"Report of {ctx['long_date']}")
        _cover(doc, session, entry, ctx)
        _year(doc, session, entry, ctx)
        _firm(doc, entry, ctx)
        _failures(doc, session, entry, ctx)
        _limits(doc, entry, ctx)
        _assumptions(doc, session, entry, ctx)
        doc.footers()
    doc.metadata = {
        "Title": f"Plant operator's report: {did}",
        "Author": "Dioscuri",
        "Subject": ctx["name"],
        "Creator": "Dioscuri agent (matplotlib)",
        "CreationDate": datetime(today.year, today.month, today.day),
    }
    return doc
