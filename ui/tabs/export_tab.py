"""Export tab: Excel report, PDF summary and Power BI Starter Kit downloads."""

from __future__ import annotations

import re

import streamlit as st

from core.pipeline import Analysis
from exports.excel import build_excel
from exports.pdf import build_pdf
from ui.components import esc, source_badge_html
from ui.tabs.insights_tab import current_insights


def _stem(name: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    return re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "veridash"


def _export_card(title: str, text: str) -> None:
    st.markdown(f"<p class='vd-chart-title'>{esc(title)}</p><p class='vd-chart-insight'>{esc(text)}</p>",
                unsafe_allow_html=True)


def render(analysis: Analysis, cache_key: str) -> None:
    """Render the download buttons. Files are generated only when clicked."""
    insights = current_insights(analysis, cache_key)
    stem = _stem(analysis.name)
    st.markdown(
        "<div class='vd-badges'>Exports include the insights currently shown: "
        f"{source_badge_html(insights.source, insights.model)}</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3, gap="medium")
    with cols[0], st.container(key="card_export_excel"):
        _export_card("Excel report",
                     "Summary, column profile, one sheet per chart with a native Excel chart, and the full data as a filterable table.")
        st.download_button(
            "Download Excel",
            data=lambda: build_excel(analysis, insights),
            file_name=f"{stem}_veridash.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            width="stretch",
            on_click="ignore",
            key="dl_excel",
        )
    with cols[1], st.container(key="card_export_pdf"):
        _export_card("PDF summary", "A short report: health, KPIs, top charts, insights and methodology.")
        st.download_button(
            "Download PDF",
            data=lambda: build_pdf(analysis, insights),
            file_name=f"{stem}_veridash.pdf",
            mime="application/pdf",
            type="primary",
            width="stretch",
            on_click="ignore",
            key="dl_pdf",
        )
    with cols[2], st.container(key="card_export_pbi"):
        _export_card("Power BI Starter Kit", "Cleaned CSV, Power Query script, DAX measures, a date table and a quickstart.")
        st.button("Coming soon", disabled=True, width="stretch", key="dl_pbi_soon")
    st.caption("Files are built in memory when you click, sent to your browser and never stored.")
