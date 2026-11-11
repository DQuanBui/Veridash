"""Export tab: web report, Excel, PDF, Power BI Starter Kit and audit trail downloads."""

from __future__ import annotations

import re

import streamlit as st

from core.pipeline import Analysis
from exports.audit import build_audit_csv
from exports.excel import build_excel
from exports.html_report import build_html_report
from exports.pdf import build_pdf
from exports.powerbi import build_powerbi_kit
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
    with st.container(key="card_export_html"):
        left, right = st.columns([3, 1.2], vertical_alignment="center", gap="medium")
        with left:
            st.markdown(
                "<p class='vd-chart-title'>Shareable web report <span class='vd-badge teal'>New</span></p>"
                "<p class='vd-chart-insight'>One file that opens in any browser, no app needed. Every number in "
                "the insights links to the fact and SQL behind it.</p>",
                unsafe_allow_html=True,
            )
        with right:
            st.download_button(
                "Download web report",
                data=lambda: build_html_report(analysis, insights),
                file_name=f"{stem}_veridash_report.html",
                mime="text/html",
                type="primary",
                width="stretch",
                on_click="ignore",
                key="dl_html",
            )
    st.write("")
    cols = st.columns(2, gap="medium")
    with cols[0], st.container(key="card-eqb_export_excel"):
        _export_card("Excel report",
                     "Summary, column profile, native Excel charts and the full data as a filterable table.")
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
    with cols[1], st.container(key="card-eqb_export_pdf"):
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
    st.write("")
    cols = st.columns(2, gap="medium")
    with cols[0], st.container(key="card-eqb_export_pbi"):
        _export_card("Power BI Starter Kit", "Cleaned CSV, Power Query script, DAX measures, a date table and a quickstart.")
        st.download_button(
            "Download Power BI kit",
            data=lambda: build_powerbi_kit(analysis),
            file_name=f"{stem}_powerbi_kit.zip",
            mime="application/zip",
            type="primary",
            width="stretch",
            on_click="ignore",
            key="dl_pbi",
        )
    with cols[1], st.container(key="card-eqb_export_audit"):
        _export_card("Audit trail",
                     "Every number Veridash computed, with its fact ID and the exact SQL behind it, as a CSV.")
        st.download_button(
            "Download audit trail",
            data=lambda: build_audit_csv(analysis, insights),
            file_name=f"{stem}_audit_trail.csv",
            mime="text/csv",
            type="primary",
            width="stretch",
            on_click="ignore",
            key="dl_audit",
        )
    st.caption("Files are built in memory when you click, sent to your browser and never stored.")
