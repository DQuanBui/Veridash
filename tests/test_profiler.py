"""Tests for core.profiler type detection and statistics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.profiler import ColType, parse_numeric, profile_dataframe


def _types(df: pd.DataFrame) -> dict[str, ColType]:
    return {c.name: c.col_type for c in profile_dataframe(df).columns}


def test_detects_core_types():
    n = 60
    df = pd.DataFrame(
        {
            "order_id": range(1, n + 1),
            "date": pd.date_range("2024-01-01", periods=n).astype(str),
            "region": ["North", "South", "East"] * 20,
            "revenue": np.linspace(10, 600, n),
            "returned": ["Yes", "No"] * 30,
            "notes": [f"Customer comment number {i} describing the order in detail" for i in range(n)],
        }
    )
    assert _types(df) == {
        "order_id": ColType.ID,
        "date": ColType.DATE,
        "region": ColType.CATEGORY,
        "revenue": ColType.NUMBER,
        "returned": ColType.BOOLEAN,
        "notes": ColType.TEXT,
    }


@pytest.mark.parametrize(
    ("raw", "expected", "unit"),
    [
        (["$1,234.50", "$10", "$0.99"], [1234.5, 10.0, 0.99], "currency"),
        (["(123)", "45", "-6"], [-123.0, 45.0, -6.0], None),
        (["12.5%", "50%", "0%"], [12.5, 50.0, 0.0], "percent"),
        (["€1,000", "€ 2", "€3"], [1000.0, 2.0, 3.0], "currency"),
    ],
)
def test_parse_numeric_formats(raw, expected, unit):
    values, ratio, got_unit = parse_numeric(pd.Series(raw))
    assert ratio == 1.0
    assert values.tolist() == pytest.approx(expected)
    assert got_unit == unit


def test_currency_strings_become_numbers_in_typed_frame():
    prof = profile_dataframe(pd.DataFrame({"price": ["$1,000", "$2,500", "($300)"] * 5}))
    col = prof.get("price")
    assert col.col_type == ColType.NUMBER
    assert col.unit == "currency"
    assert prof.df["price"].sum() == pytest.approx((1000 + 2500 - 300) * 5)


def test_mixed_type_column_flagged():
    values = [str(v) for v in range(1, 40)] + ["TBD"]
    col = profile_dataframe(pd.DataFrame({"unit_price": values})).get("unit_price")
    assert col.col_type == ColType.NUMBER
    assert col.mixed_type
    assert col.n_unparsed == 1


def test_numeric_id_needs_uniqueness():
    df = pd.DataFrame({"store_id": [1, 2, 3, 1, 2, 3] * 10, "customer_id": range(60)})
    types = _types(df)
    assert types["store_id"] == ColType.NUMBER
    assert types["customer_id"] == ColType.ID


def test_constant_and_missing_stats():
    df = pd.DataFrame({"currency": ["USD"] * 10, "x": [1.0, None, 3.0, None, 5.0, 6, 7, 8, 9, 10]})
    prof = profile_dataframe(df)
    assert prof.get("currency").is_constant
    x = prof.get("x")
    assert x.n_missing == 2
    assert x.missing_pct == pytest.approx(20.0)
    assert x.stats["sum"] == pytest.approx(49.0)


def test_iqr_outliers():
    values = [10.0] * 5 + [11.0] * 5 + [12.0] * 5 + [1000.0]
    col = profile_dataframe(pd.DataFrame({"v": values})).get("v")
    assert col.stats["outliers"] == 1
    assert col.stats["outlier_pct"] == pytest.approx(100 / 16)


def test_weekday_names_are_not_dates():
    assert _types(pd.DataFrame({"day": ["Mon", "Tue", "Wed"] * 10}))["day"] == ColType.CATEGORY
