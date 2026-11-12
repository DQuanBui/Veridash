"""Reusable UI building blocks rendered as small, escaped HTML snippets.

Rule: any value that may come from user data (column names, category labels,
file names) must pass through :func:`esc` before it is placed in HTML.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Iterable, Sequence

import streamlit as st

from core.settings import AUTHOR_EMAIL, AUTHOR_NAME, GITHUB_URL, LINKEDIN_URL
from ui.branding import icon, wordmark

TYPE_BADGE_VARIANT = {
    "number": "teal",
    "date": "indigo",
    "category": "violet",
    "boolean": "sky",
    "text": "slate",
    "id": "amber",
}
SEVERITY_VARIANT = {"high": "red", "medium": "amber", "low": "slate", "info": "sky"}


def esc(value: object) -> str:
    """HTML-escape any value for safe interpolation into markup."""
    return html.escape(str(value), quote=True)


def _md(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def badge_html(text: str, variant: str = "slate") -> str:
    """Return a pill badge. ``text`` is escaped."""
    return f'<span class="vd-badge {esc(variant)}">{esc(text)}</span>'


def badges(items: Iterable[tuple[str, str]]) -> None:
    """Render a row of ``(text, variant)`` badges."""
    _md('<div class="vd-badges">' + "".join(badge_html(t, v) for t, v in items) + "</div>")


def type_badge_html(col_type: str) -> str:
    """Badge for a detected column type."""
    return badge_html(col_type, TYPE_BADGE_VARIANT.get(col_type, "slate"))


def source_badge_html(source: str, model: str | None = None) -> str:
    """Badge stating whether insights are AI-generated or rule-based."""
    if source == "ai":
        label = f"AI-generated · {model}" if model else "AI-generated"
        return badge_html(label, "indigo")
    return badge_html("Rule-based", "slate")


def verified_badge_html(verified: int, total: int) -> str:
    """Badge such as "Verified numbers: 12/12" (green only when all verify)."""
    variant = "green" if total and verified == total else ("slate" if total == 0 else "amber")
    return badge_html(f"Verified numbers: {verified}/{total}", variant)



def section_header(title: str, subtitle: str = "", kicker: str = "", center: bool = False, top: bool = False,
                   icon_name: str | None = None) -> None:
    """Section heading with optional kicker line and subtitle.

    ``top`` marks a page title (no top margin, a faint grid behind it); ``icon_name`` adds an icon tile beside it.
    """
    cls = "vd-section" + (" center" if center else "") + (" top" if top else "")
    k = f'<div class="vd-kicker">{esc(kicker)}</div>' if kicker else ""
    s = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    heading = f"<h2>{esc(title)}</h2>"
    if icon_name:
        heading = f'<div class="vd-title"><span class="vd-icon">{icon(icon_name, 22)}</span>{heading}</div>'
    _md(f'<div class="{cls}">{k}{heading}{s}</div>')


def kpi_card(label: str, value: str, sub: str = "") -> None:
    """A single KPI tile."""
    s = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    _md(
        f'<div class="vd-kpi"><div class="label">{esc(label)}</div>'
        f'<div class="value">{esc(value)}</div>{s}</div>'
    )



def step_card(number: int, icon_name: str, title: str, text: str) -> None:
    """Numbered step card for "How it works"."""
    _md(
        f'<div class="vd-card vd-step"><span class="num">0{number}</span>'
        f'<div class="vd-icon">{icon(icon_name)}</div>'
        f"<h4>{esc(title)}</h4><p>{esc(text)}</p></div>"
    )


def callout(text: str, title: str = "", kind: str = "info") -> None:
    """Bordered note. ``kind`` is ``info``, ``warn`` or ``error``."""
    t = f'<div class="title">{esc(title)}</div>' if title else ""
    _md(f'<div class="vd-callout {esc(kind)}">{t}{esc(text)}</div>')


def chart_card(
    title: str,
    insight: str,
    render: Callable[[], None],
    key: str,
    notes: Iterable[tuple[str, str]] = (),
) -> None:
    """Card with a title, one computed insight sentence and a body callback."""
    with st.container(key=f"card_{key}"):
        _md(f'<p class="vd-chart-title">{esc(title)}</p>')
        _md(f'<p class="vd-chart-insight">{esc(insight)}</p>')
        notes = list(notes)
        if notes:
            badges(notes)
        render()


def sparkline_svg(values: Sequence[float], label: str, width: int = 160, height: int = 40) -> str:
    """A small trend line with a soft fill and a dot on the latest value. ``label`` describes it for screen readers."""
    vals = [float(v) for v in values if v == v]  # drop NaN
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pts = [(2 + i * (width - 6) / (len(vals) - 1), height - 4 - (v - lo) / span * (height - 10))
           for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pts[0][0]:.1f},{height} {line} {pts[-1][0]:.1f},{height}"
    x, y = pts[-1]
    return (
        f'<svg class="vd-spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" '
        f'aria-label="{esc(label)}"><polygon class="a" points="{area}"/><polyline class="l" points="{line}"/>'
        f'<circle class="d" cx="{x:.1f}" cy="{y:.1f}" r="2.6"/></svg>'
    )


def compare_table(left_title: str, right_title: str, rows: Iterable[tuple[str, str, str]]) -> None:
    """Two-column comparison; the right column is highlighted as Veridash's."""
    body = "".join(
        f"<tr><th scope='row'>{esc(label)}</th><td><span class='lbl'>{esc(left_title)}</span>{esc(left)}</td>"
        f"<td class='ours'><span class='lbl'>{esc(right_title)}</span>{esc(right)}</td></tr>"
        for label, left, right in rows
    )
    _md(
        "<div class='vd-compare'><table><thead><tr><th></th>"
        f"<th>{esc(left_title)}</th><th class='ours'>{esc(right_title)}</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


FOOTER_PAGES = [
    ("views/analyze.py", "Analyze"),
    ("views/compare.py", "Compare"),
    ("views/examples.py", "Examples"),
    ("views/benchmark.py", "Benchmark"),
    ("views/guide.py", "Guide"),
]


def footer() -> None:
    """Site footer: what Veridash is, links to every page and contact links, with the credit underneath.

    Page links use ``st.page_link`` so they switch pages inside the app and keep the visitor's open file.
    """
    with st.container(key="vd_footer"):
        brand, pages, contact = st.columns([2.2, 1, 1], gap="large")
        with brand:
            _md(f'<div class="vd-footer-brand">{wordmark(22)}<p>Verifiable data analysis: every number is '
                "computed by code, shown with its query and checked before you see it.</p></div>")
        with pages:
            _md('<p class="vd-footer-h">Product</p>')
            with st.container(gap=None):
                for path, label in FOOTER_PAGES:
                    st.page_link(path, label=label)
        with contact:
            _md(
                '<p class="vd-footer-h">Contact</p><nav class="vd-footer-links" aria-label="Contact">'
                f'<a href="mailto:{esc(AUTHOR_EMAIL)}">Email</a>'
                f'<a href="{esc(LINKEDIN_URL)}" target="_blank" rel="noopener">LinkedIn</a>'
                f'<a href="{esc(GITHUB_URL)}" target="_blank" rel="noopener">GitHub</a></nav>'
            )
        _md(f'<div class="vd-footer-credit">Built by {esc(AUTHOR_NAME)}</div>')
