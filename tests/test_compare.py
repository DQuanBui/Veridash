"""Tests for comparing two versions of a dataset."""

from __future__ import annotations

import pandas as pd
import pytest

from core.compare import AFTER, BEFORE, SIDE, column_diff, health_diff, stacked
from core.pipeline import prepare


def _prep(df: pd.DataFrame, name: str = "file.csv"):
    return prepare(df.to_csv(index=False).encode(), name)


@pytest.fixture
def pair():
    before = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="D"),
        "region": ["East", "West", "North"] * 20,
        "revenue": [100.0 + i for i in range(60)],
        "notes": ["ok"] * 60,
        "code": [str(i) for i in range(60)],
    })
    after = before.drop(columns=["notes"]).assign(
        revenue=lambda d: d["revenue"] * 1.1,
        channel=["Web", "Store"] * 30,
        code=["A" + str(i) for i in range(60)],
    )
    return _prep(before, "jan.csv"), _prep(after, "feb.csv")


def test_column_diff_finds_added_removed_and_retyped(pair):
    diff = column_diff(*pair)
    assert diff.added == ["channel"]
    assert diff.removed == ["notes"]
    assert [name for name, _, _ in diff.retyped] == ["code"]
    assert {"date", "region", "revenue"} <= set(diff.common)
    assert not diff.unchanged


def test_identical_files_have_no_column_changes(pair):
    diff = column_diff(pair[0], pair[0])
    assert diff.unchanged


def test_health_diff_reports_both_scores(pair):
    dirty = pd.DataFrame({"region": ["East", None, "West", None] * 10, "revenue": [1.0, 2.0, None, 4.0] * 10})
    clean = dirty.fillna({"region": "East", "revenue": 0.0})
    h = health_diff(_prep(dirty), _prep(clean))
    assert h.after > h.before
    assert "Missing cells" in h.better
    assert h.worse == []


def test_stacked_marks_each_side(pair):
    diff = column_diff(*pair)
    df = stacked(*pair, diff.common)
    assert list(df[SIDE].unique()) == [BEFORE, AFTER]
    assert len(df) == 120
    assert SIDE not in diff.common
