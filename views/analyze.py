"""Analyze page: upload or pick an example, then explore six tabs."""

from __future__ import annotations

import streamlit as st

from core.formatting import pretty
from core.loader import EXCEL_EXTENSIONS, LoadError, file_hash, list_excel_sheets
from core.profiler import ColType
from core.recommender import GRAINS, make_selection
from core.samples import EXAMPLES
from core.settings import MAX_FILE_MB
from ui.components import badges, callout, esc, section_header
from ui.state import (
    API_KEY,
    Source,
    cached_analysis,
    cached_prepare,
    get_source,
    load_example,
    set_source,
)
from ui.tabs import charts_tab, data_tab, insights_tab, overview

EXAMPLE_PLACEHOLDER = "Choose an example..."


def _on_upload() -> None:
    uploaded = st.session_state.get("vd_uploader")
    if uploaded is not None:
        set_source(Source(name=uploaded.name, data=uploaded.getvalue(), kind="upload"))
        st.session_state["vd_example_pick"] = EXAMPLE_PLACEHOLDER


def _on_example() -> None:
    choice = st.session_state.get("vd_example_pick")
    key = next((k for k, e in EXAMPLES.items() if e.title == choice), None)
    if key:
        load_example(key)


def _input_row() -> None:
    left, right = st.columns([3, 2], gap="medium", vertical_alignment="bottom")
    with left:
        st.file_uploader(
            f"Upload a CSV or Excel file (max {MAX_FILE_MB} MB)",
            type=["csv", "xlsx", "xls"],
            key="vd_uploader",
            on_change=_on_upload,
            help="Files are processed in memory and never written to disk.",
        )
    with right:
        st.selectbox(
            "Or load an example",
            [EXAMPLE_PLACEHOLDER] + [e.title for e in EXAMPLES.values()],
            key="vd_example_pick",
            on_change=_on_example,
        )


def _empty_state() -> None:
    callout(
        "Upload a tidy table (one header row, one row per record) or pick an example above. "
        "Veridash will check its health, profile every column, recommend charts and KPIs, "
        "and write insights you can verify.",
        title="Start with a file",
    )


def _sidebar(prepared, file_id: str) -> tuple[str | None, str | None, str | None, bool]:
    """Render overrides; returns (metric, date_col, grain, use_date)."""
    profile = prepared.profile
    auto = make_selection(profile)
    with st.sidebar:
        st.markdown("#### Analysis settings")
        numerics = [c.name for c in profile.columns if c.col_type == ColType.NUMBER and not c.is_constant]
        metric = None
        if numerics:
            metric = st.selectbox(
                "Primary metric",
                numerics,
                index=numerics.index(auto.metric) if auto.metric in numerics else 0,
                key=f"vd_metric_{file_id}",
                help="Auto-detected from a priority list (revenue, sales, amount...). Change it any time.",
            )
        dates = [c.name for c in profile.columns if c.col_type == ColType.DATE]
        none_label = "No date column"
        date_options = [*dates, none_label]
        date_choice = st.selectbox(
            "Date column",
            date_options,
            index=dates.index(auto.date_col) if auto.date_col in dates else len(dates),
            key=f"vd_date_{file_id}",
        )
        use_date = date_choice != none_label
        grain = st.selectbox(
            "Date grain",
            GRAINS,
            index=GRAINS.index(auto.grain),
            key=f"vd_grain_{file_id}",
            disabled=not use_date,
            format_func=str.title,
        )
        st.divider()
        st.markdown("#### Gemini key (optional)")
        st.text_input(
            "Bring your own Gemini key",
            type="password",
            key=API_KEY,
            placeholder="Paste a key to enable AI features",
            help="Kept only in this browser session's memory. Never logged, stored or shared.",
        )
        st.caption("Without a key, Veridash uses rule-based insights with the same structure.")
        st.divider()
        st.markdown("#### Privacy")
        st.caption(
            "Your file is processed in memory and never written to disk. AI features receive only the "
            "schema and aggregated statistics, never raw rows. Ask your data also shares up to 10 "
            "category labels per column."
        )
    return metric, (date_choice if use_date else None), grain, use_date


def _placeholder(text: str) -> None:
    callout(text, title="Coming soon")


section_header(
    "Analyze your data",
    "Every number on this page comes from a DuckDB query you can inspect.",
    kicker="Analyze",
)
_input_row()
requested = st.query_params.get("example")
if requested in EXAMPLES and get_source() is None:
    load_example(requested)
source = get_source()
if source is None:
    _empty_state()
    st.stop()

sheet = None
if source.name.lower().endswith(EXCEL_EXTENSIONS):
    try:
        sheets = list_excel_sheets(source.data, source.name)
    except LoadError as exc:
        callout(str(exc), title="This file could not be loaded", kind="error")
        st.stop()
    if len(sheets) > 1:
        sheet = st.selectbox("Sheet", sheets, key=f"vd_sheet_{file_hash(source.data)}")

fid = file_hash(source.data + (sheet or "").encode())
try:
    with st.spinner("Profiling your data..."):
        prepared = cached_prepare(fid, source.name, sheet, source.data)
except LoadError as exc:
    callout(str(exc), title="This file could not be loaded", kind="error")
    st.stop()

metric, date_col, grain, use_date = _sidebar(prepared, fid)
with st.spinner("Running queries..."):
    analysis = cached_analysis(fid, source.name, sheet, metric, date_col, grain, use_date, source.data)

head_l, head_r = st.columns([5, 1], vertical_alignment="center")
with head_l:
    label = "Example" if source.kind == "example" else "Upload"
    st.markdown(f"<p class='vd-chart-title'>{esc(source.name)}</p>", unsafe_allow_html=True)
    badges(
        [
            (label, "teal"),
            (f"{analysis.profile.n_rows:,} rows", "slate"),
            (f"{analysis.profile.n_cols} columns", "slate"),
            (f"Metric: {pretty(analysis.selection.metric or 'records')}", "indigo"),
        ]
        + ([(f"Sheet: {sheet}", "slate")] if sheet else [])
    )
with head_r:
    if st.button("Clear", width="stretch"):
        set_source(None)
        st.rerun()

tabs = st.tabs(["Overview", "Charts", "Insights", "Ask your data", "Data", "Export"])
with tabs[0]:
    overview.render(analysis)
with tabs[1]:
    charts_tab.render(analysis)
with tabs[2]:
    insights_tab.render(analysis, cache_key=f"{fid}|{metric}|{date_col}|{grain}")
with tabs[3]:
    _placeholder("Ask questions in plain English. This tab arrives with the AI layer.")
with tabs[4]:
    data_tab.render(analysis)
with tabs[5]:
    _placeholder("Excel, PDF and Power BI exports are on the way.")
