"""Veridash entry point: page config, theme and navigation.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from core.settings import APP_NAME, ASSETS_DIR
from ui.theme import apply_theme

st.set_page_config(
    page_title=f"{APP_NAME} · Verifiable data analysis",
    page_icon=str(ASSETS_DIR / "icon.png"),
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={"Get help": None, "Report a bug": None, "About": None},
)
apply_theme()
st.logo(str(ASSETS_DIR / "logo.svg"), icon_image=str(ASSETS_DIR / "mark.svg"), size="large")

pages = [
    st.Page("views/home.py", title="Home", default=True),
    st.Page("views/analyze.py", title="Analyze", url_path="analyze"),
    st.Page("views/examples.py", title="Examples", url_path="examples"),
    st.Page("views/guide.py", title="Guide", url_path="guide"),
    st.Page("views/about.py", title="About", url_path="about"),
]

st.navigation(pages, position="top").run()
