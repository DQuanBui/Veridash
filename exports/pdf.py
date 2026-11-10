"""PDF summary report (fpdf2 + static matplotlib charts), built in memory.

Layout (2-4 pages): title block, dataset and health summary, KPIs, the top
four charts, insights (labelled AI or rule-based) and a methodology note.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from matplotlib.ticker import FuncFormatter

from ai.factcheck import fact_check
from core.formatting import compact, fmt_value, pretty
from core.insights_rules import Insights
from core.pipeline import Analysis
from core.recommender import ChartSpec
from ui.charts import correlation_matrix

TEAL = "#0D9488"
RED = "#DC2626"
INK = (15, 23, 42)
MUTED = (100, 116, 139)
TEAL_RGB = (13, 148, 136)
PALETTE = ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#0EA5E9", "#84CC16", "#8B5CF6", "#F97316"]
FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
MAX_CHARTS = 4


def _axis_formatter(kind: str) -> FuncFormatter:
    prefix = "$" if kind == "currency" else ""
    suffix = "%" if kind == "percent" else ""
    return FuncFormatter(lambda v, _: f"{prefix}{f'{v:g}' if abs(v) < 1000 else compact(v)}{suffix}")


def _style(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#CBD5E1")
    ax.tick_params(colors="#64748B", labelsize=7)
    ax.grid(axis="y", color="#F1F5F9", linewidth=0.8)
    ax.set_axisbelow(True)


def _png(spec: ChartSpec) -> bytes:
    """Render one chart spec to PNG bytes."""
    fig, ax = plt.subplots(figsize=(4.6, 2.7), dpi=170)
    df = spec.data
    if spec.kind == "line":
        ax.plot(df[spec.x], df[spec.y], color=TEAL, linewidth=1.6)
        ax.fill_between(df[spec.x], df[spec.y], color=TEAL, alpha=0.08)
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(_axis_formatter(spec.value_kind))
        fig.autofmt_xdate()
    elif spec.kind == "bar" and spec.meta.get("discrete"):
        ax.bar([str(v) for v in df[spec.x]], df["records"], color=TEAL)
    elif spec.kind == "bar":
        labels = [str(v)[:22] for v in df[spec.x]][::-1]
        values = df[spec.y][::-1]
        colors = [TEAL if v >= 0 else RED for v in values] if spec.meta.get("diverging") else TEAL
        ax.barh(labels, values, color=colors)
        if spec.meta.get("diverging"):
            ax.axvline(0, color="#64748B", linewidth=0.8)
        ax.xaxis.set_major_formatter(_axis_formatter(spec.value_kind))
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
        ax.grid(axis="x", color="#F1F5F9")
        ax.grid(axis="y", visible=False)
    elif spec.kind == "histogram":
        ax.bar(df["bin_start"], df["records"], width=(df["bin_end"] - df["bin_start"]) * 0.92, align="edge", color=TEAL)
        ax.axvline(float(df["median"].iloc[0]), color="#0F172A", linestyle=":", linewidth=1)
        ax.xaxis.set_major_formatter(_axis_formatter(spec.meta.get("x_kind", "number")))
    elif spec.kind == "donut":
        ax.pie(df[spec.y], labels=[str(v)[:18] for v in df[spec.x]], colors=PALETTE[: len(df)],
               wedgeprops={"width": 0.38, "edgecolor": "white"}, autopct="%1.0f%%", pctdistance=0.81,
               textprops={"fontsize": 7, "color": "#334155"}, startangle=90, counterclock=False)
        ax.axis("equal")
    elif spec.kind == "box":
        stats = [
            {"label": str(r[spec.x])[:12], "q1": r["q1"], "med": r["median"], "q3": r["q3"],
             "whislo": r["lower_fence"], "whishi": r["upper_fence"], "fliers": []}
            for _, r in df.iterrows()
        ]
        ax.bxp(stats, showfliers=False, patch_artist=True,
               boxprops={"facecolor": "#CCFBF1", "edgecolor": TEAL}, medianprops={"color": TEAL})
        ax.yaxis.set_major_formatter(_axis_formatter(spec.value_kind))
    elif spec.kind == "heatmap":
        m = correlation_matrix(spec)
        im = ax.imshow(m.values, cmap="BrBG", vmin=-1, vmax=1)
        names = [pretty(c)[:12] for c in m.columns]
        ax.set_xticks(range(len(names)), names, rotation=35, ha="right")
        ax.set_yticks(range(len(names)), names)
        for i in range(len(names)):
            for j in range(len(names)):
                ax.text(j, i, f"{m.values[i, j]:.2f}", ha="center", va="center", fontsize=6)
        fig.colorbar(im, ax=ax, shrink=0.8)
    elif spec.kind == "scatter":
        ax.scatter(df[spec.x], df[spec.y], s=6, color=TEAL, alpha=0.4, linewidths=0)
        ax.set_xlabel(pretty(spec.x), fontsize=7, color="#64748B")
        ax.set_ylabel(pretty(spec.y), fontsize=7, color="#64748B")
    if spec.kind not in ("donut", "heatmap"):
        _style(ax)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


class _Report(FPDF):
    def __init__(self, footer_text: str) -> None:
        super().__init__(format="A4")
        self._footer_text = footer_text
        self.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(16, 14, 16)

    def footer(self) -> None:
        self.set_y(-11)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"{self._footer_text} · page {self.page_no()}", align="R")

    def h2(self, text: str) -> None:
        self.ln(2)
        self.set_font("DejaVu", "B", 11)
        self.set_text_color(*TEAL_RGB)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*INK)

    def para(self, text: str, size: float = 9, bold: bool = False, color=INK, indent: float = 0) -> None:
        self.set_font("DejaVu", "B" if bold else "", size)
        self.set_text_color(*color)
        self.set_x(self.l_margin + indent)
        self.multi_cell(self.epw - indent, size * 0.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def bullet(self, text: str, size: float = 9) -> None:
        self.set_font("DejaVu", "", size)
        self.set_text_color(*INK)
        self.set_x(self.l_margin)
        self.cell(4, size * 0.5, "•")
        self.multi_cell(self.epw - 4, size * 0.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _title_block(pdf: _Report, analysis: Analysis) -> None:
    pdf.set_fill_color(*TEAL_RGB)
    pdf.rect(0, 0, pdf.w, 4, style="F")
    pdf.set_y(12)
    pdf.set_font("DejaVu", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, "Veridash report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    p = analysis.profile
    pdf.para(f"{analysis.name} · {p.n_rows:,} rows · {p.n_cols} columns · generated {stamp}", 9, color=MUTED)


def _health_and_kpis(pdf: _Report, analysis: Analysis) -> None:
    h = analysis.health
    pdf.h2("Data health")
    y = pdf.get_y()
    pdf.set_draw_color(226, 232, 240)
    pdf.set_fill_color(240, 253, 250)
    pdf.rect(pdf.l_margin, y, 38, 24, style="DF", round_corners=True, corner_radius=2)
    pdf.set_xy(pdf.l_margin, y + 3)
    pdf.set_font("DejaVu", "B", 20)
    pdf.set_text_color(*TEAL_RGB)
    pdf.cell(38, 10, str(h.score), align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(38, 6, f"out of 100 · grade {h.grade}", align="C")
    pdf.set_xy(pdf.l_margin + 44, y)
    issues = [i for i in h.issues if i.severity != "info"][:5] or []
    pdf.set_left_margin(pdf.l_margin + 44)
    if not issues:
        pdf.para("No issues found.", 9)
    for issue in issues:
        pdf.para(f"[{issue.severity}] {issue.title}", 8.5, bold=True)
        pdf.para(issue.why, 8, color=MUTED)
        if issue.fix:
            pdf.para(f"How to fix: {issue.fix}", 8, color=MUTED)
    pdf.set_left_margin(16)
    pdf.set_y(max(pdf.get_y(), y + 26))

    pdf.h2("Key metrics")
    y = pdf.get_y()
    n = max(len(analysis.kpis), 1)
    gap = 4
    w = (pdf.epw - gap * (n - 1)) / n
    for i, kpi in enumerate(analysis.kpis):
        x = pdf.l_margin + i * (w + gap)
        pdf.rect(x, y, w, 20, style="D", round_corners=True, corner_radius=2)
        pdf.set_xy(x + 3, y + 3)
        size = 7.0
        pdf.set_font("DejaVu", "", size)
        while pdf.get_string_width(kpi.label.upper()) > w - 6 and size > 5:
            size -= 0.5
            pdf.set_font("DejaVu", "", size)
        pdf.set_text_color(*MUTED)
        pdf.cell(w - 6, 4, kpi.label.upper())
        pdf.set_xy(x + 3, y + 9)
        pdf.set_font("DejaVu", "B", 14)
        pdf.set_text_color(*INK)
        pdf.cell(w - 6, 8, kpi.display)
    pdf.set_y(y + 24)


def _charts(pdf: _Report, analysis: Analysis) -> None:
    charts = [c for c in analysis.charts if c.kind != "heatmap"][:MAX_CHARTS]
    if not charts:
        return
    pdf.h2("Top charts")
    col_w = (pdf.epw - 6) / 2
    img_h = col_w * 2.7 / 4.6
    for i, spec in enumerate(charts):
        if i % 2 == 0:
            if pdf.get_y() + img_h + 22 > pdf.h - pdf.b_margin:
                pdf.add_page()
            row_y = pdf.get_y()
        x = pdf.l_margin + (i % 2) * (col_w + 6)
        pdf.set_xy(x, row_y)
        pdf.set_font("DejaVu", "B", 9)
        pdf.set_text_color(*INK)
        pdf.cell(col_w, 5, spec.title[:60])
        pdf.image(io.BytesIO(_png(spec)), x=x, y=row_y + 6, w=col_w, h=img_h)
        pdf.set_xy(x, row_y + 7 + img_h)
        pdf.set_font("DejaVu", "", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(col_w, 3.6, spec.insight)
        if i % 2 == 1 or i == len(charts) - 1:
            pdf.set_y(row_y + 7 + img_h + 14)


def _insights(pdf: _Report, analysis: Analysis, insights: Insights) -> None:
    report = fact_check(insights.texts(), analysis.facts)
    label = f"AI-generated ({insights.model})" if insights.source == "ai" else "Rule-based"
    pdf.h2("Insights")
    pdf.para(f"{label} · verified numbers: {report.verified}/{report.total}", 8, color=MUTED)
    pdf.para("Executive summary", 9.5, bold=True)
    for s in insights.summary:
        pdf.bullet(s.text)
    pdf.ln(1)
    pdf.para("Key findings", 9.5, bold=True)
    for s in insights.findings:
        pdf.bullet(s.text)
    pdf.ln(1)
    pdf.para("Recommendations to test", 9.5, bold=True)
    for r in insights.recommendations:
        pdf.bullet(f"{r.hypothesis} Evidence: {r.evidence} How to validate: {r.how_to_validate}")
    pdf.ln(1)
    pdf.para("Data caveats", 9.5, bold=True)
    for c in insights.caveats:
        pdf.bullet(c)


def _methodology(pdf: _Report, analysis: Analysis) -> None:
    sel = analysis.selection
    metric = pretty(sel.metric) if sel.metric else "record count"
    pdf.ln(3)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + pdf.epw, pdf.get_y())
    pdf.ln(2)
    pdf.para(
        "Methodology. Every number in this report was computed by code: DuckDB SQL over the uploaded file, "
        f"using {metric} ({sel.agg}) as the primary metric"
        + (f" and {sel.date_col} at {sel.grain} grain" if sel.date_col else "")
        + ". The health score starts at 100 and subtracts capped penalties for missing cells, duplicate rows, "
        "mixed-type, constant and high-outlier columns. AI, when used, only selects and explains computed facts; "
        "every number in its text is checked against them. "
        f"Health score {fmt_value(analysis.health.score, 'int')}/100. The file was processed in memory and not stored.",
        7.5,
        color=MUTED,
    )


def build_pdf(analysis: Analysis, insights: Insights | None = None) -> bytes:
    """Build the PDF summary and return its bytes (never touches disk)."""
    pdf = _Report(f"Veridash · {analysis.name}")
    pdf.add_page()
    _title_block(pdf, analysis)
    _health_and_kpis(pdf, analysis)
    _charts(pdf, analysis)
    pdf.add_page()
    _insights(pdf, analysis, insights or analysis.rule_insights)
    _methodology(pdf, analysis)
    return bytes(pdf.output())
