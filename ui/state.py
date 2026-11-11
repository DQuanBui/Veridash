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
from core.samples import EXAMPLES, compare_example_files
from core.settings import CACHE_TTL_S

SOURCE_KEY = "vd_source"
COMPARE_KEYS = {"before": "vd_cmp_before", "after": "vd_cmp_after"}
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


def load_compare_example(key: str) -> None:
    """Put a compare example's before and after files on the Compare page."""
    (name_b, data_b), (name_a, data_a) = compare_example_files(key)
    st.session_state[COMPARE_KEYS["before"]] = Source(name_b, data_b, "example", key)
    st.session_state[COMPARE_KEYS["after"]] = Source(name_a, data_a, "example", key)


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


def example_trend(key: str) -> list[float]:
    """The values of an example's trend chart (empty if it has none)."""
    from core.loader import file_hash

    ex = EXAMPLES[key]
    data = ex.read_bytes()
    analysis = cached_analysis(file_hash(data), ex.filename, None, None, None, None, True, data)
    trend = next((c for c in analysis.charts if c.key == "trend"), None)
    return [] if trend is None else [float(v) for v in trend.data[trend.y]]


def session_api_key() -> str | None:
    """The user's own Gemini key, if they entered one (session only)."""
    key = st.session_state.get(API_KEY)
    return key.strip() if isinstance(key, str) and key.strip() else None
