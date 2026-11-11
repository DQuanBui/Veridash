"""Home: what Veridash does, who it is for, and why its numbers can be trusted."""

from __future__ import annotations

import streamlit as st

from ai.factcheck import check_text
from bench.__main__ import load as load_benchmark
from core.loader import file_hash
from core.samples import EXAMPLES
from core.settings import SUBHEAD
from ui.branding import icon
from ui.components import compare_table, esc, section_header, step_card
from ui.state import cached_analysis, load_example
from ui.worksheet import worksheet_html

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
                   "This month's export compared with last month's, record by record",
                   "Excel, PDF, Power BI and a web report, plus an audit trail of every number"],
        "button": "Analyze your own file",
    },
]

COMPARISON = [
    ("Where the numbers come from", "Generated or summarized by the AI",
     "Computed by code, with the exact query shown next to every chart"),
    ("Checking AI text", "Taken on trust", "Every number fact-checked, and anything unmatched flagged"),
    ("Your data", "Uploaded to an account and stored in the cloud",
     "Kept in memory for your session and never stored; the AI never sees your rows"),
    ("A new month's file", "Rebuild the report and spot the differences by eye",
     "Compare two files: columns, totals, the groups that moved and the records that changed"),
    ("Getting started", "Sign-up first", "No sign-up, and it works without an AI key"),
    ("Taking results further", "Shared from inside their app",
     "A web report, Excel with native charts, a PDF, a Power BI starter kit and an audit trail"),
]

# Example sentence for the worksheet: two figures check out, one belongs to a different category.
DEMO_SENTENCE = "Revenue reached $785.3K. Electronics led with $209.1K, and revenue rose 19.6% last month."

ex = EXAMPLES["retail"]
data = ex.read_bytes()
analysis = cached_analysis(file_hash(data), ex.filename, None, None, None, None, True, data)

st.write("")
left, right = st.columns([1.2, 1], gap="large", vertical_alignment="center")
with left:
    st.markdown(
        "<div class='vd-hero'><h1>Drop your data.<br>Trust every number.</h1>"
        f"<p>{esc(SUBHEAD)}</p></div>",
        unsafe_allow_html=True,
    )
    b1, b2, b3 = st.columns(3, gap="small")
    with b1:
        if st.button("Analyze your data", type="primary", width="stretch"):
            st.switch_page("views/analyze.py")
    with b2:
        if st.button("Compare two files", width="stretch"):
            st.switch_page("views/compare.py")
    with b3:
        if st.button("Try an example", width="stretch"):
            st.switch_page("views/examples.py")
    st.markdown(
        "<div class='vd-trust'><span>No sign-up</span><span>Files never stored</span>"
        "<span>Works without an AI key</span></div>",
        unsafe_allow_html=True,
    )
with right:
    sentence = st.session_state.get("home_demo", DEMO_SENTENCE)
    st.markdown(worksheet_html(sentence, check_text(sentence, analysis.facts), "the retail example"),
                unsafe_allow_html=True)
    st.text_input(
        "Edit the sentence, then press Enter",
        value=DEMO_SENTENCE,
        key="home_demo",
        max_chars=240,
        help="Every number is checked against what Veridash computed from the retail example.",
    )
    st.caption("Try changing $209.1K to $271.4K.")

section_header(
    "Answers for the questions teams actually ask",
    "Start from a realistic example in one click, or bring your own file.",
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

section_header("How it works", "From raw file to a report you can share, in four steps.", center=True)
s1, s2, s3, s4 = st.columns(4, gap="medium")
with s1:
    step_card(1, "upload", "Upload", "Drop in a CSV or Excel file, or pick an example.")
with s2:
    step_card(2, "search", "Check", "See a 0 to 100 health score, with every issue explained.")
with s3:
    step_card(3, "chart", "Understand", "Get charts, KPIs and insights, each with its query.")
with s4:
    step_card(4, "export", "Export", "Take the results to Excel, PDF or Power BI.")
