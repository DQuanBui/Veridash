"""Veridash entry point: page config, theme and navigation.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import threading
from pathlib import Path

import streamlit as st

from ui.freshness import refresh_changed_modules


@st.cache_resource
def _code_state() -> dict:
    """Lives for the whole server process, across reruns and sessions."""
    return {"lock": threading.Lock()}


# After a deploy, load the new versions of the project's modules before importing them, and drop
# results cached by the old code (for example, the examples' analyses) so every page shows the new version.
if refresh_changed_modules(Path(__file__).resolve().parent, _code_state()):
    st.cache_data.clear()

from core.settings import APP_NAME, ASSETS_DIR  # noqa: E402
from ui.components import footer  # noqa: E402
from ui.state import show_notices  # noqa: E402
from ui.theme import apply_theme  # noqa: E402

st.set_page_config(
    page_title=f"{APP_NAME} · Verifiable data analysis",
    page_icon=str(ASSETS_DIR / "icon.png"),
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={"Get help": None, "Report a bug": None, "About": None},
)
apply_theme()
show_notices()
st.logo(str(ASSETS_DIR / "logo.svg"), icon_image=str(ASSETS_DIR / "mark.svg"), size="large")

pages = [
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/analyze.py", title="Analyze", icon=":material/query_stats:", url_path="analyze"),
    st.Page("views/compare.py", title="Compare", icon=":material/compare_arrows:", url_path="compare"),
    st.Page("views/examples.py", title="Examples", icon=":material/dataset:", url_path="examples"),
    st.Page("views/benchmark.py", title="Benchmark", icon=":material/verified:", url_path="benchmark"),
    st.Page("views/guide.py", title="Guide", icon=":material/menu_book:", url_path="guide"),
]

st.navigation(pages, position="top").run()
footer()  # one footer, at the bottom of every page
