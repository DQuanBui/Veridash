"""Plotly figures built from :class:`~core.recommender.ChartSpec` results.

Figures only *draw* query results; they never compute new numbers (the one
exception is laying a correlation list out as a symmetric matrix).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.formatting import fmt_value, pretty
from core.recommender import ChartSpec
from ui.components import chart_card
from ui.theme import BORDER, DIVERGING, MUTED, PALETTE, PRIMARY

HEIGHT = 340
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
_TEAL_FILL = "rgba(13,148,136,0.08)"
_TEAL_BOX = "rgba(13,148,136,0.18)"


def _axis_format(kind: str) -> dict:
    if kind == "currency":
        return {"tickprefix": "$", "tickformat": "~s"}
    if kind == "percent":
        return {"ticksuffix": "%", "tickformat": ".0f"}
    if kind == "int":
        return {"tickformat": "~s"}
    return {"tickformat": "~s"}


def _labels(values: pd.Series, kind: str) -> list[str]:
    return [fmt_value(float(v), kind) if pd.notna(v) else "n/a" for v in values]


def _base(fig: go.Figure, height: int = HEIGHT) -> go.Figure:
    fig.update_layout(template="veridash", height=height, showlegend=False)
    return fig


def _line(spec: ChartSpec) -> go.Figure:
    df = spec.data
    fig = go.Figure(
        go.Scatter(
            x=df[spec.x],
            y=df[spec.y],
            mode="lines+markers" if len(df) <= 36 else "lines",
            line={"color": PRIMARY, "width": 2},
            marker={"size": 6, "color": PRIMARY, "line": {"color": "#fff", "width": 1.5}},
            fill="tozeroy",
            fillcolor=_TEAL_FILL,
            customdata=_labels(df[spec.y], spec.value_kind),
            hovertemplate="%{x|%b %d, %Y}<br><b>%{customdata}</b><extra></extra>",
        )
    )
    fig.update_yaxes(rangemode="tozero", **_axis_format(spec.value_kind))
    fig.update_layout(hovermode="x unified")
    return _base(fig)


def _hbar(spec: ChartSpec) -> go.Figure:
    df = spec.data.iloc[::-1]  # largest at the top
    labels = [str(v) for v in df[spec.x]]
    text = _labels(df[spec.y], spec.value_kind)
    fig = go.Figure(
        go.Bar(
            x=df[spec.y],
            y=labels,
            orientation="h",
            marker={"color": PRIMARY, "cornerradius": 4},
            text=text,
            textposition="outside",
            cliponaxis=False,
            textfont={"color": MUTED, "size": 12},
            customdata=text,
            hovertemplate="%{y}<br><b>%{customdata}</b><extra></extra>",
        )
    )
    ref = spec.meta.get("reference")
    if ref and ref in df:
        overall = float(df[ref].iloc[0])
        fig.add_vline(x=overall, line={"color": MUTED, "dash": "dot", "width": 1.5})
        fig.add_annotation(
            x=overall, y=1.04, yref="paper", text=f"Overall {fmt_value(overall, 'percent')}",
            showarrow=False, font={"color": MUTED, "size": 12},
        )
    fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9", **_axis_format(spec.value_kind))
    fig.update_yaxes(showgrid=False, automargin=True)
    height = max(260, min(HEIGHT + 60, 36 * len(df) + 80))
    fig.update_layout(margin={"r": 56})
    return _base(fig, height)


def _discrete(spec: ChartSpec) -> go.Figure:
    df = spec.data
    kind = spec.meta.get("x_kind", "number")
    fig = go.Figure(
        go.Bar(
            x=[fmt_value(float(v), kind) for v in df[spec.x]],
            y=df["records"],
            marker={"color": PRIMARY, "cornerradius": 4},
            customdata=_labels(df["share_pct"], "percent"),
            hovertemplate="%{x}<br><b>%{y:,} records</b> (%{customdata})<extra></extra>",
        )
    )
    fig.update_xaxes(type="category", title={"text": pretty(spec.x)})
    return _base(fig)


def _histogram(spec: ChartSpec) -> go.Figure:
    df = spec.data
    kind = spec.meta.get("x_kind", "number")
    mids = (df["bin_start"] + df["bin_end"]) / 2
    widths = (df["bin_end"] - df["bin_start"]) * 0.92
    ranges = [f"{fmt_value(a, kind)} to {fmt_value(b, kind)}" for a, b in zip(df["bin_start"], df["bin_end"], strict=True)]
    fig = go.Figure(
        go.Bar(
            x=mids,
            y=df["records"],
            width=widths,
            marker={"color": PRIMARY, "cornerradius": 3},
            customdata=list(zip(ranges, _labels(df["share_pct"], "percent"), strict=True)),
            hovertemplate="%{customdata[0]}<br><b>%{y:,} records</b> (%{customdata[1]})<extra></extra>",
        )
    )
    median = float(df["median"].iloc[0])
    fig.add_vline(x=median, line={"color": "#0F172A", "dash": "dot", "width": 1.5})
    fig.add_annotation(x=median, y=1.04, yref="paper", text=f"Median {fmt_value(median, kind)}",
                       showarrow=False, font={"color": MUTED, "size": 12})
    fig.update_xaxes(**_axis_format(kind))
    return _base(fig)


def _donut(spec: ChartSpec) -> go.Figure:
    df = spec.data
    labels = [str(v) for v in df[spec.x]]
    colors = PALETTE[: len(labels)] if len(labels) <= len(PALETTE) else None
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=df[spec.y],
            hole=0.62,
            sort=False,
            direction="clockwise",
            marker={"colors": colors, "line": {"color": "#fff", "width": 2}},
            textinfo="percent",
            textfont={"color": "#fff", "size": 12},
            customdata=_labels(df[spec.y], spec.value_kind),
            hovertemplate="%{label}<br><b>%{customdata}</b> (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        showlegend=True,
        legend={"orientation": "v", "x": 1.02, "y": 0.5, "yanchor": "middle", "font": {"color": "#0F172A"}},
    )
    fig.update_layout(template="veridash", height=HEIGHT)
    return fig


def _box(spec: ChartSpec) -> go.Figure:
    df = spec.data
    cats = [str(v) for v in df[spec.x]]
    fig = go.Figure(
        go.Box(
            x=cats,
            q1=df["q1"],
            median=df["median"],
            q3=df["q3"],
            lowerfence=df["lower_fence"],
            upperfence=df["upper_fence"],
            marker={"color": PRIMARY},
            line={"color": PRIMARY, "width": 1.5},
            fillcolor=_TEAL_BOX,
            hoverinfo="x+y",
        )
    )
    fig.update_yaxes(**_axis_format(spec.value_kind))
    fig.update_xaxes(type="category")
    return _base(fig)


def correlation_matrix(spec: ChartSpec) -> pd.DataFrame:
    """Lay the pairwise correlation rows out as a symmetric matrix."""
    cols = spec.meta["columns"]
    matrix = pd.DataFrame(float("nan"), index=cols, columns=cols)
    for c in cols:
        matrix.loc[c, c] = 1.0
    for row in spec.data.itertuples(index=False):
        matrix.loc[row.col_a, row.col_b] = row.r
        matrix.loc[row.col_b, row.col_a] = row.r
    return matrix


def _heatmap(spec: ChartSpec) -> go.Figure:
    matrix = correlation_matrix(spec)
    names = [pretty(c) for c in matrix.columns]
    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=names,
            y=names,
            zmin=-1,
            zmax=1,
            zmid=0,
            colorscale=DIVERGING,
            xgap=2,
            ygap=2,
            texttemplate="%{z:.2f}",
            textfont={"size": 12},
            hovertemplate="%{y} and %{x}<br><b>r = %{z:.2f}</b><extra></extra>",
            colorbar={"thickness": 10, "outlinewidth": 0, "tickfont": {"color": MUTED}},
        )
    )
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, tickangle=0)
    return _base(fig, max(HEIGHT, 46 * len(names) + 80))


def _scatter(spec: ChartSpec) -> go.Figure:
    df = spec.data
    x_kind = spec.meta.get("x_kind", "number")
    fig = go.Figure(
        go.Scattergl(
            x=df[spec.x],
            y=df[spec.y],
            mode="markers",
            marker={"color": PRIMARY, "size": 7, "opacity": 0.5, "line": {"color": "#fff", "width": 0.5}},
            hovertemplate=f"{pretty(spec.x)}: %{{x:,.2f}}<br>{pretty(spec.y)}: %{{y:,.2f}}<extra></extra>",
        )
    )
    fig.update_xaxes(title={"text": pretty(spec.x)}, showgrid=True, gridcolor="#F1F5F9", **_axis_format(x_kind))
    fig.update_yaxes(title={"text": pretty(spec.y)}, **_axis_format(spec.value_kind))
    return _base(fig)


_BUILDERS = {
    "line": _line,
    "bar": _hbar,
    "histogram": _histogram,
    "donut": _donut,
    "box": _box,
    "heatmap": _heatmap,
    "scatter": _scatter,
}


def figure_for(spec: ChartSpec) -> go.Figure:
    """Return the Plotly figure for a chart spec."""
    if spec.kind == "bar" and spec.meta.get("discrete"):
        return _discrete(spec)
    return _BUILDERS[spec.kind](spec)


def sql_expander(sql: str, data: pd.DataFrame | None = None, label: str = "How this was calculated") -> None:
    """Show the exact SQL that ran, plus the result table it returned."""
    with st.expander(label):
        st.caption("This is the exact DuckDB SQL that produced the numbers above. The table is named data.")
        st.code(sql, language="sql")
        if data is not None:
            st.dataframe(data, hide_index=True, height=min(320, 36 * (len(data) + 1) + 2))


def render_chart_card(spec: ChartSpec, key_prefix: str = "chart") -> None:
    """Render a chart card: title, insight, figure and the SQL expander."""

    def body() -> None:
        st.plotly_chart(figure_for(spec), theme=None, config=PLOTLY_CONFIG, key=f"{key_prefix}_{spec.key}")
        sql_expander(spec.sql, spec.data)

    chart_card(spec.title, spec.insight, body, key=f"{key_prefix}_{spec.key}", notes=[(n, "slate") for n in spec.notes])


def auto_figure(df: pd.DataFrame) -> go.Figure | None:
    """Pick a simple chart for an arbitrary query result, or ``None`` if none fits."""
    if df.empty or df.shape[1] < 2 or len(df) < 2:
        return None
    first, numeric = df.columns[0], [c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric:
        return None
    y = numeric[0]
    if pd.api.types.is_datetime64_any_dtype(df[first]):
        fig = go.Figure(go.Scatter(x=df[first], y=df[y], mode="lines+markers", line={"color": PRIMARY, "width": 2},
                                   marker={"size": 6}))
    elif len(df) <= 30 and not pd.api.types.is_numeric_dtype(df[first]):
        fig = go.Figure(go.Bar(x=[str(v) for v in df[first]], y=df[y], marker={"color": PRIMARY, "cornerradius": 4}))
        fig.update_xaxes(type="category")
    elif pd.api.types.is_numeric_dtype(df[first]):
        fig = go.Figure(go.Scattergl(x=df[first], y=df[y], mode="markers",
                                     marker={"color": PRIMARY, "size": 7, "opacity": 0.6}))
        fig.update_xaxes(title={"text": pretty(str(first))}, showgrid=True, gridcolor="#F1F5F9")
    else:
        return None
    fig.update_yaxes(title={"text": pretty(str(y))})
    fig.update_layout(template="veridash", height=HEIGHT, showlegend=False, xaxis={"linecolor": BORDER})
    return fig
