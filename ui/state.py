"""Session state and caching helpers for the Analyze flow.

Uploaded bytes live only in ``st.session_state`` (server memory for this
browser session). Analysis results are cached in memory with ``st.cache_data``
keyed on the file's SHA-256 fingerprint, so reruns are instant and identical
files are never re-processed. Nothing is written to disk.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from core.pipeline import Analysis, Prepared, analyze, prepare
from core.samples import EXAMPLES
from core.settings import CACHE_TTL_S

SOURCE_KEY = "vd_source"
API_KEY = "vd_api_key"


@dataclass
class Source:
    """The file currently being analyzed."""

    name: str
    data: bytes
    kind: str  # "upload" | "example"
    example_key: str | None = None


def get_source() -> Source | None:
    """Return the active source, if any."""
    return st.session_state.get(SOURCE_KEY)


def set_source(source: Source | None) -> None:
    """Replace the active source (``None`` clears it)."""
    if source is None:
        st.session_state.pop(SOURCE_KEY, None)
    else:
        st.session_state[SOURCE_KEY] = source


def load_example(key: str) -> None:
    """Make a bundled example the active source."""
    ex = EXAMPLES[key]
    set_source(Source(name=ex.filename, data=ex.read_bytes(), kind="example", example_key=key))


@st.cache_data(ttl=CACHE_TTL_S, max_entries=8, show_spinner=False)
def cached_prepare(file_hash: str, filename: str, sheet: str | None, _data: bytes) -> Prepared:
    """Load + profile + health check, cached by file fingerprint."""
    return prepare(_data, filename, sheet)


@st.cache_data(ttl=CACHE_TTL_S, max_entries=16, show_spinner=False)
def cached_analysis(
    file_hash: str,
    filename: str,
    sheet: str | None,
    metric: str | None,
    date_col: str | None,
    grain: str | None,
    use_date: bool,
    _data: bytes,
) -> Analysis:
    """Full analysis for one set of sidebar choices, cached."""
    prepared = cached_prepare(file_hash, filename, sheet, _data)
    return analyze(prepared, metric=metric, date_col=date_col, grain=grain, use_date=use_date)


def session_api_key() -> str | None:
    """The user's own Gemini key, if they entered one (session only)."""
    key = st.session_state.get(API_KEY)
    return key.strip() if isinstance(key, str) and key.strip() else None
