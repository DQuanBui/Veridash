"""Smoke tests for every page with Streamlit's AppTest (no API key)."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from core.samples import EXAMPLES

PAGES = ["views/home.py", "views/analyze.py", "views/examples.py", "views/guide.py", "views/about.py"]


def _app() -> AppTest:
    return AppTest.from_file("../app.py", default_timeout=120)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_errors(page):
    at = _app().run()
    at.switch_page(page).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]


@pytest.mark.parametrize("example", [e.title for e in EXAMPLES.values()])
def test_analyze_each_example_end_to_end(example):
    at = _app().run()
    at.switch_page("views/analyze.py").run()
    at.selectbox(key="vd_example_pick").select(example).run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 6
    # Overview metrics rendered and the locked Ask state is shown without a key
    assert any(m.label == "Rows" for m in at.metric)
    assert any(e.label.startswith("Write SQL yourself") for e in at.expander)
