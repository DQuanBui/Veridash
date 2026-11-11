"""Tests for the Home page worksheet that marks up a checked sentence."""

from __future__ import annotations

from ai.factcheck import check_text
from core.facts import Fact, FactPack
from ui.worksheet import worksheet_html

PACK = FactPack(
    dataset={},
    schema=[],
    facts=[
        Fact("kpi.metric", "Total revenue", 785_312.4, "currency", "kpi"),
        Fact("top.1.label", "#1 category", "Electronics", "text", "top"),
        Fact("top.1.value", "Revenue for Electronics", 271_400.0, "currency", "top"),
        Fact("top.2.label", "#2 category", "Apparel", "text", "top"),
        Fact("top.2.value", "Revenue for Apparel", 209_100.0, "currency", "top"),
        Fact("kpi.period_change", "Latest month vs prior", 19.6, "percent", "kpi"),
    ],
)


def _sheet(text: str) -> str:
    return worksheet_html(text, check_text(text, PACK), "the retail example")


def test_ticks_circles_and_margin_notes():
    out = _sheet("Revenue reached $785.3K. Electronics led with $209.1K, and revenue rose 19.6% last month.")
    assert out.count('class="ok"') == 2 and out.count('class="bad"') == 1
    assert "$209.1K is the figure for Apparel, not Electronics" in out
    assert "2 of 3 numbers check out." in out
    assert out.count("(verified)") == 2 and "(not verified)" in out  # screen readers hear the result


def test_fixed_sentence_checks_out():
    out = _sheet("Electronics led with $271.4K and revenue rose 19.6%.")
    assert "Every number checks out." in out and 'class="notes"' not in out


def test_wrong_direction_and_unknown_numbers_get_plain_notes():
    out = _sheet("Revenue fell 19.6% to $123.4K.")
    assert "19.6% is real, but the change went the other way" in out
    assert "$123.4K is not a figure from this file" in out


def test_visitor_text_is_escaped():
    out = _sheet('<img src=x onerror="alert(1)"> $785.3K')
    assert "<img" not in out and "&lt;img" in out


def test_empty_sentence_invites_input():
    assert "No numbers to check yet." in _sheet("Nothing to see here.")
