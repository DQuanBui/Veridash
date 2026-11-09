"""Ask your data tab: natural-language questions (with a key) and a SQL box (always)."""

from __future__ import annotations

import streamlit as st

from ai.client import GeminiClient, resolve_api_key, resolve_model
from ai.nl2sql import AskResult, ask, example_questions, run_validated
from core.engine import QueryEngine
from core.pipeline import Analysis
from core.settings import ASK_MAX_ROWS, CATEGORY_LABELS_FOR_AI
from ui.branding import icon
from ui.charts import PLOTLY_CONFIG, auto_figure
from ui.components import badge_html, callout, esc
from ui.state import session_api_key

HISTORY_KEY = "vd_ask_history"


def _render_result(res: AskResult, key: str) -> None:
    with st.container(key=f"card_ask_{key}"):
        if res.question:
            st.markdown(f"<p class='vd-chart-title'>{esc(res.question)}</p>", unsafe_allow_html=True)
        if res.explanation:
            st.markdown(f"<p class='vd-chart-insight'>{esc(res.explanation)}</p>", unsafe_allow_html=True)
        if res.sql:
            st.code(res.sql, language="sql")
        if res.error:
            callout(res.error, title="The query did not run", kind="error")
            return
        meta = [f"{len(res.data):,} row(s)", f"{res.elapsed_ms:,.0f} ms"]
        if res.truncated:
            meta.append(f"truncated to {ASK_MAX_ROWS:,} rows")
        st.markdown("<div class='vd-badges'>" + "".join(badge_html(m, "slate") for m in meta) + "</div>",
                    unsafe_allow_html=True)
        fig = auto_figure(res.data)
        if fig is not None:
            st.plotly_chart(fig, theme=None, config=PLOTLY_CONFIG, key=f"ask_fig_{key}")
        st.dataframe(res.data, hide_index=True, height=min(360, 36 * (len(res.data) + 1) + 2))


def _locked(examples: list[str]) -> None:
    chips = "".join(f"<span class='vd-badge slate' style='margin:4px'>{esc(q)}</span>" for q in examples)
    st.markdown(
        f"<div class='vd-locked'><div class='vd-icon'>{icon('lock')}</div>"
        "<h4>Ask questions in plain English</h4>"
        "<p>Add a Gemini key in the sidebar to turn questions into SQL. Gemini sees only column names, "
        f"types, simple ranges and up to {CATEGORY_LABELS_FOR_AI} category labels per column, never your rows.</p>"
        f"<div style='margin-top:14px'>{chips}</div></div>",
        unsafe_allow_html=True,
    )


def render(analysis: Analysis, file_key: str) -> None:
    """Render the Ask your data tab. History is kept per file for this session."""
    history: list[AskResult] = st.session_state.setdefault(HISTORY_KEY, {}).setdefault(file_key, [])
    examples = example_questions(analysis.selection)
    api_key, _ = resolve_api_key(session_api_key())

    if api_key:
        client = GeminiClient(api_key, resolve_model(), st.session_state)
        picked = st.pills("Try an example", examples, key="vd_ask_pick")
        with st.form("vd_ask_form", clear_on_submit=False, border=False):
            question = st.text_input("Your question", value=picked or "", placeholder=examples[0],
                                     key="vd_question")
            submitted = st.form_submit_button("Ask", type="primary", disabled=client.calls_left <= 0)
        st.caption(f"Gemini writes one SELECT query; Veridash validates it and runs it on DuckDB. "
                   f"{client.calls_left} AI call(s) left this session.")
        if submitted and question.strip():
            with st.spinner("Writing and checking the query..."), QueryEngine(analysis.profile.df) as engine:
                history.insert(0, ask(client, engine, analysis.profile, question.strip()))
            del history[5:]
    else:
        _locked(examples)

    st.write("")
    with st.expander("Write SQL yourself (no key needed)", expanded=not api_key and not history):
        st.caption("Query the table named data with DuckDB SQL. The same safety checks apply: "
                   f"SELECT only, no file access, and at most {ASK_MAX_ROWS:,} rows.")
        default_sql = analysis.charts[0].sql if analysis.charts else "SELECT * FROM data"
        with st.form("vd_sql_form", border=False):
            sql = st.text_area("SQL", value=default_sql, height=180, key="vd_sql_text", label_visibility="collapsed")
            run = st.form_submit_button("Run query")
        if run:
            with QueryEngine(analysis.profile.df) as engine:
                history.insert(0, run_validated(engine, sql, question="Your SQL"))
            del history[5:]

    for i, res in enumerate(history):
        st.write("")
        _render_result(res, f"{len(history) - i}")
