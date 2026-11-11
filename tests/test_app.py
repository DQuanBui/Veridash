"""Smoke tests for every page with Streamlit's AppTest (no API key)."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from core.samples import EXAMPLES

PAGES = ["views/home.py", "views/analyze.py", "views/compare.py", "views/examples.py", "views/benchmark.py",
         "views/guide.py"]


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


def test_benchmark_page_shows_published_scores():
    from bench.__main__ import load

    at = _app().run()
    at.switch_page("views/benchmark.py").run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert f"{load()['factcheck']['catch_pct']}%" in html
    assert "Another group&#x27;s number" in html or "Another group's number" in html


def test_compare_page_with_two_files():
    import pandas as pd

    from ui.state import Source

    ids = [f"E{i:04d}" for i in range(60)]
    before = pd.DataFrame({"employee_id": ids[:50], "team": ["A", "B"] * 25,
                           "salary": [50_000.0 + 100 * i for i in range(50)]})
    after = pd.DataFrame({"employee_id": ids[10:], "team": ["A", "B", "C", "D"] * 12 + ["A", "B"],
                          "salary": [52_000.0 + 100 * i for i in range(50)], "level": ["L1", "L2"] * 25})
    at = _app().run()
    at.session_state["vd_cmp_before"] = Source("jan.csv", before.to_csv(index=False).encode(), "upload")
    at.session_state["vd_cmp_after"] = Source("feb.csv", after.to_csv(index=False).encode(), "upload")
    at.switch_page("views/compare.py").run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "What changed" in html and "Verified numbers: " in html
    assert "added (level)" in html
    assert any(m.label == "New" and m.value == "10" for m in at.metric)


def test_compare_example_buttons():
    at = _app().run()
    at.switch_page("views/compare.py").run()
    at.button(key="cmp_ex_portfolio_months").click().run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "portfolio_2024_12.csv" in html and "What changed" in html
    at.button(key="cmp_reset").click().run()
    assert any(b.key == "cmp_ex_retail_years" for b in at.button)


def test_check_any_text_on_the_insights_tab():
    at = _app().run()
    at.switch_page("views/analyze.py").run()
    at.button(key="start_retail").click().run()
    area = next(t for t in at.text_area if t.key.startswith("vd_check_text_"))
    area.input("Electronics comes to $209.1K, total revenue is $785.3K and it rose 99.9%.").run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "Verified numbers: 1/3" in html
    table = next(d.value for d in at.dataframe if "Computed value" in d.value.columns)
    assert list(table["Status"]) == ["Wrong group", "Verified", "Not found"]
    assert "is the figure for Apparel, not Electronics" in html


def test_home_worksheet_rechecks_an_edited_sentence():
    at = _app().run()
    html = " ".join(m.value for m in at.markdown)
    assert "2 of 3 numbers check out." in html
    at.text_input(key="home_demo").input(
        "Revenue reached $785.3K. Electronics led with $271.4K, and revenue rose 19.6% last month."
    ).run()
    assert not at.exception, at.exception
    assert "Every number checks out." in " ".join(m.value for m in at.markdown)


def test_home_tour_switches_and_opens_compare():
    at = _app().run()
    tour = at.button_group(key="home_tour") if hasattr(at, "button_group") else None
    if tour is None:  # older AppTest: drive it through session state
        at.session_state["home_tour"] = "Compare"
    else:
        tour.set_value("Compare")
    at.run()
    assert not at.exception, at.exception
    assert "See what changed" in " ".join(m.value for m in at.markdown)
    at.button(key="tour_go_compare").click().run()
    assert not at.exception, at.exception
    assert at.session_state["vd_cmp_after"].name == "portfolio_2024_12.csv"


def test_home_offers_to_resume_an_open_file():
    at = _app().run()
    assert not any(b.key == "resume_analyze" for b in at.button)
    at.switch_page("views/analyze.py").run()
    at.button(key="start_hr").click().run()
    at.switch_page("views/home.py").run()
    assert not at.exception, at.exception
    assert "hr_workforce.xlsx" in " ".join(m.value for m in at.markdown)
    assert any(b.key == "resume_analyze" for b in at.button)


def test_actions_are_confirmed_with_a_toast():
    at = _app().run()
    at.switch_page("views/analyze.py").run()
    at.button(key="start_portfolio").click().run()
    assert not at.exception, at.exception
    assert any("Opened the example: Investment portfolio" in t.value for t in at.toast)
    at.button(key="vd_start_over").click().run()
    assert any("Cleared" in t.value for t in at.toast)


def test_start_here_guide_can_be_dismissed():
    at = _app().run()
    at.switch_page("views/analyze.py").run()
    at.button(key="start_retail").click().run()
    assert "Check the health score and issues below." in " ".join(m.value for m in at.markdown)
    at.button(key="vd_start_here_close").click().run()
    assert not at.exception, at.exception
    assert "Check the health score and issues below." not in " ".join(m.value for m in at.markdown)
