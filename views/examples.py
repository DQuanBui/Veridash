"""Examples: three seeded datasets with live findings and one-click analysis."""

from __future__ import annotations

import streamlit as st

from core.formatting import pretty
from core.loader import file_hash
from core.samples import EXAMPLES
from ui.branding import icon
from ui.components import SEVERITY_VARIANT, badge_html, esc, section_header, sparkline_svg
from ui.state import cached_analysis, example_trend, load_example

MIME = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

section_header(
    "Example datasets",
    "Three realistic, synthetic datasets with fictional names. Each has a few planted data issues "
    "so you can see the health check at work. The findings below are computed live.",
    top=True,
    icon_name="table",
)

cols = st.columns(3, gap="medium")
for col, ex in zip(cols, EXAMPLES.values(), strict=True):
    data = ex.read_bytes()
    analysis = cached_analysis(file_hash(data), ex.filename, None, None, None, None, True, data)
    health = analysis.health
    issues = [i for i in health.issues if i.severity != "info"][:3]
    findings = "".join(
        f"<li style='display:flex;gap:10px;align-items:baseline;margin:4px 0'>"
        f"{badge_html(i.severity, SEVERITY_VARIANT[i.severity])}<span>{esc(i.title)}</span></li>"
        for i in issues
    )
    metric = pretty(analysis.selection.metric) if analysis.selection.metric else "Records"
    with col, st.container(key=f"card-eqb_example_{ex.key}"):
        st.markdown(
            f"<div class='vd-exhead'><span class='vd-icon'>{icon(ex.icon)}</span>"
            f"<p class='vd-chart-title' style='font-size:18px'>{esc(ex.title)}</p></div>"
            + sparkline_svg(example_trend(ex.key), f"Trend of the {ex.title} example")
            + f"<div class='vd-badges' style='margin-top:12px'>{badge_html(ex.file_kind + ' file', 'slate')}"
            f"{badge_html(f'Health grade {health.grade}', 'teal')}</div>"
            f"<p class='vd-chart-insight'>{esc(ex.summary)}</p>"
            "<p style='font-weight:600;font-size:14px;margin:14px 0 6px 0'>What Veridash finds</p>"
            f"<ul style='list-style:none;padding:0;margin:0;font-size:14px;line-height:1.5'>{findings}</ul>"
            f"<p class='vd-chart-insight' style='margin-top:10px'>Main metric: <b>{esc(metric)}</b></p>",
            unsafe_allow_html=True,
        )
        with st.expander("Peek at the first rows"):
            st.dataframe(analysis.prepared.loaded.df.head(5), hide_index=True)
        with st.container(gap="small"):  # one block, so it pins to the card bottom
            if st.button("Analyze this", key=f"go_{ex.key}", type="primary", width="stretch"):
                load_example(ex.key)
                st.switch_page("views/analyze.py")
            st.download_button(
                f"Download {ex.filename}",
                data=data,
                file_name=ex.filename,
                mime=MIME.get(ex.filename.rsplit(".", 1)[-1], "application/octet-stream"),
                type="tertiary",
                width="stretch",
                on_click="ignore",
                key=f"dl_example_{ex.key}",
            )

st.write("")
st.caption(
    "Download any example to see the layout Veridash expects, edit it and upload it again. "
    "The datasets are generated the same way every time, and every company, store, product and "
    "ticker name is invented."
)
