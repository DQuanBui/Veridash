"""Insights tab: summary, findings, hypotheses and caveats with citations."""

from __future__ import annotations

import streamlit as st

from core.facts import FactPack
from core.insights_rules import Insights
from core.pipeline import Analysis
from ui.components import esc, source_badge_html


def _cites(ids: list[str], pack: FactPack) -> str:
    facts = pack.by_id()
    chips = []
    for fid in ids:
        fact = facts.get(fid)
        title = f"{fact.label}: {fact.display}" if fact else "Unknown fact ID"
        chips.append(f"<span class='vd-cite' title='{esc(title)}'>{esc(fid)}</span>")
    return "".join(chips)


def render_insights(insights: Insights, pack: FactPack, badges_html: str = "") -> None:
    """Render an :class:`Insights` object. ``badges_html`` is trusted markup."""
    st.markdown(
        f"<div class='vd-badges'>{source_badge_html(insights.source, insights.model)}{badges_html}</div>",
        unsafe_allow_html=True,
    )
    with st.container(key="card_summary"):
        st.markdown("<p class='vd-chart-title'>Executive summary</p>", unsafe_allow_html=True)
        st.markdown(
            "".join(
                f"<div class='vd-insight'><div class='txt'>{esc(s.text)}</div>"
                f"<div class='meta'>{_cites(s.fact_ids, pack)}</div></div>"
                for s in insights.summary
            ),
            unsafe_allow_html=True,
        )
    st.write("")
    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card_findings"):
        st.markdown("<p class='vd-chart-title'>Key findings</p>", unsafe_allow_html=True)
        st.markdown(
            "".join(
                f"<div class='vd-insight'><div class='txt'>{esc(s.text)}</div>"
                f"<div class='meta'>{_cites(s.fact_ids, pack)}</div></div>"
                for s in insights.findings
            ),
            unsafe_allow_html=True,
        )
    with right, st.container(key="card_caveats"):
        st.markdown("<p class='vd-chart-title'>Data caveats</p>", unsafe_allow_html=True)
        st.markdown(
            "".join(f"<div class='vd-insight'><div class='txt'>{esc(c)}</div></div>" for c in insights.caveats),
            unsafe_allow_html=True,
        )
    st.write("")
    st.markdown("<p class='vd-chart-title'>Recommendations to test</p>", unsafe_allow_html=True)
    st.caption("Framed as hypotheses: each one says what supports it and how you could confirm it.")
    cols = st.columns(2, gap="medium")
    for i, rec in enumerate(insights.recommendations):
        with cols[i % 2], st.container(key=f"card_rec_{i}"):
            st.markdown(
                f"<div class='txt' style='font-weight:600;font-size:15px'>{esc(rec.hypothesis)}</div>"
                f"<div class='vd-chart-insight' style='margin-top:8px'><b>Evidence:</b> {esc(rec.evidence)}</div>"
                f"<div class='vd-chart-insight'><b>How to validate:</b> {esc(rec.how_to_validate)}</div>"
                f"<div class='meta' style='margin-top:8px'>{_cites(rec.fact_ids, pack)}</div>",
                unsafe_allow_html=True,
            )


def render(analysis: Analysis) -> None:
    """Render rule-based insights for the current analysis."""
    render_insights(analysis.rule_insights, analysis.facts)
