"""Tests for the DuckDB engine and the chart/KPI recommender."""

from __future__ import annotations

import pandas as pd
import pytest

from core.engine import QueryEngine, QueryError, quote_ident
from core.loader import load_file
from core.profiler import profile_dataframe
from core.recommender import build_kpis, make_selection, pick_metric, recommend_charts
from core.samples import EXAMPLES


@pytest.fixture(scope="module", params=list(EXAMPLES))
def analysed(request):
    ex = EXAMPLES[request.param]
    profile = profile_dataframe(load_file(ex.read_bytes(), ex.filename).df)
    sel = make_selection(profile)
    with QueryEngine(profile.df) as engine:
        kpis = build_kpis(engine, profile, sel)
        charts = recommend_charts(engine, profile, sel)
    return profile, sel, kpis, charts


def test_engine_blocks_file_access(tmp_path):
    path = tmp_path / "secret.csv"
    path.write_text("a\n1\n")
    with QueryEngine(pd.DataFrame({"a": [1]})) as engine:
        with pytest.raises(QueryError):
            engine.run(f"SELECT * FROM read_csv('{path.as_posix()}')")
        with pytest.raises(QueryError):
            engine.run("SET enable_external_access = true")


def test_engine_timeout():
    with QueryEngine(pd.DataFrame({"a": [1]})) as engine, pytest.raises(QueryError, match="longer than"):
        engine.run("SELECT COUNT(*) FROM range(100000000000) t(i) WHERE i % 7 = 3", timeout_s=0.2)


def test_engine_row_cap_and_quoting():
    df = pd.DataFrame({'weird "name"': range(50)})
    with QueryEngine(df) as engine:
        res = engine.run(f"SELECT {quote_ident(df.columns[0])} FROM data", max_rows=10)
    assert len(res.df) == 10 and res.truncated


def test_every_chart_sql_runs_and_returns_the_same_data(analysed):
    profile, _, _, charts = analysed
    assert 4 <= len(charts) <= 8
    with QueryEngine(profile.df) as engine:
        for chart in charts:
            fresh = engine.run(chart.sql).df
            assert not fresh.empty, chart.key
            assert fresh.shape == chart.data.shape, chart.key
            assert chart.insight, chart.key
            assert chart.facts, chart.key


def test_kpi_sql_runs(analysed):
    profile, _, kpis, _ = analysed
    assert 3 <= len(kpis) <= 4
    with QueryEngine(profile.df) as engine:
        for kpi in kpis:
            assert not engine.run(kpi.sql).df.empty, kpi.key


def test_ids_never_charted(analysed):
    profile, sel, _, charts = analysed
    ids = set(profile.names("id"))
    assert not ids & set(sel.numerics)
    for chart in charts:
        assert chart.x not in ids and chart.y not in ids


def test_retail_picks_revenue_and_monthly_trend():
    ex = EXAMPLES["retail"]
    profile = profile_dataframe(load_file(ex.read_bytes(), ex.filename).df)
    sel = make_selection(profile)
    assert (sel.metric, sel.agg, sel.date_col, sel.grain) == ("revenue", "SUM", "date", "month")
    assert pick_metric(profile, override="units") == "units"
    assert make_selection(profile, grain="quarter").grain == "quarter"


def test_total_matches_pandas():
    ex = EXAMPLES["retail"]
    profile = profile_dataframe(load_file(ex.read_bytes(), ex.filename).df)
    sel = make_selection(profile)
    with QueryEngine(profile.df) as engine:
        kpis = {k.key: k for k in build_kpis(engine, profile, sel)}
    assert kpis["metric"].value == pytest.approx(profile.df["revenue"].sum())
    assert kpis["records"].value == len(profile.df)


def _drivers_for(df: pd.DataFrame, metric: str | None = None, grain: str = "month"):
    profile = profile_dataframe(df)
    sel = make_selection(profile, metric=metric, grain=grain)
    with QueryEngine(profile.df) as engine:
        charts = recommend_charts(engine, profile, sel)
    return sel, next((c for c in charts if c.key == "drivers"), None)


def _monthly_sales() -> pd.DataFrame:
    rows = []
    for month, amounts in {"2024-01-15": (100, 50, 30), "2024-02-15": (160, 20, 30), "2024-03-15": (200, 10, 45)}.items():
        for region, amount in zip(("East", "West", "North"), amounts, strict=True):
            rows.append({"date": month, "region": region, "revenue": float(amount)})
    rows.append({"date": "2024-03-31", "region": "East", "revenue": 0.0})  # keeps March complete
    return pd.DataFrame(rows)


def test_drivers_add_up_to_the_total_change():
    _, spec = _drivers_for(_monthly_sales())
    assert spec is not None and spec.kind == "bar" and spec.meta["diverging"]
    facts = {f.id: f.value for f in spec.facts}
    assert facts["drivers.last_period"] == "Mar 2024" and facts["drivers.prev_period"] == "Feb 2024"
    assert facts["drivers.total_change"] == pytest.approx(255 - 210)
    assert spec.data["change"].sum() == pytest.approx(facts["drivers.total_change"])
    # Largest mover first, and decreases are kept with their sign.
    assert list(spec.data["region"]) == ["East", "North", "West"]
    assert facts["drivers.3.change"] == pytest.approx(-10)
    assert "East moved the most (+$40)" in spec.insight
    assert "West pulled the other way (-$10)" in spec.insight


def test_drivers_skip_averages_and_files_without_dates():
    df = _monthly_sales().rename(columns={"revenue": "satisfaction_score"})
    sel, spec = _drivers_for(df, metric="satisfaction_score")
    assert sel.agg == "AVG" and spec is None
    _, spec = _drivers_for(_monthly_sales().drop(columns="date"))
    assert spec is None


def test_drivers_text_passes_the_fact_check():
    from ai.factcheck import fact_check
    from core.pipeline import analyze, prepare

    ex = EXAMPLES["retail"]
    analysis = analyze(prepare(ex.read_bytes(), ex.filename))
    spec = next(c for c in analysis.charts if c.key == "drivers")
    texts = [spec.insight, *[s.text for s in analysis.rule_insights.findings if "changed by" in s.text]]
    assert len(texts) == 2
    report = fact_check(texts, analysis.facts)
    assert report.total and not report.unverified
