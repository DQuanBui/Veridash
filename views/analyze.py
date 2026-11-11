"""Analyze page: pick a file, then explore six tabs.

Two states keep the page uncluttered:

* **No file yet:** one card with the uploader and one-click examples.
* **File loaded:** a compact file bar (name, size, metric) with a "Change file"
  menu, the six analysis tabs, and settings in the sidebar.
"""

from __future__ import annotations

import streamlit as st

from ai.client import resolve_api_key
from core.formatting import pretty
from core.loader import EXCEL_EXTENSIONS, LoadError, file_hash, list_excel_sheets
from core.profiler import ColType
from core.recommender import GRAINS, make_selection
from core.samples import EXAMPLES
from core.settings import CATEGORY_LABELS_FOR_AI, MAX_FILE_MB
from ui.branding import icon
from ui.components import badge_html, callout, esc, section_header, sparkline_svg
from ui.state import (
    API_KEY,
    Source,
    cached_analysis,
    cached_prepare,
    example_trend,
    get_source,
    load_example,
    session_api_key,
    set_source,
)
from ui.tabs import ask_tab, charts_tab, data_tab, export_tab, insights_tab, overview

UPLOAD_COUNTER = "vd_upload_n"


def _uploader_key() -> str:
    return f"vd_uploader_{st.session_state.get(UPLOAD_COUNTER, 0)}"


def _on_upload() -> None:
    uploaded = st.session_state.get(_uploader_key())
    if uploaded is not None:
        set_source(Source(name=uploaded.name, data=uploaded.getvalue(), kind="upload"))


def _start_over() -> None:
    set_source(None)
    st.session_state[UPLOAD_COUNTER] = st.session_state.get(UPLOAD_COUNTER, 0) + 1


def _uploader(collapsed: bool = False) -> None:
    st.file_uploader(
        f"Upload a CSV or Excel file (up to {MAX_FILE_MB} MB)",
        type=["csv", "xlsx", "xls"],
        key=_uploader_key(),
        on_change=_on_upload,
        help="Processed in memory and never written to disk.",
        label_visibility="collapsed" if collapsed else "visible",
    )


GETS = [
    ("check", "A health score, with a practical fix for every issue"),
    ("chart", "Charts and KPIs chosen for the shape of your data"),
    ("spark", "Insights in plain words, with every number checked"),
    ("export", "A web report, Excel, PDF and a Power BI starter kit"),
]


def _empty_state() -> None:
    section_header(
        "Analyze your data",
        "Upload a file and get a health check, charts, insights and exports. Every number comes "
        "from a query you can inspect.",
        top=True,
    )
    left, right = st.columns([1.2, 1], gap="large")
    with left, st.container(key="card_start"):
        st.markdown(
            "<p class='vd-chart-title'>Upload a file</p>"
            f"<p class='vd-chart-insight'>CSV or Excel, up to {MAX_FILE_MB} MB. It stays in memory and is never "
            "stored.</p>",
            unsafe_allow_html=True,
        )
        _uploader(collapsed=True)
        st.markdown(
            "<p class='vd-gets-title'>What you get</p><ul class='vd-gets'>"
            + "".join(f"<li><span class='vd-icon'>{icon(name, 18)}</span>{esc(text)}</li>" for name, text in GETS)
            + "</ul>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<p class='vd-chart-title' style='margin-bottom:10px'>Or open an example</p>",
                    unsafe_allow_html=True)
        for ex in EXAMPLES.values():
            with st.container(key=f"card_exrow_{ex.key}"):
                text, go = st.columns([3, 1], vertical_alignment="center", gap="small")
                text.markdown(
                    f"<div class='vd-exrow'><span class='vd-icon'>{icon(ex.icon, 18)}</span><div>"
                    f"<b>{esc(ex.title)}</b><span>{esc(ex.tagline)}</span></div></div>"
                    + sparkline_svg(example_trend(ex.key), f"Trend of the {ex.title.lower()} example"),
                    unsafe_allow_html=True,
                )
                go.button("Open", key=f"start_{ex.key}", on_click=load_example, args=(ex.key,), width="stretch")
    st.caption("Works best with a tidy table: one header row and one row per record. See the Guide for tips.")


def _sidebar(prepared, file_id: str) -> tuple[str | None, str | None, str | None, bool]:
    """Render settings; returns (metric, date_col, grain, use_date)."""
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
                format_func=pretty,
                help="Picked automatically (revenue, sales, amount...). Change it any time.",
            )
        dates = [c.name for c in profile.columns if c.col_type == ColType.DATE]
        none_label = "None"
        date_choice = st.selectbox(
            "Date column",
            [*dates, none_label],
            index=dates.index(auto.date_col) if auto.date_col in dates else len(dates),
            key=f"vd_date_{file_id}",
            format_func=lambda v: "No date column" if v == none_label else pretty(v),
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
        st.markdown("#### AI features")
        st.text_input(
            "Gemini API key",
            type="password",
            key=API_KEY,
            placeholder="Optional: paste a key",
            help="Kept only in this browser session's memory. Never logged or stored.",
        )
        _, source = resolve_api_key(session_api_key())
        if source == "session":
            st.markdown(badge_html("AI on · your key", "green"), unsafe_allow_html=True)
        elif source == "secrets":
            st.markdown(badge_html("AI on · app key", "green"), unsafe_allow_html=True)
        else:
            st.caption("Optional. Adds AI-written insights and plain-English questions; everything else works without it.")

        st.divider()
        st.caption(
            "**Privacy.** Your file is processed in memory and never stored. AI sees only column "
            f"names, aggregated results and up to {CATEGORY_LABELS_FOR_AI} labels per category, never your rows."
        )
    return metric, (date_choice if use_date else None), grain, use_date


def _file_bar(source: Source, analysis, sheets: list[str], sheet_key: str) -> str | None:
    """Compact header for the loaded file. Returns the chosen sheet (if any)."""
    left, mid, right = st.columns([6, 2, 1.4], vertical_alignment="center", gap="small")
    sheet = st.session_state.get(sheet_key) if sheets else None
    with left:
        kind = "Example" if source.kind == "example" else "Your file"
        parts = [
            badge_html(kind, "teal"),
            badge_html(f"{analysis.profile.n_rows:,} rows · {analysis.profile.n_cols} columns", "slate"),
            badge_html(f"Metric: {pretty(analysis.selection.metric or 'records')}", "indigo"),
        ]
        st.markdown(
            f"<div class='vd-filebar'><span class='name'>{esc(source.name)}</span>{''.join(parts)}</div>",
            unsafe_allow_html=True,
        )
    with mid:
        if sheets:
            sheet = st.selectbox("Sheet", sheets, key=sheet_key, label_visibility="collapsed")
    with right, st.popover("Change file", width="stretch"):
        _uploader()
        st.caption("Or load an example")
        for ex in EXAMPLES.values():
            st.button(ex.title, key=f"swap_{ex.key}", on_click=load_example, args=(ex.key,), width="stretch")
        st.divider()
        st.button("Start over", key="vd_start_over", on_click=_start_over, width="stretch", type="tertiary")
    return sheet


def main() -> None:
    """Render the page. Returns early (rather than st.stop) so the site footer still renders."""
    requested = st.query_params.get("example")
    if requested in EXAMPLES and get_source() is None:
        load_example(requested)
    source = get_source()
    if source is None:
        _empty_state()
        return

    sheets: list[str] = []
    if source.name.lower().endswith(EXCEL_EXTENSIONS):
        try:
            sheets = list_excel_sheets(source.data, source.name)
        except LoadError as exc:
            callout(str(exc), title="This file could not be loaded", kind="error")
            st.button("Choose another file", on_click=_start_over)
            return
        sheets = sheets if len(sheets) > 1 else []
    sheet_key = f"vd_sheet_{file_hash(source.data)}"
    sheet = st.session_state.get(sheet_key, sheets[0] if sheets else None)

    fid = file_hash(source.data + (sheet or "").encode())
    try:
        with st.spinner("Profiling your data..."):
            prepared = cached_prepare(fid, source.name, sheet, source.data)
    except LoadError as exc:
        callout(str(exc), title="This file could not be loaded", kind="error")
        st.button("Choose another file", on_click=_start_over)
        return

    metric, date_col, grain, use_date = _sidebar(prepared, fid)
    cache_key = f"{fid}|{metric}|{date_col}|{grain}"
    with st.spinner("Running queries..."):
        analysis = cached_analysis(fid, source.name, sheet, metric, date_col, grain, use_date, source.data)

    _file_bar(source, analysis, sheets, sheet_key)
    for note in prepared.loaded.notes:
        st.caption(note)

    tabs = st.tabs([
        ":material/health_and_safety: Overview",
        ":material/bar_chart: Charts",
        ":material/lightbulb: Insights",
        ":material/forum: Ask your data",
        ":material/table_view: Data",
        ":material/download: Export",
    ])
    with tabs[0]:
        overview.render(analysis)
    with tabs[1]:
        charts_tab.render(analysis)
    with tabs[2]:
        insights_tab.render(analysis, cache_key=cache_key)
    with tabs[3]:
        ask_tab.render(analysis, file_key=fid)
    with tabs[4]:
        data_tab.render(analysis)
    with tabs[5]:
        export_tab.render(analysis, cache_key=cache_key)


main()
