"""Design tokens, global CSS and the Plotly templates, for light and dark mode.

All styling lives here so the look of the app can be changed in one place.

How dark mode works:

* ``.streamlit/config.toml`` defines ``[theme.light]`` and ``[theme.dark]``.
  Streamlit follows the visitor's system setting and offers a switch in the
  app menu, and it sets ``color-scheme`` on the app container.
* Every custom color in the CSS below is a token defined once with CSS
  ``light-dark()``, so cards, badges and tables switch instantly with no Python.
* Plotly figures are drawn in Python, so :func:`chart_tokens` picks the light
  or dark chart colors from ``st.context.theme`` each time a page is drawn.

Call :func:`apply_theme` once per script run from ``app.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

PRIMARY = "#0D9488"
FONT_STACK = "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

# Categorical palettes: same hue order in both modes so a category keeps its color.
# Both are validated for lightness band, chroma, CVD separation and contrast.
PALETTE_LIGHT = ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#0EA5E9", "#84CC16", "#8B5CF6", "#F97316"]
PALETTE_DARK = ["#0D9488", "#6366F1", "#D97706", "#DB2777", "#0284C7", "#65A30D", "#7C3AED", "#EA580C"]
PALETTE = PALETTE_LIGHT  # used by static exports (white paper)


@dataclass(frozen=True)
class ChartTokens:
    """Colors a Plotly figure needs for one mode."""

    mode: str
    template: str
    primary: str
    muted: str
    grid: str
    axis_line: str
    surface: str
    fill: str
    box_fill: str
    negative: str
    palette: tuple[str, ...]
    diverging: tuple[tuple[float, str], ...]


LIGHT = ChartTokens(
    mode="light",
    template="veridash",
    primary=PRIMARY,
    muted="#64748B",
    grid="#F1F5F9",
    axis_line="#E2E8F0",
    surface="#FFFFFF",
    fill="rgba(13,148,136,0.08)",
    box_fill="rgba(13,148,136,0.18)",
    negative="#DC2626",
    palette=tuple(PALETTE_LIGHT),
    diverging=((0.0, "#4F46E5"), (0.5, "#F1F5F9"), (1.0, "#0D9488")),
)
DARK = ChartTokens(
    mode="dark",
    template="veridash_dark",
    primary="#14B8A6",
    muted="#94A3B8",
    grid="#1E293B",
    axis_line="#334155",
    surface="#111A2C",
    fill="rgba(20,184,166,0.12)",
    box_fill="rgba(20,184,166,0.22)",
    negative="#F87171",
    palette=tuple(PALETTE_DARK),
    diverging=((0.0, "#6366F1"), (0.5, "#1E293B"), (1.0, "#14B8A6")),
)


def theme_mode() -> str:
    """``"dark"`` or ``"light"`` for the current visitor (light if unknown)."""
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # outside a Streamlit run (tests, exports)
        return "light"


def chart_tokens() -> ChartTokens:
    """Chart colors for the current mode."""
    return DARK if theme_mode() == "dark" else LIGHT


def _template(tk: ChartTokens, text: str, hover_bg: str) -> go.layout.Template:
    axis = {
        "showgrid": False,
        "zeroline": False,
        "linecolor": tk.axis_line,
        "ticks": "",
        "tickfont": {"color": tk.muted, "size": 12},
        "ticklabelstandoff": 6,
        "title": {"font": {"color": tk.muted, "size": 12}},
        "automargin": True,
    }
    return go.layout.Template(
        layout={
            "font": {"family": FONT_STACK, "size": 13, "color": text},
            "colorway": list(tk.palette),
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": axis,
            "yaxis": {**axis, "showgrid": True, "gridcolor": tk.grid, "linecolor": "rgba(0,0,0,0)"},
            "hoverlabel": {
                "bgcolor": hover_bg,
                "bordercolor": tk.axis_line,
                "font": {"family": FONT_STACK, "color": text, "size": 13},
            },
            "hovermode": "closest",
            "margin": {"l": 8, "r": 8, "t": 16, "b": 8},
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "font": {"color": tk.muted, "size": 12},
                "title": {"text": ""},
            },
            "bargap": 0.28,
            "colorscale": {"diverging": [list(s) for s in tk.diverging]},
        },
        data={
            "bar": [go.Bar(marker={"line": {"width": 0}, "cornerradius": 4})],
            "scatter": [go.Scatter(line={"width": 2})],
        },
    )


def _register_plotly_templates() -> None:
    pio.templates["veridash"] = _template(LIGHT, "#0F172A", "#FFFFFF")
    pio.templates["veridash_dark"] = _template(DARK, "#E2E8F0", "#1E293B")
    pio.templates.default = "veridash"


_register_plotly_templates()


# Each token is defined once; light-dark() picks the value for the active mode.
_CSS = """
<style>
:root {
  --vd-primary: #0D9488;
  --vd-text: light-dark(#10213A, #E4EAF2);
  --vd-muted: light-dark(#64748B, #94A3B8);
  --vd-faint: light-dark(#CBD5E1, #334155);
  --vd-border: light-dark(#DCE4EC, #22304A);
  --vd-divider: light-dark(#F1F5F9, #1A2438);
  --vd-surface: light-dark(#FFFFFF, #111A2C);
  --vd-subtle: light-dark(#F7FAFC, #131D30);
  --vd-accent: light-dark(#0F766E, #5EEAD4);
  --vd-tint: light-dark(#F0FDFA, rgba(20, 184, 166, 0.12));
  --vd-tint-border: light-dark(#CCFBF1, rgba(45, 212, 191, 0.28));
  --vd-shadow-color: light-dark(rgba(16, 33, 58, 0.07), rgba(0, 0, 0, 0.35));
  --vd-page: light-dark(#F5F8FA, #0A1322);
  --vd-ink: #0B1B33;
  --vd-indigo: light-dark(#4F46E5, #818CF8);
  --vd-chip: light-dark(#F1F5F9, #1E293B);
  --vd-ok: light-dark(#15803D, #4ADE80);
  --vd-bad-bg: light-dark(#FEE2E2, rgba(239, 68, 68, 0.22));
  --vd-warn-bg: light-dark(#FFFBEB, rgba(245, 158, 11, 0.10));
  --vd-error-bg: light-dark(#FEF2F2, rgba(239, 68, 68, 0.10));
  --vd-radius: 12px;
  --vd-display: 'Bricolage Grotesque', 'IBM Plex Sans', sans-serif;
  --vd-body: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --vd-mist: light-dark(#F2F6F8, #0F1A2C);
  --vd-red-pen: light-dark(#C8281E, #FF7A6E);
  --vd-shadow: 0 1px 2px var(--vd-shadow-color), 0 10px 28px -18px light-dark(rgba(16, 33, 58, 0.28), rgba(0, 0, 0, 0.6));
}
html, body { font-family: var(--vd-body); }
/* The page: a cool off-white with two soft glows at the top, so white cards have depth */
.stApp { background:
  radial-gradient(1100px 520px at 88% -8%, light-dark(rgba(13, 148, 136, 0.10), rgba(20, 184, 166, 0.10)), transparent 62%),
  radial-gradient(900px 460px at -6% 2%, light-dark(rgba(79, 70, 229, 0.06), rgba(99, 102, 241, 0.08)), transparent 60%),
  var(--vd-page) !important; }
/* A frosted top bar that stays readable over the content as you scroll */
header[data-testid="stHeader"] { background: color-mix(in srgb, var(--vd-page) 78%, transparent) !important;
  backdrop-filter: saturate(160%) blur(12px); -webkit-backdrop-filter: saturate(160%) blur(12px);
  border-bottom: 1px solid color-mix(in srgb, var(--vd-border) 70%, transparent); }
h1, h2, h3, h4, .vd-hero h1, .vd-section h2, .vd-chart-title, .vd-kpi .value, .vd-wordmark {
  font-family: var(--vd-display); font-optical-sizing: auto; }
.stApp { font-variant-numeric: tabular-nums; }
.block-container { max-width: 1200px; padding-top: 4.75rem; padding-bottom: 4rem; }
footer, [data-testid="stAppDeployButton"], [data-testid="stStatusWidget"] { display: none !important; }
h1, h2, h3 { letter-spacing: -0.02em; }
a { color: var(--vd-accent); }

/* Keyed containers named card_* act as cards */
div[class*="st-key-card"] {
  background: var(--vd-surface); border: 1px solid var(--vd-border); border-radius: var(--vd-radius);
  padding: 20px 22px; box-shadow: var(--vd-shadow);
}
/* Cards in a row: card-eq* share the row's height; card-eqb* also pin the last element
   (usually a button) to the bottom so buttons line up. */
[data-testid="stHorizontalBlock"]:has(div[class*="st-key-card-eq"]) { align-items: stretch; }
[data-testid="stColumn"]:has(div[class*="st-key-card-eq"]) > [data-testid="stVerticalBlock"] { height: 100%; }
[data-testid="stLayoutWrapper"]:has(> div[class*="st-key-card-eq"]) { flex: 1 1 auto; }
div[class*="st-key-card-eq"] { flex: 1 1 auto; align-self: stretch; box-sizing: border-box; }
div[class*="st-key-card-eqb"] > :last-child { margin-top: auto; }

/* Tabs (Streamlit 1.6x builds them with react-aria: role="tablist" and data-testid="stTab") */
.stTabs [role="tablist"] { gap: 20px; border-bottom: 1px solid var(--vd-border); }
.stTabs [data-testid="stTab"] { padding: 10px 2px; }
.stTabs [data-testid="stTab"] p { font-weight: 600; color: var(--vd-muted); }
.stTabs [data-testid="stTab"][aria-selected="true"] p { color: var(--vd-text); }
.stTabs [data-testid="stTab"]:hover p { color: var(--vd-text); }

/* Code blocks (SQL) */
[data-testid="stCode"] pre { border: 1px solid var(--vd-border); border-radius: 10px; }

/* Wordmark */
.vd-wordmark { display: inline-flex; align-items: center; gap: 10px; font-weight: 800;
  font-size: 20px; color: var(--vd-text); letter-spacing: -0.02em; }

/* Home hero: left-aligned headline beside the auditor's worksheet */
.vd-hero { padding: 8px 0 18px 0; text-align: left; }
.vd-hero h1 { font-size: clamp(38px, 4.5vw, 60px); line-height: 1.0; font-weight: 800; letter-spacing: -0.045em;
  margin: 0 0 18px 0; padding: 0; color: var(--vd-text); }
.vd-hero p { font-size: clamp(16px, 1.6vw, 18.5px); color: var(--vd-muted); max-width: 34em; margin: 0; line-height: 1.6; }
.vd-trust { display: flex; flex-wrap: wrap; gap: 6px 20px; margin-top: 14px; color: var(--vd-muted); font-size: 14px; }
.vd-trust span::before { content: "✓"; color: var(--vd-primary); font-weight: 700; margin-right: 6px; }

/* Home hero band: deep navy with a faint ledger grid and two soft glows; the worksheet is the paper on it */
div[class*="st-key-vd_hero_band"] { position: relative; overflow: hidden; border-radius: 24px; padding: 40px 44px 30px;
  background:
    radial-gradient(640px 340px at 88% 0%, rgba(20, 184, 166, 0.30), transparent 62%),
    radial-gradient(560px 300px at 0% 100%, rgba(99, 102, 241, 0.22), transparent 60%),
    linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px) 0 0 / 34px 34px,
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px) 0 0 / 34px 34px,
    light-dark(#0B1B33, #0E1E38);
  border: 1px solid light-dark(transparent, rgba(255, 255, 255, 0.07));
  box-shadow: 0 40px 70px -46px light-dark(rgba(11, 27, 51, 0.75), rgba(0, 0, 0, 0.9)); }
div[class*="st-key-vd_hero_band"] .vd-hero h1 { color: #FFFFFF; }
div[class*="st-key-vd_hero_band"] .vd-hero p { color: rgba(226, 234, 242, 0.78); }
div[class*="st-key-vd_hero_band"] .vd-trust { color: rgba(226, 234, 242, 0.72); }
div[class*="st-key-vd_hero_band"] .vd-trust span::before { color: #5EEAD4; }
div[class*="st-key-vd_hero_band"] [data-testid="stWidgetLabel"] p,
div[class*="st-key-vd_hero_band"] [data-testid="stCaptionContainer"],
div[class*="st-key-vd_hero_band"] [data-testid="stCaptionContainer"] p { color: rgba(226, 234, 242, 0.78); }
div[class*="st-key-vd_hero_band"] [data-testid="stTooltipIcon"] button,
div[class*="st-key-vd_hero_band"] [data-testid="stTooltipIcon"] svg { color: rgba(226, 234, 242, 0.7) !important;
  stroke: rgba(226, 234, 242, 0.7) !important; }
div[class*="st-key-vd_hero_band"] [data-testid="stCaptionContainer"] { opacity: 1; }
div[class*="st-key-vd_hero_band"] .vd-hero h1 { font-size: clamp(36px, 4.1vw, 54px); }
div[class*="st-key-vd_hero_band"] .stButton button[kind="secondary"] { background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.22); color: #FFFFFF; }
div[class*="st-key-vd_hero_band"] .stButton button[kind="secondary"]:hover { background: rgba(255, 255, 255, 0.12);
  border-color: rgba(94, 234, 212, 0.6); color: #FFFFFF; }
div[class*="st-key-vd_hero_band"] .stButton button[kind="primary"] { box-shadow: 0 10px 26px -10px rgba(20, 184, 166, 0.8); }
div[class*="st-key-vd_hero_band"] .vd-sheet { border-color: light-dark(#CFE3DC, rgba(94, 234, 212, 0.25));
  box-shadow: 0 28px 50px -24px rgba(0, 0, 0, 0.55); }

/* The worksheet: ruled paper with a red margin line, green ticks and red-pen circles */
.vd-sheet { position: relative; margin: 0 0 10px 0; padding: 18px 22px 16px 46px; border-radius: 4px 4px 16px 4px;
  border: 1px solid light-dark(#CFE3DC, #24413D);
  background-color: light-dark(#F5FAF8, #0F1E22);
  background-image: repeating-linear-gradient(to bottom, transparent 0 35px, light-dark(#DCEBE5, #1C3236) 35px 36px);
  background-position: 0 6px; box-shadow: 0 18px 40px -26px light-dark(rgba(16, 33, 58, 0.35), rgba(0, 0, 0, 0.7)); }
.vd-sheet::before { content: ""; position: absolute; left: 30px; top: 0; bottom: 0; width: 1.5px;
  background: var(--vd-red-pen); opacity: 0.45; }
.vd-sheet figcaption { font-size: 13px; color: var(--vd-muted); line-height: 36px; margin: -6px 0 0 0; }
.vd-sheet .line { font-size: clamp(17px, 1.7vw, 20px); line-height: 36px; color: var(--vd-text); margin: 0; }
.vd-sheet .ok { white-space: nowrap; font-weight: 600; }
.vd-sheet .tk { width: 1.05em; height: 1.05em; vertical-align: -0.05em; margin-left: 2px; fill: none;
  stroke: var(--vd-primary); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
.vd-sheet .bad { position: relative; white-space: nowrap; font-weight: 600; color: var(--vd-red-pen); padding: 0 3px;
  margin: 0 5px; }
.vd-sheet .bad::after { content: ""; position: absolute; inset: 2px -4px; border: 2px solid var(--vd-red-pen);
  border-radius: 50% 46% 52% 44% / 58% 50% 54% 46%; transform: rotate(-3deg); pointer-events: none; }
.vd-sheet .notes { list-style: none; margin: 0 !important; padding: 0 !important; }
.vd-sheet .notes li { font-size: 14.5px; line-height: 36px; color: var(--vd-red-pen); margin: 0 !important; }
.vd-sheet .notes li::before { content: "✗ "; font-weight: 700; }
/* One orchestrated moment: ticks draw in, the red circle lands, the note follows */
.vd-sheet .tk path { stroke-dasharray: 24; stroke-dashoffset: 24;
  animation: vd-draw 0.42s ease-out forwards; animation-delay: calc(var(--i, 0) * 0.32s + 0.25s); }
.vd-sheet .bad::after { opacity: 0; animation: vd-ring 0.45s cubic-bezier(.2, .9, .3, 1.2) forwards;
  animation-delay: calc(var(--i, 0) * 0.32s + 0.25s); }
.vd-sheet .notes li { opacity: 0; animation: vd-rise 0.4s ease-out forwards;
  animation-delay: calc(var(--i, 0) * 0.32s + 0.35s); }
@keyframes vd-draw { to { stroke-dashoffset: 0; } }
@keyframes vd-ring { from { opacity: 0; transform: rotate(-9deg) scale(1.35); }
  to { opacity: 1; transform: rotate(-3deg) scale(1); } }
@keyframes vd-rise { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) {
  .vd-sheet .tk path { animation: none; stroke-dashoffset: 0; }
  .vd-sheet .bad::after { animation: none; opacity: 1; }
  .vd-sheet .notes li { animation: none; opacity: 1; }
}
.vd-sheet .tally { font-size: 14px; line-height: 36px; color: var(--vd-muted); margin: 0; }

/* Analyze start screen */
.vd-gets-title { font-weight: 600; font-size: 14.5px; color: var(--vd-text); margin: 14px 0 6px 0; }
.vd-gets { list-style: none; margin: 0 !important; padding: 0 !important; }
.vd-gets li { display: flex; align-items: center; gap: 12px; margin: 0 !important; padding: 7px 0;
  font-size: 14.5px; color: var(--vd-muted); }
.vd-gets .vd-icon, .vd-exrow .vd-icon { width: 32px; height: 32px; border-radius: 8px; flex: none; }
div[class*="st-key-card_exrow"] { padding: 14px 16px; margin-bottom: 2px; }
.vd-exrow { display: flex; gap: 12px; align-items: center; }
.vd-exrow b { display: block; font-size: 15.5px; color: var(--vd-text); }
.vd-exrow span:not(.vd-icon) { display: block; font-size: 13.5px; color: var(--vd-muted); line-height: 1.4; }
.vd-spark { display: block; width: 100%; height: 34px; margin-top: 8px; }
.vd-spark .l { fill: none; stroke: var(--vd-primary); stroke-width: 1.8; stroke-linejoin: round;
  vector-effect: non-scaling-stroke; }
.vd-spark .a { fill: var(--vd-tint); }
.vd-spark .d { fill: var(--vd-primary); }

.vd-exhead { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.vd-exhead .vd-icon { flex: none; }
.vd-exhead + .vd-spark { height: 46px; }

/* Overview: the start-here guide */
div[class*="st-key-card_start_here"] { padding: 12px 14px 12px 18px; background: var(--vd-subtle); box-shadow: none; }
.vd-start { counter-reset: step; list-style: none; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px 22px; margin: 0 !important; padding: 0 !important; }
.vd-start li { counter-increment: step; margin: 0 !important; padding: 0 !important; font-size: 13.5px;
  color: var(--vd-muted); line-height: 1.45; }
.vd-start b { display: flex; align-items: center; gap: 8px; color: var(--vd-text); font-size: 14.5px; margin-bottom: 2px; }
.vd-start b::before { content: counter(step); display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; border-radius: 50%; background: var(--vd-primary); color: #fff; font-size: 12px; }

/* Guide: jump links */
.vd-jump { display: flex; flex-wrap: wrap; gap: 8px; margin: -6px 0 18px 0; }
.vd-jump a { font-size: 14px; color: var(--vd-text); text-decoration: none; padding: 6px 12px; border-radius: 999px;
  border: 1px solid var(--vd-border); background: var(--vd-surface); }
.vd-jump a:hover { border-color: var(--vd-primary); color: var(--vd-accent); }

/* Compare start screen picture */
.vd-diffpic { display: block; width: 100%; max-width: 360px; height: auto; margin: 4px 0 6px 0; }
.vd-diffpic .sheet > rect:first-child { fill: var(--vd-surface); stroke: var(--vd-border); stroke-width: 1.5; }
.vd-diffpic .row { fill: var(--vd-chip); }
.vd-diffpic .row.out { fill: light-dark(#FEE2E2, rgba(239, 68, 68, 0.35)); stroke: var(--vd-red-pen); stroke-width: 1; }
.vd-diffpic .row.in { fill: light-dark(#DCFCE7, rgba(34, 197, 94, 0.3)); stroke: var(--vd-primary); stroke-width: 1; }
.vd-diffpic .arrow { fill: none; stroke: var(--vd-muted); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

/* Home: resume banner */
div[class*="st-key-card_resume"] { padding: 10px 16px; background: var(--vd-tint); border-color: var(--vd-tint-border);
  box-shadow: none; }
.vd-resume { margin: 0; font-size: 15px; color: var(--vd-text); }

/* Home tour: a framed screen beside its description */
.vd-shot { border-radius: 14px; border: 1px solid var(--vd-border); overflow: hidden; background: var(--vd-surface);
  box-shadow: 0 28px 56px -34px light-dark(rgba(16, 33, 58, 0.5), rgba(0, 0, 0, 0.8)); }
.vd-shot img { display: block; width: 100%; height: auto;
  -webkit-mask-image: linear-gradient(to bottom, #000 80%, transparent 100%);
  mask-image: linear-gradient(to bottom, #000 80%, transparent 100%); }
.vd-tour h3 { font-size: clamp(22px, 2.4vw, 28px); font-weight: 700; letter-spacing: -0.02em; line-height: 1.2;
  margin: 0 0 10px 0; padding: 0; color: var(--vd-text); }
.vd-tour p { font-size: 16px; line-height: 1.6; color: var(--vd-muted); margin: 0 0 18px 0; max-width: 30em; }

/* Feedback that answers an action: the tour's new screen fades in, buttons press in slightly */
.vd-shot, .vd-tour { animation: vd-swap 0.32s ease-out; }
@keyframes vd-swap { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.stButton button, .stDownloadButton button { transition: transform 0.08s ease, box-shadow 0.15s ease; }
.stButton button:active, .stDownloadButton button:active { transform: translateY(1px) scale(0.985); }
.stButton button[kind="primary"]:hover, .stDownloadButton button[kind="primary"]:hover {
  box-shadow: 0 6px 16px -8px rgba(13, 148, 136, 0.55); }
@media (prefers-reduced-motion: reduce) {
  .vd-shot, .vd-tour { animation: none; }
  .stButton button:active, .stDownloadButton button:active { transform: none; }
}

/* Section header */
.vd-section { margin: 52px 0 20px 0; }
.vd-section.top { margin-top: 0; }
.vd-section .vd-kicker { font-size: 14px; font-weight: 600;
  color: var(--vd-accent); margin-bottom: 6px; }
.vd-section h2 { font-size: clamp(26px, 3.2vw, 34px); font-weight: 700; letter-spacing: -0.025em; line-height: 1.15;
  margin: 0 0 8px 0; padding: 0; }
.vd-section p { color: var(--vd-muted); margin: 0; font-size: 16px; max-width: 720px; }
.vd-section.center { text-align: center; }
.vd-section.center p { margin: 0 auto; }
.vd-section.compact { margin: 8px 0 18px 0; }

/* Cards */
.vd-card { background: var(--vd-surface); border: 1px solid var(--vd-border); border-radius: var(--vd-radius);
  padding: 20px 22px; box-shadow: var(--vd-shadow); height: 100%; }
.vd-card h4 { margin: 12px 0 6px 0; font-size: 16px; font-weight: 700; padding: 0; color: var(--vd-text); }
.vd-card p { margin: 0; color: var(--vd-muted); font-size: 14.5px; line-height: 1.55; }
.vd-icon { width: 40px; height: 40px; border-radius: 10px; background: var(--vd-tint);
  color: var(--vd-primary); display: inline-flex; align-items: center; justify-content: center; }

/* KPI card */
.vd-kpi { background: var(--vd-surface); border: 1px solid var(--vd-border); border-radius: var(--vd-radius);
  padding: 16px 18px; box-shadow: var(--vd-shadow); height: 100%; min-height: 124px; }
.vd-kpi .label { font-size: 13.5px; font-weight: 500; color: var(--vd-muted); }
.vd-kpi .value { font-size: 28px; font-weight: 700; color: var(--vd-text); margin-top: 6px;
  letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.vd-kpi .sub { font-size: 13px; color: var(--vd-muted); margin-top: 4px; }

/* Badges */
.vd-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 999px; border: 1px solid transparent; white-space: nowrap; line-height: 1.6; }
.vd-badge.teal { background: light-dark(#F0FDFA, rgba(20,184,166,0.14)); color: light-dark(#0F766E, #5EEAD4); border-color: light-dark(#99F6E4, rgba(45,212,191,0.32)); }
.vd-badge.indigo { background: light-dark(#EEF2FF, rgba(99,102,241,0.16)); color: light-dark(#4338CA, #A5B4FC); border-color: light-dark(#C7D2FE, rgba(129,140,248,0.34)); }
.vd-badge.slate { background: light-dark(#F8FAFC, rgba(148,163,184,0.10)); color: light-dark(#475569, #CBD5E1); border-color: light-dark(#E2E8F0, rgba(148,163,184,0.26)); }
.vd-badge.amber { background: light-dark(#FFFBEB, rgba(245,158,11,0.14)); color: light-dark(#B45309, #FCD34D); border-color: light-dark(#FDE68A, rgba(245,158,11,0.32)); }
.vd-badge.red { background: light-dark(#FEF2F2, rgba(239,68,68,0.14)); color: light-dark(#B91C1C, #FCA5A5); border-color: light-dark(#FECACA, rgba(239,68,68,0.32)); }
.vd-badge.green { background: light-dark(#F0FDF4, rgba(34,197,94,0.14)); color: light-dark(#15803D, #86EFAC); border-color: light-dark(#BBF7D0, rgba(34,197,94,0.32)); }
.vd-badge.violet { background: light-dark(#F5F3FF, rgba(139,92,246,0.16)); color: light-dark(#6D28D9, #C4B5FD); border-color: light-dark(#DDD6FE, rgba(167,139,250,0.34)); }
.vd-badge.sky { background: light-dark(#F0F9FF, rgba(14,165,233,0.14)); color: light-dark(#0369A1, #7DD3FC); border-color: light-dark(#BAE6FD, rgba(56,189,248,0.32)); }
.vd-badges { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 4px 0 12px 0; }

/* Callout */
.vd-callout { border: 1px solid var(--vd-border); border-left: 4px solid var(--vd-primary);
  background: var(--vd-subtle); border-radius: 10px; padding: 14px 16px; font-size: 14.5px;
  color: var(--vd-text); line-height: 1.55; margin: 8px 0 16px 0; }
.vd-callout.warn { border-left-color: #F59E0B; background: var(--vd-warn-bg); }
.vd-callout.error { border-left-color: #EF4444; background: var(--vd-error-bg); }
.vd-callout .title { font-weight: 700; margin-bottom: 2px; }

/* Step card */
.vd-step { position: relative; }
.vd-step .num { position: absolute; top: 18px; right: 20px; font-size: 13px; font-weight: 700; color: var(--vd-faint); }

/* Chart card text */
.vd-chart-title { font-size: 17px; font-weight: 650; letter-spacing: -0.01em; color: var(--vd-text); margin: 0; }
.vd-chart-insight { font-size: 14px; color: var(--vd-muted); margin: 4px 0 4px 0; line-height: 1.5; }

/* File bar on Analyze */
.vd-filebar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.vd-filebar .name { font-weight: 700; font-size: 16px; color: var(--vd-text); }

/* Health score */
.vd-score { display: flex; align-items: center; gap: 18px; }
.vd-score .ring { width: 92px; height: 92px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; flex: none; }
.vd-score .inner { width: 76px; height: 76px; border-radius: 50%; background: var(--vd-surface); display: flex;
  flex-direction: column; align-items: center; justify-content: center; }
.vd-score .n { font-size: 28px; font-weight: 800; letter-spacing: -0.02em; }
.vd-score .g { font-size: 12px; font-weight: 700; color: var(--vd-muted); }
.vd-score .title { font-weight: 700; font-size: 18px; color: var(--vd-text); }
.vd-score .meta { color: var(--vd-muted); font-size: 14px; }

/* Issue rows */
.vd-issue { display: grid; grid-template-columns: 84px 1fr; gap: 12px; padding: 12px 0;
  border-top: 1px solid var(--vd-border); }
.vd-issue:first-child { border-top: none; }
.vd-issue .t { font-weight: 600; font-size: 14.5px; color: var(--vd-text); }
.vd-issue .d { font-size: 13.5px; color: var(--vd-muted); margin-top: 2px; }
.vd-issue .w { font-size: 13.5px; color: var(--vd-text); margin-top: 4px; }
.vd-fix { margin-top: 6px; font-size: 13.5px; color: var(--vd-text); }
.vd-fix summary { cursor: pointer; color: var(--vd-primary); font-weight: 600; width: fit-content; }
.vd-fix > div { margin-top: 4px; padding-left: 10px; border-left: 2px solid var(--vd-border); }

/* Insight lists */
.vd-insight { padding: 12px 0; border-top: 1px solid var(--vd-border); }
.vd-insight:first-child { border-top: none; }
.vd-insight .txt { font-size: 15px; line-height: 1.6; color: var(--vd-text); }
.vd-insight .meta { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }
.vd-cite { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; color: var(--vd-muted);
  background: var(--vd-chip); border-radius: 6px; padding: 1px 6px; }
.vd-num-ok { text-decoration: underline dotted var(--vd-ok); text-decoration-thickness: 2px; text-underline-offset: 4px; }
.vd-num-bad { background: var(--vd-bad-bg); border-radius: 4px; padding: 0 3px;
  text-decoration: underline wavy #EF4444; text-underline-offset: 3px; }
.vd-rec-h { font-weight: 600; font-size: 15px; line-height: 1.5; color: var(--vd-text); }
.vd-rec-l { font-size: 14px; color: var(--vd-muted); line-height: 1.55; margin-top: 8px; }
.vd-rec-l b { color: var(--vd-text); font-weight: 600; }

/* Tables rendered as HTML (profile, health checks) */
.vd-table-wrap { border: 1px solid var(--vd-border); border-radius: var(--vd-radius); overflow: auto; max-height: 560px; }
table.vd-table { width: 100%; border-collapse: collapse; font-size: 13.5px; color: var(--vd-text); }
table.vd-table td, table.vd-table th { white-space: nowrap; }
table.vd-table td.wrap { white-space: normal; }
table.vd-table th { position: sticky; top: 0; background: var(--vd-subtle); text-align: left; font-weight: 600;
  color: var(--vd-muted); padding: 10px 12px; border-bottom: 1px solid var(--vd-border); }
table.vd-table td { padding: 9px 12px; border-bottom: 1px solid var(--vd-divider); vertical-align: top; }
table.vd-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
/* Tables inside half-width cards (the health checks) wrap instead of hiding columns behind a scroll */
table.vd-table.fit th, table.vd-table.fit td { white-space: normal; padding: 8px 10px; }
table.vd-table.fit td.num { white-space: nowrap; }
table.vd-table.fit .cap { color: var(--vd-muted); }
.vd-table-wrap:has(> table.vd-table.fit) { container-type: inline-size; }
@container (max-width: 330px) { table.vd-table.fit .wcol { display: none; }
  table.vd-table.fit th, table.vd-table.fit td { padding: 8px 7px; } }

/* Author card */
.vd-author { display: flex; gap: 16px; align-items: center; }
.vd-author .n { font-weight: 700; font-size: 18px; color: var(--vd-text); }
.vd-author .r { color: var(--vd-muted); }

/* Footer: brand and links on one row, author credit centered underneath */
div[class*="st-key-vd_footer"] { margin-top: 72px; padding-top: 28px; border-top: 1px solid var(--vd-border); }
.vd-footer-brand p { color: var(--vd-muted); font-size: 14px; line-height: 1.55; margin: 10px 0 0 0; max-width: 26em; }
.vd-footer-h { font-weight: 600; font-size: 14px; color: var(--vd-text); margin: 0 0 6px 0; }
div[class*="st-key-vd_footer"] [data-testid="stPageLink"] a { padding: 4px 0; min-height: 0; background: none; }
div[class*="st-key-vd_footer"] [data-testid="stPageLink"] p { color: var(--vd-muted); font-size: 14px; }
div[class*="st-key-vd_footer"] [data-testid="stPageLink"] a:hover p { color: var(--vd-accent); }
.vd-footer-links { display: flex; flex-direction: column; gap: 7px; margin-top: 6px; }
.vd-footer-links a { color: var(--vd-muted); text-decoration: none; font-size: 14px; }
.vd-footer-links a:hover { color: var(--vd-accent); }
.vd-footer-credit { text-align: center; font-size: 13px; margin-top: 22px; color: var(--vd-muted); }

/* Comparison table (Home) */
.vd-compare { border: 1px solid var(--vd-border); border-radius: var(--vd-radius); overflow: hidden;
  background: var(--vd-surface); box-shadow: var(--vd-shadow); }
.vd-compare table { width: 100%; border-collapse: collapse; font-size: 15px; color: var(--vd-text); }
.vd-compare th, .vd-compare td { padding: 14px 18px; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--vd-divider); line-height: 1.5; }
.vd-compare tr:last-child th, .vd-compare tr:last-child td { border-bottom: none; }
.vd-compare thead th { font-size: 14px; font-weight: 600; color: var(--vd-muted);
  background: var(--vd-subtle); }
.vd-compare tbody th { font-weight: 600; width: 22%; }
.vd-compare td { color: var(--vd-muted); width: 39%; }
.vd-compare .ours { background: var(--vd-tint); color: var(--vd-text); }
.vd-compare thead .ours { color: var(--vd-accent); }
.vd-compare .lbl { display: none; }
.vd-compare td.ours::before { content: "✓"; color: var(--vd-primary); font-weight: 700; margin-right: 8px; }

/* Use case cards */
.vd-usecase .who { font-size: 14px; font-weight: 600;
  color: var(--vd-accent); margin-top: 12px; }
.vd-usecase .q { font-size: 17px; font-weight: 700; line-height: 1.4; color: var(--vd-text); margin: 6px 0 8px 0; }
.vd-usecase ul { margin: 0 0 12px 0; padding-left: 18px; color: var(--vd-muted); font-size: 14.5px; line-height: 1.6; }

/* Benchmark meters: label, bar, count */
.vd-meter { display: grid; grid-template-columns: minmax(150px, 1.2fr) 2fr minmax(92px, auto); gap: 6px 16px;
  align-items: center; padding: 10px 0; border-bottom: 1px solid var(--vd-divider); }
.vd-meter:last-of-type { border-bottom: none; }
.vd-meter .t { font-weight: 600; color: var(--vd-text); font-size: 14.5px; }
.vd-meter .e { color: var(--vd-muted); font-size: 12.5px; margin-top: 1px; }
.vd-meter .bar { height: 10px; border-radius: 999px; background: var(--vd-chip); overflow: hidden; }
.vd-meter .bar > span { display: block; height: 100%; background: var(--vd-primary); border-radius: 999px; }
.vd-meter .bar > span { transform-origin: left center; animation: vd-grow 0.9s cubic-bezier(.2, .8, .2, 1) both; }
@keyframes vd-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@media (prefers-reduced-motion: reduce) { .vd-meter .bar > span { animation: none; } }
.vd-inshort { font-size: 17px; line-height: 1.6; color: var(--vd-text); margin: -4px 0 18px 0; max-width: 46em;
  padding-left: 14px; border-left: 3px solid var(--vd-primary); }
.vd-meter .n { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--vd-text); font-size: 14px;
  text-align: right; }

.vd-checks { list-style: none; padding: 0 !important; margin: 4px 0 8px 0 !important; display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.vd-checks li { display: flex; justify-content: space-between; gap: 10px; padding: 8px 0;
  border-bottom: 1px solid var(--vd-divider); font-size: 14px; color: var(--vd-text); margin: 0 !important; }
.vd-checks li span::before { content: "✓"; color: var(--vd-primary); font-weight: 700; margin-right: 8px; }
.vd-checks li.bad span::before { content: "✗"; color: #EF4444; }
.vd-checks b { font-variant-numeric: tabular-nums; white-space: nowrap; }
.vd-checks.plain { grid-template-columns: 1fr; }
.vd-checks.plain li { align-items: center; }
.vd-checks.plain li span::before { content: none; }

/* Home: the tested note and the four-step timeline */
.vd-tested { font-size: 16.5px; line-height: 1.6; color: var(--vd-muted); margin: 0; max-width: 48em; }
.vd-tested b { color: var(--vd-text); font-family: var(--vd-display); font-size: 18px; margin-right: 4px; }
.vd-steps { position: relative; list-style: none; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 24px; margin: 8px 0 0 0 !important; padding: 0 !important; }
.vd-steps::before { content: ""; position: absolute; top: 19px; left: 20px; right: calc(25% - 38px); height: 2px;
  background: linear-gradient(to right, var(--vd-primary), var(--vd-tint-border)); }
.vd-steps li { position: relative; margin: 0 !important; padding: 0 !important; }
.vd-steps .dot { position: relative; z-index: 1; display: inline-flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 50%; background: var(--vd-surface); border: 2px solid var(--vd-primary);
  color: var(--vd-accent); font-weight: 700; font-family: var(--vd-display); }
.vd-steps h4 { margin: 14px 0 4px 0; padding: 0; font-size: 18px; font-weight: 700; color: var(--vd-text); }
.vd-steps p { margin: 0; color: var(--vd-muted); font-size: 15px; line-height: 1.55; max-width: 18em; }

/* Empty and locked states */
.vd-locked { text-align: center; padding: 36px 20px; border: 1px dashed var(--vd-faint); border-radius: var(--vd-radius);
  background: var(--vd-subtle); }
.vd-locked h4 { margin: 10px 0 6px 0; padding: 0; color: var(--vd-text); }
.vd-locked p { color: var(--vd-muted); margin: 0 auto; max-width: 520px; }

/* Small screens */
/* Accessibility */
.vd-sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.vd-footer-links a:focus-visible, .vd-fix summary:focus-visible, .stApp a:focus-visible {
  outline: 2px solid var(--vd-primary); outline-offset: 2px; border-radius: 4px; }
.stButton button:focus-visible, .stDownloadButton button:focus-visible {
  outline: 2px solid var(--vd-primary); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}

@media (max-width: 640px) {
  div[class*="st-key-vd_hero_band"] { padding: 26px 18px 18px; border-radius: 18px; }
  /* Headline numbers two per row instead of one per screen */
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .vd-kpi) { flex-direction: row !important;
    flex-wrap: wrap !important; gap: 8px !important; }
  [data-testid="stColumn"]:has(.vd-kpi):not(:has([data-testid="stHorizontalBlock"])) {
    flex: 1 1 calc(50% - 4px) !important; width: calc(50% - 4px) !important; min-width: calc(50% - 4px) !important; }
  .vd-kpi { min-height: 0; padding: 12px 14px; }
  .vd-kpi .value { font-size: 22px; }
  /* All six analysis tabs fit on one line: no icons, a little tighter */
  .stTabs [role="tablist"] { gap: 8px; }
  .stTabs [data-testid="stTab"] { padding: 10px 1px; }
  .stTabs [data-testid="stTab"] p > span[role="img"] { display: none !important; }
  .stTabs [data-testid="stTab"] p { font-size: 13px; }
  .block-container { padding-top: 4rem; }
  .vd-hero { padding: 32px 0 24px 0; }
  .vd-issue { grid-template-columns: 1fr; gap: 4px; }
  .vd-compare thead { display: none; }
  .vd-compare table, .vd-compare tbody, .vd-compare tr, .vd-compare th, .vd-compare td { display: block; width: auto; }
  .vd-compare tr { border-bottom: 1px solid var(--vd-divider); padding: 12px 14px; }
  .vd-compare tr:last-child { border-bottom: none; }
  .vd-compare th, .vd-compare td { padding: 4px 0; border: none; font-size: 14.5px; }
  .vd-compare td.ours { background: none; }
  .vd-compare tbody th, .vd-compare td { width: auto; }
  .vd-compare td.ours::before { content: none; }
  .vd-compare .lbl { display: block; font-size: 12.5px; font-weight: 600; color: var(--vd-muted); }
  .vd-compare td.ours .lbl { color: var(--vd-accent); }
  div[class*="st-key-card"] { padding: 16px; }
  .vd-meter { grid-template-columns: 1fr auto; }
  .vd-checks { grid-template-columns: 1fr; }
  .vd-steps { grid-template-columns: 1fr; gap: 18px; }
  .vd-start { grid-template-columns: 1fr 1fr; }
  .vd-steps::before { display: none; }
  [data-testid="stColumn"] .vd-kpi { margin-bottom: 4px; }
  .vd-meter .bar { grid-column: 1 / -1; grid-row: 2; }
}
</style>
"""


def apply_theme() -> None:
    """Inject the global CSS. Call once per run from ``app.py``."""
    st.html(_CSS)
