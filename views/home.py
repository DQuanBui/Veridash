"""Home: what Veridash does, who it is for, and why its numbers can be trusted."""

from __future__ import annotations

import streamlit as st

from bench.__main__ import load as load_benchmark
from core.loader import file_hash
from core.samples import EXAMPLES
from core.settings import SUBHEAD
from ui.branding import icon
from ui.charts import PLOTLY_CONFIG, figure_for
from ui.components import compare_table, esc, hero, kpi_card, section_header, step_card
from ui.state import cached_analysis, load_example

# Use cases: the question a team asks, what Veridash answers, and a one-click demo.
USE_CASES = [
    {
        "key": "retail",
        "icon": "store",
        "who": "Sales and retail",
        "question": "Which stores and products drive revenue, and is growth real?",
        "points": ["Monthly revenue trend with peaks called out",
                   "Which regions drove last month's change, and by how much",
                   "Bulk orders and outliers flagged before they skew averages"],
        "button": "Try the retail example",
    },
    {
        "key": "hr",
        "icon": "users",
        "who": "People and HR",
        "question": "Where is attrition highest, and what is different about those teams?",
        "points": ["Attrition rate by department against the company average",
                   "Satisfaction by role and salary band", "Missing survey answers counted, not hidden"],
        "button": "Try the HR example",
    },
    {
        "key": "portfolio",
        "icon": "trend",
        "who": "Finance and investments",
        "question": "Which holdings and sectors carry the portfolio?",
        "points": ["Market value by ticker and sector share",
                   "Sectors that moved the portfolio most last month",
                   "Very large positions and missing prices surfaced"],
        "button": "Try the portfolio example",
    },
    {
        "key": None,
        "icon": "table",
        "who": "Reporting and BI",
        "question": "Need a trustworthy first read before you build the real report?",
        "points": ["Health check with a practical fix for every issue",
                   "Excel, PDF and a Power BI starter kit with DAX measures",
                   "An audit trail listing every number and the SQL behind it"],
        "button": "Analyze your own file",
    },
]

COMPARISON = [
    ("Where the numbers come from", "Generated or summarized by the AI",
     "Computed by code, with the exact query shown next to every chart"),
    ("Checking AI text", "Taken on trust", "Every number fact-checked, and anything unmatched flagged"),
    ("Your data", "Uploaded to an account and stored in the cloud",
     "Kept in memory for your session and never stored; the AI never sees your rows"),
    ("Getting started", "Sign-up first", "No sign-up, and it works without an AI key"),
    ("Taking results further", "Shared from inside their app",
     "Excel with native charts, a PDF, a Power BI starter kit and an audit trail of every number"),
]

hero(
    "Verifiable data analysis",
    "Drop your data.<br><span class='vd-accent'>Trust every number.</span>",
    SUBHEAD,
)
_, b1, b2, _ = st.columns([2.2, 1.3, 1.3, 2.2], gap="small")
with b1:
    if st.button("Analyze your data", type="primary", width="stretch"):
        st.switch_page("views/analyze.py")
with b2:
    if st.button("Try an example", width="stretch"):
        st.switch_page("views/examples.py")
st.markdown(
    "<div class='vd-trust'><span>No sign-up</span><span>Files never stored</span>"
    "<span>Works without an AI key</span></div>",
    unsafe_allow_html=True,
)

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
        "retail example. Every figure comes from a query you can inspect.</p>",
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
    "Answers for the questions teams actually ask",
    "Start from a realistic example in one click, or bring your own file.",
    kicker="Use cases",
    center=True,
)
for row in (USE_CASES[:2], USE_CASES[2:]):
    cols = st.columns(2, gap="medium")
    for col, case in zip(cols, row, strict=True):
        with col, st.container(key=f"card-eqb_usecase_{case['key'] or 'own'}"):
            points = "".join(f"<li>{esc(p)}</li>" for p in case["points"])
            st.markdown(
                f"<div class='vd-usecase'><div class='vd-icon'>{icon(case['icon'])}</div>"
                f"<div class='who'>{esc(case['who'])}</div><div class='q'>{esc(case['question'])}</div>"
                f"<ul>{points}</ul></div>",
                unsafe_allow_html=True,
            )
            if st.button(case["button"], key=f"usecase_{case['key'] or 'own'}", width="stretch"):
                if case["key"]:
                    load_example(case["key"])
                st.switch_page("views/analyze.py")

section_header(
    "What makes Veridash different",
    "Most AI data tools ask you to trust their numbers. Veridash shows its work.",
    kicker="Why Veridash",
    center=True,
)
compare_table("Many AI dashboard tools", "Veridash", COMPARISON)

# Proof, not promises: published benchmark scores, re-checked on every push.
scores = load_benchmark()
fc, sg = scores["factcheck"], scores["sql_guard"]
st.write("")
with st.container(key="card_proof"):
    left, right = st.columns([4, 1.2], vertical_alignment="center", gap="medium")
    with left:
        st.markdown(
            "<div class='vd-proof'>"
            f"<div><b>{fc['catch_pct']}%</b><span>of planted wrong numbers caught</span></div>"
            f"<div><b>{fc['false_alarms']}</b><span>false alarms on {fc['correct_sentences']:,} correct sentences</span></div>"
            f"<div><b>{sg['guard_blocked']} of {sg['attacks']}</b><span>harmful queries blocked</span></div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with right:
        if st.button("See the benchmark", key="home_benchmark", width="stretch"):
            st.switch_page("views/benchmark.py")

section_header("How it works", "From raw file to a report you can share, in four steps.", kicker="Workflow", center=True)
s1, s2, s3, s4 = st.columns(4, gap="medium")
with s1:
    step_card(1, "upload", "Upload", "Drop in a CSV or Excel file, or pick an example.")
with s2:
    step_card(2, "search", "Check", "See a 0 to 100 health score, with every issue explained.")
with s3:
    step_card(3, "chart", "Understand", "Get charts, KPIs and insights, each with its query.")
with s4:
    step_card(4, "export", "Export", "Take the results to Excel, PDF or Power BI.")
