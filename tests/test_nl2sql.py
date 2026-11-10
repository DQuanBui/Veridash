"""Tests for the Ask-your-data SQL validator and question flow."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from ai.client import GeminiClient
from ai.nl2sql import (
    SQLValidationError,
    ask,
    example_questions,
    run_validated,
    schema_context,
    starter_queries,
    validate_sql,
)
from core.engine import QueryEngine
from core.pipeline import analyze, prepare
from core.samples import EXAMPLES


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT region, SUM(revenue) FROM data GROUP BY 1",
        "WITH t AS (SELECT * FROM data) SELECT COUNT(*) FROM t",
        "select * from data where store = 'load; drop'",  # keywords inside literals are fine
        'SELECT "set" FROM data',  # and inside quoted identifiers
        "SELECT replace(region, 'a', 'b') FROM data",
        "SELECT 1;",
    ],
)
def test_accepts_safe_selects(sql):
    out = validate_sql(sql)
    assert out.rstrip().upper().endswith(("LIMIT 1000",)) or "limit" in out.lower()


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("DROP TABLE data", "Only SELECT"),
        ("DELETE FROM data", "Only SELECT"),
        ("INSERT INTO data VALUES (1)", "Only SELECT"),
        ("SELECT 1; DROP TABLE data", "one statement"),
        ("SELECT 1; SELECT 2", "one statement"),
        ("ATTACH 'x.db'", "Only SELECT"),
        ("SELECT * FROM data -- sneaky", "Comments"),
        ("SELECT * FROM read_csv('secret.csv')", "read_csv"),
        ("SELECT * FROM read_parquet('s3://bucket/x')", "read_parquet"),
        ("SELECT * FROM 'secret.csv'", "files or URLs"),
        ("SELECT * FROM query('DROP TABLE data')", "query"),
        ("SELECT getenv('HOME')", "getenv"),
        ("WITH x AS (SELECT 1) COPY data TO 'out.csv'", "COPY"),
        ("SELECT * FROM data; PRAGMA database_list", "one statement"),
        ("SELECT * FRM data", "parsed"),
        ("", "empty"),
    ],
)
def test_rejects_unsafe_or_invalid(sql, message):
    with pytest.raises(SQLValidationError, match=message):
        validate_sql(sql)


def test_limit_added_and_capped():
    assert validate_sql("SELECT * FROM data").endswith("\nLIMIT 1000")
    assert validate_sql("SELECT * FROM data LIMIT 50").endswith("LIMIT 50")
    capped = validate_sql("SELECT * FROM data WHERE x = 'it''s' LIMIT 999999")
    assert capped.endswith("LIMIT 1000")
    assert "'it''s'" in capped


def test_run_validated_executes_exact_sql():
    with QueryEngine(pd.DataFrame({"a": range(3000)})) as engine:
        res = run_validated(engine, "SELECT a FROM data ORDER BY a")
    assert res.error is None
    assert res.sql.endswith("LIMIT 1000")
    assert len(res.data) == 1000


@pytest.fixture(scope="module")
def retail():
    ex = EXAMPLES["retail"]
    return analyze(prepare(ex.read_bytes(), ex.filename))


def test_schema_context_has_labels_not_rows(retail):
    ctx = schema_context(retail.profile)
    region = next(c for c in ctx["columns"] if c["name"] == "region")
    assert 1 <= len(region["labels"]) <= 10
    assert all("labels" not in c for c in ctx["columns"] if c["type"] in ("number", "date"))
    assert "rows" in ctx and isinstance(ctx["rows"], int)


def test_example_questions(retail):
    qs = example_questions(retail.selection)
    assert len(qs) == 3
    assert all(q.endswith("?") for q in qs)


def _fake_client(payload: dict) -> GeminiClient:
    fake = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_: SimpleNamespace(text=json.dumps(payload))))
    return GeminiClient("k", "m", {}, client_factory=lambda key: fake)


def test_ask_end_to_end_with_fake_model(retail):
    client = _fake_client({"sql": 'SELECT "region", SUM("revenue") AS total FROM data GROUP BY 1 ORDER BY 2 DESC',
                           "explanation": "Total revenue by region."})
    with QueryEngine(retail.profile.df) as engine:
        res = ask(client, engine, retail.profile, "Revenue by region?")
    assert res.error is None
    assert len(res.data) == 6  # 5 regions plus the group of rows with a missing region
    assert res.data["total"].sum() == pytest.approx(retail.profile.df["revenue"].sum())


def test_ask_blocks_malicious_model_output(retail):
    client = _fake_client({"sql": "COPY data TO 'stolen.csv'", "explanation": "x"})
    with QueryEngine(retail.profile.df) as engine:
        res = ask(client, engine, retail.profile, "Export everything")
    assert res.error and res.data.empty


@pytest.mark.parametrize("key", list(EXAMPLES))
def test_starter_queries_validate_and_run(key):
    ex = EXAMPLES[key]
    analysis = analyze(prepare(ex.read_bytes(), ex.filename))
    starters = starter_queries(analysis.profile, analysis.selection)
    assert 3 <= len(starters) <= 5
    with QueryEngine(analysis.profile.df) as engine:
        for starter in starters:
            res = run_validated(engine, starter.sql, starter.question)
            assert res.error is None, (starter.question, res.error)
            assert not res.data.empty


def test_missing_values_starter_counts_blanks():
    from core.loader import load_file
    from core.profiler import profile_dataframe
    from core.recommender import make_selection

    data = b"city,amount\nParis,1\n,2\nRome,\nRome,4\n"
    profile = profile_dataframe(load_file(data, "x.csv").df)
    starter = next(s for s in starter_queries(profile, make_selection(profile)) if s.question.startswith("Missing"))
    with QueryEngine(profile.df) as engine:
        res = run_validated(engine, starter.sql)
    assert dict(zip(res.data["column_name"], res.data["missing"], strict=True)) == {"amount": 1, "city": 1}
