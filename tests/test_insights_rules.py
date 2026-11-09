"""Tests for the fact pack and rule-based insights."""

from __future__ import annotations

import json

import pytest

from core.pipeline import analyze, prepare
from core.samples import EXAMPLES


@pytest.fixture(scope="module", params=list(EXAMPLES))
def analysis(request):
    ex = EXAMPLES[request.param]
    return analyze(prepare(ex.read_bytes(), ex.filename))


def test_structure(analysis):
    ins = analysis.rule_insights
    assert ins.source == "rules"
    assert len(ins.summary) == 3
    assert 3 <= len(ins.findings) <= 5
    assert ins.recommendations
    assert all(r.evidence and r.how_to_validate for r in ins.recommendations)
    assert ins.caveats


def test_every_citation_exists(analysis):
    ids = analysis.facts.by_id()
    assert analysis.rule_insights.cited_ids() <= set(ids)


def test_fact_ids_unique_and_pack_is_json(analysis):
    ids = [f.id for f in analysis.facts.facts]
    assert len(ids) == len(set(ids))
    payload = json.loads(analysis.facts.to_json())
    assert payload["dataset"]["rows"] == analysis.profile.n_rows


def test_fact_pack_has_no_raw_rows(analysis):
    """Only aggregates: no fact value should be an untouched raw ID/text cell."""
    raw_ids = {str(v) for c in analysis.profile.names("id", "text") for v in analysis.profile.df[c].dropna().head(200)}
    values = {str(f.value) for f in analysis.facts.facts}
    assert not raw_ids & values


def test_average_metrics_never_use_share_language():
    ex = EXAMPLES["hr"]
    a = analyze(prepare(ex.read_bytes(), ex.filename))
    assert a.selection.agg == "AVG"
    assert not any("of the total" in t for t in a.rule_insights.texts())
