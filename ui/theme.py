"""Design tokens, global CSS and the Plotly "veridash" template.

All styling lives here so the look of the app can be changed in one place.
Call :func:`apply_theme` once per script run from ``app.py``.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Design tokens
PRIMARY = "#0D9488"
PRIMARY_DARK = "#0F766E"
PRIMARY_TINT = "#F0FDFA"
BG = "#FFFFFF"
BG_SUBTLE = "#F8FAFC"
TEXT = "#0F172A"
MUTED = "#64748B"
BORDER = "#E2E8F0"
GRID = "#F1F5F9"

# Categorical palette, fixed order, validated for CVD separation (see docs).
PALETTE = [
    "#0D9488",  # teal
    "#6366F1",  # indigo
    "#F59E0B",  # amber
    "#EC4899",  # pink
    "#0EA5E9",  # sky
    "#84CC16",  # lime
    "#8B5CF6",  # violet
    "#F97316",  # orange
]
# Diverging scale for correlations: indigo (negative), neutral gray, teal (positive).
DIVERGING = [[0.0, "#4F46E5"], [0.5, "#F1F5F9"], [1.0, "#0D9488"]]
# Sequential single-hue scale.
SEQUENTIAL = [[0.0, "#CCFBF1"], [1.0, "#115E59"]]

FONT_STACK = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"


def _register_plotly_template() -> None:
    """Register the ``veridash`` Plotly template and make it the default."""
    axis = {
        "showgrid": False,
        "zeroline": False,
        "linecolor": BORDER,
        "ticks": "",
        "tickfont": {"color": MUTED, "size": 12},
        "title": {"font": {"color": MUTED, "size": 12}},
        "automargin": True,
    }
    template = go.layout.Template(
        layout={
            "font": {"family": FONT_STACK, "size": 13, "color": TEXT},
            "colorway": PALETTE,
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": axis,
            "yaxis": {**axis, "showgrid": True, "gridcolor": GRID, "linecolor": "rgba(0,0,0,0)"},
            "hoverlabel": {
                "bgcolor": BG,
                "bordercolor": BORDER,
                "font": {"family": FONT_STACK, "color": TEXT, "size": 13},
            },
            "hovermode": "closest",
            "margin": {"l": 8, "r": 8, "t": 16, "b": 8},
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "left",
                "x": 0,
                "font": {"color": MUTED, "size": 12},
                "title": {"text": ""},
            },
            "bargap": 0.28,
            "colorscale": {"sequential": SEQUENTIAL, "diverging": DIVERGING},
        },
        data={
            "bar": [go.Bar(marker={"line": {"width": 0}, "cornerradius": 4})],
            "scatter": [go.Scatter(line={"width": 2})],
        },
    )
    pio.templates["veridash"] = template
    pio.templates.default = "veridash"


_CSS = f"""
<style>
:root {{
  --vd-primary: {PRIMARY};
  --vd-primary-dark: {PRIMARY_DARK};
  --vd-primary-tint: {PRIMARY_TINT};
  --vd-text: {TEXT};
  --vd-muted: {MUTED};
  --vd-border: {BORDER};
  --vd-subtle: {BG_SUBTLE};
  --vd-radius: 12px;
  --vd-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06);
}}
html, body, [class*="css"] {{ font-family: {FONT_STACK}; }}
.block-container {{ max-width: 1200px; padding-top: 2.5rem; padding-bottom: 4rem; }}
footer, [data-testid="stAppDeployButton"], [data-testid="stStatusWidget"] {{ display: none !important; }}
h1, h2, h3 {{ letter-spacing: -0.02em; color: var(--vd-text); }}
a {{ color: var(--vd-primary-dark); }}

/* Bordered containers act as cards */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
  border-radius: var(--vd-radius);
}}
div[class*="st-key-card"] {{
  background: #fff; border: 1px solid var(--vd-border); border-radius: var(--vd-radius);
  padding: 20px 22px; box-shadow: var(--vd-shadow);
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 8px; border-bottom: 1px solid var(--vd-border); }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; padding: 10px 4px; color: var(--vd-muted); }}
.stTabs [aria-selected="true"] {{ color: var(--vd-text); }}

/* Code blocks (SQL) */
[data-testid="stCode"] pre {{ border: 1px solid var(--vd-border); border-radius: 10px; }}

/* Wordmark */
.vd-wordmark {{ display: inline-flex; align-items: center; gap: 10px; font-weight: 800;
  font-size: 20px; color: var(--vd-text); letter-spacing: -0.02em; }}

/* Hero */
.vd-hero {{ position: relative; padding: 56px 8px 40px 8px; text-align: center; }}
.vd-hero::before {{ content: ""; position: absolute; inset: -40px 0 0 0; z-index: -1;
  background: radial-gradient(60% 60% at 50% 0%, rgba(13,148,136,0.12) 0%, rgba(13,148,136,0) 70%); }}
.vd-eyebrow {{ display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--vd-primary-dark); background: var(--vd-primary-tint);
  border: 1px solid #CCFBF1; padding: 4px 12px; border-radius: 999px; margin-bottom: 20px; }}
.vd-hero h1 {{ font-size: clamp(36px, 5.5vw, 60px); line-height: 1.05; font-weight: 800;
  letter-spacing: -0.035em; margin: 0 auto 16px auto; max-width: 820px; padding: 0; }}
.vd-hero h1 span {{ color: var(--vd-primary); }}
.vd-hero p {{ font-size: 19px; color: var(--vd-muted); max-width: 640px; margin: 0 auto; line-height: 1.55; }}

/* Section header */
.vd-section {{ margin: 48px 0 20px 0; }}
.vd-section .vd-kicker {{ font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--vd-primary-dark); margin-bottom: 6px; }}
.vd-section h2 {{ font-size: 28px; font-weight: 700; margin: 0 0 6px 0; padding: 0; }}
.vd-section p {{ color: var(--vd-muted); margin: 0; font-size: 16px; max-width: 720px; }}
.vd-section.center {{ text-align: center; }}
.vd-section.center p {{ margin: 0 auto; }}

/* Cards */
.vd-card {{ background: #fff; border: 1px solid var(--vd-border); border-radius: var(--vd-radius);
  padding: 20px 22px; box-shadow: var(--vd-shadow); height: 100%; }}
.vd-card h4 {{ margin: 12px 0 6px 0; font-size: 16px; font-weight: 700; padding: 0; }}
.vd-card p {{ margin: 0; color: var(--vd-muted); font-size: 14.5px; line-height: 1.55; }}
.vd-icon {{ width: 40px; height: 40px; border-radius: 10px; background: var(--vd-primary-tint);
  color: var(--vd-primary); display: inline-flex; align-items: center; justify-content: center; }}

/* KPI card */
.vd-kpi {{ background: #fff; border: 1px solid var(--vd-border); border-radius: var(--vd-radius);
  padding: 16px 18px; box-shadow: var(--vd-shadow); height: 100%; }}
.vd-kpi .label {{ font-size: 12px; font-weight: 600; color: var(--vd-muted); text-transform: uppercase;
  letter-spacing: 0.06em; }}
.vd-kpi .value {{ font-size: 28px; font-weight: 700; color: var(--vd-text); margin-top: 6px;
  letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }}
.vd-kpi .sub {{ font-size: 13px; color: var(--vd-muted); margin-top: 4px; }}

/* Badges */
.vd-badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 999px; border: 1px solid transparent; white-space: nowrap;
  line-height: 1.6; }}
.vd-badge.teal {{ background: #F0FDFA; color: #0F766E; border-color: #99F6E4; }}
.vd-badge.indigo {{ background: #EEF2FF; color: #4338CA; border-color: #C7D2FE; }}
.vd-badge.slate {{ background: #F8FAFC; color: #475569; border-color: #E2E8F0; }}
.vd-badge.amber {{ background: #FFFBEB; color: #B45309; border-color: #FDE68A; }}
.vd-badge.red {{ background: #FEF2F2; color: #B91C1C; border-color: #FECACA; }}
.vd-badge.green {{ background: #F0FDF4; color: #15803D; border-color: #BBF7D0; }}
.vd-badge.violet {{ background: #F5F3FF; color: #6D28D9; border-color: #DDD6FE; }}
.vd-badge.sky {{ background: #F0F9FF; color: #0369A1; border-color: #BAE6FD; }}
.vd-badges {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 12px 0; }}

/* Callout */
.vd-callout {{ border: 1px solid var(--vd-border); border-left: 4px solid var(--vd-primary);
  background: var(--vd-subtle); border-radius: 10px; padding: 14px 16px; font-size: 14.5px;
  color: var(--vd-text); line-height: 1.55; margin: 8px 0 16px 0; }}
.vd-callout.warn {{ border-left-color: #F59E0B; background: #FFFBEB; }}
.vd-callout.error {{ border-left-color: #EF4444; background: #FEF2F2; }}
.vd-callout .title {{ font-weight: 700; margin-bottom: 2px; }}

/* Step card */
.vd-step {{ position: relative; }}
.vd-step .num {{ position: absolute; top: 18px; right: 20px; font-size: 13px; font-weight: 700;
  color: #CBD5E1; }}

/* Chart card text */
.vd-chart-title {{ font-size: 16px; font-weight: 700; color: var(--vd-text); margin: 0; }}
.vd-chart-insight {{ font-size: 14px; color: var(--vd-muted); margin: 4px 0 4px 0; line-height: 1.5; }}

/* Health score */
.vd-score {{ display: flex; align-items: center; gap: 18px; }}
.vd-score .ring {{ width: 92px; height: 92px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; flex-direction: column; }}
.vd-score .ring .n {{ font-size: 28px; font-weight: 800; letter-spacing: -0.02em; }}
.vd-score .ring .g {{ font-size: 12px; font-weight: 700; color: var(--vd-muted); }}

/* Issue rows */
.vd-issue {{ display: grid; grid-template-columns: 84px 1fr; gap: 12px; padding: 12px 0;
  border-top: 1px solid var(--vd-border); }}
.vd-issue:first-child {{ border-top: none; }}
.vd-issue .t {{ font-weight: 600; font-size: 14.5px; }}
.vd-issue .d {{ font-size: 13.5px; color: var(--vd-muted); margin-top: 2px; }}
.vd-issue .w {{ font-size: 13.5px; color: var(--vd-text); margin-top: 4px; }}

/* Insight lists */
.vd-insight {{ padding: 12px 0; border-top: 1px solid var(--vd-border); }}
.vd-insight:first-child {{ border-top: none; }}
.vd-insight .txt {{ font-size: 15px; line-height: 1.55; }}
.vd-insight .meta {{ margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }}
.vd-cite {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; color: #475569;
  background: #F1F5F9; border-radius: 6px; padding: 1px 6px; }}
.vd-num-ok {{ background: #DCFCE7; border-radius: 4px; padding: 0 2px; }}
.vd-num-bad {{ background: #FEE2E2; border-radius: 4px; padding: 0 2px; text-decoration: underline wavy #EF4444; }}

/* Tables rendered as HTML (profile) */
.vd-table-wrap {{ border: 1px solid var(--vd-border); border-radius: var(--vd-radius); overflow: auto;
  max-height: 560px; }}
table.vd-table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
table.vd-table th {{ position: sticky; top: 0; background: var(--vd-subtle); text-align: left; font-weight: 600;
  color: var(--vd-muted); padding: 10px 12px; border-bottom: 1px solid var(--vd-border); white-space: nowrap; }}
table.vd-table td {{ padding: 9px 12px; border-bottom: 1px solid #F1F5F9; vertical-align: top; }}
table.vd-table td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

/* Footer */
.vd-footer {{ margin-top: 72px; padding: 28px 0 8px 0; border-top: 1px solid var(--vd-border);
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; color: var(--vd-muted);
  font-size: 14px; }}
.vd-footer a {{ color: var(--vd-muted); text-decoration: none; margin-left: 18px; }}
.vd-footer a:hover {{ color: var(--vd-primary-dark); }}

/* Locked state */
.vd-locked {{ text-align: center; padding: 36px 20px; border: 1px dashed #CBD5E1; border-radius: var(--vd-radius);
  background: var(--vd-subtle); }}
.vd-locked h4 {{ margin: 10px 0 6px 0; padding: 0; }}
.vd-locked p {{ color: var(--vd-muted); margin: 0 auto; max-width: 520px; }}
</style>
"""


def apply_theme() -> None:
    """Inject global CSS and register the Plotly template. Call once per run."""
    _register_plotly_template()
    st.html(_CSS)
