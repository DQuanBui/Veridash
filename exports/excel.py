"""Excel report with native Excel charts (xlsxwriter, fully in memory).

Sheets:
    Summary   health, KPIs, insights (AI or rule-based), timestamp
    Profile   one row per column
    01 ... 08 one sheet per chart: its aggregated table plus a native chart
    Data      the cleaned dataset as an Excel Table with filters
"""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime

import pandas as pd
import xlsxwriter
from xlsxwriter.worksheet import Worksheet

from ai.factcheck import fact_check
from core.formatting import fmt_value, pretty
from core.insights_rules import Insights
from core.pipeline import Analysis
from core.recommender import ChartSpec
from ui.charts import correlation_matrix

EXCEL_MAX_ROWS = 1_048_575  # Excel's row limit minus the header row
TEAL = "#0D9488"
PALETTE = ["#0D9488", "#6366F1", "#F59E0B", "#EC4899", "#0EA5E9", "#84CC16", "#8B5CF6", "#F97316"]


def _sheet_name(index: int, title: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "", f"{index:02d} {title}")[:31].strip()
    name, n = base, 2
    while name.lower() in used:
        name = f"{base[:28]}~{n}"
        n += 1
    used.add(name.lower())
    return name


def _cell(value: object) -> object:
    """Convert pandas/numpy values into something xlsxwriter can write."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):
        return value.item()
    return value


class _Formats:
    def __init__(self, wb: xlsxwriter.Workbook) -> None:
        self.title = wb.add_format({"bold": True, "font_size": 18, "font_color": "#0F172A"})
        self.subtitle = wb.add_format({"font_color": "#64748B", "italic": True})
        self.h2 = wb.add_format({"bold": True, "font_size": 12, "font_color": "#0F766E"})
        self.header = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": TEAL, "border": 1,
                                     "border_color": "#0F766E", "valign": "vcenter"})
        self.text = wb.add_format({"text_wrap": True, "valign": "top"})
        self.label = wb.add_format({"bold": True, "valign": "top"})
        self.number = wb.add_format({"num_format": "#,##0.00"})
        self.integer = wb.add_format({"num_format": "#,##0"})
        self.date = wb.add_format({"num_format": "yyyy-mm-dd"})
        self.big = wb.add_format({"bold": True, "font_size": 16, "font_color": TEAL})
        self.code = wb.add_format({"font_name": "Consolas", "font_size": 9, "text_wrap": True, "valign": "top",
                                   "font_color": "#334155"})


def _write_table(ws: Worksheet, df: pd.DataFrame, row: int, col: int, fmt: _Formats) -> None:
    for j, name in enumerate(df.columns):
        ws.write(row, col + j, str(name), fmt.header)
    for i, record in enumerate(df.itertuples(index=False), start=1):
        for j, value in enumerate(record):
            v = _cell(value)
            if isinstance(v, datetime):
                ws.write_datetime(row + i, col + j, v, fmt.date)
            elif isinstance(v, float):
                ws.write_number(row + i, col + j, v, fmt.number)
            else:
                ws.write(row + i, col + j, v)


def _summary_sheet(wb: xlsxwriter.Workbook, analysis: Analysis, insights: Insights, fmt: _Formats) -> None:
    ws = wb.add_worksheet("Summary")
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 34)
    ws.set_column(1, 1, 22)
    ws.set_column(2, 2, 90)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    ws.write(0, 0, "Veridash report", fmt.title)
    ws.write(1, 0, f"{analysis.name} · generated {stamp}", fmt.subtitle)

    h = analysis.health
    ws.write(3, 0, "Data health", fmt.h2)
    ws.write(4, 0, "Health score", fmt.label)
    ws.write(4, 1, f"{h.score}/100 (grade {h.grade})", fmt.big)
    ws.write(5, 0, "Rows / columns", fmt.label)
    ws.write(5, 1, f"{analysis.profile.n_rows:,} / {analysis.profile.n_cols}")
    row = 7
    ws.write_row(row, 0, ["Issue", "Severity", "Why it matters"], fmt.header)
    for issue in h.issues:
        row += 1
        ws.write(row, 0, issue.title, fmt.text)
        ws.write(row, 1, issue.severity)
        ws.write(row, 2, f"{issue.detail} {issue.why}", fmt.text)

    row += 2
    ws.write(row, 0, "Key metrics", fmt.h2)
    row += 1
    ws.write_row(row, 0, ["KPI", "Value", "SQL that produced it"], fmt.header)
    for kpi in analysis.kpis:
        row += 1
        ws.write(row, 0, kpi.label, fmt.text)
        ws.write(row, 1, kpi.display)
        ws.write(row, 2, kpi.sql, fmt.code)

    report = fact_check(insights.texts(), analysis.facts)
    source = f"AI-generated ({insights.model})" if insights.source == "ai" else "Rule-based"
    row += 2
    ws.write(row, 0, "Insights", fmt.h2)
    ws.write(row, 1, source)
    ws.write(row, 2, f"Verified numbers: {report.verified}/{report.total}")
    sections = [
        ("Executive summary", [s.text for s in insights.summary]),
        ("Key findings", [s.text for s in insights.findings]),
        ("Recommendations (hypotheses)", [
            f"{r.hypothesis} Evidence: {r.evidence} How to validate: {r.how_to_validate}"
            for r in insights.recommendations
        ]),
        ("Data caveats", insights.caveats),
    ]
    for title, items in sections:
        row += 1
        ws.write(row, 0, title, fmt.label)
        for item in items:
            ws.write(row, 2, f"• {item}", fmt.text)
            row += 1
    row += 1
    ws.write(row, 0, "Methodology", fmt.label)
    ws.write(row, 2, "Every number was computed by DuckDB SQL on the uploaded data; each chart sheet lists its "
             "query. AI text (if any) was fact-checked against these computed values.", fmt.text)


def _profile_sheet(wb: xlsxwriter.Workbook, analysis: Analysis, fmt: _Formats) -> None:
    ws = wb.add_worksheet("Profile")
    rows = []
    for c in analysis.profile.columns:
        s = c.stats
        rows.append({
            "column": c.name, "type": str(c.col_type), "missing_pct": round(c.missing_pct, 2),
            "distinct": c.n_unique, "mean": s.get("mean") if c.col_type == "number" else None,
            "median": s.get("median") if c.col_type == "number" else None,
            "min": s.get("min") if c.col_type == "number" else None,
            "max": s.get("max") if c.col_type == "number" else None,
            "top_values": ", ".join(f"{v} ({n})" for v, n in c.top_values[:3]),
            "flags": ", ".join(f for f, on in (("mixed types", c.mixed_type), ("constant", c.is_constant)) if on),
        })
    df = pd.DataFrame(rows)
    _write_table(ws, df, 0, 0, fmt)
    ws.freeze_panes(1, 1)
    ws.set_column(0, 0, 24)
    ws.set_column(1, 7, 13)
    ws.set_column(8, 8, 50)
    ws.set_column(9, 9, 18)


def _chart_table(spec: ChartSpec) -> pd.DataFrame:
    df = spec.data.copy()
    if spec.kind == "histogram":
        kind = spec.meta.get("x_kind", "number")
        df.insert(0, "range", [f"{fmt_value(a, kind)} to {fmt_value(b, kind)}" for a, b in zip(df["bin_start"], df["bin_end"], strict=True)])
    return df


def _native_chart(wb: xlsxwriter.Workbook, sheet: str, spec: ChartSpec, df: pd.DataFrame):
    n = len(df)
    cols = list(df.columns)

    def ref(col_name: str) -> list:
        j = cols.index(col_name)
        return [sheet, 1, j, n, j]

    if spec.kind == "line":
        chart = wb.add_chart({"type": "line"})
        chart.add_series({"name": pretty(spec.y), "categories": ref(spec.x), "values": ref(spec.y),
                          "line": {"color": TEAL, "width": 2.25}, "marker": {"type": "circle", "size": 4,
                          "fill": {"color": TEAL}, "border": {"color": TEAL}}})
    elif spec.kind == "bar" and spec.meta.get("discrete"):
        chart = wb.add_chart({"type": "column"})
        chart.add_series({"name": "Records", "categories": ref(spec.x), "values": ref("records"),
                          "fill": {"color": TEAL}, "gap": 60})
    elif spec.kind == "bar":
        chart = wb.add_chart({"type": "bar"})
        series = {"name": pretty(spec.y), "categories": ref(spec.x), "values": ref(spec.y),
                  "fill": {"color": TEAL}, "gap": 60}
        if spec.meta.get("diverging"):
            series |= {"invert_if_negative": True, "invert_if_negative_color": "#DC2626"}
        chart.add_series(series)
        chart.set_y_axis({"reverse": True})
    elif spec.kind == "histogram":
        chart = wb.add_chart({"type": "column"})
        chart.add_series({"name": "Records", "categories": ref("range"), "values": ref("records"),
                          "fill": {"color": TEAL}, "gap": 10})
    elif spec.kind == "donut":
        chart = wb.add_chart({"type": "doughnut"})
        chart.add_series({"name": pretty(spec.y), "categories": ref(spec.x), "values": ref(spec.y),
                          "points": [{"fill": {"color": PALETTE[i % len(PALETTE)]}} for i in range(n)],
                          "data_labels": {"percentage": True}})
        chart.set_hole_size(55)
    elif spec.kind == "box":
        chart = wb.add_chart({"type": "column"})
        chart.add_series({"name": "Median", "categories": ref(spec.x), "values": ref("median"),
                          "fill": {"color": TEAL}, "gap": 60})
    elif spec.kind == "scatter":
        chart = wb.add_chart({"type": "scatter"})
        chart.add_series({"name": f"{pretty(spec.x)} vs {pretty(spec.y)}", "categories": ref(spec.x),
                          "values": ref(spec.y), "marker": {"type": "circle", "size": 4,
                          "fill": {"color": TEAL, "transparency": 50}, "border": {"none": True}}})
        chart.set_x_axis({"name": pretty(spec.x)})
        chart.set_y_axis({"name": pretty(spec.y)})
    else:
        return None
    chart.set_title({"name": spec.title, "name_font": {"size": 12, "bold": True}})
    chart.set_legend({"none": spec.kind != "donut"})
    chart.set_size({"width": 720, "height": 380})
    return chart


def _chart_sheet(wb: xlsxwriter.Workbook, index: int, spec: ChartSpec, used: set[str], fmt: _Formats) -> None:
    name = _sheet_name(index, spec.title, used)
    ws = wb.add_worksheet(name)
    df = _chart_table(spec)
    if spec.kind == "heatmap":
        df = correlation_matrix(spec).reset_index().rename(columns={"index": "column"})
    _write_table(ws, df, 0, 0, fmt)
    ws.freeze_panes(1, 0)
    ws.set_column(0, len(df.columns) - 1, 16)
    note_col = len(df.columns) + 1
    ws.set_column(note_col, note_col, 80)
    ws.write(0, note_col, spec.title, fmt.h2)
    ws.write(1, note_col, spec.insight, fmt.text)
    ws.write(2, note_col, "SQL that produced this table:", fmt.label)
    ws.write(3, note_col, spec.sql, fmt.code)
    ws.set_row(3, 15 * (spec.sql.count("\n") + 1))
    if spec.kind == "heatmap":
        n = len(df)
        ws.conditional_format(1, 1, n, n, {"type": "3_color_scale", "min_type": "num", "min_value": -1,
                                           "mid_type": "num", "mid_value": 0, "max_type": "num", "max_value": 1,
                                           "min_color": "#4F46E5", "mid_color": "#F1F5F9", "max_color": "#0D9488"})
        return
    chart = _native_chart(wb, name, spec, df)
    if chart is not None:
        ws.insert_chart(5, note_col, chart)


def _data_sheet(wb: xlsxwriter.Workbook, analysis: Analysis, fmt: _Formats) -> None:
    ws = wb.add_worksheet("Data")
    df = analysis.profile.df
    truncated = len(df) > EXCEL_MAX_ROWS
    df = df.head(EXCEL_MAX_ROWS)
    for j, col in enumerate(df.columns):
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            values = [None if pd.isna(v) else v.to_pydatetime() for v in series]
            ws.write_column(1, j, values, fmt.date)
            width = 12
        else:
            values = [_cell(v) for v in series.astype(object)]
            ws.write_column(1, j, values)
            width = min(40, max(10, len(str(col)) + 2, int(series.astype(str).str.len().head(500).max() or 0) + 2))
        ws.set_column(j, j, width)
    ws.add_table(0, 0, max(len(df), 1), len(df.columns) - 1, {
        "name": "VeridashData",
        "style": "Table Style Medium 2",
        "columns": [{"header": str(c)} for c in df.columns],
    })
    ws.freeze_panes(1, 0)
    if truncated:
        ws.write_comment(0, 0, f"Truncated to Excel's limit of {EXCEL_MAX_ROWS:,} rows.")


def build_excel(analysis: Analysis, insights: Insights | None = None) -> bytes:
    """Build the Excel report and return its bytes (never touches disk)."""
    buffer = io.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True, "nan_inf_to_errors": True, "remove_timezone": True})
    wb.set_properties({"title": f"Veridash report: {analysis.name}", "author": "Veridash"})
    fmt = _Formats(wb)
    _summary_sheet(wb, analysis, insights or analysis.rule_insights, fmt)
    _profile_sheet(wb, analysis, fmt)
    used = {"summary", "profile", "data"}
    for i, spec in enumerate(analysis.charts, start=1):
        _chart_sheet(wb, i, spec, used, fmt)
    _data_sheet(wb, analysis, fmt)
    wb.close()
    return buffer.getvalue()
