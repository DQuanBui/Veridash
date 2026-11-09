"""Charts tab: auto-recommended charts in a responsive grid."""

from __future__ import annotations

import streamlit as st

from core.pipeline import Analysis
from ui.charts import render_chart_card
from ui.components import callout

FULL_WIDTH = {"trend", "correlation"}


def render(analysis: Analysis) -> None:
    """Render chart cards: wide charts full width, the rest two per row."""
    charts = analysis.charts
    if not charts:
        callout("No charts could be recommended for this file. Check the Data tab for column types.", kind="warn")
        return
    st.caption(
        f"{len(charts)} charts chosen from the shape of your data. Open \"How this was calculated\" on any "
        "card to see the exact SQL that ran and the table it returned."
    )
    pending: list = []
    for chart in charts:
        if chart.key in FULL_WIDTH:
            _flush(pending)
            render_chart_card(chart)
        else:
            pending.append(chart)
            if len(pending) == 2:
                _flush(pending)
    _flush(pending)


def _flush(pending: list) -> None:
    if not pending:
        return
    cols = st.columns(2, gap="medium")
    for col, chart in zip(cols, pending, strict=False):
        with col:
            render_chart_card(chart)
    pending.clear()
