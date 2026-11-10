"""Tests for core.health scoring and issue detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.health import FIX, HEALTH_WEIGHTS, assess_health, grade_for
from core.loader import load_file
from core.profiler import profile_dataframe


def _health(df: pd.DataFrame):
    return assess_health(profile_dataframe(df))


def test_clean_data_scores_100():
    df = pd.DataFrame({"a": np.arange(50, dtype=float), "b": ["x", "y"] * 25})
    report = _health(df)
    assert report.score == 100
    assert report.grade == "A"
    assert [i for i in report.issues if i.severity != "info"] == []


def test_missing_penalty_matches_formula():
    a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, None, None]
    df = pd.DataFrame({"a": a, "b": list(range(10))})
    report = _health(df)
    # 2 of 20 cells missing = 10% -> 10 * 1.5 = 15 points
    check = next(c for c in report.checks if c.key == "missing_cells")
    assert check.measure == pytest.approx(10.0)
    assert check.penalty == pytest.approx(15.0)
    assert report.score == 85
    assert report.grade == "B"


def test_duplicates_detected():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 1], "b": ["x", "y", "z", "w", "x"]})
    report = _health(df)
    assert report.duplicate_rows == 1
    assert any(i.check == "duplicate_rows" for i in report.issues)


def test_penalties_are_capped():
    df = pd.DataFrame({"a": [None] * 9 + [1.0], "b": [None] * 9 + ["x"]})
    check = next(c for c in _health(df).checks if c.key == "missing_cells")
    assert check.penalty == HEALTH_WEIGHTS["missing_cells"]["cap"]


def test_constant_mixed_and_outlier_issues():
    df = pd.DataFrame(
        {
            "currency": ["USD"] * 40,
            "price": [str(v) for v in range(1, 40)] + ["TBD"],
            "spiky": [1.0] * 30 + [2.0] * 7 + [500.0, 600.0, 700.0],
        }
    )
    checks = {i.check for i in _health(df).issues}
    assert {"constant_columns", "mixed_types", "outlier_columns"} <= checks


@pytest.mark.parametrize(("score", "grade"), [(100, "A"), (90, "A"), (89, "B"), (75, "C"), (60, "D"), (12, "F")])
def test_grades(score, grade):
    assert grade_for(score) == grade


def test_every_actionable_issue_has_a_fix():
    assert set(FIX) == set(HEALTH_WEIGHTS)
    data = b"id,amount,flag,note\n1,10,x,TBD\n1,10,x,TBD\n2,,x,ok\n3,1000000,x,5\n4,12,x,6\n5,11,x,7\n"
    report = assess_health(profile_dataframe(load_file(data, "f.csv").df))
    actionable = [i for i in report.issues if i.severity != "info"]
    assert actionable and all(i.fix for i in actionable)
    assert all(i.fix == "" for i in report.issues if i.check == "id_columns")
