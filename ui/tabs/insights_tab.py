"""Insights tab: AI or rule-based insights, citations, the fact-check badge and a checker for any text."""

from __future__ import annotations

import streamlit as st

from ai.client import GeminiClient, resolve_api_key, resolve_model
from ai.factcheck import FactCheckReport, check_text, fact_check, highlight_html
from ai.insights_ai import DEFAULT_LANGUAGE, LANGUAGES, generate_ai_insights
from core.facts import FactPack
from core.formatting import plural
from core.insights_rules import Insights
from core.pipeline import Analysis
from ui.components import callout, esc, source_badge_html, verified_badge_html
from ui.state import session_api_key

AI_CACHE_KEY = "vd_ai_insights"
MAX_CHECK_CHARS = 4000


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


def _item(text: str, ids: list[str], pack: FactPack, report: FactCheckReport, show: bool) -> str:
    meta = f"<div class='meta'>{_cites(ids, pack)}</div>" if show and ids else ""
    return f"<div class='vd-insight'><div class='txt'>{_text(text, report)}</div>{meta}</div>"


def render_insights(insights: Insights, pack: FactPack) -> FactCheckReport:
    """Render insights with highlighted, fact-checked numbers. Returns the report."""
    report = fact_check(insights.texts(), pack)
    left, right = st.columns([3, 1], vertical_alignment="center")
    with left:
        st.markdown(
            "<div class='vd-badges' style='margin:0'>"
            + source_badge_html(insights.source, insights.model)
            + verified_badge_html(report.verified, report.total)
            + "</div>",
            unsafe_allow_html=True,
        )
    with right:
        show = st.toggle("Show fact sources", key="vd_show_sources",
                         help="Show the ID of each computed fact a sentence relies on. "
                              "Hover a dotted number to see where it came from.")
    if insights.notice:
        callout(insights.notice, kind="warn")
    if report.unverified:
        raws = ", ".join(sorted({c.raw for c in report.unverified}))
        callout(
            f"{plural(len(report.unverified), 'number')} could not be matched to a computed fact: {raws}. "
            "They are underlined in red below. Treat them with caution.",
            title="Some numbers are unverified",
            kind="warn",
        )

    with st.container(key="card_summary"):
        st.markdown("<p class='vd-chart-title'>Executive summary</p>", unsafe_allow_html=True)
        st.markdown("".join(_item(s.text, s.fact_ids, pack, report, show) for s in insights.summary),
                    unsafe_allow_html=True)
    st.write("")
    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card_findings"):
        st.markdown("<p class='vd-chart-title'>Key findings</p>", unsafe_allow_html=True)
        st.markdown("".join(_item(s.text, s.fact_ids, pack, report, show) for s in insights.findings),
                    unsafe_allow_html=True)
    with right, st.container(key="card_caveats"):
        st.markdown("<p class='vd-chart-title'>Data caveats</p>", unsafe_allow_html=True)
        st.markdown(
            "".join(f"<div class='vd-insight'><div class='txt'>{_text(c, report)}</div></div>" for c in insights.caveats),
            unsafe_allow_html=True,
        )
    st.write("")
    st.markdown("<p class='vd-chart-title'>Recommendations to test</p>", unsafe_allow_html=True)
    st.caption("Each one is a hypothesis: what supports it, and how you could confirm it.")
    recs = insights.recommendations
    for start in range(0, len(recs), 2):
        cols = st.columns(2, gap="medium")
        for offset, rec in enumerate(recs[start : start + 2]):
            with cols[offset], st.container(key=f"card-eq_rec_{start + offset}"):
                cites = f"<div class='meta' style='margin-top:10px'>{_cites(rec.fact_ids, pack)}</div>" if show else ""
                st.markdown(
                    f"<div class='vd-rec-h'>{_text(rec.hypothesis, report)}</div>"
                    f"<div class='vd-rec-l'><b>Evidence</b> {_text(rec.evidence, report)}</div>"
                    f"<div class='vd-rec-l'><b>How to validate</b> {_text(rec.how_to_validate, report)}</div>"
                    f"{cites}",
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
                "Matched fact": c.fact_id or c.reason,
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

    if api_key:
        client = GeminiClient(api_key, resolve_model(), st.session_state)
        left, mid, right = st.columns([3, 1.2, 1.8], vertical_alignment="bottom")
        with left:
            if cached is None:
                st.markdown(
                    "**AI insights are available.** Gemini will read only the fact pack (schema and "
                    "aggregated results) and every number it writes will be fact-checked."
                )
            else:
                st.markdown("**Want them in another language?** Pick one and write them again.")
            src = "your session key" if key_source == "session" else "the app's configured key"
            st.caption(f"Using {src} · model {client.model} · {plural(client.calls_left, 'AI call')} left this session")
        with mid:
            current = cached.language if cached is not None and cached.source == "ai" else DEFAULT_LANGUAGE
            language = st.selectbox("Language", list(LANGUAGES), index=list(LANGUAGES).index(current),
                                    key="vd_ai_language")
        with right:
            label = "Write AI insights with Gemini" if cached is None else "Write again"
            go = st.button(label, type="primary" if cached is None else "secondary", width="stretch",
                           disabled=client.calls_left <= 0)
        if go:
            with st.spinner("Gemini is reading the fact pack..."):
                cache[cache_key] = generate_ai_insights(client, analysis.facts, analysis.rule_insights, language)
            st.rerun()
    elif not api_key:
        st.caption(
            "Rule-based insights, written directly from computed facts. Add a Gemini key in the sidebar "
            "for AI-written insights with the same structure and the same fact-check."
        )

    insights = cached or analysis.rule_insights
    if cached is not None and cached.source == "ai":
        show_rules = st.toggle("Show rule-based version instead", key=f"vd_rules_{cache_key}")
        if show_rules:
            insights = analysis.rule_insights
    st.write("")
    render_insights(insights, analysis.facts)
    st.write("")
    check_any_text(analysis.facts, cache_key)


def check_any_text(pack: FactPack, cache_key: str) -> None:
    """Fact-check text written elsewhere (a colleague's report, an AI chat) against this file."""
    with st.container(key="card_check_text"):
        st.markdown(
            "<p class='vd-chart-title'>Check someone else's numbers</p>"
            "<p class='vd-chart-insight'>Paste a paragraph from a report, an email or an AI chat about this file. "
            "Every number is checked against what Veridash computed, including its direction and which group "
            "it belongs to. No key needed, and nothing is sent anywhere.</p>",
            unsafe_allow_html=True,
        )
        text = st.text_area(
            "Text to check",
            key=f"vd_check_text_{cache_key}",
            max_chars=MAX_CHECK_CHARS,
            height=110,
            placeholder="For example: Electronics brought in $271.4K, and revenue rose 19.6% last month.",
            label_visibility="collapsed",
        )
        if not text.strip():
            return
        claims = check_text(text, pack)
        if not claims:
            st.caption("No numbers found in that text.")
            return
        ok = sum(c.verified for c in claims)
        st.markdown(
            f"<div class='vd-badges'>{verified_badge_html(ok, len(claims))}</div>"
            f"<div class='vd-insight'><div class='txt'>{highlight_html(text, claims)}</div></div>",
            unsafe_allow_html=True,
        )
        facts = pack.by_id()
        st.dataframe(
            [
                {
                    "Number": c.raw,
                    "Status": "Verified" if c.verified else (c.reason.split(":", 1)[0] if c.reason else "Not found"),
                    "Matched fact": c.fact_id or "",
                    "Computed value": facts[c.fact_id].display if c.fact_id in facts else "",
                }
                for c in claims
            ],
            hide_index=True,
        )
        reasons = [f"<li><b>{esc(c.raw)}</b>: {esc(c.reason)}</li>" for c in claims if not c.verified and c.reason]
        if reasons:
            st.markdown(f"<ul class='vd-reasons'>{''.join(reasons)}</ul>", unsafe_allow_html=True)
        if any(not c.verified and not c.reason for c in claims):
            st.caption(
                "Not found means Veridash did not compute that number. It may still be right, for example a figure "
                "for one month; check it with Ask your data."
            )
