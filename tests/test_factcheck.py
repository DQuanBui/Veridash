"""Tests for number extraction and verification against the fact pack."""

from __future__ import annotations

import pytest

from ai.factcheck import check_text, extract_numbers, fact_check, highlight_html
from core.facts import Fact, FactPack


@pytest.fixture
def pack() -> FactPack:
    return FactPack(
        dataset={},
        schema=[],
        facts=[
            Fact("kpi.metric", "Total revenue", 785_312.4, "currency", "kpi"),
            Fact("kpi.records", "Records", 5000, "int", "kpi"),
            Fact("top.1.share_pct", "Share", 34.6123, "percent", "top"),
            Fact("trend.change_pct", "Change", -1.083, "percent", "trend"),
            Fact("corr.a~b", "r", 0.7712, "ratio", "correlation"),
            Fact("trend.first_period", "First month", "Jan 2023", "text", "trend"),
            Fact("top.1.label", "Top store", "Store 01", "text", "top"),
            Fact("dataset.date_start", "Start", "2023-01-01", "date", "dataset"),
            Fact("dataset.date_end", "End", "2024-12-31", "date", "dataset"),
        ],
    )


def _status(text: str, pack: FactPack) -> list[tuple[str, bool]]:
    return [(c.raw, c.verified) for c in check_text(text, pack)]


def test_verified_numbers_in_many_formats(pack):
    text = "Revenue was $785.3K ($0.79M, 785,312) across 5,000 records; the top share was 34.6%."
    status = _status(text, pack)
    assert len(status) == 5
    assert all(ok for _, ok in status)


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("Electronics holds 35% of revenue.", True),  # rounded to a whole percent
        ("Electronics holds 34.61% of revenue.", True),
        ("Electronics holds 35.0% of revenue.", False),  # claimed precision is wrong
        ("Satisfaction fell 1.1% overall.", True),  # sign-insensitive
        ("Correlation r = 0.77.", True),
        ("Revenue was $790K.", False),
        ("Revenue was $785K.", True),
    ],
)
def test_rounding_cases(pack, text, ok):
    status = _status(text, pack)
    assert status
    assert all(v == ok for _, v in status)


def test_unverified_numbers_are_flagged(pack):
    report = fact_check(["Revenue will grow 12.5% next year to $999,999."], pack)
    assert report.total == 2
    assert report.verified == 0
    assert {c.raw for c in report.unverified} == {"12.5%", "$999,999"}


def test_percent_only_matches_percent_facts(pack):
    # 5000 exists as a count, but "5000%" is a different claim.
    assert _status("A 5000% jump.", pack) == [("5000%", False)]


def test_labels_ids_and_dates_are_not_counted_as_numbers(pack):
    claims = extract_numbers("Store 01 led in Jan 2023 (see kpi.metric); code B6 and 12pk items.", pack)
    assert claims == []


def test_years_and_dates_checked_against_range(pack):
    text = "Growth from 2023 to 2024 continued, peaking on 2024-03-05; 2031 is a forecast."
    assert _status(text, pack) == [("2023", True), ("2024", True), ("2024-03-05", True), ("2031", False)]


def test_highlight_escapes_and_marks(pack):
    text = "<b>34.6%</b> and 12.5%"
    out = highlight_html(text, check_text(text, pack))
    assert "&lt;b&gt;" in out
    assert 'class="vd-num-ok"' in out
    assert 'class="vd-num-bad"' in out


def test_unverified_numbers_are_announced_to_screen_readers(pack):
    text = "Revenue is $1,234 and a made-up 99.9%."
    out = highlight_html(text, check_text(text, pack))
    assert out.count('class="vd-sr"') == sum(not c.verified for c in check_text(text, pack)) >= 1
    assert "(not verified)" in out
