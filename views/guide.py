"""Guide: a short how-to first, with the technical detail tucked into expanders."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bench.__main__ import load as load_benchmark
from core.health import GRADE_BANDS, HEALTH_WEIGHTS, OUTLIER_SHARE_THRESHOLD
from core.recommender import AVG_HINTS, MAX_CHARTS, METRIC_PRIORITY, TOP_N
from core.settings import (
    ASK_MAX_ROWS,
    CATEGORY_LABELS_FOR_AI,
    HEAVY_VISUAL_ROW_LIMIT,
    MAX_AI_CALLS_PER_SESSION,
    MAX_COLUMNS,
    MAX_FILE_MB,
    MAX_ROWS,
    QUERY_TIMEOUT_S,
    SCATTER_MAX_POINTS,
)
from ui.components import callout, section_header, step_card

section_header("Guide", "Everything you need for a great result, in a two-minute read.", kicker="Guide", top=True)

c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    step_card(1, "upload", "Add your data", "Upload a CSV or Excel file on Analyze, or pick one of the examples.")
with c2:
    step_card(2, "search", "Read the Overview", "Check the health score and issues first, then explore Charts and Insights.")
with c3:
    step_card(3, "export", "Take it with you", "Ask follow-up questions, then download a web report, Excel, PDF or a Power BI kit.")

st.markdown("### Prepare your file")
left, right = st.columns([3, 2], gap="large")
with left:
    st.markdown(
        f"""
- **One row per record** (an order, an employee, a transaction) and one column per field.
- **One header row** at the top, with no titles, notes or merged cells above it.
- **One kind of value per column.** Text such as "TBD" in a number column is flagged and treated as missing.
- **Up to {MAX_FILE_MB} MB:** CSV, XLSX or XLS, up to {MAX_ROWS:,} rows and {MAX_COLUMNS} columns.
"""
    )
with right:
    st.caption("A tidy table")
    st.dataframe(
        pd.DataFrame(
            {
                "date": ["2024-01-03", "2024-01-03", "2024-01-04"],
                "region": ["East", "West", "East"],
                "product": ["Lamp", "Jacket", "Lamp"],
                "units": [2, 1, 4],
                "revenue": [118.0, 119.0, 236.0],
            }
        ),
        hide_index=True,
    )

st.markdown("### What each tab does")
st.markdown(
    """
| Tab | What you get |
|---|---|
| **Overview** | A health score with each issue explained, plus your key numbers. |
| **Charts** | Four to eight charts picked for your data, each with a one-line takeaway. |
| **Insights** | A short summary, key findings and ideas to test, with every number checked. You can also paste anyone's text to check its numbers. |
| **Ask your data** | One-click quick questions, plain-English questions with a key, or your own SQL. |
| **Data** | Search the cleaned data, see what each column contains, and download either as a CSV. |
| **Export** | Download a shareable web report, an Excel report, a PDF summary, a Power BI starter kit or an audit trail of every number. |
"""
)

st.markdown("### Your privacy")
callout(
    "Your file is processed in memory and never stored. The AI never sees your rows: only column names, "
    f"summary results and, for questions, up to {CATEGORY_LABELS_FOR_AI} example labels per column.",
    title="The short version",
)

st.markdown("### Common questions")
bench = load_benchmark()["factcheck"]
faqs = [
    ("Do I need an API key?",
     "No. Without a key you get the health check, charts, KPIs, rule-based insights, quick questions, the SQL box "
     "and every export. "
     "A free Gemini key adds AI-written insights and plain-English questions."),
    ("Why does a number show as unverified?",
     "The AI wrote a number that does not match anything Veridash calculated, for example a difference it worked out "
     "itself. It is flagged in red instead of hidden, so you can judge it."),
    ("How do I know the fact-check works?",
     f"It is measured. The Benchmark page plants {bench['planted_errors']:,} wrong numbers in sentences and counts how "
     f"many are caught ({bench['catch_pct']}% at the last run) and how often correct numbers are wrongly flagged "
     f"({bench['false_alarms']} of {bench['correct_sentences']:,}). It re-runs on every code change."),
    ("Can I share results with someone who does not use Veridash?",
     "Yes. On the Export tab, download the web report: one file that opens in any browser, with the charts, the "
     "insights and the SQL behind every number. It needs no app, account or internet connection."),
    ("How do I compare this month's file with last month's?",
     "Open Compare and upload both files. You get the change in rows, columns, data health and the main metric, "
     "the groups that moved it most and, if both files share an ID column, which records are new or gone. Every "
     "figure shows its SQL, and the whole comparison downloads as a CSV."),
    ("Can I check the numbers in someone else's report?",
     "Yes. At the bottom of the Insights tab, paste a paragraph from a report, an email or an AI chat about the "
     "same file. Each number is matched to what Veridash computed, with the reason for any that fail."),
    ("Can I change the main metric or the date grouping?",
     "Yes. Use the sidebar on the Analyze page. Charts, numbers, insights and exports all update together."),
    ("Why was my column read as text instead of numbers?",
     "Fewer than 90% of its values look like numbers. Clean up stray text such as N/A or TBD and upload again."),
    ("Can the insights be in my language?",
     "Yes, with a Gemini key. On the Insights tab, pick Spanish, French, German, Portuguese, Italian, Dutch or "
     "Vietnamese before writing. Numbers keep the same format in every language, so the fact-check still works."),
    ("Is there a dark mode?",
     "Yes. Veridash follows your device's setting. To switch, open the menu in the top-right corner, choose "
     "Settings and pick a theme."),
    ("Where does my file go when I close the tab?",
     "Nowhere. Your session's memory is released, and cached results expire from server memory within an hour."),
]
for question, answer in faqs:
    with st.expander(question):
        st.write(answer)

st.markdown("### Under the hood")
st.caption("For the curious: exactly how Veridash scores, chooses and checks.")

with st.expander("How the health score is calculated"):
    st.markdown("The score starts at 100. Each check subtracts a penalty that grows with the problem, up to a cap:")
    st.code("score = 100 - sum( min(cap, points_per_unit x measure) )", language="text")
    st.dataframe(
        pd.DataFrame(
            [
                {"Check": c["label"], "Measure": c["unit"], "Points per unit": c["points_per_unit"], "Cap": c["cap"]}
                for c in HEALTH_WEIGHTS.values()
            ]
        ),
        hide_index=True,
    )
    bands = ", ".join(f"{g} at {f}+" for f, g in GRADE_BANDS[:-1]) + ", F below 60"
    st.markdown(
        f"""
- **Grades:** {bands}.
- **Outliers** use the IQR rule (below Q1 - 1.5 x IQR or above Q3 + 1.5 x IQR). A column counts as
  high-outlier when more than {OUTLIER_SHARE_THRESHOLD:g}% of its values are outliers.
- **Example:** 2% missing cells (3 points), 1% duplicate rows (2 points) and one mixed-type column (5 points)
  gives 100 - 10 = 90, grade A.
"""
    )

with st.expander("How charts are chosen"):
    st.markdown(
        f"""
- **Main metric:** the first number column matching {", ".join(METRIC_PRIORITY[:8])} and so on. Rates,
  prices and scores ({", ".join(AVG_HINTS[:5])}...) are averaged; everything else is summed.
- **Trend** when there is a date column, grouped by day, week, month or quarter depending on the date span.
- **What drove the latest change:** for totals and counts, how much each group added or removed
  between the last two complete periods. The bars add up to the total change.
- **Top {TOP_N}** bar charts, **share of total**, **rate by group** for yes/no columns, a **distribution**,
  **spread by group**, a **correlation heatmap** and a **scatter** of the strongest pair, up to {MAX_CHARTS} charts.
- ID columns are never charted. Above {HEAVY_VISUAL_ROW_LIMIT:,} rows, distributions use a labelled sample and
  scatter plots show at most {SCATTER_MAX_POINTS:,} points; key numbers always use the full data.
"""
    )

with st.expander("How AI is used and fact-checked"):
    st.markdown(
        f"""
1. **Code calculates every number** with SQL, and each result gets an ID.
2. **The AI only picks and explains** those numbers. It is told to cite them, avoid inventing causes and
   phrase recommendations as ideas to test.
3. **Every number it writes is checked** against the calculated results, allowing for rounding: "35%" matches
   34.6, but "35.0%" does not. A stated direction must be right ("rose 1.1%" fails for a fall), and a
   group's number must belong to the group named next to it. Anything unmatched is underlined in red.
4. **If anything goes wrong,** Veridash falls back to rule-based insights. Each session gets
   {MAX_AI_CALLS_PER_SESSION} AI calls, and results are reused for the same file.
"""
    )

with st.expander("How comparisons work"):
    st.markdown(
        """
- **Same pipeline:** both files are loaded, typed and health-checked exactly like a single upload.
- **Shared columns only:** a column is compared when it has the same name and type in both files. Others are
  listed as added, removed or retyped.
- **One table, one query per number:** the two files are stacked into one table with a `_file` column, so each
  figure is a single SQL query you can open.
- **Groups:** for totals and counts, a group missing from one file counts as zero, so the changes add up; for
  averages, only groups present in both files are compared.
- **Records:** when both files share an ID column, records are matched on it. Value changes are counted only
  when each ID appears once per file.
"""
    )

with st.expander("Privacy in detail"):
    st.markdown(
        f"""
- **In memory only.** Uploads live in your session's server memory. Results are cached for up to an hour by a
  fingerprint of the file. Nothing is written to disk, and exports are built when you click.
- **AI insights** see column names and types, the health results and the summary results behind the charts,
  including the group names in them (for example, the top {TOP_N} products). Never individual rows.
- **Ask your data** also shares simple ranges and up to {CATEGORY_LABELS_FOR_AI} labels per column so the AI can
  write correct filters. Query results stay on the server.
- **Your key** is kept only in your session and never logged. Google's terms apply to anything sent to Gemini;
  on the free tier Google may use prompts to improve its products.
"""
    )

with st.expander("Limitations"):
    st.markdown(
        f"""
- One tidy table at a time; it does not join files or unpivot layouts. Compare lines up two versions of the
  same table, and a renamed column counts as one removed and one added.
- Ambiguous dates such as 03/04/2024 are read month first, and European number formats (1.234,56) are not supported.
- Correlations and group differences show association, not cause, and are not significance-tested.
- The fact-check verifies each number, its direction and which group it belongs to, not the reasoning around it.
- Ask your data returns at most {ASK_MAX_ROWS:,} rows and stops queries after {QUERY_TIMEOUT_S:g} seconds.
- The Power BI kit is a starting point, not a finished report.
"""
    )
