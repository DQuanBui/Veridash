"""End-to-end pipeline tests: edge-case shapes, sampling and format round-trips."""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from ai.factcheck import check_text
from core import recommender
from core.facts import Fact, FactPack
from core.formatting import fmt_signed_pct, fmt_value
from core.pipeline import analyze, prepare
from exports.excel import build_excel
from exports.pdf import build_pdf
from exports.powerbi import build_powerbi_kit


def _csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


rng = np.random.default_rng(7)
EDGE_CASES = {
    "only_categories": pd.DataFrame({"city": ["A", "B", "C", "A"] * 10, "tier": ["x", "y"] * 20}),
    "single_numeric": pd.DataFrame({"amount": rng.normal(100, 10, 50)}),
    "no_date_two_numbers": pd.DataFrame({"price": rng.uniform(1, 9, 60), "units": rng.integers(1, 5, 60)}),
    "tiny": pd.DataFrame({"date": ["2024-01-01"], "sales": [10.0], "region": ["East"]}),
    "constant_metric": pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30).astype(str), "value": [5.0] * 30}),
    "weird_names": pd.DataFrame({'Sales "Q1"': [1.0, 2.0, 3.0] * 5, "Région ]x[": ["a", "b", "c"] * 5}),
    "all_missing_numeric": pd.DataFrame({"x": [None] * 10, "label": list("abcdefghij")}),
}


@pytest.mark.parametrize("name", list(EDGE_CASES))
def test_edge_cases_run_through_pipeline_and_exports(name):
    analysis = analyze(prepare(_csv(EDGE_CASES[name]), f"{name}.csv"))
    assert analysis.kpis, name
    assert analysis.rule_insights.summary, name
    assert build_excel(analysis)[:2] == b"PK"
    assert build_pdf(analysis).startswith(b"%PDF")
    assert "measures.dax" in zipfile.ZipFile(io.BytesIO(build_powerbi_kit(analysis))).namelist()


def test_rule_insights_always_fully_verified_on_edge_cases():
    from ai.factcheck import fact_check

    for name, df in EDGE_CASES.items():
        analysis = analyze(prepare(_csv(df), f"{name}.csv"))
        report = fact_check(analysis.rule_insights.texts(), analysis.facts)
        assert report.verified == report.total, (name, [c.raw for c in report.unverified])


def test_large_files_sample_heavy_visuals_but_not_kpis(monkeypatch):
    monkeypatch.setattr(recommender, "HEAVY_VISUAL_ROW_LIMIT", 500)
    monkeypatch.setattr(recommender, "SCATTER_MAX_POINTS", 300)
    n = 3_000
    df = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=n, freq="h").astype(str),
            "revenue": rng.lognormal(3, 1, n).round(2),
            "cost": rng.lognormal(2.5, 1, n).round(2),
            "units": rng.integers(1, 100, n),
        }
    )
    analysis = analyze(prepare(_csv(df), "big.csv"))
    dist = next(c for c in analysis.charts if c.key == "distribution")
    assert any(n.startswith("Sampled 500") for n in dist.notes)
    assert "USING SAMPLE" in dist.sql
    assert int(dist.data["records"].sum()) == 500
    scatter = next(c for c in analysis.charts if c.key == "scatter")
    assert len(scatter.data) == 300
    kpi = next(k for k in analysis.kpis if k.key == "metric")
    assert kpi.value == pytest.approx(df["revenue"].sum())


@pytest.mark.parametrize(
    "value", [0.0, 0.5, 3.14159, 12.0, 999.994, 1_234.5, 98_765.4, 123_456.0, 7_654_321.0, 2_500_000_000.0, -4_321.0]
)
@pytest.mark.parametrize("kind", ["number", "currency", "percent", "int"])
def test_every_formatted_value_verifies_against_its_fact(value, kind):
    pack = FactPack({}, [], [Fact("x", "x", value, kind)])
    text = f"The value is {fmt_value(value, kind)}."
    claims = check_text(text, pack)
    assert claims and all(c.verified for c in claims), (text, claims)


def test_signed_percent_verifies():
    pack = FactPack({}, [], [Fact("c", "change", -12.345, "percent")])
    assert all(c.verified for c in check_text(f"Revenue changed {fmt_signed_pct(-12.345)}.", pack))
