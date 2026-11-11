"""Compare: two versions of a file, what changed and where."""

from __future__ import annotations

import streamlit as st

from ai.factcheck import fact_check, highlight_html
from core.compare import Comparison, compare
from core.formatting import fmt_signed_pct, fmt_value, pretty
from core.loader import LoadError, file_hash
from core.samples import COMPARE_EXAMPLES, compare_example_files
from core.settings import CACHE_TTL_S, MAX_FILE_MB
from exports.compare_csv import build_compare_csv
from ui.charts import PLOTLY_CONFIG, figure_for, sql_expander
from ui.components import badge_html, callout, esc, kpi_card, section_header, verified_badge_html
from ui.state import Source, cached_prepare

SIDES = {"before": "vd_cmp_before", "after": "vd_cmp_after"}
COUNTER = "vd_cmp_n"


@st.cache_data(ttl=CACHE_TTL_S, max_entries=8, show_spinner=False)
def cached_compare(hash_b: str, hash_a: str, name_b: str, name_a: str, _data_b: bytes, _data_a: bytes) -> Comparison:
    """The comparison of two files, cached by both fingerprints."""
    before = cached_prepare(hash_b, name_b, None, _data_b)
    after = cached_prepare(hash_a, name_a, None, _data_a)
    return compare(before, after, name_b, name_a)


def _key(side: str) -> str:
    return f"vd_cmp_upload_{side}_{st.session_state.get(COUNTER, 0)}"


def _on_upload(side: str) -> None:
    uploaded = st.session_state.get(_key(side))
    if uploaded is not None:
        st.session_state[SIDES[side]] = Source(uploaded.name, uploaded.getvalue(), "upload")


def _load_example(key: str) -> None:
    (name_b, data_b), (name_a, data_a) = compare_example_files(key)
    st.session_state[SIDES["before"]] = Source(name_b, data_b, "example", key)
    st.session_state[SIDES["after"]] = Source(name_a, data_a, "example", key)


def _start_over() -> None:
    for key in SIDES.values():
        st.session_state.pop(key, None)
    st.session_state[COUNTER] = st.session_state.get(COUNTER, 0) + 1


def _uploaders() -> None:
    left, right = st.columns(2, gap="medium")
    for col, side, label in ((left, "before", "Before (older file)"), (right, "after", "After (newer file)")):
        with col:
            current = st.session_state.get(SIDES[side])
            st.file_uploader(label, type=["csv", "xlsx", "xls"], key=_key(side), on_change=_on_upload, args=(side,),
                             help=f"Up to {MAX_FILE_MB} MB. Processed in memory and never stored.")
            if current is not None:
                st.caption(f"Loaded: {current.name}")


def _signed(value: float, kind: str) -> str:
    return ("+" if value >= 0 else "-") + fmt_value(abs(value), kind)


def _kpis(c: Comparison) -> None:
    m, sel = c.metric, c.metric.selection
    k1, k2, k3, k4 = st.columns(4, gap="small")
    with k1:
        diff = c.rows_after - c.rows_before
        kpi_card("Rows", f"{c.rows_after:,}", f"{diff:+,} vs {c.rows_before:,} before" if diff else "Same as before")
    with k2:
        if m.after is not None and m.change is not None:
            if fmt_value(abs(m.change), sel.value_kind) == fmt_value(0, sel.value_kind):
                sub = "No visible change"
            else:
                sub = _signed(m.change, sel.value_kind)
                if m.change_pct is not None:
                    sub += f" ({fmt_signed_pct(m.change_pct)})"
                sub += " vs before"
            kpi_card(sel.metric_label, fmt_value(m.after, sel.value_kind), sub)
        else:
            kpi_card(sel.metric_label, "n/a", "Not available in both files")
    with k3:
        h = c.health
        kpi_card("Data health", f"{h.after}/100", f"{h.after - h.before:+d} vs {h.before} before" if h.after != h.before
                 else "Same as before")
    with k4:
        cols = c.columns
        value = "Same" if cols.unchanged else f"+{len(cols.added)} / -{len(cols.removed)}"
        sub = f"{len(cols.common)} shared" + (f", {len(cols.retyped)} retyped" if cols.retyped else "")
        kpi_card("Columns", value, sub)


def _summary(c: Comparison) -> None:
    report = fact_check(c.summary, c.facts)
    with st.container(key="card_cmp_summary"):
        st.markdown(
            "<div style='display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap'>"
            "<p class='vd-chart-title' style='margin:0'>What changed</p>"
            f"{verified_badge_html(report.verified, report.total)}</div>"
            + "".join(f"<div class='vd-insight'><div class='txt'>{highlight_html(t, report.by_text.get(t, []))}</div></div>"
                      for t in c.summary),
            unsafe_allow_html=True,
        )


def _columns_card(c: Comparison) -> None:
    cols = c.columns
    with st.container(key="card-eq_cmp_columns"):
        st.markdown("<p class='vd-chart-title'>Columns</p>", unsafe_allow_html=True)
        if cols.unchanged:
            st.markdown(f"<p class='vd-chart-insight'>The same {len(cols.common)} columns, with the same types, "
                        "in both files.</p>", unsafe_allow_html=True)
        rows = [(name, badge_html("Added", "green")) for name in cols.added]
        rows += [(name, badge_html("Removed", "red")) for name in cols.removed]
        rows += [(name, badge_html(f"{b} → {a}", "amber")) for name, b, a in cols.retyped]
        if rows:
            st.markdown(
                "<ul class='vd-checks plain'>"
                + "".join(f"<li><span>{esc(name)}</span>{badge}</li>" for name, badge in rows)
                + "</ul>",
                unsafe_allow_html=True,
            )
            st.caption("Only columns in both files with the same type are compared.")
        r = c.records
        if r is not None:
            st.markdown(f"<p class='vd-chart-title' style='margin-top:14px'>Records, matched on {esc(r.id_col)}</p>",
                        unsafe_allow_html=True)
            a, b, k = st.columns(3, gap="small")
            a.metric("New", f"{r.added:,}")
            b.metric("Gone", f"{r.removed:,}")
            k.metric("In both", f"{r.kept:,}", f"{r.changed:,} changed" if r.changed else None, delta_color="off")
            examples = []
            if r.added_examples:
                examples.append("New: " + ", ".join(r.added_examples))
            if r.removed_examples:
                examples.append("Gone: " + ", ".join(r.removed_examples))
            if examples:
                st.caption(" · ".join(examples))
            sql_expander(r.sql, label="How records were matched")
        m = c.metric
        if not m.groups.empty and m.group_col:
            kind = m.selection.value_kind
            st.markdown(f"<p class='vd-chart-title' style='margin-top:14px'>Before and after, by "
                        f"{esc(pretty(m.group_col).lower())}</p>", unsafe_allow_html=True)
            st.dataframe(
                [{pretty(m.group_col): g.label, "Before": fmt_value(g.before, kind), "After": fmt_value(g.after, kind),
                  "Change": _signed(g.change, kind)} for g in m.groups.itertuples(index=False)],
                hide_index=True,
            )


def _chart_card(c: Comparison) -> None:
    spec = c.chart()
    with st.container(key="card-eq_cmp_chart"):
        if spec is None:
            st.markdown("<p class='vd-chart-title'>Where the change came from</p>"
                        "<p class='vd-chart-insight'>No shared grouping column, or no group changed.</p>",
                        unsafe_allow_html=True)
            sql_expander(c.metric.sql)
            return
        n = len(spec.data)
        st.markdown(f"<p class='vd-chart-title'>{esc(spec.title)}</p><p class='vd-chart-insight'>"
                    f"The {n} {pretty(c.metric.group_col).lower()} value{'s' if n != 1 else ''} that moved most, "
                    "after minus before.</p>", unsafe_allow_html=True)
        st.plotly_chart(figure_for(spec), theme=None, config=PLOTLY_CONFIG, key="cmp_chart")
        sql_expander(c.metric.sql + ";\n\n" + spec.sql, spec.data)


def _results(c: Comparison) -> None:
    top_l, top_r = st.columns([4, 1], vertical_alignment="center")
    with top_l:
        st.markdown(
            f"<div class='vd-badges' style='margin:0'>{badge_html('Before: ' + c.before_name, 'slate')}"
            f"<span style='color:var(--vd-muted)'>→</span>{badge_html('After: ' + c.after_name, 'teal')}</div>",
            unsafe_allow_html=True,
        )
    with top_r:
        st.button("Compare other files", on_click=_start_over, width="stretch", key="cmp_reset")
    st.write("")
    _kpis(c)
    st.write("")
    _summary(c)
    st.write("")
    left, right = st.columns([3, 2], gap="medium")
    with left:
        _chart_card(c)
    with right:
        _columns_card(c)
    st.write("")
    note, dl = st.columns([4, 1.3], vertical_alignment="center", gap="medium")
    with note:
        st.caption("Both files are stacked into one table, data, with a _file column saying which file each row "
                   "came from. Files are processed in memory and never stored.")
    with dl:
        stem = c.after_name.rsplit(".", 1)[0]
        st.download_button("Download comparison", data=lambda: build_compare_csv(c),
                           file_name=f"{stem}_comparison.csv", mime="text/csv", on_click="ignore",
                           width="stretch", key="dl_compare", help="Every compared figure with its SQL, as a CSV.")


section_header(
    "Compare two files",
    "Last month against this month, before and after a cleanup: see what changed in the columns, the "
    "numbers and the records, with every figure computed by a query you can inspect.",
    top=True,
)
before, after = (st.session_state.get(SIDES[s]) for s in ("before", "after"))
if before is None or after is None:
    with st.container(key="card_cmp_start"):
        _uploaders()
        st.markdown("<p class='vd-chart-insight' style='margin:6px 0 8px 0'>No files handy? Compare two slices of "
                    "an example:</p>", unsafe_allow_html=True)
        cols = st.columns(len(COMPARE_EXAMPLES), gap="small")
        for col, ex in zip(cols, COMPARE_EXAMPLES.values(), strict=True):
            col.button(ex.title, key=f"cmp_ex_{ex.key}", on_click=_load_example, args=(ex.key,), width="stretch")
    st.caption("Works best when both files have the same layout, such as two monthly exports of one report. "
               "With a shared ID column, records are matched one by one.")
else:
    try:
        with st.spinner("Comparing the two files..."):
            result = cached_compare(file_hash(before.data), file_hash(after.data), before.name, after.name,
                                    before.data, after.data)
    except LoadError as exc:
        callout(str(exc), title="One of the files could not be read", kind="error")
        st.button("Start over", on_click=_start_over, key="cmp_error_reset")
    else:
        _results(result)
