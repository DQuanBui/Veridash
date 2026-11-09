"""Home page (placeholder until the landing page milestone)."""

import streamlit as st

from core.settings import SUBHEAD
from ui.components import footer, hero

hero("Verifiable data analysis", "Drop your data. <span>Trust every number.</span>", SUBHEAD)
st.caption("The full landing page is coming in a later milestone.")
footer()
