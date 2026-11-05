"""Generate the Dioscuri logo: the two i's of the name joined underground by a geothermal loop.

Usage:
    pip install cairosvg fonttools
    python make_logo.py "InstrumentSans[wdth,wght].ttf" [OUT_DIR]

The font is Instrument Sans (SIL Open Font License) from Google Fonts. Letters are outlined, so the
SVGs render the same everywhere without the font installed.
"""

import math
import pathlib
import sys
import tempfile

import cairosvg
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

FONT_VF = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(__file__).parent
SVG_DIR, PNG_DIR = OUT / "svg", OUT / "png"

INK, PAPER, WHITE = "#11181C", "#F4F2EE", "#FFFFFF"
POLLUX, CASTOR = "#E35D28", "#3F7FE0"  # hot producer and cold injector; 3:1 or more on white, paper and ink
# Brine temperature along the reservoir, from the hot producer to the cold injector.
THERMAL = [(0, POLLUX), (0.42, "#D94A5A"), (0.62, "#9A55C9"), (1, CASTOR)]
DEPTH = 0.44  # loop depth below the baseline, as a share of the x-height

static = pathlib.Path(tempfile.gettempdir()) / "InstrumentSans-620-100.ttf"
if not static.exists():
    instantiateVariableFont(TTFont(FONT_VF), {"wght": 620, "wdth": 100}).save(static)
FONT = TTFont(static)
GLYPHS = FONT.getGlyphSet()
CMAP = FONT.getBestCmap()
UPM = FONT["head"].unitsPerEm
XHEIGHT = FONT["OS/2"].sxHeight


def logo(uid, size, x0, y0, ink=INK, mono=None, pulse=False, period=4.2, track=-0.022):
    """Lowercase 'dioscuri' with its two i's joined below the baseline.

    The first i is the producer well and Pollux, the brighter twin; the last i is the injector and
    Castor. The loop between them carries the brine's temperature. `mono` paints everything in one
    colour. Returns (svg elements, box) where box = (left, top, right, bottom) in user units.
    """
    s = size / UPM
    x, letters, wells = 0.0, [], []
    for ch in "dioscuri":
        glyph = GLYPHS[CMAP[0x131] if ch == "i" else CMAP[ord(ch)]]
        pen = SVGPathPen(GLYPHS)
        glyph.draw(TransformPen(pen, (s, 0, 0, -s, x0 + x * s, y0)))
        if ch == "i":
            bp = BoundsPen(GLYPHS)
            glyph.draw(bp)
            xmin, _, xmax, ymax = bp.bounds
            wells.append((x0 + (x + (xmin + xmax) / 2) * s, (xmax - xmin) * s, ymax * s, pen.getCommands()))
        else:
            letters.append(pen.getCommands())
        x += glyph.width + track * UPM
    (x1, stem, top, producer), (x2, _, _, injector) = wells
    depth = XHEIGHT * s * DEPTH
    r = min(depth * 0.62, (x2 - x1) / 2)
    yb = y0 + depth
    down = f"M{x1:.2f} {y0 - 0.6:.2f} V{yb - r:.2f} A{r:.2f} {r:.2f} 0 0 0 {x1 + r:.2f} {yb:.2f} H{x2 - r:.2f} A{r:.2f} {r:.2f} 0 0 0 {x2:.2f} {yb - r:.2f} V{y0 - 0.6:.2f}"
    dot_y = y0 - top - stem * 1.30
    dots = (stem * 0.70, stem * 0.66)  # Pollux is the brighter twin in the night sky
    hot, cold = (mono, mono) if mono else (POLLUX, CASTOR)
    loop_paint = mono or f"url(#{uid})"
    defs = "" if mono else (
        f'<defs><linearGradient id="{uid}" x1="{x1 - stem / 2:.2f}" y1="0" x2="{x2 + stem / 2:.2f}" y2="0" gradientUnits="userSpaceOnUse">'
        + "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in THERMAL) + "</linearGradient></defs>")
    glint = ""
    if pulse:
        legs = 2 * (yb - r - (y0 - 0.6))
        length = legs + math.pi * r + (x2 - x1 - 2 * r)
        seg = length * 0.16
        up = f"M{x2:.2f} {y0 - 0.6:.2f} V{yb - r:.2f} A{r:.2f} {r:.2f} 0 0 1 {x2 - r:.2f} {yb:.2f} H{x1 + r:.2f} A{r:.2f} {r:.2f} 0 0 1 {x1:.2f} {yb - r:.2f} V{y0 - 0.6:.2f}"
        glint = (f'<path d="{up}" fill="none" stroke="#FFFFFF" stroke-opacity="0.55" stroke-width="{stem * 0.46:.2f}" stroke-linecap="round" '
                 f'stroke-dasharray="{seg:.2f} {length:.2f}"><animate attributeName="stroke-dashoffset" values="{seg:.2f};{-length:.2f}" dur="{period}s" repeatCount="indefinite"/></path>')
    body = (defs + f'<path d="{" ".join(letters)}" fill="{ink}"/>'
            f'<path d="{down}" fill="none" stroke="{loop_paint}" stroke-width="{stem:.2f}"/>'
            f'<path d="{producer}" fill="{hot}"/><path d="{injector}" fill="{cold}"/>' + glint
            + f'<circle cx="{x1:.2f}" cy="{dot_y:.2f}" r="{dots[0]:.2f}" fill="{hot}"/>'
            f'<circle cx="{x2:.2f}" cy="{dot_y:.2f}" r="{dots[1]:.2f}" fill="{cold}"/>')
    box = (x0, dot_y - dots[0], max(x0 + (x - track * UPM) * s, x2 + dots[0]), yb + stem / 2)
    return body, box


def document(size=120, ink=INK, mono=None, pulse=False, pad=0.12, background=None, square=False):
    body, (l, t, r, b) = logo("g", size, 0, 0, ink=ink, mono=mono, pulse=pulse)
    p = size * pad
    w, h = r - l + 2 * p, b - t + 2 * p
    dx, dy = p - l, p - t
    if square:
        side = max(w, h) * 1.18
        dx, dy, w, h = (side - (r - l)) / 2 - l, (side - (b - t)) / 2 - t, side, side
    bg = f'<rect width="{w:.0f}" height="{h:.0f}" rx="{h * 0.22 if square else 0:.0f}" fill="{background}"/>' if background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">'
            f'{bg}<g transform="translate({dx:.2f} {dy:.2f})">{body}</g></svg>')


FILES = {
    "dioscuri-logo.svg": document(),
    "dioscuri-logo-white.svg": document(ink=WHITE),
    "dioscuri-logo-mono.svg": document(mono=INK, ink=INK),
    "dioscuri-logo-mono-white.svg": document(mono=WHITE, ink=WHITE),
    "dioscuri-logo-animated.svg": document(pulse=True),
    "dioscuri-logo-animated-white.svg": document(ink=WHITE, pulse=True),
    "dioscuri-avatar.svg": document(size=100, ink=WHITE, background=INK, square=True),
}

if __name__ == "__main__":
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    for old in list(SVG_DIR.glob("dioscuri-*.svg")) + list(PNG_DIR.glob("dioscuri-*.png")):
        old.unlink()
    for name, svg in FILES.items():
        (SVG_DIR / name).write_text(svg)
    for name in ("dioscuri-logo", "dioscuri-logo-white", "dioscuri-logo-mono"):
        svg = FILES[name + ".svg"]
        w, h = (float(svg.split(f'{k}="', 1)[1].split('"', 1)[0]) for k in ("width", "height"))
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(PNG_DIR / f"{name}@4x.png"), output_width=round(w * 4), output_height=round(h * 4))
    for size in (1024, 512):
        cairosvg.svg2png(bytestring=FILES["dioscuri-avatar.svg"].encode(), write_to=str(PNG_DIR / f"dioscuri-avatar-{size}.png"), output_width=size, output_height=size)
    print(f"wrote {len(FILES)} SVGs to {SVG_DIR} and PNGs to {PNG_DIR}")
