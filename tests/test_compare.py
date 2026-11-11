"""Tests for comparing two versions of a dataset."""

from __future__ import annotations

import pandas as pd
import pytest

from core.compare import (
    AFTER,
    BEFORE,
    SIDE,
    column_diff,
    compare,
    health_diff,
    metric_change,
    pick_selection,
    record_change,
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


def _records(before, after):
    diff = column_diff(before, after)
    sel = pick_selection(after, diff)
    with QueryEngine(stacked(before, after, diff.common)) as engine:
        return record_change(engine, before, after, diff, sel)


def test_records_matched_by_id():
    ids = [f"E{i:04d}" for i in range(1, 41)]
    before = pd.DataFrame({"employee_id": ids[:30], "team": ["A", "B", "C"] * 10, "salary": [50_000.0] * 30})
    after = pd.DataFrame({"employee_id": ids[5:40], "team": ["A", "B", "C", "D", "E"] * 7, "salary": [50_000.0] * 35})
    after.loc[after["employee_id"].isin(["E0010", "E0011"]), "salary"] = 55_000.0
    r = _records(_prep(before), _prep(after))
    assert r.id_col == "employee_id"
    assert (r.added, r.removed, r.kept) == (10, 5, 25)
    assert r.changed == 2
    assert r.added_examples == ["E0031", "E0032", "E0033", "E0034", "E0035"]
    assert r.removed_examples[0] == "E0001"


def test_no_id_column_means_no_record_matching(pair):
    assert _records(*pair) is None


def _split_example(key: str, mask_before, mask_after):
    from core.samples import EXAMPLES

    ex = EXAMPLES[key]
    df = prepare(ex.read_bytes(), ex.filename).profile.df
    return _prep(df[mask_before(df)], "before.csv"), _prep(df[mask_after(df)], "after.csv")


def test_summary_numbers_all_pass_the_fact_check(pair):
    from ai.factcheck import fact_check

    c = compare(*pair, "jan_2024.csv", "feb_2024.csv")
    report = fact_check(c.summary, c.facts)
    assert report.total >= 8
    assert report.verified == report.total, [x.raw for x in report.unverified]
    assert any("1 added (channel)" in s for s in c.summary)
    assert c.chart() is not None and c.chart().meta["diverging"]


def test_summary_is_fact_checked_on_the_examples():
    from ai.factcheck import fact_check

    retail = _split_example("retail", lambda d: d["date"].dt.year == 2023, lambda d: d["date"].dt.year == 2024)
    hr = _split_example("hr", lambda d: d.index < 1200, lambda d: d.index >= 300)
    for before, after in (retail, hr):
        c = compare(before, after, "before.csv", "after.csv")
        report = fact_check(c.summary, c.facts)
        assert report.verified == report.total > 0, [x.raw for x in report.unverified]
    ids_b = set(hr[0].profile.df["employee_id"].dropna())
    ids_a = set(hr[1].profile.df["employee_id"].dropna())
    r = c.records
    assert r is not None
    assert (r.added, r.removed, r.kept) == (len(ids_a - ids_b), len(ids_b - ids_a), len(ids_a & ids_b))
    assert r.changed is None  # the example has duplicate IDs, so values are not matched one to one


def test_wrong_numbers_in_a_comparison_are_caught(pair):
    from ai.factcheck import check_text

    c = compare(*pair)
    claims = check_text("Revenue went up by 25%, with 70 rows.", c.facts)
    assert not any(x.verified for x in claims)


def test_no_change_is_worded_plainly():
    df = pd.DataFrame({"team": ["A", "B"] * 5, "sales": [10.0, 20.0] * 5})
    c = compare(_prep(df), _prep(df))
    assert "Total sales is $150 in both files." in c.summary


def test_changes_that_round_to_zero_are_not_shown_as_minus_zero():
    before = pd.DataFrame({"team": ["A", "B"] * 50, "satisfaction_score": [3.552, 3.553] * 50})
    after = pd.DataFrame({"team": ["A", "B"] * 50, "satisfaction_score": [3.549, 3.551] * 50})
    c = compare(_prep(before), _prep(after))
    assert "Average satisfaction score is 3.55 in both files, once rounded." in c.summary
    assert not any("-0" in s for s in c.summary)


def test_record_counts_read_naturally():
    c = compare(_prep(pd.DataFrame({"team": ["A", "B"] * 5})), _prep(pd.DataFrame({"team": ["A", "B"] * 6})))
    assert "The number of records went from 10 to 12, a change of +2 (+20.0%)." in c.summary
