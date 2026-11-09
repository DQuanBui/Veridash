"""AI-written insights from the fact pack, with graceful fallback to rules.

The model receives only the fact pack (schema + aggregated, code-computed
facts). It is asked to *select and explain* those facts, cite their IDs and
phrase recommendations as hypotheses. It never receives raw rows and is told
never to calculate new numbers; the fact-checker verifies that afterwards.
"""

from __future__ import annotations

from typing import Any

from ai.client import AIError, GeminiClient
from core.facts import FactPack
from core.insights_rules import Insights, Recommendation, Statement

_STATEMENT = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "fact_ids"],
}
INSIGHTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "array", "items": _STATEMENT, "minItems": 3, "maxItems": 3},
        "findings": {"type": "array", "items": _STATEMENT, "minItems": 3, "maxItems": 5},
        "recommendations": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "hypothesis": {"type": "string"},
                    "evidence": {"type": "string"},
                    "how_to_validate": {"type": "string"},
                    "fact_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["hypothesis", "evidence", "how_to_validate", "fact_ids"],
            },
        },
        "caveats": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
    },
    "required": ["summary", "findings", "recommendations", "caveats"],
}

SYSTEM_PROMPT = """You are a careful senior data analyst writing for business stakeholders.
You receive a FACT PACK: the schema of a dataset plus facts that code has already computed.
Each fact has an id, a label, a value and a display string.

Rules you must follow:
1. Use only numbers that appear in the fact pack. Write them as in the "display" field
   (rounding is fine). Never calculate new numbers: no sums, differences, ratios or
   averages of facts, and no counts you derived yourself.
2. Cite the ids of every fact you use in "fact_ids". Do not put ids in the text.
3. Describe patterns; do not invent causes. Any explanation is a hypothesis ("may", "could").
4. Recommendations are hypotheses with "evidence" (from cited facts) and "how_to_validate"
   (a concrete check the analyst could run).
5. Caveats must mention material data-quality issues from the health facts and the limits
   of the analysis.
6. Plain English, short sentences, no markdown, no emoji.
Return exactly 3 summary bullets, 3-5 findings, 2-4 recommendations and 2-5 caveats."""


def build_prompt(pack: FactPack) -> str:
    """User prompt containing the fact pack JSON."""
    return (
        "Write an executive summary, key findings, recommendations and caveats for this dataset.\n"
        "FACT PACK (JSON):\n" + pack.to_json()
    )


def _statements(items: list[dict[str, Any]], valid: set[str]) -> list[Statement]:
    out = []
    for item in items:
        text = str(item.get("text", "")).strip()
        if text:
            out.append(Statement(text, [i for i in item.get("fact_ids", []) if i in valid]))
    return out


def parse_insights(payload: dict[str, Any], pack: FactPack, model: str) -> Insights:
    """Convert the model's JSON into :class:`Insights`, dropping unknown citations."""
    valid = set(pack.by_id())
    cited = {i for key in ("summary", "findings", "recommendations") for item in payload.get(key, []) for i in item.get("fact_ids", [])}
    unknown = cited - valid
    recs = [
        Recommendation(
            hypothesis=str(r.get("hypothesis", "")).strip(),
            evidence=str(r.get("evidence", "")).strip(),
            how_to_validate=str(r.get("how_to_validate", "")).strip(),
            fact_ids=[i for i in r.get("fact_ids", []) if i in valid],
        )
        for r in payload.get("recommendations", [])
        if r.get("hypothesis")
    ]
    insights = Insights(
        summary=_statements(payload.get("summary", []), valid)[:3],
        findings=_statements(payload.get("findings", []), valid)[:5],
        recommendations=recs[:4],
        caveats=[str(c).strip() for c in payload.get("caveats", []) if str(c).strip()][:5],
        source="ai",
        model=model,
    )
    if not insights.summary or not insights.findings:
        raise AIError("Gemini's response was missing required sections.")
    if unknown:
        insights.notice = f"{len(unknown)} citation(s) referred to facts that do not exist and were removed."
    return insights


def generate_ai_insights(client: GeminiClient, pack: FactPack, fallback: Insights) -> Insights:
    """Ask Gemini for insights; on any failure return ``fallback`` with a notice."""
    try:
        payload = client.generate_json(build_prompt(pack), INSIGHTS_SCHEMA, SYSTEM_PROMPT)
        return parse_insights(payload, pack, client.model)
    except AIError as exc:
        reason = str(exc)
    except Exception:  # defensive: never let AI break the page
        reason = "An unexpected error occurred while generating AI insights."
    fallback_copy = Insights(
        summary=fallback.summary,
        findings=fallback.findings,
        recommendations=fallback.recommendations,
        caveats=fallback.caveats,
        source="rules",
        notice=f"AI insights are unavailable: {reason} Showing rule-based insights instead.",
    )
    return fallback_copy
