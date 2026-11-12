"""Plotly figures built from :class:`~core.recommender.ChartSpec` results.

Figures only *draw* query results; they never compute new numbers (the one
exception is laying a correlation list out as a symmetric matrix). Colors come
from :func:`ui.theme.chart_tokens`, so every chart matches light or dark mode.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.formatting import fmt_value, pretty
from core.recommender import ChartSpec
from ui.components import chart_card
from ui.theme import ChartTokens, chart_tokens

HEIGHT = 340
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def _axis_format(kind: str) -> dict:
    if kind == "currency":
        return {"tickprefix": "$", "tickformat": "~s"}
    if kind == "percent":
        return {"ticksuffix": "%", "tickformat": ".0f"}
    return {"tickformat": "~s"}


def _labels(values: pd.Series, kind: str) -> list[str]:
    return [fmt_value(float(v), kind) if pd.notna(v) else "n/a" for v in values]


def _base(fig: go.Figure, tk: ChartTokens, height: int = HEIGHT) -> go.Figure:
    fig.update_layout(template=tk.template, height=height, showlegend=False)
    return fig


def _reference_line(fig: go.Figure, tk: ChartTokens, x: float, text: str) -> None:
    fig.add_vline(x=x, line={"color": tk.muted, "dash": "dot", "width": 1.5})
    fig.add_annotation(x=x, y=1.04, yref="paper", text=text, showarrow=False, font={"color": tk.muted, "size": 12})


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _line(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
    df = spec.data
    top = 0.26 if tk.mode == "dark" else 0.18
    fig = go.Figure(
        go.Scatter(
            x=df[spec.x],
            y=df[spec.y],
            mode="lines+markers" if len(df) <= 36 else "lines",
            line={"color": tk.primary, "width": 2.4},  # straight segments: no curve past the real values
            marker={"size": 6, "color": tk.primary, "line": {"color": tk.surface, "width": 1.5}},
            fill="tozeroy",
            # A tint that fades toward the axis, instead of a flat wash
            fillgradient={"type": "vertical",
                          "colorscale": [[0, _rgba(tk.primary, 0)], [1, _rgba(tk.primary, top)]]},
            customdata=_labels(df[spec.y], spec.value_kind),
            hovertemplate="%{x|%b %d, %Y}<br><b>%{customdata}</b><extra></extra>",
        )
    )
    if len(df):  # mark the latest value so the eye lands on "now"
        fig.add_trace(go.Scatter(
            x=[df[spec.x].iloc[-1]], y=[df[spec.y].iloc[-1]], mode="markers", hoverinfo="skip", showlegend=False,
            marker={"size": 11, "color": tk.primary, "line": {"color": tk.surface, "width": 2.5}},
        ))
    fig.update_yaxes(rangemode="tozero", **_axis_format(spec.value_kind))
    fig.update_layout(hovermode="x unified")
    return _base(fig, tk)


def _hbar(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
    df = spec.data.iloc[::-1]  # largest at the top
    labels = [str(v) for v in df[spec.x]]
    diverging = bool(spec.meta.get("diverging"))
    text = _labels(df[spec.y], spec.value_kind)
    color: str | list[str] = tk.primary
    if diverging:
        text = [("+" if v >= 0 else "-") + fmt_value(abs(float(v)), spec.value_kind) for v in df[spec.y]]
        color = [tk.primary if v >= 0 else tk.negative for v in df[spec.y]]
    fig = go.Figure(
        go.Bar(
            x=df[spec.y],
            y=labels,
            orientation="h",
            marker={"color": color, "cornerradius": 4},
            text=text,
            textposition="outside",
            cliponaxis=False,
            textfont={"color": tk.muted, "size": 12},
            customdata=text,
            hovertemplate="%{y}<br><b>%{customdata}</b><extra></extra>",
        )
    )
    ref = spec.meta.get("reference")
    if ref and ref in df:
        overall = float(df[ref].iloc[0])
        _reference_line(fig, tk, overall, f"Overall {fmt_value(overall, 'percent')}")
    fig.update_xaxes(showgrid=True, gridcolor=tk.grid, **_axis_format(spec.value_kind))
    if diverging:
        # Pad both sides so the signed labels outside the bars never collide with the group names.
        # Each bar carries its signed value, so the axis numbers are hidden.
        lo, hi = min(0.0, float(df[spec.y].min())), max(0.0, float(df[spec.y].max()))
        span = (hi - lo) or 1.0
        fig.update_xaxes(zeroline=True, zerolinecolor=tk.muted, zerolinewidth=1, showticklabels=False,
                         range=[lo - (0.5 * span if lo < 0 else 0), hi + (0.35 * span if hi > 0 else 0)])
    fig.update_yaxes(showgrid=False, automargin=True, ticklabelstandoff=8)
    fig.update_layout(margin={"r": 56, "l": 8})
    return _base(fig, tk, max(260, min(HEIGHT + 60, 36 * len(df) + 80)))


def _discrete(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
    df = spec.data
    kind = spec.meta.get("x_kind", "number")
    fig = go.Figure(
        go.Bar(
            x=[fmt_value(float(v), kind) for v in df[spec.x]],
            y=df["records"],
            marker={"color": tk.primary, "cornerradius": 4},
            customdata=_labels(df["share_pct"], "percent"),
            hovertemplate="%{x}<br><b>%{y:,} records</b> (%{customdata})<extra></extra>",
        )
    )
    fig.update_xaxes(type="category", title={"text": pretty(spec.x)})
    return _base(fig, tk)


def _histogram(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
    df = spec.data
    kind = spec.meta.get("x_kind", "number")
    ranges = [f"{fmt_value(a, kind)} to {fmt_value(b, kind)}" for a, b in zip(df["bin_start"], df["bin_end"], strict=True)]
    fig = go.Figure(
        go.Bar(
            x=(df["bin_start"] + df["bin_end"]) / 2,
            y=df["records"],
            width=(df["bin_end"] - df["bin_start"]) * 0.92,
            marker={"color": tk.primary, "cornerradius": 3},
            customdata=list(zip(ranges, _labels(df["share_pct"], "percent"), strict=True)),
            hovertemplate="%{customdata[0]}<br><b>%{y:,} records</b> (%{customdata[1]})<extra></extra>",
        )
    )
    median = float(df["median"].iloc[0])
    _reference_line(fig, tk, median, f"Median {fmt_value(median, kind)}")
    fig.update_xaxes(**_axis_format(kind))
    return _base(fig, tk)


def _donut(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
    df = spec.data
    labels = [str(v) for v in df[spec.x]]
    colors = list(tk.palette[: len(labels)]) if len(labels) <= len(tk.palette) else None
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=df[spec.y],
            hole=0.62,
            sort=False,
            direction="clockwise",
            marker={"colors": colors, "line": {"color": tk.surface, "width": 2}},
            textinfo="percent",
            textfont={"color": "#FFFFFF", "size": 12},
            customdata=_labels(df[spec.y], spec.value_kind),
            hovertemplate="%{label}<br><b>%{customdata}</b> (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(template=tk.template, height=HEIGHT, showlegend=True,
                      legend={"orientation": "v", "x": 1.02, "y": 0.5, "yanchor": "middle"})
    return fig


def _box(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
    df = spec.data
    fig = go.Figure(
        go.Box(
            x=[str(v) for v in df[spec.x]],
            q1=df["q1"],
            median=df["median"],
            q3=df["q3"],
            lowerfence=df["lower_fence"],
            upperfence=df["upper_fence"],
            marker={"color": tk.primary},
            line={"color": tk.primary, "width": 1.5},
            fillcolor=tk.box_fill,
            hoverinfo="x+y",
        )
    )
    fig.update_yaxes(**_axis_format(spec.value_kind))
    fig.update_xaxes(type="category")
    return _base(fig, tk)


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


def _heatmap(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
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
            colorscale=[list(s) for s in tk.diverging],
            xgap=2,
            ygap=2,
            texttemplate="%{z:.2f}",
            textfont={"size": 12},
            hovertemplate="%{y} and %{x}<br><b>r = %{z:.2f}</b><extra></extra>",
            colorbar={"thickness": 10, "outlinewidth": 0, "tickfont": {"color": tk.muted}},
        )
    )
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, tickangle=0)
    return _base(fig, tk, max(HEIGHT, 46 * len(names) + 80))


def _scatter(spec: ChartSpec, tk: ChartTokens) -> go.Figure:
    df = spec.data
    x_kind = spec.meta.get("x_kind", "number")
    fig = go.Figure(
        go.Scattergl(
            x=df[spec.x],
            y=df[spec.y],
            mode="markers",
            marker={"color": tk.primary, "size": 7, "opacity": 0.5, "line": {"color": tk.surface, "width": 0.5}},
            hovertemplate=f"{pretty(spec.x)}: %{{x:,.2f}}<br>{pretty(spec.y)}: %{{y:,.2f}}<extra></extra>",
        )
    )
    fig.update_xaxes(title={"text": pretty(spec.x)}, showgrid=True, gridcolor=tk.grid, **_axis_format(x_kind))
    fig.update_yaxes(title={"text": pretty(spec.y)}, **_axis_format(spec.value_kind))
    return _base(fig, tk)


_BUILDERS = {
    "line": _line,
    "bar": _hbar,
    "histogram": _histogram,
    "donut": _donut,
    "box": _box,
    "heatmap": _heatmap,
    "scatter": _scatter,
}


def figure_for(spec: ChartSpec, tk: ChartTokens | None = None) -> go.Figure:
    """Return the Plotly figure for a chart spec in the current (or given) mode."""
    tk = tk or chart_tokens()
    if spec.kind == "bar" and spec.meta.get("discrete"):
        return _discrete(spec, tk)
    return _BUILDERS[spec.kind](spec, tk)


def number_columns(df: pd.DataFrame) -> dict:
    """Column config that shows floats with thousands separators and 2 decimals."""
    return {
        str(c): st.column_config.NumberColumn(format="%,.2f")
        for c in df.columns
        if pd.api.types.is_float_dtype(df[c])
    }


def sql_expander(sql: str, data: pd.DataFrame | None = None, label: str = "How this was calculated",
                 download_name: str | None = None) -> None:
    """Show the exact SQL that ran and the result table it returned, with an optional CSV download of that table."""
    with st.expander(label):
        st.caption("The exact DuckDB SQL that produced the numbers above. The table is named data.")
        st.code(sql, language="sql")
        if data is not None:
            st.dataframe(data, hide_index=True, height=min(320, 36 * (len(data) + 1) + 2),
                         column_config=number_columns(data))
            if download_name:
                st.download_button(
                    "Download this data",
                    data=lambda: data.round(4).to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{download_name}.csv",
                    mime="text/csv",
                    icon=":material/download:",
                    type="tertiary",
                    on_click="ignore",
                    key=f"dl_chart_{download_name}",
                )


def render_chart_card(spec: ChartSpec, key_prefix: str = "chart") -> None:
    """Render a chart card: title, insight, figure and the SQL expander."""

    def body() -> None:
        st.plotly_chart(figure_for(spec), theme=None, config=PLOTLY_CONFIG, key=f"{key_prefix}_{spec.key}")
        sql_expander(spec.sql, spec.data, download_name=f"{key_prefix}_{spec.key}")

    chart_card(spec.title, spec.insight, body, key=f"{key_prefix}_{spec.key}", notes=[(n, "slate") for n in spec.notes])


def auto_figure(df: pd.DataFrame, tk: ChartTokens | None = None) -> go.Figure | None:
    """Pick a simple chart for an arbitrary query result, or ``None`` if none fits."""
    tk = tk or chart_tokens()
    if df.empty or df.shape[1] < 2 or len(df) < 2:
        return None
    first, numeric = df.columns[0], [c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric:
        return None
    y = numeric[0]
    if pd.api.types.is_datetime64_any_dtype(df[first]):
        fig = go.Figure(go.Scatter(x=df[first], y=df[y], mode="lines+markers", line={"color": tk.primary, "width": 2},
                                   marker={"size": 6}))
    elif len(df) <= 30 and not pd.api.types.is_numeric_dtype(df[first]):
        fig = go.Figure(go.Bar(x=[str(v) for v in df[first]], y=df[y], marker={"color": tk.primary, "cornerradius": 4}))
        fig.update_xaxes(type="category")
    elif pd.api.types.is_numeric_dtype(df[first]):
        fig = go.Figure(go.Scattergl(x=df[first], y=df[y], mode="markers",
                                     marker={"color": tk.primary, "size": 7, "opacity": 0.6}))
        fig.update_xaxes(title={"text": pretty(str(first))}, showgrid=True, gridcolor=tk.grid)
    else:
        return None
    fig.update_yaxes(title={"text": pretty(str(y))})
    fig.update_layout(template=tk.template, height=HEIGHT, showlegend=False)
    return fig
