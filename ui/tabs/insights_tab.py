"""Insights tab: AI or rule-based insights, citations and the fact-check badge."""

from __future__ import annotations

import streamlit as st

from ai.client import GeminiClient, resolve_api_key, resolve_model
from ai.factcheck import FactCheckReport, fact_check, highlight_html
from ai.insights_ai import generate_ai_insights
from core.facts import FactPack
from core.insights_rules import Insights
from core.pipeline import Analysis
from ui.components import callout, esc, source_badge_html, verified_badge_html
from ui.state import session_api_key

AI_CACHE_KEY = "vd_ai_insights"


def _cites(ids: list[str], pack: FactPack) -> str:
    facts = pack.by_id()
    chips = []
    for fid in ids:
        fact = facts.get(fid)
        title = f"{fact.label}: {fact.display}" if fact else "Unknown fact ID"
        chips.append(f"<span class='vd-cite' title='{esc(title)}'>{esc(fid)}</span>")
    return "".join(chips)


def _text(text: str, report: FactCheckReport) -> str:
    return highlight_html(text, report.by_text.get(text, []))


def _item(text: str, ids: list[str], pack: FactPack, report: FactCheckReport) -> str:
    return (
        f"<div class='vd-insight'><div class='txt'>{_text(text, report)}</div>"
        f"<div class='meta'>{_cites(ids, pack)}</div></div>"
    )


def render_insights(insights: Insights, pack: FactPack) -> FactCheckReport:
    """Render insights with highlighted, fact-checked numbers. Returns the report."""
    report = fact_check(insights.texts(), pack)
    st.markdown(
        "<div class='vd-badges'>"
        + source_badge_html(insights.source, insights.model)
        + verified_badge_html(report.verified, report.total)
        + "</div>",
        unsafe_allow_html=True,
    )
    if insights.notice:
        callout(insights.notice, kind="warn")
    if report.unverified:
        raws = ", ".join(sorted({c.raw for c in report.unverified}))
        callout(
            f"{len(report.unverified)} number(s) could not be matched to a computed fact: {raws}. "
            "They are underlined in red below. Treat them with caution.",
            title="Some numbers are unverified",
            kind="warn",
        )

    with st.container(key="card_summary"):
        st.markdown("<p class='vd-chart-title'>Executive summary</p>", unsafe_allow_html=True)
        st.markdown("".join(_item(s.text, s.fact_ids, pack, report) for s in insights.summary), unsafe_allow_html=True)
    st.write("")
    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card_findings"):
        st.markdown("<p class='vd-chart-title'>Key findings</p>", unsafe_allow_html=True)
        st.markdown("".join(_item(s.text, s.fact_ids, pack, report) for s in insights.findings), unsafe_allow_html=True)
    with right, st.container(key="card_caveats"):
        st.markdown("<p class='vd-chart-title'>Data caveats</p>", unsafe_allow_html=True)
        st.markdown(
            "".join(f"<div class='vd-insight'><div class='txt'>{_text(c, report)}</div></div>" for c in insights.caveats),
            unsafe_allow_html=True,
        )
    st.write("")
    st.markdown("<p class='vd-chart-title'>Recommendations to test</p>", unsafe_allow_html=True)
    st.caption("Framed as hypotheses: each one says what supports it and how you could confirm it.")
    cols = st.columns(2, gap="medium")
    for i, rec in enumerate(insights.recommendations):
        with cols[i % 2], st.container(key=f"card_rec_{i}"):
            st.markdown(
                f"<div style='font-weight:600;font-size:15px'>{_text(rec.hypothesis, report)}</div>"
                f"<div class='vd-chart-insight' style='margin-top:8px'><b>Evidence:</b> {_text(rec.evidence, report)}</div>"
                f"<div class='vd-chart-insight'><b>How to validate:</b> {_text(rec.how_to_validate, report)}</div>"
                f"<div class='meta' style='margin-top:8px'>{_cites(rec.fact_ids, pack)}</div>",
                unsafe_allow_html=True,
            )

    with st.expander("Fact-check details"):
        st.caption(
            "Every number in the text above was extracted and compared with the facts the code computed, "
            "allowing for rounding and %/$ formatting."
        )
        facts = pack.by_id()
        rows = [
            {
                "Number": c.raw,
                "Status": "Verified" if c.verified else "Unverified",
                "Matched fact": c.fact_id or "",
                "Fact value": facts[c.fact_id].display if c.fact_id in facts else "",
            }
            for c in report.claims
        ]
        if rows:
            st.dataframe(rows, hide_index=True)
        else:
            st.write("No numbers found in the text.")
    return report


def current_insights(analysis: Analysis, cache_key: str) -> Insights:
    """AI insights for this file/selection if generated this session, else rule-based."""
    return st.session_state.get(AI_CACHE_KEY, {}).get(cache_key) or analysis.rule_insights


def render(analysis: Analysis, cache_key: str) -> None:
    """Render the Insights tab, with an optional AI generation step."""
    api_key, key_source = resolve_api_key(session_api_key())
    cache: dict[str, Insights] = st.session_state.setdefault(AI_CACHE_KEY, {})
    cached = cache.get(cache_key)

    if api_key and cached is None:
        client = GeminiClient(api_key, resolve_model(), st.session_state)
        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            st.markdown(
                "**AI insights are available.** Gemini will read only the fact pack (schema and "
                "aggregated results) and every number it writes will be fact-checked."
            )
            src = "your session key" if key_source == "session" else "the app's configured key"
            st.caption(f"Using {src} · model {client.model} · {client.calls_left} AI call(s) left this session")
        with right:
            go = st.button("Write AI insights with Gemini", type="primary", width="stretch",
                           disabled=client.calls_left <= 0)
        if go:
            with st.spinner("Gemini is reading the fact pack..."):
                cache[cache_key] = generate_ai_insights(client, analysis.facts, analysis.rule_insights)
            st.rerun()
    elif not api_key:
        callout(
            "Add a Gemini key in the sidebar to get AI-written insights. The rule-based insights below use "
            "the same structure and are built directly from computed facts.",
            title="Rule-based mode",
        )

    insights = cached or analysis.rule_insights
    if cached is not None and cached.source == "ai":
        show_rules = st.toggle("Show rule-based version instead", key=f"vd_rules_{cache_key}")
        if show_rules:
            insights = analysis.rule_insights
    st.write("")
    render_insights(insights, analysis.facts)
