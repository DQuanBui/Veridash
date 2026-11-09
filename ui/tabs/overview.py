"""Overview tab: health score, issues, KPIs and dataset facts."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import streamlit as st

from core.formatting import fmt_value, human_bytes
from core.health import HealthReport
from core.pipeline import Analysis
from ui.components import SEVERITY_VARIANT, TYPE_BADGE_VARIANT, badge_html, esc, kpi_card

_GRADE_COLOR = {"A": "#0D9488", "B": "#0D9488", "C": "#D97706", "D": "#DC2626", "F": "#DC2626"}


def _score_ring(health: HealthReport) -> str:
    color = _GRADE_COLOR[health.grade]
    return (
        '<div class="vd-score">'
        f'<div class="ring" style="background: conic-gradient({color} {health.score * 3.6}deg, #E2E8F0 0);">'
        '<div style="width:76px;height:76px;border-radius:50%;background:#fff;display:flex;flex-direction:column;'
        'align-items:center;justify-content:center;">'
        f'<div class="n" style="color:{color}">{health.score}</div><div class="g">GRADE {health.grade}</div></div></div>'
        "<div><div style='font-weight:700;font-size:18px'>Data health</div>"
        f"<div style='color:#64748B;font-size:14px'>{len([i for i in health.issues if i.severity != 'info'])} issue(s) found · "
        "score starts at 100 and loses capped points per check</div></div></div>"
    )


def _checks_table(health: HealthReport) -> str:
    rows = "".join(
        f"<tr><td>{esc(c.label)}</td><td class='num'>{c.measure:,.1f}</td>"
        f"<td class='num'>x{c.points_per_unit:g}, cap {c.cap:g}</td>"
        f"<td class='num'><b>-{c.penalty:g}</b></td></tr>"
        for c in health.checks
    )
    return (
        "<div class='vd-table-wrap' style='margin-top:16px'><table class='vd-table'><thead><tr>"
        "<th>Check</th><th style='text-align:right'>Measure</th><th style='text-align:right'>Weight</th>"
        f"<th style='text-align:right'>Penalty</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def _issues(health: HealthReport) -> str:
    if not health.issues:
        return "<div class='vd-callout'>No issues found. This file is in great shape.</div>"
    items = "".join(
        "<div class='vd-issue'>"
        f"<div>{badge_html(i.severity, SEVERITY_VARIANT[i.severity])}</div>"
        f"<div><div class='t'>{esc(i.title)}</div><div class='d'>{esc(i.detail)}</div>"
        f"<div class='w'><b>Why it matters:</b> {esc(i.why)}</div></div></div>"
        for i in health.issues
    )
    return f"<div>{items}</div>"


def render(analysis: Analysis) -> None:
    """Render the Overview tab."""
    health = analysis.health
    profile = analysis.profile

    cols = st.columns(len(analysis.kpis) or 1)
    for col, kpi in zip(cols, analysis.kpis, strict=False):
        with col:
            kpi_card(kpi.label, kpi.display, kpi.note)
    with st.expander("How these KPIs were calculated"):
        st.caption("Each KPI is computed on the full dataset by the DuckDB query shown.")
        for kpi in analysis.kpis:
            st.markdown(f"**{kpi.label}**: {kpi.display}")
            st.code(kpi.sql, language="sql")
            if kpi.key == "period_change":
                st.caption("The change compares the last two complete periods returned by this query.")

    st.write("")
    left, right = st.columns(2, gap="medium")
    with left, st.container(key="card_health"):
        st.markdown(_score_ring(health), unsafe_allow_html=True)
        st.markdown(_checks_table(health), unsafe_allow_html=True)
        st.caption("Formula: score = 100 - sum of capped penalties. See the Guide for details.")
    with right, st.container(key="card_issues"):
        st.markdown("<p class='vd-chart-title'>Issues</p>", unsafe_allow_html=True)
        st.markdown(_issues(health), unsafe_allow_html=True)

    st.write("")
    with st.container(key="card_facts"):
        st.markdown("<p class='vd-chart-title'>Dataset facts</p>", unsafe_allow_html=True)
        sel = analysis.selection
        date_range = "No date column"
        if sel.date_col:
            stats = profile.get(sel.date_col).stats
            start = datetime.fromtimestamp(stats["min"], tz=UTC).strftime("%b %d, %Y")
            end = datetime.fromtimestamp(stats["max"], tz=UTC).strftime("%b %d, %Y")
            date_range = f"{start} to {end}"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", fmt_value(profile.n_rows, "int"))
        c2.metric("Columns", fmt_value(profile.n_cols, "int"))
        c3.metric("Memory size", human_bytes(profile.memory_bytes))
        c4.metric("Missing cells", fmt_value(health.missing_pct, "percent"))
        st.markdown(f"**Date range** ({esc(sel.date_col or 'n/a')}): {esc(date_range)}")
        counts = Counter(str(c.col_type) for c in profile.columns)
        st.markdown(
            "<div class='vd-badges'>"
            + "".join(badge_html(f"{n} {t}", TYPE_BADGE_VARIANT.get(t, "slate")) for t, n in counts.most_common())
            + "</div>",
            unsafe_allow_html=True,
        )
        loaded = analysis.prepared.loaded
        for note in loaded.notes:
            st.caption(note)
