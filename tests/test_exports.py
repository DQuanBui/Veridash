"""Tests for the Excel, PDF and Power BI exports."""

from __future__ import annotations

import io

import openpyxl
import pytest

from core.pipeline import analyze, prepare
from core.samples import EXAMPLES
from exports.excel import build_excel


@pytest.fixture(scope="module", params=list(EXAMPLES))
def analysis(request):
    ex = EXAMPLES[request.param]
    return analyze(prepare(ex.read_bytes(), ex.filename))


def test_excel_opens_and_has_expected_sheets(analysis):
    data = build_excel(analysis)
    wb = openpyxl.load_workbook(io.BytesIO(data))
    names = wb.sheetnames
    assert names[0] == "Summary"
    assert names[1] == "Profile"
    assert names[-1] == "Data"
    assert len(names) == 3 + len(analysis.charts)
    assert all(len(n) <= 31 for n in names)


def test_excel_data_sheet_is_a_full_table(analysis):
    wb = openpyxl.load_workbook(io.BytesIO(build_excel(analysis)))
    ws = wb["Data"]
    assert ws.max_row == analysis.profile.n_rows + 1
    assert [c.value for c in ws[1]] == list(analysis.profile.df.columns)
    assert "VeridashData" in ws.tables
    assert ws.freeze_panes == "A2"


def test_excel_has_native_charts(analysis):
    wb = openpyxl.load_workbook(io.BytesIO(build_excel(analysis)))
    chart_sheets = [wb[n] for n in wb.sheetnames[2:-1]]
    with_charts = [ws for ws in chart_sheets if ws._charts]
    non_heatmap = [c for c in analysis.charts if c.kind != "heatmap"]
    assert len(with_charts) == len(non_heatmap)


def test_excel_summary_mentions_health_and_verification(analysis):
    wb = openpyxl.load_workbook(io.BytesIO(build_excel(analysis)))
    text = " ".join(str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value)
    assert f"{analysis.health.score}/100" in text
    assert "Verified numbers:" in text
    assert "Rule-based" in text


def _pdf_pages(data: bytes) -> int:
    import re

    return len(re.findall(rb"/Type /Page\b", data))


def test_pdf_has_two_to_four_pages(analysis):
    from exports.pdf import build_pdf

    data = build_pdf(analysis)
    assert data.startswith(b"%PDF")
    assert 2 <= _pdf_pages(data) <= 4


def test_powerbi_kit_contents(analysis):
    import zipfile

    from exports.powerbi import build_powerbi_kit

    zf = zipfile.ZipFile(io.BytesIO(build_powerbi_kit(analysis)))
    assert sorted(zf.namelist()) == ["QUICKSTART.md", "data.csv", "date_table.dax", "load_data.pq", "measures.dax"]
    csv_text = zf.read("data.csv").decode("utf-8")
    assert csv_text.splitlines()[0].split(",") == list(analysis.profile.df.columns)
    assert len(csv_text.strip().splitlines()) == analysis.profile.n_rows + 1
    m = zf.read("load_data.pq").decode()
    assert all(f'"{c}"' in m for c in analysis.profile.df.columns)
    assert f"Columns = {analysis.profile.n_cols}" in m
    dax = zf.read("measures.dax").decode()
    assert "Record Count = COUNTROWS ( Data )" in dax
    assert "% of Total =" in dax
    if analysis.selection.date_col:
        assert "SAMEPERIODLASTYEAR" in dax and "DATEADD" in dax and "Running" in dax
        assert "CALENDAR ( DATE (" in zf.read("date_table.dax").decode()
    if analysis.selection.metric:
        assert f"Data[{analysis.selection.metric}]" in dax
    assert "Five steps" in zf.read("QUICKSTART.md").decode()


def test_audit_trail_lists_every_fact_with_its_sql(analysis):
    from exports.audit import audit_table, build_audit_csv

    table = audit_table(analysis, analysis.rule_insights)
    assert len(table) == len(analysis.facts.facts)
    assert table["fact_id"].is_unique
    kpi_row = table[table["fact_id"] == "kpi.records"].iloc[0]
    assert kpi_row["sql"].startswith("SELECT COUNT(*)")
    for chart in analysis.charts:
        rows = table[table["source"] == chart.key]
        assert (rows["sql"] == chart.sql).all()
    # Python-computed facts say where they came from instead of showing SQL.
    health = table[table["source"] == "health"]
    assert (health["sql"] == "").all() and health["computed_by"].str.startswith("Health check").all()
    # Every fact the rule insights cite is marked.
    cited = set(table.loc[table["cited_in_insights"] == "yes", "fact_id"])
    assert cited == analysis.rule_insights.cited_ids() & set(table["fact_id"])
    assert build_audit_csv(analysis).startswith("\ufefffact_id,label".encode())


def test_data_tab_downloads(analysis):
    from ui.tabs.data_tab import data_dictionary, to_csv_bytes

    dictionary = data_dictionary(analysis.profile.columns)
    assert list(dictionary["column"]) == [c.name for c in analysis.profile.columns]
    assert {"type", "missing_pct", "distinct_values", "summary"} <= set(dictionary.columns)
    text = to_csv_bytes(analysis.profile.df.head(3), analysis.profile.columns).decode("utf-8-sig")
    lines = text.splitlines()
    assert len(lines) == 4 and lines[0].split(",")[0] == analysis.profile.columns[0].name
    if "date" in analysis.profile.df:
        assert " 00:00:00" not in text  # date-only columns keep a plain date


def test_html_report_is_self_contained_and_verified(analysis):
    import re

    from exports.html_report import build_html_report

    doc = build_html_report(analysis).decode("utf-8")
    assert doc.startswith("<!doctype html>")
    assert "<script" not in doc.lower()  # no JavaScript at all
    assert not re.search(r'(src|href)="(https?:)?//(?!veridash\.streamlit\.app)', doc)  # nothing loaded from outside
    assert doc.count("<svg") >= min(len(analysis.charts), 6)
    total = re.search(r"Verified numbers: (\d+)/(\d+)", doc)
    assert total and total.group(1) == total.group(2)  # rule-based text always verifies
    # every link to a fact has a matching row
    for target in set(re.findall(r'href="#(fact-[^"]+)"', doc)):
        assert f'id="{target}"' in doc


def test_html_report_escapes_file_content():
    import pandas as pd

    from core.pipeline import analyze, prepare
    from exports.html_report import build_html_report

    df = pd.DataFrame({"team<script>": ["<i>A</i>", "B", "C"] * 10, "sales": range(30)})
    a = analyze(prepare(df.to_csv(index=False).encode(), "evil<img>.csv"))
    doc = build_html_report(a).decode("utf-8")
    assert "<script>" not in doc and "<img>" not in doc and "<i>A</i>" not in doc
    assert "&lt;i&gt;A&lt;/i&gt;" in doc


def test_html_report_marks_unverified_numbers():
    from core.facts import Fact, FactPack
    from exports.html_report import linked_text

    pack = FactPack({}, [], [Fact("kpi.metric", "Total", 100.0, "number", "kpi")])
    from ai.factcheck import check_text

    text = "Total is 100 but not 250."
    out = linked_text(text, check_text(text, pack), pack)
    assert 'href="#fact-kpi-metric"' in out
    assert 'class="bad"' in out and "(not verified)" in out
