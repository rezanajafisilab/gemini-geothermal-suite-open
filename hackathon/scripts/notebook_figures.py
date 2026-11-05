"""SVG figures for ADR-0003 (UI stack), shared by the notebook build and the repo markdown.

Each builder returns SVG markup. ``standalone=False`` gives the inline variant used inside the
notebook page: colours come from the page's CSS tokens (``var(--token, fallback)``) and ink is
``currentColor``, so both themes work. ``standalone=True`` adds an opaque background, an xmlns
and pixel size so the same drawing renders as an image file in any markdown viewer.
"""

from html import escape

SANS = "IBM Plex Sans, Segoe UI, Helvetica, Arial, sans-serif"
MONO = "IBM Plex Mono, Consolas, Menlo, monospace"

# fallbacks = the notebook's light theme, used by standalone files
FALLBACK = {
    "surface": "#fbfbf9",
    "panel": "#e8ebe6",
    "bg": "#f3f4f1",
    "line": "#c9cfc7",
    "muted": "#5f6b75",
    "accent": "#0b6a75",
    "accent-wash": "#d6ebec",
    "heat": "#b8471c",
    "cold": "#22679e",
    "warn": "#a86a00",
    "good": "#1f7a4d",
    "code-bg": "#eceee9",
    "bar-ctx": "#b3bab2",
    "bar-pick": "#11949f",
}


_MODE = {"standalone": False}


def ink():
    """Return the ink colour: currentColor inline (follows the theme), literal in files."""
    return "#172028" if _MODE["standalone"] else "currentColor"


def c(token):
    """Return a theme colour: a CSS token inline, the literal light value in standalone files."""
    if _MODE["standalone"]:
        return FALLBACK[token]
    return f"var(--{token},{FALLBACK[token]})"


def text(x, y, s, size=12, anchor="start", weight=None, mono=False, color=None, cls=""):
    """Return a <text> element; colour defaults to currentColor (theme ink)."""
    attrs = [
        f'x="{x}"',
        f'y="{y}"',
        f'font-size="{size}"',
        f'font-family="{MONO if mono else SANS}"',
        f'text-anchor="{anchor}"',
    ]
    if weight:
        attrs.append(f'font-weight="{weight}"')
    classes = " ".join(filter(None, ["m" if mono else "s", cls]))
    attrs.append(f'class="{classes}"')
    if color:
        attrs.append(f'style="fill:{c(color)}"')
    else:
        attrs.append(f'fill="{ink()}"')
    return f"<text {' '.join(attrs)}>{escape(s)}</text>"


def box(x, y, w, h, fill="surface", stroke_opacity=0.45, rx=6, stroke=None, dash=None, extra=""):
    """Return a rounded rectangle with a token fill and a currentColor (or token) stroke."""
    stroke_attr = f'style="fill:{c(fill)};stroke:{c(stroke)}"' if stroke else (
        f'style="fill:{c(fill)}" stroke="{ink()}" stroke-opacity="{stroke_opacity}"'
    )
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" {stroke_attr}{dash_attr}{extra}/>'
    )


def _wrap(view_w, view_h, label, body, standalone, uid):
    """Wrap figure body in an <svg> root (inline or standalone)."""
    marker = (
        f'<defs><marker id="{uid}-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{ink()}"/></marker></defs>'
    )
    if standalone:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{view_w}" height="{view_h}" '
            f'viewBox="0 0 {view_w} {view_h}" role="img" aria-label="{escape(label)}" '
            f'color="#172028">'
            f'<rect width="{view_w}" height="{view_h}" fill="{FALLBACK["surface"]}"/>'
        )
    else:
        head = (
            f'<svg viewBox="0 0 {view_w} {view_h}" role="img" aria-label="{escape(label)}" '
            f'class="fig-svg">'
        )
    return head + marker + body + "</svg>"


def arrow(x1, y1, x2, y2, uid, both=False, color=None, width=1.4):
    """Return a straight arrow line using the figure's marker."""
    stroke = f'style="stroke:{c(color)}"' if color else f'stroke="{ink()}"'
    start = f' marker-start="url(#{uid}-arrow)"' if both else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {stroke} stroke-width="{width}"'
        f'{start} marker-end="url(#{uid}-arrow)"/>'
    )


# ------------------------------------------------------------------ figure 1: runtime


def runtime_figure(standalone=False):
    """Team machine builds the SPA once; the judge's laptop runs one Python process + Ollama."""
    _MODE["standalone"] = standalone
    u = "f1"
    b = []
    # regions
    b.append(text(16, 32, "TEAM MACHINE · NODE 24", size=11, mono=True, weight=500, color="muted"))
    b.append(box(12, 42, 228, 352, fill="surface", dash="5 5", rx=10, stroke_opacity=0.35))
    b.append(
        text(266, 32, "JUDGE'S LAPTOP · WINDOWS · CPU ONLY", size=11, mono=True, weight=500,
             color="muted")
    )
    b.append(box(262, 42, 626, 352, fill="panel", rx=10, stroke_opacity=0.35))

    # team side: source -> dist -> repo
    for y, title, sub in [
        (78, "frontend/", "React · assistant-ui · shadcn"),
        (186, "frontend/dist/", "static HTML · JS · CSS"),
        (294, "Git repo", "what the judges download"),
    ]:
        b.append(box(32, y, 188, 52))
        b.append(text(126, y + 22, title, size=12.5, anchor="middle", mono=True, weight=600))
        b.append(text(126, y + 40, sub, size=11, anchor="middle", color="muted"))
    b.append(arrow(126, 130, 126, 182, u))
    b.append(text(134, 160, "vite build, once", size=11))
    b.append(arrow(126, 238, 126, 290, u))
    b.append(text(134, 268, "git commit", size=11))

    # judge side: install steps (a real sequence, so numbered)
    for x, w, label in [
        (282, 242, "1  pip install -r requirements.txt"),
        (534, 172, "2  ollama pull <model>"),
        (716, 152, "3  python run.py"),
    ]:
        b.append(box(x, 58, w, 28, fill="surface", rx=14, stroke_opacity=0.3))
        b.append(text(x + 14, 76, label, size=11, mono=True))

    # browser
    b.append(box(282, 120, 104, 220))
    b.append(text(334, 224, "Browser", size=12.5, anchor="middle", weight=600))
    b.append(text(334, 242, "opens on run", size=11, anchor="middle", color="muted"))

    # FastAPI process with three routes
    b.append(box(438, 106, 222, 244, fill="surface", rx=8, stroke_opacity=0.55))
    b.append(text(549, 126, "FastAPI · 127.0.0.1:8000", size=11.5, anchor="middle", mono=True,
                  weight=600))
    b.append(text(549, 143, "one process · Python 3.12", size=10.5, anchor="middle",
                  color="muted"))
    routes = [
        (158, "/agent", "AG-UI event stream"),
        (216, "/gradio", "Gradio safety net"),
        (274, "/", "SPA from frontend/dist/"),
    ]
    for y, path, sub in routes:
        b.append(box(452, y, 194, 46, fill="bg", stroke_opacity=0.35))
        b.append(text(464, y + 20, path, size=12, mono=True, weight=600))
        b.append(text(464, y + 37, sub, size=11, color="muted"))
    # browser <-> routes
    b.append(arrow(388, 181, 450, 181, u, both=True))
    b.append(text(419, 174, "POST · SSE", size=10, anchor="middle"))
    b.append(arrow(388, 239, 450, 239, u))
    b.append(text(419, 232, "GET", size=10, anchor="middle"))
    b.append(arrow(388, 297, 450, 297, u))
    b.append(text(419, 290, "GET", size=10, anchor="middle"))

    # agent and what it calls
    b.append(box(690, 158, 180, 46, stroke=None))
    b.append(text(780, 178, "Agent loop", size=12.5, anchor="middle", weight=600))
    b.append(text(780, 195, "intake · tools · verifier", size=11, anchor="middle", color="muted"))
    b.append(arrow(646, 181, 688, 181, u))
    b.append(text(667, 174, "runs", size=10, anchor="middle"))
    b.append(box(690, 262, 86, 56))
    b.append(text(733, 285, "Ollama", size=12, anchor="middle", weight=600))
    b.append(text(733, 303, "CPU model", size=10.5, anchor="middle", color="muted"))
    b.append(box(784, 262, 86, 56))
    b.append(text(827, 285, "GEMINI", size=12, anchor="middle", weight=600))
    b.append(text(827, 303, "+ our tools", size=10.5, anchor="middle", color="muted"))
    b.append(arrow(733, 204, 733, 260, u))
    b.append(text(727, 236, "1–2 calls", size=10, anchor="end"))
    b.append(arrow(827, 204, 827, 260, u))
    b.append(text(821, 236, "in-process", size=10, anchor="end"))

    # the one edge that removes Node from the judge's machine
    b.append(
        f'<path d="M220,320 H251 V372 H549 V323" fill="none" style="stroke:{c("accent")}" '
        f'stroke-width="1.8" marker-end="url(#{u}-arrow)"/>'
    )
    b.append(text(420, 388, "dist/ ships in the repo, so the judge needs no Node", size=11,
                  anchor="middle", color="accent", weight=500))
    label = (
        "Team machine builds the front end once and commits it; the judge's laptop runs one "
        "FastAPI process serving the page, the Gradio fallback and the agent stream, plus Ollama."
    )
    return _wrap(900, 404, label, "".join(b), standalone, u)


# ---------------------------------------------------------------- figure 2: footprint

FOOTPRINT = [
    # label, MB, packages, note, highlighted
    ("SPA only, no Gradio", 9, 56, "FastAPI backend + committed SPA bundle", False),
    ("NiceGUI + Plotly", 31, 83, "pure-Python middle ground", False),
    ("SPA + Gradio (our choice)", 80, 87, "Gradio is the safety net; the SPA adds nothing to pip",
     True),
    ("Streamlit", 85, 35, "alone, without our backend", False),
    ("Open WebUI", 604, 245, "includes torch; Python < 3.13 only", False),
]


def footprint_figure(standalone=False):
    """Horizontal bars: pip download size per UI option, our choice highlighted."""
    _MODE["standalone"] = standalone
    u = "f2"
    x0, span, top, step, bar_h = 248, 390, 44, 36, 18
    scale = span / max(mb for _, mb, *_ in FOOTPRINT)
    b = [text(0, 18, "pip download size on Windows, Python 3.12 wheels", size=12, color="muted")]
    for i, (label, mb, pkgs, note, pick) in enumerate(FOOTPRINT):
        cy = top + i * step
        y = cy - bar_h / 2
        w = mb * scale
        r = min(4, w / 2)
        path = (
            f"M{x0},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{bar_h - 2 * r} "
            f"a{r},{r} 0 0 1 -{r},{r} h-{w - r:.1f} z"
        )
        fill = c("bar-pick") if pick else c("bar-ctx")
        tip = f"{label}: {mb} MB, {pkgs} packages. {note}."
        b.append(
            f'<g class="bar" tabindex="0" data-tip="{escape(tip)}">'
            f'<rect x="0" y="{cy - step / 2:.1f}" width="800" height="{step}" fill="transparent"/>'
            f'<path d="{path}" style="fill:{fill}"/>'
            + text(x0 - 12, cy + 4, label, size=12, anchor="end", weight=600 if pick else None)
            + text(x0 + w + 8, cy + 4, f"{mb} MB", size=12, weight=600)
            + text(x0 + w + 8 + 7.6 * len(f"{mb} MB") + 6, cy + 4, f"· {pkgs} packages", size=11,
                   color="muted")
            + "</g>"
        )
    b.append(
        f'<line x1="{x0}" y1="{top - 22}" x2="{x0}" y2="{top + 4 * step + 20}" '
        f'stroke="{ink()}" stroke-opacity="0.35"/>'
    )
    label = (
        "Bar chart of pip download size: SPA only 9 MB, NiceGUI 31 MB, SPA plus Gradio (our "
        "choice) 80 MB, Streamlit 85 MB, Open WebUI 604 MB."
    )
    return _wrap(800, 236, label, "".join(b), standalone, u)


def footprint_table_html():
    """Return the footprint data as an HTML table (the chart's table view)."""
    rows = []
    for label, mb, pkgs, note, pick in FOOTPRINT:
        cls = ' class="pick"' if pick else ""
        rows.append(
            f'<tr{cls}><td>{escape(label)}</td><td class="num">{mb}</td>'
            f'<td class="num">{pkgs}</td><td>{escape(note)}</td></tr>'
        )
    rows = "".join(rows)
    return (
        "<table><thead><tr><th>Option</th><th>Download (MB)</th><th>Packages</th><th>Note</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


# ----------------------------------------------------------------- figure 3: wireframe


def wireframe_figure(standalone=False):
    """Wireframe of the planned front door: conversation left, design workspace right."""
    _MODE["standalone"] = standalone
    u = "f3"
    b = [box(0.5, 0.5, 899, 523, fill="surface", rx=12, stroke_opacity=0.3)]
    # header
    b.append(f'<path d="M0.5,48 V12.5 a12,12 0 0 1 12,-12 H887.5 a12,12 0 0 1 12,12 V48 z" '
             f'style="fill:{c("panel")}"/>')
    b.append(text(20, 30, "Geothermal design agent", size=14, weight=700))
    b.append(box(500, 12, 160, 24, fill="surface", rx=12, stroke_opacity=0.35))
    b.append(text(514, 28, "model: local CPU  ▾", size=11, mono=True))
    b.append(box(670, 12, 118, 24, fill="surface", rx=12, stroke_opacity=0.35))
    b.append(text(684, 28, "tokens · time", size=11, mono=True))
    b.append(box(798, 12, 90, 24, fill="surface", rx=12, stroke="good"))
    b.append(text(810, 28, "✓ verified", size=11, color="good", weight=600))
    b.append(f'<line x1="0.5" y1="48" x2="899.5" y2="48" stroke="{ink()}" '
             'stroke-opacity="0.2"/>')

    # left: conversation
    b.append(box(196, 62, 228, 32, fill="accent-wash", rx=10, stroke_opacity=0))
    b.append(text(210, 82, "Design heating + cooling here", size=12))
    b.append(box(16, 106, 408, 118, fill="surface", rx=8, stroke="warn"))
    b.append(f'<circle cx="34" cy="126" r="8" style="fill:none;stroke:{c("warn")}" '
             f'stroke-width="1.6"/>')
    b.append(text(34, 130, "!", size=11, anchor="middle", color="warn", weight=700))
    b.append(text(50, 130, "2 inputs missing", size=12.5, weight=600))
    for y, label, val in [
        (156, "District heating supply / return", "70/40 °C"),
        (178, "District cooling supply / return", "6/12 °C"),
    ]:
        b.append(text(34, y, label, size=11.5))
        b.append(text(404, y, f"{val} default", size=11, anchor="end", mono=True, color="muted"))
    b.append(box(34, 192, 112, 22, fill="accent", rx=6, stroke_opacity=0))
    b.append(f'<text x="90" y="207" font-size="11" font-family="{SANS}" text-anchor="middle" '
             f'font-weight="600" class="s" style="fill:{c("surface")}">Accept defaults</text>')
    b.append(box(154, 192, 48, 22, fill="surface", rx=6, stroke_opacity=0.4))
    b.append(text(178, 207, "Edit", size=11, anchor="middle"))

    for i, (call, state) in enumerate([
        ("solve_doublet(depth_m=2500)", "✓"),
        ("annual_simulation(hours=8760)", "✓"),
        ("verify_design()", "all checks ✓"),
    ]):
        y = 238 + i * 38
        b.append(box(16, y, 408, 30, fill="code-bg", rx=6, stroke_opacity=0))
        b.append(text(30, y + 19, f"▸ {call}", size=11, mono=True))
        b.append(text(410, y + 19, state, size=11, anchor="end", color="good", weight=600))

    for y, w in [(364, 340), (384, 384), (404, 300), (424, 196)]:
        b.append(f'<rect x="16" y="{y}" width="{w}" height="9" rx="4.5" '
                 f'style="fill:{c("line")}"/>')
    b.append(box(362, 360, 30, 17, fill="surface", rx=4, stroke="accent"))
    b.append(text(377, 373, "[1]", size=10, anchor="middle", mono=True, color="accent"))

    b.append(box(16, 466, 408, 42, fill="surface", rx=8, stroke_opacity=0.35))
    b.append(text(30, 492, "Ask a what-if question…", size=12, color="muted"))
    b.append(f'<circle cx="400" cy="487" r="12" style="fill:{c("accent")}"/>')
    b.append(f'<path d="M395,487 h9 m-4,-4 l4,4 l-4,4" fill="none" '
             f'style="stroke:{c("surface")}" stroke-width="1.6"/>')

    # right: workspace tabs
    for x, label in [(452, "Schematic"), (536, "Energy"), (600, "KPIs"), (652, "Alternatives"),
                     (752, "Trace")]:
        active = label == "Schematic"
        b.append(text(x, 80, label, size=12, weight=600 if active else None,
                      color=None if active else "muted"))
    b.append(f'<rect x="452" y="88" width="62" height="3" rx="1.5" style="fill:{c("accent")}"/>')
    b.append(f'<line x1="444" y1="92" x2="884" y2="92" stroke="{ink()}" '
             'stroke-opacity="0.2"/>')

    # schematic canvas: brine cascade and the two networks
    b.append(box(444, 104, 440, 240, fill="bg", rx=8, stroke_opacity=0.2))
    nodes = [(454, "Producer"), (540, "Absorption"), (626, "DH HEX"), (712, "Heat pump"),
             (798, "Injector")]
    for x, label in nodes:
        heat_end = label in ("Producer", "Injector")
        b.append(box(x, 140, 66, 30, fill="surface", rx=5,
                     stroke="heat" if heat_end else None, stroke_opacity=0.45))
        b.append(text(x + 33, 159, label, size=10.5, anchor="middle"))
    for (x1, _), (x2, _) in zip(nodes, nodes[1:]):
        b.append(arrow(x1 + 66, 155, x2 - 2, 155, u, color="heat"))
    b.append(text(454, 128, "brine, hot → cold", size=10, color="heat"))
    b.append(box(500, 248, 116, 30, fill="surface", rx=5, stroke="cold"))
    b.append(text(558, 267, "DC network", size=10.5, anchor="middle"))
    b.append(text(558, 296, "6/12 °C", size=10, anchor="middle", mono=True, color="muted"))
    b.append(box(660, 248, 116, 30, fill="surface", rx=5, stroke="heat"))
    b.append(text(718, 267, "DH network", size=10.5, anchor="middle"))
    b.append(text(718, 296, "70/40 °C", size=10, anchor="middle", mono=True, color="muted"))
    b.append(arrow(573, 170, 560, 246, u, color="cold"))
    b.append(text(552, 214, "cold", size=10, anchor="end", color="cold"))
    b.append(arrow(659, 170, 700, 246, u, color="heat"))
    b.append(arrow(745, 170, 730, 246, u, color="heat"))
    b.append(text(750, 214, "heat", size=10, color="heat"))

    # KPI strip (placeholders)
    for i, (label, unit) in enumerate([("Heat coverage", "%"), ("Cold coverage", "%"),
                                       ("LCOH", "€/MWh"), ("CO₂ saving", "%")]):
        x = 444 + i * 112
        b.append(box(x, 356, 104, 72, fill="surface", rx=8, stroke_opacity=0.25))
        b.append(text(x + 12, 378, label, size=10.5, color="muted"))
        b.append(text(x + 12, 410, f"— {unit}", size=17, weight=600))
    b.append(text(444, 452, "Every number links to the tool call that produced it.", size=11,
                  color="muted"))
    label = (
        "Wireframe of the planned UI: header with model, token meter and verified badge; "
        "conversation with a clarification card and tool-call rows on the left; design "
        "workspace with a plant schematic and KPI tiles on the right."
    )
    return _wrap(900, 524, label, "".join(b), standalone, u)


FIGURES = {
    "img/adr-0003-runtime.svg": runtime_figure,
    "img/adr-0003-footprint.svg": footprint_figure,
    "img/adr-0003-wireframe.svg": wireframe_figure,
}
