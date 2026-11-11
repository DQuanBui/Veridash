"""Tests for comparing two versions of a dataset."""

from __future__ import annotations

import pandas as pd
import pytest

from core.compare import (
    AFTER,
    BEFORE,
    SIDE,
    column_diff,
    health_diff,
    metric_change,
    pick_selection,
    stacked,
)
from core.engine import QueryEngine
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


def _metric(before, after):
    diff = column_diff(before, after)
    sel = pick_selection(after, diff)
    with QueryEngine(stacked(before, after, diff.common)) as engine:
        return metric_change(engine, sel)


def test_metric_change_overall_and_by_group(pair):
    m = _metric(*pair)
    assert m.selection.metric == "revenue" and m.selection.agg == "SUM"
    assert m.before == pytest.approx(sum(100.0 + i for i in range(60)))
    assert m.after == pytest.approx(m.before * 1.1)
    assert m.change_pct == pytest.approx(10.0)
    assert m.group_col == "region"
    assert m.groups["change"].sum() == pytest.approx(m.change)  # every group shown, so they add up
    assert "\"_file\" = 'before'" in m.sql


def test_new_and_missing_groups_count_as_zero_for_totals():
    before = _prep(pd.DataFrame({"team": ["A", "B", "C"] * 5, "sales": [10.0] * 15}))
    after = _prep(pd.DataFrame({"team": ["A", "B", "D"] * 5, "sales": [10.0, 20.0, 30.0] * 5}))
    g = _metric(before, after).groups.set_index("label")
    assert g.loc["D", "before"] == 0 and g.loc["D", "after"] == 150
    assert g.loc["C", "after"] == 0 and g.loc["C", "change"] == -50
    assert "A" not in g.index  # unchanged groups are left out


def test_averages_compare_only_groups_in_both_files():
    before = _prep(pd.DataFrame({"team": ["A", "B", "C"] * 5, "satisfaction_score": [3.0, 4.0, 5.0] * 5}))
    after = _prep(pd.DataFrame({"team": ["A", "B", "D"] * 5, "satisfaction_score": [3.5, 4.0, 2.0] * 5}))
    m = _metric(before, after)
    assert m.selection.agg == "AVG"
    assert list(m.groups["label"]) == ["A"]


def test_files_without_shared_numbers_compare_record_counts():
    before = _prep(pd.DataFrame({"team": ["A", "B"] * 5}))
    after = _prep(pd.DataFrame({"team": ["A", "B", "B"] * 5}))
    m = _metric(before, after)
    assert m.selection.agg == "COUNT"
    assert (m.before, m.after) == (10, 15)
