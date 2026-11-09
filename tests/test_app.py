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
    key = next(k for k, e in EXAMPLES.items() if e.title == example)
    at.button(key=f"start_{key}").click().run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 6
    # Overview metrics rendered and the locked Ask state is shown without a key
    assert any(m.label == "Rows" for m in at.metric)
    assert any(e.label.startswith("Write SQL yourself") for e in at.expander)


def test_change_file_menu_switches_example():
    at = _app().run()
    at.switch_page("views/analyze.py").run()
    at.button(key="start_retail").click().run()
    at.button(key="swap_portfolio").click().run()
    assert not at.exception, at.exception
    assert any("investment_portfolio.csv" in m.value for m in at.markdown)
    at.button(key="vd_start_over").click().run()
    assert any(b.key == "start_hr" for b in at.button)
