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
FONT_STACK = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

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
  --vd-text: light-dark(#0F172A, #E2E8F0);
  --vd-muted: light-dark(#64748B, #94A3B8);
  --vd-faint: light-dark(#CBD5E1, #334155);
  --vd-border: light-dark(#E2E8F0, #243045);
  --vd-divider: light-dark(#F1F5F9, #1A2438);
  --vd-surface: light-dark(#FFFFFF, #111A2C);
  --vd-subtle: light-dark(#F8FAFC, #131C2E);
  --vd-accent: light-dark(#0F766E, #5EEAD4);
  --vd-tint: light-dark(#F0FDFA, rgba(20, 184, 166, 0.12));
  --vd-tint-border: light-dark(#CCFBF1, rgba(45, 212, 191, 0.28));
  --vd-shadow-color: light-dark(rgba(15, 23, 42, 0.07), rgba(0, 0, 0, 0.35));
  --vd-chip: light-dark(#F1F5F9, #1E293B);
  --vd-ok: light-dark(#15803D, #4ADE80);
  --vd-bad-bg: light-dark(#FEE2E2, rgba(239, 68, 68, 0.22));
  --vd-warn-bg: light-dark(#FFFBEB, rgba(245, 158, 11, 0.10));
  --vd-error-bg: light-dark(#FEF2F2, rgba(239, 68, 68, 0.10));
  --vd-radius: 12px;
  --vd-shadow: 0 1px 2px var(--vd-shadow-color), 0 1px 3px var(--vd-shadow-color);
}
html, body, [class*="css"] { font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
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

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid var(--vd-border); }
.stTabs [data-baseweb="tab"] { font-weight: 600; padding: 10px 4px; color: var(--vd-muted); }
.stTabs [aria-selected="true"] { color: var(--vd-text); }

/* Code blocks (SQL) */
[data-testid="stCode"] pre { border: 1px solid var(--vd-border); border-radius: 10px; }

/* Wordmark */
.vd-wordmark { display: inline-flex; align-items: center; gap: 10px; font-weight: 800;
  font-size: 20px; color: var(--vd-text); letter-spacing: -0.02em; }

/* Hero */
.vd-hero { position: relative; padding: 24px 8px 36px 8px; text-align: center; }
.vd-hero::before { content: ""; position: absolute; inset: -40px 0 0 0; z-index: -1;
  background: radial-gradient(60% 60% at 50% 0%, rgba(13,148,136,0.14) 0%, rgba(13,148,136,0) 70%); }
.vd-eyebrow { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--vd-accent); background: var(--vd-tint);
  border: 1px solid var(--vd-tint-border); padding: 4px 12px; border-radius: 999px; margin-bottom: 20px; }
.vd-hero h1 { font-size: clamp(34px, 5.5vw, 60px); line-height: 1.05; font-weight: 800;
  letter-spacing: -0.035em; margin: 0 auto 16px auto; max-width: 820px; padding: 0; }
.vd-hero h1, .vd-hero h1 * { color: var(--vd-text) !important; }
.vd-hero h1 .vd-accent { color: var(--vd-primary) !important; }
.vd-hero p { font-size: clamp(16px, 2vw, 19px); color: var(--vd-muted); max-width: 640px; margin: 0 auto; line-height: 1.55; }
.vd-trust { display: flex; justify-content: center; flex-wrap: wrap; gap: 8px 22px; margin-top: 18px;
  color: var(--vd-muted); font-size: 13.5px; }
.vd-trust span::before { content: "✓"; color: var(--vd-primary); font-weight: 700; margin-right: 6px; }

/* Section header */
.vd-section { margin: 52px 0 20px 0; }
.vd-section.top { margin-top: 0; }
.vd-section .vd-kicker { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--vd-accent); margin-bottom: 6px; }
.vd-section h2 { font-size: clamp(24px, 3vw, 30px); font-weight: 700; margin: 0 0 6px 0; padding: 0; }
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
.vd-kpi .label { font-size: 12px; font-weight: 600; color: var(--vd-muted); text-transform: uppercase;
  letter-spacing: 0.06em; }
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
.vd-chart-title { font-size: 16px; font-weight: 700; color: var(--vd-text); margin: 0; }
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

/* Author card */
.vd-author { display: flex; gap: 16px; align-items: center; }
.vd-author .n { font-weight: 700; font-size: 18px; color: var(--vd-text); }
.vd-author .r { color: var(--vd-muted); }

/* Footer: brand and links on one row, author credit centered underneath */
.vd-footer { margin-top: 72px; padding: 24px 0 4px 0; border-top: 1px solid var(--vd-border);
  color: var(--vd-muted); font-size: 14px; }
.vd-footer .row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.vd-footer nav { display: flex; flex-wrap: wrap; gap: 6px 20px; }
.vd-footer a { color: var(--vd-muted); text-decoration: none; }
.vd-footer a:hover { color: var(--vd-accent); }
.vd-footer .credit { text-align: center; font-size: 13px; margin-top: 18px; color: var(--vd-muted); }

/* Comparison table (Home) */
.vd-compare { border: 1px solid var(--vd-border); border-radius: var(--vd-radius); overflow: hidden;
  background: var(--vd-surface); box-shadow: var(--vd-shadow); }
.vd-compare table { width: 100%; border-collapse: collapse; font-size: 15px; color: var(--vd-text); }
.vd-compare th, .vd-compare td { padding: 14px 18px; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--vd-divider); line-height: 1.5; }
.vd-compare tr:last-child th, .vd-compare tr:last-child td { border-bottom: none; }
.vd-compare thead th { font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--vd-muted);
  background: var(--vd-subtle); }
.vd-compare tbody th { font-weight: 600; width: 22%; }
.vd-compare td { color: var(--vd-muted); width: 39%; }
.vd-compare .ours { background: var(--vd-tint); color: var(--vd-text); }
.vd-compare thead .ours { color: var(--vd-accent); }
.vd-compare td.ours::before { content: "✓"; color: var(--vd-primary); font-weight: 700; margin-right: 8px; }

/* Use case cards */
.vd-usecase .who { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--vd-accent); margin-top: 12px; }
.vd-usecase .q { font-size: 17px; font-weight: 700; line-height: 1.4; color: var(--vd-text); margin: 6px 0 8px 0; }
.vd-usecase ul { margin: 0 0 12px 0; padding-left: 18px; color: var(--vd-muted); font-size: 14.5px; line-height: 1.6; }

/* Empty and locked states */
.vd-locked { text-align: center; padding: 36px 20px; border: 1px dashed var(--vd-faint); border-radius: var(--vd-radius);
  background: var(--vd-subtle); }
.vd-locked h4 { margin: 10px 0 6px 0; padding: 0; color: var(--vd-text); }
.vd-locked p { color: var(--vd-muted); margin: 0 auto; max-width: 520px; }

/* Small screens */
@media (max-width: 640px) {
  .block-container { padding-top: 4rem; }
  .vd-hero { padding: 32px 0 24px 0; }
  .vd-issue { grid-template-columns: 1fr; gap: 4px; }
  .vd-compare th, .vd-compare td { padding: 10px 12px; font-size: 14px; }
  div[class*="st-key-card"] { padding: 16px; }
}
</style>
"""


def apply_theme() -> None:
    """Inject the global CSS. Call once per run from ``app.py``."""
    st.html(_CSS)
