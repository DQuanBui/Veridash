"""Tests for the Gemini client wrapper and AI insights (no network calls)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai.client import CALLS_KEY, AIError, GeminiClient
from ai.factcheck import fact_check
from ai.insights_ai import build_prompt, generate_ai_insights, parse_insights
from core.pipeline import analyze, prepare
from core.samples import EXAMPLES


class FakeError(Exception):
    """Mimics google.genai.errors.APIError (has a ``code``)."""

    def __init__(self, code: int) -> None:
        super().__init__(f"HTTP {code}")
        self.code = code


class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


def make_client(outcomes, counter=None, max_calls=10):
    fake = SimpleNamespace(models=FakeModels(outcomes))
    client = GeminiClient(
        "k",
        "test-model",
        counter if counter is not None else {},
        max_calls=max_calls,
        client_factory=lambda key: fake,
        sleep=lambda s: None,
    )
    return client, fake.models


@pytest.fixture(scope="module")
def retail():
    ex = EXAMPLES["retail"]
    return analyze(prepare(ex.read_bytes(), ex.filename))


def _payload(analysis) -> dict:
    f = analysis.facts.by_id()
    return {
        "summary": [
            {"text": f"Total revenue is {f['kpi.metric'].display}.", "fact_ids": ["kpi.metric"]},
            {"text": f"There are {f['dataset.rows'].display} records.", "fact_ids": ["dataset.rows"]},
            {"text": "Electronics leads.", "fact_ids": ["top.1.label", "made.up"]},
        ],
        "findings": [{"text": f"Health score is {f['health.score'].display}.", "fact_ids": ["health.score"]}] * 3,
        "recommendations": [{"hypothesis": "H", "evidence": "E", "how_to_validate": "V", "fact_ids": ["kpi.metric"]}] * 2,
        "caveats": ["Duplicates exist.", "Revenue may grow 12.5% next year."],
    }


def test_retries_then_succeeds():
    client, models = make_client([FakeError(503), FakeError(429), json.dumps({"ok": True})])
    assert client.generate_json("p", {}, "s") == {"ok": True}
    assert models.calls == 3
    assert client.calls_used == 1


def test_non_retryable_error_is_friendly():
    client, models = make_client([FakeError(404)])
    with pytest.raises(AIError, match="model was not found"):
        client.generate_json("p", {}, "s")
    assert models.calls == 1


def test_session_budget_enforced():
    client, _ = make_client([json.dumps({})], counter={CALLS_KEY: 2}, max_calls=2)
    with pytest.raises(AIError, match="used its 2 AI calls"):
        client.generate_json("p", {}, "s")


def test_invalid_json_raises():
    client, _ = make_client(["not json"])
    with pytest.raises(AIError, match="not valid JSON"):
        client.generate_json("p", {}, "s")


def test_parse_drops_unknown_citations_and_factcheck_flags(retail):
    insights = parse_insights(_payload(retail), retail.facts, "test-model")
    assert insights.source == "ai"
    assert "made.up" not in insights.cited_ids()
    assert insights.notice and "removed" in insights.notice
    report = fact_check(insights.texts(), retail.facts)
    assert [c.raw for c in report.unverified] == ["12.5%"]


def test_fallback_on_error(retail):
    client, _ = make_client([FakeError(500)] * 3)
    result = generate_ai_insights(client, retail.facts, retail.rule_insights)
    assert result.source == "rules"
    assert "unavailable" in result.notice
    assert result.summary == retail.rule_insights.summary


def test_prompt_contains_no_raw_rows(retail):
    prompt = build_prompt(retail.facts)
    raw_dates = retail.profile.df["date"].dt.strftime("%Y-%m-%d").unique()[:50]
    leaked = [d for d in raw_dates if d in prompt and d not in ("2023-01-01", "2024-12-31")]
    assert leaked == []
    assert len(prompt) < 60_000


def test_system_prompt_language_rule():
    from ai.insights_ai import LANGUAGES, system_prompt

    assert "Plain English" in system_prompt()
    spanish = system_prompt("Español")
    assert "Write every text field in Spanish" in spanish and "period as the decimal" in spanish
    assert "{language_rule}" not in spanish
    assert system_prompt("Klingon") == system_prompt()  # unknown languages fall back to English
    assert "English" in LANGUAGES and len(LANGUAGES) >= 6


def test_insights_in_another_language_are_still_fact_checked(retail):
    f = retail.facts.by_id()
    payload = _payload(retail)
    payload["summary"][0]["text"] = f"Los ingresos totales son {f['kpi.metric'].display}."
    payload["findings"] = [{"text": f"La puntuación de salud es {f['health.score'].display}.",
                            "fact_ids": ["health.score"]}] * 3
    seen = {}
    client, models = make_client([json.dumps(payload)])
    original = models.generate_content
    models.generate_content = lambda **kw: seen.update(kw) or original(**kw)
    insights = generate_ai_insights(client, retail.facts, retail.rule_insights, language="Español")
    assert insights.source == "ai" and insights.language == "Español"
    assert "Spanish" in str(seen["config"])
    report = fact_check([s.text for s in insights.summary + insights.findings], retail.facts)
    assert report.total >= 2 and not report.unverified
