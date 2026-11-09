"""Home: landing page with a live preview computed from the retail example."""

from __future__ import annotations

import streamlit as st

from core.loader import file_hash
from core.samples import EXAMPLES
from core.settings import SUBHEAD
from ui.charts import PLOTLY_CONFIG, figure_for
from ui.components import feature_card, footer, hero, kpi_card, section_header, step_card
from ui.state import cached_analysis

hero(
    "Verifiable data analysis",
    "Drop your data.<br><span>Trust every number.</span>",
    SUBHEAD,
)
_, b1, b2, _ = st.columns([2.2, 1.3, 1.3, 2.2], gap="small")
with b1:
    if st.button("Analyze your data", type="primary", width="stretch"):
        st.switch_page("views/analyze.py")
with b2:
    if st.button("Try an example", width="stretch"):
        st.switch_page("views/examples.py")

# Live preview: real numbers from the bundled retail example.
ex = EXAMPLES["retail"]
data = ex.read_bytes()
analysis = cached_analysis(file_hash(data), ex.filename, None, None, None, None, True, data)
kpis = {k.key: k for k in analysis.kpis}
trend = next((c for c in analysis.charts if c.key == "trend"), None)

st.write("")
with st.container(key="card_preview"):
    st.markdown(
        "<p class='vd-chart-title'>Live preview</p><p class='vd-chart-insight'>Computed just now from the "
        "retail example. Every figure comes from a DuckDB query you can inspect.</p>",
        unsafe_allow_html=True,
    )
    left, right = st.columns([2, 3], gap="medium")
    with left:
        kpi_card(kpis["metric"].label, kpis["metric"].display, f"{analysis.profile.n_rows:,} transactions")
        st.write("")
        c1, c2 = st.columns(2, gap="small")
        with c1:
            change = kpis.get("period_change")
            kpi_card("Latest month", change.display if change else "n/a", "vs prior month")
        with c2:
            kpi_card("Data health", f"{analysis.health.score}/100", f"Grade {analysis.health.grade}")
    with right:
        if trend is not None:
            fig = figure_for(trend)
            fig.update_layout(height=250)
            st.plotly_chart(fig, theme=None, config=PLOTLY_CONFIG, key="home_trend")
            st.caption(trend.insight)

section_header(
    "Built for numbers you can defend",
    "Veridash separates computing from explaining, so every figure can be traced and every claim checked.",
    kicker="Why Veridash",
    center=True,
)
p1, p2, p3 = st.columns(3, gap="medium")
with p1:
    feature_card(
        "check",
        "Verified numbers",
        "Every chart and KPI comes from a real SQL query shown beside it. AI text is fact-checked "
        "number by number against those results.",
    )
with p2:
    feature_card(
        "lock",
        "Private by design",
        "Files are processed in memory and never stored. AI features see only the schema and "
        "aggregated statistics, never your rows.",
    )
with p3:
    feature_card(
        "export",
        "Export to your tools",
        "Download an Excel report with native charts, a PDF summary, or a Power BI Starter Kit "
        "with Power Query and DAX measures.",
    )

section_header("How it works", "From raw file to a report you can share, in four steps.", kicker="Workflow", center=True)
s1, s2, s3, s4 = st.columns(4, gap="medium")
with s1:
    step_card(1, "upload", "Upload", "Drop a CSV or Excel file, or start with one of three example datasets.")
with s2:
    step_card(2, "search", "Check", "Get a 0 to 100 health score with every issue explained and weighted.")
with s3:
    step_card(3, "chart", "Understand", "See recommended charts, KPIs and insights, each with its query.")
with s4:
    step_card(4, "export", "Export", "Take the results to Excel, PDF or Power BI in one click.")

footer()
