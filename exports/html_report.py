"""Shareable HTML report: one self-contained file that opens in any browser.

The report needs no server, no internet and no JavaScript. Charts are inline
SVG, styles are inline CSS (with a dark mode), and the SQL behind each chart
and KPI sits in a collapsible block. Every number in the insights is
fact-checked: a verified number links to the fact it matched in the appendix,
and an unverified one is marked.

All text that may come from the uploaded file is HTML-escaped.
"""

from __future__ import annotations

import html
import io
import re
from datetime import UTC, datetime

import matplotlib.pyplot as plt

from ai.factcheck import NumberClaim, check_text
from core.facts import FactPack
from core.formatting import pretty
from core.insights_rules import Insights
from core.pipeline import Analysis
from core.recommender import ChartSpec
from exports.audit import audit_table
from exports.pdf import chart_figure

MAX_CHARTS = 6
SITE_URL = "https://veridash.streamlit.app"


def esc(value: object) -> str:
    """HTML-escape any value."""
    return html.escape(str(value), quote=True)


def _anchor(fact_id: str) -> str:
    return "fact-" + re.sub(r"[^A-Za-z0-9_-]", "-", fact_id)


def _svg(spec: ChartSpec) -> str:
    """The chart as inline SVG, text kept as text so it stays small and readable."""
    with plt.rc_context({"svg.fonttype": "none", "font.family": "sans-serif"}):
        fig = chart_figure(spec)
        buf = io.StringIO()
        fig.savefig(buf, format="svg", facecolor="white")
        plt.close(fig)
    svg = buf.getvalue()
    svg = svg[svg.index("<svg") :]  # drop the XML prolog and doctype
    return re.sub(r'(<svg[^>]*?)\swidth="[^"]*"\sheight="[^"]*"', r"\1", svg, count=1)


def linked_text(text: str, claims: list[NumberClaim], pack: FactPack) -> str:
    """Escape ``text``; verified numbers link to their fact, unverified ones are marked."""
    facts = pack.by_id()
    out, pos = [], 0
    for c in claims:
        out.append(esc(text[pos : c.start]))
        raw = esc(text[c.start : c.end])
        if c.verified and c.fact_id in facts:
            fact = facts[c.fact_id]
            out.append(f'<a class="ok" href="#{_anchor(c.fact_id)}" title="Verified: {esc(fact.label)}">{raw}</a>')
        elif c.verified:
            out.append(f'<span class="ok" title="Verified against the date range">{raw}</span>')
        else:
            why = c.reason or "Not found in the computed facts"
            out.append(f'<span class="bad" title="{esc(why)}">{raw}<span class="sr"> (not verified)</span></span>')
        pos = c.end
    out.append(esc(text[pos:]))
    return "".join(out)


_CSS = """
:root { color-scheme: light dark; --text: #0F172A; --muted: #64748B; --border: #E2E8F0; --surface: #FFFFFF;
  --subtle: #F8FAFC; --accent: #0F766E; --primary: #0D9488; --tint: #F0FDFA; --bad: #B91C1C; --bad-bg: #FEE2E2; }
@media (prefers-color-scheme: dark) {
  :root { --text: #E2E8F0; --muted: #94A3B8; --border: #243045; --surface: #111A2C; --subtle: #0B1220;
    --accent: #5EEAD4; --tint: rgba(20,184,166,0.12); --bad: #FCA5A5; --bad-bg: rgba(239,68,68,0.22); }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--subtle); color: var(--text); line-height: 1.55;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 980px; margin: 0 auto; padding: 32px 16px 56px; }
header .brand { font-size: 14px; font-weight: 600; color: var(--accent); }
h1 { font-size: clamp(26px, 4vw, 36px); margin: 6px 0 4px; letter-spacing: -.02em; }
h2 { font-size: 20px; margin: 36px 0 12px; letter-spacing: -.01em; }
.meta { color: var(--muted); font-size: 14px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.kpi .label { font-size: 13px; font-weight: 500; color: var(--muted); }
.kpi .value { font-size: 26px; font-weight: 700; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi .sub { font-size: 13px; color: var(--muted); }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr)); gap: 14px; }
.chart h3 { font-size: 15px; margin: 0 0 2px; }
.chart p { margin: 0 0 8px; color: var(--muted); font-size: 13.5px; }
.chart svg { width: 100%; height: auto; display: block; background: #FFFFFF; border-radius: 8px; }
details { margin-top: 8px; font-size: 13px; }
summary { cursor: pointer; color: var(--accent); font-weight: 600; }
pre { white-space: pre-wrap; word-break: break-word; background: var(--subtle); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 12px; font-size: 12px; margin: 8px 0 0; }
ul.ins { margin: 0; padding-left: 20px; } ul.ins li { margin: 6px 0; }
a.ok, span.ok { color: var(--accent); font-weight: 600; text-decoration: underline dotted; text-underline-offset: 3px; }
span.bad { color: var(--bad); background: var(--bad-bg); border-radius: 4px; padding: 0 3px; font-weight: 600; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.badge { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 999px;
  background: var(--tint); color: var(--accent); border: 1px solid var(--border); margin-right: 6px; }
.issue { padding: 10px 0; border-bottom: 1px solid var(--border); } .issue:last-child { border-bottom: none; }
.issue b { display: block; } .issue span { color: var(--muted); font-size: 14px; }
.score { font-size: 40px; font-weight: 800; color: var(--primary); line-height: 1; }
.health { display: grid; grid-template-columns: 140px 1fr; gap: 20px; align-items: start; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 13px; }
td code { font-size: 12px; color: var(--muted); word-break: break-all; }
td a { color: var(--accent); }
.all { margin-top: 14px; }
tr:target { background: var(--tint); }
.scroll { overflow-x: auto; }
footer { margin-top: 40px; color: var(--muted); font-size: 13px; text-align: center; }
footer a { color: var(--accent); }
@media (max-width: 640px) { .health { grid-template-columns: 1fr; } }
@media print { body { background: #fff; } details { display: none; } .card { break-inside: avoid; } }
"""


def _kpis(analysis: Analysis) -> str:
    tiles = []
    for kpi in analysis.kpis:
        sub = f'<div class="sub">{esc(kpi.note)}</div>' if kpi.note else ""
        tiles.append(
            f'<div class="card kpi"><div class="label">{esc(kpi.label)}</div>'
            f'<div class="value">{esc(kpi.display)}</div>{sub}'
            f"<details><summary>SQL</summary><pre>{esc(kpi.sql)}</pre></details></div>"
        )
    return f'<div class="kpis">{"".join(tiles)}</div>'


def _health(analysis: Analysis) -> str:
    h = analysis.health
    issues = [i for i in h.issues if i.severity != "info"]
    rows = "".join(
        f'<div class="issue"><b>{esc(i.title)}</b><span>{esc(i.why)}</span>'
        + (f"<br><span>How to fix: {esc(i.fix)}</span>" if i.fix else "")
        + "</div>"
        for i in issues
    ) or '<div class="issue"><b>No issues found.</b></div>'
    return (
        '<div class="card health"><div><div class="score">'
        f'{h.score}</div><div class="meta">out of 100 · grade {esc(h.grade)}</div></div>'
        f"<div>{rows}</div></div>"
    )


def _charts(analysis: Analysis) -> str:
    cards = []
    for spec in analysis.charts[:MAX_CHARTS]:
        cards.append(
            f'<section class="card chart" id="chart-{esc(spec.key)}"><h3>{esc(spec.title)}</h3>'
            f"<p>{esc(spec.insight)}</p>{_svg(spec)}"
            f"<details><summary>SQL</summary><pre>{esc(spec.sql)}</pre></details></section>"
        )
    return f'<div class="charts">{"".join(cards)}</div>'


def _insights(analysis: Analysis, insights: Insights) -> tuple[str, int, int, set[str]]:
    """The insights as HTML, the verified and total number counts, and the facts they matched."""
    pack = analysis.facts
    verified = total = 0
    matched: set[str] = set()

    def item(text: str) -> str:
        nonlocal verified, total
        claims = check_text(text, pack)
        total += len(claims)
        verified += sum(c.verified for c in claims)
        matched.update(c.fact_id for c in claims if c.verified and c.fact_id)
        return f"<li>{linked_text(text, claims, pack)}</li>"

    parts = []
    for title, texts in (
        ("Summary", [s.text for s in insights.summary]),
        ("Key findings", [s.text for s in insights.findings]),
        ("Recommendations to test", [f"{r.hypothesis} {r.evidence} {r.how_to_validate}" for r in insights.recommendations]),
        ("Data caveats", list(insights.caveats)),
    ):
        if texts:
            parts.append(f'<h3>{esc(title)}</h3><ul class="ins">{"".join(item(t) for t in texts)}</ul>')
    return "".join(parts), verified, total, matched


_SHORT = {"dataset": "File loader (Python)", "health": "Health check (Python)", "profile": "Column profile (Python)"}


def _fact_rows(table, chart_keys: set[str], anchors: bool) -> str:
    rows = []
    for r in table.itertuples(index=False):
        if r.source in chart_keys:
            where = f'<a href="#chart-{esc(r.source)}">{esc(r.source)} chart</a>'
        elif r.source == "kpi":
            where = "KPI query (see Key metrics)"
        elif r.sql:
            where = f"<details><summary>SQL</summary><pre>{esc(r.sql)}</pre></details>"
        else:
            where = esc(_SHORT.get(r.source, r.computed_by))
        row_id = f' id="{_anchor(r.fact_id)}"' if anchors else ""
        rows.append(
            f"<tr{row_id}><td><code>{esc(r.fact_id)}</code></td><td>{esc(r.label)}</td>"
            f"<td><b>{esc(r.display)}</b></td><td>{where}</td></tr>"
        )
    head = "<thead><tr><th>Fact</th><th>What it is</th><th>Value</th><th>Computed by</th></tr></thead>"
    return f'<table>{head}<tbody>{"".join(rows)}</tbody></table>'


def _appendix(analysis: Analysis, insights: Insights, matched: set[str]) -> str:
    """Facts used in the insights first (link targets), then every fact, folded away."""
    table = audit_table(analysis, insights)
    chart_keys = {c.key for c in analysis.charts[:MAX_CHARTS]}
    used = table[table["fact_id"].isin(matched | insights.cited_ids())]
    return (
        f'<div class="card scroll">{_fact_rows(used, chart_keys, anchors=True)}'
        f'<details class="all"><summary>Show all {len(table)} computed facts</summary>'
        f"{_fact_rows(table, chart_keys, anchors=False)}</details></div>"
    )


def build_html_report(analysis: Analysis, insights: Insights | None = None) -> bytes:
    """Build the self-contained HTML report and return it as UTF-8 bytes."""
    insights = insights or analysis.rule_insights
    p, sel = analysis.profile, analysis.selection
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    source = f"AI-generated ({insights.model})" if insights.source == "ai" else "Rule-based"
    insights_html, verified, total, matched = _insights(analysis, insights)
    metric = pretty(sel.metric) if sel.metric else "record count"
    method = (
        f"Every number was computed by code: DuckDB SQL over the file, with {esc(metric)} ({esc(sel.agg)}) as the "
        "primary metric" + (f" and {esc(sel.date_col)} by {esc(sel.grain)}" if sel.date_col else "") + ". "
        "The insights were then fact-checked: each number must match a computed fact, allowing only for "
        "rounding. Click a highlighted number to see the fact it matched."
    )
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(analysis.name)} · Veridash report</title><style>{_CSS}</style></head>
<body><main>
<header><div class="brand">Veridash report</div><h1>{esc(analysis.name)}</h1>
<div class="meta">{p.n_rows:,} rows · {p.n_cols} columns · generated {stamp}</div></header>
<h2>Key metrics</h2>{_kpis(analysis)}
<h2>Data health</h2>{_health(analysis)}
<h2>Charts</h2>{_charts(analysis)}
<h2>Insights</h2><div class="card"><span class="badge">{esc(source)}</span>
<span class="badge">Verified numbers: {verified}/{total}</span>{insights_html}</div>
<h2>Where every number came from</h2>
<p class="meta">{method}</p>{_appendix(analysis, insights, matched)}
<footer>Made with <a href="{SITE_URL}">Veridash</a>. The file was processed in memory and not stored.</footer>
</main></body></html>
"""
    return doc.encode("utf-8")
