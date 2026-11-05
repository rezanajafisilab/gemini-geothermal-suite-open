"""Compose the canvas brand board (Brand.dc.html) and the header snippets from make_logo.py.

Usage:
    python compose_brand_board.py "InstrumentSans[wdth,wght].ttf" . ../design/ui-prototype/Brand.dc.html

Also writes _brand_snippets.json (22 px header logo, 40 px chat logo) next to the target.
"""

import json
import math
import pathlib
import sys

FONT, BRAND, TARGET = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
sys.argv = ["make_logo.py", FONT]
sys.path.insert(0, BRAND)
import make_logo as ml  # noqa: E402

INK, PAPER, WHITE, MUTED = ml.INK, ml.PAPER, ml.WHITE, "#66727C"


def anchors(size, x0, y0, track=-0.022):
    """Key points of the logo, mirroring make_logo.logo()."""
    s = size / ml.UPM
    x, wells = 0.0, []
    from fontTools.pens.boundsPen import BoundsPen
    for ch in "dioscuri":
        glyph = ml.GLYPHS[ml.CMAP[0x131] if ch == "i" else ml.CMAP[ord(ch)]]
        if ch == "i":
            bp = BoundsPen(ml.GLYPHS)
            glyph.draw(bp)
            xmin, _, xmax, ymax = bp.bounds
            wells.append((x0 + (x + (xmin + xmax) / 2) * s, (xmax - xmin) * s, ymax * s))
        x += glyph.width + track * ml.UPM
    (x1, stem, top), (x2, _, _) = wells
    depth = ml.XHEIGHT * s * ml.DEPTH
    r = min(depth * 0.62, (x2 - x1) / 2)
    return dict(x1=x1, x2=x2, stem=stem, top=top, base=y0, yb=y0 + depth, r=r, dot_y=y0 - top - stem * 1.30,
                xh=ml.XHEIGHT * s, right=x0 + (x - track * ml.UPM) * s)


def glint(a, period=4.2):
    """Brine glint path from the injector down, through the reservoir, up the producer."""
    x1, x2, y0, yb, r = a["x1"], a["x2"], a["base"] - 0.6, a["yb"], a["r"]
    length = 2 * (yb - r - y0) + math.pi * r + (x2 - x1 - 2 * r)
    seg = length * 0.16
    d = f"M{x2:.2f} {y0:.2f} V{yb - r:.2f} A{r:.2f} {r:.2f} 0 0 1 {x2 - r:.2f} {yb:.2f} H{x1 + r:.2f} A{r:.2f} {r:.2f} 0 0 1 {x1:.2f} {yb - r:.2f} V{y0:.2f}"
    return d, seg, length


def inline(uid, size, ink=INK, mono=None, pad=0.08, extra="", label="dioscuri"):
    body, (l, t, rr, b) = ml.logo(uid, size, 0, 0, ink=ink, mono=mono)
    p = size * pad
    w, h = rr - l + 2 * p, b - t + 2 * p
    return (f'<svg width="{w:.0f}" height="{h:.0f}" viewBox="{l - p:.1f} {t - p:.1f} {w:.1f} {h:.1f}" role="img" aria-label="{label}" style="display: block; max-width: 100%; height: auto">'
            f"{body}{extra}</svg>"), w, h


# Hero: white logo with an animated glint of brine.
HS = 168
ha = anchors(HS, 0, 0)
gd, gseg, glen = glint(ha)
hero_extra = (f'<path class="ta-glint" d="{gd}" fill="none" stroke="#FFFFFF" stroke-opacity="0.6" stroke-width="{ha["stem"] * 0.46:.2f}" '
              f'stroke-linecap="round" stroke-dasharray="{gseg:.2f} {glen:.2f}" style="animation-play-state: {{{{ anim }}}}"></path>')
hero_svg, _, _ = inline("hero", HS, ink=WHITE, extra=hero_extra, label="dioscuri logo, animated")

# Anatomy: annotated logo on paper.
AS, AX, AY = 150, 250, 190
aa = anchors(AS, AX, AY)
abody, (al, at, ar, ab) = ml.logo("anat", AS, AX, AY)
lead = "#8E999E"


def note(px, py, tx, ty, text, anchor="start"):
    return (f'<path d="M{px:.1f} {py:.1f} L{tx:.1f} {ty:.1f}" stroke="{lead}" stroke-width="1"/>'
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.6" fill="{INK}"/>'
            f'<text x="{tx + (6 if anchor == "start" else -6):.1f}" y="{ty + 4:.1f}" text-anchor="{anchor}" '
            f'style="font-family: \'JetBrains Mono\', Consolas, monospace; font-size: 13px; fill: #45515B">{text}</text>')


mid_x = (aa["x1"] + aa["x2"]) / 2
anatomy = (f'<svg viewBox="0 0 1060 318" role="img" aria-label="Anatomy of the logo" style="display: block; width: 100%; height: auto">'
           f'<path d="M40 {aa["base"]:.1f} H1020" stroke="#B6AE9F" stroke-width="1" stroke-dasharray="4 5"/>'
           f'<text x="1020" y="{aa["base"] + 20:.1f}" text-anchor="end" style="font-family: \'JetBrains Mono\', Consolas, monospace; font-size: 13px; fill: #8C7F68">ground</text>'
           + abody
           + note(aa["x1"], aa["dot_y"], aa["x1"] - 70, aa["dot_y"] - 52, "Pollux, the brighter twin", "end")
           + note(aa["x2"], aa["dot_y"], aa["x2"] + 70, aa["dot_y"] - 52, "Castor")
           + note(aa["x1"], aa["base"] + 8, aa["x1"] - 150, aa["base"] + 8, "producer well, hot", "end")
           + note(aa["x2"], aa["base"] - aa["xh"] * 0.5, aa["x2"] + 70, aa["base"] - aa["xh"] * 0.5, "injector well, cold")
           + note(mid_x, aa["yb"], mid_x, aa["yb"] + 58, "reservoir: the brine heats up on its way back", "middle").replace(f'x="{mid_x - 6:.1f}"', f'x="{mid_x:.1f}"')
           + "</svg>")

# Usage tiles.
tiles = []
for bg, ink, mono, name in ((PAPER, INK, None, "On paper"), (INK, WHITE, None, "On dark"), (WHITE, INK, INK, "One colour"), (ml.POLLUX, WHITE, WHITE, "Reversed")):
    svg_, w_, h_ = inline("u" + name.split()[-1].lower(), 84, ink=ink, mono=mono)
    tiles.append((bg, svg_, name, bg in (INK, ml.POLLUX)))
small_hdr, _, _ = inline("hdrdemo", 22)
small_14, _, _ = inline("s14", 15)
avatar = (pathlib.Path(BRAND) / "svg" / "dioscuri-avatar.svg").read_text().replace("<svg ", '<svg aria-hidden="true" style="display: block; width: 116px; height: 116px" ', 1)

CARD = "background: #FFFFFF; border-radius: 22px; box-shadow: 0 0 0 1px rgba(17,24,28,.07), 0 12px 32px -18px rgba(17,24,28,.18)"
MONO = "font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; color: #45515B"
grad_css = ", ".join(f"{c} {o * 100:.0f}%" for o, c in ml.THERMAL)

tile_html = "".join(
    f'<div style="border-radius: 18px; background: {bg}; padding: 30px 26px 16px; display: flex; flex-direction: column; gap: 14px; min-width: 0; box-shadow: 0 0 0 1px rgba(17,24,28,.06)">'
    f'<div style="display: flex; justify-content: center">{svg_}</div>'
    f'<span style="font-size: 12.5px; color: {"#D3DCDD" if dark else "#45515B"}">{name}</span></div>'
    for bg, svg_, name, dark in tiles)

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Dioscuri: logo</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wdth,wght@75..100,400..700&amp;family=JetBrains+Mono:wght@400;500&amp;display=swap">
<style>
body{{margin:0}}
.ta-btn{{transition:background-color .16s ease,transform .16s ease}}
.ta-btn:hover{{transform:translateY(-1px)}}
@keyframes ta-glint{{from{{stroke-dashoffset:{gseg:.2f}}}to{{stroke-dashoffset:{-glen:.2f}}}}}
.ta-glint{{animation:ta-glint 4.2s linear infinite}}
@keyframes ta-rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
.ta-rise{{animation:ta-rise .5s cubic-bezier(.2,.7,.2,1) both}}
:focus-visible{{outline:2px solid #0B8FA0;outline-offset:2px;border-radius:8px}}
@media (prefers-reduced-motion: reduce){{.ta-glint{{animation:none;opacity:0}}.ta-rise{{animation:none}}}}
</style>
</helmet>
<div style="min-height: 100vh; background: {PAPER}; color: {INK}; font-family: 'Instrument Sans', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 15px; line-height: 1.5">
  <main style="max-width: 1240px; margin: 0 auto; padding: 32px 24px 48px; box-sizing: border-box; display: flex; flex-direction: column; gap: 22px">

    <section class="ta-rise" aria-label="The Dioscuri logo" style="border-radius: 28px; background: radial-gradient(110% 120% at 50% 0%, #1A242C 0%, {INK} 60%); color: #FFFFFF; padding: 72px 48px 40px; display: flex; flex-direction: column; align-items: center; gap: 34px">
      {hero_svg}
      <div style="display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; max-width: 62ch">
        <span style="font-size: 24px; font-weight: 600; letter-spacing: -0.01em">Two i's, one doublet.</span>
        <span style="font-size: 16px; color: #AEB9BE; text-wrap: pretty">The first i is the producer and Pollux, the brighter twin. The last i is the injector and Castor. Below the ground they become one loop, coloured by the brine's temperature.</span>
        <span style="display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 6px">
          <span style="padding: 4px 11px; border-radius: 999px; background: rgba(255,255,255,.08); font-size: 13px; color: #D3DCDD">SPE Europe GeoHackathon 2026</span>
          <button type="button" class="ta-btn" onClick="{{{{ toggle }}}}" aria-pressed="{{{{ paused }}}}" style="padding: 4px 11px; border-radius: 999px; border: 1px solid rgba(255,255,255,.18); background: transparent; font: inherit; font-size: 13px; color: #D3DCDD; cursor: pointer">{{{{ toggleLabel }}}}</button>
        </span>
      </div>
    </section>

    <section class="ta-rise" aria-label="Anatomy" style="animation-delay: .06s; {CARD}; padding: 22px 26px 18px; display: flex; flex-direction: column; gap: 4px">
      <span style="font-size: 13px; color: #45515B">Anatomy</span>
      {anatomy}
    </section>

    <section class="ta-rise" aria-label="In use" style="animation-delay: .12s; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(270px, 100%), 1fr)); gap: 16px">
      {tile_html}
    </section>

    <section class="ta-rise" style="animation-delay: .18s; display: grid; grid-template-columns: repeat(auto-fit, minmax(min(360px, 100%), 1fr)); gap: 16px">
      <div style="{CARD}; padding: 22px 24px; display: flex; flex-direction: column; gap: 16px">
        <span style="font-size: 13px; color: #45515B">Small sizes</span>
        <div style="display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 14px; background: #FFFFFF; box-shadow: 0 0 0 1px rgba(17,24,28,.08)">{small_hdr}<span style="width: 1px; height: 22px; background: rgba(17,24,28,.14)"></span><span style="font-size: 13px; color: {MUTED}">Example district</span></div>
        <div style="display: flex; align-items: center; gap: 22px">{small_14}{avatar}</div>
        <span style="font-size: 13px; color: {MUTED}">The app header uses the logo at 22 px. The square avatar is for GitHub and slides.</span>
      </div>
      <div style="{CARD}; padding: 22px 24px; display: flex; flex-direction: column; gap: 16px">
        <span style="font-size: 13px; color: #45515B">Colour and type</span>
        <div style="height: 18px; border-radius: 9px; background: linear-gradient(90deg, {grad_css})"></div>
        <div style="display: flex; justify-content: space-between; {MONO}"><span>hot {ml.POLLUX}</span><span>#D94A5A</span><span>#9A55C9</span><span>cold {ml.CASTOR}</span></div>
        <div style="display: flex; flex-wrap: wrap; gap: 14px 24px; align-items: center">
          <span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 28px; height: 28px; border-radius: 9px; background: {INK}"></span><span style="{MONO}">ink {INK}</span></span>
          <span style="display: inline-flex; align-items: center; gap: 8px"><span style="width: 28px; height: 28px; border-radius: 9px; background: {PAPER}; box-shadow: inset 0 0 0 1px rgba(17,24,28,.14)"></span><span style="{MONO}">paper {PAPER}</span></span>
        </div>
        <span style="font-size: 13px; color: {MUTED}">Instrument Sans SemiBold, tracked in 2.2%, with the two i-dots replaced by the twin stars. Files: hackathon/brand/</span>
      </div>
    </section>
  </main>
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":1440,"height":1540}}}}'>
class Component extends DCLogic {{
  constructor(props) {{
    super(props);
    this.state = {{ paused: false }};
  }}

  renderVals() {{
    const paused = this.state.paused;
    return {{
      anim: paused ? 'paused' : 'running',
      paused,
      toggle: () => this.setState({{ paused: !this.state.paused }}),
      toggleLabel: paused ? 'Play the loop' : 'Pause the loop',
    }};
  }}
}}
</script>
</body>
</html>
"""
TARGET.write_text(page)

# Header snippet for the app screens: logo at 22 px, a hairline, and the project name.
hdr, _, _ = inline("hdr", 22, label="dioscuri")
idle, _, _ = inline("idle", 40, label="dioscuri")
json.dump({"header": hdr, "idle": idle}, open(TARGET.with_name("_brand_snippets.json"), "w"))
print("wrote", TARGET, len(page))
