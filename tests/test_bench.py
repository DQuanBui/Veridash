"""Tests for the trust benchmark, including minimum scores the app must keep."""

from __future__ import annotations

import pytest

from bench import factcheck_bench as fb
from core.facts import Fact, FactPack


@pytest.fixture
def pack() -> FactPack:
    return FactPack(
        dataset={},
        schema=[],
        facts=[
            Fact("kpi.metric", "Total revenue", 785_312.4, "currency", "kpi"),
            Fact("top.1.label", "#1 category", "Electronics", "text", "top"),
            Fact("top.1.value", "Revenue for Electronics", 271_400.0, "currency", "top"),
            Fact("top.2.label", "#2 category", "Apparel", "text", "top"),
            Fact("top.2.value", "Revenue for Apparel", 209_100.0, "currency", "top"),
            Fact("trend.change_pct", "Change", 67.08, "percent", "trend"),
        ],
    )


def test_cases_cover_every_type(pack):
    cases = fb.build_cases("demo", pack, ["Revenue is $785.3K."])
    types = {c.type for c in cases}
    assert {"exact", "rounded", "spelled", "rule_text", "near_miss", "off_10pct", "wrong_unit",
            "digit_swap", "wrong_group", "sign_flip", "direction", "signed"} <= types


def test_corruptions_change_the_number(pack):
    for case in fb.build_cases("demo", pack, []):
        if case.type == "near_miss" and case.fact_id == "kpi.metric":
            assert "$785.6K" in case.text
        if case.type == "wrong_group" and case.fact_id == "top.1.value":
            assert case.text == "Electronics comes to $209.1K."


def test_correct_sentences_are_never_flagged(pack):
    for case in fb.build_cases("demo", pack, []):
        if not case.corrupt:
            assert not fb.flagged(case, pack), case.text


@pytest.fixture(scope="module")
def results() -> dict:
    return fb.run()


def test_example_benchmark_has_no_false_alarms(results):
    assert results["correct_sentences"] > 300
    assert results["false_alarms"] == 0


def test_example_benchmark_catches_most_errors(results):
    assert results["planted_errors"] > 500
    assert results["catch_pct"] >= 75


def test_sql_guard_blocks_every_attack_and_runs_harmless_queries():
    from bench import sql_guard_bench as sg

    r = sg.run()
    assert r["guard_blocked"] == r["attacks"] >= 30
    assert r["sandbox_blocked"] == r["sandbox_attacks"] >= 15
    assert r["harmless_ran"] == r["harmless"] >= 20
    assert r["row_cap_held"]
    assert all("{file}" not in a["sql"] for a in r["attack_rows"])


def test_crosscheck_agrees_with_pandas():
    from bench import crosscheck

    r = crosscheck.run()
    assert r["checked"] >= 150
    assert r["matched"] == r["checked"]


def test_crosscheck_catches_a_wrong_number():
    from bench.crosscheck import cross_check
    from core.pipeline import analyze, prepare
    from core.samples import EXAMPLES

    ex = EXAMPLES["retail"]
    analysis = analyze(prepare(ex.read_bytes(), ex.filename))
    top = next(c for c in analysis.charts if c.key == "top")
    fact = next(f for f in top.facts if f.id == "top.1.value")
    fact.value = float(fact.value) + 1.0
    res = cross_check("retail", analysis)
    assert [m["fact_id"] for m in res.mismatches] == ["top.1.value"]


def test_published_results_have_every_suite():
    from bench.__main__ import load, summary

    r = load()
    assert {"generated", "factcheck", "sql_guard", "crosscheck"} <= set(r)
    assert "Fact-check: caught" in summary(r)
