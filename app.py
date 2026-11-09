"""Veridash entry point: page config, theme and navigation."""

from __future__ import annotations

import streamlit as st

from core.settings import APP_NAME

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="auto")

pages = [
    st.Page("pages/home.py", title="Home", default=True, url_path="home"),
    st.Page("pages/analyze.py", title="Analyze", url_path="analyze"),
    st.Page("pages/examples.py", title="Examples", url_path="examples"),
    st.Page("pages/guide.py", title="Guide", url_path="guide"),
    st.Page("pages/about.py", title="About", url_path="about"),
]

st.navigation(pages, position="top").run()
