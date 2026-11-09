"""Guide: how to prepare files, what each tab does, and how Veridash works."""

from __future__ import annotations

import pandas as pd
import streamlit as st

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
from ui.components import callout, footer, section_header

section_header("Guide", "Everything Veridash does, and exactly how it does it.", kicker="Guide")

st.markdown("### Prepare your file")
left, right = st.columns([3, 2], gap="large")
with left:
    st.markdown(
        f"""
- **Tidy format.** One row per record (an order, an employee, a transaction) and one column per field.
- **One header row.** The first row names the columns. No merged cells, titles or notes above it.
- **One table per sheet.** For Excel workbooks with several sheets, pick the sheet in Analyze.
- **Consistent values.** Keep each column to one kind of value. Text such as "TBD" in a number column is
  flagged as a mixed-type issue and treated as missing.
- **Formats Veridash understands.** Dates like 2024-03-31 or 03/31/2024, numbers like 1,234.50, $1,234,
  (123) for negatives and 12.5%. European decimal commas (1.234,56) are not supported.
- **Limits.** CSV, XLSX or XLS up to {MAX_FILE_MB} MB, {MAX_ROWS:,} rows and {MAX_COLUMNS} columns.
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
| **Overview** | Health score and grade, every issue with its severity and why it matters, the KPI row and dataset facts. |
| **Charts** | Four to eight recommended charts. Each has a one-sentence insight and a "How this was calculated" panel with the exact SQL and its result. |
| **Insights** | Executive summary, key findings, recommendations framed as hypotheses and data caveats, with fact citations and a verification badge. |
| **Ask your data** | Ask a question in plain English (with a Gemini key) or write SQL yourself. Every query is validated before it runs. |
| **Data** | A searchable preview of the cleaned data and a profile of every column. |
| **Export** | Excel report with native charts, a PDF summary and a Power BI Starter Kit. |
"""
)

st.markdown("### How the health score is calculated")
st.markdown("The score starts at 100. Each check subtracts a penalty that grows with the size of the problem and is capped:")
st.code("score = 100 - sum( min(cap_i, points_per_unit_i x measure_i) )", language="text")
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
- **Outliers** use the IQR rule: a value is an outlier if it falls below Q1 - 1.5 x IQR or above
  Q3 + 1.5 x IQR. A column counts as high-outlier when more than {OUTLIER_SHARE_THRESHOLD:g}% of its values are outliers.
- **Example:** 2% missing cells (3 points) plus 1% duplicate rows (2 points) and one mixed-type column (5 points)
  gives 100 - 10 = 90, grade A.
- Identifier columns are reported for information only and do not lose points.
"""
)

st.markdown("### How charts are chosen")
st.markdown(
    f"""
- **Primary metric:** the first numeric column matching this priority list:
  {", ".join(METRIC_PRIORITY[:12])} and so on. You can override it in the sidebar.
- **Aggregation:** metrics that look like rates, prices or scores ({", ".join(AVG_HINTS[:6])}...) are averaged;
  everything else is summed.
- **Trend** when there is a date column; the grain (day, week, month, quarter) is chosen from the date span.
- **Top {TOP_N} bar chart** for the most useful category, and a second one when another category exists.
- **Share of total** donut for a category with eight or fewer values (only for summed metrics).
- **Rate by group** when there is a yes/no column, such as attrition by department.
- **Distribution** of the metric (histogram, or counts for small whole-number columns) and its **spread by group** (box plot).
- **Correlation heatmap** when there are three or more numeric columns, plus a **scatter** of the strongest pair.
- At most {MAX_CHARTS} charts. Identifier columns are never charted.
- Above {HEAVY_VISUAL_ROW_LIMIT:,} rows, distributions use a reproducible sample of {HEAVY_VISUAL_ROW_LIMIT:,} rows and
  scatter plots show at most {SCATTER_MAX_POINTS:,} points. Each sampled chart says so. KPIs always use the full data.
"""
)

st.markdown("### How AI is used and fact-checked")
st.markdown(
    f"""
1. **Code computes every number.** DuckDB runs the SQL behind each KPI and chart. Each result becomes a
   *fact* with an ID, such as `kpi.metric` or `top.1.share_pct`.
2. **The AI only selects and explains.** Gemini receives the fact pack (the schema plus those computed facts)
   and is instructed to use only those numbers, cite fact IDs, describe patterns without inventing causes and
   phrase recommendations as hypotheses.
3. **Every number is checked.** Veridash extracts each number from the AI's text (including $, %, K/M/B
   and years) and matches it to a fact, allowing for display rounding. "35%" verifies against 34.6, but
   "35.0%" does not. The badge shows how many verified, and unverified numbers are underlined in red, never hidden.
4. **It degrades gracefully.** Retries handle temporary errors. Any failure falls back to rule-based insights
   with a notice. Each session can make at most {MAX_AI_CALLS_PER_SESSION} AI calls, and results are cached per file.
"""
)

st.markdown("### Privacy")
callout(
    "Your file is processed in memory and never written to disk or stored by Veridash. Raw rows are never sent to the AI.",
    title="The short version",
)
st.markdown(
    f"""
- **In memory only.** Uploaded bytes live in your browser session's server memory. Results are cached in
  server memory for up to an hour, keyed by a fingerprint of the file, so repeat views are fast. Nothing is
  written to disk, and exports are built in memory when you click.
- **What the AI sees for insights:** column names and types, the health results and the aggregated results
  behind the KPIs and charts. That includes group labels that appear in those results (for example, the top
  {TOP_N} products by revenue). It never sees individual rows.
- **What the AI sees for Ask your data:** column names and types, simple ranges (min, max, date range) and up
  to {CATEGORY_LABELS_FOR_AI} distinct category labels per column, so it can write correct filters. Query results
  are computed locally by DuckDB and are not sent back to the AI.
- **Your key.** A key entered in the sidebar is kept only in your session's memory and is never logged or stored.
- **Google's terms apply** to anything sent to Gemini. On the free tier Google may use prompts to improve its
  products, so use a paid key for sensitive work, or leave AI off: every feature except plain-English questions
  works without it.
- **Hosting.** On Streamlit Community Cloud the app runs on Streamlit's servers; the same in-memory rules apply.
"""
)

st.markdown("### Limitations")
st.markdown(
    f"""
- Designed for one clean, tidy table at a time; it does not join files or reshape pivoted layouts.
- Type detection is heuristic. Ambiguous dates such as 03/04/2024 are read month-first, and European
  number formats are not supported.
- Correlations and group differences describe association only; they are not causal and are not
  significance-tested.
- The fact-checker verifies that each number exists in the computed facts, not that the sentence around it
  uses the number correctly. Read AI text critically.
- Ask your data returns at most {ASK_MAX_ROWS:,} rows, and queries stop after {QUERY_TIMEOUT_S:g} seconds.
- The Power BI kit is a starting point (data, Power Query, DAX and a date table), not a finished .pbix report.
"""
)

st.markdown("### FAQ")
faqs = [
    ("Do I need an API key?",
     "No. Without a key you get the full health check, charts, KPIs, rule-based insights, the SQL box and all exports. "
     "A Gemini key adds AI-written insights and plain-English questions."),
    ("Why does a number show as unverified?",
     "The AI wrote a number that does not match any computed fact at the precision it was written, for example a "
     "difference it calculated itself. Veridash flags it instead of hiding it so you can judge it."),
    ("Is the SQL shown really what ran?",
     "Yes. The SQL string displayed is the same string passed to DuckDB, and the table under it is the result it returned."),
    ("Why was my column detected as text instead of a number?",
     "Fewer than 90% of its values could be read as numbers. Clean the stray values or check for unusual formats."),
    ("Can I change the metric or date grain?",
     "Yes. Use the sidebar on the Analyze page. Charts, KPIs, insights and exports update together."),
    ("Where does my file go after I close the tab?",
     "Your session's memory is released, and cached results expire from server memory within an hour."),
]
for question, answer in faqs:
    with st.expander(question):
        st.write(answer)

footer()
