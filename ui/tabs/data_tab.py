"""Data tab: searchable preview and the column profile table."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from core.formatting import fmt_value, metric_kind
from core.pipeline import Analysis
from core.profiler import ColType, ColumnProfile
from core.settings import HEAVY_VISUAL_ROW_LIMIT
from ui.components import esc, type_badge_html

PREVIEW_ROWS = 1_000


def _summary(col: ColumnProfile) -> str:
    s = col.stats
    if col.col_type == ColType.NUMBER and s:
        k = metric_kind(col.name, col.unit)
        return (
            f"mean {fmt_value(s['mean'], k)} · median {fmt_value(s['median'], k)} · "
            f"min {fmt_value(s['min'], k)} · max {fmt_value(s['max'], k)}"
        )
    if col.col_type == ColType.DATE and s:
        fmt = "%Y-%m-%d"
        return (
            f"{datetime.fromtimestamp(s['min'], tz=UTC).strftime(fmt)} to "
            f"{datetime.fromtimestamp(s['max'], tz=UTC).strftime(fmt)}"
        )
    if col.top_values:
        return ", ".join(f"{v} ({n:,})" for v, n in col.top_values[:3])
    return ""


def profile_table_html(columns: list[ColumnProfile]) -> str:
    """The column profile as an escaped HTML table with type badges."""
    rows = []
    for c in columns:
        flags = []
        if c.mixed_type:
            flags.append("mixed types")
        if c.is_constant:
            flags.append("constant")
        if c.unit:
            flags.append(c.unit)
        rows.append(
            f"<tr><td><b>{esc(c.name)}</b></td><td>{type_badge_html(str(c.col_type))}</td>"
            f"<td class='num'>{c.missing_pct:.1f}%</td><td class='num'>{c.n_unique:,}</td>"
            f"<td class='wrap'>{esc(_summary(c))}</td><td>{esc(', '.join(flags))}</td></tr>"
        )
    return (
        "<div class='vd-table-wrap'><table class='vd-table'><thead><tr><th>Column</th><th>Type</th>"
        "<th style='text-align:right'>Missing</th><th style='text-align:right'>Distinct</th>"
        f"<th>Summary</th><th>Notes</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _search(df: pd.DataFrame, term: str) -> pd.DataFrame:
    mask = pd.Series(False, index=df.index)
    lowered = term.lower()
    for col in df.columns:
        mask |= df[col].astype("string").str.lower().str.contains(lowered, regex=False, na=False)
    return df[mask]


def render(analysis: Analysis) -> None:
    """Render the preview and the profile."""
    profile = analysis.profile
    df = profile.df
    st.markdown("<p class='vd-chart-title'>Preview</p>", unsafe_allow_html=True)
    term = st.text_input("Search all columns", placeholder="Type to filter rows, e.g. a product or region",
                         key="vd_search", label_visibility="collapsed")
    view = df
    if len(df) > HEAVY_VISUAL_ROW_LIMIT:
        view = df.head(HEAVY_VISUAL_ROW_LIMIT)
        st.caption(f"Search covers the first {HEAVY_VISUAL_ROW_LIMIT:,} rows of {len(df):,}.")
    if term:
        view = _search(view, term)
    st.caption(f"Showing {min(len(view), PREVIEW_ROWS):,} of {len(view):,} matching rows (cleaned values).")
    date_only = {
        c.name: st.column_config.DatetimeColumn(format="YYYY-MM-DD")
        for c in profile.columns
        if c.col_type == ColType.DATE and not c.stats.get("has_time")
    }
    st.dataframe(view.head(PREVIEW_ROWS), hide_index=True, height=360, column_config=date_only)

    st.write("")
    st.markdown("<p class='vd-chart-title'>Column profile</p>", unsafe_allow_html=True)
    st.caption("Detected type, completeness and a short summary for every column. ID columns are excluded from charts.")
    st.markdown(profile_table_html(profile.columns), unsafe_allow_html=True)
