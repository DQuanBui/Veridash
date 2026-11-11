"""Benchmark: published scores for Veridash's own safety checks."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from bench.__main__ import load
from ui.components import callout, esc, kpi_card, section_header

# The first published run (commit b8170ce), before the sign and group checks existed.
FIRST_RUN_CATCH_PCT = 77.9


@st.cache_data(show_spinner=False)
def _results() -> dict:
    return load()


def _meter(title: str, example: str, flagged: int, cases: int, good_when_high: bool = True) -> str:
    pct = 100.0 * flagged / cases if cases else 0.0
    shown = pct if good_when_high else 100.0 - pct
    return (
        "<div class='vd-meter'>"
        f"<div><div class='t'>{esc(title)}</div><div class='e'>{esc(example)}</div></div>"
        f"<div class='bar' role='img' aria-label='{shown:.0f} percent'><span style='width:{shown:.1f}%'></span></div>"
        f"<div class='n'>{flagged:,} of {cases:,}</div></div>"
    )


r = _results()
fc, sg, cc = r["factcheck"], r["sql_guard"], r["crosscheck"]

section_header(
    "Trust benchmark",
    "Veridash claims its numbers can be trusted, so we tried to break it: over a thousand planted "
    "errors and dozens of harmful queries. These are the results.",
    kicker="Benchmark",
    top=True,
)
k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    kpi_card("Wrong numbers caught", f"{fc['catch_pct']}%", f"{fc['caught']:,} of {fc['planted_errors']:,} planted")
with k2:
    kpi_card("False alarms", f"{fc['false_alarms']}", f"on {fc['correct_sentences']:,} correct sentences")
with k3:
    kpi_card("Harmful queries blocked", f"{sg['guard_blocked']} of {sg['attacks']}", "file, network and write attempts")
with k4:
    kpi_card("Numbers recomputed", f"{cc['matched']} of {cc['checked']}", "agree with a pandas recount")
st.caption(
    f"Re-run on every code change; the build fails if these results go out of date. Last run {r['generated']}, "
    "on the three example datasets."
)

st.write("")
with st.container(key="card_bench_factcheck"):
    st.markdown(
        "<p class='vd-chart-title'>Fact-check: planted errors caught</p>"
        "<p class='vd-chart-insight'>Each headline number in the examples is written into a sentence, then "
        "corrupted in six ways. A planted error counts as caught when its number is flagged.</p>"
        + "".join(_meter(row["title"], row["example"], row["flagged"], row["cases"]) for row in fc["corrupt"]),
        unsafe_allow_html=True,
    )
    callout(
        f"The first run caught {FIRST_RUN_CATCH_PCT}% and missed every number given to the wrong group or "
        f"written with the wrong sign. Both checks were added, and it now catches {fc['catch_pct']}%. The "
        "remaining misses are wrong numbers that happen to equal another real figure in the same file.",
        title="What the benchmark changed",
    )
    with st.expander(f"Correct sentences: {fc['false_alarms']} wrongly flagged"):
        st.markdown(
            "".join(_meter(row["title"], row["example"], row["cases"] - row["flagged"], row["cases"])
                    for row in fc["correct"]),
            unsafe_allow_html=True,
        )
        st.caption("Shown as sentences passed. Correct numbers may be rounded, spelled out or signed.")

st.write("")
left, right = st.columns([3, 2], gap="medium")
with left, st.container(key="card-eq_bench_sql"):
    rows = "<ul class='vd-checks'>" + "".join(
        f"<li class='{'ok' if c['blocked'] == c['queries'] else 'bad'}'><span>{esc(c['category'])}</span>"
        f"<b>{c['blocked']} of {c['queries']}</b></li>"
        for c in sg["categories"]
    ) + "</ul>"
    st.markdown(
        "<p class='vd-chart-title'>Ask your data: harmful queries blocked</p>"
        "<p class='vd-chart-insight'>SQL written by the AI or typed by a visitor passes a guard, then runs in "
        f"a locked sandbox. With the guard switched off, the sandbox alone still blocked "
        f"{sg['sandbox_blocked']} of {sg['sandbox_attacks']} file, network, extension and setting attacks.</p>"
        + rows,
        unsafe_allow_html=True,
    )
    with st.expander("See every query"):
        st.dataframe(
            pd.DataFrame(sg["attack_rows"]).rename(columns={
                "category": "Attempt", "sql": "Query", "guard_blocked": "Guard blocked",
                "sandbox_blocked": "Sandbox alone blocked",
            }),
            hide_index=True,
        )
with right, st.container(key="card-eq_bench_cross"):
    st.markdown(
        "<p class='vd-chart-title'>Every number, computed twice</p>"
        "<p class='vd-chart-insight'>Charts and KPIs come from DuckDB SQL. The benchmark rebuilds them with "
        "plain pandas, without any SQL, and compares the two.</p>"
        + "".join(_meter(d["dataset"], "", d["matched"], d["checked"]) for d in cc["datasets"]),
        unsafe_allow_html=True,
    )
    st.caption("Covered: counts, KPIs, trends, rankings, shares, the change breakdown, rates, medians, correlations "
               "and both Compare examples.")
    st.markdown(
        "<p class='vd-chart-title' style='margin-top:18px'>Safe queries still work</p>"
        "<p class='vd-chart-insight'>Blocking is easy if you block everything. These ordinary questions, some "
        "with words like DROP inside text, must still run.</p>"
        + _meter("Harmless queries ran",
                 f"Every result under the {sg['row_cap']:,}-row cap" if sg["row_cap_held"] else "",
                 sg["harmless_ran"], sg["harmless"]),
        unsafe_allow_html=True,
    )

section_header(
    "Why this matters",
    "An AI that writes about your data can be fluent and wrong. Veridash never lets the AI calculate, "
    "and this benchmark measures how well it catches the AI when it gets a number wrong.",
    kicker="Method",
)
c1, c2, c3 = st.columns(3, gap="medium")
for col, (title, text) in zip(
    (c1, c2, c3),
    [
        ("Deterministic", "No randomness and no AI calls, so anyone can re-run it and get the same scores."),
        ("Honest about misses", "Misses and false alarms are counted and shown, not hidden."),
        ("Kept up to date", "Every push to GitHub re-runs it; stale results fail the build."),
    ],
    strict=True,
):
    with col:
        st.markdown(f"<div class='vd-card'><h4 style='margin-top:0'>{esc(title)}</h4><p>{esc(text)}</p></div>",
                    unsafe_allow_html=True)
