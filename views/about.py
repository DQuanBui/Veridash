"""About: the story, architecture, stack, design decisions, roadmap and author."""

from __future__ import annotations

import streamlit as st

from core.settings import AUTHOR_EMAIL, AUTHOR_NAME, AUTHOR_ROLE, GITHUB_URL, LINKEDIN_URL
from ui.branding import mark
from ui.components import esc, footer, section_header
from ui.theme import theme_mode

section_header("About Veridash", "Why it exists and how it is built.", kicker="About", top=True)

st.markdown("### The problem")
st.markdown(
    """
Turning a raw spreadsheet into a first trustworthy read of the data takes longer than it should: checking
quality, finding the right columns, building the first charts and writing up what matters. AI assistants
promise to shortcut this, but they often produce numbers that cannot be traced to anything, which is a
non-starter for anyone who has to defend a figure in a meeting.

Veridash takes a different approach. Code computes every number with SQL you can read, and AI is limited to
choosing and explaining facts that were already computed. Then every number the AI writes is checked
against those facts. The result is a fast first analysis you can actually trust.
"""
)

st.markdown("### Architecture")
dark = theme_mode() == "dark"
node_fill, node_line, ink = ("#131C2E", "#334155", "#E2E8F0") if dark else ("#F8FAFC", "#CBD5E1", "#0F172A")
accent_fill, accent_line = ("#0F2E2C", "#14B8A6") if dark else ("#F0FDFA", "#5EEAD4")
ai_fill, ai_line = ("#1E1B4B", "#6366F1") if dark else ("#EEF2FF", "#A5B4FC")
edge = "#14B8A6" if dark else "#0D9488"
st.graphviz_chart(
    f"""
digraph G {{
  rankdir=LR; bgcolor="transparent"; nodesep=0.5; ranksep=0.55; pad=0.2;
  node [shape=box, style="rounded,filled", fillcolor="{node_fill}", color="{node_line}", fontname="Helvetica",
        fontsize=13, fontcolor="{ink}", margin="0.18,0.1"];
  edge [color="{edge}", arrowsize=0.8, penwidth=1.3];
  upload [label="CSV or Excel\nin memory", fillcolor="{accent_fill}", color="{accent_line}"];
  prep [label="Load, type and\nhealth-check"];
  duckdb [label="DuckDB SQL\nKPIs and charts"];
  facts [label="Fact pack\nan ID per number"];
  rules [label="Rule-based\ninsights"];
  gemini [label="Gemini\n(optional)", fillcolor="{ai_fill}", color="{ai_line}"];
  check [label="Fact-check\nevery number"];
  ui [label="Streamlit UI", fillcolor="{accent_fill}", color="{accent_line}"];
  exports [label="Excel, PDF,\nPower BI kit"];
  ask [label="Ask your data\nvalidated SELECT"];
  upload -> prep -> duckdb -> facts;
  facts -> rules -> check;
  facts -> gemini -> check;
  check -> ui -> exports;
  ui -> ask;
  ask -> duckdb [style=dashed, constraint=false, color="#94A3B8"];
}}
""",
    width="stretch",
)

st.markdown("### Tech stack")
st.markdown(
    """
| Layer | Tools |
|---|---|
| Interface | Streamlit (multipage with st.navigation), custom CSS design system, Plotly |
| Analysis engine | pandas, NumPy, DuckDB (in-memory, sandboxed) |
| AI | Google Gen AI SDK (Gemini), structured JSON output |
| Exports | xlsxwriter (native Excel charts), fpdf2 and matplotlib (PDF), Power Query M and DAX |
| Quality | pytest (including Streamlit AppTest), Ruff |
"""
)

st.markdown("### Key design decisions")
st.markdown(
    f"""
- **The AI never does math.** Numbers come from code; the AI selects and explains them.
- **Every chart shows its real query.** The SQL on screen is the SQL that ran.
- **AI output is fact-checked.** Every number is matched to a computed fact or flagged.
- **Only summaries reach the AI.** Schema and aggregates, never raw rows.
- **A Power BI kit instead of a .pbix.** Plain-text M and DAX that open anywhere and can be reviewed.
- **A transparent health score.** One formula, one config, shown in full in the Guide.

Read the full reasoning, alternatives and trade-offs in
[DESIGN_DECISIONS.md]({GITHUB_URL}/blob/main/docs/DESIGN_DECISIONS.md).
"""
)

st.markdown("### Roadmap")
st.markdown(
    """
- A PBIP project with a TMDL semantic model, once it can be validated against Power BI Desktop.
- Joining two related files (for example, orders and customers) with a guided key picker.
- Significance tests for group differences, reported alongside the existing hypotheses.
- Saved analysis "recipes" that re-run the same checks on next month's file.
- Dark mode and an accessibility pass on chart colors and keyboard navigation.
"""
)

st.markdown("### Author")
with st.container(key="card_author"):
    st.markdown(
        f"<div class='vd-author'>{mark(48)}<div>"
        f"<div class='n'>{esc(AUTHOR_NAME)}</div>"
        f"<div class='r'>{esc(AUTHOR_ROLE)}</div>"
        f"<div style='margin-top:6px'><a href='mailto:{esc(AUTHOR_EMAIL)}'>{esc(AUTHOR_EMAIL)}</a>"
        f" · <a href='{esc(LINKEDIN_URL)}' target='_blank' rel='noopener'>LinkedIn</a></div></div></div>",
        unsafe_allow_html=True,
    )

footer()
